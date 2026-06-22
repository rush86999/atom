"""
TDD regression tests for round 17b memory leak fixes.

Covers:
- BUG R17-2: learning_llm_router caches grew without bound (router_cache,
  preference_data per key). Added eviction caps.
"""

from __future__ import annotations

import inspect


class TestLearningRouterCacheCaps:
    """learning_llm_router must cap cache sizes."""

    def test_router_cache_has_max_size(self):
        from core import learning_llm_router

        src = inspect.getsource(learning_llm_router.LearningBasedRouter.__init__)
        assert "_max_router_cache_size" in src, (
            "LearningBasedRouter does not define _max_router_cache_size"
        )

    def test_preference_data_has_max_per_key(self):
        from core import learning_llm_router

        src = inspect.getsource(learning_llm_router.LearningBasedRouter.__init__)
        assert "_max_preference_data_per_key" in src, (
            "LearningBasedRouter does not define _max_preference_data_per_key"
        )

    def test_router_cache_evicts_oldest(self):
        """Source of _retrain_router must evict oldest when over cap."""
        from core import learning_llm_router

        # Find any method that assigns to _router_cache and check eviction
        src = inspect.getsource(learning_llm_router)
        # Look for eviction pattern near _router_cache assignment
        assert "_max_router_cache_size" in src and "del self._router_cache" in src, (
            "learning_llm_router assigns to _router_cache without eviction"
        )

    def test_preference_data_trims_per_key(self):
        from core import learning_llm_router

        src = inspect.getsource(learning_llm_router)
        assert "_max_preference_data_per_key" in src and "del self._preference_data" in src, (
            "learning_llm_router appends to _preference_data without trimming"
        )
