from __future__ import annotations
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from core.error_handlers import (
    global_exception_handler,
    atom_exception_handler,
)

logger = logging.getLogger(__name__)

# Try to import AtomException hierarchy for unified error handling
try:
    from core.exceptions import AtomException
except ImportError:
    AtomException = None

try:
    from core.exceptions import APIError
except ImportError:
    APIError = None


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    # Ensure detail is always JSON-serializable
    if isinstance(exc.detail, dict):
        content = exc.detail
    else:
        content = {"detail": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=content)


async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    logger.error(f"Database error occurred: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error_code": "DATABASE_ERROR",
            "message": "A database error occurred",
            "request_id": request_id,
        }
    )


async def api_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) if hasattr(request, "state") else None
    message = getattr(exc, "message", str(exc))
    error_code = getattr(exc, "error_code", "API_ERROR")
    status_code = getattr(exc, "status_code", 500)
    details = getattr(exc, "details", None)
    
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error_code": str(error_code),
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return await global_exception_handler(request, exc)


def setup_error_handlers(app: FastAPI):
    """
    Setup all error handlers for a FastAPI app.
    Call this in main_api_app.py after creating the FastAPI app.
    """
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(SQLAlchemyError, database_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)
    
    if AtomException is not None:
        app.add_exception_handler(AtomException, atom_exception_handler)
        
    if APIError is not None:
        app.add_exception_handler(APIError, api_error_handler)
