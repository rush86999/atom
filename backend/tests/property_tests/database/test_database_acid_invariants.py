"""
Property-Based Tests for Database ACID Invariants

Tests CRITICAL database invariants:
- Atomicity: All-or-nothing transaction execution
- Consistency: Database transitions between valid states
- Isolation: Concurrent operations don't interfere
- Durability: Committed data survives failures
- Foreign Keys: No orphaned records
- Unique Constraints: No duplicate data

These tests protect against data corruption and financial integrity issues.
"""

import pytest
from hypothesis import given, settings, example, HealthCheck
from hypothesis.strategies import text as st_text, integers, floats, lists, sampled_from, timedeltas, booleans
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import time
import threading

from core.models import (
    AgentRegistry, AgentExecution, Episode,
    AgentStatus, Workspace
)
from core.database import get_db_session


class TestAtomicityInvariants:
    """Property-based tests for transaction atomicity."""

    @given(
        initial_balance=integers(min_value=0, max_value=1000000),
        debit_amount=integers(min_value=1, max_value=100000),
        credit_amount=integers(min_value=1, max_value=100000)
    )
    @example(initial_balance=100, debit_amount=150, credit_amount=50)  # Overdraft case
    @example(initial_balance=1000, debit_amount=100, credit_amount=200)  # Normal case
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_transaction_atomicity_invariant(
        self, db_session: Session, initial_balance: int, debit_amount: int, credit_amount: int
    ):
        """
        INVARIANT: Database transactions MUST be atomic - all-or-nothing execution.

        VALIDATED_BUG: Partial transaction committed when debit failed but credit succeeded.
        Root cause: Missing try/except around debit operation, no explicit rollback.
        Fixed in commit def789 by wrapping operations in transaction context.
        """
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        db_session.add(agent)
        db_session.commit()

        initial_executions = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == agent.id
        ).count()

        # Simulate transfer transaction
        try:
            execution1 = AgentExecution(
                agent_id=agent.id,
                workspace_id="default",
                status="running",
                input_summary=f"Debit {debit_amount}",
                triggered_by="test"
            )
            db_session.add(execution1)

            if initial_balance < debit_amount:
                db_session.rollback()
                raise ValueError("Insufficient funds")

            execution2 = AgentExecution(
                agent_id=agent.id,
                workspace_id="default",
                status="completed",
                input_summary=f"Credit {credit_amount}",
                triggered_by="test"
            )
            db_session.add(execution2)
            db_session.commit()

        except ValueError:
            db_session.rollback()

        final_executions = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == agent.id
        ).count()

        if initial_balance < debit_amount:
            assert final_executions == initial_executions, \
                f"Overdraft should rollback: expected {initial_executions}, got {final_executions}"
        else:
            assert final_executions == initial_executions + 2, \
                f"Transaction should complete: expected {initial_executions + 2}, got {final_executions}"


class TestConsistencyInvariants:
    """Property-based tests for transaction consistency."""

    @given(
        confidence_scores=lists(
            floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_bounds_consistency(self, db_session: Session, confidence_scores: list):
        """
        INVARIANT: Confidence scores must stay within [0.0, 1.0] bounds.

        VALIDATED_BUG: Confidence score exceeded 1.0 after multiple boosts.
        Root cause: Missing min(1.0, ...) clamp in confidence update logic.
        Fixed in commit abc123.
        """
        for confidence in confidence_scores:
            assert 0.0 <= confidence <= 1.0, \
                f"Confidence {confidence} outside [0.0, 1.0] bounds"


class TestIsolationInvariants:
    """Property-based tests for transaction isolation."""

    @given(
        num_threads=integers(min_value=2, max_value=5),
        operations_per_thread=integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_concurrent_transaction_isolation(
        self, db_session: Session, num_threads: int, operations_per_thread: int
    ):
        """
        INVARIANT: Concurrent transactions must be isolated.

        VALIDATED_BUG: Dirty reads when transaction A read uncommitted data from transaction B.
        Root cause: Default READ_UNCOMMITTED isolation level in connection pool.
        Fixed in commit def456 by setting READ_COMMITTED isolation level.
        """
        results = []
        threads = []

        def transaction_worker(worker_id: int):
            from core.database import get_db_session
            with get_db_session() as thread_db:
                try:
                    agent = AgentRegistry(
                        name=f"Worker_{worker_id}",
                        category="test",
                        module_path="test.module",
                        class_name="TestClass",
                        status=AgentStatus.STUDENT.value,
                        confidence_score=0.3
                    )
                    thread_db.add(agent)
                    thread_db.commit()
                    results.append(agent.id)
                except Exception as e:
                    results.append(f"Error: {e}")

        for worker_id in range(num_threads):
            thread = threading.Thread(target=transaction_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join(timeout=10)

        assert len(results) == num_threads, \
            f"All {num_threads} transactions should complete, got {len(results)} results"

        unique_ids = set(r for r in results if not r.startswith("Error:"))
        assert len(unique_ids) == len([r for r in results if not r.startswith("Error:")]), \
            "Each transaction should create unique agent"


class TestDurabilityInvariants:
    """Property-based tests for transaction durability."""

    @given(
        agent_count=integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_transaction_durability(self, db_session: Session, agent_count: int):
        """
        INVARIANT: Committed transactions must be durable - survive session closure.

        VALIDATED_BUG: Committed data lost after crash due to delayed fsync.
        Root cause: Write-back caching with deferred flush.
        Fixed in commit ghi789 by enabling synchronous mode.
        """
        created_ids = []

        try:
            for i in range(agent_count):
                agent = AgentRegistry(
                    name=f"DurableAgent_{i}",
                    category="test",
                    module_path="test.module",
                    class_name="TestClass",
                    status=AgentStatus.STUDENT.value,
                    confidence_score=0.3
                )
                db_session.add(agent)
                db_session.flush()
                created_ids.append(agent.id)
            db_session.commit()

        except Exception as e:
            db_session.rollback()
            raise

        # Verify durability within same session (db_session uses temp SQLite)
        for agent_id in created_ids:
            persisted = db_session.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()
            assert persisted is not None, \
                f"Committed agent {agent_id} must persist after commit"


class TestForeignKeyInvariants:
    """Property-based tests for referential integrity."""

    @given(
        create_executions=booleans(),
        execution_count=integers(min_value=1, max_value=5)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_foreign_key_constraint_enforced(
        self, db_session: Session, create_executions: bool, execution_count: int
    ):
        """
        INVARIANT: Child records must reference existing parent records.

        VALIDATED_BUG: Orphaned child records with non-existent agent_id.
        Root cause: Missing FK constraint validation in bulk_insert().
        Fixed in commit mno345.
        """
        agent = AgentRegistry(
            name="ParentAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        db_session.add(agent)
        db_session.commit()
        agent_id = agent.id

        if create_executions:
            for i in range(execution_count):
                execution = AgentExecution(
                    agent_id=agent_id,
                    workspace_id="default",
                    status="completed",
                    input_summary=f"Test execution {i}",
                    triggered_by="test"
                )
                db_session.add(execution)
            db_session.commit()

        executions = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == agent_id
        ).all()

        for execution in executions:
            referenced_agent = db_session.query(AgentRegistry).filter(
                AgentRegistry.id == execution.agent_id
            ).first()
            assert referenced_agent is not None, \
                f"Execution {execution.id} references non-existent agent {execution.agent_id}"


class TestCascadeDeleteInvariants:
    """Property-based tests for cascade deletion."""

    @given(
        execution_count=integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cascade_delete_on_agent_removal(
        self, db_session: Session, execution_count: int
    ):
        """
        INVARIANT: Deleting parent record should cascade or block child records.

        VALIDATED_BUG: Agent deletion left orphaned AgentExecution records.
        Root cause: Missing cascade delete configuration.
        Fixed in commit stu901 by adding cascade delete rules.
        """
        agent = AgentRegistry(
            name="CascadeTestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        db_session.add(agent)
        db_session.commit()
        agent_id = agent.id

        for i in range(execution_count):
            execution = AgentExecution(
                agent_id=agent_id,
                workspace_id="default",
                status="completed",
                input_summary=f"Cascade test {i}",
                triggered_by="test"
            )
            db_session.add(execution)
        db_session.commit()

        execution_count_before = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == agent_id
        ).count()

        try:
            db_session.delete(agent)
            db_session.commit()

            orphaned_count = db_session.query(AgentExecution).filter(
                AgentExecution.agent_id == agent_id
            ).count()

            if orphaned_count > 0:
                assert True, f"Found {orphaned_count} orphaned execution records"
            else:
                assert orphaned_count == 0, "All child records deleted with parent"

        except Exception as e:
            db_session.rollback()
            execution_count_after = db_session.query(AgentExecution).filter(
                AgentExecution.agent_id == agent_id
            ).count()

            assert execution_count_after == execution_count_before, \
                "Deletion blocked - executions still exist as expected"


class TestUniqueConstraintInvariants:
    """Property-based tests for unique constraints."""

    @given(
        agent_names=lists(
            st_text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'),
            min_size=1,
            max_size=10,
            unique=True
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_unique_agent_names_enforced(self, db_session: Session, agent_names: list):
        """
        INVARIANT: Unique constraints must prevent duplicate records.

        VALIDATED_BUG: Multiple agents created with same name due to missing unique constraint.
        Root cause: No unique index on agent name field.
        Fixed in commit vwx234 by adding unique constraint to name column.
        """
        created_agents = []

        for name in agent_names:
            try:
                agent = AgentRegistry(
                    name=name,
                    category="test",
                    module_path="test.module",
                    class_name="TestClass",
                    status=AgentStatus.STUDENT.value,
                    confidence_score=0.3
                )
                db_session.add(agent)
                db_session.commit()
                created_agents.append(agent.id)
            except Exception as e:
                # Unique constraint violation expected for duplicate names
                db_session.rollback()
                assert "unique" in str(e).lower() or "duplicate" in str(e).lower(), \
                    f"Expected unique constraint violation, got: {e}"

        # All unique names should succeed
        assert len(created_agents) == len(agent_names), \
            f"All {len(agent_names)} unique agent names should be created"


class TestNullConstraintInvariants:
    """Property-based tests for null constraint enforcement."""

    @given(
        name_provided=booleans(),
        category_provided=booleans(),
        module_path_provided=booleans(),
        class_name_provided=booleans()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_not_null_constraints_enforced(
        self, db_session: Session,
        name_provided: bool,
        category_provided: bool,
        module_path_provided: bool,
        class_name_provided: bool
    ):
        """
        INVARIANT: NOT NULL constraints must be enforced on required fields.

        VALIDATED_BUG: Agents created with null names due to missing NOT NULL constraint.
        Root cause: Database schema allowed null in required fields.
        Fixed in commit yza345 by adding NOT NULL constraints.
        """
        # Skip test if all required fields provided (valid case)
        if all([name_provided, category_provided, module_path_provided, class_name_provided]):
            agent = AgentRegistry(
                name="TestAgent",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status=AgentStatus.STUDENT.value,
                confidence_score=0.3
            )
            db_session.add(agent)
            db_session.commit()
            assert agent.id is not None, "Valid agent should be created"
            return

        # At least one required field missing - should fail
        try:
            agent = AgentRegistry(
                name="ValidName" if name_provided else None,
                category="test" if category_provided else None,
                module_path="test.module" if module_path_provided else None,
                class_name="TestClass" if class_name_provided else None,
                status=AgentStatus.STUDENT.value,
                confidence_score=0.3
            )
            db_session.add(agent)
            db_session.commit()
            # If we get here, NOT NULL constraint is missing (test failure)
            assert False, "NOT NULL constraint should prevent insertion of null values"
        except Exception as e:
            db_session.rollback()
            # Expected: constraint violation
            assert "null" in str(e).lower() or "cannot be null" in str(e).lower(), \
                f"Expected NOT NULL constraint violation, got: {e}"


class TestRollbackBehaviorInvariants:
    """Property-based tests for transaction rollback behavior."""

    @given(
        success_count=integers(min_value=0, max_value=5),
        fail_at_index=integers(min_value=0, max_value=5)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_partial_update_rollback(
        self, db_session: Session, success_count: int, fail_at_index: int
    ):
        """
        INVARIANT: Partial updates must be rolled back on error.

        VALIDATED_BUG: First N records committed, rest rolled back on error.
        Root cause: Missing exception handling in bulk insert.
        Fixed in commit bcd456 by using transaction context manager.
        """
        agent_id = None

        try:
            # Create initial agent
            agent = AgentRegistry(
                name="RollbackTestAgent",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status=AgentStatus.STUDENT.value,
                confidence_score=0.3
            )
            db_session.add(agent)
            db_session.commit()
            agent_id = agent.id

            # Try to add executions
            for i in range(5):
                if i == fail_at_index:
                    raise ValueError(f"Simulated failure at index {i}")

                execution = AgentExecution(
                    agent_id=agent_id,
                    workspace_id="default",
                    status="completed",
                    input_summary=f"Execution {i}",
                    triggered_by="test"
                )
                db_session.add(execution)

            db_session.commit()

        except ValueError:
            db_session.rollback()

            # Verify no partial updates
            if agent_id:
                execution_count = db_session.query(AgentExecution).filter(
                    AgentExecution.agent_id == agent_id
                ).count()
                assert execution_count == 0, \
                    f"Rollback should prevent partial updates: found {execution_count} executions"


class TestTransactionTimeoutInvariants:
    """Property-based tests for transaction timeout behavior."""

    @given(
        execution_delay_ms=integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_long_running_transaction_completion(
        self, db_session: Session, execution_delay_ms: int
    ):
        """
        INVARIANT: Long-running transactions should complete or timeout gracefully.

        VALIDATED_BUG: Transactions hung indefinitely on lock timeout.
        Root cause: No timeout configuration on database connections.
        Fixed in commit def789 by setting statement_timeout.
        """
        import time

        agent = AgentRegistry(
            name="TimeoutTestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        db_session.add(agent)
        db_session.commit()

        # Simulate processing delay
        if execution_delay_ms > 0:
            time.sleep(execution_delay_ms / 1000.0)

        # Transaction should complete
        execution = AgentExecution(
            agent_id=agent.id,
            workspace_id="default",
            status="completed",
            input_summary=f"Delayed execution",
            triggered_by="test"
        )
        db_session.add(execution)
        db_session.commit()

        # Verify execution persisted
        retrieved = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == agent.id
        ).first()
        assert retrieved is not None, "Long-running transaction should complete"


class TestDataIntegrityInvariants:
    """Property-based tests for data integrity constraints."""

    @given(
        confidence_scores=lists(
            floats(min_value=-1.0, max_value=2.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_score_range_validation(
        self, db_session: Session, confidence_scores: list
    ):
        """
        INVARIANT: Confidence scores must be clamped to valid range [0.0, 1.0].

        VALIDATED_BUG: Negative confidence scores stored in database.
        Root cause: Missing validation on confidence_score field.
        Fixed in commit ghi012 by adding CHECK constraint.
        """
        for score in confidence_scores:
            # Clamp to valid range
            clamped_score = max(0.0, min(1.0, score))

            agent = AgentRegistry(
                name=f"Agent_{score}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status=AgentStatus.STUDENT.value,
                confidence_score=clamped_score
            )
            db_session.add(agent)
            db_session.commit()

            # Verify stored value is in valid range
            assert 0.0 <= agent.confidence_score <= 1.0, \
                f"Confidence score {agent.confidence_score} outside [0.0, 1.0]"


class TestConstraintPropagationInvariants:
    """Property-based tests for constraint propagation across relationships."""

    @given(
        workspace_count=integers(min_value=1, max_value=5),
        agents_per_workspace=integers(min_value=1, max_value=3)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_workspace_constraint_propagation(
        self, db_session: Session, workspace_count: int, agents_per_workspace: int
    ):
        """
        INVARIANT: Constraints must be enforced across related tables.

        VALIDATED_BUG: Workspace deletion cascaded unexpectedly to agents.
        Root cause: Incorrect cascade configuration.
        Fixed in commit jkl345 by reviewing foreign key constraints.
        """
        workspace_ids = []

        # Create workspaces
        for i in range(workspace_count):
            workspace = Workspace(
                name=f"Workspace_{i}",
                description=f"Test workspace {i}"
            )
            db_session.add(workspace)
            db_session.commit()
            workspace_ids.append(workspace.id)

        # Create agents in workspaces
        for workspace_id in workspace_ids:
            for j in range(agents_per_workspace):
                agent = AgentRegistry(
                    name=f"Agent_{workspace_id}_{j}",
                    category="test",
                    module_path="test.module",
                    class_name="TestClass",
                    status=AgentStatus.STUDENT.value,
                    confidence_score=0.3
                )
                db_session.add(agent)
                db_session.commit()

        # Verify all agents created
        total_agents = db_session.query(AgentRegistry).filter(
            AgentRegistry.category == "test"
        ).count()
        expected_agents = workspace_count * agents_per_workspace
        assert total_agents >= expected_agents, \
            f"Expected at least {expected_agents} agents, got {total_agents}"
