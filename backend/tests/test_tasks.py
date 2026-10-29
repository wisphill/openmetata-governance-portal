from app.openmetadata.tasks import OpenMetadataTaskService
from app.cache.user_names import MemoryUserNameCache
from app.models.contracts import TaskResolutionRequest
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


class AssignedTaskStubClient:
    def __init__(self, settings):
        self.settings = settings
        self.calls = []

    async def get(self, path, params):
        self.calls.append((path, params))
        return {"data": [
            {"id": "assigned-1", "taskId": "TASK-00043", "type": "DataAccessRequest", "status": "Open", "assignees": [{"id": "user-1", "displayName": "Alice"}]},
            {"id": "cancelled-1", "taskId": "TASK-00042", "type": "DataAccessRequest", "status": "Cancelled", "assignees": [{"id": "user-1", "displayName": "Alice"}]},
            {"id": "other-1", "taskId": "TASK-00044", "type": "DataAccessRequest", "status": "Open", "assignees": [{"id": "user-2", "displayName": "Bob"}]},
        ], "paging": {}}


@pytest.mark.asyncio
async def test_assigned_tasks_are_filtered_by_openmetadata_identity(settings):
    client = AssignedTaskStubClient(settings)

    page = await OpenMetadataTaskService(client, "user-1").list_tasks(page=1, page_size=20, status_filter=None, task_type=None)

    assert [task.request_id for task in page.items] == ["TASK-00043"]
    assert page.items[0].assignees == ["Alice"]
    assert client.calls[0][0] == settings.openmetadata_tasks_path
    assert client.calls[0][1]["status"] == "Open"


class RequesterNameStubClient:
    def __init__(self, settings):
        self.settings = settings
        self.user_reads = 0

    async def get(self, path, params):
        if path == self.settings.openmetadata_tasks_path:
            return {"data": [{"id": "assigned-1", "taskId": "TASK-00043", "status": "Open", "createdById": "creator-1", "assignees": [{"id": "user-1"}]}], "paging": {}}
        if path == "/users/creator-1":
            self.user_reads += 1
            return {"id": "creator-1", "displayName": "Request Owner"}
        raise AssertionError(path)


@pytest.mark.asyncio
async def test_requester_names_are_aggregated_and_cached(settings):
    client = RequesterNameStubClient(settings)
    service = OpenMetadataTaskService(client, "user-1", MemoryUserNameCache())

    first = await service.list_tasks(page=1, page_size=20, status_filter=None, task_type=None)
    second = await service.list_tasks(page=1, page_size=20, status_filter=None, task_type=None)

    assert first.items[0].requester == "Request Owner"
    assert second.items[0].requester == "Request Owner"
    assert client.user_reads == 1


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
        "resolution": {"type": "Rejected", "comment": "Access is limited to the finance team."},
    })

    detail = await OpenMetadataTaskService(client, "user-1").get_created_task("task-1")

    assert detail.table_fully_qualified_name == "oracle.freepdb1.app.ORDERS"
    assert detail.database == "freepdb1"
    assert detail.schema_name == "app"
    assert detail.access_level == "Read"
    assert detail.columns == ["order_id", "status"]
    assert detail.resolution_type == "Rejected"
    assert detail.resolution_comment == "Access is limited to the finance team."


class ResolveStubClient:
    def __init__(self, settings, task):
        self.settings = settings
        self.task = task
        self.resolutions = []

    async def get(self, path, params=None):
        return self.task

    async def post(self, path, payload):
        self.resolutions.append((path, payload))
        transition = payload.get("transitionId")
        if transition == "approve":
            if self.task.get("type") == self.settings.openmetadata_data_product_publication_task_type:
                return {**self.task, "status": "Approved", "availableTransitions": [{"id": "grant"}]}
            return {**self.task, "status": "Approved", "availableTransitions": [{"id": "grant"}, {"id": "fail"}]}
        if transition == "grant":
            return {**self.task, "status": "Granted"}
        if transition == "reject":
            return {**self.task, "status": "Rejected"}
        return {**self.task, "status": payload["resolutionType"]}


@pytest.mark.asyncio
async def test_assignee_can_resolve_task_with_comment(settings):
    client = ResolveStubClient(settings, {
        "id": "task-43", "type": settings.openmetadata_access_request_task_type, "status": "Pending", "createdById": "d2719c8a-6c97-4b35-b662-e791647b41b3",
        "assignees": [{"id": "user-1"}],
        "about": {"fullyQualifiedName": "oracle.freepdb1.app.ORDERS"},
        "payload": {"accessType": "FullAccess", "columns": []},
        "availableTransitions": [{"id": "approve"}, {"id": "reject"}],
    })
    resolved = await OpenMetadataTaskService(client, "user-1", settings=settings).resolve_assigned_task(
        "task-43", TaskResolutionRequest(resolution_type="Approved", comment="Approved for reporting"),
    )

    assert resolved.status == "Granted"
    assert client.resolutions == [
        ("/tasks/task-43/resolve", {"transitionId": "approve", "comment": "Approved for reporting"}),
        ("/tasks/task-43/resolve", {"transitionId": "grant", "comment": "Access granted in OpenMetadata."}),
    ]


@pytest.mark.asyncio
async def test_non_assignee_cannot_resolve_task(settings):
    client = ResolveStubClient(settings, {"id": "task-43", "status": "Open", "assignees": [{"id": "user-2"}]})

    with pytest.raises(PermissionError):
        await OpenMetadataTaskService(client, "user-1").resolve_assigned_task(
            "task-43", TaskResolutionRequest(resolution_type="Rejected", comment="Not approved"),
        )
