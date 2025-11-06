import logging
from flask import Blueprint, request, jsonify, current_app
import shopify_service

logger = logging.getLogger(__name__)

shopify_bp = Blueprint("shopify_bp", __name__)


@shopify_bp.route("/api/shopify/products", methods=["GET"])
async def handle_products():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id is required.",
                },
            }
        ), 400

    db_conn_pool = current_app.config.get("DB_CONNECTION_POOL")
    if not db_conn_pool:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "CONFIG_ERROR",
                    "message": "Database connection not available.",
                },
            }
        ), 500

    try:
        sh = shopify_service.get_shopify_client(user_id, db_conn_pool)
        if not sh:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "Could not get authenticated Shopify client. Please connect your Shopify account.",
                    },
                }
            ), 401

        products = await sh.get_products(user_id)
        return jsonify({"ok": True, "data": {"products": products}})
    except Exception as e:
        logger.error(
            f"Error handling Shopify products for user {user_id}: {e}", exc_info=True
        )
        return jsonify(
            {
                "ok": False,
                "error": {"code": "PRODUCTS_HANDLING_FAILED", "message": str(e)},
            }
        ), 500


@shopify_bp.route("/api/shopify/orders/<order_id>", methods=["GET"])
async def handle_order(order_id):
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id is required.",
                },
            }
        ), 400

    db_conn_pool = current_app.config.get("DB_CONNECTION_POOL")
    if not db_conn_pool:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "CONFIG_ERROR",
                    "message": "Database connection not available.",
                },
            }
        ), 500

    try:
        sh = shopify_service.get_shopify_client(user_id, db_conn_pool)
        if not sh:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "Could not get authenticated Shopify client. Please connect your Shopify account.",
                    },
                }
            ), 401

        orders = await sh.get_orders(user_id)
        order = next(
            (o for o in orders if o.get("id") == order_id or o.get("name") == order_id),
            None,
        )
        if order is None:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Order with ID {order_id} not found.",
                    },
                }
            ), 404

        return jsonify({"ok": True, "data": order})
    except Exception as e:
        logger.error(
            f"Error handling Shopify order {order_id} for user {user_id}: {e}",
            exc_info=True,
        )
        return jsonify(
            {"ok": False, "error": {"code": "ORDER_HANDLING_FAILED", "message": str(e)}}
        ), 500


@shopify_bp.route("/api/shopify/top-selling-products", methods=["GET"])
async def handle_top_selling_products():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id is required.",
                },
            }
        ), 400

    db_conn_pool = current_app.config.get("DB_CONNECTION_POOL")
    if not db_conn_pool:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "CONFIG_ERROR",
                    "message": "Database connection not available.",
                },
            }
        ), 500

    try:
        sh = shopify_service.get_shopify_client(user_id, db_conn_pool)
        if not sh:
            return jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTH_ERROR",
                        "message": "Could not get authenticated Shopify client. Please connect your Shopify account.",
                    },
                }
            ), 401

        products = await sh.get_products(user_id)
        top_products = sorted(
            products, key=lambda x: x.get("total_sales", 0), reverse=True
        )[:10]
        return jsonify({"ok": True, "data": {"products": top_products}})
    except Exception as e:
        logger.error(
            f"Error handling Shopify top-selling products for user {user_id}: {e}",
            exc_info=True,
        )
        return jsonify(
            {
                "ok": False,
                "error": {"code": "TOP_SELLING_HANDLING_FAILED", "message": str(e)},
            }
        ), 500


@shopify_bp.route("/api/shopify/connection-status", methods=["GET"])
async def get_connection_status():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id is required.",
                },
            }
        ), 400

    db_conn_pool = current_app.config.get("DB_CONNECTION_POOL")
    if not db_conn_pool:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "CONFIG_ERROR",
                    "message": "Database connection not available.",
                },
            }
        ), 500

    try:
        sh = shopify_service.get_shopify_client(user_id, db_conn_pool)
        if not sh:
            return jsonify({"ok": True, "data": {"isConnected": False}})

        # Try to get shop info to verify connection
        shop_info = await sh.get_shop_info(user_id)
        return jsonify(
            {
                "ok": True,
                "data": {
                    "isConnected": True,
                    "shopUrl": shop_info.get("domain", "Unknown"),
                },
            }
        )
    except Exception:
        return jsonify({"ok": True, "data": {"isConnected": False}})
    except Exception as e:
        logger.error(
            f"Error checking Shopify connection status for user {user_id}: {e}",
            exc_info=True,
        )
        return jsonify(
            {
                "ok": False,
                "error": {"code": "CONNECTION_STATUS_FAILED", "message": str(e)},
            }
        ), 500


@shopify_bp.route("/api/shopify/disconnect", methods=["POST"])
async def disconnect_shopify():
    user_id = request.get_json().get("user_id")
    if not user_id:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "user_id is required.",
                },
            }
        ), 400

    db_conn_pool = current_app.config.get("DB_CONNECTION_POOL")
    if not db_conn_pool:
        return jsonify(
            {
                "ok": False,
                "error": {
                    "code": "CONFIG_ERROR",
                    "message": "Database connection not available.",
                },
            }
        ), 500

    try:
        from db_oauth_shopify import revoke_user_shopify_tokens

        await revoke_user_shopify_tokens(db_conn_pool, user_id)
        return jsonify({"ok": True, "data": None})
    except Exception as e:
        logger.error(
            f"Error disconnecting Shopify for user {user_id}: {e}", exc_info=True
        )
        return jsonify(
            {"ok": False, "error": {"code": "DISCONNECT_FAILED", "message": str(e)}}
        ), 500
