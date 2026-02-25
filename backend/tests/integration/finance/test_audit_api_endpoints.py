"""
Financial Audit API Integration Tests - Phase 94-05

Integration tests for financial audit API endpoints.

Tests verify:
- Compliance validation endpoint (all 5 AUD requirements)
- Compliance report generation (json/summary/detailed)
- Audit trail export with hash chain verification
- Health metrics endpoint (0-100 score)
- Hash chain verification endpoint
- Gap detection endpoint

All endpoints use FinancialAuditOrchestrator for unified operations.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock
import uuid

from sqlalchemy.orm import Session

from core.models import (
    FinancialAudit, FinancialAccount, User, AgentRegistry,
    AgentExecution
)
from main_api_app import app
from core.database import get_db


# ==================== FIXTURES ====================

@pytest.fixture
def client(db_session):
    """Test client with database override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def test_user(db_session: Session):
    """Create test user."""
    user = User(
        id=str(uuid.uuid4()),
        email="api_test@example.com"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_account(db_session: Session, test_user: User):
    """Create test financial account."""
    account = FinancialAccount(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        name="API Test Account",
        balance=Decimal("1000.00"),
        account_type="checking"
    )
    db_session.add(account)
    db_session.commit()
    return account


# ==================== TEST CLASS ====================

@pytest.mark.usefixtures("db_session")
class TestFinancialAuditAPI:
    """Integration tests for financial audit API endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session, client):
        """Setup test dependencies."""
        self.db = db_session
        self.client = client

    # ========================================================================
    # Test: Compliance Validation Endpoint
    # ========================================================================

    def test_validate_compliance_endpoint(self, test_account):
        """
        Verify: GET /api/v1/financial-audit/validate returns compliance status.
        """
        # Call API
        response = self.client.get("/api/v1/financial-audit/validate")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert 'validated_at' in data
        assert 'overall_compliant' in data
        assert 'requirements' in data
        assert 'summary' in data

        # Verify all 5 AUD requirements present
        assert 'AUD-01' in data['requirements']
        assert 'AUD-02' in data['requirements']
        assert 'AUD-03' in data['requirements']
        assert 'AUD-04' in data['requirements']
        assert 'AUD-05' in data['requirements']

        # Verify each requirement has required fields
        for req_id, req_data in data['requirements'].items():
            assert 'name' in req_data
            assert 'description' in req_data
            assert 'compliant' in req_data

    def test_validate_compliance_with_account_filter(self, test_account):
        """
        Verify: Compliance validation accepts account_id filter.
        """
        response = self.client.get(
            f"/api/v1/financial-audit/validate?account_id={test_account.id}"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify account filter applied
        assert data['account_id'] == test_account.id

    def test_validate_compliance_with_time_range(self, test_account):
        """
        Verify: Compliance validation accepts time range filters.
        """
        start_time = datetime.utcnow() - timedelta(days=7)
        end_time = datetime.utcnow()

        response = self.client.get(
            f"/api/v1/financial-audit/validate"
            f"?start_time={start_time.isoformat()}"
            f"&end_time={end_time.isoformat()}"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify time range applied
        assert data['time_range']['start'] == start_time.isoformat()
        assert data['time_range']['end'] == end_time.isoformat()

    # ========================================================================
    # Test: Compliance Report Endpoint
    # ========================================================================

    def test_compliance_report_endpoint_json(self):
        """
        Verify: GET /api/v1/financial-audit/compliance returns compliance report.
        """
        response = self.client.get("/api/v1/financial-audit/compliance?format=json")

        assert response.status_code == 200
        data = response.json()

        # Verify report structure
        assert 'generated_at' in data
        assert 'report_type' in data
        assert 'format' in data
        assert 'statistics' in data
        assert 'model_coverage' in data
        assert 'compliance' in data
        assert 'recommendations' in data

        # Verify statistics
        stats = data['statistics']
        assert 'total_audits' in stats
        assert 'by_action_type' in stats
        assert 'success_rate' in stats

    def test_compliance_report_endpoint_summary(self):
        """
        Verify: Compliance report supports summary format.
        """
        response = self.client.get("/api/v1/financial-audit/compliance?format=summary")

        assert response.status_code == 200
        data = response.json()

        # Verify simplified report structure
        assert 'generated_at' in data
        assert 'overall_compliant' in data
        assert 'total_audits' in data
        assert 'compliant_requirements' in data
        assert 'total_requirements' in data
        assert 'recommendations' in data

        # Verify detailed fields not present in summary
        assert 'statistics' not in data
        assert 'model_coverage' not in data

    # ========================================================================
    # Test: Audit Trail Export Endpoint
    # ========================================================================

    def test_audit_trail_export_endpoint(self, test_account):
        """
        Verify: GET /api/v1/financial-audit/trail/{account_id} exports audit trail.
        """
        # Call API
        response = self.client.get(
            f"/api/v1/financial-audit/trail/{test_account.id}"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify export structure
        assert 'export_metadata' in data
        assert 'audit_entries' in data
        assert 'verification' in data

        # Verify metadata
        metadata = data['export_metadata']
        assert metadata['account_id'] == test_account.id
        assert metadata['total_entries'] >= 0
        assert metadata['include_hash_chains'] is True

        # Verify entries have required fields (if any exist)
        entries = data['audit_entries']
        for entry in entries:
            assert 'id' in entry
            assert 'timestamp' in entry
            assert 'sequence_number' in entry
            assert 'account_id' in entry
            assert 'action_type' in entry
            assert 'integrity' in entry  # Hash chain data
            assert 'entry_hash' in entry['integrity']

    def test_audit_trail_export_with_time_range(self, test_account):
        """
        Verify: Audit trail export accepts time range filters.
        """
        start_time = datetime.utcnow() - timedelta(days=1)
        end_time = datetime.utcnow()

        response = self.client.get(
            f"/api/v1/financial-audit/trail/{test_account.id}"
            f"?start_time={start_time.isoformat()}"
            f"&end_time={end_time.isoformat()}"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify time range in metadata
        metadata = data['export_metadata']
        assert metadata['time_range']['start'] == start_time.isoformat()
        assert metadata['time_range']['end'] == end_time.isoformat()

    def test_audit_trail_export_without_hash_chains(self, test_account):
        """
        Verify: Audit trail export can exclude hash chain data.
        """
        response = self.client.get(
            f"/api/v1/financial-audit/trail/{test_account.id}?include_hash_chains=false"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify hash chains excluded
        assert data['export_metadata']['include_hash_chains'] is False

        # Entries should not have integrity field
        for entry in data['audit_entries']:
            assert 'integrity' not in entry

    # ========================================================================
    # Test: Health Metrics Endpoint
    # ========================================================================

    def test_health_metrics_endpoint_default(self):
        """
        Verify: GET /api/v1/financial-audit/health returns health metrics.
        """
        response = self.client.get("/api/v1/financial-audit/health")

        assert response.status_code == 200
        data = response.json()

        # Verify health structure
        assert 'period_days' in data
        assert 'period_start' in data
        assert 'period_end' in data
        assert 'health_score' in data
        assert 'total_audits' in data
        assert 'success_rate' in data
        assert 'issues_detected' in data

        # Verify health score is between 0 and 100
        assert 0 <= data['health_score'] <= 100

        # Verify issues structure
        issues = data['issues_detected']
        assert 'sequence_gaps' in issues
        assert 'hash_chain_breaks' in issues
        assert 'tampered_accounts' in issues

    def test_health_metrics_endpoint_custom_days(self):
        """
        Verify: Health metrics accepts custom period.
        """
        response = self.client.get("/api/v1/financial-audit/health?days=7")

        assert response.status_code == 200
        data = response.json()

        # Verify custom period applied
        assert data['period_days'] == 7

    def test_health_metrics_days_validation(self):
        """
        Verify: Health metrics validates days parameter (1-365).
        """
        # Test invalid days (too large)
        response = self.client.get("/api/v1/financial-audit/health?days=400")

        # Should return validation error
        assert response.status_code == 422  # Unprocessable Entity

    # ========================================================================
    # Test: Hash Chain Verification Endpoint
    # ========================================================================

    def test_hash_chain_verification_endpoint(self, test_account):
        """
        Verify: GET /api/v1/financial-audit/verify/{account_id} verifies hash chains.
        """
        response = self.client.get(
            f"/api/v1/financial-audit/verify/{test_account.id}"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify verification structure
        assert 'is_valid' in data
        assert 'total_entries' in data
        assert 'break_count' in data

    def test_hash_chain_verification_with_sequence_range(self, test_account):
        """
        Verify: Hash chain verification accepts sequence range.
        """
        response = self.client.get(
            f"/api/v1/financial-audit/verify/{test_account.id}"
            f"?start_sequence=1"
            f"&end_sequence=10"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert 'is_valid' in data
        assert 'total_entries' in data

    # ========================================================================
    # Test: Gap Detection Endpoint
    # ========================================================================

    def test_gap_detection_endpoint_all_accounts(self):
        """
        Verify: GET /api/v1/financial-audit/gaps detects sequence gaps.
        """
        response = self.client.get("/api/v1/financial-audit/gaps")

        assert response.status_code == 200
        data = response.json()

        # Verify gap detection structure
        assert 'has_gaps' in data
        assert 'gaps' in data
        assert 'total_gaps' in data
        assert 'accounts_with_gaps' in data
        assert 'checked_at' in data

    def test_gap_detection_endpoint_account_filter(self, test_account):
        """
        Verify: Gap detection accepts account filter.
        """
        response = self.client.get(
            f"/api/v1/financial-audit/gaps?account_id={test_account.id}"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert 'has_gaps' in data
        assert 'gaps' in data
        assert isinstance(data['gaps'], list)

    def test_gap_detection_endpoint_with_time_range(self, test_account):
        """
        Verify: Gap detection accepts time range filters.
        """
        start_time = datetime.utcnow() - timedelta(days=7)
        end_time = datetime.utcnow()

        response = self.client.get(
            f"/api/v1/financial-audit/gaps"
            f"?account_id={test_account.id}"
            f"&start_time={start_time.isoformat()}"
            f"&end_time={end_time.isoformat()}"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert 'has_gaps' in data
        assert 'checked_at' in data

    # ========================================================================
    # Test: Error Handling
    # ========================================================================

    def test_validate_endpoint_handles_errors(self, test_account):
        """
        Verify: Compliance validation endpoint handles errors gracefully.
        """
        # This test verifies the endpoint doesn't crash on empty database
        response = self.client.get("/api/v1/financial-audit/validate")

        # Should succeed even with no data
        assert response.status_code == 200

    def test_export_endpoint_for_nonexistent_account(self):
        """
        Verify: Export endpoint handles nonexistent account.
        """
        fake_account_id = str(uuid.uuid4())

        response = self.client.get(
            f"/api/v1/financial-audit/trail/{fake_account_id}"
        )

        # Should return 200 with empty entries (not 404)
        assert response.status_code == 200
        data = response.json()

        assert data['export_metadata']['total_entries'] == 0
        assert len(data['audit_entries']) == 0
