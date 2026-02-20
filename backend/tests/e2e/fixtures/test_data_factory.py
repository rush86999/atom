"""
Test Data Factory Module for E2E Testing

This module provides reusable factory classes for generating test data across
different domains: CRM, tasks, tickets, knowledge, canvas, and finance.

All factories use UUID v4 for unique values to avoid collisions in parallel tests.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List


class CRMContactFactory:
    """
    Factory for creating CRM contact test data.

    Supports customer contacts with email, phone, company, and status fields.
    """

    def create_contact(
        self,
        first_name: str = "Test",
        last_name: str = "User",
        email: Optional[str] = None,
        phone: str = "+15551234567",
        company: str = "Test Corp",
        status: str = "lead",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a CRM contact dictionary.

        Args:
            first_name: Contact's first name
            last_name: Contact's last name
            email: Email address (auto-generated if None)
            phone: Phone number
            company: Company name
            status: Contact status (lead, prospect, customer, churned)
            **kwargs: Additional custom fields

        Returns:
            Dictionary with contact data
        """
        if email is None:
            email = f"test.user.{uuid.uuid4()}@example.com"

        contact = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "company": company,
            "status": status,
            "source": "e2e_test",
            "created_at": datetime.utcnow().isoformat(),
        }

        contact.update(kwargs)
        return contact

    def create_contacts_batch(
        self, count: int, **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Create multiple CRM contacts.

        Args:
            count: Number of contacts to create
            **kwargs: Fields to override in all contacts

        Returns:
            List of contact dictionaries
        """
        return [self.create_contact(**kwargs) for _ in range(count)]


class TaskFactory:
    """
    Factory for creating task test data.

    Supports tasks with title, description, status, priority, and assignee.
    """

    def create_task(
        self,
        title: Optional[str] = None,
        description: str = "Test task description",
        status: str = "todo",
        priority: str = "medium",
        assignee: str = "test-user",
        due_date: Optional[datetime] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a task dictionary.

        Args:
            title: Task title (auto-generated if None)
            description: Task description
            status: Task status (todo, in_progress, done, cancelled)
            priority: Task priority (low, medium, high, urgent)
            assignee: User assigned to the task
            due_date: Task due date (None if not set)
            **kwargs: Additional custom fields

        Returns:
            Dictionary with task data
        """
        if title is None:
            title = f"Test Task {uuid.uuid4()}"

        task = {
            "title": title,
            "description": description,
            "status": status,
            "priority": priority,
            "assignee": assignee,
            "due_date": due_date.isoformat() if due_date else None,
            "created_at": datetime.utcnow().isoformat(),
        }

        task.update(kwargs)
        return task

    def create_tasks_batch(
        self, count: int, **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Create multiple tasks.

        Args:
            count: Number of tasks to create
            **kwargs: Fields to override in all tasks

        Returns:
            List of task dictionaries
        """
        return [self.create_task(**kwargs) for _ in range(count)]


class SupportTicketFactory:
    """
    Factory for creating support ticket test data.

    Supports customer support tickets with subject, description, priority, and status.
    """

    def create_ticket(
        self,
        subject: Optional[str] = None,
        description: str = "Test ticket description",
        priority: str = "normal",
        status: str = "open",
        customer_email: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a support ticket dictionary.

        Args:
            subject: Ticket subject (auto-generated if None)
            description: Ticket description
            priority: Ticket priority (low, normal, high, urgent)
            status: Ticket status (open, in_progress, resolved, closed)
            customer_email: Customer email (auto-generated if None)
            **kwargs: Additional custom fields

        Returns:
            Dictionary with ticket data
        """
        if subject is None:
            subject = f"Test Issue {uuid.uuid4()}"

        if customer_email is None:
            customer_email = f"customer.{uuid.uuid4()}@example.com"

        ticket = {
            "subject": subject,
            "description": description,
            "priority": priority,
            "status": status,
            "customer_email": customer_email,
            "created_at": datetime.utcnow().isoformat(),
        }

        ticket.update(kwargs)
        return ticket

    def create_tickets_batch(
        self, count: int, **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Create multiple support tickets.

        Args:
            count: Number of tickets to create
            **kwargs: Fields to override in all tickets

        Returns:
            List of ticket dictionaries
        """
        return [self.create_ticket(**kwargs) for _ in range(count)]


class KnowledgeDocFactory:
    """
    Factory for creating knowledge document and business fact test data.

    Supports knowledge base documents and business facts with citations.
    """

    def create_document(
        self,
        title: Optional[str] = None,
        content: str = "Test knowledge content",
        source: str = "e2e_test",
        doc_type: str = "text",
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a knowledge document dictionary.

        Args:
            title: Document title (auto-generated if None)
            content: Document content
            source: Document source
            doc_type: Document type (text, pdf, html, markdown)
            tags: Document tags
            **kwargs: Additional custom fields

        Returns:
            Dictionary with document data
        """
        if title is None:
            title = f"Test Doc {uuid.uuid4()}"

        if tags is None:
            tags = ["test", "e2e"]

        document = {
            "title": title,
            "content": content,
            "source": source,
            "doc_type": doc_type,
            "tags": tags,
            "created_at": datetime.utcnow().isoformat(),
        }

        document.update(kwargs)
        return document

    def create_business_fact(
        self,
        fact: str = "Test business fact",
        citations: Optional[List[str]] = None,
        reason: str = "For testing",
        source: str = "e2e_test",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a business fact dictionary.

        Args:
            fact: Business fact statement
            citations: List of citation sources
            reason: Reason for storing this fact
            source: Fact source
            **kwargs: Additional custom fields

        Returns:
            Dictionary with business fact data
        """
        if citations is None:
            citations = ["test/doc.pdf"]

        business_fact = {
            "fact": fact,
            "citations": citations,
            "reason": reason,
            "source": source,
            "created_at": datetime.utcnow().isoformat(),
        }

        business_fact.update(kwargs)
        return business_fact

    def create_documents_batch(
        self, count: int, **kwargs
    ) -> List[Dict[str, Any]]:
        """Create multiple knowledge documents."""
        return [self.create_document(**kwargs) for _ in range(count)]


class CanvasDataFactory:
    """
    Factory for creating canvas presentation test data.

    Supports chart and form canvas types with various configurations.
    """

    def create_chart_data(
        self,
        chart_type: str = "line",
        title: Optional[str] = None,
        labels: Optional[List[str]] = None,
        datasets: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Create chart canvas data.

        Args:
            chart_type: Chart type (line, bar, pie, doughnut)
            title: Chart title (auto-generated if None)
            labels: X-axis labels
            datasets: Chart datasets

        Returns:
            Dictionary with chart data
        """
        if title is None:
            title = f"Test Chart {uuid.uuid4()}"

        if labels is None:
            labels = ["A", "B", "C", "D", "E"]

        if datasets is None:
            datasets = [
                {
                    "label": "Dataset 1",
                    "data": [10, 20, 30, 40, 50],
                    "borderColor": "rgb(75, 192, 192)",
                }
            ]

        return {
            "type": chart_type,
            "title": title,
            "data": {
                "labels": labels,
                "datasets": datasets,
            },
        }

    def create_form_data(
        self,
        title: Optional[str] = None,
        fields: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Create form canvas data.

        Args:
            title: Form title (auto-generated if None)
            fields: Form field definitions

        Returns:
            Dictionary with form data
        """
        if title is None:
            title = f"Test Form {uuid.uuid4()}"

        if fields is None:
            fields = [
                {"name": "email", "type": "email", "label": "Email", "required": True},
                {"name": "name", "type": "text", "label": "Full Name", "required": True},
                {"name": "consent", "type": "checkbox", "label": "I agree", "required": True},
            ]

        return {
            "type": "form",
            "title": title,
            "fields": fields,
        }

    def create_canvas_batch(
        self, count: int, canvas_type: str = "chart", **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Create multiple canvas presentations.

        Args:
            count: Number of canvases to create
            canvas_type: Type of canvas (chart or form)
            **kwargs: Fields to override in all canvases

        Returns:
            List of canvas data dictionaries
        """
        if canvas_type == "chart":
            return [self.create_chart_data(**kwargs) for _ in range(count)]
        elif canvas_type == "form":
            return [self.create_form_data(**kwargs) for _ in range(count)]
        else:
            raise ValueError(f"Unknown canvas type: {canvas_type}")


class FinanceDataFactory:
    """
    Factory for creating finance-related test data.

    Supports invoices, payments, and transaction data.
    """

    def create_invoice(
        self,
        customer_id: Optional[str] = None,
        amount: float = 100.00,
        currency: str = "USD",
        description: str = "Test invoice",
        status: str = "pending",
        due_date: Optional[datetime] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create an invoice dictionary.

        Args:
            customer_id: Customer ID (auto-generated if None)
            amount: Invoice amount
            currency: Currency code (USD, EUR, GBP)
            description: Invoice description
            status: Invoice status (pending, paid, overdue, cancelled)
            due_date: Invoice due date
            **kwargs: Additional custom fields

        Returns:
            Dictionary with invoice data
        """
        if customer_id is None:
            customer_id = f"cust_{uuid.uuid4().hex[:8]}"

        if due_date is None:
            due_date = datetime.utcnow() + timedelta(days=30)

        invoice = {
            "customer_id": customer_id,
            "amount": amount,
            "currency": currency,
            "description": description,
            "status": status,
            "due_date": due_date.isoformat(),
            "created_at": datetime.utcnow().isoformat(),
        }

        invoice.update(kwargs)
        return invoice

    def create_payment(
        self,
        invoice_id: Optional[str] = None,
        amount: float = 100.00,
        currency: str = "USD",
        method: str = "credit_card",
        status: str = "completed",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a payment dictionary.

        Args:
            invoice_id: Associated invoice ID
            amount: Payment amount
            currency: Currency code
            method: Payment method (credit_card, bank_transfer, etc.)
            status: Payment status (pending, completed, failed)
            **kwargs: Additional custom fields

        Returns:
            Dictionary with payment data
        """
        if invoice_id is None:
            invoice_id = f"inv_{uuid.uuid4().hex[:8]}"

        payment = {
            "invoice_id": invoice_id,
            "amount": amount,
            "currency": currency,
            "method": method,
            "status": status,
            "created_at": datetime.utcnow().isoformat(),
        }

        payment.update(kwargs)
        return payment

    def create_invoices_batch(
        self, count: int, **kwargs
    ) -> List[Dict[str, Any]]:
        """Create multiple invoices."""
        return [self.create_invoice(**kwargs) for _ in range(count)]


# =============================================================================
# Factory Instances for Easy Import
# =============================================================================

# Singleton instances for convenience
crm_contact_factory = CRMContactFactory()
task_factory = TaskFactory()
support_ticket_factory = SupportTicketFactory()
knowledge_doc_factory = KnowledgeDocFactory()
canvas_data_factory = CanvasDataFactory()
finance_data_factory = FinanceDataFactory()
