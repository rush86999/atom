# Real QuickBooks service implementation using python-quickbooks
# This provides real implementations for QuickBooks Online API functionality

import os
import logging
from typing import Optional, List, Dict, Any
from quickbooks import QuickBooks
from quickbooks.objects.invoice import Invoice
from quickbooks.objects.bill import Bill
from quickbooks.objects.customer import Customer
from quickbooks.objects.vendor import Vendor
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes

logger = logging.getLogger(__name__)

async def get_quickbooks_client(user_id: str, db_conn_pool) -> Optional[QuickBooks]:
    """
    Get real QuickBooks client with OAuth2 credentials.
    """
    try:
        # Get credentials from environment variables
        client_id = os.environ.get("QUICKBOOKS_CLIENT_ID")
        client_secret = os.environ.get("QUICKBOOKS_CLIENT_SECRET")
        access_token = os.environ.get("QUICKBOOKS_ACCESS_TOKEN")
        refresh_token = os.environ.get("QUICKBOOKS_REFRESH_TOKEN")
        realm_id = os.environ.get("QUICKBOOKS_REALM_ID")
        environment = os.environ.get("QUICKBOOKS_ENVIRONMENT", "sandbox")

        if not all([client_id, client_secret, access_token, refresh_token, realm_id]):
            logger.error("QuickBooks credentials are not configured in environment variables.")
            return None

        # Create auth client
        auth_client = AuthClient(
            client_id=client_id,
            client_secret=client_secret,
            environment=environment,
            redirect_uri='https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl',  # Placeholder
        )

        auth_client.access_token = access_token
        auth_client.refresh_token = refresh_token

        # Create QuickBooks client
        qb_client = QuickBooks(
            auth_client=auth_client,
            refresh_token=refresh_token,
            company_id=realm_id,
        )

        logger.info(f"Successfully created QuickBooks client for user {user_id}")
        return qb_client

    except Exception as e:
        logger.error(f"Error creating QuickBooks client for user {user_id}: {e}")
        return None

async def list_invoices(client: QuickBooks) -> List[Dict[str, Any]]:
    """
    Get list of invoices from QuickBooks.
    """
    try:
        invoices = Invoice.all(qb=client)

        invoices_data = []
        for invoice in invoices:
            invoices_data.append({
                "id": invoice.Id,
                "doc_number": invoice.DocNumber,
                "customer_name": invoice.CustomerRef.name if invoice.CustomerRef else None,
                "customer_id": invoice.CustomerRef.value if invoice.CustomerRef else None,
                "total_amount": invoice.TotalAmt,
                "balance": invoice.Balance,
                "due_date": invoice.DueDate,
                "created_date": invoice.MetaData.CreateTime if invoice.MetaData else None,
                "status": invoice.EmailStatus,
                "line_items": [
                    {
                        "description": item.Description,
                        "amount": item.Amount,
                        "quantity": item.Qty,
                        "unit_price": item.UnitPrice
                    } for item in invoice.Line if hasattr(item, 'Description')
                ]
            })

        return invoices_data

    except Exception as e:
        logger.error(f"Error listing QuickBooks invoices: {e}")
        raise

async def list_bills(client: QuickBooks) -> List[Dict[str, Any]]:
    """
    Get list of bills from QuickBooks.
    """
    try:
        bills = Bill.all(qb=client)

        bills_data = []
        for bill in bills:
            bills_data.append({
                "id": bill.Id,
                "doc_number": bill.DocNumber,
                "vendor_name": bill.VendorRef.name if bill.VendorRef else None,
                "vendor_id": bill.VendorRef.value if bill.VendorRef else None,
                "total_amount": bill.TotalAmt,
                "due_date": bill.DueDate,
                "created_date": bill.MetaData.CreateTime if bill.MetaData else None,
                "status": bill.PayType,
                "line_items": [
                    {
                        "description": item.Description,
                        "amount": item.Amount,
                        "account": item.AccountBasedExpenseLineDetail.AccountRef.name
                                  if hasattr(item, 'AccountBasedExpenseLineDetail') and item.AccountBasedExpenseLineDetail
                                  else None
                    } for item in bill.Line if hasattr(item, 'Description')
                ]
            })

        return bills_data

    except Exception as e:
        logger.error(f"Error listing QuickBooks bills: {e}")
        raise

async def list_customers(client: QuickBooks) -> List[Dict[str, Any]]:
    """
    Get list of customers from QuickBooks.
    """
    try:
        customers = Customer.all(qb=client)

        customers_data = []
        for customer in customers:
            customers_data.append({
                "id": customer.Id,
                "name": customer.DisplayName,
                "email": customer.PrimaryEmailAddr.Address if customer.PrimaryEmailAddr else None,
                "phone": customer.PrimaryPhone.FreeFormNumber if customer.PrimaryPhone else None,
                "balance": customer.Balance,
                "created_date": customer.MetaData.CreateTime if customer.MetaData else None
            })

        return customers_data

    except Exception as e:
        logger.error(f"Error listing QuickBooks customers: {e}")
        raise

async def list_vendors(client: QuickBooks) -> List[Dict[str, Any]]:
    """
    Get list of vendors from QuickBooks.
    """
    try:
        vendors = Vendor.all(qb=client)

        vendors_data = []
        for vendor in vendors:
            vendors_data.append({
                "id": vendor.Id,
                "name": vendor.DisplayName,
                "email": vendor.PrimaryEmailAddr.Address if vendor.PrimaryEmailAddr else None,
                "phone": vendor.PrimaryPhone.FreeFormNumber if vendor.PrimaryPhone else None,
                "created_date": vendor.MetaData.CreateTime if vendor.MetaData else None
            })

        return vendors_data

    except Exception as e:
        logger.error(f"Error listing QuickBooks vendors: {e}")
        raise

async def get_invoice(client: QuickBooks, invoice_id: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific invoice.
    """
    try:
        invoice = Invoice.get(invoice_id, qb=client)

        return {
            "id": invoice.Id,
            "doc_number": invoice.DocNumber,
            "customer_name": invoice.CustomerRef.name if invoice.CustomerRef else None,
            "customer_id": invoice.CustomerRef.value if invoice.CustomerRef else None,
            "total_amount": invoice.TotalAmt,
            "balance": invoice.Balance,
            "due_date": invoice.DueDate,
            "created_date": invoice.MetaData.CreateTime if invoice.MetaData else None,
            "status": invoice.EmailStatus,
            "line_items": [
                {
                    "description": item.Description,
                    "amount": item.Amount,
                    "quantity": item.Qty,
                    "unit_price": item.UnitPrice
                } for item in invoice.Line if hasattr(item, 'Description')
            ],
            "payments": [
                {
                    "amount": payment.Amount,
                    "date": payment.PaymentRefNum
                } for payment in (invoice.Line if hasattr(invoice.Line, '__iter__') else [])
                if hasattr(payment, 'Amount') and hasattr(payment, 'PaymentRefNum')
            ]
        }

    except Exception as e:
        logger.error(f"Error getting QuickBooks invoice {invoice_id}: {e}")
        return None

async def get_service_status(client: QuickBooks) -> Dict[str, Any]:
    """
    Get QuickBooks service status and connectivity information.
    """
    try:
        # Test connectivity by getting company info
        company_info = client.get_company_info()

        return {
            "status": "connected",
            "message": "QuickBooks service connected successfully",
            "available": True,
            "mock_data": False,
            "company_name": company_info.CompanyName if company_info else "Unknown",
            "realm_id": client.company_id
        }

    except Exception as e:
        return {
            "status": "disconnected",
            "message": f"QuickBooks service connection failed: {str(e)}",
            "available": False,
            "mock_data": False
        }
