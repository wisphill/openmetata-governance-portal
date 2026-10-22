from app.models.contracts import Identity, MeResponse, RoleSummary
from app.openmetadata.client import OpenMetadataClient


class OpenMetadataAuthorizationService:
    def __init__(self, client: OpenMetadataClient, email: str | None) -> None:
        self.client = client
        self.email = email

    async def get_current_user(self) -> MeResponse:
        if not self.email:
            raise PermissionError("The OIDC token has no configured user mapping claim")
        user = await self._find_user_by_email(self.email)
        if not user or user.get("isActive", True) is False:
            raise PermissionError("No active OpenMetadata user is mapped to this OIDC identity")
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

    async def _find_user_by_email(self, email: str) -> dict | None:
        """Use OM's cursor pagination because its Users list API has no email filter."""
        cursor: str | None = None
        target = email.casefold()
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
            user = next((item for item in payload.get("data", []) if item.get("email", "").casefold() == target), None)
            if user:
                return user
            cursor = payload.get("paging", {}).get("after")
            if not cursor:
                return None
        return None
