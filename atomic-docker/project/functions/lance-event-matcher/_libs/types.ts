// Structure of event records as stored in/retrieved from LanceDB
export interface EventRecord {
  id: string; // Primary key: eventId#calendarId
  userId: string;
  vector: number[];
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

// Response body for the search endpoint
export interface SearchResponse {
  success: boolean;
  data: EventRecord[];
  message?: string;
}

// For OpenAI client
export interface OpenAIInterface {
    apiKey: string;
}

// Schema for LanceDB, mirrors EventRecord but used for table interaction
export interface EventSchema {
    id: string;
    userId: string;
    vector: number[];
    start_date: string;
    end_date: string;
    raw_event_text?: string;
}
