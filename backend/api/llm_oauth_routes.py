"""
LLM OAuth 2.0 API Routes

REST API endpoints for OAuth authentication with LLM providers.
Supports Google AI Studio, OpenAI, Anthropic, and Hugging Face.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.llm_credential_service import LLMCredentialService
from core.llm_oauth_config import (
    get_provider_display_name,
    is_provider_oauth_configured,
    list_supported_providers
)
from core.llm_oauth_handler import LLMOAuthHandler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/llm/oauth", tags=["llm-oauth"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AuthorizeRequest(BaseModel):
    """Request to initiate OAuth flow"""
    provider_id: str = Field(..., description="Provider ID (google, openai, anthropic, huggingface)")
    redirect_uri: Optional[str] = Field(None, description="OAuth callback URL")


class AuthorizeResponse(BaseModel):
    """Response with OAuth authorization URL"""
    authorization_url: str
    state: str
    provider_id: str


class CallbackRequest(BaseModel):
    """OAuth callback request"""
    code: str = Field(..., description="Authorization code")
    state: str = Field(..., description="State parameter for CSRF protection")
    redirect_uri: Optional[str] = Field(None, description="Original redirect URI")


class CallbackResponse(BaseModel):
    """Response after successful OAuth callback"""
    success: bool
    credential_id: Optional[str] = None
    account_info: Optional[dict] = None
    message: str


class CredentialInfo(BaseModel):
    """OAuth credential information"""
    credential_id: str
    provider_id: str
    account_email: Optional[str] = None
    account_name: Optional[str] = None
    is_active: bool
    expires_at: Optional[str] = None
    last_used_at: Optional[str] = None
    usage_count: int
    created_at: str


class CredentialListResponse(BaseModel):
    """Response listing OAuth credentials"""
    credentials: list[CredentialInfo]


class RevokeResponse(BaseModel):
    """Response after revoking credential"""
    success: bool
    message: str


class RefreshResponse(BaseModel):
    """Response after refreshing credential"""
    success: bool
    expires_at: Optional[str] = None
    message: str


class ProviderStatusResponse(BaseModel):
    """Provider credential status"""
    provider_id: str
    has_oauth: bool
    has_byok: bool
    has_env: bool
    active_method: Optional[str] = None
    oauth_info: Optional[dict] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/providers", response_model=list[str])
async def list_providers():
    """
    List supported OAuth providers.

    Returns:
        List of provider IDs
    """
    return list_supported_providers()


@router.get("/providers/{provider_id}/status", response_model=ProviderStatusResponse)
async def get_provider_status(
    provider_id: str,
    request: Request
):
    """
    Get credential status for a provider.

    Checks OAuth, BYOK, and environment variable credentials.
    """
    # Get user context from request (adjust based on your auth system)
    user_id = getattr(request.state, "user_id", None)
    tenant_id = getattr(request.state, "tenant_id", None)
    workspace_id = getattr(request.state, "workspace_id", None)

    credential_service = LLMCredentialService(
        user_id=user_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id
    )

    status = credential_service.get_provider_status(provider_id)

    return ProviderStatusResponse(**status)


@router.post("/authorize", response_model=AuthorizeResponse)
async def authorize(
    request: AuthorizeRequest,
    req: Request
):
    """
    Initiate OAuth flow for a provider.

    Returns authorization URL and state parameter.
    User should be redirected to the authorization URL.
    """
    # Check if provider is supported
    if request.provider_id not in list_supported_providers():
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider: {request.provider_id}"
        )

    # Check if OAuth is configured
    if not is_provider_oauth_configured(request.provider_id):
        raise HTTPException(
            status_code=500,
            detail=f"OAuth not configured for provider: {request.provider_id}"
        )

    # Get user context
    user_id = getattr(req.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Generate authorization URL
    handler = LLMOAuthHandler()
    result = handler.get_authorization_url(
        provider_id=request.provider_id,
        redirect_uri=request.redirect_uri
    )

    return AuthorizeResponse(**result)


@router.post("/callback", response_model=CallbackResponse)
async def oauth_callback(
    request: CallbackRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """
    OAuth callback handler.

    Exchanges authorization code for tokens and stores credentials.
    """
    # Get user context
    user_id = getattr(req.state, "user_id", None)
    tenant_id = getattr(req.state, "tenant_id", None)

    if not user_id or not tenant_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Determine provider from state (you may want to store state in DB/Redis)
    # For now, we'll require provider_id in the request
    # TODO: Implement proper state validation with OAuthState model

    # Exchange code for tokens
    handler = LLMOAuthHandler()

    try:
        # For now, we need to determine provider_id from state or request
        # This is a simplified version - in production, validate state from DB
        provider_id = getattr(req.state, "oauth_provider_id", None)

        if not provider_id:
            raise HTTPException(
                status_code=400,
                detail="Could not determine provider from OAuth state"
            )

        tokens = await handler.exchange_code_for_tokens(
            provider_id=provider_id,
            code=request.code,
            redirect_uri=request.redirect_uri
        )

        # Store credentials
        credential = handler.store_oauth_credentials(
            user_id=user_id,
            tenant_id=tenant_id,
            provider_id=provider_id,
            tokens=tokens,
            account_info=None  # TODO: Fetch account info from provider if available
        )

        provider_name = get_provider_display_name(provider_id)

        return CallbackResponse(
            success=True,
            credential_id=credential.id,
            account_info={
                "email": credential.account_email,
                "name": credential.account_name,
            },
            message=f"Successfully connected to {provider_name}"
        )

    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"OAuth callback failed: {str(e)}"
        )


@router.get("/credentials", response_model=CredentialListResponse)
async def list_credentials(
    request: Request
):
    """
    List OAuth credentials for the current user.

    Returns all credentials (active and revoked).
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    credential_service = LLMCredentialService(user_id=user_id)
    credentials = credential_service.list_oauth_credentials()

    return CredentialListResponse(credentials=credentials)


@router.delete("/credentials/{credential_id}", response_model=RevokeResponse)
async def revoke_credential(
    credential_id: str,
    request: Request
):
    """
    Revoke an OAuth credential.

    Marks the credential as inactive and prevents future use.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    credential_service = LLMCredentialService(user_id=user_id)
    success = credential_service.revoke_oauth_credential(credential_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Credential not found: {credential_id}"
        )

    return RevokeResponse(
        success=True,
        message="Credential revoked successfully"
    )


@router.post("/credentials/{credential_id}/refresh", response_model=RefreshResponse)
async def refresh_credential(
    credential_id: str,
    request: Request
):
    """
    Refresh an OAuth credential.

    Forces token refresh even if not expired.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    credential_service = LLMCredentialService(user_id=user_id)
    success = await credential_service.refresh_oauth_credential(credential_id)

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to refresh credential"
        )

    return RefreshResponse(
        success=True,
        message="Credential refreshed successfully"
    )


@router.post("/credentials/{credential_id}/validate", response_model=ProviderStatusResponse)
async def validate_credential(
    credential_id: str,
    request: Request
):
    """
    Validate an OAuth credential.

    Checks if credential is valid and refreshes if needed.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # TODO: Implement credential validation
    # For now, just return success
    raise HTTPException(
        status_code=501,
        detail="Credential validation not yet implemented"
    )
