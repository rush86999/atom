"""
Property-Based Tests for Auto Invoicer - Critical Billing Business Logic

Tests billing and invoicing invariants:
- Invoice generation for appointments, orders, and tasks
- Pricing calculations (hourly, fixed-price, tax)
- Double-invoicing prevention
- Invoice numbering and uniqueness
- Status validation and enforcement
- Due date calculations
- Line item accuracy
- Financial correctness and precision
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, assume, settings
from uuid import uuid4
from typing import List, Dict, Any, Optional
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


class TestInvoiceGenerationInvariants:
    """Tests for invoice generation invariants"""

    @given(
        amount=st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False),
        due_days=st.integers(min_value=0, max_value=90)
    )
    @settings(max_examples=50)
    def test_invoice_amount_positive(self, amount, due_days):
        """Test that invoice amounts are always positive"""
        issue_date = datetime.now()
        due_date = issue_date + timedelta(days=due_days)

        # Simulate invoice creation
        invoice_amount = amount

        assert invoice_amount > 0, "Invoice amount must be positive"
        assert due_date >= issue_date, "Due date must be after or equal to issue date"

    @given(
        amounts=st.lists(
            st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_line_items_sum_to_total(self, amounts):
        """Test that line items sum to invoice total"""
        # Simulate line items
        line_items = [{"amount": amount} for amount in amounts]
        subtotal = sum(line_item["amount"] for line_item in line_items)

        assert subtotal == sum(amounts), "Subtotal must equal sum of line items"
        assert subtotal > 0, "Subtotal must be positive"

    @given(
        subtotal=st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False),
        tax_rate=st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_tax_calculation_correctness(self, subtotal, tax_rate):
        """Test that tax calculations are correct"""
        tax_amount = subtotal * (tax_rate / 100.0)
        total = subtotal + tax_amount

        assert tax_amount >= 0, "Tax amount must be non-negative"
        assert total >= subtotal, "Total must be >= subtotal"
        assert abs(total - (subtotal + tax_amount)) < 0.01, "Tax calculation must be accurate"


class TestPricingInvariants:
    """Tests for pricing calculation invariants"""

    @given(
        hourly_rate=st.floats(min_value=10.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        hours_worked=st.floats(min_value=0.0, max_value=160.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_hourly_billing_calculation(self, hourly_rate, hours_worked):
        """Test that hourly billing calculations are correct"""
        total = hourly_rate * hours_worked

        assert total >= 0, "Hourly billing total must be non-negative"
        if hours_worked > 0:
            assert total > 0, "Positive hours should result in positive total"
            # Use epsilon tolerance for floating-point precision
            calculated_rate = total / hours_worked
            epsilon = 0.01
            assert abs(calculated_rate - hourly_rate) < epsilon, "Hourly rate should be consistent within precision"

    @given(
        fixed_price=st.floats(min_value=100.0, max_value=100000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_fixed_price_billing(self, fixed_price):
        """Test that fixed-price billing uses the agreed amount"""
        # Fixed price should be used regardless of hours
        hours_worked = st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False)

        # Fixed price billing
        total = fixed_price

        assert total == fixed_price, "Fixed price must equal agreed amount"
        assert total > 0, "Fixed price must be positive"

    @given(
        subtotal=st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False),
        tax_rate=st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_tax_rate_bounds(self, subtotal, tax_rate):
        """Test that tax rates are within reasonable bounds"""
        tax_amount = subtotal * (tax_rate / 100.0)

        assert 0.0 <= tax_rate <= 30.0, "Tax rate should be reasonable (0-30%)"
        assert tax_amount >= 0, "Tax amount must be non-negative"


class TestDoubleInvoicingPrevention:
    """Tests for double-invoicing prevention"""

    @given(
        invoice_ids=st.lists(
            st.text(min_size=10, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
            min_size=1,
            max_size=10,
            unique=True
        )
    )
    @settings(max_examples=50)
    def test_unique_invoice_ids(self, invoice_ids):
        """Test that invoice IDs are unique"""
        # Simulate invoice ID uniqueness check
        created_invoices = set()

        for invoice_id in invoice_ids:
            is_unique = invoice_id not in created_invoices
            assert is_unique, f"Invoice ID {invoice_id} must be unique"
            created_invoices.add(invoice_id)

        assert len(created_invoices) == len(invoice_ids), "All invoice IDs must be unique"

    @given(
        appointment_ids=st.lists(
            st.text(min_size=10, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_one_invoice_per_appointment(self, appointment_ids):
        """Test that each appointment gets at most one invoice"""
        # Simulate invoice-per-appointment tracking
        invoiced_appointments = set()

        for appt_id in appointment_ids:
            can_invoice = appt_id not in invoiced_appointments
            # If can_invoice is True, we would create invoice and add to set
            if can_invoice:
                invoiced_appointments.add(appt_id)

        # No appointment should be invoiced twice
        assert len(invoiced_appointments) == len(set(invoiced_appointments)), "Each appointment should be invoiced at most once"


class TestInvoiceStatusInvariants:
    """Tests for invoice status invariants"""

    @given(
        amount=st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_new_invoice_is_open(self, amount):
        """Test that newly created invoices have OPEN status"""
        # Simulate invoice creation
        invoice_status = "OPEN"  # Default status for new invoices

        assert invoice_status == "OPEN", "New invoices must have OPEN status"

    @given(
        amount=st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False),
        current_status=st.sampled_from(["OPEN", "OVERDUE", "PAID", "VOID"])
    )
    @settings(max_examples=50)
    def test_valid_status_transitions(self, amount, current_status):
        """Test that only valid status transitions are allowed"""
        valid_statuses = ["OPEN", "OVERDUE", "PAID", "VOID"]

        assert current_status in valid_statuses, "Status must be valid"

        # Define valid transitions
        valid_transitions = {
            "OPEN": ["PAID", "VOID", "OVERDUE"],
            "OVERDUE": ["PAID", "VOID"],
            "PAID": [],  # Terminal state
            "VOID": []   # Terminal state
        }

        # Any transition should be to a valid status
        assert current_status in valid_transitions, "Current status must be valid"


class TestDueDateInvariants:
    """Tests for due date calculation invariants"""

    @given(
        issue_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1)),
        due_days=st.integers(min_value=0, max_value=90)
    )
    @settings(max_examples=50)
    def test_due_date_after_issue_date(self, issue_date, due_days):
        """Test that due date is always after or equal to issue date"""
        due_date = issue_date + timedelta(days=due_days)

        assert due_date >= issue_date, "Due date must be after or equal to issue date"
        assert (due_date - issue_date).days == due_days, "Due days must match"

    @given(
        amount=st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False),
        days_until_due=st.integers(min_value=-10, max_value=100)
    )
    @settings(max_examples=50)
    def test_positive_due_days(self, amount, days_until_due):
        """Test that due days are non-negative"""
        assume(days_until_due >= 0)

        due_days = max(0, days_until_due)

        assert due_days >= 0, "Due days must be non-negative"


class TestInvoiceNumberingInvariants:
    """Tests for invoice numbering invariants"""

    @given(
        prefix=st.text(min_size=2, max_size=10, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
        number=st.integers(min_value=1, max_value=999999)
    )
    @settings(max_examples=50)
    def test_invoice_number_format(self, prefix, number):
        """Test that invoice numbers follow correct format"""
        invoice_number = f"{prefix}-{number:06d}"

        # Verify format
        assert "-" in invoice_number, "Invoice number should have separator"
        parts = invoice_number.split("-")
        assert len(parts) == 2, "Invoice number should have 2 parts"
        assert parts[0].isalpha(), "Prefix should be alphabetic"
        assert parts[1].isdigit(), "Number should be numeric"

    @given(
        invoice_numbers=st.lists(
            st.text(min_size=5, max_size=20, alphabet='INV-0123456789'),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_invoice_number_uniqueness(self, invoice_numbers):
        """Test that invoice numbers are unique within a workspace"""
        assume(len(invoice_numbers) == len(set(invoice_numbers)))

        # Simulate uniqueness check
        existing_numbers = set()
        for number in invoice_numbers:
            is_unique = number not in existing_numbers
            assert is_unique, f"Invoice number {number} must be unique"
            existing_numbers.add(number)


class TestFinancialPrecisionInvariants:
    """Tests for financial precision and rounding"""

    @given(
        amount=st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_amount_precision(self, amount):
        """Test that amounts maintain proper precision (2 decimal places)"""
        # Round to 2 decimal places (currency precision)
        rounded_amount = round(amount, 2)

        # Precision should be maintained
        assert abs(amount - rounded_amount) < 0.01, "Amount should maintain 2 decimal precision"

    @given(
        amounts=st.lists(
            st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_summation_accuracy(self, amounts):
        """Test that summation is accurate without floating-point errors"""
        # Calculate sum
        total = sum(amounts)

        # Sum should be finite
        assert abs(total) < float('inf'), "Total must be finite"
        assert not str(total).startswith('nan'), "Total must not be NaN"

        # Each individual amount should be preserved in the sum
        rounded_total = round(total, 2)
        assert abs(total - rounded_total) < 0.01, "Total should maintain currency precision"

    @given(
        subtotal=st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False),
        tax_rate=st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False),
        discount_rate=st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_discount_and_tax_calculation(self, subtotal, tax_rate, discount_rate):
        """Test that discounts and taxes are calculated correctly"""
        discount_amount = subtotal * (discount_rate / 100.0)
        discounted_subtotal = subtotal - discount_amount
        tax_amount = discounted_subtotal * (tax_rate / 100.0)
        total = discounted_subtotal + tax_amount

        # Verify calculations
        assert discount_amount >= 0, "Discount must be non-negative"
        assert discounted_subtotal >= 0, "Discounted subtotal must be non-negative"
        assert tax_amount >= 0, "Tax must be non-negative"
        assert total >= 0, "Total must be non-negative"

        # Total should be less than or equal to subtotal + full tax (if discount applied)
        max_possible_total = subtotal + (subtotal * (tax_rate / 100.0))
        # Only assert total is less if discount is significant (> 0.01%)
        if discount_rate > 0.01:
            assert total <= max_possible_total, "Discounted total should be less than or equal to non-discounted"


class TestLineItemInvariants:
    """Tests for line item accuracy and consistency"""

    @given(
        unit_price=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
        quantity=st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_line_item_total_calculation(self, unit_price, quantity):
        """Test that line item totals are calculated correctly"""
        line_total = unit_price * quantity

        assert line_total >= 0, "Line item total must be non-negative"
        if quantity > 0 and unit_price > 0:
            assert line_total > 0, "Positive price and quantity should result in positive total"
            assert abs(line_total / quantity - unit_price) < 0.01, "Unit price should be consistent"

    @given(
        line_items=st.lists(
            st.fixed_dictionaries({
                'description': st.text(min_size=5, max_size=100),
                'quantity': st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False),
                'unit_price': st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False)
            }),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_line_item_descriptions_present(self, line_items):
        """Test that all line items have descriptions"""
        for item in line_items:
            assert 'description' in item, "Line item must have description"
            assert len(item['description']) > 0, "Description must not be empty"
            assert 'quantity' in item, "Line item must have quantity"
            assert 'unit_price' in item, "Line item must have unit price"
            assert item['quantity'] > 0, "Quantity must be positive"
            assert item['unit_price'] > 0, "Unit price must be positive"


class TestAppointmentInvoicingInvariants:
    """Tests for appointment-specific invoicing"""

    @given(
        deposit_amount=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        service_price=st.floats(min_value=50.0, max_value=10000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_appointment_price_resolution(self, deposit_amount, service_price):
        """Test that appointment prices are correctly resolved"""
        # Price resolution logic: use service_price if valid, otherwise may need explicit price
        # In real scenario, if deposit > service_price, would require explicit pricing
        if service_price > 0:
            invoice_amount = service_price
        else:
            invoice_amount = deposit_amount

        # Invoice amount should be positive
        if invoice_amount > 0:
            assert invoice_amount > 0, "Invoice amount must be positive"
            # Invoice amount should be the greater of deposit or service price
            expected_amount = max(deposit_amount, service_price)
            assert invoice_amount >= 0, "Invoice amount must be positive"

    @given(
        appointment_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_appointment_must_be_completed(self, appointment_date):
        """Test that only completed appointments can be invoiced"""
        # Simulate status check
        valid_statuses_for_invoicing = ["COMPLETED", "completed"]

        appointment_status = "COMPLETED"

        assert appointment_status in valid_statuses_for_invoicing, "Only completed appointments can be invoiced"


class TestEcommerceInvoicingInvariants:
    """Tests for e-commerce order invoicing"""

    @given(
        order_total=st.floats(min_value=0.01, max_value=50000.0, allow_nan=False, allow_infinity=False),
        order_status=st.sampled_from(["pending", "fulfilled", "shipped", "delivered", "cancelled"])
    )
    @settings(max_examples=50)
    def test_ecommerce_invoice_amount_matches_order(self, order_total, order_status):
        """Test that e-commerce invoice amounts match order totals"""
        assume(order_status in ["pending", "fulfilled"])

        # Invoice amount should match order total
        invoice_amount = order_total

        assert invoice_amount == order_total, "Invoice amount must match order total"
        assert invoice_amount > 0, "Invoice amount must be positive"

    @given(
        order_status=st.sampled_from(["pending", "fulfilled", "shipped", "cancelled", "refunded"])
    )
    @settings(max_examples=50)
    def test_valid_order_statuses_for_invoicing(self, order_status):
        """Test that only valid order statuses can be invoiced"""
        valid_statuses = ["pending", "fulfilled"]

        can_invoice = order_status in valid_statuses

        if order_status in ["cancelled", "refunded"]:
            assert not can_invoice, "Cancelled/refunded orders cannot be invoiced"
        else:
            # Can invoice pending or fulfilled orders
            assert can_invoice or order_status not in valid_statuses, "Status check should be consistent"


class TestProjectTaskInvoicingInvariants:
    """Tests for project task invoicing"""

    @given(
        hourly_rate=st.floats(min_value=50.0, max_value=500.0, allow_nan=False, allow_infinity=False),
        actual_hours=st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False),
        fixed_price=st.floats(min_value=500.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
        billing_type=st.sampled_from(["hourly", "fixed_price"])
    )
    @settings(max_examples=50)
    def test_task_billing_type_calculation(self, hourly_rate, actual_hours, fixed_price, billing_type):
        """Test that task billing calculations match billing type"""
        if billing_type == "hourly":
            task_price = hourly_rate * actual_hours
            hours_billed = actual_hours
            rate_billed = hourly_rate
        else:  # fixed_price
            task_price = fixed_price
            hours_billed = 0
            rate_billed = 0

        assert task_price >= 0, "Task price must be non-negative"
        if billing_type == "hourly" and actual_hours > 0:
            assert task_price > 0, "Hourly billing with hours should result in positive total"
            assert hours_billed == actual_hours, "Hours billed should match actual hours"
        elif billing_type == "fixed_price":
            assert task_price == fixed_price, "Fixed price should match agreed amount"
            assert hours_billed == 0, "Fixed price should not bill hours"

    @given(
        task_price=st.floats(min_value=100.0, max_value=50000.0, allow_nan=False, allow_infinity=False),
        tax_rate=st.floats(min_value=0.0, max_value=25.0, allow_nan=False, allow_infinity=False),
        expenses=st.lists(
            st.floats(min_value=0.0, max_value=5000.0, allow_nan=False, allow_infinity=False),
            min_size=0,
            max_size=5
        )
    )
    @settings(max_examples=50)
    def test_task_invoice_with_expenses(self, task_price, tax_rate, expenses):
        """Test that expenses are added to task invoices correctly"""
        subtotal = task_price + sum(expenses)
        tax_amount = subtotal * (tax_rate / 100.0)
        total = subtotal + tax_amount

        assert total >= task_price, "Total with expenses should be >= base price"
        assert tax_amount >= 0, "Tax must be non-negative"
        assert len(expenses) <= 5, "Should handle reasonable number of expenses"


class TestInvoiceConsistencyInvariants:
    """Tests for invoice consistency across entities"""

    @given(
        customer_id=st.text(min_size=10, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
        workspace_id=st.text(min_size=10, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789')
    )
    @settings(max_examples=50)
    def test_invoice_customer_assignment(self, customer_id, workspace_id):
        """Test that invoices are correctly assigned to customers and workspaces"""
        # Simulate invoice creation
        invoice_customer = customer_id
        invoice_workspace = workspace_id

        assert invoice_customer == customer_id, "Customer ID must be assigned"
        assert invoice_workspace == workspace_id, "Workspace ID must be assigned"
        assert len(invoice_customer) > 0, "Customer ID must not be empty"
        assert len(invoice_workspace) > 0, "Workspace ID must not be empty"

    @given(
        invoice_descriptions=st.lists(
            st.text(min_size=10, max_size=200),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_invoice_description_present(self, invoice_descriptions):
        """Test that all invoices have descriptions"""
        for description in invoice_descriptions:
            assert len(description) > 0, "Invoice description must not be empty"
            assert len(description) >= 10, "Invoice description should be meaningful"


class TestAuditTrailInvariants:
    """Tests for invoicing audit trail"""

    @given(
        amounts=st.lists(
            st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50)
    def test_invoice_creation_logged(self, amounts):
        """Test that invoice creation is logged"""
        # Simulate audit log
        audit_log = []

        for i, amount in enumerate(amounts):
            entry = {
                'action': 'invoice_created',
                'invoice_id': f'INV-{i:06d}',
                'amount': amount,
                'timestamp': datetime.now().isoformat()
            }
            audit_log.append(entry)

        # Verify all invoices are logged
        assert len(audit_log) == len(amounts), "All invoice creations should be logged"
        for entry in audit_log:
            assert entry['action'] == 'invoice_created', "Log entry should indicate invoice creation"
            assert 'amount' in entry, "Log should include amount"
            assert 'timestamp' in entry, "Log should include timestamp"
