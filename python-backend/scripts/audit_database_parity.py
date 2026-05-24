#!/usr/bin/env python3
"""Audit Drizzle database snapshot parity against Python SQLModel metadata.

This is a static audit. It does not connect to a database and is intended to
make the database-package removal work measurable before deleting TS schemas.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_BACKEND = REPO_ROOT / "python-backend"
DRIZZLE_META = REPO_ROOT / "src/database/migrations/meta"
DRIZZLE_MIGRATIONS = REPO_ROOT / "src/database/migrations"
DEFAULT_DECISIONS = Path(__file__).with_name("database_parity_decisions.json")


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    type: str
    normalized_type: str
    nullable: bool
    primary_key: bool
    default: str | None


@dataclass(frozen=True)
class TableInfo:
    name: str
    columns: dict[str, ColumnInfo]
    indexes: dict[str, list[str]]
    unique_indexes: dict[str, list[str]]
    foreign_keys: dict[str, tuple[tuple[str, ...], str, tuple[str, ...], str | None]]
    primary_key: tuple[str, ...]


def _normalize_type(raw: str) -> str:
    value = raw.lower().strip()
    value = re.sub(r"\s+", " ", value)

    if value in {"json", "jsonb"}:
        return "json"
    if value.endswith("[]") or value.startswith("array"):
        return "array"
    if value.startswith("varchar") or value in {"character varying", "string"}:
        return "text"
    if value in {"text", "varchar", "character varying"}:
        return "text"
    if value in {"bool", "boolean"}:
        return "boolean"
    if value in {"int", "int4", "integer", "serial"}:
        return "integer"
    if value in {"bigint", "int8", "bigserial"}:
        return "bigint"
    if value in {"real", "float", "double precision", "double"}:
        return "float"
    if value in {"numeric", "decimal"} or value.startswith("numeric("):
        return "numeric"
    if value in {"timestamp", "timestamp without time zone", "datetime", "timestamp with time zone", "timestamptz"}:
        return "timestamp"
    if value in {"uuid"}:
        return "uuid"
    if value == "vector":
        return "vector"

    return value


def _latest_drizzle_snapshot() -> Path:
    snapshots = sorted(DRIZZLE_META.glob("*_snapshot.json"))
    if not snapshots:
        raise FileNotFoundError(f"No Drizzle snapshots found in {DRIZZLE_META}")
    return snapshots[-1]


def _load_drizzle_tables(snapshot_path: Path) -> dict[str, TableInfo]:
    data = json.loads(snapshot_path.read_text())
    tables: dict[str, TableInfo] = {}

    for table in data.get("tables", {}).values():
        table_name = table["name"]
        columns: dict[str, ColumnInfo] = {}
        pk_columns: list[str] = []

        for column in table.get("columns", {}).values():
            name = column["name"]
            primary_key = bool(column.get("primaryKey"))
            if primary_key:
                pk_columns.append(name)

            columns[name] = ColumnInfo(
                name=name,
                type=column.get("type", ""),
                normalized_type=_normalize_type(column.get("type", "")),
                nullable=not bool(column.get("notNull")),
                primary_key=primary_key,
                default=column.get("default"),
            )

        for composite_pk in table.get("compositePrimaryKeys", {}).values():
            pk_columns.extend(composite_pk.get("columns", []))

        for pk_column in pk_columns:
            column = columns.get(pk_column)
            if column is None:
                continue
            columns[pk_column] = ColumnInfo(
                name=column.name,
                type=column.type,
                normalized_type=column.normalized_type,
                nullable=False,
                primary_key=True,
                default=column.default,
            )

        indexes: dict[str, list[str]] = {}
        unique_indexes: dict[str, list[str]] = {}
        for name, index in table.get("indexes", {}).items():
            expressions = [
                column["expression"]
                for column in index.get("columns", [])
                if not column.get("isExpression") and isinstance(column.get("expression"), str)
            ]
            if not expressions:
                continue
            target = unique_indexes if index.get("isUnique") else indexes
            target[name] = expressions

        unique_constraints = table.get("uniqueConstraints", {})
        for name, constraint in unique_constraints.items():
            cols = constraint.get("columns", [])
            if cols:
                unique_indexes[name] = cols

        foreign_keys: dict[str, tuple[tuple[str, ...], str, tuple[str, ...], str | None]] = {}
        for name, fk in table.get("foreignKeys", {}).items():
            foreign_keys[name] = (
                tuple(fk.get("columnsFrom", [])),
                fk.get("tableTo", ""),
                tuple(fk.get("columnsTo", [])),
                fk.get("onDelete"),
            )

        tables[table_name] = TableInfo(
            name=table_name,
            columns=columns,
            indexes=indexes,
            unique_indexes=unique_indexes,
            foreign_keys=foreign_keys,
            primary_key=tuple(dict.fromkeys(pk_columns)),
        )

    return tables


def _load_python_tables() -> dict[str, TableInfo]:
    sys.path.insert(0, str(PYTHON_BACKEND))

    from sqlalchemy import ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint
    from sqlmodel import SQLModel

    import app.models  # noqa: F401

    tables: dict[str, TableInfo] = {}

    for table_name, table in SQLModel.metadata.tables.items():
        columns: dict[str, ColumnInfo] = {}
        for column in table.columns:
            raw_type = str(column.type)
            default = None
            if column.server_default is not None:
                default = str(column.server_default.arg)
            elif column.default is not None:
                default = str(column.default.arg)

            columns[column.name] = ColumnInfo(
                name=column.name,
                type=raw_type,
                normalized_type=_normalize_type(raw_type),
                nullable=bool(column.nullable),
                primary_key=bool(column.primary_key),
                default=default,
            )

        indexes: dict[str, list[str]] = {}
        unique_indexes: dict[str, list[str]] = {}
        for index in table.indexes:
            cols = [expr.name for expr in index.expressions if hasattr(expr, "name")]
            if not cols:
                continue
            target = unique_indexes if index.unique else indexes
            target[index.name or ",".join(cols)] = cols

        foreign_keys: dict[str, tuple[tuple[str, ...], str, tuple[str, ...], str | None]] = {}
        primary_key: tuple[str, ...] = ()
        for constraint in table.constraints:
            if isinstance(constraint, PrimaryKeyConstraint):
                primary_key = tuple(column.name for column in constraint.columns)
            elif isinstance(constraint, UniqueConstraint):
                cols = [column.name for column in constraint.columns]
                if cols:
                    unique_indexes[constraint.name or ",".join(cols)] = cols
            elif isinstance(constraint, ForeignKeyConstraint):
                local_cols = tuple(element.parent.name for element in constraint.elements)
                remote_table = constraint.referred_table.name
                remote_cols = tuple(element.column.name for element in constraint.elements)
                foreign_keys[constraint.name or ",".join(local_cols)] = (
                    local_cols,
                    remote_table,
                    remote_cols,
                    constraint.ondelete,
                )

        tables[table_name] = TableInfo(
            name=table_name,
            columns=columns,
            indexes=indexes,
            unique_indexes=unique_indexes,
            foreign_keys=foreign_keys,
            primary_key=primary_key,
        )

    return tables


def _migration_journal_drift() -> dict[str, list[str]]:
    journal_path = DRIZZLE_META / "_journal.json"
    if not journal_path.exists():
        return {"sql_missing_from_journal": [], "journal_missing_sql": []}

    journal = json.loads(journal_path.read_text())
    journal_tags = {entry["tag"] for entry in journal.get("entries", [])}
    sql_tags = {path.stem for path in DRIZZLE_MIGRATIONS.glob("*.sql")}

    return {
        "sql_missing_from_journal": sorted(sql_tags - journal_tags),
        "journal_missing_sql": sorted(journal_tags - sql_tags),
    }


def _load_decisions(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"missing_tables": {}}

    return json.loads(path.read_text())


def _classify_missing_tables(missing_tables: list[str], decisions: dict[str, Any]) -> dict[str, Any]:
    configured = decisions.get("missing_tables", {})
    classified: dict[str, list[dict[str, str]]] = {}

    for table in missing_tables:
        entry = configured.get(table, {})
        decision = entry.get("decision", "unclassified")
        classified.setdefault(decision, []).append(
            {
                "table": table,
                "reason": entry.get("reason", "No decision recorded."),
            }
        )

    return {
        "counts": {decision: len(items) for decision, items in sorted(classified.items())},
        "items": {decision: sorted(items, key=lambda item: item["table"]) for decision, items in classified.items()},
    }


def _classify_table_mismatches(mismatched_tables: list[str], decisions: dict[str, Any]) -> dict[str, Any]:
    configured = decisions.get("table_mismatches", {})
    classified: dict[str, list[dict[str, str]]] = {}

    for table in mismatched_tables:
        entry = configured.get(table, {})
        decision = entry.get("decision", "unclassified")
        classified.setdefault(decision, []).append(
            {
                "table": table,
                "reason": entry.get("reason", "No decision recorded."),
            }
        )

    return {
        "counts": {decision: len(items) for decision, items in sorted(classified.items())},
        "items": {decision: sorted(items, key=lambda item: item["table"]) for decision, items in classified.items()},
    }


def _compare_tables(
    ts_tables: dict[str, TableInfo],
    py_tables: dict[str, TableInfo],
    decisions: dict[str, Any],
) -> dict[str, Any]:
    ts_names = set(ts_tables)
    py_names = set(py_tables)

    matched_tables = sorted(ts_names & py_names)
    python_missing_tables = sorted(ts_names - py_names)
    report: dict[str, Any] = {
        "table_counts": {
            "typescript": len(ts_tables),
            "python": len(py_tables),
            "matched": len(matched_tables),
            "python_missing": len(ts_names - py_names),
            "python_extra": len(py_names - ts_names),
        },
        "python_missing_table_decisions": _classify_missing_tables(python_missing_tables, decisions),
        "python_missing_tables": python_missing_tables,
        "python_extra_tables": sorted(py_names - ts_names),
        "column_mismatches": {},
        "constraint_mismatches": {},
    }

    for table_name in matched_tables:
        ts = ts_tables[table_name]
        py = py_tables[table_name]
        table_decision = decisions.get("table_mismatches", {}).get(table_name, {})
        accepted_python_missing_columns = set(table_decision.get("accept_python_missing_columns", []))
        accepted_python_extra_columns = set(table_decision.get("accept_python_extra_columns", []))
        accepted_changed_columns = set(table_decision.get("accept_changed_columns", []))
        accepted_python_missing_fk_columns = {
            tuple(columns) for columns in table_decision.get("accept_python_missing_foreign_key_columns", [])
        }
        accepted_python_extra_fk_columns = {
            tuple(columns) for columns in table_decision.get("accept_python_extra_foreign_key_columns", [])
        }
        accepted_python_missing_unique_columns = {
            tuple(columns) for columns in table_decision.get("accept_python_missing_unique_columns", [])
        }
        accepted_python_extra_unique_columns = {
            tuple(columns) for columns in table_decision.get("accept_python_extra_unique_columns", [])
        }
        accept_primary_key_mismatch = bool(table_decision.get("accept_primary_key_mismatch"))
        ts_cols = set(ts.columns)
        py_cols = set(py.columns)
        missing_cols = sorted((ts_cols - py_cols) - accepted_python_missing_columns)
        extra_cols = sorted((py_cols - ts_cols) - accepted_python_extra_columns)
        changed_cols: list[dict[str, Any]] = []

        for column_name in sorted(ts_cols & py_cols):
            if column_name in accepted_changed_columns:
                continue
            ts_col = ts.columns[column_name]
            py_col = py.columns[column_name]
            differences: dict[str, Any] = {}
            if ts_col.normalized_type != py_col.normalized_type:
                differences["type"] = {
                    "typescript": ts_col.type,
                    "python": py_col.type,
                    "normalized_types": [ts_col.normalized_type, py_col.normalized_type],
                }
            if ts_col.nullable != py_col.nullable:
                differences["nullable"] = {"typescript": ts_col.nullable, "python": py_col.nullable}

            if differences:
                changed_cols.append({"column": column_name, "differences": differences})

        if missing_cols or extra_cols or changed_cols:
            report["column_mismatches"][table_name] = {
                "python_missing_columns": missing_cols,
                "python_extra_columns": extra_cols,
                "changed_columns": changed_cols,
            }

        constraint_delta: dict[str, Any] = {}
        if set(ts.primary_key) != set(py.primary_key) and not accept_primary_key_mismatch:
            constraint_delta["primary_key"] = {"typescript": ts.primary_key, "python": py.primary_key}

        ts_fk_cols = {fk[0] for fk in ts.foreign_keys.values()}
        py_fk_cols = {fk[0] for fk in py.foreign_keys.values()}
        missing_fk_cols = (ts_fk_cols - py_fk_cols) - accepted_python_missing_fk_columns
        extra_fk_cols = (py_fk_cols - ts_fk_cols) - accepted_python_extra_fk_columns
        if missing_fk_cols or extra_fk_cols:
            constraint_delta["foreign_key_columns"] = {
                "python_missing": sorted([list(cols) for cols in missing_fk_cols]),
                "python_extra": sorted([list(cols) for cols in extra_fk_cols]),
            }

        ts_unique_cols = {tuple(cols) for cols in ts.unique_indexes.values()}
        py_unique_cols = {tuple(cols) for cols in py.unique_indexes.values()}
        missing_unique_cols = (ts_unique_cols - py_unique_cols) - accepted_python_missing_unique_columns
        extra_unique_cols = (py_unique_cols - ts_unique_cols) - accepted_python_extra_unique_columns
        if missing_unique_cols or extra_unique_cols:
            constraint_delta["unique_columns"] = {
                "python_missing": sorted([list(cols) for cols in missing_unique_cols]),
                "python_extra": sorted([list(cols) for cols in extra_unique_cols]),
            }

        if constraint_delta:
            report["constraint_mismatches"][table_name] = constraint_delta

    mismatched_tables = sorted(set(report["column_mismatches"]) | set(report["constraint_mismatches"]))
    report["table_mismatch_decisions"] = _classify_table_mismatches(mismatched_tables, decisions)

    return report


def _render_markdown(report: dict[str, Any]) -> str:
    counts = report["table_counts"]
    lines = [
        "# Database Python Parity Audit",
        "",
        f"- Drizzle snapshot: `{report['drizzle_snapshot']}`",
        f"- TS tables: {counts['typescript']}",
        f"- Python tables: {counts['python']}",
        f"- Matched tables: {counts['matched']}",
        f"- Python-missing tables: {counts['python_missing']}",
        f"- Python-extra tables: {counts['python_extra']}",
        f"- Tables with column mismatches: {len(report['column_mismatches'])}",
        f"- Tables with constraint mismatches: {len(report['constraint_mismatches'])}",
        "",
        "## Migration Journal Drift",
        "",
    ]

    drift = report["migration_journal_drift"]
    if drift["sql_missing_from_journal"] or drift["journal_missing_sql"]:
        lines.append("Drift detected.")
        if drift["sql_missing_from_journal"]:
            lines.append("")
            lines.append("SQL migrations missing from `_journal.json`:")
            lines.extend(f"- `{tag}`" for tag in drift["sql_missing_from_journal"])
        if drift["journal_missing_sql"]:
            lines.append("")
            lines.append("Journal entries without SQL files:")
            lines.extend(f"- `{tag}`" for tag in drift["journal_missing_sql"])
    else:
        lines.append("No Drizzle SQL/journal drift detected.")

    lines.extend(["", "## Python-Missing Tables", ""])
    if report["python_missing_tables"]:
        lines.extend(f"- `{table}`" for table in report["python_missing_tables"])
    else:
        lines.append("None.")

    lines.extend(["", "## Python-Missing Table Decisions", ""])
    decisions = report["python_missing_table_decisions"]
    if decisions["items"]:
        for decision, items in sorted(decisions["items"].items()):
            lines.append(f"### `{decision}` ({len(items)})")
            for item in items:
                lines.append(f"- `{item['table']}`: {item['reason']}")
            lines.append("")
    else:
        lines.append("None.")

    lines.extend(["", "## Python-Extra Tables", ""])
    if report["python_extra_tables"]:
        lines.extend(f"- `{table}`" for table in report["python_extra_tables"])
    else:
        lines.append("None.")

    lines.extend(["", "## Matched Table Mismatch Decisions", ""])
    mismatch_decisions = report["table_mismatch_decisions"]
    if mismatch_decisions["items"]:
        for decision, items in sorted(mismatch_decisions["items"].items()):
            lines.append(f"### `{decision}` ({len(items)})")
            for item in items:
                lines.append(f"- `{item['table']}`: {item['reason']}")
            lines.append("")
    else:
        lines.append("None.")

    lines.extend(["", "## Column Mismatches", ""])
    if report["column_mismatches"]:
        for table, mismatch in sorted(report["column_mismatches"].items()):
            lines.append(f"### `{table}`")
            if mismatch["python_missing_columns"]:
                missing_columns = ", ".join(f"`{column}`" for column in mismatch["python_missing_columns"])
                lines.append(f"- Python missing columns: {missing_columns}")
            if mismatch["python_extra_columns"]:
                extra_columns = ", ".join(f"`{column}`" for column in mismatch["python_extra_columns"])
                lines.append(f"- Python extra columns: {extra_columns}")
            for changed in mismatch["changed_columns"][:20]:
                lines.append(f"- `{changed['column']}`: `{json.dumps(changed['differences'], sort_keys=True)}`")
            if len(mismatch["changed_columns"]) > 20:
                lines.append(f"- ... {len(mismatch['changed_columns']) - 20} more changed columns")
            lines.append("")
    else:
        lines.append("None.")

    lines.extend(["", "## Constraint Mismatches", ""])
    if report["constraint_mismatches"]:
        for table, mismatch in sorted(report["constraint_mismatches"].items()):
            lines.append(f"### `{table}`")
            lines.append(f"```json\n{json.dumps(mismatch, indent=2, sort_keys=True)}\n```")
    else:
        lines.append("None.")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--decisions",
        default=DEFAULT_DECISIONS,
        type=Path,
        help="JSON file that records accepted decisions for known parity gaps.",
    )
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", type=Path, help="Write report to this path instead of stdout")
    args = parser.parse_args()

    snapshot = _latest_drizzle_snapshot()
    ts_tables = _load_drizzle_tables(snapshot)
    py_tables = _load_python_tables()
    decisions = _load_decisions(args.decisions)
    report = _compare_tables(ts_tables, py_tables, decisions)
    report["drizzle_snapshot"] = str(snapshot.relative_to(REPO_ROOT))
    report["migration_journal_drift"] = _migration_journal_drift()
    report["decisions_file"] = str(args.decisions.relative_to(REPO_ROOT)) if args.decisions.exists() else None

    rendered = (
        json.dumps(report, indent=2, sort_keys=True) + "\n" if args.format == "json" else _render_markdown(report)
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end="")

    has_gaps = any(
        [
            report["table_counts"]["python_missing"],
            report["table_counts"]["python_extra"],
            report["column_mismatches"],
            report["constraint_mismatches"],
            report["migration_journal_drift"]["sql_missing_from_journal"],
            report["migration_journal_drift"]["journal_missing_sql"],
        ]
    )
    return 1 if has_gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
