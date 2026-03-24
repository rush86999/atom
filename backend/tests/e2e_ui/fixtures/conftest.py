"""
Fixtures conftest.py - Register all fixtures from this directory.

This file ensures pytest discovers all fixtures in the fixtures directory.
"""

# Import all fixture modules to register them with pytest
from . import database_fixtures
from . import auth_fixtures
from . import api_fixtures
from . import test_data_factory
from . import network_fixtures

__all__ = ['database_fixtures', 'auth_fixtures', 'api_fixtures', 'test_data_factory', 'network_fixtures']
