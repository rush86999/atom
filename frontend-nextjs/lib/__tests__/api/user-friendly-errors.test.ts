/**
 * User-Friendly Error Message Tests
 *
 * Validates that error messages are:
 * - User-friendly (no technical jargon)
 * - Actionable (specific guidance)
 * - Consistent (snapshot testing)
 */

import {
  getUserFriendlyErrorMessage,
  getErrorAction,
  getErrorSeverity,
  isRetryableError,
  enhanceError,
} from '../../error-mapping';

describe('getUserFriendlyErrorMessage', () => {
  describe('Network Error Messages', () => {
    it('ENOTFOUND returns friendly message without technical jargon', () => {
      const error: any = new Error('getaddrinfo ENOTFOUND');
      error.code = 'ENOTFOUND';

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatch(/unable to connect/i);
      expect(message).toMatch(/check your internet/i);
      expect(message).not.toMatch(/ENOTFOUND/i);
      expect(message).not.toMatch(/getaddrinfo/i);
    });

    it('ECONNREFUSED returns helpful guidance', () => {
      const error: any = new Error('connect ECONNREFUSED');
      error.code = 'ECONNREFUSED';

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatch(/unable to connect/i);
      expect(message).toMatch(/check your internet/i);
      expect(message).not.toMatch(/ECONNREFUSED/i);
    });

    it('ETIMEDOUT returns timeout explanation', () => {
      const error: any = new Error('timeout ETIMEDOUT');
      error.code = 'ETIMEDOUT';

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatch(/request timed out/i);
      expect(message).toMatch(/try again/i);
      expect(message).not.toMatch(/ETIMEDOUT/i);
    });

    it('ECONNABORTED returns timeout explanation', () => {
      const error: any = new Error('request aborted');
      error.code = 'ECONNABORTED';

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatch(/request timed out/i);
      expect(message).toMatch(/try again/i);
    });

    it('ECONNRESET returns connection interrupted message', () => {
      const error: any = new Error('socket hang up');
      error.code = 'ECONNRESET';

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatch(/connection was interrupted/i);
      expect(message).toMatch(/check your internet/i);
    });
  });

  describe('HTTP Error Messages', () => {
    it('401 mentions session expired and prompts login', () => {
      const error: any = {
        response: {
          status: 401,
          data: { error: 'Unauthorized' },
        },
      };

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatch(/your session has expired/i);
      expect(message).toMatch(/log in again/i);
      expect(message).not.toMatch(/401/i);
    });

    it('403 explains permission issue and suggests contact admin', () => {
      const error: any = {
        response: {
          status: 403,
          data: { error: 'Forbidden' },
        },
      };

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatch(/do not have permission/i);
      expect(message).toMatch(/contact your administrator/i);
      expect(message).not.toMatch(/403/i);
    });

    it('404 provides actionable guidance for resource not found', () => {
      const error: any = {
        response: {
          status: 404,
          data: { error: 'Not Found' },
        },
      };

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatch(/resource was not found/i);
      expect(message).toMatch(/check the url/i);
      expect(message).toMatch(/contact support/i);
      expect(message).not.toMatch(/404/i);
    });

    it('500 apologizes and mentions team notified', () => {
      const error: any = {
        response: {
          status: 500,
          data: { error: 'Internal Server Error' },
        },
      };

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatch(/something went wrong/i);
      expect(message).toMatch(/our end/i);
      expect(message).toMatch(/team has been notified/i);
      expect(message).toMatch(/try again later/i);
      expect(message).not.toMatch(/500/i);
      expect(message).not.toMatch(/internal server error/i);
    });

    it('503 explains temporary unavailability and suggests retry', () => {
      const error: any = {
        response: {
          status: 503,
          data: { error: 'Service Unavailable' },
        },
      };

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatch(/temporarily unavailable/i);
      expect(message).toMatch(/try again in a few moments/i);
      expect(message).not.toMatch(/503/i);
    });

    it('504 explains gateway timeout and suggests retry', () => {
      const error: any = {
        response: {
          status: 504,
          data: { error: 'Gateway Timeout' },
        },
      };

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatch(/took too long to process/i);
      expect(message).toMatch(/try again/i);
      expect(message).not.toMatch(/504/i);
    });

    it('429 explains rate limiting and suggests wait', () => {
      const error: any = {
        response: {
          status: 429,
          data: { error: 'Too Many Requests' },
        },
      };

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatch(/too many requests/i);
      expect(message).toMatch(/wait before trying again/i);
      expect(message).not.toMatch(/429/i);
    });

    it('408 explains request timeout and suggests retry', () => {
      const error: any = {
        response: {
          status: 408,
          data: { error: 'Request Timeout' },
        },
      };

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatch(/request timed out/i);
      expect(message).toMatch(/try again/i);
    });

    it('400 explains invalid request', () => {
      const error: any = {
        response: {
          status: 400,
          data: { error: 'Bad Request' },
        },
      };

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatch(/invalid request/i);
      expect(message).toMatch(/check your input/i);
    });

    it('422 explains invalid input', () => {
      const error: any = {
        response: {
          status: 422,
          data: { error: 'Unprocessable Entity' },
        },
      };

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatch(/invalid input/i);
      expect(message).toMatch(/check your data/i);
    });
  });

  describe('Unknown Errors', () => {
    it('returns default message for unknown error', () => {
      const error: any = new Error('Unknown error');

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toBe('An unexpected error occurred. Please try again.');
    });

    it('no undefined or null returns', () => {
      const error: any = new Error('Test error');

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toBeTruthy();
      expect(message).not.toBeNull();
      expect(message).not.toBeUndefined();
    });

    it('no technical error codes exposed', () => {
      const error: any = new Error('ECONNREFUSED 127.0.0.1:8000');
      error.code = 'ECONNREFUSED';

      const message = getUserFriendlyErrorMessage(error);

      expect(message).not.toMatch(/ECONNREFUSED/i);
      expect(message).not.toMatch(/127\.0\.0\.1/i);
      expect(message).not.toMatch(/:8000/i);
    });
  });

  describe('Snapshot Testing', () => {
    it('matches snapshot for network errors', () => {
      const error: any = new Error('getaddrinfo ENOTFOUND');
      error.code = 'ENOTFOUND';

      const message = getUserFriendlyErrorMessage(error);

      expect(message).toMatchSnapshot();
    });

    it('matches snapshot for HTTP errors', () => {
      const error401: any = { response: { status: 401 } };
      const error500: any = { response: { status: 500 } };

      expect(getUserFriendlyErrorMessage(error401)).toMatchSnapshot();
      expect(getUserFriendlyErrorMessage(error500)).toMatchSnapshot();
    });
  });
});

describe('getErrorAction', () => {
  describe('HTTP Error Actions', () => {
    it('401 returns "Log in again"', () => {
      const error: any = { response: { status: 401 } };

      const action = getErrorAction(error);

      expect(action).toBe('Log in again');
    });

    it('5xx returns "Retry"', () => {
      const error500: any = { response: { status: 500 } };
      const error503: any = { response: { status: 503 } };

      expect(getErrorAction(error500)).toBe('Retry');
      expect(getErrorAction(error503)).toBe('Retry');
    });

    it('504 returns "Retry"', () => {
      const error: any = { response: { status: 504 } };

      const action = getErrorAction(error);

      expect(action).toBe('Retry');
    });

    it('408 returns "Retry"', () => {
      const error: any = { response: { status: 408 } };

      const action = getErrorAction(error);

      expect(action).toBe('Retry');
    });

    it('429 returns "Wait a moment"', () => {
      const error: any = { response: { status: 429 } };

      const action = getErrorAction(error);

      expect(action).toBe('Wait a moment');
    });

    it('403 returns null (no specific action)', () => {
      const error: any = { response: { status: 403 } };

      const action = getErrorAction(error);

      expect(action).toBeNull();
    });

    it('404 returns null (no specific action)', () => {
      const error: any = { response: { status: 404 } };

      const action = getErrorAction(error);

      expect(action).toBeNull();
    });
  });

  describe('Network Error Actions', () => {
    it('ENOTFOUND returns "Check connection"', () => {
      const error: any = new Error('Network error');
      error.code = 'ENOTFOUND';

      const action = getErrorAction(error);

      expect(action).toBe('Check connection');
    });

    it('ECONNREFUSED returns "Check connection"', () => {
      const error: any = new Error('Connection refused');
      error.code = 'ECONNREFUSED';

      const action = getErrorAction(error);

      expect(action).toBe('Check connection');
    });

    it('ECONNRESET returns "Check connection"', () => {
      const error: any = new Error('Connection reset');
      error.code = 'ECONNRESET';

      const action = getErrorAction(error);

      expect(action).toBe('Check connection');
    });

    it('ETIMEDOUT returns "Retry"', () => {
      const error: any = new Error('Timeout');
      error.code = 'ETIMEDOUT';

      const action = getErrorAction(error);

      expect(action).toBe('Retry');
    });

    it('ECONNABORTED returns "Retry"', () => {
      const error: any = new Error('Request aborted');
      error.code = 'ECONNABORTED';

      const action = getErrorAction(error);

      expect(action).toBe('Retry');
    });
  });

  describe('Other Errors', () => {
    it('returns null for errors without specific action', () => {
      const error: any = { response: { status: 403 } };

      const action = getErrorAction(error);

      expect(action).toBeNull();
    });
  });
});

describe('getErrorSeverity', () => {
  describe('HTTP Error Severity', () => {
    it('4xx (except 429) returns warning', () => {
      const error400: any = { response: { status: 400 } };
      const error401: any = { response: { status: 401 } };
      const error403: any = { response: { status: 403 } };
      const error404: any = { response: { status: 404 } };

      expect(getErrorSeverity(error400)).toBe('warning');
      expect(getErrorSeverity(error401)).toBe('warning');
      expect(getErrorSeverity(error403)).toBe('warning');
      expect(getErrorSeverity(error404)).toBe('warning');
    });

    it('429 returns error (rate limiting is severe)', () => {
      const error: any = { response: { status: 429 } };

      const severity = getErrorSeverity(error);

      expect(severity).toBe('error');
    });

    it('5xx returns error', () => {
      const error500: any = { response: { status: 500 } };
      const error503: any = { response: { status: 503 } };
      const error504: any = { response: { status: 504 } };

      expect(getErrorSeverity(error500)).toBe('error');
      expect(getErrorSeverity(error503)).toBe('error');
      expect(getErrorSeverity(error504)).toBe('error');
    });
  });

  describe('Network Error Severity', () => {
    it('network errors return error', () => {
      const errorENOTFOUND: any = { code: 'ENOTFOUND' };
      const errorECONNREFUSED: any = { code: 'ECONNREFUSED' };
      const errorETIMEDOUT: any = { code: 'ETIMEDOUT' };
      const errorECONNABORTED: any = { code: 'ECONNABORTED' };
      const errorECONNRESET: any = { code: 'ECONNRESET' };

      expect(getErrorSeverity(errorENOTFOUND)).toBe('error');
      expect(getErrorSeverity(errorECONNREFUSED)).toBe('error');
      expect(getErrorSeverity(errorETIMEDOUT)).toBe('error');
      expect(getErrorSeverity(errorECONNABORTED)).toBe('error');
      expect(getErrorSeverity(errorECONNRESET)).toBe('error');
    });
  });

  describe('Other Errors', () => {
    it('returns info for unknown errors', () => {
      const error: any = new Error('Unknown error');

      const severity = getErrorSeverity(error);

      expect(severity).toBe('info');
    });
  });
});

describe('isRetryableError', () => {
  describe('HTTP Retryable Errors', () => {
    it('5xx returns true', () => {
      const error500: any = { response: { status: 500 } };
      const error503: any = { response: { status: 503 } };
      const error504: any = { response: { status: 504 } };

      expect(isRetryableError(error500)).toBe(true);
      expect(isRetryableError(error503)).toBe(true);
      expect(isRetryableError(error504)).toBe(true);
    });

    it('408 returns true', () => {
      const error: any = { response: { status: 408 } };

      expect(isRetryableError(error)).toBe(true);
    });

    it('4xx (except 408) returns false', () => {
      const error400: any = { response: { status: 400 } };
      const error401: any = { response: { status: 401 } };
      const error403: any = { response: { status: 403 } };
      const error404: any = { response: { status: 404 } };
      const error422: any = { response: { status: 422 } };

      expect(isRetryableError(error400)).toBe(false);
      expect(isRetryableError(error401)).toBe(false);
      expect(isRetryableError(error403)).toBe(false);
      expect(isRetryableError(error404)).toBe(false);
      expect(isRetryableError(error422)).toBe(false);
    });
  });

  describe('Network Retryable Errors', () => {
    it('ECONNABORTED returns true', () => {
      const error: any = { code: 'ECONNABORTED' };

      expect(isRetryableError(error)).toBe(true);
    });

    it('ETIMEDOUT returns true', () => {
      const error: any = { code: 'ETIMEDOUT' };

      expect(isRetryableError(error)).toBe(true);
    });

    it('ECONNRESET returns true', () => {
      const error: any = { code: 'ECONNRESET' };

      expect(isRetryableError(error)).toBe(true);
    });

    it('ENOTFOUND returns true', () => {
      const error: any = { code: 'ENOTFOUND' };

      expect(isRetryableError(error)).toBe(true);
    });
  });

  describe('Non-Retryable Errors', () => {
    it('returns false for unknown errors', () => {
      const error: any = new Error('Unknown error');

      expect(isRetryableError(error)).toBe(false);
    });
  });
});

describe('enhanceError', () => {
  it('adds user-friendly properties to error', () => {
    const originalError: any = {
      code: 'ENOTFOUND',
      message: 'getaddrinfo ENOTFOUND',
    };

    const enhanced = enhanceError(originalError);

    expect(enhanced.userMessage).toBeTruthy();
    expect(enhanced.userAction).toBeTruthy();
    expect(enhanced.severity).toBeTruthy();
    expect(enhanced.isRetryable).toBeTruthy();
    expect(enhanced.technical).toBeTruthy();
  });

  it('preserves original error in technical property', () => {
    const originalError: any = {
      code: 'ENOTFOUND',
      message: 'getaddrinfo ENOTFOUND',
      response: {
        status: 404,
        data: { error: 'Not Found' },
        statusText: 'Not Found',
      },
      config: { url: '/api/test' },
    };

    const enhanced = enhanceError(originalError);

    expect(enhanced.technical?.code).toBe('ENOTFOUND');
    expect(enhanced.technical?.message).toBe('getaddrinfo ENOTFOUND');
    expect(enhanced.technical?.response?.status).toBe(404);
    expect(enhanced.technical?.response?.data).toEqual({ error: 'Not Found' });
    expect(enhanced.technical?.config).toEqual({ url: '/api/test' });
  });

  it('sets user-friendly message', () => {
    const error: any = { code: 'ENOTFOUND' };

    const enhanced = enhanceError(error);

    expect(enhanced.userMessage).toMatch(/unable to connect/i);
    expect(enhanced.userMessage).not.toMatch(/ENOTFOUND/i);
  });

  it('sets correct action', () => {
    const error: any = { code: 'ENOTFOUND' };

    const enhanced = enhanceError(error);

    expect(enhanced.userAction).toBe('Check connection');
  });

  it('sets correct severity', () => {
    const error: any = { code: 'ENOTFOUND' };

    const enhanced = enhanceError(error);

    expect(enhanced.severity).toBe('error');
  });

  it('sets correct retryable flag', () => {
    const error: any = { code: 'ENOTFOUND' };

    const enhanced = enhanceError(error);

    expect(enhanced.isRetryable).toBe(true);
  });
});

describe('Integration: Error Message Consistency', () => {
  it('all 4xx errors have user-friendly messages', () => {
    const statusCodes = [400, 401, 403, 404, 408, 409, 422, 429];

    statusCodes.forEach((status) => {
      const error: any = { response: { status } };
      const message = getUserFriendlyErrorMessage(error);

      expect(message).toBeTruthy();
      expect(message).not.toMatch(new RegExp(`${status}`)); // No status codes
      expect(message.length).toBeGreaterThan(10); // Meaningful message
    });
  });

  it('all 5xx errors have user-friendly messages', () => {
    const statusCodes = [500, 502, 503, 504];

    statusCodes.forEach((status) => {
      const error: any = { response: { status } };
      const message = getUserFriendlyErrorMessage(error);

      expect(message).toBeTruthy();
      expect(message).not.toMatch(new RegExp(`${status}`));
      expect(message).toMatch(/try again/i); // All suggest retry
    });
  });

  it('all network errors have user-friendly messages', () => {
    const codes = ['ENOTFOUND', 'ECONNREFUSED', 'ETIMEDOUT', 'ECONNABORTED', 'ECONNRESET'];

    codes.forEach((code) => {
      const error: any = { code };
      const message = getUserFriendlyErrorMessage(error);

      expect(message).toBeTruthy();
      expect(message).not.toMatch(new RegExp(code));
      expect(message.length).toBeGreaterThan(10);
    });
  });

  it('all retryable errors have action suggestions', () => {
    const retryableErrors = [
      { response: { status: 500 } },
      { response: { status: 503 } },
      { response: { status: 504 } },
      { response: { status: 408 } },
      { code: 'ENOTFOUND' },
      { code: 'ETIMEDOUT' },
      { code: 'ECONNABORTED' },
      { code: 'ECONNRESET' },
    ];

    retryableErrors.forEach((error) => {
      const action = getErrorAction(error as any);

      expect(action).toBeTruthy(); // All retryable errors have actions
    });
  });
});
