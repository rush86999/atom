from core.assignment_plan import new_step


def test_long_outbound_body_survives_step_sanitization():
    body = ("This is a long authorized outbound body.\n\n" * 80).strip()
    assert len(body) > 1000
    step = new_step(
        step_id="send",
        title="Send the approved response",
        operation_type="outbound",
        adapter="email.send_outlook",
        inputs={"to": ["owner@example.invalid"], "subject": "S", "body": body},
        effect="external",
        approval_required=True,
    )
    assert step["inputs"]["body"] == body
    assert step["inputs"]["to"] == ["owner@example.invalid"]
