import { NextApiRequest, NextApiResponse } from 'next';
import httpMocks from 'node-mocks-http';
import statusGmailHandler from './atom/auth/email/status'; // Update path
import { getAtomGmailTokens } from '../../../../../project/functions/atom-agent/_libs/token-utils';
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

const mockGetUserId = jest.fn(() => 'mock_user_id_gmail_status');
const mockSessionAttachToReq = (req: any) => {
  req.session = { getUserId: mockGetUserId } as any;
};

jest.mock('../../../../../project/functions/atom-agent/_libs/token-utils.ts', () => ({
  getAtomGmailTokens: jest.fn(),
}));
const mockedGetGmailTokens = getAtomGmailTokens as jest.Mock;

describe('/api/atom/auth/email/status API Endpoint', () => {
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

  it('should return { isConnected: true, email } if tokens with email are found', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockedGetGmailTokens.mockResolvedValue({ access_token: 'mock_gmail_access', appEmail: 'user@gmail.com' });

    await statusGmailHandler(mockReq, mockRes);

    expect(mockedGetGmailTokens).toHaveBeenCalledWith('mock_user_id_gmail_status');
    expect(mockRes.statusCode).toBe(200);
    expect(mockRes._getJSONData()).toEqual({ isConnected: true, email: 'user@gmail.com' });
  });

  it('should return { isConnected: true, email: null } if tokens found but no appEmail', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockedGetGmailTokens.mockResolvedValue({ access_token: 'mock_gmail_access', appEmail: null });

    await statusGmailHandler(mockReq, mockRes);
    expect(mockRes._getJSONData()).toEqual({ isConnected: true, email: null });
  });

  it('should return { isConnected: false } if no tokens are found', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockedGetGmailTokens.mockResolvedValue(null);

    await statusGmailHandler(mockReq, mockRes);
    expect(mockRes._getJSONData()).toEqual({ isConnected: false });
  });

  it('should return 500 if getAtomGmailTokens throws', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockedGetGmailTokens.mockRejectedValue(new Error("DB error"));

    await statusGmailHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(500);
    expect(mockRes._getJSONData().error).toBe('Failed to retrieve Gmail connection status.');
  });

  it('should return 401 if unauthenticated', async () => {
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => {
      res.statusCode = 401; res.writableEnded = true;
    });
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    await statusGmailHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(401);
  });
});
