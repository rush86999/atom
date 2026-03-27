# Roadmap: Atom v9.0 Collaboration & Team Management

## Overview

Atom v9.0 enables real-time collaboration and team management for workflows, agents, and canvases. This milestone delivers user presence, live updates, collaborative editing with conflict resolution, threaded comments, team-based RBAC, and shared resources. The journey begins with database models and basic RBAC, builds WebSocket infrastructure for real-time features, adds team management and permissions, implements conflict resolution with edit locks, delivers comments and collaboration sessions, and culminates in advanced features like live cursors, agent collaboration, and workflow co-editing.

## Milestones

- ✅ **v8.0 Automated Bug Discovery & QA Testing** - Phases 237-245 (shipped 2026-03-24)
- 🚧 **v9.0 Collaboration & Team Management** - Phases 246-252 (in progress)
- 📋 **v10.0 [Next Milestone]** - Phases 253+ (planned)

## Phases

<details>
<summary>✅ v8.0 Automated Bug Discovery & QA Testing (Phases 237-245) - SHIPPED 2026-03-24</summary>

### Phase 237: Bug Discovery Infrastructure Foundation
**Goal**: Bug discovery integrates into existing pytest infrastructure with separate CI pipelines
**Plans**: 5 plans
**Completed**: 2026-03-24

### Phase 238: Property-Based Testing Expansion
**Goal**: 50+ new property tests validate critical invariants across agent execution, LLM routing, episodic memory, governance, and security
**Plans**: 5 plans
**Completed**: 2026-03-24

### Phase 239: API Fuzzing Infrastructure
**Goal**: Coverage-guided fuzzing for FastAPI endpoints discovers crashes in parsing/validation code
**Plans**: 5 plans
**Completed**: 2026-03-24

### Phase 240: Headless Browser Bug Discovery
**Goal**: Intelligent exploration agent discovers UI bugs through console errors, accessibility violations, broken links, visual regression
**Plans**: 5 plans
**Completed**: 2026-03-25

### Phase 241: Chaos Engineering Integration
**Goal**: Controlled failure injection tests resilience to network issues, resource exhaustion, and service crashes
**Plans**: 7 plans
**Status**: Not started

### Phase 242: Unified Bug Discovery Pipeline
**Goal**: Orchestrate all discovery methods with result aggregation, deduplication, automated triage, and GitHub filing
**Plans**: TBD
**Status**: Not started

### Phase 243: Memory & Performance Bug Discovery
**Goal**: Specialized discovery for memory leaks and performance regressions using memray and pytest-benchmark
**Plans**: 5 plans
**Completed**: 2026-03-25

### Phase 244: AI-Enhanced Bug Discovery
**Goal**: Multi-agent fuzzing orchestration and AI-generated invariants expand bug discovery coverage
**Plans**: 4 plans
**Completed**: 2026-03-25

### Phase 245: Feedback Loops & ROI Tracking
**Goal**: Close the loop with regression test generation, effectiveness metrics, and ROI tracking
**Plans**: 6 plans
**Status**: Complete (5/6 executed, 1 pending manual execution)

</details>

### 🚧 v9.0 Collaboration & Team Management (In Progress)

**Milestone Goal:** Enable real-time collaboration and team management for workflows, agents, and canvases with user presence, live updates, collaborative editing, comments/threads, role-based access control (RBAC), and shared resources.

- [ ] **Phase 246: Foundation Models & Basic RBAC** - Database models and ownership-based authorization
- [ ] **Phase 247: WebSocket Infrastructure & Security** - Real-time communication with hardened security
- [ ] **Phase 248: User Presence & Real-Time Activity** - Online/offline tracking and live updates
- [ ] **Phase 249: Team-Based RBAC & Permissions** - Team management with role inheritance
- [ ] **Phase 250: Conflict Resolution & Resource Sharing** - Edit locks and share links
- [ ] **Phase 251: Comments & Collaboration Sessions** - Threaded comments and session management
- [ ] **Phase 252: Advanced Features (Cursors, Agents, Co-Editing)** - Live cursors, agent collaboration, workflow co-editing

#### Phase 246: Foundation Models & Basic RBAC
**Goal**: Database foundation for collaboration with ownership-based authorization and version control
**Depends on**: Nothing (first phase of v9.0)
**Requirements**: DB-01, DB-02, DB-03, DB-04, DB-05, DB-06, RBAC-01, CONF-03
**Success Criteria** (what must be TRUE):
  1. System stores all collaboration data (sessions, comments, locks, shares, audit logs, participants) in PostgreSQL with proper relationships
  2. Users cannot share or modify resources they don't own (ownership-based authorization enforced)
  3. Workflow model has version field that detects concurrent modifications and raises conflicts on stale updates
  4. All collaboration actions create audit log entries with before/after state, action type, user context, and timestamps
**Plans**: TBD

Plans:
- [ ] 246-01: Create 6 collaboration database models (WorkflowCollaborationSession, CollaborationComment, EditLock, WorkflowShare, CollaborationAudit, CollaborationSessionParticipant)
- [ ] 246-02: Implement ownership-based authorization decorator and service layer
- [ ] 246-03: Add version field to Workflow model with optimistic locking and conflict detection
- [ ] 246-04: Create CollaborationAudit middleware for audit logging

#### Phase 247: WebSocket Infrastructure & Security
**Goal**: Secure WebSocket infrastructure for real-time collaboration with heartbeat, cleanup, and deduplication
**Depends on**: Phase 246
**Requirements**: WS-01, WS-02, WS-03, WS-04
**Success Criteria** (what must be TRUE):
  1. WebSocket connections require JWT token validation on connection AND re-validation on every sensitive action (prevents permission escalation)
  2. Dead connections are detected within 30 seconds via heartbeat and cleaned up within 2 minutes of inactivity (prevents memory leaks)
  3. Users with multiple connections receive notifications once per user (not per connection) to prevent duplicate notifications
  4. Collaboration state persists to Redis and survives server restarts with client auto-reconnect using exponential backoff
**Plans**: TBD

Plans:
- [ ] 247-01: Extend ConnectionManager with presence events and room-based routing (workflow_{id} rooms)
- [ ] 247-02: Implement CollaborationWebSocketManager with hardened handlers and per-message authorization
- [ ] 247-03: Add heartbeat/ping mechanism (30s timeout) and periodic cleanup task (60s for >2min inactivity)
- [ ] 247-04: Implement Redis-backed session state with client-side auto-reconnect and exponential backoff
- [ ] 247-05: Add notification deduplication per user across multiple WebSocket connections

#### Phase 248: User Presence & Real-Time Activity
**Goal**: Real-time user presence tracking and live updates for collaboration awareness
**Depends on**: Phase 247
**Requirements**: PRES-01, PRES-02, PRES-03, REAL-01, REAL-02, REAL-03
**Success Criteria** (what must be TRUE):
  1. Users see online/offline/away status for all workspace members with last seen timestamps and current resource viewing
  2. Presence changes broadcast in real-time to all workspace members via WebSocket when users join/leave/go idle
  3. Workflow/agent/canvas changes appear instantly to all connected clients via WebSocket without requiring page refresh
  4. Updates target only users viewing the affected resource (room-based broadcasting) to prevent broadcast storms
  5. Stale presence auto-expires after 60 seconds of inactivity (2x heartbeat interval of 30s)
**Plans**: TBD

Plans:
- [ ] 248-01: Implement UserPresenceService with Redis-backed presence tracking and heartbeat management
- [ ] 248-02: Add presence broadcast events (user:join, user:leave, user:idle) with online/offline/away status
- [ ] 248-03: Implement real-time update broadcasting for workflow/agent/canvas changes via WebSocket rooms
- [ ] 248-04: Add Redis-based persistence for collaboration state with automatic cleanup on expiration
- [ ] 248-05: Implement client-side auto-reconnect with exponential backoff (1s → 2s → 4s → 8s max)

#### Phase 249: Team-Based RBAC & Permissions
**Goal**: Team management with hierarchical roles and resource-level ACLs for fine-grained permissions
**Depends on**: Phase 246 (Foundation Models & Basic RBAC)
**Requirements**: TEAM-01, TEAM-02, TEAM-03, TEAM-04, TEAM-05, TEAM-06, RBAC-02, RBAC-03, RBAC-04, RBAC-05
**Success Criteria** (what must be TRUE):
  1. Authorized users can create teams with name, description, and default roles (owner/admin/member/viewer)
  2. Team owners and admins can add/remove members with role assignment and hierarchical permission inheritance (owner > admin > member > viewer)
  3. System supports resource-level ACLs with fine-grained permissions (resource_type, resource_id, permissions JSONB)
  4. Permission checks complete in <50ms using GovernanceCache with cache invalidation on permission changes
  5. RBAC checks apply to ALL users including guests and apply to WebSocket messages (not just REST API endpoints)
**Plans**: TBD

Plans:
- [ ] 249-01: Implement TeamManagementService (team CRUD, member management, role assignment)
- [ ] 249-02: Extend RBACService with team-based permissions and role inheritance (team_lead inherits member permissions)
- [ ] 249-03: Implement resource-level ACLs (resource_type, resource_id, permissions JSONB) with authorization decorator
- [ ] 249-04: Integrate permission caching in GovernanceCache with <50ms lookups and cache invalidation
- [ ] 249-05: Add Casbin integration with model.conf and policy.csv for policy-based RBAC
- [ ] 249-06: Implement FastAPI dependency injection for route-level permissions and check_permission decorator

#### Phase 250: Conflict Resolution & Resource Sharing
**Goal**: Prevent concurrent edit conflicts with pessimistic locking and enable secure resource sharing
**Depends on**: Phase 246 (Foundation Models & Basic RBAC), Phase 248 (User Presence)
**Requirements**: CONF-01, CONF-02, CONF-04, SHARE-01, SHARE-02, SHARE-03, SHARE-04
**Success Criteria** (what must be TRUE):
  1. Users must acquire edit locks before editing resources to prevent concurrent edit conflicts
  2. Edit locks expire after 30 minutes of inactivity with automatic release and users can extend active locks
  3. System shows conflict resolution UI when concurrent edits detected warning users before overwriting changes
  4. Workflow owners can create share links with customizable permissions (can_view/can_edit/can_share) and optional expiration
  5. Share links use cryptographically secure random tokens and track usage count with revocation support
**Plans**: TBD

Plans:
- [ ] 250-01: Implement ConflictResolutionService with pessimistic locking (acquire, release, check, extend)
- [ ] 250-02: Add edit lock expiry handling (30-minute default) and lock status broadcasting via WebSocket
- [ ] 250-03: Implement conflict resolution UI with warnings before overwriting concurrent changes
- [ ] 250-04: Implement share link creation with permissions, expiration, usage tracking, and revocation
- [ ] 250-05: Add share link access with permission validation and secure token generation (UUID4 or secrets.token_urlsafe())

#### Phase 251: Comments & Collaboration Sessions
**Goal**: Threaded comments with @mentions and collaboration session management for multi-user workflows
**Depends on**: Phase 246 (Foundation Models), Phase 248 (User Presence), Phase 249 (Team RBAC)
**Requirements**: COMM-01, COMM-02, COMM-03, COMM-04, COMM-05
**Success Criteria** (what must be TRUE):
  1. Authorized users can create threaded comments on workflows/agents/canvases with context-aware placement (node/canvas/workflow-level)
  2. Users can reply to comments forming nested threads with recursive CTE queries for retrieval and parent-child relationships
  3. Users can @mention other users in comments which triggers notifications and mentioned users receive real-time alerts
  4. Comment authors and authorized users can edit/delete their own comments with audit trail and version tracking
  5. Users can resolve comment threads marking them as resolved with resolver tracking and resolution timestamp
**Plans**: TBD

Plans:
- [ ] 251-01: Implement CommentService with threaded comments (recursive CTEs for nesting)
- [ ] 251-02: Add comment CRUD operations (create, reply, edit, delete, resolve) with permissions linked to resource access
- [ ] 251-03: Implement @mention parsing in comment content with notification delivery to mentioned users
- [ ] 251-04: Add CollaborationSessionService (create, join, leave, list) with participant tracking
- [ ] 251-05: Implement session state persistence (Redis + PostgreSQL) and real-time comment delivery via WebSocket

#### Phase 252: Advanced Features (Cursors, Agents, Co-Editing)
**Goal**: Live cursor tracking, agent collaboration governance, and workflow co-editing with presence indicators
**Depends on**: Phase 247 (WebSocket Infrastructure), Phase 248 (User Presence), Phase 250 (Conflict Resolution)
**Requirements**: CURS-01, CURS-02, CURS-03, AGENT-01, AGENT-02, AGENT-03, COED-01, COED-02
**Success Criteria** (what must be TRUE):
  1. System broadcasts real-time cursor positions to all users viewing the same workflow with user names and colors for visual identification
  2. Multiple agents can coordinate on shared canvases with role-based permissions (STUDENT agents blocked, INTERN+ require approval)
  3. Agent maturity levels (STUDENT/INTERN/SUPERVISED/AUTONOMOUS) are enforced in collaboration sessions with governance checks
  4. Multiple users can view workflows simultaneously with presence indicators showing who is viewing each node/canvas
  5. System uses pessimistic locking for edit conflicts with visual lock indicators showing who is editing what
**Plans**: TBD

Plans:
- [ ] 252-01: Implement live cursor tracking with Redis storage (2-min TTL) and batched broadcasts (max 50 messages or 100ms)
- [ ] 252-02: Extend CanvasCollaborationService to support both agent-to-agent and user-to-user collaboration
- [ ] 252-03: Add agent maturity checks (STUDENT blocked, INTERN requires approval, SUPERVISED/AUTONOMOUS allowed) on collaboration session join
- [ ] 252-04: Implement workflow co-editing with presence indicators showing who is viewing each node/canvas
- [ ] 252-05: Add pessimistic lock acquisition before editing with visual lock indicators showing who is editing what

## Progress

**Execution Order:**
Phases execute in numeric order: 246 → 247 → 248 → 249 → 250 → 251 → 252

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 246. Foundation Models & Basic RBAC | v9.0 | 0/4 | Not started | - |
| 247. WebSocket Infrastructure & Security | v9.0 | 0/5 | Not started | - |
| 248. User Presence & Real-Time Activity | v9.0 | 0/5 | Not started | - |
| 249. Team-Based RBAC & Permissions | v9.0 | 0/6 | Not started | - |
| 250. Conflict Resolution & Resource Sharing | v9.0 | 0/5 | Not started | - |
| 251. Comments & Collaboration Sessions | v9.0 | 0/5 | Not started | - |
| 252. Advanced Features (Cursors, Agents, Co-Editing) | v9.0 | 0/5 | Not started | - |

**Overall Progress:** 0/35 plans complete (0%)
