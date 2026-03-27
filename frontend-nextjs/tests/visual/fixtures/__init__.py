"""
Percy visual regression testing fixtures package.

This package provides pytest fixtures for Percy visual regression testing.
"""

from .percy_fixtures import (
    percy_snapshot,
    percy_page,
    authenticated_percy_page,
    percy_test_data,
    perci_token,
    verify_percy_setup
)

__all__ = [
    "percy_snapshot",
    "percy_page",
    "authenticated_percy_page",
    "percy_test_data",
    "perci_token",
    "verify_percy_setup"
]
