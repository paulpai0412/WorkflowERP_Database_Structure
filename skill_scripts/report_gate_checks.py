from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


MOJIBAKE_MARKERS = (
    "�",
    "雿",
    "閮",
    "蝞",
    "鞎",
    "撌",
    "銝",
    "瘙",
    "摰",
)


def scan_text_readability(text: str) -> dict[str, Any]:
    errors: list[str] = []
    if "????" in text:
        errors.append("repeated_question_marks")
    if any(marker in text for marker in MOJIBAKE_MARKERS):
        errors.append("mojibake_marker")
    return {"valid": not errors, "errors": errors}


def load_json_no_bom(path: str | Path) -> dict[str, Any]:
    json_path = Path(path)
    raw = json_path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return {"valid": False, "error": "utf8_bom", "path": str(json_path)}
    try:
        text = raw.decode("utf-8")
        payload = json.loads(text)
    except UnicodeDecodeError:
        return {"valid": False, "error": "utf8_decode", "path": str(json_path)}
    except json.JSONDecodeError as exc:
        return {
            "valid": False,
            "error": "invalid_json",
            "path": str(json_path),
            "message": str(exc),
        }
    if not isinstance(payload, dict):
        return {"valid": False, "error": "json_not_object", "path": str(json_path)}
    readability = scan_text_readability(text)
    return {
        "valid": readability["valid"],
        "error": None if readability["valid"] else "text_readability",
        "path": str(json_path),
        "payload": payload,
        "readability_errors": readability["errors"],
    }


def _relative_or_absolute(base: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return base / candidate


def _forbidden_delivery_patterns(text: str) -> list[str]:
    patterns = {
        "external_script": r"<script\b[^>]*\bsrc\s*=",
        "external_stylesheet": r"<link\b[^>]*\bhref\s*=",
        "network_fetch": r"\bfetch\s*\(",
        "websocket": r"websocket",
        "http_reference": r"https?://",
        "credential_text": r"password|credential|connection_string|Integrated Security|Initial Catalog|User ID|Data Source",
    }
    return [
        name
        for name, pattern in patterns.items()
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]


def _validator_payloads(run_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    validator_dir = run_dir / "review" / "validators"
    if not validator_dir.exists():
        return [], ["missing_validators_dir"]
    payloads: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in sorted(validator_dir.glob("*.json")):
        result = load_json_no_bom(path)
        if not result["valid"]:
            errors.append(f"invalid_validator_json:{path.name}:{result['error']}")
            continue
        payloads.append(result["payload"])
    return payloads, errors


def evaluate_delivery_artifacts(
    run_dir: str | Path,
    *,
    required_validators: list[str] | None = None,
) -> dict[str, Any]:
    run_path = Path(run_dir)
    blocking: list[str] = []
    evidence: list[str] = []

    manifest_path = run_path / "report" / "delivery" / "manifest.json"
    manifest_result = load_json_no_bom(manifest_path) if manifest_path.exists() else {
        "valid": False,
        "error": "missing_manifest",
    }
    if not manifest_result["valid"]:
        blocking.append(str(manifest_result["error"]))
        return {"allowed": False, "blocking_reasons": blocking, "evidence": evidence}

    manifest = manifest_result["payload"]
    html_value = str(manifest.get("html_path") or "report/delivery/report.html")
    html_path = _relative_or_absolute(run_path, html_value)
    if not html_path.exists():
        blocking.append("missing_html")
    else:
        html_text = html_path.read_text(encoding="utf-8")
        html_sha = hashlib.sha256(html_text.encode("utf-8")).hexdigest()
        expected_sha = str(manifest.get("sha256") or manifest.get("html_sha256") or "")
        if expected_sha and html_sha != expected_sha:
            blocking.append("manifest_hash_mismatch")
        readability = scan_text_readability(html_text)
        if not readability["valid"]:
            blocking.extend(f"html_{error}" for error in readability["errors"])
        if "__WFERP_REPORT_PACKAGE__" not in html_text:
            blocking.append("missing_embedded_package_marker")
        blocking.extend(_forbidden_delivery_patterns(html_text))
        evidence.append(f"html_sha256:{html_sha}")

    if manifest.get("single_file") is not True:
        blocking.append("manifest_single_file_not_true")
    if manifest.get("network_dependencies", 0) not in {0, "0"}:
        blocking.append("manifest_network_dependencies_nonzero")

    validator_payloads, validator_errors = _validator_payloads(run_path)
    blocking.extend(validator_errors)
    validators_by_role = {
        str(payload.get("role")): payload
        for payload in validator_payloads
        if payload.get("role")
    }
    for role in required_validators or []:
        if role not in validators_by_role:
            blocking.append(f"missing_validator:{role}")
            continue
        fixes = validators_by_role[role].get("required_fixes")
        if fixes is None:
            fixes = validators_by_role[role].get("requiredFixes")
        if fixes:
            blocking.append(f"validator_required_fixes:{role}")

    return {
        "allowed": not blocking,
        "blocking_reasons": blocking,
        "evidence": evidence,
        "validator_count": len(validator_payloads),
    }
