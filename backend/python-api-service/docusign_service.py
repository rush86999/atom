# Mock Docusign service for development
# This provides mock implementations for Docusign API functionality

import os
import logging
from typing import Optional, Dict, Any
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MockApiClient:
    """Mock ApiClient for Docusign integration"""

    def __init__(self):
        self.host = None
        self.headers = {}

    def set_default_header(self, key: str, value: str):
        """Mock method to set headers"""
        self.headers[key] = value

class MockEnvelopesApi:
    """Mock EnvelopesApi for Docusign integration"""

    def __init__(self, client):
        self.client = client

    def create_envelope(self, account_id: str, envelope_definition: Dict[str, Any]) -> 'MockEnvelope':
        """Mock method to create envelope"""
        envelope_id = f"env_{uuid.uuid4().hex[:8]}"
        return MockEnvelope(envelope_id, envelope_definition)

    def get_envelope(self, account_id: str, envelope_id: str) -> 'MockEnvelope':
        """Mock method to get envelope"""
        # Return a mock envelope with the given ID
        return MockEnvelope(envelope_id, {})

class MockEnvelope:
    """Mock Envelope object"""

    def __init__(self, envelope_id: str, definition: Dict[str, Any]):
        self.envelope_id = envelope_id
        self.status = "sent"
        self.created_date_time = datetime.now().isoformat()
        self.last_modified_date_time = datetime.now().isoformat()
        self.definition = definition

    def to_dict(self) -> Dict[str, Any]:
        """Convert envelope to dictionary"""
        return {
            "envelope_id": self.envelope_id,
            "status": self.status,
            "created_date_time": self.created_date_time,
            "last_modified_date_time": self.last_modified_date_time,
            "definition": self.definition
        }

# Mock API classes for compatibility
ApiClient = MockApiClient
EnvelopesApi = MockEnvelopesApi

async def get_docusign_client(user_id: str, db_conn_pool) -> Optional[MockApiClient]:
    """Mock function to get Docusign client"""
    # In development mode, return a mock client without requiring real credentials
    access_token = os.environ.get("DOCUSIGN_ACCESS_TOKEN", "mock_docusign_access_token")
    account_id = os.environ.get("DOCUSIGN_ACCOUNT_ID", "mock_account_id")
    base_path = os.environ.get("DOCUSIGN_BASE_PATH", "https://demo.docusign.net/restapi/v2.1")

    if not all([access_token, account_id, base_path]):
        logger.warning("Docusign credentials not configured, using mock client")

    api_client = MockApiClient()
    api_client.host = base_path
    api_client.set_default_header("Authorization", f"Bearer {access_token}")

    return api_client

async def create_envelope(client: MockApiClient, envelope_definition: Dict[str, Any]) -> Dict[str, Any]:
    """Mock function to create envelope"""
    try:
        envelopes_api = MockEnvelopesApi(client)
        results = envelopes_api.create_envelope(
            os.environ.get("DOCUSIGN_ACCOUNT_ID", "mock_account_id"),
            envelope_definition
        )
        return results.to_dict()
    except Exception as e:
        logger.error(f"Error creating envelope: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }

async def get_envelope_status(client: MockApiClient, envelope_id: str) -> str:
    """Mock function to get envelope status"""
    try:
        envelopes_api = MockEnvelopesApi(client)
        results = envelopes_api.get_envelope(
            os.environ.get("DOCUSIGN_ACCOUNT_ID", "mock_account_id"),
            envelope_id
        )
        return results.status
    except Exception as e:
        logger.error(f"Error getting envelope status: {e}")
        return "error"

async def get_envelope(client: MockApiClient, envelope_id: str) -> Dict[str, Any]:
    """Mock function to get envelope"""
    try:
        envelopes_api = MockEnvelopesApi(client)
        results = envelopes_api.get_envelope(
            os.environ.get("DOCUSIGN_ACCOUNT_ID", "mock_account_id"),
            envelope_id
        )
        return results.to_dict()
    except Exception as e:
        logger.error(f"Error getting envelope: {e}")
        return {
            "error": str(e),
            "envelope_id": envelope_id
        }

# Mock envelope statuses for testing
MOCK_ENVELOPE_STATUSES = [
    "created",
    "sent",
    "delivered",
    "completed",
    "declined",
    "voided"
]

def get_mock_envelope_template() -> Dict[str, Any]:
    """Get a mock envelope template for development"""
    return {
        "email_subject": "Please sign this document",
        "documents": [
            {
                "document_id": "1",
                "name": "Sample Document.pdf",
                "file_extension": "pdf",
                "document_base64": "mock_base64_content"
            }
        ],
        "recipients": {
            "signers": [
                {
                    "email": "signer@example.com",
                    "name": "John Doe",
                    "recipient_id": "1",
                    "routing_order": "1"
                }
            ]
        },
        "status": "sent"
    }
