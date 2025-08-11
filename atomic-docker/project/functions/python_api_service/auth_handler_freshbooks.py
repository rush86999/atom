import logging
import os
from flask import Blueprint, request, redirect, session, current_app, jsonify
import requests
from . import db_oauth_freshbooks

logger = logging.getLogger(__name__)

freshbooks_auth_bp = Blueprint('freshbooks_auth_bp', __name__)

FRESHBOOKS_CLIENT_ID = os.getenv("FRESHBOOKS_CLIENT_ID")
FRESHBOOKS_CLIENT_SECRET = os.getenv("FRESHBOOKS_CLIENT_SECRET")
FRESHBOOKS_REDIRECT_URI = os.getenv("FRESHBOOKS_REDIRECT_URI")

@freshbooks_auth_bp.route('/api/auth/freshbooks/login')
def freshbooks_login():
    session['user_id'] = request.args.get('user_id')
    return redirect(
        f"https://my.freshbooks.com/service/auth/oauth/authorize?client_id={FRESHBOOKS_CLIENT_ID}&response_type=code&redirect_uri={FRESHBOOKS_REDIRECT_URI}"
    )

@freshbooks_auth_bp.route('/api/auth/freshbooks/callback')
async def freshbooks_callback():
    code = request.args.get('code')
    user_id = session.pop('user_id', None)
    if not user_id:
        return "Error: User ID not found in session.", 400

    token_url = "https://api.freshbooks.com/auth/oauth/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": FRESHBOOKS_CLIENT_ID,
        "client_secret": FRESHBOOKS_CLIENT_SECRET,
        "redirect_uri": FRESHBOOKS_REDIRECT_URI,
        "code": code,
    }
    response = requests.post(token_url, json=token_data)
    if response.status_code != 200:
        logger.error(f"Error getting FreshBooks token: {response.text}")
        return "Error getting FreshBooks token.", 400
    token_info = response.json()

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    await db_oauth_freshbooks.store_freshbooks_tokens(user_id, token_info['access_token'], token_info['refresh_token'], db_conn_pool)

    return "FreshBooks authentication successful!", 200

@freshbooks_auth_bp.route('/api/auth/freshbooks/disconnect', methods=['POST'])
async def freshbooks_disconnect():
    data = request.get_json()
    user_id = data.get('user_id')
    if not user_id:
        return "Error: User ID is required.", 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    await db_oauth_freshbooks.delete_freshbooks_tokens(user_id, db_conn_pool)

    return "FreshBooks account disconnected successfully!", 200

@freshbooks_auth_bp.route('/api/auth/freshbooks/status', methods=['GET'])
async def freshbooks_status():
    user_id = request.args.get('user_id')
    if not user_id:
        return "Error: User ID is required.", 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    status = await db_oauth_freshbooks.get_freshbooks_integration_status(user_id, db_conn_pool)

    return jsonify(status), 200
