/**
 * Admin API Client
 *
 * Provides functions for calling admin-specific endpoints.
 * These endpoints require ADMIN role and proper authentication.
 *
 * @module adminAPI
 */

import axios from "axios";
import type {
  CacheStatsResponse,
  WorkerMetricsResponse,
  VerifyCitationsRequest,
  VerifyCitationsResponse,
  HealthCheckResponse,
  CacheClearResponse,
  WorkerControlResponse,
  CacheWarmResponse,
  BusinessFact,
  BusinessFactFilters,
  CreateBusinessFactRequest,
  UpdateBusinessFactRequest,
  DeleteBusinessFactResponse,
  TopCitationsResponse,
  JITConfigResponse,
  VerifyFactCitationsResponse,
} from "@/types/jit-verification";

// Base API configuration (same as main API client)
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_BASE_URL ||
  process.env.PYTHON_BACKEND_URL ||
  "http://127.0.0.1:8000";

const API_TIMEOUT = 30000; // 30 seconds for admin operations

// Create dedicated axios instance for admin APIs
const adminApiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor for adding auth tokens
adminApiClient.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem("auth_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // Add request ID for tracking
    config.headers["X-Request-ID"] = generateRequestId();

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
adminApiClient.interceptors.response.use(
  (response) => response,
  async (error: any) => {
    const originalRequest = error.config;

    console.error("[Admin API Error]", {
      code: error.code,
      status: error.response?.status,
      message: error.message,
      url: originalRequest?.url,
    });

    // Don't retry admin operations - they should be idempotent
    // Enhance error with user-friendly properties
    const enhancedError = {
      ...error,
      userMessage: error.response?.data?.message || error.message,
      severity: error.response?.status === 401 ? "auth" : "error",
      action: error.response?.status === 401 ? "Please log in again" : undefined,
    };

    return Promise.reject(enhancedError);
  }
);

/**
 * Generate a unique request ID for tracking
 */
function generateRequestId(): string {
  return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * JIT Verification Admin API
 *
 * Provides functions for managing the JIT verification cache and background worker.
 */
export const jitVerificationAPI = {
  /**
   * Get JIT verification cache statistics
   */
  getCacheStats: () =>
    adminApiClient.get<CacheStatsResponse>(
      "/api/admin/governance/jit/cache/stats"
    ),

  /**
   * Clear all JIT verification caches (L1 and L2)
   */
  clearCache: () =>
    adminApiClient.post<CacheClearResponse>(
      "/api/admin/governance/jit/cache/clear"
    ),

  /**
   * Verify one or more citations (with cache check)
   */
  verifyCitations: (request: VerifyCitationsRequest) =>
    adminApiClient.post<VerifyCitationsResponse>(
      "/api/admin/governance/jit/verify-citations",
      request
    ),

  /**
   * Get worker metrics
   */
  getWorkerMetrics: () =>
    adminApiClient.get<WorkerMetricsResponse>(
      "/api/admin/governance/jit/worker/metrics"
    ),

  /**
   * Start the background verification worker
   */
  startWorker: () =>
    adminApiClient.post<WorkerControlResponse>(
      "/api/admin/governance/jit/worker/start"
    ),

  /**
   * Stop the background verification worker
   */
  stopWorker: () =>
    adminApiClient.post<WorkerControlResponse>(
      "/api/admin/governance/jit/worker/stop"
    ),

  /**
   * Verify all citations for a specific fact
   */
  verifyFactCitations: (factId: string) =>
    adminApiClient.post<VerifyFactCitationsResponse>(
      `/api/admin/governance/jit/worker/verify-fact/${factId}`
    ),

  /**
   * Get most frequently accessed citations
   */
  getTopCitations: (limit: number = 20) =>
    adminApiClient.get<TopCitationsResponse>(
      `/api/admin/governance/jit/worker/top-citations?limit=${limit}`
    ),

  /**
   * Get system health status
   */
  getHealth: () =>
    adminApiClient.get<HealthCheckResponse>(
      "/api/admin/governance/jit/health"
    ),

  /**
   * Warm the cache by pre-verifying citations
   */
  warmCache: (limit: number = 100) =>
    adminApiClient.post<CacheWarmResponse>(
      `/api/admin/governance/jit/cache/warm?limit=${limit}`
    ),

  /**
   * Get current configuration
   */
  getConfig: () =>
    adminApiClient.get<JITConfigResponse>(
      "/api/admin/governance/jit/config"
    ),
};

/**
 * Business Facts Admin API
 *
 * Provides functions for managing business facts with citations.
 */
export const businessFactsAPI = {
  /**
   * List all business facts with optional filters
   */
  listFacts: (filters: BusinessFactFilters = {}) => {
    const params = new URLSearchParams();

    if (filters.status && filters.status !== "all") {
      params.append("status", filters.status);
    }
    if (filters.domain) {
      params.append("domain", filters.domain);
    }
    if (filters.limit) {
      params.append("limit", filters.limit.toString());
    }

    const queryString = params.toString();
    return adminApiClient.get<{ facts: BusinessFact[] }>(
      `/api/admin/governance/facts${queryString ? `?${queryString}` : ""}`
    );
  },

  /**
   * Get a specific fact by ID
   */
  getFact: (factId: string) =>
    adminApiClient.get<BusinessFact>(
      `/api/admin/governance/facts/${factId}`
    ),

  /**
   * Create a new business fact
   */
  createFact: (request: CreateBusinessFactRequest) =>
    adminApiClient.post<BusinessFact>(
      "/api/admin/governance/facts",
      request
    ),

  /**
   * Update an existing fact
   */
  updateFact: (factId: string, request: UpdateBusinessFactRequest) =>
    adminApiClient.put<BusinessFact>(
      `/api/admin/governance/facts/${factId}`,
      request
    ),

  /**
   * Delete (soft delete) a fact
   */
  deleteFact: (factId: string) =>
    adminApiClient.delete<DeleteBusinessFactResponse>(
      `/api/admin/governance/facts/${factId}`
    ),
};

/**
 * Real-time polling helper
 *
 * Provides a convenient way to poll endpoints for real-time updates
 */
export class AdminPoller {
  private intervalId: NodeJS.Timeout | null = null;

  /**
   * Start polling an endpoint at a specified interval
   */
  start<T>(
    fetchFn: () => Promise<T>,
    onUpdate: (data: T) => void,
    intervalMs: number = 10000 // Default 10 seconds
  ): void {
    // Clear any existing interval
    this.stop();

    // Initial fetch
    fetchFn()
      .then((response) => {
        onUpdate(response.data);
      })
      .catch((error) => {
        console.error("[AdminPoller] Initial fetch error:", error);
      });

    // Set up recurring fetch
    this.intervalId = setInterval(async () => {
      try {
        const response = await fetchFn();
        onUpdate(response.data);
      } catch (error) {
        console.error("[AdminPoller] Polling error:", error);
        // Don't stop on error - continue polling
      }
    }, intervalMs);
  }

  /**
   * Stop polling
   */
  stop(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  /**
   * Check if currently polling
   */
  isRunning(): boolean {
    return this.intervalId !== null;
  }
}

/**
 * Helper function to get auth token for API requests
 */
export function getAuthToken(): string | null {
  return localStorage.getItem("auth_token");
}

/**
 * Helper function to set auth token
 */
export function setAuthToken(token: string): void {
  localStorage.setItem("auth_token", token);
}

/**
 * Helper function to clear auth token
 */
export function clearAuthToken(): void {
  localStorage.removeItem("auth_token");
}

/**
 * Helper function to check if user is authenticated
 */
export function isAuthenticated(): boolean {
  return !!getAuthToken();
}

/**
 * Export API clients for use in components
 */
export default adminApiClient;
