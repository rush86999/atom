#!/usr/bin/env python3
"""
Xero Migration Runner
Run Xero database schema migrations
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

async def run_xero_migration():
    """Run Xero schema migration"""
    try:
        # Database connection
        db_pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            database=os.getenv("DB_NAME", "atom"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            min_size=2,
            max_size=10,
        )
        
        logger.info("Connected to database successfully")
        
        # Read and execute Xero schema
        schema_path = os.path.join(os.path.dirname(__file__), "xero_schema.sql")
        
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Execute schema
        async with db_pool.acquire() as conn:
            await conn.execute(schema_sql)
            
        logger.info("Xero schema migration completed successfully")
        
        # Close connection
        await db_pool.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to run Xero migration: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_xero_migration())
    if success:
        logger.info("Xero migration completed successfully")
        exit(0)
    else:
        logger.error("Xero migration failed")
        exit(1)