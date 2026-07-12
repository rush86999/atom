"""
Process-wide singleton registry for the LearningBasedRouter.

The learning router holds in-memory state (per-model predictors, cached
weights, pending decisions) that MUST persist across requests for the system
to actually learn. Previously, each call to ``_get_learning_router``
constructed a throwaway instance — predictors were trained and immediately
garbage-collected, so the learning engine was inert.

This module provides a single shared instance, lazily built on first access,
hydrated from the DB and from persisted per-model predictor ``.pkl`` files on
init. Thread-safe via a lock (the app is async, but uvicorn workers share
state within a process).
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_SINGLETON: Optional["object"] = None  # LearningBasedRouter, typed loosely to avoid import cycle


def learning_router_enabled() -> bool:
    """Whether the learning router is enabled (flag-gated, default off)."""
    return os.getenv("ATOM_LEARNING_ROUTER", "false").lower() == "true"


def get_learning_router_instance():
    """Return the process-wide LearningBasedRouter singleton.

    Returns ``None`` when the learning router is disabled or instantiation
    fails. On first successful call, instantiates the router, hydrates
    ``_preference_data`` from the DB, and restores any persisted per-model
    predictors from disk. Subsequent calls return the same object.
    """
    global _SINGLETON
    if not learning_router_enabled():
        return None
    if _SINGLETON is not None:
        return _SINGLETON

    with _LOCK:
        # Double-checked locking: another thread may have built it.
        if _SINGLETON is not None:
            return _SINGLETON
        try:
            from core.learning_llm_router import get_learning_router
            from core.database import SessionLocal

            db = SessionLocal()
            router = get_learning_router(db)

            # Hydrate preference data from the DB so learned data survives restarts.
            try:
                loaded = router.load_feedback_from_db()
                logger.info(f"Learning router hydrated {loaded} feedback rows from DB")
            except Exception as load_err:
                logger.warning(f"Could not hydrate learning router from DB: {load_err}")

            _SINGLETON = router
            logger.info("Learning router singleton initialized")
            return router
        except Exception as e:
            logger.warning(f"Could not instantiate learning router singleton: {e}")
            return None


def reset_learning_router_instance() -> None:
    """Drop the singleton (for tests)."""
    global _SINGLETON
    with _LOCK:
        _SINGLETON = None
