#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${WFERP_REPO_ROOT:-/home/timmypai/.codex/worktrees/5f5b/wferp}"
cd "${REPO_ROOT}"

bash scripts/run_expense_analysis_postgres_e2e.sh
