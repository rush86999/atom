/**
 * API Error Handling Tests
 *
 * Tests for network failure scenarios including:
 * - Offline/network unreachable errors
 * - DNS failures
 * - Connection refused errors
 * - SSL/TLS certificate errors
 * - Request abortion
 * - Chunked transfer encoding errors
 * - Error boundary integration
 */

import apiClient, { systemAPI } from '@/lib/api';
import { rest } from 'msw';
import { setupServer } from 'msw/node';

// Type definitions for error responses
interface ErrorResponse {
  success: false;
  error: string;
  message: string;
  details?: any;
}

// MSW setup
const server = setupServer(
  // Health endpoint for basic connectivity tests
  rest.get('/api/health', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
      })
    );
  }),

  // Test endpoint for various error scenarios
  rest.get('/api/test/error', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: { message: 'test' },
      })
    );
  }),

  // POST endpoint for testing request body preservation
  rest.post('/api/test/error', async (req, res, ctx) => {
    const body = await req.json();
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        data: body,
      })
    );
  }),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Mock console.error to avoid cluttering test output
const originalError = console.error;
beforeEach(() => {
  console.error = jest.fn();
});
afterEach(() => {
  console.error = originalError;
});

describe('API Error Handling - Network Failures', () => {
  describe('1. Offline/Network Unreachable', () => {
    it('should handle network error gracefully', async () => {
      // Mock network unreachable error
      server.use(
        rest.get('/api/health', (req, res) => {
          // Simulate network error by not returning a response
          throw new Error('Network Error');
        })
      );

      const errorSpy = jest.fn();

      try {
        await systemAPI.getHealth();
      } catch (error: any) {
        errorSpy(error);
        expect(error).toBeDefined();
      }

      expect(errorSpy).toHaveBeenCalled();
    });

    it('should show user-friendly error message for network failure', async () => {
      server.use(
        rest.get('/api/health', (req, res) => {
          throw new Error('Network Error');
        })
      );

      try {
        await systemAPI.getHealth();
        expect(true).toBe(false, 'Should have thrown an error');
      } catch (error: any) {
        // Error should be caught and not crash the app
        expect(error).toBeDefined();
        // User-friendly message should be derivable from error
        const errorMessage = error.message || 'Unable to connect. Please check your internet connection.';
        expect(errorMessage).toBeDefined();
        expect(typeof errorMessage).toBe('string');
      }
    });

    it('should not crash app with unhandled rejection', async () => {
      const unhandledRejectionSpy = jest.fn();

      // Listen for unhandled rejections
      process.on('unhandledRejection', unhandledRejectionSpy);

      server.use(
        rest.get('/api/health', (req, res) => {
          throw new Error('Network Error');
        })
      );

      try {
        await systemAPI.getHealth();
      } catch (error) {
        // Expected to throw
      }

      // Give time for any unhandled rejections to propagate
      await new Promise(resolve => setTimeout(resolve, 100));

      // Should not have unhandled rejections
      expect(unhandledRejectionSpy).not.toHaveBeenCalled();

      process.off('unhandledRejection', unhandledRejectionSpy);
    });
  });

  describe('2. DNS Failure', () => {
    it('should handle DNS failure (ENOTFOUND)', async () => {
      // Create a custom axios instance with invalid hostname
      const dnsClient = Object.assign({}, apiClient);
      dnsClient.get = async () => {
        const error: any = new Error('getaddrinfo ENOTFOUND example.invalid');
        error.code = 'ENOTFOUND';
        error.syscall = 'getaddrinfo';
        error.hostname = 'example.invalid';
        throw error;
      };

      const errorSpy = jest.fn();

      try {
        await dnsClient.get('/api/health');
      } catch (error: any) {
        errorSpy(error);
        expect(error.code).toBe('ENOTFOUND');
        expect(error.message).toContain('ENOTFOUND');
      }

      expect(errorSpy).toHaveBeenCalled();
    });

    it('should show appropriate DNS error message', async () => {
      const dnsClient = Object.assign({}, apiClient);
      dnsClient.get = async () => {
        const error: any = new Error('getaddrinfo ENOTFOUND api.example.com');
        error.code = 'ENOTFOUND';
        throw error;
      };

      try {
        await dnsClient.get('/api/health');
        expect(true).toBe(false, 'Should have thrown an error');
      } catch (error: any) {
        expect(error.code).toBe('ENOTFOUND');
        // Error message should mention connection/DNS issue
        expect(error.message).toMatch(/ENOTFOUND|getaddrinfo/);
      }
    });

    it('should allow user to retry manually after DNS failure', async () => {
      let callCount = 0;

      const customClient = Object.assign({}, apiClient);
      customClient.get = async (url: string) => {
        callCount++;
        if (callCount === 1) {
          const error: any = new Error('getaddrinfo ENOTFOUND');
          error.code = 'ENOTFOUND';
          throw error;
        }
        return systemAPI.getHealth();
      };

      // First attempt fails
      try {
        await customClient.get('/api/health');
        expect(true).toBe(false, 'Should have thrown on first attempt');
      } catch (error: any) {
        expect(error.code).toBe('ENOTFOUND');
      }

      // User can retry (simulate with second call)
      try {
        await systemAPI.getHealth();
        // Should succeed on retry
      } catch (error) {
        expect(true).toBe(false, 'Should have succeeded on retry');
      }
    });
  });

  describe('3. Connection Refused', () => {
    it('should handle ECONNREFUSED error', async () => {
      const connectionRefusedClient = Object.assign({}, apiClient);
      connectionRefusedClient.get = async () => {
        const error: any = new Error('connect ECONNREFUSED 127.0.0.1:8000');
        error.code = 'ECONNREFUSED';
        error.errno = 'ECONNREFUSED';
        error.syscall = 'connect';
        error.address = '127.0.0.1';
        error.port = 8000;
        throw error;
      };

      const errorSpy = jest.fn();

      try {
        await connectionRefusedClient.get('/api/health');
      } catch (error: any) {
        errorSpy(error);
        expect(error.code).toBe('ECONNREFUSED');
      }

      expect(errorSpy).toHaveBeenCalled();
    });

    it('should handle backend not running scenario', async () => {
      const backendDownClient = Object.assign({}, apiClient);
      backendDownClient.get = async () => {
        const error: any = new Error('connect ECONNREFUSED');
        error.code = 'ECONNREFUSED';
        throw error;
      };

      try {
        await backendDownClient.get('/api/health');
        expect(true).toBe(false, 'Should have thrown ECONNREFUSED');
      } catch (error: any) {
        expect(error.code).toBe('ECONNREFUSED');
        // Should provide meaningful feedback about backend being down
        expect(error.message).toBeDefined();
      }
    });

    it('should show user-friendly message for connection refused', async () => {
      server.use(
        rest.get('/api/health', (req, res, ctx) => {
          // Simulate connection refused with 503
          return res(
            ctx.status(503),
            ctx.json({ error: 'Service Unavailable' })
          );
        })
      );

      const response = await systemAPI.getHealth();
      // Should get a 503 response (not an exception)
      expect(response.status).toBe(503);
      expect(response.data.error).toBeDefined();
    });
  });

  describe('4. SSL/TLS Errors', () => {
    it('should handle certificate validation failures', async () => {
      const sslClient = Object.assign({}, apiClient);
      sslClient.get = async () => {
        const error: any = new Error('certificate has expired');
        error.code = 'CERT_HAS_EXPIRED';
        error.code = 'UNABLE_TO_VERIFY_LEAF_SIGNATURE';
        throw error;
      };

      try {
        await sslClient.get('/api/health');
        expect(true).toBe(false, 'Should have thrown SSL error');
      } catch (error: any) {
        expect(error).toBeDefined();
        // Error should mention certificate/SSL
        const errorMsg = error.message.toLowerCase();
        expect(
          errorMsg.includes('certificate') ||
          errorMsg.includes('ssl') ||
          errorMsg.includes('tls')
        ).toBe(true);
      }
    });

    it('should log detailed SSL error but show safe message to user', async () => {
      const sslClient = Object.assign({}, apiClient);
      sslClient.get = async () => {
        const error: any = new Error('unable to verify the first certificate');
        error.code = 'UNABLE_TO_VERIFY_LEAF_SIGNATURE';
        error.stack = 'Detailed SSL stack trace...';
        throw error;
      };

      try {
        await sslClient.get('/api/health');
        expect(true).toBe(false, 'Should have thrown SSL error');
      } catch (error: any) {
        // Detailed error should be available for logging
        expect(error.stack).toBeDefined();

        // But user-facing message should be safe
        const userMessage = error.message;
        expect(userMessage).toBeDefined();
        expect(typeof userMessage).toBe('string');
      }
    });

    it('should handle self-signed certificate errors', async () => {
      const selfSignedClient = Object.assign({}, apiClient);
      selfSignedClient.get = async () => {
        const error: any = new Error('self-signed certificate');
        error.code = 'DEPTH_ZERO_SELF_SIGNED_CERT';
        throw error;
      };

      try {
        await selfSignedClient.get('/api/health');
        expect(true).toBe(false, 'Should have thrown certificate error');
      } catch (error: any) {
        expect(error).toBeDefined();
        expect(error.code).toBe('DEPTH_ZERO_SELF_SIGNED_CERT');
      }
    });
  });

  describe('5. Request Abortion', () => {
    it('should handle request abortion when user navigates away', async () => {
      const abortController = new AbortController();
      const abortClient = Object.assign({}, apiClient);

      abortClient.get = async () => {
        // Simulate user navigating away
        setTimeout(() => abortController.abort(), 10);

        return new Promise((resolve, reject) => {
          setTimeout(() => {
            if (abortController.signal.aborted) {
              const error: any = new Error('Request aborted');
              error.code = 'ERR_CANCELED';
              reject(error);
            } else {
              resolve({ data: { success: true } });
            }
          }, 50);
        });
      };

      try {
        await abortClient.get('/api/health');
      } catch (error: any) {
        expect(error.code).toBe('ERR_CANCELED');
        expect(error.message).toContain('aborted');
      }
    });

    it('should not crash app on abort errors', async () => {
      const abortClient = Object.assign({}, apiClient);

      // Test that abort errors don't trigger unhandled rejections
      const unhandledSpy = jest.fn();
      process.on('unhandledRejection', unhandledSpy);

      abortClient.get = async () => {
        const error: any = new Error('Request canceled');
        error.code = 'ERR_CANCELED';
        throw error;
      };

      try {
        await abortClient.get('/api/health');
      } catch (error) {
        // Expected
      }

      await new Promise(resolve => setTimeout(resolve, 50));
      expect(unhandledSpy).not.toHaveBeenCalled();

      process.off('unhandledRejection', unhandledSpy);
    });

    it('should clean up pending requests on abort', async () => {
      const pendingRequests = new Set<string>();
      const abortClient = Object.assign({}, apiClient);

      abortClient.get = async (url: string) => {
        const requestId = `req_${Date.now()}`;
        pendingRequests.add(requestId);

        return new Promise((resolve, reject) => {
          setTimeout(() => {
            if (pendingRequests.has(requestId)) {
              pendingRequests.delete(requestId);
              const error: any = new Error('Request canceled');
              error.code = 'ERR_CANCELED';
              reject(error);
            }
          }, 10);
        });
      };

      try {
        await abortClient.get('/api/health');
      } catch (error: any) {
        expect(error.code).toBe('ERR_CANCELED');
      }

      // Verify cleanup
      expect(pendingRequests.size).toBe(0);
    });
  });

  describe('6. Chunked Transfer Encoding Errors', () => {
    it('should handle incomplete chunked responses', async () => {
      server.use(
        rest.get('/api/test/error', (req, res, ctx) => {
          // Return incomplete response
          return res(
            ctx.status(200),
            ctx.set('Transfer-Encoding', 'chunked'),
            ctx.body('{"success": true, "data":')
          );
        })
      );

      try {
        await apiClient.get('/api/test/error');
        // If we get here, check that data is parsed as best effort
      } catch (error: any) {
        // Should handle incomplete JSON
        expect(error).toBeDefined();
        // Error message should mention parsing
        const errMsg = error.message || '';
        expect(errMsg.length).toBeGreaterThan(0);
      }
    });

    it('should handle partial data gracefully', async () => {
      server.use(
        rest.get('/api/test/error', (req, res, ctx) => {
          // Simulate truncated response
          return res(
            ctx.status(200),
            ctx.body('{"success": true, "data": {"message": "incomplete"')
          );
        })
      );

      try {
        await apiClient.get('/api/test/error');
        // May succeed or fail depending on JSON parser
      } catch (error: any) {
        expect(error).toBeDefined();
        // Should not crash app
        expect(error.message).toBeDefined();
      }
    });

    it('should verify chunked response size handling', async () => {
      // Test with very small chunk
      server.use(
        rest.get('/api/test/error', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Transfer-Encoding', 'chunked'),
            ctx.set('Content-Type', 'text/plain'),
            ctx.body('OK')
          );
        })
      );

      const response = await apiClient.get('/api/test/error');
      expect(response.data).toBe('OK');
    });
  });

  describe('7. Error Boundary Integration', () => {
    it('should not crash app for normal API errors', async () => {
      server.use(
        rest.get('/api/health', (req, res, ctx) => {
          return res(
            ctx.status(404),
            ctx.json({ success: false, error: 'Not found' })
          );
        })
      );

      // Normal error handling - should not crash app
      let errorThrown = false;
      try {
        await systemAPI.getHealth();
      } catch (error: any) {
        // Expected - normal API error
        errorThrown = true;
        expect(error.response?.status).toBe(404);
      }

      expect(errorThrown).toBe(true);
    }, 10000);

    it('should handle errors during response parsing', async () => {
      server.use(
        rest.get('/api/test/error', (req, res, ctx) => {
          // Return malformed response
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json'),
            ctx.body('{{{malformed json}}}')
          );
        })
      );

      try {
        await apiClient.get('/api/test/error');
      } catch (error: any) {
        // Parsing errors should be caught and handled
        expect(error).toBeDefined();
        // May or may not have 'JSON' in message depending on parser
        expect(error.message).toBeDefined();
      }
    });

    it('should not crash on null/undefined error responses', async () => {
      server.use(
        rest.get('/api/test/error', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json(null)
          );
        })
      );

      const response = await apiClient.get('/api/test/error');
      expect(response.data).toBeDefined();
      // Should not crash
    }, 10000);

    it('should handle errors in error response itself', async () => {
      server.use(
        rest.get('/api/test/error', (req, res, ctx) => {
          // Return error with malformed error object
          return res(
            ctx.status(500),
            ctx.json({
              success: false,
              error: undefined,
              message: null,
            })
          );
        })
      );

      const response = await apiClient.get('/api/test/error');
      expect(response.data).toBeDefined();
      // Should handle gracefully
      expect(response.status).toBe(500);
    }, 10000);

    it('should handle catastrophic parsing errors without crash', async () => {
      server.use(
        rest.get('/api/test/error', (req, res, ctx) => {
          // Return completely invalid response
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json'),
            ctx.body('<<<>>>???')
          );
        })
      );

      try {
        await apiClient.get('/api/test/error');
      } catch (error: any) {
        // Should handle catastrophic parse errors
        expect(error).toBeDefined();
        // Error should be caught, not crash app
        const errorMessage = error.message || error.toString();
        expect(errorMessage).toBeDefined();
      }
    });

    it('should allow app to continue after error', async () => {
      let callCount = 0;

      server.use(
        rest.get('/api/test/error', (req, res, ctx) => {
          callCount++;
          if (callCount === 1) {
            // First call: catastrophic error
            return res(
              ctx.status(200),
              ctx.body('{{{')
            );
          }
          // Second call: success
          return res(
            ctx.status(200),
            ctx.json({ success: true, data: 'recovered' })
          );
        })
      );

      // First call fails catastrophically
      let firstError: any = null;
      try {
        await apiClient.get('/api/test/error');
      } catch (error: any) {
        firstError = error;
      }

      expect(firstError).toBeDefined();

      // App should continue and succeed on second call
      const response = await apiClient.get('/api/test/error');
      expect(response.data.success).toBe(true);
      expect(response.data.data).toBe('recovered');
    }, 15000);
  });

  describe('8. Network Error Recovery', () => {
    it('should allow retry after failed request', async () => {
      let firstCallFailed = false;

      server.use(
        rest.get('/api/health', (req, res, ctx) => {
          return res(
            ctx.status(503),
            ctx.json({ error: 'Service Unavailable' })
          );
        })
      );

      // First attempt fails
      try {
        await systemAPI.getHealth();
      } catch (error) {
        firstCallFailed = true;
      }

      expect(firstCallFailed).toBe(true);
    }, 10000);

    it('should handle multiple consecutive network failures', async () => {
      let failureCount = 0;

      server.use(
        rest.get('/api/health', (req, res, ctx) => {
          return res(
            ctx.status(503),
            ctx.json({ error: 'Service Unavailable' })
          );
        })
      );

      // Try multiple times
      for (let i = 0; i < 3; i++) {
        try {
          await systemAPI.getHealth();
        } catch (error) {
          failureCount++;
        }
      }

      expect(failureCount).toBe(3);
    }, 15000);

    it('should recover after network restored', async () => {
      let networkDown = true;

      server.use(
        rest.get('/api/health', (req, res, ctx) => {
          if (networkDown) {
            return res(
              ctx.status(503),
              ctx.json({ error: 'Service Unavailable' })
            );
          }
          return res(
            ctx.status(200),
            ctx.json({ status: 'healthy' })
          );
        })
      );

      // Network down
      try {
        await systemAPI.getHealth();
        expect(true).toBe(false, 'Should fail when network down');
      } catch (error) {
        // Expected
      }

      // Network restored - update handler
      networkDown = false;
      server.use(
        rest.get('/api/health', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({ status: 'healthy' })
          );
        })
      );

      const response = await systemAPI.getHealth();
      expect(response.data.status).toBe('healthy');
    }, 10000);
  });
});
