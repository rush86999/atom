"""
Shared helpers for the canvas E2E cluster (tests/test_canvas_*.py).

These helpers drive the REAL rendering path — no phantom state injection:

1. A canvas is created as a `Canvas` row + append-only `CanvasAudit` row in
   the same database the running backend serves (SQLite e2e_dev.db). The
   backend requires BOTH rows: `tools.canvas_crud_tool._verify_canvas_owner`
   reads the `Canvas` row (IDOR ownership guard), while `read_canvas` reads
   the latest audit row for content/type/title.
2. Tests then navigate to the real route `http://localhost:3001/canvas/{id}`,
   where `pages/canvas/[id].tsx` fetches `/api/canvas/{id}` from the backend
   and renders `CanvasPanel`, which renders the chart/form/markdown component.

This mirrors exactly what `tools/canvas_tool.present_chart()` / `present_form()`
persist in production (audit details_json carries `title` + `content`).
"""

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.models import Canvas, CanvasAudit, User


def create_canvas(
    db: Session,
    user: User,
    canvas_id: str,
    canvas_type: str,
    title: str,
    content: Any,
    action: str = "present",
) -> None:
    """Create a Canvas row + audit trail row for a real `/canvas/{id}` render.

    Mirrors the audit rows written by ``tools/canvas_tool._create_canvas_audit``
    (details_json carries ``title`` + ``content``).

    Args:
        db: Test database session (must match the running backend's DB).
        user: Owner of the canvas (backend ownership guard uses created_by).
        canvas_id: Canvas ID (the URL path segment on /canvas/{id}).
        canvas_type: Component type — "markdown", "line_chart", "bar_chart",
            "pie_chart", "form", "sheet", "snapshot", "browser_view", ...
        title: Canvas title shown in the host header.
        content: Canvas content payload (what read_canvas returns as content).
        action: Audit action_type ("present" or "update").
    """
    canvas = Canvas(
        id=canvas_id,
        tenant_id="default",
        created_by=str(user.id),
        name=title or canvas_id,
        canvas_type=canvas_type,
        content=content,
    )
    db.add(canvas)
    db.add(
        CanvasAudit(
            id=str(uuid.uuid4()),
            tenant_id="default",
            canvas_id=canvas_id,
            user_id=str(user.id),
            action_type=action,
            canvas_type=canvas_type,
            details_json={"title": title, "content": content},
        )
    )
    db.commit()


def create_chart_canvas(
    db: Session,
    user: User,
    chart_type: str,
    data: List[Dict[str, Any]],
    title: str = "Test Chart",
) -> str:
    """Create a chart canvas and return its ID.

    Args:
        db: Database session.
        user: Canvas owner.
        chart_type: "line_chart", "bar_chart", or "pie_chart".
        data: Chart data points (line: {timestamp, value, label?};
            bar/pie: {name, value}).
        title: Chart title.

    Returns:
        str: Canvas ID to navigate to (/canvas/{id}).
    """
    canvas_id = f"e2e-{chart_type}-{uuid.uuid4()}"
    create_canvas(db, user, canvas_id, chart_type, title, data)
    return canvas_id


def create_form_canvas(
    db: Session,
    user: User,
    fields: List[Dict[str, Any]],
    title: str = "Test Form",
) -> str:
    """Create a form canvas and return its ID.

    Args:
        db: Database session.
        user: Canvas owner.
        fields: InteractiveForm field configs ({name, label, type, required, ...}).
        title: Form title.

    Returns:
        str: Canvas ID to navigate to (/canvas/{id}).
    """
    canvas_id = f"e2e-form-{uuid.uuid4()}"
    create_canvas(
        db,
        user,
        canvas_id,
        "form",
        title,
        {"schema": {"fields": fields}, "title": title},
    )
    return canvas_id


def create_markdown_canvas(
    db: Session,
    user: User,
    title: str,
    content: str,
) -> str:
    """Create a markdown canvas and return its ID."""
    canvas_id = f"e2e-markdown-{uuid.uuid4()}"
    create_canvas(db, user, canvas_id, "markdown", title, {"content": content})
    return canvas_id


def append_update_audit(
    db: Session,
    user: User,
    canvas_id: str,
    canvas_type: str,
    title: str,
    content: Any,
) -> None:
    """Append an "update" audit row (bumps the version shown on /canvas/{id})."""
    db.add(
        CanvasAudit(
            id=str(uuid.uuid4()),
            tenant_id="default",
            canvas_id=canvas_id,
            user_id=str(user.id),
            action_type="update",
            canvas_type=canvas_type,
            details_json={"title": title, "content": content},
        )
    )
    db.commit()
