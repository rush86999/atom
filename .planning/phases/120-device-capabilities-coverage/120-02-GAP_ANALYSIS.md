# Phase 120: Device Capabilities Coverage - Gap Analysis

**Plan:** 120-02
**Created:** 2026-03-02
**Status:** COMPLETE

---

## Executive Summary

Device capabilities coverage baseline analysis reveals strong foundation with both files exceeding 60% target:

- **api/device_capabilities.py**: 79.84% (198/248 lines) - **EXCEEDS target by 19.84 pp**
- **tools/device_tool.py**: 70.13% (216/308 lines) - **EXCEEDS target by 10.13 pp**

**Combined Coverage: 74.15%** (414/558 lines)

### Recommendation

Both files already exceed the 60% coverage target. However, significant gaps remain in critical security and governance paths. Plan 03 should focus on:

1. **Zero-coverage functions** (2 functions, 32 lines)
2. **Partial coverage functions** below 60% (3 functions)
3. **Governance and error paths** (security-critical)

### Target

- **Current Combined**: 74.15%
- **Target**: 85%+ (stretch goal for security-critical code)
- **Tests Needed**: 20-25 tests

---

## Coverage Baseline

### api/device_capabilities.py

| Metric | Value |
|--------|-------|
| Coverage | 79.84% |
| Lines Covered | 198/248 |
| Missing Lines | 50 |
| Functions Total | 11 |
| Functions ≥60% | 9/11 (82%) |
| Zero Coverage Functions | 1 |
| Below Target Functions | 3 |

### tools/device_tool.py

| Metric | Value |
|--------|-------|
| Coverage | 70.13% |
| Lines Covered | 216/308 |
| Missing Lines | 92 |
| Functions Total | 14 |
| Functions ≥60% | 11/14 (79%) |
| Zero Coverage Functions | 2 |
| Below Target Functions | 4 |

---

## Zero Coverage Functions (HIGH PRIORITY)

### Gap 1: list_devices_endpoint - 0% (6 lines)
**File:** api/device_capabilities.py (Lines 600-606)

**Impact:** HIGH - Device listing is core functionality

**Missing Lines:**
```python
600     try:
601         result = await list_devices(db, current_user.id, status)
602         return result
603
604     except Exception as e:
605         logger.error(f"List devices error: {e}")
606         raise router.internal_error(f"List devices error: {str(e)}")
```

**Tests Needed:**
1. `test_list_devices_endpoint_success` - List devices with no filter
2. `test_list_devices_endpoint_with_status_filter` - List devices filtered by status
3. `test_list_devices_endpoint_exception_handling` - Verify error handling on exception

**Estimated Coverage Gain:** +5% (global), +6 lines covered

**Priority:** HIGH - Zero coverage, core endpoint

---

### Gap 2: cleanup_expired_sessions - 0% (11 lines)
**File:** tools/device_tool.py (Lines 129-145)

**Impact:** MEDIUM - Session cleanup is background maintenance

**Missing Lines:**
```python
129     def cleanup_expired_sessions(self):
130         """Remove expired sessions based on timeout."""
131         now = datetime.now()
132         expired = []
133
134         for session_id, session in self.sessions.items():
135             last_used = session.get("last_used", session["created_at"])
136             age_minutes = (now - last_used).total_seconds() / 60
137
138             if age_minutes > self.session_timeout_minutes:
139                 expired.append(session_id)
140
141         for session_id in expired:
142             self.close_session(session_id)
143             logger.info(f"Expired device session {session_id} cleaned up")
144
145         return len(expired)
```

**Tests Needed:**
1. `test_cleanup_expired_sessions_no_expired` - No sessions to clean
2. `test_cleanup_expired_sessions_some_expired` - Multiple sessions expired
3. `test_cleanup_expired_sessions_all_expired` - All sessions expired
4. `test_cleanup_expired_sessions_returns_count` - Verify return count

**Estimated Coverage Gain:** +3.5% (global), +11 lines covered

**Priority:** MEDIUM - Background task, but prevents memory leaks

---

### Gap 3: execute_device_command - 0% (21 lines)
**File:** tools/device_tool.py (Lines 1234-1291)

**Impact:** HIGH - Generic wrapper used by proposal service

**Missing Lines:**
```python
1234     try:
1235         if command_type == "camera":
1236             # Camera capture
1237             timeout = parameters.get("timeout", 10)
1238             return await device_camera_snap(...)
1239
1245         elif command_type == "location":
1246             # Get location
1247             high_accuracy = parameters.get("high_accuracy", True)
1248             return await device_get_location(...)
1249
1255         elif command_type == "notification":
1256             # Send notification
1257             title = parameters.get("title", "Notification")
1258             body = parameters.get("body", "")
1259             return await device_send_notification(...)
1260
1267         elif command_type == "command":
1268             # Execute shell command
1269             command = parameters.get("command")
1270             working_dir = parameters.get("working_dir")
1271             timeout = parameters.get("timeout", 30)
1272             return await device_execute_command(...)
1273
1282         else:
1283             logger.warning(f"Unknown device command type: {command_type}")
1284             return {
1285                 "success": False,
1286                 "error": f"Unknown command type: {command_type}..."
1287             }
1288
1289     except Exception as e:
1290         logger.error(f"Failed to execute device command: {e}")
1291         return {"success": False, "error": str(e)}
```

**Tests Needed:**
1. `test_execute_device_command_camera` - Route to camera_snap
2. `test_execute_device_command_location` - Route to get_location
3. `test_execute_device_command_notification` - Route to send_notification
4. `test_execute_device_command_shell` - Route to execute_command
5. `test_execute_device_command_unknown_type` - Unknown command type handling
6. `test_execute_device_command_exception_handling` - Exception routing

**Estimated Coverage Gain:** +6.8% (global), +21 lines covered

**Priority:** HIGH - Zero coverage, used by proposal service

---

## Partial Coverage Functions (< 60%)

### Gap 4: _check_device_governance - 22.22% (2/9 lines)
**File:** tools/device_tool.py (Lines 256-276)

**Impact:** HIGH - Security-critical governance enforcement

**Missing Lines:**
```python
256     if not FeatureFlags.should_enforce_governance('device'):
257         return {
258             "allowed": True,
259             "reason": "Device governance disabled or emergency bypass active",
260             "governance_check_passed": True
261         }

263     try:
264         governance = ServiceFactory.get_governance_service(db)
265         check = governance.can_perform_action(agent_id, action_type)
266
267         return {
268             "allowed": check["allowed"],
269             "reason": check["reason"],
270             "governance_check_passed": check["allowed"]
271         }
273
274     except Exception as e:
275         logger.error(f"Governance check failed for {action_type}: {e}")
276         return {...}  # Fail open
```

**Current Coverage:** Only lines 257, 276 (exception path) covered

**Tests Needed:**
1. `test_check_governance_feature_flag_disabled` - FeatureFlags.should_enforce_governance returns False
2. `test_check_governance_allowed` - Agent has permission
3. `test_check_governance_denied` - Agent lacks permission
4. `test_check_governance_exception_fail_open` - Governance service fails, verify fail-open

**Estimated Coverage Gain:** +2.3% (global), +7 lines covered

**Priority:** HIGH - Security-critical, low coverage (22%)

---

### Gap 5: device_get_location - 50.00% (13/26 lines)
**File:** tools/device_tool.py (Lines 700-813)

**Impact:** MEDIUM - Location services

**Missing Lines:**
```python
727     if not WEBSOCKET_AVAILABLE:
728         raise ValueError("Device WebSocket module not available...")

730     if not is_device_online(device_node_id):
731         raise ValueError("Device {device_node_id} is not currently connected...")

740     location_data = response.get("data", {})
750     "altitude": location_data.get("altitude"),
759     "timestamp": location_data.get("timestamp", datetime.now().isoformat())

762     # Create audit entry for failure
773     error_msg = f"Get location failed: {str(e)}"
```

**Tests Needed:**
1. `test_device_get_location_websocket_unavailable` - WEBSOCKET_AVAILABLE = False
2. `test_device_get_location_device_offline` - is_device_online returns False
3. `test_device_get_location_success_full_data` - Success with altitude, timestamp
4. `test_device_get_location_governance_blocked` - Governance blocks action

**Estimated Coverage Gain:** +4.2% (global), +13 lines covered

**Priority:** MEDIUM - Partial coverage (50%)

---

### Gap 6: device_send_notification - 52.00% (13/25 lines)
**File:** tools/device_tool.py (Lines 816-946)

**Impact:** MEDIUM - Notification sending

**Missing Lines:**
```python
849     if not WEBSOCKET_AVAILABLE:
850         raise ValueError("Device WebSocket module not available...")

852     if not is_device_online(device_node_id):
853         raise ValueError("Device {device_node_id} is not currently connected...")

862     response = await send_device_command(...)

884     except Exception as e:
885         logger.error(f"Failed to send notification: {e}")
896     # Create audit entry for failure
916     # Create audit entry for failure
917     logger.error(error_msg)
```

**Tests Needed:**
1. `test_device_send_notification_websocket_unavailable` - WEBSOCKET_AVAILABLE = False
2. `test_device_send_notification_device_offline` - is_device_online returns False
3. `test_device_send_notification_success_with_icon_sound` - Success with optional params
4. `test_device_send_notification_governance_blocked` - Governance blocks action

**Estimated Coverage Gain:** +3.9% (global), +12 lines covered

**Priority:** MEDIUM - Partial coverage (52%)

---

## Additional Partial Coverage Functions (60-80%)

### Gap 7: execute_command - 42.11% (8/19 lines)
**File:** api/device_capabilities.py (Lines 485-536)

**Impact:** HIGH - Command execution is AUTONOMOUS-only

**Missing Lines:**
```python
492     if not agent_id:
493         raise router.permission_denied_error(...)

503     if not agent or agent.status != "autonomous":
504         current_status = agent.status if agent else 'None'
505         raise router.governance_denied_error(...)

514     result = await device_execute_command(...)

525     if not result.get("success"):
526         if result.get("governance_blocked"):
527             raise router.permission_denied_error(...)
528         raise router.error_response(...)

530     return router.success_response(data=result, ...)
535     raise router.internal_error(...)
```

**Tests Needed:**
1. `test_execute_command_no_agent_id` - Missing agent_id
2. `test_execute_command_non_autonomous_agent` - Agent not AUTONOMOUS status
3. `test_execute_command_success` - Successful command execution
4. `test_execute_command_governance_blocked` - Governance blocks action

**Estimated Coverage Gain:** +3.5% (global), +11 lines covered

**Priority:** HIGH - AUTONOMOUS-only enforcement, partial coverage (42%)

---

### Gap 8: get_device_info_endpoint - 46.15% (6/13 lines)
**File:** api/device_capabilities.py (Lines 539-580)

**Impact:** MEDIUM - Device info retrieval

**Missing Lines:**
```python
560     if not result:
561         raise router.not_found_error("Device", device_node_id)

568     if device.user_id != current_user.id:
569         raise router.permission_denied_error(...)

576     except Exception as e:
577         logger.error(f"Get device info error: {e}")
578         if "not found" in str(e).lower():
579             raise router.not_found_error("Device", device_node_id)
580         raise router.internal_error(...)
```

**Tests Needed:**
1. `test_get_device_info_endpoint_device_not_found` - Device doesn't exist
2. `test_get_device_info_endpoint_wrong_user` - User doesn't own device
3. `test_get_device_info_endpoint_success` - Successful retrieval

**Estimated Coverage Gain:** +2.8% (global), +7 lines covered

**Priority:** MEDIUM - Ownership check important

---

### Gap 9: get_device_audit - 46.15% (6/13 lines)
**File:** api/device_capabilities.py (Lines 609-671)

**Impact:** MEDIUM - Audit trail retrieval

**Missing Lines:**
```python
635     if not device:
636         raise router.not_found_error("Device", device_node_id)

638     if device.user_id != current_user.id:
639         raise router.permission_denied_error(...)

667     return [
668         {...}
669         for audit in audits
670     ]

671     except Exception as e:
```

**Tests Needed:**
1. `test_get_device_audit_device_not_found` - Device doesn't exist
2. `test_get_device_audit_wrong_user` - User doesn't own device
3. `test_get_device_audit_success` - Successful audit retrieval

**Estimated Coverage Gain:** +2.8% (global), +7 lines covered

**Priority:** LOW - Audit retrieval is less critical

---

### Gap 10: get_active_sessions - 50.00% (3/6 lines)
**File:** api/device_capabilities.py (Lines 674-710)

**Impact:** LOW - Active session listing

**Missing Lines:**
```python
708     except Exception as e:
709         logger.error(f"Get active sessions error: {e}")
710         raise router.internal_error(...)
```

**Tests Needed:**
1. `test_get_active_sessions_exception_handling` - Exception handling

**Estimated Coverage Gain:** +1% (global), +3 lines covered

**Priority:** LOW - Only exception handling missing

---

## Edge Cases and Error Paths

### Gap 11: Governance Enforcement Across All Endpoints
**Impact:** HIGH - Security-critical

All endpoints (camera_snap, screen_record_start, get_location, send_notification) have 76.92% coverage with missing governance error handling:

**Missing Pattern (repeated across 5 endpoints):**
```python
# Line 253, 311, 396, 447
if result.get("governance_blocked"):
    raise router.permission_denied_error(...)
```

**Tests Needed:**
1. `test_camera_snap_governance_blocked`
2. `test_screen_record_start_governance_blocked`
3. `test_get_location_governance_blocked`
4. `test_send_notification_governance_blocked`

**Estimated Coverage Gain:** +1.3% (global), +4 lines covered

**Priority:** HIGH - Security-critical error path

---

### Gap 12: WebSocket Unavailability Paths
**Impact:** MEDIUM - Device connectivity

Functions need WebSocket availability checks:
- device_camera_snap (92%, missing line 331)
- device_get_location (50%, missing line 727)
- device_send_notification (52%, missing line 849)
- device_execute_command (90%, missing line 1030)

**Tests Needed:**
1. `test_device_camera_snap_websocket_unavailable`
2. `test_device_get_location_websocket_unavailable`
3. `test_device_send_notification_websocket_unavailable`
4. `test_device_execute_command_websocket_unavailable`

**Estimated Coverage Gain:** +1.3% (global), +4 lines covered

**Priority:** MEDIUM - Graceful degradation path

---

### Gap 13: Device Offline Paths
**Impact:** MEDIUM - Device connectivity

Functions need device online checks:
- device_get_location (50%, missing line 730)
- device_send_notification (52%, missing line 852)
- device_execute_command (90%, missing line 1034)

**Tests Needed:**
1. `test_device_get_location_device_offline`
2. `test_device_send_notification_device_offline`
3. `test_device_execute_command_device_offline`

**Estimated Coverage Gain:** +1% (global), +3 lines covered

**Priority:** MEDIUM - Connection error handling

---

## Test Allocation for 85% Target

### Current State
- **api/device_capabilities.py**: 79.84% (50 missing lines)
- **tools/device_tool.py**: 70.13% (92 missing lines)
- **Combined**: 74.15% (142 missing lines)

### Target: 85% Combined Coverage

**Tests by Priority:**

#### HIGH PRIORITY (12 tests, +17.9% estimated)
1. list_devices_endpoint (3 tests) - +5%
2. execute_device_command (6 tests) - +6.8%
3. execute_command enforcement (4 tests) - +3.5%
4. _check_device_governance (4 tests) - +2.3%
5. Governance blocked paths (4 tests) - +1.3%

#### MEDIUM PRIORITY (10 tests, +13.6% estimated)
1. cleanup_expired_sessions (4 tests) - +3.5%
2. device_get_location (4 tests) - +4.2%
3. device_send_notification (4 tests) - +3.9%
4. get_device_info_endpoint (3 tests) - +2.8%

#### LOW PRIORITY (4 tests, +4.8% estimated)
1. get_device_audit (3 tests) - +2.8%
2. get_active_sessions (1 test) - +1%
3. WebSocket unavailable (4 tests) - +1.3%
4. Device offline (3 tests) - +1%

### Estimated Test Count

**Total Tests Needed: 24-27 tests**

**File Breakdown:**
- **api/device_capabilities.py**: 10-12 tests
- **tools/device_tool.py**: 14-15 tests

**Expected Final Coverage:**
- api/device_capabilities.py: 79.84% → 90%+ (+10.16 pp)
- tools/device_tool.py: 70.13% → 85%+ (+14.87 pp)
- **Combined**: 74.15% → 86%+ (+11.85 pp)

---

## Implementation Notes

### Test Infrastructure Patterns

1. **WebSocket Mocking**: All device functions require WebSocket mocking
   ```python
   mock.patch("tools.device_tool.is_device_online", return_value=True)
   mock.patch("tools.device_tool.send_device_command", return_value={...})
   ```

2. **Governance Service Mocking**: Governance checks require ServiceFactory patch
   ```python
   mock.patch("core.service_factory.ServiceFactory.get_governance_service")
   ```

3. **Feature Flags Mocking**: Feature flag checks
   ```python
   mock.patch("core.feature_flags.FeatureFlags.should_enforce_governance")
   ```

4. **Database Models**: DeviceNode, DeviceSession creation for ownership tests

### Test Files to Modify

- `backend/tests/test_device_tool.py` - Add 14-15 tests
- `backend/tests/api/test_device_capabilities.py` - Add 10-12 tests

---

## Success Criteria for Plan 03

After implementing the 24-27 prioritized tests:

- [ ] All zero-coverage functions covered (list_devices_endpoint, cleanup_expired_sessions, execute_device_command)
- [ ] Security-critical governance paths covered (_check_device_governance, execute_command enforcement)
- [ ] Error handling paths tested (WebSocket unavailable, device offline, governance blocked)
- [ ] Combined coverage reaches 85%+ (stretch goal)
- [ ] All new tests passing (100% pass rate)

---

## Summary

**Current Coverage:**
- api/device_capabilities.py: 79.84%
- tools/device_tool.py: 70.13%
- Combined: 74.15%

**Target Coverage:**
- Combined: 85%+ (stretch goal for security-critical code)

**Tests Required:**
- HIGH: 12 tests (governance, zero-coverage functions)
- MEDIUM: 10 tests (partial coverage, error paths)
- LOW: 4-5 tests (optional edge cases)
- **Total: 24-27 tests**

**Priority Order:**
1. Zero-coverage functions (HIGH ROI)
2. Security-critical governance paths (HIGH impact)
3. Partial coverage functions below 60%
4. Error handling and edge cases

**Next Step:** Proceed to Plan 03 - Add prioritized tests
