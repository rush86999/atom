/**
 * Authentication Utilities Tests
 *
 * Tests verify NextAuth configuration, credential provider behavior,
 * JWT/session callbacks, and authentication error handling.
 *
 * Source: lib/auth.ts (305 lines)
 */

import { authOptions } from '../auth';

// Mock dependencies
jest.mock('../db', () => ({
  query: jest.fn(),
}));

jest.mock('../api', () => ({
  USE_BACKEND_API: false,
  adminAPI: {
    getAdminUsers: jest.fn(),
    updateAdminLastLogin: jest.fn(),
  },
  tenantAPI: {
    getTenantBySubdomain: jest.fn(),
    getTenantById: jest.fn(),
  },
}));

// Mock NextAuth
jest.mock('next-auth', () => ({
  __esModule: true,
  default: jest.fn(),
  NextAuth: jest.fn(),
}));

import { query } from '../db';
import { adminAPI, tenantAPI } from '../api';

describe('auth.ts - NextAuth Configuration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    process.env.NODE_ENV = 'test';
    process.env.JWT_SECRET = 'test-secret';
    process.env.NEXTAUTH_SECRET = 'test-nextauth-secret';
  });

  afterEach(() => {
    delete process.env.NODE_ENV;
    delete process.env.JWT_SECRET;
    delete process.env.NEXTAUTH_SECRET;
  });

  // Test 1: authOptions is properly configured
  test('authOptions should be defined with required properties', () => {
    expect(authOptions).toBeDefined();
    expect(authOptions.providers).toBeDefined();
    expect(authOptions.session).toBeDefined();
    expect(authOptions.jwt).toBeDefined();
    expect(authOptions.callbacks).toBeDefined();
    expect(authOptions.pages).toBeDefined();
  });

  // Test 2: credentials provider configuration
  test('credentials provider should be configured', () => {
    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');

    expect(credentialsProvider).toBeDefined();
    expect(credentialsProvider.name).toBe('credentials');
    expect(credentialsProvider.credentials).toBeDefined();
    expect(credentialsProvider.credentials.email).toBeDefined();
    expect(credentialsProvider.credentials.password).toBeDefined();
    expect(credentialsProvider.credentials.totp_code).toBeDefined();
  });

  // Test 3: session strategy is JWT
  test('session strategy should be JWT', () => {
    expect(authOptions.session.strategy).toBe('jwt');
    expect(authOptions.session.maxAge).toBe(24 * 60 * 60); // 24 hours
  });

  // Test 4: JWT configuration
  test('JWT configuration should use secret from environment', () => {
    expect(authOptions.jwt.secret).toBe('test-nextauth-secret');
  });

  // Test 5: custom pages configuration
  test('custom sign-in and error pages should be configured', () => {
    expect(authOptions.pages.signIn).toBe('/auth/signin');
    expect(authOptions.pages.error).toBe('/auth/error');
  });

  // Test 6: authorize function rejects missing credentials
  test('authorize should return null for missing email or password', async () => {
    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    const authorize = credentialsProvider.authorize;

    // Missing both email and password
    const result1 = await authorize({ email: '', password: '' });
    expect(result1).toBeNull();

    // Missing password
    const result2 = await authorize({ email: 'test@example.com', password: '' });
    expect(result2).toBeNull();

    // Missing email
    const result3 = await authorize({ email: '', password: 'password123' });
    expect(result3).toBeNull();
  });

  // Test 7: authorize function handles successful admin login
  test('authorize should authenticate admin users successfully', async () => {
    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    const authorize = credentialsProvider.authorize;

    const mockAdminUser = {
      id: 'admin-123',
      email: 'admin@atom-saas.com',
      name: 'Admin User',
      role_name: 'super_admin',
      permissions: ['*'],
      status: 'active',
    };

    (query as jest.Mock).mockResolvedValueOnce({
      rows: [mockAdminUser],
    });

    // Mock successful fetch for login
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'test-jwt-token' }),
      })
    ) as any;

    const result = await authorize({
      email: 'admin@atom-saas.com',
      password: 'password123',
    });

    expect(result).toBeDefined();
    expect(result.email).toBe('admin@atom-saas.com');
    expect(result.role).toBe('super_admin');
    expect(result.access_token).toBe('test-jwt-token');
  });

  // Test 8: authorize function handles successful regular user login
  test('authorize should authenticate regular users successfully', async () => {
    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    const authorize = credentialsProvider.authorize;

    const mockUser = {
      id: 'user-123',
      email: 'user@example.com',
      name: 'Regular User',
      first_name: 'Regular',
      last_name: 'User',
      role: 'user',
      status: 'active',
      tenant_id: null,
    };

    (query as jest.Mock).mockResolvedValueOnce({ rows: [] }); // No admin
    (query as jest.Mock).mockResolvedValueOnce({ rows: [mockUser] }); // User found

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'test-jwt-token' }),
      })
    ) as any;

    const result = await authorize({
      email: 'user@example.com',
      password: 'password123',
    });

    expect(result).toBeDefined();
    expect(result.email).toBe('user@example.com');
    expect(result.role).toBe('user');
  });

  // Test 9: authorize function handles 2FA required
  test('authorize should throw 2FA_REQUIRED error when two_factor_required is true', async () => {
    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    const authorize = credentialsProvider.authorize;

    (query as jest.Mock).mockResolvedValue({ rows: [] });

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: false,
        status: 200,
        json: () => Promise.resolve({ two_factor_required: true }),
      })
    ) as any;

    await expect(
      authorize({
        email: 'user@example.com',
        password: 'password123',
      })
    ).rejects.toThrow('2FA_REQUIRED');
  });

  // Test 10: authorize function handles invalid 2FA code
  test('authorize should throw INVALID_2FA_CODE error for invalid 2FA', async () => {
    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    const authorize = credentialsProvider.authorize;

    (query as jest.Mock).mockResolvedValue({ rows: [] });

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Invalid 2FA code' }),
      })
    ) as any;

    await expect(
      authorize({
        email: 'user@example.com',
        password: 'password123',
        totp_code: '123456',
      })
    ).rejects.toThrow('INVALID_2FA_CODE');
  });

  // Test 11: JWT callback populates token with user data
  test('JWT callback should populate token with user data', async () => {
    const mockUser = {
      id: 'user-123',
      email: 'user@example.com',
      name: 'Test User',
      role: 'user',
      tenant_id: 'tenant-123',
      access_token: 'jwt-token',
    };

    const mockToken = {};

    const result = await authOptions.callbacks.jwt({
      token: mockToken,
      user: mockUser,
    });

    expect(result.id).toBe('user-123');
    expect(result.email).toBe('user@example.com');
    expect(result.name).toBe('Test User');
    expect(result.role).toBe('user');
    expect(result.tenant_id).toBe('tenant-123');
    expect(result.backendToken).toBe('jwt-token');
  });

  // Test 12: JWT callback preserves token without user
  test('JWT callback should preserve token when user is undefined', async () => {
    const mockToken = {
      id: 'user-123',
      email: 'user@example.com',
    };

    const result = await authOptions.callbacks.jwt({
      token: mockToken,
      user: undefined,
    });

    expect(result.id).toBe('user-123');
    expect(result.email).toBe('user@example.com');
  });

  // Test 13: session callback populates session with token data
  test('session callback should populate session with token data', async () => {
    const mockToken = {
      id: 'user-123',
      email: 'user@example.com',
      name: 'Test User',
      role: 'user',
      tenant_id: 'tenant-123',
      tenant_subdomain: 'test-tenant',
      tenant_name: 'Test Tenant',
      plan_type: 'premium',
      admin_role: 'admin',
      permissions: ['read', 'write'],
      backendToken: 'backend-jwt',
    };

    const mockSession = {
      user: {},
    };

    const result = await authOptions.callbacks.session({
      session: mockSession,
      token: mockToken,
    });

    expect(result.user.id).toBe('user-123');
    expect(result.user.email).toBe('user@example.com');
    expect(result.user.name).toBe('Test User');
    expect(result.user.role).toBe('user');
    expect(result.user.tenant_id).toBe('tenant-123');
    expect(result.user.tenant_subdomain).toBe('test-tenant');
    expect(result.user.tenant_name).toBe('Test Tenant');
    expect(result.user.plan_type).toBe('premium');
    expect(result.user.admin_role).toBe('admin');
    expect(result.user.permissions).toEqual(['read', 'write']);
    expect(result.backendToken).toBe('backend-jwt');
  });

  // Test 14: authorize handles tenant user with subdomain
  test('authorize should authenticate tenant users with subdomain', async () => {
    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    const authorize = credentialsProvider.authorize;

    const mockTenant = {
      id: 'tenant-123',
      subdomain: 'test-tenant',
      name: 'Test Tenant',
      plan_type: 'premium',
      status: 'active',
    };

    const mockUser = {
      id: 'user-456',
      email: 'tenant-user@test-tenant.com',
      name: 'Tenant User',
      role: 'tenant_admin',
      status: 'active',
      tenant_id: 'tenant-123',
    };

    (query as jest.Mock)
      .mockResolvedValueOnce({ rows: [] }) // No admin
      .mockResolvedValueOnce({ rows: [] }) // No regular user
      .mockResolvedValueOnce({ rows: [mockTenant] }) // Tenant found
      .mockResolvedValueOnce({ rows: [mockUser] }); // User found

    // Mock set_tenant_context
    (query as jest.Mock).mockResolvedValue({});

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'tenant-jwt-token' }),
      })
    ) as any;

    const result = await authorize({
      email: 'tenant-user@test-tenant.com',
      password: 'password123',
      tenant_subdomain: 'test-tenant',
    });

    expect(result).toBeDefined();
    expect(result.email).toBe('tenant-user@test-tenant.com');
    expect(result.tenant_id).toBe('tenant-123');
    expect(result.tenant_subdomain).toBe('test-tenant');
  });

  // Test 15: authorize returns null for inactive users
  test('authorize should return null for inactive users', async () => {
    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    const authorize = credentialsProvider.authorize;

    const mockInactiveUser = {
      id: 'user-123',
      email: 'user@example.com',
      status: 'inactive',
    };

    (query as jest.Mock).mockResolvedValueOnce({ rows: [] }); // No admin
    (query as jest.Mock).mockResolvedValueOnce({ rows: [mockInactiveUser] }); // Inactive user

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'test-jwt-token' }),
      })
    ) as any;

    const result = await authorize({
      email: 'user@example.com',
      password: 'password123',
    });

    expect(result).toBeNull();
  });
});
