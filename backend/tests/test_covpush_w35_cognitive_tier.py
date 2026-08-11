"""Coverage wave 35 — core/llm/cognitive_tier_system.py (81% → 90%+).

Covers the classify COMPLEX fallback and the workspace tier_models override
path (user-configured models, empty-list fall-through, query exception
tolerance) in get_tier_models.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier


class TestClassifyFallback:
    def test_extreme_complexity_falls_back_to_complex(self):
        clf = CognitiveClassifier()
        # Long, keyword-dense prompt: no tier threshold matches → COMPLEX
        prompt = ("Write a production-grade Kubernetes operator that orchestrates "
                  "a distributed event-sourcing system with CQRS, sagas, and "
                  "multi-region failover, including Helm charts, CRDs, admission "
                  "webhooks, and performance benchmarks under chaos testing. ") * 8
        assert clf.classify(prompt) == CognitiveTier.COMPLEX


class TestGetTierModelsWorkspaceOverride:
    def _pref(self, tier_models):
        return SimpleNamespace(metadata_json={"tier_models": tier_models})

    def test_workspace_override_returns_user_models(self):
        clf = CognitiveClassifier()
        pref = self._pref({CognitiveTier.MICRO.value: ["local-1", "local-2"]})
        with patch("core.database.get_db_session") as gds:
            db = gds.return_value.__enter__.return_value
            db.query.return_value.filter.return_value.first.return_value = pref
            models = clf.get_tier_models(CognitiveTier.MICRO, workspace_id="ws-1")
        assert models == ["local-1", "local-2"]

    def test_workspace_override_empty_list_falls_through(self):
        clf = CognitiveClassifier()
        pref = self._pref({CognitiveTier.MICRO.value: []})
        with patch("core.database.get_db_session") as gds:
            db = gds.return_value.__enter__.return_value
            db.query.return_value.filter.return_value.first.return_value = pref
            models = clf.get_tier_models(CognitiveTier.MICRO, workspace_id="ws-1")
        assert models  # defaults returned
        assert "deepseek-chat" in models

    def test_no_pref_row_falls_through(self):
        clf = CognitiveClassifier()
        with patch("core.database.get_db_session") as gds:
            db = gds.return_value.__enter__.return_value
            db.query.return_value.filter.return_value.first.return_value = None
            models = clf.get_tier_models(CognitiveTier.MICRO, workspace_id="ws-1")
        assert "deepseek-chat" in models

    def test_db_exception_falls_through(self):
        clf = CognitiveClassifier()
        with patch("core.database.get_db_session",
                   side_effect=RuntimeError("db down")):
            models = clf.get_tier_models(CognitiveTier.MICRO, workspace_id="ws-1")
        assert "deepseek-chat" in models

    def test_no_workspace_uses_defaults(self):
        clf = CognitiveClassifier()
        models = clf.get_tier_models(CognitiveTier.MICRO)
        assert "deepseek-chat" in models
