"""
Test Error Handler Decorators

Tests for the standardized error handling decorators.
"""

import pytest
from core.error_handler_decorator import handle_errors, handle_validation_errors, log_errors
from core.error_handlers import ErrorCode, api_error
from fastapi import HTTPException


class TestHandleErrors:
    """Test suite for @handle_errors decorator"""

    def test_handle_basic_error(self):
        """Test basic error handling"""
        @handle_errors(error_code=ErrorCode.VALIDATION_ERROR)
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(HTTPException) as exc_info:
            failing_function()

        assert exc_info.value.status_code == 500
        assert "Test error" in str(exc_info.value.detail)

    def test_handle_with_reraise(self):
        """Test error handling with reraise=True"""
        @handle_errors(error_code=ErrorCode.INTERNAL_SERVER_ERROR, reraise=True)
        def failing_function():
            raise ValueError("Original error")

        with pytest.raises(ValueError) as exc_info:
            failing_function()

        assert str(exc_info.value) == "Original error"

    def test_handle_success_case(self):
        """Test that successful cases work normally"""
        @handle_errors()
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"


class TestHandleValidationErrors:
    """Test suite for @handle_validation_errors decorator"""

    def test_value_error_converted(self):
        """Test that ValueError is converted to validation error"""
        @handle_validation_errors
        def failing_function():
            raise ValueError("Invalid input")

        with pytest.raises(HTTPException) as exc_info:
            failing_function()

        assert exc_info.value.status_code == 400

    def test_type_error_converted(self):
        """Test that TypeError is converted to validation error"""
        @handle_validation_errors
        def failing_function():
            raise TypeError("Wrong type")

        with pytest.raises(HTTPException) as exc_info:
            failing_function()

        assert exc_info.value.status_code == 400

    def test_http_exception_passthrough(self):
        """Test that HTTPException passes through unchanged"""
        @handle_validation_errors
        def raise_http():
            raise api_error(ErrorCode.PERMISSION_DENIED, "Access denied", status_code=403)

        with pytest.raises(HTTPException) as exc_info:
            raise_http()

        assert exc_info.value.status_code == 403


class TestLogErrors:
    """Test suite for @log_errors decorator"""

    def test_logs_before_reraise(self, caplog):
        """Test that errors are logged before re-raising"""
        import logging

        @log_errors(level="ERROR")
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            with caplog.at_level(logging.ERROR):
                failing_function()

        assert "Test error" in caplog.text

    def test_reraises_exception(self):
        """Test that exception is re-raised"""
        @log_errors()
        def failing_function():
            raise ValueError("Original error")

        with pytest.raises(ValueError) as exc_info:
            failing_function()

        assert str(exc_info.value) == "Original error"


class TestErrorPropagation:
    """Test error propagation through decorated functions"""

    def test_error_context_preserved(self):
        """Test that error context is preserved"""
        @handle_errors(error_code=ErrorCode.AGENT_EXECUTION_FAILED)
        def multi_layer_function():
            def inner():
                raise RuntimeError("Inner error")
            inner()

        with pytest.raises(HTTPException):
            multi_layer_function()

    def test_async_error_handling(self):
        """Test error handling with async functions"""
        import asyncio

        @handle_errors(error_code=ErrorCode.INTERNAL_SERVER_ERROR)
        async def async_failing_function():
            raise ValueError("Async error")

        async def run_test():
            with pytest.raises(HTTPException):
                await async_failing_function()

        asyncio.run(run_test())
