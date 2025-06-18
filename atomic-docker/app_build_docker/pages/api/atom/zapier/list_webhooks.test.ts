import { NextApiRequest, NextApiResponse } from 'next';
import httpMocks from 'node-mocks-http';
import listWebhooksHandler from './atom/zapier/list_webhooks';
import { listZapierWebhooks, ZapierWebhook } from '../../../../../project/functions/atom-agent/_libs/zapier-utils';
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

const mockGetUserId = jest.fn(() => 'mock_user_id_zap_list');
const mockSessionAttachToReq = (req: any) => {
  req.session = { getUserId: mockGetUserId } as any;
};

jest.mock('../../../../../project/functions/atom-agent/_libs/zapier-utils', () => ({
  listZapierWebhooks: jest.fn(),
}));
const mockedListZapierWebhooks = listZapierWebhooks as jest.Mock;

describe('/api/atom/zapier/list_webhooks API Endpoint', () => {
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

  it('should return 200 with list of webhooks on successful GET', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    const mockWebhooks: ZapierWebhook[] = [{ id: 'z1', zap_name: 'Zap One' }, { id: 'z2', zap_name: 'Zap Two' }];
    mockedListZapierWebhooks.mockResolvedValue(mockWebhooks);

    await listWebhooksHandler(mockReq, mockRes);

    expect(mockedListZapierWebhooks).toHaveBeenCalledWith('mock_user_id_zap_list');
    expect(mockRes.statusCode).toBe(200);
    expect(mockRes._getJSONData()).toEqual({ success: true, webhooks: mockWebhooks });
  });

  it('should return 200 with empty list if no webhooks found', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockedListZapierWebhooks.mockResolvedValue([]);
    await listWebhooksHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(200);
    expect(mockRes._getJSONData()).toEqual({ success: true, webhooks: [] });
  });

  it('should return 500 if listZapierWebhooks throws an error', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);
    mockedListZapierWebhooks.mockRejectedValue(new Error("DB list error"));
    await listWebhooksHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(500);
    expect(mockRes._getJSONData().error).toContain("DB list error");
  });

  it('should return 401 if unauthenticated', async () => {
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => { res.statusCode = 401; res.writableEnded = true; });
    const mockReq = httpMocks.createRequest<NextApiRequest>({ method: 'GET' });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    await listWebhooksHandler(mockReq, mockRes);
    expect(mockRes.statusCode).toBe(401);
  });
});
