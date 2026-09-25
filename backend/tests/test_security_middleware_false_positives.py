"""Regression: request-security rules must match real vectors, not
mid-word substrings of ordinary content.

Live 2026-09-25: the agent's own workbook provenance line
'content_hash=…' contains 'ontent_hash=' — the unanchored on\\w+\\s*= rule
rejected every canvas chat turn whose conversation_history carried a
workbook answer (POST /api/chat/message → 400 'Invalid request content'),
bricking the conversation with 'Could not reach the agent'. Same class:
'confirmation=', 'connection_id=', 'retrieval(' (eval\\().
"""
from unittest.mock import MagicMock

from core.security.middleware import InputValidationMiddleware


def _mw() -> InputValidationMiddleware:
    return InputValidationMiddleware(app=MagicMock())


class TestLegitimateContentPasses:
    def test_workbook_provenance_line_passes(self):
        # The exact substring the live canvas turn was rejected on.
        provenance = (
            "resource=u8ai1e3a4ceb717574b5bbf20429142d718b4, "
            "ingested=2026-09-07T23:06:19, "
            "content_hash=ff2597d26fc6d0ea216c (sha1), "
            "source_modified=unknown, 46 sheet(s) indexed."
        )
        assert _mw()._contains_malicious_content(provenance) is False

    def test_on_prefixed_key_words_pass(self):
        for text in (
            "confirmation=yes",
            "connection_id=abc-123",
            "location=warehouse",
            "duration=10 weeks",
        ):
            assert _mw()._contains_malicious_content(text) is False, text

    def test_midword_exec_family_passes(self):
        for text in (
            "data retrieval(x) latency",
            "medieval(ish) settings",
            "reexecution(steps)",
        ):
            assert _mw()._contains_malicious_content(text) is False, text

    def test_full_canvas_chat_body_passes(self):
        """The reconstructed panel payload: message + canvas_content (email
        draft with styled HTML table) + history carrying a workbook answer."""
        import json

        body = json.dumps({
            "message": "try search again",
            "context": {
                "canvas_id": "0e4defa5-a0f3-4e56-b8a7-976c0a93d4fb",
                "canvas_title": "Quote – Roper Whitney Roll Bender",
                "conversation_history": [
                    {"role": "user", "content": "find the prices"},
                    {"role": "assistant", "content": (
                        "MATERIALIZED COPY — resource=u8ai1e3a4ceb717574b5"
                        "bbf20429142d718b4, content_hash=ff2597d26fc6d0ea"
                        "216c (sha1), source_modified=unknown")},
                ],
            },
        })
        assert _mw()._contains_malicious_content(body) is False


class TestRealVectorsStillRejected:
    def test_every_rule_still_fires(self):
        mw = _mw()
        vectors = {
            "xss_script_tag": "<script>alert(1)</script>",
            "js_protocol": "javascript:alert(1)",
            "xss_event_handler": "<img src=x onerror=alert(1)>",
            "xss_event_handler_spaced": "onclick =x",
            "sqli_union_select": "union select 1",
            "sqli_drop_table": "drop table users",
            "code_exec_exec": "exec(code)",
            "code_exec_eval": "eval(code)",
            "code_exec_system": "system(cmd)",
            "css_expression": "width: expression(alert(1));",
            "vbscript_protocol": "vbscript:msgbox",
            "css_behavior": "div { behavior: url(xss.htc); }",
            "css_binding": "a { binding: url('javascript:alert(1)'); }",
            "css_binding_moz": "body { -moz-binding: url('javascript:alert(1)'); }",
        }
        for _label, payload in vectors.items():
            rule = mw._find_malicious_rule(payload)
            assert rule is not None, payload
        # Entity-encoded payloads decode before matching (stored-XSS vector).
        assert mw._contains_malicious_content(
            "<img src=x onerror&#x3d;alert(1)>") is True


class TestRejectionLoggingIdentifiers:
    def test_rule_id_returned(self):
        rule = _mw()._find_malicious_rule("<img src=x onerror=alert(1)>")
        assert rule is not None and rule[0] == "xss_event_handler"

    def test_field_paths_are_json_identifiers(self):
        import json

        body = json.dumps({
            "message": "hello",
            "context": {
                "conversation_history": [
                    {"role": "assistant", "content": "<script>x</script>"},
                ],
            },
        })
        paths = _mw()._malicious_field_paths(body)
        assert paths == [
            "context.conversation_history[0].content",
        ]

    def test_non_json_body_yields_no_paths(self):
        assert _mw()._malicious_field_paths("<not json onerror=x") == []

    def test_rejected_rule_rides_the_400_body(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.add_middleware(InputValidationMiddleware)

        @app.post("/probe")
        async def probe():
            return {"ok": True}

        client = TestClient(app)
        response = client.post(
            "/probe", json={"content": "<img src=x onerror=alert(1)>"})
        assert response.status_code == 400
        assert response.json()["rejected_rule"] == "xss_event_handler"
        assert response.json()["error"] == "Invalid request content"
