import { NextApiRequest, NextApiResponse } from 'next';
import httpMocks from 'node-mocks-http';
import callbackMicrosoftHandler from './atom/auth/microsoft/callback'; // Update path
import got from 'got';
import { saveAtomMicrosoftGraphTokens } from '../../../../../project/functions/atom-agent/_libs/token-utils';
import * as constants from '../../../../../project/functions/atom-agent/_libs/constants';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from 'supertokens-node/recipe/session/framework/express';

// Mocks
jest.mock('supertokens-node/nextjs', () => ({
  superTokensNextWrapper: jest.fn(async (middleware, req, res) => {
    let nextCalled = false;
    await middleware(async () => { nextCalled = true; });
  }),
}));
const mockVerifySessionMiddleware = jest.fn((req, res, next) => next());
jest.mock('supertokens-node/recipe/session/framework/express', () => ({
  verifySession: jest.fn(() => mockVerifySessionMiddleware),
}));
jest.mock('supertokens-node/recipe/session');

const mockGetUserId = jest.fn(() => 'mock_user_id_ms_callback');
const mockSessionAttachToReq = (req: any) => {
  req.session = { getUserId: mockGetUserId } as any;
};

jest.mock('got');
const mockedGot = got as jest.Mocked<typeof got>;

jest.mock('../../../../../project/functions/atom-agent/_libs/token-utils.ts', () => ({
  saveAtomMicrosoftGraphTokens: jest.fn(),
}));
const mockedSaveTokens = saveAtomMicrosoftGraphTokens as jest.Mock;

const mockMsGraphConstants = {
  ATOM_MSGRAPH_CLIENT_ID: 'test_ms_client_id_cb',
  ATOM_MSGRAPH_CLIENT_SECRET: 'test_ms_client_secret_cb',
  ATOM_MSGRAPH_REDIRECT_URI: 'http://localhost:3000/api/atom/auth/microsoft/callback',
  ATOM_MSGRAPH_TENANT_ID: 'common_test_tenant_cb',
  MSGRAPH_OAUTH_AUTHORITY_BASE: 'https://login.microsoftonline.com/',
  MSGRAPH_API_SCOPES: ['User.Read', 'Mail.Send', 'offline_access'],
};
jest.mock('../../../../../project/functions/atom-agent/_libs/constants', () => ({
  ...jest.requireActual('../../../../../project/functions/atom-agent/_libs/constants'),
  ...mockMsGraphConstants,
}));


describe('/api/atom/auth/microsoft/callback API Endpoint', () => {
  let consoleErrorSpy: jest.SpyInstance;
  beforeEach(() => {
    jest.clearAllMocks();
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => {
      mockSessionAttachToReq(req);
      next();
    });
  });
  afterEach(() => { consoleErrorSpy.mockRestore(); });

  it('should save tokens and redirect on valid code, state, token exchange, and userinfo fetch', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'GET',
      query: { code: 'valid_ms_code', state: 'valid_ms_state' },
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    const mockMsTokens = { access_token: 'ms_access_token', refresh_token: 'ms_refresh_token', expires_in: 3600, scope: 'User.Read Mail.Send offline_access', token_type: 'Bearer' };
    const mockMsUserInfo = { mail: 'user@microsoft.com', userPrincipalName: 'user_upn@microsoft.com' };

    mockedGot.post.mockResolvedValueOnce({ body: mockMsTokens } as any); // For token exchange
    mockedGot.get.mockResolvedValueOnce({ body: mockMsUserInfo } as any);  // For user info (/me)
    mockedSaveTokens.mockResolvedValue({ id: 'token_id', userId: 'mock_user_id_ms_callback' });

    await callbackMicrosoftHandler(mockReq, mockRes);

    expect(mockedGot.post).toHaveBeenCalledWith(
      `${mockMsGraphConstants.MSGRAPH_OAUTH_AUTHORITY_BASE}${mockMsGraphConstants.ATOM_MSGRAPH_TENANT_ID}/oauth2/v2.0/token`,
      expect.objectContaining({
        form: expect.objectContaining({ client_id: mockMsGraphConstants.ATOM_MSGRAPH_CLIENT_ID, code: 'valid_ms_code' })
      })
    );
    expect(mockedGot.get).toHaveBeenCalledWith(
      'https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName',
      expect.objectContaining({ headers: { 'Authorization': `Bearer ms_access_token` }})
    );
    expect(mockedSaveTokens).toHaveBeenCalledWith(
      'mock_user_id_ms_callback',
      expect.objectContaining({ access_token: 'ms_access_token', refresh_token: 'ms_refresh_token' }),
      'user@microsoft.com' // mail takes precedence
    );
    expect(mockRes.statusCode).toBe(302);
    expect(mockRes._getRedirectUrl()).toBe('/Settings/UserViewSettings?mgraph_auth_success=true&atom_agent_mgraph=true');
  });

  it('should use userPrincipalName if mail is null from userinfo', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
        method: 'GET', query: { code: 'valid_ms_code_upn', state: 'valid_ms_state_upn' },
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    const mockMsTokens = { access_token: 'ms_access_token_upn', expires_in: 3600 };
    const mockMsUserInfo = { mail: null, userPrincipalName: 'user_upn_only@microsoft.com' };
    mockedGot.post.mockResolvedValueOnce({ body: mockMsTokens } as any);
    mockedGot.get.mockResolvedValueOnce({ body: mockMsUserInfo } as any);
    mockedSaveTokens.mockResolvedValue({ id: 'token_id_upn', userId: 'mock_user_id_ms_callback' });

    await callbackMicrosoftHandler(mockReq, mockRes);
    expect(mockedSaveTokens).toHaveBeenCalledWith(
        expect.anything(), expect.anything(), 'user_upn_only@microsoft.com'
    );
  });

  it('should redirect with error if MS returns error parameter', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET', query: { error: 'interaction_required', error_description: 'User consent needed' } });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    await callbackMicrosoftHandler(mockReq, mockRes);
    expect(mockRes._getRedirectUrl()).toBe('/Settings/UserViewSettings?mgraph_auth_error=interaction_required&mgraph_error_desc=User%20consent%20needed&atom_agent_mgraph=true');
  });

  it('should redirect with error if code is missing', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET', query: { state: 'some_state' } });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    await callbackMicrosoftHandler(mockReq, mockRes);
    expect(mockRes._getRedirectUrl()).toBe('/Settings/UserViewSettings?mgraph_auth_error=no_code&atom_agent_mgraph=true');
  });

  it('should redirect with error if token exchange fails', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET', query: { code: 'bad_ms_code', state: 's_state'} });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockedGot.post.mockRejectedValue({ response: { body: {error: 'invalid_grant', error_description: 'Bad code'} } } as any);
    await callbackMicrosoftHandler(mockReq, mockRes);
    expect(mockRes._getRedirectUrl()).toContain('mgraph_auth_error=invalid_grant');
  });

  it('should redirect with error if saveAtomMicrosoftGraphTokens fails', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET', query: { code: 'good_ms_code', state: 's_state'} });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockedGot.post.mockResolvedValue({ body: { access_token: 'token', expires_in: 300 } } as any); // Token exchange OK
    mockedGot.get.mockResolvedValue({ body: { mail: 'user@ms.com'} } as any); // UserInfo OK
    mockedSaveTokens.mockRejectedValue(new Error("DB save failed for MS"));
    await callbackMicrosoftHandler(mockReq, mockRes);
    expect(mockRes._getRedirectUrl()).toContain('mgraph_auth_error=token_storage_failed');
  });
});
