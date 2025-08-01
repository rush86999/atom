import os
import logging
from typing import Optional, List, Dict, Any
import shopify

logger = logging.getLogger(__name__)

def get_shopify_client(user_id: str, db_conn_pool) -> Optional[shopify.ShopifyAPI]:
    """
    Constructs and returns a Shopify API client.

    For now, this function uses environment variables for credentials.
    In a production environment, these should be fetched from a secure database
    based on the user_id.
    """
    shop_url = os.environ.get("SHOPIFY_SHOP_URL")
    api_key = os.environ.get("SHOPIFY_API_KEY")
    password = os.environ.get("SHOPIFY_PASSWORD")
    api_version = os.environ.get("SHOPIFY_API_VERSION", "2023-01")

    if not all([shop_url, api_key, password]):
        logger.error("Shopify credentials are not fully configured in environment variables.")
        return None

    try:
        session = shopify.Session(shop_url, api_version, password)
        shopify.ShopifyResource.activate_session(session)
        return shopify
    except Exception as e:
        logger.error(f"Failed to initialize Shopify session for user {user_id}: {e}", exc_info=True)
        return None

async def list_products(sh: shopify.ShopifyAPI) -> List[Dict[str, Any]]:
    """
    Retrieves a list of products from Shopify.
    """
    products = sh.Product.find()
    return [product.to_dict() for product in products]

async def get_order(sh: shopify.ShopifyAPI, order_id: str) -> Optional[Dict[str, Any]]:
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
