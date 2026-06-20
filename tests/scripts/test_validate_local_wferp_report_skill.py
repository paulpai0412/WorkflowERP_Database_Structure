import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "validate_local_wferp_report_skill.py"

REQUIRED_PARITY_FILES = [
    "SKILL.md",
    "manifest.json",
    "README.md",
    "references/harness.md",
    "references/db-config.md",
    "references/excel-intake.md",
    "references/schema-context.md",
    "references/sql-safety.md",
    "references/checkpoint-payload-schema.md",
    "references/report-payload-schema.md",
    "references/component-policy.md",
    "references/rawblock-policy.md",
    "references/scaffold.md",
    "references/section-build.md",
    "references/report-plan-template.md",
    "references/review-checklist.md",
    "references/repair-policy.md",
    "references/html-output.md",
    "references/validators.md",
    "references/e2e-expense-analysis.md",
    "references/single-html-export.md",
    "references/visual-companion-ui.md",
    "references/dynamic-design-brief.md",
    "references/style-replay.md",
    "scripts/scaffold-report.sh",
    "scripts/validate-skill.sh",
    "scripts/print-expense-fixture-sql.sh",
    "scripts/run-expense-sqlite-e2e.sh",
    "scripts/run-expense-postgres-e2e.sh",
    "report_designs/index.json",
    "report_designs/design.md",
    "report_designs/financial-control.md",
    "report_designs/executive-summary.md",
    "report_designs/detail-ledger.md",
    "report_designs/exception-audit.md",
    "report_designs/operations-review.md",
    "report_designs/trend-briefing.md",
    "assets/scaffold-template/package.json",
    "assets/scaffold-template/index.html",
    "assets/scaffold-template/report/Report.tsx",
]

REQUIRED_PHASES = [
    "Phase 0 —— Intake",
    "Phase 1 —— Source / Excel Requirement",
    "Phase 2 —— Report Planning",
    "Phase 3 —— Field & Formula Checkpoint",
    "Phase 4 —— SQL Review Checkpoint",
    "Phase 5 —— Confirmed DB Execution",
    "Phase 6 —— Data Preview Checkpoint",
    "Phase 7 —— Report Selection Checkpoint",
    "Phase 8 —— Final Report Scaffold",
    "Phase 9 —— Section Build",
    "Phase 10 —— Final Review",
    "Phase 11 —— Repair",
    "Phase 12 —— Delivery",
]

REQUIRED_PHASE_FIELDS = [
    "目標：",
    "輸入：",
    "必讀 references：",
    "執行步驟：",
    "產物：",
    "停止條件：",
    "使用者 checkpoint：",
    "validator：",
    "失敗時 repair slice：",
]


def load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_local_wferp_report_skill", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_file(path: Path, content: str = "content") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def complete_skill_md(
    omitted_phase: str | None = None,
    omitted_field_by_phase: dict[str, str] | None = None,
) -> str:
    omitted_field_by_phase = omitted_field_by_phase or {}
    lines = [
        "# wferp-report",
        "Intake prompt and uploaded files.",
        "Parse Excel fields and formulas.",
        "Generate Excel confirmation HTML.",
        "Map requested fields to WFERP schema and relationships.",
        "Generate read-only SQL.",
        "Validate SQL safety locally.",
        "Execute only after user confirmation.",
        "Present data preview HTML.",
        "Ask user to choose report type, design, and options.",
        "Generate report draft HTML via React renderer.",
        "Run validators using subagents.",
        "Present final report and validation evidence.",
    ]
    for phase in REQUIRED_PHASES:
        if phase == omitted_phase:
            continue
        lines.append(f"## {phase}")
        for field in REQUIRED_PHASE_FIELDS:
            if omitted_field_by_phase.get(phase) == field:
                continue
            lines.append(f"{field} phase content")
    return "\n".join(lines)


def create_complete_skill_tree(root: Path) -> None:
    write_file(root / "SKILL.md", complete_skill_md())
    for relative_path in REQUIRED_PARITY_FILES:
        path = root / relative_path
        if path.exists():
            continue
        write_file(path, f"# {path.name}\n")
    write_file(
        root / "references" / "single-html-export.md",
        "\n".join(
            [
                "# Single HTML Export",
                "單檔 HTML delivery must use checkpoint-confirmed data.",
                "HTML 不得連 DB。",
                "HTML 不得執行 SQL。",
                "network requests = 0",
            ]
        ),
    )
    write_file(
        root / "references" / "dynamic-design-brief.md",
        "# Dynamic Design Brief\nsingle HTML visual checkpoint and 使用者確認\n",
    )
    write_file(
        root / "references" / "style-replay.md",
        "# Style Replay\nsingle HTML style replay requires checkpoint for incompatible charts\n",
    )
    write_file(
        root / "references" / "validators.md",
        "\n".join(
            [
                "# validators",
                "需求/來源 validator",
                "Excel 欄位與公式 validator",
                "SQL 安全 validator",
                "Schema/relationship validator",
                "Data preview validator",
                "報告內容 validator",
                "視覺/技術 validator",
            ]
        ),
    )
    for name in [
        "design.md",
        "executive-summary.md",
        "financial-control.md",
        "operations-review.md",
        "exception-audit.md",
        "trend-briefing.md",
        "detail-ledger.md",
    ]:
        write_file(root / "report_designs" / name, f"# {name}\nrequired_sections\nvalidator_checklist\n")
    write_file(root / "assets" / "sample-expense-analysis-prompt.md", "請產出2026第一季費用分析")


def validate_skill_directory(skill_dir: Path) -> dict[str, list[dict[str, str]]]:
    module = load_validator_module()
    result = module.validate_skill_tree(skill_dir)
    missing = []
    for error in result.errors:
        if ": " not in error:
            continue
        path = error.rsplit(": ", 1)[1]
        missing.append({"path": path})
    return {"missing": missing}


def test_validator_requires_harness_parity_files(tmp_path):
    skill_dir = tmp_path / "wferp-report"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "scripts").mkdir()
    (skill_dir / "report_designs").mkdir()
    (skill_dir / "SKILL.md").write_text("## 背景原則\n", encoding="utf-8")

    result = validate_skill_directory(skill_dir)

    missing = {item["path"] for item in result["missing"]}
    assert "manifest.json" in missing
    assert "references/checkpoint-payload-schema.md" in missing
    assert "references/rawblock-policy.md" in missing
    assert "references/scaffold.md" in missing
    assert "report_designs/index.json" in missing
    assert "assets/scaffold-template/package.json" in missing


def test_validator_accepts_complete_skill_tree(tmp_path):
    module = load_validator_module()
    skill_root = tmp_path / "wferp-report"
    create_complete_skill_tree(skill_root)

    result = module.validate_skill_tree(skill_root)

    assert result.ok is True
    assert result.errors == []


def test_validator_rejects_missing_skill_md(tmp_path):
    module = load_validator_module()
    skill_root = tmp_path / "wferp-report"
    create_complete_skill_tree(skill_root)
    (skill_root / "SKILL.md").unlink()

    result = module.validate_skill_tree(skill_root)

    assert result.ok is False
    assert any("SKILL.md" in error for error in result.errors)


def test_validator_requires_harness_sections(tmp_path):
    module = load_validator_module()
    skill_root = tmp_path / "wferp-report"
    create_complete_skill_tree(skill_root)
    write_file(skill_root / "SKILL.md", "# wferp-report\nGenerate read-only SQL.")

    result = module.validate_skill_tree(skill_root)

    assert result.ok is False
    assert any("Excel confirmation" in error or "React renderer" in error for error in result.errors)


def test_validator_requires_exact_phase_headings(tmp_path):
    module = load_validator_module()
    skill_root = tmp_path / "wferp-report"
    create_complete_skill_tree(skill_root)
    write_file(skill_root / "SKILL.md", complete_skill_md(omitted_phase="Phase 4 —— SQL Review Checkpoint"))

    result = module.validate_skill_tree(skill_root)

    assert result.ok is False
    assert any("Missing required SKILL.md phase: Phase 4 —— SQL Review Checkpoint" in error for error in result.errors)


def test_validator_requires_phase_fields_inside_phase_section(tmp_path):
    module = load_validator_module()
    skill_root = tmp_path / "wferp-report"
    create_complete_skill_tree(skill_root)
    write_file(
        skill_root / "SKILL.md",
        complete_skill_md(
            omitted_field_by_phase={
                "Phase 4 —— SQL Review Checkpoint": "使用者 checkpoint：",
            }
        ),
    )

    result = module.validate_skill_tree(skill_root)

    assert result.ok is False
    assert any(
        "Phase 4 —— SQL Review Checkpoint missing required field: 使用者 checkpoint：" in error
        for error in result.errors
    )


def test_validator_requires_validator_references(tmp_path):
    module = load_validator_module()
    skill_root = tmp_path / "wferp-report"
    create_complete_skill_tree(skill_root)
    write_file(skill_root / "references" / "validators.md", "# validators\nSQL 安全 validator")

    result = module.validate_skill_tree(skill_root)

    assert result.ok is False
    assert any("Data preview validator" in error for error in result.errors)


def test_validator_requires_report_designs(tmp_path):
    module = load_validator_module()
    skill_root = tmp_path / "wferp-report"
    create_complete_skill_tree(skill_root)
    (skill_root / "report_designs" / "financial-control.md").unlink()

    result = module.validate_skill_tree(skill_root)

    assert result.ok is False
    assert any("financial-control.md" in error for error in result.errors)


def test_validator_reports_invalid_utf8_in_read_files(tmp_path):
    module = load_validator_module()
    skill_root = tmp_path / "wferp-report"
    create_complete_skill_tree(skill_root)
    validators_text = "\n".join(
        [
            "# validators",
            "需求/來源 validator",
            "Excel 欄位與公式 validator",
            "SQL 安全 validator",
            "Schema/relationship validator",
            "Data preview validator",
            "報告內容 validator",
            "視覺/技術 validator",
        ]
    ).encode("utf-8")
    (skill_root / "references" / "validators.md").write_bytes(validators_text + b"\xff")

    result = module.validate_skill_tree(skill_root)

    assert result.ok is False
    assert "Invalid UTF-8: references/validators.md" in result.errors


def test_skill_documents_single_html_export_and_style_replay(tmp_path):
    skill_root = tmp_path / "wferp-report"
    create_complete_skill_tree(skill_root)

    for path in [
        skill_root / "references" / "single-html-export.md",
        skill_root / "references" / "dynamic-design-brief.md",
        skill_root / "references" / "style-replay.md",
    ]:
        assert path.exists(), path
        text = path.read_text(encoding="utf-8")
        assert "single HTML" in text or "單檔 HTML" in text
        assert "checkpoint" in text or "確認" in text


@pytest.mark.parametrize(
    "relative_path",
    [
        "references/single-html-export.md",
        "references/dynamic-design-brief.md",
        "references/style-replay.md",
    ],
)
def test_validator_rejects_missing_single_html_reference_files(tmp_path, relative_path):
    module = load_validator_module()
    skill_root = tmp_path / "wferp-report"
    create_complete_skill_tree(skill_root)
    (skill_root / relative_path).unlink()

    result = module.validate_skill_tree(skill_root)

    assert result.ok is False
    assert f"Missing required file: {relative_path}" in result.errors


def test_skill_requires_no_db_access_from_single_html(tmp_path):
    skill_root = tmp_path / "wferp-report"
    create_complete_skill_tree(skill_root)
    text = (skill_root / "references" / "single-html-export.md").read_text(encoding="utf-8")

    assert "不得連 DB" in text
    assert "不得執行 SQL" in text
    assert "network requests = 0" in text


@pytest.mark.parametrize("needle", ["不得連 DB", "不得執行 SQL", "network requests = 0"])
def test_validator_rejects_missing_single_html_safety_text(tmp_path, needle):
    module = load_validator_module()
    skill_root = tmp_path / "wferp-report"
    create_complete_skill_tree(skill_root)
    path = skill_root / "references" / "single-html-export.md"
    path.write_text(path.read_text(encoding="utf-8").replace(needle, ""), encoding="utf-8")

    result = module.validate_skill_tree(skill_root)

    assert result.ok is False
    assert f"single-html-export.md missing required text: {needle}" in result.errors


def test_wferp_report_skill_documents_4_step_stateful_visual_companion():
    repo_root = ROOT
    skill = (repo_root / "skills" / "wferp-report" / "SKILL.md").read_text(encoding="utf-8")
    harness = (repo_root / "skills" / "wferp-report" / "references" / "harness.md").read_text(encoding="utf-8")
    ui = (repo_root / "skills" / "wferp-report" / "references" / "visual-companion-ui.md").read_text(
        encoding="utf-8"
    )
    validators = (repo_root / "skills" / "wferp-report" / "references" / "validators.md").read_text(
        encoding="utf-8"
    )
    excel = (repo_root / "skills" / "wferp-report" / "references" / "excel-intake.md").read_text(
        encoding="utf-8"
    )

    for text in (skill, harness, ui):
        assert "13" in text
        assert "4-step" in text or "4 user-facing" in text
        assert "state.json" in text
        assert "Build Web Apps" in text
        assert "Build Web Data Visualization" in text
        assert "spreadsheets" in text
        assert "50" in text
        assert "prompt" in text and "repair" in text

    assert "fresh reviewer" in validators
    assert "subagent" in validators
    assert "hardcode" in validators
    assert "source-to-output" in excel.lower()
    assert "@oai/artifact-tool" in excel
