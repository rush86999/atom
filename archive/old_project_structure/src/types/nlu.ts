/**
 * Atom Project - NLU Types and Interfaces
 * Shared TypeScript Definitions for NLU Agents and Chat System

 * CONVERTED FROM JS - Week 1
 * Priority: 🔴 HIGH
 * Objective: Convert JavaScript to TypeScript with proper types
 * Timeline: 8 hours conversion + 4 hours testing

 * This file provides TypeScript definitions for the NLU system,
 * chat interface, and agent communication with proper type safety.
 */

// ============================================================================
// NLU Agent Types
// ============================================================================

export interface NLUIntent {
  name: string;
  confidence: number;
  entities?: NLUEntity[];
  metadata?: {
    agent?: string;
    processing_time?: number;
    alternative_intents?: NLUIntent[];
    reasoning?: string;
  };
}

export interface NLUEntity {
  text: string;
  type: string;
  confidence: number;
  start: number;
  end: number;
  metadata?: Record<string, any>;
}

export interface NLUContext {
  conversation_id: string;
  user_id: string;
  message_count: number;
  previous_intents: NLUIntent[];
  user_preferences?: Record<string, any>;
  session_data?: Record<string, any>;
  integration_context?: Record<string, any>;
}

export interface NLUSkill {
  name: string;
  description: string;
  enabled: boolean;
  integrations: string[];
  parameters: Record<string, any>;
}

export interface NLUAgent {
  id: string;
  name: string;
  type: 'analytical' | 'creative' | 'practical' | 'social_media' | 'trading' | 'workflow' | 'specialized';
  capabilities: string[];
  default_temperature: number;
  default_model: string;
  integrations: string[];
  skills: NLUSkill[];
  status: 'active' | 'inactive' | 'error';
}

// ============================================================================
// Chat Message Types
// ============================================================================

export type MessageSender = 'user' | 'ai' | 'system';
export type MessageStatus = 'sending' | 'sent' | 'delivered' | 'read' | 'error';

export interface ChatMessage {
  id: string;
  content: string;
  sender: MessageSender;
  timestamp: Date;
  status: MessageStatus;
  metadata?: MessageMetadata;
  userId?: string;
  agentId?: string;
  conversationId?: string;
}

export interface MessageMetadata {
  intent?: string;
  entities?: NLUEntity[];
  agent?: string;
  confidence?: number;
  processing_time?: number;
  error?: string;
  edited?: boolean;
  edited_at?: Date;
  reply_to?: string;
  attachments?: MessageAttachment[];
  reactions?: MessageReaction[];
  integrations?: IntegrationMetadata[];
}

export interface MessageAttachment {
  id: string;
  type: 'image' | 'file' | 'link' | 'code' | 'workflow';
  url: string;
  name: string;
  size?: number;
  mime_type?: string;
  metadata?: Record<string, any>;
}

export interface MessageReaction {
  emoji: string;
  count: number;
  users: string[];
}

export interface IntegrationMetadata {
  platform: string;
  action?: string;
  data?: Record<string, any>;
  status?: 'pending' | 'completed' | 'error';
}

// ============================================================================
// Chat State Types
// ============================================================================

export interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  isTyping: boolean;
  isConnected: boolean;
  currentUser: ChatUser;
  aiAgent: ChatAgent;
  conversationId: string;
  context?: NLUContext;
}

export interface ChatUser {
  id: string;
  name: string;
  avatar?: string;
  email?: string;
  preferences?: UserPreferences;
}

export interface ChatAgent {
  id: string;
  name: string;
  avatar?: string;
  status: AgentStatus;
  capabilities: string[];
  last_seen?: Date;
  active_integrations: string[];
}

export type AgentStatus = 'online' | 'offline' | 'busy' | 'away' | 'error';

export interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  notifications: boolean;
  sound: boolean;
  auto_reply?: boolean;
  language: string;
  timezone: string;
  integrations: Record<string, boolean>;
  agent_preferences: Record<string, any>;
}

// ============================================================================
// WebSocket Types
// ============================================================================

export interface WebSocketMessage {
  type: WebSocketMessageType;
  data?: any;
  message?: ChatMessage;
  userId?: string;
  agentId?: string;
  messageId?: string;
  timestamp?: string;
}

export type WebSocketMessageType = 
  | 'message'
  | 'typing_indicator'
  | 'agent_status'
  | 'history_request'
  | 'history_response'
  | 'heartbeat'
  | 'heartbeat_response'
  | 'connection_status'
  | 'message_delivered'
  | 'message_read'
  | 'error';

export interface TypingIndicator {
  userId: string;
  agentId?: string;
  isTyping: boolean;
  timestamp: Date;
}

export interface ConnectionStatus {
  connected: boolean;
  reconnecting: boolean;
  lastConnected?: Date;
  lastDisconnected?: Date;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
}

// ============================================================================
// NLU Processing Types
// ============================================================================

export interface NLUResponse {
  intent: NLUIntent;
  entities: NLUEntity[];
  agent: string;
  response: string;
  confidence: number;
  processing_time: number;
  metadata?: NLUResponseMetadata;
}

export interface NLUResponseMetadata {
  alternative_responses?: string[];
  reasoning?: string;
  context_used?: boolean;
  memory_retrieved?: boolean;
  skills_used?: string[];
  integrations_triggered?: string[];
  workflow_created?: boolean;
}

export interface NLUProcessingRequest {
  content: string;
  context: NLUContext;
  preferences: UserPreferences;
  integrations: string[];
  skills: NLUSkill[];
}

export interface NLUProcessingResult {
  success: boolean;
  response?: NLUResponse;
  error?: string;
  processing_time: number;
  agent_used: string;
  skills_used: string[];
}

// ============================================================================
// LLM Configuration Types
// ============================================================================

export interface LLMConfig {
  model: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  frequency_penalty: number;
  presence_penalty: number;
  stop_sequences?: string[];
  system_prompt?: string;
}

export interface LLMAgentConfig {
  id: string;
  name: string;
  type: string;
  llm_config: LLMConfig;
  system_prompt: string;
  examples: LLMExample[];
  tools: LLMTool[];
}

export interface LLMExample {
  input: string;
  output: string;
  metadata?: Record<string, any>;
}

export interface LLMTool {
  name: string;
  description: string;
  parameters: Record<string, any>;
  type: 'function' | 'api' | 'integration';
  integration_id?: string;
}

// ============================================================================
// Integration Types
// ============================================================================

export interface IntegrationConfig {
  id: string;
  name: string;
  platform: string;
  type: IntegrationType;
  enabled: boolean;
  credentials?: IntegrationCredentials;
  settings: Record<string, any>;
  webhook_url?: string;
  capabilities: string[];
}

export type IntegrationType = 
  | 'oauth'
  | 'api_key'
  | 'webhook'
  | 'basic_auth'
  | 'custom';

export interface IntegrationCredentials {
  client_id?: string;
  client_secret?: string;
  access_token?: string;
  refresh_token?: string;
  api_key?: string;
  username?: string;
  password?: string;
  webhook_secret?: string;
}

export interface IntegrationAction {
  id: string;
  name: string;
  description: string;
  type: ActionType;
  parameters: Record<string, any>;
  required_integrations: string[];
}

export type ActionType = 
  | 'create'
  | 'read'
  | 'update'
  | 'delete'
  | 'search'
  | 'send'
  | 'analyze'
  | 'workflow';

// ============================================================================
// Memory System Types
// ============================================================================

export interface MemoryConfig {
  enabled: boolean;
  provider: 'lancedb' | 'postgres' | 'redis';
  max_conversation_length: number;
  context_window_size: number;
  embedding_model: string;
  similarity_threshold: number;
}

export interface MemoryEntry {
  id: string;
  type: 'message' | 'context' | 'preference' | 'integration';
  content: string;
  embedding?: number[];
  metadata: Record<string, any>;
  created_at: Date;
  updated_at: Date;
  user_id: string;
  conversation_id?: string;
}

export interface MemoryQuery {
  query: string;
  type?: 'semantic' | 'exact' | 'fuzzy';
  limit?: number;
  threshold?: number;
  filters?: Record<string, any>;
}

export interface MemoryResult {
  entries: MemoryEntry[];
  total: number;
  query_time: number;
  similarity_scores?: number[];
}

// ============================================================================
// Workflow Types
// ============================================================================

export interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  steps: WorkflowStep[];
  triggers: WorkflowTrigger[];
  variables: Record<string, any>;
  status: 'active' | 'inactive' | 'error';
}

export interface WorkflowStep {
  id: string;
  type: StepType;
  action: string;
  parameters: Record<string, any>;
  conditions?: Record<string, any>;
  on_success?: string;
  on_failure?: string;
  timeout?: number;
}

export type StepType = 
  | 'ai_processing'
  | 'integration_action'
  | 'condition'
  | 'delay'
  | 'notification'
  | 'data_processing';

export interface WorkflowTrigger {
  id: string;
  type: TriggerType;
  conditions: Record<string, any>;
  parameters: Record<string, any>;
}

export type TriggerType = 
  | 'message_received'
  | 'intent_detected'
  | 'time_based'
  | 'integration_event'
  | 'manual';

// ============================================================================
// Application Configuration Types
// ============================================================================

export interface AppConfig {
  appType: 'web' | 'desktop' | 'mobile';
  version: string;
  environment: 'development' | 'staging' | 'production';
  user?: ChatUser;
  aiAgent?: ChatAgent;
  websocket?: WebSocketConfig;
  integrations?: IntegrationConfig[];
  nlu?: NLUConfig;
  memory?: MemoryConfig;
  desktop?: DesktopConfig;
  mobile?: MobileConfig;
}

export interface WebSocketConfig {
  url: string;
  protocols?: string[];
  reconnect_attempts?: number;
  reconnect_delay?: number;
  heartbeat_interval?: number;
  timeout?: number;
}

export interface DesktopConfig {
  auto_start: boolean;
  minimize_to_tray: boolean;
  show_notifications: boolean;
  system_integration: boolean;
  file_access: boolean;
  deep_links: boolean;
}

export interface MobileConfig {
  push_notifications: boolean;
  background_sync: boolean;
  offline_mode: boolean;
  biometric_auth: boolean;
  accessibility: boolean;
}

// ============================================================================
// API Response Types
// ============================================================================

export interface APIResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
  metadata?: Record<string, any>;
  timestamp: string;
}

export interface PaginatedResponse<T = any> extends APIResponse<T[]> {
  pagination: {
    page: number;
    limit: number;
    total: number;
    pages: number;
  };
}

// ============================================================================
// Error Types
// ============================================================================

export interface AtomError {
  code: string;
  message: string;
  details?: Record<string, any>;
  stack?: string;
  timestamp: Date;
  user_id?: string;
  request_id?: string;
}

export type ErrorCode = 
  | 'NETWORK_ERROR'
  | 'AUTHENTICATION_ERROR'
  | 'PERMISSION_ERROR'
  | 'VALIDATION_ERROR'
  | 'INTEGRATION_ERROR'
  | 'NLU_ERROR'
  | 'WEBSOCKET_ERROR'
  | 'MEMORY_ERROR'
  | 'WORKFLOW_ERROR'
  | 'UNKNOWN_ERROR';

// ============================================================================
// Constants and Defaults
// ============================================================================

export const DEFAULT_CONFIG = {
  LLM: {
    DEFAULT_MODEL_FOR_AGENTS: 'mixtral-8x7b-32768' as const,
    DEFAULT_MODEL_LEAD_SYNTHESIS: 'mixtral-8x7b-32768' as const,
    DEFAULT_TEMPERATURE_ANALYTICAL: 0.2,
    DEFAULT_TEMPERATURE_CREATIVE: 0.8,
    DEFAULT_TEMPERATURE_PRACTICAL: 0.4,
    DEFAULT_TEMPERATURE_LEAD_SYNTHESIS: 0.3,
  } as const,
  
  WEBSOCKET: {
    RECONNECT_ATTEMPTS: 5,
    RECONNECT_DELAY: 3000,
    HEARTBEAT_INTERVAL: 30000,
    CONNECTION_TIMEOUT: 10000,
    MESSAGE_TIMEOUT: 30000,
  } as const,
  
  CHAT: {
    MAX_MESSAGE_LENGTH: 10000,
    MAX_CONVERSATION_LENGTH: 1000,
    TYPING_INDICATOR_TIMEOUT: 3000,
    MESSAGE_HISTORY_LIMIT: 50,
  } as const,
  
  MEMORY: {
    MAX_CONVERSATION_LENGTH: 1000,
    CONTEXT_WINDOW_SIZE: 4096,
    SIMILARITY_THRESHOLD: 0.7,
    EMBEDDING_MODEL: 'text-embedding-ada-002',
  } as const,
} as const;

// ============================================================================
// Utility Types
// ============================================================================

export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

export type Optional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

export type RequiredKeys<T, K extends keyof T> = T & Required<Pick<T, K>>;

export type EventCallback<T = any> = (data: T) => void;
export type AsyncEventCallback<T = any> = (data: T) => Promise<void>;

export type Promisable<T> = T | Promise<T>;

export type Constructor<T = {}> = new (...args: any[]) => T;

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Safely parse JSON from LLM response with error handling
 */
export function safeParseJSON<T = any>(
  jsonString: string,
  agentName: string,
  task: string
): T | null {
  if (!jsonString) {
    console.warn(`[${agentName}] LLM response for task '${task}' was empty.`);
    return null;
  }
  
  try {
    return JSON.parse(jsonString);
  } catch (error) {
    console.error(
      `[${agentName}] Failed to parse JSON response for task '${task}'. Error: ${error}. Response: ${jsonString.substring(0, 200)}...`
    );
    return null;
  }
}

/**
 * Generate unique ID for messages
 */
export function generateMessageId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Generate unique ID for conversations
 */
export function generateConversationId(): string {
  return `conv-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Check if value is not null or undefined
 */
export function isNotNullish<T>(value: T | null | undefined): value is T {
  return value !== null && value !== undefined;
}

/**
 * Type guard to check if object has property
 */
export function hasProperty<T extends object>(
  obj: T,
  prop: string
): prop is keyof T {
  return Object.prototype.hasOwnProperty.call(obj, prop);
}

// Export all types
export type {
  // Core types that can be imported from other files
  NLUIntent,
  NLUEntity,
  NLUContext,
  NLUSkill,
  NLUAgent,
  ChatMessage,
  ChatState,
  ChatUser,
  ChatAgent,
  MessageMetadata,
  WebSocketMessage,
  NLUResponse,
  AppConfig,
  AtomError,
};