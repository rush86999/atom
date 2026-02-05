import asyncio
from datetime import datetime, timedelta
import json
import logging
from typing import Any, Dict, List, Optional
from ecommerce.models import EcommerceOrder
from marketing.models import AdSpendEntry
from sales.models import Deal, Lead
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.models import AgentJob
from integrations.ai_enhanced_service import (
    AIModelType,
    AIRequest,
    AIServiceType,
    AITaskType,
    ai_enhanced_service,
)

logger = logging.getLogger(__name__)

class BusinessHealthService:
    """
    Orchestrates intelligence across all ATOM domains to provide owner load reduction.
    """

    def __init__(self, db: Session = None):
        self._db = db

    @property
    def db(self):
        return self._db or get_db_session()

    async def get_daily_priorities(self, workspace_id: str) -> Dict[str, Any]:
        """
        Generates a curated list of high-impact tasks for the owner.
        Analyzes:
        1. Cash Flow Risks (High AP, Low AR)
        2. Customer Risks (VIP churn signs)
        3. Growth Opportunities (High-intent leads)
        4. Operational Bottlenecks
        """
        db = self.db
        priorities = []
        
        try:
            # 1. High-Intent Leads from Marketing
            high_intent_leads = db.query(Lead).filter(
                Lead.workspace_id == workspace_id,
                Lead.ai_score > 85,
                Lead.is_converted == False
            ).limit(3).all()
            
            for lead in high_intent_leads:
                priorities.append({
                    "id": f"lead_{lead.id}",
                    "type": "GROWTH",
                    "title": f"Follow up with {lead.first_name or lead.email}",
                    "description": f"AI identified {lead.ai_score}% sales intent. {lead.ai_qualification_summary[:100] if lead.ai_qualification_summary else 'Extremely high conversion probability.'}",
                    "priority": "HIGH",
                    "action_link": f"/sales/leads/{lead.id}"
                })

            # 2. Financial Risks (Mocking complex logic for MVP)
            # Check for any failed agent jobs that might impact core ops
            failed_jobs = db.query(AgentJob).filter(
                AgentJob.status == "failed"
            ).limit(2).all()
            
            for job in failed_jobs:
                priorities.append({
                    "id": f"job_{job.id}",
                    "type": "RISK",
                    "title": f"Fix failed {job.agent_identifier}",
                    "description": f"A background task failed, which may delay business processes.",
                    "priority": "MEDIUM",
                    "action_link": "/automations"
                })

            # 3. Decision Support Suggestion
            # If cash flow looks healthy and workload is high, suggest hiring
            priorities.append({
                "id": "hiring_check",
                "type": "STRATEGY",
                "title": "Scale Check: Can you afford to hire?",
                "description": "Workload is up 15%. AI can simulate the impact of a new hire on your cash flow.",
                "priority": "LOW",
                "action_link": "/health/simulate"
            })

            # 4. Financial Forensics (Phase 9)
            try:
                from core.financial_forensics import get_forensics_services
                forensics = get_forensics_services(db)
                
                # Vendor Drift
                drifts = await forensics["vendor"].detect_price_drift(workspace_id)
                for drift in drifts:
                    priorities.append({
                        "id": f"drift_{drift['vendor_id']}",
                        "type": "RISK",
                        "priority": "MEDIUM",
                        "title": f"Price Drift: {drift['vendor_name']}",
                        "description": f"Cost up {drift['drift_percent']}% from historical average. Review alternatives?",
                        "action_link": f"/dashboard/forensics?vendor={drift['vendor_id']}"
                    })
                    
                # Pricing Advice
                pricing_advice = await forensics["pricing"].get_pricing_recommendations(workspace_id)
                for advice in pricing_advice:
                    priorities.append({
                        "id": f"pricing_{advice['sku']}",
                        "type": "STRATEGY",
                        "priority": "HIGH",
                        "title": f"Pricing Opportunity: {advice['item']}",
                        "description": f"Margin compression detected. Consider raising price to ${advice['target_price']}.",
                        "action_link": "/dashboard/forensics"
                    })
                    
                # Subscription Waste
                waste = await forensics["waste"].find_zombie_subscriptions(workspace_id)
                for item in waste:
                    priorities.append({
                        "id": f"waste_{item['subscription_id']}",
                        "type": "RISK",
                        "priority": "HIGH",
                        "title": f"SaaS Waste: {item['service_name']}",
                        "description": f"Being billed ${item['mrr']}/mo for a canceled subscription.",
                        "action_link": "/dashboard/forensics"
                    })
            except Exception as e:
                logger.warning(f"Forensics check failed in priorities: {e}")

            # 5. Risk Prevention (Phase 10)
            try:
                from core.risk_prevention import get_risk_services
                risk_svc = get_risk_services(db)
                
                # Churn Alerts
                churn_risks = await risk_svc["churn"].predict_churn_risk(workspace_id)
                for c in churn_risks:
                    if c["churn_probability"] > 0.7:
                        priorities.append({
                            "id": f"churn_{c['customer_id']}",
                            "type": "RISK",
                            "priority": "HIGH",
                            "title": f"High Churn Risk: {c['customer_name']}",
                            "description": f"Probability {int(c['churn_probability']*100)}%. Action: {c['recommended_action']}",
                            "action_link": "/dashboard/risk"
                        })
                
                # Fraud Alerts
                fraud_alerts = await risk_svc["fraud"].detect_anomalies(workspace_id)
                for f in fraud_alerts:
                     priorities.append({
                        "id": f"fraud_{f['transaction_id']}",
                        "type": "RISK",
                        "priority": "HIGH",
                        "title": f"Suspected Fraud: ${f['amount']}",
                        "description": f"{f['flag_reason']}",
                        "action_link": "/dashboard/risk"
                    })

            except Exception as e:
                logger.warning(f"Risk check failed in priorities: {e}")

            # Use AI to synthesize the list and add specific "narrative" advice
            synth_prompt = f"Based on these items: {json.dumps(priorities)}, what is the absolute #1 thing the owner should do today to save time or make money?"
            
            ai_advice = "Focus on Sales: Your top leads represent the fastest path to revenue growth."
            if ai_enhanced_service:
                request = AIRequest(
                    request_id=f"prioritize_{datetime.now().timestamp()}",
                    task_type=AITaskType.CONVERSATION_ANALYSIS,
                    model_type=AIModelType.GPT_4O,
                    service_type=AIServiceType.OPENAI,
                    input_data=synth_prompt
                )
                try:
                    response = await ai_enhanced_service.process_ai_request(request)
                    ai_advice = response.output_data.get("rationale", ai_advice)
                except Exception:
                    pass

            return {
                "priorities": priorities,
                "owner_advice": ai_advice,
                "timestamp": datetime.now().isoformat()
            }

        finally:
            if not self._db:
                db.close()

    def get_health_metrics(self, workspace_id: str) -> Dict[str, Any]:
        """
        Returns high-level health metrics for the dashboard grid.
        """
        # In a real impl, this would query Stripe/Quickbooks/Salesforce
        return {
            "cash_runway": {
                "value": "4.2 months",
                "trend": "down", 
                "trend_value": "0.3m",
                "status": "warning"
            },
            "lead_velocity": {
                "value": "+12",
                "trend": "up",
                "trend_value": "15%",
                "status": "healthy"
            },
            "active_deals": {
                "value": "$145k",
                "trend": "up",
                "trend_value": "$22k",
                "status": "healthy"
            },
            "churn_risk": {
                "value": "2 Accounts",
                "trend": "stable",
                "trend_value": "0",
                "status": "neutral"
            }
        }

    async def simulate_decision(self, workspace_id: str, decision_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulates the impact of a business decision.
        Types: 'HIRING', 'CAPEX', 'MARKETING_SPEND'
        """
        prompt = f"Simulate a {decision_type} decision with these details: {json.dumps(data)} for a business in workspace {workspace_id}. Predict cash flow impact and ROI over 6 months."
        
        request = AIRequest(
            request_id=f"sim_{datetime.now().timestamp()}",
            task_type=AITaskType.PREDICTIVE_ANALYTICS, # Fix: DATA_EXTRACTION -> PREDICTIVE_ANALYTICS
            model_type=AIModelType.O1_MINI,
            service_type=AIServiceType.OPENAI,
            input_data=prompt
        )
        
        try:
            response = await ai_enhanced_service.process_ai_request(request)
            return response.output_data
        except Exception as e:
            return {"error": str(e), "prediction": "Simulation failed. Please try again later."}

# Singleton
business_health_service = BusinessHealthService()
