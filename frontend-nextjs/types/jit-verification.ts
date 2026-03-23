/**
 * JIT Verification System Type Definitions
 *
 * These types match the backend API response models exactly.
 * Source: backend/api/admin/jit_verification_routes.py
 */

/**
 * Citation verification result with metadata
 */
export interface CitationVerificationResult {
  exists: boolean;
  checked_at: string; // ISO datetime
  citation: string;
  size?: number; // File size in bytes
  last_modified?: string; // ISO datetime
}

/**
 * Business fact with verification status
 */
export interface BusinessFact {
  id: string;
  fact: string;
  citations: string[];
  reason: string;
  domain: string;
  verification_status: "verified" | "unverified" | "outdated" | "deleted";
  created_at: string; // ISO datetime
  last_verified: string; // ISO datetime
}

/**
 * Cache statistics response
 */
export interface CacheStatsResponse {
  l1_verification_cache_size: number;
  l1_query_cache_size: number;
  l1_verification_hits: number;
  l1_verification_misses: number;
  l1_verification_hit_rate: number;
  l1_query_hits: number;
  l1_query_misses: number;
  l1_query_hit_rate: number;
  l1_evictions: number;
  l2_enabled: boolean;
}

/**
 * Worker metrics response
 */
export interface WorkerMetricsResponse {
  running: boolean;
  total_citations: number;
  verified_count: number;
  failed_count: number;
  stale_facts: number;
  outdated_facts: number;
  last_run_time?: string; // ISO datetime
  last_run_duration: number; // seconds
  average_verification_time: number; // seconds
  top_citations: TopCitation[];
}

/**
 * Top citation by access frequency
 */
export interface TopCitation {
  citation: string;
  access_count: number;
}

/**
 * Verification request
 */
export interface VerifyCitationsRequest {
  citations: string[];
  force_refresh?: boolean;
}

/**
 * Verification response
 */
export interface VerifyCitationsResponse {
  results: CitationVerificationResult[];
  total_count: number;
  verified_count: number;
  failed_count: number;
  duration_seconds: number;
}

/**
 * System health status
 */
export type SystemHealthStatus = "healthy" | "degraded" | "unhealthy";

/**
 * Health check response
 */
export interface HealthCheckResponse {
  status: SystemHealthStatus;
  issues: string[];
  cache: {
    l1_enabled: boolean;
    l2_enabled: boolean;
    verification_hit_rate: string; // e.g., "87%"
    query_hit_rate: string; // e.g., "80%"
    total_cached_verifications: number;
  };
  worker: {
    running: boolean;
    last_run?: string; // ISO datetime
    verified_count: number;
    failed_count: number;
    avg_verification_time: string; // e.g., "0.200s"
  };
  checked_at: string; // ISO datetime
}

/**
 * Cache clear response
 */
export interface CacheClearResponse {
  status: string;
  message: string;
  cleared_at: string; // ISO datetime
}

/**
 * Worker control response (start/stop)
 */
export interface WorkerControlResponse {
  status: string;
  message: string;
  workspace_id?: string;
  check_interval_seconds?: number;
  started_at?: string; // ISO datetime for start
  stopped_at?: string; // ISO datetime for stop
}

/**
 * Cache warm response
 */
export interface CacheWarmResponse {
  status: string;
  facts_processed: number;
  citations_verified: number;
  verified_count: number;
  duration_seconds: number;
  warmed_at: string; // ISO datetime
}

/**
 * Business fact list response
 */
export interface BusinessFactListResponse {
  facts: BusinessFact[];
  total_count: number;
  filtered_count: number;
}

/**
 * Business fact create request
 */
export interface CreateBusinessFactRequest {
  fact: string;
  citations: string[];
  reason: string;
  domain: string;
}

/**
 * Business fact update request
 */
export interface UpdateBusinessFactRequest {
  fact?: string;
  citations?: string[];
  reason?: string;
  domain?: string;
  verification_status?: "verified" | "unverified" | "outdated";
}

/**
 * Business fact delete response
 */
export interface DeleteBusinessFactResponse {
  status: string;
  id: string;
  deleted_at: string; // ISO datetime
}

/**
 * Top citations response
 */
export interface TopCitationsResponse {
  top_citations: TopCitation[];
  total_unique_citations: number;
  retrieved_at: string; // ISO datetime
}

/**
 * JIT configuration response
 */
export interface JITConfigResponse {
  worker: {
    workspace_id: string;
    check_interval_seconds: number;
    batch_size: number;
    max_concurrent: number;
    running: boolean;
  };
  cache: {
    l1: {
      max_size: number;
      verification_ttl_seconds: number;
      query_ttl_seconds: number;
    };
    l2: {
      enabled: boolean;
      verification_ttl_seconds: number;
      query_ttl_seconds: number;
      redis_url: string;
    };
  };
}

/**
 * Verification log entry
 */
export interface VerificationLogEntry {
  timestamp: string; // ISO datetime
  event: string;
  details?: string;
  level: "info" | "warning" | "error";
  citation?: string;
}

/**
 * Fact verification response
 */
export interface VerifyFactCitationsResponse {
  fact_id: string;
  citation_count: number;
  results: Record<string, CitationVerificationResult>;
  verified_at: string; // ISO datetime
}

/**
 * Filter options for business facts
 */
export interface BusinessFactFilters {
  status?: "all" | "verified" | "unverified" | "outdated" | "deleted";
  domain?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

/**
 * UI State for JIT dashboard
 */
export interface JITDashboardState {
  workerStatus: "loading" | "running" | "stopped" | "error";
  cacheStats: CacheStatsResponse | null;
  workerMetrics: WorkerMetricsResponse | null;
  healthStatus: HealthCheckResponse | null;
  lastRefresh: Date | null;
  autoRefreshEnabled: boolean;
}

/**
 * UI State for business facts page
 */
export interface BusinessFactsPageState {
  facts: BusinessFact[];
  filteredFacts: BusinessFact[];
  filters: BusinessFactFilters;
  loading: boolean;
  error: string | null;
  selectedFact: BusinessFact | null;
  showCreateDialog: boolean;
  showEditDialog: boolean;
}

/**
 * Citations panel state
 */
export interface CitationsPanelState {
  inputText: string;
  forceRefresh: boolean;
  verifying: boolean;
  results: CitationVerificationResult[] | null;
  filter: "all" | "verified" | "failed";
}
