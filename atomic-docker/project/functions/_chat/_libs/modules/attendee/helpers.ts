// Attendee Helper Module - attendee management and operations
import { ApolloClient, InMemoryCache, NormalizedCacheObject } from '@apollo/client';
import { AttendeeType } from '../../types/AttendeeType';
import { MeetingAssistAttendeeType } from '../../types/MeetingAssistAttendeeType';
import { graphileClient } from '../../graphile/client';
import { v4 as uuid } from 'uuid';

const attendeeLogger = {
  info: console.log.bind(console, '[AttendeeHelpers] INFO:'),
  error: console.error.bind(console, '[AttendeeHelpers] ERROR:'),
  warn: console.warn.bind(console, '[AttendeeHelpers] WARN:'),
};

// Insert attendees for an event
export const upsertAttendeesForEvent = async (
  attendees: AttendeeType[],
  eventId: string
): Promise<boolean> => {
  try {
    if (!eventId || !attendees || attendees.length === 0) {
      attendeeLogger.warn('Invalid parameters for upserting attendees', { eventId, attendeeCount: attendees?.length });
      return false;
    }

    const uniqueAttendees = Array.from(new Set(attendees.map(a => a.email)))
      .map(email => attendees.find(a => a.email === email))
      .filter(Boolean);

    const attendeeData = uniqueAttendees.map(att => ({
      id: att?.id || uuid(),
      userId: att?.userId,
      eventId,
      name: att?.name,
      emails: att?.emails || [{ value: att?.email || '' }],
      phoneNumbers: att?.phoneNumbers,
      contactId: att?.contactId,
      updatedAt: new Date().toISOString(),
      createdDate: new Date().toISOString(),
      deleted: false,
    }));

    if (attendeeData.length === 0) return true;

    const query = `
      mutation UpsertAttendees($attendees: [Attendee_insert_input!]!) {
        insert_Attendee(
          objects: $attendees
          on_conflict: {
            constraint: Attendee_pkey
            update_columns: [
              name
              emails
              phoneNumbers
              contactId
              updatedAt
            ]
          }
        ) {
          affected_rows
          returning {
            id
            email
            name
          }
        }
      }
    `;

    const result = await graphileClient.request(query, { attendees: attendeeData });

    attendeeLogger.info('Successfully upserted attendees', {
      eventId,
      attendeeCount: attendeeData.length,
      affectedRows: result?.insert_Attendee?.affected_rows || 0
    });

    return true;
  } catch (error) {
    attendeeLogger.error('Error upserting attendees:', error);
    return false;
  }
};

// Delete attendees by IDs
export const deleteAttendeesWithIds = async (ids: string[]): Promise<boolean> => {
  try {
    if (!ids || ids.length === 0) {
      attendeeLogger.info('No attendees to delete');
      return true;
    }

    const query = `
      mutation DeleteAttendees($ids: [String!]!) {
        update_Attendee(where: { id: { _in: $ids } }, _set: { deleted: true }) {
          affected_rows
        }
      }
    `;

    const result = await graphileClient.request(query, { ids });

    attendeeLogger.info('Successfully deleted attendees', {
      attendeeCount: ids.length,
      affectedRows: result?.update_Attendee?.affected_rows || 0
    });

    return true;
  } catch (error) {
    attendeeLogger.error('Error deleting attendees:', error);
    return false;
  }
};

// Find attendee by email and event
export const findAttendeeByEmailAndEvent = async (
  email: string,
  eventId: string
): Promise<AttendeeType | null> => {
  try {
    const query = `
      query FindAttendeeByEmail($email: String!, $eventId: String!) {
        Attendee(
          where: {
            _and: [
              { eventId: { _eq: $eventId } },
              { emails: { _contains: { value: $email } } }
            ]
          }
        ) {
          id
          userId
          eventId
          name
          emails
          phoneNumbers
          contactId
          createdDate
          updatedAt
          deleted
        }
      }
    `;

    const result = await graphileClient.request(query, { email, eventId });
    const attendees = result?.Attendee || [];

    return attendees.length > 0 ? attendees[0] : null;
  } catch (error) {
    attendeeLogger.error('Error finding attendee by email and event:', error);
    return null;
  }
};

// Get attendees for an event
export const getAttendeesForEvent = async (eventId: string): Promise<AttendeeType[]> => {
  try {
    const query = `
      query GetAttendeesForEvent($eventId: String!) {
        Attendee(
          where: {
            _and: [
              { eventId: { _eq: $eventId } },
              { deleted: { _eq: false } }
            ]
          }
        ) {
          id
          userId
          eventId
          name
          emails
          phoneNumbers
          contactId
          createdDate
          updatedAt
          deleted
        }
      }
    `;

    const result = await graphileClient.request(query, { eventId });

    attendeeLogger.info('Successfully retrieved attendees for event', {
      eventId,
      attendeeCount: result?.Attendee?.length || 0
    });

    return result?.Attendee || [];
  } catch (error) {
    attendeeLogger.error('Error getting attendees for event:', error);
    return [];
  }
};

// Insert meeting assist attendees
export const insertMeetingAssistAttendee = async (
  attendee: MeetingAssistAttendeeType
): Promise<string | null> => {
  try {
    if (!attendee) {
      attendeeLogger.error('Attendee is required');
      return null;
    }

    const attendeeId = attendee.id || uuid();
    const query = `
      mutation InsertMeetingAttendee($attendee: Meeting_Assist_Attendee_insert_input!) {
        insert_Meeting_Assist_Attendee_one(object: $attendee) {
          id
          name
          emails
        }
      }
    `;

    const variables = {
      attendee: {
        id: attendeeId,
        meetingId: attendee.meetingId,
        name: attendee.name,
        emails: attendee.emails,
        hostId: attendee.hostId,
        contactId: attendee.contactId,
        createdDate: new Date().toISOString(),
        userId: attendee.userId,
        externalAttendee: attendee.externalAttendee || false,
        timezone: attendee.timezone,
        phoneNumbers: attendee.phoneNumbers,
      }
    };

    const result = await graphileClient.request(query, variables);
    const savedAttendee = result?.insert_Meeting_Assist_Attendee_one;

    if (savedAttendee) {
      attendeeLogger.info('Successfully inserted meeting assist attendee', {
        attendeeId: savedAttendee.id,
        meetingId: attendee.meetingId,
        name: savedAttendee.name
      });
      return savedAttendee.id;
    }

    return null;
  } catch (error) {
    attendeeLogger.error('Error inserting meeting assist attendee:', error);
    return null;
  }
};

// Create host attendee for meeting
export const createHostAttendee = async (
  meetingId: string,
  userId: string,
  hostName: string,
  hostEmail: string,
  contactId?: string
): Promise<string | null> => {
  try {
    if (!meetingId || !userId || !hostName) {
      attendeeLogger.error('Meeting ID, user ID, and host name are required');
      return null;
    }

    const attendeeId = uuid();
    const attendee: MeetingAssistAttendeeType = {
      id: attendeeId,
      meetingId,
      userId,
      name: hostName,
      emails: [{ value: hostEmail, primary: true }],
      hostId: userId,
      contactId,
      createdDate: new Date().toISOString(),
      externalAttendee: false,
    };

    return await insertMeetingAssistAttendee(attendee);
  } catch (error) {
    attendeeLogger.error('Error creating host attendee:', error);
    return null;
  }
};

// Validate attendee data
export const validateAttendeeData = (attendee: Partial<AttendeeType>): { isValid: boolean; errors: string[] } => {
  const errors: string[] = [];

  if (!attendee.email && (!attendee.emails || attendee.emails.length === 0)) {
    errors.push('Email is required');
  }

  if (!attendee.eventId) {
    errors.push('Event ID is required');
  }

  if (attendee.name && attendee.name.trim().length === 0) {
    errors.push('Name cannot be empty');
  }

  return {
    isValid: errors.length === 0,
    errors
  };
};

// Check if attendee exists
export const attendeeExists = async (attendeeId: string): Promise<boolean> => {
  try {
    const query = `
      query AttendeeExists($id: String!) {
        Attendee_by_pk(id: $id) {
n          id
        }
      }
    `;

    const result = await graphileClient.request(query, { id: attendeeId });
    return !!result?.Attendee_by_pk;
  } catch (error) {
    attendeeLogger.error('Error checking attendee existence:', error);
    return false;
  }
};

export default {
  upsertAttendeesForEvent,
  deleteAttendeesWithIds,
  findAttendeeByEmailAndEvent,
  getAttendeesForEvent,
  insertMeetingAssistAttendee,
  createHostAttendee,
  validateAttendeeData,
  attendeeExists,
};
