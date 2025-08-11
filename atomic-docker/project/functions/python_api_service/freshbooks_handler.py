import logging
from flask import Blueprint, request, jsonify, current_app
from . import freshbooks_service

logger = logging.getLogger(__name__)

freshbooks_bp = Blueprint('freshbooks_bp', __name__)

@freshbooks_bp.route('/api/freshbooks/invoices', methods=['GET'])
async def get_freshbooks_invoices():
    user_id = request.args.get('user_id')
    account_id = request.args.get('account_id')
    if not all([user_id, account_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and account_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await freshbooks_service.get_freshbooks_invoices(user_id, account_id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting FreshBooks invoices for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_FRESHBOOKS_INVOICES_FAILED", "message": str(e)}}), 500

@freshbooks_bp.route('/api/freshbooks/invoices', methods=['POST'])
async def create_freshbooks_invoice():
    data = request.get_json()
    user_id = data.get('user_id')
    account_id = data.get('account_id')
    invoice_data = data.get('invoice_data')
    if not all([user_id, account_id, invoice_data]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, account_id, and invoice_data are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await freshbooks_service.create_freshbooks_invoice(user_id, account_id, invoice_data, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating FreshBooks invoice for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREATE_FRESHBOOKS_INVOICE_FAILED", "message": str(e)}}), 500

@freshbooks_bp.route('/api/freshbooks/clients', methods=['GET'])
async def get_freshbooks_clients():
    user_id = request.args.get('user_id')
    account_id = request.args.get('account_id')
    if not all([user_id, account_id]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id and account_id are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await freshbooks_service.get_freshbooks_clients(user_id, account_.id, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error getting FreshBooks clients for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "GET_FRESHBOOKS_CLIENTS_FAILED", "message": str(e)}}), 500

@freshbooks_bp.route('/api/freshbooks/clients', methods=['POST'])
async def create_freshbooks_client():
    data = request.get_json()
    user_id = data.get('user_id')
    account_id = data.get('account_id')
    client_data = data.get('client_data')
    if not all([user_id, account_id, client_data]):
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id, account_id, and client_data are required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        result = await freshbooks_service.create_freshbooks_client(user_id, account_id, client_data, db_conn_pool)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error(f"Error creating FreshBooks client for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CREATE_FRESHBOOKS_CLIENT_FAILED", "message": str(e)}}), 500
