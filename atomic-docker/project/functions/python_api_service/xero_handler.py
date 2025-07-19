import logging
from flask import Blueprint, request, jsonify, current_app
from . import xero_service

logger = logging.getLogger(__name__)

xero_bp = Blueprint('xero_bp', __name__)

@xero_bp.route('/api/xero/invoices', methods=['GET', 'POST'])
async def handle_invoices():
    user_id = request.args.get('user_id') if request.method == 'GET' else request.get_json().get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        xero = await xero_service.get_xero_client(user_id, db_conn_pool)
        if not xero:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Xero client. Please connect your Xero account."}}), 401

        if request.method == 'GET':
            invoices = await xero_service.list_invoices(xero)
            return jsonify({"ok": True, "data": {"invoices": invoices}})
        else: # POST
            data = request.get_json()
            invoice_data = {
                "Type": "ACCREC",
                "Contact": data.get('Contact'),
                "LineItems": data.get('LineItems'),
                "Status": data.get('Status', 'DRAFT')
            }
            invoice = await xero_service.create_invoice(xero, invoice_data)
            return jsonify({"ok": True, "data": invoice})
    except Exception as e:
        logger.error(f"Error handling Xero invoices for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "INVOICES_HANDLING_FAILED", "message": str(e)}}), 500

@xero_bp.route('/api/xero/bills', methods=['GET', 'POST'])
async def handle_bills():
    user_id = request.args.get('user_id') if request.method == 'GET' else request.get_json().get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        xero = await xero_service.get_xero_client(user_id, db_conn_pool)
        if not xero:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Xero client. Please connect your Xero account."}}), 401

        if request.method == 'GET':
            bills = await xero_service.list_bills(xero)
            return jsonify({"ok": True, "data": {"bills": bills}})
        else: # POST
            data = request.get_json()
            bill_data = {
                "Type": "ACCPAY",
                "Contact": data.get('Contact'),
                "LineItems": data.get('LineItems'),
                "Status": data.get('Status', 'DRAFT')
            }
            bill = await xero_service.create_bill(xero, bill_data)
            return jsonify({"ok": True, "data": bill})
    except Exception as e:
        logger.error(f"Error handling Xero bills for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "BILLS_HANDLING_FAILED", "message": str(e)}}), 500

@xero_bp.route('/api/xero/contacts', methods=['GET'])
async def get_contacts():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        xero = await xero_service.get_xero_client(user_id, db_conn_pool)
        if not xero:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Xero client. Please connect your Xero account."}}), 401

        contacts = await xero_service.list_contacts(xero)
        return jsonify({"ok": True, "data": {"contacts": contacts}})
    except Exception as e:
        logger.error(f"Error getting Xero contacts for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CONTACTS_FETCH_FAILED", "message": str(e)}}), 500
