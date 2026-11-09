jest.mock('next-auth', () => ({ __esModule: true, default: jest.fn() }));
jest.mock('@/lib/db', () => ({ query: jest.fn() }));
jest.mock('@/lib/api', () => ({ USE_BACKEND_API:true, adminAPI:{getAdminUsers:jest.fn(),updateAdminLastLogin:jest.fn()},tenantAPI:{getTenantBySubdomain:jest.fn()} }));
import { authOptions } from '@/pages/api/auth/[...nextauth]';
import { query } from '@/lib/db';
import { authOptions as sharedOptions } from '@/lib/auth';
import { adminAPI } from '@/lib/api';
const provider = authOptions.providers.find((p: any) => p.id === 'credentials') as any;
const authorize = (credentials: any) => provider.options.authorize(credentials, {});
const reply = (body: any, status = 200) => ({ ok: status === 200, status, headers: { get: () => 'application/json' }, json: async () => body });
const identity = { id: 'canonical-user-01', email: 'owner@example.invalid', first_name: 'Canonical', last_name: 'Owner', role: 'member', status: 'active', workspace_id: 'workspace-01' };
const credentials = { email: 'input@example.invalid', password: 'synthetic-only' };
beforeEach(() => { jest.clearAllMocks(); global.fetch = jest.fn(); });
it('uses authenticated canonical identity rather than the submitted email or a fabricated id', async () => {
 (global.fetch as jest.Mock).mockResolvedValueOnce(reply({access_token:'synthetic-bearer'})).mockResolvedValueOnce(reply(identity));
 const user = await authorize(credentials);
 expect(user).toMatchObject({ id: identity.id, email: identity.email, name: 'Canonical Owner', role:'member', workspace_id:identity.workspace_id, token:'synthetic-bearer' });
 expect(global.fetch).toHaveBeenNthCalledWith(2, expect.stringMatching(/\/api\/auth\/me$/), expect.objectContaining({headers: expect.objectContaining({Authorization:'Bearer synthetic-bearer'})}));
 expect(query).not.toHaveBeenCalled();
});
it.each([reply({},401), reply({email:identity.email}), reply({...identity,status:'suspended'})])('does not mint a browser identity when canonical authorization is missing or refused', async response => {
 (global.fetch as jest.Mock).mockResolvedValueOnce(reply({access_token:'synthetic-bearer',user:identity})).mockResolvedValueOnce(response);
 expect(await authorize(credentials)).toBeNull();
 expect(query).not.toHaveBeenCalled();
});
it('does not write a parallel JavaScript database during a credentials JWT callback', async () => {
 const token = await authOptions.callbacks!.jwt!({token:{}, user:{id:identity.id,email:identity.email,token:'synthetic-bearer'},account:{provider:'credentials'}} as any);
 expect(token).toMatchObject({id:identity.id,backendToken:'synthetic-bearer'});
 expect(query).not.toHaveBeenCalled();
});

describe('shared credentials consumer uses the same canonical authority', () => {
 const sharedProvider = sharedOptions.providers.find((p:any) => p.id === 'credentials') as any;
 const sharedAuthorize = (c:any) => sharedProvider.options.authorize(c, {});
 it('does not promote an admin-shaped submitted email from an unrelated admin row', async () => {
  (global.fetch as jest.Mock).mockResolvedValueOnce(reply({access_token:'synthetic-bearer'})).mockResolvedValueOnce(reply(identity));
  (adminAPI.getAdminUsers as jest.Mock).mockResolvedValue({data:[{id:'foreign-admin',email:'admin@example.com',status:'active',permissions:['*']}]});
  const user = await sharedAuthorize({...credentials,email:'admin@example.com'});
  expect(user).toMatchObject({id:identity.id,email:identity.email,role:'member',workspace_id:identity.workspace_id});
  expect(adminAPI.getAdminUsers).not.toHaveBeenCalled();
  expect(query).not.toHaveBeenCalled();
 });
 it('does not consult a parallel database or fabricate a successful identity when /me refuses', async () => {
  (global.fetch as jest.Mock).mockResolvedValueOnce(reply({access_token:'synthetic-bearer'})).mockResolvedValueOnce(reply({},401));
  (query as jest.Mock).mockResolvedValue({rows:[{id:'foreign-user',email:credentials.email,role:'super_admin',status:'active'}]});
  expect(await sharedAuthorize(credentials)).toBeNull();
  expect(query).not.toHaveBeenCalled();
 });
 it('does not retry a failed login under a submitted tenant hint', async () => {
  (global.fetch as jest.Mock).mockResolvedValue(reply({},401));
  (query as jest.Mock).mockResolvedValue({rows:[{id:'foreign-tenant',status:'active'}]});
  expect(await sharedAuthorize({...credentials,tenant_subdomain:'foreign'})).toBeNull();
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(query).not.toHaveBeenCalled();
 });
});
