#!/usr/bin/env python3
"""
🚀 Salesforce Core Service Integration
Enterprise-grade Salesforce API integration with comprehensive business object support
"""

import os
import json
import logging
import requests
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, List, Union
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlencode
from enum import Enum

import asyncpg

logger = logging.getLogger(__name__)

class SalesforceEnvironment(Enum):
    """Salesforce environment types"""
    PRODUCTION = "production"
    SANDBOX = "sandbox"

class SalesforceObject(Enum):
    """Salesforce object types"""
    ACCOUNT = "Account"
    CONTACT = "Contact"
    LEAD = "Lead"
    OPPORTUNITY = "Opportunity"
    CASE = "Case"
    CAMPAIGN = "Campaign"
    TASK = "Task"
    EVENT = "Event"
    NOTE = "Note"
    ATTACHMENT = "Attachment"

@dataclass
class SalesforceQueryResult:
    """Salesforce query result wrapper"""
    total_size: int
    done: bool
    next_records_url: Optional[str]
    records: List[Dict[str, Any]]

@dataclass
class SalesforceCredentials:
    """Salesforce API credentials"""
    access_token: str
    instance_url: str
    refresh_token: str
    expires_at: datetime
    user_id: str
    organization_id: str
    username: str

class SalesforceAPIError(Exception):
    """Salesforce API specific error"""
    
    def __init__(self, message: str, status_code: int = None, error_code: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code

class SalesforceCoreService:
    """Enterprise-grade Salesforce API service"""
    
    def __init__(self, db_pool: asyncpg.Pool = None):
        self.db_pool = db_pool
        self.session = requests.Session()
        self.session.timeout = 30
        self._setup_session()
    
    def _setup_session(self):
        """Configure HTTP session for Salesforce API"""
        self.session.headers.update({
            'User-Agent': 'ATOM-Enterprise/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    async def get_credentials(self, user_id: str, username: str = None) -> Optional[SalesforceCredentials]:
        """
        Retrieve Salesforce credentials for user
        
        Args:
            user_id: Salesforce user ID
            username: Optional username (if multiple accounts)
            
        Returns:
            SalesforceCredentials or None if not found
        """
        try:
            from db_oauth_salesforce import get_user_salesforce_tokens
            
            tokens = await get_user_salesforce_tokens(self.db_pool, user_id, username)
            
            if not tokens:
                logger.warning(f"No Salesforce tokens found for user: {user_id}")
                return None
            
            # Check if token is expired
            expires_at = datetime.fromisoformat(tokens["expires_at"].replace('Z', '+00:00'))
            if expires_at < datetime.now(timezone.utc):
                logger.warning(f"Salesforce token expired for user: {user_id}")
                return None
            
            return SalesforceCredentials(
                access_token=tokens["access_token"],
                instance_url=tokens["instance_url"],
                refresh_token=tokens["refresh_token"],
                expires_at=expires_at,
                user_id=tokens["user_id"],
                organization_id=tokens["organization_id"],
                username=tokens["username"]
            )
            
        except Exception as e:
            logger.error(f"Error retrieving Salesforce credentials: {e}")
            return None
    
    def _make_api_request(
        self,
        credentials: SalesforceCredentials,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated API request to Salesforce
        
        Args:
            credentials: Valid Salesforce credentials
            method: HTTP method
            endpoint: API endpoint
            data: Request data
            params: Query parameters
            
        Returns:
            API response dictionary
        """
        try:
            # Build full URL
            base_url = credentials.instance_url
            if not endpoint.startswith('/'):
                endpoint = f'/services/data/v56.0/{endpoint}'  # Latest API version
            
            url = urljoin(base_url, endpoint)
            
            # Prepare headers with authentication
            headers = {
                'Authorization': f'Bearer {credentials.access_token}',
                'Sforce-Call-Options': 'default=norouting'
            }
            
            # Make request
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=data if data else None,
                params=params
            )
            
            # Log API usage
            self._log_api_usage(
                credentials.user_id,
                credentials.username,
                f"{method} {endpoint}",
                len(str(data)) if data else 0,
                response.status_code < 400,
                None if response.status_code < 400 else response.text
            )
            
            # Handle response
            if response.status_code == 200:
                return response.json() if response.content else {}
            elif response.status_code == 204:  # No content
                return {}
            else:
                # Parse error response
                try:
                    error_data = response.json()
                    error_message = error_data.get('error_description', error_data.get('error', 'Unknown error'))
                    error_code = error_data.get('error_code', 'UNKNOWN_ERROR')
                except:
                    error_message = response.text
                    error_code = 'HTTP_ERROR'
                
                raise SalesforceAPIError(
                    message=error_message,
                    status_code=response.status_code,
                    error_code=error_code
                )
        
        except SalesforceAPIError:
            raise
        except requests.exceptions.Timeout:
            raise SalesforceAPIError(
                message="Request timeout",
                status_code=408,
                error_code="TIMEOUT_ERROR"
            )
        except requests.exceptions.RequestException as e:
            raise SalesforceAPIError(
                message=f"Network error: {str(e)}",
                error_code="NETWORK_ERROR"
            )
        except Exception as e:
            raise SalesforceAPIError(
                message=f"Unexpected error: {str(e)}",
                error_code="UNKNOWN_ERROR"
            )
    
    def _log_api_usage(
        self,
        user_id: str,
        username: str,
        api_endpoint: str,
        data_transferred: int,
        success: bool,
        error_message: str
    ) -> None:
        """Log API usage for analytics"""
        try:
            if self.db_pool:
                asyncio.create_task(
                    self._log_api_usage_async(
                        user_id, username, api_endpoint, 
                        data_transferred, success, error_message
                    )
                )
        except Exception as e:
            logger.error(f"Failed to log API usage: {e}")
    
    async def _log_api_usage_async(
        self,
        user_id: str,
        username: str,
        api_endpoint: str,
        data_transferred: int,
        success: bool,
        error_message: str
    ) -> None:
        """Async API usage logging"""
        try:
            from db_oauth_salesforce import log_api_usage
            await log_api_usage(
                self.db_pool, user_id, username, api_endpoint,
                data_transferred, success, error_message
            )
        except Exception as e:
            logger.error(f"Failed to log API usage async: {e}")
    
    # ACCOUNT MANAGEMENT
    
    async def list_accounts(
        self,
        user_id: str,
        username: Optional[str] = None,
        query: Optional[str] = None,
        fields: Optional[List[str]] = None,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        List Salesforce accounts with advanced filtering
        
        Args:
            user_id: Salesforce user ID
            username: Optional username
            query: SOQL WHERE clause
            fields: List of fields to retrieve
            limit: Maximum records to return
            offset: Record offset for pagination
            
        Returns:
            Dictionary with accounts list and metadata
        """
        try:
            credentials = await self.get_credentials(user_id, username)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            # Build SOQL query
            default_fields = ["Id", "Name", "Type", "Industry", "BillingCity", 
                          "BillingState", "BillingCountry", "Phone", "Website", 
                          "AnnualRevenue", "NumberOfEmployees", "CreatedDate"]
            query_fields = fields if fields else default_fields
            query_clause = f"WHERE {query}" if query else ""
            
            soql = f"""
                SELECT {', '.join(query_fields)} 
                FROM Account 
                {query_clause}
                ORDER BY CreatedDate DESC 
                LIMIT {limit} OFFSET {offset}
            """
            
            # Make API request
            response = self._make_api_request(
                credentials=credentials,
                method="GET",
                endpoint=f"query/?q={soql}"
            )
            
            # Format response
            accounts = response.get("records", [])
            
            return {
                "ok": True,
                "accounts": accounts,
                "total_size": response.get("totalSize", len(accounts)),
                "done": response.get("done", True),
                "query": soql,
                "limit": limit,
                "offset": offset
            }
            
        except SalesforceAPIError as e:
            logger.error(f"Salesforce list accounts error: {e}")
            return {
                "ok": False,
                "error": "api_error",
                "message": str(e),
                "status_code": e.status_code,
                "error_code": e.error_code
            }
        except Exception as e:
            logger.error(f"Unexpected error in list accounts: {e}")
            return {
                "ok": False,
                "error": "unexpected_error",
                "message": "Unexpected error occurred"
            }
    
    async def create_account(
        self,
        user_id: str,
        username: Optional[str] = None,
        account_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create new Salesforce account
        
        Args:
            user_id: Salesforce user ID
            username: Optional username
            account_data: Account data fields
            
        Returns:
            Dictionary with creation result
        """
        try:
            credentials = await self.get_credentials(user_id, username)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            if not account_data:
                return {
                    "ok": False,
                    "error": "validation_error",
                    "message": "Account data is required"
                }
            
            # Create account
            response = self._make_api_request(
                credentials=credentials,
                method="POST",
                endpoint="sobjects/Account/",
                data=account_data
            )
            
            return {
                "ok": True,
                "account": response,
                "message": "Account created successfully"
            }
            
        except SalesforceAPIError as e:
            logger.error(f"Salesforce create account error: {e}")
            return {
                "ok": False,
                "error": "api_error",
                "message": str(e),
                "status_code": e.status_code,
                "error_code": e.error_code
            }
        except Exception as e:
            logger.error(f"Unexpected error in create account: {e}")
            return {
                "ok": False,
                "error": "unexpected_error",
                "message": "Unexpected error occurred"
            }
    
    # CONTACT MANAGEMENT
    
    async def list_contacts(
        self,
        user_id: str,
        username: Optional[str] = None,
        account_id: Optional[str] = None,
        query: Optional[str] = None,
        fields: Optional[List[str]] = None,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        List Salesforce contacts with filtering options
        
        Args:
            user_id: Salesforce user ID
            username: Optional username
            account_id: Filter by account ID
            query: Additional SOQL WHERE clause
            fields: List of fields to retrieve
            limit: Maximum records to return
            offset: Record offset for pagination
            
        Returns:
            Dictionary with contacts list and metadata
        """
        try:
            credentials = await self.get_credentials(user_id, username)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            # Build SOQL query
            default_fields = ["Id", "FirstName", "LastName", "Email", "Phone", 
                          "Title", "AccountId", "LeadSource", "CreatedDate"]
            query_fields = fields if fields else default_fields
            
            # Build WHERE clause
            conditions = []
            if account_id:
                conditions.append(f"AccountId = '{account_id}'")
            if query:
                conditions.append(query)
            
            where_clause = ""
            if conditions:
                where_clause = f"WHERE {' AND '.join(conditions)}"
            
            soql = f"""
                SELECT {', '.join(query_fields)} 
                FROM Contact 
                {where_clause}
                ORDER BY CreatedDate DESC 
                LIMIT {limit} OFFSET {offset}
            """
            
            # Make API request
            response = self._make_api_request(
                credentials=credentials,
                method="GET",
                endpoint=f"query/?q={soql}"
            )
            
            # Format response
            contacts = response.get("records", [])
            
            return {
                "ok": True,
                "contacts": contacts,
                "total_size": response.get("totalSize", len(contacts)),
                "done": response.get("done", True),
                "query": soql,
                "limit": limit,
                "offset": offset
            }
            
        except SalesforceAPIError as e:
            logger.error(f"Salesforce list contacts error: {e}")
            return {
                "ok": False,
                "error": "api_error",
                "message": str(e),
                "status_code": e.status_code,
                "error_code": e.error_code
            }
        except Exception as e:
            logger.error(f"Unexpected error in list contacts: {e}")
            return {
                "ok": False,
                "error": "unexpected_error",
                "message": "Unexpected error occurred"
            }
    
    # OPPORTUNITY MANAGEMENT
    
    async def list_opportunities(
        self,
        user_id: str,
        username: Optional[str] = None,
        account_id: Optional[str] = None,
        stage: Optional[str] = None,
        query: Optional[str] = None,
        fields: Optional[List[str]] = None,
        limit: int = 25,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        List Salesforce opportunities with sales pipeline filtering
        
        Args:
            user_id: Salesforce user ID
            username: Optional username
            account_id: Filter by account ID
            stage: Filter by opportunity stage
            query: Additional SOQL WHERE clause
            fields: List of fields to retrieve
            limit: Maximum records to return
            offset: Record offset for pagination
            
        Returns:
            Dictionary with opportunities list and metadata
        """
        try:
            credentials = await self.get_credentials(user_id, username)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            # Build SOQL query
            default_fields = ["Id", "Name", "AccountId", "Amount", "StageName", 
                          "Probability", "CloseDate", "LeadSource", "Type", 
                          "ForecastCategory", "CreatedDate"]
            query_fields = fields if fields else default_fields
            
            # Build WHERE clause
            conditions = []
            if account_id:
                conditions.append(f"AccountId = '{account_id}'")
            if stage:
                conditions.append(f"StageName = '{stage}'")
            if query:
                conditions.append(query)
            
            where_clause = ""
            if conditions:
                where_clause = f"WHERE {' AND '.join(conditions)}"
            
            soql = f"""
                SELECT {', '.join(query_fields)} 
                FROM Opportunity 
                {where_clause}
                ORDER BY CloseDate ASC, CreatedDate DESC 
                LIMIT {limit} OFFSET {offset}
            """
            
            # Make API request
            response = self._make_api_request(
                credentials=credentials,
                method="GET",
                endpoint=f"query/?q={soql}"
            )
            
            # Format response
            opportunities = response.get("records", [])
            
            # Calculate pipeline statistics
            total_pipeline = sum(opp.get("Amount", 0) for opp in opportunities)
            weighted_pipeline = sum(
                opp.get("Amount", 0) * (opp.get("Probability", 0) / 100) 
                for opp in opportunities
            )
            
            return {
                "ok": True,
                "opportunities": opportunities,
                "total_size": response.get("totalSize", len(opportunities)),
                "done": response.get("done", True),
                "query": soql,
                "limit": limit,
                "offset": offset,
                "pipeline_statistics": {
                    "total_pipeline_value": total_pipeline,
                    "weighted_pipeline_value": weighted_pipeline,
                    "opportunity_count": len(opportunities)
                }
            }
            
        except SalesforceAPIError as e:
            logger.error(f"Salesforce list opportunities error: {e}")
            return {
                "ok": False,
                "error": "api_error",
                "message": str(e),
                "status_code": e.status_code,
                "error_code": e.error_code
            }
        except Exception as e:
            logger.error(f"Unexpected error in list opportunities: {e}")
            return {
                "ok": False,
                "error": "unexpected_error",
                "message": "Unexpected error occurred"
            }
    
    # UTILITY METHODS
    
    async def get_user_info(
        self,
        user_id: str,
        username: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get Salesforce user information
        
        Args:
            user_id: Salesforce user ID
            username: Optional username
            
        Returns:
            Dictionary with user information
        """
        try:
            credentials = await self.get_credentials(user_id, username)
            if not credentials:
                return {
                    "ok": False,
                    "error": "authentication_failed",
                    "message": "Invalid or expired credentials"
                }
            
            # Get user info from Identity service
            identity_url = f"{credentials.instance_url}/services/oauth2/userinfo"
            
            # Use requests directly for this call
            response = requests.get(
                identity_url,
                headers={'Authorization': f'Bearer {credentials.access_token}'},
                timeout=30
            )
            
            if response.status_code == 200:
                user_data = response.json()
                
                return {
                    "ok": True,
                    "user_info": {
                        "user_id": user_data.get("user_id"),
                        "organization_id": user_data.get("organization_id"),
                        "username": user_data.get("username"),
                        "email": user_data.get("email"),
                        "display_name": user_data.get("display_name"),
                        "profile_id": user_data.get("profile_id"),
                        "timezone": user_data.get("timezone"),
                        "locale": user_data.get("locale"),
                        "active": user_data.get("active", True),
                        "environment": "production" if "login.salesforce.com" in credentials.instance_url else "sandbox"
                    }
                }
            else:
                return {
                    "ok": False,
                    "error": "user_info_failed",
                    "message": "Failed to retrieve user information",
                    "status_code": response.status_code
                }
            
        except Exception as e:
            logger.error(f"Error getting Salesforce user info: {e}")
            return {
                "ok": False,
                "error": "unexpected_error",
                "message": "Unexpected error occurred"
            }

# Global Salesforce service instance
salesforce_core_service = None

def get_salesforce_core_service(db_pool: asyncpg.Pool = None) -> SalesforceCoreService:
    """Get or create Salesforce service instance"""
    global salesforce_core_service
    if salesforce_core_service is None:
        salesforce_core_service = SalesforceCoreService(db_pool)
    return salesforce_core_service