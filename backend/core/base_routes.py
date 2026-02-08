"""
Base API Router with Standardized Error Handling and Response Formats

Provides a consistent API response structure across all Atom routes.
This enforces proper error handling, logging, and governance integration.

Usage:
    from core.base_routes import BaseAPIRouter

    router = BaseAPIRouter(prefix="/api/canvas", tags=["canvas"])

    @router.post("/submit")
    async def submit_form(submission: FormSubmission, db: Session = Depends(get_db)):
        if not agent:
            raise router.not_found_error("Agent", submission.agent_id)

        if not governance_check.allowed:
            raise router.permission_denied_error("submit_form", "agent")

        return router.success_response(
            data={"submission_id": submission.id},
            message="Form submitted successfully"
        )
"""

from datetime import datetime
import logging
import os
import traceback
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class BaseAPIRouter(APIRouter):
    """
    Base router with standardized error handling and response formats.

    Enforces consistent JSON structure across all API endpoints:
    {
        "success": true/false,
        "data": {...},
        "message": "User-friendly message",
        "error": {...},  # Only present on errors
        "metadata": {...}  # Optional pagination, timing info
    }
    """

    def __init__(self, *args, **kwargs):
        """Initialize the base router with standard APIRouter args"""
        super().__init__(*args, **kwargs)
        self._debug_mode = os.getenv("DEBUG", "False").lower() == "true"

    # ========================================================================
    # Success Response Methods
    # ========================================================================

    def success_response(
        self,
        data: Any = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status_code: int = status.HTTP_200_OK
    ) -> Dict[str, Any]:
        """
        Create a standardized success response.

        Args:
            data: Response data (any JSON-serializable type)
            message: Optional success message
            metadata: Optional metadata (pagination, timing, etc.)
            status_code: HTTP status code (default: 200)

        Returns:
            Dictionary with consistent success structure

        Example:
            return router.success_response(
                data={"user_id": "123", "name": "John"},
                message="User created successfully",
                metadata={"version": "v1.0"}
            )
        """
        response = {
            "success": True,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if message:
            response["message"] = message

        if metadata:
            response["metadata"] = metadata

        return response

    def success_list_response(
        self,
        items: List[Any],
        total: Optional[int] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a standardized success response for list endpoints.

        Args:
            items: List of items
            total: Total count (for pagination)
            page: Current page number
            page_size: Number of items per page
            message: Optional success message

        Returns:
            Dictionary with list-specific structure

        Example:
            return router.success_list_response(
                items=[user1, user2],
                total=100,
                page=1,
                page_size=20
            )
        """
        metadata = {}
        if total is not None:
            metadata["total"] = total
        if page is not None:
            metadata["page"] = page
        if page_size is not None:
            metadata["page_size"] = page_size

        return self.success_response(
            data=items,
            message=message or f"Retrieved {len(items)} items",
            metadata=metadata if metadata else None
        )

    # ========================================================================
    # Error Response Methods (return HTTPException)
    # ========================================================================

    def error_response(
        self,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST
    ) -> HTTPException:
        """
        Create a standardized error response as HTTPException.

        Args:
            error_code: Application-specific error code (e.g., "USER_NOT_FOUND")
            message: Human-readable error message
            details: Additional error context
            status_code: HTTP status code

        Returns:
            HTTPException with structured error body

        Example:
            raise router.error_response(
                error_code="USER_NOT_FOUND",
                message="User not found",
                details={"user_id": "123"},
                status_code=404
            )
        """
        error_body = {
            "success": False,
            "error": {
                "code": error_code,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
            }
        }

        if details:
            error_body["error"]["details"] = details

        # Include stack trace in debug mode
        if self._debug_mode:
            error_body["error"]["stack_trace"] = traceback.format_stack()

        logger.warning(
            f"API Error: {error_code} - {message}",
            extra={"error_code": error_code, "details": details}
        )

        return HTTPException(
            status_code=status_code,
            detail=error_body
        )

    def validation_error(
        self,
        field: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> HTTPException:
        """
        Convenience method for validation errors.

        Args:
            field: Field name that failed validation
            message: Validation error message
            details: Additional context

        Returns:
            HTTPException with 400 status code

        Example:
            raise router.validation_error(
                field="email",
                message="Invalid email format",
                details={"provided": "invalid-email"}
            )
        """
        error_details = {"field": field}
        if details:
            error_details.update(details)

        return self.error_response(
            error_code="VALIDATION_ERROR",
            message=message,
            details=error_details,
            status_code=status.HTTP_400_BAD_REQUEST
        )

    def not_found_error(
        self,
        resource: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> HTTPException:
        """
        Convenience method for not found errors.

        Args:
            resource: Resource type (e.g., "Agent", "User", "Canvas")
            resource_id: Optional resource identifier
            details: Additional context

        Returns:
            HTTPException with 404 status code

        Example:
            raise router.not_found_error("Agent", agent_id)
        """
        message = f"{resource} not found"
        if resource_id:
            message += f": {resource_id}"

        error_details = {"resource": resource}
        if resource_id:
            error_details["resource_id"] = resource_id
        if details:
            error_details.update(details)

        return self.error_response(
            error_code="NOT_FOUND",
            message=message,
            details=error_details,
            status_code=status.HTTP_404_NOT_FOUND
        )

    def permission_denied_error(
        self,
        action: str,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> HTTPException:
        """
        Convenience method for permission errors.

        Args:
            action: Action that was denied (e.g., "delete_agent")
            resource: Optional resource type
            details: Additional context (e.g., required_permission)

        Returns:
            HTTPException with 403 status code

        Example:
            raise router.permission_denied_error(
                action="delete_agent",
                resource="Agent",
                details={"required_maturity": "AUTONOMOUS", "actual_maturity": "STUDENT"}
            )
        """
        message = f"Permission denied: {action}"
        if resource:
            message += f" on {resource}"

        error_details = {"action": action}
        if resource:
            error_details["resource"] = resource
        if details:
            error_details.update(details)

        return self.error_response(
            error_code="PERMISSION_DENIED",
            message=message,
            details=error_details,
            status_code=status.HTTP_403_FORBIDDEN
        )

    def unauthorized_error(
        self,
        message: str = "Authentication required",
        details: Optional[Dict[str, Any]] = None
    ) -> HTTPException:
        """
        Convenience method for unauthorized errors.

        Args:
            message: Error message
            details: Additional context

        Returns:
            HTTPException with 401 status code
        """
        return self.error_response(
            error_code="UNAUTHORIZED",
            message=message,
            details=details,
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    def conflict_error(
        self,
        message: str,
        conflicting_resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> HTTPException:
        """
        Convenience method for conflict errors.

        Args:
            message: Error message
            conflicting_resource: Optional conflicting resource identifier
            details: Additional context

        Returns:
            HTTPException with 409 status code
        """
        error_details = {}
        if conflicting_resource:
            error_details["conflicting_resource"] = conflicting_resource
        if details:
            error_details.update(details)

        return self.error_response(
            error_code="CONFLICT",
            message=message,
            details=error_details if error_details else None,
            status_code=status.HTTP_409_CONFLICT
        )

    def rate_limit_error(
        self,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> HTTPException:
        """
        Convenience method for rate limit errors.

        Args:
            retry_after: Seconds until retry is allowed
            details: Additional context

        Returns:
            HTTPException with 429 status code
        """
        error_details = {}
        if retry_after:
            error_details["retry_after"] = retry_after
        if details:
            error_details.update(details)

        return self.error_response(
            error_code="RATE_LIMIT_EXCEEDED",
            message="Rate limit exceeded",
            details=error_details if error_details else None,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )

    def internal_error(
        self,
        message: str = "An internal error occurred",
        details: Optional[Dict[str, Any]] = None
    ) -> HTTPException:
        """
        Convenience method for internal server errors.

        Args:
            message: Error message
            details: Additional context

        Returns:
            HTTPException with 500 status code
        """
        return self.error_response(
            error_code="INTERNAL_ERROR",
            message=message,
            details=details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # ========================================================================
    # Governance Integration
    # ========================================================================

    def governance_denied_error(
        self,
        agent_id: str,
        action: str,
        maturity_level: str,
        required_level: str,
        reason: Optional[str] = None
    ) -> HTTPException:
        """
        Convenience method for governance denial errors.

        Args:
            agent_id: Agent identifier
            action: Action that was denied
            maturity_level: Agent's current maturity level
            required_level: Required maturity level
            reason: Optional reason for denial

        Returns:
            HTTPException with 403 status code
        """
        message = f"Agent {agent_id} (maturity: {maturity_level}) cannot perform action: {action}"
        if reason:
            message += f" - {reason}"

        return self.permission_denied_error(
            action=action,
            resource="Agent",
            details={
                "agent_id": agent_id,
                "maturity_level": maturity_level,
                "required_maturity": required_level,
                "reason": reason or f"Requires {required_level} maturity level"
            }
        )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def log_api_call(
        self,
        endpoint: str,
        method: str,
        user_id: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ):
        """
        Log API call for analytics and auditing.

        Args:
            endpoint: Endpoint path
            method: HTTP method
            user_id: Optional user identifier
            extra_data: Additional data to log
        """
        log_data = {
            "endpoint": endpoint,
            "method": method,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if user_id:
            log_data["user_id"] = user_id
        if extra_data:
            log_data.update(extra_data)

        logger.info(f"API Call: {method} {endpoint}", extra=log_data)


# ========================================================================
# Exception Handler for Integration with FastAPI
# ========================================================================

async def atom_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Global exception handler for Atom API.

    Converts HTTPException to standardized JSON response.
    """
    # Extract error detail from exception
    detail = exc.detail

    # Handle both string and dict details
    if isinstance(detail, dict):
        # Already in our format
        return JSONResponse(
            status_code=exc.status_code,
            content=detail
        )
    else:
        # Legacy format - convert to standard format
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": "HTTP_ERROR",
                    "message": str(detail),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler for unexpected exceptions.

    Logs the full error and returns a generic error message.
    """
    logger.error(
        f"Unhandled exception at {request.url}: {exc}",
        exc_info=True,
        extra={"path": str(request.url.path), "method": request.method}
    )

    # In debug mode, include full error details
    debug_mode = os.getenv("DEBUG", "False").lower() == "true"

    error_content = {
        "success": False,
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An internal error occurred" if not debug_mode else str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
    }

    if debug_mode:
        error_content["error"]["type"] = type(exc).__name__
        error_content["error"]["stack_trace"] = traceback.format_exc()

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_content
    )


# ============================================================================
# Database Operation Utilities
# ============================================================================

def safe_db_operation(operation: callable, error_message: str = "Database operation failed"):
    """
    Decorator for safe database operations with automatic error handling and rollback.

    Args:
        operation: The database operation function to wrap
        error_message: Custom error message for failures

    Returns:
        Result of the operation or raises HTTPException on failure

    Example:
        @safe_db_operation
        def update_agent(agent_id: str, **kwargs):
            with get_db_session() as db:
                agent = db.query(AgentRegistry).filter(...).first()
                agent.name = kwargs.get("name")
                db.commit()
                return agent
    """
    def wrapper(*args, **kwargs):
        from core.database import get_db_session
        import logging

        logger = logging.getLogger(__name__)

        try:
            with get_db_session() as db:
                # Inject db session if operation expects it
                if 'db' in operation.__code__.co_varnames:
                    kwargs['db'] = db

                result = operation(*args, **kwargs)
                return result

        except Exception as e:
            logger.error(f"{error_message}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "error": {
                        "code": "DATABASE_ERROR",
                        "message": error_message,
                        "details": str(e) if os.getenv("DEBUG") else None
                    }
                }
            )

    return wrapper


def execute_db_query(
    query_func: callable,
    error_message: str = "Query execution failed",
    return_value: Any = None
) -> Any:
    """
    Execute a database query with proper error handling and context management.

    Args:
        query_func: Function that executes the query (receives db session)
        error_message: Custom error message
        return_value: Default return value on failure (if not raising exception)

    Returns:
        Query result or default value

    Example:
        def get_agent(db, agent_id):
            return db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()

        agent = execute_db_query(lambda db: get_agent(db, agent_id))
    """
    from core.database import get_db_session
    import logging

    logger = logging.getLogger(__name__)

    try:
        with get_db_session() as db:
            return query_func(db)

    except Exception as e:
        logger.error(f"{error_message}: {e}")
        if return_value is not None:
            return return_value
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": error_message
                }
            }
        )

