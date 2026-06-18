from __future__ import annotations

import re
from pathlib import Path

NETWORK_PATTERN = re.compile(r"""(?:src|href)=["'](https?://[^"']+)["']""", re.IGNORECASE)
SCRIPT_SRC_PATTERN = re.compile(r"""<script\b[^>]*\bsrc\s*=""", re.IGNORECASE)
LINK_HREF_PATTERN = re.compile(r"""<link\b[^>]*\bhref\s*=""", re.IGNORECASE)


def validate_single_html_static(path: str | Path) -> dict[str, object]:
    html = Path(path).read_text(encoding="utf-8")
    lowered = html.lower()
    errors: list[str] = []
    network_references = NETWORK_PATTERN.findall(html)

    if SCRIPT_SRC_PATTERN.search(html):
        errors.append("external_script")
    if LINK_HREF_PATTERN.search(html):
        errors.append("external_stylesheet")
    if "fetch(" in html:
        errors.append("network_fetch")
    if "websocket" in lowered:
        errors.append("websocket")
    if any(token in lowered for token in ("password", "connection_string", "credential")):
        errors.append("credentials")
    if "__WFERP_REPORT_PACKAGE__" not in html:
        errors.append("missing_package")

    return {
        "valid": not errors,
        "errors": errors,
        "network_references": network_references,
    }
