import { NextApiRequest, NextApiResponse } from 'next';
import httpMocks from 'node-mocks-http';
import addWebhookHandler from './atom/zapier/add_webhook';
import { addZapierWebhook } from '../../../../../project/functions/atom-agent/_libs/zapier-utils';
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

const mockGetUserId = jest.fn(() => 'mock_user_id_zap_add');
const mockSessionAttachToReq = (req: any) => {
  req.session = { getUserId: mockGetUserId } as any;
};

jest.mock('../../../../../project/functions/atom-agent/_libs/zapier-utils', () => ({
  addZapierWebhook: jest.fn(),
}));
const mockedAddZapierWebhook = addZapierWebhook as jest.Mock;

describe('/api/atom/zapier/add_webhook API Endpoint', () => {
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

  it('should add webhook and return 201 on valid POST', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'POST',
      body: { zap_name: 'MyNewZap', webhook_url: 'https://hooks.zapier.com/hooks/catch/123/abc/' },
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    const mockAddedWebhook = { id: 'zap-id-1', zap_name: 'MyNewZap' };
    mockedAddZapierWebhook.mockResolvedValue(mockAddedWebhook);

    await addWebhookHandler(mockReq, mockRes);

    expect(mockedAddZapierWebhook).toHaveBeenCalledWith('mock_user_id_zap_add', 'MyNewZap', 'https://hooks.zapier.com/hooks/catch/123/abc/');
    expect(mockRes.statusCode).toBe(201);
    expect(mockRes._getJSONData()).toEqual({
      success: true,
      message: 'Zapier webhook added/updated successfully.',
      webhook: mockAddedWebhook,
    });
  });

  it('should return 400 if zap_name is missing', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST', body: { webhook_url: 'https://hooks.zapier.com/hooks/catch/123/abc/' } });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    await addWebhookHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(400);
    expect(mockRes._getJSONData().error).toBe('Missing zap_name or webhook_url in request body');
  });

  it('should return 400 if webhook_url is invalid', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST', body: { zap_name: 'Test', webhook_url: 'invalid-url' } });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    await addWebhookHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(400);
    expect(mockRes._getJSONData().error).toBe('Invalid webhook_url format');
  });

  it('should return 409 if addZapierWebhook throws duplicate name error', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST', body: { zap_name: 'DuplicateZap', webhook_url: 'https://hooks.zapier.com/hooks/catch/123/def/' } });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockedAddZapierWebhook.mockRejectedValue(new Error('A Zap with the name "DuplicateZap" already exists.'));
    await addWebhookHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(409);
    expect(mockRes._getJSONData().error).toBe('A Zap with the name "DuplicateZap" already exists.');
  });

  it('should return 500 if addZapierWebhook throws encryption error', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST', body: { zap_name: 'EncFailZap', webhook_url: 'https://hooks.zapier.com/hooks/catch/123/ghi/' } });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockedAddZapierWebhook.mockRejectedValue(new Error('Webhook URL encryption failed.'));
    await addWebhookHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(500);
    expect(mockRes._getJSONData().error).toBe('Failed to secure webhook information.');
  });


  it('should return 401 if unauthenticated', async () => {
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => { res.statusCode = 401; res.writableEnded = true; });
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'POST', body: { zap_name: 'Test', webhook_url: 'https://example.com' } });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    await addWebhookHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(401);
  });
});
