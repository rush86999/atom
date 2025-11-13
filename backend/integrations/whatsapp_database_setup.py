"""
WhatsApp Database Setup
Automated database initialization for WhatsApp Business integration
"""

import psycopg2
import psycopg2.extras
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class WhatsAppDatabaseManager:
    """Database manager for WhatsApp Business integration"""
    
    def __init__(self):
        self.config = {
            'host': os.getenv('DATABASE_HOST', 'localhost'),
            'database': os.getenv('DATABASE_NAME', 'atom_development'),
            'user': os.getenv('DATABASE_USER', 'postgres'),
            'password': os.getenv('DATABASE_PASSWORD', ''),
            'port': os.getenv('DATABASE_PORT', '5432'),
        }
        self.connection = None
    
    def test_connection(self) -> dict:
        """Test database connection"""
        try:
            connection = psycopg2.connect(
                host=self.config['host'],
                user=self.config['user'],
                password=self.config['password'],
                port=self.config['port'],
                connect_timeout=5
            )
            
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            connection.close()
            
            return {
                'success': True,
                'message': 'Database connection successful',
                'config': {
                    'host': self.config['host'],
                    'database': self.config['database'],
                    'port': self.config['port'],
                    'user': self.config['user']
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'config': {
                    'host': self.config['host'],
                    'database': self.config['database'],
                    'port': self.config['port'],
                    'user': self.config['user']
                }
            }
    
    def create_database(self) -> dict:
        """Create database if it doesn't exist"""
        try:
            # Connect to default database to create target database
            connection = psycopg2.connect(
                host=self.config['host'],
                user=self.config['user'],
                password=self.config['password'],
                port=self.config['port'],
                database='postgres'
            )
            connection.autocommit = True
            
            with connection.cursor() as cursor:
                # Check if database exists
                cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (self.config['database'],))
                exists = cursor.fetchone()
                
                if not exists:
                    cursor.execute(f"CREATE DATABASE {self.config['database']}")
                    created = True
                    message = f"Database '{self.config['database']}' created successfully"
                else:
                    created = False
                    message = f"Database '{self.config['database']}' already exists"
            
            connection.close()
            
            return {
                'success': True,
                'created': created,
                'message': message,
                'database': self.config['database']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'database': self.config['database']
            }
    
    def initialize_tables(self) -> dict:
        """Initialize all WhatsApp tables"""
        try:
            # Connect to target database
            self.connection = psycopg2.connect(**self.config)
            self.connection.autocommit = True
            
            with self.connection.cursor() as cursor:
                # Create contacts table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS whatsapp_contacts (
                        id SERIAL PRIMARY KEY,
                        whatsapp_id VARCHAR(50) UNIQUE NOT NULL,
                        name VARCHAR(255),
                        phone_number VARCHAR(20),
                        profile_picture_url TEXT,
                        about TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create messages table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS whatsapp_messages (
                        id SERIAL PRIMARY KEY,
                        message_id VARCHAR(100) UNIQUE NOT NULL,
                        whatsapp_id VARCHAR(50) NOT NULL,
                        message_type VARCHAR(20) NOT NULL,
                        content JSONB NOT NULL,
                        direction VARCHAR(10) NOT NULL,
                        status VARCHAR(20) DEFAULT 'sent',
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (whatsapp_id) REFERENCES whatsapp_contacts(whatsapp_id)
                    )
                ''')
                
                # Create templates table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS whatsapp_templates (
                        id SERIAL PRIMARY KEY,
                        template_name VARCHAR(100) NOT NULL,
                        category VARCHAR(50) NOT NULL,
                        language_code VARCHAR(10) NOT NULL,
                        components JSONB NOT NULL,
                        status VARCHAR(20) DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(template_name, language_code)
                    )
                ''')
                
                # Create conversations table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS whatsapp_conversations (
                        id SERIAL PRIMARY KEY,
                        conversation_id VARCHAR(100) UNIQUE NOT NULL,
                        whatsapp_id VARCHAR(50) NOT NULL,
                        status VARCHAR(20) DEFAULT 'active',
                        last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (whatsapp_id) REFERENCES whatsapp_contacts(whatsapp_id)
                    )
                ''')
                
                # Create indexes for performance
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_whatsapp_id ON whatsapp_messages(whatsapp_id)",
                    "CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_timestamp ON whatsapp_messages(timestamp)",
                    "CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_direction ON whatsapp_messages(direction)",
                    "CREATE INDEX IF NOT EXISTS idx_whatsapp_conversations_whatsapp_id ON whatsapp_conversations(whatsapp_id)",
                    "CREATE INDEX IF NOT EXISTS idx_whatsapp_conversations_status ON whatsapp_conversations(status)",
                    "CREATE INDEX IF NOT EXISTS idx_whatsapp_conversations_last_message_at ON whatsapp_conversations(last_message_at)",
                    "CREATE INDEX IF NOT EXISTS idx_whatsapp_contacts_whatsapp_id ON whatsapp_contacts(whatsapp_id)",
                    "CREATE INDEX IF NOT EXISTS idx_whatsapp_contacts_phone_number ON whatsapp_contacts(phone_number)"
                ]
                
                for index_sql in indexes:
                    cursor.execute(index_sql)
                
                # Insert demo data
                self._insert_demo_data(cursor)
            
            self.connection.close()
            
            return {
                'success': True,
                'message': 'Database tables initialized successfully',
                'tables': [
                    'whatsapp_contacts',
                    'whatsapp_messages',
                    'whatsapp_templates',
                    'whatsapp_conversations'
                ],
                'indexes_created': len(indexes)
            }
            
        except Exception as e:
            if self.connection:
                self.connection.close()
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to initialize database tables'
            }
    
    def _insert_demo_data(self, cursor):
        """Insert demo data for testing"""
        try:
            # Insert demo contacts
            demo_contacts = [
                ('+1234567890', 'John Doe', '+1234567890', 'Test user 1'),
                ('+9876543210', 'Jane Smith', '+9876543210', 'Test user 2'),
                ('+5555555555', 'Test User', '+5555555555', 'Demo contact')
            ]
            
            cursor.executemany('''
                INSERT INTO whatsapp_contacts (whatsapp_id, name, phone_number, about)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (whatsapp_id) DO NOTHING
            ''', demo_contacts)
            
            # Insert demo conversations
            cursor.executemany('''
                INSERT INTO whatsapp_conversations (conversation_id, whatsapp_id, status)
                VALUES (%s, %s, 'active')
                ON CONFLICT (conversation_id) DO NOTHING
            ''', [
                (f'conv_{i}_{datetime.now().strftime("%Y%m%d")}', contact[0])
                for i, contact in enumerate(demo_contacts, 1)
            ])
            
            # Insert demo messages
            demo_messages = [
                ('msg_demo_1', '+1234567890', 'text', '{"body": "Hello! This is a demo message"}', 'inbound', 'received'),
                ('msg_demo_2', '+1234567890', 'text', '{"body": "Demo response from ATOM"}', 'outbound', 'sent'),
                ('msg_demo_3', '+9876543210', 'text', '{"body": "Welcome to ATOM WhatsApp integration!"}', 'outbound', 'sent'),
            ]
            
            cursor.executemany('''
                INSERT INTO whatsapp_messages (message_id, whatsapp_id, message_type, content, direction, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (message_id) DO NOTHING
            ''', demo_messages)
            
            # Insert demo templates
            demo_templates = [
                ('welcome_message', 'UTILITY', 'en', '[{"type": "body", "text": "Welcome to {{1}}!"}]'),
                ('appointment_reminder', 'UTILITY', 'en', '[{"type": "body", "text": "Your appointment is scheduled for {{1}}."}]'),
                ('follow_up', 'MARKETING', 'en', '[{"type": "body", "text": "Hi {{1}}, just checking in about {{2}}."}]')
            ]
            
            cursor.executemany('''
                INSERT INTO whatsapp_templates (template_name, category, language_code, components)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (template_name, language_code) DO NOTHING
            ''', demo_templates)
            
            logger.info("Demo data inserted successfully")
            
        except Exception as e:
            logger.error(f"Error inserting demo data: {str(e)}")
    
    def get_status(self) -> dict:
        """Get database status and statistics"""
        try:
            connection = psycopg2.connect(**self.config)
            
            with connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Get table statistics
                cursor.execute('''
                    SELECT 
                        schemaname,
                        tablename,
                        attname,
                        n_distinct,
                        correlation
                    FROM pg_stats
                    WHERE schemaname = 'public' 
                    AND tablename LIKE 'whatsapp_%'
                ''')
                table_stats = cursor.fetchall()
                
                # Get row counts
                cursor.execute('''
                    SELECT 
                        'whatsapp_contacts' as table_name, COUNT(*) as row_count
                    FROM whatsapp_contacts
                    UNION ALL
                    SELECT 
                        'whatsapp_messages' as table_name, COUNT(*) as row_count
                    FROM whatsapp_messages
                    UNION ALL
                    SELECT 
                        'whatsapp_templates' as table_name, COUNT(*) as row_count
                    FROM whatsapp_templates
                    UNION ALL
                    SELECT 
                        'whatsapp_conversations' as table_name, COUNT(*) as row_count
                    FROM whatsapp_conversations
                ''')
                row_counts = cursor.fetchall()
            
            connection.close()
            
            return {
                'success': True,
                'database': self.config['database'],
                'table_statistics': [dict(row) for row in table_stats],
                'row_counts': [dict(row) for row in row_counts],
                'total_tables': len(row_counts)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'database': self.config['database']
            }

def setup_database() -> dict:
    """Complete database setup process"""
    db_manager = WhatsAppDatabaseManager()
    
    result = {
        'setup_complete': False,
        'steps_completed': [],
        'errors': [],
        'final_status': 'failed'
    }
    
    try:
        # Step 1: Test connection
        print("🔗 Step 1: Testing database connection...")
        connection_result = db_manager.test_connection()
        
        if connection_result['success']:
            result['steps_completed'].append('connection_test_passed')
            print("✅ Database connection successful")
        else:
            result['errors'].append(f"Connection test failed: {connection_result['error']}")
            return result
        
        # Step 2: Create database
        print("📊 Step 2: Creating database...")
        database_result = db_manager.create_database()
        
        if database_result['success']:
            result['steps_completed'].append('database_created')
            created_msg = "created" if database_result['created'] else "already exists"
            print(f"✅ Database {database_result['database']} {created_msg}")
        else:
            result['errors'].append(f"Database creation failed: {database_result['error']}")
            return result
        
        # Step 3: Initialize tables
        print("📋 Step 3: Initializing tables...")
        tables_result = db_manager.initialize_tables()
        
        if tables_result['success']:
            result['steps_completed'].append('tables_initialized')
            print(f"✅ Tables initialized: {', '.join(tables_result['tables'])}")
            print(f"✅ Indexes created: {tables_result['indexes_created']}")
        else:
            result['errors'].append(f"Table initialization failed: {tables_result['error']}")
            return result
        
        # Step 4: Get status
        print("📊 Step 4: Getting database status...")
        status_result = db_manager.get_status()
        
        if status_result['success']:
            result['steps_completed'].append('status_verified')
            result['database_status'] = status_result
            print(f"✅ Database status verified")
            print(f"📊 Total tables: {status_result['total_tables']}")
            
            for table_info in status_result['row_counts']:
                print(f"   - {table_info['table_name']}: {table_info['row_count']} rows")
        
        result['setup_complete'] = True
        result['final_status'] = 'success'
        
        print("🎉 WhatsApp database setup completed successfully!")
        
    except Exception as e:
        result['errors'].append(f"Setup process error: {str(e)}")
        print(f"❌ Database setup failed: {str(e)}")
    
    return result

if __name__ == '__main__':
    import json
    
    result = setup_database()
    
    print("\n" + "="*50)
    print("📋 WHATSAPP DATABASE SETUP RESULTS")
    print("="*50)
    print(f"🎯 Final Status: {result['final_status'].upper()}")
    print(f"✅ Setup Complete: {result['setup_complete']}")
    
    if result['setup_complete']:
        print(f"\n📊 Steps Completed: {len(result['steps_completed'])}")
        for i, step in enumerate(result['steps_completed'], 1):
            print(f"  {i}. {step.replace('_', ' ').title()}")
    
    if result['errors']:
        print(f"\n❌ Errors Encountered: {len(result['errors'])}")
        for i, error in enumerate(result['errors'], 1):
            print(f"  {i}. {error}")
    
    if 'database_status' in result:
        status = result['database_status']
        print(f"\n📊 Database Statistics:")
        print(f"  - Database: {status['database']}")
        print(f"  - Total Tables: {status['total_tables']}")
        for count_info in status['row_counts']:
            print(f"  - {count_info['table_name']}: {count_info['row_count']} rows")
    
    # Save result
    with open('/tmp/whatsapp_database_setup.json', 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"\n📁 Setup result saved to: /tmp/whatsapp_database_setup.json")