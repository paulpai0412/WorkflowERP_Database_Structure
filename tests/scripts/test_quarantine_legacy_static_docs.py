from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts/quarantine_legacy_static_docs.py"

LEGACY_PATHS = [
    "index.html",
    "df_style.css",
    "HTML/table.html",
    "_Source/3_CreateIndexHtml.py",
    "_Source/4_CreateTableStructureHtml.py",
    "_Source/5_CreateTableStructureSQL.py",
]

PROTECTED_PATHS = [
    "_Source/1_mssql_to_json.py",
    "_Source/2_FieldNameConvert2utf8.py",
    "_Source/TableName.json",
    "skill_scripts/cli_generate_select.py",
]


def write(path: Path, text: str = "fixture") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(text, encoding="utf-8")


def make_fake_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    for relative_path in LEGACY_PATHS:
        write(repo_root / relative_path, f"legacy:{relative_path}")
    for relative_path in PROTECTED_PATHS:
        write(repo_root / relative_path, f"protected:{relative_path}")
    return repo_root


def run_quarantine(repo_root: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--repo-root", str(repo_root), *extra_args],
        check=False,
        text=True,
        capture_output=True,
    )


def test_quarantine_dry_run_lists_expected_paths(tmp_path: Path):
    repo_root = make_fake_repo(tmp_path)

    result = run_quarantine(repo_root, "--dry-run")

    assert result.returncode == 0, result.stderr
    for relative_path in [
        "index.html",
        "df_style.css",
        "HTML",
        "_Source/3_CreateIndexHtml.py",
        "_Source/4_CreateTableStructureHtml.py",
        "_Source/5_CreateTableStructureSQL.py",
    ]:
        assert f"would_move {relative_path} -> legacy_static_docs/{relative_path}" in result.stdout
        assert (repo_root / relative_path).exists()
    assert not (repo_root / "legacy_static_docs").exists()


def test_quarantine_moves_expected_paths_and_writes_manifest(tmp_path: Path):
    repo_root = make_fake_repo(tmp_path)

    result = run_quarantine(repo_root)

    assert result.returncode == 0, result.stderr
    for relative_path in [
        "index.html",
        "df_style.css",
        "HTML/table.html",
        "_Source/3_CreateIndexHtml.py",
        "_Source/4_CreateTableStructureHtml.py",
        "_Source/5_CreateTableStructureSQL.py",
    ]:
        assert not (repo_root / relative_path).exists()
        assert (repo_root / "legacy_static_docs" / relative_path).exists()

    manifest = json.loads((repo_root / "legacy_static_docs/manifest.json").read_text(encoding="utf-8"))
    assert manifest["reason"] == "legacy_static_html_artifacts_quarantine"
    entries = {entry["source"]: entry for entry in manifest["entries"]}
    assert entries["index.html"]["destination"] == "legacy_static_docs/index.html"
    assert entries["index.html"]["status"] == "moved"
    assert entries["HTML"]["status"] == "moved"
    assert entries["_Source/3_CreateIndexHtml.py"]["moved_at"]


def test_quarantine_is_idempotent_when_sources_already_moved(tmp_path: Path):
    repo_root = make_fake_repo(tmp_path)
    first = run_quarantine(repo_root)
    assert first.returncode == 0, first.stderr

    second = run_quarantine(repo_root)

    assert second.returncode == 0, second.stderr
    manifest = json.loads((repo_root / "legacy_static_docs/manifest.json").read_text(encoding="utf-8"))
    statuses = {entry["source"]: entry["status"] for entry in manifest["entries"]}
    assert statuses["index.html"] == "already_quarantined"
    assert statuses["df_style.css"] == "already_quarantined"
    assert statuses["HTML"] == "already_quarantined"
    assert statuses["_Source/5_CreateTableStructureSQL.py"] == "already_quarantined"


def test_quarantine_never_moves_protected_paths(tmp_path: Path):
    repo_root = make_fake_repo(tmp_path)

    result = run_quarantine(repo_root)

    assert result.returncode == 0, result.stderr
    for relative_path in PROTECTED_PATHS:
        assert (repo_root / relative_path).exists()
        assert not (repo_root / "legacy_static_docs" / relative_path).exists()
