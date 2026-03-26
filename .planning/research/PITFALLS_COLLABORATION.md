# Domain Pitfalls: Real-Time Collaboration & Team Management

**Domain:** Real-Time Collaboration, Team Management, RBAC for Automation Platform
**Researched:** 2026-03-26
**Overall confidence:** MEDIUM (WebSearch unavailable, relying on training data and codebase analysis)

---

## Critical Pitfalls

Mistakes that cause rewrites, security breaches, data corruption, or major operational issues.

### Pitfall 1: WebSocket Race Conditions in Collaborative Editing

**What goes wrong:**
Multiple users edit the same workflow node simultaneously. Last-write-wins behavior causes data loss. User A changes node configuration while User B renames the node. User A's save overwrites User B's rename without warning.

**Why it happens:**
- In-memory `WebSocketConnectionManager` doesn't coordinate between multiple server instances
- Missing optimistic locking or version checks on workflow updates
- No operational transformation (OT) or conflict-free replicated data types (CRDT) for concurrent edits
- Database writes happen without checking if data changed since read

**Consequences:**
- **HIGH**: User work silently lost (poor UX, data corruption)
- Workflow executions fail due to inconsistent state
- Users lose trust in collaboration features
- Support tickets: "My changes disappeared!"

**Prevention:**
```python
# 1. Add version/optimistic locking to workflow models
class Workflow(Base):
    version = Column(Integer, default=1, nullable=False)
    updated_at = Column(DateTime, onupdate=func.now())

# 2. Check version on update
def update_workflow(workflow_id: str, updates: dict, expected_version: int, user_id: str):
    workflow = db.query(Workflow).filter(
        and_(
            Workflow.id == workflow_id,
            Workflow.version == expected_version  # Prevent stale updates
        )
    ).first()

    if not workflow:
        raise ConcurrentEditError("Workflow was modified by another user")

    workflow.version += 1
    # Apply updates...

# 3. Broadcast edit intent before committing
await websocket_manager.broadcast_edit_intent(
    workflow_id=workflow_id,
    user_id=user_id,
    node_id=node_id,
    edit_type="rename"
)
```

**Detection:**
- Support reports of "lost changes"
- Audit logs show overlapping edits from different users
- Version conflicts spike in production logs

**Phase to address:**
Phase 01 (Foundation Models & Basic RBAC) - Add versioning to Workflow model
Phase 02 (WebSocket Infrastructure) - Implement edit intent broadcasting

---

### Pitfall 2: Permission Escalation via WebSocket Message Spoofing

**What goes wrong:**
Attacker crafts WebSocket message claiming to be another user with higher privileges. System updates participant role to "admin" without verifying sender permissions. Attacker gains admin access to collaboration session.

**Why it happens:**
- WebSocket handler trusts `user_id` from client message without re-validating
- Missing authorization checks on WebSocket message handlers
- JWT tokens not validated on each WebSocket message (only on connection)
- No RBAC checks for collaboration actions (promote participant, change role)

**Consequences:**
- **CRITICAL**: Privilege escalation allows unauthorized workflow access
- Attacker can edit/delete workflows they shouldn't access
- Bypasses existing governance system
- Data breach requiring customer notification

**Prevention:**
```python
# 1. NEVER trust user_id from WebSocket messages
@app.websocket("/ws/collaboration/{session_id}")
async def collaboration_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str  # JWT token required
):
    # Validate token ONCE on connection
    user = await validate_token(token)
    user_id = user.id  # Store server-side

    # 2. Check permissions on EVERY action
    async for message in websocket:
        data = json.loads(message)

        # CRITICAL: Use server-side user_id, never from message
        if data["action"] == "promote_participant":
            # Check if user has permission to promote
            if not await can_promote_participant(user_id, session_id):
                await websocket.send_json({"error": "Unauthorized"})
                continue

            # Use server-side user_id for audit
            await promote_participant(
                session_id=session_id,
                target_user_id=data["target_user_id"],
                promoted_by=user_id  # Server-side, not from message
            )
```

**Detection:**
- Audit logs show user promoting themselves
- Role changes from non-admin users
- WebSocket messages with mismatched user_id vs. token

**Phase to address:**
Phase 02 (WebSocket Infrastructure) - Hardened WebSocket handlers with RBAC

---

### Pitfall 3: Memory Leaks from Orphaned WebSocket Connections

**What goes wrong:**
WebSocket connections accumulate without proper cleanup. Server memory grows until OOM kill. Users get "connection refused" errors. Existing WebSocket manager lacks heartbeat/ping mechanism.

**Why it happens:**
- Clients disconnect without sending close frame (network drops, browser close)
- No heartbeat/ping mechanism to detect dead connections
- `disconnect()` not called on connection errors
- In-memory dictionaries (`active_connections`, `connection_streams`) never cleaned up

**Consequences:**
- **HIGH**: Memory exhaustion requires server restart
- Degraded performance as connection tracking grows
- Broadcast operations slow down (iterating over dead connections)
- Production outage every 24-48 hours

**Prevention:**
```python
# 1. Add heartbeat/ping mechanism
@app.websocket("/ws/collaboration/{session_id}")
async def collaboration_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    user_id = get_user_from_token(websocket)

    # Track connection with timestamp
    await manager.connect(websocket, session_id, user_id)

    try:
        # Send ping every 30 seconds
        while True:
            try:
                # Wait for ping response with timeout
                await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                # Update last activity
                manager.update_last_activity(websocket)
            except asyncio.TimeoutError:
                # No response, disconnect
                logger.warning(f"Client {user_id} timed out")
                break
    finally:
        manager.disconnect(websocket)  # ALWAYS cleanup

# 2. Periodic cleanup task
async def cleanup_dead_connections():
    """Remove connections inactive for >2 minutes"""
    while True:
        await asyncio.sleep(60)  # Run every minute
        now = datetime.now()
        dead_connections = [
            ws for ws, info in manager.connection_info.items()
            if (now - info["last_activity"]).seconds > 120
        ]
        for ws in dead_connections:
            logger.warning(f"Cleaning up dead connection")
            manager.disconnect(ws)
```

**Detection:**
- Memory usage grows steadily over time
- `len(active_connections)` >> actual user count
- Connection timeouts in logs
- Server restarts required every 24-48 hours

**Phase to address:**
Phase 02 (WebSocket Infrastructure) - Implement heartbeat + cleanup

---

### Pitfall 4: Database Lock Contention from High-Frequency Updates

**What goes wrong:**
Collaboration session updates (cursor positions, heartbeats) write to database on every change. 10 users × 5 updates/second = 50 writes/second. Database locks cause latency spikes. Agent executions timeout waiting for locks.

**Why it happens:**
- `update_participant_heartbeat()` writes to DB every time
- No batching or debouncing for high-frequency updates
- Database row locks on participant updates block other operations
- Same transaction table used for both collaboration and agent execution

**Consequences:**
- **MEDIUM**: Agent execution latency spikes (500ms → 5s)
- Workflow editor becomes laggy (cursor updates slow)
- Database connection pool exhaustion
- Poor UX despite "real-time" features

**Prevention:**
```python
# 1. Use Redis for high-frequency data (cursor positions, heartbeats)
class CollaborationTracker:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.db = SessionLocal()

    async def update_cursor_position(self, session_id: str, user_id: str, position: dict):
        # Fast: Write to Redis with 2-minute TTL
        key = f"cursor:{session_id}:{user_id}"
        await self.redis.setex(key, 120, json.dumps(position))

        # Don't write to database for cursor updates

    async def update_heartbeat(self, session_id: str, user_id: str):
        # Fast: Redis heartbeat
        key = f"heartbeat:{session_id}:{user_id}"
        await self.redis.setex(key, 120, "1")

    # Periodic batch sync to database (every 30 seconds)
    async def sync_to_database(self):
        # Fetch all active sessions from Redis
        # Batch update to database
        # Reduces 50 writes/sec → 2 writes/30sec
        pass

# 2. Use separate database tables
# collab_session_state (high-frequency, Redis-backed)
# collab_audit_log (low-frequency, PostgreSQL)
# agent_execution (separate, no lock contention)
```

**Detection:**
- Database query latency spikes during collaboration
- Lock wait timeouts in PostgreSQL logs
- Agent execution metrics show increased latency
- `pg_stat_activity` shows many `UPDATE collaboration_session_participant` waiting

**Phase to address:**
Phase 03 (Real-Time Presence & Activity) - Redis-backed state management

---

### Pitfall 5: RBAC Bypass via Missing Ownership Checks

**What goes wrong:**
User creates share link for workflow they don't own. System checks `can_view` but not `is_owner`. User shares workspace admin's workflow with external guest. Data leak.

**Why it happens:**
- RBAC checks `user_role` but not `resource_ownership`
- Missing `created_by` validation on share operations
- Authorization logic assumes role implies ownership (false)
- Workspace admin can share ANY workflow, not just their own

**Consequences:**
- **CRITICAL**: Data leak via unauthorized sharing
- Users share workflows they don't own
- Guests access restricted workflows
- Compliance violation (GDPR, SOC2)

**Prevention:**
```python
# 1. Separate permission checks
def can_share_workflow(user_id: str, workflow_id: str) -> bool:
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()

    # Check ownership OR explicit sharing permission
    if workflow.created_by == user_id:
        return True  # Owner can always share

    # Check if user has explicit share permission
    share_permission = db.query(WorkflowShare).filter(
        and_(
            WorkflowShare.workflow_id == workflow_id,
            WorkflowShare.shared_with == user_id,
            WorkflowShare.permissions["can_share"].astext == "true"
        )
    ).first()

    return share_permission is not None

# 2. Authorization decorator
def require_ownership(permission: str):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            user_id = get_current_user()
            resource_id = kwargs["workflow_id"]

            # Check BOTH role + ownership
            if not has_ownership(user_id, resource_id, permission):
                raise HTTPException(403, "Not authorized")

            return await func(*args, **kwargs)
        return wrapper
    return decorator

# 3. Use for share operations
@app.post("/workflows/{workflow_id}/share")
@require_ownership("can_share")
async def create_workflow_share(workflow_id: str, ...):
    # Guaranteed user owns workflow or has explicit share permission
    pass
```

**Detection:**
- Audit logs show non-owners sharing workflows
- Share links created for workflows user didn't create
- Guest access to restricted workflows

**Phase to address:**
Phase 01 (Foundation Models & Basic RBAC) - Ownership-based authorization

---

## Moderate Pitfalls

Issues that cause significant problems but are recoverable.

### Pitfall 6: Broken Collaboration State After Server Restart

**What goes wrong:**
Server restarts (deployment, crash). All WebSocket connections dropped. In-memory collaboration state (active users, cursor positions, edit locks) lost. Users see stale "5 users editing" but nobody is actually there.

**Why it happens:**
- `WebSocketConnectionManager` is in-memory only
- No persistence of collaboration state
- Clients don't re-connect automatically
- No "stale session" detection after restart

**Consequences:**
- **MEDIUM**: Confusing UX ("ghost users")
- Edit locks stuck (can't edit node)
- Users refresh page to fix (frustration)
- Distrust in real-time features

**Prevention:**
```python
# 1. Persist collaboration state to Redis
class PersistentCollaborationManager:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def add_participant(self, session_id: str, user_id: str):
        # Write to Redis with TTL
        key = f"session:{session_id}:participants"
        await self.redis.sadd(key, user_id)
        await self.redis.expire(key, 1800)  # 30 min TTL

    async def get_active_participants(self, session_id: str) -> Set[str]:
        key = f"session:{session_id}:participants"
        return await self.redis.smembers(key)

# 2. Client-side auto-reconnect
class CollaborationClient {
  connect() {
    this.ws = new WebSocket(url)

    this.ws.onclose = () => {
      // Exponential backoff reconnection
      setTimeout(() => this.connect(), 1000)
    }
  }
}

# 3. Server-side session cleanup on startup
async def cleanup_stale_sessions():
    """Remove sessions with no active connections"""
    active_sessions = get_active_sessions_from_redis()
    for session in active_sessions:
        if not has_active_websockets(session):
            await clear_session_state(session)
```

**Detection:**
- Users report "ghost participants" after deployment
- Edit locks stuck with "locked by user who left"
- High number of page refreshes after server restart

**Phase to address:**
Phase 02 (WebSocket Infrastructure) - Redis-backed session state

---

### Pitfall 7: Broadcast Storm from Multi-Workspace Updates

**What goes wrong:**
User edits workflow in workspace with 100 active users. System broadcasts update to all 100 connections. Each user's client sends ACK (100 messages). Server processes 100 ACKs. CPU spikes to 100%. Other requests timeout.

**Why it happens:**
- No message batching or throttling
- Broadcasts to entire workspace instead of relevant users
- ACK storms from clients (every broadcast triggers N ACKs)
- No rate limiting on broadcast operations

**Consequences:**
- **MEDIUM**: CPU spikes, request timeouts
- Degraded performance for large workspaces
- WebSocket connections dropped due to slow processing
- Poor experience for teams >20 users

**Prevention:**
```python
# 1. Targeted broadcasts (not entire workspace)
async def broadcast_workflow_update(workflow_id: str, update: dict):
    # Only broadcast to users viewing THIS workflow
    key = f"viewing:{workflow_id}"
    viewer_ids = await redis.smembers(key)

    for user_id in viewer_ids:
        await send_to_user(user_id, update)

    # Instead of: broadcast to entire workspace (100+ users)

# 2. Batch updates
class UpdateBatcher:
    def __init__(self, max_batch_size=50, max_wait_ms=100):
        self.batch = []
        self.max_batch_size = max_batch_size
        self.max_wait_ms = max_wait_ms

    async def add_update(self, user_id: str, update: dict):
        self.batch.append((user_id, update))

        if len(self.batch) >= self.max_batch_size:
            await self.flush()

    async def flush(self):
        # Send all updates in parallel
        await asyncio.gather(*[
            send_to_user(uid, upd) for uid, upd in self.batch
        ])
        self.batch.clear()

# 3. Disable ACKs for broadcasts (fire-and-forget)
# Clients should poll for missed updates if needed
```

**Detection:**
- CPU spikes correlate with user count
- Request latency increases in workspaces with >20 users
- WebSocket slow logs showing many sequential broadcasts

**Phase to address:**
Phase 03 (Real-Time Presence & Activity) - Targeted broadcasts + batching

---

### Pitfall 8: Missing Audit Trail for Collaboration Actions

**What goes wrong:**
User accidentally deletes important workflow node. No audit log showing who did what. Can't restore. Compliance failure (no audit trail for workflow changes).

**Why it happens:**
- `CollaborationAudit` model doesn't exist (TODO in code)
- No audit logging for collaboration actions
- Audit only for CRUD, not real-time actions
- No before/after state capture

**Consequences:**
- **MEDIUM**: Can't investigate incidents
- Compliance violations (SOC2, HIPAA require audit trails)
- Can't undo accidental deletions
- "Who changed this?" questions unanswered

**Prevention:**
```python
# 1. Create CollaborationAudit model (currently TODO)
class CollaborationAudit(Base):
    __tablename__ = "collaboration_audit"

    id = Column(String, primary_key=True)
    workflow_id = Column(String, index=True)
    user_id = Column(String, index=True)
    session_id = Column(String)

    action_type = Column(String)  # edit, delete, share, comment
    resource_type = Column(String)  # node, workflow, comment
    resource_id = Column(String)

    # Capture state changes
    before_state = Column(JSONB)
    after_state = Column(JSONB)

    created_at = Column(DateTime, default=func.now())

# 2. Audit decorator
def audit_collaboration_action(action_type: str):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Capture before state
            before = capture_state(kwargs)

            result = await func(*args, **kwargs)

            # Capture after state
            after = capture_state(kwargs)

            # Write audit log
            await db.add(CollaborationAudit(
                workflow_id=kwargs.get("workflow_id"),
                user_id=get_current_user(),
                action_type=action_type,
                before_state=before,
                after_state=after
            ))

            return result
        return wrapper
    return decorator

# 3. Use for all collaboration actions
@app.post("/workflows/{workflow_id}/nodes")
@audit_collaboration_action("create_node")
async def create_node(workflow_id: str, node_data: dict):
    # Automatically audited
    pass
```

**Detection:**
- Compliance audit failures
- Support requests: "Who deleted this?"
- Missing `CollaborationAudit` records in database

**Phase to address:**
Phase 01 (Foundation Models & Basic RBAC) - Create audit models + middleware

---

## Minor Pitfalls

Issues that cause annoyance but are easy to work around.

### Pitfall 9: Stale "User is typing..." Indicators

**What goes wrong:**
User starts typing comment, navigates away. "User is typing..." indicator stays forever. Other users wait for comment that never comes.

**Why it happens:**
- No timeout for typing indicators
- Client doesn't send "stopped typing" event
- Server trusts client to clear state

**Consequences:**
- **MINOR**: Minor UX annoyance
- Users wait for comments that aren't coming
- Distrust in presence indicators

**Prevention:**
```python
# Server-side timeout
class TypingIndicatorTracker:
    async def set_typing(self, workflow_id: str, user_id: str):
        key = f"typing:{workflow_id}:{user_id}"
        await redis.setex(key, 10, "1")  # Auto-expire after 10s

    async def get_typing_users(self, workflow_id: str) -> List[str]:
        pattern = f"typing:{workflow_id}:*"
        keys = await redis.keys(pattern)

        # Extract user IDs from keys
        return [key.split(":")[-1] for key in keys]
```

**Phase to address:**
Phase 03 (Real-Time Presence & Activity)

---

### Pitfall 10: Duplicate Notifications from Multiple WebSocket Connections

**What goes wrong:**
User has 3 browser tabs open. Receives 3 copies of every notification. Spammy experience.

**Why it happens:**
- Each tab creates separate WebSocket connection
- Broadcast sends to all connections for same user
- No deduplication across connections

**Consequences:**
- **MINOR**: Notification spam
- Users close tabs to reduce noise
- Miss important notifications due to fatigue

**Prevention:**
```python
# 1. Track multiple connections per user
class ConnectionManager:
    def __init__(self):
        self.user_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(websocket)

# 2. Send notification once per user (not per connection)
async def notify_user(user_id: str, message: dict):
    connections = self.user_connections.get(user_id, set())

    # Send to first connection only
    if connections:
        await next(iter(connections)).send_json(message)
```

**Phase to address:**
Phase 02 (WebSocket Infrastructure)

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| **Skip versioning on workflow model** | Faster initial implementation | Data corruption from concurrent edits | Never - versioning is critical for collaboration |
| **In-memory WebSocket state only** | Simpler, no Redis dependency | Lost state on restart, can't scale horizontally | MVP only, must migrate before production |
| **Use existing User model for collaboration** | No new models to create | Mixing concerns, can't evolve independently | Acceptable for MVP, create separate models later |
| **Skip audit logging for real-time features** | Less code, faster development | Compliance violations, can't investigate incidents | Never - audit is non-negotiable for production |
| **Broadcast to entire workspace** | Easier than tracking who's viewing what | Performance issues, privacy concerns | MVP only, must target broadcasts before production |
| **No heartbeat mechanism** | Simpler connection handling | Memory leaks from dead connections | MVP only (with frequent restarts), must add before production |
| **Use database for cursor positions** | No Redis dependency | Lock contention, poor performance | Acceptable for <10 concurrent users, migrate to Redis before scale |
| **Skip OT/CRDT for conflict resolution** | Much simpler to implement | Last-write-wins data loss | Acceptable for MVP with optimistic locking, full OT/CRDT in production |

---

## Integration Gotchas

Common mistakes when connecting collaboration features to existing systems.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **Existing Agent Execution** | Block agent execution when collaboration session active (thinking they conflict) | Agent execution and collaboration are independent - agent runs create audit log entries, don't block |
| **Existing Governance System** | Duplicate permission checks (check twice in same request) | Create shared `check_permission()` helper used by both systems |
| **Existing WebSocket Manager** | Try to reuse debugging WebSocket manager for collaboration | Create separate `CollaborationWebSocketManager` - different concerns (debugging vs. multi-user editing) |
| **Existing User/Team Models** | Add collaboration fields to existing models (bloat) | Create separate models (`CollaborationSession`, `EditLock`) linked via foreign keys |
| **Existing Audit System** | Create separate audit logging for collaboration | Extend existing audit system with `action_type="collaboration"` - unified audit trail |
| **Existing Database Sessions** | Use same DB session pattern (context manager) | Keep using context managers, but add separate models |
| **Existing Redis** | Use same Redis instance without namespacing | Use namespace keys (`collab:`, `debug:`) to avoid collisions |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **Database-backed cursor tracking** | Query latency spikes, lock contention | Move cursor positions to Redis with 2-min TTL | Breaks at 10+ concurrent users |
| **Broadcast to all workspace members** | CPU spikes, slow broadcasts | Target broadcasts to users actually viewing workflow | Breaks at 20+ workspace members |
| **No message batching** | High CPU, many small writes | Batch updates every 100ms or 50 messages | Breaks at 5+ updates/second |
| **In-memory connection state** | Can't scale horizontally, lost state on restart | Store state in Redis with TTL | Breaks at 2+ server instances |
| **Synchronous database writes in WebSocket loop** | Blocked WebSocket loop, slow updates | Use async writes or Redis buffering | Breaks at 10+ concurrent editors |
| **No rate limiting on updates** | Spam updates (every keystroke) | Debounce updates (max 1 per 100ms per user) | Breaks at 5+ concurrent users |
| **Full document sync on every change** | High bandwidth, slow updates | Send incremental patches (OT/CRDT) | Breaks at workflows >100 nodes |

**Scale thresholds for Atom:**
- **MVP** (<10 users per workspace): In-memory state acceptable, database-backed cursors OK
- **Production** (10-50 users per workspace): Redis required, targeted broadcasts, incremental updates
- **Enterprise** (50+ users per workspace): Full OT/CRDT, horizontal scaling, Redis Cluster

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| **Trust user_id from WebSocket message** | Permission escalation, impersonation | NEVER trust user_id from client - use server-side token validation |
| **Missing RBAC on share operations** | Users share workflows they don't own, data leak | Check ownership + explicit share permission before creating share link |
| **No authorization on WebSocket endpoints** | Unauthenticated connections, data exposure | Require JWT token on WebSocket connection, validate on every sensitive action |
| **Share links guessable** | Unauthorized access via brute force | Use cryptographically secure random tokens (UUID4 or secrets.token_urlsafe()) |
| **No expiration on share links** | Permanent access hole | Default 7-day expiration, max 30 days, audit all access |
| **Missing audit logging for collaboration** | Can't investigate security incidents | Audit ALL collaboration actions (edit, share, comment, delete) |
| **Edit locks don't check ownership** | User locks node they don't own, blocks others | Verify `locked_by == current_user` before honoring lock |
| **Guest access bypasses governance** | Guests trigger agents they shouldn't | Apply governance rules to ALL users including guests |

---

## UX Pitfalls

Common user experience mistakes in collaboration features.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| **Silent overwrites on concurrent edits** | "My changes disappeared!" | Show conflict resolution UI, warn before overwriting |
| **Stale "user is typing" indicators** | Users wait for comments that never come | Auto-expire typing indicators after 10 seconds |
| **No indication who else is viewing** | Accidental concurrent edits | Show "Viewing: Alice, Bob" in UI |
| **Edit locks with no expiration** | Node locked forever after user leaves | Auto-expire locks after 30 minutes inactivity |
| **No undo for collaborative edits** | Fear of breaking workflow | Implement undo stack per-user, collaborative undo |
| **Duplicate notifications (multiple tabs)** | Notification spam | Deduplicate notifications per user |
| **No visual feedback on save conflicts** | Confusing error messages | Show "Alice edited this node while you were working. Overwrite?" |
| **Slow cursor updates (500ms+ lag)** | Cursor jumps around, feels broken | Optimistic updates, <100ms lag target |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Collaboration Models:** Often missing actual database models (currently TODO in code) — verify `CollaborationAudit`, `CollaborationComment`, `CollaborationSessionParticipant`, `EditLock`, `WorkflowCollaborationSession`, `WorkflowShare` models exist in `models.py`
- [ ] **WebSocket Authentication:** Often missing per-message authorization — verify JWT validated on connection AND on every sensitive action
- [ ] **Optimistic Locking:** Often missing version checks — verify Workflow model has `version` field and updates check version
- [ ] **Audit Logging:** Often missing for real-time actions — verify ALL collaboration actions create audit entries
- [ ] **Redis Integration:** Often skipped for simplicity — verify high-frequency state (cursors, heartbeats) uses Redis not database
- [ ] **Cleanup Jobs:** Often missing — verify scheduled tasks for dead connection cleanup, expired lock cleanup, stale session cleanup
- [ ] **Rate Limiting:** Often missing on WebSocket — verify update throttling (max 1 per 100ms per user)
- [ ] **Conflict Resolution UI:** Often missing — verify UI shows "concurrent edit" warnings, not silent overwrites
- [ ] **Reconnection Logic:** Often missing — verify clients auto-reconnect with exponential backoff
- [ ] **Ownership Checks:** Often missing on share operations — verify users can only share workflows they own or have explicit permission

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| **Concurrent edit data loss** | HIGH | 1. Restore from database backup 2. Replay audit log to reconstruct changes 3. Contact affected users with restored data 4. Implement versioning to prevent recurrence |
| **Permission escalation via WebSocket** | CRITICAL | 1. Immediate: Rotate all JWT secrets, force logout all users 2. Audit all collaboration actions in last 24h 3. Revoke suspicious permissions 4. Deploy hardened WebSocket handlers with RBAC 5. Notify affected users |
| **Memory leak from dead connections** | MEDIUM | 1. Deploy connection cleanup job (heartbeat + timeout) 2. Restart server to clear memory 3. Monitor connection count vs. active users 4. Add alerts for memory growth |
| **Database lock contention** | MEDIUM | 1. Move cursor/heartbeat data to Redis 2. Add connection pooling (increase pool size) 3. Monitor `pg_stat_activity` for lock waits 4. Add indexes on frequently queried columns |
| **RBAC bypass on share links** | HIGH | 1. Revoke all active share links immediately 2. Audit share access logs for unauthorized access 3. Deploy ownership-based authorization 4. Require re-approval for all shares |
| **Stale collaboration state after restart** | LOW | 1. Client-side: Add auto-reconnect with backoff 2. Server-side: Migrate state to Redis 3. Add startup cleanup job for stale sessions 4. Monitor session freshness metrics |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| **Concurrent edit data loss** | Phase 01: Add versioning to Workflow model | Integration test: 2 users edit same node simultaneously, verify conflict error raised |
| **WebSocket permission escalation** | Phase 02: Hardened WebSocket handlers | Security test: Craft WebSocket message with spoofed user_id, verify rejected |
| **Memory leaks from dead connections** | Phase 02: Heartbeat + cleanup job | Load test: 100 connections drop without close, verify all cleaned up within 3 min |
| **Database lock contention** | Phase 03: Redis-backed cursor/heartbeat tracking | Performance test: 10 users, 5 updates/sec each, verify DB lock waits <10ms |
| **RBAC bypass on share** | Phase 01: Ownership-based authorization | Security test: Non-owner attempts to share workflow, verify 403 error |
| **Broadcast storms** | Phase 03: Targeted broadcasts + batching | Load test: 100-user workspace, broadcast update, verify only relevant users notified |
| **Missing audit trail** | Phase 01: CollaborationAudit model + middleware | Audit test: Create share link, verify audit log entry created |
| **Stale state after restart** | Phase 02: Redis-backed session state | Chaos test: Kill server, verify clients auto-reconnect and state preserved |

---

## Sources

**Confidence: MEDIUM** (WebSearch unavailable due to rate limits, relying on training data and codebase analysis)

- **Codebase Analysis:**
  - `/Users/rushiparikh/projects/atom/backend/core/collaboration_service.py` - Existing collaboration service with TODO models
  - `/Users/rushiparikh/projects/atom/backend/core/websocket_manager.py` - Current WebSocket implementation (in-memory only)
  - `/Users/rushiparikh/projects/atom/backend/core/models.py` - Existing User, Team, Workspace, UserRole models

- **Training Data (Knowledge Cutoff: January 2025):**
  - FastAPI WebSocket best practices
  - Real-time collaboration patterns (OT, CRDT)
  - Redis pub/sub for WebSocket scaling
  - RBAC authorization patterns
  - Database race conditions and optimistic locking

- **Missing WebSearch Verification** (rate limited):
  - Current 2025 best practices for WebSocket scaling
  - Recent RBAC security vulnerabilities in FastAPI
  - Latest collaboration frameworks (Yjs, Automerge) patterns
  - Redis Cluster vs. single instance for pub/sub

**Flags for Phase-Specific Research:**
- Phase 02 (WebSocket Infrastructure): Verify current FastAPI WebSocket patterns (check for breaking changes in 2025)
- Phase 03 (Redis Integration): Research Redis Cluster setup for horizontal scaling
- Phase 04 (Advanced Collaboration): Research OT vs. CRDT libraries for Python/JavaScript

---

*Pitfalls research for: Real-Time Collaboration & Team Management*
*Researched: 2026-03-26*
