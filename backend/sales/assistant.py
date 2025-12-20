import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sales.models import Lead, Deal, FollowUpTask, LeadStatus
from sales.intelligence import SalesIntelligence
from core.automation_settings import get_automation_settings

logger = logging.getLogger(__name__)

class SalesAssistant:
    """
    Conversational AI for Sales and CRM data.
    """
    def __init__(self, db: Session):
        self.db = db
        self.intelligence = SalesIntelligence(db)
        self.settings = get_automation_settings()

    async def answer_sales_query(self, workspace_id: str, query: str) -> str:
        """
        Process natural language queries about sales data.
        """
        if not self.settings.is_sales_enabled():
            return "AI Sales features are currently disabled in settings."

        query_lower = query.lower()

        # 1. Pipeline/Forecast Queries
        if any(word in query_lower for word in ["pipeline", "forecast", "revenue", "expecting"]):
            forecast = self.intelligence.get_pipeline_forecast(workspace_id)
            return (f"Your current weighted pipeline is **${forecast['weighted_pipeline']:,.2f}** "
                    f"across {forecast['deal_count']} active deals. "
                    f"The total unweighted value is ${forecast['unweighted_pipeline']:,.2f}.")

        # 2. Risk/Health Queries
        if any(word in query_lower for word in ["risk", "health", "stalled", "problem"]):
            deals = self.db.query(Deal).filter(
                Deal.workspace_id == workspace_id,
                Deal.health_score < 50
            ).all()
            
            if not deals:
                return "Great news! No high-risk deals detected in your current pipeline."
            
            deal_list = "\n".join([f"- **{d.name}**: Health {d.health_score:.0f}/100 (Risk: {d.risk_level})" for d in deals])
            return f"I've identified {len(deals)} deals that might need attention:\n{deal_list}"

        # 3. Lead Queries
        if any(word in query_lower for word in ["leads", "prospects", "new signup"]):
            leads = self.db.query(Lead).filter(
                Lead.workspace_id == workspace_id,
                Lead.status == LeadStatus.NEW
            ).order_by(Lead.ai_score.desc()).limit(5).all()
            
            if not leads:
                return "You're all caught up on new leads!"
            
            lead_list = "\n".join([f"- **{l.first_name or ''} {l.last_name or ''}** ({l.company or 'Unknown'}): AI Score {l.ai_score:.0f}" for l in leads])
            return f"Here are your top new leads to follow up on:\n{lead_list}"

        # 4. Follow-up Queries
        if any(word in query_lower for word in ["follow up", "task", "todo", "action items"]):
            tasks = self.db.query(FollowUpTask).filter(
                FollowUpTask.workspace_id == workspace_id,
                FollowUpTask.is_completed == False
            ).limit(5).all()
            
            if not tasks:
                return "You have no pending sales follow-up tasks."
            
            task_list = "\n".join([f"- {t.description}" for t in tasks])
            return f"Here are your priority follow-ups:\n{task_list}"

        return "I can help you with sales pipeline forecasts, lead scoring, deal health, and follow-up tasks. What would you like to know?"
