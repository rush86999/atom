// Event CRUD Operations - Comprehensive event management
import { EventType } from '../../types/EventType';
import { LanceDbEventSchema } from '../../../_utils/lancedb_service';
import getEventById from '../../../gql/getEventById';
import insertEventOne from '../../../gql/insertEventOne';
import updateEventById from '../../../gql/updateEventById';
import deleteEventById from '../../../gql/deleteEventById';

// Logger for events module
const eventLogger = {
  info: console.log,
  error: console.error,
  debug: console.debug,
};

/**
 * Get event by its primary key
 * @param eventId - Event UUID
 * @returns Event data or undefined
 */
export const getEventFromPrimaryKey = async (eventId: string): Promise<EventType | undefined> => {
  try {
    const event = await getEventById({ eventId });
    return event;
  } catch (error) {
    eventLogger.error('Error getting event by primary key:', error);
    return undefined;
  }
};

/**
 * Get event from LanceDB by ID
 * @param id - Event ID in LanceDB
 * @returns LanceDbEventSchema or null
 */
export const getEventFromLanceDb = async (id: string): Promise<LanceDbEventSchema | null> => {
  try {
    const { getEventById: getEventFromLanceDbById } = require('../../../_utils/lancedb_service');
    const event = await getEventFromLanceDbById(id);
    return event;
  } catch (error) {
    eventLogger.error('Error fetching event from LanceDB:', error);
    return null;
  }
};

/**
 * Upsert multiple events (bulk operation)
 * @param events - Array of events to upsert
 */
export const upsertEvents = async (events: EventType[]): Promise<void> => {
  try {
    if (!(events?.length > 0)) {
      eventLogger.info('No events provided to upsertEvents, returning early.', { eventCount: events?.length });
      return;
    }

    const operationName = 'InsertEvent';
    const query = `
      mutation InsertEvent($events: [Event_insert_input!]!) {
        insert_Event(objects: $events, on_conflict: {
          constraint: Event_pkey,
          update_columns: [
            allDay
            anyoneCanAddSelf
            attendees
            attendeeCount
            attendeeRespondedCount
            backgroundColor
            bufferTime
            calendarId
            calendar
            cancelIfAnyRefuse
            cancelled
            colorId
            conferenceId
            createdDate
            creator
            duration
            deleted
            endDate
            endDateTime
            eventId
            eventType
            extendedProperties
            followUp
            foregroundColor
            guestsCanInviteOthers
            guestsCanModify
            guestsCanSeeOtherGuests
            hangoutLink
            htmlLink
            iCalUID
            includeSuggestions
            meetingId
            notes
            organizer
            originalStartDateTime
            originalTimezone
            postPreference
            preEvent
            postEvent
            preferred
            priority
            privateCopy
            recurrence
            recurrenceRule
            recurringEventId
            sendUpdates
            source
            startDate
            startDateTime
            summary
            task
            taskId
            taskType
            timezone
            title
            transparency
            updatedAt
            userId
            user
            visibility
            weekly
            work
            weeklyWork
            weeklyPrivate
            weeklyWorkNonExceedingCapitalLimit
            weeklyPrivateNonExceedingIndividualCapitalLimit
            weeklyPrivateNonExceedingIndividualProfitThreshold
            weeklyWorkNonExceedingCapitalThreshold
            weeklyWorkNonExceedingIndividualCapitalLimit
            weeklyWorkNonExceedingIndividualProfitThreshold
            weeklyPrivateNonExceedingCapitalLimit
            weeklyPrivateNonExceedingIndividualCapitalLimit
            weeklyPrivateNonExceedingIndividualProfitThreshold
            weeklyWorkNonExceedingCapitalThreshold
            weeklyWorkNonExceedingIndividualCapitalLimit
            weeklyWorkNonExceedingIndividualProfitThreshold
            monthly
            monthlyWork
            monthlyPrivate
            monthlyWorkNonExceedingCapitalLimit
            monthlyPrivateNonExceedingIndividualCapitalLimit
            monthlyPrivateNonExceedingIndividualProfitThreshold
            monthlyWorkNonExceedingCapitalThreshold
            monthlyWorkNonExceedingIndividualCapitalLimit
            monthlyWorkNonExceedingIndividualProfitThreshold
            yearly
            yearlyWork
            yearlyPrivate
            yearlyWorkNonExceedingCapitalLimit
            yearlyPrivateNonExceedingIndividualCapitalLimit
            yearlyPrivateNonExceedingIndividualProfitThreshold
            yearlyWorkNonExceedingCapitalThreshold
            yearlyWorkNonExceedingIndividualCapitalLimit
            yearlyWorkNonExceedingIndividualProfitThreshold
            isBreak
            isFollowUp
            isBreakExceedingTime
            isBreakExceedingTimeAfterDuration
            isFollowUpExceedingTime
            isFollowUpExceedingTimeAfterDuration
            isPostEvent
            isPostEventExceedingTime
            isPreEvent
            isPreEventExceedingTime
            isModifiable
            isModifiableByAttendees
            pending
            userModifiedBy
            userModifiedAt
          ]
        }) {
          affected_rows
          returning {
            id
          }
        }
      }
    `;

    const variables = { events };

    const { makeHasuraGraphQLRequest } = require('../../../_utils/graphql-client');
    await makeHasuraGraphQLRequest(query, variables, operationName);

    eventLogger.info('Successfully upserted events', { count: events.length });
  } catch (error) {
    eventLogger.error('Error upserting events:', error);
    throw error;
  }
};

/**
 * Create single event
 * @param event - Single event to create
 */
export const createEvent = async (event: EventType): Promise<boolean> => {
  try {
    if (!event) {
      eventLogger.warn('No event provided to createEvent');
      return false;
    }

    const { insertEventOne } = require('../../../gql/insertEventOne');
    const result = await insertEventOne(event);

    eventLogger.info('Successfully created event', { eventId: result?.id });
    return true;
  } catch (error) {
    eventLogger.error('Error creating event:', error);
    return false;
  }
};

/**
 * Update single event by ID
 * @param eventId - Event ID to update
 * @param updates - Partial event updates
 */
export const updateEventById = async (
  eventId: string,
  updates: Partial<EventType>
): Promise<boolean> => {
  try {
    if (!eventId || !updates) {
      eventLogger.warn('Invalid arguments to updateEventById', { eventId, updates });
      return false;
    }

    const { updateEventById: updateEvent } = require('../../../gql/updateEventById');
    const result = await updateEvent(eventId, updates);

    eventLogger.info('Successfully updated event', { eventId });
    return true;
  } catch (error) {
    eventLogger.error('Error updating event:', error);
    return false;
  }
};

/**
 * Delete event by ID
 * @param eventId - Event ID to delete
 */
export const deleteEventGivenId = async (eventId: string): Promise<boolean> => {
  try {
    if (!eventId) {
      eventLogger.warn('No event ID provided to deleteEventGivenId');
      return false;
    }

    const result = await deleteEventById({ eventId });

    eventLogger.info('Successfully deleted event', { eventId });
    return true;
  } catch (error) {
    eventLogger.error('Error deleting event:', error);
    return false;
  }
};

/**
 * Bulk delete events by IDs
 * @param eventIds - Array of event IDs to delete
 */
export const deleteEventsByIds = async (eventIds: string[]): Promise<boolean> => {
  try {
    if (!(eventIds?.length > 0)) {
      eventLogger.warn('No event IDs provided to deleteEventsByIds');
      return false;
    }

    const { deleteEventsByIds: deleteEvents } = require('../../../_utils/lancedb_service');
    await deleteEvents(eventIds);

    eventLogger.info('Successfully deleted events', { count: eventIds.length });
    return true;
  } catch (error) {
    eventLogger.error('Error deleting events:', error);
    return false;
  }
};
