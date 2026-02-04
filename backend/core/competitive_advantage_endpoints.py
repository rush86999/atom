"""
Competitive Advantage Dashboard Endpoints
API endpoints for showcasing ATOM's competitive advantages and market positioning
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from .competitive_advantage_dashboard import (
    AdvantageCategory,
    CompetitiveAdvantageEngine,
    get_competitive_advantage_engine,
)

router = APIRouter()

@router.get("/api/v1/competitive-advantage/dashboard")
async def get_competitive_dashboard(
    engine: CompetitiveAdvantageEngine = Depends(get_competitive_advantage_engine)
):
    """Get comprehensive competitive advantage dashboard"""
    try:
        dashboard = engine.get_competitive_dashboard()

        return {
            "success": True,
            "dashboard": dashboard,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate competitive dashboard: {str(e)}"
        )

@router.get("/api/v1/competitive-advantage/summary")
async def get_competitive_summary(
    engine: CompetitiveAdvantageEngine = Depends(get_competitive_advantage_engine)
):
    """Get executive summary of competitive advantages"""
    try:
        dashboard = engine.get_competitive_dashboard()
        summary = dashboard["summary"]

        # Add key highlights
        highlights = []

        if summary["overall_competitive_score"] > 150:
            highlights.append("Strong market leadership position")
        if summary["advantages_with_significant_lead"] >= 5:
            highlights.append(f"{summary['advantages_with_significant_lead']} category-leading advantages")
        if summary["market_growth_rate"] > 100:
            highlights.append("Explosive market growth trajectory")
        if summary["sustainable_moats"] >= 2:
            highlights.append("Multiple sustainable competitive moats")

        return {
            "success": True,
            "executive_summary": {
                **summary,
                "key_highlights": highlights,
                "competitive_positioning": "Challenging market leaders with differentiated approach",
                "primary_message": "Enterprise-grade automation at wholesale AI costs"
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate competitive summary: {str(e)}"
        )

@router.get("/api/v1/competitive-advantage/byok-analysis")
async def get_byok_competitive_analysis(
    engine: CompetitiveAdvantageEngine = Depends(get_competitive_advantage_engine)
):
    """Get detailed BYOK competitive analysis"""
    try:
        dashboard = engine.get_competitive_dashboard()
        cost_advantages = dashboard["advantages_by_category"]["cost"]

        # BYOK-specific analysis
        byok_metrics = [m for m in cost_advantages["metrics"] if "BYOK" in m["name"] or "cost" in m["name"].lower()]

        comparison_data = {
            "atom_approach": {
                "model": "Bring Your Own Key (BYOK)",
                "pricing": "Wholesale rates from AI providers",
                "transparency": "100% cost visibility",
                "control": "Complete user control over API keys",
                "vendor_lock_in": "None - users own their integrations"
            },
            "competitor_approach": {
                "model": "Reseller/Platform markup",
                "pricing": "200-500% markup on AI costs",
                "transparency": "Hidden fees and complex pricing",
                "control": "Platform controls all AI access",
                "vendor_lock_in": "High - difficult to export workflows"
            }
        }

        roi_calculation = {
            "example_scenarios": [
                {
                    "scenario": "Medium Business (100K AI tokens/month)",
                    "atom_cost": 200,
                    "competitor_cost": 800,
                    "monthly_savings": 600,
                    "annual_savings": 7200
                },
                {
                    "scenario": "Large Enterprise (1M AI tokens/month)",
                    "atom_cost": 2000,
                    "competitor_cost": 10000,
                    "monthly_savings": 8000,
                    "annual_savings": 96000
                }
            ],
            "payback_period": "Immediate - savings start from day 1"
        }

        return {
            "success": True,
            "byok_analysis": {
                "metrics": byok_metrics,
                "comparison": comparison_data,
                "roi_examples": roi_calculation,
                "key_advantages": [
                    "No service markup on AI costs",
                    "Complete pricing transparency",
                    "User-controlled API keys",
                    "Multi-provider optimization",
                    "No vendor lock-in"
                ],
                "market_impact": "BYOK model fundamentally changes automation platform economics"
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate BYOK analysis: {str(e)}"
        )

@router.get("/api/v1/competitive-advantage/roi-calculator")
async def calculate_roi(
    monthly_ai_usage: float = Query(..., description="Monthly AI usage in tokens"),
    current_platform_cost: Optional[float] = Query(None, description="Current monthly platform cost"),
    implementation_time_weeks: float = Query(4.0, description="Expected implementation time in weeks"),
    hourly_rate: float = Query(50.0, description="Hourly rate for time value calculation"),
    engine: CompetitiveAdvantageEngine = Depends(get_competitive_advantage_engine)
):
    """Calculate ROI for switching to ATOM"""
    try:
        # Calculate costs
        # AI cost (wholesale rates)
        ai_cost_per_token = 0.002  # Average across providers
        atom_ai_cost = monthly_ai_usage * ai_cost_per_token

        # Platform cost (ATOM has minimal platform fees)
        atom_platform_cost = 50  # Minimal subscription

        # Implementation cost
        implementation_cost = implementation_time_weeks * 40 * hourly_rate  # 40 hours/week

        # Competitor cost calculation
        if current_platform_cost:
            competitor_cost = current_platform_cost
        else:
            # Estimate based on typical competitor pricing
            competitor_ai_cost = monthly_ai_usage * ai_cost_per_token * 3.5  # 250% markup
            competitor_platform_cost = 500  # Typical enterprise platform fee
            competitor_cost = competitor_ai_cost + competitor_platform_cost

        # Monthly savings
        monthly_savings = competitor_cost - (atom_ai_cost + atom_platform_cost)

        # ROI calculations
        monthly_roi = (monthly_savings / (atom_ai_cost + atom_platform_cost)) * 100 if (atom_ai_cost + atom_platform_cost) > 0 else 0
        payback_period_weeks = implementation_cost / monthly_savings if monthly_savings > 0 else 52  # Default to 1 year

        # 3-year projections
        three_year_savings = monthly_savings * 36
        total_investment = implementation_cost + (atom_ai_cost + atom_platform_cost) * 36
        three_year_roi = ((three_year_savings - total_investment) / total_investment) * 100 if total_investment > 0 else 0

        return {
            "success": True,
            "roi_analysis": {
                "assumptions": {
                    "monthly_ai_usage": monthly_ai_usage,
                    "ai_cost_per_token": ai_cost_per_token,
                    "implementation_time_weeks": implementation_time_weeks,
                    "hourly_rate": hourly_rate
                },
                "cost_comparison": {
                    "atom": {
                        "ai_cost": round(atom_ai_cost, 2),
                        "platform_cost": atom_platform_cost,
                        "total_monthly_cost": round(atom_ai_cost + atom_platform_cost, 2)
                    },
                    "competitor": {
                        "monthly_cost": round(competitor_cost, 2),
                        "estimated_markup_percentage": 250
                    }
                },
                "financial_impact": {
                    "monthly_savings": round(monthly_savings, 2),
                    "annual_savings": round(monthly_savings * 12, 2),
                    "monthly_roi_percentage": round(monthly_roi, 1),
                    "payback_period_weeks": round(payback_period_weeks, 1),
                    "three_year_savings": round(three_year_savings, 2),
                    "three_year_roi_percentage": round(three_year_roi, 1)
                },
                "intangible_benefits": [
                    "Complete data control and privacy",
                    "No vendor lock-in",
                    "Multi-provider AI optimization",
                    "50+ deep integrations",
                    "Industry-specific templates"
                ]
            },
            "calculated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"ROI calculation failed: {str(e)}"
        )

@router.get("/api/v1/competitive-advantage/differentiators")
async def get_key_differentiators(
    engine: CompetitiveAdvantageEngine = Depends(get_competitive_advantage_engine)
):
    """Get ATOM's key differentiators with evidence"""
    try:
        dashboard = engine.get_competitive_dashboard()
        differentiators = dashboard["key_differentiators"]

        # Add competitive landscape context
        landscape_analysis = {
            "primary_competitors": [
                {
                    "name": "Zapier",
                    "strengths": ["Large user base", "Brand recognition", "Extensive integration library"],
                    "weaknesses": ["High pricing markup", "No AI optimization", "Limited data control"]
                },
                {
                    "name": "Make (Integromat)",
                    "strengths": ["Visual interface", "Good pricing tiers", "Strong integration support"],
                    "weaknesses": ["Single AI provider", "No BYOK", "Limited enterprise features"]
                },
                {
                    "name": "Microsoft Power Automate",
                    "strengths": ["Microsoft ecosystem", "Enterprise features", "RPA capabilities"],
                    "weaknesses": ["Proprietary lock-in", "Complex pricing", "Limited AI provider choice"]
                }
            ],
            "atom_unique_position": "Only platform combining BYOK, multi-provider AI optimization, and enterprise-grade privacy"
        }

        return {
            "success": True,
            "differentiators": differentiators,
            "competitive_landscape": landscape_analysis,
            "market_positioning": "Premium automation at wholesale costs",
            "next_generation_features": [
                "Real-time AI provider optimization",
                "Zero-knowledge workflow execution",
                "Industry-specific automation templates",
                "Advanced data transformation engine"
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get differentiators: {str(e)}"
        )

@router.get("/api/v1/competitive-advantage/testimonials")
async def get_customer_testimonials():
    """Get customer testimonials and success stories"""
    # Mock testimonials - in real implementation, these would come from database
    testimonials = [
        {
            "company": "TechStartup Inc",
            "industry": "Technology",
            "size": "50-100 employees",
            "quote": "ATOM reduced our automation costs by 40% while giving us complete control over our AI tools. The BYOK model is a game-changer.",
            "results": {
                "cost_savings": "40%",
                "implementation_time": "3 weeks",
                "automated_processes": 25
            },
            "use_case": "Customer onboarding and support automation"
        },
        {
            "company": "Healthcare Solutions Group",
            "industry": "Healthcare",
            "size": "200-500 employees",
            "quote": "The zero data retention policy and industry-specific templates made ATOM the only choice for our compliance requirements.",
            "results": {
                "compliance_achievement": "HIPAA compliant in 30 days",
                "implementation_time": "4 weeks",
                "automated_processes": 40
            },
            "use_case": "Patient onboarding and appointment management"
        },
        {
            "company": "Global Logistics Co",
            "industry": "Logistics",
            "size": "1000+ employees",
            "quote": "The multi-provider AI optimization and deep integrations saved us $200K in the first year alone.",
            "results": {
                "annual_savings": "$200,000",
                "implementation_time": "6 weeks",
                "automated_processes": 60
            },
            "use_case": "Supply chain automation and tracking"
        }
    ]

    return {
        "success": True,
        "testimonials": testimonials,
        "success_metrics": {
            "average_cost_savings": "38%",
            "average_implementation_time": "4.3 weeks",
            "total_automated_processes": 125,
            "customer_satisfaction": "4.8/5"
        }
    }

@router.get("/api/v1/competitive-advantage/industry-analysis/{industry}")
async def get_industry_competitive_analysis(
    industry: str,
    engine: CompetitiveAdvantageEngine = Depends(get_competitive_advantage_engine)
):
    """Get competitive analysis for a specific industry"""
    try:
        # Industry-specific competitive advantages
        industry_advantages = {
            "healthcare": {
                "key_advantages": [
                    "HIPAA-compliant by design",
                    "Zero data retention policy",
                    "Healthcare-specific workflow templates",
                    "Secure patient data handling"
                ],
                "competitive_pain_points": [
                    "Data privacy concerns",
                    "Regulatory compliance",
                    "Complex patient workflows"
                ],
                "value_proposition": "Compliant automation without compromising patient privacy"
            },
            "finance": {
                "key_advantages": [
                    "SOC 2 Type II compliance",
                    "Complete audit trails",
                    "Financial industry templates",
                    "Secure transaction handling"
                ],
                "competitive_pain_points": [
                    "Regulatory compliance costs",
                    "Data security requirements",
                    "Legacy system integration"
                ],
                "value_proposition": "Enterprise-grade security at a fraction of traditional costs"
            },
            "education": {
                "key_advantages": [
                    "FERPA compliance",
                    "Student data protection",
                    "Education workflow templates",
                    "Affordable pricing for schools"
                ],
                "competitive_pain_points": [
                    "Limited IT budgets",
                    "Student privacy concerns",
                    "Administrative burden"
                ],
                "value_proposition": "Streamline administration while protecting student data"
            },
            "retail": {
                "key_advantages": [
                    "E-commerce integrations",
                    "Inventory automation",
                    "Customer experience workflows",
                    "Rapid implementation"
                ],
                "competitive_pain_points": [
                    "Thin margins",
                    "Complex supply chains",
                    "Customer expectations"
                ],
                "value_proposition": "Automate operations while maintaining profitability"
            }
        }

        if industry.lower() not in industry_advantages:
            raise HTTPException(
                status_code=404,
                detail=f"Industry analysis not available for: {industry}"
            )

        advantages = industry_advantages[industry.lower()]

        return {
            "success": True,
            "industry": industry,
            "competitive_analysis": advantages,
            "market_opportunity": f"{industry.title()} sector ripe for automation disruption",
            "atom_positioning": f"Leading {industry} automation platform with privacy-first approach"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Industry analysis failed: {str(e)}"
        )

@router.get("/api/v1/competitive-advantage/implementation-roadmap")
async def get_implementation_roadmap():
    """Get implementation roadmap for competitive advantages"""
    roadmap = {
        "current_quarter": {
            "focus": "Strengthen BYOK Leadership",
            "initiatives": [
                "Expand AI provider partnerships to 10+ providers",
                "Develop advanced cost optimization algorithms",
                "Create comprehensive BYOK documentation",
                "Build customer success stories for cost savings"
            ]
        },
        "next_quarter": {
            "focus": "Enterprise Market Expansion",
            "initiatives": [
                "Achieve SOC 2 Type II certification",
                "Build enterprise sales team",
                "Develop enterprise onboarding process",
                "Create compliance automation packages"
            ]
        },
        "next_6_months": {
            "focus": "Integration Moat Deepening",
            "initiatives": [
                "Launch integration marketplace",
                "Add 20 new deep integrations",
                "Release connector SDK",
                "Build integration partner program"
            ]
        },
        "next_year": {
            "focus": "Market Leadership",
            "initiatives": [
                "Achieve #3 market position",
                "Expand to international markets",
                "Develop mobile automation capabilities",
                "Build AI-powered workflow discovery"
            ]
        }
    }

    return {
        "success": True,
        "implementation_roadmap": roadmap,
        "strategic_priorities": [
            "Maintain BYOK cost advantage leadership",
            "Capture enterprise market share",
            "Build sustainable integration moat",
            "Expand geographic presence"
        ]
    }