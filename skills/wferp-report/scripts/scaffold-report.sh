#!/usr/bin/env bash
set -euo pipefail

SKILL_ROOT="${WFERP_REPORT_SKILL_ROOT:-/home/timmypai/.codex/skills/wferp-report}"
DESTINATION="${1:-}"

if [[ -z "${DESTINATION}" ]]; then
  echo "usage: scaffold-report.sh <destination-dir>" >&2
  exit 2
fi

mkdir -p "${DESTINATION}"
cp -R "${SKILL_ROOT}/assets/scaffold-template/." "${DESTINATION}/"
echo "scaffold created: ${DESTINATION}"
