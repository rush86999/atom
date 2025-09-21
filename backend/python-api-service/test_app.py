import os
import sys
from flask import Flask
from flask.testing import FlaskClient

# Set environment variables for testing
os.environ['DATABASE_URL'] = 'postgresql://user:pass@localhost/atom_db'
os.environ['ATOM_OAUTH_ENCRYPTION_KEY'] = 'dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1jaGFycy1sb25n'
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key-for-development'

def test_app_health():
    """Test the Flask application health endpoint"""
    try:
        # Import and create the app
        from main_api_app import create_app
        app = create_app()

        print("✅ Main app created successfully")

        # Test health endpoint
        with app.test_client() as client:
            response = client.get('/healthz')
            data = response.get_json()

            print(f"✅ Health endpoint: {response.status_code}")
            print(f"📊 Health data: {data}")

            return True

    except Exception as e:
        print(f"❌ Error testing app: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_minimal_app():
    """Test the minimal Flask application"""
    try:
        # Import and create the minimal app
        from minimal_app import create_minimal_app
        app = create_minimal_app()

        print("✅ Minimal app created successfully")

        # Test root endpoint
        with app.test_client() as client:
            response = client.get('/')
            data = response.get_json()

            print(f"✅ Root endpoint: {response.status_code}")
            print(f"📊 Root data: {data}")

            # Test health endpoint
            response = client.get('/healthz')
            data = response.get_json()

            print(f"✅ Health endpoint: {response.status_code}")
            print(f"📊 Health data: {data}")

            return True

    except Exception as e:
        print(f"❌ Error testing minimal app: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_goals_endpoint():
    """Test the goals endpoint"""
    try:
        from main_api_app import create_app
        app = create_app()

        with app.test_client() as client:
            # Test goals endpoint with demo user
            response = client.get('/api/goals?userId=demo_user')
            data = response.get_json()

            print(f"✅ Goals endpoint: {response.status_code}")
            print(f"📊 Goals data: {data}")

            return True

    except Exception as e:
        print(f"❌ Error testing goals: {e}")
        return False

if __name__ == '__main__':
    print("🚀 Testing ATOM Application...")
    print("=" * 50)

    success1 = test_app_health()
    print("\n" + "=" * 50)
    success2 = test_minimal_app()

    print("\n" + "=" * 50)
    success3 = test_goals_endpoint()

    if success1 and success2 and success3:
        print("\n" + "=" * 50)
        print("✅ All tests passed! Application is ready.")
    else:
        print("\n" + "=" * 50)
        print("❌ Some tests failed. Check the logs above.")
        sys.exit(1)
