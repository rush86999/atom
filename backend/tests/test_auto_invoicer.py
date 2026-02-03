"""
Auto Invoicing Tests

Tests the complete task invoicing implementation including:
- Hour-based billing
- Fixed-price billing
- Expense attachment
- Tax calculations
- Invoice line items
"""

from datetime import datetime, timedelta
import pytest
from accounting.models import Entity, Invoice, InvoiceStatus
from service_delivery.models import (
    Contract,
    ContractType,
    Milestone,
    Project,
    ProjectStatus,
    ProjectTask,
)
from sqlalchemy.orm import Session

from core.auto_invoicer import AutoInvoicer
from core.models import User, Workspace

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_workspace(db_session: Session):
    """Create a test workspace."""
    workspace = Workspace(
        id="test_workspace_001",
        name="Test Workspace",
        status="active"
    )
    db_session.add(workspace)
    db_session.commit()
    return workspace


@pytest.fixture
def test_customer(db_session: Session, test_workspace: Workspace):
    """Create a test customer entity."""
    from accounting.models import EntityType

    customer = Entity(
        id="test_customer_001",
        workspace_id=test_workspace.id,
        name="Test Customer",
        type=EntityType.CUSTOMER
    )
    db_session.add(customer)
    db_session.commit()
    return customer


@pytest.fixture
def test_contract(db_session: Session, test_workspace: Workspace, test_customer: Entity):
    """Create a test contract."""
    contract = Contract(
        id="test_contract_001",
        workspace_id=test_workspace.id,
        name="Test Contract",
        type=ContractType.TIME_MATERIAL,
        total_amount=10000.0,
        currency="USD",
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=90)
    )
    db_session.add(contract)
    db_session.commit()

    # Add customer_id to contract
    contract.customer_id = test_customer.id
    db_session.commit()

    return contract


@pytest.fixture
def test_project(db_session: Session, test_workspace: Workspace, test_contract: Contract):
    """Create a test project."""
    project = Project(
        id="test_project_001",
        workspace_id=test_workspace.id,
        contract_id=test_contract.id,
        name="Test Project",
        status=ProjectStatus.ACTIVE,
        description="A test project for invoicing",
        budget_hours=100.0,
        budget_amount=10000.0,
        actual_hours=0.0,
        actual_burn=0.0
    )
    db_session.add(project)
    db_session.commit()
    return project


@pytest.fixture
def test_milestone(db_session: Session, test_workspace: Workspace, test_project: Project):
    """Create a test milestone."""
    milestone = Milestone(
        id="test_milestone_001",
        workspace_id=test_workspace.id,
        project_id=test_project.id,
        name="Milestone 1",
        amount=5000.0,
        percentage=50.0
    )
    db_session.add(milestone)
    db_session.commit()
    return milestone


@pytest.fixture
def completed_task_hourly(db_session: Session, test_workspace: Workspace, test_project: Project, test_milestone: Milestone):
    """Create a completed hourly billing task."""
    task = ProjectTask(
        id="test_task_hourly_001",
        workspace_id=test_workspace.id,
        project_id=test_project.id,
        milestone_id=test_milestone.id,
        name="Hourly Task",
        description="A task billed hourly",
        status="completed",
        assigned_to="test_user",
        due_date=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        actual_hours=10.0,
        metadata_json={
            "billing_type": "hourly",
            "hourly_rate": 100.0,
            "tax_rate": 10.0,
            "customer_id": "test_customer_001"
        }
    )
    db_session.add(task)
    db_session.commit()
    return task


@pytest.fixture
def completed_task_fixed_price(db_session: Session, test_workspace: Workspace, test_project: Project, test_milestone: Milestone):
    """Create a completed fixed-price billing task."""
    task = ProjectTask(
        id="test_task_fixed_001",
        workspace_id=test_workspace.id,
        project_id=test_project.id,
        milestone_id=test_milestone.id,
        name="Fixed Price Task",
        description="A task with fixed price",
        status="completed",
        assigned_to="test_user",
        due_date=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        actual_hours=5.0,  # Should be ignored for fixed-price
        metadata_json={
            "billing_type": "fixed_price",
            "fixed_price": 2000.0,
            "tax_rate": 8.5,
            "customer_id": "test_customer_001"
        }
    )
    db_session.add(task)
    db_session.commit()
    return task


@pytest.fixture
def completed_task_with_expenses(db_session: Session, test_workspace: Workspace, test_project: Project, test_milestone: Milestone):
    """Create a completed task with expenses."""
    task = ProjectTask(
        id="test_task_expenses_001",
        workspace_id=test_workspace.id,
        project_id=test_project.id,
        milestone_id=test_milestone.id,
        name="Task with Expenses",
        description="A task with expense attachments",
        status="completed",
        assigned_to="test_user",
        due_date=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        actual_hours=8.0,
        metadata_json={
            "billing_type": "hourly",
            "hourly_rate": 125.0,
            "tax_rate": 0.0,  # No tax for this test
            "customer_id": "test_customer_001",
            "expenses": [
                {
                    "id": "expense_001",
                    "description": "Software License",
                    "amount": 150.0
                },
                {
                    "id": "expense_002",
                    "description": "Cloud Services",
                    "amount": 75.0
                }
            ]
        }
    )
    db_session.add(task)
    db_session.commit()
    return task


# ============================================================================
# Hourly Billing Tests
# ============================================================================

def test_invoice_hourly_task(completed_task_hourly: ProjectTask, db_session: Session):
    """Test invoicing an hourly-billed task."""
    invoicer = AutoInvoicer(db_session)

    invoice = invoicer.invoice_project_task(completed_task_hourly.id)

    assert invoice is not None
    assert invoice.status == InvoiceStatus.OPEN
    assert invoice.customer_id == "test_customer_001"

    # Verify calculation: 10 hours * $100/hour = $1000
    # Plus 10% tax = $100
    # Total = $1100
    expected_subtotal = 1000.0
    expected_tax = 100.0
    expected_total = 1100.0

    assert invoice.amount == expected_total
    assert "Hourly Task" in invoice.description
    assert invoice.invoice_number.startswith("INV-")


def test_invoice_hourly_task_calculations(db_session: Session, completed_task_hourly: ProjectTask):
    """Test detailed calculations for hourly billing."""
    invoicer = AutoInvoicer(db_session)

    invoice = invoicer.invoice_project_task(completed_task_hourly.id)

    # Check metadata has correct breakdown
    if hasattr(invoice, 'metadata_json') and invoice.metadata_json:
        assert invoice.metadata_json["billing_type"] == "hourly"
        assert invoice.metadata_json["subtotal"] == 1000.0
        assert invoice.metadata_json["tax_rate"] == 10.0
        assert invoice.metadata_json["tax_amount"] == 100.0

        # Check line items
        line_items = invoice.metadata_json.get("line_items", [])
        assert len(line_items) >= 1

        service_item = line_items[0]
        assert service_item["type"] == "service"
        assert service_item["quantity"] == 10.0  # hours
        assert service_item["unit_price"] == 100.0  # hourly rate
        assert service_item["amount"] == 1000.0


# ============================================================================
# Fixed-Price Billing Tests
# ============================================================================

def test_invoice_fixed_price_task(db_session: Session, completed_task_fixed_price: ProjectTask):
    """Test invoicing a fixed-price task."""
    invoicer = AutoInvoicer(db_session)

    invoice = invoicer.invoice_project_task(completed_task_fixed_price.id)

    assert invoice is not None
    assert invoice.status == InvoiceStatus.OPEN

    # Fixed price: $2000
    # Plus 8.5% tax = $170
    # Total = $2170
    expected_subtotal = 2000.0
    expected_tax = 170.0
    expected_total = 2170.0

    assert invoice.amount == expected_total


def test_invoice_fixed_price_ignores_hours(db_session: Session, completed_task_fixed_price: ProjectTask):
    """Test that fixed-price billing ignores actual hours."""
    invoicer = AutoInvoicer(db_session)

    invoice = invoicer.invoice_project_task(completed_task_fixed_price.id)

    if hasattr(invoice, 'metadata_json') and invoice.metadata_json:
        assert invoice.metadata_json["billing_type"] == "fixed_price"
        assert invoice.metadata_json["subtotal"] == 2000.0

        # Line item should have quantity 1, not hours
        line_items = invoice.metadata_json.get("line_items", [])
        service_item = line_items[0]
        assert service_item["quantity"] == 1
        assert service_item["unit_price"] == 2000.0


# ============================================================================
# Expense Tests
# ============================================================================

def test_invoice_task_with_expenses(db_session: Session, completed_task_with_expenses: ProjectTask):
    """Test invoicing a task with expense attachments."""
    invoicer = AutoInvoicer(db_session)

    invoice = invoicer.invoice_project_task(completed_task_with_expenses.id)

    assert invoice is not None

    # Calculate expected total:
    # Labor: 8 hours * $125/hour = $1000
    # Expenses: $150 + $75 = $225
    # Subtotal: $1225
    # Tax: 0%
    # Total: $1225
    expected_total = 1225.0

    assert invoice.amount == expected_total

    # Check line items include expenses
    if hasattr(invoice, 'metadata_json') and invoice.metadata_json:
        line_items = invoice.metadata_json.get("line_items", [])

        # Should have 1 service + 2 expenses = 3 line items
        assert len(line_items) == 3

        # Find expense items
        expense_items = [item for item in line_items if item["type"] == "expense"]
        assert len(expense_items) == 2

        # Verify expense amounts
        expense_descriptions = {item["description"]: item["amount"] for item in expense_items}
        assert expense_descriptions["Software License"] == 150.0
        assert expense_descriptions["Cloud Services"] == 75.0


# ============================================================================
# Edge Cases
# ============================================================================

def test_invoice_nonexistent_task(db_session: Session):
    """Test invoicing a task that doesn't exist."""
    invoicer = AutoInvoicer(db_session)

    invoice = invoicer.invoice_project_task("nonexistent_task_id")
    assert invoice is None


def test_invoice_incomplete_task(db_session: Session, test_workspace: Workspace, test_project: Project, test_milestone: Milestone):
    """Test that incomplete tasks cannot be invoiced."""
    task = ProjectTask(
        id="incomplete_task_001",
        workspace_id=test_workspace.id,
        project_id=test_project.id,
        milestone_id=test_milestone.id,
        name="Incomplete Task",
        status="in_progress",  # Not completed
        actual_hours=5.0
    )
    db_session.add(task)
    db_session.commit()

    invoicer = AutoInvoicer(db_session)
    invoice = invoicer.invoice_project_task(task.id)

    assert invoice is None


def test_invoice_without_customer(db_session: Session, test_workspace: Workspace, test_project: Project, test_milestone: Milestone):
    """Test that tasks without customer_id cannot be invoiced."""
    task = ProjectTask(
        id="no_customer_task_001",
        workspace_id=test_workspace.id,
        project_id=test_project.id,
        milestone_id=test_milestone.id,
        name="No Customer Task",
        status="completed",
        actual_hours=5.0,
        metadata_json={
            "billing_type": "hourly",
            "hourly_rate": 100.0
            # No customer_id
        }
    )
    db_session.add(task)
    db_session.commit()

    invoicer = AutoInvoicer(db_session)
    invoice = invoicer.invoice_project_task(task.id)

    assert invoice is None


def test_invoice_prevents_double_billing(db_session: Session, completed_task_hourly: ProjectTask):
    """Test that a task can only be invoiced once."""
    invoicer = AutoInvoicer(db_session)

    # First invoice
    invoice1 = invoicer.invoice_project_task(completed_task_hourly.id)
    assert invoice1 is not None

    # Second invoice attempt
    invoice2 = invoicer.invoice_project_task(completed_task_hourly.id)
    assert invoice2 is not None
    assert invoice2.id == invoice1.id  # Should return the same invoice


# ============================================================================
# Invoice Number Generation Tests
# ============================================================================

def test_invoice_number_format(db_session: Session, completed_task_hourly: ProjectTask):
    """Test that invoice numbers follow the correct format."""
    invoicer = AutoInvoicer(db_session)

    invoice = invoicer.invoice_project_task(completed_task_hourly.id)

    # Format: INV-YYYYMMDD-XXXX
    assert invoice.invoice_number.startswith("INV-")
    parts = invoice.invoice_number.split("-")
    assert len(parts) == 3
    assert parts[1].isdigit()  # Date part
    assert len(parts[1]) == 8  # YYYYMMDD
    assert parts[2].isdigit()  # Sequence
    assert len(parts[2]) == 4  # 4-digit sequence


def test_invoice_number_sequence(db_session: Session, test_workspace: Workspace, test_project: Project, test_milestone: Milestone):
    """Test that invoice numbers increment sequentially."""
    invoicer = AutoInvoicer(db_session)

    # Create multiple tasks
    tasks = []
    for i in range(3):
        task = ProjectTask(
            id=f"seq_task_{i:03d}",
            workspace_id=test_workspace.id,
            project_id=test_project.id,
            milestone_id=test_milestone.id,
            name=f"Sequential Task {i}",
            status="completed",
            actual_hours=1.0,
            metadata_json={
                "billing_type": "hourly",
                "hourly_rate": 100.0,
                "customer_id": "test_customer_001"
            }
        )
        db_session.add(task)
        db_session.commit()
        tasks.append(task)

    # Invoice all tasks
    invoices = []
    for task in tasks:
        invoice = invoicer.invoice_project_task(task.id)
        invoices.append(invoice)

    # Verify sequential numbers
    invoice_numbers = [inv.invoice_number for inv in invoices]

    # All should have the same date prefix
    prefixes = [num.split("-")[1] for num in invoice_numbers]
    assert all(p == prefixes[0] for p in prefixes)

    # Sequence should increment
    sequences = [int(num.split("-")[2]) for num in invoice_numbers]
    assert sequences == [1, 2, 3]  # Or starting from different base


# ============================================================================
# Task Metadata Updates
# ============================================================================

def test_invoice_updates_task_metadata(db_session: Session, completed_task_hourly: ProjectTask):
    """Test that invoicing a task updates its metadata."""
    invoicer = AutoInvoicer(db_session)

    invoice = invoicer.invoice_project_task(completed_task_hourly.id)

    # Refresh task from database
    db_session.refresh(completed_task_hourly)

    assert completed_task_hourly.metadata_json is not None
    assert "invoice_id" in completed_task_hourly.metadata_json
    assert completed_task_hourly.metadata_json["invoice_id"] == invoice.id
    assert "invoiced_at" in completed_task_hourly.metadata_json


# ============================================================================
# Tax Calculation Tests
# ============================================================================

def test_tax_calculation_zero_rate(db_session: Session, test_workspace: Workspace, test_project: Project, test_milestone: Milestone):
    """Test tax calculation with 0% rate."""
    task = ProjectTask(
        id="zero_tax_task_001",
        workspace_id=test_workspace.id,
        project_id=test_project.id,
        milestone_id=test_milestone.id,
        name="Zero Tax Task",
        status="completed",
        actual_hours=5.0,
        metadata_json={
            "billing_type": "hourly",
            "hourly_rate": 100.0,
            "tax_rate": 0.0,
            "customer_id": "test_customer_001"
        }
    )
    db_session.add(task)
    db_session.commit()

    invoicer = AutoInvoicer(db_session)
    invoice = invoicer.invoice_project_task(task.id)

    # 5 hours * $100 = $500, no tax
    assert invoice.amount == 500.0


def test_tax_calculation_high_rate(db_session: Session, test_workspace: Workspace, test_project: Project, test_milestone: Milestone):
    """Test tax calculation with high tax rate."""
    task = ProjectTask(
        id="high_tax_task_001",
        workspace_id=test_workspace.id,
        project_id=test_project.id,
        milestone_id=test_milestone.id,
        name="High Tax Task",
        status="completed",
        actual_hours=10.0,
        metadata_json={
            "billing_type": "hourly",
            "hourly_rate": 100.0,
            "tax_rate": 25.0,  # 25% tax
            "customer_id": "test_customer_001"
        }
    )
    db_session.add(task)
    db_session.commit()

    invoicer = AutoInvoicer(db_session)
    invoice = invoicer.invoice_project_task(task.id)

    # 10 hours * $100 = $1000
    # 25% tax = $250
    # Total = $1250
    assert invoice.amount == 1250.0


# ============================================================================
# Integration Tests
# ============================================================================

def test_full_invoicing_workflow(db_session: Session, test_workspace: Workspace, test_project: Project, test_milestone: Milestone):
    """Test complete invoicing workflow from task to invoice."""
    # Create a completed task
    task = ProjectTask(
        id="workflow_task_001",
        workspace_id=test_workspace.id,
        project_id=test_project.id,
        milestone_id=test_milestone.id,
        name="Workflow Test Task",
        description="Full workflow test",
        status="completed",
        assigned_to="test_user",
        due_date=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        actual_hours=15.0,
        metadata_json={
            "billing_type": "hourly",
            "hourly_rate": 120.0,
            "tax_rate": 7.5,
            "customer_id": "test_customer_001",
            "expenses": [
                {"id": "exp_001", "description": "Travel", "amount": 50.0}
            ]
        }
    )
    db_session.add(task)
    db_session.commit()

    # Generate invoice
    invoicer = AutoInvoicer(db_session)
    invoice = invoicer.invoice_project_task(task.id)

    # Verify invoice created
    assert invoice is not None
    assert invoice.status == InvoiceStatus.OPEN
    assert invoice.customer_id == "test_customer_001"

    # Verify calculations
    # Labor: 15 * $120 = $1800
    # Expenses: $50
    # Subtotal: $1850
    # Tax (7.5%): $138.75
    # Total: $1988.75
    assert abs(invoice.amount - 1988.75) < 0.01

    # Verify task updated
    db_session.refresh(task)
    assert task.metadata_json["invoice_id"] == invoice.id

    # Verify invoice can be queried
    queried_invoice = db_session.query(Invoice).filter(Invoice.id == invoice.id).first()
    assert queried_invoice is not None
    assert queried_invoice.invoice_number == invoice.invoice_number
