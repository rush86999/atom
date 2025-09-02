"""
Compatibility utilities for Python 3.8+ and package dependencies.

This module provides fallback implementations and compatibility shims
for various Python dependencies that might not be available in all environments.
"""

import sys
import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Python version check
PYTHON_VERSION = sys.version_info
IS_PYTHON_3_8_OR_HIGHER = PYTHON_VERSION >= (3, 8)

def ensure_python_compat():
    """Ensure Python compatibility checks are met."""
    if not IS_PYTHON_3_8_OR_HIGHER:
        logger.warning(f"Running on Python {PYTHON_VERSION.major}.{PYTHON_VERSION.minor}. "
                       f"Recommended: Python 3.8+")
    return IS_PYTHON_3_8_OR_HIGHER

# Optional import handling with typing support
def safe_import(module_name: str, fallback: Any = None) -> Any:
    """Safely import a module with fallback."""
    try:
        return __import__(module_name)
    except ImportError:
        logger.warning(f"Module {module_name} not available, using fallback")
        return fallback

# Import mapping for common missing dependencies
_import_cache = {}

def get_import(name: str, default: Any = None) -> Any:
    """Get an import with caching and fallback."""
    if name in _import_cache:
        return _import_cache[name]

    try:
        parts = name.split('.')
        if len(parts) == 1:
            module = __import__(name)
        else:
            module = __import__('.'.join(parts[:-1]), fromlist=[parts[-1]])
            module = getattr(module, parts[-1])

        _import_cache[name] = module
        return module
    except (ImportError, AttributeError):
        logger.debug(f"Could not import {name}, using default")
        _import_cache[name] = default
        return default

# Common compatibility types
try:
    from typing import TypedDict, Protocol
except ImportError:
    # Fallback for Python < 3.8
    try:
        from typing_extensions import TypedDict, Protocol
    except ImportError:
        # Basic fallback
        TypedDict = dict
        Protocol = object

# Common mock implementations
class MockObject:
    """Generic mock object for missing dependencies."""
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return self

    def __getattr__(self, name):
        return self

class MockException(Exception):
    """Generic mock exception for missing dependencies."""
    pass

# Environment detection helpers
def is_production() -> bool:
    """Check if running in production environment."""
    return os.environ.get('ENVIRONMENT', 'development').lower() == 'production'

def is_development() -> bool:
    """Check if running in development environment."""
    return os.environ.get('ENVIRONMENT', 'development').lower() == 'development'

def ensure_dependencies():
    """Ensure basic dependencies are available."""
    requires = [
        'cryptography',
        'requests',
        'google-api-python-client',
        'tweepy'
    ]

    missing = []
    for req in requires:
        try:
            __import__(req)
        except ImportError:
            missing.append(req)

    if missing:
        logger.warning(f"Missing Python dependencies: {missing}")
        if is_production():
            raise ImportError(f"Required dependencies missing: {missing}")

    return len(missing) == 0

# Export commonly used utilities
__all__ = [
    'IS_PYTHON_3_8_OR_HIGHER',
    'ensure_python_compat',
    'safe_import',
    'get_import',
    'MockObject',
    'MockException',
    'TypedDict',
    'Protocol',
    'is_production',
    'is_development',
    'ensure_dependencies',
]

# Initialize compatibility on import
ensure_python_compat()
