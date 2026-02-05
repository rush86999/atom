import asyncio
from datetime import datetime, timedelta
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from integrations.microsoft365_service import microsoft365_service
from integrations.stripe_service import stripe_service
from integrations.xero_service import XeroService
from integrations.zoho_books_service import ZohoBooksService

router = APIRouter(prefix="/api/atom/finance/live", tags=["finance-live"])
logger = logging.getLogger(__name__)

# --- Data Models ---

class UnifiedTransaction(BaseModel):
    id: str
    description: str
    amount: float
    currency: str
    date: str
    status: str
    platform: str  # 'stripe', 'xero', 'quickbooks', 'zoho', 'dynamics'
    customer_name: Optional[str] = None
    url: Optional[str] = None

class FinanceStats(BaseModel):
    total_revenue: float
    pending_revenue: float
    transaction_count: int
    platform_breakdown: Dict[str, float]

class LiveFinanceResponse(BaseModel):
    ok: bool = True
    stats: FinanceStats
    transactions: List[UnifiedTransaction]
    providers: Dict[str, bool]

# --- Helper Functions ---

def map_stripe_payment(payment: Dict[str, Any]) -> UnifiedTransaction:
    amount = float(payment.get("amount", 0)) / 100.0 # Stripe is in cents
    return UnifiedTransaction(
        id=payment.get("id"),
        description=payment.get("description") or "Stripe Payment",
        amount=amount,
        currency=payment.get("currency", "usd"),
        date=datetime.fromtimestamp(payment.get("created", 0)).isoformat(),
        status=payment.get("status", "unknown"),
        platform="stripe",
        customer_name=None, # Requires extra fetch or expansion
        url=f"https://dashboard.stripe.com/payments/{payment.get('id')}"
    )

def map_xero_invoice(invoice: Dict[str, Any]) -> UnifiedTransaction:
    return UnifiedTransaction(
        id=invoice.get("InvoiceID"),
        description=f"Invoice #{invoice.get('InvoiceNumber')}",
        amount=float(invoice.get("Total", 0.0)),
        currency=invoice.get("CurrencyCode", "USD"),
        date=invoice.get("DateString", "") or datetime.now().isoformat(),
        status=invoice.get("Status", "unknown"),
        platform="xero",
        customer_name=invoice.get("Contact", {}).get("Name"),
        url=None # Would need organization ID to construct Deep Link
    )

def map_zoho_invoice(invoice: Dict[str, Any]) -> UnifiedTransaction:
    return UnifiedTransaction(
        id=invoice.get("invoice_id"),
        description=f"Invoice {invoice.get('invoice_number')}",
        amount=float(invoice.get("total", 0.0)),
        currency=invoice.get("currency_code", "USD"),
        date=invoice.get("date"),
        status=invoice.get("status"),
        customer_name=invoice.get("customer_name")
    )

def map_dynamics_invoice(invoice: Dict[str, Any]) -> UnifiedTransaction:
    # Placeholder mapping for Dynamics 365 via MS Graph trending/insights
    return UnifiedTransaction(
        id=invoice.get("id", "dynamics_invoice"),
        description=invoice.get("resourceVisualization", {}).get("title") or "Dynamics Invoice",
        amount=0.0,
        currency="USD",
        date=datetime.now().isoformat(),
        status="active",
        platform="dynamics",
        url=invoice.get("resourceReference", {}).get("webUrl")
    )

# --- Endpoints ---

@router.get("/overview", response_model=LiveFinanceResponse)
async def get_live_financial_overview(
    limit: int = 50,
):
    """
    Fetch live financial data from connected providers (Stripe, Xero)
    and aggregate into a unified view.
    """
    transactions = []
    providers_status = {"stripe": False, "xero": False, "zoho": False, "dynamics": False}

    # 1. Fetch Stripe Data
    try:
        # Check env token for now, similar to other live APIs
        stripe_token = os.getenv("STRIPE_SECRET_KEY")
        if stripe_token:
             raw_payments = stripe_service.list_payments(stripe_token, limit=limit)
             charges = raw_payments.get("data", [])
             transactions.extend([map_stripe_payment(p) for p in charges])
             providers_status["stripe"] = True
    except Exception as e:
        logger.warning(f"Failed to fetch live Stripe data: {e}")

    # 2. Fetch Xero Data
    # Fetching Xero requires a valid access_token from environment or user context
    try:
         xero_token = os.getenv("XERO_ACCESS_TOKEN")
         if not xero_token:
             logger.warning("XERO_ACCESS_TOKEN not configured, skipping Xero fetch")
         else:
             # Use xero_service to fetch invoices/transactions
             from integrations.xero_service import xero_service
             xero_invoices = xero_service.get_invoices(access_token=xero_token, limit=limit)
             transactions.extend([map_xero_invoice(i) for i in xero_invoices])
             providers_status["xero"] = True
    except Exception as e:
        logger.warning(f"Failed to fetch live Xero data: {e}")

    # 3. Fetch Zoho Books Data
    try:
        zoho_token = os.getenv("ZOHO_CRM_ACCESS_TOKEN") # Reusing token
        org_id = os.getenv("ZOHO_BOOKS_ORG_ID")
        
        if zoho_token and org_id:
            zoho = ZohoBooksService()
            # Fetching invoices as proxy for transactions
            headers = zoho._get_headers(zoho_token, org_id)
            url = f"{zoho.base_url}/invoices"
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, params={"organization_id": org_id})
                if res.status_code == 200:
                    raw_invoices = res.json().get("invoices", [])
                    transactions.extend([map_zoho_invoice(i) for i in raw_invoices])
                    providers_status["zoho"] = True
    except Exception as e:
        logger.warning(f"Failed to fetch live Zoho Books data: {e}")

    # 4. Fetch Dynamics 365 Finance Data
    try:
        ms_token = os.getenv("MICROSOFT_365_ACCESS_TOKEN")
        if ms_token:
            res = await microsoft365_service.get_dynamics_invoices(access_token=ms_token, top=limit)
            if res.get("status") == "success":
                raw_invoices = res.get("data", {}).get("value", [])
                transactions.extend([map_dynamics_invoice(i) for i in raw_invoices])
                providers_status["dynamics"] = True
    except Exception as e:
        logger.warning(f"Failed to fetch live Dynamics 365 data: {e}")

    # Calculate Stats
    total_rev = sum(t.amount for t in transactions if t.status in ['succeeded', 'paid', 'paid'])
    pending_rev = sum(t.amount for t in transactions if t.status in ['pending', 'open'])

    breakdown = {
        "stripe": sum(t.amount for t in transactions if t.platform == 'stripe'),
        "xero": sum(t.amount for t in transactions if t.platform == 'xero'),
        "zoho": sum(t.amount for t in transactions if t.platform == 'zoho'),
        "dynamics": sum(t.amount for t in transactions if t.platform == 'dynamics')
    }

    return LiveFinanceResponse(
        ok=True,
        stats=FinanceStats(
            total_revenue=total_rev,
            pending_revenue=pending_rev,
            transaction_count=len(transactions),
            platform_breakdown=breakdown
        ),
        transactions=sorted(transactions, key=lambda x: x.date, reverse=True)[:limit],
        providers=providers_status
    )
