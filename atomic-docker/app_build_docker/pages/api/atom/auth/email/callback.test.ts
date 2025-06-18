import { NextApiRequest, NextApiResponse } from 'next';
import httpMocks from 'node-mocks-http';
import callbackGmailHandler from './atom/auth/email/callback'; // Update path
import { google } from 'googleapis';
import { saveAtomGmailTokens } from '../../../../../project/functions/atom-agent/_libs/token-utils';
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

const mockGetUserId = jest.fn(() => 'mock_user_id_gmail_callback');
const mockSessionAttachToReq = (req: any) => {
  req.session = { getUserId: mockGetUserId } as any;
};

const mockGetToken = jest.fn();
const mockGetUserInfo = jest.fn();
const mockSetCredentials = jest.fn(); // Added to mock setCredentials on OAuth2 client

jest.mock('googleapis', () => ({
  google: {
    auth: {
      OAuth2: jest.fn().mockImplementation(() => ({
        getToken: mockGetToken,
        setCredentials: mockSetCredentials, // Mock setCredentials
      })),
    },
    oauth2: jest.fn(() => ({ // Mock for google.oauth2('v2')
      userinfo: {
        get: mockGetUserInfo,
      },
    })),
  },
}));
const mockedGoogleAuthOAuth2 = google.auth.OAuth2 as jest.MockedClass<typeof google.auth.OAuth2>;

jest.mock('../../../../../project/functions/atom-agent/_libs/token-utils.ts', () => ({
  saveAtomGmailTokens: jest.fn(),
}));
const mockedSaveTokens = saveAtomGmailTokens as jest.Mock;

jest.mock('../../../../../project/functions/atom-agent/_libs/constants', () => ({
  ...jest.requireActual('../../../../../project/functions/atom-agent/_libs/constants'),
  ATOM_GMAIL_CLIENT_ID: 'test_gmail_client_id',
  ATOM_GMAIL_CLIENT_SECRET: 'test_gmail_client_secret',
  ATOM_GMAIL_REDIRECT_URI: 'test_gmail_redirect_uri',
}));

describe('/api/atom/auth/email/callback API Endpoint', () => {
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

  it('should save tokens and redirect on valid code, state, and userinfo fetch', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'GET',
      query: { code: 'valid_gmail_code', state: 'valid_gmail_state' },
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    const mockOAuthTokens = { access_token: 'mock_gmail_access', expiry_date: Date.now() + 3600000 };
    mockGetToken.mockResolvedValue({ tokens: mockOAuthTokens });
    mockGetUserInfo.mockResolvedValue({ data: { email: 'user@gmail.com' } });
    mockedSaveTokens.mockResolvedValue({ id: 'token_id', userId: 'mock_user_id_gmail_callback' });

    await callbackGmailHandler(mockReq, mockRes);

    expect(mockGetToken).toHaveBeenCalledWith('valid_gmail_code');
    expect(mockSetCredentials).toHaveBeenCalledWith(mockOAuthTokens); // Verify setCredentials was called
    expect(mockGetUserInfo).toHaveBeenCalledTimes(1);
    expect(mockedSaveTokens).toHaveBeenCalledWith(
      'mock_user_id_gmail_callback',
      expect.objectContaining({ access_token: 'mock_gmail_access' }),
      'user@gmail.com'
    );
    expect(mockRes.statusCode).toBe(302);
    expect(mockRes._getRedirectUrl()).toBe('/Settings/UserViewSettings?email_auth_success=true&atom_agent_email=true');
  });

  it('should proceed to save tokens even if userinfo fetch fails', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
        method: 'GET',
        query: { code: 'valid_code_no_email_fetch', state: 'valid_state_no_email' },
      });
      const mockRes = httpMocks.createResponse<NextApiResponse>();
      mockSessionAttachToReq(mockReq);

      const mockOAuthTokens = { access_token: 'mock_access_token_no_email', expiry_date: Date.now() + 3600000 };
      mockGetToken.mockResolvedValue({ tokens: mockOAuthTokens });
      mockGetUserInfo.mockRejectedValue(new Error("Failed to fetch userinfo")); // Simulate userinfo error
      mockedSaveTokens.mockResolvedValue({ id: 'token_id', userId: 'mock_user_id_gmail_callback' });

      await callbackGmailHandler(mockReq, mockRes);

      expect(mockGetToken).toHaveBeenCalledWith('valid_code_no_email_fetch');
      expect(mockGetUserInfo).toHaveBeenCalledTimes(1);
      expect(mockedSaveTokens).toHaveBeenCalledWith(
        'mock_user_id_gmail_callback',
        expect.objectContaining({ access_token: 'mock_access_token_no_email' }),
        null // Expecting null or undefined for email
      );
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('Error fetching Google user info for Atom Agent Gmail'), expect.any(Error));
      expect(mockRes.statusCode).toBe(302); // Should still redirect to success if token saving works
      expect(mockRes._getRedirectUrl()).toBe('/Settings/UserViewSettings?email_auth_success=true&atom_agent_email=true');
  });

  it('should redirect with error if Google returns error parameter', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET', query: { error: 'consent_required' } });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    await callbackGmailHandler(mockReq, mockRes);
    expect(mockRes._getRedirectUrl()).toBe('/Settings/UserViewSettings?email_auth_error=consent_required&atom_agent_email=true');
  });

  it('should redirect with error if code is missing', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET', query: { state: 'some_state' } });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    await callbackGmailHandler(mockReq, mockRes);
    expect(mockRes._getRedirectUrl()).toBe('/Settings/UserViewSettings?email_auth_error=no_code&atom_agent_email=true');
  });

  it('should redirect with error if getToken fails', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET', query: { code: 'bad_code', state: 's_state'} });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockGetToken.mockRejectedValue(new Error("getToken OAuth error"));
    await callbackGmailHandler(mockReq, mockRes);
    expect(mockRes._getRedirectUrl()).toContain('email_auth_error=');
  });

  it('should redirect with error if saveAtomGmailTokens fails', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET', query: { code: 'good_code', state: 's_state'} });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockGetToken.mockResolvedValue({ tokens: { access_token: 'valid_access', expiry_date: Date.now() + 1000 }});
    mockGetUserInfo.mockResolvedValue({ data: { email: 'user@example.com' }});
    mockedSaveTokens.mockRejectedValue(new Error("DB save failed"));
    await callbackGmailHandler(mockReq, mockRes);
    expect(mockRes._getRedirectUrl()).toContain('email_auth_error=token_storage_failed');
  });
});
