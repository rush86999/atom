"""
Figma Integration Registration
Add Figma OAuth handler, enhanced API, and health monitoring to main app
"""

import logging

# Figma integration registration function
def register_figma_integration(app, db_pool):
    """Register all Figma components with the main app"""
    try:
        # Import Figma OAuth handler
        try:
            from auth_handler_figma import auth_figma_bp
            from db_oauth_figma import init_figma_oauth_table
            
            app.register_blueprint(auth_figma_bp, url_prefix="/api/auth", name="figma_auth")
            logging.info("Figma OAuth handler registered successfully")
            
            # Initialize database table
            import asyncio
            asyncio.run(init_figma_oauth_table(db_pool))
            logging.info("Figma OAuth table initialized successfully")
            
            FIGMA_OAUTH_AVAILABLE = True
        except ImportError as e:
            logging.warning(f"Figma OAuth handler not available: {e}")
            FIGMA_OAUTH_AVAILABLE = False
        
        # Import Figma enhanced API
        try:
            from figma_enhanced_api import figma_enhanced_bp
            
            app.register_blueprint(
                figma_enhanced_bp,
                url_prefix="/api/figma/enhanced",
                name="figma_enhanced"
            )
            logging.info("Figma Enhanced API registered successfully")
            
            FIGMA_ENHANCED_AVAILABLE = True
        except ImportError as e:
            logging.warning(f"Figma Enhanced API not available: {e}")
            FIGMA_ENHANCED_AVAILABLE = False
        
        # Import Figma handler
        try:
            from figma_handler import figma_bp
            
            app.register_blueprint(figma_bp, url_prefix="/api", name="figma_handler")
            logging.info("Figma Handler registered successfully")
            
            FIGMA_HANDLER_AVAILABLE = True
        except ImportError as e:
            logging.warning(f"Figma Handler not available: {e}")
            FIGMA_HANDLER_AVAILABLE = False
        
        # Import Figma health handler
        try:
            from figma_health_handler import figma_health_bp
            
            app.register_blueprint(
                figma_health_bp,
                url_prefix="/api/figma",
                name="figma_health"
            )
            logging.info("Figma Health Handler registered successfully")
            
            FIGMA_HEALTH_AVAILABLE = True
        except ImportError as e:
            logging.warning(f"Figma Health Handler not available: {e}")
            FIGMA_HEALTH_AVAILABLE = False
        
        # Add Figma OAuth endpoints
        @app.route("/api/oauth/figma/url", methods=["GET"])
        def figma_oauth_url():
            """Generate Figma OAuth authorization URL"""
            from figma_service_real import get_figma_service_mock
            import os
            
            client_id = os.getenv("FIGMA_CLIENT_ID")
            redirect_uri = os.getenv("FIGMA_REDIRECT_URI", "http://localhost:3000/oauth/figma/callback")
            
            if not client_id or client_id.startswith(("mock_", "YOUR_")):
                return jsonify({
                    "error": "Figma OAuth not configured",
                    "message": "Add FIGMA_CLIENT_ID to your .env file",
                    "success": False,
                }), 400
            
            # Figma OAuth parameters
            state = os.urandom(16).hex()
            scopes = ["file_read", "file_write", "team_read", "user_read"]
            scope = " ".join(scopes)
            
            oauth_url = (
                f"https://www.figma.com/oauth?"
                f"client_id={client_id}&"
                f"redirect_uri={redirect_uri}&"
                f"scope={scope}&"
                f"state={state}&"
                f"response_type=code"
            )
            
            return jsonify({
                "oauth_url": oauth_url,
                "service": "figma",
                "success": True,
                "state": state,
                "scopes": scopes
            })
        
        # Add Figma OAuth callback endpoint
        @app.route("/api/oauth/figma/callback", methods=["POST"])
        def figma_oauth_callback():
            """Handle Figma OAuth callback"""
            data = request.get_json()
            code = data.get("code")
            state = data.get("state")
            
            if not code:
                return jsonify({
                    "success": False,
                    "error": "Authorization code required",
                    "service": "figma",
                }), 400
            
            # Exchange code for tokens (simplified for demo)
            mock_response = {
                "success": True,
                "service": "figma",
                "user_info": {
                    "id": "fig-user-123",
                    "name": "John Designer",
                    "username": "johndesigner",
                    "email": "john@company.com",
                    "profile_picture_url": "https://example.com/john.png"
                },
                "tokens": {
                    "access_token": "mock_figma_access_token_" + os.urandom(8).hex(),
                    "refresh_token": "mock_figma_refresh_token_" + os.urandom(8).hex(),
                    "expires_in": 3600,
                    "scope": "file_read file_write team_read user_read"
                },
                "workspace_info": {
                    "id": "workspace-1",
                    "name": "Design Team"
                },
                "stored": True
            }
            
            return jsonify(mock_response)
        
        return {
            "FIGMA_OAUTH_AVAILABLE": FIGMA_OAUTH_AVAILABLE,
            "FIGMA_ENHANCED_AVAILABLE": FIGMA_ENHANCED_AVAILABLE,
            "FIGMA_HANDLER_AVAILABLE": FIGMA_HANDLER_AVAILABLE,
            "FIGMA_HEALTH_AVAILABLE": FIGMA_HEALTH_AVAILABLE,
        }
        
    except Exception as e:
        logging.error(f"Failed to register Figma integration: {e}")
        return {
            "FIGMA_OAUTH_AVAILABLE": False,
            "FIGMA_ENHANCED_AVAILABLE": False,
            "FIGMA_HANDLER_AVAILABLE": False,
            "FIGMA_HEALTH_AVAILABLE": False,
        }


# Figma service registration for global access
def register_figma_service():
    """Register Figma service for global access"""
    try:
        from figma_service_real import figma_service
        
        # Service is already globally available via singleton
        return {
            "available": True,
            "service_info": figma_service.get_service_info()
        }
        
    except ImportError as e:
        logging.warning(f"Figma service not available: {e}")
        return {
            "available": False,
            "error": str(e)
        }


# Figma desktop integration
def register_figma_desktop_integration():
    """Register Figma desktop integration functions"""
    try:
        from figma_service_real import get_figma_service_mock, get_figma_service_real
        
        # Register desktop integration functions
        desktop_functions = {
            "get_figma_files": lambda user_id: get_figma_service_mock().get_user_files(user_id),
            "get_figma_teams": lambda user_id: get_figma_service_mock().get_user_teams(user_id),
            "get_figma_projects": lambda user_id, team_id: get_figma_service_mock().get_team_projects(user_id, team_id),
            "get_figma_components": lambda user_id, file_key: get_figma_service_mock().get_file_components(user_id, file_key),
            "get_figma_user_profile": lambda user_id: get_figma_service_mock().get_user_profile(user_id),
            "search_figma": lambda user_id, query: get_figma_service_mock().search_figma(user_id, query)
        }
        
        return {
            "available": True,
            "functions": desktop_functions
        }
        
    except ImportError as e:
        logging.warning(f"Figma desktop integration not available: {e}")
        return {
            "available": False,
            "error": str(e)
        }