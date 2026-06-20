from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile
from typing import Any


class ExcelWorkbookExportError(RuntimeError):
    pass


def _runtime_root() -> Path:
    return Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies"


def _node_executable() -> str:
    found = shutil.which("node")
    if found:
        return found
    bundled = _runtime_root() / "node" / "bin" / "node.exe"
    if bundled.exists():
        return str(bundled)
    raise ExcelWorkbookExportError("Node.js runtime was not found")


def _node_modules_source() -> Path:
    configured = os.getenv("WFERP_NODE_MODULES")
    if configured:
        path = Path(configured)
        if path.exists():
            return path
    bundled = _runtime_root() / "node" / "node_modules"
    if bundled.exists():
        return bundled
    raise ExcelWorkbookExportError("Bundled node_modules was not found")


def _artifact_tool_module() -> Path:
    module_path = _node_modules_source() / "@oai" / "artifact-tool" / "dist" / "artifact_tool.mjs"
    if module_path.exists():
        return module_path
    raise ExcelWorkbookExportError("artifact-tool module was not found")


def _prepare_node_workdir(work_dir: Path) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    builder_source = Path(__file__).with_name("excel_workbook_exporter.mjs")
    builder_target = work_dir / "excel_workbook_exporter.mjs"
    shutil.copy2(builder_source, builder_target)
    return builder_target


def _verify_xlsx(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
    return {
        "xlsx_contains_workbook_xml": "xl/workbook.xml" in names,
        "xlsx_contains_shared_strings": "xl/sharedStrings.xml" in names,
        "xlsx_file_count": len(names),
    }


def export_workbook(
    payload: dict[str, Any],
    output_path: str | Path,
    *,
    evidence_path: str | Path | None = None,
) -> dict[str, Any]:
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence = (Path(evidence_path) if evidence_path else output.with_suffix(".evidence.json")).resolve()
    evidence.parent.mkdir(parents=True, exist_ok=True)
    work_dir = evidence.parent / ".excel-workbook-exporter"
    builder = _prepare_node_workdir(work_dir)
    payload_path = work_dir / "payload.json"
    result_path = work_dir / "result.json"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    env = dict(os.environ)
    env["WFERP_ARTIFACT_TOOL_MODULE"] = str(_artifact_tool_module())
    completed = subprocess.run(
        [_node_executable(), str(builder), str(payload_path), str(output), str(evidence), str(result_path)],
        cwd=work_dir,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if completed.returncode != 0:
        message = (completed.stderr or "").strip() or (completed.stdout or "").strip() or "Excel workbook export failed"
        raise ExcelWorkbookExportError(message)
    if not result_path.exists():
        raise ExcelWorkbookExportError("Excel workbook exporter did not write a result file")

    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ExcelWorkbookExportError("Excel workbook exporter result must be an object")
    verification = dict(result.get("verification") or {})
    verification.update(_verify_xlsx(output))
    result["verification"] = verification
    evidence.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
