import base64
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
from ecommerce.models import EcommerceCustomer, EcommerceOrder, EcommerceOrderItem, EcommerceStore
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from core.database import get_db
from core.identity_resolver import CustomerResolutionEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks/shopify", tags=["shopify_webhooks"])

def verify_shopify_webhook(data: bytes, hmac_header: str):
    secret = os.getenv("SHOPIFY_API_SECRET")
    if not secret:
        logger.warning("SHOPIFY_API_SECRET not set, skipping verification")
        return True
        
    digest = hmac.new(secret.encode('utf-8'), data, hashlib.sha256).digest()
    computed_hmac = base64.b64encode(digest)
    
    return hmac.compare_digest(computed_hmac, hmac_header.encode('utf-8'))

async def get_workspace_id(shop_domain: str, db: Session) -> str:
    """Resolve workspace_id from shop domain"""
    store = db.query(EcommerceStore).filter(EcommerceStore.shop_domain == shop_domain).first()
    if store:
        return store.workspace_id
    
    # Fallback/Default for testing if not found
    logger.warning(f"No store found for domain {shop_domain}, using 'default'")
    return "default"

@router.post("/orders-create")
@router.post("/order-created")
async def shopify_order_created(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None),
    x_shopify_shop_domain: str = Header(None),
    db: Session = Depends(get_db)
):
    data = await request.body()
    
    # Verify Webhook
    if x_shopify_hmac_sha256 and not verify_shopify_webhook(data, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    payload = json.loads(data)
    shop_domain = x_shopify_shop_domain or payload.get("domain")
    
    # 1. Identity Resolution
    workspace_id = await get_workspace_id(shop_domain, db)
    
    resolver = CustomerResolutionEngine(db)
    shopify_cust = payload.get("customer", {})
    customer = resolver.resolve_customer(
        workspace_id,
        shopify_cust.get("email"),
        shopify_cust.get("first_name"),
        shopify_cust.get("last_name")
    )
    
    # 2. Persist Order
    existing_order = db.query(EcommerceOrder).filter(
        EcommerceOrder.workspace_id == workspace_id,
        EcommerceOrder.external_id == str(payload.get("id"))
    ).first()
    
    if existing_order:
        return {"status": "already_processed"}

    order = EcommerceOrder(
        workspace_id=workspace_id,
        customer_id=customer.id,
        external_id=str(payload.get("id")),
        order_number=str(payload.get("order_number")),
        total_price=float(payload.get("total_price", 0.0)),
        subtotal_price=float(payload.get("subtotal_price", 0.0)),
        total_tax=float(payload.get("total_tax", 0.0)),
        total_shipping=float(payload.get("total_shipping_line_price", 0.0) if "total_shipping_line_price" in payload else (payload.get("total_shipping_price_set", {}).get("shop_money", {}).get("amount", 0.0))),
        currency=payload.get("currency", "USD"),
        status="paid" if payload.get("financial_status") == "paid" else "pending",
        metadata_json=payload
    )
    db.add(order)
    db.flush()
    
    # Add items
    for item in payload.get("line_items", []):
        db.add(EcommerceOrderItem(
            order_id=order.id,
            product_id=str(item.get("product_id")),
            variant_id=str(item.get("variant_id")),
            title=item.get("title"),
            sku=item.get("sku"),
            quantity=item.get("quantity"),
            price=float(item.get("price", 0.0)),
            metadata_json=item
        ))
    
    db.commit()
    logger.info(f"Ingested Shopify Order {order.order_number} for {workspace_id}")

    # 3. Trigger Advanced Workflow
    orchestrator = AdvancedWorkflowOrchestrator()
    await orchestrator.trigger_event(
        event_type="SHOPIFY_ORDER_CREATED",
        data={
            "order_id": order.id,
            "order_number": order.order_number,
            "total_price": order.total_price,
            "customer_email": customer.email,
            "workspace_id": workspace_id
        }
    )

    return {"status": "success", "order_id": order.id}

@router.post("/orders-updated")
async def shopify_order_updated(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None),
    x_shopify_shop_domain: str = Header(None),
    db: Session = Depends(get_db)
):
    data = await request.body()
    if x_shopify_hmac_sha256 and not verify_shopify_webhook(data, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    payload = json.loads(data)
    shop_domain = x_shopify_shop_domain
    workspace_id = await get_workspace_id(shop_domain, db)
    
    order = db.query(EcommerceOrder).filter(
        EcommerceOrder.workspace_id == workspace_id,
        EcommerceOrder.external_id == str(payload.get("id"))
    ).first()
    
    if not order:
        return {"status": "order_not_found"}
        
    # Update status and prices
    old_status = order.status
    order.status = "paid" if payload.get("financial_status") == "paid" else order.status
    if payload.get("cancelled_at"):
        order.status = "cancelled"
    
    order.total_price = float(payload.get("total_price", order.total_price))
    order.metadata_json = payload
    db.commit()
    
    if old_status != order.status:
        logger.info(f"Updated Shopify Order {order.order_number} status to {order.status}")
        orchestrator = AdvancedWorkflowOrchestrator()
        await orchestrator.trigger_event(
            event_type="SHOPIFY_ORDER_UPDATED",
            data={
                "order_id": order.id,
                "order_number": order.order_number,
                "new_status": order.status,
                "workspace_id": workspace_id
            }
        )
        
    return {"status": "success"}

@router.post("/refunds-create")
async def shopify_refund_created(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None),
    x_shopify_shop_domain: str = Header(None),
    db: Session = Depends(get_db)
):
    data = await request.body()
    if x_shopify_hmac_sha256 and not verify_shopify_webhook(data, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    payload = json.loads(data)
    shop_domain = x_shopify_shop_domain
    workspace_id = await get_workspace_id(shop_domain, db)
    
    order_id = str(payload.get("order_id"))
    order = db.query(EcommerceOrder).filter(
        EcommerceOrder.workspace_id == workspace_id,
        EcommerceOrder.external_id == order_id
    ).first()
    
    if not order:
        return {"status": "order_not_found"}
        
    # Calculate refund total
    refund_amount = 0.0
    for transaction in payload.get("transactions", []):
        if transaction.get("kind") == "refund" and transaction.get("status") == "success":
            refund_amount += float(transaction.get("amount", 0.0))
            
    order.total_refunded += refund_amount
    if order.total_refunded >= order.total_price:
        order.status = "refunded"
        
    db.commit()
    logger.info(f"Processed refund for Shopify Order {order.order_number}: ${refund_amount}")
    
    orchestrator = AdvancedWorkflowOrchestrator()
    await orchestrator.trigger_event(
        event_type="SHOPIFY_ORDER_REFUNDED",
        data={
            "order_id": order.id,
            "order_number": order.order_number,
            "refund_amount": refund_amount,
            "total_refunded": order.total_refunded,
            "workspace_id": workspace_id
        }
    )
    
    return {"status": "success"}
