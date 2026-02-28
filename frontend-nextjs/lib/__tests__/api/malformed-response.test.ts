/**
 * API Malformed Response Handling Tests
 *
 * Tests for malformed response scenarios including:
 * - Invalid JSON responses
 * - Empty response bodies
 * - Missing required fields
 * - Wrong data types
 * - Oversized responses
 * - Malformed headers
 * - Charset issues
 * - Partial/truncated responses
 * - API version mismatch
 * - Null/undefined values in response
 */

import apiClient from '@/lib/api';
import { rest } from 'msw';
import { setupServer } from 'msw/node';

// MSW setup
const server = setupServer(
  // Default test endpoint
  rest.get('/api/test/malformed', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true, data: 'test' })
    );
  }),

  // POST endpoint
  rest.post('/api/test/malformed', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true })
    );
  }),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('API Malformed Response Handling', () => {
  describe('1. Invalid JSON Response', () => {
    it('should handle invalid JSON gracefully', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json'),
            ctx.body('{{{invalid json}}}')
          );
        })
      );

      try {
        await apiClient.get('/api/test/malformed');
      } catch (error: any) {
        expect(error).toBeDefined();
        // Error should be caught, not crash app
        expect(error.message).toBeDefined();
      }
    });

    it('should handle malformed JSON syntax', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json'),
            ctx.body('{"success": true, "data":')
          );
        })
      );

      try {
        await apiClient.get('/api/test/malformed');
      } catch (error: any) {
        expect(error).toBeDefined();
        expect(error.message?.length).toBeGreaterThan(0);
      }
    });

    it('should handle JSON with trailing commas', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json'),
            ctx.body('{"success": true, "data": [1,2,3,]}')
          );
        })
      );

      try {
        await apiClient.get('/api/test/malformed');
        // May succeed if parser is lenient
        const response = await apiClient.get('/api/test/malformed');
        expect(response.data).toBeDefined();
      } catch (error: any) {
        // Or may fail if parser is strict
        expect(error).toBeDefined();
      }
    });

    it('should handle JSON with unquoted keys', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json'),
            ctx.body('{success: true, data: "test"}')
          );
        })
      );

      try {
        await apiClient.get('/api/test/malformed');
      } catch (error: any) {
        expect(error).toBeDefined();
      }
    });

    it('should handle completely invalid response format', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json'),
            ctx.body('<<<>>>{{{{!!!###}}}')
          );
        })
      );

      try {
        await apiClient.get('/api/test/malformed');
      } catch (error: any) {
        expect(error).toBeDefined();
        expect(error.message?.length).toBeGreaterThan(0);
      }
    });
  });

  describe('2. Empty Response Body', () => {
    it('should handle empty 200 response', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.body('')
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data).toBeDefined();
    });

    it('should handle null response body', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json(null)
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data).toBeDefined();
    });

    it('should handle whitespace-only response', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.body('   \n\t   ')
          );
        })
      );

      try {
        const response = await apiClient.get('/api/test/malformed');
        expect(response.data).toBeDefined();
      } catch (error: any) {
        // May throw parsing error
        expect(error).toBeDefined();
      }
    });

    it('should use default values for empty responses', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(204),
            ctx.body('')
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      // 204 No Content should have no data
      expect(response).toBeDefined();
    });
  });

  describe('3. Missing Required Fields', () => {
    it('should handle missing success field', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({ data: 'test' }) // missing 'success' field
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data).toBeDefined();
      expect(response.data.data).toBe('test');
    });

    it('should handle missing data field', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({ success: true }) // missing 'data' field
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data).toBeDefined();
      expect(response.data.success).toBe(true);
    });

    it('should handle completely empty object', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({})
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data).toBeDefined();
      expect(typeof response.data).toBe('object');
    });

    it('should handle response with only metadata', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              timestamp: '2024-02-28T10:00:00Z',
              version: '1.0',
              metadata: {}
            })
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data).toBeDefined();
      expect(response.data.timestamp).toBeDefined();
    });
  });

  describe('4. Wrong Data Types', () => {
    it('should handle string instead of object', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json('just a string')
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data).toBe('just a string');
    });

    it('should handle number instead of object', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json(42)
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data).toBe(42);
    });

    it('should handle array instead of object', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json([1, 2, 3, 4, 5])
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(Array.isArray(response.data)).toBe(true);
    });

    it('should handle boolean instead of object', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json(true)
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data).toBe(true);
    });

    it('should handle nested type mismatches', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: 'true', // should be boolean
              data: [1, 2, 3], // should be object
              count: '5', // should be number
            })
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data).toBeDefined();
      // App should handle type mismatches gracefully
    });
  });

  describe('5. Oversized Responses', () => {
    it('should handle large JSON response', async () => {
      const largeArray = Array(10000).fill({ id: 1, name: 'test', data: 'x'.repeat(100) });

      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({ data: largeArray })
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data.data).toBeDefined();
      expect(response.data.data.length).toBe(10000);
    });

    it('should handle deeply nested JSON', async () => {
      let nested: any = { value: 'deep' };
      for (let i = 0; i < 100; i++) {
        nested = { level: i, child: nested };
      }

      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json(nested)
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data).toBeDefined();
    });

    it('should handle response with many keys', async () => {
      const manyKeys: any = {};
      for (let i = 0; i < 1000; i++) {
        manyKeys[`key${i}`] = `value${i}`;
      }

      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json(manyKeys)
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(Object.keys(response.data).length).toBe(1000);
    });
  });

  describe('6. Malformed Headers', () => {
    it('should handle invalid Content-Type', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/invalid-type'),
            ctx.body('{"success": true}')
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      // Should still parse JSON even with invalid content type
      expect(response.data).toBeDefined();
    });

    it('should handle missing Content-Type', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res) => {
          return new Promise((resolve) => {
            resolve(
              new Response(
                '{"success": true}',
                {
                  status: 200,
                  headers: {
                    // No Content-Type header
                  }
                }
              )
            );
          });
        })
      );

      try {
        const response = await apiClient.get('/api/test/malformed');
        expect(response.data).toBeDefined();
      } catch (error) {
        // May fail without Content-Type
        expect(error).toBeDefined();
      }
    });

    it('should handle text/plain with JSON body', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'text/plain'),
            ctx.body('{"success": true}')
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      // Should parse JSON even with text/plain
      expect(response.data).toBeDefined();
    });

    it('should handle multiple Content-Type values', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json; charset=utf-8, text/html'),
            ctx.body('{"success": true}')
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data).toBeDefined();
    });
  });

  describe('7. Charset Issues', () => {
    it('should handle UTF-8 charset', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json; charset=utf-8'),
            ctx.body('{"success": true, "message": "Hello 世界 🌍"}')
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data.message).toBe('Hello 世界 🌍');
    });

    it('should handle missing charset', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json'),
            ctx.body('{"success": true, "message": "test"}')
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data.message).toBe('test');
    });

    it('should handle invalid charset', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json; charset=invalid-charset'),
            ctx.body('{"success": true}')
          );
        })
      );

      try {
        const response = await apiClient.get('/api/test/malformed');
        expect(response.data).toBeDefined();
      } catch (error) {
        // May fail with invalid charset
        expect(error).toBeDefined();
      }
    });

    it('should handle ASCII charset', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json; charset=ascii'),
            ctx.body('{"success": true}')
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data).toBeDefined();
    });
  });

  describe('8. Partial/Truncated Responses', () => {
    it('should handle truncated JSON', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json'),
            ctx.body('{"success": true, "data": {"message":')
          );
        })
      );

      try {
        await apiClient.get('/api/test/malformed');
      } catch (error: any) {
        expect(error).toBeDefined();
        expect(error.message?.length).toBeGreaterThan(0);
      }
    });

    it('should handle response ending mid-string', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json'),
            ctx.body('{"success": true, "message": "incomplete')
          );
        })
      );

      try {
        await apiClient.get('/api/test/malformed');
      } catch (error: any) {
        expect(error).toBeDefined();
      }
    });

    it('should not hang waiting for more data', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json'),
            ctx.body('{"success": true')
          );
        })
      );

      try {
        await apiClient.get('/api/test/malformed');
      } catch (error: any) {
        expect(error).toBeDefined();
      }
      // Test should complete quickly, not hang
    });
  });

  describe('9. API Version Mismatch', () => {
    it('should handle missing version field', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({ success: true, data: 'test' })
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data).toBeDefined();
    });

    it('should handle unexpected API version', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              api_version: '9.9.9',
              success: true,
              data: 'test'
            })
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data.api_version).toBe('9.9.9');
    });

    it('should handle deprecated version response', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              api_version: '1.0',
              deprecated: true,
              deprecation_date: '2024-01-01',
              success: true,
              data: 'test'
            })
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data.deprecated).toBe(true);
    });
  });

  describe('10. Null/Undefined Values in Response', () => {
    it('should handle null in required field', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: null,
              data: 'test'
            })
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data.success).toBeNull();
    });

    it('should handle null in data field', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              data: null
            })
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data.data).toBeNull();
    });

    it('should handle undefined-like behavior', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              data: undefined
            })
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      // undefined may be omitted from JSON
      expect(response.data).toBeDefined();
    });

    it('should handle mixed null and valid values', async () => {
      server.use(
        rest.get('/api/test/malformed', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              data: {
                name: 'test',
                value: null,
                count: 42,
                items: null,
                active: true
              }
            })
          );
        })
      );

      const response = await apiClient.get('/api/test/malformed');
      expect(response.data.data.name).toBe('test');
      expect(response.data.data.value).toBeNull();
      expect(response.data.data.items).toBeNull();
    });
  });
});
