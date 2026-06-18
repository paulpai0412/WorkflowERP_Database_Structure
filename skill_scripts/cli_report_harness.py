from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from typing import Any

from skill_scripts.excel_intake import build_excel_confirmation_payload, parse_excel_requirement
from skill_scripts.report_catalog import build_report_selection_payload
from skill_scripts.report_catalog import get_report_design_defaults
from skill_scripts.report_catalog import list_report_designs
from skill_scripts.report_harness import ReportHarness
from skill_scripts.report_harness_state import load_run_state
from skill_scripts.report_scaffold import scaffold_report_workspace
from skill_scripts.schema_loader import load_schema_bundle
from skill_scripts.sql_generator import generate_select_sql

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


def _default_scaffold_template_dir() -> Path:
    return Path.home() / ".codex" / "skills" / "wferp-report" / "assets" / "scaffold-template"


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
    parser.add_argument("--design", default="financial-control")
    parser.add_argument("--template-dir", type=Path, default=_default_scaffold_template_dir())
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = scaffold_report_workspace(
            run_dir=Path(args.run_dir),
            template_dir=args.template_dir,
            sections=_sections_for_design(args.design),
            payload={"approved_query_result": {"rows": []}},
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
        raise SystemExit(f"Report run does not exist: {run_dir}")
    with CheckpointCompanionServer.serve(run_dir, host=args.host, port=args.port) as server:
        print(
            f"checkpoint_companion_url={server.base_url}/runs/{run_dir.name}/checkpoints/current",
            flush=True,
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


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if argv and argv[0] == "serve-checkpoint":
        return _serve_checkpoint(argv[1:])
    if argv and argv[0] == "scaffold-report":
        return _scaffold_report(argv[1:])

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
