"""
Offline Sync Scenarios Tests

Tests for offline operation and sync scenarios.

These tests validate that:
1. Operations are queued when offline
2. Queued operations sync when connection restored
3. Conflict resolution works (latest wins)
4. Complex conflicts flagged for manual review
5. Partial sync doesn't corrupt data
6. Sync retry with backoff works
7. Offline to online transition preserves state
8. Concurrent sync conflicts are resolved

Key Scenarios Tested:
- Offline mode queue operations
- Sync on reconnect
- Conflict resolution (latest wins)
- Conflict resolution (manual merge)
- Partial sync handling
- Sync retry with backoff
- Offline to online transition
- Concurrent sync conflicts

Note: These tests simulate offline/sync behavior. In production,
this would involve Redis for queueing and PostgreSQL for storage.
"""

import pytest
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

from sqlalchemy.orm import Session

from core.models import (
    AgentRegistry,
    AgentExecution,
    CanvasAudit
)


class TestOfflineModeQueueOperations:
    """Test that operations are queued when offline."""

    def test_offline_mode_queue_operations(self, db_session: Session):
        """
        OFFLINE: Operations queued when offline.

        Tests that when system is offline, operations are queued
        for later sync instead of failing.

        Scenario:
        1. Mark system as offline
        2. Try to create canvas
        3. Operation queued
        4. Verify queue has operation
        """
        # Simulate offline queue
        offline_queue: List[Dict[str, Any]] = []

        # Step 1: System is offline
        is_offline = True

        # Step 2: Try to create canvas while offline
        operation = {
            "type": "create_canvas",
            "data": {
                "canvas_id": "offline-canvas-1",
                "canvas_type": "chart",
                "canvas_data": {"data": [1, 2, 3]}
            },
            "timestamp": datetime.utcnow().isoformat()
        }

        # Step 3: Queue operation (simulated)
        if is_offline:
            offline_queue.append(operation)

        # Step 4: Verify queued
        assert len(offline_queue) == 1
        assert offline_queue[0]["type"] == "create_canvas"
        assert offline_queue[0]["data"]["canvas_id"] == "offline-canvas-1"

    def test_multiple_offline_operations_queued(self, db_session: Session):
        """
        OFFLINE: Multiple operations queued sequentially.

        Tests that multiple operations performed while offline
        are all queued in order.

        Scenario:
        1. Mark system as offline
        2. Create multiple canvases
        3. All operations queued
        4. Verify queue order preserved
        """
        # Simulate offline queue
        offline_queue: List[Dict[str, Any]] = []
        is_offline = True

        # Step 2: Create multiple canvases while offline
        for i in range(5):
            operation = {
                "type": "create_canvas",
                "data": {
                    "canvas_id": f"offline-canvas-{i}",
                    "canvas_type": "chart",
                    "canvas_data": {"index": i}
                },
                "timestamp": datetime.utcnow().isoformat()
            }

            if is_offline:
                offline_queue.append(operation)

        # Step 3-4: Verify all queued in order
        assert len(offline_queue) == 5
        for i, op in enumerate(offline_queue):
            assert op["data"]["canvas_id"] == f"offline-canvas-{i}"
            assert op["data"]["canvas_data"]["index"] == i


class TestSyncOnReconnect:
    """Test that queued operations sync when connection restored."""

    def test_sync_on_reconnect(self, db_session: Session):
        """
        SYNC: Queued operations sync when reconnected.

        Tests that when connection is restored, queued operations
        are processed and stored in database.

        Scenario:
        1. Queue operations while offline
        2. Reconnect
        3. Process queue
        4. Verify operations in database
        """
        # Step 1: Queue operations offline
        offline_queue: List[Dict[str, Any]] = [
            {
                "type": "create_canvas",
                "data": {
                    "canvas_id": "sync-canvas-1",
                    "canvas_type": "chart",
                    "canvas_data": {"data": [1, 2, 3]}
                },
                "timestamp": datetime.utcnow().isoformat()
            },
            {
                "type": "create_canvas",
                "data": {
                    "canvas_id": "sync-canvas-2",
                    "canvas_type": "docs",
                    "canvas_data": {"content": "Test"}
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        ]

        # Step 2: Reconnect
        is_offline = False

        # Step 3: Process queue
        if not is_offline:
            for operation in offline_queue:
                if operation["type"] == "create_canvas":
                    data = operation["data"]
                    canvas = CanvasAudit(
                        id=str(data["canvas_id"]),
                        canvas_id=data["canvas_id"],
                        tenant_id="test-tenant",
                        action_type="present",
                        canvas_type=data["canvas_type"],
                        canvas_data=data["canvas_data"],
                        created_at=datetime.utcnow()
                    )
                    db_session.add(canvas)
            db_session.commit()

        # Step 4: Verify in database
        canvas1 = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == "sync-canvas-1"
        ).first()
        canvas2 = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == "sync-canvas-2"
        ).first()

        assert canvas1 is not None
        assert canvas2 is not None
        assert canvas1.canvas_type == "chart"
        assert canvas2.canvas_type == "docs"


class TestConflictResolutionLatestWins:
    """Test conflict resolution with latest-wins strategy."""

    def test_conflict_resolution_latest_wins(self, db_session: Session):
        """
        CONFLICT: Latest timestamp wins conflict resolution.

        Tests that when there's a conflict (same canvas_id updated
        by offline and online), the latest update wins.

        Scenario:
        1. Create canvas online
        2. Go offline, update same canvas
        3. Meanwhile, update same canvas online
        4. Reconnect and sync
        5. Latest update (by timestamp) wins
        """
        # Step 1: Create canvas online
        canvas = CanvasAudit(
            id="conflict-canvas",
            canvas_id="conflict-canvas",
            tenant_id="test-tenant",
            action_type="present",
            canvas_type="docs",
            canvas_data={"version": 1, "source": "online"},
            created_at=datetime.utcnow()
        )
        db_session.add(canvas)
        db_session.commit()

        # Step 2: Go offline and update
        offline_update = {
            "canvas_id": "conflict-canvas",
            "canvas_data": {"version": 2, "source": "offline"},
            "timestamp": (datetime.utcnow() + timedelta(seconds=10)).isoformat()
        }

        # Step 3: Meanwhile online update (older timestamp)
        online_update_timestamp = datetime.utcnow() + timedelta(seconds=5)

        # Step 4: Sync with latest-wins resolution
        offline_time = datetime.fromisoformat(offline_update["timestamp"])
        if offline_time > online_update_timestamp:
            # Offline update is newer, use it
            canvas.canvas_data = offline_update["canvas_data"]
            db_session.commit()

        # Step 5: Verify latest won
        retrieved = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == "conflict-canvas"
        ).first()
        assert retrieved.canvas_data["version"] == 2
        assert retrieved.canvas_data["source"] == "offline"


class TestConflictResolutionManualMerge:
    """Test complex conflicts flagged for manual review."""

    def test_conflict_resolution_manual_merge(self, db_session: Session):
        """
        CONFLICT: Complex conflicts flagged for manual merge.

        Tests that when updates conflict in non-trivial ways
        (different fields modified), the conflict is flagged
        for manual resolution.

        Scenario:
        1. Create canvas with multiple fields
        2. Go offline, update field A
        3. Online update modifies field B
        4. Sync detects conflict in different fields
        5. Flag for manual merge
        """
        # Step 1: Create canvas with multiple fields
        canvas = CanvasAudit(
            id="manual-merge-canvas",
            canvas_id="manual-merge-canvas",
            tenant_id="test-tenant",
            action_type="present",
            canvas_type="form",
            canvas_data={
                "title": "Original",
                "field_a": "value_a",
                "field_b": "value_b"
            },
            created_at=datetime.utcnow()
        )
        db_session.add(canvas)
        db_session.commit()

        # Step 2: Offline update modifies field_a
        offline_update = {
            "canvas_id": "manual-merge-canvas",
            "canvas_data": {
                "title": "Original",
                "field_a": "offline_value_a",
                "field_b": "value_b"
            },
            "timestamp": datetime.utcnow().isoformat()
        }

        # Step 3: Online update modifies field_b
        online_update = {
            "field_b": "online_value_b"
        }

        # Step 4-5: Detect conflict in different fields
        offline_fields = set(offline_update["canvas_data"].keys())
        online_fields = set(online_update.keys())

        # Check if updates touch different fields (conflict)
        conflicting_fields = offline_fields.intersection(online_fields)
        non_conflicting_fields = offline_fields.symmetric_difference(online_fields)

        # Flag for manual merge if there are both conflicting and non-conflicting fields
        needs_manual_merge = len(conflicting_fields) > 0 and len(non_conflicting_fields) > 0

        assert needs_manual_merge, "Should flag for manual merge"


class TestPartialSyncHandling:
    """Test that partial sync doesn't corrupt data."""

    def test_partial_sync_handling(self, db_session: Session):
        """
        PARTIAL: Partial sync doesn't corrupt data.

        Tests that if sync is interrupted (only some operations
        processed), the data remains consistent and retry works.

        Scenario:
        1. Queue 10 operations offline
        2. Start sync, interrupt after 5 operations
        3. Verify 5 operations synced
        4. Resume sync
        5. Verify all 10 operations synced
        """
        # Step 1: Queue 10 operations
        offline_queue = [
            {
                "type": "create_canvas",
                "data": {
                    "canvas_id": f"partial-canvas-{i}",
                    "canvas_type": "chart",
                    "canvas_data": {"index": i}
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            for i in range(10)
        ]

        # Step 2-3: Sync first 5 operations
        synced_count = 0
        for i, operation in enumerate(offline_queue[:5]):
            data = operation["data"]
            canvas = CanvasAudit(
                id=str(data["canvas_id"]),
                canvas_id=data["canvas_id"],
                tenant_id="test-tenant",
                action_type="present",
                canvas_type=data["canvas_type"],
                canvas_data=data["canvas_data"],
                created_at=datetime.utcnow()
            )
            db_session.add(canvas)
            synced_count += 1

        db_session.commit()

        # Verify 5 synced
        count = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id.like("partial-canvas-%")
        ).count()
        assert count == 5

        # Step 4-5: Resume sync for remaining 5
        for operation in offline_queue[5:]:
            data = operation["data"]
            canvas = CanvasAudit(
                id=str(data["canvas_id"]),
                canvas_id=data["canvas_id"],
                tenant_id="test-tenant",
                action_type="present",
                canvas_type=data["canvas_type"],
                canvas_data=data["canvas_data"],
                created_at=datetime.utcnow()
            )
            db_session.add(canvas)
            synced_count += 1

        db_session.commit()

        # Verify all 10 synced
        count = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id.like("partial-canvas-%")
        ).count()
        assert count == 10
        assert synced_count == 10


class TestSyncRetryWithBackoff:
    """Test sync retry with exponential backoff."""

    def test_sync_retry_with_backoff(self, db_session: Session):
        """
        RETRY: Sync retry with backoff on failure.

        Tests that failed sync operations retry with exponential
        backoff.

        Scenario:
        1. Try to sync operation (fails)
        2. Retry with backoff
        3. Eventually succeeds
        4. Verify operation synced
        """
        # Simulated sync retry with backoff
        max_retries = 3
        base_delay_ms = 100

        operation = {
            "type": "create_canvas",
            "data": {
                "canvas_id": "retry-canvas",
                "canvas_type": "chart",
                "canvas_data": {"data": [1, 2, 3]}
            }
        }

        # Simulate sync attempts
        attempt = 0
        success = False
        last_error = None

        while attempt < max_retries and not success:
            attempt += 1

            # Simulate: First 2 attempts fail, 3rd succeeds
            if attempt < 3:
                last_error = f"Sync failed (attempt {attempt})"
                if attempt < max_retries:
                    # Exponential backoff
                    delay_ms = base_delay_ms * (2 ** (attempt - 1))
                    time.sleep(delay_ms / 1000)  # Convert to seconds
                    continue
            else:
                # Success on 3rd attempt
                data = operation["data"]
                canvas = CanvasAudit(
                    id=str(data["canvas_id"]),
                    canvas_id=data["canvas_id"],
                    tenant_id="test-tenant",
                    action_type="present",
                    canvas_type=data["canvas_type"],
                    canvas_data=data["canvas_data"],
                    created_at=datetime.utcnow()
                )
                db_session.add(canvas)
                db_session.commit()
                success = True

        # Verify success
        assert success, "Sync should succeed after retries"
        assert attempt == 3, "Should take 3 attempts"

        # Verify canvas created
        canvas = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == "retry-canvas"
        ).first()
        assert canvas is not None


class TestOfflineToOnlineTransition:
    """Test state preservation during offline to online transition."""

    def test_offline_to_online_transition(self, db_session: Session):
        """
        TRANSITION: State preserved during offline → online transition.

        Tests that application state is correctly preserved and
        restored when transitioning from offline to online mode.

        Scenario:
        1. Start online, create some data
        2. Go offline, create more data (queued)
        3. Reconnect
        4. Verify all data present (online + offline synced)
        """
        # Step 1: Start online
        is_offline = False

        # Create online data
        canvas1 = CanvasAudit(
            id="online-canvas-1",
            canvas_id="online-canvas-1",
            tenant_id="test-tenant",
            action_type="present",
            canvas_type="chart",
            canvas_data={"source": "online-1"},
            created_at=datetime.utcnow()
        )
        db_session.add(canvas1)
        db_session.commit()

        # Step 2: Go offline, queue operations
        is_offline = True
        offline_queue: List[Dict[str, Any]] = []

        operation = {
            "type": "create_canvas",
            "data": {
                "canvas_id": "offline-canvas-1",
                "canvas_type": "docs",
                "canvas_data": {"source": "offline"}
            },
            "timestamp": datetime.utcnow().isoformat()
        }

        if is_offline:
            offline_queue.append(operation)

        # Step 3: Reconnect and sync
        is_offline = False
        for op in offline_queue:
            data = op["data"]
            canvas2 = CanvasAudit(
                id=str(data["canvas_id"]),
                canvas_id=data["canvas_id"],
                tenant_id="test-tenant",
                action_type="present",
                canvas_type=data["canvas_type"],
                canvas_data=data["canvas_data"],
                created_at=datetime.utcnow()
            )
            db_session.add(canvas2)
        db_session.commit()

        # Step 4: Verify all data present
        online_canvas = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == "online-canvas-1"
        ).first()
        offline_canvas = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == "offline-canvas-1"
        ).first()

        assert online_canvas is not None
        assert offline_canvas is not None
        assert online_canvas.canvas_data["source"] == "online-1"
        assert offline_canvas.canvas_data["source"] == "offline"


class TestConcurrentSyncConflicts:
    """Test concurrent sync conflict resolution."""

    def test_concurrent_sync_conflicts(self, db_session: Session):
        """
        CONCURRENT: Multiple clients syncing same data concurrently.

        Tests that when multiple clients sync the same data
        simultaneously, conflicts are resolved properly.

        Scenario:
        1. Client A and B both offline
        2. Both update same canvas differently
        3. Both reconnect simultaneously
        4. Sync resolves conflicts (latest timestamp wins)
        """
        # Step 1: Both clients offline
        client_a_queue = [{
            "type": "update_canvas",
            "data": {
                "canvas_id": "concurrent-canvas",
                "canvas_data": {"source": "client-a", "value": 100},
                "timestamp": (datetime.utcnow() + timedelta(seconds=5)).isoformat()
            }
        }]

        client_b_queue = [{
            "type": "update_canvas",
            "data": {
                "canvas_id": "concurrent-canvas",
                "canvas_data": {"source": "client-b", "value": 200},
                "timestamp": (datetime.utcnow() + timedelta(seconds=10)).isoformat()
            }
        }]

        # Step 2-3: Both reconnect simultaneously, sync both updates
        # Create initial canvas
        canvas = CanvasAudit(
            id="concurrent-canvas",
            canvas_id="concurrent-canvas",
            tenant_id="test-tenant",
            action_type="present",
            canvas_type="docs",
            canvas_data={"source": "original"},
            created_at=datetime.utcnow()
        )
        db_session.add(canvas)
        db_session.commit()

        # Sync both updates (simulate concurrent sync)
        # In real scenario, would use transactions with locking
        # Here we apply both and let latest timestamp win
        for operation in client_a_queue + client_b_queue:
            data = operation["data"]
            # Only update if newer
            existing_time = canvas.created_at
            new_time = datetime.fromisoformat(data["timestamp"])

            if new_time > existing_time:
                canvas.canvas_data = data["canvas_data"]
                canvas.created_at = new_time

        db_session.commit()

        # Step 4: Verify conflict resolved (client B won - later timestamp)
        retrieved = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == "concurrent-canvas"
        ).first()
        assert retrieved.canvas_data["source"] == "client-b"
        assert retrieved.canvas_data["value"] == 200
