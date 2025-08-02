import logging
from flask import Blueprint, request, jsonify, current_app
from . import zoho_service

logger = logging.getLogger(__name__)

zoho_bp = Blueprint('zoho_bp', __name__)

@zoho_bp.route('/api/zoho/organizations', methods=['GET'])
async def get_zoho_organizations():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await zoho_service.get_zoho_organizations(user_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting Zoho organizations for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_ZOHO_ORGANIZATIONS_FAILED", "message": str(e)}}), 500

@zoho_bp.route('/api/zoho/invoices', methods=['GET'])
async def get_zoho_invoices():
    user_id = request.args.get('user_id')
    org_id = request.args.get('org_id')
    if not all([user_id, org_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and org_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await zoho_service.get_zoho_invoices(user_id, org_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting Zoho invoices for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_ZOHO_INVOICES_FAILED", "message": str(e)}}), 500

@zoho_bp.route('/api/zoho/invoices', methods=['POST'])
async def create_zoho_invoice():
    data = request.get_json()
    user_id = data.get('user_id')
    org_id = data.get('org_id')
    invoice_data = data.get('invoice_data')
    if not all([user_id, org_id, invoice_data]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, org_id, and invoice_data are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await zoho_service.create_zoho_invoice(user_id, org_id, invoice_data, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Zoho invoice for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREATE_ZOHO_INVOICE_FAILED", "message": str(e)}}), 500

@zoho_bp.route('/api/zoho/customers', methods=['GET'])
async def get_zoho_customers():
    user_id = request.args.get('user_id')
    org_id = request.args.get('org_id')
    if not all([user_id, org_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and org_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await zoho_service.get_zoho_customers(user_id, org_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting Zoho customers for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_ZOHO_CUSTOMERS_FAILED", "message": str(e)}}), 500

@zoho_bp.route('/api/zoho/customers', methods=['POST'])
async def create_zoho_customer():
    data = request.get_json()
    user_id = data.get('user_id')
    org_id = data.get('org_id')
    customer_data = data.get('customer_data')
    if not all([user_id, org_id, customer_data]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, org_id, and customer_data are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await zoho_service.create_zoho_customer(user_id, org_id, customer_data, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Zoho customer for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREATE_ZOHO_CUSTOMER_FAILED", "message": str(e)}}), 500

@zoho_bp.route('/api/zoho/items', methods=['GET'])
async def get_zoho_items():
    user_id = request.args.get('user_id')
    org_id = request.args.get('org_id')
    if not all([user_id, org_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and org_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await zoho_service.get_zoho_items(user_id, org_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting Zoho items for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_ZOHO_ITEMS_FAILED", "message": str(e)}}), 500

@zoho_bp.route('/api/zoho/items', methods=['POST'])
async def create_zoho_item():
    data = request.get_json()
    user_id = data.get('user_id')
    org_id = data.get('org_id')
    item_data = data.get('item_data')
    if not all([user_id, org_id, item_data]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, org_id, and item_data are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await zoho_service.create_zoho_item(user_id, org_id, item_data, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Zoho item for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREATE_ZOHO_ITEM_FAILED", "message": str(e)}}), 500

@zoho_bp.route('/api/zoho/bills', methods=['GET'])
async def get_zoho_bills():
    user_id = request.args.get('user_id')
    org_id = request.args.get('org_id')
    if not all([user_id, org_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and org_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await zoho_service.get_zoho_bills(user_id, org_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting Zoho bills for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_ZOHO_BILLS_FAILED", "message": str(e)}}), 500

@zoho_bp.route('/api/zoho/bills', methods=['POST'])
async def create_zoho_bill():
    data = request.get_json()
    user_id = data.get('user_id')
    org_id = data.get('org_id')
    bill_data = data.get('bill_data')
    if not all([user_id, org_id, bill_data]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, org_id, and bill_data are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await zoho_service.create_zoho_bill(user_id, org_id, bill_data, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Zoho bill for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREATE_ZOHO_BILL_FAILED", "message": str(e)}}), 500

@zoho_bp.route('/api/zoho/vendors', methods=['GET'])
async def get_zoho_vendors():
    user_id = request.args.get('user_id')
    org_id = request.args.get('org_id')
    if not all([user_id, org_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and org_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await zoho_service.get_zoho_vendors(user_id, org_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting Zoho vendors for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_ZOHO_VENDORS_FAILED", "message": str(e)}}), 500

@zoho_bp.route('/api/zoho/vendors', methods=['POST'])
async def create_zoho_vendor():
    data = request.get_json()
    user_id = data.get('user_id')
    org_id = data.get('org_id')
    vendor_data = data.get('vendor_data')
    if not all([user_id, org_id, vendor_data]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, org_id, and vendor_data are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await zoho_service.create_zoho_vendor(user_id, org_id, vendor_data, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Zoho vendor for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREATE_ZOHO_VENDOR_FAILED", "message": str(e)}}), 500

@zoho_bp.route('/api/zoho/purchaseorders', methods=['GET'])
async def get_zoho_purchase_orders():
    user_id = request.args.get('user_id')
    org_id = request.args.get('org_id')
    if not all([user_id, org_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and org_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await zoho_service.get_zoho_purchase_orders(user_id, org_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting Zoho purchase orders for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_ZOHO_PURCHASE_ORDERS_FAILED", "message": str(e)}}), 500

@zoho_bp.route('/api/zoho/purchaseorders', methods=['POST'])
async def create_zoho_purchase_order():
    data = request.get_json()
    user_id = data.get('user_id')
    org_id = data.get('org_id')
    purchase_order_data = data.get('purchase_order_data')
    if not all([user_id, org_id, purchase_order_data]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, org_id, and purchase_order_data are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await zoho_service.create_zoho_purchase_order(user_id, org_id, purchase_order_data, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating Zoho purchase order for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREATE_ZOHO_PURCHASE_ORDER_FAILED", "message": str(e)}}), 500
