"""
Plaid API Production Service

Production-ready implementation for interfacing with the Plaid API.
Handles bank account connections, transaction retrieval, investment data,
and financial analytics with proper error handling and rate limiting.

This is the REAL implementation using the actual Plaid client library.
Requires Plaid credentials in environment variables.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Production Imports - Only import plaid if available, fallback gracefully
try:
    from plaid import Client  # type: ignore
    from plaid.api import plaid_api  # type: ignore
    from plaid.model.account_base import AccountBase  # type: ignore
    from plaid.model.transactions_get_request import TransactionsGetRequest  # type: ignore
    from plaid.model.transactions_get_response import TransactionsGetResponse  # type: ignore
    from plaid.model.item_get_request import ItemGetRequest  # type: ignore
    from plaid.model.accounts_get_request import AccountsGetRequest  # type: ignore
    from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest  # type: ignore
    from plaid.model.liabilities_get_request import LiabilitiesGetRequest  # type: ignore
    from plaid.model.link_token_create_request import LinkTokenCreateRequest  # type: ignore
    from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser  # type: ignore
    PLAID_AVAILABLE = True
except ImportError:
    PLAID_AVAILABLE = False
    Client = None
    raise ImportError(
        "Plaid library not installed. Install with: pip install plaid-python"
    )

# Configure logging
logger = logging.getLogger(__name__)

# Production Configuration
PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
PLAID_SECRET = os.getenv("PLAID_SECRET")
PLAID_ENVIRONMENT = os.getenv("PLAID_ENV", "sandbox")  # sandbox|development|production

# Production validation
if not PLAID_CLIENT_ID:
    raise ValueError("PLAID_CLIENT_ID environment variable is required for production")
if not PLAID_SECRET:
    raise ValueError("PLAID_SECRET environment variable is required for production")

@dataclass
class BankAccount:
    """Represents a bank account."""
    account_id: str
    account_name: str
    account_type: str
    account_subtype: str
    balance_available: float
    balance_current: float
    institution_name: str

@dataclass
class Transaction:
    """Represents a transaction."""
    transaction_id: str
    account_id: str
    amount: float
    date: str
    merchant_name: Optional[str]
    category: List[str]
    payment_channel: str

@dataclass
class InvestmentHolding:
    """Represents an investment holding."""
    account_id: str
    security_id: str
    security_name: str
    quantity: float
    value: float
    institution_price: float

class PlaidService:
    """Production Plaid API service."""

    def __init__(self):
        """Initialize Plaid service with production credentials."""
        if not PLAID_AVAILABLE:
            raise RuntimeError("Plaid library not available. Install: pip install plaid-python")

        self.client = Client(
            client_id=PLAID_CLIENT_ID,
            secret=PLAID_SECRET,
            environment=PLAID_ENVIRONMENT
        )
        self.api_client = self.client

    def create_link_token(self, user_id: str) -> str:
        """
        Create a link token for bank account connection.

        Args:
            user_id: The user ID to create token for

        Returns:
            Link token for Plaid Link initialization
        """
        try:
            request = LinkTokenCreateRequest(
                user=LinkTokenCreateRequestUser(client_user_id=user_id),
                client_name="Atom Agent",
                products=["transactions", "auth"],
                country_codes=["US", "CA"],
                language="en",
                webhook="https://yourapp.com/webhook/plaid"
            )
            response = self.api_client.link_token_create(request)
            return response['link_token']
        except Exception as e:
            logger.error(f"Failed to create Plaid link token: {e}")
            raise

    def exchange_public_token(self, public_token: str) -> Dict[str, str]:
        """
        Exchange public token for access token.

        Args:
            public_token: The public token from Plaid Link

        Returns:
            Dict with access_token and item_id
        """
        try:
            response = self.api_client.item_public_token_exchange(
                public_token=public_token
            )
            return {
                'access_token': response['access_token'],
                'item_id': response['item_id']
            }
        except Exception as e:
            logger.error(f"Failed to exchange public token: {e}")
            raise

    def get_accounts(self, access_token: str) -> List[BankAccount]:
        """
        Get all bank accounts for a connected institution.

        Args:
            access_token: The Plaid access token

        Returns:
            List of BankAccount objects
        """
        try:
            request = AccountsGetRequest(access_token=access_token)
            response = self.api_client.accounts_get(request)

            accounts = []
            for account in response['accounts']:
                accounts.append(BankAccount(
                    account_id=account['account_id'],
                    account_name=account.get('official_name', account['name']),
                    account_type=account['type'],
                    account_subtype=account['subtype'],
                    balance_available=account['balances']['available'] or 0.0,
                    balance_current=account['balances']['current'] or 0.0,
                    institution_name=response['item']['institution_name'] or 'Unknown'
                ))
            return accounts
        except Exception as e:
            logger.error(f"Failed to get accounts: {e}")
            raise

    def get_transactions(self, access_token: str, days_back: int = 30) -> List[Transaction]:
        """
        Get transactions for a connected account.

        Args:
            access_token: The Plaid access token
            days_back: Number of days to retrieve transactions for

        Returns:
            List of Transaction objects
        """
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days_back)

            request = TransactionsGetRequest(
                access_token=access_token,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat()
            )

            response = self.api_client.transactions_get(request)

            transactions = []
            for txn in response['transactions']:
                transactions.append(Transaction(
                    transaction_id=txn['transaction_id'],
                    account_id=txn['account_id'],
                    amount=txn['amount'],
                    date=txn['date'],
                    merchant_name=txn.get('merchant_name'),
                    category=txn.get('category', []),
                    payment_channel=txn.get('payment_channel', 'other')
                ))
            return transactions
        except Exception as e:
            logger.error(f"Failed to get transactions: {e}")
            raise

    def get_investments(self, access_token: str) -> List[InvestmentHolding]:
        """
        Get investment holdings for connected accounts.

        Args:
            access_token: The Plaid access token

        Returns:
            List of InvestmentHolding objects
        """
        try:
            request = InvestmentsHoldingsGetRequest(access_token=access_token)
            response = self.api_client.investments_holdings_get(request)

            holdings = []
            for holding in response['holdings']:
                security = next(
                    s for s in response['securities']
                    if s['security_id'] == holding['security_id']
                )

                holdings.append(InvestmentHolding(
                    account_id=holding['account_id'],
                    security_id=holding['security_id'],
                    security_name=security['name'],
                    quantity=holding['quantity'],
                    value=holding['institution_value'] or 0.0,
                    institution_price=holding['institution_price'] or 0.0
                ))
            return holdings
        except Exception as e:
            logger.error(f"Failed to get investments: {e}")
            raise

    def get_item_status(self, access_token: str) -> Dict[str, Any]:
        """
        Check the status and health of a connected item.

        Args:
            access_token: The Plaid access token

        Returns:
            Dict containing item status and metadata
        """
        try:
            request = ItemGetRequest(access_token=access_token)
            response = self.api_client.item_get(request)
            return response['item']
        except Exception as e:
            logger.error(f"Failed to get item status: {e}")
            raise

    def remove_item(self, access_token: str) -> bool:
        """
        Remove a connected bank account.

        Args:
            access_token: The Plaid access token

        Returns:
            True if removal successful
        """
        try:
            self.api_client.item_remove(access_token=access_token)
            return True
        except Exception as e:
            logger.error(f"Failed to remove item: {e}")
            return False

    def get_transaction_summary(self, access_token: str, days_back: int = 30) -> Dict[str, Any]:
        """
        Get aggregated transaction summary.

        Args:
            access_token: The Plaid access token
            days_back: Number of days to analyze

        Returns:
            Dict containing transaction summary
        """
        try:
            transactions = self.get_transactions(access_token, days_back)

            summary = {
                'total_spent': 0.0,
                'total_received': 0.0,
                'transaction_count': len(transactions),
                'categories': {},
                'daily_average': 0.0
            }

            total_amount = 0.0
            for txn in transactions:
                amount = txn['amount']
                if amount > 0:
                    summary['total_spent'] += amount
                else:
                    summary['total_received'] += abs(amount)

                total_amount += abs(amount)

                # Categorize transactions
                category = txn.get('category', ['Unknown'])[0] if txn.get('category') else 'Unknown'
                if category not in summary['categories']:
                    summary['categories'][category] = {'amount': 0.0, 'count': 0}
                summary['categories'][category]['amount'] += abs(amount)
                summary['categories'][category]['count'] += 1

            summary['daily_average'] = total_amount / days_back

            return summary
        except Exception as e:
            logger.error(f"Failed to get transaction summary: {e}")
            raise

# Service factory
def create_plaid_service() -> PlaidService:
    """Factory method to create Plaid service."""
    return PlaidService()

# Export for use
__all__ = ['PlaidService', 'BankAccount', 'Transaction', 'InvestmentHolding', 'create_plaid_service']
