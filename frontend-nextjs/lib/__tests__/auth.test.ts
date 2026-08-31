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

// Toggleable USE_BACKEND_API: the mock exports a getter so the authorize()
// function re-reads the flag at every call site (ts-jest CJS emits property
// accesses, not a captured binding).
let mockUseBackendApi = false;

jest.mock('../api', () => ({
  get USE_BACKEND_API() {
    return mockUseBackendApi;
  },
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
    mockUseBackendApi = false;
    (process.env as any).NODE_ENV = 'test';
    process.env.JWT_SECRET = 'test-secret';
    process.env.NEXTAUTH_SECRET = 'test-nextauth-secret';
  });

  afterEach(() => {
    delete (process.env as any).NODE_ENV;
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
    // next-auth v4 default provider name is capitalized ("Credentials")
    expect(credentialsProvider.name).toBe('Credentials');
    // In next-auth 4.24.x the provider config (credentials, authorize) lives
    // under provider.options
    expect(credentialsProvider.options).toBeDefined();
    expect(credentialsProvider.options.credentials).toBeDefined();
    expect(credentialsProvider.options.credentials.email).toBeDefined();
    expect(credentialsProvider.options.credentials.password).toBeDefined();
    expect(credentialsProvider.options.credentials.totp_code).toBeDefined();
  });

  // Test 3: session strategy is JWT
  test('session strategy should be JWT', () => {
    expect(authOptions.session.strategy).toBe('jwt');
    expect(authOptions.session.maxAge).toBe(24 * 60 * 60); // 24 hours
  });

  // Test 4: JWT configuration
  test('JWT configuration should use secret from environment', () => {
    // lib/auth.ts reads the env at module load (jwt.secret), so re-evaluate
    // the module with the env vars set; JWT_SECRET takes precedence
    process.env.JWT_SECRET = 'test-secret';
    process.env.NEXTAUTH_SECRET = 'test-nextauth-secret';
    jest.isolateModules(() => {
      const freshModule = require('../auth');
      expect(freshModule.authOptions.jwt.secret).toBe('test-secret');
    });
  });

  // Test 5: custom pages configuration
  test('custom sign-in and error pages should be configured', () => {
    expect(authOptions.pages.signIn).toBe('/auth/signin');
    expect(authOptions.pages.error).toBe('/auth/error');
  });

  // Test 6: authorize function rejects missing credentials
  test('authorize should return null for missing email or password', async () => {
    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    const authorize = credentialsProvider.options.authorize;

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
    const authorize = credentialsProvider.options.authorize;

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
    const authorize = credentialsProvider.options.authorize;

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

    // Non-admin email: the app skips the admin_users query entirely
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
    const authorize = credentialsProvider.options.authorize;

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
    const authorize = credentialsProvider.options.authorize;

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
      // lib/auth.ts's jwt callback ignores `account`; it is required by the
      // next-auth callback signature but irrelevant to this fixture.
    } as any);

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
    } as any);

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

    // Fixture uses a partial Session and an enriched user (extra token claims
    // copied by the callback), so bypass next-auth's strict Session typing.
    const result = (await authOptions.callbacks.session({
      session: mockSession,
      token: mockToken,
    } as any)) as any;

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
    const authorize = credentialsProvider.options.authorize;

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

    // Non-admin email: the app skips the admin_users query entirely
    (query as jest.Mock)
      .mockResolvedValueOnce({ rows: [] }) // No regular user
      .mockResolvedValueOnce({ rows: [mockTenant] }) // Tenant found
      .mockResolvedValueOnce({ rows: [] }) // set_tenant_context
      .mockResolvedValueOnce({ rows: [mockUser] }); // Tenant user found

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
    const authorize = credentialsProvider.options.authorize;

    const mockInactiveUser = {
      id: 'user-123',
      email: 'user@example.com',
      status: 'inactive',
    };

    (query as jest.Mock).mockResolvedValueOnce({ rows: [] }); // No admin
    // The app's SQL filters status = 'active', so an inactive user yields no rows
    (query as jest.Mock).mockResolvedValueOnce({ rows: [] }); // Inactive user filtered by SQL

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

  // Test 16: authorize resolves the admin via the backend API when
  // USE_BACKEND_API is enabled (adminAPI.getAdminUsers path)
  test('authorize should use adminAPI to authenticate admins when USE_BACKEND_API is on', async () => {
    mockUseBackendApi = true;

    const mockAdminUser = {
      id: 'admin-1',
      email: 'admin@atom-saas.com',
      name: 'API Admin',
      role_name: 'super_admin',
      permissions: ['*'],
      status: 'active',
    };

    (adminAPI.getAdminUsers as jest.Mock).mockResolvedValue({ data: [mockAdminUser] });

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'jwt-1' }),
      })
    ) as any;

    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    const result = await credentialsProvider.options.authorize({
      email: 'admin@atom-saas.com',
      password: 'pw',
    });

    expect(adminAPI.getAdminUsers).toHaveBeenCalled();
    expect(adminAPI.updateAdminLastLogin).toHaveBeenCalledWith('admin-1');
    expect(result).toMatchObject({
      id: 'admin-1',
      role: 'super_admin',
      admin_role: 'super_admin',
      access_token: 'jwt-1',
    });
  });

  // Test 17: when the backend API fails, admin auth falls back to the DB query
  test('authorize should fall back to DB when adminAPI fails', async () => {
    mockUseBackendApi = true;

    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
    (adminAPI.getAdminUsers as jest.Mock).mockRejectedValue(new Error('api down'));

    const mockAdminUser = {
      id: 'admin-2',
      email: 'admin@atom-saas.com',
      name: 'DB Admin',
      role_name: 'super_admin',
      permissions: ['*'],
      status: 'active',
    };

    (query as jest.Mock).mockResolvedValueOnce({ rows: [mockAdminUser] });

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'jwt-2' }),
      })
    ) as any;

    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    const result = await credentialsProvider.options.authorize({
      email: 'admin@atom-saas.com',
      password: 'pw',
    });

    expect(consoleSpy).toHaveBeenCalledWith('Failed to fetch admin users from API:', expect.any(Error));
    expect(result).toMatchObject({ id: 'admin-2', role: 'super_admin' });
    consoleSpy.mockRestore();
  });

  // Test 18: an inactive admin found via adminAPI falls through to the DB query
  test('authorize should ignore inactive admins from adminAPI and use DB', async () => {
    mockUseBackendApi = true;

    (adminAPI.getAdminUsers as jest.Mock).mockResolvedValue({
      data: [{ id: 'inactive-1', email: 'admin@atom-saas.com', status: 'inactive' }],
    });

    const mockAdminUser = {
      id: 'admin-3',
      email: 'admin@atom-saas.com',
      name: 'Active Admin',
      role_name: 'super_admin',
      permissions: ['*'],
      status: 'active',
    };

    (query as jest.Mock).mockResolvedValueOnce({ rows: [mockAdminUser] });

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'jwt-3' }),
      })
    ) as any;

    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    const result = await credentialsProvider.options.authorize({
      email: 'admin@atom-saas.com',
      password: 'pw',
    });

    expect(result).toMatchObject({ id: 'admin-3' });
  });

  // Test 19: a user with a tenant_id resolves tenant info (API path fails over
  // to the DB query) and returns the enriched user object
  test('authorize should enrich users with tenant info via DB fallback', async () => {
    mockUseBackendApi = true;

    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
    (tenantAPI.getTenantBySubdomain as jest.Mock).mockRejectedValue(new Error('tenant api down'));

    const mockUser = {
      id: 'user-t1',
      email: 'user@example.com',
      first_name: 'Tenant',
      last_name: 'User',
      role: 'admin',
      status: 'active',
      tenant_id: 'tenant-1',
    };

    // 1) users SELECT (found) — the tenant lookup happens inside the same block
    (query as jest.Mock).mockResolvedValueOnce({ rows: [mockUser] });
    // 2) tenants fallback query
    (query as jest.Mock).mockResolvedValueOnce({
      rows: [{ id: 'tenant-1', subdomain: 'acme', name: 'Acme', plan_type: 'pro' }],
    });

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'jwt-4' }),
      })
    ) as any;

    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    const result = await credentialsProvider.options.authorize({
      email: 'user@example.com',
      password: 'pw',
    });

    expect(consoleSpy).toHaveBeenCalledWith('Failed to fetch tenant from API:', expect.any(Error));
    expect(result).toMatchObject({
      id: 'user-t1',
      tenant_id: 'tenant-1',
      tenant_subdomain: 'acme',
      tenant_name: 'Acme',
      plan_type: 'pro',
      name: 'Tenant User',
    });
    consoleSpy.mockRestore();
  });

  // Test 20: tenant-scoped login resolves the tenant via API when enabled
  test('authorize should authenticate tenant users via tenantAPI when USE_BACKEND_API is on', async () => {
    mockUseBackendApi = true;

    (tenantAPI.getTenantBySubdomain as jest.Mock).mockResolvedValue({
      data: { id: 'tenant-2', subdomain: 'beta', name: 'Beta', plan_type: 'starter', status: 'active' },
    });

    const mockUser = {
      id: 'user-456',
      email: 'tenant-user@beta.com',
      name: 'Tenant User',
      role: 'tenant_admin',
      status: 'active',
      tenant_id: 'tenant-2',
    };

    // 1) First users SELECT (regular-user path) → empty
    // 2) set_tenant_context
    // 3) Tenant users SELECT → found
    (query as jest.Mock)
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({ rows: [mockUser] });

    // First login fetch succeeds; the tenant-path login fetch also succeeds.
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ access_token: 'tenant-jwt' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ access_token: 'tenant-jwt-2' }),
      }) as any;

    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    const result = await credentialsProvider.options.authorize({
      email: 'tenant-user@beta.com',
      password: 'pw',
      tenant_subdomain: 'beta',
    });

    expect(tenantAPI.getTenantBySubdomain).toHaveBeenCalledWith('beta');
    expect(result).toMatchObject({
      id: 'user-456',
      tenant_id: 'tenant-2',
      tenant_subdomain: 'beta',
      tenant_name: 'Beta',
      plan_type: 'starter',
    });
  });

  // Test 21: tenant login with an unknown subdomain returns null
  test('authorize should return null when the tenant subdomain is unknown', async () => {
    const mockUser = { id: 'u1', email: 'x@nope.com' };
    (query as jest.Mock)
      .mockResolvedValueOnce({ rows: [] }) // regular users
      .mockResolvedValueOnce({ rows: [] }) // tenants → none
      .mockResolvedValueOnce({ rows: [mockUser] }); // unused

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'jwt' }),
      })
    ) as any;

    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    const result = await credentialsProvider.options.authorize({
      email: 'x@nope.com',
      password: 'pw',
      tenant_subdomain: 'ghost',
    });

    expect(result).toBeNull();
  });

  // Test 22: invalid 2FA in the tenant path surfaces INVALID_2FA_CODE
  test('authorize should throw INVALID_2FA_CODE for invalid 2FA on tenant login', async () => {
    (query as jest.Mock)
      .mockResolvedValueOnce({ rows: [] }) // regular users
      .mockResolvedValueOnce({ rows: [{ id: 't1', subdomain: 'acme', name: 'A', plan_type: 'p' }] }) // tenant
      .mockResolvedValueOnce({ rows: [] }) // set_tenant_context
      .mockResolvedValueOnce({ rows: [] }); // tenant user lookup

    global.fetch = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ access_token: 'jwt' }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Invalid 2FA code' }),
      }) as any;

    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    await expect(
      credentialsProvider.options.authorize({
        email: 'tenant-user@acme.com',
        password: 'pw',
        tenant_subdomain: 'acme',
        totp_code: '000000',
      })
    ).rejects.toThrow('INVALID_2FA_CODE');
  });

  // Test 23: a generic backend failure in authorize returns null (no throw)
  test('authorize should swallow unexpected errors and return null', async () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
    (query as jest.Mock).mockRejectedValue(new Error('db exploded'));

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'jwt' }),
      })
    ) as any;

    const credentialsProvider = authOptions.providers.find((p: any) => p.id === 'credentials');
    const result = await credentialsProvider.options.authorize({
      email: 'user@example.com',
      password: 'pw',
    });

    expect(consoleSpy).toHaveBeenCalledWith('Authentication error:', expect.any(Error));
    expect(result).toBeNull();
    consoleSpy.mockRestore();
  });

  // Test 24: production requires NEXTAUTH_SECRET
  test('authOptions should throw in production without NEXTAUTH_SECRET', () => {
    const previousNodeEnv = process.env.NODE_ENV;
    const previousSecret = process.env.NEXTAUTH_SECRET;
    (process.env as any).NODE_ENV = 'production';
    delete process.env.NEXTAUTH_SECRET;
    try {
      expect(() => {
        jest.isolateModules(() => {
          require('../auth');
        });
      }).toThrow('CRITICAL: NEXTAUTH_SECRET is required in production');
    } finally {
      (process.env as any).NODE_ENV = previousNodeEnv;
      process.env.NEXTAUTH_SECRET = previousSecret;
    }
  });
});
