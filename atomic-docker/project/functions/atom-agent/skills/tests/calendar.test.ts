import { handleGetCalendarEvents, handleCreateCalendarEvent } from '../calendar';
import * as calendarSkills from '../calendarSkills';

jest.mock('../calendarSkills', () => ({
    listUpcomingEvents: jest.fn(),
    createCalendarEvent: jest.fn(),
}));

describe('calendar skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });

    describe('handleGetCalendarEvents', () => {
        it('should return a list of upcoming events', async () => {
            const mockEvents = [
                {
                    summary: 'Test Event 1',
                    startTime: new Date().toISOString(),
                    endTime: new Date().toISOString(),
                },
                {
                    summary: 'Test Event 2',
                    startTime: new Date().toISOString(),
                    endTime: new Date().toISOString(),
                },
            ];
            (calendarSkills.listUpcomingEvents as jest.Mock).mockResolvedValue(mockEvents);

            const result = await handleGetCalendarEvents('test-user', {});

            expect(result).toContain('Upcoming calendar events:');
            expect(result).toContain('Test Event 1');
            expect(result).toContain('Test Event 2');
        });

        it('should return a message when there are no upcoming events', async () => {
            (calendarSkills.listUpcomingEvents as jest.Mock).mockResolvedValue([]);

            const result = await handleGetCalendarEvents('test-user', {});

            expect(result).toBe("No upcoming calendar events found matching your criteria, or I couldn't access them.");
        });

        it('should return an error message when an error occurs', async () => {
            (calendarSkills.listUpcomingEvents as jest.Mock).mockRejectedValue(new Error('Test Error'));

            const result = await handleGetCalendarEvents('test-user', {});

            expect(result).toBe("Sorry, I couldn't fetch your calendar events due to an error.");
        });
    });

    describe('handleCreateCalendarEvent', () => {
        it('should create a new calendar event', async () => {
            const mockEvent = {
                summary: 'Test Event',
                start_time: new Date().toISOString(),
                end_time: new Date().toISOString(),
            };
            (calendarSkills.createCalendarEvent as jest.Mock).mockResolvedValue({
                success: true,
                message: 'Event created successfully',
                eventId: 'test-event-id',
            });

            const result = await handleCreateCalendarEvent('test-user', mockEvent);

            expect(result).toContain('Event created: Event created successfully');
        });

        it('should return an error message when the summary is missing', async () => {
            const mockEvent = {
                start_time: new Date().toISOString(),
                end_time: new Date().toISOString(),
            };

            const result = await handleCreateCalendarEvent('test-user', mockEvent);

            expect(result).toBe('Event summary is required to create an event via NLU.');
        });

        it('should return an error message when the start time is missing', async () => {
            const mockEvent = {
                summary: 'Test Event',
                end_time: new Date().toISOString(),
            };

            const result = await handleCreateCalendarEvent('test-user', mockEvent);

            expect(result).toBe('Event start time is required to create an event via NLU.');
        });

        it('should return an error message when the end time and duration are missing', async () => {
            const mockEvent = {
                summary: 'Test Event',
                start_time: new Date().toISOString(),
            };

            const result = await handleCreateCalendarEvent('test-user', mockEvent);

            expect(result).toBe('Event end time or duration is required to create an event via NLU.');
        });

        it('should return an error message when an error occurs', async () => {
            const mockEvent = {
                summary: 'Test Event',
                start_time: new Date().toISOString(),
                end_time: new Date().toISOString(),
            };
            (calendarSkills.createCalendarEvent as jest.Mock).mockRejectedValue(new Error('Test Error'));

            const result = await handleCreateCalendarEvent('test-user', mockEvent);

            expect(result).toBe("Sorry, I couldn't create the calendar event due to an error.");
        });
    });
});
