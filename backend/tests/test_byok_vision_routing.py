"""BYOK vision routing — image turns must take images into account in the
BYOK layer: vision-capable candidates ranked up front (required_capability),
composite BYOK model ids ("openrouter/openai/gpt-4o") recognized as vision
via prefix-tolerant capability lookups, and context-window estimation
charged for the image.
"""

from types import SimpleNamespace

from core.llm.byok_handler import BYOKHandler


def _handler_with_fetcher(capabilities_by_name):
    """A handler shell with only the pieces the vision checks touch."""
    handler = object.__new__(BYOKHandler)

    class _Fetcher:
        def __init__(self):
            self.calls = []

        def get_model_capabilities(self, name):
            self.calls.append(name)
            return capabilities_by_name.get(name, {
                "supports_tools": True,
                "supports_vision": False,
                "supports_reasoning": False,
            })

    handler.pricing_fetcher = _Fetcher()
    return handler


def test_model_supports_vision_recognizes_composite_byok_ids():
    """The pricing cache keys the base name; the router id carries a
    provider prefix. A false negative here demoted perfectly good BYOK
    vision models during vision routing."""
    handler = _handler_with_fetcher({
        "gpt-4o": {"supports_vision": True},
    })
    assert handler._model_supports_vision("openrouter/openai/gpt-4o") is True


def test_model_supports_vision_false_stays_false():
    handler = _handler_with_fetcher({})
    assert handler._model_supports_vision("some/text-only-model") is False


def test_capability_filter_tries_stripped_variants():
    handler = object.__new__(BYOKHandler)
    index = {"gpt-4o": ["chat", "vision"]}
    assert handler._filter_by_capabilities(
        "openrouter/openai/gpt-4o", "vision", capability_index=index
    ) is True
    assert handler._filter_by_capabilities(
        "openrouter/openai/gpt-4o", "computer_use", capability_index=index
    ) is False


def test_unknown_models_pass_the_capability_filter():
    """Conservative pass-through: an unverified BYOK model is not dropped
    for a capability we can't verify — quality/health filters still apply."""
    handler = object.__new__(BYOKHandler)
    assert handler._filter_by_capabilities(
        "mystery/model-9000", "vision", capability_index={}
    ) is True


def test_generate_response_ranks_with_vision_capability():
    """Source contract: the chat completion ranking call must pass
    required_capability='vision' and charge the image-token estimate when
    an image is present — this is what makes BYOK vision models surface
    instead of a GPT-4o panic fallback."""
    src = open("core/llm/byok_handler.py").read()
    assert 'required_capability=("vision" if requires_vision else None)' in src
    assert "_image_tokens = 1106 if requires_vision else 0" in src
    assert "estimated_tokens=max(1000, _est_input_chars // 4) + _image_tokens" in src
