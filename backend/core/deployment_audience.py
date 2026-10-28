"""Deployment audience guard.

The expanded core is accepted for a single-user pilot only. Multi-user use
requires per-file authorization on the direct office file-path APIs; that work
is explicitly outside this release. This module makes the boundary executable:

- ``development`` (default): existing dev/test behaviour, no gate.
- ``single_user``: only the declared pilot account may use canvas/office
  surfaces; self-registration is refused; direct office file access remains a
  documented shared namespace owned by that one account.
- ``multi_user``: fail closed until per-file authorization exists.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import Depends, HTTPException

from core.auth import get_current_user


def deployment_audience() -> str:
    return str(os.getenv("ATOM_DEPLOYMENT_AUDIENCE", "development") or "development").strip().lower()


def is_single_user() -> bool:
    return deployment_audience() == "single_user"


def pilot_email() -> str:
    return str(os.getenv("ATOM_PILOT_USER_EMAIL", "") or "").strip().lower()


def validate_audience_config() -> None:
    """Fail closed on an undeclared or unsupported deployment audience."""
    audience = deployment_audience()
    if audience == "multi_user":
        raise RuntimeError(
            "ATOM_DEPLOYMENT_AUDIENCE=multi_user is refused: direct office "
            "file-path authorization (wrong-owner/workspace negative controls) "
            "is not implemented in this release. Use single_user or stay in "
            "development."
        )
    if audience == "single_user" and not pilot_email():
        raise RuntimeError(
            "ATOM_DEPLOYMENT_AUDIENCE=single_user requires "
            "ATOM_PILOT_USER_EMAIL so the shared office namespace has one owner."
        )


def require_pilot_user(user: Any = Depends(get_current_user)) -> Any:
    """FastAPI dependency: in a single-user pilot, only the declared account."""
    if not is_single_user():
        return user
    expected = pilot_email()
    actual = str(getattr(user, "email", "") or "").strip().lower()
    if not expected or actual != expected:
        raise HTTPException(
            status_code=403,
            detail="This deployment is a single-user pilot; the signed-in account is not the declared pilot owner.",
        )
    return user
