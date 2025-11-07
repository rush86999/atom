"""
ATOM QuickBooks Integration Service - Enhanced Version
Comprehensive QuickBooks API integration for accounting and financial management
Following ATOM integration patterns for consistency and reliability
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
from dataclasses import dataclass
import aiohttp
import logging
from loguru import logger

@dataclass
class QuickBooksConfig:
    """QuickBooks configuration class"""
    client_id: str
    client_secret: str
    redirect_uri: str
    environment: str = "sandbox"  # sandbox, production
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    realm_id: Optional[str] = None
    
    def __post_init__(self):
        if self.environment == "sandbox":
            self.api_base_url = "https://sandbox-quickbooks.api.intuit.com/v3"
        else:
            self.api_base_url = "https://quickbooks.api.intuit.com/v3"

class QuickBooksService:
    """Enhanced QuickBooks service class for API interactions"""
    
    def __init__(self, config: Optional[QuickBooksConfig] = None):
        self.config = config or self._get_config_from_env()
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=60)
        self.max_retries = 3
        
    def _get_config_from_env(self) -> QuickBooksConfig:
        """Load configuration from environment variables"""
        return QuickBooksConfig(
            client_id=os.getenv("QUICKBOOKS_CLIENT_ID", ""),
            client_secret=os.getenv("QUICKBOOKS_CLIENT_SECRET", ""),
            redirect_uri=os.getenv("QUICKBOOKS_REDIRECT_URI", ""),
            environment=os.getenv("QUICKBOOKS_ENVIRONMENT", "sandbox"),
            access_token=os.getenv("QUICKBOOKS_ACCESS_TOKEN"),
            refresh_token=os.getenv("QUICKBOOKS_REFRESH_TOKEN"),
            realm_id=os.getenv("QUICKBOOKS_REALM_ID")
        )
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if not self.session or self.session.closed:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "ATOM-QuickBooks-Integration/1.0"
            }
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=self.timeout
            )
        return self.session
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        access_token: str,
        realm_id: str,
        data: Optional[Dict] = None, 
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated request to QuickBooks API with retry logic"""
        session = await self._get_session()
        url = f"{self.config.api_base_url}/company/{realm_id}{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        for attempt in range(self.max_retries):
            try:
                async with session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=headers
                ) as response:
                    if response.status == 401:
                        raise Exception("Invalid or expired access token")
                    elif response.status == 429:
                        retry_after = int(response.headers.get('Retry-After', 5))
                        await asyncio.sleep(retry_after)
                        continue
                    elif response.status >= 400:
                        error_text = await response.text()
                        raise Exception(f"QuickBooks API error: {response.status} - {error_text}")
                    
                    if response.status == 204:  # No Content
                        return {"success": True}
                    
                    result = await response.json()
                    
                    # Handle QuickBooks API response structure
                    if "Fault" in result:
                        raise Exception(f"QuickBooks API fault: {result['Fault']}")
                    
                    return result
                    
            except aiohttp.ClientError as e:
                if attempt == self.max_retries - 1:
                    raise Exception(f"Request failed after {self.max_retries} attempts: {str(e)}")
                await asyncio.sleep(2 ** attempt)
        
        raise Exception("Request failed after all retries")

# Invoice management
    async def get_invoices(
        self, 
        access_token: str,
        realm_id: str,
        limit: int = 30,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get list of invoices with optional filtering"""
        params = {"query": f"SELECT * FROM Invoice STARTPOSITION 1 MAXRESULTS {limit}"}
        
        query_parts = []
        if customer_id:
            query_parts.append(f"CustomerRef = '{customer_id}'")
        if status:
            query_parts.append(f"Balance = {0 if status == 'paid' else '0' if status == 'void' else '1'}")
        if date_from:
            query_parts.append(f"TxnDate >= '{date_from.strftime('%Y-%m-%d')}'")
        if date_to:
            query_parts.append(f"TxnDate <= '{date_to.strftime('%Y-%m-%d')}'")
        
        if query_parts:
            params["query"] = f"SELECT * FROM Invoice WHERE {' AND '.join(query_parts)} STARTPOSITION 1 MAXRESULTS {limit}"
        
        return await self._make_request("GET", "/query", access_token, realm_id, params=params)
    
    async def get_invoice(self, invoice_id: str, access_token: str, realm_id: str) -> Dict[str, Any]:
        """Get specific invoice by ID"""
        query = f"SELECT * FROM Invoice WHERE Id = '{invoice_id}'"
        params = {"query": query}
        
        return await self._make_request("GET", "/query", access_token, realm_id, params=params)
    
    async def create_invoice(
        self, 
        access_token: str,
        realm_id: str,
        customer_id: str,
        line_items: List[Dict[str, Any]],
        due_date: Optional[date] = None,
        memo: Optional[str] = None,
        email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new invoice"""
        invoice_data = {
            "Invoice": {
                "CustomerRef": {"value": customer_id},
                "Line": line_items,
                "TxnDate": date.fromisoformat(datetime.utcnow().strftime('%Y-%m-%d')).isoformat()
            }
        }
        
        if due_date:
            invoice_data["Invoice"]["DueDate"] = due_date.isoformat()
        if memo:
            invoice_data["Invoice"]["PrivateNote"] = memo
        if email:
            invoice_data["Invoice"]["BillEmail"] = {"Address": email}
        
        return await self._make_request("POST", "/invoice", access_token, realm_id, data=invoice_data)
    
    async def update_invoice(
        self, 
        invoice_id: str,
        access_token: str,
        realm_id: str,
        customer_id: Optional[str] = None,
        line_items: Optional[List[Dict[str, Any]]] = None,
        due_date: Optional[date] = None,
        memo: Optional[str] = None,
        sync_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update existing invoice"""
        invoice_data = {
            "Invoice": {
                "Id": invoice_id,
                "sparse": "true"
            }
        }
        
        if customer_id:
            invoice_data["Invoice"]["CustomerRef"] = {"value": customer_id}
        if line_items:
            invoice_data["Invoice"]["Line"] = line_items
        if due_date:
            invoice_data["Invoice"]["DueDate"] = due_date.isoformat()
        if memo:
            invoice_data["Invoice"]["PrivateNote"] = memo
        if sync_token:
            invoice_data["Invoice"]["SyncToken"] = sync_token
        
        return await self._make_request("POST", "/invoice", access_token, realm_id, data=invoice_data)
    
    async def delete_invoice(self, invoice_id: str, access_token: str, realm_id: str) -> Dict[str, Any]:
        """Void/delete invoice"""
        return await self._make_request("POST", f"/invoice?operation=delete", access_token, realm_id, 
                                     data={"Invoice": {"Id": invoice_id, "sparse": "true"}})

# Customer management
    async def get_customers(
        self, 
        access_token: str,
        realm_id: str,
        limit: int = 30,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get list of customers with optional filtering"""
        query = f"SELECT * FROM Customer STARTPOSITION 1 MAXRESULTS {limit}"
        query_parts = []
        
        if name:
            query_parts.append(f"FullyQualifiedName LIKE '%{name}%'")
        if email:
            query_parts.append(f"PrimaryEmailAddr LIKE '%{email}%'")
        if phone:
            query_parts.append(f"PrimaryPhone LIKE '%{phone}%'")
        
        if query_parts:
            query = f"SELECT * FROM Customer WHERE {' AND '.join(query_parts)} STARTPOSITION 1 MAXRESULTS {limit}"
        
        params = {"query": query}
        return await self._make_request("GET", "/query", access_token, realm_id, params=params)
    
    async def get_customer(self, customer_id: str, access_token: str, realm_id: str) -> Dict[str, Any]:
        """Get specific customer by ID"""
        query = f"SELECT * FROM Customer WHERE Id = '{customer_id}'"
        params = {"query": query}
        
        return await self._make_request("GET", "/query", access_token, realm_id, params=params)
    
    async def create_customer(
        self, 
        access_token: str,
        realm_id: str,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[Dict[str, str]] = None,
        company_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new customer"""
        customer_data = {
            "Customer": {
                "FullyQualifiedName": name,
                "DisplayName": name
            }
        }
        
        if email:
            customer_data["Customer"]["PrimaryEmailAddr"] = {"Address": email}
        if phone:
            customer_data["Customer"]["PrimaryPhone"] = {"FreeFormNumber": phone}
        if address:
            customer_data["Customer"]["BillAddr"] = address
        if company_name:
            customer_data["Customer"]["CompanyName"] = company_name
        
        return await self._make_request("POST", "/customer", access_token, realm_id, data=customer_data)
    
    async def update_customer(
        self, 
        customer_id: str,
        access_token: str,
        realm_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[Dict[str, str]] = None,
        sync_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update existing customer"""
        customer_data = {
            "Customer": {
                "Id": customer_id,
                "sparse": "true"
            }
        }
        
        if name:
            customer_data["Customer"]["DisplayName"] = name
        if email:
            customer_data["Customer"]["PrimaryEmailAddr"] = {"Address": email}
        if phone:
            customer_data["Customer"]["PrimaryPhone"] = {"FreeFormNumber": phone}
        if address:
            customer_data["Customer"]["BillAddr"] = address
        if sync_token:
            customer_data["Customer"]["SyncToken"] = sync_token
        
        return await self._make_request("POST", "/customer", access_token, realm_id, data=customer_data)
    
    async def delete_customer(self, customer_id: str, access_token: str, realm_id: str) -> Dict[str, Any]:
        """Delete customer (mark as inactive)"""
        customer_data = {
            "Customer": {
                "Id": customer_id,
                "Active": "false",
                "sparse": "true"
            }
        }
        
        return await self._make_request("POST", "/customer", access_token, realm_id, data=customer_data)

# Expense management
    async def get_expenses(
        self, 
        access_token: str,
        realm_id: str,
        limit: int = 30,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        account_id: Optional[str] = None,
        vendor_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get list of expenses with optional filtering"""
        query_parts = []
        if date_from:
            query_parts.append(f"TxnDate >= '{date_from.strftime('%Y-%m-%d')}'")
        if date_to:
            query_parts.append(f"TxnDate <= '{date_to.strftime('%Y-%m-%d')}'")
        if account_id:
            query_parts.append(f"AccountRef = '{account_id}'")
        if vendor_id:
            query_parts.append(f"VendorRef = '{vendor_id}'")
        
        base_query = "SELECT * FROM Purchase"
        if query_parts:
            base_query = f"{base_query} WHERE {' AND '.join(query_parts)}"
        
        query = f"{base_query} STARTPOSITION 1 MAXRESULTS {limit}"
        params = {"query": query}
        
        return await self._make_request("GET", "/query", access_token, realm_id, params=params)
    
    async def get_expense(self, expense_id: str, access_token: str, realm_id: str) -> Dict[str, Any]:
        """Get specific expense by ID"""
        query = f"SELECT * FROM Purchase WHERE Id = '{expense_id}'"
        params = {"query": query}
        
        return await self._make_request("GET", "/query", access_token, realm_id, params=params)
    
    async def create_expense(
        self, 
        access_token: str,
        realm_id: str,
        account_id: str,
        amount: float,
        description: str,
        vendor_id: Optional[str] = None,
        date: Optional[date] = None,
        reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new expense"""
        expense_data = {
            "Purchase": {
                "AccountRef": {"value": account_id},
                "TotalAmt": amount,
                "Desc": description,
                "TxnDate": (date or date.fromisoformat(datetime.utcnow().strftime('%Y-%m-%d'))).isoformat()
            }
        }
        
        if vendor_id:
            expense_data["Purchase"]["VendorRef"] = {"value": vendor_id}
        if reference:
            expense_data["Purchase"]["Memo"] = reference
        
        return await self._make_request("POST", "/purchase", access_token, realm_id, data=expense_data)
    
    async def update_expense(
        self, 
        expense_id: str,
        access_token: str,
        realm_id: str,
        amount: Optional[float] = None,
        description: Optional[str] = None,
        vendor_id: Optional[str] = None,
        account_id: Optional[str] = None,
        sync_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update existing expense"""
        expense_data = {
            "Purchase": {
                "Id": expense_id,
                "sparse": "true"
            }
        }
        
        if amount:
            expense_data["Purchase"]["TotalAmt"] = amount
        if description:
            expense_data["Purchase"]["Desc"] = description
        if vendor_id:
            expense_data["Purchase"]["VendorRef"] = {"value": vendor_id}
        if account_id:
            expense_data["Purchase"]["AccountRef"] = {"value": account_id}
        if sync_token:
            expense_data["Purchase"]["SyncToken"] = sync_token
        
        return await self._make_request("POST", "/purchase", access_token, realm_id, data=expense_data)
    
    async def delete_expense(self, expense_id: str, access_token: str, realm_id: str) -> Dict[str, Any]:
        """Void/delete expense"""
        expense_data = {
            "Purchase": {
                "Id": expense_id,
                "sparse": "true"
            }
        }
        
        return await self._make_request("POST", f"/purchase?operation=delete", access_token, realm_id, data=expense_data)

# Account management
    async def get_accounts(
        self, 
        access_token: str,
        realm_id: str,
        limit: int = 30,
        account_type: Optional[str] = None,
        active_only: bool = True
    ) -> Dict[str, Any]:
        """Get list of Chart of Accounts"""
        query_parts = []
        if account_type:
            query_parts.append(f"AccountType = '{account_type}'")
        if active_only:
            query_parts.append("Active = true")
        
        base_query = "SELECT * FROM Account"
        if query_parts:
            base_query = f"{base_query} WHERE {' AND '.join(query_parts)}"
        
        query = f"{base_query} STARTPOSITION 1 MAXRESULTS {limit}"
        params = {"query": query}
        
        return await self._make_request("GET", "/query", access_token, realm_id, params=params)
    
    async def get_account(self, account_id: str, access_token: str, realm_id: str) -> Dict[str, Any]:
        """Get specific account by ID"""
        query = f"SELECT * FROM Account WHERE Id = '{account_id}'"
        params = {"query": query}
        
        return await self._make_request("GET", "/query", access_token, realm_id, params=params)
    
    async def create_account(
        self, 
        access_token: str,
        realm_id: str,
        name: str,
        account_type: str,
        classification: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new account"""
        account_data = {
            "Account": {
                "Name": name,
                "AccountType": account_type
            }
        }
        
        if classification:
            account_data["Account"]["Classification"] = classification
        if description:
            account_data["Account"]["Description"] = description
        
        return await self._make_request("POST", "/account", access_token, realm_id, data=account_data)
    
    async def get_vendors(
        self, 
        access_token: str,
        realm_id: str,
        limit: int = 30,
        name: Optional[str] = None,
        active_only: bool = True
    ) -> Dict[str, Any]:
        """Get list of vendors"""
        query_parts = []
        if name:
            query_parts.append(f"DisplayName LIKE '%{name}%'")
        if active_only:
            query_parts.append("Active = true")
        
        base_query = "SELECT * FROM Vendor"
        if query_parts:
            base_query = f"{base_query} WHERE {' AND '.join(query_parts)}"
        
        query = f"{base_query} STARTPOSITION 1 MAXRESULTS {limit}"
        params = {"query": query}
        
        return await self._make_request("GET", "/query", access_token, realm_id, params=params)
    
    async def get_vendor(self, vendor_id: str, access_token: str, realm_id: str) -> Dict[str, Any]:
        """Get specific vendor by ID"""
        query = f"SELECT * FROM Vendor WHERE Id = '{vendor_id}'"
        params = {"query": query}
        
        return await self._make_request("GET", "/query", access_token, realm_id, params=params)
    
    async def create_vendor(
        self, 
        access_token: str,
        realm_id: str,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create a new vendor"""
        vendor_data = {
            "Vendor": {
                "DisplayName": name
            }
        }
        
        if email:
            vendor_data["Vendor"]["PrimaryEmailAddr"] = {"Address": email}
        if phone:
            vendor_data["Vendor"]["PrimaryPhone"] = {"FreeFormNumber": phone}
        if address:
            vendor_data["Vendor"]["BillAddr"] = address
        
        return await self._make_request("POST", "/vendor", access_token, realm_id, data=vendor_data)
    
    # Financial reporting
    async def get_profit_and_loss(
        self, 
        access_token: str,
        realm_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        summary_only: bool = False
    ) -> Dict[str, Any]:
        """Get Profit and Loss report"""
        params = {}
        
        if date_from:
            params["start_date"] = date_from.strftime("%Y-%m-%d")
        if date_to:
            params["end_date"] = date_to.strftime("%Y-%m-%d")
        if summary_only:
            params["summarize_column_by"] = "Total"
        
        return await self._make_request("GET", "/reports/ProfitAndLoss", access_token, realm_id, params=params)
    
    async def get_balance_sheet(
        self, 
        access_token: str,
        realm_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        summary_only: bool = False
    ) -> Dict[str, Any]:
        """Get Balance Sheet report"""
        params = {}
        
        if date_from:
            params["start_date"] = date_from.strftime("%Y-%m-%d")
        if date_to:
            params["end_date"] = date_to.strftime("%Y-%m-%d")
        if summary_only:
            params["summarize_column_by"] = "Total"
        
        return await self._make_request("GET", "/reports/BalanceSheet", access_token, realm_id, params=params)
    
    async def get_cash_flow(
        self, 
        access_token: str,
        realm_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get Cash Flow report"""
        params = {}
        
        if date_from:
            params["start_date"] = date_from.strftime("%Y-%m-%d")
        if date_to:
            params["end_date"] = date_to.strftime("%Y-%m-%d")
        
        return await self._make_request("GET", "/reports/CashFlow", access_token, realm_id, params=params)
    
    async def get_aging_report(
        self, 
        access_token: str,
        realm_id: str,
        aging_period: int = 30,
        customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get Accounts Receivable Aging report"""
        params = {
            "aging_period": aging_period,
            "report_date": date.fromisoformat(datetime.utcnow().strftime('%Y-%m-%d')).isoformat()
        }
        
        if customer_id:
            params["customer_ref"] = customer_id
        
        return await self._make_request("GET", "/reports/AgedReceivables", access_token, realm_id, params=params)
    
    async def close_session(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()

# Legacy functions for backward compatibility
import os
import logging
from typing import Optional, List, Dict, Any
from loguru import logger

# Mock implementations for QuickBooks API (replace with real imports in production)
class AuthClient:
    """Mock AuthClient for QuickBooks integration"""
    def __init__(self, client_id, client_secret, redirect_uri, environment):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.environment = environment
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.realm_id: Optional[str] = None

class Scopes:
    """Mock Scopes enum for QuickBooks"""
    ACCOUNTING = "com.intuit.quickbooks.accounting"

class QuickBooks:
    """Mock QuickBooks client"""
    def __init__(self, auth_client, refresh_token, realm_id):
        self.auth_client = auth_client
        self.refresh_token = refresh_token
        self.realm_id = realm_id
        self.company_id = realm_id

    def get_invoices(self):
        """Mock method to get invoices"""
        return []

    def get_bills(self):
        """Mock method to get bills"""
        return []

class Invoice:
    """Mock Invoice object"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def all(cls, qb=None):
        return []

    def to_dict(self):
        return self.__dict__

class Bill:
    """Mock Bill object"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def all(cls, qb=None):
        return []

    def to_dict(self):
        return self.__dict__

logger = logging.getLogger(__name__)

async def get_quickbooks_client(user_id: str, db_conn_pool) -> Optional[QuickBooks]:
    # This is a placeholder. In a real application, you would fetch the user's QuickBooks credentials
    # from a secure database. For now, we'll use environment variables.
    # You'll need to create a table to store these credentials, similar to the Dropbox and Google Drive implementations.
    client_id = os.environ.get("QUICKBOOKS_CLIENT_ID")
    client_secret = os.environ.get("QUICKBOOKS_CLIENT_SECRET")
    access_token = os.environ.get("QUICKBOOKS_ACCESS_TOKEN")
    refresh_token = os.environ.get("QUICKBOOKS_REFRESH_TOKEN")
    realm_id = os.environ.get("QUICKBOOKS_REALM_ID")

    if not all([client_id, client_secret, access_token, refresh_token, realm_id]):
        logger.error("QuickBooks credentials are not configured in environment variables.")
        return None

    auth_client = AuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri='https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl',  # This is a placeholder
        environment='sandbox',  # Or 'production'
    )

    auth_client.access_token = access_token
    auth_client.refresh_token = refresh_token

    client = QuickBooks(
        auth_client=auth_client,
        refresh_token=refresh_token,
        realm_id=realm_id,
    )

    return client

async def list_invoices(client: QuickBooks) -> List[Dict[str, Any]]:
    invoices = Invoice.all(qb=client)
    return [i.to_dict() for i in invoices]

async def list_bills(client: QuickBooks) -> List[Dict[str, Any]]:
    bills = Bill.all(qb=client)
    return [b.to_dict() for b in bills]

# Utility functions for response formatting
def format_quickbooks_response(data: Any, service: str = "quickbooks") -> Dict[str, Any]:
    """Format successful QuickBooks response"""
    return {
        "ok": True,
        "data": data,
        "service": service,
        "timestamp": datetime.utcnow().isoformat()
    }

def format_quickbooks_error_response(error_msg: str, service: str = "quickbooks") -> Dict[str, Any]:
    """Format error response"""
    return {
        "ok": False,
        "error": {
            "code": "QUICKBOOKS_ERROR",
            "message": error_msg,
            "service": service
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# QuickBooks service factory
def create_quickbooks_service(config: Optional[QuickBooksConfig] = None) -> QuickBooksService:
    """Factory function to create enhanced QuickBooks service instance"""
    return QuickBooksService(config)
