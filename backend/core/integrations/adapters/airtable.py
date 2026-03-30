"""
Airtable Integration Adapter

Provides OAuth-based integration with Airtable for database and spreadsheet operations.
"""

import logging
import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class AirtableAdapter:
    """
    Adapter for Airtable OAuth integration.

    Supports:
    - OAuth 2.0 authentication (personal access tokens)
    - Table and record management
    - Base and schema operations
    - Field and view access
    """

    def __init__(self, db, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.service_name = "airtable"
        self.base_url = "https://api.airtable.com/v0"

        # OAuth credentials from environment
        self.client_id = os.getenv("AIRTABLE_CLIENT_ID")
        self.client_secret = os.getenv("AIRTABLE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("AIRTABLE_REDIRECT_URI")
        self.personal_access_token = os.getenv("AIRTABLE_PAT")

        # Token storage
        self._access_token: Optional[str] = None
        _refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def get_oauth_url(self) -> str:
        """
        Generate Airtable OAuth authorization URL.

        Returns:
            Authorization URL to redirect user to Airtable OAuth consent screen
        """
        if not self.client_id:
            raise ValueError("AIRTABLE_CLIENT_ID not configured")

        # Airtable OAuth endpoint
        auth_url = "https://airtable.com/oauth2/v1/authorize"

        # Build authorization URL
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "data.records:read data.records:write schema.bases:read",
            "state": self.workspace_id,  # Use workspace_id as state
        }

        auth_url_with_params = f"{auth_url}?{urlencode(params)}"

        logger.info(f"Generated Airtable OAuth URL for workspace {self.workspace_id}")
        return auth_url_with_params

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange OAuth authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token response with access_token, refresh_token, expires_in, etc.
        """
        if not self.client_id or not self.client_secret:
            raise ValueError("Airtable OAuth credentials not configured")

        token_url = "https://airtable.com/oauth2/v1/token"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=data)
                response.raise_for_status()

                token_data = response.json()

                # Store tokens
                self._access_token = token_data.get("access_token")
                _refresh_token = token_data.get("refresh_token")

                # Calculate token expiration
                if "expires_in" in token_data:
                    self._token_expires_at = datetime.now() + timedelta(
                        seconds=token_data["expires_in"]
                    )

                logger.info(f"Successfully obtained Airtable access token for workspace {self.workspace_id}")
                return token_data

        except httpx.HTTPStatusError as e:
            logger.error(f"Airtable token exchange failed: {e}")
            raise

    async def test_connection(self) -> bool:
        """
        Test the Airtable API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._access_token and not self.personal_access_token:
            return False

        token = self._access_token or self.personal_access_token

        try:
            async with httpx.AsyncClient() as client:
                # Test by getting user info
                response = await client.get(
                    f"{self.base_url}/v0/meta/whoami",
                    headers={
                        "Authorization": f"Bearer {token}"
                    }
                )
                response.raise_for_status()

                logger.info(f"Airtable connection test successful for workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Airtable connection test failed: {e}")
            return False

    async def list_bases(self) -> List[Dict[str, Any]]:
        """
        Retrieve all Airtable bases accessible to the user.

        Returns:
            List of base objects
        """
        token = self._access_token or self.personal_access_token
        if not token:
            raise ValueError("Airtable access token not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.airtable.com/v0/meta/bases",
                    headers={
                        "Authorization": f"Bearer {token}"
                    }
                )
                response.raise_for_status()

                data = response.json()
                bases = data.get("bases", [])

                logger.info(f"Retrieved {len(bases)} Airtable bases for workspace {self.workspace_id}")
                return bases

        except Exception as e:
            logger.error(f"Failed to retrieve Airtable bases: {e}")
            raise

    async def list_tables(self, base_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all tables in an Airtable base.

        Args:
            base_id: Base ID

        Returns:
            List of table objects with schema
        """
        token = self._access_token or self.personal_access_token
        if not token:
            raise ValueError("Airtable access token not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.airtable.com/v0/meta/bases/{base_id}/tables",
                    headers={
                        "Authorization": f"Bearer {token}"
                    }
                )
                response.raise_for_status()

                data = response.json()
                tables = data.get("tables", [])

                logger.info(f"Retrieved {len(tables)} Airtable tables for base {base_id}")
                return tables

        except Exception as e:
            logger.error(f"Failed to retrieve Airtable tables for base {base_id}: {e}")
            raise

    async def get_records(self, base_id: str, table_name: str,
                         filter_by_formula: str = None, sort: List[Dict] = None,
                         max_records: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve records from an Airtable table.

        Args:
            base_id: Base ID
            table_name: Table name or ID
            filter_by_formula: Airtable formula to filter records
            sort: List of sort objects [{"field": "Name", "direction": "asc"}]
            max_records: Maximum number of records to return

        Returns:
            List of record objects
        """
        token = self._access_token or self.personal_access_token
        if not token:
            raise ValueError("Airtable access token not configured")

        try:
            params = {"max_records": max_records}
            if filter_by_formula:
                params["filter_by_formula"] = filter_by_formula
            if sort:
                params["sort[]"] = [f"{s['field']}:{s.get('direction', 'asc')}" for s in sort]

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{base_id}/{table_name}",
                    headers={
                        "Authorization": f"Bearer {token}"
                    },
                    params=params
                )
                response.raise_for_status()

                data = response.json()
                records = data.get("records", [])

                logger.info(f"Retrieved {len(records)} Airtable records for workspace {self.workspace_id}")
                return records

        except Exception as e:
            logger.error(f"Failed to retrieve Airtable records: {e}")
            raise

    async def get_record(self, base_id: str, table_name: str, record_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific Airtable record by ID.

        Args:
            base_id: Base ID
            table_name: Table name or ID
            record_id: Record ID

        Returns:
            Record details with all fields
        """
        token = self._access_token or self.personal_access_token
        if not token:
            raise ValueError("Airtable access token not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{base_id}/{table_name}/{record_id}",
                    headers={
                        "Authorization": f"Bearer {token}"
                    }
                )
                response.raise_for_status()

                record = response.json()

                logger.info(f"Retrieved Airtable record {record_id} for workspace {self.workspace_id}")
                return record

        except Exception as e:
            logger.error(f"Failed to retrieve Airtable record {record_id}: {e}")
            raise

    async def create_record(self, base_id: str, table_name: str,
                           fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new Airtable record.

        Args:
            base_id: Base ID
            table_name: Table name or ID
            fields: Record field values

        Returns:
            Created record object with ID
        """
        token = self._access_token or self.personal_access_token
        if not token:
            raise ValueError("Airtable access token not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/{base_id}/{table_name}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "records": [
                            {
                                "fields": fields
                            }
                        ]
                    }
                )
                response.raise_for_status()

                data = response.json()
                record = data.get("records", [{}])[0]

                logger.info(f"Created Airtable record {record.get('id')} for workspace {self.workspace_id}")
                return record

        except Exception as e:
            logger.error(f"Failed to create Airtable record: {e}")
            raise

    async def update_record(self, base_id: str, table_name: str, record_id: str,
                           fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an Airtable record.

        Args:
            base_id: Base ID
            table_name: Table name or ID
            record_id: Record ID to update
            fields: Field values to update

        Returns:
            Updated record object
        """
        token = self._access_token or self.personal_access_token
        if not token:
            raise ValueError("Airtable access token not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/{base_id}/{table_name}/{record_id}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "fields": fields
                    }
                )
                response.raise_for_status()

                record = response.json()

                logger.info(f"Updated Airtable record {record_id} in workspace {self.workspace_id}")
                return record

        except Exception as e:
            logger.error(f"Failed to update Airtable record {record_id}: {e}")
            raise

    async def delete_record(self, base_id: str, table_name: str, record_id: str) -> bool:
        """
        Delete an Airtable record.

        Args:
            base_id: Base ID
            table_name: Table name or ID
            record_id: Record ID to delete

        Returns:
            True if successful
        """
        token = self._access_token or self.personal_access_token
        if not token:
            raise ValueError("Airtable access token not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/{base_id}/{table_name}/{record_id}",
                    headers={
                        "Authorization": f"Bearer {token}"
                    }
                )
                response.raise_for_status()

                logger.info(f"Deleted Airtable record {record_id} in workspace {self.workspace_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to delete Airtable record {record_id}: {e}")
            return False

    async def search_records(self, base_id: str, table_name: str,
                            field_name: str, search_value: str,
                            max_records: int = 20) -> List[Dict[str, Any]]:
        """
        Search Airtable records by field value.

        Args:
            base_id: Base ID
            table_name: Table name or ID
            field_name: Field to search in
            search_value: Value to search for
            max_records: Maximum number of results

        Returns:
            List of matching record objects
        """
        token = self._access_token or self.personal_access_token
        if not token:
            raise ValueError("Airtable access token not configured")

        try:
            # Build filter formula
            formula = f"FIND('{search_value}', LOWER({{{field_name}}})) > 0"

            return await self.get_records(
                base_id=base_id,
                table_name=table_name,
                filter_by_formula=formula,
                max_records=max_records
            )

        except Exception as e:
            logger.error(f"Failed to search Airtable records: {e}")
            raise
