import os
import logging
from typing import Optional, List, Dict, Any
import shopify

logger = logging.getLogger(__name__)

from .db_utils import get_db_connection

def get_shopify_client(user_id: str, db_conn_pool) -> Optional[shopify.ShopifyResource]:
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

async def list_products(sh: shopify.ShopifyResource) -> List[Dict[str, Any]]:
    """
    Retrieves a list of products from Shopify.
    """
    products = sh.Product.find()
    return [product.to_dict() for product in products]

async def get_order(sh: shopify.ShopifyResource, order_id: str) -> Optional[Dict[str, Any]]:
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
