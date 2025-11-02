# Add these user authentication endpoints to main_api_app.py

# ============ USER AUTHENTICATION STORAGE ============

# In production, use a proper database like PostgreSQL
# For now, use in-memory storage for demonstration
user_tokens = {}  # {user_id: {service: {access_token, refresh_token, expires_at, user_info}}}

@app.route('/oauth/notion/token-exchange', methods=['POST'])
def notion_token_exchange():
    """Exchange authorization code for user-specific access token"""
    data = request.get_json()
    code = data.get('code')
    user_id = data.get('user_id')  # Get from frontend auth system
    
    if not code:
        return jsonify({'error': 'Authorization code required', 'success': False}), 400
    
    try:
        client_id = os.getenv('NOTION_CLIENT_ID')
        client_secret = os.getenv('NOTION_CLIENT_SECRET')
        redirect_uri = os.getenv('NOTION_REDIRECT_URI', 'http://localhost:3000/oauth/notion/callback')
        
        token_url = 'https://api.notion.com/v1/oauth/token'
        token_data = {
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'redirect_uri': redirect_uri
        }
        
        headers = {'Content-Type': 'application/json'}
        response = requests.post(token_url, json=token_data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            token_info = response.json()
            access_token = token_info.get('access_token')
            
            # Get user's workspace info
            workspace_headers = {
                'Authorization': f'Bearer {access_token}',
                'Notion-Version': '2022-06-28'
            }
            
            search_response = requests.post(
                'https://api.notion.com/v1/search',
                headers=workspace_headers,
                json={'query': '', 'filter': {'property': 'object', 'value': 'database'}},
                timeout=10
            )
            
            if search_response.status_code == 200:
                workspace_data = search_response.json()
                databases = workspace_data.get('results', [])
                
                # Store user token (in production, use encrypted database)
                if user_id not in user_tokens:
                    user_tokens[user_id] = {}
                
                user_tokens[user_id]['notion'] = {
                    'access_token': access_token,
                    'token_type': token_info.get('token_type'),
                    'scope': token_info.get('scope'),
                    'workspace_info': {
                        'databases_count': len(databases),
                        'workspace_name': 'User Workspace',  # You can extract from search results
                        'integration_active': True
                    },
                    'connected_at': datetime.now().isoformat(),
                    'expires_at': token_info.get('expires_in', 0)
                }
                
                return jsonify({
                    'success': True,
                    'user_id': user_id,
                    'service': 'notion',
                    'access_granted': True,
                    'workspace_info': user_tokens[user_id]['notion']['workspace_info'],
                    'message': 'User Notion workspace connected successfully'
                })
        
        return jsonify({
            'error': 'Failed to exchange authorization code',
            'success': False,
            'status_code': response.status_code
        }), 400
        
    except Exception as e:
        return jsonify({
            'error': f'Token exchange error: {str(e)}',
            'success': False
        }), 500

@app.route('/api/real/notion/user-data/<user_id>')
def get_user_notion_data(user_id):
    """Get data from user's specific Notion workspace"""
    
    # Check if user has connected Notion
    if user_id not in user_tokens or 'notion' not in user_tokens[user_id]:
        return jsonify({
            'error': 'User has not connected Notion workspace',
            'success': False
        }), 401
    
    try:
        user_token_info = user_tokens[user_id]['notion']
        access_token = user_token_info['access_token']
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Notion-Version': '2022-06-28'
        }
        
        # Search user's pages and databases
        search_data = {
            'query': '',
            'filter': {
                'value': 'page',
                'property': 'object'
            }
        }
        
        response = requests.post(
            'https://api.notion.com/v1/search',
            headers=headers,
            json=search_data,
            timeout=10
        )
        
        if response.status_code == 200:
            search_results = response.json()
            pages = search_results.get('results', [])
            
            # Also search for databases
            search_data['filter']['value'] = 'database'
            db_response = requests.post(
                'https://api.notion.com/v1/search',
                headers=headers,
                json=search_data,
                timeout=10
            )
            
            databases = []
            if db_response.status_code == 200:
                db_results = db_response.json()
                databases = db_results.get('results', [])
            
            return jsonify({
                'success': True,
                'user_id': user_id,
                'service': 'notion',
                'api_connected': True,
                'real_user_data': True,
                'pages': [
                    {
                        'id': page.get('id'),
                        'title': page.get('properties', {}).get('title', [{}])[0].get('title', 'Untitled') if page.get('properties', {}).get('title') else 'Untitled',
                        'created_time': page.get('created_time'),
                        'last_edited_time': page.get('last_edited_time'),
                        'url': page.get('url'),
                        'user_specific': True
                    } for page in pages[:10]
                ],
                'databases': [
                    {
                        'id': db.get('id'),
                        'title': db.get('title', [{}])[0].get('title', 'Untitled') if db.get('title') else 'Untitled',
                        'created_time': db.get('created_time'),
                        'last_edited_time': db.get('last_edited_time'),
                        'user_specific': True
                    } for db in databases[:10]
                ],
                'total_pages': len(pages),
                'total_databases': len(databases),
                'workspace_info': user_token_info['workspace_info'],
                'last_sync': datetime.now().isoformat()
            })
        
        return jsonify({
            'error': 'Failed to fetch user Notion data',
            'success': False,
            'status_code': response.status_code
        }), response.status_code
        
    except Exception as e:
        return jsonify({
            'error': f'User Notion data fetch error: {str(e)}',
            'success': False
        }), 500

@app.route('/api/v1/users/<user_id>/services')
def get_user_services(user_id):
    """Get all services connected by specific user"""
    
    connected_services = []
    service_info = {}
    
    if user_id in user_tokens:
        for service, info in user_tokens[user_id].items():
            connected_services.append(service)
            service_info[service] = {
                'connected_at': info.get('connected_at'),
                'workspace_info': info.get('workspace_info'),
                'status': 'connected'
            }
    
    return jsonify({
        'success': True,
        'user_id': user_id,
        'connected_services': connected_services,
        'service_info': service_info,
        'total_services': len(connected_services)
    })

@app.route('/api/v1/users/<user_id>/search')
def search_user_data(user_id):
    """Search across all connected services for specific user"""
    query = request.args.get('query', '')
    service = request.args.get('service', 'all')
    
    if not query:
        return jsonify({'error': 'Query parameter required', 'success': False}), 400
    
    results = []
    
    # Search user's Notion data
    if service in ['all', 'notion'] and user_id in user_tokens and 'notion' in user_tokens[user_id]:
        try:
            user_token_info = user_tokens[user_id]['notion']
            access_token = user_token_info['access_token']
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Notion-Version': '2022-06-28'
            }
            
            search_data = {
                'query': query,
                'filter': {'property': 'object', 'value': 'page'}
            }
            
            response = requests.post(
                'https://api.notion.com/v1/search',
                headers=headers,
                json=search_data,
                timeout=10
            )
            
            if response.status_code == 200:
                search_results = response.json()
                pages = search_results.get('results', [])
                
                results.extend([
                    {
                        'id': f'notion_{page.get("id")}',
                        'title': page.get('properties', {}).get('title', [{}])[0].get('title', 'Untitled') if page.get('properties', {}).get('title') else 'Untitled',
                        'source': 'notion',
                        'type': 'page',
                        'url': page.get('url'),
                        'user_specific': True,
                        'match_score': calculate_match_score(query, page.get('properties', {}).get('title', [{}])[0].get('title', ''))
                    } for page in pages[:5]
                ])
        
        except Exception as e:
            print(f"Notion search error for user {user_id}: {e}")
    
    # Sort by relevance
    results.sort(key=lambda x: x.get('match_score', 0), reverse=True)
    
    return jsonify({
        'success': True,
        'user_id': user_id,
        'query': query,
        'service': service,
        'results': results,
        'total': len(results),
        'services_searched': len(['notion'] if user_id in user_tokens and 'notion' in user_tokens[user_id] else []),
        'timestamp': datetime.now().isoformat()
    })

def calculate_match_score(query, title):
    """Simple relevance scoring for search results"""
    if not title:
        return 0
    
    query_lower = query.lower()
    title_lower = title.lower()
    
    if query_lower == title_lower:
        return 100
    elif query_lower in title_lower:
        return 80
    elif title_lower.startswith(query_lower):
        return 60
    elif any(word in title_lower for word in query_lower.split()):
        return 40
    else:
        return 0