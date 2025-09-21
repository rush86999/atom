from flask import Flask, jsonify
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_minimal_app():
    """Create a minimal Flask app for testing basic functionality"""
    app = Flask(__name__)

    # Basic configuration
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-for-testing")

    @app.route('/healthz')
    def healthz():
        """Basic health check endpoint"""
        return jsonify({
            "status": "ok",
            "service": "atom-minimal-test",
            "version": "1.0.0",
            "database": "not_configured"
        }), 200

    @app.route('/api/test')
    def test_endpoint():
        """Test endpoint to verify basic functionality"""
        return jsonify({
            "message": "Minimal test app is working!",
            "endpoints": {
                "health": "/healthz",
                "test": "/api/test"
            }
        })

    @app.route('/api/integrations/validate', methods=['POST'])
    def validate_api_keys():
        """Test API key validation endpoint"""
        # Simulate API key validation
        return jsonify({
            "success": True,
            "validation_results": {
                "openai_api_key": {
                    "valid": True,
                    "message": "API key validation simulated - use real keys for actual validation"
                }
            }
        })

    logger.info("Minimal test app created successfully")
    return app

if __name__ == '__main__':
    app = create_minimal_app()
    port = int(os.environ.get("PYTHON_API_PORT", 5058))
    logger.info(f"Starting minimal test server on port {port}")
    logger.info("Endpoints available:")
    logger.info("  GET  /healthz - Health check")
    logger.info("  GET  /api/test - Test endpoint")
    logger.info("  POST /api/integrations/validate - API key validation test")
    app.run(host='0.0.0.0', port=port, debug=True)
