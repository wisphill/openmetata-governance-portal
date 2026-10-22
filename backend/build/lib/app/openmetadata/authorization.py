from app.models.contracts import Identity, MeResponse, RoleSummary
from app.openmetadata.client import OpenMetadataClient


class OpenMetadataAuthorizationService:
    def __init__(self, client: OpenMetadataClient, email: str | None) -> None:
        self.client = client
        self.email = email

    async def get_current_user(self) -> MeResponse:
        if not self.email:
            raise PermissionError("The OIDC token has no configured user mapping claim")
        # This field expansion follows common OM v1 entity APIs; retain it inside this boundary for upgrades.
        data = await self.client.get("/users", {"q": self.email, "fields": "teams,roles,profile"})
        users = data.get("data", [])
        user = next((item for item in users if item.get("email", "").lower() == self.email.lower()), None)
        if not user or user.get("isAdmin") is False and user.get("isActive") is False:
            raise PermissionError("No active OpenMetadata user is mapped to this OIDC identity")
        direct_roles = user.get("roles", [])
        teams = user.get("teams", [])
        inherited = [role for team in teams for role in team.get("roles", [])]
        policies = [policy for role in direct_roles + inherited for policy in role.get("policies", [])]
        return MeResponse(
            identity=Identity(id=user["id"], username=user.get("name", user["id"]), display_name=user.get("displayName"), email=user.get("email")),
            teams=teams,
            roles=RoleSummary(direct=direct_roles, inherited=inherited),
            policies=policies,
        )
