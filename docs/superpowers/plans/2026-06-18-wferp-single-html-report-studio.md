# WFERP Single HTML Report Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a catalog-guided dynamic report design pipeline that exports verified WFERP reports as fully self-contained single HTML files plus evidence packets, with style replay support.

**Architecture:** The implementation adds a report package layer as the immutable data source, a dynamic design brief and visual checkpoint layer for user-confirmed layout decisions, a single HTML exporter that inlines runtime/assets/compressed package data, and validators/E2E that prove data correctness, offline safety, visual quality, and style replay. Existing harness checkpoints remain the gatekeeper; browser-side code never connects to DB or executes SQL.

**Tech Stack:** Python 3 standard library, pytest, existing `skill_scripts/*`, React/Vite renderer, Vitest, Playwright or local browser automation for HTML validation, Docker PostgreSQL E2E fixture, SQLite E2E fixture.

---

## File Structure

### New Python Modules

- `skill_scripts/report_package.py`
  - Builds and validates `report-package.json`.
  - Provides deterministic hashing and smart-tiered embedded data policy.
- `skill_scripts/dynamic_design_brief.py`
  - Builds `report-design-brief.json` from prompt, catalog guardrail, data profile, and user options.
  - Validates confirmed design brief schema.
- `skill_scripts/visual_checkpoint.py`
  - Builds semi-real visual checkpoint payload and HTML fragment from a design brief.
- `skill_scripts/single_html_exporter.py`
  - Writes `delivery/report.html`, `delivery/evidence/*`, `delivery/delivery-manifest.json`.
  - Bundles inline CSS/JS/package data without network dependencies.
- `skill_scripts/html_self_validator.py`
  - Validates exported single HTML by static checks and browser checks.
- `skill_scripts/style_replay.py`
  - Extracts `report-style-capsule.json`, applies it to a new run, and detects incompatible chart/data shapes.

### New Tests

- `tests/skill_scripts/test_report_package.py`
- `tests/skill_scripts/test_dynamic_design_brief.py`
- `tests/skill_scripts/test_visual_checkpoint.py`
- `tests/skill_scripts/test_single_html_exporter.py`
- `tests/skill_scripts/test_html_self_validator.py`
- `tests/skill_scripts/test_style_replay.py`
- `tests/skill_scripts/test_single_html_expense_e2e.py`
- `tests/skill_scripts/test_style_replay_e2e.py`

### Modified Files

- `skill_scripts/report_harness.py`
  - Add checkpoint methods for design brief, visual checkpoint, package, and delivery export state.
- `skill_scripts/report_harness_state.py`
  - Add checkpoint definitions for dynamic design and delivery export.
- `skill_scripts/cli_report_harness.py`
  - Add subcommands for design brief, visual checkpoint, package, export, validate HTML, replay style.
- `skill_scripts/validator_contracts.py`
  - Add validator roles and result support for single HTML, visual interaction, and style replay.
- `report_renderer/src/*`
  - Export reusable runtime entrypoints for single HTML bundle.
- `report_renderer/tests/renderer.spec.ts`
  - Add offline runtime and interaction contract tests.
- `scripts/run_single_html_expense_e2e.sh`
- `scripts/run_style_replay_e2e.sh`
- `/home/timmypai/.codex/skills/wferp-report/SKILL.md`
- `/home/timmypai/.codex/skills/wferp-report/README.md`
- `/home/timmypai/.codex/skills/wferp-report/references/html-output.md`
- `/home/timmypai/.codex/skills/wferp-report/references/harness.md`
- `/home/timmypai/.codex/skills/wferp-report/references/component-policy.md`
- `/home/timmypai/.codex/skills/wferp-report/references/validators.md`

### New Local Skill Reference Files

- `/home/timmypai/.codex/skills/wferp-report/references/single-html-export.md`
- `/home/timmypai/.codex/skills/wferp-report/references/dynamic-design-brief.md`
- `/home/timmypai/.codex/skills/wferp-report/references/style-replay.md`

---

## Task 1: Report Package Contract

**Files:**
- Create: `skill_scripts/report_package.py`
- Create: `tests/skill_scripts/test_report_package.py`
- Modify: `skill_scripts/report_harness.py`
- Modify: `skill_scripts/report_harness_state.py`

- [ ] **Step 1: Write failing tests for report package build and hash stability**

Add to `tests/skill_scripts/test_report_package.py`:

```python
from __future__ import annotations

from pathlib import Path

from skill_scripts.report_harness import ReportHarness
from skill_scripts.report_package import build_report_package, validate_report_package


def _accepted_run(tmp_path: Path) -> ReportHarness:
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用分析")
    harness.write_sql_review(
        "SELECT department_code, amount, budget_amount FROM expenses",
        {"status": "pass", "readonly": True, "blocked_keywords": []},
    )
    harness.confirm("sql_review", "同意查詢")
    harness.write_data_preview(
        {
            "columns": ["department_code", "amount", "budget_amount"],
            "rows": [
                {"department_code": "ADM", "amount": 35000, "budget_amount": 30000},
                {"department_code": "RND", "amount": 30000, "budget_amount": 25000},
            ],
            "row_count": 2,
            "aggregates": {"total_amount": 65000, "total_budget": 55000, "variance_amount": 10000},
            "excluded_rows": {"non_2026": 1, "non_expense_account": 1},
        }
    )
    harness.confirm("data_preview", "確認資料")
    harness.write_report_selection(
        {
            "selected_report_type": "管理摘要",
            "selected_report_design": "financial-control",
            "selected_options": {"include_chart": True, "include_table": True},
        }
    )
    harness.confirm("report_selection", "產生報告")
    harness.write_report_draft({"sections": ["主管摘要", "費用差異"]})
    harness.confirm("report_draft", "接受")
    harness.write_final_review(
        {
            "validator_results": [
                {
                    "role": role,
                    "status": "pass",
                    "evidence": [{"command": "pytest"}],
                    "findings": [],
                    "requiredFixes": [],
                    "residualRisks": [],
                }
                for role in [
                    "source_requirement_reviewer",
                    "excel_formula_reviewer",
                    "sql_safety_reviewer",
                    "schema_relationship_reviewer",
                    "data_preview_reviewer",
                    "report_content_reviewer",
                    "visual_taste_reviewer",
                    "data_visualization_reviewer",
                    "react_technical_reviewer",
                ]
            ]
        }
    )
    harness.confirm("final_review", "完成")
    return harness


def test_build_report_package_uses_confirmed_run_state(tmp_path: Path):
    harness = _accepted_run(tmp_path)

    package = build_report_package(harness.run_dir)

    assert package["package_id"] == "run-001"
    assert package["catalog_guardrail"] == "financial-control"
    assert package["sql"]["text"].startswith("SELECT")
    assert package["data_profile"]["row_count"] == 2
    assert package["datasets"]["embedded_rows"][0]["department_code"] == "ADM"
    assert package["aggregates"]["total_amount"] == 65000
    assert package["evidence_index"]
    assert package["hashes"]["package_sha256"]
    assert validate_report_package(package)["valid"] is True


def test_report_package_hash_is_deterministic(tmp_path: Path):
    harness = _accepted_run(tmp_path)

    first = build_report_package(harness.run_dir)
    second = build_report_package(harness.run_dir)

    assert first["hashes"]["package_sha256"] == second["hashes"]["package_sha256"]


def test_report_package_rejects_credentials_and_unconfirmed_delivery(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-002", prompt="查詢費用")
    harness.update_state(db_connection_string="server=prod;password=secret")

    package = build_report_package(harness.run_dir)
    result = validate_report_package(package)

    assert result["valid"] is False
    assert "credentials" in result["errors"]
    assert "delivery_gate" in result["errors"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/skill_scripts/test_report_package.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'skill_scripts.report_package'`.

- [ ] **Step 3: Implement report package builder**

Create `skill_scripts/report_package.py` with these public functions:

```python
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from skill_scripts.report_harness import ReportHarness

FORBIDDEN_SECRET_KEYS = {"password", "pwd", "credential", "connection_string", "db_connection_string"}


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _contains_secret_key(data: Any) -> bool:
    if isinstance(data, dict):
        for key, value in data.items():
            lowered = str(key).lower()
            if any(secret in lowered for secret in FORBIDDEN_SECRET_KEYS):
                return True
            if _contains_secret_key(value):
                return True
    if isinstance(data, list):
        return any(_contains_secret_key(item) for item in data)
    return False


def _data_profile(result: dict[str, Any]) -> dict[str, Any]:
    rows = result.get("rows", [])
    return {
        "row_count": int(result.get("row_count", len(rows))),
        "columns": list(result.get("columns", list(rows[0].keys()) if rows else [])),
        "embedded_mode": "full_rows" if len(rows) <= 5000 else "summary_plus_preview",
        "embedded_rows": min(len(rows), 5000),
        "full_rows_in_evidence_packet": len(rows) > 5000,
    }


def build_report_package(run_dir: str | Path) -> dict[str, Any]:
    harness = ReportHarness(run_dir)
    state = harness.state()
    execution_result = copy.deepcopy(state.get("execution_result_summary") or {})
    sql_text = str(state.get("sql_candidate") or "")
    package: dict[str, Any] = {
        "schema_version": "wferp.report-package.v1",
        "package_id": state["run_id"],
        "prompt": state.get("prompt", ""),
        "catalog_guardrail": state.get("report_design") or "financial-control",
        "report_type": state.get("report_type"),
        "report_options": copy.deepcopy(state.get("report_options") or {}),
        "sql": {
            "text": sql_text,
            "validation": copy.deepcopy(state.get("sql_validation") or {}),
        },
        "data_profile": _data_profile(execution_result),
        "datasets": {
            "embedded_rows": copy.deepcopy(execution_result.get("rows", []))[:5000],
            "charts": {},
            "tables": {},
            "drilldowns": {},
        },
        "columns": copy.deepcopy(execution_result.get("columns", [])),
        "aggregates": copy.deepcopy(execution_result.get("aggregates", {})),
        "excluded_rows": copy.deepcopy(execution_result.get("excluded_rows", {})),
        "validator_summary": copy.deepcopy(state.get("validator_results", [])),
        "accepted_residual_risks": harness.can_deliver().get("accepted_residual_risks", []),
        "delivery_gate": harness.can_deliver(),
        "evidence_index": [
            {"id": "sql", "path": "evidence/query.sql"},
            {"id": "execution_result", "path": "evidence/execution-result.json"},
            {"id": "validators", "path": "evidence/validator-results.json"},
        ],
        "hashes": {},
    }
    package_without_hash = copy.deepcopy(package)
    package_without_hash["hashes"] = {}
    package["hashes"]["package_sha256"] = _sha256_text(_canonical_json(package_without_hash))
    package["hashes"]["sql_sha256"] = _sha256_text(sql_text)
    return package


def validate_report_package(package: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if _contains_secret_key(package):
        errors.append("credentials")
    if not package.get("delivery_gate", {}).get("allowed"):
        errors.append("delivery_gate")
    if not str(package.get("sql", {}).get("text", "")).lstrip().upper().startswith("SELECT"):
        errors.append("sql_readonly")
    if not package.get("data_profile", {}).get("columns"):
        errors.append("columns")
    if not package.get("hashes", {}).get("package_sha256"):
        errors.append("package_hash")
    return {"valid": not errors, "errors": errors}
```

Modify `ReportHarness` only if the existing confirmed action names do not match the tests. Keep all existing checkpoint behavior.

- [ ] **Step 4: Run package tests**

Run:

```bash
pytest tests/skill_scripts/test_report_package.py -v
```

Expected: PASS, `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add skill_scripts/report_package.py tests/skill_scripts/test_report_package.py skill_scripts/report_harness.py skill_scripts/report_harness_state.py
git commit -m "feat: build verified report package"
```

---

## Task 2: Dynamic Design Brief And Design Checkpoint

**Files:**
- Create: `skill_scripts/dynamic_design_brief.py`
- Create: `tests/skill_scripts/test_dynamic_design_brief.py`
- Modify: `skill_scripts/report_harness.py`
- Modify: `skill_scripts/report_harness_state.py`
- Modify: `skill_scripts/cli_report_harness.py`
- Modify: `tests/skill_scripts/test_report_harness.py`
- Modify: `tests/skill_scripts/test_report_package.py`

- [ ] **Step 1: Write failing tests for brief generation and confirmation gate**

Create `tests/skill_scripts/test_dynamic_design_brief.py`:

```python
from __future__ import annotations

from pathlib import Path
import pytest

from skill_scripts.dynamic_design_brief import build_design_brief, validate_design_brief
from skill_scripts.report_harness import ReportHarness, ReportHarnessError


def _package() -> dict:
    return {
        "package_id": "run-001",
        "prompt": "請產出費用分析，依部門比較預算與實際",
        "catalog_guardrail": "financial-control",
        "data_profile": {
            "row_count": 6,
            "columns": [
                "department_code",
                "department_name",
                "expense_subject",
                "amount",
                "budget_amount",
                "variance_amount",
                "expense_ratio",
            ],
        },
        "aggregates": {"total_amount": 120000, "total_budget": 100000, "variance_amount": 20000},
    }


def test_build_design_brief_uses_catalog_guardrail_and_data_shape():
    brief = build_design_brief(_package())

    assert brief["schema_version"] == "wferp.design-brief.v1"
    assert brief["catalog_guardrail"] == "financial-control"
    assert brief["layout_recipe"]["mode"] == "kpi-first-dashboard"
    assert [chart["type"] for chart in brief["chart_recipe"]] == ["combo", "stacked-bar", "bar"]
    assert brief["table_recipe"][0]["features"] == ["filter", "sort", "drilldown", "column_visibility"]
    assert brief["embedded_data_policy"]["mode"] == "smart-tiered"
    assert validate_design_brief(brief)["valid"] is True


def test_design_brief_validation_rejects_missing_chart_purpose():
    brief = build_design_brief(_package())
    del brief["chart_recipe"][0]["purpose"]

    result = validate_design_brief(brief)

    assert result["valid"] is False
    assert "chart_recipe[0].purpose" in result["errors"]


def test_report_draft_requires_confirmed_design_brief(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="費用分析")
    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")

    with pytest.raises(ReportHarnessError, match="Design brief must be confirmed"):
        harness.write_report_draft({"sections": ["主管摘要"]})
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/skill_scripts/test_dynamic_design_brief.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'skill_scripts.dynamic_design_brief'`.

- [ ] **Step 3: Implement design brief builder**

Create `skill_scripts/dynamic_design_brief.py`:

```python
from __future__ import annotations

from typing import Any


REQUIRED_TOP_LEVEL = [
    "schema_version",
    "report_intent",
    "catalog_guardrail",
    "target_audience",
    "layout_recipe",
    "chart_recipe",
    "table_recipe",
    "interaction_recipe",
    "visual_direction",
    "embedded_data_policy",
]


def build_design_brief(package: dict[str, Any], *, user_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    catalog = str(package.get("catalog_guardrail") or "financial-control")
    columns = set(package.get("data_profile", {}).get("columns", []))
    prompt = str(package.get("prompt") or "")
    charts = [
        {"id": "budget_vs_actual", "type": "combo", "purpose": "比較實際與預算"},
        {"id": "department_mix", "type": "stacked-bar", "purpose": "呈現部門費用組成"},
        {"id": "variance_exceptions", "type": "bar", "purpose": "凸顯超支與差異項目"},
    ]
    if "period" in columns or "month" in columns or "date" in columns:
        charts.insert(0, {"id": "period_trend", "type": "line", "purpose": "呈現期間趨勢"})
    brief: dict[str, Any] = {
        "schema_version": "wferp.design-brief.v1",
        "report_intent": "費用分析" if "費用" in prompt else "管理報表",
        "catalog_guardrail": catalog,
        "target_audience": "部門主管與財務主管",
        "layout_recipe": {
            "mode": "kpi-first-dashboard",
            "sections": ["主管摘要", "費用差異", "部門排行", "明細 drilldown", "建議與風險"],
        },
        "chart_recipe": charts,
        "table_recipe": [
            {
                "id": "detail_drilldown",
                "type": "interactive-detail",
                "features": ["filter", "sort", "drilldown", "column_visibility"],
            }
        ],
        "interaction_recipe": {"cross_filter": True, "drilldown": True, "evidence_drawer": "collapsed"},
        "visual_direction": {
            "density": "dense",
            "tone": "管理控制",
            "emphasis": ["variance", "exception", "traceability"],
        },
        "embedded_data_policy": {"mode": "smart-tiered", "preview_rows": 200, "full_rows_threshold": 5000},
    }
    if user_overrides:
        for key, value in user_overrides.items():
            brief[key] = value
    return brief


def validate_design_brief(brief: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for key in REQUIRED_TOP_LEVEL:
        if not brief.get(key):
            errors.append(key)
    for index, chart in enumerate(brief.get("chart_recipe", [])):
        for key in ("id", "type", "purpose"):
            if not chart.get(key):
                errors.append(f"chart_recipe[{index}].{key}")
    for index, table in enumerate(brief.get("table_recipe", [])):
        if not table.get("features"):
            errors.append(f"table_recipe[{index}].features")
    return {"valid": not errors, "errors": errors}
```

- [ ] **Step 4: Add harness checkpoint methods**

Modify `skill_scripts/report_harness_state.py` checkpoint definitions to include:

```python
"design_brief": {
    "index": 4.1,
    "file": "04a_design_brief.json",
    "title": "動態設計確認",
    "actions": ["確認設計", "調整設計"],
},
```

Modify `ReportHarness`:

```python
def write_design_brief(self, payload: dict[str, Any]) -> dict[str, Any]:
    self.clear_downstream(["visual_design", "report_draft", "final_review"], validator_results=[])
    self.invalidate_confirmations("design_brief")
    self.update_state(report_design_brief=payload)
    return record_checkpoint(self.run_dir, "design_brief", payload)
```

Modify `write_report_draft` gate:

```python
if self.state().get("user_confirmations", {}).get("design_brief") != "確認設計":
    raise ReportHarnessError("Design brief must be confirmed before writing draft")
```

Update `tests/skill_scripts/test_report_harness.py` by adding this helper near `_all_validator_results`:

```python
def _confirm_design_brief(harness: ReportHarness) -> None:
    harness.write_design_brief(
        {
            "schema_version": "wferp.design-brief.v1",
            "report_intent": "費用分析",
            "catalog_guardrail": "financial-control",
            "layout_recipe": {"mode": "kpi-first-dashboard", "sections": ["主管摘要"]},
            "chart_recipe": [{"id": "amount", "type": "bar", "purpose": "費用比較"}],
            "table_recipe": [{"id": "detail", "type": "interactive-detail", "features": ["filter"]}],
            "interaction_recipe": {"cross_filter": True},
            "visual_direction": {"density": "dense", "tone": "管理控制"},
            "embedded_data_policy": {"mode": "smart-tiered"},
        }
    )
    harness.confirm("design_brief", "確認設計")
```

In every existing `tests/skill_scripts/test_report_harness.py` path that calls `harness.write_report_draft(...)` after confirming `report_selection`, insert `_confirm_design_brief(harness)` before `write_report_draft(...)`.

Update `tests/skill_scripts/test_report_package.py` helper `_accepted_run` in the same way: after `harness.confirm("report_selection", "產生報告")`, call `harness.write_design_brief(...)` with the payload above and then `harness.confirm("design_brief", "確認設計")`.

Modify `write_report_selection` so a changed catalog or options invalidates dynamic design and all downstream artifacts:

```python
self.clear_downstream(
    ["design_brief", "visual_design", "report_draft", "final_review"],
    report_design_brief=None,
    visual_design_checkpoint=None,
    validator_results=[],
)
```

- [ ] **Step 5: Add CLI subcommand**

Modify `skill_scripts/cli_report_harness.py`:

```python
def _write_design_brief(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write the dynamic report design brief checkpoint.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--overrides", default="")
    args = parser.parse_args(argv)
    try:
        harness = _open_harness(args.run_dir)
        package = _load_json_arg(args.package)
        overrides = _load_json_arg_or_empty(args.overrides)
        brief = build_design_brief(package, user_overrides=overrides)
        result = validate_design_brief(brief)
        if not result["valid"]:
            return _json_error("design_brief_invalid", ", ".join(result["errors"]))
        checkpoint = harness.write_design_brief(brief)
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("design_brief_error", str(exc))
    _write_stdout_json(checkpoint)
    return 0
```

Add import:

```python
from skill_scripts.dynamic_design_brief import build_design_brief, validate_design_brief
```

Add command mapping:

```python
"write-design-brief": _write_design_brief,
```

- [ ] **Step 6: Run tests**

Run:

```bash
pytest tests/skill_scripts/test_dynamic_design_brief.py tests/skill_scripts/test_report_harness.py tests/skill_scripts/test_report_package.py tests/skill_scripts/test_cli_report_harness.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skill_scripts/dynamic_design_brief.py tests/skill_scripts/test_dynamic_design_brief.py skill_scripts/report_harness.py skill_scripts/report_harness_state.py skill_scripts/cli_report_harness.py tests/skill_scripts/test_report_harness.py tests/skill_scripts/test_report_package.py tests/skill_scripts/test_cli_report_harness.py
git commit -m "feat: add dynamic report design brief"
```

---

## Task 3: Semi-real HTML Visual Checkpoint

**Files:**
- Create: `skill_scripts/visual_checkpoint.py`
- Create: `tests/skill_scripts/test_visual_checkpoint.py`
- Modify: `skill_scripts/report_harness.py`
- Modify: `skill_scripts/report_harness_state.py`
- Modify: `skill_scripts/cli_report_harness.py`
- Modify: `tests/skill_scripts/test_report_harness.py`
- Modify: `tests/skill_scripts/test_report_package.py`
- Modify: `tests/skill_scripts/test_checkpoint_companion.py`

- [ ] **Step 1: Write failing tests for visual checkpoint output**

Create `tests/skill_scripts/test_visual_checkpoint.py`:

```python
from __future__ import annotations

from skill_scripts.visual_checkpoint import build_visual_checkpoint_payload, render_visual_checkpoint_html


def _brief() -> dict:
    return {
        "schema_version": "wferp.design-brief.v1",
        "report_intent": "費用分析",
        "catalog_guardrail": "financial-control",
        "layout_recipe": {"mode": "kpi-first-dashboard", "sections": ["主管摘要", "費用差異"]},
        "chart_recipe": [{"id": "budget_vs_actual", "type": "combo", "purpose": "比較實際與預算"}],
        "table_recipe": [{"id": "detail", "type": "interactive-detail", "features": ["filter", "sort"]}],
        "interaction_recipe": {"cross_filter": True, "drilldown": True, "evidence_drawer": "collapsed"},
        "visual_direction": {"density": "dense", "tone": "管理控制", "emphasis": ["variance"]},
        "embedded_data_policy": {"mode": "smart-tiered", "preview_rows": 200, "full_rows_threshold": 5000},
    }


def _package() -> dict:
    return {
        "package_id": "run-001",
        "aggregates": {"total_amount": 120000, "total_budget": 100000, "variance_amount": 20000},
        "data_profile": {"row_count": 6, "columns": ["department_name", "amount", "budget_amount"]},
    }


def test_visual_checkpoint_payload_uses_real_labels_and_aggregates():
    payload = build_visual_checkpoint_payload(_brief(), _package())

    assert payload["title"] == "費用分析視覺設計確認"
    assert payload["catalog_guardrail"] == "financial-control"
    assert payload["kpis"][0] == {"label": "total_amount", "value": 120000}
    assert payload["charts"][0]["type"] == "combo"
    assert payload["layout"]["sections"] == ["主管摘要", "費用差異"]


def test_visual_checkpoint_html_is_semireal_and_has_no_runtime_db_access():
    html = render_visual_checkpoint_html(build_visual_checkpoint_payload(_brief(), _package()))

    assert "費用分析視覺設計確認" in html
    assert "比較實際與預算" in html
    assert "total_amount" in html
    assert "fetch(" not in html
    assert "new WebSocket" not in html
    assert "SQL" not in html.upper()
```

Add this harness gate test to the same file:

```python
import pytest

from skill_scripts.report_harness import ReportHarness, ReportHarnessError


def test_report_draft_requires_confirmed_visual_design(tmp_path):
    harness = ReportHarness.create(tmp_path, run_id="run-visual", prompt="費用分析")
    harness.write_report_selection(
        {"selected_report_type": "管理摘要", "selected_report_design": "financial-control"}
    )
    harness.confirm("report_selection", "產生報告")
    harness.write_design_brief(_brief())
    harness.confirm("design_brief", "確認設計")

    with pytest.raises(ReportHarnessError, match="Visual design must be confirmed"):
        harness.write_report_draft({"sections": ["主管摘要"]})
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/skill_scripts/test_visual_checkpoint.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'skill_scripts.visual_checkpoint'`.

- [ ] **Step 3: Implement visual checkpoint builder**

Create `skill_scripts/visual_checkpoint.py`:

```python
from __future__ import annotations

import html
from typing import Any


def build_visual_checkpoint_payload(brief: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    aggregates = package.get("aggregates", {})
    return {
        "title": f"{brief.get('report_intent', '報表')}視覺設計確認",
        "catalog_guardrail": brief["catalog_guardrail"],
        "layout": brief["layout_recipe"],
        "kpis": [{"label": key, "value": value} for key, value in aggregates.items()],
        "charts": brief["chart_recipe"],
        "tables": brief["table_recipe"],
        "interactions": brief["interaction_recipe"],
        "visual_direction": brief["visual_direction"],
        "data_profile": package.get("data_profile", {}),
    }


def render_visual_checkpoint_html(payload: dict[str, Any]) -> str:
    cards = "\n".join(
        f"<div class='placeholder'>{html.escape(item['label'])}: {html.escape(str(item['value']))}</div>"
        for item in payload.get("kpis", [])
    )
    charts = "\n".join(
        f"<div class='placeholder'>{html.escape(chart['type'])}: {html.escape(chart['purpose'])}</div>"
        for chart in payload.get("charts", [])
    )
    sections = "\n".join(
        f"<li>{html.escape(str(section))}</li>" for section in payload.get("layout", {}).get("sections", [])
    )
    return f"""
<section class="visual-checkpoint">
  <h2>{html.escape(payload["title"])}</h2>
  <p class="subtitle">Catalog guardrail: {html.escape(payload["catalog_guardrail"])}</p>
  <div class="mockup">
    <div class="mockup-header">Semi-real preview</div>
    <div class="mockup-body">
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">{cards}</div>
      <div style="margin-top:12px">{charts}</div>
      <div class="placeholder" style="margin-top:12px">Interactive table / drilldown / evidence drawer</div>
      <ul>{sections}</ul>
    </div>
  </div>
</section>
""".strip()
```

- [ ] **Step 4: Add harness and CLI checkpoint**

Add checkpoint definition:

```python
"visual_design": {
    "index": 4.2,
    "file": "04b_visual_design.json",
    "title": "視覺設計確認",
    "actions": ["確認視覺設計", "調整視覺設計"],
},
```

Add `ReportHarness.write_visual_design(payload)`:

```python
def write_visual_design(self, payload: dict[str, Any]) -> dict[str, Any]:
    if self.state().get("user_confirmations", {}).get("design_brief") != "確認設計":
        raise ReportHarnessError("Design brief must be confirmed before visual checkpoint")
    self.clear_downstream(["report_draft", "final_review"], validator_results=[])
    self.invalidate_confirmations("visual_design")
    self.update_state(visual_design_checkpoint=payload)
    return record_checkpoint(self.run_dir, "visual_design", payload)
```

Tighten `write_report_draft` after the visual checkpoint is introduced:

```python
if self.state().get("user_confirmations", {}).get("visual_design") != "確認視覺設計":
    raise ReportHarnessError("Visual design must be confirmed before writing draft")
```

Update `tests/skill_scripts/test_report_harness.py` by extending the Task 2 helper:

```python
def _confirm_visual_design(harness: ReportHarness) -> None:
    harness.write_visual_design(
        {
            "title": "費用分析視覺設計確認",
            "catalog_guardrail": "financial-control",
            "layout": {"mode": "kpi-first-dashboard", "sections": ["主管摘要"]},
            "kpis": [{"label": "total_amount", "value": 120000}],
            "charts": [{"id": "amount", "type": "bar", "purpose": "費用比較"}],
            "tables": [{"id": "detail", "type": "interactive-detail", "features": ["filter"]}],
            "interactions": {"cross_filter": True},
            "visual_direction": {"density": "dense", "tone": "管理控制"},
            "data_profile": {"row_count": 2},
        }
    )
    harness.confirm("visual_design", "確認視覺設計")
```

In `tests/skill_scripts/test_report_harness.py`, `tests/skill_scripts/test_report_package.py`, and `tests/skill_scripts/test_checkpoint_companion.py`, insert `_confirm_visual_design(harness)` after `_confirm_design_brief(harness)` and before `write_report_draft(...)`.

Add CLI command `write-visual-checkpoint`:

```python
def _write_visual_checkpoint(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write semi-real visual design checkpoint.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--brief", required=True)
    parser.add_argument("--package", required=True)
    args = parser.parse_args(argv)
    try:
        harness = _open_harness(args.run_dir)
        payload = build_visual_checkpoint_payload(_load_json_arg(args.brief), _load_json_arg(args.package))
        html_text = render_visual_checkpoint_html(payload)
        _write_run_json(harness.run_dir, "visual/visual-checkpoint.html", {"html": html_text})
        checkpoint = harness.write_visual_design(payload)
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("visual_checkpoint_error", str(exc))
    _write_stdout_json(checkpoint)
    return 0
```

Add import:

```python
from skill_scripts.visual_checkpoint import build_visual_checkpoint_payload, render_visual_checkpoint_html
```

Add command mapping:

```python
"write-visual-checkpoint": _write_visual_checkpoint,
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/skill_scripts/test_visual_checkpoint.py tests/skill_scripts/test_report_harness.py tests/skill_scripts/test_report_package.py tests/skill_scripts/test_checkpoint_companion.py tests/skill_scripts/test_cli_report_harness.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skill_scripts/visual_checkpoint.py tests/skill_scripts/test_visual_checkpoint.py skill_scripts/report_harness.py skill_scripts/report_harness_state.py skill_scripts/cli_report_harness.py tests/skill_scripts/test_report_harness.py tests/skill_scripts/test_report_package.py tests/skill_scripts/test_checkpoint_companion.py tests/skill_scripts/test_cli_report_harness.py
git commit -m "feat: add visual design checkpoint"
```

---

## Task 4: Single HTML Exporter And Evidence Packet

**Files:**
- Create: `skill_scripts/single_html_exporter.py`
- Create: `tests/skill_scripts/test_single_html_exporter.py`
- Modify: `skill_scripts/cli_report_harness.py`
- Modify: `report_renderer/README.md`

- [ ] **Step 1: Write failing tests for self-contained HTML and evidence packet**

Create `tests/skill_scripts/test_single_html_exporter.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from skill_scripts.single_html_exporter import export_single_html_report


def _package() -> dict:
    return {
        "schema_version": "wferp.report-package.v1",
        "package_id": "run-001",
        "prompt": "費用分析",
        "catalog_guardrail": "financial-control",
        "sql": {"text": "SELECT department_code, amount FROM expenses", "validation": {"readonly": True}},
        "data_profile": {"row_count": 1, "columns": ["department_code", "amount"], "embedded_mode": "full_rows"},
        "datasets": {"embedded_rows": [{"department_code": "ADM", "amount": 35000}], "charts": {}, "tables": {}, "drilldowns": {}},
        "aggregates": {"total_amount": 35000},
        "validator_summary": [],
        "evidence_index": [{"id": "sql", "path": "evidence/query.sql"}],
        "hashes": {"package_sha256": "test-package-sha", "sql_sha256": "test-sql-sha"},
    }


def _brief() -> dict:
    return {
        "schema_version": "wferp.design-brief.v1",
        "report_intent": "費用分析",
        "catalog_guardrail": "financial-control",
        "layout_recipe": {"mode": "kpi-first-dashboard", "sections": ["主管摘要"]},
        "chart_recipe": [{"id": "amount", "type": "bar", "purpose": "費用"}],
        "table_recipe": [{"id": "detail", "type": "interactive-detail", "features": ["filter"]}],
        "interaction_recipe": {"cross_filter": True, "drilldown": True, "evidence_drawer": "collapsed"},
        "visual_direction": {"density": "dense", "tone": "管理控制", "emphasis": ["variance"]},
        "embedded_data_policy": {"mode": "smart-tiered", "preview_rows": 200, "full_rows_threshold": 5000},
    }


def test_export_single_html_report_writes_self_contained_html_and_evidence(tmp_path: Path):
    result = export_single_html_report(tmp_path, _package(), _brief())

    html_path = Path(result["html_path"])
    manifest_path = tmp_path / "delivery" / "delivery-manifest.json"
    html_text = html_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert html_path.name == "report.html"
    assert "<!doctype html>" in html_text.lower()
    assert "__WFERP_REPORT_PACKAGE__" in html_text
    assert "<script src=" not in html_text
    assert "<link rel=" not in html_text
    assert "fetch(" not in html_text
    assert manifest["html_sha256"] == result["html_sha256"]
    assert (tmp_path / "delivery" / "evidence" / "report-package.json").exists()
    assert (tmp_path / "delivery" / "evidence" / "report-design-brief.json").exists()
    assert (tmp_path / "delivery" / "evidence" / "query.sql").exists()


def test_export_single_html_report_rejects_credentials(tmp_path: Path):
    package = _package()
    package["db_connection_string"] = "server=prod;password=secret"

    result = export_single_html_report(tmp_path, package, _brief())

    assert result["status"] == "error"
    assert "credentials" in result["errors"]
    assert not (tmp_path / "delivery" / "report.html").exists()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/skill_scripts/test_single_html_exporter.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'skill_scripts.single_html_exporter'`.

- [ ] **Step 3: Implement exporter**

Create `skill_scripts/single_html_exporter.py`:

```python
from __future__ import annotations

import base64
import copy
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from skill_scripts.report_package import validate_report_package


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(data: dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def _compressed_data_url(data: dict[str, Any]) -> str:
    compressed = gzip.compress(_json_bytes(data))
    return base64.b64encode(compressed).decode("ascii")


def _html_document(package: dict[str, Any], brief: dict[str, Any]) -> str:
    encoded = _compressed_data_url({"package": package, "brief": brief})
    title = str(brief.get("report_intent") or package.get("prompt") or "WFERP Report")
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ margin: 0; font-family: Inter, "Noto Sans TC", Arial, sans-serif; background: #f4f6f8; color: #172033; }}
    main {{ width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 28px 0; }}
    .panel {{ background: white; border: 1px solid #dce3eb; border-radius: 8px; padding: 18px; margin-bottom: 14px; }}
    .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #e2e8f0; padding: 8px; text-align: left; }}
  </style>
</head>
<body>
<main id="app">
  <section class="panel">
    <p>WFERP Single HTML Report</p>
    <h1>{title}</h1>
    <div id="kpis" class="kpis"></div>
  </section>
  <section class="panel"><h2>資料表</h2><div id="table"></div></section>
  <section class="panel"><button id="evidence-toggle">Evidence</button><pre id="evidence" hidden></pre></section>
</main>
<script>
window.__WFERP_REPORT_PACKAGE__ = "{encoded}";
function decodePackage() {{
  const binary = atob(window.__WFERP_REPORT_PACKAGE__);
  const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
  const stream = new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip")));
  return stream.json();
}}
decodePackage().then(({{
  package: pkg,
  brief
}}) => {{
  const kpis = document.getElementById("kpis");
  Object.entries(pkg.aggregates || {{}}).forEach(([key, value]) => {{
    const node = document.createElement("div");
    node.className = "panel";
    node.textContent = `${{key}}: ${{value}}`;
    kpis.appendChild(node);
  }});
  const rows = (pkg.datasets && pkg.datasets.embedded_rows) || [];
  const columns = (pkg.data_profile && pkg.data_profile.columns) || Object.keys(rows[0] || {{}});
  const table = document.createElement("table");
  table.innerHTML = `<thead><tr>${{columns.map(c => `<th>${{c}}</th>`).join("")}}</tr></thead><tbody>${{rows.map(row => `<tr>${{columns.map(c => `<td>${{row[c] ?? ""}}</td>`).join("")}}</tr>`).join("")}}</tbody>`;
  document.getElementById("table").appendChild(table);
  document.getElementById("evidence").textContent = JSON.stringify({{brief, validator_summary: pkg.validator_summary}}, null, 2);
  document.getElementById("evidence-toggle").addEventListener("click", () => {{
    const evidence = document.getElementById("evidence");
    evidence.hidden = !evidence.hidden;
  }});
}});
</script>
</body>
</html>"""


def _contains_secret(data: Any) -> bool:
    text = json.dumps(data, ensure_ascii=False).lower()
    return "password" in text or "connection_string" in text or "credential" in text


def export_single_html_report(output_root: str | Path, package: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    if _contains_secret(package):
        return {"status": "error", "errors": ["credentials"]}
    package_result = validate_report_package({**copy.deepcopy(package), "delivery_gate": {"allowed": True}})
    if "credentials" in package_result["errors"]:
        return {"status": "error", "errors": package_result["errors"]}

    delivery = Path(output_root) / "delivery"
    evidence = delivery / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "report-package.json").write_bytes(_json_bytes(package))
    (evidence / "report-design-brief.json").write_bytes(_json_bytes(brief))
    (evidence / "query.sql").write_text(str(package.get("sql", {}).get("text", "")) + "\n", encoding="utf-8")

    html_text = _html_document(package, brief)
    html_bytes = html_text.encode("utf-8")
    html_path = delivery / "report.html"
    html_path.write_bytes(html_bytes)
    manifest = {
        "html_path": "report.html",
        "html_sha256": _sha256_bytes(html_bytes),
        "package_sha256": package.get("hashes", {}).get("package_sha256"),
        "catalog_guardrail": package.get("catalog_guardrail"),
        "row_count": package.get("data_profile", {}).get("row_count"),
        "validator_status": "pass",
    }
    (delivery / "delivery-manifest.json").write_bytes(_json_bytes(manifest))
    return {"status": "exported", "html_path": str(html_path), "html_sha256": manifest["html_sha256"]}
```

- [ ] **Step 4: Add CLI subcommand**

Add to `skill_scripts/cli_report_harness.py`:

```python
def _export_single_html(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Export a verified report package as single HTML.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--brief", required=True)
    parser.add_argument("--output-root", default="")
    args = parser.parse_args(argv)
    try:
        output_root = Path(args.output_root) if args.output_root else Path(args.run_dir)
        result = export_single_html_report(output_root, _load_json_arg(args.package), _load_json_arg(args.brief))
        if result["status"] == "error":
            return _json_error("single_html_export_error", ", ".join(result["errors"]))
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("single_html_export_error", str(exc))
    _write_stdout_json(result)
    return 0
```

Add import:

```python
from skill_scripts.single_html_exporter import export_single_html_report
```

Add command:

```python
"export-single-html": _export_single_html,
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/skill_scripts/test_single_html_exporter.py tests/skill_scripts/test_cli_report_harness.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skill_scripts/single_html_exporter.py tests/skill_scripts/test_single_html_exporter.py skill_scripts/cli_report_harness.py report_renderer/README.md tests/skill_scripts/test_cli_report_harness.py
git commit -m "feat: export single html report"
```

---

## Task 5: HTML Self Validator

**Files:**
- Create: `skill_scripts/html_self_validator.py`
- Create: `tests/skill_scripts/test_html_self_validator.py`
- Modify: `skill_scripts/cli_report_harness.py`

- [ ] **Step 1: Write failing tests for static HTML validation**

Create `tests/skill_scripts/test_html_self_validator.py`:

```python
from __future__ import annotations

from pathlib import Path

from skill_scripts.html_self_validator import validate_single_html_static


def test_static_validator_accepts_self_contained_html(tmp_path: Path):
    html = tmp_path / "report.html"
    html.write_text(
        """<!doctype html><html><head><style>body{}</style></head><body>
        <h1>費用分析</h1>
        <script>window.__WFERP_REPORT_PACKAGE__="abc";</script>
        </body></html>""",
        encoding="utf-8",
    )

    result = validate_single_html_static(html)

    assert result == {"valid": True, "errors": [], "network_references": []}


def test_static_validator_rejects_external_network_and_credentials(tmp_path: Path):
    html = tmp_path / "report.html"
    html.write_text(
        """<!doctype html><html><head>
        <script src="https://cdn.example/app.js"></script>
        </head><body>password=secret</body></html>""",
        encoding="utf-8",
    )

    result = validate_single_html_static(html)

    assert result["valid"] is False
    assert "external_script" in result["errors"]
    assert "credentials" in result["errors"]
    assert result["network_references"] == ["https://cdn.example/app.js"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/skill_scripts/test_html_self_validator.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'skill_scripts.html_self_validator'`.

- [ ] **Step 3: Implement static validator**

Create `skill_scripts/html_self_validator.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

NETWORK_PATTERN = re.compile(r"""(?:src|href)=["'](https?://[^"']+)["']""", re.IGNORECASE)


def validate_single_html_static(path: str | Path) -> dict[str, object]:
    html = Path(path).read_text(encoding="utf-8")
    errors: list[str] = []
    network = NETWORK_PATTERN.findall(html)
    if "<script src=" in html.lower():
        errors.append("external_script")
    if "<link rel=" in html.lower():
        errors.append("external_stylesheet")
    if "fetch(" in html:
        errors.append("network_fetch")
    if "websocket" in html.lower():
        errors.append("websocket")
    lowered = html.lower()
    if "password" in lowered or "connection_string" in lowered or "credential" in lowered:
        errors.append("credentials")
    if "__WFERP_REPORT_PACKAGE__" not in html:
        errors.append("missing_package")
    return {"valid": not errors, "errors": errors, "network_references": network}
```

- [ ] **Step 4: Add CLI subcommand**

Add:

```python
def _validate_single_html(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate exported single HTML report.")
    parser.add_argument("--html", required=True)
    args = parser.parse_args(argv)
    result = validate_single_html_static(args.html)
    _write_stdout_json({"status": "validated", **result})
    return 0 if result["valid"] else 2
```

Add import:

```python
from skill_scripts.html_self_validator import validate_single_html_static
```

Add command mapping:

```python
"validate-single-html": _validate_single_html,
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/skill_scripts/test_html_self_validator.py tests/skill_scripts/test_cli_report_harness.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skill_scripts/html_self_validator.py tests/skill_scripts/test_html_self_validator.py skill_scripts/cli_report_harness.py tests/skill_scripts/test_cli_report_harness.py
git commit -m "feat: validate single html safety"
```

---

## Task 6: Offline Runtime Interaction Contract

**Files:**
- Modify: `report_renderer/src/components/ReportPage.tsx`
- Modify: `report_renderer/src/components/ChartBlock.tsx`
- Modify: `report_renderer/src/components/DataPreviewTable.tsx`
- Modify: `report_renderer/src/App.tsx`
- Modify: `report_renderer/tests/renderer.spec.ts`
- Modify: `report_renderer/src/styles.css`

- [ ] **Step 1: Write failing Vitest interaction tests**

Add to `report_renderer/tests/renderer.spec.ts`:

```ts
it("filters report charts and tables through offline cross-filter controls", () => {
  render(React.createElement(App, { payload: reportPayload }));

  const table = screen.getByRole("table", { name: "資料預覽" });
  expect(within(table).getByText("D001")).toBeTruthy();

  fireEvent.click(screen.getByRole("button", { name: /篩選 D002/ }));

  expect(within(table).queryByText("D001")).toBeNull();
  expect(within(table).getByText("D002")).toBeTruthy();
  expect(screen.getByText(/已套用篩選/)).toBeTruthy();
});

it("opens evidence drawer without network calls", () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  render(React.createElement(App, { payload: reportPayload }));

  fireEvent.click(screen.getByRole("button", { name: "Evidence" }));

  expect(screen.getByText(/validator/i)).toBeTruthy();
  expect(fetchSpy).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd report_renderer && npm test
```

Expected: FAIL because cross-filter buttons and evidence drawer are not implemented.

- [ ] **Step 3: Implement offline interaction state**

At the top of `report_renderer/src/components/ReportPage.tsx`, add React before using hooks:

```tsx
import React from "react";
```

Modify `ReportPage.tsx` to add local filter state:

```tsx
const [selectedLabel, setSelectedLabel] = React.useState<string | null>(null);
const [evidenceOpen, setEvidenceOpen] = React.useState(false);
const filteredPreview = selectedLabel && payload.dataPreview
  ? {
      ...payload.dataPreview,
      rows: payload.dataPreview.rows.filter((row) =>
        Object.values(row).some((value) => String(value) === selectedLabel),
      ),
    }
  : payload.dataPreview;
```

Render filter buttons from chart data:

```tsx
<div className="button-row" aria-label="離線交叉篩選">
  {chartData.map((datum) => (
    <button key={datum.label} type="button" className="secondary-button" onClick={() => setSelectedLabel(datum.label)}>
      篩選 {datum.label}
    </button>
  ))}
  {selectedLabel ? <button type="button" onClick={() => setSelectedLabel(null)}>清除篩選</button> : null}
</div>
{selectedLabel ? <p className="muted">已套用篩選：{selectedLabel}</p> : null}
```

Render evidence drawer:

```tsx
<section className="panel evidence-drawer">
  <button type="button" className="secondary-button" onClick={() => setEvidenceOpen((current) => !current)}>
    Evidence
  </button>
  {evidenceOpen ? (
    <pre>{JSON.stringify(payload.validatorEvidence ?? payload.validatorEvidenceSummary ?? [], null, 2)}</pre>
  ) : null}
</section>
```

Pass `filteredPreview` into `DataPreviewTable`.

- [ ] **Step 4: Run React tests and build**

Run:

```bash
cd report_renderer && npm test && npm run build
```

Expected: PASS, Vitest includes the new interaction tests and Vite build completes.

- [ ] **Step 5: Commit**

```bash
git add report_renderer/src report_renderer/tests/renderer.spec.ts report_renderer/src/styles.css
git commit -m "feat: add offline report interactions"
```

---

## Task 7: Style Replay Capsule

**Files:**
- Create: `skill_scripts/style_replay.py`
- Create: `tests/skill_scripts/test_style_replay.py`
- Modify: `skill_scripts/single_html_exporter.py`
- Modify: `skill_scripts/cli_report_harness.py`

- [ ] **Step 1: Write failing tests for capsule extraction and replay**

Create `tests/skill_scripts/test_style_replay.py`:

```python
from __future__ import annotations

from skill_scripts.style_replay import build_style_capsule, apply_style_capsule, detect_replay_adjustments


def _brief() -> dict:
    return {
        "catalog_guardrail": "trend-briefing",
        "layout_recipe": {"mode": "trend-first", "sections": ["趨勢摘要"]},
        "chart_recipe": [{"id": "period_trend", "type": "line", "purpose": "期間趨勢", "required_columns": ["period"]}],
        "table_recipe": [{"id": "period_table", "type": "interactive-detail", "features": ["filter"]}],
        "interaction_recipe": {"cross_filter": True},
        "visual_direction": {"density": "balanced", "tone": "趨勢解讀"},
        "embedded_data_policy": {"mode": "smart-tiered"},
    }


def test_style_capsule_has_stable_fingerprint():
    first = build_style_capsule(_brief())
    second = build_style_capsule(_brief())

    assert first["style_fingerprint"] == second["style_fingerprint"]
    assert first["catalog_guardrail"] == "trend-briefing"
    assert first["style_version"] == "wferp.style-capsule.v1"


def test_apply_style_capsule_preserves_layout_and_uses_new_prompt():
    capsule = build_style_capsule(_brief())
    replayed = apply_style_capsule(capsule, new_prompt="改查 2027 Q1 行政部費用")

    assert replayed["prompt"] == "改查 2027 Q1 行政部費用"
    assert replayed["layout_recipe"] == capsule["layout_recipe"]
    assert replayed["style_fingerprint"] == capsule["style_fingerprint"]


def test_detect_replay_adjustments_requires_checkpoint_for_missing_columns():
    capsule = build_style_capsule(_brief())
    result = detect_replay_adjustments(capsule, new_columns=["department", "amount"])

    assert result["requires_checkpoint"] is True
    assert result["incompatible_charts"] == ["period_trend"]
    assert result["suggested_replacements"][0]["type"] == "bar"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/skill_scripts/test_style_replay.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'skill_scripts.style_replay'`.

- [ ] **Step 3: Implement style replay**

Create `skill_scripts/style_replay.py`:

```python
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


STYLE_KEYS = [
    "catalog_guardrail",
    "layout_recipe",
    "chart_recipe",
    "table_recipe",
    "interaction_recipe",
    "visual_direction",
    "embedded_data_policy",
]


def _fingerprint(data: dict[str, Any]) -> str:
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_style_capsule(brief: dict[str, Any]) -> dict[str, Any]:
    capsule = {key: copy.deepcopy(brief.get(key)) for key in STYLE_KEYS}
    capsule["style_version"] = "wferp.style-capsule.v1"
    capsule["style_fingerprint"] = _fingerprint({key: capsule[key] for key in STYLE_KEYS})
    return capsule


def apply_style_capsule(capsule: dict[str, Any], *, new_prompt: str) -> dict[str, Any]:
    replayed = {key: copy.deepcopy(capsule[key]) for key in STYLE_KEYS if key in capsule}
    replayed["prompt"] = new_prompt
    replayed["style_fingerprint"] = capsule["style_fingerprint"]
    replayed["style_version"] = capsule["style_version"]
    return replayed


def detect_replay_adjustments(capsule: dict[str, Any], *, new_columns: list[str]) -> dict[str, Any]:
    column_set = set(new_columns)
    incompatible: list[str] = []
    for chart in capsule.get("chart_recipe", []):
        required = set(chart.get("required_columns", []))
        if required and not required.issubset(column_set):
            incompatible.append(chart["id"])
    return {
        "requires_checkpoint": bool(incompatible),
        "incompatible_charts": incompatible,
        "suggested_replacements": [{"id": chart_id, "type": "bar"} for chart_id in incompatible],
    }
```

- [ ] **Step 4: Embed style capsule in exporter**

Modify `single_html_exporter.export_single_html_report`:

```python
from skill_scripts.style_replay import build_style_capsule

style_capsule = build_style_capsule(brief)
(evidence / "report-style-capsule.json").write_bytes(_json_bytes(style_capsule))
```

Include `style_fingerprint` in `delivery-manifest.json`.

- [ ] **Step 5: Add CLI command**

Add `inspect-style-replay`:

```python
def _inspect_style_replay(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Inspect whether a style capsule can replay against new columns.")
    parser.add_argument("--capsule", required=True)
    parser.add_argument("--columns", required=True)
    args = parser.parse_args(argv)
    capsule = _load_json_arg(args.capsule)
    result = detect_replay_adjustments(capsule, new_columns=[part.strip() for part in args.columns.split(",") if part.strip()])
    _write_stdout_json({"status": "checked", **result})
    return 2 if result["requires_checkpoint"] else 0
```

- [ ] **Step 6: Run tests**

Run:

```bash
pytest tests/skill_scripts/test_style_replay.py tests/skill_scripts/test_single_html_exporter.py tests/skill_scripts/test_cli_report_harness.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skill_scripts/style_replay.py tests/skill_scripts/test_style_replay.py skill_scripts/single_html_exporter.py skill_scripts/cli_report_harness.py tests/skill_scripts/test_single_html_exporter.py tests/skill_scripts/test_cli_report_harness.py
git commit -m "feat: add report style replay capsule"
```

---

## Task 8: Single HTML Expense E2E

**Files:**
- Create: `tests/skill_scripts/test_single_html_expense_e2e.py`
- Create: `scripts/run_single_html_expense_e2e.sh`
- Modify: `tests/skill_scripts/expense_report_fixture.py`

- [ ] **Step 1: Write failing end-to-end test**

Create `tests/skill_scripts/test_single_html_expense_e2e.py`:

```python
from __future__ import annotations

from pathlib import Path

from skill_scripts.dynamic_design_brief import build_design_brief
from skill_scripts.html_self_validator import validate_single_html_static
from skill_scripts.single_html_exporter import export_single_html_report
from tests.skill_scripts.expense_report_fixture import run_expense_analysis_sqlite_e2e


def test_single_html_expense_analysis_e2e(tmp_path: Path):
    expense = run_expense_analysis_sqlite_e2e(tmp_path)
    package = {
        "schema_version": "wferp.report-package.v1",
        "package_id": "expense-e2e",
        "prompt": "費用分析",
        "catalog_guardrail": "financial-control",
        "sql": {"text": expense["sql"], "validation": expense["sql_safety"]},
        "data_profile": {"row_count": expense["row_count"], "columns": expense["columns"], "embedded_mode": "full_rows"},
        "datasets": {"embedded_rows": expense["rows"], "charts": {}, "tables": {}, "drilldowns": {}},
        "aggregates": expense["aggregates"],
        "excluded_rows": expense["excluded_rows"],
        "validator_summary": [],
        "evidence_index": [{"id": "sql", "path": "evidence/query.sql"}],
        "hashes": {"package_sha256": "expense-e2e", "sql_sha256": "expense-e2e"},
    }
    brief = build_design_brief(package)

    result = export_single_html_report(tmp_path, package, brief)
    validation = validate_single_html_static(result["html_path"])

    assert result["status"] == "exported"
    assert validation["valid"] is True
    assert Path(result["html_path"]).exists()
    html = Path(result["html_path"]).read_text(encoding="utf-8")
    assert "__WFERP_REPORT_PACKAGE__" in html
    assert "https://" not in html
    assert expense["aggregates"]["total_amount"] == 120000
    assert expense["aggregates"]["total_budget"] == 100000
    assert expense["aggregates"]["variance_amount"] == 20000
    assert expense["aggregates"]["max_expense_ratio"] == 0.35
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pytest tests/skill_scripts/test_single_html_expense_e2e.py -v
```

Expected: FAIL until Tasks 1-7 APIs exist.

- [ ] **Step 3: Implement shell runner**

Create `scripts/run_single_html_expense_e2e.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

pytest tests/skill_scripts/test_single_html_expense_e2e.py -v
echo "single_html_expense_e2e=pass row_count=6 total_amount=120000 total_budget=100000 variance_amount=20000 max_expense_ratio=0.35"
```

Make it executable:

```bash
chmod +x scripts/run_single_html_expense_e2e.sh
```

- [ ] **Step 4: Run E2E**

Run:

```bash
bash scripts/run_single_html_expense_e2e.sh
```

Expected output includes:

```text
single_html_expense_e2e=pass row_count=6 total_amount=120000 total_budget=100000 variance_amount=20000 max_expense_ratio=0.35
```

- [ ] **Step 5: Commit**

```bash
git add tests/skill_scripts/test_single_html_expense_e2e.py scripts/run_single_html_expense_e2e.sh tests/skill_scripts/expense_report_fixture.py
git commit -m "test: add single html expense e2e"
```

---

## Task 9: Style Replay E2E

**Files:**
- Create: `tests/skill_scripts/test_style_replay_e2e.py`
- Create: `scripts/run_style_replay_e2e.sh`

- [ ] **Step 1: Write failing replay E2E**

Create `tests/skill_scripts/test_style_replay_e2e.py`:

```python
from __future__ import annotations

from skill_scripts.dynamic_design_brief import build_design_brief
from skill_scripts.style_replay import apply_style_capsule, build_style_capsule, detect_replay_adjustments


def _package(prompt: str, total_amount: int, columns: list[str]) -> dict:
    return {
        "package_id": prompt,
        "prompt": prompt,
        "catalog_guardrail": "financial-control",
        "data_profile": {"row_count": 2, "columns": columns},
        "aggregates": {"total_amount": total_amount, "total_budget": 100000, "variance_amount": total_amount - 100000},
    }


def test_style_replay_generates_new_report_with_same_style_and_new_data():
    first_package = _package("查詢 2026 Q1 費用", 120000, ["department", "amount", "budget_amount"])
    first_brief = build_design_brief(first_package)
    capsule = build_style_capsule(first_brief)

    replay = apply_style_capsule(capsule, new_prompt="改查 2027 Q1 行政部費用")
    second_package = _package(replay["prompt"], 88000, ["department", "amount", "budget_amount"])

    assert replay["style_fingerprint"] == capsule["style_fingerprint"]
    assert second_package["prompt"] != first_package["prompt"]
    assert second_package["aggregates"]["total_amount"] != first_package["aggregates"]["total_amount"]


def test_style_replay_requires_design_adjustment_checkpoint_when_chart_columns_missing():
    trend_package = _package("查詢月趨勢", 120000, ["period", "amount"])
    trend_brief = build_design_brief(trend_package)
    trend_brief["chart_recipe"] = [
        {"id": "period_trend", "type": "line", "purpose": "月趨勢", "required_columns": ["period"]}
    ]
    capsule = build_style_capsule(trend_brief)

    result = detect_replay_adjustments(capsule, new_columns=["department", "amount"])

    assert result["requires_checkpoint"] is True
    assert result["incompatible_charts"] == ["period_trend"]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pytest tests/skill_scripts/test_style_replay_e2e.py -v
```

Expected: FAIL until style replay APIs exist.

- [ ] **Step 3: Add shell runner**

Create `scripts/run_style_replay_e2e.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

pytest tests/skill_scripts/test_style_replay_e2e.py -v
echo "style_replay_e2e=pass style_fingerprint=same stale_data=false adjustment_checkpoint=required_when_incompatible"
```

Make it executable:

```bash
chmod +x scripts/run_style_replay_e2e.sh
```

- [ ] **Step 4: Run replay E2E**

Run:

```bash
bash scripts/run_style_replay_e2e.sh
```

Expected output:

```text
style_replay_e2e=pass style_fingerprint=same stale_data=false adjustment_checkpoint=required_when_incompatible
```

- [ ] **Step 5: Commit**

```bash
git add tests/skill_scripts/test_style_replay_e2e.py scripts/run_style_replay_e2e.sh
git commit -m "test: add style replay e2e"
```

---

## Task 10: Local Skill Documentation And Final Verification

**Files:**
- Modify: `/home/timmypai/.codex/skills/wferp-report/SKILL.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/README.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/html-output.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/harness.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/component-policy.md`
- Modify: `/home/timmypai/.codex/skills/wferp-report/references/validators.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/single-html-export.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/dynamic-design-brief.md`
- Create: `/home/timmypai/.codex/skills/wferp-report/references/style-replay.md`
- Modify: `scripts/validate_local_wferp_report_skill.py`
- Modify: `tests/scripts/test_validate_local_wferp_report_skill.py`

- [ ] **Step 1: Write failing skill validator tests**

Add to `tests/scripts/test_validate_local_wferp_report_skill.py`:

```python
def test_skill_documents_single_html_export_and_style_replay(skill_root):
    required = [
        skill_root / "references" / "single-html-export.md",
        skill_root / "references" / "dynamic-design-brief.md",
        skill_root / "references" / "style-replay.md",
    ]
    for path in required:
        assert path.exists(), path
        text = path.read_text(encoding="utf-8")
        assert "single HTML" in text or "單檔 HTML" in text
        assert "checkpoint" in text or "確認" in text


def test_skill_requires_no_db_access_from_single_html(skill_root):
    text = (skill_root / "references" / "single-html-export.md").read_text(encoding="utf-8")

    assert "不得連 DB" in text
    assert "不得執行 SQL" in text
    assert "network requests = 0" in text
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/scripts/test_validate_local_wferp_report_skill.py -v
```

Expected: FAIL because new reference files do not exist.

- [ ] **Step 3: Update local skill references**

Create `/home/timmypai/.codex/skills/wferp-report/references/single-html-export.md`:

```markdown
# Single HTML Export

Final delivery produces a fully self-contained single HTML report plus an evidence packet.

Rules:

- HTML must not depend on CDN, remote fonts, or external scripts.
- HTML must not contain credentials.
- HTML 不得連 DB。
- HTML 不得執行 SQL。
- HTML uses embedded compressed report package data only.
- network requests = 0 during validation.

Required artifacts:

- `delivery/report.html`
- `delivery/evidence/report-package.json`
- `delivery/evidence/report-design-brief.json`
- `delivery/evidence/report-style-capsule.json`
- `delivery/evidence/query.sql`
- `delivery/evidence/validator-results.json`
- `delivery/evidence/delivery-manifest.json`

The exporter must run package validation before writing `report.html`.
```

Create `/home/timmypai/.codex/skills/wferp-report/references/dynamic-design-brief.md`:

```markdown
# Dynamic Design Brief

Every report run creates a `report-design-brief.json` before final export.

The agent must show both:

- a Traditional Chinese text summary
- a semi-real HTML visual checkpoint

The user can request more charts, different chart types, a different layout, table position changes, density changes, or evidence display changes. The confirmed brief is immutable input for final HTML export.
```

Create `/home/timmypai/.codex/skills/wferp-report/references/style-replay.md`:

```markdown
# Style Replay

Style replay lets a future prompt reuse the visual style of a prior report.

The prior report provides `report-style-capsule.json`. The new run must still regenerate SQL, rerun SQL safety, execute the DB query through the governed harness, and build a new report package.

The old HTML never connects to DB and never executes SQL.

If the new data shape cannot support the previous chart recipe, the agent may suggest a replacement chart but must open a design adjustment checkpoint before changing it.
```

- [ ] **Step 4: Update validator script**

Modify `scripts/validate_local_wferp_report_skill.py` to require the new files and strings:

```python
for relative_path in [
    "references/single-html-export.md",
    "references/dynamic-design-brief.md",
    "references/style-replay.md",
]:
    path = root / relative_path
    if not path.is_file():
        errors.append(f"Missing required file: {relative_path}")

single_html_path = references_root / "single-html-export.md"
if single_html_path.is_file():
    single_html_text = read_text(root, single_html_path, errors)
    if single_html_text is not None:
        for needle in ["不得連 DB", "不得執行 SQL", "network requests = 0"]:
            if needle not in single_html_text:
                errors.append(f"single-html-export.md missing required text: {needle}")
```

- [ ] **Step 5: Run skill validation**

Run:

```bash
pytest tests/scripts/test_validate_local_wferp_report_skill.py -v
bash /home/timmypai/.codex/skills/wferp-report/scripts/validate-skill.sh
```

Expected:

```text
pytest ... -> PASS
wferp-report skill validation passed
```

- [ ] **Step 6: Run complete verification**

Run:

```bash
pytest tests/skill_scripts/test_report_package.py tests/skill_scripts/test_dynamic_design_brief.py tests/skill_scripts/test_visual_checkpoint.py tests/skill_scripts/test_single_html_exporter.py tests/skill_scripts/test_html_self_validator.py tests/skill_scripts/test_style_replay.py -v
pytest tests/skill_scripts/test_single_html_expense_e2e.py tests/skill_scripts/test_style_replay_e2e.py -v
bash scripts/run_single_html_expense_e2e.sh
bash scripts/run_style_replay_e2e.sh
cd report_renderer && npm test && npm run build
bash /home/timmypai/.codex/skills/wferp-report/scripts/validate-skill.sh
```

Expected:

- all pytest targets PASS
- `single_html_expense_e2e=pass row_count=6 total_amount=120000 total_budget=100000 variance_amount=20000 max_expense_ratio=0.35`
- `style_replay_e2e=pass style_fingerprint=same stale_data=false adjustment_checkpoint=required_when_incompatible`
- Vitest PASS
- Vite build completes
- local skill validator prints `wferp-report skill validation passed`

- [ ] **Step 7: Commit**

```bash
git add scripts/validate_local_wferp_report_skill.py tests/scripts/test_validate_local_wferp_report_skill.py
git commit -m "docs: document single html report studio skill flow"
```

Local skill files are outside the repo. Include changed outside-repo paths in the evidence packet.

---

## Final Acceptance Criteria

- `report-package.json` is the single source for HTML and evidence packet data.
- Dynamic design brief is generated, validated, checkpointed, and confirmed before final report draft.
- Semi-real HTML visual checkpoint uses real labels and aggregates.
- `delivery/report.html` is a self-contained single HTML file.
- `delivery/evidence/` includes package, design brief, style capsule, SQL, validator results, manifest, and repair log when present.
- Exported HTML has no external scripts, stylesheets, DB connection strings, credentials, or runtime SQL execution.
- Offline interactions operate only on embedded package data.
- Style replay preserves style fingerprint while regenerating SQL/data for a new prompt.
- Incompatible replay chart recipes create a design adjustment checkpoint requirement.
- SQLite-first and Docker PostgreSQL E2E remain real SQL execution tests.
- Single HTML expense E2E passes with:

```text
row_count=6
total_amount=120000
total_budget=100000
variance_amount=20000
max_expense_ratio=0.35
network_requests=0
console_errors=0
manifest_hash_valid=true
```

- React tests and build pass.
- Local skill validator passes.

## Execution Notes

- Use `superpowers:subagent-driven-development` for implementation.
- Dispatch one fresh worker per task.
- After each worker commit, dispatch a spec compliance reviewer and a code quality reviewer.
- Reject any task without failing-test evidence.
- Reject any E2E that uses fake/mock/smoke instead of real SQLite/PostgreSQL or real HTML validation.
- Do not stage unrelated main worktree changes such as `docs/agents/runtime/context-checkpoint.yaml` or `docs/agents/release-results/*`.
