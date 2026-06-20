from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from skill_scripts.report_scaffold import (
    scaffold_report_workspace,
    validate_report_protocol,
    write_generated_report_section,
)


def create_minimal_template(template_dir: Path) -> None:
    (template_dir / "report" / "sections").mkdir(parents=True)
    (template_dir / "report" / "raw-blocks").mkdir()
    (template_dir / "report" / "components").mkdir()
    (template_dir / "report" / "payload").mkdir()
    (template_dir / "package.json").write_text(
        json.dumps({"private": True, "type": "module"}),
        encoding="utf-8",
    )
    (template_dir / "index.html").write_text(
        '<div id="root"></div><script type="module" src="/report/Report.tsx"></script>',
        encoding="utf-8",
    )
    (template_dir / "report" / "Report.tsx").write_text(
        'export default function Report() { return <main data-testid="report" />; }\n',
        encoding="utf-8",
    )


def test_scaffold_creates_one_section_per_file_workspace(tmp_path: Path):
    run_dir = tmp_path / "run-001"
    template_dir = tmp_path / "template"
    create_minimal_template(template_dir)

    result = scaffold_report_workspace(
        run_dir=run_dir,
        template_dir=template_dir,
        sections=["executive-summary", "kpi-overview", "data-table"],
        payload={"approved_query_result": {"rows": []}},
    )

    assert (run_dir / "report" / "Report.tsx").exists()
    assert (run_dir / "report" / "sections" / "01-executive-summary.tsx").exists()
    assert (run_dir / "report" / "sections" / "02-kpi-overview.tsx").exists()
    assert (run_dir / "report" / "sections" / "03-data-table.tsx").exists()
    assert (run_dir / "report" / "payload" / "approved-query-result.json").exists()
    assert result["section_count"] == 3


def test_cli_scaffold_report_builds_default_five_section_workspace(tmp_path: Path):
    run_dir = tmp_path / "run-002"
    template_dir = tmp_path / "template"
    create_minimal_template(template_dir)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_scripts.cli_report_harness",
            "scaffold-report",
            "--run-dir",
            str(run_dir),
            "--design",
            "financial-control",
            "--template-dir",
            str(template_dir),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "scaffolded"
    assert payload["section_count"] == 5
    assert (run_dir / "report" / "sections" / "05-recommendations.tsx").exists()


def test_scaffold_refuses_existing_report_files_without_force(tmp_path: Path):
    run_dir = tmp_path / "run-existing"
    template_dir = tmp_path / "template"
    create_minimal_template(template_dir)
    (run_dir / "report").mkdir(parents=True)
    report_path = run_dir / "report" / "Report.tsx"
    report_path.write_text("export default function ExistingReport() { return null; }\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Report.tsx"):
        scaffold_report_workspace(
            run_dir=run_dir,
            template_dir=template_dir,
            sections=["executive-summary"],
            payload={"approved_query_result": {"rows": []}},
        )

    assert "ExistingReport" in report_path.read_text(encoding="utf-8")


def test_scaffold_refuses_existing_payload_without_force(tmp_path: Path):
    run_dir = tmp_path / "run-existing-payload"
    template_dir = tmp_path / "template"
    create_minimal_template(template_dir)
    (run_dir / "report" / "payload").mkdir(parents=True)
    payload_path = run_dir / "report" / "payload" / "approved-query-result.json"
    payload_path.write_text('{"stale": true}\n', encoding="utf-8")

    with pytest.raises(FileExistsError, match="approved-query-result.json"):
        scaffold_report_workspace(
            run_dir=run_dir,
            template_dir=template_dir,
            sections=["executive-summary"],
            payload={"approved_query_result": {"rows": []}},
        )

    assert json.loads(payload_path.read_text(encoding="utf-8")) == {"stale": True}


def test_scaffold_force_allows_overwriting_existing_report_files(tmp_path: Path):
    run_dir = tmp_path / "run-force"
    template_dir = tmp_path / "template"
    create_minimal_template(template_dir)
    (run_dir / "report" / "payload").mkdir(parents=True)
    (run_dir / "report" / "payload" / "approved-query-result.json").write_text(
        '{"stale": true}\n',
        encoding="utf-8",
    )

    result = scaffold_report_workspace(
        run_dir=run_dir,
        template_dir=template_dir,
        sections=["executive-summary"],
        payload={"approved_query_result": {"rows": [{"id": 1}]}},
        force=True,
    )

    assert result["section_count"] == 1
    approved = json.loads(
        (run_dir / "report" / "payload" / "approved-query-result.json").read_text(encoding="utf-8")
    )
    assert approved == {"rows": [{"id": 1}]}


def test_scaffold_generates_unique_components_for_duplicate_and_non_ascii_sections(tmp_path: Path):
    run_dir = tmp_path / "run-duplicates"
    template_dir = tmp_path / "template"
    create_minimal_template(template_dir)

    scaffold_report_workspace(
        run_dir=run_dir,
        template_dir=template_dir,
        sections=["KPI Overview", "kpi-overview", "Risk & Control", "Risk Control", "管理摘要", "!!!"],
        payload={"approved_query_result": {"rows": []}},
    )

    component_names = []
    for section_file in sorted((run_dir / "report" / "sections").glob("*.tsx")):
        match = re.search(r"export function ([A-Za-z][A-Za-z0-9]*)\(", section_file.read_text(encoding="utf-8"))
        assert match is not None
        component_names.append(match.group(1))

    assert len(component_names) == 6
    assert len(set(component_names)) == len(component_names)
    assert all(re.search(r"\d{2}Section$", name) for name in component_names)


def test_validate_report_protocol_rejects_mismatched_import_export_render_linkage(tmp_path: Path):
    run_dir = tmp_path / "run-invalid-linkage"
    template_dir = tmp_path / "template"
    create_minimal_template(template_dir)
    scaffold_report_workspace(
        run_dir=run_dir,
        template_dir=template_dir,
        sections=["executive-summary"],
        payload={"approved_query_result": {"rows": []}},
    )
    (run_dir / "report" / "Report.tsx").write_text(
        "\n".join(
            [
                'import { ExecutiveSummary01Section } from "./sections/01-executive-summary";',
                "export default function Report() {",
                "  return <main><MissingSection /></main>;",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="render"):
        validate_report_protocol(run_dir)


def test_scaffold_preserves_full_payload_context_and_validator_evidence(tmp_path: Path):
    run_dir = tmp_path / "run-payload-context"
    template_dir = tmp_path / "template"
    create_minimal_template(template_dir)
    payload = {
        "approved_query_result": {"rows": [{"amount": 1200}]},
        "validator_evidence": [{"validator": "sql-execution", "status": "pass"}],
        "report_context": {"design": "financial-control"},
    }

    scaffold_report_workspace(
        run_dir=run_dir,
        template_dir=template_dir,
        sections=["executive-summary"],
        payload=payload,
    )

    payload_dir = run_dir / "report" / "payload"
    assert json.loads((payload_dir / "approved-query-result.json").read_text(encoding="utf-8")) == {
        "rows": [{"amount": 1200}]
    }
    assert json.loads((payload_dir / "report-context.json").read_text(encoding="utf-8")) == payload


def test_cli_scaffold_report_returns_json_error_for_expected_scaffold_errors(tmp_path: Path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_scripts.cli_report_harness",
            "scaffold-report",
            "--run-dir",
            str(tmp_path / "run-missing-template"),
            "--design",
            "financial-control",
            "--template-dir",
            str(tmp_path / "missing-template"),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    error = json.loads(result.stderr)
    assert error["status"] == "error"
    assert error["code"] == "scaffold_error"
    assert "template" in error["message"].lower()


def test_write_generated_report_section_replaces_single_section_and_preserves_protocol(tmp_path: Path):
    run_dir = tmp_path / "run-generated-section"
    template_dir = tmp_path / "template"
    create_minimal_template(template_dir)
    scaffold_report_workspace(
        run_dir=run_dir,
        template_dir=template_dir,
        sections=["executive-summary", "data-table"],
        payload={"approved_query_result": {"rows": [{"amount": 1200}]}},
    )
    code = """
import React from "react";

export function ExecutiveSummary01Section() {
  const dataRefs = ["approved-query-result.rows.amount"];
  return (
    <section data-section="executive-summary" data-refs={dataRefs.join(",")}>
      <h2>費用摘要</h2>
      <p>本段由 LLM 依已確認資料產生。</p>
    </section>
  );
}
"""

    result = write_generated_report_section(
        run_dir=run_dir,
        section_id="01-executive-summary",
        component_name="ExecutiveSummary01Section",
        code=code,
        mode="repair",
    )

    section_path = Path(result["path"])
    assert section_path.name == "01-executive-summary.tsx"
    assert "本段由 LLM" in section_path.read_text(encoding="utf-8")
    assert result["status"] == "section_written"
    validate_report_protocol(run_dir)


def test_write_generated_report_section_rejects_network_env_and_missing_data_refs(tmp_path: Path):
    run_dir = tmp_path / "run-unsafe-section"
    template_dir = tmp_path / "template"
    create_minimal_template(template_dir)
    scaffold_report_workspace(
        run_dir=run_dir,
        template_dir=template_dir,
        sections=["executive-summary"],
        payload={"approved_query_result": {"rows": []}},
    )
    unsafe_code = """
import React from "react";

export function ExecutiveSummary01Section() {
  fetch("https://example.com/report");
  return <section data-section="executive-summary"><h2>Bad</h2></section>;
}
"""

    with pytest.raises(ValueError, match="network"):
        write_generated_report_section(
            run_dir=run_dir,
            section_id="01-executive-summary",
            component_name="ExecutiveSummary01Section",
            code=unsafe_code,
            mode="repair",
        )


def test_cli_generate_and_validate_report_section(tmp_path: Path):
    run_dir = tmp_path / "run-cli-generated-section"
    template_dir = tmp_path / "template"
    create_minimal_template(template_dir)
    scaffold_report_workspace(
        run_dir=run_dir,
        template_dir=template_dir,
        sections=["executive-summary"],
        payload={"approved_query_result": {"rows": [{"amount": 1200}]}},
    )
    code_file = tmp_path / "section.tsx"
    code_file.write_text(
        """
import React from "react";

export function ExecutiveSummary01Section() {
  const dataRefs = ["approved-query-result.rows.amount"];
  return <section data-section="executive-summary" data-refs={dataRefs.join(",")}><h2>費用摘要</h2></section>;
}
""",
        encoding="utf-8",
    )

    generated = subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_scripts.cli_report_harness",
            "generate-report-section",
            "--run-dir",
            str(run_dir),
            "--section-id",
            "01-executive-summary",
            "--component-name",
            "ExecutiveSummary01Section",
            "--code-file",
            str(code_file),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert generated.returncode == 0, generated.stderr
    assert json.loads(generated.stdout)["status"] == "section_written"

    validated = subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_scripts.cli_report_harness",
            "validate-report-section",
            "--run-dir",
            str(run_dir),
            "--section-id",
            "01-executive-summary",
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert validated.returncode == 0, validated.stderr
    assert json.loads(validated.stdout)["status"] == "section_valid"
