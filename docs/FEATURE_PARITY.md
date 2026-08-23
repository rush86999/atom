# Feature Parity Matrix — Web / Mobile / Desktop / CLI

> **Created**: Round 80s (Aug 2026). Audits the four surfaces against each
> other for user-journey coverage. ✅ shipped · 🟡 partial · ❌ missing ·
> ➖ not applicable (surface-inappropriate)

| Feature | Web | Mobile | Desktop (menubar) | CLI (`atom-os`) |
|---|---|---|---|---|
| Auth / session | ✅ | ✅ (biometric) | ✅ LoginScreen | ✅ `login` (80r, token 0600) |
| Agent list + chat | ✅ | ✅ AgentList/AgentChat | ✅ AgentList/Detail/QuickChat | ✅ `ask` posts to /api/chat/message (80t); `execute` stub repointed |
| Workflow list + trigger | ✅ | ✅ full suite (list/trigger/logs/progress) | ✅ 80u WorkflowsPanel (list/run) | ✅ 80w `workflows list/run` |
| **Approvals / HITL** | ✅ approvals.tsx + R81i panel | ✅ **80s** ApprovalsScreen | ❌ | ✅ 80t2 `approvals list/approve/reject` |
| Canvas viewer | ✅ canvas suite | ✅ CanvasViewer | ✅ CanvasList | ➖ |
| Integrations status | ✅ hub + health | ✅ v1 section | ✅ 80r panel | ✅ `integrations list/status` (80r) |
| Integrations connect | ✅ OAuth flows | ✅ 80p system-browser | ✅ 80r browser | ✅ `connect` prints URL (80r) |
| Integrations disconnect | ✅ | ✅ 80o | ✅ 80r | ✅ `disconnect` (80r) |
| Analytics / KPIs | ✅ dashboards | ✅ AnalyticsDashboard | ✅ 80v AnalyticsPanel | ✅ 80x `analytics [--window]` |
| Debugging / traces | ✅ dev-studio | ✅ debugging suite | ❌ | ➖ |
| Device capabilities | ➖ web-only APIs | ✅ camera/location/notifs | ➖ | ➖ |
| Server control (start/daemon) | ➖ | ➖ | ➖ | ✅ start/daemon/stop/status |
| Office automation (excel/word) | ✅ | ➖ | ➖ | ✅ office group |
| Cache preseed / config | ✅ admin | ➖ | ➖ | ✅ preseed/config |

## Gaps ranked by journey value

1. ~~Mobile approvals~~ — closed in 80s.
2. **CLI `execute`** is an admitted stub ("Command routing not yet
   implemented"). Wiring it to `POST /api/agent/start` +
   `/api/agent/execute` would complete the agent-chat journey from the
   terminal. (80t candidate)
3. ~~Desktop workflows~~ — closed in 80u (WorkflowsPanel: catalog + Run).

## Notes

- Desktop tests live at `desktop/tests/*.py` and run without TAURI_CI for
  source-contract checks; Rust IPC behavior requires TAURI_CI=true.
- Full FE jest tree requires `--maxWorkers=2` on this machine (MSW/global-fetch
  contention under default worker count).
- Backend full-tree pytest has cross-file ordering pollution (autodev suites
  fail only in whole-tree runs); per-suite batteries are the reliable signal.
