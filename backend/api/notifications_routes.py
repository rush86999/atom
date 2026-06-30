"""
P2.2 — In-app notification center REST surface.

Three endpoints powering the Header bell icon + dropdown:
  GET    /api/notifications              — list (filterable by unread)
  POST   /api/notifications/{id}/read    — mark single read
  POST   /api/notifications/read-all     — mark all read

All endpoints require authentication (get_current_user) — never trust a
notification_id from the URL alone; ownership is enforced on the row lookup.
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import Notification, User

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/notifications", tags=["Notifications"])


class NotificationBatchResponse(BaseModel):
    marked_read: int


@router.get("")
async def list_notifications(
    unread_only: bool = False,
    type: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the current user's notifications, newest first.

    Args:
        unread_only: When true, only return rows where read=False.
        type: Optional free-form type filter. Matched as a substring against
            ``metadata_json->notification_type`` (set by NotificationService)
            so callers can ask for e.g. ``type=agent_graduated`` without the
            backend needing an enum for every notification_type.
        limit: Cap on returned rows (default 50, max 200).
    """
    limit = max(1, min(int(limit or 50), 200))

    q = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        q = q.filter(Notification.read.is_(False))

    # Soft type filter: the canonical type lives in metadata_json under the
    # "notification_type" key (set by NotificationService). We can't rely on a
    # JSON path expression across SQLite + Postgres without dialect branching,
    # so we fetch the bounded result set and filter in Python. Cap is small
    # (default 50, max 200) so this is cheap.
    rows = q.order_by(Notification.created_at.desc()).limit(limit).all()
    if type:
        wanted = type.lower()
        rows = [
            n for n in rows
            if (
                isinstance(n.metadata_json, dict)
                and str(n.metadata_json.get("notification_type", "")).lower() == wanted
            )
        ]

    return router.success_response(
        data={
            "notifications": [_serialize(n) for n in rows],
            "unread_count": (
                db.query(Notification)
                .filter(Notification.user_id == current_user.id)
                .filter(Notification.read.is_(False))
                .count()
            ),
        }
    )


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a single notification read. Ownership enforced."""
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id)
        .filter(Notification.user_id == current_user.id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if not notification.read:
        notification.read = True
        from datetime import datetime, timezone
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)

    return router.success_response(
        data=_serialize(notification),
        message="Notification marked as read",
    )


@router.post("/read-all")
async def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark every unread notification for the current user as read."""
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .filter(Notification.read.is_(False))
        .all()
    )
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    for row in rows:
        row.read = True
        row.read_at = now
    db.commit()

    return router.success_response(
        data={"marked_read": len(rows)},
        message=f"Marked {len(rows)} notifications as read",
    )


def _serialize(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "type": notification.type,
        "title": notification.title,
        "message": notification.message,
        "read": bool(notification.read),
        "action_url": notification.action_url,
        "action_label": notification.action_label,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
        "metadata": notification.metadata_json or {},
    }
