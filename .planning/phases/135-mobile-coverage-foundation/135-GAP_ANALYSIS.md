# Phase 135-02: Mobile Coverage Gap Analysis

**Generated:** 2026-03-05
**Baseline Date:** 2026-03-04
**Baseline Commit:** 2241b931f

## Executive Summary

| Metric | Value |
|--------|-------|
| **Overall Coverage** | **16.16%** statements (981/6069) |
| **Functions Coverage** | 14.68% (186/1267) |
| **Branches Coverage** | 10.77% (369/3427) |
| **Total Files** | 60 files |
| **Untested Files** | 45 files (75%) |
| **Coverage Gap to 80%** | 63.84 percentage points |

## Coverage by File Type

| Type | Files | Avg Coverage | Untested | Key Gap |
|------|-------|--------------|----------|---------|
| **Screens** | 23 | 7.4% | 20/23 | Chat, Auth, Canvas, Workflows |
| **Components** | 13 | 0.0% | 13/13 | All components untested |
| **Services** | 17 | 25.6% | 10/17 | Device bridge, sync services |
| **Contexts** | 2 | 52.6% | 0/2 | Good foundation |
| **Navigation** | 2 | 0.0% | 2/2 | App navigation untested |
| **Other** | 3 | 0.0% | 3/3 | Types, utilities |

## Detailed Analysis by File Type

### Screens (20/23 untested)

**Covered:**
- ✅ `screens/workflows/WorkflowsListScreen.tsx` - 93.0% (53/57 stmt)
- ✅ `screens/settings/SettingsScreen.tsx` - 43.6% (17/39 stmt)
- ✅ `screens/agent/AgentChatScreen.tsx` - 32.5% (40/123 stmt)

**Untested (sorted by statements):**
1. `screens/chat/ConversationListScreen.tsx` - 148 statements - **HIGH PRIORITY**
2. `screens/canvas/CanvasViewerScreen.tsx` - 144 statements - **HIGH PRIORITY**
3. `screens/agent/AgentListScreen.tsx` - 125 statements - **HIGH PRIORITY**
4. `screens/auth/RegisterScreen.tsx` - 110 statements
5. `screens/chat/ChatTabScreen.tsx` - 93 statements - **HIGH PRIORITY**
6. `screens/auth/ForgotPasswordScreen.tsx` - 89 statements
7. `screens/auth/LoginScreen.tsx` - 87 statements
8. `screens/auth/BiometricAuthScreen.tsx` - 79 statements
9. `screens/workflows/ExecutionProgressScreen.tsx` - 64 statements
10. `screens/workflows/WorkflowDetailScreen.tsx` - 57 statements
11. `screens/device/CameraScreen.tsx` - 53 statements
12. `screens/device/LocationScreen.tsx` - 52 statements
13. `screens/debugging/BreakpointsScreen.tsx` - 49 statements
14. `screens/debugging/TracesScreen.tsx` - 46 statements
15. `screens/analytics/AnalyticsDashboardScreen.tsx` - 44 statements
16. `screens/workflows/WorkflowLogsScreen.tsx` - 44 statements
17. `screens/device/NotificationPreferencesScreen.tsx` - 36 statements
18. `screens/workflows/WorkflowTriggerScreen.tsx` - 36 statements
19. `screens/debugging/DebugSessionScreen.tsx` - 35 statements
20. `screens/analytics/ExecutionChart.tsx` - 10 statements

**Auth Screens (4 files):**
- All auth screens untested (Login, Register, ForgotPassword, BiometricAuth)
- Critical for user onboarding flow
- 365 total statements across 4 files

**Chat Screens (2 files):**
- `ConversationListScreen.tsx` - 148 statements - Critical for chat history
- `ChatTabScreen.tsx` - 93 statements - Core chat functionality
- Combined: 241 statements

**Agent Screens (1 file):**
- `AgentListScreen.tsx` - 125 statements - Agent selection UI

**Canvas Screens (1 file):**
- `CanvasViewerScreen.tsx` - 144 statements - Canvas rendering

**Workflow Screens (4 untested / 1 tested):**
- 5 workflow screens total (201 untested statements)
- `WorkflowsListScreen.tsx` is well-tested (93%)
- Other workflow screens need tests

**Device Screens (3 files):**
- Camera, Location, NotificationPreferences
- 141 total statements

**Debugging Screens (3 files):**
- DebugSession, Breakpoints, Traces
- 130 total statements

**Analytics Screens (2 files):**
- AnalyticsDashboard, ExecutionChart
- 54 total statements

---

### Components (13/13 untested - 100% untested)

**Canvas Components (6 files):**
1. `components/canvas/CanvasGestures.tsx` - 170 statements - **HIGH PRIORITY**
2. `components/canvas/CanvasForm.tsx` - 156 statements - **HIGH PRIORITY**
3. `components/canvas/CanvasSheet.tsx` - 126 statements - **HIGH PRIORITY**
4. `components/canvas/CanvasTerminal.tsx` - 126 statements - **HIGH PRIORITY**
5. `components/canvas/CanvasChart.tsx` - 75 statements
6. **Total: 753 statements across canvas components**

**Chat Components (4 files):**
1. `components/chat/MessageInput.tsx` - 139 statements - **HIGH PRIORITY**
2. `components/chat/MessageList.tsx` - 118 statements - **HIGH PRIORITY**
3. `components/chat/StreamingText.tsx` - 78 statements - **HIGH PRIORITY**
4. `components/chat/TypingIndicator.tsx` - 51 statements
5. **Total: 386 statements across chat components**

**Offline Components (3 files):**
1. `components/offline/PendingActionsList.tsx` - 155 statements - **HIGH PRIORITY**
2. `components/offline/OfflineIndicator.tsx` - 105 statements
3. `components/offline/SyncProgressModal.tsx` - 80 statements
4. **Total: 340 statements across offline components**

**Other Components (1 file):**
- `components/MetricsCards.tsx` - 13 statements

**Component Total:** 1,392 untested statements (0% coverage)

---

### Services (10/17 untested)

**Well-Tested Services (>80%):**
- ✅ `services/agentService.ts` - 92.7% (51/55 stmt)
- ✅ `services/notificationService.ts` - 82.8% (90/132 stmt)

**Moderately-Tested Services (50-80%):**
- ✅ `services/biometricService.ts` - 68.2% (90/132 stmt)
- ✅ `services/storageService.ts` - 56.7% (114/201 stmt)
- ✅ `services/locationService.ts` - 55.8% (134/240 stmt)

**Low-Tested Services (<50%):**
- ⚠️ `services/offlineSyncService.ts` - 44.2% (177/400 stmt)
- ⚠️ `services/api.ts` - 35.1% (13/37 stmt)

**Untested Services (sorted by statements):**
1. `services/cameraService.ts` - 200 statements - **HIGH PRIORITY**
2. `services/agentDeviceBridge.ts` - 194 statements - **CRITICAL**
3. `services/workflowSyncService.ts` - 180 statements - **HIGH PRIORITY**
4. `services/canvasSyncService.ts` - 169 statements - **HIGH PRIORITY**
5. `services/deviceSocket.ts` - 149 statements - **CRITICAL**
6. `services/canvasService.ts` - 142 statements - **HIGH PRIORITY**
7. `services/agentSyncService.ts` - 138 statements
8. `services/chatService.ts` - 106 statements
9. `services/workflowService.ts` - 56 statements
10. `services/analyticsService.ts` - 30 statements

**Service Total:** 1,464 untested statements across 10 files

**Critical Gaps:**
- `agentDeviceBridge.ts` - Mobile-backend agent integration (194 stmt)
- `deviceSocket.ts` - WebSocket device communication (149 stmt)
- Both are critical for real-time agent execution

---

### Contexts (0/2 untested)

**Good Coverage:**
- ✅ `contexts/AuthContext.tsx` - 85.8% (151/176 stmt) - Excellent
- ✅ `contexts/DeviceContext.tsx` - 19.5% (30/154 stmt) - Needs enhancement

**Context Total:** 330 statements, 181 covered (52.6% avg)

**Note:** AuthContext is well-tested. DeviceContext could use enhancement tests.

---

### Navigation (2/2 untested - 100% untested)

**Untested:**
1. `navigation/AppNavigator.tsx` - 23 statements
2. `navigation/AuthNavigator.tsx` - 17 statements

**Navigation Total:** 40 untested statements

**Note:** Navigation structure is simple but should be tested for route configuration.

---

## Priority Ranking: Top 10 Files

**Priority scoring:** Statements × Business Impact × Complexity

| Rank | File | Statements | Business Impact | Complexity | Score | Priority |
|------|------|------------|-----------------|------------|-------|----------|
| 1 | `services/agentDeviceBridge.ts` | 194 | CRITICAL | HIGH | 5820 | **URGENT** |
| 2 | `components/canvas/CanvasGestures.tsx` | 170 | HIGH | HIGH | 3400 | **HIGH** |
| 3 | `services/cameraService.ts` | 200 | MEDIUM | HIGH | 2000 | **HIGH** |
| 4 | `services/workflowSyncService.ts` | 180 | HIGH | MEDIUM | 1800 | **HIGH** |
| 5 | `services/deviceSocket.ts` | 149 | CRITICAL | MEDIUM | 1788 | **HIGH** |
| 6 | `components/canvas/CanvasForm.tsx` | 156 | HIGH | MEDIUM | 1560 | **HIGH** |
| 7 | `components/chat/MessageInput.tsx` | 139 | HIGH | MEDIUM | 1390 | **MEDIUM** |
| 8 | `services/canvasSyncService.ts` | 169 | HIGH | LOW | 845 | **MEDIUM** |
| 9 | `screens/chat/ConversationListScreen.tsx` | 148 | HIGH | LOW | 740 | **MEDIUM** |
| 10 | `services/canvasService.ts` | 142 | HIGH | LOW | 710 | **MEDIUM** |

**Legend:**
- **Business Impact:** CRITICAL (core functionality), HIGH (important UX), MEDIUM (nice-to-have)
- **Complexity:** HIGH (async, state, WebSocket), MEDIUM (UI logic), LOW (simple rendering)
- **Priority:** URGENT (Plan 03), HIGH (Plan 04), MEDIUM (Plan 05), LOW (Plan 06)

---

## Gap Analysis Summary

### Coverage Distribution

```
████████████████████████████████████████████████████████████████ 80% TARGET
████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 16.16% CURRENT
```

**Gap: 63.84 percentage points to 80% threshold**

### Untested Files Distribution

| Category | Total Files | Untested | % Untested | Total Statements |
|----------|-------------|----------|------------|------------------|
| Screens | 23 | 20 | 87% | 1,620 |
| Components | 13 | 13 | 100% | 1,392 |
| Services | 17 | 10 | 59% | 2,563 |
| Contexts | 2 | 0 | 0% | 330 |
| Navigation | 2 | 2 | 100% | 40 |
| **TOTAL** | **60** | **45** | **75%** | **6,069** |

### Quick Wins (Low-Hanging Fruit)

**Easy to test (simple UI, minimal state):**
- `navigation/AppNavigator.tsx` - 23 statements - Route config only
- `navigation/AuthNavigator.tsx` - 17 statements - Route config only
- `components/MetricsCards.tsx` - 13 statements - Simple display
- `screens/analytics/ExecutionChart.tsx` - 10 statements - Simple chart

**Expected gain:** ~63 statements with minimal effort

### High-Impact Targets

**Critical business value:**
- `services/agentDeviceBridge.ts` - 194 statements - Agent execution
- `services/deviceSocket.ts` - 149 statements - Real-time communication
- `components/canvas/CanvasGestures.tsx` - 170 statements - Canvas interaction
- `components/chat/MessageInput.tsx` - 139 statements - Chat UX
- `screens/chat/ChatTabScreen.tsx` - 93 statements - Core chat

**Expected gain:** ~745 statements with high business impact

---

## Testing Strategy Recommendations

### Wave 1: Critical Path (Plans 03-04)
**Focus:** Services that power core functionality
- `agentDeviceBridge.ts` - Agent execution
- `deviceSocket.ts` - WebSocket communication
- `workflowSyncService.ts` - Workflow sync
- `canvasSyncService.ts` - Canvas sync

**Expected Coverage Gain:** +15-20 percentage points

### Wave 2: User Experience (Plans 05-06)
**Focus:** Screens and components users interact with
- Chat screens and components (ConversationList, ChatTab, MessageInput)
- Canvas screens and components (CanvasViewer, CanvasGestures)
- Auth screens (Login, Register)

**Expected Coverage Gain:** +20-25 percentage points

### Wave 3: Edge Cases (Plans 07+)
**Focus:** Device features, debugging, analytics
- Device screens (Camera, Location)
- Debugging screens
- Analytics screens
- Offline components

**Expected Coverage Gain:** +15-20 percentage points

---

## Next Steps

1. ✅ **Plan 01:** Fix failing tests (61 tests with mock/async issues) - COMPLETE
2. ✅ **Plan 02:** Generate coverage baseline - COMPLETE
3. ⏭️ **Plan 03:** Test critical services (agentDeviceBridge, deviceSocket)
4. ⏭️ **Plan 04:** Test canvas and chat components
5. ⏭️ **Plan 05:** Test screens (chat, canvas, auth)
6. ⏭️ **Plan 06:** Test remaining services and navigation

**Target:** Reach 80% coverage threshold by Plan 06
