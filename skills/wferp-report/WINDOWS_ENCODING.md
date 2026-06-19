# Windows Encoding Notes

All files in this skill package are stored as UTF-8 without BOM unless a file
format requires otherwise. `SKILL.md` and JSON files must stay UTF-8 without BOM
because skill loaders and JSON parsers may require the first byte to be `-`,
`{`, or `[`.

If Chinese text looks garbled on Windows, open the folder with an editor that
honors UTF-8:

- VS Code: this folder includes `.vscode/settings.json` with `files.encoding`
  set to `utf8`.
- Notepad++: choose `Encoding -> UTF-8`.
- Windows Terminal / PowerShell: use UTF-8 output, for example `chcp 65001`
  before using legacy console tools.

Do not convert these files to Big5, CP950, ANSI, or UTF-16. That will break the
Codex skill loader, JSON payload examples, and Python validation scripts.

