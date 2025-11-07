/**
 * ATOM Integration Constants
 * Shared constants for ATOM integration system
 */

// Integration Categories
export const INTEGRATION_CATEGORY_STORAGE = 'storage';
export const INTEGRATION_CATEGORY_COMMUNICATION = 'communication';
export const INTEGRATION_CATEGORY_PRODUCTIVITY = 'productivity';
export const INTEGRATION_CATEGORY_DEVELOPMENT = 'development';
export const INTEGRATION_CATEGORY_COLLABORATION = 'collaboration';
export const INTEGRATION_CATEGORY_MARKETING = 'marketing';
export const INTEGRATION_CATEGORY_CUSTOMER_SERVICE = 'customer_service';

// Integration Status
export const INTEGRATION_STATUS_COMPLETE = 'complete';
export const INTEGRATION_STATUS_IN_PROGRESS = 'in_progress';
export const INTEGRATION_STATUS_PLANNED = 'planned';

// Integration Platforms
export const INTEGRATION_PLATFORM_WEB = 'web';
export const INTEGRATION_PLATFORM_TAURI = 'tauri';
export const INTEGRATION_PLATFORM_NEXTJS = 'nextjs';

// OAuth Flow Types
export const OAUTH_FLOW_AUTH_CODE = 'oauth2';
export const OAUTH_FLOW_CLIENT_CREDENTIALS = 'client_credentials';
export const OAUTH_FLOW_IMPLICIT = 'implicit';

// HTTP Methods
export const HTTP_METHOD_GET = 'GET';
export const HTTP_METHOD_POST = 'POST';
export const HTTP_METHOD_PUT = 'PUT';
export const HTTP_METHOD_DELETE = 'DELETE';
export const HTTP_METHOD_PATCH = 'PATCH';

// API Response Status Codes
export const HTTP_STATUS_OK = 200;
export const HTTP_STATUS_CREATED = 201;
export const HTTP_STATUS_ACCEPTED = 202;
export const HTTP_STATUS_NO_CONTENT = 204;
export const HTTP_STATUS_BAD_REQUEST = 400;
export const HTTP_STATUS_UNAUTHORIZED = 401;
export const HTTP_STATUS_FORBIDDEN = 403;
export const HTTP_STATUS_NOT_FOUND = 404;
export const HTTP_STATUS_CONFLICT = 409;
export const HTTP_STATUS_UNPROCESSABLE_ENTITY = 422;
export const HTTP_STATUS_TOO_MANY_REQUESTS = 429;
export const HTTP_STATUS_INTERNAL_SERVER_ERROR = 500;
export const HTTP_STATUS_BAD_GATEWAY = 502;
export const HTTP_STATUS_SERVICE_UNAVAILABLE = 503;

// Error Types
export const ERROR_TYPE_NETWORK = 'network';
export const ERROR_TYPE_AUTHENTICATION = 'authentication';
export const ERROR_TYPE_AUTHORIZATION = 'authorization';
export const ERROR_TYPE_VALIDATION = 'validation';
export const ERROR_TYPE_RATE_LIMIT = 'rate_limit';
export const ERROR_TYPE_SERVER = 'server';
export const ERROR_TYPE_UNKNOWN = 'unknown';

// Pagination
export const DEFAULT_PAGE_SIZE = 50;
export const MAX_PAGE_SIZE = 1000;

// File Size Limits
export const MAX_FILE_SIZE_MB = 100;
export const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

// Time Constants
export const SECOND_IN_MS = 1000;
export const MINUTE_IN_MS = 60 * SECOND_IN_MS;
export const HOUR_IN_MS = 60 * MINUTE_IN_MS;
export const DAY_IN_MS = 24 * HOUR_IN_MS;
export const WEEK_IN_MS = 7 * DAY_IN_MS;
export const MONTH_IN_MS = 30 * DAY_IN_MS;

// Cache TTLs
export const CACHE_TTL_SHORT = 5 * MINUTE_IN_MS;
export const CACHE_TTL_MEDIUM = 30 * MINUTE_IN_MS;
export const CACHE_TTL_LONG = 2 * HOUR_IN_MS;

// Webhook Event Statuses
export const WEBHOOK_STATUS_PENDING = 'pending';
export const WEBHOOK_STATUS_DELIVERED = 'delivered';
export const WEBHOOK_STATUS_FAILED = 'failed';
export const WEBHOOK_STATUS_RETRYING = 'retrying';

// Workflow Types
export const WORKFLOW_TYPE_AUTOMATED = 'automated';
export const WORKFLOW_TYPE_MANUAL = 'manual';
export const WORKFLOW_TYPE_SCHEDULED = 'scheduled';
export const WORKFLOW_TYPE_TRIGGER_BASED = 'trigger_based';

// Trigger Types
export const TRIGGER_TYPE_WEBHOOK = 'webhook';
export const TRIGGER_TYPE_SCHEDULED = 'scheduled';
export const TRIGGER_TYPE_MANUAL = 'manual';
export const TRIGGER_TYPE_EVENT_BASED = 'event_based';

// Action Types
export const ACTION_TYPE_API_CALL = 'api_call';
export const ACTION_TYPE_EMAIL = 'email';
export const ACTION_TYPE_WEBHOOK = 'webhook';
export const ACTION_TYPE_DATABASE = 'database';
export const ACTION_TYPE_SCRIPT = 'script';
export const ACTION_TYPE_NOTIFICATION = 'notification';

// Data Types
export const DATA_TYPE_STRING = 'string';
export const DATA_TYPE_NUMBER = 'number';
export const DATA_TYPE_BOOLEAN = 'boolean';
export const DATA_TYPE_ARRAY = 'array';
export const DATA_TYPE_OBJECT = 'object';
export const DATA_TYPE_DATE = 'date';
export const DATA_TYPE_DATETIME = 'datetime';

// Sort Orders
export const SORT_ORDER_ASC = 'asc';
export const SORT_ORDER_DESC = 'desc';

// Date Formats
export const DATE_FORMAT_ISO = 'YYYY-MM-DD';
export const DATE_FORMAT_US = 'MM/DD/YYYY';
export const DATE_FORMAT_EU = 'DD/MM/YYYY';
export const DATETIME_FORMAT_ISO = 'YYYY-MM-DDTHH:mm:ssZ';
export const DATETIME_FORMAT_US = 'MM/DD/YYYY HH:mm:ss';
export const DATETIME_FORMAT_EU = 'DD/MM/YYYY HH:mm:ss';

// Validation Patterns
export const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const URL_PATTERN = /^https?:\/\/.+/;
export const PHONE_PATTERN = /^\+?[\d\s\-\(\)]+$/;

// Default Values
export const DEFAULT_TIMEOUT = 30000; // 30 seconds
export const DEFAULT_RETRY_ATTEMPTS = 3;
export const DEFAULT_RETRY_DELAY = 1000; // 1 second

// Environment Variables
export const ENV_VAR_PREFIX = 'ATOM_';
export const ENV_VAR_SUFFIX_API_KEY = '_API_KEY';
export const ENV_VAR_SUFFIX_CLIENT_ID = '_CLIENT_ID';
export const ENV_VAR_SUFFIX_CLIENT_SECRET = '_CLIENT_SECRET';
export const ENV_VAR_SUFFIX_WEBHOOK_SECRET = '_WEBHOOK_SECRET';