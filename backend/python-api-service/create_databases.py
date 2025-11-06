#!/usr/bin/env python3
"""
Database Creation Script
Create SQLite databases for testing and development
"""

import os
import sys
import sqlite3
from datetime import datetime
from typing import Dict, Any

class DatabaseCreator:
    """Create and initialize SQLite databases for testing"""

    def __init__(self):
        self.db_dir = os.path.dirname(os.path.abspath(__file__))
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "databases_created": [],
            "tables_created": {},
            "errors": [],
        }

    def create_main_database(self):
        """Create main ATOM database"""
        db_path = os.path.join(self.db_dir, "atom.db")
        
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Create users table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create integrations table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS integrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT,
                        service_name TEXT,
                        status TEXT DEFAULT 'inactive',
                        access_token TEXT,
                        refresh_token TEXT,
                        token_expires TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                ''')
                
                # Create workflows table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS workflows (
                        id TEXT PRIMARY KEY,
                        user_id TEXT,
                        name TEXT,
                        description TEXT,
                        config TEXT,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                ''')
                
                conn.commit()
                self.results["databases_created"].append("atom.db")
                self.results["tables_created"]["atom.db"] = ["users", "integrations", "workflows"]
                print("✅ Created main database: atom.db")
                
        except Exception as e:
            error = f"Failed to create atom.db: {str(e)}"
            self.results["errors"].append(error)
            print(f"❌ {error}")

    def create_integrations_database(self):
        """Create integrations database for OAuth tokens"""
        db_path = os.path.join(self.db_dir, "integrations.db")
        
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Create OAuth tokens table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS oauth_tokens (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        service_name TEXT NOT NULL,
                        access_token TEXT,
                        refresh_token TEXT,
                        token_type TEXT,
                        expires_at TIMESTAMP,
                        scope TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, service_name)
                    )
                ''')
                
                # Create service configurations table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS service_configs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        service_name TEXT UNIQUE NOT NULL,
                        client_id TEXT,
                        client_secret TEXT,
                        redirect_uri TEXT,
                        scopes TEXT,
                        webhook_url TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Insert default service configurations
                services = [
                    ('google', os.getenv('GOOGLE_CLIENT_ID', ''), 'calendar,drive,gmail'),
                    ('slack', os.getenv('SLACK_CLIENT_ID', ''), 'channels:read,chat:read,users:read'),
                    ('asana', os.getenv('ASANA_CLIENT_ID', ''), 'tasks:read,tasks:write,projects:read'),
                    ('notion', os.getenv('NOTION_CLIENT_ID', ''), ''),
                    ('teams', os.getenv('MICROSOFT_CLIENT_ID', ''), 'User.Read,Chat.Read,Team.ReadBasic.All'),
                ]
                
                for service in services:
                    cursor.execute('''
                        INSERT OR IGNORE INTO service_configs 
                        (service_name, client_id, scopes) VALUES (?, ?, ?)
                    ''', service)
                
                conn.commit()
                self.results["databases_created"].append("integrations.db")
                self.results["tables_created"]["integrations.db"] = ["oauth_tokens", "service_configs"]
                print("✅ Created integrations database: integrations.db")
                
        except Exception as e:
            error = f"Failed to create integrations.db: {str(e)}"
            self.results["errors"].append(error)
            print(f"❌ {error}")

    def create_test_data(self):
        """Create test data for development"""
        try:
            # Add test user to atom.db
            atom_db_path = os.path.join(self.db_dir, "atom.db")
            with sqlite3.connect(atom_db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR IGNORE INTO users (id, email, name) VALUES 
                    ('test_user_google', 'test_user_google@gmail.com', 'Test Google User'),
                    ('test_user_asana', 'test_user_asana@asana.com', 'Test Asana User'),
                    ('test_user_slack', 'test_user_slack@slack.com', 'Test Slack User'),
                    ('test_user_notion', 'test_user_notion@notion.com', 'Test Notion User'),
                    ('test_user_teams', 'test_user_teams@teams.com', 'Test Teams User')
                ''')
                
                # Add sample integrations
                cursor.execute('''
                    INSERT OR IGNORE INTO integrations 
                    (user_id, service_name, status) VALUES 
                    ('test_user_google', 'google', 'active'),
                    ('test_user_asana', 'asana', 'active'),
                    ('test_user_slack', 'slack', 'active'),
                    ('test_user_notion', 'notion', 'active'),
                    ('test_user_teams', 'teams', 'active')
                ''')
                
                conn.commit()
                print("✅ Created test data")
                
        except Exception as e:
            error = f"Failed to create test data: {str(e)}"
            self.results["errors"].append(error)
            print(f"❌ {error}")

    def verify_databases(self):
        """Verify databases are accessible and have tables"""
        verification_results = {}
        
        db_files = ['atom.db', 'integrations.db']
        for db_file in db_files:
            db_path = os.path.join(self.db_dir, db_file)
            if os.path.exists(db_path):
                try:
                    with sqlite3.connect(db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                        tables = [row[0] for row in cursor.fetchall()]
                        verification_results[db_file] = {
                            "accessible": True,
                            "tables": tables,
                            "size": os.path.getsize(db_path)
                        }
                        print(f"✅ {db_file}: {len(tables)} tables, {os.path.getsize(db_path)} bytes")
                except Exception as e:
                    verification_results[db_file] = {"accessible": False, "error": str(e)}
                    print(f"❌ {db_file}: {str(e)}")
            else:
                verification_results[db_file] = {"accessible": False, "error": "File not found"}
                print(f"❌ {db_file}: File not found")
        
        self.results["verification"] = verification_results

    def create_all_databases(self):
        """Create all databases and test data"""
        print("🚀 Starting Database Creation")
        print("=" * 40)
        
        self.create_main_database()
        self.create_integrations_database()
        self.create_test_data()
        self.verify_databases()
        
        print("\n" + "=" * 40)
        print("📊 Database Creation Summary")
        print(f"Databases Created: {len(self.results['databases_created'])}")
        print(f"Errors: {len(self.results['errors'])}")
        
        if self.results['errors']:
            print("\n❌ Errors:")
            for error in self.results['errors']:
                print(f"   - {error}")
        
        # Save results
        results_file = os.path.join(self.db_dir, "database_creation_results.json")
        import json
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n📄 Results saved to: database_creation_results.json")
        
        return self.results


def main():
    """Main execution function"""
    creator = DatabaseCreator()
    results = creator.create_all_databases()
    
    if not results['errors']:
        print("\n🎉 Database Creation: SUCCESS - Ready for development!")
    else:
        print("\n⚠️ Database Creation: COMPLETED WITH ERRORS")


if __name__ == "__main__":
    main()