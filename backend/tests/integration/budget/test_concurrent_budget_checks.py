"""
Integration tests for concurrent budget checks with a real database.

The previous version of this suite called `approve_spend_locked` on
`Project`/`BudgetStatus` models — an API that never existed in this
codebase (the service is tenant/agent/action based and async). Rewritten
(R72 bug-hunt wave) against the real contract: concurrent
`BudgetEnforcementService.check_budget_before_action` calls on a shared
file-backed SQLite session, verifying consistent results under thread
concurrency, plus the fleet aggregate cap (chain_id) path.

Deterministic spend state is injected via `update_tenant_spend` (the same
pattern the unit suite uses); enforcement mode is exercised against the
real `TenantSetting['billing']` persistence path.
"""

import pytest
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json

from sqlalchemy.orm import Session

from core.budget_enforcement_service import (
    BudgetEnforcementService,
    BudgetEnforcementMode,
)
from core.models import Tenant, TenantSetting, TokenUsage, AgentRegistry, DelegationChain


def _run_concurrently(coro_factory, workers: int = 10):
    """Run `workers` coroutines in parallel threads, returning all results."""
    results = []

    def worker(i):
        return asyncio.run(coro_factory(i))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker, i) for i in range(workers)]
        for future in as_completed(futures):
            results.append(future.result())
    return results


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def budget_service(db_session):
    """Provide BudgetEnforcementService backed by the test session."""
    return BudgetEnforcementService(db_session)


@pytest.fixture
def tenant_factory(db_session):
    """Create test tenants with an optional enforcement mode."""
    def _create(mode: str = None) -> Tenant:
        suffix = time.time_ns()
        tenant = Tenant(
            id=f"tenant_intg_{suffix}",
            name=f"Concurrent Test {suffix}",
            subdomain=f"concurrent-{suffix}",
            plan_type="pro",
            edition="personal",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(tenant)
        if mode:
            db_session.add(TenantSetting(
                tenant_id=tenant.id,
                setting_key="billing",
                setting_value=json.dumps({"enforcement": {"mode": mode}}),
            ))
        db_session.commit()
        return tenant

    return _create


# ============================================================================
# Test Concurrent Budget Checks
# ============================================================================

class TestConcurrentBudgetChecks:
    """Concurrent check_budget_before_action calls on a shared session."""

    def test_concurrent_checks_allowed_under_budget(
        self, budget_service, tenant_factory, db_session: Session
    ):
        """Under budget, all 10 concurrent checks are allowed."""
        tenant = tenant_factory()
        budget_service.spend_service.update_tenant_spend = lambda tid: {
            "current_spend_usd": 50.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 50.0,
        }

        results = _run_concurrently(
            lambda i: budget_service.check_budget_before_action(
                tenant_id=tenant.id,
                agent_id=f"agent-{i}",
                action="run_episode",
            )
        )

        assert len(results) == 10
        assert all(r["allowed"] is True for r in results)
        assert all(r["utilization_percent"] == 50.0 for r in results)

    def test_concurrent_checks_hard_stop_blocks_all(
        self, budget_service, tenant_factory
    ):
        """At/over budget in hard_stop mode, all 10 concurrent checks block."""
        tenant = tenant_factory(mode=BudgetEnforcementMode.HARD_STOP)
        budget_service.spend_service.update_tenant_spend = lambda tid: {
            "current_spend_usd": 100.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 100.0,
        }

        results = _run_concurrently(
            lambda i: budget_service.check_budget_before_action(
                tenant_id=tenant.id,
                agent_id=f"agent-{i}",
                action="run_episode",
            )
        )

        assert len(results) == 10
        assert all(r["allowed"] is False for r in results)
        assert all(r["enforcement_mode"] == BudgetEnforcementMode.HARD_STOP for r in results)

    def test_concurrent_checks_alert_only_allows_over_budget(
        self, budget_service, tenant_factory
    ):
        """Over budget in alert_only mode, all 10 concurrent checks allow."""
        tenant = tenant_factory(mode=BudgetEnforcementMode.ALERT_ONLY)
        budget_service.spend_service.update_tenant_spend = lambda tid: {
            "current_spend_usd": 150.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 150.0,
        }

        results = _run_concurrently(
            lambda i: budget_service.check_budget_before_action(
                tenant_id=tenant.id,
                agent_id=f"agent-{i}",
                action="run_episode",
            )
        )

        assert len(results) == 10
        assert all(r["allowed"] is True for r in results)


class TestConcurrentFleetAggregate:
    """Concurrent checks against a delegation chain aggregate cap."""

    def test_fleet_aggregate_cap_blocks_concurrent_checks(
        self, budget_service, tenant_factory, db_session: Session
    ):
        """Fleet cap reached → every concurrent check with chain_id blocks."""
        tenant = tenant_factory()
        budget_service.spend_service.update_tenant_spend = lambda tid: {
            "current_spend_usd": 10.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 10.0,
        }

        agent = AgentRegistry(
            id=f"agent_root_{time.time_ns()}",
            name="Root Agent",
            category="Operations",
            module_path="operations.automations.inventory",
            class_name="InventoryAgent",
            tenant_id=tenant.id,
            status="autonomous",
        )
        db_session.add(agent)
        db_session.flush()

        chain = DelegationChain(
            id=f"chain_intg_{time.time_ns()}",
            tenant_id=tenant.id,
            root_agent_id=agent.id,
            root_task="test",
            total_spend_usd=100.0,
        )
        db_session.add(chain)
        db_session.flush()

        for i in range(5):
            db_session.add(TokenUsage(
                id=f"tu_intg_{time.time_ns()}_{i}",
                agent_id=agent.id,
                tenant_id=tenant.id,
                chain_id=chain.id,
                cost_usd=20.0,
                total_tokens=100,
                billed=True,
            ))
        db_session.commit()

        results = _run_concurrently(
            lambda i: budget_service.check_budget_before_action(
                tenant_id=tenant.id,
                agent_id=agent.id,
                action="run_episode",
                chain_id=chain.id,
            )
        )

        assert len(results) == 10
        assert all(r["allowed"] is False for r in results)
        assert all("Fleet aggregate budget limit" in r["reason"] for r in results)

    def test_fleet_aggregate_under_cap_allows(
        self, budget_service, tenant_factory, db_session: Session
    ):
        """Fleet cap not reached → concurrent checks with chain_id allow."""
        tenant = tenant_factory()
        budget_service.spend_service.update_tenant_spend = lambda tid: {
            "current_spend_usd": 10.0,
            "budget_limit_usd": 100.0,
            "utilization_percent": 10.0,
        }

        agent = AgentRegistry(
            id=f"agent_root_{time.time_ns()}",
            name="Root Agent",
            category="Operations",
            module_path="operations.automations.inventory",
            class_name="InventoryAgent",
            tenant_id=tenant.id,
            status="autonomous",
        )
        db_session.add(agent)
        db_session.flush()

        chain = DelegationChain(
            id=f"chain_intg_{time.time_ns()}",
            tenant_id=tenant.id,
            root_agent_id=agent.id,
            root_task="test",
            total_spend_usd=1000.0,
        )
        db_session.add(chain)
        db_session.commit()

        results = _run_concurrently(
            lambda i: budget_service.check_budget_before_action(
                tenant_id=tenant.id,
                agent_id=agent.id,
                action="run_episode",
                chain_id=chain.id,
            )
        )

        assert len(results) == 10
        assert all(r["allowed"] is True for r in results)
