"""Focused tests for sending one already-persisted Outlook draft.

The transport is synthetic: each test replaces only the instance's
``_make_graph_request`` coroutine and records the single call it receives.
No provider, database, or module is stubbed.
"""

import asyncio
import inspect
import sys
import urllib.parse
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

pytest.importorskip("aiohttp")

try:
    from integrations.outlook_service import OutlookService
except ImportError as exc:  # pragma: no cover - only when app deps are absent
    pytest.skip(
        f"Outlook service dependencies unavailable: {exc}",
        allow_module_level=True,
    )


def _service(*, result=None, status=None, transport_error=None):
    """An OutlookService whose Graph transport records and returns one result."""
    service = object.__new__(OutlookService)
    service.last_graph_status = 599
    service.last_transport_error = "stale transport error"
    service.last_send_error = {"stale": True}
    calls = []

    async def transport(
        user_id,
        endpoint,
        method="GET",
        data=None,
        access_token=None,
        full_url=False,
        extra_headers=None,
    ):
        calls.append(
            {
                "user_id": user_id,
                "endpoint": endpoint,
                "method": method,
                "data": data,
                "access_token": access_token,
                "full_url": full_url,
                "extra_headers": extra_headers,
                "state_at_call": (
                    service.last_graph_status,
                    service.last_transport_error,
                    service.last_send_error,
                ),
            }
        )
        service.last_graph_status = status
        service.last_transport_error = transport_error
        return result

    service._make_graph_request = transport
    return service, calls


def test_sends_the_exact_encoded_id_once_with_immutable_prefer_header():
    message_id = "AAMkAGI/abc+def==?x=1#fragment"
    service, calls = _service(result={"success": True}, status=202)

    result = asyncio.run(
        service.send_existing_immutable_draft("user-1", message_id)
    )

    assert len(calls) == 1
    call = calls[0]
    assert call["user_id"] == "user-1"
    assert call["method"] == "POST"
    assert call["endpoint"] == (
        "/me/messages/" + urllib.parse.quote(message_id, safe="") + "/send"
    )
    assert "%2F" in call["endpoint"]
    assert call["data"] == {}
    assert call["full_url"] is False
    assert call["access_token"] is None  # no caller token override exists
    assert call["extra_headers"] == {"Prefer": 'IdType="ImmutableId"'}
    assert call["state_at_call"] == (None, None, None)

    assert result["status"] == "provider_accepted"
    assert result["provider_accepted"] is True
    assert result["sent_items_verified"] is False
    assert result["effect_uncertain"] is False
    assert result["message_id"] == message_id


def test_has_no_token_parameter():
    parameters = inspect.signature(
        OutlookService.send_existing_immutable_draft
    ).parameters
    assert "token" not in parameters


@pytest.mark.parametrize("bad_id", [None, "", "   "])
def test_refuses_a_missing_or_empty_id_without_transport(bad_id):
    service, calls = _service()

    result = asyncio.run(
        service.send_existing_immutable_draft("user-1", bad_id)
    )

    assert calls == []
    assert result["status"] == "not_sent"
    assert result["reason"] == "invalid_message_id"
    assert result["effect_uncertain"] is False
    assert result["sent_items_verified"] is False
    assert service.last_graph_status is None
    assert service.last_transport_error is None


def test_404_is_uncertain_because_an_earlier_send_can_look_like_not_found():
    service, calls = _service(status=404)

    result = asyncio.run(
        service.send_existing_immutable_draft("user-1", "immutable-draft-id")
    )

    assert len(calls) == 1
    assert result["status"] == "unknown"
    assert result["reason"] == "draft_not_found_or_already_sent"
    assert result["effect_uncertain"] is True
    assert result["provider_accepted"] is None
    assert result["sent_items_verified"] is False


def test_timeout_and_5xx_are_uncertain():
    cases = [
        _service(transport_error="timed out"),
        _service(status=500),
        _service(status=503),
    ]
    for service, calls in cases:
        result = asyncio.run(
            service.send_existing_immutable_draft("user-1", "immutable-draft-id")
        )
        assert len(calls) == 1
        assert result["status"] == "unknown"
        assert result["effect_uncertain"] is True
        assert result["provider_accepted"] is None
        assert result["sent_items_verified"] is False


def test_non_202_success_is_not_treated_as_verified():
    service, calls = _service(result={"success": True}, status=200)

    result = asyncio.run(
        service.send_existing_immutable_draft("user-1", "immutable-draft-id")
    )

    assert len(calls) == 1
    assert result["status"] == "unknown"
    assert result["reason"] == "inconclusive_status"
    assert result["effect_uncertain"] is True
    assert result["sent_items_verified"] is False


def test_an_explicit_non_404_denial_is_not_sent():
    service, calls = _service(status=400)

    result = asyncio.run(
        service.send_existing_immutable_draft("user-1", "immutable-draft-id")
    )

    assert len(calls) == 1
    assert result["status"] == "not_sent"
    assert result["reason"] == "provider_rejected"
    assert result["provider_accepted"] is False
    assert result["effect_uncertain"] is False
    assert result["sent_items_verified"] is False
