import { NextApiRequest, NextApiResponse } from 'next';
import httpMocks from 'node-mocks-http';
import initiateGmailHandler from './atom/auth/email/initiate'; // Update path
import { google } from 'googleapis';
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

const mockGetUserId = jest.fn(() => 'mock_user_id_gmail_initiate');
const mockSessionAttachToReq = (req: any) => {
  req.session = { getUserId: mockGetUserId } as any;
};

const mockGenerateAuthUrl = jest.fn(() => 'http://mocked_gmail_authurl.com/with_state');
jest.mock('googleapis', () => ({
  google: {
    auth: {
      OAuth2: jest.fn().mockImplementation(() => ({
        generateAuthUrl: mockGenerateAuthUrl,
      })),
    },
  },
}));
const mockedGoogleAuthOAuth2 = google.auth.OAuth2 as jest.MockedClass<typeof google.auth.OAuth2>;

// Mock constants specific to Gmail
jest.mock('../../../../../project/functions/atom-agent/_libs/constants', () => ({
  ...jest.requireActual('../../../../../project/functions/atom-agent/_libs/constants'), // retain other constants
  ATOM_GMAIL_CLIENT_ID: 'test_gmail_client_id',
  ATOM_GMAIL_CLIENT_SECRET: 'test_gmail_client_secret',
  ATOM_GMAIL_REDIRECT_URI: 'test_gmail_redirect_uri',
  GMAIL_API_SCOPES: ['scope1_gmail', 'scope2_gmail'],
}));

describe('/api/atom/auth/email/initiate API Endpoint', () => {
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

  it('should successfully redirect to Google OAuth URL for Gmail', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    await initiateGmailHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockGetUserId).toHaveBeenCalledTimes(1);
    expect(mockedGoogleAuthOAuth2).toHaveBeenCalledWith(
      constants.ATOM_GMAIL_CLIENT_ID,
      constants.ATOM_GMAIL_CLIENT_SECRET,
      constants.ATOM_GMAIL_REDIRECT_URI
    );
    expect(mockGenerateAuthUrl).toHaveBeenCalledWith(expect.objectContaining({
      access_type: 'offline',
      scope: constants.GMAIL_API_SCOPES,
      state: expect.any(String),
    }));
    expect(mockRes.statusCode).toBe(302);
    expect(mockRes._getRedirectUrl()).toBe('http://mocked_gmail_authurl.com/with_state');
  });

  it('should return 401 if unauthenticated', async () => {
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => {
      res.statusCode = 401;
      res.writableEnded = true;
    });
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    await initiateGmailHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(401);
    expect(mockGenerateAuthUrl).not.toHaveBeenCalled();
  });

  it('should return 405 if method is not GET', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    await initiateGmailHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(405);
    expect(mockGenerateAuthUrl).not.toHaveBeenCalled();
  });

  it('should return 500 if Gmail Client ID is missing', async () => {
    const originalClientId = constants.ATOM_GMAIL_CLIENT_ID;
    // @ts-ignore
    constants.ATOM_GMAIL_CLIENT_ID = undefined;
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    await initiateGmailHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(500);
    expect(mockRes._getJSONData().error).toContain('OAuth configuration error for Atom Agent Gmail');
    // @ts-ignore
    constants.ATOM_GMAIL_CLIENT_ID = originalClientId; // Restore
  });
});
