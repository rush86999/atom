"""
DB persistence tests for the learning-based LLM router.

Verifies that routing feedback survives a simulated process restart: write
feedback through ``record_feedback`` → the row lands in the DB → a fresh
router instance (empty in-memory state) calls ``load_feedback_from_db`` and
recovers the feedback so predictors can retrain.

Also covers the two crash-bug regressions: ``optimize_routing_configuration``
(no broken import) and ``_create_model`` for NEURAL_NETWORK / ENSEMBLE.
"""

from __future__ import annotations

import os
from unittest.mock import Mock

import pytest


# ----------------------------------------------------------------------------
# Bug-fix regression tests
# ----------------------------------------------------------------------------

class TestCrashBugFixes:
    """The two latent crash bugs identified in the completeness audit."""

    def test_neural_network_model_type_trains(self, tmp_path):
        """ModelType.NEURAL_NETWORK must train, not raise ValueError."""
        from core.llm.routing import (
            RouteLLMTrainer, TrainingConfig, ModelType, TrainingExample,
        )
        import math

        def ex(satisfied):
            return TrainingExample(
                estimated_tokens=800, task_type="code_generation",
                prompt_features={
                    "log_tokens": math.log2(801), "token_bucket": 1.0,
                    "task_code": 1.0, "task_analysis": 0.0,
                    "task_reasoning": 0.0, "task_chat": 0.0,
                    "task_general": 0.0, "has_code": 1.0,
                    "has_numbers": 1.0, "avg_word_length": 5.0,
                },
                user_satisfaction=0.9 if satisfied else 0.1,
                was_successful=satisfied,
            )

        cfg = TrainingConfig(
            model_type=ModelType.NEURAL_NETWORK,
            min_samples=10, epochs=50,
            model_path=str(tmp_path / "models"),
        )
        trainer = RouteLLMTrainer(cfg)
        result = trainer.train([ex(i % 2 == 0) for i in range(30)])
        from core.llm.routing import TrainingStatus
        assert result.status == TrainingStatus.COMPLETED, result.metadata

    def test_ensemble_model_type_trains(self, tmp_path):
        """ModelType.ENSEMBLE must train, not raise ValueError."""
        from core.llm.routing import (
            RouteLLMTrainer, TrainingConfig, ModelType, TrainingStatus,
            TrainingExample,
        )
        import math

        def ex(satisfied):
            return TrainingExample(
                estimated_tokens=800, task_type="code_generation",
                prompt_features={
                    "log_tokens": math.log2(801), "token_bucket": 1.0,
                    "task_code": 1.0, "task_analysis": 0.0,
                    "task_reasoning": 0.0, "task_chat": 0.0,
                    "task_general": 0.0, "has_code": 1.0,
                    "has_numbers": 1.0, "avg_word_length": 5.0,
                },
                user_satisfaction=0.9 if satisfied else 0.1,
                was_successful=satisfied,
            )

        cfg = TrainingConfig(
            model_type=ModelType.ENSEMBLE,
            min_samples=10,
            model_path=str(tmp_path / "models"),
        )
        trainer = RouteLLMTrainer(cfg)
        result = trainer.train([ex(i % 2 == 0) for i in range(30)])
        assert result.status == TrainingStatus.COMPLETED, result.metadata

    @pytest.mark.asyncio
    async def test_optimize_routing_configuration_runs(self, monkeypatch, tmp_path):
        """optimize_routing_configuration must not crash on the broken import."""
        from core import learning_llm_router

        original_init = learning_llm_router.TrainingConfig.__init__

        def patched_init(self, *args, **kwargs):
            kwargs.setdefault("model_path", str(tmp_path / "models"))
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(
            learning_llm_router.TrainingConfig, "__init__", patched_init
        )

        router = learning_llm_router.LearningBasedRouter(Mock())
        # Previously raised ImportError (HypothesisTree not in core.models) +
        # misused db.add/flush/commit on a dataclass.
        result = await router.optimize_routing_configuration(
            tenant_id="t1",
            task_type="code_generation",
            requirements={"max_latency_ms": 2000, "min_quality": 0.8},
        )
        assert result is not None
        assert "optimization_score" in result
        assert "nodes_explored" in result


# ----------------------------------------------------------------------------
# DB persistence round-trip
# ----------------------------------------------------------------------------

class TestRoutingFeedbackDBPersistence:
    """Feedback must survive a simulated restart via DB persistence."""

    @pytest.fixture
    def isolated_db(self, monkeypatch, tmp_path):
        """Point the router's DB layer at an isolated SQLite file.

        Reconfigures ``core.database``'s engine + sessionmaker to a fresh
        SQLite DB and creates the routing-feedback table. Restored on teardown.
        """
        import core.database as dbmod
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from core.models import Base

        db_file = tmp_path / "rt_test.db"
        engine = create_engine(f"sqlite:///{db_file}")
        # Create only the table under test (avoids the full schema's FK
        # ordering issues on a bare SQLite DB).
        from core.models import LLMRoutingFeedback
        LLMRoutingFeedback.__table__.create(engine, checkfirst=True)

        TestSession = sessionmaker(bind=engine, expire_on_commit=False)

        # Monkeypatch get_db_session to yield sessions on our test engine.
        from contextlib import contextmanager

        @contextmanager
        def test_get_db_session():
            session = TestSession()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        import core.learning_llm_router as llr
        monkeypatch.setattr(llr, "get_db_session", test_get_db_session)

        yield db_file

        engine.dispose()

    @pytest.fixture
    def router(self, monkeypatch, tmp_path, isolated_db):
        from core import learning_llm_router

        original_init = learning_llm_router.TrainingConfig.__init__

        def patched_init(self, *args, **kwargs):
            kwargs.setdefault("model_path", str(tmp_path / "models"))
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(
            learning_llm_router.TrainingConfig, "__init__", patched_init
        )

        router = learning_llm_router.LearningBasedRouter(Mock())
        router._min_samples_per_model = 10_000_000  # disable retrain in tests
        return router

    def _fb(self, result_id, model_id, success, tenant="t1", task="code_generation"):
        from core.learning_llm_router import RoutingFeedback
        return RoutingFeedback(
            routing_result_id=result_id,
            tenant_id=tenant, model_id=model_id, task_type=task,
            success=success, quality_satisfied=success,
            cost_within_budget=True, user_satisfaction=0.9 if success else 0.1,
        )

    @pytest.mark.asyncio
    async def test_feedback_persists_to_db(self, router, isolated_db):
        """record_feedback writes a row to the DB."""
        await router.record_feedback(self._fb("rid-1", "gpt-4o", True))

        # Read the DB directly.
        from contextlib import contextmanager
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from core.models import LLMRoutingFeedback

        engine = create_engine(f"sqlite:///{isolated_db}")
        Session = sessionmaker(bind=engine)
        with Session() as s:
            rows = s.query(LLMRoutingFeedback).all()
        engine.dispose()

        assert len(rows) == 1
        assert rows[0].model_id == "gpt-4o"
        assert rows[0].success is True
        assert rows[0].routing_result_id == "rid-1"

    @pytest.mark.asyncio
    async def test_feedback_survives_restart(self, router, isolated_db, monkeypatch, tmp_path):
        """A fresh router instance recovers persisted feedback on load."""
        # Write some feedback with the "first" router.
        for i in range(5):
            await router.record_feedback(self._fb(f"rid-{i}", "gpt-4o", True))

        # Simulate a restart: brand-new router, empty in-memory state, same DB.
        from core import learning_llm_router

        original_init = learning_llm_router.TrainingConfig.__init__

        def patched_init(self, *args, **kwargs):
            kwargs.setdefault("model_path", str(tmp_path / "models2"))
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(
            learning_llm_router.TrainingConfig, "__init__", patched_init
        )

        # Re-wire the new router's DB layer to the same DB file.
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from contextlib import contextmanager

        engine = create_engine(f"sqlite:///{isolated_db}")
        TestSession = sessionmaker(bind=engine, expire_on_commit=False)

        @contextmanager
        def test_get_db_session():
            session = TestSession()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        restarted = learning_llm_router.LearningBasedRouter(Mock())
        monkeypatch.setattr(restarted, "_persist_feedback", lambda *a, **k: None)
        # Patch the module-level get_db_session the load helper uses.
        import core.learning_llm_router as llr
        monkeypatch.setattr(llr, "get_db_session", test_get_db_session)

        loaded = restarted.load_feedback_from_db()
        assert loaded == 5, f"expected 5 rows recovered, got {loaded}"
        assert len(restarted._preference_data["t1:code_generation"]) == 5
        # The recovered feedback must carry the original fields.
        fb = restarted._preference_data["t1:code_generation"][0]
        assert fb.model_id == "gpt-4o"
        assert fb.success is True

        engine.dispose()

    @pytest.mark.asyncio
    async def test_db_failure_does_not_break_routing(self, router, monkeypatch):
        """A DB write failure must be swallowed (best-effort), not raised."""
        from contextlib import contextmanager

        @contextmanager
        def failing_db_session():
            raise RuntimeError("DB is down")

        import core.learning_llm_router as llr
        monkeypatch.setattr(llr, "get_db_session", failing_db_session)

        # Must not raise.
        await router.record_feedback(self._fb("rid-x", "gpt-4o", True))
        # In-memory state must still be updated.
        assert len(router._preference_data["t1:code_generation"]) == 1
