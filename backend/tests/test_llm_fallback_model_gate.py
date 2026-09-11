"""Local providers must not be offered a gateway-namespaced model id.

Live 2026-09-11 (Sales Agent canvas turn, session agent-fix-…): OpenRouter
streamed an empty completion for ``z-ai/glm-5.3-flash``; the streaming
fallback then tried the SAME id on ``ollama`` (404 — a local runtime does not
have gateway catalog models) and the turn died with "All 2 providers failed
for z-ai/glm-5.3-flash". ``_provider_serves_model`` advertised local runtimes
as serving ANY model name, so the fallback-eligibility gate let it through.

Rule: a local/open runtime serves arbitrary BARE model names (llama3:8b,
qwen2.5-coder-7b-instruct), but a ``namespace/model`` id is a gateway catalog
model and must not be sent to a local runtime as a fallback. The requested
primary provider is still always tried by the callers, so an explicitly
selected local model keeps working.
"""
from core.llm import byok_handler


def _handler():
    return byok_handler.BYOKHandler.__new__(byok_handler.BYOKHandler)


def test_local_provider_rejects_gateway_namespaced_model():
    h = _handler()
    assert h._provider_serves_model("ollama", "z-ai/glm-5.3-flash") is False
    assert h._provider_serves_model("vllm", "qwen/qwen3.8-flash") is False


def test_local_provider_still_serves_bare_model_names():
    h = _handler()
    assert h._provider_serves_model("ollama", "llama3:8b") is True
    assert h._provider_serves_model(
        "lmstudio", "qwen2.5-coder-7b-instruct") is True


def test_gateways_still_serve_their_catalog():
    h = _handler()
    assert h._provider_serves_model("openrouter", "z-ai/glm-5.3-flash") is True
    assert h._provider_serves_model("opencode-go", "deepseek-v4-flash") is True
