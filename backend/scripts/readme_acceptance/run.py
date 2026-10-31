"""Run README feature acceptance groups against an isolated world.

Usage (from ``backend/``):
    python -m scripts.readme_acceptance.run --groups governance
    python -m scripts.readme_acceptance.run --groups all --merge
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "scripts.readme_acceptance"

from . import common

GROUPS = {
    "governance": "groups_governance:governance",
    "oracle": "groups_governance:oracle",
    "ask": "groups_governance:ask",
    "agent-teams": "groups_governance:agent_teams",
    "radio": "groups_radio:radio",
    "workflows": "groups_workflows:workflows",
    "data": "groups_data:data_group",
    "memory": "groups_data:memory_group",
    "office": "groups_office:office",
    "graphrag": "groups_graphrag:graphrag",
    "goals": "groups_graphrag:goals",
    "interop": "groups_interop:interop",
    "gateway": "groups_gateway:gateway",
    "integrations": "groups_integrations:integrations",
    "mini-apps": "groups_miniapp:mini_apps",
    "security": "groups_miniapp:security",
    "core": "groups_core:core_workspace",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--groups", default="all")
    parser.add_argument("--out", type=Path,
                        default=common.EVIDENCE / "README_ACCEPTANCE_RESULTS.json")
    parser.add_argument("--merge", action="store_true",
                        help="also rewrite the claim inventory with these results")
    parser.add_argument("--keep-world", action="store_true")
    args = parser.parse_args()

    selected = list(GROUPS) if args.groups == "all" else [
        g.strip() for g in args.groups.split(",") if g.strip()]
    unknown = [g for g in selected if g not in GROUPS]
    if unknown:
        raise SystemExit(f"unknown groups: {unknown}")

    common.prepare_world(reset=not args.keep_world)
    # Bounded local upstream: gateway + provider routing + (scripted) agent
    # loops use this, never a cloud API.
    from . import mock_llm_server
    llm = mock_llm_server.Server(59997).start()
    os.environ["OLLAMA_BASE_URL"] = llm.base_url
    os.environ["OPENAI_BASE_URL"] = llm.base_url
    os.environ["ATOM_HARNESS_LLM_URL"] = llm.base_url
    # Expose the bounded server so a scenario can force a real transport
    # failure (error-propagation acceptance) and restart it.
    _HARNESS_STATE = {"llm_server": llm}
    # Controlled OAuth provider (consent + code exchange) for one provider.
    os.environ.update({
        "GITHUB_CLIENT_ID": "acceptance-github-client",
        "GITHUB_CLIENT_SECRET": "acceptance-github-secret",
        "GITHUB_AUTHORIZE_URL": "http://127.0.0.1:59997/github/authorize",
        "GITHUB_TOKEN_URL": "http://127.0.0.1:59997/github/token",
        "GITHUB_REDIRECT_URI": "http://127.0.0.1:8001/api/v1/auth/oauth/github/callback",
        "FRONTEND_URL": "http://127.0.0.1:3001",
    })
    from fastapi.testclient import TestClient
    from main_api_app import app

    results = []
    failures = []
    started = datetime.now(timezone.utc)
    # Workflow definitions are file-backed at backend/workflows.json. Keep the
    # acceptance fixtures inside the throwaway world instead of the repo file.
    import core.workflow_endpoints as _wfe
    world_workflows = common.WORLD / "workflows.json"
    world_workflows.write_text("[]\n")
    _wfe.WORKFLOWS_FILE = str(world_workflows)
    try:
        import api.workflow_versioning_endpoints as _wve
        import json as _json

        async def _world_workflow_data(workflow_id):
            try:
                rows = _json.loads(world_workflows.read_text() or "[]")
            except Exception:
                rows = []
            return next((w for w in rows if w.get("id") == workflow_id), None) or {
                "steps": [], "parameters": {}, "dependencies": [], "metadata": {}}

        _wve.get_workflow_data = _world_workflow_data
    except Exception:
        pass

    with TestClient(app) as client:
        token = ""
        headers = {}
        # login needs a Ctx; build a placeholder then fill identity rows
        ctx = common.Ctx(client=client, headers=headers, token=token,
                         admin_id="", tenant_id="", workspace_id="",
                         world=common.WORLD, evidence=common.EVIDENCE)
        ctx.cache["llm_server"] = llm
        common.login(ctx)
        from core.models import User, Workspace
        db = ctx.db()
        try:
            user = db.query(User).filter(User.email == common.ADMIN_EMAIL).first()
            ws = db.query(Workspace).first()
            ctx.admin_id = user.id
            ctx.tenant_id = (getattr(user, "tenant_id", None)
                             or (getattr(ws, "tenant_id", None) if ws else None)
                             or "default_tenant")
            ctx.workspace_id = (getattr(user, "workspace_id", None)
                                or (ws.id if ws else None)
                                or "default")
            # Bind the operator to the default tenant/workspace so BYOK,
            # graph partitions, memory and gateway identity all resolve the
            # same scope (a NULL user.tenant_id made the gateway unable to see
            # the key it had just stored).
            user.tenant_id = ctx.tenant_id
            user.workspace_id = ctx.workspace_id
            # Acceptance world: the operator account needs every role-gated
            # surface (SSO config is super_admin). This does not weaken the
            # RBAC scenario, which uses a separate member account.
            user.role = "super_admin"
            db.commit()
        finally:
            db.close()
        for name in selected:
            module_name, func_name = GROUPS[name].split(":")
            started_group = len(ctx.results)
            print(f"[group] {name}", flush=True)
            try:
                module = importlib.import_module(f".{module_name}", __package__)
                getattr(module, func_name)(ctx)
                print(f"[group] {name}: done", flush=True)
            except Exception as exc:
                traceback.print_exc()
                failures.append({"group": name, "error": repr(exc)})
                print(f"[group] {name}: ERROR {exc}", flush=True)
            finally:
                new = ctx.results[started_group:]
                results.extend(new)
                bad = [r for r in new if r["status"] == "failed"]
                print(f"[group] {name}: {len(new)} claims, {len(bad)} failed",
                      flush=True)

    payload = {
        "schema_version": 1,
        "harness": "backend/scripts/readme_acceptance",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "started_at": started.isoformat(),
        "config": {
            "world": str(common.WORLD),
            "database": str(common.WORLD / "atom.db"),
            "product_profile": "full",
            "external_integrations": "tokenless; schedulers/pollers off",
            "llm": "bounded local OpenAI-compatible stub (no cloud spend)",
        },
        "groups": {g: GROUPS[g] for g in selected},
        "group_errors": failures,
        "results": sorted(results, key=lambda r: r["claim_id"]),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    try:
        llm.stop()
    except Exception:
        pass
    try:
        ctx.cache.get("llm_server").stop()
    except Exception:
        pass
    by_status = {}
    for r in results:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    print(json.dumps({"claims": len(results), "by_status": by_status,
                      "out": str(args.out)}, indent=2))

    if args.merge:
        script = common.REPO / "scripts" / "acceptance" / "readme_claim_inventory.py"
        import subprocess
        subprocess.run([sys.executable, str(script), "--merge", str(args.out)], check=True)


if __name__ == "__main__":
    main()
