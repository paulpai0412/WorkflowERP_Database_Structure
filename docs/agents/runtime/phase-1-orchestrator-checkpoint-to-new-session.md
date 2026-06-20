# Phase 1 orchestrator checkpoint-to-new-session spec

## Status

- Status: active MVP
- Owner: main orchestrator session
- Source of truth: `docs/agents/autonomous-development-workflow.yaml#context_budget_policy`

## Purpose

Define the minimum executable contract for Phase 1 of the autonomous workflow:

1. select the next ready AFK issue
2. persist a checkpoint for the selected issue
3. derive a compact payload from the checkpoint
4. write a fresh-session continuation request for the plugin
5. continue into the selected issue PR flow from a fresh session

This phase reduces orchestrator context before new issue PR work by switching from checkpoint state into a fresh session instead of relying on native compaction.

## Applies to

- `main_orchestrator` only

## Does not apply to

- issue worker sessions
- PR verifier sessions
- phase verifier sessions
- release worker sessions
- no-ready-issue PRD completeness audit path

## Trigger

Trigger this flow only when all conditions are true:

1. the orchestrator is inside `issue_development_loop`
2. `issue_selection` returned an issue labeled `ready-for-agent`
3. the selected slice type is `AFK`
4. the orchestrator is about to enter `per_issue_flow`

Do not trigger from branch changes, git hooks, PR webhooks, or generic session events.

## Required inputs

- selected issue number
- selected issue branch name
- selected issue packet path
- latest prior handoff path when present
- current workflow policy path
- current orchestrator role

## Required outputs

- updated `docs/agents/runtime/context-checkpoint.yaml`
- derived compact payload embedded in the checkpoint
- written `.opencode/runtime/new-session-request.json`
- fresh orchestrator session ready to continue `per_issue_flow`

## Current implementation reference

- payload derivation and checkpoint rewrite helper: `scripts/phase1_compact_payload.py`
- orchestrator runner: `scripts/phase1_orchestrator_runner.py`
- continuation plugin: `.opencode/plugins/session-continuation.ts`
- OpenCode project command: `.opencode/commands/phase1-start.md`

## Algorithm

1. Run `issue_selection`.
2. If no `ready-for-agent` AFK issue exists, do not start `per_issue_flow`; return control to `prd_phase_completeness_audit` in the main workflow.
3. Populate `context-checkpoint.yaml` for the selected issue.
4. Derive `compact_payload` from the checkpoint using the rules below.
5. Write `.opencode/runtime/new-session-request.json` with a checkpoint-only bootstrap prompt.
6. Let the session-continuation plugin consume the request on `session.idle` and create a fresh root session.
7. Continue `per_issue_flow` in the fresh session in this order:
   - `create_or_switch_issue_branch`
   - `build_issue_packet`
   - `spawn_fresh_issue_worker`
   - remaining verifier and handoff steps already defined in workflow policy

If any step before request generation fails, stop and report blocked; do not start worker execution.

When step 2 routes to `prd_phase_completeness_audit`, this Phase 1 checkpoint-to-new-session contract is not the active flow. In that branch, the orchestrator should resume from PRD/workflow references and the latest phase handoff rather than forcing an issue packet-shaped payload.

## Compact payload contract

The orchestrator must not inject the full checkpoint body into the continuation prompt. It must derive a compact payload with exactly these sections:

### 1. active_target

- `issue_number`
- `branch`
- `role`
- `next_flow`

### 2. authoritative_refs

Must include only canonical resume entry points:

- issue packet
- prior handoff when present
- workflow policy

Must not include full transcript exports, raw logs, or ad hoc search dumps.

### 3. state_snapshot

- `completed`
- `in_progress`
- `next`
- `blockers`

Keep each list short and action-oriented.

### 4. resume_rules

Must restate these rules in compact form:

- resume from checkpoint and compact payload, not full chat history
- keep raw evidence as refs only
- do not inline logs, traces, or long transcripts

### 5. immediate_next_action

One imperative sentence that tells the fresh session what to do first.

## Checkpoint and continuation request write rules

When updating `context-checkpoint.yaml` and writing the continuation request, the orchestrator must:

- set `subject.role` to `main_orchestrator`
- record the selected issue and branch
- keep the checkpoint file within the 80-line cap
- update `metadata.updated_at`
- keep refs stable and canonical
- write the continuation request under `.opencode/runtime/new-session-request.json`
- ensure the request prompt explicitly says checkpoint-only bootstrap and forbids prior transcript import

## Failure handling

### Checkpoint update failure

- status: blocked
- action: stop before continuation request write
- report: checkpoint write failure and missing fields

### Compact payload derivation failure

- status: blocked
- action: stop before continuation request write
- report: which required payload section is missing

### Continuation request write failure

- status: blocked
- action: stop before worker spawn
- report: request path write failed or required fields were missing

### Fresh-session bootstrap failure

- status: blocked
- action: stop before worker spawn
- report: plugin failed to create the root session or prompt it from checkpoint

## Non-goals

- native session compaction for Phase 1 startup
- automatic `>50%` context auto-rotation outside this flow
- hook-driven orchestration beyond consuming the explicit continuation request
- branch-change or webhook-driven passive triggering

## Active handoff contract

Phase 1 now uses this order:

1. write checkpoint
2. write fresh-session continuation request
3. plugin creates a fresh orchestrator session from checkpoint
4. fresh session continues `per_issue_flow`

This replaces the previous same-session startup behavior.
