import { NextApiRequest, NextApiResponse } from 'next';
import httpMocks from 'node-mocks-http';
import deleteWebhookHandler from './atom/zapier/delete_webhook';
import { deleteZapierWebhook } from '../../../../../project/functions/atom-agent/_libs/zapier-utils';
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

const mockGetUserId = jest.fn(() => 'mock_user_id_zap_delete');
const mockSessionAttachToReq = (req: any) => {
  req.session = { getUserId: mockGetUserId } as any;
};

jest.mock('../../../../../project/functions/atom-agent/_libs/zapier-utils', () => ({
  deleteZapierWebhook: jest.fn(),
}));
const mockedDeleteZapierWebhook = deleteZapierWebhook as jest.Mock;

describe('/api/atom/zapier/delete_webhook API Endpoint', () => {
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

  it('should delete webhook and return 200 on valid POST with zap_id', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'POST',
      body: { zap_id: 'zap-to-delete-123' },
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockedDeleteZapierWebhook.mockResolvedValue({ affected_rows: 1 });

    await deleteWebhookHandler(mockReq, mockRes);

    expect(mockedDeleteZapierWebhook).toHaveBeenCalledWith('mock_user_id_zap_delete', 'zap-to-delete-123');
    expect(mockRes.statusCode).toBe(200);
    expect(mockRes._getJSONData()).toEqual({
      success: true,
      message: 'Zapier webhook deleted successfully.',
      affected_rows: 1,
    });
  });

  it('should return 404 if webhook not found or already deleted', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST', body: { zap_id: 'zap-not-found-456' } });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockedDeleteZapierWebhook.mockResolvedValue({ affected_rows: 0 });
    await deleteWebhookHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(404);
    expect(mockRes._getJSONData().error).toBe('Zapier webhook not found or already deleted.');
  });

  it('should return 400 if zap_id is missing', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST', body: {} });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    await deleteWebhookHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(400);
    expect(mockRes._getJSONData().error).toBe('Missing zap_id in request body');
  });

  it('should return 500 if deleteZapierWebhook throws an error', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST', body: { zap_id: 'zap-error-789' } });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockedDeleteZapierWebhook.mockRejectedValue(new Error("DB delete error for Zapier"));
    await deleteWebhookHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(500);
    expect(mockRes._getJSONData().error).toContain("DB delete error for Zapier");
  });

  it('should return 401 if unauthenticated', async () => {
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => { res.statusCode = 401; res.writableEnded = true; });
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST', body: { zap_id: 'any_id' } });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    await deleteWebhookHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(401);
  });
});
