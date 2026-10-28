"""Public product-surface contract for the frontend.

The sidebar, dashboard links and direct-page guard all read this one
document, so navigation and access agree with the capability configuration
in ``core.product_profile``. It contains no secrets and no user data.
"""
from __future__ import annotations

from fastapi import APIRouter

from core.product_profile import profile_document

router = APIRouter(prefix="/api/product", tags=["Product Profile"])


@router.get("/profile")
async def get_product_profile():
    return profile_document()
