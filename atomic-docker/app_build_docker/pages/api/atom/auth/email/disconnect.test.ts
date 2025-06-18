import { NextApiRequest, NextApiResponse } from 'next';
import httpMocks from 'node-mocks-http';
import disconnectGmailHandler from './atom/auth/email/disconnect'; // Update path
import { deleteAtomGmailTokens } from '../../../../../project/functions/atom-agent/_libs/token-utils';
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

const mockGetUserId = jest.fn(() => 'mock_user_id_gmail_disconnect');
const mockSessionAttachToReq = (req: any) => {
  req.session = { getUserId: mockGetUserId } as any;
};

jest.mock('../../../../../project/functions/atom-agent/_libs/token-utils.ts', () => ({
  deleteAtomGmailTokens: jest.fn(),
}));
const mockedDeleteGmailTokens = deleteAtomGmailTokens as jest.Mock;

describe('/api/atom/auth/email/disconnect API Endpoint', () => {
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

  it('should successfully disconnect and return 200 for authenticated POST', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockedDeleteGmailTokens.mockResolvedValue({ affected_rows: 1 });

    await disconnectGmailHandler(mockReq, mockRes);

    expect(mockedDeleteGmailTokens).toHaveBeenCalledWith('mock_user_id_gmail_disconnect');
    expect(mockRes.statusCode).toBe(200);
    expect(mockRes._getJSONData()).toEqual({
      success: true,
      message: 'Gmail account disconnected successfully for Atom Agent.',
    });
  });

  it('should return 500 if deleteAtomGmailTokens throws', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockedDeleteGmailTokens.mockRejectedValue(new Error("DB delete error"));

    await disconnectGmailHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(500);
    expect(mockRes._getJSONData().message).toContain("DB delete error");
  });

  it('should return 401 if unauthenticated', async () => {
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => {
      res.statusCode = 401; res.writableEnded = true;
    });
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    await disconnectGmailHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(401);
  });

  it('should return 405 if method is not POST', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    await disconnectGmailHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(405);
  });
});
