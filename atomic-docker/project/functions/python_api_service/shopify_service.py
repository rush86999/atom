import os
import logging
import types
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from collections import Counter
import shopify

logger = logging.getLogger(__name__)

from .db_utils import get_db_connection

def get_shopify_client(user_id: str, db_conn_pool) -> Optional[types.ModuleType]:
    """
    Constructs and returns an authenticated Shopify API client for the given user.
    """
    try:
        with get_db_connection(db_conn_pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT access_token, shop_url FROM shopify_oauth_tokens WHERE user_id = %s",
                    (user_id,)
                )
                token_info = cur.fetchone()
    except Exception as e:
        logger.error(f"Database error while fetching Shopify token for user {user_id}: {e}", exc_info=True)
        return None

    if not token_info:
        logger.warn(f"No Shopify token found for user {user_id}.")
        return None

    access_token, shop_url = token_info
    api_version = os.environ.get("SHOPIFY_API_VERSION", "2023-01")

    try:
        session = shopify.Session(shop_url, api_version, access_token)
        shopify.ShopifyResource.activate_session(session)
        return shopify
    except Exception as e:
        logger.error(f"Failed to initialize Shopify session for user {user_id}: {e}", exc_info=True)
        return None

async def list_products(sh: types.ModuleType) -> List[Dict[str, Any]]:
    """
    Retrieves a list of products from Shopify.
    """
    products = sh.Product.find()
    return [product.to_dict() for product in products]

async def get_order(sh: types.ModuleType, order_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a specific order by its ID.
    """
    try:
        order = sh.Order.find(order_id)
        return order.to_dict() if order else None
    except Exception as e:
        # The shopify library can raise exceptions for 404 Not Found
        logger.error(f"Error fetching order {order_id} from Shopify: {e}", exc_info=True)
        return None

async def get_top_selling_products(sh: types.ModuleType, days: int = 30, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retrieves the top-selling products over a given number of days.
    """
    try:
        # Calculate the start date for fetching orders
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        start_date_iso = start_date.isoformat()

        # Fetch orders from the specified date
        orders = sh.Order.find(created_at_min=start_date_iso, status='any')

        # Use a Counter to aggregate product sales
        product_sales = Counter()
        product_details = {}

        for order in orders:
            for item in order.line_items:
                # Use variant_id if available, otherwise product_id
                item_id = item.variant_id if item.variant_id else item.product_id
                if not item_id:
                    continue

                product_sales[item_id] += item.quantity

                # Store product details if not already stored
                if item_id not in product_details:
                    product_details[item_id] = {
                        'product_id': item.product_id,
                        'variant_id': item.variant_id,
                        'title': item.title,
                        'variant_title': item.variant_title,
                    }

        # Prepare the list of top-selling products
        top_products = []
        for item_id, quantity_sold in product_sales.most_common(limit):
            details = product_details.get(item_id, {})
            top_products.append({
                'product_id': details.get('product_id'),
                'variant_id': details.get('variant_id'),
                'title': details.get('title'),
                'variant_title': details.get('variant_title'),
                'quantity_sold': quantity_sold,
            })

        return top_products

    except Exception as e:
        logger.error(f"Error fetching top-selling products from Shopify: {e}", exc_info=True)
        return []
