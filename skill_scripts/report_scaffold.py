from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any


def _slug_to_component_name(slug: str, index: int) -> str:
    words = re.findall(r"[A-Za-z0-9]+", slug)
    if not words:
        words = ["section", str(index)]
    return "".join(word[:1].upper() + word[1:] for word in words) + "Section"


def _safe_slug(section: str, index: int) -> str:
    slug = section.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or f"section-{index:02d}"


def _copy_template(template_dir: Path, run_dir: Path) -> None:
    if not template_dir.exists() or not template_dir.is_dir():
        raise FileNotFoundError(f"Report scaffold template not found: {template_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template_dir, run_dir, dirs_exist_ok=True)


def _write_payload(run_dir: Path, payload: dict[str, Any]) -> None:
    payload_dir = run_dir / "report" / "payload"
    payload_dir.mkdir(parents=True, exist_ok=True)
    approved_query_result = payload.get("approved_query_result", payload)
    (payload_dir / "approved-query-result.json").write_text(
        json.dumps(approved_query_result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _create_section_files(run_dir: Path, sections: list[str]) -> list[dict[str, str]]:
    sections_dir = run_dir / "report" / "sections"
    sections_dir.mkdir(parents=True, exist_ok=True)
    generated: list[dict[str, str]] = []
    for index, section in enumerate(sections, start=1):
        slug = _safe_slug(section, index)
        component_name = _slug_to_component_name(slug, index)
        filename = f"{index:02d}-{slug}.tsx"
        (sections_dir / filename).write_text(
            "\n".join(
                [
                    "import React from \"react\";",
                    "",
                    f"export function {component_name}() {{",
                    "  return (",
                    f"    <section data-section=\"{slug}\">",
                    f"      <h2>{section}</h2>",
                    "    </section>",
                    "  );",
                    "}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        generated.append(
            {
                "component": component_name,
                "filename": filename,
                "import_path": f"./sections/{filename.removesuffix('.tsx')}",
            }
        )
    return generated


def _write_report_entry(run_dir: Path, generated_sections: list[dict[str, str]]) -> None:
    report_path = run_dir / "report" / "Report.tsx"
    imports = "\n".join(
        f'import {{ {section["component"]} }} from "{section["import_path"]}";'
        for section in generated_sections
    )
    rendered = "\n".join(
        f"        <{section['component']} key=\"{section['component']}\" />"
        for section in generated_sections
    )
    report_path.write_text(
        "\n".join(
            [
                "import React from \"react\";",
                'import approvedQueryResult from "./payload/approved-query-result.json";',
                imports,
                "",
                "export default function Report() {",
                "  return (",
                "    <main>",
                "      <h1>WFERP 報告</h1>",
                "      <pre data-payload=\"approved-query-result\">",
                "        {JSON.stringify(approvedQueryResult, null, 2)}",
                "      </pre>",
                rendered,
                "    </main>",
                "  );",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def validate_report_protocol(run_dir: Path) -> None:
    report_path = run_dir / "report" / "Report.tsx"
    if not report_path.exists():
        raise ValueError(f"Report.tsx missing: {report_path}")

    report_text = report_path.read_text(encoding="utf-8")
    section_files = sorted((run_dir / "report" / "sections").glob("*.tsx"))
    if not section_files:
        raise ValueError("Report scaffold must contain at least one generated section file")

    for section_path in section_files:
        import_reference = f"./sections/{section_path.stem}"
        if import_reference not in report_text and section_path.stem not in report_text:
            raise ValueError(f"Report.tsx does not reference generated section: {section_path.name}")

        section_text = section_path.read_text(encoding="utf-8")
        exports = re.findall(r"export function [A-Za-z][A-Za-z0-9]*\(", section_text)
        if len(exports) != 1:
            raise ValueError(f"Section must export one React component: {section_path}")

    raw_blocks_dir = run_dir / "report" / "raw-blocks"
    if not raw_blocks_dir.exists() or not raw_blocks_dir.is_dir():
        raise ValueError(f"raw-blocks directory missing: {raw_blocks_dir}")

    payload_path = run_dir / "report" / "payload" / "approved-query-result.json"
    if not payload_path.exists():
        raise ValueError(f"approved query result payload missing: {payload_path}")


def scaffold_report_workspace(
    run_dir: Path,
    template_dir: Path,
    sections: list[str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not sections:
        raise ValueError("At least one report section is required")

    _copy_template(template_dir, run_dir)
    _write_payload(run_dir, payload)
    generated_sections = _create_section_files(run_dir, sections)
    _write_report_entry(run_dir, generated_sections)
    validate_report_protocol(run_dir)
    return {"section_count": len(sections), "run_dir": str(run_dir)}
