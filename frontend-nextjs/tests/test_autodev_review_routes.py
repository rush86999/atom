

# ── guidance: tool-error pattern → feed event → API ─────────────────────────

def test_guidance_lists_tool_error_pattern_notices():
    from core.models import AgentFeedEvent

    events = [SimpleNamespace(
        id="g1", agent_id=AGENT, event_type="autodev_guidance",
        message="outlook.search_emails has failed 3× recently",
        data={"kind": "tool_error_pattern",
              "detail": "tool_error: 400 Syntax error"},
        importance=2, timestamp="2026-09-02T18:00:00",
    )]
    db = _StubDB({review_routes.AgentFeedEvent: events})
    client = _make_client(db)

    r = client.get("/api/autodev/guidance")
    assert r.status_code == 200
    body = r.json()["data"]["guidance"]
    assert len(body) == 1
    assert body[0]["kind"] == "tool_error_pattern"
    assert "3×" in body[0]["title"]


def test_notify_tool_error_pattern_dedupes_within_hour():
    """A tool failing 10 times must produce ONE hourly guidance, not 10."""
    from core.auto_dev import guidance

    calls = []
    original = guidance._emit
    def _capture(**kwargs):
        calls.append(kwargs)
    guidance._emit = _capture
    try:
        for _ in range(5):
            guidance.notify_tool_error_pattern(
                agent_id=AGENT, tenant_id=TENANT,
                signature="outlook.search_emails", count=3,
                last_error="400 '@'",
            )
        assert len(calls) == 1, "hourly dedupe must suppress repeats"
        # A different signature is a different message.
        guidance.notify_tool_error_pattern(
            agent_id=AGENT, tenant_id=TENANT,
            signature="gmail.send_message", count=2, last_error="500",
        )
        assert len(calls) == 2
    finally:
        guidance._emit = original
        guidance._notified.clear()
