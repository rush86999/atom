# Architecture Research

**Domain:** Real-time Collaboration and Team Management (WebSocket Presence, Conflict Resolution, RBAC)
**Researched:** March 26, 2026
**Confidence:** HIGH

## Executive Summary

Atom's existing architecture provides a strong foundation for real-time collaboration features with FastAPI, SQLAlchemy 2.0, Redis-based WebSocket infrastructure, and established RBAC patterns. The platform already has WebSocket managers (`ConnectionManager`, `WebSocketConnectionManager`), multi-agent canvas collaboration (`CanvasCollaborationService`), governance caching (`GovernanceCache`), and role-based access control (`RBACService`). This research outlines how to extend these systems for user-to-user collaboration with presence, conflict resolution, and team management while reusing existing components.

**Key Findings:**
- **Existing infrastructure**: FastAPI WebSocket support, 2 WebSocket managers (channel-based + stream-based), Redis for pub/sub, SQLAlchemy 2.0 with User/Team/Workspace models, RBACService with role permissions
- **Integration points**: Extend `ConnectionManager` for presence, create `ConflictResolutionService` using existing governance cache patterns, enhance `RBACService` for team-based permissions, create database models for collaboration sessions
- **New components needed**: UserPresenceService, EditLockService (beyond existing agent locks), CommentService, CollaborationSessionService, TeamManagementService
- **Build order**: Database models → Presence service → Conflict resolution → Team RBAC → REST API + WebSocket → Frontend integration → Testing
- **Performance targets**: <100ms presence updates, <50ms edit lock acquisition, <200ms permission checks, support 100+ concurrent users per workspace

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Frontend Layer (Next.js)                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │Presence UI   │  │Collab Edit   │  │Team Manager  │  │Comments UI   │    │
│  │(Who's online)│  │(Real-time)   │  │(RBAC UI)     │  │(Threads)     │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
└─────────┼──────────────────┼──────────────────┼──────────────────┼───────────┘
          │ WebSocket        │ WebSocket        │ REST API        │ WebSocket   │
          │ (/ws/collab)     │ (/ws/collab)     │ (/api/teams)    │ (/ws/collab) │
┌─────────┴──────────────────┴──────────────────┴──────────────────┴───────────┐
│                       API Layer (FastAPI)                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Collaboration Routes (REST + WebSocket)                             │    │
│  │  - /api/collaboration/* (sessions, locks, comments)                 │    │
│  │  - /api/teams/* (team management, RBAC)                             │    │
│  │  - /ws/collaboration/{workspace_id} (WebSocket endpoint)            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────────────┤
│                       Service Layer                                          │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌────────────────────┐ │
│  │ UserPresenceService  │  │ ConflictResolution   │  │ TeamManagementSvc  │ │
│  │ (Redis-backed)       │  │ Service (Edit locks) │  │ (RBAC enforcement) │ │
│  │  - Heartbeats        │  │  - Pessimistic locks │  │  - Team CRUD       │ │
│  │  - Online status     │  │  - OT/CRDT          │  │  - Permission check│ │
│  └──────────┬───────────┘  └──────────┬───────────┘  └──────────┬─────────┘ │
├─────────────┼──────────────────────────┼──────────────────────────┼───────────┤
│  ┌──────────┴───────────┐  ┌──────────┴───────────┐  ┌──────────┴─────────┐ │
│  │ CollabSessionService │  │ CommentService       │  │ RBACService (EXTEND)│ │
│  │ (Session mgmt)       │  │ (Threads/mentions)   │  │  - Resource perms  │ │
│  │  - Session lifecycle │  │  - Nested comments   │  │  - Team roles      │ │
│  └──────────┬───────────┘  └──────────┬───────────┘  └──────────┬─────────┘ │
├─────────────┼──────────────────────────┼──────────────────────────┼───────────┤
│  ┌──────────┴───────────┐  ┌──────────┴───────────┐  ┌──────────┴─────────┐ │
│  │ ConnectionManager    │  │ GovernanceCache (reuse)│ ActivityPublisher │ │
│  │ (EXTEND for presence)│  │ (Lock caching)        │ (Event broadcast) │ │
│  └──────────────────────┘  └──────────────────────┘  └────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
              │                          │                        │
┌─────────────┴──────────────────────────┴────────────────────────┴───────────┐
│                       Data Layer                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ PostgreSQL   │  │ Redis        │  │ PostgreSQL   │  │ PostgreSQL   │     │
│  │ (Users/Teams │  │ (Presence    │  │ (Collab      │  │ (Comments/   │     │
│  │  Workspaces) │  │  Pub/Sub)    │  │  Sessions)   │  │  Locks)      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **UserPresenceService** | Track user online status, heartbeat management, broadcasting presence changes | Redis-backed service with TTL-based expiry, pub/sub for real-time updates |
| **ConflictResolutionService** | Manage edit locks, implement OT/CRDT for collaborative editing, detect conflicts | Pessimistic locking (SQLAlchemy) + operational transformation (Python OT library) |
| **TeamManagementService** | CRUD for teams, member management, role assignment, workspace-level permissions | SQLAlchemy service with User/Team/Workspace relationships |
| **CollaborationSessionService** | Create/join sessions, track participants, manage session lifecycle | SQLAlchemy models + Redis for active session state |
| **CommentService** | Threaded comments, mentions, notifications, comment permissions | SQLAlchemy with recursive CTEs for nested comments |
| **RBACService (EXTEND)** | Team-based permission checks, resource-level ACLs, role inheritance | Extend existing `RBACService` with team-aware permissions |
| **ConnectionManager (EXTEND)** | WebSocket connection management with presence tracking, channel subscriptions | Extend existing `ConnectionManager` with presence events |

## Recommended Project Structure

```
atom/
├── backend/
│   ├── core/
│   │   ├── models.py                      # EXTEND: Add collaboration models
│   │   │   ├── UserPresence               # NEW: User presence tracking
│   │   │   ├── CollaborationSession       # NEW: Collab session model
│   │   │   ├── EditLock                   # NEW: Resource edit locks
│   │   │   ├── CollaborationComment       # NEW: Threaded comments
│   │   │   ├── TeamMember                 # NEW: Team membership with roles
│   │   │   └── ResourcePermission         # NEW: Resource-level ACLs
│   │   ├── user_presence_service.py       # NEW: Presence tracking
│   │   ├── conflict_resolution_service.py # NEW: Edit locks + OT/CRDT
│   │   ├── team_management_service.py     # NEW: Team CRUD + permissions
│   │   ├── collaboration_service.py       # EXTEND: Already exists, add user collab
│   │   ├── comment_service.py             # NEW: Comment threads + mentions
│   │   ├── rbac_service.py                # EXTEND: Add team/resource permissions
│   │   ├── websockets.py                  # EXTEND: Add presence events
│   │   ├── governance_cache.py            # EXTEND: Add permission/lock caching
│   │   └── activity_publisher.py          # EXTEND: Add collab event types
│   ├── api/
│   │   ├── collaboration_routes.py        # NEW: Collab REST endpoints
│   │   ├── team_routes.py                 # NEW: Team management API
│   │   ├── comment_routes.py              # NEW: Comment CRUD
│   │   └── websocket_routes.py            # EXTEND: Add collab WebSocket endpoint
│   ├── tests/
│   │   ├── test_presence_service.py       # NEW: Presence tracking tests
│   │   ├── test_conflict_resolution.py    # NEW: Edit lock + OT tests
│   │   ├── test_team_management.py        # NEW: Team CRUD tests
│   │   ├── test_collaboration.py          # NEW: Collab session tests
│   │   └── test_rbac_collaboration.py     # NEW: Team RBAC tests
│   └── migrations/versions/
│       └── XXX_add_collaboration_models.py # NEW: DB migration
└── frontend-nextjs/
    ├── hooks/
    │   ├── usePresence.ts                 # NEW: Real-time presence hook
    │   ├── useCollaboration.ts            # NEW: Collab session hook
    │   └── useConflictResolution.ts       # NEW: Edit lock hook
    ├── components/
    │   ├── collaboration/
    │   │   ├── PresenceIndicator.tsx      # NEW: "Who's online" UI
    │   │   ├── CollaborativeEditor.tsx    # NEW: Real-time editing with locks
    │   │   ├── CommentThread.tsx          # NEW: Nested comments UI
    │   │   └── TeamManager.tsx            # NEW: Team management UI
    │   └── websocket/
    │       └── CollaborationWebSocket.tsx # NEW: Collab WebSocket client
    └── services/
        └── collaborationService.ts        # NEW: Collab API client
```

### Structure Rationale

- **`backend/core/models.py`**: Extend existing SQLAlchemy models with collaboration tables (UserPresence, CollaborationSession, EditLock, CollaborationComment) - keeps all models in one place
- **`backend/core/user_presence_service.py`**: NEW service for presence tracking using Redis pub/sub for <100ms updates
- **`backend/core/conflict_resolution_service.py`**: NEW service combining pessimistic locking (existing EditLock pattern from CollaborationService) with operational transformation
- **`backend/core/team_management_service.py`**: NEW service for Team CRUD, leveraging existing User/Team/Workspace relationships
- **`backend/core/collaboration_service.py`**: EXTEND existing service to add user-to-user collaboration (currently agent-focused)
- **`backend/core/rbac_service.py`**: EXTEND existing RBACService with team-based permissions and resource-level ACLs
- **`backend/core/websockets.py`**: EXTEND existing ConnectionManager to add presence events (user:join, user:leave, user:typing)
- **`backend/api/collaboration_routes.py`**: NEW REST API for collaboration sessions, locks, comments
- **`backend/api/team_routes.py`**: NEW REST API for team management and member permissions
- **`frontend-nextjs/hooks/usePresence.ts`**: NEW React hook for real-time presence updates
- **`frontend-nextjs/components/collaboration/`**: NEW UI components for presence indicators, collaborative editing, comments

## Architectural Patterns

### Pattern 1: Redis-Backed Presence Tracking

**What:** Use Redis to track user presence with TTL-based expiration and pub/sub for real-time broadcasts. Each user's presence is stored as a Redis hash with last_seen timestamp, current resource, and status. Clients send heartbeats every 30s, Redis expires keys after 60s (2x heartbeat interval).

**When to use:**
- Real-time "who's online" features
- Presence indicators (online, idle, offline)
- Multi-device presence tracking

**Trade-offs:**
- ✅ Fast (<50ms lookups, <100ms broadcasts)
- ✅ Automatic expiration (no cleanup jobs)
- ✅ Scalable (Redis pub/sub to multiple servers)
- ❌ Data loss on Redis restart (acceptable for transient presence)

**Example:**
```python
# backend/core/user_presence_service.py
from typing import Optional, Dict, Any, List
import json
from datetime import datetime, timedelta
import redis

class UserPresenceService:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.heartbeat_interval = 30  # seconds
        self.presence_ttl = 60  # seconds (2x heartbeat)

    async def update_presence(
        self,
        user_id: str,
        workspace_id: str,
        resource_type: str,
        resource_id: str,
        status: str = "online"
    ):
        """Update user presence with TTL"""
        key = f"presence:{workspace_id}:{user_id}"
        presence_data = {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "status": status,
            "last_seen": datetime.now().isoformat()
        }
        # Store with TTL
        self.redis.hset(key, mapping=presence_data)
        self.redis.expire(key, self.presence_ttl)

        # Publish presence update
        await self._publish_presence_event(workspace_id, presence_data)

    async def get_workspace_presence(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get all active users in workspace"""
        pattern = f"presence:{workspace_id}:*"
        keys = self.redis.keys(pattern)
        presences = []
        for key in keys:
            data = self.redis.hgetall(key)
            if data:
                presences.append({k.decode(): v.decode() for k, v in data.items()})
        return presences

    async def _publish_presence_event(self, workspace_id: str, presence_data: Dict[str, Any]):
        """Publish presence update via Redis pub/sub"""
        channel = f"presence:{workspace_id}"
        message = {
            "type": "presence_update",
            "data": presence_data,
            "timestamp": datetime.now().isoformat()
        }
        self.redis.publish(channel, json.dumps(message))
```

### Pattern 2: Pessimistic Locking with Conflict Detection

**What:** Use database-level pessimistic locking for resource edits (workflow, agent, canvas) to prevent concurrent modifications. Combine with last-write-wins conflict detection using version vectors. Extend existing `EditLock` pattern from `CollaborationService`.

**When to use:**
- Low-contention resources (<10 concurrent editors)
- Strong consistency requirements
- Existing SQLAlchemy models

**Trade-offs:**
- ✅ Simple to implement (leverages existing EditLock)
- ✅ Strong consistency (database-level locks)
- ✅ Conflict detection via version vectors
- ❌ Doesn't scale to 100+ concurrent editors (use CRDTs instead)

**Example:**
```python
# backend/core/conflict_resolution_service.py
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from core.models import EditLock, User

class ConflictResolutionService:
    def __init__(self, db: Session):
        self.db = db

    def acquire_lock(
        self,
        resource_type: str,
        resource_id: str,
        user_id: str,
        duration_minutes: int = 30
    ) -> Optional[EditLock]:
        """Acquire edit lock using existing EditLock model"""
        # Check for existing active lock
        existing_lock = self.db.query(EditLock).filter(
            and_(
                EditLock.resource_type == resource_type,
                EditLock.resource_id == resource_id,
                EditLock.is_active == True
            )
        ).first()

        if existing_lock:
            # Check if expired
            if existing_lock.expires_at and existing_lock.expires_at < datetime.now():
                existing_lock.is_active = False
                self.db.commit()
            else:
                # Lock held by another user
                return None

        # Create new lock
        lock = EditLock(
            session_id=f"lock_{resource_type}_{resource_id}",
            workflow_id=resource_id,  # Reuse field
            resource_type=resource_type,
            resource_id=resource_id,
            locked_by=user_id,
            locked_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=duration_minutes),
            is_active=True
        )

        self.db.add(lock)
        self.db.commit()
        self.db.refresh(lock)

        return lock

    def release_lock(self, resource_type: str, resource_id: str, user_id: str) -> bool:
        """Release edit lock"""
        lock = self.db.query(EditLock).filter(
            and_(
                EditLock.resource_type == resource_type,
                EditLock.resource_id == resource_id,
                EditLock.locked_by == user_id,
                EditLock.is_active == True
            )
        ).first()

        if lock:
            lock.is_active = False
            self.db.commit()
            return True

        return False

    def check_conflict(
        self,
        resource_type: str,
        resource_id: str,
        current_version: int,
        user_id: str
    ) -> bool:
        """Detect version conflict (last-write-wins)"""
        # Resource version check would be implemented in resource models
        # This is a placeholder for the pattern
        return False
```

### Pattern 3: Team-Based RBAC with Resource Permissions

**What:** Extend existing `RBACService` to support team-based permissions with resource-level ACLs. Users inherit permissions from their team roles, and resources can have explicit ACLs (e.g., "workflow:abc123 can be edited by team:XYZ"). Cache permission checks in `GovernanceCache` for <50ms lookups.

**When to use:**
- Multi-team workspaces
- Resource-level access control
- Existing RBAC infrastructure

**Trade-offs:**
- ✅ Reuses existing RBACService
- ✅ Fast cached lookups (<50ms)
- ✅ Flexible team + resource permissions
- ❌ Requires cache invalidation on permission changes

**Example:**
```python
# backend/core/rbac_service.py (EXTEND)
from typing import Set, Optional
from core.models import User, Team, ResourcePermission
from core.governance_cache import get_governance_cache

class RBACService:
    # EXISTING: Role-based permissions
    @staticmethod
    def get_user_permissions(user: User) -> Set[str]:
        """Get all permissions for a user based on their role"""
        # ... existing implementation ...

    @staticmethod
    def check_permission(user: User, required_permission: Permission) -> bool:
        """Check if user has specific permission"""
        # ... existing implementation ...

    # NEW: Team-based permissions
    @staticmethod
    def get_team_permissions(user_id: str, team_id: str) -> Set[str]:
        """Get permissions for user in specific team"""
        cache = get_governance_cache()
        cache_key = f"team_perms:{user_id}:{team_id}"

        cached = cache.get(user_id, f"team:{team_id}")
        if cached:
            return set(cached.get("permissions", []))

        # Query database for team role permissions
        # Implementation would query TeamMember model
        permissions = set()  # Placeholder

        # Cache result
        cache.set(user_id, f"team:{team_id}", {"permissions": list(permissions)})
        return permissions

    # NEW: Resource-level ACLs
    @staticmethod
    def check_resource_permission(
        user: User,
        resource_type: str,
        resource_id: str,
        required_permission: str
    ) -> bool:
        """Check if user has permission on specific resource"""
        cache = get_governance_cache()
        cache_key = f"resource_acl:{user.id}:{resource_type}:{resource_id}"

        cached = cache.get(user.id, f"acl:{resource_type}:{resource_id}")
        if cached is not None:
            return cached.get("allowed", False)

        # Check resource ACLs in database
        # Implementation would query ResourcePermission model
        allowed = False  # Placeholder

        # Cache result
        cache.set(user.id, f"acl:{resource_type}:{resource_id}", {"allowed": allowed})
        return allowed
```

## Data Flow

### Request Flow

```
[User Action: Edit Workflow]
    ↓
[Frontend: useConflictResolution hook]
    ↓
[API: POST /api/collaboration/acquire_lock]
    ↓
[ConflictResolutionService.acquire_lock]
    ↓
[Database: EditLock (SQLAlchemy)]
    ↓ (lock acquired)
[WebSocket: broadcast lock event via ConnectionManager]
    ↓
[Other clients: Receive lock event, disable editing]
    ↓
[User edits workflow]
    ↓
[API: PUT /api/workflows/{id}]
    ↓
[WorkflowService.update]
    ↓
[WebSocket: broadcast update event]
    ↓
[Frontend: Update UI with new version]
```

### WebSocket Event Flow

```
[Client connects to /ws/collaboration/{workspace_id}]
    ↓
[ConnectionManager.connect]
    ├─ Auto-subscribe to workspace channel
    ├─ Get initial presence list
    └─ Send "connected" event
    ↓
[Client sends heartbeat every 30s]
    ↓
[UserPresenceService.update_presence]
    ├─ Update Redis with TTL
    └─ Publish "presence_update" event
    ↓
[Other clients receive "presence_update"]
    └─ Update presence indicators
    ↓
[Client disconnects]
    ↓
[ConnectionManager.disconnect]
    └─ Redis TTL expires presence (60s)
```

### Presence Update Flow

```
[User navigates to workflow]
    ↓
[Frontend: usePresence hook sends presence event]
    ↓
[WebSocket: Send "presence:update"]
    ↓
[UserPresenceService.update_presence]
    ├─ Update Redis hash: presence:{workspace_id}:{user_id}
    ├─ Set TTL = 60s
    └─ Publish to Redis pub/sub: presence:{workspace_id}
    ↓
[ConnectionManager receives Redis pub/sub message]
    ↓
[Broadcast to all WebSocket subscribers]
    ↓
[Clients update "Who's online" UI]
```

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-1k users | Single FastAPI server, Redis for presence, PostgreSQL for locks |
| 1k-10k users | Multiple FastAPI servers with shared Redis, partition workspaces by Redis shard |
| 10k+ users | CRDT-based collaborative editing (Yjs/Automerge), distributed lock manager (etcd), workspace sharding |

### Scaling Priorities

1. **First bottleneck**: WebSocket connections (~1000 per server) - scale horizontally with sticky sessions
2. **Second bottleneck**: Redis pub/sub throughput - use Redis Cluster or sharded channels
3. **Third bottleneck**: Database lock contention - move to CRDTs for high-contention resources

## Anti-Patterns

### Anti-Pattern 1: Polling for Presence

**What people do:** Frontend polls API every 5s to check "who's online"

**Why it's wrong:**
- Unnecessary API load (1000 users = 200 req/s)
- Stale presence data (5s delay)
- Server resources wasted on duplicate queries

**Do this instead:**
- Use WebSocket with server-sent presence events
- Client sends heartbeat every 30s
- Server broadcasts presence changes via Redis pub/sub

### Anti-Pattern 2: Database-Level Presence Tracking

**What people do:** Store presence in PostgreSQL with UPDATE on every heartbeat

**Why it's wrong:**
- Database write load (1000 users × 2 heartbeats/min = 2000 writes/min)
- No automatic expiration (need cleanup job)
- Slow presence queries (table scans)

**Do this instead:**
- Use Redis with TTL-based expiration
- Automatic key expiry = no cleanup
- <50ms presence queries via Redis

### Anti-Pattern 3: Optimistic Locking Without Conflict Resolution

**What people do:** Use version numbers for optimistic locking but don't handle conflicts

**Why it's wrong:**
- Users overwrite each other's changes (last-write-wins)
- No notification of conflicts
- Data loss without user awareness

**Do this instead:**
- Pessimistic locking for <10 concurrent editors
- Conflict detection with version vectors
- Show conflict resolution UI when detected

### Anti-Pattern 4: Ignoring Existing Infrastructure

**What people do:** Build new WebSocket manager, new RBAC system, new cache layer

**Why it's wrong:**
- Duplicates existing functionality
- Inconsistent patterns across codebase
- Misses performance optimizations (GovernanceCache)

**Do this instead:**
- Extend existing `ConnectionManager` for presence
- Extend existing `RBACService` for team permissions
- Use existing `GovernanceCache` for permission caching

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Redis | Presence tracking, pub/sub for real-time events | Use existing Redis dependency (already in requirements.txt) |
| PostgreSQL | Persistent storage for sessions, locks, comments | Extend existing models.py |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| **UserPresenceService → ConnectionManager** | Direct method calls + WebSocket broadcasts | Extend ConnectionManager with presence event types |
| **ConflictResolutionService → CollaborationService** | Shared EditLock model | CollaborationService already has EditLock, reuse pattern |
| **TeamManagementService → RBACService** | Extend RBACService with team permissions | Don't duplicate permission logic |
| **All services → GovernanceCache** | Cached permission/lock lookups | Use existing cache for <50ms checks |
| **All services → ActivityPublisher** | Event broadcasting for audit logs | Add collaboration event types |

## New vs Modified Components

### New Components

1. **UserPresenceService** - Presence tracking with Redis
2. **ConflictResolutionService** - Edit locks + conflict detection
3. **TeamManagementService** - Team CRUD + member management
4. **CommentService** - Threaded comments + mentions
5. **Database models** - UserPresence, CollaborationSession, EditLock (extend), CollaborationComment, ResourcePermission
6. **REST API routes** - collaboration_routes.py, team_routes.py, comment_routes.py
7. **Frontend hooks** - usePresence.ts, useCollaboration.ts, useConflictResolution.ts
8. **Frontend components** - PresenceIndicator, CollaborativeEditor, CommentThread, TeamManager

### Modified Components

1. **ConnectionManager** (websockets.py) - Add presence event types (user:join, user:leave, user:typing)
2. **RBACService** - Add team-based permissions and resource ACLs
3. **CollaborationService** - Extend for user-to-user collaboration (currently agent-focused)
4. **GovernanceCache** - Add cache keys for team permissions and resource ACLs
5. **ActivityPublisher** - Add collaboration event types (session_created, lock_acquired, comment_added)

### Data Flow Changes

**Before (Agent Collaboration):**
```
Agent → CanvasCollaborationService → Agent Coordination → Canvas Update
```

**After (User Collaboration):**
```
User → WebSocket → UserPresenceService → Redis Pub/Sub → Other Users
User → REST API → ConflictResolutionService → Edit Lock → Database
User → REST API → CollaborationService → Session → Broadcast
User → REST API → CommentService → Comment → Notification
```

### Build Order (Dependencies)

1. **Database models** (foundational) - UserPresence, CollaborationSession, EditLock, CollaborationComment, ResourcePermission
2. **Service layer** (depends on models) - UserPresenceService, ConflictResolutionService, TeamManagementService, CommentService
3. **RBAC extension** (depends on Team service) - Extend RBACService with team permissions
4. **WebSocket extension** (depends on Presence service) - Extend ConnectionManager with presence events
5. **REST API** (depends on services) - collaboration_routes.py, team_routes.py, comment_routes.py
6. **Frontend hooks** (depends on API) - usePresence.ts, useCollaboration.ts, useConflictResolution.ts
7. **Frontend components** (depends on hooks) - PresenceIndicator, CollaborativeEditor, CommentThread, TeamManager
8. **Testing** (depends on all components) - Integration tests, E2E tests

## Sources

- **Existing Atom Architecture**: `/Users/rushiparikh/projects/atom/backend/core/websockets.py` (ConnectionManager), `/Users/rushiparikh/projects/atom/backend/core/websocket_manager.py` (WebSocketConnectionManager), `/Users/rushiparikh/projects/atom/backend/core/collaboration_service.py` (existing collaboration patterns), `/Users/rushiparikh/projects/atom/backend/core/rbac_service.py` (existing RBAC)
- **Existing Models**: `/Users/rushiparikh/projects/atom/backend/core/models.py` (User, Team, Workspace, EditLock models)
- **Project Context**: `/Users/rushiparikh/projects/atom/.planning/PROJECT.md` (v9.0 Collaboration & Team Management milestone)
- **Requirements**: `/Users/rushiparikh/projects/atom/backend/requirements.txt` (FastAPI, SQLAlchemy, Redis, websockets)
- **Architecture Documentation**: `/Users/rushiparikh/projects/atom/docs/ARCHITECTURE.md` (overall system architecture)

---
*Architecture research for: Real-time Collaboration and Team Management (WebSocket Presence, Conflict Resolution, RBAC)*
*Researched: March 26, 2026*
