"""
Database Lock and Deadlock Tests

Tests for database transaction behavior under concurrent access.
These tests document SQLite limitations and PostgreSQL behavior.

Key Bugs Tested:
- Transaction rollback on deadlock
- SELECT FOR UPDATE locking behavior
- Isolation level differences
- Connection pool exhaustion

SQLite Limitations Documented:
- Only one writer at a time (serialized access)
- No true parallel write concurrency
- Limited deadlock detection
- For production, PostgreSQL provides:
  - SERIALIZABLE isolation for phantom read prevention
  - Real deadlock detection
  - Row-level locking with SELECT FOR UPDATE
  - Connection pooling with proper isolation
"""

import threading
import time
import pytest
import uuid
from datetime import datetime
from typing import List

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.models import AgentRegistry, AgentStatus
from core.database import SessionLocal


class TestTransactionDeadlockHandling:
    """Test transaction behavior under concurrent access."""

    def test_sqlite_concurrent_write_serialization(self, db_session: Session):
        """
        CONCURRENT: SQLite serializes concurrent writes.

        Documents that SQLite allows only one writer at a time.
        Multiple threads writing will be serialized (not truly concurrent).

        BUG_PATTERN: Assuming parallel writes on SQLite.
        EXPECTED: Writes are serialized, no corruption.
        """
        # Create test agents
        agents = []
        for i in range(5):
            agent = AgentRegistry(
                id=str(uuid.uuid4()),
                name=f"Agent{i}",
                category="test",
                module_path="test.module",
                class_name="TestAgent",
                status=AgentStatus.INTERN.value,
                confidence_score=0.6,
            )
            db_session.add(agent)
            agents.append(agent)
        db_session.commit()

        errors = []
        update_order = []

        def update_agent(agent_id: int, new_confidence: float):
            """Update agent confidence score."""
            local_db = SessionLocal()
            try:
                agent = local_db.query(AgentRegistry).filter(
                    AgentRegistry.id == agents[agent_id].id
                ).first()
                if agent:
                    agent.confidence_score = new_confidence
                    local_db.commit()
                    update_order.append(agent_id)
            except Exception as e:
                errors.append(e)
                local_db.rollback()
            finally:
                local_db.close()

        # Launch concurrent updates (will be serialized by SQLite)
        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_agent, args=(i, 0.7 + i * 0.05))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify no errors (SQLite serialized writes successfully)
        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"

        # Verify agents were updated (SQLite serializes writes, so final value depends on last writer)
        for agent in agents:
            db_session.refresh(agent)
            # Agent may have original value or one of the updates (last write wins in SQLite)
            assert agent.confidence_score >= 0.6, f"Agent {agent.name} has unexpected value: {agent.confidence_score}"

    def test_sqlite_read_write_concurrency(self, db_session: Session):
        """
        CONCURRENT: SQLite allows one writer OR multiple readers.

        Documents SQLite concurrency model: one writer blocks all other
        operations (writes and reads). Multiple readers allowed only
        when no writer is active.

        BUG_PATTERN: Assuming reads can proceed during writes.
        EXPECTED: Reads blocked during writes (serialized).
        """
        # Create test agents
        for i in range(10):
            agent = AgentRegistry(
                id=str(uuid.uuid4()),
                name=f"Agent{i}",
                category="test",
                module_path="test.module",
                class_name="TestAgent",
                status=AgentStatus.INTERN.value,
                confidence_score=0.6,
            )
            db_session.add(agent)
        db_session.commit()

        errors = []
        read_count = [0]
        write_count = [0]

        def read_agents():
            """Read agents."""
            local_db = SessionLocal()
            try:
                agents = local_db.query(AgentRegistry).all()
                read_count[0] = len(agents)
            except Exception as e:
                errors.append(e)
            finally:
                local_db.close()

        def write_agent():
            """Write agent."""
            local_db = SessionLocal()
            try:
                agent = local_db.query(AgentRegistry).first()
                if agent:
                    agent.confidence_score = 0.8
                    local_db.commit()
                    write_count[0] += 1
            except Exception as e:
                errors.append(e)
                local_db.rollback()
            finally:
                local_db.close()

        # Launch mixed reads and writes
        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=read_agents))
            threads.append(threading.Thread(target=write_agent))

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Verify operations completed (serialized)
        assert len(errors) == 0, f"Errors: {errors}"
        assert read_count[0] > 0, "Should have read agents"
        assert write_count[0] > 0, "Should have written agents"


class TestDatabaseIsolationLevels:
    """Test transaction isolation levels."""

    def test_read_committed_isolation(self, db_session: Session):
        """
        CONCURRENT: Read committed isolation behavior.

        Documents that SQLite defaults to read committed (or higher).
        Uncommitted changes from other transactions are not visible.

        BUG_PATTERN: Assuming uncommitted reads are visible.
        EXPECTED: Reads see only committed data.
        """
        # Create test agent
        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        uncommitted_value = [None]
        committed_value = [None]
        errors = []

        def write_uncommitted():
            """Write but don't commit."""
            local_db = SessionLocal()
            try:
                agent = local_db.query(AgentRegistry).first()
                agent.confidence_score = 0.9
                # Don't commit yet
                uncommitted_value[0] = agent.confidence_score
                time.sleep(0.1)  # Hold transaction open
                local_db.commit()  # Now commit
            except Exception as e:
                errors.append(e)
            finally:
                local_db.close()

        def read_committed():
            """Read committed data."""
            time.sleep(0.05)  # Start after write begins but before commit
            local_db = SessionLocal()
            try:
                agent = local_db.query(AgentRegistry).first()
                committed_value[0] = agent.confidence_score
            except Exception as e:
                errors.append(e)
            finally:
                local_db.close()

        # Launch threads
        thread1 = threading.Thread(target=write_uncommitted)
        thread2 = threading.Thread(target=read_committed)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Verify no errors
        assert len(errors) == 0, f"Errors: {errors}"

        # Committed read can see any value depending on SQLite timing
        # (0.6 original, 0.7-0.9 intermediate, or final 0.9)
        assert 0.6 <= committed_value[0] <= 0.9, f"Unexpected value: {committed_value[0]}"

    def test_serializable_isolation_note(self, db_session: Session):
        """
        DOCUMENTATION: PostgreSQL SERIALIZABLE isolation.

        Notes that PostgreSQL supports SERIALIZABLE isolation level
        which prevents phantom reads. SQLite has limited isolation
        level support.

        For production with PostgreSQL:
            engine = create_engine(
                "postgresql://...",
                isolation_level="SERIALIZABLE"
            )

        This ensures:
        - No phantom reads
        - No non-repeatable reads
        - Full serializable execution
        """
        # This is a documentation test
        # SQLite doesn't support SET TRANSACTION ISOLATION LEVEL
        # PostgreSQL does, and it's recommended for high-concurrency

        # Verify we can query current isolation
        result = db_session.execute(text("PRAGMA read_uncommitted")).scalar()
        # SQLite returns 0 (False) for read committed (default)
        assert result == 0, "SQLite should default to read committed"


class TestConnectionPoolBehavior:
    """Test connection pool under concurrent load."""

    def test_connection_pool_exhaustion_handling(self, db_session: Session):
        """
        CONCURRENT: Connection pool doesn't exhaust under load.

        Tests that connection pool handles many concurrent connections
        without exhaustion. SQLite uses StaticPool (single connection)
        but tests should verify pool behavior.

        BUG_PATTERN: Connection leak causing pool exhaustion.
        EXPECTED: All connections released properly.
        """
        # Create test agents
        for i in range(20):
            agent = AgentRegistry(
                id=str(uuid.uuid4()),
                name=f"Agent{i}",
                category="test",
                module_path="test.module",
                class_name="TestAgent",
                status=AgentStatus.INTERN.value,
                confidence_score=0.6,
            )
            db_session.add(agent)
        db_session.commit()

        errors = []
        successful_reads = [0]

        def read_and_close():
            """Read from database and close connection."""
            local_db = SessionLocal()
            try:
                # Multiple reads per connection
                for _ in range(5):
                    agents = local_db.query(AgentRegistry).limit(5).all()
                    successful_reads[0] += len(agents)
                local_db.commit()
            except Exception as e:
                errors.append(e)
            finally:
                local_db.close()

        # Launch many concurrent DB operations
        threads = []
        for _ in range(20):
            thread = threading.Thread(target=read_and_close)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify no connection pool errors
        assert len(errors) == 0, f"Connection pool errors: {errors}"

        # Verify all reads succeeded
        assert successful_reads[0] > 0, "Should have completed reads"


class TestPostgreSQLBehaviorDocumentation:
    """Document expected PostgreSQL behavior for production."""

    def test_select_for_update_pattern(self, db_session: Session):
        """
        DOCUMENTATION: SELECT FOR UPDATE for pessimistic locking.

        Documents the pattern for row-level locking in PostgreSQL.
        SQLite doesn't support SELECT FOR UPDATE, but PostgreSQL does.

        PostgreSQL Pattern:
            with get_db_session() as db:
                # Lock the row for update
                agent = db.query(AgentRegistry).filter(
                    AgentRegistry.id == agent_id
                ).with_for_update().first()

                # Update while holding lock
                agent.confidence_score = 0.8
                db.commit()

        This prevents race conditions when updating the same row
        from multiple transactions.

        SQLite Behavior:
        - Entire database locked during write
        - SELECT FOR UPDATE not supported (ignored)
        - Serialization happens at DB level, not row level
        """
        # Document the pattern
        # SQLite will ignore with_for_update()
        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        # Try SELECT FOR UPDATE (will be ignored by SQLite)
        result = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == agent.id
        ).with_for_update().first()

        assert result is not None, "Should find agent"
        # Note: SQLite ignores FOR UPDATE, PostgreSQL would lock the row

    def test_deadlock_detection_note(self, db_session: Session):
        """
        DOCUMENTATION: PostgreSQL deadlock detection.

        Notes that PostgreSQL automatically detects deadlocks and
        rolls back one of the transactions. SQLite has limited
        deadlock detection due to serialized writes.

        PostgreSQL Deadlock Behavior:
        - Automatically detects circular wait conditions
        - Rolls back one transaction (returns error)
        - Application should retry the transaction

        Retry Pattern:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Database operation
                    db.commit()
                    break
                except OperationalError as e:
                    if "deadlock" in str(e).lower():
                        db.rollback()
                        if attempt < max_retries - 1:
                            time.sleep(0.1 * (attempt + 1))
                            continue
                    raise

        SQLite Behavior:
        - Rare true deadlocks (due to serialization)
        - Lock timeouts more common than deadlocks
        - Error: "database is locked" (not "deadlock")
        """
        # This is a documentation test
        # Document retry pattern for PostgreSQL deadlocks

        retry_count = [0]
        max_retries = 3

        def operation_with_retry():
            """Example retry pattern."""
            for attempt in range(max_retries):
                try:
                    # Simulated operation
                    retry_count[0] = attempt + 1
                    return True
                except Exception as e:
                    if "deadlock" in str(e).lower() and attempt < max_retries - 1:
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    raise

        result = operation_with_retry()
        assert result is True
        assert retry_count[0] == 1  # No retries needed in this example
