import logging
from flask import Blueprint, request, jsonify, current_app
from .goals_service import GoalsService

goals_bp = Blueprint('goals', __name__)
logger = logging.getLogger(__name__)

@goals_bp.route('/api/goals', methods=['GET'])
def get_goals():
    """Get all financial goals for a user."""
    try:
        user_id = request.args.get('userId')
        goal_type = request.args.get('goalType', 'all')
        status = request.args.get('status', 'all')

        if not user_id:
            return jsonify({"error": "userId is required"}), 400

        db_pool = current_app.config['DB_CONNECTION_POOL']
        goals = GoalsService.get_goals(user_id, db_pool, goal_type, status)

        return jsonify({"goals": goals}), 200

    except Exception as e:
        logger.error(f"Error getting goals: {e}")
        return jsonify({"error": str(e)}), 500

@goals_bp.route('/api/goals', methods=['POST'])
def create_goal():
    """Create a new financial goal."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        user_id = data.get('userId')
        if not user_id:
            return jsonify({"error": "userId is required"}), 400

        required_fields = ['title', 'targetAmount', 'goalType']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"{field} is required"}), 400

        db_pool = current_app.config['DB_CONNECTION_POOL']

        goal = GoalsService.create_goal(
            user_id=user_id,
            db_conn_pool=db_pool,
            title=data['title'],
            target_amount=data['targetAmount'],
            goal_type=data['goalType'],
            description=data.get('description'),
            target_date=data.get('targetDate'),
            priority=data.get('priority', 1),
            account_id=data.get('accountId'),
            initial_amount=data.get('initialAmount', 0)
        )

        return jsonify(goal), 201

    except Exception as e:
        logger.error(f"Error creating goal: {e}")
        return jsonify({"error": str(e)}), 500

@goals_bp.route('/api/goals/<int:goal_id>', methods=['GET'])
def get_goal(goal_id):
    """Get a specific financial goal."""
    try:
        user_id = request.args.get('userId')
        if not user_id:
            return jsonify({"error": "userId is required"}), 400

        db_pool = current_app.config['DB_CONNECTION_POOL']
        goal = GoalsService.get_goal_by_id(user_id, db_pool, goal_id)

        if not goal:
            return jsonify({"error": "Goal not found"}), 404

        return jsonify(goal), 200

    except Exception as e:
        logger.error(f"Error getting goal: {e}")
        return jsonify({"error": str(e)}), 500

@goals_bp.route('/api/goals/<int:goal_id>', methods=['PUT'])
def update_goal(goal_id):
    """Update a financial goal."""
    try:
        data = request.get_json()
        user_id = data.get('userId')

        if not user_id:
            return jsonify({"error": "userId is required"}), 400

        # Build update kwargs from allowed fields
        allowed_fields = ['title', 'description', 'targetAmount', 'goalType',
                         'targetDate', 'priority', 'status', 'accountId']
        update_kwargs = {}

        for field in allowed_fields:
            if field in data:
                # Convert field names to database column names
                db_field = 'target_amount' if field == 'targetAmount' else \
                          'target_date' if field == 'targetDate' else \
                          'account_id' if field == 'accountId' else field
                update_kwargs[db_field] = data[field]

        if not update_kwargs:
            return jsonify({"error": "No valid fields to update"}), 400

        db_pool = current_app.config['DB_CONNECTION_POOL']
        updated_goal = GoalsService.update_goal(user_id, db_pool, goal_id, **update_kwargs)

        return jsonify(updated_goal), 200

    except Exception as e:
        logger.error(f"Error updating goal: {e}")
        return jsonify({"error": str(e)}), 500

@goals_bp.route('/api/goals/<int:goal_id>', methods=['DELETE'])
def delete_goal(goal_id):
    """Delete a financial goal."""
    try:
        user_id = request.args.get('userId')
        if not user_id:
            return jsonify({"error": "userId is required"}), 400

        db_pool = current_app.config['DB_CONNECTION_POOL']
        success = GoalsService.delete_goal(user_id, db_pool, goal_id)

        if success:
            return jsonify({"message": "Goal deleted successfully"}), 200
        else:
            return jsonify({"error": "Goal not found or not deleted"}), 404

    except Exception as e:
        logger.error(f"Error deleting goal: {e}")
        return jsonify({"error": str(e)}), 500

@goals_bp.route('/api/goals/<int:goal_id>/contribute', methods=['POST'])
def add_contribution(goal_id):
    """Add a contribution to a financial goal."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        user_id = data.get('userId')
        amount = data.get('amount')

        if not user_id:
            return jsonify({"error": "userId is required"}), 400

        if amount is None:
            return jsonify({"error": "amount is required"}), 400

        db_pool = current_app.config['DB_CONNECTION_POOL']
        contribution = GoalsService.add_contribution(
            user_id=user_id,
            db_conn_pool=db_pool,
            goal_id=goal_id,
            amount=amount,
            description=data.get('description'),
            source_account_id=data.get('sourceAccountId'),
            contribution_date=data.get('contributionDate')
        )

        return jsonify(contribution), 201

    except Exception as e:
        logger.error(f"Error adding contribution: {e}")
        return jsonify({"error": str(e)}), 500

@goals_bp.route('/api/goals/<int:goal_id>/contributions', methods=['GET'])
def get_contributions(goal_id):
    """Get all contributions for a specific goal."""
    try:
        user_id = request.args.get('userId')
        if not user_id:
            return jsonify({"error": "userId is required"}), 400

        db_pool = current_app.config['DB_CONNECTION_POOL']
        contributions = GoalsService.get_contributions(user_id, db_pool, goal_id)

        return jsonify({"contributions": contributions}), 200

    except Exception as e:
        logger.error(f"Error getting contributions: {e}")
        return jsonify({"error": str(e)}), 500
