"""Startup/periodic audit of IntegrationToken rows — find stale credentials
and rectify them before anything consumes them (pollers, tool calls).

Why (2026-09-05): the live-DB wipe re-seeded users while rows elsewhere
survived; token rows can also be left behind by partial reconnects. A token
row that references a user that no longer exists can never refresh or be
used again, but every consumer filters on status == 'active' — so an
orphaned row silently stays in play (the poller picks its owner, the poll
then fails on the dead token every cycle). Rectify the impossible cases so
'active' means usable.

Provider-agnostic by design (works for every integration); conservative by
design — the access-token TTL (expires_at) is NOT a staleness signal by
itself because the refresh flow renews it; a token is only marked expired
when it can provably never work again (expired AND no refresh token).
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Statuses this audit writes (IntegrationToken.status comment allows
# active/revoked/expired; superseded marks the loser of a duplicate pair).
SUPERSEDED = "superseded"


def audit_integration_tokens(db, apply: bool = True) -> dict:
    """Audit + rectify IntegrationToken rows. Returns a report dict.

    Rectifications (only when apply=True):
    - orphaned: user_id points at a user that no longer exists -> 'revoked'
      (can never refresh or authorize; forensics stay in the row).
    - superseded: duplicate active rows for the same (user_id, provider) ->
      only the most recently updated stays 'active'.
    - expired: status active, access token past expires_at, and NO refresh
      token -> 'expired' (provably unusable; refreshable tokens are left to
      their normal refresh flow).

    Pass apply=False for a dry run (report only).
    """
    from core.models import IntegrationToken, User

    report = {"orphaned": [], "superseded": [], "expired": [], "checked": 0}
    try:
        report["checked"] = db.query(IntegrationToken).count()
        live_user_ids = {str(u) for (u,) in db.query(User.id).all()}

        tokens = db.query(IntegrationToken).all()
        now = datetime.now(timezone.utc)

        seen_pairs = {}
        for tok in tokens:
            uid = str(tok.user_id) if tok.user_id else None
            if uid and uid not in live_user_ids:
                if tok.status == "active":
                    report["orphaned"].append(
                        {"id": tok.id, "user_id": uid, "provider": tok.provider}
                    )
                    if apply:
                        tok.status = "revoked"
                continue

            # Duplicate detection on active rows only.
            if tok.status == "active" and tok.user_id:
                key = (str(tok.tenant_id), uid, str(tok.provider))
                prev = seen_pairs.get(key)
                if prev is None:
                    seen_pairs[key] = tok
                else:
                    newer, older = (
                        (tok, prev)
                        if (tok.updated_at or tok.created_at or _MIN)
                        >= (prev.updated_at or prev.created_at or _MIN)
                        else (prev, tok)
                    )
                    report["superseded"].append(
                        {
                            "id": older.id,
                            "user_id": uid,
                            "provider": older.provider,
                            "kept": newer.id,
                        }
                    )
                    if apply:
                        older.status = SUPERSEDED
                    seen_pairs[key] = newer

            # Provably-unusable active token: past expiry with no way to
            # refresh. expires_at alone is NOT stale — refresh renews it.
            if (
                tok.status == "active"
                and tok.expires_at is not None
                and not (tok.refresh_token or "").strip()
            ):
                exp = tok.expires_at
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp < now:
                    report["expired"].append(
                        {"id": tok.id, "user_id": uid, "provider": tok.provider}
                    )
                    if apply:
                        tok.status = "expired"

        if apply and (report["orphaned"] or report["superseded"] or report["expired"]):
            db.commit()

        if any(report[k] for k in ("orphaned", "superseded", "expired")):
            logger.warning(
                "IntegrationToken audit: %d orphaned, %d superseded, %d "
                "unrefreshable-expired (checked %d, applied=%s)",
                len(report["orphaned"]),
                len(report["superseded"]),
                len(report["expired"]),
                report["checked"],
                apply,
            )
        return report
    except Exception as e:
        # Never block startup on the audit — log and continue.
        logger.error("IntegrationToken audit failed: %s", e)
        if apply:
            db.rollback()
        return report


from datetime import datetime as _dt

_MIN = _dt.min.replace(tzinfo=timezone.utc)
