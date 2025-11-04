# Add these OAuth callback endpoints to main_api_app.py

# ============ OAUTH CALLBACK ENDPOINTS ============

@app.route('/oauth/github/callback')
def github_oauth_callback():
    """Handle GitHub OAuth callback"""
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        return jsonify({'error': 'Authorization code not found', 'success': False}), 400
    
    try:
        # Exchange code for access token
        client_id = os.getenv('GITHUB_CLIENT_ID')
        client_secret = os.getenv('GITHUB_CLIENT_SECRET')
        
        token_url = 'https://github.com/login/oauth/access_token'
        data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'redirect_uri': os.getenv('GITHUB_REDIRECT_URI', 'http://localhost:3000/oauth/github/callback')
        }
        
        headers = {'Accept': 'application/json'}
        response = requests.post(token_url, data=data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            
            # Get user info
            user_headers = {'Authorization': f'token {access_token}'}
            user_response = requests.get('https://api.github.com/user', headers=user_headers, timeout=10)
            
            if user_response.status_code == 200:
                user_data = user_response.json()
                
                # Return success with user and token info
                # In production, store this securely per user
                return jsonify({
                    'success': True,
                    'service': 'github',
                    'user': {
                        'id': user_data.get('id'),
                        'login': user_data.get('login'),
                        'name': user_data.get('name'),
                        'email': user_data.get('email'),
                        'avatar_url': user_data.get('avatar_url')
                    },
                    'tokens': {
                        'access_token': access_token,
                        'token_type': token_data.get('token_type'),
                        'scope': token_data.get('scope')
                    },
                    'message': 'GitHub connected successfully'
                })
        
        return jsonify({'error': 'Failed to exchange authorization code', 'success': False}), 400
        
    except Exception as e:
        return jsonify({'error': f'OAuth callback error: {str(e)}', 'success': False}), 500

@app.route('/oauth/google/callback')
def google_oauth_callback():
    """Handle Google OAuth callback"""
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        return jsonify({'error': 'Authorization code not found', 'success': False}), 400
    
    try:
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:3000/oauth/google/callback')
        
        token_url = 'https://oauth2.googleapis.com/token'
        data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri
        }
        
        response = requests.post(token_url, data=data, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            
            # Get user info
            user_headers = {'Authorization': f'Bearer {access_token}'}
            user_response = requests.get('https://www.googleapis.com/oauth2/v2/userinfo', headers=user_headers, timeout=10)
            
            if user_response.status_code == 200:
                user_data = user_response.json()
                
                return jsonify({
                    'success': True,
                    'service': 'google',
                    'user': {
                        'id': user_data.get('id'),
                        'email': user_data.get('email'),
                        'name': user_data.get('name'),
                        'picture': user_data.get('picture')
                    },
                    'tokens': {
                        'access_token': access_token,
                        'refresh_token': token_data.get('refresh_token'),
                        'token_type': token_data.get('token_type'),
                        'expires_in': token_data.get('expires_in')
                    },
                    'message': 'Google connected successfully'
                })
        
        return jsonify({'error': 'Failed to exchange authorization code', 'success': False}), 400
        
    except Exception as e:
        return jsonify({'error': f'OAuth callback error: {str(e)}', 'success': False}), 500

@app.route('/oauth/slack/callback')
def slack_oauth_callback():
    """Handle Slack OAuth callback"""
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        return jsonify({'error': 'Authorization code not found', 'success': False}), 400
    
    try:
        client_id = os.getenv('SLACK_CLIENT_ID')
        client_secret = os.getenv('SLACK_CLIENT_SECRET')
        redirect_uri = os.getenv('SLACK_REDIRECT_URI', 'http://localhost:3000/oauth/slack/callback')
        
        token_url = 'https://slack.com/api/oauth.v2.access'
        data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'redirect_uri': redirect_uri
        }
        
        response = requests.post(token_url, data=data, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            if token_data.get('ok'):
                access_token = token_data.get('access_token')
                
                # Get user info
                user_headers = {'Authorization': f'Bearer {access_token}'}
                user_response = requests.get('https://slack.com/api/users.info', headers=user_headers, timeout=10)
                
                if user_response.status_code == 200 and user_response.json().get('ok'):
                    user_data = user_response.json().get('user')
                    
                    return jsonify({
                        'success': True,
                        'service': 'slack',
                        'user': {
                            'id': user_data.get('id'),
                            'name': user_data.get('name'),
                            'email': user_data.get('email'),
                            'real_name': user_data.get('real_name'),
                            'display_name': user_data.get('profile').get('display_name') if user_data.get('profile') else None,
                            'avatar': user_data.get('profile').get('image_192') if user_data.get('profile') else None
                        },
                        'team': token_data.get('team'),
                        'tokens': {
                            'access_token': access_token,
                            'token_type': token_data.get('token_type'),
                            'scope': token_data.get('scope')
                        },
                        'message': 'Slack connected successfully'
                    })
        
        return jsonify({'error': 'Failed to exchange authorization code', 'success': False}), 400
        
    except Exception as e:
        return jsonify({'error': f'OAuth callback error: {str(e)}', 'success': False}), 500

@app.route('/oauth/notion/callback')
def notion_oauth_callback():
    """Handle Notion OAuth callback"""
    code = request.args.get('code')
    state = request.args.get('state')
    owner = request.args.get('owner') or 'user'
    
    if not code:
        return jsonify({'error': 'Authorization code not found', 'success': False}), 400
    
    try:
        client_id = os.getenv('NOTION_CLIENT_ID')
        client_secret = os.getenv('NOTION_CLIENT_SECRET')
        redirect_uri = os.getenv('NOTION_REDIRECT_URI', 'http://localhost:3000/oauth/notion/callback')
        
        token_url = 'https://api.notion.com/v1/oauth/token'
        data = {
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'redirect_uri': redirect_uri
        }
        
        headers = {'Content-Type': 'application/json'}
        response = requests.post(token_url, json=data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            
            # Get user info (Notion doesn't have user info endpoint, use bot token if available)
            bot_token = os.getenv('NOTION_TOKEN')
            user_info = {'access_to_workspace': True}
            
            return jsonify({
                'success': True,
                'service': 'notion',
                'user': {
                    'access_to_workspace': True,
                    'owner': owner,
                    'workspace_name': 'ATOM Enterprise Workspace'  # You can customize this
                },
                'tokens': {
                    'access_token': access_token,
                    'bot_token': bot_token if bot_token else None,
                    'token_type': token_data.get('token_type'),
                    'expires_in': token_data.get('expires_in')
                },
                'message': 'Notion connected successfully'
            })
        
        return jsonify({'error': 'Failed to exchange authorization code', 'success': False}), 400
        
    except Exception as e:
        return jsonify({'error': f'OAuth callback error: {str(e)}', 'success': False}), 500

@app.route('/oauth/trello/callback')
def trello_oauth_callback():
    """Handle Trello OAuth callback"""
    token = request.args.get('token')
    state = request.args.get('state')
    
    if not token:
        return jsonify({'error': 'Authorization token not found', 'success': False}), 400
    
    try:
        api_key = os.getenv('TRELLO_API_KEY')
        
        # Trello uses simple token flow, no need to exchange
        return jsonify({
            'success': True,
            'service': 'trello',
            'user': {
                'token': token,
                'api_key': api_key
            },
            'tokens': {
                'access_token': token,
                'api_key': api_key
            },
            'message': 'Trello connected successfully'
        })
        
    except Exception as e:
        return jsonify({'error': f'OAuth callback error: {str(e)}', 'success': False}), 500

@app.route('/oauth/asana/callback')
def asana_oauth_callback():
    """Handle Asana OAuth callback"""
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        return jsonify({'error': 'Authorization code not found', 'success': False}), 400
    
    try:
        client_id = os.getenv('ASANA_CLIENT_ID')
        client_secret = os.getenv('ASANA_CLIENT_SECRET')
        redirect_uri = os.getenv('ASANA_REDIRECT_URI', 'http://localhost:3000/oauth/asana/callback')
        
        token_url = 'https://app.asana.com/-/oauth_token'
        data = {
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'redirect_uri': redirect_uri
        }
        
        headers = {'Content-Type': 'application/json'}
        response = requests.post(token_url, json=data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            
            # Get user info
            user_headers = {'Authorization': f'Bearer {access_token}'}
            user_response = requests.get('https://app.asana.com/api/1.0/users/me', headers=user_headers, timeout=10)
            
            if user_response.status_code == 200:
                user_data = user_response.json().get('data', {})
                
                return jsonify({
                    'success': True,
                    'service': 'asana',
                    'user': {
                        'id': user_data.get('gid'),
                        'email': user_data.get('email'),
                        'name': user_data.get('name')
                    },
                    'tokens': {
                        'access_token': access_token,
                        'refresh_token': token_data.get('refresh_token'),
                        'expires_in': token_data.get('expires_in')
                    },
                    'message': 'Asana connected successfully'
                })
        
        return jsonify({'error': 'Failed to exchange authorization code', 'success': False}), 400
        
    except Exception as e:
        return jsonify({'error': f'OAuth callback error: {str(e)}', 'success': False}), 500

@app.route('/oauth/dropbox/callback')
def dropbox_oauth_callback():
    """Handle Dropbox OAuth callback"""
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        return jsonify({'error': 'Authorization code not found', 'success': False}), 400
    
    try:
        app_key = os.getenv('DROPBOX_APP_KEY')
        app_secret = os.getenv('DROPBOX_APP_SECRET')
        redirect_uri = os.getenv('DROPBOX_REDIRECT_URI', 'http://localhost:3000/oauth/dropbox/callback')
        
        token_url = 'https://api.dropboxapi.com/oauth2/token'
        data = {
            'grant_type': 'authorization_code',
            'client_id': app_key,
            'client_secret': app_secret,
            'code': code,
            'redirect_uri': redirect_uri
        }
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = requests.post(token_url, data=data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            
            # Get user info
            user_headers = {'Authorization': f'Bearer {access_token}'}
            user_response = requests.get('https://api.dropboxapi.com/2/users/get_current_account', headers=user_headers, timeout=10)
            
            if user_response.status_code == 200:
                user_data = user_response.json()
                
                return jsonify({
                    'success': True,
                    'service': 'dropbox',
                    'user': {
                        'account_id': user_data.get('account_id'),
                        'name': user_data.get('name'),
                        'email': user_data.get('email'),
                        'profile_photo_url': user_data.get('profile_photo_url')
                    },
                    'tokens': {
                        'access_token': access_token,
                        'token_type': token_data.get('token_type'),
                        'expires_in': token_data.get('expires_in')
                    },
                    'message': 'Dropbox connected successfully'
                })
        
        return jsonify({'error': 'Failed to exchange authorization code', 'success': False}), 400
        
    except Exception as e:
        return jsonify({'error': f'OAuth callback error: {str(e)}', 'success': False}), 500