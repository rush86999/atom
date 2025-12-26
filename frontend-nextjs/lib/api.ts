// API client for ATOM platform frontend-backend integration
import axios, { AxiosResponse, AxiosError } from "axios";

// Base API configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_TIMEOUT = 10000; // 10 seconds
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // 1 second

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
  },
);

// Response interceptor with retry logic
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as any;

    if (!config || !config.retryCount) {
      config.retryCount = 0;
    }

    if (config.retryCount < MAX_RETRIES) {
      config.retryCount += 1;
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY));
      return apiClient(config);
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
  getTemplates: () => apiClient.get("/api/workflows/templates"),
  getTemplate: (templateId: string) =>
    apiClient.get(`/api/workflows/templates/${templateId}`),
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
