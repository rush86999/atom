"""
Error Handler Decorator for Atom Platform

Provides standardized error handling decorators for API routes and services.
This ensures consistent error responses and logging across the entire codebase.
"""

import functools
import logging
from typing import Any, Callable, Optional, Type, Union
from fastapi import HTTPException
from core.error_handlers import ErrorCode, api_error

logger = logging.getLogger(__name__)


def handle_errors(
    error_code: ErrorCode = ErrorCode.INTERNAL_SERVER_ERROR,
    reraise: bool = False,
    default_message: str = "An error occurred"
):
    """
    Decorator for standardized error handling in functions.

    Args:
        error_code: Default error code to use for unhandled exceptions
        reraise: If True, re-raises the exception after logging
        default_message: Default error message for unhandled exceptions

    Example:
        @handle_errors(error_code=ErrorCode.AGENT_EXECUTION_FAILED)
        async def execute_agent(agent_id: str, db: Session):
            agent = db.query(AgentRegistry).filter_by(id=agent_id).first()
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")
            return agent.execute()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                # Re-raise HTTPException as-is (already formatted)
                raise
            except Exception as e:
                logger.error(
                    f"Error in {func.__name__}: {str(e)}",
                    extra={"function": func.__name__, "error_type": type(e).__name__},
                    exc_info=True
                )
                if reraise:
                    raise
                raise api_error(error_code, str(e))

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except HTTPException:
                # Re-raise HTTPException as-is (already formatted)
                raise
            except Exception as e:
                logger.error(
                    f"Error in {func.__name__}: {str(e)}",
                    extra={"function": func.__name__, "error_type": type(e).__name__},
                    exc_info=True
                )
                if reraise:
                    raise
                raise api_error(error_code, str(e))

        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def handle_validation_errors(func: Callable) -> Callable:
    """
    Decorator specifically for handling validation errors.

    Catches ValueError, TypeError, and ValidationError exceptions
    and converts them to standardized validation error responses.

    Example:
        @handle_validation_errors
        async def create_agent(agent_data: AgentCreate, db: Session):
            if not agent_data.name:
                raise ValueError("Agent name is required")
            return create_agent(db, agent_data)
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except (ValueError, TypeError) as e:
            # Convert ValueError and TypeError to validation errors
            raise api_error(
                ErrorCode.VALIDATION_ERROR,
                str(e),
                status_code=400
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in {func.__name__}: {str(e)}",
                extra={"function": func.__name__},
                exc_info=True
            )
            raise api_error(
                ErrorCode.INTERNAL_SERVER_ERROR,
                "An unexpected error occurred"
            )

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ValueError, TypeError) as e:
            # Convert ValueError and TypeError to validation errors
            raise api_error(
                ErrorCode.VALIDATION_ERROR,
                str(e),
                status_code=400
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in {func.__name__}: {str(e)}",
                extra={"function": func.__name__},
                exc_info=True
            )
            raise api_error(
                ErrorCode.INTERNAL_SERVER_ERROR,
                "An unexpected error occurred"
            )

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def handle_database_errors(
    default_message: str = "Database operation failed",
    reraise: bool = False
):
    """
    Decorator for handling database-specific errors.

    Args:
        default_message: Default error message for database failures
        reraise: If True, re-raises the exception after logging

    Example:
        @handle_database_errors(default_message="Failed to fetch agent")
        async def get_agent(agent_id: str, db: Session):
            return db.query(AgentRegistry).filter_by(id=agent_id).first()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                error_msg = str(e)
                # Check for common database error patterns
                if "unique constraint" in error_msg.lower() or "duplicate" in error_msg.lower():
                    logger.error(f"Database unique constraint violation in {func.__name__}: {error_msg}")
                    raise api_error(
                        ErrorCode.RESOURCE_ALREADY_EXISTS,
                        "Resource already exists",
                        details={"original_error": error_msg},
                        status_code=409
                    )
                elif "foreign key" in error_msg.lower():
                    logger.error(f"Database foreign key violation in {func.__name__}: {error_msg}")
                    raise api_error(
                        ErrorCode.VALIDATION_ERROR,
                        "Referenced resource does not exist",
                        details={"original_error": error_msg},
                        status_code=400
                    )
                elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                    logger.error(f"Database connection error in {func.__name__}: {error_msg}")
                    raise api_error(
                        ErrorCode.DATABASE_ERROR,
                        "Database connection failed",
                        status_code=503
                    )
                else:
                    # Generic database error
                    logger.error(
                        f"Database error in {func.__name__}: {error_msg}",
                        exc_info=True
                    )
                    if reraise:
                        raise
                    raise api_error(
                        ErrorCode.DATABASE_ERROR,
                        default_message,
                        details={"original_error": error_msg} if logger.level <= logging.DEBUG else None
                    )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                error_msg = str(e)
                # Check for common database error patterns
                if "unique constraint" in error_msg.lower() or "duplicate" in error_msg.lower():
                    logger.error(f"Database unique constraint violation in {func.__name__}: {error_msg}")
                    raise api_error(
                        ErrorCode.RESOURCE_ALREADY_EXISTS,
                        "Resource already exists",
                        details={"original_error": error_msg},
                        status_code=409
                    )
                elif "foreign key" in error_msg.lower():
                    logger.error(f"Database foreign key violation in {func.__name__}: {error_msg}")
                    raise api_error(
                        ErrorCode.VALIDATION_ERROR,
                        "Referenced resource does not exist",
                        details={"original_error": error_msg},
                        status_code=400
                    )
                elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                    logger.error(f"Database connection error in {func.__name__}: {error_msg}")
                    raise api_error(
                        ErrorCode.DATABASE_ERROR,
                        "Database connection failed",
                        status_code=503
                    )
                else:
                    # Generic database error
                    logger.error(
                        f"Database error in {func.__name__}: {error_msg}",
                        exc_info=True
                    )
                    if reraise:
                        raise
                    raise api_error(
                        ErrorCode.DATABASE_ERROR,
                        default_message,
                        details={"original_error": error_msg} if logger.level <= logging.DEBUG else None
                    )

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def log_errors(func: Optional[Callable] = None, *, level: str = "ERROR") -> Callable:
    """
    Decorator that logs all exceptions before re-raising them.

    Args:
        func: Function to decorate (if used without arguments)
        level: Log level ("ERROR", "WARNING", "INFO", "DEBUG")

    Example:
        @log_errors
        def my_function():
            pass

        @log_errors(level="WARNING")
        def my_other_function():
            pass
    """
    def decorator(f: Callable) -> Callable:
        log_func = getattr(logger, level.lower(), logger.error)

        @functools.wraps(f)
        async def async_wrapper(*args, **kwargs):
            try:
                return await f(*args, **kwargs)
            except Exception as e:
                log_func(
                    f"Exception in {f.__name__}: {str(e)}",
                    extra={"function": f.__name__, "error_type": type(e).__name__},
                    exc_info=True
                )
                raise

        @functools.wraps(f)
        def sync_wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                log_func(
                    f"Exception in {f.__name__}: {str(e)}",
                    extra={"function": f.__name__, "error_type": type(e).__name__},
                    exc_info=True
                )
                raise

        if asyncio.iscoroutinefunction(f):
            return async_wrapper
        return sync_wrapper

    if func is not None:
        # Called as @log_errors without arguments
        return decorator(func)
    return decorator


# Import asyncio at module level for iscoroutinefunction check
import asyncio
