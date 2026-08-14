/**
 * lib/auth.ts — supplemental branch coverage:
 * tenantAPI rejection fallback (line 165) and 2FA_REQUIRED in the tenant path
 * (lines 224-226).
 */

import { authOptions } from '../auth';

jest.mock('../db', () => ({ query: jest.fn() }));

let mockUseBackendApi = false;
jest.mock('../api', () => ({
  get USE_BACKEND_API() {
    return mockUseBackendApi;
  },
  adminAPI: { getAdminUsers: jest.fn(), updateAdminLastLogin: jest.fn() },
  tenantAPI: { getTenantBySubdomain: jest.fn(), getTenantById: jest.fn() },
}));

jest.mock('next-auth', () => ({
  __esModule: true,
  default: jest.fn(),
  NextAuth: jest.fn(),
}));

import { query } from '../db';
import { tenantAPI } from '../api';

const credentialsProvider: any = authOptions.providers.find((p: any) => p.id === 'credentials');

describe('lib/auth tenant fallback branches', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, 'error').mockImplementation(() => {});
    mockUseBackendApi = true;
  });

  test('falls back to the DB when tenantAPI rejects', async () => {
    (tenantAPI.getTenantBySubdomain as jest.Mock).mockRejectedValue(new Error('tenant api down'));

    const mockTenant = { id: 't-1', subdomain: 'beta', name: 'Beta', plan_type: 'starter', status: 'active' };
    const mockUser = {
      id: 'user-1',
      email: 'u@beta.com',
      name: 'U',
      role: 'tenant_admin',
      status: 'active',
      tenant_id: 't-1',
    };
    (query as jest.Mock)
      .mockResolvedValueOnce({ rows: [] }) // regular-user path
      .mockResolvedValueOnce({ rows: [mockTenant] }) // tenants DB fallback
      .mockResolvedValueOnce({ rows: [] }) // set_tenant_context
      .mockResolvedValueOnce({ rows: [mockUser] }); // tenant user

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ access_token: 'jwt' }),
      })
    ) as any;

    const result = await credentialsProvider.options.authorize({
      email: 'u@beta.com',
      password: 'pw',
      tenant_subdomain: 'beta',
    });

    expect(tenantAPI.getTenantBySubdomain).toHaveBeenCalledWith('beta');
    expect(console.error).toHaveBeenCalledWith('Failed to fetch tenant from API:', expect.any(Error));
    expect(result).toMatchObject({ id: 'user-1', tenant_subdomain: 'beta', tenant_name: 'Beta' });
  });

  test('throws 2FA_REQUIRED from the tenant login path', async () => {
    (tenantAPI.getTenantBySubdomain as jest.Mock).mockResolvedValue({
      data: { id: 't-2', subdomain: 'gamma', name: 'Gamma', plan_type: 'pro', status: 'active' },
    });

    (query as jest.Mock)
      .mockResolvedValueOnce({ rows: [] }) // regular-user path
      .mockResolvedValueOnce({ rows: [] }) // set_tenant_context
      .mockResolvedValueOnce({ rows: [] }); // unused

    global.fetch = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ access_token: 'first' }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 200,
        json: () => Promise.resolve({ two_factor_required: true }),
      }) as any;

    await expect(
      credentialsProvider.options.authorize({
        email: 'u@gamma.com',
        password: 'pw',
        tenant_subdomain: 'gamma',
      })
    ).rejects.toThrow('2FA_REQUIRED');
  });
});
