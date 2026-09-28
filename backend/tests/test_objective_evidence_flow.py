from decimal import Decimal
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openpyxl import Workbook

from core.async_turn_continuation import (
    AsyncTurnContinuation,
    _latest_turn_contract,
)
from core.chat_canvas_editor import (
    CanvasEditPlan,
    CanvasPatchOp,
    apply_canvas_edit,
    artifact_observations,
    build_canvas_evidence_comparison,
    fetch_fresh_data_section,
)
from core.chat_tool_planner import (
    ToolPlan,
    _outlook_read_by_ids,
    ingested_row_source_observations,
    outlook_source_observations,
)
from core.task_outcome_contract import build_task_outcome
from integrations.chat_orchestrator import (
    ChatOrchestrator,
    _canvas_edit_shaped,
    _read_only_file_ask,
)
from core.workbook_read_artifact import (
    _comparison_number,
    build_source_comparison,
    designated_source_ids,
    inspect_workbook_bytes,
    observations_from_text,
    render_source_comparison,
    workbook_artifact_observations,
)


TARGETS = (
    "381",
    "U-22",
    "622",
    "SLE24-16",
    "GSL48-16",
    "GSL24-16",
    "SLE16-8",
    "U-38",
)

CURRENT_QUOTE = {
    "381": ("2902.00", "Roper Whitney"),
    "U-22": ("1777.00", "Linmac"),
    "622": ("2421.00", "Roper Whitney"),
    "SLE24-16": ("8880.00", "Tennsmith"),
    "GSL48-16": ("14166.00", "Tennsmith"),
    "GSL24-16": ("12838.00", "Tinknocker"),
    "SLE16-8": ("8040.00", "Tinknocker"),
    "U-38": ("2902.00", "Roper Whitney"),
}


def _workbook_bytes():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Historical"
    sheet.append(["Model", "Organization", "PRICE"])
    manufacturers = {
        "381": "Roper Whitney",
        "U-22": "Linmac",
        "622": "Roper Whitney",
        "SLE24-16": "Tennsmith",
        "GSL48-16": "Tennsmith",
        "GSL24-16": "Tinknocker",
        "SLE16-8": "Tinknocker",
        "U-38": "Roper Whitney",
    }
    values = {
        "U-22": 1777,
        "622": 2421,
        "SLE24-16": 8880,
        "GSL48-16": 14166,
        "GSL24-16": 12838,
        "SLE16-8": 8040,
        "U-38": 2902,
    }
    for target in TARGETS:
        sheet.append([target, manufacturers[target], values.get(target)])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _quote_observations():
    return [
        {
            "observation_id": f"quote:{target}",
            "entity_id": target,
            "entity_attributes": {"organization": manufacturer},
            "field": "price",
            "raw_value": f"${value}",
            "currency": "CAD",
            "unit": None,
            "basis": "FOB Woodstock; excluding taxes",
            "effective_date": "2026-09-18",
            "source": {
                "source_id": "supplier-quote-2026-09-18",
                "source_type": "supplier_quote",
                "version": "supplier-quote-2026-09-18",
                "subject": "Acme supplier quote",
            },
            "locator": {"message_id": "supplier-quote-2026-09-18"},
            "verification": "verified",
        }
        for target, (value, manufacturer) in CURRENT_QUOTE.items()
    ]


def _quote_observation(target: str) -> dict:
    return next(
        item for item in _quote_observations()
        if item["entity_id"] == target
    )


def test_eight_workbook_outcomes_compare_without_promoting_history():
    artifact = inspect_workbook_bytes(
        _workbook_bytes(),
        "Consolidated Price List 2019.xlsx",
        targets=list(TARGETS),
        requested_fields=["price"],
        resource_id="workbook-2019",
        source_metadata={"temporal_role": "historical"},
        ingested_at="2026-09-07T23:06:19Z",
    )
    workbook_observations = workbook_artifact_observations(artifact)

    assert len(artifact["coverage"]["outcomes"]) == 8
    assert len({
        observation["entity_id"]
        for observation in workbook_observations
    }) == 8
    no_381 = [
        observation
        for observation in workbook_observations
        if observation["entity_id"] == "381"
    ]
    assert no_381
    assert all(
        observation["verification"] == "field_missing"
        for observation in no_381
    )

    comparison = build_source_comparison(
        workbook_observations + _quote_observations(),
        requested_entities=list(TARGETS),
        requested_fields=["price"],
    )

    assert comparison["coverage"]["complete"] is False
    assert comparison["coverage"]["outcome_count"] == 8
    assert comparison["coverage"]["verified_numeric_matches"] == 7
    assert comparison["coverage"]["field_missing"] == 1
    assert comparison["actions"] == []
    assert any(
        "historical" in implication["statement"].lower()
        and "change" in implication["statement"].lower()
        for implication in comparison["implications"]
    )
    assert all(
        outcome["status"] != "comparable_match"
        for outcome in comparison["coverage"]["outcomes"]
    )

    quote_rows = "".join(
        f"<tr><td>{manufacturer} {target}</td><td>${value}</td></tr>"
        for target, (value, manufacturer) in CURRENT_QUOTE.items()
    )
    canvas_comparison = build_canvas_evidence_comparison(
        {
            "canvas_id": "quote-draft",
            "canvas_type": "email",
            "content": {
                "body": (
                    "<table><tr><th>Machine</th><th>Price</th></tr>"
                    f"{quote_rows}</table>"
                    "<p>All prices are in CAD, FOB Woodstock.</p>"
                )
            },
        },
        artifact,
        source_observations=_quote_observations(),
    )

    assert canvas_comparison["coverage"]["outcome_count"] == 8
    assert canvas_comparison["actions"] == []
    assert any(
        "no draft value should change" in item["statement"].casefold()
        for item in canvas_comparison["implications"]
    )

    rendered = render_source_comparison(comparison)
    assert "No draft value should change from the workbook evidence alone" in rendered
    assert "381" in rendered
    assert "currency" in rendered.lower()
    assert "basis" in rendered.lower()


@pytest.mark.asyncio
async def test_chat_acceptance_compares_eight_outcomes_without_mutation():
    artifact = inspect_workbook_bytes(
        _workbook_bytes(),
        "Consolidated Price List 2019.xlsx",
        targets=list(TARGETS),
        requested_fields=["price"],
        resource_id="workbook-2019",
        source_metadata={"temporal_role": "historical"},
        ingested_at="2026-09-07T23:06:19Z",
    )
    quote_rows = "".join(
        f"<tr><td>{manufacturer} {target}</td><td>${value}</td></tr>"
        for target, (value, manufacturer) in CURRENT_QUOTE.items()
    )
    canvas = {
        "canvas_id": "quote-draft",
        "canvas_type": "email",
        "title": "Supplier quote",
        "content": {
            "body": (
                "<table><tr><th>Machine</th><th>Price</th></tr>"
                f"{quote_rows}</table>"
                "<p>All prices are in CAD, FOB Woodstock.</p>"
            )
        },
    }
    message = (
        "Compare the eight machines in Consolidated Price List 2019.xlsx "
        "with the supplier quote in the draft and explain whether any "
        "draft values should change: " + ", ".join(TARGETS)
    )
    plan = ToolPlan(
        use_tool=True,
        service="datasets",
        intent="search",
        query=message,
        reason="objective requires comparison",
    )

    async def execute_tool_plan(*args, **kwargs):
        plan._result_meta["storage_read"] = {
            "service": "zoho_workdrive",
            "file_id": "workbook-2019",
            "resource_id": "workbook-2019",
            "file_name": "Consolidated Price List 2019.xlsx",
            "source": "zoho_workdrive",
            "content_hash": "workbook-hash",
            "content_hash_algorithm": "sha1",
            "ingested_at": "2026-09-07T23:06:19Z",
            "source_modified_at": None,
            "version_verified": True,
            "identity_verified": True,
            "coverage_complete": True,
            "completed": True,
            "workbook_read": artifact,
            "rendered_answer": "Eight structured workbook outcomes.",
        }
        return f"LIVE TOOL RESULTS (datasets.search, query='{plan.query}')\n"

    async def mail_evidence(_message, _user_id, context, plan_date=None):
        context["_source_observations"] = _quote_observations()
        return ["[ingested mailbox] verified supplier quote"]

    orchestrator = ChatOrchestrator()
    orchestrator.ai_engines = {}
    llm = MagicMock()
    llm.generate_completion = AsyncMock(
        side_effect=RuntimeError("narration unavailable")
    )
    orchestrator.llm_service = llm
    session = {"id": "objective-session", "history": []}
    finish = MagicMock()

    with (
        patch.object(
            orchestrator,
            "_get_or_create_session",
            return_value=session,
        ),
        patch.object(
            orchestrator,
            "_resolve_canvas_ctx",
            new=AsyncMock(return_value=canvas),
        ),
        patch.object(
            orchestrator,
            "_start_chat_execution",
            return_value="objective-exec",
        ),
        patch.object(
            orchestrator,
            "_record_chat_step",
            new=AsyncMock(),
        ),
        patch.object(
            orchestrator,
            "_emit_agent_status",
            new=AsyncMock(),
        ),
        patch.object(orchestrator, "_finish_chat_execution", finish),
        patch.object(orchestrator, "_update_session"),
        patch.object(orchestrator, "_try_canvas_edit", new=AsyncMock()) as edit,
        patch.object(
            orchestrator,
            "_create_file_mention_canvas",
            new=AsyncMock(return_value=None),
        ) as preview,
        patch.object(
            orchestrator,
            "_try_canvas_action",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            orchestrator,
            "_try_zoho_crm_write",
            new=AsyncMock(),
        ),
        patch.object(
            orchestrator,
            "_route_to_features",
            new=AsyncMock(return_value={}),
        ),
        patch.object(
            orchestrator,
            "_load_conversation_mail_handles",
            return_value=([], []),
        ),
        patch(
            "core.chat_mini_app_authoring.try_handle",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "core.chat_tool_planner._provenance_menu",
            new=AsyncMock(return_value=""),
        ),
        patch(
            "core.chat_tool_planner.plan_tool_use",
            new=AsyncMock(return_value=plan),
        ),
        patch(
            "core.chat_tool_planner.execute_tool_plan",
            new=AsyncMock(side_effect=execute_tool_plan),
        ),
        patch(
            "integrations.chat_orchestrator._verbatim_mail_evidence",
            new=AsyncMock(side_effect=mail_evidence),
        ),
        patch(
            "core.memory_context_assembler.assembly_enabled",
            return_value=False,
        ),
        patch(
            "core.chat_canvas_editor.apply_canvas_edit",
            new=AsyncMock(),
        ) as apply_edit,
    ):
        result = await orchestrator.process_chat_message(
            "user-1",
            message,
            "objective-session",
            context={"canvas": canvas},
        )

    edit.assert_not_called()
    preview.assert_not_called()
    apply_edit.assert_not_called()
    assert result["success"] is True
    assert result["model"] == "deterministic"
    assert "SOURCE COMPARISON" in result["message"]
    assert "No draft value should change" in result["message"]
    objective = result["data"]["objective_evidence"]
    assert objective["coverage"]["outcome_count"] == 8
    assert objective["coverage"]["verified_numeric_matches"] == 7
    assert objective["coverage"]["field_missing"] == 1
    assert objective["actions"] == []


def test_task_outcome_persists_objective_evidence_and_action_boundaries():
    outcome = build_task_outcome(
        objective="compare workbook values with the supplier quote",
        objective_state={
            "goal": "decide whether the quote draft should change",
            "target_entities": list(TARGETS),
            "requested_attributes": ["price"],
            "source_constraints": {"file": "Consolidated Price List 2019.xlsx"},
            "authorized_actions": ["read"],
        },
        evidence_ledger={
            "known": 7,
            "missing": 1,
            "conflicting": 0,
            "incomparable": 7,
            "covered": 8,
            "total": 8,
        },
        gaps=[{
            "entity_id": "381",
            "status": "field_missing",
            "reasons": ["field_missing"],
            "next_evidence_needed": "verified price for 381",
        }],
        implications=[{
            "statement": "No draft value should change from workbook evidence alone.",
            "verification": "derived",
            "evidence_refs": [{"source": {"source_id": "workbook-2019"}}],
        }],
        actions=[{
            "action_type": "edit_artifact",
            "entity_id": "U-22",
            "status": "not_authorized",
            "authorized": False,
            "applied": False,
            "evidence_refs": [{"source": {"source_id": "quote"}}],
        }],
    )

    assert outcome["objective_state"]["target_entities"] == list(TARGETS)
    assert outcome["evidence_ledger"]["covered"] == 8
    assert outcome["gaps"][0]["criterion_id"] == "381"
    assert outcome["implications"][0]["verification"] == "derived"
    assert outcome["actions"][0]["authorized"] is False
    assert outcome["actions"][0]["applied"] is False


def test_precomputed_comparison_criterion_does_not_skip_mutation_failure():
    outcome = build_task_outcome(
        objective="compare and update",
        objective_met=True,
        completion_criteria=[
            {"kind": "source_comparison"},
            {"kind": "mutation"},
        ],
        criterion_results=[{
            "criterion": "comparison complete",
            "met": True,
        }],
        mutation={"requested": True, "readback_matched": False},
        delivery={"delivered": True},
    )

    assert outcome["success_kinds"]["task_success"] is False
    assert outcome["success_kinds"]["task_success_basis"] == "criteria_not_met"


def test_unregistered_criterion_remains_unknown_despite_trusted_results():
    outcome = build_task_outcome(
        objective="compare and apply an unregistered policy",
        objective_met=True,
        completion_criteria=[
            {"kind": "source_comparison"},
            {"kind": "new_unregistered_policy"},
        ],
        criterion_results=[{
            "criterion": "comparison complete",
            "met": True,
            "verifier": "source_comparison",
        }],
        delivery={"delivered": True},
    )

    assert outcome["success_kinds"]["task_success"] is None
    assert outcome["success_kinds"]["task_success_basis"] == (
        "no_verifier:new_unregistered_policy"
    )


def test_orchestrator_persists_comparison_as_task_outcome():
    comparison = build_source_comparison(
        [
            {
                "observation_id": "inventory:a",
                "entity_id": "SKU-A",
                "field": "quantity",
                "raw_value": "12",
                "unit": "each",
                "source": {"source_id": "inventory"},
                "verification": "verified",
            },
            {
                "observation_id": "draft:a",
                "entity_id": "SKU-A",
                "field": "quantity",
                "raw_value": "10",
                "unit": "each",
                "source": {"source_id": "draft"},
                "verification": "verified",
            },
        ],
        requested_entities=["SKU-A"],
        requested_fields=["quantity"],
        artifact_source_ids=["draft"],
        decision_source_ids=["inventory"],
        authorized_actions=[],
    )
    orchestrator = ChatOrchestrator.__new__(ChatOrchestrator)
    outcome = orchestrator._build_turn_task_outcome(
        {
            "id": "session-1",
            "_pending_file_task": {
                "original_message": "compare inventory and draft quantity",
                "mention": "stock.xlsx",
                "status": "delivered",
            },
            "_pending_file_result": {
                "status": "delivered",
                "coverage_complete": True,
                "identity": {
                    "file_name": "stock.xlsx",
                    "resource_id": "stock-resource",
                    "content_hash": "stock-hash",
                    "identity_verified": True,
                },
            },
            "_objective_evidence": comparison,
        },
        "compare inventory and draft quantity",
        {
            "success": True,
            "message": "The draft is lower; no edit was authorized.",
            "model": "deterministic",
            "data": {"objective_evidence": comparison},
        },
        None,
        None,
        status="success",
        authorized_actions=["read"],
    )

    assert outcome["objective_state"]["target_entities"] == ["SKU-A"]
    assert outcome["evidence_ledger"]["conflicting"] == 1
    assert outcome["criterion_results"][0]["met"] is True
    assert outcome["actions"][0]["authorized"] is False
    assert outcome["success_kinds"]["task_success"] is True


def test_explicit_decision_source_can_propose_only_authorized_artifact_changes():
    observations = workbook_artifact_observations(
        inspect_workbook_bytes(
            _workbook_bytes(),
            "Consolidated Price List 2019.xlsx",
            targets=list(TARGETS),
            requested_fields=["price"],
            resource_id="workbook-2019",
            source_metadata={"temporal_role": "historical"},
        )
    )
    observations.extend(_quote_observations())
    observations.append({
        "observation_id": "draft:U-22",
        "entity_id": "U-22",
        "entity_attributes": {"organization": "Linmac"},
        "field": "price",
        "raw_value": "$1700.00",
        "currency": "CAD",
        "unit": None,
        "basis": "FOB Woodstock; excluding taxes",
        "effective_date": "2026-09-18",
        "source": {
            "source_id": "quote-draft",
            "source_type": "artifact",
        },
        "locator": {"row": 2, "column": "Price"},
        "verification": "verified",
    })

    comparison = build_source_comparison(
        observations,
        requested_entities=list(TARGETS),
        requested_fields=["price"],
        artifact_source_ids=["quote-draft"],
        decision_source_ids=["supplier-quote-2026-09-18"],
        authorized_actions=["edit_artifact"],
    )

    assert len(comparison["actions"]) == 1
    action = comparison["actions"][0]
    assert action["entity_id"] == "U-22"
    assert action["current_value"] == "$1700.00"
    assert action["proposed_value"] == "$1777.00"
    assert action["status"] == "ready"
    assert action["evidence_ids"]


@pytest.mark.asyncio
async def test_authorized_source_backed_edit_is_read_back_verified():
    current = {
        "body": (
            "<table><tr><th>Machine</th><th>Price</th></tr>"
            "<tr><td>Linmac U-22</td><td>$1,700.00</td></tr></table>"
        )
    }
    updated = {
        "body": (
            "<table><tr><th>Machine</th><th>Price</th></tr>"
            "<tr><td>Linmac U-22</td><td>$1,777.00</td></tr></table>"
        )
    }
    plan = CanvasEditPlan(
        wants_edit=True,
        ops=[CanvasPatchOp(
            field="body",
            find=current["body"],
            replace=updated["body"],
        )],
        reply="Updated the quote.",
    )
    contract = {
        "actions": [{
            "action_type": "edit_artifact",
            "entity_id": "U-22",
            "field": "price",
            "current_value": "$1,700.00",
            "proposed_value": "$1,777.00",
            "status": "ready",
            "authorized": True,
            "applied": False,
            "expected": {
                "raw_value": "$1,777.00",
                "currency": None,
                "unit": None,
                "basis": None,
                "field_meaning": "unspecified",
                "destination_field_meaning": "unspecified",
            },
            "evidence_ids": ["quote:U-22", "draft:U-22"],
        }]
    }

    with (
        patch(
            "tools.canvas_crud_tool.update_canvas_content",
            new=AsyncMock(return_value={
                "success": True,
                "audit_id": "audit-1",
                "review_status": "accepted",
            }),
        ) as update,
        patch(
            "tools.canvas_crud_tool.read_canvas",
            new=AsyncMock(return_value={
                "success": True,
                "content": updated,
            }),
        ),
    ):
        result = await apply_canvas_edit(
            plan,
            "user-1",
            {
                "canvas_id": "quote-draft",
                "canvas_type": "email",
                "content": current,
            },
            evidence_contract=contract,
            require_evidence_postconditions=True,
        )

    assert result["postcondition_verified"] is True
    assert result["postcondition_evidence_refs"] == [
        "quote:U-22",
        "draft:U-22",
    ]
    assert update.await_args.kwargs["evidence_refs"] == [
        "quote:U-22",
        "draft:U-22",
    ]
    assert update.await_args.kwargs["postconditions"][0]["expected_value"] == (
        "$1,777.00"
    )


def test_supplier_quote_text_becomes_source_observations():
    text = "\n".join(
        f"{manufacturer} {target}: ${value}; availability follows"
        for target, (value, manufacturer) in CURRENT_QUOTE.items()
    ) + "\nAll prices are in CAD, excluding taxes and FOB Woodstock."

    observations = observations_from_text(
        text,
        requested_entities=list(TARGETS),
        requested_fields=["price"],
        source={
            "source_id": "supplier-quote-2026-09-18",
            "source_type": "supplier_quote",
            "version": "supplier-quote-2026-09-18",
            "received_date_time": "2026-09-18T14:55:38Z",
        },
        verification="verified",
    )

    assert len(observations) == 8
    assert {item["entity_id"] for item in observations} == set(TARGETS)
    assert {item["currency"] for item in observations} == {"CAD"}
    assert all("FOB Woodstock" in (item["basis"] or "") for item in observations)
    assert {item["effective_date"] for item in observations} == {"2026-09-18"}
    assert all(item["verification"] == "verified" for item in observations)
    assert all(item["locator"]["line"] > 0 for item in observations)


def test_email_canvas_table_becomes_artifact_observations():
    observations = artifact_observations(
        {
            "canvas_id": "quote-draft",
            "canvas_type": "email",
            "content": {
                "body": (
                    "<table><tr><th>Machine</th><th>Price</th></tr>"
                    "<tr><td>U-22</td><td>$1,777.00</td></tr>"
                    "<tr><td>622</td><td>$2,421.00</td></tr></table>"
                    "<p>All prices are in CAD, FOB Woodstock.</p>"
                )
            },
        },
        requested_entities=["U-22", "622"],
        requested_fields=["price"],
        source={
            "source_id": "quote-draft",
            "source_type": "artifact",
        },
    )

    assert [item["entity_id"] for item in observations] == ["U-22", "622"]
    assert [item["raw_value"] for item in observations] == [
        "$1,777.00",
        "$2,421.00",
    ]
    assert {item["currency"] for item in observations} == {"CAD"}
    assert all("FOB Woodstock" in (item["basis"] or "") for item in observations)
    assert all(item["source"]["source_id"] == "quote-draft" for item in observations)


def test_outlook_hydration_attaches_structured_source_observations():
    observations = outlook_source_observations(
        {
            "id": "message-1",
            "subject": "Quote for requested machines",
            "received_date_time": "2026-09-18T14:55:38Z",
        },
        {
            "text": "U-22: $1,777.00\nAll prices are in CAD, FOB Woodstock.",
            "truncated": False,
        },
        {
            "message": "compare the U-22 quote with the workbook",
            "requested_targets": ["U-22"],
        },
    )

    assert len(observations) == 1
    assert observations[0]["entity_id"] == "U-22"
    assert observations[0]["raw_value"] == "$1,777.00"
    assert observations[0]["currency"] == "CAD"
    assert observations[0]["source"]["source_id"] == "message-1"
    assert observations[0]["effective_date"] == "2026-09-18"


@pytest.mark.asyncio
async def test_direct_outlook_read_preserves_sender_identity():
    with patch(
        "integrations.outlook_service.outlook_service.get_email_by_id",
        new=AsyncMock(return_value={
            "id": "message-2",
            "subject": "Supplier quote",
            "sender": "supplier@example.com",
            "sender_name": "Supplier Co",
            "body": {"content": "U-22: $1,777.00"},
        }),
    ):
        result = await _outlook_read_by_ids(
            "user-1",
            ["message-2"],
            2000,
            context={"message": "read message-2"},
        )
    observations = outlook_source_observations(
        result["message-2"]["email"],
        {"text": result["message-2"]["text"]},
        {"message": "compare U-22", "requested_targets": ["U-22"]},
    )
    assert observations[0]["source"]["sender"] == "supplier@example.com"
    assert observations[0]["source"]["sender_name"] == "Supplier Co"


def test_ingested_mail_row_keeps_structured_source_identity():
    observations = ingested_row_source_observations(
        {
            "id": "ingested-message-1",
            "timestamp": "2026-09-18T14:55:38Z",
            "subject": "Quote for requested machines",
            "content": (
                "U-22: $1,777.00\n"
                "All prices are in CAD, excluding taxes and FOB Woodstock."
            ),
        },
        {"message": "compare the U-22 supplier quote with the workbook"},
    )

    assert len(observations) == 1
    assert observations[0]["entity_id"] == "U-22"
    assert observations[0]["currency"] == "CAD"
    assert observations[0]["effective_date"] == "2026-09-18"
    assert observations[0]["source"]["source_id"] == "ingested-message-1"
    assert observations[0]["locator"]["message_id"] == "ingested-message-1"


def test_cross_domain_comparison_statuses():
    cases = [
        (
            "inventory",
            [
                {
                    "entity_id": "SKU-A",
                    "field": "quantity",
                    "raw_value": "12",
                    "unit": "each",
                    "source": {"source_id": "inventory-a"},
                    "verification": "verified",
                },
                {
                    "entity_id": "SKU-A",
                    "field": "quantity",
                    "raw_value": "1",
                    "unit": "case",
                    "source": {"source_id": "inventory-b"},
                    "verification": "verified",
                },
            ],
            "numeric_changed_incomparable",
            "unit_mismatch",
        ),
        (
            "contract",
            [
                {
                    "entity_id": "Contract-7",
                    "field": "price",
                    "raw_value": "1000 EUR",
                    "currency": "EUR",
                    "basis": "net",
                    "effective_date": "2026-01-01",
                    "source": {"source_id": "contract-a"},
                    "verification": "verified",
                },
                {
                    "entity_id": "Contract-7",
                    "field": "price",
                    "raw_value": "1000 EUR",
                    "currency": "EUR",
                    "basis": "net",
                    "effective_date": "2026-02-01",
                    "source": {"source_id": "contract-b"},
                    "verification": "verified",
                },
            ],
            "numeric_match_incomparable",
            "effective_date_differs",
        ),
        (
            "technical",
            [
                {
                    "entity_id": "ingest-api",
                    "field": "required_version",
                    "raw_value": "7.3.0",
                    "source": {"source_id": "requirements"},
                    "verification": "verified",
                },
                {
                    "entity_id": "ingest-api",
                    "field": "required_version",
                    "raw_value": "7.3.0",
                    "source": {"source_id": "architecture"},
                    "verification": "verified",
                },
            ],
            "comparable_match",
            None,
        ),
        (
            "missing",
            [
                {
                    "entity_id": "ingest-api",
                    "field": "required_version",
                    "raw_value": "",
                    "source": {"source_id": "requirements"},
                    "verification": "field_missing",
                }
            ],
            "field_missing",
            "field_missing",
        ),
        (
            "conflict",
            [
                {
                    "entity_id": "SKU-A",
                    "field": "quantity",
                    "raw_value": "10",
                    "unit": "each",
                    "source": {"source_id": "inventory-a"},
                    "verification": "verified",
                },
                {
                    "entity_id": "SKU-A",
                    "field": "quantity",
                    "raw_value": "12",
                    "unit": "each",
                    "source": {"source_id": "inventory-b"},
                    "verification": "verified",
                },
            ],
            "comparable_changed",
            None,
        ),
    ]
    fields = {
        "inventory": "quantity",
        "contract": "price",
        "technical": "required_version",
        "missing": "required_version",
        "conflict": "quantity",
    }
    entities = {
        "inventory": "SKU-A",
        "contract": "Contract-7",
        "technical": "ingest-api",
        "missing": "ingest-api",
        "conflict": "SKU-A",
    }

    for domain, observations, expected_status, expected_reason in cases:
        comparison = build_source_comparison(
            observations,
            requested_entities=[entities[domain]],
            requested_fields=[fields[domain]],
        )
        outcome = comparison["coverage"]["outcomes"][0]
        assert outcome["status"] == expected_status, domain
        if expected_reason:
            assert expected_reason in outcome["reasons"], domain


def test_unauthorized_artifact_change_is_reported_but_not_prepared():
    observations = [
        {
            "observation_id": "inventory:a",
            "entity_id": "SKU-A",
            "field": "quantity",
            "raw_value": "12",
            "unit": "each",
            "source": {"source_id": "inventory", "source_type": "inventory"},
            "verification": "verified",
        },
        {
            "observation_id": "draft:a",
            "entity_id": "SKU-A",
            "field": "quantity",
            "raw_value": "10",
            "unit": "each",
            "source": {"source_id": "draft", "source_type": "artifact"},
            "verification": "verified",
        },
    ]

    comparison = build_source_comparison(
        observations,
        requested_entities=["SKU-A"],
        requested_fields=["quantity"],
        artifact_source_ids=["draft"],
        decision_source_ids=["inventory"],
        authorized_actions=[],
    )

    assert comparison["coverage"]["outcomes"][0]["status"] == "comparable_changed"
    assert comparison["actions"] == []
    assert any(
        item["status"] == "not_authorized"
        for item in comparison["blocked_actions"]
    )


def test_shorter_entity_token_cannot_match_a_longer_model_code():
    source = {"source_id": "quote", "source_type": "supplier_quote"}
    assert observations_from_text(
        "U-22: $1,777.00",
        requested_entities=["U-2"],
        requested_fields=["price"],
        source=source,
    ) == []
    assert observations_from_text(
        "ABC_DEF: $1,777.00",
        requested_entities=["ABC"],
        requested_fields=["price"],
        source=source,
    ) == []
    assert observations_from_text(
        "U-22: $1,777.00",
        requested_entities=["U"],
        requested_fields=["price"],
        source=source,
    ) == []


def test_numeric_quantity_does_not_become_a_model_designation():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["SKU", "Quantity", "Price"])
    sheet.append(["SKU-A", "381 kg", 1777])
    buffer = BytesIO()
    workbook.save(buffer)

    artifact = inspect_workbook_bytes(
        buffer.getvalue(),
        "stock.xlsx",
        targets=["381"],
        requested_fields=["price"],
    )

    assert artifact["coverage"]["outcomes"][0]["status"] != "found"


def test_only_one_verified_decision_source_can_be_designated():
    first = _quote_observations()[:1]
    second = [dict(first[0])]
    second[0] = {
        **second[0],
        "observation_id": "quote:U-22:other",
        "source": {
            **second[0]["source"],
            "source_id": "other-supplier-quote",
        },
    }

    assert designated_source_ids("use the Acme supplier quote", first) == [
        "supplier-quote-2026-09-18"
    ]
    assert designated_source_ids(
        "use the Acme supplier quote", first + second
    ) == []
    unverified = [{**first[0], "verification": "unverified"}]
    assert designated_source_ids(
        "use the Acme supplier quote", unverified
    ) == []
    assert designated_source_ids("use the supplier quote", first) == []
    assert designated_source_ids(
        "use the historical Acme supplier quote", first
    ) == []
    excluded = [{
        **first[0],
        "observation_id": "quote:excluded",
        "source": {
            **first[0]["source"],
            "source_id": "zenith-quote",
            "subject": "Zenith supplier quote",
        },
    }]
    assert designated_source_ids(
        "exclude Zenith and use the Acme supplier quote", excluded
    ) == []


def test_explicit_empty_designation_disables_source_inference():
    artifact = inspect_workbook_bytes(
        _workbook_bytes(),
        "Consolidated Price List 2019.xlsx",
        targets=list(TARGETS),
        requested_fields=["price"],
        resource_id="workbook-2019",
        source_metadata={"temporal_role": "historical"},
    )
    comparison = build_canvas_evidence_comparison(
        {
            "canvas_id": "quote-draft",
            "content": {
                "body": (
                    "<table><tr><th>Machine</th><th>Price</th></tr>"
                    "<tr><td>Linmac U-22</td><td>$1,700.00</td></tr>"
                    "</table><p>CAD, FOB Woodstock.</p>"
                )
            },
        },
        artifact,
        source_observations=[_quote_observation("U-22")],
        decision_source_ids=[],
        authorized_actions=["edit_artifact"],
        objective_text="use the supplier quote",
    )

    assert comparison["actions"] == []
    assert comparison["blocked_actions"] == []


def test_ambiguous_artifact_price_columns_never_authorize_a_change():
    artifact = inspect_workbook_bytes(
        _workbook_bytes(),
        "Consolidated Price List 2019.xlsx",
        targets=list(TARGETS),
        requested_fields=["price"],
        resource_id="workbook-2019",
        source_metadata={"temporal_role": "historical"},
    )
    comparison = build_canvas_evidence_comparison(
        {
            "canvas_id": "quote-draft",
            "content": {
                "body": (
                    "<table><tr><th>Machine</th><th>Retail Price</th>"
                    "<th>Wholesale Price</th></tr>"
                    "<tr><td>Linmac U-22</td><td>$1,800.00</td>"
                    "<td>$1,700.00</td></tr></table>"
                    "<p>CAD, FOB Woodstock.</p>"
                )
            },
        },
        artifact,
        source_observations=[_quote_observation("U-22")],
        authorized_actions=["edit_artifact"],
        objective_text="use the supplier quote",
    )

    u22 = next(
        item for item in comparison["coverage"]["outcomes"]
        if item["entity_id"] == "U-22"
    )
    assert u22["status"] == "partially_comparable"
    assert comparison["coverage"]["complete"] is False
    assert comparison["actions"] == []


def test_qualified_price_column_cannot_compare_as_generic_price():
    observations = artifact_observations(
        {
            "canvas_id": "quote-draft",
            "content": {
                "body": (
                    "<table><tr><th>Machine</th><th>Wholesale Price</th></tr>"
                    "<tr><td>Linmac U-22</td><td>$1,700.00</td></tr></table>"
                    "<p>CAD, FOB Woodstock.</p>"
                )
            },
        },
        requested_entities=["U-22"],
        requested_fields=["price"],
        source={
            "source_id": "quote-draft",
            "source_type": "artifact",
        },
    )
    observations.extend([_quote_observation("U-22")])

    comparison = build_source_comparison(
        observations,
        requested_entities=["U-22"],
        requested_fields=["price"],
        artifact_source_ids=["quote-draft"],
        decision_source_ids=["supplier-quote-2026-09-18"],
        authorized_actions=["edit_artifact"],
    )

    outcome = comparison["coverage"]["outcomes"][0]
    assert "field_meaning_mismatch" in outcome["reasons"]
    assert comparison["actions"] == []


def test_factory_price_cannot_compare_as_generic_supplier_quote():
    observations = artifact_observations(
        {
            "canvas_id": "quote-draft",
            "content": {
                "body": (
                    "<table><tr><th>Machine</th><th>Factory Price</th></tr>"
                    "<tr><td>Linmac U-22</td><td>$1,700.00</td></tr></table>"
                    "<p>CAD, FOB Woodstock.</p>"
                )
            },
        },
        requested_entities=["U-22"],
        requested_fields=["price"],
        source={
            "source_id": "quote-draft",
            "source_type": "artifact",
        },
    )
    observations.extend([_quote_observation("U-22")])
    comparison = build_source_comparison(
        observations,
        requested_entities=["U-22"],
        requested_fields=["price"],
        artifact_source_ids=["quote-draft"],
        decision_source_ids=["supplier-quote-2026-09-18"],
        authorized_actions=["edit_artifact"],
    )

    assert "field_meaning_mismatch" in (
        comparison["coverage"]["outcomes"][0]["reasons"]
    )
    assert comparison["actions"] == []


def test_non_workbook_evidence_still_builds_an_artifact_contract():
    quote = {
        **_quote_observation("U-22"),
        "basis": "FOB Woodstock",
    }
    comparison = build_canvas_evidence_comparison(
        {
            "canvas_id": "quote-draft",
            "content": {
                "body": (
                    "<table><tr><th>Machine</th><th>Price</th></tr>"
                    "<tr><td>Linmac U-22</td><td>$1,700.00</td></tr></table>"
                    "<p>CAD, FOB Woodstock.</p>"
                )
            },
        },
        {},
        source_observations=[quote],
        decision_source_ids=["supplier-quote-2026-09-18"],
        authorized_actions=["edit_artifact"],
    )

    assert comparison["coverage"]["requested_entities"] == ["U-22"]
    assert len(comparison["actions"]) == 1


@pytest.mark.asyncio
async def test_mail_evidence_lookup_builds_a_structured_edit_contract():
    message = "Update the draft using the Acme supplier quote."
    plan = ToolPlan(
        use_tool=True,
        service="outlook",
        intent="read",
        query=message,
        reason="current supplier quote requested",
    )
    quote = {
        **_quote_observation("U-22"),
        "basis": "FOB Woodstock",
    }

    async def execute_lookup(_plan, _user_id, context=None):
        _plan._result_meta["source_observations"] = [quote]
        return "LIVE TOOL RESULTS (outlook.read)"

    with (
        patch(
            "core.chat_tool_planner.plan_tool_use",
            new=AsyncMock(return_value=plan),
        ),
        patch(
            "core.chat_tool_planner.execute_tool_plan",
            new=AsyncMock(side_effect=execute_lookup),
        ),
    ):
        result = await fetch_fresh_data_section(
            message,
            [],
            MagicMock(),
            "user-1",
            canvas={
                "canvas_id": "quote-draft",
                "content": {
                    "body": (
                        "<table><tr><th>Machine</th><th>Price</th></tr>"
                        "<tr><td>Linmac U-22</td><td>$1,700.00</td></tr>"
                        "</table><p>CAD, FOB Woodstock.</p>"
                    )
                },
            },
            allow_canvas_target=True,
            authorized_actions=["edit_artifact"],
        )

    assert result.evidence_contract is not None
    assert len(result.evidence_contract["actions"]) == 1


def test_unverified_decision_observation_cannot_create_an_action():
    comparison = build_source_comparison(
        [
            {
                "observation_id": "draft:U-22",
                "entity_id": "U-22",
                "field": "price",
                "raw_value": "$1,700.00",
                "currency": "CAD",
                "basis": "FOB Woodstock",
                "effective_date": "2026-09-18",
                "source": {"source_id": "draft", "source_type": "artifact"},
                "verification": "verified",
            },
            {
                "observation_id": "quote:U-22",
                "entity_id": "U-22",
                "field": "price",
                "raw_value": "$1,777.00",
                "currency": "CAD",
                "basis": "FOB Woodstock",
                "effective_date": "2026-09-18",
                "source": {"source_id": "quote", "source_type": "supplier_quote"},
                "verification": "unverified",
            },
        ],
        requested_entities=["U-22"],
        requested_fields=["price"],
        artifact_source_ids=["draft"],
        decision_source_ids=["quote"],
        authorized_actions=["edit_artifact"],
    )

    assert comparison["coverage"]["outcomes"][0]["status"] == "unverified"
    assert comparison["actions"] == []


def test_unverified_evidence_cannot_be_masked_by_a_verified_conflict():
    comparison = build_source_comparison(
        [
            {
                "entity_id": "U-22",
                "field": "price",
                "raw_value": "$1,700.00",
                "currency": "CAD",
                "basis": "FOB Woodstock",
                "source": {"source_id": "draft", "source_type": "artifact"},
                "verification": "verified",
            },
            {
                "entity_id": "U-22",
                "field": "price",
                "raw_value": "$1,777.00",
                "currency": "CAD",
                "basis": "FOB Woodstock",
                "source": {"source_id": "quote"},
                "verification": "unverified",
            },
            {
                "entity_id": "U-22",
                "field": "price",
                "raw_value": "$1,800.00",
                "currency": "CAD",
                "basis": "FOB Woodstock",
                "source": {"source_id": "other"},
                "verification": "verified",
            },
        ],
        requested_entities=["U-22"],
        requested_fields=["price"],
        artifact_source_ids=["draft"],
        decision_source_ids=["quote", "other"],
        authorized_actions=["edit_artifact"],
    )

    assert comparison["coverage"]["outcomes"][0]["status"] == (
        "partially_comparable"
    )
    assert comparison["coverage"]["complete"] is False
    assert comparison["actions"] == []


def test_row_currency_conflict_is_not_hidden_by_document_currency():
    observations = observations_from_text(
        "All prices are in CAD.\nU-22: €100",
        requested_entities=["U-22"],
        requested_fields=["price"],
        source={"source_id": "quote", "source_type": "supplier_quote"},
    )

    assert observations[0]["currency"] is None
    assert observations[0]["basis"] is None


def test_comparison_number_is_bounded_and_keeps_currency_suffixes_out():
    assert _comparison_number("1000 EUR") == 1000
    assert _comparison_number("$1,777.00") == 1777
    assert _comparison_number("-$1,777.00") == -1777
    assert _comparison_number("1e999999999") is None
    assert _comparison_number(Decimal("1e999999999")) is None
    assert _comparison_number(Decimal("1" * 257)) is None
    assert _comparison_number("1" * 257) is None


@pytest.mark.asyncio
async def test_evidence_postcondition_rejects_currency_and_basis_mismatch():
    current = {
        "body": (
            "<table><tr><th>Machine</th><th>Price</th></tr>"
            "<tr><td>Linmac U-22</td><td>$1,700.00</td></tr></table>"
            "<p>CAD, FOB Woodstock.</p>"
        )
    }
    wrong = {
        "body": (
            "<table><tr><th>Machine</th><th>Price</th></tr>"
            "<tr><td>Linmac U-22</td><td>USD 1,777.00</td></tr></table>"
            "<p>USD, FOB Vancouver.</p>"
        )
    }
    plan = CanvasEditPlan(
        wants_edit=True,
        ops=[CanvasPatchOp(
            field="body",
            find=current["body"],
            replace=wrong["body"],
        )],
    )
    contract = {
        "actions": [{
            "action_type": "edit_artifact",
            "entity_id": "U-22",
            "field": "price",
            "proposed_value": "$1,777.00",
            "expected": {
                "raw_value": "$1,777.00",
                "currency": "CAD",
                "unit": None,
                "basis": "FOB Woodstock",
            },
            "status": "ready",
            "authorized": True,
            "evidence_ids": ["quote:U-22", "draft:U-22"],
        }]
    }

    with patch(
        "tools.canvas_crud_tool.update_canvas_content",
        new=AsyncMock(),
    ) as update:
        result, reason = await apply_canvas_edit(
            plan,
            "user-1",
            {
                "canvas_id": "quote-draft",
                "canvas_type": "email",
                "content": current,
            },
            return_reason=True,
            evidence_contract=contract,
        )

    assert result is None
    assert reason == "postcondition_missing:U-22"
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_postcondition_rejects_a_different_qualified_price_column():
    current = {
        "body": (
            "<table><tr><th>Machine</th><th>Price</th></tr>"
            "<tr><td>Linmac U-22</td><td>$1,700.00</td></tr></table>"
            "<p>CAD, FOB Woodstock.</p>"
        )
    }
    wrong_column = {
        "body": (
            "<table><tr><th>Machine</th><th>Wholesale Price</th></tr>"
            "<tr><td>Linmac U-22</td><td>$1,777.00</td></tr></table>"
            "<p>CAD, FOB Woodstock.</p>"
        )
    }
    plan = CanvasEditPlan(
        wants_edit=True,
        ops=[CanvasPatchOp(
            field="body",
            find=current["body"],
            replace=wrong_column["body"],
        )],
    )
    contract = {
        "actions": [{
            "action_type": "edit_artifact",
            "entity_id": "U-22",
            "field": "price",
            "proposed_value": "$1,777.00",
            "expected": {
                "raw_value": "$1,777.00",
                "currency": "CAD",
                "unit": None,
                "basis": "FOB Woodstock",
                "field_meaning": "quoted",
            },
            "status": "ready",
            "authorized": True,
            "evidence_ids": ["quote:U-22", "draft:U-22"],
        }]
    }

    with patch(
        "tools.canvas_crud_tool.update_canvas_content",
        new=AsyncMock(),
    ) as update:
        result, reason = await apply_canvas_edit(
            plan,
            "user-1",
            {
                "canvas_id": "quote-draft",
                "canvas_type": "email",
                "content": current,
            },
            return_reason=True,
            evidence_contract=contract,
        )

    assert result is None
    assert reason == "postcondition_missing:U-22"
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_target_rows_do_not_satisfy_a_postcondition():
    current = {
        "body": (
            "<table><tr><th>Machine</th><th>Price</th></tr>"
            "<tr><td>Linmac U-22</td><td>$1,700.00</td></tr></table>"
            "<p>CAD, FOB Woodstock.</p>"
        )
    }
    duplicate = {
        "body": (
            "<table><tr><th>Machine</th><th>Price</th></tr>"
            "<tr><td>Linmac U-22</td><td>$1,700.00</td></tr>"
            "<tr><td>Linmac U-22</td><td>$1,777.00</td></tr></table>"
            "<p>CAD, FOB Woodstock.</p>"
        )
    }
    plan = CanvasEditPlan(
        wants_edit=True,
        ops=[CanvasPatchOp(
            field="body",
            find=current["body"],
            replace=duplicate["body"],
        )],
    )
    contract = {
        "actions": [{
            "action_type": "edit_artifact",
            "entity_id": "U-22",
            "field": "price",
            "proposed_value": "$1,777.00",
            "expected": {
                "raw_value": "$1,777.00",
                "currency": "CAD",
                "unit": None,
                "basis": "FOB Woodstock",
            },
            "status": "ready",
            "authorized": True,
            "evidence_ids": ["quote:U-22", "draft:U-22"],
        }]
    }

    with patch(
        "tools.canvas_crud_tool.update_canvas_content",
        new=AsyncMock(),
    ) as update:
        result, reason = await apply_canvas_edit(
            plan,
            "user-1",
            {
                "canvas_id": "quote-draft",
                "canvas_type": "email",
                "content": current,
            },
            return_reason=True,
            evidence_contract=contract,
        )

    assert result is None
    assert reason == "postcondition_missing:U-22"
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_readback_is_not_reported_as_a_successful_update():
    current = {
        "body": (
            "<table><tr><th>Machine</th><th>Price</th></tr>"
            "<tr><td>Linmac U-22</td><td>$1,700.00</td></tr></table>"
            "<p>CAD, FOB Woodstock.</p>"
        )
    }
    updated = {
        "body": (
            "<table><tr><th>Machine</th><th>Price</th></tr>"
            "<tr><td>Linmac U-22</td><td>$1,777.00</td></tr></table>"
            "<p>CAD, FOB Woodstock.</p>"
        )
    }
    plan = CanvasEditPlan(
        wants_edit=True,
        ops=[CanvasPatchOp(
            field="body",
            find=current["body"],
            replace=updated["body"],
        )],
    )
    contract = {
        "actions": [{
            "action_type": "edit_artifact",
            "entity_id": "U-22",
            "field": "price",
            "proposed_value": "$1,777.00",
            "expected": {
                "raw_value": "$1,777.00",
                "currency": "CAD",
                "unit": None,
                "basis": "FOB Woodstock",
            },
            "status": "ready",
            "authorized": True,
            "evidence_ids": ["quote:U-22", "draft:U-22"],
        }]
    }

    with (
        patch(
            "tools.canvas_crud_tool.update_canvas_content",
            new=AsyncMock(return_value={
                "success": True,
                "audit_id": "audit-unverified",
            }),
        ),
        patch(
            "tools.canvas_crud_tool.read_canvas",
            new=AsyncMock(return_value={
                "success": True,
                "content": current,
            }),
        ),
    ):
        result, reason = await apply_canvas_edit(
            plan,
            "user-1",
            {
                "canvas_id": "quote-draft",
                "canvas_type": "email",
                "content": current,
            },
            return_reason=True,
            evidence_contract=contract,
        )

    assert result["success"] is False
    assert result["write_recorded"] is True
    assert result["postcondition_verified"] is False
    assert reason == "postcondition_readback_failed"


@pytest.mark.asyncio
async def test_ready_non_edit_action_cannot_write():
    current = {"body": "U-22: $1,700.00"}
    updated = {"body": "U-22: $1,777.00"}
    plan = CanvasEditPlan(
        wants_edit=True,
        ops=[CanvasPatchOp(
            field="body",
            find=current["body"],
            replace=updated["body"],
        )],
    )
    contract = {
        "actions": [{
            "action_type": "delete_artifact",
            "entity_id": "U-22",
            "field": "price",
            "proposed_value": "$1,777.00",
            "expected": {
                "raw_value": "$1,777.00",
                "destination_field_meaning": "unspecified",
            },
            "status": "ready",
            "authorized": True,
        }]
    }
    with patch(
        "tools.canvas_crud_tool.update_canvas_content",
        new=AsyncMock(),
    ) as update:
        result, reason = await apply_canvas_edit(
            plan,
            "user-1",
            {"canvas_id": "quote-draft", "canvas_type": "email", "content": current},
            return_reason=True,
            evidence_contract=contract,
        )
    assert result is None
    assert reason == "no_ready_evidence_change"
    update.assert_not_awaited()


def test_artifact_entity_boundary_rejects_longer_identifiers():
    observations = artifact_observations(
        {
            "canvas_id": "quote-draft",
            "content": {"body": "ABC_DEF: $10.00"},
        },
        requested_entities=["ABC"],
        requested_fields=["price"],
    )
    assert observations == []


def test_duplicate_text_evidence_is_not_collapsed_to_one_row():
    observations = observations_from_text(
        "E: $10.00\nE: $20.00",
        requested_entities=["E"],
        requested_fields=["price"],
        source={"source_id": "quote", "source_type": "supplier_quote"},
    )
    assert len(observations) == 2
    assert {item["raw_value"] for item in observations} == {"$10.00", "$20.00"}


def test_text_observations_preserve_explicit_units():
    observations = observations_from_text(
        "E: 10 each\nF: $10 per hour",
        requested_entities=["E", "F"],
        requested_fields=["quantity", "price"],
        source={"source_id": "quote", "source_type": "supplier_quote"},
    )
    by_entity = {item["entity_id"]: item for item in observations}
    assert by_entity["E"]["unit"] == "each"
    assert by_entity["F"]["unit"] == "hour"


@pytest.mark.asyncio
async def test_missing_expected_postcondition_blocks_write():
    current = {"body": "U-22: $1,700.00"}
    updated = {"body": "U-22: $1,777.00"}
    plan = CanvasEditPlan(
        wants_edit=True,
        ops=[CanvasPatchOp(
            field="body",
            find=current["body"],
            replace=updated["body"],
        )],
    )
    contract = {
        "actions": [{
            "action_type": "edit_artifact",
            "entity_id": "U-22",
            "field": "price",
            "proposed_value": "$1,777.00",
            "status": "ready",
            "authorized": True,
        }]
    }
    with patch(
        "tools.canvas_crud_tool.update_canvas_content",
        new=AsyncMock(),
    ) as update:
        result, reason = await apply_canvas_edit(
            plan,
            "user-1",
            {"canvas_id": "quote-draft", "canvas_type": "email", "content": current},
            return_reason=True,
            evidence_contract=contract,
        )
    assert result is None
    assert reason == "postcondition_missing:U-22"
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_evidence_contract_without_ready_action_blocks_the_write():
    current = {"body": "U-22: $1,700.00"}
    updated = {"body": "U-22: $1,777.00"}
    plan = CanvasEditPlan(
        wants_edit=True,
        ops=[CanvasPatchOp(
            field="body",
            find=current["body"],
            replace=updated["body"],
        )],
    )

    with patch(
        "tools.canvas_crud_tool.update_canvas_content",
        new=AsyncMock(),
    ) as update:
        result, reason = await apply_canvas_edit(
            plan,
            "user-1",
            {
                "canvas_id": "quote-draft",
                "canvas_type": "email",
                "content": current,
            },
            return_reason=True,
            evidence_contract={"actions": [], "blocked_actions": []},
        )

    assert result is None
    assert reason == "no_ready_evidence_change"
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_reused_evidence_block_keeps_structured_contract():
    contract = {
        "contract_version": 1,
        "actions": [],
        "blocked_actions": [],
    }
    result = await fetch_fresh_data_section(
        "update the draft with the quote",
        [],
        MagicMock(),
        "user-1",
        existing_block="LIVE TOOL RESULTS",
        existing_evidence_contract=contract,
        authorized_actions=["edit_artifact"],
    )

    assert result.evidence_contract == contract


def test_background_continuation_reads_execution_scoped_contract():
    orchestrator = MagicMock()
    contract = {"contract_version": 1, "actions": []}
    orchestrator.conversation_sessions = {
        "session-1": {
            "_objective_evidence_execution-1": contract
        }
    }
    continuation = AsyncTurnContinuation(
        continuation_id="continuation-1",
        user_id="user-1",
        session_id="session-1",
        message="update the draft",
        canvas={},
        execution_id="execution-1",
        agent_id=None,
        history_snapshot=[],
    )
    object.__setattr__(continuation, "_orchestrator", orchestrator)

    assert _latest_turn_contract(orchestrator, continuation) == contract


@pytest.mark.asyncio
async def test_incomplete_direct_workbook_read_stays_resumable():
    orchestrator = ChatOrchestrator()
    orchestrator.ai_engines = {}
    orchestrator.llm_service = MagicMock()
    session = {"id": "incomplete-session", "history": []}
    finish = MagicMock()

    with (
        patch.object(
            orchestrator,
            "_get_or_create_session",
            return_value=session,
        ),
        patch.object(
            orchestrator,
            "_resolve_canvas_ctx",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            orchestrator,
            "_start_chat_execution",
            return_value="incomplete-exec",
        ),
        patch.object(
            orchestrator,
            "_record_chat_step",
            new=AsyncMock(),
        ),
        patch.object(
            orchestrator,
            "_emit_agent_status",
            new=AsyncMock(),
        ),
        patch.object(orchestrator, "_finish_chat_execution", finish),
        patch.object(orchestrator, "_update_session"),
        patch.object(
            orchestrator,
            "_load_conversation_mail_handles",
            return_value=([], []),
        ),
        patch.object(
            orchestrator,
            "_try_zoho_crm_write",
            new=AsyncMock(),
        ),
        patch(
            "core.chat_mini_app_authoring.try_handle",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            orchestrator,
            "_direct_confirmed_file_read",
            new=AsyncMock(return_value={
                "ok": True,
                "rendered_answer": "PARTIAL: one target remains unresolved.",
                "retrieval_complete": False,
                "identity": {
                    "file_name": "Consolidated Price List 2019.xlsx",
                    "resource_id": "workbook-2019",
                },
            }),
        ),
    ):
        result = await orchestrator.process_chat_message(
            "user-1",
            "Find prices in Consolidated Price List 2019.xlsx for U-22.",
            "incomplete-session",
        )

    assert result["data"]["coverage_complete"] is False
    assert result["data"]["resumable"] is True
    assert session["_pending_file_task"]["status"] == "pending"
    assert finish.call_args.args[1] == "partial"


def test_advisory_and_explicit_edit_routing_stays_distinct():
    canvas = {"canvas": {"canvas_id": "quote-draft"}}
    assert not _canvas_edit_shaped(
        "compare the workbook and explain whether the draft should change",
        canvas,
    )
    assert not _canvas_edit_shaped(
        "tell me whether I should update the draft", canvas
    )
    assert not _canvas_edit_shaped(
        "tell me whether to update the draft", canvas
    )
    assert not _canvas_edit_shaped(
        "let me know if we should update the draft", canvas
    )
    assert _canvas_edit_shaped(
        "update the draft and explain whether the change is supported",
        canvas,
    )
    assert not _read_only_file_ask(
        "find prices in Consolidated Price List 2019.xlsx and send the draft",
        {"canvas_id": "quote-draft"},
    )


def test_task_outcome_ignores_stale_session_objective_evidence():
    orchestrator = ChatOrchestrator.__new__(ChatOrchestrator)
    stale = build_source_comparison(
        [
            {
                "entity_id": "SKU-A",
                "field": "quantity",
                "raw_value": "10",
                "unit": "each",
                "source": {"source_id": "old-inventory"},
                "verification": "verified",
            },
            {
                "entity_id": "SKU-A",
                "field": "quantity",
                "raw_value": "12",
                "unit": "each",
                "source": {"source_id": "old-draft"},
                "verification": "verified",
            },
        ],
        requested_entities=["SKU-A"],
        requested_fields=["quantity"],
    )
    outcome = orchestrator._build_turn_task_outcome(
        {
            "id": "session-1",
            "_objective_evidence": stale,
        },
        "what is the weather?",
        {
            "success": True,
            "message": "It is sunny.",
        },
        None,
        None,
        status="success",
    )

    assert outcome["evidence_ledger"].get("total", 0) == 0
    assert outcome["objective_state"]["target_entities"] == []


def test_task_outcome_rejects_stale_file_identity():
    orchestrator = ChatOrchestrator.__new__(ChatOrchestrator)
    outcome = orchestrator._build_turn_task_outcome(
        {
            "id": "session-1",
            "_resolved_file_identity": {
                "file_name": "old.xlsx",
                "resource_id": "old-resource",
                "execution_id": "old-exec",
            },
        },
        "find values in report.xlsx",
        {
            "success": True,
            "message": "The read is pending.",
        },
        None,
        None,
        execution_id="current-exec",
        status="success",
    )

    assert all(
        ref.get("file_name") != "old.xlsx"
        for ref in outcome["evidence_refs"]
    )
    assert not outcome["source_constraints"].get("file_identity")


def test_task_outcome_does_not_mark_pending_review_as_applied():
    orchestrator = ChatOrchestrator.__new__(ChatOrchestrator)
    outcome = orchestrator._build_turn_task_outcome(
        {"id": "session-1"},
        "update the draft",
        {
            "success": True,
            "message": "Draft proposal ready for review.",
            "data": {
                "canvas_edit": {
                    "updated": True,
                    "postcondition_verified": True,
                    "review_status": "pending_review",
                },
                "objective_evidence": {
                    "actions": [{
                        "action_type": "edit_artifact",
                        "entity_id": "SKU-A",
                        "field": "quantity",
                        "status": "ready",
                        "authorized": True,
                    }],
                },
            },
        },
        None,
        None,
        execution_id="execution-1",
        status="success",
        authorized_actions=["edit_artifact"],
    )
    assert outcome["mutation"]["readback_matched"] is False
    assert outcome["actions"][0]["applied"] is False
    assert outcome["success_kinds"]["task_success"] is not True


def test_task_outcome_requires_an_execution_id_for_session_file_evidence():
    orchestrator = ChatOrchestrator.__new__(ChatOrchestrator)
    outcome = orchestrator._build_turn_task_outcome(
        {
            "id": "session-1",
            "_pending_file_result": {
                "status": "delivered",
                "coverage_complete": True,
                "identity": {
                    "file_name": "old.xlsx",
                    "resource_id": "old-resource",
                },
            },
        },
        "find values in report.xlsx",
        {"success": True, "message": "The read is pending."},
        None,
        None,
        status="success",
    )
    assert outcome["evidence_refs"] == []
    assert not outcome["source_constraints"].get("file_identity")


def test_task_outcome_records_verified_canvas_mutation():
    orchestrator = ChatOrchestrator.__new__(ChatOrchestrator)
    comparison = build_source_comparison(
        [
            {
                "entity_id": "SKU-A",
                "field": "quantity",
                "raw_value": "10",
                "unit": "each",
                "source": {"source_id": "draft", "source_type": "artifact"},
                "verification": "verified",
            },
            {
                "entity_id": "SKU-A",
                "field": "quantity",
                "raw_value": "12",
                "unit": "each",
                "source": {"source_id": "inventory"},
                "verification": "verified",
            },
        ],
        requested_entities=["SKU-A"],
        requested_fields=["quantity"],
        artifact_source_ids=["draft"],
        decision_source_ids=["inventory"],
        authorized_actions=["edit_artifact"],
    )
    outcome = orchestrator._build_turn_task_outcome(
        {"id": "session-1"},
        "update the draft",
        {
            "success": True,
            "message": "Updated the draft.",
            "data": {
                "canvas_edit": {
                    "canvas_id": "quote-draft",
                    "updated": True,
                    "postcondition_verified": True,
                    "review_status": "accepted",
                },
                "objective_evidence": comparison,
            },
        },
        None,
        None,
        status="success",
        authorized_actions=["edit_artifact"],
    )

    assert outcome["mutation"] == {
        "requested": True,
        "readback_matched": True,
        "status": True,
    }
    assert {"kind": "mutation"} in outcome["completion_criteria"]
    assert outcome["actions"][0]["status"] == "applied"
    assert outcome["actions"][0]["applied"] is True
    assert outcome["success_kinds"]["task_success"] is True
