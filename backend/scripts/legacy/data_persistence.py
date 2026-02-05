from datetime import datetime
import json
import logging
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataPersistence:
    """Data persistence layer for ATOM platform backend"""

    def __init__(self, db_path: str = "atom_data.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_database()

    def _init_database(self):
        """Initialize database with required tables"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                # Service Registry table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS services (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        status TEXT NOT NULL,
                        configuration TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # AI Providers table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_providers (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        provider_type TEXT NOT NULL,
                        api_key TEXT,
                        base_url TEXT,
                        configuration TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Workflow Templates table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS workflow_templates (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        template_data TEXT NOT NULL,
                        category TEXT,
                        version TEXT DEFAULT '1.0.0',
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Workflow Executions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS workflow_executions (
                        id TEXT PRIMARY KEY,
                        template_id TEXT,
                        input_data TEXT,
                        output_data TEXT,
                        status TEXT NOT NULL,
                        error_message TEXT,
                        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        execution_time_ms INTEGER,
                        FOREIGN KEY (template_id) REFERENCES workflow_templates (id)
                    )
                """)

                # OAuth Tokens table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS oauth_tokens (
                        service_id TEXT PRIMARY KEY,
                        access_token TEXT NOT NULL,
                        refresh_token TEXT,
                        token_type TEXT,
                        expires_at TIMESTAMP,
                        scope TEXT,
                        user_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # System Settings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        description TEXT,
                        category TEXT DEFAULT 'general',
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Audit Log table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        action TEXT NOT NULL,
                        resource_type TEXT NOT NULL,
                        resource_id TEXT,
                        user_id TEXT,
                        details TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.commit()
                logger.info("Database initialized successfully")

            except Exception as e:
                logger.error(f"Error initializing database: {e}")
                raise
            finally:
                conn.close()

    # Service Registry Operations
    def save_service(self, service_data: Dict[str, Any]) -> bool:
        """Save or update a service in the registry"""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO services
                    (id, name, category, status, configuration, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        service_data["id"],
                        service_data["name"],
                        service_data.get("category", "general"),
                        service_data.get("status", "active"),
                        json.dumps(service_data.get("configuration", {})),
                        datetime.now().isoformat(),
                    ),
                )

                conn.commit()
                self._log_audit("save_service", "service", service_data["id"])
                return True

        except Exception as e:
            logger.error(f"Error saving service {service_data.get('id')}: {e}")
            return False
        finally:
            conn.close()

    def get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get a service by ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM services WHERE id = ?", (service_id,))
            row = cursor.fetchone()

            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "category": row[2],
                    "status": row[3],
                    "configuration": json.loads(row[4]) if row[4] else {},
                    "created_at": row[5],
                    "updated_at": row[6],
                }
            return None

        except Exception as e:
            logger.error(f"Error getting service {service_id}: {e}")
            return None
        finally:
            conn.close()

    def get_all_services(self) -> List[Dict[str, Any]]:
        """Get all registered services"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM services ORDER BY name")
            rows = cursor.fetchall()

            services = []
            for row in rows:
                services.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "category": row[2],
                        "status": row[3],
                        "configuration": json.loads(row[4]) if row[4] else {},
                        "created_at": row[5],
                        "updated_at": row[6],
                    }
                )

            return services

        except Exception as e:
            logger.error(f"Error getting all services: {e}")
            return []
        finally:
            conn.close()

    def delete_service(self, service_id: str) -> bool:
        """Delete a service from the registry"""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute("DELETE FROM services WHERE id = ?", (service_id,))
                conn.commit()

                self._log_audit("delete_service", "service", service_id)
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error deleting service {service_id}: {e}")
            return False
        finally:
            conn.close()

    # AI Provider Operations
    def save_ai_provider(self, provider_data: Dict[str, Any]) -> bool:
        """Save or update an AI provider configuration"""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO ai_providers
                    (id, name, provider_type, api_key, base_url, configuration, is_active, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        provider_data["id"],
                        provider_data["name"],
                        provider_data["provider_type"],
                        provider_data.get("api_key"),
                        provider_data.get("base_url"),
                        json.dumps(provider_data.get("configuration", {})),
                        provider_data.get("is_active", True),
                        datetime.now().isoformat(),
                    ),
                )

                conn.commit()
                self._log_audit("save_ai_provider", "ai_provider", provider_data["id"])
                return True

        except Exception as e:
            logger.error(f"Error saving AI provider {provider_data.get('id')}: {e}")
            return False
        finally:
            conn.close()

    def get_ai_provider(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get an AI provider by ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM ai_providers WHERE id = ?", (provider_id,))
            row = cursor.fetchone()

            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "provider_type": row[2],
                    "api_key": row[3],
                    "base_url": row[4],
                    "configuration": json.loads(row[5]) if row[5] else {},
                    "is_active": bool(row[6]),
                    "created_at": row[7],
                    "updated_at": row[8],
                }
            return None

        except Exception as e:
            logger.error(f"Error getting AI provider {provider_id}: {e}")
            return None
        finally:
            conn.close()

    def get_all_ai_providers(self) -> List[Dict[str, Any]]:
        """Get all AI providers"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM ai_providers ORDER BY name")
            rows = cursor.fetchall()

            providers = []
            for row in rows:
                providers.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "provider_type": row[2],
                        "api_key": row[3],
                        "base_url": row[4],
                        "configuration": json.loads(row[5]) if row[5] else {},
                        "is_active": bool(row[6]),
                        "created_at": row[7],
                        "updated_at": row[8],
                    }
                )

            return providers

        except Exception as e:
            logger.error(f"Error getting all AI providers: {e}")
            return []
        finally:
            conn.close()

    # Workflow Operations
    def save_workflow_template(self, template_data: Dict[str, Any]) -> bool:
        """Save or update a workflow template"""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO workflow_templates
                    (id, name, description, template_data, category, version, is_active, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        template_data["id"],
                        template_data["name"],
                        template_data.get("description", ""),
                        json.dumps(template_data["template_data"]),
                        template_data.get("category", "general"),
                        template_data.get("version", "1.0.0"),
                        template_data.get("is_active", True),
                        datetime.now().isoformat(),
                    ),
                )

                conn.commit()
                self._log_audit(
                    "save_workflow_template", "workflow_template", template_data["id"]
                )
                return True

        except Exception as e:
            logger.error(
                f"Error saving workflow template {template_data.get('id')}: {e}"
            )
            return False
        finally:
            conn.close()

    def get_workflow_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get a workflow template by ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM workflow_templates WHERE id = ?", (template_id,)
            )
            row = cursor.fetchone()

            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "template_data": json.loads(row[3]),
                    "category": row[4],
                    "version": row[5],
                    "is_active": bool(row[6]),
                    "created_at": row[7],
                    "updated_at": row[8],
                }
            return None

        except Exception as e:
            logger.error(f"Error getting workflow template {template_id}: {e}")
            return None
        finally:
            conn.close()

    def get_all_workflow_templates(self) -> List[Dict[str, Any]]:
        """Get all workflow templates"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM workflow_templates WHERE is_active = 1 ORDER BY name"
            )
            rows = cursor.fetchall()

            templates = []
            for row in rows:
                templates.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "description": row[2],
                        "template_data": json.loads(row[3]),
                        "category": row[4],
                        "version": row[5],
                        "is_active": bool(row[6]),
                        "created_at": row[7],
                        "updated_at": row[8],
                    }
                )

            return templates

        except Exception as e:
            logger.error(f"Error getting all workflow templates: {e}")
            return []
        finally:
            conn.close()

    def save_workflow_execution(self, execution_data: Dict[str, Any]) -> bool:
        """Save workflow execution data"""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO workflow_executions
                    (id, template_id, input_data, output_data, status, error_message,
                     started_at, completed_at, execution_time_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        execution_data["id"],
                        execution_data.get("template_id"),
                        json.dumps(execution_data.get("input_data", {})),
                        json.dumps(execution_data.get("output_data", {})),
                        execution_data["status"],
                        execution_data.get("error_message"),
                        execution_data.get("started_at", datetime.now().isoformat()),
                        execution_data.get("completed_at"),
                        execution_data.get("execution_time_ms"),
                    ),
                )

                conn.commit()
                return True

        except Exception as e:
            logger.error(
                f"Error saving workflow execution {execution_data.get('id')}: {e}"
            )
            return False
        finally:
            conn.close()

    # OAuth Token Operations
    def save_oauth_token(self, token_data: Dict[str, Any]) -> bool:
        """Save or update OAuth token for a service"""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO oauth_tokens
                    (service_id, access_token, refresh_token, token_type, expires_at, scope, user_id, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        token_data["service_id"],
                        token_data["access_token"],
                        token_data.get("refresh_token"),
                        token_data.get("token_type", "Bearer"),
                        token_data.get("expires_at"),
                        token_data.get("scope"),
                        token_data.get("user_id", "default"),
                        datetime.now().isoformat(),
                    ),
                )

                conn.commit()
                self._log_audit(
                    "save_oauth_token", "oauth_token", token_data["service_id"]
                )
                return True

        except Exception as e:
            logger.error(
                f"Error saving OAuth token for service {token_data.get('service_id')}: {e}"
            )
            return False
        finally:
            conn.close()

    def get_oauth_token(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get OAuth token for a service"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM oauth_tokens WHERE service_id = ?", (service_id,)
            )
            row = cursor.fetchone()

            if row:
                return {
                    "service_id": row[0],
                    "access_token": row[1],
                    "refresh_token": row[2],
                    "token_type": row[3],
                    "expires_at": row[4],
                    "scope": row[5],
                    "user_id": row[6],
                    "created_at": row[7],
                    "updated_at": row[8],
                }
            return None

        except Exception as e:
            logger.error(f"Error getting OAuth token for service {service_id}: {e}")
            return None
        finally:
            conn.close()

    # System Settings Operations
    def save_setting(
        self, key: str, value: Any, description: str = "", category: str = "general"
    ) -> bool:
        """Save or update a system setting"""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO system_settings
                    (key, value, description, category, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        key,
                        json.dumps(value),
                        description,
                        category,
                        datetime.now().isoformat(),
                    ),
                )

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error saving setting {key}: {e}")
            return False
        finally:
            conn.close()

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a system setting"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
            row = cursor.fetchone()

            if row:
                return json.loads(row[0])
            return default

        except Exception as e:
            logger.error(f"Error getting setting {key}: {e}")
            return default
        finally:
            conn.close()

    # Audit Logging
    def _log_audit(
        self,
        action: str,
        resource_type: str,
        resource_id: str = None,
        user_id: str = "system",
        details: str = None,
        ip_address: str = None,
        user_agent: str = None,
    ):
        """Log an audit event"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO audit_log
                (action, resource_type, resource_id, user_id, details, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    action,
                    resource_type,
                    resource_id,
                    user_id,
                    details,
                    ip_address,
                    user_agent,
                ),
            )

            conn.commit()

        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
        finally:
            conn.close()

    def get_audit_log(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get audit log entries"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM audit_log
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """,
                (limit, offset),
            )

            rows = cursor.fetchall()

            logs = []
            for row in rows:
                logs.append(
                    {
                        "id": row[0],
                        "action": row[1],
                        "resource_type": row[2],
                        "resource_id": row[3],
                        "user_id": row[4],
                        "details": row[5],
                        "ip_address": row[6],
                        "user_agent": row[7],
                        "created_at": row[8],
                    }
                )

            return logs

        except Exception as e:
            logger.error(f"Error getting audit log: {e}")
            return []
        finally:
            conn.close()

    # Utility Methods
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            stats = {}

            # Get table counts
            tables = [
                "services",
                "ai_providers",
                "workflow_templates",
                "workflow_executions",
                "oauth_tokens",
                "system_settings",
                "audit_log",
            ]

            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                stats[f"{table}_count"] = count

            # Get database size
            cursor.execute("""
                SELECT page_count * page_size as size_bytes
                FROM pragma_page_count(), pragma_page_size()
            """)
            size_bytes = cursor.fetchone()[0]
            stats["database_size_bytes"] = size_bytes
            stats["database_size_mb"] = round(size_bytes / (1024 * 1024), 2)

            # Get recent activity
            cursor.execute("""
                SELECT COUNT(*) FROM audit_log
                WHERE created_at >= datetime('now', '-1 hour')
            """)
            stats["recent_activity_count"] = cursor.fetchone()[0]

            return stats

        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
        finally:
            conn.close()

    def backup_database(self, backup_path: str) -> bool:
        """Create a backup of the database"""
        try:
            import shutil

            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Database backup created: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Error creating database backup: {e}")
            return False

    def cleanup_old_data(self, days_old: int = 30) -> int:
        """Clean up old data from audit log and workflow executions"""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                # Delete old audit log entries
                cursor.execute(
                    """
                    DELETE FROM audit_log
                    WHERE created_at < datetime('now', ?)
                """,
                    (f"-{days_old} days",),
                )

                audit_deleted = cursor.rowcount

                # Delete old workflow executions
                cursor.execute(
                    """
                    DELETE FROM workflow_executions
                    WHERE started_at < datetime('now', ?)
                """,
                    (f"-{days_old} days",),
                )

                workflow_deleted = cursor.rowcount

                conn.commit()
                total_deleted = audit_deleted + workflow_deleted

                logger.info(f"Cleaned up {total_deleted} old records")
                return total_deleted

        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            return 0
        finally:
            conn.close()

    def export_data(self, table_name: str) -> List[Dict[str, Any]]:
        """Export all data from a specific table"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()

            # Get column names
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]

            data = []
            for row in rows:
                row_data = {}
                for i, col in enumerate(columns):
                    # Handle JSON fields
                    if col in [
                        "configuration",
                        "template_data",
                        "input_data",
                        "output_data",
                        "value",
                    ]:
                        try:
                            row_data[col] = json.loads(row[i]) if row[i] else {}
                        except:
                            row_data[col] = row[i]
                    else:
                        row_data[col] = row[i]
                data.append(row_data)

            return data

        except Exception as e:
            logger.error(f"Error exporting data from {table_name}: {e}")
            return []
        finally:
            conn.close()

    def import_data(self, table_name: str, data: List[Dict[str, Any]]) -> bool:
        """Import data into a specific table"""
        try:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                for item in data:
                    # Convert dictionary to tuple for insertion
                    placeholders = ", ".join(["?" for _ in item])
                    columns = ", ".join(item.keys())
                    values = list(item.values())

                    # Handle JSON serialization for specific fields
                    for key, value in item.items():
                        if key in [
                            "configuration",
                            "template_data",
                            "input_data",
                            "output_data",
                            "value",
                        ]:
                            if isinstance(value, (dict, list)):
                                values[list(item.keys()).index(key)] = json.dumps(value)

                    cursor.execute(
                        f"""
                        INSERT OR REPLACE INTO {table_name} ({columns})
                        VALUES ({placeholders})
                    """,
                        values,
                    )

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error importing data to {table_name}: {e}")
            return False
        finally:
            conn.close()


# Global instance for easy access
data_persistence = DataPersistence()
