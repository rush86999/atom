#!/usr/bin/env python3
"""
Database Initialization Script for ATOM Google Drive Integration
Initializes database with schema, indexes, and sample data
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import config
from extensions import db, redis_client
from loguru import logger

class DatabaseInitializer:
    """Database initialization and management"""
    
    def __init__(self, db_config):
        self.db_config = db_config
        self.connection = None
        
    async def initialize(self):
        """Complete database initialization"""
        
        try:
            logger.info("🚀 Starting database initialization...")
            
            # Step 1: Connect to database
            await self._connect()
            
            # Step 2: Create database if not exists
            await self._create_database()
            
            # Step 3: Create extensions
            await self._create_extensions()
            
            # Step 4: Create schema
            await self._create_schema()
            
            # Step 5: Create indexes
            await self._create_indexes()
            
            # Step 6: Seed initial data
            await self._seed_data()
            
            # Step 7: Verify setup
            await self._verify_setup()
            
            logger.info("✅ Database initialization completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            raise
        
        finally:
            await self._cleanup()
    
    async def _connect(self):
        """Connect to PostgreSQL"""
        
        try:
            import asyncpg
            
            # Parse database URL
            db_url = self.db_config.get('DATABASE_URL')
            if not db_url:
                raise ValueError("DATABASE_URL is required")
            
            # Connect to postgres database initially
            postgres_url = db_url.rsplit('/', 1)[0] + '/postgres'
            self.connection = await asyncpg.connect(postgres_url)
            
            logger.info("✅ Connected to PostgreSQL")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to database: {e}")
            raise
    
    async def _create_database(self):
        """Create database if it doesn't exist"""
        
        try:
            db_name = self.db_config.get('DATABASE_NAME', 'atom')
            
            # Check if database exists
            result = await self.connection.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", db_name
            )
            
            if not result:
                logger.info(f"📝 Creating database: {db_name}")
                await self.connection.execute(f'CREATE DATABASE "{db_name}"')
                logger.info(f"✅ Database {db_name} created")
            else:
                logger.info(f"✅ Database {db_name} already exists")
            
            # Switch to the target database
            await self.connection.close()
            
            db_url = self.db_config.get('DATABASE_URL')
            self.connection = await asyncpg.connect(db_url)
            
        except Exception as e:
            logger.error(f"❌ Failed to create database: {e}")
            raise
    
    async def _create_extensions(self):
        """Create required PostgreSQL extensions"""
        
        try:
            extensions = [
                ('uuid-ossp', 'UUID generation'),
                ('pg_trgm', 'Text search with trigrams'),
                ('unaccent', 'Diacritic removal'),
                ('vector', 'Vector operations (pgvector)')
            ]
            
            for ext_name, description in extensions:
                try:
                    await self.connection.execute(f'CREATE EXTENSION IF NOT EXISTS "{ext_name}"')
                    logger.info(f"✅ Extension {ext_name} created ({description})")
                except Exception as e:
                    if 'already exists' not in str(e):
                        logger.warning(f"⚠️ Could not create extension {ext_name}: {e}")
            
        except Exception as e:
            logger.error(f"❌ Failed to create extensions: {e}")
            raise
    
    async def _create_schema(self):
        """Create database schema"""
        
        try:
            # Read schema file
            schema_file = project_root / "migrations" / "google_drive_schema.sql"
            
            if not schema_file.exists():
                raise FileNotFoundError(f"Schema file not found: {schema_file}")
            
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # Execute schema
            await self.connection.execute(schema_sql)
            
            logger.info("✅ Database schema created")
            
        except Exception as e:
            logger.error(f"❌ Failed to create schema: {e}")
            raise
    
    async def _create_indexes(self):
        """Create additional performance indexes"""
        
        try:
            indexes = [
                # Full-text search indexes
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_google_drive_files_fulltext 
                ON google_drive_files USING GIN(
                    to_tsvector('english', unaccent(name || ' ' || COALESCE(description, ''))
                );
                """,
                
                # Composite indexes for common queries
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_google_drive_files_user_modified
                ON google_drive_files(user_id, modified_time DESC);
                """,
                
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_google_drive_files_user_type
                ON google_drive_files(user_id, mime_type);
                """,
                
                # Vector similarity index (if pgvector is available)
                """
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_google_drive_file_embeddings_vector_cosine
                        ON google_drive_file_embeddings USING ivfflat (embedding_vector vector_cosine_ops) 
                        WITH (lists = 100);
                    END IF;
                END $$;
                """
            ]
            
            for index_sql in indexes:
                try:
                    await self.connection.execute(index_sql)
                    logger.info("✅ Additional index created")
                except Exception as e:
                    if 'already exists' not in str(e) and 'does not exist' not in str(e):
                        logger.warning(f"⚠️ Could not create index: {e}")
            
            # Update table statistics
            await self.connection.execute("ANALYZE;")
            
            logger.info("✅ Performance indexes created")
            
        except Exception as e:
            logger.error(f"❌ Failed to create indexes: {e}")
            raise
    
    async def _seed_data(self):
        """Seed initial data"""
        
        try:
            # Check if data already exists
            existing_data = await self.connection.fetchval(
                "SELECT COUNT(*) FROM google_drive_workflow_templates"
            )
            
            if existing_data > 0:
                logger.info("✅ Sample data already exists")
                return
            
            # Seed workflow templates
            templates = [
                ('File Backup Automation', 'Automatically backup files to a designated folder', 'Backup', 
                 '[{"type": "file_created", "conditions": [{"field": "trigger_data.mime_type", "operator": "contains", "value": "application/pdf"}]}]',
                 '[{"type": "copy_file", "config": {"file_id": "{{trigger_data.file_id}}", "new_name": "{{trigger_data.file_name}}_backup", "parent_ids": ["{{backup_folder_id}}"]}}]',
                 '📁', '{backup, automation, files}', True),
                
                ('Document Processing Pipeline', 'Extract text and metadata from uploaded documents', 'Processing',
                 '[{"type": "file_created", "conditions": [{"field": "trigger_data.mime_type", "operator": "in", "value": ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]}]}]',
                 '[{"type": "extract_text", "config": {"file_id": "{{trigger_data.file_id}}"}}, {"type": "generate_embeddings", "config": {"file_id": "{{trigger_data.file_id}}"}}, {"type": "update_search_index", "config": {"file_id": "{{trigger_data.file_id}}"}}, {"type": "send_notification", "config": {"message": "Document processed: {{trigger_data.file_name}}", "recipients": ["{{user_email}}"]}}]',
                 '📄', '{processing, documents, extraction}', True),
                
                ('Smart File Organization', 'Automatically organize files into appropriate folders', 'Organization',
                 '[{"type": "file_created", "conditions": []}]',
                 '[{"type": "condition_check", "config": {"conditions": [{"field": "trigger_data.mime_type", "operator": "starts_with", "value": "image/"}], "logic": "and"}}, {"type": "move_file", "config": {"file_id": "{{trigger_data.file_id}}", "add_parents": ["{{images_folder_id}}"]}}]',
                 '📂', '{organization, folders, automation}', True),
                
                ('Email Notification System', 'Send email notifications for file changes', 'Communication',
                 '[{"type": "file_shared", "conditions": []}, {"type": "file_updated", "conditions": []}, {"type": "file_created", "conditions": []}]',
                 '[{"type": "send_email", "config": {"to": "{{user_email}}", "subject": "File {{trigger_data.action}}: {{trigger_data.file_name}}", "body": "File {{trigger_data.file_name}} has been {{trigger_data.action}} by {{trigger_data.user}} on {{trigger_data.timestamp}}", "template": "file_notification.html"}}, {"type": "log_activity", "config": {"activity": "{{trigger_data.action}}", "file_id": "{{trigger_data.file_id}}", "user_id": "{{trigger_data.user_id}}"}}}]',
                 '📧', '{email, notifications, communication}', True),
                
                ('Content Analysis Workflow', 'Analyze content and extract insights', 'Analytics',
                 '[{"type": "file_created", "conditions": [{"field": "trigger_data.mime_type", "operator": "in", "value": ["application/pdf", "text/plain", "application/msword"]}]}]',
                 '[{"type": "extract_text", "config": {"file_id": "{{trigger_data.file_id}}"}}, {"type": "analyze_content", "config": {"file_id": "{{trigger_data.file_id}}", "analysis_types": ["sentiment", "entities", "keywords"]}}, {"type": "generate_summary", "config": {"file_id": "{{trigger_data.file_id}}"}}, {"type": "store_insights", "config": {"file_id": "{{trigger_data.file_id}}", "insights": "{{analysis_results}}"}}}, {"type": "update_dashboard", "config": {"file_id": "{{trigger_data.file_id}}", "insights": "{{analysis_results}}"}}}]',
                 '📊', '{analytics, content, insights}', True)
            ]
            
            for template in templates:
                await self.connection.execute("""
                    INSERT INTO google_drive_workflow_templates 
                    (name, description, category, triggers, actions, icon, tags, public)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT DO NOTHING
                """, template)
            
            logger.info("✅ Sample workflow templates seeded")
            
        except Exception as e:
            logger.error(f"❌ Failed to seed data: {e}")
            raise
    
    async def _verify_setup(self):
        """Verify database setup"""
        
        try:
            # Check table counts
            tables = await self.connection.fetch("""
                SELECT table_name, 
                       (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
                FROM information_schema.tables t 
                WHERE table_schema = 'public' 
                AND table_name LIKE 'google_drive_%'
                ORDER BY table_name
            """)
            
            logger.info(f"📊 Created {len(tables)} Google Drive tables:")
            for table in tables:
                logger.info(f"   - {table['table_name']} ({table['column_count']} columns)")
            
            # Check template data
            template_count = await self.connection.fetchval(
                "SELECT COUNT(*) FROM google_drive_workflow_templates"
            )
            logger.info(f"📝 Seeded {template_count} workflow templates")
            
            # Check extensions
            extensions = await self.connection.fetch("""
                SELECT extname FROM pg_extension 
                WHERE extname IN ('uuid-ossp', 'pg_trgm', 'unaccent', 'vector')
                ORDER BY extname
            """)
            
            logger.info(f"🔧 Installed extensions: {[ext['extname'] for ext in extensions]}")
            
            # Test basic operations
            test_uuid = await self.connection.fetchval("SELECT uuid_generate_v4()")
            test_vector = None
            
            try:
                test_vector = await self.connection.fetchval("SELECT '[1,2,3]'::vector")
            except:
                pass
            
            logger.info(f"✅ Database verification passed")
            logger.info(f"   - UUID generation: {'✅' if test_uuid else '❌'}")
            logger.info(f"   - Vector support: {'✅' if test_vector else '❌'}")
            
        except Exception as e:
            logger.error(f"❌ Database verification failed: {e}")
            raise
    
    async def _cleanup(self):
        """Cleanup connections"""
        
        try:
            if self.connection:
                await self.connection.close()
                logger.info("✅ Database connection closed")
        except Exception as e:
            logger.error(f"❌ Error closing connection: {e}")

class RedisInitializer:
    """Redis initialization and management"""
    
    def __init__(self, redis_config):
        self.redis_config = redis_config
        self.redis_client = None
    
    async def initialize(self):
        """Initialize Redis"""
        
        try:
            logger.info("🔴 Starting Redis initialization...")
            
            # Connect to Redis
            import redis.asyncio as redis
            redis_url = self.redis_config.get('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            
            # Test connection
            await self.redis_client.ping()
            logger.info("✅ Connected to Redis")
            
            # Flush if needed (for fresh start)
            # await self.redis_client.flushdb()
            
            # Set initial keys
            await self._setup_keys()
            
            logger.info("✅ Redis initialization completed!")
            
        except Exception as e:
            logger.error(f"❌ Redis initialization failed: {e}")
            raise
        
        finally:
            await self._cleanup()
    
    async def _setup_keys(self):
        """Setup initial Redis keys"""
        
        try:
            # Service status keys
            await self.redis_client.set(
                "atom:google_drive:status", 
                "initializing", 
                ex=3600  # 1 hour TTL
            )
            
            # Configuration keys
            config_data = {
                "search_enabled": True,
                "sync_enabled": True,
                "automation_enabled": True,
                "max_file_size": 100 * 1024 * 1024,  # 100MB
                "supported_formats": ["pdf", "doc", "docx", "txt", "jpg", "png"]
            }
            
            await self.redis_client.hset(
                "atom:google_drive:config",
                mapping=config_data
            )
            
            # Queue initialization
            await self.redis_client.delete("atom:google_drive:sync_queue")
            await self.redis_client.delete("atom:google_drive:processing_queue")
            await self.redis_client.delete("atom:google_drive:automation_queue")
            
            logger.info("✅ Redis keys initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup Redis keys: {e}")
            raise
    
    async def _cleanup(self):
        """Cleanup Redis connection"""
        
        try:
            if self.redis_client:
                await self.redis_client.close()
                logger.info("✅ Redis connection closed")
        except Exception as e:
            logger.error(f"❌ Error closing Redis connection: {e}")

async def main():
    """Main initialization function"""
    
    try:
        # Get configuration
        env = os.getenv('FLASK_ENV', 'development')
        app_config = config.get(env, config['default'])
        
        logger.info(f"🚀 Initializing ATOM Google Drive Integration")
        logger.info(f"📋 Environment: {env}")
        logger.info(f"⏰ Started at: {datetime.now().isoformat()}")
        
        # Initialize database
        db_initializer = DatabaseInitializer(app_config)
        await db_initializer.initialize()
        
        # Initialize Redis
        redis_initializer = RedisInitializer(app_config)
        await redis_initializer.initialize()
        
        # Update status
        if redis_initializer.redis_client:
            await redis_initializer.redis_client.set(
                "atom:google_drive:status", 
                "ready", 
                ex=3600
            )
        
        logger.info("🎉 ATOM Google Drive Integration initialized successfully!")
        logger.info("📚 Next steps:")
        logger.info("   1. Configure Google Drive API credentials")
        logger.info("   2. Run: python app.py")
        logger.info("   3. Visit: http://localhost:8000")
        logger.info("   4. Connect your Google Drive account")
        logger.info("   5. Start using the integration!")
        
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())