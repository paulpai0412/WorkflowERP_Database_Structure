from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _lookup_sheet(formula: str) -> str:
    match = re.search(
        r"VLOOKUP\s*\([^,]+,\s*(?:'([^']+)'|([^!,]+))!",
        formula,
        re.IGNORECASE,
    )
    if not match:
        return ""
    return (match.group(1) or match.group(2) or "").strip()


def classify_workbook(
    workbook_path: str | Path,
    *,
    source_dir: str | Path,
    primary_sheet: str = "",
) -> dict[str, Any]:
    raise RuntimeError("RULE_FALLBACK_REMOVED_USE_LLM_TABLE_FIRST_CLASSIFIER")
