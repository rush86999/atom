import * as msCalendarSkills from './microsoftCalendarSkills';
import { CalendarEvent, CreateEventResponse } from '../types';
import got from 'got'; // Actual 'got' for type, but will be mocked by jest.mock
import * as tokenUtils from '../_libs/token-utils';
import * as constants from '../_libs/constants';

// Mocks
jest.mock('got');
const mockedGot = got as jest.Mocked<typeof got>;

jest.mock('../_libs/token-utils', () => ({
    getAtomMicrosoftGraphTokens: jest.fn(),
    saveAtomMicrosoftGraphTokens: jest.fn(),
    deleteAtomMicrosoftGraphTokens: jest.fn(), // For refresh token failure case
}));

jest.mock('../_libs/constants', () => ({
    ATOM_MSGRAPH_CLIENT_ID: 'test_ms_client_id_skill',
    ATOM_MSGRAPH_CLIENT_SECRET: 'test_ms_client_secret_skill',
    ATOM_MSGRAPH_TENANT_ID: 'common_tenant_skill',
    MSGRAPH_OAUTH_AUTHORITY_BASE: 'https://login.microsoftonline.com/',
    MSGRAPH_API_SCOPES: ['User.Read', 'Calendars.ReadWrite', 'Mail.ReadWrite', 'Mail.Send', 'offline_access'],
    ATOM_MSGRAPH_REDIRECT_URI: 'http://localhost/ms_callback_skill',
}));

const mockedGetMsGraphTokens = tokenUtils.getAtomMicrosoftGraphTokens as jest.Mock;
const mockedSaveMsGraphTokens = tokenUtils.saveAtomMicrosoftGraphTokens as jest.Mock;
const mockedDeleteMsGraphTokens = tokenUtils.deleteAtomMicrosoftGraphTokens as jest.Mock;


describe('Microsoft Calendar Skills with Graph API Mocks', () => {
    const mockUserId = 'test-user-ms-calendar-skill';
    const initialMockTokenSet = {
        access_token: 'valid_ms_access_token',
        refresh_token: 'valid_ms_refresh_token',
        expiry_date: Date.now() + 3600000, // Valid for 1 hour
        appEmail: 'user.ms@example.com'
    };
    let consoleErrorSpy: jest.SpyInstance;
    let consoleLogSpy: jest.SpyInstance;

    beforeEach(() => {
        jest.clearAllMocks();
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
        consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {}); // For refresh logs
    });
    afterEach(() => {
        consoleErrorSpy.mockRestore();
        consoleLogSpy.mockRestore();
    });

    describe('listUpcomingEventsMicrosoft', () => {
        it('should return empty array if no tokens are found', async () => {
            mockedGetMsGraphTokens.mockResolvedValue(null);
            const events = await msCalendarSkills.listUpcomingEventsMicrosoft(mockUserId, 5);
            expect(events).toEqual([]);
            expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('No valid Microsoft Graph tokens'));
        });

        it('should fetch and map calendar events successfully', async () => {
            mockedGetMsGraphTokens.mockResolvedValue(initialMockTokenSet);
            const mockGraphResponse = {
                body: {
                    value: [
                        { id: 'ms_event1', subject: 'MS Event 1', bodyPreview: 'Desc 1', start: { dateTime: '2024-05-01T10:00:00.0000000' }, end: { dateTime: '2024-05-01T11:00:00.0000000' }, location: {displayName: 'MS Location 1'}, webLink: 'ms_link1' },
                        { id: 'ms_event2', subject: 'MS Event 2', start: { dateTime: '2024-05-02T12:00:00.0000000' }, end: { dateTime: '2024-05-02T13:00:00.0000000' } },
                    ]
                }
            };
            mockedGot.get.mockResolvedValue(mockGraphResponse as any);

            const events = await msCalendarSkills.listUpcomingEventsMicrosoft(mockUserId, 2);
            expect(mockedGot.get).toHaveBeenCalledWith(expect.stringContaining('https://graph.microsoft.com/v1.0/me/calendarview'), expect.any(Object));
            expect(events.length).toBe(2);
            expect(events[0].summary).toBe('MS Event 1');
            expect(events[0].startTime).toBe('2024-05-01T10:00:00.000Z'); // Check ISO conversion with Z
        });

        it('should attempt token refresh on 401 and retry API call', async () => {
            mockedGetMsGraphTokens.mockResolvedValue(initialMockTokenSet);
            const refreshedAccessToken = 'refreshed_ms_access_token';

            // First call to Graph API (events list) fails with 401
            mockedGot.get.mockRejectedValueOnce({ response: { statusCode: 401 } } as any);
            // Mock token refresh call
            mockedGot.post.mockResolvedValueOnce({ body: { access_token: refreshedAccessToken, expires_in: 3600, refresh_token: initialMockTokenSet.refresh_token } } as any);
            // Second call to Graph API (events list) succeeds
            mockedGot.get.mockResolvedValueOnce({ body: { value: [{ id: 'event_after_refresh', subject: 'Refreshed Event' , start: {dateTime: '2023-01-01T10:00:00'}, end: {dateTime: '2023-01-01T11:00:00'}}] } } as any);

            const events = await msCalendarSkills.listUpcomingEventsMicrosoft(mockUserId, 1);

            expect(mockedGot.post).toHaveBeenCalledWith(expect.stringContaining('/oauth2/v2.0/token'), expect.any(Object)); // Refresh call
            expect(mockedSaveMsGraphTokens).toHaveBeenCalledWith(mockUserId, expect.objectContaining({ access_token: refreshedAccessToken }), initialMockTokenSet.appEmail);
            expect(mockedGot.get).toHaveBeenCalledTimes(2); // Original call + retry
            expect(events.length).toBe(1);
            expect(events[0].summary).toBe('Refreshed Event');
        });
         it('should return empty array if refresh token fails', async () => {
            mockedGetMsGraphTokens.mockResolvedValue(initialMockTokenSet);
            mockedGot.get.mockRejectedValueOnce({ response: { statusCode: 401 } } as any); // Initial API call fails
            mockedGot.post.mockRejectedValueOnce(new Error("Refresh failed invalid_grant")); // Refresh call fails

            const events = await msCalendarSkills.listUpcomingEventsMicrosoft(mockUserId, 1);
            expect(events).toEqual([]);
            expect(mockedSaveMsGraphTokens).not.toHaveBeenCalled(); // Save should not be called if refresh fails
            expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('Failed to refresh token for userId'));
            expect(mockedDeleteMsGraphTokens).toHaveBeenCalledWith(mockUserId); // Ensure bad tokens are deleted
        });
    });

    describe('createCalendarEventMicrosoft', () => {
        const eventDetails: Partial<CalendarEvent> = { summary: 'New MS Event', startTime: '2024-06-01T10:00:00Z', endTime: '2024-06-01T11:00:00Z' };

        it('should return auth error if no tokens', async () => {
            mockedGetMsGraphTokens.mockResolvedValue(null);
            const result = await msCalendarSkills.createCalendarEventMicrosoft(mockUserId, eventDetails);
            expect(result.success).toBe(false);
            expect(result.message).toContain('Authentication required');
        });

        it('should create event successfully', async () => {
            mockedGetMsGraphTokens.mockResolvedValue(initialMockTokenSet);
            const mockCreatedGraphEvent = { id: 'ms_created_event1', webLink: 'ms_created_link1', subject: eventDetails.summary };
            mockedGot.post.mockResolvedValue({ body: mockCreatedGraphEvent } as any);

            const result = await msCalendarSkills.createCalendarEventMicrosoft(mockUserId, eventDetails);
            expect(mockedGot.post).toHaveBeenCalledWith('https://graph.microsoft.com/v1.0/me/events', expect.any(Object));
            const requestBody = (mockedGot.post.mock.calls[0][1] as any).json;
            expect(requestBody.subject).toBe(eventDetails.summary);
            expect(result.success).toBe(true);
            expect(result.eventId).toBe('ms_created_event1');
            expect(result.htmlLink).toBe('ms_created_link1');
        });

        it('should attempt token refresh on 401 for createEvent and retry', async () => {
            mockedGetMsGraphTokens.mockResolvedValue(initialMockTokenSet);
            const refreshedAccessToken = 'refreshed_ms_access_token_create';

            mockedGot.post
                .mockRejectedValueOnce({ response: { statusCode: 401 } } as any) // First create attempt fails
                .mockResolvedValueOnce({ body: { access_token: refreshedAccessToken, expires_in: 3600 } } as any) // Token refresh succeeds
                .mockResolvedValueOnce({ body: { id: 'createdAfterRefresh', webLink: 'linkAfterRefresh' } } as any); // Second create attempt succeeds

            const result = await msCalendarSkills.createCalendarEventMicrosoft(mockUserId, eventDetails);

            expect(mockedGot.post).toHaveBeenCalledTimes(3); // 1st create, refresh, 2nd create
            expect(mockedSaveMsGraphTokens).toHaveBeenCalledWith(mockUserId, expect.objectContaining({ access_token: refreshedAccessToken }), initialMockTokenSet.appEmail);
            expect(result.success).toBe(true);
            expect(result.eventId).toBe('createdAfterRefresh');
        });
    });
});
