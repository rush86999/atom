"""
Migration Runner for ATOM Google Drive Integration
Handles database schema migrations and data seeding
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import asyncpg
import psycopg2
from psycopg2.extras import execute_values
import psycopg2.pool
from loguru import logger

class Migration:
    """Migration model"""
    
    def __init__(self, version: str, name: str, up_sql: str, down_sql: str = ""):
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql
        self.applied_at: Optional[datetime] = None

class MigrationRunner:
    """Migration runner for Google Drive integration"""
    
    def __init__(self, db_url: str, migrations_dir: str = "migrations"):
        self.db_url = db_url
        self.migrations_dir = Path(migrations_dir)
        self.migrations: List[Migration] = []
        self.applied_migrations: Dict[str, Migration] = {}
        
        # Ensure migrations directory exists
        self.migrations_dir.mkdir(exist_ok=True)
        
        # Initialize connection pool
        self.connection_pool = psycopg2.pool.SimpleConnectionPool(
            1, 10, db_url
        )
        
        logger.info("Migration runner initialized")
    
    def load_migrations(self) -> None:
        """Load all migration files"""
        
        try:
            self.migrations = []
            
            # Load schema migration
            schema_file = self.migrations_dir / "google_drive_schema.sql"
            if schema_file.exists():
                with open(schema_file, 'r', encoding='utf-8') as f:
                    schema_sql = f.read()
                
                migration = Migration(
                    version="001",
                    name="Create Google Drive schema",
                    up_sql=schema_sql,
                    down_sql="-- Drop schema\nDROP SCHEMA IF EXISTS google_drive CASCADE;"
                )
                self.migrations.append(migration)
            
            # Load additional migration files
            migration_files = sorted(
                self.migrations_dir.glob("migration_*.sql"),
                key=lambda x: x.name
            )
            
            for migration_file in migration_files:
                version = migration_file.name.split('_')[1].split('.')[0]
                name = f"Migration {version}"
                
                with open(migration_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Split up and down migrations
                parts = content.split("-- DOWN")
                up_sql = parts[0].replace("-- UP", "").strip()
                down_sql = parts[1].strip() if len(parts) > 1 else ""
                
                migration = Migration(
                    version=version,
                    name=name,
                    up_sql=up_sql,
                    down_sql=down_sql
                )
                self.migrations.append(migration)
            
            logger.info(f"Loaded {len(self.migrations)} migrations")
        
        except Exception as e:
            logger.error(f"Error loading migrations: {e}")
            raise
    
    def create_migration_table(self) -> None:
        """Create migration tracking table"""
        
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(20) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    execution_time_ms INTEGER
                );
            """)
            
            conn.commit()
            logger.info("Migration table created")
        
        except Exception as e:
            logger.error(f"Error creating migration table: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def load_applied_migrations(self) -> None:
        """Load applied migrations from database"""
        
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT version, name, applied_at 
                FROM schema_migrations 
                ORDER BY applied_at
            """)
            
            rows = cursor.fetchall()
            self.applied_migrations = {}
            
            for row in rows:
                migration = Migration(
                    version=row[0],
                    name=row[1],
                    up_sql="",
                    down_sql=""
                )
                migration.applied_at = row[2]
                self.applied_migrations[version] = migration
            
            logger.info(f"Loaded {len(self.applied_migrations)} applied migrations")
        
        except Exception as e:
            logger.error(f"Error loading applied migrations: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def get_pending_migrations(self) -> List[Migration]:
        """Get pending migrations"""
        
        pending = []
        for migration in self.migrations:
            if migration.version not in self.applied_migrations:
                pending.append(migration)
        
        return sorted(pending, key=lambda m: m.version)
    
    def apply_migration(self, migration: Migration) -> bool:
        """Apply a single migration"""
        
        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor()
            
            logger.info(f"Applying migration {migration.version}: {migration.name}")
            
            start_time = datetime.now()
            
            # Execute migration
            cursor.execute(migration.up_sql)
            
            # Record migration
            end_time = datetime.now()
            execution_time = int((end_time - start_time).total_seconds() * 1000)
            
            cursor.execute("""
                INSERT INTO schema_migrations (version, name, applied_at, execution_time_ms)
                VALUES (%s, %s, %s, %s)
            """, (migration.version, migration.name, end_time, execution_time))
            
            conn.commit()
            
            migration.applied_at = end_time
            self.applied_migrations[migration.version] = migration
            
            logger.info(f"Migration {migration.version} applied successfully ({execution_time}ms)")
            return True
        
        except Exception as e:
            logger.error(f"Error applying migration {migration.version}: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def rollback_migration(self, migration: Migration) -> bool:
        """Rollback a single migration"""
        
        conn = None
        try:
            if not migration.down_sql:
                logger.warning(f"No rollback script for migration {migration.version}")
                return False
            
            conn = self.connection_pool.getconn()
            cursor = conn.cursor()
            
            logger.info(f"Rolling back migration {migration.version}: {migration.name}")
            
            # Execute rollback
            cursor.execute(migration.down_sql)
            
            # Remove from applied migrations
            cursor.execute("""
                DELETE FROM schema_migrations WHERE version = %s
            """, (migration.version,))
            
            conn.commit()
            
            # Remove from applied migrations
            if migration.version in self.applied_migrations:
                del self.applied_migrations[migration.version]
            
            logger.info(f"Migration {migration.version} rolled back successfully")
            return True
        
        except Exception as e:
            logger.error(f"Error rolling back migration {migration.version}: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def run_migrations(self, target_version: Optional[str] = None) -> bool:
        """Run all pending migrations up to target version"""
        
        try:
            logger.info("Starting migration process")
            
            # Load migrations
            self.load_migrations()
            
            # Create migration table
            self.create_migration_table()
            
            # Load applied migrations
            self.load_applied_migrations()
            
            # Get pending migrations
            pending = self.get_pending_migrations()
            
            if not pending:
                logger.info("No pending migrations")
                return True
            
            # Filter by target version
            if target_version:
                pending = [m for m in pending if m.version <= target_version]
            
            logger.info(f"Found {len(pending)} pending migrations")
            
            # Apply migrations
            applied_count = 0
            for migration in pending:
                if self.apply_migration(migration):
                    applied_count += 1
                else:
                    logger.error(f"Failed to apply migration {migration.version}")
                    return False
            
            logger.info(f"Successfully applied {applied_count} migrations")
            return True
        
        except Exception as e:
            logger.error(f"Error running migrations: {e}")
            return False
    
    def rollback_migrations(self, target_version: Optional[str] = None) -> bool:
        """Rollback migrations to target version"""
        
        try:
            logger.info("Starting rollback process")
            
            # Load applied migrations
            self.load_applied_migrations()
            
            # Get migrations to rollback (in reverse order)
            to_rollback = sorted(
                self.applied_migrations.values(),
                key=lambda m: m.version,
                reverse=True
            )
            
            # Filter by target version
            if target_version:
                to_rollback = [m for m in to_rollback if m.version > target_version]
            
            if not to_rollback:
                logger.info("No migrations to rollback")
                return True
            
            logger.info(f"Rolling back {len(to_rollback)} migrations")
            
            # Rollback migrations
            rolled_back_count = 0
            for migration in to_rollback:
                if self.rollback_migration(migration):
                    rolled_back_count += 1
                else:
                    logger.error(f"Failed to rollback migration {migration.version}")
                    return False
            
            logger.info(f"Successfully rolled back {rolled_back_count} migrations")
            return True
        
        except Exception as e:
            logger.error(f"Error rolling back migrations: {e}")
            return False
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status"""
        
        try:
            self.load_migrations()
            self.load_applied_migrations()
            
            pending = self.get_pending_migrations()
            
            return {
                "total_migrations": len(self.migrations),
                "applied_migrations": len(self.applied_migrations),
                "pending_migrations": len(pending),
                "last_migration": self.get_last_migration(),
                "migrations": [
                    {
                        "version": m.version,
                        "name": m.name,
                        "applied": m.version in self.applied_migrations,
                        "applied_at": m.applied_at.isoformat() if m.applied_at else None
                    }
                    for m in self.migrations
                ]
            }
        
        except Exception as e:
            logger.error(f"Error getting migration status: {e}")
            return {"error": str(e)}
    
    def get_last_migration(self) -> Optional[Dict[str, Any]]:
        """Get last applied migration"""
        
        if not self.applied_migrations:
            return None
        
        last_version = max(self.applied_migrations.keys())
        last_migration = self.applied_migrations[last_version]
        
        return {
            "version": last_migration.version,
            "name": last_migration.name,
            "applied_at": last_migration.applied_at.isoformat() if last_migration.applied_at else None
        }
    
    def seed_sample_data(self) -> bool:
        """Seed sample data for development"""
        
        try:
            logger.info("Seeding sample data")
            
            conn = self.connection_pool.getconn()
            cursor = conn.cursor()
            
            # Check if data already exists
            cursor.execute("SELECT COUNT(*) FROM google_drive_workflow_templates")
            count = cursor.fetchone()[0]
            
            if count > 0:
                logger.info("Sample data already exists")
                return True
            
            # Sample workflow templates
            sample_templates = [
                ('Email Notifications', 'Send email notifications for file changes', 'Notifications',
                 '[{"type": "file_created", "config": {}}]',
                 '[{"type": "send_email", "config": {"to": "{{user_email}}", "subject": "File: {{trigger_data.file_name}}", "body": "A new file has been uploaded: {{trigger_data.file_name}}"}}]',
                 '📧', '{backup, email, notifications}', True),
                
                ('File Cleanup', 'Automatically cleanup old files', 'Maintenance',
                 '[{"type": "scheduled", "config": {"cron": "0 2 * * 0"}}]',
                 '[{"type": "condition_check", "config": {"conditions": [{"field": "trigger_data.age_days", "operator": "greater_than", "value": 30}]}}, {"type": "delete_file", "config": {"file_id": "{{trigger_data.file_id}}"}}]',
                 '🗑️', '{cleanup, maintenance, automation}', True)
            ]
            
            for template in sample_templates:
                cursor.execute("""
                    INSERT INTO google_drive_workflow_templates 
                    (name, description, category, triggers, actions, icon, tags, public)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, template)
            
            # Sample search analytics
            sample_analytics = [
                ('user123', datetime.now().date(), 10, 8, 25.5, 1.2, '{"quarterly report": 3, "meeting notes": 2, "presentation": 1}', '{"semantic": 6, "text": 4}'),
                ('user456', datetime.now().date(), 15, 12, 32.1, 1.5, '{"invoice": 5, "contract": 3, "proposal": 2}', '{"semantic": 10, "text": 5}'),
            ]
            
            for analytics in sample_analytics:
                cursor.execute("""
                    INSERT INTO google_drive_search_analytics 
                    (user_id, date, total_searches, unique_queries, average_results, average_execution_time, popular_queries, search_types)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, analytics)
            
            conn.commit()
            logger.info("Sample data seeded successfully")
            return True
        
        except Exception as e:
            logger.error(f"Error seeding sample data: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def close(self) -> None:
        """Close connection pool"""
        
        try:
            if self.connection_pool:
                self.connection_pool.closeall()
                logger.info("Connection pool closed")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")

def main():
    """Main migration runner"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="ATOMIC Google Drive Migration Runner")
    parser.add_argument("action", choices=["up", "down", "status", "seed", "reset"])
    parser.add_argument("--version", help="Target migration version")
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL"), help="Database URL")
    parser.add_argument("--migrations-dir", default="migrations", help="Migrations directory")
    
    args = parser.parse_args()
    
    if not args.db_url:
        logger.error("Database URL is required (set DATABASE_URL or use --db-url)")
        sys.exit(1)
    
    # Create migration runner
    runner = MigrationRunner(args.db_url, args.migrations_dir)
    
    try:
        if args.action == "up":
            success = runner.run_migrations(args.version)
            if success:
                logger.info("Migrations completed successfully")
            else:
                logger.error("Migrations failed")
                sys.exit(1)
        
        elif args.action == "down":
            success = runner.rollback_migrations(args.version)
            if success:
                logger.info("Rollback completed successfully")
            else:
                logger.error("Rollback failed")
                sys.exit(1)
        
        elif args.action == "status":
            status = runner.get_migration_status()
            print(json.dumps(status, indent=2, default=str))
        
        elif args.action == "seed":
            success = runner.seed_sample_data()
            if success:
                logger.info("Sample data seeded successfully")
            else:
                logger.error("Sample data seeding failed")
                sys.exit(1)
        
        elif args.action == "reset":
            logger.warning("Resetting database - this will drop all data")
            runner.rollback_migrations()
            runner.run_migrations()
            runner.seed_sample_data()
            logger.info("Database reset completed")
    
    finally:
        runner.close()

if __name__ == "__main__":
    import json
    main()