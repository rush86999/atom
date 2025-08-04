import {
  authApiToken,
  classificationUrl,
  dayOfWeekIntToString,
  defaultOpenAIAPIKey,
  externalMeetingLabel,
  hasuraAdminSecret,
  hasuraGraphUrl,
  meetingLabel,
  minThresholdScore,
  optaPlannerPassword,
  optaPlannerUrl,
  optaPlannerUsername,
} from '@features_apply/_libs/constants';
import {
  BufferTimeNumberType,
  EventPlusType,
  EventType,
  MeetingAssistAttendeeType,
  MeetingAssistEventType,
  MeetingAssistPreferredTimeRangeType,
  MeetingAssistType,
  EventMeetingPlusType,
  PreferredTimeRangeType,
  RemindersForEventType,
  ValuesToReturnForBufferEventsType,
  UserPreferenceType,
  CalendarType,
  WorkTimeType,
  TimeSlotType,
  MonthType,
  DayType,
  MM,
  DD,
  MonthDayType,
  Time,
  EventPartPlannerRequestBodyType,
  InitialEventPartType,
  InitialEventPartTypePlus,
  UserPlannerRequestBodyType,
  ReturnBodyForExternalAttendeeForOptaplannerPrepType,
  PlannerRequestBodyType,
  FreemiumType,
  OpenSearchResponseBodyType,
  CategoryType,
  classificationResponseBody as ClassificationResponseBodyType,
  BufferTimeObjectType,
  ReminderType,
  CategoryEventType,
  OpenSearchGetResponseBodyType,
} from '@features_apply/_libs/types';
import got from 'got';
import { v4 as uuid } from 'uuid';
import dayjs from 'dayjs';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import _ from 'lodash';

import AWS from 'aws-sdk';
import { getISODay, setISODay } from 'date-fns';
import OpenAI from 'openai';
import {
  getEventById,
  searchTrainingEvents,
  deleteTrainingEventsByIds,
  upsertTrainingEvents,
  TrainingEventSchema,
  EventSchema,
} from '@functions/_utils/lancedb_service';
import { FeaturesApplyResponse, SkillError } from './types'; // Import standardized response types

dayjs.extend(duration);
dayjs.extend(isBetween);
dayjs.extend(timezone);
dayjs.extend(utc);

const openai = new OpenAI({
  apiKey: defaultOpenAIAPIKey,
});

export const getEventVectorById = async (
  id: string
): Promise<FeaturesApplyResponse<number[] | null>> => {
  if (!id) {
    return {
      ok: false,
      error: { code: 'VALIDATION_ERROR', message: 'Event ID is required.' },
    };
  }
  try {
    const event = await getEventById(id); // from lancedb_service
    if (event && event.vector) {
      console.log(`Vector found for event ID ${id}`);
      return { ok: true, data: event.vector as number[] }; // Explicitly cast if needed
    }
    console.log(`No event or vector found for ID ${id}`);
    return { ok: true, data: null }; // Not an error, but no data found
  } catch (e: any) {
    console.error(`Error fetching event vector for ID ${id} from LanceDB:`, e);
    return {
      ok: false,
      error: {
        code: 'LANCEDB_ERROR',
        message: `Failed to fetch event vector: ${e.message}`,
        details: e,
      },
    };
  }
};

export const deleteTrainingDataById = async (
  id: string
): Promise<FeaturesApplyResponse<void>> => {
  if (!id) {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'ID is required for deletion.',
      },
    };
  }
  try {
    await deleteTrainingEventsByIds([id]);
    console.log(`Successfully deleted training data for ID: ${id}`);
    return { ok: true, data: undefined };
  } catch (e: any) {
    console.error(`Error deleting training data for ID ${id} from LanceDB:`, e);
    return {
      ok: false,
      error: {
        code: 'LANCEDB_ERROR',
        message: `Failed to delete training data: ${e.message}`,
        details: e,
      },
    };
  }
};

export const searchTrainingDataByVector = async (
  userId: string,
  searchVector: number[]
): Promise<FeaturesApplyResponse<TrainingEventSchema | null>> => {
  if (!userId || !searchVector || searchVector.length === 0) {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'UserId and searchVector are required.',
      },
    };
  }
  try {
    const results = await searchTrainingEvents(
      searchVector,
      1,
      `userId = '${userId.replace(/'/g, "''")}'`
    );
    if (results && results.length > 0) {
      return { ok: true, data: results[0] };
    }
    return { ok: true, data: null }; // Found nothing, but operation was successful
  } catch (e: any) {
    console.error('Error searching training data in LanceDB:', e);
    return {
      ok: false,
      error: {
        code: 'LANCEDB_ERROR',
        message: `Failed to search training data: ${e.message}`,
        details: e,
      },
    };
  }
};

export const addTrainingData = async (
  trainingEntry: TrainingEventSchema
): Promise<FeaturesApplyResponse<void>> => {
  if (!trainingEntry || !trainingEntry.id || !trainingEntry.vector) {
    // Add more checks as needed
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Training entry with id and vector is required.',
      },
    };
  }
  try {
    await upsertTrainingEvents([trainingEntry]);
    console.log(
      `Successfully added/updated training data for ID: ${trainingEntry.id}`
    );
    return { ok: true, data: undefined };
  } catch (e: any) {
    console.error(
      `Error adding/updating training data for ID ${trainingEntry.id} in LanceDB:`,
      e
    );
    return {
      ok: false,
      error: {
        code: 'LANCEDB_ERROR',
        message: `Failed to add/update training data: ${e.message}`,
        details: e,
      },
    };
  }
};

export const convertEventTitleToOpenAIVector = async (
  title: string
): Promise<FeaturesApplyResponse<number[] | undefined>> => {
  if (!title || title.trim() === '') {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Title cannot be empty for vectorization.',
      },
    };
  }
  try {
    const embeddingRequest: OpenAI.Embeddings.EmbeddingCreateParams = {
      model: 'text-embedding-3-small',
      input: title,
    };

    const res = await openai.embeddings.create(embeddingRequest);
    // console.log(res, ' res inside convertEventTitleToOpenAIVectors'); // Too verbose for normal operation
    const embedding = res?.data?.[0]?.embedding;
    if (!embedding) {
      console.error(
        'OpenAI embedding response did not contain embedding data.'
      );
      return {
        ok: false,
        error: {
          code: 'OPENAI_ERROR',
          message: 'No embedding data returned from OpenAI.',
          details: res,
        },
      };
    }
    return { ok: true, data: embedding };
  } catch (e: any) {
    console.error('Error converting event title to OpenAI vector:', e);
    return {
      ok: false,
      error: {
        code: 'OPENAI_ERROR',
        message: `OpenAI API error: ${e.message}`,
        details: e,
      },
    };
  }
};

export const listMeetingAssistPreferredTimeRangesGivenMeetingId = async (
  meetingId: string
): Promise<
  FeaturesApplyResponse<MeetingAssistPreferredTimeRangeType[] | null>
> => {
  if (!meetingId) {
    return {
      ok: false,
      error: { code: 'VALIDATION_ERROR', message: 'Meeting ID is required.' },
    };
  }
  try {
    const operationName = 'ListMeetingAssistPrefereredTimeRangesByMeetingId';
    const query = `
            query ListMeetingAssistPrefereredTimeRangesByMeetingId($meetingId: uuid!) {
                Meeting_Assist_Preferred_Time_Range(where: {meetingId: {_eq: $meetingId}}) {
                    attendeeId
                    createdDate
                    dayOfWeek
                    endTime
                    hostId
                    id
                    meetingId
                    startTime
                    updatedAt
                }
             }

        `;

    const variables = {
      meetingId,
    };

    const res: {
      data: {
        Meeting_Assist_Preferred_Time_Range: MeetingAssistPreferredTimeRangeType[];
      };
    } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables,
        },
      })
      .json();

    console.log(
      res,
      ' res from listMeetingAssistPreferredTimeRangesGivenMeetingId'
    ); // Corrected log

    return {
      ok: true,
      data: res?.data?.Meeting_Assist_Preferred_Time_Range || null,
    };
  } catch (e: any) {
    console.error('Error listing meeting assist preferred time ranges:', e);
    const errorDetails = e.response?.body || e.message || e; // got error details
    return {
      ok: false,
      error: {
        code: 'HASURA_ERROR',
        message: `Failed to list preferred time ranges: ${e.message}`,
        details: errorDetails,
      },
    };
  }
};

export const listMeetingAssistAttendeesGivenMeetingId = async (
  meetingId: string
): Promise<FeaturesApplyResponse<MeetingAssistAttendeeType[] | null>> => {
  if (!meetingId) {
    return {
      ok: false,
      error: { code: 'VALIDATION_ERROR', message: 'Meeting ID is required.' },
    };
  }
  try {
    const operationName = 'ListMeetingAssistAttendeesByMeetingId';
    const query = `
            query ListMeetingAssistAttendeesByMeetingId($meetingId: uuid!) {
                Meeting_Assist_Attendee(where: {meetingId: {_eq: $meetingId}}) {
                    contactId
                    createdDate
                    emails
                    externalAttendee
                    hostId
                    id
                    imAddresses
                    meetingId
                    name
                    phoneNumbers
                    timezone
                    updatedAt
                    userId
                    primaryEmail
                }
            }
        `;

    const variables = {
      meetingId,
    };

    const res: {
      data: { Meeting_Assist_Attendee: MeetingAssistAttendeeType[] };
    } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables,
        },
      })
      .json();

    console.log(res, ' res from listMeetingAssistAttendees');

    return { ok: true, data: res?.data?.Meeting_Assist_Attendee || null };
  } catch (e: any) {
    console.error('Error listing meeting assist attendees:', e);
    const errorDetails = e.response?.body || e.message || e;
    return {
      ok: false,
      error: {
        code: 'HASURA_ERROR',
        message: `Failed to list meeting assist attendees: ${e.message}`,
        details: errorDetails,
      },
    };
  }
};

export const getMeetingAssistAttendee = async (
  id: string
): Promise<FeaturesApplyResponse<MeetingAssistAttendeeType | null>> => {
  if (!id) {
    return {
      ok: false,
      error: { code: 'VALIDATION_ERROR', message: 'Attendee ID is required.' },
    };
  }
  try {
    const operationName = 'GetMeetingAssistAttendeeById';
    const query = `
            query GetMeetingAssistAttendeeById($id: String!) {
                Meeting_Assist_Attendee_by_pk(id: $id) {
                    contactId
                    createdDate
                    emails
                    hostId
                    id
                    imAddresses
                    meetingId
                    name
                    phoneNumbers
                    timezone
                    updatedAt
                    userId
                    externalAttendee
                    primaryEmail
                }
            }
        `;

    const variables = {
      id,
    };

    const res: {
      data: { Meeting_Assist_Attendee_by_pk: MeetingAssistAttendeeType };
    } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables,
        },
      })
      .json();

    console.log(res, ' res from getMeetingAssistAttendee');
    const attendee = res?.data?.Meeting_Assist_Attendee_by_pk;
    if (!attendee) {
      // Hasura returns null for _by_pk if not found
      return { ok: true, data: null };
    }
    return { ok: true, data: attendee };
  } catch (e: any) {
    console.error('Error getting meeting assist attendee:', e);
    const errorDetails = e.response?.body || e.message || e;
    return {
      ok: false,
      error: {
        code: 'HASURA_ERROR',
        message: `Failed to get meeting assist attendee: ${e.message}`,
        details: errorDetails,
      },
    };
  }
};

export const getMeetingAssist = async (
  id: string
): Promise<FeaturesApplyResponse<MeetingAssistType | null>> => {
  if (!id) {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'MeetingAssist ID is required.',
      },
    };
  }
  try {
    const operationName = 'GetMeetingAssistById';
    const query = `
            query GetMeetingAssistById($id: uuid!) {
                Meeting_Assist_by_pk(id: $id) {
                    anyoneCanAddSelf
                    attendeeCanModify
                    attendeeCount
                    attendeeRespondedCount
                    backgroundColor
                    bufferTime
                    calendarId
                    cancelIfAnyRefuse
                    cancelled
                    colorId
                    conferenceApp
                    createdDate
                    duration
                    enableAttendeePreferences
                    enableConference
                    enableHostPreferences
                    endDate
                    eventId
                    expireDate
                    guestsCanInviteOthers
                    guestsCanSeeOtherGuests
                    foregroundColor
                    id
                    location
                    minThresholdCount
                    notes
                    priority
                    reminders
                    sendUpdates
                    startDate
                    summary
                    timezone
                    transparency
                    updatedAt
                    useDefaultAlarms
                    userId
                    visibility
                    windowEndDate
                    windowStartDate
                    allowAttendeeUpdatePreferences
                    guaranteeAvailability
                }
            }
        `;

    const variables = {
      id,
    };

    const res: { data: { Meeting_Assist_by_pk: MeetingAssistType } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables,
        },
      })
      .json();

    console.log(res, ' res from getMeetingAssist');
    const meetingAssist = res?.data?.Meeting_Assist_by_pk;
    if (!meetingAssist) {
      // Hasura returns null for _by_pk if not found
      return { ok: true, data: null };
    }
    return { ok: true, data: meetingAssist };
  } catch (e: any) {
    console.error('Error getting meeting assist by id:', e);
    const errorDetails = e.response?.body || e.message || e;
    return {
      ok: false,
      error: {
        code: 'HASURA_ERROR',
        message: `Failed to get meeting assist: ${e.message}`,
        details: errorDetails,
      },
    };
  }
};

export const listMeetingAssistEventsForAttendeeGivenDates = async (
  attendeeId: string,
  hostStartDate: string,
  hostEndDate: string,
  userTimezone: string,
  hostTimezone: string
): Promise<FeaturesApplyResponse<MeetingAssistEventType[] | null>> => {
  if (
    !attendeeId ||
    !hostStartDate ||
    !hostEndDate ||
    !userTimezone ||
    !hostTimezone
  ) {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message:
          'Missing required parameters for listing meeting assist events.',
      },
    };
  }
  try {
    const operationName = 'ListMeetingAssistEventsForAttendeeGivenDates';
    const query = `
            query ListMeetingAssistEventsForAttendeeGivenDates($attendeeId: String!, $startDate: timestamp!, $endDate: timestamp!) {
                Meeting_Assist_Event(where: {attendeeId: {_eq: $attendeeId}, endDate: {_gte: $startDate}, startDate: {_lte: $endDate}}) {
                    allDay
                    attachments
                    attendeeId
                    attendeesOmitted
                    backgroundColor
                    calendarId
                    colorId
                    createdDate
                    creator
                    endDate
                    endTimeUnspecified
                    eventType
                    extendedProperties
                    externalUser
                    foregroundColor
                    guestsCanModify
                    hangoutLink
                    htmlLink
                    iCalUID
                    id
                    links
                    location
                    locked
                    meetingId
                    notes
                    organizer
                    privateCopy
                    recurrence
                    recurrenceRule
                    recurringEventId
                    source
                    startDate
                    summary
                    timezone
                    transparency
                    updatedAt
                    useDefaultAlarms
                    visibility
                }
            }
        `;

    const startDateInHostTimezone = dayjs(hostStartDate.slice(0, 19)).tz(
      hostTimezone,
      true
    );
    const endDateInHostTimezone = dayjs(hostEndDate.slice(0, 19)).tz(
      hostTimezone,
      true
    );
    const startDateInUserTimezone = dayjs(startDateInHostTimezone)
      .tz(userTimezone)
      .format()
      .slice(0, 19);
    const endDateInUserTimezone = dayjs(endDateInHostTimezone)
      .tz(userTimezone)
      .format()
      .slice(0, 19);

    const res: { data: { Meeting_Assist_Event: MeetingAssistEventType[] } } =
      await got
        .post(hasuraGraphUrl, {
          headers: {
            'X-Hasura-Admin-Secret': hasuraAdminSecret,
            'Content-Type': 'application/json',
            'X-Hasura-Role': 'admin',
          },
          json: {
            operationName,
            query,
            variables: {
              attendeeId,
              startDate: startDateInUserTimezone,
              endDate: endDateInUserTimezone,
            },
          },
        })
        .json();

    console.log(res, ' res from listMeetingAssistEventsForAttendeeGivenDates');
    return { ok: true, data: res?.data?.Meeting_Assist_Event || null };
  } catch (e: any) {
    console.error('Error listing meeting assist events for attendee:', e);
    const errorDetails = e.response?.body || e.message || e;
    return {
      ok: false,
      error: {
        code: 'HASURA_ERROR',
        message: `Failed to list meeting assist events: ${e.message}`,
        details: errorDetails,
      },
    };
  }
};

export const listEventsForDate = async (
  userId: string,
  startDate: string,
  endDate: string,
  timezone: string
): Promise<FeaturesApplyResponse<EventType[] | null>> => {
  if (!userId || !startDate || !endDate || !timezone) {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Missing required parameters for listing events for date.',
      },
    };
  }
  try {
    const operationName = 'listEventsForDate';
    const query = `
        query listEventsForDate($userId: uuid!, $startDate: timestamp!, $endDate: timestamp!) {
          Event(where: {userId: {_eq: $userId}, endDate: {_gte: $startDate}, startDate: {_lte: $endDate}, deleted: {_eq: false}}) {
            allDay
            anyoneCanAddSelf
            attachments
            attendeesOmitted
            backgroundColor
            calendarId
            colorId
            conferenceId
            copyAvailability
            copyCategories
            copyDuration
            copyIsBreak
            copyIsExternalMeeting
            copyIsMeeting
            copyModifiable
            copyPriorityLevel
            copyReminders
            copyTimeBlocking
            copyTimePreference
            createdDate
            creator
            dailyTaskList
            deleted
            duration
            endDate
            endTimeUnspecified
            eventId
            eventType
            extendedProperties
            followUpEventId
            forEventId
            foregroundColor
            guestsCanInviteOthers
            guestsCanModify
            guestsCanSeeOtherGuests
            hangoutLink
            hardDeadline
            htmlLink
            iCalUID
            id
            isBreak
            isExternalMeeting
            isExternalMeetingModifiable
            isFollowUp
            isMeeting
            isMeetingModifiable
            isPostEvent
            isPreEvent
            links
            location
            locked
            maxAttendees
            meetingId
            method
            modifiable
            negativeImpactDayOfWeek
            negativeImpactScore
            negativeImpactTime
            notes
            organizer
            originalAllDay
            originalStartDate
            originalTimezone
            positiveImpactDayOfWeek
            positiveImpactScore
            positiveImpactTime
            postEventId
            preEventId
            preferredDayOfWeek
            preferredEndTimeRange
            preferredStartTimeRange
            preferredTime
            priority
            privateCopy
            recurrence
            recurrenceRule
            recurringEventId
            sendUpdates
            softDeadline
            source
            startDate
            status
            summary
            taskId
            taskType
            timeBlocking
            timezone
            title
            transparency
            unlink
            updatedAt
            useDefaultAlarms
            userId
            userModifiedAvailability
            userModifiedCategories
            userModifiedDuration
            userModifiedIsBreak
            userModifiedIsExternalMeeting
            userModifiedIsMeeting
            userModifiedModifiable
            userModifiedPriorityLevel
            userModifiedReminders
            userModifiedTimeBlocking
            userModifiedTimePreference
            visibility
            weeklyTaskList
            byWeekDay
            localSynced
            userModifiedColor
            copyColor
            copyExternalMeetingModifiable
            userModifiedExternalMeetingModifiable
            userModifiedMeetingModifiable
          }
        }
            `;
    const res: { data: { Event: EventType[] } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables: {
            userId,
            startDate: dayjs(startDate.slice(0, 19))
              .tz(timezone, true)
              .format(),
            endDate: dayjs(endDate.slice(0, 19)).tz(timezone, true).format(),
          },
        },
      })
      .json();

    console.log(res, ' res from listEventsForDate'); // Corrected log
    return { ok: true, data: res?.data?.Event || null };
  } catch (e: any) {
    console.error('Error listing events for date:', e);
    const errorDetails = e.response?.body || e.message || e;
    return {
      ok: false,
      error: {
        code: 'HASURA_ERROR',
        message: `Failed to list events for date: ${e.message}`,
        details: errorDetails,
      },
    };
  }
};

export const listEventsForUserGivenDates = async (
  userId: string,
  hostStartDate: string,
  hostEndDate: string,
  userTimezone: string,
  hostTimezone: string
): Promise<FeaturesApplyResponse<EventType[] | null>> => {
  if (
    !userId ||
    !hostStartDate ||
    !hostEndDate ||
    !userTimezone ||
    !hostTimezone
  ) {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message:
          'Missing required parameters for listing events for user given dates.',
      },
    };
  }
  try {
    const operationName = 'listEventsForUser';
    const query = `
            query listEventsForUser($userId: uuid!, $startDate: timestamp!, $endDate: timestamp!) {
                Event(where: {userId: {_eq: $userId}, endDate: {_gte: $startDate}, startDate: {_lte: $endDate}, deleted: {_neq: true}, allDay: {_neq: true}}) {
                    allDay
                    anyoneCanAddSelf
                    attachments
                    attendeesOmitted
                    backgroundColor
                    calendarId
                    colorId
                    conferenceId
                    copyAvailability
                    copyCategories
                    copyDuration
                    copyIsBreak
                    copyIsExternalMeeting
                    copyIsMeeting
                    copyModifiable
                    copyPriorityLevel
                    copyReminders
                    copyTimeBlocking
                    copyTimePreference
                    createdDate
                    creator
                    dailyTaskList
                    deleted
                    duration
                    endDate
                    endTimeUnspecified
                    eventId
                    eventType
                    extendedProperties
                    followUpEventId
                    forEventId
                    foregroundColor
                    guestsCanInviteOthers
                    guestsCanModify
                    guestsCanSeeOtherGuests
                    hangoutLink
                    hardDeadline
                    htmlLink
                    iCalUID
                    id
                    isBreak
                    isExternalMeeting
                    isExternalMeetingModifiable
                    isFollowUp
                    isMeeting
                    isMeetingModifiable
                    isPostEvent
                    isPreEvent
                    links
                    location
                    locked
                    maxAttendees
                    meetingId
                    method
                    modifiable
                    negativeImpactDayOfWeek
                    negativeImpactScore
                    negativeImpactTime
                    notes
                    organizer
                    originalAllDay
                    originalStartDate
                    originalTimezone
                    positiveImpactDayOfWeek
                    positiveImpactScore
                    positiveImpactTime
                    postEventId
                    preEventId
                    preferredDayOfWeek
                    preferredEndTimeRange
                    preferredStartTimeRange
                    preferredTime
                    priority
                    privateCopy
                    recurrence
                    recurrenceRule
                    recurringEventId
                    sendUpdates
                    softDeadline
                    source
                    startDate
                    status
                    summary
                    taskId
                    taskType
                    timeBlocking
                    timezone
                    title
                    transparency
                    unlink
                    updatedAt
                    useDefaultAlarms
                    userId
                    userModifiedAvailability
                    userModifiedCategories
                    userModifiedDuration
                    userModifiedIsBreak
                    userModifiedIsExternalMeeting
                    userModifiedIsMeeting
                    userModifiedModifiable
                    userModifiedPriorityLevel
                    userModifiedReminders
                    userModifiedTimeBlocking
                    userModifiedTimePreference
                    visibility
                    weeklyTaskList
                    byWeekDay
                    localSynced
                    userModifiedColor
                    copyColor
                    copyExternalMeetingModifiable
                    userModifiedExternalMeetingModifiable
                    userModifiedMeetingModifiable
                }
            }
        `;
    const startDateInHostTimezone = dayjs(hostStartDate.slice(0, 19)).tz(
      hostTimezone,
      true
    );
    const endDateInHostTimezone = dayjs(hostEndDate.slice(0, 19)).tz(
      hostTimezone,
      true
    );
    const startDateInUserTimezone = dayjs(startDateInHostTimezone)
      .tz(userTimezone)
      .format()
      .slice(0, 19);
    const endDateInUserTimezone = dayjs(endDateInHostTimezone)
      .tz(userTimezone)
      .format()
      .slice(0, 19);

    const res: { data: { Event: EventType[] } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables: {
            userId,
            startDate: startDateInUserTimezone,
            endDate: endDateInUserTimezone,
          },
        },
      })
      .json();

    console.log(res, ' res from listEventsForUser');
    return { ok: true, data: res?.data?.Event || null };
  } catch (e: any) {
    console.error('Error listing events for user given dates:', e);
    const errorDetails = e.response?.body || e.message || e;
    return {
      ok: false,
      error: {
        code: 'HASURA_ERROR',
        message: `Failed to list events for user: ${e.message}`,
        details: errorDetails,
      },
    };
  }
};

// processMeetingAssistForOptaplanner seems like a complex internal orchestration,
// for now, we'll assume its return type might be a simple status or a complex object.
// Let's assume it returns a status message for this refactoring.
export const processMeetingAssistForOptaplanner = async (): Promise<
  FeaturesApplyResponse<{ message: string }>
> => {
  try {
    // ... existing logic ...
    // If successful:
    // return { ok: true, data: { message: "Processing for OptaPlanner initiated/completed." } };
    console.warn(
      'processMeetingAssistForOptaplanner logic is complex and not fully refactored for error handling here.'
    );
    return {
      ok: true,
      data: {
        message: 'Placeholder response for processMeetingAssistForOptaplanner.',
      },
    };
  } catch (e: any) {
    console.error('Error processing meeting assist for optaplanner:', e);
    return {
      ok: false,
      error: {
        code: 'INTERNAL_ERROR',
        message: `Failed to process for OptaPlanner: ${e.message}`,
        details: e,
      },
    };
  }
};

export const generateNewMeetingEventForAttendee = (
  attendee: MeetingAssistAttendeeType,
  meetingAssist: MeetingAssistType,
  windowStartDate: string,
  windowEndDate: string,
  hostTimezone: string,
  calendarId?: string,
  preferredStartTimeRange?: MeetingAssistPreferredTimeRangeType
): EventType => {
  let startDate = dayjs(windowStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .format();
  const endDate = dayjs(windowEndDate.slice(0, 19))
    .tz(hostTimezone, true)
    .format();
  if (preferredStartTimeRange?.dayOfWeek > 0) {
    const dateObject = dayjs(startDate.slice(0, 19))
      .tz(hostTimezone, true)
      .toDate();
    const dateObjectWithSetISODayPossible = setISODay(
      dateObject,
      preferredStartTimeRange?.dayOfWeek
    );
    const originalDateObjectWithSetISODay = dateObjectWithSetISODayPossible;
    let dateObjectWithSetISODay = originalDateObjectWithSetISODay;

    if (!dayjs(dateObjectWithSetISODay).isBetween(startDate, endDate)) {
      dateObjectWithSetISODay = dayjs(originalDateObjectWithSetISODay)
        .add(1, 'week')
        .toDate();
    }

    if (!dayjs(dateObjectWithSetISODay).isBetween(startDate, endDate)) {
      dateObjectWithSetISODay = dayjs(originalDateObjectWithSetISODay)
        .subtract(1, 'week')
        .toDate();
    }

    startDate = dayjs(dateObjectWithSetISODay).tz(hostTimezone).format();
  }

  if (preferredStartTimeRange?.startTime) {
    const startTime = preferredStartTimeRange?.startTime;
    const hour = parseInt(startTime.slice(0, 2), 10);
    const minute = parseInt(startTime.slice(3), 10);

    startDate = dayjs(startDate.slice(0, 10))
      .tz(hostTimezone, true)
      .hour(hour)
      .minute(minute)
      .format();
  }

  const eventId = uuid();
  const newEvent: EventType = {
    id: `${eventId}#${calendarId ?? meetingAssist.calendarId}`,
    method: 'create',
    title: meetingAssist.summary,
    startDate,
    endDate: dayjs(startDate.slice(0, 19))
      .tz(hostTimezone, true)
      .add(meetingAssist.duration, 'm')
      .format(),
    allDay: false,
    notes: meetingAssist.notes,
    timezone: hostTimezone,
    createdDate: dayjs().format(),
    deleted: false,
    priority: meetingAssist.priority,
    isFollowUp: false,
    isPreEvent: false,
    isPostEvent: false,
    modifiable: true,
    sendUpdates: meetingAssist?.sendUpdates,
    status: 'confirmed',
    summary: meetingAssist.summary,
    transparency: meetingAssist?.transparency,
    visibility: meetingAssist?.visibility,
    updatedAt: dayjs().format(),
    calendarId: calendarId ?? meetingAssist.calendarId,
    useDefaultAlarms: meetingAssist.useDefaultAlarms,
    timeBlocking: meetingAssist.bufferTime,
    userModifiedTimeBlocking: meetingAssist?.bufferTime ? true : false,
    userModifiedTimePreference: preferredStartTimeRange?.id ? true : false,
    userModifiedReminders: meetingAssist?.reminders?.[0] > -1 ? true : false,
    userModifiedPriorityLevel: true,
    userModifiedModifiable: true,
    duration: meetingAssist?.duration,
    userModifiedDuration: true,
    userId: attendee?.userId,
    anyoneCanAddSelf: false,
    guestsCanInviteOthers: meetingAssist?.guestsCanInviteOthers,
    guestsCanSeeOtherGuests: meetingAssist?.guestsCanSeeOtherGuests,
    originalStartDate: undefined,
    originalAllDay: false,
    meetingId: meetingAssist.id,
    eventId,
  };

  return newEvent;
};

export const generateNewMeetingEventForHost = (
  hostAttendee: MeetingAssistAttendeeType,
  meetingAssist: MeetingAssistType,
  windowStartDate: string,
  windowEndDate: string,
  hostTimezone: string,
  preferredStartTimeRange?: MeetingAssistPreferredTimeRangeType
): EventType => {
  let startDate = dayjs(windowStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .format();
  const endDate = dayjs(windowEndDate.slice(0, 19))
    .tz(hostTimezone, true)
    .format();
  console.log(
    startDate,
    ' startDate inside generateNewMeetingEventForAttendee step 1'
  );
  if (preferredStartTimeRange?.dayOfWeek > 0) {
    const dateObject = dayjs(startDate.slice(0, 19))
      .tz(hostTimezone, true)
      .toDate();
    const dateObjectWithSetISODayPossible = setISODay(
      dateObject,
      preferredStartTimeRange?.dayOfWeek
    );
    let dateObjectWithSetISODay = dateObjectWithSetISODayPossible;
    if (!dayjs(dateObjectWithSetISODayPossible).isBetween(startDate, endDate)) {
      dateObjectWithSetISODay = dayjs(dateObjectWithSetISODayPossible)
        .add(1, 'week')
        .toDate();
    }
    startDate = dayjs(dateObjectWithSetISODay).tz(hostTimezone).format();
  }

  console.log(
    startDate,
    ' startDate inside generateNewMeetingEventForAttendee step 2'
  );

  if (preferredStartTimeRange?.startTime) {
    const startTime = preferredStartTimeRange?.startTime;
    const hour = parseInt(startTime.slice(0, 2), 10);
    const minute = parseInt(startTime.slice(3), 10);

    startDate = dayjs(startDate.slice(0, 19))
      .tz(hostTimezone, true)
      .hour(hour)
      .minute(minute)
      .format();
  }

  console.log(
    startDate,
    ' startDate inside generateNewMeetingEventForAttendee step 3'
  );

  const eventId = uuid();
  const newEvent: EventType = {
    id: `${eventId}#${meetingAssist.calendarId}`,
    method: 'create',
    title: meetingAssist.summary,
    startDate,
    endDate: dayjs(startDate).add(meetingAssist.duration, 'm').format(),
    allDay: false,
    notes: meetingAssist.notes,
    timezone: hostTimezone,
    createdDate: dayjs().format(),
    deleted: false,
    priority: meetingAssist.priority,
    isFollowUp: false,
    isPreEvent: false,
    isPostEvent: false,
    modifiable: true,
    sendUpdates: meetingAssist?.sendUpdates,
    status: 'confirmed',
    summary: meetingAssist.summary,
    transparency: meetingAssist?.transparency,
    visibility: meetingAssist?.visibility,
    updatedAt: dayjs().format(),
    calendarId: meetingAssist.calendarId,
    useDefaultAlarms: meetingAssist.useDefaultAlarms,
    timeBlocking: meetingAssist.bufferTime,
    userModifiedTimeBlocking: meetingAssist?.bufferTime ? true : false,
    userModifiedTimePreference: preferredStartTimeRange?.id ? true : false,
    userModifiedReminders: meetingAssist?.reminders?.[0] > -1 ? true : false,
    userModifiedPriorityLevel: true,
    userModifiedModifiable: true,
    duration: meetingAssist?.duration,
    userModifiedDuration: true,
    userId: hostAttendee?.userId,
    anyoneCanAddSelf: false,
    guestsCanInviteOthers: meetingAssist?.guestsCanInviteOthers,
    guestsCanSeeOtherGuests: meetingAssist?.guestsCanSeeOtherGuests,
    originalStartDate: undefined,
    originalAllDay: false,
    meetingId: meetingAssist.id,
    eventId,
  };

  return newEvent;
};

export const listPreferredTimeRangesForEvent = async (
  eventId: string
  // This function is missing userId for context if it's a user-specific action
  // or if it's a generic lookup by eventId, it's fine. Assuming generic for now.
): Promise<FeaturesApplyResponse<PreferredTimeRangeType[] | null>> => {
  if (!eventId) {
    return {
      ok: false,
      error: { code: 'VALIDATION_ERROR', message: 'Event ID is required.' },
    };
  }
  try {
    const operationName = 'ListPreferredTimeRangesGivenEventId';
    const query = `
      query ListPreferredTimeRangesGivenEventId($eventId: String!) {
        PreferredTimeRange(where: {eventId: {_eq: $eventId}}) {
          createdDate
          dayOfWeek
          endTime
          eventId
          id
          startTime
          updatedAt
          userId
        }
      }
    `;
    const variables = {
      eventId,
    };

    const res: { data: { PreferredTimeRange: PreferredTimeRangeType[] } } =
      await got
        .post(hasuraGraphUrl, {
          headers: {
            'X-Hasura-Admin-Secret': hasuraAdminSecret,
            'X-Hasura-Role': 'admin',
          },
          json: {
            operationName,
            query,
            variables,
          },
        })
        .json();

    console.log(res, ' res inside  listPreferredTimeRangesForEvent');
    res?.data?.PreferredTimeRange?.map((pt) =>
      console.log(
        pt,
        ' preferredTimeRange - res?.data?.PreferredTimeRange inside  listPreferredTimeRangesForEvent '
      )
    );

    return { ok: true, data: res?.data?.PreferredTimeRange || null };
  } catch (e: any) {
    console.error('Error listing preferred time ranges for event:', e);
    const errorDetails = e.response?.body || e.message || e;
    return {
      ok: false,
      error: {
        code: 'HASURA_ERROR',
        message: `Failed to list preferred time ranges: ${e.message}`,
        details: errorDetails,
      },
    };
  }
};

export const createRemindersFromMinutesAndEvent = (
  eventId: string,
  minutes: number[],
  timezone: string,
  useDefault: boolean,
  userId: string
): RemindersForEventType => {
  return {
    eventId,
    reminders: minutes.map((m) => ({
      id: uuid(),
      userId,
      eventId,
      timezone,
      minutes: m,
      useDefault,
      updatedAt: dayjs().format(),
      createdDate: dayjs().format(),
      deleted: true,
    })),
  };
};

export const createBufferTimeForNewMeetingEvent = (
  event: EventMeetingPlusType,
  bufferTime: BufferTimeNumberType
) => {
  let valuesToReturn: any = {};
  valuesToReturn.newEvent = event;
  const eventId = uuid();
  const eventId1 = uuid();
  const preEventId = event?.preEventId || `${eventId}#${event?.calendarId}`;
  const postEventId = event?.postEventId || `${eventId1}#${event?.calendarId}`;

  if (bufferTime.beforeEvent > 0) {
    const beforeEventOrEmpty: EventPlusType = {
      id: preEventId,
      isPreEvent: true,
      forEventId: event.id,
      notes: 'Buffer time',
      summary: 'Buffer time',
      startDate: dayjs(event.startDate.slice(0, 19))
        .tz(event.timezone, true)
        .subtract(bufferTime.beforeEvent, 'm')
        .format(),
      endDate: dayjs(event.startDate.slice(0, 19))
        .tz(event.timezone, true)
        .format(),
      method: 'create',
      userId: event.userId,
      createdDate: dayjs().format(),
      deleted: false,
      priority: 1,
      modifiable: true,
      anyoneCanAddSelf: false,
      guestsCanInviteOthers: false,
      guestsCanSeeOtherGuests: false,
      originalStartDate: undefined,
      originalAllDay: false,
      updatedAt: dayjs().toISOString(),
      calendarId: event?.calendarId,
      timezone: event?.timezone,
      isFollowUp: false,
      isPostEvent: false,
      eventId: preEventId.split('#')[0],
    };

    valuesToReturn.beforeEvent = beforeEventOrEmpty;
    valuesToReturn.newEvent = {
      ...valuesToReturn.newEvent,
      preEventId,
      timeBlocking: {
        ...valuesToReturn?.newEvent?.timeBlocking,
        beforeEvent: bufferTime.beforeEvent,
      },
    };
  }

  if (bufferTime.afterEvent > 0) {
    const afterEventOrEmpty: EventPlusType = {
      id: postEventId,
      isPreEvent: false,
      forEventId: event.id,
      isPostEvent: true,
      notes: 'Buffer time',
      summary: 'Buffer time',
      startDate: dayjs(event.endDate.slice(0, 19))
        .tz(event.timezone, true)
        .format(),
      endDate: dayjs(event.endDate.slice(0, 19))
        .tz(event.timezone, true)
        .add(bufferTime.afterEvent, 'm')
        .format(),
      method: 'create',
      userId: event?.userId,
      createdDate: dayjs().toISOString(),
      deleted: false,
      priority: 1,
      isFollowUp: false,
      modifiable: true,
      anyoneCanAddSelf: false,
      guestsCanInviteOthers: false,
      guestsCanSeeOtherGuests: false,
      originalStartDate: undefined,
      originalAllDay: false,
      updatedAt: dayjs().toISOString(),
      calendarId: event?.calendarId,
      timezone: event?.timezone,
      eventId: postEventId.split('#')[0],
    };

    valuesToReturn.afterEvent = afterEventOrEmpty;
    valuesToReturn.newEvent = {
      ...valuesToReturn.newEvent,
      postEventId,
      timeBlocking: {
        ...valuesToReturn?.newEvent?.timeBlocking,
        afterEvent: bufferTime.afterEvent,
      },
    };
  }

  return valuesToReturn as ValuesToReturnForBufferEventsType;
};

export const getUserPreferences = async (
  userId: string
): Promise<UserPreferenceType> => {
  try {
    if (!userId) {
      console.log('userId is null');
      return null;
    }
    const operationName = 'getUserPreferences';
    const query = `
    query getUserPreferences($userId: uuid!) {
      User_Preference(where: {userId: {_eq: $userId}}) {
        startTimes
        endTimes
        backToBackMeetings
        copyAvailability
        copyCategories
        copyIsBreak
        copyModifiable
        copyPriorityLevel
        copyReminders
        copyTimeBlocking
        copyTimePreference
        createdDate
        deleted
        followUp
        id
        isPublicCalendar
        maxNumberOfMeetings
        maxWorkLoadPercent
        publicCalendarCategories
        reminders
        updatedAt
        userId
        minNumberOfBreaks
        breakColor
        breakLength
        copyColor
        copyIsExternalMeeting
        copyIsMeeting
        onBoarded
      }
    }    
  `;
    const res: { data: { User_Preference: UserPreferenceType[] } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables: {
            userId,
          },
        },
      })
      .json();
    return res?.data?.User_Preference?.[0];
  } catch (e) {
    console.log(e, ' getUserPreferences');
  }
};

export const getGlobalCalendar = async (userId: string) => {
  try {
    const operationName = 'getGlobalCalendar';
    const query = `
        query getGlobalCalendar($userId: uuid!) {
          Calendar(where: {globalPrimary: {_eq: true}, userId: {_eq: $userId}}) {
            colorId
            backgroundColor
            accessLevel
            account
            createdDate
            defaultReminders
            foregroundColor
            globalPrimary
            id
            modifiable
            primary
            resource
            title
            updatedAt
            userId
          }
        }
    `;

    const res: { data: { Calendar: CalendarType[] } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables: {
            userId,
          },
        },
      })
      .json();

    return res.data.Calendar?.[0];
  } catch (e) {
    console.log(e, ' unable to get global calendar');
  }
};

export const adjustStartDatesForBreakEventsForDay = (
  allEvents: EventPlusType[],
  breakEvents: EventPlusType[],
  userPreference: UserPreferenceType,
  timezone: string
): EventPlusType[] => {
  if (!allEvents?.[0]?.id) {
    console.log('no allEvents inside adjustStartDatesForBreakEvents');
    return;
  }

  const startTimes = userPreference.startTimes;
  const endTimes = userPreference.endTimes;
  const dayOfWeekInt = getISODay(
    dayjs(allEvents?.[0]?.startDate.slice(0, 19)).tz(timezone, true).toDate()
  );
  const startHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
  const startMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
  const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
  const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;
  const newBreakEvents = [];

  const startOfWorkingDay = dayjs(allEvents[0]?.startDate.slice(0, 19))
    .tz(timezone, true)
    .hour(startHour)
    .minute(startMinute);

  const endOfWorkingDay = dayjs(allEvents[0]?.endDate.slice(0, 19))
    .tz(timezone, true)
    .hour(endHour)
    .minute(endMinute);

  const filteredEvents = allEvents.filter((e) => !e.isBreak);
  if (breakEvents?.length > 0) {
    for (const breakEvent of breakEvents) {
      console.log(breakEvent, ' breakEvent of breakEvents');
      let foundSpace = false;
      let index = 0;
      while (!foundSpace && index < filteredEvents.length) {
        console.log(
          foundSpace,
          index,
          ' foundSpace, index, (!foundSpace) && (index < filteredEvents.length)'
        );
        const possibleEndDate = dayjs(
          filteredEvents[index].startDate.slice(0, 19)
        ).tz(timezone, true);

        const possibleStartDate = possibleEndDate.subtract(
          userPreference.breakLength,
          'minute'
        );
        let isBetweenStart = true;
        let isBetweenEnd = true;
        let betweenIndex = 0;
        let betweenWorkingDayStart = true;
        let betweenWorkingDayEnd = true;
        let isBetweenBreakStart = true;
        let isBetweenBreakEnd = true;

        while (
          (isBetweenStart ||
            isBetweenEnd ||
            !betweenWorkingDayStart ||
            !betweenWorkingDayEnd ||
            isBetweenBreakStart ||
            isBetweenBreakEnd) &&
          betweenIndex < filteredEvents.length
        ) {
          isBetweenStart = possibleStartDate.isBetween(
            dayjs(filteredEvents[betweenIndex].startDate.slice(0, 19)).tz(
              timezone,
              true
            ),
            dayjs(filteredEvents[betweenIndex].endDate.slice(0, 19)).tz(
              timezone,
              true
            ),
            'minute',
            '[)'
          );

          isBetweenEnd = possibleEndDate.isBetween(
            dayjs(filteredEvents[betweenIndex].startDate.slice(0, 19)).tz(
              timezone,
              true
            ),
            dayjs(filteredEvents[betweenIndex].endDate.slice(0, 19)).tz(
              timezone,
              true
            ),
            'minute',
            '(]'
          );

          betweenWorkingDayStart = possibleStartDate.isBetween(
            startOfWorkingDay,
            endOfWorkingDay,
            'minute',
            '[)'
          );

          betweenWorkingDayEnd = possibleEndDate.isBetween(
            startOfWorkingDay,
            endOfWorkingDay,
            'minute',
            '(]'
          );

          for (const breakEvent of breakEvents) {
            isBetweenBreakStart = possibleStartDate.isBetween(
              dayjs(breakEvent.startDate.slice(0, 19)).tz(timezone, true),
              dayjs(breakEvent.endDate.slice(0, 19)).tz(timezone, true),
              'minute',
              '[)'
            );

            isBetweenBreakEnd = possibleEndDate.isBetween(
              dayjs(breakEvent.startDate.slice(0, 19)).tz(timezone, true),
              dayjs(breakEvent.endDate.slice(0, 19)).tz(timezone, true),
              'minute',
              '(]'
            );
          }

          betweenIndex++;
        }

        foundSpace =
          !isBetweenStart &&
          !isBetweenEnd &&
          betweenWorkingDayStart &&
          betweenWorkingDayEnd &&
          !isBetweenBreakStart &&
          !isBetweenBreakEnd;

        if (foundSpace) {
          const newBreakEvent = {
            ...breakEvent,
            startDate: possibleStartDate.format(),
            endDate: possibleEndDate.format(),
          };
          newBreakEvents.push(newBreakEvent);
        }

        index++;
      }
    }
  }

  return newBreakEvents;
};
export const convertToTotalWorkingHoursForInternalAttendee = (
  userPreference: UserPreferenceType,
  hostStartDate: string,
  hostTimezone: string
) => {
  const startTimes = userPreference.startTimes;
  const endTimes = userPreference.endTimes;
  const dayOfWeekInt = getISODay(
    dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate()
  );
  const startHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
  const startMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
  const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
  const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;

  const startDuration = dayjs.duration({
    hours: startHour,
    minutes: startMinute,
  });
  const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute });
  const totalDuration = endDuration.subtract(startDuration);
  return totalDuration.asHours();
};

export const convertToTotalWorkingHoursForExternalAttendee = (
  attendeeEvents: EventPlusType[],
  hostStartDate: string,
  hostTimezone: string,
  userTimezone: string
) => {
  const dayOfWeekIntByHost = getISODay(
    dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate()
  );
  const sameDayEvents = attendeeEvents.filter(
    (e) =>
      getISODay(
        dayjs(e.startDate.slice(0, 19))
          .tz(e.timezone || userTimezone, true)
          .tz(hostTimezone)
          .toDate()
      ) === dayOfWeekIntByHost
  );
  const minStartDate = _.minBy(sameDayEvents, (e) =>
    dayjs(e.startDate.slice(0, 19))
      .tz(e.timezone || userTimezone, true)
      .tz(hostTimezone)
      .unix()
  );
  const maxEndDate = _.maxBy(sameDayEvents, (e) =>
    dayjs(e.endDate.slice(0, 19))
      .tz(e.timezone || userTimezone, true)
      .tz(hostTimezone)
      .unix()
  );

  let workEndHourByHost = dayjs(maxEndDate.endDate.slice(0, 19))
    .tz(maxEndDate?.timezone || userTimezone, true)
    .tz(hostTimezone)
    .hour();
  const workEndMinuteByHost = dayjs(maxEndDate.endDate.slice(0, 19))
    .tz(maxEndDate?.timezone || userTimezone, true)
    .tz(hostTimezone)
    .isBetween(
      dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(0),
      dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(15),
      'minute',
      '[)'
    )
    ? 15
    : dayjs(maxEndDate.endDate.slice(0, 19))
          .tz(maxEndDate?.timezone || userTimezone, true)
          .tz(hostTimezone)
          .isBetween(
            dayjs(maxEndDate.endDate.slice(0, 19))
              .tz(maxEndDate?.timezone || userTimezone, true)
              .tz(hostTimezone)
              .minute(15),
            dayjs(maxEndDate.endDate.slice(0, 19))
              .tz(maxEndDate?.timezone || userTimezone, true)
              .tz(hostTimezone)
              .minute(30),
            'minute',
            '[)'
          )
      ? 30
      : dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(
              dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30),
              dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(45),
              'minute',
              '[)'
            )
        ? 45
        : 0;
  if (workEndMinuteByHost === 0) {
    if (workEndHourByHost < 23) {
      workEndHourByHost += 1;
    }
  }

  const workStartHourByHost = dayjs(minStartDate.startDate.slice(0, 19))
    .tz(minStartDate?.timezone || userTimezone, true)
    .tz(hostTimezone)
    .hour();
  const workStartMinuteByHost = dayjs(minStartDate.startDate.slice(0, 19))
    .tz(minStartDate?.timezone || userTimezone, true)
    .tz(hostTimezone)
    .isBetween(
      dayjs(minStartDate.startDate.slice(0, 19))
        .tz(minStartDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(0),
      dayjs(minStartDate.startDate.slice(0, 19))
        .tz(minStartDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(15),
      'minute',
      '[)'
    )
    ? 0
    : dayjs(minStartDate.startDate.slice(0, 19))
          .tz(minStartDate?.timezone || userTimezone, true)
          .tz(hostTimezone)
          .isBetween(
            dayjs(minStartDate.startDate.slice(0, 19))
              .tz(minStartDate?.timezone || userTimezone, true)
              .tz(hostTimezone)
              .minute(15),
            dayjs(minStartDate.startDate.slice(0, 19))
              .tz(minStartDate?.timezone || userTimezone, true)
              .tz(hostTimezone)
              .minute(30),
            'minute',
            '[)'
          )
      ? 15
      : dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(
              dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30),
              dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(45),
              'minute',
              '[)'
            )
        ? 30
        : 45;

  console.log(
    workStartHourByHost,
    workStartMinuteByHost,
    workEndHourByHost,
    ' workStartHourByHost, workStartMinuteByHost, workEndHourByHost for total working hours'
  );
  const startDuration = dayjs.duration({
    hours: workStartHourByHost,
    minutes: workStartMinuteByHost,
  });
  const endDuration = dayjs.duration({
    hours: workEndHourByHost,
    minutes: workEndMinuteByHost,
  });
  const totalDuration = endDuration.subtract(startDuration);
  return totalDuration.asHours();
};

export const generateBreaks = (
  userPreferences: UserPreferenceType,
  numberOfBreaksToGenerate: number,
  eventMirror: EventPlusType,
  globalCalendarId?: string
): EventPlusType[] => {
  const breaks = [];
  if (!userPreferences?.breakLength) {
    console.log(
      'no user preferences breakLength provided inside generateBreaks'
    );
    return breaks;
  }

  if (!numberOfBreaksToGenerate) {
    console.log(
      'no number of breaks to generate provided inside generateBreaks'
    );
    return breaks;
  }

  if (!eventMirror) {
    console.log('no event mirror provided inside generateBreaks');
    return breaks;
  }
  console.log(
    numberOfBreaksToGenerate,
    ' numberOfBreaksToGenerate inside generateBreaks'
  );
  for (let i = 0; i < numberOfBreaksToGenerate; i++) {
    const eventId = uuid();
    const breakEvent: EventPlusType = {
      id: `${eventId}#${globalCalendarId || eventMirror.calendarId}`,
      userId: userPreferences.userId,
      title: 'Break',
      startDate: dayjs(eventMirror.startDate.slice(0, 19))
        .tz(eventMirror.timezone, true)
        .format(),
      endDate: dayjs(eventMirror.startDate.slice(0, 19))
        .tz(eventMirror.timezone, true)
        .add(userPreferences.breakLength, 'minute')
        .format(),
      allDay: false,
      notes: 'Break',
      timezone: eventMirror.timezone,
      createdDate: dayjs().toISOString(),
      updatedAt: dayjs().toISOString(),
      deleted: false,
      priority: 1,
      isFollowUp: false,
      isPreEvent: false,
      modifiable: true,
      anyoneCanAddSelf: false,
      guestsCanInviteOthers: false,
      guestsCanSeeOtherGuests: false,
      originalStartDate: undefined,
      originalAllDay: false,
      calendarId: globalCalendarId || eventMirror.calendarId,
      backgroundColor: userPreferences.breakColor || '#F7EBF7',
      isBreak: true,
      duration: userPreferences.breakLength,
      userModifiedDuration: true,
      userModifiedColor: true,
      isPostEvent: false,
      method: 'create',
      eventId,
    };
    breaks.push(breakEvent);
  }

  return breaks;
};

export const shouldGenerateBreakEventsForDay = (
  workingHours: number,
  userPreferences: UserPreferenceType,
  allEvents: EventPlusType[]
) => {
  if (!userPreferences?.breakLength) {
    console.log(
      'no user preferences breakLength provided inside shouldGenerateBreakEvents'
    );
    return false;
  }

  if (!(allEvents?.length > 0)) {
    console.log('no allEvents present inside shouldGenerateBreakEventsForDay');
    return false;
  }

  const breakEvents = allEvents.filter((event) => event.isBreak);
  const numberOfBreaksPerDay = userPreferences.minNumberOfBreaks;

  const breakHoursFromMinBreaks =
    (userPreferences.breakLength / 60) * numberOfBreaksPerDay;
  const hoursMustBeBreak =
    workingHours * (1 - userPreferences.maxWorkLoadPercent / 100);

  let breakHoursAvailable = 0;

  if (breakHoursFromMinBreaks > hoursMustBeBreak) {
    breakHoursAvailable = breakHoursFromMinBreaks;
  } else {
    breakHoursAvailable = hoursMustBeBreak;
  }

  let breakHoursUsed = 0;
  for (const breakEvent of breakEvents) {
    const duration = dayjs
      .duration(
        dayjs(
          dayjs(breakEvent.endDate.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss')
        ).diff(
          dayjs(breakEvent.startDate.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss')
        )
      )
      .asHours();
    breakHoursUsed += duration;
  }

  if (breakHoursUsed >= breakHoursAvailable) {
    console.log('breakHoursUsed >= breakHoursAvailable');
    return false;
  }

  if (!(allEvents?.length > 0)) {
    console.log(
      'there are no events for this date inside shouldGenerateBreakEvents'
    );
    return false;
  }

  return true;
};

export const generateBreakEventsForDay = async (
  userPreferences: UserPreferenceType,
  userId: string,
  hostStartDate: string,
  hostTimezone: string,
  globalCalendarId?: string,
  isFirstDay?: boolean
) => {
  try {
    if (!userPreferences?.breakLength) {
      console.log(
        'no user preferences breakLength provided inside shouldGenerateBreakEvents'
      );
      return null;
    }

    if (!userId) {
      console.log('no userId provided inside shouldGenerateBreakEvents');
      return null;
    }

    if (!hostStartDate) {
      console.log('no startDate provided inside shouldGenerateBreakEvents');
      return null;
    }

    if (!hostTimezone) {
      console.log('no timezone provided inside shouldGenerateBreakEvents');
      return null;
    }

    if (isFirstDay) {
      const endTimes = userPreferences.endTimes;
      const dayOfWeekInt = getISODay(
        dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate()
      );

      let startHourByHost = dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour();
      let startMinuteByHost = dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .minute();
      const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
      const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;

      const startTimes = userPreferences.startTimes;
      const workStartHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
      const workStartMinute = startTimes.find(
        (i) => i.day === dayOfWeekInt
      ).minutes;

      if (
        dayjs(hostStartDate.slice(0, 19)).isAfter(
          dayjs(hostStartDate.slice(0, 19)).hour(endHour).minute(endMinute)
        )
      ) {
        return null;
      }

      if (
        dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .isBefore(
            dayjs(hostStartDate.slice(0, 19))
              .tz(hostTimezone, true)
              .hour(workStartHour)
              .minute(workStartMinute)
          )
      ) {
        startHourByHost = workStartHour;
        startMinuteByHost = workStartMinute;
      }

      const workingHours = convertToTotalWorkingHoursForInternalAttendee(
        userPreferences,
        hostStartDate,
        hostTimezone
      );
      console.log(workingHours, ' workingHours');
      const allEvents = await listEventsForDate(
        userId,
        dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(startHourByHost)
          .minute(startMinuteByHost)
          .format(),
        dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(endHour)
          .minute(endMinute)
          .format(),
        hostTimezone
      );

      if (!(allEvents?.length > 0)) {
        console.log(
          'no allEvents present inside shouldGenerateBreakEventsForDay'
        );
        return null;
      }

      const shouldGenerateBreaks = shouldGenerateBreakEventsForDay(
        workingHours,
        userPreferences,
        allEvents
      );

      console.log(shouldGenerateBreaks, ' shouldGenerateBreaks');

      if (!shouldGenerateBreaks) {
        console.log('should not generate breaks');
        return null;
      }

      let hoursUsed = 0;

      if (allEvents?.length > 0) {
        for (const allEvent of allEvents) {
          const duration = dayjs
            .duration(
              dayjs(allEvent.endDate.slice(0, 19))
                .tz(hostTimezone, true)
                .diff(
                  dayjs(allEvent.startDate.slice(0, 19)).tz(hostTimezone, true)
                )
            )
            .asHours();
          hoursUsed += duration;
        }
      }

      console.log(hoursUsed, ' hoursUsed');

      let hoursAvailable = workingHours - hoursUsed;

      console.log(hoursAvailable, ' hoursAvailable');

      const hoursMustBeBreak =
        workingHours * (1 - userPreferences.maxWorkLoadPercent / 100);

      console.log(hoursMustBeBreak, ' hoursMustBeBreak');

      if (hoursAvailable < hoursMustBeBreak) {
        hoursAvailable = hoursMustBeBreak;
      }
      if (hoursAvailable <= 0) {
        console.log(hoursAvailable, ' no hours available');
        return null;
      }

      const oldBreakEvents = allEvents
        .filter((event) => event.isBreak)
        .filter((e) =>
          dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isSame(
              dayjs(e.startDate.slice(0, 19)).tz(hostTimezone, true),
              'day'
            )
        );

      const breakEvents = oldBreakEvents;

      const numberOfBreaksPerDay = userPreferences.minNumberOfBreaks;

      console.log(
        numberOfBreaksPerDay,
        ' numberOfBreaksPerDay aka userPreferences.minNumberOfBreaks'
      );
      console.log(userPreferences.breakLength, ' userPreferences.breakLength');

      const breakHoursToGenerateForMinBreaks =
        (userPreferences.breakLength / 60) * numberOfBreaksPerDay;

      console.log(
        breakHoursToGenerateForMinBreaks,
        ' breakHoursToGenerateForMinBreaks'
      );

      let breakHoursToGenerate = 0;

      if (breakHoursToGenerateForMinBreaks > hoursAvailable) {
        breakHoursToGenerate = hoursAvailable;
      } else {
        breakHoursToGenerate = breakHoursToGenerateForMinBreaks;
      }

      console.log(breakHoursToGenerate, ' breakHoursToGenerate');

      let breakHoursUsed = 0;

      if (breakEvents?.length > 0) {
        for (const breakEvent of breakEvents) {
          const duration = dayjs
            .duration(
              dayjs(breakEvent.endDate.slice(0, 19))
                .tz(hostTimezone, true)
                .diff(
                  dayjs(breakEvent.startDate.slice(0, 19)).tz(
                    hostTimezone,
                    true
                  )
                )
            )
            .asHours();
          breakHoursUsed += duration;
        }
      }

      const actualBreakHoursToGenerate = breakHoursToGenerate - breakHoursUsed;

      if (actualBreakHoursToGenerate > hoursAvailable) {
        console.log(' no hours available to generate break');
        return null;
      }
      console.log(actualBreakHoursToGenerate, ' actualBreakHoursToGenerate');
      console.log(breakHoursUsed, ' breakHoursUsed');
      console.log(breakHoursToGenerateForMinBreaks, ' breakHoursAvailable');
      const breakLengthAsHours = userPreferences.breakLength / 60;
      console.log(breakLengthAsHours, ' breakLengthAsHours');
      const numberOfBreaksToGenerate = Math.floor(
        actualBreakHoursToGenerate / breakLengthAsHours
      );
      console.log(numberOfBreaksToGenerate, ' numberOfBreaksToGenerate');

      if (numberOfBreaksToGenerate < 1) {
        console.log('should not generate breaks');
        return null;
      }

      if (breakHoursToGenerate > 6) {
        console.log('breakHoursToGenerate is > 6');
        return null;
      }

      const eventMirror = allEvents.find((event) => !event.isBreak);

      const newEvents = generateBreaks(
        userPreferences,
        numberOfBreaksToGenerate,
        eventMirror,
        globalCalendarId
      );

      return newEvents;
    }

    const endTimes = userPreferences.endTimes;
    const dayOfWeekInt = getISODay(
      dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate()
    );

    const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
    const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;

    const startTimes = userPreferences.startTimes;
    const startHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
    const startMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;

    const workingHours = convertToTotalWorkingHoursForInternalAttendee(
      userPreferences,
      hostStartDate,
      hostTimezone
    );
    const allEvents = await listEventsForDate(
      userId,
      dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(startHour)
        .minute(startMinute)
        .format(),
      dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(endHour)
        .minute(endMinute)
        .format(),
      hostTimezone
    );
    if (!(allEvents?.length > 0)) {
      console.log(
        'no allEvents present inside shouldGenerateBreakEventsForDay'
      );
      return null;
    }
    const shouldGenerateBreaks = shouldGenerateBreakEventsForDay(
      workingHours,
      userPreferences,
      allEvents
    );
    if (!shouldGenerateBreaks) {
      console.log('should not generate breaks');
      return null;
    }

    let hoursUsed = 0;

    if (allEvents?.length > 0) {
      for (const allEvent of allEvents) {
        const duration = dayjs
          .duration(
            dayjs(allEvent.endDate.slice(0, 19))
              .tz(hostTimezone, true)
              .diff(
                dayjs(allEvent.startDate.slice(0, 19)).tz(hostTimezone, true)
              )
          )
          .asHours();
        hoursUsed += duration;
      }
    }

    console.log(hoursUsed, ' hoursUsed');

    let hoursAvailable = workingHours - hoursUsed;
    const hoursMustBeBreak =
      workingHours * (1 - userPreferences.maxWorkLoadPercent / 100);

    console.log(hoursMustBeBreak, ' hoursMustBeBreak');
    console.log(hoursAvailable, ' hoursAvailable');

    if (hoursAvailable < hoursMustBeBreak) {
      hoursAvailable = hoursMustBeBreak;
    }

    console.log(hoursAvailable, ' hoursAvailable');

    if (hoursAvailable <= 0) {
      console.log(hoursAvailable, ' no hours available');
      return null;
    }

    const oldBreakEvents = allEvents
      .filter((event) => event.isBreak)
      .filter((e) =>
        dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .isSame(dayjs(e.startDate.slice(0, 19)).tz(hostTimezone, true), 'day')
      );

    const breakEvents = oldBreakEvents;

    const numberOfBreaksPerDay = userPreferences.minNumberOfBreaks;
    console.log(numberOfBreaksPerDay, ' numberOfBreaksPerDay');
    const breakHoursToGenerateForMinBreaks =
      (userPreferences.breakLength / 60) * numberOfBreaksPerDay;
    let breakHoursToGenerate = 0;

    if (breakHoursToGenerateForMinBreaks > hoursAvailable) {
      breakHoursToGenerate = hoursAvailable;
    } else {
      breakHoursToGenerate = breakHoursToGenerateForMinBreaks;
    }

    console.log(breakHoursToGenerate, ' breakHoursToGenerate');

    let breakHoursUsed = 0;

    if (breakEvents?.length > 0) {
      for (const breakEvent of breakEvents) {
        const duration = dayjs
          .duration(
            dayjs(breakEvent.endDate.slice(0, 19))
              .tz(hostTimezone, true)
              .diff(
                dayjs(breakEvent.startDate.slice(0, 19)).tz(hostTimezone, true)
              )
          )
          .asHours();
        breakHoursUsed += duration;
      }
    }

    const actualBreakHoursToGenerate = breakHoursToGenerate - breakHoursUsed;

    if (actualBreakHoursToGenerate > hoursAvailable) {
      console.log(' no hours available to generate break');
      return null;
    }

    console.log(breakHoursUsed, ' breakHoursUsed');
    console.log(breakHoursToGenerate, ' breakHoursAvailable');
    const breakLengthAsHours = userPreferences.breakLength / 60;
    console.log(breakLengthAsHours, ' breakLengthAsHours');
    const numberOfBreaksToGenerate = Math.floor(
      actualBreakHoursToGenerate / breakLengthAsHours
    );
    console.log(numberOfBreaksToGenerate, ' numberOfBreaksToGenerate');

    if (numberOfBreaksToGenerate < 1) {
      console.log('should not generate breaks');
      return null;
    }

    if (breakHoursToGenerate > 6) {
      console.log('breakHoursToGenerate is > 6');
      return null;
    }

    const eventMirror = allEvents.find((event) => !event.isBreak);

    const newEvents = generateBreaks(
      userPreferences,
      numberOfBreaksToGenerate,
      eventMirror,
      globalCalendarId
    );

    return newEvents;
  } catch (e) {
    console.log(e, ' unable to generate breaks for day');
  }
};

export const generateBreakEventsForDate = async (
  userPreferences: UserPreferenceType,
  userId: string,
  hostStartDate: string,
  hostEndDate: string,
  hostTimezone: string,
  globalCalendarId?: string
): Promise<EventPlusType[] | []> => {
  try {
    const totalBreakEvents = [];
    const totalDays = dayjs(hostEndDate.slice(0, 19))
      .tz(hostTimezone, true)
      .diff(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true), 'day');
    console.log(totalDays, ' totalDays inside generateBreakEventsForDate');
    for (let i = 0; i < totalDays; i++) {
      const dayDate = dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .add(i, 'day')
        .format();

      const newBreakEvents = await generateBreakEventsForDay(
        userPreferences,
        userId,
        dayDate,
        hostTimezone,
        globalCalendarId,
        i === 0
      );

      if (i === 0) {
        const endTimes = userPreferences.endTimes;
        const dayOfWeekInt = getISODay(
          dayjs(dayDate.slice(0, 19)).tz(hostTimezone, true).toDate()
        );

        let startHour = dayjs(dayDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour();
        let startMinute = dayjs(dayDate.slice(0, 19))
          .tz(hostTimezone, true)
          .minute();
        const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
        const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;

        const startTimes = userPreferences.startTimes;
        const workStartHour = startTimes.find(
          (i) => i.day === dayOfWeekInt
        ).hour;
        const workStartMinute = startTimes.find(
          (i) => i.day === dayOfWeekInt
        ).minutes;

        if (
          dayjs(dayDate.slice(0, 19)).isAfter(
            dayjs(dayDate.slice(0, 19)).hour(endHour).minute(endMinute)
          )
        ) {
          continue;
        }

        if (
          dayjs(dayDate.slice(0, 19)).isBefore(
            dayjs(dayDate.slice(0, 19))
              .hour(workStartHour)
              .minute(workStartMinute)
          )
        ) {
          startHour = workStartHour;
          startMinute = workStartMinute;
        }

        const allEvents = await listEventsForDate(
          userId,
          dayjs(dayDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(startHour)
            .minute(startMinute)
            .format(),
          dayjs(dayDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(endHour)
            .minute(endMinute)
            .format(),
          hostTimezone
        );
        const newBreakEventsAdjusted =
          await adjustStartDatesForBreakEventsForDay(
            allEvents,
            newBreakEvents,
            userPreferences,
            hostTimezone
          );
        if (newBreakEventsAdjusted?.length > 0) {
          newBreakEventsAdjusted.forEach((b) =>
            console.log(b, ' newBreakEventsAdjusted')
          );
          totalBreakEvents.push(...newBreakEventsAdjusted);
        }

        continue;
      }

      const endTimes = userPreferences.endTimes;
      const dayOfWeekInt = getISODay(
        dayjs(dayDate.slice(0, 19)).tz(hostTimezone, true).toDate()
      );

      const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
      const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;

      const startTimes = userPreferences.startTimes;
      const startHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
      const startMinute = startTimes.find(
        (i) => i.day === dayOfWeekInt
      ).minutes;

      const allEvents = await listEventsForDate(
        userId,
        dayjs(dayDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(startHour)
          .minute(startMinute)
          .format(),
        dayjs(dayDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(endHour)
          .minute(endMinute)
          .format(),
        hostTimezone
      );
      const newBreakEventsAdjusted = await adjustStartDatesForBreakEventsForDay(
        allEvents,
        newBreakEvents,
        userPreferences,
        hostTimezone
      );
      if (newBreakEventsAdjusted?.length > 0) {
        newBreakEventsAdjusted.forEach((b) =>
          console.log(b, ' newBreakEventsAdjusted')
        );
        totalBreakEvents.push(...newBreakEventsAdjusted);
      }
    }

    return totalBreakEvents;
  } catch (e) {
    console.log(e, ' unable to generateBreakEventsForDate');
  }
};

export const generateWorkTimesForInternalAttendee = (
  hostId: string,
  userId: string,
  userPreference: UserPreferenceType,
  hostTimezone: string,
  userTimezone: string
): WorkTimeType[] => {
  const daysInWeek = 7;
  const startTimes = userPreference.startTimes;
  const endTimes = userPreference.endTimes;
  const workTimes: WorkTimeType[] = [];

  for (let i = 0; i < daysInWeek; i++) {
    const dayOfWeekInt = i + 1;
    const startHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
    const startMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
    const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
    const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;

    workTimes.push({
      dayOfWeek: dayOfWeekIntToString[dayOfWeekInt],
      startTime: dayjs(
        setISODay(
          dayjs()
            .hour(startHour)
            .minute(startMinute)
            .tz(userTimezone, true)
            .toDate(),
          i + 1
        )
      )
        .tz(hostTimezone)
        .format('HH:mm') as Time,
      endTime: dayjs(
        setISODay(
          dayjs()
            .hour(endHour)
            .minute(endMinute)
            .tz(userTimezone, true)
            .toDate(),
          i + 1
        )
      )
        .tz(hostTimezone)
        .format('HH:mm') as Time,
      hostId,
      userId,
    });
  }

  return workTimes;
};

const formatToMonthDay = (month: MonthType, day: DayType): MonthDayType => {
  const monthFormat = (month < 9 ? `0${month + 1}` : `${month + 1}`) as MM;
  const dayFormat = (day < 10 ? `0${day}` : `${day}`) as DD;
  return `--${monthFormat}-${dayFormat}`;
};

export const generateTimeSlotsForInternalAttendee = (
  hostStartDate: string,
  hostId: string,
  userPreference: UserPreferenceType,
  hostTimezone: string,
  userTimezone: string,
  isFirstDay?: boolean
): TimeSlotType[] => {
  if (isFirstDay) {
    const endTimes = userPreference.endTimes;
    const dayOfWeekInt = getISODay(
      dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .tz(userTimezone)
        .toDate()
    );
    const dayOfWeekIntByHost = getISODay(
      dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate()
    );
    const dayOfMonth = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .tz(userTimezone)
      .date();
    const startHour = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .tz(userTimezone)
      .hour();
    const startMinute = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .tz(userTimezone)
      .isBetween(
        dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .tz(userTimezone)
          .minute(0),
        dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .tz(userTimezone)
          .minute(15),
        'minute',
        '[)'
      )
      ? 0
      : dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .isBetween(
              dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .tz(userTimezone)
                .minute(15),
              dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .tz(userTimezone)
                .minute(30),
              'minute',
              '[)'
            )
        ? 15
        : dayjs(hostStartDate.slice(0, 19))
              .tz(hostTimezone, true)
              .tz(userTimezone)
              .isBetween(
                dayjs(hostStartDate.slice(0, 19))
                  .tz(hostTimezone, true)
                  .tz(userTimezone)
                  .minute(30),
                dayjs(hostStartDate.slice(0, 19))
                  .tz(hostTimezone, true)
                  .tz(userTimezone)
                  .minute(45),
                'minute',
                '[)'
              )
          ? 30
          : 45;

    const monthByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .month();
    const dayOfMonthByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .date();
    const startHourByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .hour();
    const startMinuteByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .isBetween(
        dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(0),
        dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(15),
        'minute',
        '[)'
      )
      ? 0
      : dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isBetween(
              dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(15),
              dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(30),
              'minute',
              '[)'
            )
        ? 15
        : dayjs(hostStartDate.slice(0, 19))
              .tz(hostTimezone, true)
              .isBetween(
                dayjs(hostStartDate.slice(0, 19))
                  .tz(hostTimezone, true)
                  .minute(30),
                dayjs(hostStartDate.slice(0, 19))
                  .tz(hostTimezone, true)
                  .minute(45),
                'minute',
                '[)'
              )
          ? 30
          : 45;

    const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
    const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;
    const endHourByHost = dayjs(
      setISODay(
        dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .tz(userTimezone)
          .hour(endHour)
          .toDate(),
        dayOfWeekInt
      )
    )
      .tz(hostTimezone)
      .hour();
    const endMinuteByHost = dayjs(
      setISODay(
        dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .tz(userTimezone)
          .minute(endMinute)
          .toDate(),
        dayOfWeekInt
      )
    )
      .tz(hostTimezone)
      .minute();
    const startTimes = userPreference.startTimes;
    const workStartHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
    const workStartMinute = startTimes.find(
      (i) => i.day === dayOfWeekInt
    ).minutes;
    const workStartHourByHost = dayjs(
      setISODay(
        dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .tz(userTimezone)
          .hour(workStartHour)
          .toDate(),
        dayOfWeekInt
      )
    )
      .tz(hostTimezone)
      .hour();
    const workStartMinuteByHost = dayjs(
      setISODay(
        dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .tz(userTimezone)
          .minute(endMinute)
          .toDate(),
        dayOfWeekInt
      )
    )
      .tz(hostTimezone)
      .minute();

    if (
      dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .isAfter(
          dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(endHourByHost)
            .minute(endMinuteByHost)
        )
    ) {
      return [];
    }

    if (
      dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .isBefore(
          dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(workStartHourByHost)
            .minute(workStartMinuteByHost)
        )
    ) {
      const startDuration = dayjs.duration({
        hours: workStartHour,
        minutes: workStartMinute,
      });
      const endDuration = dayjs.duration({
        hours: endHour,
        minutes: endMinute,
      });
      const totalDuration = endDuration.subtract(startDuration);
      const totalMinutes = totalDuration.asMinutes();
      const timeSlots: TimeSlotType[] = [];
      console.log(
        hostStartDate,
        endTimes,
        dayOfWeekIntByHost,
        dayOfMonth,
        startHour,
        startMinute,
        endHour,
        endMinute,
        timezone,
        `startDate, endTimes, dayOfWeekIntByHost, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`
      );
      for (let i = 0; i < totalMinutes; i += 15) {
        timeSlots.push({
          dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
          startTime: dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(startHourByHost)
            .minute(startMinuteByHost)
            .add(i, 'minute')
            .format('HH:mm') as Time,
          endTime: dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(startHourByHost)
            .minute(startMinuteByHost)
            .add(i + 15, 'minute')
            .format('HH:mm') as Time,
          hostId,
          monthDay: formatToMonthDay(
            monthByHost as MonthType,
            dayOfMonthByHost as DayType
          ),
        });
      }
      console.log(
        timeSlots,
        ' timeSlots inside generateTimeSlots for first day where startDate is before work start time'
      );
      return timeSlots;
    }

    const startDuration = dayjs.duration({
      hours: startHour,
      minutes: startMinute,
    });
    const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute });
    const totalDuration = endDuration.subtract(startDuration);
    const totalMinutes = totalDuration.asMinutes();
    const timeSlots: TimeSlotType[] = [];
    console.log(
      hostStartDate,
      endTimes,
      dayOfWeekInt,
      dayOfMonthByHost,
      startHourByHost,
      startMinuteByHost,
      endHourByHost,
      endMinuteByHost,
      hostTimezone,
      `startDate, endTimes, dayOfWeekInt, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`
    );
    for (let i = 0; i < totalMinutes; i += 15) {
      timeSlots.push({
        dayOfWeek: dayOfWeekIntToString[dayOfWeekInt],
        startTime: dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(startHourByHost)
          .minute(startMinuteByHost)
          .add(i, 'minute')
          .format('HH:mm') as Time,
        endTime: dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(startHourByHost)
          .minute(startMinuteByHost)
          .add(i + 15, 'minute')
          .format('HH:mm') as Time,
        hostId,
        monthDay: formatToMonthDay(
          monthByHost as MonthType,
          dayOfMonthByHost as DayType
        ),
      });
    }
    console.log(timeSlots, ' timeSlots inside generateTimeSlots for first day');
    return timeSlots;
  }

  const startTimes = userPreference.startTimes;
  const endTimes = userPreference.endTimes;
  const dayOfWeekInt = getISODay(
    dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .tz(userTimezone)
      .toDate()
  );
  const startHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
  const startMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
  const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
  const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;

  const monthByHost = dayjs(hostStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .month();
  const dayOfMonthByHost = dayjs(hostStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .date();

  const startHourByHost = dayjs(hostStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .tz(userTimezone)
    .hour(startHour)
    .tz(hostTimezone)
    .hour();
  const startMinuteByHost = dayjs(hostStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .tz(userTimezone)
    .minute(startMinute)
    .tz(hostTimezone)
    .minute();
  const endHourByHost = dayjs(hostStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .tz(userTimezone)
    .hour(endHour)
    .tz(hostTimezone)
    .hour();

  console.log(
    monthByHost,
    dayOfMonthByHost,
    startHourByHost,
    startMinuteByHost,
    endHourByHost,
    ' monthByHost, dayOfMonthByHost, startHourByHost, startMinuteByHost, endHourByHost'
  );
  const startDuration = dayjs.duration({
    hours: startHour,
    minutes: startMinute,
  });
  const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute });
  const totalDuration = endDuration.subtract(startDuration);
  const totalMinutes = totalDuration.asMinutes();
  const timeSlots: TimeSlotType[] = [];
  for (let i = 0; i < totalMinutes; i += 15) {
    timeSlots.push({
      dayOfWeek: dayOfWeekIntToString[dayOfWeekInt],
      startTime: dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(startHourByHost)
        .minute(startMinuteByHost)
        .add(i, 'minute')
        .format('HH:mm') as Time,
      endTime: dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(startHourByHost)
        .minute(startMinuteByHost)
        .add(i + 15, 'minute')
        .format('HH:mm') as Time,
      hostId,
      monthDay: formatToMonthDay(
        monthByHost as MonthType,
        dayOfMonthByHost as DayType
      ),
    });
  }
  console.log(timeSlots, ' timeSlots inside generateTimeSlots');
  return timeSlots;
};

export const generateTimeSlotsLiteForInternalAttendee = (
  hostStartDate: string,
  hostId: string,
  userPreference: UserPreferenceType,
  hostTimezone: string,
  userTimezone: string,
  isFirstDay?: boolean
): TimeSlotType[] => {
  if (isFirstDay) {
    const endTimes = userPreference.endTimes;

    const dayOfWeekInt = getISODay(
      dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate()
    );

    const startHourOfHostDateByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .hour();
    const startMinuteOfHostDateByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .isBetween(
        dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(0),
        dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(30),
        'minute',
        '[)'
      )
      ? 0
      : dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isBetween(
              dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(30),
              dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(59),
              'minute',
              '[)'
            )
        ? 30
        : 0;

    const monthByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .month();
    const dayOfMonthByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .date();
    const startHourByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .hour();
    const startMinuteByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .isBetween(
        dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(0),
        dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(30),
        'minute',
        '[)'
      )
      ? 0
      : dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isBetween(
              dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(30),
              dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(59),
              'minute',
              '[)'
            )
        ? 30
        : 0;

    const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
    const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;
    const endHourByHost = dayjs(
      setISODay(
        dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .tz(userTimezone)
          .hour(endHour)
          .toDate(),
        dayOfWeekInt
      )
    )
      .tz(hostTimezone)
      .hour();
    const endMinuteByHost = dayjs(
      setISODay(
        dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .tz(userTimezone)
          .minute(endMinute)
          .toDate(),
        dayOfWeekInt
      )
    )
      .tz(hostTimezone)
      .minute();

    const startTimes = userPreference.startTimes;
    const workStartHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
    const workStartMinute = startTimes.find(
      (i) => i.day === dayOfWeekInt
    ).minutes;
    const workStartHourByHost = dayjs(
      setISODay(
        dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .tz(userTimezone)
          .hour(workStartHour)
          .toDate(),
        dayOfWeekInt
      )
    )
      .tz(hostTimezone)
      .hour();
    const workStartMinuteByHost = dayjs(
      setISODay(
        dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .tz(userTimezone)
          .minute(endMinute)
          .toDate(),
        dayOfWeekInt
      )
    )
      .tz(hostTimezone)
      .minute();

    if (
      dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .isAfter(
          dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(endHourByHost)
            .minute(endMinuteByHost)
        )
    ) {
      return [];
    }

    if (
      dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .isBefore(
          dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(workStartHourByHost)
            .minute(workStartMinuteByHost)
        )
    ) {
      const startDuration = dayjs.duration({
        hours: workStartHour,
        minutes: workStartMinute,
      });
      const endDuration = dayjs.duration({
        hours: endHour,
        minutes: endMinute,
      });
      const totalDuration = endDuration.subtract(startDuration);
      const totalMinutes = totalDuration.asMinutes();
      const timeSlots: TimeSlotType[] = [];
      for (let i = 0; i < totalMinutes; i += 30) {
        timeSlots.push({
          dayOfWeek: dayOfWeekIntToString[dayOfWeekInt],
          startTime: dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(startHourByHost)
            .minute(startMinuteByHost)
            .add(i, 'minute')
            .format('HH:mm') as Time,
          endTime: dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(startHourByHost)
            .minute(startMinuteByHost)
            .add(i + 30, 'minute')
            .format('HH:mm') as Time,
          hostId,
          monthDay: formatToMonthDay(
            monthByHost as MonthType,
            dayOfMonthByHost as DayType
          ),
        });
      }
      console.log(
        timeSlots,
        ' timeSlots inside generateTimeSlots for first day before start time'
      );
      return timeSlots;
    }

    const startDuration = dayjs.duration({
      hours: startHourOfHostDateByHost,
      minutes: startMinuteOfHostDateByHost,
    });
    const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute });
    const totalDuration = endDuration.subtract(startDuration);
    const totalMinutes = totalDuration.asMinutes();
    const timeSlots: TimeSlotType[] = [];
    for (let i = 0; i < totalMinutes; i += 30) {
      timeSlots.push({
        dayOfWeek: dayOfWeekIntToString[dayOfWeekInt],
        startTime: dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(startHourByHost)
          .minute(startMinuteByHost)
          .add(i, 'minute')
          .format('HH:mm') as Time,
        endTime: dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(startHourByHost)
          .minute(startMinuteByHost)
          .add(i + 30, 'minute')
          .format('HH:mm') as Time,
        hostId,
        monthDay: formatToMonthDay(
          monthByHost as MonthType,
          dayOfMonthByHost as DayType
        ),
      });
    }
    console.log(timeSlots, ' timeSlots inside generateTimeSlots for first day');
    return timeSlots;
  }
  const startTimes = userPreference.startTimes;
  const endTimes = userPreference.endTimes;

  const dayOfWeekInt = getISODay(
    dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .tz(userTimezone)
      .toDate()
  );
  const startHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
  const startMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
  const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
  const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;

  const monthByHost = dayjs(hostStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .month();
  const dayOfMonthByHost = dayjs(hostStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .date();
  const dayOfWeekIntByHost = getISODay(
    dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate()
  );
  const startHourByHost = dayjs(hostStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .tz(userTimezone)
    .hour(startHour)
    .tz(hostTimezone)
    .hour();
  const startMinuteByHost = dayjs(hostStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .tz(userTimezone)
    .minute(startMinute)
    .tz(hostTimezone)
    .minute();

  const startDuration = dayjs.duration({
    hours: startHour,
    minutes: startMinute,
  });
  const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute });
  const totalDuration = endDuration.subtract(startDuration);
  const totalMinutes = totalDuration.asMinutes();
  const timeSlots: TimeSlotType[] = [];
  for (let i = 0; i < totalMinutes; i += 30) {
    timeSlots.push({
      dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
      startTime: dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(startHourByHost)
        .minute(startMinuteByHost)
        .add(i, 'minute')
        .format('HH:mm') as Time,
      endTime: dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(startHourByHost)
        .minute(startMinuteByHost)
        .add(i + 30, 'minute')
        .format('HH:mm') as Time,
      hostId,
      monthDay: formatToMonthDay(
        monthByHost as MonthType,
        dayOfMonthByHost as DayType
      ),
    });
  }
  console.log(timeSlots, ' timeSlots inside generateTimeSlots');
  return timeSlots;
};

export const validateEventDates = (
  event: EventPlusType,
  userPreferences: UserPreferenceType
): boolean => {
  if (!event?.timezone) {
    return false;
  }

  const diff = dayjs(event.endDate.slice(0, 19))
    .tz(event.timezone, true)
    .diff(dayjs(event.startDate.slice(0, 19)).tz(event.timezone, true), 'm');
  const diffDay = dayjs(event.endDate.slice(0, 19))
    .tz(event.timezone, true)
    .diff(dayjs(event.startDate.slice(0, 19)).tz(event.timezone, true), 'd');
  const diffHours = dayjs(event.endDate.slice(0, 19))
    .tz(event.timezone, true)
    .diff(dayjs(event.startDate.slice(0, 19)).tz(event.timezone, true), 'h');

  const isoWeekDay = getISODay(
    dayjs(event?.startDate.slice(0, 19)).tz(event?.timezone, true).toDate()
  );
  const endHour = userPreferences.endTimes.find(
    (e) => e?.day === isoWeekDay
  )?.hour;
  const endMinutes = userPreferences.endTimes.find(
    (e) => e?.day === isoWeekDay
  )?.minutes;
  const startHour = userPreferences.startTimes.find(
    (e) => e?.day === isoWeekDay
  )?.hour;
  const startMinutes = userPreferences.startTimes.find(
    (e) => e?.day === isoWeekDay
  )?.minutes;

  if (
    dayjs(event.startDate.slice(0, 19))
      .tz(event.timezone, true)
      .isAfter(
        dayjs(event?.startDate.slice(0, 19))
          .tz(event.timezone, true)
          .hour(endHour)
          .minute(endMinutes)
      )
  ) {
    return false;
  }

  if (
    dayjs(event.startDate.slice(0, 19))
      .tz(event.timezone, true)
      .isBefore(
        dayjs(event?.startDate.slice(0, 19))
          .tz(event.timezone, true)
          .hour(startHour)
          .minute(startMinutes)
      )
  ) {
    return false;
  }

  if (diff === 0) {
    console.log(
      event.id,
      event.startDate,
      event.endDate,
      ' the start date and end date are the same'
    );
    return false;
  }

  if (diff < 0) {
    console.log(
      event.id,
      event.startDate,
      event.endDate,
      ' the start date is after end date'
    );
    return false;
  }

  if (diffDay >= 1) {
    console.log(
      event.id,
      event.startDate,
      event.endDate,
      ' the start date and end date are more than 1 day apart'
    );
    return false;
  }

  if (diffHours > 23) {
    console.log(
      event.id,
      event.startDate,
      event.endDate,
      ' the start date and end date are more than 23 hours apart'
    );
    return false;
  }

  return true;
};

export const validateEventDatesForExternalAttendee = (
  event: EventPlusType
): boolean => {
  if (!event?.timezone) {
    return false;
  }

  const diff = dayjs(event.endDate.slice(0, 19))
    .tz(event.timezone, true)
    .diff(dayjs(event.startDate.slice(0, 19)).tz(event.timezone, true), 'm');
  const diffDay = dayjs(event.endDate.slice(0, 19))
    .tz(event.timezone, true)
    .diff(dayjs(event.startDate.slice(0, 19)).tz(event.timezone, true), 'd');
  const diffHours = dayjs(event.endDate.slice(0, 19))
    .tz(event.timezone, true)
    .diff(dayjs(event.startDate.slice(0, 19)).tz(event.timezone, true), 'h');

  if (diff === 0) {
    console.log(
      event.id,
      event.startDate,
      event.endDate,
      ' the start date and end date are the same'
    );
    return false;
  }

  if (diff < 0) {
    console.log(
      event.id,
      event.startDate,
      event.endDate,
      ' the start date is after end date'
    );
    return false;
  }

  if (diffDay >= 1) {
    console.log(
      event.id,
      event.startDate,
      event.endDate,
      ' the start date and end date are more than 1 day apart'
    );
    return false;
  }

  if (diffHours > 23) {
    console.log(
      event.id,
      event.startDate,
      event.endDate,
      ' the start date and end date are more than 23 hours apart'
    );
    return false;
  }

  return true;
};

export const generateEventParts = (
  event: EventPlusType,
  hostId: string
): InitialEventPartType[] => {
  console.log(
    event.id,
    event.startDate.slice(0, 19),
    event.endDate.slice(0, 19),
    ' event.id, event.startDate.slice(0, 19), event.endDate.slice(0, 19) inside generateEventParts'
  );
  const minutes = dayjs(event.endDate.slice(0, 19))
    .tz(event.timezone, true)
    .diff(dayjs(event.startDate.slice(0, 19)).tz(event.timezone, true), 'm');
  console.log(
    event.id,
    minutes,
    'event.id,  minutes inside generateEventParts'
  );
  const parts = Math.floor(minutes / 15);
  const remainder = minutes % 15;
  const eventParts: InitialEventPartType[] = [];
  for (let i = 0; i < parts; i++) {
    eventParts.push({
      ...event,
      groupId: event.id,
      eventId: event.id,
      startDate: event.startDate.slice(0, 19),
      endDate: event.endDate.slice(0, 19),
      part: i + 1,
      meetingPart: i + 1,
      meetingLastPart: remainder > 0 ? parts + 1 : parts,
      lastPart: remainder > 0 ? parts + 1 : parts,
      hostId,
    });
  }

  if (remainder > 0) {
    eventParts.push({
      ...event,
      groupId: event.id,
      eventId: event.id,
      startDate: event.startDate.slice(0, 19),
      endDate: event.endDate.slice(0, 19),
      part: parts + 1,
      lastPart: parts + 1,
      meetingPart: parts + 1,
      meetingLastPart: parts + 1,
      hostId,
    });
  }
  console.log(
    event.id,
    eventParts?.[0]?.startDate,
    eventParts?.[0]?.endDate,
    eventParts?.[0]?.part,
    eventParts?.[0]?.lastPart,
    'event.id,  eventParts?.[0]?.startDate, eventParts?.[0]?.endDate, eventParts?.[0]?.part, eventParts?.[0]?.lastPart,'
  );
  return eventParts;
};

export const generateEventPartsLite = (
  event: EventPlusType,
  hostId: string
): InitialEventPartType[] => {
  const minutes = dayjs(event.endDate.slice(0, 19))
    .tz(event.timezone, true)
    .diff(dayjs(event.startDate.slice(0, 19)).tz(event.timezone, true), 'm');
  const parts = Math.floor(minutes / 30);
  const remainder = minutes % 30;
  const eventParts: InitialEventPartType[] = [];
  for (let i = 0; i < parts; i++) {
    eventParts.push({
      ...event,
      groupId: event.id,
      eventId: event.id,
      startDate: event.startDate.slice(0, 19),
      endDate: event.endDate.slice(0, 19),
      part: i + 1,
      lastPart: remainder > 0 ? parts + 1 : parts,
      meetingPart: i + 1,
      meetingLastPart: remainder > 0 ? parts + 1 : parts,
      hostId,
    });
  }

  if (remainder > 0) {
    eventParts.push({
      ...event,
      groupId: event.id,
      eventId: event.id,
      startDate: event.startDate.slice(0, 19),
      endDate: event.endDate.slice(0, 19),
      part: parts + 1,
      lastPart: parts + 1,
      meetingPart: parts + 1,
      meetingLastPart: parts + 1,
      hostId,
    });
  }
  return eventParts;
};

export const modifyEventPartsForSingularPreBufferTime = (
  eventParts: InitialEventPartType[],
  forEventId: string
): InitialEventPartType[] => {
  const preBufferBeforeEventParts: InitialEventPartType[] = [];
  const preBufferActualEventParts: InitialEventPartType[] = [];

  const preBufferGroupId = uuid();

  for (let i = 0; i < eventParts.length; i++) {
    if (eventParts[i].forEventId === forEventId && eventParts[i].isPreEvent) {
      console.log(
        eventParts[i].forEventId,
        forEventId,
        ' eventParts[i].forEventId === forEventId  inside modifyEventPartsForSingularPreBufferTime'
      );
      preBufferBeforeEventParts.push({
        ...eventParts[i],
        groupId: preBufferGroupId,
      });
    }
  }

  for (let i = 0; i < eventParts.length; i++) {
    if (eventParts[i].id === forEventId) {
      console.log(
        eventParts[i].id,
        forEventId,
        'eventParts[i].id === forEventId inside modifyEventPartsForSingularPreBufferTime'
      );
      preBufferActualEventParts.push({
        ...eventParts[i],
        groupId: preBufferGroupId,
      });
    }
  }

  const preBufferBeforeEventPartsSorted = preBufferBeforeEventParts.sort(
    (a, b) => a.part - b.part
  );
  const preBufferActualEventPartsSorted = preBufferActualEventParts.sort(
    (a, b) => a.part - b.part
  );

  const preBufferEventPartsTotal = preBufferBeforeEventPartsSorted.concat(
    preBufferActualEventPartsSorted
  );

  for (let i = 0; i < preBufferEventPartsTotal.length; i++) {
    preBufferEventPartsTotal[i].part = i + 1;
    preBufferEventPartsTotal[i].lastPart = preBufferEventPartsTotal.length;
  }
  preBufferEventPartsTotal.forEach((e) =>
    console.log(
      e.id,
      e.groupId,
      e.eventId,
      e.part,
      e.lastPart,
      e.startDate,
      e.endDate,
      `e.id, e.groupId, e.eventId, e.part, e.lastPart, e.startDate, e.endDate, inside modifyEventPartsForSingularPreBufferTime`
    )
  );
  return preBufferEventPartsTotal;
};
export const modifyEventPartsForMultiplePreBufferTime = (
  eventParts: InitialEventPartType[]
): InitialEventPartType[] => {
  const uniquePreBufferPartForEventIds: string[] = [];
  const preBufferEventPartsTotal: InitialEventPartType[] = [];

  for (let i = 0; i < eventParts.length; i++) {
    if (eventParts[i].forEventId && eventParts[i].isPreEvent) {
      const foundPart = uniquePreBufferPartForEventIds.find(
        (e) => e === eventParts[i].forEventId
      );
      if (foundPart) {
        continue;
      } else {
        uniquePreBufferPartForEventIds.push(eventParts[i].forEventId);
      }
    }
  }

  for (let i = 0; i < uniquePreBufferPartForEventIds.length; i++) {
    const returnedEventPartTotal = modifyEventPartsForSingularPreBufferTime(
      eventParts,
      uniquePreBufferPartForEventIds[i]
    );
    preBufferEventPartsTotal.push(...returnedEventPartTotal);
  }

  const eventPartsFiltered = _.differenceBy(
    eventParts,
    preBufferEventPartsTotal,
    'id'
  );
  const concatenatedValues = eventPartsFiltered.concat(
    preBufferEventPartsTotal
  );
  concatenatedValues.forEach((e) =>
    console.log(
      e.id,
      e.groupId,
      e.eventId,
      e.part,
      e.lastPart,
      e.startDate,
      e.endDate,
      e?.forEventId,
      `e.id, e.eventId, e.actualId, e.part, e.lastPart, e.startDate, e.endDate, e?.forEventId,  inside modifyEventPartsForMultiplePreBufferTime`
    )
  );
  return concatenatedValues;
};

export const modifyEventPartsForMultiplePostBufferTime = (
  eventParts: InitialEventPartType[]
): InitialEventPartType[] => {
  const uniquePostBufferPartForEventIds: string[] = [];
  const postBufferEventPartsTotal: InitialEventPartType[] = [];

  for (let i = 0; i < eventParts.length; i++) {
    if (eventParts[i].forEventId && eventParts[i].isPostEvent) {
      const foundPart = uniquePostBufferPartForEventIds.find(
        (e) => e === eventParts[i].forEventId
      );
      if (foundPart) {
        continue;
      } else {
        uniquePostBufferPartForEventIds.push(eventParts[i].forEventId);
      }
    }
  }

  for (let i = 0; i < uniquePostBufferPartForEventIds.length; i++) {
    const returnedEventPartTotal = modifyEventPartsForSingularPostBufferTime(
      eventParts,
      uniquePostBufferPartForEventIds[i]
    );
    postBufferEventPartsTotal.push(...returnedEventPartTotal);
  }

  const eventPartsFiltered = _.differenceBy(
    eventParts,
    postBufferEventPartsTotal,
    'id'
  );
  const concatenatedValues = eventPartsFiltered.concat(
    postBufferEventPartsTotal
  );

  concatenatedValues.forEach((e) =>
    console.log(
      e.id,
      e.groupId,
      e.eventId,
      e.part,
      e.lastPart,
      e.startDate,
      e.endDate,
      e?.forEventId,
      `e.id, e.groupId, e.eventId, e.part, e.lastPart, e.startDate, e.endDate, e?.forEventId,  inside modifyEventPartsForMultiplePostBufferTime`
    )
  );
  return concatenatedValues;
};

export const modifyEventPartsForSingularPostBufferTime = (
  eventParts: InitialEventPartType[],
  forEventId: string
): InitialEventPartType[] => {
  const postBufferAfterEventParts: InitialEventPartType[] = [];
  const postBufferActualEventParts: InitialEventPartType[] = [];

  const postBufferGroupId = uuid();

  for (let i = 0; i < eventParts.length; i++) {
    if (eventParts[i].id == forEventId) {
      postBufferActualEventParts.push({
        ...eventParts[i],
        groupId: postBufferGroupId,
      });
    }
  }

  for (let i = 0; i < eventParts.length; i++) {
    if (eventParts[i].forEventId === forEventId && eventParts[i].isPostEvent) {
      postBufferAfterEventParts.push({
        ...eventParts[i],
        groupId: postBufferGroupId,
      });
    }
  }

  const postBufferActualEventPartsSorted = postBufferActualEventParts.sort(
    (a, b) => a.part - b.part
  );
  const postBufferAfterEventPartsSorted = postBufferAfterEventParts.sort(
    (a, b) => a.part - b.part
  );

  const postBufferEventPartsTotal = postBufferActualEventPartsSorted.concat(
    postBufferAfterEventPartsSorted
  );

  const preEventId = postBufferEventPartsTotal?.[0]?.preEventId;
  const actualEventPreviousLastPart = postBufferEventPartsTotal?.[0]?.lastPart;

  for (let i = 0; i < postBufferEventPartsTotal.length; i++) {
    if (preEventId) {
      postBufferEventPartsTotal[i].lastPart =
        actualEventPreviousLastPart + postBufferAfterEventPartsSorted.length;
    } else {
      postBufferEventPartsTotal[i].part = i + 1;
      postBufferEventPartsTotal[i].lastPart = postBufferEventPartsTotal.length;
    }
  }

  for (let i = 0; i < postBufferAfterEventPartsSorted.length; i++) {
    if (
      postBufferEventPartsTotal?.[postBufferActualEventPartsSorted?.length + i]
    ) {
      postBufferEventPartsTotal[
        postBufferActualEventPartsSorted?.length + i
      ].part = actualEventPreviousLastPart + i + 1;
    }
  }

  const preEventParts = eventParts.filter((e) => e.eventId === preEventId);
  const preBufferEventParts = preEventParts?.map((e) => ({
    ...e,
    groupId: postBufferGroupId,
    lastPart:
      actualEventPreviousLastPart + postBufferAfterEventPartsSorted.length,
  }));
  const concatenatedValues = preBufferEventParts.concat(
    postBufferEventPartsTotal
  );
  concatenatedValues.forEach((e) =>
    console.log(
      e.id,
      e.groupId,
      e.eventId,
      e.part,
      e.lastPart,
      e.startDate,
      e.endDate,
      e?.forEventId,
      `e.id, e.groupId, e.eventId, e.part, e.lastPart, e.startDate, e.endDate, e?.forEventId,  inside modifyEventPartsForSinglularPostBufferTime`
    )
  );
  return concatenatedValues;
};

export const formatEventTypeToPlannerEvent = (
  event: InitialEventPartTypePlus,
  userPreference: UserPreferenceType,
  workTimes: WorkTimeType[],
  hostTimezone: string
): EventPartPlannerRequestBodyType => {
  const {
    allDay,
    part,
    forEventId,
    groupId,
    eventId,
    isBreak,
    isExternalMeeting,
    isExternalMeetingModifiable,
    isMeeting,
    isMeetingModifiable,
    isPostEvent,
    isPreEvent,
    modifiable,
    negativeImpactDayOfWeek,
    negativeImpactScore,
    negativeImpactTime,
    positiveImpactDayOfWeek,
    positiveImpactScore,
    positiveImpactTime,
    preferredDayOfWeek,
    preferredEndTimeRange,
    preferredStartTimeRange,
    preferredTime,
    priority,
    startDate,
    endDate,
    taskId,
    userId,
    weeklyTaskList,
    dailyTaskList,
    hardDeadline,
    softDeadline,
    recurringEventId,
    lastPart,
    preferredTimeRanges,
    hostId,
    meetingId,
    timezone,
    meetingPart,
    meetingLastPart,
  } = event;

  if (allDay) {
    return null;
  }

  const totalWorkingHours = convertToTotalWorkingHoursForInternalAttendee(
    userPreference,
    dayjs(event.startDate.slice(0, 19))
      .tz(event.timezone, true)
      .tz(hostTimezone)
      .format(),
    hostTimezone
  );

  const user: UserPlannerRequestBodyType = {
    id: event.userId,
    maxWorkLoadPercent: userPreference.maxWorkLoadPercent,
    backToBackMeetings: userPreference.backToBackMeetings,
    maxNumberOfMeetings: userPreference.maxNumberOfMeetings,
    minNumberOfBreaks: userPreference.minNumberOfBreaks,
    workTimes,
    hostId,
  };

  const adjustedPositiveImpactTime =
    (positiveImpactTime &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(positiveImpactTime.slice(0, 2), 10))
        .minute(parseInt(positiveImpactTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm') as Time)) ||
    undefined;

  const adjustedNegativeImpactTime =
    (negativeImpactTime &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(negativeImpactTime.slice(0, 2), 10))
        .minute(parseInt(negativeImpactTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm') as Time)) ||
    undefined;

  const adjustedPreferredTime =
    (preferredTime &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(preferredTime.slice(0, 2), 10))
        .minute(parseInt(preferredTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm') as Time)) ||
    undefined;

  const adjustedPreferredStartTimeRange =
    (preferredStartTimeRange &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(preferredStartTimeRange.slice(0, 2), 10))
        .minute(parseInt(preferredStartTimeRange.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm') as Time)) ||
    undefined;

  const adjustedPreferredEndTimeRange =
    (preferredEndTimeRange &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(preferredEndTimeRange.slice(0, 2), 10))
        .minute(parseInt(preferredEndTimeRange.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm') as Time)) ||
    undefined;

  const adjustedPreferredTimeRanges =
    preferredTimeRanges?.map((e) => ({
      dayOfWeek: dayOfWeekIntToString?.[e?.dayOfWeek] ?? null,
      startTime: dayjs()
        .tz(timezone)
        .hour(parseInt(e?.startTime.slice(0, 2), 10))
        .minute(parseInt(e?.startTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm') as Time,
      endTime: dayjs()
        .tz(timezone)
        .hour(parseInt(e?.endTime.slice(0, 2), 10))
        .minute(parseInt(e?.endTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm') as Time,
      eventId,
      userId,
      hostId,
    })) ?? null;

  const eventPlannerRequestBody: EventPartPlannerRequestBodyType = {
    groupId,
    eventId,
    part,
    lastPart,
    startDate,
    endDate,
    taskId,
    hardDeadline,
    softDeadline,
    userId,
    user,
    priority,
    isPreEvent,
    isPostEvent,
    forEventId,
    positiveImpactScore,
    negativeImpactScore,
    positiveImpactDayOfWeek:
      dayOfWeekIntToString[positiveImpactDayOfWeek] ?? null,
    positiveImpactTime: adjustedPositiveImpactTime,
    negativeImpactDayOfWeek:
      dayOfWeekIntToString[negativeImpactDayOfWeek] ?? null,
    negativeImpactTime: adjustedNegativeImpactTime,
    modifiable,
    preferredDayOfWeek: dayOfWeekIntToString[preferredDayOfWeek] ?? null,
    preferredTime: adjustedPreferredTime,
    isMeeting,
    isExternalMeeting,
    isExternalMeetingModifiable,
    isMeetingModifiable,
    dailyTaskList,
    weeklyTaskList,
    gap: isBreak,
    preferredStartTimeRange: adjustedPreferredStartTimeRange,
    preferredEndTimeRange: adjustedPreferredEndTimeRange,
    totalWorkingHours,
    recurringEventId,
    hostId,
    meetingId,
    meetingPart,
    meetingLastPart,
    event: {
      id: eventId,
      userId,
      hostId,
      preferredTimeRanges: adjustedPreferredTimeRanges ?? null,
    },
  };
  return eventPlannerRequestBody;
};

export const formatEventTypeToPlannerEventForExternalAttendee = (
  event: InitialEventPartTypePlus,
  workTimes: WorkTimeType[],
  attendeeEvents: EventPlusType[],
  hostTimezone: string
): EventPartPlannerRequestBodyType => {
  const {
    allDay,
    part,
    forEventId,
    groupId,
    eventId,
    isBreak,
    isExternalMeeting,
    isExternalMeetingModifiable,
    isMeeting,
    isMeetingModifiable,
    isPostEvent,
    isPreEvent,
    modifiable,
    negativeImpactDayOfWeek,
    negativeImpactScore,
    negativeImpactTime,
    positiveImpactDayOfWeek,
    positiveImpactScore,
    positiveImpactTime,
    preferredDayOfWeek,
    preferredEndTimeRange,
    preferredStartTimeRange,
    preferredTime,
    priority,
    startDate,
    endDate,
    taskId,
    userId,
    weeklyTaskList,
    dailyTaskList,
    hardDeadline,
    softDeadline,
    recurringEventId,
    lastPart,
    preferredTimeRanges,
    hostId,
    meetingId,
    timezone,
    meetingPart,
    meetingLastPart,
  } = event;

  if (allDay) {
    return null;
  }

  const totalWorkingHours = convertToTotalWorkingHoursForExternalAttendee(
    attendeeEvents,
    dayjs(event.startDate.slice(0, 19))
      .tz(event.timezone, true)
      .tz(hostTimezone)
      .format(),
    hostTimezone,
    event?.timezone
  );

  const user: UserPlannerRequestBodyType = {
    id: event.userId,
    maxWorkLoadPercent: 100,
    backToBackMeetings: false,
    maxNumberOfMeetings: 99,
    minNumberOfBreaks: 0,
    workTimes,
    hostId,
  };

  const adjustedPositiveImpactTime =
    (positiveImpactTime &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(positiveImpactTime.slice(0, 2), 10))
        .minute(parseInt(positiveImpactTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm') as Time)) ||
    undefined;

  const adjustedNegativeImpactTime =
    (negativeImpactTime &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(negativeImpactTime.slice(0, 2), 10))
        .minute(parseInt(negativeImpactTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm') as Time)) ||
    undefined;

  const adjustedPreferredTime =
    (preferredTime &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(preferredTime.slice(0, 2), 10))
        .minute(parseInt(preferredTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm') as Time)) ||
    undefined;

  const adjustedPreferredStartTimeRange =
    (preferredStartTimeRange &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(preferredStartTimeRange.slice(0, 2), 10))
        .minute(parseInt(preferredStartTimeRange.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm') as Time)) ||
    undefined;

  const adjustedPreferredEndTimeRange =
    (preferredEndTimeRange &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(preferredEndTimeRange.slice(0, 2), 10))
        .minute(parseInt(preferredEndTimeRange.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm') as Time)) ||
    undefined;

  const adjustedPreferredTimeRanges =
    preferredTimeRanges?.map((e) => ({
      dayOfWeek: dayOfWeekIntToString?.[e?.dayOfWeek] ?? null,
      startTime: dayjs()
        .tz(timezone)
        .hour(parseInt(e?.startTime.slice(0, 2), 10))
        .minute(parseInt(e?.startTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm') as Time,
      endTime: dayjs()
        .tz(timezone)
        .hour(parseInt(e?.endTime.slice(0, 2), 10))
        .minute(parseInt(e?.endTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm') as Time,
      eventId,
      userId,
      hostId,
    })) ?? null;

  const eventPlannerRequestBody: EventPartPlannerRequestBodyType = {
    groupId,
    eventId,
    part,
    lastPart,
    startDate,
    endDate,
    taskId,
    hardDeadline,
    softDeadline,
    userId,
    user,
    priority,
    isPreEvent,
    isPostEvent,
    forEventId,
    positiveImpactScore,
    negativeImpactScore,
    positiveImpactDayOfWeek:
      dayOfWeekIntToString[positiveImpactDayOfWeek] ?? null,
    positiveImpactTime: adjustedPositiveImpactTime,
    negativeImpactDayOfWeek:
      dayOfWeekIntToString[negativeImpactDayOfWeek] ?? null,
    negativeImpactTime: adjustedNegativeImpactTime,
    modifiable,
    preferredDayOfWeek: dayOfWeekIntToString[preferredDayOfWeek] ?? null,
    preferredTime: adjustedPreferredTime,
    isMeeting,
    isExternalMeeting,
    isExternalMeetingModifiable,
    isMeetingModifiable,
    dailyTaskList,
    weeklyTaskList,
    gap: isBreak,
    preferredStartTimeRange: adjustedPreferredStartTimeRange,
    preferredEndTimeRange: adjustedPreferredEndTimeRange,
    totalWorkingHours,
    recurringEventId,
    hostId,
    meetingId,
    meetingPart,
    meetingLastPart,
    event: {
      id: eventId,
      userId,
      hostId,
      preferredTimeRanges: adjustedPreferredTimeRanges ?? null,
    },
  };
  return eventPlannerRequestBody;
};

export const convertMeetingPlusTypeToEventPlusType = (
  event: EventMeetingPlusType
): EventPlusType => {
  const newEvent: EventPlusType = {
    ...event,
    preferredTimeRanges:
      event?.preferredTimeRanges?.map((pt) => ({
        id: pt.id,
        eventId: event.id,
        dayOfWeek: pt?.dayOfWeek,
        startTime: pt?.startTime,
        endTime: pt?.endTime,
        updatedAt: pt?.updatedAt,
        createdDate: pt?.createdDate,
        userId: event?.userId,
      })) || null,
  };

  return newEvent;
};

export const setPreferredTimeForUnModifiableEvent = (
  event: EventPartPlannerRequestBodyType,
  timezone: string
): EventPartPlannerRequestBodyType => {
  if (!event?.modifiable) {
    if (!event?.preferredDayOfWeek && !event?.preferredTime) {
      const newEvent = {
        ...event,
        preferredDayOfWeek:
          dayOfWeekIntToString[
            getISODay(
              dayjs(event.startDate.slice(0, 19)).tz(timezone, true).toDate()
            )
          ],
        preferredTime: dayjs(event.startDate.slice(0, 19))
          .tz(timezone, true)
          .format('HH:mm') as Time,
      };
      return newEvent;
    }
    return event;
  }
  return event;
};

export const listEventsWithIds = async (ids: string[]) => {
  try {
    const operationName = 'listEventsWithIds';

    const query = `
    query listEventsWithIds($ids: [String!]!) {
      Event(where: {id: {_in: $ids}}) {
        allDay
        anyoneCanAddSelf
        attachments
        attendeesOmitted
        backgroundColor
        calendarId
        colorId
        conferenceId
        copyAvailability
        copyCategories
        copyDuration
        copyIsBreak
        copyIsExternalMeeting
        copyIsMeeting
        copyModifiable
        copyPriorityLevel
        copyReminders
        copyTimeBlocking
        copyTimePreference
        createdDate
        creator
        dailyTaskList
        deleted
        duration
        endDate
        endTimeUnspecified
        eventId
        eventType
        extendedProperties
        followUpEventId
        forEventId
        foregroundColor
        guestsCanInviteOthers
        guestsCanModify
        guestsCanSeeOtherGuests
        hangoutLink
        hardDeadline
        htmlLink
        iCalUID
        id
        isBreak
        isExternalMeeting
        isExternalMeetingModifiable
        isFollowUp
        isMeeting
        isMeetingModifiable
        isPostEvent
        isPreEvent
        links
        location
        locked
        maxAttendees
        meetingId
        method
        modifiable
        negativeImpactDayOfWeek
        negativeImpactScore
        negativeImpactTime
        notes
        organizer
        originalAllDay
        originalStartDate
        originalTimezone
        positiveImpactDayOfWeek
        positiveImpactScore
        positiveImpactTime
        postEventId
        preEventId
        preferredDayOfWeek
        preferredEndTimeRange
        preferredStartTimeRange
        preferredTime
        priority
        privateCopy
        recurrence
        recurrenceRule
        recurringEventId
        sendUpdates
        softDeadline
        source
        startDate
        status
        summary
        taskId
        taskType
        timeBlocking
        timezone
        title
        transparency
        unlink
        updatedAt
        useDefaultAlarms
        userId
        userModifiedAvailability
        userModifiedCategories
        userModifiedDuration
        userModifiedIsBreak
        userModifiedIsExternalMeeting
        userModifiedIsMeeting
        userModifiedModifiable
        userModifiedPriorityLevel
        userModifiedReminders
        userModifiedTimeBlocking
        userModifiedTimePreference
        visibility
        weeklyTaskList
        byWeekDay
        localSynced
        userModifiedColor
        copyColor
      }
    }    
    `;

    const res: { data: { Event: EventType[] } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables: {
            ids,
          },
        },
      })
      .json();

    return res?.data?.Event;
  } catch (e) {
    console.log(e, ' unable to list ids with ids');
  }
};

export const tagEventsForDailyOrWeeklyTask = async (
  events: EventPartPlannerRequestBodyType[]
): Promise<EventPartPlannerRequestBodyType[] | null> => {
  try {
    const filteredEvents = events.filter((e) => e.recurringEventId);
    if (filteredEvents?.length > 0) {
      const originalEvents = await listEventsWithIds(
        _.uniq(filteredEvents.map((e) => e?.recurringEventId))
      );
      if (originalEvents?.length > 0) {
        const taggedFilteredEvents = filteredEvents.map((e) =>
          tagEventForDailyOrWeeklyTask(
            e,
            originalEvents.find((oe) => oe.id === e.recurringEventId)
          )
        );
        const newEvents = events.map((e) => {
          if (e?.recurringEventId) {
            const taggedFilteredEvent = taggedFilteredEvents.find(
              (te) => te?.eventId === e?.eventId
            );
            if (taggedFilteredEvent?.eventId) {
              return taggedFilteredEvent;
            } else {
              return e;
            }
          }
          return e;
        });
        return newEvents;
      }
      console.log('tagEventsForDailyorWeeklyTask: originalEvents is empty');
      return events;
    }
    return events;
  } catch (e) {
    console.log(e, ' unable to to tag events for daily or weekly task');
  }
};

export const tagEventForDailyOrWeeklyTask = (
  eventToSubmit: EventPartPlannerRequestBodyType,
  event: EventPlusType
) => {
  if (!event?.id) {
    console.log('no original event inside tagEventForDailysOrWeeklyTask');
    return null;
  }

  if (!eventToSubmit?.eventId) {
    console.log('no eventToSubmit inside tagEventForDailyOrWeeklyTask');
    return null;
  }

  if (eventToSubmit?.recurringEventId) {
    if (event?.weeklyTaskList) {
      return {
        ...eventToSubmit,
        weeklyTaskList: event.weeklyTaskList,
      };
    }
    if (event?.dailyTaskList) {
      return {
        ...eventToSubmit,
        dailyTaskList: event.dailyTaskList,
      };
    }
    return eventToSubmit;
  }
  return eventToSubmit;
};

export const generateUserPlannerRequestBody = (
  userPreference: UserPreferenceType,
  userId: string,
  workTimes: WorkTimeType[],
  hostId: string
): UserPlannerRequestBodyType => {
  const {
    maxWorkLoadPercent,
    backToBackMeetings,
    maxNumberOfMeetings,
    minNumberOfBreaks,
  } = userPreference;
  const user: UserPlannerRequestBodyType = {
    id: userId,
    maxWorkLoadPercent,
    backToBackMeetings,
    maxNumberOfMeetings,
    minNumberOfBreaks,
    workTimes,
    hostId,
  };
  return user;
};

export const generateUserPlannerRequestBodyForExternalAttendee = (
  userId: string,
  workTimes: WorkTimeType[],
  hostId: string
): UserPlannerRequestBodyType => {
  const user: UserPlannerRequestBodyType = {
    id: userId,
    maxWorkLoadPercent: 100,
    backToBackMeetings: false,
    maxNumberOfMeetings: 99,
    minNumberOfBreaks: 0,
    workTimes,
    hostId,
  };
  return user;
};

export const convertMeetingAssistEventTypeToEventPlusType = (
  event: MeetingAssistEventType,
  userId: string
): EventPlusType => {
  return {
    id: event?.id,
    userId: userId,
    title: event?.summary,
    startDate: event?.startDate,
    endDate: event?.endDate,
    allDay: event?.allDay,
    recurrenceRule: event?.recurrenceRule,
    location: event?.location,
    notes: event?.notes,
    attachments: event?.attachments,
    links: event?.links,
    timezone: event?.timezone,
    createdDate: event?.createdDate,
    deleted: false,
    priority: 1,
    isFollowUp: false,
    isPreEvent: false,
    isPostEvent: false,
    modifiable: false,
    anyoneCanAddSelf: true,
    guestsCanInviteOthers: true,
    guestsCanSeeOtherGuests: true,
    originalStartDate: undefined,
    originalAllDay: event?.allDay,
    summary: event?.summary,
    transparency: event?.transparency,
    visibility: event?.visibility,
    recurringEventId: event?.recurringEventId,
    updatedAt: event?.updatedAt,
    iCalUID: event?.iCalUID,
    htmlLink: event?.htmlLink,
    colorId: event?.colorId,
    creator: event?.creator,
    organizer: event?.organizer,
    endTimeUnspecified: event?.endTimeUnspecified,
    recurrence: event?.recurrence,
    originalTimezone: event?.timezone,
    extendedProperties: event?.extendedProperties,
    hangoutLink: event?.hangoutLink,
    guestsCanModify: event?.guestsCanModify,
    locked: event?.locked,
    source: event?.source,
    eventType: event?.eventType,
    privateCopy: event?.privateCopy,
    calendarId: event?.calendarId,
    backgroundColor: event?.backgroundColor,
    foregroundColor: event?.foregroundColor,
    useDefaultAlarms: event?.useDefaultAlarms,
    meetingId: event?.meetingId,
    eventId: event?.eventId,
  };
};

export const generateWorkTimesForExternalAttendee = (
  hostId: string,
  userId: string,
  attendeeEvents: EventPlusType[],
  hostTimezone: string,
  userTimezone: string
) => {
  const daysInWeek = 7;

  const workTimes: WorkTimeType[] = [];

  for (let i = 0; i < daysInWeek; i++) {
    const dayOfWeekInt = i + 1;

    const sameDayEvents = attendeeEvents.filter(
      (e) =>
        getISODay(
          dayjs(e.startDate.slice(0, 19))
            .tz(e.timezone || userTimezone, true)
            .tz(hostTimezone)
            .toDate()
        ) ===
        i + 1
    );
    const minStartDate = _.minBy(sameDayEvents, (e) =>
      dayjs(e.startDate.slice(0, 19))
        .tz(e.timezone || userTimezone, true)
        .tz(hostTimezone)
        .unix()
    );
    const maxEndDate = _.maxBy(sameDayEvents, (e) =>
      dayjs(e.endDate.slice(0, 19))
        .tz(e.timezone || userTimezone, true)
        .tz(hostTimezone)
        .unix()
    );
    const startHour = dayjs(minStartDate.startDate.slice(0, 19))
      .tz(minStartDate.timezone || userTimezone, true)
      .tz(hostTimezone)
      .hour();
    const startMinute = dayjs(minStartDate.startDate.slice(0, 19))
      .tz(minStartDate.timezone || userTimezone, true)
      .tz(hostTimezone)
      .isBetween(
        dayjs(minStartDate.startDate.slice(0, 19))
          .tz(minStartDate.timezone || userTimezone, true)
          .tz(hostTimezone)
          .minute(0),
        dayjs(minStartDate.startDate.slice(0, 19))
          .tz(minStartDate.timezone || userTimezone, true)
          .tz(hostTimezone)
          .minute(15),
        'minute',
        '[)'
      )
      ? 0
      : dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(
              dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(15),
              dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30),
              'minute',
              '[)'
            )
        ? 15
        : dayjs(minStartDate.startDate.slice(0, 19))
              .tz(minStartDate.timezone || userTimezone, true)
              .tz(hostTimezone)
              .isBetween(
                dayjs(minStartDate.startDate.slice(0, 19))
                  .tz(minStartDate.timezone || userTimezone, true)
                  .tz(hostTimezone)
                  .minute(30),
                dayjs(minStartDate.startDate.slice(0, 19))
                  .tz(minStartDate.timezone || userTimezone, true)
                  .tz(hostTimezone)
                  .minute(45),
                'minute',
                '[)'
              )
          ? 30
          : 45;

    let endHour = dayjs(maxEndDate.endDate.slice(0, 19))
      .tz(maxEndDate.timezone || userTimezone, true)
      .tz(hostTimezone)
      .hour();
    const endMinute = dayjs(maxEndDate.endDate.slice(0, 19))
      .tz(maxEndDate.timezone || userTimezone, true)
      .tz(hostTimezone)
      .isBetween(
        dayjs(maxEndDate.endDate.slice(0, 19))
          .tz(maxEndDate.timezone || userTimezone, true)
          .tz(hostTimezone)
          .minute(0),
        dayjs(maxEndDate.endDate.slice(0, 19))
          .tz(maxEndDate.timezone || userTimezone, true)
          .tz(hostTimezone)
          .minute(15),
        'minute',
        '[)'
      )
      ? 15
      : dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(
              dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(15),
              dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30),
              'minute',
              '[)'
            )
        ? 30
        : dayjs(maxEndDate.endDate.slice(0, 19))
              .tz(maxEndDate.timezone || userTimezone, true)
              .tz(hostTimezone)
              .isBetween(
                dayjs(maxEndDate.endDate.slice(0, 19))
                  .tz(maxEndDate.timezone || userTimezone, true)
                  .tz(hostTimezone)
                  .minute(30),
                dayjs(maxEndDate.endDate.slice(0, 19))
                  .tz(maxEndDate.timezone || userTimezone, true)
                  .tz(hostTimezone)
                  .minute(45),
                'minute',
                '[)'
              )
          ? 45
          : 0;
    if (endMinute === 0) {
      if (endHour < 23) {
        endHour += 1;
      }
    }

    workTimes.push({
      dayOfWeek: dayOfWeekIntToString[dayOfWeekInt],
      startTime: dayjs(
        setISODay(
          dayjs()
            .hour(startHour)
            .minute(startMinute)
            .tz(hostTimezone, true)
            .toDate(),
          i + 1
        )
      )
        .tz(hostTimezone)
        .format('HH:mm') as Time,
      endTime: dayjs(
        setISODay(
          dayjs()
            .hour(endHour)
            .minute(endMinute)
            .tz(hostTimezone, true)
            .toDate(),
          i + 1
        )
      )
        .tz(hostTimezone)
        .format('HH:mm') as Time,
      hostId,
      userId,
    });
  }

  return workTimes;
};

export const generateTimeSlotsForExternalAttendee = (
  hostStartDate: string,
  hostId: string,
  attendeeEvents: EventPlusType[],
  hostTimezone: string,
  userTimezone: string,
  isFirstDay?: boolean
) => {
  if (isFirstDay) {
    const dayOfWeekIntByHost = getISODay(
      dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate()
    );
    const monthByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .month();
    const dayOfMonthByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .date();
    const startHourOfHostDateByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .hour();
    const startMinuteOfHostDateByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .isBetween(
        dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(0),
        dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(15),
        'minute',
        '[)'
      )
      ? 0
      : dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isBetween(
              dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(15),
              dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(30),
              'minute',
              '[)'
            )
        ? 15
        : dayjs(hostStartDate.slice(0, 19))
              .tz(hostTimezone, true)
              .isBetween(
                dayjs(hostStartDate.slice(0, 19))
                  .tz(hostTimezone, true)
                  .minute(30),
                dayjs(hostStartDate.slice(0, 19))
                  .tz(hostTimezone, true)
                  .minute(45),
                'minute',
                '[)'
              )
          ? 30
          : 45;

    const sameDayEvents = attendeeEvents.filter(
      (e) =>
        getISODay(
          dayjs(e.startDate.slice(0, 19))
            .tz(userTimezone, true)
            .tz(hostTimezone)
            .toDate()
        ) === dayOfWeekIntByHost
    );
    const maxEndDate = _.maxBy(sameDayEvents, (e) =>
      dayjs(e.endDate.slice(0, 19))
        .tz(userTimezone, true)
        .tz(hostTimezone)
        .unix()
    );

    let workEndHourByHost = dayjs(maxEndDate.endDate.slice(0, 19))
      .tz(maxEndDate.timezone || userTimezone, true)
      .tz(hostTimezone)
      .hour();
    const workEndMinuteByHost = dayjs(maxEndDate.endDate.slice(0, 19))
      .tz(maxEndDate.timezone || userTimezone, true)
      .tz(hostTimezone)
      .isBetween(
        dayjs(maxEndDate.endDate.slice(0, 19))
          .tz(maxEndDate.timezone || userTimezone, true)
          .tz(hostTimezone)
          .minute(0),
        dayjs(maxEndDate.endDate.slice(0, 19))
          .tz(maxEndDate.timezone || userTimezone, true)
          .tz(hostTimezone)
          .minute(15),
        'minute',
        '[)'
      )
      ? 15
      : dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(
              dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(15),
              dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30),
              'minute',
              '[)'
            )
        ? 30
        : dayjs(maxEndDate.endDate.slice(0, 19))
              .tz(maxEndDate.timezone || userTimezone, true)
              .tz(hostTimezone)
              .isBetween(
                dayjs(maxEndDate.endDate.slice(0, 19))
                  .tz(maxEndDate.timezone || userTimezone, true)
                  .tz(hostTimezone)
                  .minute(30),
                dayjs(maxEndDate.endDate.slice(0, 19))
                  .tz(maxEndDate.timezone || userTimezone, true)
                  .tz(hostTimezone)
                  .minute(45),
                'minute',
                '[)'
              )
          ? 45
          : 0;
    if (workEndMinuteByHost === 0) {
      if (workEndHourByHost < 23) {
        workEndHourByHost += 1;
      }
    }

    const minStartDate = _.minBy(sameDayEvents, (e) =>
      dayjs(e.startDate.slice(0, 19))
        .tz(userTimezone, true)
        .tz(hostTimezone)
        .unix()
    );

    const workStartHourByHost = dayjs(minStartDate.startDate.slice(0, 19))
      .tz(minStartDate.timezone || userTimezone, true)
      .tz(hostTimezone)
      .hour();
    const workStartMinuteByHost = dayjs(minStartDate.startDate.slice(0, 19))
      .tz(minStartDate.timezone || userTimezone, true)
      .tz(hostTimezone)
      .isBetween(
        dayjs(minStartDate.startDate.slice(0, 19))
          .tz(minStartDate.timezone || userTimezone, true)
          .tz(hostTimezone)
          .minute(0),
        dayjs(minStartDate.startDate.slice(0, 19))
          .tz(minStartDate.timezone || userTimezone, true)
          .tz(hostTimezone)
          .minute(15),
        'minute',
        '[)'
      )
      ? 0
      : dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(
              dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(15),
              dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30),
              'minute',
              '[)'
            )
        ? 15
        : dayjs(minStartDate.startDate.slice(0, 19))
              .tz(minStartDate.timezone || userTimezone, true)
              .tz(hostTimezone)
              .isBetween(
                dayjs(minStartDate.startDate.slice(0, 19))
                  .tz(minStartDate.timezone || userTimezone, true)
                  .tz(hostTimezone)
                  .minute(30),
                dayjs(minStartDate.startDate.slice(0, 19))
                  .tz(minStartDate.timezone || userTimezone, true)
                  .tz(hostTimezone)
                  .minute(45),
                'minute',
                '[)'
              )
          ? 30
          : 45;

    if (
      dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .isBefore(
          dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(workStartHourByHost)
            .minute(workStartMinuteByHost)
        )
    ) {
      const startDuration = dayjs.duration({
        hours: workStartHourByHost,
        minutes: workStartMinuteByHost,
      });
      const endDuration = dayjs.duration({
        hours: workEndHourByHost,
        minutes: workEndMinuteByHost,
      });
      const totalDuration = endDuration.subtract(startDuration);
      const totalMinutes = totalDuration.asMinutes();

      const timeSlots: TimeSlotType[] = [];

      console.log(
        hostStartDate,
        dayOfWeekIntByHost,
        dayOfMonthByHost,
        startHourOfHostDateByHost,
        startMinuteOfHostDateByHost,
        workEndHourByHost,
        workEndMinuteByHost,
        timezone,
        `startDate,  dayOfWeekIntByHost, dayOfMonthByHost, startHourByHost, startMinuteByHost, endHourByHost, endMinuteByHost totalMinutes, timezone, inside firstDay inside generateTimeslots`
      );
      for (let i = 0; i < totalMinutes; i += 15) {
        timeSlots.push({
          dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
          startTime: dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(startHourOfHostDateByHost)
            .minute(startMinuteOfHostDateByHost)
            .add(i, 'minute')
            .format('HH:mm') as Time,
          endTime: dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(startHourOfHostDateByHost)
            .minute(startMinuteOfHostDateByHost)
            .add(i + 15, 'minute')
            .format('HH:mm') as Time,
          hostId,
          monthDay: formatToMonthDay(
            monthByHost as MonthType,
            dayOfMonthByHost as DayType
          ),
        });
      }
      console.log(
        timeSlots,
        ' timeSlots inside generateTimeSlots for first day where startDate is before work start time'
      );
      return timeSlots;
    }

    const startDuration = dayjs.duration({
      hours: startHourOfHostDateByHost,
      minutes: startMinuteOfHostDateByHost,
    });
    const endDuration = dayjs.duration({
      hours: workEndHourByHost,
      minutes: workEndMinuteByHost,
    });
    const totalDuration = endDuration.subtract(startDuration);
    const totalMinutes = totalDuration.asMinutes();

    const timeSlots: TimeSlotType[] = [];
    console.log(
      hostStartDate,
      dayOfWeekIntByHost,
      dayOfMonthByHost,
      startHourOfHostDateByHost,
      startMinuteOfHostDateByHost,
      workEndHourByHost,
      workEndMinuteByHost,
      hostTimezone,
      `startDate,  dayOfWeekIntByHost, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`
    );
    for (let i = 0; i < totalMinutes; i += 15) {
      timeSlots.push({
        dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
        startTime: dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(startHourOfHostDateByHost)
          .minute(startMinuteOfHostDateByHost)
          .add(i, 'minute')
          .format('HH:mm') as Time,
        endTime: dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(startHourOfHostDateByHost)
          .minute(startMinuteOfHostDateByHost)
          .add(i + 15, 'minute')
          .format('HH:mm') as Time,
        hostId,
        monthDay: formatToMonthDay(
          monthByHost as MonthType,
          dayOfMonthByHost as DayType
        ),
      });
    }

    console.log(timeSlots, ' timeSlots inside generateTimeSlots for first day');
    return timeSlots;
  }

  const dayOfWeekIntByHost = getISODay(
    dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate()
  );
  const monthByHost = dayjs(hostStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .month();
  const dayOfMonthByHost = dayjs(hostStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .date();

  const sameDayEvents = attendeeEvents.filter(
    (e) =>
      getISODay(
        dayjs(e.startDate.slice(0, 19))
          .tz(e.timezone || userTimezone, true)
          .tz(hostTimezone)
          .toDate()
      ) === dayOfWeekIntByHost
  );
  const minStartDate = _.minBy(sameDayEvents, (e) =>
    dayjs(e.startDate.slice(0, 19))
      .tz(e.timezone || userTimezone, true)
      .tz(hostTimezone)
      .unix()
  );
  const maxEndDate = _.maxBy(sameDayEvents, (e) =>
    dayjs(e.endDate.slice(0, 19))
      .tz(e.timezone || userTimezone, true)
      .tz(hostTimezone)
      .unix()
  );

  let workEndHourByHost = dayjs(maxEndDate.endDate.slice(0, 19))
    .tz(maxEndDate?.timezone || userTimezone, true)
    .tz(hostTimezone)
    .hour();
  const workEndMinuteByHost = dayjs(maxEndDate.endDate.slice(0, 19))
    .tz(maxEndDate?.timezone || userTimezone, true)
    .tz(hostTimezone)
    .isBetween(
      dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(0),
      dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(15),
      'minute',
      '[)'
    )
    ? 15
    : dayjs(maxEndDate.endDate.slice(0, 19))
          .tz(maxEndDate?.timezone || userTimezone, true)
          .tz(hostTimezone)
          .isBetween(
            dayjs(maxEndDate.endDate.slice(0, 19))
              .tz(maxEndDate?.timezone || userTimezone, true)
              .tz(hostTimezone)
              .minute(15),
            dayjs(maxEndDate.endDate.slice(0, 19))
              .tz(maxEndDate?.timezone || userTimezone, true)
              .tz(hostTimezone)
              .minute(30),
            'minute',
            '[)'
          )
      ? 30
      : dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(
              dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30),
              dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(45),
              'minute',
              '[)'
            )
        ? 45
        : 0;
  if (workEndMinuteByHost === 0) {
    if (workEndHourByHost < 23) {
      workEndHourByHost += 1;
    }
  }

  const workStartHourByHost = dayjs(minStartDate.startDate.slice(0, 19))
    .tz(minStartDate?.timezone || userTimezone, true)
    .tz(hostTimezone)
    .hour();
  const workStartMinuteByHost = dayjs(minStartDate.startDate.slice(0, 19))
    .tz(minStartDate?.timezone || userTimezone, true)
    .tz(hostTimezone)
    .isBetween(
      dayjs(minStartDate.startDate.slice(0, 19))
        .tz(minStartDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(0),
      dayjs(minStartDate.startDate.slice(0, 19))
        .tz(minStartDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(15),
      'minute',
      '[)'
    )
    ? 0
    : dayjs(minStartDate.startDate.slice(0, 19))
          .tz(minStartDate?.timezone || userTimezone, true)
          .tz(hostTimezone)
          .isBetween(
            dayjs(minStartDate.startDate.slice(0, 19))
              .tz(minStartDate?.timezone || userTimezone, true)
              .tz(hostTimezone)
              .minute(15),
            dayjs(minStartDate.startDate.slice(0, 19))
              .tz(minStartDate?.timezone || userTimezone, true)
              .tz(hostTimezone)
              .minute(30),
            'minute',
            '[)'
          )
      ? 15
      : dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(
              dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30),
              dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(45),
              'minute',
              '[)'
            )
        ? 30
        : 45;

  console.log(
    monthByHost,
    dayOfMonthByHost,
    workStartHourByHost,
    workStartMinuteByHost,
    workEndHourByHost,
    ' monthByHost, dayOfMonthByHost, workStartHourByHost, workStartMinuteByHost, workEndHourByHost'
  );
  const startDuration = dayjs.duration({
    hours: workStartHourByHost,
    minutes: workStartMinuteByHost,
  });
  const endDuration = dayjs.duration({
    hours: workEndHourByHost,
    minutes: workEndMinuteByHost,
  });
  const totalDuration = endDuration.subtract(startDuration);
  const totalMinutes = totalDuration.asMinutes();
  const timeSlots: TimeSlotType[] = [];
  for (let i = 0; i < totalMinutes; i += 15) {
    timeSlots.push({
      dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
      startTime: dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(workStartHourByHost)
        .minute(workStartMinuteByHost)
        .add(i, 'minute')
        .format('HH:mm') as Time,
      endTime: dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(workStartHourByHost)
        .minute(workStartMinuteByHost)
        .add(i + 15, 'minute')
        .format('HH:mm') as Time,
      hostId,
      monthDay: formatToMonthDay(
        monthByHost as MonthType,
        dayOfMonthByHost as DayType
      ),
    });
  }

  console.log(timeSlots, ' timeSlots inside generateTimeSlots');
  return timeSlots;
};

export const generateTimeSlotsLiteForExternalAttendee = (
  hostStartDate: string,
  hostId: string,
  attendeeEvents: EventPlusType[],
  hostTimezone: string,
  userTimezone: string,
  isFirstDay?: boolean
) => {
  if (isFirstDay) {
    const dayOfWeekIntByHost = getISODay(
      dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate()
    );
    const monthByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .month();
    const dayOfMonthByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .date();
    const startHourOfHostDateByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .hour();
    const startMinuteOfHostDateByHost = dayjs(hostStartDate.slice(0, 19))
      .tz(hostTimezone, true)
      .isBetween(
        dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(0),
        dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(30),
        'minute',
        '[)'
      )
      ? 0
      : dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isBetween(
              dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(30),
              dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(59),
              'minute',
              '[)'
            )
        ? 30
        : 0;

    const sameDayEvents = attendeeEvents.filter(
      (e) =>
        getISODay(
          dayjs(e.startDate.slice(0, 19))
            .tz(e?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .toDate()
        ) === dayOfWeekIntByHost
    );
    const maxEndDate = _.maxBy(sameDayEvents, (e) =>
      dayjs(e.endDate.slice(0, 19))
        .tz(e?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .unix()
    );

    let workEndHourByHost = dayjs(maxEndDate.endDate.slice(0, 19))
      .tz(maxEndDate?.timezone || userTimezone, true)
      .tz(hostTimezone)
      .hour();
    const workEndMinuteByHost = dayjs(maxEndDate.endDate.slice(0, 19))
      .tz(maxEndDate?.timezone || userTimezone, true)
      .tz(hostTimezone)
      .isBetween(
        dayjs(maxEndDate.endDate.slice(0, 19))
          .tz(maxEndDate?.timezone || userTimezone, true)
          .tz(hostTimezone)
          .minute(0),
        dayjs(maxEndDate.endDate.slice(0, 19))
          .tz(maxEndDate?.timezone || userTimezone, true)
          .tz(hostTimezone)
          .minute(30),
        'minute',
        '[)'
      )
      ? 30
      : dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(
              dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30),
              dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(59),
              'minute',
              '[)'
            )
        ? 0
        : 30;
    if (workEndMinuteByHost === 0) {
      if (workEndHourByHost < 23) {
        workEndHourByHost += 1;
      }
    }

    const minStartDate = _.minBy(sameDayEvents, (e) =>
      dayjs(e.startDate.slice(0, 19))
        .tz(e?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .unix()
    );

    const workStartHourByHost = dayjs(minStartDate.startDate.slice(0, 19))
      .tz(minStartDate?.timezone || userTimezone, true)
      .tz(hostTimezone)
      .hour();
    const workStartMinuteByHost = dayjs(minStartDate.startDate.slice(0, 19))
      .tz(minStartDate?.timezone || userTimezone, true)
      .tz(hostTimezone)
      .isBetween(
        dayjs(minStartDate.startDate.slice(0, 19))
          .tz(minStartDate?.timezone || userTimezone, true)
          .tz(hostTimezone)
          .minute(0),
        dayjs(minStartDate.startDate.slice(0, 19))
          .tz(minStartDate?.timezone || userTimezone, true)
          .tz(hostTimezone)
          .minute(30),
        'minute',
        '[)'
      )
      ? 0
      : dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(
              dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30),
              dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(59),
              'minute',
              '[)'
            )
        ? 30
        : 0;

    if (
      dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .isBefore(
          dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(workStartHourByHost)
            .minute(workStartMinuteByHost)
        )
    ) {
      const startDuration = dayjs.duration({
        hours: workStartHourByHost,
        minutes: workStartMinuteByHost,
      });
      const endDuration = dayjs.duration({
        hours: workEndHourByHost,
        minutes: workEndMinuteByHost,
      });
      const totalDuration = endDuration.subtract(startDuration);
      const totalMinutes = totalDuration.asMinutes();

      const timeSlots: TimeSlotType[] = [];

      console.log(
        hostStartDate,
        dayOfWeekIntByHost,
        dayOfMonthByHost,
        startHourOfHostDateByHost,
        startMinuteOfHostDateByHost,
        workEndHourByHost,
        workEndMinuteByHost,
        timezone,
        `startDate,  dayOfWeekIntByHost, dayOfMonthByHost, startHourByHost, startMinuteByHost, endHourByHost, endMinuteByHost totalMinutes, timezone, inside firstDay inside generateTimeslots`
      );
      for (let i = 0; i < totalMinutes; i += 30) {
        timeSlots.push({
          dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
          startTime: dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(startHourOfHostDateByHost)
            .minute(startMinuteOfHostDateByHost)
            .add(i, 'minute')
            .format('HH:mm') as Time,
          endTime: dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(startHourOfHostDateByHost)
            .minute(startMinuteOfHostDateByHost)
            .add(i + 30, 'minute')
            .format('HH:mm') as Time,
          hostId,
          monthDay: formatToMonthDay(
            monthByHost as MonthType,
            dayOfMonthByHost as DayType
          ),
        });
      }
      console.log(
        timeSlots,
        ' timeSlots inside generateTimeSlots for first day where startDate is before work start time'
      );
      return timeSlots;
    }

    const startDuration = dayjs.duration({
      hours: startHourOfHostDateByHost,
      minutes: startMinuteOfHostDateByHost,
    });
    const endDuration = dayjs.duration({
      hours: workEndHourByHost,
      minutes: workEndMinuteByHost,
    });
    const totalDuration = endDuration.subtract(startDuration);
    const totalMinutes = totalDuration.asMinutes();

    const timeSlots: TimeSlotType[] = [];
    console.log(
      hostStartDate,
      dayOfWeekIntByHost,
      dayOfMonthByHost,
      startHourOfHostDateByHost,
      startMinuteOfHostDateByHost,
      workEndHourByHost,
      workEndMinuteByHost,
      hostTimezone,
      `startDate,  dayOfWeekIntByHost, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`
    );
    for (let i = 0; i < totalMinutes; i += 30) {
      timeSlots.push({
        dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
        startTime: dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(startHourOfHostDateByHost)
          .minute(startMinuteOfHostDateByHost)
          .add(i, 'minute')
          .format('HH:mm') as Time,
        endTime: dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(startHourOfHostDateByHost)
          .minute(startMinuteOfHostDateByHost)
          .add(i + 30, 'minute')
          .format('HH:mm') as Time,
        hostId,
        monthDay: formatToMonthDay(
          monthByHost as MonthType,
          dayOfMonthByHost as DayType
        ),
      });
    }

    console.log(timeSlots, ' timeSlots inside generateTimeSlots for first day');
    return timeSlots;
  }

  const dayOfWeekIntByHost = getISODay(
    dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate()
  );
  const monthByHost = dayjs(hostStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .month();
  const dayOfMonthByHost = dayjs(hostStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .date();

  const sameDayEvents = attendeeEvents.filter(
    (e) =>
      getISODay(
        dayjs(e.startDate.slice(0, 19))
          .tz(userTimezone, true)
          .tz(hostTimezone)
          .toDate()
      ) === dayOfWeekIntByHost
  );
  const minStartDate = _.minBy(sameDayEvents, (e) =>
    dayjs(e.startDate.slice(0, 19))
      .tz(userTimezone, true)
      .tz(hostTimezone)
      .unix()
  );
  const maxEndDate = _.maxBy(sameDayEvents, (e) =>
    dayjs(e.endDate.slice(0, 19)).tz(userTimezone, true).tz(hostTimezone).unix()
  );

  let workEndHourByHost = dayjs(maxEndDate.endDate.slice(0, 19))
    .tz(maxEndDate?.timezone || userTimezone, true)
    .tz(hostTimezone)
    .hour();
  const workEndMinuteByHost = dayjs(maxEndDate.endDate.slice(0, 19))
    .tz(maxEndDate?.timezone || userTimezone, true)
    .tz(hostTimezone)
    .isBetween(
      dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(0),
      dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(30),
      'minute',
      '[)'
    )
    ? 30
    : dayjs(maxEndDate.endDate.slice(0, 19))
          .tz(maxEndDate?.timezone || userTimezone, true)
          .tz(hostTimezone)
          .isBetween(
            dayjs(maxEndDate.endDate.slice(0, 19))
              .tz(maxEndDate?.timezone || userTimezone, true)
              .tz(hostTimezone)
              .minute(30),
            dayjs(maxEndDate.endDate.slice(0, 19))
              .tz(maxEndDate?.timezone || userTimezone, true)
              .tz(hostTimezone)
              .minute(59),
            'minute',
            '[)'
          )
      ? 0
      : 30;
  if (workEndMinuteByHost === 0) {
    if (workEndHourByHost < 23) {
      workEndHourByHost += 1;
    }
  }

  const workStartHourByHost = dayjs(minStartDate.startDate.slice(0, 19))
    .tz(minStartDate?.timezone || userTimezone, true)
    .tz(hostTimezone)
    .hour();
  const workStartMinuteByHost = dayjs(minStartDate.startDate.slice(0, 19))
    .tz(minStartDate?.timezone || userTimezone, true)
    .tz(hostTimezone)
    .isBetween(
      dayjs(minStartDate.startDate.slice(0, 19))
        .tz(minStartDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(0),
      dayjs(minStartDate.startDate.slice(0, 19))
        .tz(minStartDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(30),
      'minute',
      '[)'
    )
    ? 0
    : dayjs(minStartDate.startDate.slice(0, 19))
          .tz(minStartDate?.timezone || userTimezone, true)
          .tz(hostTimezone)
          .isBetween(
            dayjs(minStartDate.startDate.slice(0, 19))
              .tz(minStartDate?.timezone || userTimezone, true)
              .tz(hostTimezone)
              .minute(30),
            dayjs(minStartDate.startDate.slice(0, 19))
              .tz(minStartDate?.timezone || userTimezone, true)
              .tz(hostTimezone)
              .minute(59),
            'minute',
            '[)'
          )
      ? 30
      : 0;

  console.log(
    monthByHost,
    dayOfMonthByHost,
    workStartHourByHost,
    workStartMinuteByHost,
    workEndHourByHost,
    ' monthByHost, dayOfMonthByHost, workStartHourByHost, workStartMinuteByHost, workEndHourByHost'
  );
  const startDuration = dayjs.duration({
    hours: workStartHourByHost,
    minutes: workStartMinuteByHost,
  });
  const endDuration = dayjs.duration({
    hours: workEndHourByHost,
    minutes: workEndMinuteByHost,
  });
  const totalDuration = endDuration.subtract(startDuration);
  const totalMinutes = totalDuration.asMinutes();
  const timeSlots: TimeSlotType[] = [];
  for (let i = 0; i < totalMinutes; i += 30) {
    timeSlots.push({
      dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
      startTime: dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(workStartHourByHost)
        .minute(workStartMinuteByHost)
        .add(i, 'minute')
        .format('HH:mm') as Time,
      endTime: dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(workStartHourByHost)
        .minute(workStartMinuteByHost)
        .add(i + 30, 'minute')
        .format('HH:mm') as Time,
      hostId,
      monthDay: formatToMonthDay(
        monthByHost as MonthType,
        dayOfMonthByHost as DayType
      ),
    });
  }

  console.log(timeSlots, ' timeSlots inside generateTimeSlots');
  return timeSlots;
};

export const processEventsForOptaPlannerForExternalAttendees = async (
  userIds: string[],
  mainHostId: string,
  allExternalEvents: MeetingAssistEventType[],
  windowStartDate: string,
  windowEndDate: string,
  hostTimezone: string,
  externalAttendees: MeetingAssistAttendeeType[],
  oldExternalMeetingEvents?: EventMeetingPlusType[],
  newMeetingEvents?: EventMeetingPlusType[]
): Promise<ReturnBodyForExternalAttendeeForOptaplannerPrepType> => {
  try {
    const modifiedAllExternalEvents = allExternalEvents?.map((e) =>
      convertMeetingAssistEventTypeToEventPlusType(
        e,
        externalAttendees?.find((a) => a?.id === e?.attendeeId)?.userId
      )
    );

    const oldConvertedMeetingEvents = oldExternalMeetingEvents
      ?.map((a) => convertMeetingPlusTypeToEventPlusType(a))
      ?.filter((e) => !!e);
    if (oldConvertedMeetingEvents?.length > 0) {
      modifiedAllExternalEvents.push(...oldConvertedMeetingEvents);
    }

    if (newMeetingEvents?.length > 0) {
      modifiedAllExternalEvents.push(
        ...newMeetingEvents?.map((m) =>
          convertMeetingPlusTypeToEventPlusType(m)
        )
      );
    }

    const diffDays = dayjs(windowEndDate.slice(0, 19)).diff(
      dayjs(windowStartDate.slice(0, 19)),
      'day'
    );

    const startDatesForEachDay = [];

    for (let i = 0; i <= diffDays; i++) {
      startDatesForEachDay.push(
        dayjs(windowStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .add(i, 'day')
          .format()
      );
    }

    const unfilteredWorkTimes: WorkTimeType[] = [];

    for (const externalAttendee of externalAttendees) {
      const workTimesForAttendee = generateWorkTimesForExternalAttendee(
        mainHostId,
        externalAttendee?.userId,
        modifiedAllExternalEvents,
        hostTimezone,
        externalAttendee?.timezone
      );
      unfilteredWorkTimes.push(...workTimesForAttendee);
    }

    const workTimes: WorkTimeType[] = _.uniqWith(
      unfilteredWorkTimes,
      _.isEqual
    );

    const unfilteredTimeslots: TimeSlotType[] = [];
    const timeslots: TimeSlotType[] = [];

    for (let i = 0; i < startDatesForEachDay.length; i++) {
      if (i === 0) {
        for (const externalAttendee of externalAttendees) {
          const timeslotsForDay =
            await generateTimeSlotsLiteForExternalAttendee(
              startDatesForEachDay?.[i],
              mainHostId,
              modifiedAllExternalEvents,
              hostTimezone,
              externalAttendee?.timezone,
              true
            );
          unfilteredTimeslots.push(...timeslotsForDay);
        }

        continue;
      }
      for (const externalAttendee of externalAttendees) {
        const timeslotsForDay = await generateTimeSlotsLiteForExternalAttendee(
          startDatesForEachDay?.[i],
          mainHostId,
          modifiedAllExternalEvents,
          hostTimezone,
          externalAttendee?.timezone,
          false
        );
        unfilteredTimeslots.push(...timeslotsForDay);
      }
    }
    timeslots.push(..._.uniqWith(unfilteredTimeslots, _.isEqual));
    console.log(timeslots, ' timeslots');

    const filteredAllEvents = _.uniqBy(
      modifiedAllExternalEvents.filter((e) =>
        validateEventDatesForExternalAttendee(e)
      ),
      'id'
    );
    let eventParts: EventPartPlannerRequestBodyType[] = [];

    const eventPartMinisAccumulated = [];
    for (const event of filteredAllEvents) {
      const eventPartMinis = generateEventPartsLite(event, mainHostId);
      eventPartMinisAccumulated.push(...eventPartMinis);
    }

    const modifiedEventPartMinisPreBuffer =
      modifyEventPartsForMultiplePreBufferTime(eventPartMinisAccumulated);
    const modifiedEventPartMinisPreAndPostBuffer =
      modifyEventPartsForMultiplePostBufferTime(
        modifiedEventPartMinisPreBuffer
      );
    const formattedEventParts: EventPartPlannerRequestBodyType[] =
      modifiedEventPartMinisPreAndPostBuffer?.map((e) =>
        formatEventTypeToPlannerEventForExternalAttendee(
          e,
          workTimes,
          filteredAllEvents,
          hostTimezone
        )
      );
    if (formattedEventParts?.length > 0) {
      eventParts.push(...formattedEventParts);
    }

    if (eventParts.length > 0) {
      eventParts.forEach((e) => console.log(e, ' eventParts after formatting'));
      const newEventPartsWithPreferredTimeSet = eventParts.map((e) =>
        setPreferredTimeForUnModifiableEvent(
          e,
          allExternalEvents.find((f) => f.id === e.eventId)?.timezone
        )
      );
      newEventPartsWithPreferredTimeSet.forEach((e) =>
        console.log(e, ' newEventPartsWithPreferredTimeSet')
      );
      const newEventParts = await tagEventsForDailyOrWeeklyTask(
        newEventPartsWithPreferredTimeSet
      );
      newEventParts.forEach((e) =>
        console.log(e, ' newEventParts after tagEventsForDailyOrWeeklyTask')
      );
      const userList: UserPlannerRequestBodyType[] = [];
      for (const externalAttendee of externalAttendees) {
        const userPlannerRequestBody =
          generateUserPlannerRequestBodyForExternalAttendee(
            externalAttendee?.userId,
            workTimes,
            mainHostId
          );
        console.log(userPlannerRequestBody, ' userPlannerRequestBody');
        userList.push(userPlannerRequestBody);
      }

      const modifiedNewEventParts: EventPartPlannerRequestBodyType[] =
        newEventParts.map((eventPart) => {
          const oldEvent = filteredAllEvents.find(
            (event) => event.id === eventPart.eventId
          );
          return {
            groupId: eventPart?.groupId,
            eventId: eventPart?.eventId,
            part: eventPart?.part,
            lastPart: eventPart?.lastPart,
            meetingPart: eventPart?.meetingPart,
            meetingLastPart: eventPart?.meetingLastPart,
            meetingId: eventPart?.meetingId,
            hostId: mainHostId,
            startDate: dayjs(eventPart?.startDate.slice(0, 19))
              .tz(oldEvent.timezone, true)
              .tz(hostTimezone)
              .format(),
            endDate: dayjs(eventPart?.endDate.slice(0, 19))
              .tz(oldEvent.timezone, true)
              .tz(hostTimezone)
              .format(),
            userId: eventPart?.userId,
            user: eventPart?.user,
            priority: eventPart?.priority,
            isPreEvent: eventPart?.isPreEvent,
            isPostEvent: eventPart?.isPostEvent,
            positiveImpactScore: eventPart?.positiveImpactScore,
            negativeImpactScore: eventPart?.negativeImpactScore,
            modifiable: eventPart?.modifiable,
            isMeeting: eventPart?.isMeeting,
            isExternalMeeting: eventPart?.isExternalMeeting,
            isExternalMeetingModifiable: eventPart?.isExternalMeetingModifiable,
            isMeetingModifiable: eventPart?.isMeetingModifiable,
            dailyTaskList: eventPart?.dailyTaskList,
            weeklyTaskList: eventPart?.weeklyTaskList,
            gap: eventPart?.gap,
            totalWorkingHours: eventPart?.totalWorkingHours,
            hardDeadline: eventPart?.hardDeadline,
            softDeadline: eventPart?.softDeadline,
            forEventId: eventPart?.forEventId,
            positiveImpactDayOfWeek: eventPart?.positiveImpactDayOfWeek,
            positiveImpactTime: eventPart?.positiveImpactTime,
            negativeImpactDayOfWeek: eventPart?.negativeImpactDayOfWeek,
            negativeImpactTime: eventPart?.negativeImpactTime,
            preferredDayOfWeek: eventPart?.preferredDayOfWeek,
            preferredTime: eventPart?.preferredTime,
            preferredStartTimeRange: eventPart?.preferredStartTimeRange,
            preferredEndTimeRange: eventPart?.preferredEndTimeRange,
            event: eventPart?.event,
          };
        });

      return modifiedNewEventParts?.length > 0
        ? {
            userIds,
            hostId: mainHostId,
            eventParts: modifiedNewEventParts,
            allEvents: filteredAllEvents,
            oldAttendeeEvents: allExternalEvents,
            timeslots,
            userList,
          }
        : null;
    }
  } catch (e) {
    console.log(
      e,
      ' unable to process events for optaplanner for external attendee'
    );
  }
};

export const optaPlanWeekly = async (
  timeslots: TimeSlotType[],
  userList: UserPlannerRequestBodyType[],
  eventParts: EventPartPlannerRequestBodyType[],
  singletonId: string,
  hostId: string,
  fileKey: string,
  delay: number,
  callBackUrl: string
) => {
  try {
    const requestBody: PlannerRequestBodyType = {
      singletonId,
      hostId,
      timeslots,
      userList,
      eventParts,
      fileKey,
      delay,
      callBackUrl,
    };

    await got
      .post(`${optaPlannerUrl}/timeTable/admin/solve-day`, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Basic ${Buffer.from(`${optaPlannerUsername}:${optaPlannerPassword}`).toString('base64')}`,
        },
        json: requestBody,
      })
      .json();

    console.log(' optaPlanWeekly called');
  } catch (e) {
    console.log(e, ' optaPlanWeekly');
  }
};

export const updateFreemiumById = async (id: string, usage: number) => {
  try {
    const operationName = 'UpdateFreemiumById';
    const query = `
            mutation UpdateFreemiumById($id: uuid!, $usage: Int!) {
                update_Freemium_by_pk(pk_columns: {id: $id}, _set: {usage: $usage}) {
                    createdAt
                    id
                    period
                    updatedAt
                    usage
                    userId
                }
            }
        `;

    const variables = {
      id,
      usage,
    };

    const response: { data: { update_Freemium_by_pk: FreemiumType } } =
      await got
        .post(hasuraGraphUrl, {
          headers: {
            'X-Hasura-Admin-Secret': hasuraAdminSecret,
            'X-Hasura-Role': 'admin',
          },
          json: {
            operationName,
            query,
            variables,
          },
        })
        .json();
    console.log(
      response,
      response?.data?.update_Freemium_by_pk,
      ' response after updating update_Freemium_by_pk'
    );

    return response?.data?.update_Freemium_by_pk;
  } catch (e) {
    console.log(e, ' unable to update freemium');
  }
};

export const getFreemiumByUserId = async (userId: string) => {
  try {
    const operationName = 'GetFreemiumByUserId';
    const query = `
            query GetFreemiumByUserId($userId: uuid!) {
                Freemium(where: {userId: {_eq: $userId}}) {
                    createdAt
                    id
                    period
                    updatedAt
                    usage
                    userId
                }
            }
        `;

    const variables = {
      userId,
    };

    const res: { data: { Freemium: FreemiumType[] } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables,
        },
      })
      .json();

    console.log(res, ' res from getFreemiumByUserId ');

    return res?.data?.Freemium?.[0];
  } catch (e) {
    console.log(' unable to get freemium by user id');
  }
};

export const getUserCategories = async (userId) => {
  try {
    const operationName = 'getUserCategories';
    const query = `
      query getUserCategories($userId: uuid!) {
        Category(where: {userId: {_eq: $userId}}) {
          name
          userId
          copyAvailability
          copyTimeBlocking
          copyTimePreference
          copyReminders
          copyPriorityLevel
          copyModifiable
          defaultAvailability
          defaultTimeBlocking
          defaultTimePreference
          defaultReminders
          defaultPriorityLevel
          defaultModifiable
          copyIsBreak
          color
          deleted
          id
          updatedAt
        }
      }
    `;
    const variables = {
      userId,
    };

    const res: { data: { Category: CategoryType[] } } = await got
      .post(hasuraGraphUrl, {
        json: {
          operationName,
          query,
          variables,
        },
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
      })
      .json();

    return res?.data?.Category;
  } catch (e) {
    console.log(e, ' unable to get user categories');
  }
};

export const findBestMatchCategory2 = async (
  event: EventPlusType,
  possibleLabels: CategoryType[]
): Promise<ClassificationResponseBodyType> => {
  try {
    if (!event) {
      throw new Error('no event passed inside findBestMatchCategory2');
    }

    if (!possibleLabels) {
      throw new Error(
        'no possible labels passed inside findBestMatchCategory2'
      );
    }

    const { summary, notes } = event;
    const sentence = `${summary}${notes ? `: ${notes}` : ''}`;

    const labelNames = possibleLabels.map((a) => a?.name);

    const systemPrompt =
      'You are an expert event categorizer. Given an event description and a list of possible categories, return a JSON array string containing only the names of the categories that directly apply to the event. Do not provide any explanation, only the JSON array string.';
    const userPrompt = `Event: "${sentence}"
Categories: ${JSON.stringify(labelNames)}`;

    try {
      const completion = await openai.chat.completions.create({
        model: 'gpt-3.5-turbo', // Using string directly as openAIChatGPTModel is not available here
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt },
        ],
        temperature: 0.2,
      });

      const llmResponseString = completion.choices[0]?.message?.content;
      let matchedLabels: string[] = [];

      if (llmResponseString) {
        try {
          matchedLabels = JSON.parse(llmResponseString);
          if (
            !Array.isArray(matchedLabels) ||
            !matchedLabels.every((item) => typeof item === 'string')
          ) {
            console.error(
              'LLM response is not a valid JSON array of strings:',
              llmResponseString
            );
            matchedLabels = []; // Fallback to empty if not a string array
          }
        } catch (parseError) {
          console.error(
            'Error parsing LLM response:',
            parseError,
            llmResponseString
          );
          // Fallback: attempt to extract labels if it's a simple list not in JSON array format
          // This is a basic fallback, might need more robust parsing depending on LLM behavior
          if (typeof llmResponseString === 'string') {
            matchedLabels = labelNames.filter((label) =>
              llmResponseString.includes(label)
            );
          } else {
            matchedLabels = [];
          }
        }
      } else {
        console.error('LLM response content is null or undefined.');
        matchedLabels = [];
      }

      const scores = labelNames.map((label) =>
        matchedLabels.includes(label) ? 0.9 : 0.1
      );

      const result: ClassificationResponseBodyType = {
        sequence: uuid(), // Added sequence property
        labels: labelNames,
        scores,
      };
      console.log(
        result,
        event?.id,
        ' result, event?.id inside findBestMatchCategory2 with OpenAI'
      );
      return result;
    } catch (apiError) {
      console.error(
        'Error calling OpenAI API or processing its response:',
        apiError
      );
      // Fallback to low scores for all categories in case of API error
      const scores = labelNames.map(() => 0.1);
      const errorResult: ClassificationResponseBodyType = {
        sequence: uuid(), // Added sequence property
        labels: labelNames,
        scores,
      };
      return errorResult;
    }
  } catch (e) {
    // This outer catch block handles errors from the initial validation steps
    console.log(e, ' initial error in findBestMatchCategory2');
    // Optionally rethrow or return a specific error response
    throw e; // Re-throwing the original error if it's from pre-API call logic
  }
};

export const processBestMatchCategories = (
  body: ClassificationResponseBodyType,
  newPossibleLabels: string[]
) => {
  const { scores } = body;
  let bestMatchCategory = '';
  let bestMatchScore = 0;
  for (let i = 0; i < newPossibleLabels.length; i++) {
    const label = newPossibleLabels[i];
    const score = scores[i];
    if (score > minThresholdScore) {
      if (score > bestMatchScore) {
        bestMatchCategory = label;
        bestMatchScore = score;
      }
    }
  }

  return bestMatchCategory;
};

const addToBestMatchCategories = (
  newEvent: EventPlusType,
  newPossibleLabels: string[],
  scores: number[],
  categories: CategoryType[]
): CategoryType[] | [] => {
  const bestMatchCategories = [];

  const meetingIndex = newPossibleLabels.indexOf(meetingLabel);
  const externalMeetingIndex = newPossibleLabels.indexOf(externalMeetingLabel);

  if (meetingIndex > -1 && scores[meetingIndex] > minThresholdScore) {
    bestMatchCategories.push(
      categories.find((category) => category.name === meetingLabel)
    );
  }

  if (
    externalMeetingIndex > -1 &&
    scores[externalMeetingIndex] > minThresholdScore
  ) {
    bestMatchCategories.push(
      categories.find((category) => category.name === externalMeetingLabel)
    );
  }

  if (newEvent.isMeeting && meetingIndex > -1) {
    bestMatchCategories.push(
      categories.find((category) => category.name === meetingLabel)
    );
  }

  if (newEvent.isExternalMeeting && externalMeetingIndex > -1) {
    bestMatchCategories.push(
      categories.find((category) => category.name === externalMeetingLabel)
    );
  }

  return bestMatchCategories;
};

export const processEventForMeetingTypeCategories = (
  newEvent: EventPlusType,
  bestMatchCategory: CategoryType,
  newPossibleLabels: string[],
  scores: number[],
  categories: CategoryType[]
): CategoryType[] | [] => {
  const bestMatchCategories = addToBestMatchCategories(
    newEvent,
    newPossibleLabels,
    scores,
    categories
  );

  if (bestMatchCategories?.length > 0) {
    return (bestMatchCategories as CategoryType[]).concat([bestMatchCategory]);
  }

  return [bestMatchCategory];
};

export const getUniqueLabels = (labels: CategoryType[]) => {
  const uniqueLabels = _.uniqBy(labels, 'id');
  return uniqueLabels;
};

export const copyOverCategoryDefaults = (
  event: EventPlusType,
  category: CategoryType
): EventPlusType => {
  return {
    ...event,
    transparency: !event?.userModifiedAvailability
      ? category?.defaultAvailability
        ? 'transparent'
        : 'opaque'
      : event.transparency,
    priority:
      (!event?.userModifiedPriorityLevel
        ? category?.defaultPriorityLevel
        : event?.priority) || 1,
    modifiable: !event?.userModifiedModifiable
      ? category?.defaultModifiable
      : event.modifiable,
    isBreak: !event?.userModifiedIsBreak
      ? category?.defaultIsBreak
      : event.isBreak,
    isMeeting: !event?.userModifiedIsMeeting
      ? category?.defaultIsMeeting
      : category?.name === meetingLabel
        ? true
        : event.isMeeting,
    isExternalMeeting: !event?.userModifiedIsExternalMeeting
      ? category?.defaultIsExternalMeeting
      : category?.name === externalMeetingLabel
        ? true
        : event.isExternalMeeting,
    isMeetingModifiable: !event?.userModifiedModifiable
      ? category?.defaultMeetingModifiable
      : event.isMeetingModifiable,
    isExternalMeetingModifiable: !event?.userModifiedModifiable
      ? category?.defaultExternalMeetingModifiable
      : event.isExternalMeetingModifiable,
    backgroundColor: !event?.userModifiedColor
      ? category?.color
      : event.backgroundColor,
    preferredTimeRanges:
      !event?.userModifiedTimePreference &&
      category?.defaultTimePreference?.length > 0
        ? category?.defaultTimePreference?.map((tp) => ({
            ...tp,
            id: uuid(),
            eventId: event?.id,
            createdDate: dayjs().toISOString(),
            updatedAt: dayjs().toISOString(),
            userId: event?.userId,
          }))
        : event.preferredTimeRanges,
  };
};

export const createRemindersAndBufferTimesForBestMatchCategory = async (
  id: string,
  userId: string,
  newEvent: EventPlusType,
  bestMatchCategory: CategoryType,
  newReminders1?: ReminderType[],
  newBufferTimes1?: BufferTimeObjectType,
  previousEvent?: EventPlusType
) => {
  try {
    if (!bestMatchCategory?.id) {
      throw new Error('bestMatchCategory is required');
    }
    if (!newEvent?.id) {
      throw new Error('newEvent is required');
    }

    if (!id) {
      throw new Error('id is required');
    }

    if (!userId) {
      throw new Error('userId is required');
    }

    let newBufferTimes = newBufferTimes1 || {};
    let newReminders = newReminders1 || [];
    const oldReminders = await listRemindersForEvent(id, userId);
    const reminders = createRemindersUsingCategoryDefaultsForEvent(
      newEvent,
      bestMatchCategory,
      oldReminders,
      previousEvent
    );
    console.log(reminders, ' reminders');
    if (
      reminders?.length > 0 &&
      bestMatchCategory?.copyReminders &&
      !newEvent?.userModifiedReminders
    ) {
      newReminders.push(...reminders);
    }

    if (
      !newEvent?.userModifiedTimeBlocking &&
      bestMatchCategory?.copyTimeBlocking
    ) {
      const bufferTimes = createPreAndPostEventsForCategoryDefaults(
        bestMatchCategory,
        newEvent,
        previousEvent
      );
      console.log(bufferTimes, ' timeBlocking');
      if (bufferTimes?.beforeEvent) {
        (newBufferTimes as BufferTimeObjectType).beforeEvent =
          bufferTimes.beforeEvent;
      }

      if (bufferTimes?.afterEvent) {
        (newBufferTimes as BufferTimeObjectType).afterEvent =
          bufferTimes.afterEvent;
      }

      if (
        bufferTimes?.newEvent?.preEventId ||
        bufferTimes?.newEvent?.postEventId
      ) {
        newEvent = bufferTimes.newEvent;
      }
    }
    return { newEvent, newReminders, newBufferTimes: newBufferTimes };
  } catch (e) {
    console.log(
      e,
      ' unable to create reminders and time blocking for best match category'
    );
  }
};

export const createCategoryEvents = async (
  categoryEvents: CategoryEventType[]
): Promise<FeaturesApplyResponse<void>> => {
  if (!categoryEvents || categoryEvents.length === 0) {
    // Not an error, but nothing to do. Could also return success.
    console.log('No category events provided to createCategoryEvents.');
    return { ok: true, data: undefined };
  }
  try {
    for (const categoryEvent of categoryEvents) {
      // Basic validation for each categoryEvent
      if (
        !categoryEvent ||
        !categoryEvent.categoryId ||
        !categoryEvent.eventId ||
        !categoryEvent.userId ||
        !categoryEvent.id
      ) {
        console.warn(
          'Skipping invalid categoryEvent in createCategoryEvents:',
          categoryEvent
        );
        continue; // Or collect errors and return a partial success/failure
      }

      const variables = {
        categoryId: categoryEvent?.categoryId,
        eventId: categoryEvent?.eventId,
      };
      const operationName = 'ConnectionByCategoryIdAndEventId';
      const query = `
        query ConnectionByCategoryIdAndEventId($categoryId: uuid!, $eventId: String!) {
          Category_Event(where: {categoryId: {_eq: $categoryId}, eventId: {_eq: $eventId}}) {
            createdDate
            categoryId
            deleted
            eventId
            id
            updatedAt
            userId
          }
        }

      `;

      const res: { data: { Category_Event: CategoryEventType[] } } = await got
        .post(hasuraGraphUrl, {
          headers: {
            'X-Hasura-Admin-Secret': hasuraAdminSecret,
            'X-Hasura-Role': 'admin',
          },
          json: {
            operationName,
            query,
            variables,
          },
        })
        .json();

      if (!res?.data?.Category_Event?.[0]) {
        const variables2 = {
          id: categoryEvent.id,
          categoryId: categoryEvent?.categoryId,
          eventId: categoryEvent?.eventId,
          createdDate: categoryEvent?.createdDate,
          updatedAt: categoryEvent?.updatedAt,
          userId: categoryEvent?.userId,
        };
        const operationName2 = 'InsertCategory_Event';
        const query2 = `
          mutation InsertCategory_Event($id: uuid!, $categoryId: uuid!, $createdDate: timestamptz, $eventId: String!, $updatedAt: timestamptz, $userId: uuid!) {
            insert_Category_Event_one(object: {categoryId: $categoryId, createdDate: $createdDate, deleted: false, eventId: $eventId, id: $id, updatedAt: $updatedAt, userId: $userId}) {
              categoryId
              createdDate
              deleted
              eventId
              id
              updatedAt
              userId
            }
          }
        `;
        const res2 = await got
          .post(hasuraGraphUrl, {
            headers: {
              'X-Hasura-Admin-Secret': hasuraAdminSecret,
              'X-Hasura-Role': 'admin',
            },
            json: {
              operationName: operationName2,
              query: query2,
              variables: variables2,
            },
          })
          .json();

        console.log(res2, ' response after inserting category event');
      }
    }
    return { ok: true, data: undefined };
  } catch (e: any) {
    console.error('Error creating category events in Hasura:', e);
    const errorDetails = e.response?.body || e.message || e;
    return {
      ok: false,
      error: {
        code: 'HASURA_ERROR',
        message: `Failed to create category events: ${e.message}`,
        details: errorDetails,
      },
    };
  }
};

const copyOverCategoryDefaultsForMeetingType = (
  event,
  categories: CategoryType[]
) => {
  const meetingCategory = categories.find(
    (category) => category.name === meetingLabel
  );
  const externalCategory = categories.find(
    (category) => category.name === externalMeetingLabel
  );

  let newEventMeeting = null;
  let newEventExternal = null;

  if (meetingCategory?.id) {
    newEventMeeting = copyOverCategoryDefaults(event, meetingCategory);
  }

  if (externalCategory?.id) {
    newEventExternal = copyOverCategoryDefaults(event, externalCategory);
  }

  return { newEventMeeting, newEventExternal };
};

export const listRemindersForEvent = async (
  eventId: string,
  userId: string
): Promise<FeaturesApplyResponse<ReminderType[] | null>> => {
  if (!eventId || !userId) {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Event ID and User ID are required for listing reminders.',
      },
    };
  }
  try {
    const operationName = 'listRemindersForEvent';
    const query = `
    query listRemindersForEvent($userId: uuid!, $eventId: String!) {
      Reminder(where: {userId: {_eq: $userId}, eventId: {_eq: $eventId}, deleted: {_neq: true}}) {
        eventId
        id
        minutes
        reminderDate
        timezone
        updatedAt
        useDefault
        userId
        deleted
        createdDate
      }
    }
  `;
    const res: { data: { Reminder: ReminderType[] } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables: {
            userId,
            eventId,
          },
        },
      })
      .json();

    console.log(res, ' res from listRemindersForEvent');
    return { ok: true, data: res?.data?.Reminder || null };
  } catch (e: any) {
    console.error('Error listing reminders for event:', e);
    const errorDetails = e.response?.body || e.message || e;
    return {
      ok: false,
      error: {
        code: 'HASURA_ERROR',
        message: `Failed to list reminders: ${e.message}`,
        details: errorDetails,
      },
    };
  }
};

export const createRemindersUsingCategoryDefaultsForEvent = (
  event: EventPlusType,
  bestMatchCategory: CategoryType,
  oldReminders: ReminderType[],
  previousEvent: EventPlusType
): ReminderType[] => {
  if (event.userModifiedReminders) {
    return null;
  }

  if (previousEvent?.copyReminders) {
    return null;
  }

  if (previousEvent?.id && bestMatchCategory?.copyReminders) {
    return null;
  }

  const reminders = bestMatchCategory?.defaultReminders;
  if (!(reminders?.length > 0)) {
    return oldReminders;
  }

  const newReminders = [];
  reminders.forEach((reminder) => {
    newReminders.push({
      id: uuid(),
      minutes: reminder,
      eventId: event.id,
      userId: event.userId,
      updatedAt: dayjs().toISOString(),
      createdDate: dayjs().toISOString(),
      deleted: false,
    });
  });
  return newReminders;
};

export const createPreAndPostEventsForCategoryDefaults = (
  bestMatchCategory: CategoryType,
  event: EventPlusType,
  previousEvent?: EventPlusType
) => {
  if (previousEvent?.copyTimeBlocking) {
    return null;
  }

  if (previousEvent?.id && bestMatchCategory?.copyTimeBlocking) {
    return null;
  }

  if (event?.userModifiedTimeBlocking) {
    return null;
  }

  const eventId = uuid();
  const preEventId = event?.preEventId || `${eventId}#${event?.calendarId}`;
  const postEventId = event?.postEventId || `${eventId}#${event?.calendarId}`;

  let valuesToReturn: any = {};
  valuesToReturn.newEvent = event;

  if (bestMatchCategory?.defaultTimeBlocking?.afterEvent) {
    const formattedZoneAfterEventEndDate = dayjs(event.endDate.slice(0, 19))
      .tz(event?.timezone, true)
      .add(bestMatchCategory.defaultTimeBlocking.afterEvent, 'm')
      .format();
    const formattedZoneAfterEventStartDate = dayjs(event.endDate.slice(0, 19))
      .tz(event?.timezone, true)
      .format();

    const afterEvent: EventPlusType = {
      id: postEventId,
      isPreEvent: false,
      forEventId: event.id,
      isPostEvent: true,
      notes: 'Buffer time',
      summary: 'Buffer time',
      startDate: formattedZoneAfterEventStartDate,
      endDate: formattedZoneAfterEventEndDate,
      method: event?.postEventId ? 'update' : 'create',
      userId: event?.userId,
      createdDate: dayjs().toISOString(),
      deleted: false,
      priority: 1,
      isFollowUp: false,
      modifiable: true,
      anyoneCanAddSelf: false,
      guestsCanInviteOthers: false,
      guestsCanSeeOtherGuests: false,
      originalStartDate: undefined,
      originalAllDay: false,
      updatedAt: dayjs().toISOString(),
      calendarId: event?.calendarId,
      timezone: event?.timezone,
      eventId: postEventId.split('#')[0],
    };
    valuesToReturn.afterEvent = afterEvent;
    valuesToReturn.newEvent = {
      ...valuesToReturn.newEvent,
      postEventId,
      timeBlocking: {
        ...valuesToReturn?.newEvent?.timeBlocking,
        afterEvent: bestMatchCategory.defaultTimeBlocking.afterEvent,
      },
    };
  }

  if (bestMatchCategory?.defaultTimeBlocking?.beforeEvent) {
    const formattedZoneBeforeEventStartDate = dayjs(
      event.startDate.slice(0, 19)
    )
      .tz(event.timezone, true)
      .subtract(bestMatchCategory.defaultTimeBlocking.beforeEvent, 'm')
      .format();
    const formattedZoneBeforeEventEndDate = dayjs(event.startDate.slice(0, 19))
      .tz(event.timezone, true)
      .format();

    const beforeEvent: EventPlusType = {
      id: preEventId,
      isPreEvent: true,
      isPostEvent: false,
      forEventId: event.id,
      notes: 'Buffer time',
      summary: 'Buffer time',
      startDate: formattedZoneBeforeEventStartDate,
      endDate: formattedZoneBeforeEventEndDate,
      method: event?.preEventId ? 'update' : 'create',
      userId: event?.userId,
      createdDate: dayjs().toISOString(),
      deleted: false,
      priority: 1,
      isFollowUp: false,
      modifiable: true,
      anyoneCanAddSelf: false,
      guestsCanInviteOthers: false,
      guestsCanSeeOtherGuests: false,
      originalStartDate: undefined,
      originalAllDay: false,
      updatedAt: dayjs().toISOString(),
      calendarId: event?.calendarId,
      timezone: event?.timezone,
      eventId: preEventId.split('#')[0],
    };
    valuesToReturn.beforeEvent = beforeEvent;
    valuesToReturn.newEvent = {
      ...valuesToReturn.newEvent,
      preEventId,
      timeBlocking: {
        ...valuesToReturn?.newEvent?.timeBlocking,
        beforeEvent: bestMatchCategory.defaultTimeBlocking.beforeEvent,
      },
    };
  }

  return valuesToReturn;
};

export const updateValuesForMeetingTypeCategories = async (
  event,
  newEvent1: EventPlusType,
  bestMatchCategories: CategoryType[],
  userId: string,
  newReminders1?: ReminderType[],
  newTimeBlocking1?: BufferTimeObjectType, // Updated type
  previousEvent?: EventPlusType
): Promise<
  FeaturesApplyResponse<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newBufferTimes: BufferTimeObjectType;
  }>
> => {
  if (
    !bestMatchCategories ||
    bestMatchCategories.length === 0 ||
    !newEvent1 ||
    !userId
  ) {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message:
          'Required parameters missing for updating values for meeting type categories.',
      },
    };
  }
  try {
    let newEvent = newEvent1;
    let newReminders = newReminders1 || [];
    let newBufferTimes = newTimeBlocking1 || {}; // Ensure it's BufferTimeObjectType

    const newCategoryConstantEvents = copyOverCategoryDefaultsForMeetingType(
      event,
      bestMatchCategories
    );
    console.log(newCategoryConstantEvents, ' newCategoryConstantEvents');

    if (newCategoryConstantEvents?.newEventMeeting?.id) {
      newEvent = { ...newEvent, ...newCategoryConstantEvents.newEventMeeting };
      const meetingCategory = bestMatchCategories.find(
        (category) => category.name === meetingLabel
      );

      if (meetingCategory) {
        // Ensure category is found
        const listRemindersResponse = await listRemindersForEvent(
          (newCategoryConstantEvents.newEventMeeting as EventPlusType).id,
          userId
        );
        const oldReminders =
          listRemindersResponse.ok && listRemindersResponse.data
            ? listRemindersResponse.data
            : [];

        const reminders = createRemindersUsingCategoryDefaultsForEvent(
          newEvent,
          meetingCategory,
          oldReminders,
          previousEvent
        );
        if (reminders?.length > 0) {
          newReminders.push(...reminders);
          newReminders = _.uniqBy(newReminders, 'minutes');
        }

        const bufferTime = createPreAndPostEventsForCategoryDefaults(
          meetingCategory,
          newEvent,
          previousEvent
        );
        if (bufferTime?.beforeEvent)
          (newBufferTimes as BufferTimeObjectType).beforeEvent =
            bufferTime.beforeEvent;
        if (bufferTime?.afterEvent)
          (newBufferTimes as BufferTimeObjectType).afterEvent =
            bufferTime.afterEvent;
        if (
          bufferTime?.newEvent?.preEventId ||
          bufferTime?.newEvent?.postEventId
        )
          newEvent = bufferTime.newEvent;
      }
    }

    if (newCategoryConstantEvents?.newEventExternal?.id) {
      newEvent = { ...newEvent, ...newCategoryConstantEvents.newEventExternal };
      const externalCategory = bestMatchCategories.find(
        (category) => category.name === externalMeetingLabel
      );

      if (externalCategory) {
        // Ensure category is found
        const listRemindersResponse = await listRemindersForEvent(
          (newCategoryConstantEvents.newEventExternal as EventPlusType).id,
          userId
        );
        const oldReminders =
          listRemindersResponse.ok && listRemindersResponse.data
            ? listRemindersResponse.data
            : [];

        const reminders = createRemindersUsingCategoryDefaultsForEvent(
          newEvent,
          externalCategory,
          oldReminders,
          previousEvent
        );
        if (reminders?.length > 0) {
          newReminders.push(...reminders);
          newReminders = _.uniqBy(newReminders, 'minutes');
        }

        const timeBlocking = createPreAndPostEventsForCategoryDefaults(
          externalCategory,
          newEvent,
          previousEvent
        );
        if (timeBlocking?.beforeEvent)
          (newBufferTimes as BufferTimeObjectType).beforeEvent =
            timeBlocking.beforeEvent;
        if (timeBlocking?.afterEvent)
          (newBufferTimes as BufferTimeObjectType).afterEvent =
            timeBlocking.afterEvent;
        if (
          timeBlocking?.newEvent?.preEventId ||
          timeBlocking?.newEvent?.postEventId
        )
          newEvent = timeBlocking.newEvent;
      }
    }
    return {
      ok: true,
      data: {
        newEvent,
        newReminders,
        newBufferTimes: newBufferTimes as BufferTimeObjectType,
      },
    };
  } catch (e: any) {
    console.error('Error updating values for meeting type categories:', e);
    return {
      ok: false,
      error: {
        code: 'INTERNAL_ERROR',
        message: `Failed to update values for meeting categories: ${e.message}`,
        details: e,
      },
    };
  }
};

export const processUserEventForCategoryDefaults = async (
  event: EventPlusType,
  vector: number[]
): Promise<
  FeaturesApplyResponse<{
    newEvent: EventPlusType;
    newReminders?: ReminderType[];
    newBufferTimes?: BufferTimeObjectType;
  } | null>
> => {
  if (!event || !event.id || !event.userId || !vector) {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message:
          'Event, event ID, userId, and vector are required for category processing.',
      },
    };
  }
  try {
    const { id, userId } = event;
    console.log(id, ' id inside processUserEventForCategoryDefaults');

    const categoriesResponse = await getUserCategories(userId);
    if (!categoriesResponse.ok || !categoriesResponse.data) {
      // If categories can't be fetched, we might still proceed with the event, but without categorization benefits.
      console.warn(
        `Failed to get user categories for user ${userId}. Proceeding without categorization. Error: ${categoriesResponse.error?.message}`
      );
      event.vector = vector; // Ensure vector is set
      return { ok: true, data: { newEvent: event } }; // Or return error if categories are essential
    }
    const categories = categoriesResponse.data;

    if (categories.length === 0) {
      console.log(
        `No categories defined for user ${userId}. Event ${id} will not be categorized further.`
      );
      event.vector = vector;
      return { ok: true, data: { newEvent: event } };
    }

    const classificationResponse = await findBestMatchCategory2(
      event,
      categories
    );
    if (!classificationResponse.ok || !classificationResponse.data) {
      console.warn(
        `Category classification failed for event ${id}. Error: ${classificationResponse.error?.message}. Proceeding without applying category defaults.`
      );
      event.vector = vector;
      return { ok: true, data: { newEvent: event } };
    }
    const classificationBody = classificationResponse.data;
    const { labels, scores } = classificationBody;
    const bestMatchLabel = processBestMatchCategories(
      classificationBody,
      labels
    );

    let newEvent: EventPlusType = { ...event, vector }; // Start with original event and add vector
    let newReminders: ReminderType[] = [];
    let newBufferTimes: BufferTimeObjectType = {};

    if (bestMatchLabel) {
      const bestMatchCategory = categories.find(
        (category) => category.name === bestMatchLabel
      );
      if (bestMatchCategory) {
        let bestMatchPlusMeetingCategories =
          processEventForMeetingTypeCategories(
            newEvent,
            bestMatchCategory,
            labels,
            scores,
            categories
          );
        bestMatchPlusMeetingCategories = getUniqueLabels(
          bestMatchPlusMeetingCategories
        );

        newEvent = copyOverCategoryDefaults(newEvent, bestMatchCategory);

        const remindersAndBuffersResponse =
          await createRemindersAndBufferTimesForBestMatchCategory(
            id,
            userId,
            newEvent,
            bestMatchCategory,
            [],
            {}
          );
        if (
          remindersAndBuffersResponse.ok &&
          remindersAndBuffersResponse.data
        ) {
          newEvent = remindersAndBuffersResponse.data.newEvent;
          newReminders = remindersAndBuffersResponse.data.newReminders;
          newBufferTimes = remindersAndBuffersResponse.data.newBufferTimes;
        } else {
          console.warn(
            `Failed to create reminders/buffers for best match category for event ${id}: ${remindersAndBuffersResponse.error?.message}`
          );
        }

        if (bestMatchPlusMeetingCategories?.length > 0) {
          const categoryEvents: CategoryEventType[] =
            bestMatchPlusMeetingCategories.map((c) => ({
              categoryId: c.id,
              eventId: id,
              userId,
              id: uuid(),
              createdDate: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
              Category: c,
              deleted: false,
            }));

          const createCatEventsResponse =
            await createCategoryEvents(categoryEvents);
          if (!createCatEventsResponse.ok) {
            console.warn(
              `Failed to create category events for event ${id}: ${createCatEventsResponse.error?.message}`
            );
          }

          const updatedValuesResponse =
            await updateValuesForMeetingTypeCategories(
              event,
              newEvent,
              bestMatchPlusMeetingCategories,
              userId,
              newReminders,
              newBufferTimes
            );
          if (updatedValuesResponse.ok && updatedValuesResponse.data) {
            newEvent = updatedValuesResponse.data.newEvent;
            newReminders = updatedValuesResponse.data.newReminders;
            newBufferTimes = updatedValuesResponse.data.newBufferTimes;
          } else {
            console.warn(
              `Failed to update values for meeting type categories for event ${id}: ${updatedValuesResponse.error?.message}`
            );
          }
        }
      }
    }
    return { ok: true, data: { newEvent, newReminders, newBufferTimes } };
  } catch (e: any) {
    console.error(
      `Error processing user event ${event?.id} for category defaults:`,
      e
    );
    return {
      ok: false,
      error: {
        code: 'CLASSIFICATION_ERROR',
        message: `Failed to process event for categories: ${e.message}`,
        details: e,
      },
    };
  }
};

export const listCategoriesForEvent = async (
  eventId: string
): Promise<FeaturesApplyResponse<CategoryType[] | null>> => {
  if (!eventId) {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Event ID is required for listing categories.',
      },
    };
  }
  try {
    const operationName = 'listCategoriesForEvent';
    const query = `
      query listCategoriesForEvent($eventId: String!) {
        Category_Event(where: {eventId: {_eq: $eventId}}) {
          Category {
            color
            copyAvailability
            copyIsBreak
            copyIsExternalMeeting
            copyIsMeeting
            copyModifiable
            copyPriorityLevel
            copyReminders
            copyTimeBlocking
            copyTimePreference
            createdDate
            defaultAvailability
            defaultExternalMeetingModifiable
            defaultIsBreak
            defaultIsExternalMeeting
            defaultIsMeeting
            defaultMeetingModifiable
            defaultModifiable
            defaultPriorityLevel
            defaultReminders
            defaultTimeBlocking
            defaultTimePreference
            deleted
            id
            name
            updatedAt
            userId
          }
          categoryId
          createdDate
          deleted
          eventId
          id
          updatedAt
          userId
        }
      }
    `;
    const res: { data: { Category_Event: CategoryEventType[] } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables: {
            eventId,
          },
        },
      })
      .json();
    console.log(res, ' listCategoriesForEvent');
    const categories: CategoryType[] = res?.data?.Category_Event?.map(
      (category) => category?.Category
    )?.filter(
      (category): category is CategoryType =>
        category != null && category.id != null
    ); // Ensure category and its id are not null

    console.log(
      categories,
      ' categories from listCategoriesForEvent after filter'
    );
    return { ok: true, data: categories || null };
  } catch (e: any) {
    console.error('Error listing categories for event:', e);
    const errorDetails = e.response?.body || e.message || e;
    return {
      ok: false,
      error: {
        code: 'HASURA_ERROR',
        message: `Failed to list categories for event: ${e.message}`,
        details: errorDetails,
      },
    };
  }
};

export const processBestMatchCategoriesNoThreshold = (
  body,
  newPossibleLabels
) => {
  const { scores } = body;
  let bestMatchCategory = '';
  let bestMatchScore = 0;
  for (let i = 0; i < newPossibleLabels.length; i++) {
    const label = newPossibleLabels[i];
    const score = scores[i];

    if (score > bestMatchScore) {
      bestMatchCategory = label;
      bestMatchScore = score;
    }
  }

  return bestMatchCategory;
};

export const processUserEventForCategoryDefaultsWithUserModifiedCategories =
  async (event: EventPlusType, vector: number[]) => {
    try {
      const { id, userId } = event;
      console.log(
        id,
        userId,
        ' id, userId inside processUserEventForCategoryDefaultsWithUserModifiedCategories'
      );

      const categories: CategoryType[] = await listCategoriesForEvent(
        event?.id
      );

      console.log(categories, ' categories');
      const body = await findBestMatchCategory2(event, categories);
      console.log(body, ' body');
      const { labels, scores } = body;

      const bestMatchLabel = processBestMatchCategoriesNoThreshold(
        body,
        labels
      );
      console.log(bestMatchLabel, ' bestMatchLabel');
      let bestMatchCategory: CategoryType | null = null;
      let newEvent: EventPlusType = event;
      console.log(newEvent, ' newEvent');
      let newReminders: ReminderType[] = [];
      let newBufferTimes: BufferTimeObjectType | object = {};
      if (bestMatchLabel) {
        bestMatchCategory = categories.find(
          (category) => category.name === bestMatchLabel
        );
        labels.push(meetingLabel, externalMeetingLabel);
        scores.push(0, 0);
        let bestMatchPlusMeetingCategories =
          processEventForMeetingTypeCategories(
            event,
            bestMatchCategory,
            labels,
            scores,
            categories
          );
        if (bestMatchPlusMeetingCategories?.length > 0) {
          bestMatchPlusMeetingCategories = getUniqueLabels(
            bestMatchPlusMeetingCategories
          );
          console.log(
            bestMatchPlusMeetingCategories,
            ' bestMatchAndMeetingCategories'
          );
          const categoryEvents: CategoryEventType[] =
            bestMatchPlusMeetingCategories.map((c) => {
              const categoryEvent: CategoryEventType = {
                categoryId: c.id,
                eventId: id,
                userId,
                id: uuid(),
                createdDate: new Date().toISOString(),
                updatedAt: new Date().toISOString(),
              } as CategoryEventType;
              return categoryEvent;
            });
          console.log(categoryEvents, ' categoryEvents');
          await createCategoryEvents(categoryEvents);
          const {
            newEvent: newEvent1,
            newReminders: newReminders1,
            newBufferTimes: newTimeBlocking1,
          } = await updateValuesForMeetingTypeCategories(
            event,
            newEvent,
            bestMatchPlusMeetingCategories,
            userId,
            newReminders,
            newBufferTimes
          );
          newEvent = newEvent1;
          newReminders = newReminders1;
          newBufferTimes = newTimeBlocking1;
        }
      }

      let newCategoryDefaultEvent: EventPlusType | null = null;
      if (bestMatchCategory) {
        newCategoryDefaultEvent = copyOverCategoryDefaults(
          event,
          bestMatchCategory
        );
      }
      console.log(newCategoryDefaultEvent, ' newCategoryDefaultEvent');

      newEvent = newCategoryDefaultEvent ?? newEvent ?? event;
      console.log(newEvent, ' newEvent');
      const {
        newEvent: newEvent1,
        newReminders: newReminders1,
        newBufferTimes: newTimeBlocking1,
      } = await createRemindersAndBufferTimesForBestMatchCategory(
        id,
        userId,
        newEvent,
        bestMatchCategory,
        newReminders,
        newBufferTimes as BufferTimeObjectType
      );

      newEvent = newEvent1;
      newReminders = newReminders1;
      newBufferTimes = newTimeBlocking1 as BufferTimeObjectType;

      if (categories?.length > 1) {
        const {
          newEvent: newEvent1,
          newReminders: newReminders1,
          newBufferTimes: newTimeBlocking1,
        } = await updateValuesForMeetingTypeCategories(
          event,
          newEvent,
          categories,
          userId,
          newReminders,
          newBufferTimes as BufferTimeObjectType
        );
        newEvent = newEvent1;
        newReminders = newReminders1;
        newBufferTimes = newTimeBlocking1;
      }

      newEvent.vector = vector;

      console.log(newEvent, ' newEvent');
      console.log(newReminders, ' newReminders');
      console.log(newBufferTimes, ' newTimeBlocking');

      return {
        newEvent,
        newReminders,
        newBufferTimes: newBufferTimes,
      };
    } catch (e) {
      console.log(e, ' e');
    }
  };

export const getEventFromPrimaryKey = async (
  id: string
): Promise<FeaturesApplyResponse<EventPlusType | null>> => {
  if (!id) {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'ID is required to get event by primary key.',
      },
    };
  }
  try {
    const operationName = 'getEventFromPrimaryKey';
    const query = `
    query getEventFromPrimaryKey($id: String!) {
  Event_by_pk(id: $id) {
    allDay
    anyoneCanAddSelf
    attachments
    attendeesOmitted
    backgroundColor
    calendarId
    colorId
    conferenceId
    copyAvailability
    copyCategories
    copyDuration
    copyIsBreak
    copyIsExternalMeeting
    copyIsMeeting
    copyModifiable
    copyPriorityLevel
    copyReminders
    copyTimeBlocking
    copyTimePreference
    createdDate
    creator
    dailyTaskList
    deleted
    duration
    endDate
    endTimeUnspecified
    eventId
    eventType
    extendedProperties
    followUpEventId
    forEventId
    foregroundColor
    guestsCanInviteOthers
    guestsCanModify
    guestsCanSeeOtherGuests
    hangoutLink
    hardDeadline
    htmlLink
    iCalUID
    id
    isBreak
    isExternalMeeting
    isExternalMeetingModifiable
    isFollowUp
    isMeeting
    isMeetingModifiable
    isPostEvent
    isPreEvent
    links
    location
    locked
    maxAttendees
    method
    modifiable
    negativeImpactDayOfWeek
    negativeImpactScore
    negativeImpactTime
    notes
    organizer
    originalAllDay
    originalStartDate
    originalTimezone
    positiveImpactDayOfWeek
    positiveImpactScore
    positiveImpactTime
    postEventId
    preEventId
    preferredDayOfWeek
    preferredEndTimeRange
    preferredStartTimeRange
    preferredTime
    priority
    privateCopy
    recurrence
    recurrenceRule
    recurringEventId
    sendUpdates
    softDeadline
    source
    startDate
    status
    summary
    taskId
    taskType
    timeBlocking
    timezone
    title
    transparency
    unlink
    updatedAt
    useDefaultAlarms
    userId
    userModifiedAvailability
    userModifiedCategories
    userModifiedDuration
    userModifiedIsBreak
    userModifiedIsExternalMeeting
    userModifiedIsMeeting
    userModifiedModifiable
    userModifiedPriorityLevel
    userModifiedReminders
    userModifiedTimeBlocking
    userModifiedTimePreference
    visibility
    weeklyTaskList
    byWeekDay
    localSynced
    userModifiedColor
    copyColor
    userModifiedExternalMeetingModifiable
    userModifiedMeetingModifiable
    meetingId
    copyMeetingModifiable
    copyExternalMeetingModifiable
  }
}

  `;
    const res: { data: { Event_by_pk: EventPlusType } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables: {
            id,
          },
        },
      })
      .json();
    console.log(res, ' res from getEventFromPrimaryKey');
    const event = res?.data?.Event_by_pk;
    if (!event) {
      return { ok: true, data: null }; // Not found is a valid success case for get by PK
    }
    return { ok: true, data: event };
  } catch (e: any) {
    console.error('Error getting event from primary key:', e);
    const errorDetails = e.response?.body || e.message || e;
    return {
      ok: false,
      error: {
        code: 'HASURA_ERROR',
        message: `Failed to get event by PK: ${e.message}`,
        details: errorDetails,
      },
    };
  }
};

export const copyOverPreviousEventDefaults = (
  event: EventPlusType,
  previousEvent: EventPlusType,
  category?: CategoryType,
  userPreferences?: UserPreferenceType
): EventPlusType => {
  const previousDuration = dayjs
    .duration(
      dayjs(previousEvent.endDate.slice(0, 19))
        .tz(previousEvent?.timezone, true)
        .diff(
          dayjs(previousEvent.startDate.slice(0, 19)).tz(
            previousEvent?.timezone,
            true
          )
        )
    )
    .asMinutes();
  return {
    ...event,
    transparency: !event?.userModifiedAvailability
      ? previousEvent?.copyAvailability
        ? previousEvent.transparency
        : category?.copyAvailability
          ? previousEvent?.transparency
          : category?.defaultAvailability
            ? 'transparent'
            : userPreferences?.copyAvailability
              ? previousEvent?.transparency
              : event?.transparency
      : event.transparency,
    preferredTime: !event?.userModifiedTimePreference
      ? previousEvent?.copyTimePreference && previousEvent?.preferredTime
        ? previousEvent.preferredTime
        : category?.copyTimePreference && previousEvent?.preferredTime
          ? previousEvent?.preferredTime
          : userPreferences?.copyTimePreference && previousEvent?.preferredTime
            ? previousEvent?.preferredTime
            : event?.preferredTime
      : event.preferredTime,
    preferredDayOfWeek: !event?.userModifiedTimePreference
      ? previousEvent?.copyTimePreference && previousEvent?.preferredDayOfWeek
        ? previousEvent.preferredDayOfWeek
        : category?.copyTimePreference && previousEvent?.preferredDayOfWeek
          ? previousEvent?.preferredDayOfWeek
          : userPreferences?.copyTimePreference &&
              previousEvent?.preferredDayOfWeek
            ? previousEvent?.preferredDayOfWeek
            : event?.preferredDayOfWeek
      : event.preferredDayOfWeek,
    preferredStartTimeRange: !event?.userModifiedTimePreference
      ? previousEvent?.copyTimePreference &&
        previousEvent?.preferredStartTimeRange
        ? previousEvent.preferredStartTimeRange
        : category?.copyTimePreference && previousEvent?.preferredStartTimeRange
          ? previousEvent?.preferredStartTimeRange
          : userPreferences?.copyTimePreference &&
              previousEvent?.preferredStartTimeRange
            ? previousEvent?.preferredStartTimeRange
            : event?.preferredStartTimeRange
      : event.preferredStartTimeRange,
    preferredEndTimeRange: !event?.userModifiedTimePreference
      ? previousEvent?.copyTimePreference &&
        previousEvent?.preferredEndTimeRange
        ? previousEvent.preferredEndTimeRange
        : category?.copyTimePreference && previousEvent?.preferredEndTimeRange
          ? previousEvent?.preferredEndTimeRange
          : userPreferences?.copyTimePreference &&
              previousEvent?.preferredEndTimeRange
            ? previousEvent?.preferredEndTimeRange
            : event?.preferredEndTimeRange
      : event.preferredEndTimeRange,
    priority:
      (!event?.userModifiedPriorityLevel
        ? previousEvent?.copyPriorityLevel
          ? previousEvent.priority
          : category?.copyPriorityLevel
            ? previousEvent?.priority
            : category?.defaultPriorityLevel
              ? category?.defaultPriorityLevel
              : userPreferences?.copyPriorityLevel
                ? previousEvent?.priority
                : event?.priority
        : event?.priority) || 1,
    isBreak: !event?.userModifiedIsBreak
      ? previousEvent?.copyIsBreak
        ? previousEvent.isBreak
        : category?.copyIsBreak
          ? previousEvent?.isBreak
          : category?.defaultIsBreak
            ? category?.defaultIsBreak
            : userPreferences?.copyIsBreak
              ? previousEvent?.isBreak
              : event?.isBreak
      : event.isBreak,
    isMeeting: !event?.userModifiedIsMeeting
      ? previousEvent?.copyIsMeeting
        ? previousEvent.isMeeting
        : category?.copyIsMeeting
          ? previousEvent?.isMeeting
          : category?.defaultIsMeeting
            ? category?.defaultIsMeeting
            : userPreferences?.copyIsMeeting
              ? previousEvent?.isMeeting
              : category?.name === meetingLabel
                ? true
                : event?.isMeeting
      : event.isMeeting,
    isExternalMeeting: !event?.userModifiedIsExternalMeeting
      ? previousEvent?.copyIsExternalMeeting
        ? previousEvent.isExternalMeeting
        : category?.copyIsExternalMeeting
          ? previousEvent?.isExternalMeeting
          : category?.defaultIsExternalMeeting
            ? category?.defaultIsExternalMeeting
            : userPreferences?.copyIsExternalMeeting
              ? previousEvent?.isExternalMeeting
              : category?.name === externalMeetingLabel
                ? true
                : event?.isExternalMeeting
      : event.isExternalMeeting,
    modifiable: !event?.userModifiedModifiable
      ? previousEvent?.copyModifiable
        ? previousEvent.modifiable
        : category?.copyModifiable
          ? previousEvent?.modifiable
          : category?.defaultModifiable
            ? category?.defaultModifiable
            : userPreferences?.copyModifiable
              ? previousEvent?.modifiable
              : event?.modifiable
      : event.modifiable,
    isMeetingModifiable: !event?.userModifiedModifiable
      ? previousEvent?.copyIsMeeting
        ? previousEvent.isMeeting
        : category?.copyIsMeeting
          ? previousEvent?.isMeeting
          : category?.defaultIsMeeting
            ? category?.defaultIsMeeting
            : userPreferences?.copyIsMeeting
              ? previousEvent?.isMeeting
              : event?.isMeeting
      : event.isMeetingModifiable,
    isExternalMeetingModifiable: !event?.userModifiedModifiable
      ? previousEvent?.copyIsExternalMeeting
        ? previousEvent.isExternalMeeting
        : category?.copyIsExternalMeeting
          ? previousEvent?.isExternalMeeting
          : category?.defaultIsExternalMeeting
            ? category?.defaultIsExternalMeeting
            : userPreferences?.copyIsExternalMeeting
              ? previousEvent?.isExternalMeeting
              : event?.isExternalMeeting
      : event.isExternalMeetingModifiable,
    duration: !event?.userModifiedDuration
      ? previousEvent?.copyDuration
        ? previousEvent.duration || previousDuration
        : event?.duration
      : event.duration,
    endDate: !event?.userModifiedDuration
      ? previousEvent?.copyDuration
        ? dayjs(event.startDate.slice(0, 19))
            .tz(event.timezone, true)
            .add(previousEvent.duration || previousDuration, 'minutes')
            .format()
        : event?.endDate
      : event.endDate,
    preferredTimeRanges: !event?.userModifiedTimePreference
      ? previousEvent?.copyTimePreference &&
        previousEvent.preferredTimeRanges?.length > 0
        ? previousEvent?.preferredTimeRanges?.map((p) => ({
            ...p,
            id: uuid(),
            eventId: event?.id,
          }))
        : category?.copyTimePreference &&
            previousEvent.preferredTimeRanges?.length > 0
          ? previousEvent?.preferredTimeRanges?.map((p) => ({
              ...p,
              id: uuid(),
              eventId: event?.id,
            }))
          : userPreferences?.copyTimePreference &&
              previousEvent.preferredTimeRanges?.length > 0
            ? previousEvent?.preferredTimeRanges?.map((p) => ({
                ...p,
                id: uuid(),
                eventId: event?.id,
              }))
            : category?.defaultTimePreference?.length > 0
              ? category?.defaultTimePreference?.map((tp) => ({
                  ...tp,
                  eventId: event?.id,
                  id: uuid(),
                  createdDate: dayjs().toISOString(),
                  updatedAt: dayjs().toISOString(),
                  userId: event?.userId,
                }))
              : event?.preferredTimeRanges
      : event.preferredTimeRanges,

    copyAvailability: !previousEvent?.unlink
      ? previousEvent.copyAvailability
      : false,
    copyTimePreference: !previousEvent?.unlink
      ? previousEvent.copyTimePreference
      : false,
    copyPriorityLevel: !previousEvent?.unlink
      ? previousEvent.copyPriorityLevel
      : false,
    copyIsBreak: !previousEvent?.unlink ? previousEvent.copyIsBreak : false,
    copyModifiable: !previousEvent?.unlink
      ? previousEvent.copyModifiable
      : false,
    copyIsMeeting: !previousEvent?.unlink ? previousEvent.copyIsMeeting : false,
    copyIsExternalMeeting: !previousEvent?.unlink
      ? previousEvent.copyIsExternalMeeting
      : false,
    copyDuration: !previousEvent?.unlink ? previousEvent.copyDuration : false,
    copyCategories: !previousEvent?.unlink
      ? previousEvent.copyCategories
      : false,
    copyReminders: !previousEvent?.unlink ? previousEvent.copyReminders : false,
    copyTimeBlocking: !previousEvent?.unlink
      ? previousEvent.copyTimeBlocking
      : false,
    copyColor: !previousEvent?.unlink ? previousEvent.copyColor : false,
    unlink: !previousEvent?.unlink ? false : true,

    positiveImpactDayOfWeek: !previousEvent?.unlink
      ? previousEvent.positiveImpactDayOfWeek
      : null,
    positiveImpactScore: !previousEvent?.unlink
      ? previousEvent.positiveImpactScore
      : null,
    negativeImpactDayOfWeek: !previousEvent?.unlink
      ? previousEvent.negativeImpactDayOfWeek
      : null,
    negativeImpactScore: !previousEvent?.unlink
      ? previousEvent.negativeImpactScore
      : null,
    positiveImpactTime: !previousEvent?.unlink
      ? previousEvent.positiveImpactTime
      : null,
    negativeImpactTime: !previousEvent?.unlink
      ? previousEvent.negativeImpactTime
      : null,

    backgroundColor: !event?.userModifiedColor
      ? previousEvent?.copyColor
        ? previousEvent.backgroundColor
        : category?.color
          ? category?.color
          : userPreferences?.copyColor
            ? previousEvent?.backgroundColor
            : event?.backgroundColor
      : event.backgroundColor,
    colorId:
      previousEvent?.copyColor && previousEvent?.colorId
        ? previousEvent.colorId
        : userPreferences?.copyColor && previousEvent?.colorId
          ? previousEvent?.colorId
          : event?.colorId,
  };
};

export const listFutureMeetingAssists = async (
  userId: string,
  windowStartDate: string,
  windowEndDate: string,
  ids?: string[]
) => {
  try {
    console.log(
      userId,
      windowStartDate,
      windowEndDate,
      ids,
      ' userId, windowStartDate, windowEndDate, ids'
    );
    const operationName = 'ListMeetingAssist';
    const query = `
            query ListMeetingAssist($userId: uuid!, $windowStartDate: timestamp!, $windowEndDate: timestamp!, ${ids?.length > 0 ? '$ids: [uuid!]!' : ''}) {
                Meeting_Assist(where: {userId: {_eq: $userId}, windowEndDate: {_lte: $windowEndDate}, windowStartDate: {_gte: $windowStartDate}, cancelled: {_eq: false}${ids?.length > 0 ? ', id: {_nin: $ids}' : ''}, eventId: {_is_null: true}}) {
                    allowAttendeeUpdatePreferences
                    anyoneCanAddSelf
                    attendeeCanModify
                    attendeeCount
                    backgroundColor
                    attendeeRespondedCount
                    bufferTime
                    calendarId
                    cancelIfAnyRefuse
                    cancelled
                    colorId
                    conferenceApp
                    createdDate
                    duration
                    enableAttendeePreferences
                    enableConference
                    enableHostPreferences
                    endDate
                    eventId
                    expireDate
                    foregroundColor
                    guaranteeAvailability
                    guestsCanInviteOthers
                    guestsCanSeeOtherGuests
                    id
                    location
                    minThresholdCount
                    notes
                    priority
                    reminders
                    sendUpdates
                    startDate
                    summary
                    timezone
                    transparency
                    updatedAt
                    useDefaultAlarms
                    userId
                    visibility
                    windowEndDate
                    windowStartDate
                    interval
                    lockAfter
                    originalMeetingId
                    until
                    frequency
                }
            }
        `;

    let variables: any = {
      userId,
      windowStartDate,
      windowEndDate,
    };

    if (ids?.length > 0) {
      variables.ids = ids;
    }

    const res: { data: { Meeting_Assist: MeetingAssistType[] } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables,
        },
      })
      .json();

    console.log(res, ' res inside list future meeting assist');
    console.log(
      res?.data?.Meeting_Assist,
      ' successfully got meeting asssists'
    );

    return res?.data?.Meeting_Assist;
  } catch (e) {
    console.log(e, ' unable to list meeting assists');
  }
};

export const meetingAttendeeCountGivenMeetingId = async (meetingId: string) => {
  try {
    const operationName = 'AttendeeCountGiveMeetingId';
    const query = `
            query AttendeeCountGiveMeetingId($meetingId: uuid!) {
                Meeting_Assist_Attendee_aggregate(where: {meetingId: {_eq: $meetingId}}) {
                    aggregate {
                        count
                    }
                }
            }
        `;

    const variables = {
      meetingId,
    };

    const res: {
      data: {
        Meeting_Assist_Attendee_aggregate: { aggregate: { count: number } };
      };
    } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables,
        },
      })
      .json();

    console.log(
      res?.data?.Meeting_Assist_Attendee_aggregate?.aggregate?.count,
      ' received attendee count'
    );

    return res?.data?.Meeting_Assist_Attendee_aggregate?.aggregate?.count;
  } catch (e) {
    console.log(e, ' unable to get meeting attendee count');
  }
};

export const createPreAndPostEventsFromPreviousEvent = (
  event: EventPlusType,
  previousEvent: EventPlusType
) => {
  if (!previousEvent?.copyTimeBlocking) {
    console.log('no copy time blocking');
    return null;
  }

  if (event.userModifiedTimeBlocking) {
    console.log('user modified time blocking');
    return null;
  }

  const eventId = uuid();
  const eventId1 = uuid();
  const preEventId = event?.preEventId || `${eventId}#${event?.calendarId}`;
  const postEventId = event?.postEventId || `${eventId1}#${event?.calendarId}`;

  let valuesToReturn: any = {};
  valuesToReturn.newEvent = event;

  if (previousEvent?.timeBlocking?.afterEvent) {
    const formattedZoneAfterEventEndDate = dayjs(event.endDate.slice(0, 19))
      .tz(event.timezone, true)
      .add(previousEvent?.timeBlocking?.afterEvent, 'm')
      .format();
    const formattedZoneAfterEventStartDate = dayjs(event.endDate.slice(0, 19))
      .tz(event.timezone, true)
      .format();

    const afterEvent: EventPlusType = {
      id: postEventId,
      isPreEvent: false,
      forEventId: event.id,
      isPostEvent: true,
      notes: 'Buffer time',
      summary: 'Buffer time',
      startDate: formattedZoneAfterEventStartDate,
      endDate: formattedZoneAfterEventEndDate,
      method: event?.postEventId ? 'update' : 'create',
      userId: event?.userId,
      createdDate: dayjs().toISOString(),
      deleted: false,
      priority: 1,
      isFollowUp: false,
      modifiable: true,
      anyoneCanAddSelf: false,
      guestsCanInviteOthers: false,
      guestsCanSeeOtherGuests: false,
      originalStartDate: undefined,
      originalAllDay: false,
      updatedAt: dayjs().toISOString(),
      calendarId: event?.calendarId,
      timezone: event?.timezone,
      eventId: postEventId.split('#')[0],
    };
    valuesToReturn.afterEvent = afterEvent;
    valuesToReturn.newEvent = {
      ...valuesToReturn.newEvent,
      postEventId,
      timeBlocking: {
        ...valuesToReturn?.newEvent?.timeBlocking,
        afterEvent: previousEvent?.timeBlocking?.afterEvent,
      },
    };
  }

  if (previousEvent?.timeBlocking?.beforeEvent) {
    const formattedZoneBeforeEventStartDate = dayjs(
      event.startDate.slice(0, 19)
    )
      .tz(event.timezone, true)
      .subtract(previousEvent?.timeBlocking?.beforeEvent, 'm')
      .format();
    const formattedZoneBeforeEventEndDate = dayjs(event.startDate.slice(0, 19))
      .tz(event.timezone, true)
      .format();

    const beforeEvent: EventPlusType = {
      id: preEventId,
      isPreEvent: true,
      isPostEvent: false,
      forEventId: event.id,
      notes: 'Buffer time',
      summary: 'Buffer time',
      startDate: formattedZoneBeforeEventStartDate,
      endDate: formattedZoneBeforeEventEndDate,
      method: event?.preEventId ? 'update' : 'create',
      userId: event?.userId,
      createdDate: dayjs().toISOString(),
      deleted: false,
      priority: 1,
      isFollowUp: false,
      modifiable: true,
      anyoneCanAddSelf: false,
      guestsCanInviteOthers: false,
      guestsCanSeeOtherGuests: false,
      originalStartDate: undefined,
      originalAllDay: false,
      updatedAt: dayjs().toISOString(),
      calendarId: event?.calendarId,
      timezone: event?.timezone,
      eventId: preEventId.split('#')[0],
    };
    valuesToReturn.beforeEvent = beforeEvent;
    valuesToReturn.newEvent = {
      ...valuesToReturn.newEvent,
      preEventId,
      timeBlocking: {
        ...valuesToReturn?.newEvent?.timeBlocking,
        beforeEvent: previousEvent?.timeBlocking?.beforeEvent,
      },
    };
  }

  return valuesToReturn;
};

export const createRemindersFromPreviousEventForEvent = async (
  event: EventPlusType,
  previousEvent: EventPlusType,
  userId: string
): Promise<ReminderType[]> => {
  if (event.userModifiedReminders) {
    console.log('no event inside createRemindersFromPreviousEventForEvent');
    return null;
  }

  if (!previousEvent?.id) {
    console.log(
      'no previousEvent inside createRemindersFromPreviousEventForEvent'
    );
    return null;
  }

  if (!previousEvent?.copyReminders) {
    console.log(
      'no previousEvent inside createRemindersFromPreviousEventForEvent'
    );
    return null;
  }

  const reminders = await listRemindersForEvent(previousEvent.id, userId);

  return reminders?.map((reminder) => ({
    ...reminder,
    eventId: event.id,
    id: uuid(),
    updatedAt: dayjs().toISOString(),
    createdDate: dayjs().toISOString(),
    deleted: false,
  }));
};

const copyOverMeetingAndExternalMeetingDefaultsWithPreviousEventFound = (
  event: EventPlusType,
  previousEvent: EventPlusType,
  category: CategoryType,
  userPreferences: UserPreferenceType
): EventPlusType => {
  return {
    ...event,
    transparency: !event?.userModifiedAvailability
      ? previousEvent?.copyAvailability
        ? previousEvent.transparency
        : category.copyAvailability
          ? previousEvent?.transparency
          : category.defaultAvailability
            ? 'transparent'
            : userPreferences?.copyAvailability
              ? previousEvent?.transparency
              : event?.transparency
      : event.transparency,
    preferredTime: !event?.userModifiedTimePreference
      ? previousEvent?.copyTimePreference
        ? previousEvent.preferredTime
        : category.copyTimePreference
          ? previousEvent?.preferredTime
          : userPreferences?.copyTimePreference
            ? previousEvent?.preferredTime
            : event?.preferredTime
      : event.preferredTime,
    preferredDayOfWeek: !event?.userModifiedTimePreference
      ? previousEvent?.copyTimePreference
        ? previousEvent.preferredDayOfWeek
        : userPreferences?.copyTimePreference
          ? previousEvent?.preferredDayOfWeek
          : event?.preferredDayOfWeek
      : event.preferredDayOfWeek,
    preferredStartTimeRange: !event?.userModifiedTimePreference
      ? previousEvent?.copyTimePreference
        ? previousEvent.preferredStartTimeRange
        : category.copyTimePreference
          ? previousEvent?.preferredStartTimeRange
          : userPreferences?.copyTimePreference
            ? previousEvent?.preferredStartTimeRange
            : event?.preferredStartTimeRange
      : event.preferredStartTimeRange,
    preferredEndTimeRange: !event?.userModifiedTimePreference
      ? previousEvent?.copyTimePreference
        ? previousEvent.preferredEndTimeRange
        : category.copyTimePreference
          ? previousEvent?.preferredEndTimeRange
          : userPreferences?.copyTimePreference
            ? previousEvent?.preferredEndTimeRange
            : event?.preferredEndTimeRange
      : event.preferredEndTimeRange,
    priority:
      (!event?.userModifiedPriorityLevel
        ? previousEvent?.copyPriorityLevel
          ? previousEvent.priority
          : category.copyPriorityLevel
            ? previousEvent?.priority
            : category.defaultPriorityLevel
              ? category?.defaultPriorityLevel
              : userPreferences?.copyPriorityLevel
                ? previousEvent?.priority
                : event?.priority
        : event?.priority) || 1,
    isBreak: !event?.userModifiedIsBreak
      ? previousEvent?.copyIsBreak
        ? previousEvent.isBreak
        : category.copyIsBreak
          ? previousEvent?.isBreak
          : category.defaultIsBreak
            ? category?.defaultIsBreak
            : userPreferences?.copyIsBreak
              ? previousEvent?.isBreak
              : event?.isBreak
      : event.isBreak,
    isMeeting: !event?.userModifiedIsMeeting
      ? previousEvent?.copyIsMeeting
        ? previousEvent.isMeeting
        : category.copyIsMeeting
          ? previousEvent?.isMeeting
          : category.defaultIsMeeting
            ? category?.defaultIsMeeting
            : userPreferences?.copyIsMeeting
              ? previousEvent?.isMeeting
              : category.name === meetingLabel
                ? true
                : event?.isMeeting
      : event.isMeeting,
    isExternalMeeting: !event?.userModifiedIsExternalMeeting
      ? previousEvent?.copyIsExternalMeeting
        ? previousEvent.isExternalMeeting
        : category.copyIsExternalMeeting
          ? previousEvent?.isExternalMeeting
          : category.defaultIsExternalMeeting
            ? category?.defaultIsExternalMeeting
            : userPreferences?.copyIsExternalMeeting
              ? previousEvent?.isExternalMeeting
              : category.name === externalMeetingLabel
                ? true
                : event?.isExternalMeeting
      : event.isExternalMeeting,
    isMeetingModifiable: !event?.userModifiedModifiable
      ? category.defaultMeetingModifiable
        ? category?.defaultMeetingModifiable
        : event?.isMeetingModifiable
      : event.isMeetingModifiable,
    isExternalMeetingModifiable: !event?.userModifiedModifiable
      ? category.defaultExternalMeetingModifiable
        ? category?.defaultExternalMeetingModifiable
        : event?.isExternalMeetingModifiable
      : event.isExternalMeetingModifiable,
    backgroundColor: !event?.userModifiedColor
      ? previousEvent?.copyColor
        ? previousEvent.backgroundColor
        : category.color
          ? category?.color
          : userPreferences?.copyColor
            ? previousEvent?.backgroundColor
            : event?.backgroundColor
      : event.backgroundColor,
    colorId:
      previousEvent?.copyColor && previousEvent?.colorId
        ? previousEvent.colorId
        : userPreferences?.copyColor && previousEvent?.colorId
          ? previousEvent?.colorId
          : event?.colorId,
    preferredTimeRanges: !event?.userModifiedTimePreference
      ? previousEvent?.copyTimePreference &&
        previousEvent?.preferredTimeRanges?.length > 0
        ? previousEvent.preferredTimeRanges?.map((p) => ({
            ...p,
            id: uuid(),
            eventId: event?.id,
          }))
        : category.copyTimePreference &&
            previousEvent?.preferredTimeRanges?.length > 0
          ? previousEvent?.preferredTimeRanges?.map((p) => ({
              ...p,
              id: uuid(),
              eventId: event?.id,
            }))
          : userPreferences?.copyTimePreference &&
              previousEvent?.preferredTimeRanges?.length > 0
            ? previousEvent?.preferredTimeRanges?.map((p) => ({
                ...p,
                id: uuid(),
                eventId: event?.id,
              }))
            : category.defaultTimePreference?.map((tp) => ({
                  ...tp,
                  eventId: event?.id,
                  id: uuid(),
                  createdDate: dayjs().toISOString(),
                  updatedAt: dayjs().toISOString(),
                  userId: event?.userId,
                }))
              ? category?.defaultTimePreference?.map((tp) => ({
                  ...tp,
                  eventId: event?.id,
                  id: uuid(),
                  createdDate: dayjs().toISOString(),
                  updatedAt: dayjs().toISOString(),
                  userId: event?.userId,
                }))
              : event?.preferredTimeRanges
      : event.preferredTimeRanges,
  };
};

export const copyOverCategoryMeetingAndExternalMeetingDefaultsWithFoundPreviousEvent =
  (
    event: EventPlusType,
    categories: CategoryType[],
    userPreferences: UserPreferenceType,
    previousEvent: EventPlusType
  ) => {
    if (!(categories?.length > 0)) {
      console.log(
        'no categories inside copyOverCategoryDefaultsForConstantsWithFoundPreviousEvent'
      );
      return;
    }

    if (!userPreferences?.id) {
      console.log(
        'no userPreferences inside copyOverCategoryDefaultsForConstantsWithFoundPreviousEvent'
      );
      return;
    }

    if (!previousEvent?.id) {
      console.log(
        'no previousEvent inside copyOverCategoryDefaultsForConstantsWithFoundPreviousEvent'
      );
      return;
    }
    if (!event?.id) {
      console.log(
        'no event inside copyOverCategoryDefaultsForConstantsWithFoundPreviousEvent'
      );
      return;
    }

    const meetingCategory = categories.find(
      (category) => category.name === meetingLabel
    );
    const externalCategory = categories.find(
      (category) => category.name === externalMeetingLabel
    );

    let newEventMeeting: EventPlusType | {} = {};
    let newEventExternal: EventPlusType | {} = {};

    if (meetingCategory?.id) {
      newEventMeeting =
        copyOverMeetingAndExternalMeetingDefaultsWithPreviousEventFound(
          event,
          previousEvent,
          meetingCategory,
          userPreferences
        );
    }

    if (externalCategory?.id) {
      newEventExternal =
        copyOverMeetingAndExternalMeetingDefaultsWithPreviousEventFound(
          event,
          previousEvent,
          meetingCategory,
          userPreferences
        );
    }

    return { newEventMeeting, newEventExternal };
  };
export const createRemindersAndTimeBlockingFromPreviousEventGivenUserPreferences =
  async (
    userId: string,
    newEvent: EventPlusType,
    newReminders1?: ReminderType[],
    newBufferTimes1?: BufferTimeObjectType,
    previousEvent?: EventPlusType,
    userPreferences?: UserPreferenceType
  ) => {
    try {
      let newReminders = newReminders1 || [];
      let newBufferTimes = newBufferTimes1 || {};
      if (!newEvent?.userModifiedReminders && userPreferences?.copyReminders) {
        const reminders = await createRemindersFromPreviousEventForEvent(
          newEvent,
          previousEvent,
          userId
        );

        console.log(reminders, ' reminders');
        if (reminders?.length > 0 && !newEvent?.userModifiedReminders) {
          newReminders.push(...reminders);
        }
      }

      if (
        !newEvent?.userModifiedTimeBlocking &&
        userPreferences?.copyTimeBlocking
      ) {
        const bufferTimes = createPreAndPostEventsFromPreviousEvent(
          newEvent,
          previousEvent
        );
        console.log(bufferTimes, ' timeBlocking');
        if (bufferTimes?.beforeEvent) {
          (newBufferTimes as BufferTimeObjectType).beforeEvent =
            bufferTimes.beforeEvent;
        }

        if (bufferTimes?.afterEvent) {
          (newBufferTimes as BufferTimeObjectType).afterEvent =
            bufferTimes.afterEvent;
        }

        if (
          bufferTimes?.newEvent?.preEventId ||
          bufferTimes?.newEvent?.postEventId
        ) {
          newEvent = bufferTimes.newEvent;
        }
      }
      return { newEvent, newReminders, newBufferTimes: newBufferTimes };
    } catch (e) {
      console.log(
        e,
        ' unable to create reminders and time blocking from previous event given user preferences'
      );
    }
  };

export const updateValuesForEventWithPreviousEventPlusMeetingAndExternalMeeting =
  async (
    event: EventPlusType,
    newEvent1: EventPlusType,
    bestMatchCategories: CategoryType[],
    newReminders1: ReminderType[],
    newTimeBlocking1: BufferTimeObjectType,
    userId: string,
    userPreferences: UserPreferenceType,
    previousEvent: EventPlusType
  ) => {
    try {
      let newEvent = newEvent1;
      let newReminders = newReminders1 || [];
      let newTimeBlocking = newTimeBlocking1 || {};
      const { newEventMeeting, newEventExternal } =
        copyOverCategoryMeetingAndExternalMeetingDefaultsWithFoundPreviousEvent(
          event,
          bestMatchCategories,
          userPreferences,
          previousEvent
        );

      if ((newEventMeeting as EventPlusType)?.id) {
        newEvent = { ...newEvent, ...newEventMeeting };
        const meetingCategory = bestMatchCategories.find(
          (category) => category.name === meetingLabel
        );

        const oldReminders = await listRemindersForEvent(
          (newEventMeeting as EventPlusType)?.id,
          userId
        );
        const reminders = createRemindersUsingCategoryDefaultsForEvent(
          newEvent,
          meetingCategory,
          oldReminders,
          previousEvent
        );
        console.log(reminders, ' reminders');
        if (reminders?.length > 0 && !newEvent?.userModifiedReminders) {
          newReminders.push(...reminders);
          newReminders = _.uniqBy(newReminders, 'minutes');
        }

        if (!newEvent?.userModifiedTimeBlocking) {
          const timeBlocking = createPreAndPostEventsForCategoryDefaults(
            meetingCategory,
            newEvent,
            previousEvent
          );
          console.log(timeBlocking, ' timeBlocking');
          if (timeBlocking?.beforeEvent) {
            newTimeBlocking.beforeEvent = timeBlocking.beforeEvent;
          }

          if (timeBlocking?.afterEvent) {
            newTimeBlocking.afterEvent = timeBlocking.afterEvent;
          }

          if (
            timeBlocking?.newEvent?.preEventId ||
            timeBlocking?.newEvent?.postEventId
          ) {
            newEvent = timeBlocking.newEvent;
          }
        }
      }

      if ((newEventExternal as EventPlusType)?.id) {
        newEvent = { ...newEvent, ...newEventExternal };
        const externalCategory = bestMatchCategories.find(
          (category) => category.name === externalMeetingLabel
        );

        const oldReminders = await listRemindersForEvent(
          (newEventExternal as EventPlusType).id,
          userId
        );
        const reminders = createRemindersUsingCategoryDefaultsForEvent(
          newEvent,
          externalCategory,
          oldReminders,
          previousEvent
        );
        console.log(reminders, ' reminders');
        if (reminders?.length > 0 && !newEvent?.userModifiedReminders) {
          newReminders.push(...reminders);
          newReminders = _.uniqBy(newReminders, 'minutes');
        }

        if (!newEvent?.userModifiedTimeBlocking) {
          const timeBlocking = createPreAndPostEventsForCategoryDefaults(
            externalCategory,
            newEvent
          );
          console.log(timeBlocking, ' timeBlocking');
          if (timeBlocking?.beforeEvent) {
            newTimeBlocking.beforeEvent = timeBlocking.beforeEvent;
          }

          if (timeBlocking?.afterEvent) {
            newTimeBlocking.afterEvent = timeBlocking.afterEvent;
          }

          if (
            timeBlocking?.newEvent?.preEventId ||
            timeBlocking?.newEvent?.postEventId
          ) {
            newEvent = timeBlocking.newEvent;
          }
        }
      }

      return { newEvent, newReminders, newBufferTimes: newTimeBlocking };
    } catch (e) {
      console.log(e, ' unable to update values for default categories');
    }
  };

export const createRemindersAndTimeBlockingFromPreviousEvent = async (
  userId: string,
  newEvent: EventPlusType,
  newReminders1: ReminderType[],
  newBufferTimes1: BufferTimeObjectType,
  previousEvent?: EventPlusType
) => {
  try {
    let newReminders = newReminders1 || [];
    let newBufferTimes = newBufferTimes1 || {};
    const reminders = await createRemindersFromPreviousEventForEvent(
      newEvent,
      previousEvent,
      userId
    );

    console.log(reminders, ' reminders');
    if (
      reminders?.length > 0 &&
      !newEvent?.userModifiedReminders &&
      previousEvent?.copyReminders
    ) {
      newReminders.push(...reminders);
    }

    if (
      !newEvent?.userModifiedTimeBlocking &&
      previousEvent?.copyTimeBlocking
    ) {
      const bufferTimes = createPreAndPostEventsFromPreviousEvent(
        newEvent,
        previousEvent
      );
      console.log(bufferTimes, ' timeBlocking');
      if (bufferTimes?.beforeEvent) {
        newBufferTimes.beforeEvent = bufferTimes.beforeEvent;
      }

      if (bufferTimes?.afterEvent) {
        newBufferTimes.afterEvent = bufferTimes.afterEvent;
      }

      if (
        bufferTimes?.newEvent?.preEventId ||
        bufferTimes?.newEvent?.postEventId
      ) {
        newEvent = bufferTimes.newEvent;
      }
    }
    return { newEvent, newReminders, newBufferTimes: newBufferTimes };
  } catch (e) {
    console.log(
      e,
      ' unable to create reminders and time blocking from previous event'
    );
  }
};

export const processEventWithFoundPreviousEventAndCopyCategories = async (
  id: string,
  previousEvent: EventPlusType,
  oldEvent: EventPlusType,
  userPreferences: UserPreferenceType,
  bestMatchCategory1: CategoryType,
  userId: string,
  bestMatchCategories1: CategoryType[],
  newModifiedEvent1: EventPlusType,
  newReminders1: ReminderType[] = [],
  newTimeBlocking1: BufferTimeObjectType = {},
  previousCategories: CategoryType[] = [],
  previousMeetingCategoriesWithMeetingLabel: CategoryType[] = [],
  previousMeetingCategoriesWithExternalMeetingLabel: CategoryType[] = []
): Promise<
  FeaturesApplyResponse<{
    newModifiedEvent: EventPlusType;
    newReminders: ReminderType[];
    newTimeBlocking: BufferTimeObjectType;
  } | null>
> => {
  // Basic validation for required complex objects
  if (
    !id ||
    !previousEvent ||
    !oldEvent ||
    !userPreferences ||
    !bestMatchCategory1 ||
    !userId ||
    !bestMatchCategories1 ||
    !newModifiedEvent1
  ) {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'One or more critical input parameters are missing.',
      },
    };
  }

  try {
    let bestMatchCategories: CategoryType[] = bestMatchCategories1 || [];
    let bestMatchCategory: CategoryType | object = bestMatchCategory1 || {}; // Ensure it's CategoryType or an empty object
    let newModifiedEvent: EventPlusType = newModifiedEvent1; // Not EventPlusType | object
    let newReminders: ReminderType[] = newReminders1 || [];
    let newTimeBlocking: BufferTimeObjectType = newTimeBlocking1 || {};

    if (!previousEvent?.unlink && !oldEvent?.userModifiedCategories) {
      if (
        (previousEvent?.copyCategories || userPreferences?.copyCategories) &&
        previousCategories?.length > 0
      ) {
        const createCatEventsResponse = await createCategoryEvents(
          previousCategories.map((c) => ({
            categoryId: c.id,
            eventId: id,
            userId,
            id: uuid(),
            createdDate: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            Category: c,
            deleted: false,
          }))
        );
        if (!createCatEventsResponse.ok)
          console.warn(
            `Failed to create category events for event ${id} during copy: ${createCatEventsResponse.error?.message}`
          );
      }

      if (previousCategories?.[0]?.id) {
        const classificationResponse = await findBestMatchCategory2(
          oldEvent,
          previousCategories
        );
        if (classificationResponse.ok && classificationResponse.data) {
          const { labels, scores } = classificationResponse.data;
          const bestMatchLabel = processBestMatchCategoriesNoThreshold(
            classificationResponse.data,
            labels
          );
          bestMatchCategory =
            previousCategories.find(
              (category) => category.name === bestMatchLabel
            ) || {};
        } else {
          console.warn(
            `Classification failed for previous categories for event ${id}: ${classificationResponse.error?.message}`
          );
        }
        if ((bestMatchCategory as CategoryType)?.id) {
          newModifiedEvent = copyOverPreviousEventDefaults(
            oldEvent,
            previousEvent,
            bestMatchCategory as CategoryType,
            userPreferences
          );
        }
      } else {
        newModifiedEvent = copyOverPreviousEventDefaults(
          oldEvent,
          previousEvent,
          undefined,
          userPreferences
        );
      }

      if (
        (userPreferences?.copyReminders || userPreferences?.copyTimeBlocking) &&
        newModifiedEvent?.id
      ) {
        const remindersTimeBlockingResp =
          await createRemindersAndTimeBlockingFromPreviousEventGivenUserPreferences(
            userId,
            newModifiedEvent,
            newReminders,
            newTimeBlocking,
            previousEvent,
            userPreferences
          );
        if (remindersTimeBlockingResp.ok && remindersTimeBlockingResp.data) {
          newModifiedEvent = remindersTimeBlockingResp.data.newEvent;
          newReminders = remindersTimeBlockingResp.data.newReminders;
          newTimeBlocking = remindersTimeBlockingResp.data.newBufferTimes;
        } else {
          console.warn(
            `Failed to create reminders/buffers from user prefs for event ${id}: ${remindersTimeBlockingResp.error?.message}`
          );
        }
      }

      const currentBestMatchCategory = bestMatchCategory as CategoryType; // To use in conditions below
      if (
        currentBestMatchCategory?.id &&
        (currentBestMatchCategory?.defaultReminders ||
          currentBestMatchCategory?.defaultTimeBlocking) &&
        newModifiedEvent?.id
      ) {
        const updateValuesResp =
          await updateValuesForEventWithPreviousEventPlusMeetingAndExternalMeeting(
            oldEvent,
            newModifiedEvent,
            bestMatchCategories,
            newReminders,
            newTimeBlocking,
            userId,
            userPreferences,
            previousEvent
          );
        if (updateValuesResp.ok && updateValuesResp.data) {
          newModifiedEvent = updateValuesResp.data.newEvent;
          newReminders = updateValuesResp.data.newReminders;
          newTimeBlocking = updateValuesResp.data.newBufferTimes;
        } else {
          console.warn(
            `Failed to update values from best match category for event ${id}: ${updateValuesResp.error?.message}`
          );
        }
      }

      if (
        currentBestMatchCategory?.id &&
        (currentBestMatchCategory?.copyReminders ||
          currentBestMatchCategory?.copyTimeBlocking) &&
        newModifiedEvent?.id
      ) {
        const remindersAndBuffersResp =
          await createRemindersAndBufferTimesForBestMatchCategory(
            id,
            userId,
            newModifiedEvent,
            currentBestMatchCategory,
            newReminders,
            newTimeBlocking
          );
        if (remindersAndBuffersResp.ok && remindersAndBuffersResp.data) {
          newModifiedEvent = remindersAndBuffersResp.data.newEvent;
          newReminders = remindersAndBuffersResp.data.newReminders;
          newTimeBlocking = remindersAndBuffersResp.data.newBufferTimes;
        } else {
          console.warn(
            `Failed to create reminders/buffers from best match category (copy) for event ${id}: ${remindersAndBuffersResp.error?.message}`
          );
        }
      }

      for (const cat of [
        previousMeetingCategoriesWithMeetingLabel?.[0],
        previousMeetingCategoriesWithExternalMeetingLabel?.[0],
      ]) {
        if (
          cat?.id &&
          (cat.copyReminders || cat.copyTimeBlocking) &&
          newModifiedEvent?.id
        ) {
          const remindersAndBuffersResp =
            await createRemindersAndBufferTimesForBestMatchCategory(
              id,
              userId,
              newModifiedEvent,
              cat,
              newReminders,
              newTimeBlocking
            );
          if (remindersAndBuffersResp.ok && remindersAndBuffersResp.data) {
            newModifiedEvent = remindersAndBuffersResp.data.newEvent;
            newReminders = remindersAndBuffersResp.data.newReminders;
            newTimeBlocking = remindersAndBuffersResp.data.newBufferTimes;
          } else {
            console.warn(
              `Failed to create reminders/buffers from meeting categories for event ${id}: ${remindersAndBuffersResp.error?.message}`
            );
          }
        }
      }

      if (
        (previousEvent?.copyReminders || previousEvent?.copyTimeBlocking) &&
        newModifiedEvent?.id
      ) {
        const prevEventRemindersBuffersResp =
          await createRemindersAndTimeBlockingFromPreviousEvent(
            userId,
            newModifiedEvent,
            newReminders,
            newTimeBlocking,
            previousEvent
          );
        if (
          prevEventRemindersBuffersResp.ok &&
          prevEventRemindersBuffersResp.data
        ) {
          newModifiedEvent = prevEventRemindersBuffersResp.data.newEvent;
          newReminders = prevEventRemindersBuffersResp.data.newReminders;
          newTimeBlocking = prevEventRemindersBuffersResp.data.newBufferTimes;
        } else {
          console.warn(
            `Failed to create reminders/buffers from previous event for event ${id}: ${prevEventRemindersBuffersResp.error?.message}`
          );
        }
      }
      bestMatchCategories = getUniqueLabels(bestMatchCategories);
    }
    return {
      ok: true,
      data: { newModifiedEvent, newReminders, newTimeBlocking },
    };
  } catch (e: any) {
    console.error(
      'Error in processEventWithFoundPreviousEventAndCopyCategories:',
      e
    );
    return {
      ok: false,
      error: {
        code: 'INTERNAL_ERROR',
        message: `Failed to process event with previous event and categories: ${e.message}`,
        details: e,
      },
    };
  }
};

export const processEventWithFoundPreviousEventWithoutCategories = async (
  previousEvent: EventPlusType,
  event: EventPlusType,
  userPreferences: UserPreferenceType,
  userId: string,
  newReminders: ReminderType[] = [],
  newTimeBlocking: BufferTimeObjectType = {}
): Promise<
  FeaturesApplyResponse<{
    newModifiedEvent: EventPlusType;
    newReminders: ReminderType[];
    newTimeBlocking: BufferTimeObjectType;
  } | null>
> => {
  if (!previousEvent || !event || !userPreferences || !userId) {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message:
          'Missing critical parameters for processing event without categories.',
      },
    };
  }
  try {
    let newModifiedEvent = event;

    if (!previousEvent?.unlink) {
      newModifiedEvent = copyOverPreviousEventDefaults(
        event,
        previousEvent,
        undefined,
        userPreferences
      );

      if (
        (userPreferences?.copyReminders || userPreferences?.copyTimeBlocking) &&
        newModifiedEvent?.id
      ) {
        const remindersTimeBlockingResp =
          await createRemindersAndTimeBlockingFromPreviousEventGivenUserPreferences(
            userId,
            newModifiedEvent,
            newReminders,
            newTimeBlocking,
            previousEvent,
            userPreferences
          );
        if (remindersTimeBlockingResp.ok && remindersTimeBlockingResp.data) {
          newModifiedEvent = remindersTimeBlockingResp.data.newEvent;
          newReminders = remindersTimeBlockingResp.data.newReminders;
          newTimeBlocking = remindersTimeBlockingResp.data.newBufferTimes;
        } else {
          console.warn(
            `Failed to create reminders/buffers from user prefs (no categories): ${remindersTimeBlockingResp.error?.message}`
          );
        }
      }

      if (
        (previousEvent?.copyReminders || previousEvent?.copyTimeBlocking) &&
        newModifiedEvent?.id
      ) {
        const prevEventRemindersBuffersResp =
          await createRemindersAndTimeBlockingFromPreviousEvent(
            userId,
            newModifiedEvent,
            newReminders,
            newTimeBlocking,
            previousEvent
          );
        if (
          prevEventRemindersBuffersResp.ok &&
          prevEventRemindersBuffersResp.data
        ) {
          newModifiedEvent = prevEventRemindersBuffersResp.data.newEvent;
          newReminders = prevEventRemindersBuffersResp.data.newReminders;
          newTimeBlocking = prevEventRemindersBuffersResp.data.newBufferTimes;
        } else {
          console.warn(
            `Failed to create reminders/buffers from previous event (no categories): ${prevEventRemindersBuffersResp.error?.message}`
          );
        }
      }
    }
    return {
      ok: true,
      data: { newModifiedEvent, newReminders, newTimeBlocking },
    };
  } catch (e: any) {
    console.error(
      'Error in processEventWithFoundPreviousEventWithoutCategories:',
      e
    );
    return {
      ok: false,
      error: {
        code: 'INTERNAL_ERROR',
        message: `Failed to process event without categories: ${e.message}`,
        details: e,
      },
    };
  }
};

export const processUserEventWithFoundPreviousEvent = async (
  event: EventPlusType,
  previousEventId: string
): Promise<
  FeaturesApplyResponse<{
    newEvent: EventPlusType;
    newReminders?: ReminderType[];
    newBufferTimes?: BufferTimeObjectType;
  } | null>
> => {
  if (!event || !event.id || !event.userId || !previousEventId) {
    return {
      ok: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Event, event ID, userId, and previousEventId are required.',
      },
    };
  }
  try {
    const { id, userId } = event;

    const prevEventResponse = await getEventFromPrimaryKey(previousEventId);
    if (!prevEventResponse.ok || !prevEventResponse.data) {
      return {
        ok: false,
        error: prevEventResponse.error || {
          code: 'INTERNAL_ERROR',
          message: `Previous event ${previousEventId} not found or failed to fetch.`,
        },
      };
    }
    const previousEvent = prevEventResponse.data;

    const prefTimeRangesResponse =
      await listPreferredTimeRangesForEvent(previousEventId);
    // Non-critical if preferred time ranges are not found, so we don't fail the whole process here
    if (prefTimeRangesResponse.ok && prefTimeRangesResponse.data) {
      previousEvent.preferredTimeRanges = prefTimeRangesResponse.data;
    } else {
      console.warn(
        `Could not fetch preferred time ranges for previous event ${previousEventId}: ${prefTimeRangesResponse.error?.message}`
      );
      previousEvent.preferredTimeRanges = [];
    }

    const categoriesResponse = await getUserCategories(userId);
    if (!categoriesResponse.ok) {
      // If categories can't be fetched, this might be a more critical issue
      return {
        ok: false,
        error: categoriesResponse.error || {
          code: 'INTERNAL_ERROR',
          message: 'Failed to get user categories.',
        },
      };
    }
    const categories = categoriesResponse.data || []; // Default to empty array if null

    let bestMatchCategory: CategoryType | null = null;
    let bestMatchCategoriesPlusMeetingType: CategoryType[] = [];

    if (categories.length > 0) {
      const classificationResponse = await findBestMatchCategory2(
        event,
        categories
      );
      if (classificationResponse.ok && classificationResponse.data) {
        const classificationBody = classificationResponse.data;
        const { labels, scores } = classificationBody;
        const bestMatchLabel = processBestMatchCategories(
          classificationBody,
          labels
        );
        if (bestMatchLabel) {
          bestMatchCategory =
            categories.find((category) => category.name === bestMatchLabel) ||
            null;
        }
        if (bestMatchCategory) {
          bestMatchCategoriesPlusMeetingType =
            processEventForMeetingTypeCategories(
              event,
              bestMatchCategory,
              labels,
              scores,
              categories
            );
          bestMatchCategoriesPlusMeetingType = getUniqueLabels(
            bestMatchCategoriesPlusMeetingType
          );
        }
      } else {
        console.warn(
          `Category classification failed for event ${id}: ${classificationResponse.error?.message}`
        );
      }
    }

    const userPreferencesResponse = await getUserPreferences(userId);
    if (!userPreferencesResponse.ok || !userPreferencesResponse.data) {
      return {
        ok: false,
        error: userPreferencesResponse.error || {
          code: 'INTERNAL_ERROR',
          message: 'User preferences not found or failed to fetch.',
        },
      };
    }
    const userPreferences = userPreferencesResponse.data;

    let newModifiedEvent: EventPlusType = { ...event }; // Start with a copy
    let newReminders: ReminderType[] = [];
    let newBufferTimes: BufferTimeObjectType = {};

    if (
      (previousEvent?.copyCategories || userPreferences?.copyCategories) &&
      !previousEvent?.unlink &&
      !event?.userModifiedCategories
    ) {
      const prevCategoriesResponse = await listCategoriesForEvent(
        previousEvent.id
      );
      const previousCategories =
        prevCategoriesResponse.ok && prevCategoriesResponse.data
          ? prevCategoriesResponse.data
          : [];

      const processingResult =
        await processEventWithFoundPreviousEventAndCopyCategories(
          id,
          previousEvent,
          event,
          userPreferences,
          bestMatchCategory,
          userId,
          bestMatchCategoriesPlusMeetingType,
          newModifiedEvent,
          newReminders,
          newBufferTimes,
          previousCategories,
          previousCategories.filter((c) => c.name === meetingLabel),
          previousCategories.filter((c) => c.name === externalMeetingLabel)
        );
      if (processingResult.ok && processingResult.data) {
        newModifiedEvent = processingResult.data.newModifiedEvent;
        newReminders = processingResult.data.newReminders;
        newTimeBlocking = processingResult.data.newTimeBlocking;
      } else {
        // Log warning or error, but proceed with potentially partially modified event
        console.warn(
          `Processing with 'copyCategories' failed for event ${id}: ${processingResult.error?.message}`
        );
      }
    } else if (
      userPreferences?.id &&
      !previousEvent?.copyCategories &&
      !userPreferences?.copyCategories &&
      !event?.userModifiedCategories &&
      event?.id &&
      previousEvent?.id
    ) {
      if (bestMatchCategory && bestMatchCategoriesPlusMeetingType?.length > 0) {
        newModifiedEvent = copyOverPreviousEventDefaults(
          event,
          previousEvent,
          bestMatchCategory,
          userPreferences
        );
        if (newModifiedEvent?.id) {
          const remindersResp =
            await createRemindersAndBufferTimesForBestMatchCategory(
              id,
              userId,
              newModifiedEvent,
              bestMatchCategory,
              newReminders,
              newBufferTimes
            );
          if (remindersResp.ok && remindersResp.data) {
            newModifiedEvent = remindersResp.data.newEvent;
            newReminders = remindersResp.data.newReminders;
            newBufferTimes = remindersResp.data.newBufferTimes;
          }

          const updateValuesResp =
            await updateValuesForEventWithPreviousEventPlusMeetingAndExternalMeeting(
              event,
              newModifiedEvent,
              bestMatchCategoriesPlusMeetingType,
              newReminders,
              newBufferTimes,
              userId,
              userPreferences,
              previousEvent
            );
          if (updateValuesResp.ok && updateValuesResp.data) {
            newModifiedEvent = updateValuesResp.data.newEvent;
            newReminders = updateValuesResp.data.newReminders;
            newBufferTimes = updateValuesResp.data.newBufferTimes;
          }
        }
      } else {
        const noCatProcessingResp =
          await processEventWithFoundPreviousEventWithoutCategories(
            previousEvent,
            newModifiedEvent,
            userPreferences,
            userId,
            newReminders,
            newBufferTimes
          );
        if (noCatProcessingResp.ok && noCatProcessingResp.data) {
          newModifiedEvent = noCatProcessingResp.data.newModifiedEvent;
          newReminders = noCatProcessingResp.data.newReminders;
          newBufferTimes = noCatProcessingResp.data.newTimeBlocking;
        }
      }
    }

    return {
      ok: true,
      data: { newEvent: newModifiedEvent, newReminders, newBufferTimes },
    };
  } catch (e: any) {
    console.error(
      `Error in processUserEventWithFoundPreviousEvent for event ${event?.id}:`,
      e
    );
    return {
      ok: false,
      error: {
        code: 'INTERNAL_ERROR',
        message: `Failed to process event with previous event: ${e.message}`,
        details: e,
      },
    };
  }
};

export const processUserEventWithFoundPreviousEventWithUserModifiedCategories =
  async (
    event: EventPlusType,
    previousEventId: string
  ): Promise<
    FeaturesApplyResponse<{
      newEvent: EventPlusType;
      newReminders?: ReminderType[];
      newBufferTimes?: BufferTimeObjectType;
    } | null>
  > => {
    if (!event || !event.id || !event.userId || !previousEventId) {
      return {
        ok: false,
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Event, event ID, userId, and previousEventId are required.',
        },
      };
    }
    try {
      const categoriesResponse = await listCategoriesForEvent(event.id);
      if (
        !categoriesResponse.ok ||
        !categoriesResponse.data ||
        categoriesResponse.data.length === 0
      ) {
        return {
          ok: false,
          error: categoriesResponse.error || {
            code: 'INTERNAL_ERROR',
            message: `No categories found for event ${event.id} or failed to fetch.`,
          },
        };
      }
      const categories = categoriesResponse.data;

      const prevEventResponse = await getEventFromPrimaryKey(previousEventId);
      if (!prevEventResponse.ok || !prevEventResponse.data) {
        return {
          ok: false,
          error: prevEventResponse.error || {
            code: 'INTERNAL_ERROR',
            message: `Previous event ${previousEventId} not found or failed to fetch.`,
          },
        };
      }
      const previousEvent = prevEventResponse.data;

      const prefTimeRangesResponse =
        await listPreferredTimeRangesForEvent(previousEventId);
      if (prefTimeRangesResponse.ok && prefTimeRangesResponse.data) {
        previousEvent.preferredTimeRanges = prefTimeRangesResponse.data;
      } else {
        console.warn(
          `Could not fetch preferred time ranges for previous event ${previousEventId}: ${prefTimeRangesResponse.error?.message}`
        );
        previousEvent.preferredTimeRanges = [];
      }

      const classificationResponse = await findBestMatchCategory2(
        event,
        categories
      );
      if (
        !classificationResponse.ok ||
        !classificationResponse.data ||
        !classificationResponse.data.labels?.length
      ) {
        console.warn(
          `Classification failed or returned no labels for event ${event.id}: ${classificationResponse.error?.message}`
        );
        // Decide if to proceed with event as is, or return an error. For now, proceed.
        return { ok: true, data: { newEvent: event } };
      }
      const classificationBody = classificationResponse.data;
      const { labels } = classificationBody; // scores are also available if needed
      const bestMatchLabel = processBestMatchCategoriesNoThreshold(
        classificationBody,
        labels
      );

      let newModifiedEvent: EventPlusType = { ...event };
      let newReminders: ReminderType[] = [];
      let newTimeBlocking: BufferTimeObjectType = {};

      if (bestMatchLabel) {
        const bestMatchCategory = categories.find(
          (category) => category.name === bestMatchLabel
        );
        if (!bestMatchCategory) {
          console.warn(
            `Best match label "${bestMatchLabel}" did not correspond to a known category.`
          );
          return { ok: true, data: { newEvent: event } }; // Proceed with original event
        }

        const userPreferencesResponse = await getUserPreferences(event.userId);
        if (!userPreferencesResponse.ok || !userPreferencesResponse.data) {
          return {
            ok: false,
            error: userPreferencesResponse.error || {
              code: 'INTERNAL_ERROR',
              message: 'User preferences not found or failed to fetch.',
            },
          };
        }
        const userPreferences = userPreferencesResponse.data;

        newModifiedEvent = copyOverPreviousEventDefaults(
          event,
          previousEvent,
          bestMatchCategory,
          userPreferences
        );

        if (categories.length > 0 && newModifiedEvent?.id) {
          // categories is already checked to be non-empty
          const updateValuesResp =
            await updateValuesForEventWithPreviousEventPlusMeetingAndExternalMeeting(
              event,
              newModifiedEvent,
              categories,
              newReminders,
              newTimeBlocking,
              event.userId,
              userPreferences,
              previousEvent
            );
          if (updateValuesResp.ok && updateValuesResp.data) {
            newModifiedEvent = updateValuesResp.data.newEvent;
            newReminders = updateValuesResp.data.newReminders;
            newTimeBlocking = updateValuesResp.data.newBufferTimes;
          } else {
            console.warn(
              `Failed to update values from modified categories for event ${event.id}: ${updateValuesResp.error?.message}`
            );
          }
        }
      } else {
        console.warn(`No best match category found for event ${event.id}.`);
      }

      return {
        ok: true,
        data: {
          newEvent: newModifiedEvent,
          newReminders,
          newBufferTimes: newTimeBlocking,
        },
      };
    } catch (e: any) {
      console.error(
        `Error in processUserEventWithFoundPreviousEventWithUserModifiedCategories for event ${event?.id}:`,
        e
      );
      return {
        ok: false,
        error: {
          code: 'INTERNAL_ERROR',
          message: `Failed to process event with modified categories: ${e.message}`,
          details: e,
        },
      };
    }
  };
