#!/usr/bin/env bash
set -euo pipefail

pytest tests/skill_scripts/test_style_replay_e2e.py -v
echo "style_replay_e2e=pass style_fingerprint=same stale_data=false adjustment_checkpoint=required_when_incompatible"
