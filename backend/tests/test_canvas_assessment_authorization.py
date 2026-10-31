"""Downstream use of an assessment requires an authorized review.

The verifier's boundary: an assessment that needs review must not become an
authorized decision by being handed to a caller, and a human approval must be
bound to the exact assessment, source revision and policy revision.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import Canvas


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def canvas(db):
    row = Canvas(
        id="canvas_review_1", tenant_id="default", workspace_id="ws-1",
        created_by="user-1", name="Review", canvas_type="sheet",
        content={}, status="active",
    )
    db.add(row)
    db.commit()
    return row


@pytest.fixture()
def user():
    return SimpleNamespace(
        id="user-1", workspace_id="ws-1", tenant_id="default",
        role="workspace_admin",
    )


def _manifest(policy=None):
    return {
        "schema_version": 1,
        "base_component": "table",
        "operations": [
            "read", "select", "calculate", "assess", "edit", "export", "bind",
        ],
        "data_binding": {
            "subject_field": "Ref", "measure_field": "Amount",
            "status_field": "Status",
        },
        "editable_fields": ["Amount", "Status"],
        "teaching_binding": {"agent_id": "agent-1", "scope_id": "task-1"},
        "decision_options": ["APPROVE", "REVIEW", "DENY"],
        "task_policy": policy or (
            "Approve Amount >= 100 when Status is Open. Review 50-99. "
            "Deny below 50 or Closed."
        ),
        "outputs": ["xlsx"],
        "required_approvals": [],
    }


def _bind(db, canvas, user):
    from core.canvas_capability_service import bind_dataset, set_manifest

    set_manifest(db, canvas, user, _manifest())
    return bind_dataset(
        db, canvas, user,
        ["Ref", "Amount", "Status", "Note"],
        [
            ["R-1", 120, "Open", "alpha"],
            ["R-2", 75, "Open", "beta"],
            ["R-3", 20, "Closed", "gamma"],
            ["R-4", 95, "Open", "delta"],
        ],
        source={"file_name": "review.csv", "sha256": "fixture-sha"},
    )


def _fake_review(monkeypatch, unresolved=None):
    from core import review_result

    unresolved = unresolved or {}

    async def fake_generate(llm, **kwargs):
        rev = _FAKE_REV["revision"]
        assessments = []
        for subject, decision in (
            ("R-1", "APPROVE"), ("R-2", "REVIEW"),
            ("R-3", "DENY"), ("R-4", "REVIEW"),
        ):
            assessments.append({
                "subject_id": subject,
                "decision": decision,
                "basis": ["fixture"],
                "evidence_ids": [
                    f"ev:{subject}:{_FAKE_REV['rows'][subject]}"],
                "policy_ids": [f"policy:{rev}"],
                "unresolved_requirements": list(unresolved.get(subject, [])),
            })
        return "```review_result\n" + json.dumps(
            {"assessments": assessments}) + "\n```"

    monkeypatch.setenv("ATOM_REVIEW_MODEL", "deepseek-flash")
    monkeypatch.setattr(review_result, "generate_structured_review", fake_generate)
    review_result.LAST_STRUCTURED_REVIEW.update(
        ok=True, dispatched=True, failure_kind=None, failure_stage=None,
        served_provider="ollama", served_model="llama3.1:8b")


_FAKE_REV = {}


def _assess(db, canvas, user):
    from core.canvas_capability_service import (
        assess_operation, get_manifest, policy_revision,
    )

    _FAKE_REV["revision"] = policy_revision(get_manifest(canvas))
    _FAKE_REV["rows"] = {"R-1": 2, "R-2": 3, "R-3": 4, "R-4": 5}
    return asyncio.run(assess_operation(
        db, canvas, user, "all rows", llm_service=object()))


def test_unreviewed_recommendation_blocks_downstream_decisions(
        db, canvas, user, monkeypatch):
    from core.canvas_capability_service import (
        CapabilityError, decisions_operation,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch, unresolved={"R-4": ["Amount 95 is below the band; confirm."]})
    result = _assess(db, canvas, user)

    assert result["certified"] is True
    assert result["review_required"] is True
    assert result["authorization"]["state"] == "review_required"

    with pytest.raises(CapabilityError) as exc:
        decisions_operation(canvas)
    assert exc.value.code == "review_required"
    assert exc.value.extra["authorization"]["unresolved_subjects"] == ["R-4"]


def test_human_approval_binds_to_the_exact_assessment(
        db, canvas, user, monkeypatch):
    from core.canvas_capability_service import (
        approve_assessment, decisions_operation,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch, unresolved={"R-4": ["Confirm the amount."]})
    result = _assess(db, canvas, user)

    approved = approve_assessment(db, canvas, user, result["execution_id"])
    assert approved["authorization"]["state"] == "authorized"
    approval = approved["authorization"]["approval"]
    assert approval["execution_fingerprint"] == result["execution_fingerprint"]
    assert approval["policy_revision"] == result["policy_revision"]
    assert approval["source_revision"] == result["source_revision"]
    assert approval["approved_by"] == "user-1"
    assert len(approval["assessment_content_sha256"]) == 64

    decisions = decisions_operation(canvas)
    assert decisions["decisions"] == {
        "R-1": "APPROVE", "R-2": "REVIEW", "R-3": "DENY", "R-4": "REVIEW"}
    assert decisions["authorization"]["state"] == "authorized"


def test_changed_assessment_after_approval_requires_fresh_review(
        db, canvas, user, monkeypatch):
    from core.canvas_capability_service import (
        CapabilityError, approve_assessment, decisions_operation,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch, unresolved={"R-4": ["Confirm the amount."]})
    first = _assess(db, canvas, user)
    approve_assessment(db, canvas, user, first["execution_id"])
    assert decisions_operation(canvas)["success"] is True

    # A new assessment is a new execution: the earlier approval must not carry.
    second = _assess(db, canvas, user)
    assert second["execution_id"] != first["execution_id"]
    with pytest.raises(CapabilityError) as exc:
        decisions_operation(canvas)
    assert exc.value.code == "review_required"
    assert exc.value.extra["authorization"]["state"] == "review_required"


def test_a_stale_approval_cannot_authorize_a_new_execution(
        db, canvas, user, monkeypatch):
    from core.canvas_capability_service import (
        CapabilityError, approve_assessment, get_manifest, policy_revision,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch, unresolved={"R-4": ["Confirm the amount."]})
    result = _assess(db, canvas, user)
    approve_assessment(db, canvas, user, result["execution_id"])

    # APPROVING a different execution id is refused: the approval is bound to
    # the one that was actually reviewed.
    with pytest.raises(CapabilityError) as exc:
        approve_assessment(db, canvas, user, "some-other-execution")
    assert exc.value.code == "stale_assessment"


def _mutate_record(canvas, db, mutate):
    """Change the persisted artifact WITHOUT touching the stored digest."""
    import copy
    from core.canvas_capability_service import _canvas_content

    content = copy.deepcopy(_canvas_content(canvas))
    mutate(content["assessment_review"])
    canvas.content = content
    db.commit()


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda record: record["assessments"][0].__setitem__(
                "decision", "DENY"),
            id="decision",
        ),
        pytest.param(
            lambda record: record["assessments"][0]["basis"].append(
                "forged basis"),
            id="basis",
        ),
        pytest.param(
            lambda record: record["assessments"][0]["evidence"].append(
                {"evidence_id": "ev:forged", "row_ref": "row 99", "values": []}),
            id="evidence",
        ),
        pytest.param(
            lambda record: record["assessments"][0][
                "unresolved_requirements"].append("forged requirement"),
            id="unresolved",
        ),
    ],
)
def test_content_drift_with_an_untouched_hash_requires_fresh_review(
        db, canvas, user, monkeypatch, mutate):
    """The verifier's bypass: swap content, leave the digest as it was."""
    from core.canvas_capability_service import (
        CapabilityError, approve_assessment, decisions_operation,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch)
    result = _assess(db, canvas, user)
    approve_assessment(db, canvas, user, result["execution_id"])
    assert decisions_operation(canvas)["success"] is True

    # The stored digest is deliberately left untouched.
    _mutate_record(canvas, db, mutate)

    with pytest.raises(CapabilityError) as exc:
        decisions_operation(canvas)
    assert exc.value.code == "review_required"
    assert exc.value.extra["authorization"]["state"] == "content_drift"


def test_approval_refuses_content_drift(db, canvas, user, monkeypatch):
    from core.canvas_capability_service import (
        CapabilityError, approve_assessment,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch)
    result = _assess(db, canvas, user)
    _mutate_record(
        canvas, db,
        lambda record: record["assessments"][0].__setitem__(
            "decision", "DENY"))

    with pytest.raises(CapabilityError) as exc:
        approve_assessment(db, canvas, user, result["execution_id"])
    assert exc.value.code == "assessment_content_changed"


def test_unchanged_approved_content_survives_reload(db, canvas, user, monkeypatch):
    """Positive control: approval survives a fresh session/read."""
    from sqlalchemy.orm import sessionmaker

    from core.canvas_capability_service import (
        approve_assessment, decisions_operation,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch)
    result = _assess(db, canvas, user)
    approve_assessment(db, canvas, user, result["execution_id"])
    expected = decisions_operation(canvas)["decisions"]

    fresh = sessionmaker(bind=db.get_bind())()
    try:
        reloaded = fresh.query(Canvas).filter(Canvas.id == canvas.id).first()
        decisions = decisions_operation(reloaded)
        assert decisions["decisions"] == expected
        assert decisions["authorization"]["state"] == "authorized"
        assert decisions["assessment_content_sha256"] == result[
            "execution_id"] or decisions["assessment_content_sha256"]
    finally:
        fresh.close()


def test_canvas_change_after_approval_requires_fresh_review(
        db, canvas, user, monkeypatch):
    """CAS: any data revision change invalidates the approval."""
    from core.canvas_capability_service import (
        CapabilityError, approve_assessment, decisions_operation, edit_operation,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch)
    result = _assess(db, canvas, user)
    approve_assessment(db, canvas, user, result["execution_id"])

    edit_operation(
        db, canvas, user,
        [{"row": 2, "column": "Amount", "value": 130}],
        expected_revision=1,
    )
    with pytest.raises(CapabilityError) as exc:
        decisions_operation(canvas)
    assert exc.value.code == "review_required"
    assert exc.value.extra["authorization"]["state"] == "stale_assessment"


def test_policy_change_after_approval_requires_fresh_review(
        db, canvas, user, monkeypatch):
    from core.canvas_capability_service import (
        CapabilityError, approve_assessment, decisions_operation, set_manifest,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch, unresolved={"R-4": ["Confirm the amount."]})
    result = _assess(db, canvas, user)
    approve_assessment(db, canvas, user, result["execution_id"])
    assert decisions_operation(canvas)["success"] is True

    set_manifest(db, canvas, user, _manifest(
        policy="Approve Amount >= 200 when Status is Open. Review otherwise."))
    with pytest.raises(CapabilityError) as exc:
        decisions_operation(canvas)
    assert exc.value.code == "review_required"
    assert exc.value.extra["authorization"]["state"] == "stale_assessment"


def test_default_policy_requires_review_even_when_certified_and_uncertainty_free(
        db, canvas, user, monkeypatch):
    """A confident, wrong assessment reports no uncertainty — review anyway."""
    from core.canvas_capability_service import (
        CapabilityError, decisions_operation,
    )

    monkeypatch.delenv("ATOM_ASSESSMENT_REVIEW_POLICY", raising=False)
    _bind(db, canvas, user)
    # Certified, every subject resolved, no reported uncertainty at all.
    _fake_review(monkeypatch)
    result = _assess(db, canvas, user)

    assert result["certified"] is True
    assert result["review_required"] is True
    assert "review_policy_always" in result["review_reasons"]
    assert result["authorized"] is False
    assert result["rendered"] == ""
    assert result["rendered_suppressed"] is True

    with pytest.raises(CapabilityError) as exc:
        decisions_operation(canvas)
    assert exc.value.code == "review_required"


SERVING = {"base_url": "http://127.0.0.1:11435/v1", "request_timeout": "1800"}


def _write_registry(tmp_path, monkeypatch, *, status, revoked=False,
                    policy=None, contract="review-result-2"):
    import json as _json

    path = tmp_path / "assessment_qualification.json"
    path.write_text(_json.dumps({
        "schema": "atom-assessment-qualification-1",
        "configurations": [{
            "id": "unit-config",
            "capability": "canvas_assessment.model_judgment",
            "provider": "ollama",
            "model": "llama3.1:8b",
            "contract_version": contract,
            "status": status,
            "revoked": revoked,
            "evidence": "unit",
            "scope": {
                "task_policy": policy or _manifest()["task_policy"],
                "decision_options": ["APPROVE", "REVIEW", "DENY"],
                "subject_field": "Ref",
            },
            "serving": dict(SERVING),
        }],
    }))
    monkeypatch.setenv("ATOM_ASSESSMENT_QUALIFICATION_FILE", str(path))
    monkeypatch.setenv("OLLAMA_BASE_URL", SERVING["base_url"])
    monkeypatch.setenv("OLLAMA_REQUEST_TIMEOUT", SERVING["request_timeout"])
    return path


def test_scoped_policy_requires_a_qualified_configuration(
        db, canvas, user, monkeypatch):
    """A failed configuration cannot earn autonomy under scoped policy."""
    from core.canvas_capability_service import decisions_operation

    monkeypatch.setenv("ATOM_ASSESSMENT_REVIEW_POLICY", "scoped")
    _bind(db, canvas, user)
    _fake_review(monkeypatch)
    result = _assess(db, canvas, user)

    assert result["review_required"] is True
    assert "qualification_required" in result["review_reasons"]
    assert result["qualification"]["status"] == "failed"
    with pytest.raises(Exception) as exc:
        decisions_operation(canvas)
    assert exc.value.code == "review_required"


def test_scoped_policy_with_qualification_and_owner_autonomy_executes(
        db, canvas, user, monkeypatch, tmp_path):
    """Qualified configuration AND owner policy, both required."""
    from core import autonomy_policy
    from core.canvas_capability_service import decisions_operation

    monkeypatch.setenv("ATOM_ASSESSMENT_REVIEW_POLICY", "scoped")
    _write_registry(tmp_path, monkeypatch, status="qualified")
    monkeypatch.setattr(
        autonomy_policy, "gate_for_topic",
        lambda *a, **k: {"outcome": "execute"})
    _bind(db, canvas, user)
    _fake_review(monkeypatch)
    result = _assess(db, canvas, user)

    assert result["review_required"] is False
    assert result["authorization"]["state"] == "authorized"
    assert decisions_operation(canvas, db=db)["decisions"]["R-1"] == "APPROVE"


def test_scoped_policy_still_requires_owner_autonomy(
        db, canvas, user, monkeypatch, tmp_path):
    """A qualified model cannot grant itself the owner's permission."""
    from core import autonomy_policy

    monkeypatch.setenv("ATOM_ASSESSMENT_REVIEW_POLICY", "scoped")
    _write_registry(tmp_path, monkeypatch, status="qualified")
    monkeypatch.setattr(
        autonomy_policy, "gate_for_topic",
        lambda *a, **k: {"outcome": "propose"})
    _bind(db, canvas, user)
    _fake_review(monkeypatch)
    result = _assess(db, canvas, user)

    assert result["review_required"] is True
    assert "autonomy_policy_denied" in result["review_reasons"]


def test_revoked_qualification_stops_consumption(
        db, canvas, user, monkeypatch, tmp_path):
    """Registry revocation takes effect without a new assessment."""
    from core import autonomy_policy
    from core.canvas_capability_service import (
        CapabilityError, decisions_operation,
    )

    monkeypatch.setenv("ATOM_ASSESSMENT_REVIEW_POLICY", "scoped")
    registry = _write_registry(tmp_path, monkeypatch, status="qualified")
    monkeypatch.setattr(
        autonomy_policy, "gate_for_topic",
        lambda *a, **k: {"outcome": "execute"})
    _bind(db, canvas, user)
    _fake_review(monkeypatch)
    result = _assess(db, canvas, user)
    assert result["review_required"] is False
    assert decisions_operation(canvas, db=db)["success"] is True

    _write_registry(tmp_path, monkeypatch, status="qualified", revoked=True)
    with pytest.raises(CapabilityError) as exc:
        decisions_operation(canvas, db=db)
    assert exc.value.code == "review_required"
    assert exc.value.extra["authorization"]["state"] == "revoked"


def test_approval_is_bound_to_the_assessment_content(
        db, canvas, user, monkeypatch):
    """A changed decision invalidates the approval, not just a new execution."""
    from core.canvas_capability_service import (
        CapabilityError, _canvas_content, approve_assessment,
        decisions_operation,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch)
    result = _assess(db, canvas, user)
    approve_assessment(db, canvas, user, result["execution_id"])
    assert decisions_operation(canvas)["success"] is True

    # Simulate the assessment content changing under an unchanged execution
    # identity: the content hash no longer matches the approved one.
    import copy

    content = copy.deepcopy(_canvas_content(canvas))
    record = content["assessment_review"]
    record["assessment_content_sha256"] = "tampered"
    canvas.content = content
    db.commit()

    with pytest.raises(CapabilityError) as exc:
        decisions_operation(canvas)
    assert exc.value.code == "review_required"


def test_owner_authority_withdrawal_blocks_consumption(
        db, canvas, user, monkeypatch, tmp_path):
    """Changing the owner gate execute -> propose must stop consumption now."""
    from core import autonomy_policy
    from core.canvas_capability_service import (
        CapabilityError, decisions_operation,
    )

    monkeypatch.setenv("ATOM_ASSESSMENT_REVIEW_POLICY", "scoped")
    _write_registry(tmp_path, monkeypatch, status="qualified")
    gate = {"outcome": "execute"}
    monkeypatch.setattr(
        autonomy_policy, "gate_for_topic", lambda *a, **k: dict(gate))

    _bind(db, canvas, user)
    _fake_review(monkeypatch)
    result = _assess(db, canvas, user)
    assert result["review_required"] is False
    assert decisions_operation(canvas, db=db)["success"] is True

    # The owner withdraws authority; the stored review_required=false must not
    # keep the decision consumable.
    gate["outcome"] = "propose"
    with pytest.raises(CapabilityError) as exc:
        decisions_operation(canvas, db=db)
    assert exc.value.code == "review_required"
    assert exc.value.extra["authorization"]["state"] == "authority_withdrawn"

    # Still withdrawn after a reload from a fresh session.
    from sqlalchemy.orm import sessionmaker

    fresh = sessionmaker(bind=db.get_bind())()
    try:
        reloaded = fresh.query(Canvas).filter(Canvas.id == canvas.id).first()
        with pytest.raises(CapabilityError) as exc2:
            decisions_operation(reloaded, db=fresh)
        assert exc2.value.extra["authorization"]["state"] == "authority_withdrawn"
    finally:
        fresh.close()

    # An unrelated capability is not affected by withdrawing this authority.
    from core.canvas_capability_service import edit_operation

    edited = edit_operation(
        db, canvas, user,
        [{"row": 2, "column": "Amount", "value": 130}],
        expected_revision=1,
    )
    assert edited["success"] is True


def test_qualified_configuration_is_scoped_to_its_policy(
        db, canvas, user, monkeypatch, tmp_path):
    """A model name must not authorize an arbitrary policy."""
    from core import autonomy_policy

    monkeypatch.setenv("ATOM_ASSESSMENT_REVIEW_POLICY", "scoped")
    _write_registry(
        tmp_path, monkeypatch, status="qualified",
        policy="Approve everything above 10. Deny nothing.")
    monkeypatch.setattr(
        autonomy_policy, "gate_for_topic",
        lambda *a, **k: {"outcome": "execute"})
    _bind(db, canvas, user)
    _fake_review(monkeypatch)
    result = _assess(db, canvas, user)

    assert result["review_required"] is True
    assert "qualification_required" in result["review_reasons"]
    assert "policy_out_of_scope" in result["qualification"]["scope_reasons"]


def test_qualified_configuration_requires_its_contract_version(
        db, canvas, user, monkeypatch, tmp_path):
    from core import autonomy_policy

    monkeypatch.setenv("ATOM_ASSESSMENT_REVIEW_POLICY", "scoped")
    _write_registry(
        tmp_path, monkeypatch, status="qualified",
        contract="review-result-1")
    monkeypatch.setattr(
        autonomy_policy, "gate_for_topic",
        lambda *a, **k: {"outcome": "execute"})
    _bind(db, canvas, user)
    _fake_review(monkeypatch)
    result = _assess(db, canvas, user)

    assert result["review_required"] is True
    assert "contract_version_mismatch" in result["qualification"]["scope_reasons"]


def test_scoped_consumption_without_a_session_fails_closed(
        db, canvas, user, monkeypatch, tmp_path):
    from core import autonomy_policy
    from core.canvas_capability_service import (
        CapabilityError, assessment_authorization,
    )

    monkeypatch.setenv("ATOM_ASSESSMENT_REVIEW_POLICY", "scoped")
    _write_registry(tmp_path, monkeypatch, status="qualified")
    monkeypatch.setattr(
        autonomy_policy, "gate_for_topic",
        lambda *a, **k: {"outcome": "execute"})
    _bind(db, canvas, user)
    _fake_review(monkeypatch)
    _assess(db, canvas, user)

    state = assessment_authorization(canvas)
    assert state["state"] == "authority_unverified"


def test_a_different_owner_cannot_consume_the_assessment(
        db, canvas, user, monkeypatch):
    from core.canvas_capability_service import (
        CapabilityError, approve_assessment, decisions_operation,
    )

    _bind(db, canvas, user)
    _fake_review(monkeypatch)
    result = _assess(db, canvas, user)
    approve_assessment(db, canvas, user, result["execution_id"])

    other = SimpleNamespace(
        id="other-user", workspace_id="ws-1", tenant_id="default",
        role="workspace_admin")
    with pytest.raises(CapabilityError) as exc:
        decisions_operation(canvas, db=db, user=other)
    assert exc.value.code == "authority_mismatch"
