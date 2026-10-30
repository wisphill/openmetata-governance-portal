#!/usr/bin/env python3
"""Smoke-test Oracle Data Redaction on APP.V_ORDER_TOTALS.

The script creates a temporary least-privilege user, grants it access only to
the published view, and verifies that every published column is redacted. The
user is dropped on every exit path. Credentials and unredacted source values
are never written to logs.

Run as a dedicated test provisioner. It needs CREATE USER, DROP USER, GRANT
CREATE SESSION, and GRANT SELECT ON APP.V_ORDER_TOTALS. It also needs SELECT on
APP.ORDERS only to calculate the expected result in memory, plus
SELECT_CATALOG_ROLE or direct SELECT access to SYS.REDACTION_POLICIES and
SYS.REDACTION_COLUMNS for policy preflight. Do not run it as SYS or APP.
"""

import logging
import os
import secrets
import sys
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
POLICY_NAME = "V_ORDER_TOTALS_ORDER_TOTAL_DDM"
VIEW_OWNER = "APP"
VIEW_NAME = "V_ORDER_TOTALS"
REDACTED_COLUMNS = {
    "ORDER_ID": "FULL REDACTION",
    "CUSTOMER_ID": "FULL REDACTION",
    "ORDER_TOTAL": "FULL REDACTION",
}

logger = logging.getLogger(__name__)


def quote_identifier(value: str) -> str:
    """Safely quote a generated Oracle identifier."""
    return '"' + value.replace('"', '""') + '"'


def temporary_username() -> str:
    # Oracle identifiers are restricted to 30 bytes on older supported
    # versions. The generated name is ASCII and well below that limit.
    return f"DDM_TEST_{secrets.token_hex(8).upper()}"


def temporary_password() -> str:
    # token_urlsafe contains only characters valid in a quoted password and
    # avoids logging a credential that could be used after the test.
    return secrets.token_urlsafe(32)


def execute(cursor: Any, statement: str, operation: str) -> None:
    # Do not log the statement itself: CREATE USER includes the temporary
    # password, which must never be exposed in application logs.
    logger.info("Executing: %s", operation)
    cursor.execute(statement)


def verify_policy(cursor: Any) -> None:
    logger.info("Checking enabled redaction policy on all columns of %s.%s", VIEW_OWNER, VIEW_NAME)
    cursor.execute(
        """
        SELECT p.enable, c.function_type, c.column_name
        FROM sys.redaction_policies p
        JOIN sys.redaction_columns c
          ON c.object_owner = p.object_owner
         AND c.object_name = p.object_name
        WHERE p.object_owner = :owner
          AND p.object_name = :view_name
          AND p.policy_name = :policy_name
        """,
        owner=VIEW_OWNER,
        view_name=VIEW_NAME,
        policy_name=POLICY_NAME,
    )
    rows = cursor.fetchall()
    actual = {column_name: function_type for enabled, function_type, column_name in rows if enabled == "YES"}
    if set(actual) != set(REDACTED_COLUMNS) or any(
        not actual[column].startswith(expected) for column, expected in REDACTED_COLUMNS.items()
    ):
        raise RuntimeError(
            f"Expected enabled policy {POLICY_NAME!r} for {sorted(REDACTED_COLUMNS)!r}; found {actual!r}"
        )
    logger.info("Policy preflight passed: %s", actual)


def status_policy_key(cursor: Any) -> str:
    cursor.execute(
        """
        SELECT policy_key
        FROM app.data_redaction_policy_catalog
        WHERE object_owner = 'APP' AND object_name = 'V_ORDER_TOTALS' AND column_name = 'STATUS'
          AND enabled = 'Y'
        """
    )
    row = cursor.fetchone()
    if not row:
        raise RuntimeError("No active catalog entry exists for APP.V_ORDER_TOTALS.STATUS")
    logger.info("Catalog preflight passed: STATUS policy_key=%s", row[0])
    return str(row[0])


def partial_status(value: str) -> str:
    if len(value) <= 2:
        return "*" * len(value)
    return value[0] + ("*" * (len(value) - 2)) + value[-1]


def verify_masked(test_connection: Any, expected_status: str, policy_key: str) -> None:
    """Verify every view column returns its configured redacted representation."""
    with test_connection.cursor() as cursor:
        cursor.execute("SELECT SYS_CONTEXT('APP_REDACTION_CTX', :attribute) FROM dual", attribute=policy_key)
        context_level = cursor.fetchone()[0]
        logger.info("Logon-loaded STATUS entitlement level=%s", context_level or "<unset>")
        logger.info("Querying %s.%s as the temporary user", VIEW_OWNER, VIEW_NAME)
        cursor.execute(
            "SELECT ORDER_ID, CUSTOMER_ID, STATUS, ORDER_TOTAL "
            f"FROM {VIEW_OWNER}.{VIEW_NAME} "
            "WHERE ORDER_ID IS NOT NULL "
            "FETCH FIRST 50 ROWS ONLY"
        )
        rows = cursor.fetchall()

    if not rows:
        raise RuntimeError("No rows were returned; redaction cannot be verified")

    expected = (0, 0, expected_status, 0)
    if any(row != expected for row in rows):
        raise RuntimeError(
            "Data Redaction verification failed: the temporary user received "
            "a value that did not match the expected all-column mask"
        )
    logger.info("Masking verified: rows=%d, observed masked values=%s", len(rows), rows)


def main() -> int:
    # Make backend/.env discoverable even when invoked from the repository root.
    os.chdir(SCRIPT_ROOT)
    sys.path.insert(0, str(SCRIPT_ROOT))

    from app.config import get_settings

    try:
        import oracledb
    except ImportError as exc:
        raise RuntimeError("Install the backend oracle dependency to run this smoke test") from exc

    settings = get_settings()
    if not all((settings.oracle_dsn, settings.oracle_provisioner_user, settings.oracle_provisioner_password)):
        raise RuntimeError("ORACLE_DSN, ORACLE_PROVISIONER_USER, and ORACLE_PROVISIONER_PASSWORD must be configured")

    username = temporary_username()
    password = temporary_password()
    admin_connection = None
    test_connection = None
    user_created = False
    entitlement_created = False
    failed = False

    logger.info("Starting Oracle Data Redaction smoke test with temporary user %s", username)
    try:
        admin_connection = oracledb.connect(
            user=settings.oracle_provisioner_user,
            password=settings.oracle_provisioner_password,
            dsn=settings.oracle_dsn,
        )
        logger.info("Connected as the configured provisioner")
        with admin_connection.cursor() as cursor:
            verify_policy(cursor)
            policy_key = status_policy_key(cursor)
            # Read the source only to compute the expected partial mask. It is
            # never logged; the view itself is context-aware and would return
            # its default mask for this provisioner session.
            cursor.execute("SELECT status FROM app.orders WHERE status IS NOT NULL FETCH FIRST 1 ROW ONLY")
            source_status = cursor.fetchone()
            if not source_status:
                raise RuntimeError("No non-null STATUS value was returned; partial redaction cannot be verified")
            expected_status = partial_status(str(source_status[0]))
            execute(
                cursor,
                f"CREATE USER {quote_identifier(username)} IDENTIFIED BY {quote_identifier(password)}",
                f"CREATE USER {username} (password withheld)",
            )
            user_created = True
            execute(cursor, f"GRANT CREATE SESSION TO {quote_identifier(username)}", f"GRANT CREATE SESSION TO {username}")
            execute(
                cursor,
                f"GRANT SELECT ON {VIEW_OWNER}.{VIEW_NAME} TO {quote_identifier(username)}",
                f"GRANT SELECT ON {VIEW_OWNER}.{VIEW_NAME} TO {username}",
            )
            cursor.execute(
                """
                INSERT INTO app.data_redaction_entitlements
                    (principal_name, object_owner, object_name, column_name, unmask_level)
                VALUES (:principal_name, 'APP', 'V_ORDER_TOTALS', 'STATUS', 'PARTIAL')
                """,
                principal_name=username,
            )
            entitlement_created = True
        admin_connection.commit()
        logger.info("Created %s and granted only CREATE SESSION and SELECT on %s.%s", username, VIEW_OWNER, VIEW_NAME)

        test_connection = oracledb.connect(user=username, password=password, dsn=settings.oracle_dsn)
        logger.info("Connected as temporary user %s", username)
        verify_masked(test_connection, expected_status, policy_key)
        logger.info("Oracle Data Redaction smoke test passed")
    except Exception:
        failed = True
        logger.exception("Oracle Data Redaction smoke test failed")
    finally:
        if test_connection:
            try:
                test_connection.close()
                logger.info("Closed temporary-user connection")
            except Exception:
                logger.exception("Could not close temporary-user connection")
                failed = True
        if admin_connection and user_created:
            try:
                with admin_connection.cursor() as cursor:
                    if entitlement_created:
                        execute(
                            cursor,
                            f"DELETE FROM app.data_redaction_entitlements WHERE principal_name = '{username}'",
                            f"DELETE temporary entitlement for {username}",
                        )
                    execute(cursor, f"DROP USER {quote_identifier(username)}", f"DROP USER {username}")
                admin_connection.commit()
                logger.info("Dropped temporary user %s", username)
            except Exception:
                logger.exception("Could not drop temporary user %s", username)
                failed = True
        if admin_connection:
            try:
                admin_connection.close()
                logger.info("Closed provisioner connection")
            except Exception:
                logger.exception("Could not close provisioner connection")
                failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(main())
