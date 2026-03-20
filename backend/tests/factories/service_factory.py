"""
Factory Boy factories for service delivery models.

Provides factories for:
- Contract (Service contracts)
- Project (Service projects)
- Milestone (Project milestones)
- ProjectTask (Project tasks)
- Appointment (Service appointments)
"""

import factory
from factory import fuzzy
from datetime import datetime, timedelta, timezone
from tests.factories.base import BaseFactory
from tests.factories.workspace_factory import WorkspaceFactory
from service_delivery.models import (
    Contract, Project, Milestone, ProjectTask, Appointment,
    ContractType, ProjectStatus, MilestoneStatus, BudgetStatus, AppointmentStatus
)


class ContractFactory(BaseFactory):
    """Factory for creating Contract instances (Service contracts)."""

    class Meta:
        model = Contract

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.Faker('uuid4')  # Override in tests with WorkspaceFactory
    name = factory.Faker('company')

    # Optional deal link (from sales.Deal)
    deal_id = factory.Faker('uuid4')  # Override in tests with DealFactory

    # Product service link (from core.models.BusinessProductService)
    product_service_id = factory.Faker('uuid4')

    # Contract type
    type = fuzzy.FuzzyChoice([t.value for t in ContractType])

    # Financials
    total_amount = fuzzy.FuzzyFloat(0.0, 500000.0)
    currency = "USD"

    # Date range
    start_date = factory.LazyAttribute(lambda o: datetime.now(timezone.utc) - timedelta(days=30))
    end_date = factory.LazyAttribute(lambda o: datetime.now(timezone.utc) + timedelta(days=365))

    # Metadata
    metadata_json = factory.LazyFunction(dict)


class ProjectFactory(BaseFactory):
    """Factory for creating Project instances (Service projects)."""

    class Meta:
        model = Project

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.Faker('uuid4')  # Override in tests
    name = factory.Faker('company')

    # Optional contract link
    contract_id = factory.Faker('uuid4')  # Override in tests with ContractFactory

    # Status
    status = fuzzy.FuzzyChoice([s.value for s in ProjectStatus])

    # Description
    description = factory.Faker('text', max_nb_chars=1000)

    # Budget tracking
    budget_hours = fuzzy.FuzzyFloat(0.0, 2000.0)
    actual_hours = fuzzy.FuzzyFloat(0.0, 2000.0)
    budget_amount = fuzzy.FuzzyFloat(0.0, 500000.0)
    actual_burn = fuzzy.FuzzyFloat(0.0, 500000.0)
    budget_status = fuzzy.FuzzyChoice([s.value for s in BudgetStatus])

    # Budget guardrail thresholds (application-level validation: warn < pause < block)
    warn_threshold_pct = fuzzy.FuzzyInteger(50, 89)
    pause_threshold_pct = fuzzy.FuzzyInteger(80, 98)
    block_threshold_pct = fuzzy.FuzzyInteger(90, 100)

    # Priority
    priority = factory.Iterator(['low', 'medium', 'high', 'critical'])
    project_type = factory.Iterator(['general', 'development', 'consulting', 'support'])

    # Dates
    planned_start_date = factory.LazyAttribute(lambda o: datetime.now(timezone.utc) - timedelta(days=15))
    planned_end_date = factory.LazyAttribute(lambda o: datetime.now(timezone.utc) + timedelta(days=90))
    actual_start_date = factory.LazyAttribute(lambda o: datetime.now(timezone.utc) - timedelta(days=10))
    actual_end_date = factory.LazyAttribute(lambda o: datetime.now(timezone.utc) + timedelta(days=80))

    # Risk assessment
    risk_level = factory.Iterator(['low', 'medium', 'high'])
    risk_score = fuzzy.FuzzyFloat(0.0, 100.0)
    risk_rationale = factory.Faker('text', max_nb_chars=500)

    # Metadata
    metadata_json = factory.LazyFunction(dict)


class MilestoneFactory(BaseFactory):
    """Factory for creating Milestone instances (Project milestones)."""

    class Meta:
        model = Milestone

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.Faker('uuid4')  # Override in tests
    project_id = factory.Faker('uuid4')  # Override in tests with ProjectFactory
    name = factory.Faker('sentence', nb_words=3)

    # Billing amount
    amount = fuzzy.FuzzyFloat(0.0, 100000.0)
    percentage = fuzzy.FuzzyFloat(0.0, 100.0)

    # Status
    status = fuzzy.FuzzyChoice([s.value for s in MilestoneStatus])

    # Ordering
    order = fuzzy.FuzzyInteger(0, 20)

    # Budget tracking
    actual_burn = fuzzy.FuzzyFloat(0.0, 50000.0)
    budget_status = fuzzy.FuzzyChoice([s.value for s in BudgetStatus])

    # Dates
    planned_start_date = factory.LazyAttribute(lambda o: datetime.now(timezone.utc) - timedelta(days=10))
    due_date = factory.LazyAttribute(lambda o: datetime.now(timezone.utc) + timedelta(days=30))
    completed_at = factory.Faker('date_time_this_year')

    # Invoice link
    invoice_id = factory.Faker('uuid4')

    # Metadata
    metadata_json = factory.LazyFunction(dict)


class ProjectTaskFactory(BaseFactory):
    """Factory for creating ProjectTask instances (Project tasks)."""

    class Meta:
        model = ProjectTask

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.Faker('uuid4')  # Override in tests
    project_id = factory.Faker('uuid4')  # Override in tests with ProjectFactory
    milestone_id = factory.Faker('uuid4')  # Override in tests with MilestoneFactory
    name = factory.Faker('sentence', nb_words=4)

    # Optional fields
    description = factory.Faker('text', max_nb_chars=1000)
    status = factory.Iterator(['pending', 'in_progress', 'completed', 'blocked'])

    # Assignment
    assigned_to = factory.Faker('uuid4')  # Links to User

    # Dates
    due_date = factory.LazyAttribute(lambda o: datetime.now(timezone.utc) + timedelta(days=7))
    completed_at = factory.Faker('date_time_this_year')

    # Time tracking
    actual_hours = fuzzy.FuzzyFloat(0.0, 100.0)

    # Metadata
    metadata_json = factory.LazyFunction(dict)


class AppointmentFactory(BaseFactory):
    """Factory for creating Appointment instances (Service appointments)."""

    class Meta:
        model = Appointment

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.Faker('uuid4')  # Override in tests with WorkspaceFactory
    customer_id = factory.Faker('uuid4')  # Links to accounting.Entity
    start_time = factory.LazyAttribute(lambda o: datetime.now(timezone.utc) + timedelta(days=1, hours=10))
    end_time = factory.LazyAttribute(lambda o: datetime.now(timezone.utc) + timedelta(days=1, hours=11))

    # Optional service link (from core.models.BusinessProductService)
    service_id = factory.Faker('uuid4')

    # Status
    status = fuzzy.FuzzyChoice([s.value for s in AppointmentStatus])

    # Deposit
    deposit_amount = fuzzy.FuzzyFloat(0.0, 500.0)
    is_deposit_paid = fuzzy.FuzzyChoice([True, False])

    # Notes
    notes = factory.Faker('text', max_nb_chars=1000)

    # Metadata (travel heuristics, etc.)
    metadata_json = factory.LazyFunction(dict)
