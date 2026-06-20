---
description: Start the Phase 1 orchestrator checkpoint-to-new-session flow for a selected AFK issue packet
agent: build
subtask: false
---

Run the Phase 1 orchestrator checkpoint-to-new-session runner for issue packet `$ARGUMENTS`.

1. Execute:
!`python3 scripts/phase1_orchestrator_runner.py --issue-packet $ARGUMENTS`
2. Read `docs/agents/runtime/context-checkpoint.yaml` after the runner updates it.
3. Read `.opencode/runtime/new-session-request.json` after the runner writes it.
4. Tell me the checkpoint update result, the continuation request path, and the immediate next action.

Do not start worker execution yet. Stop after reporting the runner output and the generated continuation request.
