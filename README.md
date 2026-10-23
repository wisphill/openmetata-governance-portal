# OpenMetadata Governance Portal

A two-application starter for a governance portal that shares an OIDC identity provider with OpenMetadata. The portal is a thin BFF: OpenMetadata remains authoritative for users, roles, policies, task visibility, and resource permissions.

## Layout

- `backend/` — FastAPI OIDC BFF, OpenMetadata adapter, and pluggable database adapters.
- `frontend/` — React + TypeScript UI with English and Vietnamese translations.

## Security model

1. `GET /auth/login` starts Authorization Code + PKCE and saves `state` and `code_verifier` in a short-lived in-memory session.
2. `/auth/callback` exchanges the code server-side, validates the ID token against issuer JWKS/audience, then maps the validated identity to an OpenMetadata user.
3. Before session creation, the backend uses the server-only `OM_ADMIN_BOT_TOKEN` to find an active OpenMetadata user with the configured Google email claim. An unmapped or disabled user is redirected to `/access-denied`.
4. The browser receives only an opaque, HMAC-signed, `HttpOnly` session cookie. Google credentials are discarded after identity verification; OpenMetadata calls use the server-only admin-bot token.
5. Routes derive the OpenMetadata identity and task assignee from the validated portal session. The portal admission gate is not a substitute for narrowly scoped OpenMetadata permissions.

The default session store is intentionally in memory because this release has no portal database. Run a single backend replica, or replace `SessionStore` with a shared encrypted session implementation before scaling horizontally.

## Run locally

```bash
cp backend/.env.example backend/.env
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8000

cd ../frontend && npm install && npm run dev
```

Configure an IdP and an OpenMetadata instance before signing in. This deployment uses `OM_ADMIN_BOT_TOKEN` for backend-to-OpenMetadata calls; never expose it to the browser, source control, or application logs. The portal allows sign-in only for an active, mapped OpenMetadata user.

For Google OIDC, set `OIDC_AUDIENCE` to the Google OAuth client ID, or leave it empty to validate against `OIDC_CLIENT_ID` automatically.

`POST /api/database/query` is deliberately disabled unless `DATABASE_QUERIES_ENABLED=true`; it supports parameterized, read-only SQL through an Oracle proxy session. Configure proxy grants and the identity allowlist in Oracle—never accept a database username from the browser.

## Delivery flow

The backend and frontend use different deployment targets:

- **Backend:** CI builds and pushes the `backend/Dockerfile` image, then updates the immutable image tag in the Kubernetes GitOps manifests. Argo CD watches those manifests and syncs the backend workload. Argo CD does not build container images itself.
- **Frontend:** Cloudflare Pages builds and publishes the static React bundle from Git. It is outside the Kubernetes/Argo CD reconciliation loop. Use Cloudflare Pages Git integration for production; the Makefile also offers a direct-upload target for an authorized CI job.

### Backend image

```bash
make -C backend test
make -C backend build IMAGE=registry.example.com/governance-portal/backend TAG=<immutable-tag>
make -C backend push IMAGE=registry.example.com/governance-portal/backend TAG=<immutable-tag>
```

The deployment manifest should reference the same immutable image tag. `make -C backend run` expects `backend/.env` and is intended only for local verification.

### Cloudflare Pages frontend

Create a Cloudflare Pages project from the repository with these build settings:

| Setting | Value |
| --- | --- |
| Production branch | `main` (or the repository's release branch) |
| Root directory | `frontend` |
| Build command | `npm run build` |
| Build output directory | `dist` |

Set `VITE_API_URL` in Cloudflare Pages to the public HTTPS backend origin, for example `https://api.example.com`. This value is compiled into browser JavaScript, so it must not be secret. Configure the backend's `PORTAL_PUBLIC_URL`, `CORS_ORIGINS`, `OIDC_REDIRECT_URI`, and `OIDC_LOGOUT_URI` to use the final Pages domain.

For a direct upload from an authorized CI environment, provide a scoped `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`, then run:

```bash
make -C frontend install
make -C frontend pages-deploy PAGES_PROJECT=<pages-project> PAGES_BRANCH=main
```

Do not place Cloudflare or OpenMetadata credentials in the repository, a frontend `.env` file, or Kubernetes ConfigMaps.
