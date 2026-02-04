from ecommerce.models import EcommerceStore
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db

from .shopify_service import ShopifyService

logger = logging.getLogger(__name__)

# Auth Type: OAuth2
router = APIRouter(prefix="/api/shopify", tags=["shopify"])

@router.get("/auth/url")
async def get_auth_url():
    """Get Shopify OAuth URL"""
    return {
        "url": "https://{shop}.myshopify.com/admin/oauth/authorize?client_id=INSERT_CLIENT_ID&scope=read_products,read_orders,write_webhooks&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fshopify%2Fcallback",
        "timestamp": datetime.now().isoformat()
    }

# Initialize service
shopify_service = ShopifyService()

class ShopifyAuthRequest(BaseModel):
    code: str
    shop: str
    workspace_id: str = "default"

@router.post("/auth/callback")
async def shopify_auth_callback(auth_request: ShopifyAuthRequest, db: Session = Depends(get_db)):
    """Exchange authorization code for access token and save store"""
    try:
        token_data = await shopify_service.exchange_token(auth_request.code, auth_request.shop)
        access_token = token_data["access_token"]
        
        # Save or update EcommerceStore
        store = db.query(EcommerceStore).filter(
            EcommerceStore.shop_domain == auth_request.shop
        ).first()
        
        if not store:
            store = EcommerceStore(
                workspace_id=auth_request.workspace_id,
                shop_domain=auth_request.shop,
                access_token=access_token,
                platform="shopify"
            )
            db.add(store)
        else:
            store.access_token = access_token
            store.workspace_id = auth_request.workspace_id
            
        db.commit()
        
        return {
            "ok": True,
            "access_token": access_token,
            "scope": token_data.get("scope"),
            "service": "shopify",
            "workspace_id": auth_request.workspace_id
        }
    except Exception as e:
        logger.error(f"Shopify callback error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/shop")
async def get_shop_info(
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain (e.g. my-shop.myshopify.com)")
):
    """Get shop information"""
    info = await shopify_service.get_shop_info(access_token, shop)
    return {"ok": True, "data": info}

@router.get("/products")
async def list_products(
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
    limit: int = Query(20, ge=1, le=100)
):
    """List Shopify products"""
    products = await shopify_service.get_products(access_token, shop, limit)
    return {"ok": True, "data": products, "count": len(products)}

@router.get("/orders")
async def list_orders(
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
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
    webhook_base_url: str = Query(..., description="Base URL for webhooks (e.g. https://your-domain.com/api/webhooks/shopify)")
):
    """Register all required webhooks for this shop"""
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
            "/webhooks/setup",
            "/status"
        ]
    }

# ==================== FULL BUSINESS LIFECYCLE ROUTES ====================

# --- CUSTOMERS ---
@router.get("/customers")
async def list_customers(
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
    limit: int = Query(20, ge=1, le=100)
):
    """List Shopify customers"""
    customers = await shopify_service.get_customers(access_token, shop, limit)
    return {"ok": True, "data": customers, "count": len(customers)}

@router.get("/customers/search")
async def search_customers(
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
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain")
):
    """Get fulfillments for an order"""
    fulfillments = await shopify_service.get_fulfillments(access_token, shop, order_id)
    return {"ok": True, "data": fulfillments, "count": len(fulfillments)}

@router.post("/fulfillments/{order_id}")
async def create_fulfillment(
    order_id: str,
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
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain")
):
    """Get refunds for an order"""
    refunds = await shopify_service.get_refunds(access_token, shop, order_id)
    return {"ok": True, "data": refunds, "count": len(refunds)}

# --- DRAFT ORDERS ---
@router.get("/draft-orders")
async def list_draft_orders(
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
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain")
):
    """Get transactions for an order"""
    transactions = await shopify_service.get_transactions(access_token, shop, order_id)
    return {"ok": True, "data": transactions, "count": len(transactions)}

# --- ANALYTICS ---
@router.get("/analytics")
async def get_shop_analytics(
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain")
):
    """Get comprehensive shop analytics"""
    analytics = await shopify_service.get_shop_analytics(access_token, shop)
    return {"ok": True, "data": analytics}

@router.get("/inventory")
async def get_inventory(
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain"),
    location_id: str = Query(None, description="Filter by location")
):
    """Get inventory levels"""
    inventory = await shopify_service.get_inventory_levels(access_token, shop, location_id)
    return {"ok": True, "data": inventory, "count": len(inventory)}

@router.get("/locations")
async def get_locations(
    access_token: str = Query(..., description="Access Token"),
    shop: str = Query(..., description="Shop Domain")
):
    """Get shop locations"""
    locations = await shopify_service.get_locations(access_token, shop)
    return {"ok": True, "data": locations, "count": len(locations)}
