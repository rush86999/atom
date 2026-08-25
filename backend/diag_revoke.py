"""Revoke dead microsoft/outlook tokens to stop daemon refresh spam."""
import os
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from core.database import get_db_session
from core.models import IntegrationToken

with get_db_session() as db:
    rows = (
        db.query(IntegrationToken)
        .filter(
            IntegrationToken.provider.in_(["outlook", "microsoft"]),
            IntegrationToken.status == "active",
        )
        .all()
    )
    for r in rows:
        r.status = "revoked"
        print(f"revoked: provider={r.provider} user={r.user_id} expired_at={r.expires_at}")
    db.commit()
    print(f"\ntotal revoked: {len(rows)}")
