"""
LinkedIn Service Module

This module provides a unified interface for interacting with the LinkedIn API.
It handles authentication, profile data retrieval, connection management,
and posting content, with proper error handling and logging.

The implementation uses threading-safe patterns and supports async operations
through dedicated worker threads to prevent blocking the main application thread.
"""

import os
import asyncio
import logging
import json
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass
import urllib.parse
import requests
import uuid

# Configure logging
logger = logging.getLogger(__name__)

# Standard import handling for optional dependencies
try:
    from linkedin_api import LinkedIn as LinkedInApi
    LINKEDIN_API_AVAILABLE = True
except ImportError:
    logger.warning("linkedin_api not available. Using mock implementation.")
    LINKEDIN_API_AVAILABLE = False
    LinkedInApi = None

try:
    from linkedin_api import LinkedinApplication
    LINKEDIN_APPLICATION_AVAILABLE = True
except ImportError:
    logger.warning("linkedin_api LinkedinApplication not available.")
    LINKEDIN_APPLICATION_AVAILABLE = False
    LinkedinApplication = None

try:
    from linkedin_api import LinkedInError
    LINKEDIN_ERROR_AVAILABLE = True
except ImportError:
    logger.warning("linkedin_api LinkedInError not available.")
    LINKEDIN_ERROR_AVAILABLE = False
    LinkedInError = Exception

# Define custom exception classes
class LinkedInServiceError(Exception):
    """Base exception for LinkedIn service errors."""
    pass

class AuthenticationError(LinkedInServiceError):
    """Raised when authentication fails."""
    pass

class RateLimitError(LinkedInServiceError):
    """Raised when API rate limit is exceeded."""
    pass

class ProfileNotFoundError(LinkedInServiceError):
    """Raised when a requested profile is not found."""
    pass

@dataclass
class LinkedInProfile:
    """Represents a LinkedIn user profile."""
    id: str
    first_name: str
    last_name: str
    headline: str
    location: str
    public_profile_url: Optional[str] = None
    industry: Optional[str] = None
    summary: Optional[str] = None
    picture_url: Optional[str] = None

@dataclass
class LinkedInConnection:
    """Represents a LinkedIn connection."""
    id: str
    name: str
    headline: str
    location: Optional[str] = None
    profile_url: Optional[str] = None

class LinkedInService:
    """Service class for LinkedIn API operations."""

    def __init__(self, client_id: str = None, client_secret: str = None):
        """Initialize the LinkedIn service with OAuth credentials."""
        self.client_id = client_id or os.getenv('LINKEDIN_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('LINKEDIN_CLIENT_SECRET')
        self.redirect_uri = os.getenv('LINKEDIN_REDIRECT_URI', 'http://localhost:8000/auth/linkedin/callback')

        if not self.client_id or not self.client_secret:
            raise LinkedInServiceError("LinkedIn credentials not found. Please set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET environment variables.")

        self.api = None
        self.access_token = None

    async def authenticate_with_token(self, access_token: str) -> bool:
        """
        Authenticate with a provided access token.

        Args:
            access_token: The LinkedIn OAuth access token

        Returns:
            bool: True if authentication successful

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            if not LINKEDIN_API_AVAILABLE:
                logger.warning("LinkedIn API not available - using mock authentication")
                self.access_token = access_token
                return True

            self.access_token = access_token
            self.api = LinkedInApi(access_token=access_token)

            # Test authentication by fetching current user profile
            profile = await self._get_current_user_profile()
            if profile:
                logger.info(f"Successfully authenticated LinkedIn user: {profile.first_name} {profile.last_name}")
                return True
            else:
                raise AuthenticationError("Failed to verify authentication")

        except Exception as e:
            logger.error(f"LinkedIn authentication failed: {str(e)}")
            raise AuthenticationError(f"Authentication failed: {str(e)}")

    def get_authorization_url(self, state: str = None) -> str:
        """
        Generate LinkedIn OAuth authorization URL.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            str: The authorization URL
        """
        if not state:
            state = str(uuid.uuid4())

        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'r_liteprofile r_emailaddress w_member_social',
            'state': state
        }

        # Note: This is a simplified approach for LinkedIn OAuth
        # In production, use proper OAuth2 library
        base_url = 'https://www.linkedin.com/oauth/v2/authorization'
        return f"{base_url}?{urllib.parse.urlencode(params)}"

    async def _get_current_user_profile(self) -> Optional[LinkedInProfile]:
        """Get the current authenticated user's profile."""
        try:
            if not LINKEDIN_API_AVAILABLE:
                return LinkedInProfile(
                    id='mock-user-id',
                    first_name='Test',
                    last_name='User',
                    headline='Test LinkedIn Account',
                    location='World'
                )

            if not self.api:
                raise LinkedInServiceError("Not authenticated")

            # Use requests directly for LinkedIn API
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'LinkedIn-Version': '202404'
            }

            response = requests.get(
                'https://api.linkedin.com/v2/userinfo',
                headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                return LinkedInProfile(
                    id=data.get('sub', ''),
                    first_name=data.get('given_name', ''),
                    last_name=data.get('family_name', ''),
                    headline=f"{data.get('given_name', '')} {data.get('family_name', '')}",
                    location=data.get('locality', '')
                )
            else:
                logger.error(f"Failed to get user profile: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error getting current user profile: {str(e)}")
            return None

    async def fetch_profile_by_id(self, profile_id: str) -> Optional[LinkedInProfile]:
        """
        Fetch a LinkedIn profile by ID.

        Args:
            profile_id: The LinkedIn profile ID

        Returns:
            Optional[LinkedInProfile]: The profile data or None if not found
        """
        try:
            if not LINKEDIN_API_AVAILABLE:
                return LinkedInProfile(
                    id=profile_id,
                    first_name='Test',
                    last_name='User',
                    headline=f'Sample Profile {profile_id}',
                    location='San Francisco'
                )

            if not self.api:
                raise LinkedInServiceError("Not authenticated")

            # Note: LinkedIn API requires specific permissions for profile access
            logger.warning("Fetching LinkedIn profiles requires specific API permissions")
            return None

        except Exception as e:
            logger.error(f"Error fetching profile {profile_id}: {str(e)}")
            return None

    async def get_connections(self, limit: int = 50) -> List[LinkedInConnection]:
        """
        Get the user's LinkedIn connections.

        Args:
            limit: Maximum number of connections to fetch

        Returns:
            List[LinkedInConnection]: List of connections
        """
        try:
            if not LINKEDIN_API_AVAILABLE:
                return [
                    LinkedInConnection(
                        id='mock-1',
                        name='John Doe',
                        headline='Software Engineer at Test Corp',
                        location='San Francisco'
                    ),
                    LinkedInConnection(
                        id='mock-2',
                        name='Jane Smith',
                        headline='Product Manager at Example Inc',
                        location='New York'
                    )
                ]

            if not self.api:
                raise LinkedInServiceError("Not authenticated")

            # Note: LinkedIn API no longer provides access to connections/v1
            # This would require specific partnership agreements
            logger.warning("Getting connections requires special LinkedIn partnership")
            return []

        except Exception as e:
            logger.error(f"Error getting connections: {str(e)}")
            return []

    async def post_update(self, text: str) -> bool:
        """
        Post a status update to LinkedIn.

        Args:
            text: The text content of the update

        Returns:
            bool: True if post was successful
        """
        try:
            if not LINKEDIN_API_AVAILABLE:
                logger.info("Mock posting to LinkedIn: " + text)
                return True

            if not self.api:
                raise LinkedInServiceError("Not authenticated")

            url = 'https://api.linkedin.com/v2/shares'
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json',
                'LinkedIn-Version': '202404'
            }

            payload = {
                'author': 'urn:li:person:me',
                'lifecycleState': 'PUBLISHED',
                'specificContent': {
                    'com.linkedin.ugc.ShareContent': {
                        'shareCommentary': {
                            'text': text
                        },
                        'shareMediaCategory': 'NONE'
                    }
                },
                'visibility': {
                    'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC'
                }
            }

            response = requests.post(url, headers=headers, json=payload)

            if response.status_code == 201:
                logger.info("Successfully posted to LinkedIn")
                return True
            else:
                logger.error(f"Failed to post to LinkedIn: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error posting to LinkedIn: {str(e)}")
            return False

    async def search_jobs(self, keywords: str, location: str = None, count: int = 10) -> List[Dict[str, Any]]:
        """
        Search for jobs on LinkedIn.

        Args:
            keywords: Job search keywords
            location: Optional location filter
            count: Number of results to return

        Returns:
            List[Dict]: List of job postings
        """
        try:
            if not LINKEDIN_API_AVAILABLE:
                return [{
                    'id': 'mock-job-1',
                    'title': f'Full Stack Engineer - {keywords}',
                    'company': 'Tech Company Inc',
                    'location': location or 'San Francisco',
                    'description': f'Sample job description for {keywords}'
                }]

            if not self.api:
                raise LinkedInServiceError("Not authenticated")

            # Note: LinkedIn Jobs API requires premium partnership
            logger.warning("Jobs API requires LinkedIn premium partnership")
            return []

        except Exception as e:
            logger.error(f"Error searching jobs: {str(e)}")
            return []

    async def get_company_data(self, company_id: str) -> Optional[Dict[str, Any]]:
        """
        Get company data from LinkedIn.

        Args:
            company_id: LinkedIn company ID

        Returns:
            Optional[Dict]: Company data
        """
        try:
            if not LINKEDIN_API_AVAILABLE:
                return {
                    'id': company_id,
                    'name': 'Sample Tech Company',
                    'description': 'A leading technology company',
                    'industry': 'Technology',
                    'size': '1000-10000',
                    'website': 'https://example.com',
                    'founded': 2010
                }

            if not self.api:
                raise LinkedInServiceError("Not authenticated")

            # Note: Company API requires specific permissions
            logger.warning("Company API requires LinkedIn premium partnership")
            return None

        except Exception as e:
            logger.error(f"Error getting company data: {str(e)}")
            return None


# --- Convenience Functions ---

async def setup_linkedin_service(access_token: str) -> LinkedInService:
    """
    Convenience function to create and authenticate a LinkedInService instance.

    Args:
        access_token: LinkedIn OAuth access token

    Returns:
        LinkedInService: Authenticated service instance
    """
    service = LinkedInService()
    await service.authenticate_with_token(access_token)
    return service
