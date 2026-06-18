#!/usr/bin/env bash
set -euo pipefail

PROMPT="請產出2026第一季費用分析，依部門與會計科目彙總未稅金額、稅額、總額與占比"

echo "SQLite first-pass E2E: local database syntax and aggregate validation"
echo "Generated SQL:"
python3 -m tests.skill_scripts.expense_report_fixture

export WFERP_RUN_SQLITE_E2E=1
pytest tests/skill_scripts/test_expense_analysis_sqlite_e2e.py -v
