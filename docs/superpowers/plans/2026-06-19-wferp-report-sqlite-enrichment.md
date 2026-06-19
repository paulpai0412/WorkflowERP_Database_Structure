# WFERP Report SQLite Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the SQLite enrichment pipeline for `wferp-report` so the formal ERP database receives only one reviewed raw-field SELECT, while Excel formula and lookup fields are reconstructed in a run-scoped local SQLite workspace and validated through raw/enriched checkpoints.

**Architecture:** The implementation adds focused Python modules for readable schema metadata, workbook column classification, SQLite workspace lifecycle, lookup import, formula translation, and enrichment execution. Existing harness state and CLI commands become the orchestration layer: classify workbook columns, confirm raw SQL, execute/import raw rows, enrich locally, show raw/enriched previews, and record retention decisions. Validator gates remain subagent-owned; local static checks are evidence input only.

**Tech Stack:** Python 3 standard library, `openpyxl`, SQLite `sqlite3`, pytest, existing `skill_scripts/*`, existing checkpoint companion, WFERP `_Source` schema metadata, local `wferp-report` skill references.

---

## Approved Spec

Implement against:

- `docs/superpowers/specs/2026-06-19-wferp-report-sqlite-enrichment-design.md`

Do not reduce scope. Each task must leave a tested, production-grade vertical slice. Preserve existing unrelated worktree changes.

## Goal Prompt For Execution

Use this prompt to execute the plan in a fresh Codex session:

```text
使用 superpowers:subagent-driven-development 與 TDD 執行 /home/timmypai/.codex/worktrees/5f5b/wferp/docs/superpowers/plans/2026-06-19-wferp-report-sqlite-enrichment.md。

要求：
1. 每個 Task 派 fresh subagent 實作，主 agent 做 task packet、review、整合與下一步決策。
2. 每個 Task 必須先寫 failing tests，確認失敗原因符合 plan，再做最小產品級實作。
3. 每個 Task 完成後提供 evidence packet：修改檔案、測試命令、失敗前證據、通過後證據、量化驗收與剩餘風險。
4. 正式 DB SQL 只允許單一 read-only SELECT，且只查 raw database fields，不包含 Excel lookup/formula 欄位。
5. Excel 公式、VLOOKUP、對照表、關係人、匯率表與人工分類欄位必須在本地 SQLite enrichment 階段處理。
6. Checkpoint 顯示任何 DB 欄位時，必須包含 table_id、table_name、column_id、column_name、business/source reason。
7. Data preview 必須同時顯示 raw DB result 與 SQLite enriched result。
8. SQLite table names 必須 run-scoped 且不重覆；final checkpoint 預設保留 temp tables，並可只刪除本 run manifest 內列出的 tables。
9. 不得用 fake、mock、smoke 取代 enrichment E2E；SQLite E2E 要建立真實 tables、匯入 lookup、寫入 raw rows、執行 enrichment SQL、驗證 rows/columns/aggregates/ignored lookup rows。
10. 每個 Task 通過後做小 commit。不要 stage unrelated worktree changes 或 run artifacts。
```

## File Structure

### New Python Modules

- `skill_scripts/schema_metadata.py`
  - Loads table and field display metadata from `_Source/TableName.json` and `_Source/TableStructure.json`.
  - Provides `describe_field(table_id, column_id)` and `describe_expression(inputs)`.
- `skill_scripts/workbook_classifier.py`
  - Classifies workbook output columns into `db_source_field`, `db_derived_field`, `excel_enrichment_field`, and `unresolved_field`.
  - Produces `column_classification.json`, `lookup_sheet_inventory.json`, and readable field lineage.
- `skill_scripts/sqlite_workspace.py`
  - Creates run-scoped SQLite table prefixes, writes manifests, creates/drops tables listed in the manifest, and exports table summaries.
- `skill_scripts/workbook_lookup_importer.py`
  - Imports Excel lookup sheets into SQLite tables and records ignored header/meta rows.
- `skill_scripts/formula_sqlite_translator.py`
  - Converts supported Excel formula patterns into SQLite expressions.
- `skill_scripts/sqlite_enrichment.py`
  - Builds and executes enrichment SQL from raw tables, lookup tables, and column classification.

### Modified Python Modules

- `skill_scripts/excel_intake.py`
  - Preserve richer formula/value/range metadata needed by the classifier.
- `skill_scripts/report_harness_state.py`
  - Add checkpoint definitions and state fields for classification, raw preview, enriched preview, SQLite manifest, and retention decision.
- `skill_scripts/report_harness.py`
  - Add methods for classification checkpoint, raw preview, enriched preview, SQLite manifest update, and retention checkpoint.
- `skill_scripts/cli_report_harness.py`
  - Add subcommands: `classify-workbook`, `init-sqlite-workspace`, `import-lookups`, `write-raw-table`, `run-sqlite-enrichment`, `write-raw-preview`, `write-enriched-preview`, `write-sqlite-retention`, `cleanup-sqlite-run`.
- `skill_scripts/checkpoint_companion.py`
  - Render classification, raw preview, enriched preview, and SQLite retention payloads in readable tables.
- `skill_scripts/validator_contracts.py`
  - Add validator roles: `excel_classification_reviewer`, `sqlite_enrichment_reviewer`.

### Local Skill Docs

- Modify: `/home/timmypai/.codex/skills/wferp-report/SKILL.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/harness.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/excel-intake.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/schema-context.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/sqlite-enrichment.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/field-classification.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/validators.md`

### Tests

- Create: `tests/skill_scripts/test_schema_metadata.py`
- Create: `tests/skill_scripts/test_workbook_classifier.py`
- Create: `tests/skill_scripts/test_sqlite_workspace.py`
- Create: `tests/skill_scripts/test_workbook_lookup_importer.py`
- Create: `tests/skill_scripts/test_formula_sqlite_translator.py`
- Create: `tests/skill_scripts/test_sqlite_enrichment.py`
- Modify: `tests/skill_scripts/test_cli_report_harness.py`
- Modify: `tests/skill_scripts/test_checkpoint_companion.py`
- Modify: `tests/skill_scripts/test_validator_contracts.py`
- Create: `tests/skill_scripts/test_sqlite_enrichment_expense_e2e.py`

---

## Task 1: Readable WFERP Schema Metadata

**Files:**
- Create: `skill_scripts/schema_metadata.py`
- Create: `tests/skill_scripts/test_schema_metadata.py`

- [ ] **Step 1: Write failing tests for table and field descriptions**

Add `tests/skill_scripts/test_schema_metadata.py`:

```python
from __future__ import annotations

from skill_scripts.schema_metadata import SchemaMetadata


def test_describe_field_returns_readable_table_and_column_names():
    metadata = SchemaMetadata.from_source_dir("_Source")

    field = metadata.describe_field("ACTML", "ML006")

    assert field["table_id"] == "ACTML"
    assert field["column_id"] == "ML006"
    assert field["column_name"] == "明細科目編號"
    assert field["table_name"]
    assert field["metadata_status"] == "ok"


def test_describe_missing_field_returns_warning_not_bare_code():
    metadata = SchemaMetadata.from_source_dir("_Source")

    field = metadata.describe_field("ACTML", "ZZ999")

    assert field["table_id"] == "ACTML"
    assert field["column_id"] == "ZZ999"
    assert field["column_name"] == "schema description missing"
    assert field["metadata_status"] == "warning"
    assert "ZZ999" in field["business_meaning"]


def test_describe_expression_includes_each_input_field():
    metadata = SchemaMetadata.from_source_dir("_Source")

    expression = metadata.describe_expression(
        [
            {"table_id": "ACTML", "column_id": "ML007", "reason": "借貸別"},
            {"table_id": "ACTML", "column_id": "ML014", "reason": "原幣金額"},
        ]
    )

    assert expression["metadata_status"] == "ok"
    assert [item["column_name"] for item in expression["inputs"]] == ["借貸別", "原幣金額"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/skill_scripts/test_schema_metadata.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'skill_scripts.schema_metadata'`.

- [ ] **Step 3: Implement `SchemaMetadata`**

Create `skill_scripts/schema_metadata.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SchemaMetadata:
    def __init__(self, table_names: dict[str, str], field_names: dict[tuple[str, str], str]):
        self._table_names = table_names
        self._field_names = field_names

    @classmethod
    def from_source_dir(cls, source_dir: str | Path) -> "SchemaMetadata":
        source = Path(source_dir)
        table_rows = json.loads((source / "TableName.json").read_text(encoding="utf-8"))
        field_rows = json.loads((source / "TableStructure.json").read_text(encoding="utf-8"))
        table_names: dict[str, str] = {}
        for row in table_rows:
            table_id = str(row.get("TableID", "")).strip()
            table_name = str(row.get("TableName", "") or row.get("TableNameCHT", "") or "").strip()
            if table_id:
                table_names[table_id.upper()] = table_name or "schema description missing"
        field_names: dict[tuple[str, str], str] = {}
        for row in field_rows:
            table_id = str(row.get("TableID", "")).strip().upper()
            column_id = str(row.get("ID", "")).strip().upper()
            column_name = str(row.get("FieldName", "") or row.get("Name", "") or "").strip()
            if table_id and column_id:
                field_names[(table_id, column_id)] = column_name or "schema description missing"
        return cls(table_names, field_names)

    def describe_field(
        self,
        table_id: str,
        column_id: str,
        *,
        join_reason: str = "",
        business_meaning: str = "",
    ) -> dict[str, Any]:
        table_key = table_id.strip().upper()
        column_key = column_id.strip().upper()
        table_name = self._table_names.get(table_key, "schema description missing")
        column_name = self._field_names.get((table_key, column_key), "schema description missing")
        status = "ok" if table_name != "schema description missing" and column_name != "schema description missing" else "warning"
        reason = business_meaning or f"{table_key}.{column_key} from WFERP schema"
        return {
            "table_id": table_key,
            "table_name": table_name,
            "column_id": column_key,
            "column_name": column_name,
            "join_reason": join_reason,
            "business_meaning": reason,
            "metadata_status": status,
        }

    def describe_expression(self, inputs: list[dict[str, str]]) -> dict[str, Any]:
        described = [
            self.describe_field(
                item["table_id"],
                item["column_id"],
                business_meaning=item.get("reason", ""),
            )
            for item in inputs
        ]
        status = "ok" if all(item["metadata_status"] == "ok" for item in described) else "warning"
        return {"metadata_status": status, "inputs": described}
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
pytest tests/skill_scripts/test_schema_metadata.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add skill_scripts/schema_metadata.py tests/skill_scripts/test_schema_metadata.py
git commit -m "feat: add readable schema metadata"
```

---

## Task 2: Workbook Column Classification

**Files:**
- Create: `skill_scripts/workbook_classifier.py`
- Create: `tests/skill_scripts/test_workbook_classifier.py`
- Modify: `skill_scripts/excel_intake.py`

- [ ] **Step 1: Write failing classifier tests**

Add `tests/skill_scripts/test_workbook_classifier.py`:

```python
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from skill_scripts.workbook_classifier import classify_workbook


def _classification_workbook(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "明細帳"
    ws.append(["科目編號", "傳票日期", "原幣借方金額", "原幣貸方金額", "金額-原幣", "BU", "原幣餘額"])
    ws.append(["6111", "20260101", 100, 0, "=C2-D2", "=VLOOKUP(A2,對照表!A:B,2,0)", None])
    lookup = wb.create_sheet("對照表")
    lookup.append(["科目編號", "BU"])
    lookup.append(["6111", "營運管理中心"])
    wb.save(path)


def test_classify_workbook_splits_db_derived_excel_and_unresolved_columns(tmp_path: Path):
    workbook = tmp_path / "req.xlsx"
    _classification_workbook(workbook)

    result = classify_workbook(workbook, source_dir="_Source", primary_sheet="明細帳")
    by_header = {item["excel_header"]: item for item in result["columns"]}

    assert by_header["科目編號"]["classification"] == "db_source_field"
    assert by_header["科目編號"]["field_metadata"][0]["column_name"] == "明細科目編號"
    assert by_header["傳票日期"]["classification"] == "db_source_field"
    assert by_header["金額-原幣"]["classification"] == "db_derived_field"
    assert by_header["金額-原幣"]["processing_location"] == "sqlite_enrichment"
    assert by_header["BU"]["classification"] == "excel_enrichment_field"
    assert by_header["BU"]["lookup_sheet"] == "對照表"
    assert by_header["原幣餘額"]["classification"] == "unresolved_field"
    assert result["lookup_sheet_inventory"][0]["sheet_name"] == "對照表"


def test_every_column_has_confidence_reason_and_processing_location(tmp_path: Path):
    workbook = tmp_path / "req.xlsx"
    _classification_workbook(workbook)

    result = classify_workbook(workbook, source_dir="_Source", primary_sheet="明細帳")

    for column in result["columns"]:
        assert column["confidence"] in {"high", "medium", "low"}
        assert column["reason"]
        assert column["processing_location"] in {"formal_db_sql", "sqlite_enrichment", "excluded_pending_rule"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/skill_scripts/test_workbook_classifier.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'skill_scripts.workbook_classifier'`.

- [ ] **Step 3: Implement classifier with deterministic seed mapping**

Create `skill_scripts/workbook_classifier.py`:

```python
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from skill_scripts.schema_metadata import SchemaMetadata


FIELD_SEEDS = {
    "科目編號": [{"table_id": "ACTML", "column_id": "ML006", "reason": "明細帳科目編號"}],
    "傳票日期": [{"table_id": "ACTML", "column_id": "ML002", "reason": "傳票日期"}],
    "部門代號": [{"table_id": "ACTML", "column_id": "ML010", "reason": "部門代號"}],
    "專案代號": [{"table_id": "ACTML", "column_id": "ML011", "reason": "專案代號"}],
    "摘要": [{"table_id": "ACTML", "column_id": "ML009", "reason": "摘要"}],
    "幣別": [{"table_id": "ACTML", "column_id": "ML012", "reason": "幣別"}],
    "匯率": [{"table_id": "ACTML", "column_id": "ML013", "reason": "匯率"}],
}

DERIVED_HEADERS = {"金額-原幣", "金額-本幣", "年月", "原幣借方金額", "原幣貸方金額", "本幣借方金額", "本幣貸方金額"}
UNRESOLVED_HEADERS = {"原幣餘額", "原幣借/貸餘", "本幣餘額", "本幣借/貸餘"}


def _formula_text(value: object) -> str:
    text = str(value or "")
    return text if text.startswith("=") else ""


def _lookup_sheet(formula: str) -> str:
    match = re.search(r"VLOOKUP\([^,]+,\s*([^!]+)!", formula, re.IGNORECASE)
    return match.group(1).strip("'") if match else ""


def classify_workbook(workbook_path: str | Path, *, source_dir: str | Path, primary_sheet: str = "") -> dict[str, Any]:
    workbook = load_workbook(workbook_path, data_only=False, read_only=False)
    sheet = workbook[primary_sheet] if primary_sheet else workbook[workbook.sheetnames[0]]
    headers = [str(cell.value or "").strip() for cell in sheet[1]]
    sample_row = sheet[2] if sheet.max_row >= 2 else []
    metadata = SchemaMetadata.from_source_dir(source_dir)
    columns: list[dict[str, Any]] = []
    lookup_sheets: set[str] = set()

    for index, header in enumerate(headers, start=1):
        sample = sample_row[index - 1].value if index <= len(sample_row) else None
        formula = _formula_text(sample)
        field_inputs = FIELD_SEEDS.get(header, [])
        if field_inputs:
            field_metadata = [metadata.describe_field(item["table_id"], item["column_id"], business_meaning=item["reason"]) for item in field_inputs]
            classification = "db_source_field"
            processing_location = "formal_db_sql"
            confidence = "high"
            reason = "Header matched WFERP seed mapping and field metadata is available."
            lookup_sheet = ""
        elif formula and _lookup_sheet(formula):
            classification = "excel_enrichment_field"
            processing_location = "sqlite_enrichment"
            confidence = "high"
            lookup_sheet = _lookup_sheet(formula)
            lookup_sheets.add(lookup_sheet)
            field_metadata = []
            reason = f"Formula references workbook lookup sheet {lookup_sheet}."
        elif formula or header in DERIVED_HEADERS:
            classification = "db_derived_field"
            processing_location = "sqlite_enrichment"
            confidence = "medium"
            lookup_sheet = ""
            field_metadata = []
            reason = "Column can be derived from raw database fields during SQLite enrichment."
        elif header in UNRESOLVED_HEADERS:
            classification = "unresolved_field"
            processing_location = "excluded_pending_rule"
            confidence = "medium"
            lookup_sheet = ""
            field_metadata = []
            reason = "Column requires opening-balance or external business rule before enrichment."
        else:
            classification = "unresolved_field"
            processing_location = "excluded_pending_rule"
            confidence = "low"
            lookup_sheet = ""
            field_metadata = []
            reason = "No deterministic schema, formula, or lookup evidence was found."
        columns.append(
            {
                "excel_column": index,
                "excel_header": header,
                "classification": classification,
                "processing_location": processing_location,
                "source_expression": formula,
                "lookup_sheet": lookup_sheet,
                "field_metadata": field_metadata,
                "confidence": confidence,
                "reason": reason,
                "risks": [],
            }
        )

    inventory = [{"sheet_name": name, "role": "lookup_sheet"} for name in sorted(lookup_sheets)]
    return {"workbook_path": str(workbook_path), "primary_sheet": sheet.title, "columns": columns, "lookup_sheet_inventory": inventory}
```

- [ ] **Step 4: Run classifier tests**

Run:

```bash
pytest tests/skill_scripts/test_schema_metadata.py tests/skill_scripts/test_workbook_classifier.py -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add skill_scripts/schema_metadata.py skill_scripts/workbook_classifier.py tests/skill_scripts/test_schema_metadata.py tests/skill_scripts/test_workbook_classifier.py
git commit -m "feat: classify workbook fields for sqlite enrichment"
```

---

## Task 3: SQLite Workspace and Manifest

**Files:**
- Create: `skill_scripts/sqlite_workspace.py`
- Create: `tests/skill_scripts/test_sqlite_workspace.py`

- [ ] **Step 1: Write failing workspace tests**

Add `tests/skill_scripts/test_sqlite_workspace.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

from skill_scripts.sqlite_workspace import SQLiteRunWorkspace


def test_workspace_creates_unique_run_prefix_and_manifest(tmp_path: Path):
    first = SQLiteRunWorkspace.create(tmp_path, run_id="run-001")
    second = SQLiteRunWorkspace.create(tmp_path, run_id="run-001")

    assert first.run_prefix != second.run_prefix
    assert first.raw_table.endswith("_raw_ledger")
    assert first.enriched_table.endswith("_enriched_ledger")
    assert first.manifest_path.exists()
    assert first.manifest()["cleanup_status"] == "active"


def test_workspace_writes_raw_rows_and_cleanup_only_manifest_tables(tmp_path: Path):
    workspace = SQLiteRunWorkspace.create(tmp_path, run_id="run-001")
    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        conn.execute("CREATE TABLE unrelated_table(id INTEGER)")

    workspace.write_raw_rows(
        [{"account_code": "6111", "amount": 100}, {"account_code": "6113", "amount": 200}]
    )
    workspace.register_lookup_table("lookup_account", [{"account_code": "6111", "category": "租金"}])
    workspace.cleanup_run_tables()

    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "unrelated_table" in names
    assert workspace.raw_table not in names
    assert workspace.manifest()["cleanup_status"] == "deleted"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/skill_scripts/test_sqlite_workspace.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'skill_scripts.sqlite_workspace'`.

- [ ] **Step 3: Implement workspace**

Create `skill_scripts/sqlite_workspace.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import sqlite3
from typing import Any


def _now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _sqlite_type(value: object) -> str:
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    return "TEXT"


@dataclass
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
        path.mkdir(parents=True, exist_ok=True)
        sqlite_dir = path / "sqlite"
        sqlite_dir.mkdir(parents=True, exist_ok=True)
        suffix = secrets.token_hex(2)
        safe_run = "".join(ch.lower() if ch.isalnum() else "_" for ch in run_id).strip("_")
        prefix = f"wferp_{_now_tag()}_{suffix}_{safe_run}"
        workspace = cls(
            run_dir=path,
            sqlite_db_path=sqlite_dir / "wferp-report.sqlite3",
            run_prefix=prefix,
            raw_table=f"{prefix}_raw_ledger",
            enriched_table=f"{prefix}_enriched_ledger",
            manifest_path=sqlite_dir / "sqlite_manifest.json",
        )
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
                "created_at": datetime.now(timezone.utc).isoformat(),
                "residual_risks": [],
            }
        )
        return workspace

    def manifest(self) -> dict[str, Any]:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def _write_manifest(self, payload: dict[str, Any]) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _update_manifest(self, **updates: Any) -> None:
        payload = self.manifest()
        payload.update(updates)
        self._write_manifest(payload)

    def write_raw_rows(self, rows: list[dict[str, Any]]) -> None:
        self._write_rows(self.raw_table, rows)
        self._update_manifest(raw_row_count=len(rows))

    def register_lookup_table(self, logical_name: str, rows: list[dict[str, Any]]) -> str:
        table_name = f"{self.run_prefix}_{logical_name}"
        self._write_rows(table_name, rows)
        manifest = self.manifest()
        lookup_tables = list(manifest.get("lookup_tables", []))
        if table_name not in lookup_tables:
            lookup_tables.append(table_name)
        lookup_counts = dict(manifest.get("lookup_row_counts", {}))
        lookup_counts[table_name] = len(rows)
        self._update_manifest(lookup_tables=lookup_tables, lookup_row_counts=lookup_counts)
        return table_name

    def _write_rows(self, table_name: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            raise ValueError(f"Cannot create {table_name} without rows")
        columns = list(rows[0].keys())
        definitions = ", ".join(f'"{column}" {_sqlite_type(rows[0].get(column))}' for column in columns)
        bind_marks = ", ".join("?" for _ in columns)
        quoted_columns = ", ".join(f'"{column}"' for column in columns)
        with sqlite3.connect(self.sqlite_db_path) as conn:
            conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            conn.execute(f'CREATE TABLE "{table_name}" ({definitions})')
            conn.executemany(
                f'INSERT INTO "{table_name}" ({quoted_columns}) VALUES ({bind_marks})',
                [[row.get(column) for column in columns] for row in rows],
            )

    def cleanup_run_tables(self) -> None:
        manifest = self.manifest()
        tables = [manifest["raw_table"], manifest["enriched_table"], *manifest.get("lookup_tables", [])]
        with sqlite3.connect(self.sqlite_db_path) as conn:
            for table in tables:
                conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        self._update_manifest(cleanup_status="deleted", retention_decision="delete")
```

- [ ] **Step 4: Run workspace tests**

Run:

```bash
pytest tests/skill_scripts/test_sqlite_workspace.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add skill_scripts/sqlite_workspace.py tests/skill_scripts/test_sqlite_workspace.py
git commit -m "feat: add run scoped sqlite workspace"
```

---

## Task 4: Workbook Lookup Import Hygiene

**Files:**
- Create: `skill_scripts/workbook_lookup_importer.py`
- Create: `tests/skill_scripts/test_workbook_lookup_importer.py`
- Modify: `skill_scripts/sqlite_workspace.py`

- [ ] **Step 1: Write failing lookup importer tests**

Add `tests/skill_scripts/test_workbook_lookup_importer.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

from openpyxl import Workbook

from skill_scripts.sqlite_workspace import SQLiteRunWorkspace
from skill_scripts.workbook_lookup_importer import import_lookup_sheet


def _lookup_workbook(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "對照表"
    ws.append(["科目編號", "費用類別", "費用類別 (群組)"])
    ws.append(["公司別", "AIS", "0"])
    ws.append(["科目編號", "費用類別", "費用類別 (群組)"])
    ws.append(["6111", "8.租金支出", "8.租金支出"])
    ws.append(["6113", "9001.旅費", "9001.旅費"])
    ws.append([None, None, None])
    ws.append(["加總 - 換算台幣", None, None])
    wb.save(path)


def test_import_lookup_sheet_ignores_header_meta_and_blank_rows(tmp_path: Path):
    workbook = tmp_path / "lookup.xlsx"
    _lookup_workbook(workbook)
    workspace = SQLiteRunWorkspace.create(tmp_path / "run-001", run_id="run-001")

    result = import_lookup_sheet(
        workbook,
        workspace,
        sheet_name="對照表",
        logical_name="lookup_account_category",
        key_column="A",
        value_columns={"expense_category": "B", "expense_group": "C"},
    )

    assert result["imported_row_count"] == 2
    assert result["ignored_row_count"] == 4
    assert result["ignored_rows"][0]["reason"] == "header_or_metadata"

    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        rows = conn.execute(
            f'SELECT account_code, expense_category FROM "{result["table_name"]}" ORDER BY account_code'
        ).fetchall()
    assert rows == [("6111", "8.租金支出"), ("6113", "9001.旅費")]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/skill_scripts/test_workbook_lookup_importer.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'skill_scripts.workbook_lookup_importer'`.

- [ ] **Step 3: Implement lookup importer**

Create `skill_scripts/workbook_lookup_importer.py`:

```python
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils.cell import column_index_from_string

from skill_scripts.sqlite_workspace import SQLiteRunWorkspace

META_KEYS = {"", "科目編號", "公司別", "加總 - 換算台幣", "本月匯率"}


def _cell_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_lookup_sheet(
    workbook_path: str | Path,
    workspace: SQLiteRunWorkspace,
    *,
    sheet_name: str,
    logical_name: str,
    key_column: str,
    value_columns: dict[str, str],
) -> dict[str, Any]:
    path = Path(workbook_path)
    workbook = load_workbook(path, data_only=True, read_only=True)
    sheet = workbook[sheet_name]
    key_index = column_index_from_string(key_column) - 1
    value_indexes = {name: column_index_from_string(column) - 1 for name, column in value_columns.items()}
    rows: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    for row_number, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        key = _cell_text(row[key_index] if len(row) > key_index else None)
        if key in META_KEYS or key.startswith("加總"):
            ignored.append({"row_number": row_number, "key": key, "reason": "header_or_metadata"})
            continue
        record = {"account_code": key}
        for name, index in value_indexes.items():
            record[name] = _cell_text(row[index] if len(row) > index else None)
        if not any(value for field, value in record.items() if field != "account_code"):
            ignored.append({"row_number": row_number, "key": key, "reason": "blank_values"})
            continue
        rows.append(record)
    table_name = workspace.register_lookup_table(logical_name, rows)
    manifest = workspace.manifest()
    ignored_lookup_rows = dict(manifest.get("ignored_lookup_rows", {}))
    ignored_lookup_rows[table_name] = ignored
    manifest["ignored_lookup_rows"] = ignored_lookup_rows
    manifest["source_workbook"] = str(path)
    manifest["source_workbook_hash"] = _file_hash(path)
    workspace._write_manifest(manifest)
    return {
        "table_name": table_name,
        "sheet_name": sheet_name,
        "imported_row_count": len(rows),
        "ignored_row_count": len(ignored),
        "ignored_rows": ignored,
    }
```

- [ ] **Step 4: Run lookup importer tests**

Run:

```bash
pytest tests/skill_scripts/test_workbook_lookup_importer.py tests/skill_scripts/test_sqlite_workspace.py -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add skill_scripts/workbook_lookup_importer.py skill_scripts/sqlite_workspace.py tests/skill_scripts/test_workbook_lookup_importer.py
git commit -m "feat: import workbook lookups into sqlite"
```

---

## Task 5: Formula Translation and SQLite Enrichment

**Files:**
- Create: `skill_scripts/formula_sqlite_translator.py`
- Create: `skill_scripts/sqlite_enrichment.py`
- Create: `tests/skill_scripts/test_formula_sqlite_translator.py`
- Create: `tests/skill_scripts/test_sqlite_enrichment.py`

- [ ] **Step 1: Write failing formula translator tests**

Add `tests/skill_scripts/test_formula_sqlite_translator.py`:

```python
from __future__ import annotations

from skill_scripts.formula_sqlite_translator import translate_formula


def test_translate_arithmetic_cell_formula_to_sqlite_expression():
    column_map = {"Q": '"original_debit"', "R": '"original_credit"', "AB": '"local_signed"', "AN": "4.5958"}

    assert translate_formula("=Q2-R2", column_map) == '("original_debit" - "original_credit")'
    assert translate_formula("=AN2*AB2", column_map) == "(4.5958 * \"local_signed\")"


def test_translate_mid_and_if_left_formula():
    column_map = {"F": '"voucher_no"', "A": '"account_code"'}

    assert translate_formula("=MID(F2,6,6)", column_map) == 'SUBSTR("voucher_no", 6, 6)'
    assert translate_formula('=IF(LEFT(A2,2)="57","57",LEFT(A2,1))', column_map) == (
        'CASE WHEN SUBSTR("account_code", 1, 2) = \'57\' THEN \'57\' ELSE SUBSTR("account_code", 1, 1) END'
    )


def test_unsupported_formula_returns_structured_error():
    result = translate_formula("=INDIRECT(A2)", {"A": '"account_code"'}, strict=False)

    assert result["status"] == "unsupported"
    assert result["function"] == "INDIRECT"
```

- [ ] **Step 2: Write failing enrichment tests**

Add `tests/skill_scripts/test_sqlite_enrichment.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

from skill_scripts.sqlite_enrichment import run_enrichment
from skill_scripts.sqlite_workspace import SQLiteRunWorkspace


def test_run_enrichment_creates_enriched_table_from_raw_and_lookup(tmp_path: Path):
    workspace = SQLiteRunWorkspace.create(tmp_path / "run-001", run_id="run-001")
    workspace.write_raw_rows(
        [
            {"account_code": "6111", "original_debit": 100.0, "original_credit": 0.0, "local_debit": 459.58, "local_credit": 0.0},
            {"account_code": "6113", "original_debit": 0.0, "original_credit": 25.0, "local_debit": 0.0, "local_credit": 114.895},
        ]
    )
    lookup_table = workspace.register_lookup_table(
        "lookup_account_category",
        [
            {"account_code": "6111", "expense_category": "8.租金支出"},
            {"account_code": "6113", "expense_category": "9001.旅費"},
        ],
    )

    result = run_enrichment(
        workspace,
        computed_columns=[
            {"name": "amount_original", "expression": '"original_debit" - "original_credit"'},
            {"name": "amount_local", "expression": '"local_debit" - "local_credit"'},
            {"name": "rate_2", "expression": "4.5958"},
            {"name": "amount_ntd", "expression": '4.5958 * ("local_debit" - "local_credit")'},
        ],
        lookup_columns=[
            {
                "name": "expense_category",
                "lookup_table": lookup_table,
                "raw_key": "account_code",
                "lookup_key": "account_code",
                "lookup_value": "expense_category",
            }
        ],
    )

    assert result["enriched_row_count"] == 2
    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        rows = conn.execute(
            f'SELECT account_code, amount_original, expense_category FROM "{workspace.enriched_table}" ORDER BY account_code'
        ).fetchall()
    assert rows == [("6111", 100.0, "8.租金支出"), ("6113", -25.0, "9001.旅費")]
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
pytest tests/skill_scripts/test_formula_sqlite_translator.py tests/skill_scripts/test_sqlite_enrichment.py -v
```

Expected: FAIL with missing modules.

- [ ] **Step 4: Implement formula translator**

Create `skill_scripts/formula_sqlite_translator.py`:

```python
from __future__ import annotations

import re
from typing import Any


def _col_ref(token: str, column_map: dict[str, str]) -> str:
    column = re.match(r"([A-Z]+)", token).group(1)
    return column_map[column]


def translate_formula(formula: str, column_map: dict[str, str], *, strict: bool = True) -> str | dict[str, Any]:
    text = formula.strip()
    if text.startswith("="):
        text = text[1:]
    simple = re.fullmatch(r"([A-Z]+\d+)\s*([*-])\s*([A-Z]+\d+)", text)
    if simple:
        left, op, right = simple.groups()
        return f"({_col_ref(left, column_map)} {op} {_col_ref(right, column_map)})"
    subtract = re.fullmatch(r"([A-Z]+\d+)\s*-\s*([A-Z]+\d+)", text)
    if subtract:
        left, right = subtract.groups()
        return f"({_col_ref(left, column_map)} - {_col_ref(right, column_map)})"
    mid = re.fullmatch(r"MID\(([A-Z]+\d+),\s*(\d+),\s*(\d+)\)", text, re.IGNORECASE)
    if mid:
        cell, start, length = mid.groups()
        return f"SUBSTR({_col_ref(cell, column_map)}, {start}, {length})"
    if_left = re.fullmatch(
        r'IF\(LEFT\(([A-Z]+\d+),\s*(\d+)\)="([^"]+)",\s*"([^"]+)",\s*LEFT\(([A-Z]+\d+),\s*(\d+)\)\)',
        text,
        re.IGNORECASE,
    )
    if if_left:
        test_cell, test_len, expected, true_value, else_cell, else_len = if_left.groups()
        return (
            f"CASE WHEN SUBSTR({_col_ref(test_cell, column_map)}, 1, {test_len}) = '{expected}' "
            f"THEN '{true_value}' ELSE SUBSTR({_col_ref(else_cell, column_map)}, 1, {else_len}) END"
        )
    function_match = re.match(r"([A-Z]+)\(", text, re.IGNORECASE)
    function = function_match.group(1).upper() if function_match else "UNKNOWN"
    if strict:
        raise ValueError(f"Unsupported Excel formula function: {function}")
    return {"status": "unsupported", "function": function, "formula": formula}
```

- [ ] **Step 5: Implement enrichment runner**

Create `skill_scripts/sqlite_enrichment.py`:

```python
from __future__ import annotations

import sqlite3
from typing import Any

from skill_scripts.sqlite_workspace import SQLiteRunWorkspace


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def run_enrichment(
    workspace: SQLiteRunWorkspace,
    *,
    computed_columns: list[dict[str, str]],
    lookup_columns: list[dict[str, str]],
) -> dict[str, Any]:
    select_parts = ["raw.*"]
    joins: list[str] = []
    for index, lookup in enumerate(lookup_columns):
        alias = f"lk{index}"
        joins.append(
            f'LEFT JOIN {_quote(lookup["lookup_table"])} {alias} '
            f'ON {alias}.{_quote(lookup["lookup_key"])} = raw.{_quote(lookup["raw_key"])}'
        )
        select_parts.append(f'{alias}.{_quote(lookup["lookup_value"])} AS {_quote(lookup["name"])}')
    for column in computed_columns:
        select_parts.append(f'{column["expression"]} AS {_quote(column["name"])}')
    sql = (
        f'CREATE TABLE {_quote(workspace.enriched_table)} AS '
        f'SELECT {", ".join(select_parts)} FROM {_quote(workspace.raw_table)} raw '
        + " ".join(joins)
    )
    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        conn.execute(f'DROP TABLE IF EXISTS {_quote(workspace.enriched_table)}')
        conn.execute(sql)
        row_count = conn.execute(f'SELECT COUNT(*) FROM {_quote(workspace.enriched_table)}').fetchone()[0]
    manifest = workspace.manifest()
    manifest["enriched_row_count"] = row_count
    manifest["enrichment_sql"] = sql
    workspace._write_manifest(manifest)
    return {"status": "enriched", "enriched_table": workspace.enriched_table, "enriched_row_count": row_count, "sql": sql}
```

- [ ] **Step 6: Run formula and enrichment tests**

Run:

```bash
pytest tests/skill_scripts/test_formula_sqlite_translator.py tests/skill_scripts/test_sqlite_enrichment.py -v
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add skill_scripts/formula_sqlite_translator.py skill_scripts/sqlite_enrichment.py tests/skill_scripts/test_formula_sqlite_translator.py tests/skill_scripts/test_sqlite_enrichment.py
git commit -m "feat: enrich workbook formulas in sqlite"
```

---

## Task 6: Harness CLI and Checkpoints

**Files:**
- Modify: `skill_scripts/report_harness_state.py`
- Modify: `skill_scripts/report_harness.py`
- Modify: `skill_scripts/cli_report_harness.py`
- Modify: `skill_scripts/checkpoint_companion.py`
- Modify: `tests/skill_scripts/test_cli_report_harness.py`
- Modify: `tests/skill_scripts/test_checkpoint_companion.py`

- [ ] **Step 1: Write failing CLI flow tests**

Add to `tests/skill_scripts/test_cli_report_harness.py`:

```python
def test_cli_sqlite_enrichment_flow_writes_raw_and_enriched_checkpoints(tmp_path: Path):
    run_root = tmp_path / "runs"
    run_dir = run_root / "run-sqlite"
    workbook = tmp_path / "req.xlsx"
    _write_requirement_workbook(workbook)

    created = _run_cli(
        ["create-run", "--run-root", str(run_root), "--run-id", "run-sqlite", "--prompt", "費用分析", "--input-file", str(workbook)],
        cwd=Path.cwd(),
    )
    assert created.returncode == 0, created.stderr

    classified = _run_cli(
        ["classify-workbook", "--run-dir", str(run_dir), "--input-file", str(workbook), "--primary-sheet", "明細帳"],
        cwd=Path.cwd(),
    )
    assert classified.returncode == 0, classified.stderr
    assert json.loads(classified.stdout)["checkpoint"] == "field_formula_classification"

    initialized = _run_cli(["init-sqlite-workspace", "--run-dir", str(run_dir)], cwd=Path.cwd())
    assert initialized.returncode == 0, initialized.stderr

    raw_rows = tmp_path / "raw-rows.json"
    raw_rows.write_text('[{"account_code":"6111","amount":100}]', encoding="utf-8")
    raw = _run_cli(["write-raw-table", "--run-dir", str(run_dir), "--rows", str(raw_rows)], cwd=Path.cwd())
    assert raw.returncode == 0, raw.stderr

    raw_preview = _run_cli(["write-raw-preview", "--run-dir", str(run_dir)], cwd=Path.cwd())
    assert raw_preview.returncode == 0, raw_preview.stderr
    assert json.loads(raw_preview.stdout)["checkpoint"] == "raw_data_preview"
```

- [ ] **Step 2: Write failing companion rendering test**

Add to `tests/skill_scripts/test_checkpoint_companion.py`:

```python
def test_classification_checkpoint_renders_readable_db_metadata(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="費用分析")
    harness.write_field_formula_classification(
        {
            "columns": [
                {
                    "excel_header": "科目編號",
                    "classification": "db_source_field",
                    "processing_location": "formal_db_sql",
                    "field_metadata": [
                        {
                            "table_id": "ACTML",
                            "table_name": "分類帳檔",
                            "column_id": "ML006",
                            "column_name": "明細科目編號",
                            "business_meaning": "Main ledger account code",
                            "metadata_status": "ok",
                        }
                    ],
                    "confidence": "high",
                    "reason": "Header matched schema.",
                }
            ]
        }
    )

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/current", timeout=5) as response:
            html = response.read().decode("utf-8")

    assert "科目編號" in html
    assert "明細科目編號" in html
    assert "分類帳檔" in html
    assert "ACTML.ML006" in html
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
pytest tests/skill_scripts/test_cli_report_harness.py -k sqlite_enrichment_flow -v
pytest tests/skill_scripts/test_checkpoint_companion.py -k classification_checkpoint -v
```

Expected: FAIL due missing CLI commands, checkpoint definitions, and renderer branch.

- [ ] **Step 4: Add checkpoint definitions**

Modify `skill_scripts/report_harness_state.py` by adding definitions:

```python
"field_formula_classification": {
    "index": 1.5,
    "file": "01b_field_formula_classification.json",
    "title": "欄位分類與公式確認",
    "actions": ["確認欄位分類", "要求修正"],
},
"raw_data_preview": {
    "index": 3.1,
    "file": "03a_raw_data_preview.json",
    "title": "DB 原始資料確認",
    "actions": ["原始資料正確", "重新查詢"],
},
"enriched_data_preview": {
    "index": 3.2,
    "file": "03b_enriched_data_preview.json",
    "title": "SQLite 補欄資料確認",
    "actions": ["補欄資料正確", "修正補欄規則"],
},
"sqlite_retention": {
    "index": 6.5,
    "file": "06b_sqlite_retention.json",
    "title": "SQLite 暫存資料保留確認",
    "actions": ["保留本地資料", "刪除本次資料", "匯出封存後刪除"],
},
```

- [ ] **Step 5: Add harness methods**

Modify `skill_scripts/report_harness.py` with methods:

```python
def write_field_formula_classification(self, payload: dict[str, Any]) -> dict[str, Any]:
    self.update_state(column_classification=payload)
    self.invalidate_confirmations("sql_review", "raw_data_preview", "enriched_data_preview", "report_selection")
    return record_checkpoint(self.run_dir, "field_formula_classification", payload)

def write_raw_data_preview(self, payload: dict[str, Any]) -> dict[str, Any]:
    self.update_state(raw_data_preview=payload)
    return record_checkpoint(self.run_dir, "raw_data_preview", payload)

def write_enriched_data_preview(self, payload: dict[str, Any]) -> dict[str, Any]:
    self.update_state(enriched_data_preview=payload, execution_result_summary=payload)
    return record_checkpoint(self.run_dir, "enriched_data_preview", payload)

def write_sqlite_retention(self, payload: dict[str, Any]) -> dict[str, Any]:
    self.update_state(sqlite_retention=payload)
    return record_checkpoint(self.run_dir, "sqlite_retention", payload)
```

- [ ] **Step 6: Add CLI subcommands**

Modify `skill_scripts/cli_report_harness.py` to dispatch these commands:

```python
COMMANDS.update(
    {
        "classify-workbook": _classify_workbook,
        "init-sqlite-workspace": _init_sqlite_workspace,
        "write-raw-table": _write_raw_table,
        "write-raw-preview": _write_raw_preview,
        "run-sqlite-enrichment": _run_sqlite_enrichment,
        "write-enriched-preview": _write_enriched_preview,
        "write-sqlite-retention": _write_sqlite_retention,
        "cleanup-sqlite-run": _cleanup_sqlite_run,
    }
)
```

The `_classify_workbook` command must call `classify_workbook()` and `harness.write_field_formula_classification()`. The `_init_sqlite_workspace` command must create `SQLiteRunWorkspace` and persist the manifest into harness state. The `_write_raw_table` command must load a JSON list of raw rows and write the raw table.

- [ ] **Step 7: Render checkpoint tables**

Modify `skill_scripts/checkpoint_companion.py` so classification payloads render as tables with:

- Excel header;
- classification;
- processing location;
- field display name;
- table display name;
- ERP code;
- confidence;
- reason.

Raw preview and enriched preview pages must show row count, columns, aggregates, and sample table. SQLite retention page must show manifest path, table names, row counts, and default action `保留本地資料`.

- [ ] **Step 8: Run CLI and companion tests**

Run:

```bash
pytest tests/skill_scripts/test_cli_report_harness.py -k "sqlite_enrichment_flow or wait_confirmation" -v
pytest tests/skill_scripts/test_checkpoint_companion.py -k "classification_checkpoint or current_checkpoint_page" -v
```

Expected: selected tests pass. If companion tests fail in sandbox with socket permission, rerun the same command with sandbox escalation for local bind.

- [ ] **Step 9: Commit**

```bash
git add skill_scripts/report_harness_state.py skill_scripts/report_harness.py skill_scripts/cli_report_harness.py skill_scripts/checkpoint_companion.py tests/skill_scripts/test_cli_report_harness.py tests/skill_scripts/test_checkpoint_companion.py
git commit -m "feat: add sqlite enrichment checkpoints"
```

---

## Task 7: Validator Contracts and Local Skill References

**Files:**
- Modify: `skill_scripts/validator_contracts.py`
- Modify: `tests/skill_scripts/test_validator_contracts.py`
- Modify: `/home/timmypai/.codex/skills/wferp-report/SKILL.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/harness.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/excel-intake.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/schema-context.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/validators.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/sqlite-enrichment.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/field-classification.md`

- [ ] **Step 1: Write failing validator role tests**

Add to `tests/skill_scripts/test_validator_contracts.py`:

```python
def test_required_validators_include_classification_and_sqlite_enrichment():
    assert "excel_classification_reviewer" in REQUIRED_VALIDATORS
    assert "sqlite_enrichment_reviewer" in REQUIRED_VALIDATORS


def test_sqlite_enrichment_reviewer_requires_manifest_and_row_counts():
    packet = {
        "role": "sqlite_enrichment_reviewer",
        "status": "pass",
        "evidence": [
            {"type": "file", "path": "sqlite/sqlite_manifest.json", "detail": "manifest with raw/enriched row counts"},
            {"type": "metric", "name": "raw_row_count", "value": 2},
            {"type": "metric", "name": "enriched_row_count", "value": 2},
            {"type": "metric", "name": "ignored_lookup_rows", "value": 0},
        ],
        "findings": [],
        "requiredFixes": [],
        "residualRisks": [],
    }

    result = validate_evidence_packet(packet)

    assert result["valid"] is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/skill_scripts/test_validator_contracts.py -v
```

Expected: FAIL because validator roles do not include the new reviewers.

- [ ] **Step 3: Add validator roles**

Modify `skill_scripts/validator_contracts.py`:

```python
REQUIRED_VALIDATORS = [
    "source_requirement_reviewer",
    "excel_classification_reviewer",
    "excel_formula_reviewer",
    "schema_relationship_reviewer",
    "sql_safety_reviewer",
    "sqlite_enrichment_reviewer",
    "data_preview_reviewer",
    "report_content_reviewer",
    "data_visualization_reviewer",
    "visual_taste_reviewer",
    "react_technical_reviewer",
]
```

Ensure `validate_evidence_packet()` accepts `type=file`, `type=metric`, `type=inspection`, and `type=command` evidence entries with non-empty identifying fields.

- [ ] **Step 4: Update skill references**

Create `/home/timmypai/.codex/skills/wferp-report/references/field-classification.md`:

```markdown
# Field Classification

The skill automatically classifies workbook output columns into:

- `db_source_field`
- `db_derived_field`
- `excel_enrichment_field`
- `unresolved_field`

The user should not need to manually identify these categories. Every classification must include confidence, reason, processing location, and readable WFERP field metadata when a DB field is referenced.
```

Create `/home/timmypai/.codex/skills/wferp-report/references/sqlite-enrichment.md`:

```markdown
# SQLite Enrichment

Formal DB SQL returns only raw fields. Excel formulas, VLOOKUPs, lookup sheets, related-party sheets, currency tables, and manual classifications are applied in local run-scoped SQLite tables.

Each run writes `sqlite_manifest.json`, uses unique table names, shows raw and enriched previews, and asks at final checkpoint whether to keep or delete local temp data. The default is keep.
```

Update `SKILL.md` and `harness.md` so Phase 1 includes automatic field classification, Phase 5 writes raw DB rows to SQLite, Phase 6 performs SQLite enrichment, and Phase 12 includes SQLite retention.

- [ ] **Step 5: Run validator tests**

Run:

```bash
pytest tests/skill_scripts/test_validator_contracts.py -v
```

Expected: all validator contract tests pass.

- [ ] **Step 6: Commit**

```bash
git add skill_scripts/validator_contracts.py tests/skill_scripts/test_validator_contracts.py
git commit -m "feat: add sqlite enrichment validator gates"
```

If local skill files are outside the repo, record their changed paths in the task evidence packet and do not include them in this repo commit unless the execution environment explicitly supports committing local skill files.

---

## Task 8: SQLite Enrichment Expense E2E

**Files:**
- Create: `tests/skill_scripts/test_sqlite_enrichment_expense_e2e.py`
- Modify: `tests/skill_scripts/expense_report_fixture.py`
- Modify: `tests/skill_scripts/test_expense_analysis_sqlite_e2e.py`

- [ ] **Step 1: Write failing E2E test**

Create `tests/skill_scripts/test_sqlite_enrichment_expense_e2e.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

from openpyxl import Workbook

from skill_scripts.sqlite_enrichment import run_enrichment
from skill_scripts.sqlite_workspace import SQLiteRunWorkspace
from skill_scripts.workbook_lookup_importer import import_lookup_sheet


def _expense_workbook(path: Path) -> None:
    wb = Workbook()
    detail = wb.active
    detail.title = "明細帳"
    detail.append(["科目編號", "科目名稱", "傳票日期", "本幣借方金額", "本幣貸方金額", "金額-本幣", "費用類別"])
    detail.append(["6111", "租金支出", "20260105", 1000, 0, "=D2-E2", "=VLOOKUP(A2,對照表!A:B,2,0)"])
    detail.append(["6113", "旅費", "20260106", 300, 0, "=D3-E3", "=VLOOKUP(A3,對照表!A:B,2,0)"])
    lookup = wb.create_sheet("對照表")
    lookup.append(["科目編號", "費用類別"])
    lookup.append(["公司別", "AIS"])
    lookup.append(["科目編號", "費用類別"])
    lookup.append(["6111", "8.租金支出"])
    lookup.append(["6113", "9001.旅費"])
    wb.save(path)


def test_expense_sqlite_enrichment_e2e_without_fake_or_mock(tmp_path: Path):
    workbook = tmp_path / "expense.xlsx"
    _expense_workbook(workbook)
    workspace = SQLiteRunWorkspace.create(tmp_path / "run-expense", run_id="expense")
    workspace.write_raw_rows(
        [
            {"account_code": "6111", "account_name": "租金支出", "voucher_date": "20260105", "local_debit": 1000.0, "local_credit": 0.0},
            {"account_code": "6113", "account_name": "旅費", "voucher_date": "20260106", "local_debit": 300.0, "local_credit": 0.0},
        ]
    )
    lookup = import_lookup_sheet(
        workbook,
        workspace,
        sheet_name="對照表",
        logical_name="lookup_account_category",
        key_column="A",
        value_columns={"expense_category": "B"},
    )

    result = run_enrichment(
        workspace,
        computed_columns=[{"name": "amount_local", "expression": '"local_debit" - "local_credit"'}],
        lookup_columns=[
            {
                "name": "expense_category",
                "lookup_table": lookup["table_name"],
                "raw_key": "account_code",
                "lookup_key": "account_code",
                "lookup_value": "expense_category",
            }
        ],
    )

    assert result["enriched_row_count"] == 2
    assert lookup["ignored_row_count"] == 2
    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        rows = conn.execute(
            f'SELECT account_code, amount_local, expense_category FROM "{workspace.enriched_table}" ORDER BY account_code'
        ).fetchall()
        total = conn.execute(f'SELECT SUM(amount_local) FROM "{workspace.enriched_table}"').fetchone()[0]
    assert rows == [("6111", 1000.0, "8.租金支出"), ("6113", 300.0, "9001.旅費")]
    assert total == 1300.0
    manifest = workspace.manifest()
    assert manifest["raw_row_count"] == 2
    assert manifest["enriched_row_count"] == 2
    assert manifest["cleanup_status"] == "active"
```

- [ ] **Step 2: Run E2E to verify failure**

Run:

```bash
pytest tests/skill_scripts/test_sqlite_enrichment_expense_e2e.py -v
```

Expected: FAIL until Tasks 3-5 are implemented, then pass.

- [ ] **Step 3: Integrate with existing expense SQLite E2E fixture**

Modify `tests/skill_scripts/expense_report_fixture.py` so expense E2E returns these additional keys:

```python
{
    "sqlite_manifest": workspace.manifest(),
    "raw_table": workspace.raw_table,
    "enriched_table": workspace.enriched_table,
    "ignored_lookup_rows": lookup_result["ignored_row_count"],
}
```

Modify `tests/skill_scripts/test_expense_analysis_sqlite_e2e.py` assertions:

```python
assert result["sqlite_manifest"]["raw_row_count"] >= 1
assert result["sqlite_manifest"]["enriched_row_count"] == result["sqlite_manifest"]["raw_row_count"]
assert result["ignored_lookup_rows"] >= 0
assert result["sqlite_manifest"]["cleanup_status"] == "active"
```

- [ ] **Step 4: Run full relevant tests**

Run:

```bash
pytest tests/skill_scripts/test_schema_metadata.py \
  tests/skill_scripts/test_workbook_classifier.py \
  tests/skill_scripts/test_sqlite_workspace.py \
  tests/skill_scripts/test_workbook_lookup_importer.py \
  tests/skill_scripts/test_formula_sqlite_translator.py \
  tests/skill_scripts/test_sqlite_enrichment.py \
  tests/skill_scripts/test_sqlite_enrichment_expense_e2e.py \
  tests/skill_scripts/test_expense_analysis_sqlite_e2e.py -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/skill_scripts/test_sqlite_enrichment_expense_e2e.py tests/skill_scripts/expense_report_fixture.py tests/skill_scripts/test_expense_analysis_sqlite_e2e.py
git commit -m "test: cover sqlite enrichment expense e2e"
```

---

## Final Verification

After all tasks pass, run:

```bash
python3 -m py_compile skill_scripts/schema_metadata.py \
  skill_scripts/workbook_classifier.py \
  skill_scripts/sqlite_workspace.py \
  skill_scripts/workbook_lookup_importer.py \
  skill_scripts/formula_sqlite_translator.py \
  skill_scripts/sqlite_enrichment.py \
  skill_scripts/cli_report_harness.py \
  skill_scripts/report_harness.py \
  skill_scripts/report_harness_state.py \
  skill_scripts/checkpoint_companion.py

pytest tests/skill_scripts/test_schema_metadata.py \
  tests/skill_scripts/test_workbook_classifier.py \
  tests/skill_scripts/test_sqlite_workspace.py \
  tests/skill_scripts/test_workbook_lookup_importer.py \
  tests/skill_scripts/test_formula_sqlite_translator.py \
  tests/skill_scripts/test_sqlite_enrichment.py \
  tests/skill_scripts/test_cli_report_harness.py \
  tests/skill_scripts/test_checkpoint_companion.py \
  tests/skill_scripts/test_validator_contracts.py \
  tests/skill_scripts/test_sqlite_enrichment_expense_e2e.py \
  tests/skill_scripts/test_expense_analysis_sqlite_e2e.py -v
```

Quantitative acceptance criteria:

- 100% of workbook output columns in classifier test are categorized into one of the four categories.
- 100% of DB field references in classification checkpoint include readable table and column names or a warning.
- 0 header/meta lookup rows are imported as business mappings in lookup importer tests.
- Raw and enriched row counts are recorded in `sqlite_manifest.json`.
- The expense SQLite E2E verifies enriched rows, aggregate total, ignored lookup row count, and active retention status.
- Cleanup drops only tables listed in the run manifest and leaves unrelated tables untouched.

## Plan Self-Review

- Spec coverage: Tasks cover field classification, readable DB metadata, formal DB raw SQL boundary, SQLite staging, lookup import hygiene, formula enrichment, raw/enriched checkpoints, retention manifest, subagent validators, and SQLite E2E.
- Red-flag scan: This plan gives concrete file paths, test cases, commands, and public function signatures.
- Type consistency: Core names are consistent across tasks: `SchemaMetadata`, `classify_workbook`, `SQLiteRunWorkspace`, `import_lookup_sheet`, `translate_formula`, and `run_enrichment`.
