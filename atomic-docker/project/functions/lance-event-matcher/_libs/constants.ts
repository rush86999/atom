// LanceDB Configuration
export const LANCEDB_DATA_PATH = process.env.LANCEDB_DATA_PATH || '/data/lancedb'; // Default path
export const LANCEDB_EVENT_TABLE_NAME = 'events';

// OpenAI Configuration
export const OPENAI_API_KEY = process.env.OPENAI_API_KEY || 'your-default-openai-api-key';
export const OPENAI_EMBEDDING_MODEL = 'text-embedding-3-small';
export const OPENAI_EMBEDDING_DIMENSION = 1536;

// Service Configuration
export const DEFAULT_SEARCH_LIMIT = 10;
