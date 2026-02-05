from datetime import datetime, timedelta
import json
import logging
from typing import Any, Dict, List, Optional
from accounting.models import Entity
from service_delivery.models import Appointment, AppointmentStatus

from core.communication_intelligence import CommunicationIntelligenceService
from core.database import get_db_session
from core.models import BusinessProductService

logger = logging.getLogger(__name__)

class SmallBizScheduler:
    """
    Autonomous scheduling assistant for small businesses.
    """

    def __init__(self, db_session: Any = None, intel_service: Any = None):
        self.db = db_session
        self.intel_service = intel_service or CommunicationIntelligenceService(db_session=db_session)

    async def parse_booking_intent(self, content: str) -> Dict[str, Any]:
        """
        Uses AI to extract booking details from natural language.
        Note: In a real system, we'd call the AI service to parse 'tomorrow at 2pm'.
        For the prototype, we simulate extraction.
        """
        # Simulated extraction results
        # In production, we'd use CommunicationIntelligenceService or a specialized extractor
        return {
            "intent": "book_appointment",
            "service_type": "consultation",
            "start_time": datetime.utcnow() + timedelta(days=1, hours=2), # Mock: Tomorrow + 2h
            "duration_minutes": 60
        }

    def check_availability(self, workspace_id: str, start_time: datetime, end_time: datetime) -> bool:
        """
        Checks for overlapping appointments.
        """
        db = self.db or get_db_session()
        try:
            overlaps = (
                db.query(Appointment)
                .filter(Appointment.workspace_id == workspace_id)
                .filter(Appointment.status == AppointmentStatus.SCHEDULED)
                .filter(
                    (Appointment.start_time < end_time) & (Appointment.end_time > start_time)
                )
                .count()
            )
            return overlaps == 0
        finally:
            if not self.db:
                db.close()

    def create_appointment(self, workspace_id: str, customer_id: str, service_id: Optional[str], 
                           start_time: datetime, end_time: datetime, deposit: float = 0.0) -> Optional[Appointment]:
        """
        Finalizes an appointment booking.
        """
        db = self.db or get_db_session()
        try:
            if not self.check_availability(workspace_id, start_time, end_time):
                logger.warning(f"Conflict detected for workspace {workspace_id} at {start_time}")
                return None

            appt = Appointment(
                workspace_id=workspace_id,
                customer_id=customer_id,
                service_id=service_id,
                start_time=start_time,
                end_time=end_time,
                deposit_amount=deposit,
                status=AppointmentStatus.SCHEDULED
            )
            db.add(appt)
            db.commit()
            db.refresh(appt)
            return appt
        finally:
            if not self.db:
                db.close()

    async def trigger_no_show_flow(self, appointment_id: str) -> bool:
        """
        Handles recovery for missed appointments.
        """
        db = self.db or get_db_session()
        try:
            appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
            if not appt:
                return False

            logger.info(f"Triggering No-Show flow for Appointment {appointment_id}")
            appt.status = AppointmentStatus.NO_SHOW
            
            # Generate a "Polite but Firm" rebooking nudge
            comm_data = {
                "content": "[SYSTEM TRIGGER: NO-SHOW RECOVERY]",
                "metadata": {
                    "appointment_id": appt.id,
                    "customer_id": appt.customer_id,
                    "is_recovery": True
                },
                "app_type": "sms" # Preferred for immediate no-show recovery
            }
            
            # This triggers the suggestion/draft/send flow
            await self.intel_service.analyze_and_route(comm_data, "system")
            
            db.commit()
            return True
        finally:
            if not self.db:
                db.close()
