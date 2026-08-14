"""Import selected JSON exports into the configured MySQL database.

The target schema is created from the application SQLAlchemy models. Only the
employee and MO tables listed in IMPORT_TABLES receive data.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import os
import pkgutil
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, JSON, MetaData, select, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


def load_all_models() -> None:
    models_path = PROJECT_ROOT / "app" / "models"
    for module in pkgutil.iter_modules([str(models_path)]):
        if module.name != "__init__":
            importlib.import_module(f"app.models.{module.name}")


def read_json(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Required export file not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_export(json_dir: Path) -> dict[str, list[dict[str, Any]]]:
    exports: dict[str, list[dict[str, Any]]] = {}

    for table_name in IMPORT_TABLES:
        headers_path = json_dir / "headers" / f"{table_name}_headers.json"
        data_path = json_dir / "data" / f"{table_name}_data.json"
        headers = read_json(headers_path)
        rows = read_json(data_path)

        if not isinstance(headers, list) or not isinstance(rows, list):
            raise ValueError(f"Invalid JSON structure for table {table_name}")

        header_names = {
            item["column_name"]
            for item in headers
            if isinstance(item, dict) and "column_name" in item
        }
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValueError(f"{data_path}: row {index + 1} is not an object")
            unknown = set(row) - header_names
            if unknown:
                raise ValueError(
                    f"{data_path}: row {index + 1} contains unknown columns: "
                    f"{', '.join(sorted(unknown))}"
                )

        exports[table_name] = rows

    return exports


def normalize_and_validate_relationships(
    exports: dict[str, list[dict[str, Any]]], metadata: MetaData
) -> None:
    for table_name, rows in exports.items():
        table = metadata.tables[table_name]
        columns = {column.name: column for column in table.columns}
        for row in rows:
            for column_name, value in list(row.items()):
                column = columns.get(column_name)
                if column is not None and column.nullable and value == "":
                    row[column_name] = None

    employee_codes = {row["employee_code"] for row in exports["employees"]}
    for row in exports["employees"]:
        if row.get("created_by") == "SYSTEM":
            if row.get("employee_code") != "ADM001":
                raise ValueError(
                    "Only bootstrap employee ADM001 may use created_by=SYSTEM"
                )
            row["created_by"] = row["employee_code"]

    for table_name, rows in exports.items():
        table = metadata.tables[table_name]
        for column in table.columns:
            for foreign_key in column.foreign_keys:
                target_table = foreign_key.column.table.name
                target_column = foreign_key.column.name
                target_rows = exports.get(target_table)
                target_values = (
                    {row[target_column] for row in target_rows}
                    if target_rows is not None
                    else set()
                )

                for index, row in enumerate(rows):
                    value = row.get(column.name)
                    if value is None:
                        continue
                    if target_rows is None:
                        raise ValueError(
                            f"{table_name} row {index + 1}: {column.name}={value!r} "
                            f"requires data from excluded table {target_table}"
                        )
                    if value not in target_values:
                        raise ValueError(
                            f"{table_name} row {index + 1}: {column.name}={value!r} "
                            f"does not exist in {target_table}.{target_column}"
                        )

    if "ADM001" not in employee_codes:
        raise ValueError("Bootstrap employee ADM001 is missing from the export")


def convert_value(value: Any, column_type: Any) -> Any:
    if value is None:
        return None
    if isinstance(column_type, DateTime) and isinstance(value, str):
        return dt.datetime.fromisoformat(value)
    if isinstance(column_type, Date) and isinstance(value, str):
        return dt.date.fromisoformat(value)
    if isinstance(column_type, Boolean):
        return bool(value)
    if isinstance(column_type, JSON) and isinstance(value, str):
        return json.loads(value)
    return value


def prepare_rows(rows: list[dict[str, Any]], table: Any) -> list[dict[str, Any]]:
    target_columns = {column.name: column for column in table.columns}
    prepared: list[dict[str, Any]] = []

    for row in rows:
        unknown = set(row) - set(target_columns)
        if unknown:
            raise ValueError(
                f"Table {table.name} has no target columns for: "
                f"{', '.join(sorted(unknown))}"
            )
        prepared.append(
            {
                name: convert_value(value, target_columns[name].type)
                for name, value in row.items()
            }
        )

    return prepared


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import selected employee and MO JSON data into MySQL."
    )
    parser.add_argument(
        "--json-dir",
        type=Path,
        default=PROJECT_ROOT / "jsons",
        help="Directory containing headers/ and data/ (default: project jsons/).",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing rows from the selected MySQL tables before import.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    exports = validate_export(args.json_dir.resolve())

    from app.core.db.engine import Base, engine

    if engine.dialect.name not in {"mysql", "mariadb"}:
        raise RuntimeError(
            "Target database is not MySQL. Set DB_ENGINE=mysql and the DB_* "
            "values in .env before running this script."
        )

    load_all_models()
    normalize_and_validate_relationships(exports, Base.metadata)
    Base.metadata.create_all(bind=engine)

    metadata = MetaData()
    metadata.reflect(bind=engine, only=list(IMPORT_TABLES))
    missing_tables = set(IMPORT_TABLES) - set(metadata.tables)
    if missing_tables:
        raise RuntimeError(
            f"Target schema is missing tables: {', '.join(sorted(missing_tables))}"
        )

    with engine.connect() as connection:
        existing_counts = {
            name: connection.execute(
                select(text("COUNT(*)")).select_from(metadata.tables[name])
            ).scalar_one()
            for name in IMPORT_TABLES
        }

        nonempty = {name: count for name, count in existing_counts.items() if count}
        if nonempty and not args.replace:
            details = ", ".join(f"{name}={count}" for name, count in nonempty.items())
            raise RuntimeError(
                f"Target tables are not empty ({details}). Use --replace only if "
                "those rows may be deleted."
            )

        connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        connection.commit()
        transaction = connection.begin()
        try:
            if args.replace:
                for table_name in reversed(IMPORT_TABLES):
                    connection.execute(metadata.tables[table_name].delete())

            for table_name in IMPORT_TABLES:
                table = metadata.tables[table_name]
                rows = prepare_rows(exports[table_name], table)
                if rows:
                    connection.execute(table.insert(), rows)
                print(f"Imported {table_name}: {len(rows)} rows")

            transaction.commit()
        except Exception:
            transaction.rollback()
            raise
        finally:
            connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            connection.commit()

        mismatches: list[str] = []
        for table_name in IMPORT_TABLES:
            actual = connection.execute(
                select(text("COUNT(*)")).select_from(metadata.tables[table_name])
            ).scalar_one()
            expected = len(exports[table_name])
            if actual != expected:
                mismatches.append(f"{table_name}: expected {expected}, found {actual}")

        if mismatches:
            raise RuntimeError("Row-count verification failed: " + "; ".join(mismatches))

    print("Employee data import completed and row counts verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
