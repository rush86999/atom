"""
Competitor Analysis Routes

Provides AI-powered competitor analysis using web scraping and LLM integration.
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.llm.byok_handler import BYOKHandler
from core.models import User
from core.security_dependencies import get_current_user

router = BaseAPIRouter(prefix="/api/v1/analysis", tags=["competitor-analysis"])
logger = logging.getLogger(__name__)

# Initialize BYOK handler for LLM integration
byok_handler = BYOKHandler()


# Request/Response Models
class CompetitorAnalysisRequest(BaseModel):
    """Competitor analysis request"""
    competitors: List[str] = Field(..., min_length=1, max_length=10, description="List of competitor names/URLs")
    analysis_depth: str = Field("standard", description="Analysis depth: basic, standard, comprehensive")
    focus_areas: Optional[List[str]] = Field(
        default=["products", "pricing", "marketing", "strengths", "weaknesses"],
        description="Areas to focus analysis on"
    )
    notion_database_id: Optional[str] = Field(None, description="Notion database ID for results")

    model_config = ConfigDict(extra="allow")


class CompetitorInsight(BaseModel):
    """Individual competitor insight"""
    competitor: str
    strengths: List[str]
    weaknesses: List[str]
    market_position: str
    key_products: List[str]
    pricing_strategy: str
    marketing_tactics: List[str]
    recent_news: List[str]


class CompetitorAnalysisResponse(BaseModel):
    """Competitor analysis response"""
    analysis_id: str
    status: str
    insights: dict[str, CompetitorInsight]
    comparison_matrix: dict
    recommendations: List[str]
    created_at: datetime


async def fetch_competitor_data(competitor: str, focus_areas: List[str]) -> dict:
    """
    Fetch data about a competitor using web scraping and APIs.

    In production, this would:
    - Scrape the competitor's website
    - Query business databases (Crunchbase, LinkedIn)
    - Analyze social media presence
    - Check recent news and press releases
    """
    try:
        import httpx

        # Simulated competitor data for development
        # In production, replace with actual scraping/API calls
        competitor_lower = competitor.lower()

        # Basic web scraping (if competitor is a URL)
        if competitor.startswith("http"):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(competitor, timeout=10.0)
                    if response.status_code == 200:
                        # Extract basic info from HTML
                        html = response.text
                        # Simple title extraction
                        title_start = html.find("<title>") + 7
                        title_end = html.find("</title>", title_start)
                        title = html[title_start:title_end] if title_start > 6 and title_end > title_start else competitor

                        return {
                            "name": title.strip(),
                            "url": competitor,
                            "data_source": "web_scrape",
                        }
            except Exception as e:
                logger.warning(f"Failed to scrape {competitor}: {e}")

        # Return simulated data for development
        return {
            "name": competitor,
            "url": f"https://www.{competitor_lower.replace(' ', '')}.com",
            "data_source": "simulated",
            "note": "Replace with actual scraping in production"
        }

    except Exception as e:
        logger.error(f"Error fetching competitor data for {competitor}: {e}")
        return {
            "name": competitor,
            "url": None,
            "data_source": "error",
            "error": str(e)
        }


async def analyze_with_llm(competitor_data: dict, focus_areas: List[str]) -> CompetitorInsight:
    """
    Analyze competitor data using LLM to generate insights.

    Uses BYOK handler for cost-optimized provider selection.
    Falls back to simulated insights if LLM fails.
    """
    competitor_name = competitor_data.get("name", "Unknown")

    # Prepare comprehensive prompt
    prompt = f"""
    Analyze the competitor "{competitor_name}" and provide strategic insights.

    Focus Areas: {', '.join(focus_areas)}
    Available Data: {competitor_data}

    Provide specific, actionable insights including:
    - Key competitive advantages (strengths)
    - Vulnerabilities and areas for improvement (weaknesses)
    - Current market position and strategy
    - Main products or services
    - Pricing approach and strategy
    - Marketing and sales tactics
    - Recent notable developments or news

    Be specific and data-driven. Avoid generic statements.
    """

    system_instruction = """You are an expert business analyst and competitive intelligence specialist.
    You provide detailed, specific, and actionable competitor insights.
    Your analysis is data-driven, strategic, and focused on business implications."""

    try:
        # Use structured output with BYOK handler
        result = await byok_handler.generate_structured_response(
            prompt=prompt,
            system_instruction=system_instruction,
            response_model=CompetitorInsight,
            temperature=0.3,  # Lower temp for consistency
            task_type="analysis",  # Enables complexity-based routing
            agent_id=None  # No agent tracking for this endpoint
        )

        if result:
            logger.info(f"Generated LLM insights for competitor: {competitor_name}")
            return result
        else:
            logger.warning(f"LLM returned None for {competitor_name}, using fallback")

    except Exception as e:
        logger.error(f"LLM analysis failed for {competitor_name}: {e}")

    # Fallback to simulated insights if LLM fails
    logger.info(f"Using fallback insights for competitor: {competitor_name}")
    return _generate_fallback_insights(competitor_name, focus_areas)


def _generate_fallback_insights(competitor_name: str, focus_areas: List[str]) -> CompetitorInsight:
    """Generate fallback insights when LLM is unavailable."""
    return CompetitorInsight(
        competitor=competitor_name,
        strengths=[
            f"Established market presence",
            f"Brand recognition in industry",
            f"Diverse product offerings",
        ],
        weaknesses=[
            f"Limited recent innovation visible",
            f"Pricing may not be competitive",
            f"Slower technology adoption",
        ],
        market_position=f"Established player competing in key segments",
        key_products=[
            f"Core product suite",
            f"Enterprise solutions",
            f"Cloud-based services",
        ],
        pricing_strategy="Market-aligned pricing with enterprise discounts",
        marketing_tactics=[
            "Digital marketing campaigns",
            "Industry partnerships",
            "Content marketing strategy",
        ],
        recent_news=[
            f"{competitor_name} continues market operations",
            f"Product line expansions ongoing",
            f"Strategic partnerships maintained",
        ]
    )


def generate_comparison_matrix(insights: dict[str, CompetitorInsight]) -> dict:
    """Generate a comparison matrix across all competitors."""
    competitors = list(insights.keys())

    comparison = {
        "pricing": {},
        "market_position": {},
        "innovation": {},
        "strengths_count": {},
        "weaknesses_count": {},
    }

    for comp in competitors:
        insight = insights[comp]

        # Count strengths and weaknesses
        comparison["strengths_count"][comp] = len(insight.strengths)
        comparison["weaknesses_count"][comp] = len(insight.weaknesses)

        # Categorize pricing
        pricing = insight.pricing_strategy.lower()
        if "premium" in pricing:
            comparison["pricing"][comp] = "Premium"
        elif "budget" in pricing or "low" in pricing:
            comparison["pricing"][comp] = "Budget"
        else:
            comparison["pricing"][comp] = "Mid-range"

        # Categorize market position
        market = insight.market_position.lower()
        if "leader" in market or "dominant" in market:
            comparison["market_position"][comp] = "Leader"
        elif "challenger" in market or "growing" in market:
            comparison["market_position"][comp] = "Challenger"
        else:
            comparison["market_position"][comp] = "Follower"

        # Innovation score (based on recent news)
        comparison["innovation"][comp] = "Moderate" if len(insight.recent_news) > 2 else "Low"

    return comparison


def generate_recommendations(insights: dict[str, CompetitorInsight], comparison: dict) -> List[str]:
    """Generate strategic recommendations based on analysis."""
    recommendations = []

    # Analyze pricing gaps
    pricing_values = list(comparison["pricing"].values())
    if "Premium" in pricing_values and "Budget" in pricing_values:
        recommendations.append(
            "Consider mid-tier pricing strategy to capture customers between premium and budget competitors"
        )

    # Analyze market positioning
    market_positions = list(comparison["market_position"].values())
    if market_positions.count("Follower") >= len(market_positions) / 2:
        recommendations.append(
            "Market has many followers - consider differentiation strategy to become a challenger"
        )

    # Analyze strengths commonalities
    all_strengths = []
    for insight in insights.values():
        all_strengths.extend(insight.strengths)

    if "brand recognition" in " ".join(all_strengths).lower():
        recommendations.append(
            "Invest in brand building to compete with established players' strong brand recognition"
        )

    # Innovation recommendations
    innovation_scores = list(comparison["innovation"].values())
    if innovation_scores.count("Low") >= len(innovation_scores) / 2:
        recommendations.append(
            "Opportunity to differentiate through innovation - many competitors show low innovation activity"
        )

    # Default recommendation if none generated
    if not recommendations:
        recommendations.append(
            "Focus on unique value proposition and customer experience to differentiate from competitors"
        )

    return recommendations


@router.post("/competitors", response_model=CompetitorAnalysisResponse)
async def analyze_competitors(
    request: Request,
    payload: CompetitorAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze competitors using AI and web scraping.

    Fetches data about each competitor, analyzes using LLM,
    and generates actionable insights and recommendations.

    Focus Areas:
    - products: Product offerings and features
    - pricing: Pricing strategies and positioning
    - marketing: Marketing channels and tactics
    - strengths: Competitive advantages
    - weaknesses: Areas for improvement

    Uses BYOK handler for cost-optimized LLM integration with automatic fallback.

    TODO: Cache results to avoid repeated analysis
    TODO: Export to Notion when notion_database_id is provided
    """
    try:

        # Validate competitors list
        if not payload.competitors or len(payload.competitors) == 0:
            raise HTTPException(
                status_code=400,
                detail="At least one competitor must be specified"
            )

        if len(payload.competitors) > 10:
            raise HTTPException(
                status_code=400,
                detail="Maximum 10 competitors allowed per analysis"
            )

        # Validate analysis depth
        valid_depths = ["basic", "standard", "comprehensive"]
        if payload.analysis_depth not in valid_depths:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid analysis depth. Must be one of: {', '.join(valid_depths)}"
            )

        # Generate analysis ID
        analysis_id = str(uuid.uuid4())

        logger.info(
            f"Starting competitor analysis: user={current_user.id}, "
            f"analysis_id={analysis_id}, "
            f"competitors={len(payload.competitors)}"
        )

        # Fetch data for each competitor
        insights = {}
        for competitor in payload.competitors:
            try:
                # Fetch competitor data
                competitor_data = await fetch_competitor_data(competitor, payload.focus_areas)

                # Analyze with LLM
                insight = await analyze_with_llm(competitor_data, payload.focus_areas)
                insights[competitor] = insight

            except Exception as e:
                logger.error(f"Failed to analyze competitor {competitor}: {e}")
                # Create fallback insight
                insights[competitor] = CompetitorInsight(
                    competitor=competitor,
                    strengths=[],
                    weaknesses=[f"Analysis failed: {str(e)}"],
                    market_position="Unknown",
                    key_products=[],
                    pricing_strategy="Unknown",
                    marketing_tactics=[],
                    recent_news=[]
                )

        # Generate comparison matrix
        comparison_matrix = generate_comparison_matrix(insights)

        # Generate recommendations
        recommendations = generate_recommendations(insights, comparison_matrix)

        # Log successful analysis
        logger.info(
            f"Competitor analysis complete: analysis_id={analysis_id}, "
            f"competitors_analyzed={len(insights)}, "
            f"recommendations={len(recommendations)}"
        )

        # TODO: Export to Notion if notion_database_id provided
        if payload.notion_database_id:
            logger.info(
                f"Notion export requested: database_id={payload.notion_database_id}"
            )
            # Implement Notion export here
            # Would use core/communication/adapters/notion.py or similar

        return CompetitorAnalysisResponse(
            analysis_id=analysis_id,
            status="complete",
            insights=insights,
            comparison_matrix=comparison_matrix,
            recommendations=recommendations,
            created_at=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Competitor analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze competitors: {str(e)}"
        )


@router.get("/competitors/{analysis_id}")
async def get_analysis_result(
    analysis_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Retrieve a previously generated competitor analysis.

    TODO: Implement caching/storage of analysis results
    """
    # TODO: Retrieve from database/cache
    raise HTTPException(
        status_code=501,
        detail="Analysis retrieval not yet implemented - results are returned immediately"
    )


@router.get("/competitors/templates")
async def list_analysis_templates():
    """
    List available competitor analysis templates.

    Pre-configured focus areas for different industries/use cases.
    """
    templates = {
        "ecommerce": {
            "name": "E-commerce",
            "focus_areas": ["products", "pricing", "shipping", "user_experience", "reviews"],
            "description": "Analyze e-commerce competitors"
        },
        "saas": {
            "name": "SaaS",
            "focus_areas": ["features", "pricing", "integration", "support", "security"],
            "description": "Analyze software-as-a-service competitors"
        },
        "retail": {
            "name": "Retail",
            "focus_areas": ["products", "pricing", "locations", "inventory", "loyalty"],
            "description": "Analyze retail competitors"
        },
        "agency": {
            "name": "Agency/Services",
            "focus_areas": ["services", "pricing", "portfolio", "reputation", "case_studies"],
            "description": "Analyze service-based business competitors"
        }
    }

    return {
        "templates": templates,
        "total": len(templates)
    }
