# -*- coding: utf-8 -*-
"""Coverage wave 69 — core/social_post_generator (fully mocked LLM service,
zero LLM spend, no network, no real DB).

- is_significant_operation: non-significant op, completed/failed statuses,
  approval_requested / agent_to_agent_call always-significant, other status.
- is_rate_limited: unknown agent, within window, expired, and a NAIVE
  timestamp (regression: naive vs aware subtraction raised TypeError instead
  of returning False).
- update_rate_limit: entry set, stale (>1h) entries pruned.
- generate_from_operation: missing what_explanation → ValueError; LLM
  disabled; llm_service None; LLM success (workspace/tenant ids from
  agent/tracker context); asyncio.TimeoutError → template; generic → template.
- _generate_with_llm: no service → ValueError; short/long (truncated) output;
  TimeoutError and generic exception re-raised.
- generate_with_template: completed/running/default templates, truncation,
  KeyError → default fallback.
- generate_with_episode_context: episodes+LLM, no episodes → template,
  metadata keys (mentioned ids, episode_count, generated_with_context).
- _retrieve_relevant_episodes: no db, success, exception tolerance.
- _format_episode_context: empty, summaries, >280 truncation, summary-less.
- _generate_with_llm_and_context: no service → RuntimeError; success;
  truncation; TimeoutError and generic → template fallback.
- _build_system_prompt / _build_user_prompt variants.
- module-level singleton exists.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.social_post_generator as spg
from core.social_post_generator import SocialPostGenerator


# ============================================================================
# Helpers
# ============================================================================

def _tracker(operation_type="workflow_execute", status="completed",
             what="did stuff", why="because", next_steps="more stuff"):
    return SimpleNamespace(
        operation_type=operation_type,
        status=status,
        what_explanation=what,
        why_explanation=why,
        next_steps=next_steps,
    )


def _agent(name="Test Agent"):
    return SimpleNamespace(name=name, workspace_id="ws-1", tenant_id="t1")


def _llm_patch(return_value):
    """Patch ServiceFactory.get_llm_service (lazily imported by the property)."""
    return patch(
        "core.service_factory.ServiceFactory.get_llm_service",
        new=classmethod(lambda cls, *a, **k: return_value),
    )


@pytest.fixture
def generator(monkeypatch):
    monkeypatch.setenv("SOCIAL_POST_LLM_ENABLED", "true")
    return SocialPostGenerator()


# ============================================================================
# Significance / rate limiting
# ============================================================================

class TestSignificance:
    def test_non_significant_operation(self, generator):
        assert generator.is_significant_operation(_tracker(operation_type="database_query")) is False

    @pytest.mark.parametrize("status", ["completed", "failed"])
    def test_completed_and_failed_significant(self, generator, status):
        assert generator.is_significant_operation(_tracker(status=status)) is True

    def test_approval_requested_always_significant(self, generator):
        assert generator.is_significant_operation(
            _tracker(operation_type="approval_requested", status="waiting")
        ) is True

    def test_agent_to_agent_call_always_significant(self, generator):
        assert generator.is_significant_operation(
            _tracker(operation_type="agent_to_agent_call", status="pending")
        ) is True

    def test_running_status_not_significant(self, generator):
        assert generator.is_significant_operation(_tracker(status="running")) is False


class TestRateLimit:
    def test_unknown_agent_not_limited(self, generator):
        assert generator.is_rate_limited("agent-x") is False

    def test_within_window_limited(self, generator):
        generator.update_rate_limit("agent-1")
        assert generator.is_rate_limited("agent-1") is True

    def test_expired_aware_timestamp(self, generator):
        generator._rate_limit_tracker["agent-1"] = (
            datetime.now(timezone.utc) - timedelta(minutes=30)
        )
        assert generator.is_rate_limited("agent-1") is False

    def test_naive_timestamp_does_not_crash(self, generator):
        """TDD regression: a naive timestamp in the tracker raised
        TypeError (naive vs aware subtraction) instead of returning False."""
        generator._rate_limit_tracker["agent-1"] = (
            datetime.now() - timedelta(minutes=30)
        )
        assert generator.is_rate_limited("agent-1") is False

    def test_update_prunes_stale_entries(self, generator):
        old = datetime.now(timezone.utc) - timedelta(hours=2)
        generator._rate_limit_tracker["stale-agent"] = old
        generator.update_rate_limit("fresh-agent")
        assert "stale-agent" not in generator._rate_limit_tracker
        assert "fresh-agent" in generator._rate_limit_tracker


# ============================================================================
# generate_from_operation
# ============================================================================

class TestGenerateFromOperation:
    def test_missing_what_explanation_raises(self, generator):
        tracker = _tracker(what=None)
        with pytest.raises(ValueError, match="what_explanation is required"):
            asyncio.run(generator.generate_from_operation(tracker, _agent()))

    def test_llm_disabled_uses_template(self, generator, monkeypatch):
        monkeypatch.setenv("SOCIAL_POST_LLM_ENABLED", "false")
        gen = SocialPostGenerator()
        post = asyncio.run(gen.generate_from_operation(_tracker(), _agent()))
        assert "workflow_execute" in post

    def test_llm_service_none_uses_template(self, generator):
        with _llm_patch(None):
            post = asyncio.run(generator.generate_from_operation(_tracker(), _agent()))
        assert "workflow_execute" in post

    def test_llm_success(self, generator):
        llm = MagicMock()
        llm.generate_response = AsyncMock(return_value="Just finished the report!")
        with _llm_patch(llm):
            post = asyncio.run(generator.generate_from_operation(_tracker(), _agent()))
        assert post == "Just finished the report!"
        kwargs = llm.generate_response.call_args[1]
        assert kwargs["workspace_id"] == "ws-1"
        assert kwargs["tenant_id"] == "t1"
        assert kwargs["temperature"] == 0.7

    def test_llm_success_agent_defaults(self, generator):
        llm = MagicMock()
        llm.generate_response = AsyncMock(return_value="ok")
        plain_agent = SimpleNamespace(name="no-ctx")
        with _llm_patch(llm):
            post = asyncio.run(generator.generate_from_operation(_tracker(), plain_agent))
        assert post == "ok"
        kwargs = llm.generate_response.call_args[1]
        assert kwargs["workspace_id"] == "default"
        assert kwargs["tenant_id"] == "default"

    def test_llm_timeout_falls_back_to_template(self, generator):
        llm = MagicMock()
        llm.generate_response = AsyncMock(side_effect=asyncio.TimeoutError())
        with _llm_patch(llm):
            post = asyncio.run(generator.generate_from_operation(_tracker(), _agent()))
        assert "workflow_execute" in post

    def test_llm_error_falls_back_to_template(self, generator):
        llm = MagicMock()
        llm.generate_response = AsyncMock(side_effect=RuntimeError("api down"))
        with _llm_patch(llm):
            post = asyncio.run(generator.generate_from_operation(_tracker(), _agent()))
        assert "workflow_execute" in post


class TestGenerateWithLlm:
    def test_no_service_raises_value_error(self, generator):
        with _llm_patch(None):
            with pytest.raises(ValueError, match="LLMService not initialized"):
                asyncio.run(generator._generate_with_llm(_tracker(), _agent()))

    def test_short_content(self, generator):
        llm = MagicMock()
        llm.generate_response = AsyncMock(return_value="short post")
        with _llm_patch(llm):
            post = asyncio.run(generator._generate_with_llm(_tracker(), _agent()))
        assert post == "short post"

    def test_long_content_truncated(self, generator):
        llm = MagicMock()
        llm.generate_response = AsyncMock(return_value="x" * 300)
        with _llm_patch(llm):
            post = asyncio.run(generator._generate_with_llm(_tracker(), _agent()))
        assert len(post) == 280
        assert post.endswith("...")

    def test_timeout_re_raised(self, generator):
        llm = MagicMock()
        llm.generate_response = AsyncMock(side_effect=asyncio.TimeoutError())
        with _llm_patch(llm):
            with pytest.raises(asyncio.TimeoutError):
                asyncio.run(generator._generate_with_llm(_tracker(), _agent()))

    def test_generic_error_re_raised(self, generator):
        llm = MagicMock()
        llm.generate_response = AsyncMock(side_effect=RuntimeError("boom"))
        with _llm_patch(llm):
            with pytest.raises(RuntimeError, match="boom"):
                asyncio.run(generator._generate_with_llm(_tracker(), _agent()))


# ============================================================================
# Template fallback
# ============================================================================

class TestTemplateFallback:
    def _meta(self, status="completed", **over):
        meta = {
            "agent_name": "Test Agent",
            "operation_type": "workflow_execute",
            "what_explanation": "ran tests",
            "why_explanation": "quality",
            "next_steps": "fix bugs",
            "status": status,
        }
        meta.update(over)
        return meta

    def test_completed_template(self, generator):
        post = generator.generate_with_template("workflow_execute", self._meta())
        assert "Just finished workflow_execute!" in post

    def test_running_template(self, generator):
        post = generator.generate_with_template("workflow_execute", self._meta(status="running"))
        assert post.startswith("Working on workflow_execute:")

    def test_default_template(self, generator):
        post = generator.generate_with_template("workflow_execute", self._meta(status="pending"))
        assert "Test Agent completed workflow_execute" in post

    def test_truncation(self, generator):
        post = generator.generate_with_template(
            "workflow_execute", self._meta(what_explanation="x" * 500)
        )
        assert len(post) <= 280
        assert post.endswith("...")

    def test_missing_key_uses_fallback(self, generator):
        post = generator.generate_with_template(
            "workflow_execute", {"agent_name": "A", "status": "completed"}
        )
        assert "A working on workflow_execute" == post


# ============================================================================
# Episode-context generation
# ============================================================================

class TestEpisodeContext:
    def _episode(self, summary="Did X before", eid="ep-1"):
        return SimpleNamespace(id=eid, summary=summary)

    def test_no_db_no_episodes_template(self, generator):
        out = asyncio.run(generator.generate_with_episode_context("a1", {"operation_type": "workflow_execute"}, db=None))
        assert out["content"]
        assert out["mentioned_episode_ids"] == []
        assert out["metadata"]["generated_with_context"] is False

    def test_episodes_with_llm(self, generator):
        llm = MagicMock()
        llm.generate_response = AsyncMock(return_value="Similar to before, I did it again!")
        with _llm_patch(llm), patch(
            "core.episode_retrieval_service.EpisodeRetrievalService"
        ) as ers:
            ers.return_value.retrieve_episodes = AsyncMock(
                return_value=[self._episode(summary="Ran ETL before", eid="ep-7")]
            )
            db = MagicMock()
            out = asyncio.run(generator.generate_with_episode_context(
                "a1", {"operation_type": "etl", "what_explanation": "loaded data"}, db=db
            ))
        assert out["content"] == "Similar to before, I did it again!"
        assert out["mentioned_episode_ids"] == ["ep-7"]
        assert out["metadata"]["episode_count"] == 1
        assert out["metadata"]["generated_with_context"] is True
        assert "Similar to past experiences" in llm.generate_response.call_args[1]["prompt"]

    def test_retrieve_episodes_no_db(self, generator):
        assert asyncio.run(generator._retrieve_relevant_episodes("a1", {}, 3, None)) == []

    def test_retrieve_episodes_success(self, generator):
        with patch("core.episode_retrieval_service.EpisodeRetrievalService") as ers:
            ers.return_value.retrieve_episodes = AsyncMock(return_value=["e1", "e2"])
            db = MagicMock()
            out = asyncio.run(generator._retrieve_relevant_episodes("a1", {"operation_type": "t"}, 3, db))
        assert out == ["e1", "e2"]
        assert ers.return_value.retrieve_episodes.await_count == 1

    def test_retrieve_episodes_exception_tolerated(self, generator):
        with patch("core.episode_retrieval_service.EpisodeRetrievalService") as ers:
            ers.return_value.retrieve_episodes = AsyncMock(side_effect=RuntimeError("boom"))
            db = MagicMock()
            out = asyncio.run(generator._retrieve_relevant_episodes("a1", {}, 3, db))
        assert out == []

    def test_format_context_empty(self, generator):
        assert generator._format_episode_context([]) == ""

    def test_format_context_with_summaries(self, generator):
        episodes = [self._episode(summary="First experience", eid="1")]
        ctx = generator._format_episode_context(episodes)
        assert ctx.startswith("Similar to past experiences:")
        assert "- First experience" in ctx

    def test_format_context_truncated(self, generator):
        # summaries are sliced to 100 chars each; 3 episodes exceed 280
        episodes = [self._episode(summary="y" * 200, eid=f"e{i}") for i in range(3)]
        ctx = generator._format_episode_context(episodes)
        assert len(ctx) <= 280
        assert ctx.endswith("...")

    def test_format_context_summaryless(self, generator):
        assert generator._format_episode_context([self._episode(summary=None)]) == ""

    def test_generate_with_context_no_service_raises(self, generator):
        with _llm_patch(None):
            with pytest.raises(RuntimeError, match="LLMService not initialized"):
                asyncio.run(generator._generate_with_llm_and_context({"operation_type": "t"}, "ctx"))

    def test_generate_with_context_success(self, generator):
        llm = MagicMock()
        llm.generate_response = AsyncMock(return_value="post with context")
        with _llm_patch(llm):
            out = asyncio.run(generator._generate_with_llm_and_context({"operation_type": "t"}, "ctx"))
        assert out == "post with context"
        assert "Similar to when I" in llm.generate_response.call_args[1]["system_prompt"]
        assert "ctx" in llm.generate_response.call_args[1]["prompt"]

    def test_generate_with_context_truncated(self, generator):
        llm = MagicMock()
        llm.generate_response = AsyncMock(return_value="x" * 300)
        with _llm_patch(llm):
            out = asyncio.run(generator._generate_with_llm_and_context({"operation_type": "t"}, "ctx"))
        assert len(out) == 280

    def test_generate_with_context_timeout_falls_back(self, generator):
        llm = MagicMock()
        llm.generate_response = AsyncMock(side_effect=asyncio.TimeoutError())
        with _llm_patch(llm):
            out = asyncio.run(generator._generate_with_llm_and_context(
                {"operation_type": "workflow_execute", "status": "completed",
                 "what_explanation": "x"}, "ctx"))
        assert "workflow_execute" in out

    def test_generate_with_context_error_falls_back(self, generator):
        llm = MagicMock()
        llm.generate_response = AsyncMock(side_effect=RuntimeError("boom"))
        with _llm_patch(llm):
            out = asyncio.run(generator._generate_with_llm_and_context(
                {"operation_type": "workflow_execute", "status": "completed",
                 "what_explanation": "x"}, "ctx"))
        assert "workflow_execute" in out


# ============================================================================
# Prompt builders + module singleton
# ============================================================================

class TestPromptBuilders:
    def test_system_prompt_base(self, generator):
        prompt = generator._build_system_prompt()
        assert "under 280 characters" in prompt
        assert "Similar to when I" not in prompt

    def test_system_prompt_with_episodes(self, generator):
        prompt = generator._build_system_prompt(with_episodes=True)
        assert "Similar to when I" in prompt

    def test_user_prompt_full(self, generator):
        prompt = generator._build_user_prompt(
            {"operation_type": "etl", "what_explanation": "loaded", "why_explanation": "why"},
            episode_context="ctx",
        )
        assert "Operation: etl" in prompt
        assert "What: loaded" in prompt
        assert "Why: why" in prompt
        assert "ctx" in prompt

    def test_user_prompt_minimal(self, generator):
        prompt = generator._build_user_prompt({"operation_type": "etl"})
        assert prompt == "Operation: etl\n"


class TestModuleSingleton:
    def test_global_generator_exists(self):
        assert isinstance(spg.social_post_generator, SocialPostGenerator)

    def test_significant_operations_set(self):
        assert spg.SocialPostGenerator.SIGNIFICANT_OPERATIONS >= {
            "workflow_execute", "approval_requested", "agent_to_agent_call"
        }
