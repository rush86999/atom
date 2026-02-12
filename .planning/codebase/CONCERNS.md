# Codebase Concerns

**Analysis Date:** 2026-02-10

## Tech Debt

### 1. Large Monolithic Files
**File**: `backend/core/models.py` (5,040 lines)
- **Issue**: Excessive size makes maintenance difficult
- **Files**: `/Users/rushiparikh/projects/atom/backend/core/models.py`
- **Impact**: Hard to navigate, slow performance, high cognitive load
- **Fix approach**: Split into domain-specific modules (agents, workflows, integrations)

### 2. Archive Directory Bloat
**Directory**: `backend/test_archives_20260205_133256/`
- **Issue**: 700+ archived test files clutter workspace
- **Files**: 700+ files in archive directory
- **Impact**: Confuses navigation, slows down git operations
- **Fix approach**: Create proper test archive strategy, move to S3 or separate repository

### 3. Inconsistent Database Patterns
**Files**: Multiple service files throughout backend
- **Issue**: Mix of `SessionLocal()` and `get_db_session()` patterns
- **Files**: Scattered across 30+ service files
- **Impact**: Potential connection leaks, inconsistent error handling
- **Fix approach**: Standardize on `DatabaseSessionManager` pattern across all services

### 4. Duplicate Test Files
**Pattern**: Test files exist both in `backend/accounting/test_*.py` and `backend/tests/`
- **Issue**: Duplicate test coverage
- **Files**: Accounting tests in both locations
- **Impact**: Confusing test execution, maintenance overhead
- **Fix approach**: Consolidate into single `backend/tests/` directory

## Known Bugs

### 1. WebSocket Connection Handling
**File**: `backend/tools/canvas_tool.py`
- **Issue**: Potential WebSocket connection leaks
- **Files**: `/Users/rushiparikh/projects/atom/backend/tools/canvas_tool.py`
- **Symptoms**: Memory leaks, degraded performance over time
- **Trigger**: Multiple simultaneous canvas sessions
- **Workaround**: Monitor connection count and force cleanup

### 2. PDF Processing Dependencies
**File**: `backend/integrations/pdf_processing/pdf_ocr_service.py`
- **Issue**: Multiple fallback dependencies can cause conflicts
- **Files**: `/Users/rushiparikh/projects/atom/backend/integrations/pdf_processing/pdf_ocr_service.py`
- **Symptoms**: Inconsistent image quality, import errors
- **Trigger**: PDFs with complex layouts or images
- **Workaround**: Use single PDF engine, remove fallback conflicts

### 3. Mobile Navigation State
**File**: `mobile/src/navigation/AppNavigator.tsx`
- **Issue**: Navigation state not properly persisted
- **Files**: `/Users/rushiparikh/projects/atom/mobile/src/navigation/AppNavigator.tsx`
- **Symptoms**: Navigation reset on app refresh
- **Trigger**: App background/foreground cycles
- **Workaround**: Implement proper state persistence with AsyncStorage

## Security Considerations

### 1. Debug Mode Security Risk
**File**: `backend/core/base_routes.py`
- **Risk**: Debug mode exposes sensitive error details
- **Files**: `/Users/rushiparikh/projects/atom/backend/core/base_routes.py:536-548`
- **Issue**: Full error messages exposed when `DEBUG=true`
- **Impact**: Information disclosure to attackers
- **Recommendation**: Sanitize error messages in production, enable IP whitelist for debug access

### 2. Canvas JavaScript Security
**File**: `backend/tools/canvas_tool.py`
- **Risk**: JavaScript validation bypass potential
- **Files**: `/Users/rushiparikh/projects/atom/backend/tools/canvas_tool.py:898`
- **Issue**: Pattern-based JavaScript filtering could be circumvented
- **Impact**: Remote code execution
- **Recommendation**: Use Content Security Policy (CSP), sandbox iframe execution

### 3. JWT Debug Bypass
**File**: `backend/core/jwt_verifier.py`
- **Risk**: Debug mode could bypass security checks
- **Files**: `/Users/rushiparikh/projects/atom/backend/core/jwt_verifier.py`
- **Issue**: Debug mode whitelisting could be abused
- **Impact**: Unauthorized access in development environments
- **Recommendation**: Separate dev/prod JWT secrets, disable whitelisting in production

## Performance Bottlenecks

### 1. Large File Processing
**File**: `backend/integrations/pdf_processing/pdf_memory_integration.py`
- **Problem**: Memory-intensive PDF operations
- **Files**: `/Users/rushiparikh/projects/atom/backend/integrations/pdf_processing/pdf_memory_integration.py`
- **Cause**: Loading entire PDFs into memory
- **Improvement path**: Stream processing, chunk-based processing

### 2. Database Query Patterns
**Files**: Multiple service files with potential N+1 queries
- **Problem**: Inefficient database operations
- **Files**: Scattered across integration services
- **Cause**: Individual queries in loops
- **Improvement path**: Implement query batching, use SQLAlchemy eager loading

### 3. WebSocket Connection Management
**File**: `standalone_test_server.py`
- **Problem**: Memory growth with many connections
- **Files**: `/Users/rushiparikh/projects/atom/backend/standalone_test_server.py`
- **Cause**: No connection cleanup timeout
- **Improvement path**: Implement connection timeouts, periodic cleanup

## Fragile Areas

### 1. Mobile Device Context
**File**: `mobile/src/contexts/DeviceContext.tsx`
- **Files**: `/Users/rushiparikh/projects/atom/mobile/src/contexts/DeviceContext.tsx`
- **Why fragile**: Platform-specific APIs, permission handling
- **Safe modification**: Always test on both iOS and Android
- **Test coverage**: Needs device-specific unit tests

### 2. Agent Governance System
**Files**: Core governance services
- **Why fragile**: Complex dependency chain, critical business logic
- **Files**: `/Users/rushiparikh/projects/atom/backend/core/agent_governance_service.py`, `/Users/rushiparikh/projects/atom/backend/core/governance_cache.py`
- **Safe modification**: Use service factory pattern, extensive testing
- **Test coverage**: Needs integration tests for all maturity levels

### 3. Episodic Memory System
**Files**: Episode retrieval and segmentation services
- **Why fragile**: Complex algorithms, database dependencies
- **Files**: `/Users/rushiparikh/projects/atom/backend/episode_segmentation_service.py`, `/Users/rushiparikh/projects/atom/backend/episode_retrieval_service.py`
- **Safe modification**: Separate business logic from storage
- **Test coverage**: Needs performance tests with large datasets

## Scaling Limits

### 1. Concurrent WebSocket Connections
**Current capacity**: ~100 connections (estimated)
- **Limit**: Memory constraints in WebSocket manager
- **Scaling path**: Implement connection pooling, horizontal scaling

### 2. PDF Processing Throughput
**Current capacity**: ~10 PDFs/minute (estimated)
- **Limit**: CPU-bound processing
- **Scaling path**: Queue-based processing, worker nodes

### 3. Database Connection Pool
**Current capacity**: 10 connections (SQLite default)
- **Limit**: Concurrency bottleneck
- **Scaling path**: PostgreSQL, connection pooling

## Dependencies at Risk

### 1. pdf2image Dependency
**Package**: pdf2image
- **Risk**: Poppler system dependency
- **Impact**: Installation complexity, platform compatibility
- **Migration plan**: Use PyMuPDF as primary, pdf2image as optional

### 2. Playwright Browser Automation
**Package**: playwright
- **Risk**: Browser updates breaking automation
- **Impact**: Maintenance overhead, automation failures
- **Migration plan**: Implement headless browser fallback strategy

## Missing Critical Features

### 1. Production Monitoring
- **Problem**: No comprehensive monitoring system
- **Blocks**: Proactive issue detection, performance optimization
- **Priority**: High - essential for production reliability

### 2. Comprehensive Error Recovery
- **Problem**: Inconsistent error recovery patterns
- **Blocks**: System resilience, automated recovery
- **Priority**: Medium - improves user experience

### 3. Data Archival Strategy
- **Problem**: No data lifecycle management
- **Blocks**: Compliance, performance, storage costs
- **Priority**: Medium - long-term system health

## Test Coverage Gaps

### 1. Canvas JavaScript Security Tests
**Untested area**: JavaScript pattern validation
- **What's not tested**: Edge cases in pattern matching
- **Files**: `/Users/rushiparikh/projects/atom/backend/tests/test_canvas_javascript.py`
- **Risk**: Potential security bypass
- **Priority**: High - security-critical

### 2. Mobile Integration Tests
**Untested area**: Mobile-backend integration flows
- **What's not tested**: Authentication, device registration
- **Files**: `/Users/rushiparikh/projects/atom/mobile/src/__tests__/`
- **Risk**: Integration failures in production
- **Priority**: High - user-facing feature

### 3. Performance Tests for Large Datasets
**Untested area**: Episodic memory performance with >10k episodes
- **What's not tested**: Retrieval latency, memory usage
- **Files**: Performance tests for episode services
- **Risk**: Degraded performance in production
- **Priority**: Medium - scalability concern

---

*Concerns audit: 2026-02-10*