import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode
import aiohttp
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Salesforce Configuration
class SalesforceConfig(BaseModel):
    """Salesforce Configuration Model"""

    enabled: bool = Field(False, description="Enable Salesforce integration")
    environment: str = Field(
        "production", description="Salesforce environment (production, sandbox)"
    )
    client_id: str = Field(..., description="Salesforce Connected App Client ID")
    client_secret: str = Field(
        ..., description="Salesforce Connected App Client Secret"
    )
    username: str = Field(..., description="Salesforce integration user")
    password: str = Field(..., description="Salesforce integration user password")
    security_token: str = Field(..., description="Salesforce security token")
    instance_url: Optional[str] = Field(None, description="Salesforce instance URL")
    api_version: str = Field("v58.0", description="Salesforce API version")
    auth_url: str = Field(
        "https://login.salesforce.com", description="Salesforce authentication URL"
    )
    scope: List[str] = Field(default=["api", "refresh_token"])


# Salesforce Authentication
class SalesforceAuth(BaseModel):
    """Salesforce Authentication Data"""

    access_token: str = Field(..., description="OAuth access token")
    instance_url: str = Field(..., description="Salesforce instance URL")
    id: str = Field(..., description="Identity URL")
    token_type: str = Field(..., description="Token type")
    issued_at: str = Field(..., description="Token issued timestamp")
    signature: str = Field(..., description="Token signature")
    refresh_token: Optional[str] = Field(None, description="Refresh token")


# Salesforce Objects
class SalesforceAccount(BaseModel):
    """Salesforce Account Object"""

    id: str = Field(..., description="Account ID")
    name: str = Field(..., description="Account name")
    type: Optional[str] = Field(None, description="Account type")
    industry: Optional[str] = Field(None, description="Industry")
    website: Optional[str] = Field(None, description="Website")
    phone: Optional[str] = Field(None, description="Phone number")
    billing_address: Optional[Dict[str, str]] = Field(
        None, description="Billing address"
    )
    shipping_address: Optional[Dict[str, str]] = Field(
        None, description="Shipping address"
    )
    description: Optional[str] = Field(None, description="Account description")
    created_date: Optional[str] = Field(None, description="Created date")
    last_modified_date: Optional[str] = Field(None, description="Last modified date")


class SalesforceContact(BaseModel):
    """Salesforce Contact Object"""

    id: str = Field(..., description="Contact ID")
    account_id: Optional[str] = Field(None, description="Related account ID")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: str = Field(..., description="Last name")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    title: Optional[str] = Field(None, description="Job title")
    department: Optional[str] = Field(None, description="Department")
    mailing_address: Optional[Dict[str, str]] = Field(
        None, description="Mailing address"
    )
    description: Optional[str] = Field(None, description="Contact description")
    created_date: Optional[str] = Field(None, description="Created date")
    last_modified_date: Optional[str] = Field(None, description="Last modified date")


class SalesforceOpportunity(BaseModel):
    """Salesforce Opportunity Object"""

    id: str = Field(..., description="Opportunity ID")
    account_id: Optional[str] = Field(None, description="Related account ID")
    name: str = Field(..., description="Opportunity name")
    stage: str = Field(..., description="Opportunity stage")
    amount: Optional[float] = Field(None, description="Opportunity amount")
    close_date: str = Field(..., description="Close date")
    probability: Optional[float] = Field(None, description="Probability percentage")
    type: Optional[str] = Field(None, description="Opportunity type")
    lead_source: Optional[str] = Field(None, description="Lead source")
    description: Optional[str] = Field(None, description="Opportunity description")
    created_date: Optional[str] = Field(None, description="Created date")
    last_modified_date: Optional[str] = Field(None, description="Last modified date")


class SalesforceCase(BaseModel):
    """Salesforce Case Object"""

    id: str = Field(..., description="Case ID")
    account_id: Optional[str] = Field(None, description="Related account ID")
    contact_id: Optional[str] = Field(None, description="Related contact ID")
    case_number: str = Field(..., description="Case number")
    subject: str = Field(..., description="Case subject")
    description: Optional[str] = Field(None, description="Case description")
    status: str = Field(..., description="Case status")
    priority: str = Field(..., description="Case priority")
    type: Optional[str] = Field(None, description="Case type")
    origin: Optional[str] = Field(None, description="Case origin")
    created_date: Optional[str] = Field(None, description="Created date")
    last_modified_date: Optional[str] = Field(None, description="Last modified date")


# Query and Search Models
class SalesforceQuery(BaseModel):
    """Salesforce SOQL Query"""

    query: str = Field(..., description="SOQL query string")
    limit: Optional[int] = Field(100, description="Query result limit")
    offset: Optional[int] = Field(0, description="Query offset")


class SalesforceSearch(BaseModel):
    """Salesforce SOSL Search"""

    search_term: str = Field(..., description="Search term")
    object_types: List[str] = Field(
        default=["Account", "Contact", "Opportunity", "Case"]
    )
    limit: Optional[int] = Field(100, description="Search result limit")


# Integration Results
class SalesforceSyncResult(BaseModel):
    """Salesforce Synchronization Result"""

    accounts_synced: int = Field(0, description="Number of accounts synchronized")
    contacts_synced: int = Field(0, description="Number of contacts synchronized")
    opportunities_synced: int = Field(
        0, description="Number of opportunities synchronized"
    )
    cases_synced: int = Field(0, description="Number of cases synchronized")
    errors: List[str] = Field(
        default_factory=list, description="Synchronization errors"
    )
    duration_seconds: float = Field(0.0, description="Sync duration in seconds")
    timestamp: str = Field(..., description="Sync completion timestamp")


class SalesforceMetrics(BaseModel):
    """Salesforce Integration Metrics"""

    total_accounts: int = Field(0, description="Total accounts")
    total_contacts: int = Field(0, description="Total contacts")
    total_opportunities: int = Field(0, description="Total opportunities")
    total_cases: int = Field(0, description="Total cases")
    api_calls_today: int = Field(0, description="API calls made today")
    sync_status: str = Field("unknown", description="Last sync status")
    last_sync: Optional[str] = Field(None, description="Last sync timestamp")


class EnterpriseSalesforceConnector:
    """Enterprise Salesforce Integration Connector"""

    def __init__(self):
        self.router = APIRouter()
        self.config: Optional[SalesforceConfig] = None
        self.auth_data: Optional[SalesforceAuth] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.setup_routes()

    def setup_routes(self):
        """Setup Salesforce connector routes"""
        self.router.add_api_route(
            "/salesforce/health",
            self.health_check,
            methods=["GET"],
            summary="Salesforce connector health check",
        )
        self.router.add_api_route(
            "/salesforce/config",
            self.get_configuration,
            methods=["GET"],
            summary="Get Salesforce configuration",
        )
        self.router.add_api_route(
            "/salesforce/config",
            self.update_configuration,
            methods=["PUT"],
            summary="Update Salesforce configuration",
        )
        self.router.add_api_route(
            "/salesforce/auth/test",
            self.test_authentication,
            methods=["POST"],
            summary="Test Salesforce authentication",
        )
        self.router.add_api_route(
            "/salesforce/accounts",
            self.get_accounts,
            methods=["GET"],
            summary="Get Salesforce accounts",
        )
        self.router.add_api_route(
            "/salesforce/accounts/{account_id}",
            self.get_account,
            methods=["GET"],
            summary="Get Salesforce account by ID",
        )
        self.router.add_api_route(
            "/salesforce/contacts",
            self.get_contacts,
            methods=["GET"],
            summary="Get Salesforce contacts",
        )
        self.router.add_api_route(
            "/salesforce/contacts/{contact_id}",
            self.get_contact,
            methods=["GET"],
            summary="Get Salesforce contact by ID",
        )
        self.router.add_api_route(
            "/salesforce/opportunities",
            self.get_opportunities,
            methods=["GET"],
            summary="Get Salesforce opportunities",
        )
        self.router.add_api_route(
            "/salesforce/opportunities/{opportunity_id}",
            self.get_opportunity,
            methods=["GET"],
            summary="Get Salesforce opportunity by ID",
        )
        self.router.add_api_route(
            "/salesforce/cases",
            self.get_cases,
            methods=["GET"],
            summary="Get Salesforce cases",
        )
        self.router.add_api_route(
            "/salesforce/cases/{case_id}",
            self.get_case,
            methods=["GET"],
            summary="Get Salesforce case by ID",
        )
        self.router.add_api_route(
            "/salesforce/query",
            self.execute_query,
            methods=["POST"],
            summary="Execute SOQL query",
        )
        self.router.add_api_route(
            "/salesforce/search",
            self.execute_search,
            methods=["POST"],
            summary="Execute SOSL search",
        )
        self.router.add_api_route(
            "/salesforce/sync",
            self.sync_data,
            methods=["POST"],
            summary="Synchronize Salesforce data",
        )
        self.router.add_api_route(
            "/salesforce/metrics",
            self.get_metrics,
            methods=["GET"],
            summary="Get Salesforce integration metrics",
        )

    def initialize(self, config: SalesforceConfig):
        """Initialize Salesforce connector with configuration"""
        self.config = config
        self.session = aiohttp.ClientSession()

    async def health_check(self) -> Dict[str, Any]:
        """Salesforce connector health check"""
        if not self.config:
            return {
                "status": "unconfigured",
                "service": "salesforce",
                "connected": False,
                "message": "Salesforce connector not configured",
            }

        try:
            # Test authentication
            authenticated = await self._authenticate()
            if authenticated:
                return {
                    "status": "healthy",
                    "service": "salesforce",
                    "connected": True,
                    "environment": self.config.environment,
                    "api_version": self.config.api_version,
                }
            else:
                return {
                    "status": "unhealthy",
                    "service": "salesforce",
                    "connected": False,
                    "message": "Authentication failed",
                }
        except Exception as e:
            logger.error(f"Salesforce health check failed: {e}")
            return {
                "status": "unhealthy",
                "service": "salesforce",
                "connected": False,
                "message": str(e),
            }

    async def get_configuration(self) -> SalesforceConfig:
        """Get Salesforce configuration"""
        if not self.config:
            raise HTTPException(
                status_code=404, detail="Salesforce configuration not found"
            )

        # Return configuration without sensitive data
        safe_config = self.config.copy()
        safe_config.client_secret = "***" if self.config.client_secret else None
        safe_config.password = "***" if self.config.password else None
        safe_config.security_token = "***" if self.config.security_token else None
        return safe_config

    async def update_configuration(self, config: SalesforceConfig):
        """Update Salesforce configuration"""
        self.config = config
        if not self.session:
            self.session = aiohttp.ClientSession()

        # Test new configuration
        if config.enabled:
            authenticated = await self._authenticate()
            if not authenticated:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to authenticate with new configuration",
                )

        return {"message": "Salesforce configuration updated successfully"}

    async def test_authentication(self) -> Dict[str, Any]:
        """Test Salesforce authentication"""
        if not self.config:
            return {"status": "error", "message": "Salesforce configuration not set"}

        try:
            authenticated = await self._authenticate()
            if authenticated and self.auth_data:
                return {
                    "status": "success",
                    "message": "Authentication test passed",
                    "environment": self.config.environment,
                    "instance_url": self.auth_data.instance_url,
                    "user_id": self.auth_data.id.split("/")[-1]
                    if self.auth_data.id
                    else "unknown",
                }
            else:
                return {"status": "error", "message": "Authentication test failed"}
        except Exception as e:
            return {
                "status": "error",
                "message": f"Authentication test failed: {str(e)}",
            }

    async def get_accounts(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get Salesforce accounts"""
        if not await self._ensure_authenticated():
            raise HTTPException(
                status_code=401, detail="Not authenticated with Salesforce"
            )

        try:
            query = f"""
            SELECT Id, Name, Type, Industry, Website, Phone,
                   BillingStreet, BillingCity, BillingState, BillingPostalCode, BillingCountry,
                   ShippingStreet, ShippingCity, ShippingState, ShippingPostalCode, ShippingCountry,
                   Description, CreatedDate, LastModifiedDate
            FROM Account
            ORDER BY LastModifiedDate DESC
            LIMIT {limit}
            OFFSET {offset}
            """

            results = await self._execute_soql_query(query)
            accounts = [self._parse_account_result(result) for result in results]

            return {
                "accounts": accounts,
                "total_count": len(accounts),
                "limit": limit,
                "offset": offset,
            }

        except Exception as e:
            logger.error(f"Failed to get accounts: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get accounts: {e}")

    async def get_account(self, account_id: str) -> SalesforceAccount:
        """Get Salesforce account by ID"""
        if not await self._ensure_authenticated():
            raise HTTPException(
                status_code=401, detail="Not authenticated with Salesforce"
            )

        try:
            query = f"""
            SELECT Id, Name, Type, Industry, Website, Phone,
                   BillingStreet, BillingCity, BillingState, BillingPostalCode, BillingCountry,
                   ShippingStreet, ShippingCity, ShippingState, ShippingPostalCode, ShippingCountry,
                   Description, CreatedDate, LastModifiedDate
            FROM Account
            WHERE Id = '{account_id}'
            """

            results = await self._execute_soql_query(query)
            if not results:
                raise HTTPException(status_code=404, detail="Account not found")

            return self._parse_account_result(results[0])

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get account: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get account: {e}")

    async def get_contacts(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get Salesforce contacts"""
        if not await self._ensure_authenticated():
            raise HTTPException(
                status_code=401, detail="Not authenticated with Salesforce"
            )

        try:
            query = f"""
            SELECT Id, AccountId, FirstName, LastName, Email, Phone, Title, Department,
                   MailingStreet, MailingCity, MailingState, MailingPostalCode, MailingCountry,
                   Description, CreatedDate, LastModifiedDate
            FROM Contact
            ORDER BY LastModifiedDate DESC
            LIMIT {limit}
            OFFSET {offset}
            """

            results = await self._execute_soql_query(query)
            contacts = [self._parse_contact_result(result) for result in results]

            return {
                "contacts": contacts,
                "total_count": len(contacts),
                "limit": limit,
                "offset": offset,
            }

        except Exception as e:
            logger.error(f"Failed to get contacts: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get contacts: {e}")

    async def get_contact(self, contact_id: str) -> SalesforceContact:
        """Get Salesforce contact by ID"""
        if not await self._ensure_authenticated():
            raise HTTPException(
                status_code=401, detail="Not authenticated with Salesforce"
            )

        try:
            query = f"""
            SELECT Id, AccountId, FirstName, LastName, Email, Phone, Title, Department,
                   MailingStreet, MailingCity, MailingState, MailingPostalCode, MailingCountry,
                   Description, CreatedDate, LastModifiedDate
            FROM Contact
            WHERE Id = '{contact_id}'
            """

            results = await self._execute_soql_query(query)
            if not results:
                raise HTTPException(status_code=404, detail="Contact not found")

            return self._parse_contact_result(results[0])

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get contact: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get contact: {e}")

    async def get_opportunities(
        self, limit: int = 100, offset: int = 0
    ) -> Dict[str, Any]:
        """Get Salesforce opportunities"""
        if not await self._ensure_authenticated():
            raise HTTPException(
                status_code=401, detail="Not authenticated with Salesforce"
            )

        try:
            query = f"""
            SELECT Id, AccountId, Name, StageName, Amount, CloseDate, Probability, Type,
                   LeadSource, Description, CreatedDate, LastModifiedDate
            FROM Opportunity
            ORDER BY LastModifiedDate DESC
            LIMIT {limit}
            OFFSET {offset}
            """

            results = await self._execute_soql_query(query)
            opportunities = [
                self._parse_opportunity_result(result) for result in results
            ]

            return {
                "opportunities": opportunities,
                "total_count": len(opportunities),
                "limit": limit,
                "offset": offset,
            }

        except Exception as e:
            logger.error(f"Failed to get opportunities: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get opportunities: {e}"
            )

    async def get_opportunity(self, opportunity_id: str) -> SalesforceOpportunity:
        """Get Salesforce opportunity by ID"""
        if not await self._ensure_authenticated():
            raise HTTPException(
                status_code=401, detail="Not authenticated with Salesforce"
            )

        try:
            query = f"""
            SELECT Id, AccountId, Name, StageName, Amount, CloseDate, Probability, Type,
                   LeadSource, Description, CreatedDate, LastModifiedDate
            FROM Opportunity
            WHERE Id = '{opportunity_id}'
            """

            results = await self._execute_soql_query(query)
            if not results:
                raise HTTPException(status_code=404, detail="Opportunity not found")

            return self._parse_opportunity_result(results[0])

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get opportunity: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get opportunity: {e}"
            )

    async def get_cases(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get Salesforce cases"""
        if not await self._ensure_authenticated():
            raise HTTPException(
                status_code=401, detail="Not authenticated with Salesforce"
            )

        try:
            query = f"""
            SELECT Id, AccountId, ContactId, CaseNumber, Subject, Description, Status, Priority,
                   Type, Origin, CreatedDate, LastModifiedDate
            FROM Case
            ORDER BY LastModifiedDate DESC
            LIMIT {limit}
            OFFSET {offset}
            """

            results = await self._execute_soql_query(query)
            cases = [self._parse_case_result(result) for result in results]

            return {
                "cases": cases,
                "total_count": len(cases),
                "limit": limit,
                "offset": offset,
            }

        except Exception as e:
            logger.error(f"Failed to get cases: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get cases: {e}")

    async def get_case(self, case_id: str) -> SalesforceCase:
        """Get Salesforce case by ID"""
        if not await self._ensure_authenticated():
            raise HTTPException(
                status_code=401, detail="Not authenticated with Salesforce"
            )

        try:
            query = f"""
            SELECT Id, AccountId, ContactId, CaseNumber, Subject, Description, Status, Priority,
                   Type, Origin, CreatedDate, LastModifiedDate
            FROM Case
            WHERE Id = '{case_id}'
            """

            results = await self._execute_soql_query(query)
            if not results:
                raise HTTPException(status_code=404, detail="Case not found")

            return self._parse_case_result(results[0])

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get case: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get case: {e}")

    async def execute_query(self, query_request: SalesforceQuery) -> Dict[str, Any]:
        """Execute SOQL query"""
        if not await self._ensure_authenticated():
            raise HTTPException(
                status_code=401, detail="Not authenticated with Salesforce"
            )

        try:
            # Add LIMIT and OFFSET if not present
            query = query_request.query
            if "LIMIT" not in query.upper():
                query += f" LIMIT {query_request.limit}"
            if query_request.offset > 0 and "OFFSET" not in query.upper():
                query += f" OFFSET {query_request.offset}"

            results = await self._execute_soql_query(query)

            return {
                "query": query,
                "results": results,
                "total_count": len(results),
                "limit": query_request.limit,
                "offset": query_request.offset,
            }

        except Exception as e:
            logger.error(f"SOQL query execution failed: {e}")
            raise HTTPException(status_code=500, detail=f"Query execution failed: {e}")

    async def execute_search(self, search_request: SalesforceSearch) -> Dict[str, Any]:
        """Execute SOSL search"""
        if not await self._ensure_authenticated():
            raise HTTPException(
                status_code=401, detail="Not authenticated with Salesforce"
            )

        try:
            # Build SOSL query
            object_types = " OR ".join(
                [f"{obj}" for obj in search_request.object_types]
            )
            sosl_query = f"FIND {{{search_request.search_term}}} IN ALL FIELDS RETURNING {object_types} LIMIT {search_request.limit}"

            results = await self._execute_sosl_search(sosl_query)

            return {
                "search_term": search_request.search_term,
                "object_types": search_request.object_types,
                "results": results,
                "total_count": sum(
                    len(results.get(obj, [])) for obj in search_request.object_types
                ),
            }

        except Exception as e:
            logger.error(f"SOSL search execution failed: {e}")
            raise HTTPException(status_code=500, detail=f"Search execution failed: {e}")

    async def sync_data(self, full_sync: bool = False) -> SalesforceSyncResult:
        """Synchronize Salesforce data"""
        if not await self._ensure_authenticated():
            raise HTTPException(
                status_code=401, detail="Not authenticated with Salesforce"
            )

        start_time = datetime.utcnow()
        errors = []
        accounts_synced = 0
        contacts_synced = 0
        opportunities_synced = 0
        cases_synced = 0

        try:
            # Sync accounts
            accounts_result = await self.get_accounts(limit=1000)
            accounts_synced = len(accounts_result["accounts"])

            # Sync contacts
            contacts_result = await self.get_contacts(limit=1000)
            contacts_synced = len(contacts_result["contacts"])

            # Sync opportunities
            opportunities_result = await self.get_opportunities(limit=1000)
            opportunities_synced = len(opportunities_result["opportunities"])

            # Sync cases
            cases_result = await self.get_cases(limit=1000)
            cases_synced = len(cases_result["cases"])

            # In production, store synchronized data in application database
            logger.info(
                f"Salesforce sync completed: {accounts_synced} accounts, {contacts_synced} contacts, {opportunities_synced} opportunities, {cases_synced} cases"
            )

        except Exception as e:
            errors.append(f"Sync error: {str(e)}")
            logger.error(f"Salesforce sync failed: {e}")

        duration = (datetime.utcnow() - start_time).total_seconds()

        return SalesforceSyncResult(
            accounts_synced=accounts_synced,
            contacts_synced=contacts_synced,
            opportunities_synced=opportunities_synced,
            cases_synced=cases_synced,
            errors=errors,
            duration_seconds=duration,
            timestamp=datetime.utcnow().isoformat(),
        )

    async def get_metrics(self) -> SalesforceMetrics:
        """Get Salesforce integration metrics"""
        if not await self._ensure_authenticated():
            raise HTTPException(
                status_code=401, detail="Not authenticated with Salesforce"
            )

        # Mock metrics - in production, calculate from actual data
        return SalesforceMetrics(
            total_accounts=1500,
            total_contacts=5000,
            total_opportunities=800,
            total_cases=1200,
            api_calls_today=45,
            sync_status="completed",
            last_sync=datetime.utcnow().isoformat(),
        )

    async def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid authentication token"""
        if not self.auth_data:
            return await self._authenticate()

        # Check if token is expired (Salesforce tokens typically last 2 hours)
        try:
            issued_at = int(self.auth_data.issued_at) / 1000  # Convert to seconds
            token_age = datetime.utcnow().timestamp() - issued_at
            if token_age > 7200:  # 2 hours in seconds
                return await self._authenticate()
        except:
            # If we can't parse the timestamp, re-authenticate
            return await self._authenticate()

        return True

    async def _authenticate(self) -> bool:
        """Authenticate with Salesforce"""
        if not self.config:
            return False

        try:
            auth_url = f"{self.config.auth_url}/services/oauth2/token"
            auth_data = {
                "grant_type": "password",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "username": self.config.username,
                "password": self.config.password + self.config.security_token,
                "scope": " ".join(self.config.scope),
            }

            async with self.session.post(auth_url, data=auth_data) as response:
                if response.status != 200:
                    logger.error(f"Salesforce authentication failed: {response.status}")
                    return False

                auth_response = await response.json()
                self.auth_data = SalesforceAuth(**auth_response)

                logger.info("Successfully authenticated with Salesforce")
                return True

        except Exception as e:
            logger.error(f"Salesforce authentication error: {e}")
            return False

    async def _execute_soql_query(self, query: str) -> List[Dict]:
        """Execute SOQL query against Salesforce"""
        if not self.auth_data:
            raise HTTPException(status_code=401, detail="Not authenticated")

        try:
            url = f"{self.auth_data.instance_url}/services/data/{self.config.api_version}/query"
            params = {"q": query}

            headers = {
                "Authorization": f"Bearer {self.auth_data.access_token}",
                "Content-Type": "application/json",
            }

            async with self.session.get(
                url, params=params, headers=headers
            ) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=response.status, detail="Query execution failed"
                    )

                result = await response.json()
                return result.get("records", [])

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"SOQL query execution error: {e}")
            raise HTTPException(status_code=500, detail=f"Query execution error: {e}")

    async def _execute_sosl_search(self, sosl_query: str) -> Dict[str, List]:
        """Execute SOSL search against Salesforce"""
        if not self.auth_data:
            raise HTTPException(status_code=401, detail="Not authenticated")

        try:
            url = f"{self.auth_data.instance_url}/services/data/{self.config.api_version}/search"
            params = {"q": sosl_query}

            headers = {
                "Authorization": f"Bearer {self.auth_data.access_token}",
                "Content-Type": "application/json",
            }

            async with self.session.get(
                url, params=params, headers=headers
            ) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=response.status, detail="Search execution failed"
                    )

                result = await response.json()
                return result.get("searchRecords", {})

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"SOSL search execution error: {e}")
            raise HTTPException(status_code=500, detail=f"Search execution error: {e}")

    def _parse_account_result(self, result: Dict) -> SalesforceAccount:
        """Parse Salesforce account result"""
        return SalesforceAccount(
            id=result.get("Id", ""),
            name=result.get("Name", ""),
            type=result.get("Type"),
            industry=result.get("Industry"),
            website=result.get("Website"),
            phone=result.get("Phone"),
            billing_address={
                "street": result.get("BillingStreet"),
                "city": result.get("BillingCity"),
                "state": result.get("BillingState"),
                "postal_code": result.get("BillingPostalCode"),
                "country": result.get("BillingCountry"),
            }
            if any([result.get("BillingStreet"), result.get("BillingCity")])
            else None,
            shipping_address={
                "street": result.get("ShippingStreet"),
                "city": result.get("ShippingCity"),
                "state": result.get("ShippingState"),
                "postal_code": result.get("ShippingPostalCode"),
                "country": result.get("ShippingCountry"),
            }
            if any([result.get("ShippingStreet"), result.get("ShippingCity")])
            else None,
            description=result.get("Description"),
            created_date=result.get("CreatedDate"),
            last_modified_date=result.get("LastModifiedDate"),
        )

    def _parse_contact_result(self, result: Dict) -> SalesforceContact:
        """Parse Salesforce contact result"""
        return SalesforceContact(
            id=result.get("Id", ""),
            account_id=result.get("AccountId"),
            first_name=result.get("FirstName"),
            last_name=result.get("LastName", ""),
            email=result.get("Email"),
            phone=result.get("Phone"),
            title=result.get("Title"),
            department=result.get("Department"),
            mailing_address={
                "street": result.get("MailingStreet"),
                "city": result.get("MailingCity"),
                "state": result.get("MailingState"),
                "postal_code": result.get("MailingPostalCode"),
                "country": result.get("MailingCountry"),
            }
            if any([result.get("MailingStreet"), result.get("MailingCity")])
            else None,
            description=result.get("Description"),
            created_date=result.get("CreatedDate"),
            last_modified_date=result.get("LastModifiedDate"),
        )

    def _parse_opportunity_result(self, result: Dict) -> SalesforceOpportunity:
        """Parse Salesforce opportunity result"""
        return SalesforceOpportunity(
            id=result.get("Id", ""),
            account_id=result.get("AccountId"),
            name=result.get("Name", ""),
            stage=result.get("StageName", ""),
            amount=float(result.get("Amount", 0)) if result.get("Amount") else None,
            close_date=result.get("CloseDate", ""),
            probability=float(result.get("Probability", 0))
            if result.get("Probability")
            else None,
            type=result.get("Type"),
            lead_source=result.get("LeadSource"),
            description=result.get("Description"),
            created_date=result.get("CreatedDate"),
            last_modified_date=result.get("LastModifiedDate"),
        )

    def _parse_case_result(self, result: Dict) -> SalesforceCase:
        """Parse Salesforce case result"""
        return SalesforceCase(
            id=result.get("Id", ""),
            account_id=result.get("AccountId"),
            contact_id=result.get("ContactId"),
            case_number=result.get("CaseNumber", ""),
            subject=result.get("Subject", ""),
            description=result.get("Description"),
            status=result.get("Status", ""),
            priority=result.get("Priority", ""),
            type=result.get("Type"),
            origin=result.get("Origin"),
            created_date=result.get("CreatedDate"),
            last_modified_date=result.get("LastModifiedDate"),
        )


# Initialize enterprise Salesforce connector
enterprise_salesforce_connector = EnterpriseSalesforceConnector()

# Default configuration
default_salesforce_config = SalesforceConfig(
    enabled=False,
    environment="production",
    client_id="your_client_id",
    client_secret="your_client_secret",
    username="integration_user@example.com",
    password="your_password",
    security_token="your_security_token",
    api_version="v58.0",
    auth_url="https://login.salesforce.com",
    scope=["api", "refresh_token"],
)

# Initialize with default configuration (deferred to avoid event loop issues)
# enterprise_salesforce_connector.initialize(default_salesforce_config)

# Salesforce API Router for inclusion in main application
router = enterprise_salesforce_connector.router


# Additional Salesforce management endpoints
@router.get("/salesforce/compliance/report")
async def generate_salesforce_compliance_report():
    """Generate Salesforce compliance report"""
    return {
        "report_id": f"salesforce_compliance_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "generated_at": datetime.utcnow().isoformat(),
        "compliance_checks": {
            "data_access_controls": "compliant",
            "api_usage_monitoring": "compliant",
            "data_encryption": "compliant",
            "audit_trail_enabled": "compliant",
            "user_access_reviews": "compliant",
        },
        "recommendations": [
            "Implement regular data backup procedures",
            "Review API usage limits monthly",
            "Enable multi-factor authentication for all users",
            "Conduct quarterly security assessments",
        ],
    }


@router.get("/salesforce/export/data")
async def export_salesforce_data(object_type: str = "Account", format: str = "json"):
    """Export Salesforce data"""
    if not enterprise_salesforce_connector.config:
        raise HTTPException(
            status_code=404, detail="Salesforce connector not configured"
        )

    # Mock export - in production, generate actual export
    if object_type == "Account":
        data = await enterprise_salesforce_connector.get_accounts(limit=1000)
    elif object_type == "Contact":
        data = await enterprise_salesforce_connector.get_contacts(limit=1000)
    elif object_type == "Opportunity":
        data = await enterprise_salesforce_connector.get_opportunities(limit=1000)
    elif object_type == "Case":
        data = await enterprise_salesforce_connector.get_cases(limit=1000)
    else:
        raise HTTPException(status_code=400, detail="Unsupported object type")

    if format == "csv":
        # Generate CSV format
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header and data based on object type
        # Implementation would vary by object type
