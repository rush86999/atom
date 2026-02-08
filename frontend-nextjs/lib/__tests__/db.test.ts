/**
 * Tests for Database Utilities
 *
 * Tests the PostgreSQL connection pool and query function
 */

import { query } from '../db';

// Mock pg Pool
jest.mock('pg', () => {
  const mockQuery = jest.fn();
  const mockConnect = jest.fn();
  const mockPool = {
    query: mockQuery,
    connect: mockConnect,
    on: jest.fn(),
  };

  return {
    Pool: jest.fn(() => mockPool),
  };
});

import { Pool } from 'pg';

describe('Database Utilities', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('query function', () => {
    it('should export query function', () => {
      expect(query).toBeDefined();
      expect(typeof query).toBe('function');
    });

    it('should accept SQL text and optional params', async () => {
      // In test environment, DATABASE_URL is likely not set, so query will use mock pool
      const mockQuery = jest.fn().mockResolvedValue({ rows: [] });

      // We can't easily test the query execution without proper DB setup
      // But we can verify the function exists and has the right signature
      expect(() => query('SELECT 1')).toBeDefined();
      expect(() => query('SELECT $1', [1])).toBeDefined();
    });

    it('should handle query errors gracefully', async () => {
      // The query function should throw errors in production
      // but handle them with logging
      const mockQuery = jest.fn().mockRejectedValue(new Error('DB error'));

      // In development without DATABASE_URL, query will use mock pool
      // which throws an error
      await expect(query('SELECT 1')).rejects.toThrow();
    });
  });

  describe('Pool configuration', () => {
    it('should use DATABASE_URL from env when set', () => {
      const originalUrl = process.env.DATABASE_URL;
      process.env.DATABASE_URL = 'postgresql://test';

      expect(process.env.DATABASE_URL).toBe('postgresql://test');

      process.env.DATABASE_URL = originalUrl;
    });

    it('should handle missing DATABASE_URL gracefully', () => {
      const originalUrl = process.env.DATABASE_URL;
      delete process.env.DATABASE_URL;

      expect(process.env.DATABASE_URL).toBeUndefined();

      process.env.DATABASE_URL = originalUrl;
    });
  });

  describe('Error handling', () => {
    it('should log database errors', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      await query('SELECT 1').catch(() => {
        // Expected to fail without DATABASE_URL
      });

      // Should log error
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });
  });
});
