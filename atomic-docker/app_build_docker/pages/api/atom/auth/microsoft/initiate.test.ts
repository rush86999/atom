import { NextApiRequest, NextApiResponse } from 'next';
import httpMocks from 'node-mocks-http';
import initiateMicrosoftHandler from './atom/auth/microsoft/initiate'; // Update path
import * as constants from '../../../../../project/functions/atom-agent/_libs/constants';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from 'supertokens-node/recipe/session/framework/express';
import crypto from 'crypto'; // Used by the handler

// Mocks
jest.mock('supertokens-node/nextjs', () => ({
  superTokensNextWrapper: jest.fn(async (middleware, req, res) => {
    let nextCalled = false;
    await middleware(async () => { nextCalled = true; });
    // Simplified mock
  }),
}));

const mockVerifySessionMiddleware = jest.fn((req, res, next) => next());
jest.mock('supertokens-node/recipe/session/framework/express', () => ({
  verifySession: jest.fn(() => mockVerifySessionMiddleware),
}));
jest.mock('supertokens-node/recipe/session');

const mockGetUserId = jest.fn(() => 'mock_user_id_ms_initiate');
const mockSessionAttachToReq = (req: any) => {
  req.session = { getUserId: mockGetUserId } as any;
};

// Mock constants specific to Microsoft Graph
// We need to ensure the actual values from the module are overridden for the test.
const mockMsGraphConstants = {
  ATOM_MSGRAPH_CLIENT_ID: 'test_ms_client_id',
  ATOM_MSGRAPH_REDIRECT_URI: 'http://localhost:3000/api/atom/auth/microsoft/callback',
  MSGRAPH_API_SCOPES: ['User.Read', 'Mail.Send', 'offline_access'],
  ATOM_MSGRAPH_TENANT_ID: 'common_test_tenant',
  MSGRAPH_OAUTH_AUTHORITY_BASE: 'https://login.microsoftonline.com/',
};

jest.mock('../../../../../project/functions/atom-agent/_libs/constants', () => ({
  ...jest.requireActual('../../../../../project/functions/atom-agent/_libs/constants'), // retain other constants
  ...mockMsGraphConstants,
}));


describe('/api/atom/auth/microsoft/initiate API Endpoint', () => {
  let consoleErrorSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => {
      mockSessionAttachToReq(req);
      next();
    });
     // Reset constants to mock values for each test if they were changed
     Object.entries(mockMsGraphConstants).forEach(([key, value]) => {
        Object.defineProperty(constants, key, { value, configurable: true, writable: true });
    });
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it('should successfully redirect to Microsoft OAuth URL', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    await initiateMicrosoftHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockGetUserId).toHaveBeenCalledTimes(1);

    expect(mockRes.statusCode).toBe(302); // Redirect status
    const redirectUrl = new URL(mockRes._getRedirectUrl());
    expect(redirectUrl.origin).toBe(mockMsGraphConstants.MSGRAPH_OAUTH_AUTHORITY_BASE.slice(0,-1)); // remove trailing /
    expect(redirectUrl.pathname).toBe(`/${mockMsGraphConstants.ATOM_MSGRAPH_TENANT_ID}/oauth2/v2.0/authorize`);
    expect(redirectUrl.searchParams.get('client_id')).toBe(mockMsGraphConstants.ATOM_MSGRAPH_CLIENT_ID);
    expect(redirectUrl.searchParams.get('response_type')).toBe('code');
    expect(redirectUrl.searchParams.get('redirect_uri')).toBe(mockMsGraphConstants.ATOM_MSGRAPH_REDIRECT_URI);
    expect(redirectUrl.searchParams.get('response_mode')).toBe('query');
    expect(redirectUrl.searchParams.get('scope')).toBe(mockMsGraphConstants.MSGRAPH_API_SCOPES.join(' '));
    expect(redirectUrl.searchParams.get('state')).toEqual(expect.any(String));
    expect(redirectUrl.searchParams.get('state')?.length).toBe(32); // crypto.randomBytes(16).toString('hex')
  });

  it('should return 401 if unauthenticated', async () => {
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => {
      res.statusCode = 401;
      res.writableEnded = true;
    });
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    await initiateMicrosoftHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(401);
  });

  it('should return 405 if method is not GET', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    await initiateMicrosoftHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(405);
  });

  it('should return 500 if MS Graph Client ID is missing', async () => {
    Object.defineProperty(constants, 'ATOM_MSGRAPH_CLIENT_ID', { value: undefined });
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    await initiateMicrosoftHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(500);
    expect(mockRes._getJSONData().error).toContain('OAuth configuration error');
  });
});
