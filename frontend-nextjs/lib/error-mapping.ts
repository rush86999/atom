/**
 * User-Friendly Error Message Mapping Utilities
 *
 * Transforms technical error messages into actionable guidance for end users.
 * Prevents exposure of internal error codes, stack traces, and network details.
 *
 * @module error-mapping
 */

/**
 * Error severity levels for UI display and logging
 */
export type ErrorSeverity = 'info' | 'warning' | 'error';

/**
 * User-friendly error action suggestions
 */
export type ErrorAction = 'Log in again' | 'Retry' | 'Check connection' | 'Wait a moment' | null;

/**
 * Extended error interface with user-friendly properties
 */
export interface UserFriendlyError extends Error {
  /** User-friendly error message (no technical jargon) */
  userMessage?: string;
  /** Suggested action for user to resolve the error */
  userAction?: ErrorAction;
  /** Severity level for UI display */
  severity?: ErrorSeverity;
  /** Whether error should trigger automatic retry */
  isRetryable?: boolean;
  /** Original technical error (for debugging) */
  technical?: any;
}

/**
 * Maps technical errors to user-friendly messages
 *
 * Transforms network errors, HTTP status codes, and system errors into
 * actionable, non-technical messages that end users can understand.
 *
 * @param error - Error object from axios, fetch, or network layer
 * @returns User-friendly error message without technical jargon
 *
 * @example
 * ```typescript
 * try {
 *   await apiClient.get('/api/agents');
 * } catch (error) {
 *   const message = getUserFriendlyErrorMessage(error);
 *   // "Unable to connect to the server. Please check your internet connection."
 *   // NOT: "ENOTFOUND getaddrinfo failed"
 * }
 * ```
 */
export function getUserFriendlyErrorMessage(error: any): string {
  // Network errors (DNS, connection refused, etc.)
  if (error.code === 'ENOTFOUND' || error.code === 'ECONNREFUSED') {
    return 'Unable to connect to the server. Please check your internet connection.';
  }

  if (error.code === 'ETIMEDOUT' || error.code === 'ECONNABORTED') {
    return 'Request timed out. Please try again.';
  }

  if (error.code === 'ECONNRESET') {
    return 'Connection was interrupted. Please check your internet connection and try again.';
  }

  // HTTP 4xx errors
  if (error.response?.status === 400) {
    return 'Invalid request. Please check your input and try again.';
  }

  if (error.response?.status === 401) {
    return 'Your session has expired. Please log in again.';
  }

  if (error.response?.status === 403) {
    return 'You do not have permission to perform this action. Please contact your administrator.';
  }

  if (error.response?.status === 404) {
    return 'The requested resource was not found. Please check the URL or contact support.';
  }

  if (error.response?.status === 408) {
    return 'Request timed out. Please try again.';
  }

  if (error.response?.status === 409) {
    return 'This resource is currently in use. Please refresh and try again.';
  }

  if (error.response?.status === 422) {
    return 'Invalid input. Please check your data and try again.';
  }

  if (error.response?.status === 429) {
    return 'Too many requests. Please wait before trying again.';
  }

  // HTTP 5xx errors (server errors)
  if (error.response?.status === 500) {
    return 'Something went wrong on our end. Our team has been notified. Please try again later.';
  }

  if (error.response?.status === 502) {
    return 'Service temporarily unavailable. Please try again in a few moments.';
  }

  if (error.response?.status === 503) {
    return 'Our service is temporarily unavailable. Please try again in a few moments.';
  }

  if (error.response?.status === 504) {
    return 'The request took too long to process. Please try again.';
  }

  // Generic fallback (no technical details)
  return 'An unexpected error occurred. Please try again.';
}

/**
 * Returns suggested user action for error recovery
 *
 * Provides actionable guidance based on error type. Actions are
 * brief and user-friendly (e.g., "Log in again" instead of "Re-authenticate").
 *
 * @param error - Error object from axios, fetch, or network layer
 * @returns Action suggestion string or null if no specific action
 *
 * @example
 * ```typescript
 * const action = getErrorAction(error);
 * if (action) {
 *   // Show action button: "Log in again"
 * }
 * ```
 */
export function getErrorAction(error: any): ErrorAction {
  // Authentication errors
  if (error.response?.status === 401) {
    return 'Log in again';
  }

  // Server errors (retryable)
  if (error.response?.status >= 500) {
    return 'Retry';
  }

  // Gateway timeout (retryable)
  if (error.response?.status === 504) {
    return 'Retry';
  }

  // Rate limiting (wait)
  if (error.response?.status === 429) {
    return 'Wait a moment';
  }

  // Request timeout (retryable)
  if (error.response?.status === 408) {
    return 'Retry';
  }

  // Network errors (check connection)
  if (error.code === 'ENOTFOUND' ||
      error.code === 'ECONNREFUSED' ||
      error.code === 'ECONNRESET') {
    return 'Check connection';
  }

  // Timeout errors (retryable)
  if (error.code === 'ETIMEDOUT' || error.code === 'ECONNABORTED') {
    return 'Retry';
  }

  // No specific action for other errors
  return null;
}

/**
 * Maps error to severity level for UI display
 *
 * Severity levels determine visual presentation:
 * - 'info': Blue/neutral, informational messages
 * - 'warning': Yellow/orange, client errors (4xx)
 * - 'error': Red, server errors (5xx) and network failures
 *
 * @param error - Error object from axios, fetch, or network layer
 * @returns Severity level ('info' | 'warning' | 'error')
 *
 * @example
 * ```typescript
 * const severity = getErrorSeverity(error);
 * // Use for toast notification styling
 * showToast({ severity, message: getUserFriendlyErrorMessage(error) });
 * ```
 */
export function getErrorSeverity(error: any): ErrorSeverity {
  // Client errors (4xx) -> warning (except 429 rate limit -> error)
  if (error.response?.status >= 400 && error.response?.status < 500) {
    if (error.response?.status === 429) {
      return 'error'; // Rate limiting is severe
    }
    return 'warning';
  }

  // Server errors (5xx) -> error
  if (error.response?.status >= 500) {
    return 'error';
  }

  // Network errors -> error
  if (error.code === 'ENOTFOUND' ||
      error.code === 'ECONNREFUSED' ||
      error.code === 'ETIMEDOUT' ||
      error.code === 'ECONNABORTED' ||
      error.code === 'ECONNRESET') {
    return 'error';
  }

  // Default -> info
  return 'info';
}

/**
 * Determines if error should trigger automatic retry
 *
 * Returns true for transient failures (5xx, network errors, timeouts).
 * Returns false for permanent errors (4xx except 408).
 *
 * Use this to decide whether to:
 * - Automatically retry with exponential backoff
 * - Show retry button to user
 * - Show error without retry option
 *
 * @param error - Error object from axios, fetch, or network layer
 * @returns True if error is retryable, false otherwise
 *
 * @example
 * ```typescript
 * if (isRetryableError(error)) {
 *   // Automatic retry with exponential backoff
 *   await retryWithBackoff(request);
 * } else {
 *   // Show error to user (no retry)
 *   showError(error);
 * }
 * ```
 */
export function isRetryableError(error: any): boolean {
  // Server errors (5xx) -> retryable
  if (error.response?.status >= 500) {
    return true;
  }

  // Request timeout (408) -> retryable
  if (error.response?.status === 408) {
    return true;
  }

  // Network errors -> retryable
  if (error.code === 'ECONNABORTED' ||
      error.code === 'ETIMEDOUT' ||
      error.code === 'ECONNRESET' ||
      error.code === 'ENOTFOUND') {
    return true;
  }

  // Client errors (4xx) -> not retryable (permanent)
  return false;
}

/**
 * Enhances error object with user-friendly properties
 *
 * Adds userMessage, userAction, severity, and isRetryable properties
 * to error objects while preserving original technical error.
 *
 * @param error - Error object from axios, fetch, or network layer
 * @returns Enhanced error with user-friendly properties
 *
 * @example
 * ```typescript
 * try {
 *   await apiClient.get('/api/agents');
 * } catch (error) {
 *   const enhancedError = enhanceError(error);
 *   console.log(enhancedError.userMessage); // User-friendly message
 *   console.log(enhancedError.technical); // Original error (debugging)
 * }
 * ```
 */
export function enhanceError(error: any): UserFriendlyError {
  const enhanced = error as UserFriendlyError;

  // Add user-friendly properties
  enhanced.userMessage = getUserFriendlyErrorMessage(error);
  enhanced.userAction = getErrorAction(error);
  enhanced.severity = getErrorSeverity(error);
  enhanced.isRetryable = isRetryableError(error);

  // Preserve original error for debugging
  enhanced.technical = {
    code: error.code,
    message: error.message,
    response: error.response ? {
      status: error.response.status,
      data: error.response.data,
      statusText: error.response.statusText,
    } : undefined,
    config: error.config,
  };

  return enhanced;
}
