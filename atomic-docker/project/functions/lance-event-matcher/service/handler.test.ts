import { eventSearchHandler } from './handler'; // Assuming handler.ts is the entry point
import * as apiHelper from '../_libs/api_helper';
import * as lancedbConnect from '../_libs/lancedb_connect';
import { SearchRequest, EventRecord } from '../_libs/types';
import * as fs from 'fs';
import * as path from 'path';

// Mock dependencies
jest.mock('../_libs/api_helper', () => ({
  convertTextToVector: jest.fn(),
  // We don't mock searchEventsInLanceDB directly, but rather its constituent parts if called from handler
  // However, handler calls searchEventsInLanceDB, so we mock it.
  searchEventsInLanceDB: jest.fn(),
}));

jest.mock('../_libs/lancedb_connect'); // Not used directly by handler, but searchEventsInLanceDB uses it.

const mockConvertTextToVector = apiHelper.convertTextToVector as jest.Mock;
const mockSearchEventsInLanceDB = apiHelper.searchEventsInLanceDB as jest.Mock;


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
  beforeEach(() => {
    mockConvertTextToVector.mockClear();
    mockSearchEventsInLanceDB.mockClear();
  });

  const defaultRequestBody: SearchRequest = {
    userId: 'user123',
    searchText: 'Team meeting',
    limit: 5,
  };

  const sampleEventRecords: EventRecord[] = [
    { id: 'evt1', userId: 'user123', vector: [0.1], start_date: '2024-01-01T10:00:00Z', end_date: '2024-01-01T11:00:00Z', raw_event_text: 'Team meeting notes' },
    { id: 'evt2', userId: 'user123', vector: [0.2], start_date: '2024-01-02T14:00:00Z', end_date: '2024-01-02T15:00:00Z', raw_event_text: 'Follow up on team meeting' },
  ];

  it('should return matching events for a successful search without date filters', async () => {
    const mockVector = [0.1, 0.2, 0.3];
    mockConvertTextToVector.mockResolvedValue(mockVector);
    mockSearchEventsInLanceDB.mockResolvedValue(sampleEventRecords);

    const req = mockRequest(defaultRequestBody);
    const res = mockResponse();

    await eventSearchHandler(req as any, res as any);

    expect(mockConvertTextToVector).toHaveBeenCalledWith(defaultRequestBody.searchText);
    expect(mockSearchEventsInLanceDB).toHaveBeenCalledWith(
      defaultRequestBody.userId,
      mockVector,
      undefined, // startDate
      undefined, // endDate
      defaultRequestBody.limit
    );
    expect(res.status).toHaveBeenCalledWith(200);
    expect(res.json).toHaveBeenCalledWith({
      success: true,
      data: sampleEventRecords.map(e => ({ ...e, vector: [] })), // vector excluded in response
    });
  });

  it('should call searchEventsInLanceDB with date filters if provided', async () => {
    const mockVector = [0.4, 0.5, 0.6];
    mockConvertTextToVector.mockResolvedValue(mockVector);
    mockSearchEventsInLanceDB.mockResolvedValue([]);

    const requestBodyWithDates: SearchRequest = {
      ...defaultRequestBody,
      startDate: '2024-01-01T00:00:00Z',
      endDate: '2024-01-05T23:59:59Z',
    };
    const req = mockRequest(requestBodyWithDates);
    const res = mockResponse();

    await eventSearchHandler(req as any, res as any);

    expect(mockSearchEventsInLanceDB).toHaveBeenCalledWith(
      requestBodyWithDates.userId,
      mockVector,
      requestBodyWithDates.startDate,
      requestBodyWithDates.endDate,
      requestBodyWithDates.limit
    );
    expect(res.status).toHaveBeenCalledWith(200);
  });

  it('should return an empty array when search yields no results', async () => {
    const mockVector = [0.1, 0.2, 0.3];
    mockConvertTextToVector.mockResolvedValue(mockVector);
    mockSearchEventsInLanceDB.mockResolvedValue([]); // No results

    const req = mockRequest(defaultRequestBody);
    const res = mockResponse();

    await eventSearchHandler(req as any, res as any);

    expect(res.status).toHaveBeenCalledWith(200);
    expect(res.json).toHaveBeenCalledWith({ success: true, data: [] });
  });


  describe('Input Validation', () => {
    const testCases = [
      { field: 'userId', value: undefined, expectedMessage: 'Missing required parameter: userId' },
      { field: 'searchText', value: undefined, expectedMessage: 'Missing required parameter: searchText' },
      { field: 'searchText', value: '', expectedMessage: 'Parameter searchText must be a non-empty string.' },
      { field: 'searchText', value: '  ', expectedMessage: 'Parameter searchText must be a non-empty string.' },
      { field: 'limit', value: 0, expectedMessage: 'Parameter limit must be a positive number.' },
      { field: 'limit', value: -5, expectedMessage: 'Parameter limit must be a positive number.' },
      // @ts-ignore to test invalid type
      { field: 'limit', value: 'not-a-number', expectedMessage: 'Parameter limit must be a positive number.' },
    ];

    testCases.forEach(({ field, value, expectedMessage }) => {
      it(`should return 400 if ${field} is invalid (${value})`, async () => {
        const invalidBody = { ...defaultRequestBody, [field]: value };
        // Need to remove the field if value is undefined, as it wouldn't be in req.body
        if (value === undefined) delete invalidBody[field];

        const req = mockRequest(invalidBody);
        const res = mockResponse();

        await eventSearchHandler(req as any, res as any);

        expect(res.status).toHaveBeenCalledWith(400);
        expect(res.json).toHaveBeenCalledWith({ error: expectedMessage });
      });
    });
  });

  it('should handle errors from convertTextToVector', async () => {
    const errorMessage = 'OpenAI API error during vector conversion: Test error';
    mockConvertTextToVector.mockRejectedValue(new Error(errorMessage));

    const req = mockRequest(defaultRequestBody);
    const res = mockResponse();

    await eventSearchHandler(req as any, res as any);

    expect(res.status).toHaveBeenCalledWith(500);
    expect(res.json).toHaveBeenCalledWith({ error: `Service error: ${errorMessage}` });
  });

  it('should handle errors from searchEventsInLanceDB', async () => {
    const mockVector = [0.1,0.2,0.3];
    mockConvertTextToVector.mockResolvedValue(mockVector);
    const errorMessage = 'LanceDB search failed: Test DB error';
    mockSearchEventsInLanceDB.mockRejectedValue(new Error(errorMessage));

    const req = mockRequest(defaultRequestBody);
    const res = mockResponse();

    await eventSearchHandler(req as any, res as any);

    expect(res.status).toHaveBeenCalledWith(500);
    expect(res.json).toHaveBeenCalledWith({ error: `Service error: ${errorMessage}` });
  });

  it('should handle generic errors', async () => {
    // Make convertTextToVector succeed, but searchEventsInLanceDB throw a generic error
    mockConvertTextToVector.mockResolvedValue([0.1, 0.2, 0.3]);
    const genericErrorMessage = "A very generic error";
    mockSearchEventsInLanceDB.mockRejectedValue(new Error(genericErrorMessage));

    const req = mockRequest(defaultRequestBody);
    const res = mockResponse();

    await eventSearchHandler(req as any, res as any);

    expect(res.status).toHaveBeenCalledWith(500);
    expect(res.json).toHaveBeenCalledWith({ error: 'An unexpected error occurred.' });
  });

  // This test reads the actual handler file content.
  // It's a bit unusual for a unit test but specifically requested.
  it('should contain placeholder comments for AI Agent Integration', () => {
    const handlerFilePath = path.join(__dirname, 'handler.ts');
    try {
      const handlerFileContent = fs.readFileSync(handlerFilePath, 'utf8');
      expect(handlerFileContent).toContain('// TODO: Process LanceDB results with AI agent to find and apply event types.');
      expect(handlerFileContent).toContain("// This will involve calling the AI agent's API with the event data");
      expect(handlerFileContent).toContain("// and using its response to enrich or modify the event information.");
    } catch (err) {
      // If the file can't be read, fail the test explicitly.
      // This might happen if the test execution environment is different from expected.
      throw new Error(`Could not read handler.ts for comment verification: ${err.message}`);
    }
  });
});
