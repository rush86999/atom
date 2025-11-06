"""
Shopify Webhooks Integration
Real-time event notifications and triggers for Shopify
"""

import json
import hmac
import hashlib
import base64
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass
from flask import Blueprint, request, jsonify, current_app
from loguru import logger

# Shopify webhook topics
SHOPIFY_WEBHOOK_TOPICS = {
    # Order events
    "orders/create": "New order created",
    "orders/updated": "Order updated",
    "orders/paid": "Order paid",
    "orders/cancelled": "Order cancelled",
    "orders/fulfilled": "Order fulfilled",
    "orders/partially_fulfilled": "Order partially fulfilled",
    
    # Product events
    "products/create": "New product created",
    "products/update": "Product updated",
    "products/delete": "Product deleted",
    
    # Collection events
    "collections/create": "New collection created",
    "collections/update": "Collection updated",
    "collections/delete": "Collection deleted",
    
    # Customer events
    "customers/create": "New customer created",
    "customers/update": "Customer updated",
    "customers/delete": "Customer deleted",
    "customers/enable": "Customer account enabled",
    "customers/disable": "Customer account disabled",
    
    # Inventory events
    "inventory_levels/update": "Inventory level updated",
    "inventory_items/create": "Inventory item created",
    "inventory_items/update": "Inventory item updated",
    "inventory_items/delete": "Inventory item deleted",
    
    # Shop events
    "shop/update": "Shop updated",
    "app/uninstalled": "App uninstalled",
    
    # Checkout events
    "checkouts/create": "Checkout created",
    "checkouts/update": "Checkout updated",
    "checkouts/delete": "Checkout deleted",
}

@dataclass
class ShopifyWebhookEvent:
    """Shopify webhook event model"""
    id: str
    topic: str
    shop_domain: str
    timestamp: datetime
    data: Dict[str, Any]
    headers: Dict[str, str]
    processed: bool = False
    processing_error: Optional[str] = None

@dataclass
class ShopifyWebhookRegistration:
    """Shopify webhook registration model"""
    topic: str
    address: str
    format: str = "json"
    fields: List[str] = None
    metafield_namespaces: List[str] = None
    api_version: str = "2024-01"
    created_at: Optional[datetime] = None
    webhook_id: Optional[int] = None
    
    def __post_init__(self):
        if self.fields is None:
            self.fields = []
        if self.metafield_namespaces is None:
            self.metafield_namespaces = []

class ShopifyWebhookProcessor:
    """Shopify webhook event processor"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.global_handlers: List[Callable] = []
        self.processed_events: List[ShopifyWebhookEvent] = []
        self.max_events_history = 1000
    
    def register_handler(self, topic: str, handler: Callable):
        """Register handler for specific webhook topic"""
        if topic not in self.event_handlers:
            self.event_handlers[topic] = []
        self.event_handlers[topic].append(handler)
        logger.info(f"Registered webhook handler for topic: {topic}")
    
    def register_global_handler(self, handler: Callable):
        """Register global handler for all webhook events"""
        self.global_handlers.append(handler)
        logger.info("Registered global webhook handler")
    
    def verify_signature(self, body: str, signature: str) -> bool:
        """Verify Shopify webhook signature"""
        calculated_signature = hmac.new(
            self.secret_key.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        calculated_signature_b64 = base64.b64encode(calculated_signature).decode()
        
        return hmac.compare_digest(calculated_signature_b64, signature)
    
    def parse_webhook_event(self, request) -> Optional[ShopifyWebhookEvent]:
        """Parse incoming webhook event"""
        try:
            # Get webhook headers
            shop_domain = request.headers.get('X-Shopify-Shop-Domain')
            topic = request.headers.get('X-Shopify-Topic')
            timestamp = request.headers.get('X-Shopify-Timestamp')
            signature = request.headers.get('X-Shopify-Hmac-Sha256')
            
            if not all([shop_domain, topic, timestamp, signature]):
                logger.error("Missing required webhook headers")
                return None
            
            # Verify signature
            body = request.data.decode('utf-8')
            if not self.verify_signature(body, signature):
                logger.error("Webhook signature verification failed")
                return None
            
            # Check for replay attacks
            webhook_time = datetime.fromtimestamp(int(timestamp), timezone.utc)
            current_time = datetime.now(timezone.utc)
            
            if (current_time - webhook_time).total_seconds() > 300:  # 5 minutes
                logger.error(f"Webhook timestamp too old: {webhook_time}")
                return None
            
            # Parse event data
            event_data = json.loads(body)
            
            return ShopifyWebhookEvent(
                id=request.headers.get('X-Shopify-Webhook-Id', ''),
                topic=topic,
                shop_domain=shop_domain,
                timestamp=webhook_time,
                data=event_data,
                headers=dict(request.headers)
            )
            
        except Exception as e:
            logger.error(f"Error parsing webhook event: {e}")
            return None
    
    async def process_event(self, event: ShopifyWebhookEvent) -> bool:
        """Process webhook event"""
        try:
            # Add to history
            self.processed_events.append(event)
            if len(self.processed_events) > self.max_events_history:
                self.processed_events.pop(0)
            
            # Call global handlers
            for handler in self.global_handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Global webhook handler error: {e}")
            
            # Call topic-specific handlers
            topic_handlers = self.event_handlers.get(event.topic, [])
            for handler in topic_handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Topic webhook handler error: {e}")
            
            event.processed = True
            logger.info(f"Successfully processed webhook event: {event.topic}")
            return True
            
        except Exception as e:
            event.processing_error = str(e)
            logger.error(f"Error processing webhook event: {e}")
            return False
    
    def get_event_history(
        self, 
        topic: Optional[str] = None, 
        shop_domain: Optional[str] = None,
        limit: int = 100
    ) -> List[ShopifyWebhookEvent]:
        """Get webhook event history"""
        events = self.processed_events
        
        # Filter by topic
        if topic:
            events = [e for e in events if e.topic == topic]
        
        # Filter by shop domain
        if shop_domain:
            events = [e for e in events if e.shop_domain == shop_domain]
        
        # Sort by timestamp (newest first) and limit
        events.sort(key=lambda x: x.timestamp, reverse=True)
        return events[:limit]
    
    def get_event_statistics(self) -> Dict[str, Any]:
        """Get webhook event processing statistics"""
        total_events = len(self.processed_events)
        processed_events = len([e for e in self.processed_events if e.processed])
        failed_events = total_events - processed_events
        
        # Events by topic
        topic_counts = {}
        for event in self.processed_events:
            topic_counts[event.topic] = topic_counts.get(event.topic, 0) + 1
        
        # Recent events (last hour)
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_events = [e for e in self.processed_events if e.timestamp > one_hour_ago]
        
        return {
            "total_events": total_events,
            "processed_events": processed_events,
            "failed_events": failed_events,
            "success_rate": (processed_events / total_events * 100) if total_events > 0 else 0,
            "events_by_topic": topic_counts,
            "recent_events_1h": len(recent_events),
            "registered_handlers": {
                "global": len(self.global_handlers),
                "topic_specific": sum(len(handlers) for handlers in self.event_handlers.values())
            },
            "active_topics": list(self.event_handlers.keys())
        }

# Global webhook processor instance
_webhook_processor: Optional[ShopifyWebhookProcessor] = None

def get_webhook_processor(secret_key: Optional[str] = None) -> ShopifyWebhookProcessor:
    """Get global webhook processor instance"""
    global _webhook_processor
    
    if _webhook_processor is None and secret_key:
        _webhook_processor = ShopifyWebhookProcessor(secret_key)
    
    return _webhook_processor

# Flask blueprint for webhook endpoints
shopify_webhooks_bp = Blueprint("shopify_webhooks_bp", __name__)

@shopify_webhooks_bp.route('/api/shopify/webhooks/<webhook_topic>', methods=['POST'])
async def handle_webhook(webhook_topic: str):
    """Handle incoming Shopify webhook"""
    try:
        # Get webhook processor
        processor = get_webhook_processor()
        if not processor:
            logger.error("Webhook processor not initialized")
            return jsonify({"error": "Webhook processor not initialized"}), 500
        
        # Parse webhook event
        event = processor.parse_webhook_event(request)
        if not event:
            return jsonify({"error": "Invalid webhook event"}), 400
        
        # Verify topic matches
        if event.topic != webhook_topic:
            logger.error(f"Topic mismatch: expected {webhook_topic}, got {event.topic}")
            return jsonify({"error": "Topic mismatch"}), 400
        
        # Process event
        success = await processor.process_event(event)
        
        if success:
            return jsonify({"status": "success", "event_id": event.id}), 200
        else:
            return jsonify({"error": "Event processing failed"}), 500
            
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return jsonify({"error": str(e)}), 500

@shopify_webhooks_bp.route('/api/shopify/webhooks', methods=['POST'])
async def register_webhook():
    """Register new Shopify webhook"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        webhook_data = data.get('webhook', {})
        
        if not user_id or not webhook_data:
            return jsonify({"error": "user_id and webhook data are required"}), 400
        
        # Get Shopify service
        from shopify_service import get_shopify_client
        shopify_client = await get_shopify_client(user_id)
        
        if not shopify_client:
            return jsonify({"error": "Failed to get Shopify client"}), 500
        
        # Register webhook
        result = await shopify_client.register_webhook(
            topic=webhook_data.get('topic'),
            address=webhook_data.get('address'),
            format=webhook_data.get('format', 'json'),
            fields=webhook_data.get('fields', []),
            metafield_namespaces=webhook_data.get('metafield_namespaces', [])
        )
        
        if result.get('success'):
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error registering webhook: {e}")
        return jsonify({"error": str(e)}), 500

@shopify_webhooks_bp.route('/api/shopify/webhooks', methods=['GET'])
async def list_webhooks():
    """List registered Shopify webhooks"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        # Get Shopify service
        from shopify_service import get_shopify_client
        shopify_client = await get_shopify_client(user_id)
        
        if not shopify_client:
            return jsonify({"error": "Failed to get Shopify client"}), 500
        
        # List webhooks
        webhooks = await shopify_client.list_webhooks()
        
        return jsonify({
            "success": True,
            "webhooks": [
                {
                    "id": webhook.id,
                    "topic": webhook.topic,
                    "address": webhook.address,
                    "format": webhook.format,
                    "api_version": webhook.api_version,
                    "created_at": webhook.created_at.isoformat(),
                    "fields": webhook.fields,
                    "metafield_namespaces": webhook.metafield_namespaces
                }
                for webhook in webhooks
            ],
            "total": len(webhooks)
        })
        
    except Exception as e:
        logger.error(f"Error listing webhooks: {e}")
        return jsonify({"error": str(e)}), 500

@shopify_webhooks_bp.route('/api/shopify/webhooks/<int:webhook_id>', methods=['DELETE'])
async def delete_webhook(webhook_id: int):
    """Delete Shopify webhook"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        # Get Shopify service
        from shopify_service import get_shopify_client
        shopify_client = await get_shopify_client(user_id)
        
        if not shopify_client:
            return jsonify({"error": "Failed to get Shopify client"}), 500
        
        # Delete webhook
        result = await shopify_client.delete_webhook(webhook_id)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        return jsonify({"error": str(e)}), 500

@shopify_webhooks_bp.route('/api/shopify/webhooks/events', methods=['GET'])
async def get_webhook_events():
    """Get webhook event history and statistics"""
    try:
        topic = request.args.get('topic')
        shop_domain = request.args.get('shop_domain')
        limit = int(request.args.get('limit', 100))
        include_stats = request.args.get('include_stats', 'true').lower() == 'true'
        
        # Get webhook processor
        processor = get_webhook_processor()
        if not processor:
            return jsonify({"error": "Webhook processor not initialized"}), 500
        
        # Get event history
        events = processor.get_event_history(topic, shop_domain, limit)
        
        response = {
            "success": True,
            "events": [
                {
                    "id": event.id,
                    "topic": event.topic,
                    "shop_domain": event.shop_domain,
                    "timestamp": event.timestamp.isoformat(),
                    "processed": event.processed,
                    "processing_error": event.processing_error
                }
                for event in events
            ],
            "total": len(events)
        }
        
        # Include statistics if requested
        if include_stats:
            response["statistics"] = processor.get_event_statistics()
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting webhook events: {e}")
        return jsonify({"error": str(e)}), 500

@shopify_webhooks_bp.route('/api/shopify/webhooks/topics', methods=['GET'])
def get_webhook_topics():
    """Get available webhook topics"""
    return jsonify({
        "success": True,
        "topics": [
            {
                "topic": topic,
                "description": description
            }
            for topic, description in SHOPIFY_WEBHOOK_TOPICS.items()
        ],
        "total": len(SHOPIFY_WEBHOOK_TOPICS)
    })

# Example webhook event handlers
async def handle_order_created(event: ShopifyWebhookEvent):
    """Handle order created event"""
    order_data = event.data
    logger.info(f"Order created: {order_data.get('name', 'Unknown')} - {order_data.get('total_price', '0.00')}")
    
    # Trigger business logic here
    # e.g., send confirmation email, update inventory, notify team
    
async def handle_product_updated(event: ShopifyWebhookEvent):
    """Handle product updated event"""
    product_data = event.data
    logger.info(f"Product updated: {product_data.get('title', 'Unknown')}")
    
    # Trigger business logic here
    # e.g., update search index, sync with other systems

async def handle_inventory_low(event: ShopifyWebhookEvent):
    """Handle low inventory alert"""
    inventory_data = event.data
    if inventory_data.get('available', 0) < 10:  # Low stock threshold
        logger.warning(f"Low inventory for item: {inventory_data.get('inventory_item_id')}")
        
        # Trigger restock notification
        # e.g., send alert to procurement team

def setup_default_handlers(processor: ShopifyWebhookProcessor):
    """Setup default webhook event handlers"""
    processor.register_handler('orders/create', handle_order_created)
    processor.register_handler('products/update', handle_product_updated)
    processor.register_handler('inventory_levels/update', handle_inventory_low)
    
    # Register global handler for logging all events
    async def global_logger(event: ShopifyWebhookEvent):
        logger.info(f"Webhook received: {event.topic} from {event.shop_domain}")
    
    processor.register_global_handler(global_logger)
    logger.info("Default webhook handlers registered")

# Export components
__all__ = [
    "ShopifyWebhookProcessor",
    "ShopifyWebhookEvent",
    "ShopifyWebhookRegistration",
    "get_webhook_processor",
    "setup_default_handlers",
    "shopify_webhooks_bp"
]