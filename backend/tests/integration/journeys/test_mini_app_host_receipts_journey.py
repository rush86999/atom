"""Real-auth producer controls for the supported mini-app host writes.

This walks the public RPC surface a normal authenticated member uses. It is a
producer control, not an ORACLE acceptance claim: the assignment-executor
verifier twins live in ``tests/test_oracle_mini_app_host_mutations.py``.

Scaffold, logic write, revert, publish and install each append their receipt in
the same transaction as the host effect. ``mini_app_db_write`` keeps its
SUPERVISED+ maturity floor: a plain member RPC call is refused and writes no
record/receipt (the registered consumer path supplies an explicit tier).
"""
from __future__ import annotations

import time

SOURCE = "state = dict(state or {})\nstate['runs'] = state.get('runs', 0) + 1\n"


def _rpc(client, token, action, params):
    response = client.post(
        f"/api/rpc/{action}", json={"params": params},
        headers={"Authorization": "Bearer " + token})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_public_rpc_producers_write_bound_receipts(real_auth_client, registered_user):
    from core.database import SessionLocal
    from core.models import CanvasAudit, CanvasRecord

    client, _, _, token = registered_user
    scaffold = _rpc(client, token, "mini_app_scaffold", {
        "name": f"receipt-journey-{int(time.time())}",
        "declared_scopes": ["canvas_render"], "dependencies": []})
    assert scaffold["success"] is True, scaffold
    assert scaffold.get("audit_id")

    write = _rpc(client, token, "mini_app_write_logic", {
        "app_id": scaffold["app_id"], "source": SOURCE})
    assert write["success"] is True, write
    assert write.get("audit_id") and write.get("source_sha256")

    revert = _rpc(client, token, "mini_app_revert_logic", {
        "app_id": scaffold["app_id"], "version": write["version"]})
    assert revert["success"] is True, revert
    assert revert.get("audit_id")

    publish = _rpc(client, token, "mini_app_publish", {
        "app_id": scaffold["app_id"]})
    assert publish["success"] is True, publish
    assert publish.get("audit_id")

    install = _rpc(client, token, "mini_app_install", {
        "app_id": scaffold["app_id"]})
    assert install["success"] is True, install
    instance = install["canvas_id"]
    assert install.get("audit_id")

    with SessionLocal() as db:
        for action, receipt_id in (
                ("mini_app_scaffold", scaffold["audit_id"]),
                ("mini_app_logic", write["audit_id"]),
                ("mini_app_logic", revert["audit_id"]),
                ("mini_app_publish", publish["audit_id"]),
                ("mini_app_install", install["audit_id"])):
            row = db.query(CanvasAudit).filter(
                CanvasAudit.id == receipt_id).one()
            assert row.action_type == action, (action, row.action_type)
            assert row.details_json.get("request_sha256"), action
        assert db.query(CanvasAudit).filter(
            CanvasAudit.id == revert["audit_id"]
        ).one().details_json.get("reverted_to") == write["version"]

    # The SUPERVISED+ tier floor is not relaxed for the public RPC path: a
    # plain member cannot manufacture a record write (or a receipt for one).
    refused = _rpc(client, token, "mini_app_db_write", {
        "canvas_id": instance, "op": "append", "series": "ledger",
        "data": {"amount": 1}})
    assert refused["success"] is False
    assert "SUPERVISED" in refused.get("error", "")
    with SessionLocal() as db:
        assert db.query(CanvasRecord).filter(
            CanvasRecord.canvas_id == instance).count() == 0
        assert db.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == instance,
            CanvasAudit.action_type == "mini_app_db_write").count() == 0
