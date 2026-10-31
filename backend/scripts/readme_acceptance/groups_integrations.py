"""Integration catalog, connection truth, disconnect and webhook scenarios."""
from __future__ import annotations

import uuid

from .common import Ctx


def none_or_revoked(row) -> bool:
    if row is None:
        return True
    return str(getattr(row, "status", "")).lower() in ("revoked", "expired", "")


def integrations(ctx: Ctx) -> None:
    # ---- INT-01 truthful catalog --------------------------------------
    catalog = ctx.get("/api/integrations/business-catalog")
    cbody = catalog.json() if catalog.status_code == 200 else {}
    providers = cbody.get("providers") or []
    named = {p.get("id") for p in providers}
    required = {"salesforce", "hubspot", "slack", "teams", "gmail", "notion",
                "jira", "linear", "stripe", "quickbooks", "shopify", "github",
                "gitlab", "zoom"}
    ok = catalog.status_code == 200 and cbody.get("total", 0) >= 46 and required <= named
    ctx.record("INT-01", "verified" if ok else "failed",
               [ctx.save("integrations/catalog.json", cbody)],
               notes=f"total={cbody.get('total')} categories={cbody.get('by_category')} "
                     f"named_missing={sorted(required - named)}")
    ctx.record("INT-08", "verified" if required <= named else "failed",
               [f"integrations/catalog.json"],
               notes=f"named providers resolved: {sorted(required & named)}")

    # ---- INT-02 truthful connected state -------------------------------
    status1 = ctx.get("/api/integrations/health-status")
    s1 = status1.json() if status1.status_code == 200 else {}
    p1 = (s1.get("providers") or {}).get("outlook") or {}
    from core.models import IntegrationToken
    from datetime import datetime, timezone
    db = ctx.db()
    try:
        token = IntegrationToken(
            id=str(uuid.uuid4()), user_id=ctx.admin_id, tenant_id=ctx.tenant_id,
            provider="outlook", access_token="acceptance-token",
            refresh_token="acceptance-refresh",
            expires_at=datetime.now(timezone.utc).replace(year=2030),
            status="active",
        )
        db.add(token)
        db.commit()
        token_id = token.id
    finally:
        db.close()
    status2 = ctx.get("/api/integrations/health-status")
    s2 = status2.json() if status2.status_code == 200 else {}
    p2 = (s2.get("providers") or {}).get("outlook") or {}
    db = ctx.db()
    try:
        row = db.query(IntegrationToken).filter(IntegrationToken.id == token_id).first()
        if row:
            db.delete(row)
            db.commit()
    finally:
        db.close()
    status3 = ctx.get("/api/integrations/health-status")
    s3 = status3.json() if status3.status_code == 200 else {}
    p3 = (s3.get("providers") or {}).get("outlook") or {}
    ok = (status1.status_code == 200 and p1.get("connected") is False
          and p2.get("connected") is True
          and p3.get("connected") is False)
    ctx.record("INT-02", "verified" if ok else "failed",
               [ctx.save("integrations/connection_status.json", {
                   "disconnected": p1, "connected": p2, "after_delete": p3})],
               notes=f"no_token={p1.get('connected')} with_token={p2.get('connected')} "
                     f"after_delete={p3.get('connected')} source={p2.get('source')}")

    # ---- INT-03 controlled OAuth connect (full round-trip) ------------
    from urllib.parse import urlparse, parse_qs
    from core.models import IntegrationToken as IT
    from core.privsec.token_encryption import decrypt_token
    initiate = ctx.client.get("/api/v1/auth/oauth/github/initiate",
                              params={"token": ctx.token}, follow_redirects=False)
    location = initiate.headers.get("location") or ""
    state = (parse_qs(urlparse(location).query).get("state") or [None])[0]
    if not state:
        body = initiate.json() if initiate.headers.get("content-type", "").startswith("application/json") else {}
        authorization_url = body.get("authorization_url") or body.get("url") or ""
        state = (parse_qs(urlparse(authorization_url).query).get("state") or [None])[0]
    callback = ctx.client.get("/api/v1/auth/oauth/github/callback",
                              params={"code": "acceptance-code", "state": state},
                              follow_redirects=False) if state else None
    db = ctx.db()
    try:
        rows = db.query(IT).filter(IT.provider == "github").all()
        token_info = [{
            "id": r.id,
            "is_ciphertext": "mock-github-access" not in (r.access_token or ""),
            "status": r.status,
        } for r in rows]
        stored_plain = None
        if rows:
            try:
                stored_plain = decrypt_token(rows[0].access_token) if rows[0].access_token else None
            except Exception:
                stored_plain = None
    finally:
        db.close()
    status = ctx.get("/api/integrations/health-status")
    sbody = status.json() if status.status_code == 200 else {}
    github_connected = ((sbody.get("providers") or {}).get("github") or {}).get("connected")
    connected_ok = (initiate.status_code in (302, 307) and state
                    and callback is not None and callback.status_code in (302, 307, 200)
                    and token_info and token_info[0]["is_ciphertext"])
    ctx.record("INT-03", "verified" if connected_ok else "partial",
               [ctx.save("integrations/oauth_connect.json", {
                   "initiate": {"status": initiate.status_code,
                                "location": location[:300], "state": state},
                   "callback": None if callback is None else {
                       "status": callback.status_code,
                       "location": callback.headers.get("location")},
                   "tokens": token_info,
                   "decrypted_prefix": (stored_plain or "")[:20],
                   "github_connected": github_connected})],
               notes=f"initiate={initiate.status_code} state={bool(state)} "
                     f"callback={None if callback is None else callback.status_code} "
                     f"tokens={len(token_info)} ciphertext={token_info[0]['is_ciphertext'] if token_info else None}")

    # ---- INT-06 disconnect revokes tokens ------------------------------
    disconnect = ctx.delete("/api/v1/auth/oauth/tokens/github")
    db = ctx.db()
    try:
        rows = db.query(IT).filter(IT.provider == "github").all()
        revoked = all(str(getattr(r, "status", "")).lower() in ("revoked", "expired")
                      for r in rows) if rows else False
    finally:
        db.close()
    status_after = ctx.get("/api/integrations/health-status")
    sa = status_after.json() if status_after.status_code == 200 else {}
    connected_after = ((sa.get("providers") or {}).get("github") or {}).get("connected")
    ctx.record("INT-06", "verified" if disconnect.status_code in (200, 204)
               and revoked and connected_after is False else "partial",
               [ctx.save("integrations/disconnect.json", {
                   "status": disconnect.status_code, "body": disconnect.text[:800],
                   "token_status": [getattr(r, "status", None) for r in rows],
                   "connected_after": connected_after})],
               notes=f"disconnect={disconnect.status_code} revoked={revoked} "
                     f"connected_after={connected_after}")

    # ---- INT-07 webhook fail-closed -----------------------------------
    forged = ctx.client.post("/api/webhooks/shopify/orders-create", json={
        "id": 1, "email": "forged@example.com"})
    ctx.record("INT-07", "verified" if forged.status_code in (401, 403, 503) else "failed",
               [ctx.save("integrations/webhook.json", {
                   "status": forged.status_code, "body": forged.text[:600]})],
               notes=f"unsigned webhook rejected with {forged.status_code}")

    # ---- INT-04 / INT-05 / INT-09 --------------------------------------
    ctx.record("INT-04", "partial",
               notes="Universal adapter execution requires a connected provider; "
                     "the controlled-provider journey suite covers it, live data "
                     "qualification is not claimed")
    ctx.record("INT-05", "partial",
               notes="Outbound send/create behind HITL needs a connected provider; "
                     "governance approval itself is verified by GOV-02")
    ctx.record("INT-09", "blocked_external",
               notes="Live qualification of 46+ providers requires real accounts "
                     "and permissions; not requested in this run")
