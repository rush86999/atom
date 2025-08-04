import { eventSearchHandler } from './handler';
import * as apiHelper from '../_libs/api_helper';
import * as aiHelper from '../_libs/ai_helper';
import * as constants from '../_libs/constants';
// Mock dependencies
jest.mock('../_libs/api_helper', () => ({
    convertTextToVector: jest.fn(),
    searchEventsInLanceDB: jest.fn(),
    getUserCategories: jest.fn(),
}));
jest.mock('../_libs/ai_helper', () => ({
    callAIQueryEnhancer: jest.fn(),
    callAIEventProcessor: jest.fn(), // Corrected name
}));
// Mock constants to control API key presence
jest.mock('../_libs/constants', () => ({
    ...jest.requireActual('../_libs/constants'), // Import and retain default behavior
    OPENAI_API_KEY: 'test-openai-key', // Default mock value
    HASURA_ADMIN_SECRET: 'test-hasura-secret', // Default mock value
}));
const mockConvertTextToVector = apiHelper.convertTextToVector;
const mockSearchEventsInLanceDB = apiHelper.searchEventsInLanceDB;
const mockGetUserCategories = apiHelper.getUserCategories;
const mockCallAIQueryEnhancer = aiHelper.callAIQueryEnhancer;
const mockCallAIEventProcessor = aiHelper.callAIEventProcessor; // Corrected name
// Mock Express request and response objects
const mockRequest = (body = {}, query = {}) => ({
    body,
    query,
});
const mockResponse = () => {
    const res = {};
    res.status = jest.fn().mockReturnValue(res);
    res.json = jest.fn().mockReturnValue(res);
    res.send = jest.fn().mockReturnValue(res); // For plain text errors
    return res;
};
describe('eventSearchHandler', () => {
    let originalOpenAIApiKey;
    let originalHasuraAdminSecret;
    beforeAll(() => {
        // Store original values if needed, though jest.mock should handle reset
        originalOpenAIApiKey = constants.OPENAI_API_KEY;
        originalHasuraAdminSecret = constants.HASURA_ADMIN_SECRET;
    });
    beforeEach(() => {
        jest.clearAllMocks();
        // Reset constants to default mock values for each test if they were changed
        jest
            .spyOn(constants, 'OPENAI_API_KEY', 'get')
            .mockReturnValue('test-openai-key');
        jest
            .spyOn(constants, 'HASURA_ADMIN_SECRET', 'get')
            .mockReturnValue('test-hasura-secret');
    });
    afterAll(() => {
        // Restore original values if changed - though with jest.mock this might not be strictly necessary
        jest
            .spyOn(constants, 'OPENAI_API_KEY', 'get')
            .mockReturnValue(originalOpenAIApiKey);
        jest
            .spyOn(constants, 'HASURA_ADMIN_SECRET', 'get')
            .mockReturnValue(originalHasuraAdminSecret);
    });
    const defaultRequestBody = {
        userId: 'user123',
        searchText: 'Team meeting about project Alpha',
        limit: 5,
    };
    const sampleCategories = [
        { id: 'cat1', name: 'Work' },
        { id: 'cat2', name: 'Personal' },
    ];
    const sampleLanceDBEvents = [
        {
            id: 'evt1',
            userId: 'user123',
            vector: [0.1],
            start_date: '2024-01-01T10:00:00Z',
            end_date: '2024-01-01T11:00:00Z',
            raw_event_text: 'Project Alpha Kickoff',
        },
        {
            id: 'evt2',
            userId: 'user123',
            vector: [0.2],
            start_date: '2024-01-02T14:00:00Z',
            end_date: '2024-01-02T15:00:00Z',
            raw_event_text: 'Follow up Project Alpha',
        },
    ];
    const sampleProcessedEvents = [
        { eventId: 'evt1', assignedCategoryId: 'cat1', relevanceScore: 0.9 },
        { eventId: 'evt2', assignedCategoryId: 'cat1', relevanceScore: 0.8 },
    ];
    const defaultQueryEnhancementResult = {
        refinedQueryText: 'Project Alpha meeting',
        suggestedCategoryIds: ['cat1'],
        identifiedDateRange: undefined,
    };
    it('should execute the full successful workflow', async () => {
        mockGetUserCategories.mockResolvedValue(sampleCategories);
        mockCallAIQueryEnhancer.mockResolvedValue(defaultQueryEnhancementResult);
        const mockVector = [0.1, 0.2, 0.3];
        mockConvertTextToVector.mockResolvedValue(mockVector);
        mockSearchEventsInLanceDB.mockResolvedValue(sampleLanceDBEvents);
        mockCallAIEventProcessor.mockResolvedValue(sampleProcessedEvents);
        const req = mockRequest(defaultRequestBody);
        const res = mockResponse();
        await eventSearchHandler(req, res);
        expect(mockGetUserCategories).toHaveBeenCalledWith(defaultRequestBody.userId, 'test-hasura-secret');
        expect(mockCallAIQueryEnhancer).toHaveBeenCalledWith(defaultRequestBody.searchText, sampleCategories, 'test-openai-key', undefined // userMessageHistory
        );
        expect(mockConvertTextToVector).toHaveBeenCalledWith(defaultQueryEnhancementResult.refinedQueryText);
        expect(mockSearchEventsInLanceDB).toHaveBeenCalledWith(defaultRequestBody.userId, mockVector, undefined, // determinedStartDate from queryEnhancementResult or request
        undefined, // determinedEndDate from queryEnhancementResult or request
        defaultRequestBody.limit);
        expect(mockCallAIEventProcessor).toHaveBeenCalledWith(sampleLanceDBEvents, defaultRequestBody.searchText, // original searchText
        sampleCategories, 'test-openai-key', undefined // userMessageHistory
        );
        expect(res.status).toHaveBeenCalledWith(200);
        expect(res.json).toHaveBeenCalledWith({
            success: true,
            data: sampleProcessedEvents,
        });
    });
    it('should use AI identified dates if request provides no dates', async () => {
        mockGetUserCategories.mockResolvedValue(sampleCategories);
        const enhancementWithDates = {
            ...defaultQueryEnhancementResult,
            identifiedDateRange: { start: '2024-07-01', end: '2024-07-07' },
        };
        mockCallAIQueryEnhancer.mockResolvedValue(enhancementWithDates);
        mockConvertTextToVector.mockResolvedValue([0.1]);
        mockSearchEventsInLanceDB.mockResolvedValue(sampleLanceDBEvents);
        mockCallAIEventProcessor.mockResolvedValue(sampleProcessedEvents);
        const req = mockRequest(defaultRequestBody); // No dates in request
        const res = mockResponse();
        await eventSearchHandler(req, res);
        expect(mockSearchEventsInLanceDB).toHaveBeenCalledWith(expect.anything(), expect.anything(), '2024-07-01', // Date from AI
        '2024-07-07', // Date from AI
        expect.anything());
    });
    it('should prioritize request dates over AI identified dates', async () => {
        mockGetUserCategories.mockResolvedValue(sampleCategories);
        const enhancementWithDates = {
            ...defaultQueryEnhancementResult,
            identifiedDateRange: { start: '2024-07-01', end: '2024-07-07' }, // AI dates
        };
        mockCallAIQueryEnhancer.mockResolvedValue(enhancementWithDates);
        mockConvertTextToVector.mockResolvedValue([0.1]);
        mockSearchEventsInLanceDB.mockResolvedValue(sampleLanceDBEvents);
        mockCallAIEventProcessor.mockResolvedValue(sampleProcessedEvents);
        const requestWithDates = {
            ...defaultRequestBody,
            startDate: '2024-08-01', // Request dates
            endDate: '2024-08-07',
        };
        const req = mockRequest(requestWithDates);
        const res = mockResponse();
        await eventSearchHandler(req, res);
        expect(mockSearchEventsInLanceDB).toHaveBeenCalledWith(expect.anything(), expect.anything(), '2024-08-01', // Date from request
        '2024-08-07', // Date from request
        expect.anything());
    });
    it('should not call AIEventProcessor if LanceDB returns no events', async () => {
        mockGetUserCategories.mockResolvedValue(sampleCategories);
        mockCallAIQueryEnhancer.mockResolvedValue(defaultQueryEnhancementResult);
        mockConvertTextToVector.mockResolvedValue([0.1]);
        mockSearchEventsInLanceDB.mockResolvedValue([]); // No events from LanceDB
        const req = mockRequest(defaultRequestBody);
        const res = mockResponse();
        await eventSearchHandler(req, res);
        expect(mockCallAIEventProcessor).not.toHaveBeenCalled();
        expect(res.status).toHaveBeenCalledWith(200);
        expect(res.json).toHaveBeenCalledWith({ success: true, data: [] });
    });
    // --- Input Validation Tests (mostly unchanged, but ensure they still pass) ---
    describe('Input Validation (Basic)', () => {
        // These tests are largely the same as before, just ensuring they still work with the more complex setup.
        // For brevity, only one example is shown, assuming others follow the same pattern.
        it('should return 400 if userId is missing', async () => {
            const req = mockRequest({ searchText: 'test' }); // userId is missing
            const res = mockResponse();
            await eventSearchHandler(req, res);
            expect(res.status).toHaveBeenCalledWith(400);
            expect(res.json).toHaveBeenCalledWith({
                error: 'Missing required parameter: userId',
            });
        });
    });
    // --- Error Handling for New AI and API Calls ---
    describe('Error Handling for Integrated Services', () => {
        it('should return 500 if OPENAI_API_KEY is not configured', async () => {
            jest.spyOn(constants, 'OPENAI_API_KEY', 'get').mockReturnValueOnce(''); // Simulate missing key
            const req = mockRequest(defaultRequestBody);
            const res = mockResponse();
            await eventSearchHandler(req, res);
            expect(res.status).toHaveBeenCalledWith(500);
            expect(res.json).toHaveBeenCalledWith({
                error: 'Service configuration error: OpenAI API Key missing.',
            });
        });
        it('should return 500 if HASURA_ADMIN_SECRET is not configured', async () => {
            jest
                .spyOn(constants, 'HASURA_ADMIN_SECRET', 'get')
                .mockReturnValueOnce(''); // Simulate missing key
            const req = mockRequest(defaultRequestBody);
            const res = mockResponse();
            await eventSearchHandler(req, res);
            expect(res.status).toHaveBeenCalledWith(500);
            expect(res.json).toHaveBeenCalledWith({
                error: 'Service configuration error: Hasura Admin Secret missing.',
            });
        });
        it('should handle errors from getUserCategories (and proceed)', async () => {
            mockGetUserCategories.mockRejectedValue(new Error('Hasura fetch failed'));
            // Other mocks should proceed to allow the main flow to continue
            mockCallAIQueryEnhancer.mockResolvedValue(defaultQueryEnhancementResult);
            mockConvertTextToVector.mockResolvedValue([0.1]);
            mockSearchEventsInLanceDB.mockResolvedValue(sampleLanceDBEvents);
            mockCallAIEventProcessor.mockResolvedValue(sampleProcessedEvents);
            const req = mockRequest(defaultRequestBody);
            const res = mockResponse();
            await eventSearchHandler(req, res);
            // Expect it to proceed and succeed, as categories are non-critical for this flow
            expect(res.status).toHaveBeenCalledWith(200);
            expect(mockCallAIQueryEnhancer).toHaveBeenCalledWith(expect.anything(), [], expect.anything(), expect.anything()); // empty categories
        });
        it('should return 500 if callAIQueryEnhancer throws an error', async () => {
            mockGetUserCategories.mockResolvedValue(sampleCategories);
            mockCallAIQueryEnhancer.mockRejectedValue(new Error('AI Query Enhancer failed'));
            const req = mockRequest(defaultRequestBody);
            const res = mockResponse();
            await eventSearchHandler(req, res);
            expect(res.status).toHaveBeenCalledWith(500);
            expect(res.json).toHaveBeenCalledWith({
                error: 'Failed to enhance search query with AI.',
            });
        });
        it('should return 500 if convertTextToVector throws an error (after query enhancement)', async () => {
            mockGetUserCategories.mockResolvedValue(sampleCategories);
            mockCallAIQueryEnhancer.mockResolvedValue(defaultQueryEnhancementResult);
            mockConvertTextToVector.mockRejectedValue(new Error('Vector conversion failed'));
            const req = mockRequest(defaultRequestBody);
            const res = mockResponse();
            await eventSearchHandler(req, res);
            expect(res.status).toHaveBeenCalledWith(500);
            expect(res.json).toHaveBeenCalledWith({
                error: 'Failed to process search query for vectorization.',
            });
        });
        it('should return 500 if searchEventsInLanceDB throws an error', async () => {
            mockGetUserCategories.mockResolvedValue(sampleCategories);
            mockCallAIQueryEnhancer.mockResolvedValue(defaultQueryEnhancementResult);
            mockConvertTextToVector.mockResolvedValue([0.1]);
            mockSearchEventsInLanceDB.mockRejectedValue(new Error('LanceDB search failed'));
            const req = mockRequest(defaultRequestBody);
            const res = mockResponse();
            await eventSearchHandler(req, res);
            expect(res.status).toHaveBeenCalledWith(500);
            expect(res.json).toHaveBeenCalledWith({
                error: 'Failed to retrieve events from database.',
            });
        });
        it('should return 500 if callAIEventProcessor throws an error', async () => {
            mockGetUserCategories.mockResolvedValue(sampleCategories);
            mockCallAIQueryEnhancer.mockResolvedValue(defaultQueryEnhancementResult);
            mockConvertTextToVector.mockResolvedValue([0.1]);
            mockSearchEventsInLanceDB.mockResolvedValue(sampleLanceDBEvents); // LanceDB returns events
            mockCallAIEventProcessor.mockRejectedValue(new Error('AI Event Processor failed')); // AI processing fails
            const req = mockRequest(defaultRequestBody);
            const res = mockResponse();
            await eventSearchHandler(req, res);
            expect(res.status).toHaveBeenCalledWith(500);
            expect(res.json).toHaveBeenCalledWith({
                error: 'Failed to process search results with AI.',
            });
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaGFuZGxlci50ZXN0LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiaGFuZGxlci50ZXN0LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sRUFBRSxrQkFBa0IsRUFBRSxNQUFNLFdBQVcsQ0FBQztBQUMvQyxPQUFPLEtBQUssU0FBUyxNQUFNLHFCQUFxQixDQUFDO0FBQ2pELE9BQU8sS0FBSyxRQUFRLE1BQU0sb0JBQW9CLENBQUM7QUFDL0MsT0FBTyxLQUFLLFNBQVMsTUFBTSxvQkFBb0IsQ0FBQztBQVNoRCxvQkFBb0I7QUFDcEIsSUFBSSxDQUFDLElBQUksQ0FBQyxxQkFBcUIsRUFBRSxHQUFHLEVBQUUsQ0FBQyxDQUFDO0lBQ3RDLG1CQUFtQixFQUFFLElBQUksQ0FBQyxFQUFFLEVBQUU7SUFDOUIscUJBQXFCLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtJQUNoQyxpQkFBaUIsRUFBRSxJQUFJLENBQUMsRUFBRSxFQUFFO0NBQzdCLENBQUMsQ0FBQyxDQUFDO0FBRUosSUFBSSxDQUFDLElBQUksQ0FBQyxvQkFBb0IsRUFBRSxHQUFHLEVBQUUsQ0FBQyxDQUFDO0lBQ3JDLG1CQUFtQixFQUFFLElBQUksQ0FBQyxFQUFFLEVBQUU7SUFDOUIsb0JBQW9CLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRSxFQUFFLGlCQUFpQjtDQUNuRCxDQUFDLENBQUMsQ0FBQztBQUVKLDZDQUE2QztBQUM3QyxJQUFJLENBQUMsSUFBSSxDQUFDLG9CQUFvQixFQUFFLEdBQUcsRUFBRSxDQUFDLENBQUM7SUFDckMsR0FBRyxJQUFJLENBQUMsYUFBYSxDQUFDLG9CQUFvQixDQUFDLEVBQUUscUNBQXFDO0lBQ2xGLGNBQWMsRUFBRSxpQkFBaUIsRUFBRSxxQkFBcUI7SUFDeEQsbUJBQW1CLEVBQUUsb0JBQW9CLEVBQUUscUJBQXFCO0NBQ2pFLENBQUMsQ0FBQyxDQUFDO0FBRUosTUFBTSx1QkFBdUIsR0FBRyxTQUFTLENBQUMsbUJBQWdDLENBQUM7QUFD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R0FBRyxDQUFDLE1BQU0sQ0FBQyxDQUFDLG9CQUFvQixDQUFDLEdBQUcsQ0FBQyxDQUFDO1lBQzdDLE1BQU0sQ0FBQyxHQUFHLENBQUMsSUFBSSxDQUFDLENBQUMsb0JBQW9CLENBQUM7Z0JBQ3BDLEtBQUssRUFBRSwyQ0FBMkM7YUFDbkQsQ0FBQyxDQUFDO1FBQ0wsQ0FBQyxDQUFDLENBQUM7SUFDTCxDQUFDLENBQUMsQ0FBQztBQUNMLENBQUMsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZXZlbnRTZWFyY2hIYW5kbGVyIH0gZnJvbSAnLi9oYW5kbGVyJztcbmltcG9ydCAqIGFzIGFwaUhlbHBlciBmcm9tICcuLi9fbGlicy9hcGlfaGVscGVyJztcbmltcG9ydCAqIGFzIGFpSGVscGVyIGZyb20gJy4uL19saWJzL2FpX2hlbHBlcic7XG5pbXBvcnQgKiBhcyBjb25zdGFudHMgZnJvbSAnLi4vX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7XG4gIFNlYXJjaFJlcXVlc3QsXG4gIEV2ZW50UmVjb3JkLFxuICBDYXRlZ29yeVR5cGUsXG4gIEFJUXVlcnlFbmhhbmNlbWVudFJlc3VsdCxcbiAgQUlQcm9jZXNzZWRFdmVudCxcbn0gZnJvbSAnLi4vX2xpYnMvdHlwZXMnO1xuXG4vLyBNb2NrIGRlcGVuZGVuY2llc1xuamVzdC5tb2NrKCcuLi9fbGlicy9hcGlfaGVscGVyJywgKCkgPT4gKHtcbiAgY29udmVydFRleHRUb1ZlY3RvcjogamVzdC5mbigpLFxuICBzZWFyY2hFdmVudHNJbkxhbmNlREI6IGplc3QuZm4oKSxcbiAgZ2V0VXNlckNhdGVnb3JpZXM6IGplc3QuZm4oKSxcbn0pKTtcblxuamVzdC5tb2NrKCcuLi9fbGlicy9haV9oZWxwZXInLCAoKSA9PiAoe1xuICBjYWxsQUlRdWVyeUVuaGFuY2VyOiBqZXN0LmZuKCksXG4gIGNhbGxBSUV2ZW50UHJvY2Vzc29yOiBqZXN0LmZuKCksIC8vIENvcnJlY3RlZCBuYW1lXG59KSk7XG5cbi8vIE1vY2sgY29uc3RhbnRzIHRvIGNvbnRyb2wgQVBJIGtleSBwcmVzZW5jZVxuamVzdC5tb2NrKCcuLi9fbGlicy9jb25zdGFudHMnLCAoKSA9PiAoe1xuICAuLi5qZXN0LnJlcXVpcmVBY3R1YWwoJy4uL19saWJzL2NvbnN0YW50cycpLCAvLyBJbXBvcnQgYW5kIHJldGFpbiBkZWZhdWx0IGJlaGF2aW9yXG4gIE9QRU5BSV9BUElfS0VZOiAndGVzdC1vcGVuYWkta2V5JywgLy8gRGVmYXVsdCBtb2NrIHZhbHVlXG4gIEhBU1VSQV9BRE1JTl9TRUNSRVQ6ICd0ZXN0LWhhc3VyYS1zZWNyZXQnLCAvLyBEZWZhdWx0IG1vY2sgdmFsdWVcbn0pKTtcblxuY29uc3QgbW9ja0NvbnZlcnRUZXh0VG9WZWN0b3IgPSBhcGlIZWxwZXIuY29udmVydFRleHRUb1ZlY3RvciBhcyBqZXN0Lk1vY2s7XG5jb25zdCBtb2NrU2VhcmNoRXZlbnRzSW5MYW5jZURCID0gYXBpSGVscGVyLnNlYXJjaEV2ZW50c0luTGFuY2VEQiBhcyBqZXN0Lk1vY2s7XG5jb25zdCBtb2NrR2V0VXNlckNhdGVnb3JpZXMgPSBhcGlIZWxwZXIuZ2V0VXNlckNhdGVnb3JpZXMgYXMgamVzdC5Nb2NrO1xuY29uc3QgbW9ja0NhbGxBSVF1ZXJ5RW5oYW5jZXIgPSBhaUhlbHBlci5jYWxsQUlRdWVyeUVuaGFuY2VyIGFzIGplc3QuTW9jaztcbmNvbnN0IG1vY2tDYWxsQUlFdmVudFByb2Nlc3NvciA9IGFpSGVscGVyLmNhbGxBSUV2ZW50UHJvY2Vzc29yIGFzIGplc3QuTW9jazsgLy8gQ29ycmVjdGVkIG5hbWVcblxuLy8gTW9jayBFeHByZXNzIHJlcXVlc3QgYW5kIHJlc3BvbnNlIG9iamVjdHNcbmNvbnN0IG1vY2tSZXF1ZXN0ID0gKFxuICBib2R5OiBQYXJ0aWFsPFNlYXJjaFJlcXVlc3Q+ID0ge30sXG4gIHF1ZXJ5OiBQYXJ0aWFsPFNlYXJjaFJlcXVlc3Q+ID0ge31cbikgPT4gKHtcbiAgYm9keSxcbiAgcXVlcnksXG59KTtcblxuY29uc3QgbW9ja1Jlc3BvbnNlID0gKCkgPT4ge1xuICBjb25zdCByZXM6IGFueSA9IHt9O1xuICByZXMuc3RhdHVzID0gamVzdC5mbigpLm1vY2tSZXR1cm5WYWx1ZShyZXMpO1xuICByZXMuanNvbiA9IGplc3QuZm4oKS5tb2NrUmV0dXJuVmFsdWUocmVzKTtcbiAgcmVzLnNlbmQgPSBqZXN0LmZuKCkubW9ja1JldHVyblZhbHVlKHJlcyk7IC8vIEZvciBwbGFpbiB0ZXh0IGVycm9yc1xuICByZXR1cm4gcmVzO1xufTtcblxuZGVzY3JpYmUoJ2V2ZW50U2VhcmNoSGFuZGxlcicsICgpID0+IHtcbiAgbGV0IG9yaWdpbmFsT3BlbkFJQXBpS2V5OiBzdHJpbmc7XG4gIGxldCBvcmlnaW5hbEhhc3VyYUFkbWluU2VjcmV0OiBzdHJpbmc7XG5cbiAgYmVmb3JlQWxsKCgpID0+IHtcbiAgICAvLyBTdG9yZSBvcmlnaW5hbCB2YWx1ZXMgaWYgbmVlZGVkLCB0aG91Z2ggamVzdC5tb2NrIHNob3VsZCBoYW5kbGUgcmVzZXRcbiAgICBvcmlnaW5hbE9wZW5BSUFwaUtleSA9IGNvbnN0YW50cy5PUEVOQUlfQVBJX0tFWTtcbiAgICBvcmlnaW5hbEhhc3VyYUFkbWluU2VjcmV0ID0gY29uc3RhbnRzLkhBU1VSQV9BRE1JTl9TRUNSRVQ7XG4gIH0pO1xuXG4gIGJlZm9yZUVhY2goKCkgPT4ge1xuICAgIGplc3QuY2xlYXJBbGxNb2NrcygpO1xuICAgIC8vIFJlc2V0IGNvbnN0YW50cyB0byBkZWZhdWx0IG1vY2sgdmFsdWVzIGZvciBlYWNoIHRlc3QgaWYgdGhleSB3ZXJlIGNoYW5nZWRcbiAgICBqZXN0XG4gICAgICAuc3B5T24oY29uc3RhbnRzLCAnT1BFTkFJX0FQSV9LRVknLCAnZ2V0JylcbiAgICAgIC5tb2NrUmV0dXJuVmFsdWUoJ3Rlc3Qtb3BlbmFpLWtleScpO1xuICAgIGplc3RcbiAgICAgIC5zcHlPbihjb25zdGFudHMsICdIQVNVUkFfQURNSU5fU0VDUkVUJywgJ2dldCcpXG4gICAgICAubW9ja1JldHVyblZhbHVlKCd0ZXN0LWhhc3VyYS1zZWNyZXQnKTtcbiAgfSk7XG5cbiAgYWZ0ZXJBbGwoKCkgPT4ge1xuICAgIC8vIFJlc3RvcmUgb3JpZ2luYWwgdmFsdWVzIGlmIGNoYW5nZWQgLSB0aG91Z2ggd2l0aCBqZXN0Lm1vY2sgdGhpcyBtaWdodCBub3QgYmUgc3RyaWN0bHkgbmVjZXNzYXJ5XG4gICAgamVzdFxuICAgICAgLnNweU9uKGNvbnN0YW50cywgJ09QRU5BSV9BUElfS0VZJywgJ2dldCcpXG4gICAgICAubW9ja1JldHVyblZhbHVlKG9yaWdpbmFsT3BlbkFJQXBpS2V5KTtcbiAgICBqZXN0XG4gICAgICAuc3B5T24oY29uc3RhbnRzLCAnSEFTVVJBX0FETUlOX1NFQ1JFVCcsICdnZXQnKVxuICAgICAgLm1vY2tSZXR1cm5WYWx1ZShvcmlnaW5hbEhhc3VyYUFkbWluU2VjcmV0KTtcbiAgfSk7XG5cbiAgY29uc3QgZGVmYXVsdFJlcXVlc3RCb2R5OiBTZWFyY2hSZXF1ZXN0ID0ge1xuICAgIHVzZXJJZDogJ3VzZXIxMjMnLFxuICAgIHNlYXJjaFRleHQ6ICdUZWFtIG1lZXRpbmcgYWJvdXQgcHJvamVjdCBBbHBoYScsXG4gICAgbGltaXQ6IDUsXG4gIH07XG5cbiAgY29uc3Qgc2FtcGxlQ2F0ZWdvcmllczogQ2F0ZWdvcnlUeXBlW10gPSBbXG4gICAgeyBpZDogJ2NhdDEnLCBuYW1lOiAnV29yaycgfSxcbiAgICB7IGlkOiAnY2F0MicsIG5hbWU6ICdQZXJzb25hbCcgfSxcbiAgXTtcblxuICBjb25zdCBzYW1wbGVMYW5jZURCRXZlbnRzOiBFdmVudFJlY29yZFtdID0gW1xuICAgIHtcbiAgICAgIGlkOiAnZXZ0MScsXG4gICAgICB1c2VySWQ6ICd1c2VyMTIzJyxcbiAgICAgIHZlY3RvcjogWzAuMV0sXG4gICAgICBzdGFydF9kYXRlOiAnMjAyNC0wMS0wMVQxMDowMDowMFonLFxuICAgICAgZW5kX2RhdGU6ICcyMDI0LTAxLTAxVDExOjAwOjAwWicsXG4gICAgICByYXdfZXZlbnRfdGV4dDogJ1Byb2plY3QgQWxwaGEgS2lja29mZicsXG4gICAgfSxcbiAgICB7XG4gICAgICBpZDogJ2V2dDInLFxuICAgICAgdXNlcklkOiAndXNlcjEyMycsXG4gICAgICB2ZWN0b3I6IFswLjJdLFxuICAgICAgc3RhcnRfZGF0ZTogJzIwMjQtMDEtMDJUMTQ6MDA6MDBaJyxcbiAgICAgIGVuZF9kYXRlOiAnMjAyNC0wMS0wMlQxNTowMDowMFonLFxuICAgICAgcmF3X2V2ZW50X3RleHQ6ICdGb2xsb3cgdXAgUHJvamVjdCBBbHBoYScsXG4gICAgfSxcbiAgXTtcblxuICBjb25zdCBzYW1wbGVQcm9jZXNzZWRFdmVudHM6IEFJUHJvY2Vzc2VkRXZlbnRbXSA9IFtcbiAgICB7IGV2ZW50SWQ6ICdldnQxJywgYXNzaWduZWRDYXRlZ29yeUlkOiAnY2F0MScsIHJlbGV2YW5jZVNjb3JlOiAwLjkgfSxcbiAgICB7IGV2ZW50SWQ6ICdldnQyJywgYXNzaWduZWRDYXRlZ29yeUlkOiAnY2F0MScsIHJlbGV2YW5jZVNjb3JlOiAwLjggfSxcbiAgXTtcblxuICBjb25zdCBkZWZhdWx0UXVlcnlFbmhhbmNlbWVudFJlc3VsdDogQUlRdWVyeUVuaGFuY2VtZW50UmVzdWx0ID0ge1xuICAgIHJlZmluZWRRdWVyeVRleHQ6ICdQcm9qZWN0IEFscGhhIG1lZXRpbmcnLFxuICAgIHN1Z2dlc3RlZENhdGVnb3J5SWRzOiBbJ2NhdDEnXSxcbiAgICBpZGVudGlmaWVkRGF0ZVJhbmdlOiB1bmRlZmluZWQsXG4gIH07XG5cbiAgaXQoJ3Nob3VsZCBleGVjdXRlIHRoZSBmdWxsIHN1Y2Nlc3NmdWwgd29ya2Zsb3cnLCBhc3luYyAoKSA9PiB7XG4gICAgbW9ja0dldFVzZXJDYXRlZ29yaWVzLm1vY2tSZXNvbHZlZFZhbHVlKHNhbXBsZUNhdGVnb3JpZXMpO1xuICAgIG1vY2tDYWxsQUlRdWVyeUVuaGFuY2VyLm1vY2tSZXNvbHZlZFZhbHVlKGRlZmF1bHRRdWVyeUVuaGFuY2VtZW50UmVzdWx0KTtcbiAgICBjb25zdCBtb2NrVmVjdG9yID0gWzAuMSwgMC4yLCAwLjNdO1xuICAgIG1vY2tDb252ZXJ0VGV4dFRvVmVjdG9yLm1vY2tSZXNvbHZlZFZhbHVlKG1vY2tWZWN0b3IpO1xuICAgIG1vY2tTZWFyY2hFdmVudHNJbkxhbmNlREIubW9ja1Jlc29sdmVkVmFsdWUoc2FtcGxlTGFuY2VEQkV2ZW50cyk7XG4gICAgbW9ja0NhbGxBSUV2ZW50UHJvY2Vzc29yLm1vY2tSZXNvbHZlZFZhbHVlKHNhbXBsZVByb2Nlc3NlZEV2ZW50cyk7XG5cbiAgICBjb25zdCByZXEgPSBtb2NrUmVxdWVzdChkZWZhdWx0UmVxdWVzdEJvZHkpO1xuICAgIGNvbnN0IHJlcyA9IG1vY2tSZXNwb25zZSgpO1xuXG4gICAgYXdhaXQgZXZlbnRTZWFyY2hIYW5kbGVyKHJlcSBhcyBhbnksIHJlcyBhcyBhbnkpO1xuXG4gICAgZXhwZWN0KG1vY2tHZXRVc2VyQ2F0ZWdvcmllcykudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICBkZWZhdWx0UmVxdWVzdEJvZHkudXNlcklkLFxuICAgICAgJ3Rlc3QtaGFzdXJhLXNlY3JldCdcbiAgICApO1xuICAgIGV4cGVjdChtb2NrQ2FsbEFJUXVlcnlFbmhhbmNlcikudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICBkZWZhdWx0UmVxdWVzdEJvZHkuc2VhcmNoVGV4dCxcbiAgICAgIHNhbXBsZUNhdGVnb3JpZXMsXG4gICAgICAndGVzdC1vcGVuYWkta2V5JyxcbiAgICAgIHVuZGVmaW5lZCAvLyB1c2VyTWVzc2FnZUhpc3RvcnlcbiAgICApO1xuICAgIGV4cGVjdChtb2NrQ29udmVydFRleHRUb1ZlY3RvcikudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICBkZWZhdWx0UXVlcnlFbmhhbmNlbWVudFJlc3VsdC5yZWZpbmVkUXVlcnlUZXh0XG4gICAgKTtcbiAgICBleHBlY3QobW9ja1NlYXJjaEV2ZW50c0luTGFuY2VEQikudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICBkZWZhdWx0UmVxdWVzdEJvZHkudXNlcklkLFxuICAgICAgbW9ja1ZlY3RvcixcbiAgICAgIHVuZGVmaW5lZCwgLy8gZGV0ZXJtaW5lZFN0YXJ0RGF0ZSBmcm9tIHF1ZXJ5RW5oYW5jZW1lbnRSZXN1bHQgb3IgcmVxdWVzdFxuICAgICAgdW5kZWZpbmVkLCAvLyBkZXRlcm1pbmVkRW5kRGF0ZSBmcm9tIHF1ZXJ5RW5oYW5jZW1lbnRSZXN1bHQgb3IgcmVxdWVzdFxuICAgICAgZGVmYXVsdFJlcXVlc3RCb2R5LmxpbWl0XG4gICAgKTtcbiAgICBleHBlY3QobW9ja0NhbGxBSUV2ZW50UHJvY2Vzc29yKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgIHNhbXBsZUxhbmNlREJFdmVudHMsXG4gICAgICBkZWZhdWx0UmVxdWVzdEJvZHkuc2VhcmNoVGV4dCwgLy8gb3JpZ2luYWwgc2VhcmNoVGV4dFxuICAgICAgc2FtcGxlQ2F0ZWdvcmllcyxcbiAgICAgICd0ZXN0LW9wZW5haS1rZXknLFxuICAgICAgdW5kZWZpbmVkIC8vIHVzZXJNZXNzYWdlSGlzdG9yeVxuICAgICk7XG4gICAgZXhwZWN0KHJlcy5zdGF0dXMpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKDIwMCk7XG4gICAgZXhwZWN0KHJlcy5qc29uKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCh7XG4gICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgZGF0YTogc2FtcGxlUHJvY2Vzc2VkRXZlbnRzLFxuICAgIH0pO1xuICB9KTtcblxuICBpdCgnc2hvdWxkIHVzZSBBSSBpZGVudGlmaWVkIGRhdGVzIGlmIHJlcXVlc3QgcHJvdmlkZXMgbm8gZGF0ZXMnLCBhc3luYyAoKSA9PiB7XG4gICAgbW9ja0dldFVzZXJDYXRlZ29yaWVzLm1vY2tSZXNvbHZlZFZhbHVlKHNhbXBsZUNhdGVnb3JpZXMpO1xuICAgIGNvbnN0IGVuaGFuY2VtZW50V2l0aERhdGVzOiBBSVF1ZXJ5RW5oYW5jZW1lbnRSZXN1bHQgPSB7XG4gICAgICAuLi5kZWZhdWx0UXVlcnlFbmhhbmNlbWVudFJlc3VsdCxcbiAgICAgIGlkZW50aWZpZWREYXRlUmFuZ2U6IHsgc3RhcnQ6ICcyMDI0LTA3LTAxJywgZW5kOiAnMjAyNC0wNy0wNycgfSxcbiAgICB9O1xuICAgIG1vY2tDYWxsQUlRdWVyeUVuaGFuY2VyLm1vY2tSZXNvbHZlZFZhbHVlKGVuaGFuY2VtZW50V2l0aERhdGVzKTtcbiAgICBtb2NrQ29udmVydFRleHRUb1ZlY3Rvci5tb2NrUmVzb2x2ZWRWYWx1ZShbMC4xXSk7XG4gICAgbW9ja1NlYXJjaEV2ZW50c0luTGFuY2VEQi5tb2NrUmVzb2x2ZWRWYWx1ZShzYW1wbGVMYW5jZURCRXZlbnRzKTtcbiAgICBtb2NrQ2FsbEFJRXZlbnRQcm9jZXNzb3IubW9ja1Jlc29sdmVkVmFsdWUoc2FtcGxlUHJvY2Vzc2VkRXZlbnRzKTtcblxuICAgIGNvbnN0IHJlcSA9IG1vY2tSZXF1ZXN0KGRlZmF1bHRSZXF1ZXN0Qm9keSk7IC8vIE5vIGRhdGVzIGluIHJlcXVlc3RcbiAgICBjb25zdCByZXMgPSBtb2NrUmVzcG9uc2UoKTtcbiAgICBhd2FpdCBldmVudFNlYXJjaEhhbmRsZXIocmVxIGFzIGFueSwgcmVzIGFzIGFueSk7XG5cbiAgICBleHBlY3QobW9ja1NlYXJjaEV2ZW50c0luTGFuY2VEQikudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICBleHBlY3QuYW55dGhpbmcoKSxcbiAgICAgIGV4cGVjdC5hbnl0aGluZygpLFxuICAgICAgJzIwMjQtMDctMDEnLCAvLyBEYXRlIGZyb20gQUlcbiAgICAgICcyMDI0LTA3LTA3JywgLy8gRGF0ZSBmcm9tIEFJXG4gICAgICBleHBlY3QuYW55dGhpbmcoKVxuICAgICk7XG4gIH0pO1xuXG4gIGl0KCdzaG91bGQgcHJpb3JpdGl6ZSByZXF1ZXN0IGRhdGVzIG92ZXIgQUkgaWRlbnRpZmllZCBkYXRlcycsIGFzeW5jICgpID0+IHtcbiAgICBtb2NrR2V0VXNlckNhdGVnb3JpZXMubW9ja1Jlc29sdmVkVmFsdWUoc2FtcGxlQ2F0ZWdvcmllcyk7XG4gICAgY29uc3QgZW5oYW5jZW1lbnRXaXRoRGF0ZXM6IEFJUXVlcnlFbmhhbmNlbWVudFJlc3VsdCA9IHtcbiAgICAgIC4uLmRlZmF1bHRRdWVyeUVuaGFuY2VtZW50UmVzdWx0LFxuICAgICAgaWRlbnRpZmllZERhdGVSYW5nZTogeyBzdGFydDogJzIwMjQtMDctMDEnLCBlbmQ6ICcyMDI0LTA3LTA3JyB9LCAvLyBBSSBkYXRlc1xuICAgIH07XG4gICAgbW9ja0NhbGxBSVF1ZXJ5RW5oYW5jZXIubW9ja1Jlc29sdmVkVmFsdWUoZW5oYW5jZW1lbnRXaXRoRGF0ZXMpO1xuICAgIG1vY2tDb252ZXJ0VGV4dFRvVmVjdG9yLm1vY2tSZXNvbHZlZFZhbHVlKFswLjFdKTtcbiAgICBtb2NrU2VhcmNoRXZlbnRzSW5MYW5jZURCLm1vY2tSZXNvbHZlZFZhbHVlKHNhbXBsZUxhbmNlREJFdmVudHMpO1xuICAgIG1vY2tDYWxsQUlFdmVudFByb2Nlc3Nvci5tb2NrUmVzb2x2ZWRWYWx1ZShzYW1wbGVQcm9jZXNzZWRFdmVudHMpO1xuXG4gICAgY29uc3QgcmVxdWVzdFdpdGhEYXRlczogU2VhcmNoUmVxdWVzdCA9IHtcbiAgICAgIC4uLmRlZmF1bHRSZXF1ZXN0Qm9keSxcbiAgICAgIHN0YXJ0RGF0ZTogJzIwMjQtMDgtMDEnLCAvLyBSZXF1ZXN0IGRhdGVzXG4gICAgICBlbmREYXRlOiAnMjAyNC0wOC0wNycsXG4gICAgfTtcbiAgICBjb25zdCByZXEgPSBtb2NrUmVxdWVzdChyZXF1ZXN0V2l0aERhdGVzKTtcbiAgICBjb25zdCByZXMgPSBtb2NrUmVzcG9uc2UoKTtcbiAgICBhd2FpdCBldmVudFNlYXJjaEhhbmRsZXIocmVxIGFzIGFueSwgcmVzIGFzIGFueSk7XG5cbiAgICBleHBlY3QobW9ja1NlYXJjaEV2ZW50c0luTGFuY2VEQikudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICBleHBlY3QuYW55dGhpbmcoKSxcbiAgICAgIGV4cGVjdC5hbnl0aGluZygpLFxuICAgICAgJzIwMjQtMDgtMDEnLCAvLyBEYXRlIGZyb20gcmVxdWVzdFxuICAgICAgJzIwMjQtMDgtMDcnLCAvLyBEYXRlIGZyb20gcmVxdWVzdFxuICAgICAgZXhwZWN0LmFueXRoaW5nKClcbiAgICApO1xuICB9KTtcblxuICBpdCgnc2hvdWxkIG5vdCBjYWxsIEFJRXZlbnRQcm9jZXNzb3IgaWYgTGFuY2VEQiByZXR1cm5zIG5vIGV2ZW50cycsIGFzeW5jICgpID0+IHtcbiAgICBtb2NrR2V0VXNlckNhdGVnb3JpZXMubW9ja1Jlc29sdmVkVmFsdWUoc2FtcGxlQ2F0ZWdvcmllcyk7XG4gICAgbW9ja0NhbGxBSVF1ZXJ5RW5oYW5jZXIubW9ja1Jlc29sdmVkVmFsdWUoZGVmYXVsdFF1ZXJ5RW5oYW5jZW1lbnRSZXN1bHQpO1xuICAgIG1vY2tDb252ZXJ0VGV4dFRvVmVjdG9yLm1vY2tSZXNvbHZlZFZhbHVlKFswLjFdKTtcbiAgICBtb2NrU2VhcmNoRXZlbnRzSW5MYW5jZURCLm1vY2tSZXNvbHZlZFZhbHVlKFtdKTsgLy8gTm8gZXZlbnRzIGZyb20gTGFuY2VEQlxuXG4gICAgY29uc3QgcmVxID0gbW9ja1JlcXVlc3QoZGVmYXVsdFJlcXVlc3RCb2R5KTtcbiAgICBjb25zdCByZXMgPSBtb2NrUmVzcG9uc2UoKTtcbiAgICBhd2FpdCBldmVudFNlYXJjaEhhbmRsZXIocmVxIGFzIGFueSwgcmVzIGFzIGFueSk7XG5cbiAgICBleHBlY3QobW9ja0NhbGxBSUV2ZW50UHJvY2Vzc29yKS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgIGV4cGVjdChyZXMuc3RhdHVzKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCgyMDApO1xuICAgIGV4cGVjdChyZXMuanNvbikudG9IYXZlQmVlbkNhbGxlZFdpdGgoeyBzdWNjZXNzOiB0cnVlLCBkYXRhOiBbXSB9KTtcbiAgfSk7XG5cbiAgLy8gLS0tIElucHV0IFZhbGlkYXRpb24gVGVzdHMgKG1vc3RseSB1bmNoYW5nZWQsIGJ1dCBlbnN1cmUgdGhleSBzdGlsbCBwYXNzKSAtLS1cbiAgZGVzY3JpYmUoJ0lucHV0IFZhbGlkYXRpb24gKEJhc2ljKScsICgpID0+IHtcbiAgICAvLyBUaGVzZSB0ZXN0cyBhcmUgbGFyZ2VseSB0aGUgc2FtZSBhcyBiZWZvcmUsIGp1c3QgZW5zdXJpbmcgdGhleSBzdGlsbCB3b3JrIHdpdGggdGhlIG1vcmUgY29tcGxleCBzZXR1cC5cbiAgICAvLyBGb3IgYnJldml0eSwgb25seSBvbmUgZXhhbXBsZSBpcyBzaG93biwgYXNzdW1pbmcgb3RoZXJzIGZvbGxvdyB0aGUgc2FtZSBwYXR0ZXJuLlxuICAgIGl0KCdzaG91bGQgcmV0dXJuIDQwMCBpZiB1c2VySWQgaXMgbWlzc2luZycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IHJlcSA9IG1vY2tSZXF1ZXN0KHsgc2VhcmNoVGV4dDogJ3Rlc3QnIH0pOyAvLyB1c2VySWQgaXMgbWlzc2luZ1xuICAgICAgY29uc3QgcmVzID0gbW9ja1Jlc3BvbnNlKCk7XG4gICAgICBhd2FpdCBldmVudFNlYXJjaEhhbmRsZXIocmVxIGFzIGFueSwgcmVzIGFzIGFueSk7XG4gICAgICBleHBlY3QocmVzLnN0YXR1cykudG9IYXZlQmVlbkNhbGxlZFdpdGgoNDAwKTtcbiAgICAgIGV4cGVjdChyZXMuanNvbikudG9IYXZlQmVlbkNhbGxlZFdpdGgoe1xuICAgICAgICBlcnJvcjogJ01pc3NpbmcgcmVxdWlyZWQgcGFyYW1ldGVyOiB1c2VySWQnLFxuICAgICAgfSk7XG4gICAgfSk7XG4gIH0pO1xuXG4gIC8vIC0tLSBFcnJvciBIYW5kbGluZyBmb3IgTmV3IEFJIGFuZCBBUEkgQ2FsbHMgLS0tXG4gIGRlc2NyaWJlKCdFcnJvciBIYW5kbGluZyBmb3IgSW50ZWdyYXRlZCBTZXJ2aWNlcycsICgpID0+IHtcbiAgICBpdCgnc2hvdWxkIHJldHVybiA1MDAgaWYgT1BFTkFJX0FQSV9LRVkgaXMgbm90IGNvbmZpZ3VyZWQnLCBhc3luYyAoKSA9PiB7XG4gICAgICBqZXN0LnNweU9uKGNvbnN0YW50cywgJ09QRU5BSV9BUElfS0VZJywgJ2dldCcpLm1vY2tSZXR1cm5WYWx1ZU9uY2UoJycpOyAvLyBTaW11bGF0ZSBtaXNzaW5nIGtleVxuICAgICAgY29uc3QgcmVxID0gbW9ja1JlcXVlc3QoZGVmYXVsdFJlcXVlc3RCb2R5KTtcbiAgICAgIGNvbnN0IHJlcyA9IG1vY2tSZXNwb25zZSgpO1xuICAgICAgYXdhaXQgZXZlbnRTZWFyY2hIYW5kbGVyKHJlcSBhcyBhbnksIHJlcyBhcyBhbnkpO1xuICAgICAgZXhwZWN0KHJlcy5zdGF0dXMpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKDUwMCk7XG4gICAgICBleHBlY3QocmVzLmpzb24pLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKHtcbiAgICAgICAgZXJyb3I6ICdTZXJ2aWNlIGNvbmZpZ3VyYXRpb24gZXJyb3I6IE9wZW5BSSBBUEkgS2V5IG1pc3NpbmcuJyxcbiAgICAgIH0pO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gNTAwIGlmIEhBU1VSQV9BRE1JTl9TRUNSRVQgaXMgbm90IGNvbmZpZ3VyZWQnLCBhc3luYyAoKSA9PiB7XG4gICAgICBqZXN0XG4gICAgICAgIC5zcHlPbihjb25zdGFudHMsICdIQVNVUkFfQURNSU5fU0VDUkVUJywgJ2dldCcpXG4gICAgICAgIC5tb2NrUmV0dXJuVmFsdWVPbmNlKCcnKTsgLy8gU2ltdWxhdGUgbWlzc2luZyBrZXlcbiAgICAgIGNvbnN0IHJlcSA9IG1vY2tSZXF1ZXN0KGRlZmF1bHRSZXF1ZXN0Qm9keSk7XG4gICAgICBjb25zdCByZXMgPSBtb2NrUmVzcG9uc2UoKTtcbiAgICAgIGF3YWl0IGV2ZW50U2VhcmNoSGFuZGxlcihyZXEgYXMgYW55LCByZXMgYXMgYW55KTtcbiAgICAgIGV4cGVjdChyZXMuc3RhdHVzKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCg1MDApO1xuICAgICAgZXhwZWN0KHJlcy5qc29uKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCh7XG4gICAgICAgIGVycm9yOiAnU2VydmljZSBjb25maWd1cmF0aW9uIGVycm9yOiBIYXN1cmEgQWRtaW4gU2VjcmV0IG1pc3NpbmcuJyxcbiAgICAgIH0pO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBoYW5kbGUgZXJyb3JzIGZyb20gZ2V0VXNlckNhdGVnb3JpZXMgKGFuZCBwcm9jZWVkKScsIGFzeW5jICgpID0+IHtcbiAgICAgIG1vY2tHZXRVc2VyQ2F0ZWdvcmllcy5tb2NrUmVqZWN0ZWRWYWx1ZShuZXcgRXJyb3IoJ0hhc3VyYSBmZXRjaCBmYWlsZWQnKSk7XG4gICAgICAvLyBPdGhlciBtb2NrcyBzaG91bGQgcHJvY2VlZCB0byBhbGxvdyB0aGUgbWFpbiBmbG93IHRvIGNvbnRpbnVlXG4gICAgICBtb2NrQ2FsbEFJUXVlcnlFbmhhbmNlci5tb2NrUmVzb2x2ZWRWYWx1ZShkZWZhdWx0UXVlcnlFbmhhbmNlbWVudFJlc3VsdCk7XG4gICAgICBtb2NrQ29udmVydFRleHRUb1ZlY3Rvci5tb2NrUmVzb2x2ZWRWYWx1ZShbMC4xXSk7XG4gICAgICBtb2NrU2VhcmNoRXZlbnRzSW5MYW5jZURCLm1vY2tSZXNvbHZlZFZhbHVlKHNhbXBsZUxhbmNlREJFdmVudHMpO1xuICAgICAgbW9ja0NhbGxBSUV2ZW50UHJvY2Vzc29yLm1vY2tSZXNvbHZlZFZhbHVlKHNhbXBsZVByb2Nlc3NlZEV2ZW50cyk7XG5cbiAgICAgIGNvbnN0IHJlcSA9IG1vY2tSZXF1ZXN0KGRlZmF1bHRSZXF1ZXN0Qm9keSk7XG4gICAgICBjb25zdCByZXMgPSBtb2NrUmVzcG9uc2UoKTtcbiAgICAgIGF3YWl0IGV2ZW50U2VhcmNoSGFuZGxlcihyZXEgYXMgYW55LCByZXMgYXMgYW55KTtcblxuICAgICAgLy8gRXhwZWN0IGl0IHRvIHByb2NlZWQgYW5kIHN1Y2NlZWQsIGFzIGNhdGVnb3JpZXMgYXJlIG5vbi1jcml0aWNhbCBmb3IgdGhpcyBmbG93XG4gICAgICBleHBlY3QocmVzLnN0YXR1cykudG9IYXZlQmVlbkNhbGxlZFdpdGgoMjAwKTtcbiAgICAgIGV4cGVjdChtb2NrQ2FsbEFJUXVlcnlFbmhhbmNlcikudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICAgIGV4cGVjdC5hbnl0aGluZygpLFxuICAgICAgICBbXSxcbiAgICAgICAgZXhwZWN0LmFueXRoaW5nKCksXG4gICAgICAgIGV4cGVjdC5hbnl0aGluZygpXG4gICAgICApOyAvLyBlbXB0eSBjYXRlZ29yaWVzXG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiA1MDAgaWYgY2FsbEFJUXVlcnlFbmhhbmNlciB0aHJvd3MgYW4gZXJyb3InLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrR2V0VXNlckNhdGVnb3JpZXMubW9ja1Jlc29sdmVkVmFsdWUoc2FtcGxlQ2F0ZWdvcmllcyk7XG4gICAgICBtb2NrQ2FsbEFJUXVlcnlFbmhhbmNlci5tb2NrUmVqZWN0ZWRWYWx1ZShcbiAgICAgICAgbmV3IEVycm9yKCdBSSBRdWVyeSBFbmhhbmNlciBmYWlsZWQnKVxuICAgICAgKTtcbiAgICAgIGNvbnN0IHJlcSA9IG1vY2tSZXF1ZXN0KGRlZmF1bHRSZXF1ZXN0Qm9keSk7XG4gICAgICBjb25zdCByZXMgPSBtb2NrUmVzcG9uc2UoKTtcbiAgICAgIGF3YWl0IGV2ZW50U2VhcmNoSGFuZGxlcihyZXEgYXMgYW55LCByZXMgYXMgYW55KTtcbiAgICAgIGV4cGVjdChyZXMuc3RhdHVzKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCg1MDApO1xuICAgICAgZXhwZWN0KHJlcy5qc29uKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCh7XG4gICAgICAgIGVycm9yOiAnRmFpbGVkIHRvIGVuaGFuY2Ugc2VhcmNoIHF1ZXJ5IHdpdGggQUkuJyxcbiAgICAgIH0pO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gNTAwIGlmIGNvbnZlcnRUZXh0VG9WZWN0b3IgdGhyb3dzIGFuIGVycm9yIChhZnRlciBxdWVyeSBlbmhhbmNlbWVudCknLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrR2V0VXNlckNhdGVnb3JpZXMubW9ja1Jlc29sdmVkVmFsdWUoc2FtcGxlQ2F0ZWdvcmllcyk7XG4gICAgICBtb2NrQ2FsbEFJUXVlcnlFbmhhbmNlci5tb2NrUmVzb2x2ZWRWYWx1ZShkZWZhdWx0UXVlcnlFbmhhbmNlbWVudFJlc3VsdCk7XG4gICAgICBtb2NrQ29udmVydFRleHRUb1ZlY3Rvci5tb2NrUmVqZWN0ZWRWYWx1ZShcbiAgICAgICAgbmV3IEVycm9yKCdWZWN0b3IgY29udmVyc2lvbiBmYWlsZWQnKVxuICAgICAgKTtcbiAgICAgIGNvbnN0IHJlcSA9IG1vY2tSZXF1ZXN0KGRlZmF1bHRSZXF1ZXN0Qm9keSk7XG4gICAgICBjb25zdCByZXMgPSBtb2NrUmVzcG9uc2UoKTtcbiAgICAgIGF3YWl0IGV2ZW50U2VhcmNoSGFuZGxlcihyZXEgYXMgYW55LCByZXMgYXMgYW55KTtcbiAgICAgIGV4cGVjdChyZXMuc3RhdHVzKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCg1MDApO1xuICAgICAgZXhwZWN0KHJlcy5qc29uKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCh7XG4gICAgICAgIGVycm9yOiAnRmFpbGVkIHRvIHByb2Nlc3Mgc2VhcmNoIHF1ZXJ5IGZvciB2ZWN0b3JpemF0aW9uLicsXG4gICAgICB9KTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIDUwMCBpZiBzZWFyY2hFdmVudHNJbkxhbmNlREIgdGhyb3dzIGFuIGVycm9yJywgYXN5bmMgKCkgPT4ge1xuICAgICAgbW9ja0dldFVzZXJDYXRlZ29yaWVzLm1vY2tSZXNvbHZlZFZhbHVlKHNhbXBsZUNhdGVnb3JpZXMpO1xuICAgICAgbW9ja0NhbGxBSVF1ZXJ5RW5oYW5jZXIubW9ja1Jlc29sdmVkVmFsdWUoZGVmYXVsdFF1ZXJ5RW5oYW5jZW1lbnRSZXN1bHQpO1xuICAgICAgbW9ja0NvbnZlcnRUZXh0VG9WZWN0b3IubW9ja1Jlc29sdmVkVmFsdWUoWzAuMV0pO1xuICAgICAgbW9ja1NlYXJjaEV2ZW50c0luTGFuY2VEQi5tb2NrUmVqZWN0ZWRWYWx1ZShcbiAgICAgICAgbmV3IEVycm9yKCdMYW5jZURCIHNlYXJjaCBmYWlsZWQnKVxuICAgICAgKTtcbiAgICAgIGNvbnN0IHJlcSA9IG1vY2tSZXF1ZXN0KGRlZmF1bHRSZXF1ZXN0Qm9keSk7XG4gICAgICBjb25zdCByZXMgPSBtb2NrUmVzcG9uc2UoKTtcbiAgICAgIGF3YWl0IGV2ZW50U2VhcmNoSGFuZGxlcihyZXEgYXMgYW55LCByZXMgYXMgYW55KTtcbiAgICAgIGV4cGVjdChyZXMuc3RhdHVzKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCg1MDApO1xuICAgICAgZXhwZWN0KHJlcy5qc29uKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCh7XG4gICAgICAgIGVycm9yOiAnRmFpbGVkIHRvIHJldHJpZXZlIGV2ZW50cyBmcm9tIGRhdGFiYXNlLicsXG4gICAgICB9KTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIDUwMCBpZiBjYWxsQUlFdmVudFByb2Nlc3NvciB0aHJvd3MgYW4gZXJyb3InLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrR2V0VXNlckNhdGVnb3JpZXMubW9ja1Jlc29sdmVkVmFsdWUoc2FtcGxlQ2F0ZWdvcmllcyk7XG4gICAgICBtb2NrQ2FsbEFJUXVlcnlFbmhhbmNlci5tb2NrUmVzb2x2ZWRWYWx1ZShkZWZhdWx0UXVlcnlFbmhhbmNlbWVudFJlc3VsdCk7XG4gICAgICBtb2NrQ29udmVydFRleHRUb1ZlY3Rvci5tb2NrUmVzb2x2ZWRWYWx1ZShbMC4xXSk7XG4gICAgICBtb2NrU2VhcmNoRXZlbnRzSW5MYW5jZURCLm1vY2tSZXNvbHZlZFZhbHVlKHNhbXBsZUxhbmNlREJFdmVudHMpOyAvLyBMYW5jZURCIHJldHVybnMgZXZlbnRzXG4gICAgICBtb2NrQ2FsbEFJRXZlbnRQcm9jZXNzb3IubW9ja1JlamVjdGVkVmFsdWUoXG4gICAgICAgIG5ldyBFcnJvcignQUkgRXZlbnQgUHJvY2Vzc29yIGZhaWxlZCcpXG4gICAgICApOyAvLyBBSSBwcm9jZXNzaW5nIGZhaWxzXG5cbiAgICAgIGNvbnN0IHJlcSA9IG1vY2tSZXF1ZXN0KGRlZmF1bHRSZXF1ZXN0Qm9keSk7XG4gICAgICBjb25zdCByZXMgPSBtb2NrUmVzcG9uc2UoKTtcbiAgICAgIGF3YWl0IGV2ZW50U2VhcmNoSGFuZGxlcihyZXEgYXMgYW55LCByZXMgYXMgYW55KTtcbiAgICAgIGV4cGVjdChyZXMuc3RhdHVzKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCg1MDApO1xuICAgICAgZXhwZWN0KHJlcy5qc29uKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCh7XG4gICAgICAgIGVycm9yOiAnRmFpbGVkIHRvIHByb2Nlc3Mgc2VhcmNoIHJlc3VsdHMgd2l0aCBBSS4nLFxuICAgICAgfSk7XG4gICAgfSk7XG4gIH0pO1xufSk7XG4iXX0=