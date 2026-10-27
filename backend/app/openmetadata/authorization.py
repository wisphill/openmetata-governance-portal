from app.models.contracts import Identity, MeResponse, RoleSummary
from app.openmetadata.client import OpenMetadataClient


class OpenMetadataAuthorizationService:
    def __init__(self, client: OpenMetadataClient, email: str | None, username: str | None = None) -> None:
        self.client = client
        self.email = email
        self.username = username

    async def get_current_user(self) -> MeResponse:
        lookup_value = self._lookup_value()
        if not lookup_value:
            raise PermissionError("The OIDC token has no configured user mapping claim")
        user = await self._find_user(lookup_value)
        if not user or user.get("isActive", True) is False:
            raise PermissionError("No active OpenMetadata user is mapped to this OIDC identity")
        return await self._to_me_response(user)

    async def get_user_by_email(self, email: str) -> MeResponse | None:
        """Resolve an active OpenMetadata user by their email address."""
        user = await self._find_user_by_field("email", email)
        if not user or user.get("isActive", True) is False:
            return None
        return await self._to_me_response(user)

    async def _to_me_response(self, user: dict) -> MeResponse:
        user = await self.client.get(f"/users/{user['id']}", {"fields": "teams,roles,profile"})
        teams = user.get("teams", [])
        direct_roles = await self._resolve_roles(user.get("roles", []))
        inherited = await self._resolve_roles([role for team in teams for role in team.get("roles", [])])
        is_admin = bool(user.get("isAdmin"))
        if is_admin:
            direct_roles.insert(0, {
                "name": "Administrator",
                "displayName": "Administrator",
                "isBuiltIn": True,
                "source": "openmetadata.isAdmin",
            })
        policies = self._unique_policies(direct_roles + inherited)
        return MeResponse(
            identity=Identity(id=user["id"], username=user.get("name", user["id"]), display_name=user.get("displayName"), email=user.get("email")),
            teams=teams,
            roles=RoleSummary(direct=direct_roles, inherited=inherited),
            policies=policies,
            is_admin=is_admin,
        )

    async def _resolve_roles(self, references: list[dict]) -> list[dict]:
        resolved: list[dict] = []
        seen: set[str] = set()
        for reference in references:
            role_id = reference.get("id")
            if not role_id or role_id in seen:
                continue
            seen.add(role_id)
            resolved.append(await self.client.get(f"/roles/{role_id}", {"fields": "policies"}))
        return resolved

    @staticmethod
    def _unique_policies(roles: list[dict]) -> list[dict]:
        policies: list[dict] = []
        seen: set[str] = set()
        for role in roles:
            for policy in role.get("policies", []):
                key = policy.get("id") or policy.get("name")
                if key and key not in seen:
                    seen.add(key)
                    policies.append(policy)
        return policies

    def _lookup_value(self) -> str | None:
        if self.client.settings.openmetadata_user_lookup_field == "email":
            return self.email
        # Google commonly does not issue `preferred_username`; OpenMetadata
        # installations often use the email local part as their user name.
        return self.username or (self.email.split("@", 1)[0] if self.email else None)

    async def _find_user(self, value: str) -> dict | None:
        return await self._find_user_by_field(self.client.settings.openmetadata_user_lookup_field, value)

    async def _find_user_by_field(self, field: str, value: str) -> dict | None:
        """Use OM's cursor pagination because its Users list API has no identity filter."""
        cursor: str | None = None
        target = value.casefold()
        for _ in range(self.client.settings.openmetadata_user_lookup_max_pages):
            params = {
                "limit": self.client.settings.openmetadata_user_lookup_page_size,
                "fields": "teams,roles,profile",
                "isBot": "false",
                "include": "non-deleted",
            }
            if cursor:
                params["after"] = cursor
            payload = await self.client.get("/users", params)
            user = next((item for item in payload.get("data", []) if str(item.get(field, "")).casefold() == target), None)
            if user:
                return user
            cursor = payload.get("paging", {}).get("after")
            if not cursor:
                return None
        return None
