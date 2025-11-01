"""
User Authentication API for ATOM Platform

This module provides REST API endpoints for user authentication and management
including registration, login, profile management, and password operations.
"""

import logging
from flask import Blueprint, request, jsonify
from typing import Dict, Any, Tuple
from user_auth_service import UserAuthService

logger = logging.getLogger(__name__)

# Create blueprint for user authentication routes
user_auth_bp = Blueprint("user_auth", __name__, url_prefix="/api/auth")


@user_auth_bp.route("/register", methods=["POST"])
def register_user():
    """
    Register a new user account
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: user
        description: User registration data
        schema:
          type: object
          required:
            - email
            - password
          properties:
            email:
              type: string
              format: email
              description: User email address
            password:
              type: string
              description: User password (min 6 characters)
            name:
              type: string
              description: User full name
    responses:
      201:
        description: User created successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            user:
              type: object
              properties:
                id:
                  type: string
                email:
                  type: string
                name:
                  type: string
      400:
        description: Invalid input or user already exists
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No JSON data provided"}), 400

        email = data.get("email")
        password = data.get("password")
        name = data.get("name")

        # Validate required fields
        if not email or not password:
            return jsonify(
                {"success": False, "message": "Email and password are required"}
            ), 400

        # Validate password length
        if len(password) < 6:
            return jsonify(
                {"success": False, "message": "Password must be at least 6 characters"}
            ), 400

        # Register user
        success, error_message, user_info = UserAuthService.create_user(
            email=email, password=password, name=name
        )

        if success:
            logger.info(f"User registered successfully: {email}")
            return jsonify(
                {
                    "success": True,
                    "message": "User registered successfully",
                    "user": user_info,
                }
            ), 201
        else:
            return jsonify({"success": False, "message": error_message}), 400

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify(
            {"success": False, "message": "Internal server error during registration"}
        ), 500


@user_auth_bp.route("/login", methods=["POST"])
def login_user():
    """
    Authenticate user and return JWT token
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: credentials
        description: User login credentials
        schema:
          type: object
          required:
            - email
            - password
          properties:
            email:
              type: string
              format: email
              description: User email address
            password:
              type: string
              description: User password
    responses:
      200:
        description: Login successful
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            user:
              type: object
              properties:
                id:
                  type: string
                email:
                  type: string
                name:
                  type: string
                token:
                  type: string
      401:
        description: Invalid credentials
      400:
        description: Missing required fields
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No JSON data provided"}), 400

        email = data.get("email")
        password = data.get("password")

        # Validate required fields
        if not email or not password:
            return jsonify(
                {"success": False, "message": "Email and password are required"}
            ), 400

        # Authenticate user
        success, error_message, user_info = UserAuthService.authenticate_user(
            email=email, password=password
        )

        if success:
            logger.info(f"User logged in successfully: {email}")
            return jsonify(
                {"success": True, "message": "Login successful", "user": user_info}
            ), 200
        else:
            return jsonify({"success": False, "message": error_message}), 401

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify(
            {"success": False, "message": "Internal server error during login"}
        ), 500


@user_auth_bp.route("/profile", methods=["GET"])
def get_user_profile():
    """
    Get user profile information
    ---
    tags:
      - User Management
    parameters:
      - in: header
        name: Authorization
        description: JWT token (Bearer token)
        required: true
        type: string
    responses:
      200:
        description: Profile retrieved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            user:
              type: object
              properties:
                id:
                  type: string
                email:
                  type: string
                name:
                  type: string
                created_date:
                  type: string
                updated_at:
                  type: string
      401:
        description: Unauthorized - invalid or missing token
      404:
        description: User not found
      500:
        description: Internal server error
    """
    try:
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify(
                {"success": False, "message": "Authorization token required"}
            ), 401

        token = auth_header.split(" ")[1]

        # Verify token
        payload = UserAuthService.verify_jwt_token(token)
        if not payload:
            return jsonify(
                {"success": False, "message": "Invalid or expired token"}
            ), 401

        user_id = payload.get("user_id")

        # Get user profile
        user = UserAuthService.get_user_by_id(user_id)
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404

        return jsonify(
            {
                "success": True,
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "name": user["name"],
                    "created_date": user["createdDate"].isoformat()
                    if user.get("createdDate")
                    else None,
                    "updated_at": user["updatedAt"].isoformat()
                    if user.get("updatedAt")
                    else None,
                },
            }
        ), 200

    except Exception as e:
        logger.error(f"Profile retrieval error: {str(e)}")
        return jsonify(
            {"success": False, "message": "Internal server error retrieving profile"}
        ), 500


@user_auth_bp.route("/profile", methods=["PUT"])
def update_user_profile():
    """
    Update user profile information
    ---
    tags:
      - User Management
    parameters:
      - in: header
        name: Authorization
        description: JWT token (Bearer token)
        required: true
        type: string
      - in: body
        name: profile
        description: Profile update data
        schema:
          type: object
          properties:
            name:
              type: string
              description: User full name
            email:
              type: string
              format: email
              description: User email address
    responses:
      200:
        description: Profile updated successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
      400:
        description: Bad request - validation error
      401:
        description: Unauthorized - invalid or missing token
      409:
        description: Conflict - email already taken
      500:
        description: Internal server error
    """
    try:
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify(
                {"success": False, "message": "Authorization token required"}
            ), 401

        token = auth_header.split(" ")[1]

        # Verify token
        payload = UserAuthService.verify_jwt_token(token)
        if not payload:
            return jsonify(
                {"success": False, "message": "Invalid or expired token"}
            ), 401

        user_id = payload.get("user_id")
        data = request.get_json()

        if not data:
            return jsonify(
                {"success": False, "message": "No data provided for update"}
            ), 400

        name = data.get("name")
        email = data.get("email")

        # Update profile
        success, error_message = UserAuthService.update_user_profile(
            user_id=user_id, name=name, email=email
        )

        if success:
            logger.info(f"Profile updated successfully for user: {user_id}")
            return jsonify(
                {"success": True, "message": "Profile updated successfully"}
            ), 200
        else:
            status_code = 409 if "already taken" in error_message else 400
            return jsonify({"success": False, "message": error_message}), status_code

    except Exception as e:
        logger.error(f"Profile update error: {str(e)}")
        return jsonify(
            {"success": False, "message": "Internal server error updating profile"}
        ), 500


@user_auth_bp.route("/change-password", methods=["POST"])
def change_password():
    """
    Change user password
    ---
    tags:
      - User Management
    parameters:
      - in: header
        name: Authorization
        description: JWT token (Bearer token)
        required: true
        type: string
      - in: body
        name: passwords
        description: Password change data
        schema:
          type: object
          required:
            - current_password
            - new_password
          properties:
            current_password:
              type: string
              description: Current password
            new_password:
              type: string
              description: New password (min 6 characters)
    responses:
      200:
        description: Password changed successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
      400:
        description: Bad request - validation error
      401:
        description: Unauthorized - invalid credentials or token
      500:
        description: Internal server error
    """
    try:
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify(
                {"success": False, "message": "Authorization token required"}
            ), 401

        token = auth_header.split(" ")[1]

        # Verify token
        payload = UserAuthService.verify_jwt_token(token)
        if not payload:
            return jsonify(
                {"success": False, "message": "Invalid or expired token"}
            ), 401

        user_id = payload.get("user_id")
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "message": "No JSON data provided"}), 400

        current_password = data.get("current_password")
        new_password = data.get("new_password")

        # Validate required fields
        if not current_password or not new_password:
            return jsonify(
                {
                    "success": False,
                    "message": "Current password and new password are required",
                }
            ), 400

        # Change password
        success, error_message = UserAuthService.change_password(
            user_id=user_id,
            current_password=current_password,
            new_password=new_password,
        )

        if success:
            logger.info(f"Password changed successfully for user: {user_id}")
            return jsonify(
                {"success": True, "message": "Password changed successfully"}
            ), 200
        else:
            return jsonify({"success": False, "message": error_message}), 401

    except Exception as e:
        logger.error(f"Password change error: {str(e)}")
        return jsonify(
            {"success": False, "message": "Internal server error changing password"}
        ), 500


@user_auth_bp.route("/verify-token", methods=["POST"])
def verify_token():
    """
    Verify JWT token validity
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: token
        description: JWT token to verify
        schema:
          type: object
          required:
            - token
          properties:
            token:
              type: string
              description: JWT token to verify
    responses:
      200:
        description: Token is valid
        schema:
          type: object
          properties:
            success:
              type: boolean
            valid:
              type: boolean
            user_id:
              type: string
            email:
              type: string
      400:
        description: Bad request - token not provided
      401:
        description: Token is invalid or expired
    """
    try:
        data = request.get_json()

        if not data or not data.get("token"):
            return jsonify({"success": False, "message": "Token is required"}), 400

        token = data.get("token")

        # Verify token
        payload = UserAuthService.verify_jwt_token(token)
        if payload:
            return jsonify(
                {
                    "success": True,
                    "valid": True,
                    "user_id": payload.get("user_id"),
                    "email": payload.get("email"),
                }
            ), 200
        else:
            return jsonify(
                {
                    "success": True,
                    "valid": False,
                    "message": "Token is invalid or expired",
                }
            ), 401

    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return jsonify(
            {"success": False, "message": "Internal server error verifying token"}
        ), 500


@user_auth_bp.route("/health", methods=["GET"])
def auth_health():
    """
    Authentication service health check
    ---
    tags:
      - Health
    responses:
      200:
        description: Service is healthy
        schema:
          type: object
          properties:
            success:
              type: boolean
            service:
              type: string
            status:
              type: string
            timestamp:
              type: string
    """
    return jsonify(
        {
            "success": True,
            "service": "user_auth_api",
            "status": "healthy",
            "timestamp": "2025-10-31T09:00:00Z",
        }
    ), 200
