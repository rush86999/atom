"""
Dynamic AI Provider Pricing Fetcher
Fetches real-time pricing from LiteLLM's maintained pricing database and OpenRouter API.
"""

import asyncio
from datetime import datetime, timedelta
import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

# LiteLLM pricing database URL (regularly maintained)
LITELLM_PRICING_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"

# OpenRouter models endpoint
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# OpenCode Zen models endpoint (OpenCode Go subscription gateway)
OPENCODE_MODELS_URL = "https://opencode.ai/zen/v1/models"

# Cache file path — anchored to backend/ so the store is independent of the
# launch CWD. A root-vs-backend launch previously maintained TWO divergent
# caches: a launch from the repo root silently read a stale snapshot without
# the OpenRouter catalog, and every refresh wrote to the other file
# (same class of bug as the LanceDB/DATABASE_URL anchoring).
def _anchor_data_path(filename: str) -> Path:
    path = Path(filename)
    if path.is_absolute():
        return path
    return Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / filename


PRICING_CACHE_PATH = _anchor_data_path("data/ai_pricing_cache.json")

# Cache duration (24 hours)
CACHE_DURATION_HOURS = 24

# Phase M staleness gate (plan v2): rolling per-refresh diff history for the
# openrouter slice of the cache + BPC-side expired-candidate counters.
# Measurement ONLY — decides whether a server-side query-param candidate path
# is ever worth building (see docs/testing/TESTED_FILES_TRACKER.md).
STALENESS_STATS_PATH = _anchor_data_path("data/pricing_staleness_stats.json")
STALENESS_HISTORY_CAP = 50


def is_expiration_past(value: Optional[str], now: Optional[datetime] = None) -> bool:
    """True when an OpenRouter ``expiration_date`` is in the past.

    Tolerant by design: None/empty/unparseable → False (fail-open; the date
    semantically means "may be removed", never a hard routing signal here).
    """
    if not value:
        return False
    try:
        exp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if exp.tzinfo is not None:
            exp = exp.replace(tzinfo=None)
        return exp < (now or datetime.now())
    except (ValueError, TypeError):
        return False


def compute_staleness_stats(
    previous: Dict[str, Any],
    current: Dict[str, Any],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Diff the openrouter-sourced slice of two pricing caches.

    Returns added/removed model ids, ids still cached past their
    ``expiration_date``, and the current openrouter count.
    """
    prev_or = {k for k, v in (previous or {}).items()
               if isinstance(v, dict) and v.get("source") == "openrouter"}
    curr_items = {k: v for k, v in (current or {}).items()
                  if isinstance(v, dict) and v.get("source") == "openrouter"}
    curr_keys = set(curr_items)
    expired = sorted(
        mid for mid, v in curr_items.items() if is_expiration_past(v.get("expiration_date"), now)
    )
    return {
        "generated_at": (now or datetime.now()).isoformat(),
        "added": sorted(curr_keys - prev_or),
        "removed": sorted(prev_or - curr_keys),
        "expired_served": expired,
        "openrouter_count": len(curr_keys),
    }


class DynamicPricingFetcher:
    """
    Fetches and caches AI provider pricing from multiple sources.
    Primary: LiteLLM's model_prices database
    Fallback: OpenRouter API
    """
    
    def __init__(self):
        self.pricing_cache: Dict[str, Any] = {}
        self.last_fetch: Optional[datetime] = None
        # Phase M staleness measurement (see module docstring near STALENESS_STATS_PATH)
        self.bpc_stale_seen: Dict[str, int] = {}
        self.staleness_history: List[Dict[str, Any]] = []
        self._load_cache()
    
    def _load_cache(self):
        """Load pricing from local cache file"""
        try:
            if PRICING_CACHE_PATH.exists():
                with open(PRICING_CACHE_PATH, 'r') as f:
                    data = json.load(f)
                    self.pricing_cache = data.get("pricing", {})
                    last_fetch_str = data.get("last_fetch")
                    if last_fetch_str:
                        self.last_fetch = datetime.fromisoformat(last_fetch_str)
                    logger.info(f"Loaded {len(self.pricing_cache)} model prices from cache")
        except Exception as e:
            logger.warning(f"Could not load pricing cache: {e}")
    
    def _save_cache(self):
        """Save pricing to local cache file"""
        try:
            PRICING_CACHE_PATH.parent.mkdir(exist_ok=True)
            data = {
                "pricing": self.pricing_cache,
                "last_fetch": self.last_fetch.isoformat() if self.last_fetch else None,
                "source": "litellm+openrouter"
            }
            with open(PRICING_CACHE_PATH, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self.pricing_cache)} model prices to cache")
        except Exception as e:
            logger.error(f"Could not save pricing cache: {e}")
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        if not self.last_fetch or not self.pricing_cache:
            return False
        age = datetime.now() - self.last_fetch
        return age < timedelta(hours=CACHE_DURATION_HOURS)
    
    async def fetch_litellm_pricing(self) -> Dict[str, Any]:
        """Fetch pricing from LiteLLM's GitHub repository"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(LITELLM_PRICING_URL)
                response.raise_for_status()
                data = response.json()

                # Transform to our format
                pricing = {}
                for model_name, model_data in data.items():
                    if not isinstance(model_data, dict):
                        continue
                    # PRESERVE the catalog row/metadata even when monetary
                    # price is unknown; only OMIT an invalid provided rate
                    # (never default it to 0). Context-window consumers read
                    # max_input_tokens/max_tokens from this row.
                    _rates = {}
                    for _rk in ("input_cost_per_token",
                                "output_cost_per_token",
                                # Audio/transcription rows are priced by TIME.
                                # Preserve those units instead of dropping the
                                # only material rate an audio model has.
                                "input_cost_per_second",
                                "output_cost_per_second"):
                        _rv = model_data.get(_rk)
                        if _rv is None:
                            continue
                        if self.rate_is_valid(_rv):
                            _rates[_rk] = float(_rv)
                    pricing[model_name] = {
                        **_rates,
                        "max_tokens": model_data.get("max_tokens", 0),
                        "max_input_tokens": model_data.get("max_input_tokens", 0),
                        "max_output_tokens": model_data.get("max_output_tokens", 0),
                        "litellm_provider": model_data.get("litellm_provider", "unknown"),
                        "mode": model_data.get("mode", "chat"),
                        "source": "litellm",
                        "supports_cache": model_data.get("supports_cache", False),  # Cache support metadata
                    }

                # Add MiniMax models fallback if not in LiteLLM yet
                for _m3 in ("MiniMax-M3", "MiniMax-M3-highspeed"):
                    if _m3 not in pricing:
                        pricing[_m3] = {
                            "input_cost_per_token": 0.000001,
                            "output_cost_per_token": 0.000001,
                            "max_tokens": 512000,
                            "litellm_provider": "minimax",
                            "mode": "chat",
                            "source": "estimated",
                            "supports_cache": False,
                        }
                for _m27 in ("MiniMax-M2.7", "MiniMax-M2.7-highspeed"):
                    if _m27 not in pricing:
                        pricing[_m27] = {
                            "input_cost_per_token": 0.000001,
                            "output_cost_per_token": 0.000001,
                            "max_tokens": 204000,
                            "litellm_provider": "minimax",
                            "mode": "chat",
                            "source": "estimated",
                            "supports_cache": False,
                        }

                # Zhipu AI GLM family fallback if not in LiteLLM yet
                _glm_models = {
                    "glm-5.2": {"input": 0.000002, "output": 0.000002, "ctx": 1000000},
                    "glm-5": {"input": 0.0000015, "output": 0.0000015, "ctx": 200000},
                    "glm-4.6": {"input": 0.0000005, "output": 0.0000005, "ctx": 128000},
                    "glm-4.5": {"input": 0.0000005, "output": 0.0000005, "ctx": 128000},
                }
                for _glm, _ginfo in _glm_models.items():
                    if _glm not in pricing:
                        pricing[_glm] = {
                            "input_cost_per_token": _ginfo["input"],
                            "output_cost_per_token": _ginfo["output"],
                            "max_tokens": _ginfo["ctx"],
                            "litellm_provider": "glm",
                            "mode": "chat",
                            "source": "estimated",
                            "supports_cache": False,
                        }

                # Kimi K2 (Moonshot AI) fallback if not in LiteLLM yet
                _kimi_models = {
                    "kimi-k2.6": {"input": 0.000001, "output": 0.000003, "ctx": 256000},
                    "kimi-k2-thinking": {"input": 0.000001, "output": 0.000003, "ctx": 256000},
                    "kimi-k2": {"input": 0.0000007, "output": 0.0000025, "ctx": 128000},
                    "kimi-k3": {"input": 0.0000029, "output": 0.000014, "ctx": 1000000},
                }
                for _kimi, _kinfo in _kimi_models.items():
                    if _kimi not in pricing:
                        pricing[_kimi] = {
                            "input_cost_per_token": _kinfo["input"],
                            "output_cost_per_token": _kinfo["output"],
                            "max_tokens": _kinfo["ctx"],
                            "litellm_provider": "moonshot",
                            "mode": "chat",
                            "source": "estimated",
                            "supports_cache": True,
                        }

                # LUX Computer Use fallback (proprietary model, not in LiteLLM)
                if "lux-1.0" not in pricing:
                    pricing["lux-1.0"] = {
                        "input_cost_per_token": 0.000003,
                        "output_cost_per_token": 0.000015,
                        "max_tokens": 200000,
                        "litellm_provider": "lux",
                        "mode": "chat",
                        "source": "estimated",
                        "supports_cache": False,
                    }

                logger.info(f"Fetched {len(pricing)} model prices from LiteLLM")
                return pricing

        except Exception as e:
            logger.error(f"Failed to fetch LiteLLM pricing: {e}")
            return {}
    
    async def fetch_openrouter_pricing(self) -> Dict[str, Any]:
        """Fetch pricing from OpenRouter API"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(OPENROUTER_MODELS_URL)
                response.raise_for_status()
                data = response.json()
                
                pricing = {}
                for model in data.get("data", []):
                    model_id = model.get("id", "")
                    model_pricing = model.get("pricing", {})
                    # Preserve the catalog row; omit only an invalid/missing
                    # monetary rate so the charge stays unknown.
                    _rates = {}
                    for _rk, _src in (("input_cost_per_token", "prompt"),
                                      ("output_cost_per_token", "completion")):
                        _rv = model_pricing.get(_src)
                        if _rv is None:
                            continue
                        if self.rate_is_valid(_rv):
                            _rates[_rk] = float(_rv)
                    pricing[model_id] = {
                        **_rates,
                        "max_tokens": model.get("context_length", 0),
                        "name": model.get("name", model_id),
                        "description": model.get("description", ""),
                        "source": "openrouter",
                        # Phase M freshness fields (measurement only)
                        "expiration_date": model.get("expiration_date"),
                        "created": model.get("created"),
                        # Critical: set litellm_provider so the BPC ranker can
                        # route these models to the openrouter client. Without
                        # this, the substring match in byok_handler.get_ranked_providers
                        # can't join OpenRouter models to a provider client.
                        "litellm_provider": "openrouter",
                    }
                
                # Apply curated overrides in pricing shape
                from core.llm.registry.curated_overrides import (
                    apply_curated_overrides_to_pricing,
                )
                pricing = apply_curated_overrides_to_pricing(pricing)

                logger.info(f"Fetched {len(pricing)} model prices from OpenRouter (incl. curated overrides)")
                return pricing
                
        except Exception as e:
            logger.error(f"Failed to fetch OpenRouter pricing: {e}")
            return {}

    def _opencode_pricing_entry(
        self,
        model_id: str,
        input_per_1m: float,
        output_per_1m: float,
        max_input_tokens: Optional[int] = None,
        name: Optional[str] = None,
        supports_cache: bool = False,
    ) -> Dict[str, Any]:
        """Build one pricing-cache entry for an OpenCode Zen model."""
        # Lazy import: a module-level ``core.llm`` import here created an
        # import cycle (fetcher -> core.llm/__init__ -> byok_handler ->
        # fetcher), the same reason ``curated_overrides`` is imported lazily.
        from core.llm.opencode_catalog import OPCODE_GATEWAY_MAX_CONTEXT

        return {
            "input_cost_per_token": float(input_per_1m) / 1_000_000,
            "output_cost_per_token": float(output_per_1m) / 1_000_000,
            "max_input_tokens": int(max_input_tokens or OPCODE_GATEWAY_MAX_CONTEXT),
            "name": name or model_id,
            "source": "opencode-zen",
            # Critical: tag with the opencode-go provider so BPC joins these
            # models to the opencode-go client (same pattern as OpenRouter).
            "litellm_provider": "opencode-go",
            "supports_cache": bool(supports_cache),
        }

    def _opencode_static_fallback(self) -> Dict[str, Any]:
        """Table-driven OpenCode Zen catalog used when the live endpoint is
        unreachable (or yields nothing priceable).

        Prices come from the shared ``OPCODE_KNOWN_PRICES`` table
        (https://opencode.ai/docs/zen, refreshed 2026-10-15) because the live
        models endpoint returns IDs only. Models are keyed by their bare
        gateway IDs and tagged with the opencode-go provider so the BPC ranker
        routes them to the opencode-go client.
        """
        from core.llm.opencode_catalog import OPCODE_KNOWN_PRICES

        return {
            model_id: self._opencode_pricing_entry(model_id, inp, out)
            for model_id, (inp, out) in OPCODE_KNOWN_PRICES.items()
        }

    async def fetch_opencode_pricing(self) -> Dict[str, Any]:
        """Fetch the OpenCode Zen model catalog (OpenCode Go gateway) and merge
        it with the known-price table.

        The live endpoint returns model IDs only — no prices, no context. Live
        IDs decide *what exists* (delisted models drop out automatically); the
        shared ``OPCODE_KNOWN_PRICES`` table decides *what each model costs*.
        A served-but-unpriced ID is dropped with a log line rather than being
        mispriced as $0 (the bug this merge fixes: every cached Zen entry
        carried a $0 price because the endpoint never sent cost fields).

        Falls back to the full table when the endpoint is unreachable or
        returns no live IDs, so routing never loses opencode-go candidates.
        Entries carry ``litellm_provider: "opencode-go"`` for BPC join, and the
        provider's custom RPM/TPM/context limits are applied at routing time by
        ``core.llm.provider_rate_limits``.
        """
        from core.llm.opencode_catalog import (
            OPCODE_KNOWN_FREE_MODELS,
            OPCODE_KNOWN_PRICES,
        )

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(OPENCODE_MODELS_URL)
                response.raise_for_status()
                data = response.json()

            # The endpoint returns a model list; accept both a bare list and
            # {data: [...]} envelope for forward-compat.
            models = data.get("data", data) if isinstance(data, dict) else data
            live: Dict[str, Any] = {}
            if isinstance(models, list):
                for model in models:
                    if isinstance(model, str):
                        live.setdefault(model, {})
                        continue
                    if not isinstance(model, dict):
                        continue
                    model_id = model.get("id", "") or model.get("model", "")
                    if model_id:
                        live[model_id] = model
        except Exception as e:
            logger.debug(f"Failed to fetch OpenCode Zen pricing (using static fallback): {e}")
            return self._opencode_static_fallback()

        pricing: Dict[str, Any] = {}
        unpriced: List[str] = []
        for model_id, raw in live.items():
            # Free/stealth models are deliberately unpriced (BPC must not rank
            # a $0 model a direct API key usually cannot call).
            if model_id in OPCODE_KNOWN_FREE_MODELS or model_id.endswith("-free"):
                continue
            known = OPCODE_KNOWN_PRICES.get(model_id)
            if known is not None:
                pricing[model_id] = self._opencode_pricing_entry(
                    model_id, known[0], known[1],
                    name=raw.get("name"),
                    supports_cache=bool(raw.get("supports_cache", False)),
                )
                continue
            # Forward-compat: if the gateway ever starts serving prices for an
            # ID the table does not know, prefer the live numbers over dropping
            # it. Zero/absent values still mean "unpriced" — not "free".
            live_in = raw.get("input_cost", raw.get("prompt"))
            live_out = raw.get("output_cost", raw.get("completion"))
            try:
                live_in_f = float(live_in) if live_in is not None else 0.0
                live_out_f = float(live_out) if live_out is not None else 0.0
            except (TypeError, ValueError):
                live_in_f = live_out_f = 0.0
            if live_in_f > 0 or live_out_f > 0:
                pricing[model_id] = self._opencode_pricing_entry(
                    model_id, live_in_f, live_out_f,
                    max_input_tokens=raw.get("context_length", raw.get("context")),
                    name=raw.get("name"),
                    supports_cache=bool(raw.get("supports_cache", False)),
                )
            else:
                unpriced.append(model_id)

        if unpriced:
            shown = ", ".join(sorted(unpriced)[:10])
            more = f" (+{len(unpriced) - 10} more)" if len(unpriced) > 10 else ""
            logger.info(
                f"OpenCode Zen serves {len(unpriced)} model(s) missing from "
                f"OPCODE_KNOWN_PRICES — dropped until priced: {shown}{more}"
            )
        if pricing:
            logger.info(
                f"Fetched {len(pricing)} OpenCode Zen model prices "
                f"({len(live)} served; table-merged)"
            )
            return pricing
        logger.warning("OpenCode Zen endpoint returned no priced models; using static fallback")
        return self._opencode_static_fallback()
    
    async def refresh_pricing(self, force: bool = False) -> Dict[str, Any]:
        """
        Refresh pricing data from all sources.
        Uses cache if valid unless force=True.
        """
        if not force and self._is_cache_valid():
            logger.info("Using cached pricing data")
            return self.pricing_cache

        # Fetch from all sources
        previous_cache = dict(self.pricing_cache)
        litellm_pricing = await self.fetch_litellm_pricing()
        openrouter_pricing = await self.fetch_openrouter_pricing()
        opencode_pricing = await self.fetch_opencode_pricing()

        # Merge pricing (LiteLLM takes precedence)
        self.pricing_cache = {**opencode_pricing, **openrouter_pricing, **litellm_pricing}

        # Infer capabilities for all models (run once at fetch time)
        logger.info("Inferring capabilities for all models...")
        capabilities = self._infer_capabilities(self.pricing_cache)

        # Merge capabilities into pricing cache
        for model_name, caps in capabilities.items():
            if model_name in self.pricing_cache and caps:
                self.pricing_cache[model_name].update(caps)

        self.last_fetch = datetime.now()

        # Phase M: per-refresh staleness diff (openrouter slice only). The
        # first sample records the cold-boot baseline; never raises into the
        # refresh path.
        try:
            self._record_staleness_stats(
                compute_staleness_stats(previous_cache, self.pricing_cache)
            )
        except Exception as e:
            logger.debug(f"Staleness accounting skipped: {e}")

        # Save to cache
        self._save_cache()

        return self.pricing_cache

    def _or_entry(self, model_id: str) -> Dict[str, Any]:
        """Canonical minimal openrouter-sourced pricing entry (tests/tools)."""
        return {
            "source": "openrouter",
            "litellm_provider": "openrouter",
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
            "max_tokens": 0,
            "name": model_id,
        }

    def _record_staleness_stats(self, stats: Dict[str, Any]) -> None:
        """Append to in-memory history + rolling JSON file (last N samples)."""
        self.staleness_history.append(stats)
        del self.staleness_history[:-STALENESS_HISTORY_CAP]
        if stats.get("expired_served"):
            logger.warning(
                f"Pricing cache serving {len(stats['expired_served'])} expired "
                f"openrouter models: {stats['expired_served'][:5]}"
            )
        try:
            STALENESS_STATS_PATH.parent.mkdir(exist_ok=True)
            with open(STALENESS_STATS_PATH, "w") as f:
                json.dump({"history": self.staleness_history}, f, indent=2)
        except Exception as e:
            logger.debug(f"Could not persist staleness stats: {e}")

    def record_stale_consideration(self, model_id: str) -> None:
        """BPC hook: candidate considered whose expiration_date has passed.

        Measurement only — never influences ranking (an expired date means
        "may be removed", not "is removed").
        """
        self.bpc_stale_seen[model_id] = self.bpc_stale_seen.get(model_id, 0) + 1

    def staleness_summary(self) -> Dict[str, Any]:
        """Aggregate view for the /api/ai/pricing/staleness-stats route."""
        currently_expired = sorted({
            mid for mid, entry in self.pricing_cache.items()
            if isinstance(entry, dict)
            and entry.get("source") == "openrouter"
            and is_expiration_past(entry.get("expiration_date"))
        })
        return {
            "refresh_samples": len(self.staleness_history),
            "latest": self.staleness_history[-1] if self.staleness_history else None,
            "added_total": sum(len(s.get("added", [])) for s in self.staleness_history),
            "removed_total": sum(len(s.get("removed", [])) for s in self.staleness_history),
            "expired_models_currently_cached": currently_expired,
            "bpc_stale_considerations": dict(self.bpc_stale_seen),
        }
    
    def get_model_price(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get pricing for a specific model"""
        # Try exact match first
        if model_name in self.pricing_cache:
            return self.pricing_cache[model_name]

        # Try case-insensitive exact match (some providers vary casing)
        model_lower = model_name.lower()
        for cached_model, pricing in self.pricing_cache.items():
            if cached_model.lower() == model_lower:
                return pricing

        # No match found. Previously a loose bidirectional substring match
        # returned the first key containing the query — e.g. "gpt-4-mini"
        # matched "gpt-4o", returning the wrong (6x cheaper) price and
        # corrupting cost attribution. Return None for unknown models (BUG-041).
        return None
    
    def get_provider_models(self, provider: str) -> List[Dict[str, Any]]:
        """Get all models for a specific provider"""
        models = []
        provider_lower = provider.lower()
        
        for model_name, pricing in self.pricing_cache.items():
            litellm_provider = pricing.get("litellm_provider", "").lower()
            if provider_lower in model_name.lower() or provider_lower in litellm_provider:
                models.append({
                    "model": model_name,
                    **pricing
                })
        
        # Sort by input cost
        models.sort(key=lambda x: x.get("input_cost_per_token", float("inf")))
        return models
    
    def get_cheapest_models(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the cheapest models across all providers.

        Only rows with a COMPLETE valid rate pair participate; a row whose
        monetary price is unknown is not ranked as if it were free.
        """
        models = []
        
        for model_name, pricing in self.pricing_cache.items():
            rates = self.material_rates(pricing)
            if rates is None:
                continue
            input_cost, output_cost = rates
            
            # Skip models with zero cost (usually local/self-hosted)
            if input_cost > 0 or output_cost > 0:
                models.append({
                    "model": model_name,
                    "avg_cost": (input_cost + output_cost) / 2,
                    **pricing
                })
        
        models.sort(key=lambda x: x.get("avg_cost", float("inf")))
        return models[:limit]
    
    def compare_providers(self) -> Dict[str, Dict[str, Any]]:
        """Compare average costs across providers"""
        provider_costs: Dict[str, List[float]] = {}
        
        for model_name, pricing in self.pricing_cache.items():
            provider = pricing.get("litellm_provider", "unknown")
            if not provider:
                # Try to extract from model name
                if "gpt" in model_name.lower() or "openai" in model_name.lower():
                    provider = "openai"
                elif "claude" in model_name.lower() or "anthropic" in model_name.lower():
                    provider = "anthropic"
                elif "deepseek" in model_name.lower():
                    provider = "deepseek"
                elif "gemini" in model_name.lower():
                    provider = "google"
                else:
                    provider = "other"
            
            rates = self.material_rates(pricing)
            if rates is None:
                continue
            input_cost, output_cost = rates
            
            if input_cost > 0:
                if provider not in provider_costs:
                    provider_costs[provider] = []
                provider_costs[provider].append((input_cost + output_cost) / 2)
        
        # Calculate averages and ranges
        comparison = {}
        for provider, costs in provider_costs.items():
            if costs:
                comparison[provider] = {
                    "avg_cost_per_token": sum(costs) / len(costs),
                    "min_cost_per_token": min(costs),
                    "max_cost_per_token": max(costs),
                    "model_count": len(costs)
                }
        
        return comparison
    
    @staticmethod
    def rate_is_valid(value: Any) -> bool:
        """A monetary rate is material only when explicit, finite, >= 0, non-bool."""
        if value is None or isinstance(value, bool):
            return False
        try:
            rate = float(value)
        except (TypeError, ValueError):
            return False
        return math.isfinite(rate) and rate >= 0

    @classmethod
    def material_rates(cls, pricing: Any) -> Optional[tuple]:
        """``(input_rate, output_rate)`` only when BOTH are explicit material.

        Used by consumers that need a complete price pair for ranking/display
        (cache router, provider-cost sync). Absence is unknown, never 0.
        """
        if not isinstance(pricing, dict):
            return None
        values = []
        for key in ("input_cost_per_token", "output_cost_per_token"):
            value = pricing.get(key)
            if not cls.rate_is_valid(value):
                return None
            values.append(float(value))
        return values[0], values[1]

    @classmethod
    def rates_are_material(cls, pricing: Any) -> bool:
        """True only when BOTH rates are explicit valid numbers."""
        return cls.material_rates(pricing) is not None

    def estimate_cost(self, model_name: str, input_tokens: int, output_tokens: int) -> Optional[float]:
        """Quantity-aware configured cost, or ``None`` when not chargeable.

        Contract:
        * every PROVIDED rate must be explicit, finite, non-negative, non-bool;
        * a rate is REQUIRED only for a dimension with positive quantity (a
          chat reservation has positive input and output cap, so both are
          required there);
        * an ABSENT rate for a zero-quantity dimension is genuinely unused
          basis, not a reason to invent a 0 output price — legitimate
          input-only (e.g. embedding) charges keep their known input cost;
        * explicit 0 rates are authoritative free; absence is never free.
        """
        if isinstance(input_tokens, bool) or isinstance(output_tokens, bool):
            return None
        try:
            in_qty = int(input_tokens or 0)
            out_qty = int(output_tokens or 0)
        except (TypeError, ValueError):
            return None
        if in_qty < 0 or out_qty < 0:
            return None
        pricing = self.get_model_price(model_name)
        if not isinstance(pricing, dict):
            return None
        total = 0.0
        for key, qty in (("input_cost_per_token", in_qty),
                         ("output_cost_per_token", out_qty)):
            value = pricing.get(key)
            if value is not None:
                # Validate every PROVIDED rate, even for a zero quantity.
                if not self.rate_is_valid(value):
                    return None
                total += float(value) * qty
            elif qty > 0:
                # A positive charge needs this dimension's price.
                return None
            # qty == 0 and absent: unused basis, contributes exactly 0.
        if not math.isfinite(total) or total < 0:
            return None
        return total

    @classmethod
    def audio_rate_per_second(cls, pricing: Any) -> Optional[float]:
        """Configured USD/second for an audio model, or ``None``.

        Accepts the LiteLLM audio field (``input_cost_per_second``) and a
        per-minute spelling when a catalog publishes that instead. A provided
        rate must be explicit, finite, non-negative and non-bool; an explicit
        zero stays authoritative free, while absence remains unknown.
        """
        if not isinstance(pricing, dict):
            return None
        for key in ("input_cost_per_second", "audio_cost_per_second"):
            value = pricing.get(key)
            if value is None:
                continue
            if not cls.rate_is_valid(value):
                return None
            return float(value)
        for key in ("input_cost_per_minute", "audio_cost_per_minute"):
            value = pricing.get(key)
            if value is None:
                continue
            if not cls.rate_is_valid(value):
                return None
            return float(value) / 60.0
        return None

    def estimate_audio_cost(
        self, model_name: str, audio_seconds: Any,
    ) -> Optional[float]:
        """Quantity-aware configured cost for TIME-billed audio.

        ``audio_seconds`` is the real media duration (not bytes and not a
        token count). Missing duration/price is explicit unknown; an explicit
        zero rate is authoritative free. This is the audio analogue of
        :meth:`estimate_cost`, living on the same model-price catalog.
        """
        if isinstance(audio_seconds, bool):
            return None
        try:
            seconds = float(audio_seconds)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(seconds) or seconds < 0:
            return None
        pricing = self.get_model_price(model_name)
        if not isinstance(pricing, dict):
            return None
        rate = self.audio_rate_per_second(pricing)
        if rate is None:
            return None
        total = rate * seconds
        if not math.isfinite(total) or total < 0:
            return None
        return total

    def model_supports_cache(self, model_name: str) -> bool:
        """
        Check if a model supports prompt caching.

        Uses the supports_cache field from pricing data if available.
        Falls back to provider-based inference for known caching providers.

        Args:
            model_name: Model identifier (e.g., "gpt-4o", "claude-3-5-sonnet")

        Returns:
            True if model supports caching, False otherwise

        Examples:
            >>> fetcher.model_supports_cache("gpt-4o")
            True
            >>> fetcher.model_supports_cache("deepseek-chat")
            False
        """
        pricing = self.get_model_price(model_name)
        if pricing:
            # Use explicit supports_cache field if available
            if "supports_cache" in pricing:
                return pricing["supports_cache"]

        # Fallback: Infer from provider
        provider = self._infer_provider(model_name)
        return provider in ["openai", "anthropic", "google"]

    def _infer_provider(self, model_name: str) -> str:
        """
        Infer provider from model name.

        Args:
            model_name: Model identifier

        Returns:
            Provider name (lowercase)
        """
        model_lower = model_name.lower()

        if "gpt" in model_lower or "openai" in model_lower:
            return "openai"
        elif "claude" in model_lower or "anthropic" in model_lower:
            return "anthropic"
        elif "deepseek" in model_lower:
            return "deepseek"
        elif "gemini" in model_lower or "google" in model_lower:
            return "google"
        elif "minimax" in model_lower:
            return "minimax"
        elif "glm" in model_lower:
            return "glm"
        elif "kimi" in model_lower or "moonshot" in model_lower:
            return "moonshot"
        elif "mistral" in model_lower:
            return "mistral"
        elif "groq" in model_lower:
            return "groq"  # Only classify as Groq if the model name contains "groq"
        elif "llama" in model_lower:
            return "meta"  # Generic Llama models are from Meta (served by many providers)
        elif "lux" in model_lower:
            return "lux"
        else:
            return "unknown"

    def infer_capabilities_for_model(self, model_name: str, metadata: Dict[str, Any]) -> Dict[str, bool]:
        """Infer capabilities for ONE model from its metadata + name.

        Read-time fallback for cache entries that were merged WITHOUT
        capability annotations (e.g. OpenRouter payloads for dated flagship
        variants): without this, get_model_capabilities classified any
        annotation-less entry as conservatively tool-incapable, which zeroed
        out agentic routing for exactly the flagship models.

        Infers three capabilities:
        - supports_tools: Can the model use function calling/tools?
        - supports_vision: Can the model process images?
        - supports_reasoning: Is this a reasoning model (o3, R1, etc.)?

        Inference is based on:
        1. Model mode field (if available)
        2. Model name patterns (provider-specific keywords)
        3. Provider behavior
        """
        model_lower = model_name.lower()

        # Get mode from metadata, default to "chat"
        mode = metadata.get("mode", "chat").lower()

        # Infer supports_tools
        # Reasoning models and small models don't support tools
        if any(k in model_lower for k in ("gpt-6",)):
            # GPT-6 flagships (gpt-6-astra) are reasoning-first yet fully
            # tool-capable (agentic). The mode=="reasoning" branch below
            # would wrongly zero their supports_tools and lock them out of
            # every requires_tools route (agentic, computer_use) before the
            # frontier gate ever got a chance to admit them.
            supports_tools = True
        elif mode == "reasoning":
            supports_tools = False
        elif "speciale" in model_lower:
            supports_tools = False
        else:
            # Most models support tools — including the small/cheap tiers
            # (gpt-4o-mini, claude-haiku): the earlier "haiku/mini/tiny ->
            # False" keyword rule wrongly demoted flagship-cheap models and,
            # combined with the conservative unknown-model default, zeroed
            # out agentic (tools-required) routing entirely.
            supports_tools = True

        # Infer supports_vision
        # Vision mode, or specific model capabilities
        if mode == "vision":
            supports_vision = True
        elif any(keyword in model_lower for keyword in ["vision", "vl", "multimodal"]):
            supports_vision = True
        elif any(keyword in model_lower for keyword in ["gpt-4o", "gpt-6", "gemini-2.5", "gemini-2-flash", "gemini-3-flash", "gemini-3.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"]):
            supports_vision = True
        elif any(keyword in model_lower for keyword in ["claude-3.5-sonnet", "claude-3-opus", "claude-mythos", "claude-fable"]):
            supports_vision = True
        elif "kimi-k3" in model_lower or "gpt-5.6" in model_lower:
            supports_vision = True
        else:
            supports_vision = False

        # Infer supports_reasoning
        # Specific model families indicate reasoning capability
        if mode == "reasoning":
            supports_reasoning = True
        elif any(keyword in model_lower for keyword in ["o3", "o1", "-reasoner", "-thinking", "r1"]):
            supports_reasoning = True
        elif "speciale" in model_lower:
            supports_reasoning = True
        else:
            supports_reasoning = False

        # NOTE: this return must sit at method level. It used to be indented
        # inside the else-branch above, so any mode=="reasoning" model made
        # this function return None — and refresh_pricing then crashed on
        # caps.update(None), aborting the whole pricing refresh before the
        # OpenRouter catalog could be saved. The cache froze on its last
        # good state and BPC value-ranking silently lost all candidates.
        return {
            "supports_tools": supports_tools,
            "supports_vision": supports_vision,
            "supports_reasoning": supports_reasoning,
        }

    def _infer_capabilities(self, model_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, bool]]:
        """Batch wrapper over :meth:`infer_capabilities_for_model`."""
        return {
            model_name: self.infer_capabilities_for_model(model_name, metadata)
            for model_name, metadata in model_data.items()
        }

    def get_model_capabilities(self, model_name: str) -> Dict[str, bool]:
        """
        Get model capabilities from pricing cache.

        Args:
            model_name: Model identifier

        Returns:
            Dict with supports_tools, supports_vision, supports_reasoning
            Returns default (False for all) if model not in cache
        """
        model_data = self.pricing_cache.get(model_name)

        # Entry present WITH annotations: return them. A None value (upstream
        # data sources return null for "unknown") must fall back to the
        # default — a raw None leaks out as a falsy "not supported" in bool()
        # contexts and silently demotes tool-capable models.
        if model_data is not None and "supports_tools" in model_data:
            st = model_data.get("supports_tools")
            sv = model_data.get("supports_vision")
            sr = model_data.get("supports_reasoning")
            return {
                "supports_tools": True if st is None else bool(st),
                "supports_vision": False if sv is None else bool(sv),
                "supports_reasoning": False if sr is None else bool(sr),
            }

        # Entry present but WITHOUT annotations: infer from the name/mode —
        # these are known models, not unknown ones.
        if model_data is not None:
            return self.infer_capabilities_for_model(model_name, model_data)

        # Truly unknown model (absent from cache). Availability-first:
        # defaulting tools to False here barred EVERY model that postdated the
        # local cache snapshot from agentic routing — with a small/stale cache
        # that meant a total agent outage ("No eligible LLM providers") even
        # though unknown in practice overwhelmingly means a modern tool-capable
        # model. Per-model failures are recoverable via the provider cascade;
        # a zero-option ranking is not. Vision/reasoning stay conservative.
        return {
            "supports_tools": True,
            "supports_vision": False,
            "supports_reasoning": False,
        }

    def get_cache_min_tokens(self, model_name: str) -> int:
        """
        Get minimum token threshold for prompt caching.

        Returns the minimum prompt length required for caching to be applied.
        Returns 0 if the model doesn't support caching.

        Args:
            model_name: Model identifier

        Returns:
            Minimum token count (1024 for OpenAI/Gemini, 2048 for Anthropic, 0 for no cache)

        Examples:
            >>> fetcher.get_cache_min_tokens("gpt-4o")
            1024
            >>> fetcher.get_cache_min_tokens("claude-3-5-sonnet")
            2048
            >>> fetcher.get_cache_min_tokens("deepseek-chat")
            0
        """
        if not self.model_supports_cache(model_name):
            return 0

        provider = self._infer_provider(model_name)

        # Research-verified minimum token thresholds
        if provider == "openai":
            return 1024
        elif provider == "anthropic":
            return 2048
        elif provider == "google":
            return 1024
        else:
            return 0

    def is_pricing_estimated(self, model_name: str) -> bool:
        """
        Check if pricing for a model is estimated (not from official source).

        Useful for UI disclaimers and cost estimation warnings.

        Args:
            model_name: Model identifier

        Returns:
            True if pricing is estimated, False if from official source

        Examples:
            >>> fetcher.is_pricing_estimated("MiniMax-M3")
            True  # Estimated until official pricing announced
            >>> fetcher.is_pricing_estimated("gpt-4o")
            False  # Official from LiteLLM
        """
        pricing = self.get_model_price(model_name)
        if pricing:
            return pricing.get("source") == "estimated"
        return False


# Singleton instance
_pricing_fetcher: Optional[DynamicPricingFetcher] = None
_pricing_initialized = False


def get_pricing_fetcher() -> DynamicPricingFetcher:
    """Get the singleton pricing fetcher instance"""
    global _pricing_fetcher
    if _pricing_fetcher is None:
        _pricing_fetcher = DynamicPricingFetcher()
    return _pricing_fetcher


async def get_pricing_fetcher_initialized(
    auto_refresh: bool = True,
    force_refresh: bool = False
) -> DynamicPricingFetcher:
    """
    Get pricing fetcher with lazy async initialization.

    Ensures pricing cache is populated on first use by fetching from
    LiteLLM and OpenRouter APIs. Subsequent calls use cached data.

    Args:
        auto_refresh: If True, automatically refresh cache if empty
        force_refresh: If True, force refresh even if cache exists

    Returns:
        Initialized DynamicPricingFetcher instance

    Example:
        >>> fetcher = await get_pricing_fetcher_initialized()
        >>> # Cache is now populated with latest pricing and capabilities
    """
    global _pricing_fetcher, _pricing_initialized

    fetcher = get_pricing_fetcher()

    # Check if we need to initialize
    needs_init = (
        not _pricing_initialized or
        force_refresh or
        (auto_refresh and not fetcher.pricing_cache)
    )

    if needs_init:
        logger.info("Auto-populating pricing cache from LiteLLM and OpenRouter...")
        await fetcher.refresh_pricing(force=force_refresh)
        _pricing_initialized = True
        logger.info(f"Pricing cache populated with {len(fetcher.pricing_cache)} models")

    return fetcher


def get_pricing_fetcher_initialized_sync(
    auto_refresh: bool = True,
    force_refresh: bool = False
) -> DynamicPricingFetcher:
    """Get pricing fetcher with lazy synchronous initialization."""
    global _pricing_fetcher, _pricing_initialized

    fetcher = get_pricing_fetcher()

    needs_init = (
        not _pricing_initialized or
        force_refresh or
        (auto_refresh and not fetcher.pricing_cache)
    )

    if needs_init:
        logger.info("Auto-populating pricing cache synchronously...")
        import asyncio
        import concurrent.futures
        try:
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                executor.submit(lambda: asyncio.run(fetcher.refresh_pricing(force=force_refresh))).result()
        except RuntimeError:
            asyncio.run(fetcher.refresh_pricing(force=force_refresh))
        _pricing_initialized = True
        logger.info(f"Pricing cache populated with {len(fetcher.pricing_cache)} models")

    return fetcher



async def refresh_pricing_cache(force: bool = False) -> Dict[str, Any]:
    """Convenience function to refresh pricing cache"""
    fetcher = get_pricing_fetcher()
    return await fetcher.refresh_pricing(force=force)
