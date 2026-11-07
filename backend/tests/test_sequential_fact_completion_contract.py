"""Information arrival is not itself a verified business outcome.

Public assignment/source routes and executor are real. The existing proposal
fixture controls model choices; this does not claim served model judgment.
"""
from tests.test_task_wait_two_fact_events import (
    route_env,
    _fixtures,
    _install_transport,
    _start,
    _reconciliations,
    _applied_artifacts,
)


def test_answering_all_facts_without_business_work_does_not_complete(
        route_env, tmp_path, monkeypatch):
    from api import assignment_routes as routes
    from core.employee_adaptation import WorkAdaptationProposal

    monkeypatch.setenv("ATOM_ASSIGNMENT_OUTPUT_DIR", str(tmp_path / "reports"))
    po, invoice, receiving = _fixtures(tmp_path)
    _install_transport(monkeypatch)
    original = routes.propose_adaptation
    calls = []

    async def retain_when_ready(context, observations, **kwargs):
        capabilities = context.get("available_business_operations") or []
        ready = any(
            capability.get("operation") == "invoice_reconciliation"
            and capability.get("status") == "ready"
            for capability in capabilities
        )
        if ready:
            calls.append("retain-ready")
            proposal = WorkAdaptationProposal(
                decision="retain",
                reason="No business work selected",
                observation_ids=[item["observation_id"] for item in observations],
            )
            return {
                "proposal": proposal.model_dump(),
                "source": "model",
                "technical_fallback": False,
                "errors": [],
            }
        return await original(context, observations, **kwargs)

    monkeypatch.setattr(routes, "propose_adaptation", retain_when_ready)
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]
    run_id = _start(client, po)
    for path in (invoice, receiving):
        response = client.post(
            f"/api/assignments/{run_id}/sources",
            json={"source": {"path": str(path)}},
        )
        assert response.status_code == 200, response.text

    final = lifecycle.get_assignment(run_id)
    assert calls, "the model must reach the ready-but-retain boundary"
    assert _reconciliations(final) == []
    assert final["status"] != "completed", (
        "Evidence arrival must not complete a job without reconciliation")
    assert _applied_artifacts(final) == [], (
        "No final report may appear without the required business result")
