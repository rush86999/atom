import {
  bucketName,
  optaplannerDuration,
  dayOfWeekIntToString,
  hasuraAdminSecret,
  hasuraGraphUrl,
  onOptaPlanCalendarAdminCallBackUrl,
  optaPlannerPassword,
  optaPlannerUrl,
  optaPlannerUsername,
} from '@schedule_assist/_libs/constants';
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
  BufferTimeObjectType,
  FetchedExternalPreference,
  NewConstraints,
} from '@schedule_assist/_libs/types'; // Added FetchedExternalPreference and NewConstraints
import got from 'got';
import { v4 as uuid } from 'uuid';
import dayjs from 'dayjs';

import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import _ from 'lodash';
import { PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
import { getISODay, setISODay } from 'date-fns';

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

  console.log(
    startDate,
    ' startDate inside generateNewMeetingEventForAttendee step 2'
  );

  if (preferredStartTimeRange?.startTime) {
    console.log(
      preferredStartTimeRange?.startTime,
      ' preferredStartTimeRange?.startTime'
    );
    const startTime = preferredStartTimeRange?.startTime;
    const hour = parseInt(startTime.slice(0, 2), 10);

    console.log(hour, ' hour');
    const minute = parseInt(startTime.slice(3), 10);

    console.log(minute, ' minute');

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

  console.log(newEvent, ' newEvent inside generateNewMeetingEventForAttendee');
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
  userPreferences: UserPreferenceType,
  timezone: string
): EventPlusType[] => {
  if (!allEvents?.[0]?.id) {
    console.log('no allEvents inside adjustStartDatesForBreakEvents');
    return;
  }

  const startTimes = userPreferences.startTimes;
  const endTimes = userPreferences.endTimes;
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
  const breakLength =
    userPreferences.breakLength <= 15 ? 15 : userPreferences.breakLength;
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
          .subtract(breakLength, 'minute');
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

export const getEventDetailsForModification = async (
  hasuraEventId: string // Format: "googleEventId#calendarId"
): Promise<
  (EventType & { attendees?: MeetingAssistAttendeeType[] }) | null
> => {
  try {
    const operationName = 'GetEventWithAttendeesForModification';
    const query = `
            query ${operationName}($eventId: String!) {
                Event_by_pk(id: $eventId) {
                    id
                    userId
                    calendarId
                    eventId
                    summary
                    startDate
                    endDate
                    timezone
                    duration
                    notes
                    location
                    status
                    transparency
                    visibility
                    colorId
                    recurringEventId
                    allDay
                    recurrenceRule
                    attachments
                    links
                    createdDate
                    deleted
                    taskId
                    taskType
                    priority
                    followUpEventId
                    isFollowUp
                    isPreEvent
                    isPostEvent
                    preEventId
                    postEventId
                    modifiable
                    forEventId
                    conferenceId
                    maxAttendees
                    sendUpdates
                    anyoneCanAddSelf
                    guestsCanInviteOthers
                    guestsCanSeeOtherGuests
                    originalStartDate
                    originalAllDay
                    htmlLink
                    creator
                    organizer
                    endTimeUnspecified
                    recurrence
                    originalTimezone
                    attendeesOmitted
                    extendedProperties
                    hangoutLink
                    guestsCanModify
                    locked
                    source
                    eventType
                    privateCopy
                    backgroundColor
                    foregroundColor
                    useDefaultAlarms
                    iCalUID

                    Attendees {
                        id
                        userId
                        contactId
                        name
                        primaryEmail
                        emails
                        timezone
                        externalAttendee
                        hostId
                        meetingId
                    }
                }
            }
        `;

    const variables = {
      eventId: hasuraEventId,
    };

    const response: {
      data: {
        Event_by_pk: EventType & { Attendees?: MeetingAssistAttendeeType[] };
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
        responseType: 'json',
      })
      .json();

    if ((response as any)?.errors) {
      console.error(
        `Hasura error fetching event ${hasuraEventId} for modification:`,
        JSON.stringify((response as any).errors, null, 2)
      );
      return null;
    }

    const eventData = response.data.Event_by_pk;
    if (eventData) {
      if (eventData.Attendees) {
        eventData.attendees = eventData.Attendees;
        delete (eventData as any).Attendees;
      } else {
        eventData.attendees = [];
      }
      return eventData;
    }
    return null;
  } catch (error) {
    console.error(
      `Error in getEventDetailsForModification for event ${hasuraEventId}:`,
      error
    );
    return null;
  }
};

export function generateEventPartsForReplan(
  allUserEvents: EventPlusType[], // All events for all relevant users
  eventToReplanHasuraId: string, // e.g., "googleEventId#calendarId"
  replanConstraints: NewConstraints,
  hostId: string, // Typically originalEventDetails.userId
  hostTimezone: string // To resolve event part start/end for OptaPlanner if needed by formatEventType...
): InitialEventPartTypePlus[] {
  const allEventParts: InitialEventPartTypePlus[] = [];

  for (const event of allUserEvents) {
    // Ensure preferredTimeRanges is at least an empty array for InitialEventPartTypePlus
    const eventWithPrefs: EventPlusType = {
      ...event,
      preferredTimeRanges: event.preferredTimeRanges || [],
    };

    let parts = generateEventPartsLite(eventWithPrefs, hostId); // Returns InitialEventPartType[]

    if (event.id === eventToReplanHasuraId) {
      // This is the event being replanned
      const newDuration = replanConstraints.newDurationMinutes;
      if (newDuration && newDuration > 0) {
        const originalEventStartDate = dayjs(event.startDate.slice(0, 19)).tz(
          event.timezone || hostTimezone,
          true
        );
        const newEventEndDate = originalEventStartDate.add(
          newDuration,
          'minutes'
        );

        // Create a temporary event with the new duration to generate parts
        const tempEventForNewDuration: EventPlusType = {
          ...eventWithPrefs,
          endDate: newEventEndDate.format(), // Ensure correct format
        };
        parts = generateEventPartsLite(tempEventForNewDuration, hostId);
      }

      parts = parts.map((p) => ({
        ...p,
        modifiable: true,
        // Add empty preferredTimeRanges if not present, to satisfy InitialEventPartTypePlus
        preferredTimeRanges:
          (p as InitialEventPartTypePlus).preferredTimeRanges || [],
      }));
    } else {
      // This is not the event being replanned, so pin it
      parts = parts.map((p) => {
        const initialPartPlus: InitialEventPartTypePlus = {
          ...p,
          modifiable: false,
          // Add empty preferredTimeRanges if not present
          preferredTimeRanges:
            (p as InitialEventPartTypePlus).preferredTimeRanges || [],
        };

        // Apply pinning logic similar to setPreferredTimeForUnModifiableEvent
        // This function expects EventPartPlannerRequestBodyType, so we adapt its logic here for InitialEventPartTypePlus
        if (
          !initialPartPlus.preferredDayOfWeek &&
          !initialPartPlus.preferredTime
        ) {
          const partStartDate = dayjs(
            initialPartPlus.startDate.slice(0, 19)
          ).tz(initialPartPlus.timezone || hostTimezone, true);
          initialPartPlus.preferredDayOfWeek = getISODay(
            partStartDate.toDate()
          ) as any; // May need dayOfWeekIntToString conversion if type mismatch
          initialPartPlus.preferredTime = partStartDate.format(
            'HH:mm:ss'
          ) as Time;
        }
        return initialPartPlus;
      });
    }
    allEventParts.push(...parts);
  }
  return allEventParts;
}

export async function generateTimeSlotsForReplan(
  users: MeetingAssistAttendeeType[], // Final list of users for the replanned event
  replanConstraints: NewConstraints,
  hostTimezone: string,
  globalDefaultWindowStart: string, // Fallback window start (ISO string)
  globalDefaultWindowEnd: string, // Fallback window end (ISO string)
  mainHostId: string, // Needed by generateTimeSlotsLiteForInternalAttendee
  userPreferencesCache: Map<string, UserPreferenceType> // Cache to avoid re-fetching
): Promise<TimeSlotType[]> {
  const allTimeSlots: TimeSlotType[] = [];

  const effectiveWindowStartUTC =
    replanConstraints.newTimeWindowStartUTC || globalDefaultWindowStart;
  const effectiveWindowEndUTC =
    replanConstraints.newTimeWindowEndUTC || globalDefaultWindowEnd;

  // Convert effective UTC window to hostTimezone for generating slots locally if needed,
  // or ensure downstream functions correctly handle UTC or convert to hostTimezone.
  // For generateTimeSlotsLiteForInternalAttendee, it expects hostStartDate in hostTimezone.
  const effectiveWindowStartInHostTz = dayjs
    .utc(effectiveWindowStartUTC)
    .tz(hostTimezone)
    .format();
  const effectiveWindowEndInHostTz = dayjs
    .utc(effectiveWindowEndUTC)
    .tz(hostTimezone)
    .format();

  const diffDays = dayjs(effectiveWindowEndInHostTz).diff(
    dayjs(effectiveWindowStartInHostTz),
    'day'
  );
  const startDatesForEachDayInWindow: string[] = [];
  for (let i = 0; i <= diffDays; i++) {
    startDatesForEachDayInWindow.push(
      dayjs(effectiveWindowStartInHostTz).add(i, 'day').format()
    );
  }

  for (const user of users) {
    let userPrefs = userPreferencesCache.get(user.userId);
    if (!userPrefs) {
      userPrefs = await getUserPreferences(user.userId);
      if (userPrefs) {
        userPreferencesCache.set(user.userId, userPrefs);
      } else {
        // Handle case where user preferences might not be found for a user
        console.warn(
          `Preferences not found for user ${user.userId}, skipping timeslot generation for them.`
        );
        continue;
      }
    }

    // Assuming generateTimeSlotsLiteForInternalAttendee is the primary one.
    // If external users have a different slot generation mechanism, that would need to be called here.
    // The generateTimeSlotsLiteForInternalAttendee expects hostStartDate for each day.
    for (let i = 0; i < startDatesForEachDayInWindow.length; i++) {
      const dayToGenerateSlots = startDatesForEachDayInWindow[i];
      const isFirstDayLoop = i === 0;

      // Ensure the date being passed to generateTimeSlotsLiteForInternalAttendee is correctly formatted and in hostTimezone.
      // The loop already generates dates in hostTimezone based on effectiveWindowStartInHostTz
      const userSpecificSlots = generateTimeSlotsLiteForInternalAttendee(
        dayToGenerateSlots, // This is already a date string in hostTimezone
        mainHostId, // Or user.hostId if appropriate, mainHostId seems more aligned with OptaPlanner's model
        userPrefs,
        hostTimezone, // Host's overall timezone
        user.timezone || hostTimezone, // Attendee's specific timezone
        isFirstDayLoop
      );
      allTimeSlots.push(...userSpecificSlots);
    }
  }

  return _.uniqWith(allTimeSlots, _.isEqual);
}

export async function orchestrateReplanOptaPlannerInput(
  userId: string, // User initiating the replan (usually the host)
  hostTimezone: string,
  originalEventDetails: EventType & {
    attendees?: MeetingAssistAttendeeType[];
    meetingId?: string;
  },
  newConstraints: NewConstraints,
  allUsersFromOriginalEventAndAdded: MeetingAssistAttendeeType[], // Combined list of original and newly added attendees
  allExistingEventsForUsers: EventPlusType[] // Pre-fetched events for ALL relevant users in a broad window
  // client: any, // ApolloClient, if needed - currently using global got for Hasura
): Promise<PlannerRequestBodyType | null> {
  try {
    const singletonId = uuid();
    const eventToReplanHasuraId = originalEventDetails.id; // googleEventId#calendarId

    // 1. Generate Event Parts
    // Host ID for event parts is typically the user ID from the original event
    const eventParts = generateEventPartsForReplan(
      allExistingEventsForUsers,
      eventToReplanHasuraId,
      newConstraints,
      originalEventDetails.userId,
      hostTimezone
    );

    if (!eventParts || eventParts.length === 0) {
      console.error('No event parts generated for replan. Aborting.');
      return null;
    }

    // 2. Generate Time Slots
    // Use a cache for user preferences within this function's scope
    const userPreferencesCache = new Map<string, UserPreferenceType>();

    // Define global fallback window (e.g., next 7 days from original event start if no new window specified)
    // These should be ISO datetime strings
    const originalEventStartDayjs = dayjs(
      originalEventDetails.startDate.slice(0, 19)
    ).tz(originalEventDetails.timezone || hostTimezone, true);
    const globalDefaultWindowStart =
      newConstraints.newTimeWindowStartUTC ||
      originalEventStartDayjs.toISOString();
    const globalDefaultWindowEnd =
      newConstraints.newTimeWindowEndUTC ||
      originalEventStartDayjs.add(7, 'days').toISOString();

    const timeSlots = await generateTimeSlotsForReplan(
      allUsersFromOriginalEventAndAdded,
      newConstraints,
      hostTimezone,
      globalDefaultWindowStart,
      globalDefaultWindowEnd,
      originalEventDetails.userId, // mainHostId for timeslot generation context
      userPreferencesCache
    );

    if (!timeSlots || timeSlots.length === 0) {
      console.error('No time slots generated for replan. Aborting.');
      return null;
    }

    // 3. Construct User List (UserPlannerRequestBodyType)
    const userListForPlanner: UserPlannerRequestBodyType[] = [];
    for (const user of allUsersFromOriginalEventAndAdded) {
      let userPrefs = userPreferencesCache.get(user.userId);
      if (!userPrefs) {
        userPrefs = await getUserPreferences(user.userId);
        if (userPrefs) {
          userPreferencesCache.set(user.userId, userPrefs);
        } else {
          console.warn(
            `Preferences not found for user ${user.userId} while building userListForPlanner. Using defaults.`
          );
          // Provide default/minimal UserPreferenceType if none found
          userPrefs = {
            id: uuid(), // temp id
            userId: user.userId,
            maxWorkLoadPercent: 100, // Default values
            backToBackMeetings: false,
            maxNumberOfMeetings: 99,
            minNumberOfBreaks: 0,
            startTimes: [], // Default empty start/end times
            endTimes: [],
            breakLength: 30,
            // Add other mandatory fields from UserPreferenceType with defaults
            deleted: false,
          } as UserPreferenceType;
        }
      }

      const workTimes = user.externalAttendee
        ? generateWorkTimesForExternalAttendee(
            originalEventDetails.userId, // hostId context
            user.userId,
            allExistingEventsForUsers.filter((e) => e.userId === user.userId), // Pass only this user's events
            hostTimezone,
            user.timezone || hostTimezone
          )
        : generateWorkTimesForInternalAttendee(
            originalEventDetails.userId, // hostId context
            user.userId,
            userPrefs,
            hostTimezone,
            user.timezone || hostTimezone
          );

      userListForPlanner.push(
        user.externalAttendee
          ? generateUserPlannerRequestBodyForExternalAttendee(
              user.userId,
              workTimes,
              originalEventDetails.userId
            )
          : generateUserPlannerRequestBody(
              userPrefs,
              user.userId,
              workTimes,
              originalEventDetails.userId
            )
      );
    }

    const uniqueUserListForPlanner = _.uniqBy(userListForPlanner, 'id');

    // 4. Assemble PlannerRequestBodyType
    const fileKey = `${originalEventDetails.userId}/${singletonId}_REPLAN_${originalEventDetails.eventId}.json`;

    const plannerRequestBody: PlannerRequestBodyType = {
      singletonId,
      hostId: originalEventDetails.userId,
      timeslots: _.uniqWith(timeSlots, _.isEqual),
      userList: uniqueUserListForPlanner,
      // Event parts need to be correctly formatted as EventPartPlannerRequestBodyType
      // The generateEventPartsForReplan returns InitialEventPartTypePlus[]
      // We need to map these to EventPartPlannerRequestBodyType, similar to how processEventsForOptaPlanner does.
      // This requires userPreferences for each event part's user.
      eventParts: eventParts
        .map((ep) => {
          const partUser = allUsersFromOriginalEventAndAdded.find(
            (u) => u.userId === ep.userId
          );
          let partUserPrefs = userPreferencesCache.get(ep.userId);
          if (!partUserPrefs) {
            // This should ideally not happen if all users in eventParts are in allUsersFromOriginalEventAndAdded
            // and their prefs were fetched for userList. Adding a fallback.
            console.warn(
              `Prefs not in cache for user ${ep.userId} during event part formatting. Using defaults.`
            );
            partUserPrefs = {
              /* ... default UserPreferenceType ... */
            } as UserPreferenceType;
          }

          const partWorkTimes = partUser?.externalAttendee
            ? generateWorkTimesForExternalAttendee(
                originalEventDetails.userId,
                ep.userId,
                allExistingEventsForUsers.filter((e) => e.userId === ep.userId),
                hostTimezone,
                partUser?.timezone || hostTimezone
              )
            : generateWorkTimesForInternalAttendee(
                originalEventDetails.userId,
                ep.userId,
                partUserPrefs,
                hostTimezone,
                partUser?.timezone || hostTimezone
              );

          return partUser?.externalAttendee
            ? formatEventTypeToPlannerEventForExternalAttendee(
                ep,
                partWorkTimes,
                allExistingEventsForUsers.filter((e) => e.userId === ep.userId),
                hostTimezone
              )
            : formatEventTypeToPlannerEvent(
                ep,
                partUserPrefs,
                partWorkTimes,
                hostTimezone
              );
        })
        .filter((ep) => ep !== null), // Filter out nulls if allDay events were skipped
      fileKey,
      delay: optaplannerDuration, // from constants
      callBackUrl: onOptaPlanCalendarAdminCallBackUrl, // from constants
    };

    // Filter out any null event parts that might result from allDay events etc.
    plannerRequestBody.eventParts = plannerRequestBody.eventParts.filter(
      (ep) => ep != null
    );

    if (
      !plannerRequestBody.eventParts ||
      plannerRequestBody.eventParts.length === 0
    ) {
      console.error(
        'No valid event parts to send to OptaPlanner after formatting. Aborting.'
      );
      return null;
    }

    // 5. S3 Upload
    const s3UploadParams = {
      Body: JSON.stringify({
        // Storing the input to OptaPlanner for debugging/history
        singletonId: plannerRequestBody.singletonId,
        hostId: plannerRequestBody.hostId,
        eventParts: plannerRequestBody.eventParts, // These are now EventPartPlannerRequestBodyType
        allEvents: allExistingEventsForUsers, // For context
        // Include any other relevant data for debugging the replan request
        originalEventDetails,
        newConstraints,
        finalUserListForPlanner: uniqueUserListForPlanner,
        finalTimeSlots: timeSlots,
        isReplan: true,
        originalGoogleEventId: originalEventDetails.eventId, // Assuming eventId is googleEventId here
        originalCalendarId: originalEventDetails.calendarId,
      }),
      Bucket: bucketName, // from constants
      Key: fileKey,
      ContentType: 'application/json',
    };
    const s3Command = new PutObjectCommand(s3UploadParams);
    await s3Client.send(s3Command);
    console.log(`Successfully uploaded replan input to S3: ${fileKey}`);

    // 6. Call optaPlanWeekly
    await optaPlanWeekly(
      plannerRequestBody.timeslots,
      plannerRequestBody.userList,
      plannerRequestBody.eventParts,
      plannerRequestBody.singletonId,
      plannerRequestBody.hostId,
      plannerRequestBody.fileKey,
      plannerRequestBody.delay,
      plannerRequestBody.callBackUrl
    );
    console.log(
      `OptaPlanner replan task initiated for singletonId: ${singletonId}`
    );

    return plannerRequestBody;
  } catch (error) {
    console.error(
      `Error in orchestrateReplanOptaPlannerInput for event ${originalEventDetails.id}:`,
      error
    );
    return null;
  }
}

// New function to list external attendee preferences
export const listExternalAttendeePreferences = async (
  // client: any, // Not needed as got is used directly with global config
  meetingAssistId: string,
  meetingAssistAttendeeId: string
): Promise<FetchedExternalPreference[]> => {
  try {
    const operationName = 'ListExternalAttendeePreferences';
    const query = `
            query ListExternalAttendeePreferences($meetingAssistId: uuid!, $meetingAssistAttendeeId: uuid!) {
                Meeting_Assist_External_Attendee_Preference(
                    where: {
                        meeting_assist_id: {_eq: $meetingAssistId},
                        meeting_assist_attendee_id: {_eq: $meetingAssistAttendeeId}
                    },
                    order_by: {preferred_start_datetime: asc}
                ) {
                    preferred_start_datetime
                    preferred_end_datetime
                }
            }
        `;

    const variables = {
      meetingAssistId,
      meetingAssistAttendeeId,
    };

    const res: {
      data: {
        Meeting_Assist_External_Attendee_Preference: FetchedExternalPreference[];
      };
    } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin', // Or appropriate role
        },
        json: {
          operationName,
          query,
          variables,
        },
        responseType: 'json', // Ensure got parses the response as JSON
      })
      .json();

    // Check for GraphQL errors in the response body
    if ((res as any)?.errors) {
      console.error(
        'Hasura errors while fetching external preferences:',
        JSON.stringify((res as any).errors, null, 2)
      );
      throw new Error(
        `Hasura request failed: ${(res as any).errors[0].message}`
      );
    }

    return res?.data?.Meeting_Assist_External_Attendee_Preference || [];
  } catch (e) {
    // Log the error caught by the try-catch block
    console.error(
      'Error fetching external attendee preferences (catch block):',
      e
    );
    return []; // Return empty array on error
  }
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
    console.log(
      hostStartDate,
      ' hostStartDate inside firstday inside generatetimeslotsforinternalattendee'
    );
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
    console.log(
      dayOfMonthByHost,
      ' dayOfMonthByHost inside generateTimeSlotsForInternalAttendees'
    );
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
      meetingPart: i + 1,
      meetingLastPart: remainder > 0 ? parts + 1 : parts,
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
      meetingPart: parts + 1,
      meetingLastPart: parts + 1,
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
  console.log(event, ' event before generateEventPartsLite');
  console.log(
    event.id,
    event.startDate.slice(0, 19),
    event.endDate.slice(0, 19),
    ' event.id, event.startDate.slice(0, 19), event.endDate.slice(0, 19) inside generateEventPartsLite'
  );
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
      meetingPart: i + 1,
      meetingLastPart: remainder > 0 ? parts + 1 : parts,
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
      meetingPart: parts + 1,
      meetingLastPart: parts + 1,
    });
  }
  console.log(eventParts, ' eventParts inside generateEventPartsLite');
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
      (dayjs(startDate?.slice(0, 19))
        .tz(timezone)
        .hour(parseInt(positiveImpactTime.slice(0, 2), 10))
        .minute(parseInt(positiveImpactTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time)) ||
    undefined;

  const adjustedNegativeImpactTime =
    (negativeImpactTime &&
      (dayjs(startDate?.slice(0, 19))
        .tz(timezone)
        .hour(parseInt(negativeImpactTime.slice(0, 2), 10))
        .minute(parseInt(negativeImpactTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time)) ||
    undefined;

  const adjustedPreferredTime =
    (preferredTime &&
      (dayjs(startDate?.slice(0, 19))
        .tz(timezone)
        .hour(parseInt(preferredTime.slice(0, 2), 10))
        .minute(parseInt(preferredTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time)) ||
    undefined;

  const adjustedPreferredStartTimeRange =
    (preferredStartTimeRange &&
      (dayjs(startDate?.slice(0, 19))
        .tz(timezone)
        .hour(parseInt(preferredStartTimeRange.slice(0, 2), 10))
        .minute(parseInt(preferredStartTimeRange.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time)) ||
    undefined;

  const adjustedPreferredEndTimeRange =
    (preferredEndTimeRange &&
      (dayjs(startDate?.slice(0, 19))
        .tz(timezone)
        .hour(parseInt(preferredEndTimeRange.slice(0, 2), 10))
        .minute(parseInt(preferredEndTimeRange.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time)) ||
    undefined;

  const adjustedPreferredTimeRanges =
    preferredTimeRanges?.map((e) => ({
      dayOfWeek: dayOfWeekIntToString?.[e?.dayOfWeek] ?? null,
      startTime: dayjs(startDate?.slice(0, 19))
        .tz(timezone)
        .hour(parseInt(e?.startTime.slice(0, 2), 10))
        .minute(parseInt(e?.startTime.slice(3), 10))
        .tz(hostTimezone)
        .format('HH:mm:ss') as Time,
      endTime: dayjs(startDate?.slice(0, 19))
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

    if (newBufferTimeArray?.length > 0) {
      modifiedAllHostEvents.push(...newBufferTimeArray);
    }

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
    if (formattedEventParts?.length > 0) {
      eventParts.push(...formattedEventParts);
    }

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
      modifiedAllEvents.push(
        ...newMeetingEvents?.map((m) =>
          convertMeetingPlusTypeToEventPlusType(m)
        )
      );
    }

    modifiedAllEvents?.forEach((e) => console.log(e, ' modifiedAllEvents'));

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

    globalPrimaryCalendars?.forEach((c) =>
      console.log(c, ' globalPrimaryCalendars')
    );

    const modifiedAllEventsWithBreaks: EventPlusType[] = [];

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
    // const minStartDate = _.minBy(sameDayEvents, (e) => dayjs(e.startDate.slice(0, 19)).tz(userTimezone, true).tz(hostTimezone).unix())
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
      for (let i = 0; i < totalMinutes; i += 15) {
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
          .format('HH:mm:ss') as Time,
        endTime: dayjs(hostStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .hour(startHourOfHostDateByHost)
          .minute(startMinuteOfHostDateByHost)
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
        .format('HH:mm:ss') as Time,
      endTime: dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(workStartHourByHost)
        .minute(workStartMinuteByHost)
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
  allExternalEvents: MeetingAssistEventType[], // These are MeetingAssistEvents from the user's calendar connection
  windowStartDate: string,
  windowEndDate: string,
  hostTimezone: string,
  externalAttendees: MeetingAssistAttendeeType[],
  oldExternalMeetingEvents?: EventMeetingPlusType[],
  newMeetingEvents?: EventMeetingPlusType[],
  meetingAssistId?: string // Added: ID of the current meeting assist for preference lookup
): Promise<ReturnBodyForExternalAttendeeForOptaplannerPrepType> => {
  try {
    // Convert MeetingAssistEventType to EventPlusType for consistent processing
    // These events are typically from the external user's own calendar, not specific meeting invites yet
    const baseExternalUserEvents = allExternalEvents?.map((e) =>
      convertMeetingAssistEventTypeToEventPlusType(
        e,
        externalAttendees?.find((a) => a?.id === e?.attendeeId)?.userId
      )
    );

    let modifiedAllExternalEvents = [...baseExternalUserEvents];

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
    // This `timeslots` variable will be the final one passed to OptaPlanner after processing all attendees
    const timeslots: TimeSlotType[] = [];

    for (const externalAttendee of externalAttendees) {
      const attendeeSpecificTimeslots: TimeSlotType[] = [];
      let useExplicitPreferences = false;

      if (meetingAssistId && externalAttendee.id) {
        const externalPreferences = await listExternalAttendeePreferences(
          meetingAssistId,
          externalAttendee.id
        );
        if (externalPreferences.length > 0) {
          useExplicitPreferences = true;
          for (const pref of externalPreferences) {
            let currentSlotStartTime = dayjs.utc(pref.preferred_start_datetime);
            const prefEndTime = dayjs.utc(pref.preferred_end_datetime);

            while (currentSlotStartTime.isBefore(prefEndTime)) {
              const currentSlotEndTime = currentSlotStartTime.add(30, 'minute');
              if (currentSlotEndTime.isAfter(prefEndTime)) {
                break;
              }

              const startTimeInHostTz = currentSlotStartTime.tz(hostTimezone);
              const endTimeInHostTz = currentSlotEndTime.tz(hostTimezone);

              const meetingWindowDayjsStart = dayjs(windowStartDate).tz(
                hostTimezone,
                true
              );
              const meetingWindowDayjsEnd = dayjs(windowEndDate).tz(
                hostTimezone,
                true
              );

              if (
                startTimeInHostTz.isBefore(meetingWindowDayjsStart) ||
                endTimeInHostTz.isAfter(meetingWindowDayjsEnd)
              ) {
                currentSlotStartTime = currentSlotEndTime;
                continue;
              }

              attendeeSpecificTimeslots.push({
                dayOfWeek:
                  dayOfWeekIntToString[
                    startTimeInHostTz.isoWeekday() as keyof typeof dayOfWeekIntToString
                  ],
                startTime: startTimeInHostTz.format('HH:mm:ss') as Time,
                endTime: endTimeInHostTz.format('HH:mm:ss') as Time,
                hostId: mainHostId,
                monthDay: formatToMonthDay(
                  startTimeInHostTz.month() as MonthType,
                  startTimeInHostTz.date() as DayType
                ),
                date: startTimeInHostTz.format('YYYY-MM-DD'),
                // userId: externalAttendee.userId, // Optional: if OptaPlanner needs this
              });
              currentSlotStartTime = currentSlotEndTime;
            }
          }
        }
      }

      if (!useExplicitPreferences) {
        // Fallback to existing logic: generate timeslots based on their general availability (e.g. synced calendar events)
        // The existing logic iterates through `startDatesForEachDay`
        for (let i = 0; i < startDatesForEachDay.length; i++) {
          const isFirstDayLoop = i === 0;
          // `modifiedAllExternalEvents` should be filtered for the specific `externalAttendee.userId` if not already
          const attendeeEventsForFallback = modifiedAllExternalEvents.filter(
            (evt) => evt.userId === externalAttendee.userId
          );
          const fallbackSlots = await generateTimeSlotsLiteForExternalAttendee(
            startDatesForEachDay[i],
            mainHostId,
            attendeeEventsForFallback, // Pass only this attendee's events
            hostTimezone,
            externalAttendee.timezone,
            isFirstDayLoop
          );
          attendeeSpecificTimeslots.push(...fallbackSlots);
        }
      }
      // Add this attendee's generated timeslots (either from prefs or fallback) to the main list
      unfilteredTimeslots.push(...attendeeSpecificTimeslots);
    }

    timeslots.push(..._.uniqWith(unfilteredTimeslots, _.isEqual)); // Ensure unique timeslots before sending to OptaPlanner
    console.log(timeslots, ' final timeslots for external attendees');

    // Note on WorkTimes: If explicit preferences are used, WorkTimeType generation might also need adjustment.
    // For this subtask, WorkTime generation remains based on existing logic (inferred from all events).
    // `workTimes` variable used in `formatEventTypeToPlannerEventForExternalAttendee` would be the place for this.

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
  newMeetingEventPlus: EventMeetingPlusType[],
  allEvents: EventPlusType[],
  windowStartDate: string,
  windowEndDate: string,
  hostTimezone: string,
  oldEvents: EventPlusType[],
  externalAttendees?: MeetingAssistAttendeeType[],
  meetingAssistEvents?: MeetingAssistEventType[],
  newHostReminders?: RemindersForEventType[],
  newHostBufferTimes?: BufferTimeObjectType[],
  isReplan?: boolean,
  eventBeingReplanned?: {
    originalEventId: string; // Hasura event ID: googleEventId#calendarId
    googleEventId: string;
    calendarId: string;
    newConstraints: NewConstraints;
    originalAttendees: MeetingAssistAttendeeType[];
  }
) => {
  try {
    let currentInternalAttendees = [...internalAttendees];
    let currentExternalAttendees = [...externalAttendees];

    console.log(
      windowStartDate,
      windowEndDate,
      ' windowStartDate, windowEndDate inside processEventsForOptaPlanner'
    );
    if (isReplan && eventBeingReplanned) {
      console.log(
        'Replanning event:',
        eventBeingReplanned.originalEventId,
        'with constraints:',
        eventBeingReplanned.newConstraints
      );

      let processedOriginalAttendees =
        eventBeingReplanned.originalAttendees.map((a) => ({
          ...a,
          primaryEmail:
            a.emails?.find((e) => e.primary)?.value ||
            a.emails?.[0]?.value ||
            a.primaryEmail,
        }));

      // Handle removed attendees
      if (
        eventBeingReplanned.newConstraints.removedAttendeeEmailsOrIds?.length >
        0
      ) {
        processedOriginalAttendees = processedOriginalAttendees.filter(
          (att) =>
            !eventBeingReplanned.newConstraints.removedAttendeeEmailsOrIds.includes(
              att.primaryEmail
            ) &&
            !eventBeingReplanned.newConstraints.removedAttendeeEmailsOrIds.includes(
              att.id
            ) &&
            !eventBeingReplanned.newConstraints.removedAttendeeEmailsOrIds.includes(
              att.userId
            )
        );
      }

      // Handle added attendees
      if (eventBeingReplanned.newConstraints.addedAttendees?.length > 0) {
        for (const addedAtt of eventBeingReplanned.newConstraints
          .addedAttendees) {
          // Avoid adding duplicates if they somehow remained from original list
          if (
            processedOriginalAttendees.some(
              (oa) =>
                oa.primaryEmail === addedAtt.email ||
                (addedAtt.userId && oa.userId === addedAtt.userId)
            )
          ) {
            continue;
          }
          // Fetch full attendee details if needed, or construct a partial MeetingAssistAttendeeType
          // This example assumes we might need to fetch full details using getMeetingAssistAttendeeByEmailOrUserId (hypothetical function)
          // For now, construct a partial object based on NewConstraints, assuming MA_Attendee ID is not known yet for new ones.
          const newAttendeeObject: MeetingAssistAttendeeType = {
            id: uuid(), // Generate a temporary ID or handle appropriately if it's a known user
            userId: addedAtt.userId || null, // UserID might be known if internal
            hostId: mainHostId, // Associate with the main host
            meetingId: null, // Not tied to a specific MA record yet, or use current MA if appropriate
            name: addedAtt.name || addedAtt.email.split('@')[0],
            primaryEmail: addedAtt.email,
            emails: [
              {
                primary: true,
                value: addedAtt.email,
                type: 'work',
                displayName: addedAtt.name || addedAtt.email.split('@')[0],
              },
            ],
            timezone: addedAtt.timezone || hostTimezone, // Default to host timezone if not provided
            externalAttendee:
              addedAtt.externalAttendee !== undefined
                ? addedAtt.externalAttendee
                : !addedAtt.userId,
            createdDate: dayjs().toISOString(),
            updatedAt: dayjs().toISOString(),
          };
          processedOriginalAttendees.push(newAttendeeObject);
        }
      }
      // Separate into internal and external based on the final list
      currentInternalAttendees = processedOriginalAttendees.filter(
        (a) => !a.externalAttendee
      );
      currentExternalAttendees = processedOriginalAttendees.filter(
        (a) => a.externalAttendee
      );
    }

    const newInternalMeetingEventsPlus = newMeetingEventPlus
      ?.map((e) => {
        const foundIndex = currentExternalAttendees?.findIndex(
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
        const foundIndex = currentExternalAttendees?.findIndex(
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

    const hostIsInternalAttendee = currentInternalAttendees.some(
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
          // TODO: For replan, if eventBeingReplanned.newConstraints.newTimeWindowStartUTC is set, use it here for relevant attendees
          windowStartDate,
          windowEndDate,
          hostTimezone,
          currentInternalAttendees, // Use finalized list
          oldEvents,
          meetingEventPlus,
          newInternalMeetingEventsPlus,
          newHostBufferTimes,
          // Pass isReplan and eventBeingReplanned for modifiable flag and duration logic
          isReplan,
          eventBeingReplanned
        );
    } else {
      // Assuming mainHost is always part of internalAttendees if they are internal.
      // If mainHost can be external or not in the list, this logic needs adjustment.
      returnValuesFromHost = await processEventsForOptaPlannerForMainHost(
        mainHostId,
        allHostEvents,
        // TODO: For replan, if eventBeingReplanned.newConstraints.newTimeWindowStartUTC is set, use it here
        windowStartDate,
        windowEndDate,
        hostTimezone,
        oldHostEvents,
        newHostBufferTimes,
        // Pass isReplan and eventBeingReplanned for modifiable flag and duration logic
        isReplan,
        eventBeingReplanned
      );
    }

    console.log(
      returnValuesFromInternalAttendees,
      ' returnValuesFromInternalAttendees'
    );
    const externalMeetingEventPlus = meetingEventPlus
      .map((e) => {
        const foundIndex = currentExternalAttendees.findIndex(
          (a) => a?.userId === e?.userId
        );
        if (foundIndex > -1) {
          return e;
        }
        return null;
      })
      ?.filter((e) => e !== null);

    const returnValuesFromExternalAttendees: ReturnBodyForExternalAttendeeForOptaplannerPrepType =
      currentExternalAttendees?.length > 0
        ? await processEventsForOptaPlannerForExternalAttendees(
            currentExternalAttendees?.map((a) => a.userId),
            mainHostId,
            meetingAssistEvents,
            // TODO: For replan, if eventBeingReplanned.newConstraints.newTimeWindowStartUTC is set, use it here for relevant attendees
            windowStartDate,
            windowEndDate,
            hostTimezone,
            currentExternalAttendees, // Use finalized list
            externalMeetingEventPlus,
            newExternalMeetingEventsPlus,
            // Pass meetingAssistId if available (e.g. from eventBeingReplanned or other context)
            // For now, assuming it might come from the event being replanned if it's a meeting assist event
            eventBeingReplanned?.originalEventId.includes('#')
              ? null
              : eventBeingReplanned?.originalEventId, // Simplistic check, might need better logic
            // Pass isReplan and eventBeingReplanned for modifiable flag and duration logic
            isReplan,
            eventBeingReplanned
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
        ...(isReplan &&
          eventBeingReplanned && {
            isReplan: true,
            originalGoogleEventId: eventBeingReplanned.googleEventId,
            originalCalendarId: eventBeingReplanned.calendarId,
          }),
      }),
      Bucket: bucketName,
      Key:
        isReplan && eventBeingReplanned
          ? `${mainHostId}/${singletonId}_REPLAN_${eventBeingReplanned.googleEventId}.json`
          : `${mainHostId}/${singletonId}.json`,
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
      isReplan && eventBeingReplanned
        ? `${mainHostId}/${singletonId}_REPLAN_${eventBeingReplanned.googleEventId}.json`
        : `${mainHostId}/${singletonId}.json`,
      optaplannerDuration,
      onOptaPlanCalendarAdminCallBackUrl
    );

    console.log('optaplanner request sent');
  } catch (e) {
    console.log(e, ' unable to process events for optaplanner');
  }
};
