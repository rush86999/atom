import { NextApiRequest, NextApiResponse } from 'next';
import httpMocks from 'node-mocks-http';
import callbackHandler from './atom/auth/calendar/callback';
import { google } from 'googleapis';
import { saveAtomGoogleCalendarTokens } from '../../../../../project/functions/atom-agent/_libs/token-utils';
import * as constants from '../../../../../project/functions/atom-agent/_libs/constants';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from 'supertokens-node/recipe/session/framework/express';

// Mocks
jest.mock('supertokens-node/nextjs', () => ({
  superTokensNextWrapper: jest.fn(async (middleware, req, res) => {
    let nextCalled = false;
    await middleware(async () => { nextCalled = true; });
    // This simplified mock assumes if next is called by verifySession, the main handler logic runs.
  }),
}));

const mockVerifySessionMiddleware = jest.fn((req, res, next) => next());
jest.mock('supertokens-node/recipe/session/framework/express', () => ({
  verifySession: jest.fn(() => mockVerifySessionMiddleware),
}));
jest.mock('supertokens-node/recipe/session'); // For Session.SessionContainer if needed for type

const mockGetUserId = jest.fn(() => 'mock_user_id_from_supertokens');
const mockSessionAttachToReq = (req: any) => {
  req.session = { getUserId: mockGetUserId } as any;
};

jest.mock('googleapis', () => ({
  google: {
    auth: {
      OAuth2: jest.fn().mockImplementation(() => ({
        getToken: jest.fn(),
      })),
    },
  },
}));
const mockedGoogleAuthOAuth2 = google.auth.OAuth2 as jest.MockedClass<typeof google.auth.OAuth2>;
const mockGetToken = new (mockedGoogleAuthOAuth2 as any)().getToken as jest.Mock;


jest.mock('../../../../../project/functions/atom-agent/_libs/token-utils.ts', () => ({
  saveAtomGoogleCalendarTokens: jest.fn(),
}));
const mockedSaveTokens = saveAtomGoogleCalendarTokens as jest.Mock;

jest.mock('../../../../../project/functions/atom-agent/_libs/constants', () => ({
  ATOM_GOOGLE_CALENDAR_CLIENT_ID: 'test_client_id',
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET: 'test_client_secret',
  ATOM_GOOGLE_CALENDAR_REDIRECT_URI: 'test_redirect_uri',
}));

describe('/api/atom/auth/calendar/callback API Endpoint', () => {
  let consoleErrorSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => {
      mockSessionAttachToReq(req);
      next();
    });
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it('should save tokens and redirect to success on valid code and state', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'GET',
      query: { code: 'valid_code', state: 'valid_state' },
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    const mockOAuthTokens = {
      access_token: 'mock_access_token',
      refresh_token: 'mock_refresh_token',
      expiry_date: Date.now() + 3600000,
      scope: 'scope',
      token_type: 'Bearer',
    };
    mockGetToken.mockResolvedValue({ tokens: mockOAuthTokens });
    mockedSaveTokens.mockResolvedValue({ id: 'token_id', userId: 'mock_user_id_from_supertokens' });

    await callbackHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockGetUserId).toHaveBeenCalledTimes(1);
    expect(mockedGoogleAuthOAuth2).toHaveBeenCalledWith('test_client_id', 'test_client_secret', 'test_redirect_uri');
    expect(mockGetToken).toHaveBeenCalledWith('valid_code');
    expect(mockedSaveTokens).toHaveBeenCalledWith('mock_user_id_from_supertokens', expect.objectContaining({
        access_token: 'mock_access_token',
        refresh_token: 'mock_refresh_token',
    }));
    expect(mockRes.statusCode).toBe(302); // Redirect status
    expect(mockRes._getRedirectUrl()).toBe('/Settings/UserViewSettings?calendar_auth_success=true&atom_agent=true');
  });

  it('should redirect to error if Google returns an error', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'GET',
      query: { error: 'access_denied' },
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    await callbackHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockGetUserId).toHaveBeenCalledTimes(1); // User ID still fetched before error check
    expect(mockRes.statusCode).toBe(302);
    expect(mockRes._getRedirectUrl()).toBe('/Settings/UserViewSettings?calendar_auth_error=access_denied&atom_agent=true');
    expect(mockGetToken).not.toHaveBeenCalled();
  });

  it('should redirect to error if code is missing', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'GET',
      query: { state: 'valid_state' }, // Missing code
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    await callbackHandler(mockReq, mockRes);

    expect(mockRes.statusCode).toBe(302);
    expect(mockRes._getRedirectUrl()).toBe('/Settings/UserViewSettings?calendar_auth_error=no_code&atom_agent=true');
  });

  it('should redirect to error if getToken throws', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'GET',
      query: { code: 'valid_code', state: 'valid_state' },
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    mockGetToken.mockRejectedValue(new Error('Google getToken failed'));

    await callbackHandler(mockReq, mockRes);

    expect(mockRes.statusCode).toBe(302);
    expect(mockRes._getRedirectUrl()).toContain('/Settings/UserViewSettings?calendar_auth_error=');
  });

  it('should redirect to error if saveAtomGoogleCalendarTokens throws', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'GET',
      query: { code: 'valid_code', state: 'valid_state' },
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    mockGetToken.mockResolvedValue({ tokens: { access_token: 'a', expiry_date: 1 } });
    mockedSaveTokens.mockRejectedValue(new Error('DB save failed'));

    await callbackHandler(mockReq, mockRes);

    expect(mockRes.statusCode).toBe(302);
    expect(mockRes._getRedirectUrl()).toContain('/Settings/UserViewSettings?calendar_auth_error=token_storage_failed');
  });

  it('should return 401 if unauthenticated', async () => {
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => {
      res.statusCode = 401;
      res.writableEnded = true;
    });
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();

    await callbackHandler(mockReq, mockRes);

    expect(mockRes.statusCode).toBe(401);
    expect(mockGetToken).not.toHaveBeenCalled();
  });
});
