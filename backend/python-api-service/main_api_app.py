import os
import logging
from flask import Flask
from psycopg2 import pool
from db_utils import init_db_pool, close_db_pool, get_db_pool
from init_database import initialize_database
from lancedb_handler import get_lancedb_connection, LANCEDB_AVAILABLE

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

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import Blueprints from all the handlers
# Note: The handlers themselves will need to be slightly modified to not create their own app = Flask(__name__)
# if it's at the global scope, but instead define their routes on a Blueprint.
# Let's assume for now they are already using Blueprints correctly.

# from document_handler import document_bp # Example
from search_routes import search_routes_bp  # Example
from auth_handler_dropbox import dropbox_auth_bp
from dropbox_handler import dropbox_bp
from auth_handler_gdrive import gdrive_auth_bp
from gdrive_handler import gdrive_bp
from trello_handler import trello_bp
from salesforce_handler import salesforce_bp
from xero_handler import xero_bp
from shopify_handler import shopify_bp
from twitter_handler import twitter_bp
from social_media_handler import social_media_bp
from sales_manager_handler import sales_manager_bp
from project_manager_handler import project_manager_bp
from personal_assistant_handler import personal_assistant_bp
from financial_analyst_handler import financial_analyst_bp
from marketing_manager_handler import marketing_manager_bp
from mailchimp_handler import mailchimp_bp
from customer_support_manager_handler import customer_support_manager_bp
from legal_handler import legal_bp
from it_manager_handler import it_manager_bp
from devops_manager_handler import devops_manager_bp
from content_marketer_handler import content_marketer_bp
from meeting_prep import meeting_prep_bp
from mcp_handler import mcp_bp
from account_handler import account_bp
from transaction_handler import transaction_bp
from investment_handler import investment_bp
from financial_calculation_handler import financial_calculation_bp
from financial_handler import financial_bp
from budgeting_handler import budgeting_bp
from bookkeeping_handler import bookkeeping_bp
from net_worth_handler import net_worth_bp
from invoicing_handler import invoicing_bp
from billing_handler import billing_bp
from payroll_handler import payroll_bp
from manual_account_handler import manual_account_bp
from manual_transaction_handler import manual_transaction_bp
from reporting_handler import reporting_bp
from box_handler import box_bp
from asana_handler import asana_bp
from jira_handler import jira_bp
from auth_handler_box_real import box_auth_bp
from auth_handler_asana import asana_auth_bp
from auth_handler_trello import trello_auth_bp
from auth_handler_notion import notion_auth_bp
from auth_handler_zoho import zoho_auth_bp
from auth_handler_shopify import shopify_auth_bp
from zoho_handler import zoho_bp
from notion_handler_real import notion_bp
from calendar_handler import calendar_bp
from task_handler import task_bp
from message_handler import message_bp
from transcription_handler import transcription_bp


def create_app(db_pool=None):
    """
    Application factory for the main Python API service.
    """
    app = Flask(__name__)

    # --- Configuration ---
    # It's crucial for session management that a secret key is set.
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_default_dev_secret_key_change_me")
    if app.secret_key == "a_default_dev_secret_key_change_me":
        logger.warning(
            "Using default Flask secret key. This is not secure for production."
        )

    # --- Database Connection Pool ---
    if db_pool:
        app.config["DB_CONNECTION_POOL"] = db_pool
    else:
        try:
            logger.info("Initializing database...")
            # Initialize database tables
            if initialize_database():
                logger.info("Database tables initialized successfully")
            else:
                logger.warning(
                    "Database table initialization failed. Some features may not work."
                )

            logger.info("Initializing PostgreSQL connection pool...")
            # Initialize the database connection pool
            db_pool = init_db_pool()
            app.config["DB_CONNECTION_POOL"] = db_pool

            if db_pool:
                logger.info("PostgreSQL connection pool initialized successfully.")
            else:
                logger.warning(
                    "Database connection pool initialization failed. Some features may not work."
                )
                app.config["DB_CONNECTION_POOL"] = None
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
            # Depending on strictness, we could exit or continue with the pool as None.
            app.config["DB_CONNECTION_POOL"] = None

    # --- Register Blueprints ---
    # A real implementation would refactor other handlers to use blueprints and register them here.
    # For now, I will just register the new Dropbox auth blueprint.

    app.register_blueprint(dropbox_auth_bp)
    logger.info("Registered 'dropbox_auth_bp' blueprint.")
    app.register_blueprint(dropbox_bp)
    logger.info("Registered 'dropbox_bp' blueprint.")
    app.register_blueprint(gdrive_auth_bp)
    logger.info("Registered 'gdrive_auth_bp' blueprint.")
    app.register_blueprint(gdrive_bp)
    logger.info("Registered 'gdrive_bp' blueprint.")
    app.register_blueprint(trello_bp)
    logger.info("Registered 'trello_bp' blueprint.")
    app.register_blueprint(salesforce_bp)
    logger.info("Registered 'salesforce_bp' blueprint.")
    app.register_blueprint(shopify_bp)
    logger.info("Registered 'shopify_bp' blueprint.")
    app.register_blueprint(xero_bp)
    logger.info("Registered 'xero_bp' blueprint.")
    app.register_blueprint(twitter_bp)
    logger.info("Registered 'twitter_bp' blueprint.")
    app.register_blueprint(social_media_bp)
    logger.info("Registered 'social_media_bp' blueprint.")
    app.register_blueprint(sales_manager_bp)
    logger.info("Registered 'sales_manager_bp' blueprint.")
    app.register_blueprint(project_manager_bp)
    logger.info("Registered 'project_manager_bp' blueprint.")
    app.register_blueprint(personal_assistant_bp)
    logger.info("Registered 'personal_assistant_bp' blueprint.")
    app.register_blueprint(marketing_manager_bp)
    logger.info("Registered 'marketing_manager_bp' blueprint.")
    app.register_blueprint(mailchimp_bp)
    logger.info("Registered 'mailchimp_bp' blueprint.")
    app.register_blueprint(customer_support_manager_bp)
    logger.info("Registered 'customer_support_manager_bp' blueprint.")
    app.register_blueprint(legal_bp)
    logger.info("Registered 'legal_bp' blueprint.")
    app.register_blueprint(it_manager_bp)
    logger.info("Registered 'it_manager_bp' blueprint.")
    app.register_blueprint(devops_manager_bp)
    logger.info("Registered 'devops_manager_bp' blueprint.")
    app.register_blueprint(content_marketer_bp)
    logger.info("Registered 'content_marketer_bp' blueprint.")
    app.register_blueprint(mcp_bp)
    logger.info("Registered 'mcp_bp' blueprint.")
    app.register_blueprint(account_bp)
    logger.info("Registered 'account_bp' blueprint.")

    # Goals API
    from goals_handler import goals_bp

    app.register_blueprint(goals_bp)
    logger.info("Registered 'goals_bp' blueprint.")

    app.register_blueprint(transaction_bp)
    logger.info("Registered 'transaction_bp' blueprint.")
    app.register_blueprint(investment_bp)
    logger.info("Registered 'investment_bp' blueprint.")
    app.register_blueprint(financial_calculation_bp)
    logger.info("Registered 'financial_calculation_bp' blueprint.")
    app.register_blueprint(financial_bp)
    logger.info("Registered 'financial_bp' blueprint.")
    app.register_blueprint(budgeting_bp)
    logger.info("Registered 'budgeting_bp' blueprint.")
    app.register_blueprint(bookkeeping_bp)
    logger.info("Registered 'bookkeeping_bp' blueprint.")
    app.register_blueprint(net_worth_bp)
    logger.info("Registered 'net_worth_bp' blueprint.")
    app.register_blueprint(invoicing_bp)
    logger.info("Registered 'invoicing_bp' blueprint.")
    app.register_blueprint(billing_bp)
    logger.info("Registered 'billing_bp' blueprint.")
    app.register_blueprint(payroll_bp)
    logger.info("Registered 'payroll_bp' blueprint.")
    app.register_blueprint(manual_account_bp)
    logger.info("Registered 'manual_account_bp' blueprint.")
    app.register_blueprint(manual_transaction_bp)
    logger.info("Registered 'manual_transaction_bp' blueprint.")
    app.register_blueprint(reporting_bp)
    logger.info("Registered 'reporting_bp' blueprint.")
    app.register_blueprint(box_bp)
    logger.info("Registered 'box_bp' blueprint (real implementation).")
    app.register_blueprint(asana_bp)
    logger.info("Registered 'asana_bp' blueprint (real implementation).")
    app.register_blueprint(jira_bp)
    app.register_blueprint(notion_bp)
    logger.info("Registered 'notion_bp' blueprint (real implementation).")
    logger.info("Registered 'jira_bp' blueprint (real implementation).")
    app.register_blueprint(box_auth_bp)
    logger.info("Registered 'box_auth_bp' blueprint (real implementation).")
    app.register_blueprint(asana_auth_bp)
    logger.info("Registered 'asana_auth_bp' blueprint.")
    app.register_blueprint(trello_auth_bp)
    app.register_blueprint(notion_auth_bp)
    logger.info("Registered 'notion_auth_bp' blueprint.")
    logger.info("Registered 'trello_auth_bp' blueprint.")
    app.register_blueprint(zoho_auth_bp)
    logger.info("Registered 'zoho_auth_bp' blueprint.")
    app.register_blueprint(shopify_auth_bp)
    logger.info("Registered 'shopify_auth_bp' blueprint.")
    app.register_blueprint(zoho_bp)
    logger.info("Registered 'zoho_bp' blueprint.")

    # Register calendar blueprint
    app.register_blueprint(calendar_bp)
    logger.info("Registered 'calendar_bp' blueprint.")

    # Register task blueprint
    app.register_blueprint(task_bp)
    logger.info("Registered 'task_bp' blueprint.")

    # Register message blueprint
    app.register_blueprint(message_bp)
    logger.info("Registered 'message_bp' blueprint.")

    # Register transcription blueprint
    app.register_blueprint(transcription_bp)
    logger.info("Registered 'transcription_bp' blueprint.")

    from github_handler import github_bp

    app.register_blueprint(github_bp)
    logger.info("Registered 'github_bp' blueprint.")

    # Example of registering other blueprints:
    # app.register_blueprint(document_bp)
    app.register_blueprint(search_routes_bp)

    @app.route("/healthz")
    def healthz():
        # Check PostgreSQL database connection
        db_pool = get_db_pool()
        db_status = "healthy" if db_pool else "unhealthy"

        # If PostgreSQL is unavailable, try SQLite fallback
        sqlite_status = "not_configured"
        if db_status == "unhealthy" and SQLITE_AVAILABLE:
            sqlite_healthy = health_check_sqlite()
            sqlite_status = "healthy" if sqlite_healthy else "unhealthy"
            if sqlite_healthy:
                db_status = "healthy (sqlite fallback)"

        # Check LanceDB connection
        lancedb_status = "unavailable"
        if LANCEDB_AVAILABLE:
            try:
                lancedb_conn = get_lancedb_connection()
                lancedb_status = "healthy" if lancedb_conn else "unhealthy"
            except Exception as e:
                logger.error(f"LanceDB health check failed: {e}")
                lancedb_status = "error"
        else:
            lancedb_status = "not_configured"

        return {
            "status": "ok",
            "database": {
                "postgresql": db_status,
                "sqlite_fallback": sqlite_status,
                "lancedb": lancedb_status,
            },
            "version": "1.0.0",
        }, 200

    # Add cleanup on app teardown
    @app.teardown_appcontext
    def teardown_db(exception):
        """Clean up database connections when app context is torn down"""
        if exception:
            logger.error(f"App context teardown with exception: {exception}")
        # Connection pool cleanup is handled by db_utils

    logger.info("Flask app created and configured.")
    return app


if __name__ == "__main__":
    # This allows running the app directly for development/debugging
    # In production, a WSGI server like Gunicorn would call create_app()
    app = create_app()
    port = int(
        os.environ.get("PYTHON_API_PORT", 5058)
    )  # Using a new port for the combined service
    app.run(host="0.0.0.0", port=port, debug=True)
