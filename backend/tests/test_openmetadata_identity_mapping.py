from app.openmetadata.authorization import OpenMetadataAuthorizationService


class StubClient:
    def __init__(self, settings, users):
        self.settings = settings
        self.users = users

    async def get(self, path, params):
        assert path == "/users"
        return {"data": self.users, "paging": {}}


async def test_user_lookup_matches_configured_email_field(settings):
    client = StubClient(settings, [{"id": "user-1", "email": "phi.nguyen3@sotatek.com", "name": "phi.nguyen3"}])

    user = await OpenMetadataAuthorizationService(client, "phi.nguyen3@sotatek.com")._find_user("phi.nguyen3@sotatek.com")

    assert user["id"] == "user-1"


async def test_name_lookup_uses_username_claim_or_email_local_part(settings):
    name_settings = settings.model_copy(update={"openmetadata_user_lookup_field": "name"})
    client = StubClient(name_settings, [{"id": "user-1", "email": "another@example.com", "name": "phi.nguyen3"}])
    service = OpenMetadataAuthorizationService(client, "phi.nguyen3@sotatek.com")

    assert service._lookup_value() == "phi.nguyen3"
    user = await service._find_user(service._lookup_value())

    assert user["id"] == "user-1"


class UserDetailClient(StubClient):
    async def get(self, path, params):
        if path == "/users":
            return {"data": self.users, "paging": {}}
        assert path == "/users/user-1"
        return {"id": "user-1", "name": "phuong", "email": "phuong@example.com", "isActive": True, "teams": [], "roles": []}


async def test_user_access_lookup_always_uses_email(settings):
    name_settings = settings.model_copy(update={"openmetadata_user_lookup_field": "name"})
    client = UserDetailClient(name_settings, [{"id": "user-1", "email": "phuong@example.com", "name": "phuong"}])

    user = await OpenMetadataAuthorizationService(client, "viewer@example.com").get_user_by_email("phuong@example.com")

    assert user is not None
    assert user.identity.email == "phuong@example.com"
