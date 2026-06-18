import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "validate_local_wferp_report_skill.py"


def load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_local_wferp_report_skill", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_file(path: Path, content: str = "content") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_complete_skill_tree(root: Path) -> None:
    write_file(
        root / "SKILL.md",
        "\n".join(
            [
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
        ),
    )
    for name in [
        "harness.md",
        "db-config.md",
        "schema-context.md",
        "excel-intake.md",
        "sql-safety.md",
        "validators.md",
        "react-renderer.md",
        "e2e-expense-analysis.md",
    ]:
        write_file(root / "references" / name, f"# {name}\n")
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
