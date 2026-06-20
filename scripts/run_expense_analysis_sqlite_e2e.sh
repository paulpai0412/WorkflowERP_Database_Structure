#!/usr/bin/env bash
set -euo pipefail

python3 -m tests.skill_scripts.expense_report_fixture --sqlite-e2e
