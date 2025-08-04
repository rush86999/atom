// LanceDB Configuration
export const LANCEDB_DATA_PATH =
  process.env.LANCEDB_DATA_PATH || '/data/lancedb'; // Default path
export const LANCEDB_EVENT_TABLE_NAME = 'events';

// OpenAI Configuration
export const OPENAI_API_KEY =
  process.env.OPENAI_API_KEY || 'your-default-openai-api-key'; // Ensure this is securely managed
export const OPENAI_EMBEDDING_MODEL = 'text-embedding-3-small';
export const OPENAI_EMBEDDING_DIMENSION = 1536;
export const DEFAULT_OPENAI_MODEL = 'gpt-3.5-turbo'; // Or your preferred default chat model

// Hasura Configuration
export const HASURA_GRAPHQL_URL =
  process.env.HASURA_GRAPHQL_URL || 'http://localhost:8080/v1/graphql'; // Replace with your actual Hasura URL
export const HASURA_ADMIN_SECRET =
  process.env.HASURA_ADMIN_SECRET || 'your-hasura-admin-secret'; // Ensure this is securely managed

// Service Configuration
export const DEFAULT_SEARCH_LIMIT = 10;
