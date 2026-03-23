# Research Summary: Verification Result Caching for Business Policy Facts

**Domain:** Business Policy Citation Verification Caching
**Researched:** March 22, 2026
**Overall Confidence:** MEDIUM

## Executive Summary

The Atom platform currently performs real-time verification of business fact citations by checking R2/S3 storage on every citation validation request. This creates unnecessary latency (~200ms per citation per the CITATION_SYSTEM_GUIDE.md benchmarks) and cost. Research reveals that citation verification results are highly cacheable: citations don't change frequently, and verification checks are binary (exists/doesn't exist).

The research confirms that Atom already has two production-grade caching implementations (`GovernanceCache` and `MessagingCache`) that can serve as patterns. A dedicated `CitationVerificationCache` following these patterns would reduce verification latency by 90%+ (from ~200ms to <5ms) and cut R2/S3 API costs by 80%+ through aggressive caching with intelligent invalidation.

## Key Findings

**Stack:** In-memory OrderedDict cache with thread-safe operations (based on existing `GovernanceCache`), 24-hour TTL for verification results with manual invalidation hooks, SHA-256 hash-based cache keys for deduplication

**Architecture:** Dedicated `CitationVerificationCache` class in `backend/core/`, decorator pattern for transparent caching of `storage.check_exists()` calls, metrics integration with existing monitoring infrastructure

**Critical Pitfall:** MUST implement version-based invalidation for policy documents that are updated/re-uploaded, otherwise stale verification results will persist for up to 24 hours

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Phase 1: Cache Foundation** - Implement `CitationVerificationCache` class with TTL-based expiration
   - Addresses: Core latency problem (200ms → <5ms)
   - Avoids: Complex invalidation scenarios initially
   - Complexity: Low (follows existing `GovernanceCache` pattern)

2. **Phase 2: Cache Invalidation** - Add manual invalidation hooks and event-driven updates
   - Addresses: Document update scenarios, policy changes
   - Avoids: Serving stale verification results
   - Complexity: Medium (requires document update event listeners)

3. **Phase 3: Cache Pre-warming** - Implement intelligent pre-loading of frequent facts
   - Addresses: Cold start problem, first-request latency
   - Complexity: Medium (requires usage analytics)

**Phase ordering rationale:**
- Start with cache foundation to get immediate performance benefits
- Add invalidation before pre-warming to ensure cache freshness
- Pre-warming last, as it requires accumulated usage data

**Research flags for phases:**
- Phase 1: Standard patterns (use `GovernanceCache` as reference), unlikely to need research
- Phase 2: Document update event hooks may need investigation into upload workflow
- Phase 3: Requires analytics data collection strategy definition

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Based on proven `GovernanceCache` implementation (975 lines production code) |
| Cache Key Design | HIGH | Content-addressable storage patterns well-established, SHA-256 hashing standard |
| TTL Strategy | MEDIUM | 24-hour recommendation based on policy change frequency assumptions |
| Pre-warming Criteria | LOW | No existing usage analytics in codebase; requires data collection first |
| Invalidation Mechanisms | MEDIUM | Document update events understood, but hook points need verification |

## Gaps to Address

1. **Usage Analytics**: Need to collect citation verification frequency data before implementing pre-warming
2. **Document Versioning**: Current storage system doesn't track document versions; may need metadata extension
3. **Multi-citation Coordination**: When a fact has multiple citations, should we cache each independently or as a group?
4. **Cache Size Limits**: GovernanceCache uses 1000-entry max; need sizing guidance for citation cache
5. **Workspace Isolation**: How to handle per-workspace citation caches (global vs. partitioned)?
