from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from typing import Any

from skill_scripts.dynamic_design_brief import build_design_brief
from skill_scripts.dynamic_design_brief import validate_design_brief
from skill_scripts.excel_intake import build_excel_confirmation_payload, parse_excel_requirement
from skill_scripts.report_catalog import build_report_selection_payload
from skill_scripts.report_catalog import get_report_design_defaults
from skill_scripts.report_catalog import list_report_designs
from skill_scripts.report_harness import ReportHarness
from skill_scripts.report_harness import ReportHarnessError
from skill_scripts.report_harness_state import load_run_state
from skill_scripts.report_harness_state import write_confirmation
from skill_scripts.report_scaffold import scaffold_report_workspace
from skill_scripts.schema_loader import load_schema_bundle
from skill_scripts.sql_generator import generate_select_sql
from skill_scripts.visual_checkpoint import build_visual_checkpoint_payload
from skill_scripts.visual_checkpoint import render_visual_checkpoint_html

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
        loaded = json.loads(path.read_text(encoding="utf-8"))
    else:
        loaded = json.loads(value)
    if not isinstance(loaded, dict):
        raise ValueError("JSON payload must be an object")
    return loaded


def _load_json_arg_or_empty(value: str | None) -> dict[str, Any]:
    return _load_json_arg(value) if value else {}


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


def _build_sql(prompt: str, mode: str) -> str:
    if mode != "rule":
        # The harness must remain deterministic until LLM orchestration has a user-visible review gate.
        mode = "rule"
    bundle = load_schema_bundle("_Source")
    return generate_select_sql(prompt, bundle)


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
    parser.add_argument("--mode", choices=["rule", "shadow", "llm-first"], default="rule")
    parser.add_argument("--validation", default="")
    args = parser.parse_args(argv)

    try:
        harness = _open_harness(args.run_dir)
        state = harness.state()
        prompt = args.prompt or state.get("prompt", "")
        sql = args.sql or _build_sql(prompt, args.mode)
        validation = _load_json_arg_or_empty(args.validation) or {"status": "pending_user_confirmation"}
        _write_run_json(harness.run_dir, "sql/query.sql.json", {"sql": sql, "validation": validation})
        (harness.run_dir / "sql" / "query.sql").write_text(sql + "\n", encoding="utf-8")
        checkpoint = harness.write_sql_review(sql, validation)
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
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
        state = harness.confirm(args.checkpoint, args.action, selected_options=selected_options)
        write_confirmation(
            harness.run_dir,
            args.checkpoint,
            {
                "action": args.action,
                "comment": args.comment,
                "selectedOptions": selected_options,
            },
        )
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("confirmation_error", str(exc))
    _write_stdout_json(
        {
            "status": "confirmed",
            "checkpoint": args.checkpoint,
            "action": args.action,
            "selectedOptions": selected_options,
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
        brief = _load_json_arg(args.brief)
        package = _load_json_arg(args.package)
        payload = build_visual_checkpoint_payload(brief, package)
        html_text = render_visual_checkpoint_html(payload)
        checkpoint = harness.write_visual_design(payload)
        _write_run_text(harness.run_dir, "visual/visual-checkpoint.html", html_text)
    except (FileNotFoundError, ReportHarnessError, ValueError, json.JSONDecodeError) as exc:
        return _json_error("visual_checkpoint_error", str(exc))
    _write_stdout_json(checkpoint)
    return 0


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


COMMANDS = {
    "create-run": _create_run,
    "write-excel-confirmation": _write_excel_confirmation,
    "write-sql-review": _write_sql_review,
    "confirm": _confirm,
    "write-data-preview": _write_data_preview,
    "write-report-selection": _write_report_selection,
    "write-design-brief": _write_design_brief,
    "write-visual-checkpoint": _write_visual_checkpoint,
    "scaffold-report": _scaffold_report,
    "write-report-draft": _write_report_draft,
    "write-final-review": _write_final_review,
    "can-deliver": _can_deliver,
    "serve-checkpoint": _serve_checkpoint,
}


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if argv and argv[0] in COMMANDS:
        return COMMANDS[argv[0]](argv[1:])

    parser = argparse.ArgumentParser(description="Create and advance WFERP report harness runs.")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--input-file", action="append", type=Path, default=[])
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--mode", choices=["rule", "shadow", "llm-first"], default="rule")
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
        sql = _build_sql(prompt, args.mode)
        harness.write_sql_review(sql, {"status": "pending_user_confirmation"})

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
