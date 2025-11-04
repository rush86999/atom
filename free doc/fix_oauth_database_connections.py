#!/usr/bin/env python3
"""
Fix OAuth Status Endpoints Database Connection Issue
"""

import os
import sys
import logging

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend', 'python-api-service'))

def fix_oauth_database_connections():
    """Fix OAuth status endpoints database connection issues"""
    
    print("🔧 Fixing OAuth Status Endpoint Database Connections")
    print("=" * 60)
    
    # Services to fix
    oauth_services = [
        'gmail', 'outlook', 'slack', 'teams', 'trello', 
        'asana', 'notion', 'github', 'dropbox', 'gdrive'
    ]
    
    fixes_applied = 0
    
    for service in oauth_services:
        auth_file = f"auth_handler_{service}.py"
        
        if os.path.exists(os.path.join('backend', 'python-api-service', auth_file)):
            print(f"🔧 Fixing {service} OAuth database connection...")
            
            # Read the auth file
            file_path = os.path.join('backend', 'python-api-service', auth_file)
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Fix database connection reference
            original_line = 'db_conn_pool = current_app.config.get("DB_CONNECTION_POOL", None)'
            fixed_line = 'db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)'
            
            if original_line in content:
                content = content.replace(original_line, fixed_line)
                
                # Write back the fixed content
                with open(file_path, 'w') as f:
                    f.write(content)
                
                print(f"   ✅ Fixed {service} database connection")
                fixes_applied += 1
            else:
                print(f"   ⚠️  Database connection pattern not found in {service}")
        else:
            print(f"   ⚠️  {service} auth file not found: {auth_file}")
    
    print("\n" + "=" * 60)
    print(f"🎉 OAuth Database Connection Fix Complete!")
    print(f"   Fixes applied: {fixes_applied}/{len(oauth_services)}")
    
    if fixes_applied > 0:
        print("\n📋 Next Steps:")
        print("   1. Restart the backend application")
        print("   2. Test OAuth status endpoints")
        print("   3. Verify all services return working status")
        
        return True
    else:
        print("\n⚠️  No fixes were applied. Check file patterns.")
        return False

def create_database_connection_helper():
    """Create a database connection helper for OAuth handlers"""
    
    helper_code = '''# Database connection helper for OAuth handlers
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
'''
    
    helper_path = os.path.join('backend', 'python-api-service', 'oauth_db_helper.py')
    with open(helper_path, 'w') as f:
        f.write(helper_code)
    
    print(f"📄 Created OAuth database helper: {helper_path}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Apply fixes
    success = fix_oauth_database_connections()
    
    # Create helper
    create_database_connection_helper()
    
    if success:
        print("\n🚀 OAuth status endpoints should now work after backend restart!")
        print("   Run: cd backend/python-api-service && python main_api_app.py")
    else:
        print("\n❌ No fixes applied. Manual intervention may be required.")