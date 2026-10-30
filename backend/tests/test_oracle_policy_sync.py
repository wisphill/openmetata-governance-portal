import pytest

from app.database.oracle_access_provisioning import OracleAccessProvisioner
from app.database.oracle_policy_sync import OraclePolicySynchronizer
from app.openmetadata.policy_sync import OpenMetadataViewGrant


def test_policy_sync_only_creates_desired_grants_for_explicit_view_mappings(settings):
    settings.oracle_policy_sync_view_map = '{"om.service.db.schema.view":"DWH_PRODUCT.DP_BOOKING_ANALYTICS_V"}'
    sync = OraclePolicySynchronizer(settings)

    desired = sync._desired([
        OpenMetadataViewGrant("d2719c8a-6c97-4b35-b662-e791647b41b3", None, "om.service.db.schema.view"),
        OpenMetadataViewGrant("d2719c8a-6c97-4b35-b662-e791647b41b3", None, "om.service.db.schema.unmapped"),
    ])

    assert len(desired) == 1
    grant = desired.pop()
    assert grant.username == OracleAccessProvisioner.client_username("d2719c8a-6c97-4b35-b662-e791647b41b3")
    assert (grant.owner, grant.view) == ("DWH_PRODUCT", "DP_BOOKING_ANALYTICS_V")


@pytest.mark.parametrize("mapping", ["[]", '{"asset":"DWH_PRODUCT; DROP USER X"}', '{"asset": 1}'])
def test_policy_sync_rejects_unsafe_or_invalid_view_map(settings, mapping):
    settings.oracle_policy_sync_view_map = mapping
    with pytest.raises(ValueError):
        OraclePolicySynchronizer(settings)
