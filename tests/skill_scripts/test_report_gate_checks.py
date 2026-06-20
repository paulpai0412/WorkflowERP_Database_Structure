from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from skill_scripts.report_gate_checks import evaluate_delivery_artifacts
from skill_scripts.report_gate_checks import load_json_no_bom
from skill_scripts.report_gate_checks import scan_run_text_artifacts
from skill_scripts.report_gate_checks import scan_text_readability


def _case_dir(name: str) -> Path:
    path = Path("tests") / ".tmp" / f"{name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_readability_scan_rejects_repeated_question_marks_and_mojibake() -> None:
    result = scan_text_readability("報表標題 ???? 閮")

    assert result["valid"] is False
    assert "repeated_question_marks" in result["errors"]
    assert "mojibake_marker" in result["errors"]


def test_run_text_artifact_scan_covers_checkpoint_plan_data_and_state_json() -> None:
    run_dir = _case_dir("run-readability") / "run"
    for relative_path, text in {
        "checkpoints/01b_field_formula_classification.json": '{"label": "????"}',
        "plan/source-to-output-matrix.json": '[{"column": "Excel??"}]',
        "data/excel-workbook-preview.json": '{"status": "ok"}',
        "state.json": '{"status": "ok"}',
    }.items():
        path = run_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    result = scan_run_text_artifacts(run_dir)

    assert result["valid"] is False
    assert "checkpoints/01b_field_formula_classification.json:repeated_question_marks" in result["errors"]
    assert "plan/source-to-output-matrix.json:repeated_question_marks" in result["errors"]


def test_cli_check_run_text_artifacts_blocks_unreadable_run_payload() -> None:
    run_dir = _case_dir("cli-run-readability") / "run"
    checkpoint_path = run_dir / "checkpoints" / "01b_field_formula_classification.json"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text('{"label": "????"}', encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_scripts.cli_report_harness",
            "check-run-text-artifacts",
            "--run-dir",
            str(run_dir),
        ],
        capture_output=True,
        check=False,
        encoding="utf-8",
    )

    assert completed.returncode == 2
    assert "repeated_question_marks" in completed.stdout


def test_load_json_no_bom_rejects_utf8_bom() -> None:
    path = _case_dir("bom") / "validator.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"status": "pass"}).encode("utf-8"))

    result = load_json_no_bom(path)

    assert result["valid"] is False
    assert result["error"] == "utf8_bom"


def test_delivery_artifact_gate_blocks_hash_mismatch_and_missing_validator() -> None:
    run_dir = _case_dir("blocked") / "run"
    delivery_dir = run_dir / "report" / "delivery"
    validators_dir = run_dir / "review" / "validators"
    delivery_dir.mkdir(parents=True)
    validators_dir.mkdir(parents=True)
    html_path = delivery_dir / "report.html"
    html_path.write_text(
        "<!doctype html><html><body>訂單專案即時分析管理報表"
        "<script type=\"application/json\" id=\"__WFERP_REPORT_PACKAGE__\">e30=</script>"
        "</body></html>",
        encoding="utf-8",
    )
    (delivery_dir / "manifest.json").write_text(
        json.dumps(
            {
                "html_path": "report/delivery/report.html",
                "sha256": "not-the-real-hash",
                "single_file": True,
                "network_dependencies": 0,
            }
        ),
        encoding="utf-8",
    )
    (validators_dir / "report-content.json").write_text(
        json.dumps(
            {
                "role": "report_content_reviewer",
                "status": "pass",
                "required_fixes": [],
            }
        ),
        encoding="utf-8",
    )

    result = evaluate_delivery_artifacts(
        run_dir,
        required_validators=["report_content_reviewer", "visual_taste_reviewer"],
    )

    assert result["allowed"] is False
    assert "manifest_hash_mismatch" in result["blocking_reasons"]
    assert "missing_validator:visual_taste_reviewer" in result["blocking_reasons"]


def test_delivery_artifact_gate_allows_complete_delivery() -> None:
    run_dir = _case_dir("complete") / "run"
    delivery_dir = run_dir / "report" / "delivery"
    validators_dir = run_dir / "review" / "validators"
    delivery_dir.mkdir(parents=True)
    validators_dir.mkdir(parents=True)
    html_path = delivery_dir / "report.html"
    html_text = (
        "<!doctype html><html><body>訂單專案即時分析管理報表 A15-003 150331006 "
        "<script type=\"application/json\" id=\"__WFERP_REPORT_PACKAGE__\">e30=</script>"
        "</body></html>"
    )
    html_path.write_text(html_text, encoding="utf-8")
    (delivery_dir / "manifest.json").write_text(
        json.dumps(
            {
                "html_path": "report/delivery/report.html",
                "sha256": hashlib.sha256(html_text.encode("utf-8")).hexdigest(),
                "single_file": True,
                "network_dependencies": 0,
            }
        ),
        encoding="utf-8",
    )
    for role in ("report_content_reviewer", "visual_taste_reviewer"):
        (validators_dir / f"{role}.json").write_text(
            json.dumps({"role": role, "status": "warning", "required_fixes": []}),
            encoding="utf-8",
        )

    result = evaluate_delivery_artifacts(
        run_dir,
        required_validators=["report_content_reviewer", "visual_taste_reviewer"],
    )

    assert result["allowed"] is True
    assert result["blocking_reasons"] == []


def test_cli_check_delivery_artifacts_returns_success_for_complete_delivery() -> None:
    run_dir = _case_dir("cli-complete") / "run"
    delivery_dir = run_dir / "report" / "delivery"
    validators_dir = run_dir / "review" / "validators"
    delivery_dir.mkdir(parents=True)
    validators_dir.mkdir(parents=True)
    html_path = delivery_dir / "report.html"
    html_text = (
        "<!doctype html><html><body>訂單專案即時分析管理報表 A15-003 150331006 "
        "<script type=\"application/json\" id=\"__WFERP_REPORT_PACKAGE__\">e30=</script>"
        "</body></html>"
    )
    html_path.write_text(html_text, encoding="utf-8")
    (delivery_dir / "manifest.json").write_text(
        json.dumps(
            {
                "html_path": "report/delivery/report.html",
                "sha256": hashlib.sha256(html_text.encode("utf-8")).hexdigest(),
                "single_file": True,
                "network_dependencies": 0,
            }
        ),
        encoding="utf-8",
    )
    (validators_dir / "report-content.json").write_text(
        json.dumps(
            {
                "role": "report_content_reviewer",
                "status": "pass",
                "required_fixes": [],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_scripts.cli_report_harness",
            "check-delivery-artifacts",
            "--run-dir",
            str(run_dir),
            "--required-validator",
            "report_content_reviewer",
        ],
        capture_output=True,
        check=False,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    assert '"allowed": true' in completed.stdout
