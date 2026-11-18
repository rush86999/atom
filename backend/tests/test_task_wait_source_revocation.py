"""TASK-WAIT-01 E3: public source-route revocation recheck.

A waiting assignment asks for one tabular price source. The answer is a real
local connected-catalog reference backed by the existing IntegrationToken
grant (no external provider call). With the grant revoked, the public
`/sources` route refuses the answer before any read/quote effect and leaves
the same question open. Re-activating the same grant is the valid unchanged
twin: the identical answer settles only that question and the same task
produces one verified quote receipt.

Public assignment routes, the real compiler/executor/catalog recheck and
scratch durable records are exercised. Discovery/adaptation proposal choices and authentication use controlled
high-level fixtures; this is not transport-only or served-model qualification.

E3b adds the ordinary public disconnect route: the integrations UI's
Microsoft 365 disconnect
(frontend-nextjs/components/Microsoft365Integration.tsx) -> ``DELETE
/api/v1/auth/oauth/tokens/microsoft`` is mounted beside the
assignment router on the same scratch database and user, then the waiting
task's source answer is replayed. The route must persist the revoked grant
for the onedrive token family the catalog read depends on, and the answer
must get the exact source-permission refusal.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from tests.test_assignment_routes import route_env  # noqa: F401


DATASET = "e3_quote_prices"
SHEET = "Prices"


def _seed_connected_grant(route_env, tmp_path):
    from core.models import DatasetEntry, IntegrationToken

    db = route_env["db"]
    root = tmp_path / "sheet_datasets"
    root.mkdir(parents=True, exist_ok=True)
    parquet = root / "quote.parquet"
    pd.DataFrame({
        "Item": ["SC-1"],
        "Qty": [3],
        "Unit Price": [12.5],
        "Currency": ["USD"],
        "__sheet_row": [2],
    }).to_parquet(parquet, index=False)
    db.add(DatasetEntry(
        id="e3-entry", workspace_id="ws-1", tenant_id="tenant-1",
        created_by="lead-1", source_kind="file", source="onedrive",
        external_id="e3-drive", file_name="quote.xlsx",
        content_hash="b" * 40, entity_name=SHEET, dataset_name=DATASET,
        parquet_path=str(parquet), row_count=1, column_count=4,
        columns_json={
            "columns": [
                {"name": "Item"}, {"name": "Qty"},
                {"name": "Unit Price"}, {"name": "Currency"},
                {"name": "__sheet_row"}],
            "coverage": {
                "known": True, "source_row_count": 1,
                "materialized_row_count": 1, "truncated": False},
        },
        status="active"))
    token = IntegrationToken(
        id="e3-token", tenant_id="tenant-1", user_id="lead-1",
        workspace_id="ws-1", provider="onedrive",
        access_token="local-not-a-secret", status="active")
    db.add(token)
    db.commit()
    return token


def _seed_oauth_disconnect_pair(route_env):
    """The OAuthToken row the shipped disconnect route looks up.

    The UI disconnect targets provider ``microsoft``; the route updates the
    legacy page row and fans the revoke out to the IntegrationToken rows the
    data routes read (``microsoft``/``outlook``/``onedrive``/``microsoft365``).
    """
    from core.models import OAuthClient, OAuthToken

    db = route_env["db"]
    db.add(OAuthClient(
        id="microsoft_client", client_id="microsoft_client",
        name="Microsoft 365", redirect_uris=["http://localhost/oauth/cb"],
        allowed_scopes=["Files.Read"], tenant_id="tenant-1"))
    db.add(OAuthToken(
        id="e3-oauth-token", client_id="microsoft_client",
        user_id="lead-1", tenant_id="tenant-1",
        access_token_hash="a" * 64,
        scope="Files.Read offline_access", token_type="Bearer",
        access_token_expires_at=(
            datetime.now(timezone.utc) + timedelta(hours=1)),
        is_active=True))
    db.commit()


def _mount_disconnect_route(route_env, monkeypatch):
    """Mount the real v1 OAuth router on the same scratch app/db/user."""
    from api import oauth_routes

    app = route_env["client"].app
    app.include_router(oauth_routes.router)

    # The handler's Depends is the wrapper captured at import time; its body
    # then awaits the module global again. Both resolve to the fixture user.
    dependency = oauth_routes.get_current_user
    app.dependency_overrides[dependency] = lambda: route_env["current"]["user"]

    async def _fixture_user(request=None, db=None):
        return route_env["current"]["user"]

    monkeypatch.setattr(oauth_routes, "get_current_user", _fixture_user)


def _install_transport(monkeypatch):
    calls = []
    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import (
        MoneyTerm, QuoteCalculationRequest, QuoteColumns, TaxTerm,
    )

    async def discovery(context, **kwargs):
        calls.append("discovery")
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "read the authorized scope",
                "evidence_reads": [
                    {"step_id": f"evidence-{index}", "title": "Read source",
                     "source_id": source["source_id"]}
                    for index, source in enumerate(context["sources"], 1)
                ],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    async def adaptation(context, observations, **kwargs):
        calls.append("adaptation")
        tabular = next(
            (item for item in context.get("evidence_results") or []
             if item.get("rows")
             and any(str(entry.get("column") or "") == "Unit Price"
                     for entry in (item.get("schema") or [])
                     if isinstance(entry, dict))),
            None)
        common = {
            "reason": "model-selected supported work",
            "observation_ids": [
                item["observation_id"] for item in observations],
        }
        if tabular is None:
            return {
                "proposal": WorkAdaptationProposal(
                    decision="clarify",
                    clarification={
                        "question": (
                            "Which authorized source contains the tabular "
                            "price rows needed for the quote?"),
                        "concept": "quote_calculation",
                        "unblocks": "quote calculation",
                    },
                    **common,
                ).model_dump(),
                "source": "model",
                "technical_fallback": False,
                "errors": [],
            }
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan",
                work_request=QuoteCalculationRequest(
                    operation="quote_calculation",
                    source_step_id=str(tabular["step_id"]),
                    columns=QuoteColumns(
                        item_id="Item", quantity="Qty",
                        unit_price="Unit Price", currency="Currency"),
                    currency="USD",
                    freight=MoneyTerm(value="0.00", authority_ref="freight"),
                    tax=TaxTerm(basis="none", authority_ref="tax_basis")),
                **common,
            ).model_dump(),
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", discovery)
    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", adaptation)
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm", lambda *a, **k: object())
    return calls


def _start(client, memo):
    answer = client.post(
        "/api/assignments/from-objective",
        json={
            "objective": "Prepare a quote for item SC-1 from the price list",
            "sources": [{"path": str(memo)}],
            "authorized_actions": ["retrieve", "calculate"],
            "teaching_terms": {
                "currency": "USD", "freight": "0.00", "tax_basis": "none"},
            "use_model": True,
        })
    assert answer.status_code == 200, answer.text
    return answer.json()["run_id"]


def _questions(lifecycle, run_id):
    from core.task_lifecycle import open_unresolved_questions

    return open_unresolved_questions(lifecycle.get_task(run_id))


def _source_steps(assignment):
    return [
        step for step in assignment["steps"]
        if step["adapter"] in ("dataset.read", "workbook.read")
        and step["status"] == "applied"
    ]


def _quotes(assignment):
    return [
        step for step in assignment["steps"]
        if step["adapter"] == "quote.calculate"
        and step["status"] == "applied"
    ]


def _answer(client, run_id):
    return client.post(
        f"/api/assignments/{run_id}/sources",
        json={
            "source": {
                "kind": "workbook",
                "dataset_name": DATASET,
                "sheet": SHEET,
            },
            "reason": "authorized local price-list answer",
        })


def test_revoked_local_grant_refuses_source_answer_then_valid_twin_completes(
        route_env, tmp_path, monkeypatch):
    monkeypatch.setenv(
        "ATOM_ASSIGNMENT_OUTPUT_DIR", str(tmp_path / "artifacts"))
    # datasets_root() anchors under ATOM_DATA_DIR/sheet_datasets; keep the
    # connected catalog's materialized copy inside this owned scratch root.
    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path))
    token = _seed_connected_grant(route_env, tmp_path)
    calls = _install_transport(monkeypatch)
    memo = tmp_path / "request.txt"
    memo.write_text("Please prepare the SC-1 quote from the price list.")
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]

    run_id = _start(client, memo)
    question = _questions(lifecycle, run_id)
    assert len(question) == 1, question
    assert question[0]["concept"] == "quote_calculation", question[0]
    before = lifecycle.get_assignment(run_id)
    assert _source_steps(before) == []
    assert _quotes(before) == []

    # The owner revokes the existing local grant while the task waits.
    token.status = "revoked"
    route_env["db"].commit()
    before_calls = list(calls)
    revoked = _answer(client, run_id)
    assert revoked.status_code == 403, revoked.text
    assert calls == before_calls
    after_revoke = lifecycle.get_assignment(run_id)
    assert _source_steps(after_revoke) == []
    assert _quotes(after_revoke) == []
    still_open = _questions(lifecycle, run_id)
    assert [item["question_id"] for item in still_open] == [
        question[0]["question_id"]]

    assert still_open == question

    # Valid unchanged twin: the same grant re-activated and the same answer.
    token.status = "active"
    route_env["db"].commit()
    accepted = _answer(client, run_id)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["resolved_question_ids"] == [
        question[0]["question_id"]], accepted.json()

    final = lifecycle.get_assignment(run_id)
    assert final["status"] == "completed", {
        "status": final["status"],
        "steps": [(step["adapter"], step["status"],
                   (step.get("result") or {}).get("value"),
                   step.get("error"))
                  for step in final["steps"]],
        "open": _questions(lifecycle, run_id),
        "rounds": accepted.json().get("continuation_rounds"),
    }
    assert len(_source_steps(final)) == 1, [
        (step["adapter"], step["status"]) for step in final["steps"]]
    quotes = _quotes(final)
    assert len(quotes) == 1, [
        (step["adapter"], step["status"]) for step in final["steps"]]
    assert quotes[0]["result"]["value"] == "37.50"
    assert _questions(lifecycle, run_id) == []


def test_public_disconnect_route_refuses_waiting_source_answer(
        route_env, tmp_path, monkeypatch):
    """The shipped UI disconnect, not a direct row edit, revokes the grant."""
    monkeypatch.setenv(
        "ATOM_ASSIGNMENT_OUTPUT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path))
    # Same connected catalog/grant the waiting task will name.
    _seed_connected_grant(route_env, tmp_path)
    _seed_oauth_disconnect_pair(route_env)
    calls = _install_transport(monkeypatch)
    _mount_disconnect_route(route_env, monkeypatch)

    # No provider round-trip is part of this scenario; trip if one happens.
    from core.oauth_handler import OAuthHandler

    external = []

    async def _no_provider(*args, **kwargs):
        external.append("provider")
        raise AssertionError("disconnect must not call the provider")

    monkeypatch.setattr(OAuthHandler, "exchange_code_for_tokens", _no_provider)
    monkeypatch.setattr(OAuthHandler, "refresh_access_token", _no_provider)

    memo = tmp_path / "request.txt"
    memo.write_text("Please prepare the SC-1 quote from the price list.")
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]
    db = route_env["db"]

    run_id = _start(client, memo)
    question = _questions(lifecycle, run_id)
    assert len(question) == 1, question
    assert question[0]["concept"] == "quote_calculation", question[0]
    before = lifecycle.get_assignment(run_id)
    assert _source_steps(before) == []
    assert _quotes(before) == []

    # Precondition: the very grant the catalog read will recheck is active.
    checker = route_env["factory"]()
    try:
        from core.models import IntegrationToken

        granted = checker.query(IntegrationToken).filter_by(
            id="e3-token").one()
        assert granted.status == "active"
    finally:
        checker.close()

    # The owner disconnects Microsoft 365 through the public route the
    # integrations UI calls while the task waits.
    revoked = client.delete("/api/v1/auth/oauth/tokens/microsoft")
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["status"] == "success"
    assert external == []

    # The revocation is in the durable store, not just the response.
    checker = route_env["factory"]()
    try:
        from core.models import IntegrationToken, OAuthToken

        persisted = checker.query(IntegrationToken).filter_by(
            id="e3-token").one()
        assert persisted.status == "revoked"
        page_row = checker.query(OAuthToken).filter_by(
            id="e3-oauth-token").one()
        assert page_row.is_active is False
    finally:
        checker.close()

    # A request-scoped session reads the committed rows; this fixture shares
    # one session across requests, so drop its cached page rows explicitly.
    db.expire_all()
    before_calls = list(calls)
    refused = _answer(client, run_id)
    assert refused.status_code == 403, refused.text
    assert refused.json()["detail"]["error"] == "source_permission_revoked"
    assert calls == before_calls
    after_revoke = lifecycle.get_assignment(run_id)
    assert after_revoke["status"] == before["status"]
    assert _source_steps(after_revoke) == []
    assert _quotes(after_revoke) == []
    still_open = _questions(lifecycle, run_id)
    assert still_open == question
    assert external == []

    # Valid unchanged twin: the same grant re-activated and the same answer.
    checker = route_env["factory"]()
    try:
        from core.models import IntegrationToken

        twin = checker.query(IntegrationToken).filter_by(id="e3-token").one()
        twin.status = "active"
        checker.commit()
    finally:
        checker.close()
    db.expire_all()

    accepted = _answer(client, run_id)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["resolved_question_ids"] == [
        question[0]["question_id"]], accepted.json()
    final = lifecycle.get_assignment(run_id)
    assert final["status"] == "completed", {
        "status": final["status"],
        "steps": [(step["adapter"], step["status"],
                   (step.get("result") or {}).get("value"),
                   step.get("error"))
                  for step in final["steps"]],
        "open": _questions(lifecycle, run_id),
    }
    assert len(_source_steps(final)) == 1, [
        (step["adapter"], step["status"]) for step in final["steps"]]
    quotes = _quotes(final)
    assert len(quotes) == 1, [
        (step["adapter"], step["status"]) for step in final["steps"]]
    assert quotes[0]["result"]["value"] == "37.50"
    assert _questions(lifecycle, run_id) == []
    assert external == []
