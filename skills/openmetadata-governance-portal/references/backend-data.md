# FastAPI backend and database adapters

Use this reference for backend service design, task APIs, Oracle proxy sessions, and future database implementations.

## FastAPI shape

- Use dependency injection for settings, OIDC verifier/session, current user, OpenMetadata client, database adapter, and service objects.
- Keep routers thin: parse/validate Pydantic input, call a service, and map domain errors to stable HTTP responses.
- Use async I/O for external HTTP and database operations when the selected drivers support it. Set explicit connect/read timeouts and close clients/pools on application shutdown.
- Separate transport schemas from domain models and upstream OpenMetadata DTOs. Avoid returning ORM or vendor objects directly.
- Make error handling consistent with a correlation id and safe detail message; do not leak stack traces or secrets.

## DatabaseAdapter

Define a small interface around the portal's actual business operations, not around every Oracle API. Keep `DatabaseAdapter` implementation-agnostic so Oracle is the first implementation and MySQL can be added without changing route/service contracts. Use typed inputs/outputs, explicit transaction boundaries, parameter binding, and a capability/error model for operations that differ by engine.

## Oracle proxy authentication

- Use the approved Python Oracle driver and a bounded connection pool.
- Isolate credential acquisition/configuration from request handlers. A proxy session must map the validated application identity to an allowlisted Oracle user; never accept an arbitrary proxy username from the request.
- Acquire/release pooled connections safely, reset session state before reuse, and avoid putting passwords or connect descriptors in logs.
- Make proxy behavior testable behind an injected factory; contract tests should cover mapping, denied identities, pool exhaustion, rollback, and cleanup.

## Task API normalization

The portal task endpoint should derive the assignee from the current user, apply validated filters, call the OpenMetadata service, and return a stable envelope with items plus pagination. Keep upstream status/type values intact and put presentation labels in the frontend i18n resources.
