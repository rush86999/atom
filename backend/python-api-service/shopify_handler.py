import logging
from flask import Blueprint, request, jsonify, current_app
from . import shopify_service

logger = logging.getLogger(__name__)

shopify_bp = Blueprint('shopify_bp', __name__)

@shopify_bp.route('/api/shopify/products', methods=['GET'])
async def handle_products():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        sh = shopify_service.get_shopify_client(user_id, db_conn_pool)
        if not sh:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Shopify client. Please connect your Shopify account."}}), 401

        products = await shopify_service.list_products(sh)
        return jsonify({"ok": True, "data": {"products": products}})
    except Exception as e:
        logger.error(f"Error handling Shopify products for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "PRODUCTS_HANDLING_FAILED", "message": str(e)}}), 500

@shopify_bp.route('/api/shopify/orders/<order_id>', methods=['GET'])
async def handle_order(order_id):
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        sh = shopify_service.get_shopify_client(user_id, db_conn_pool)
        if not sh:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Shopify client. Please connect your Shopify account."}}), 401

        order = await shopify_service.get_order(sh, order_id)
        if order is None:
            return jsonify({"ok": False, "error": {"code": "NOT_FOUND", "message": f"Order with ID {order_id} not found."}}), 404

        return jsonify({"ok": True, "data": order})
    except Exception as e:
        logger.error(f"Error handling Shopify order {order_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "ORDER_HANDLING_FAILED", "message": str(e)}}), 500

@shopify_bp.route('/api/shopify/top-selling-products', methods=['GET'])
async def handle_top_selling_products():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        sh = shopify_service.get_shopify_client(user_id, db_conn_pool)
        if not sh:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Shopify client. Please connect your Shopify account."}}), 401

        top_products = await shopify_service.get_top_selling_products(sh)
        return jsonify({"ok": True, "data": {"products": top_products}})
    except Exception as e:
        logger.error(f"Error handling Shopify top-selling products for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "TOP_SELLING_HANDLING_FAILED", "message": str(e)}}), 500

@shopify_bp.route('/api/shopify/connection-status', methods=['GET'])
def get_connection_status():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        with get_db_connection(db_conn_pool) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT shop_url FROM shopify_oauth_tokens WHERE user_id = %s", (user_id,))
                token_info = cur.fetchone()

        if token_info:
            return jsonify({"ok": True, "data": {"isConnected": True, "shopUrl": token_info[0]}})
        else:
            return jsonify({"ok": True, "data": {"isConnected": False}})
    except Exception as e:
        logger.error(f"Error checking Shopify connection status for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CONNECTION_STATUS_FAILED", "message": str(e)}}), 500

@shopify_bp.route('/api/shopify/disconnect', methods=['POST'])
def disconnect_shopify():
    user_id = request.get_json().get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        with get_db_connection(db_conn_pool) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM shopify_oauth_tokens WHERE user_id = %s", (user_id,))

        return jsonify({"ok": True, "data": None})
    except Exception as e:
        logger.error(f"Error disconnecting Shopify for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "DISCONNECT_FAILED", "message": str(e)}}), 500
