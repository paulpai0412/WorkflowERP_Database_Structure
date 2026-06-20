#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${WFERP_REPO_ROOT:-/home/timmypai/.codex/worktrees/5f5b/wferp}"
SKILL_ROOT="${WFERP_REPORT_SKILL_ROOT:-/home/timmypai/.codex/skills/wferp-report}"
cd "${REPO_ROOT}"

python3 scripts/validate_local_wferp_report_skill.py --skill-root "${SKILL_ROOT}"
