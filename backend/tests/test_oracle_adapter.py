import pytest

from app.database.oracle import OracleAdapter


@pytest.mark.asyncio
async def test_oracle_rejects_identity_not_on_allowlist(settings):
    adapter = OracleAdapter(settings)
    with pytest.raises(PermissionError):
        await adapter.connect("not-allowed@example.com")
