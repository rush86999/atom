"""
P1.1 regression tests — actionable "no LLM provider" error.

Verifies:
- NoProvidersConfiguredError is raised (not bare ValueError) when no clients.
- It subclasses ValueError so legacy `except ValueError` blocks still catch it.
- The structured payload carries a recovery_url the UI deep-links to.
- to_dict() shape matches what atom_agent_endpoints.py reads back.

Run: PYTHONPATH=backend pytest backend/tests/unit/llm/test_no_providers_error.py -v
"""
import pytest

from core.llm.byok_handler import (
    BYOKHandler,
    NoProvidersConfiguredError,
    QueryComplexity,
)


def _empty_handler() -> BYOKHandler:
    """Construct a BYOKHandler with zero configured clients."""
    handler = BYOKHandler.__new__(BYOKHandler)
    handler.clients = {}
    return handler


def test_no_providers_raises_structured_error():
    """get_optimal_provider must raise NoProvidersConfiguredError, not ValueError."""
    handler = _empty_handler()
    with pytest.raises(NoProvidersConfiguredError) as exc_info:
        # get_optimal_provider is async even when clients is empty (it calls
        # get_ranked_providers first, which returns [] when clients is empty,
        # then hits the fallback that raises). Use asyncio.run-equivalent.
        import asyncio
        asyncio.run(handler.get_optimal_provider(QueryComplexity.SIMPLE))

    err = exc_info.value
    assert err.recovery_url == "/settings/ai"
    assert err.error_code == "no_llm_provider"
    assert "provider" in err.message.lower()


def test_subclasses_value_error_for_backward_compat():
    """Legacy callers that catch ValueError must keep working."""
    handler = _empty_handler()
    import asyncio
    with pytest.raises(ValueError):  # broad catch still works
        asyncio.run(handler.get_optimal_provider(QueryComplexity.SIMPLE))


def test_to_dict_shape_matches_endpoint_contract():
    """atom_agent_endpoints.py reads error_code, message, recovery_url off the exception."""
    err = NoProvidersConfiguredError()
    payload = err.to_dict()
    assert set(payload.keys()) == {"error_code", "message", "recovery_url"}
    assert payload["error_code"] == "no_llm_provider"
    assert payload["recovery_url"] == "/settings/ai"


def test_custom_message_preserved():
    custom = NoProvidersConfiguredError(message="Custom recovery guidance")
    assert custom.message == "Custom recovery guidance"
    assert "Custom recovery guidance" in str(custom)
