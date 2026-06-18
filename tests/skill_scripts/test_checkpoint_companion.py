from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

from skill_scripts.checkpoint_companion import CheckpointCompanionServer
from skill_scripts.report_harness import ReportHarness


def post_json(url: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def test_confirmation_post_writes_confirmation_and_audit(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_sql_review("SELECT department, amount FROM expenses", {"status": "pass"})

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        result = post_json(
            f"{server.base_url}/api/runs/run-001/checkpoints/sql_review/confirm",
            {
                "action": "同意查詢",
                "checkpointId": "sql_review",
                "comment": "條件正確，可以查詢",
                "selectedOptions": {"view": "management"},
            },
        )

    assert result["status"] == "confirmed"
    confirmation = json.loads(
        (tmp_path / "run-001" / "checkpoints" / "02_sql_review.confirmation.json").read_text(
            encoding="utf-8"
        )
    )
    assert confirmation["action"] == "同意查詢"
    assert confirmation["comment"] == "條件正確，可以查詢"
    assert confirmation["selectedOptions"] == {"view": "management"}
    audit_lines = (tmp_path / "run-001" / "audit" / "events.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    assert len(audit_lines) == 1
    assert json.loads(audit_lines[0])["event"] == "checkpoint_confirmed"
