"""
ATOM QuickBooks Integration Routes
FastAPI routes for QuickBooks accounting and financial management
Following ATOM API patterns and conventions
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date
from loguru import logger
import asyncio

from quickbooks_service import create_quickbooks_service, QuickBooksService
from db_oauth_quickbooks import create_quickbooks_db_handler, QuickBooksOAuthToken
from auth_handler_quickbooks import QuickBooksAuthHandler

# Create router
router = APIRouter(prefix="/api/quickbooks", tags=["quickbooks"])

# Global instances
quickbooks_service = create_quickbooks_service()
db_handler = create_quickbooks_db_handler()
auth_handler = QuickBooksAuthHandler()

# Dependencies
async def get_access_token_and_realm(user_id: str) -> tuple[str, str]:
    """Get access token and realm ID for user"""
    tokens = await db_handler.get_tokens(user_id)
    if not tokens:
        raise HTTPException(status_code=401, detail="QuickBooks not authenticated for this user")
    
    if not tokens.realm_id:
        raise HTTPException(status_code=400, detail="QuickBooks realm ID not configured")
    
    # Check if token is expired and refresh if needed
    if await db_handler.is_token_expired(user_id):
        if tokens.refresh_token:
            try:
                new_tokens = await auth_handler.refresh_access_token(tokens.refresh_token)
                await db_handler.save_tokens(QuickBooksOAuthToken(
                    user_id=user_id,
                    access_token=new_tokens["access_token"],
                    refresh_token=new_tokens["refresh_token"],
                    token_type=new_tokens["token_type"],
                    expires_in=new_tokens["expires_in"],
                    realm_id=tokens.realm_id
                ))
                return new_tokens["access_token"], tokens.realm_id
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                raise HTTPException(status_code=401, detail="Token expired and refresh failed")
        else:
            raise HTTPException(status_code=401, detail="Token expired and no refresh token available")
    
    return tokens.access_token, tokens.realm_id

# Invoice management endpoints
@router.get("/invoices")
async def get_invoices(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(30, ge=1, le=100, description="Number of invoices to return"),
    customer_id: Optional[str] = Query(None, description="Customer ID filter"),
    status: Optional[str] = Query(None, description="Status filter (paid/unpaid/void)"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """Get list of invoices with optional filtering"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        # Parse dates if provided
        start_date = date.fromisoformat(date_from) if date_from else None
        end_date = date.fromisoformat(date_to) if date_to else None
        
        result = await quickbooks_service.get_invoices(
            access_token=access_token,
            realm_id=realm_id,
            limit=limit,
            customer_id=customer_id,
            status=status,
            date_from=start_date,
            date_to=end_date
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get invoices: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    user_id: str = Query(..., description="User ID")
):
    """Get specific invoice by ID"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.get_invoice(invoice_id, access_token, realm_id)
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get invoice {invoice_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/invoices")
async def create_invoice(
    invoice_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Create a new invoice"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        # Parse date if provided
        due_date = date.fromisoformat(invoice_data["due_date"]) if invoice_data.get("due_date") else None
        
        result = await quickbooks_service.create_invoice(
            access_token=access_token,
            realm_id=realm_id,
            customer_id=invoice_data["customer_id"],
            line_items=invoice_data["line_items"],
            due_date=due_date,
            memo=invoice_data.get("memo"),
            email=invoice_data.get("email")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Invoice created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create invoice: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/invoices/{invoice_id}")
async def update_invoice(
    invoice_id: str,
    update_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Update existing invoice"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        # Parse date if provided
        due_date = date.fromisoformat(update_data["due_date"]) if update_data.get("due_date") else None
        
        result = await quickbooks_service.update_invoice(
            invoice_id=invoice_id,
            access_token=access_token,
            realm_id=realm_id,
            customer_id=update_data.get("customer_id"),
            line_items=update_data.get("line_items"),
            due_date=due_date,
            memo=update_data.get("memo"),
            sync_token=update_data.get("sync_token")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Invoice updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update invoice {invoice_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/invoices/{invoice_id}")
async def delete_invoice(
    invoice_id: str,
    user_id: str = Query(..., description="User ID")
):
    """Void/delete invoice"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.delete_invoice(invoice_id, access_token, realm_id)
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Invoice deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete invoice {invoice_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Customer management endpoints
@router.get("/customers")
async def get_customers(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(30, ge=1, le=100, description="Number of customers to return"),
    name: Optional[str] = Query(None, description="Customer name filter"),
    email: Optional[str] = Query(None, description="Customer email filter"),
    phone: Optional[str] = Query(None, description="Customer phone filter")
):
    """Get list of customers with optional filtering"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.get_customers(
            access_token=access_token,
            realm_id=realm_id,
            limit=limit,
            name=name,
            email=email,
            phone=phone
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get customers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/customers/{customer_id}")
async def get_customer(
    customer_id: str,
    user_id: str = Query(..., description="User ID")
):
    """Get specific customer by ID"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.get_customer(customer_id, access_token, realm_id)
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/customers")
async def create_customer(
    customer_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Create a new customer"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.create_customer(
            access_token=access_token,
            realm_id=realm_id,
            name=customer_data["name"],
            email=customer_data.get("email"),
            phone=customer_data.get("phone"),
            address=customer_data.get("address"),
            company_name=customer_data.get("company_name")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Customer created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create customer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/customers/{customer_id}")
async def update_customer(
    customer_id: str,
    update_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Update existing customer"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.update_customer(
            customer_id=customer_id,
            access_token=access_token,
            realm_id=realm_id,
            name=update_data.get("name"),
            email=update_data.get("email"),
            phone=update_data.get("phone"),
            address=update_data.get("address"),
            sync_token=update_data.get("sync_token")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Customer updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/customers/{customer_id}")
async def delete_customer(
    customer_id: str,
    user_id: str = Query(..., description="User ID")
):
    """Delete customer (mark as inactive)"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.delete_customer(customer_id, access_token, realm_id)
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Customer deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Expense management endpoints
@router.get("/expenses")
async def get_expenses(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(30, ge=1, le=100, description="Number of expenses to return"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    account_id: Optional[str] = Query(None, description="Account ID filter"),
    vendor_id: Optional[str] = Query(None, description="Vendor ID filter")
):
    """Get list of expenses with optional filtering"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        # Parse dates if provided
        start_date = date.fromisoformat(date_from) if date_from else None
        end_date = date.fromisoformat(date_to) if date_to else None
        
        result = await quickbooks_service.get_expenses(
            access_token=access_token,
            realm_id=realm_id,
            limit=limit,
            date_from=start_date,
            date_to=end_date,
            account_id=account_id,
            vendor_id=vendor_id
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get expenses: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/expenses/{expense_id}")
async def get_expense(
    expense_id: str,
    user_id: str = Query(..., description="User ID")
):
    """Get specific expense by ID"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.get_expense(expense_id, access_token, realm_id)
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get expense {expense_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/expenses")
async def create_expense(
    expense_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Create a new expense"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        # Parse date if provided
        expense_date = date.fromisoformat(expense_data["date"]) if expense_data.get("date") else None
        
        result = await quickbooks_service.create_expense(
            access_token=access_token,
            realm_id=realm_id,
            account_id=expense_data["account_id"],
            amount=expense_data["amount"],
            description=expense_data["description"],
            vendor_id=expense_data.get("vendor_id"),
            date=expense_date,
            reference=expense_data.get("reference")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Expense created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create expense: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/expenses/{expense_id}")
async def update_expense(
    expense_id: str,
    update_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Update existing expense"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.update_expense(
            expense_id=expense_id,
            access_token=access_token,
            realm_id=realm_id,
            amount=update_data.get("amount"),
            description=update_data.get("description"),
            vendor_id=update_data.get("vendor_id"),
            account_id=update_data.get("account_id"),
            sync_token=update_data.get("sync_token")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Expense updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update expense {expense_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/expenses/{expense_id}")
async def delete_expense(
    expense_id: str,
    user_id: str = Query(..., description="User ID")
):
    """Void/delete expense"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.delete_expense(expense_id, access_token, realm_id)
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Expense deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete expense {expense_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Account management endpoints
@router.get("/accounts")
async def get_accounts(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(30, ge=1, le=100, description="Number of accounts to return"),
    account_type: Optional[str] = Query(None, description="Account type filter"),
    active_only: bool = Query(True, description="Filter active accounts only")
):
    """Get list of Chart of Accounts"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.get_accounts(
            access_token=access_token,
            realm_id=realm_id,
            limit=limit,
            account_type=account_type,
            active_only=active_only
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/accounts/{account_id}")
async def get_account(
    account_id: str,
    user_id: str = Query(..., description="User ID")
):
    """Get specific account by ID"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.get_account(account_id, access_token, realm_id)
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/accounts")
async def create_account(
    account_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Create a new account"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.create_account(
            access_token=access_token,
            realm_id=realm_id,
            name=account_data["name"],
            account_type=account_data["account_type"],
            classification=account_data.get("classification"),
            description=account_data.get("description")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Account created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create account: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vendors")
async def get_vendors(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(30, ge=1, le=100, description="Number of vendors to return"),
    name: Optional[str] = Query(None, description="Vendor name filter"),
    active_only: bool = Query(True, description="Filter active vendors only")
):
    """Get list of vendors"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.get_vendors(
            access_token=access_token,
            realm_id=realm_id,
            limit=limit,
            name=name,
            active_only=active_only
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get vendors: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vendors/{vendor_id}")
async def get_vendor(
    vendor_id: str,
    user_id: str = Query(..., description="User ID")
):
    """Get specific vendor by ID"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.get_vendor(vendor_id, access_token, realm_id)
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get vendor {vendor_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/vendors")
async def create_vendor(
    vendor_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Create a new vendor"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.create_vendor(
            access_token=access_token,
            realm_id=realm_id,
            name=vendor_data["name"],
            email=vendor_data.get("email"),
            phone=vendor_data.get("phone"),
            address=vendor_data.get("address")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Vendor created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create vendor: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Financial reporting endpoints
@router.get("/reports/profit-loss")
async def get_profit_loss_report(
    user_id: str = Query(..., description="User ID"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    summary_only: bool = Query(False, description="Return summary only")
):
    """Get Profit and Loss report"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        # Parse dates if provided
        start_date = date.fromisoformat(date_from) if date_from else None
        end_date = date.fromisoformat(date_to) if date_to else None
        
        result = await quickbooks_service.get_profit_and_loss(
            access_token=access_token,
            realm_id=realm_id,
            date_from=start_date,
            date_to=end_date,
            summary_only=summary_only
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profit and loss report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/balance-sheet")
async def get_balance_sheet_report(
    user_id: str = Query(..., description="User ID"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    summary_only: bool = Query(False, description="Return summary only")
):
    """Get Balance Sheet report"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        # Parse dates if provided
        start_date = date.fromisoformat(date_from) if date_from else None
        end_date = date.fromisoformat(date_to) if date_to else None
        
        result = await quickbooks_service.get_balance_sheet(
            access_token=access_token,
            realm_id=realm_id,
            date_from=start_date,
            date_to=end_date,
            summary_only=summary_only
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get balance sheet report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/cash-flow")
async def get_cash_flow_report(
    user_id: str = Query(..., description="User ID"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """Get Cash Flow report"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        # Parse dates if provided
        start_date = date.fromisoformat(date_from) if date_from else None
        end_date = date.fromisoformat(date_to) if date_to else None
        
        result = await quickbooks_service.get_cash_flow(
            access_token=access_token,
            realm_id=realm_id,
            date_from=start_date,
            date_to=end_date
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get cash flow report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/aging")
async def get_aging_report(
    user_id: str = Query(..., description="User ID"),
    aging_period: int = Query(30, description="Aging period in days"),
    customer_id: Optional[str] = Query(None, description="Customer ID filter")
):
    """Get Accounts Receivable Aging report"""
    try:
        access_token, realm_id = await get_access_token_and_realm(user_id)
        
        result = await quickbooks_service.get_aging_report(
            access_token=access_token,
            realm_id=realm_id,
            aging_period=aging_period,
            customer_id=customer_id
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get aging report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Authentication endpoints
@router.post("/auth/save")
async def save_auth_data(
    auth_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Save authentication data"""
    try:
        # Save tokens
        tokens_data = auth_data.get("tokens", {})
        tokens = QuickBooksOAuthToken(
            user_id=user_id,
            access_token=tokens_data.get("access_token"),
            refresh_token=tokens_data.get("refresh_token"),
            token_type=tokens_data.get("token_type", "Bearer"),
            expires_in=tokens_data.get("expires_in", 3600),
            x_refresh_token_expires_in=tokens_data.get("x_refresh_token_expires_in", 864000),
            realm_id=tokens_data.get("realm_id")
        )
        
        success = await db_handler.save_tokens(tokens)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save tokens")
        
        # Save user/company data
        company_data_dict = auth_data.get("company", {})
        from db_oauth_quickbooks import QuickBooksUserData
        company_data = QuickBooksUserData(
            user_id=user_id,
            realm_id=tokens_data.get("realm_id"),
            company_name=company_data_dict.get("company_name"),
            legal_name=company_data_dict.get("legal_name"),
            company_type=company_data_dict.get("company_type"),
            domain=company_data_dict.get("domain"),
            email=company_data_dict.get("email"),
            phone=company_data_dict.get("phone"),
            website=company_data_dict.get("website"),
            address=company_data_dict.get("address"),
            environment=tokens_data.get("environment", "sandbox")
        )
        
        await db_handler.save_user_data(company_data)
        
        return {
            "ok": True,
            "message": "Authentication data saved successfully",
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save auth data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/status")
async def get_auth_status(user_id: str = Query(..., description="User ID")):
    """Get authentication status"""
    try:
        tokens = await db_handler.get_tokens(user_id)
        user_data = await db_handler.get_user_data(user_id)
        is_expired = await db_handler.is_token_expired(user_id)
        refresh_expired = await db_handler.is_refresh_token_expired(user_id)
        
        return {
            "ok": True,
            "data": {
                "authenticated": bool(tokens) and not is_expired,
                "user": user_data,
                "tokens_exist": bool(tokens),
                "token_expired": is_expired,
                "refresh_token_expired": refresh_expired,
                "realm_configured": bool(tokens and tokens.realm_id) if tokens else False
            },
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get auth status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/auth")
async def revoke_auth(user_id: str = Query(..., description="User ID")):
    """Revoke authentication"""
    try:
        # Get tokens for revocation
        tokens = await db_handler.get_tokens(user_id)
        if tokens and tokens.access_token:
            await auth_handler.revoke_token(tokens.access_token)
        
        # Delete from database
        await db_handler.delete_tokens(user_id)
        
        return {
            "ok": True,
            "message": "Authentication revoked successfully",
            "service": "quickbooks",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to revoke auth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@router.get("/health")
async def health_check():
    """QuickBooks integration health check"""
    try:
        # Check service configuration
        config_status = bool(
            quickbooks_service.config.client_id and
            quickbooks_service.config.client_secret
        )
        
        return {
            "ok": True,
            "data": {
                "service": "quickbooks",
                "status": "healthy" if config_status else "misconfigured",
                "configured": config_status,
                "environment": quickbooks_service.config.environment,
                "database_connected": db_handler is not None,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"QuickBooks health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Export router
def register_quickbooks_routes(app):
    """Register QuickBooks API routes"""
    app.include_router(router)
    logger.info("QuickBooks API routes registered")