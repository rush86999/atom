import { requestScheduleMeeting } from '../ScheduleHelper';
import * as apiBackendHelper from '@lib/api-backend-helper';
import { ApolloClient, InMemoryCache } from '@apollo/client';

// Mock the api-backend-helper module
jest.mock('@lib/api-backend-helper', () => ({
  scheduleMeeting: jest.fn(),
}));

describe('ScheduleHelper', () => {
  describe('requestScheduleMeeting', () => {
    let mockClient: ApolloClient<any>; // eslint-disable-line @typescript-eslint/no-explicit-any

    beforeEach(() => {
      jest.clearAllMocks();
      mockClient = new ApolloClient({ cache: new InMemoryCache() }); // Mock ApolloClient
    });

    it('should call callScheduleMeetingApi with the correct payload', async () => {
      const mockUserId = 'user-123';
      const mockParticipantNames = ['Alice', 'Bob'];
      const mockDurationMinutes = 60;
      const mockPreferredDate = '2024-08-15';
      const mockPreferredStartTimeFrom = '10:00:00';
      const mockPreferredStartTimeTo = '11:00:00';
      const expectedPayload = {
        participantNames: mockParticipantNames,
        durationMinutes: mockDurationMinutes,
        preferredDate: mockPreferredDate,
        preferredStartTimeFrom: mockPreferredStartTimeFrom,
        preferredStartTimeTo: mockPreferredStartTimeTo,
      };

      (apiBackendHelper.scheduleMeeting as jest.Mock).mockResolvedValueOnce({
        success: true,
      });

      await requestScheduleMeeting(
        mockClient,
        mockUserId,
        mockParticipantNames,
        mockDurationMinutes,
        mockPreferredDate,
        mockPreferredStartTimeFrom,
        mockPreferredStartTimeTo
      );

      expect(apiBackendHelper.scheduleMeeting).toHaveBeenCalledTimes(1);
      expect(apiBackendHelper.scheduleMeeting).toHaveBeenCalledWith(
        expectedPayload
      );
    });

    it('should return the response from callScheduleMeetingApi on success', async () => {
      const mockResponse = { meetingId: 'meeting-456', status: 'PENDING' };
      (apiBackendHelper.scheduleMeeting as jest.Mock).mockResolvedValueOnce(
        mockResponse
      );

      const result = await requestScheduleMeeting(
        mockClient,
        'user-123',
        ['Alice'],
        30,
        '2024-08-16',
        '14:00:00',
        '15:00:00'
      );

      expect(result).toEqual(mockResponse);
    });

    it('should throw an error if callScheduleMeetingApi throws an error', async () => {
      const mockError = new Error('API Failure');
      (apiBackendHelper.scheduleMeeting as jest.Mock).mockRejectedValueOnce(
        mockError
      );

      await expect(
        requestScheduleMeeting(
          mockClient,
          'user-123',
          ['Bob'],
          45,
          '2024-08-17',
          '09:00:00',
          '10:00:00'
        )
      ).rejects.toThrow('API Failure');
    });
  });
});
