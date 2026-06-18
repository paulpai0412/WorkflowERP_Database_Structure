from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


QUARANTINE_DIR = "legacy_static_docs"
REASON = "legacy_static_html_artifacts_quarantine"
LEGACY_PATHS = [
    "index.html",
    "df_style.css",
    "HTML",
    "_Source/3_CreateIndexHtml.py",
    "_Source/4_CreateTableStructureHtml.py",
    "_Source/5_CreateTableStructureSQL.py",
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Move legacy static WFERP HTML documentation artifacts into quarantine."
    )
    parser.add_argument("--repo-root", required=True, help="Path to the WFERP repository root.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned moves without changing files.")
    return parser.parse_args(argv)


def relative_path(path: str) -> str:
    return Path(path).as_posix()


def build_entry(repo_root: Path, relative_source: str, moved_at: str) -> dict[str, str]:
    source = repo_root / relative_source
    destination_relative = f"{QUARANTINE_DIR}/{relative_source}"
    destination = repo_root / destination_relative

    if source.exists():
        status = "pending"
    elif destination.exists():
        status = "already_quarantined"
    else:
        status = "missing"

    return {
        "source": relative_path(relative_source),
        "destination": relative_path(destination_relative),
        "status": status,
        "reason": REASON,
        "moved_at": moved_at,
    }


def plan_quarantine(repo_root: Path, moved_at: str) -> list[dict[str, str]]:
    return [build_entry(repo_root, relative_source, moved_at) for relative_source in LEGACY_PATHS]


def print_entries(entries: Sequence[dict[str, str]], *, dry_run: bool) -> None:
    for entry in entries:
        status = "would_move" if dry_run and entry["status"] == "pending" else entry["status"]
        print(f"{status} {entry['source']} -> {entry['destination']}")


def move_entries(repo_root: Path, entries: list[dict[str, str]]) -> list[dict[str, str]]:
    quarantine_root = repo_root / QUARANTINE_DIR
    quarantine_root.mkdir(parents=True, exist_ok=True)

    moved_entries: list[dict[str, str]] = []
    for entry in entries:
        source = repo_root / entry["source"]
        destination = repo_root / entry["destination"]

        if entry["status"] != "pending":
            moved_entries.append(entry)
            continue

        if destination.exists():
            moved_entries.append({**entry, "status": "destination_exists"})
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        moved_entries.append({**entry, "status": "moved"})

    return moved_entries


def write_manifest(repo_root: Path, entries: Sequence[dict[str, str]], moved_at: str) -> None:
    manifest = {
        "reason": REASON,
        "moved_at": moved_at,
        "entries": list(entries),
    }
    manifest_path = repo_root / QUARANTINE_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    moved_at = datetime.now(timezone.utc).isoformat()
    entries = plan_quarantine(repo_root, moved_at)

    if args.dry_run:
        print_entries(entries, dry_run=True)
        return 0

    moved_entries = move_entries(repo_root, entries)
    write_manifest(repo_root, moved_entries, moved_at)
    print_entries(moved_entries, dry_run=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
