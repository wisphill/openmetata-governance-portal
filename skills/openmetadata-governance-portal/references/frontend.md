# React, TypeScript, and i18n

Use this reference for the portal UI.

- Keep one typed API client and one auth/session state source. Centralize handling for 401, 403, refresh, cancellation, and API error envelopes.
- Use protected routes for navigation and loading states, but assume every backend endpoint independently enforces access.
- Type normalized portal contracts rather than OpenMetadata vendor payloads. Handle loading, empty, error, unauthorized, and stale states explicitly.
- Keep profile/access pages focused on effective access explanation: show source/evidence from OpenMetadata where available, never claim permission solely because a route rendered. Treat an access-explanation page as distinct from the generic 403/access-denied state.
- Use `react-i18next` with organized namespaces and `en`/`vi` resources. Do not hardcode user-visible text, status labels, task types, dates, or error messages in components.
- Use stable translation keys and interpolate values safely. Format dates, numbers, and status badges through shared helpers so locale changes do not alter API semantics.
- Avoid persisting tokens in ordinary local storage. Prefer the server/session mechanism selected by the security design.
- Provide an explicit fallback locale and translation keys for unknown task types/statuses. Locale selection/persistence belongs to the established app preference/session mechanism, not ad hoc component storage.
