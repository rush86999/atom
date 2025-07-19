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
from .meeting_prep import meeting_prep_bp
from .mcp_handler import mcp_bp

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
    app.register_blueprint(mcp_bp)
    logger.info("Registered 'mcp_bp' blueprint.")

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
