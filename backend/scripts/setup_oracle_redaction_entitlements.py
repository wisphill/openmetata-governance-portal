#!/usr/bin/env python3
"""Install Oracle entitlement-backed STATUS redaction for APP.V_ORDER_TOTALS.

Levels: NONE (****), PARTIAL (first and last character), FULL (original).
The trusted application context is populated at database logon.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)


def run_ddl(cursor: Any, label: str, statement: str) -> None:
    logger.info("Applying: %s", label)
    cursor.execute(statement)


def main() -> int:
    os.chdir(SCRIPT_ROOT)
    sys.path.insert(0, str(SCRIPT_ROOT))
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
            try:
                run_ddl(cursor, "entitlement table", """
                    CREATE TABLE app.data_redaction_entitlements (
                        principal_name VARCHAR2(128) NOT NULL,
                        object_owner VARCHAR2(128) NOT NULL,
                        object_name VARCHAR2(128) NOT NULL,
                        column_name VARCHAR2(128) NOT NULL,
                        unmask_level VARCHAR2(7) NOT NULL,
                        enabled CHAR(1) DEFAULT 'Y' NOT NULL,
                        valid_from TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
                        valid_until TIMESTAMP NULL,
                        created_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
                        created_by VARCHAR2(128) DEFAULT SYS_CONTEXT('USERENV', 'SESSION_USER') NOT NULL,
                        CONSTRAINT data_redaction_entitlements_pk PRIMARY KEY
                            (principal_name, object_owner, object_name, column_name),
                        CONSTRAINT data_redaction_entitlements_level_ck
                            CHECK (unmask_level IN ('NONE', 'PARTIAL', 'FULL')),
                        CONSTRAINT data_redaction_entitlements_enabled_ck CHECK (enabled IN ('Y', 'N')),
                        CONSTRAINT data_redaction_entitlements_window_ck
                            CHECK (valid_until IS NULL OR valid_until > valid_from)
                    )
                """)
            except oracledb.DatabaseError as exc:
                if "ORA-00955" not in str(exc):
                    raise
                logger.info("Entitlement table already exists")

            run_ddl(cursor, "trusted context package specification", """
                CREATE OR REPLACE PACKAGE app.redaction_context_pkg AUTHID DEFINER AS
                  PROCEDURE load_session_entitlements;
                END;
            """)
            run_ddl(cursor, "trusted context package body", """
                CREATE OR REPLACE PACKAGE BODY app.redaction_context_pkg AS
                  PROCEDURE load_session_entitlements IS
                    l_attribute VARCHAR2(30);
                  BEGIN
                    DBMS_SESSION.SET_CONTEXT('APP_REDACTION_CTX', 'APP_V_ORDER_TOTALS_STATUS', 'NONE');
                    FOR entitlement IN (
                      SELECT object_owner, object_name, column_name, unmask_level
                      FROM app.data_redaction_entitlements
                      WHERE principal_name = SYS_CONTEXT('USERENV', 'SESSION_USER')
                        AND enabled = 'Y'
                        AND valid_from <= SYSTIMESTAMP
                        AND (valid_until IS NULL OR valid_until > SYSTIMESTAMP)
                    ) LOOP
                      l_attribute := SUBSTR(
                        REGEXP_REPLACE(
                          entitlement.object_owner || '_' || entitlement.object_name || '_' || entitlement.column_name,
                          '[^A-Z0-9_]', '_'
                        ),
                        1,
                        30
                      );
                      DBMS_SESSION.SET_CONTEXT('APP_REDACTION_CTX', l_attribute, entitlement.unmask_level);
                    END LOOP;
                  END;
                END;
            """)
            run_ddl(cursor, "database-trigger privilege for APP", "GRANT ADMINISTER DATABASE TRIGGER TO APP")
            try:
                run_ddl(cursor, "trusted application context", """
                    CREATE CONTEXT app_redaction_ctx USING app.redaction_context_pkg
                """)
            except oracledb.DatabaseError as exc:
                if "ORA-44303" not in str(exc) and "ORA-00955" not in str(exc):
                    raise
                logger.info("Trusted application context already exists")
            try:
                run_ddl(cursor, "obsolete SYSTEM logon trigger cleanup", "DROP TRIGGER system.app_redaction_context_on_logon")
            except oracledb.DatabaseError as exc:
                if "ORA-04080" not in str(exc):
                    raise
            run_ddl(cursor, "database logon trigger", """
                CREATE OR REPLACE TRIGGER app.app_redaction_context_on_logon
                AFTER LOGON ON DATABASE
                BEGIN
                  redaction_context_pkg.load_session_entitlements;
                EXCEPTION
                  WHEN OTHERS THEN
                    NULL; -- fail closed: the view defaults to the NONE mask.
                END;
            """)
            run_ddl(cursor, "context-aware security view", """
                CREATE OR REPLACE VIEW app.v_order_totals AS
                SELECT o.order_id,
                       o.customer_id,
                       CASE SYS_CONTEXT('APP_REDACTION_CTX', 'APP_V_ORDER_TOTALS_STATUS')
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
                run_ddl(cursor, "removing static STATUS policy", """
                    BEGIN
                      DBMS_REDACT.ALTER_POLICY(
                        object_schema => 'APP', object_name => 'V_ORDER_TOTALS',
                        policy_name => 'V_ORDER_TOTALS_ORDER_TOTAL_DDM',
                        action => DBMS_REDACT.DROP_COLUMN, column_name => 'STATUS'
                      );
                    END;
                """)
        connection.commit()
        logger.info("Entitlement setup complete")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(main())
