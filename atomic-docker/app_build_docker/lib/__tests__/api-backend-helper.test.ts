import { scheduleMeeting } from '../api-backend-helper';
import { ScheduleMeetingRequestType } from '../dataTypes/ScheduleMeetingRequestType';
import { SCHEDULER_API_URL } from '../constants';
import got from 'got';

// Mock the 'got' module
jest.mock('got');

const mockGot = got as jest.Mocked<typeof got>;

describe('api-backend-helper', () => {
  describe('scheduleMeeting', () => {
    const mockPayload: ScheduleMeetingRequestType = {
      participantNames: ['Alice', 'Bob'],
      durationMinutes: 30,
      preferredDate: '2024-07-25',
      preferredTime: '10:00:00',
    };
    const expectedUrl = `${SCHEDULER_API_URL}/timeTable/user/scheduleMeeting`;

    beforeEach(() => {
      // Clear all mock implementations and calls before each test
      mockGot.post.mockClear();
    });

    it('should make a POST request to the correct URL with the correct payload', async () => {
      const mockApiResponse = { data: { meetingId: '123' } };
      // Mock the chained .json() call
      mockGot.post.mockReturnValue({
        json: jest.fn().mockResolvedValue(mockApiResponse),
      } as any); // eslint-disable-line @typescript-eslint/no-explicit-any

      await scheduleMeeting(mockPayload);

      expect(mockGot.post).toHaveBeenCalledTimes(1);
      expect(mockGot.post).toHaveBeenCalledWith(expectedUrl, {
        json: mockPayload,
        headers: {
          'Content-Type': 'application/json',
        },
      });
    });

    it('should return the JSON response from the API on success', async () => {
      const mockApiResponse = { meetingId: 'xyz789', status: 'SCHEDULED' };
      mockGot.post.mockReturnValue({
        json: jest.fn().mockResolvedValue(mockApiResponse),
      } as any); // eslint-disable-line @typescript-eslint/no-explicit-any

      const result = await scheduleMeeting(mockPayload);

      expect(result).toEqual(mockApiResponse);
    });

    it('should throw an error if the API call fails (network error)', async () => {
      const networkError = new Error('Network failure');
      mockGot.post.mockRejectedValue(networkError);

      await expect(scheduleMeeting(mockPayload)).rejects.toThrow('Network failure');
    });

    it('should throw a structured error if API returns an error response with JSON body', async () => {
      const errorResponse = {
        statusCode: 400,
        body: JSON.stringify({ message: 'Invalid participants' }),
      };
      // Simulate got's error structure
      const apiError = { response: errorResponse, message: 'Response code 400 (Bad Request)' } as any; // eslint-disable-line @typescript-eslint/no-explicit-any
      mockGot.post.mockRejectedValue(apiError);

      await expect(scheduleMeeting(mockPayload)).rejects.toThrow('API Error: Invalid participants');
    });

    it('should throw a generic error if API returns an error response with non-JSON body', async () => {
        const errorResponse = {
          statusCode: 500,
          body: 'Internal Server Error Text',
        };
        const apiError = { response: errorResponse, message: 'Response code 500 (Internal Server Error)' } as any; // eslint-disable-line @typescript-eslint/no-explicit-any
        mockGot.post.mockRejectedValue(apiError);

        await expect(scheduleMeeting(mockPayload)).rejects.toThrow('API Error: Internal Server Error Text');
      });

    it('should throw a generic error if parsing error body fails', async () => {
        const errorResponse = {
            statusCode: 400,
            body: 'This is not JSON', // Non-JSON error body
        };
        const apiError = { response: errorResponse, message: 'Response code 400 (Bad Request)' } as any; // eslint-disable-line @typescript-eslint/no-explicit-any
        mockGot.post.mockRejectedValue(apiError);

        // The error message will be the non-JSON string itself
        await expect(scheduleMeeting(mockPayload)).rejects.toThrow(`API Error: ${errorResponse.body}`);
    });
  });
});
