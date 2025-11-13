"""
Finances API routes
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import db, Transaction, User
from ..utils import generate_uuid, validate_transaction_data
from datetime import datetime, timedelta
import logging

finances_bp = Blueprint('finances', __name__)
logger = logging.getLogger(__name__)

@finances_bp.route('/transactions', methods=['GET'])
@jwt_required()
def get_transactions():
    """Get all transactions for the current user"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Get query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        category = request.args.get('category')
        type_filter = request.args.get('type')  # debit, credit
        limit = request.args.get('limit', 100, type=int)

        query = Transaction.query.filter_by(user_id=user_id)

        if start_date:
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(Transaction.date >= start)

        if end_date:
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(Transaction.date <= end)

        if category:
            query = query.filter_by(category=category)

        if type_filter:
            query = query.filter_by(type=type_filter)

        transactions = query.order_by(Transaction.date.desc()).limit(limit).all()
        return jsonify([transaction.to_dict() for transaction in transactions])
    except Exception as e:
        logger.error(f'Error fetching transactions: {str(e)}')
        return jsonify({'error': 'Failed to fetch transactions'}), 500

@finances_bp.route('/transactions', methods=['POST'])
@jwt_required()
def create_transaction():
    """Create a new transaction"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()
        if not data or not data.get('date') or not data.get('description') or not data.get('amount') or not data.get('category') or not data.get('type'):
            return jsonify({'error': 'Date, description, amount, category, and type are required'}), 400

        # Validate transaction data
        validation_error = validate_transaction_data(data)
        if validation_error:
            return jsonify({'error': validation_error}), 400

        transaction = Transaction(
            id=generate_uuid(),
            user_id=user_id,
            date=datetime.fromisoformat(data['date'].replace('Z', '+00:00')),
            description=data['description'],
            amount=float(data['amount']),
            category=data['category'],
            type=data['type'],
            account=data.get('account'),
            tags=data.get('tags', [])
        )

        db.session.add(transaction)
        db.session.commit()

        logger.info(f'Transaction created: {transaction.id} for user {user_id}')
        return jsonify(transaction.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error creating transaction: {str(e)}')
        return jsonify({'error': 'Failed to create transaction'}), 500

@finances_bp.route('/transactions/<transaction_id>', methods=['GET'])
@jwt_required()
def get_transaction(transaction_id):
    """Get a specific transaction"""
    try:
        user_id = get_jwt_identity()
        transaction = Transaction.query.filter_by(id=transaction_id, user_id=user_id).first()
        if not transaction:
            return jsonify({'error': 'Transaction not found'}), 404

        return jsonify(transaction.to_dict())
    except Exception as e:
        logger.error(f'Error fetching transaction {transaction_id}: {str(e)}')
        return jsonify({'error': 'Failed to fetch transaction'}), 500

@finances_bp.route('/transactions/<transaction_id>', methods=['PUT'])
@jwt_required()
def update_transaction(transaction_id):
    """Update a transaction"""
    try:
        user_id = get_jwt_identity()
        transaction = Transaction.query.filter_by(id=transaction_id, user_id=user_id).first()
        if not transaction:
            return jsonify({'error': 'Transaction not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate transaction data
        validation_error = validate_transaction_data(data, partial=True)
        if validation_error:
            return jsonify({'error': validation_error}), 400

        # Update transaction fields
        for field in ['date', 'description', 'amount', 'category', 'type', 'account', 'tags']:
            if field in data:
                if field == 'date':
                    setattr(transaction, field, datetime.fromisoformat(data[field].replace('Z', '+00:00')))
                elif field == 'amount':
                    setattr(transaction, field, float(data[field]))
                else:
                    setattr(transaction, field, data[field])

        db.session.commit()

        logger.info(f'Transaction updated: {transaction_id} for user {user_id}')
        return jsonify(transaction.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error updating transaction {transaction_id}: {str(e)}')
        return jsonify({'error': 'Failed to update transaction'}), 500

@finances_bp.route('/transactions/<transaction_id>', methods=['DELETE'])
@jwt_required()
def delete_transaction(transaction_id):
    """Delete a transaction"""
    try:
        user_id = get_jwt_identity()
        transaction = Transaction.query.filter_by(id=transaction_id, user_id=user_id).first()
        if not transaction:
            return jsonify({'error': 'Transaction not found'}), 404

        db.session.delete(transaction)
        db.session.commit()

        logger.info(f'Transaction deleted: {transaction_id} for user {user_id}')
        return jsonify({'message': 'Transaction deleted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting transaction {transaction_id}: {str(e)}')
        return jsonify({'error': 'Failed to delete transaction'}), 500

@finances_bp.route('/summary', methods=['GET'])
@jwt_required()
def get_financial_summary():
    """Get financial summary for the current user"""
    try:
        user_id = get_jwt_identity()
        transactions = Transaction.query.filter_by(user_id=user_id).all()

        # Calculate totals
        total_income = sum(t.amount for t in transactions if t.type == 'credit')
        total_expenses = sum(t.amount for t in transactions if t.type == 'debit')
        net_income = total_income - total_expenses

        # Group by category
        expenses_by_category = {}
        income_by_category = {}

        for transaction in transactions:
            if transaction.type == 'debit':
                expenses_by_category[transaction.category] = expenses_by_category.get(transaction.category, 0) + transaction.amount
            else:
                income_by_category[transaction.category] = income_by_category.get(transaction.category, 0) + transaction.amount

        # Monthly breakdown (last 12 months)
        monthly_data = {}
        for i in range(12):
            month_start = datetime.utcnow().replace(day=1) - timedelta(days=i*30)
            month_end = month_start.replace(day=28) + timedelta(days=4)  # Last day of month
            month_end = month_end - timedelta(days=month_end.day)

            month_transactions = [t for t in transactions if month_start <= t.date <= month_end]
            month_income = sum(t.amount for t in month_transactions if t.type == 'credit')
            month_expenses = sum(t.amount for t in month_transactions if t.type == 'debit')

            monthly_data[month_start.strftime('%Y-%m')] = {
                'income': month_income,
                'expenses': month_expenses,
                'net': month_income - month_expenses
            }

        summary = {
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_income': net_income,
            'expenses_by_category': expenses_by_category,
            'income_by_category': income_by_category,
            'monthly_breakdown': monthly_data,
            'transaction_count': len(transactions)
        }

        return jsonify(summary)
    except Exception as e:
        logger.error(f'Error fetching financial summary: {str(e)}')
        return jsonify({'error': 'Failed to fetch financial summary'}), 500

@finances_bp.route('/budgets', methods=['GET'])
@jwt_required()
def get_budgets():
    """Get budget information (mock data for now)"""
    # In a real implementation, this would have a Budget model
    budgets = [
        {'id': 'budget-1', 'category': 'Groceries', 'amount': 500, 'spent': 85.40},
        {'id': 'budget-2', 'category': 'Entertainment', 'amount': 100, 'spent': 15.99},
        {'id': 'budget-3', 'category': 'Utilities', 'amount': 150, 'spent': 120.50},
        {'id': 'budget-4', 'category': 'Transportation', 'amount': 80, 'spent': 75.00},
    ]
    return jsonify(budgets)

@finances_bp.route('/insights', methods=['GET'])
@jwt_required()
def get_financial_insights():
    """Get financial insights and recommendations"""
    try:
        user_id = get_jwt_identity()
        transactions = Transaction.query.filter_by(user_id=user_id).all()

        insights = []

        # Calculate spending patterns
        expenses = [t for t in transactions if t.type == 'debit']
        if expenses:
            avg_daily_spending = sum(t.amount for t in expenses) / max(1, len(set(t.date.date() for t in expenses)))

            # Check for unusual spending
            recent_expenses = [t for t in expenses if (datetime.utcnow() - t.date).days <= 30]
            if recent_expenses:
                avg_recent = sum(t.amount for t in recent_expenses) / len(recent_expenses)
                if avg_recent > avg_daily_spending * 1.5:
                    insights.append({
                        'type': 'warning',
                        'title': 'Increased Spending',
                        'message': 'Your recent spending is 50% higher than your average.',
                        'recommendation': 'Review your recent transactions to identify unusual expenses.'
                    })

        # Budget alerts
        budgets = get_budgets().get_json()  # This is a mock call
        for budget in budgets:
            spent_percentage = (budget['spent'] / budget['amount']) * 100
            if spent_percentage >= 90:
                insights.append({
                    'type': 'warning',
                    'title': f'Budget Alert: {budget["category"]}',
                    'message': f'You\'ve spent {spent_percentage:.1f}% of your {budget["category"]} budget.',
                    'recommendation': 'Consider reducing spending in this category or increasing your budget.'
                })

        # Savings recommendations
        income = sum(t.amount for t in transactions if t.type == 'credit')
        expenses_total = sum(t.amount for t in transactions if t.type == 'debit')
        savings_rate = ((income - expenses_total) / max(1, income)) * 100

        if savings_rate < 20:
            insights.append({
                'type': 'info',
                'title': 'Savings Opportunity',
                'message': f'Your current savings rate is {savings_rate:.1f}%.',
                'recommendation': 'Consider saving at least 20% of your income for financial security.'
            })

        return jsonify(insights)
    except Exception as e:
        logger.error(f'Error fetching financial insights: {str(e)}')
        return jsonify({'error': 'Failed to fetch financial insights'}), 500
