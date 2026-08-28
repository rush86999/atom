/**
 * Tests for Database Utilities — comprehensive coverage of pool
 * configuration (prod/dev, DATABASE_URL present/absent), the mock-pool
 * fallback, global pool reuse, and query error handling.
 */

const mockPoolQuery = jest.fn();
const mockPoolInstance = {
  query: mockPoolQuery,
  on: jest.fn(),
  connect: jest.fn(),
};
jest.mock('pg', () => ({
  Pool: jest.fn(() => mockPoolInstance),
}));

import { Pool } from 'pg';
const MockPool = Pool as unknown as jest.Mock;

const originalEnv = { ...process.env };
const originalPostgresPool = (global as any).postgresPool;

const loadDb = (env: Record<string, string | undefined>) => {
  for (const [k, v] of Object.entries(env)) {
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
  let loaded: any;
  jest.isolateModules(() => {
    loaded = require('../db');
  });
  return loaded;
};

describe('lib/db', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    MockPool.mockImplementation(() => mockPoolInstance);
    delete (global as any).postgresPool;
    process.env = { ...originalEnv };
    delete process.env.DATABASE_URL;
    delete process.env.DB_SSL_REJECT_UNAUTHORIZED;
    (process.env as { NODE_ENV?: string }).NODE_ENV = 'test';
  });

  afterEach(() => {
    process.env = { ...originalEnv };
    delete (global as any).postgresPool;
    if (originalPostgresPool) (global as any).postgresPool = originalPostgresPool;
  });

  it('creates a real pool with SSL in production', () => {
    (process.env as { NODE_ENV?: string }).NODE_ENV = 'production';
    process.env.DATABASE_URL = 'postgresql://prod:5432/db';
    const db = loadDb({});
    expect(db.query).toBeDefined();
    expect(MockPool).toHaveBeenCalledWith(
      expect.objectContaining({
        connectionString: 'postgresql://prod:5432/db',
        ssl: { rejectUnauthorized: true },
        connectionTimeoutMillis: 2000,
      }),
    );
  });

  it('honors DB_SSL_REJECT_UNAUTHORIZED=false in production', () => {
    (process.env as { NODE_ENV?: string }).NODE_ENV = 'production';
    process.env.DATABASE_URL = 'postgresql://prod:5432/db';
    process.env.DB_SSL_REJECT_UNAUTHORIZED = 'false';
    loadDb({});
    expect(MockPool).toHaveBeenCalledWith(
      expect.objectContaining({ ssl: { rejectUnauthorized: false } }),
    );
  });

  it('creates a pool with an undefined connection string in production without DATABASE_URL', () => {
    (process.env as { NODE_ENV?: string }).NODE_ENV = 'production';
    const db = loadDb({});
    expect(db.query).toBeDefined();
    expect(MockPool).toHaveBeenCalledWith(
      expect.objectContaining({
        connectionString: undefined,
        ssl: { rejectUnauthorized: true },
      }),
    );
  });

  it('reuses the global pool in development', () => {
    (process.env as { NODE_ENV?: string }).NODE_ENV = 'development';
    process.env.DATABASE_URL = 'postgresql://dev:5432/db';
    loadDb({});
    loadDb({});
    expect(MockPool).toHaveBeenCalledTimes(1);
  });

  it('uses the mock pool in development without DATABASE_URL', async () => {
    (process.env as { NODE_ENV?: string }).NODE_ENV = 'development';
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const db = loadDb({});
    expect(warnSpy).toHaveBeenCalled();
    await expect(db.query('SELECT 1')).rejects.toThrow('Database not connected');
  });

  it('returns pool.query results', async () => {
    process.env.DATABASE_URL = 'postgresql://x:5432/db';
    const db = loadDb({});
    mockPoolQuery.mockResolvedValue({ rows: [{ id: 1 }] });
    await expect(db.query('SELECT * FROM users WHERE id = $1', [1])).resolves.toEqual({
      rows: [{ id: 1 }],
    });
    expect(mockPoolQuery).toHaveBeenCalledWith('SELECT * FROM users WHERE id = $1', [1]);
  });

  it('logs and re-throws query errors', async () => {
    process.env.DATABASE_URL = 'postgresql://x:5432/db';
    const db = loadDb({});
    const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    mockPoolQuery.mockRejectedValue(new Error('connection refused'));
    await expect(db.query('SELECT broken', ['p'])).rejects.toThrow('connection refused');
    expect(errorSpy).toHaveBeenCalledWith('❌ Database connection error:', {
      message: 'connection refused',
      query: 'SELECT broken',
      params: ['p'],
    });
  });
});
