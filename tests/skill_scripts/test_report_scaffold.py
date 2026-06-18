from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from skill_scripts.report_scaffold import scaffold_report_workspace


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
