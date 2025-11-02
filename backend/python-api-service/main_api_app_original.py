import os
import logging
from flask import Flask, jsonify
from threading import Thread
import time
from workflow_handler import workflow_bp, create_workflow_tables
from workflow_api import workflow_api_bp
from workflow_agent_api import workflow_agent_api_bp
from workflow_automation_api import workflow_automation_api
from voice_integration_api import voice_integration_api_bp
# from workflow_execution_api import workflow_execution_bp

# Import enhanced service endpoints
try:
    from enhanced_service_endpoints import enhanced_service_bp

    ENHANCED_SERVICES_AVAILABLE = True
except ImportError:
    ENHANCED_SERVICES_AVAILABLE = False
    logging.warning("Enhanced service endpoints not available")


# SMART BLUEPRINT IMPORT WRAPPER - Handle slow imports gracefully
import threading
import signal
import sys


class SmartImportTimeout(Exception):
    pass


def smart_import_with_timeout(module_name, bp_name, timeout=10):
    """Import module with timeout to prevent hanging"""
    import importlib

    def import_target():
        try:
            module = importlib.import_module(module_name, fromlist=[bp_name])
            blueprint = getattr(module, bp_name, None)
            if blueprint:
                print(f"✅ Successfully imported {bp_name} from {module_name}")
                return blueprint
            else:
                print(f"⚠️ Blueprint {bp_name} not found in {module_name}")
                return None
        except ImportError as e:
            print(f"⚠️ Import error for {bp_name} from {module_name}: {e}")
            return None
        except Exception as e:
            print(f"⚠️ Unexpected error importing {bp_name}: {e}")
            return None

    result = [None]
    thread = threading.Thread(target=lambda: result.__setitem__(0, import_target()))
    thread.daemon = True
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        print(f"⚠️ Import timeout for {bp_name} from {module_name} after {timeout}s")
        return result[0]  # Return whatever we got

    return result[0]


def fast_import_module(module_name, bp_name):
    """Quick import for modules that should load immediately"""
    return smart_import_with_timeout(module_name, bp_name, timeout=3)


def slow_import_module(module_name, bp_name):
    """Patient import for modules that may take longer"""
    return smart_import_with_timeout(module_name, bp_name, timeout=15)


# Enable debug logging for blueprint registration
import logging

logging.getLogger().setLevel(logging.DEBUG)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    import os

    # Load from project root .env file
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    env_path = os.path.join(project_root, ".env")

    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger = logging.getLogger(__name__)
        logger.info(f"Loaded environment variables from .env file at {env_path}")
    else:
        logger = logging.getLogger(__name__)
        logger.warning(
            f".env file not found at {env_path}, using system environment variables"
        )
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("python-dotenv not available, using system environment variables")

# Import OAuth configuration for development
try:
    from oauth_config import setup_oauth_environment, get_oauth_config

    OAUTH_CONFIG_AVAILABLE = True
except ImportError:
    OAUTH_CONFIG_AVAILABLE = False
    logging.warning("OAuth configuration module not available")


# SAFE IMPORT WRAPPER - Handle problematic imports gracefully
def safe_import_module(module_name, bp_name, fallback_msg=None):
    try:
        module = __import__(module_name, fromlist=[bp_name])
        blueprint = getattr(module, bp_name, None)
        print(f"✅ Successfully imported {bp_name} from {module_name}")
        return blueprint
    except ImportError as e:
        print(f"⚠️ Could not import {bp_name} from {module_name}: {e}")
        if fallback_msg:
            print(f"   {fallback_msg}")
        return None
    except Exception as e:
        print(f"⚠️ Error importing {bp_name} from {module_name}: {e}")
        if fallback_msg:
            print(f"   {fallback_msg}")
        return None


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import fallback database utilities
try:
    from db_utils_fallback import (
        get_db_connection as get_sqlite_connection,
        health_check_sqlite,
    )

    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False
    logging.warning("SQLite fallback not available")


def create_app():
    """
    Application factory for the main Python API service.
    Uses lazy imports to avoid startup hangs.
    """
    app = Flask(__name__)

    @app.route("/api/routes")
    def list_routes():
        """Debug endpoint to list all registered routes"""
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append(
                {
                    "endpoint": rule.endpoint,
                    "methods": list(rule.methods),
                    "path": str(rule),
                }
            )
        return jsonify({"ok": True, "routes": routes, "total": len(routes)})

    # --- Configuration ---
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_default_dev_secret_key_change_me")
    if app.secret_key == "a_default_dev_secret_key_change_me":
        logger.warning(
            "Using default Flask secret key. This is not secure for production."
        )

    # Configure OAuth for development environment
    if OAUTH_CONFIG_AVAILABLE:
        oauth_config = setup_oauth_environment()
        logger.info(f"OAuth environment configured: {oauth_config}")
    else:
        logger.warning("OAuth configuration not available - HTTPS may be required")

    # Initialize blueprints dictionary (will be populated lazily)
    app.blueprints = {}
    app.db_pool = None

    def initialize_database_async():
        """Initialize database connection pool asynchronously"""
        try:
            logger.info("Starting database initialization...")

            # Import database utilities only when needed
            try:
                from db_utils import init_db_pool, get_db_pool
                from init_database import initialize_database

                # Initialize database tables
                if initialize_database():
                    logger.info("Database tables initialized successfully")
                else:
                    logger.warning(
                        "Database table initialization failed. Some features may not work."
                    )

                # Initialize the database connection pool
                db_pool = init_db_pool()
                app.db_pool = db_pool

                if db_pool:
                    logger.info("PostgreSQL connection pool initialized successfully.")
                else:
                    logger.warning(
                        "Database connection pool initialization failed. Some features may not work."
                    )
            except ImportError as e:
                logger.warning(f"Database utilities not available: {e}")
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in database initialization: {e}")

    def register_core_blueprints():
        """Register core blueprints synchronously during app creation"""
        try:
            logger.info("Starting core blueprint registration...")

            # Core blueprints (fast imports)
            core_blueprints = [
                ("search_routes", "search_routes_bp", "search"),
                ("lancedb_search_api", "lancedb_search_api", "lancedb_search"),
                ("calendar_handler", "calendar_bp", "calendar"),
                ("task_handler_sqlite", "task_bp", "tasks"),
                ("message_handler_sqlite", "message_bp", "messages"),
                ("transcription_handler", "transcription_bp", "transcription"),
                ("workflow_api", "workflow_api_bp", "workflow_api"),
                ("workflow_agent_api", "workflow_agent_api_bp", "workflow_agent"),
                (
                    "workflow_automation_api",
                    "workflow_automation_api",
                    "workflow_automation",
                ),
                (
                    "voice_integration_api",
                    "voice_integration_api_bp",
                    "voice_integration",
                ),
                ("dashboard_routes", "dashboard_bp", "dashboard"),
                ("service_registry_routes", "service_registry_bp", "services"),
                ("user_service", "user_bp", "user"),
                ("user_auth_api", "user_auth_bp", "user_auth"),
                ("service_status_handler", "service_status_bp", "service_status"),
                ("ai_settings_handler", "ai_settings_bp", "ai_settings"),
                ("test_workflow_api", "test_workflow_api_bp", "test_workflow"),
                (
                    "context_management_api",
                    "context_management_api_bp",
                    "context_management",
                ),
                (
                    "test_service_availability",
                    "test_service_availability_bp",
                    "test_service_availability",
                ),
                ("user_api_key_routes", "user_api_key_bp", "user_api_keys"),
                # Health endpoint blueprints
                ("gmail_health_handler", "gmail_bp", "gmail_health"),
                ("outlook_health_handler", "outlook_bp", "outlook_health"),
                ("slack_health_handler", "slack_bp", "slack_health"),
                ("teams_health_handler", "teams_bp", "teams_health"),
                ("github_health_handler", "github_bp", "github_health"),
                ("gdrive_health_handler", "gdrive_bp", "gdrive_health"),
            ]

            # Register workflow_agent_api_bp directly (already imported at top level)
            try:
                app.register_blueprint(workflow_agent_api_bp)
                app.blueprints["workflow_agent"] = True
                logger.info("Registered workflow_agent blueprint (direct)")
            except Exception as e:
                logger.warning(
                    f"Failed to register workflow_agent blueprint directly: {e}"
                )

            for module_name, bp_name, service_name in core_blueprints:
                # Skip workflow_agent_api since we already registered it directly
                if module_name == "workflow_agent_api":
                    continue

                try:
                    module = __import__(module_name, fromlist=[bp_name])
                    blueprint = getattr(module, bp_name)
                    app.register_blueprint(blueprint)
                    app.blueprints[service_name] = True
                    logger.info(f"Registered {service_name} blueprint")
                except ImportError as e:
                    logger.warning(f"Failed to import {module_name}: {e}")
                except Exception as e:
                    logger.warning(f"Failed to register {service_name}: {e}")

            logger.info("Completed core blueprint registration")

        except Exception as e:
            logger.error(f"Error in core blueprint registration: {e}")

    def lazy_register_slow_blueprints():  # COMMENTED OUT - Import issues:
        """Register slow blueprints in background thread"""
        try:
            logger.info("Starting slow blueprint registration...")

            # Slow blueprints (register in background)
            slow_blueprints = [
                ("dropbox_handler", "dropbox_bp", "dropbox"),
                ("gdrive_handler", "gdrive_bp", "gdrive"),
                ("trello_handler", "trello_bp", "trello"),
                ("salesforce_handler", "salesforce_bp", "salesforce"),
                ("shopify_handler", "shopify_bp", "shopify"),
                ("xero_handler", "xero_bp", "xero"),
                ("twitter_handler", "twitter_bp", "twitter"),
                ("social_media_handler", "social_media_bp", "social_media"),
                ("sales_manager_handler", "sales_manager_bp", "sales_manager"),
                ("project_manager_handler", "project_manager_bp", "project_manager"),
                (
                    "personal_assistant_handler",
                    "personal_assistant_bp",
                    "personal_assistant",
                ),
                (
                    "financial_analyst_handler",
                    "financial_analyst_bp",
                    "financial_analyst",
                ),
                (
                    "marketing_manager_handler",
                    "marketing_manager_bp",
                    "marketing_manager",
                ),
                ("mailchimp_handler", "mailchimp_bp", "mailchimp"),
                (
                    "customer_support_manager_handler",
                    "customer_support_manager_bp",
                    "customer_support",
                ),
                ("legal_handler", "legal_bp", "legal"),
                ("it_manager_handler", "it_manager_bp", "it_manager"),
                ("devops_manager_handler", "devops_manager_bp", "devops_manager"),
                ("content_marketer_handler", "content_marketer_bp", "content_marketer"),
                ("meeting_prep", "meeting_prep_bp", "meeting_prep"),
                ("mcp_handler", "mcp_bp", "mcp"),
                ("account_handler", "account_bp", "account"),
                ("transaction_handler", "transaction_bp", "transaction"),
                ("investment_handler", "investment_bp", "investment"),
                (
                    "financial_calculation_handler",
                    "financial_calculation_bp",
                    "financial_calculation",
                ),
                ("financial_handler", "financial_bp", "financial"),
                ("budgeting_handler", "budgeting_bp", "budgeting"),
                ("bookkeeping_handler", "bookkeeping_bp", "bookkeeping"),
                ("net_worth_handler", "net_worth_bp", "net_worth"),
                ("invoicing_handler", "invoicing_bp", "invoicing"),
                ("billing_handler", "billing_bp", "billing"),
                ("payroll_handler", "payroll_bp", "payroll"),
                ("manual_account_handler", "manual_account_bp", "manual_account"),
                (
                    "manual_transaction_handler",
                    "manual_transaction_bp",
                    "manual_transaction",
                ),
                ("reporting_handler", "reporting_bp", "reporting"),
                ("box_handler", "box_bp", "box"),
                ("asana_handler", "asana_bp", "asana"),
                ("jira_handler", "jira_bp", "jira"),
                ("auth_handler_box_real", "box_auth_bp", "box_auth"),
                ("auth_handler_asana", "auth_asana_bp", "asana_auth"),
                ("auth_handler_trello", "auth_trello_bp", "trello_auth"),
                ("auth_handler_notion", "auth_notion_bp", "notion_auth"),
                ("auth_handler_zoho", "zoho_auth_bp", "zoho_auth"),
                ("auth_handler_shopify", "shopify_auth_bp", "shopify_auth"),
                ("zoho_handler", "zoho_bp", "zoho"),
                ("notion_handler_real", "notion_bp", "notion"),
                ("github_handler", "github_bp", "github"),
                ("auth_handler_teams", "auth_teams_bp", "teams_auth"),
                ("auth_handler_gmail", "auth_gmail_bp", "gmail_auth"),
                ("auth_handler_outlook", "auth_outlook_bp", "outlook_auth"),
                ("auth_handler_slack", "auth_slack_bp", "slack_auth"),
                ("auth_handler_github", "auth_github_bp", "github_auth"),
                ("auth_handler_dropbox", "auth_dropbox_bp", "dropbox_auth"),
                ("auth_handler_gdrive_fixed", "gdrive_auth_bp", "gdrive_auth"),
                ("slack_handler_simple", "slack_bp", "slack"),
            ]

            for module_name, bp_name, service_name in slow_blueprints:
                try:
                    logger.info(
                        f"🔍 Attempting to import {module_name}.{bp_name} for {service_name}"
                    )

                    # Check if module exists
                    import importlib.util

                    spec = importlib.util.find_spec(module_name)
                    if spec is None:
                        logger.error(
                            f"❌ Module {module_name} not found in Python path"
                        )
                        continue

                    module = __import__(module_name, fromlist=[bp_name])
                    logger.info(f"✅ Successfully imported module {module_name}")

                    # Check if blueprint exists in module
                    if not hasattr(module, bp_name):
                        logger.error(
                            f"❌ Blueprint {bp_name} not found in module {module_name}"
                        )
                        logger.info(
                            f"   Available attributes: {[attr for attr in dir(module) if not attr.startswith('_')]}"
                        )
                        continue

                    blueprint = getattr(module, bp_name)
                    logger.info(
                        f"✅ Successfully got blueprint {bp_name} from {module_name}"
                    )

                    # Register blueprint
                    app.register_blueprint(blueprint)
                    app.blueprints[service_name] = True
                    logger.info(f"✅ Registered {service_name} blueprint")

                    # Verify routes are registered
                    auth_routes = [
                        str(rule)
                        for rule in app.url_map.iter_rules()
                        if "/api/auth/" in str(rule) and bp_name in rule.endpoint
                    ]
                    logger.info(
                        f"📋 {service_name} auth routes registered: {len(auth_routes)}"
                    )
                    for route in auth_routes:
                        logger.info(f"   - {route}")

                except ImportError as e:
                    logger.error(f"❌ Failed to import {module_name}: {e}")
                    import traceback

                    logger.error(f"   Import traceback: {traceback.format_exc()}")
                except Exception as e:
                    logger.error(f"❌ Failed to register {service_name}: {e}")
                    import traceback

                    logger.error(f"   Registration traceback: {traceback.format_exc()}")

            # Goals API
            try:
                from goals_handler import goals_bp

                app.register_blueprint(goals_bp)
                app.blueprints["goals"] = True
                logger.info("Registered goals blueprint")
            except ImportError as e:
                logger.warning(f"Failed to import goals_handler: {e}")

            # Final debug: Check all registered auth routes
            auth_routes = [
                str(rule)
                for rule in app.url_map.iter_rules()
                if "/api/auth/" in str(rule)
            ]
            logger.info(
                f"🎉 Completed slow blueprint registration - Total auth routes: {len(auth_routes)}"
            )

            # Detailed breakdown by service
            service_routes = {}
            for rule in app.url_map.iter_rules():
                if "/api/auth/" in str(rule):
                    service = str(rule).split("/")[
                        3
                    ]  # Extract service name from /api/auth/{service}/
                    if service not in service_routes:
                        service_routes[service] = []
                    service_routes[service].append(str(rule))

            logger.info("📊 Auth routes by service:")
            for service, routes in sorted(service_routes.items()):
                logger.info(f"   🔐 {service}: {len(routes)} routes")
                for route in routes:
                    logger.info(f"      - {route}")

        except Exception as e:
            logger.error(f"Error in slow blueprint registration: {e}")

    # Start database initialization in background thread
    db_thread = Thread(target=initialize_database_async, daemon=True)
    db_thread.start()

    # Register core blueprints synchronously
    register_core_blueprints()

    # Register workflow execution blueprint
    # try:
    #     app.register_blueprint(workflow_execution_bp)
    #     app.blueprints["workflow_execution"] = True
    #     logger.info("Registered workflow execution blueprint")

    # Register enhanced service endpoints
    if ENHANCED_SERVICES_AVAILABLE:
        try:
            app.register_blueprint(enhanced_service_bp)
            app.blueprints["enhanced_services"] = True
            logger.info("✅ Registered enhanced service endpoints blueprint")
        except Exception as e:
            logger.warning(f"Failed to register enhanced service endpoints: {e}")
    # except Exception as e:
    #     logger.error(f"Failed to register workflow execution blueprint: {e}")

    # Register slow blueprints synchronously to ensure all are registered before app starts    # lazy_register_slow_blueprints()  # COMMENTED OUT - Import issues

    # Create workflow tables if they don't exist
    workflow_tables_created = create_workflow_tables()
    if workflow_tables_created:
        logger.info("Workflow tables created successfully")
    else:
        logger.warning("Failed to create workflow tables")

    logger.info(
        f"All blueprint registration completed. Total blueprints: {len([v for v in app.blueprints.values() if v])}"
    )

    # Health check endpoint
    @app.route("/healthz")
    def healthz():
        # Check database connection
        db_status = "initializing"
        if app.db_pool:
            db_status = "healthy"
        elif SQLITE_AVAILABLE:
            sqlite_healthy = health_check_sqlite()
            db_status = "healthy (sqlite)" if sqlite_healthy else "unhealthy"

        # Check LanceDB connection
        lancedb_status = "not_configured"
        try:
            from lancedb_handler import get_lancedb_connection, LANCEDB_AVAILABLE

            if LANCEDB_AVAILABLE:
                lancedb_conn = get_lancedb_connection()
                lancedb_status = "healthy" if lancedb_conn else "unhealthy"
        except ImportError:
            lancedb_status = "not_available"

        blueprint_status = {
            service: "registered" if status else "pending"
            for service, status in app.blueprints.items()
        }

        return jsonify(
            {
                "status": "ok",
                "service": "atom-python-api",
                "database": {
                    "postgresql": db_status,
                    "sqlite_fallback": "available"
                    if SQLITE_AVAILABLE
                    else "not_available",
                    "lancedb": lancedb_status,
                },
                "blueprints": blueprint_status,
                "total_blueprints": len([v for v in app.blueprints.values() if v]),
                "version": "1.0.0",
                "message": "API server is running with lazy imports",
            }
        ), 200

    # Root endpoint
    @app.route("/")
    def root():
        return jsonify(
            {
                "service": "Atom Python API",
                "version": "1.0.0",
                "status": "running",
                "mode": "lazy_imports",
                "database": "available"
                if app.db_pool or SQLITE_AVAILABLE
                else "not_configured",
                "blueprints_loaded": len([v for v in app.blueprints.values() if v]),
                "endpoints": {
                    "dashboard": "/api/dashboard",
                    "calendar": "/api/calendar/events",
                    "tasks": "/api/tasks",
                    "messages": "/api/messages",
                    "integrations": "/api/integrations/status",
                    "health": "/healthz",
                },
            }
        )

    # Add cleanup on app teardown
    @app.teardown_appcontext
    def teardown_db(exception):
        """Clean up database connections when app context is torn down"""
        if exception:
            logger.error(f"App context teardown with exception: {exception}")
        # Connection pool cleanup is handled by db_utils

    logger.info("Flask app created with lazy imports")
    return app


if __name__ == "__main__":
    # This allows running the app directly for development/debugging
    # In production, a WSGI server like Gunicorn would call create_app()
    logger.info("Starting Atom API server with lazy imports...")
    app = create_app()
    port = int(os.environ.get("PYTHON_API_PORT", 5058))
    logger.info(f"Server starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# Add Teams, Gmail, and Outlook auth handlers to the slow_blueprints list
# Find the slow_blueprints list and add these entries:
# ("auth_handler_teams", "auth_teams_bp", "teams_auth"),
# ("auth_handler_gmail", "auth_gmail_bp", "gmail_auth"),
# ("auth_handler_outlook", "auth_outlook_bp", "outlook_auth"),
