import { event2VectorBody } from './index'; // Assuming index.ts is the entry point
import * as lancedbHelper from '../_libs/lancedb_helper';
import * as eventApiHelper from '../_libs/event2VectorsWorker/api-helper'; // For convertEventTitleToOpenAIVector
import {
  Event2VectorBodyType,
  EventObject,
} from '../_libs/types/event2Vectors/types'; // Adjust path as needed
import { dayjs } from '@google_calendar_sync/_libs/date-utils'; // For date manipulations if needed in test data

// Mock dependencies
jest.mock('../_libs/lancedb_helper', () => ({
  bulkUpsertToLanceDBEvents: jest.fn(),
  bulkDeleteFromLanceDBEvents: jest.fn(),
}));

jest.mock('../_libs/event2VectorsWorker/api-helper', () => ({
  convertEventTitleToOpenAIVector: jest.fn(),
}));

const mockConvertEventTitleToOpenAIVector =
  eventApiHelper.convertEventTitleToOpenAIVector as jest.Mock;
const mockBulkUpsert = lancedbHelper.bulkUpsertToLanceDBEvents as jest.Mock;
const mockBulkDelete = lancedbHelper.bulkDeleteFromLanceDBEvents as jest.Mock;

describe('event2VectorBody', () => {
  beforeEach(() => {
    // Clear mock history before each test
    mockConvertEventTitleToOpenAIVector.mockClear();
    mockBulkUpsert.mockClear();
    mockBulkDelete.mockClear();
  });

  const baseEvent = {
    id: 'testEvent1',
    summary: 'Test Event Summary',
    description: 'Test Event Description',
    start: { dateTime: '2024-01-01T10:00:00Z', timeZone: 'UTC' },
    end: { dateTime: '2024-01-01T11:00:00Z', timeZone: 'UTC' },
  };

  const userId = 'testUser';
  const calendarId = 'testCalendar';

  it('should handle upsert operations correctly', async () => {
    const mockVector = [0.1, 0.2, 0.3];
    mockConvertEventTitleToOpenAIVector.mockResolvedValue(mockVector);

    const eventObject: EventObject = {
      method: 'upsert',
      event: baseEvent,
      calendarId,
    };
    const body: Event2VectorBodyType = { userId, events: [eventObject] };

    await event2VectorBody(body);

    expect(mockConvertEventTitleToOpenAIVector).toHaveBeenCalledTimes(1);
    expect(mockConvertEventTitleToOpenAIVector).toHaveBeenCalledWith(
      `${baseEvent.summary}:${baseEvent.description}`
    );

    expect(mockBulkUpsert).toHaveBeenCalledTimes(1);
    expect(mockBulkUpsert).toHaveBeenCalledWith([
      expect.objectContaining({
        id: `${baseEvent.id}#${calendarId}`,
        userId,
        vector: mockVector,
        start_date: dayjs(baseEvent.start.dateTime.slice(0, 19))
          .tz(baseEvent.start.timeZone, true)
          .format(),
        end_date: dayjs(baseEvent.end.dateTime.slice(0, 19))
          .tz(baseEvent.end.timeZone, true)
          .format(),
        raw_event_text: `${baseEvent.summary}:${baseEvent.description}`,
      }),
    ]);
    expect(mockBulkDelete).not.toHaveBeenCalled();
  });

  it('should handle upsert operations for events with only summary', async () => {
    const mockVector = [0.4, 0.5, 0.6];
    mockConvertEventTitleToOpenAIVector.mockResolvedValue(mockVector);
    const eventWithoutDescription = { ...baseEvent, description: undefined };

    const eventObject: EventObject = {
      method: 'upsert',
      event: eventWithoutDescription,
      calendarId,
    };
    const body: Event2VectorBodyType = { userId, events: [eventObject] };

    await event2VectorBody(body);

    expect(mockConvertEventTitleToOpenAIVector).toHaveBeenCalledTimes(1);
    expect(mockConvertEventTitleToOpenAIVector).toHaveBeenCalledWith(
      eventWithoutDescription.summary
    );

    expect(mockBulkUpsert).toHaveBeenCalledTimes(1);
    expect(mockBulkUpsert).toHaveBeenCalledWith([
      expect.objectContaining({
        raw_event_text: eventWithoutDescription.summary,
      }),
    ]);
  });

  it('should handle delete operations correctly', async () => {
    const eventObject: EventObject = {
      method: 'delete',
      event: { id: 'eventToDelete1' }, // Only ID is needed for delete
      calendarId,
    };
    const body: Event2VectorBodyType = { userId, events: [eventObject] };

    await event2VectorBody(body);

    expect(mockConvertEventTitleToOpenAIVector).not.toHaveBeenCalled();
    expect(mockBulkUpsert).not.toHaveBeenCalled();
    expect(mockBulkDelete).toHaveBeenCalledTimes(1);
    expect(mockBulkDelete).toHaveBeenCalledWith([
      `${eventObject.event.id}#${calendarId}`,
    ]);
  });

  it('should handle mixed upsert and delete operations', async () => {
    const mockVectorUpsert = [0.7, 0.8, 0.9];
    mockConvertEventTitleToOpenAIVector.mockResolvedValue(mockVectorUpsert);

    const upsertEventObject: EventObject = {
      method: 'upsert',
      event: baseEvent,
      calendarId: 'calUpsert',
    };
    const deleteEventObject: EventObject = {
      method: 'delete',
      event: { id: 'eventToDelete2' },
      calendarId: 'calDelete',
    };
    const body: Event2VectorBodyType = {
      userId,
      events: [upsertEventObject, deleteEventObject],
    };

    await event2VectorBody(body);

    // Upsert checks
    expect(mockConvertEventTitleToOpenAIVector).toHaveBeenCalledTimes(1);
    expect(mockBulkUpsert).toHaveBeenCalledTimes(1);
    expect(mockBulkUpsert).toHaveBeenCalledWith([
      expect.objectContaining({
        id: `${baseEvent.id}#${upsertEventObject.calendarId}`,
      }),
    ]);

    // Delete checks
    expect(mockBulkDelete).toHaveBeenCalledTimes(1);
    expect(mockBulkDelete).toHaveBeenCalledWith([
      `${deleteEventObject.event.id}#${deleteEventObject.calendarId}`,
    ]);
  });

  it('should handle empty events array', async () => {
    const body: Event2VectorBodyType = { userId, events: [] };
    await event2VectorBody(body);

    expect(mockConvertEventTitleToOpenAIVector).not.toHaveBeenCalled();
    expect(mockBulkUpsert).not.toHaveBeenCalled();
    expect(mockBulkDelete).not.toHaveBeenCalled();
  });

  it('should handle events array with only unknown methods', async () => {
    const eventObject: EventObject = {
      method: 'unknown_method' as any, // Test invalid method
      event: baseEvent,
      calendarId,
    };
    const body: Event2VectorBodyType = { userId, events: [eventObject] };
    await event2VectorBody(body);

    expect(mockConvertEventTitleToOpenAIVector).not.toHaveBeenCalled();
    expect(mockBulkUpsert).not.toHaveBeenCalled();
    expect(mockBulkDelete).not.toHaveBeenCalled();
  });

  it('should use end.timeZone if available, otherwise start.timeZone for end_date calculation', async () => {
    const mockVector = [0.1, 0.2, 0.3];
    mockConvertEventTitleToOpenAIVector.mockResolvedValue(mockVector);

    const eventWithSpecificEndTimeZone = {
      ...baseEvent,
      end: { dateTime: '2024-01-01T12:00:00Z', timeZone: 'America/New_York' }, // Different from start
    };
    const eventObject: EventObject = {
      method: 'upsert',
      event: eventWithSpecificEndTimeZone,
      calendarId,
    };
    const body: Event2VectorBodyType = { userId, events: [eventObject] };
    await event2VectorBody(body);

    expect(mockBulkUpsert).toHaveBeenCalledWith([
      expect.objectContaining({
        end_date: dayjs(eventWithSpecificEndTimeZone.end.dateTime.slice(0, 19))
          .tz(eventWithSpecificEndTimeZone.end.timeZone, true)
          .format(),
      }),
    ]);

    // Test fallback to start.timeZone for end_date if end.timeZone is missing
    mockBulkUpsert.mockClear();
    const eventWithoutEndTimeZone = {
      ...baseEvent,
      end: { dateTime: '2024-01-01T11:00:00Z', timeZone: undefined }, // end.timeZone is undefined
    };
    const eventObject2: EventObject = {
      method: 'upsert',
      event: eventWithoutEndTimeZone,
      calendarId,
    };
    const body2: Event2VectorBodyType = { userId, events: [eventObject2] };
    await event2VectorBody(body2);

    expect(mockBulkUpsert).toHaveBeenCalledWith([
      expect.objectContaining({
        end_date: dayjs(eventWithoutEndTimeZone.end.dateTime.slice(0, 19))
          .tz(eventWithoutEndTimeZone.start.timeZone, true)
          .format(),
      }),
    ]);
  });
});
