import os
import logging
from flask import Flask, jsonify
from threading import Thread
import time
from workflow_handler import workflow_bp, create_workflow_tables
from workflow_api import workflow_api_bp
from workflow_agent_api import workflow_agent_api_bp

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

    # --- Configuration ---
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_default_dev_secret_key_change_me")
    if app.secret_key == "a_default_dev_secret_key_change_me":
        logger.warning(
            "Using default Flask secret key. This is not secure for production."
        )

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

    def lazy_register_blueprints():
        """Register blueprints lazily to avoid import hangs"""
        try:
            logger.info("Starting lazy blueprint registration...")

            # Core blueprints (fast imports)
            core_blueprints = [
                ("search_routes", "search_routes_bp", "search"),
                ("calendar_handler", "calendar_bp", "calendar"),
                ("task_handler", "task_bp", "tasks"),
                ("message_handler", "message_bp", "messages"),
                ("transcription_handler", "transcription_bp", "transcription"),
                ("workflow_api", "workflow_api_bp", "workflows"),
                ("workflow_agent_api", "workflow_agent_api_bp", "workflow_agent"),
                ("dashboard_routes", "dashboard_bp", "dashboard"),
                ("service_registry_routes", "service_registry_bp", "services"),
            ]

            for module_name, bp_name, service_name in core_blueprints:
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

            # Slow blueprints (register in background)
            slow_blueprints = [
                ("auth_handler_dropbox", "dropbox_auth_bp", "dropbox_auth"),
                ("dropbox_handler", "dropbox_bp", "dropbox"),
                ("auth_handler_gdrive", "gdrive_auth_bp", "gdrive_auth"),
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
                ("auth_handler_asana", "asana_auth_bp", "asana_auth"),
                ("auth_handler_trello", "trello_auth_bp", "trello_auth"),
                ("auth_handler_notion", "notion_auth_bp", "notion_auth"),
                ("auth_handler_zoho", "zoho_auth_bp", "zoho_auth"),
                ("auth_handler_shopify", "shopify_auth_bp", "shopify_auth"),
                ("zoho_handler", "zoho_bp", "zoho"),
                ("notion_handler_real", "notion_bp", "notion"),
                ("github_handler", "github_bp", "github"),
            ]

            for module_name, bp_name, service_name in slow_blueprints:
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

            # Goals API
            try:
                from goals_handler import goals_bp

                app.register_blueprint(goals_bp)
                app.blueprints["goals"] = True
                logger.info("Registered goals blueprint")
            except ImportError as e:
                logger.warning(f"Failed to import goals_handler: {e}")

            logger.info("Completed lazy blueprint registration")

        except Exception as e:
            logger.error(f"Error in lazy blueprint registration: {e}")

    # Start database initialization in background thread
    db_thread = Thread(target=initialize_database_async, daemon=True)
    db_thread.start()

    # Start blueprint registration in background thread
    blueprint_thread = Thread(target=lazy_register_blueprints, daemon=True)
    blueprint_thread.start()

    # Create workflow tables if they don't exist
    workflow_tables_created = create_workflow_tables()
    if workflow_tables_created:
        logger.info("Workflow tables created successfully")
    else:
        logger.warning("Failed to create workflow tables")

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
