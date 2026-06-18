#!/usr/bin/env python3
"""Validate the local wferp-report Codex skill tree."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED_REFERENCES = [
    "harness.md",
    "db-config.md",
    "schema-context.md",
    "excel-intake.md",
    "sql-safety.md",
    "validators.md",
    "react-renderer.md",
    "e2e-expense-analysis.md",
]

REQUIRED_REPORT_DESIGNS = [
    "design.md",
    "executive-summary.md",
    "financial-control.md",
    "operations-review.md",
    "exception-audit.md",
    "trend-briefing.md",
    "detail-ledger.md",
]

REQUIRED_SKILL_SECTIONS = {
    "uploaded files": "SKILL.md must describe intake of uploaded files.",
    "Excel confirmation": "SKILL.md must describe Excel confirmation HTML.",
    "WFERP schema": "SKILL.md must describe mapping to WFERP schema and relationships.",
    "read-only SQL": "SKILL.md must describe read-only SQL generation.",
    "SQL safety": "SKILL.md must describe local SQL safety validation.",
    "user confirmation": "SKILL.md must require user confirmation before execution.",
    "data preview": "SKILL.md must describe data preview HTML.",
    "report type": "SKILL.md must ask the user to choose report type/design/options.",
    "React renderer": "SKILL.md must describe report draft generation via React renderer.",
    "validators": "SKILL.md must describe validators.",
    "validation evidence": "SKILL.md must present final validation evidence.",
}

REQUIRED_VALIDATOR_TEXT = {
    "需求/來源 validator": "validators.md must define 需求/來源 validator.",
    "Excel 欄位與公式 validator": "validators.md must define Excel 欄位與公式 validator.",
    "SQL 安全 validator": "validators.md must define SQL 安全 validator.",
    "Schema/relationship validator": "validators.md must define Schema/relationship validator.",
    "Data preview validator": "validators.md must define Data preview validator.",
    "報告內容 validator": "validators.md must define 報告內容 validator.",
    "視覺/技術 validator": "validators.md must define 視覺/技術 validator.",
}


class ValidationResult:
    def __init__(self, errors: list[str]):
        self.errors = errors

    @property
    def ok(self) -> bool:
        return not self.errors


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def validate_skill_tree(skill_root: str | Path) -> ValidationResult:
    root = Path(skill_root)
    errors: list[str] = []

    skill_md = root / "SKILL.md"
    if not skill_md.is_file():
        errors.append(f"Missing required file: {skill_md.name}")
    else:
        skill_text = read_text(skill_md)
        for needle, message in REQUIRED_SKILL_SECTIONS.items():
            if needle not in skill_text:
                errors.append(message)

    references_root = root / "references"
    for name in REQUIRED_REFERENCES:
        path = references_root / name
        if not path.is_file():
            errors.append(f"Missing required reference: references/{name}")

    validators_path = references_root / "validators.md"
    if validators_path.is_file():
        validators_text = read_text(validators_path)
        for needle, message in REQUIRED_VALIDATOR_TEXT.items():
            if needle not in validators_text:
                errors.append(message)

    designs_root = root / "report_designs"
    for name in REQUIRED_REPORT_DESIGNS:
        path = designs_root / name
        if not path.is_file():
            errors.append(f"Missing required report design: report_designs/{name}")

    sample_prompt = root / "assets" / "sample-expense-analysis-prompt.md"
    if not sample_prompt.is_file():
        errors.append("Missing required asset: assets/sample-expense-analysis-prompt.md")

    return ValidationResult(errors)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local wferp-report skill files.")
    parser.add_argument("--skill-root", required=True, help="Path to /home/.../.codex/skills/wferp-report")
    args = parser.parse_args()

    result = validate_skill_tree(args.skill_root)
    if result.ok:
        print("wferp-report skill validation passed")
        return 0
    print("wferp-report skill validation failed")
    for error in result.errors:
        print(f"- {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
