import { NextApiRequest, NextApiResponse } from 'next';
import httpMocks from 'node-mocks-http';
import initiateHandler from './atom/auth/calendar/initiate';
import { google } from 'googleapis';
import * as constants from '../../../../../project/functions/atom-agent/_libs/constants';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from 'supertokens-node/recipe/session/framework/express';

// Mocks
jest.mock('supertokens-node/nextjs', () => ({
  superTokensNextWrapper: jest.fn(async (middleware, req, res) => {
    let nextCalled = false;
    await middleware(async () => { nextCalled = true; });
    // Simplified mock: assumes if next is called by verifySession, the main handler logic runs.
  }),
}));

const mockVerifySessionMiddleware = jest.fn((req, res, next) => next());
jest.mock('supertokens-node/recipe/session/framework/express', () => ({
  verifySession: jest.fn(() => mockVerifySessionMiddleware),
}));
jest.mock('supertokens-node/recipe/session'); // For Session.SessionContainer type if needed

const mockGetUserId = jest.fn(() => 'mock_user_id_initiate');
const mockSessionAttachToReq = (req: any) => {
  req.session = { getUserId: mockGetUserId } as any;
};

const mockGenerateAuthUrl = jest.fn(() => 'http://mockedauthurl.com/with_state');
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

// Mock constants module
jest.mock('../../../../../project/functions/atom-agent/_libs/constants', () => ({
  ATOM_GOOGLE_CALENDAR_CLIENT_ID: 'test_client_id_initiate',
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET: 'test_client_secret_initiate',
  ATOM_GOOGLE_CALENDAR_REDIRECT_URI: 'test_redirect_uri_initiate',
  GOOGLE_CALENDAR_API_SCOPE: 'test_scope_initiate',
}));


describe('/api/atom/auth/calendar/initiate API Endpoint', () => {
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

  it('should successfully redirect to Google OAuth URL for authenticated GET request', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'GET',
      url: '/api/atom/auth/calendar/initiate',
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    await initiateHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockGetUserId).toHaveBeenCalledTimes(1);
    expect(mockedGoogleAuthOAuth2).toHaveBeenCalledWith(
      constants.ATOM_GOOGLE_CALENDAR_CLIENT_ID,
      constants.ATOM_GOOGLE_CALENDAR_CLIENT_SECRET,
      constants.ATOM_GOOGLE_CALENDAR_REDIRECT_URI
    );
    expect(mockGenerateAuthUrl).toHaveBeenCalledWith(expect.objectContaining({
      access_type: 'offline',
      scope: constants.GOOGLE_CALENDAR_API_SCOPE,
      state: expect.any(String), // Check that a state string is generated
    }));
    expect(mockRes.statusCode).toBe(302); // Redirect status
    expect(mockRes._getRedirectUrl()).toBe('http://mockedauthurl.com/with_state');
    // Check if state is a non-empty string
    const stateArg = mockGenerateAuthUrl.mock.calls[0][0].state;
    expect(stateArg).toBeDefined();
    expect(typeof stateArg).toBe('string');
    expect(stateArg.length).toBeGreaterThan(0);
  });

  it('should return 401 if user is not authenticated', async () => {
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => {
      res.statusCode = 401;
      res.writableEnded = true;
    });
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();

    await initiateHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockRes.statusCode).toBe(401);
    expect(mockGenerateAuthUrl).not.toHaveBeenCalled();
  });

  it('should return 405 if method is not GET', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    // No need to attach session if method check happens before Supertokens wrapper's main logic part

    // To accurately test this, we need to simulate how superTokensNextWrapper calls the inner handler.
    // If the method check is inside the logic passed to superTokensNextWrapper (which it is),
    // then verifySession will still run.
    mockSessionAttachToReq(mockReq); // Assume it runs for any method before our handler logic

    await initiateHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1); // Supertokens wrapper runs first
    expect(mockRes.statusCode).toBe(405);
    expect(mockGenerateAuthUrl).not.toHaveBeenCalled();
  });

  it('should return 500 if Google Client ID is missing', async () => {
    const originalClientId = constants.ATOM_GOOGLE_CALENDAR_CLIENT_ID;
    // @ts-ignore
    constants.ATOM_GOOGLE_CALENDAR_CLIENT_ID = undefined;

    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    await initiateHandler(mockReq, mockRes);

    expect(mockRes.statusCode).toBe(500);
    expect(mockRes._getJSONData().error).toContain('OAuth configuration error');
    expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('Google Calendar OAuth environment variables not set'));

    // @ts-ignore
    constants.ATOM_GOOGLE_CALENDAR_CLIENT_ID = originalClientId; // Restore
  });

  it('should return 500 if Redirect URI is missing', async () => {
    const originalRedirectUri = constants.ATOM_GOOGLE_CALENDAR_REDIRECT_URI;
    // @ts-ignore
    constants.ATOM_GOOGLE_CALENDAR_REDIRECT_URI = undefined;

    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    await initiateHandler(mockReq, mockRes);

    expect(mockRes.statusCode).toBe(500);
    expect(mockRes._getJSONData().error).toContain('OAuth configuration error');
    // @ts-ignore
    constants.ATOM_GOOGLE_CALENDAR_REDIRECT_URI = originalRedirectUri; // Restore
  });
});
