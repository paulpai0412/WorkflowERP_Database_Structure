from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError
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


def request_bytes(url: str, data: bytes, content_type: str = "application/json") -> tuple[int, dict]:
    request = Request(
        url,
        data=data,
        headers={"Content-Type": content_type},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


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


def test_companion_server_uses_daemon_request_threads(tmp_path: Path):
    ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        assert server.httpd.daemon_threads is True


def test_confirmation_post_rejects_malformed_json_and_invalid_utf8(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_sql_review("SELECT department, amount FROM expenses", {"status": "pass"})

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        malformed_status, malformed_body = request_bytes(
            f"{server.base_url}/api/runs/run-001/checkpoints/sql_review/confirm",
            b'{"action":',
        )
        utf8_status, utf8_body = request_bytes(
            f"{server.base_url}/api/runs/run-001/checkpoints/sql_review/confirm",
            b"\xff\xfe\xfd",
        )

    assert malformed_status == 400
    assert malformed_body == {"status": "bad_request"}
    assert utf8_status == 400
    assert utf8_body == {"status": "bad_request"}


def test_confirmation_post_rejects_body_that_is_too_large(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_sql_review("SELECT department, amount FROM expenses", {"status": "pass"})

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        status, body = request_bytes(
            f"{server.base_url}/api/runs/run-001/checkpoints/sql_review/confirm",
            b'{"action":"' + ("同意查詢".encode("utf-8") * 20000) + b'"}',
        )

    assert status == 413
    assert body == {"status": "request_too_large"}


def test_current_checkpoint_page_returns_html_with_confirm_url(tmp_path: Path):
    harness = ReportHarness.create(tmp_path, run_id="run-001", prompt="查詢費用")
    harness.write_sql_review("SELECT department, amount FROM expenses", {"status": "pass"})

    with CheckpointCompanionServer.serve(tmp_path / "run-001") as server:
        with urlopen(f"{server.base_url}/runs/run-001/checkpoints/current", timeout=5) as response:
            html = response.read().decode("utf-8")
            content_type = response.headers["Content-Type"]

    assert response.status == 200
    assert content_type == "text/html; charset=utf-8"
    assert "SQL 查詢確認" in html
    assert "/api/runs/run-001/checkpoints/sql_review/confirm" in html
