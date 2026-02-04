/**
 * ATOM Constants - Shared configuration values
 */

// API Configuration
export const API_CONFIG = {
  TIMEOUT: 10000,
  RETRY_ATTEMPTS: 3,
  RETRY_DELAY: 1000,
} as const;

// Backend Service URLs
export const PYTHON_API_SERVICE_BASE_URL = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';
export const NEXT_PUBLIC_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

// Environment
export const ENVIRONMENT = process.env.NODE_ENV || 'development';
export const IS_DEVELOPMENT = ENVIRONMENT === 'development';
export const IS_PRODUCTION = ENVIRONMENT === 'production';

// Authentication
export const AUTH_CONFIG = {
  TOKEN_KEY: 'atom_auth_token',
  REFRESH_TOKEN_KEY: 'atom_refresh_token',
  TOKEN_EXPIRY_BUFFER: 5 * 60 * 1000, // 5 minutes
} as const;

// Database
export const DB_CONFIG = {
  LANCEDB_PATH: process.env.LANCEDB_PATH || './data/lancedb',
  SQLITE_PATH: process.env.SQLITE_PATH || './data/atom.db',
} as const;

// Feature Flags
export const FEATURES = {
  ENABLE_LANCEDB: process.env.ENABLE_LANCEDB === 'true',
  ENABLE_OAUTH: process.env.ENABLE_OAUTH !== 'false',
  ENABLE_WORKFLOWS: process.env.ENABLE_WORKFLOWS !== 'false',
  ENABLE_VOICE: process.env.ENABLE_VOICE === 'true',
} as const;

// Logging
export const LOG_LEVELS = {
  ERROR: 'error',
  WARN: 'warn',
  INFO: 'info',
  DEBUG: 'debug',
} as const;

export const DEFAULT_LOG_LEVEL = process.env.LOG_LEVEL || LOG_LEVELS.INFO;

// Service Health
export const HEALTH_CHECK_INTERVAL = 30000; // 30 seconds
export const HEALTH_CHECK_TIMEOUT = 5000; // 5 seconds

// Rate Limiting
export const RATE_LIMITS = {
  API_REQUESTS_PER_MINUTE: 60,
  OAUTH_REQUESTS_PER_HOUR: 10,
  SEARCH_REQUESTS_PER_MINUTE: 30,
} as const;