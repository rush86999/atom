import { NextApiRequest, NextApiResponse } from 'next';
import httpMocks from 'node-mocks-http';
import statusHandler from './atom/auth/calendar/status';
import { getAtomGoogleCalendarTokens } from '../../../../../project/functions/atom-agent/_libs/token-utils';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from 'supertokens-node/recipe/session/framework/express';

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

const mockGetUserId = jest.fn(() => 'mock_user_id_status');
const mockSessionAttachToReq = (req: any) => {
  req.session = { getUserId: mockGetUserId } as any;
};

jest.mock('../../../../../project/functions/atom-agent/_libs/token-utils.ts', () => ({
  getAtomGoogleCalendarTokens: jest.fn(),
}));
const mockedGetTokens = getAtomGoogleCalendarTokens as jest.Mock;

describe('/api/atom/auth/calendar/status API Endpoint', () => {
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

  it('should return { isConnected: true, email: ... } if tokens are found', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    mockedGetTokens.mockResolvedValue({
      access_token: 'mock_access_token',
      // Other token fields if necessary for the logic being tested
    });

    await statusHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockGetUserId).toHaveBeenCalledTimes(1);
    expect(mockedGetTokens).toHaveBeenCalledWith('mock_user_id_status');
    expect(mockRes.statusCode).toBe(200);
    expect(mockRes._getJSONData()).toEqual({ isConnected: true, email: "user_from_token@example.com" });
  });

  it('should return { isConnected: false } if no tokens are found', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    mockedGetTokens.mockResolvedValue(null);

    await statusHandler(mockReq, mockRes);

    expect(mockedGetTokens).toHaveBeenCalledWith('mock_user_id_status');
    expect(mockRes.statusCode).toBe(200);
    expect(mockRes._getJSONData()).toEqual({ isConnected: false });
  });

  it('should return { isConnected: false, error: ... } if getAtomGoogleCalendarTokens throws', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    mockedGetTokens.mockRejectedValue(new Error('DB connection error'));

    await statusHandler(mockReq, mockRes);

    expect(mockedGetTokens).toHaveBeenCalledWith('mock_user_id_status');
    expect(mockRes.statusCode).toBe(500);
    expect(mockRes._getJSONData()).toEqual({
      isConnected: false,
      error: 'Failed to retrieve calendar connection status.',
    });
    expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('Error fetching Atom Google Calendar token status'), 'DB connection error');
  });

  it('should return 401 if unauthenticated', async () => {
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => {
      res.statusCode = 401;
      res.writableEnded = true;
    });
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();

    await statusHandler(mockReq, mockRes);

    expect(mockRes.statusCode).toBe(401);
    expect(mockedGetTokens).not.toHaveBeenCalled();
  });

  it('should return 405 if method is not GET', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq); // Assume authenticated for this check

    await statusHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockRes.statusCode).toBe(405);
    expect(mockedGetTokens).not.toHaveBeenCalled();
  });
});
