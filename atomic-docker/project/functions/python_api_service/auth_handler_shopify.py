import os
import logging
from flask import Blueprint, request, jsonify, redirect, current_app
import shopify
from .db_utils import get_db_connection

logger = logging.getLogger(__name__)

shopify_auth_bp = Blueprint('shopify_auth_bp', __name__)

SHOPIFY_API_KEY = os.environ.get("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.environ.get("SHOPIFY_API_SECRET")
# These scopes can be adjusted based on the required permissions
SHOPIFY_SCOPES = ["read_products", "read_orders"]

@shopify_auth_bp.route('/api/shopify/auth', methods=['GET'])
def get_shopify_auth_url():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    if not all([SHOPIFY_API_KEY, SHOPIFY_API_SECRET]):
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Shopify API key and secret are not configured."}}), 500

    # The shop name is required to start the OAuth flow. We'll need to get this from the user.
    # For now, we'll require it as a query parameter.
    shop_name = request.args.get('shop_name')
    if not shop_name:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "shop_name is required."}}), 400

    shop_url = f"{shop_name}.myshopify.com"

    try:
        session = shopify.Session(shop_url, "2023-01")
        auth_url = session.create_permission_url(SHOPIFY_SCOPES, request.url_root + 'api/shopify/callback', state=user_id)
        return jsonify({"ok": True, "data": {"auth_url": auth_url}})
    except Exception as e:
        logger.error(f"Error creating Shopify auth URL for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "AUTH_URL_CREATION_FAILED", "message": str(e)}}), 500


@shopify_auth_bp.route('/api/shopify/callback', methods=['GET'])
def shopify_callback():
    shop_url = request.args.get('shop')
    code = request.args.get('code')
    user_id = request.args.get('state') # We should pass user_id in the state parameter

    if not all([shop_url, code]):
        return "Error: missing parameters", 400

    try:
        session = shopify.Session(shop_url, "2023-01")
        access_token = session.request_token(request.args)

        with get_db_connection(current_app.config.get('DB_CONNECTION_POOL')) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO shopify_oauth_tokens (user_id, access_token, scope, shop_url)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        access_token = EXCLUDED.access_token,
                        scope = EXCLUDED.scope,
                        shop_url = EXCLUDED.shop_url,
                        updated_at = CURRENT_TIMESTAMP;
                    """,
                    (user_id, access_token, ",".join(SHOPIFY_SCOPES), shop_url)
                )
        # Redirect to a success page on the frontend
        return redirect(os.environ.get("FRONTEND_URL", "/") + "settings/integrations?shopify_status=success")
    except Exception as e:
        logger.error(f"Error handling Shopify callback: {e}", exc_info=True)
        # Redirect to a failure page on the frontend
        return redirect(os.environ.get("FRONTEND_URL", "/") + "settings/integrations?shopify_status=error")
