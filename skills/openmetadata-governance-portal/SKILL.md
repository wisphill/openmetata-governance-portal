---
name: openmetadata-governance-portal
description: Build or change a secure FastAPI + React/TypeScript governance portal that uses OpenMetadata for users, roles, policies, and tasks; not for generic OpenMetadata client work or unrelated CRUD apps.
---

# OpenMetadata Governance Portal

Use this skill for portal features that cross identity, OpenMetadata authorization, database access, backend APIs, and the React UI. Keep the portal a thin, well-tested integration layer: OIDC authenticates the person, OpenMetadata remains the source of truth for governance authorization, and the portal owns only presentation and narrowly scoped orchestration.

## Core invariants

- Validate OIDC tokens against the configured issuer, audience, signature keys, expiry, and required scopes. Never trust identity or roles supplied only by the browser.
- Map the OIDC subject/email to the OpenMetadata user explicitly and handle an unmapped or disabled user as an authorization failure.
- Delegate role, policy, resource, and operation decisions to OpenMetadata. Do not create a parallel portal RBAC model or infer permissions from UI visibility.
- Keep OpenMetadata API version differences behind a small client/adapter boundary. Preserve pagination, error status, and request correlation information.
- Forward only the minimum required identity/access context to downstream services. Never log tokens, client secrets, database passwords, or raw authorization headers.
- Make backend authorization checks enforceable independently of the React route guard. UI guards are usability, not security.
- Prefer typed, normalized portal contracts over leaking OpenMetadata response shapes to the frontend.

## Routing

Read only the references relevant to the current change:

- OIDC login, PKCE, token validation, refresh, logout, CORS/cookies, or security review: [references/identity-security.md](references/identity-security.md).
- OpenMetadata users, teams, roles, policies, permissions, API compatibility, or task querying: [references/openmetadata.md](references/openmetadata.md).
- FastAPI dependencies, service boundaries, task endpoint normalization, Oracle proxying, or database adapters: [references/backend-data.md](references/backend-data.md).
- React routing/auth state, protected pages, API client, or English/Vietnamese localization: [references/frontend.md](references/frontend.md).
- Test strategy, mocks/contracts, Dockerfiles, health/readiness, or Kubernetes configuration: [references/testing-operations.md](references/testing-operations.md).

## Delivery behavior

Before changing code, locate the existing configuration, API contracts, OpenMetadata version, and test conventions. State assumptions when a deployment-specific value is missing. Implement the smallest vertical slice, then add or update tests at the affected boundaries. For external integrations, use dependency injection and deterministic mocks so unit tests do not require a live IdP, OpenMetadata server, Oracle instance, or browser.

For a new endpoint, define its authorization question first: who is the current OpenMetadata user, what resource/operation is being checked, and what normalized response is safe to expose? For a UI feature, wire auth state and i18n through existing providers rather than adding ad hoc local storage, hardcoded labels, or a second API client.
