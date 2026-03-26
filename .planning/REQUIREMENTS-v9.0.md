# Requirements: Atom v9.0 Collaboration & Team Management

**Defined:** March 26, 2026
**Core Value:** Real-time collaboration enables teams to work together seamlessly on workflows, agents, and canvases with proper access control.

## v1 Requirements

Requirements for Atom v9.0 Collaboration & Team Management milestone. Each maps to roadmap phases for real-time collaboration, team management, RBAC, shared resources, and conflict resolution.

### Database Models

- [ ] **DB-01**: System stores workflow collaboration sessions with participant tracking, session lifecycle, and collaboration mode (parallel/sequential/locked)
- [ ] **DB-02**: System stores threaded comments on workflows/agents/canvases with nested replies, @mentions, and resolution status
- [ ] **DB-03**: System stores edit locks for resources (workflow/node/canvas) with expiration, ownership, and active status
- [ ] **DB-04**: System stores workflow share links with permissions (can_view/can_edit), expiration, usage tracking, and revocation
- [ ] **DB-05**: System stores collaboration audit log with before/after state, action type, user context, and timestamps
- [ ] **DB-06**: System stores collaboration session participants with cursor positions, roles (owner/editor/viewer), and heartbeat tracking

### User Presence

- [ ] **PRES-01**: System tracks user online/offline/away status with last seen timestamps and current resource viewing
- [ ] **PRES-02**: System broadcasts presence changes in real-time to all workspace members via WebSocket when users join/leave/go idle
- [ ] **PRES-03**: System automatically expires stale presence after 60 seconds of inactivity (2x heartbeat interval of 30s)

### Real-Time Updates

- [ ] **REAL-01**: System delivers workflow/agent/canvas changes instantly to all connected clients via WebSocket without requiring page refresh
- [ ] **REAL-02**: System uses room-based broadcasting to target updates only to users viewing the affected resource (not entire workspace)
- [ ] **REAL-03**: System persists collaboration state to Redis to survive server restarts and clients auto-reconnect with exponential backoff

### Team Management

- [ ] **TEAM-01**: Authorized users can create teams with name, description, and default roles (owner/admin/member/viewer)
- [ ] **TEAM-02**: Team owners and admins can add/remove members with role assignment and permission inheritance
- [ ] **TEAM-03**: System supports team roles with hierarchical permissions (owner > admin > member > viewer) and role inheritance
- [ ] **TEAM-04**: Teams have ownership of workflows/agents/canvases with created_by tracking for ownership-based authorization
- [ ] **TEAM-05**: System lists all teams a user belongs to with their role and permission level for authorization checks
- [ ] **TEAM-06**: Team owners can transfer ownership to another member with audit logging and notification

### Comments & Threads

- [ ] **COMM-01**: Authorized users can create threaded comments on workflows/agents/canvases with context-aware placement (node/canvas/workflow-level)
- [ ] **COMM-02**: Users can reply to comments forming nested threads with recursive CTE queries for retrieval and parent-child relationships
- [ ] **COMM-03**: Users can @mention other users in comments which triggers notifications and mentioned users receive real-time alerts
- [ ] **COMM-04**: Comment authors and authorized users can edit/delete their own comments with audit trail and version tracking
- [ ] **COMM-05**: Users can resolve comment threads marking them as resolved with resolver tracking and resolution timestamp

### Conflict Resolution

- [ ] **CONF-01**: System prevents concurrent edit conflicts using pessimistic edit locks that users must acquire before editing resources
- [ ] **CONF-02**: Edit locks expire after 30 minutes of inactivity with automatic release and users can extend active locks
- [ ] **CONF-03**: System uses version vectors on workflow model to detect concurrent modifications and raise conflict errors on stale updates
- [ ] **CONF-04**: System shows conflict resolution UI when concurrent edits detected warning users before overwriting changes

### Resource Sharing

- [ ] **SHARE-01**: Workflow owners can create share links with customizable permissions (can_view/can_edit/can_share) and optional expiration
- [ ] **SHARE-02**: Share links use cryptographically secure random tokens (UUID4 or secrets.token_urlsafe()) to prevent unauthorized access
- [ ] **SHARE-03**: Share links track usage count, last accessed timestamp, and can be revoked by workflow owners or admins
- [ ] **SHARE-04**: Users accessing resources via share links have permissions restricted to share link permissions (no privilege escalation)

### Role-Based Access Control (RBAC)

- [ ] **RBAC-01**: System enforces ownership-based authorization requiring users to own resources OR have explicit permissions for share/modify operations
- [ ] **RBAC-02**: Team roles inherit permissions hierarchically (team_lead inherits member permissions, workspace_admin inherits team_lead)
- [ ] **RBAC-03**: System supports resource-level ACLs with fine-grained permissions (resource_type, resource_id, permissions JSONB)
- [ ] **RBAC-04**: Permission checks are cached in GovernanceCache for <50ms lookups with cache invalidation on permission changes
- [ ] **RBAC-05**: RBAC checks apply to ALL users including guests and apply to WebSocket messages (not just REST API endpoints)

### WebSocket Infrastructure

- [ ] **WS-01**: WebSocket connections require JWT token validation on connection AND re-validation on every sensitive action (prevent permission escalation)
- [ ] **WS-02**: System implements heartbeat/ping mechanism with 30-second timeout to detect dead connections and trigger cleanup
- [ ] **WS-03**: System runs periodic cleanup task every 60 seconds to remove dead connections inactive for >2 minutes and free memory
- [ ] **WS-04**: WebSocket manager tracks multiple connections per user and sends notifications once per user (not per connection) to prevent duplicate notifications

### Live Cursors

- [ ] **CURS-01**: System broadcasts real-time cursor positions to all users viewing the same workflow with user names and colors for visual identification
- [ ] **CURS-02**: Cursor positions use Redis for high-frequency updates with 2-minute TTL and are not written to database on every movement
- [ ] **CURS-03**: System batches cursor updates (max 50 messages or 100ms) to prevent broadcast storms in workspaces with many users

### Agent Collaboration

- [ ] **AGENT-01**: Multiple agents can coordinate on shared canvases with role-based permissions (STUDENT agents blocked, INTERN+ require approval)
- [ ] **AGENT-02**: System extends CanvasCollaborationService to support both agent-to-agent and user-to-user collaboration with unified session management
- [ ] **AGENT-03**: Agent maturity levels (STUDENT/INTERN/SUPERVISED/AUTONOMOUS) are enforced in collaboration sessions with governance checks

### Workflow Co-Editing

- [ ] **COED-01**: Multiple users can view workflows simultaneously with presence indicators showing who is viewing each node/canvas
- [ ] **COED-02**: System uses pessimistic locking for edit conflicts (users acquire lock before editing) with visual lock indicators showing who is editing what

## v2 Requirements

Deferred to future milestone (v9.1+). Acknowledged but not in current roadmap.

### Advanced Collaboration

- **COED-03**: Multiple users can edit workflows simultaneously with operational transformation (OT) or CRDT for conflict-free collaborative editing
- **CONF-05**: System provides AI-powered conflict resolution with LLM-generated merge suggestions for concurrent edits
- **TEAM-07**: System supports custom team roles (user-defined roles beyond fixed owner/admin/member/viewer)
- **SHARE-05**: Share links support password protection and additional security options

### Video/Audio Integration

- **REAL-04**: System supports integrated video/audio calling for collaboration sessions
- **REAL-05**: System provides screen sharing capabilities for real-time collaboration

### Advanced Features

- **COMM-06**: Comments support rich text formatting, attachments, and emoji reactions
- **PRES-04**: System tracks user activity across multiple devices with presence sync
- **RBAC-06**: System supports time-based permissions (temporary access with expiration)

## Out of Scope

Explicitly excluded from v9.0. Documented to prevent scope creep.

| Feature | Reason | Alternative |
|---------|--------|-------------|
| **Video/Audio Integration** | Commoditized feature, better integrated via external tools (Slack/Zoom) | Deep links to external communication tools |
| **Custom Team Roles** | Role explosion, support burden, complex UI | Fixed roles (Owner/Admin/Member/Viewer) + resource-level permissions |
| **AI Conflict Resolution** | Unclear value proposition, could confuse users, LLM hallucination risk | Clear conflict UI with manual resolution and visual warnings |
| **Collaborative Editing (OT/CRDT)** | High complexity, uncertain demand, niche use case | Pessimistic locking + version vectors for MVP |
| **100+ Concurrent Editors** | Edge case, requires CRDTs and distributed lock manager | Pessimistic locking scales to 10-20 concurrent editors (sufficient for MVP) |
| **Offline Mode for Collaboration** | Conflict resolution complexity, stale state risks | Require online connection for collaboration features |
| **Real-Time Voice Commands** | Privacy concerns, unclear user value | Text-based comments and @mentions |
| **Collaborative Workflow Execution** | Safety risks (agents triggering with multiple users), governance complexity | Single-user workflow execution with collaboration on editing only |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DB-01 | Phase 246-01 | Pending |
| DB-02 | Phase 246-01 | Pending |
| DB-03 | Phase 246-01 | Pending |
| DB-04 | Phase 246-01 | Pending |
| DB-05 | Phase 246-01 | Pending |
| DB-06 | Phase 246-01 | Pending |
| PRES-01 | Phase 247-01 | Pending |
| PRES-02 | Phase 247-01 | Pending |
| PRES-03 | Phase 247-01 | Pending |
| REAL-01 | Phase 247-02 | Pending |
| REAL-02 | Phase 247-02 | Pending |
| REAL-03 | Phase 247-02 | Pending |
| TEAM-01 | Phase 248-01 | Pending |
| TEAM-02 | Phase 248-01 | Pending |
| TEAM-03 | Phase 248-01 | Pending |
| TEAM-04 | Phase 248-01 | Pending |
| TEAM-05 | Phase 248-01 | Pending |
| TEAM-06 | Phase 248-01 | Pending |
| COMM-01 | Phase 249-01 | Pending |
| COMM-02 | Phase 249-01 | Pending |
| COMM-03 | Phase 249-01 | Pending |
| COMM-04 | Phase 249-01 | Pending |
| COMM-05 | Phase 249-01 | Pending |
| CONF-01 | Phase 250-01 | Pending |
| CONF-02 | Phase 250-01 | Pending |
| CONF-03 | Phase 250-01 | Pending |
| CONF-04 | Phase 250-01 | Pending |
| SHARE-01 | Phase 251-01 | Pending |
| SHARE-02 | Phase 251-01 | Pending |
| SHARE-03 | Phase 251-01 | Pending |
| SHARE-04 | Phase 251-01 | Pending |
| RBAC-01 | Phase 252-01 | Pending |
| RBAC-02 | Phase 252-01 | Pending |
| RBAC-03 | Phase 252-01 | Pending |
| RBAC-04 | Phase 252-01 | Pending |
| RBAC-05 | Phase 252-01 | Pending |
| WS-01 | Phase 247-03 | Pending |
| WS-02 | Phase 247-03 | Pending |
| WS-03 | Phase 247-03 | Pending |
| WS-04 | Phase 247-03 | Pending |
| CURS-01 | Phase 253-01 | Pending |
| CURS-02 | Phase 253-01 | Pending |
| CURS-03 | Phase 253-01 | Pending |
| AGENT-01 | Phase 254-01 | Pending |
| AGENT-02 | Phase 254-01 | Pending |
| AGENT-03 | Phase 254-01 | Pending |
| COED-01 | Phase 255-01 | Pending |
| COED-02 | Phase 255-01 | Pending |

**Coverage:**
- v1 requirements: 48 total
- Mapped to phases: 48
- Unmapped: 0 ✓

## Requirements Summary

### By Category

| Category | Count | Requirements |
|----------|-------|--------------|
| Database Models | 6 | DB-01 through DB-06 |
| User Presence | 3 | PRES-01 through PRES-03 |
| Real-Time Updates | 3 | REAL-01 through REAL-03 |
| Team Management | 6 | TEAM-01 through TEAM-06 |
| Comments & Threads | 5 | COMM-01 through COMM-05 |
| Conflict Resolution | 4 | CONF-01 through CONF-04 |
| Resource Sharing | 4 | SHARE-01 through SHARE-04 |
| RBAC | 5 | RBAC-01 through RBAC-05 |
| WebSocket Infrastructure | 4 | WS-01 through WS-04 |
| Live Cursors | 3 | CURS-01 through CURS-03 |
| Agent Collaboration | 3 | AGENT-01 through AGENT-03 |
| Workflow Co-Editing | 2 | COED-01 through COED-02 |
| **Total** | **48** | |

### By Priority

| Priority | Count | Categories |
|----------|-------|------------|
| **P1 (Table Stakes - MVP)** | 28 | DB (all), PRES (all), REAL (all), TEAM (all), SHARE (all), RBAC (all), WS (all), CONF (all) |
| **P2 (Differentiators)** | 12 | COMM (all), CURS (all), AGENT (all), COED (all) |
| **P3 (v2 Deferred)** | 8 | COED-03, CONF-05, TEAM-07, SHARE-05, REAL-04, REAL-05, COMM-06, PRES-04, RBAC-06 |

### Dependency Graph

```
[Database Models: DB-01 to DB-06]
    ↓ required by
[Team Management: TEAM-01 to TEAM-06]
    ↓ required by
[RBAC: RBAC-01 to RBAC-05]
    ↓ required by
[Resource Sharing: SHARE-01 to SHARE-04]
    ↓ required by
[WebSocket Infrastructure: WS-01 to WS-04]
    ↓ required by
[User Presence: PRES-01 to PRES-03]
    ↓ required by
[Real-Time Updates: REAL-01 to REAL-03]
    ↓ required by
[Conflict Resolution: CONF-01 to CONF-04]
    ↓ required by
[Live Cursors: CURS-01 to CURS-03]
    ↓ required by
[Comments & Threads: COMM-01 to COMM-05]
    ↓ required by
[Agent Collaboration: AGENT-01 to AGENT-03]
    ↓ required by
[Workflow Co-Editing: COED-01 to COED-02]
```

## Non-Functional Requirements

### Performance

- **NFR-PERF-01**: Presence updates broadcast in <100ms to all workspace members
- **NFR-PERF-02**: Edit lock acquisition completes in <50ms (cached checks)
- **NFR-PERF-03**: Permission checks complete in <50ms using GovernanceCache
- **NFR-PERF-04**: Cursor position updates broadcast in <100ms with batching (max 50 messages or 100ms)
- **NFR-PERF-05**: System supports 100+ concurrent users per workspace with targeted broadcasts

### Security

- **NFR-SEC-01**: All WebSocket connections require JWT token validation
- **NFR-SEC-02**: WebSocket message handlers NEVER trust user_id from client (server-side validation only)
- **NFR-SEC-03**: Share links use cryptographically secure random tokens (UUID4 or secrets.token_urlsafe())
- **NFR-SEC-04**: All collaboration actions create audit log entries with before/after state
- **NFR-SEC-05**: RBAC checks apply to ALL users including guests and external share link users
- **NFR-SEC-06**: Ownership-based authorization prevents users from sharing resources they don't own

### Reliability

- **NFR-REL-01**: Collaboration state persists to Redis to survive server restarts
- **NFR-REL-02**: Clients auto-reconnect with exponential backoff after connection drops
- **NFR-REL-03**: Dead WebSocket connections are cleaned up within 2 minutes of inactivity
- **NFR-REL-04**: Edit locks auto-expire after 30 minutes of inactivity
- **NFR-REL-05**: Stale presence indicators auto-expire after 60 seconds (2x heartbeat interval)

### Scalability

- **NFR-SCALE-01**: High-frequency updates (cursor positions, heartbeats) use Redis with TTL (not database)
- **NFR-SCALE-02**: Broadcasts target only relevant users (not entire workspace) to prevent CPU spikes
- **NFR-SCALE-03**: Cursor updates batch to max 50 messages or 100ms to prevent broadcast storms
- **NFR-SCALE-04**: System scales horizontally with shared Redis for pub/sub across multiple FastAPI instances

### Usability

- **NFR-USE-01**: "Who's online" presence indicators show all active users in workspace
- **NFR-USE-02**: Visual lock indicators show which resources are locked and by whom
- **NFR-USE-03**: Conflict resolution UI warns users before overwriting concurrent changes
- **NFR-USE-04**: Notifications are deduplicated per user (not per WebSocket connection)
- **NFR-USE-05**: Typing indicators auto-expire after 10 seconds to prevent stale "user is typing" states

## Acceptance Criteria

### Database Models (DB-01 to DB-06)
- [ ] Alembic migration creates all 6 collaboration models with proper indexes and foreign keys
- [ ] Models extend existing User/Team/Workspace relationships with tenant_id for multi-tenancy
- [ ] Workflow model gains version field for optimistic locking
- [ ] All collaboration models include audit fields (created_at, updated_at, created_by)

### User Presence (PRES-01 to PRES-03)
- [ ] Redis-backed presence tracking with SETEX and 60-second TTL
- [ ] Heartbeat endpoint extends TTL on every 30-second interval
- [ ] WebSocket broadcasts presence changes (user:join, user:leave, user:idle) to workspace members
- [ ] Last seen timestamps stored in Redis hash and retrieved via GET all online users endpoint

### Real-Time Updates (REAL-01 to REAL-03)
- [ ] WebSocket endpoint `/ws/collaboration/{workspace_id}` accepts JWT token and subscribes to workspace channel
- [ ] Workflow/agent/canvas changes broadcast to room `workflow_{id}` not entire workspace
- [ ] Collaboration state persists to Redis with 30-minute TTL and survives server restart
- [ ] Clients auto-reconnect with exponential backoff (1s → 2s → 4s → 8s max)

### Team Management (TEAM-01 to TEAM-06)
- [ ] REST API endpoints for team CRUD (POST /api/teams, GET /api/teams, PUT /api/teams/{id}, DELETE /api/teams/{id})
- [ ] Team member management endpoints (POST /api/teams/{id}/members, DELETE /api/teams/{id}/members/{user_id})
- [ ] Role assignment with hierarchical permissions (owner > admin > member > viewer)
- [ ] Team ownership transfer with audit logging and notification to new owner
- [ ] Workflow ownership tracked via created_by field and checked on share operations

### Comments & Threads (COMM-01 to COMM-05)
- [ ] REST API endpoints for comment CRUD (POST /api/comments, GET /api/comments, PUT /api/comments/{id}, DELETE /api/comments/{id})
- [ ] Threaded comments with parent_comment_id foreign key and recursive CTE queries for nested retrieval
- [ ] @mention parsing in comment content with notification delivery to mentioned users
- [ ] Comment resolution endpoint (POST /api/comments/{id}/resolve) with resolver tracking
- [ ] Comment permissions linked to resource access (can comment if can view resource)

### Conflict Resolution (CONF-01 to CONF-04)
- [ ] Edit lock acquisition endpoint (POST /api/collaboration/locks) with resource_type and resource_id
- [ ] Edit lock release endpoint (DELETE /api/collaboration/locks/{id}) with ownership validation
- [ ] Edit lock extension endpoint (PUT /api/collaboration/locks/{id}/extend) with timeout reset
- [ ] Version conflict detection on workflow updates with 409 Conflict response on stale version
- [ ] Conflict resolution UI shows warning before overwriting with "Another user edited this node. Overwrite?"

### Resource Sharing (SHARE-01 to SHARE-04)
- [ ] Share link creation endpoint (POST /api/workflows/{id}/share) with permissions JSONB
- [ ] Share link access endpoint (GET /api/shared/{share_token}) with permission validation
- [ ] Share link revocation endpoint (DELETE /api/workflows/{id}/share/{share_id}) with ownership check
- [ ] Share link tracking (use_count, last_accessed) updated on every access
- [ ] Share link expiration with expires_at check and 403 response if expired

### RBAC (RBAC-01 to RBAC-05)
- [ ] Ownership-based authorization decorator @require_ownership(permission) checks created_by before allowing share/modify
- [ ] Team role permissions queried from TeamMember model and cached in GovernanceCache
- [ ] Resource-level ACLs stored in ResourcePermission model with resource_type, resource_id, permissions JSONB
- [ ] Permission checks cache in GovernanceCache with cache_key pattern "team_perms:{user_id}:{team_id}" and "resource_acl:{user_id}:{resource_type}:{resource_id}"
- [ ] WebSocket message handlers validate permissions on every sensitive action (promote_participant, change_role)

### WebSocket Infrastructure (WS-01 to WS-04)
- [ ] WebSocket connection requires JWT token validation with validate_token(token) on connect
- [ ] WebSocket message handlers check permissions on every action (NEVER trust user_id from message)
- [ ] Heartbeat/ping mechanism sends ping every 30 seconds and disconnects after timeout
- [ ] Periodic cleanup task runs every 60 seconds removing connections inactive >2 minutes
- [ ] Multiple connections per user tracked in user_connections dict and notifications sent once per user

### Live Cursors (CURS-01 to CURS-03)
- [ ] Cursor position broadcasts via WebSocket with user_id, position {x, y}, user_name, user_color
- [ ] Redis storage for cursor positions with key pattern "cursor:{session_id}:{user_id}" and 120-second TTL
- [ ] Cursor update batching with max 50 messages or 100ms wait before flush
- [ ] Frontend renders cursor indicators with user name and color on canvas/workflow editor

### Agent Collaboration (AGENT-01 to AGENT-03)
- [ ] CanvasCollaborationService extended to support both agent-to-agent and user-to-user collaboration
- [ ] Agent maturity checks (STUDENT blocked, INTERN requires approval, SUPERVISED/AUTONOMOUS allowed) on collaboration session join
- [ ] Unified session management with participant tracking for both agents and users
- [ ] Agent governance integration with governance cache checks for agent collaboration permissions

### Workflow Co-Editing (COED-01 to COED-02)
- [ ] Presence indicators show "Viewing: Alice, Bob" for workflows/agents/canvases
- [ ] Pessimistic lock acquisition before editing with visual lock indicator showing "Locked by Alice"
- [ ] Lock status broadcast via WebSocket to all users viewing resource
- [ ] Lock release on save or navigation away with automatic release after 30 minutes inactivity

## Testing Requirements

### Unit Tests
- [ ] Database model tests for all 6 collaboration models (CRUD, relationships, validation)
- [ ] UserPresenceService tests (Redis operations, heartbeat, expiration, broadcasting)
- [ ] ConflictResolutionService tests (lock acquisition, release, expiration, conflict detection)
- [ ] TeamManagementService tests (team CRUD, member management, role assignment)
- [ ] CommentService tests (threaded comments, mentions, resolution, permissions)
- [ ] RBACService tests (ownership checks, team permissions, resource ACLs, caching)

### Integration Tests
- [ ] WebSocket connection tests (JWT validation, heartbeat, cleanup, reconnection)
- [ ] Collaboration session tests (create, join, leave, participant tracking)
- [ ] Edit lock tests (acquire, release, extend, expiration, ownership)
- [ ] Share link tests (create, access, revoke, expiration, permissions)
- [ ] Presence broadcast tests (join, leave, idle, multi-user scenarios)
- [ ] Conflict resolution tests (concurrent edits, version conflicts, UI warnings)

### E2E Tests
- [ ] Multi-user collaboration scenarios (2 users editing same workflow, conflict resolution)
- [ ] Team management workflows (create team, add members, assign roles, verify permissions)
- [ ] Comment threads (create comment, reply, mention, resolve, verify permissions)
- [ ] Share link workflows (create share, access via link, verify permissions, revoke)
- [ ] Presence workflows (user joins, presence indicators update, user leaves, presence expires)
- [ ] Agent collaboration (agent joins session, governance checks, multi-agent coordination)

### Performance Tests
- [ ] Presence broadcast latency (<100ms target with 100 users in workspace)
- [ ] Edit lock acquisition latency (<50ms target with cached checks)
- [ ] Permission check latency (<50ms target with GovernanceCache)
- [ ] Cursor update throughput (10 users, 5 updates/sec each, verify no DB lock contention)
- [ ] WebSocket connection cleanup (100 connections drop, verify all cleaned up within 3 min)

### Security Tests
- [ ] WebSocket permission escalation test (craft message with spoofed user_id, verify rejected)
- [ ] Share link ownership test (non-owner attempts to share, verify 403 error)
- [ ] RBAC bypass test (guest attempts admin action, verify denied)
- [ ] Edit lock ownership test (user attempts to release lock held by another, verify denied)
- [ ] JWT validation test (expired token, invalid token, missing token)

## Documentation Requirements

- [ ] Architecture documentation for collaboration system (WebSocket, Redis, PostgreSQL integration)
- [ ] API documentation for all collaboration endpoints (OpenAPI spec)
- [ ] WebSocket protocol documentation (message formats, event types, reconnection strategy)
- [ ] RBAC guide (team roles, permissions, ownership-based authorization)
- [ ] Deployment guide (Redis setup, WebSocket configuration, scaling considerations)
- [ ] Troubleshooting guide (common issues, debugging tips, performance tuning)

## Migration Requirements

- [ ] Alembic migration for 6 new collaboration models with proper indexes
- [ ] Database migration for Workflow model version field addition
- [ ] Redis namespace setup for collaboration keys (presence:, cursor:, session:, etc.)
- [ ] GovernanceCache key pattern setup for permission caching
- [ ] WebSocket endpoint configuration in production environment
- [ ] Backward compatibility with existing agent collaboration features

## Rollback Requirements

- [ ] Database migration rollback script (drop collaboration models if needed)
- [ ] Feature flags to disable collaboration features without code deployment
- [ ] Graceful degradation if Redis unavailable (fallback to database for presence)
- [ ] WebSocket fallback to HTTP polling if WebSocket unavailable
- [ ] Emergency bypass for governance checks (EMERGENCY_GOVERNANCE_BYPASS env var)

---
*Requirements defined: March 26, 2026*
*Last updated: March 26, 2026 after initial requirements definition*
