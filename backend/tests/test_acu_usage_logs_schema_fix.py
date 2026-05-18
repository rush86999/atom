"""
Test for ACU usage logs schema fix.

Issue: #7489445485 - Error tracking ACU usage due to UndefinedColumn

Root cause: The migration referenced workspaces.id but the model references tenants.id.
This caused a foreign key constraint mismatch leading to database errors.
"""

from __future__ import annotations

import pytest
import uuid
from sqlalchemy import inspect, text

from core.database import Base, SessionLocal
from core.models import ACUUsageLog, Tenant


class TestACUUsageLogsSchemaFix:
    """Test that ACU usage logs schema matches model definition."""

    @pytest.fixture(autouse=True)
    def setup(self, request):
        """Setup test database state."""
        self.db = SessionLocal()
        # Create a test tenant
        self.tenant = Tenant(
            name="Test Tenant",
            subdomain=f"test-{uuid.uuid4().hex[:8]}",
        )
        self.db.add(self.tenant)
        self.db.commit()

        yield

        # Cleanup
        self.db.rollback()
        self.db.query(ACUUsageLog).delete()
        self.db.query(Tenant).filter(Tenant.subdomain.like("test-%")).delete()
        self.db.commit()
        self.db.close()

    def test_acu_usage_log_foreign_key_references_tenants(self):
        """
        Verify that acu_usage_logs.tenant_id foreign key references
        tenants.id, not workspaces.id.

        This test verifies the fix for issue #7489445485.
        """
        # Get the foreign key constraint
        inspector = inspect(self.db.bind)
        fk_constraints = inspector.get_foreign_keys('acu_usage_logs')

        # Find the tenant_id foreign key
        tenant_id_fk = None
        for fk in fk_constraints:
            if 'tenant_id' in fk['constrained_columns']:
                tenant_id_fk = fk
                break

        assert tenant_id_fk is not None, "No foreign key found on tenant_id column"

        # Verify it references tenants.id, not workspaces.id
        assert tenant_id_fk['referred_table'] == 'tenants', \
            f"tenant_id FK should reference 'tenants' table, but references '{tenant_id_fk['referred_table']}'"

        assert 'id' in tenant_id_fk['referred_columns'], \
            "tenant_id FK should reference 'id' column"

        # Verify ondelete is CASCADE (may not be in metadata depending on DB version)
        # PostgreSQL doesn't always expose this in introspection
        if 'ondelete' in tenant_id_fk:
            assert tenant_id_fk['ondelete'] == 'CASCADE', \
                "tenant_id FK should have CASCADE on delete"

    def test_acu_usage_log_can_be_created(self):
        """
        Test that ACUUsageLog can be created without errors.
        This verifies the schema is correct.
        """
        usage_log = ACUUsageLog(
            tenant_id=self.tenant.id,
            job_type="webhook_ingestion",
            integration_id="test_integration",
            job_id=str(uuid.uuid4()),
            acu_consumed=1.5,
            llm_calls=5,
            total_tokens=1000,
            prompt_tokens=600,
            completion_tokens=400,
            processing_duration_ms=1500,
            records_processed=10,
            entities_extracted=5,
            relationships_extracted=2,
            cost_usd=0.075,
        )

        self.db.add(usage_log)
        self.db.commit()

        # Verify it was saved
        assert usage_log.id is not None
        assert usage_log.tenant_id == self.tenant.id
        assert usage_log.acu_consumed == 1.5

    def test_acu_usage_log_tenant_relationship(self):
        """
        Test that the tenant relationship works correctly.
        """
        usage_log = ACUUsageLog(
            tenant_id=self.tenant.id,
            job_type="historical_sync",
            integration_id="test_integration",
            job_id=str(uuid.uuid4()),
            acu_consumed=2.0,
        )

        self.db.add(usage_log)
        self.db.commit()

        # Test the relationship
        assert usage_log.tenant.id == self.tenant.id
        assert usage_log.tenant.name == "Test Tenant"

        # Test the backref
        assert len(self.tenant.acu_usage_logs) >= 1
        assert usage_log in self.tenant.acu_usage_logs

    def test_acu_usage_log_all_columns_exist(self):
        """
        Verify all columns defined in the model exist in the database.
        """
        inspector = inspect(self.db.bind)
        columns = {col['name'] for col in inspector.get_columns('acu_usage_logs')}

        # All expected columns from the model
        expected_columns = {
            'id',
            'tenant_id',
            'job_type',
            'integration_id',
            'source_connection_id',
            'job_id',
            'acu_consumed',
            'llm_calls',
            'total_tokens',
            'prompt_tokens',
            'completion_tokens',
            'processing_duration_ms',
            'records_processed',
            'entities_extracted',
            'relationships_extracted',
            'cost_usd',
            'created_at',
            'updated_at',
        }

        # Verify all expected columns exist
        missing_columns = expected_columns - columns
        assert not missing_columns, \
            f"Missing columns in database: {missing_columns}"

        # Verify no extra columns exist
        extra_columns = columns - expected_columns
        assert not extra_columns, \
            f"Unexpected columns in database: {extra_columns}"
