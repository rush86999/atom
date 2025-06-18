import { listZoomMeetings, getZoomMeetingDetails, resetTokenCache } from './zoomSkills';
import axios from 'axios';
import * as constants from '../_libs/constants';
import { ZoomMeeting, ZoomTokenResponse } from '../types'; // Assuming types are correctly defined

// Mock external dependencies
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

jest.mock('../_libs/constants', () => ({
  ATOM_ZOOM_ACCOUNT_ID: 'test_account_id',
  ATOM_ZOOM_CLIENT_ID: 'test_client_id',
  ATOM_ZOOM_CLIENT_SECRET: 'test_client_secret',
}));

// Spy on console.error and console.log
let consoleErrorSpy: jest.SpyInstance;
let consoleLogSpy: jest.SpyInstance;

describe('zoomSkills', () => {
  beforeEach(() => {
    mockedAxios.post.mockReset();
    mockedAxios.get.mockReset();
    resetTokenCache(); // Reset the in-memory token cache before each test

    // Set default mock values for constants for each test, can be overridden by spyOn
    jest.spyOn(constants, 'ATOM_ZOOM_ACCOUNT_ID', 'get').mockReturnValue('test_account_id');
    jest.spyOn(constants, 'ATOM_ZOOM_CLIENT_ID', 'get').mockReturnValue('test_client_id');
    jest.spyOn(constants, 'ATOM_ZOOM_CLIENT_SECRET', 'get').mockReturnValue('test_client_secret');

    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.clearAllMocks(); // Clears all mocks, including spies
    consoleErrorSpy.mockRestore();
    consoleLogSpy.mockRestore();
  });

  describe('getZoomAccessToken (tested implicitly via skill functions)', () => {
    const mockZoomUserId = 'user123';

    it('should fetch and cache a new token successfully', async () => {
      mockedAxios.post.mockResolvedValueOnce({
        data: { access_token: 'new_token_123', expires_in: 3600, token_type: 'Bearer' } as ZoomTokenResponse,
        status: 200,
      });
      mockedAxios.get.mockResolvedValueOnce({ data: { meetings: [] } }); // For listZoomMeetings call

      await listZoomMeetings(mockZoomUserId); // First call, fetches and caches token
      expect(mockedAxios.post).toHaveBeenCalledTimes(1);
      expect(mockedAxios.post).toHaveBeenCalledWith(
        'https://zoom.us/oauth/token',
        expect.stringContaining('grant_type=account_credentials'),
        expect.objectContaining({
          headers: expect.objectContaining({ 'Authorization': expect.stringContaining('Basic ') }),
        })
      );

      mockedAxios.get.mockClear(); // Clear get mock before next call
      mockedAxios.get.mockResolvedValueOnce({ data: { meetings: [] } }); // Mock for second listZoomMeetings

      await listZoomMeetings(mockZoomUserId); // Second call, should use cached token
      expect(mockedAxios.post).toHaveBeenCalledTimes(1); // Still 1, token was cached
      expect(mockedAxios.get).toHaveBeenCalledTimes(1); // listZoomMeetings' GET was called
    });

    it('should refresh token if expired', async () => {
      mockedAxios.post.mockResolvedValueOnce({ // Initial token, expires quickly
        data: { access_token: 'token_initial', expires_in: 1 }, status: 200,
      });
      mockedAxios.post.mockResolvedValueOnce({ // Refreshed token
        data: { access_token: 'token_refreshed', expires_in: 3600 }, status: 200,
      });
      mockedAxios.get.mockResolvedValue({ data: { meetings: [] } }); // For listZoomMeetings

      await listZoomMeetings(mockZoomUserId); // Initial call
      expect(mockedAxios.post).toHaveBeenCalledTimes(1);

      jest.useFakeTimers();
      jest.advanceTimersByTime(2000); // Advance time by 2 seconds, enough for token to expire
      jest.useRealTimers();

      await listZoomMeetings(mockZoomUserId); // Second call, should trigger refresh
      expect(mockedAxios.post).toHaveBeenCalledTimes(2); // Token refreshed
      // Check if the GET call for the second listZoomMeetings used the refreshed token
      // This requires inspecting the actual call arguments if the mock setup allows.
      // The current mock setup for axios.get might not easily allow direct inspection of headers for the *second* call if not reset.
      // However, the fact that POST was called twice is the primary indicator of refresh.
      // To verify the header, we'd need a more granular mock or capture arguments.
      // For now, we assume the new token from the second POST would be used.
      // A more robust test might involve capturing the token in getZoomAccessToken if it were directly testable
      // or ensuring the Authorization header in the second GET call is 'Bearer token_refreshed'.
      // Let's check the last call to GET (which is the second one here)
      const lastGetCall = mockedAxios.get.mock.calls[mockedAxios.get.mock.calls.length - 1];
      expect(lastGetCall[1]?.headers?.Authorization).toBe('Bearer token_refreshed');

    });

    it('should return error if Zoom auth API fails', async () => {
      mockedAxios.post.mockRejectedValueOnce(new Error('Zoom Auth Failed'));
      const result = await listZoomMeetings(mockZoomUserId);
      expect(result.ok).toBe(false);
      expect(result.error).toContain('Failed to obtain Zoom access token.');
      expect(consoleErrorSpy).toHaveBeenCalledWith('Error obtaining Zoom access token:', 'Zoom Auth Failed');
    });

    it('should return error if Zoom auth constants are missing', async () => {
      jest.spyOn(constants, 'ATOM_ZOOM_CLIENT_ID', 'get').mockReturnValue(''); // Simulate missing client ID
      const result = await listZoomMeetings(mockZoomUserId);
      expect(result.ok).toBe(false);
      expect(result.error).toContain('Failed to obtain Zoom access token.'); // The getZoomAccessToken returns null
      expect(consoleErrorSpy).toHaveBeenCalledWith('Zoom API credentials (Account ID, Client ID, Client Secret) not configured.');
    });
  });

  describe('listZoomMeetings', () => {
    const mockZoomUserId = 'user456';
    beforeEach(() => {
      // Ensure a valid token is mocked for these tests, as token logic is tested separately
      mockedAxios.post.mockResolvedValue({
        data: { access_token: 'valid_token_for_list', expires_in: 3600 }, status: 200,
      });
    });

    it('should list meetings successfully', async () => {
      const mockMeetingsData: Partial<ZoomMeeting>[] = [{ id: 'm1', topic: 'Meeting 1' }];
      mockedAxios.get.mockResolvedValueOnce({
        data: { meetings: mockMeetingsData, next_page_token: 'next_token_here' },
        status: 200,
      });

      const result = await listZoomMeetings(mockZoomUserId, { type: 'upcoming', page_size: 10 });
      expect(result.ok).toBe(true);
      expect(result.meetings).toEqual(mockMeetingsData);
      expect(result.next_page_token).toBe('next_token_here');
      expect(mockedAxios.get).toHaveBeenCalledWith(
        `${ZOOM_API_BASE_URL}/users/${mockZoomUserId}/meetings`,
        expect.objectContaining({
          headers: { 'Authorization': 'Bearer valid_token_for_list' },
          params: { type: 'upcoming', page_size: 10 },
        })
      );
    });

    it('should handle API error when listing meetings', async () => {
      const apiError = { isAxiosError: true, response: { data: { message: 'Error from Zoom API' } }, message: 'Request failed' } as AxiosError;
      mockedAxios.get.mockRejectedValueOnce(apiError);

      const result = await listZoomMeetings(mockZoomUserId);
      expect(result.ok).toBe(false);
      expect(result.error).toBe('Error from Zoom API');
      expect(consoleErrorSpy).toHaveBeenCalledWith(`Error listing Zoom meetings for userId ${mockZoomUserId}:`, 'Request failed');
    });
  });

  describe('getZoomMeetingDetails', () => {
    const mockMeetingId = 'meeting789';
     beforeEach(() => {
      mockedAxios.post.mockResolvedValue({
        data: { access_token: 'valid_token_for_details', expires_in: 3600 }, status: 200,
      });
    });

    it('should get meeting details successfully', async () => {
      const mockMeetingDetailData: Partial<ZoomMeeting> = { id: mockMeetingId, topic: 'Detailed Meeting Topic' };
      mockedAxios.get.mockResolvedValueOnce({ data: mockMeetingDetailData, status: 200 });

      const result = await getZoomMeetingDetails(mockMeetingId);
      expect(result.ok).toBe(true);
      expect(result.meeting).toEqual(mockMeetingDetailData);
      expect(mockedAxios.get).toHaveBeenCalledWith(
        `${ZOOM_API_BASE_URL}/meetings/${mockMeetingId}`,
        expect.objectContaining({
          headers: { 'Authorization': 'Bearer valid_token_for_details' },
        })
      );
    });

    it('should handle meeting not found (404 error)', async () => {
      const axiosError = {
        isAxiosError: true,
        response: { status: 404, data: { message: 'Meeting does not exist.' } },
        message: 'Request failed with status code 404',
      } as AxiosError;
      mockedAxios.get.mockRejectedValueOnce(axiosError);

      const result = await getZoomMeetingDetails('non_existent_id');
      expect(result.ok).toBe(false);
      expect(result.error).toContain('Meeting not found (ID: non_existent_id). Meeting does not exist.');
      expect(consoleErrorSpy).toHaveBeenCalledWith(`Error getting Zoom meeting details for meetingId non_existent_id:`, 'Request failed with status code 404');
    });

    it('should handle other API errors when getting details', async () => {
      const apiError = { isAxiosError: true, response: { data: { message: 'Some other API error' } }, message: 'Request failed' } as AxiosError;
      mockedAxios.get.mockRejectedValueOnce(apiError);

      const result = await getZoomMeetingDetails(mockMeetingId);
      expect(result.ok).toBe(false);
      expect(result.error).toBe('Some other API error');
    });
  });
});
