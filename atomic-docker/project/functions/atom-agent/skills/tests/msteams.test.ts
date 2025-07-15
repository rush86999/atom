import { handleListMicrosoftTeamsMeetings, handleGetMicrosoftTeamsMeetingDetails } from '../msteams';
import * as msTeamsSkills from '../msTeamsSkills';

jest.mock('../msTeamsSkills', () => ({
    listMicrosoftTeamsMeetings: jest.fn(),
    getMicrosoftTeamsMeetingDetails: jest.fn(),
}));

describe('msteams skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });

    describe('handleListMicrosoftTeamsMeetings', () => {
        it('should return a list of Microsoft Teams meetings', async () => {
            const mockResponse = {
                ok: true,
                events: [
                    {
                        subject: 'Test Teams Meeting 1',
                        id: '123',
                        start: { dateTime: new Date().toISOString() },
                        onlineMeeting: { joinUrl: 'https://example.com/join/1' },
                    },
                ],
            };
            (msTeamsSkills.listMicrosoftTeamsMeetings as jest.Mock).mockResolvedValue(mockResponse);

            const result = await handleListMicrosoftTeamsMeetings('test-user', {});

            expect(result).toContain('Your Microsoft Teams Meetings (via NLU):');
            expect(result).toContain('Test Teams Meeting 1');
        });

        it('should return a message when there are no meetings', async () => {
            (msTeamsSkills.listMicrosoftTeamsMeetings as jest.Mock).mockResolvedValue({
                ok: true,
                events: [],
            });

            const result = await handleListMicrosoftTeamsMeetings('test-user', {});

            expect(result).toBe('No Microsoft Teams meetings found matching your criteria (via NLU).');
        });

        it('should return an error message when an error occurs', async () => {
            (msTeamsSkills.listMicrosoftTeamsMeetings as jest.Mock).mockRejectedValue(new Error('Test Error'));

            const result = await handleListMicrosoftTeamsMeetings('test-user', {});

            expect(result).toBe('Sorry, an unexpected error occurred while fetching your Microsoft Teams meetings (NLU path).');
        });
    });

    describe('handleGetMicrosoftTeamsMeetingDetails', () => {
        it('should return the details of a Microsoft Teams meeting', async () => {
            const mockResponse = {
                ok: true,
                event: {
                    subject: 'Test Teams Meeting 1',
                    id: '123',
                    start: { dateTime: new Date().toISOString() },
                    end: { dateTime: new Date().toISOString() },
                    onlineMeeting: { joinUrl: 'https://example.com/join/1' },
                },
            };
            (msTeamsSkills.getMicrosoftTeamsMeetingDetails as jest.Mock).mockResolvedValue(mockResponse);

            const result = await handleGetMicrosoftTeamsMeetingDetails('test-user', { event_id: '123' });

            expect(result).toContain('Teams Meeting (via NLU): Test Teams Meeting 1');
        });

        it('should return an error message when the event ID is missing', async () => {
            const result = await handleGetMicrosoftTeamsMeetingDetails('test-user', {});

            expect(result).toBe('Microsoft Graph Event ID is required to get Teams meeting details via NLU.');
        });

        it('should return an error message when an error occurs', async () => {
            (msTeamsSkills.getMicrosoftTeamsMeetingDetails as jest.Mock).mockRejectedValue(new Error('Test Error'));

            const result = await handleGetMicrosoftTeamsMeetingDetails('test-user', { event_id: '123' });

            expect(result).toBe('Sorry, an unexpected error occurred while fetching details for Teams meeting 123 (NLU path).');
        });
    });
});
