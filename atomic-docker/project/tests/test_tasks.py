import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta
from project.tasks import check_budget_alerts
from project.database import SessionLocal
from project.models import User, Account, Budget, Transaction

@pytest.fixture
def db_session():
    """Creates a new database session for a test."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@patch('project.tasks.execute_http_request.delay')
def test_check_budget_alerts_sends_email_when_budget_exceeded(mock_execute_http_request, db_session):
    # 1. Set up test data
    user = User(id='test-user', email='test@example.com')
    account = Account(id=1, user_id=user.id, account_name='Test Account', account_type='checking', balance=1000)
    budget = Budget(id=1, user_id=user.id, name='Groceries', category='Groceries', amount=500, start_date=date.today() - timedelta(days=1), is_active=True)
    transaction = Transaction(id=1, account_id=account.id, amount=460, category='Groceries', date=date.today())

    db_session.add_all([user, account, budget, transaction])
    db_session.commit()

    # 2. Call the task
    check_budget_alerts()

    # 3. Assert that the email was sent
    mock_execute_http_request.assert_called_once()
    args, kwargs = mock_execute_http_request.call_args
    assert args[0] == 'POST'
    assert args[1] == 'http://gmail-service:3000/send-email'
    assert args[2]['to'] == user.email
    assert 'Approaching limit' in args[2]['subject']

    # Clean up
    db_session.delete(transaction)
    db_session.delete(budget)
    db_session.delete(account)
    db_session.delete(user)
    db_session.commit()
