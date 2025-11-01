#!/usr/bin/env python3
"""
Database Migration Runner for ATOM Platform

This script runs database migrations to create necessary tables for user authentication.
It should be run before starting the application to ensure the database schema is up to date.
"""

import os
import sys
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_database_connection():
    """Get database connection from environment variables"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable is not set")
        logger.info("Using default connection parameters")
        return psycopg2.connect(
            host="localhost",
            port=5432,
            database="atom_production",
            user="atom_user",
            password="atom_secure_2024",
        )

    try:
        return psycopg2.connect(database_url)
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


def run_migration(connection, migration_file_path):
    """Run a single migration file"""
    try:
        with open(migration_file_path, "r") as f:
            migration_sql = f.read()

        with connection.cursor() as cursor:
            cursor.execute(migration_sql)

        logger.info(f"Successfully executed migration: {migration_file_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to execute migration {migration_file_path}: {e}")
        return False


def check_table_exists(connection, table_name):
    """Check if a table exists in the database"""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = %s
                );
            """,
                (table_name,),
            )
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error checking if table {table_name} exists: {e}")
        return False


def main():
    """Main migration runner function"""
    logger.info("🚀 Starting ATOM Database Migration")
    logger.info("=" * 50)

    try:
        # Get database connection
        connection = get_database_connection()
        connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        logger.info("✅ Connected to database successfully")

        # Check if User_Credentials table already exists
        if check_table_exists(connection, "User_Credentials"):
            logger.info("✅ User_Credentials table already exists")
            logger.info("Migration completed successfully")
            return True

        # Run the user credentials migration
        migration_file = Path(__file__).parent / "create_user_credentials_table.sql"

        if not migration_file.exists():
            logger.error(f"Migration file not found: {migration_file}")
            return False

        logger.info(f"Running migration: {migration_file.name}")

        if run_migration(connection, migration_file):
            logger.info("✅ Migration completed successfully")

            # Verify the table was created
            if check_table_exists(connection, "User_Credentials"):
                logger.info("✅ User_Credentials table verified")
            else:
                logger.error("❌ User_Credentials table was not created")
                return False

            return True
        else:
            logger.error("❌ Migration failed")
            return False

    except Exception as e:
        logger.error(f"Migration failed with error: {e}")
        return False
    finally:
        if "connection" in locals():
            connection.close()
            logger.info("Database connection closed")


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
