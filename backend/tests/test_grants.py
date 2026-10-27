from app.openmetadata.grants import OpenMetadataGrantedAccessService


class StubClient:
    async def get(self, path, params):
        assert path == "/tasks/dataAccessRequests"
        assert params["status"] in {"Approved", "Granted"}
        if "requestedById" in params and params["status"] == "Approved":
            return {"data": [{
                "id": "grant-1", "taskId": "TASK-7", "about": {"id": "table-1", "name": "CUSTOMERS", "fullyQualifiedName": "db.schema.CUSTOMERS"},
                "payload": {"accessType": "ColumnLevel", "requestedAccess": "Read", "columns": ["db.schema.CUSTOMERS.EMAIL"], "expirationDate": 1_800_000_000_000},
                "approvedAt": 1_700_000_000_000,
            }]}
        return {"data": []}


async def test_granted_access_exposes_table_column_scope_and_permission():
    page = await OpenMetadataGrantedAccessService(StubClient(), "user-1").list_granted()

    assert page.total == 1
    assert page.items[0].table_name == "CUSTOMERS"
    assert page.items[0].access_type == "ColumnLevel"
    assert page.items[0].columns == ["db.schema.CUSTOMERS.EMAIL"]


async def test_granted_access_checks_approved_and_granted_statuses_for_openmetadata_compatibility():
    class StatusClient:
        def __init__(self):
            self.statuses = []

        async def get(self, path, params):
            self.statuses.append(params["status"])
            return {"data": []}

    client = StatusClient()
    await OpenMetadataGrantedAccessService(client, "user-1").list_granted()

    assert set(client.statuses) == {"Approved", "Granted"}
