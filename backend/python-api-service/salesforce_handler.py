import logging
from flask import Blueprint, request, jsonify, current_app
from . import salesforce_service

logger = logging.getLogger(__name__)

salesforce_bp = Blueprint('salesforce_bp', __name__)

@salesforce_bp.route('/api/salesforce/contacts', methods=['GET', 'POST'])
async def handle_contacts():
    user_id = request.args.get('user_id') if request.method == 'GET' else request.get_json().get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        sf = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
        if not sf:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Salesforce client. Please connect your Salesforce account."}}), 401

        if request.method == 'GET':
            contacts = await salesforce_service.list_contacts(sf)
            return jsonify({"ok": True, "data": {"contacts": contacts}})
        else: # POST
            data = request.get_json()
            last_name = data.get('LastName')
            if not last_name:
                return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "LastName is required to create a contact."}}), 400

            first_name = data.get('FirstName')
            email = data.get('Email')
            contact = await salesforce_service.create_contact(sf, last_name, first_name, email)
            return jsonify({"ok": True, "data": contact})
    except Exception as e:
        logger.error(f"Error handling Salesforce contacts for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "CONTACTS_HANDLING_FAILED", "message": str(e)}}), 500

@salesforce_bp.route('/api/salesforce/accounts', methods=['GET', 'POST'])
async def handle_accounts():
    user_id = request.args.get('user_id') if request.method == 'GET' else request.get_json().get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        sf = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
        if not sf:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Salesforce client. Please connect your Salesforce account."}}), 401

        if request.method == 'GET':
            accounts = await salesforce_service.list_accounts(sf)
            return jsonify({"ok": True, "data": {"accounts": accounts}})
        else: # POST
            data = request.get_json()
            name = data.get('Name')
            if not name:
                return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "Name is required to create an account."}}), 400

            account = await salesforce_service.create_account(sf, name)
            return jsonify({"ok": True, "data": account})
    except Exception as e:
        logger.error(f"Error handling Salesforce accounts for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "ACCOUNTS_HANDLING_FAILED", "message": str(e)}}), 500

@salesforce_bp.route('/api/salesforce/opportunities', methods=['GET', 'POST'])
async def handle_opportunities():
    user_id = request.args.get('user_id') if request.method == 'GET' else request.get_json().get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        sf = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
        if not sf:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Salesforce client. Please connect your Salesforce account."}}), 401

        if request.method == 'GET':
            opportunities = await salesforce_service.list_opportunities(sf)
            return jsonify({"ok": True, "data": {"opportunities": opportunities}})
        else: # POST
            data = request.get_json()
            name = data.get('Name')
            stage_name = data.get('StageName')
            close_date = data.get('CloseDate')
            if not all([name, stage_name, close_date]):
                return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "Name, StageName, and CloseDate are required to create an opportunity."}}), 400

            amount = data.get('Amount')
            opportunity = await salesforce_service.create_opportunity(sf, name, stage_name, close_date, amount)
            return jsonify({"ok": True, "data": opportunity})
    except Exception as e:
        logger.error(f"Error handling Salesforce opportunities for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "OPPORTUNITIES_HANDLING_FAILED", "message": str(e)}}), 500

@salesforce_bp.route('/api/salesforce/opportunities/<opportunity_id>', methods=['GET', 'PUT'])
async def handle_opportunity(opportunity_id):
    user_id = request.args.get('user_id') if request.method == 'GET' else request.get_json().get('user_id')
    if not user_id:
        return jsonify({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "user_id is required."}}), 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    if not db_conn_pool:
        return jsonify({"ok": False, "error": {"code": "CONFIG_ERROR", "message": "Database connection not available."}}), 500

    try:
        sf = await salesforce_service.get_salesforce_client(user_id, db_conn_pool)
        if not sf:
            return jsonify({"ok": False, "error": {"code": "AUTH_ERROR", "message": "Could not get authenticated Salesforce client. Please connect your Salesforce account."}}), 401

        if request.method == 'GET':
            opportunity = await salesforce_service.get_opportunity(sf, opportunity_id)
            return jsonify({"ok": True, "data": opportunity})
        else: # PUT
            data = request.get_json()
            fields_to_update = {k: v for k, v in data.items() if k not in ['user_id']}
            opportunity = await salesforce_service.update_opportunity(sf, opportunity_id, fields_to_update)
            return jsonify({"ok": True, "data": opportunity})
    except Exception as e:
        logger.error(f"Error handling Salesforce opportunity {opportunity_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({"ok": False, "error": {"code": "OPPORTUNITY_HANDLING_FAILED", "message": str(e)}}), 500
