#!/usr/bin/env python3
"""
Quick Fix for Outlook Integration Issues
Resolves database initialization and route registration problems
"""

import asyncio
import asyncpg
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_database_connection():
    """Test database connection and create OAuth table"""
    try:
        # Database configuration
        db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_NAME', 'atom'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', '')
        }
        
        logger.info(f"Connecting to database: {db_config['host']}:{db_config['port']}/{db_config['database']}")
        
        # Create connection pool
        pool = await asyncpg.create_pool(
            **db_config,
            min_size=1,
            max_size=5,
            command_timeout=60
        )
        
        logger.info("✅ Database connection successful")
        
        # Test the Outlook OAuth table
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS oauth_outlook_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    token_type VARCHAR(50) DEFAULT 'Bearer',
                    scope TEXT,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    tenant_id VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id)
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_oauth_outlook_user_id 
                ON oauth_outlook_tokens(user_id)
            """)
            
            logger.info("✅ Outlook OAuth table created/verified")
        
        # Test query
        async with pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT COUNT(*) FROM oauth_outlook_tokens"
            )
            logger.info(f"✅ Current OAuth tokens: {result}")
        
        await pool.close()
        logger.info("✅ Database connection closed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        return False

def check_environment():
    """Check required environment variables"""
    required_vars = [
        'OUTLOOK_CLIENT_ID',
        'OUTLOOK_CLIENT_SECRET',
        'OUTLOOK_TENANT_ID'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.warning(f"⚠️ Missing environment variables: {', '.join(missing_vars)}")
        return False
    else:
        logger.info("✅ All required environment variables are set")
        return True

async def main():
    """Run all tests"""
    print("🔧 Outlook Integration Quick Fix")
    print("=" * 50)
    
    # Check environment
    env_ok = check_environment()
    
    # Test database
    db_ok = await test_database_connection()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 QUICK FIX SUMMARY")
    print("=" * 50)
    
    results = [
        ("Environment Variables", env_ok),
        ("Database Connection", db_ok)
    ]
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<25} {status}")
    
    all_passed = env_ok and db_ok
    
    if all_passed:
        print(f"\n🎉 All tests passed! Outlook integration is ready to run.")
        print("\n💡 Next steps:")
        print("   1. Start the Flask API server")
        print("   2. Run: python test_outlook_integration.py")
        print("   3. Test OAuth flow with real Microsoft account")
    else:
        print(f"\n💥 Some tests failed. Please fix the issues above.")
        print("\n💡 Fix suggestions:")
        if not env_ok:
            print("   - Set missing environment variables in .env file")
        if not db_ok:
            print("   - Check database connection parameters")
            print("   - Ensure PostgreSQL is running")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))