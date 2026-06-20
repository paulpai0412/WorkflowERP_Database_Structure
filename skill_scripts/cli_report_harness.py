from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any

from skill_scripts.dynamic_design_brief import build_design_brief
from skill_scripts.dynamic_design_brief import validate_design_brief
from skill_scripts.excel_intake import build_excel_confirmation_payload, parse_excel_requirement
from skill_scripts.html_self_validator import validate_single_html_static
from skill_scripts.llm_workbook_classifier import classify_workbook_with_llm
from skill_scripts.report_gate_checks import evaluate_delivery_artifacts
from skill_scripts.report_gate_checks import scan_run_text_artifacts
from skill_scripts.sqlite_enrichment import run_enrichment
from skill_scripts.sqlite_workspace import SQLiteRunWorkspace
from skill_scripts.report_catalog import build_report_selection_payload
from skill_scripts.report_catalog import get_report_design_defaults
from skill_scripts.report_catalog import list_report_designs
from skill_scripts.report_harness import ReportHarness
from skill_scripts.report_harness import ReportHarnessError
from skill_scripts.report_harness_state import load_run_state
from skill_scripts.report_harness_state import CHECKPOINT_DEFINITIONS
from skill_scripts.report_scaffold import scaffold_report_workspace
from skill_scripts.report_scaffold import validate_generated_report_section
from skill_scripts.schema_loader import load_schema_bundle
from skill_scripts.single_html_exporter import export_single_html_report
from skill_scripts.sql_router import RoutingOptions, route_generate_sql
from skill_scripts.style_replay import detect_replay_adjustments
from skill_scripts.user_step_payload import build_user_step_payload
from skill_scripts.visual_checkpoint import build_visual_checkpoint_payload
from skill_scripts.visual_checkpoint import render_visual_checkpoint_html
from skill_scripts.workbook_lookup_importer import import_lookup_sheet
from skill_scripts.report_scaffold import write_generated_report_section

DEFAULT_REPORT_SECTIONS = [
    "executive-summary",
    "kpi-overview",
    "exception-review",
    "data-table",
    "recommendations",
]

DESIGN_SECTION_DEFAULTS = {
    "financial-control": DEFAULT_REPORT_SECTIONS,
}


def _write_stdout_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _write_stderr_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2), file=sys.stderr)


def _json_error(code: str, message: str) -> int:
    _write_stderr_json({"status": "error", "code": code, "message": message})
    return 2


def _default_scaffold_template_dir() -> Path:
    return Path.home() / ".codex" / "skills" / "wferp-report" / "assets" / "scaffold-template"


def _load_json_arg(value: str) -> dict[str, Any]:
    path = Path(value)
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    else:
        loaded = json.loads(value)
    if not isinstance(loaded, dict):
        raise ValueError("JSON payload must be an object")
    return loaded


def _load_json_list_arg(value: str) -> list[dict[str, Any]]:
    path = Path(value)
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    else:
        loaded = json.loads(value)
    if not isinstance(loaded, list) or not all(isinstance(item, dict) for item in loaded):
        raise ValueError("JSON payload must be a list of objects")
    return loaded


def _load_json_arg_or_empty(value: str | None) -> dict[str, Any]:
    return _load_json_arg(value) if value else {}


def _payload_or_checkpoint_payload(value: dict[str, Any]) -> dict[str, Any]:
    payload = value.get("payload")
    if isinstance(payload, dict) and "checkpoint" in value:
        return payload
    return value


def _load_text_arg(*, inline: str | None, file_path: str | None) -> str:
    if bool(inline) == bool(file_path):
        raise ValueError("Provide exactly one of --code or --code-file")
    if file_path:
        return Path(file_path).read_text(encoding="utf-8")
    return inline or ""


def _write_run_json(run_dir: Path, relative_path: str, payload: dict[str, Any]) -> None:
    path = run_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_run_text(run_dir: Path, relative_path: str, text: str) -> None:
    path = run_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _slugify_section(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() and char.isascii() else "-" for char in value)
    return "-".join(part for part in slug.split("-") if part)


def _sections_for_design(design: str) -> list[str]:
    defaults = get_report_design_defaults(design)
    sections = [str(section) for section in defaults["sections"] if str(section).strip()]
    if sections:
        return sections

    if design in DESIGN_SECTION_DEFAULTS:
        return list(DESIGN_SECTION_DEFAULTS[design])

    sections: list[str] = []
    for profile in list_report_designs():
        if profile["id"] != design:
            continue
        for section in profile.get("required_sections", []):
            slug = _slugify_section(str(section))
            if slug:
                sections.append(slug)
        break

    for fallback in DEFAULT_REPORT_SECTIONS:
        if fallback not in sections:
            sections.append(fallback)
        if len(sections) >= 5:
            break
    return sections[:5]


def _scaffold_report(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Scaffold a per-run WFERP React report workspace.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--design", default="")
    parser.add_argument("--template-dir", type=Path, default=_default_scaffold_template_dir())
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    try:
        state = load_run_state(run_dir)
    except FileNotFoundError:
        state = {}
    design = args.design or state.get("report_design") or "financial-control"
    payload = {
        "run": state,
        "approved_query_result": state.get("execution_result_summary") or {"rows": []},
    }
    try:
        result = scaffold_report_workspace(
            run_dir=run_dir,
            template_dir=args.template_dir,
            sections=_sections_for_design(design),
            payload=payload,
            force=args.force,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        _write_stderr_json(
            {
                "status": "error",
                "code": "scaffold_error",
                "message": str(exc),
            }
        )
        return 2
    _write_stdout_json(
        {
            "status": "scaffolded",
            "section_count": result["section_count"],
            "run_dir": result["run_dir"],
            "design": design,
        }
    )
    return 0


def _serve_checkpoint(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Serve WFERP checkpoint companion confirmations.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args(argv)

    from skill_scripts.checkpoint_companion import CheckpointCompanionServer

    run_dir = Path(args.run_dir)
    if not (run_dir / "state.json").exists():
        return _json_error("run_not_found", f"Report run does not exist: {run_dir}")
    with CheckpointCompanionServer.serve(run_dir, host=args.host, port=args.port) as server:
        _write_stdout_json(
            {
                "status": "serving",
                "url": f"{server.base_url}/runs/{run_dir.name}/checkpoints/current",
            }
        )
        try:
            server.thread.join()
        except KeyboardInterrupt:
            return 0
    return 0


def _confirmation_path(run_dir: Path, checkpoint: str) -> Path:
    definition = CHECKPOINT_DEFINITIONS[checkpoint]
    filename = definition["file"].replace(".json", ".confirmation.json")
    return run_dir / "checkpoints" / filename


def _read_confirmation_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Confirmation payload must be an object")
    return payload


def _wait_confirmation(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Wait until a checkpoint confirmation is written.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=0.5)
    parser.add_argument("--allow-existing", action="store_true")
    parser.add_argument("--fresh-only", action="store_true")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    if not (run_dir / "state.json").exists():
        return _json_error("run_not_found", f"Report run does not exist: {run_dir}")
    if args.checkpoint not in CHECKPOINT_DEFINITIONS:
        return _json_error("unknown_checkpoint", f"Unknown checkpoint: {args.checkpoint}")
    if args.timeout_seconds < 0:
        return _json_error("invalid_timeout", "--timeout-seconds must be >= 0")
    if args.poll_interval_seconds <= 0:
        return _json_error("invalid_poll_interval", "--poll-interval-seconds must be > 0")

    path = _confirmation_path(run_dir, args.checkpoint)
    started_wall_time = time.time()
    deadline = time.monotonic() + args.timeout_seconds

    while True:
        if path.exists():
            stat = path.stat()
            if args.allow_existing or not args.fresh_only or stat.st_mtime >= started_wall_time:
                try:
                    confirmation = _read_confirmation_payload(path)
                except (json.JSONDecodeError, ValueError) as exc:
                    return _json_error("confirmation_read_error", str(exc))
                _write_stdout_json(
                    {
                        "status": "confirmed",
                        "checkpoint": args.checkpoint,
                        "action": confirmation.get("action", ""),
                        "comment": confirmation.get("comment", ""),
                        "selectedOptions": confirmation.get("selectedOptions", {}),
                        "run_id": confirmation.get("run_id", ""),
                        "checkpoint_id": confirmation.get("checkpoint_id", args.checkpoint),
                        "payload_hash": confirmation.get("payload_hash", ""),
                        "confirmation_id": confirmation.get("confirmation_id", ""),
                        "created_at": confirmation.get("created_at", ""),
                        "confirmation_file": str(path),
                    }
                )
                return 0

        if time.monotonic() >= deadline:
            _write_stderr_json(
                {
                    "status": "error",
                    "code": "confirmation_timeout",
                    "message": f"Timed out waiting for checkpoint confirmation: {args.checkpoint}",
                    "checkpoint": args.checkpoint,
                    "confirmation_file": str(path),
                }
            )
            return 2
        time.sleep(min(args.poll_interval_seconds, max(0.0, deadline - time.monotonic())))


def _ensure_harness(args: argparse.Namespace) -> ReportHarness:
    run_dir = Path(args.run_dir)
    if (run_dir / "state.json").exists():
        return ReportHarness(run_dir)

    if not args.prompt:
        raise SystemExit("--prompt is required when creating a new report run")
    run_id = run_dir.name
    run_root = run_dir.parent if str(run_dir.parent) else Path(".")
    return ReportHarness.create(
        run_root,
        run_id=run_id,
        prompt=args.prompt,
        input_files=[str(path) for path in args.input_file],
    )


def _open_harness(run_dir: str | Path) -> ReportHarness:
    path = Path(run_dir)
    if not (path / "state.json").exists():
        raise ReportHarnessError(f"Report run does not exist: {path}")
    return ReportHarness(path)


def _quote_sqlite_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _workspace_from_manifest(run_dir: Path, manifest_path: str | Path) -> SQLiteRunWorkspace:
    path = Path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"SQLite manifest does not exist: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return SQLiteRunWorkspace(
        run_dir=run_dir,
        sqlite_db_path=Path(manifest["sqlite_db_path"]),
        run_prefix=str(manifest["run_prefix"]),
        raw_table=str(manifest["raw_table"]),
        enriched_table=str(manifest["enriched_table"]),
        manifest_path=path,
    )


def _workspace_from_state(harness: ReportHarness) -> SQLiteRunWorkspace:
    manifest_path = harness.state().get("sqlite_manifest_path")
    if not manifest_path:
        raise ReportHarnessError("SQLite workspace has not been initialized")
    return _workspace_from_manifest(harness.run_dir, manifest_path)


def _sqlite_table_preview(workspace: SQLiteRunWorkspace, table_name: str, *, limit: int = 25) -> dict[str, Any]:
    quoted_table = _quote_sqlite_identifier(table_name)
    with sqlite3.connect(workspace.sqlite_db_path) as conn:
        conn.row_factory = sqlite3.Row
        columns = [row[1] for row in conn.execute(f"PRAGMA table_info({quoted_table})")]
        row_count = conn.execute(f"SELECT COUNT(*) FROM {quoted_table}").fetchone()[0]
        rows = [
            dict(row)
            for row in conn.execute(
                f"SELECT * FROM {quoted_table} LIMIT ?",
                (limit,),
            ).fetchall()
        ]
    return {
        "sqlite_db_path": str(workspace.sqlite_db_path),
        "table_name": table_name,
        "row_count": row_count,
        "columns": columns,
        "sample_rows": rows,
    }


def _parse_excel_inputs(harness: ReportHarness, input_files: list[Path]) -> dict[str, Any] | None:
    excel_files = [path for path in input_files if path.suffix.lower() == ".xlsx"]
    if not excel_files:
        return None
    requirement = parse_excel_requirement(excel_files[0])
    payload = build_excel_confirmation_payload(requirement)
    requirement_state = requirement.to_dict()
    requirement_state.setdefault(
        "database_fields",
        [asdict(field) for field in requirement.database_fields],
    )
    harness.update_state(excel_requirement=requirement_state)
    return payload


def _build_prompt_sql(
    prompt: str,
    *,
    source_dir: str | Path = "_Source",
    llm_provider: str = "codex",
    llm_model: str = "none",
    llm_timeout_seconds: float = 30.0,
    llm_min_confidence: float = 0.6,
    llm_repair_attempts: int = 2,
) -> tuple[str, dict[str, Any]]:
    bundle = load_schema_bundle(str(source_dir))
    return route_generate_sql(
        prompt,
        bundle,
        RoutingOptions(
            mode="llm-first",
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_timeout_sec=llm_timeout_seconds,
            min_confidence=llm_min_confidence,
            llm_repair_attempts=llm_repair_attempts,
        ),
    )


def _guard_execution(args: argparse.Namespace, harness: ReportHarness) -> bool:
    if not args.validate_execution:
        return False
    if not args.confirm_sql:
        print("SQL 尚未確認，未執行資料庫查詢。")
        return False
    db_env = str(args.db_env or os.getenv("DB_ENV", "")).strip().lower()
    if db_env != "test" and not args.allow_non_test_db_execution:
        print(
            "ERROR: non-test DB execution requires --allow-non-test-db-execution",
            file=sys.stderr,
        )
        raise SystemExit(2)
    state = harness.state()
    if not state.get("sql_candidate") or "sql_review" not in {
        item["checkpoint"] for item in state.get("checkpoints", [])
    }:
        print("ERROR: --confirm-sql requires an existing reviewed SQL checkpoint", file=sys.stderr)
        raise SystemExit(2)
    harness.confirm("sql_review", "同意查詢")
    harness.update_state(
        execution_result_summary={
            "status": "not_executed_by_harness",
            "reason": "DB execution is delegated to the governed SQL validation path.",
        }
    )
    print("SQL 已確認；資料庫執行需由 governed validation path 產生 evidence。")
    return True


def _create_run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Create a WFERP report harness run.")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--input-file", action="append", type=Path, default=[])
    args = parser.parse_args(argv)

    try:
        harness = ReportHarness.create(
            args.run_root,
            run_id=args.run_id,
            prompt=args.prompt,
            input_files=[str(path) for path in args.input_file],
        )
    except FileExistsError as exc:
        return _json_error("run_exists", str(exc))
    _write_stdout_json({"status": "created", "run_dir": str(harness.run_dir), "state": harness.state()})
    return 0


def _write_excel_confirmation(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write the Excel field/formula confirmation checkpoint.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--payload", default="")
    parser.add_argument("--input-file", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        if args.input_file:
            payload = _parse_excel_inputs(harness, [args.input_file])
            if payload is None:
                return _json_error("excel_required", f"Not an Excel file: {args.input_file}")
        else:
            payload = _load_json_arg_or_empty(args.payload)
        checkpoint = harness.write_excel_confirmation(payload)
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("excel_confirmation_error", str(exc))
    _write_stdout_json(checkpoint)
    return 0


def _write_sql_review(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write the SQL review checkpoint.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--sql", default="")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--validation", default="")
    parser.add_argument("--source-dir", default="_Source")
    parser.add_argument("--llm-provider", default=os.getenv("LLM_PROVIDER", "codex"))
    parser.add_argument("--llm-model", default=os.getenv("LLM_MODEL", "none"))
    parser.add_argument("--llm-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--llm-min-confidence", type=float, default=0.6)
    parser.add_argument("--llm-repair-attempts", type=int, default=2)
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        state = harness.state()
        prompt = args.prompt or state.get("prompt", "")
        route_meta: dict[str, Any] = {"route": "manual_sql", "reason": "USER_PROVIDED_SQL"}
        if args.sql:
            sql = args.sql
        else:
            sql, route_meta = _build_prompt_sql(
                prompt,
                source_dir=args.source_dir,
                llm_provider=args.llm_provider,
                llm_model=args.llm_model,
                llm_timeout_seconds=args.llm_timeout_seconds,
                llm_min_confidence=args.llm_min_confidence,
                llm_repair_attempts=args.llm_repair_attempts,
            )
        validation = _load_json_arg_or_empty(args.validation) or {
            "status": "pending_user_confirmation",
            "route": route_meta.get("route", ""),
            "reason": route_meta.get("reason", ""),
            "llm_provider": args.llm_provider if not args.sql else "",
            "llm_model": args.llm_model if not args.sql else "",
        }
        if not args.sql and "candidate_sql" in route_meta:
            validation["candidate_sql"] = route_meta["candidate_sql"]
        _write_run_json(harness.run_dir, "sql/query.sql.json", {"sql": sql, "validation": validation})
        (harness.run_dir / "sql" / "query.sql").write_text(sql + "\n", encoding="utf-8")
        checkpoint = harness.write_sql_review(sql, validation)
    except (FileNotFoundError, ReportHarnessError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("sql_review_error", str(exc))
    _write_stdout_json(checkpoint)
    return 0


def _parse_selected_option_values(values: list[str]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"selected option must use key=value: {value}")
        key, raw_value = value.split("=", 1)
        lowered = raw_value.lower()
        if lowered in {"true", "false"}:
            selected[key] = lowered == "true"
        else:
            selected[key] = raw_value
    return selected


def _parse_value_columns(values: list[str]) -> dict[str, str]:
    columns: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"value column must use output_name=ExcelColumn: {value}")
        name, column = value.split("=", 1)
        name = name.strip()
        column = column.strip()
        if not name or not column:
            raise ValueError(f"value column must include both name and column: {value}")
        columns[name] = column
    if not columns:
        raise ValueError("At least one --value-column is required")
    return columns


def _confirm(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Confirm a checkpoint and persist selected options.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--comment", default="")
    parser.add_argument("--selected-options", default="")
    parser.add_argument("--selected-option", action="append", default=[])
    parser.add_argument("--accepted-residual-risk", action="append", default=[])
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        selected_options = _load_json_arg_or_empty(args.selected_options)
        selected_options.update(_parse_selected_option_values(args.selected_option))
        if args.accepted_residual_risk:
            selected_options["acceptedResidualRisks"] = list(args.accepted_residual_risk)
        state = harness.confirm(args.checkpoint, args.action, selected_options=selected_options, comment=args.comment)
        confirmation_path = _confirmation_path(harness.run_dir, args.checkpoint)
        confirmation = _read_confirmation_payload(confirmation_path)
        if args.comment:
            confirmation["comment"] = args.comment
            confirmation_path.write_text(
                json.dumps(confirmation, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("confirmation_error", str(exc))
    _write_stdout_json(
        {
            "status": "confirmed",
            "checkpoint": args.checkpoint,
            "action": args.action,
            "selectedOptions": selected_options,
            "confirmation": confirmation,
            "state": state,
        }
    )
    return 0


def _write_data_preview(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write the data preview checkpoint after SQL confirmation.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--payload", required=True)
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        payload = _load_json_arg(args.payload)
        checkpoint = harness.write_data_preview(payload)
        _write_run_json(harness.run_dir, "data/execution-result.json", payload)
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("data_preview_error", str(exc))
    _write_stdout_json(checkpoint)
    return 0


def _classify_workbook(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Classify workbook fields for DB SQL and SQLite enrichment.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--primary-sheet", default="")
    parser.add_argument(
        "--classification-payload",
        default="",
        help="JSON object or path produced by the authenticated current Codex session; skips external LLM CLI.",
    )
    parser.add_argument("--source-dir", default="_Source")
    parser.add_argument("--llm-provider", default=os.getenv("LLM_PROVIDER", "codex"))
    parser.add_argument("--llm-model", default=os.getenv("LLM_MODEL", "default"))
    parser.add_argument("--llm-timeout-seconds", type=float, default=60.0)
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        if args.classification_payload:
            payload = _load_json_arg(args.classification_payload)
        else:
            payload = classify_workbook_with_llm(
                args.input_file,
                source_dir=args.source_dir,
                primary_sheet=args.primary_sheet,
                user_prompt=str(harness.state().get("prompt") or ""),
                llm_provider=args.llm_provider,
                llm_model=args.llm_model,
                timeout_sec=args.llm_timeout_seconds,
            )
        _write_run_json(harness.run_dir, "data/column-classification.json", payload)
        checkpoint = harness.write_field_formula_classification(payload)
    except (FileNotFoundError, ReportHarnessError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        return _json_error("classification_error", str(exc))
    _write_stdout_json(checkpoint)
    return 0


def _init_sqlite_workspace(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Initialize a run-scoped SQLite workspace.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        state = harness.state()
        workspace = SQLiteRunWorkspace.create(harness.run_dir, run_id=str(state["run_id"]))
        manifest = workspace.manifest()
        harness.update_state(sqlite_manifest=manifest, sqlite_manifest_path=str(workspace.manifest_path))
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("sqlite_workspace_error", str(exc))
    _write_stdout_json(
        {
            "status": "initialized",
            "sqlite_manifest_path": str(workspace.manifest_path),
            "manifest": manifest,
        }
    )
    return 0


def _import_lookups(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Import a workbook lookup sheet into the run SQLite workspace.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--sheet-name", required=True)
    parser.add_argument("--logical-name", required=True)
    parser.add_argument("--key-column", required=True)
    parser.add_argument("--value-column", action="append", default=[])
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        workspace = _workspace_from_state(harness)
        result = import_lookup_sheet(
            args.input_file,
            workspace,
            sheet_name=args.sheet_name,
            logical_name=args.logical_name,
            key_column=args.key_column,
            value_columns=_parse_value_columns(args.value_column),
        )
        manifest = workspace.manifest()
        harness.update_state(sqlite_manifest=manifest, sqlite_manifest_path=str(workspace.manifest_path))
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("lookup_import_error", str(exc))
    _write_stdout_json({**result, "manifest": manifest})
    return 0


def _write_raw_table(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write formal DB raw rows into the SQLite raw table.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--rows", required=True)
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        workspace = _workspace_from_state(harness)
        rows = _load_json_list_arg(args.rows)
        workspace.write_raw_rows(rows)
        manifest = workspace.manifest()
        harness.update_state(sqlite_manifest=manifest, sqlite_manifest_path=str(workspace.manifest_path))
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("raw_table_error", str(exc))
    _write_stdout_json(
        {
            "status": "written",
            "table_name": workspace.raw_table,
            "row_count": manifest["raw_row_count"],
            "manifest": manifest,
        }
    )
    return 0


def _write_raw_preview(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write a checkpoint preview of the SQLite raw table.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        workspace = _workspace_from_state(harness)
        payload = _sqlite_table_preview(workspace, workspace.raw_table, limit=args.limit)
        checkpoint = harness.write_raw_data_preview(payload)
    except (FileNotFoundError, ReportHarnessError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        return _json_error("raw_preview_error", str(exc))
    _write_stdout_json(checkpoint)
    return 0


def _run_sqlite_enrichment(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run SQLite enrichment from JSON column payloads.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--computed-columns", default="[]")
    parser.add_argument("--lookup-columns", default="[]")
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        workspace = _workspace_from_state(harness)
        result = run_enrichment(
            workspace,
            computed_columns=_load_json_list_arg(args.computed_columns),
            lookup_columns=_load_json_list_arg(args.lookup_columns),
        )
        manifest = workspace.manifest()
        harness.update_state(sqlite_manifest=manifest, sqlite_manifest_path=str(workspace.manifest_path))
    except (FileNotFoundError, ReportHarnessError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        return _json_error("sqlite_enrichment_error", str(exc))
    _write_stdout_json({"status": "enriched", "result": result, "manifest": manifest})
    return 0


def _write_enriched_preview(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write a checkpoint preview of the enriched SQLite table.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        workspace = _workspace_from_state(harness)
        payload = _sqlite_table_preview(workspace, workspace.enriched_table, limit=args.limit)
        checkpoint = harness.write_enriched_data_preview(payload)
    except (FileNotFoundError, ReportHarnessError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        return _json_error("enriched_preview_error", str(exc))
    _write_stdout_json(checkpoint)
    return 0


def _write_sqlite_retention(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write SQLite retention checkpoint payload.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--decision", default="keep", choices=["keep", "delete", "export_then_delete"])
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        workspace = _workspace_from_state(harness)
        manifest = workspace.manifest()
        lookup_counts = manifest.get("lookup_row_counts", {})
        tables = [
            {"table_name": manifest["raw_table"], "row_count": manifest.get("raw_row_count", 0)},
            {"table_name": manifest["enriched_table"], "row_count": manifest.get("enriched_row_count", 0)},
        ]
        if isinstance(lookup_counts, dict):
            tables.extend(
                {"table_name": str(table), "row_count": count}
                for table, count in lookup_counts.items()
            )
        payload = {
            "manifest_path": str(workspace.manifest_path),
            "sqlite_db_path": str(workspace.sqlite_db_path),
            "tables": tables,
            "default_action": "保留本地資料",
            "retention_decision": args.decision,
            "cleanup_status": manifest.get("cleanup_status", "active"),
        }
        checkpoint = harness.write_sqlite_retention(payload)
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("sqlite_retention_error", str(exc))
    _write_stdout_json(checkpoint)
    return 0


def _cleanup_sqlite_run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Drop only SQLite tables listed in the run manifest.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        workspace = _workspace_from_state(harness)
        workspace.cleanup_run_tables()
        manifest = workspace.manifest()
        harness.update_state(sqlite_manifest=manifest, sqlite_manifest_path=str(workspace.manifest_path))
    except (FileNotFoundError, ReportHarnessError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        return _json_error("sqlite_cleanup_error", str(exc))
    _write_stdout_json({"status": "cleaned", "manifest": manifest})
    return 0


def _write_report_selection(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write the report selection checkpoint.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--payload", default="")
    parser.add_argument("--report-type", default="")
    parser.add_argument("--report-design", default="")
    parser.add_argument("--include-chart", action="store_true")
    parser.add_argument("--include-table", action="store_true")
    parser.add_argument("--include-analysis", action="store_true")
    parser.add_argument("--include-recommendations", action="store_true")
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        payload = _load_json_arg_or_empty(args.payload) or build_report_selection_payload()
        if args.report_type:
            payload["selected_report_type"] = args.report_type
        if args.report_design:
            get_report_design_defaults(args.report_design)
            payload["selected_report_design"] = args.report_design
        payload["selected_options"] = {
            **payload.get("selected_options", {}),
            "include_chart": args.include_chart,
            "include_table": args.include_table,
            "include_analysis": args.include_analysis,
            "include_recommendations": args.include_recommendations,
        }
        checkpoint = harness.write_report_selection(payload)
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("report_selection_error", str(exc))
    _write_stdout_json(checkpoint)
    return 0


def _write_design_brief(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write the dynamic design brief checkpoint.")
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


def _write_visual_checkpoint(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write the semi-real visual design checkpoint.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--brief", required=True)
    parser.add_argument("--package", required=True)
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        brief = _payload_or_checkpoint_payload(_load_json_arg(args.brief))
        package = _payload_or_checkpoint_payload(_load_json_arg(args.package))
        payload = build_visual_checkpoint_payload(brief, package)
        html_text = render_visual_checkpoint_html(payload)
        checkpoint = harness.write_visual_design(payload)
        _write_run_text(harness.run_dir, "visual/visual-checkpoint.html", html_text)
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("visual_checkpoint_error", str(exc))
    _write_stdout_json(checkpoint)
    return 0


def _export_single_html(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Export a self-contained WFERP single HTML report.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--brief", required=True)
    parser.add_argument("--output-root", default="")
    args = parser.parse_args(argv)

    try:
        package = _payload_or_checkpoint_payload(_load_json_arg(args.package))
        brief = _payload_or_checkpoint_payload(_load_json_arg(args.brief))
        output_root = Path(args.output_root) if args.output_root else Path(args.run_dir)
        result = export_single_html_report(output_root, package, brief)
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        return _json_error("single_html_export_error", str(exc))
    if result.get("status") == "error":
        errors = result.get("errors", [])
        message = ", ".join(str(error) for error in errors)
        return _json_error("single_html_export_error", message)
    _write_stdout_json(result)
    return 0


def _validate_single_html(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate exported single HTML report.")
    parser.add_argument("--html", required=True)
    args = parser.parse_args(argv)

    try:
        result = validate_single_html_static(args.html)
    except FileNotFoundError:
        return _json_error("single_html_validation_error", f"HTML file not found: {args.html}")
    except OSError as exc:
        return _json_error("single_html_validation_error", str(exc))
    _write_stdout_json({"status": "validated", **result})
    return 0 if result["valid"] else 2


def _inspect_style_replay(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Inspect whether a style capsule can replay against new columns.")
    parser.add_argument("--capsule", required=True)
    parser.add_argument("--columns", required=True)
    args = parser.parse_args(argv)

    try:
        capsule = _load_json_arg(args.capsule)
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        return _json_error("style_replay_error", str(exc))
    columns = [part.strip() for part in args.columns.split(",") if part.strip()]
    result = detect_replay_adjustments(capsule, new_columns=columns)
    _write_stdout_json({"status": "checked", **result})
    return 2 if result["requires_checkpoint"] else 0


def _write_report_draft(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write the report draft checkpoint after report selection.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--payload", required=True)
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        payload = _load_json_arg(args.payload)
        checkpoint = harness.write_report_draft(payload)
        _write_run_json(harness.run_dir, "reports/report-draft.json", payload)
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("report_draft_error", str(exc))
    _write_stdout_json(checkpoint)
    return 0


def _generate_report_section(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write LLM-generated TSX for one report section.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--section-id", required=True)
    parser.add_argument("--component-name", required=True)
    parser.add_argument("--code", default=None)
    parser.add_argument("--code-file", default=None)
    args = parser.parse_args(argv)

    try:
        code = _load_text_arg(inline=args.code, file_path=args.code_file)
        result = write_generated_report_section(
            run_dir=Path(args.run_dir),
            section_id=args.section_id,
            component_name=args.component_name,
            code=code,
            mode="generate",
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("report_section_error", str(exc))
    _write_stdout_json(result)
    return 0


def _repair_report_section(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Repair one generated report section with replacement TSX.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--section-id", required=True)
    parser.add_argument("--component-name", required=True)
    parser.add_argument("--code", default=None)
    parser.add_argument("--code-file", default=None)
    args = parser.parse_args(argv)

    try:
        code = _load_text_arg(inline=args.code, file_path=args.code_file)
        result = write_generated_report_section(
            run_dir=Path(args.run_dir),
            section_id=args.section_id,
            component_name=args.component_name,
            code=code,
            mode="repair",
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("report_section_error", str(exc))
    _write_stdout_json(result)
    return 0


def _validate_report_section(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate one generated report section and scaffold linkage.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--section-id", required=True)
    parser.add_argument("--component-name", default=None)
    args = parser.parse_args(argv)

    try:
        result = validate_generated_report_section(
            run_dir=Path(args.run_dir),
            section_id=args.section_id,
            component_name=args.component_name,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("report_section_validation_error", str(exc))
    _write_stdout_json(result)
    return 0


def _write_final_review(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write the final review checkpoint with validator evidence.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--payload", required=True)
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        payload = _load_json_arg(args.payload)
        _write_run_json(harness.run_dir, "review/final-review.json", payload)
        checkpoint = harness.write_final_review(payload)
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("final_review_error", str(exc))
    _write_stdout_json(checkpoint)
    return 0


def _can_deliver(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Evaluate final delivery gate.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        result = harness.can_deliver()
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("delivery_gate_error", str(exc))
    _write_stdout_json({"status": "ok", **result})
    return 0 if result.get("allowed") else 2


def _check_delivery_artifacts(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Evaluate final HTML/manifest/validator artifacts.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--required-validator",
        action="append",
        default=[],
        help="Validator role that must have JSON evidence with no required fixes. Repeatable.",
    )
    args = parser.parse_args(argv)

    result = evaluate_delivery_artifacts(
        Path(args.run_dir),
        required_validators=[role for role in args.required_validator if role],
    )
    _write_stdout_json({"status": "ok", **result})
    return 0 if result["allowed"] else 2


def _check_run_text_artifacts(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Scan current run artifacts for UTF-8 readability issues.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)

    result = scan_run_text_artifacts(Path(args.run_dir))
    _write_stdout_json({"status": "ok", **result})
    return 0 if result["valid"] else 2


def _write_user_step_preview(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Write a 4-step Visual Companion payload.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--step", required=True, type=int, choices=[1, 2, 3, 4])
    args = parser.parse_args(argv)

    try:
        run_dir = Path(args.run_dir)
        payload = build_user_step_payload(run_dir, args.step)
        _write_run_json(run_dir, f"checkpoints/user_step_{args.step}.json", payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("user_step_preview_error", str(exc))
    _write_stdout_json(payload)
    return 0


def _export_excel_workbook(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Export a real XLSX workbook and record harness evidence.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--payload", required=True)
    parser.add_argument("--output", default="report/delivery/report.xlsx")
    args = parser.parse_args(argv)

    try:
        from skill_scripts.excel_workbook_exporter import export_workbook

        harness = _open_harness(args.run_dir)
        payload = _payload_or_checkpoint_payload(_load_json_arg(args.payload))
        output_path = harness.run_dir / args.output
        result = export_workbook(
            payload,
            output_path,
            evidence_path=harness.run_dir / "review" / "excel-workbook-evidence.json",
        )
        harness.update_state(final_xlsx_path=result["workbook_path"], excel_workbook_evidence=result)
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError, OSError, RuntimeError) as exc:
        return _json_error("excel_workbook_export_error", str(exc))
    _write_stdout_json(result)
    return 0


COMMANDS = {
    "create-run": _create_run,
    "write-excel-confirmation": _write_excel_confirmation,
    "write-sql-review": _write_sql_review,
    "classify-workbook": _classify_workbook,
    "init-sqlite-workspace": _init_sqlite_workspace,
    "import-lookups": _import_lookups,
    "write-raw-table": _write_raw_table,
    "write-raw-preview": _write_raw_preview,
    "run-sqlite-enrichment": _run_sqlite_enrichment,
    "write-enriched-preview": _write_enriched_preview,
    "write-sqlite-retention": _write_sqlite_retention,
    "cleanup-sqlite-run": _cleanup_sqlite_run,
    "confirm": _confirm,
    "write-data-preview": _write_data_preview,
    "write-report-selection": _write_report_selection,
    "write-design-brief": _write_design_brief,
    "write-visual-checkpoint": _write_visual_checkpoint,
    "export-single-html": _export_single_html,
    "validate-single-html": _validate_single_html,
    "inspect-style-replay": _inspect_style_replay,
    "scaffold-report": _scaffold_report,
    "generate-report-section": _generate_report_section,
    "repair-report-section": _repair_report_section,
    "validate-report-section": _validate_report_section,
    "write-report-draft": _write_report_draft,
    "write-final-review": _write_final_review,
    "can-deliver": _can_deliver,
    "check-delivery-artifacts": _check_delivery_artifacts,
    "check-run-text-artifacts": _check_run_text_artifacts,
    "write-user-step-preview": _write_user_step_preview,
    "export-excel-workbook": _export_excel_workbook,
    "serve-checkpoint": _serve_checkpoint,
    "wait-confirmation": _wait_confirmation,
}


def _print_main_help() -> None:
    command_lines = "\n".join(f"  {name}" for name in sorted(COMMANDS))
    print(
        "usage: python3 -m skill_scripts.cli_report_harness <command> [options]\n"
        "       python3 -m skill_scripts.cli_report_harness --run-dir RUN_DIR [legacy options]\n\n"
        "Create and advance WFERP report harness runs.\n\n"
        "Primary subcommands:\n"
        f"{command_lines}\n\n"
        "Use '<command> --help' for command-specific options.\n\n"
        "Legacy compatibility options are still accepted for older scripts, but the\n"
        "wferp-report skill flow should use subcommands such as create-run,\n"
        "classify-workbook, write-sql-review, serve-checkpoint, wait-confirmation,\n"
        "write-raw-preview, write-enriched-preview, and export-single-html.\n"
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if argv in (["--help"], ["-h"]):
        _print_main_help()
        return 0
    if argv and argv[0] in COMMANDS:
        return COMMANDS[argv[0]](argv[1:])

    parser = argparse.ArgumentParser(description="Create and advance WFERP report harness runs.")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--input-file", action="append", type=Path, default=[])
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--source-dir", default="_Source")
    parser.add_argument("--llm-provider", default=os.getenv("LLM_PROVIDER", "codex"))
    parser.add_argument("--llm-model", default=os.getenv("LLM_MODEL", "none"))
    parser.add_argument("--llm-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--llm-min-confidence", type=float, default=0.6)
    parser.add_argument("--llm-repair-attempts", type=int, default=2)
    parser.add_argument("--checkpoint", choices=["excel", "sql", "report-selection"], default="")
    parser.add_argument("--confirm-sql", action="store_true")
    parser.add_argument("--validate-execution", action="store_true")
    parser.add_argument("--allow-non-test-db-execution", action="store_true")
    parser.add_argument("--db-env", default=None)
    parser.add_argument("--report-type", default="")
    parser.add_argument("--report-design", default="")
    parser.add_argument("--include-chart", action="store_true")
    parser.add_argument("--include-table", action="store_true")
    parser.add_argument("--include-analysis", action="store_true")
    parser.add_argument("--include-recommendations", action="store_true")
    args = parser.parse_args(argv)

    harness = _ensure_harness(args)
    state = harness.state()
    prompt = args.prompt or state.get("prompt", "")

    excel_payload = _parse_excel_inputs(harness, args.input_file)
    if excel_payload is not None and args.checkpoint in {"", "excel"}:
        harness.write_excel_confirmation(excel_payload)

    if args.checkpoint == "sql":
        try:
            sql, route_meta = _build_prompt_sql(
                prompt,
                source_dir=args.source_dir,
                llm_provider=args.llm_provider,
                llm_model=args.llm_model,
                llm_timeout_seconds=args.llm_timeout_seconds,
                llm_min_confidence=args.llm_min_confidence,
                llm_repair_attempts=args.llm_repair_attempts,
            )
        except (RuntimeError, ValueError) as exc:
            _write_stderr_json({"status": "error", "code": "sql_review_error", "message": str(exc)})
            return 2
        harness.write_sql_review(
            sql,
            {
                "status": "pending_user_confirmation",
                "route": route_meta.get("route", ""),
                "reason": route_meta.get("reason", ""),
                "llm_provider": args.llm_provider,
                "llm_model": args.llm_model,
            },
        )

    if args.checkpoint == "report-selection" or args.report_type or args.report_design:
        payload = build_report_selection_payload()
        if args.report_type:
            payload["selected_report_type"] = args.report_type
        if args.report_design:
            try:
                get_report_design_defaults(args.report_design)
            except ValueError as exc:
                _write_stderr_json(
                    {
                        "status": "error",
                        "code": "unknown_report_design",
                        "message": str(exc),
                    }
                )
                return 2
            payload["selected_report_design"] = args.report_design
        payload["selected_options"] = {
            "include_chart": args.include_chart,
            "include_table": args.include_table,
            "include_analysis": args.include_analysis,
            "include_recommendations": args.include_recommendations,
        }
        harness.write_report_selection(payload)

    _guard_execution(args, harness)
    _write_stdout_json({"run_dir": str(harness.run_dir), "state": load_run_state(harness.run_dir)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
