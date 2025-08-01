import os
import logging
from flask import Flask
from psycopg2 import pool

# Import Blueprints from all the handlers
# Note: The handlers themselves will need to be slightly modified to not create their own app = Flask(__name__)
# if it's at the global scope, but instead define their routes on a Blueprint.
# Let's assume for now they are already using Blueprints correctly.

# from .document_handler import document_bp # Example
# from .search_routes import search_routes_bp # Example
from .auth_handler_dropbox import dropbox_auth_bp
from .dropbox_handler import dropbox_bp
from .auth_handler_gdrive import gdrive_auth_bp
from .gdrive_handler import gdrive_bp
from .trello_handler import trello_bp
from .salesforce_handler import salesforce_bp
from .xero_handler import xero_bp
from .shopify_handler import shopify_bp
from .twitter_handler import twitter_bp
from .social_media_handler import social_media_bp
from .sales_manager_handler import sales_manager_bp
from .project_manager_handler import project_manager_bp
from .personal_assistant_handler import personal_assistant_bp
from .financial_analyst_handler import financial_analyst_bp
from .marketing_manager_handler import marketing_manager_bp
from .customer_support_manager_handler import customer_support_manager_bp
from .recruiting_manager_handler import recruiting_manager_bp
from .legal_handler import legal_bp
from .it_manager_handler import it_manager_bp
from .devops_manager_handler import devops_manager_bp
from .hr_manager_handler import hr_manager_bp
from .content_marketer_handler import content_marketer_bp
from .meeting_prep import meeting_prep_bp
from .mcp_handler import mcp_bp
from .account_handler import account_bp
from .transaction_handler import transaction_bp
from .investment_handler import investment_bp
from .financial_calculation_handler import financial_calculation_bp
from .financial_handler import financial_bp
from .budgeting_handler import budgeting_bp
from .bookkeeping_handler import bookkeeping_bp
from .net_worth_handler import net_worth_bp
from .invoicing_handler import invoicing_bp
from .billing_handler import billing_bp
from .payroll_handler import payroll_bp
from .manual_account_handler import manual_account_bp
from .manual_transaction_handler import manual_transaction_bp
from .reporting_handler import reporting_bp
from .box_handler import box_bp
from .asana_handler import asana_bp
from .jira_handler import jira_bp
from .auth_handler_box import box_auth_bp
from .auth_handler_asana import asana_auth_bp
from .auth_handler_trello import trello_auth_bp
from .auth_handler_zoho import zoho_auth_bp
from .zoho_handler import zoho_bp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_app(db_pool=None):
    """
    Application factory for the main Python API service.
    """
    app = Flask(__name__)

    # --- Configuration ---
    # It's crucial for session management that a secret key is set.
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_default_dev_secret_key_change_me")
    if app.secret_key == "a_default_dev_secret_key_change_me":
        logger.warning("Using default Flask secret key. This is not secure for production.")

    # --- Database Connection Pool ---
    if db_pool:
        app.config['DB_CONNECTION_POOL'] = db_pool
    else:
        try:
            logger.info("Initializing PostgreSQL connection pool...")
            app.config['DB_CONNECTION_POOL'] = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=os.getenv("DATABASE_URL") # Assumes DATABASE_URL is in the format: postgresql://user:password@host:port/dbname
            )
            logger.info("PostgreSQL connection pool initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize database connection pool: {e}", exc_info=True)
            # Depending on strictness, we could exit or continue with the pool as None.
            app.config['DB_CONNECTION_POOL'] = None


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
    app.register_blueprint(customer_support_manager_bp)
    logger.info("Registered 'customer_support_manager_bp' blueprint.")
    app.register_blueprint(recruiting_manager_bp)
    logger.info("Registered 'recruiting_manager_bp' blueprint.")
    app.register_blueprint(legal_bp)
    logger.info("Registered 'legal_bp' blueprint.")
    app.register_blueprint(it_manager_bp)
    logger.info("Registered 'it_manager_bp' blueprint.")
    app.register_blueprint(devops_manager_bp)
    logger.info("Registered 'devops_manager_bp' blueprint.")
    app.register_blueprint(hr_manager_bp)
    logger.info("Registered 'hr_manager_bp' blueprint.")
    app.register_blueprint(content_marketer_bp)
    logger.info("Registered 'content_marketer_bp' blueprint.")
    app.register_blueprint(mcp_bp)
    logger.info("Registered 'mcp_bp' blueprint.")
    app.register_blueprint(account_bp)
    logger.info("Registered 'account_bp' blueprint.")
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
    logger.info("Registered 'box_bp' blueprint.")
    app.register_blueprint(asana_bp)
    logger.info("Registered 'asana_bp' blueprint.")
    app.register_blueprint(jira_bp)
    logger.info("Registered 'jira_bp' blueprint.")
    app.register_blueprint(box_auth_bp)
    logger.info("Registered 'box_auth_bp' blueprint.")
    app.register_blueprint(asana_auth_bp)
    logger.info("Registered 'asana_auth_bp' blueprint.")
    app.register_blueprint(trello_auth_bp)
    logger.info("Registered 'trello_auth_bp' blueprint.")
    app.register_blueprint(zoho_auth_bp)
    logger.info("Registered 'zoho_auth_bp' blueprint.")
    app.register_blueprint(zoho_bp)
    logger.info("Registered 'zoho_bp' blueprint.")

    from .github_handler import github_bp
    app.register_blueprint(github_bp)
    logger.info("Registered 'github_bp' blueprint.")

    # Example of registering other blueprints:
    # app.register_blueprint(document_bp)
    # app.register_blueprint(search_routes_bp)

    @app.route('/healthz')
    def healthz():
        return "OK", 200

    logger.info("Flask app created and configured.")
    return app

if __name__ == '__main__':
    # This allows running the app directly for development/debugging
    # In production, a WSGI server like Gunicorn would call create_app()
    app = create_app()
    port = int(os.environ.get("PYTHON_API_PORT", 5058)) # Using a new port for the combined service
    app.run(host='0.0.0.0', port=port, debug=True)
