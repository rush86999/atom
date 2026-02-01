#!/usr/bin/env python3
"""
Tests for Project Risk Assessment
Tests the risk-based project gating logic
"""

import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service_delivery.project_service import ProjectService
from sales.models import Deal, DealStage
from service_delivery.models import ProjectStatus


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_project_risk.db"


@pytest.fixture
def db_session():
    """Create test database session"""
    from service_delivery.models import Base
    from sales.models import Base as SalesBase

    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SalesBase.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()

    yield db

    db.close()
    # Cleanup
    import os
    try:
        os.remove("./test_project_risk.db")
    except:
        pass


@pytest.fixture
def project_service(db_session):
    """Create ProjectService instance"""
    return ProjectService(db_session)


class TestLowRiskProjects:
    """Tests for low-risk project assessment"""

    def test_low_risk_small_deal(self, project_service, db_session):
        """Test that small, low-risk deals proceed normally"""
        deal = Deal(
            name="Small Deal Inc",
            value=5000,  # Low value
            risk_level="low",
            health_score=90,  # High health
            probability=100,  # Closed at 100%
            stage=DealStage.CLOSED_WON
        )
        db_session.add(deal)
        db_session.commit()

        status = project_service._assess_project_risk_and_set_status(deal)

        assert status == ProjectStatus.PENDING
        print(f"✓ Low risk small deal -> {status}")

    def test_low_risk_healthy_deal(self, project_service, db_session):
        """Test that healthy deals proceed normally"""
        deal = Deal(
            name="Healthy Customer Corp",
            value=25000,  # Medium value
            risk_level="low",
            health_score=85,
            probability=95,
            stage=DealStage.CLOSED_WON
        )
        db_session.add(deal)
        db_session.commit()

        status = project_service._assess_project_risk_and_set_status(deal)

        assert status == ProjectStatus.PENDING


class TestMediumRiskProjects:
    """Tests for medium-risk project assessment"""

    def test_medium_risk_from_deal_risk(self, project_service, db_session):
        """Test that medium deal risk level triggers monitoring"""
        deal = Deal(
            name="Medium Risk Deal",
            value=15000,
            risk_level="medium",  # Medium risk
            health_score=75,
            probability=95,
            stage=DealStage.CLOSED_WON
        )
        db_session.add(deal)
        db_session.commit()

        status = project_service._assess_project_risk_and_set_status(deal)

        # Should proceed with monitoring
        assert status == ProjectStatus.PENDING

    def test_medium_risk_from_health_score(self, project_service, db_session):
        """Test that lower health score triggers monitoring"""
        deal = Deal(
            name="Lower Health Deal",
            value=20000,
            risk_level="low",
            health_score=55,  # Lower health
            probability=90,
            stage=DealStage.CLOSED_WON
        )
        db_session.add(deal)
        db_session.commit()

        status = project_service._assess_project_risk_and_set_status(deal)

        assert status == ProjectStatus.PENDING


class TestHighRiskProjects:
    """Tests for high-risk project assessment that triggers gating"""

    def test_high_risk_paused_payment(self, project_service, db_session):
        """Test that high-risk deals are paused for payment"""
        deal = Deal(
            name="High Risk Customer",
            value=75000,  # High value
            risk_level="high",  # High risk
            health_score=40,  # Low health
            probability=80,  # Lower close probability
            stage=DealStage.CLOSED_WON
        )
        db_session.add(deal)
        db_session.commit()

        status = project_service._assess_project_risk_and_set_status(deal)

        assert status == ProjectStatus.PAUSED_PAYMENT
        print(f"✓ High risk deal -> {status}")

    def test_high_risk_very_large_deal(self, project_service, db_session):
        """Test that very large deals with some risk factors are gated"""
        deal = Deal(
            name="Large Deal with Risk",
            value=150000,  # Very large
            risk_level="medium",
            health_score=50,
            probability=85,
            stage=DealStage.CLOSED_WON
        )
        db_session.add(deal)
        db_session.commit()

        status = project_service._assess_project_risk_and_set_status(deal)

        assert status == ProjectStatus.PAUSED_PAYMENT

    def test_high_risk_low_health_high_value(self, project_service, db_session):
        """Test combination of low health and high value"""
        deal = Deal(
            name="Risky Large Deal",
            value=80000,
            risk_level="medium",
            health_score=35,  # Very low health
            probability=90,
            stage=DealStage.CLOSED_WON
        )
        db_session.add(deal)
        db_session.commit()

        status = project_service._assess_project_risk_and_set_status(deal)

        assert status == ProjectStatus.PAUSED_PAYMENT


class TestCriticalRiskProjects:
    """Tests for critical-risk projects requiring manual review"""

    def test_critical_risk_multiple_factors(self, project_service, db_session):
        """Test that multiple high-risk factors trigger ON_HOLD"""
        deal = Deal(
            name="Critical Risk Deal",
            value=120000,  # High value
            risk_level="high",  # High risk
            health_score=20,  # Very low health
            probability=60,  # Low close probability
            stage=DealStage.CLOSED_WON
        )
        db_session.add(deal)
        db_session.commit()

        status = project_service._assess_project_risk_and_set_status(deal)

        assert status == ProjectStatus.ON_HOLD
        print(f"✓ Critical risk deal -> {status}")

    def test_critical_risk_extreme_values(self, project_service, db_session):
        """Test extreme risk values"""
        deal = Deal(
            name="Extreme Risk Deal",
            value=200000,  # Very high value
            risk_level="high",
            health_score=10,  # Extremely low health
            probability=50,  # Very low probability
            stage=DealStage.CLOSED_WON
        )
        db_session.add(deal)
        db_session.commit()

        status = project_service._assess_project_risk_and_set_status(deal)

        assert status == ProjectStatus.ON_HOLD


class TestRiskScenarios:
    """Test real-world risk scenarios"""

    def test_new_customer_large_deal(self, project_service, db_session):
        """Scenario: New customer with large first deal"""
        deal = Deal(
            name="New Customer Enterprise",
            value=95000,
            risk_level="medium",  # New customer = medium risk
            health_score=60,
            probability=85,
            stage=DealStage.CLOSED_WON
        )
        db_session.add(deal)
        db_session.commit()

        status = project_service._assess_project_risk_and_set_status(deal)

        # Should be gated due to large size for new customer
        assert status == ProjectStatus.PAUSED_PAYMENT

    def test_established_customer_small_deal(self, project_service, db_session):
        """Scenario: Established customer, small deal"""
        deal = Deal(
            name="Repeat Customer Small",
            value=8000,
            risk_level="low",
            health_score=95,
            probability=100,
            stage=DealStage.CLOSED_WON
        )
        db_session.add(deal)
        db_session.commit()

        status = project_service._assess_project_risk_and_set_status(deal)

        # Should proceed normally
        assert status == ProjectStatus.PENDING

    def test_struggling_customer(self, project_service, db_session):
        """Scenario: Customer with declining engagement"""
        deal = Deal(
            name="Struggling Customer",
            value=45000,
            risk_level="high",  # Flagged as high risk
            health_score=25,  # Very poor engagement
            probability=70,  # Reluctant close
            stage=DealStage.CLOSED_WON
        )
        db_session.add(deal)
        db_session.commit()

        status = project_service._assess_project_risk_and_set_status(deal)

        # Should be paused due to multiple risk factors
        assert status in [ProjectStatus.PAUSED_PAYMENT, ProjectStatus.ON_HOLD]


class TestRiskScoreCalculation:
    """Test risk score calculation details"""

    def test_risk_factors_accumulate(self, project_service, db_session):
        """Test that multiple risk factors increase score"""
        # Each factor should add to the risk score
        deal = Deal(
            name="Accumulating Risk",
            value=60000,  # +15 points
            risk_level="medium",  # +15 points
            health_score=45,  # +10 points
            probability=85,  # +5 points
            stage=DealStage.CLOSED_WON
        )
        db_session.add(deal)
        db_session.commit()

        status = project_service._assess_project_risk_and_set_status(deal)

        # Base score: 15+15+10+5 = 45 points (MEDIUM risk)
        assert status == ProjectStatus.PENDING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
