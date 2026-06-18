from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any


def _slug_to_component_name(slug: str, index: int) -> str:
    words = re.findall(r"[A-Za-z0-9]+", slug)
    if not words or slug == f"section-{index:02d}":
        words = ["section"]
    base = "".join(word[:1].upper() + word[1:] for word in words)
    return f"{base}{index:02d}Section"


def _safe_slug(section: str, index: int) -> str:
    slug = section.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or f"section-{index:02d}"


def _protected_outputs(run_dir: Path) -> list[Path]:
    report_dir = run_dir / "report"
    candidates = [
        report_dir / "Report.tsx",
        report_dir / "payload" / "approved-query-result.json",
        report_dir / "payload" / "report-context.json",
    ]
    candidates.extend(sorted((report_dir / "sections").glob("*.tsx")))
    return [path for path in candidates if path.exists()]


def _ensure_can_write(run_dir: Path, force: bool) -> None:
    if force:
        return
    existing = _protected_outputs(run_dir)
    if existing:
        relative = existing[0].relative_to(run_dir)
        raise FileExistsError(
            f"Refusing to scaffold into existing report workspace without force: {relative}"
        )


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
    (payload_dir / "report-context.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
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


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Payload JSON is not loadable: {path}") from exc


def _section_export(section_path: Path) -> str:
    section_text = section_path.read_text(encoding="utf-8")
    exports = re.findall(r"export\s+function\s+([A-Za-z][A-Za-z0-9]*)\s*\(", section_text)
    if len(exports) != 1:
        raise ValueError(f"Section must export one React component: {section_path}")
    return exports[0]


def _report_section_imports(report_text: str) -> dict[str, str]:
    imports: dict[str, str] = {}
    pattern = re.compile(
        r'import\s+\{\s*([A-Za-z][A-Za-z0-9]*)\s*\}\s+from\s+["\']\.\/sections\/([^"\']+)["\']'
    )
    for component, section_stem in pattern.findall(report_text):
        if component in imports:
            raise ValueError(f"Report.tsx imports duplicate component identifier: {component}")
        imports[component] = section_stem
    return imports


def _rendered_components(report_text: str) -> list[str]:
    names = re.findall(r"<([A-Z][A-Za-z0-9]*)\b", report_text)
    return [name for name in names if name not in {"React"}]


def validate_report_protocol(run_dir: Path) -> None:
    report_path = run_dir / "report" / "Report.tsx"
    if not report_path.exists():
        raise ValueError(f"Report.tsx missing: {report_path}")

    report_text = report_path.read_text(encoding="utf-8")
    section_files = sorted((run_dir / "report" / "sections").glob("*.tsx"))
    if not section_files:
        raise ValueError("Report scaffold must contain at least one generated section file")

    expected_by_stem: dict[str, str] = {}
    for section_path in section_files:
        expected_by_stem[section_path.stem] = _section_export(section_path)

    exported_components = list(expected_by_stem.values())
    if len(set(exported_components)) != len(exported_components):
        raise ValueError("Section component identifiers must be unique")

    imports = _report_section_imports(report_text)
    imported_by_stem = {section_stem: component for component, section_stem in imports.items()}
    if set(imported_by_stem) != set(expected_by_stem):
        raise ValueError("Report.tsx section imports do not exactly match generated section files")
    for section_stem, exported_component in expected_by_stem.items():
        imported_component = imported_by_stem[section_stem]
        if imported_component != exported_component:
            raise ValueError(
                f"Report.tsx imports {imported_component} but {section_stem} exports {exported_component}"
            )

    rendered = _rendered_components(report_text)
    if sorted(rendered) != sorted(exported_components):
        raise ValueError("Report.tsx render linkage does not exactly match generated sections")

    raw_blocks_dir = run_dir / "report" / "raw-blocks"
    if not raw_blocks_dir.exists() or not raw_blocks_dir.is_dir():
        raise ValueError(f"raw-blocks directory missing: {raw_blocks_dir}")

    payload_path = run_dir / "report" / "payload" / "approved-query-result.json"
    if not payload_path.exists():
        raise ValueError(f"approved query result payload missing: {payload_path}")
    _read_json(payload_path)

    context_path = run_dir / "report" / "payload" / "report-context.json"
    if not context_path.exists():
        raise ValueError(f"report context payload missing: {context_path}")
    _read_json(context_path)


def scaffold_report_workspace(
    run_dir: Path,
    template_dir: Path,
    sections: list[str],
    payload: dict[str, Any],
    *,
    force: bool = False,
) -> dict[str, Any]:
    if not sections:
        raise ValueError("At least one report section is required")

    _ensure_can_write(run_dir, force)
    _copy_template(template_dir, run_dir)
    _write_payload(run_dir, payload)
    generated_sections = _create_section_files(run_dir, sections)
    _write_report_entry(run_dir, generated_sections)
    validate_report_protocol(run_dir)
    return {"section_count": len(sections), "run_dir": str(run_dir)}
