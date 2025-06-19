import { handler } from '../google-calendar-sync-auth';
import { google } from 'googleapis';
import {
  getGoogleIntegration,
  getGoogleCalendarInDb,
  getGoogleAPIToken,
  getGoogleColor,
  updateGoogleCalendarTokensInDb,
  upsertEvents2,
  upsertAttendees2,
  insertRemindersGivenEventResource,
  upsertConference2,
  getCalendarWebhookByCalendarId,
  requestCalendarWatch,
  insertCalendarWebhook,
  addToQueueForVectorSearch,
  addlocalItemsToEvent2VectorObjects,
  deleteAttendees,
  deleteReminders,
  deleteEvents,
  deleteConferences,
  stopCalendarWatch,
  deleteCalendarWebhookById,
  updateGoogleIntegration,
  resetGoogleSyncForCalendar,
} from '@google_calendar_sync/_libs/api-helper';

// Mock Express req and res objects
const mockRequest = (body: any, headers?: any, params?: any): any => ({
  body,
  headers: headers || {},
  params: params || {},
});

const mockResponse = (): any => {
  const res: any = {};
  res.status = jest.fn().mockReturnValue(res);
  res.json = jest.fn().mockReturnValue(res);
  return res;
};

// Mock googleapis
const mockGoogleEventsList = jest.fn();
const mockGoogleColorsGet = jest.fn();

jest.mock('googleapis', () => ({
  google: {
    calendar: jest.fn(() => ({
      events: {
        list: mockGoogleEventsList,
      },
      colors: {
        get: mockGoogleColorsGet,
      }
    })),
  },
}));

// Mock api-helper
jest.mock('@google_calendar_sync/_libs/api-helper', () => ({
  getGoogleIntegration: jest.fn(),
  getGoogleCalendarInDb: jest.fn(),
  getGoogleAPIToken: jest.fn(),
  getGoogleColor: jest.fn(),
  updateGoogleCalendarTokensInDb: jest.fn(),
  upsertEvents2: jest.fn(),
  upsertAttendees2: jest.fn(),
  insertRemindersGivenEventResource: jest.fn(),
  upsertConference2: jest.fn(),
  getCalendarWebhookByCalendarId: jest.fn(),
  requestCalendarWatch: jest.fn(),
  insertCalendarWebhook: jest.fn(),
  addToQueueForVectorSearch: jest.fn(),
  addlocalItemsToEvent2VectorObjects: jest.fn(), // This is actually in sync-logic, but sync-logic calls it.
                                               // The handler calls performCalendarSync which calls initialGoogleCalendarSync2, which calls this.
                                               // So we mock it here as if it's a direct dependency for simplicity in integration test.
  deleteAttendees: jest.fn(),
  deleteReminders: jest.fn(),
  deleteEvents: jest.fn(),
  deleteConferences: jest.fn(),
  stopCalendarWatch: jest.fn(),
  deleteCalendarWebhookById: jest.fn(),
  updateGoogleIntegration: jest.fn(),
  resetGoogleSyncForCalendar: jest.fn(),
}));

describe('Google Calendar Sync Auth Handler - Integration Tests', () => {
  let consoleLogSpy: jest.SpyInstance;
  let consoleErrorSpy: jest.SpyInstance;

  const defaultRequestBody = {
    calendarIntegrationId: 'int-id-123',
    calendarId: 'cal-id-456',
    userId: 'user-id-789',
    timezone: 'America/New_York',
  };

  const mockEventItems = [
    { id: 'event1', summary: 'Event 1', status: 'confirmed', start: { dateTime: '2024-01-01T10:00:00Z'}, end: { dateTime: '2024-01-01T11:00:00Z'} },
    { id: 'event2', summary: 'Event 2', status: 'confirmed', start: { dateTime: '2024-01-02T10:00:00Z'}, end: { dateTime: '2024-01-02T11:00:00Z'} },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {}); // If handler uses console.error

    // Default Mocks for successful flow
    (getGoogleIntegration as jest.Mock).mockResolvedValue({
        id: defaultRequestBody.calendarIntegrationId,
        clientType: 'web',
        googleRefreshToken: 'refresh-token',
        userId: defaultRequestBody.userId
    });
    (getGoogleCalendarInDb as jest.Mock).mockResolvedValue({
        id: defaultRequestBody.calendarId,
        userId: defaultRequestBody.userId,
        syncToken: null,
        pageToken: null
    });
    (getGoogleAPIToken as jest.Mock).mockResolvedValue('dummy-access-token');
    (getGoogleColor as jest.Mock).mockResolvedValue({ calendar: {}, event: {} }); // Mock for getGoogleColor in sync-logic
    mockGoogleColorsGet.mockResolvedValue({ data: { calendar: {}, event: {} } }); // Mock for google.colors.get

    mockGoogleEventsList.mockResolvedValue({
      data: {
        items: mockEventItems,
        nextPageToken: null,
        nextSyncToken: 'new-sync-token-123',
      },
    });

    (updateGoogleCalendarTokensInDb as jest.Mock).mockResolvedValue(undefined);
    (upsertEvents2 as jest.Mock).mockResolvedValue(undefined);
    (upsertAttendees2 as jest.Mock).mockResolvedValue(undefined);
    (insertRemindersGivenEventResource as jest.Mock).mockResolvedValue(undefined);
    (upsertConference2 as jest.Mock).mockResolvedValue(undefined);
    (getCalendarWebhookByCalendarId as jest.Mock).mockResolvedValue(null); // No existing webhook
    (requestCalendarWatch as jest.Mock).mockResolvedValue({ id: 'watch-id-xyz', resourceId: 'resource-id-abc' });
    (insertCalendarWebhook as jest.Mock).mockResolvedValue(undefined);
    (addToQueueForVectorSearch as jest.Mock).mockResolvedValue(undefined);
    (addlocalItemsToEvent2VectorObjects as jest.Mock).mockImplementation(() => {}); // Does not return promise

    (deleteAttendees as jest.Mock).mockResolvedValue(undefined);
    (deleteReminders as jest.Mock).mockResolvedValue(undefined);
    (deleteEvents as jest.Mock).mockResolvedValue([]);
    (deleteConferences as jest.Mock).mockResolvedValue(undefined);
    (stopCalendarWatch as jest.Mock).mockResolvedValue(undefined);
    (deleteCalendarWebhookById as jest.Mock).mockResolvedValue(undefined);
    (updateGoogleIntegration as jest.Mock).mockResolvedValue(undefined);
    (resetGoogleSyncForCalendar as jest.Mock).mockResolvedValue(true);
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
    consoleErrorSpy.mockRestore();
  });

  it('should perform a successful initial sync and create a new webhook', async () => {
    const mockReq = mockRequest(defaultRequestBody);
    const mockRes = mockResponse();

    await handler(mockReq, mockRes);

    expect(mockRes.status).toHaveBeenCalledWith(200);
    expect(mockRes.json).toHaveBeenCalledWith({
      message: 'successfully taken care of googleCalendarySync!',
      event: defaultRequestBody,
    });

    expect(getGoogleIntegration).toHaveBeenCalledWith(defaultRequestBody.calendarIntegrationId);
    expect(getGoogleCalendarInDb).toHaveBeenCalledWith(defaultRequestBody.calendarId);
    expect(getGoogleAPIToken).toHaveBeenCalledWith(defaultRequestBody.userId, 'google_calendar', 'web');
    // getGoogleColor is called by performCalendarSync, which is called by the handler
    expect(getGoogleColor).toHaveBeenCalledWith('dummy-access-token');

    expect(mockGoogleEventsList).toHaveBeenCalledWith({
      calendarId: defaultRequestBody.calendarId,
      showDeleted: true,
      singleEvents: true,
    });
    expect(updateGoogleCalendarTokensInDb).toHaveBeenCalledWith(defaultRequestBody.calendarId, 'new-sync-token-123', null);

    // Check that upsertEvents2 was called with the events from the mock
    // The actual events passed to upsertEvents2 are transformed, so we check for key properties if transformation is complex
    // For now, assuming events are passed as is from the list.
    expect(upsertEvents2).toHaveBeenCalledWith(
        expect.arrayContaining(mockEventItems.map(item => expect.objectContaining({id: item.id}))),
        defaultRequestBody.userId,
        defaultRequestBody.calendarId,
        expect.any(Object) // colorItem
    );

    expect(getCalendarWebhookByCalendarId).toHaveBeenCalledWith(defaultRequestBody.calendarId);
    expect(requestCalendarWatch).toHaveBeenCalled();
    expect(insertCalendarWebhook).toHaveBeenCalledWith(expect.objectContaining({
      calendarId: defaultRequestBody.calendarId,
      userId: defaultRequestBody.userId,
      calendarIntegrationId: defaultRequestBody.calendarIntegrationId,
    }));
    expect(addToQueueForVectorSearch).toHaveBeenCalled();
    expect(addlocalItemsToEvent2VectorObjects).toHaveBeenCalled(); // Called by initialGoogleCalendarSync2
  });

  it('should disable sync and not create webhooks if initial sync logic fails', async () => {
    const mockReq = mockRequest(defaultRequestBody);
    const mockRes = mockResponse();

    // Override getGoogleAPIToken to simulate a failure in initialGoogleCalendarSync2
    // This should cause initialGoogleCalendarSync2 to return false,
    // then performCalendarSync to return { success: true, ..., syncDisabled: true }
    // and the handler to then call updateGoogleIntegration with 'false'
    (getGoogleAPIToken as jest.Mock).mockRejectedValueOnce(new Error('Failed to get API token'));

    await handler(mockReq, mockRes);

    expect(mockRes.status).toHaveBeenCalledWith(200);
    expect(mockRes.json).toHaveBeenCalledWith({
      message: 'sync is disabled for googleCalendarSync', // This message comes from performCalendarSync's handling of initialGoogleCalendarSync2 returning false
      event: defaultRequestBody,
    });

    // performCalendarSync calls updateGoogleIntegration when initialGoogleCalendarSync2 returns false
    expect(updateGoogleIntegration).toHaveBeenCalledWith(defaultRequestBody.calendarIntegrationId, false);

    expect(requestCalendarWatch).not.toHaveBeenCalled();
    expect(insertCalendarWebhook).not.toHaveBeenCalled();
    expect(addToQueueForVectorSearch).not.toHaveBeenCalled(); // This is part of initialGoogleCalendarSync2, which effectively failed
  });

  // Further test cases will be added here:
  // - Handling of existing webhook
  // - Error scenarios (e.g., getGoogleIntegration fails, events.list fails with non-410, events.list fails with 410)
  // - Input validation failures
});
