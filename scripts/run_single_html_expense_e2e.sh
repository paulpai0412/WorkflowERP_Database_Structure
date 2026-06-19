#!/usr/bin/env bash
set -euo pipefail

pytest tests/skill_scripts/test_single_html_expense_e2e.py -v
echo "single_html_expense_e2e=pass row_count=6 total_amount=120000 total_budget=100000 variance_amount=20000 max_expense_ratio=0.35"
