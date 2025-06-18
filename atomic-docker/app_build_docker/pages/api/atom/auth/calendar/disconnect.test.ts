import { NextApiRequest, NextApiResponse } from 'next';
import httpMocks from 'node-mocks-http';
import disconnectHandler from './atom/auth/calendar/disconnect';
import { deleteAtomGoogleCalendarTokens } from '../../../../../project/functions/atom-agent/_libs/token-utils';
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

const mockGetUserId = jest.fn(() => 'mock_user_id_disconnect');
const mockSessionAttachToReq = (req: any) => {
  req.session = { getUserId: mockGetUserId } as any;
};

jest.mock('../../../../../project/functions/atom-agent/_libs/token-utils.ts', () => ({
  deleteAtomGoogleCalendarTokens: jest.fn(),
}));
const mockedDeleteTokens = deleteAtomGoogleCalendarTokens as jest.Mock;

describe('/api/atom/auth/calendar/disconnect API Endpoint', () => {
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

  it('should successfully disconnect and return 200 for authenticated POST request', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'POST',
      url: '/api/atom/auth/calendar/disconnect',
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    mockedDeleteTokens.mockResolvedValue({ affected_rows: 1 });

    await disconnectHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockGetUserId).toHaveBeenCalledTimes(1);
    expect(mockedDeleteTokens).toHaveBeenCalledWith('mock_user_id_disconnect');
    expect(mockRes.statusCode).toBe(200);
    expect(mockRes._getJSONData()).toEqual({
      success: true,
      message: 'Google Calendar disconnected successfully for Atom Agent.',
    });
  });

  it('should return 500 if deleteAtomGoogleCalendarTokens throws an error', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    const errorMessage = 'Database deletion failed';
    mockedDeleteTokens.mockRejectedValue(new Error(errorMessage));

    await disconnectHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockGetUserId).toHaveBeenCalledTimes(1);
    expect(mockedDeleteTokens).toHaveBeenCalledWith('mock_user_id_disconnect');
    expect(mockRes.statusCode).toBe(500);
    expect(mockRes._getJSONData().success).toBe(false);
    expect(mockRes._getJSONData().message).toContain(errorMessage);
    expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('Error during Google Calendar disconnect'), errorMessage);
  });

  it('should return 401 if user is not authenticated', async () => {
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => {
      res.statusCode = 401;
      res.writableEnded = true;
    });
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();

    await disconnectHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockRes.statusCode).toBe(401);
    expect(mockedDeleteTokens).not.toHaveBeenCalled();
  });

  it('should return 405 if method is not POST', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq); // Supertokens wrapper runs first

    await disconnectHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockRes.statusCode).toBe(405);
    expect(mockedDeleteTokens).not.toHaveBeenCalled();
  });
});
