"""Standalone import of the audited JSON bundle into a new local MySQL DB."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pymysql


# Edit these values if your MySQL connection is different.
MYSQL_HOST = "127.0.0.1"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = ""
MYSQL_DATABASE = "pbac_db"

BASE_DIR = Path(__file__).resolve().parent
IMPORT_TABLES = (
    "roles",
    "name_prefixs",
    "fields",
    "departments",
    "divisions",
    "positions",
    "routes",
    "shifts",
    "employees",
    "employee_permissions",
    "mo_daily_transactions",
    "mo_daily_transaction_details",
    "mo_daily_transaction_discipline_warnings",
    "mo_daily_transaction_projects",
    "mo_report_export_job",
)
EXPECTED_SCHEMA_TABLES = {
    "addresses",
    "audit_logs",
    "departments",
    "districts",
    "divisions",
    "employee_permissions",
    "employees",
    "fields",
    "mo_daily_transaction_details",
    "mo_daily_transaction_discipline_warnings",
    "mo_daily_transaction_projects",
    "mo_daily_transactions",
    "mo_report_export_job",
    "name_prefixs",
    "position_change_logs",
    "positions",
    "postal_codes",
    "provinces",
    "roles",
    "route_change_logs",
    "routes",
    "shifts",
    "sub_districts",
}


def quote_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", value):
        raise ValueError(f"Unsafe SQL identifier: {value!r}")
    return f"`{value}`"


def read_json(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Missing migration file: {path}")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_bundle() -> dict[str, tuple[list[str], list[dict]]]:
    manifest = read_json(BASE_DIR / "migration_manifest.json")
    for relative_path, expected_hash in manifest["sha256"].items():
        path = BASE_DIR / relative_path
        actual_hash = sha256(path)
        if actual_hash != expected_hash:
            raise ValueError(f"Checksum mismatch: {relative_path}")

    exports: dict[str, tuple[list[str], list[dict]]] = {}
    for table_name in IMPORT_TABLES:
        headers = read_json(BASE_DIR / "headers" / f"{table_name}_headers.json")
        rows = read_json(BASE_DIR / "data" / f"{table_name}_data.json")
        columns = [item["column_name"] for item in headers]
        if len(rows) != manifest["row_counts"][table_name]:
            raise ValueError(f"Unexpected row count in {table_name}")
        if any(set(row) != set(columns) for row in rows):
            raise ValueError(f"Header/data column mismatch in {table_name}")
        exports[table_name] = (columns, rows)

    for row in exports["employees"][1]:
        if row.get("division_id") == "":
            row["division_id"] = None
        if row.get("employee_code") == "630589" and row.get("is_active") == "z":
            row["is_active"] = 1
        if row.get("employee_code") == "ADM001" and row.get("created_by") == "SYSTEM":
            row["created_by"] = "ADM001"

    for row in exports["mo_report_export_job"][1]:
        filters = row.get("filters_json")
        if isinstance(filters, str):
            json.loads(filters)

    return exports


def create_database() -> None:
    database = quote_identifier(MYSQL_DATABASE)
    connection = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {database} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
    finally:
        connection.close()


def connect_database():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        autocommit=False,
    )


def ensure_schema(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES")
        existing = {row[0] for row in cursor.fetchall()}

    if not existing:
        statements = read_json(BASE_DIR / "mysql_schema_statements.json")
        connection.autocommit(True)
        try:
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
        finally:
            connection.autocommit(False)
        existing = EXPECTED_SCHEMA_TABLES

    missing = EXPECTED_SCHEMA_TABLES - existing
    if missing:
        raise RuntimeError(
            "MySQL schema is incomplete; missing: " + ", ".join(sorted(missing))
        )


def validate_target_columns(connection, table_name: str, columns: list[str]) -> None:
    table = quote_identifier(table_name)
    with connection.cursor() as cursor:
        cursor.execute(f"SHOW COLUMNS FROM {table}")
        target_columns = {row[0] for row in cursor.fetchall()}
    missing = set(columns) - target_columns
    if missing:
        raise RuntimeError(
            f"MySQL table {table_name} is missing columns: {', '.join(sorted(missing))}"
        )


def import_rows(connection, exports) -> None:
    with connection.cursor() as cursor:
        nonempty = {}
        for table_name in IMPORT_TABLES:
            cursor.execute(f"SELECT COUNT(*) FROM {quote_identifier(table_name)}")
            count = cursor.fetchone()[0]
            if count:
                nonempty[table_name] = count
        if nonempty:
            details = ", ".join(f"{name}={count}" for name, count in nonempty.items())
            raise RuntimeError(f"Import stopped because target tables are not empty: {details}")

        cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        try:
            for table_name in IMPORT_TABLES:
                columns, rows = exports[table_name]
                validate_target_columns(connection, table_name, columns)
                if not rows:
                    continue
                column_sql = ", ".join(quote_identifier(name) for name in columns)
                placeholders = ", ".join(["%s"] * len(columns))
                sql = (
                    f"INSERT INTO {quote_identifier(table_name)} ({column_sql}) "
                    f"VALUES ({placeholders})"
                )
                values = [[row[name] for name in columns] for row in rows]
                cursor.executemany(sql, values)
                print(f"Imported {table_name}: {len(rows)} rows")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.execute("SET FOREIGN_KEY_CHECKS=1")
            connection.commit()


def verify_counts(connection, exports) -> None:
    with connection.cursor() as cursor:
        for table_name in IMPORT_TABLES:
            cursor.execute(f"SELECT COUNT(*) FROM {quote_identifier(table_name)}")
            actual = cursor.fetchone()[0]
            expected = len(exports[table_name][1])
            if actual != expected:
                raise RuntimeError(
                    f"Verification failed for {table_name}: expected {expected}, found {actual}"
                )
    print("Import completed: 15 tables and 373 rows verified.")


def main() -> None:
    exports = validate_bundle()
    create_database()
    connection = connect_database()
    try:
        ensure_schema(connection)
        import_rows(connection, exports)
        verify_counts(connection, exports)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
