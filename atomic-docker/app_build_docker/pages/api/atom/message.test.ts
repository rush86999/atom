import { NextApiRequest, NextApiResponse } from 'next';
import httpMocks from 'node-mocks-http';
import messageHandler from './atom/message'; // Assuming the handler is default export from atom/message.ts
import { handleMessage as mockAtomHandleMessage } from '../../../../project/functions/atom-agent/handler';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from 'supertokens-node/recipe/session/framework/express';
import Session from 'supertokens-node/recipe/session';

// Mock dependencies
jest.mock('supertokens-node/nextjs', () => ({
  superTokensNextWrapper: jest.fn(async (fn, req, res) => { // Ensure it handles async correctly
    const middleware = fn; // The first function passed to superTokensNextWrapper
    let nextCalled = false;
    const nextCb = async () => { nextCalled = true; };
    await middleware(nextCb); // Call the middleware (verifySession)
    if (nextCalled && !res.writableEnded) { // If next was called and response not ended by middleware
        // This means verifySession "succeeded" in our mock, so the actual handler logic in message.ts runs
        // We need to call the original handler logic which is now inside the superTokensNextWrapper in message.ts
        // This is tricky because the handler itself is wrapped.
        // For simplicity, we'll assume the handler logic is directly testable if verifySession mock calls next().
        // The structure of message.ts is: export default async function handler(req, res) { await superTokensNextWrapper(...); /* actual logic here */ }
        // So, the "actual logic" part needs to be invoked after the wrapper's middleware part.
        // This mock needs to be more sophisticated or the handler refactored for easier testing of the inner logic.
        // Let's simplify: the test will focus on what happens *after* superTokensNextWrapper.
        // The wrapper calls verifySession, then the main logic.
        // We assume superTokensNextWrapper will eventually call the main logic if verifySession calls next().
    }
    // If res.writableEnded is true, verifySession mock handled the response (e.g. 401)
  }),
}));

const mockVerifySessionMiddleware = jest.fn((req, res, next) => next());
jest.mock('supertokens-node/recipe/session/framework/express', () => ({
  verifySession: jest.fn(() => mockVerifySessionMiddleware),
}));

// Session.SessionContainer is a class, its methods might be called on an instance.
// We'll mock getUserId on the session object attached to req.
const mockGetUserId = jest.fn(() => 'mock_user_id_from_supertokens');
const mockSessionAttachToReq = (req: any) => {
  req.session = { getUserId: mockGetUserId } as any; // Mock Session.SessionContainer instance
};


jest.mock('../../../../project/functions/atom-agent/handler', () => ({
  handleMessage: jest.fn(),
}));

const mockedAtomHandleMessage = handleMessage as jest.Mock;

describe('/api/atom/message API Endpoint', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Default behavior for verifySession: success
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => {
        mockSessionAttachToReq(req); // Attach session object on successful verification
        next();
    });
    (superTokensNextWrapper as jest.Mock).mockImplementation(async (middleware, req, res) => {
        // This mock simulates that the middleware (verifySession) is called,
        // and then if not ended, the main handler logic (which we are testing) is called.
        let nextCalled = false;
        await middleware(async () => {nextCalled = true});
        if(nextCalled && !res.writableEnded) {
            // The actual handler from message.ts needs to be called here.
            // This is tricky because it's an export default.
            // For this test, we'll call a "conceptual" inner handler.
            // A better way would be to export the inner logic from message.ts for direct testing.
            // Given the current structure, we'll test the conditions *inside* the default export handler.
        }
    });
  });

  it('should return 200 and Atom response on successful POST', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'POST',
      url: '/api/atom/message',
      body: { message: 'list events' },
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();

    mockSessionAttachToReq(mockReq); // Simulate session being attached by Supertokens

    mockedAtomHandleMessage.mockResolvedValue('Mocked Atom Response');

    // Manually invoke the handler logic as superTokensNextWrapper mock is simplified
    await messageHandler(mockReq, mockRes);


    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1); // verifySession middleware itself
    expect(mockGetUserId).toHaveBeenCalledTimes(1);
    expect(mockedAtomHandleMessage).toHaveBeenCalledWith('list events', 'mock_user_id_from_supertokens');
    expect(mockRes.statusCode).toBe(200);
    expect(mockRes._getJSONData()).toEqual({ response: 'Mocked Atom Response' });
  });

  it('should return 401 if user is not authenticated', async () => {
    // Configure verifySession mock to simulate auth failure
    mockVerifySessionMiddleware.mockImplementation((req, res, next) => {
      res.statusCode = 401; // Simulate SuperTokens sending 401
      res.writableEnded = true; // Simulate SuperTokens ending the response
      // Not calling next()
    });

    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'POST',
      body: { message: 'list events' },
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();

    // The wrapper should execute verifySession, which then ends the response.
    // We need to call the actual handler to trigger the wrapper.
    await messageHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockRes.statusCode).toBe(401); // This is set by our mock verifySession
    expect(mockedAtomHandleMessage).not.toHaveBeenCalled();
  });

  it('should return 405 if method is not POST', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'GET',
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq); // Assume authenticated for this check

    await messageHandler(mockReq, mockRes);

    // verifySession is still called due to the wrapper
    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockRes.statusCode).toBe(405);
    expect(mockRes._getHeaders().allow).toBe('POST');
    expect(mockedAtomHandleMessage).not.toHaveBeenCalled();
  });

  it('should return 400 if message is missing in POST body', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'POST',
      body: {}, // Missing message
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    await messageHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockGetUserId).toHaveBeenCalledTimes(1); // User ID is fetched before body check
    expect(mockRes.statusCode).toBe(400);
    expect(mockRes._getJSONData().error).toBe('Missing message in request body');
    expect(mockedAtomHandleMessage).not.toHaveBeenCalled();
  });

  it('should return 500 if handleMessage throws an error', async () => {
    const mockReq = httpMocks.createRequest<NextApiRequest>({
      method: 'POST',
      body: { message: 'cause error' },
    });
    const mockRes = httpMocks.createResponse<NextApiResponse>();
    mockSessionAttachToReq(mockReq);

    mockedAtomHandleMessage.mockRejectedValue(new Error('Atom Internal Error'));

    await messageHandler(mockReq, mockRes);

    expect(mockVerifySessionMiddleware).toHaveBeenCalledTimes(1);
    expect(mockGetUserId).toHaveBeenCalledTimes(1);
    expect(mockedAtomHandleMessage).toHaveBeenCalledWith('cause error', 'mock_user_id_from_supertokens');
    expect(mockRes.statusCode).toBe(500);
    expect(mockRes._getJSONData().error).toBe('Atom Internal Error');
  });
});
