from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import secrets
import sqlite3
from typing import Any


_IDENTIFIER_PART_RE = re.compile(r"[^a-z0-9]+")


def _created_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _sanitize_identifier_part(value: str, *, default: str) -> str:
    sanitized = _IDENTIFIER_PART_RE.sub("_", value.lower()).strip("_")
    return sanitized or default


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _sqlite_type(value: object) -> str:
    if isinstance(value, bool):
        return "INTEGER"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    return "TEXT"


@dataclass(frozen=True)
class SQLiteRunWorkspace:
    run_dir: Path
    sqlite_db_path: Path
    run_prefix: str
    raw_table: str
    enriched_table: str
    manifest_path: Path

    @classmethod
    def create(cls, run_dir: str | Path, *, run_id: str) -> "SQLiteRunWorkspace":
        path = Path(run_dir)
        sqlite_dir = path / "sqlite"
        sqlite_dir.mkdir(parents=True, exist_ok=True)

        safe_run = _sanitize_identifier_part(run_id, default="run")
        run_prefix = f"wferp_{_now_tag()}_{secrets.token_hex(3)}_{safe_run}"
        workspace = cls(
            run_dir=path,
            sqlite_db_path=sqlite_dir / "wferp-report.sqlite3",
            run_prefix=run_prefix,
            raw_table=f"{run_prefix}_raw_ledger",
            enriched_table=f"{run_prefix}_enriched_ledger",
            manifest_path=sqlite_dir / f"{run_prefix}_sqlite_manifest.json",
        )

        with sqlite3.connect(workspace.sqlite_db_path):
            pass

        workspace._write_manifest(
            {
                "sqlite_db_path": str(workspace.sqlite_db_path),
                "run_prefix": workspace.run_prefix,
                "raw_table": workspace.raw_table,
                "lookup_tables": [],
                "enriched_table": workspace.enriched_table,
                "raw_row_count": 0,
                "enriched_row_count": 0,
                "lookup_row_counts": {},
                "ignored_lookup_rows": {},
                "cleanup_status": "active",
                "retention_decision": "keep",
                "created_at": _created_at(),
                "residual_risks": [],
                "source_workbook": None,
                "source_workbook_hash": None,
                "formal_db_query_hash": None,
            }
        )
        return workspace

    def manifest(self) -> dict[str, Any]:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def write_raw_rows(self, rows: list[dict[str, Any]]) -> None:
        self._write_rows(self.raw_table, rows)
        self._update_manifest(raw_row_count=len(rows))

    def register_lookup_table(self, logical_name: str, rows: list[dict[str, Any]]) -> str:
        logical_part = _sanitize_identifier_part(logical_name, default="lookup")
        table_name = self._unique_lookup_table_name(f"{self.run_prefix}_{logical_part}")
        self._write_rows(table_name, rows)

        manifest = self.manifest()
        lookup_tables = list(manifest.get("lookup_tables", []))
        lookup_tables.append(table_name)
        lookup_row_counts = dict(manifest.get("lookup_row_counts", {}))
        lookup_row_counts[table_name] = len(rows)
        self._update_manifest(
            lookup_tables=lookup_tables,
            lookup_row_counts=lookup_row_counts,
        )
        return table_name

    def cleanup_run_tables(self) -> None:
        manifest = self.manifest()
        tables = [
            manifest["raw_table"],
            manifest["enriched_table"],
            *manifest.get("lookup_tables", []),
        ]
        with sqlite3.connect(self.sqlite_db_path) as conn:
            for table in tables:
                conn.execute(f"DROP TABLE IF EXISTS {_quote_identifier(table)}")
        self._update_manifest(cleanup_status="deleted", retention_decision="delete")

    def _write_rows(self, table_name: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            raise ValueError(f"Cannot create {table_name} without rows")

        columns: list[str] = []
        seen_columns: set[str] = set()
        for row in rows:
            for column in row:
                if column not in seen_columns:
                    seen_columns.add(column)
                    columns.append(column)
        if not columns:
            raise ValueError(f"Cannot create {table_name} without columns")

        definitions = ", ".join(
            f"{_quote_identifier(column)} {_sqlite_type(next((row[column] for row in rows if column in row), None))}"
            for column in columns
        )
        quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
        bind_marks = ", ".join("?" for _ in columns)

        with sqlite3.connect(self.sqlite_db_path) as conn:
            conn.execute(f"DROP TABLE IF EXISTS {_quote_identifier(table_name)}")
            conn.execute(f"CREATE TABLE {_quote_identifier(table_name)} ({definitions})")
            conn.executemany(
                (
                    f"INSERT INTO {_quote_identifier(table_name)} "
                    f"({quoted_columns}) VALUES ({bind_marks})"
                ),
                [[row.get(column) for column in columns] for row in rows],
            )

    def _unique_lookup_table_name(self, base_name: str) -> str:
        manifest = self.manifest()
        existing = set(manifest.get("lookup_tables", []))
        with sqlite3.connect(self.sqlite_db_path) as conn:
            existing.update(
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            )

        if base_name not in existing:
            return base_name

        suffix = 2
        while f"{base_name}_{suffix}" in existing:
            suffix += 1
        return f"{base_name}_{suffix}"

    def _update_manifest(self, **updates: Any) -> None:
        manifest = self.manifest()
        manifest.update(updates)
        self._write_manifest(manifest)

    def _write_manifest(self, payload: dict[str, Any]) -> None:
        self.manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
