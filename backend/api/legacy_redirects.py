from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter(tags=["Legacy Redirects"])

@router.get("/api/integrations/{provider}/authorize")
async def legacy_authorize_redirect(provider: str):
    """
    Catch-all redirect for legacy integration authorization paths.
    Redirects to the unified OAuth initiation endpoint.
    """
    return RedirectResponse(url=f"/api/v1/auth/oauth/{provider}/initiate")
