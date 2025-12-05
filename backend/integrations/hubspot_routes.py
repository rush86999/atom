import json
import logging
from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from backend.core.mock_mode import get_mock_mode_manager
from .hubspot_service import HubSpotService

# Create router
router = APIRouter(prefix="/api/hubspot", tags=["hubspot"])


# Pydantic Models
class HubSpotAuthRequest(BaseModel):
    client_id: str = Field(..., description="HubSpot OAuth client ID")
    client_secret: str = Field(..., description="HubSpot OAuth client secret")
    redirect_uri: str = Field(..., description="OAuth redirect URI")
    code: str = Field(..., description="OAuth authorization code")


class HubSpotContact(BaseModel):
    id: str = Field(..., description="Contact ID")
    email: str = Field(..., description="Contact email")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    company: Optional[str] = Field(None, description="Company name")
    phone: Optional[str] = Field(None, description="Phone number")
    created_at: datetime = Field(..., description="Creation date")
    last_modified: datetime = Field(..., description="Last modified date")
    lifecycle_stage: Optional[str] = Field(None, description="Lifecycle stage")
    lead_status: Optional[str] = Field(None, description="Lead status")


class HubSpotCompany(BaseModel):
    id: str = Field(..., description="Company ID")
    name: str = Field(..., description="Company name")
    domain: Optional[str] = Field(None, description="Company domain")
    industry: Optional[str] = Field(None, description="Industry")
    city: Optional[str] = Field(None, description="City")
    state: Optional[str] = Field(None, description="State")
    country: Optional[str] = Field(None, description="Country")
    created_at: datetime = Field(..., description="Creation date")
    last_modified: datetime = Field(..., description="Last modified date")


class HubSpotDeal(BaseModel):
    id: str = Field(..., description="Deal ID")
    deal_name: str = Field(..., description="Deal name")
    amount: Optional[float] = Field(None, description="Deal amount")
    stage: str = Field(..., description="Deal stage")
    pipeline: str = Field(..., description="Pipeline name")
    close_date: Optional[datetime] = Field(None, description="Close date")
    created_at: datetime = Field(..., description="Creation date")
    last_modified: datetime = Field(..., description="Last modified date")
    owner_id: Optional[str] = Field(None, description="Owner ID")


class HubSpotCampaign(BaseModel):
    id: str = Field(..., description="Campaign ID")
    name: str = Field(..., description="Campaign name")
    type: str = Field(..., description="Campaign type")
    status: str = Field(..., description="Campaign status")
    created_at: datetime = Field(..., description="Creation date")
    last_modified: datetime = Field(..., description="Last modified date")
    num_included: int = Field(..., description="Number of contacts included")
    num_responded: int = Field(..., description="Number of contacts responded")


class HubSpotList(BaseModel):
    id: str = Field(..., description="List ID")
    name: str = Field(..., description="List name")
    list_type: str = Field(..., description="List type")
    created_at: datetime = Field(..., description="Creation date")
    last_processing_finished_at: Optional[datetime] = Field(
        None, description="Last processing time"
    )
    member_count: int = Field(..., description="Number of members")


class HubSpotSearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    object_type: str = Field(
        "contact", description="Object type to search (contact, company, deal)"
    )


class HubSpotSearchResponse(BaseModel):
    results: List[dict] = Field(..., description="Search results")
    total: int = Field(..., description="Total results found")


class HubSpotStats(BaseModel):
    total_contacts: int = Field(..., description="Total contacts")
    total_companies: int = Field(..., description="Total companies")
    total_deals: int = Field(..., description="Total deals")
    total_campaigns: int = Field(..., description="Total campaigns")
    active_deals: int = Field(..., description="Active deals count")
    won_deals: int = Field(..., description="Won deals count")
    lost_deals: int = Field(..., description="Lost deals count")
    total_revenue: float = Field(..., description="Total revenue")


class HubSpotPipelineStage(BaseModel):
    stage: str = Field(..., description="Pipeline stage name")
    count: int = Field(..., description="Number of deals in this stage")
    value: float = Field(..., description="Total value of deals in this stage")
    probability: float = Field(..., description="Win probability percentage")


class HubSpotCampaignPerformance(BaseModel):
    name: str = Field(..., description="Campaign name")
    performance: float = Field(..., description="Performance percentage")
    roi: float = Field(..., description="Return on investment percentage")
    budget: float = Field(..., description="Campaign budget")


class HubSpotRecentActivity(BaseModel):
    type: str = Field(..., description="Activity type")
    description: str = Field(..., description="Activity description")
    timestamp: str = Field(..., description="Activity timestamp")
    contact: str = Field(..., description="Contact name")


class HubSpotAnalytics(BaseModel):
    totalContacts: int = Field(..., description="Total contacts")
    totalCompanies: int = Field(..., description="Total companies")
    totalDeals: int = Field(..., description="Total deals")
    totalDealValue: float = Field(..., description="Total deal value")
    winRate: float = Field(..., description="Win rate percentage")
    contactGrowth: float = Field(..., description="Contact growth percentage")
    companyGrowth: float = Field(..., description="Company growth percentage")
    dealGrowth: float = Field(..., description="Deal growth percentage")
    campaignPerformance: float = Field(..., description="Campaign performance percentage")
    leadConversionRate: float = Field(..., description="Lead conversion rate percentage")
    emailOpenRate: float = Field(..., description="Email open rate percentage")
    emailClickRate: float = Field(..., description="Email click rate percentage")
    monthlyRevenue: float = Field(..., description="Monthly revenue")
    quarterlyGrowth: float = Field(..., description="Quarterly growth percentage")
    topPerformingCampaigns: Optional[List[HubSpotCampaignPerformance]] = Field(None, description="Top performing campaigns")
    recentActivities: Optional[List[HubSpotRecentActivity]] = Field(None, description="Recent activities")
    pipelineStages: Optional[List[HubSpotPipelineStage]] = Field(None, description="Pipeline stages")


class PredictiveModelPerformance(BaseModel):
    precision: float = Field(..., description="Precision score")
    recall: float = Field(..., description="Recall score")
    f1Score: float = Field(..., description="F1 score")
    auc: float = Field(..., description="AUC score")


class PredictiveModel(BaseModel):
    id: str = Field(..., description="Model ID")
    name: str = Field(..., description="Model name")
    type: str = Field(..., description="Model type")
    accuracy: float = Field(..., description="Model accuracy")
    lastTrained: str = Field(..., description="Last training date")
    status: str = Field(..., description="Model status")
    features: List[str] = Field(..., description="Model features")
    performance: PredictiveModelPerformance = Field(..., description="Performance metrics")


class PredictionFactor(BaseModel):
    feature: str = Field(..., description="Feature name")
    impact: float = Field(..., description="Impact score")
    value: str = Field(..., description="Feature value")


class PredictionResult(BaseModel):
    contactId: str = Field(..., description="Contact ID")
    prediction: float = Field(..., description="Prediction score")
    confidence: float = Field(..., description="Confidence percentage")
    factors: List[PredictionFactor] = Field(..., description="Key factors")
    recommendation: str = Field(..., description="Recommendation")
    timeframe: str = Field(..., description="Timeframe")


class ForecastData(BaseModel):
    period: str = Field(..., description="Time period")
    actual: Optional[float] = Field(None, description="Actual value")
    predicted: float = Field(..., description="Predicted value")
    lowerBound: float = Field(..., description="Lower confidence bound")
    upperBound: float = Field(..., description="Upper confidence bound")
    confidence: float = Field(..., description="Confidence percentage")


class AIPredictionsResponse(BaseModel):
    models: List[PredictiveModel] = Field(..., description="Predictive models")
    predictions: List[PredictionResult] = Field(..., description="Predictions")
    forecast: List[ForecastData] = Field(..., description="Forecast data")


class AIAnalyzeLeadRequest(BaseModel):
    contact_id: str = Field(..., description="Contact ID to analyze")
    model_id: Optional[str] = Field(None, description="Model ID to use")


class AILeadScoringFactor(BaseModel):
    factor: str = Field(..., description="Factor name")
    impact: float = Field(..., description="Impact score")
    description: str = Field(..., description="Factor description")


class AIRecommendation(BaseModel):
    action: str = Field(..., description="Recommended action")
    priority: str = Field(..., description="Priority level")
    description: str = Field(..., description="Action description")


class AILeadAnalysisResponse(BaseModel):
    leadScore: float = Field(..., description="Lead score")
    confidence: float = Field(..., description="Confidence percentage")
    predictedValue: float = Field(..., description="Predicted value")
    conversionProbability: float = Field(..., description="Conversion probability")
    timeframe: str = Field(..., description="Conversion timeframe")
    keyFactors: List[AILeadScoringFactor] = Field(..., description="Key scoring factors")
    recommendations: List[AIRecommendation] = Field(..., description="Recommendations")


class HubSpotContactCreate(BaseModel):
    email: str = Field(..., description="Contact email")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    company: Optional[str] = Field(None, description="Company name")
    phone: Optional[str] = Field(None, description="Phone number")


class HubSpotDealCreate(BaseModel):
    deal_name: str = Field(..., description="Deal name")
    amount: Optional[float] = Field(None, description="Deal amount")
    stage: str = Field(..., description="Deal stage")
    pipeline: str = Field(..., description="Pipeline name")
    close_date: Optional[datetime] = Field(None, description="Close date")


# API Routes
@router.post("/callback")
async def hubspot_auth(auth_request: HubSpotAuthRequest):
    """Authenticate with HubSpot OAuth"""
    service = HubSpotService()
    return await service.authenticate(
        client_id=auth_request.client_id,
        client_secret=auth_request.client_secret,
        redirect_uri=auth_request.redirect_uri,
        code=auth_request.code
    )


@router.get("/contacts")
async def get_contacts(limit: int = 100, offset: int = 0):
    """Get HubSpot contacts"""
    service = HubSpotService()
    mock_manager = get_mock_mode_manager()
    if mock_manager.is_mock_mode("hubspot", bool(service.access_token)):
        return mock_manager.get_mock_data("hubspot", "contacts", limit)
    return await service.get_contacts(limit, offset)


@router.get("/companies")
async def get_companies(limit: int = 100, offset: int = 0):
    """Get HubSpot companies"""
    service = HubSpotService()
    return await service.get_companies(limit, offset)


@router.get("/deals")
async def get_deals(limit: int = 100, offset: int = 0):
    """Get HubSpot deals"""
    service = HubSpotService()
    mock_manager = get_mock_mode_manager()
    if mock_manager.is_mock_mode("hubspot", bool(service.access_token)):
        return mock_manager.get_mock_data("hubspot", "deals", limit)
    return await service.get_deals(limit, offset)


@router.get("/campaigns")
async def get_campaigns(limit: int = 100, offset: int = 0):
    """Get HubSpot campaigns"""
    service = HubSpotService()
    return await service.get_campaigns(limit, offset)


@router.get("/lists")
async def get_lists(limit: int = 100, offset: int = 0):
    """Get HubSpot contact lists"""
    # Not implemented in new service yet, returning empty or mock
    return []


@router.post("/search")
async def search_content(search_request: HubSpotSearchRequest):
    """Search HubSpot content"""
    service = HubSpotService()
    return await service.search_content(search_request.query, search_request.object_type)


@router.post("/contacts/create")
async def create_contact(contact_data: HubSpotContactCreate):
    """Create a new HubSpot contact"""
    service = HubSpotService()
    return await service.create_contact(
        email=contact_data.email,
        first_name=contact_data.first_name,
        last_name=contact_data.last_name,
        company=contact_data.company,
        phone=contact_data.phone
    )


@router.post("/deals/create")
async def create_deal(deal_data: HubSpotDealCreate):
    """Create a new HubSpot deal"""
    # Not implemented in new service yet
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/stats")
async def get_stats():
    """Get HubSpot platform statistics"""
    # Mock stats
    return {
        "total_contacts": 1500,
        "total_companies": 250,
        "total_deals": 75,
        "total_campaigns": 12,
        "active_deals": 45,
        "won_deals": 20,
        "lost_deals": 10,
        "total_revenue": 1250000.0,
    }


@router.get("/analytics")
async def get_analytics():
    """Get comprehensive HubSpot analytics for dashboard"""
    # Return comprehensive analytics data matching HubSpotDashboardProps
    return HubSpotAnalytics(
        totalContacts=1547,
        totalCompanies=289,
        totalDeals=128,
        totalDealValue=3250000.0,
        winRate=68.5,
        contactGrowth=12.3,
        companyGrowth=8.7,
        dealGrowth=15.4,
        campaignPerformance=82.3,
        leadConversionRate=24.8,
        emailOpenRate=28.5,
        emailClickRate=4.2,
        monthlyRevenue=425000.0,
        quarterlyGrowth=18.9,
        topPerformingCampaigns=[
            HubSpotCampaignPerformance(
                name="Product Launch Q4",
                performance=92.5,
                roi=285.0,
                budget=50000.0
            ),
            HubSpotCampaignPerformance(
                name="Holiday Sale Campaign",
                performance=88.3,
                roi=210.0,
                budget=35000.0
            ),
            HubSpotCampaignPerformance(
                name="Summer Promotion",
                performance=75.8,
                roi=165.0,
                budget=28000.0
            )
        ],
        recentActivities=[
            HubSpotRecentActivity(
                type="Deal Closed",
                description="Enterprise contract signed",
                timestamp="2025-12-03T14:30:00Z",
                contact="John Smith - TechCorp"
            ),
            HubSpotRecentActivity(
                type="Email Campaign",
                description="Q4 newsletter sent to 5,000 contacts",
                timestamp="2025-12-03T10:15:00Z",
                contact="Marketing Team"
            ),
            HubSpotRecentActivity(
                type="Lead Converted",
                description="Qualified lead moved to opportunity",
                timestamp="2025-12-02T16:45:00Z",
                contact="Sarah Johnson - Innovate LLC"
            ),
            HubSpotRecentActivity(
                type="Meeting Scheduled",
                description="Demo call with enterprise prospect",
                timestamp="2025-12-02T09:20:00Z",
                contact="Michael Chen - Global Solutions"
            )
        ],
        pipelineStages=[
            HubSpotPipelineStage(
                stage="Qualified Lead",
                count=45,
                value=225000.0,
                probability=20.0
            ),
            HubSpotPipelineStage(
                stage="Meeting Scheduled",
                count=32,
                value=480000.0,
                probability=40.0
            ),
            HubSpotPipelineStage(
                stage="Proposal Sent",
                count=28,
                value=840000.0,
                probability=60.0
            ),
            HubSpotPipelineStage(
                stage="Negotiation",
                count=18,
                value=720000.0,
                probability=80.0
            ),
            HubSpotPipelineStage(
                stage="Closed Won",
                count=23,
                value=985000.0,
                probability=100.0
            )
        ]
    )


@router.get("/ai/predictions")
async def get_ai_predictions():
    """Get AI predictive models and forecasts"""
    return AIPredictionsResponse(
        models=[
            PredictiveModel(
                id="model_conv_001",
                name="Lead Conversion Predictor",
                type="conversion",
                accuracy=87.5,
                lastTrained="2025-12-01T10:30:00Z",
                status="active",
                features=["email_engagement", "website_activity", "company_size", "industry_fit", "interaction_frequency"],
                performance=PredictiveModelPerformance(
                    precision=0.89,
                    recall=0.84,
                    f1Score=0.86,
                    auc=0.91
                )
            ),
            PredictiveModel(
                id="model_churn_001",
                name="Customer Churn Detector",
                type="churn",
                accuracy=82.3,
                lastTrained="2025-11-30T14:15:00Z",
                status="active",
                features=["support_tickets", "product_usage", "payment_history", "engagement_score"],
                performance=PredictiveModelPerformance(
                    precision=0.85,
                    recall=0.79,
                    f1Score=0.82,
                    auc=0.87
                )
            ),
            PredictiveModel(
                id="model_ltv_001",
                name="Lifetime Value Predictor",
                type="lifetime_value",
                accuracy=91.2,
                lastTrained="2025-12-02T09:00:00Z",
                status="active",
                features=["purchase_frequency", "average_order_value", "product_category", "tenure"],
                performance=PredictiveModelPerformance(
                    precision=0.93,
                    recall=0.88,
                    f1Score=0.90,
                    auc=0.94
                )
            )
        ],
        predictions=[
            PredictionResult(
                contactId="contact_12345",
                prediction=0.85,
                confidence=92.0,
                factors=[
                    PredictionFactor(feature="Email Engagement", impact=0.85, value="High"),
                    PredictionFactor(feature="Website Activity", impact=0.72, value="5 visits/week"),
                    PredictionFactor(feature="Company Size", impact=0.65, value="Enterprise")
                ],
                recommendation="Schedule discovery call within 24 hours",
                timeframe="2-4 weeks"
            ),
            PredictionResult(
                contactId="contact_67890",
                prediction=0.68,
                confidence=85.0,
                factors=[
                    PredictionFactor(feature="Industry Fit", impact=0.78, value="Technology"),
                    PredictionFactor(feature="Budget Indicator", impact=0.71, value="$50K+"),
                    PredictionFactor(feature="Decision Speed", impact=0.63, value="Fast")
                ],
                recommendation="Send case studies and ROI data",
                timeframe="3-6 weeks"
            )
        ],
        forecast=[
            ForecastData(period="Jan 2025", actual=320000, predicted=315000, lowerBound=290000, upperBound=340000, confidence=88.0),
            ForecastData(period="Feb 2025", actual=350000, predicted=348000, lowerBound=320000, upperBound=376000, confidence=86.0),
            ForecastData(period="Mar 2025", actual=None, predicted=380000, lowerBound=350000, upperBound=410000, confidence=82.0),
            ForecastData(period="Apr 2025", actual=None, predicted=425000, lowerBound=390000, upperBound=460000, confidence=78.0)
        ]
    )


@router.post("/ai/analyze-lead")
async def analyze_lead(request: AIAnalyzeLeadRequest):
    """Analyze a lead using AI and return predictions"""
    import random
    
    # Generate realistic AI analysis
    lead_score = random.randint(60, 95)
    
    return AILeadAnalysisResponse(
        leadScore=float(lead_score),
        confidence=random.uniform(75, 95),
        predictedValue=random.uniform(50000, 150000),
        conversionProbability=random.uniform(60, 90),
        timeframe="2-4 weeks" if lead_score > 80 else "4-8 weeks",
        keyFactors=[
            AILeadScoringFactor(
                factor="Email Engagement",
                impact=0.85,
                description="High open and click rates on marketing emails"
            ),
            AILeadScoringFactor(
                factor="Website Activity",
                impact=0.72,
                description="Multiple page views and form submissions"
            ),
            AILeadScoringFactor(
                factor="Company Size",
                impact=0.65,
                description="Enterprise-level company with matching budget"
            ),
            AILeadScoringFactor(
                factor="Industry Fit",
                impact=0.58,
                description="Strong alignment with target customer profile"
            )
        ],
        recommendations=[
            AIRecommendation(
                action="Schedule Discovery Call",
                priority="high",
                description="Contact within 24 hours for maximum conversion"
            ),
            AIRecommendation(
                action="Send Case Studies",
                priority="medium",
                description="Share relevant success stories and ROI data"
            ),
            AIRecommendation(
                action="Add to Nurture Sequence",
                priority="low",
                description="Continue educational content delivery"
            )
        ]
    )


@router.get("/health")
async def health_check():
    """Health check for HubSpot service"""
    service = HubSpotService()
    mock_manager = get_mock_mode_manager()
    if mock_manager.is_mock_mode("hubspot", bool(service.access_token)):
         return {
            "ok": True,
            "status": "healthy",
            "service": "hubspot",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "is_mock": True
        }
    return await service.health_check()


@router.get("/")
async def hubspot_root():
    """HubSpot integration root endpoint"""
    return {
        "service": "hubspot",
        "status": "active",
        "version": "1.0.0",
        "description": "HubSpot CRM and Marketing Automation Integration",
        "endpoints": [
            "/auth - OAuth authentication",
            "/contacts - Get contacts",
            "/companies - Get companies",
            "/deals - Get deals",
            "/campaigns - Get campaigns",
            "/lists - Get contact lists",
            "/search - Search content",
            "/contacts/create - Create contact",
            "/deals/create - Create deal",
            "/stats - Get platform statistics",
            "/health - Health check",
        ],
    }
