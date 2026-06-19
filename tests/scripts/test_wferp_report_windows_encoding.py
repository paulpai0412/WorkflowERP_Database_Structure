from __future__ import annotations

import json
from pathlib import Path


SKILL_ROOT = Path("skills/wferp-report")


def test_wferp_report_skill_files_are_utf8_decodable() -> None:
    for path in SKILL_ROOT.rglob("*"):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        path.read_text(encoding="utf-8")


def test_parser_sensitive_files_do_not_use_utf8_bom() -> None:
    parser_sensitive = [SKILL_ROOT / "SKILL.md", *SKILL_ROOT.rglob("*.json")]

    for path in parser_sensitive:
        assert not path.read_bytes().startswith(b"\xef\xbb\xbf"), f"{path} must not start with UTF-8 BOM"


def test_windows_editor_settings_force_utf8_for_skill_folder() -> None:
    editorconfig = (SKILL_ROOT / ".editorconfig").read_text(encoding="utf-8")
    vscode_settings = json.loads((SKILL_ROOT / ".vscode" / "settings.json").read_text(encoding="utf-8"))

    assert "charset = utf-8" in editorconfig
    assert vscode_settings["files.encoding"] == "utf8"
    assert vscode_settings["files.autoGuessEncoding"] is False
