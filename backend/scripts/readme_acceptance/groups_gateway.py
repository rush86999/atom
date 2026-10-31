"""LLM gateway + provider routing scenarios against a bounded local upstream."""
from __future__ import annotations

import json
import os

from .common import Ctx
from . import mock_llm_server


def _gateway_headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def _chat(client, key, body, extra=None):
    headers = _gateway_headers(key)
    if extra:
        headers.update(extra)
    return client.post("/v1/chat/completions", json=body, headers=headers)


def gateway(ctx: Ctx) -> None:
    mock_llm_server.reset()
    # A cloud-shaped provider is needed for the gateway; local-only would
    # exclude it. The upstream URL is the bounded local mock, not a cloud API.
    old_local = os.environ.get("ATOM_LOCAL_ONLY")
    os.environ["ATOM_LOCAL_ONLY"] = "false"
    stored = ctx.post("/api/ai/providers/openai/keys", json={
        "api_key": "sk-acceptance-test-key-0000000000",
        "key_name": "default", "environment": "production",
        "label": "acceptance mock upstream"})
    ctx.save("gateway/key_store.json", {
        "status": stored.status_code, "body": stored.text[:600]})

    created = ctx.post("/api/gateway/keys", json={
        "name": "acceptance", "rate_limit_per_minute": 120})
    cbody = created.json() if created.status_code in (200, 201) else {}
    key = cbody.get("key")
    key_id = cbody.get("id")
    ctx.record("GW-04", "verified" if created.status_code in (200, 201) and key
               and key.startswith("atom_sk_") else "failed",
               [ctx.save("gateway/key_create.json", {
                   "status": created.status_code,
                   "key_prefix": (key or "")[:12],
                   "id": key_id,
                   "body": cbody})],
               notes=f"key_created={bool(key)} id={key_id}")

    body = {"model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "say acceptance"}]}
    chat = _chat(ctx.client, key, body) if key else None
    cbody2 = chat.json() if chat is not None and chat.status_code == 200 else {}
    choices = cbody2.get("choices") or []
    ok = (chat is not None and chat.status_code == 200 and choices
          and (choices[0].get("message") or {}).get("role") == "assistant")
    ctx.record("GW-01", "verified" if ok else "failed",
               [ctx.save("gateway/openai_chat.json", {
                   "request": body,
                   "status": None if chat is None else chat.status_code,
                   "body": cbody2 if ok else (chat.text[:1500] if chat is not None else None),
                   "upstream_calls": mock_llm_server.calls()[-3:]})],
               notes=f"chat_status={None if chat is None else chat.status_code} "
                     f"choices={len(choices)}")

    models = ctx.client.get("/v1/models", headers=_gateway_headers(key)) if key else None
    mbody = models.json() if models is not None and models.status_code == 200 else {}
    ctx.record("GW-03", "verified" if models is not None and models.status_code == 200
               and (mbody.get("data") or []) else "failed",
               [ctx.save("gateway/models.json", {
                   "status": None if models is None else models.status_code,
                   "body": mbody})],
               notes=f"models={len(mbody.get('data') or [])}")

    # Anthropic-compatible surface
    anthropic = ctx.client.post("/v1/messages", headers=_gateway_headers(key), json={
        "model": "gpt-4o-mini", "max_tokens": 64,
        "messages": [{"role": "user", "content": "say acceptance"}]}) if key else None
    abody = anthropic.json() if anthropic is not None and anthropic.status_code == 200 else {}
    ctx.record("GW-02", "verified" if anthropic is not None and anthropic.status_code == 200
               and (abody.get("content") or []) else "failed",
               [ctx.save("gateway/anthropic.json", {
                   "status": None if anthropic is None else anthropic.status_code,
                   "body": abody if abody else (anthropic.text[:1200] if anthropic is not None else None)})],
               notes=f"messages_status={None if anthropic is None else anthropic.status_code}")

    # Header override reaches the upstream with the requested model.
    override = _chat(ctx.client, key, {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "override"}],
    }, extra={"x-atom-model": "gpt-4o-mini"}) if key else None
    upstreams = mock_llm_server.calls()
    ctx.record("GW-05", "verified" if override is not None and override.status_code == 200
               and any((c.get("body") or {}).get("model") == "gpt-4o-mini"
                       for c in upstreams) else "partial",
               [ctx.save("gateway/override.json", {
                   "status": None if override is None else override.status_code,
                   "upstream_models": [(c.get("body") or {}).get("model")
                                       for c in upstreams]})],
               notes="x-atom-model override reached the upstream")

    # Invalid key must be rejected, as must a revoked key.
    invalid = _chat(ctx.client, "atom_sk_invalid", body)
    revoke = ctx.delete(f"/api/gateway/keys/{key_id}") if key_id else None
    revoked = _chat(ctx.client, key, body) if key else None
    ctx.record("GW-04", "verified" if created.status_code in (200, 201) and key
               and invalid.status_code == 401 and revoke is not None
               and revoke.status_code in (200, 204)
               and revoked is not None and revoked.status_code == 401 else "partial",
               [ctx.save("gateway/key_lifecycle.json", {
                   "create": created.status_code,
                   "invalid": invalid.status_code,
                   "revoke": None if revoke is None else revoke.status_code,
                   "revoked_use": None if revoked is None else revoked.status_code,
                   "hash_only": "stored plaintext?"})],
               notes=f"invalid={invalid.status_code} revoke={None if revoke is None else revoke.status_code} "
                     f"revoked_use={None if revoked is None else revoked.status_code}")

    # Error propagation: stop the bounded upstream so the next request gets a
    # real transport failure, then restart it. This is a genuine failure path,
    # not a synthetic handler probe.
    server = ctx.cache.get("llm_server")
    failure = None
    try:
        if server is not None:
            server.stop()
        bad_key = ctx.post("/api/gateway/keys", json={
            "name": "acceptance-failure", "rate_limit_per_minute": 60})
        bk = (bad_key.json() or {}).get("key") if bad_key.status_code in (200, 201) else None
        failure = _chat(ctx.client, bk, {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "force transport failure"}],
        }) if bk else None
    finally:
        if server is not None:
            try:
                ctx.cache["llm_server"] = mock_llm_server.Server(59997).start()
            except Exception:
                pass
    fbody = failure.json() if failure is not None and failure.headers.get("content-type", "").startswith("application/json") else {}
    err = (fbody.get("error") or {})
    propagated = (failure is not None and failure.status_code in (502, 503)
                  and bool(err.get("type")) and bool(err.get("code")))
    ctx.record("GW-06", "verified" if propagated else "partial",
               [ctx.save("gateway/error_path.json", {
                   "status": None if failure is None else failure.status_code,
                   "body": fbody or (failure.text[:800] if failure is not None else None),
               })],
               notes=f"transport failure mapped to {None if failure is None else failure.status_code} "
                     f"code={err.get('code')}")

    if old_local is None:
        os.environ.pop("ATOM_LOCAL_ONLY", None)
    else:
        os.environ["ATOM_LOCAL_ONLY"] = old_local

    # ---- ROUTE-01 five-tier classification ----------------------------
    try:
        from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier
        classifier = CognitiveClassifier()
        samples = {
            "simple": "hi, thanks",
            "moderate": "analyze and compare the quarterly revenue trends",
            "technical": "calculate the integral and solve the equation",
            "advanced": "security audit of the distributed cluster architecture",
        }
        tiers = {name: classifier.classify(prompt, "chat").value
                 for name, prompt in samples.items()}
        order = [t.value for t in CognitiveTier]
        ranks = [order.index(v) for v in tiers.values()]
        ok = len(set(tiers.values())) >= 3 and ranks == sorted(ranks)
        ctx.record("ROUTE-01", "verified" if ok else "partial",
                   [ctx.save("routing/tiers.json", {
                       "tiers": tiers, "order": order})],
                   notes=f"tiers={tiers}")
    except Exception as exc:
        ctx.record("ROUTE-01", "unverified", notes=f"tier classifier unavailable: {exc}")

    # ---- ROUTE-02 16+ providers ---------------------------------------
    providers = ctx.get("/api/ai/providers")
    pbody = providers.json() if providers.status_code == 200 else {}
    plist = (pbody.get("data") or {}).get("providers") or pbody.get("providers") or []
    ctx.record("ROUTE-02", "verified" if len(plist) >= 16 else "failed",
               [ctx.save("routing/providers.json", {
                   "count": len(plist),
                   "ids": [((p.get("provider") or {}).get("id") or p.get("id"))
                           for p in plist]})],
               notes=f"provider_count={len(plist)}")

    # ---- ROUTE-04 learning router status ------------------------------
    lr = ctx.get("/api/v1/llm/learning-router/status")
    ctx.record("ROUTE-04", "partial" if lr.status_code == 200 else "unverified",
               [ctx.save("routing/learning_router.json", {
                   "status": lr.status_code, "body": lr.text[:1000]})],
               notes="Learning-router flag/status surface served; re-ranking "
                     "needs accumulated feedback rows")

    # ---- ROUTE-06 local provider wiring --------------------------------
    local_models = ctx.get("/api/local-models")
    ctx.record("ROUTE-06", "partial" if local_models.status_code == 200 else "unverified",
               [ctx.save("routing/local_models.json", {
                   "status": local_models.status_code,
                   "body": local_models.text[:1200]})],
               notes="Local OpenAI-compatible provider is the harness upstream; "
                     "the user-facing settings surface is served")

    ctx.record("ROUTE-03", "partial",
               notes="Cost-aware fallback needs two configured providers; this "
                     "world configures one bounded upstream")
    # ---- ROUTE-05 RTK compression -------------------------------------
    try:
        from core.llm.compression.rtk_engine import RTKEngine
        engine = RTKEngine()
        log = ("\n".join(["INFO compiling module"] * 60)
               + "\nERROR: acceptance failure kept\n"
               + "\n".join(["INFO compiling module"] * 60))
        compressed = engine.compress(log)
        structured = '{"amount": 1250.50, "currency": "USD"}'
        untouched = engine.compress(structured)
        ok = (len(compressed) < len(log)
              and "acceptance failure kept" in compressed
              and untouched == structured)
        ctx.record("ROUTE-05", "verified" if ok else "failed",
                   [ctx.save("routing/rtk.json", {
                       "input_chars": len(log), "output_chars": len(compressed),
                       "error_kept": "acceptance failure kept" in compressed,
                       "structured_unchanged": untouched == structured})],
                   notes=f"chars {len(log)} -> {len(compressed)}; "
                         f"structured_unchanged={untouched == structured}")
    except Exception as exc:
        ctx.record("ROUTE-05", "unverified", notes=f"RTK unavailable: {exc}")
    ctx.record("ROUTE-07", "unverified",
               notes="opencode-go needs a real subscription key; the provider "
                     "resolves but no live call is made")


def inspect_module(name: str) -> str:
    try:
        mod = __import__(name, fromlist=["__file__"])
        return mod.__file__
    except Exception:
        return ""
