# JIT Verification Admin Dashboard - Implementation Plan

**Phase**: JIT Verification Admin Dashboard
**Goal**: Build comprehensive admin UI for managing JIT verification cache, worker, and business facts compliance
**Backend Status**: ✅ Complete (100% - all API endpoints implemented and tested)
**Frontend Status**: ❌ Missing (0% - no UI components exist)

---

## Overview

This plan implements the complete admin dashboard for the JIT Verification System that provides:
- Real-time monitoring of verification worker status
- Cache performance metrics and management
- Business facts management with citation verification
- Worker control (start/stop/verify-now)
- Compliance audit capabilities

**Architecture**:
- Backend: FastAPI with `/api/admin/governance/jit/*` endpoints (✅ Complete)
- Frontend: Next.js pages in `/app/admin/` with React components (❌ To Implement)
- Real-time: Polling-based updates (WebSocket optional future enhancement)

---

## Implementation Waves

### Wave 1: Foundation & API Integration (Plan 01)
**Goal**: Set up project structure, API client, and navigation integration

**Tasks**:
1. Create admin API client functions (`lib/api-admin.ts`)
2. Create TypeScript types for API responses (`types/jit-verification.ts`)
3. Add navigation menu items for JIT Verification and Business Facts
4. Create base layout wrapper for admin pages
5. Set up authentication pattern for admin routes

**Files Created**:
- `frontend-nextjs/lib/api-admin.ts` - Admin API functions
- `frontend-nextjs/types/jit-verification.ts` - TypeScript types
- `frontend-nextjs/app/admin/jit-verification/layout.tsx` - Admin layout
- `frontend-nextjs/components/layout/Sidebar.tsx` - Updated with governance links

**Dependencies**: None
**Autonomous**: Yes - can be developed independently

**Verification Criteria**:
- [ ] API client can successfully call backend endpoints
- [ ] TypeScript types match backend response models exactly
- [ ] Navigation links work and route to correct pages
- [ ] Authentication token is properly passed to API calls

---

### Wave 2: Main Dashboard & Worker Monitor (Plan 02)
**Goal**: Build primary dashboard with worker status and system overview

**Tasks**:
1. Create main JIT Verification Dashboard page
2. Build Worker Status Monitor component
3. Implement system status cards (worker, cache, citations, stale facts)
4. Add quick action buttons (start/stop worker, clear cache, warm cache)
5. Create tabbed interface for different views
6. Implement real-time polling for status updates

**Files Created**:
- `frontend-nextjs/app/admin/jit-verification/page.tsx` - Main dashboard
- `frontend-nextjs/components/admin/jit-verification/JITVerificationDashboard.tsx`
- `frontend-nextjs/components/admin/jit-verification/WorkerStatusMonitor.tsx`
- `frontend-nextjs/components/admin/jit-verification/SystemStatusCards.tsx`
- `frontend-nextjs/components/admin/jit-verification/QuickActions.tsx`

**Dependencies**: Plan 01 (API integration)
**Autonomous**: Yes - depends only on Plan 01

**Verification Criteria**:
- [ ] Dashboard displays worker running status correctly
- [ ] System status cards show accurate metrics (worker, cache, citations, stale facts)
- [ ] Quick action buttons work (start/stop worker, clear cache, warm cache)
- [ ] Tabs switch between different views (Overview, Citations, Cache, Worker)
- [ ] Status updates every 10 seconds via polling
- [ ] Error handling for failed API calls
- [ ] Loading states during data fetching

**must_haves** (from phase goal):
- Admins can view real-time worker status
- Admins can control worker (start/stop)
- System health is visible at a glance

---

### Wave 3: Cache Metrics & Performance (Plan 03)
**Goal**: Build cache performance monitoring and management UI

**Tasks**:
1. Create Cache Metrics Panel component
2. Display hit rates (L1, L2, overall) with progress bars
3. Show cache size and eviction statistics
4. Display latency metrics (L1, L2, R2/S3)
5. Implement cache warming dialog
6. Add cache clearing confirmation
7. Create performance history chart (24h trends)

**Files Created**:
- `frontend-nextjs/components/admin/jit-verification/CacheMetricsPanel.tsx`
- `frontend-nextjs/components/admin/jit-verification/HitRateDisplay.tsx`
- `frontend-nextjs/components/admin/jit-verification/LatencyDisplay.tsx`
- `frontend-nextjs/components/admin/jit-verification/PerformanceChart.tsx`
- `frontend-nextjs/components/admin/jit-verification/CacheActions.tsx`

**Dependencies**: Plan 01 (API integration), Plan 02 (dashboard structure)
**Autonomous**: No - builds on dashboard from Plan 02

**Verification Criteria**:
- [ ] Cache hit rates display correctly with visual progress bars
- [ ] Cache size shows current/max with percentage
- [ ] Latency metrics display for L1, L2, R2/S3
- [ ] Cache warming dialog works with custom limit input
- [ ] Cache clearing has confirmation dialog
- [ ] Performance chart shows 24h trend data
- [ ] All metrics update every 10 seconds
- [ ] Error handling for missing or malformed data

**must_haves** (from phase goal):
- Admins can monitor cache performance (hit rates, latency)
- Admins can manage cache (clear, warm)
- Performance metrics are visible

---

### Wave 4: Citation Verification Panel (Plan 04)
**Goal**: Build citation verification interface for manual checks

**Tasks**:
1. Create Citation Verification Panel component
2. Implement text area for entering citations (one per line)
3. Add force refresh toggle option
4. Display verification results with status icons
5. Show citation metadata (size, last verified, status)
6. Add bulk verification functionality
7. Implement result filtering (all, verified, failed)

**Files Created**:
- `frontend-nextjs/components/admin/jit-verification/CitationVerificationPanel.tsx`
- `frontend-nextjs/components/admin/jit-verification/CitationInput.tsx`
- `frontend-nextjs/components/admin/jit-verification/VerificationResults.tsx`
- `frontend-nextjs/components/admin/jit-verification/CitationStatusBadge.tsx`

**Dependencies**: Plan 01 (API integration)
**Autonomous**: Yes - independent component

**Verification Criteria**:
- [ ] Citations can be entered (one per line or comma-separated)
- [ ] Force refresh toggle works correctly
- [ ] Verification results display with status icons (✅ exists, ❌ missing)
- [ ] Citation metadata shows (size, last verified, checked at)
- [ ] Bulk verification works for multiple citations
- [ ] Results can be filtered by status
- [ ] Loading state during verification
- [ ] Error handling for failed verifications
- [ ] Copy results to clipboard functionality

**must_haves** (from phase goal):
- Admins can manually verify citations
- Verification results show citation existence status
- Bulk verification supported

---

### Wave 5: Business Facts Management (Plan 05)
**Goal**: Build business facts table and management interface

**Tasks**:
1. Create Business Facts management page
2. Build facts table with filtering (status, domain, search)
3. Implement fact creation form
4. Add fact editing dialog
5. Create fact deletion with confirmation
6. Show citation viewer for each fact
7. Add verification status badges
8. Implement pagination for large datasets

**Files Created**:
- `frontend-nextjs/app/admin/business-facts/page.tsx` - Business facts page
- `frontend-nextjs/components/admin/business-facts/BusinessFactsTable.tsx`
- `frontend-nextjs/components/admin/business-facts/FactFilters.tsx`
- `frontend-nextjs/components/admin/business-facts/BusinessFactForm.tsx`
- `frontend-nextjs/components/admin/business-facts/CitationViewer.tsx`
- `frontend-nextjs/components/admin/business-facts/VerificationStatusBadge.tsx`

**Dependencies**: Plan 01 (API integration)
**Autonomous**: Yes - independent page

**Verification Criteria**:
- [ ] Facts table displays all facts with correct columns
- [ ] Filters work (status: all/verified/unverified/outdated/deleted)
- [ ] Domain filter works correctly
- [ ] Search finds facts by text content
- [ ] Fact creation form works with validation
- [ ] Fact editing dialog pre-populates existing data
- [ ] Fact deletion has confirmation dialog
- [ ] Citation viewer shows all citations for a fact
- [ ] Verification status badges display correctly
- [ ] Pagination works for datasets > 50 facts
- [ ] Sort by columns (created date, verification status, domain)

**must_haves** (from phase goal):
- Admins can view all business facts
- Admins can filter/search facts
- Admins can create/edit/delete facts
- Citation verification status visible

---

### Wave 6: Activity Logs & Top Citations (Plan 06)
**Goal**: Add verification activity log and top citations display

**Tasks**:
1. Create Verification Logs component
2. Display recent worker activity (successes, failures, warnings)
3. Implement log filtering by level (all, info, warning, error)
4. Show Top Citations by access frequency
5. Add citation detail view (access count, last accessed)
6. Implement log export functionality
7. Create time range filter for logs

**Files Created**:
- `frontend-nextjs/components/admin/jit-verification/VerificationLogs.tsx`
- `frontend-nextjs/components/admin/jit-verification/LogEntry.tsx`
- `frontend-nextjs/components/admin/jit-verification/TopCitations.tsx`
- `frontend-nextjs/components/admin/jit-verification/CitationDetail.tsx`

**Dependencies**: Plan 01 (API integration), Plan 02 (dashboard)
**Autonomous**: No - integrates with dashboard

**Verification Criteria**:
- [ ] Verification logs display in reverse chronological order
- [ ] Log filtering works by level (all, info, warning, error)
- [ ] Each log entry shows timestamp, event, details
- [ ] Top citations display with access counts
- [ ] Citation detail view shows metadata
- [ ] Logs can be exported to CSV
- [ ] Time range filter works (last hour, day, week)
- [ ] Auto-refresh every 10 seconds

**must_haves** (from phase goal):
- Admins can view verification activity
- Top citations identified for optimization
- Activity audit trail available

---

### Wave 7: Polish & Error Handling (Plan 07)
**Goal**: Add comprehensive error handling, loading states, and polish

**Tasks**:
1. Implement error boundaries for all components
2. Add loading skeletons for better perceived performance
3. Create toast notifications for user feedback
4. Implement retry logic for failed API calls
5. Add empty states when no data available
6. Create offline indicator for connection issues
7. Add keyboard shortcuts (Ctrl+K for search, etc.)
8. Implement responsive design for mobile
9. Add accessibility features (ARIA labels, screen readers)
10. Create help tooltips for complex metrics

**Files Modified**:
- All components from Plans 02-06
- `frontend-nextjs/components/admin/shared/LoadingSkeleton.tsx`
- `frontend-nextjs/components/admin/shared/ErrorBoundary.tsx`
- `frontend-nextjs/components/admin/shared/EmptyState.tsx`

**Dependencies**: Plans 02-06 (all components)
**Autonomous**: No - final polish phase

**Verification Criteria**:
- [ ] Error boundaries catch and display errors gracefully
- [ ] Loading skeletons show during data fetch
- [ ] Toast notifications appear for actions (start worker, clear cache, etc.)
- [ ] Failed API calls auto-retry 3 times with exponential backoff
- [ ] Empty states display when no data (no facts, no logs, etc.)
- [ ] Offline indicator shows when backend unreachable
- [ ] Keyboard shortcuts work (documented in help tooltip)
- [ ] Responsive design works on mobile/tablet
- [ ] All components have ARIA labels
- [ ] Help tooltips explain complex metrics

**must_haves** (from phase goal):
- Robust error handling throughout
- Good UX with loading states and feedback
- Accessible to all users
- Works on mobile devices

---

## Execution Order

**Sequential Waves**:
1. **Wave 1** (Foundation) → **Wave 2** (Dashboard) → **Wave 3** (Cache) → **Wave 7** (Polish)
2. **Wave 1** (Foundation) → **Wave 4** (Citations) → **Wave 7** (Polish)
3. **Wave 1** (Foundation) → **Wave 5** (Business Facts) → **Wave 7** (Polish)
4. **Wave 1** → **Wave 2** → **Wave 6** (Logs) → **Wave 7** (Polish)

**Parallel Execution**:
- Waves 4 and 5 can run in parallel after Wave 1
- Wave 6 can start after Wave 2
- Wave 7 is final polish for all components

---

## Success Criteria

**Phase Goal**: Admins can fully manage JIT verification system through web UI

**Functional Requirements**:
- [ ] Admins can view worker status and control it (start/stop)
- [ ] Admins can monitor cache performance (hit rates, latency, size)
- [ ] Admins can manage cache (clear, warm, view metrics)
- [ ] Admins can manually verify citations with bulk support
- [ ] Admins can manage business facts (CRUD operations)
- [ ] Admins can view verification activity logs
- [ ] Admins can identify top citations for optimization

**Non-Functional Requirements**:
- [ ] All API calls have error handling
- [ ] Loading states for all async operations
- [ ] Responsive design (mobile, tablet, desktop)
- [ ] Accessible (ARIA labels, keyboard navigation)
- [ ] Real-time updates (10s polling)
- [ ] Performance: < 2s page load, < 500ms interaction response

**Quality Gates**:
- [ ] No console errors in production build
- [ ] TypeScript strict mode passes
- [ ] All components have unit tests
- [ ] API integration tested with mocked responses
- [ ] Cross-browser tested (Chrome, Firefox, Safari)

---

## Files Modified

### Backend (Already Complete)
- `backend/api/admin/jit_verification_routes.py` - Admin API endpoints
- `backend/core/jit_verification_cache.py` - Cache implementation
- `backend/core/jit_verification_worker.py` - Worker implementation
- `backend/main_api_app.py` - Route registration

### Frontend (To Be Created)
- `frontend-nextjs/app/admin/jit-verification/page.tsx` - Main dashboard
- `frontend-nextjs/app/admin/business-facts/page.tsx` - Facts management
- `frontend-nextjs/components/admin/jit-verification/*` - Dashboard components
- `frontend-nextjs/components/admin/business-facts/*` - Facts components
- `frontend-nextjs/lib/api-admin.ts` - Admin API client
- `frontend-nextjs/types/jit-verification.ts` - TypeScript types
- `frontend-nextjs/components/layout/Sidebar.tsx` - Navigation updates

---

## Testing Strategy

**Unit Tests** (Jest + React Testing Library):
- Component rendering tests
- User interaction tests
- Error boundary tests
- Form validation tests

**Integration Tests**:
- API client function tests
- End-to-end workflow tests
- Error handling tests

**Manual Testing Checklist**:
- [ ] Worker can be started and stopped
- [ ] Cache can be cleared and warmed
- [ ] Citations can be verified (single and bulk)
- [ ] Facts can be created, edited, deleted
- [ ] Filters work on all tables
- [ ] Real-time updates work (10s polling)
- [ ] Error states display correctly
- [ ] Mobile responsive

---

## Timeline Estimate

**Total Development Time**: 3-4 weeks

**Wave Breakdown**:
- Wave 1 (Foundation): 2 days
- Wave 2 (Dashboard): 4 days
- Wave 3 (Cache): 3 days
- Wave 4 (Citations): 2 days
- Wave 5 (Business Facts): 4 days
- Wave 6 (Logs): 2 days
- Wave 7 (Polish): 3 days

**Parallel Execution Potential**: Waves 4 and 5 can run in parallel after Wave 1, saving ~2 days.

**Optimized Timeline**: ~3 weeks with parallel execution
