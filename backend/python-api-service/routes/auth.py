"""
Authentication API routes
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from ..models import db, User
from ..utils import generate_uuid, validate_user_data
from datetime import datetime
import logging

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        if not data or not data.get('email') or not data.get('password') or not data.get('name'):
            return jsonify({'error': 'Email, password, and name are required'}), 400

        # Check if user already exists
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user:
            return jsonify({'error': 'User with this email already exists'}), 409

        # Validate user data
        validation_error = validate_user_data(data)
        if validation_error:
            return jsonify({'error': validation_error}), 400

        # Create new user
        user = User(
            id=generate_uuid(),
            email=data['email'],
            name=data['name'],
            preferences=data.get('preferences', {}),
            advanced_settings=data.get('advanced_settings', {})
        )
        user.set_password(data['password'])

        db.session.add(user)
        db.session.commit()

        # Create access token
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)

        logger.info(f'User registered: {user.id} - {user.email}')
        return jsonify({
            'message': 'User registered successfully',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error registering user: {str(e)}')
        return jsonify({'error': 'Failed to register user'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return tokens"""
    try:
        data = request.get_json()
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password are required'}), 400

        # Find user
        user = User.query.filter_by(email=data['email']).first()
        if not user or not user.check_password(data['password']):
            return jsonify({'error': 'Invalid email or password'}), 401

        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 401

        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()

        # Create tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)

        logger.info(f'User logged in: {user.id} - {user.email}')
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        })
    except Exception as e:
        logger.error(f'Error logging in user: {str(e)}')
        return jsonify({'error': 'Failed to login'}), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    try:
        current_user_id = get_jwt_identity()
        access_token = create_access_token(identity=current_user_id)

        logger.info(f'Token refreshed for user: {current_user_id}')
        return jsonify({
            'access_token': access_token
        })
    except Exception as e:
        logger.error(f'Error refreshing token: {str(e)}')
        return jsonify({'error': 'Failed to refresh token'}), 500

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify(user.to_dict())
    except Exception as e:
        logger.error(f'Error fetching profile for user {get_jwt_identity()}: {str(e)}')
        return jsonify({'error': 'Failed to fetch profile'}), 500

@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate user data
        validation_error = validate_user_data(data, partial=True)
        if validation_error:
            return jsonify({'error': validation_error}), 400

        # Update user fields
        for field in ['name', 'preferences', 'advanced_settings']:
            if field in data:
                setattr(user, field, data[field])

        # Handle password change
        if 'password' in data:
            user.set_password(data['password'])

        db.session.commit()

        logger.info(f'Profile updated for user: {user_id}')
        return jsonify(user.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error updating profile for user {user_id}: {str(e)}')
        return jsonify({'error': 'Failed to update profile'}), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user (client should discard tokens)"""
    try:
        user_id = get_jwt_identity()
        logger.info(f'User logged out: {user_id}')
        return jsonify({'message': 'Logged out successfully'})
    except Exception as e:
        logger.error(f'Error logging out user {get_jwt_identity()}: {str(e)}')
        return jsonify({'error': 'Failed to logout'}), 500

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()
        if not data or not data.get('current_password') or not data.get('new_password'):
            return jsonify({'error': 'Current password and new password are required'}), 400

        # Verify current password
        if not user.check_password(data['current_password']):
            return jsonify({'error': 'Current password is incorrect'}), 401

        # Update password
        user.set_password(data['new_password'])
        db.session.commit()

        logger.info(f'Password changed for user: {user_id}')
        return jsonify({'message': 'Password changed successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error changing password for user {user_id}: {str(e)}')
        return jsonify({'error': 'Failed to change password'}), 500

@auth_bp.route('/deactivate', methods=['POST'])
@jwt_required()
def deactivate_account():
    """Deactivate user account"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        user.is_active = False
        db.session.commit()

        logger.info(f'Account deactivated: {user_id}')
        return jsonify({'message': 'Account deactivated successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deactivating account {user_id}: {str(e)}')
        return jsonify({'error': 'Failed to deactivate account'}), 500
