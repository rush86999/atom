# Future Work and Incomplete Features

This document tracks incomplete features, work-in-progress items, and intentional stubs in the Atom codebase.

---

## Recently Completed (February 5, 2026)

The following incomplete implementations have been fixed:
- ✅ Backend workflow engine Slack and Asana actions
- ✅ PDF document listing and tag update endpoints
- ✅ PDF OCR image processing
- ✅ Mobile device permissions
- ✅ Mobile authentication flow improvements
- ✅ Mobile navigation with SettingsScreen

**See**: `backend/docs/INCOMPLETE_IMPLEMENTATIONS.md` for detailed information about these fixes.

---

## SendGrid Integration

**File**: `backend/integrations/sendgrid_routes.py`

**Status**: Stub implementation - OAuth flow not implemented

**Current Behavior**: Throws `NotImplementedError` when attempting to use SendGrid OAuth endpoints

**Blocking**: Requires SendGrid OAuth flow implementation

**Est. Effort**: 2-3 days

**Priority**: P3 (Low)

**Notes**: Current `NotImplementedError` is intentional security practice - prevents mock API keys from reaching production. The basic webhook endpoints are implemented, but OAuth authentication needs full implementation.

---

## Discord Enhanced API (Flask Version)

**File**: `backend/integrations/discord_enhanced_api_routes.py`

**Status**: DEPRECATED - Superseded by FastAPI version

**Migration**: Use `backend/integrations/discord_routes.py` instead

**Removal**: Planned for v2.0

**Reason**: Modernizing all API routes to FastAPI for consistency with the rest of the codebase

**Unique Features**: None - all functionality has been ported to FastAPI version

**Est. Effort**: 0 hours (already migrated)

---

## Enterprise API

**File**: `backend/integrations/atom_enterprise_api_routes.py`

**Status**: Premium feature - Requires enterprise license key

**Current Behavior**: Throws `NotImplementedError` when `ENTERPRISE_KEY` environment variable is not set

**Blocking**: Requires enterprise licensing system and valid license key

**Priority**: P2 (Medium)

**Notes**: This is intentionally gated enterprise functionality. The endpoints are defined but will only work with a valid enterprise license key.

**Est. Effort**: 1-2 weeks (requires licensing infrastructure)

---

## AI Enhanced API

**File**: `backend/integrations/ai_enhanced_api_routes.py`

**Status**: Optional feature - Requires paid API keys

**Current Behavior**: Throws `NotImplementedError` when `AI_ENHANCED_API_KEY` environment variable is not set

**Blocking**: Requires third-party AI service integration

**Priority**: P3 (Low)

**Notes**: This is an add-on functionality. The core system does not depend on it.

**Est. Effort**: 3-5 days (requires API integration)

---

## Database Performance Indexes

**File**: `backend/core/models.py`

**Status**: Planned optimization

**Description**: Add database indexes to frequently queried fields for improved performance

**Fields to Index**:
- `User.email` - User lookups
- `AgentRegistry.agent_id` - Agent resolution
- `AgentExecution.agent_id` - Execution history
- `Canvas.workspace_id` - Canvas filtering
- `created_at` timestamps - Commonly used for sorting

**Priority**: P3 (Low)

**Risk**: Medium - Indexes slow down writes, requires benchmarking

**Est. Effort**: 2 hours (implementation + migration)

**Notes**: Requires performance testing before deploying to production

---

## Mobile Support (React Native)

**Status**: Architecture complete, implementation pending

**Documentation**: `docs/REACT_NATIVE_ARCHITECTURE.md`

**Priority**: P2 (Medium)

**Est. Effort**: 4-6 weeks

**Platform Support**: iOS 13+, Android 8+

**Notes**: Architecture and design are complete. Implementation requires:
- React Native project setup
- API client integration
- Component development
- Testing framework setup

---

## Advanced Canvas Features

**Custom Components Security Enhancements**

**File**: `backend/tools/canvas_tool.py`

**Status**: Basic security implemented, advanced sanitization pending

**Description**: Enhanced HTML/CSS/JS sanitization with more sophisticated CSP policies

**Priority**: P3 (Low)

**Est. Effort**: 1 week

**Notes**: Current implementation uses basic sanitization. Advanced features needed:
- DOMPurify integration
- More granular CSP policies
- Sandbox iframe improvements

---

## Real-Time Collaboration Features

**Multi-Agent Canvas Coordination**

**Status**: Basic implementation complete

**File**: `backend/tools/canvas_tool.py`

**Enhancements Needed**:
- Conflict resolution improvements
- Real-time presence indicators
- Optimistic UI updates
- Operational transformation (OT) or CRDT support

**Priority**: P3 (Low)

**Est. Effort**: 2-3 weeks

---

## Testing Coverage Improvements

**Areas Needing More Tests**:

1. **Browser Automation Edge Cases**
   - Network failure handling
   - Timeout scenarios
   - Cross-browser compatibility

2. **Device Permissions**
   - Permission denial flows
   - Platform-specific behaviors
   - Error recovery

3. **Performance Testing**
   - Load testing for streaming endpoints
   - Cache performance under high concurrency
   - Database query optimization validation

**Priority**: P2 (Medium)

**Est. Effort**: Ongoing

---

## Documentation Improvements

**Items Needed**:
- [ ] API reference documentation (auto-generated from FastAPI schemas)
- [ ] Deployment guide for production environments
- [ ] Contribution guidelines for external developers
- [ ] Security best practices guide
- [ ] Performance tuning guide

**Priority**: P2 (Medium)

**Est. Effort**: 1-2 weeks

---

## Deprecation Timeline

### Version 2.0 (Planned)
- Remove Flask-based `discord_enhanced_api_routes.py`
- Remove all archived fix scripts from repository
- Require all API routes to use FastAPI

### Version 2.1 (Planned)
- Deprecate legacy WebSocket endpoints in favor of unified streaming
- Consolidate duplicate utility functions

---

## Notes

- **Intentional Stubs**: Many `NotImplementedError` exceptions are intentional security measures to prevent incomplete features from being used in production
- **Gradual Rollout**: Major features will be rolled out gradually with feature flags
- **Backward Compatibility**: We maintain backward compatibility for at least one major version
- **Performance First**: All performance optimizations are benchmarked before deployment

---

*Last Updated: February 3, 2026*
