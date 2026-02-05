/**
 * Agent Types
 * Type definitions for agents, chat messages, and agent interactions
 */

import { DateTime } from 'luxon';

// Agent maturity levels
export enum AgentMaturity {
  STUDENT = 'STUDENT',
  INTERN = 'INTERN',
  SUPERVISED = 'SUPERVISED',
  AUTONOMOUS = 'AUTONOMOUS',
}

// Agent status
export enum AgentStatus {
  ONLINE = 'online',
  OFFLINE = 'offline',
  BUSY = 'busy',
  MAINTENANCE = 'maintenance',
}

// Agent capability
export interface AgentCapability {
  name: string;
  description: string;
  enabled: boolean;
}

// Agent registry
export interface Agent {
  id: string;
  name: string;
  description: string;
  maturity_level: AgentMaturity;
  status: AgentStatus;
  system_prompt: string;
  capabilities: AgentCapability[];
  created_at: string;
  updated_at: string;
  version: number;
  confidence_score?: number;
  last_execution_at?: string;
}

// Chat message
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  agent_id?: string;
  agent_name?: string;
  is_streaming?: boolean;
  governance_badge?: {
    maturity: AgentMaturity;
    confidence: number;
    requires_supervision: boolean;
  };
  metadata?: {
    canvas_presented?: boolean;
    canvas_id?: string;
    episode_references?: string[];
    tool_calls?: string[];
  };
}

// Chat session
export interface ChatSession {
  id: string;
  agent_id: string;
  agent_name: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

// Agent list filters
export interface AgentFilters {
  maturity?: AgentMaturity | 'ALL';
  status?: AgentStatus | 'ALL';
  capability?: string;
  search_query?: string;
  sort_by?: 'name' | 'created_at' | 'last_execution' | 'confidence';
  sort_order?: 'asc' | 'desc';
}

// Streaming chunk
export interface StreamingChunk {
  token: string;
  is_complete: boolean;
  metadata?: {
    canvas_presented?: boolean;
    canvas_id?: string;
    governance_badge?: {
      maturity: AgentMaturity;
      confidence: number;
    };
  };
}

// Episode context
export interface EpisodeContext {
  id: string;
  title: string;
  summary: string;
  created_at: string;
  relevance_score: number;
  canvas_context?: {
    canvas_id: string;
    canvas_type: string;
    action: string;
  };
  feedback_context?: {
    average_rating: number;
    feedback_count: number;
  };
}
