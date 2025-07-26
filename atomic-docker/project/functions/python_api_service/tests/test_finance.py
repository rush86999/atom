import pytest
from main_api_app import create_app
import json

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_create_account(client):
    """Test creating a new account."""
    response = client.post('/api/accounts', data=json.dumps({
        "user_id": "test_user",
        "account_name": "Test Account",
        "account_type": "Checking",
        "balance": 1000.00
    }), content_type='application/json')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] == True
    assert data['data']['account_name'] == 'Test Account'

def test_get_accounts(client):
    """Test getting accounts for a user."""
    response = client.get('/api/accounts?user_id=test_user')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] == True
    assert isinstance(data['data'], list)

def test_create_transaction(client):
    """Test creating a new transaction."""
    # First, create an account to associate the transaction with
    client.post('/api/accounts', data=json.dumps({
        "user_id": "test_user",
        "account_name": "Test Account",
        "account_type": "Checking",
        "balance": 1000.00
    }), content_type='application/json')

    response = client.post('/api/transactions', data=json.dumps({
        "account_id": 1,
        "amount": -50.00,
        "description": "Test Transaction",
        "date": "2025-01-01",
        "category": "Groceries"
    }), content_type='application/json')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] == True
    assert data['data']['description'] == 'Test Transaction'

def test_get_transactions(client):
    """Test getting transactions for an account."""
    response = client.get('/api/transactions?account_id=1')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] == True
    assert isinstance(data['data'], list)

def test_get_net_worth(client):
    """Test getting net worth for a user."""
    response = client.get('/api/financial-calculations/net-worth?user_id=test_user')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] == True
    assert 'net_worth' in data['data']
