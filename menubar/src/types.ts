export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
}

export interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface AgentSummary {
  id: string;
  name: string;
  maturity_level: string;
  status: string;
  last_execution: string | null;
  execution_count: number;
}

export interface CanvasSummary {
  id: string;
  canvas_type: string;
  created_at: string;
  agent_id: string | null;
  agent_name: string | null;
}

export interface QuickChatRequest {
  message: string;
  agent_id?: string;
  context?: Record<string, unknown>;
}

export interface QuickChatResponse {
  success: boolean;
  response?: string;
  execution_id?: string;
  agent_id?: string;
  error?: string;
}

export interface ConnectionStatus {
  status: "connected" | "disconnected" | "error";
  device_id?: string;
  last_seen?: string;
  server_time: string;
}
