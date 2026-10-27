from app.openmetadata.tasks import OpenMetadataTaskService
import pytest


class StubClient:
    def __init__(self, settings):
        self.settings = settings
        self.calls = []

    async def get(self, path, params):
        self.calls.append((path, params))
        if len(self.calls) == 1:
            return {"data": [
                {"id": "mine-1", "name": "portal-access-user-1-one", "createdById": "bot", "type": "DataAccessRequest", "status": "Open", "createdAt": 1_700_000_000_000, "assignees": [{"displayName": "Customer Data Owners"}], "payload": {"reason": "Monthly reporting"}},
                {"id": "other-1", "name": "portal-access-user-2-one", "createdById": "bot", "type": "DataAccessRequest", "status": "Open"},
            ], "paging": {"after": "next"}}
        return {"data": [{"id": "mine-2", "name": "portal-access-user-1-two", "createdBy": {"id": "bot"}, "type": "DataAccessRequest", "status": "Approved"}], "paging": {}}


async def test_created_tasks_are_derived_from_the_authenticated_user(settings):
    client = StubClient(settings)

    page = await OpenMetadataTaskService(client, "user-1").list_created_tasks(page=1, page_size=20)

    assert [task.id for task in page.items] == ["mine-1", "mine-2"]
    assert page.items[0].reason == "Monthly reporting"
    assert page.items[0].assignees == ["Customer Data Owners"]
    assert page.total == 2
    assert all(path == settings.openmetadata_access_request_task_path for path, _ in client.calls)
    assert client.calls[0][1]["q"] == "portal-access-user-1"
    assert "assignees" in client.calls[0][1]["fields"]


class CancelStubClient:
    def __init__(self, settings, task):
        self.settings = settings
        self.task = task
        self.closed = None

    async def get(self, path, params=None):
        return self.task

    async def post(self, path, payload):
        self.closed = (path, payload)
        return payload


@pytest.mark.asyncio
async def test_created_request_can_be_cancelled_by_its_requester(settings):
    client = CancelStubClient(settings, {"id": "task-1", "name": "portal-access-user-1-one", "status": "Open"})

    await OpenMetadataTaskService(client, "user-1").cancel_created_task("task-1")

    assert client.closed == ("/tasks/task-1/close", {})


@pytest.mark.asyncio
async def test_cannot_cancel_another_users_request(settings):
    client = CancelStubClient(settings, {"id": "task-2", "name": "portal-access-user-2-one", "status": "Open"})

    with pytest.raises(PermissionError):
        await OpenMetadataTaskService(client, "user-1").cancel_created_task("task-2")


@pytest.mark.asyncio
async def test_created_request_detail_exposes_normalized_access_scope(settings):
    client = CancelStubClient(settings, {
        "id": "task-1", "name": "portal-access-user-1-one", "status": "Open", "assignees": [{"displayName": "Data Owners"}],
        "about": {"name": "ORDERS", "fullyQualifiedName": "oracle.freepdb1.app.ORDERS"},
        "payload": {"accessType": "ColumnLevel", "requestedAccess": "Read", "columns": ["order_id", "status"], "reason": "Reporting", "expirationDate": 1_700_000_000_000},
    })

    detail = await OpenMetadataTaskService(client, "user-1").get_created_task("task-1")

    assert detail.table_fully_qualified_name == "oracle.freepdb1.app.ORDERS"
    assert detail.database == "freepdb1"
    assert detail.schema_name == "app"
    assert detail.access_level == "Read"
    assert detail.columns == ["order_id", "status"]
