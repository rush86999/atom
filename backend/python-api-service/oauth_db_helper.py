# Database connection helper for OAuth handlers
def get_db_connection():
    """Get database connection from Flask app"""
    try:
        from flask import current_app
        # Try multiple ways to get database connection
        db_pool = getattr(current_app, "db_pool", None)
        if not db_pool:
            db_pool = current_app.config.get("DB_CONNECTION_POOL", None)
        if not db_pool:
            db_pool = current_app.config.get("DATABASE_POOL", None)
        return db_pool
    except:
        return None

def handle_oauth_status(service_name, user_id):
    """Standard OAuth status handler"""
    try:
        db_pool = get_db_connection()
        if not db_pool:
            return {
                "ok": False,
                "error": {
                    "code": "CONFIG_ERROR",
                    "message": "Database connection pool is not available.",
                },
            }, 500
        
        # Check if tokens exist for user
        try:
            # Use appropriate token storage function
            tokens = check_user_tokens(db_pool, user_id, service_name)
            if tokens:
                return {
                    "ok": True,
                    "status": "connected",
                    "service": service_name,
                    "user_id": user_id
                }
            else:
                return {
                    "ok": True,
                    "status": "disconnected", 
                    "service": service_name,
                    "user_id": user_id
                }
        except Exception as token_error:
            return {
                "ok": False,
                "error": {
                    "code": "TOKEN_ERROR",
                    "message": f"Failed to check tokens: {str(token_error)}",
                },
            }, 500
            
    except Exception as e:
        return {
            "ok": False,
            "error": {
                "code": "SERVER_ERROR",
                "message": str(e),
            },
        }, 500

def check_user_tokens(db_pool, user_id, service_name):
    """Check if user has tokens for service"""
    # Simple token check implementation
    return False  # Placeholder
