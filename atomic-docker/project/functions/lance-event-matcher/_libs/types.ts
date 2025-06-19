// Structure of event records as stored in/retrieved from LanceDB
export interface EventRecord {
  id: string; // Primary key: eventId#calendarId
  userId: string;
  vector: number[]; // Should be Float32Array or number[] depending on lancedb library usage
  start_date: string; // ISO 8601 format
  end_date: string; // ISO 8601 format
  raw_event_text?: string; // Optional: summary:description
  // Potentially other fields like eventType if added by AI agent
  eventType?: string;
}

// Request body for the search endpoint
export interface SearchRequest {
  userId: string;
  searchText: string;
  startDate?: string; // ISO 8601 format
  endDate?: string; // ISO 8601 format
  limit?: number;
}

// --- Generic Skill Error and Response Types ---
// (Mirrors the structure from project/functions/atom-agent/types.ts for consistency)
export interface SkillError {
  code: string;
  message: string;
  details?: any;
}

export interface LanceEventMatcherResponse<T> {
  ok: boolean; // Changed from 'success' to 'ok' for consistency
  data?: T;
  error?: SkillError;
}

// Old SearchResponse, to be replaced by LanceEventMatcherResponse<AIProcessedEvent[]>
/*
export interface SearchResponse {
  success: boolean;
  data: EventRecord[]; // Note: This was EventRecord[], the handler now returns AIProcessedEvent[]
  message?: string;
}
*/

// For OpenAI client
export interface OpenAIInterface {
    apiKey: string;
}

// Schema for LanceDB, mirrors EventRecord but used for table interaction
export interface EventSchema {
    id: string;
    userId: string;
  vector: number[]; // Should be Float32Array or number[]
    start_date: string;
    end_date: string;
    raw_event_text?: string;
}

// Minimal representation of a user category
export interface CategoryType {
  id: string;
  name: string;
  description?: string; // Optional, but could be useful for AI
}

// Structure for events after processing by the AI
export interface AIProcessedEvent {
  eventId: string;
  assignedCategoryId: string;
  relevanceScore: number; // A score from 0.0 to 1.0
  // Potentially other fields added by AI, like rationale or suggested actions
  rationale?: string;
}

// Structure for the output of the AI Query Enhancer
export interface AIQueryEnhancementResult {
  refinedQueryText: string;
  suggestedCategoryIds?: string[];
  identifiedDateRange?: {
    start?: string; // YYYY-MM-DD
    end?: string;   // YYYY-MM-DD
  };
}
