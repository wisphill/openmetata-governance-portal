# Testing and operations

Use this reference for tests, containers, and Kubernetes delivery.

## Tests

- Unit-test token validation/mapping, authorization decisions at the client boundary, service error translation, task normalization, adapter behavior, and i18n-rendered states.
- Mock OIDC discovery/JWKS and token exchange deterministically; include expired, wrong issuer/audience, missing scope, unmapped user, and refresh failure cases.
- Mock OpenMetadata responses for pagination, direct/inherited policy cases, 401/403/404/409/429/5xx, unknown task values, and version-shape differences.
- Add contract tests for `DatabaseAdapter` that every implementation must pass. Keep Oracle-specific proxy/pool tests separate from pure service tests.
- Add frontend API/component tests for protected routes, access denied, task filters/pagination, loading/empty/error states, and `en`/`vi` resources. Use end-to-end tests only for a small number of cross-system flows.
- Include cross-user assignee-tampering tests, cache/session isolation tests, direct-API authorization bypass tests, and safe-link/data-boundary tests.

## Containers and Kubernetes

- Keep images minimal, non-root, reproducible, and free of secrets. Pin base/runtime dependencies according to project conventions.
- Separate build-time and runtime configuration. Inject issuer/audience, OpenMetadata URL/version, database settings, CORS origins, and log level through environment/config; mount secrets through the platform's secret mechanism.
- Expose a cheap liveness endpoint and a readiness endpoint that reflects required dependency/configuration state without leaking credentials. Make startup/shutdown and pool cleanup deterministic.
- Define resource requests/limits, graceful termination, security context, and network/egress policy appropriate to the deployment. Do not put secrets in ConfigMaps, Docker layers, or Helm values committed to source.
- Keep migrations, rollout compatibility, and health checks backward-compatible during staged deployment. Verify the deployed OpenMetadata API version before enabling version-sensitive features.
