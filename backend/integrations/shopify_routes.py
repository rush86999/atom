from datetime import datetime
import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Optional
from urllib.parse import urlencode

from ecommerce.models import EcommerceStore
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import User

from .shopify_service import ShopifyService

logger = logging.getLogger(__name__)

# Auth Type: OAuth2
router = APIRouter(prefix="/api/shopify", tags=["shopify"])

# OAuth state validity window (seconds). Short so a leaked state token can't be
# replayed for long; long enough for the Shopify authorize round-trip.
_STATE_TTL_SECONDS = 600


def _env_or_die(name: str) -> str:
    """Return env var value or raise 500 (Shopify OAuth misconfiguration)."""
    val = os.getenv(name, "")
    if not val:
        raise HTTPException(
            status_code=500,
            detail=f"Shopify OAuth not configured. Please set {name} in the backend environment."
        )
    return val


def _shopify_state_secret() -> str:
    """Secret used to sign the OAuth ``state`` so the callback can verify that
    the merchant came back from the same authorize request. Falls back to the
    app SECRET_KEY when SHOPIFY_STATE_SECRET is unset (test/dev)."""
    secret = os.getenv("SHOPIFY_STATE_SECRET") or os.getenv("SECRET_KEY") or ""
    if not secret:
        raise HTTPException(status_code=500, detail="Shopify OAuth not configured. SECRET_KEY missing.")
    return secret


def _sign_state(user_id: str, workspace_id: str, shop: str) -> str:
    """Return a signed, single-use OAuth state token.

    Binds the authorize request to the user, workspace, AND the target shop,
    with a random nonce and an expiry. The nonce makes each state one-time-only
    (a previously-issued state cannot be replayed with a fresh code against
    another shop), and the expiry bounds reuse."""
    nonce = secrets.token_hex(16)
    exp = str(int(time.time()) + _STATE_TTL_SECONDS)
    # '|'-separated payload; shop may contain dots so we never split state on '.'.
    payload = f"{user_id}|{workspace_id}|{shop}|{nonce}|{exp}"
    sig = hmac.new(_shopify_state_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{sig}.{payload}"


def _verify_state(state: str, expected_shop: Optional[str] = None) -> tuple:
    """Verify a signed OAuth state token.

    Returns ``(user_id, workspace_id)`` or raises 400. Rejects expired states,
    tampered signatures, and states bound to a different shop than the one the
    callback received (cross-shop replay)."""
    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state")
    if "." not in state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    sig, payload = state.split(".", 1)
    parts = payload.split("|")
    if len(parts) != 5:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    user_id, workspace_id, shop, nonce, exp = parts
    expected = hmac.new(_shopify_state_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    try:
        if int(exp) < int(time.time()):
            raise HTTPException(status_code=400, detail="OAuth state expired")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    if expected_shop is not None:
        norm_expected = expected_shop if expected_shop.endswith(".myshopify.com") else f"{expected_shop}.myshopify.com"
        if shop != norm_expected:
            raise HTTPException(status_code=400, detail="OAuth state shop mismatch")
    return user_id, workspace_id


def _redirect_base_url() -> str:
    """Public base URL for Shopify's browser redirect (NOT the user's machine).

    Resolved from deployment config: ATOM_PUBLIC_URL -> ATOM_BASE_URL ->
    PYTHON_BACKEND_URL -> NEXT_PUBLIC_API_URL. Fails closed (no loopback
    fallback) unless SHOPIFY_DEV_LOOPBACK=1 is explicitly set for local dev."""
    if os.getenv("SHOPIFY_DEV_LOOPBACK", "").lower() in ("1", "true", "yes", "on"):
        return os.getenv("SHOPIFY_DEV_BASE_URL", "http://localhost:8000").rstrip("/")
    for name in ("ATOM_PUBLIC_URL", "ATOM_BASE_URL", "PYTHON_BACKEND_URL", "NEXT_PUBLIC_API_URL"):
        val = os.getenv(name, "").strip()
        if val:
            return val.rstrip("/")
    raise HTTPException(
        status_code=500,
        detail="Shopify OAuth not configured: no public ATOM URL set. "
               "Set ATOM_PUBLIC_URL (or SHOPIFY_DEV_LOOPBACK=1 for local dev)."
    )


def _callback_url() -> str:
    return f"{_redirect_base_url()}/api/shopify/auth/callback"

@router.get("/auth/url")
async def get_auth_url(
    shop: str = Query(..., description="Shop name (e.g. my-great-store)"),
    current_user: User = Depends(get_current_user),
):
    """Get Shopify OAuth URL for a shop (authenticated).

    Builds a signed OAuth ``state`` bound to the authenticated user + their
    workspace so the callback can verify the merchant is the same principal.
    The redirect URI is derived from deployment config, never hardcoded to a
    local machine. Requires SHOPIFY_API_KEY / SHOPIFY_API_SECRET env vars.
    """
    client_id = _env_or_die("SHOPIFY_API_KEY")
    _env_or_die("SHOPIFY_API_SECRET")
    shop_url = shop if shop.endswith(".myshopify.com") else f"{shop}.myshopify.com"
    scopes = "read_products,write_products,read_content,write_content,read_orders,read_customers,write_orders,write_draft_orders"
    workspace_id = getattr(current_user, "workspace_id", None) or "default"
    params = {
        "client_id": client_id,
        "scope": scopes,
        "redirect_uri": _callback_url(),
        "state": _sign_state(str(current_user.id), workspace_id, shop_url),
    }
    url = f"https://{shop_url}/admin/oauth/authorize?{urlencode(params)}"
    return {
        "url": url,
        "shop": shop_url,
        "configured": True,
        "timestamp": datetime.now().isoformat()
    }

@router.get("/connection")
async def shopify_connection(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Whether a Shopify store is connected for the caller's workspace."""
    from ecommerce.models import EcommerceStore as EcommerceStoreModel
    ws_id = getattr(current_user, "workspace_id", None) or "default"
    store = db.query(EcommerceStoreModel).filter(
        EcommerceStoreModel.tenant_id == ws_id
    ).first()
    if not store or not store.access_token:
        return {"ok": True, "connected": False, "shop": None}
    return {"ok": True, "connected": True, "shop": store.shop_domain}

# Initialize service
shopify_service = ShopifyService()

class ShopifyAuthRequest(BaseModel):
    code: str
    shop: str
    workspace_id: str = "default"

class ProductCreateRequest(BaseModel):
    title: str
    body_html: str = ""
    vendor: str = ""
    product_type: str = ""
    tags: str = ""
    handle: str = ""
    status: str = "active"
    variants: list = []
    images: list = []

class BlogCreateRequest(BaseModel):
    title: str
    handle: str = ""

class ArticleCreateRequest(BaseModel):
    title: str
    body_html: str
    author: str = ""
    tags: str = ""
    published: bool = True

@router.get("/auth/callback")
async def shopify_auth_callback_get(
    code: str = Query(...),
    state: str = Query(...),
    shop: str = Query(""),
    hmac: str = Query(""),
    db: Session = Depends(get_db),
):
    """OAuth callback — browser GET redirect from Shopify.

    Validates the signed ``state`` (bound to the authenticated user + workspace
    from the authorize step), then exchanges ``code`` for an access token and
    persists the store under that verified workspace. Redirects the merchant's
    browser back to the frontend connect page on success/failure.
    """
    # 2. Exchange the code for an access token.
    if not shop:
        # Shopify sends the shop domain in the state-verified authorize flow via
        # the shop query param; require it.
        raise HTTPException(status_code=400, detail="Missing shop parameter")

    # 3. Verify OAuth state -> recover the owning user + workspace, AND enforce
    #    that the state was issued for THIS shop (blocks cross-shop replay:
    #    reusing an old state token with a fresh code for a different store).
    #    No client-supplied workspace is trusted — it comes from the signed state.
    try:
        user_id, workspace_id = _verify_state(state, expected_shop=shop)
    except HTTPException:
        logger.warning(f"Shopify callback: state verification failed for shop {shop}")
        return _redirect_connect(connected=False, shop=shop)

    # 4. Exchange the code for an access token.
    try:
        token_data = await shopify_service.exchange_token(code, shop)
    except Exception:
        logger.error("Shopify token exchange failed in callback")
        return _redirect_connect(connected=False, shop=shop)

    access_token = token_data.get("access_token")
    if not access_token:
        logger.error("Shopify callback: no access_token returned")
        return _redirect_connect(connected=False, shop=shop)

    # 5. Persist the store, scoped to the verified workspace. Refuse to
    #    reassign a store already owned by a DIFFERENT workspace.
    store = db.query(EcommerceStore).filter(
        EcommerceStore.shop_domain == shop
    ).first()
    if store is not None:
        existing_owner = store.tenant_id or "default"
        if existing_owner != workspace_id:
            logger.warning(
                f"Shopify callback: refusing to reassign store {shop} "
                f"(owner {existing_owner} != verified {workspace_id})"
            )
            return _redirect_connect(connected=False, shop=shop)
        store.access_token = access_token
        store_meta = dict(store.metadata_json or {})
        store_meta["workspace_id"] = workspace_id
        store.metadata_json = store_meta
    else:
        store = EcommerceStore(
            shop_domain=shop,
            access_token=access_token,
            platform="shopify",
            tenant_id=workspace_id,
            metadata_json={"workspace_id": workspace_id},
        )
        db.add(store)
    db.commit()

    logger.info(f"Shopify store {shop} connected for workspace {workspace_id}")
    return _redirect_connect(connected=True, shop=shop)


def _redirect_connect(connected: bool, shop: str) -> RedirectResponse:
    """Redirect the merchant's browser to the frontend Shopify connect page with
    the result encoded in the query string (frontend clears the stored state)."""
    frontend = os.getenv("FRONTEND_URL") or _redirect_base_url().replace("/api", "") or "http://localhost:3000"
    params = {"connected": "true" if connected else "false", "shop": shop}
    return RedirectResponse(f"{frontend}/integrations/shopify?{urlencode(params)}", status_code=303)


@router.post("/auth/callback")
async def shopify_auth_callback_post(
    auth_request: ShopifyAuthRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """OAuth callback — authenticated JSON alternative for non-browser clients.

    Accepts the client's token as the identity source (state is implicit in the
    authenticated principal). Ownership is still enforced: an existing store
    owned by a different workspace is never reassigned.
    """
    try:
        workspace_id = getattr(current_user, "workspace_id", None) or "default"
        token_data = await shopify_service.exchange_token(auth_request.code, auth_request.shop)
        access_token = token_data["access_token"]

        store = db.query(EcommerceStore).filter(
            EcommerceStore.shop_domain == auth_request.shop
        ).first()
        if store is not None:
            existing_owner = store.tenant_id or "default"
            if existing_owner != workspace_id:
                raise HTTPException(status_code=403, detail="Store belongs to another workspace")
            store.access_token = access_token
            store_meta = dict(store.metadata_json or {})
            store_meta["workspace_id"] = workspace_id
            store.metadata_json = store_meta
        else:
            store = EcommerceStore(
                shop_domain=auth_request.shop,
                access_token=access_token,
                platform="shopify",
                tenant_id=workspace_id,
                metadata_json={"workspace_id": workspace_id},
            )
            db.add(store)
        db.commit()

        return {
            "ok": True,
            "access_token": access_token,
            "scope": token_data.get("scope"),
            "service": "shopify",
            "workspace_id": workspace_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Shopify callback error: {e}")
        raise HTTPException(status_code=400, detail="Internal error")

@router.get("/shop")
async def get_shop_info(
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain (e.g. my-shop.myshopify.com)")
):
    """Get shop information"""
    info = await shopify_service.get_shop_info(access_token, shop)
    return {"ok": True, "data": info}

@router.get("/products")
async def list_products(
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
    limit: int = Query(20, ge=1, le=100)
):
    """List Shopify products"""
    products = await shopify_service.get_products(access_token, shop, limit)
    return {"ok": True, "data": products, "count": len(products)}

@router.post("/products")
async def create_product(
    request: ProductCreateRequest,
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
):
    """Create a Shopify product listing (agent-driven)."""
    payload = request.model_dump(exclude_none=True)
    product = await shopify_service.create_product(access_token, shop, payload)
    return {"ok": True, "data": product}

@router.get("/blogs")
async def list_blogs(
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
):
    """List Shopify blogs"""
    blogs = await shopify_service.list_blogs(access_token, shop)
    return {"ok": True, "data": blogs, "count": len(blogs)}

@router.post("/blogs")
async def create_blog(
    request: BlogCreateRequest,
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
):
    """Create a Shopify blog"""
    blog = await shopify_service.create_blog(access_token, shop, request.title, request.handle or None)
    return {"ok": True, "data": blog}

@router.get("/blogs/{blog_id}/articles")
async def list_articles(
    blog_id: str,
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
    limit: int = Query(20, ge=1, le=100)
):
    """List articles in a Shopify blog"""
    articles = await shopify_service.list_articles(access_token, shop, blog_id, limit)
    return {"ok": True, "data": articles, "count": len(articles)}

@router.post("/blogs/{blog_id}/articles")
async def create_article(
    blog_id: str,
    request: ArticleCreateRequest,
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
):
    """Create a Shopify blog article (post)"""
    article = await shopify_service.create_article(
        access_token, shop, blog_id,
        title=request.title,
        body_html=request.body_html,
        author=request.author or None,
        tags=request.tags or None,
        published=request.published,
    )
    return {"ok": True, "data": article}

@router.get("/orders")
async def list_orders(
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
    limit: int = Query(20, ge=1, le=100)
):
    """List Shopify orders"""
    orders = await shopify_service.get_orders(access_token, shop, limit)
    return {"ok": True, "data": orders, "count": len(orders)}

@router.get("/status")
async def shopify_status():
    """Get Shopify integration status"""
    return {
        "ok": True,
        "service": "shopify",
        "status": "active",
        "version": "1.0.0",
        "mode": "real"
    }

@router.post("/webhooks/setup")
async def setup_shopify_webhooks(
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
    webhook_base_url: str = Query(..., description="Base URL for webhooks (e.g. https://your-domain.com/api/webhooks/shopify)")
):
    """Register all required webhooks for this shop"""
    # SSRF guard: validate webhook_base_url doesn't point to internal/private IPs
    from core.ssrf_guard import validate_url, SSRFError
    try:
        validate_url(webhook_base_url)
    except SSRFError as e:
        raise HTTPException(status_code=400, detail="Invalid webhook configuration")
    results = await shopify_service.register_webhooks(access_token, shop, webhook_base_url)
    return {"ok": True, "results": results}

@router.get("/")
async def shopify_root():
    """Shopify integration root endpoint"""
    return {
        "service": "shopify",
        "status": "active",
        "endpoints": [
            "/auth/callback",
            "/shop",
            "/products",
            "/orders",
            "/customers",
            "/customers/search",
            "/fulfillments/{order_id}",
            "/refunds/{order_id}",
            "/draft-orders",
            "/transactions/{order_id}",
            "/analytics",
            "/blogs",
            "/blogs/{blog_id}/articles",
            "/webhooks/setup",
            "/status"
        ]
    }

# ==================== FULL BUSINESS LIFECYCLE ROUTES ====================

# --- CUSTOMERS ---
@router.get("/customers")
async def list_customers(
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
    limit: int = Query(20, ge=1, le=100)
):
    """List Shopify customers"""
    customers = await shopify_service.get_customers(access_token, shop, limit)
    return {"ok": True, "data": customers, "count": len(customers)}

@router.get("/customers/search")
async def search_customers(
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
    query: str = Query(..., description="Search query (email, name, etc.)")
):
    """Search customers"""
    customers = await shopify_service.search_customers(access_token, shop, query)
    return {"ok": True, "data": customers, "count": len(customers)}

@router.get("/customers/{customer_id}")
async def get_customer(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain")
):
    """Get a specific customer"""
    customer = await shopify_service.get_customer(access_token, shop, customer_id)
    return {"ok": True, "data": customer}

# --- FULFILLMENTS ---
@router.get("/fulfillments/{order_id}")
async def get_fulfillments(
    order_id: str,
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain")
):
    """Get fulfillments for an order"""
    fulfillments = await shopify_service.get_fulfillments(access_token, shop, order_id)
    return {"ok": True, "data": fulfillments, "count": len(fulfillments)}

@router.post("/fulfillments/{order_id}")
async def create_fulfillment(
    order_id: str,
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
    location_id: str = Query(..., description="Location ID"),
    tracking_number: str = Query(None, description="Tracking Number"),
    tracking_company: str = Query(None, description="Tracking Company")
):
    """Create a fulfillment for an order"""
    result = await shopify_service.create_fulfillment(
        access_token, shop, order_id, location_id, tracking_number, tracking_company
    )
    return {"ok": True, "data": result}

# --- REFUNDS ---
@router.get("/refunds/{order_id}")
async def get_refunds(
    order_id: str,
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain")
):
    """Get refunds for an order"""
    refunds = await shopify_service.get_refunds(access_token, shop, order_id)
    return {"ok": True, "data": refunds, "count": len(refunds)}

# --- DRAFT ORDERS ---
@router.get("/draft-orders")
async def list_draft_orders(
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
    limit: int = Query(20, ge=1, le=100)
):
    """List draft orders"""
    drafts = await shopify_service.get_draft_orders(access_token, shop, limit)
    return {"ok": True, "data": drafts, "count": len(drafts)}

@router.post("/draft-orders/{draft_id}/complete")
async def complete_draft_order(
    draft_id: str,
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain")
):
    """Convert draft order to real order"""
    result = await shopify_service.complete_draft_order(access_token, shop, draft_id)
    return {"ok": True, "data": result}

# --- TRANSACTIONS ---
@router.get("/transactions/{order_id}")
async def get_transactions(
    order_id: str,
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain")
):
    """Get transactions for an order"""
    transactions = await shopify_service.get_transactions(access_token, shop, order_id)
    return {"ok": True, "data": transactions, "count": len(transactions)}

# --- ANALYTICS ---
@router.get("/analytics")
async def get_shop_analytics(
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain")
):
    """Get comprehensive shop analytics"""
    analytics = await shopify_service.get_shop_analytics(access_token, shop)
    return {"ok": True, "data": analytics}

@router.get("/inventory")
async def get_inventory(
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
    location_id: str = Query(None, description="Filter by location")
):
    """Get inventory levels"""
    inventory = await shopify_service.get_inventory_levels(access_token, shop, location_id)
    return {"ok": True, "data": inventory, "count": len(inventory)}

@router.get("/locations")
async def get_locations(
    current_user: User = Depends(get_current_user),
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain")
):
    """Get shop locations"""
    locations = await shopify_service.get_locations(access_token, shop)
    return {"ok": True, "data": locations, "count": len(locations)}
