from __future__ import annotations

from pathlib import Path

from skill_scripts.html_self_validator import validate_single_html_static


def test_static_validator_accepts_self_contained_html(tmp_path: Path):
    html = tmp_path / "report.html"
    html.write_text(
        """<!doctype html><html><head><style>body{}</style></head><body>
        <h1>費用分析</h1>
        <script>window.__WFERP_REPORT_PACKAGE__="abc";</script>
        </body></html>""",
        encoding="utf-8",
    )

    result = validate_single_html_static(html)

    assert result == {"valid": True, "errors": [], "network_references": []}


def test_static_validator_rejects_external_network_and_credentials(tmp_path: Path):
    html = tmp_path / "report.html"
    html.write_text(
        """<!doctype html><html><head>
        <script src="https://cdn.example/app.js"></script>
        </head><body>password=secret</body></html>""",
        encoding="utf-8",
    )

    result = validate_single_html_static(html)

    assert result["valid"] is False
    assert "external_script" in result["errors"]
    assert "credentials" in result["errors"]
    assert result["network_references"] == ["https://cdn.example/app.js"]


def test_static_validator_rejects_fetch_websocket_link_and_missing_package(tmp_path: Path):
    html = tmp_path / "report.html"
    html.write_text(
        """<!doctype html><html><head>
        <link rel="stylesheet" href="https://cdn.example/app.css">
        </head><body><script>fetch('/api/report'); const ws = new WebSocket('ws://x');</script></body></html>""",
        encoding="utf-8",
    )

    result = validate_single_html_static(html)

    assert result["valid"] is False
    assert "external_stylesheet" in result["errors"]
    assert "network_fetch" in result["errors"]
    assert "websocket" in result["errors"]
    assert "missing_package" in result["errors"]
    assert result["network_references"] == ["https://cdn.example/app.css"]


def test_static_validator_rejects_external_script_and_link_attribute_order_variants(
    tmp_path: Path,
):
    html = tmp_path / "report.html"
    html.write_text(
        """<!doctype html><html><head>
        <script type="module" src="https://cdn.example/app.js"></script>
        <link href="https://cdn.example/app.css" rel="stylesheet">
        </head><body><script>window.__WFERP_REPORT_PACKAGE__="abc";</script></body></html>""",
        encoding="utf-8",
    )

    result = validate_single_html_static(html)

    assert result["valid"] is False
    assert "external_script" in result["errors"]
    assert "external_stylesheet" in result["errors"]
    assert result["network_references"] == [
        "https://cdn.example/app.js",
        "https://cdn.example/app.css",
    ]
