"""List ALL outlook/microsoft integration token rows."""
import os
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from core.database import get_db_session
from core.models import IntegrationToken

with get_db_session() as db:
    rows = (
        db.query(IntegrationToken)
        .filter(IntegrationToken.provider.in_(["outlook", "microsoft", "microsoft365"]))
        .all()
    )
    print(f"total rows: {len(rows)}\n")
    for r in rows:
        print(f"id={r.id}")
        print(f"  provider={r.provider}  status={r.status}")
        print(f"  user_id={r.user_id}")
        print(f"  expires_at={r.expires_at}")
        print(f"  created_at={getattr(r, 'created_at', '?')}  updated_at={getattr(r, 'updated_at', '?')}")
        print(f"  has_access={bool(r.access_token)}  has_refresh={bool(r.refresh_token)}")
        print()
