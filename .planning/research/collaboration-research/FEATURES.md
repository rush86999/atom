# Feature Research: Real-Time Collaboration & Team Management

**Domain:** Real-time collaboration and team management for AI-powered business automation platform
**Researched:** March 26, 2026
**Confidence:** MEDIUM (based on existing codebase analysis and collaboration patterns)

**Note:** Web search services were unavailable during research. Findings are based on:
- Existing Atom codebase (collaboration_service.py, canvas_collaboration_service.py, websockets.py)
- Industry-standard collaboration patterns
- Database models (User, Team, Workspace, UserRole, CanvasCollaborationSession)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist in any collaboration platform. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **User Presence Indicators** | Users need to know who's online/active | LOW | Online/offline/away status, last seen timestamp |
| **Live Cursor Tracking** | Visual awareness of where others are working | MEDIUM | Real-time cursor positions with user names/colors |
| **Real-Time Updates** | Changes appear instantly without refresh | HIGH | WebSocket-based pub/sub (already exists: `websockets.py`) |
| **Basic Comments** | Feedback and discussion on resources | LOW | Comments threading, @mentions, resolved status |
| **Resource Sharing** | Share workflows/agents/canvases with others | LOW | Shareable links with permission levels (view/edit/comment) |
| **Team Creation/Management** | Basic organizational structure | LOW | Team CRUD operations, member management |
| **User Roles** | Permission boundaries (Owner/Admin/Member/Viewer) | MEDIUM | `UserRole` enum exists, needs RBAC implementation |
| **Activity Feed** | See what's happening on resources | LOW | Recent changes, who did what, when |
| **Edit Locks** | Prevent concurrent edit conflicts | MEDIUM | Acquire/release locks, expiry handling (already stubbed in `collaboration_service.py`) |
| **Typing Indicators** | Know when someone is editing/typing | LOW | "User X is typing..." for agent/chat interactions |

### Differentiators (Competitive Advantage)

Features that set Atom apart from standard collaboration tools.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **AI Agent Collaboration** | Multi-agent coordination on shared canvases | HIGH | Already partially implemented in `canvas_collaboration_service.py` - agents as participants |
| **Agent Governance in Teams** | Maturity-based agent permissions (STUDENT→INTERN→SUPERVISED→AUTONOMOUS) | MEDIUM | Leverage existing `agent_governance_service.py` for team-aware governance |
| **Canvas-Aware Presence** | Show which agents are working on which canvas components | MEDIUM | Agent participants, cursor tracking at node level |
| **Collaborative Agent Training** | Teams can train student agents together | HIGH | Shared training sessions, collective supervision |
| **Workflow Co-Editing** | Multiple users editing agent workflows simultaneously | HIGH | Requires OT/CRDT for conflict resolution |
| **Smart Conflict Resolution** | AI-suggested merge solutions for concurrent edits | HIGH | LLM-powered conflict resolution using existing BYOK system |
| **Contextual Permissions** | Resource-level RBAC with team inheritance | MEDIUM | Workspace → Team → Resource permission cascade |
| **Real-Time Audit Stream** | Live collaboration events for compliance | LOW | Existing audit infrastructure, needs real-time delivery |
| **Agent Handoff Coordination** | Smooth agent transitions during collaborative sessions | MEDIUM | Already has `agent:handoff` event in `websockets.py` |
| **Presence-Based Routing** | Route agent requests to available team members | MEDIUM | Integration with existing agent governance |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Unlimited Concurrent Editors** | "Everyone should edit at once" | Performance degradation, merge conflicts, UX chaos | Limit to 5-10 concurrent editors with queuing |
| **Real-Time Video/Audio** | "See and hear collaborators" | Bandwidth issues, privacy concerns, distraction | Integrate with existing tools (Slack Huddles, Google Meet) |
| **Granular Undo/Redo** | "Undo every collaborator's action" | Complex state management, conflicts, confusion | Per-user undo for own actions, collaborative history view |
| **Anonymous Collaboration** | "Anyone can join and edit" | Security risk, audit trail broken, governance impossible | Require authentication, guest accounts with limited permissions |
| **Real-Time Everything** | "Live updates for all changes" | Notification fatigue, performance cost, distraction | Batch updates for minor changes, live for critical ones |
| **Complex Permission Inheritance** | "Permissions flow from anywhere" | Unpredictable behavior, hard to debug, security holes | Simple hierarchy: Workspace → Team → Resource |
| **Custom Roles for Every Team** | "Teams define their own roles" | Role explosion, support nightmare, governance conflicts | Fixed roles (Owner/Admin/Member/Viewer) + resource-level permissions |

---

## Feature Dependencies

```
[WebSocket Infrastructure] ✅ EXISTS
    ├──requires──> [User Presence System]
                    ├──requires──> [Team Membership Model]
                    ├──requires──> [User Role System (UserRole enum exists)]
                    └──enhances──> [Real-Time Updates]

[User Presence System]
    ├──requires──> [Team Membership Model]
    ├──requires──> [WebSocket Infrastructure]
    └──enables──> [Live Cursor Tracking]
                └──requires──> [Resource Context (workflow/canvas)]

[Team Management]
    ├──requires──> [User Role System]
    ├──requires──> [Workspace Model (exists)]
    └──enables──> [Team-Based Permissions]
                └──requires──> [RBAC Implementation]

[Collaborative Editing]
    ├──requires──> [Edit Locking System (stub exists)]
    ├──requires──> [Real-Time Updates]
    ├──requires──> [Conflict Resolution]
    └──conflicts──> [Agent Governance] (needs coordination)

[Comments System]
    ├──requires──> [User Authentication]
    ├──requires──> [Resource Context]
    └──enhances──> [Agent Training Feedback]

[Agent Collaboration]
    ├──requires──> [Canvas Collaboration Service (exists)]
    ├──requires──> [Agent Governance Service (exists)]
    ├──requires──> [Multi-Agent Coordination (exists)]
    └──enables──> [Agent Handoff (event exists)]

[RBAC Implementation]
    ├──requires──> [User Role System]
    ├──requires──> [Team Membership]
    ├──requires──> [Permission Model]
    └──enables──> [Resource-Level Security]
```

### Dependency Notes

- **WebSocket Infrastructure EXISTS**: `backend/core/websockets.py` has ConnectionManager with pub/sub, user/team/workspace channels
- **User Role System EXISTS**: `UserRole` enum in models.py (OWNER, ADMIN, MEMBER, VIEWER)
- **Canvas Collaboration Service EXISTS**: `backend/core/canvas_collaboration_service.py` handles multi-agent sessions
- **Edit Locking STUBBED**: `collaboration_service.py` has acquire/release_edit_lock methods but models are TODO
- **Team Management STUBBED**: `Team` model exists but collaboration-specific fields missing
- **Agent Collaboration PARTIAL**: Multi-agent coordination exists, but user+agent collaboration missing

---

## MVP Definition

### Launch With (v1)

Minimum viable product — validate collaborative workflows on Atom.

- [ ] **User Presence** — Online/offline/away status, last active timestamp
  - Why: Foundation for all collaboration features
  - Complexity: LOW
  - Implementation: Heartbeat via WebSocket, presence status in User model

- [ ] **Real-Time Updates** — WebSocket broadcasts for resource changes
  - Why: Users see changes instantly (table stakes)
  - Complexity: MEDIUM
  - Implementation: Extend existing ConnectionManager events

- [ ] **Basic Comments** — Add/view comments on workflows, agents, canvases
  - Why: Feedback loop essential for collaboration
  - Complexity: MEDIUM
  - Implementation: CollaborationComment model (stubbed), REST API + WebSocket broadcast

- [ ] **Team CRUD** — Create teams, add/remove members, assign roles
  - Why: Organizational structure for permissions
  - Complexity: LOW
  - Implementation: Extend existing Team model with membership management

- [ ] **Resource Sharing** — Share workflows/agents via link with permissions
  - Why: Enable cross-team collaboration
  - Complexity: LOW
  - Implementation: WorkflowShare model (stubbed), share link generation

- [ ] **Edit Locks** — Prevent concurrent edits on same resource
  - Why: Avoid data loss and conflicts
  - Complexity: MEDIUM
  - Implementation: EditLock model (stubbed), lock API with expiry

### Add After Validation (v1.x)

Features to add once core collaboration is validated.

- [ ] **Live Cursor Tracking** — Real-time cursor positions for workflows/canvases
  - Trigger: User feedback requesting awareness of others' focus
  - Complexity: MEDIUM
  - Implementation: WebSocket cursor events, frontend cursor rendering

- [ ] **Typing Indicators** — "User X is editing..." for comments/chat
  - Trigger: Users stepping on each other's edits
  - Complexity: LOW
  - Implementation: Debounced typing events via WebSocket

- [ ] **Activity Feed** — Recent changes, who did what, when
  - Trigger: Teams asking "what changed since yesterday?"
  - Complexity: MEDIUM
  - Implementation: Audit log query API, feed aggregation

- [ ] **Agent Collaboration** — Users + agents working together on canvases
  - Trigger: Demand for human-AI co-creation workflows
  - Complexity: HIGH
  - Implementation: Extend CanvasCollaborationService for mixed participants

- [ ] **RBAC Implementation** — Workspace → Team → Resource permissions
  - Trigger: Teams needing fine-grained access control
  - Complexity: HIGH
  - Implementation: Permission model, role checks, inheritance logic

### Future Consideration (v2+)

Defer until product-market fit for collaboration is established.

- [ ] **Collaborative Workflow Editing** — OT/CRDT for concurrent edits
  - Why defer: Complex, uncertain demand, niche use case
  - Alternative: Edit locks + version history

- [ ] **Video/Audio Integration** — Built-in calls/meetings
  - Why defer: Commoditized feature, better integrated via Slack/Zoom
  - Alternative: Deep links to external meeting tools

- [ ] **Custom Team Roles** — Teams define their own roles
  - Why defer: Role explosion, support burden
  - Alternative: Fixed roles (Owner/Admin/Member/Viewer) + resource permissions

- [ ] **AI Conflict Resolution** — LLM-powered merge suggestions
  - Why defer: Unclear value proposition, could confuse users
  - Alternative: Clear conflict UI with manual resolution

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| User Presence | HIGH | LOW | **P1** |
| Real-Time Updates | HIGH | MEDIUM | **P1** |
| Basic Comments | HIGH | MEDIUM | **P1** |
| Team CRUD | HIGH | LOW | **P1** |
| Resource Sharing | HIGH | LOW | **P1** |
| Edit Locks | HIGH | MEDIUM | **P1** |
| Live Cursor Tracking | MEDIUM | MEDIUM | **P2** |
| Typing Indicators | MEDIUM | LOW | **P2** |
| Activity Feed | MEDIUM | MEDIUM | **P2** |
| Agent Collaboration | HIGH | HIGH | **P2** (after P1 validated) |
| RBAC Implementation | HIGH | HIGH | **P2** (after P1 validated) |
| Collaborative Workflow Editing | LOW | HIGH | **P3** |
| Video/Audio Integration | LOW | HIGH | **P3** |
| Custom Team Roles | LOW | HIGH | **P3** |
| AI Conflict Resolution | LOW | HIGH | **P3** |

**Priority key:**
- **P1**: Must have for launch (v1)
- **P2**: Should have, add when validated (v1.x)
- **P3**: Nice to have, future consideration (v2+)

---

## Competitor Feature Analysis

| Feature | Figma | Notion | Miro | Slack | Atom Approach |
|---------|-------|--------|------|-------|---------------|
| **User Presence** | Online/offline avatars | Last seen timestamps | Active cursors | Green dots | Online/offline + activity status |
| **Real-Time Updates** | Milliseconds sync | Instant updates | Live cursors | Instant messages | WebSocket pub/sub (exists) |
| **Comments** | Pin comments, threads | Block comments | Sticky notes | Threaded messages | Resource-level threads |
| **Collaborative Editing** | Multiplayer, OT | Block-level real-time | Infinite canvas real-time | N/A (chat) | Edit locks first, OT later |
| **Cursor Tracking** | Named cursors, colors | N/A | Cursor flags, avatars | N/A | Cursor position + context |
| **Team Management** | Teams, projects | Workspaces, teams | Teams, boards | Workspaces, channels | Workspace → Teams → Resources |
| **Permissions** | Role-based, file-level | Workspace-level | Board-level | Channel-level | RBAC with inheritance |
| **Version History** | Unlimited, visual | Page history | Version timeline | Message history | Audit log (exists) |
| **Agent Collaboration** | N/A | AI mentions | AI side panel | AI agents | Multi-agent canvas sessions (exists) |

**Key Differentiators for Atom:**
1. **Multi-Agent Collaboration**: Atom is unique in having AI agents as first-class participants
2. **Governance-First**: Maturity levels (STUDENT→AUTONOMOUS) apply to team interactions
3. **Canvas-Centric**: Collaboration around canvas presentations, not just documents
4. **Workflow Co-Creation**: Teams build automations together (vs. just documents)

---

## Feature Categories by Complexity

### LOW Complexity (1-2 weeks)
- User presence status
- Team CRUD operations
- Resource sharing links
- Typing indicators
- Basic activity feed

### MEDIUM Complexity (3-6 weeks)
- Real-time updates via WebSocket
- Basic comments with threading
- Edit locking with expiry
- Live cursor tracking
- RBAC implementation
- Agent collaboration (extend existing)

### HIGH Complexity (8-12+ weeks)
- Collaborative workflow editing (OT/CRDT)
- AI conflict resolution
- Advanced agent training collaboration
- Complex permission inheritance
- Cross-organization collaboration

---

## Technical Considerations

### Real-Time Infrastructure
- **WebSocket Manager**: Already exists in `backend/core/websockets.py`
  - Supports user, team, workspace channels
  - Has event types for canvas, agent, device, coordination
  - Needs: Presence events, cursor events, comment events

### Database Models
- **Existing**: User, Team, Workspace, UserRole, CanvasCollaborationSession
- **Stubbed** (need implementation):
  - CollaborationAudit
  - CollaborationComment
  - CollaborationSessionParticipant
  - EditLock
  - WorkflowCollaborationSession
  - WorkflowShare

### Performance Targets
- Presence updates: <100ms via WebSocket
- Cursor tracking: <50ms broadcast
- Comment delivery: <200ms
- Edit lock acquisition: <50ms
- Real-time sync: <500ms for resource changes

### Security Considerations
- All collaboration events must be authenticated
- RBAC checks before every state-changing operation
- Audit logging for all collaborative actions
- Rate limiting on WebSocket events
- Share link expiration and revocation

---

## Sources

- **Existing Atom Codebase**:
  - `backend/core/collaboration_service.py` — Collaboration service with TODO models
  - `backend/core/canvas_collaboration_service.py` — Multi-agent canvas collaboration
  - `backend/core/websockets.py` — WebSocket manager with pub/sub
  - `backend/core/models.py` — User, Team, Workspace, UserRole, CanvasCollaborationSession

- **Industry Patterns** (from training data):
  - Operational Transformation (OT) for concurrent editing
  - CRDTs (Conflict-free Replicated Data Types) for distributed sync
  - Role-Based Access Control (RBAC) best practices
  - WebSocket pub/sub patterns for real-time updates

- **Competitor Analysis** (from training data):
  - Figma: Multiplayer collaborative editing with cursors
  - Notion: Block-level real-time collaboration
  - Miro: Infinite canvas with real-time presence
  - Slack: Workspace/channel-based messaging and presence

**Confidence Assessment**:
- **HIGH**: Existing codebase capabilities (WebSocket, models)
- **MEDIUM**: Industry patterns and competitor features (based on training data)
- **LOW**: Specific 2026 trends (web search unavailable)

---

*Feature research for: Real-time collaboration and team management features*
*Researched: March 26, 2026*
*Confidence: MEDIUM*
