#!/usr/bin/env python3
"""Install reusable Oracle entitlement and application-context infrastructure.

Run as a DBA/provisioning account, never as the portal runtime account. When
the provisioner is not APP, it needs CREATE ANY TABLE, CREATE ANY PROCEDURE,
CREATE ANY CONTEXT, CREATE ANY TRIGGER, DROP ANY TRIGGER, and authority to grant ADMINISTER
DATABASE TRIGGER to APP.

APP receives ADMINISTER DATABASE TRIGGER so it can own the trusted database
logon trigger. APP owns the catalog, entitlement table, and context package.
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

            try:
                run_ddl(cursor, "redaction policy catalog", """
                    CREATE TABLE app.data_redaction_policy_catalog (
                        policy_key VARCHAR2(30) NOT NULL,
                        object_owner VARCHAR2(128) NOT NULL,
                        object_name VARCHAR2(128) NOT NULL,
                        column_name VARCHAR2(128) NOT NULL,
                        default_unmask_level VARCHAR2(7) DEFAULT 'NONE' NOT NULL,
                        partial_mask_rule VARCHAR2(30) DEFAULT 'FIRST_LAST' NOT NULL,
                        enabled CHAR(1) DEFAULT 'Y' NOT NULL,
                        created_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
                        CONSTRAINT data_redaction_policy_catalog_pk PRIMARY KEY (policy_key),
                        CONSTRAINT data_redaction_policy_catalog_uq UNIQUE
                            (object_owner, object_name, column_name),
                        CONSTRAINT data_redaction_policy_catalog_level_ck
                            CHECK (default_unmask_level IN ('NONE', 'PARTIAL', 'FULL')),
                        CONSTRAINT data_redaction_policy_catalog_enabled_ck CHECK (enabled IN ('Y', 'N'))
                    )
                """)
            except oracledb.DatabaseError as exc:
                if "ORA-00955" not in str(exc):
                    raise
                logger.info("Redaction policy catalog already exists")
            try:
                run_ddl(cursor, "active-entitlement lookup index", """
                    CREATE INDEX app.data_redaction_entitlements_active_ix
                    ON app.data_redaction_entitlements
                       (principal_name, enabled, valid_from, valid_until)
                """)
            except oracledb.DatabaseError as exc:
                if "ORA-00955" not in str(exc):
                    raise
                logger.info("Active-entitlement lookup index already exists")
            run_ddl(cursor, "V_ORDER_TOTALS.STATUS catalog seed", """
                MERGE INTO app.data_redaction_policy_catalog catalog
                USING (SELECT 'APP_V_ORDER_TOTALS_STATUS' policy_key FROM dual) source
                ON (catalog.policy_key = source.policy_key)
                WHEN MATCHED THEN UPDATE SET
                    object_owner = 'APP', object_name = 'V_ORDER_TOTALS', column_name = 'STATUS',
                    default_unmask_level = 'NONE', partial_mask_rule = 'FIRST_LAST', enabled = 'Y'
                WHEN NOT MATCHED THEN INSERT
                    (policy_key, object_owner, object_name, column_name, default_unmask_level, partial_mask_rule, enabled)
                VALUES
                    ('APP_V_ORDER_TOTALS_STATUS', 'APP', 'V_ORDER_TOTALS', 'STATUS', 'NONE', 'FIRST_LAST', 'Y')
            """)

            run_ddl(cursor, "trusted context package specification", """
                CREATE OR REPLACE PACKAGE app.redaction_context_pkg AUTHID DEFINER AS
                  PROCEDURE load_session_entitlements;
                END;
            """)
            run_ddl(cursor, "trusted context package body", """
                CREATE OR REPLACE PACKAGE BODY app.redaction_context_pkg AS
                  PROCEDURE load_session_entitlements IS
                  BEGIN
                    FOR entitlement IN (
                      SELECT catalog.policy_key, entitlement.unmask_level
                      FROM app.data_redaction_entitlements entitlement
                      JOIN app.data_redaction_policy_catalog catalog
                        ON catalog.object_owner = entitlement.object_owner
                       AND catalog.object_name = entitlement.object_name
                       AND catalog.column_name = entitlement.column_name
                      WHERE entitlement.principal_name = SYS_CONTEXT('USERENV', 'SESSION_USER')
                        AND entitlement.enabled = 'Y'
                        AND entitlement.valid_from <= SYSTIMESTAMP
                        AND (entitlement.valid_until IS NULL OR entitlement.valid_until > SYSTIMESTAMP)
                        AND catalog.enabled = 'Y'
                    ) LOOP
                      DBMS_SESSION.SET_CONTEXT('APP_REDACTION_CTX', entitlement.policy_key, entitlement.unmask_level);
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
        connection.commit()
        logger.info("Entitlement setup complete")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(main())
