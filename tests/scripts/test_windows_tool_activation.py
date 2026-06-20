from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_powershell_activation_sets_utf8_console_and_python_io() -> None:
    text = (REPO_ROOT / ".tools" / "activate.ps1").read_text(encoding="utf-8")

    assert "chcp 65001" in text
    assert "[Console]::InputEncoding" in text
    assert "[Console]::OutputEncoding" in text
    assert "$OutputEncoding" in text
    assert "PYTHONUTF8" in text
    assert "PYTHONIOENCODING" in text


def test_cmd_activation_sets_python_utf8_environment() -> None:
    text = (REPO_ROOT / ".tools" / "activate.cmd").read_text(encoding="utf-8")

    assert "PYTHONUTF8=1" in text
    assert "PYTHONIOENCODING=utf-8" in text
