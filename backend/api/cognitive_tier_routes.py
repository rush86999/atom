"""
Cognitive Tier Management API Routes

Provides REST endpoints for managing cognitive tier preferences:
- Get/Set workspace tier preferences
- Cost estimation per tier
- Tier comparison (quality vs cost)
- Budget management

Author: Atom AI Platform
Created: 2026-02-20
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import CognitiveTierPreference
from core.llm.cognitive_tier_system import CognitiveTier, CognitiveClassifier
from core.dynamic_pricing_fetcher import get_pricing_fetcher

logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================

class TierPreferenceRequest(BaseModel):
    """Request to create or update tier preference"""
    default_tier: str = "standard"  # micro, standard, versatile, heavy, complex
    min_tier: Optional[str] = None
    max_tier: Optional[str] = None
    monthly_budget_cents: Optional[int] = None
    max_cost_per_request_cents: Optional[int] = None
    enable_cache_aware_routing: bool = True
    enable_auto_escalation: bool = True
    enable_minimax_fallback: bool = True
    preferred_providers: List[str] = []


class TierPreferenceResponse(BaseModel):
    """Response with tier preference details"""
    id: str
    workspace_id: str
    default_tier: str
    min_tier: Optional[str]
    max_tier: Optional[str]
    monthly_budget_cents: Optional[int]
    max_cost_per_request_cents: Optional[int]
    enable_cache_aware_routing: bool
    enable_auto_escalation: bool
    enable_minimax_fallback: bool
    preferred_providers: List[str]
    metadata_json: Optional[Dict[str, Any]]
    created_at: str
    updated_at: Optional[str]


class BudgetUpdateRequest(BaseModel):
    """Request to update budget settings"""
    monthly_budget_cents: Optional[int] = None
    max_cost_per_request_cents: Optional[int] = None


class CostEstimateRequest(BaseModel):
    """Request for cost estimation"""
    prompt: Optional[str] = None
    estimated_tokens: Optional[int] = None
    tier: Optional[str] = None


class TierCostEstimate(BaseModel):
    """Cost estimate for a specific tier"""
    tier: str
    estimated_cost_usd: float
    models_in_tier: List[str]
    cache_aware_available: bool


class CostEstimateResponse(BaseModel):
    """Response with cost estimates for all tiers"""
    estimates: List[TierCostEstimate]
    recommended_tier: str
    prompt_used: Optional[str]
    estimated_tokens: int


class TierComparison(BaseModel):
    """Comparison data for a single tier"""
    tier: str
    description: str
    quality_range: str  # e.g., "80-85"
    cost_range_usd: str  # e.g., "$0.0001 - $0.001"
    example_models: List[str]
    cache_aware_support: bool


class TierComparisonResponse(BaseModel):
    """Response with tier comparison table"""
    tiers: List[TierComparison]
    total_tiers: int


# ============================================================================
# Router
# ============================================================================

router = BaseAPIRouter(
    prefix="/api/v1/cognitive-tier",
    tags=["Cognitive Tier Management"]
)

# Cognitive classifier instance
_classifier = CognitiveClassifier()


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "/preferences/{workspace_id}",
    response_model=TierPreferenceResponse,
    summary="Get workspace tier preferences",
    description="Returns the workspace's cognitive tier preference or defaults if not set."
)
def get_preferences(
    workspace_id: str,
    db: Session = Depends(get_db)
) -> TierPreferenceResponse:
    """
    Get tier preferences for a workspace.

    Args:
        workspace_id: The workspace ID
        db: Database session

    Returns:
        TierPreferenceResponse with current settings or defaults

    Example:
        GET /api/v1/cognitive-tier/preferences/workspace_123
    """
    preference = db.query(CognitiveTierPreference).filter_by(
        workspace_id=workspace_id
    ).first()

    if not preference:
        # Return default preference
        return TierPreferenceResponse(
            id="",
            workspace_id=workspace_id,
            default_tier="standard",
            min_tier=None,
            max_tier=None,
            monthly_budget_cents=None,
            max_cost_per_request_cents=None,
            enable_cache_aware_routing=True,
            enable_auto_escalation=True,
            enable_minimax_fallback=True,
            preferred_providers=[],
            metadata_json=None,
            created_at="",
            updated_at=None
        )

    return TierPreferenceResponse(
        id=preference.id,
        workspace_id=preference.workspace_id,
        default_tier=preference.default_tier,
        min_tier=preference.min_tier,
        max_tier=preference.max_tier,
        monthly_budget_cents=preference.monthly_budget_cents,
        max_cost_per_request_cents=preference.max_cost_per_request_cents,
        enable_cache_aware_routing=preference.enable_cache_aware_routing,
        enable_auto_escalation=preference.enable_auto_escalation,
        enable_minimax_fallback=preference.enable_minimax_fallback,
        preferred_providers=preference.preferred_providers or [],
        metadata_json=preference.metadata_json,
        created_at=preference.created_at.isoformat() if preference.created_at else "",
        updated_at=preference.updated_at.isoformat() if preference.updated_at else None
    )


@router.post(
    "/preferences/{workspace_id}",
    response_model=TierPreferenceResponse,
    summary="Create or update tier preferences",
    description="Creates a new tier preference or updates an existing one for the workspace."
)
def create_or_update_preferences(
    workspace_id: str,
    request: TierPreferenceRequest,
    db: Session = Depends(get_db)
) -> TierPreferenceResponse:
    """
    Create or update tier preferences for a workspace.

    Args:
        workspace_id: The workspace ID
        request: Tier preference settings
        db: Database session

    Returns:
        Updated TierPreferenceResponse

    Example:
        POST /api/v1/cognitive-tier/preferences/workspace_123
        {
            "default_tier": "standard",
            "monthly_budget_cents": 1000,
            "enable_cache_aware_routing": true
        }
    """
    # Validate tier values
    valid_tiers = [t.value for t in CognitiveTier]
    if request.default_tier not in valid_tiers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid default_tier. Must be one of: {valid_tiers}"
        )

    if request.min_tier and request.min_tier not in valid_tiers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid min_tier. Must be one of: {valid_tiers}"
        )

    if request.max_tier and request.max_tier not in valid_tiers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid max_tier. Must be one of: {valid_tiers}"
        )

    # Validate budget values
    if request.monthly_budget_cents is not None and request.monthly_budget_cents < 0:
        raise HTTPException(
            status_code=400,
            detail="monthly_budget_cents must be non-negative"
        )

    if request.max_cost_per_request_cents is not None and request.max_cost_per_request_cents < 0:
        raise HTTPException(
            status_code=400,
            detail="max_cost_per_request_cents must be non-negative"
        )

    # Check for existing preference
    preference = db.query(CognitiveTierPreference).filter_by(
        workspace_id=workspace_id
    ).first()

    if preference:
        # Update existing
        preference.default_tier = request.default_tier
        preference.min_tier = request.min_tier
        preference.max_tier = request.max_tier
        preference.monthly_budget_cents = request.monthly_budget_cents
        preference.max_cost_per_request_cents = request.max_cost_per_request_cents
        preference.enable_cache_aware_routing = request.enable_cache_aware_routing
        preference.enable_auto_escalation = request.enable_auto_escalation
        preference.enable_minimax_fallback = request.enable_minimax_fallback
        preference.preferred_providers = request.preferred_providers
    else:
        # Create new
        preference = CognitiveTierPreference(
            workspace_id=workspace_id,
            default_tier=request.default_tier,
            min_tier=request.min_tier,
            max_tier=request.max_tier,
            monthly_budget_cents=request.monthly_budget_cents,
            max_cost_per_request_cents=request.max_cost_per_request_cents,
            enable_cache_aware_routing=request.enable_cache_aware_routing,
            enable_auto_escalation=request.enable_auto_escalation,
            enable_minimax_fallback=request.enable_minimax_fallback,
            preferred_providers=request.preferred_providers
        )
        db.add(preference)

    db.commit()
    db.refresh(preference)

    return TierPreferenceResponse(
        id=preference.id,
        workspace_id=preference.workspace_id,
        default_tier=preference.default_tier,
        min_tier=preference.min_tier,
        max_tier=preference.max_tier,
        monthly_budget_cents=preference.monthly_budget_cents,
        max_cost_per_request_cents=preference.max_cost_per_request_cents,
        enable_cache_aware_routing=preference.enable_cache_aware_routing,
        enable_auto_escalation=preference.enable_auto_escalation,
        enable_minimax_fallback=preference.enable_minimax_fallback,
        preferred_providers=preference.preferred_providers or [],
        metadata_json=preference.metadata_json,
        created_at=preference.created_at.isoformat() if preference.created_at else "",
        updated_at=preference.updated_at.isoformat() if preference.updated_at else None
    )


@router.put(
    "/preferences/{workspace_id}/budget",
    response_model=TierPreferenceResponse,
    summary="Update budget settings",
    description="Updates only the budget-related fields for a workspace's tier preference."
)
def update_budget(
    workspace_id: str,
    request: BudgetUpdateRequest,
    db: Session = Depends(get_db)
) -> TierPreferenceResponse:
    """
    Update budget settings for a workspace.

    Args:
        workspace_id: The workspace ID
        request: Budget update request
        db: Database session

    Returns:
        Updated TierPreferenceResponse

    Example:
        PUT /api/v1/cognitive-tier/preferences/workspace_123/budget
        {
            "monthly_budget_cents": 5000,
            "max_cost_per_request_cents": 10
        }
    """
    # Validate budget values
    if request.monthly_budget_cents is not None and request.monthly_budget_cents < 0:
        raise HTTPException(
            status_code=400,
            detail="monthly_budget_cents must be non-negative"
        )

    if request.max_cost_per_request_cents is not None and request.max_cost_per_request_cents < 0:
        raise HTTPException(
            status_code=400,
            detail="max_cost_per_request_cents must be non-negative"
        )

    preference = db.query(CognitiveTierPreference).filter_by(
        workspace_id=workspace_id
    ).first()

    if not preference:
        # Create with defaults
        preference = CognitiveTierPreference(
            workspace_id=workspace_id,
            default_tier="standard"
        )
        db.add(preference)

    if request.monthly_budget_cents is not None:
        preference.monthly_budget_cents = request.monthly_budget_cents

    if request.max_cost_per_request_cents is not None:
        preference.max_cost_per_request_cents = request.max_cost_per_request_cents

    db.commit()
    db.refresh(preference)

    return TierPreferenceResponse(
        id=preference.id,
        workspace_id=preference.workspace_id,
        default_tier=preference.default_tier,
        min_tier=preference.min_tier,
        max_tier=preference.max_tier,
        monthly_budget_cents=preference.monthly_budget_cents,
        max_cost_per_request_cents=preference.max_cost_per_request_cents,
        enable_cache_aware_routing=preference.enable_cache_aware_routing,
        enable_auto_escalation=preference.enable_auto_escalation,
        enable_minimax_fallback=preference.enable_minimax_fallback,
        preferred_providers=preference.preferred_providers or [],
        metadata_json=preference.metadata_json,
        created_at=preference.created_at.isoformat() if preference.created_at else "",
        updated_at=preference.updated_at.isoformat() if preference.updated_at else None
    )


@router.get(
    "/estimate-cost",
    response_model=CostEstimateResponse,
    summary="Estimate cost by tier",
    description="Returns projected costs for all tiers based on prompt or token count."
)
def estimate_cost(
    prompt: Optional[str] = None,
    estimated_tokens: Optional[int] = None,
    tier: Optional[str] = None,
    db: Session = Depends(get_db)
) -> CostEstimateResponse:
    """
    Estimate LLM costs across all cognitive tiers.

    Args:
        prompt: Optional prompt text for auto-token estimation
        estimated_tokens: Direct token count (overrides prompt estimation)
        tier: Optional specific tier to estimate
        db: Database session

    Returns:
        CostEstimateResponse with all tier costs and recommendation

    Example:
        GET /api/v1/cognitive-tier/estimate-cost?prompt=hello%20world&estimated_tokens=10
    """
    # Estimate tokens if not provided
    if estimated_tokens is None and prompt:
        estimated_tokens = len(prompt) // 4  # 1 token ≈ 4 chars

    if estimated_tokens is None:
        estimated_tokens = 100  # Default

    # Get pricing fetcher
    pricing_fetcher = get_pricing_fetcher()

    # Generate estimates for all tiers
    estimates = []
    for cognitive_tier in CognitiveTier:
        if tier and cognitive_tier.value != tier:
            continue

        models = _classifier.get_tier_models(cognitive_tier)

        # Calculate average cost for this tier
        total_cost = 0.0
        model_count = 0
        cache_aware_available = False

        for model_id in models:
            pricing = pricing_fetcher.get_pricing(model_id)
            if pricing:
                input_cost = pricing.get("input_cost_per_token", 0)
                output_cost = pricing.get("output_cost_per_token", 0)
                # Assume 50/50 input/output split
                avg_cost = (input_cost + output_cost) / 2
                total_cost += avg_cost
                model_count += 1

                if pricing.get("supports_cache", False):
                    cache_aware_available = True

        avg_cost = total_cost / model_count if model_count > 0 else 0.0
        estimated_cost = avg_cost * estimated_tokens

        estimates.append(TierCostEstimate(
            tier=cognitive_tier.value,
            estimated_cost_usd=round(estimated_cost, 6),
            models_in_tier=models,
            cache_aware_available=cache_aware_available
        ))

    # Determine recommended tier
    if prompt:
        recommended = _classifier.classify(prompt).value
    else:
        # Default to standard for small requests
        if estimated_tokens < 100:
            recommended = CognitiveTier.MICRO.value
        elif estimated_tokens < 500:
            recommended = CognitiveTier.STANDARD.value
        elif estimated_tokens < 2000:
            recommended = CognitiveTier.VERSATILE.value
        elif estimated_tokens < 5000:
            recommended = CognitiveTier.HEAVY.value
        else:
            recommended = CognitiveTier.COMPLEX.value

    return CostEstimateResponse(
        estimates=estimates,
        recommended_tier=recommended,
        prompt_used=prompt,
        estimated_tokens=estimated_tokens
    )


@router.get(
    "/compare-tiers",
    response_model=TierComparisonResponse,
    summary="Compare all cognitive tiers",
    description="Returns a comparison table showing quality vs cost tradeoffs for all tiers."
)
def compare_tiers(
    db: Session = Depends(get_db)
) -> TierComparisonResponse:
    """
    Compare all cognitive tiers with quality and cost information.

    Args:
        db: Database session

    Returns:
        TierComparisonResponse with comparison data for all tiers

    Example:
        GET /api/v1/cognitive-tier/compare-tiers
    """
    # Get pricing fetcher
    pricing_fetcher = get_pricing_fetcher()

    comparisons = []

    # Quality ranges (MIN_QUALITY_BY_TIER from cognitive_tier_system.py)
    quality_ranges = {
        CognitiveTier.MICRO: "0-80",
        CognitiveTier.STANDARD: "80-86",
        CognitiveTier.VERSATILE: "86-90",
        CognitiveTier.HEAVY: "90-94",
        CognitiveTier.COMPLEX: "94-100"
    }

    for cognitive_tier in CognitiveTier:
        models = _classifier.get_tier_models(cognitive_tier)
        description = _classifier.get_tier_description(cognitive_tier)

        # Calculate cost range for this tier
        costs = []
        cache_aware_support = False

        for model_id in models:
            pricing = pricing_fetcher.get_pricing(model_id)
            if pricing:
                input_cost = pricing.get("input_cost_per_token", 0)
                output_cost = pricing.get("output_cost_per_token", 0)
                avg_cost = (input_cost + output_cost) / 2
                costs.append(avg_cost)

                if pricing.get("supports_cache", False):
                    cache_aware_support = True

        if costs:
            min_cost = min(costs) * 1000  # Per 1k tokens
            max_cost = max(costs) * 1000
            cost_range = f"${min_cost:.6f} - ${max_cost:.6f}"
        else:
            cost_range = "N/A"

        comparisons.append(TierComparison(
            tier=cognitive_tier.value,
            description=description,
            quality_range=quality_ranges[cognitive_tier],
            cost_range_usd=cost_range,
            example_models=models[:3],  # Show first 3 models
            cache_aware_support=cache_aware_support
        ))

    return TierComparisonResponse(
        tiers=comparisons,
        total_tiers=len(comparisons)
    )


@router.delete(
    "/preferences/{workspace_id}",
    summary="Delete tier preferences",
    description="Removes custom tier preferences for a workspace, reverting to defaults."
)
def delete_preferences(
    workspace_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delete tier preferences for a workspace.

    Args:
        workspace_id: The workspace ID
        db: Database session

    Returns:
        Success message

    Example:
        DELETE /api/v1/cognitive-tier/preferences/workspace_123
    """
    preference = db.query(CognitiveTierPreference).filter_by(
        workspace_id=workspace_id
    ).first()

    if preference:
        db.delete(preference)
        db.commit()

    return {
        "success": True,
        "message": "Tier preferences deleted. Workspace will use defaults.",
        "workspace_id": workspace_id
    }


# Singleton function to get pricing fetcher
def get_pricing_fetcher():
    """Get or create the pricing fetcher instance"""
    from core.dynamic_pricing_fetcher import DynamicPricingFetcher
    return DynamicPricingFetcher()
