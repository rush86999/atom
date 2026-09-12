"""Computer-use model pool for the BPC router (research: 2026-09).

The loop itself never branches on model identity — model choice is
capability data. Entries here get the ``computer_use`` capability so
get_ranked_providers(required_capability="computer_use") can discover
them as fallbacks behind the explicit ATOM_COMPUTER_USE_MODEL pin.

Evidence base (sources recorded per entry):
- Claude 4.6 + the computer-use tool (computer_20250124) holds the top
  OSWorld-Verified scores: Opus 4.6 72.7%, Sonnet 4.6 72.5% (Anthropic
  announcements, steel.dev leaderboard).
- OpenAI's purpose-built CUA (computer-use-preview, Responses API) leads
  browser-only work (WebArena ~87%); $3/$12 per MTok (OpenAI/Azure list
  pricing pages).
- gpt-6-astra (already the repo default via lux_config) leads GUI
  grounding (ScreenSpot-Pro ~92.7%).

Pricing discipline (AGENTS.md §2 — evidence over plausibility): only
models whose list prices could be verified are registered. Gemini 2.5
Computer Use and the open pool (UI-TARS, Qwen3-VL) are recorded below as
DOCUMENTED CANDIDATES — registering a guessed price would poison BPC
cost ranking and the pricing cache. Enable one only after verifying its
price and capability against the provider's pricing page.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Verified entries: provider, model, list prices (USD per token),
# capabilities, and the evidence trail.
OPERATOR_MODEL_POOL: List[Dict[str, Any]] = [
    {
        "provider": "anthropic",
        "model_name": "claude-opus-4-6",
        "context_window": 200000,
        "input_price_per_token": 0.000005,   # $5 / MTok
        "output_price_per_token": 0.000025,  # $25 / MTok
        "capabilities": ["vision", "tools", "computer_use", "agentic"],
        "provider_metadata": {
            "source": "operator_pool_research_2026-09",
            "specialization": "computer_use",
            "evidence": "OSWorld-Verified 72.7%; computer-use tool "
                        "computer_20250124 (Anthropic/steel.dev)",
        },
    },
    {
        "provider": "anthropic",
        "model_name": "claude-sonnet-4-6",
        "context_window": 200000,
        "input_price_per_token": 0.000003,   # $3 / MTok
        "output_price_per_token": 0.000015,  # $15 / MTok
        "capabilities": ["vision", "tools", "computer_use", "agentic"],
        "provider_metadata": {
            "source": "operator_pool_research_2026-09",
            "specialization": "computer_use",
            "evidence": "OSWorld-Verified 72.5%; computer-use tool "
                        "computer_20250124 (Anthropic/steel.dev)",
        },
    },
    {
        "provider": "openai",
        "model_name": "computer-use-preview",
        "context_window": 128000,
        "input_price_per_token": 0.000003,   # $3 / MTok
        "output_price_per_token": 0.000012,  # $12 / MTok
        "capabilities": ["vision", "tools", "computer_use", "agentic"],
        "provider_metadata": {
            "source": "operator_pool_research_2026-09",
            "specialization": "computer_use",
            "evidence": "WebArena ~87% browser-only leader; Responses API "
                        "computer_use_preview (OpenAI/Azure pricing pages)",
        },
    },
]

# Documented, NOT registered: competitive on OSWorld boards but list
# pricing unverified as of 2026-09. Verify price + capability against the
# provider's own pricing page, then promote into OPERATOR_MODEL_POOL.
OPERATOR_MODEL_CANDIDATES_UNPRICED: List[Dict[str, Any]] = [
    {
        "provider": "google",
        "model_name": "gemini-2.5-computer-use",
        "note": "Google claims browser/mobile edge; pricing page varies by "
                "preview status — verify before registering.",
    },
    {
        "provider": "openrouter",
        "model_name": "ui-tars",
        "note": "ByteDance open GUI-agent family, competitive on OSWorld "
                "boards; OpenRouter catalog price must be checked at "
                "registration time.",
    },
]


def register_operator_model_pool(service, tenant_id: str,
                                 enabled: bool = True) -> list:
    """Upsert the verified computer-use pool for a tenant.

    ``service`` is an LLMRegistryService; called from
    register_computer_use_models so existing startup wiring picks the pool
    up without new call sites.
    """
    if not enabled:
        return []
    registered = []
    for model_data in OPERATOR_MODEL_POOL:
        try:
            model = service.upsert_model(tenant_id, dict(model_data))
            if "computer_use" not in model.capabilities:
                model.capabilities.append("computer_use")
            model.sync_capabilities()
            service.db.flush()
            registered.append(model)
        except Exception as exc:
            logger.error(
                f"failed to register computer-use model "
                f"{model_data['model_name']}: {exc}")
    return registered
