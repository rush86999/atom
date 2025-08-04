// Test suite for sync-logic.ts
import * as syncLogic from './sync-logic'; // Import all exports for spyOn
const { initialGoogleCalendarSync2, performCalendarSync } = syncLogic;
import { getGoogleAPIToken, updateGoogleCalendarTokensInDb, addlocalItemsToEvent2VectorObjects, deleteAttendees, deleteReminders, deleteEvents, deleteConferences, insertRemindersGivenEventResource, upsertAttendees2, upsertConference2, upsertEvents2, addToQueueForVectorSearch, 
// Added for performCalendarSync
getGoogleIntegration, getGoogleCalendarInDb, getGoogleColor, updateGoogleIntegration, getCalendarWebhookByCalendarId, stopCalendarWatch, deleteCalendarWebhookById, requestCalendarWatch, insertCalendarWebhook, resetGoogleSyncForCalendar, // Added for 410 GONE error handling
 } from './api-helper';
import { google } from 'googleapis';
// Mock the entire api-helper module
jest.mock('./api-helper', () => ({
    getGoogleAPIToken: jest.fn(),
    updateGoogleCalendarTokensInDb: jest.fn(),
    addlocalItemsToEvent2VectorObjects: jest.fn(),
    deleteAttendees: jest.fn(),
    deleteReminders: jest.fn(),
    deleteEvents: jest.fn(),
    deleteConferences: jest.fn(),
    insertRemindersGivenEventResource: jest.fn(),
    upsertAttendees2: jest.fn(),
    upsertConference2: jest.fn(),
    upsertEvents2: jest.fn(),
    addToQueueForVectorSearch: jest.fn(),
    getGoogleCalendarInDb: jest.fn(),
    getGoogleColor: jest.fn(),
    getGoogleIntegration: jest.fn(),
    requestCalendarWatch: jest.fn(),
    updateGoogleIntegration: jest.fn(),
    insertCalendarWebhook: jest.fn(),
    getCalendarWebhookByCalendarId: jest.fn(),
    stopCalendarWatch: jest.fn(),
    deleteCalendarWebhookById: jest.fn(),
    resetGoogleSyncForCalendar: jest.fn(), // Added for 410 GONE error handling
}));
// Mock googleapis
jest.mock('googleapis', () => {
    const mockEventsList = jest.fn();
    return {
        google: {
            calendar: jest.fn(() => ({
                events: {
                    list: mockEventsList,
                },
            })),
        },
        // Expose mockEventsList for easier access in tests
        __mockEventsList: mockEventsList,
    };
});
// Helper to access the mock for events.list
const mockGoogleEventsList = google.__mockEventsList;
describe('initialGoogleCalendarSync2', () => {
    // Spy on console.log and suppress output during tests
    let consoleLogSpy;
    beforeEach(() => {
        jest.clearAllMocks();
        consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => { });
    });
    afterEach(() => {
        consoleLogSpy.mockRestore();
    });
    const dummyCalendarId = 'test-calendar-id';
    const dummyUserId = 'test-user-id';
    const dummyClientType = 'web';
    const dummyColorItem = {
        calendar: {
            ETag: 'test',
            backgroundColor: '#FFF',
            foregroundColor: '#000',
        },
        event: { ETag: 'test', backgroundColor: '#CCC', foregroundColor: '#111' },
    };
    const dummyToken = 'dummy-google-api-token';
    const dummySyncToken = 'dummy-sync-token';
    // Test Case 1: Successful initial sync with a single page of new (non-deleted) events.
    it('should successfully sync with a single page of new events', async () => {
        getGoogleAPIToken.mockResolvedValue(dummyToken);
        mockGoogleEventsList.mockResolvedValueOnce({
            data: {
                items: [
                    { id: 'event1', summary: 'Event 1', status: 'confirmed' },
                    { id: 'event2', summary: 'Event 2', status: 'tentative' },
                ],
                nextPageToken: null,
                nextSyncToken: dummySyncToken,
            },
        });
        deleteEvents.mockResolvedValue([]); // Assume no events were actually deleted from DB
        const result = await initialGoogleCalendarSync2(dummyCalendarId, dummyUserId, dummyClientType, dummyColorItem);
        expect(result).toBe(true);
        expect(getGoogleAPIToken).toHaveBeenCalledWith(dummyUserId, 'google_calendar', dummyClientType);
        expect(google.calendar).toHaveBeenCalledWith({
            version: 'v3',
            headers: { Authorization: `Bearer ${dummyToken}` },
        });
        expect(mockGoogleEventsList).toHaveBeenCalledWith({
            calendarId: dummyCalendarId,
            showDeleted: true,
            singleEvents: true,
        });
        expect(updateGoogleCalendarTokensInDb).toHaveBeenCalledWith(dummyCalendarId, dummySyncToken, null);
        expect(addlocalItemsToEvent2VectorObjects).toHaveBeenCalled();
        expect(upsertEvents2).toHaveBeenCalledWith(expect.arrayContaining([
            expect.objectContaining({ id: 'event1' }),
            expect.objectContaining({ id: 'event2' }),
        ]), dummyUserId, dummyCalendarId, dummyColorItem);
        expect(upsertAttendees2).toHaveBeenCalled();
        expect(upsertConference2).toHaveBeenCalled();
        expect(insertRemindersGivenEventResource).toHaveBeenCalled();
        expect(deleteEvents).not.toHaveBeenCalledWith(expect.arrayContaining([
            expect.objectContaining({ status: 'cancelled' }),
        ]), dummyCalendarId);
        expect(deleteAttendees).not.toHaveBeenCalled();
        expect(deleteReminders).toHaveBeenCalled(); // deleteReminders is called for eventsToUpsert as well
        expect(deleteConferences).not.toHaveBeenCalled();
        expect(addToQueueForVectorSearch).toHaveBeenCalled();
    });
    // Test Case 2: Successful initial sync with some deleted events on the first page.
    it('should successfully sync with deleted events on the first page', async () => {
        getGoogleAPIToken.mockResolvedValue(dummyToken);
        const mockItems = [
            { id: 'event1', summary: 'Active Event', status: 'confirmed' },
            { id: 'event2', summary: 'Cancelled Event', status: 'cancelled' },
            { id: 'event3', summary: 'Another Active Event', status: 'tentative' },
        ];
        mockGoogleEventsList.mockResolvedValueOnce({
            data: {
                items: mockItems,
                nextPageToken: null,
                nextSyncToken: dummySyncToken,
            },
        });
        // Mock that deleteEvents returns the events it "deleted"
        deleteEvents.mockImplementation(async (eventsToDelete, _calendarId) => {
            return eventsToDelete.map((e) => e.id);
        });
        const result = await initialGoogleCalendarSync2(dummyCalendarId, dummyUserId, dummyClientType, dummyColorItem);
        expect(result).toBe(true);
        expect(updateGoogleCalendarTokensInDb).toHaveBeenCalledWith(dummyCalendarId, dummySyncToken, null);
        expect(addlocalItemsToEvent2VectorObjects).toHaveBeenCalled();
        // Check upsert for non-cancelled events
        expect(upsertEvents2).toHaveBeenCalledWith(expect.arrayContaining([
            expect.objectContaining({ id: 'event1', status: 'confirmed' }),
            expect.objectContaining({ id: 'event3', status: 'tentative' }),
        ]), dummyUserId, dummyCalendarId, dummyColorItem);
        expect(upsertEvents2).not.toHaveBeenCalledWith(expect.arrayContaining([
            expect.objectContaining({ id: 'event2', status: 'cancelled' }),
        ]), expect.anything(), expect.anything(), expect.anything());
        expect(upsertAttendees2).toHaveBeenCalled();
        expect(upsertConference2).toHaveBeenCalled();
        expect(insertRemindersGivenEventResource).toHaveBeenCalled();
        // Check delete for cancelled events
        expect(deleteEvents).toHaveBeenCalledWith(expect.arrayContaining([
            expect.objectContaining({ id: 'event2', status: 'cancelled' }),
        ]), dummyCalendarId);
        expect(deleteAttendees).toHaveBeenCalledWith(expect.arrayContaining([expect.objectContaining({ id: 'event2' })]), dummyCalendarId);
        // deleteReminders is called for both deleted and upserted events
        expect(deleteReminders).toHaveBeenCalledWith(expect.arrayContaining([expect.objectContaining({ id: 'event2' })]), dummyUserId, dummyCalendarId);
        expect(deleteConferences).toHaveBeenCalledWith(expect.arrayContaining(['event2'])); // Since deleteEvents returns IDs
        expect(addToQueueForVectorSearch).toHaveBeenCalled();
    });
    // Test Case 3: getGoogleAPIToken throws an error.
    it('should return false if getGoogleAPIToken throws an error', async () => {
        const errorMessage = 'Failed to get API token';
        getGoogleAPIToken.mockRejectedValue(new Error(errorMessage));
        const result = await initialGoogleCalendarSync2(dummyCalendarId, dummyUserId, dummyClientType, dummyColorItem);
        expect(result).toBe(false);
        expect(consoleLogSpy).toHaveBeenCalledWith(expect.any(Error), ' unable to initial google sync');
        expect(mockGoogleEventsList).not.toHaveBeenCalled();
    });
    // Test Case 4: google.calendar().events.list throws a non-410 error on the first call.
    it('should return false if events.list throws a non-410 error', async () => {
        const errorToThrow = { code: 500, message: 'Internal Server Error' };
        getGoogleAPIToken.mockResolvedValue(dummyToken);
        mockGoogleEventsList.mockRejectedValueOnce(errorToThrow);
        const result = await initialGoogleCalendarSync2(dummyCalendarId, dummyUserId, dummyClientType, dummyColorItem);
        expect(result).toBe(false);
        expect(consoleLogSpy).toHaveBeenCalledWith(errorToThrow, ' unable to initial google sync');
        expect(updateGoogleCalendarTokensInDb).not.toHaveBeenCalled();
        expect(addToQueueForVectorSearch).not.toHaveBeenCalled();
        expect(resetGoogleSyncForCalendar).not.toHaveBeenCalled();
    });
    // New Test Case for 410 GONE error
    it('should attempt full resync and return true if events.list throws a 410 GONE error', async () => {
        const error410 = { code: 410, message: 'Gone' };
        getGoogleAPIToken.mockResolvedValue(dummyToken);
        // This mock setup implies that the first call to events.list (initial sync) triggers the 410
        mockGoogleEventsList.mockRejectedValueOnce(error410);
        resetGoogleSyncForCalendar.mockResolvedValue(true); // Successful resync
        const result = await initialGoogleCalendarSync2(dummyCalendarId, dummyUserId, dummyClientType, dummyColorItem);
        expect(result).toBe(true);
        expect(consoleLogSpy).toHaveBeenCalledWith(`Google API returned 410 (GONE) for calendar ${dummyCalendarId}. Attempting full resync.`);
        expect(resetGoogleSyncForCalendar).toHaveBeenCalledWith(dummyCalendarId, dummyUserId, dummyClientType, dummyColorItem);
        // Ensure other operations that would occur before the error are not unexpectedly called again by this path
        expect(updateGoogleCalendarTokensInDb).not.toHaveBeenCalled();
        expect(addToQueueForVectorSearch).not.toHaveBeenCalled();
    });
    // TODO: Add more tests:
    // - Pagination: events.list is called multiple times
    // - No events to upsert initially, but found in paginated results
    // - No events at all (empty items array)
    // - Specific error handling if individual DB operations fail (though the current function seems to catch all with a generic message)
});
describe('performCalendarSync', () => {
    let consoleLogSpy;
    let initialGoogleCalendarSync2Spy;
    beforeEach(() => {
        jest.clearAllMocks();
        consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => { });
        // Spy on initialGoogleCalendarSync2 as it's in the same module
        initialGoogleCalendarSync2Spy = jest.spyOn(syncLogic, 'initialGoogleCalendarSync2');
    });
    afterEach(() => {
        consoleLogSpy.mockRestore();
        initialGoogleCalendarSync2Spy.mockRestore();
    });
    const defaultParams = {
        calendarIntegrationId: 'cal-int-id',
        calendarId: 'cal-id',
        userId: 'user-id',
        timezone: 'America/New_York',
    };
    const mockGoogleIntegrationData = {
        id: 'gi-id',
        clientType: 'web',
    };
    const mockCalendarInDbData = {
        id: 'db-cal-id',
        userId: defaultParams.userId,
    };
    const mockGoogleColorData = { event: {}, calendar: {} }; // Dummy color data
    const mockWebhookData = { id: 'webhook-id', resourceId: 'resource-id' };
    // Test Case 1: Successful sync and new webhook creation.
    it('should successfully sync and create a new webhook if none exists', async () => {
        getGoogleIntegration.mockResolvedValue(mockGoogleIntegrationData);
        getGoogleCalendarInDb.mockResolvedValue(mockCalendarInDbData);
        getGoogleAPIToken.mockResolvedValue('dummy-api-token');
        getGoogleColor.mockResolvedValue(mockGoogleColorData);
        initialGoogleCalendarSync2Spy.mockResolvedValue(true);
        getCalendarWebhookByCalendarId.mockResolvedValue(null); // No existing webhook
        requestCalendarWatch.mockResolvedValue({
            resourceId: 'new-resource-id',
            resourceUri: 'uri',
        });
        insertCalendarWebhook.mockResolvedValue({});
        const result = await performCalendarSync(defaultParams);
        expect(result).toEqual({
            success: true,
            message: 'successfully taken care of googleCalendarySync!',
            status: 200,
        });
        expect(initialGoogleCalendarSync2Spy).toHaveBeenCalledWith(defaultParams.calendarId, defaultParams.userId, mockGoogleIntegrationData.clientType, mockGoogleColorData);
        expect(stopCalendarWatch).not.toHaveBeenCalled();
        expect(deleteCalendarWebhookById).not.toHaveBeenCalled();
        expect(requestCalendarWatch).toHaveBeenCalled();
        expect(insertCalendarWebhook).toHaveBeenCalled();
    });
    // Test Case 2: Successful sync and existing webhook is replaced.
    it('should successfully sync and replace an existing webhook', async () => {
        getGoogleIntegration.mockResolvedValue(mockGoogleIntegrationData);
        getGoogleCalendarInDb.mockResolvedValue(mockCalendarInDbData);
        getGoogleAPIToken.mockResolvedValue('dummy-api-token');
        getGoogleColor.mockResolvedValue(mockGoogleColorData);
        initialGoogleCalendarSync2Spy.mockResolvedValue(true);
        getCalendarWebhookByCalendarId.mockResolvedValue(mockWebhookData); // Existing webhook
        stopCalendarWatch.mockResolvedValue({});
        deleteCalendarWebhookById.mockResolvedValue({});
        requestCalendarWatch.mockResolvedValue({
            resourceId: 'new-resource-id',
            resourceUri: 'uri',
        });
        insertCalendarWebhook.mockResolvedValue({});
        const result = await performCalendarSync(defaultParams);
        expect(result).toEqual({
            success: true,
            message: 'successfully taken care of googleCalendarySync!',
            status: 200,
        });
        expect(stopCalendarWatch).toHaveBeenCalledWith(mockWebhookData.id, mockWebhookData.resourceId);
        expect(deleteCalendarWebhookById).toHaveBeenCalledWith(mockWebhookData.id);
        expect(requestCalendarWatch).toHaveBeenCalled();
        expect(insertCalendarWebhook).toHaveBeenCalled();
    });
    // Test Case 3: initialGoogleCalendarSync2 returns false (sync disabled).
    it('should handle sync being disabled by initialGoogleCalendarSync2', async () => {
        getGoogleIntegration.mockResolvedValue(mockGoogleIntegrationData);
        getGoogleCalendarInDb.mockResolvedValue(mockCalendarInDbData);
        getGoogleAPIToken.mockResolvedValue('dummy-api-token');
        getGoogleColor.mockResolvedValue(mockGoogleColorData);
        initialGoogleCalendarSync2Spy.mockResolvedValue(false); // Sync disabled
        updateGoogleIntegration.mockResolvedValue({});
        const result = await performCalendarSync(defaultParams);
        expect(result).toEqual({
            success: true,
            message: 'sync is disabled for googleCalendarSync',
            status: 200,
            syncDisabled: true,
        });
        expect(updateGoogleIntegration).toHaveBeenCalledWith(defaultParams.calendarIntegrationId, false);
        expect(requestCalendarWatch).not.toHaveBeenCalled();
    });
    // Test Case 4: getGoogleIntegration returns no clientType.
    it('should return error if clientType is not available', async () => {
        getGoogleIntegration.mockResolvedValue({ id: 'gi-id' }); // No clientType
        getGoogleCalendarInDb.mockResolvedValue(mockCalendarInDbData); // Needs to be mocked to pass this stage
        const result = await performCalendarSync(defaultParams);
        expect(result).toEqual({
            success: false,
            message: 'clientType is not available',
            status: 400,
        });
    });
    // Test Case 5: getGoogleCalendarInDb returns no id.
    it('should return error if calendar is not found in DB', async () => {
        getGoogleIntegration.mockResolvedValue(mockGoogleIntegrationData);
        getGoogleCalendarInDb.mockResolvedValue(null); // Calendar not in DB
        const result = await performCalendarSync(defaultParams);
        // The message includes the id which is undefined in this case, so it becomes 'undefined -id, calendar was deleted'
        expect(result.message).toEqual('undefined -id, calendar was deleted');
        expect(result.status).toEqual(400);
        expect(result.success).toBe(false);
    });
    // Test Case 6: requestCalendarWatch throws an error.
    it('should handle errors from requestCalendarWatch', async () => {
        getGoogleIntegration.mockResolvedValue(mockGoogleIntegrationData);
        getGoogleCalendarInDb.mockResolvedValue(mockCalendarInDbData);
        getGoogleAPIToken.mockResolvedValue('dummy-api-token');
        getGoogleColor.mockResolvedValue(mockGoogleColorData);
        initialGoogleCalendarSync2Spy.mockResolvedValue(true);
        getCalendarWebhookByCalendarId.mockResolvedValue(null);
        const watchError = new Error('Failed to watch calendar');
        requestCalendarWatch.mockRejectedValue(watchError);
        const result = await performCalendarSync(defaultParams);
        expect(result).toEqual({
            success: false,
            message: 'Error managing calendar webhook: Failed to watch calendar',
            status: 500,
        });
        expect(consoleLogSpy).toHaveBeenCalledWith(watchError, 'Error managing calendar webhook');
    });
    // Test Case 7 (New): insertCalendarWebhook throws an error
    it('should handle errors from insertCalendarWebhook', async () => {
        getGoogleIntegration.mockResolvedValue(mockGoogleIntegrationData);
        getGoogleCalendarInDb.mockResolvedValue(mockCalendarInDbData);
        getGoogleAPIToken.mockResolvedValue('dummy-api-token');
        getGoogleColor.mockResolvedValue(mockGoogleColorData);
        initialGoogleCalendarSync2Spy.mockResolvedValue(true);
        getCalendarWebhookByCalendarId.mockResolvedValue(null); // No existing webhook
        requestCalendarWatch.mockResolvedValue({
            resourceId: 'new-resource-id',
            resourceUri: 'uri',
        }); // requestCalendarWatch succeeds
        const insertError = new Error('Failed to insert webhook');
        insertCalendarWebhook.mockRejectedValue(insertError); // insertCalendarWebhook fails
        const result = await performCalendarSync(defaultParams);
        expect(result).toEqual({
            success: false,
            message: 'Error managing calendar webhook: Failed to insert webhook',
            status: 500,
        });
        expect(consoleLogSpy).toHaveBeenCalledWith(insertError, 'Error managing calendar webhook');
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic3luYy1sb2dpYy50ZXN0LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsic3luYy1sb2dpYy50ZXN0LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLCtCQUErQjtBQUMvQixPQUFPLEtBQUssU0FBUyxNQUFNLGNBQWMsQ0FBQyxDQUFDLCtCQUErQjtBQUMxRSxNQUFNLEVBQUUsMEJBQTBCLEVBQUUsbUJBQW1CLEVBQUUsR0FBRyxTQUFTLENBQUM7QUFFdEUsT0FBTyxFQUNMLGlCQUFpQixFQUNqQiw4QkFBOEIsRUFDOUIsa0NBQWtDLEVBQ2xDLGVBQWUsRUFDZixlQUFlLEVBQ2YsWUFBWSxFQUNaLGlCQUFpQixFQUNqQixpQ0FBaUMsRUFDakMsZ0JBQWdCLEVBQ2hCLGlCQUFpQixFQUNqQixhQUFhLEVBQ2IseUJBQXlCO0FBQ3pCLGdDQUFnQztBQUNoQyxvQkFBb0IsRUFDcEIscUJBQXFCLEVBQ3JCLGNBQWMsRUFDZCx1QkFBdUIsRUFDdkIsOEJBQThCLEVBQzlCLGlCQUFpQixFQUNqQix5QkFBeUIsRUFDekIsb0JBQW9CLEVBQ3BCLHFCQUFxQixFQUNyQiwwQkFBMEIsRUFBRSxvQ0FBb0M7RUFDakUsTUFBTSxjQUFjLENBQUM7QUFDdEIsT0FBTyxFQUFFLE1BQU0sRUFBRSxNQUFNLFlBQVksQ0FBQztBQUVwQyxvQ0FBb0M7QUFDcEMsSUFBSSxDQUFDLElBQUksQ0FBQyxjQUFjLEVBQUUsR0FBRyxFQUFFLENBQUMsQ0FBQztJQUMvQixpQkFBaUIsRUFBRSxJQUFJLENBQUMsRUFBRSxFQUFFO0lBQzVCLDhCQUE4QixFQUFFLElBQUksQ0FBQyxFQUFFLEVBQUU7SUFDekMsa0NBQWtDLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtJQUM3QyxlQUFlLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtJQUMxQixlQUFlLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtJQUMxQixZQUFZLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtJQUN2QixpQkFBaUIs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bUIsQ0FBQyxhQUFhLENBQUMsQ0FBQztRQUV4RCxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUMsT0FBTyxDQUFDO1lBQ3JCLE9BQU8sRUFBRSxLQUFLO1lBQ2QsT0FBTyxFQUFFLDJEQUEyRDtZQUNwRSxNQUFNLEVBQUUsR0FBRztTQUNaLENBQUMsQ0FBQztRQUNILE1BQU0sQ0FBQyxhQUFhLENBQUMsQ0FBQyxvQkFBb0IsQ0FDeEMsV0FBVyxFQUNYLGlDQUFpQyxDQUNsQyxDQUFDO0lBQ0osQ0FBQyxDQUFDLENBQUM7QUFDTCxDQUFDLENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbIi8vIFRlc3Qgc3VpdGUgZm9yIHN5bmMtbG9naWMudHNcbmltcG9ydCAqIGFzIHN5bmNMb2dpYyBmcm9tICcuL3N5bmMtbG9naWMnOyAvLyBJbXBvcnQgYWxsIGV4cG9ydHMgZm9yIHNweU9uXG5jb25zdCB7IGluaXRpYWxHb29nbGVDYWxlbmRhclN5bmMyLCBwZXJmb3JtQ2FsZW5kYXJTeW5jIH0gPSBzeW5jTG9naWM7XG5cbmltcG9ydCB7XG4gIGdldEdvb2dsZUFQSVRva2VuLFxuICB1cGRhdGVHb29nbGVDYWxlbmRhclRva2Vuc0luRGIsXG4gIGFkZGxvY2FsSXRlbXNUb0V2ZW50MlZlY3Rvck9iamVjdHMsXG4gIGRlbGV0ZUF0dGVuZGVlcyxcbiAgZGVsZXRlUmVtaW5kZXJzLFxuICBkZWxldGVFdmVudHMsXG4gIGRlbGV0ZUNvbmZlcmVuY2VzLFxuICBpbnNlcnRSZW1pbmRlcnNHaXZlbkV2ZW50UmVzb3VyY2UsXG4gIHVwc2VydEF0dGVuZGVlczIsXG4gIHVwc2VydENvbmZlcmVuY2UyLFxuICB1cHNlcnRFdmVudHMyLFxuICBhZGRUb1F1ZXVlRm9yVmVjdG9yU2VhcmNoLFxuICAvLyBBZGRlZCBmb3IgcGVyZm9ybUNhbGVuZGFyU3luY1xuICBnZXRHb29nbGVJbnRlZ3JhdGlvbixcbiAgZ2V0R29vZ2xlQ2FsZW5kYXJJbkRiLFxuICBnZXRHb29nbGVDb2xvcixcbiAgdXBkYXRlR29vZ2xlSW50ZWdyYXRpb24sXG4gIGdldENhbGVuZGFyV2ViaG9va0J5Q2FsZW5kYXJJZCxcbiAgc3RvcENhbGVuZGFyV2F0Y2gsXG4gIGRlbGV0ZUNhbGVuZGFyV2ViaG9va0J5SWQsXG4gIHJlcXVlc3RDYWxlbmRhcldhdGNoLFxuICBpbnNlcnRDYWxlbmRhcldlYmhvb2ssXG4gIHJlc2V0R29vZ2xlU3luY0ZvckNhbGVuZGFyLCAvLyBBZGRlZCBmb3IgNDEwIEdPTkUgZXJyb3IgaGFuZGxpbmdcbn0gZnJvbSAnLi9hcGktaGVscGVyJztcbmltcG9ydCB7IGdvb2dsZSB9IGZyb20gJ2dvb2dsZWFwaXMnO1xuXG4vLyBNb2NrIHRoZSBlbnRpcmUgYXBpLWhlbHBlciBtb2R1bGVcbmplc3QubW9jaygnLi9hcGktaGVscGVyJywgKCkgPT4gKHtcbiAgZ2V0R29vZ2xlQVBJVG9rZW46IGplc3QuZm4oKSxcbiAgdXBkYXRlR29vZ2xlQ2FsZW5kYXJUb2tlbnNJbkRiOiBqZXN0LmZuKCksXG4gIGFkZGxvY2FsSXRlbXNUb0V2ZW50MlZlY3Rvck9iamVjdHM6IGplc3QuZm4oKSxcbiAgZGVsZXRlQXR0ZW5kZWVzOiBqZXN0LmZuKCksXG4gIGRlbGV0ZVJlbWluZGVyczogamVzdC5mbigpLFxuICBkZWxldGVFdmVudHM6IGplc3QuZm4oKSxcbiAgZGVsZXRlQ29uZmVyZW5jZXM6IGplc3QuZm4oKSxcbiAgaW5zZXJ0UmVtaW5kZXJzR2l2ZW5FdmVudFJlc291cmNlOiBqZXN0LmZuKCksXG4gIHVwc2VydEF0dGVuZGVlczI6IGplc3QuZm4oKSxcbiAgdXBzZXJ0Q29uZmVyZW5jZTI6IGplc3QuZm4oKSxcbiAgdXBzZXJ0RXZlbnRzMjogamVzdC5mbigpLFxuICBhZGRUb1F1ZXVlRm9yVmVjdG9yU2VhcmNoOiBqZXN0LmZuKCksXG4gIGdldEdvb2dsZUNhbGVuZGFySW5EYjogamVzdC5mbigpLFxuICBnZXRHb29nbGVDb2xvcjogamVzdC5mbigpLFxuICBnZXRHb29nbGVJbnRlZ3JhdGlvbjogamVzdC5mbigpLFxuICByZXF1ZXN0Q2FsZW5kYXJXYXRjaDogamVzdC5mbigpLFxuICB1cGRhdGVHb29nbGVJbnRlZ3JhdGlvbjogamVzdC5mbigpLFxuICBpbnNlcnRDYWxlbmRhcldlYmhvb2s6IGplc3QuZm4oKSxcbiAgZ2V0Q2FsZW5kYXJXZWJob29rQnlDYWxlbmRhcklkOiBqZXN0LmZuKCksXG4gIHN0b3BDYWxlbmRhcldhdGNoOiBqZXN0LmZuKCksXG4gIGRlbGV0ZUNhbGVuZGFyV2ViaG9va0J5SWQ6IGplc3QuZm4oKSxcbiAgcmVzZXRHb29nbGVTeW5jRm9yQ2FsZW5kYXI6IGplc3QuZm4oKSwgLy8gQWRkZWQgZm9yIDQxMCBHT05FIGVycm9yIGhhbmRsaW5nXG59KSk7XG5cbi8vIE1vY2sgZ29vZ2xlYXBpc1xuamVzdC5tb2NrKCdnb29nbGVhcGlzJywgKCkgPT4ge1xuICBjb25zdCBtb2NrRXZlbnRzTGlzdCA9IGplc3QuZm4oKTtcbiAgcmV0dXJuIHtcbiAgICBnb29nbGU6IHtcbiAgICAgIGNhbGVuZGFyOiBqZXN0LmZuKCgpID0+ICh7XG4gICAgICAgIGV2ZW50czoge1xuICAgICAgICAgIGxpc3Q6IG1vY2tFdmVudHNMaXN0LFxuICAgICAgICB9LFxuICAgICAgfSkpLFxuICAgIH0sXG4gICAgLy8gRXhwb3NlIG1vY2tFdmVudHNMaXN0IGZvciBlYXNpZXIgYWNjZXNzIGluIHRlc3RzXG4gICAgX19tb2NrRXZlbnRzTGlzdDogbW9ja0V2ZW50c0xpc3QsXG4gIH07XG59KTtcblxuLy8gSGVscGVyIHRvIGFjY2VzcyB0aGUgbW9jayBmb3IgZXZlbnRzLmxpc3RcbmNvbnN0IG1vY2tHb29nbGVFdmVudHNMaXN0ID0gZ29vZ2xlLl9fbW9ja0V2ZW50c0xpc3Q7XG5cbmRlc2NyaWJlKCdpbml0aWFsR29vZ2xlQ2FsZW5kYXJTeW5jMicsICgpID0+IHtcbiAgLy8gU3B5IG9uIGNvbnNvbGUubG9nIGFuZCBzdXBwcmVzcyBvdXRwdXQgZHVyaW5nIHRlc3RzXG4gIGxldCBjb25zb2xlTG9nU3B5OiBqZXN0LlNweUluc3RhbmNlO1xuXG4gIGJlZm9yZUVhY2goKCkgPT4ge1xuICAgIGplc3QuY2xlYXJBbGxNb2NrcygpO1xuICAgIGNvbnNvbGVMb2dTcHkgPSBqZXN0LnNweU9uKGNvbnNvbGUsICdsb2cnKS5tb2NrSW1wbGVtZW50YXRpb24oKCkgPT4ge30pO1xuICB9KTtcblxuICBhZnRlckVhY2goKCkgPT4ge1xuICAgIGNvbnNvbGVMb2dTcHkubW9ja1Jlc3RvcmUoKTtcbiAgfSk7XG5cbiAgY29uc3QgZHVtbXlDYWxlbmRhcklkID0gJ3Rlc3QtY2FsZW5kYXItaWQnO1xuICBjb25zdCBkdW1teVVzZXJJZCA9ICd0ZXN0LXVzZXItaWQnO1xuICBjb25zdCBkdW1teUNsaWVudFR5cGUgPSAnd2ViJztcbiAgY29uc3QgZHVtbXlDb2xvckl0ZW0gPSB7XG4gICAgY2FsZW5kYXI6IHtcbiAgICAgIEVUYWc6ICd0ZXN0JyxcbiAgICAgIGJhY2tncm91bmRDb2xvcjogJyNGRkYnLFxuICAgICAgZm9yZWdyb3VuZENvbG9yOiAnIzAwMCcsXG4gICAgfSxcbiAgICBldmVudDogeyBFVGFnOiAndGVzdCcsIGJhY2tncm91bmRDb2xvcjogJyNDQ0MnLCBmb3JlZ3JvdW5kQ29sb3I6ICcjMTExJyB9LFxuICB9O1xuICBjb25zdCBkdW1teVRva2VuID0gJ2R1bW15LWdvb2dsZS1hcGktdG9rZW4nO1xuICBjb25zdCBkdW1teVN5bmNUb2tlbiA9ICdkdW1teS1zeW5jLXRva2VuJztcblxuICAvLyBUZXN0IENhc2UgMTogU3VjY2Vzc2Z1bCBpbml0aWFsIHN5bmMgd2l0aCBhIHNpbmdsZSBwYWdlIG9mIG5ldyAobm9uLWRlbGV0ZWQpIGV2ZW50cy5cbiAgaXQoJ3Nob3VsZCBzdWNjZXNzZnVsbHkgc3luYyB3aXRoIGEgc2luZ2xlIHBhZ2Ugb2YgbmV3IGV2ZW50cycsIGFzeW5jICgpID0+IHtcbiAgICAoZ2V0R29vZ2xlQVBJVG9rZW4gYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShkdW1teVRva2VuKTtcbiAgICBtb2NrR29vZ2xlRXZlbnRzTGlzdC5tb2NrUmVzb2x2ZWRWYWx1ZU9uY2Uoe1xuICAgICAgZGF0YToge1xuICAgICAgICBpdGVtczogW1xuICAgICAgICAgIHsgaWQ6ICdldmVudDEnLCBzdW1tYXJ5OiAnRXZlbnQgMScsIHN0YXR1czogJ2NvbmZpcm1lZCcgfSxcbiAgICAgICAgICB7IGlkOiAnZXZlbnQyJywgc3VtbWFyeTogJ0V2ZW50IDInLCBzdGF0dXM6ICd0ZW50YXRpdmUnIH0sXG4gICAgICAgIF0sXG4gICAgICAgIG5leHRQYWdlVG9rZW46IG51bGwsXG4gICAgICAgIG5leHRTeW5jVG9rZW46IGR1bW15U3luY1Rva2VuLFxuICAgICAgfSxcbiAgICB9KTtcbiAgICAoZGVsZXRlRXZlbnRzIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoW10pOyAvLyBBc3N1bWUgbm8gZXZlbnRzIHdlcmUgYWN0dWFsbHkgZGVsZXRlZCBmcm9tIERCXG5cbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBpbml0aWFsR29vZ2xlQ2FsZW5kYXJTeW5jMihcbiAgICAgIGR1bW15Q2FsZW5kYXJJZCxcbiAgICAgIGR1bW15VXNlcklkLFxuICAgICAgZHVtbXlDbGllbnRUeXBlLFxuICAgICAgZHVtbXlDb2xvckl0ZW1cbiAgICApO1xuXG4gICAgZXhwZWN0KHJlc3VsdCkudG9CZSh0cnVlKTtcbiAgICBleHBlY3QoZ2V0R29vZ2xlQVBJVG9rZW4pLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgZHVtbXlVc2VySWQsXG4gICAgICAnZ29vZ2xlX2NhbGVuZGFyJyxcbiAgICAgIGR1bW15Q2xpZW50VHlwZVxuICAgICk7XG4gICAgZXhwZWN0KGdvb2dsZS5jYWxlbmRhcikudG9IYXZlQmVlbkNhbGxlZFdpdGgoe1xuICAgICAgdmVyc2lvbjogJ3YzJyxcbiAgICAgIGhlYWRlcnM6IHsgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke2R1bW15VG9rZW59YCB9LFxuICAgIH0pO1xuICAgIGV4cGVjdChtb2NrR29vZ2xlRXZlbnRzTGlzdCkudG9IYXZlQmVlbkNhbGxlZFdpdGgoe1xuICAgICAgY2FsZW5kYXJJZDogZHVtbXlDYWxlbmRhcklkLFxuICAgICAgc2hvd0RlbGV0ZWQ6IHRydWUsXG4gICAgICBzaW5nbGVFdmVudHM6IHRydWUsXG4gICAgfSk7XG4gICAgZXhwZWN0KHVwZGF0ZUdvb2dsZUNhbGVuZGFyVG9rZW5zSW5EYikudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICBkdW1teUNhbGVuZGFySWQsXG4gICAgICBkdW1teVN5bmNUb2tlbixcbiAgICAgIG51bGxcbiAgICApO1xuICAgIGV4cGVjdChhZGRsb2NhbEl0ZW1zVG9FdmVudDJWZWN0b3JPYmplY3RzKS50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gICAgZXhwZWN0KHVwc2VydEV2ZW50czIpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgZXhwZWN0LmFycmF5Q29udGFpbmluZyhbXG4gICAgICAgIGV4cGVjdC5vYmplY3RDb250YWluaW5nKHsgaWQ6ICdldmVudDEnIH0pLFxuICAgICAgICBleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7IGlkOiAnZXZlbnQyJyB9KSxcbiAgICAgIF0pLFxuICAgICAgZHVtbXlVc2VySWQsXG4gICAgICBkdW1teUNhbGVuZGFySWQsXG4gICAgICBkdW1teUNvbG9ySXRlbVxuICAgICk7XG4gICAgZXhwZWN0KHVwc2VydEF0dGVuZGVlczIpLnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgICBleHBlY3QodXBzZXJ0Q29uZmVyZW5jZTIpLnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgICBleHBlY3QoaW5zZXJ0UmVtaW5kZXJzR2l2ZW5FdmVudFJlc291cmNlKS50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gICAgZXhwZWN0KGRlbGV0ZUV2ZW50cykubm90LnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgZXhwZWN0LmFycmF5Q29udGFpbmluZyhbXG4gICAgICAgIGV4cGVjdC5vYmplY3RDb250YWluaW5nKHsgc3RhdHVzOiAnY2FuY2VsbGVkJyB9KSxcbiAgICAgIF0pLFxuICAgICAgZHVtbXlDYWxlbmRhcklkXG4gICAgKTtcbiAgICBleHBlY3QoZGVsZXRlQXR0ZW5kZWVzKS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgIGV4cGVjdChkZWxldGVSZW1pbmRlcnMpLnRvSGF2ZUJlZW5DYWxsZWQoKTsgLy8gZGVsZXRlUmVtaW5kZXJzIGlzIGNhbGxlZCBmb3IgZXZlbnRzVG9VcHNlcnQgYXMgd2VsbFxuICAgIGV4cGVjdChkZWxldGVDb25mZXJlbmNlcykubm90LnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgICBleHBlY3QoYWRkVG9RdWV1ZUZvclZlY3RvclNlYXJjaCkudG9IYXZlQmVlbkNhbGxlZCgpO1xuICB9KTtcblxuICAvLyBUZXN0IENhc2UgMjogU3VjY2Vzc2Z1bCBpbml0aWFsIHN5bmMgd2l0aCBzb21lIGRlbGV0ZWQgZXZlbnRzIG9uIHRoZSBmaXJzdCBwYWdlLlxuICBpdCgnc2hvdWxkIHN1Y2Nlc3NmdWxseSBzeW5jIHdpdGggZGVsZXRlZCBldmVudHMgb24gdGhlIGZpcnN0IHBhZ2UnLCBhc3luYyAoKSA9PiB7XG4gICAgKGdldEdvb2dsZUFQSVRva2VuIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoZHVtbXlUb2tlbik7XG4gICAgY29uc3QgbW9ja0l0ZW1zID0gW1xuICAgICAgeyBpZDogJ2V2ZW50MScsIHN1bW1hcnk6ICdBY3RpdmUgRXZlbnQnLCBzdGF0dXM6ICdjb25maXJtZWQnIH0sXG4gICAgICB7IGlkOiAnZXZlbnQyJywgc3VtbWFyeTogJ0NhbmNlbGxlZCBFdmVudCcsIHN0YXR1czogJ2NhbmNlbGxlZCcgfSxcbiAgICAgIHsgaWQ6ICdldmVudDMnLCBzdW1tYXJ5OiAnQW5vdGhlciBBY3RpdmUgRXZlbnQnLCBzdGF0dXM6ICd0ZW50YXRpdmUnIH0sXG4gICAgXTtcbiAgICBtb2NrR29vZ2xlRXZlbnRzTGlzdC5tb2NrUmVzb2x2ZWRWYWx1ZU9uY2Uoe1xuICAgICAgZGF0YToge1xuICAgICAgICBpdGVtczogbW9ja0l0ZW1zLFxuICAgICAgICBuZXh0UGFnZVRva2VuOiBudWxsLFxuICAgICAgICBuZXh0U3luY1Rva2VuOiBkdW1teVN5bmNUb2tlbixcbiAgICAgIH0sXG4gICAgfSk7XG4gICAgLy8gTW9jayB0aGF0IGRlbGV0ZUV2ZW50cyByZXR1cm5zIHRoZSBldmVudHMgaXQgXCJkZWxldGVkXCJcbiAgICAoZGVsZXRlRXZlbnRzIGFzIGplc3QuTW9jaykubW9ja0ltcGxlbWVudGF0aW9uKFxuICAgICAgYXN5bmMgKGV2ZW50c1RvRGVsZXRlLCBfY2FsZW5kYXJJZCkgPT4ge1xuICAgICAgICByZXR1cm4gZXZlbnRzVG9EZWxldGUubWFwKChlKSA9PiBlLmlkKTtcbiAgICAgIH1cbiAgICApO1xuXG4gICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaW5pdGlhbEdvb2dsZUNhbGVuZGFyU3luYzIoXG4gICAgICBkdW1teUNhbGVuZGFySWQsXG4gICAgICBkdW1teVVzZXJJZCxcbiAgICAgIGR1bW15Q2xpZW50VHlwZSxcbiAgICAgIGR1bW15Q29sb3JJdGVtXG4gICAgKTtcblxuICAgIGV4cGVjdChyZXN1bHQpLnRvQmUodHJ1ZSk7XG4gICAgZXhwZWN0KHVwZGF0ZUdvb2dsZUNhbGVuZGFyVG9rZW5zSW5EYikudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICBkdW1teUNhbGVuZGFySWQsXG4gICAgICBkdW1teVN5bmNUb2tlbixcbiAgICAgIG51bGxcbiAgICApO1xuICAgIGV4cGVjdChhZGRsb2NhbEl0ZW1zVG9FdmVudDJWZWN0b3JPYmplY3RzKS50b0hhdmVCZWVuQ2FsbGVkKCk7XG5cbiAgICAvLyBDaGVjayB1cHNlcnQgZm9yIG5vbi1jYW5jZWxsZWQgZXZlbnRzXG4gICAgZXhwZWN0KHVwc2VydEV2ZW50czIpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgZXhwZWN0LmFycmF5Q29udGFpbmluZyhbXG4gICAgICAgIGV4cGVjdC5vYmplY3RDb250YWluaW5nKHsgaWQ6ICdldmVudDEnLCBzdGF0dXM6ICdjb25maXJtZWQnIH0pLFxuICAgICAgICBleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7IGlkOiAnZXZlbnQzJywgc3RhdHVzOiAndGVudGF0aXZlJyB9KSxcbiAgICAgIF0pLFxuICAgICAgZHVtbXlVc2VySWQsXG4gICAgICBkdW1teUNhbGVuZGFySWQsXG4gICAgICBkdW1teUNvbG9ySXRlbVxuICAgICk7XG4gICAgZXhwZWN0KHVwc2VydEV2ZW50czIpLm5vdC50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgIGV4cGVjdC5hcnJheUNvbnRhaW5pbmcoW1xuICAgICAgICBleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7IGlkOiAnZXZlbnQyJywgc3RhdHVzOiAnY2FuY2VsbGVkJyB9KSxcbiAgICAgIF0pLFxuICAgICAgZXhwZWN0LmFueXRoaW5nKCksXG4gICAgICBleHBlY3QuYW55dGhpbmcoKSxcbiAgICAgIGV4cGVjdC5hbnl0aGluZygpXG4gICAgKTtcbiAgICBleHBlY3QodXBzZXJ0QXR0ZW5kZWVzMikudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgIGV4cGVjdCh1cHNlcnRDb25mZXJlbmNlMikudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgIGV4cGVjdChpbnNlcnRSZW1pbmRlcnNHaXZlbkV2ZW50UmVzb3VyY2UpLnRvSGF2ZUJlZW5DYWxsZWQoKTtcblxuICAgIC8vIENoZWNrIGRlbGV0ZSBmb3IgY2FuY2VsbGVkIGV2ZW50c1xuICAgIGV4cGVjdChkZWxldGVFdmVudHMpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgZXhwZWN0LmFycmF5Q29udGFpbmluZyhbXG4gICAgICAgIGV4cGVjdC5vYmplY3RDb250YWluaW5nKHsgaWQ6ICdldmVudDInLCBzdGF0dXM6ICdjYW5jZWxsZWQnIH0pLFxuICAgICAgXSksXG4gICAgICBkdW1teUNhbGVuZGFySWRcbiAgICApO1xuICAgIGV4cGVjdChkZWxldGVBdHRlbmRlZXMpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgZXhwZWN0LmFycmF5Q29udGFpbmluZyhbZXhwZWN0Lm9iamVjdENvbnRhaW5pbmcoeyBpZDogJ2V2ZW50MicgfSldKSxcbiAgICAgIGR1bW15Q2FsZW5kYXJJZFxuICAgICk7XG4gICAgLy8gZGVsZXRlUmVtaW5kZXJzIGlzIGNhbGxlZCBmb3IgYm90aCBkZWxldGVkIGFuZCB1cHNlcnRlZCBldmVudHNcbiAgICBleHBlY3QoZGVsZXRlUmVtaW5kZXJzKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgIGV4cGVjdC5hcnJheUNvbnRhaW5pbmcoW2V4cGVjdC5vYmplY3RDb250YWluaW5nKHsgaWQ6ICdldmVudDInIH0pXSksXG4gICAgICBkdW1teVVzZXJJZCxcbiAgICAgIGR1bW15Q2FsZW5kYXJJZFxuICAgICk7XG4gICAgZXhwZWN0KGRlbGV0ZUNvbmZlcmVuY2VzKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgIGV4cGVjdC5hcnJheUNvbnRhaW5pbmcoWydldmVudDInXSlcbiAgICApOyAvLyBTaW5jZSBkZWxldGVFdmVudHMgcmV0dXJucyBJRHNcblxuICAgIGV4cGVjdChhZGRUb1F1ZXVlRm9yVmVjdG9yU2VhcmNoKS50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gIH0pO1xuXG4gIC8vIFRlc3QgQ2FzZSAzOiBnZXRHb29nbGVBUElUb2tlbiB0aHJvd3MgYW4gZXJyb3IuXG4gIGl0KCdzaG91bGQgcmV0dXJuIGZhbHNlIGlmIGdldEdvb2dsZUFQSVRva2VuIHRocm93cyBhbiBlcnJvcicsIGFzeW5jICgpID0+IHtcbiAgICBjb25zdCBlcnJvck1lc3NhZ2UgPSAnRmFpbGVkIHRvIGdldCBBUEkgdG9rZW4nO1xuICAgIChnZXRHb29nbGVBUElUb2tlbiBhcyBqZXN0Lk1vY2spLm1vY2tSZWplY3RlZFZhbHVlKG5ldyBFcnJvcihlcnJvck1lc3NhZ2UpKTtcblxuICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGluaXRpYWxHb29nbGVDYWxlbmRhclN5bmMyKFxuICAgICAgZHVtbXlDYWxlbmRhcklkLFxuICAgICAgZHVtbXlVc2VySWQsXG4gICAgICBkdW1teUNsaWVudFR5cGUsXG4gICAgICBkdW1teUNvbG9ySXRlbVxuICAgICk7XG5cbiAgICBleHBlY3QocmVzdWx0KS50b0JlKGZhbHNlKTtcbiAgICBleHBlY3QoY29uc29sZUxvZ1NweSkudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICBleHBlY3QuYW55KEVycm9yKSxcbiAgICAgICcgdW5hYmxlIHRvIGluaXRpYWwgZ29vZ2xlIHN5bmMnXG4gICAgKTtcbiAgICBleHBlY3QobW9ja0dvb2dsZUV2ZW50c0xpc3QpLm5vdC50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gIH0pO1xuXG4gIC8vIFRlc3QgQ2FzZSA0OiBnb29nbGUuY2FsZW5kYXIoKS5ldmVudHMubGlzdCB0aHJvd3MgYSBub24tNDEwIGVycm9yIG9uIHRoZSBmaXJzdCBjYWxsLlxuICBpdCgnc2hvdWxkIHJldHVybiBmYWxzZSBpZiBldmVudHMubGlzdCB0aHJvd3MgYSBub24tNDEwIGVycm9yJywgYXN5bmMgKCkgPT4ge1xuICAgIGNvbnN0IGVycm9yVG9UaHJvdyA9IHsgY29kZTogNTAwLCBtZXNzYWdlOiAnSW50ZXJuYWwgU2VydmVyIEVycm9yJyB9O1xuICAgIChnZXRHb29nbGVBUElUb2tlbiBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKGR1bW15VG9rZW4pO1xuICAgIG1vY2tHb29nbGVFdmVudHNMaXN0Lm1vY2tSZWplY3RlZFZhbHVlT25jZShlcnJvclRvVGhyb3cpO1xuXG4gICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaW5pdGlhbEdvb2dsZUNhbGVuZGFyU3luYzIoXG4gICAgICBkdW1teUNhbGVuZGFySWQsXG4gICAgICBkdW1teVVzZXJJZCxcbiAgICAgIGR1bW15Q2xpZW50VHlwZSxcbiAgICAgIGR1bW15Q29sb3JJdGVtXG4gICAgKTtcblxuICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoZmFsc2UpO1xuICAgIGV4cGVjdChjb25zb2xlTG9nU3B5KS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgIGVycm9yVG9UaHJvdyxcbiAgICAgICcgdW5hYmxlIHRvIGluaXRpYWwgZ29vZ2xlIHN5bmMnXG4gICAgKTtcbiAgICBleHBlY3QodXBkYXRlR29vZ2xlQ2FsZW5kYXJUb2tlbnNJbkRiKS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgIGV4cGVjdChhZGRUb1F1ZXVlRm9yVmVjdG9yU2VhcmNoKS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgIGV4cGVjdChyZXNldEdvb2dsZVN5bmNGb3JDYWxlbmRhcikubm90LnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgfSk7XG5cbiAgLy8gTmV3IFRlc3QgQ2FzZSBmb3IgNDEwIEdPTkUgZXJyb3JcbiAgaXQoJ3Nob3VsZCBhdHRlbXB0IGZ1bGwgcmVzeW5jIGFuZCByZXR1cm4gdHJ1ZSBpZiBldmVudHMubGlzdCB0aHJvd3MgYSA0MTAgR09ORSBlcnJvcicsIGFzeW5jICgpID0+IHtcbiAgICBjb25zdCBlcnJvcjQxMCA9IHsgY29kZTogNDEwLCBtZXNzYWdlOiAnR29uZScgfTtcbiAgICAoZ2V0R29vZ2xlQVBJVG9rZW4gYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShkdW1teVRva2VuKTtcbiAgICAvLyBUaGlzIG1vY2sgc2V0dXAgaW1wbGllcyB0aGF0IHRoZSBmaXJzdCBjYWxsIHRvIGV2ZW50cy5saXN0IChpbml0aWFsIHN5bmMpIHRyaWdnZXJzIHRoZSA0MTBcbiAgICBtb2NrR29vZ2xlRXZlbnRzTGlzdC5tb2NrUmVqZWN0ZWRWYWx1ZU9uY2UoZXJyb3I0MTApO1xuICAgIChyZXNldEdvb2dsZVN5bmNGb3JDYWxlbmRhciBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKHRydWUpOyAvLyBTdWNjZXNzZnVsIHJlc3luY1xuXG4gICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaW5pdGlhbEdvb2dsZUNhbGVuZGFyU3luYzIoXG4gICAgICBkdW1teUNhbGVuZGFySWQsXG4gICAgICBkdW1teVVzZXJJZCxcbiAgICAgIGR1bW15Q2xpZW50VHlwZSxcbiAgICAgIGR1bW15Q29sb3JJdGVtXG4gICAgKTtcblxuICAgIGV4cGVjdChyZXN1bHQpLnRvQmUodHJ1ZSk7XG4gICAgZXhwZWN0KGNvbnNvbGVMb2dTcHkpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgYEdvb2dsZSBBUEkgcmV0dXJuZWQgNDEwIChHT05FKSBmb3IgY2FsZW5kYXIgJHtkdW1teUNhbGVuZGFySWR9LiBBdHRlbXB0aW5nIGZ1bGwgcmVzeW5jLmBcbiAgICApO1xuICAgIGV4cGVjdChyZXNldEdvb2dsZVN5bmNGb3JDYWxlbmRhcikudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICBkdW1teUNhbGVuZGFySWQsXG4gICAgICBkdW1teVVzZXJJZCxcbiAgICAgIGR1bW15Q2xpZW50VHlwZSxcbiAgICAgIGR1bW15Q29sb3JJdGVtXG4gICAgKTtcbiAgICAvLyBFbnN1cmUgb3RoZXIgb3BlcmF0aW9ucyB0aGF0IHdvdWxkIG9jY3VyIGJlZm9yZSB0aGUgZXJyb3IgYXJlIG5vdCB1bmV4cGVjdGVkbHkgY2FsbGVkIGFnYWluIGJ5IHRoaXMgcGF0aFxuICAgIGV4cGVjdCh1cGRhdGVHb29nbGVDYWxlbmRhclRva2Vuc0luRGIpLm5vdC50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gICAgZXhwZWN0KGFkZFRvUXVldWVGb3JWZWN0b3JTZWFyY2gpLm5vdC50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gIH0pO1xuXG4gIC8vIFRPRE86IEFkZCBtb3JlIHRlc3RzOlxuICAvLyAtIFBhZ2luYXRpb246IGV2ZW50cy5saXN0IGlzIGNhbGxlZCBtdWx0aXBsZSB0aW1lc1xuICAvLyAtIE5vIGV2ZW50cyB0byB1cHNlcnQgaW5pdGlhbGx5LCBidXQgZm91bmQgaW4gcGFnaW5hdGVkIHJlc3VsdHNcbiAgLy8gLSBObyBldmVudHMgYXQgYWxsIChlbXB0eSBpdGVtcyBhcnJheSlcbiAgLy8gLSBTcGVjaWZpYyBlcnJvciBoYW5kbGluZyBpZiBpbmRpdmlkdWFsIERCIG9wZXJhdGlvbnMgZmFpbCAodGhvdWdoIHRoZSBjdXJyZW50IGZ1bmN0aW9uIHNlZW1zIHRvIGNhdGNoIGFsbCB3aXRoIGEgZ2VuZXJpYyBtZXNzYWdlKVxufSk7XG5cbmRlc2NyaWJlKCdwZXJmb3JtQ2FsZW5kYXJTeW5jJywgKCkgPT4ge1xuICBsZXQgY29uc29sZUxvZ1NweTogamVzdC5TcHlJbnN0YW5jZTtcbiAgbGV0IGluaXRpYWxHb29nbGVDYWxlbmRhclN5bmMyU3B5OiBqZXN0LlNweUluc3RhbmNlO1xuXG4gIGJlZm9yZUVhY2goKCkgPT4ge1xuICAgIGplc3QuY2xlYXJBbGxNb2NrcygpO1xuICAgIGNvbnNvbGVMb2dTcHkgPSBqZXN0LnNweU9uKGNvbnNvbGUsICdsb2cnKS5tb2NrSW1wbGVtZW50YXRpb24oKCkgPT4ge30pO1xuICAgIC8vIFNweSBvbiBpbml0aWFsR29vZ2xlQ2FsZW5kYXJTeW5jMiBhcyBpdCdzIGluIHRoZSBzYW1lIG1vZHVsZVxuICAgIGluaXRpYWxHb29nbGVDYWxlbmRhclN5bmMyU3B5ID0gamVzdC5zcHlPbihcbiAgICAgIHN5bmNMb2dpYyxcbiAgICAgICdpbml0aWFsR29vZ2xlQ2FsZW5kYXJTeW5jMidcbiAgICApO1xuICB9KTtcblxuICBhZnRlckVhY2goKCkgPT4ge1xuICAgIGNvbnNvbGVMb2dTcHkubW9ja1Jlc3RvcmUoKTtcbiAgICBpbml0aWFsR29vZ2xlQ2FsZW5kYXJTeW5jMlNweS5tb2NrUmVzdG9yZSgpO1xuICB9KTtcblxuICBjb25zdCBkZWZhdWx0UGFyYW1zID0ge1xuICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZDogJ2NhbC1pbnQtaWQnLFxuICAgIGNhbGVuZGFySWQ6ICdjYWwtaWQnLFxuICAgIHVzZXJJZDogJ3VzZXItaWQnLFxuICAgIHRpbWV6b25lOiAnQW1lcmljYS9OZXdfWW9yaycsXG4gIH07XG5cbiAgY29uc3QgbW9ja0dvb2dsZUludGVncmF0aW9uRGF0YSA9IHtcbiAgICBpZDogJ2dpLWlkJyxcbiAgICBjbGllbnRUeXBlOiAnd2ViJyBhcyAnd2ViJyB8ICdpb3MnIHwgJ2FuZHJvaWQnIHwgJ2F0b21pYy13ZWInLFxuICB9O1xuICBjb25zdCBtb2NrQ2FsZW5kYXJJbkRiRGF0YSA9IHtcbiAgICBpZDogJ2RiLWNhbC1pZCcsXG4gICAgdXNlcklkOiBkZWZhdWx0UGFyYW1zLnVzZXJJZCxcbiAgfTtcbiAgY29uc3QgbW9ja0dvb2dsZUNvbG9yRGF0YSA9IHsgZXZlbnQ6IHt9LCBjYWxlbmRhcjoge30gfTsgLy8gRHVtbXkgY29sb3IgZGF0YVxuICBjb25zdCBtb2NrV2ViaG9va0RhdGEgPSB7IGlkOiAnd2ViaG9vay1pZCcsIHJlc291cmNlSWQ6ICdyZXNvdXJjZS1pZCcgfTtcblxuICAvLyBUZXN0IENhc2UgMTogU3VjY2Vzc2Z1bCBzeW5jIGFuZCBuZXcgd2ViaG9vayBjcmVhdGlvbi5cbiAgaXQoJ3Nob3VsZCBzdWNjZXNzZnVsbHkgc3luYyBhbmQgY3JlYXRlIGEgbmV3IHdlYmhvb2sgaWYgbm9uZSBleGlzdHMnLCBhc3luYyAoKSA9PiB7XG4gICAgKGdldEdvb2dsZUludGVncmF0aW9uIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoXG4gICAgICBtb2NrR29vZ2xlSW50ZWdyYXRpb25EYXRhXG4gICAgKTtcbiAgICAoZ2V0R29vZ2xlQ2FsZW5kYXJJbkRiIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoXG4gICAgICBtb2NrQ2FsZW5kYXJJbkRiRGF0YVxuICAgICk7XG4gICAgKGdldEdvb2dsZUFQSVRva2VuIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoJ2R1bW15LWFwaS10b2tlbicpO1xuICAgIChnZXRHb29nbGVDb2xvciBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKG1vY2tHb29nbGVDb2xvckRhdGEpO1xuICAgIGluaXRpYWxHb29nbGVDYWxlbmRhclN5bmMyU3B5Lm1vY2tSZXNvbHZlZFZhbHVlKHRydWUpO1xuICAgIChnZXRDYWxlbmRhcldlYmhvb2tCeUNhbGVuZGFySWQgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShudWxsKTsgLy8gTm8gZXhpc3Rpbmcgd2ViaG9va1xuICAgIChyZXF1ZXN0Q2FsZW5kYXJXYXRjaCBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgIHJlc291cmNlSWQ6ICduZXctcmVzb3VyY2UtaWQnLFxuICAgICAgcmVzb3VyY2VVcmk6ICd1cmknLFxuICAgIH0pO1xuICAgIChpbnNlcnRDYWxlbmRhcldlYmhvb2sgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZSh7fSk7XG5cbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBwZXJmb3JtQ2FsZW5kYXJTeW5jKGRlZmF1bHRQYXJhbXMpO1xuXG4gICAgZXhwZWN0KHJlc3VsdCkudG9FcXVhbCh7XG4gICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgbWVzc2FnZTogJ3N1Y2Nlc3NmdWxseSB0YWtlbiBjYXJlIG9mIGdvb2dsZUNhbGVuZGFyeVN5bmMhJyxcbiAgICAgIHN0YXR1czogMjAwLFxuICAgIH0pO1xuICAgIGV4cGVjdChpbml0aWFsR29vZ2xlQ2FsZW5kYXJTeW5jMlNweSkudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICBkZWZhdWx0UGFyYW1zLmNhbGVuZGFySWQsXG4gICAgICBkZWZhdWx0UGFyYW1zLnVzZXJJZCxcbiAgICAgIG1vY2tHb29nbGVJbnRlZ3JhdGlvbkRhdGEuY2xpZW50VHlwZSxcbiAgICAgIG1vY2tHb29nbGVDb2xvckRhdGFcbiAgICApO1xuICAgIGV4cGVjdChzdG9wQ2FsZW5kYXJXYXRjaCkubm90LnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgICBleHBlY3QoZGVsZXRlQ2FsZW5kYXJXZWJob29rQnlJZCkubm90LnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgICBleHBlY3QocmVxdWVzdENhbGVuZGFyV2F0Y2gpLnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgICBleHBlY3QoaW5zZXJ0Q2FsZW5kYXJXZWJob29rKS50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gIH0pO1xuXG4gIC8vIFRlc3QgQ2FzZSAyOiBTdWNjZXNzZnVsIHN5bmMgYW5kIGV4aXN0aW5nIHdlYmhvb2sgaXMgcmVwbGFjZWQuXG4gIGl0KCdzaG91bGQgc3VjY2Vzc2Z1bGx5IHN5bmMgYW5kIHJlcGxhY2UgYW4gZXhpc3Rpbmcgd2ViaG9vaycsIGFzeW5jICgpID0+IHtcbiAgICAoZ2V0R29vZ2xlSW50ZWdyYXRpb24gYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShcbiAgICAgIG1vY2tHb29nbGVJbnRlZ3JhdGlvbkRhdGFcbiAgICApO1xuICAgIChnZXRHb29nbGVDYWxlbmRhckluRGIgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShcbiAgICAgIG1vY2tDYWxlbmRhckluRGJEYXRhXG4gICAgKTtcbiAgICAoZ2V0R29vZ2xlQVBJVG9rZW4gYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZSgnZHVtbXktYXBpLXRva2VuJyk7XG4gICAgKGdldEdvb2dsZUNvbG9yIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUobW9ja0dvb2dsZUNvbG9yRGF0YSk7XG4gICAgaW5pdGlhbEdvb2dsZUNhbGVuZGFyU3luYzJTcHkubW9ja1Jlc29sdmVkVmFsdWUodHJ1ZSk7XG4gICAgKGdldENhbGVuZGFyV2ViaG9va0J5Q2FsZW5kYXJJZCBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKFxuICAgICAgbW9ja1dlYmhvb2tEYXRhXG4gICAgKTsgLy8gRXhpc3Rpbmcgd2ViaG9va1xuICAgIChzdG9wQ2FsZW5kYXJXYXRjaCBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKHt9KTtcbiAgICAoZGVsZXRlQ2FsZW5kYXJXZWJob29rQnlJZCBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKHt9KTtcbiAgICAocmVxdWVzdENhbGVuZGFyV2F0Y2ggYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICByZXNvdXJjZUlkOiAnbmV3LXJlc291cmNlLWlkJyxcbiAgICAgIHJlc291cmNlVXJpOiAndXJpJyxcbiAgICB9KTtcbiAgICAoaW5zZXJ0Q2FsZW5kYXJXZWJob29rIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoe30pO1xuXG4gICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgcGVyZm9ybUNhbGVuZGFyU3luYyhkZWZhdWx0UGFyYW1zKTtcblxuICAgIGV4cGVjdChyZXN1bHQpLnRvRXF1YWwoe1xuICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgIG1lc3NhZ2U6ICdzdWNjZXNzZnVsbHkgdGFrZW4gY2FyZSBvZiBnb29nbGVDYWxlbmRhcnlTeW5jIScsXG4gICAgICBzdGF0dXM6IDIwMCxcbiAgICB9KTtcbiAgICBleHBlY3Qoc3RvcENhbGVuZGFyV2F0Y2gpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgbW9ja1dlYmhvb2tEYXRhLmlkLFxuICAgICAgbW9ja1dlYmhvb2tEYXRhLnJlc291cmNlSWRcbiAgICApO1xuICAgIGV4cGVjdChkZWxldGVDYWxlbmRhcldlYmhvb2tCeUlkKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChtb2NrV2ViaG9va0RhdGEuaWQpO1xuICAgIGV4cGVjdChyZXF1ZXN0Q2FsZW5kYXJXYXRjaCkudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgIGV4cGVjdChpbnNlcnRDYWxlbmRhcldlYmhvb2spLnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgfSk7XG5cbiAgLy8gVGVzdCBDYXNlIDM6IGluaXRpYWxHb29nbGVDYWxlbmRhclN5bmMyIHJldHVybnMgZmFsc2UgKHN5bmMgZGlzYWJsZWQpLlxuICBpdCgnc2hvdWxkIGhhbmRsZSBzeW5jIGJlaW5nIGRpc2FibGVkIGJ5IGluaXRpYWxHb29nbGVDYWxlbmRhclN5bmMyJywgYXN5bmMgKCkgPT4ge1xuICAgIChnZXRHb29nbGVJbnRlZ3JhdGlvbiBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKFxuICAgICAgbW9ja0dvb2dsZUludGVncmF0aW9uRGF0YVxuICAgICk7XG4gICAgKGdldEdvb2dsZUNhbGVuZGFySW5EYiBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKFxuICAgICAgbW9ja0NhbGVuZGFySW5EYkRhdGFcbiAgICApO1xuICAgIChnZXRHb29nbGVBUElUb2tlbiBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKCdkdW1teS1hcGktdG9rZW4nKTtcbiAgICAoZ2V0R29vZ2xlQ29sb3IgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShtb2NrR29vZ2xlQ29sb3JEYXRhKTtcbiAgICBpbml0aWFsR29vZ2xlQ2FsZW5kYXJTeW5jMlNweS5tb2NrUmVzb2x2ZWRWYWx1ZShmYWxzZSk7IC8vIFN5bmMgZGlzYWJsZWRcbiAgICAodXBkYXRlR29vZ2xlSW50ZWdyYXRpb24gYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZSh7fSk7XG5cbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBwZXJmb3JtQ2FsZW5kYXJTeW5jKGRlZmF1bHRQYXJhbXMpO1xuXG4gICAgZXhwZWN0KHJlc3VsdCkudG9FcXVhbCh7XG4gICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgbWVzc2FnZTogJ3N5bmMgaXMgZGlzYWJsZWQgZm9yIGdvb2dsZUNhbGVuZGFyU3luYycsXG4gICAgICBzdGF0dXM6IDIwMCxcbiAgICAgIHN5bmNEaXNhYmxlZDogdHJ1ZSxcbiAgICB9KTtcbiAgICBleHBlY3QodXBkYXRlR29vZ2xlSW50ZWdyYXRpb24pLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgZGVmYXVsdFBhcmFtcy5jYWxlbmRhckludGVncmF0aW9uSWQsXG4gICAgICBmYWxzZVxuICAgICk7XG4gICAgZXhwZWN0KHJlcXVlc3RDYWxlbmRhcldhdGNoKS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpO1xuICB9KTtcblxuICAvLyBUZXN0IENhc2UgNDogZ2V0R29vZ2xlSW50ZWdyYXRpb24gcmV0dXJucyBubyBjbGllbnRUeXBlLlxuICBpdCgnc2hvdWxkIHJldHVybiBlcnJvciBpZiBjbGllbnRUeXBlIGlzIG5vdCBhdmFpbGFibGUnLCBhc3luYyAoKSA9PiB7XG4gICAgKGdldEdvb2dsZUludGVncmF0aW9uIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoeyBpZDogJ2dpLWlkJyB9KTsgLy8gTm8gY2xpZW50VHlwZVxuICAgIChnZXRHb29nbGVDYWxlbmRhckluRGIgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShcbiAgICAgIG1vY2tDYWxlbmRhckluRGJEYXRhXG4gICAgKTsgLy8gTmVlZHMgdG8gYmUgbW9ja2VkIHRvIHBhc3MgdGhpcyBzdGFnZVxuXG4gICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgcGVyZm9ybUNhbGVuZGFyU3luYyhkZWZhdWx0UGFyYW1zKTtcblxuICAgIGV4cGVjdChyZXN1bHQpLnRvRXF1YWwoe1xuICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICBtZXNzYWdlOiAnY2xpZW50VHlwZSBpcyBub3QgYXZhaWxhYmxlJyxcbiAgICAgIHN0YXR1czogNDAwLFxuICAgIH0pO1xuICB9KTtcblxuICAvLyBUZXN0IENhc2UgNTogZ2V0R29vZ2xlQ2FsZW5kYXJJbkRiIHJldHVybnMgbm8gaWQuXG4gIGl0KCdzaG91bGQgcmV0dXJuIGVycm9yIGlmIGNhbGVuZGFyIGlzIG5vdCBmb3VuZCBpbiBEQicsIGFzeW5jICgpID0+IHtcbiAgICAoZ2V0R29vZ2xlSW50ZWdyYXRpb24gYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShcbiAgICAgIG1vY2tHb29nbGVJbnRlZ3JhdGlvbkRhdGFcbiAgICApO1xuICAgIChnZXRHb29nbGVDYWxlbmRhckluRGIgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShudWxsKTsgLy8gQ2FsZW5kYXIgbm90IGluIERCXG5cbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBwZXJmb3JtQ2FsZW5kYXJTeW5jKGRlZmF1bHRQYXJhbXMpO1xuXG4gICAgLy8gVGhlIG1lc3NhZ2UgaW5jbHVkZXMgdGhlIGlkIHdoaWNoIGlzIHVuZGVmaW5lZCBpbiB0aGlzIGNhc2UsIHNvIGl0IGJlY29tZXMgJ3VuZGVmaW5lZCAtaWQsIGNhbGVuZGFyIHdhcyBkZWxldGVkJ1xuICAgIGV4cGVjdChyZXN1bHQubWVzc2FnZSkudG9FcXVhbCgndW5kZWZpbmVkIC1pZCwgY2FsZW5kYXIgd2FzIGRlbGV0ZWQnKTtcbiAgICBleHBlY3QocmVzdWx0LnN0YXR1cykudG9FcXVhbCg0MDApO1xuICAgIGV4cGVjdChyZXN1bHQuc3VjY2VzcykudG9CZShmYWxzZSk7XG4gIH0pO1xuXG4gIC8vIFRlc3QgQ2FzZSA2OiByZXF1ZXN0Q2FsZW5kYXJXYXRjaCB0aHJvd3MgYW4gZXJyb3IuXG4gIGl0KCdzaG91bGQgaGFuZGxlIGVycm9ycyBmcm9tIHJlcXVlc3RDYWxlbmRhcldhdGNoJywgYXN5bmMgKCkgPT4ge1xuICAgIChnZXRHb29nbGVJbnRlZ3JhdGlvbiBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKFxuICAgICAgbW9ja0dvb2dsZUludGVncmF0aW9uRGF0YVxuICAgICk7XG4gICAgKGdldEdvb2dsZUNhbGVuZGFySW5EYiBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKFxuICAgICAgbW9ja0NhbGVuZGFySW5EYkRhdGFcbiAgICApO1xuICAgIChnZXRHb29nbGVBUElUb2tlbiBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKCdkdW1teS1hcGktdG9rZW4nKTtcbiAgICAoZ2V0R29vZ2xlQ29sb3IgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShtb2NrR29vZ2xlQ29sb3JEYXRhKTtcbiAgICBpbml0aWFsR29vZ2xlQ2FsZW5kYXJTeW5jMlNweS5tb2NrUmVzb2x2ZWRWYWx1ZSh0cnVlKTtcbiAgICAoZ2V0Q2FsZW5kYXJXZWJob29rQnlDYWxlbmRhcklkIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUobnVsbCk7XG4gICAgY29uc3Qgd2F0Y2hFcnJvciA9IG5ldyBFcnJvcignRmFpbGVkIHRvIHdhdGNoIGNhbGVuZGFyJyk7XG4gICAgKHJlcXVlc3RDYWxlbmRhcldhdGNoIGFzIGplc3QuTW9jaykubW9ja1JlamVjdGVkVmFsdWUod2F0Y2hFcnJvcik7XG5cbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBwZXJmb3JtQ2FsZW5kYXJTeW5jKGRlZmF1bHRQYXJhbXMpO1xuXG4gICAgZXhwZWN0KHJlc3VsdCkudG9FcXVhbCh7XG4gICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgIG1lc3NhZ2U6ICdFcnJvciBtYW5hZ2luZyBjYWxlbmRhciB3ZWJob29rOiBGYWlsZWQgdG8gd2F0Y2ggY2FsZW5kYXInLFxuICAgICAgc3RhdHVzOiA1MDAsXG4gICAgfSk7XG4gICAgZXhwZWN0KGNvbnNvbGVMb2dTcHkpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgd2F0Y2hFcnJvcixcbiAgICAgICdFcnJvciBtYW5hZ2luZyBjYWxlbmRhciB3ZWJob29rJ1xuICAgICk7XG4gIH0pO1xuXG4gIC8vIFRlc3QgQ2FzZSA3IChOZXcpOiBpbnNlcnRDYWxlbmRhcldlYmhvb2sgdGhyb3dzIGFuIGVycm9yXG4gIGl0KCdzaG91bGQgaGFuZGxlIGVycm9ycyBmcm9tIGluc2VydENhbGVuZGFyV2ViaG9vaycsIGFzeW5jICgpID0+IHtcbiAgICAoZ2V0R29vZ2xlSW50ZWdyYXRpb24gYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShcbiAgICAgIG1vY2tHb29nbGVJbnRlZ3JhdGlvbkRhdGFcbiAgICApO1xuICAgIChnZXRHb29nbGVDYWxlbmRhckluRGIgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShcbiAgICAgIG1vY2tDYWxlbmRhckluRGJEYXRhXG4gICAgKTtcbiAgICAoZ2V0R29vZ2xlQVBJVG9rZW4gYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZSgnZHVtbXktYXBpLXRva2VuJyk7XG4gICAgKGdldEdvb2dsZUNvbG9yIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUobW9ja0dvb2dsZUNvbG9yRGF0YSk7XG4gICAgaW5pdGlhbEdvb2dsZUNhbGVuZGFyU3luYzJTcHkubW9ja1Jlc29sdmVkVmFsdWUodHJ1ZSk7XG4gICAgKGdldENhbGVuZGFyV2ViaG9va0J5Q2FsZW5kYXJJZCBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKG51bGwpOyAvLyBObyBleGlzdGluZyB3ZWJob29rXG4gICAgKHJlcXVlc3RDYWxlbmRhcldhdGNoIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgcmVzb3VyY2VJZDogJ25ldy1yZXNvdXJjZS1pZCcsXG4gICAgICByZXNvdXJjZVVyaTogJ3VyaScsXG4gICAgfSk7IC8vIHJlcXVlc3RDYWxlbmRhcldhdGNoIHN1Y2NlZWRzXG4gICAgY29uc3QgaW5zZXJ0RXJyb3IgPSBuZXcgRXJyb3IoJ0ZhaWxlZCB0byBpbnNlcnQgd2ViaG9vaycpO1xuICAgIChpbnNlcnRDYWxlbmRhcldlYmhvb2sgYXMgamVzdC5Nb2NrKS5tb2NrUmVqZWN0ZWRWYWx1ZShpbnNlcnRFcnJvcik7IC8vIGluc2VydENhbGVuZGFyV2ViaG9vayBmYWlsc1xuXG4gICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgcGVyZm9ybUNhbGVuZGFyU3luYyhkZWZhdWx0UGFyYW1zKTtcblxuICAgIGV4cGVjdChyZXN1bHQpLnRvRXF1YWwoe1xuICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICBtZXNzYWdlOiAnRXJyb3IgbWFuYWdpbmcgY2FsZW5kYXIgd2ViaG9vazogRmFpbGVkIHRvIGluc2VydCB3ZWJob29rJyxcbiAgICAgIHN0YXR1czogNTAwLFxuICAgIH0pO1xuICAgIGV4cGVjdChjb25zb2xlTG9nU3B5KS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgIGluc2VydEVycm9yLFxuICAgICAgJ0Vycm9yIG1hbmFnaW5nIGNhbGVuZGFyIHdlYmhvb2snXG4gICAgKTtcbiAgfSk7XG59KTtcbiJdfQ==