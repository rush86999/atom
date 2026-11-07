import sqlite3
import pytest

@pytest.mark.asyncio
async def test_mutation_without_independent_verifier_cannot_certify_applied(tmp_path, monkeypatch):
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter
    from core.oracle import get_postcondition
    monkeypatch.setattr(action_registry, "_actions", dict(action_registry._actions))
    path = tmp_path / "effect.db"
    with sqlite3.connect(path) as db:
        db.execute("create table effects (value integer)")
    async def write(args, context):
        with sqlite3.connect(path) as db:
            db.execute("insert into effects values (?)", (args["value"],))
        return {"status": "success", "action_result": "applied",
                "remote_id": "local-effect",
                "verification": {"status": "verified", "verified": True}}
    name = "lead_probe.unverified_mutation"
    action_registry.register(name, write, effects=[{"effect": "write"}])
    assert get_postcondition(name) is None
    result = await _action_registry_adapter(
        {"action": name, "arguments": {"value": 7}},
        {"workspace_id": "proof-ws", "tenant_id": "proof-tenant",
         "employee_id": "proof-owner", "run_id": "proof-run",
         "step": {"effect": "local", "operation_id": "proof-op"}})
    with sqlite3.connect(path) as db:
        assert db.execute("select value from effects").fetchall() == [(7,)]
    assert result["status"] != "applied", result

@pytest.mark.asyncio
async def test_read_without_mutation_verifier_still_works(monkeypatch):
    from core.action_registry import action_registry
    from core.assignment_executor import _action_registry_adapter
    monkeypatch.setattr(action_registry, "_actions", dict(action_registry._actions))
    async def read(args, context):
        return {"status": "success", "value": 7}
    name = "lead_probe.read"
    action_registry.register(name, read, effects=[{"effect": "read"}])
    result = await _action_registry_adapter(
        {"action": name, "arguments": {}}, {"step": {"effect": "read"}})
    assert result["status"] == "applied", result
