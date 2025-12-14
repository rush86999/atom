"""
Industry-Specific Workflow Endpoints
API endpoints for accessing and managing industry-tailored workflow templates
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .industry_workflow_templates import (
    get_industry_workflow_engine,
    IndustryWorkflowEngine,
    Industry
)

router = APIRouter()

# Pydantic models for requests/responses

class ROICalculationRequest(BaseModel):
    template_id: str
    hourly_rate: float = Field(50.0, description="Hourly rate for time value calculation")

class TemplateSearchRequest(BaseModel):
    industry: Optional[str] = None
    complexity: Optional[str] = None
    keywords: Optional[List[str]] = None

# Industry Endpoints

@router.get("/api/v1/industries")
async def get_supported_industries(
    engine: IndustryWorkflowEngine = Depends(get_industry_workflow_engine)
):
    """Get list of all supported industries"""
    industries = engine.get_all_industries()
    industry_data = {}

    for industry in industries:
        templates = engine.get_templates_by_industry(industry)
        industry_data[industry.value] = {
            "name": industry.value.replace("_", " ").title(),
            "template_count": len(templates),
            "complexities": list(set(t.complexity for t in templates)),
            "avg_time_savings": _calculate_avg_savings(templates)
        }

    return {
        "success": True,
        "industries": industry_data,
        "total_industries": len(industries)
    }

@router.get("/api/v1/industries/{industry}/templates")
async def get_industry_templates(
    industry: str,
    complexity: Optional[str] = Query(None, description="Filter by complexity level"),
    engine: IndustryWorkflowEngine = Depends(get_industry_workflow_engine)
):
    """Get all templates for a specific industry"""
    try:
        industry_enum = Industry(industry.lower())
        templates = engine.get_templates_by_industry(industry_enum)

        # Filter by complexity if specified
        if complexity:
            templates = [t for t in templates if t.complexity == complexity]

        template_data = []
        for template in templates:
            template_data.append({
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "sub_category": template.sub_category,
                "complexity": template.complexity,
                "estimated_time_savings": template.estimated_time_savings,
                "required_integrations": template.required_integrations,
                "optional_integrations": template.optional_integrations,
                "benefits": template.benefits,
                "use_cases": template.use_cases,
                "created_at": template.created_at
            })

        return {
            "success": True,
            "industry": industry,
            "templates": template_data,
            "template_count": len(template_data)
        }
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Industry {industry} not supported")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get industry templates: {str(e)}"
        )

@router.get("/api/v1/templates/industry/{template_id}")
async def get_industry_template_details(
    template_id: str,
    engine: IndustryWorkflowEngine = Depends(get_industry_workflow_engine)
):
    """Get detailed information about a specific industry template"""
    template = engine.get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")

    return {
        "success": True,
        "template": {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "industry": template.industry.value,
            "sub_category": template.sub_category,
            "complexity": template.complexity,
            "estimated_time_savings": template.estimated_time_savings,
            "required_integrations": template.required_integrations,
            "optional_integrations": template.optional_integrations,
            "setup_instructions": template.setup_instructions,
            "benefits": template.benefits,
            "use_cases": template.use_cases,
            "compliance_notes": template.compliance_notes,
            "workflow_data": template.workflow_data,
            "created_at": template.created_at
        }
    }

@router.post("/api/v1/templates/search")
async def search_industry_templates(
    request: TemplateSearchRequest,
    engine: IndustryWorkflowEngine = Depends(get_industry_workflow_engine)
):
    """Search industry templates with filters"""
    try:
        # Convert industry string to enum if provided
        industry_enum = None
        if request.industry:
            industry_enum = Industry(request.industry.lower())

        templates = engine.search_templates(
            industry=industry_enum,
            complexity=request.complexity,
            keywords=request.keywords or []
        )

        template_data = []
        for template in templates:
            template_data.append({
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "industry": template.industry.value,
                "sub_category": template.sub_category,
                "complexity": template.complexity,
                "estimated_time_savings": template.estimated_time_savings,
                "required_integrations": template.required_integrations,
                "benefits": template.benefits[:3],  # Return top 3 benefits
                "created_at": template.created_at
            })

        return {
            "success": True,
            "search_criteria": {
                "industry": request.industry,
                "complexity": request.complexity,
                "keywords": request.keywords
            },
            "results": template_data,
            "result_count": len(template_data)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )

@router.post("/api/v1/templates/{template_id}/roi")
async def calculate_template_roi(
    template_id: str,
    request: ROICalculationRequest,
    engine: IndustryWorkflowEngine = Depends(get_industry_workflow_engine)
):
    """Calculate ROI for implementing a specific template"""
    try:
        roi_data = engine.calculate_roi(template_id, request.hourly_rate)

        if "error" in roi_data:
            raise HTTPException(status_code=400, detail=roi_data["error"])

        # Add additional insights
        template = engine.get_template_by_id(template_id)
        if template:
            roi_data["insights"] = {
                "primary_benefits": template.benefits[:3],
                "implementation_complexity": template.complexity,
                "setup_timeframe": f"{1 if template.complexity == 'Beginner' else 3 if template.complexity == 'Intermediate' else 5} business days",
                "integration_requirements": {
                    "required": len(template.required_integrations),
                    "optional": len(template.optional_integrations),
                    "total": len(template.required_integrations) + len(template.optional_integrations)
                }
            }

        return {
            "success": True,
            "template_id": template_id,
            "hourly_rate_used": request.hourly_rate,
            "roi_analysis": roi_data,
            "calculated_at": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"ROI calculation failed: {str(e)}"
        )

@router.get("/api/v1/templates/recommendations")
async def get_template_recommendations(
    industry: Optional[str] = Query(None, description="User's industry"),
    company_size: Optional[str] = Query(None, description="Company size: small, medium, large"),
    current_integrations: Optional[str] = Query(None, description="Comma-separated list of current integrations"),
    engine: IndustryWorkflowEngine = Depends(get_industry_workflow_engine)
):
    """Get personalized template recommendations"""
    try:
        all_templates = list(engine.templates.values())

        # Filter by industry if specified
        if industry:
            try:
                industry_enum = Industry(industry.lower())
                all_templates = [t for t in all_templates if t.industry == industry_enum]
            except ValueError:
                pass

        # Parse current integrations
        current_integration_list = []
        if current_integrations:
            current_integration_list = [i.strip().lower() for i in current_integrations.split(",")]

        recommendations = []
        for template in all_templates:
            score = 0
            reasons = []

            # Compatibility with current integrations
            template_integrations = set(i.lower() for i in template.required_integrations)
            compatible_integrations = set(current_integration_list) & template_integrations
            compatibility_score = len(compatible_integrations) / len(template_integrations) if template_integrations else 0

            if compatibility_score >= 0.5:
                score += 30
                reasons.append(f"Compatible with {len(compatible_integrations)} existing integrations")

            # Complexity matching based on company size
            if company_size:
                if company_size == "small" and template.complexity == "Beginner":
                    score += 25
                    reasons.append("Suitable complexity for small business")
                elif company_size == "medium" and template.complexity in ["Beginner", "Intermediate"]:
                    score += 20
                    reasons.append("Appropriate complexity level")
                elif company_size == "large" and template.complexity in ["Intermediate", "Advanced"]:
                    score += 20
                    reasons.append("Scalable for enterprise")

            # Time savings impact
            if "10+ hours" in template.estimated_time_savings:
                score += 25
                reasons.append("High time savings potential")
            elif "5+" in template.estimated_time_savings:
                score += 15
                reasons.append("Moderate time savings")

            # Integration requirements
            if len(template.required_integrations) <= 3:
                score += 10
                reasons.append("Low integration overhead")

            if score >= 30:  # Only include relevant recommendations
                recommendations.append({
                    "template": {
                        "id": template.id,
                        "name": template.name,
                        "description": template.description,
                        "industry": template.industry.value,
                        "complexity": template.complexity,
                        "estimated_time_savings": template.estimated_time_savings,
                        "required_integrations": template.required_integrations,
                        "benefits": template.benefits[:3]
                    },
                    "score": score,
                    "reasons": reasons,
                    "compatibility_score": round(compatibility_score * 100, 1)
                })

        # Sort by score
        recommendations.sort(key=lambda x: x["score"], reverse=True)

        return {
            "success": True,
            "criteria": {
                "industry": industry,
                "company_size": company_size,
                "current_integrations": current_integration_list
            },
            "recommendations": recommendations[:10],  # Top 10 recommendations
            "total_recommendations": len(recommendations)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recommendations: {str(e)}"
        )

@router.get("/api/v1/templates/industry-analytics")
async def get_industry_analytics(
    engine: IndustryWorkflowEngine = Depends(get_industry_workflow_engine)
):
    """Get analytics about industry template usage and trends"""
    try:
        industries = engine.get_all_industries()
        analytics = {
            "industry_distribution": {},
            "complexity_distribution": {"Beginner": 0, "Intermediate": 0, "Advanced": 0},
            "top_integrations": {},
            "time_savings_analysis": {},
            "sub_categories": {}
        }

        for industry in industries:
            templates = engine.get_templates_by_industry(industry)

            # Industry distribution
            analytics["industry_distribution"][industry.value] = len(templates)

            # Complexity distribution
            for template in templates:
                analytics["complexity_distribution"][template.complexity] += 1

                # Integration analysis
                for integration in template.required_integrations:
                    analytics["top_integrations"][integration] = analytics["top_integrations"].get(integration, 0) + 1

                # Sub-category analysis
                if industry.value not in analytics["sub_categories"]:
                    analytics["sub_categories"][industry.value] = {}
                sub_cat = template.sub_category
                analytics["sub_categories"][industry.value][sub_cat] = analytics["sub_categories"][industry.value].get(sub_cat, 0) + 1

                # Time savings analysis
                hours = _extract_hours_from_savings(template.estimated_time_savings)
                if hours:
                    if industry.value not in analytics["time_savings_analysis"]:
                        analytics["time_savings_analysis"][industry.value] = []
                    analytics["time_savings_analysis"][industry.value].append(hours)

        # Calculate average time savings per industry
        for industry in analytics["time_savings_analysis"]:
            hours_list = analytics["time_savings_analysis"][industry]
            analytics["time_savings_analysis"][industry] = {
                "average_hours_per_week": sum(hours_list) / len(hours_list),
                "max_hours_per_week": max(hours_list),
                "template_count": len(hours_list)
            }

        # Sort integrations by usage
        analytics["top_integrations"] = dict(
            sorted(analytics["top_integrations"].items(), key=lambda x: x[1], reverse=True)[:10]
        )

        return {
            "success": True,
            "analytics": analytics,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate analytics: {str(e)}"
        )

@router.get("/api/v1/templates/implementation-guide/{template_id}")
async def get_implementation_guide(
    template_id: str,
    engine: IndustryWorkflowEngine = Depends(get_industry_workflow_engine)
):
    """Get detailed implementation guide for a template"""
    template = engine.get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")

    # Generate comprehensive implementation guide
    guide = {
        "template_info": {
            "name": template.name,
            "industry": template.industry.value,
            "complexity": template.complexity,
            "estimated_setup_time": f"{1 if template.complexity == 'Beginner' else 3 if template.complexity == 'Intermediate' else 5} days"
        },
        "prerequisites": {
            "required_integrations": template.required_integrations,
            "optional_integrations": template.optional_integrations,
            "technical_requirements": [
                "Active ATOM account with workflow automation",
                "API access for all required integrations",
                "Administrator permissions for setup"
            ],
            "pre_setup_checklist": [
                f"Verify API credentials for {', '.join(template.required_integrations)}",
                "Review workflow requirements with team",
                "Prepare test data for validation",
                "Schedule implementation timeline"
            ]
        },
        "step_by_step_setup": template.setup_instructions,
        "configuration_details": {
            "integration_setup": _get_integration_setup_details(template.required_integrations),
            "workflow_customization": [
                "Review trigger conditions",
                "Adjust notification preferences",
                "Configure approval workflows if applicable",
                "Set up monitoring and alerts"
            ],
            "testing_checklist": [
                "Test trigger functionality",
                "Validate data flow between integrations",
                "Verify notification delivery",
                "Check error handling"
            ]
        },
        "post_implementation": {
            "monitoring_points": [
                "Track workflow execution success rate",
                "Monitor processing times",
                "Review error logs regularly",
                "Collect user feedback"
            ],
            "optimization_tips": [
                "Review workflow performance weekly",
                "Adjust triggers based on usage patterns",
                "Add additional error handling as needed",
                "Scale batch sizes based on volume"
            ]
        },
        "support_and_troubleshooting": {
            "common_issues": [
                "API authentication failures",
                "Rate limiting from integration APIs",
                "Data format mismatches",
                "Permission errors"
            ],
            "support_resources": [
                "ATOM knowledge base",
                "Integration documentation",
                "Community forums",
                "Technical support team"
            ]
        }
    }

    if template.compliance_notes:
        guide["compliance_requirements"] = template.compliance_notes

    return {
        "success": True,
        "template_id": template_id,
        "implementation_guide": guide,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }

# Helper functions

def _calculate_avg_savings(templates) -> str:
    """Calculate average time savings for templates"""
    if not templates:
        return "0 hours/week"

    total_hours = 0
    count = 0

    for template in templates:
        hours = _extract_hours_from_savings(template.estimated_time_savings)
        if hours:
            total_hours += hours
            count += 1

    if count == 0:
        return "0 hours/week"

    avg_hours = total_hours / count
    return f"{avg_hours:.1f} hours/week"

def _extract_hours_from_savings(savings_text: str) -> Optional[float]:
    """Extract hours number from savings text"""
    import re
    match = re.search(r'(\d+(?:\.\d+)?)\s*hours?', savings_text.lower())
    if match:
        return float(match.group(1))
    return None

def _get_integration_setup_details(integrations: List[str]) -> Dict[str, List[str]]:
    """Get setup details for integrations"""
    setup_details = {
        "salesforce": [
            "Enable API access in Salesforce settings",
            "Create connected app with appropriate permissions",
            "Generate consumer key and secret",
            "Configure OAuth scopes"
        ],
        "slack": [
            "Create Slack app in workspace",
            "Add bot token permissions",
            "Configure webhook URLs",
            "Set up channel access"
        ],
        "gmail": [
            "Enable Gmail API in Google Cloud Console",
            "Create service account credentials",
            "Configure OAuth consent screen",
            "Set up email templates"
        ],
        "quickbooks": [
            "Create QuickBooks Online app",
            "Configure OAuth 2.0 settings",
            "Set appropriate scopes",
            "Test API connection"
        ],
        "shopify": [
            "Create custom app in Shopify admin",
            "Configure Admin API scopes",
            "Generate API credentials",
            "Test webhook endpoints"
        ],
        "zoom": [
            "Create JWT or OAuth app in Zoom Marketplace",
            "Configure required scopes",
            "Set up webhook events",
            "Test meeting creation"
        ]
    }

    details = {}
    for integration in integrations:
        details[integration] = setup_details.get(integration, [
            f"Configure {integration} API access",
            "Generate necessary credentials",
            "Test connection",
            "Set up required permissions"
        ])

    return details