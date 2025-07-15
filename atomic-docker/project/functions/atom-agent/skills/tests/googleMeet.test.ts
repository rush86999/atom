import { handleListGoogleMeetEvents, handleGetGoogleMeetEventDetails } from '../googleMeet';
import * as calendarSkills from '../calendarSkills';

jest.mock('../calendarSkills', () => ({
    listUpcomingGoogleMeetEvents: jest.fn(),
    getGoogleMeetEventDetails: jest.fn(),
}));

describe('googleMeet skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });

    describe('handleListGoogleMeetEvents', () => {
        it('should return a list of Google Meet events', async () => {
            const mockResponse = {
                ok: true,
                events: [
                    {
                        summary: 'Test Meet Event 1',
                        startTime: new Date().toISOString(),
                        conferenceData: {
                            entryPoints: [
                                {
                                    entryPointType: 'video',
                                    uri: 'https://meet.google.com/123',
                                },
                            ],
                        },
                    },
                ],
            };
            (calendarSkills.listUpcomingGoogleMeetEvents as jest.Mock).mockResolvedValue(mockResponse);

            const result = await handleListGoogleMeetEvents('test-user', {});

            expect(result).toContain('Your Upcoming Google Meet Events (via NLU):');
            expect(result).toContain('Test Meet Event 1');
        });

        it('should return a message when there are no events', async () => {
            (calendarSkills.listUpcomingGoogleMeetEvents as jest.Mock).mockResolvedValue({
                ok: true,
                events: [],
            });

            const result = await handleListGoogleMeetEvents('test-user', {});

            expect(result).toBe('No upcoming Google Meet events found (via NLU).');
        });

        it('should return an error message when an error occurs', async () => {
            (calendarSkills.listUpcomingGoogleMeetEvents as jest.Mock).mockRejectedValue(new Error('Test Error'));

            const result = await handleListGoogleMeetEvents('test-user', {});

            expect(result).toBe('Sorry, an unexpected error occurred while fetching your Google Meet events (NLU path).');
        });
    });

    describe('handleGetGoogleMeetEventDetails', () => {
        it('should return the details of a Google Meet event', async () => {
            const mockResponse = {
                ok: true,
                event: {
                    summary: 'Test Meet Event 1',
                    startTime: new Date().toISOString(),
                    endTime: new Date().toISOString(),
                    conferenceData: {
                        entryPoints: [
                            {
                                entryPointType: 'video',
                                uri: 'https://meet.google.com/123',
                            },
                        ],
                    },
                },
            };
            (calendarSkills.getGoogleMeetEventDetails as jest.Mock).mockResolvedValue(mockResponse);

            const result = await handleGetGoogleMeetEventDetails('test-user', { event_id: '123' });

            expect(result).toContain('Event (via NLU): Test Meet Event 1');
        });

        it('should return an error message when the event ID is missing', async () => {
            const result = await handleGetGoogleMeetEventDetails('test-user', {});

            expect(result).toBe('Google Calendar Event ID is required to get details via NLU.');
        });

        it('should return an error message when an error occurs', async () => {
            (calendarSkills.getGoogleMeetEventDetails as jest.Mock).mockRejectedValue(new Error('Test Error'));

            const result = await handleGetGoogleMeetEventDetails('test-user', { event_id: '123' });

            expect(result).toBe('Sorry, an unexpected error occurred while fetching details for event 123 (NLU path).');
        });
    });
});
