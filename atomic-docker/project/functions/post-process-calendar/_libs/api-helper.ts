import {
  authApiToken,
  classificationUrl,
  dayOfWeekIntToString,
  eventVectorName,
  externalMeetingLabel,
  googleCalendarResource,
  googleClientIdAndroid,
  googleClientIdAtomicWeb,
  googleClientIdIos,
  googleClientIdWeb,
  googleClientSecretAtomicWeb,
  googleClientSecretWeb,
  googleTokenUrl,
  hasuraAdminSecret,
  hasuraGraphUrl,
  meetingLabel,
  minThresholdScore,
  onOptaPlanCalendarAdminCallBackUrl,
  openSearchEndPoint,
  optaPlannerPassword,
  optaPlannerUrl,
  optaPlannerUsername,
  optaplannerDuration,
  searchIndex,
  text2VectorUrl,
  vectorDimensions,
  zoomBaseTokenUrl,
  zoomBaseUrl,
  zoomClientId,
  zoomClientSecret,
  zoomIVForPass,
  zoomPassKey,
  zoomResourceName,
  zoomSaltForPass,
} from '@post_process_calendar/_libs/constants';
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
  classificationResponseBody as ClassificationResponseBodyType,
  BufferTimeObjectType,
  ReminderType,
  CategoryEventType,
  EventPlannerResponseBodyType,
  ReminderTypeAdjusted,
  CalendarIntegrationType,
  GoogleReminderType,
  OverrideTypes,
  GoogleSendUpdatesType,
  GoogleAttendeeType,
  GoogleConferenceDataType,
  GoogleExtendedPropertiesType,
  GoogleSourceType,
  GoogleTransparencyType,
  GoogleVisibilityType,
  GoogleAttachmentType,
  GoogleEventType1,
  ZoomMeetingObjectType,
  ConferenceType,
  CreateGoogleEventResponseType,
  CreateZoomMeetingRequestBodyType,
  AttendeeType,
} from '@post_process_calendar/_libs/types';
import got from 'got';
import { v4 as uuid } from 'uuid';
import dayjs from 'dayjs';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import _ from 'lodash';
import { PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
import { Client } from '@opensearch-project/opensearch';
import AWS from 'aws-sdk';
import { getISODay, setISODay } from 'date-fns';
import { Configuration, OpenAIApi } from 'openai';
import { Readable } from 'stream';
import { google } from 'googleapis';
import axios from 'axios';
import { URLSearchParams } from 'node:url';
import crypto from 'crypto';
import { bucketName } from '@/gpt/_libs/constants';

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
  apiKey,
});
openai = new OpenAIApi(configuration);
defaultOpenAIAPIKey = apiKey;

export async function streamToString(stream: Readable): Promise<string> {
  return await new Promise((resolve, reject) => {
    const chunks: Uint8Array[] = [];
    stream.on('data', (chunk) => chunks.push(chunk));
    stream.on('error', reject);
    stream.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
  });
}

export const getSearchClient = async () => {
  try {
    return new Client({
      node: process.env.OPENSEARCH_ENDPOINT,
      auth: {
        username: process.env.OPENSEARCH_USERNAME,
        password: process.env.OPENSEARCH_PASSWORD,
      },
    });
  } catch (e) {
    console.log(e, ' unable to get search client');
  }
};
export const searchData3 = async (
  userId: string,
  searchVector: number[]
): Promise<esResponseBody> => {
  try {
    const client = await getSearchClient();
    const response = await client.search({
      index: searchIndex,
      body: {
        size: vectorDimensions,
        query: {
          script_score: {
            query: {
              bool: {
                filter: {
                  term: {
                    userId,
                  },
                },
              },
            },
            script: {
              lang: 'knn',
              source: 'knn_score',
              params: {
                field: eventVectorName,
                query_value: searchVector,
                space_type: 'cosinesimil',
              },
            },
          },
        },
        min_score: 1.2,
      },
    });
    console.log(response, ' search data in search engine');
    return response.body;
  } catch (e) {
    console.log(e, ' unable to search data');
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
      // Handle cases where summary and notes might be empty or just ":"
      console.log(
        'Empty or invalid text for embedding, returning null or empty array.'
      );
      return []; // Or handle as per existing error patterns if any
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
    // Consider re-throwing or returning a specific error/value based on how callers handle it
    throw e;
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
          Event(where: {userId: {_eq: $userId}, endDate: {_gte: $startDate, _lt: $endDate}, deleted: {_eq: false}}) {
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
            endDate: dayjs(endDate).tz(timezone, true).format(),
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
  hostTimezone: string,
  preferredStartTimeRange?: MeetingAssistPreferredTimeRangeType
): EventType => {
  let startDate = dayjs(windowStartDate.slice(0, 19))
    .tz(hostTimezone, true)
    .format();
  if (preferredStartTimeRange?.dayOfWeek > 0) {
    startDate = dayjs(startDate)
      .tz(hostTimezone)
      .isoWeek(preferredStartTimeRange?.dayOfWeek)
      .format();
  }

  if (preferredStartTimeRange?.startTime) {
    const startTime = preferredStartTimeRange?.startTime;
    const hour = parseInt(startTime.slice(0, 2), 10);
    const minute = parseInt(startTime.slice(3), 10);

    startDate = dayjs(startDate)
      .tz(hostTimezone)
      .hour(hour)
      .minute(minute)
      .format();
  }

  const eventId = uuid();

  const newEvent: EventType = {
    id: `${eventId}#${meetingAssist.calendarId}`,
    method: 'create',
    title: meetingAssist.summary,
    startDate,
    endDate: dayjs(startDate)
      .tz(hostTimezone)
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
      .tz(hostTimezone)
      .isoWeek(preferredStartTimeRange?.dayOfWeek)
      .format();
  }

  if (preferredStartTimeRange?.startTime) {
    const startTime = preferredStartTimeRange?.startTime;
    const hour = parseInt(startTime.slice(0, 2), 10);
    const minute = parseInt(startTime.slice(3), 10);

    startDate = dayjs(startDate)
      .tz(hostTimezone)
      .hour(hour)
      .minute(minute)
      .format();
  }

  const eventId = uuid();

  const newEvent: EventType = {
    id: `${eventId}#${meetingAssist?.calendarId}`,
    method: 'create',
    title: meetingAssist.summary,
    startDate,
    endDate: dayjs(startDate)
      .tz(hostTimezone)
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

  const breakLength =
    userPreferences.breakLength <= 15 ? 15 : userPreferences.breakLength;

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
        .add(breakLength, 'minute')
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
      duration: breakLength,
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

  const breakLength =
    userPreferences.breakLength <= 15 ? 15 : userPreferences.breakLength;

  const breakHoursAvailable = (breakLength / 60) * numberOfBreaksPerDay;
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
  let hoursUsed = 0;
  for (const event of allEvents) {
    const duration = dayjs
      .duration(
        dayjs(
          dayjs(event.endDate.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss')
        ).diff(
          dayjs(event.startDate.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss')
        )
      )
      .asHours();
    hoursUsed += duration;
  }

  if (hoursUsed >= workingHours) {
    console.log('hoursUsed >= workingHours');
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

      let hoursAvailable = workingHours - hoursUsed;
      hoursAvailable -= workingHours * userPreferences.maxWorkLoadPercent;
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
      console.log(numberOfBreaksPerDay, ' numberOfBreaksPerDay');
      const breakHoursToGenerate =
        (userPreferences.breakLength / 60) * numberOfBreaksPerDay;
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

    let hoursAvailable = workingHours - hoursUsed;
    hoursAvailable -= workingHours * userPreferences.maxWorkLoadPercent;

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
    const breakHoursToGenerate =
      (userPreferences.breakLength / 60) * numberOfBreaksPerDay;
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
    positiveImpactTime,
    negativeImpactDayOfWeek:
      dayOfWeekIntToString[negativeImpactDayOfWeek] ?? null,
    negativeImpactTime,
    modifiable,
    preferredDayOfWeek: dayOfWeekIntToString[preferredDayOfWeek] ?? null,
    preferredTime,
    isMeeting,
    isExternalMeeting,
    isExternalMeetingModifiable,
    isMeetingModifiable,
    dailyTaskList,
    weeklyTaskList,
    gap: isBreak,
    preferredStartTimeRange,
    preferredEndTimeRange,
    totalWorkingHours,
    recurringEventId,
    hostId,
    meetingId,
    event: {
      id: eventId,
      userId,
      hostId,
      preferredTimeRanges:
        preferredTimeRanges?.map((e) => ({
          dayOfWeek: dayOfWeekIntToString?.[e?.dayOfWeek] ?? null,
          startTime: e?.startTime,
          endTime: e?.endTime,
          eventId,
          userId,
          hostId,
        })) ?? null,
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
    positiveImpactTime,
    negativeImpactDayOfWeek:
      dayOfWeekIntToString[negativeImpactDayOfWeek] ?? null,
    negativeImpactTime,
    modifiable,
    preferredDayOfWeek: dayOfWeekIntToString[preferredDayOfWeek] ?? null,
    preferredTime,
    isMeeting,
    isExternalMeeting,
    isExternalMeetingModifiable,
    isMeetingModifiable,
    dailyTaskList,
    weeklyTaskList,
    gap: isBreak,
    preferredStartTimeRange,
    preferredEndTimeRange,
    totalWorkingHours,
    recurringEventId,
    hostId,
    meetingId,
    event: {
      id: eventId,
      userId,
      hostId,
      preferredTimeRanges:
        preferredTimeRanges?.map((e) => ({
          dayOfWeek: dayOfWeekIntToString?.[e?.dayOfWeek] ?? null,
          startTime: e?.startTime,
          endTime: e?.endTime,
          eventId,
          userId,
          hostId,
        })) ?? null,
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

export const processEventsForOptaPlannerForMainHost = async (
  mainHostId: string,
  allHostEvents: EventPlusType[],
  windowStartDate: string,
  windowEndDate: string,
  hostTimezone: string,
  oldHostEvents: EventPlusType[],
  newHostReminders?: RemindersForEventType[],
  newHostBufferTimes?: BufferTimeObjectType[]
): Promise<ReturnBodyForHostForOptaplannerPrepType> => {
  try {
    const newBufferTimeArray: EventPlusType[] = [];
    newHostBufferTimes?.forEach((newHostBufferTime) => {
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
    });

    const modifiedAllHostEvents = _.cloneDeep(allHostEvents);

    modifiedAllHostEvents.push(...newBufferTimeArray);

    const userPreferences = await getUserPreferences(mainHostId);

    const globalPrimaryCalendar = await getGlobalCalendar(mainHostId);

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
    console.log(timeslots, ' timeslots');

    const filteredAllEvents = _.uniqBy(
      modifiedAllEventsWithBreaks.filter((e) =>
        validateEventDates(e, userPreferences)
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
      modifiedEventPartMinisPreAndPostBuffer.map((e) =>
        formatEventTypeToPlannerEvent(
          e,
          userPreferences,
          workTimes,
          hostTimezone
        )
      );
    if (formattedEventParts.length > 0) {
      eventParts.push(...formattedEventParts);
    }

    if (eventParts.length > 0) {
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
            meetingId: eventPart?.meetingId,
            hostId: mainHostId,
            startDate: dayjs(eventPart?.startDate.slice(0, 19))
              .tz(oldEvent.timezone, true)
              .format(),
            endDate: dayjs(eventPart?.endDate.slice(0, 19))
              .tz(oldEvent.timezone, true)
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
            userId: mainHostId,
            hostId: mainHostId,
            eventParts: modifiedNewEventParts,
            allEvents: filteredAllEvents,
            breaks: parentBreaks,
            oldEvents: oldHostEvents,
            timeslots,
            userPlannerRequestBody,
            newHostReminders,
            newHostBufferTimes,
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
  oldEvents: EventType[],
  oldMeetingEvents: EventMeetingPlusType[],
  newHostReminders?: RemindersForEventType[],
  newHostBufferTimes?: BufferTimeObjectType[]
): Promise<ReturnBodyForAttendeeForOptaplannerPrepType> => {
  try {
    const newBufferTimeArray: EventPlusType[] = [];
    newHostBufferTimes?.forEach((newHostBufferTime) => {
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
    });

    const filteredOldMeetingEvents = oldMeetingEvents
      ?.map((m) => {
        const foundIndex = allEvents?.findIndex((a) => a?.id === m?.id);

        if (foundIndex > -1) {
          return null;
        }
        return m;
      })
      ?.filter((e) => e !== null);

    const modifiedAllEvents = _.cloneDeep(allEvents);

    if (filteredOldMeetingEvents?.[0]?.id) {
      modifiedAllEvents.push(
        ...filteredOldMeetingEvents?.map((a) =>
          convertMeetingPlusTypeToEventPlusType(a)
        )
      );
    }

    modifiedAllEvents.push(...newBufferTimeArray);

    const unfilteredUserPreferences: UserPreferenceType[] = [];
    for (const internalAttendee of internalAttendees) {
      const userPreference = await getUserPreferences(internalAttendee?.userId);
      unfilteredUserPreferences.push(userPreference);
    }

    const userPreferences: UserPreferenceType[] = _.uniqWith(
      unfilteredUserPreferences,
      _.isEqual
    );

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

    const modifiedAllEventsWithBreaks: EventPlusType[] = [];

    let parentBreaks: EventPlusType[] = [];
    for (const userPreference of userPreferences) {
      const globalPrimaryCalendar = globalPrimaryCalendars.find(
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
        const allEventsWithDuplicateFreeBreaks = _.differenceBy(
          modifiedAllEvents,
          breaks,
          'id'
        );
        modifiedAllEventsWithBreaks.push(...allEventsWithDuplicateFreeBreaks);
        modifiedAllEventsWithBreaks.push(...breaks);
        parentBreaks.push(...breaks);
      } else {
        modifiedAllEventsWithBreaks.push(...modifiedAllEvents);
      }
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
    console.log(timeslots, 'isMachinePro timeslots');

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
    const filteredAllEvents = _.uniqBy(unfilteredAllEvents, 'id');
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
    const formattedEventParts: EventPartPlannerRequestBodyType[] = [];
    for (const userPreference of userPreferences) {
      const formattedEventPartsForUser: EventPartPlannerRequestBodyType[] =
        modifiedEventPartMinisPreAndPostBuffer
          .filter((e) => e?.userId === userPreference?.userId)
          .map((e) =>
            formatEventTypeToPlannerEvent(
              e,
              userPreference,
              workTimes,
              hostTimezone
            )
          );
      formattedEventParts.push(...formattedEventPartsForUser);
    }

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
            userIds: internalAttendees.map((a) => a.userId),
            hostId: mainHostId,
            eventParts: modifiedNewEventParts,
            allEvents: filteredAllEvents,
            oldEvents,
            timeslots,
            userList,
            newHostReminders,
            newHostBufferTimes,
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
    originalAllDay: undefined,
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
  oldExternalMeetingEvents?: EventMeetingPlusType[]
): Promise<ReturnBodyForExternalAttendeeForOptaplannerPrepType> => {
  try {
    const modifiedAllExternalEvents = allExternalEvents.map((e) =>
      convertMeetingAssistEventTypeToEventPlusType(
        e,
        externalAttendees.find((a) => a.id === e.attendeeId)?.userId
      )
    );

    const oldConvertedMeetingEvents = oldExternalMeetingEvents
      .map((a) => convertMeetingPlusTypeToEventPlusType(a))
      ?.filter((e) => !!e);
    if (oldConvertedMeetingEvents?.length > 0) {
      modifiedAllExternalEvents.push(...oldConvertedMeetingEvents);
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
      modifiedEventPartMinisPreAndPostBuffer.map((e) =>
        formatEventTypeToPlannerEventForExternalAttendee(
          e,
          workTimes,
          filteredAllEvents,
          hostTimezone
        )
      );
    if (formattedEventParts.length > 0) {
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
          const oldEvent = filteredAllEvents?.find(
            (event) => event.id === eventPart.eventId
          );
          return {
            groupId: eventPart?.groupId,
            eventId: eventPart?.eventId,
            part: eventPart?.part,
            lastPart: eventPart?.lastPart,
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

export const processEventsForOptaPlanner = async (
  mainHostId: string,
  internalAttendees: MeetingAssistAttendeeType[],
  meetingEventPlus: EventMeetingPlusType[],
  allEvents: EventPlusType[],
  windowStartDate: string,
  windowEndDate: string,
  hostTimezone: string,
  oldEvents: EventType[],
  externalAttendees?: MeetingAssistAttendeeType[],
  meetingAssistEvents?: MeetingAssistEventType[],
  newHostReminders?: RemindersForEventType[],
  newHostBufferTimes?: BufferTimeObjectType[]
) => {
  try {
    const allHostEvents = allEvents.filter((e) => e.userId === mainHostId);

    const oldHostEvents = oldEvents.filter((e) => e?.userId === mainHostId);

    const hostIsInternalAttendee = internalAttendees.some(
      (ia) => ia?.userId === mainHostId
    );

    let returnValuesFromInternalAttendees:
      | ReturnBodyForAttendeeForOptaplannerPrepType
      | {} = {};
    let returnValuesFromHost: ReturnBodyForHostForOptaplannerPrepType | {} = {};

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
          newHostReminders,
          newHostBufferTimes
        );
    } else {
      returnValuesFromHost = await processEventsForOptaPlannerForMainHost(
        mainHostId,
        allHostEvents,
        windowStartDate,
        windowEndDate,
        hostTimezone,
        oldHostEvents,
        newHostReminders,
        newHostBufferTimes
      );
    }

    const externalMeetingEventPlus = meetingEventPlus
      .map((e) => {
        const foundIndex = externalAttendees?.findIndex(
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
            externalMeetingEventPlus
          )
        : null;

    const eventParts: EventPartPlannerRequestBodyType[] = [];
    const allEventsForPlanner: EventPlusType[] = [];
    const breaks: EventPlusType[] = [];
    const oldEventsForPlanner: EventPlusType[] = [];
    const oldAttendeeEvents: MeetingAssistEventType[] = [];
    const unfilteredTimeslots: TimeSlotType[] = [];
    const unfilteredUserList: UserPlannerRequestBodyType[] = [];

    if (
      !(
        (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
          ?.eventParts?.length > 0
      )
    ) {
      throw new Error(
        'no event parts produced something went wrong in optaplanner'
      );
    }

    if (
      (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
        ?.eventParts?.length > 0
    ) {
      eventParts.push(
        ...(returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
          ?.eventParts
      );
    }

    if (allHostEvents?.length > 0) {
      allEventsForPlanner.push(...allHostEvents);
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

    const duplicateFreeEventParts = _.uniqWith(eventParts, _.isEqual);
    const duplicateFreeAllEvents = _.uniqWith(allEventsForPlanner, _.isEqual);
    const duplicateFreeBreaks = _.uniqWith(breaks, _.isEqual);
    const duplicateFreeOldEvents = _.uniqWith(oldEvents, _.isEqual);
    const duplicateFreeOldAttendeeEvents = _.uniqWith(
      oldAttendeeEvents,
      _.isEqual
    );
    const duplicateFreeTimeslots = _.uniqWith(unfilteredTimeslots, _.isEqual);
    const singletonId = uuid();

    if (!duplicateFreeEventParts || duplicateFreeEventParts?.length === 0) {
      throw new Error('Event Parts length is 0 or do not exist');
    }

    const params = {
      Body: JSON.stringify({
        singletonId,
        hostId: mainHostId,
        eventParts: duplicateFreeEventParts,
        allEvents: duplicateFreeAllEvents,
        breaks: duplicateFreeBreaks,
        oldEvents: duplicateFreeOldEvents,
        oldAttendeeEvents: duplicateFreeOldAttendeeEvents,
        newHostReminders,
        newHostBufferTimes,
      }),
      Bucket: bucketName,
      Key: `${mainHostId}/${singletonId}.json`,
      ContentType: 'application/json',
    };

    const s3Command = new PutObjectCommand(params);

    const s3Response = await s3Client.send(s3Command);

    console.log(s3Response, ' s3Response');

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
    console.log('optaplanner request sent');
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
        labels: labelNames,
        scores,
        sentence,
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
        labels: labelNames,
        scores,
        sentence,
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
      categories?.find((category) => category.name === meetingLabel)
    );
  }

  if (
    externalMeetingIndex > -1 &&
    scores[externalMeetingIndex] > minThresholdScore
  ) {
    bestMatchCategories.push(
      categories?.find((category) => category.name === externalMeetingLabel)
    );
  }

  if (newEvent.isMeeting && meetingIndex > -1) {
    bestMatchCategories.push(
      categories?.find((category) => category.name === meetingLabel)
    );
  }

  if (newEvent.isExternalMeeting && externalMeetingIndex > -1) {
    bestMatchCategories.push(
      categories?.find((category) => category.name === externalMeetingLabel)
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

    let newTimeBlocking = newTimeBlocking1 || {};
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
      const timeBlocking = createPreAndPostEventsForCategoryDefaults(
        bestMatchCategory,
        newEvent,
        previousEvent
      );
      console.log(timeBlocking, ' timeBlocking');
      if (timeBlocking?.beforeEvent) {
        (newTimeBlocking as BufferTimeObjectType).beforeEvent =
          timeBlocking.beforeEvent;
      }

      if (timeBlocking?.afterEvent) {
        (newTimeBlocking as BufferTimeObjectType).afterEvent =
          timeBlocking.afterEvent;
      }

      if (
        timeBlocking?.newEvent?.preEventId ||
        timeBlocking?.newEvent?.postEventId
      ) {
        newEvent = timeBlocking.newEvent;
      }
    }
    return { newEvent, newReminders, newTimeBlocking };
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
  const meetingCategory = categories?.find(
    (category) => category.name === meetingLabel
  );
  const externalCategory = categories?.find(
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
    if (!eventId) {
      console.log(eventId, ' no eventId present inside listRemindersForEvent');
      return;
    }

    if (!userId) {
      console.log(userId, ' no userId present inside listRemindersForEvent');
      return;
    }
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
  const eventId1 = uuid();
  const preEventId = event?.preEventId || `${eventId}#${event?.calendarId}`;
  const postEventId = event?.postEventId || `${eventId1}#${event?.calendarId}`;

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
      const meetingCategory = bestMatchCategories?.find(
        (category) => category.name === meetingLabel
      );

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
      const externalCategory = bestMatchCategories?.find(
        (category) => category.name === externalMeetingLabel
      );

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

    const categories: CategoryType[] = await getUserCategories(userId);

    if (!categories?.[0]?.id) {
      throw new Error(
        'categories is not available processUserEventForCategoryDefaults'
      );
    }

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
      const bestMatchCategory = categories?.find(
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
      const newCategoryDefaultEvent = copyOverCategoryDefaults(
        event,
        bestMatchCategory
      );
      console.log(
        newCategoryDefaultEvent,
        id,
        ' newCategoryDefaultEvent, id processUserEventForCategoryDefaults'
      );

      let newEvent: EventPlusType = newCategoryDefaultEvent ?? event;
      console.log(newEvent, ' newEvent processUserEventForCategoryDefaults');
      let newReminders: ReminderType[] = [];
      let newTimeBlocking: BufferTimeObjectType = {};

      const {
        newEvent: newEvent1,
        newReminders: newReminders1,
        newTimeBlocking: newTimeBlocking1,
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
    event.vector = vector;
    return {
      newEvent: event,
    };
  } catch (e) {
    console.log(e, ' e');
  }
};

export const listCategoriesForEvent = async (eventId: string) => {
  try {
    console.log(eventId, ' eventId inside listCategoriesForEvent');
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
    )?.filter((category) => category?.id !== null);
    console.log(
      categories,
      ' categories from listCategoriesForEvent after filter'
    );
    return categories;
  } catch (e) {
    console.log(e, ' unable to listCategoriesForEvent');
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
      let newTimeBlocking: BufferTimeObjectType | object = {};
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
        newTimeBlocking: newTimeBlocking1,
      } = await createRemindersAndTimeBlockingForBestMatchCategory(
        id,
        userId,
        newEvent,
        bestMatchCategory,
        newReminders,
        newTimeBlocking as BufferTimeObjectType
      );

      newEvent = newEvent1;
      newReminders = newReminders1;
      newTimeBlocking = newTimeBlocking1 as BufferTimeObjectType;

      if (categories?.length > 1) {
        const {
          newEvent: newEvent1,
          newReminders: newReminders1,
          newTimeBlocking: newTimeBlocking1,
        } = await updateValuesForMeetingTypeCategories(
          event,
          newEvent,
          categories,
          userId,
          newReminders,
          newTimeBlocking as BufferTimeObjectType
        );
        newEvent = newEvent1;
        newReminders = newReminders1;
        newTimeBlocking = newTimeBlocking1;
      }

      newEvent.vector = vector;

      console.log(newEvent, ' newEvent');
      console.log(newReminders, ' newReminders');
      console.log(newTimeBlocking, ' newTimeBlocking');

      return {
        newEvent,
        newReminders,
        newTimeBlocking,
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
              meetingId
              copyExternalMeetingModifiable
              copyMeetingModifiable
              userModifiedExternalMeetingModifiable
              userModifiedMeetingModifiable
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
        ? previousEvent.preferredTimeRanges
        : category.copyTimePreference &&
            previousEvent?.preferredTimeRanges?.length > 0
          ? previousEvent?.preferredTimeRanges
          : userPreferences?.copyTimePreference &&
              previousEvent?.preferredTimeRanges?.length > 0
            ? previousEvent?.preferredTimeRanges
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
    newTimeBlocking1?: BufferTimeObjectType,
    previousEvent?: EventPlusType,
    userPreferences?: UserPreferenceType
  ) => {
    try {
      let newReminders = newReminders1 || [];
      let newTimeBlocking = newTimeBlocking1 || {};
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
        const timeBlocking = createPreAndPostEventsFromPreviousEvent(
          newEvent,
          previousEvent
        );
        console.log(timeBlocking, ' timeBlocking');
        if (timeBlocking?.beforeEvent) {
          (newTimeBlocking as BufferTimeObjectType).beforeEvent =
            timeBlocking.beforeEvent;
        }

        if (timeBlocking?.afterEvent) {
          (newTimeBlocking as BufferTimeObjectType).afterEvent =
            timeBlocking.afterEvent;
        }

        if (
          timeBlocking?.newEvent?.preEventId ||
          timeBlocking?.newEvent?.postEventId
        ) {
          newEvent = timeBlocking.newEvent;
        }
      }
      return { newEvent, newReminders, newTimeBlocking };
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

      return { newEvent, newReminders, newTimeBlocking };
    } catch (e) {
      console.log(e, ' unable to update values for default categories');
    }
  };

export const createRemindersAndTimeBlockingFromPreviousEvent = async (
  userId: string,
  newEvent: EventPlusType,
  newReminders1: ReminderType[],
  newTimeBlocking1: BufferTimeObjectType,
  previousEvent?: EventPlusType
) => {
  try {
    let newReminders = newReminders1 || [];
    let newTimeBlocking = newTimeBlocking1 || {};
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
      const timeBlocking = createPreAndPostEventsFromPreviousEvent(
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
    return { newEvent, newReminders, newTimeBlocking };
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
) => {
  try {
    if (!id) {
      console.log(
        ' no id inside processEventWithFoundPreviousEventAndCopyCategories'
      );
      return null;
    }

    if (!previousEvent) {
      console.log(
        ' no previousEvent inside processEventWithFoundPreviousEventAndCopyCategories'
      );
      return null;
    }

    if (!oldEvent) {
      console.log(
        ' no event inside processEventWithFoundPreviousEventAndCopyCategories'
      );
      return null;
    }

    if (!userPreferences) {
      console.log(
        ' no userPreferences inside processEventWithFoundPreviousEventAndCopyCategories'
      );
      return null;
    }

    if (!bestMatchCategory1) {
      console.log(
        'no bestMatchCategories inside processEventWithFoundPreviousEventAndCopyCategories'
      );
      return null;
    }

    if (!userId) {
      console.log(
        ' no userId inside processEventWithFoundPreviousEventAndCopyCategories'
      );
      return null;
    }

    if (!bestMatchCategories1) {
      console.log(
        ' no bestMatchCategories inside processEventWithFoundPreviousEventAndCopyCategories'
      );
      return null;
    }

    if (!newModifiedEvent1) {
      console.log(
        ' no newModifiedEvent1 inside processEventWithFoundPreviousEventAndCopyCategories'
      );
      return null;
    }

    let bestMatchCategories: CategoryType[] = bestMatchCategories1 || [];
    let bestMatchCategory: CategoryType | object = bestMatchCategory1 || {};
    let newModifiedEvent: EventPlusType | object = newModifiedEvent1 || {};
    let newReminders: ReminderType[] = newReminders1 || [];
    let newTimeBlocking: BufferTimeObjectType = newTimeBlocking1 || {};

    if (!previousEvent?.unlink && !oldEvent?.userModifiedCategories) {
      if (
        (previousEvent?.copyCategories || userPreferences?.copyCategories) &&
        previousCategories?.length > 0
      ) {
        const categoryEvents: CategoryEventType[] = previousCategories.map(
          (c) => {
            const categoryEvent: CategoryEventType = {
              categoryId: c.id,
              eventId: id,
              userId,
              id: uuid(),
              createdDate: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            } as CategoryEventType;
            return categoryEvent;
          }
        );
        console.log(categoryEvents, ' categoryEvents');
        await createCategoryEvents(categoryEvents);
      }

      if (previousCategories?.[0]?.id) {
        const body = await findBestMatchCategory2(oldEvent, previousCategories);
        console.log(body, ' body');
        const { labels } = body;

        const bestMatchLabel = processBestMatchCategoriesNoThreshold(
          body,
          labels
        );
        console.log(bestMatchLabel, ' bestMatchLabel');

        bestMatchCategory = previousCategories.find(
          (category) => category.name === bestMatchLabel
        );

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
        (newModifiedEvent as EventPlusType)?.id
      ) {
        const {
          newEvent: newEvent1,
          newReminders: newReminders1,
          newTimeBlocking: newTimeBlocking1,
        } = await createRemindersAndTimeBlockingFromPreviousEventGivenUserPreferences(
          userId,
          newModifiedEvent as EventPlusType,
          newReminders,
          newTimeBlocking as BufferTimeObjectType,
          previousEvent,
          userPreferences
        );

        if (newEvent1?.id) {
          newModifiedEvent = newEvent1;
        }

        if (newReminders1?.length > 0) {
          newReminders = newReminders1;
        }

        if (newTimeBlocking1?.afterEvent || newTimeBlocking1?.beforeEvent) {
          newTimeBlocking = newTimeBlocking1;
        }
      }

      if (
        ((bestMatchCategory as CategoryType)?.defaultReminders ||
          (bestMatchCategory as CategoryType)?.defaultTimeBlocking) &&
        (newModifiedEvent as EventPlusType)?.id
      ) {
        const {
          newEvent: newEvent3,
          newReminders: newReminders3,
          newTimeBlocking: newTimeBlocking3,
        } = await updateValuesForEventWithPreviousEventPlusMeetingAndExternalMeeting(
          oldEvent,
          newModifiedEvent as EventPlusType,
          bestMatchCategories,
          newReminders,
          newTimeBlocking,
          userId,
          userPreferences,
          previousEvent
        );

        if (newEvent3) {
          newModifiedEvent = newEvent3;
        }

        if (newReminders3) {
          newReminders = newReminders3;
        }

        if (newTimeBlocking3) {
          newTimeBlocking = newTimeBlocking3;
        }
      }

      if (
        ((bestMatchCategory as CategoryType)?.copyReminders ||
          (bestMatchCategory as CategoryType)?.copyTimeBlocking) &&
        (newModifiedEvent as EventPlusType)?.id
      ) {
        const {
          newEvent: newEvent2,
          newReminders: newReminders2,
          newTimeBlocking: newTimeBlocking2,
        } = await createRemindersAndTimeBlockingForBestMatchCategory(
          id,
          userId,
          newModifiedEvent as EventPlusType,
          bestMatchCategory as CategoryType,
          newReminders,
          newTimeBlocking
        );
        if (newEvent2?.id) {
          newModifiedEvent = newEvent2;
        }

        if (newReminders2?.[0]?.id) {
          newReminders = newReminders2;
        }

        if (
          (newTimeBlocking2 as BufferTimeObjectType)?.beforeEvent?.id ||
          (newTimeBlocking2 as BufferTimeObjectType)?.afterEvent?.id
        ) {
          newTimeBlocking = newTimeBlocking2;
        }
      }

      if (
        (previousMeetingCategoriesWithMeetingLabel?.[0]?.copyReminders ||
          previousMeetingCategoriesWithMeetingLabel?.[0]?.copyTimeBlocking) &&
        (newModifiedEvent as EventPlusType)?.id
      ) {
        const {
          newEvent: newEvent2,
          newReminders: newReminders2,
          newTimeBlocking: newTimeBlocking2,
        } = await createRemindersAndTimeBlockingForBestMatchCategory(
          id,
          userId,
          newModifiedEvent as EventPlusType,
          previousMeetingCategoriesWithMeetingLabel?.[0],
          newReminders,
          newTimeBlocking
        );
        if (newEvent2?.id) {
          newModifiedEvent = newEvent2;
        }

        if (newReminders2?.[0]?.id) {
          newReminders = newReminders2;
        }

        if (
          newTimeBlocking2?.afterEvent?.id ||
          newTimeBlocking2?.beforeEvent?.id
        ) {
          newTimeBlocking = newTimeBlocking2;
        }
      }

      if (
        (previousMeetingCategoriesWithExternalMeetingLabel?.[0]
          ?.copyReminders ||
          previousMeetingCategoriesWithExternalMeetingLabel?.[0]
            ?.copyTimeBlocking) &&
        (newModifiedEvent as EventPlusType)?.id
      ) {
        const {
          newEvent: newEvent2,
          newReminders: newReminders2,
          newTimeBlocking: newTimeBlocking2,
        } = await createRemindersAndTimeBlockingForBestMatchCategory(
          id,
          userId,
          newModifiedEvent as EventPlusType,
          previousMeetingCategoriesWithExternalMeetingLabel?.[0],
          newReminders,
          newTimeBlocking
        );
        if (newEvent2) {
          newModifiedEvent = newEvent2;
        }

        if (newReminders2) {
          newReminders = newReminders2;
        }

        if (newTimeBlocking2) {
          newTimeBlocking = newTimeBlocking2;
        }
      }

      if (
        (previousEvent?.copyReminders || previousEvent?.copyTimeBlocking) &&
        (newModifiedEvent as EventPlusType)?.id
      ) {
        const {
          newEvent: newEvent1,
          newReminders: newReminders1,
          newTimeBlocking: newTimeBlocking1,
        } = await createRemindersAndTimeBlockingFromPreviousEvent(
          userId,
          newModifiedEvent as EventPlusType,
          newReminders,
          newTimeBlocking
        );

        if (newEvent1?.id) {
          newModifiedEvent = newEvent1;
        }

        if (newReminders1?.[0]?.id) {
          newReminders = newReminders1;
        }

        if (
          (newTimeBlocking1 as BufferTimeObjectType)?.afterEvent?.id ||
          (newTimeBlocking1 as BufferTimeObjectType)?.beforeEvent?.id
        ) {
          newTimeBlocking = newTimeBlocking1;
        }
      }

      bestMatchCategories = getUniqueLabels(bestMatchCategories);
      console.log(
        bestMatchCategories,
        ' bestMatchCategories from previousCategories'
      );
    }

    console.log(newModifiedEvent, ' newModifiedEvent');
    console.log(newReminders, ' newReminders');
    console.log(newTimeBlocking, ' newTimeBlocking');

    return {
      newModifiedEvent,
      newReminders,
      newTimeBlocking,
    };
  } catch (e) {
    console.log(e, ' processEventWithFoundPreviousEventAndCopyCategories');
  }
};

export const processEventWithFoundPreviousEventWithoutCategories = async (
  previousEvent: EventPlusType,
  event: EventPlusType,
  userPreferences: UserPreferenceType,
  userId: string,
  newReminders: ReminderType[] = [],
  newTimeBlocking: BufferTimeObjectType = {}
) => {
  try {
    console.log('processEventWithFoundPreviousEventWithoutCategories');
    if (!previousEvent) {
      console.log(
        ' no previousEvent inside processEventWithFoundPreviousEventAndCopyCategories'
      );
      return null;
    }

    if (!userPreferences) {
      console.log(
        ' no userPreferences inside processEventWithFoundPreviousEventAndCopyCategories'
      );
      return null;
    }

    if (!userId) {
      console.log(
        ' no userId inside processEventWithFoundPreviousEventAndCopyCategories'
      );
      return null;
    }

    if (!event) {
      console.log(
        ' no newModifiedEvent inside processEventWithFoundPreviousEventAndCopyCategories'
      );
      return null;
    }

    let newModifiedEvent = event;

    if (!previousEvent?.unlink) {
      newModifiedEvent = copyOverPreviousEventDefaults(
        event,
        previousEvent,
        undefined,
        userPreferences
      );
      console.log(
        newModifiedEvent,
        ' newModifiedEvent inside processEventWithFoundPreviousEventWithoutCategories after copyOverPreviousEventDefaults'
      );
      if (
        (userPreferences?.copyReminders || userPreferences?.copyTimeBlocking) &&
        (event as EventPlusType)?.id
      ) {
        const {
          newEvent: newEvent1,
          newReminders: newReminders1,
          newTimeBlocking: newTimeBlocking1,
        } = await createRemindersAndTimeBlockingFromPreviousEventGivenUserPreferences(
          userId,
          newModifiedEvent as EventPlusType,
          newReminders,
          newTimeBlocking as BufferTimeObjectType,
          previousEvent,
          userPreferences
        );

        if (newEvent1?.id) {
          newModifiedEvent = newEvent1;
        }

        if (newReminders1?.length > 0) {
          newReminders = newReminders1;
        }

        if (newTimeBlocking1?.afterEvent || newTimeBlocking1?.beforeEvent) {
          newTimeBlocking = newTimeBlocking1;
        }
      }

      if (
        (previousEvent?.copyReminders || previousEvent?.copyTimeBlocking) &&
        (event as EventPlusType)?.id
      ) {
        const {
          newEvent: newEvent1,
          newReminders: newReminders1,
          newTimeBlocking: newTimeBlocking1,
        } = await createRemindersAndTimeBlockingFromPreviousEvent(
          userId,
          newModifiedEvent as EventPlusType,
          newReminders,
          newTimeBlocking
        );

        if (newEvent1?.id) {
          newModifiedEvent = newEvent1;
        }

        if (newReminders1?.[0]?.id) {
          newReminders = newReminders1;
        }

        if (
          (newTimeBlocking1 as BufferTimeObjectType)?.afterEvent?.id ||
          (newTimeBlocking1 as BufferTimeObjectType)?.beforeEvent?.id
        ) {
          newTimeBlocking = newTimeBlocking1;
        }
      }
    }

    console.log(newModifiedEvent, ' newModifiedEvent');
    console.log(newReminders, ' newReminders');
    console.log(newTimeBlocking, ' newTimeBlocking');

    return {
      newModifiedEvent,
      newReminders,
      newTimeBlocking,
    };
  } catch (e) {
    console.log(e, ' processEventWithFoundPreviousEventWithoutCategories');
  }
};

export const processUserEventWithFoundPreviousEvent = async (
  event: EventPlusType,
  previousEventId: string
) => {
  try {
    const { id, userId } = event;
    console.log(
      id,
      userId,
      previousEventId,
      ' id, userId, previousEventId, inside processUserEventWithFoundPreviousEvent'
    );
    if (!id || !userId) {
      throw new Error('id or userId is missing');
    }
    const previousEvent = await getEventFromPrimaryKey(previousEventId);
    const preferredTimeRanges =
      await listPreferredTimeRangesForEvent(previousEventId);
    previousEvent.preferredTimeRanges = preferredTimeRanges;
    console.log(
      previousEvent,
      ' previousEvent inside processUserEventWithFoundPreviousEvent'
    );
    const categories: CategoryType[] = await getUserCategories(userId);
    console.log(id, categories, ' id, categories');

    const body: ClassificationResponseBodyType = await findBestMatchCategory2(
      event,
      categories
    );
    console.log(id, body, ' id, body');
    const { labels, scores } = body;

    const bestMatchLabel = processBestMatchCategories(body, labels);
    console.log(id, bestMatchLabel, ' id, bestMatchLabel');
    let bestMatchCategory: CategoryType | object = {};
    if (bestMatchLabel) {
      bestMatchCategory = categories.find(
        (category) => category.name === bestMatchLabel
      );
    }

    let bestMatchCategoriesPlusMeetingType = [];
    if ((bestMatchCategory as CategoryType)?.id) {
      bestMatchCategoriesPlusMeetingType =
        await processEventForMeetingTypeCategories(
          event,
          bestMatchCategory as CategoryType,
          labels,
          scores,
          categories
        );
      console.log(
        id,
        bestMatchCategoriesPlusMeetingType,
        ' id, bestMatchCategoriesPlusMeetingType'
      );
    }

    const userPreferences = await getUserPreferences(userId);
    console.log(id, userPreferences, ' id, userPreferences');
    if (!userPreferences) {
      throw new Error('userPreferences is missing');
    }

    let newModifiedEvent = event;
    let newReminders: ReminderType[] = [];
    let newTimeBlocking: BufferTimeObjectType = {};

    console.log(
      id,
      previousEvent,
      ' id, previousEvent before if clause inside processUserEventWithFoundPreviousEvent'
    );

    if (
      (previousEvent?.copyCategories || userPreferences?.copyCategories) &&
      !previousEvent?.unlink &&
      !event?.userModifiedCategories
    ) {
      const previousCategories = await listCategoriesForEvent(previousEvent.id);
      console.log(id, previousCategories, ' id, previousCategories');

      if (userPreferences?.id && newModifiedEvent?.id) {
        const previousMeetingCategoriesWithMeetingLabel =
          previousCategories.filter(
            (category) => category.name === meetingLabel
          );
        const previousMeetingCategoriesWithExternalMeetingLabel =
          previousCategories.filter(
            (category) => category.name === externalMeetingLabel
          );
        const {
          newModifiedEvent: newModifiedEvent1,
          newReminders: newReminders1,
          newTimeBlocking: newTimeBlocking1,
        } = await processEventWithFoundPreviousEventAndCopyCategories(
          id,
          previousEvent,
          event,
          userPreferences,
          bestMatchCategory as CategoryType,
          userId,
          bestMatchCategoriesPlusMeetingType,
          newModifiedEvent,
          newReminders,
          newTimeBlocking,
          previousCategories,
          previousMeetingCategoriesWithMeetingLabel,
          previousMeetingCategoriesWithExternalMeetingLabel
        );
        console.log(
          newModifiedEvent,
          newModifiedEvent1,
          ' newModifiedEvent, newModifiedEvent1 inside processUserEventWithFoundPreviousEvent after processEventWithFoundPreviousEventAndCopyCategories'
        );
        console.log(
          newTimeBlocking,
          newTimeBlocking1,
          ' newTimeBlocking, newTimeBlocking1, inside processUserEventWithFoundPreviousEvent after processEventWithFoundPreviousEventAndCopyCategories'
        );
        newModifiedEvent = newModifiedEvent1 as EventPlusType;
        newReminders = newReminders1;
        newTimeBlocking = newTimeBlocking1 as BufferTimeObjectType;
      } else {
        const {
          newModifiedEvent: newModifiedEvent1,
          newReminders: newReminders1,
          newTimeBlocking: newTimeBlocking1,
        } = await processEventWithFoundPreviousEventWithoutCategories(
          previousEvent,
          newModifiedEvent,
          userPreferences,
          userId,
          newReminders,
          newTimeBlocking
        );
        console.log(
          newModifiedEvent,
          newModifiedEvent1,
          ' newModifiedEvent, newModifiedEvent1 inside processUserEventWithFoundPreviousEvent after else  processEventWithFoundPreviousEventAndCopyCategories'
        );
        console.log(
          newTimeBlocking,
          newTimeBlocking1,
          ' newTimeBlocking, newTimeBlocking1, inside processUserEventWithFoundPreviousEvent after else processEventWithFoundPreviousEventAndCopyCategories'
        );
        newModifiedEvent = newModifiedEvent1 as EventPlusType;
        newReminders = newReminders1;
        newTimeBlocking = newTimeBlocking1 as BufferTimeObjectType;
      }
    }

    if (
      userPreferences?.id &&
      !previousEvent?.copyCategories &&
      !userPreferences?.copyCategories &&
      !event?.userModifiedCategories &&
      event?.id &&
      previousEvent?.id
    ) {
      if (
        (bestMatchCategory as CategoryType)?.id &&
        bestMatchCategoriesPlusMeetingType?.length > 0
      ) {
        newModifiedEvent = copyOverPreviousEventDefaults(
          event,
          previousEvent,
          bestMatchCategory as CategoryType,
          userPreferences
        );
        console.log(
          newModifiedEvent,
          ' newModifiedEvent from BestMatchCategory'
        );
        if (newModifiedEvent?.id) {
          const {
            newEvent: newEvent1,
            newReminders: newReminders1,
            newTimeBlocking: newTimeBlocking1,
          } = await createRemindersAndTimeBlockingForBestMatchCategory(
            id,
            userId,
            newModifiedEvent,
            bestMatchCategory as CategoryType,
            newReminders,
            newTimeBlocking
          );
          console.log(
            newModifiedEvent,
            newEvent1,
            ' newModifiedEvent, newEvent1 inside processUserEventWithFoundPreviousEvent after createRemindersAndTimeBlockingForBestMatchCategory'
          );
          console.log(
            newTimeBlocking,
            newTimeBlocking1,
            ' newTimeBlocking, newTimeBlocking1, inside processUserEventWithFoundPreviousEvent after createRemindersAndTimeBlockingForBestMatchCategory'
          );
          newModifiedEvent = newEvent1;
          newReminders = newReminders1;
          newTimeBlocking = newTimeBlocking1;

          console.log(
            newModifiedEvent,
            ' newModifiedEvent inside BestMatchCategory'
          );
          console.log(newReminders, ' newReminders inside ');
          console.log(newTimeBlocking, ' newTimeBlocking inside ');

          const {
            newEvent: newEvent2,
            newReminders: newReminders2,
            newTimeBlocking: newTimeBlocking2,
          } = await updateValuesForEventWithPreviousEventPlusMeetingAndExternalMeeting(
            event,
            newModifiedEvent,
            bestMatchCategoriesPlusMeetingType,
            newReminders,
            newTimeBlocking,
            userId,
            userPreferences,
            previousEvent
          );
          console.log(
            newModifiedEvent,
            newEvent2,
            ' newModifiedEvent, newEvent2 inside processUserEventWithFoundPreviousEvent after updateValuesForEventWithPreviousEventPlusMeetingAndExternalMeeting'
          );
          console.log(
            newTimeBlocking,
            newTimeBlocking2,
            ' newTimeBlocking, newTimeBlocking2, inside processUserEventWithFoundPreviousEvent after updateValuesForEventWithPreviousEventPlusMeetingAndExternalMeeting'
          );
          newModifiedEvent = newEvent2;
          newReminders = newReminders2;
          newTimeBlocking = newTimeBlocking2;

          console.log(
            newModifiedEvent,
            ' newModifiedEvent inside BestMatchCategory after updateValuesForEventWithPreviousEventWithMeetingAndExternalMeeting'
          );
          console.log(
            newReminders,
            ' newReminders inside BestMatchCategory after updateValuesForEventWithPreviousEventWithMeetingAndExternalMeeting'
          );
          console.log(
            newTimeBlocking,
            ' newTimeBlocking inside BestMatchCategory after updateValuesForEventWithPreviousEventWithMeetingAndExternalMeeting'
          );
        }
      } else {
        const {
          newModifiedEvent: newModifiedEvent1,
          newReminders: newReminders1,
          newTimeBlocking: newTimeBlocking1,
        } = await processEventWithFoundPreviousEventWithoutCategories(
          previousEvent,
          newModifiedEvent,
          userPreferences,
          userId,
          newReminders,
          newTimeBlocking
        );
        console.log(
          newModifiedEvent,
          newModifiedEvent1,
          ' newModifiedEvent, newModifiedEvent1 inside processUserEventWithFoundPreviousEvent after processEventWithFoundPreviousEventWithoutCategories'
        );
        console.log(
          newTimeBlocking,
          newTimeBlocking1,
          ' newTimeBlocking, newTimeBlocking1, inside processUserEventWithFoundPreviousEvent after processEventWithFoundPreviousEventWithoutCategories'
        );
        newModifiedEvent = newModifiedEvent1 as EventPlusType;
        newReminders = newReminders1;
        newTimeBlocking = newTimeBlocking1 as BufferTimeObjectType;
      }
    }

    const newEvent: EventPlusType = newModifiedEvent ?? event;
    console.log(
      newEvent,
      event,
      ' newEvent, event last before returned inside processUserEventWithFoundPreviousEvent'
    );

    return {
      newEvent,
      newReminders,
      newTimeBlocking,
    };
  } catch (e) {
    console.log(e, ' processEventWithFoundPreviousEvent');
  }
};

export const processUserEventWithFoundPreviousEventWithUserModifiedCategories =
  async (event: EventPlusType, previousEventId: string) => {
    try {
      if (!event?.id) {
        throw new Error('event is missing');
      }
      if (!previousEventId) {
        throw new Error('previousEventId is missing');
      }

      const categories: CategoryType[] = await listCategoriesForEvent(
        event?.id
      );
      if (!categories?.[0]?.id) {
        throw new Error('categories is missing');
      }
      console.log(
        event?.id,
        'id inside  processUserEventWithFoundPreviousEventWithUserModifiedCategories'
      );
      const previousEvent = await getEventFromPrimaryKey(previousEventId);
      const preferredTimeRanges =
        await listPreferredTimeRangesForEvent(previousEventId);
      previousEvent.preferredTimeRanges = preferredTimeRanges;
      if (!previousEvent?.id) {
        throw new Error('previousEvent is missing');
      }
      console.log(categories, ' categories');
      const body = await findBestMatchCategory2(event, categories);
      console.log(body, ' body');
      if (body?.labels?.[0]) {
        const { labels } = body;

        const bestMatchLabel = processBestMatchCategoriesNoThreshold(
          body,
          labels
        );
        console.log(bestMatchLabel, ' bestMatchLabel');
        if (bestMatchLabel) {
          let bestMatchCategory = categories.find(
            (category) => category.name === bestMatchLabel
          );
          if (!bestMatchCategory) {
            throw new Error('bestMatchCategory is missing');
          }
          const userPreferences = await getUserPreferences(event?.userId);
          console.log(userPreferences, ' userPreferences');
          if (!userPreferences) {
            throw new Error('userPreferences is missing');
          }
          let newModifiedEvent = copyOverPreviousEventDefaults(
            event,
            previousEvent,
            bestMatchCategory,
            userPreferences
          );
          console.log(
            newModifiedEvent,
            ' newModifiedEvent from BestMatchCategory'
          );
          let newReminders: ReminderType[] = [];
          let newTimeBlocking: BufferTimeObjectType = {};

          if (categories?.length > 0 && newModifiedEvent?.id) {
            const {
              newEvent: newEvent1,
              newReminders: newReminders1,
              newTimeBlocking: newTimeBlocking1,
            } = await updateValuesForEventWithPreviousEventPlusMeetingAndExternalMeeting(
              event,
              newModifiedEvent,
              categories,
              newReminders,
              newTimeBlocking,
              event?.userId,
              userPreferences,
              previousEvent
            );
            newModifiedEvent = newEvent1;
            newReminders = newReminders1 || [];
            newTimeBlocking = newTimeBlocking1 || {};

            console.log(
              newModifiedEvent,
              ' newModifiedEvent inside else statement of copyCategories'
            );
            console.log(
              newReminders,
              ' newReminders inside else statement of copyCategories'
            );
            console.log(
              newTimeBlocking,
              ' newTimeBlocking inside else statement of copyCategories'
            );
          }

          const newEvent: EventPlusType = newModifiedEvent ?? event;
          console.log(newEvent, ' newEvent');

          return {
            newEvent,
            newReminders,
            newTimeBlocking,
          };
        }
      }
    } catch (e) {
      console.log(
        e,
        ' processEventWithFoundPreviousEventWithUserModifiedCategories'
      );
    }
  };

export const deleteOptaPlan = async (userId: string) => {
  try {
    console.log(' deleteOptaPlanner called');
    await got
      .delete(`${optaPlannerUrl}/timeTable/admin/delete/${userId}`, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Basic ${Buffer.from(`${optaPlannerUsername}:${optaPlannerPassword}`).toString('base64')}`,
        },
      })
      .json();

    console.log(' successfully deleted OptaPlanner');
  } catch (e) {
    console.log(e, ' deleteOptaPlanner');
  }
};

export const validateEventsFromOptaplanner = (
  unsortedEvents: EventPlannerResponseBodyType[]
) => {
  const sortedEvents = unsortedEvents.sort((a, b) => {
    if (a.part < b.part) {
      return -1;
    }
    if (a.part > b.part) {
      return 1;
    }
    return 0;
  });
  const firstPartStartTime = sortedEvents?.[0]?.timeslot?.startTime;
  const firstPartEndTime = sortedEvents?.[0]?.timeslot?.endTime;
  const lastPartEndTime =
    sortedEvents?.[sortedEvents?.length - 1]?.timeslot?.endTime;

  const startHour = parseInt(firstPartStartTime.split(':')[0], 10);
  const startMinute = parseInt(firstPartStartTime.split(':')[1], 10);
  const endHour = parseInt(lastPartEndTime.split(':')[0], 10);
  const endMinute = parseInt(lastPartEndTime.split(':')[1], 10);

  const firstPartEndHour = parseInt(firstPartEndTime.split(':')[0], 10);
  const firstPartEndMinute = parseInt(firstPartEndTime.split(':')[1], 10);
  const durationMinutes = dayjs
    .duration(
      dayjs()
        .hour(startHour)
        .minute(startMinute)
        .diff(dayjs().hour(firstPartEndHour).minute(firstPartEndMinute))
    )
    .asMinutes();

  const plannerDurationMinutes = dayjs
    .duration(
      dayjs()
        .hour(startHour)
        .minute(startMinute)
        .diff(dayjs().hour(endHour).minute(endMinute))
    )
    .asMinutes();

  const expectedDurationMinutes = sortedEvents?.[0]?.lastPart * durationMinutes;

  const diffMinutes = Math.abs(
    plannerDurationMinutes - expectedDurationMinutes
  );

  if (Math.round(diffMinutes) > 0) {
    console.log(plannerDurationMinutes, ' plannerDurationMinutes');
    console.log(expectedDurationMinutes, ' expectedDurationMinutes');
    console.log(diffMinutes, ' diffMinutes');
    console.log(
      sortedEvents?.[0]?.eventId,
      startHour,
      startMinute,
      endHour,
      endMinute,
      sortedEvents?.[0]?.startDate,
      sortedEvents?.[0]?.endDate,
      firstPartStartTime,
      lastPartEndTime,
      sortedEvents?.[0]?.timeslot,
      sortedEvents?.[sortedEvents?.length - 1]?.timeslot,
      ` sortedEvents?.[0]?.eventId, startHour, startMinute, endHour, endMinute, sortedEvents?.[0]?.startDate, sortedEvents?.[0]?.endDate, firstPartStartTime, lastPartEndTime, sortedEvents?.[0]?.timeslot, sortedEvents?.[sortedEvents?.length - 1]?.timeslot`
    );
    for (const sortedEvent of sortedEvents) {
      console.log(
        sortedEvent?.eventId,
        sortedEvent.part,
        sortedEvent?.timeslot,
        sortedEvent.lastPart,
        ' sortedEvent?.eventId, sortedEvent.part, sortedEvent?.timeslot, sortedEvent.lastPart'
      );
    }

    throw new Error(
      'plannerDurationMinutes are not equal to expectedDurationMinutes inside validateEventFromOptaplanner and more than 30 minutes apart'
    );
  }
};

export const getMonthDayFromSlot = (
  monthDay: MonthDayType
): { month: MonthType; day: DayType } => {
  const monthString = monthDay.slice(2, 4);
  const dayString = monthDay.slice(5, 7);
  const month = (parseInt(monthString, 10) - 1) as MonthType;
  const day = parseInt(dayString, 10) as DayType;
  return { month, day };
};

export const formatPlannerEventsToEventAndAdjustTime = (
  events: EventPlannerResponseBodyType[],
  oldEvent: EventPlusType,
  hostTimezone: string
): EventPlusType => {
  if (!events?.[0]?.id) {
    console.log(' no events present inside formatPlannerEventsToEvent');
    return null;
  }

  if (!oldEvent?.id) {
    console.log(' no oldEvent inside formatPlannerEventsToEvent');
    return null;
  }

  if (!oldEvent?.calendarId) {
    throw new Error('no calendarId inside oldEvent');
  }

  if (!dayjs(events?.[0]?.startDate).isValid()) {
    console.log(events?.[0], ' events?.[0]');
    throw new Error('startDate is not valid before formatting');
  }

  if (!dayjs(events?.[0]?.endDate).isValid()) {
    console.log(events?.[0], ' events?.[0]');
    throw new Error('startDate is not valid before formatting');
  }

  const sortedEvents = events.sort((a, b) => {
    if (a.part < b.part) {
      return -1;
    }
    if (a.part > b.part) {
      return 1;
    }
    return 0;
  });

  const firstPart = sortedEvents[0];
  const lastPart = sortedEvents[sortedEvents.length - 1];

  const monthDay = firstPart?.timeslot?.monthDay;
  const { month, day } = getMonthDayFromSlot(monthDay);

  const startHour = firstPart?.timeslot?.startTime
    ? parseInt(firstPart.timeslot.startTime.split(':')[0], 10)
    : dayjs(oldEvent.startDate.slice(0, 19)).tz(oldEvent.timezone, true).hour();

  const startMinute = firstPart?.timeslot?.startTime
    ? parseInt(firstPart.timeslot.startTime.split(':')[1], 10)
    : dayjs(oldEvent.startDate.slice(0, 19))
        .tz(oldEvent.timezone, true)
        .minute();
  const startDate = firstPart?.timeslot?.monthDay
    ? dayjs(oldEvent.startDate.slice(0, 19))
        .tz(oldEvent.timezone, true)
        .tz(hostTimezone)
        .month(month)
        .date(day)
        .hour(startHour)
        .minute(startMinute)
        .tz(oldEvent.timezone)
        .format()
    : dayjs(oldEvent.startDate.slice(0, 19))
        .tz(oldEvent.timezone, true)
        .hour(startHour)
        .minute(startMinute)
        .format();

  const endHour = lastPart?.timeslot?.endTime
    ? parseInt(lastPart.timeslot.endTime.split(':')[0], 10)
    : dayjs(oldEvent.endDate.slice(0, 19)).tz(oldEvent.timezone, true).hour();
  const endMinute = lastPart?.timeslot?.endTime
    ? parseInt(lastPart.timeslot.endTime.split(':')[1], 10)
    : dayjs(oldEvent.endDate.slice(0, 19)).tz(oldEvent.timezone, true).minute();
  const endDate = lastPart?.timeslot?.monthDay
    ? dayjs(oldEvent.endDate.slice(0, 19))
        .tz(oldEvent.timezone, true)
        .tz(hostTimezone)
        .month(month)
        .date(day)
        .hour(endHour)
        .minute(endMinute)
        .tz(oldEvent.timezone)
        .format()
    : dayjs(oldEvent.endDate.slice(0, 19))
        .tz(oldEvent.timezone, true)
        .minute(endMinute)
        .hour(endHour)
        .format();

  console.log(
    oldEvent.id,
    startDate,
    firstPart?.timeslot?.dayOfWeek,
    firstPart?.timeslot?.monthDay,
    firstPart?.timeslot?.startTime,
    startHour,
    startMinute,
    dayjs(oldEvent.startDate.slice(0, 19))
      .tz(oldEvent.timezone, true)
      .month(month)
      .date(day)
      .hour(startHour)
      .minute(startMinute)
      .format(),
    ` oldEvent.id, startDate, firstPart?.timeslot?.dayOfWeek, firstPart?.timeslot?.monthDay, firstPart?.timeslot?.startTime, startHour, startMinute, dayjs(oldEvent.startDate.slice(0, 19)).tz(oldEvent.timezone, true).month(month)
  .date(day)
  .hour(startHour).minute(startMinute).format(),`
  );

  console.log(
    oldEvent.id,
    endDate,
    lastPart?.timeslot?.dayOfWeek,
    lastPart?.timeslot?.monthDay,
    lastPart?.timeslot?.endTime,
    endHour,
    endMinute,
    dayjs(oldEvent.endDate.slice(0, 19))
      .tz(oldEvent.timezone, true)
      .month(month)
      .date(day)
      .hour(endHour)
      .minute(endMinute)
      .format(),
    ` oldEvent.id, endDate, lastPart?.timeslot?.dayOfWeek, lastPart?.timeslot?.monthDay, lastPart?.timeslot?.endTime, endHour, endMinute, dayjs(oldEvent.endDate.slice(0, 19)).tz(oldEvent.timezone, true)
    .month(month)
    .date(day)
    .hour(endHour).minute(endMinute).format()`
  );

  const newEvent: EventPlusType = {
    ...oldEvent,
    startDate,
    endDate,
  };
  console.log(newEvent, ' newEvent inside formatPlannerEventsToEvent');

  if (!dayjs(startDate).isValid()) {
    throw new Error('startDate is not valid after formatting');
  }

  if (!dayjs(endDate).isValid()) {
    throw new Error('startDate is not valid after formatting');
  }

  return newEvent;
};

export const putDataInSearch = async (
  id: string,
  vector: number[],
  userId: string
) => {
  try {
    const client = await getSearchClient();
    const response = await client.index({
      id,
      index: searchIndex,
      body: { [eventVectorName]: vector, userId },
      refresh: true,
    });
    console.log('Adding document:');
    console.log(response.body);
  } catch (e) {
    console.log(e, ' unable to put data into search');
  }
};

export const compareEventsToFilterUnequalEvents = (
  newEvent: EventPlusType,
  oldEvent?: EventPlusType
) => {
  if (!oldEvent?.id) {
    console.log(
      oldEvent?.id,
      ' oldEvent?.id inside compareEventsToFilterUnequalEvents likely new'
    );
    return true;
  }

  if (!newEvent?.id) {
    console.log(
      newEvent?.id,
      'no  newEvent?.id inside compareEventsToFilterUnequalEvents- bug '
    );
    throw new Error(
      `${newEvent} --- ${newEvent?.id}, no  newEvent?.id inside compareEventsToFilterUnequalEvents- bug`
    );
  }

  const oldEventModified = {
    ...oldEvent,
    startDate: dayjs(oldEvent.startDate.slice(0, 19))
      .tz(oldEvent.timezone, true)
      .format(),
    endDate: dayjs(oldEvent.endDate.slice(0, 19))
      .tz(oldEvent.timezone, true)
      .format(),
  };

  const newEventModified = {
    ...newEvent,
    startDate: dayjs(newEvent.startDate.slice(0, 19))
      .tz(newEvent.timezone, true)
      .format(),
    endDate: dayjs(newEvent.endDate.slice(0, 19))
      .tz(newEvent.timezone, true)
      .format(),
  };
  console.log(
    !_.isEqual(newEventModified, oldEventModified),
    ' !_.isEqual(newEventModified, oldEventModified)'
  );
  return !_.isEqual(newEventModified, oldEventModified);
};

export const getCalendarWithId = async (calendarId: string) => {
  try {
    const operationName = 'getCalendar';
    const query = `
    query getCalendar($id: String!) {
      Calendar_by_pk(id: $id) {
        resource
        updatedAt
        userId
        account
        colorId
        id
        modifiable
        title
        backgroundColor
        account
        accessLevel
        createdDate
        defaultReminders
        primary
        globalPrimary
        foregroundColor
        pageToken
        syncToken
      }
    }
  `;
    const variables = {
      id: calendarId,
    };

    const res: { data: { Calendar_by_pk: CalendarType } } = await got
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

    console.log(res, ' res from getCalendarForEvent');
    return res?.data?.Calendar_by_pk;
  } catch (e) {
    console.log(e, ' getCalendarForEvent');
  }
};

export const getCalendarIntegration = async (
  userId: string,
  resource: string
) => {
  try {
    const operationName = 'getCalendarIntegration';
    const query = `
      query getCalendarIntegration($userId: uuid!, $resource: String!) {
        Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}}) {
          token
          expiresAt
          id
          refreshToken
          resource
          name
          clientType
        }
      }
    `;
    const variables = {
      userId,
      resource,
    };

    const res: { data: { Calendar_Integration: CalendarIntegrationType[] } } =
      await got
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

    console.log(res, ' res inside getCalendarIntegration');
    if (res?.data?.Calendar_Integration?.length > 0) {
      return res?.data?.Calendar_Integration?.[0];
    }
  } catch (e) {
    console.log(e, ' unable to get calendar integration');
  }
};

export const formatRemindersForGoogle = (
  reminders: ReminderType[]
): GoogleReminderType => {
  const googleOverrides: OverrideTypes = reminders.map((reminder) => {
    return {
      method: 'email',
      minutes: reminder.minutes,
    };
  });
  const googleReminders: GoogleReminderType = {
    overrides: googleOverrides,
    useDefault: false,
  };
  return googleReminders;
};

export const refreshZoomToken = async (
  refreshToken: string
): Promise<{
  access_token: string;
  token_type: 'bearer';
  refresh_token: string;
  expires_in: number;
  scope: string;
}> => {
  try {
    const username = zoomClientId;
    const password = zoomClientSecret;

    return axios({
      data: new URLSearchParams({
        refresh_token: refreshToken,
        grant_type: 'refresh_token',
      }).toString(),
      baseURL: zoomBaseTokenUrl,
      url: '/oauth/token',
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      auth: {
        username,
        password,
      },
    }).then(({ data }) => Promise.resolve(data));
  } catch (e) {
    console.log(e, ' unable to refresh zoom token');
  }
};

export const refreshGoogleToken = async (
  refreshToken: string,
  clientType: 'ios' | 'android' | 'web' | 'atomic-web'
): Promise<{
  access_token: string;
  expires_in: number;
  scope: string;
  token_type: string;
}> => {
  try {
    console.log('refreshGoogleToken called', refreshToken);
    console.log('clientType', clientType);
    console.log('googleClientIdIos', googleClientIdIos);
    switch (clientType) {
      case 'ios':
        return got
          .post(googleTokenUrl, {
            form: {
              grant_type: 'refresh_token',
              refresh_token: refreshToken,
              client_id: googleClientIdIos,
            },
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
          })
          .json();
      case 'android':
        return got
          .post(googleTokenUrl, {
            form: {
              grant_type: 'refresh_token',
              refresh_token: refreshToken,
              client_id: googleClientIdAndroid,
            },
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
          })
          .json();
      case 'web':
        return got
          .post(googleTokenUrl, {
            form: {
              grant_type: 'refresh_token',
              refresh_token: refreshToken,
              client_id: googleClientIdWeb,
              client_secret: googleClientSecretWeb,
            },
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
          })
          .json();
      case 'atomic-web':
        return got
          .post(googleTokenUrl, {
            form: {
              grant_type: 'refresh_token',
              refresh_token: refreshToken,
              client_id: googleClientIdAtomicWeb,
              client_secret: googleClientSecretAtomicWeb,
            },
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
          })
          .json();
    }
  } catch (e) {
    console.log(e, ' unable to refresh google token');
  }
};

export const updateCalendarIntegration = async (
  id: string,
  token?: string,
  expiresIn?: number,
  enabled?: boolean
) => {
  try {
    const operationName = 'updateCalendarIntegration';
    const query = `
      mutation updateCalendarIntegration($id: uuid!,${token !== undefined ? ' $token: String,' : ''}${expiresIn !== undefined ? ' $expiresAt: timestamptz,' : ''}${enabled !== undefined ? ' $enabled: Boolean,' : ''}) {
        update_Calendar_Integration_by_pk(pk_columns: {id: $id}, _set: {${token !== undefined ? 'token: $token,' : ''}${expiresIn !== undefined ? ' expiresAt: $expiresAt,' : ''}${enabled !== undefined ? ' enabled: $enabled,' : ''}}) {
          id
          name
          refreshToken
          token
          clientType
          userId
          updatedAt
        }
      }
    `;
    const variables = {
      id,
      token,
      expiresAt: dayjs().add(expiresIn, 'seconds').toISOString(),
      enabled,
    };

    const res = await got
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

    console.log(res, ' res inside updateCalendarIntegration');
  } catch (e) {
    console.log(e, ' unable to update calendar integration');
  }
};

export const decryptZoomTokens = (
  encryptedToken: string,
  encryptedRefreshToken?: string
) => {
  const ivBuffer = Buffer.from(zoomIVForPass, 'base64');
  const saltBuffer = Buffer.from(zoomSaltForPass, 'base64');

  const key = crypto.pbkdf2Sync(
    zoomPassKey as string,
    saltBuffer,
    10000,
    32,
    'sha256'
  );

  const decipherToken = crypto.createDecipheriv('aes-256-cbc', key, ivBuffer);
  let decryptedToken = decipherToken.update(encryptedToken, 'base64', 'utf8');
  decryptedToken += decipherToken.final('utf8');

  if (encryptedRefreshToken) {
    const decipherRefreshToken = crypto.createDecipheriv(
      'aes-256-cbc',
      key,
      ivBuffer
    );
    let decryptedRefreshToken = decipherRefreshToken.update(
      encryptedRefreshToken,
      'base64',
      'utf8'
    );
    decryptedRefreshToken += decipherRefreshToken.final('utf8');

    return {
      token: decryptedToken,
      refreshToken: decryptedRefreshToken,
    };
  }

  return {
    token: decryptedToken,
  };
};

export const encryptZoomTokens = (token: string, refreshToken?: string) => {
  const ivBuffer = Buffer.from(zoomIVForPass, 'base64');
  const saltBuffer = Buffer.from(zoomSaltForPass, 'base64');

  const key = crypto.pbkdf2Sync(
    zoomPassKey as string,
    saltBuffer,
    10000,
    32,
    'sha256'
  );
  const cipherToken = crypto.createCipheriv('aes-256-cbc', key, ivBuffer);
  let encryptedToken = cipherToken.update(token, 'utf8', 'base64');
  encryptedToken += cipherToken.final('base64');

  let encryptedRefreshToken = '';

  if (refreshToken) {
    const cipherRefreshToken = crypto.createCipheriv(
      'aes-256-cbc',
      key,
      ivBuffer
    );
    encryptedRefreshToken = cipherRefreshToken.update(
      refreshToken,
      'utf8',
      'base64'
    );
    encryptedRefreshToken += cipherRefreshToken.final('base64');
  }

  if (encryptedRefreshToken) {
    return {
      encryptedToken,
      encryptedRefreshToken,
    };
  } else {
    return { encryptedToken };
  }
};

export const getZoomIntegration = async (userId: string) => {
  try {
    const { id, token, expiresAt, refreshToken } = await getCalendarIntegration(
      userId,
      zoomResourceName
    );

    const decryptedTokens = decryptZoomTokens(token, refreshToken);

    return {
      id,
      expiresAt,
      ...decryptedTokens,
    };
  } catch (e) {
    console.log(e, ' unable to get zoom integration');
  }
};

export const updateZoomIntegration = async (
  id: string,
  accessToken: string,
  expiresIn: number
) => {
  try {
    const { encryptedToken } = encryptZoomTokens(accessToken);
    await updateCalendarIntegration(id, encryptedToken, expiresIn);
  } catch (e) {
    console.log(e, ' unable to update zoom integration');
  }
};
export const getZoomAPIToken = async (userId: string) => {
  let integrationId = '';
  try {
    console.log('getZoomAPIToken called');
    const { id, token, expiresAt, refreshToken } =
      await getZoomIntegration(userId);
    if (!refreshToken) {
      console.log('zoom not active, no refresh token');
      return;
    }

    integrationId = id;
    console.log(
      id,
      token,
      expiresAt,
      refreshToken,
      ' id, token, expiresAt, refreshToken'
    );
    if (dayjs().isAfter(dayjs(expiresAt)) || !token) {
      const res = await refreshZoomToken(refreshToken);
      console.log(res, ' res from refreshZoomToken');
      await updateZoomIntegration(id, res.access_token, res.expires_in);
      return res.access_token;
    }

    return token;
  } catch (e) {
    console.log(e, ' unable to get zoom api token');
    await updateCalendarIntegration(integrationId, null, null, false);
  }
};
export const getGoogleAPIToken = async (
  userId: string,
  resource: string,
  clientType: 'ios' | 'android' | 'web' | 'atomic-web'
) => {
  let integrationId = '';
  try {
    const { id, token, expiresAt, refreshToken } = await getCalendarIntegration(
      userId,
      resource
    );
    integrationId = id;
    console.log(
      id,
      token,
      expiresAt,
      refreshToken,
      ' id, token, expiresAt, refreshToken'
    );
    if (dayjs().isAfter(dayjs(expiresAt)) || !token) {
      const res = await refreshGoogleToken(refreshToken, clientType);
      console.log(res, ' res from refreshGoogleToken');
      await updateCalendarIntegration(id, res.access_token, res.expires_in);
      return res.access_token;
    }
    return token;
  } catch (e) {
    console.log(e, ' unable to get api token');
    await updateCalendarIntegration(integrationId, null, null, false);
  }
};

export const patchGoogleEvent = async (
  userId: string,
  calendarId: string,
  eventId: string,
  clientType: 'ios' | 'android' | 'web' | 'atomic-web',
  endDateTime?: string,
  startDateTime?: string,
  conferenceDataVersion?: 0 | 1,
  maxAttendees?: number,
  sendUpdates?: GoogleSendUpdatesType,
  anyoneCanAddSelf?: boolean,
  attendees?: GoogleAttendeeType[],
  conferenceData?: GoogleConferenceDataType,
  summary?: string,
  description?: string,
  timezone?: string,
  startDate?: string,
  endDate?: string,
  extendedProperties?: GoogleExtendedPropertiesType,
  guestsCanInviteOthers?: boolean,
  guestsCanModify?: boolean,
  guestsCanSeeOtherGuests?: boolean,
  originalStartDateTime?: string,
  originalStartDate?: string,
  recurrence?: string[],
  reminders?: GoogleReminderType,
  source?: GoogleSourceType,
  status?: string,
  transparency?: GoogleTransparencyType,
  visibility?: GoogleVisibilityType,
  iCalUID?: string,
  attendeesOmitted?: boolean,
  hangoutLink?: string,
  privateCopy?: boolean,
  locked?: boolean,
  attachments?: GoogleAttachmentType[],
  eventType?: GoogleEventType1,
  location?: string,
  colorId?: string
) => {
  try {
    const token = await getGoogleAPIToken(
      userId,
      googleCalendarResource,
      clientType
    );

    const googleCalendar = google.calendar({
      version: 'v3',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    let variables: any = {
      calendarId,
      conferenceDataVersion,
      eventId,
      maxAttendees,
      sendUpdates,
      requestBody: {},
    };

    let requestBody: any = {};

    if (endDate && timezone && !endDateTime) {
      const end = {
        date: dayjs(endDateTime.slice(0, 19))
          .tz(timezone, true)
          .format('YYYY-MM-DD'),
        timeZone: timezone,
      };
      requestBody.end = end;
    }

    if (endDateTime && timezone && !endDate) {
      console.log(
        eventId,
        endDateTime,
        timezone,
        ' eventId, endDateTime, timezone prior'
      );
      const end = {
        dateTime: endDateTime,
        timeZone: timezone,
      };
      requestBody.end = end;

      console.log(
        eventId,
        end.dateTime,
        end.timeZone,
        ' eventId, endDateTime, timezone after'
      );
    }

    if (startDate && timezone && !startDateTime) {
      const start = {
        date: dayjs(startDateTime.slice(0, 19))
          .tz(timezone, true)
          .format('YYYY-MM-DD'),
        timeZone: timezone,
      };
      requestBody.start = start;
    }

    if (startDateTime && timezone && !startDate) {
      console.log(
        eventId,
        startDateTime,
        timezone,
        ' eventId, startDateTime, timezone prior'
      );
      const start = {
        dateTime: startDateTime,
        timeZone: timezone,
      };
      requestBody.start = start;

      console.log(
        eventId,
        start.dateTime,
        start.timeZone,
        ' eventId, startDateTime, timezone after'
      );
    }

    if (originalStartDate && timezone && !originalStartDateTime) {
      const originalStartTime = {
        date: dayjs(originalStartDate.slice(0, 19))
          .tz(timezone, true)
          .format('YYYY-MM-DD'),
        timeZone: timezone,
      };
      requestBody.originalStartTime = originalStartTime;
    }

    if (originalStartDateTime && timezone && !originalStartDate) {
      const originalStartTime = {
        dateTime: originalStartDateTime,
        timeZone: timezone,
      };
      requestBody.originalStartTime = originalStartTime;
    }

    if (anyoneCanAddSelf) {
      requestBody.anyoneCanAddSelf = anyoneCanAddSelf;
    }

    if (attendees?.[0]?.email) {
      requestBody.attendees = attendees;
    }

    if (conferenceData?.createRequest) {
      requestBody.conferenceData = {
        createRequest: {
          conferenceSolutionKey: {
            type: conferenceData.type,
          },
          requestId: conferenceData?.requestId || uuid(),
        },
      };
    } else if (conferenceData?.entryPoints?.[0]) {
      requestBody.conferenceData = {
        conferenceSolution: {
          iconUri: conferenceData?.iconUri,
          key: {
            type: conferenceData?.type,
          },
          name: conferenceData?.name,
        },
        entryPoints: conferenceData?.entryPoints,
      };
    }

    if (description?.length > 0) {
      requestBody.description = description;
    }

    if (extendedProperties?.private || extendedProperties?.shared) {
      requestBody.extendedProperties = extendedProperties;
    }

    if (guestsCanInviteOthers) {
      requestBody.guestsCanInviteOthers = guestsCanInviteOthers;
    }

    if (guestsCanModify) {
      requestBody.guestsCanModify = guestsCanModify;
    }

    if (guestsCanSeeOtherGuests) {
      requestBody.guestsCanSeeOtherGuests = guestsCanSeeOtherGuests;
    }

    if (locked) {
      requestBody.locked = locked;
    }

    if (privateCopy) {
      requestBody.privateCopy = privateCopy;
    }

    if (recurrence?.[0]) {
      requestBody.recurrence = recurrence;
    }

    if (reminders) {
      requestBody.reminders = reminders;
    }

    if (source?.title || source?.url) {
      requestBody.source = source;
    }

    if (attachments?.[0]?.fileId) {
      requestBody.attachments = attachments;
    }

    if (eventType?.length > 0) {
      requestBody.eventType = eventType;
    }

    if (status) {
      requestBody.status = status;
    }

    if (transparency) {
      requestBody.transparency = transparency;
    }

    if (visibility) {
      requestBody.visibility = visibility;
    }

    if (iCalUID?.length > 0) {
      requestBody.iCalUID = iCalUID;
    }

    if (attendeesOmitted) {
      requestBody.attendeesOmitted = attendeesOmitted;
    }

    if (hangoutLink?.length > 0) {
      requestBody.hangoutLink = hangoutLink;
    }

    if (summary?.length > 0) {
      requestBody.summary = summary;
    }

    if (location?.length > 0) {
      requestBody.location = location;
    }

    if (colorId) {
      requestBody.colorId = colorId;
    }

    variables.requestBody = requestBody;
    console.log(
      eventId,
      requestBody,
      ' eventId, requestBody inside googlePatchEvent'
    );
    const res = await googleCalendar.events.patch(variables);
    console.log(eventId, res.data, ' eventId, results from googlePatchEvent');
  } catch (e) {
    console.log(e, ' unable to patch google event');
  }
};

export const createGoogleEventWithId = async (
  userId: string,
  calendarId: string,
  clientType: 'ios' | 'android' | 'web' | 'atomic-web',
  eventId: string,
  endDateTime?: string,
  startDateTime?: string,
  conferenceDataVersion?: 0 | 1,
  maxAttendees?: number,
  sendUpdates?: GoogleSendUpdatesType,
  anyoneCanAddSelf?: boolean,
  attendees?: GoogleAttendeeType[],
  conferenceData?: GoogleConferenceDataType,
  summary?: string,
  description?: string,
  timezone?: string,
  startDate?: string,
  endDate?: string,
  extendedProperties?: GoogleExtendedPropertiesType,
  guestsCanInviteOthers?: boolean,
  guestsCanModify?: boolean,
  guestsCanSeeOtherGuests?: boolean,
  originalStartDateTime?: string,
  originalStartDate?: string,
  recurrence?: string[],
  reminders?: GoogleReminderType,
  source?: GoogleSourceType,
  status?: string,
  transparency?: GoogleTransparencyType,
  visibility?: GoogleVisibilityType,
  iCalUID?: string,
  attendeesOmitted?: boolean,
  hangoutLink?: string,
  privateCopy?: boolean,
  locked?: boolean,
  attachments?: GoogleAttachmentType[],
  eventType?: GoogleEventType1,
  location?: string,
  colorId?: string
) => {
  try {
    const token = await getGoogleAPIToken(
      userId,
      googleCalendarResource,
      clientType
    );

    const googleCalendar = google.calendar({
      version: 'v3',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    let data: any = {};

    if (endDateTime && timezone && !endDate) {
      const end = {
        dateTime: endDateTime,
        timeZone: timezone,
      };

      data.end = end;
    }

    if (endDate && timezone && !endDateTime) {
      const end = {
        date: dayjs(endDate.slice(0, 19))
          .tz(timezone, true)
          .format('YYYY-MM-DD'),
        timeZone: timezone,
      };

      data.end = end;
    }

    if (startDate && timezone && !startDateTime) {
      const start = {
        date: dayjs(startDate.slice(0, 19))
          .tz(timezone, true)
          .format('YYYY-MM-DD'),
        timeZone: timezone,
      };
      data.start = start;
    }

    if (startDateTime && timezone && !startDate) {
      const start = {
        dateTime: startDateTime,
        timeZone: timezone,
      };
      data.start = start;
    }

    if (originalStartDate && timezone && !originalStartDateTime) {
      const originalStartTime = {
        date: originalStartDate,
        timeZone: timezone,
      };
      data.originalStartTime = originalStartTime;
    }

    if (originalStartDateTime && timezone && !originalStartDate) {
      const originalStartTime = {
        dateTime: dayjs(originalStartDateTime).tz(timezone, true).format(),
        timeZone: timezone,
      };
      data.originalStartTime = originalStartTime;
    }

    if (anyoneCanAddSelf) {
      data = { ...data, anyoneCanAddSelf };
    }

    if (attendees?.[0]?.email) {
      data = { ...data, attendees };
    }

    if (conferenceData?.createRequest) {
      data = {
        ...data,
        conferenceData: {
          createRequest: {
            conferenceSolutionKey: {
              type: conferenceData.type,
            },
            requestId: conferenceData?.requestId || uuid(),
          },
        },
      };
    } else if (conferenceData?.entryPoints?.[0]) {
      data = {
        ...data,
        conferenceData: {
          conferenceSolution: {
            iconUri: conferenceData?.iconUri,
            key: {
              type: conferenceData?.type,
            },
            name: conferenceData?.name,
          },
          entryPoints: conferenceData?.entryPoints,
        },
      };
    }

    if (description?.length > 0) {
      data = { ...data, description };
    }

    if (extendedProperties?.private || extendedProperties?.shared) {
      data = { ...data, extendedProperties };
    }

    if (guestsCanInviteOthers) {
      data = { ...data, guestsCanInviteOthers };
    }

    if (guestsCanModify) {
      data = { ...data, guestsCanModify };
    }

    if (guestsCanSeeOtherGuests) {
      data = { ...data, guestsCanSeeOtherGuests };
    }

    if (locked) {
      data = { ...data, locked };
    }

    if (privateCopy) {
      data = { ...data, privateCopy };
    }

    if (recurrence?.[0]) {
      data = { ...data, recurrence };
    }

    if (reminders) {
      data = { ...data, reminders };
    }

    if (source?.title || source?.url) {
      data = { ...data, source };
    }

    if (attachments?.[0]?.fileId) {
      data = { ...data, attachments };
    }

    if (eventType?.length > 0) {
      data = { ...data, eventType };
    }

    if (status) {
      data = { ...data, status };
    }

    if (transparency) {
      data = { ...data, transparency };
    }

    if (visibility) {
      data = { ...data, visibility };
    }

    if (iCalUID?.length > 0) {
      data = { ...data, iCalUID };
    }

    if (attendeesOmitted) {
      data = { ...data, attendeesOmitted };
    }

    if (hangoutLink?.length > 0) {
      data = { ...data, hangoutLink };
    }

    if (summary?.length > 0) {
      data = { ...data, summary };
    }

    if (location?.length > 0) {
      data = { ...data, location };
    }

    if (colorId) {
      data.colorId = colorId;
    }

    data.id = eventId;

    const res = await googleCalendar.events.insert({
      calendarId,
      conferenceDataVersion,
      maxAttendees,
      sendUpdates,

      requestBody: data,
    });

    console.log(res.data);

    console.log(res?.data, ' res?.data from googleCreateEventWithId');
  } catch (e) {
    console.log(e, ' unable to create google event with id');
  }
};

export const createGoogleEvent = async (
  userId: string,
  calendarId: string,
  clientType: 'ios' | 'android' | 'web' | 'atomic-web',
  generatedId?: string,
  endDateTime?: string,
  startDateTime?: string,
  conferenceDataVersion?: 0 | 1,
  maxAttendees?: number,
  sendUpdates?: GoogleSendUpdatesType,
  anyoneCanAddSelf?: boolean,
  attendees?: GoogleAttendeeType[],
  conferenceData?: GoogleConferenceDataType,
  summary?: string,
  description?: string,
  timezone?: string,
  startDate?: string,
  endDate?: string,
  extendedProperties?: GoogleExtendedPropertiesType,
  guestsCanInviteOthers?: boolean,
  guestsCanModify?: boolean,
  guestsCanSeeOtherGuests?: boolean,
  originalStartDateTime?: string,
  originalStartDate?: string,
  recurrence?: string[],
  reminders?: GoogleReminderType,
  source?: GoogleSourceType,
  status?: string,
  transparency?: GoogleTransparencyType,
  visibility?: GoogleVisibilityType,
  iCalUID?: string,
  attendeesOmitted?: boolean,
  hangoutLink?: string,
  privateCopy?: boolean,
  locked?: boolean,
  attachments?: GoogleAttachmentType[],
  eventType?: GoogleEventType1,
  location?: string,
  colorId?: string
) => {
  try {
    console.log(
      generatedId,
      conferenceDataVersion,
      conferenceData,
      ' generatedId, conferenceDataVersion, conferenceData inside createGoogleEvent'
    );
    const token = await getGoogleAPIToken(
      userId,
      googleCalendarResource,
      clientType
    );

    const googleCalendar = google.calendar({
      version: 'v3',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    let data: any = {};

    if (endDateTime && timezone && !endDate) {
      const end = {
        dateTime: endDateTime,
        timeZone: timezone,
      };

      data.end = end;
    }

    if (endDate && timezone && !endDateTime) {
      const end = {
        date: dayjs(endDate.slice(0, 19))
          .tz(timezone, true)
          .format('YYYY-MM-DD'),
        timeZone: timezone,
      };

      data.end = end;
    }

    if (startDate && timezone && !startDateTime) {
      const start = {
        date: dayjs(startDate.slice(0, 19))
          .tz(timezone, true)
          .format('YYYY-MM-DD'),
        timeZone: timezone,
      };
      data.start = start;
    }

    if (startDateTime && timezone && !startDate) {
      const start = {
        dateTime: startDateTime,
        timeZone: timezone,
      };
      data.start = start;
    }

    if (originalStartDate && timezone && !originalStartDateTime) {
      const originalStartTime = {
        date: originalStartDate,
        timeZone: timezone,
      };
      data.originalStartTime = originalStartTime;
    }

    if (originalStartDateTime && timezone && !originalStartDate) {
      const originalStartTime = {
        dateTime: dayjs(originalStartDateTime).tz(timezone, true).format(),
        timeZone: timezone,
      };
      data.originalStartTime = originalStartTime;
    }

    if (anyoneCanAddSelf) {
      data = { ...data, anyoneCanAddSelf };
    }

    if (attendees?.[0]?.email) {
      data = { ...data, attendees };
    }

    if (conferenceData?.createRequest) {
      data = {
        ...data,
        conferenceData: {
          createRequest: {
            conferenceSolutionKey: {
              type: conferenceData.type,
            },
            requestId: conferenceData?.requestId || uuid(),
          },
        },
      };
    } else if (conferenceData?.entryPoints?.[0]) {
      data = {
        ...data,
        conferenceData: {
          conferenceSolution: {
            iconUri: conferenceData?.iconUri,
            key: {
              type: conferenceData?.type,
            },
            name: conferenceData?.name,
          },
          entryPoints: conferenceData?.entryPoints,
        },
      };
    }

    if (description?.length > 0) {
      data = { ...data, description };
    }

    if (extendedProperties?.private || extendedProperties?.shared) {
      data = { ...data, extendedProperties };
    }

    if (guestsCanInviteOthers) {
      data = { ...data, guestsCanInviteOthers };
    }

    if (guestsCanModify) {
      data = { ...data, guestsCanModify };
    }

    if (guestsCanSeeOtherGuests) {
      data = { ...data, guestsCanSeeOtherGuests };
    }

    if (locked) {
      data = { ...data, locked };
    }

    if (privateCopy) {
      data = { ...data, privateCopy };
    }

    if (recurrence?.[0]) {
      data = { ...data, recurrence };
    }

    if (reminders?.overrides?.length > 0 || reminders?.useDefault) {
      data = { ...data, reminders };
    }

    if (source?.title || source?.url) {
      data = { ...data, source };
    }

    if (attachments?.[0]?.fileId) {
      data = { ...data, attachments };
    }

    if (eventType?.length > 0) {
      data = { ...data, eventType };
    }

    if (status) {
      data = { ...data, status };
    }

    if (transparency) {
      data = { ...data, transparency };
    }

    if (visibility) {
      data = { ...data, visibility };
    }

    if (iCalUID?.length > 0) {
      data = { ...data, iCalUID };
    }

    if (attendeesOmitted) {
      data = { ...data, attendeesOmitted };
    }

    if (hangoutLink?.length > 0) {
      data = { ...data, hangoutLink };
    }

    if (summary?.length > 0) {
      data = { ...data, summary };
    }

    if (location?.length > 0) {
      data = { ...data, location };
    }

    if (colorId) {
      data.colorId = colorId;
    }

    const res = await googleCalendar.events.insert({
      calendarId,
      conferenceDataVersion,
      maxAttendees,
      sendUpdates,

      requestBody: data,
    });

    console.log(res.data);

    console.log(res?.data, ' res?.data from googleCreateEvent');
    return {
      id: `${res?.data?.id}#${calendarId}`,
      googleEventId: res?.data?.id,
      generatedId,
      calendarId,
      generatedEventId: generatedId.split('#')[0],
    };
  } catch (e) {
    console.log(e, ' createGoogleEvent');
  }
};

export const postPlannerModifyEventInCalendar = async (
  newEvent: EventPlusType,
  userId: string,
  method: 'update' | 'create' | 'createWithId',
  resource: string,
  isTimeBlocking: boolean,
  clientType: 'ios' | 'android' | 'web' | 'atomic-web',
  newReminders?: ReminderType[],
  attendees?: MeetingAssistAttendeeType[],
  conference?: ConferenceType
): Promise<string | CreateGoogleEventResponseType> => {
  try {
    console.log(newEvent, ' newEvent inside postPlannerModifyEventInCalendar');
    if (method === 'update') {
      if (resource === googleCalendarResource) {
        const googleReminders: GoogleReminderType =
          newReminders?.length > 0
            ? formatRemindersForGoogle(newReminders)
            : undefined;

        await patchGoogleEvent(
          userId,
          newEvent.calendarId,
          newEvent.eventId,
          clientType,
          newEvent.endDate,
          newEvent.startDate,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          newEvent.timezone,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          googleReminders,
          undefined,
          undefined,
          newEvent.transparency,
          newEvent?.visibility,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          newEvent?.colorId
        );
        return newEvent.id;
      }
    } else if (method === 'create') {
      console.log(
        newEvent,
        ' newEvent inside create inside postPlannerModifyEventInCalendar'
      );
      if (resource === googleCalendarResource) {
        const googleReminders: GoogleReminderType =
          newReminders?.length > 0
            ? formatRemindersForGoogle(newReminders)
            : undefined;

        const idResponseBody: CreateGoogleEventResponseType =
          await createGoogleEvent(
            userId,
            newEvent.calendarId,
            clientType,
            newEvent?.id,
            newEvent?.endDate,
            newEvent?.startDate,
            conference?.id ? 1 : 0,
            undefined,
            undefined,
            undefined,
            attendees?.map((a) => ({
              email: a?.primaryEmail?.trim(),
              id: a?.id,
              displayName: a?.name,
            })),
            conference?.id
              ? {
                  type: conference?.app === 'zoom' ? 'addOn' : 'hangoutsMeet',
                  name: conference?.name,
                  conferenceId: conference?.id,
                  entryPoints: conference?.entryPoints,
                  createRequest:
                    conference?.app === 'google'
                      ? {
                          requestId: conference?.requestId,
                          conferenceSolutionKey: {
                            type: 'hangoutsMeet',
                          },
                        }
                      : undefined,
                }
              : undefined,
            newEvent.summary || newEvent?.title,
            newEvent.notes,
            newEvent.timezone,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            newEvent?.recurrence,
            googleReminders,
            undefined,
            undefined,
            newEvent.transparency,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            isTimeBlocking ? 'focusTime' : 'default',
            undefined,
            newEvent?.colorId
          );
        console.log(
          idResponseBody,
          newEvent?.endDate,
          newEvent?.startDate,
          ' idResponseBody, newEvent?.endDate,  newEvent?.startDate'
        );
        return idResponseBody;
      }
    } else if (method === 'createWithId') {
      console.log(
        newEvent,
        ' newEvent inside createWithId inside postPlannerModifyEventInCalendar'
      );
      if (resource === googleCalendarResource) {
        const googleReminders: GoogleReminderType =
          newReminders?.length > 0
            ? formatRemindersForGoogle(newReminders)
            : undefined;

        await createGoogleEventWithId(
          userId,
          newEvent.calendarId,
          clientType,
          newEvent?.eventId,
          newEvent?.endDate,
          newEvent?.startDate,
          conference?.id ? 1 : 0,
          undefined,
          undefined,
          undefined,
          attendees?.map((a) => ({
            email: a?.primaryEmail,
            id: a?.id,
            displayName: a?.name,
          })),
          conference?.id
            ? {
                type: conference?.app === 'zoom' ? 'addOn' : 'hangoutsMeet',
                name: conference?.name,
                conferenceId: conference?.id,
                entryPoints: conference?.entryPoints,
              }
            : undefined,
          newEvent.summary || newEvent?.title,
          newEvent.notes,
          newEvent.timezone,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          newEvent?.recurrence,
          googleReminders,
          undefined,
          undefined,
          newEvent.transparency,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          undefined,
          isTimeBlocking ? 'focusTime' : 'default',
          undefined,
          newEvent?.colorId
        );
      }
    }
  } catch (e) {
    console.log(e, ' unable to update event');
    console.log(
      newEvent?.id,
      newEvent?.endDate,
      newEvent?.startDate,
      ' error - newEvent?.id, newEvent?.endDate,  newEvent?.startDate'
    );
  }
};

export const upsertEventsPostPlanner = async (events: EventType[]) => {
  try {
    const operationName = 'InsertEvent';
    const query = `
            mutation InsertEvent($events: [Event_insert_input!]!) {
                insert_Event(
                    objects: $events,
                    on_conflict: {
                        constraint: Event_pkey,
                        update_columns: [
                            userId,
                            title,
                            startDate,
                            endDate,
                            allDay,
                            recurrenceRule,
                            location,
                            notes,
                            attachments,
                            links,
                            timezone,
                            createdDate,
                            deleted,
                            taskId,
                            taskType,
                            priority,
                            followUpEventId,
                            isFollowUp,
                            isPreEvent,
                            isPostEvent,
                            preEventId,
                            postEventId,
                            modifiable,
                            forEventId,
                            conferenceId,
                            maxAttendees,
                            sendUpdates,
                            anyoneCanAddSelf,
                            guestsCanInviteOthers,
                            guestsCanSeeOtherGuests,
                            originalStartDate,
                            originalAllDay,
                            status,
                            summary,
                            transparency,
                            visibility,
                            recurringEventId,
                            updatedAt,
                            iCalUID,
                            htmlLink,
                            colorId,
                            creator,
                            organizer,
                            endTimeUnspecified,
                            recurrence,
                            originalTimezone,
                            attendeesOmitted,
                            extendedProperties,
                            hangoutLink,
                            guestsCanModify,
                            locked,
                            source,
                            eventType,
                            privateCopy,
                            calendarId,
                            backgroundColor,
                            foregroundColor,
                            useDefaultAlarms,
                            positiveImpactScore,
                            negativeImpactScore,
                            positiveImpactDayOfWeek,
                            positiveImpactTime,
                            negativeImpactDayOfWeek,
                            negativeImpactTime,
                            preferredDayOfWeek,
                            preferredTime,
                            isExternalMeeting,
                            isExternalMeetingModifiable,
                            isMeetingModifiable,
                            isMeeting,
                            dailyTaskList,
                            weeklyTaskList,
                            isBreak,
                            preferredStartTimeRange,
                            preferredEndTimeRange,
                            copyAvailability,
                            copyTimeBlocking,
                            copyTimePreference,
                            copyReminders,
                            copyPriorityLevel,
                            copyModifiable,
                            copyCategories,
                            copyIsBreak,
                            timeBlocking,
                            userModifiedAvailability,
                            userModifiedTimeBlocking,
                            userModifiedTimePreference,
                            userModifiedReminders,
                            userModifiedPriorityLevel,
                            userModifiedCategories,
                            userModifiedModifiable,
                            userModifiedIsBreak,
                            hardDeadline,
                            softDeadline,
                            copyIsMeeting,
                            copyIsExternalMeeting,
                            userModifiedIsMeeting,
                            userModifiedIsExternalMeeting,
                            duration,
                            copyDuration,
                            userModifiedDuration,
                            unlink,
                            copyColor,
                            userModifiedColor,
                            byWeekDay,
                            localSynced,
                            meetingId,
                            eventId,
                        ]
                    }){
                    returning {
                        id
                    }
                    affected_rows
                }
            }
        `;
    _.uniqBy(events, 'id').forEach((e) =>
      console.log(e?.id, e, 'id, e inside upsertEventsPostPlanner ')
    );
    const variables = {
      events: _.uniqBy(events, 'id'),
    };

    const response: {
      data: {
        insert_Event: { affected_rows: number; returning: { id: string }[] };
      };
    } = await got
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
      response?.data?.insert_Event?.affected_rows,
      ' response after upserting events'
    );
    response?.data?.insert_Event?.returning?.forEach((e) =>
      console.log(e, ' returning  response after upserting events')
    );
    return response;
  } catch (e) {
    console.log(e, ' unable to update event');
  }
};

export const insertAttendeesforEvent = async (attendees: AttendeeType[]) => {
  try {
    if (!(attendees?.filter((a) => !!a?.eventId)?.length > 0)) {
      return;
    }

    const operationName = 'InsertAttendeesForEvent';
    const query = `
            mutation InsertAttendeesForEvent($attendees: [Attendee_insert_input!]!) {
                insert_Attendee(objects: $attendees) {
                    affected_rows
                    returning {
                        additionalGuests
                        comment
                        contactId
                        createdDate
                        deleted
                        emails
                        eventId
                        id
                        imAddresses
                        name
                        optional
                        phoneNumbers
                        resource
                        responseStatus
                        updatedAt
                        userId
                    }
                }
            }
        `;
    const variables = {
      attendees,
    };

    const response: {
      data: {
        insert_Attendee: { affected_rows: number; returning: AttendeeType[] };
      };
    } = await got
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
      response?.data?.insert_Attendee?.returning,
      ' this is response in insertAttendees'
    );
    response?.data?.insert_Attendee?.returning.forEach((r) =>
      console.log(r, ' response in insertAttendees')
    );
  } catch (e) {
    console.log(e, ' unable to insert Attendees for new event');
  }
};

export const deleteAttendeesWithIds = async (
  eventIds: string[],
  userId: string
) => {
  try {
    if (!(eventIds?.filter((e) => !!e)?.length > 0)) {
      return;
    }
    eventIds.forEach((e) =>
      console.log(e, ' eventIds inside deleteRemindersWithIds')
    );
    const operationName = 'DeleteAttendeesWithEventIds';
    const query = `
            mutation DeleteAttendeesWithEventIds($userId: uuid!, $eventIds: [String!]!) {
                delete_Attendee(where: {userId: {_eq: $userId}, eventId: {_in: $eventIds}}) {
                    affected_rows
                    returning {
                        additionalGuests
                        comment
                        contactId
                        createdDate
                        deleted
                        emails
                        eventId
                        id
                        imAddresses
                        name
                        optional
                        phoneNumbers
                        resource
                        responseStatus
                        updatedAt
                        userId
                    }
                }
            }

    `;

    const variables = {
      userId,
      eventIds,
    };

    const response = await got
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
    console.log(response, ' this is response in deleteAttendeesWithIds');
  } catch (e) {
    console.log(e, ' deleteAttendeesWithIds');
  }
};

export const deleteRemindersWithIds = async (
  eventIds: string[],
  userId: string
) => {
  try {
    if (!(eventIds?.filter((e) => !!e)?.length > 0)) {
      return;
    }
    eventIds.forEach((e) =>
      console.log(e, ' eventIds inside deleteRemindersWithIds')
    );
    const operationName = 'deleteRemindersWithIds';
    const query = `
      mutation deleteRemindersWithIds($userId: uuid!, $eventIds: [String!]!) {
        delete_Reminder(where: {userId: {_eq: $userId}, eventId: {_in: $eventIds}}) {
          affected_rows
        }
      }
    `;

    const variables = {
      userId,
      eventIds,
    };

    const response = await got
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
    console.log(response, ' this is response in deleteRemindersWithIds');
  } catch (e) {
    console.log(e, ' deleteRemindersWithIds');
  }
};

export const insertReminders = async (reminders: ReminderTypeAdjusted[]) => {
  try {
    if (!(reminders?.filter((e) => !!e?.eventId)?.length > 0)) {
      return;
    }

    reminders.forEach((r) =>
      console.log(r, ' reminder inside insertReminders')
    );

    const operationName = 'InsertReminder';
    const query = `
            mutation InsertReminder($reminders: [Reminder_insert_input!]!) {
                insert_Reminder(objects: $reminders) {
                    affected_rows
                    returning {
                        id
                        createdDate
                        deleted
                        eventId
                        method
                        minutes
                        reminderDate
                        timezone
                        updatedAt
                        useDefault
                        userId
                    }
                }
            }
        `;
    const variables = {
      reminders,
    };

    const response: {
      data: { insert_Reminder: { returning: ReminderType[] } };
    } = await got
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
      response?.data?.insert_Reminder?.returning,
      ' this is response in insertReminders'
    );
    response?.data?.insert_Reminder?.returning.forEach((r) =>
      console.log(r, ' response in insertReminder')
    );
  } catch (e) {
    console.log(e, ' unable to insertReminders');
  }
};

export const deletePreferredTimeRangesForEvents = async (
  eventIds: string[]
) => {
  try {
    const operationName = 'DeletePreferredTimeRangesGivenEvents';
    const query = `mutation DeletePreferredTimeRangesGivenEvents($eventIds: [String!]!) {
                delete_PreferredTimeRange(where: {eventId: {_in: $eventIds}}) {
                    affected_rows
                }
            }
        `;

    const variables = {
      eventIds,
    };

    const res: {
      data: { delete_PreferredTimeRange: { affected_rows: number } };
    } = await got
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
      res?.data?.delete_PreferredTimeRange?.affected_rows,
      ' this is response affected_rows in deletePreferredTimeRangesForEvent'
    );
  } catch (e) {
    console.log(e, ' unable to delete preferred time ranges');
  }
};
export const deletePreferredTimeRangesForEvent = async (eventId: string) => {
  try {
    if (!eventId) {
      console.log(
        eventId,
        ' no eventId inside deletePreferredTimeRangesForEvent'
      );
      return;
    }

    const operationName = 'DeletePreferredTimeRangesGivenEvent';
    const query = `
      mutation DeletePreferredTimeRangesGivenEvent($eventId: String!) {
        delete_PreferredTimeRange(where: {eventId: {_eq: $eventId}}) {
          affected_rows
        }
      }
    `;

    const variables = {
      eventId,
    };

    const res: {
      data: { delete_PreferredTimeRange: { affected_rows: number } };
    } = await got
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
      res?.data?.delete_PreferredTimeRange?.affected_rows,
      ' this is response affected_rows in deletePreferredTimeRangesForEvent'
    );
  } catch (e) {
    console.log(e, ' unable to deletePreferredTimeRangesForEvent');
  }
};

export const insertPreferredTimeRanges = async (
  preferredTimeRanges: PreferredTimeRangeType[]
) => {
  try {
    console.log(
      preferredTimeRanges,
      ' preferredTimeRanges inside insertPreferredTimeRanges'
    );
    if (!(preferredTimeRanges?.length > 0)) {
      console.log('no preferredTimeRanges inside insertPreferredTimeRanges');
      return;
    }

    const operationName = 'InsertPreferredTimeRanges';
    const query = `
      mutation InsertPreferredTimeRanges($preferredTimeRanges: [PreferredTimeRange_insert_input!]!) {
        insert_PreferredTimeRange(objects: $preferredTimeRanges) {
          affected_rows
          returning {
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
      }
    `;

    const variables = {
      preferredTimeRanges,
    };

    const response: {
      data: {
        insert_PreferredTimeRange: {
          returning: PreferredTimeRangeType[];
          affected_rows: number;
        };
      };
    } = await got
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

    console.log(response, ' response inside insert_PreferredTimeRanges');
    console.log(
      response?.data,
      ' response?.data inside insert_PreferredTimeRanges'
    );
    console.log(
      response?.data?.insert_PreferredTimeRange?.affected_rows,
      ' affected_rows inside insertPreferredTimeRanges'
    );
    response?.data?.insert_PreferredTimeRange?.returning?.map((pt) =>
      console.log(pt, ' returning inside insertPreferredTimeRanges')
    );
  } catch (e) {
    console.log(e, ' unable to insert preferred time ranges');
  }
};

export const updateAllCalendarEventsPostPlanner = async (
  plannerEvents: EventPlannerResponseBodyType[][],
  eventsToValidate: EventPlannerResponseBodyType[][],
  allEvents: EventPlusType[],
  oldEvents: EventPlusType[],
  hostTimezone: string,
  hostBufferTimes?: BufferTimeObjectType[],
  newHostReminders?: RemindersForEventType[],
  breaks?: EventPlusType[],
  oldAttendeeExternalEvents?: MeetingAssistEventType[],
  isReplan?: boolean,
  originalGoogleEventIdToUpdate?: string,
  originalCalendarIdToUpdate?: string
) => {
  try {
    eventsToValidate.forEach((e) => validateEventsFromOptaplanner(e));
    const eventsToUpdate: EventPlusType[] = plannerEvents.map((e) =>
      formatPlannerEventsToEventAndAdjustTime(
        e,
        allEvents?.find((event) => event.id === e[0].eventId),
        hostTimezone
      )
    );
    eventsToUpdate.forEach((e) =>
      console.log(
        e,
        ' eventsToUpdate inside updateAllCalendarEventsPostPlanner'
      )
    );

    const filteredAllEvents = allEvents
      .map((e) => {
        const foundIndex = oldAttendeeExternalEvents?.findIndex(
          (a) => a?.id === e?.id
        );
        if (foundIndex > -1) {
          return null;
        }
        return e;
      })
      ?.filter((e) => e !== null);

    const eventsWithMeetingIds =
      filteredAllEvents?.filter((e) => !!e?.meetingId) || [];
    const meetingIdsOfInternalAttendees = _.uniqBy(
      filteredAllEvents,
      'meetingId'
    )
      ?.filter((e) => !!e?.meetingId)
      ?.map((e) => e.meetingId);

    console.log(eventsWithMeetingIds, ' eventsWithMeetingIds');

    console.log(
      meetingIdsOfInternalAttendees,
      ' meetingIdsOfInternalAttendees'
    );

    const eventsToBeCreatedWithNewId: {
      meetingId: string;
      event: EventPlusType;
      conference?: ConferenceType;
      attendees?: MeetingAssistAttendeeType[];
      resource?: string;
      clientType?: 'ios' | 'android' | 'web' | 'atomic-web';
    }[] = [];

    if (
      meetingIdsOfInternalAttendees &&
      meetingIdsOfInternalAttendees?.length > 0
    ) {
      const meetingAssists =
        (await listMeetingAssistsGivenMeetingIds(
          meetingIdsOfInternalAttendees
        )) || [];
      for (const meetingAssist of meetingAssists) {
        const attendees = await listMeetingAssistAttendeesGivenMeetingId(
          meetingAssist?.id
        );
        const externalAttendees = attendees?.filter(
          (a) => !!a?.externalAttendee
        );

        const eventForMeetingIdHostOnly = eventsWithMeetingIds
          ?.filter((e) => e?.meetingId === meetingAssist?.id)
          ?.filter((e) => e?.userId === meetingAssist?.userId)
          ?.filter((e) => e?.method === 'create')
          ?.filter((e) => {
            const externalIndex = externalAttendees?.findIndex(
              (a) => a?.userId === e?.userId
            );
            if (externalIndex > -1) {
              return false;
            }

            return true;
          })?.[0];

        const eventsForMeetingIdSinHost = eventsWithMeetingIds
          ?.filter((e) => e?.meetingId === meetingAssist?.id)
          ?.filter((e) => e?.userId !== meetingAssist?.userId)
          ?.filter((e) => e?.method === 'create')
          ?.filter((e) => {
            const externalIndex = externalAttendees?.findIndex(
              (a) => a?.userId === e?.userId
            );
            if (externalIndex > -1) {
              return false;
            }

            return true;
          });

        console.log(
          eventsForMeetingIdSinHost,
          ' eventsForMeetingIdSinHost inside for loop meetingIdsOfInternalAttendees'
        );

        for (const eventForMeetingIdSinHost of eventsForMeetingIdSinHost) {
          eventForMeetingIdSinHost.startDate = dayjs(
            eventForMeetingIdHostOnly.startDate.slice(0, 19)
          )
            .tz(eventForMeetingIdHostOnly.timezone, true)
            .tz(eventForMeetingIdSinHost.timezone)
            .format();
          eventForMeetingIdSinHost.endDate = dayjs(
            eventForMeetingIdHostOnly.endDate.slice(0, 19)
          )
            .tz(eventForMeetingIdHostOnly.timezone, true)
            .tz(eventForMeetingIdSinHost.timezone)
            .format();

          eventsToBeCreatedWithNewId.push({
            meetingId: meetingAssist?.id,
            event: eventForMeetingIdSinHost,
          });
        }

        const eventsForMeetingIdSinHostAnyMethod = eventsWithMeetingIds
          ?.filter((e) => e?.meetingId === meetingAssist?.id)
          ?.filter((e) => e?.userId !== meetingAssist?.userId)
          ?.filter((e) => {
            const externalIndex = externalAttendees?.findIndex(
              (a) => a?.userId === e?.userId
            );
            if (externalIndex > -1) {
              return false;
            }

            return true;
          });

        const eventForMeetingIdHostOnlyAnyMethod = eventsWithMeetingIds
          ?.filter((e) => e?.meetingId === meetingAssist?.id)
          ?.filter((e) => e?.userId === meetingAssist?.userId)
          ?.filter((e) => {
            const externalIndex = externalAttendees?.findIndex(
              (a) => a?.userId === e?.userId
            );
            if (externalIndex > -1) {
              return false;
            }

            return true;
          })?.[0];

        if (eventForMeetingIdHostOnlyAnyMethod?.id) {
          eventsForMeetingIdSinHostAnyMethod?.forEach((e) => {
            e.startDate = dayjs(
              eventForMeetingIdHostOnlyAnyMethod.startDate.slice(0, 19)
            )
              .tz(eventForMeetingIdHostOnlyAnyMethod.timezone, true)
              .tz(e.timezone)
              .format();
            e.endDate = dayjs(
              eventForMeetingIdHostOnlyAnyMethod.endDate.slice(0, 19)
            )
              .tz(eventForMeetingIdHostOnlyAnyMethod.timezone, true)
              .tz(e.timezone)
              .format();
          });
        }
      }
    }

    const filteredEventsToUpdate = eventsToUpdate
      .filter((e1) => {
        const foundOldEvent = oldEvents?.find((e2) => e2?.id === e1?.id);
        console.log(foundOldEvent, ' foundOldEvent inside filter');
        if (foundOldEvent) {
          return compareEventsToFilterUnequalEvents(e1, foundOldEvent);
        }
        return true;
      })
      ?.filter((e) => {
        const eventExists = oldAttendeeExternalEvents?.find(
          (a) => a?.id === e?.id
        );
        console.log(eventExists, ' eventExists');
        return !eventExists;
      })
      ?.filter((e) => {
        const createEventSinHostIndex = eventsToBeCreatedWithNewId?.findIndex(
          (c) => c?.event?.id === e?.id
        );

        if (createEventSinHostIndex > -1) {
          return false;
        }
        return true;
      })
      ?.filter((e) => !!e);

    filteredEventsToUpdate.forEach((e1) =>
      console.log(
        e1,
        oldEvents?.find((e2) => e2?.id === e1?.id),
        '  filteredEventsToUpdate'
      )
    );

    let createPromises: Promise<CreateGoogleEventResponseType>[] = [];
    let updatePromises: Promise<string>[] = [];
    const eventsToUpsert: EventPlusType[] = [];
    const deleteReminders: ReminderTypeAdjusted[] = [];
    const insertReminderObjects: ReminderTypeAdjusted[] = [];
    const insertPreferredTimeRangeObjects: PreferredTimeRangeType[] = [];
    const deletePreferredTimeRangeObjects: PreferredTimeRangeType[] = [];
    const insertAttendeeObjects: AttendeeType[] = [];

    const eventToFilterForUpdateConferences: EventPlusType[] = [];

    const eventsToRemove: EventPlusType[] = [];

    hostBufferTimes?.forEach((b) =>
      console.log(
        b.beforeEvent,
        b.afterEvent,
        ' bufferTimes before eventToUpdate loop inside updateAllCalendarEventsPostPlanner'
      )
    );

    for (const eventToUpdate of filteredEventsToUpdate) {
      console.log(
        eventToUpdate,
        ' eventToUpdate inside updateAllCalendarEventsPostPlanner'
      );
      const { resource } = await getCalendarWithId(eventToUpdate.calendarId);
      const calendarIntegration = await getCalendarIntegration(
        eventToUpdate.userId,
        resource
      );
      const clientType = calendarIntegration?.clientType;

      // --- REPLAN LOGIC ---
      if (
        isReplan &&
        originalGoogleEventIdToUpdate &&
        originalCalendarIdToUpdate &&
        eventToUpdate.eventId === originalGoogleEventIdToUpdate && // eventId is Google's ID
        eventToUpdate.calendarId === originalCalendarIdToUpdate
      ) {
        console.log(
          `Replanning: Updating event ${originalGoogleEventIdToUpdate} in calendar ${originalCalendarIdToUpdate}`
        );
        // Ensure attendees are in GoogleAttendeeType format if needed by patchGoogleEvent
        const googleAttendees: GoogleAttendeeType[] =
          eventToUpdate.attendees?.map((att) => ({
            email: att.primaryEmail || att.emails?.[0]?.value,
            displayName: att.name,
            // We might need to map responseStatus, optional, etc. if available and needed
          })) || [];

        // Call postPlannerModifyEventInCalendar with 'update'
        // IMPORTANT: newEvent.eventId for patchGoogleEvent should be the originalGoogleEventIdToUpdate
        // The eventToUpdate contains the new start/end times and other modified properties.
        updatePromises.push(
          postPlannerModifyEventInCalendar(
            { ...eventToUpdate, eventId: originalGoogleEventIdToUpdate }, // Pass original Google ID for update
            eventToUpdate.userId,
            'update',
            resource,
            false, // Assuming the main replanned event is not inherently a "time blocking" break
            clientType,
            remindersObjectForEvent?.reminders,
            googleAttendees, // Pass the full final list of attendees
            undefined // Conference data - handle if it can change during replan
          ) as Promise<string>
        );
        eventToUpdate.method = null; // Mark as processed for upsert logic
        eventsToUpsert.push(eventToUpdate); // Still upsert to Hasura to reflect changes

        // Handle reminders and preferred time ranges for the updated event
        if (remindersObjectForEvent?.reminders?.length > 0) {
          const oldReminders = await listRemindersForEvent(
            originalGoogleEventIdToUpdate,
            eventToUpdate.userId
          ); // Use original ID
          if (oldReminders?.length > 0) {
            deleteReminders.push(
              ...oldReminders.map((r) => ({
                ...r,
                eventId: originalGoogleEventIdToUpdate,
              }))
            );
          }
          insertReminderObjects.push(
            ...remindersObjectForEvent.reminders.map((r) => ({
              ...r,
              eventId: originalGoogleEventIdToUpdate,
            }))
          );
        }
        const oldPreferredTimeRanges = await listPreferredTimeRangesForEvent(
          originalGoogleEventIdToUpdate
        ); // Use original ID
        if (
          !_.isEqual(oldPreferredTimeRanges, eventToUpdate.preferredTimeRanges)
        ) {
          if (oldPreferredTimeRanges?.length > 0) {
            deletePreferredTimeRangeObjects.push(
              ...oldPreferredTimeRanges.map((ptr) => ({
                ...ptr,
                eventId: originalGoogleEventIdToUpdate,
              }))
            );
          }
          if (eventToUpdate?.preferredTimeRanges?.length > 0) {
            insertPreferredTimeRangeObjects.push(
              ...eventToUpdate.preferredTimeRanges.map((ptr) => ({
                ...ptr,
                eventId: originalGoogleEventIdToUpdate,
              }))
            );
          }
        }
        continue; // Skip the create logic below for this event
      }
      // --- END REPLAN LOGIC ---

      const beforeEventIndex = hostBufferTimes?.findIndex(
        (bufferTimes) => bufferTimes?.beforeEvent?.id === eventToUpdate.id
      );
      console.log(beforeEventIndex, resource, ' beforeEventIndex, resource ');
      const afterEventIndex = hostBufferTimes?.findIndex(
        (bufferTimes) => bufferTimes?.afterEvent?.id === eventToUpdate.id
      );
      console.log(afterEventIndex, resource, ' afterEventIndex, resource ');
      const remindersObjectForEvent = newHostReminders?.find(
        (reminder) => reminder.eventId === eventToUpdate.id
      );
      const breakIndex = breaks?.findIndex(
        (breakEvent) => breakEvent.id === eventToUpdate.id
      );

      if (beforeEventIndex > -1) {
        console.log(beforeEventIndex, resource, ' beforeEventIndex, resource');
        if (resource === googleCalendarResource) {
          console.log(
            eventToUpdate.id,
            beforeEventIndex,
            ' updatedEvent.id, beforeEventIndex, '
          );
          if (
            hostBufferTimes?.[beforeEventIndex]?.beforeEvent?.method ===
            'create'
          ) {
            console.log(
              eventToUpdate.id,
              beforeEventIndex,
              ' updatedEvent.id, beforeEventIndex, inside if (timeBlocking?.[beforeEventIndex]?.beforeEvent?.method === create)'
            );
            createPromises.push(
              postPlannerModifyEventInCalendar(
                eventToUpdate,
                eventToUpdate.userId,
                'create',
                resource,
                true, // isTimeBlocking for buffer events
                clientType,
                remindersObjectForEvent?.reminders, // Pass reminders if any
                undefined, // Attendees for buffer events? Usually none.
                undefined // Conference for buffer events? Usually none.
              ) as Promise<CreateGoogleEventResponseType>
            );

            eventToUpdate.method = null;

            if (remindersObjectForEvent?.reminders?.length > 0) {
              insertReminderObjects.push(...remindersObjectForEvent.reminders);
            }

            const oldPreferredTimeRanges =
              await listPreferredTimeRangesForEvent(eventToUpdate.id);
            if (
              !_.isEqual(
                oldPreferredTimeRanges,
                eventToUpdate.preferredTimeRanges
              )
            ) {
              if (oldPreferredTimeRanges?.length > 0) {
                deletePreferredTimeRangeObjects.push(...oldPreferredTimeRanges);
              }

              if (eventToUpdate?.preferredTimeRanges?.length > 0) {
                insertPreferredTimeRangeObjects.push(
                  ...eventToUpdate.preferredTimeRanges
                );
              }
            }
          } else if (
            hostBufferTimes?.[beforeEventIndex]?.beforeEvent?.method ===
            'update'
          ) {
            const oldEventToUpdate = filteredAllEvents?.find(
              (e) => e?.id === eventToUpdate?.id
            );

            if (!eventToUpdate?.modifiable && oldEventToUpdate?.id) {
              eventToUpdate.startDate = oldEventToUpdate.startDate;
              eventToUpdate.endDate = oldEventToUpdate.endDate;
              eventToUpdate.timezone = oldEventToUpdate.timezone;
            }

            updatePromises.push(
              postPlannerModifyEventInCalendar(
                eventToUpdate,
                eventToUpdate?.userId,
                'update',
                resource,
                true, // isTimeBlocking for buffer events
                clientType,
                remindersObjectForEvent?.reminders, // Pass reminders if any
                undefined, // Attendees
                undefined // Conference
              ) as Promise<string>
            );

            if (remindersObjectForEvent?.reminders?.length > 0) {
              const oldReminders = await listRemindersForEvent(
                eventToUpdate?.id,
                eventToUpdate?.userId
              );
              if (oldReminders?.length > 0) {
                deleteReminders.push(...oldReminders);
              }
              insertReminderObjects.push(...remindersObjectForEvent.reminders);
            }

            const oldPreferredTimeRanges =
              await listPreferredTimeRangesForEvent(eventToUpdate.id);
            if (
              !_.isEqual(
                oldPreferredTimeRanges,
                eventToUpdate.preferredTimeRanges
              )
            ) {
              if (oldPreferredTimeRanges?.length > 0) {
                deletePreferredTimeRangeObjects.push(...oldPreferredTimeRanges);
              }

              if (eventToUpdate?.preferredTimeRanges?.length > 0) {
                insertPreferredTimeRangeObjects.push(
                  ...eventToUpdate.preferredTimeRanges
                );
              }
            }
          }
        }

        eventsToUpsert.push(eventToUpdate);
      } else if (afterEventIndex > -1) {
        console.log(afterEventIndex, resource, ' afterEventIndex, resource');
        if (resource === googleCalendarResource) {
          if (
            hostBufferTimes?.[afterEventIndex]?.afterEvent?.method === 'create'
          ) {
            createPromises.push(
              postPlannerModifyEventInCalendar(
                eventToUpdate,
                eventToUpdate.userId,
                'create',
                resource,
                true, // isTimeBlocking for buffer events
                clientType,
                undefined, // Reminders for buffer events?
                undefined, // Attendees
                undefined // Conference
              ) as Promise<CreateGoogleEventResponseType>
            );

            eventToUpdate.method = null;

            if (remindersObjectForEvent?.reminders?.length > 0) {
              insertReminderObjects.push(...remindersObjectForEvent.reminders);
            }

            const oldPreferredTimeRanges =
              await listPreferredTimeRangesForEvent(eventToUpdate.id);
            if (
              !_.isEqual(
                oldPreferredTimeRanges,
                eventToUpdate.preferredTimeRanges
              )
            ) {
              if (oldPreferredTimeRanges?.length > 0) {
                deletePreferredTimeRangeObjects.push(...oldPreferredTimeRanges);
              }

              if (eventToUpdate?.preferredTimeRanges?.length > 0) {
                insertPreferredTimeRangeObjects.push(
                  ...eventToUpdate.preferredTimeRanges
                );
              }
            }
          } else if (
            hostBufferTimes?.[afterEventIndex]?.afterEvent?.method === 'update'
          ) {
            const oldEventToUpdate = filteredAllEvents?.find(
              (e) => e?.id === eventToUpdate?.id
            );

            if (!eventToUpdate?.modifiable && oldEventToUpdate?.id) {
              eventToUpdate.startDate = oldEventToUpdate.startDate;
              eventToUpdate.endDate = oldEventToUpdate.endDate;
              eventToUpdate.timezone = oldEventToUpdate.timezone;
            }

            updatePromises.push(
              postPlannerModifyEventInCalendar(
                eventToUpdate,
                eventToUpdate?.userId,
                'update',
                resource,
                true, // isTimeBlocking for buffer events
                clientType,
                undefined, // Reminders
                undefined, // Attendees
                undefined // Conference
              ) as Promise<string>
            );

            if (remindersObjectForEvent?.reminders?.length > 0) {
              const oldReminders = await listRemindersForEvent(
                eventToUpdate?.id,
                eventToUpdate?.userId
              );
              if (oldReminders?.length > 0) {
                deleteReminders.push(...oldReminders);
              }
              insertReminderObjects.push(...remindersObjectForEvent.reminders);
            }

            const oldPreferredTimeRanges =
              await listPreferredTimeRangesForEvent(eventToUpdate.id);
            if (
              !_.isEqual(
                oldPreferredTimeRanges,
                eventToUpdate.preferredTimeRanges
              )
            ) {
              if (oldPreferredTimeRanges?.length > 0) {
                deletePreferredTimeRangeObjects.push(...oldPreferredTimeRanges);
              }

              if (eventToUpdate?.preferredTimeRanges?.length > 0) {
                insertPreferredTimeRangeObjects.push(
                  ...eventToUpdate.preferredTimeRanges
                );
              }
            }
          }
        }

        eventsToUpsert.push(eventToUpdate);
      } else if (breakIndex > -1) {
        console.log(
          breakIndex,
          breaks?.[breakIndex]?.method,
          resource,
          ' breakIndex, breaks?.[breakIndex]?.method, resource'
        );
        if (resource === googleCalendarResource) {
          if (breaks?.[breakIndex]?.method === 'create') {
            createPromises.push(
              postPlannerModifyEventInCalendar(
                eventToUpdate,
                eventToUpdate.userId,
                'create',
                resource,
                false, // Not a break event itself
                clientType,
                remindersObjectForEvent?.reminders, // Pass reminders if any
                undefined, // Attendees
                undefined // Conference
              ) as Promise<CreateGoogleEventResponseType>
            );

            eventToUpdate.method = null;

            if (remindersObjectForEvent?.reminders?.length > 0) {
              insertReminderObjects.push(...remindersObjectForEvent.reminders);
            }

            const oldPreferredTimeRanges =
              await listPreferredTimeRangesForEvent(eventToUpdate.id);
            if (
              !_.isEqual(
                oldPreferredTimeRanges,
                eventToUpdate.preferredTimeRanges
              )
            ) {
              if (oldPreferredTimeRanges?.length > 0) {
                deletePreferredTimeRangeObjects.push(...oldPreferredTimeRanges);
              }

              if (eventToUpdate?.preferredTimeRanges?.length > 0) {
                insertPreferredTimeRangeObjects.push(
                  ...eventToUpdate.preferredTimeRanges
                );
              }
            }

            breaks[breakIndex].method = null;
          } else if (breaks?.[breakIndex]?.method === 'update') {
            const oldEventToUpdate = filteredAllEvents?.find(
              (e) => e?.id === eventToUpdate?.id
            );

            if (!eventToUpdate?.modifiable && oldEventToUpdate?.id) {
              eventToUpdate.startDate = oldEventToUpdate.startDate;
              eventToUpdate.endDate = oldEventToUpdate.endDate;
              eventToUpdate.timezone = oldEventToUpdate.timezone;
            }

            updatePromises.push(
              postPlannerModifyEventInCalendar(
                eventToUpdate,
                eventToUpdate.userId,
                'update',
                resource,
                false, // Not a break event
                clientType,
                remindersObjectForEvent?.reminders, // Pass reminders if any
                undefined, // Attendees
                undefined // Conference
              ) as Promise<string>
            );

            if (remindersObjectForEvent?.reminders?.length > 0) {
              const oldReminders = await listRemindersForEvent(
                eventToUpdate?.id,
                eventToUpdate?.userId
              );
              if (oldReminders?.length > 0) {
                deleteReminders.push(...oldReminders);
              }

              insertReminderObjects.push(...remindersObjectForEvent.reminders);
            }

            const oldPreferredTimeRanges =
              await listPreferredTimeRangesForEvent(eventToUpdate.id);
            if (
              !_.isEqual(
                oldPreferredTimeRanges,
                eventToUpdate.preferredTimeRanges
              )
            ) {
              if (oldPreferredTimeRanges?.length > 0) {
                deletePreferredTimeRangeObjects.push(...oldPreferredTimeRanges);
              }

              if (eventToUpdate?.preferredTimeRanges?.length > 0) {
                insertPreferredTimeRangeObjects.push(
                  ...eventToUpdate.preferredTimeRanges
                );
              }
            }

            breaks[breakIndex].method = null;
          }
        }
        eventsToUpsert.push(eventToUpdate);
      } else {
        if (resource === googleCalendarResource) {
          console.log(
            eventToUpdate,
            ' updatedEvent inside else inside const updatedEvent of updatedEvents inside updateAllCalendarEventsPostPlanner'
          );
          if (eventToUpdate?.method === 'create') {
            if (eventToUpdate?.meetingId) {
              const meetingAssist = await getMeetingAssist(
                eventToUpdate?.meetingId
              );

              if (meetingAssist?.userId !== eventToUpdate?.userId) {
                eventsToRemove.push(eventToUpdate);
                console.log(meetingAssist?.userId, ' meetingAssist?.userId');
                console.log(eventToUpdate?.userId, ' eventToUpdate?.userId');

                console.log(
                  eventToUpdate?.id,
                  'event with meetingAssist not host continue'
                );

                continue;
              } else if (meetingAssist?.userId === eventToUpdate?.userId) {
                console.log(
                  'get attendees called inside method create updateAllCalendarEventsPostPlanner'
                );
                const attendees =
                  await listMeetingAssistAttendeesGivenMeetingId(
                    eventToUpdate?.meetingId
                  );
                console.log(
                  attendees,
                  ' attendees inside method create updateAllCalendarEventsPostPlanner'
                );
                let conference: ConferenceType | {} = {};

                if (meetingAssist?.enableConference) {
                  console.log(
                    meetingAssist?.enableConference,
                    ' meetingAssist?.enableConference'
                  );
                  const zoomToken = await getZoomAPIToken(
                    meetingAssist?.userId
                  );

                  conference = zoomToken
                    ? {}
                    : {
                        id: uuid(),
                        userId: meetingAssist?.userId,
                        calendarId: eventToUpdate?.calendarId,
                        app: 'google',
                        name: eventToUpdate?.summary,
                        notes: eventToUpdate?.notes,
                        updatedAt: dayjs().format(),
                        createdDate: dayjs().format(),
                        deleted: false,
                        isHost: true,
                      };

                  console.log(conference, ' conference before if (zoomToken)');

                  if (zoomToken) {
                    console.log(zoomToken, ' zoomToken inside if (zoomToken)');
                    const hostAttendee = attendees?.find(
                      (a) => a?.userId === meetingAssist?.userId
                    );

                    console.log(
                      hostAttendee,
                      ' hostAttendee inside if (zoomToken)'
                    );

                    const zoomObject = await createZoomMeeting(
                      zoomToken,
                      eventToUpdate?.startDate,
                      meetingAssist?.timezone,
                      eventToUpdate?.summary,
                      meetingAssist?.duration,
                      hostAttendee?.name,
                      hostAttendee?.primaryEmail,
                      attendees?.map((a) => a?.primaryEmail)
                    );

                    console.log(
                      zoomObject,
                      ' zoomObject after createZoomMeeting'
                    );

                    if (zoomObject) {
                      conference = {
                        id: `${zoomObject?.id}`,
                        userId: eventToUpdate?.userId,
                        calendarId: eventToUpdate?.calendarId,
                        app: 'zoom',
                        name: zoomObject?.agenda,
                        notes: zoomObject?.agenda,
                        joinUrl: zoomObject?.join_url,
                        startUrl: zoomObject?.start_url,
                        isHost: true,
                        updatedAt: dayjs().format(),
                        createdDate: dayjs().format(),
                        deleted: false,
                        entryPoints: [
                          {
                            entryPointType: 'video',
                            label: zoomObject?.join_url,
                            password: zoomObject?.password,
                            uri: zoomObject?.join_url,
                          },
                        ],
                      } as ConferenceType;

                      eventToFilterForUpdateConferences.push(eventToUpdate);
                    }
                  }
                }

                console.log(
                  conference,
                  ' conference before createPromises postPlannerModifyEventInCalendar'
                );

                if (meetingAssist?.lockAfter) {
                  eventToUpdate.modifiable = false;
                }

                createPromises.push(
                  postPlannerModifyEventInCalendar(
                    eventToUpdate,
                    eventToUpdate.userId,
                    'create',
                    resource,
                    false,
                    clientType,
                    undefined,
                    attendees,
                    (conference as ConferenceType)?.id
                      ? (conference as ConferenceType)
                      : undefined
                  ) as Promise<CreateGoogleEventResponseType>
                );

                if ((conference as ConferenceType)?.id) {
                  await insertConference(conference as ConferenceType);
                  eventToUpdate.conferenceId = (
                    conference as ConferenceType
                  )?.id;
                }

                if (remindersObjectForEvent?.reminders?.length > 0) {
                  insertReminderObjects.push(
                    ...remindersObjectForEvent?.reminders
                  );
                }

                if (eventToUpdate?.preferredTimeRanges?.length > 0) {
                  insertPreferredTimeRangeObjects.push(
                    ...eventToUpdate.preferredTimeRanges
                  );
                }

                const attendeesToBeInsert: AttendeeType[] = attendees?.map(
                  (a) => ({
                    id: a?.id,
                    userId: a?.userId,
                    contactId: a?.contactId,
                    emails: a?.emails,
                    phoneNumbers: a?.phoneNumbers,
                    imAddresses: a?.imAddresses,
                    eventId: eventToUpdate?.id,
                    updatedAt: dayjs().format(),
                    createdDate: dayjs().format(),
                    deleted: false,
                  })
                );

                insertAttendeeObjects.push(...attendeesToBeInsert);

                const externalAttendees = attendees?.filter(
                  (a) => !!a?.externalAttendee
                );
                if ((conference as ConferenceType)?.id) {
                  eventsToBeCreatedWithNewId
                    ?.filter((c) => !!c)
                    ?.forEach((c) => {
                      const externalIndex = externalAttendees?.findIndex(
                        (e) => e?.userId === c?.event?.userId
                      );

                      if (
                        c?.meetingId === meetingAssist?.id &&
                        externalIndex === -1
                      ) {
                        c.conference = conference as ConferenceType;
                      }
                    });
                }

                eventsToBeCreatedWithNewId
                  ?.filter((c) => !!c)
                  ?.forEach((c) => {
                    const externalIndex = externalAttendees?.findIndex(
                      (e) => e?.userId === c?.event?.userId
                    );

                    if (
                      c?.meetingId === meetingAssist?.id &&
                      externalIndex === -1
                    ) {
                      c.attendees = attendees;
                      c.event.method = null;
                      c.resource = resource;
                      c.clientType = clientType;
                    }
                  });
              }
            }

            eventToUpdate.method = null;
          } else {
            const oldEventToUpdate = filteredAllEvents?.find(
              (e) => e?.id === eventToUpdate?.id
            );

            if (!eventToUpdate?.modifiable && oldEventToUpdate?.id) {
              eventToUpdate.startDate = oldEventToUpdate.startDate;
              eventToUpdate.endDate = oldEventToUpdate.endDate;
              eventToUpdate.timezone = oldEventToUpdate.timezone;
            }

            updatePromises.push(
              postPlannerModifyEventInCalendar(
                eventToUpdate,
                eventToUpdate.userId,
                'update',
                resource,
                false,
                clientType,
                remindersObjectForEvent?.reminders
              ) as Promise<string>
            );

            eventToUpdate.method = null;

            if (remindersObjectForEvent?.reminders?.length > 0) {
              const oldReminders = await listRemindersForEvent(
                eventToUpdate?.id,
                eventToUpdate?.userId
              );
              if (oldReminders?.length > 0) {
                deleteReminders.push(...oldReminders);
              }
              insertReminderObjects.push(...remindersObjectForEvent?.reminders);
            }

            const oldPreferredTimeRanges =
              await listPreferredTimeRangesForEvent(eventToUpdate.id);
            if (
              !_.isEqual(
                oldPreferredTimeRanges,
                eventToUpdate.preferredTimeRanges
              )
            ) {
              if (oldPreferredTimeRanges?.length > 0) {
                deletePreferredTimeRangeObjects.push(...oldPreferredTimeRanges);
              }

              if (eventToUpdate?.preferredTimeRanges?.length > 0) {
                insertPreferredTimeRangeObjects.push(
                  ...eventToUpdate.preferredTimeRanges
                );
              }
            }
          }
        }

        eventsToUpsert.push(eventToUpdate);
      }
    }

    const idResponseBodies = await Promise.all(createPromises);

    const cloneEventsToUpsert = _.cloneDeep(eventsToUpsert);

    const eventsToEdit: EventPlusType[] = [];

    const idModifiedEventsToUpsert: EventPlusType[] = eventsToUpsert.map(
      (e1) => {
        const idResponseBody = idResponseBodies?.find(
          (r) => r.generatedId === e1.id
        );
        if (idResponseBody?.id) {
          const generatedIdEditIndex = eventsToEdit?.findIndex(
            (e) => e?.id === e1?.id
          );

          const newIdEditIndex = eventsToEdit?.findIndex(
            (e) => e?.id === idResponseBody?.id
          );

          console.log(
            generatedIdEditIndex,
            newIdEditIndex,
            ' generatedIdEditIndex, newIdEditIndex'
          );

          if (generatedIdEditIndex > -1 || newIdEditIndex > -1) {
            if (generatedIdEditIndex > -1) {
              const genIdEditedEvent = eventsToEdit[generatedIdEditIndex];

              console.log(
                genIdEditedEvent,
                idResponseBody,
                ' genIdEditedEvent, idResponseBody inside generatedIdEditIndex > -1'
              );

              genIdEditedEvent.id = idResponseBody?.id;
              genIdEditedEvent.eventId = idResponseBody?.googleEventId;

              if (genIdEditedEvent?.preEventId) {
                console.log(
                  genIdEditedEvent?.preEventId,
                  ' genIdEditedEvent?.preEventId'
                );

                const clonePreEvent = cloneEventsToUpsert.find(
                  (e2) => e2.id === genIdEditedEvent.preEventId
                );

                if (clonePreEvent?.id) {
                  console.log(
                    clonePreEvent?.id,
                    ' clonePreEvent?.id inside genIdEditedEvent?.preEventId inside generatedIdEditIndex > -1'
                  );
                  clonePreEvent.forEventId = idResponseBody.id;

                  const genIdOfPreEventIndex = eventsToEdit?.findIndex(
                    (e) => e?.id === genIdEditedEvent.preEventId
                  );
                  const newIdOfPreEventResponseBody = idResponseBodies?.find(
                    (c) => c?.generatedId === genIdEditedEvent.preEventId
                  );

                  if (newIdOfPreEventResponseBody?.id) {
                    clonePreEvent.id = newIdOfPreEventResponseBody?.id;
                    clonePreEvent.eventId =
                      newIdOfPreEventResponseBody?.googleEventId;

                    const newIdOfPreEventIndex = eventsToEdit?.findIndex(
                      (e) => e?.id === newIdOfPreEventResponseBody?.id
                    );

                    if (genIdOfPreEventIndex > -1) {
                      console.log(
                        genIdOfPreEventIndex,
                        ' inside genIdOfPreEventIndex > -1 '
                      );
                      eventsToEdit[genIdOfPreEventIndex].forEventId =
                        idResponseBody.id;
                      eventsToEdit[genIdOfPreEventIndex].id =
                        newIdOfPreEventResponseBody?.id;
                      eventsToEdit[genIdOfPreEventIndex].eventId =
                        newIdOfPreEventResponseBody?.googleEventId;
                    } else if (newIdOfPreEventIndex > -1) {
                      console.log(
                        newIdOfPreEventIndex,
                        ' newIdOfPreEventIndex > -1'
                      );
                      eventsToEdit[newIdOfPreEventIndex].forEventId =
                        idResponseBody.id;
                    } else {
                      eventsToEdit.push(clonePreEvent);
                    }
                  }
                }
              }

              if (genIdEditedEvent?.postEventId) {
                console.log(
                  genIdEditedEvent?.postEventId,
                  ' genIdEditedEvent?.postEventId'
                );
                const clonePostEvent = cloneEventsToUpsert.find(
                  (e2) => e2.id === genIdEditedEvent.postEventId
                );

                if (clonePostEvent?.id) {
                  console.log(clonePostEvent?.id, ' clonePostEvent?.id');
                  clonePostEvent.forEventId = idResponseBody.id;

                  const genIdOfPostEventIndex = eventsToEdit?.findIndex(
                    (e) => e?.id === genIdEditedEvent.postEventId
                  );
                  const newIdOfPostEventResponseBody = idResponseBodies?.find(
                    (c) => c?.generatedId === genIdEditedEvent.postEventId
                  );

                  if (newIdOfPostEventResponseBody?.id) {
                    clonePostEvent.id = newIdOfPostEventResponseBody?.id;
                    clonePostEvent.eventId =
                      newIdOfPostEventResponseBody?.googleEventId;

                    const newIdOfPostEventIndex = eventsToEdit?.findIndex(
                      (e) =>
                        e?.id ===
                        `${newIdOfPostEventResponseBody}#${clonePostEvent.calendarId}`
                    );

                    if (genIdOfPostEventIndex > -1) {
                      console.log(
                        genIdOfPostEventIndex,
                        ' genIdOfPostEventIndex > -1'
                      );
                      eventsToEdit[genIdOfPostEventIndex].forEventId =
                        idResponseBody.id;
                      eventsToEdit[genIdOfPostEventIndex].id =
                        newIdOfPostEventResponseBody?.id;
                      eventsToEdit[genIdOfPostEventIndex].eventId =
                        newIdOfPostEventResponseBody?.googleEventId;
                    } else if (newIdOfPostEventIndex > -1) {
                      console.log(
                        newIdOfPostEventIndex,
                        ' newIdOfPostEventIndex > -1'
                      );
                      eventsToEdit[newIdOfPostEventIndex].forEventId =
                        idResponseBody.id;
                    } else {
                      eventsToEdit.push(clonePostEvent);
                    }
                  }
                }
              }

              if (genIdEditedEvent?.forEventId) {
                if (genIdEditedEvent?.isPreEvent) {
                  console.log(
                    genIdEditedEvent?.isPreEvent,
                    ' genIdEditedEvent?.isPreEvent inside genIdEditedEvent?.forEventId'
                  );
                  const forEvent = cloneEventsToUpsert.find(
                    (e2) => e2.id === genIdEditedEvent.forEventId
                  );

                  if (forEvent?.id) {
                    console.log(
                      forEvent?.id,
                      ' forEvent?.id inside genIdEditedEvent?.forEventId'
                    );
                    forEvent.preEventId = idResponseBody.id;
                    const genIdOfForEventIndex = eventsToEdit?.findIndex(
                      (e) => e?.id === forEvent?.id
                    );
                    const newIdOfForEventResponseBody = idResponseBodies?.find(
                      (c) => c?.generatedId === forEvent?.id
                    );

                    if (newIdOfForEventResponseBody?.id) {
                      forEvent.id = newIdOfForEventResponseBody?.id;
                      forEvent.eventId =
                        newIdOfForEventResponseBody?.googleEventId;

                      const newIdOfForEventIndex = eventsToEdit?.findIndex(
                        (e) => e?.id === newIdOfForEventResponseBody?.id
                      );

                      if (genIdOfForEventIndex > -1) {
                        console.log(
                          genIdOfForEventIndex,
                          ' genIdOfForEventIndex > -1'
                        );
                        eventsToEdit[genIdOfForEventIndex].preEventId =
                          idResponseBody.id;
                        eventsToEdit[genIdOfForEventIndex].id =
                          newIdOfForEventResponseBody?.id;
                        eventsToEdit[genIdOfForEventIndex].eventId =
                          newIdOfForEventResponseBody?.googleEventId;
                      } else if (newIdOfForEventIndex > -1) {
                        console.log(
                          newIdOfForEventIndex,
                          ' newIdOfEventIndex > -1'
                        );
                        eventsToEdit[newIdOfForEventIndex].preEventId =
                          idResponseBody.id;
                      } else {
                        eventsToEdit.push(forEvent);
                      }
                    }
                  }
                } else if (genIdEditedEvent?.isPostEvent) {
                  console.log(
                    genIdEditedEvent?.isPostEvent,
                    ' genIdEditedEvent?.isPostEvent'
                  );
                  const forEvent = cloneEventsToUpsert.find(
                    (e2) => e2.id === genIdEditedEvent.forEventId
                  );
                  if (forEvent?.id) {
                    console.log(forEvent?.id, ' forEvent?.id');
                    forEvent.postEventId = idResponseBody.id;
                    const genIdOfForEventIndex = eventsToEdit?.findIndex(
                      (e) => e?.id === forEvent?.id
                    );
                    const newIdOfForEventResponseBody = idResponseBodies?.find(
                      (c) => c?.generatedId === forEvent?.id
                    );

                    if (newIdOfForEventResponseBody?.id) {
                      const newIdOfForEventIndex = eventsToEdit?.findIndex(
                        (e) => e?.id === newIdOfForEventResponseBody?.id
                      );

                      if (genIdOfForEventIndex > -1) {
                        console.log(
                          genIdOfForEventIndex,
                          ' genIdOfForEventIndex > -1 inside genIdEditedEvent?.isPostEvent'
                        );
                        eventsToEdit[genIdOfForEventIndex].postEventId =
                          idResponseBody.id;
                        eventsToEdit[genIdOfForEventIndex].id =
                          newIdOfForEventResponseBody?.id;
                        eventsToEdit[genIdOfForEventIndex].eventId =
                          newIdOfForEventResponseBody?.googleEventId;
                      } else if (newIdOfForEventIndex > -1) {
                        console.log(
                          newIdOfForEventIndex > -1,
                          ' newIdOfForEventIndex > -1 inside genIdEditedEvent?.isPostEvent'
                        );
                        eventsToEdit[newIdOfForEventIndex].postEventId =
                          idResponseBody.id;
                      } else {
                        eventsToEdit.push(forEvent);
                      }
                    }
                  }
                }
              }

              for (const pt of insertPreferredTimeRangeObjects) {
                if (pt?.eventId === e1.id) {
                  pt.eventId = idResponseBody?.id;
                }
              }

              for (const r of insertReminderObjects) {
                if (r?.eventId === e1.id) {
                  r.eventId = idResponseBody?.id;
                }
              }

              for (const a of insertAttendeeObjects) {
                if (a?.eventId === e1.id) {
                  a.eventId = idResponseBody?.id;
                }
              }

              if (e1?.meetingId) {
                eventsToBeCreatedWithNewId
                  ?.filter((c) => c?.meetingId === e1?.meetingId)
                  ?.filter((c) => !!c?.event?.id)
                  ?.forEach((c) => {
                    console.log(
                      c.event,
                      idResponseBody,
                      genIdEditedEvent,
                      ' c.event, createdEvent, editedEvent inside editedEvent inside generatedEventsToEditIndex'
                    );
                    c.event.id = `${idResponseBody?.googleEventId}#${c.event.calendarId}`;
                    c.event.eventId = idResponseBody?.googleEventId;
                  });
              }
            } else if (newIdEditIndex > -1) {
              const newIdWithEditedEvent = eventsToEdit[newIdEditIndex];
              console.log(newIdWithEditedEvent, ' newIdWithEditedEvent');

              if (newIdWithEditedEvent?.preEventId) {
                console.log(
                  newIdWithEditedEvent?.preEventId,
                  ' newIdWithEditedEvent?.preEventId'
                );

                const clonePreEvent = cloneEventsToUpsert.find(
                  (e2) => e2.id === newIdWithEditedEvent.preEventId
                );
                const genIdOrNewIdWithPreEventEditedEvent = eventsToEdit?.find(
                  (e3) => e3.id === newIdWithEditedEvent?.preEventId
                );

                if (genIdOrNewIdWithPreEventEditedEvent?.id) {
                  console.log(
                    genIdOrNewIdWithPreEventEditedEvent,
                    ' genIdOrNewIdWithPreEventEditedEvent inside newIdWithEditedEvent?.preEventId inside newIdWithEditedEvent'
                  );

                  genIdOrNewIdWithPreEventEditedEvent.forEventId =
                    idResponseBody.id;

                  const preEventWithNewIdResponseBody = idResponseBodies?.find(
                    (i) =>
                      i.generatedId === genIdOrNewIdWithPreEventEditedEvent?.id
                  );

                  if (preEventWithNewIdResponseBody?.id) {
                    genIdOrNewIdWithPreEventEditedEvent.id =
                      preEventWithNewIdResponseBody?.id;
                    genIdOrNewIdWithPreEventEditedEvent.eventId =
                      preEventWithNewIdResponseBody.googleEventId;
                  }
                }

                if (clonePreEvent?.id) {
                  console.log(
                    clonePreEvent?.id,
                    ' clonePreEvent?.id inside newIdWithEditedEvent?.preEventId'
                  );
                  clonePreEvent.forEventId = idResponseBody.id;

                  const genIdWithPreEventIndex = eventsToEdit?.findIndex(
                    (e) => e?.id === newIdWithEditedEvent.preEventId
                  );
                  const newIdWithPreEventResponseBody = idResponseBodies?.find(
                    (c) => c?.generatedId === newIdWithEditedEvent.preEventId
                  );

                  if (newIdWithPreEventResponseBody?.id) {
                    clonePreEvent.id = newIdWithPreEventResponseBody?.id;
                    clonePreEvent.eventId =
                      newIdWithPreEventResponseBody?.googleEventId;

                    const newIdWithPreEventIndex = eventsToEdit?.findIndex(
                      (e) => e?.id === newIdWithPreEventResponseBody?.id
                    );

                    if (genIdWithPreEventIndex > -1) {
                      console.log(
                        genIdWithPreEventIndex,
                        ' genIdWithPreEventIndex > -1 inside clonePreEvent?.id inside newIdWithEditedEvent?.preEventId'
                      );
                      eventsToEdit[genIdWithPreEventIndex].forEventId =
                        idResponseBody.id;
                      eventsToEdit[genIdWithPreEventIndex].id =
                        newIdWithPreEventResponseBody?.id;
                      eventsToEdit[genIdWithPreEventIndex].eventId =
                        newIdWithPreEventResponseBody?.googleEventId;
                    } else if (newIdWithPreEventIndex > -1) {
                      console.log(
                        newIdWithPreEventIndex,
                        ' newIdWithPreEventIndex > -1 inside clonePreEvent?.id inside newIdWithEditedEvent?.preEventId'
                      );
                      eventsToEdit[newIdWithPreEventIndex].forEventId =
                        idResponseBody.id;
                    } else {
                      eventsToEdit.push(clonePreEvent);
                    }
                  }
                }
              }

              if (newIdWithEditedEvent?.postEventId) {
                const clonePostEvent = cloneEventsToUpsert?.find(
                  (e2) => e2.id === newIdWithEditedEvent.postEventId
                );

                const genIdOrNewIdWithPostEventEditedEvent = eventsToEdit?.find(
                  (e3) => e3.id === newIdWithEditedEvent?.postEventId
                );

                if (genIdOrNewIdWithPostEventEditedEvent?.id) {
                  console.log(
                    genIdOrNewIdWithPostEventEditedEvent,
                    ' genIdOrNewIdWithPostEventEditedEvent inside newIdWithEditedEvent?.postEventId inside newIdWithEditedEvent'
                  );

                  genIdOrNewIdWithPostEventEditedEvent.forEventId =
                    idResponseBody.id;

                  const postEventWithNewIdResponseBody = idResponseBodies?.find(
                    (i) =>
                      i.generatedId === genIdOrNewIdWithPostEventEditedEvent?.id
                  );

                  if (postEventWithNewIdResponseBody?.id) {
                    genIdOrNewIdWithPostEventEditedEvent.id =
                      postEventWithNewIdResponseBody?.id;
                    genIdOrNewIdWithPostEventEditedEvent.eventId =
                      postEventWithNewIdResponseBody.googleEventId;
                  }
                }

                if (clonePostEvent?.id) {
                  clonePostEvent.forEventId = newIdWithEditedEvent.id;

                  const genIdWithPostEventIndex = eventsToEdit?.findIndex(
                    (e) => e?.id === newIdWithEditedEvent.postEventId
                  );
                  const newIdWithPostEventResponseBody = idResponseBodies?.find(
                    (c) => c?.generatedId === newIdWithEditedEvent.postEventId
                  );

                  if (newIdWithPostEventResponseBody?.id) {
                    clonePostEvent.id = newIdWithPostEventResponseBody?.id;
                    clonePostEvent.eventId =
                      newIdWithPostEventResponseBody?.googleEventId;

                    const eventsToEditPostEventWithCreateIdIndex =
                      eventsToEdit?.findIndex(
                        (e) =>
                          e?.id ===
                          `${newIdWithPostEventResponseBody}#${clonePostEvent.calendarId}`
                      );

                    if (genIdWithPostEventIndex > -1) {
                      eventsToEdit[genIdWithPostEventIndex].forEventId =
                        newIdWithEditedEvent.id;
                      eventsToEdit[genIdWithPostEventIndex].id =
                        newIdWithPostEventResponseBody?.id;
                      eventsToEdit[genIdWithPostEventIndex].eventId =
                        newIdWithPostEventResponseBody?.googleEventId;
                    } else if (eventsToEditPostEventWithCreateIdIndex > -1) {
                      eventsToEdit[
                        eventsToEditPostEventWithCreateIdIndex
                      ].forEventId = newIdWithEditedEvent.id;
                    } else {
                      eventsToEdit.push(clonePostEvent);
                    }
                  }
                }
              }

              if (newIdWithEditedEvent?.forEventId) {
                console.log(
                  newIdWithEditedEvent?.forEventId,
                  ' newIdWithEditedEvent?.forEventId'
                );
                if (newIdWithEditedEvent?.isPreEvent) {
                  console.log(
                    newIdWithEditedEvent?.isPreEvent,
                    ' newIdWithEditedEvent?.isPreEvent inside newIdWithEditedEvent?.forEventId'
                  );
                  const forEvent = cloneEventsToUpsert.find(
                    (e2) => e2.id === newIdWithEditedEvent.forEventId
                  );

                  if (forEvent?.id) {
                    console.log(forEvent?.id, ' forEvent?.id');

                    forEvent.preEventId = newIdWithEditedEvent.id;
                    const genIdOfForEventIndex = eventsToEdit?.findIndex(
                      (e) => e?.id === forEvent?.id
                    );
                    const newIdOfForEventResponseBody = idResponseBodies?.find(
                      (c) => c?.generatedId === forEvent?.id
                    );

                    if (newIdOfForEventResponseBody?.id) {
                      forEvent.id = newIdOfForEventResponseBody?.id;
                      forEvent.eventId =
                        newIdOfForEventResponseBody?.googleEventId;

                      const newIdOfForEventIndex = eventsToEdit?.findIndex(
                        (e) => e?.id === newIdOfForEventResponseBody?.id
                      );
                      if (genIdOfForEventIndex > -1) {
                        console.log(
                          genIdOfForEventIndex,
                          ' genIdOfForEventIndex > -1'
                        );
                        eventsToEdit[genIdOfForEventIndex].preEventId =
                          idResponseBody.id;
                        eventsToEdit[genIdOfForEventIndex].id =
                          newIdOfForEventResponseBody?.id;
                        eventsToEdit[genIdOfForEventIndex].eventId =
                          newIdOfForEventResponseBody?.googleEventId;
                      } else if (newIdOfForEventIndex > -1) {
                        console.log(
                          newIdOfForEventIndex,
                          ' newIdOfForEventIndex > -1'
                        );
                        eventsToEdit[newIdOfForEventIndex].preEventId =
                          idResponseBody.id;
                      } else {
                        eventsToEdit.push(forEvent);
                      }
                    }
                  }
                } else if (newIdWithEditedEvent?.isPostEvent) {
                  const forEvent = cloneEventsToUpsert?.find(
                    (e2) => e2.id === newIdWithEditedEvent.forEventId
                  );
                  if (forEvent?.id) {
                    console.log(
                      forEvent?.id,
                      ' forEvent?.id inside newIdWithEditedEvent?.isPostEvent'
                    );
                    forEvent.postEventId = idResponseBody.id;
                    const genIdOfForEventIndex = eventsToEdit?.findIndex(
                      (e) => e?.id === forEvent?.id
                    );
                    const newIdOfForEventResponseBody = idResponseBodies?.find(
                      (c) => c?.generatedId === forEvent?.id
                    );

                    if (newIdOfForEventResponseBody?.id) {
                      const newIdOfForEventIndex = eventsToEdit?.findIndex(
                        (e) => e?.id === newIdOfForEventResponseBody?.id
                      );

                      if (genIdOfForEventIndex > -1) {
                        console.log(
                          genIdOfForEventIndex,
                          ' genIdOfForEventIndex > -1 inside forEvent?.id inside newIdWithEditedEvent?.isPostEvent'
                        );
                        eventsToEdit[genIdOfForEventIndex].postEventId =
                          idResponseBody.id;
                        eventsToEdit[genIdOfForEventIndex].id =
                          newIdOfForEventResponseBody?.id;
                        eventsToEdit[genIdOfForEventIndex].eventId =
                          newIdOfForEventResponseBody?.googleEventId;
                      } else if (newIdOfForEventIndex > -1) {
                        eventsToEdit[newIdOfForEventIndex].postEventId =
                          idResponseBody.id;
                      } else {
                        eventsToEdit.push(forEvent);
                      }
                    }
                  }
                }
              }

              insertPreferredTimeRangeObjects?.forEach((pt) => {
                if (pt?.eventId === e1.id) {
                  pt.eventId = idResponseBody?.id;
                }
              });

              insertReminderObjects?.forEach((r) => {
                if (r?.eventId === e1.id) {
                  r.eventId = idResponseBody?.id;
                }
              });

              if (e1?.meetingId) {
                eventsToBeCreatedWithNewId
                  ?.filter((c) => c?.meetingId === e1?.meetingId)
                  ?.filter((c) => !!c?.event?.id)
                  ?.forEach((c) => {
                    console.log(
                      c.event,
                      idResponseBody,
                      newIdWithEditedEvent,
                      ' c.event, createdEvent, createdAndEditedEvent, inside forEach inside createdEventToEditIndex'
                    );
                    c.event.id = `${idResponseBody.googleEventId}#${c?.event?.calendarId}`;
                    c.event.eventId = idResponseBody?.googleEventId;
                  });
              }
            }
          } else {
            const cloneEvent = cloneEventsToUpsert?.find(
              (e2) => e2?.id === e1?.id
            );

            if (cloneEvent?.id) {
              cloneEvent.id = idResponseBody?.id;
              cloneEvent.eventId = idResponseBody?.googleEventId;

              if (cloneEvent?.preEventId) {
                console.log(
                  cloneEvent?.preEventId,
                  ' cloneEvent?.preEventId inside else'
                );
                const clonePreEvent = cloneEventsToUpsert.find(
                  (e2) => e2.id === cloneEvent.preEventId
                );

                if (clonePreEvent?.id) {
                  console.log(
                    clonePreEvent?.id,
                    ' clonePreEvent?.id inside cloneEvent?.preEventId inside else'
                  );
                  clonePreEvent.forEventId = idResponseBody.id;

                  const genIdOfPreEventIndex = eventsToEdit?.findIndex(
                    (e) => e?.id === cloneEvent.preEventId
                  );
                  const newIdOfPreEventResponseBody = idResponseBodies?.find(
                    (c) => c?.generatedId === cloneEvent.preEventId
                  );

                  if (newIdOfPreEventResponseBody?.id) {
                    clonePreEvent.id = newIdOfPreEventResponseBody?.id;
                    clonePreEvent.eventId =
                      newIdOfPreEventResponseBody?.googleEventId;

                    const newIdOfPreEventIndex = eventsToEdit?.findIndex(
                      (e) => e?.id === newIdOfPreEventResponseBody?.id
                    );

                    if (genIdOfPreEventIndex > -1) {
                      console.log(
                        genIdOfPreEventIndex,
                        ' inside genIdOfPreEventIndex > -1 clonePreEvent?.id inside cloneEvent?.preEventId inside else'
                      );
                      eventsToEdit[genIdOfPreEventIndex].forEventId =
                        idResponseBody.id;
                      eventsToEdit[genIdOfPreEventIndex].id =
                        newIdOfPreEventResponseBody?.id;
                      eventsToEdit[genIdOfPreEventIndex].eventId =
                        newIdOfPreEventResponseBody?.googleEventId;
                    } else if (newIdOfPreEventIndex > -1) {
                      console.log(
                        newIdOfPreEventIndex,
                        ' newIdOfPreEventIndex > -1 inside genIdOfPreEventIndex > -1 clonePreEvent?.id inside cloneEvent?.preEventId inside else'
                      );
                      eventsToEdit[newIdOfPreEventIndex].forEventId =
                        idResponseBody.id;
                    } else {
                      eventsToEdit.push(clonePreEvent);
                    }
                  }
                }
              }

              if (cloneEvent?.postEventId) {
                console.log(
                  cloneEvent?.postEventId,
                  ' cloneEvent?.postEventId'
                );
                const clonePostEvent = cloneEventsToUpsert?.find(
                  (e2) => e2.id === cloneEvent.postEventId
                );

                if (clonePostEvent?.id) {
                  console.log(clonePostEvent?.id, ' clonePostEvent?.id');
                  clonePostEvent.forEventId = idResponseBody.id;

                  const genIdOfPostEventIndex = eventsToEdit?.findIndex(
                    (e) => e?.id === cloneEvent.postEventId
                  );
                  const newIdOfPostEventResponseBody = idResponseBodies?.find(
                    (c) => c?.generatedId === cloneEvent.postEventId
                  );

                  if (newIdOfPostEventResponseBody?.id) {
                    clonePostEvent.id = newIdOfPostEventResponseBody?.id;
                    clonePostEvent.eventId =
                      newIdOfPostEventResponseBody?.googleEventId;

                    const newIdOfPostEventIndex = eventsToEdit?.findIndex(
                      (e) => e?.id === newIdOfPostEventResponseBody?.id
                    );

                    if (genIdOfPostEventIndex > -1) {
                      console.log(
                        genIdOfPostEventIndex,
                        ' genIdOfPostEventIndex > -1'
                      );
                      eventsToEdit[genIdOfPostEventIndex].forEventId =
                        idResponseBody.id;
                      eventsToEdit[genIdOfPostEventIndex].id =
                        newIdOfPostEventResponseBody?.id;
                      eventsToEdit[genIdOfPostEventIndex].eventId =
                        newIdOfPostEventResponseBody?.googleEventId;
                    } else if (newIdOfPostEventIndex > -1) {
                      console.log(
                        newIdOfPostEventIndex,
                        ' newIdOfPostEventIndex > -1'
                      );
                      eventsToEdit[newIdOfPostEventIndex].forEventId =
                        idResponseBody.id;
                    } else {
                      eventsToEdit.push(clonePostEvent);
                    }
                  }
                }
              }

              eventsToEdit.push(cloneEvent);

              if (e1?.forEventId) {
                if (e1?.isPreEvent) {
                  console.log(
                    e1?.isPreEvent,
                    ' e1?.isPreEvent inside e1?.forEventId'
                  );
                  const forEvent = cloneEventsToUpsert?.find(
                    (e2) => e2.id === e1.forEventId
                  );

                  if (forEvent?.id) {
                    console.log(
                      forEvent?.id,
                      ' forEvent?.id inside genIdEditedEvent?.forEventId'
                    );
                    forEvent.preEventId = idResponseBody.id;
                    const genIdOfForEventIndex = eventsToEdit?.findIndex(
                      (e) => e?.id === forEvent?.id
                    );
                    const newIdOfForEventResponseBody = idResponseBodies?.find(
                      (c) => c?.generatedId === forEvent?.id
                    );

                    if (newIdOfForEventResponseBody?.id) {
                      forEvent.id = newIdOfForEventResponseBody?.id;
                      forEvent.eventId =
                        newIdOfForEventResponseBody?.googleEventId;

                      const newIdOfForEventIndex = eventsToEdit?.findIndex(
                        (e) => e?.id === newIdOfForEventResponseBody?.id
                      );

                      if (genIdOfForEventIndex > -1) {
                        console.log(
                          genIdOfForEventIndex,
                          ' genIdOfForEventIndex > -1'
                        );
                        eventsToEdit[genIdOfForEventIndex].preEventId =
                          idResponseBody.id;
                        eventsToEdit[genIdOfForEventIndex].id =
                          newIdOfForEventResponseBody?.id;
                        eventsToEdit[genIdOfForEventIndex].eventId =
                          newIdOfForEventResponseBody?.googleEventId;
                      } else if (newIdOfForEventIndex > -1) {
                        console.log(
                          newIdOfForEventIndex,
                          ' newIdOfForEventIndex > -1'
                        );
                        eventsToEdit[newIdOfForEventIndex].preEventId =
                          idResponseBody.id;
                      } else {
                        eventsToEdit.push(forEvent);
                      }
                    }
                  }
                } else if (e1?.isPostEvent) {
                  console.log(e1?.isPostEvent, ' e1?.isPostEvent');
                  const forEvent = cloneEventsToUpsert?.find(
                    (e2) => e2.id === e1.forEventId
                  );

                  if (forEvent?.id) {
                    console.log(
                      forEvent?.id,
                      ' forEvent?.id inside e1?.isPostEvent'
                    );
                    forEvent.postEventId = idResponseBody.id;
                    const genIdOfForEventIndex = eventsToEdit?.findIndex(
                      (e) => e?.id === forEvent?.id
                    );
                    const newIdOfForEventResponseBody = idResponseBodies?.find(
                      (c) => c?.generatedId === forEvent?.id
                    );

                    if (newIdOfForEventResponseBody?.id) {
                      const newIdOfForEventIndex = eventsToEdit?.findIndex(
                        (e) => e?.id === newIdOfForEventResponseBody?.id
                      );

                      if (genIdOfForEventIndex > -1) {
                        console.log(
                          genIdOfForEventIndex,
                          ' genIdOfForEventIndex > -1 inside e1?.isPostEvent inside e1?.isPostEvent'
                        );
                        eventsToEdit[genIdOfForEventIndex].postEventId =
                          idResponseBody.id;
                        eventsToEdit[genIdOfForEventIndex].id =
                          newIdOfForEventResponseBody?.id;
                        eventsToEdit[genIdOfForEventIndex].eventId =
                          newIdOfForEventResponseBody?.googleEventId;
                      } else if (newIdOfForEventIndex > -1) {
                        console.log(
                          newIdOfForEventIndex > -1,
                          ' newIdOfForEventIndex > -1 inside e1?.isPostEvent inside inside e1?.isPostEvent'
                        );
                        eventsToEdit[newIdOfForEventIndex].postEventId =
                          idResponseBody.id;
                      } else {
                        eventsToEdit.push(forEvent);
                      }
                    }
                  }
                }
              }

              insertPreferredTimeRangeObjects?.forEach((pt) => {
                if (pt?.eventId === e1.id) {
                  pt.eventId = idResponseBody?.id;
                }
              });

              insertReminderObjects?.forEach((r) => {
                if (r?.eventId === e1.id) {
                  r.eventId = idResponseBody?.id;
                }
              });

              if (e1?.meetingId) {
                eventsToBeCreatedWithNewId
                  ?.filter((c) => c?.meetingId === e1?.meetingId)
                  ?.filter((c) => !!c?.event?.id)
                  ?.forEach((c) => {
                    console.log(
                      c.event,
                      cloneEvent,
                      ' c.event, cloneEvent inside else '
                    );
                    c.event.id = `${idResponseBody.googleEventId}#${c?.event?.calendarId}`;
                    c.event.eventId = idResponseBody?.googleEventId;
                  });
              }
            }
          }

          eventsToRemove.push(e1);
          return e1;
        }

        return e1;
      }
    );

    const eventsWithMeetingAssistSinHost =
      eventsToBeCreatedWithNewId?.map((c) => c?.event) || [];

    eventsToEdit?.forEach((e) => console.log(e, ' eventsToEdit'));

    const eventsMinusEventsToRemove = _.differenceBy(
      idModifiedEventsToUpsert,
      eventsToRemove,
      'id'
    );

    const finalEventsToUpsert = eventsMinusEventsToRemove
      .concat(eventsWithMeetingAssistSinHost)
      .concat(_.uniqBy(eventsToEdit, 'id'))
      ?.filter((e) => !!e);

    finalEventsToUpsert?.forEach((e) => console.log(e, ' finalEventsToUpsert'));

    updatePromises?.forEach((e) =>
      console.log(e, ' updatePromises before filter')
    );

    await processEventsForUpdatingConferences(
      finalEventsToUpsert?.filter(
        (e) =>
          !eventToFilterForUpdateConferences?.find(
            (f) => e?.conferenceId === f?.conferenceId
          )
      )
    );

    await Promise.all([
      Promise.all(updatePromises?.filter((e) => !!e)),
      upsertEventsPostPlanner(
        finalEventsToUpsert.map((e) =>
          _.omit(e, ['vector', 'preferredTimeRanges'])
        )
      ),
    ]);

    for (const insertReminderObject of insertReminderObjects) {
      const idResponseBody = idResponseBodies?.find(
        (i) => i?.generatedId === insertReminderObject?.eventId
      );

      if (idResponseBody?.id) {
        insertReminderObject.eventId = idResponseBody?.id;
      }
    }

    for (const insertPreferredTimeRangeObject of insertPreferredTimeRangeObjects) {
      const idResponseBody = idResponseBodies?.find(
        (i) => i?.generatedId === insertPreferredTimeRangeObject?.eventId
      );

      if (idResponseBody?.id) {
        insertPreferredTimeRangeObject.eventId = idResponseBody?.id;
      }
    }

    for (const insertAttendeeObject of insertAttendeeObjects) {
      const idResponseBody = idResponseBodies?.find(
        (i) => i?.generatedId === insertAttendeeObject?.eventId
      );

      if (idResponseBody?.id) {
        insertAttendeeObject.eventId = idResponseBody?.id;
      }
    }

    deleteReminders.forEach((d) => console.log(d, ' deleteReminders'));
    insertReminderObjects?.forEach((i) =>
      console.log(i, ' insertReminderObjects')
    );
    const deleteReminderIds = deleteReminders
      .filter((r) => !!r?.eventId)
      ?.map((r) => r?.eventId);
    const insertRemindersFiltered: ReminderTypeAdjusted[] =
      insertReminderObjects.filter((r) => !!r?.eventId);

    deleteReminderIds.forEach((d) => console.log(d, ' deleteReminderIds'));
    insertRemindersFiltered.forEach((i) =>
      console.log(i, ' insertRemindersFiltered')
    );
    await deleteRemindersWithIds(
      _.uniq(deleteReminderIds),
      filteredEventsToUpdate?.[0]?.userId
    );
    await insertReminders(insertRemindersFiltered);
    const distinctToDeletePreferredTimeRangeObjects = _.uniqBy(
      deletePreferredTimeRangeObjects,
      'eventId'
    );
    const eventIdsForPts = distinctToDeletePreferredTimeRangeObjects?.map(
      (pt) => pt?.eventId
    );
    await deletePreferredTimeRangesForEvents(eventIdsForPts);
    await insertPreferredTimeRanges(insertPreferredTimeRangeObjects);
    await insertAttendeesforEvent(insertAttendeeObjects);
    console.log('success!');
  } catch (e) {
    console.log(e, ' unable to update ');
  }
};

export const deleteZoomMeeting = async (
  zoomToken: string,
  meetingId: number
) => {
  try {
    await got.delete(`${zoomBaseUrl}/meetings/${meetingId}`, {
      headers: {
        Authorization: `Bearer ${zoomToken}`,
        ContentType: 'application/json',
      },
    });

    console.log(meetingId, 'successfully deleted meeting');
  } catch (e) {
    console.log(e, ' unable to delete zoom meeting');
  }
};

export const getZoomMeeting = async (zoomToken: string, meetingId: number) => {
  try {
    const res: ZoomMeetingObjectType = await got(
      `${zoomBaseUrl}/meetings/${meetingId}`,
      {
        headers: {
          Authorization: `Bearer ${zoomToken}`,
          ContentType: 'application/json',
        },
      }
    ).json();

    return res;
  } catch (e) {
    console.log(e, ' unable to get zoom meeting');
  }
};

export const updateZoomMeetingStartDate = async (
  zoomToken: string,
  meetingId: number,
  startDate: string,
  timezone: string
) => {
  try {
    const reqBody = {
      start_time: dayjs(startDate?.slice(0, 19)).utc().format(),
      timezone,
    };

    await got
      .patch(`${zoomBaseUrl}/meetings/${meetingId}`, {
        json: reqBody,
        headers: {
          Authorization: `Bearer ${zoomToken}`,
          ContentType: 'application/json',
        },
      })
      .json();

    console.log(meetingId, 'successfully patched zoom meeting starting date');
  } catch (e) {
    console.log(e, ' unable to update zoom meeting');
  }
};

export const createZoomMeeting = async (
  zoomToken: string,
  startDate: string,
  timezone: string,
  agenda: string,
  duration: number,
  contactName?: string,
  contactEmail?: string,
  meetingInvitees?: string[]
) => {
  try {
    if (dayjs().isAfter(dayjs(startDate))) {
      console.log(' starttime is in the past');
      throw new Error('starttime is in the past');
    }

    console.log(
      dayjs(startDate?.slice(0, 19))
        .tz(timezone, true)
        .format('YYYY-MM-DDTHH:mm:ss'),
      timezone,
      agenda,
      duration,
      ` dayjs(startDate?.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DDTHH:mm:ss'),
            timezone,
            agenda,
            duration, createZoomMeeting called`
    );

    let settings: any = {};

    if (contactName?.length > 0 && contactEmail?.length > 0) {
      settings = {
        contact_name: contactName,
        contact_email: contactEmail,
      };
    }

    if (meetingInvitees?.length > 0) {
      settings = {
        ...settings,
        meeting_invitees: meetingInvitees?.map((m) => ({ email: m })),
      };
    }

    let reqBody: CreateZoomMeetingRequestBodyType = {};

    if (Object.keys(settings)?.length > 0) {
      reqBody.settings = settings;
    }

    reqBody = {
      ...reqBody,
      start_time: dayjs(startDate?.slice(0, 19))
        .tz(timezone, true)
        .utc()
        .format(),
      agenda,
      duration,
    };

    console.log(reqBody, ' reqBody inside createZoomMeeting');

    const res: ZoomMeetingObjectType = await got
      .post(`${zoomBaseUrl}/users/me/meetings`, {
        json: reqBody,
        headers: {
          Authorization: `Bearer ${zoomToken}`,
          ContentType: 'application/json',
        },
      })
      .json();

    console.log(res, ' res inside createZoomMeeting');

    return res;
  } catch (e) {
    console.log(e, ' unable to create zoom meeting');
  }
};

export const insertConferences = async (conferences: ConferenceType[]) => {
  try {
    const operationName = 'InsertConferences';
    const query = `
            mutation InsertConferences($conferences: [Conference_insert_input!]!) {
                insert_Conference(objects: $conferences) {
                    affected_rows
                    returning {
                        app
                        calendarId
                        createdDate
                        deleted
                        entryPoints
                        hangoutLink
                        iconUri
                        id
                        isHost
                        joinUrl
                        key
                        name
                        notes
                        parameters
                        requestId
                        startUrl
                        status
                        type
                        updatedAt
                        userId
                        zoomPrivateMeeting
                    }
                }
            }

        `;

    const variables = {
      conferences,
    };

    const res: {
      data: {
        insert_Conference: {
          affected_rows: number;
          returning: ConferenceType[];
        };
      };
    } = await got
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
      res?.data?.insert_Conference?.returning,
      ' successfully inserted conferences'
    );
  } catch (e) {
    console.log(e, ' unable to insert conferences');
  }
};

export const insertConference = async (conference: ConferenceType) => {
  try {
    const operationName = 'InsertConference';
    const query = `
            mutation InsertConference($conference: Conference_insert_input!) {
                insert_Conference_one(object: $conference) {
                    app
                    calendarId
                    createdDate
                    deleted
                    entryPoints
                    hangoutLink
                    iconUri
                    id
                    isHost
                    joinUrl
                    key
                    name
                    notes
                    parameters
                    requestId
                    startUrl
                    status
                    type
                    updatedAt
                    userId
                    zoomPrivateMeeting
                }
            }
        `;

    const variables = {
      conference,
    };

    const res: { data: { insert_Conference_one: ConferenceType } } = await got
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

    console.log(res, ' successfully inserted one conference');

    return res?.data?.insert_Conference_one;
  } catch (e) {
    console.log(e, ' unable to insert conference');
  }
};

export const listConferencesWithHosts = async (ids: string[]) => {
  try {
    const operationName = 'ListConferencesWithHostId';
    const query = `
            query ListConferencesWithHostId($ids: [String!]!) {
                Conference(where: {id: {_in: $ids}, isHost: {_eq: true}}) {
                    app
                    calendarId
                    createdDate
                    deleted
                    entryPoints
                    hangoutLink
                    iconUri
                    id
                    isHost
                    joinUrl
                    key
                    name
                    notes
                    parameters
                    requestId
                    startUrl
                    status
                    type
                    updatedAt
                    userId
                    zoomPrivateMeeting
                }
            }
        `;

    const variables = {
      ids,
    };

    const res: { data: { Conference: ConferenceType[] } } = await got
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

    console.log(res, ' successfully listed conferences with hosts');

    return res?.data?.Conference;
  } catch (e) {
    console.log(e, ' unable to list conferences with hosts');
  }
};

export const processEventsForUpdatingConferences = async (
  finalEventsToUpsert: EventPlusType[]
) => {
  try {
    const eventsWithConferences = finalEventsToUpsert.filter(
      (e) => !!e?.conferenceId
    );

    const conferenceIds = eventsWithConferences?.map((e) => e?.conferenceId);
    const conferencesWithHosts = await listConferencesWithHosts(conferenceIds);

    const eventsWithHostConferences = eventsWithConferences?.filter(
      (e) => !!conferencesWithHosts?.find((c) => c?.userId === e?.userId)
    );

    if (!eventsWithHostConferences?.[0]?.id) {
      console.log('no event with host conferences present');
      return;
    }

    for (const eventWithHostConference of eventsWithHostConferences) {
      const zoomToken = await getZoomAPIToken(eventWithHostConference?.userId);
      const conferenceToEvent = conferencesWithHosts?.find(
        (c) => c?.id === eventWithHostConference?.conferenceId
      );
      if (
        zoomToken &&
        conferenceToEvent?.app === 'zoom' &&
        typeof parseInt(conferenceToEvent?.id, 10) === 'number'
      ) {
        await updateZoomMeetingStartDate(
          zoomToken,
          parseInt(conferenceToEvent?.id, 10),
          eventWithHostConference?.startDate,
          eventWithHostConference?.timezone
        );
      }
    }
  } catch (e) {
    console.log(e, ' unable to processEventsforupdatingconferences');
  }
};

export const processEventsForCreatingConferences = async (
  finalEventsToUpsert: EventPlusType[],
  createResults: {
    id: string;
    generatedId: string;
  }[]
) => {
  try {
    const createdEventsWithMeetingId = finalEventsToUpsert
      ?.filter((e) => !!createResults?.find((c) => c?.id === e?.id))
      ?.filter((e) => !!e?.meetingId);

    const uniqueMeetingIdCreatedEvents = _.uniqBy(
      createdEventsWithMeetingId,
      'meetingId'
    );

    if (!uniqueMeetingIdCreatedEvents?.[0]) {
      console.log(' no new meeting events created');
      return;
    }
    const meetingAssistObjects = await listMeetingAssistsGivenMeetingIds(
      uniqueMeetingIdCreatedEvents?.map((e) => e?.meetingId)
    );

    const zoomObjects: (ZoomMeetingObjectType & {
      meetingId: string;
      hostId: string;
    })[] = [];

    for (const meetingAssist of meetingAssistObjects) {
      const zoomToken = await getZoomAPIToken(meetingAssist?.userId);

      if (zoomToken) {
        const meetingEvent = uniqueMeetingIdCreatedEvents?.find(
          (e) => e?.meetingId === meetingAssist?.id
        );
        if (!meetingEvent) {
          console.log(' not meetingEvent found for zoom continue');
          continue;
        }

        const attendees = await listMeetingAssistAttendeesGivenMeetingId(
          meetingEvent?.meetingId
        );

        if (!attendees) {
          console.log(' no attendees present for zoom continue');
          continue;
        }
        const hostAttendee = attendees?.find(
          (a) => a?.userId === meetingAssist?.userId
        );

        const zoomObject = await createZoomMeeting(
          zoomToken,
          meetingEvent?.startDate,
          meetingAssist?.timezone,
          meetingEvent?.summary,
          meetingAssist?.duration,
          hostAttendee?.name,
          hostAttendee?.primaryEmail,
          attendees?.map((a) => a?.primaryEmail)
        );

        zoomObjects.push({
          ...zoomObject,
          meetingId: meetingAssist?.id,
          hostId: meetingAssist?.userId,
        });

        console.log(
          zoomObject,
          ' zoomObject inside processEventsForCreatingConferences'
        );
      }
    }

    console.log(zoomObjects, ' zoomObjects');
    if (zoomObjects?.[0]?.id) {
      return zoomObjects;
    }
  } catch (e) {
    console.log(e, ' unable to create conferences');
  }
};

export const listMeetingAssistsGivenMeetingIds = async (
  meetingIds: string[]
) => {
  try {
    const operationName = 'ListMeetingAssists';
    const query = `
            query ListMeetingAssists($meetingIds: [uuid!]!) {
                Meeting_Assist(where: {id: {_in: $meetingIds}}) {
                    allowAttendeeUpdatePreferences
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
                    foregroundColor
                    guaranteeAvailability
                    guestsCanInviteOthers
                    guestsCanSeeOtherGuests
                    id
                    location
                    notes
                    minThresholdCount
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
                }
            }
        `;

    const variables = {
      meetingIds,
    };

    const res: { data: { Meeting_Assist: MeetingAssistType[] } } = await got
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

    console.log(res, ' successfully listed listMeetingAssistsGivenMeetingIds');

    return res?.data?.Meeting_Assist;
  } catch (e) {
    console.log(e, ' unable to list meeting assists');
  }
};
