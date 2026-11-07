import asyncio
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.oracle import validate
from core.task_lifecycle import _approval_payload_hash

@pytest.mark.parametrize("field", ["workspace_id", "tenant_id", "created_by", "audit_tenant", "audit_actor"])
def test_authoritative_scope_contradiction_must_refute(tmp_path, field):
    from core.models import Canvas, CanvasAudit, MiniApp

    engine = create_engine(f"sqlite:///{tmp_path}/mini.db")
    for table in (Canvas.__table__, MiniApp.__table__, CanvasAudit.__table__):
        table.create(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    tests = [{"name": "proof", "expect_state": {"runs": 1}}]
    digest = _approval_payload_hash(tests)
    with Session() as db:
        canvas = Canvas(
            id="canvas-1", tenant_id="tenant-1", workspace_id="ws-1",
            created_by="user-1", name="App source", canvas_type="mini_app",
            content={})
        app = MiniApp(
            id="app-1", tenant_id="tenant-1", workspace_id="ws-1",
            created_by="user-1", name="App", manifest={"tests": tests},
            blueprint_canvas_id=canvas.id, status="draft")
        audit = CanvasAudit(
            id="audit-1", canvas_id=canvas.id, tenant_id="tenant-1",
            action_type="mini_app_set_tests", user_id="user-1",
            canvas_type="mini_app",
            details_json={
                "app_id": app.id, "tests_sha256": digest,
                "operation_id": "op-new", "workspace_id": "ws-1",
                "tenant_id": "tenant-1", "actor_id": "user-1",
            })
        db.add_all([canvas, app, audit])
        db.commit()

        base = {
            "db": db,
            "_oracle_expected_app_id": app.id,
            "_oracle_expected_tests": tests,
            "_oracle_expected_tests_sha256": digest,
            "_oracle_expected_operation_id": "op-new",
            "_oracle_expected_tenant_id": "tenant-1",
            "_oracle_expected_workspace_id": "ws-1",
            "_oracle_expected_actor_id": "user-1",
            "audit_id": audit.id,
        }
        good = asyncio.run(validate("mini_app_set_tests", base))
        assert good is not None and good.verified is True, good

        if field == "audit_tenant":
            audit.tenant_id = "peer-scope"
        elif field == "audit_actor":
            audit.user_id = "peer-actor"
        else:
            setattr(app, field, "peer-scope")
        db.commit()
        result = asyncio.run(validate("mini_app_set_tests", base))
        assert result is not None and result.verified is False, (field, result)
