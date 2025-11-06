import os
import logging
from typing import Optional, Tuple, List, Dict, Any
from simple_salesforce import Salesforce, SalesforceAuthenticationFailed
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def get_salesforce_client(user_id: str, db_conn_pool) -> Optional[Salesforce]:
    """
    Get authenticated Salesforce client using OAuth tokens from database

    Args:
        user_id: The user ID to fetch tokens for
        db_conn_pool: Database connection pool

    Returns:
        Salesforce client instance or None if authentication fails
    """
    try:
        from db_oauth_salesforce import get_user_salesforce_tokens

        # Get user's Salesforce tokens from database
        tokens = await get_user_salesforce_tokens(db_conn_pool, user_id)

        if not tokens:
            logger.warning(f"No Salesforce tokens found for user {user_id}")
            return None

        access_token = tokens.get("access_token")
        instance_url = tokens.get("instance_url")

        if not access_token or not instance_url:
            logger.error(f"Missing required Salesforce token data for user {user_id}")
            return None

        # Check if token is expired or about to expire
        expires_at = tokens.get("expires_at")
        if expires_at:
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))

            now = datetime.now(timezone.utc)
            if expires_at < now:
                logger.warning(
                    f"Salesforce token expired for user {user_id}, attempting refresh"
                )
                try:
                    from auth_handler_salesforce import SalesforceOAuthHandler

                    oauth_handler = SalesforceOAuthHandler(db_conn_pool)
                    refresh_result = await oauth_handler.refresh_token(
                        tokens.get("refresh_token")
                    )

                    if refresh_result.get("ok"):
                        # Get updated tokens
                        tokens = await get_user_salesforce_tokens(db_conn_pool, user_id)
                        access_token = tokens.get("access_token")
                        instance_url = tokens.get("instance_url")
                    else:
                        logger.error(
                            f"Failed to refresh Salesforce token for user {user_id}"
                        )
                        return None
                except Exception as refresh_error:
                    logger.error(
                        f"Error refreshing Salesforce token for user {user_id}: {refresh_error}"
                    )
                    return None

        try:
            # Create Salesforce client with OAuth token
            sf = Salesforce(
                instance_url=instance_url,
                session_id=access_token,
                version="57.0",  # Latest supported version
            )

            # Test connection with a simple query
            test_result = sf.query("SELECT Id FROM User LIMIT 1")
            logger.info(f"Successfully connected to Salesforce for user {user_id}")
            return sf

        except SalesforceAuthenticationFailed as e:
            logger.error(f"Salesforce authentication failed for user {user_id}: {e}")
            return None

    except ImportError as e:
        logger.error(f"Salesforce OAuth database handler not available: {e}")
        return None
    except Exception as e:
        logger.error(
            f"Error getting Salesforce client for user {user_id}: {e}", exc_info=True
        )
        return None


async def list_contacts(sf: Salesforce) -> List[Dict[str, Any]]:
    """List all contacts from Salesforce"""
    try:
        query = (
            "SELECT Id, Name, Email, Phone, Title, AccountId FROM Contact ORDER BY Name"
        )
        result = sf.query_all(query)
        return result["records"]
    except Exception as e:
        logger.error(f"Error listing Salesforce contacts: {e}")
        raise


async def list_accounts(sf: Salesforce) -> List[Dict[str, Any]]:
    """List all accounts from Salesforce"""
    try:
        query = (
            "SELECT Id, Name, Type, Industry, Phone, Website FROM Account ORDER BY Name"
        )
        result = sf.query_all(query)
        return result["records"]
    except Exception as e:
        logger.error(f"Error listing Salesforce accounts: {e}")
        raise


async def list_opportunities(sf: Salesforce) -> List[Dict[str, Any]]:
    """List all opportunities from Salesforce"""
    try:
        query = "SELECT Id, Name, StageName, Amount, CloseDate, AccountId FROM Opportunity ORDER BY CloseDate DESC"
        result = sf.query_all(query)
        return result["records"]
    except Exception as e:
        logger.error(f"Error listing Salesforce opportunities: {e}")
        raise


async def list_leads(sf: Salesforce) -> List[Dict[str, Any]]:
    """List all leads from Salesforce"""
    try:
        query = "SELECT Id, Name, Company, Email, Status, LeadSource FROM Lead ORDER BY CreatedDate DESC"
        result = sf.query_all(query)
        return result["records"]
    except Exception as e:
        logger.error(f"Error listing Salesforce leads: {e}")
        raise


async def create_contact(
    sf: Salesforce,
    last_name: str,
    first_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new contact in Salesforce"""
    try:
        contact_data = {"LastName": last_name}
        if first_name:
            contact_data["FirstName"] = first_name
        if email:
            contact_data["Email"] = email
        if phone:
            contact_data["Phone"] = phone

        result = sf.Contact.create(contact_data)
        return result
    except Exception as e:
        logger.error(f"Error creating Salesforce contact: {e}")
        raise


async def create_account(
    sf: Salesforce,
    name: str,
    type: Optional[str] = None,
    industry: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new account in Salesforce"""
    try:
        account_data = {"Name": name}
        if type:
            account_data["Type"] = type
        if industry:
            account_data["Industry"] = industry

        result = sf.Account.create(account_data)
        return result
    except Exception as e:
        logger.error(f"Error creating Salesforce account: {e}")
        raise


async def create_opportunity(
    sf: Salesforce,
    name: str,
    stage_name: str,
    close_date: str,
    amount: Optional[float] = None,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new opportunity in Salesforce"""
    try:
        opportunity_data = {
            "Name": name,
            "StageName": stage_name,
            "CloseDate": close_date,
        }
        if amount is not None:
            opportunity_data["Amount"] = amount
        if account_id:
            opportunity_data["AccountId"] = account_id

        result = sf.Opportunity.create(opportunity_data)
        return result
    except Exception as e:
        logger.error(f"Error creating Salesforce opportunity: {e}")
        raise


async def update_opportunity(
    sf: Salesforce, opportunity_id: str, fields_to_update: Dict[str, Any]
) -> Dict[str, Any]:
    """Update an existing opportunity in Salesforce"""
    try:
        result = sf.Opportunity.update(opportunity_id, fields_to_update)
        return result
    except Exception as e:
        logger.error(f"Error updating Salesforce opportunity {opportunity_id}: {e}")
        raise


async def get_opportunity(sf: Salesforce, opportunity_id: str) -> Dict[str, Any]:
    """Get a specific opportunity from Salesforce"""
    try:
        result = sf.Opportunity.get(opportunity_id)
        return result
    except Exception as e:
        logger.error(f"Error getting Salesforce opportunity {opportunity_id}: {e}")
        raise


async def create_lead(
    sf: Salesforce,
    last_name: str,
    company: str,
    first_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new lead in Salesforce"""
    try:
        lead_data = {"LastName": last_name, "Company": company}
        if first_name:
            lead_data["FirstName"] = first_name
        if email:
            lead_data["Email"] = email
        if phone:
            lead_data["Phone"] = phone

        result = sf.Lead.create(lead_data)
        return result
    except Exception as e:
        logger.error(f"Error creating Salesforce lead: {e}")
        raise


async def get_campaign(sf: Salesforce, campaign_id: str) -> Dict[str, Any]:
    """Get a specific campaign from Salesforce"""
    try:
        result = sf.Campaign.get(campaign_id)
        return result
    except Exception as e:
        logger.error(f"Error getting Salesforce campaign {campaign_id}: {e}")
        raise


async def get_case(sf: Salesforce, case_id: str) -> Dict[str, Any]:
    """Get a specific case from Salesforce"""
    try:
        result = sf.Case.get(case_id)
        return result
    except Exception as e:
        logger.error(f"Error getting Salesforce case {case_id}: {e}")
        raise


async def get_user_info(sf: Salesforce) -> Dict[str, Any]:
    """Get current user information from Salesforce"""
    try:
        query = "SELECT Id, Name, Username, Email, ProfileId FROM User WHERE Id = '005'"
        result = sf.query_all(query)
        if result["records"]:
            return result["records"][0]
        return {}
    except Exception as e:
        logger.error(f"Error getting Salesforce user info: {e}")
        raise


async def execute_soql_query(sf: Salesforce, query: str) -> Dict[str, Any]:
    """Execute a custom SOQL query"""
    try:
        result = sf.query_all(query)
        return result
    except Exception as e:
        logger.error(f"Error executing SOQL query: {e}")
        raise
