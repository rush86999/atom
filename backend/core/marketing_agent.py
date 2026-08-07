from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any, Dict, List, Optional
from ecommerce.models import EcommerceCustomer, EcommerceOrder
from service_delivery.models import Appointment, AppointmentStatus

from core.communication_intelligence import CommunicationIntelligenceService
from core.database import SessionLocal

logger = logging.getLogger(__name__)

class MarketingAgent:
    """
    Automates reputation management and local SEO for small businesses.
    """

    def __init__(self, ai_service: Any = None, db_session: Any = None):
        self.ai = ai_service
        self.db = db_session
        self.comm_intel = CommunicationIntelligenceService(ai_service=ai_service, db_session=db_session)

    async def trigger_review_request(self, customer_id: str, workspace_id: str):
        """
        Sends a review request if the customer sentiment is positive.
        """
        # get_db_session() returns a context manager, NOT a Session — use it as
        # a session crashed on the no-injected-session path. Own the session
        # only when none was injected.
        db = self.db
        owns_db = db is None
        if owns_db:
            db = SessionLocal()
        try:
            customer = db.query(EcommerceCustomer).filter(EcommerceCustomer.id == customer_id).first()
            if not customer:
                return {"status": "error", "message": "Customer not found"}

            # 1. Analyze sentiment from recent communications
            # (Simplified for prototype: assume positive unless recent churn signals detected)
            sentiment_summary = "positive" # Default for completed orders/appointments
            
            # 2. Draft specialized message
            if sentiment_summary == "positive":
                message = f"Hi {customer.id}, thanks for choosing us! We'd love to hear your feedback. Please leave us a review here: [Link]"
                logger.info(f"Drafted PUBLIC review request for {customer_id}")
            else:
                message = f"Hi {customer.id}, we'd love to hear how we can improve. Please share your feedback privately here: [Internal Link]"
                logger.info(f"Drafted PRIVATE feedback request for {customer_id}")

            return {"status": "success", "message": message, "target": "sms/email"}
        finally:
            if owns_db:
                db.close()

class RetentionEngine:
    """
    Detects rebooking cycles and triggers reactivation nudges.
    """

    def __init__(self, db_session: Any = None):
        self.db = db_session

    async def scan_for_rebooking_opportunities(self, workspace_id: str):
        """
        Identify customers who are due for a recurring service.
        """
        # Same get_db_session() context-manager trap as MarketingAgent: the
        # no-session path crashed instead of just closing a session.
        db = self.db
        owns_db = db is None
        if owns_db:
            db = SessionLocal()
        opportunities = []
        try:
            # Prototype logic: If a customer had a 'COMPLETED' appointment/order > 6 months ago 
            # and nothing since, trigger a nudge.
            six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)
            
            # Find customers with no recent activity but past activity
            # (In a real app, this would use many more signals)
            
            # For the prototype, we'll return a few mock opportunities if any exist
            logger.info(f"Scanning for rebooking opportunities in workspace {workspace_id}")
            
            return opportunities
        finally:
            if owns_db:
                db.close()
