// Conference Helper Module - conference management for meetings
import { graphileClient } from '../../graphile/client';
import { ConferenceType } from '../../types/ConferenceType';

const conferenceLogger = {
  info: console.log.bind(console, '[ConferenceHelpers] INFO:'),
  error: console.error.bind(console, '[ConferenceHelpers] ERROR:'),
  warn: console.warn.bind(console, '[ConferenceHelpers] WARN:'),
};

// Get conference by ID
export const getConferenceGivenId = async (conferenceId: string): Promise<ConferenceType | null> => {
  try {
    if (!conferenceId) {
      conferenceLogger.warn('Conference ID is required');
      return null;
    }

    const query = `
      query GetConferenceById($id: String!) {
        Conference_by_pk(id: $id) {
          id
          userId
          eventId
          name
          iconUri
          isZoom
          createdDate
          updatedAt
          deleted
          conferencingType
          conferenceId
          uri
          resource
          entryPoints
          notes
        }
      }
    `;

    const response = await graphileClient.request(query, { id: conferenceId });
    return response?.Conference_by_pk || null;

  } catch (error) {
    conferenceLogger.error('Error getting conference by ID:', error);
    return null;
  }
};

// Get conference for an event
export const getConferenceForEvent = async (eventId: string): Promise<ConferenceType | null> => {
  try {
    if (!eventId) {
      conferenceLogger.warn('Event ID is required');
      return null;
    }

    const query = `
      query GetConferenceForEvent($eventId: String!) {
        Conference(where: { eventId: { _eq: $eventId }, deleted: { _eq: false } }) {
          id
          userId
          eventId
          name
          iconUri
          isZoom
          createdDate
          updatedAt
          deleted
          conferencingType
          conferenceId
          uri
          resource
          entryPoints
          notes
        }
      }
    `;

    const response = await graphileClient.request(query, { eventId });
    const conferences = response?.Conference || [];

    conferenceLogger.info('Retrieved conference for event', {
      eventId,
      hasConference: conferences.length > 0
    });

    return conferences.length > 0 ? conferences[0] : null;

  } catch (error) {
    conferenceLogger.error('Error getting conference for event:', error);
    return null;
  }
};

// Delete conference by ID
export const deleteConferenceGivenId = async (conferenceId: string): Promise<boolean> => {
  try {
    if (!conferenceId) {
      conferenceLogger.warn('Conference ID is required');
      return false;
    }

    const query = `
      mutation DeleteConference($id: String!) {
        update_Conference_by_pk(
          pk_columns: { id: $id }
          _set: { deleted: true }
        ) {
          id
        }
      }
    `;

    const response = await graphileClient.request(query, { id: conferenceId });
    const success = !!response?.update_Conference_by_pk;

    if (success) {
      conferenceLogger.info('Successfully deleted conference', { conferenceId });
    }

    return success;

  } catch (error) {
    conferenceLogger.error('Error deleting conference:', error);
    return false;
  }
};

// Upsert conference for event
export const upsertConference = async (conference: Partial<ConferenceType>): Promise<string | null> => {
  try {
    if (!conference.eventId || !conference.userId) {
      conferenceLogger.error('Event ID and User ID are required for conference');
      return null;
    }

    const conferenceId = conference.id || `${conference.eventId}-conference-${Date.now()}`;

    const query = `
      mutation UpsertConference($conference: [Conference_insert_input!]!) {
        insert_Conference(
          objects: $conference
          on_conflict: {
            constraint: Conference_pkey
            update_columns: [
              name
              iconUri
              isZoom
              conferencingType
              conferenceId
              uri
              resource
              entryPoints
              notes
              updatedAt
            ]
          }
        ) {
          returning {
            id
          }
        }
      }
    `;

    const conferenceData = {
      id: conferenceId,
      userId: conference.userId,
      eventId: conference.eventId,
      name: conference.name || 'Conference',
      iconUri: conference.iconUri,
      isZoom: conference.isZoom || false,
      conferencingType: conference.conferencingType || 'generic',
      conferenceId: conference.conferenceId,
      uri: conference.uri,
      resource: conference.resource,
      entryPoints: conference.entryPoints,
      notes: conference.notes,
      createdDate: conference.createdDate || new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      deleted: false
    };

    const response = await graphileClient.request(query, {
      conference: [conferenceData]
    });

    const savedConference = response?.insert_Conference?.returning?.[0];

    if (savedConference) {
      conferenceLogger.info('Successfully upserted conference', {
        conferenceId: savedConference.id,
        eventId: conference.eventId,
        operation: conference.id ? 'update' : 'create'
      });
      return savedConference.id;
    }

    return null;

  } catch (error) {
    conferenceLogger.error('Error upserting conference:', error);
    return null;
  }
};

// Create Zoom conference
export const createZoomConference = async (
  eventId: string,
  userId: string,
  meetingLink: string,
  meetingId?: string
): Promise<string | null> => {
  try {
    if (!eventId || !userId || !meetingLink) {
      conferenceLogger.error('Event ID, user ID, and meeting link are required');
      return null;
    }

    const conference: Partial<ConferenceType> = {
      eventId,
      userId,
      name: 'Zoom Meeting',
      uri: meetingLink,
      isZoom: true,
      conferencingType: 'zoom',
      conferenceId: meetingId,
      iconUri: 'https://zoom.us/favicon.ico'
    };

    return await upsertConference(conference);
  } catch (error) {
    conferenceLogger.error('Error creating Zoom conference:', error);
    return null;
  }
};

// Create Google Meet conference
export const createGoogleMeetConference = async (
  eventId: string,
  userId: string,
  meetLink?: string,
  conferenceId?: string
): Promise<string | null> => {
  try {
    if (!eventId || !userId) {
      conferenceLogger.error('Event ID and user ID are required');
      return null;
    }

    const conference: Partial<ConferenceType> = {
      eventId,
      userId,
      name: 'Google Meet',
      uri: meetLink,
      isZoom: false,
      conferencingType: 'google',
      conferenceId,
      iconUri: 'https://meet.google.com/favicon.ico'
    };

    return await upsertConference(conference);
  } catch (error) {
    conferenceLogger.error('Error creating Google Meet conference:', error);
    return null;
  }
};

// Delete all conferences for an event
export const deleteConferencesForEvent = async (eventId: string): Promise<boolean> => {
  try {
    if (!eventId) {
      conferenceLogger.warn('Event ID is required');
      return false;
    }

    const query = `
      mutation DeleteConferencesForEvent($eventId: String!) {
        update_Conference(
          where: { eventId: { _eq: $eventId } }
          _set: { deleted: true }
        ) {
          affected_rows
        }
      }
    `;

    const response = await graphileClient.request(query, { eventId });
    const affected = response?.update_Conference?.affected_rows || 0;

    conferenceLogger.info('Deleted conferences for event', {
      eventId,
      deletedCount: affected
    });

    return affected > 0;

  } catch (error) {
    conferenceLogger.error('Error deleting conferences for event:', error);
    return false;
  }
};

// Validate conference data
export const validateConferenceData = (conference: Partial<ConferenceType>): {
  isValid: boolean;
  errors: string[];
} => {
  const errors: string[] = [];

  if (!conference.eventId) {
    errors.push('Event ID is required');
  }

  if (!conference.userId) {
    errors.push('User ID is required');
  }

  if (conference.uri && !conference.uri.match(/^https?:\\/\\//)) {
    errors.push('URI must be a valid URL');
  }

  return {
    isValid: errors.length === 0,
    errors
  };
};

// Get conference count for user
export const getConferenceCountForUser = async (userId: string): Promise<number> => {
  try {
    const query = `
      query GetConferenceCount($userId: uuid!) {
        Conference_aggregate(where: { userId: { _eq: $userId }, deleted: { _eq: false } }) {
          aggregate {
            count
          }
        }
      }
    `;

    const response = await graphileClient.request(query, { userId });
    return response?.Conference_aggregate?.aggregate?.count || 0;

  } catch (error) {
    conferenceLogger.error('Error getting conference count:', error);
    return 0;
  }
};

export default {
  getConferenceGivenId,
  getConferenceForEvent,
  deleteConferenceGivenId,
  upsertConference,
  createZoomConference,
  createGoogleMeetConference,
  deleteConferencesForEvent,
  validateConferenceData,
  getConferenceCountForUser,
};
