#!/usr/bin/env python3
"""Apply the entitlement-aware STATUS migration for APP.V_ORDER_TOTALS.

Run after setup_oracle_redaction_entitlements.py. This migration is intentionally
specific to one view; it does not rewrite unrelated published views.

Run as APP, or as a DBA/provisioning account with CREATE ANY VIEW, EXECUTE on
DBMS_REDACT, and the object/administrative privileges required to alter the
redaction policy on APP.V_ORDER_TOTALS. Reading SYS.REDACTION_COLUMNS requires
SELECT_CATALOG_ROLE or direct SELECT access to that view.
"""

import logging
import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)


def main() -> int:
    os.chdir(BACKEND_ROOT)
    sys.path.insert(0, str(BACKEND_ROOT))
    from app.config import get_settings
    import oracledb

    settings = get_settings()
    if not all((settings.oracle_dsn, settings.oracle_provisioner_user, settings.oracle_provisioner_password)):
        raise RuntimeError("ORACLE_DSN, ORACLE_PROVISIONER_USER, and ORACLE_PROVISIONER_PASSWORD must be configured")

    connection = oracledb.connect(
        user=settings.oracle_provisioner_user,
        password=settings.oracle_provisioner_password,
        dsn=settings.oracle_dsn,
    )
    try:
        with connection.cursor() as cursor:
            logger.info("Replacing APP.V_ORDER_TOTALS with entitlement-aware STATUS masking")
            cursor.execute("""
                CREATE OR REPLACE VIEW app.v_order_totals AS
                SELECT o.order_id,
                       o.customer_id,
                       CASE NVL(SYS_CONTEXT('APP_REDACTION_CTX', 'APP_V_ORDER_TOTALS_STATUS'), 'NONE')
                         WHEN 'FULL' THEN o.status
                         WHEN 'PARTIAL' THEN CASE
                           WHEN o.status IS NULL THEN NULL
                           WHEN LENGTH(o.status) <= 2 THEN RPAD('*', LENGTH(o.status), '*')
                           ELSE SUBSTR(o.status, 1, 1) || RPAD('*', LENGTH(o.status) - 2, '*') || SUBSTR(o.status, -1)
                         END
                         ELSE '****'
                       END AS status,
                       SUM(i.quantity * i.unit_price) AS order_total
                FROM app.orders o
                JOIN app.order_items i ON i.order_id = o.order_id
                GROUP BY o.order_id, o.customer_id, o.status
            """)
            cursor.execute("""
                SELECT 1 FROM sys.redaction_columns
                WHERE object_owner = 'APP' AND object_name = 'V_ORDER_TOTALS' AND column_name = 'STATUS'
            """)
            if cursor.fetchone():
                logger.info("Removing static STATUS redaction so the view can apply NONE/PARTIAL/FULL")
                cursor.execute("""
                    BEGIN
                      DBMS_REDACT.ALTER_POLICY(
                        object_schema => 'APP', object_name => 'V_ORDER_TOTALS',
                        policy_name => 'V_ORDER_TOTALS_ORDER_TOTAL_DDM',
                        action => DBMS_REDACT.DROP_COLUMN, column_name => 'STATUS'
                      );
                    END;
                """)
        connection.commit()
        logger.info("V_ORDER_TOTALS STATUS migration complete")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(main())
