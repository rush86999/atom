"""Per-app canvas field registry — the single source of truth for how each
canvas app's content is shaped, which input fields it has, and how the
co-editor may edit it.

The canvas co-editor previously treated every canvas as "generic object or
text" with ONE hardcoded example (an email {to, cc, subject, body}). Real
apps differ structurally AND in their UI (frontend-nextjs/components/canvas/
CanvasPanel.tsx renders each component differently): an email is a composer
with To/Cc/Subject inputs plus a rich-text body, a sheet is an A1-addressable
grid, a form is a field list, a chart is a data array, and office canvases
are snapshots of REAL files on disk. Editing semantics must follow the app,
not the string.

Each app spec carries:

- ``content_kind``: how the content payload is shaped (``fields`` dict,
  plain ``text``, row ``grid``, free ``json``, or ``file_backed`` snapshot).
- ``fields``: for dict-shaped apps, the exact keys the UI renders as input
  fields — patch/merge operations are validated against these, so the
  planner cannot invent a field the UI will never display.
- ``edit_policy``: how apply should treat writes (``fields_patch`` merge,
  ``text`` replace, ``grid`` cell ops, ``json`` whole-payload, and
  ``file_backed`` — the file is authoritative, content writes are no-ops
  the user would never see, so they are refused with a pointer to the
  file instead).

Consumers: ``core.chat_canvas_editor`` (prompt section, op validation,
field-scoped merge, legacy-canvas healing) and the chat orchestrator's
failure replies. Frontend shapes mirrored here are defined in
CanvasPanel.tsx / canvasType.ts; keep the two in sync.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CanvasFieldSpec:
    """One input field of a dict-shaped canvas app, as the UI renders it."""
    name: str
    label: str
    # "line" = single-line input, "recipients" = email address list,
    # "text" = multiline plain text, "html" = rich-text body,
    # "json" = structured payload the UI renders specially.
    kind: str
    description: str = ""


@dataclass(frozen=True)
class CanvasAppSpec:
    """Everything the co-editor needs to know about ONE canvas app."""
    canvas_type: str
    label: str
    # fields | text | grid | json | file_backed
    content_kind: str
    edit_policy: str
    fields: tuple = dc_field(default=())
    edit_hint: str = ""


_EMAIL_FIELDS = (
    CanvasFieldSpec("to", "To", "recipients",
                    "comma-separated recipient email addresses (single-line input)"),
    CanvasFieldSpec("cc", "Cc", "recipients",
                    "comma-separated CC email addresses (single-line input)"),
    CanvasFieldSpec("subject", "Subject", "line",
                    "the email subject line (single-line input)"),
    CanvasFieldSpec("body", "Body", "html",
                    "the email body (rich-text editor, HTML allowed)"),
)

_FORM_FIELDS = (
    CanvasFieldSpec("title", "Title", "line", "the form's display title"),
    CanvasFieldSpec("fields", "Fields", "json",
                    "the form field definitions the interactive form renders"),
)

_CHART_FIELDS = (
    CanvasFieldSpec("title", "Title", "line", "the chart's display title"),
    CanvasFieldSpec("data", "Data", "json",
                    "the chart data: a list of {label, value} points"),
)

_APPS: Dict[str, CanvasAppSpec] = {
    "email": CanvasAppSpec(
        canvas_type="email", label="Email", content_kind="fields",
        edit_policy="fields_patch", fields=_EMAIL_FIELDS,
        edit_hint=(
            "An email composer: To/Cc/Subject are single-line recipient/subject "
            "inputs, the body is a rich-text editor. Filling the To/Cc fields is "
            "a normal edit (set-field ops or a field merge) — recipients shown in "
            "the body text are NOT the fields."
        ),
    ),
    "sheet": CanvasAppSpec(
        canvas_type="sheet", label="Sheet", content_kind="grid",
        edit_policy="grid",
        edit_hint=(
            "A spreadsheet grid addressed by A1 cell references; use cell ops, "
            "never freeform JSON."
        ),
    ),
    "document": CanvasAppSpec(
        canvas_type="document", label="Document", content_kind="text",
        edit_policy="text",
        edit_hint="A text document editor (markdown rendered in preview).",
    ),
    "markdown": CanvasAppSpec(
        canvas_type="markdown", label="Markdown", content_kind="text",
        edit_policy="text",
        edit_hint="A markdown editor with live preview.",
    ),
    "code": CanvasAppSpec(
        canvas_type="code", label="Code", content_kind="text",
        edit_policy="text",
        edit_hint="A code editor; preserve language/syntax exactly.",
    ),
    "terminal": CanvasAppSpec(
        canvas_type="terminal", label="Terminal", content_kind="text",
        edit_policy="text",
        edit_hint="A terminal-style text canvas.",
    ),
    "status_panel": CanvasAppSpec(
        canvas_type="status_panel", label="Status panel", content_kind="text",
        edit_policy="text",
        edit_hint="A status panel rendering the text as status content.",
    ),
    "form": CanvasAppSpec(
        canvas_type="form", label="Form", content_kind="fields",
        edit_policy="fields_patch", fields=_FORM_FIELDS,
        edit_hint=(
            "An interactive form; 'fields' is the structured field list the "
            "form renderer consumes — edit it as JSON, keeping the field schema."
        ),
    ),
    "line_chart": CanvasAppSpec(
        canvas_type="line_chart", label="Line chart", content_kind="json",
        edit_policy="json_replace", fields=_CHART_FIELDS,
        edit_hint="A line chart; content.data is the plotted point list.",
    ),
    "bar_chart": CanvasAppSpec(
        canvas_type="bar_chart", label="Bar chart", content_kind="json",
        edit_policy="json_replace", fields=_CHART_FIELDS,
        edit_hint="A bar chart; content.data is the plotted point list.",
    ),
    "pie_chart": CanvasAppSpec(
        canvas_type="pie_chart", label="Pie chart", content_kind="json",
        edit_policy="json_replace", fields=_CHART_FIELDS,
        edit_hint="A pie chart; content.data is the plotted point list.",
    ),
    "office_word": CanvasAppSpec(
        canvas_type="office_word", label="Word (docx)", content_kind="file_backed",
        edit_policy="file_backed",
        edit_hint=(
            "Backed by a REAL .docx file on disk — the file is the artifact; "
            "content is only a read snapshot."
        ),
    ),
    "office_excel": CanvasAppSpec(
        canvas_type="office_excel", label="Excel (xlsx)", content_kind="file_backed",
        edit_policy="file_backed",
        edit_hint=(
            "Backed by a REAL .xlsx file on disk — the file is the artifact; "
            "content is only a read snapshot."
        ),
    ),
    "office_pptx": CanvasAppSpec(
        canvas_type="office_pptx", label="PowerPoint (pptx)", content_kind="file_backed",
        edit_policy="file_backed",
        edit_hint=(
            "Backed by a REAL .pptx file on disk — the file is the artifact; "
            "content is only a read snapshot."
        ),
    ),
}

# Doc-like legacy aliases — same mapping vocabulary the frontend's
# normalizeCanvasComponent speaks (canvasType.ts) plus the audit-trail names.
_ALIASES = {
    "sheets": "sheet",
    "spreadsheet": "sheet",
    "docs": "document",
    "doc": "document",
    "generic": "markdown",
    "coding": "code",
    "office_doc": "office_word",
    "office_xlsx": "office_excel",
    "office_slides": "office_pptx",
}

_TEXT_FALLBACK = CanvasAppSpec(
    canvas_type="generic", label="Text", content_kind="text",
    edit_policy="text",
    edit_hint="A freeform text canvas rendered by its type when known.",
)


def normalize_app_type(canvas_type: Optional[str]) -> str:
    """Map legacy/registry type names onto the canonical app type."""
    raw = (canvas_type or "").strip().lower()
    return _ALIASES.get(raw, raw or "generic")


def get_app_spec(canvas_type: Optional[str]) -> CanvasAppSpec:
    """The app spec for a canvas type — never None (unknown types fall back
    to the text app so the editor stays usable for every canvas)."""
    canonical = normalize_app_type(canvas_type)
    return _APPS.get(canonical) or _TEXT_FALLBACK


def known_field_names(spec: CanvasAppSpec) -> frozenset:
    """Field names the UI actually renders as inputs for this app."""
    return frozenset(f.name for f in spec.fields)


def empty_fillable_fields(spec: CanvasAppSpec, content: Any) -> List[str]:
    """The app's input fields currently EMPTY on this canvas — the set-field
    / merge targets. Only dict-shaped apps have them; a field counts as
    empty when missing, None, or whitespace. Never claims a non-empty
    field (healing may only FILL, never overwrite)."""
    if spec.content_kind != "fields" or not isinstance(content, dict):
        return []
    empty: List[str] = []
    for f in spec.fields:
        value = content.get(f.name)
        if value is None or (isinstance(value, str) and not value.strip()):
            empty.append(f.name)
    return empty


def is_content_backed(spec: CanvasAppSpec) -> bool:
    """False for file-backed office canvases, where a content write would
    change nothing the user can see (the file is the artifact)."""
    return spec.content_kind != "file_backed"


def app_prompt_section(canvas_type: Optional[str], content: Any) -> str:
    """The planner-visible description of THIS canvas app: what its content
    shape is, the exact input fields it renders, and how edits should be
    expressed. Replaces the old single hardcoded email example so every app
    gets edit guidance matching its real UI."""
    spec = get_app_spec(canvas_type)
    lines = [
        f"CANVAS APP: {spec.label} (type \"{normalize_app_type(canvas_type)}\"). {spec.edit_hint}"
    ]
    if spec.content_kind == "fields" and spec.fields:
        empty = empty_fillable_fields(spec, content)
        lines.append("Its content is an object with these input fields:")
        for f in spec.fields:
            lines.append(f'- "{f.name}" ({f.label}, {f.kind}): {f.description}')
        if empty:
            lines.append(
                f"Currently EMPTY fields: {', '.join(empty)}. To fill one, use a "
                "set-field op (field=<name>, find=\"\", replace=<new value>) or "
                "include just that key in replace-mode content."
            )
    elif spec.content_kind == "grid":
        lines.append(
            "Its content is a grid of rows; edit cells with ops carrying "
            "\"cell\" (A1 reference) and the cell's exact current value as find."
        )
    elif spec.content_kind == "json":
        lines.append(
            "Its content is structured chart data; return the complete new "
            "content object in replace mode (same keys and types)."
        )
    elif spec.content_kind == "file_backed":
        lines.append(
            "This canvas is backed by a REAL file; content here is only a "
            "snapshot. On-canvas text edits will not change the file — if the "
            "request targets the file's contents, wants_edit=false and say so "
            "in reply."
        )
    else:
        lines.append(
            "Its content is plain text; patch it with string find→replace ops."
        )
    return "\n".join(lines) + "\n"
