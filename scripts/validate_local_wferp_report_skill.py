#!/usr/bin/env python3
"""Validate the local wferp-report Codex skill tree."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED_FILES = [
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

    for relative_path in REQUIRED_FILES:
        path = root / relative_path
        if not path.is_file():
            errors.append(f"Missing required file: {relative_path}")

    skill_md = root / "SKILL.md"
    if skill_md.is_file():
        skill_text = read_text(skill_md)
        for needle, message in REQUIRED_SKILL_SECTIONS.items():
            if needle not in skill_text:
                errors.append(message)

    references_root = root / "references"
    validators_path = references_root / "validators.md"
    if validators_path.is_file():
        validators_text = read_text(validators_path)
        for needle, message in REQUIRED_VALIDATOR_TEXT.items():
            if needle not in validators_text:
                errors.append(message)

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
