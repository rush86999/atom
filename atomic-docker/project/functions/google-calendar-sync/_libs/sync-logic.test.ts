// Test suite for sync-logic.ts
import * as syncLogic from './sync-logic'; // Import all exports for spyOn
const { initialGoogleCalendarSync2, performCalendarSync } = syncLogic;

import {
  getGoogleAPIToken,
  updateGoogleCalendarTokensInDb,
  addlocalItemsToEvent2VectorObjects,
  deleteAttendees,
  deleteReminders,
  deleteEvents,
  deleteConferences,
  insertRemindersGivenEventResource,
  upsertAttendees2,
  upsertConference2,
  upsertEvents2,
  addToQueueForVectorSearch,
  // Added for performCalendarSync
  getGoogleIntegration,
  getGoogleCalendarInDb,
  getGoogleColor,
  updateGoogleIntegration,
  getCalendarWebhookByCalendarId,
  stopCalendarWatch,
  deleteCalendarWebhookById,
  requestCalendarWatch,
  insertCalendarWebhook,
  resetGoogleSyncForCalendar, // Added for 410 GONE error handling
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
  let consoleLogSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
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
    (getGoogleAPIToken as jest.Mock).mockResolvedValue(dummyToken);
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
    (deleteEvents as jest.Mock).mockResolvedValue([]); // Assume no events were actually deleted from DB

    const result = await initialGoogleCalendarSync2(
      dummyCalendarId,
      dummyUserId,
      dummyClientType,
      dummyColorItem
    );

    expect(result).toBe(true);
    expect(getGoogleAPIToken).toHaveBeenCalledWith(
      dummyUserId,
      'google_calendar',
      dummyClientType
    );
    expect(google.calendar).toHaveBeenCalledWith({
      version: 'v3',
      headers: { Authorization: `Bearer ${dummyToken}` },
    });
    expect(mockGoogleEventsList).toHaveBeenCalledWith({
      calendarId: dummyCalendarId,
      showDeleted: true,
      singleEvents: true,
    });
    expect(updateGoogleCalendarTokensInDb).toHaveBeenCalledWith(
      dummyCalendarId,
      dummySyncToken,
      null
    );
    expect(addlocalItemsToEvent2VectorObjects).toHaveBeenCalled();
    expect(upsertEvents2).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ id: 'event1' }),
        expect.objectContaining({ id: 'event2' }),
      ]),
      dummyUserId,
      dummyCalendarId,
      dummyColorItem
    );
    expect(upsertAttendees2).toHaveBeenCalled();
    expect(upsertConference2).toHaveBeenCalled();
    expect(insertRemindersGivenEventResource).toHaveBeenCalled();
    expect(deleteEvents).not.toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ status: 'cancelled' }),
      ]),
      dummyCalendarId
    );
    expect(deleteAttendees).not.toHaveBeenCalled();
    expect(deleteReminders).toHaveBeenCalled(); // deleteReminders is called for eventsToUpsert as well
    expect(deleteConferences).not.toHaveBeenCalled();
    expect(addToQueueForVectorSearch).toHaveBeenCalled();
  });

  // Test Case 2: Successful initial sync with some deleted events on the first page.
  it('should successfully sync with deleted events on the first page', async () => {
    (getGoogleAPIToken as jest.Mock).mockResolvedValue(dummyToken);
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
    (deleteEvents as jest.Mock).mockImplementation(
      async (eventsToDelete, _calendarId) => {
        return eventsToDelete.map((e) => e.id);
      }
    );

    const result = await initialGoogleCalendarSync2(
      dummyCalendarId,
      dummyUserId,
      dummyClientType,
      dummyColorItem
    );

    expect(result).toBe(true);
    expect(updateGoogleCalendarTokensInDb).toHaveBeenCalledWith(
      dummyCalendarId,
      dummySyncToken,
      null
    );
    expect(addlocalItemsToEvent2VectorObjects).toHaveBeenCalled();

    // Check upsert for non-cancelled events
    expect(upsertEvents2).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ id: 'event1', status: 'confirmed' }),
        expect.objectContaining({ id: 'event3', status: 'tentative' }),
      ]),
      dummyUserId,
      dummyCalendarId,
      dummyColorItem
    );
    expect(upsertEvents2).not.toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ id: 'event2', status: 'cancelled' }),
      ]),
      expect.anything(),
      expect.anything(),
      expect.anything()
    );
    expect(upsertAttendees2).toHaveBeenCalled();
    expect(upsertConference2).toHaveBeenCalled();
    expect(insertRemindersGivenEventResource).toHaveBeenCalled();

    // Check delete for cancelled events
    expect(deleteEvents).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ id: 'event2', status: 'cancelled' }),
      ]),
      dummyCalendarId
    );
    expect(deleteAttendees).toHaveBeenCalledWith(
      expect.arrayContaining([expect.objectContaining({ id: 'event2' })]),
      dummyCalendarId
    );
    // deleteReminders is called for both deleted and upserted events
    expect(deleteReminders).toHaveBeenCalledWith(
      expect.arrayContaining([expect.objectContaining({ id: 'event2' })]),
      dummyUserId,
      dummyCalendarId
    );
    expect(deleteConferences).toHaveBeenCalledWith(
      expect.arrayContaining(['event2'])
    ); // Since deleteEvents returns IDs

    expect(addToQueueForVectorSearch).toHaveBeenCalled();
  });

  // Test Case 3: getGoogleAPIToken throws an error.
  it('should return false if getGoogleAPIToken throws an error', async () => {
    const errorMessage = 'Failed to get API token';
    (getGoogleAPIToken as jest.Mock).mockRejectedValue(new Error(errorMessage));

    const result = await initialGoogleCalendarSync2(
      dummyCalendarId,
      dummyUserId,
      dummyClientType,
      dummyColorItem
    );

    expect(result).toBe(false);
    expect(consoleLogSpy).toHaveBeenCalledWith(
      expect.any(Error),
      ' unable to initial google sync'
    );
    expect(mockGoogleEventsList).not.toHaveBeenCalled();
  });

  // Test Case 4: google.calendar().events.list throws a non-410 error on the first call.
  it('should return false if events.list throws a non-410 error', async () => {
    const errorToThrow = { code: 500, message: 'Internal Server Error' };
    (getGoogleAPIToken as jest.Mock).mockResolvedValue(dummyToken);
    mockGoogleEventsList.mockRejectedValueOnce(errorToThrow);

    const result = await initialGoogleCalendarSync2(
      dummyCalendarId,
      dummyUserId,
      dummyClientType,
      dummyColorItem
    );

    expect(result).toBe(false);
    expect(consoleLogSpy).toHaveBeenCalledWith(
      errorToThrow,
      ' unable to initial google sync'
    );
    expect(updateGoogleCalendarTokensInDb).not.toHaveBeenCalled();
    expect(addToQueueForVectorSearch).not.toHaveBeenCalled();
    expect(resetGoogleSyncForCalendar).not.toHaveBeenCalled();
  });

  // New Test Case for 410 GONE error
  it('should attempt full resync and return true if events.list throws a 410 GONE error', async () => {
    const error410 = { code: 410, message: 'Gone' };
    (getGoogleAPIToken as jest.Mock).mockResolvedValue(dummyToken);
    // This mock setup implies that the first call to events.list (initial sync) triggers the 410
    mockGoogleEventsList.mockRejectedValueOnce(error410);
    (resetGoogleSyncForCalendar as jest.Mock).mockResolvedValue(true); // Successful resync

    const result = await initialGoogleCalendarSync2(
      dummyCalendarId,
      dummyUserId,
      dummyClientType,
      dummyColorItem
    );

    expect(result).toBe(true);
    expect(consoleLogSpy).toHaveBeenCalledWith(
      `Google API returned 410 (GONE) for calendar ${dummyCalendarId}. Attempting full resync.`
    );
    expect(resetGoogleSyncForCalendar).toHaveBeenCalledWith(
      dummyCalendarId,
      dummyUserId,
      dummyClientType,
      dummyColorItem
    );
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
  let consoleLogSpy: jest.SpyInstance;
  let initialGoogleCalendarSync2Spy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
    // Spy on initialGoogleCalendarSync2 as it's in the same module
    initialGoogleCalendarSync2Spy = jest.spyOn(
      syncLogic,
      'initialGoogleCalendarSync2'
    );
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
    clientType: 'web' as 'web' | 'ios' | 'android' | 'atomic-web',
  };
  const mockCalendarInDbData = {
    id: 'db-cal-id',
    userId: defaultParams.userId,
  };
  const mockGoogleColorData = { event: {}, calendar: {} }; // Dummy color data
  const mockWebhookData = { id: 'webhook-id', resourceId: 'resource-id' };

  // Test Case 1: Successful sync and new webhook creation.
  it('should successfully sync and create a new webhook if none exists', async () => {
    (getGoogleIntegration as jest.Mock).mockResolvedValue(
      mockGoogleIntegrationData
    );
    (getGoogleCalendarInDb as jest.Mock).mockResolvedValue(
      mockCalendarInDbData
    );
    (getGoogleAPIToken as jest.Mock).mockResolvedValue('dummy-api-token');
    (getGoogleColor as jest.Mock).mockResolvedValue(mockGoogleColorData);
    initialGoogleCalendarSync2Spy.mockResolvedValue(true);
    (getCalendarWebhookByCalendarId as jest.Mock).mockResolvedValue(null); // No existing webhook
    (requestCalendarWatch as jest.Mock).mockResolvedValue({
      resourceId: 'new-resource-id',
      resourceUri: 'uri',
    });
    (insertCalendarWebhook as jest.Mock).mockResolvedValue({});

    const result = await performCalendarSync(defaultParams);

    expect(result).toEqual({
      success: true,
      message: 'successfully taken care of googleCalendarySync!',
      status: 200,
    });
    expect(initialGoogleCalendarSync2Spy).toHaveBeenCalledWith(
      defaultParams.calendarId,
      defaultParams.userId,
      mockGoogleIntegrationData.clientType,
      mockGoogleColorData
    );
    expect(stopCalendarWatch).not.toHaveBeenCalled();
    expect(deleteCalendarWebhookById).not.toHaveBeenCalled();
    expect(requestCalendarWatch).toHaveBeenCalled();
    expect(insertCalendarWebhook).toHaveBeenCalled();
  });

  // Test Case 2: Successful sync and existing webhook is replaced.
  it('should successfully sync and replace an existing webhook', async () => {
    (getGoogleIntegration as jest.Mock).mockResolvedValue(
      mockGoogleIntegrationData
    );
    (getGoogleCalendarInDb as jest.Mock).mockResolvedValue(
      mockCalendarInDbData
    );
    (getGoogleAPIToken as jest.Mock).mockResolvedValue('dummy-api-token');
    (getGoogleColor as jest.Mock).mockResolvedValue(mockGoogleColorData);
    initialGoogleCalendarSync2Spy.mockResolvedValue(true);
    (getCalendarWebhookByCalendarId as jest.Mock).mockResolvedValue(
      mockWebhookData
    ); // Existing webhook
    (stopCalendarWatch as jest.Mock).mockResolvedValue({});
    (deleteCalendarWebhookById as jest.Mock).mockResolvedValue({});
    (requestCalendarWatch as jest.Mock).mockResolvedValue({
      resourceId: 'new-resource-id',
      resourceUri: 'uri',
    });
    (insertCalendarWebhook as jest.Mock).mockResolvedValue({});

    const result = await performCalendarSync(defaultParams);

    expect(result).toEqual({
      success: true,
      message: 'successfully taken care of googleCalendarySync!',
      status: 200,
    });
    expect(stopCalendarWatch).toHaveBeenCalledWith(
      mockWebhookData.id,
      mockWebhookData.resourceId
    );
    expect(deleteCalendarWebhookById).toHaveBeenCalledWith(mockWebhookData.id);
    expect(requestCalendarWatch).toHaveBeenCalled();
    expect(insertCalendarWebhook).toHaveBeenCalled();
  });

  // Test Case 3: initialGoogleCalendarSync2 returns false (sync disabled).
  it('should handle sync being disabled by initialGoogleCalendarSync2', async () => {
    (getGoogleIntegration as jest.Mock).mockResolvedValue(
      mockGoogleIntegrationData
    );
    (getGoogleCalendarInDb as jest.Mock).mockResolvedValue(
      mockCalendarInDbData
    );
    (getGoogleAPIToken as jest.Mock).mockResolvedValue('dummy-api-token');
    (getGoogleColor as jest.Mock).mockResolvedValue(mockGoogleColorData);
    initialGoogleCalendarSync2Spy.mockResolvedValue(false); // Sync disabled
    (updateGoogleIntegration as jest.Mock).mockResolvedValue({});

    const result = await performCalendarSync(defaultParams);

    expect(result).toEqual({
      success: true,
      message: 'sync is disabled for googleCalendarSync',
      status: 200,
      syncDisabled: true,
    });
    expect(updateGoogleIntegration).toHaveBeenCalledWith(
      defaultParams.calendarIntegrationId,
      false
    );
    expect(requestCalendarWatch).not.toHaveBeenCalled();
  });

  // Test Case 4: getGoogleIntegration returns no clientType.
  it('should return error if clientType is not available', async () => {
    (getGoogleIntegration as jest.Mock).mockResolvedValue({ id: 'gi-id' }); // No clientType
    (getGoogleCalendarInDb as jest.Mock).mockResolvedValue(
      mockCalendarInDbData
    ); // Needs to be mocked to pass this stage

    const result = await performCalendarSync(defaultParams);

    expect(result).toEqual({
      success: false,
      message: 'clientType is not available',
      status: 400,
    });
  });

  // Test Case 5: getGoogleCalendarInDb returns no id.
  it('should return error if calendar is not found in DB', async () => {
    (getGoogleIntegration as jest.Mock).mockResolvedValue(
      mockGoogleIntegrationData
    );
    (getGoogleCalendarInDb as jest.Mock).mockResolvedValue(null); // Calendar not in DB

    const result = await performCalendarSync(defaultParams);

    // The message includes the id which is undefined in this case, so it becomes 'undefined -id, calendar was deleted'
    expect(result.message).toEqual('undefined -id, calendar was deleted');
    expect(result.status).toEqual(400);
    expect(result.success).toBe(false);
  });

  // Test Case 6: requestCalendarWatch throws an error.
  it('should handle errors from requestCalendarWatch', async () => {
    (getGoogleIntegration as jest.Mock).mockResolvedValue(
      mockGoogleIntegrationData
    );
    (getGoogleCalendarInDb as jest.Mock).mockResolvedValue(
      mockCalendarInDbData
    );
    (getGoogleAPIToken as jest.Mock).mockResolvedValue('dummy-api-token');
    (getGoogleColor as jest.Mock).mockResolvedValue(mockGoogleColorData);
    initialGoogleCalendarSync2Spy.mockResolvedValue(true);
    (getCalendarWebhookByCalendarId as jest.Mock).mockResolvedValue(null);
    const watchError = new Error('Failed to watch calendar');
    (requestCalendarWatch as jest.Mock).mockRejectedValue(watchError);

    const result = await performCalendarSync(defaultParams);

    expect(result).toEqual({
      success: false,
      message: 'Error managing calendar webhook: Failed to watch calendar',
      status: 500,
    });
    expect(consoleLogSpy).toHaveBeenCalledWith(
      watchError,
      'Error managing calendar webhook'
    );
  });

  // Test Case 7 (New): insertCalendarWebhook throws an error
  it('should handle errors from insertCalendarWebhook', async () => {
    (getGoogleIntegration as jest.Mock).mockResolvedValue(
      mockGoogleIntegrationData
    );
    (getGoogleCalendarInDb as jest.Mock).mockResolvedValue(
      mockCalendarInDbData
    );
    (getGoogleAPIToken as jest.Mock).mockResolvedValue('dummy-api-token');
    (getGoogleColor as jest.Mock).mockResolvedValue(mockGoogleColorData);
    initialGoogleCalendarSync2Spy.mockResolvedValue(true);
    (getCalendarWebhookByCalendarId as jest.Mock).mockResolvedValue(null); // No existing webhook
    (requestCalendarWatch as jest.Mock).mockResolvedValue({
      resourceId: 'new-resource-id',
      resourceUri: 'uri',
    }); // requestCalendarWatch succeeds
    const insertError = new Error('Failed to insert webhook');
    (insertCalendarWebhook as jest.Mock).mockRejectedValue(insertError); // insertCalendarWebhook fails

    const result = await performCalendarSync(defaultParams);

    expect(result).toEqual({
      success: false,
      message: 'Error managing calendar webhook: Failed to insert webhook',
      status: 500,
    });
    expect(consoleLogSpy).toHaveBeenCalledWith(
      insertError,
      'Error managing calendar webhook'
    );
  });
});
