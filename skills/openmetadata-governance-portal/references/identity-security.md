# Identity and security

Use this reference for OIDC/OAuth2 and security changes.

## Authentication flow

- Use Authorization Code + PKCE for browser login. Generate a high-entropy `state` and `code_verifier`, bind them to the user session, and verify `state` on callback.
- Discover issuer metadata or use configured endpoints; validate the ID/access token against the configured issuer and audience, signature algorithm, JWKS, `exp`, `nbf` when present, and required scopes.
- Treat the OIDC `sub` as the stable identity key. Use email only as a deliberate mapping attribute and document collision/rename behavior.
- Resolve the mapped OpenMetadata user server-side. Do not accept a client-provided user id, team, role, or permission set.
- Define one exact mapping rule for the deployment: prefer an immutable OIDC `sub` mapping; if email is used for migration or lookup, handle case normalization, collisions, rename, disabled, and unmapped states explicitly. Return a deliberate 401/403 according to whether the session is invalid or the identity is known but not allowed.
- Keep access/refresh tokens in the least exposed mechanism supported by the deployment. If cookies are used, use `HttpOnly`, `Secure`, and an explicit `SameSite` policy; protect state-changing requests from CSRF.
- Refresh on the server or through a narrowly scoped auth service. Rotate/revoke refresh tokens according to the provider contract and make logout clear local session state plus provider session when supported.

## Web/API controls

- Enforce authentication and authorization in FastAPI dependencies, not only middleware or React route guards.
- Configure exact CORS origins and allowed headers/methods; never use wildcard origins with credentials.
- Forward an access token to OpenMetadata only when the request needs it, and strip it from logs, exception payloads, tracing baggage, and client-visible errors.
- Choose and document the OpenMetadata credential model per deployment: delegated user access tokens when OpenMetadata must evaluate the signed-in user's permissions, or a narrowly scoped service credential only when OpenMetadata supports an explicit mapped-user/check mechanism. Never silently replace per-user authorization with a broad service account.
- Use parameterized SQL and an allowlist for dynamic identifiers/order fields. Validate request size, pagination bounds, and external URLs.
- Return stable, non-secret error codes to the browser while logging structured diagnostics with request/correlation ids.
- Use least-privilege OIDC scopes, OpenMetadata credentials, Oracle proxy grants, container users, and Kubernetes service accounts.
