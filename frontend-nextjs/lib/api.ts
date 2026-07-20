// API client for ATOM platform frontend-backend integration
import axios from "axios";
import {
  getUserFriendlyErrorMessage,
  getErrorAction,
  getErrorSeverity,
  isRetryableError,
  enhanceError,
} from "./error-mapping";
import { retry } from "@lifeomic/attempt";

// Base API configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_BASE_URL ||
  process.env.PYTHON_BACKEND_URL ||
  "http://127.0.0.1:8000";
const API_TIMEOUT = 10000; // 10 seconds
const MAX_RETRIES = 3;

// Create axios instance with default configuration
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor for adding auth tokens if available
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token if available (check both auth_token and token)
    const token = typeof window !== "undefined"
      ? (localStorage.getItem("auth_token") || localStorage.getItem("token"))
      : null;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // Add request ID for tracking
    config.headers["X-Request-ID"] = generateRequestId();

    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// Response interceptor with exponential backoff retry logic
apiClient.interceptors.response.use(
  (response) => response,
  async (error: any) => {
    const originalRequest = error.config;

    // Log technical error for debugging (not user-facing)
    console.error('[API Error]', {
      code: error.code,
      status: error.response?.status,
      message: error.message,
      url: originalRequest?.url,
    });

    // Don't retry if no config, request already marked to not retry, or error is permanent/non-retryable (401, 403, 404, etc.)
    if (!originalRequest || originalRequest.__isRetryRequest === true || originalRequest.retry === false || !isRetryableError(error)) {
      return Promise.reject(enhanceError(error));
    }

    // Mark the request to bypass this interceptor to prevent infinite loop
    originalRequest.__isRetryRequest = true;

    // Use @lifeomic/attempt retry for exponential backoff and jitter
    try {
      const response = await retry(
        async () => {
          return await apiClient(originalRequest);
        },
        {
          maxAttempts: MAX_RETRIES,
          delay: 1000, // Initial 1 second delay
          factor: 2, // Exponential backoff: 1s, 2s, 4s
          jitter: true, // Add randomness to prevent retry storms
          minDelay: 500,
          maxDelay: 10000,
          timeout: API_TIMEOUT,
          handleError: (attemptError: any) => {
            return isRetryableError(attemptError);
          },
          beforeAttempt: (context: any) => {
            if (context.attemptNum > 1) {
              console.log(`Retry attempt ${context.attemptNum} of ${MAX_RETRIES}`);
            }
          },
        }
      );

      return response;
    } catch (retryError) {
      return Promise.reject(enhanceError(retryError));
    }
  },
);

// Response interceptor: handle 401 cleanly without forcing browser page reload on background API calls
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      const path = typeof window !== "undefined" ? window.location.pathname : "";
      const isAuthPage = path.startsWith("/login") || path.startsWith("/auth/");
      const isExplicitLogout = typeof window !== "undefined" && localStorage.getItem("atom_explicit_logout") === "1";

      if (isExplicitLogout && !isAuthPage) {
        if (typeof window !== "undefined") {
          localStorage.removeItem("auth_token");
          localStorage.removeItem("token");
          window.location.href = `/login?callbackUrl=${encodeURIComponent(window.location.href)}`;
        }
      }
    }
    return Promise.reject(error);
  },
);

// System API
export const systemAPI = {
  getHealth: () => apiClient.get("/api/health"),
  getStatus: () => apiClient.get("/api/status"),
  getSystemStatus: () => apiClient.get("/api/status"),
};

// Service Registry API
export const serviceRegistryAPI = {
  getServices: () => apiClient.get("/api/services/registry"),
  getService: (serviceId: string) =>
    apiClient.get(`/api/services/registry/${serviceId}`),
  registerService: (serviceData: any) =>
    apiClient.post("/api/services/registry", serviceData),
  updateService: (serviceId: string, serviceData: any) =>
    apiClient.put(`/api/services/registry/${serviceId}`, serviceData),
  deleteService: (serviceId: string) =>
    apiClient.delete(`/api/services/registry/${serviceId}`),
  testService: (serviceId: string) =>
    apiClient.post(`/api/services/registry/${serviceId}/test`),
  getServiceHealth: (serviceId: string) =>
    apiClient.get(`/api/services/registry/${serviceId}/health`),
};

// BYOK (Bring Your Own Key) API
export const byokAPI = {
  getProviders: () => apiClient.get("/api/ai/providers"),
  getProvider: (providerId: string) =>
    apiClient.get(`/api/ai/providers/${providerId}`),
  configureProvider: (providerId: string, config: any) =>
    apiClient.post(`/api/ai/providers/${providerId}/configure`, config),
  testProvider: (providerId: string) =>
    apiClient.post(`/api/ai/providers/${providerId}/test`),
  getProviderStats: (providerId: string) =>
    apiClient.get(`/api/ai/providers/${providerId}/stats`),
  getProviderCosts: (providerId: string) =>
    apiClient.get(`/api/ai/providers/${providerId}/costs`),
  validateProvider: (providerId: string, config: any) =>
    apiClient.post(`/api/ai/providers/${providerId}/validate`, config),
};

// Workflow API
export const workflowAPI = {
  getTemplates: () => apiClient.get("/api/workflow-templates/"),
  getTemplate: (templateId: string) =>
    apiClient.get(`/api/workflow-templates/${templateId}`),
  createWorkflow: (workflowData: any) =>
    apiClient.post("/api/workflows", workflowData),
  executeWorkflow: (workflowId: string, inputData: any) =>
    apiClient.post(`/api/workflows/${workflowId}/execute`, inputData),
  getWorkflowStatus: (workflowId: string) =>
    apiClient.get(`/api/workflows/${workflowId}/status`),
  getWorkflowHistory: (workflowId: string) =>
    apiClient.get(`/api/workflows/${workflowId}/history`),
  cancelWorkflow: (workflowId: string) =>
    apiClient.post(`/api/workflows/${workflowId}/cancel`),
  getWorkflowLogs: (workflowId: string) =>
    apiClient.get(`/api/workflows/${workflowId}/logs`),
  validateWorkflow: (workflowData: any) =>
    apiClient.post("/api/workflows/validate", workflowData),
};

// OAuth API
export const oauthAPI = {
  authorize: (serviceId: string, redirectUri: string) =>
    apiClient.post(`/api/auth/${serviceId}/authorize`, {
      redirect_uri: redirectUri,
    }),
  handleCallback: (serviceId: string, code: string, state?: string) =>
    apiClient.post(`/api/auth/${serviceId}/callback`, { code, state }),
  getServiceStatus: (serviceId: string) =>
    apiClient.get(`/api/auth/${serviceId}/status`),
};

// Integration APIs for specific services
export const integrationAPI = {
  asana: {
    getTasks: () => apiClient.get("/api/integrations/asana/tasks"),
    createTask: (taskData: any) =>
      apiClient.post("/api/integrations/asana/tasks", taskData),
    updateTask: (taskId: string, taskData: any) =>
      apiClient.put(`/api/integrations/asana/tasks/${taskId}`, taskData),
  },
  notion: {
    getPages: () => apiClient.get("/api/integrations/notion/pages"),
    search: (query: string) =>
      apiClient.get(
        `/api/integrations/notion/search?query=${encodeURIComponent(query)}`,
      ),
  },
  slack: {
    getChannels: () => apiClient.get("/api/integrations/slack/channels"),
    sendMessage: (channelId: string, message: string) =>
      apiClient.post(`/api/integrations/slack/messages`, {
        channel: channelId,
        text: message,
      }),
    getMessages: (channelId: string) =>
      apiClient.get(`/api/integrations/slack/messages?channel=${channelId}`),
  },
  googleCalendar: {
    getEvents: () => apiClient.get("/api/integrations/google/calendar/events"),
    createEvent: (eventData: any) =>
      apiClient.post("/api/integrations/google/calendar/events", eventData),
    updateEvent: (eventId: string, eventData: any) =>
      apiClient.put(
        `/api/integrations/google/calendar/events/${eventId}`,
        eventData,
      ),
  },
  gmail: {
    getEmails: () => apiClient.get("/api/integrations/google/gmail/emails"),
    getLabels: () => apiClient.get("/api/integrations/google/gmail/labels"),
  },
};

// Dashboard data API
export const dashboardAPI = {
  getOverview: () => apiClient.get("/api/dashboard/overview"),
  getIntegrationStatus: () => apiClient.get("/api/dashboard/integrations"),
};

// ============================================================================
// USER MANAGEMENT API (Frontend to Backend Migration)
// Feature flag: Use backend API or direct DB
// ============================================================================
export const USE_BACKEND_API = process.env.NEXT_PUBLIC_USE_BACKEND_API === 'true';

// User Management API
export const userManagementAPI = {
  getCurrentUser: () => apiClient.get("/api/users/me"),
  getUserSessions: () => apiClient.get("/api/users/sessions"),
  revokeSession: (sessionId: string) =>
    apiClient.delete(`/api/users/sessions/${sessionId}`),
  revokeAllSessions: () => apiClient.delete("/api/users/sessions"),
};

// Email Verification API
export const emailVerificationAPI = {
  verifyEmail: (email: string, code: string) =>
    apiClient.post("/api/email-verification/verify", { email, code }),
  sendVerificationEmail: (email: string) =>
    apiClient.post("/api/email-verification/send", { email }),
};

// Tenant API
export const tenantAPI = {
  getTenantBySubdomain: (subdomain: string) =>
    apiClient.get(`/api/tenants/by-subdomain/${subdomain}`),
  getTenantContext: () => apiClient.get("/api/tenants/context"),
};

// Admin API
export const adminAPI = {
  getAdminUsers: () => apiClient.get("/api/admin/users"),
  updateAdminLastLogin: (adminId: string) =>
    apiClient.patch(`/api/admin/users/${adminId}/last-login`),
};

// Meeting API
export const meetingAPI = {
  getMeetingAttendance: (taskId: string) =>
    apiClient.get(`/api/meetings/attendance/${taskId}`),
};

// Financial API
export const financialAPI = {
  getNetWorthSummary: () => apiClient.get("/api/financial/net-worth/summary"),
  listFinancialAccounts: () => apiClient.get("/api/financial/accounts"),
};

// Utility functions
export const apiUtils = {
  // Generate unique request ID
  generateRequestId: () => {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  },
};

// Helper function to generate unique request ID
function generateRequestId(): string {
  return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// Export the main API client for custom requests
export default apiClient;

export interface FetchOptions extends RequestInit {
  retries?: number;
}

export async function fetchWithErrorHandling(url: string, options: FetchOptions = {}): Promise<any> {
  const { retries = 0, ...fetchOptions } = options;
  let attempts = 0;
  const maxAttempts = retries + 1;

  while (attempts < maxAttempts) {
    attempts++;
    try {
      const response = await fetch(url, fetchOptions);

      // Check for abort signal aborting before or during request
      if (fetchOptions.signal?.aborted) {
        throw new Error("Request aborted");
      }

      if (!response.ok) {
        // Only retry on 5xx status codes, not on 4xx
        if (response.status >= 500 && attempts < maxAttempts) {
          continue;
        }
        const error = new Error(`HTTP ${response.status}`);
        (error as any).noRetry = true;
        throw error;
      }

      if (response.status === 204) {
        return {};
      }

      const data = await response.json();

      if (data === null || data === undefined) {
        throw new Error("Null or undefined response");
      }

      if (Array.isArray(data)) {
        throw new Error("Array response when object expected");
      }

      if (typeof data === "object" && Object.keys(data).length === 0) {
        throw new Error("Missing response fields");
      }

      return data;
    } catch (error: any) {
      // If request was aborted or marked as noRetry, propagate the error immediately without retry
      if (error.noRetry || fetchOptions.signal?.aborted || error.name === 'AbortError') {
        throw error;
      }
      
      // If we have remaining attempts, retry on network errors (non-HTTP errors)
      if (attempts < maxAttempts) {
        continue;
      }
      throw error;
    }
  }
}

