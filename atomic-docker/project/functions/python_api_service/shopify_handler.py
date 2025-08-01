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
