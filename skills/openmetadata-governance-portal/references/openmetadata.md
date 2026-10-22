# OpenMetadata integration and authorization

Use this reference when calling or modeling OpenMetadata.

## Source of truth

OpenMetadata owns users, teams, roles, policies, resources, operations, and the effective authorization decision. The portal may cache short-lived read models for display, but must not treat a copied role list as the final permission decision. When an operation is sensitive, re-check with OpenMetadata at request time.

Resolve authorization in this order:

1. Identify the current OpenMetadata user from the validated OIDC identity.
2. Load direct and inherited role/policy relationships using the supported OpenMetadata API for the deployed version.
3. Evaluate the requested resource and operation using OpenMetadata semantics, including team/resource hierarchy and deny behavior if applicable.
4. Return a normalized allow/deny result to the portal service and preserve the upstream denial as a 403, not a generic 500.

Do not reproduce this algorithm from assumptions about role names. If the API exposes a permission/check endpoint, prefer it over reconstructing policy evaluation in portal code.

For task listing, identify the OpenMetadata resource and operation that authorizes viewing the relevant task/entity, and test that decision with the deployed API version. If OpenMetadata provides a permission/check endpoint, use it; if task query authorization is implicit, document that contract and still enforce the authenticated assignee/resource scope. Do not assume that a successful service-account query means the end user is allowed.

## API boundary

- Centralize base URL, API version, auth headers, timeout, retry policy, pagination, and error translation in an injected OpenMetadata client.
- Keep entity DTOs versioned or tolerant at the boundary; map them into small portal schemas.
- Preserve upstream pagination metadata and use bounded page sizes. Do not silently fetch an unbounded collection.
- Distinguish 401 (missing/invalid downstream credentials), 403 (not allowed), 404 (missing entity), 409 (state conflict), 429 (rate limit), and 5xx (upstream failure).
- Retry only idempotent requests and only for transient failures with bounded backoff. Never retry authorization failures.
- Record the OpenMetadata version and endpoint assumptions in configuration/tests so upgrades fail visibly.

## Tasks

Query tasks assigned to the current OpenMetadata user, then normalize fields such as task id, type, status, entity reference, assignee, timestamps, and links. Filtering should be explicit and bounded: status/type/entity plus configured page size, maximum page size, and stable sort order. A “my tasks” endpoint must derive assignee from the authenticated mapping and reject or ignore a client-supplied assignee filter; an admin-wide endpoint needs a separate authorization contract. Preserve unknown task types/statuses for forward compatibility instead of dropping them. Expose only fields required by the portal, and allowlist/sanitize entity links rather than reflecting arbitrary upstream URLs.
