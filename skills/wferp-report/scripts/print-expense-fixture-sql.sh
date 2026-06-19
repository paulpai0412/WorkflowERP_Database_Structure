#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${WFERP_REPO_ROOT:-/home/timmypai/.codex/worktrees/5f5b/wferp}"
cd "${REPO_ROOT}"

python3 -m tests.skill_scripts.expense_report_fixture
