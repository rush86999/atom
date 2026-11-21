#!/usr/bin/env python3
"""Bounded synthetic tests for the Outlook message-forward connector action.

These tests never contact Microsoft Graph, read application data, or look up
credentials. They replace the service's one-shot transport with an in-memory
fake so the exact request, acceptance semantics, and uncertain outcomes can be
checked deterministically.
"""

import sys
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import AsyncMock, patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

try:
    import integrations.outlook_service as outlook_service_module
    OutlookService = outlook_service_module.OutlookService
except Exception as exc:  # keep collection working if optional app deps are absent
    outlook_service_module = None
    OutlookService = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


_MISSING = object()


@unittest.skipIf(
    OutlookService is None,
    f"OutlookService is not importable in this environment: {IMPORT_ERROR}",
)
class OutlookForwardEmailTests(unittest.IsolatedAsyncioTestCase):
    async def _run_forward(
        self,
        *,
        status=202,
        response=None,
        error=None,
        user_id="user-1",
        message_id="source/id?1",
        to_recipients=None,
        comment="Please review",
        access_token=_MISSING,
    ):
        service = OutlookService(tenant_id="tenant-1", config={})
        calls = []

        async def fake_graph_request(
            graph_user_id,
            endpoint,
            method="GET",
            data=None,
            access_token=None,
            **kwargs,
        ):
            calls.append(
                {
                    "user_id": graph_user_id,
                    "endpoint": endpoint,
                    "method": method,
                    "data": data,
                    "access_token": access_token,
                    "kwargs": kwargs,
                }
            )
            if error is not None:
                raise error
            service.last_graph_status = status
            return response

        service._make_graph_request = fake_graph_request
        # Any credential lookup at all is a test failure: forward must use only
        # the explicitly supplied, invocation-bound delegated token.
        service._get_access_token = AsyncMock(
            side_effect=AssertionError("forward must not look up credentials")
        )
        service._pinned_access_token = "pinned-token-must-not-be-used"

        recipients = (
            ["first@example.com", "second@example.com"]
            if to_recipients is None
            else to_recipients
        )
        token_kwargs = (
            {"access_token": "delegated-token-1"}
            if access_token is _MISSING
            else {"access_token": access_token}
        )

        result = await service.forward_email(
            user_id,
            message_id,
            recipients,
            comment,
            **token_kwargs,
        )
        return service, calls, result

    async def test_success_uses_exact_documented_request_and_202_acceptance(self):
        message_id = "AAMk/source?=+ #1"
        service, calls, result = await self._run_forward(message_id=message_id)

        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["user_id"], "user-1")
        self.assertEqual(
            call["endpoint"],
            f"/me/messages/{urllib.parse.quote(message_id, safe='')}/forward",
        )
        self.assertEqual(call["method"], "POST")
        self.assertEqual(
            call["data"],
            {
                "toRecipients": [
                    {"emailAddress": {"address": "first@example.com"}},
                    {"emailAddress": {"address": "second@example.com"}},
                ],
                "comment": "Please review",
            },
        )
        self.assertEqual(call["access_token"], "delegated-token-1")
        self.assertIs(call["kwargs"].get("allow_redirects"), False)

        self.assertEqual(result["status"], "provider_accepted")
        self.assertTrue(result["provider_accepted"])
        self.assertFalse(result["effect_uncertain"])
        self.assertEqual(result["outcome"], "provider_accepted")
        self.assertEqual(result["http_status"], 202)
        self.assertEqual(result["message_id"], message_id)
        service._get_access_token.assert_not_awaited()

    async def test_comment_is_optional_and_omitted_when_empty(self):
        _service, calls, result = await self._run_forward(comment=None)

        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0]["data"],
            {
                "toRecipients": [
                    {"emailAddress": {"address": "first@example.com"}},
                    {"emailAddress": {"address": "second@example.com"}},
                ]
            },
        )
        self.assertEqual(result["status"], "provider_accepted")

    async def test_missing_input_never_calls_the_provider(self):
        cases = [
            ("invalid_user_id", {"user_id": ""}),
            ("invalid_message_id", {"message_id": "   "}),
            ("invalid_recipients", {"to_recipients": []}),
            ("invalid_recipients", {"to_recipients": ["ok@example.com", ""]}),
            ("invalid_comment", {"comment": object()}),
            ("missing_access_token", {"access_token": None}),
        ]

        for expected_reason, overrides in cases:
            with self.subTest(reason=expected_reason, overrides=overrides):
                service, calls, result = await self._run_forward(**overrides)

                self.assertEqual(calls, [])
                self.assertEqual(result["status"], "not_forwarded")
                self.assertFalse(result["provider_accepted"])
                self.assertFalse(result["effect_uncertain"])
                self.assertEqual(result["reason"], expected_reason)
                service._get_access_token.assert_not_awaited()

    async def test_conclusive_provider_denials_are_not_forwarded(self):
        for status in (400, 401, 403, 404, 422, 429):
            with self.subTest(status=status):
                _service, calls, result = await self._run_forward(
                    status=status,
                    response=None,
                )

                # Exactly one submission: a denial must not be retried.
                self.assertEqual(len(calls), 1)
                self.assertEqual(result["status"], "not_forwarded")
                self.assertFalse(result["provider_accepted"])
                self.assertFalse(result["effect_uncertain"])
                self.assertEqual(result["http_status"], status)
                self.assertEqual(result["reason"], "provider_rejected")

    async def test_timeout_5xx_and_transport_failure_are_uncertain_and_not_retried(self):
        cases = [
            (408, None, "timeout"),
            (500, None, "provider_error"),
            (503, None, "provider_error"),
            (None, RuntimeError("connection reset"), "transport_error"),
        ]

        for status, error, expected_reason in cases:
            with self.subTest(status=status, error=error):
                _service, calls, result = await self._run_forward(
                    status=status,
                    error=error,
                )

                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0]["access_token"], "delegated-token-1")
                self.assertEqual(result["status"], "unknown")
                self.assertIsNone(result["provider_accepted"])
                self.assertTrue(result["effect_uncertain"])
                self.assertEqual(result["outcome"], "unknown_effect")
                self.assertEqual(result["reason"], expected_reason)

    async def test_unexpected_success_status_is_not_exact_acceptance(self):
        _service, calls, result = await self._run_forward(
            status=200,
            response={"success": True},
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["provider_accepted"])
        self.assertTrue(result["effect_uncertain"])
        self.assertEqual(result["reason"], "inconclusive_status")
        self.assertEqual(result["http_status"], 200)

    async def test_307_is_not_followed_and_receipt_stays_uncertain(self):
        class FakeResponse:
            status = 307

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc_info):
                return False

            async def text(self):
                return ""

            async def json(self):
                return {}

        sessions = []

        class FakeClientSession:
            def __init__(self, *args, **kwargs):
                self.posts = []
                sessions.append(self)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc_info):
                return False

            def post(self, url, **kwargs):
                self.posts.append((url, kwargs))
                return FakeResponse()

        service = OutlookService(tenant_id="tenant-1", config={})
        service._get_access_token = AsyncMock(
            side_effect=AssertionError("forward must not look up credentials")
        )
        service._pinned_access_token = "pinned-token-must-not-be-used"

        with patch.object(
            outlook_service_module.aiohttp,
            "ClientSession",
            FakeClientSession,
        ):
            result = await service.forward_email(
                "user-1",
                "source-id",
                ["recipient@example.com"],
                "Please review",
                access_token="delegated-token-1",
            )

        # The real transport must submit once and must not follow the 307.
        self.assertEqual(len(sessions), 1)
        self.assertEqual(len(sessions[0].posts), 1)
        url, kwargs = sessions[0].posts[0]
        self.assertTrue(url.endswith("/me/messages/source-id/forward"))
        self.assertIs(kwargs["allow_redirects"], False)
        self.assertEqual(
            kwargs["json"],
            {
                "toRecipients": [
                    {"emailAddress": {"address": "recipient@example.com"}}
                ],
                "comment": "Please review",
            },
        )

        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["provider_accepted"])
        self.assertTrue(result["effect_uncertain"])
        self.assertEqual(result["http_status"], 307)
        self.assertEqual(result["reason"], "inconclusive_status")
        service._get_access_token.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
