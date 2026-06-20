from dataclasses import dataclass

from skill_scripts.dashboard_canvas import DashboardCanvas


@dataclass(frozen=True)
class DesignTemplate:
    template_id: str
    name: str
    description: str
    tokens: dict[str, str]

    def to_option_payload(self) -> dict[str, object]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "preview_tokens": {
                "background": self.tokens["background"],
                "surface": self.tokens["surface"],
                "accent": self.tokens["accent"],
            },
        }


@dataclass(frozen=True)
class DesignTemplateSelection:
    template_id: str
    name: str
    tokens: dict[str, str]

    def to_payload(self) -> dict[str, object]:
        return {"template_id": self.template_id, "name": self.name, "tokens": dict(self.tokens)}


_TEMPLATES = (
    DesignTemplate(
        template_id="executive_contrast",
        name="Executive Contrast",
        description="High-contrast dashboard styling for dense operational reviews.",
        tokens={"background": "#0f172a", "surface": "#1e293b", "accent": "#38bdf8", "text": "#f8fafc"},
    ),
    DesignTemplate(
        template_id="soft_operations",
        name="Soft Operations",
        description="Light, spacious dashboard styling for day-to-day process monitoring.",
        tokens={"background": "#f8fafc", "surface": "#ffffff", "accent": "#2563eb", "text": "#0f172a"},
    ),
    DesignTemplate(
        template_id="ledger_focus",
        name="Ledger Focus",
        description="Structured dashboard styling for finance and tabular control views.",
        tokens={"background": "#f5f1e8", "surface": "#fffaf0", "accent": "#b45309", "text": "#292524"},
    ),
)


def list_design_template_options() -> dict[str, object]:
    return {"templates": [template.to_option_payload() for template in _TEMPLATES]}


def select_design_template(template_id: str, current_selection: DesignTemplateSelection | None = None) -> DesignTemplateSelection:
    _ = current_selection
    template = _template_by_id(template_id)
    return DesignTemplateSelection(template_id=template.template_id, name=template.name, tokens=dict(template.tokens))


def apply_design_template_to_canvas_preview(canvas: DashboardCanvas, selection: object) -> dict[str, object]:
    if not isinstance(selection, DesignTemplateSelection):
        raise RuntimeError("DESIGN_TEMPLATE_SELECTION_REQUIRED")
    template = _template_by_id(selection.template_id)
    canonical_selection = DesignTemplateSelection(template_id=template.template_id, name=template.name, tokens=dict(template.tokens))
    return {"template": canonical_selection.to_payload(), "canvas": canvas.to_payload()}


def _template_by_id(template_id: str) -> DesignTemplate:
    normalized_id = str(template_id or "").strip()
    for template in _TEMPLATES:
        if template.template_id == normalized_id:
            return template
    raise RuntimeError(f"DESIGN_TEMPLATE_NOT_ALLOWED:{template_id}")
