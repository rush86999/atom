"""
Round 39 — Second-half auth sweep: routers where prior rounds fixed only part
of the surface (Red-Green-Refactor).

Prior rounds (20/24/25/26/27/38) added auth to *some* endpoints in these files
but left sibling endpoints anonymous. Confirmed via AST audit + manual review:

  A. api/ai_accounting_routes.py — only `ingest_transaction` was fixed (R27).
     The other 12 endpoints (bulk ingest, review queue, full ledger read,
     update/delete/post, auto-post, audit log, GL CSV export, trial balance,
     13-week forecast, scenario analysis) are anonymous, and update/delete/
     post/categorize trust a client-supplied `user_id` ("user" default) for
     the audit trail. Mounted at BOTH /api/v1/accounting and /api/ai-accounting.

  B. api/episode_routes.py — R26 fixed only ~6 of 20 retrieval endpoints.
     The remaining 14 (temporal/semantic/sequential/contextual/canvas-aware
     retrieval, feedback list, analytics, readiness, exam, audit trail,
     lifecycle decay, stats) are anonymous. `retrieve_temporal` trusts a
     client-supplied `user_id` (cross-user read = IDOR); `promote_agent`
     trusts client-supplied `validated_by` for the audit attribution.

  C. api/agent_governance_routes.py — `approve_workflow` has auth + RBAC, but
     `reject_workflow` (privilege escalation: anonymous rejection of pending
     approvals as ANY approver) and `list_pending_approvals` (anonymous read
     of the approval queue) have none. `approve_workflow` runs RBAC against
     the client-supplied `approver_id` instead of `current_user.id`.

  D. api/entity_type_routes.py — `create_entity_type` fixed (R26); the reads,
     `update_entity_type` (PATCH, schema modification) and `suggest-schema`
     (anonymous LLM usage) are not.

  E. api/graphrag_routes.py — `ingest_document`/`add_entity` fixed (R26); the
     other 9 (graph reads, `add_relationship`, `build_communities` — graph
     poisoning — and `query` — LLM cost abuse) are anonymous.

  F. api/agent_status_endpoints.py — write endpoints have auth; all 5 read
     endpoints (task status, agents, metrics) leak agent state anonymously.

  G. api/background_agent_routes.py — register/start/stop/status have auth;
     the 2 log-read endpoints do not.

  H. api/feedback_enhanced.py — submit fixed (R27); the 3 aggregate-read
     endpoints (agent summary, analytics, trends) are anonymous.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db


def make_client(router, current_user=None, db=None):
    """TestClient with auth + db dependency overrides (authenticated)."""
    app = FastAPI()
    app.include_router(router)

    def _override_user():
        return current_user if current_user is not None else MagicMock(id="r39-user")

    def _override_db():
        return db if db is not None else MagicMock()

    app.dependency_overrides[auth_get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db
    return TestClient(app, raise_server_exceptions=False)


def make_anon_client(router):
    """TestClient WITHOUT auth overrides — requests must 401."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


# ============================================================================
# A. AI Accounting — anonymous financial access + user_id spoofing
# ============================================================================

class TestAiAccountingAuth:
    def _anon(self):
        from api.ai_accounting_routes import router
        return make_anon_client(router)

    def test_bank_feed_requires_auth(self):
        resp = self._anon().post("/bank-feed", json={"transactions": []})
        assert resp.status_code == 401

    def test_review_queue_requires_auth(self):
        assert self._anon().get("/review-queue").status_code == 401

    def test_all_transactions_requires_auth(self):
        assert self._anon().get("/all-transactions").status_code == 401

    def test_update_transaction_requires_auth(self):
        resp = self._anon().put("/transactions/tx-1", json={"description": "x"})
        assert resp.status_code == 401

    def test_delete_transaction_requires_auth(self):
        assert self._anon().delete("/transactions/tx-1").status_code == 401

    def test_post_transaction_requires_auth(self):
        assert self._anon().post("/post/tx-1").status_code == 401

    def test_auto_post_requires_auth(self):
        assert self._anon().post("/auto-post").status_code == 401

    def test_audit_log_requires_auth(self):
        assert self._anon().get("/audit-log").status_code == 401

    def test_export_gl_requires_auth(self):
        assert self._anon().get("/export/gl").status_code == 401

    def test_export_trial_balance_requires_auth(self):
        assert self._anon().get("/export/trial-balance").status_code == 401

    def test_forecast_requires_auth(self):
        assert self._anon().get("/forecast").status_code == 401

    def test_scenario_requires_auth(self):
        resp = self._anon().post("/scenario?scenario_description=what-if")
        assert resp.status_code == 401

    def test_authenticated_bank_feed_works(self):
        from api.ai_accounting_routes import router
        with patch("core.ai_accounting_engine.ai_accounting") as engine:
            engine.ingest_bank_feed.return_value = []
            client = make_client(router, current_user=MagicMock(id="u-42"))
            resp = client.post("/bank-feed", json={"transactions": []})
        assert resp.status_code == 200

    def test_update_uses_current_user_id(self):
        from api.ai_accounting_routes import router
        with patch("core.ai_accounting_engine.ai_accounting") as engine:
            engine.update_transaction.return_value = True
            client = make_client(router, current_user=MagicMock(id="u-42"))
            resp = client.put("/transactions/tx-1", json={"description": "x"})
            assert resp.status_code == 200
            engine.update_transaction.assert_called_once_with(
                "tx-1", {"description": "x"}, "u-42"
            )

    def test_delete_uses_current_user_id(self):
        from api.ai_accounting_routes import router
        with patch("core.ai_accounting_engine.ai_accounting") as engine:
            engine.delete_transaction.return_value = True
            client = make_client(router, current_user=MagicMock(id="u-42"))
            resp = client.delete("/transactions/tx-1")
            assert resp.status_code == 200
            engine.delete_transaction.assert_called_once_with("tx-1", "u-42")

    def test_post_uses_current_user_id(self):
        from api.ai_accounting_routes import router
        with patch("core.ai_accounting_engine.ai_accounting") as engine:
            engine.post_transaction.return_value = True
            client = make_client(router, current_user=MagicMock(id="u-42"))
            resp = client.post("/post/tx-1")
            assert resp.status_code == 200
            engine.post_transaction.assert_called_once_with("tx-1", "u-42")

    def test_categorize_uses_current_user_id(self):
        from api.ai_accounting_routes import router
        with patch("core.ai_accounting_engine.ai_accounting") as engine:
            engine.learn_categorization.return_value = None
            client = make_client(router, current_user=MagicMock(id="u-42"))
            resp = client.post(
                "/categorize",
                json={"transaction_id": "t1", "category_id": "c1"},
            )
            assert resp.status_code == 200
            engine.learn_categorization.assert_called_once_with("t1", "c1", "u-42")


# ============================================================================
# B. Episodic memory — anonymous retrieval/state + user_id IDOR
# ============================================================================

class TestEpisodeRoutesAuth:
    def _anon(self):
        from api.episode_routes import router
        return make_anon_client(router)

    def test_retrieve_temporal_requires_auth(self):
        resp = self._anon().post(
            "/api/episodes/retrieve/temporal",
            json={"agent_id": "a-1", "time_range": "7d"},
        )
        assert resp.status_code == 401

    def test_retrieve_semantic_requires_auth(self):
        resp = self._anon().post(
            "/api/episodes/retrieve/semantic",
            json={"agent_id": "a-1", "query": "q"},
        )
        assert resp.status_code == 401

    def test_retrieve_sequential_requires_auth(self):
        assert self._anon().get(
            "/api/episodes/retrieve/e-1?agent_id=a-1"
        ).status_code == 401

    def test_retrieve_contextual_requires_auth(self):
        resp = self._anon().post(
            "/api/episodes/retrieve/contextual",
            json={"agent_id": "a-1", "current_task": "t"},
        )
        assert resp.status_code == 401

    def test_retrieve_by_canvas_type_requires_auth(self):
        resp = self._anon().post(
            "/api/episodes/retrieve/by-canvas-type",
            json={"agent_id": "a-1", "canvas_type": "sheets"},
        )
        assert resp.status_code == 401

    def test_retrieve_canvas_aware_requires_auth(self):
        resp = self._anon().post(
            "/api/episodes/retrieve/canvas-aware",
            json={"agent_id": "a-1", "query": "q", "canvas_type": "generic"},
        )
        assert resp.status_code == 401

    def test_retrieve_by_canvas_type_get_requires_auth(self):
        assert self._anon().get(
            "/api/episodes/retrieve/canvas-type/sheets?agent_id=a-1"
        ).status_code == 401

    def test_retrieve_business_data_requires_auth(self):
        resp = self._anon().post(
            "/api/episodes/retrieve/business-data",
            json={"agent_id": "a-1", "filters": {}},
        )
        assert resp.status_code == 401

    def test_get_episode_feedback_requires_auth(self):
        assert self._anon().get("/api/episodes/e-1/feedback/list").status_code == 401

    def test_feedback_weighted_episodes_requires_auth(self):
        assert self._anon().get(
            "/api/episodes/analytics/feedback-episodes?agent_id=a-1"
        ).status_code == 401

    def test_readiness_requires_auth(self):
        assert self._anon().get(
            "/api/episodes/graduation/readiness/a-1"
        ).status_code == 401

    def test_run_exam_requires_auth(self):
        resp = self._anon().post(
            "/api/episodes/graduation/exam?agent_id=a-1&edge_case_episodes=e1"
        )
        assert resp.status_code == 401

    def test_audit_trail_requires_auth(self):
        assert self._anon().get(
            "/api/episodes/graduation/audit/a-1"
        ).status_code == 401

    def test_trigger_decay_requires_auth(self):
        assert self._anon().post("/api/episodes/lifecycle/decay").status_code == 401

    def test_get_stats_requires_auth(self):
        assert self._anon().get("/api/episodes/stats/a-1").status_code == 401

    def test_retrieve_temporal_uses_current_user_id(self):
        """Client-supplied user_id is ignored; identity comes from the token."""
        from api.episode_routes import router
        service = MagicMock()
        service.retrieve_temporal = AsyncMock(return_value={})
        with patch("api.episode_routes.EpisodeRetrievalService", return_value=service):
            client = make_client(router, current_user=MagicMock(id="u-42"))
            resp = client.post(
                "/api/episodes/retrieve/temporal",
                json={"agent_id": "a-1", "time_range": "7d",
                      "user_id": "attacker", "limit": 5},
            )
            assert resp.status_code == 200
            service.retrieve_temporal.assert_awaited_once_with(
                agent_id="a-1", time_range="7d", user_id="u-42", limit=5
            )

    def test_promote_uses_current_user_id(self):
        """validated_by is attributed to the authenticated user, not the caller."""
        from api.episode_routes import router
        service = MagicMock()
        service.promote_agent = AsyncMock(return_value=True)
        with patch("api.episode_routes.AgentGraduationService", return_value=service):
            client = make_client(router, current_user=MagicMock(id="u-42"))
            resp = client.post(
                "/api/episodes/graduation/promote"
                "?agent_id=a-1&new_maturity=INTERN&validated_by=attacker"
            )
            assert resp.status_code == 200
            service.promote_agent.assert_awaited_once_with("a-1", "INTERN", "u-42")


# ============================================================================
# C. Agent governance — anonymous rejection + queue read + approver spoofing
# ============================================================================

class TestAgentGovernanceAuth:
    def _anon(self):
        from api.agent_governance_routes import router
        return make_anon_client(router)

    def test_pending_approvals_requires_auth(self):
        assert self._anon().get(
            "/api/agent-governance/pending-approvals"
        ).status_code == 401

    def test_reject_workflow_requires_auth(self):
        resp = self._anon().post(
            "/api/agent-governance/reject/ap-1?approver_id=attacker&reason=no"
        )
        assert resp.status_code == 401

    def test_generate_workflow_requires_auth(self):
        resp = self._anon().post(
            "/api/agent-governance/generate-workflow"
            "?description=build+a+report&agent_id=agent_1"
        )
        assert resp.status_code == 401

    def test_approve_uses_current_user_id(self):
        """RBAC + attribution use the token identity, not client approver_id."""
        from api.agent_governance_routes import router

        class FakeUser:
            role = "super_admin"  # UserRole.SUPER_ADMIN.value

        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = FakeUser()

        with patch("api.agent_governance_routes.intervention_service") as svc:
            svc.approve_intervention = AsyncMock(return_value={"success": True})
            client = make_client(
                router, current_user=MagicMock(id="u-42"), db=fake_db
            )
            resp = client.post(
                "/api/agent-governance/approve/ap-1?approver_id=attacker"
            )
            assert resp.status_code == 200
            svc.approve_intervention.assert_awaited_once_with("ap-1", "u-42")

    def test_reject_uses_current_user_id(self):
        from api.agent_governance_routes import router
        with patch("api.agent_governance_routes.intervention_service") as svc:
            svc.reject_intervention = AsyncMock(return_value={"success": True})
            client = make_client(router, current_user=MagicMock(id="u-42"))
            resp = client.post(
                "/api/agent-governance/reject/ap-1?approver_id=attacker&reason=no"
            )
            assert resp.status_code == 200
            svc.reject_intervention.assert_awaited_once_with("ap-1", "u-42", "no")


# ============================================================================
# D. Entity types — anonymous schema modification + LLM usage
# ============================================================================

class TestEntityTypeAuth:
    def _anon(self):
        from api.entity_type_routes import router
        return make_anon_client(router)

    def test_list_entity_types_requires_auth(self):
        assert self._anon().get("/api/entity-types?workspace_id=w").status_code == 401

    def test_get_entity_type_requires_auth(self):
        assert self._anon().get(
            "/api/entity-types/et-1?workspace_id=w"
        ).status_code == 401

    def test_update_entity_type_requires_auth(self):
        resp = self._anon().patch(
            "/api/entity-types/et-1?workspace_id=w", json={"display_name": "X"}
        )
        assert resp.status_code == 401

    def test_suggest_schema_requires_auth(self):
        resp = self._anon().post(
            "/api/entity-types/suggest-schema",
            json={"display_name": "Invoice", "description": "d"},
        )
        assert resp.status_code == 401

    def test_authenticated_update_works(self):
        from api.entity_type_routes import router
        service = MagicMock()
        service.update_entity_type.return_value = MagicMock(id="et-1")
        with patch(
            "api.entity_type_routes.get_entity_type_service", return_value=service
        ):
            client = make_client(router, current_user=MagicMock(id="u-42"))
            resp = client.patch(
                "/api/entity-types/et-1?workspace_id=w",
                json={"display_name": "Updated"},
            )
        assert resp.status_code == 200


# ============================================================================
# E. GraphRAG — anonymous graph reads/writes + LLM cost abuse
# ============================================================================

class TestGraphRAGAuth:
    def _anon(self):
        from api.graphrag_routes import router
        return make_anon_client(router)

    def test_list_entities_requires_auth(self):
        assert self._anon().get("/api/graphrag/entities?workspace_id=w").status_code == 401

    def test_canonical_search_requires_auth(self):
        assert self._anon().get(
            "/api/graphrag/canonical-search?workspace_id=w&type=person&q=joe"
        ).status_code == 401

    def test_list_relationships_requires_auth(self):
        assert self._anon().get(
            "/api/graphrag/relationships?workspace_id=w"
        ).status_code == 401

    def test_add_relationship_requires_auth(self):
        resp = self._anon().post("/api/graphrag/relationships?workspace_id=w")
        assert resp.status_code == 401

    def test_build_communities_requires_auth(self):
        resp = self._anon().post("/api/graphrag/build-communities?user_id=u")
        assert resp.status_code == 401

    def test_query_requires_auth(self):
        resp = self._anon().post(
            "/api/graphrag/query",
            json={"workspace_id": "w", "query": "q", "mode": "local"},
        )
        assert resp.status_code == 401

    def test_neighbors_requires_auth(self):
        assert self._anon().get(
            "/api/graphrag/entities/e-1/neighbors?workspace_id=w"
        ).status_code == 401

    def test_context_requires_auth(self):
        assert self._anon().get(
            "/api/graphrag/context?user_id=u&query=q"
        ).status_code == 401

    def test_stats_requires_auth(self):
        assert self._anon().get("/api/graphrag/stats").status_code == 401

    def test_authenticated_query_works(self):
        from api.graphrag_routes import router
        with patch("core.graphrag_engine.graphrag_engine") as engine:
            # query() is async on the engine — the route now awaits it.
            engine.query = AsyncMock(return_value={"results": []})
            client = make_client(router, current_user=MagicMock(id="u-42"))
            resp = client.post(
                "/api/graphrag/query",
                json={"workspace_id": "w", "query": "q", "mode": "local"},
            )
        assert resp.status_code == 200


# ============================================================================
# F. Agent status — anonymous reads of task/agent state
# ============================================================================

class TestAgentStatusReadAuth:
    def _anon(self):
        from api.agent_status_endpoints import router
        return make_anon_client(router)

    def test_get_agent_status_requires_auth(self):
        assert self._anon().get("/api/agent-status/agent/status/t-1").status_code == 401

    def test_get_all_agent_tasks_requires_auth(self):
        assert self._anon().get("/api/agent-status/agent/status").status_code == 401

    def test_get_all_agents_requires_auth(self):
        assert self._anon().get("/api/agent-status/agents").status_code == 401

    def test_get_agent_info_requires_auth(self):
        assert self._anon().get("/api/agent-status/agents/a-1").status_code == 401

    def test_get_agent_metrics_requires_auth(self):
        assert self._anon().get("/api/agent-status/agent/metrics").status_code == 401

    def test_authenticated_read_works(self):
        from api.agent_status_endpoints import router
        with patch(
            "api.agent_status_endpoints.load_agent_status",
            return_value={"agents": {}, "tasks": {}},
        ):
            client = make_client(router, current_user=MagicMock(id="u-42"))
            resp = client.get("/api/agent-status/agents")
        assert resp.status_code == 200


# ============================================================================
# G. Background agents — anonymous log reads
# ============================================================================

class TestBackgroundAgentLogsAuth:
    def _anon(self):
        from api.background_agent_routes import router
        return make_anon_client(router)

    def test_get_agent_logs_requires_auth(self):
        assert self._anon().get("/api/background-agents/a-1/logs").status_code == 401

    def test_get_all_logs_requires_auth(self):
        assert self._anon().get("/api/background-agents/logs").status_code == 401


# ============================================================================
# H. Enhanced feedback — anonymous aggregate reads
# ============================================================================

class TestFeedbackEnhancedReadsAuth:
    def _anon(self):
        from api.feedback_enhanced import router
        return make_anon_client(router)

    def test_get_agent_feedback_requires_auth(self):
        assert self._anon().get("/api/feedback/agent/a-1?days=7").status_code == 401

    def test_get_feedback_analytics_requires_auth(self):
        assert self._anon().get("/api/feedback/analytics?days=7").status_code == 401

    def test_get_feedback_trends_requires_auth(self):
        assert self._anon().get("/api/feedback/trends?days=7").status_code == 401
