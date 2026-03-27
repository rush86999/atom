# Project Research Summary

**Project:** Atom v9.0 - Real-Time Collaboration & Team Management
**Domain:** Real-time collaboration, team management, RBAC for AI-powered automation platform
**Researched:** March 26, 2026
**Confidence:** HIGH

## Executive Summary

Atom is an AI-powered business automation platform that requires real-time collaboration capabilities to enable teams to work together on workflows, agents, and canvases. Research reveals that **90% of the required infrastructure already exists** — WebSocket managers, Redis pub/sub, SQLAlchemy models, RBAC service, and governance caching. The primary gap is extending these systems for **user-to-user collaboration** (current implementation focuses on agent-to-agent coordination).

The recommended approach is **incremental extension** rather than rebuild: add presence tracking to existing WebSocket infrastructure, implement pessimistic locking for conflict resolution, extend RBAC for team-based permissions, and create 6 new database models for collaboration sessions, comments, edit locks, and sharing. This leverages existing patterns (GovernanceCache for <50ms permission checks, ConnectionManager for WebSocket, ActivityPublisher for events) while adding collaboration-specific features.

**Key risks** identified are primarily operational: WebSocket race conditions causing data loss, memory leaks from orphaned connections, database lock contention from high-frequency updates, and RBAC bypass via missing ownership checks. All are preventable with established patterns: Redis-backed presence with TTL, heartbeat/cleanup mechanisms, optimistic locking with version vectors, and ownership-based authorization. The research shows these are well-solved problems with clear mitigation strategies.

## Key Findings

### Recommended Stack

Atom has solid foundations for real-time collaboration. Primary additions are **minimal and focused**:

**Core technologies:**
- **python-socketio 5.10.0+** — Room-based broadcasting and automatic reconnection — higher-level WebSocket abstraction with presence fallback, proven at scale (Figma, Miro, Notion)
- **y-py 0.6.0+ (CRDT)** — Conflict-free collaborative editing — Python port of Yjs industry standard, enables offline support and conflict resolution without server state
- **casbin 1.34.0+** — Policy-based access control engine — model-agnostic RBAC with role inheritance, audit trails, and dynamic policies without code deploy
- **Redis presence patterns** — User online/offline tracking with TTL — <1ms operations, automatic cleanup via EXPIRE, already installed (Redis 4.5.0+ in requirements.txt)
- **fastapi-async-casbin 0.5.0+** — FastAPI/Casbin integration — Async dependency injection for route-level permissions, works with existing JWT auth

**Why this stack:** Extends existing infrastructure rather than rebuilding. All technologies have Python support, integrate with FastAPI/SQLAlchemy, and are proven in production at scale. The stack adds **presence tracking**, **conflict resolution**, and **fine-grained RBAC** while reusing existing WebSocket managers, governance cache, and database models.

### Expected Features

**Must have (table stakes) — features users assume exist in any collaboration platform:**
- **User Presence Indicators** — Online/offline/away status, last seen timestamp — foundational for all collaboration features
- **Real-Time Updates** — Changes appear instantly without refresh — WebSocket pub/sub (already exists)
- **Basic Comments** — Threaded discussions on workflows/agents/canvases — feedback loop essential
- **Team CRUD** — Create teams, add/remove members, assign roles — organizational structure for permissions
- **Resource Sharing** — Share workflows/agents via link with permissions — enable cross-team collaboration
- **Edit Locks** — Prevent concurrent edit conflicts — avoid data loss, already stubbed in collaboration_service.py

**Should have (competitive differentiators):**
- **Live Cursor Tracking** — Real-time cursor positions with user names/colors — visual awareness of collaborators' focus
- **Agent Collaboration** — Multi-agent coordination on shared canvases — unique Atom differentiator (agents as first-class participants)
- **Agent Governance in Teams** — Maturity-based permissions (STUDENT→INTERN→SUPERVISED→AUTONOMOUS) applied to team interactions
- **Workflow Co-Editing** — Multiple users editing agent workflows simultaneously — requires OT/CRDT for conflict resolution
- **Contextual Permissions** — Resource-level RBAC with team inheritance — Workspace → Team → Resource cascade

**Defer to v2+:**
- **Collaborative Workflow Editing (OT/CRDT)** — Complex, uncertain demand, niche use case — alternative: edit locks + version history
- **Video/Audio Integration** — Commoditized feature, better integrated via Slack/Zoom — alternative: deep links to external tools
- **Custom Team Roles** — Role explosion, support burden — alternative: fixed roles (Owner/Admin/Member/Viewer) + resource permissions
- **AI Conflict Resolution** — Unclear value proposition, could confuse users — alternative: clear conflict UI with manual resolution

### Architecture Approach

The recommended architecture extends **existing Atom patterns** rather than introducing new paradigms. Four new services (UserPresenceService, ConflictResolutionService, TeamManagementService, CommentService) integrate with existing components (ConnectionManager, RBACService, GovernanceCache, ActivityPublisher). Data flows through REST API for state-changing operations and WebSocket for real-time broadcasts, with Redis backing transient state (presence, cursors) and PostgreSQL for persistent data (sessions, locks, comments).

**Major components:**
1. **UserPresenceService** — Redis-backed presence tracking with TTL-based expiration, heartbeat management (30s intervals, 60s TTL), pub/sub for real-time broadcasts to all workspace members
2. **ConflictResolutionService** — Pessimistic locking using existing EditLock pattern, version vectors for conflict detection, integration with Workflow model for optimistic locking
3. **TeamManagementService** — Team CRUD operations, member management, role assignment using existing User/Team/Workspace relationships, extends RBACService for team-based permissions
4. **CollaborationSessionService** — Session lifecycle management (create/join/leave), participant tracking with cursor positions, session state persistence via Redis + PostgreSQL
5. **CommentService** — Threaded comments with recursive CTEs for nesting, @mentions with notifications, comment permissions linked to resource access
6. **RBACService (EXTEND)** — Add team-based permissions and resource-level ACLs, cache results in GovernanceCache for <50ms lookups, support role inheritance (team_lead inherits member permissions)

**Integration points:** All services use existing GovernanceCache for performance, ConnectionManager for WebSocket broadcasts, ActivityPublisher for audit events, and SQLAlchemy context managers for database transactions. This maintains consistency with current Atom architecture while adding collaboration capabilities.

### Critical Pitfalls

**Top 5 pitfalls with prevention strategies:**

1. **WebSocket Race Conditions in Collaborative Editing** — Multiple users edit same workflow node simultaneously, last-write-wins causes data loss
   - **Prevention:** Add version field to Workflow model with optimistic locking, check version on update, broadcast edit intent before committing
   - **Phase to address:** Phase 01 (Foundation Models & Basic RBAC) - add versioning to Workflow model

2. **Permission Escalation via WebSocket Message Spoofing** — Attacker crafts WebSocket message claiming to be another user with higher privileges
   - **Prevention:** NEVER trust user_id from client messages, validate JWT on connection AND re-validate on every sensitive action, use server-side user_id for audit
   - **Phase to address:** Phase 02 (WebSocket Infrastructure) - hardened WebSocket handlers with RBAC

3. **Memory Leaks from Orphaned WebSocket Connections** — Connections accumulate without proper cleanup, memory grows until OOM kill
   - **Prevention:** Add heartbeat/ping mechanism (30s timeout), periodic cleanup task for dead connections (>2min inactivity), ALWAYS cleanup in finally blocks
   - **Phase to address:** Phase 02 (WebSocket Infrastructure) - implement heartbeat + cleanup

4. **Database Lock Contention from High-Frequency Updates** — Cursor positions, heartbeats write to DB on every change, locks cause latency spikes
   - **Prevention:** Use Redis for high-frequency data (cursor positions, heartbeats) with 2-min TTL, periodic batch sync to DB (every 30s), separate tables for high vs low frequency data
   - **Phase to address:** Phase 03 (Real-Time Presence & Activity) - Redis-backed state management

5. **RBAC Bypass via Missing Ownership Checks** — User creates share link for workflow they don't own, system checks role but not ownership
   - **Prevention:** Separate permission checks (ownership OR explicit share permission), authorization decorator requiring both role + ownership, verify created_by before allowing share operations
   - **Phase to address:** Phase 01 (Foundation Models & Basic RBAC) - ownership-based authorization

## Implications for Roadmap

Based on research, suggested phase structure for Atom v9.0 Collaboration & Team Management:

### Phase 1: Foundation Models & Basic RBAC
**Rationale:** Database models are foundational — all services depend on them. RBAC ownership checks prevent critical security vulnerabilities (data leaks via unauthorized sharing). Versioning on Workflow model prevents concurrent edit data loss.

**Delivers:**
- 6 new database models: WorkflowCollaborationSession, CollaborationComment, EditLock, WorkflowShare, CollaborationAudit, CollaborationSessionParticipant
- Alembic migration with proper indexes and foreign keys
- Ownership-based authorization for share operations
- Version field on Workflow model for optimistic locking
- CollaborationAudit middleware for audit logging

**Addresses:** Team CRUD, Resource Sharing, Basic Comments, Edit Locks (from FEATURES.md table stakes)

**Avoids:** Pitfall 5 (RBAC bypass), Pitfall 1 (concurrent edit data loss), Pitfall 8 (missing audit trail)

**Stack elements:** SQLAlchemy 2.0 (already installed), PostgreSQL (existing)

### Phase 2: WebSocket Infrastructure & Security
**Rationale:** Real-time features depend on WebSocket infrastructure. Security hardening prevents permission escalation (critical). Presence tracking requires WebSocket extensions. This phase builds the communication layer for all collaboration features.

**Delivers:**
- Extended ConnectionManager with presence events (user:join, user:leave, user:typing)
- CollaborationWebSocketManager with room-based routing (workflow_{id} rooms)
- Hardened WebSocket handlers with per-message authorization
- Heartbeat/ping mechanism (30s timeout)
- Periodic cleanup task for dead connections (>2min inactivity)
- Redis-backed session state (survives server restart)
- Client-side auto-reconnect with exponential backoff

**Addresses:** User Presence, Real-Time Updates (from FEATURES.md table stakes)

**Avoids:** Pitfall 2 (permission escalation), Pitfall 3 (memory leaks), Pitfall 6 (stale state after restart)

**Stack elements:** python-socketio 5.10.0+, Redis presence patterns (already installed), FastAPI WebSocket (existing)

### Phase 3: Real-Time Presence & Activity
**Rationale:** Presence is the foundation for awareness features. Redis-backed state prevents database lock contention (performance pitfall). Targeted broadcasts prevent CPU spikes from broadcast storms. This phase delivers the "who's online" and real-time awareness capabilities.

**Delivers:**
- UserPresenceService with Redis-backed presence tracking
- Heartbeat management (30s intervals, 60s TTL)
- Online/offline/away status with last seen timestamps
- Typing indicators with auto-expiry (10s timeout)
- Targeted broadcasts (only to users viewing relevant workflow)
- Update batching (max 50 messages or 100ms)
- Live cursor tracking with real-time position broadcasts
- Activity feed (recent changes, who did what, when)

**Addresses:** User Presence Indicators, Live Cursor Tracking, Typing Indicators, Activity Feed (from FEATURES.md)

**Avoids:** Pitfall 4 (database lock contention), Pitfall 7 (broadcast storms), Pitfall 9 (stale typing indicators)

**Stack elements:** Redis presence patterns, python-socketio rooms

### Phase 4: Team-Based RBAC & Permissions
**Rationale:** Team management requires organizational structure. RBAC extension enables fine-grained permissions. Resource-level ACLs provide security boundaries. GovernanceCache integration ensures performance (<50ms permission checks).

**Delivers:**
- TeamManagementService (team CRUD, member management, role assignment)
- Extended RBACService with team-based permissions
- Resource-level ACLs (resource_type, resource_id, permissions JSONB)
- Role inheritance (team_lead inherits member permissions)
- Permission caching in GovernanceCache
- Casbin integration with model.conf and policy.csv
- FastAPI dependency injection for route-level permissions
- check_permission decorator for authorization

**Addresses:** Team Creation/Management, User Roles, Contextual Permissions (from FEATURES.md)

**Avoids:** Pitfall 5 (RBAC bypass via missing ownership checks)

**Stack elements:** casbin 1.34.0+, fastapi-async-casbin 0.5.0+, python-jose (already installed)

### Phase 5: Conflict Resolution & Collaborative Editing
**Rationale:** Collaborative editing requires conflict resolution. Pessimistic locking prevents concurrent edits. Version vectors detect conflicts. This phase enables simultaneous editing while maintaining data integrity.

**Delivers:**
- ConflictResolutionService with pessimistic locking
- EditLock CRUD (acquire, release, check, extend)
- Version vector conflict detection on Workflow model
- Conflict resolution UI (warn before overwriting)
- Integration with existing EditLock pattern from CollaborationService
- Lock expiry handling (30-minute default)
- Lock status broadcasting via WebSocket

**Addresses:** Edit Locks, Collaborative Workflow Editing (from FEATURES.md)

**Avoids:** Pitfall 1 (concurrent edit data loss)

**Stack elements:** y-py 0.6.0+ for CRDT (deferred to v2), pessimistic locking via SQLAlchemy (existing)

### Phase 6: Comments & Collaboration Sessions
**Rationale:** Comments enable feedback and discussion. Collaboration sessions coordinate multi-user workflows. Mentions and notifications improve awareness. This phase completes the collaboration feature set.

**Delivers:**
- CommentService with threaded comments (recursive CTEs for nesting)
- Comment CRUD (create, reply, edit, delete, resolve)
- @mentions with notifications
- Comment permissions (linked to resource access)
- CollaborationSessionService (create, join, leave, list)
- Session participant tracking with cursor positions
- Session state persistence (Redis + PostgreSQL)
- Real-time comment delivery via WebSocket

**Addresses:** Basic Comments, Agent Collaboration (from FEATURES.md)

**Stack elements:** SQLAlchemy recursive CTEs, WebSocket pub/sub (existing)

### Phase 7: Advanced Collaboration (v2+)
**Rationale:** Advanced features require complex technology (OT/CRDT). Defer until core collaboration is validated and product-market fit is established. These are differentiators but not blockers for launch.

**Delivers:**
- y-py CRDT integration for conflict-free collaborative editing
- Yjs WebSocket adapter for delta broadcast
- Collaborative workflow editing (simultaneous edits)
- AI conflict resolution with LLM-powered merge suggestions
- Custom team roles (user-defined roles)
- Video/audio integration (Slack/Zoom deep links)

**Addresses:** Collaborative Workflow Editing, AI Conflict Resolution, Custom Team Roles (from FEATURES.md differentiators)

**Stack elements:** y-py 0.6.0+, y-socketio 0.6.0+, LLM integration (existing BYOK)

### Phase Ordering Rationale

**Dependency-driven ordering:** Database models (Phase 1) → WebSocket infrastructure (Phase 2) → Presence (Phase 3) → RBAC (Phase 4) → Conflict resolution (Phase 5) → Comments/Sessions (Phase 6) → Advanced (Phase 7). Each phase builds on previous deliverables.

**Grouped by capability:** Foundation (models + RBAC) → Real-time infrastructure (WebSocket + presence) → Security (team permissions) → Collaboration features (conflict resolution + comments) → Advanced differentiation.

**Pitfall avoidance:** Critical security pitfalls (permission escalation, RBAC bypass) addressed early (Phase 1-2). Performance pitfalls (database lock contention, broadcast storms) addressed in Phase 3. Data loss pitfalls (concurrent edits) addressed in Phase 5.

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 5 (Conflict Resolution):** Evaluate y-py vs. operational transformation libraries for Python, research conflict resolution UI patterns, verify version vector implementation with SQLAlchemy 2.0
- **Phase 7 (Advanced Collaboration):** Research OT vs. CRDT libraries (y-py vs. Automerge), verify Yjs WebSocket adapter compatibility with python-socketio, research AI conflict resolution prompt engineering

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Foundation Models):** Standard SQLAlchemy patterns, well-documented Alembic migrations, established RBAC ownership patterns
- **Phase 2 (WebSocket Infrastructure):** FastAPI WebSocket patterns are well-documented, python-socketio has comprehensive examples, heartbeat/cleanup is established pattern
- **Phase 3 (Real-Time Presence):** Redis presence patterns are standard (SETEX with TTL), pub/sub is well-documented, typing indicators are common pattern
- **Phase 4 (Team-Based RBAC):** Casbin has extensive documentation, FastAPI dependency injection is standard, role inheritance is well-understood
- **Phase 6 (Comments & Sessions):** Recursive CTEs for nested comments are standard PostgreSQL pattern, WebSocket event broadcasting is existing pattern

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Based on existing infrastructure analysis (WebSocket managers, RBAC service, governance cache) and official documentation (python-socketio, Casbin, y-py) |
| Features | MEDIUM | Table stakes features are well-established (presence, comments, sharing), differentiators are based on Atom's unique agent collaboration capabilities but web search was unavailable for 2026 trends |
| Architecture | HIGH | Architecture patterns are proven in production (Figma, Notion, Miro), integration with existing Atom components is clear, data flows are well-understood |
| Pitfalls | HIGH | Pitfalls are based on common production issues (race conditions, memory leaks, lock contention), prevention strategies are established patterns, detection methods are actionable |

**Overall confidence:** HIGH

Research is based on:
- Existing Atom codebase analysis (collaboration_service.py, websocket_manager.py, models.py, rbac_service.py)
- Official documentation (python-socketio, Casbin, y-py, Redis, FastAPI)
- Established production patterns (Figma, Notion, Miro collaboration architectures)
- Common operational issues (WebSocket race conditions, memory leaks, database lock contention)

Only limitation: web search was unavailable during research (rate limits), so 2026-specific trends could not be verified. However, collaboration patterns are stable and well-established, so this is not a significant gap.

### Gaps to Address

- **CRDT library selection:** Research recommends y-py but verification against alternatives (Automerge) during Phase 5 planning would be prudent
- **Conflict resolution UI patterns:** Research identifies the need for conflict resolution UI but specific patterns are not detailed — should be researched during Phase 5 planning
- **AI conflict resolution prompts:** Research flags this as v2+ feature, but if implemented in Phase 7, will need prompt engineering research for LLM-powered merge suggestions
- **Performance at scale:** Research identifies scaling considerations (CRDTs for 100+ concurrent editors, Redis Cluster for 10k+ users) but these are edge cases — can be addressed when needed

These gaps are not blockers for initial implementation but should be flagged for phase-specific research during planning.

## Sources

### Primary (HIGH confidence)
- **Existing Atom Codebase** — Analyzed collaboration_service.py (742 lines), websocket_manager.py (473 lines), canvas_collaboration_service.py (840 lines), models.py (User, Team, Workspace, UserRole, EditLock), rbac_service.py
- **Official Documentation** — python-socketio (room management, automatic reconnection), Casbin (policy-based RBAC), y-py (CRDT for Python), Redis (presence patterns with SETEX/TTL), FastAPI WebSocket (connection management)
- **Production Architectures** — Figma (WebSocket rooms, CRDT), Notion (Yjs-based real-time collaboration), Miro (Redis-based presence system)

### Secondary (MEDIUM confidence)
- **Industry Patterns** — Operational Transformation vs. CRDT trade-offs, RBAC best practices (role inheritance, resource ACLs), WebSocket pub/sub patterns for horizontal scaling
- **Competitor Analysis** — Figma (multiplayer editing with cursors), Notion (block-level real-time collaboration), Miro (infinite canvas with presence), Slack (workspace/channel-based messaging)
- **Database Patterns** — SQLAlchemy 2.0 async support, recursive CTEs for nested comments, optimistic locking with version vectors, PostgreSQL JSONB for permissions

### Tertiary (LOW confidence)
- **2026 Trends** — Web search was unavailable (rate limits), so latest 2025-2026 collaboration framework trends could not be verified. However, collaboration patterns are stable and well-established, so this is not a significant gap.

---
*Research completed: March 26, 2026*
*Ready for roadmap: yes*
