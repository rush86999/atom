import logging
import os
from flask import Blueprint, request, redirect, session, current_app
import requests
from . import db_oauth_zoho

logger = logging.getLogger(__name__)

zoho_auth_bp = Blueprint('zoho_auth_bp', __name__)

ZOHO_CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
ZOHO_REDIRECT_URI = os.getenv("ZOHO_REDIRECT_URI")

@zoho_auth_bp.route('/api/auth/zoho/login')
def zoho_login():
    session['user_id'] = request.args.get('user_id')
    return redirect(
        f"https://accounts.zoho.com/oauth/v2/auth?scope=ZohoBooks.fullaccess.all&client_id={ZOHO_CLIENT_ID}&response_type=code&redirect_uri={ZOHO_REDIRECT_URI}&access_type=offline"
    )

@zoho_auth_bp.route('/api/auth/zoho/callback')
async def zoho_callback():
    code = request.args.get('code')
    user_id = session.pop('user_id', None)
    if not user_id:
        return "Error: User ID not found in session.", 400

    token_url = "https://accounts.zoho.com/oauth/v2/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "redirect_uri": ZOHO_REDIRECT_URI,
        "code": code,
    }
    response = requests.post(token_url, data=token_data)
    if response.status_code != 200:
        logger.error(f"Error getting Zoho token: {response.text}")
        return "Error getting Zoho token.", 400
    token_info = response.json()

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    await db_oauth_zoho.store_zoho_tokens(user_id, token_info['access_token'], token_info['refresh_token'], db_conn_pool)

    return "Zoho authentication successful!", 200

@zoho_auth_bp.route('/api/auth/zoho/disconnect', methods=['POST'])
async def zoho_disconnect():
    data = request.get_json()
    user_id = data.get('user_id')
    if not user_id:
        return "Error: User ID is required.", 400

    db_conn_pool = current_app.config.get('DB_CONNECTION_POOL')
    await db_oauth_zoho.delete_zoho_tokens(user_id, db_conn_pool)

    return "Zoho account disconnected successfully!", 200
