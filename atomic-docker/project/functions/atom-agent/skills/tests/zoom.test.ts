import { handleListZoomMeetings, handleGetZoomMeetingDetails } from '../zoom';
import * as zoomSkills from '../zoomSkills';

jest.mock('../zoomSkills', () => ({
  listZoomMeetings: jest.fn(),
  getZoomMeetingDetails: jest.fn(),
}));

describe('zoom skill', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('handleListZoomMeetings', () => {
    it('should return a list of Zoom meetings', async () => {
      const mockResponse = {
        ok: true,
        meetings: [
          {
            topic: 'Test Meeting 1',
            id: '123',
            start_time: new Date().toISOString(),
            join_url: 'https://example.com/join/1',
          },
        ],
      };
      (zoomSkills.listZoomMeetings as jest.Mock).mockResolvedValue(
        mockResponse
      );

      const result = await handleListZoomMeetings('test-user', {});

      expect(result).toContain('Your Zoom Meetings (upcoming, via NLU):');
      expect(result).toContain('Test Meeting 1');
    });

    it('should return a message when there are no meetings', async () => {
      (zoomSkills.listZoomMeetings as jest.Mock).mockResolvedValue({
        ok: true,
        meetings: [],
      });

      const result = await handleListZoomMeetings('test-user', {});

      expect(result).toBe(
        'No Zoom meetings found matching your criteria (via NLU).'
      );
    });

    it('should return an error message when an error occurs', async () => {
      (zoomSkills.listZoomMeetings as jest.Mock).mockRejectedValue(
        new Error('Test Error')
      );

      const result = await handleListZoomMeetings('test-user', {});

      expect(result).toBe(
        'Sorry, an unexpected error occurred while fetching your Zoom meetings (NLU path).'
      );
    });
  });

  describe('handleGetZoomMeetingDetails', () => {
    it('should return the details of a Zoom meeting', async () => {
      const mockResponse = {
        ok: true,
        meeting: {
          topic: 'Test Meeting 1',
          id: '123',
          start_time: new Date().toISOString(),
          duration: 60,
          join_url: 'https://example.com/join/1',
          agenda: 'Test Agenda',
        },
      };
      (zoomSkills.getZoomMeetingDetails as jest.Mock).mockResolvedValue(
        mockResponse
      );

      const result = await handleGetZoomMeetingDetails('test-user', {
        meeting_id: '123',
      });

      expect(result).toContain('Zoom Meeting Details (via NLU):');
      expect(result).toContain('Test Meeting 1');
    });

    it('should return an error message when the meeting ID is missing', async () => {
      const result = await handleGetZoomMeetingDetails('test-user', {});

      expect(result).toBe(
        'Zoom Meeting ID is required to get details via NLU.'
      );
    });

    it('should return an error message when an error occurs', async () => {
      (zoomSkills.getZoomMeetingDetails as jest.Mock).mockRejectedValue(
        new Error('Test Error')
      );

      const result = await handleGetZoomMeetingDetails('test-user', {
        meeting_id: '123',
      });

      expect(result).toBe(
        'Sorry, an unexpected error occurred while fetching details for Zoom meeting 123 (NLU path).'
      );
    });
  });
});
