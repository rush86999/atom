"""Integration catalog, connection truth, disconnect and webhook scenarios."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
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
    required_evidence = {"salesforce", "hubspot", "slack", "teams", "gmail",
                         "notion", "jira", "linear", "stripe", "quickbooks",
                         "shopify", "github", "gitlab", "zoom"}
    by_id = {p.get("id"): p for p in providers}
    executable_evidence = {"adapter", "oauth", "routes"}
    missing = sorted(n for n in required_evidence
                     if not (set((by_id.get(n) or {}).get("evidence") or [])
                             & executable_evidence))
    ctx.record("INT-08", "verified" if not missing else "failed",
               [f"integrations/catalog.json"],
               notes=f"named providers with adapter/oauth/route evidence: "
                     f"{sorted(required_evidence - set(missing))}; missing={missing}")

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

    # ---- INT-07 signed webhook accepted exactly once --------------------
    # Slack signs the ORIGINAL request body: v0:{timestamp}:{body}. Use the
    # exact bytes on the wire, then replay the same event and forge a
    # signature. The processor's dedupe must accept one effect.
    slack_secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    event_id = f"Ev-{uuid.uuid4().hex}"
    body_obj = {
        "type": "event_callback",
        "event_id": event_id,
        "event": {
            "type": "message",
            "text": "INT-07 controlled signed webhook",
            "channel": "C-ACCEPTANCE",
            "user": "U-ACCEPTANCE",
            "ts": str(time.time()),
            "client_msg_id": event_id,
        },
    }
    body_bytes = json.dumps(body_obj, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    signature = "v0=" + hmac.new(
        slack_secret.encode(),
        b"v0:" + timestamp.encode() + b":" + body_bytes,
        hashlib.sha256,
    ).hexdigest()
    headers = {
        "content-type": "application/json",
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": signature,
    }
    accepted = ctx.client.post("/api/webhooks/slack", content=body_bytes,
                               headers=headers)
    accepted_body = (accepted.json() if accepted.status_code == 200 else {})
    replay = ctx.client.post("/api/webhooks/slack", content=body_bytes,
                             headers=headers)
    replay_body = replay.json() if replay.status_code == 200 else {}
    forged_headers = dict(headers)
    forged_headers["X-Slack-Signature"] = "v0=" + ("0" * 64)
    forged = ctx.client.post("/api/webhooks/slack", content=body_bytes,
                             headers=forged_headers)
    missing = ctx.client.post("/api/webhooks/slack", content=body_bytes)
    int07_ok = (accepted.status_code == 200
                and accepted_body.get("status") == "success"
                and accepted_body.get("event_id") == f"slack_{event_id}"
                and replay.status_code == 200
                and replay_body.get("status") == "duplicate"
                and forged.status_code == 401
                and missing.status_code == 401)
    ctx.record("INT-07", "verified" if int07_ok else "failed",
               [ctx.save("integrations/webhook.json", {
                   "secret_configured": bool(slack_secret),
                   "event_id": event_id,
                   "accepted": {"status": accepted.status_code,
                                "body": accepted_body},
                   "replay": {"status": replay.status_code,
                              "body": replay_body},
                   "forged": {"status": forged.status_code,
                              "body": forged.text[:400]},
                   "missing_signature": {"status": missing.status_code},
               })],
               notes=f"accepted={accepted.status_code} "
                     f"replay={replay_body.get('status')} "
                     f"forged={forged.status_code} missing={missing.status_code}")

    # ---- INT-05 outbound action behind HITL approval -------------------
    # The provider transport is a controlled local stub; the governance gate,
    # HITL row and approval decision are the real product path. No network
    # send is made.
    from core.agent_integration_gateway import (
        ActionType, AgentIntegrationGateway)
    gateway = AgentIntegrationGateway()
    sent = []

    async def _controlled_send(platform, params):
        sent.append({"platform": platform,
                     "recipient": params.get("recipient_id"),
                     "content": params.get("content")})
        return {"status": "success", "controlled_provider": True}

    gateway._handle_send_message = _controlled_send
    outbound_params = {
        "workspace_id": ctx.workspace_id,
        "recipient_id": "external-contact@example.com",
        "content": "INT-05 controlled outbound acceptance",
        "is_internal": False,
    }
    before = asyncio.run(gateway.execute_action(
        ActionType.SEND_MESSAGE, "slack", outbound_params))
    hitl_id = before.get("hitl_id")
    sent_before = len(sent)
    approve = (ctx.post(f"/api/agent-governance/approve/{hitl_id}")
               if hitl_id else None)
    after = asyncio.run(gateway.execute_action(
        ActionType.SEND_MESSAGE, "slack", outbound_params))
    sent_after = len(sent)
    retry = asyncio.run(gateway.execute_action(
        ActionType.SEND_MESSAGE, "slack", outbound_params))
    sent_after_retry = len(sent)
    replay_approval = (ctx.post(
        f"/api/agent-governance/approve/{hitl_id}")
        if hitl_id else None)
    replay_body = (replay_approval.json()
                   if replay_approval is not None
                   and replay_approval.headers.get("content-type", "")
                   .startswith("application/json") else {})
    retry_after_replay = asyncio.run(gateway.execute_action(
        ActionType.SEND_MESSAGE, "slack", outbound_params))
    sent_after_replay = len(sent)

    # Rejection control: a second external pattern is denied, and retrying it
    # still pauses instead of sending.
    reject_params = {**outbound_params, "recipient_id": "denied@example.com"}
    denied = asyncio.run(gateway.execute_action(
        ActionType.SEND_MESSAGE, "email", reject_params))
    denied_id = denied.get("hitl_id")
    reject = (ctx.post(f"/api/agent-governance/reject/{denied_id}"
                       "?reason=INT-05%20rejection%20control")
              if denied_id else None)
    denied_retry = asyncio.run(gateway.execute_action(
        ActionType.SEND_MESSAGE, "email", reject_params))
    denied_sent = [s for s in sent if s.get("recipient") == "denied@example.com"]
    int05_ok = (before.get("status") == "waiting_approval" and hitl_id
                and sent_before == 0
                and approve is not None and approve.status_code == 200
                and after.get("status") == "success"
                and sent_after == 1
                and retry.get("status") == "duplicate"
                and sent_after_retry == 1
                and replay_approval is not None
                and replay_approval.status_code in (400, 409)
                and sent_after_replay == 1
                and denied.get("status") == "waiting_approval" and denied_id
                and reject is not None and reject.status_code == 200
                and denied_retry.get("status") == "waiting_approval"
                and not denied_sent)
    ctx.record("INT-05", "verified" if int05_ok else "failed",
               [ctx.save("integrations/outbound_hitl.json", {
                   "controlled_provider": True,
                   "before": before,
                   "hitl_id": hitl_id,
                   "sent_before": sent_before,
                   "approve_status": None if approve is None else approve.status_code,
                   "after": after,
                   "sent_after": sent_after,
                   "retry": retry,
                   "sent_after_retry": sent_after_retry,
                   "replay_approval": {"status": replay_approval.status_code
                                       if replay_approval is not None else None,
                                       "body": replay_body},
                   "retry_after_replay": retry_after_replay,
                   "sent_after_replay": sent_after_replay,
                   "sent": sent,
                   "denied": denied,
                   "denied_id": denied_id,
                   "reject_status": None if reject is None else reject.status_code,
                   "denied_retry": denied_retry,
                   "denied_sent": denied_sent,
               })],
               notes=f"before={before.get('status')} sent={sent_before} "
                     f"approve={None if approve is None else approve.status_code} "
                     f"after={after.get('status')} sent_after={sent_after} "
                     f"retry={retry.get('status')} sent_after_retry={sent_after_retry} "
                     f"replay_approval={None if replay_approval is None else replay_approval.status_code} "
                     f"reject={None if reject is None else reject.status_code} "
                     f"denied_retry={denied_retry.get('status')}")

    # ---- INT-04 connected-provider read through a registered adapter --
    # HubSpot is a registered provider adapter. The upstream is a controlled
    # local HTTP server; the adapter's real request shape and bearer-token
    # boundary are exercised. This is not live-provider qualification.
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    from core.integrations.adapters.hubspot import HubSpotAdapter

    observed = {"authorization": None, "path": None, "query": None}

    class _HubSpotStub(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_GET(self):
            observed["authorization"] = self.headers.get("Authorization")
            observed["path"] = self.path.split("?")[0]
            observed["query"] = self.path.split("?", 1)[1] if "?" in self.path else ""
            if observed["authorization"] != "Bearer controlled-hubspot-token":
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b'{"message":"unauthorized"}')
                return
            payload = json.dumps({
                "results": [
                    {"id": "deal-1", "properties": {"dealname": "Atlas renewal",
                                                    "amount": "1200"}},
                    {"id": "deal-2", "properties": {"dealname": "Borealis expansion",
                                                    "amount": "3400"}},
                ]
            }).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    stub = ThreadingHTTPServer(("127.0.0.1", 0), _HubSpotStub)
    thread = threading.Thread(target=stub.serve_forever, daemon=True)
    thread.start()
    port = stub.server_address[1]
    int04_error = None
    deals = []
    try:
        db = ctx.db()
        try:
            adapter = HubSpotAdapter(db=db, workspace_id=ctx.workspace_id)
            adapter.base_url = f"http://127.0.0.1:{port}"
            adapter._access_token = "controlled-hubspot-token"
            deals = asyncio.run(adapter.get_deals(limit=2))
        finally:
            db.close()
        no_token_error = None
        db = ctx.db()
        try:
            no_token = HubSpotAdapter(db=db, workspace_id=ctx.workspace_id)
            no_token.base_url = f"http://127.0.0.1:{port}"
            try:
                asyncio.run(no_token.get_deals(limit=1))
            except Exception as exc:
                no_token_error = f"{type(exc).__name__}: {exc}"
        finally:
            db.close()
    except Exception as exc:
        int04_error = f"{type(exc).__name__}: {exc}"
        no_token_error = None
    finally:
        stub.shutdown()
        stub.server_close()

    int04_ok = (int04_error is None
                and len(deals) == 2
                and observed.get("path") == "/crm/v3/objects/deals"
                and observed.get("authorization") == "Bearer controlled-hubspot-token"
                and no_token_error is not None
                and "token" in no_token_error.lower())
    ctx.record("INT-04", "verified" if int04_ok else "failed",
               [ctx.save("integrations/controlled_read.json", {
                   "controlled_provider": True,
                   "provider": "hubspot",
                   "observed": observed,
                   "deal_count": len(deals),
                   "deals": deals,
                   "error": int04_error,
                   "no_token_error": no_token_error,
               })],
               notes=f"deals={len(deals)} path={observed.get('path')} "
                     f"bearer={observed.get('authorization') is not None} "
                     f"no_token_error={bool(no_token_error)} "
                     f"controlled_provider=True error={int04_error}")

    # ---- INT-09 live qualification -------------------------------------
    ctx.record("INT-09", "blocked_external",
               notes="Live qualification of 46+ providers requires real accounts "
                     "and permissions; not requested in this run")
    ctx.record("INT-09", "blocked_external",
               notes="Live qualification of 46+ providers requires real accounts "
                     "and permissions; not requested in this run")
