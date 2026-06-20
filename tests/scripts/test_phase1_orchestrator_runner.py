from __future__ import annotations

from pathlib import Path

from pytest import CaptureFixture

from scripts.phase1_orchestrator_runner import main, parse_issue_packet_text, run_phase1


SAMPLE_ISSUE_PACKET = """schema_version: "1.0"
kind: issue_packet
line_cap: 80

issue:
  number: "42"
  title: "Demo issue"
  url: "https://github.com/example/issues/42"
  labels: [ready-for-agent]
  parent: {type: "prd", reference: "https://github.com/example/issues/1"}

branch: {name: "agent/issue-42-demo", base: "main"}

bootstrap_context:
  required_reads: ["AGENTS.md"]
  context_budget: {checkpoint_warning_at_percent: 45, stop_and_rotate_at_percent: 50}
  relevant_paths: ["scripts"]
  prior_handoff: "docs/agents/handoffs/issue-41.yaml"
"""


SAMPLE_CHECKPOINT = """schema_version: "1.0"
kind: context_checkpoint
line_cap: 80

subject:
  issue_number: "6"
  branch: "agent/issue-6-old"
  role: "main_orchestrator"
  checkpoint_reason: "selected_afk_issue"

context_budget:
  warning_at_percent: 45
  stop_and_rotate_at_percent: 50
  measured_percent_used: "unknown"
  must_rotate_now: false

resume_policy:
  checkpoint_only_cross_session_resume: true
  do_not_import_full_prior_transcript: true
  raw_evidence_policy: "index_only; raw logs/traces stay in artifact bundle"

state:
  completed:
    - "Issue #41 already merged."
  in_progress:
    - "Old state."
  next:
    - "Old next step."
  blockers:
    - "none"

refs:
  issue_packet: "docs/agents/issue-packets/issue-6.yaml"
  worker_result: ""
  evidence_packet: ""
  handoff: "docs/agents/handoffs/issue-5.yaml"
  artifact_bundle: ""

metadata:
  updated_by: "Hephaestus"
  updated_at: "2026-05-07T16:00:00+08:00"
"""


def test_parse_issue_packet_text_reads_issue_branch_and_handoff():
    record = parse_issue_packet_text(SAMPLE_ISSUE_PACKET, "docs/agents/issue-packets/issue-42.yaml")

    assert record.issue_number == "42"
    assert record.branch == "agent/issue-42-demo"
    assert record.issue_packet_path == "docs/agents/issue-packets/issue-42.yaml"
    assert record.prior_handoff == "docs/agents/handoffs/issue-41.yaml"


def test_run_phase1_updates_checkpoint_and_returns_next_action(tmp_path: Path):
    issue_packet_path = tmp_path / "issue-42.yaml"
    checkpoint_path = tmp_path / "context-checkpoint.yaml"
    request_path = tmp_path / "new-session-request.json"
    _ = issue_packet_path.write_text(SAMPLE_ISSUE_PACKET, encoding="utf-8")
    _ = checkpoint_path.write_text(SAMPLE_CHECKPOINT, encoding="utf-8")

    result = run_phase1(
        issue_packet_path=issue_packet_path,
        checkpoint_path=checkpoint_path,
        new_session_request_path=request_path,
        updated_at="2026-05-07T17:00:00+08:00",
    )

    updated = checkpoint_path.read_text(encoding="utf-8")
    request = request_path.read_text(encoding="utf-8")
    assert result.issue_number == "42"
    assert result.branch == "agent/issue-42-demo"
    assert result.new_session_request_path == request_path
    assert result.immediate_next_action.startswith("Continue per_issue_flow for issue #42")
    assert 'issue_number: "42"' in updated
    assert 'branch: "agent/issue-42-demo"' in updated
    assert 'handoff: "docs/agents/handoffs/issue-41.yaml"' in updated
    assert '"reason": "phase1 issue continuation for issue #42"' in request
    assert '"title": "Continue issue #42 on agent/issue-42-demo"' in request
    assert result.immediate_next_action in request


def test_main_reports_continuation_request_written(tmp_path: Path, capsys: CaptureFixture[str]):
    issue_packet_path = tmp_path / "issue-42.yaml"
    checkpoint_path = tmp_path / "context-checkpoint.yaml"
    request_path = tmp_path / "new-session-request.json"
    _ = issue_packet_path.write_text(SAMPLE_ISSUE_PACKET, encoding="utf-8")
    _ = checkpoint_path.write_text(SAMPLE_CHECKPOINT, encoding="utf-8")

    exit_code = main(
        [
            "--issue-packet",
            str(issue_packet_path),
            "--checkpoint",
            str(checkpoint_path),
            "--new-session-request",
            str(request_path),
            "--updated-at",
            "2026-05-07T17:00:00+08:00",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "phase1 runner: updated checkpoint" in captured.out
    assert "phase1 runner: wrote continuation request" in captured.out
