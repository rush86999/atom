"""Real registered mini-app mutation: producer + independent verifier join.

This is the supported local-authoring action path exercised through the real
RPC scaffold, the real ``mini_app_set_tests`` producer and the shared
assignment adapter/oracle consumer. The store is the journey test's isolated
in-memory SQLite database.
"""
import asyncio


def _rpc(client, token, action, params):
    response = client.post(
        f"/api/rpc/{action}",
        json={"params": params},
        headers={"Authorization": "Bearer " + token},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_registered_mini_app_manifest_write_is_independently_verified(
        real_auth_client, registered_user):
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter
    from core.database import SessionLocal
    from core.models import CanvasAudit, MiniApp, User
    from core.oracle import get_postcondition

    client, email, _, token = registered_user
    scaffold = _rpc(client, token, "mini_app_scaffold",
                    {"name": "oracle-registry-proof", "dependencies": []})
    app_id = scaffold["app_id"]
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        user_id = str(user.id)
        tenant_id = str(user.tenant_id)
        workspace_id = str(user.workspace_id or "")
        app_row = db.query(MiniApp).filter(MiniApp.id == app_id).one()
        assert str(app_row.tenant_id) == tenant_id
        if app_row.workspace_id:
            workspace_id = str(app_row.workspace_id)

    name = "mini_app_set_tests"
    action = action_registry.get_action(name)
    assert action is not None
    assert action.effects == [{"effect": "update", "scope": "local"}]
    assert get_postcondition(name) is not None

    cases = [{"name": "proof", "inputs": {},
              "expect_state": {"runs": 1}}]
    result = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": {"app_id": app_id, "tests": cases}},
        {"employee_id": user_id, "run_id": "real-oracle-run",
         "workspace_id": workspace_id, "tenant_id": tenant_id,
         "step": {"effect": "local", "operation_id": "real-oracle-op-1"}}))
    assert result["status"] == "applied", result
    assert result["oracle_verified"] is True, result
    audit_id = result["data"].get("audit_id")
    assert audit_id, result

    with SessionLocal() as db:
        saved = db.query(MiniApp).filter(MiniApp.id == app_id).one()
        assert saved.manifest["tests"] == cases
        audit = db.query(CanvasAudit).filter(
            CanvasAudit.id == audit_id).one()
        assert audit.action_type == "mini_app_set_tests"
        assert audit.details_json["operation_id"] == "real-oracle-op-1"
        assert audit.details_json["app_id"] == app_id

    # A second, distinct operation with the same accepted tests is still a new
    # operation: the durable audit receipt carries the new operation id and the
    # verifier does not accept the earlier row.
    second = asyncio.run(_action_registry_adapter(
        {"action": name, "arguments": {"app_id": app_id, "tests": cases}},
        {"employee_id": user_id, "run_id": "real-oracle-run",
         "workspace_id": workspace_id, "tenant_id": tenant_id,
         "step": {"effect": "local", "operation_id": "real-oracle-op-2"}}))
    assert second["status"] == "applied", second
    assert second["oracle_verified"] is True, second
    assert second["data"].get("audit_id") != audit_id
