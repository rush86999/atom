import {
  authApiToken,
  bucketName,
  optaplannerDuration,
  optaplannerShortDuration,
  classificationUrl,
  dayOfWeekIntToString,
  defaultOpenAIAPIKey,
  externalMeetingLabel,
  hasuraAdminSecret,
  hasuraGraphUrl,
  meetingLabel,
  minThresholdScore,
  onOptaPlanCalendarAdminCallBackUrl,
  optaPlannerPassword,
  optaPlannerUrl,
  optaPlannerUsername,
} from '@schedule_event/_libs/constants'; // Removed OpenSearch constants
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
  ReturnBodyForHostForOptaplannerPrepType,
  ReturnBodyForAttendeeForOptaplannerPrepType,
  ReturnBodyForExternalAttendeeForOptaplannerPrepType,
  PlannerRequestBodyType,
  FreemiumType,
  esResponseBody,
  CategoryType,
  ClassificationResponseBodyType,
  BufferTimeObjectType,
  ReminderType,
  CategoryEventType,
} from '@schedule_event/_libs/types'; // Removed OpenSearchGetResponseBodyType
import got from 'got';
import { v4 as uuid } from 'uuid';
import { getISODay, setISODay } from 'date-fns';
import dayjs from 'dayjs';
// import isoWeek from 'dayjs/plugin/isoWeek'
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import _ from 'lodash';
import { PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
import AWS from 'aws-sdk';
// Removed: import { OpenSearchResponseBodyType } from "./types/OpenSearchResponseType"
import { Configuration, OpenAIApi } from 'openai';
import {
  getEventById,
  searchTrainingEvents,
  deleteTrainingEventsByIds,
  upsertTrainingEvents,
  TrainingEventSchema,
  EventSchema,
} from '@functions/_utils/lancedb_service'; // Added LanceDB imports

// dayjs.extend(isoWeek)
dayjs.extend(duration);
dayjs.extend(isBetween);
dayjs.extend(timezone);
dayjs.extend(utc);

const s3Client = new S3Client({
  credentials: {
    accessKeyId: process.env.S3_ACCESS_KEY,
    secretAccessKey: process.env.S3_SECRET_KEY,
  },
  endpoint: process.env.S3_ENDPOINT,
  forcePathStyle: true,
});

const configuration = new Configuration({
  apiKey: defaultOpenAIAPIKey,
});
const openai = new OpenAIApi(configuration);

export const getEventVectorById = async (
  id: string
): Promise<number[] | null> => {
  try {
    const event = await getEventById(id); // from lancedb_service
    if (event && event.vector) {
      console.log(`Vector found for event ID ${id}`);
      return event.vector;
    }
    console.log(`No event or vector found for ID ${id}`);
    return null;
  } catch (e) {
    console.error(`Error fetching event vector for ID ${id} from LanceDB:`, e);
    return null;
  }
};

export const convertEventToVectorSpace2 = async (
  event: EventType
): Promise<number[]> => {
  try {
    if (!event) {
      throw new Error('no event provided to convertEventToVectorSpace2');
    }
    const { summary, notes } = event;
    const text = `${summary}${notes ? `: ${notes}` : ''}`;

    if (!text || text.trim() === ':') {
      console.log(
        'Empty or invalid text for embedding, returning empty array.'
      );
      return [];
    }

    const embeddingRequest: OpenAI.Embeddings.EmbeddingCreateParams = {
      model: 'text-embedding-ada-002',
      input: text,
    };
    const res = await openai.embeddings.create(embeddingRequest);
    const vector = res?.data?.[0]?.embedding;

    console.log(
      vector
        ? `Vector generated with length: ${vector.length}`
        : 'No vector generated',
      ' vector inside convertEventToVectorSpace2'
    );
    return vector;
  } catch (e) {
    console.error(e, ' unable to convertEventToVectorSpace using OpenAI');
    throw e;
  }
};

export const searchTrainingDataByVector = async (
  userId: string,
  searchVector: number[]
): Promise<TrainingEventSchema | null> => {
  try {
    // Assuming min_score logic is handled by LanceDB's search or not strictly needed,
    // or would require more complex query building if it is.
    // For now, simple search and return top hit.
    const results = await searchTrainingEvents(
      searchVector,
      1, // We need only the top match
      `userId = '${userId.replace(/'/g, "''")}'`
    );
    if (results && results.length > 0) {
      // console.log(results[0], ' search data from LanceDB training_data');
      return results[0];
    }
    return null;
  } catch (e) {
    console.error('Error searching training data in LanceDB:', e);
    throw e; // Or return null based on desired error handling
  }
};

export const deleteTrainingDataById = async (id: string): Promise<void> => {
  try {
    await deleteTrainingEventsByIds([id]);
    console.log(
      `Successfully deleted training data for ID: ${id} from LanceDB.`
    );
  } catch (e) {
    console.error(`Error deleting training data for ID ${id} from LanceDB:`, e);
    throw e;
  }
};

export const addTrainingData = async (
  trainingEntry: TrainingEventSchema
): Promise<void> => {
  try {
    await upsertTrainingEvents([trainingEntry]);
    console.log(
      `Successfully added/updated training data for ID: ${trainingEntry.id} in LanceDB.`
    );
  } catch (e) {
    console.error(
      `Error adding/updating training data for ID ${trainingEntry.id} in LanceDB:`,
      e
    );
    throw e;
  }
};

export const convertEventTitleToOpenAIVector = async (title: string) => {
  try {
    const embeddingRequest: OpenAI.Embeddings.EmbeddingCreateParams = {
      model: 'text-embedding-ada-002',
      input: title,
    };

    const res = await openai.embeddings.create(embeddingRequest);
    console.log(res, ' res inside convertEventTitleToOpenAIVectors');
    return res?.data?.[0]?.embedding;
  } catch (e) {
    console.log(e, ' unable to convert event title to openaivectors');
  }
};

export const listMeetingAssistPreferredTimeRangesGivenMeetingId = async (
  meetingId: string
) => {
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

    console.log(res, ' res from listMeetingAssistAttendees ');

    return res?.data?.Meeting_Assist_Preferred_Time_Range;
  } catch (e) {
    console.log(e, ' uanble to list meeting assist preferred time ranges');
  }
};

export const listMeetingAssistAttendeesGivenMeetingId = async (
  meetingId: string
) => {
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
                    primaryEmail
                    timezone
                    updatedAt
                    userId
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

    console.log(res, ' res from listMeetingAssistAttendees ');

    return res?.data?.Meeting_Assist_Attendee;
  } catch (e) {
    console.log(e, ' unable to list meeting assist attendees');
  }
};

export const getMeetingAssistAttendee = async (id: string) => {
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
                    primaryEmail
                    timezone
                    updatedAt
                    userId
                    externalAttendee
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

    return res?.data?.Meeting_Assist_Attendee_by_pk;
  } catch (e) {
    console.log(e, ' unable to get meeting assist attendee');
  }
};

export const getMeetingAssist = async (id: string) => {
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

    return res?.data?.Meeting_Assist_by_pk;
  } catch (e) {
    console.log(e, ' unable to get meeting assist from id');
  }
};

export const listMeetingAssistEventsForAttendeeGivenDates = async (
  attendeeId: string,
  hostStartDate: string,
  hostEndDate: string,
  userTimezone: string,
  hostTimezone: string
) => {
  try {
    const operationName = 'ListMeetingAssistEventsForAttendeeGivenDates';
    const query = `
            query ListMeetingAssistEventsForAttendeeGivenDates($attendeeId: String!, $startDate: timestamp!, $endDate: timestamp!) {
                Meeting_Assist_Event(where: {attendeeId: {_eq: $attendeeId}, startDate: {_gte: $startDate}, endDate: {_lte: $endDate}}) {
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
                    eventId
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
                    originalTimezone
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
    return res?.data?.Meeting_Assist_Event;
  } catch (e) {
    console.log(
      e,
      ' unable to list meeting assist events for attendee given dates'
    );
  }
};

export const listEventsForDate = async (
  userId: string,
  startDate: string,
  endDate: string,
  timezone: string
) => {
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

    console.log(res, ' res from listEventsforUser');
    return res?.data?.Event;
  } catch (e) {
    console.log(e, ' unable to list events for date');
  }
};

export const listEventsForUserGivenDates = async (
  userId: string,
  hostStartDate: string,
  hostEndDate: string,
  userTimezone: string,
  hostTimezone: string
) => {
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
    // get events
    // local date
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

    console.log(res, ' res from listEventsforUser');
    return res?.data?.Event;
  } catch (e) {
    console.log(e, ' listEventsForUser');
  }
};

export const processMeetingAssistForOptaplanner = async () => {
  try {
  } catch (e) {
    console.log(e, ' unable to process meeting assist for optaplanner');
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

    // try add
    if (!dayjs(dateObjectWithSetISODay).isBetween(startDate, endDate)) {
      dateObjectWithSetISODay = dayjs(originalDateObjectWithSetISODay)
        .add(1, 'week')
        .toDate();
    }

    // try subtract
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
  hostTimezone: string,
  preferredStartTimeRange?: MeetingAssistPreferredTimeRangeType
): EventType => {
  let startDate = dayjs(windowStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .format();
  if (preferredStartTimeRange?.dayOfWeek > 0) {
    startDate = dayjs(startDate)
      .isoWeek(preferredStartTimeRange?.dayOfWeek)
      .format();
  }

  if (preferredStartTimeRange?.startTime) {
    const startTime = preferredStartTimeRange?.startTime;
    const hour = parseInt(startTime.slice(0, 2), 10);
    const minute = parseInt(startTime.slice(3), 10);

    startDate = dayjs(startDate).hour(hour).minute(minute).format();
  }

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

export const listPreferredTimeRangesForEvent = async (eventId: string) => {
  try {
    // validate
    if (!eventId) {
      console.log(
        eventId,
        ' no eventId inside listPreferredTimeRangesForEvent'
      );
    }
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

    return res?.data?.PreferredTimeRange;
  } catch (e) {
    console.log(e, ' unable to list preferred time ranges for event');
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
  // validate
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
  /**
     * const startDuration = dayjs.duration({ hours: startHour, minutes: startMinute })
      const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute })
      const totalDuration = endDuration.subtract(startDuration)
      return totalDuration.asHours()
     */

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
      let foundSpace = false;
      let index = 0;
      while (!foundSpace && index < filteredEvents.length) {
        const possibleEndDate = dayjs(
          filteredEvents[index].startDate.slice(0, 19)
        ).tz(timezone, true);

        const possibleStartDate = dayjs(possibleEndDate.format().slice(0, 19))
          .tz(timezone, true)
          .subtract(userPreference.breakLength, 'minute');
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
            startDate: possibleStartDate.toISOString(),
            endDate: possibleEndDate.toISOString(),
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
  // validate
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
  // validate
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
    // validate
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

      // validate values before calculating
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
        // return empty as outside of work time
        return null;
      }

      // change to work start time as work start time after start date
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

      // validate
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

      // guarantee breaks
      const hoursMustBeBreak =
        workingHours * (1 - userPreferences.maxWorkLoadPercent / 100);

      console.log(hoursMustBeBreak, ' hoursMustBeBreak');

      if (hoursAvailable < hoursMustBeBreak) {
        hoursAvailable = hoursMustBeBreak;
      }
      // no hours available
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

    // validate values before calculating
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
    // validate
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
    // guarantee breaks
    const hoursMustBeBreak =
      workingHours * (1 - userPreferences.maxWorkLoadPercent / 100);

    console.log(hoursMustBeBreak, ' hoursMustBeBreak');
    console.log(hoursAvailable, ' hoursAvailable');

    if (hoursAvailable < hoursMustBeBreak) {
      hoursAvailable = hoursMustBeBreak;
    }

    console.log(hoursAvailable, ' hoursAvailable');

    // no hours available
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

        // validate values before calculating
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
          // return empty as outside of work time
          continue;
        }

        // change to work start time as before start time
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

      // validate values before calculating
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
  // 7 days in a week
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
        .format('HH:mm:ss') as Time,
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
        .format('HH:mm:ss') as Time,
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
    // firstday can be started outside of work time
    // prioritize work start time over when it is pressed
    // if firstDay start is after end time return []
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
    // month is zero-indexed
    // const month = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).month()
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

    // convert to host timezone so everything is linked to host timezone
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
    // validate values before calculating
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
      // return empty as outside of work time
      return [];
    }

    // change to work start time as after host start time
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
            .format('HH:mm:ss') as Time,
          endTime: dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(startHourByHost)
            .minute(startMinuteByHost)
            .add(i + 15, 'minute')
            .format('HH:mm:ss') as Time,
          hostId,
          monthDay: formatToMonthDay(
            monthByHost as MonthType,
            dayOfMonthByHost as DayType
          ),
          date: dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .format('YYYY-MM-DD'),
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
          .format('HH:mm:ss') as Time,
        endTime: dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(startHourByHost)
          .minute(startMinuteByHost)
          .add(i + 15, 'minute')
          .format('HH:mm:ss') as Time,
        hostId,
        monthDay: formatToMonthDay(
          monthByHost as MonthType,
          dayOfMonthByHost as DayType
        ),
        date: dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .format('YYYY-MM-DD'),
      });
    }
    console.log(timeSlots, ' timeSlots inside generateTimeSlots for first day');
    return timeSlots;
  }

  // not first day start from work start time schedule

  const startTimes = userPreference.startTimes;
  const endTimes = userPreference.endTimes;
  // const month = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).month()
  // const dayOfMonth = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).date()
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
        .format('HH:mm:ss') as Time,
      endTime: dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(startHourByHost)
        .minute(startMinuteByHost)
        .add(i + 15, 'minute')
        .format('HH:mm:ss') as Time,
      hostId,
      monthDay: formatToMonthDay(
        monthByHost as MonthType,
        dayOfMonthByHost as DayType
      ),
      date: dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .format('YYYY-MM-DD'),
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

    // convert to host timezone so everything is linked to host timezone
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

    // validate values before calculating
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
      // return empty as outside of work time
      return [];
    }

    // change to work start time as before start time
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
            .format('HH:mm:ss') as Time,
          endTime: dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(startHourByHost)
            .minute(startMinuteByHost)
            .add(i + 30, 'minute')
            .format('HH:mm:ss') as Time,
          hostId,
          monthDay: formatToMonthDay(
            monthByHost as MonthType,
            dayOfMonthByHost as DayType
          ),
          date: dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .format('YYYY-MM-DD'),
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
          .format('HH:mm:ss') as Time,
        endTime: dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(startHourByHost)
          .minute(startMinuteByHost)
          .add(i + 30, 'minute')
          .format('HH:mm:ss') as Time,
        hostId,
        monthDay: formatToMonthDay(
          monthByHost as MonthType,
          dayOfMonthByHost as DayType
        ),
        date: dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .format('YYYY-MM-DD'),
      });
    }
    console.log(timeSlots, ' timeSlots inside generateTimeSlots for first day');
    return timeSlots;
  }
  const startTimes = userPreference.startTimes;
  const endTimes = userPreference.endTimes;
  // const month = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).month()
  // const dayOfMonth = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).date()
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
  // const endHourByHost = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).hour(endHour).tz(hostTimezone).hour()

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
        .format('HH:mm:ss') as Time,
      endTime: dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(startHourByHost)
        .minute(startMinuteByHost)
        .add(i + 30, 'minute')
        .format('HH:mm:ss') as Time,
      hostId,
      monthDay: formatToMonthDay(
        monthByHost as MonthType,
        dayOfMonthByHost as DayType
      ),
      date: dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .format('YYYY-MM-DD'),
    });
  }
  console.log(timeSlots, ' timeSlots inside generateTimeSlots');
  return timeSlots;
};

export const validateEventDates = (
  event: EventPlusType,
  userPreferences: UserPreferenceType
): boolean => {
  // if no timezone remove
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

  // if difference in hours > 23 likely all day event
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
  // if no timezone remove
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

  // if difference in hours > 23 likely all day event
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
      // if found skip
      if (foundPart) {
        continue;
      } else {
        uniquePreBufferPartForEventIds.push(eventParts[i].forEventId);
      }
    }
  }

  // fill up preBufferEventPartsTotal
  for (let i = 0; i < uniquePreBufferPartForEventIds.length; i++) {
    const returnedEventPartTotal = modifyEventPartsForSingularPreBufferTime(
      eventParts,
      uniquePreBufferPartForEventIds[i]
    );
    preBufferEventPartsTotal.push(...returnedEventPartTotal);
  }

  // remove old values
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
      // if found skip
      if (foundPart) {
        continue;
      } else {
        uniquePostBufferPartForEventIds.push(eventParts[i].forEventId);
      }
    }
  }

  // fill up preBufferEventPartsTotal
  for (let i = 0; i < uniquePostBufferPartForEventIds.length; i++) {
    const returnedEventPartTotal = modifyEventPartsForSingularPostBufferTime(
      eventParts,
      uniquePostBufferPartForEventIds[i]
    );
    postBufferEventPartsTotal.push(...returnedEventPartTotal);
  }

  // remove old values
  const eventPartsFiltered = _.differenceBy(
    eventParts,
    postBufferEventPartsTotal,
    'id'
  );
  // add new values
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

  // add values for postBuffer part
  for (let i = 0; i < postBufferAfterEventPartsSorted.length; i++) {
    if (
      postBufferEventPartsTotal?.[postBufferActualEventPartsSorted?.length + i]
    ) {
      postBufferEventPartsTotal[
        postBufferActualEventPartsSorted?.length + i
      ].part = actualEventPreviousLastPart + i + 1;
    }
  }

  // change preEventId's last part and eventId
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
        .format('HH:mm:ss') as Time)) ||
    undefined;

  const adjustedNegativeImpactTime =
    (negativeImpactTime &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(negativeImpactTime.slice(0, 2), 10))
        .minute(parseInt(negativeImpactTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time)) ||
    undefined;

  const adjustedPreferredTime =
    (preferredTime &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(preferredTime.slice(0, 2), 10))
        .minute(parseInt(preferredTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time)) ||
    undefined;

  const adjustedPreferredStartTimeRange =
    (preferredStartTimeRange &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(preferredStartTimeRange.slice(0, 2), 10))
        .minute(parseInt(preferredStartTimeRange.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time)) ||
    undefined;

  const adjustedPreferredEndTimeRange =
    (preferredEndTimeRange &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(preferredEndTimeRange.slice(0, 2), 10))
        .minute(parseInt(preferredEndTimeRange.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time)) ||
    undefined;

  const adjustedPreferredTimeRanges =
    preferredTimeRanges?.map((e) => ({
      dayOfWeek: dayOfWeekIntToString?.[e?.dayOfWeek] ?? null,
      startTime: dayjs()
        .tz(timezone)
        .hour(parseInt(e?.startTime.slice(0, 2), 10))
        .minute(parseInt(e?.startTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time,
      endTime: dayjs()
        .tz(timezone)
        .hour(parseInt(e?.endTime.slice(0, 2), 10))
        .minute(parseInt(e?.endTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time,
      eventId,
      userId,
      hostId,
    })) ?? null;

  const eventPlannerRequestBody: EventPartPlannerRequestBodyType = {
    groupId,
    eventId,
    part,
    lastPart,
    meetingPart,
    meetingLastPart,
    startDate: dayjs(event.startDate.slice(0, 19))
      .tz(event.timezone, true)
      .format('YYYY-MM-DDTHH:mm:ss'),
    endDate: dayjs(event.endDate.slice(0, 19))
      .tz(event.timezone, true)
      .format('YYYY-MM-DDTHH:mm:ss'),
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
    event: {
      id: eventId,
      userId,
      hostId,
      preferredTimeRanges: adjustedPreferredTimeRanges ?? null,
      eventType: event.eventType,
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
        .format('HH:mm:ss') as Time)) ||
    undefined;

  const adjustedNegativeImpactTime =
    (negativeImpactTime &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(negativeImpactTime.slice(0, 2), 10))
        .minute(parseInt(negativeImpactTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time)) ||
    undefined;

  const adjustedPreferredTime =
    (preferredTime &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(preferredTime.slice(0, 2), 10))
        .minute(parseInt(preferredTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time)) ||
    undefined;

  const adjustedPreferredStartTimeRange =
    (preferredStartTimeRange &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(preferredStartTimeRange.slice(0, 2), 10))
        .minute(parseInt(preferredStartTimeRange.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time)) ||
    undefined;

  const adjustedPreferredEndTimeRange =
    (preferredEndTimeRange &&
      (dayjs()
        .tz(timezone)
        .hour(parseInt(preferredEndTimeRange.slice(0, 2), 10))
        .minute(parseInt(preferredEndTimeRange.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time)) ||
    undefined;

  const adjustedPreferredTimeRanges =
    preferredTimeRanges?.map((e) => ({
      dayOfWeek: dayOfWeekIntToString?.[e?.dayOfWeek] ?? null,
      startTime: dayjs()
        .tz(timezone)
        .hour(parseInt(e?.startTime.slice(0, 2), 10))
        .minute(parseInt(e?.startTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time,
      endTime: dayjs()
        .tz(timezone)
        .hour(parseInt(e?.endTime.slice(0, 2), 10))
        .minute(parseInt(e?.endTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time,
      eventId,
      userId,
      hostId,
    })) ?? null;

  const eventPlannerRequestBody: EventPartPlannerRequestBodyType = {
    groupId,
    eventId,
    part,
    lastPart,
    meetingPart,
    meetingLastPart,
    startDate: dayjs(event.startDate.slice(0, 19))
      .tz(event.timezone, true)
      .format('YYYY-MM-DDTHH:mm:ss'),
    endDate: dayjs(event.endDate.slice(0, 19))
      .tz(event.timezone, true)
      .format('YYYY-MM-DDTHH:mm:ss'),
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
    event: {
      id: eventId,
      userId,
      hostId,
      preferredTimeRanges: adjustedPreferredTimeRanges ?? null,
      eventType: event.eventType,
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
  // set preferred DayOfWeek and Time if not set
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
          .format('HH:mm:ss') as Time,
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
        // reconstruct events
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

// recurring events are not tagged with weekly or daily task boolean so need to be done manually
export const tagEventForDailyOrWeeklyTask = (
  eventToSubmit: EventPartPlannerRequestBodyType,
  event: EventPlusType
) => {
  // validate
  if (!event?.id) {
    console.log('no original event inside tagEventForDailysOrWeeklyTask');
    return null;
  }

  if (!eventToSubmit?.eventId) {
    console.log('no eventToSubmit inside tagEventForDailyOrWeeklyTask');
    return null;
  }

  if (eventToSubmit?.recurringEventId) {
    // const originalEvent = await getEventFromPrimaryKey(event.recurringEventId)
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
  // add default values for user request body
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

export const processEventsForOptaPlannerForMainHost = async (
  mainHostId: string,
  allHostEvents: EventPlusType[],
  windowStartDate: string,
  windowEndDate: string,
  hostTimezone: string,
  oldHostEvents: EventPlusType[],
  newHostBufferTimes?: BufferTimeObjectType[]
): Promise<ReturnBodyForHostForOptaplannerPrepType> => {
  try {
    const newBufferTimeArray: EventPlusType[] = [];

    for (const newHostBufferTime of newHostBufferTimes) {
      if (newHostBufferTime?.beforeEvent?.id) {
        console.log(
          newHostBufferTime?.beforeEvent,
          ' newTimeBlocking?.beforeEvent'
        );
        newBufferTimeArray.push(newHostBufferTime.beforeEvent);
      }

      if (newHostBufferTime?.afterEvent?.id) {
        console.log(
          newHostBufferTime?.afterEvent,
          ' newTimeBlocking?.afterEvent'
        );
        newBufferTimeArray.push(newHostBufferTime.afterEvent);
      }
    }

    const modifiedAllHostEvents = _.cloneDeep(allHostEvents);

    console.log(
      modifiedAllHostEvents,
      ' modifiedAllHostEvents inside processEventsForOptaPlannerForMainHost'
    );

    if (newBufferTimeArray?.length > 0) {
      modifiedAllHostEvents.push(...newBufferTimeArray);
    }

    // get user preferences
    const userPreferences = await getUserPreferences(mainHostId);

    // get global primary calendar
    const globalPrimaryCalendar = await getGlobalCalendar(mainHostId);

    // generate timeslots

    const diffDays = dayjs(windowEndDate.slice(0, 19)).diff(
      dayjs(windowStartDate.slice(0, 19)),
      'day'
    );

    const modifiedAllEventsWithBreaks: EventPlusType[] = [];

    const startDatesForEachDay = [];

    for (let i = 0; i <= diffDays; i++) {
      startDatesForEachDay.push(
        dayjs(windowStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .add(i, 'day')
          .format()
      );
    }

    // add breaks to all events
    let parentBreaks: EventPlusType[] = [];

    const breaks = await generateBreakEventsForDate(
      userPreferences,
      mainHostId,
      windowStartDate,
      windowEndDate,
      hostTimezone,
      globalPrimaryCalendar?.id
    );

    breaks.forEach((b) => console.log(b, ' generatedBreaks'));

    if (breaks?.length > 0) {
      // modifiedAllEvents.push(...breaks)
      const allEventsWithDuplicateFreeBreaks = _.differenceBy(
        modifiedAllHostEvents,
        breaks,
        'id'
      );
      modifiedAllEventsWithBreaks.push(...allEventsWithDuplicateFreeBreaks);
      modifiedAllEventsWithBreaks.push(...breaks);
      parentBreaks.push(...breaks);
    } else {
      modifiedAllEventsWithBreaks.push(...modifiedAllHostEvents);
    }

    const workTimes = generateWorkTimesForInternalAttendee(
      mainHostId,
      mainHostId,
      userPreferences,
      hostTimezone,
      hostTimezone
    );
    const timeslots = [];

    for (let i = 0; i < startDatesForEachDay.length; i++) {
      if (i === 0) {
        // const mostRecentEvent = _.minBy(modifiedAllEventsWithBreaks, (e) => dayjs(e?.startDate).unix())
        const timeslotsForDay = await generateTimeSlotsLiteForInternalAttendee(
          startDatesForEachDay?.[i],
          mainHostId,
          userPreferences,
          hostTimezone,
          hostTimezone,
          true
        );
        timeslots.push(...timeslotsForDay);
        continue;
      }
      const timeslotsForDay = await generateTimeSlotsLiteForInternalAttendee(
        startDatesForEachDay?.[i],
        mainHostId,
        userPreferences,
        hostTimezone,
        hostTimezone,
        false
      );
      timeslots.push(...timeslotsForDay);
    }

    // generate event parts
    const filteredAllEvents = _.uniqBy(
      modifiedAllEventsWithBreaks.filter((e) =>
        validateEventDates(e, userPreferences)
      ),
      'id'
    );
    console.log(
      filteredAllEvents,
      ' filteredAllEvents inside processEventsForOptaPlannerForMainHost'
    );
    let eventParts: EventPartPlannerRequestBodyType[] = [];

    const eventPartMinisAccumulated = [];
    for (const event of filteredAllEvents) {
      const eventPartMinis = generateEventPartsLite(event, mainHostId);
      eventPartMinisAccumulated.push(...eventPartMinis);
    }
    console.log(
      eventPartMinisAccumulated,
      ' eventPartMinisAccumulated inside processEventsForOptaPlannerForMainHost'
    );
    const modifiedEventPartMinisPreBuffer =
      modifyEventPartsForMultiplePreBufferTime(eventPartMinisAccumulated);
    console.log(
      modifiedEventPartMinisPreBuffer,
      ' modifiedEventPartMinisPreBuffer inside processEventsForOptaPlannerForMainHost'
    );
    const modifiedEventPartMinisPreAndPostBuffer =
      modifyEventPartsForMultiplePostBufferTime(
        modifiedEventPartMinisPreBuffer
      );
    console.log(
      modifiedEventPartMinisPreAndPostBuffer,
      ' modifiedEventPartMinisPreAndPostBuffer inside processEventsForOptaPlannerForMainHost'
    );
    console.log(
      userPreferences,
      workTimes,
      hostTimezone,
      ' userPreferences, workTimes, hostTimezone inside processEventsForOptaPlannerForMainHost'
    );
    const formattedEventParts: EventPartPlannerRequestBodyType[] =
      modifiedEventPartMinisPreAndPostBuffer.map((e) =>
        formatEventTypeToPlannerEvent(
          e,
          userPreferences,
          workTimes,
          hostTimezone
        )
      );
    console.log(
      formattedEventParts,
      ' formattedEventParts inside processEventsForOptaPlannerForMainHost'
    );
    if (formattedEventParts?.length > 0) {
      eventParts.push(...formattedEventParts);
    }

    console.log(
      eventParts,
      ' eventParts inside processEventsForOptaPlannerForMainHost'
    );

    if (eventParts?.length > 0) {
      eventParts.forEach((e) => console.log(e, ' eventParts after formatting'));
      const newEventPartsWithPreferredTimeSet = eventParts.map((e) =>
        setPreferredTimeForUnModifiableEvent(
          e,
          allHostEvents.find((f) => f.id === e.eventId)?.timezone
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
      const userPlannerRequestBody = generateUserPlannerRequestBody(
        userPreferences,
        userPreferences.userId,
        workTimes,
        mainHostId
      );
      console.log(userPlannerRequestBody, ' userPlannerRequestBody');

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
              .format('YYYY-MM-DDTHH:mm:ss'),
            endDate: dayjs(eventPart?.endDate.slice(0, 19))
              .tz(oldEvent.timezone, true)
              .format('YYYY-MM-DDTHH:mm:ss'),
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
            userId: mainHostId,
            hostId: mainHostId,
            eventParts: modifiedNewEventParts,
            allEvents: filteredAllEvents,
            breaks: parentBreaks,
            oldEvents: oldHostEvents,
            timeslots,
            userPlannerRequestBody,
          }
        : null;
    }
  } catch (e) {
    console.log(
      e,
      ' unable to process events for optaplanner for host attendee'
    );
  }
};

export const processEventsForOptaPlannerForInternalAttendees = async (
  mainHostId: string,
  allEvents: EventPlusType[],
  windowStartDate: string,
  windowEndDate: string,
  hostTimezone: string,
  internalAttendees: MeetingAssistAttendeeType[],
  oldEvents: EventPlusType[],
  oldMeetingEvents?: EventMeetingPlusType[],
  newMeetingEvents?: EventMeetingPlusType[],
  newHostBufferTimes?: BufferTimeObjectType[]
): Promise<ReturnBodyForAttendeeForOptaplannerPrepType> => {
  try {
    const newBufferTimeArray: EventPlusType[] = [];

    for (const newHostBufferTime of newHostBufferTimes) {
      if (newHostBufferTime?.beforeEvent?.id) {
        console.log(
          newHostBufferTime?.beforeEvent,
          ' newTimeBlocking?.beforeEvent'
        );
        newBufferTimeArray.push(newHostBufferTime.beforeEvent);
      }

      if (newHostBufferTime?.afterEvent?.id) {
        console.log(
          newHostBufferTime?.afterEvent,
          ' newTimeBlocking?.afterEvent'
        );
        newBufferTimeArray.push(newHostBufferTime.afterEvent);
      }
    }

    oldMeetingEvents?.forEach((o) => console.log(o, ' oldMeetingEvents'));
    internalAttendees?.forEach((i) =>
      console.log(
        i,
        ' internalAttendees inside processEventsForOptaPlannerForInternalAttendees'
      )
    );
    const filteredOldMeetingEvents = oldMeetingEvents
      ?.map((m) => {
        const foundIndex = allEvents?.findIndex((a) => a?.id === m?.id);

        if (foundIndex > -1) {
          return null;
        }
        return m;
      })
      ?.filter((e) => !!e);

    filteredOldMeetingEvents?.forEach((e) =>
      console.log(e, ' filteredOldMeetingEvents')
    );
    const modifiedAllEvents = _.cloneDeep(allEvents)?.filter((e) => {
      if (filteredOldMeetingEvents?.[0]?.id) {
        const foundIndex = filteredOldMeetingEvents?.findIndex(
          (m) => m?.id === e?.id
        );
        if (foundIndex > -1) {
          return false;
        }
        return true;
      }
      return true;
    });

    // add smart meeting events to all events
    if (filteredOldMeetingEvents?.[0]?.id) {
      modifiedAllEvents.push(
        ...filteredOldMeetingEvents?.map((a) =>
          convertMeetingPlusTypeToEventPlusType(a)
        )
      );
    }

    if (newBufferTimeArray?.length > 0) {
      modifiedAllEvents.push(...newBufferTimeArray);
    }

    if (newMeetingEvents?.length > 0) {
      // add newly generated host event to rest
      modifiedAllEvents.push(
        ...newMeetingEvents?.map((m) =>
          convertMeetingPlusTypeToEventPlusType(m)
        )
      );
    }

    modifiedAllEvents?.forEach((e) => console.log(e, ' modifiedAllEvents'));

    // get user preferences
    const unfilteredUserPreferences: UserPreferenceType[] = [];
    for (const internalAttendee of internalAttendees) {
      const userPreference = await getUserPreferences(internalAttendee?.userId);
      unfilteredUserPreferences.push(userPreference);
    }

    const userPreferences: UserPreferenceType[] = _.uniqWith(
      unfilteredUserPreferences,
      _.isEqual
    );

    // global primary calendars
    const unfilteredGlobalPrimaryCalendars: CalendarType[] = [];

    for (const internalAttendee of internalAttendees) {
      const globalPrimaryCalendar = await getGlobalCalendar(
        internalAttendee?.userId
      );
      unfilteredGlobalPrimaryCalendars.push(globalPrimaryCalendar);
    }

    const globalPrimaryCalendars = _.uniqWith(
      unfilteredGlobalPrimaryCalendars,
      _.isEqual
    );

    globalPrimaryCalendars?.forEach((c) =>
      console.log(c, ' globalPrimaryCalendars')
    );

    const modifiedAllEventsWithBreaks: EventPlusType[] = [];

    // add breaks to all events
    let parentBreaks: EventPlusType[] = [];
    for (const userPreference of userPreferences) {
      const globalPrimaryCalendar = globalPrimaryCalendars?.find(
        (g) => g?.userId === userPreference?.userId
      );
      if (!globalPrimaryCalendar) {
        throw new Error('no global primary calendar found');
      }
      const userId = userPreference?.userId;

      const breaks = await generateBreakEventsForDate(
        userPreference,
        userId,
        windowStartDate,
        windowEndDate,
        hostTimezone,
        globalPrimaryCalendar?.id
      );

      breaks.forEach((b) => console.log(b, ' generatedBreaks'));

      if (breaks?.length > 0) {
        // modifiedAllEvents.push(...breaks)
        const allEventsWithDuplicateFreeBreaks = _.differenceBy(
          modifiedAllEvents,
          breaks,
          'id'
        );
        modifiedAllEventsWithBreaks.push(
          ...allEventsWithDuplicateFreeBreaks?.filter(
            (e) => e?.userId === userId
          )
        );
        modifiedAllEventsWithBreaks.push(...breaks);
        parentBreaks.push(...breaks);
      } else {
        modifiedAllEventsWithBreaks.push(
          ...modifiedAllEvents?.filter((e) => e?.userId === userId)
        );
      }
    }

    modifiedAllEventsWithBreaks?.forEach((m) =>
      console.log(m, ' modifiedAllEventsWithBreaks')
    );

    // generate timeslots

    const diffDays = dayjs(windowEndDate.slice(0, 19)).diff(
      dayjs(windowStartDate.slice(0, 19)),
      'day'
    );
    console.log(
      diffDays,
      windowEndDate,
      windowStartDate,
      ' diffDays, windowEndDate, windowStartDate'
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

    console.log(startDatesForEachDay, ' startDatesForEachDay');

    const unfilteredWorkTimes: WorkTimeType[] = [];
    for (const internalAttendee of internalAttendees) {
      const userPreference = userPreferences.find(
        (u) => u.userId === internalAttendee.userId
      );
      const attendeeTimezone = internalAttendee?.timezone;
      const workTimesForAttendee = generateWorkTimesForInternalAttendee(
        mainHostId,
        internalAttendee.userId,
        userPreference,
        hostTimezone,
        attendeeTimezone
      );
      unfilteredWorkTimes.push(...workTimesForAttendee);
    }

    console.log(unfilteredWorkTimes, 'unfilteredWorkTimes');
    const workTimes: WorkTimeType[] = _.uniqWith(
      unfilteredWorkTimes,
      _.isEqual
    );

    const unfilteredTimeslots = [];
    const timeslots = [];

    for (let i = 0; i < startDatesForEachDay.length; i++) {
      if (i === 0) {
        for (const internalAttendee of internalAttendees) {
          const userPreference = userPreferences.find(
            (u) => u.userId === internalAttendee.userId
          );
          // const mostRecentEvent = _.minBy(modifiedAllEventsWithBreaks, (e) => dayjs(e?.startDate).unix())
          const timeslotsForDay =
            await generateTimeSlotsLiteForInternalAttendee(
              startDatesForEachDay?.[i],
              mainHostId,
              userPreference,
              hostTimezone,
              internalAttendee?.timezone,
              true
            );
          unfilteredTimeslots.push(...timeslotsForDay);
        }
        continue;
      }
      for (const internalAttendee of internalAttendees) {
        const userPreference = userPreferences.find(
          (u) => u.userId === internalAttendee.userId
        );
        const timeslotsForDay = await generateTimeSlotsLiteForInternalAttendee(
          startDatesForEachDay?.[i],
          mainHostId,
          userPreference,
          hostTimezone,
          internalAttendee?.timezone,
          false
        );
        unfilteredTimeslots.push(...timeslotsForDay);
      }
    }

    timeslots.push(..._.uniqWith(unfilteredTimeslots, _.isEqual));

    // generate event parts
    const unfilteredAllEvents: EventPlusType[] = [];
    for (const internalAttendee of internalAttendees) {
      const userPreference = userPreferences.find(
        (u) => u.userId === internalAttendee.userId
      );
      const modifiedAllEventsWithBreaksWithUser =
        modifiedAllEventsWithBreaks.filter(
          (e) => e.userId === internalAttendee.userId
        );
      const events = modifiedAllEventsWithBreaksWithUser.filter((e) =>
        validateEventDates(e, userPreference)
      );
      unfilteredAllEvents.push(...events);
    }
    unfilteredAllEvents?.forEach((e) => console.log(e, ' unfilteredAllEvents'));

    const filteredAllEvents = _.uniqBy(unfilteredAllEvents, 'id');

    filteredAllEvents?.forEach((e) => console.log(e, ' filteredAllEvents'));

    let eventParts: EventPartPlannerRequestBodyType[] = [];

    const eventPartMinisAccumulated = [];
    for (const event of filteredAllEvents) {
      // const preferredTimeRanges = await listPreferredTimeRangesForEvent(event?.id)
      // const eventPlus: EventPlusType = { ...event, preferredTimeRanges }
      const eventPartMinis = generateEventPartsLite(event, mainHostId);
      eventPartMinisAccumulated.push(...eventPartMinis);
    }

    eventPartMinisAccumulated?.forEach((e) =>
      console.log(e, ' eventPartMinisAccumulated')
    );
    const modifiedEventPartMinisPreBuffer =
      modifyEventPartsForMultiplePreBufferTime(eventPartMinisAccumulated);
    const modifiedEventPartMinisPreAndPostBuffer =
      modifyEventPartsForMultiplePostBufferTime(
        modifiedEventPartMinisPreBuffer
      );

    modifiedEventPartMinisPreAndPostBuffer?.forEach((e) =>
      console.log(e, ' modifiedEventPartMinisPreAndPostBuffer')
    );

    const formattedEventParts: EventPartPlannerRequestBodyType[] = [];
    for (const userPreference of userPreferences) {
      const formattedEventPartsForUser: EventPartPlannerRequestBodyType[] =
        modifiedEventPartMinisPreAndPostBuffer
          ?.filter((e) => e?.userId === userPreference?.userId)
          ?.map((e) =>
            formatEventTypeToPlannerEvent(
              e,
              userPreference,
              workTimes,
              hostTimezone
            )
          );

      formattedEventPartsForUser?.forEach((e) =>
        console.log(e, ' formattedEventPartsForUser')
      );

      formattedEventParts.push(...formattedEventPartsForUser);
    }

    formattedEventParts?.forEach((e) => console.log(e, ' formattedEventParts'));

    if (formattedEventParts.length > 0) {
      eventParts.push(..._.uniqWith(formattedEventParts, _.isEqual));
    }

    if (eventParts.length > 0) {
      eventParts.forEach((e) => console.log(e, ' eventParts after formatting'));
      const newEventPartsWithPreferredTimeSet = eventParts.map((e) =>
        setPreferredTimeForUnModifiableEvent(
          e,
          allEvents.find((f) => f.id === e.eventId)?.timezone
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
      const unfilteredUserList: UserPlannerRequestBodyType[] = [];
      for (const userPreference of userPreferences) {
        const userPlannerRequestBody = generateUserPlannerRequestBody(
          userPreference,
          userPreference?.userId,
          workTimes,
          mainHostId
        );
        console.log(userPlannerRequestBody, ' userPlannerRequestBody');
        unfilteredUserList.push(userPlannerRequestBody);
      }

      const userList: UserPlannerRequestBodyType[] = _.uniqWith(
        unfilteredUserList,
        _.isEqual
      );

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
              .format('YYYY-MM-DDTHH:mm:ss'),
            endDate: dayjs(eventPart?.endDate.slice(0, 19))
              .tz(oldEvent.timezone, true)
              .tz(hostTimezone)
              .format('YYYY-MM-DDTHH:mm:ss'),
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

      modifiedNewEventParts?.forEach((e) =>
        console.log(e, ' modifiedNewEventParts')
      );

      return modifiedNewEventParts?.length > 0
        ? {
            userIds: internalAttendees.map((a) => a.userId),
            hostId: mainHostId,
            eventParts: modifiedNewEventParts,
            allEvents: filteredAllEvents,
            breaks: parentBreaks,
            oldEvents,
            timeslots,
            userList,
          }
        : null;
    }
  } catch (e) {
    console.log(
      e,
      ' unable to process events for optaplanner for each attendee'
    );
  }
};

export const convertMeetingAssistEventTypeToEventPlusType = (
  event: MeetingAssistEventType,
  userId: string
): EventPlusType => {
  return {
    ...event,
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
    originalAllDay: false,
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
  // 7 days in a week
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
        .format('HH:mm:ss') as Time,
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
        .format('HH:mm:ss') as Time,
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
    // convert to host timezone so everything is linked to host timezone
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
    // const minStartDate = _.minBy(sameDayEvents, (e) => dayjs(e.startDate.slice(0, 19)).tz(userTimezone, true).tz(hostTimezone).unix())
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

    // change to work start time as work start time is  after host start time
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
            .format('HH:mm:ss') as Time,
          endTime: dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(startHourOfHostDateByHost)
            .minute(startMinuteOfHostDateByHost)
            .add(i + 30, 'minute')
            .format('HH:mm:ss') as Time,
          hostId,
          monthDay: formatToMonthDay(
            monthByHost as MonthType,
            dayOfMonthByHost as DayType
          ),
          date: dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .format('YYYY-MM-DD'),
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
          .format('HH:mm:ss') as Time,
        endTime: dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(startHourOfHostDateByHost)
          .minute(startMinuteOfHostDateByHost)
          .add(i + 30, 'minute')
          .format('HH:mm:ss') as Time,
        hostId,
        monthDay: formatToMonthDay(
          monthByHost as MonthType,
          dayOfMonthByHost as DayType
        ),
        date: dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .format('YYYY-MM-DD'),
      });
    }

    console.log(timeSlots, ' timeSlots inside generateTimeSlots for first day');
    return timeSlots;
  }

  // not first day start from work start time schedule

  const dayOfWeekIntByHost = getISODay(
    dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate()
  );
  // convert to host timezone so everything is linked to host timezone
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
        .format('HH:mm:ss') as Time,
      endTime: dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(workStartHourByHost)
        .minute(workStartMinuteByHost)
        .add(i + 30, 'minute')
        .format('HH:mm:ss') as Time,
      hostId,
      monthDay: formatToMonthDay(
        monthByHost as MonthType,
        dayOfMonthByHost as DayType
      ),
      date: dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .format('YYYY-MM-DD'),
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
  oldExternalMeetingEvents?: EventMeetingPlusType[], // converted from external events
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
      // add newly generated host event to rest
      modifiedAllExternalEvents.push(
        ...newMeetingEvents?.map((m) =>
          convertMeetingPlusTypeToEventPlusType(m)
        )
      );
    }

    // generate timeslots

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
          // const mostRecentEvent = _.minBy(modifiedAllExternalEvents, (e) => dayjs(e?.startDate).unix())
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
        const timeSlots = generateTimeSlotsLiteForInternalAttendee(
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

    // generate event parts
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
              .format('YYYY-MM-DDTHH:mm:ss'),
            endDate: dayjs(eventPart?.endDate.slice(0, 19))
              .tz(oldEvent.timezone, true)
              .tz(hostTimezone)
              .format('YYYY-MM-DDTHH:mm:ss'),
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
    // populate timeslots with events
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

// attendeeMeetingEvents include hostMeeting as well
export const processEventsForOptaPlanner = async (
  mainHostId: string,
  internalAttendees: MeetingAssistAttendeeType[],
  meetingEventPlus: EventMeetingPlusType[], // events with a meetingId
  newMeetingEventPlus: EventMeetingPlusType[],
  allEvents: EventPlusType[],
  windowStartDate: string,
  windowEndDate: string,
  hostTimezone: string,
  oldEvents: EventPlusType[],
  externalAttendees?: MeetingAssistAttendeeType[],
  meetingAssistEvents?: MeetingAssistEventType[],
  newHostReminders?: RemindersForEventType[],
  newHostBufferTimes?: BufferTimeObjectType[]
) => {
  try {
    /**
     * parentKey: hostId/singletonId
     * childKey: hostId/singletoneId/{internal | external | hostOnly}
     * hostIsInternalAttendee: boolean
     * externalAttendees: boolean
     * internalAttendees: boolean
     * hostIsInternalAttendee: false => HostOnlyProcessed: boolean
     * hostIsInternalAttendee: true => internalAttendeesProcessed: boolean
     */

    const newInternalMeetingEventsPlus = newMeetingEventPlus
      ?.map((e) => {
        const foundIndex = externalAttendees?.findIndex(
          (a) => a?.userId === e?.userId
        );

        if (foundIndex > -1) {
          return null;
        }
        return e;
      })
      ?.filter((e) => e !== null);

    const newExternalMeetingEventsPlus = newMeetingEventPlus
      ?.map((e) => {
        const foundIndex = externalAttendees?.findIndex(
          (a) => a?.userId === e?.userId
        );

        if (foundIndex > -1) {
          return e;
        }
        return null;
      })
      ?.filter((e) => e !== null);

    const allHostEvents = allEvents.filter((e) => e.userId === mainHostId);

    const oldHostEvents = oldEvents.filter((e) => e?.userId === mainHostId);

    // either or - either there are internal attendees that have main host included
    // or main host is not part of internal attendees

    const hostIsInternalAttendee = internalAttendees.some(
      (ia) => ia?.userId === mainHostId
    );

    let returnValuesFromInternalAttendees:
      | ReturnBodyForAttendeeForOptaplannerPrepType
      | {} = {};
    let returnValuesFromHost: ReturnBodyForHostForOptaplannerPrepType | {} = {};

    console.log(hostIsInternalAttendee, ' hostIsInternalAttendee');

    if (hostIsInternalAttendee) {
      returnValuesFromInternalAttendees =
        await processEventsForOptaPlannerForInternalAttendees(
          mainHostId,
          allEvents,
          windowStartDate,
          windowEndDate,
          hostTimezone,
          internalAttendees,
          oldEvents,
          meetingEventPlus,
          newInternalMeetingEventsPlus,
          newHostBufferTimes
        );
    } else {
      // host is not part of internal attendees
      returnValuesFromHost = await processEventsForOptaPlannerForMainHost(
        mainHostId,
        allHostEvents,
        windowStartDate,
        windowEndDate,
        hostTimezone,
        oldHostEvents,
        newHostBufferTimes
      );
    }

    console.log(
      returnValuesFromInternalAttendees,
      ' returnValuesFromInternalAttendees'
    );
    const externalMeetingEventPlus = meetingEventPlus
      .map((e) => {
        const foundIndex = externalAttendees.findIndex(
          (a) => a?.userId === e?.userId
        );
        if (foundIndex > -1) {
          return e;
        }
        return null;
      })
      ?.filter((e) => e !== null);

    const returnValuesFromExternalAttendees: ReturnBodyForExternalAttendeeForOptaplannerPrepType =
      externalAttendees?.length > 0
        ? await processEventsForOptaPlannerForExternalAttendees(
            externalAttendees?.map((a) => a.userId),
            mainHostId,
            meetingAssistEvents,
            windowStartDate,
            windowEndDate,
            hostTimezone,
            externalAttendees,
            externalMeetingEventPlus, // events with meetingId
            newExternalMeetingEventsPlus
          )
        : null;

    const eventParts: EventPartPlannerRequestBodyType[] = [];
    const allEventsForPlanner: EventPlusType[] = [];
    const breaks: EventPlusType[] = [];
    const oldEventsForPlanner: EventPlusType[] = [];
    const oldAttendeeEvents: MeetingAssistEventType[] = [];
    const unfilteredTimeslots: TimeSlotType[] = [];
    const unfilteredUserList: UserPlannerRequestBodyType[] = [];

    // start filling up the arrays for optaPlanner
    if (
      (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
        ?.eventParts?.length > 0
    ) {
      eventParts.push(
        ...(returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
          ?.eventParts
      );
    }

    if (
      (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
        ?.allEvents?.length > 0
    ) {
      allEventsForPlanner.push(
        ...(returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
          ?.allEvents
      );
    }

    if (
      (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)?.breaks
        ?.length > 0
    ) {
      breaks.push(
        ...(returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
          ?.breaks
      );
    }

    if (
      (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
        ?.oldEvents?.length > 0
    ) {
      oldEventsForPlanner.push(
        ...(returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
          ?.oldEvents
      );
    }

    if (
      (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
        ?.timeslots?.length > 0
    ) {
      unfilteredTimeslots.push(
        ...(returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
          ?.timeslots
      );
    }

    if (
      (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
        ?.userPlannerRequestBody?.id
    ) {
      unfilteredUserList.push(
        (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
          ?.userPlannerRequestBody
      );
    }

    if (
      (
        returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
      )?.userList?.[0]?.id
    ) {
      unfilteredUserList.push(
        ...(
          returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
        )?.userList
      );
    }

    (
      returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
    )?.eventParts?.forEach((e) =>
      console.log(
        e,
        ' (returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType)?.eventParts'
      )
    );

    if (
      (
        returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
      )?.eventParts?.length > 0
    ) {
      eventParts.push(
        ...(
          returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
        )?.eventParts
      );
    }

    if (
      (
        returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
      )?.allEvents?.length > 0
    ) {
      allEventsForPlanner.push(
        ...(
          returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
        )?.allEvents
      );
    }

    (
      returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
    )?.breaks?.forEach((e) =>
      console.log(
        e,
        ' (returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType)?.breaks'
      )
    );

    if (
      (
        returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
      )?.breaks?.length > 0
    ) {
      breaks.push(
        ...(
          returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
        )?.breaks
      );
    }

    if (
      (
        returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
      )?.oldEvents?.length > 0
    ) {
      oldEventsForPlanner.push(
        ...(
          returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
        )?.oldEvents
      );
    }

    if (
      (
        returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
      )?.timeslots?.length > 0
    ) {
      unfilteredTimeslots.push(
        ...(
          returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
        )?.timeslots
      );
    }

    if (returnValuesFromExternalAttendees?.eventParts?.length > 0) {
      eventParts.push(...returnValuesFromExternalAttendees?.eventParts);
    }

    if (returnValuesFromExternalAttendees?.allEvents?.length > 0) {
      allEventsForPlanner.push(...returnValuesFromExternalAttendees?.allEvents);
    }

    if (returnValuesFromExternalAttendees?.oldAttendeeEvents?.length > 0) {
      oldAttendeeEvents.push(
        ...returnValuesFromExternalAttendees?.oldAttendeeEvents
      );
    }

    if (returnValuesFromExternalAttendees?.timeslots?.length > 0) {
      unfilteredTimeslots.push(...returnValuesFromExternalAttendees?.timeslots);
    }

    if (returnValuesFromExternalAttendees?.userList?.length > 0) {
      unfilteredUserList.push(...returnValuesFromExternalAttendees?.userList);
    }

    console.log(oldEvents, ' oldEvents before saving to s3');

    // create duplicate free data
    const duplicateFreeEventParts = _.uniqWith(eventParts, _.isEqual);
    const duplicateFreeAllEvents = _.uniqWith(allEventsForPlanner, _.isEqual);
    const duplicateFreeBreaks = _.uniqWith(breaks, _.isEqual);
    const duplicateFreeOldEvents = _.uniqWith(oldEvents, _.isEqual);
    const duplicateFreeOldAttendeeEvents = _.uniqWith(
      oldAttendeeEvents,
      _.isEqual
    );
    const duplicateFreeTimeslots: TimeSlotType[] = _.uniqWith(
      unfilteredTimeslots,
      _.isEqual
    );
    const singletonId = uuid();

    console.log(eventParts, ' eventParts before validation');
    console.log(
      duplicateFreeEventParts,
      ' duplicateFreeEventParts before validation'
    );
    console.log(duplicateFreeAllEvents, ' duplicateFreeAllEvents');
    console.log(duplicateFreeOldEvents, ' duplicateFreeOldEvents');
    console.log(duplicateFreeTimeslots, ' duplicateFreeTimeslots');
    // validate eventParts
    if (!duplicateFreeEventParts || duplicateFreeEventParts?.length === 0) {
      throw new Error('Event Parts length is 0 or do not exist');
    }

    if (!duplicateFreeTimeslots || !(duplicateFreeTimeslots?.length > 0)) {
      throw new Error(' duplicateFreeTimeslots is empty');
    }

    if (!unfilteredUserList || !(unfilteredUserList?.length > 0)) {
      throw new Error('unfilteredUserList is empty');
    }

    duplicateFreeTimeslots?.forEach((d) =>
      console.log(d, ' duplicateFreeTimeslots')
    );
    unfilteredUserList?.forEach((u) => console.log(u, ' unfilteredUserList'));
    newHostBufferTimes?.forEach((b) =>
      console.log(b.beforeEvent, b.afterEvent, ' b.beforeEvent b.afterEvent ')
    );

    const params = {
      Body: JSON.stringify({
        singletonId,
        hostId: mainHostId,
        eventParts: duplicateFreeEventParts,
        allEvents: duplicateFreeAllEvents,
        breaks: duplicateFreeBreaks,
        oldEvents: duplicateFreeOldEvents,
        oldAttendeeEvents: duplicateFreeOldAttendeeEvents,
        newHostBufferTimes: newHostBufferTimes,
        newHostReminders: newHostReminders,
        hostTimezone,
      }),
      Bucket: bucketName,
      Key: `${mainHostId}/${singletonId}.json`,
      ContentType: 'application/json',
    };

    const s3Command = new PutObjectCommand(params);

    const s3Response = await s3Client.send(s3Command);

    console.log(s3Response, ' s3Response');

    const diffDays = dayjs(windowEndDate).diff(windowStartDate, 'd');

    if (diffDays < 2) {
      await optaPlanWeekly(
        duplicateFreeTimeslots,
        unfilteredUserList,
        duplicateFreeEventParts,
        singletonId,
        mainHostId,
        `${mainHostId}/${singletonId}.json`,
        optaplannerShortDuration,
        onOptaPlanCalendarAdminCallBackUrl
      );
    } else {
      await optaPlanWeekly(
        duplicateFreeTimeslots,
        unfilteredUserList,
        duplicateFreeEventParts,
        singletonId,
        mainHostId,
        `${mainHostId}/${singletonId}.json`,
        optaplannerDuration,
        onOptaPlanCalendarAdminCallBackUrl
      );
    }

    console.log('optaplanner request sent');
    // update freemium if not active subscription

    // if (!(activeSubscriptions?.length > 0)) {
    //     await updateFreemiumById(freemiumOfUser?.id, freemiumOfUser?.usage - 1 || 0)
    // }
  } catch (e) {
    console.log(e, ' unable to process events for optaplanner');
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
    // validate
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

    const res: ClassificationResponseBodyType = await got
      .post(classificationUrl, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Basic ${Buffer.from(`admin:${authApiToken}`).toString('base64')}`,
        },
        json: {
          sentence,
          labels: possibleLabels.map((a) => a?.name),
        },
      })
      .json();
    console.log(
      res,
      event?.id,
      ' res, event?.id inside findBestMatchCategory2'
    );
    return res;
  } catch (e) {
    console.log(e, ' unable to find categories');
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

  //  if meeting  categories meet threshold add to results
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

  // if event is classified as meeting type or external type then also copy over
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
  // include meeting and conference types if any

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
    // preferredDayOfWeek: !event?.userModifiedTimePreference ? (category?.defaultTimePreference?.preferredDayOfWeek) : event.preferredDayOfWeek,
    // preferredTime: !event?.userModifiedTimePreference ? (category?.defaultTimePreference?.preferredTime) : event.preferredTime,
    // preferredStartTimeRange: !event?.userModifiedTimePreference ? (category?.defaultTimePreference?.preferredStartTimeRange) : event.preferredStartTimeRange,
    // preferredEndTimeRange: !event?.userModifiedTimePreference ? (category?.defaultTimePreference?.preferredEndTimeRange) : event.preferredEndTimeRange,
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

export const createRemindersAndTimeBlockingForBestMatchCategory = async (
  id: string,
  userId: string,
  newEvent: EventPlusType,
  bestMatchCategory: CategoryType,
  newReminders1?: ReminderType[],
  newTimeBlocking1?: BufferTimeObjectType,
  previousEvent?: EventPlusType
) => {
  try {
    // validate
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

    let newBufferTimes = newTimeBlocking1 || {};
    let newReminders = newReminders1 || [];
    // create reminders
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
      // create time blocking
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
) => {
  try {
    for (const categoryEvent of categoryEvents) {
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
  } catch (e) {
    console.log(e, ' unable to upsert category events');
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
) => {
  try {
    // validate
    if (!eventId) {
      console.log(eventId, ' no eventId present inside listRemindersForEvent');
      return;
    }

    if (!userId) {
      console.log(userId, ' no userId present inside listRemindersForEvent');
      return;
    }
    // get reminders
    console.log(' listRemindersForEvent called');
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
    return res?.data?.Reminder;
  } catch (e) {
    console.log(e, ' listRemindersForEvent');
  }
};

export const createRemindersUsingCategoryDefaultsForEvent = (
  event: EventPlusType,
  bestMatchCategory: CategoryType,
  oldReminders: ReminderType[],
  previousEvent: EventPlusType
): ReminderType[] => {
  // validate time blocking
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
      // event: event,
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
  //  validate time blocking
  if (previousEvent?.copyTimeBlocking) {
    return null;
  }

  if (previousEvent?.id && bestMatchCategory?.copyTimeBlocking) {
    return null;
  }

  // user modified time blocking do not override
  if (event?.userModifiedTimeBlocking) {
    return null;
  }

  const eventId = uuid();
  const eventId1 = uuid();
  const preEventId = event?.preEventId || `${eventId}#${event?.calendarId}`;
  const postEventId = event?.postEventId || `${eventId1}#${event?.calendarId}`;

  let valuesToReturn: any = {};
  valuesToReturn.newEvent = event;

  if (bestMatchCategory?.defaultTimeBlocking?.afterEvent) {
    // const formattedZoneAfterEventEndDate = formatInTimeZone(addMinutes(zonedTimeToUtc(event.endDate.slice(0, 19), event.timezone), bestMatchCategory.defaultTimeBlocking.afterEvent).toISOString(), event.timezone, "yyyy-MM-dd'T'HH:mm:ssXXX")
    // const formattedZoneAfterEventStartDate = formatInTimeZone(zonedTimeToUtc(event.endDate.slice(0, 19), event.timezone).toISOString(), event.timezone, "yyyy-MM-dd'T'HH:mm:ssXXX")

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
    // const formattedZoneBeforeEventStartDate = formatInTimeZone(subMinutes(zonedTimeToUtc(event.startDate.slice(0, 19), event.timezone), bestMatchCategory.defaultTimeBlocking.beforeEvent).toISOString(), event.timezone, "yyyy-MM-dd'T'HH:mm:ssXXX")
    // const formattedZoneBeforeEventEndDate = formatInTimeZone(zonedTimeToUtc(event.startDate.slice(0, 19), event.timezone).toISOString(), event.timezone, "yyyy-MM-dd'T'HH:mm:ssXXX")

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
  newTimeBlocking1?: {
    beforeEvent?: EventPlusType;
    afterEvent?: EventPlusType;
  },
  previousEvent?: EventPlusType
) => {
  try {
    if (!(bestMatchCategories?.length > 0)) {
      throw new Error(
        'bestMatchCategories cannot be empty inside updateValuesForMeetingTypeCategories '
      );
    }
    let newEvent = newEvent1;
    let newReminders = newReminders1 || [];
    let newBufferTime = newTimeBlocking1 || {};
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

      // create reminders
      const oldReminders = await listRemindersForEvent(
        newCategoryConstantEvents.newEventMeeting.id,
        userId
      );
      const reminders = createRemindersUsingCategoryDefaultsForEvent(
        newEvent,
        meetingCategory,
        oldReminders,
        previousEvent
      );
      console.log(reminders, ' reminders');
      if (reminders?.length > 0) {
        newReminders.push(...reminders);
        newReminders = _.uniqBy(newReminders, 'minutes');
      }

      // create time blocking
      const bufferTime = createPreAndPostEventsForCategoryDefaults(
        meetingCategory,
        newEvent,
        previousEvent
      );
      console.log(bufferTime, ' timeBlocking');
      if (bufferTime?.beforeEvent) {
        newBufferTime.beforeEvent = bufferTime.beforeEvent;
      }

      if (bufferTime?.afterEvent) {
        newBufferTime.afterEvent = bufferTime.afterEvent;
      }

      if (
        bufferTime?.newEvent?.preEventId ||
        bufferTime?.newEvent?.postEventId
      ) {
        newEvent = bufferTime.newEvent;
      }
    }

    if (newCategoryConstantEvents?.newEventExternal?.id) {
      newEvent = { ...newEvent, ...newCategoryConstantEvents.newEventExternal };
      const externalCategory = bestMatchCategories.find(
        (category) => category.name === externalMeetingLabel
      );

      // create reminders
      const oldReminders = await listRemindersForEvent(
        newCategoryConstantEvents.newEventExternal.id,
        userId
      );
      const reminders = createRemindersUsingCategoryDefaultsForEvent(
        newEvent,
        externalCategory,
        oldReminders,
        previousEvent
      );
      console.log(reminders, ' reminders');
      if (reminders?.length > 0) {
        newReminders.push(...reminders);
        newReminders = _.uniqBy(newReminders, 'minutes');
      }

      // create time blocking
      const timeBlocking = createPreAndPostEventsForCategoryDefaults(
        externalCategory,
        newEvent,
        previousEvent
      );
      console.log(timeBlocking, ' timeBlocking');
      if (timeBlocking?.beforeEvent) {
        newBufferTime.beforeEvent = timeBlocking.beforeEvent;
      }

      if (timeBlocking?.afterEvent) {
        newBufferTime.afterEvent = timeBlocking.afterEvent;
      }

      if (
        timeBlocking?.newEvent?.preEventId ||
        timeBlocking?.newEvent?.postEventId
      ) {
        newEvent = timeBlocking.newEvent;
      }
    }
    return { newEvent, newReminders, newTimeBlocking: newBufferTime };
  } catch (e) {
    console.log(e, ' unable to update values for default categories');
  }
};

export const processUserEventForCategoryDefaults = async (
  event: EventPlusType,
  vector: number[]
) => {
  try {
    const { id, userId } = event;
    console.log(id, ' id inside processUserEventForCategoryDefaults');
    //  create new event datatype in elastic search
    // await putDataInSearch(id, vector, userId)

    // find categories and copy over defaults if any
    const categories: CategoryType[] = await getUserCategories(userId);

    if (!categories?.[0]?.id) {
      throw new Error(
        'categories is not available processUserEventForCategoryDefaults'
      );
    }

    // labelConstants are already part of categories
    console.log(
      categories,
      id,
      ' categories, id processUserEventForCategoryDefaults'
    );
    const body = await findBestMatchCategory2(event, categories);
    console.log(body, id, ' body, id processUserEventForCategoryDefaults');
    const { labels, scores } = body;

    const bestMatchLabel = processBestMatchCategories(body, labels);
    console.log(
      bestMatchLabel,
      id,
      ' bestMatchLabel, id processUserEventForCategoryDefaults'
    );

    if (bestMatchLabel) {
      const bestMatchCategory = categories.find(
        (category) => category.name === bestMatchLabel
      );
      let bestMatchPlusMeetingCategories =
        await processEventForMeetingTypeCategories(
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
          id,
          ' bestMatchAndMeetingCategories, id processUserEventForCategoryDefaults'
        );
      }
      //  copy over category defaults
      const newCategoryDefaultEvent = copyOverCategoryDefaults(
        event,
        bestMatchCategory
      );
      console.log(
        newCategoryDefaultEvent,
        id,
        ' newCategoryDefaultEvent, id processUserEventForCategoryDefaults'
      );

      // create new event
      let newEvent: EventPlusType = newCategoryDefaultEvent ?? event;
      console.log(newEvent, ' newEvent processUserEventForCategoryDefaults');
      let newReminders: ReminderType[] = [];
      let newTimeBlocking: BufferTimeObjectType = {};

      const {
        newEvent: newEvent1,
        newReminders: newReminders1,
        newBufferTimes: newTimeBlocking1,
      } = await createRemindersAndTimeBlockingForBestMatchCategory(
        id,
        userId,
        newEvent,
        bestMatchCategory,
        newReminders,
        newTimeBlocking
      );
      newEvent = newEvent1;
      newReminders = newReminders1;
      newTimeBlocking = newTimeBlocking1;

      if (bestMatchPlusMeetingCategories?.length > 0) {
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
        console.log(
          categoryEvents,
          id,
          ' categoryEvents, id processUserEventForCategoryDefaults'
        );
        await createCategoryEvents(categoryEvents);
        const {
          newEvent: newEvent1,
          newReminders: newReminders1,
          newTimeBlocking: newTimeBlocking1,
        } = await updateValuesForMeetingTypeCategories(
          event,
          newEvent,
          bestMatchPlusMeetingCategories,
          userId,
          newReminders,
          newTimeBlocking
        );
        newEvent = newEvent1;
        newReminders = newReminders1;
        newTimeBlocking = newTimeBlocking1;
      }

      newEvent.vector = vector;

      console.log(newEvent, ' newEvent processUserEventForCategoryDefaults');
      console.log(
        newReminders,
        ' newReminders processUserEventForCategoryDefaults'
      );
      console.log(
        newTimeBlocking,
        ' newTimeBlocking processUserEventForCategoryDefaults'
      );

      return {
        newEvent,
        newReminders,
        newTimeBlocking,
      };
    }
    // no best match category was found
    // just return the event to planner
    // get this week's events
    event.vector = vector;
    return {
      newEvent: event,
    };
  } catch (e) {
    console.log(e, ' e');
  }
};

export const getEventFromPrimaryKey = async (
  eventId: string
): Promise<EventPlusType> => {
  try {
    const operationName = 'getEventFromPrimaryKey';
    const query = `
    query getEventFromPrimaryKey($eventId: String!) {
      Event_by_pk(id: $eventId) {
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
            eventId,
          },
        },
      })
      .json();
    console.log(res, ' res from getEventFromPrimaryKey');
    return res?.data?.Event_by_pk;
  } catch (e) {
    console.log(e, ' getEventFromPrimaryKey');
  }
};

export const deleteDocInSearch3 = async (id: string) => {
  try {
    const client = await getSearchClient();
    const response = await client.delete({
      id,
      index: searchIndex,
    });
    console.log('Deleting document in search:');
    console.log(response.body);
  } catch (e) {
    console.log(e, ' unable to delete doc');
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
        ? previousEvent.preferredTimeRanges
        : category?.copyTimePreference &&
            previousEvent.preferredTimeRanges?.length > 0
          ? previousEvent?.preferredTimeRanges
          : userPreferences?.copyTimePreference &&
              previousEvent.preferredTimeRanges?.length > 0
            ? previousEvent?.preferredTimeRanges
            : category?.defaultTimePreference?.length > 0
              ? category.defaultTimePreference.map((tp: any) => ({
                  ...tp,
                  id: uuid(),
                  eventId: event?.id,
                  createdDate: dayjs().toISOString(),
                  updatedAt: dayjs().toISOString(),
                  userId: event?.userId,
                }))
              : event?.preferredTimeRanges
      : event.preferredTimeRanges,
  };
};
