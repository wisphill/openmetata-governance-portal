from app.openmetadata.tasks import OpenMetadataTaskService


class StubClient:
    def __init__(self, settings):
        self.settings = settings
        self.calls = []

    async def get(self, path, params):
        self.calls.append((path, params))
        if len(self.calls) == 1:
            return {"data": [
                {"id": "mine-1", "name": "portal-access-user-1-one", "createdById": "bot", "type": "DataAccessRequest", "status": "Open", "createdAt": 1_700_000_000_000, "payload": {"reason": "Monthly reporting"}},
                {"id": "other-1", "name": "portal-access-user-2-one", "createdById": "bot", "type": "DataAccessRequest", "status": "Open"},
            ], "paging": {"after": "next"}}
        return {"data": [{"id": "mine-2", "name": "portal-access-user-1-two", "createdBy": {"id": "bot"}, "type": "DataAccessRequest", "status": "Approved"}], "paging": {}}


async def test_created_tasks_are_derived_from_the_authenticated_user(settings):
    client = StubClient(settings)

    page = await OpenMetadataTaskService(client, "user-1").list_created_tasks(page=1, page_size=20)

    assert [task.id for task in page.items] == ["mine-1", "mine-2"]
    assert page.items[0].reason == "Monthly reporting"
    assert page.total == 2
    assert all(path == settings.openmetadata_access_request_task_path for path, _ in client.calls)
    assert client.calls[0][1]["q"] == "portal-access-user-1"
