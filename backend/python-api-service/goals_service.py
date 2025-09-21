import logging
from typing import Dict, List, Optional, Any
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class GoalsService:
    """Service for managing financial goals with full CRUD operations."""

    GOAL_TYPES = ['emergency_fund', 'retirement', 'savings', 'debt_payoff', 'investment', 'purchase', 'education', 'vacation', 'home', 'car']
    STATUSES = ['active', 'paused', 'completed', 'cancelled', 'on_hold']

    @staticmethod
    def get_goals(user_id: str, db_conn_pool,
                  goal_type: Optional[str] = None,
                  status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve financial goals for a user."""
        conn = None
        try:
            conn = db_conn_pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT
                        g.id,
                        g.user_id,
                        g.title AS name,
                        g.description,
                        g.target_amount AS target,
                        g.current_amount AS current,
                        g.goal_type,
                        g.target_date AS deadline,
                        g.priority,
                        g.status,
                        g.account_id,
                        a.name AS account_name
                    FROM financial_goals g
                    LEFT JOIN accounts a ON g.account_id = a.id
                    WHERE g.user_id = %s
                """

                params = [user_id]
                if goal_type and goal_type != 'all':
                    query += " AND g.goal_type = %s"
                    params.append(goal_type)

                if status and status != 'all':
                    query += " AND g.status = %s"
                    params.append(status)

                query += " ORDER BY g.priority ASC, g.created_at DESC"

                cursor.execute(query, params)
                goals = cursor.fetchall()

                processed_goals = []
                for goal in goals:
                    goal_dict = dict(goal)

                    # Calculate progress
                    target = float(goal_dict.get('target', 0))
                    current = float(goal_dict.get('current', 0))
                    goal_dict['progress'] = round((current / target * 100) if target > 0 else 0, 2)

                    # Convert decimal types to float for JSON serialization
                    for key in ['target', 'current']:
                        if goal_dict.get(key) is not None:
                            goal_dict[key] = float(goal_dict[key])

                    # Format dates
                    for date_key in ['deadline', 'created_at', 'updated_at']:
                        if goal_dict.get(date_key):
                            goal_dict[date_key] = str(goal_dict[date_key])

                    processed_goals.append(goal_dict)

                return processed_goals

        except Exception as e:
            logger.error(f"Error fetching goals: {e}")
            return []
        finally:
            if conn:
                db_conn_pool.putconn(conn)

    @staticmethod
    def get_goal_by_id(user_id: str, db_conn_pool, goal_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific goal by ID."""
        goals = GoalsService.get_goals(user_id, db_conn_pool)
        return next((goal for goal in goals if goal['id'] == goal_id), None)

    @staticmethod
    def create_goal(user_id: str, db_conn_pool,
                    title: str, target_amount: float, goal_type: str,
                    description: Optional[str] = None,
                    target_date: Optional[str] = None,
                    priority: int = 1,
                    account_id: Optional[int] = None,
                    initial_amount: float = 0) -> Dict[str, Any]:
        """Create a new financial goal."""
        conn = None
        try:
            conn = db_conn_pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    INSERT INTO financial_goals
                    (user_id, title, description, target_amount, current_amount,
                     goal_type, target_date, priority, account_id, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'active')
                    RETURNING id
                """

                cursor.execute(query, [
                    user_id, title, description, target_amount,
                    initial_amount, goal_type, target_date,
                    priority, account_id
                ])

                goal_id_result = cursor.fetchone()['id']
                conn.commit()

                # Return the newly created goal
                return GoalsService.get_goal_by_id(user_id, db_conn_pool, goal_id_result)

        except Exception as e:
            logger.error(f"Error creating goal: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                db_conn_pool.putconn(conn)

    @staticmethod
    def update_goal(user_id: str, db_conn_pool,
                    goal_id: int, **kwargs) -> Dict[str, Any]:
        """Update an existing financial goal."""
        conn = None
        try:
            conn = db_conn_pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Check if goal belongs to user
                cursor.execute(
                    "SELECT id FROM financial_goals WHERE id = %s AND user_id = %s",
                    (goal_id, user_id)
                )
                if not cursor.fetchone():
                    raise ValueError("Goal not found")

                # Build dynamic update query
                update_fields = []
                params = []
                for key, value in kwargs.items():
                    if key in ['title', 'description', 'target_amount', 'goal_type',
                               'target_date', 'priority', 'status', 'account_id']:
                        update_fields.append(f"{key} = %s")
                        params.append(value)

                if not update_fields:
                    raise ValueError("No valid fields to update")

                update_fields_str = ", ".join(update_fields)
                query = f"""
                    UPDATE financial_goals
                    SET {update_fields_str}
                    WHERE id = %s AND user_id = %s
                    RETURNING id
                """
                params.extend([goal_id, user_id])

                cursor.execute(query, params)
                conn.commit()

                return GoalsService.get_goal_by_id(user_id, db_conn_pool, goal_id)

        except Exception as e:
            logger.error(f"Error updating goal: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                db_conn_pool.putconn(conn)

    @staticmethod
    def delete_goal(user_id: str, db_conn_pool, goal_id: int) -> bool:
        """Delete a financial goal."""
        conn = None
        try:
            conn = db_conn_pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "DELETE FROM financial_goals WHERE id = %s AND user_id = %s",
                    (goal_id, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting goal: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                db_conn_pool.putconn(conn)

    @staticmethod
    def add_contribution(user_id: str, db_conn_pool,
                         goal_id: int,
                         amount: float,
                         description: Optional[str] = None,
                         source_account_id: Optional[int] = None,
                         contribution_date: Optional[str] = None) -> Dict[str, Any]:
        """Add a contribution to a financial goal."""
        if not contribution_date:
            from datetime import date
            contribution_date = date.today().isoformat()

        conn = None
        try:
            conn = db_conn_pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Verify goal belongs to user
                cursor.execute(
                    "SELECT id FROM financial_goals WHERE id = %s AND user_id = %s",
                    (goal_id, user_id)
                )
                if not cursor.fetchone():
                    raise ValueError("Goal not found or not owned by user")

                # Insert contribution
                contribution_query = """
                    INSERT INTO goal_contributions
                    (goal_id, amount, contribution_date, source_account_id, description)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING *
                """
                cursor.execute(contribution_query, [
                    goal_id, amount, contribution_date, source_account_id, description
                ])
                contribution = cursor.fetchone()

                # Update goal's current amount
                cursor.execute(
                    """
                    UPDATE financial_goals
                    SET current_amount = current_amount + %s
                    WHERE id = %s
                    """,
                    (amount, goal_id)
                )

                conn.commit()

                contribution_dict = dict(contribution)
                contribution_dict['amount'] = float(contribution_dict['amount'])
                return contribution_dict

        except Exception as e:
            logger.error(f"Error adding contribution: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                db_conn_pool.putconn(conn)

    @staticmethod
    def get_contributions(user_id: str, db_conn_pool, goal_id: int) -> List[Dict[str, Any]]:
        """Get all contributions for a specific goal."""
        conn = None
        try:
            conn = db_conn_pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Verify goal belongs to user
                cursor.execute(
                    "SELECT id FROM financial_goals WHERE id = %s AND user_id = %s",
                    (goal_id, user_id)
                )
                if not cursor.fetchone():
                    raise ValueError("Goal not found or not owned by user")

                # Get all contributions for the goal
                query = """
                    SELECT
                        gc.id,
                        gc.goal_id,
                        gc.amount,
                        gc.contribution_date,
                        gc.source_account_id,
                        gc.description,
                        gc.created_at,
                        a.name AS account_name
                    FROM goal_contributions gc
                    LEFT JOIN accounts a ON gc.source_account_id = a.id
                    WHERE gc.goal_id = %s
                    ORDER BY gc.contribution_date DESC, gc.created_at DESC
                """
                cursor.execute(query, [goal_id])
                contributions = cursor.fetchall()

                # Convert to list of dictionaries and format amounts
                result = []
                for contribution in contributions:
                    contrib_dict = dict(contribution)
                    contrib_dict['amount'] = float(contrib_dict['amount'])
                    # Format dates
                    for date_key in ['contribution_date', 'created_at']:
                        if contrib_dict.get(date_key):
                            contrib_dict[date_key] = str(contrib_dict[date_key])
                    result.append(contrib_dict)

                return result

        except Exception as e:
            logger.error(f"Error fetching contributions: {e}")
            return []
        finally:
            if conn:
                db_conn_pool.putconn(conn)
