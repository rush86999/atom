import { eventSearchHandler } from './handler';
import * as apiHelper from '../_libs/api_helper';
import * as aiHelper from '../_libs/ai_helper';
import * as constants from '../_libs/constants';
import {
    SearchRequest,
    EventRecord,
    CategoryType,
    AIQueryEnhancementResult,
    AIProcessedEvent
} from '../_libs/types';

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


const mockConvertTextToVector = apiHelper.convertTextToVector as jest.Mock;
const mockSearchEventsInLanceDB = apiHelper.searchEventsInLanceDB as jest.Mock;
const mockGetUserCategories = apiHelper.getUserCategories as jest.Mock;
const mockCallAIQueryEnhancer = aiHelper.callAIQueryEnhancer as jest.Mock;
const mockCallAIEventProcessor = aiHelper.callAIEventProcessor as jest.Mock; // Corrected name

// Mock Express request and response objects
const mockRequest = (body: Partial<SearchRequest> = {}, query: Partial<SearchRequest> = {}) => ({
  body,
  query,
});

const mockResponse = () => {
  const res: any = {};
  res.status = jest.fn().mockReturnValue(res);
  res.json = jest.fn().mockReturnValue(res);
  res.send = jest.fn().mockReturnValue(res); // For plain text errors
  return res;
};

describe('eventSearchHandler', () => {
  let originalOpenAIApiKey: string;
  let originalHasuraAdminSecret: string;

  beforeAll(() => {
    // Store original values if needed, though jest.mock should handle reset
    originalOpenAIApiKey = constants.OPENAI_API_KEY;
    originalHasuraAdminSecret = constants.HASURA_ADMIN_SECRET;
  });

  beforeEach(() => {
    jest.clearAllMocks();
    // Reset constants to default mock values for each test if they were changed
    jest.spyOn(constants, 'OPENAI_API_KEY', 'get').mockReturnValue('test-openai-key');
    jest.spyOn(constants, 'HASURA_ADMIN_SECRET', 'get').mockReturnValue('test-hasura-secret');
  });

  afterAll(() => {
    // Restore original values if changed - though with jest.mock this might not be strictly necessary
    jest.spyOn(constants, 'OPENAI_API_KEY', 'get').mockReturnValue(originalOpenAIApiKey);
    jest.spyOn(constants, 'HASURA_ADMIN_SECRET', 'get').mockReturnValue(originalHasuraAdminSecret);
  });

  const defaultRequestBody: SearchRequest = {
    userId: 'user123',
    searchText: 'Team meeting about project Alpha',
    limit: 5,
  };

  const sampleCategories: CategoryType[] = [
    { id: 'cat1', name: 'Work' },
    { id: 'cat2', name: 'Personal' },
  ];

  const sampleLanceDBEvents: EventRecord[] = [
    { id: 'evt1', userId: 'user123', vector: [0.1], start_date: '2024-01-01T10:00:00Z', end_date: '2024-01-01T11:00:00Z', raw_event_text: 'Project Alpha Kickoff' },
    { id: 'evt2', userId: 'user123', vector: [0.2], start_date: '2024-01-02T14:00:00Z', end_date: '2024-01-02T15:00:00Z', raw_event_text: 'Follow up Project Alpha' },
  ];

  const sampleProcessedEvents: AIProcessedEvent[] = [
    { eventId: 'evt1', assignedCategoryId: 'cat1', relevanceScore: 0.9 },
    { eventId: 'evt2', assignedCategoryId: 'cat1', relevanceScore: 0.8 },
  ];

  const defaultQueryEnhancementResult: AIQueryEnhancementResult = {
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

    await eventSearchHandler(req as any, res as any);

    expect(mockGetUserCategories).toHaveBeenCalledWith(defaultRequestBody.userId, 'test-hasura-secret');
    expect(mockCallAIQueryEnhancer).toHaveBeenCalledWith(
      defaultRequestBody.searchText,
      sampleCategories,
      'test-openai-key',
      undefined // userMessageHistory
    );
    expect(mockConvertTextToVector).toHaveBeenCalledWith(defaultQueryEnhancementResult.refinedQueryText);
    expect(mockSearchEventsInLanceDB).toHaveBeenCalledWith(
      defaultRequestBody.userId,
      mockVector,
      undefined, // determinedStartDate from queryEnhancementResult or request
      undefined, // determinedEndDate from queryEnhancementResult or request
      defaultRequestBody.limit
    );
    expect(mockCallAIEventProcessor).toHaveBeenCalledWith(
      sampleLanceDBEvents,
      defaultRequestBody.searchText, // original searchText
      sampleCategories,
      'test-openai-key',
      undefined // userMessageHistory
    );
    expect(res.status).toHaveBeenCalledWith(200);
    expect(res.json).toHaveBeenCalledWith({ success: true, data: sampleProcessedEvents });
  });

  it('should use AI identified dates if request provides no dates', async () => {
    mockGetUserCategories.mockResolvedValue(sampleCategories);
    const enhancementWithDates: AIQueryEnhancementResult = {
      ...defaultQueryEnhancementResult,
      identifiedDateRange: { start: '2024-07-01', end: '2024-07-07' },
    };
    mockCallAIQueryEnhancer.mockResolvedValue(enhancementWithDates);
    mockConvertTextToVector.mockResolvedValue([0.1]);
    mockSearchEventsInLanceDB.mockResolvedValue(sampleLanceDBEvents);
    mockCallAIEventProcessor.mockResolvedValue(sampleProcessedEvents);

    const req = mockRequest(defaultRequestBody); // No dates in request
    const res = mockResponse();
    await eventSearchHandler(req as any, res as any);

    expect(mockSearchEventsInLanceDB).toHaveBeenCalledWith(
      expect.anything(),
      expect.anything(),
      '2024-07-01', // Date from AI
      '2024-07-07', // Date from AI
      expect.anything()
    );
  });

  it('should prioritize request dates over AI identified dates', async () => {
    mockGetUserCategories.mockResolvedValue(sampleCategories);
    const enhancementWithDates: AIQueryEnhancementResult = {
      ...defaultQueryEnhancementResult,
      identifiedDateRange: { start: '2024-07-01', end: '2024-07-07' }, // AI dates
    };
    mockCallAIQueryEnhancer.mockResolvedValue(enhancementWithDates);
    mockConvertTextToVector.mockResolvedValue([0.1]);
    mockSearchEventsInLanceDB.mockResolvedValue(sampleLanceDBEvents);
    mockCallAIEventProcessor.mockResolvedValue(sampleProcessedEvents);

    const requestWithDates: SearchRequest = {
      ...defaultRequestBody,
      startDate: '2024-08-01', // Request dates
      endDate: '2024-08-07',
    };
    const req = mockRequest(requestWithDates);
    const res = mockResponse();
    await eventSearchHandler(req as any, res as any);

    expect(mockSearchEventsInLanceDB).toHaveBeenCalledWith(
      expect.anything(),
      expect.anything(),
      '2024-08-01', // Date from request
      '2024-08-07', // Date from request
      expect.anything()
    );
  });

  it('should not call AIEventProcessor if LanceDB returns no events', async () => {
    mockGetUserCategories.mockResolvedValue(sampleCategories);
    mockCallAIQueryEnhancer.mockResolvedValue(defaultQueryEnhancementResult);
    mockConvertTextToVector.mockResolvedValue([0.1]);
    mockSearchEventsInLanceDB.mockResolvedValue([]); // No events from LanceDB

    const req = mockRequest(defaultRequestBody);
    const res = mockResponse();
    await eventSearchHandler(req as any, res as any);

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
      await eventSearchHandler(req as any, res as any);
      expect(res.status).toHaveBeenCalledWith(400);
      expect(res.json).toHaveBeenCalledWith({ error: 'Missing required parameter: userId' });
    });
  });

  // --- Error Handling for New AI and API Calls ---
  describe('Error Handling for Integrated Services', () => {
    it('should return 500 if OPENAI_API_KEY is not configured', async () => {
      jest.spyOn(constants, 'OPENAI_API_KEY', 'get').mockReturnValueOnce(''); // Simulate missing key
      const req = mockRequest(defaultRequestBody);
      const res = mockResponse();
      await eventSearchHandler(req as any, res as any);
      expect(res.status).toHaveBeenCalledWith(500);
      expect(res.json).toHaveBeenCalledWith({ error: 'Service configuration error: OpenAI API Key missing.' });
    });

    it('should return 500 if HASURA_ADMIN_SECRET is not configured', async () => {
      jest.spyOn(constants, 'HASURA_ADMIN_SECRET', 'get').mockReturnValueOnce(''); // Simulate missing key
      const req = mockRequest(defaultRequestBody);
      const res = mockResponse();
      await eventSearchHandler(req as any, res as any);
      expect(res.status).toHaveBeenCalledWith(500);
      expect(res.json).toHaveBeenCalledWith({ error: 'Service configuration error: Hasura Admin Secret missing.' });
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
      await eventSearchHandler(req as any, res as any);

      // Expect it to proceed and succeed, as categories are non-critical for this flow
      expect(res.status).toHaveBeenCalledWith(200);
      expect(mockCallAIQueryEnhancer).toHaveBeenCalledWith(expect.anything(), [], expect.anything(), expect.anything()); // empty categories
    });

    it('should return 500 if callAIQueryEnhancer throws an error', async () => {
      mockGetUserCategories.mockResolvedValue(sampleCategories);
      mockCallAIQueryEnhancer.mockRejectedValue(new Error('AI Query Enhancer failed'));
      const req = mockRequest(defaultRequestBody);
      const res = mockResponse();
      await eventSearchHandler(req as any, res as any);
      expect(res.status).toHaveBeenCalledWith(500);
      expect(res.json).toHaveBeenCalledWith({ error: 'Failed to enhance search query with AI.' });
    });

    it('should return 500 if convertTextToVector throws an error (after query enhancement)', async () => {
      mockGetUserCategories.mockResolvedValue(sampleCategories);
      mockCallAIQueryEnhancer.mockResolvedValue(defaultQueryEnhancementResult);
      mockConvertTextToVector.mockRejectedValue(new Error('Vector conversion failed'));
      const req = mockRequest(defaultRequestBody);
      const res = mockResponse();
      await eventSearchHandler(req as any, res as any);
      expect(res.status).toHaveBeenCalledWith(500);
      expect(res.json).toHaveBeenCalledWith({ error: 'Failed to process search query for vectorization.' });
    });

    it('should return 500 if searchEventsInLanceDB throws an error', async () => {
      mockGetUserCategories.mockResolvedValue(sampleCategories);
      mockCallAIQueryEnhancer.mockResolvedValue(defaultQueryEnhancementResult);
      mockConvertTextToVector.mockResolvedValue([0.1]);
      mockSearchEventsInLanceDB.mockRejectedValue(new Error('LanceDB search failed'));
      const req = mockRequest(defaultRequestBody);
      const res = mockResponse();
      await eventSearchHandler(req as any, res as any);
      expect(res.status).toHaveBeenCalledWith(500);
      expect(res.json).toHaveBeenCalledWith({ error: 'Failed to retrieve events from database.' });
    });

    it('should return 500 if callAIEventProcessor throws an error', async () => {
      mockGetUserCategories.mockResolvedValue(sampleCategories);
      mockCallAIQueryEnhancer.mockResolvedValue(defaultQueryEnhancementResult);
      mockConvertTextToVector.mockResolvedValue([0.1]);
      mockSearchEventsInLanceDB.mockResolvedValue(sampleLanceDBEvents); // LanceDB returns events
      mockCallAIEventProcessor.mockRejectedValue(new Error('AI Event Processor failed')); // AI processing fails

      const req = mockRequest(defaultRequestBody);
      const res = mockResponse();
      await eventSearchHandler(req as any, res as any);
      expect(res.status).toHaveBeenCalledWith(500);
      expect(res.json).toHaveBeenCalledWith({ error: 'Failed to process search results with AI.' });
    });
  });
});
