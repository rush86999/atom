import os
import sys
import time
from flask import Flask

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

def test_basic_flask():
    """Test basic Flask application"""
    app = Flask(__name__)

    @app.route('/')
    def hello():
        return 'Hello, World!'

    @app.route('/health')
    def health():
        return {'status': 'ok'}

    return app

def test_main_app_import():
    """Test if main application can be imported"""
    try:
        from main_api_app import create_app
        print("✅ Main app imports successfully")
        return True
    except Exception as e:
        print(f"❌ Main app import failed: {e}")
        return False

def test_main_app_creation():
    """Test if main application can be created"""
    try:
        # Set required environment variables
        os.environ.update({
            'DATABASE_URL': 'sqlite:///tmp/atom_dev.db',
            'ATOM_OAUTH_ENCRYPTION_KEY': 'nCsfAph2Gln5Ag0uuEeqUVOvSEPtl7OLGT_jKsyzP84=',
            'FLASK_SECRET_KEY': 'dev-secret-key-change-in-production',
            'FLASK_ENV': 'development'
        })

        from main_api_app import create_app
        app = create_app()
        print("✅ Main app created successfully")
        return app
    except Exception as e:
        print(f"❌ Main app creation failed: {e}")
        return None

def test_health_endpoint(app):
    """Test health endpoint"""
    try:
        with app.test_client() as client:
            response = client.get('/healthz')
            if response.status_code == 200:
                print("✅ Health endpoint works")
                return True
            else:
                print(f"❌ Health endpoint failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Health endpoint test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting ATOM Application Startup Tests")
    print("=" * 50)

    # Test 1: Basic Flask
    print("\n1. Testing basic Flask application...")
    basic_app = test_basic_flask()
    print("✅ Basic Flask app created")

    # Test 2: Main app import
    print("\n2. Testing main application import...")
    import_success = test_main_app_import()

    # Test 3: Main app creation
    print("\n3. Testing main application creation...")
    main_app = test_main_app_creation()

    # Test 4: Health endpoint
    if main_app:
        print("\n4. Testing health endpoint...")
        health_success = test_health_endpoint(main_app)

    print("\n" + "=" * 50)
    print("🎯 Startup Tests Complete")

    # Summary
    if import_success and main_app:
        print("✅ Application is ready for real API key testing")
        print("\nNext steps:")
        print("1. Obtain real API keys for services")
        print("2. Update .env.production with real keys")
        print("3. Run integration tests")
        print("4. Deploy to production")
    else:
        print("❌ Application needs fixes before API key testing")

if __name__ == "__main__":
    main()
