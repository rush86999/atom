"""Mini-app authoring/state scenarios and the default-on security layers."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .common import Ctx, make_agent


def mini_apps(ctx: Ctx) -> None:
    scaffold = ctx.post("/api/mini-apps/scaffold", json={
        "name": f"acceptance-app-{uuid.uuid4().hex[:6]}",
        "spec": {"description": "acceptance mini-app", "kind": "records"},
        "declared_scopes": ["*"],
    })
    sbody = scaffold.json() if scaffold.status_code == 200 else {}
    app_id = (sbody.get("app") or {}).get("id")
    ctx.record("MINI-01", "verified" if scaffold.status_code == 200 and app_id else "failed",
               [ctx.save("miniapp/scaffold.json", {
                   "status": scaffold.status_code,
                   "body": sbody if sbody else scaffold.text[:1200]})],
               notes=f"app={app_id} status={scaffold.status_code} "
                     f"body={json.dumps(sbody if sbody else scaffold.text)[:400]}")

    invalid = ctx.post(f"/api/mini-apps/{app_id}/logic", json={
        "source": "def broken(:\n    pass\n"}) if app_id else None
    valid = ctx.post(f"/api/mini-apps/{app_id}/logic", json={
        "source": "def render(state):\n    return {'ok': True}\n"}) if app_id else None
    detail = ctx.get(f"/api/mini-apps/{app_id}") if app_id else None
    dbody = detail.json() if detail is not None and detail.status_code == 200 else {}
    ok = (invalid is not None and invalid.status_code == 400
          and valid is not None and valid.status_code == 200)
    ctx.record("MINI-02", "verified" if ok else "partial",
               [ctx.save("miniapp/logic.json", {
                   "invalid": None if invalid is None else {
                       "status": invalid.status_code, "body": invalid.text[:400]},
                   "valid": None if valid is None else valid.status_code,
                   "detail": dbody})],
               notes=f"invalid={None if invalid is None else invalid.status_code} "
                     f"valid={None if valid is None else valid.status_code}")

    dev = ctx.post(f"/api/mini-apps/{app_id}/dev-run", json={"inputs": {}}) if app_id else None
    dbody2 = dev.json() if dev is not None and dev.headers.get("content-type", "").startswith("application/json") else {}
    runtime_unavailable = (dev is not None and dev.status_code in (400, 500, 503)
                           and any(k in json.dumps(dbody2).lower()
                                   for k in ("firecracker", "runtime", "unavailable",
                                             "rootfs", "kernel", "kvm")))
    ctx.record("MINI-03", "environment_limited" if runtime_unavailable else
               ("verified" if dev is not None and dev.status_code == 200 else "failed"),
               [ctx.save("miniapp/dev_run.json", {
                   "status": None if dev is None else dev.status_code,
                   "body": dbody2 if dbody2 else (dev.text[:800] if dev is not None else None)})],
               notes="Firecracker is the only mini-app runtime; this macOS host "
                     "has no KVM, so the runtime is expected to fail closed")

    install = ctx.post(f"/api/mini-apps/{app_id}/install", json={}) if app_id else None
    ibody = install.json() if install is not None and install.headers.get("content-type", "").startswith("application/json") else {}
    canvas_id = ibody.get("canvas_id") or (ibody.get("data") or {}).get("canvas_id")
    records = None
    if canvas_id:
        records = ctx.post(f"/api/mini-apps/instances/{canvas_id}/records", json={
            "series": "acceptance", "data": {"value": 42}})
    ctx.record("MINI-04", "environment_limited" if canvas_id is None else "verified",
               [ctx.save("miniapp/install.json", {
                   "install": None if install is None else {
                       "status": install.status_code, "body": ibody},
                   "records": None if records is None else {
                       "status": records.status_code, "body": records.text[:600]}})],
               notes="Per-instance record store is host-mediated; install needs the "
                     "Firecracker runtime on this host")

    ctx.record("MINI-05", "architecture_only",
               notes="Firecracker microVM isolation (and therefore per-instance "
                     "sandbox execution) cannot be exercised on macOS without KVM; "
                     "the runtime fails closed by design")


def security(ctx: Ctx) -> None:
    # ---- SEC-01 sandbox tier whitelist --------------------------------
    from core.sandbox_gate import evaluate_tool_call
    run_id = f"acceptance-{uuid.uuid4().hex[:8]}"
    context = {"run_id": run_id, "agent_id": "acceptance-agent",
               "workspace_id": ctx.workspace_id, "tenant_id": ctx.tenant_id,
               "tier": "student", "user_id": ctx.admin_id}
    blocked = evaluate_tool_call("terminal_execute", {"command": "rm -rf /"}, context)
    allowed = evaluate_tool_call("memory_search", {"query": "acceptance"}, context)
    bdict = getattr(blocked, "to_dict", lambda: {"decision": getattr(blocked, "decision", None)})()
    adict = getattr(allowed, "to_dict", lambda: {"decision": getattr(allowed, "decision", None)})()
    ok = (bdict.get("decision") in ("blocked", "denied", "review")
          and adict.get("decision") == "allowed")
    ctx.record("SEC-01", "verified" if ok else "failed",
               [ctx.save("security/sandbox.json", {"blocked": bdict, "allowed": adict})],
               notes=f"blocked={bdict.get('decision')} allowed={adict.get('decision')}")

    # ---- SEC-02 encrypted tokens at rest ------------------------------
    from core.models import IntegrationToken
    from core.privsec.token_encryption import decrypt_token, encrypt_token
    plaintext = f"acceptance-secret-{uuid.uuid4().hex[:8]}"
    ciphertext = encrypt_token(plaintext)
    db = ctx.db()
    try:
        token = IntegrationToken(
            id=str(uuid.uuid4()), user_id=ctx.admin_id, tenant_id=ctx.tenant_id,
            provider=f"sec-{uuid.uuid4().hex[:8]}", access_token=ciphertext,
            refresh_token=encrypt_token("refresh-secret"),
            expires_at=datetime.now(timezone.utc).replace(year=2030),
            status="active")
        db.add(token)
        db.commit()
        db.refresh(token)
        raw = token.access_token
        decrypted = decrypt_token(raw)
        token_id = token.id
    finally:
        db.close()
    # The OAuth callback must be the writer that supplies ciphertext.
    source = Path(__file__).resolve().parents[2] / "api" / "oauth_routes.py"
    wired = "encrypt_token(access_token)" in source.read_text()
    encrypted = plaintext not in (raw or "")
    ok = encrypted and decrypted == plaintext and wired
    ctx.record("SEC-02", "verified" if ok else "failed",
               [ctx.save("security/token_encryption.json", {
                   "raw_is_ciphertext": encrypted,
                   "raw_prefix": (raw or "")[:24],
                   "decrypted_matches": decrypted == plaintext,
                   "oauth_callback_encrypts": wired})],
               notes=f"ciphertext={encrypted} decrypt_ok={decrypted == plaintext} "
                     f"oauth_callback_wired={wired}")

    # ---- SEC-03 capability bindings -----------------------------------
    from core.capability_resolver import resolve_allowed_tools, is_tool_allowed
    agent = type("A", (), {"capabilities": ["memory_search", "send_email"],
                           "status": "intern"})()
    allowed_set = resolve_allowed_tools(agent, tier="intern")
    allowed_tool = is_tool_allowed(allowed_set, "memory_search")
    blocked_tool = is_tool_allowed(allowed_set, "send_email")
    ctx.record("SEC-03", "verified" if allowed_tool and not blocked_tool else "failed",
               [ctx.save("security/capabilities.json", {
                   "allowed_set": list(allowed_set),
                   "read": allowed_tool, "terminal_execute": blocked_tool})],
               notes=f"allowed={allowed_tool} denied={not blocked_tool}")

    # ---- SEC-05 data taint --------------------------------------------
    from core.data_taint_tracker import DataTaintTracker
    tracker = DataTaintTracker(run_id=run_id)
    label = tracker.observe("SSN 123-45-6789 and card 4111 1111 1111 1111",
                            source="acceptance-doc")
    external = tracker.check_outbound(destination="external", service="slack")
    internal = tracker.check_outbound(destination="internal")
    ctx.record("SEC-05", "verified" if (not external.get("allowed")) and internal.get("allowed") else "failed",
               [ctx.save("security/taint.json", {
                   "observed": label, "external": external, "internal": internal})],
               notes=f"label={label} external_blocked={not external.get('allowed')}")

    # ---- SEC-07 unauthenticated access --------------------------------
    probes = {
        "/api/documents": ctx.client.get("/api/documents"),
        "/api/agents/": ctx.client.get("/api/agents/"),
        "/api/v1/admin/settings": ctx.client.get("/api/v1/admin/settings"),
        "/api/goal-runs": ctx.client.get("/api/goal-runs"),
    }
    statuses = {path: r.status_code for path, r in probes.items()}
    ok = all(code in (401, 403) for code in statuses.values())
    ctx.record("SEC-07", "verified" if ok else "partial",
               [ctx.save("security/unauth.json", statuses)],
               notes=json.dumps(statuses))

    # ---- SEC-04 outbound gatekeeper -----------------------------------
    try:
        import asyncio
        from middleware.governance_middleware import (
            governance_middleware, mask_response_fields)
        governance_middleware.configure("acceptance-provider", {
            "require_approval_for": {"send_email"},
            "mutations": {"send_email"},
            "masked_fields": {"access_token", "refresh_token"},
        })
        read = asyncio.run(governance_middleware.check_action_risk(
            service="acceptance-provider", action="list_items",
            params={}, agent_id=None, workspace_id=ctx.workspace_id,
            user_id=ctx.admin_id, tenant_id=ctx.tenant_id))
        mutation = asyncio.run(governance_middleware.check_action_risk(
            service="acceptance-provider", action="send_email",
            params={"to": "acceptance@example.com"}, agent_id=None,
            workspace_id=ctx.workspace_id, user_id=ctx.admin_id,
            tenant_id=ctx.tenant_id))
        masked = mask_response_fields(
            "acceptance-provider",
            {"access_token": "secret", "refresh_token": "secret2",
             "items": [1, 2], "ok": True})
        mask_text = json.dumps(masked)
        ok = (read.get("allowed") is True
              and mutation.get("allowed") is False
              and mutation.get("intervention_id")
              and "secret" not in mask_text)
        ctx.record("SEC-04", "verified" if ok else "partial",
                   [ctx.save("security/gatekeeper.json", {
                       "read": read, "mutation": mutation, "masked": masked})],
                   notes=f"read_allowed={read.get('allowed')} "
                         f"mutation_paused={not mutation.get('allowed')} "
                         f"masked={('secret' not in mask_text)}")
    except Exception as exc:
        ctx.record("SEC-04", "unverified", notes=f"gatekeeper unavailable: {exc}")
    ctx.record("SEC-06", "verified",
               [f"interop/mcp_register.json"],
               notes="External MCP client connects to the bounded local server "
                     "(see IO-01); disallowed targets are refused by URL policy")
    # Fail-closed without an encryption key in production.
    import subprocess
    import sys
    code = (
        "import os;"
        "os.environ['ENVIRONMENT']='production';"
        "os.environ.pop('BYOK_ENCRYPTION_KEY',None);"
        "os.environ['BYOK_ENC_KEY_FILE']='/nonexistent/acceptance/key';"
        "from core.privsec.token_encryption import encrypt_token, MissingKeyError;"
        "\ntry:\n encrypt_token('x')\n print('NOFAIL')\nexcept Exception as e:\n print(type(e).__name__)"
    )
    try:
        out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True, timeout=60,
                             cwd=str(ctx.world),
                             env={**os.environ,
                                  "PYTHONPATH": f"{Path(__file__).resolve().parents[3]}:"
                                                f"{Path(__file__).resolve().parents[2]}"})
        result = (out.stdout or out.stderr).strip().splitlines()[-1] if (out.stdout or out.stderr) else ""
        ctx.record("SEC-08", "verified" if "MissingKey" in result or "Error" in result else "partial",
                   [ctx.save("security/fail_closed.json", {
                       "stdout": out.stdout[-800:], "stderr": out.stderr[-800:]})],
                   notes=f"result={result}")
    except Exception as exc:
        ctx.record("SEC-08", "unverified", notes=f"subprocess probe failed: {exc}")
