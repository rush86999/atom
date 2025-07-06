import handler from '../[taskId]'; // Adjust path to your API route
import { createMocks, RequestMethod } from 'node-mocks-http';
import { Pool } from 'pg';
import { getSession } from 'supertokens-node/nextjs';
import { appServiceLogger } from '../../../../lib/logger'; // Actual logger

// Mock pg Pool
const mockQuery = jest.fn();
const mockRelease = jest.fn();
const mockConnect = jest.fn().mockResolvedValue({
  query: mockQuery,
  release: mockRelease,
});
jest.mock('pg', () => {
  const actualPg = jest.requireActual('pg');
  return {
    ...actualPg,
    Pool: jest.fn(() => ({
      connect: mockConnect,
    })),
  };
});

// Mock Supertokens getSession
jest.mock('supertokens-node/nextjs');
const mockedGetSession = getSession as jest.Mock;

// Mock the logger
jest.mock('../../../../lib/logger', () => ({
    appServiceLogger: {
        info: jest.fn(),
        warn: jest.fn(),
        error: jest.fn(),
        debug: jest.fn(),
        fatal: jest.fn(),
    },
}));
const mockedLogger = appServiceLogger as jest.Mocked<typeof appServiceLogger>;

describe('/api/meeting_attendance_status/[taskId] API Endpoint', () => {
    const taskId = 'task-123';
    const userId = 'user-abc';
    const mockStatusRecord = {
        task_id: taskId,
        user_id: userId,
        platform: 'zoom',
        meeting_identifier: 'zoom-meeting-id',
        status_timestamp: new Date().toISOString(),
        current_status_message: 'In Progress',
        final_notion_page_url: null,
        error_details: null,
        created_at: new Date().toISOString(),
    };

    beforeEach(() => {
        mockQuery.mockReset();
        mockRelease.mockReset();
        mockConnect.mockClear(); // Clear connect mock calls too
        mockedGetSession.mockReset();
        Object.values(mockedLogger).forEach(mockFn => mockFn.mockReset());

        // Default successful session
        mockedGetSession.mockResolvedValue({
            getUserId: () => userId,
            // Add other session methods if your handler uses them
        });
    });

    it('should return 405 if method is not GET', async () => {
        const { req, res } = createMocks({ method: 'POST', query: { taskId } });
        await handler(req as any, res as any);
        expect(res._getStatusCode()).toBe(405);
        expect(mockedLogger.warn).toHaveBeenCalledWith(expect.stringContaining('Method not allowed'), expect.anything());
    });

    it('should return 401 if session is not found', async () => {
        mockedGetSession.mockResolvedValueOnce(null);
        const { req, res } = createMocks({ method: 'GET', query: { taskId } });
        await handler(req as any, res as any);
        expect(res._getStatusCode()).toBe(401);
        expect(JSON.parse(res._getData()).error).toBe('Unauthorized. Please log in.');
        expect(mockedLogger.warn).toHaveBeenCalledWith(expect.stringContaining('Unauthorized attempt: No active session.'), expect.anything());
    });

    it('should return 400 if taskId is missing', async () => {
        const { req, res } = createMocks({ method: 'GET', query: {} }); // No taskId
        await handler(req as any, res as any);
        expect(res._getStatusCode()).toBe(400);
        expect(JSON.parse(res._getData()).error).toBe('Task ID is required and must be a string.');
        expect(mockedLogger.warn).toHaveBeenCalledWith(expect.stringContaining('Invalid or missing taskId.'), expect.anything());
    });


    it('should fetch and return status record successfully', async () => {
        mockQuery.mockResolvedValueOnce({ rows: [mockStatusRecord] });
        const { req, res } = createMocks({ method: 'GET', query: { taskId } });

        await handler(req as any, res as any);

        expect(res._getStatusCode()).toBe(200);
        const responseData = JSON.parse(res._getData());
        // Timestamps are stringified, compare relevant parts or re-parse
        expect(responseData.task_id).toEqual(mockStatusRecord.task_id);
        expect(responseData.current_status_message).toEqual(mockStatusRecord.current_status_message);

        expect(mockConnect).toHaveBeenCalledTimes(1);
        expect(mockQuery).toHaveBeenCalledWith(expect.any(String), [taskId, userId]);
        expect(mockRelease).toHaveBeenCalledTimes(1);
        expect(mockedLogger.info).toHaveBeenCalledWith(expect.stringContaining('Status found for task.'), expect.anything());
    });

    it('should return 404 if task is not found or not authorized', async () => {
        mockQuery.mockResolvedValueOnce({ rows: [] }); // No rows found
        const { req, res } = createMocks({ method: 'GET', query: { taskId } });

        await handler(req as any, res as any);

        expect(res._getStatusCode()).toBe(404);
        expect(JSON.parse(res._getData()).error).toBe('Task not found or not authorized.');
        expect(mockedLogger.info).toHaveBeenCalledWith(expect.stringContaining('Task not found or not authorized for user.'), expect.anything());
    });

    it('should return 500 and log error if database query fails', async () => {
        const dbError = new Error('DB query failed');
        mockQuery.mockRejectedValueOnce(dbError);
        const { req, res } = createMocks({ method: 'GET', query: { taskId } });

        await handler(req as any, res as any);

        expect(res._getStatusCode()).toBe(500);
        expect(JSON.parse(res._getData()).error).toBe('Internal Server Error');
        expect(mockedLogger.error).toHaveBeenCalledWith(
            expect.stringContaining('Database query or connection failed.'),
            expect.objectContaining({ error: dbError.message })
        );
    });

    it('should return 500 if Supertokens getSession fails', async () => {
        const sessionError = new Error('Supertokens down');
        mockedGetSession.mockRejectedValueOnce(sessionError);
        const { req, res } = createMocks({ method: 'GET', query: { taskId } });

        await handler(req as any, res as any);

        expect(res._getStatusCode()).toBe(500);
        expect(JSON.parse(res._getData()).error).toBe('Authentication error');
        expect(mockedLogger.error).toHaveBeenCalledWith(
            expect.stringContaining('Supertokens getSession error.'),
            expect.objectContaining({ error: sessionError.message })
        );
    });

});
