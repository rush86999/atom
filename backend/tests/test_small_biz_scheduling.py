import asyncio
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

import accounting.models
import ecommerce.models
import marketing.models
import saas.models
import sales.models
import service_delivery.models
from accounting.models import Entity, EntityType
from service_delivery.models import Appointment, AppointmentStatus
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models
from core.database import Base
from core.models import Workspace
from core.small_biz_scheduler import SmallBizScheduler


class MockIntelService:
    def __init__(self, db_session):
        self.recorded_calls = []

    async def analyze_and_route(self, data, source):
        self.recorded_calls.append({"data": data, "source": source})
        return {"status": "success"}

class TestSmallBizScheduling(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Workspace
        self.ws = Workspace(id="w_salon", name="Best Salon")
        self.db.add(self.ws)
        
        # Setup Customer
        self.customer = Entity(
            id="c_alice", workspace_id="w_salon", name="Alice Smith", 
            email="alice@example.com", type=EntityType.CUSTOMER
        )
        self.db.add(self.customer)
        
        self.db.commit()
        
        self.intel = MockIntelService(self.db)
        self.scheduler = SmallBizScheduler(db_session=self.db, intel_service=self.intel)

    def tearDown(self):
        self.db.close()

    def test_availability_check(self):
        start = datetime.utcnow() + timedelta(hours=1)
        end = start + timedelta(hours=1)
        
        # Empty slot
        self.assertTrue(self.scheduler.check_availability("w_salon", start, end))
        
        # Create appointment
        appt = Appointment(
            workspace_id="w_salon", customer_id="c_alice",
            start_time=start, end_time=end, status=AppointmentStatus.SCHEDULED
        )
        self.db.add(appt)
        self.db.commit()
        
        # Exact overlap
        self.assertFalse(self.scheduler.check_availability("w_salon", start, end))
        
        # Partial overlap (starts during)
        self.assertFalse(self.scheduler.check_availability("w_salon", start + timedelta(minutes=30), end + timedelta(minutes=30)))
        
        # No overlap (starts after)
        self.assertTrue(self.scheduler.check_availability("w_salon", end, end + timedelta(hours=1)))

    def test_appointment_booking(self):
        start = datetime.utcnow() + timedelta(days=2)
        end = start + timedelta(hours=1)
        
        appt = self.scheduler.create_appointment(
            workspace_id="w_salon", customer_id="c_alice",
            service_id=None, start_time=start, end_time=end
        )
        
        self.assertIsNotNone(appt)
        self.assertEqual(appt.status, AppointmentStatus.SCHEDULED)
        
        # Conflict check
        appt2 = self.scheduler.create_appointment(
            workspace_id="w_salon", customer_id="c_alice",
            service_id=None, start_time=start, end_time=end
        )
        self.assertIsNone(appt2)

    def test_no_show_recovery(self):
        start = datetime.utcnow() - timedelta(hours=1)
        end = start + timedelta(hours=1)
        
        appt = Appointment(
            id="a_missed", workspace_id="w_salon", customer_id="c_alice",
            start_time=start, end_time=end, status=AppointmentStatus.SCHEDULED
        )
        self.db.add(appt)
        self.db.commit()
        
        # Run async recovery flow
        loop = asyncio.get_event_loop()
        success = loop.run_until_complete(self.scheduler.trigger_no_show_flow("a_missed"))
        
        self.assertTrue(success)
        self.assertEqual(appt.status, AppointmentStatus.NO_SHOW)
        
        # Verify intel service call
        self.assertEqual(len(self.intel.recorded_calls), 1)
        call = self.intel.recorded_calls[0]
        self.assertIn("NO-SHOW RECOVERY", call["data"]["content"])
        self.assertTrue(call["data"]["metadata"]["is_recovery"])

if __name__ == "__main__":
    unittest.main()
