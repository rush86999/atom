import { bucketName, optaplannerDuration, dayOfWeekIntToString, hasuraAdminSecret, hasuraGraphUrl, onOptaPlanCalendarAdminCallBackUrl, optaPlannerPassword, optaPlannerUrl, optaPlannerUsername, } from '@schedule_assist/_libs/constants';
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
export const listFutureMeetingAssists = async (userId, windowStartDate, windowEndDate, ids) => {
    try {
        console.log(userId, windowStartDate, windowEndDate, ids, ' userId, windowStartDate, windowEndDate, ids');
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
        let variables = {
            userId,
            windowStartDate,
            windowEndDate,
        };
        if (ids?.length > 0) {
            variables.ids = ids;
        }
        const res = await got
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
        console.log(res?.data?.Meeting_Assist, ' successfully got meeting asssists');
        return res?.data?.Meeting_Assist;
    }
    catch (e) {
        console.log(e, ' unable to list meeting assists');
    }
};
export const listMeetingAssistPreferredTimeRangesGivenMeetingId = async (meetingId) => {
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
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' uanble to list meeting assist preferred time ranges');
    }
};
export const meetingAttendeeCountGivenMeetingId = async (meetingId) => {
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
        const res = await got
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
        console.log(res?.data?.Meeting_Assist_Attendee_aggregate?.aggregate?.count, ' received attendee count');
        return res?.data?.Meeting_Assist_Attendee_aggregate?.aggregate?.count;
    }
    catch (e) {
        console.log(e, ' unable to get meeting attendee count');
    }
};
export const listMeetingAssistAttendeesGivenMeetingId = async (meetingId) => {
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
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' unable to list meeting assist attendees');
    }
};
export const getMeetingAssistAttendee = async (id) => {
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
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' unable to get meeting assist attendee');
    }
};
export const getMeetingAssist = async (id) => {
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
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' unable to get meeting assist from id');
    }
};
export const listMeetingAssistEventsForAttendeeGivenDates = async (attendeeId, hostStartDate, hostEndDate, userTimezone, hostTimezone) => {
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
        const startDateInHostTimezone = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true);
        const endDateInHostTimezone = dayjs(hostEndDate.slice(0, 19)).tz(hostTimezone, true);
        const startDateInUserTimezone = dayjs(startDateInHostTimezone)
            .tz(userTimezone)
            .format()
            .slice(0, 19);
        const endDateInUserTimezone = dayjs(endDateInHostTimezone)
            .tz(userTimezone)
            .format()
            .slice(0, 19);
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' unable to list meeting assist events for attendee given dates');
    }
};
export const listEventsForDate = async (userId, startDate, endDate, timezone) => {
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
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' unable to list events for date');
    }
};
export const listEventsForUserGivenDates = async (userId, hostStartDate, hostEndDate, userTimezone, hostTimezone) => {
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
        const startDateInHostTimezone = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true);
        const endDateInHostTimezone = dayjs(hostEndDate.slice(0, 19)).tz(hostTimezone, true);
        const startDateInUserTimezone = dayjs(startDateInHostTimezone)
            .tz(userTimezone)
            .format()
            .slice(0, 19);
        const endDateInUserTimezone = dayjs(endDateInHostTimezone)
            .tz(userTimezone)
            .format()
            .slice(0, 19);
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' listEventsForUser');
    }
};
export const processMeetingAssistForOptaplanner = async () => {
    try {
    }
    catch (e) {
        console.log(e, ' unable to process meeting assist for optaplanner');
    }
};
export const generateNewMeetingEventForAttendee = (attendee, meetingAssist, windowStartDate, windowEndDate, hostTimezone, calendarId, preferredStartTimeRange) => {
    let startDate = dayjs(windowStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .format();
    const endDate = dayjs(windowEndDate.slice(0, 19))
        .tz(hostTimezone, true)
        .format();
    console.log(startDate, ' startDate inside generateNewMeetingEventForAttendee step 1');
    if (preferredStartTimeRange?.dayOfWeek > 0) {
        const dateObject = dayjs(startDate.slice(0, 19))
            .tz(hostTimezone, true)
            .toDate();
        const dateObjectWithSetISODayPossible = setISODay(dateObject, preferredStartTimeRange?.dayOfWeek);
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
    console.log(startDate, ' startDate inside generateNewMeetingEventForAttendee step 2');
    if (preferredStartTimeRange?.startTime) {
        console.log(preferredStartTimeRange?.startTime, ' preferredStartTimeRange?.startTime');
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
    console.log(startDate, ' startDate inside generateNewMeetingEventForAttendee step 3');
    const eventId = uuid();
    const newEvent = {
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
export const generateNewMeetingEventForHost = (hostAttendee, meetingAssist, windowStartDate, windowEndDate, hostTimezone, preferredStartTimeRange) => {
    let startDate = dayjs(windowStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .format();
    const endDate = dayjs(windowEndDate.slice(0, 19))
        .tz(hostTimezone, true)
        .format();
    console.log(startDate, ' startDate inside generateNewMeetingEventForAttendee step 1');
    if (preferredStartTimeRange?.dayOfWeek > 0) {
        const dateObject = dayjs(startDate.slice(0, 19))
            .tz(hostTimezone, true)
            .toDate();
        const dateObjectWithSetISODayPossible = setISODay(dateObject, preferredStartTimeRange?.dayOfWeek);
        let dateObjectWithSetISODay = dateObjectWithSetISODayPossible;
        if (!dayjs(dateObjectWithSetISODayPossible).isBetween(startDate, endDate)) {
            dateObjectWithSetISODay = dayjs(dateObjectWithSetISODayPossible)
                .add(1, 'week')
                .toDate();
        }
        startDate = dayjs(dateObjectWithSetISODay).tz(hostTimezone).format();
    }
    console.log(startDate, ' startDate inside generateNewMeetingEventForAttendee step 2');
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
    console.log(startDate, ' startDate inside generateNewMeetingEventForAttendee step 3');
    const eventId = uuid();
    const newEvent = {
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
export const listPreferredTimeRangesForEvent = async (eventId) => {
    try {
        if (!eventId) {
            console.log(eventId, ' no eventId inside listPreferredTimeRangesForEvent');
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
        const res = await got
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
        res?.data?.PreferredTimeRange?.map((pt) => console.log(pt, ' preferredTimeRange - res?.data?.PreferredTimeRange inside  listPreferredTimeRangesForEvent '));
        return res?.data?.PreferredTimeRange;
    }
    catch (e) {
        console.log(e, ' unable to list preferred time ranges for event');
    }
};
export const createRemindersFromMinutesAndEvent = (eventId, minutes, timezone, useDefault, userId) => {
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
export const createBufferTimeForNewMeetingEvent = (event, bufferTime) => {
    let valuesToReturn = {};
    valuesToReturn.newEvent = event;
    const eventId = uuid();
    const eventId1 = uuid();
    const preEventId = event?.preEventId || `${eventId}#${event?.calendarId}`;
    const postEventId = event?.postEventId || `${eventId1}#${event?.calendarId}`;
    if (bufferTime.beforeEvent > 0) {
        const beforeEventOrEmpty = {
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
        const afterEventOrEmpty = {
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
    return valuesToReturn;
};
export const getUserPreferences = async (userId) => {
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
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' getUserPreferences');
    }
};
export const getGlobalCalendar = async (userId) => {
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
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' unable to get global calendar');
    }
};
export const adjustStartDatesForBreakEventsForDay = (allEvents, breakEvents, userPreferences, timezone) => {
    if (!allEvents?.[0]?.id) {
        console.log('no allEvents inside adjustStartDatesForBreakEvents');
        return;
    }
    const startTimes = userPreferences.startTimes;
    const endTimes = userPreferences.endTimes;
    const dayOfWeekInt = getISODay(dayjs(allEvents?.[0]?.startDate.slice(0, 19)).tz(timezone, true).toDate());
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
    const breakLength = userPreferences.breakLength <= 15 ? 15 : userPreferences.breakLength;
    if (breakEvents?.length > 0) {
        for (const breakEvent of breakEvents) {
            let foundSpace = false;
            let index = 0;
            while (!foundSpace && index < filteredEvents.length) {
                const possibleEndDate = dayjs(filteredEvents[index].startDate.slice(0, 19)).tz(timezone, true);
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
                while ((isBetweenStart ||
                    isBetweenEnd ||
                    !betweenWorkingDayStart ||
                    !betweenWorkingDayEnd ||
                    isBetweenBreakStart ||
                    isBetweenBreakEnd) &&
                    betweenIndex < filteredEvents.length) {
                    isBetweenStart = possibleStartDate.isBetween(dayjs(filteredEvents[betweenIndex].startDate.slice(0, 19)).tz(timezone, true), dayjs(filteredEvents[betweenIndex].endDate.slice(0, 19)).tz(timezone, true), 'minute', '[)');
                    isBetweenEnd = possibleEndDate.isBetween(dayjs(filteredEvents[betweenIndex].startDate.slice(0, 19)).tz(timezone, true), dayjs(filteredEvents[betweenIndex].endDate.slice(0, 19)).tz(timezone, true), 'minute', '(]');
                    betweenWorkingDayStart = possibleStartDate.isBetween(startOfWorkingDay, endOfWorkingDay, 'minute', '[)');
                    betweenWorkingDayEnd = possibleEndDate.isBetween(startOfWorkingDay, endOfWorkingDay, 'minute', '(]');
                    for (const breakEvent of breakEvents) {
                        isBetweenBreakStart = possibleStartDate.isBetween(dayjs(breakEvent.startDate.slice(0, 19)).tz(timezone, true), dayjs(breakEvent.endDate.slice(0, 19)).tz(timezone, true), 'minute', '[)');
                        isBetweenBreakEnd = possibleEndDate.isBetween(dayjs(breakEvent.startDate.slice(0, 19)).tz(timezone, true), dayjs(breakEvent.endDate.slice(0, 19)).tz(timezone, true), 'minute', '(]');
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
export const convertToTotalWorkingHoursForInternalAttendee = (userPreference, hostStartDate, hostTimezone) => {
    const startTimes = userPreference.startTimes;
    const endTimes = userPreference.endTimes;
    const dayOfWeekInt = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
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
export const convertToTotalWorkingHoursForExternalAttendee = (attendeeEvents, hostStartDate, hostTimezone, userTimezone) => {
    const dayOfWeekIntByHost = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
    const sameDayEvents = attendeeEvents.filter((e) => getISODay(dayjs(e.startDate.slice(0, 19))
        .tz(e.timezone || userTimezone, true)
        .tz(hostTimezone)
        .toDate()) === dayOfWeekIntByHost);
    const minStartDate = _.minBy(sameDayEvents, (e) => dayjs(e.startDate.slice(0, 19))
        .tz(e.timezone || userTimezone, true)
        .tz(hostTimezone)
        .unix());
    const maxEndDate = _.maxBy(sameDayEvents, (e) => dayjs(e.endDate.slice(0, 19))
        .tz(e.timezone || userTimezone, true)
        .tz(hostTimezone)
        .unix());
    let workEndHourByHost = dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .hour();
    const workEndMinuteByHost = dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(0), dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(15), 'minute', '[)')
        ? 15
        : dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(15), dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(30), 'minute', '[)')
            ? 30
            : dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30), dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(45), 'minute', '[)')
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
        .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
        .tz(minStartDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(0), dayjs(minStartDate.startDate.slice(0, 19))
        .tz(minStartDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(15), 'minute', '[)')
        ? 0
        : dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(15), dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(30), 'minute', '[)')
            ? 15
            : dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30), dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(45), 'minute', '[)')
                ? 30
                : 45;
    console.log(workStartHourByHost, workStartMinuteByHost, workEndHourByHost, ' workStartHourByHost, workStartMinuteByHost, workEndHourByHost for total working hours');
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
export const getEventDetailsForModification = async (hasuraEventId // Format: "googleEventId#calendarId"
) => {
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
        const response = await got
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
        if (response?.errors) {
            console.error(`Hasura error fetching event ${hasuraEventId} for modification:`, JSON.stringify(response.errors, null, 2));
            return null;
        }
        const eventData = response.data.Event_by_pk;
        if (eventData) {
            if (eventData.Attendees) {
                eventData.attendees = eventData.Attendees;
                delete eventData.Attendees;
            }
            else {
                eventData.attendees = [];
            }
            return eventData;
        }
        return null;
    }
    catch (error) {
        console.error(`Error in getEventDetailsForModification for event ${hasuraEventId}:`, error);
        return null;
    }
};
export function generateEventPartsForReplan(allUserEvents, // All events for all relevant users
eventToReplanHasuraId, // e.g., "googleEventId#calendarId"
replanConstraints, hostId, // Typically originalEventDetails.userId
hostTimezone // To resolve event part start/end for OptaPlanner if needed by formatEventType...
) {
    const allEventParts = [];
    for (const event of allUserEvents) {
        // Ensure preferredTimeRanges is at least an empty array for InitialEventPartTypePlus
        const eventWithPrefs = {
            ...event,
            preferredTimeRanges: event.preferredTimeRanges || [],
        };
        let parts = generateEventPartsLite(eventWithPrefs, hostId); // Returns InitialEventPartType[]
        if (event.id === eventToReplanHasuraId) {
            // This is the event being replanned
            const newDuration = replanConstraints.newDurationMinutes;
            if (newDuration && newDuration > 0) {
                const originalEventStartDate = dayjs(event.startDate.slice(0, 19)).tz(event.timezone || hostTimezone, true);
                const newEventEndDate = originalEventStartDate.add(newDuration, 'minutes');
                // Create a temporary event with the new duration to generate parts
                const tempEventForNewDuration = {
                    ...eventWithPrefs,
                    endDate: newEventEndDate.format(), // Ensure correct format
                };
                parts = generateEventPartsLite(tempEventForNewDuration, hostId);
            }
            parts = parts.map((p) => ({
                ...p,
                modifiable: true,
                // Add empty preferredTimeRanges if not present, to satisfy InitialEventPartTypePlus
                preferredTimeRanges: p.preferredTimeRanges || [],
            }));
        }
        else {
            // This is not the event being replanned, so pin it
            parts = parts.map((p) => {
                const initialPartPlus = {
                    ...p,
                    modifiable: false,
                    // Add empty preferredTimeRanges if not present
                    preferredTimeRanges: p.preferredTimeRanges || [],
                };
                // Apply pinning logic similar to setPreferredTimeForUnModifiableEvent
                // This function expects EventPartPlannerRequestBodyType, so we adapt its logic here for InitialEventPartTypePlus
                if (!initialPartPlus.preferredDayOfWeek &&
                    !initialPartPlus.preferredTime) {
                    const partStartDate = dayjs(initialPartPlus.startDate.slice(0, 19)).tz(initialPartPlus.timezone || hostTimezone, true);
                    initialPartPlus.preferredDayOfWeek = getISODay(partStartDate.toDate()); // May need dayOfWeekIntToString conversion if type mismatch
                    initialPartPlus.preferredTime = partStartDate.format('HH:mm:ss');
                }
                return initialPartPlus;
            });
        }
        allEventParts.push(...parts);
    }
    return allEventParts;
}
export async function generateTimeSlotsForReplan(users, // Final list of users for the replanned event
replanConstraints, hostTimezone, globalDefaultWindowStart, // Fallback window start (ISO string)
globalDefaultWindowEnd, // Fallback window end (ISO string)
mainHostId, // Needed by generateTimeSlotsLiteForInternalAttendee
userPreferencesCache // Cache to avoid re-fetching
) {
    const allTimeSlots = [];
    const effectiveWindowStartUTC = replanConstraints.newTimeWindowStartUTC || globalDefaultWindowStart;
    const effectiveWindowEndUTC = replanConstraints.newTimeWindowEndUTC || globalDefaultWindowEnd;
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
    const diffDays = dayjs(effectiveWindowEndInHostTz).diff(dayjs(effectiveWindowStartInHostTz), 'day');
    const startDatesForEachDayInWindow = [];
    for (let i = 0; i <= diffDays; i++) {
        startDatesForEachDayInWindow.push(dayjs(effectiveWindowStartInHostTz).add(i, 'day').format());
    }
    for (const user of users) {
        let userPrefs = userPreferencesCache.get(user.userId);
        if (!userPrefs) {
            userPrefs = await getUserPreferences(user.userId);
            if (userPrefs) {
                userPreferencesCache.set(user.userId, userPrefs);
            }
            else {
                // Handle case where user preferences might not be found for a user
                console.warn(`Preferences not found for user ${user.userId}, skipping timeslot generation for them.`);
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
            const userSpecificSlots = generateTimeSlotsLiteForInternalAttendee(dayToGenerateSlots, // This is already a date string in hostTimezone
            mainHostId, // Or user.hostId if appropriate, mainHostId seems more aligned with OptaPlanner's model
            userPrefs, hostTimezone, // Host's overall timezone
            user.timezone || hostTimezone, // Attendee's specific timezone
            isFirstDayLoop);
            allTimeSlots.push(...userSpecificSlots);
        }
    }
    return _.uniqWith(allTimeSlots, _.isEqual);
}
export async function orchestrateReplanOptaPlannerInput(userId, // User initiating the replan (usually the host)
hostTimezone, originalEventDetails, newConstraints, allUsersFromOriginalEventAndAdded, // Combined list of original and newly added attendees
allExistingEventsForUsers // Pre-fetched events for ALL relevant users in a broad window
// client: any, // ApolloClient, if needed - currently using global got for Hasura
) {
    try {
        const singletonId = uuid();
        const eventToReplanHasuraId = originalEventDetails.id; // googleEventId#calendarId
        // 1. Generate Event Parts
        // Host ID for event parts is typically the user ID from the original event
        const eventParts = generateEventPartsForReplan(allExistingEventsForUsers, eventToReplanHasuraId, newConstraints, originalEventDetails.userId, hostTimezone);
        if (!eventParts || eventParts.length === 0) {
            console.error('No event parts generated for replan. Aborting.');
            return null;
        }
        // 2. Generate Time Slots
        // Use a cache for user preferences within this function's scope
        const userPreferencesCache = new Map();
        // Define global fallback window (e.g., next 7 days from original event start if no new window specified)
        // These should be ISO datetime strings
        const originalEventStartDayjs = dayjs(originalEventDetails.startDate.slice(0, 19)).tz(originalEventDetails.timezone || hostTimezone, true);
        const globalDefaultWindowStart = newConstraints.newTimeWindowStartUTC ||
            originalEventStartDayjs.toISOString();
        const globalDefaultWindowEnd = newConstraints.newTimeWindowEndUTC ||
            originalEventStartDayjs.add(7, 'days').toISOString();
        const timeSlots = await generateTimeSlotsForReplan(allUsersFromOriginalEventAndAdded, newConstraints, hostTimezone, globalDefaultWindowStart, globalDefaultWindowEnd, originalEventDetails.userId, // mainHostId for timeslot generation context
        userPreferencesCache);
        if (!timeSlots || timeSlots.length === 0) {
            console.error('No time slots generated for replan. Aborting.');
            return null;
        }
        // 3. Construct User List (UserPlannerRequestBodyType)
        const userListForPlanner = [];
        for (const user of allUsersFromOriginalEventAndAdded) {
            let userPrefs = userPreferencesCache.get(user.userId);
            if (!userPrefs) {
                userPrefs = await getUserPreferences(user.userId);
                if (userPrefs) {
                    userPreferencesCache.set(user.userId, userPrefs);
                }
                else {
                    console.warn(`Preferences not found for user ${user.userId} while building userListForPlanner. Using defaults.`);
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
                    };
                }
            }
            const workTimes = user.externalAttendee
                ? generateWorkTimesForExternalAttendee(originalEventDetails.userId, // hostId context
                user.userId, allExistingEventsForUsers.filter((e) => e.userId === user.userId), // Pass only this user's events
                hostTimezone, user.timezone || hostTimezone)
                : generateWorkTimesForInternalAttendee(originalEventDetails.userId, // hostId context
                user.userId, userPrefs, hostTimezone, user.timezone || hostTimezone);
            userListForPlanner.push(user.externalAttendee
                ? generateUserPlannerRequestBodyForExternalAttendee(user.userId, workTimes, originalEventDetails.userId)
                : generateUserPlannerRequestBody(userPrefs, user.userId, workTimes, originalEventDetails.userId));
        }
        const uniqueUserListForPlanner = _.uniqBy(userListForPlanner, 'id');
        // 4. Assemble PlannerRequestBodyType
        const fileKey = `${originalEventDetails.userId}/${singletonId}_REPLAN_${originalEventDetails.eventId}.json`;
        const plannerRequestBody = {
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
                const partUser = allUsersFromOriginalEventAndAdded.find((u) => u.userId === ep.userId);
                let partUserPrefs = userPreferencesCache.get(ep.userId);
                if (!partUserPrefs) {
                    // This should ideally not happen if all users in eventParts are in allUsersFromOriginalEventAndAdded
                    // and their prefs were fetched for userList. Adding a fallback.
                    console.warn(`Prefs not in cache for user ${ep.userId} during event part formatting. Using defaults.`);
                    partUserPrefs = {
                    /* ... default UserPreferenceType ... */
                    };
                }
                const partWorkTimes = partUser?.externalAttendee
                    ? generateWorkTimesForExternalAttendee(originalEventDetails.userId, ep.userId, allExistingEventsForUsers.filter((e) => e.userId === ep.userId), hostTimezone, partUser?.timezone || hostTimezone)
                    : generateWorkTimesForInternalAttendee(originalEventDetails.userId, ep.userId, partUserPrefs, hostTimezone, partUser?.timezone || hostTimezone);
                return partUser?.externalAttendee
                    ? formatEventTypeToPlannerEventForExternalAttendee(ep, partWorkTimes, allExistingEventsForUsers.filter((e) => e.userId === ep.userId), hostTimezone)
                    : formatEventTypeToPlannerEvent(ep, partUserPrefs, partWorkTimes, hostTimezone);
            })
                .filter((ep) => ep !== null), // Filter out nulls if allDay events were skipped
            fileKey,
            delay: optaplannerDuration, // from constants
            callBackUrl: onOptaPlanCalendarAdminCallBackUrl, // from constants
        };
        // Filter out any null event parts that might result from allDay events etc.
        plannerRequestBody.eventParts = plannerRequestBody.eventParts.filter((ep) => ep != null);
        if (!plannerRequestBody.eventParts ||
            plannerRequestBody.eventParts.length === 0) {
            console.error('No valid event parts to send to OptaPlanner after formatting. Aborting.');
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
        await optaPlanWeekly(plannerRequestBody.timeslots, plannerRequestBody.userList, plannerRequestBody.eventParts, plannerRequestBody.singletonId, plannerRequestBody.hostId, plannerRequestBody.fileKey, plannerRequestBody.delay, plannerRequestBody.callBackUrl);
        console.log(`OptaPlanner replan task initiated for singletonId: ${singletonId}`);
        return plannerRequestBody;
    }
    catch (error) {
        console.error(`Error in orchestrateReplanOptaPlannerInput for event ${originalEventDetails.id}:`, error);
        return null;
    }
}
// New function to list external attendee preferences
export const listExternalAttendeePreferences = async (
// client: any, // Not needed as got is used directly with global config
meetingAssistId, meetingAssistAttendeeId) => {
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
        const res = await got
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
        if (res?.errors) {
            console.error('Hasura errors while fetching external preferences:', JSON.stringify(res.errors, null, 2));
            throw new Error(`Hasura request failed: ${res.errors[0].message}`);
        }
        return res?.data?.Meeting_Assist_External_Attendee_Preference || [];
    }
    catch (e) {
        // Log the error caught by the try-catch block
        console.error('Error fetching external attendee preferences (catch block):', e);
        return []; // Return empty array on error
    }
};
export const generateBreaks = (userPreferences, numberOfBreaksToGenerate, eventMirror, globalCalendarId) => {
    const breaks = [];
    if (!userPreferences?.breakLength) {
        console.log('no user preferences breakLength provided inside generateBreaks');
        return breaks;
    }
    if (!numberOfBreaksToGenerate) {
        console.log('no number of breaks to generate provided inside generateBreaks');
        return breaks;
    }
    if (!eventMirror) {
        console.log('no event mirror provided inside generateBreaks');
        return breaks;
    }
    console.log(numberOfBreaksToGenerate, ' numberOfBreaksToGenerate inside generateBreaks');
    const breakLength = userPreferences.breakLength <= 15 ? 15 : userPreferences.breakLength;
    for (let i = 0; i < numberOfBreaksToGenerate; i++) {
        const eventId = uuid();
        const breakEvent = {
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
export const shouldGenerateBreakEventsForDay = (workingHours, userPreferences, allEvents) => {
    if (!userPreferences?.breakLength) {
        console.log('no user preferences breakLength provided inside shouldGenerateBreakEvents');
        return false;
    }
    if (!(allEvents?.length > 0)) {
        console.log('no allEvents present inside shouldGenerateBreakEventsForDay');
        return false;
    }
    const breakEvents = allEvents.filter((event) => event.isBreak);
    const numberOfBreaksPerDay = userPreferences.minNumberOfBreaks;
    const breakHoursFromMinBreaks = (userPreferences.breakLength / 60) * numberOfBreaksPerDay;
    const hoursMustBeBreak = workingHours * (1 - userPreferences.maxWorkLoadPercent / 100);
    let breakHoursAvailable = 0;
    if (breakHoursFromMinBreaks > hoursMustBeBreak) {
        breakHoursAvailable = breakHoursFromMinBreaks;
    }
    else {
        breakHoursAvailable = hoursMustBeBreak;
    }
    let breakHoursUsed = 0;
    for (const breakEvent of breakEvents) {
        const duration = dayjs
            .duration(dayjs(dayjs(breakEvent.endDate.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss')).diff(dayjs(breakEvent.startDate.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss')))
            .asHours();
        breakHoursUsed += duration;
    }
    if (breakHoursUsed >= breakHoursAvailable) {
        console.log('breakHoursUsed >= breakHoursAvailable');
        return false;
    }
    if (!(allEvents?.length > 0)) {
        console.log('there are no events for this date inside shouldGenerateBreakEvents');
        return false;
    }
    return true;
};
export const generateBreakEventsForDay = async (userPreferences, userId, hostStartDate, hostTimezone, globalCalendarId, isFirstDay) => {
    try {
        if (!userPreferences?.breakLength) {
            console.log('no user preferences breakLength provided inside shouldGenerateBreakEvents');
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
            const dayOfWeekInt = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
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
            const workStartMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
            if (dayjs(hostStartDate.slice(0, 19)).isAfter(dayjs(hostStartDate.slice(0, 19)).hour(endHour).minute(endMinute))) {
                return null;
            }
            if (dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .isBefore(dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(workStartHour)
                .minute(workStartMinute))) {
                startHourByHost = workStartHour;
                startMinuteByHost = workStartMinute;
            }
            const workingHours = convertToTotalWorkingHoursForInternalAttendee(userPreferences, hostStartDate, hostTimezone);
            console.log(workingHours, ' workingHours');
            const allEvents = await listEventsForDate(userId, dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(startHourByHost)
                .minute(startMinuteByHost)
                .format(), dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(endHour)
                .minute(endMinute)
                .format(), hostTimezone);
            if (!(allEvents?.length > 0)) {
                console.log('no allEvents present inside shouldGenerateBreakEventsForDay');
                return null;
            }
            const shouldGenerateBreaks = shouldGenerateBreakEventsForDay(workingHours, userPreferences, allEvents);
            console.log(shouldGenerateBreaks, ' shouldGenerateBreaks');
            if (!shouldGenerateBreaks) {
                console.log('should not generate breaks');
                return null;
            }
            let hoursUsed = 0;
            if (allEvents?.length > 0) {
                for (const allEvent of allEvents) {
                    const duration = dayjs
                        .duration(dayjs(allEvent.endDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .diff(dayjs(allEvent.startDate.slice(0, 19)).tz(hostTimezone, true)))
                        .asHours();
                    hoursUsed += duration;
                }
            }
            console.log(hoursUsed, ' hoursUsed');
            let hoursAvailable = workingHours - hoursUsed;
            console.log(hoursAvailable, ' hoursAvailable');
            const hoursMustBeBreak = workingHours * (1 - userPreferences.maxWorkLoadPercent / 100);
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
                .filter((e) => dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .isSame(dayjs(e.startDate.slice(0, 19)).tz(hostTimezone, true), 'day'));
            const breakEvents = oldBreakEvents;
            const numberOfBreaksPerDay = userPreferences.minNumberOfBreaks;
            console.log(numberOfBreaksPerDay, ' numberOfBreaksPerDay aka userPreferences.minNumberOfBreaks');
            console.log(userPreferences.breakLength, ' userPreferences.breakLength');
            const breakHoursToGenerateForMinBreaks = (userPreferences.breakLength / 60) * numberOfBreaksPerDay;
            console.log(breakHoursToGenerateForMinBreaks, ' breakHoursToGenerateForMinBreaks');
            let breakHoursToGenerate = 0;
            if (breakHoursToGenerateForMinBreaks > hoursAvailable) {
                breakHoursToGenerate = hoursAvailable;
            }
            else {
                breakHoursToGenerate = breakHoursToGenerateForMinBreaks;
            }
            console.log(breakHoursToGenerate, ' breakHoursToGenerate');
            let breakHoursUsed = 0;
            if (breakEvents?.length > 0) {
                for (const breakEvent of breakEvents) {
                    const duration = dayjs
                        .duration(dayjs(breakEvent.endDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .diff(dayjs(breakEvent.startDate.slice(0, 19)).tz(hostTimezone, true)))
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
            const numberOfBreaksToGenerate = Math.floor(actualBreakHoursToGenerate / breakLengthAsHours);
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
            const newEvents = generateBreaks(userPreferences, numberOfBreaksToGenerate, eventMirror, globalCalendarId);
            return newEvents;
        }
        const endTimes = userPreferences.endTimes;
        const dayOfWeekInt = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
        const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
        const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;
        const startTimes = userPreferences.startTimes;
        const startHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
        const startMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
        const workingHours = convertToTotalWorkingHoursForInternalAttendee(userPreferences, hostStartDate, hostTimezone);
        const allEvents = await listEventsForDate(userId, dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(startHour)
            .minute(startMinute)
            .format(), dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(endHour)
            .minute(endMinute)
            .format(), hostTimezone);
        if (!(allEvents?.length > 0)) {
            console.log('no allEvents present inside shouldGenerateBreakEventsForDay');
            return null;
        }
        const shouldGenerateBreaks = shouldGenerateBreakEventsForDay(workingHours, userPreferences, allEvents);
        if (!shouldGenerateBreaks) {
            console.log('should not generate breaks');
            return null;
        }
        let hoursUsed = 0;
        if (allEvents?.length > 0) {
            for (const allEvent of allEvents) {
                const duration = dayjs
                    .duration(dayjs(allEvent.endDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .diff(dayjs(allEvent.startDate.slice(0, 19)).tz(hostTimezone, true)))
                    .asHours();
                hoursUsed += duration;
            }
        }
        console.log(hoursUsed, ' hoursUsed');
        let hoursAvailable = workingHours - hoursUsed;
        const hoursMustBeBreak = workingHours * (1 - userPreferences.maxWorkLoadPercent / 100);
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
            .filter((e) => dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isSame(dayjs(e.startDate.slice(0, 19)).tz(hostTimezone, true), 'day'));
        const breakEvents = oldBreakEvents;
        const numberOfBreaksPerDay = userPreferences.minNumberOfBreaks;
        console.log(numberOfBreaksPerDay, ' numberOfBreaksPerDay');
        const breakHoursToGenerateForMinBreaks = (userPreferences.breakLength / 60) * numberOfBreaksPerDay;
        let breakHoursToGenerate = 0;
        if (breakHoursToGenerateForMinBreaks > hoursAvailable) {
            breakHoursToGenerate = hoursAvailable;
        }
        else {
            breakHoursToGenerate = breakHoursToGenerateForMinBreaks;
        }
        console.log(breakHoursToGenerate, ' breakHoursToGenerate');
        let breakHoursUsed = 0;
        if (breakEvents?.length > 0) {
            for (const breakEvent of breakEvents) {
                const duration = dayjs
                    .duration(dayjs(breakEvent.endDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .diff(dayjs(breakEvent.startDate.slice(0, 19)).tz(hostTimezone, true)))
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
        const numberOfBreaksToGenerate = Math.floor(actualBreakHoursToGenerate / breakLengthAsHours);
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
        const newEvents = generateBreaks(userPreferences, numberOfBreaksToGenerate, eventMirror, globalCalendarId);
        return newEvents;
    }
    catch (e) {
        console.log(e, ' unable to generate breaks for day');
    }
};
export const generateBreakEventsForDate = async (userPreferences, userId, hostStartDate, hostEndDate, hostTimezone, globalCalendarId) => {
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
            const newBreakEvents = await generateBreakEventsForDay(userPreferences, userId, dayDate, hostTimezone, globalCalendarId, i === 0);
            if (i === 0) {
                const endTimes = userPreferences.endTimes;
                const dayOfWeekInt = getISODay(dayjs(dayDate.slice(0, 19)).tz(hostTimezone, true).toDate());
                let startHour = dayjs(dayDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .hour();
                let startMinute = dayjs(dayDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .minute();
                const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
                const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;
                const startTimes = userPreferences.startTimes;
                const workStartHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
                const workStartMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
                if (dayjs(dayDate.slice(0, 19)).isAfter(dayjs(dayDate.slice(0, 19)).hour(endHour).minute(endMinute))) {
                    continue;
                }
                if (dayjs(dayDate.slice(0, 19)).isBefore(dayjs(dayDate.slice(0, 19))
                    .hour(workStartHour)
                    .minute(workStartMinute))) {
                    startHour = workStartHour;
                    startMinute = workStartMinute;
                }
                const allEvents = await listEventsForDate(userId, dayjs(dayDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .hour(startHour)
                    .minute(startMinute)
                    .format(), dayjs(dayDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .hour(endHour)
                    .minute(endMinute)
                    .format(), hostTimezone);
                const newBreakEventsAdjusted = await adjustStartDatesForBreakEventsForDay(allEvents, newBreakEvents, userPreferences, hostTimezone);
                if (newBreakEventsAdjusted?.length > 0) {
                    newBreakEventsAdjusted.forEach((b) => console.log(b, ' newBreakEventsAdjusted'));
                    totalBreakEvents.push(...newBreakEventsAdjusted);
                }
                continue;
            }
            const endTimes = userPreferences.endTimes;
            const dayOfWeekInt = getISODay(dayjs(dayDate.slice(0, 19)).tz(hostTimezone, true).toDate());
            const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
            const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;
            const startTimes = userPreferences.startTimes;
            const startHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
            const startMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
            const allEvents = await listEventsForDate(userId, dayjs(dayDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(startHour)
                .minute(startMinute)
                .format(), dayjs(dayDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(endHour)
                .minute(endMinute)
                .format(), hostTimezone);
            const newBreakEventsAdjusted = await adjustStartDatesForBreakEventsForDay(allEvents, newBreakEvents, userPreferences, hostTimezone);
            if (newBreakEventsAdjusted?.length > 0) {
                newBreakEventsAdjusted.forEach((b) => console.log(b, ' newBreakEventsAdjusted'));
                totalBreakEvents.push(...newBreakEventsAdjusted);
            }
        }
        return totalBreakEvents;
    }
    catch (e) {
        console.log(e, ' unable to generateBreakEventsForDate');
    }
};
export const generateWorkTimesForInternalAttendee = (hostId, userId, userPreference, hostTimezone, userTimezone) => {
    const daysInWeek = 7;
    const startTimes = userPreference.startTimes;
    const endTimes = userPreference.endTimes;
    const workTimes = [];
    for (let i = 0; i < daysInWeek; i++) {
        const dayOfWeekInt = i + 1;
        const startHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
        const startMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
        const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
        const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;
        workTimes.push({
            dayOfWeek: dayOfWeekIntToString[dayOfWeekInt],
            startTime: dayjs(setISODay(dayjs()
                .hour(startHour)
                .minute(startMinute)
                .tz(userTimezone, true)
                .toDate(), i + 1))
                .tz(hostTimezone)
                .format('HH:mm:ss'),
            endTime: dayjs(setISODay(dayjs()
                .hour(endHour)
                .minute(endMinute)
                .tz(userTimezone, true)
                .toDate(), i + 1))
                .tz(hostTimezone)
                .format('HH:mm:ss'),
            hostId,
            userId,
        });
    }
    return workTimes;
};
const formatToMonthDay = (month, day) => {
    const monthFormat = (month < 9 ? `0${month + 1}` : `${month + 1}`);
    const dayFormat = (day < 10 ? `0${day}` : `${day}`);
    return `--${monthFormat}-${dayFormat}`;
};
export const generateTimeSlotsForInternalAttendee = (hostStartDate, hostId, userPreference, hostTimezone, userTimezone, isFirstDay) => {
    if (isFirstDay) {
        console.log(hostStartDate, ' hostStartDate inside firstday inside generatetimeslotsforinternalattendee');
        const endTimes = userPreference.endTimes;
        const dayOfWeekInt = getISODay(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .toDate());
        const dayOfWeekIntByHost = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
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
            .isBetween(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .minute(0), dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .minute(15), 'minute', '[)')
            ? 0
            : dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .tz(userTimezone)
                .isBetween(dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .tz(userTimezone)
                .minute(15), dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .tz(userTimezone)
                .minute(30), 'minute', '[)')
                ? 15
                : dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .tz(userTimezone)
                    .isBetween(dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .tz(userTimezone)
                    .minute(30), dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .tz(userTimezone)
                    .minute(45), 'minute', '[)')
                    ? 30
                    : 45;
        const monthByHost = dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .month();
        const dayOfMonthByHost = dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .date();
        console.log(dayOfMonthByHost, ' dayOfMonthByHost inside generateTimeSlotsForInternalAttendees');
        const startHourByHost = dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour();
        const startMinuteByHost = dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isBetween(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(0), dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(15), 'minute', '[)')
            ? 0
            : dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .isBetween(dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(15), dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(30), 'minute', '[)')
                ? 15
                : dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .isBetween(dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .minute(30), dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .minute(45), 'minute', '[)')
                    ? 30
                    : 45;
        const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
        const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;
        const endHourByHost = dayjs(setISODay(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .hour(endHour)
            .toDate(), dayOfWeekInt))
            .tz(hostTimezone)
            .hour();
        const endMinuteByHost = dayjs(setISODay(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .minute(endMinute)
            .toDate(), dayOfWeekInt))
            .tz(hostTimezone)
            .minute();
        const startTimes = userPreference.startTimes;
        const workStartHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
        const workStartMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
        const workStartHourByHost = dayjs(setISODay(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .hour(workStartHour)
            .toDate(), dayOfWeekInt))
            .tz(hostTimezone)
            .hour();
        const workStartMinuteByHost = dayjs(setISODay(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .minute(endMinute)
            .toDate(), dayOfWeekInt))
            .tz(hostTimezone)
            .minute();
        if (dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isAfter(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(endHourByHost)
            .minute(endMinuteByHost))) {
            return [];
        }
        if (dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isBefore(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(workStartHourByHost)
            .minute(workStartMinuteByHost))) {
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
            const timeSlots = [];
            console.log(hostStartDate, endTimes, dayOfWeekIntByHost, dayOfMonth, startHour, startMinute, endHour, endMinute, timezone, `startDate, endTimes, dayOfWeekIntByHost, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`);
            for (let i = 0; i < totalMinutes; i += 15) {
                timeSlots.push({
                    dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
                    startTime: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .hour(startHourByHost)
                        .minute(startMinuteByHost)
                        .add(i, 'minute')
                        .format('HH:mm:ss'),
                    endTime: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .hour(startHourByHost)
                        .minute(startMinuteByHost)
                        .add(i + 15, 'minute')
                        .format('HH:mm:ss'),
                    hostId,
                    monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
                    date: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .format('YYYY-MM-DD'),
                });
            }
            console.log(timeSlots, ' timeSlots inside generateTimeSlots for first day where startDate is before work start time');
            return timeSlots;
        }
        const startDuration = dayjs.duration({
            hours: startHour,
            minutes: startMinute,
        });
        const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute });
        const totalDuration = endDuration.subtract(startDuration);
        const totalMinutes = totalDuration.asMinutes();
        const timeSlots = [];
        console.log(hostStartDate, endTimes, dayOfWeekInt, dayOfMonthByHost, startHourByHost, startMinuteByHost, endHourByHost, endMinuteByHost, hostTimezone, `startDate, endTimes, dayOfWeekInt, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`);
        for (let i = 0; i < totalMinutes; i += 15) {
            timeSlots.push({
                dayOfWeek: dayOfWeekIntToString[dayOfWeekInt],
                startTime: dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .hour(startHourByHost)
                    .minute(startMinuteByHost)
                    .add(i, 'minute')
                    .format('HH:mm:ss'),
                endTime: dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .hour(startHourByHost)
                    .minute(startMinuteByHost)
                    .add(i + 15, 'minute')
                    .format('HH:mm:ss'),
                hostId,
                monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
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
    const dayOfWeekInt = getISODay(dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .tz(userTimezone)
        .toDate());
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
    console.log(monthByHost, dayOfMonthByHost, startHourByHost, startMinuteByHost, endHourByHost, ' monthByHost, dayOfMonthByHost, startHourByHost, startMinuteByHost, endHourByHost');
    const startDuration = dayjs.duration({
        hours: startHour,
        minutes: startMinute,
    });
    const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute });
    const totalDuration = endDuration.subtract(startDuration);
    const totalMinutes = totalDuration.asMinutes();
    const timeSlots = [];
    for (let i = 0; i < totalMinutes; i += 15) {
        timeSlots.push({
            dayOfWeek: dayOfWeekIntToString[dayOfWeekInt],
            startTime: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(startHourByHost)
                .minute(startMinuteByHost)
                .add(i, 'minute')
                .format('HH:mm:ss'),
            endTime: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(startHourByHost)
                .minute(startMinuteByHost)
                .add(i + 15, 'minute')
                .format('HH:mm:ss'),
            hostId,
            monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
            date: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .format('YYYY-MM-DD'),
        });
    }
    console.log(timeSlots, ' timeSlots inside generateTimeSlots');
    return timeSlots;
};
export const generateTimeSlotsLiteForInternalAttendee = (hostStartDate, hostId, userPreference, hostTimezone, userTimezone, isFirstDay) => {
    if (isFirstDay) {
        const endTimes = userPreference.endTimes;
        const dayOfWeekInt = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
        const startHourOfHostDateByHost = dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour();
        const startMinuteOfHostDateByHost = dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isBetween(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(0), dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(30), 'minute', '[)')
            ? 0
            : dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .isBetween(dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(30), dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(59), 'minute', '[)')
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
            .isBetween(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(0), dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(30), 'minute', '[)')
            ? 0
            : dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .isBetween(dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(30), dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(59), 'minute', '[)')
                ? 30
                : 0;
        const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
        const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;
        const endHourByHost = dayjs(setISODay(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .hour(endHour)
            .toDate(), dayOfWeekInt))
            .tz(hostTimezone)
            .hour();
        const endMinuteByHost = dayjs(setISODay(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .minute(endMinute)
            .toDate(), dayOfWeekInt))
            .tz(hostTimezone)
            .minute();
        const startTimes = userPreference.startTimes;
        const workStartHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
        const workStartMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
        const workStartHourByHost = dayjs(setISODay(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .hour(workStartHour)
            .toDate(), dayOfWeekInt))
            .tz(hostTimezone)
            .hour();
        const workStartMinuteByHost = dayjs(setISODay(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .minute(endMinute)
            .toDate(), dayOfWeekInt))
            .tz(hostTimezone)
            .minute();
        if (dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isAfter(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(endHourByHost)
            .minute(endMinuteByHost))) {
            return [];
        }
        if (dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isBefore(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(workStartHourByHost)
            .minute(workStartMinuteByHost))) {
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
            const timeSlots = [];
            for (let i = 0; i < totalMinutes; i += 30) {
                timeSlots.push({
                    dayOfWeek: dayOfWeekIntToString[dayOfWeekInt],
                    startTime: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .hour(startHourByHost)
                        .minute(startMinuteByHost)
                        .add(i, 'minute')
                        .format('HH:mm:ss'),
                    endTime: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .hour(startHourByHost)
                        .minute(startMinuteByHost)
                        .add(i + 30, 'minute')
                        .format('HH:mm:ss'),
                    hostId,
                    monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
                    date: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .format('YYYY-MM-DD'),
                });
            }
            console.log(timeSlots, ' timeSlots inside generateTimeSlots for first day before start time');
            return timeSlots;
        }
        const startDuration = dayjs.duration({
            hours: startHourOfHostDateByHost,
            minutes: startMinuteOfHostDateByHost,
        });
        const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute });
        const totalDuration = endDuration.subtract(startDuration);
        const totalMinutes = totalDuration.asMinutes();
        const timeSlots = [];
        for (let i = 0; i < totalMinutes; i += 30) {
            timeSlots.push({
                dayOfWeek: dayOfWeekIntToString[dayOfWeekInt],
                startTime: dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .hour(startHourByHost)
                    .minute(startMinuteByHost)
                    .add(i, 'minute')
                    .format('HH:mm:ss'),
                endTime: dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .hour(startHourByHost)
                    .minute(startMinuteByHost)
                    .add(i + 30, 'minute')
                    .format('HH:mm:ss'),
                hostId,
                monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
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
    const dayOfWeekInt = getISODay(dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .tz(userTimezone)
        .toDate());
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
    const dayOfWeekIntByHost = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
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
    const timeSlots = [];
    for (let i = 0; i < totalMinutes; i += 30) {
        timeSlots.push({
            dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
            startTime: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(startHourByHost)
                .minute(startMinuteByHost)
                .add(i, 'minute')
                .format('HH:mm:ss'),
            endTime: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(startHourByHost)
                .minute(startMinuteByHost)
                .add(i + 30, 'minute')
                .format('HH:mm:ss'),
            hostId,
            monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
            date: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .format('YYYY-MM-DD'),
        });
    }
    console.log(timeSlots, ' timeSlots inside generateTimeSlots');
    return timeSlots;
};
export const validateEventDates = (event, userPreferences) => {
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
    const isoWeekDay = getISODay(dayjs(event?.startDate.slice(0, 19)).tz(event?.timezone, true).toDate());
    const endHour = userPreferences.endTimes.find((e) => e?.day === isoWeekDay)?.hour;
    const endMinutes = userPreferences.endTimes.find((e) => e?.day === isoWeekDay)?.minutes;
    const startHour = userPreferences.startTimes.find((e) => e?.day === isoWeekDay)?.hour;
    const startMinutes = userPreferences.startTimes.find((e) => e?.day === isoWeekDay)?.minutes;
    if (dayjs(event.startDate.slice(0, 19))
        .tz(event.timezone, true)
        .isAfter(dayjs(event?.startDate.slice(0, 19))
        .tz(event.timezone, true)
        .hour(endHour)
        .minute(endMinutes))) {
        return false;
    }
    if (dayjs(event.startDate.slice(0, 19))
        .tz(event.timezone, true)
        .isBefore(dayjs(event?.startDate.slice(0, 19))
        .tz(event.timezone, true)
        .hour(startHour)
        .minute(startMinutes))) {
        return false;
    }
    if (diff === 0) {
        console.log(event.id, event.startDate, event.endDate, ' the start date and end date are the same');
        return false;
    }
    if (diff < 0) {
        console.log(event.id, event.startDate, event.endDate, ' the start date is after end date');
        return false;
    }
    if (diffDay >= 1) {
        console.log(event.id, event.startDate, event.endDate, ' the start date and end date are more than 1 day apart');
        return false;
    }
    if (diffHours > 23) {
        console.log(event.id, event.startDate, event.endDate, ' the start date and end date are more than 23 hours apart');
        return false;
    }
    return true;
};
export const validateEventDatesForExternalAttendee = (event) => {
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
        console.log(event.id, event.startDate, event.endDate, ' the start date and end date are the same');
        return false;
    }
    if (diff < 0) {
        console.log(event.id, event.startDate, event.endDate, ' the start date is after end date');
        return false;
    }
    if (diffDay >= 1) {
        console.log(event.id, event.startDate, event.endDate, ' the start date and end date are more than 1 day apart');
        return false;
    }
    if (diffHours > 23) {
        console.log(event.id, event.startDate, event.endDate, ' the start date and end date are more than 23 hours apart');
        return false;
    }
    return true;
};
export const generateEventParts = (event, hostId) => {
    console.log(event.id, event.startDate.slice(0, 19), event.endDate.slice(0, 19), ' event.id, event.startDate.slice(0, 19), event.endDate.slice(0, 19) inside generateEventParts');
    const minutes = dayjs(event.endDate.slice(0, 19))
        .tz(event.timezone, true)
        .diff(dayjs(event.startDate.slice(0, 19)).tz(event.timezone, true), 'm');
    console.log(event.id, minutes, 'event.id,  minutes inside generateEventParts');
    const parts = Math.floor(minutes / 15);
    const remainder = minutes % 15;
    const eventParts = [];
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
    console.log(event.id, eventParts?.[0]?.startDate, eventParts?.[0]?.endDate, eventParts?.[0]?.part, eventParts?.[0]?.lastPart, 'event.id,  eventParts?.[0]?.startDate, eventParts?.[0]?.endDate, eventParts?.[0]?.part, eventParts?.[0]?.lastPart,');
    return eventParts;
};
export const generateEventPartsLite = (event, hostId) => {
    console.log(event, ' event before generateEventPartsLite');
    console.log(event.id, event.startDate.slice(0, 19), event.endDate.slice(0, 19), ' event.id, event.startDate.slice(0, 19), event.endDate.slice(0, 19) inside generateEventPartsLite');
    const minutes = dayjs(event.endDate.slice(0, 19))
        .tz(event.timezone, true)
        .diff(dayjs(event.startDate.slice(0, 19)).tz(event.timezone, true), 'm');
    const parts = Math.floor(minutes / 30);
    const remainder = minutes % 30;
    const eventParts = [];
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
export const modifyEventPartsForSingularPreBufferTime = (eventParts, forEventId) => {
    const preBufferBeforeEventParts = [];
    const preBufferActualEventParts = [];
    const preBufferGroupId = uuid();
    for (let i = 0; i < eventParts.length; i++) {
        if (eventParts[i].forEventId === forEventId && eventParts[i].isPreEvent) {
            console.log(eventParts[i].forEventId, forEventId, ' eventParts[i].forEventId === forEventId  inside modifyEventPartsForSingularPreBufferTime');
            preBufferBeforeEventParts.push({
                ...eventParts[i],
                groupId: preBufferGroupId,
            });
        }
    }
    for (let i = 0; i < eventParts.length; i++) {
        if (eventParts[i].id === forEventId) {
            console.log(eventParts[i].id, forEventId, 'eventParts[i].id === forEventId inside modifyEventPartsForSingularPreBufferTime');
            preBufferActualEventParts.push({
                ...eventParts[i],
                groupId: preBufferGroupId,
            });
        }
    }
    const preBufferBeforeEventPartsSorted = preBufferBeforeEventParts.sort((a, b) => a.part - b.part);
    const preBufferActualEventPartsSorted = preBufferActualEventParts.sort((a, b) => a.part - b.part);
    const preBufferEventPartsTotal = preBufferBeforeEventPartsSorted.concat(preBufferActualEventPartsSorted);
    for (let i = 0; i < preBufferEventPartsTotal.length; i++) {
        preBufferEventPartsTotal[i].part = i + 1;
        preBufferEventPartsTotal[i].lastPart = preBufferEventPartsTotal.length;
    }
    preBufferEventPartsTotal.forEach((e) => console.log(e.id, e.groupId, e.eventId, e.part, e.lastPart, e.startDate, e.endDate, `e.id, e.groupId, e.eventId, e.part, e.lastPart, e.startDate, e.endDate, inside modifyEventPartsForSingularPreBufferTime`));
    return preBufferEventPartsTotal;
};
export const modifyEventPartsForMultiplePreBufferTime = (eventParts) => {
    const uniquePreBufferPartForEventIds = [];
    const preBufferEventPartsTotal = [];
    for (let i = 0; i < eventParts.length; i++) {
        if (eventParts[i].forEventId && eventParts[i].isPreEvent) {
            const foundPart = uniquePreBufferPartForEventIds.find((e) => e === eventParts[i].forEventId);
            if (foundPart) {
                continue;
            }
            else {
                uniquePreBufferPartForEventIds.push(eventParts[i].forEventId);
            }
        }
    }
    for (let i = 0; i < uniquePreBufferPartForEventIds.length; i++) {
        const returnedEventPartTotal = modifyEventPartsForSingularPreBufferTime(eventParts, uniquePreBufferPartForEventIds[i]);
        preBufferEventPartsTotal.push(...returnedEventPartTotal);
    }
    const eventPartsFiltered = _.differenceBy(eventParts, preBufferEventPartsTotal, 'id');
    const concatenatedValues = eventPartsFiltered.concat(preBufferEventPartsTotal);
    concatenatedValues.forEach((e) => console.log(e.id, e.groupId, e.eventId, e.part, e.lastPart, e.startDate, e.endDate, e?.forEventId, `e.id, e.eventId, e.actualId, e.part, e.lastPart, e.startDate, e.endDate, e?.forEventId,  inside modifyEventPartsForMultiplePreBufferTime`));
    return concatenatedValues;
};
export const modifyEventPartsForMultiplePostBufferTime = (eventParts) => {
    const uniquePostBufferPartForEventIds = [];
    const postBufferEventPartsTotal = [];
    for (let i = 0; i < eventParts.length; i++) {
        if (eventParts[i].forEventId && eventParts[i].isPostEvent) {
            const foundPart = uniquePostBufferPartForEventIds.find((e) => e === eventParts[i].forEventId);
            if (foundPart) {
                continue;
            }
            else {
                uniquePostBufferPartForEventIds.push(eventParts[i].forEventId);
            }
        }
    }
    for (let i = 0; i < uniquePostBufferPartForEventIds.length; i++) {
        const returnedEventPartTotal = modifyEventPartsForSingularPostBufferTime(eventParts, uniquePostBufferPartForEventIds[i]);
        postBufferEventPartsTotal.push(...returnedEventPartTotal);
    }
    const eventPartsFiltered = _.differenceBy(eventParts, postBufferEventPartsTotal, 'id');
    const concatenatedValues = eventPartsFiltered.concat(postBufferEventPartsTotal);
    concatenatedValues.forEach((e) => console.log(e.id, e.groupId, e.eventId, e.part, e.lastPart, e.startDate, e.endDate, e?.forEventId, `e.id, e.groupId, e.eventId, e.part, e.lastPart, e.startDate, e.endDate, e?.forEventId,  inside modifyEventPartsForMultiplePostBufferTime`));
    return concatenatedValues;
};
export const modifyEventPartsForSingularPostBufferTime = (eventParts, forEventId) => {
    const postBufferAfterEventParts = [];
    const postBufferActualEventParts = [];
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
    const postBufferActualEventPartsSorted = postBufferActualEventParts.sort((a, b) => a.part - b.part);
    const postBufferAfterEventPartsSorted = postBufferAfterEventParts.sort((a, b) => a.part - b.part);
    const postBufferEventPartsTotal = postBufferActualEventPartsSorted.concat(postBufferAfterEventPartsSorted);
    const preEventId = postBufferEventPartsTotal?.[0]?.preEventId;
    const actualEventPreviousLastPart = postBufferEventPartsTotal?.[0]?.lastPart;
    for (let i = 0; i < postBufferEventPartsTotal.length; i++) {
        if (preEventId) {
            postBufferEventPartsTotal[i].lastPart =
                actualEventPreviousLastPart + postBufferAfterEventPartsSorted.length;
        }
        else {
            postBufferEventPartsTotal[i].part = i + 1;
            postBufferEventPartsTotal[i].lastPart = postBufferEventPartsTotal.length;
        }
    }
    for (let i = 0; i < postBufferAfterEventPartsSorted.length; i++) {
        if (postBufferEventPartsTotal?.[postBufferActualEventPartsSorted?.length + i]) {
            postBufferEventPartsTotal[postBufferActualEventPartsSorted?.length + i].part = actualEventPreviousLastPart + i + 1;
        }
    }
    const preEventParts = eventParts.filter((e) => e.eventId === preEventId);
    const preBufferEventParts = preEventParts?.map((e) => ({
        ...e,
        groupId: postBufferGroupId,
        lastPart: actualEventPreviousLastPart + postBufferAfterEventPartsSorted.length,
    }));
    const concatenatedValues = preBufferEventParts.concat(postBufferEventPartsTotal);
    concatenatedValues.forEach((e) => console.log(e.id, e.groupId, e.eventId, e.part, e.lastPart, e.startDate, e.endDate, e?.forEventId, `e.id, e.groupId, e.eventId, e.part, e.lastPart, e.startDate, e.endDate, e?.forEventId,  inside modifyEventPartsForSinglularPostBufferTime`));
    return concatenatedValues;
};
export const formatEventTypeToPlannerEvent = (event, userPreference, workTimes, hostTimezone) => {
    const { allDay, part, forEventId, groupId, eventId, isBreak, isExternalMeeting, isExternalMeetingModifiable, isMeeting, isMeetingModifiable, isPostEvent, isPreEvent, modifiable, negativeImpactDayOfWeek, negativeImpactScore, negativeImpactTime, positiveImpactDayOfWeek, positiveImpactScore, positiveImpactTime, preferredDayOfWeek, preferredEndTimeRange, preferredStartTimeRange, preferredTime, priority, startDate, endDate, taskId, userId, weeklyTaskList, dailyTaskList, hardDeadline, softDeadline, recurringEventId, lastPart, preferredTimeRanges, hostId, meetingId, timezone, meetingPart, meetingLastPart, } = event;
    if (allDay) {
        return null;
    }
    const totalWorkingHours = convertToTotalWorkingHoursForInternalAttendee(userPreference, dayjs(event.startDate.slice(0, 19))
        .tz(event.timezone, true)
        .tz(hostTimezone)
        .format(), hostTimezone);
    const user = {
        id: event.userId,
        maxWorkLoadPercent: userPreference.maxWorkLoadPercent,
        backToBackMeetings: userPreference.backToBackMeetings,
        maxNumberOfMeetings: userPreference.maxNumberOfMeetings,
        minNumberOfBreaks: userPreference.minNumberOfBreaks,
        workTimes,
        hostId,
    };
    const adjustedPositiveImpactTime = (positiveImpactTime &&
        dayjs(startDate?.slice(0, 19))
            .tz(timezone)
            .hour(parseInt(positiveImpactTime.slice(0, 2), 10))
            .minute(parseInt(positiveImpactTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm:ss')) ||
        undefined;
    const adjustedNegativeImpactTime = (negativeImpactTime &&
        dayjs(startDate?.slice(0, 19))
            .tz(timezone)
            .hour(parseInt(negativeImpactTime.slice(0, 2), 10))
            .minute(parseInt(negativeImpactTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm:ss')) ||
        undefined;
    const adjustedPreferredTime = (preferredTime &&
        dayjs(startDate?.slice(0, 19))
            .tz(timezone)
            .hour(parseInt(preferredTime.slice(0, 2), 10))
            .minute(parseInt(preferredTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm:ss')) ||
        undefined;
    const adjustedPreferredStartTimeRange = (preferredStartTimeRange &&
        dayjs(startDate?.slice(0, 19))
            .tz(timezone)
            .hour(parseInt(preferredStartTimeRange.slice(0, 2), 10))
            .minute(parseInt(preferredStartTimeRange.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm:ss')) ||
        undefined;
    const adjustedPreferredEndTimeRange = (preferredEndTimeRange &&
        dayjs(startDate?.slice(0, 19))
            .tz(timezone)
            .hour(parseInt(preferredEndTimeRange.slice(0, 2), 10))
            .minute(parseInt(preferredEndTimeRange.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm:ss')) ||
        undefined;
    const adjustedPreferredTimeRanges = preferredTimeRanges?.map((e) => ({
        dayOfWeek: dayOfWeekIntToString?.[e?.dayOfWeek] ?? null,
        startTime: dayjs(startDate?.slice(0, 19))
            .tz(timezone)
            .hour(parseInt(e?.startTime.slice(0, 2), 10))
            .minute(parseInt(e?.startTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm:ss'),
        endTime: dayjs(startDate?.slice(0, 19))
            .tz(timezone)
            .hour(parseInt(e?.endTime.slice(0, 2), 10))
            .minute(parseInt(e?.endTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm:ss'),
        eventId,
        userId,
        hostId,
    })) ?? null;
    const eventPlannerRequestBody = {
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
        positiveImpactDayOfWeek: dayOfWeekIntToString[positiveImpactDayOfWeek] ?? null,
        positiveImpactTime: adjustedPositiveImpactTime,
        negativeImpactDayOfWeek: dayOfWeekIntToString[negativeImpactDayOfWeek] ?? null,
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
export const formatEventTypeToPlannerEventForExternalAttendee = (event, workTimes, attendeeEvents, hostTimezone) => {
    const { allDay, part, forEventId, groupId, eventId, isBreak, isExternalMeeting, isExternalMeetingModifiable, isMeeting, isMeetingModifiable, isPostEvent, isPreEvent, modifiable, negativeImpactDayOfWeek, negativeImpactScore, negativeImpactTime, positiveImpactDayOfWeek, positiveImpactScore, positiveImpactTime, preferredDayOfWeek, preferredEndTimeRange, preferredStartTimeRange, preferredTime, priority, startDate, endDate, taskId, userId, weeklyTaskList, dailyTaskList, hardDeadline, softDeadline, recurringEventId, lastPart, preferredTimeRanges, hostId, meetingId, timezone, meetingPart, meetingLastPart, } = event;
    if (allDay) {
        return null;
    }
    const totalWorkingHours = convertToTotalWorkingHoursForExternalAttendee(attendeeEvents, dayjs(event.startDate.slice(0, 19))
        .tz(event.timezone, true)
        .tz(hostTimezone)
        .format(), hostTimezone, event?.timezone);
    const user = {
        id: event.userId,
        maxWorkLoadPercent: 100,
        backToBackMeetings: false,
        maxNumberOfMeetings: 99,
        minNumberOfBreaks: 0,
        workTimes,
        hostId,
    };
    const adjustedPositiveImpactTime = (positiveImpactTime &&
        dayjs()
            .tz(timezone)
            .hour(parseInt(positiveImpactTime.slice(0, 2), 10))
            .minute(parseInt(positiveImpactTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm:ss')) ||
        undefined;
    const adjustedNegativeImpactTime = (negativeImpactTime &&
        dayjs()
            .tz(timezone)
            .hour(parseInt(negativeImpactTime.slice(0, 2), 10))
            .minute(parseInt(negativeImpactTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm:ss')) ||
        undefined;
    const adjustedPreferredTime = (preferredTime &&
        dayjs()
            .tz(timezone)
            .hour(parseInt(preferredTime.slice(0, 2), 10))
            .minute(parseInt(preferredTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm:ss')) ||
        undefined;
    const adjustedPreferredStartTimeRange = (preferredStartTimeRange &&
        dayjs()
            .tz(timezone)
            .hour(parseInt(preferredStartTimeRange.slice(0, 2), 10))
            .minute(parseInt(preferredStartTimeRange.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm:ss')) ||
        undefined;
    const adjustedPreferredEndTimeRange = (preferredEndTimeRange &&
        dayjs()
            .tz(timezone)
            .hour(parseInt(preferredEndTimeRange.slice(0, 2), 10))
            .minute(parseInt(preferredEndTimeRange.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm:ss')) ||
        undefined;
    const adjustedPreferredTimeRanges = preferredTimeRanges?.map((e) => ({
        dayOfWeek: dayOfWeekIntToString?.[e?.dayOfWeek] ?? null,
        startTime: dayjs()
            .tz(timezone)
            .hour(parseInt(e?.startTime.slice(0, 2), 10))
            .minute(parseInt(e?.startTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm:ss'),
        endTime: dayjs()
            .tz(timezone)
            .hour(parseInt(e?.endTime.slice(0, 2), 10))
            .minute(parseInt(e?.endTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm:ss'),
        eventId,
        userId,
        hostId,
    })) ?? null;
    const eventPlannerRequestBody = {
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
        positiveImpactDayOfWeek: dayOfWeekIntToString[positiveImpactDayOfWeek] ?? null,
        positiveImpactTime: adjustedPositiveImpactTime,
        negativeImpactDayOfWeek: dayOfWeekIntToString[negativeImpactDayOfWeek] ?? null,
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
export const convertMeetingPlusTypeToEventPlusType = (event) => {
    const newEvent = {
        ...event,
        preferredTimeRanges: event?.preferredTimeRanges?.map((pt) => ({
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
export const setPreferredTimeForUnModifiableEvent = (event, timezone) => {
    if (!event?.modifiable) {
        if (!event?.preferredDayOfWeek && !event?.preferredTime) {
            const newEvent = {
                ...event,
                preferredDayOfWeek: dayOfWeekIntToString[getISODay(dayjs(event.startDate.slice(0, 19)).tz(timezone, true).toDate())],
                preferredTime: dayjs(event.startDate.slice(0, 19))
                    .tz(timezone, true)
                    .format('HH:mm:ss'),
            };
            return newEvent;
        }
        return event;
    }
    return event;
};
export const listEventsWithIds = async (ids) => {
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
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' unable to list ids with ids');
    }
};
export const tagEventsForDailyOrWeeklyTask = async (events) => {
    try {
        const filteredEvents = events.filter((e) => e.recurringEventId);
        if (filteredEvents?.length > 0) {
            const originalEvents = await listEventsWithIds(_.uniq(filteredEvents.map((e) => e?.recurringEventId)));
            if (originalEvents?.length > 0) {
                const taggedFilteredEvents = filteredEvents.map((e) => tagEventForDailyOrWeeklyTask(e, originalEvents.find((oe) => oe.id === e.recurringEventId)));
                const newEvents = events.map((e) => {
                    if (e?.recurringEventId) {
                        const taggedFilteredEvent = taggedFilteredEvents.find((te) => te?.eventId === e?.eventId);
                        if (taggedFilteredEvent?.eventId) {
                            return taggedFilteredEvent;
                        }
                        else {
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
    }
    catch (e) {
        console.log(e, ' unable to to tag events for daily or weekly task');
    }
};
export const tagEventForDailyOrWeeklyTask = (eventToSubmit, event) => {
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
export const generateUserPlannerRequestBody = (userPreference, userId, workTimes, hostId) => {
    const { maxWorkLoadPercent, backToBackMeetings, maxNumberOfMeetings, minNumberOfBreaks, } = userPreference;
    const user = {
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
export const generateUserPlannerRequestBodyForExternalAttendee = (userId, workTimes, hostId) => {
    const user = {
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
export const processEventsForOptaPlannerForMainHost = async (mainHostId, allHostEvents, windowStartDate, windowEndDate, hostTimezone, oldHostEvents, newHostBufferTimes) => {
    try {
        const newBufferTimeArray = [];
        for (const newHostBufferTime of newHostBufferTimes) {
            if (newHostBufferTime?.beforeEvent?.id) {
                console.log(newHostBufferTime?.beforeEvent, ' newTimeBlocking?.beforeEvent');
                newBufferTimeArray.push(newHostBufferTime.beforeEvent);
            }
            if (newHostBufferTime?.afterEvent?.id) {
                console.log(newHostBufferTime?.afterEvent, ' newTimeBlocking?.afterEvent');
                newBufferTimeArray.push(newHostBufferTime.afterEvent);
            }
        }
        const modifiedAllHostEvents = _.cloneDeep(allHostEvents);
        if (newBufferTimeArray?.length > 0) {
            modifiedAllHostEvents.push(...newBufferTimeArray);
        }
        const userPreferences = await getUserPreferences(mainHostId);
        const globalPrimaryCalendar = await getGlobalCalendar(mainHostId);
        const diffDays = dayjs(windowEndDate.slice(0, 19)).diff(dayjs(windowStartDate.slice(0, 19)), 'day');
        const modifiedAllEventsWithBreaks = [];
        const startDatesForEachDay = [];
        for (let i = 0; i <= diffDays; i++) {
            startDatesForEachDay.push(dayjs(windowStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .add(i, 'day')
                .format());
        }
        let parentBreaks = [];
        const breaks = await generateBreakEventsForDate(userPreferences, mainHostId, windowStartDate, windowEndDate, hostTimezone, globalPrimaryCalendar?.id);
        breaks.forEach((b) => console.log(b, ' generatedBreaks'));
        if (breaks?.length > 0) {
            const allEventsWithDuplicateFreeBreaks = _.differenceBy(modifiedAllHostEvents, breaks, 'id');
            modifiedAllEventsWithBreaks.push(...allEventsWithDuplicateFreeBreaks);
            modifiedAllEventsWithBreaks.push(...breaks);
            parentBreaks.push(...breaks);
        }
        else {
            modifiedAllEventsWithBreaks.push(...modifiedAllHostEvents);
        }
        const workTimes = generateWorkTimesForInternalAttendee(mainHostId, mainHostId, userPreferences, hostTimezone, hostTimezone);
        const timeslots = [];
        for (let i = 0; i < startDatesForEachDay.length; i++) {
            if (i === 0) {
                const timeslotsForDay = await generateTimeSlotsLiteForInternalAttendee(startDatesForEachDay?.[i], mainHostId, userPreferences, hostTimezone, hostTimezone, true);
                timeslots.push(...timeslotsForDay);
                continue;
            }
            const timeslotsForDay = await generateTimeSlotsLiteForInternalAttendee(startDatesForEachDay?.[i], mainHostId, userPreferences, hostTimezone, hostTimezone, false);
            timeslots.push(...timeslotsForDay);
        }
        const filteredAllEvents = _.uniqBy(modifiedAllEventsWithBreaks.filter((e) => validateEventDates(e, userPreferences)), 'id');
        let eventParts = [];
        const eventPartMinisAccumulated = [];
        for (const event of filteredAllEvents) {
            const eventPartMinis = generateEventPartsLite(event, mainHostId);
            eventPartMinisAccumulated.push(...eventPartMinis);
        }
        const modifiedEventPartMinisPreBuffer = modifyEventPartsForMultiplePreBufferTime(eventPartMinisAccumulated);
        const modifiedEventPartMinisPreAndPostBuffer = modifyEventPartsForMultiplePostBufferTime(modifiedEventPartMinisPreBuffer);
        const formattedEventParts = modifiedEventPartMinisPreAndPostBuffer.map((e) => formatEventTypeToPlannerEvent(e, userPreferences, workTimes, hostTimezone));
        if (formattedEventParts?.length > 0) {
            eventParts.push(...formattedEventParts);
        }
        if (eventParts?.length > 0) {
            eventParts.forEach((e) => console.log(e, ' eventParts after formatting'));
            const newEventPartsWithPreferredTimeSet = eventParts.map((e) => setPreferredTimeForUnModifiableEvent(e, allHostEvents.find((f) => f.id === e.eventId)?.timezone));
            newEventPartsWithPreferredTimeSet.forEach((e) => console.log(e, ' newEventPartsWithPreferredTimeSet'));
            const newEventParts = await tagEventsForDailyOrWeeklyTask(newEventPartsWithPreferredTimeSet);
            newEventParts.forEach((e) => console.log(e, ' newEventParts after tagEventsForDailyOrWeeklyTask'));
            const userPlannerRequestBody = generateUserPlannerRequestBody(userPreferences, userPreferences.userId, workTimes, mainHostId);
            console.log(userPlannerRequestBody, ' userPlannerRequestBody');
            const modifiedNewEventParts = newEventParts.map((eventPart) => {
                const oldEvent = filteredAllEvents.find((event) => event.id === eventPart.eventId);
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
    }
    catch (e) {
        console.log(e, ' unable to process events for optaplanner for host attendee');
    }
};
export const processEventsForOptaPlannerForInternalAttendees = async (mainHostId, allEvents, windowStartDate, windowEndDate, hostTimezone, internalAttendees, oldEvents, oldMeetingEvents, newMeetingEvents, newHostBufferTimes) => {
    try {
        const newBufferTimeArray = [];
        for (const newHostBufferTime of newHostBufferTimes) {
            if (newHostBufferTime?.beforeEvent?.id) {
                console.log(newHostBufferTime?.beforeEvent, ' newTimeBlocking?.beforeEvent');
                newBufferTimeArray.push(newHostBufferTime.beforeEvent);
            }
            if (newHostBufferTime?.afterEvent?.id) {
                console.log(newHostBufferTime?.afterEvent, ' newTimeBlocking?.afterEvent');
                newBufferTimeArray.push(newHostBufferTime.afterEvent);
            }
        }
        oldMeetingEvents?.forEach((o) => console.log(o, ' oldMeetingEvents'));
        internalAttendees?.forEach((i) => console.log(i, ' internalAttendees inside processEventsForOptaPlannerForInternalAttendees'));
        const filteredOldMeetingEvents = oldMeetingEvents
            ?.map((m) => {
            const foundIndex = allEvents?.findIndex((a) => a?.id === m?.id);
            if (foundIndex > -1) {
                return null;
            }
            return m;
        })
            ?.filter((e) => !!e);
        filteredOldMeetingEvents?.forEach((e) => console.log(e, ' filteredOldMeetingEvents'));
        const modifiedAllEvents = _.cloneDeep(allEvents)?.filter((e) => {
            if (filteredOldMeetingEvents?.[0]?.id) {
                const foundIndex = filteredOldMeetingEvents?.findIndex((m) => m?.id === e?.id);
                if (foundIndex > -1) {
                    return false;
                }
                return true;
            }
            return true;
        });
        if (filteredOldMeetingEvents?.[0]?.id) {
            modifiedAllEvents.push(...filteredOldMeetingEvents?.map((a) => convertMeetingPlusTypeToEventPlusType(a)));
        }
        if (newBufferTimeArray?.length > 0) {
            modifiedAllEvents.push(...newBufferTimeArray);
        }
        if (newMeetingEvents?.length > 0) {
            modifiedAllEvents.push(...newMeetingEvents?.map((m) => convertMeetingPlusTypeToEventPlusType(m)));
        }
        modifiedAllEvents?.forEach((e) => console.log(e, ' modifiedAllEvents'));
        const unfilteredUserPreferences = [];
        for (const internalAttendee of internalAttendees) {
            const userPreference = await getUserPreferences(internalAttendee?.userId);
            unfilteredUserPreferences.push(userPreference);
        }
        const userPreferences = _.uniqWith(unfilteredUserPreferences, _.isEqual);
        const unfilteredGlobalPrimaryCalendars = [];
        for (const internalAttendee of internalAttendees) {
            const globalPrimaryCalendar = await getGlobalCalendar(internalAttendee?.userId);
            unfilteredGlobalPrimaryCalendars.push(globalPrimaryCalendar);
        }
        const globalPrimaryCalendars = _.uniqWith(unfilteredGlobalPrimaryCalendars, _.isEqual);
        globalPrimaryCalendars?.forEach((c) => console.log(c, ' globalPrimaryCalendars'));
        const modifiedAllEventsWithBreaks = [];
        let parentBreaks = [];
        for (const userPreference of userPreferences) {
            const globalPrimaryCalendar = globalPrimaryCalendars?.find((g) => g?.userId === userPreference?.userId);
            if (!globalPrimaryCalendar) {
                throw new Error('no global primary calendar found');
            }
            const userId = userPreference?.userId;
            const breaks = await generateBreakEventsForDate(userPreference, userId, windowStartDate, windowEndDate, hostTimezone, globalPrimaryCalendar?.id);
            breaks.forEach((b) => console.log(b, ' generatedBreaks'));
            if (breaks?.length > 0) {
                const allEventsWithDuplicateFreeBreaks = _.differenceBy(modifiedAllEvents, breaks, 'id');
                modifiedAllEventsWithBreaks.push(...allEventsWithDuplicateFreeBreaks?.filter((e) => e?.userId === userId));
                modifiedAllEventsWithBreaks.push(...breaks);
                parentBreaks.push(...breaks);
            }
            else {
                modifiedAllEventsWithBreaks.push(...modifiedAllEvents?.filter((e) => e?.userId === userId));
            }
        }
        modifiedAllEventsWithBreaks?.forEach((m) => console.log(m, ' modifiedAllEventsWithBreaks'));
        const diffDays = dayjs(windowEndDate.slice(0, 19)).diff(dayjs(windowStartDate.slice(0, 19)), 'day');
        console.log(diffDays, windowEndDate, windowStartDate, ' diffDays, windowEndDate, windowStartDate');
        const startDatesForEachDay = [];
        for (let i = 0; i <= diffDays; i++) {
            startDatesForEachDay.push(dayjs(windowStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .add(i, 'day')
                .format());
        }
        console.log(startDatesForEachDay, ' startDatesForEachDay');
        const unfilteredWorkTimes = [];
        for (const internalAttendee of internalAttendees) {
            const userPreference = userPreferences.find((u) => u.userId === internalAttendee.userId);
            const attendeeTimezone = internalAttendee?.timezone;
            const workTimesForAttendee = generateWorkTimesForInternalAttendee(mainHostId, internalAttendee.userId, userPreference, hostTimezone, attendeeTimezone);
            unfilteredWorkTimes.push(...workTimesForAttendee);
        }
        console.log(unfilteredWorkTimes, 'unfilteredWorkTimes');
        const workTimes = _.uniqWith(unfilteredWorkTimes, _.isEqual);
        const unfilteredTimeslots = [];
        const timeslots = [];
        for (let i = 0; i < startDatesForEachDay.length; i++) {
            if (i === 0) {
                for (const internalAttendee of internalAttendees) {
                    const userPreference = userPreferences.find((u) => u.userId === internalAttendee.userId);
                    const timeslotsForDay = await generateTimeSlotsLiteForInternalAttendee(startDatesForEachDay?.[i], mainHostId, userPreference, hostTimezone, internalAttendee?.timezone, true);
                    unfilteredTimeslots.push(...timeslotsForDay);
                }
                continue;
            }
            for (const internalAttendee of internalAttendees) {
                const userPreference = userPreferences.find((u) => u.userId === internalAttendee.userId);
                const timeslotsForDay = await generateTimeSlotsLiteForInternalAttendee(startDatesForEachDay?.[i], mainHostId, userPreference, hostTimezone, internalAttendee?.timezone, false);
                unfilteredTimeslots.push(...timeslotsForDay);
            }
        }
        timeslots.push(..._.uniqWith(unfilteredTimeslots, _.isEqual));
        const unfilteredAllEvents = [];
        for (const internalAttendee of internalAttendees) {
            const userPreference = userPreferences.find((u) => u.userId === internalAttendee.userId);
            const modifiedAllEventsWithBreaksWithUser = modifiedAllEventsWithBreaks.filter((e) => e.userId === internalAttendee.userId);
            const events = modifiedAllEventsWithBreaksWithUser.filter((e) => validateEventDates(e, userPreference));
            unfilteredAllEvents.push(...events);
        }
        unfilteredAllEvents?.forEach((e) => console.log(e, ' unfilteredAllEvents'));
        const filteredAllEvents = _.uniqBy(unfilteredAllEvents, 'id');
        filteredAllEvents?.forEach((e) => console.log(e, ' filteredAllEvents'));
        let eventParts = [];
        const eventPartMinisAccumulated = [];
        for (const event of filteredAllEvents) {
            const eventPartMinis = generateEventPartsLite(event, mainHostId);
            eventPartMinisAccumulated.push(...eventPartMinis);
        }
        eventPartMinisAccumulated?.forEach((e) => console.log(e, ' eventPartMinisAccumulated'));
        const modifiedEventPartMinisPreBuffer = modifyEventPartsForMultiplePreBufferTime(eventPartMinisAccumulated);
        const modifiedEventPartMinisPreAndPostBuffer = modifyEventPartsForMultiplePostBufferTime(modifiedEventPartMinisPreBuffer);
        modifiedEventPartMinisPreAndPostBuffer?.forEach((e) => console.log(e, ' modifiedEventPartMinisPreAndPostBuffer'));
        const formattedEventParts = [];
        for (const userPreference of userPreferences) {
            const formattedEventPartsForUser = modifiedEventPartMinisPreAndPostBuffer
                ?.filter((e) => e?.userId === userPreference?.userId)
                ?.map((e) => formatEventTypeToPlannerEvent(e, userPreference, workTimes, hostTimezone));
            formattedEventPartsForUser?.forEach((e) => console.log(e, ' formattedEventPartsForUser'));
            formattedEventParts.push(...formattedEventPartsForUser);
        }
        formattedEventParts?.forEach((e) => console.log(e, ' formattedEventParts'));
        if (formattedEventParts.length > 0) {
            eventParts.push(..._.uniqWith(formattedEventParts, _.isEqual));
        }
        if (eventParts.length > 0) {
            eventParts.forEach((e) => console.log(e, ' eventParts after formatting'));
            const newEventPartsWithPreferredTimeSet = eventParts.map((e) => setPreferredTimeForUnModifiableEvent(e, allEvents.find((f) => f.id === e.eventId)?.timezone));
            newEventPartsWithPreferredTimeSet.forEach((e) => console.log(e, ' newEventPartsWithPreferredTimeSet'));
            const newEventParts = await tagEventsForDailyOrWeeklyTask(newEventPartsWithPreferredTimeSet);
            newEventParts.forEach((e) => console.log(e, ' newEventParts after tagEventsForDailyOrWeeklyTask'));
            const unfilteredUserList = [];
            for (const userPreference of userPreferences) {
                const userPlannerRequestBody = generateUserPlannerRequestBody(userPreference, userPreference?.userId, workTimes, mainHostId);
                console.log(userPlannerRequestBody, ' userPlannerRequestBody');
                unfilteredUserList.push(userPlannerRequestBody);
            }
            const userList = _.uniqWith(unfilteredUserList, _.isEqual);
            const modifiedNewEventParts = newEventParts.map((eventPart) => {
                const oldEvent = filteredAllEvents.find((event) => event.id === eventPart.eventId);
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
            modifiedNewEventParts?.forEach((e) => console.log(e, ' modifiedNewEventParts'));
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
    }
    catch (e) {
        console.log(e, ' unable to process events for optaplanner for each attendee');
    }
};
export const convertMeetingAssistEventTypeToEventPlusType = (event, userId) => {
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
export const generateWorkTimesForExternalAttendee = (hostId, userId, attendeeEvents, hostTimezone, userTimezone) => {
    const daysInWeek = 7;
    const workTimes = [];
    for (let i = 0; i < daysInWeek; i++) {
        const dayOfWeekInt = i + 1;
        const sameDayEvents = attendeeEvents.filter((e) => getISODay(dayjs(e.startDate.slice(0, 19))
            .tz(e.timezone || userTimezone, true)
            .tz(hostTimezone)
            .toDate()) ===
            i + 1);
        const minStartDate = _.minBy(sameDayEvents, (e) => dayjs(e.startDate.slice(0, 19))
            .tz(e.timezone || userTimezone, true)
            .tz(hostTimezone)
            .unix());
        const maxEndDate = _.maxBy(sameDayEvents, (e) => dayjs(e.endDate.slice(0, 19))
            .tz(e.timezone || userTimezone, true)
            .tz(hostTimezone)
            .unix());
        const startHour = dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .hour();
        const startMinute = dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(0), dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(15), 'minute', '[)')
            ? 0
            : dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(15), dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30), 'minute', '[)')
                ? 15
                : dayjs(minStartDate.startDate.slice(0, 19))
                    .tz(minStartDate.timezone || userTimezone, true)
                    .tz(hostTimezone)
                    .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
                    .tz(minStartDate.timezone || userTimezone, true)
                    .tz(hostTimezone)
                    .minute(30), dayjs(minStartDate.startDate.slice(0, 19))
                    .tz(minStartDate.timezone || userTimezone, true)
                    .tz(hostTimezone)
                    .minute(45), 'minute', '[)')
                    ? 30
                    : 45;
        let endHour = dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .hour();
        const endMinute = dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(0), dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(15), 'minute', '[)')
            ? 15
            : dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(15), dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30), 'minute', '[)')
                ? 30
                : dayjs(maxEndDate.endDate.slice(0, 19))
                    .tz(maxEndDate.timezone || userTimezone, true)
                    .tz(hostTimezone)
                    .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
                    .tz(maxEndDate.timezone || userTimezone, true)
                    .tz(hostTimezone)
                    .minute(30), dayjs(maxEndDate.endDate.slice(0, 19))
                    .tz(maxEndDate.timezone || userTimezone, true)
                    .tz(hostTimezone)
                    .minute(45), 'minute', '[)')
                    ? 45
                    : 0;
        if (endMinute === 0) {
            if (endHour < 23) {
                endHour += 1;
            }
        }
        workTimes.push({
            dayOfWeek: dayOfWeekIntToString[dayOfWeekInt],
            startTime: dayjs(setISODay(dayjs()
                .hour(startHour)
                .minute(startMinute)
                .tz(hostTimezone, true)
                .toDate(), i + 1))
                .tz(hostTimezone)
                .format('HH:mm:ss'),
            endTime: dayjs(setISODay(dayjs()
                .hour(endHour)
                .minute(endMinute)
                .tz(hostTimezone, true)
                .toDate(), i + 1))
                .tz(hostTimezone)
                .format('HH:mm:ss'),
            hostId,
            userId,
        });
    }
    return workTimes;
};
export const generateTimeSlotsForExternalAttendee = (hostStartDate, hostId, attendeeEvents, hostTimezone, userTimezone, isFirstDay) => {
    if (isFirstDay) {
        const dayOfWeekIntByHost = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
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
            .isBetween(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(0), dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(15), 'minute', '[)')
            ? 0
            : dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .isBetween(dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(15), dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(30), 'minute', '[)')
                ? 15
                : dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .isBetween(dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .minute(30), dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .minute(45), 'minute', '[)')
                    ? 30
                    : 45;
        const sameDayEvents = attendeeEvents.filter((e) => getISODay(dayjs(e.startDate.slice(0, 19))
            .tz(userTimezone, true)
            .tz(hostTimezone)
            .toDate()) === dayOfWeekIntByHost);
        // const minStartDate = _.minBy(sameDayEvents, (e) => dayjs(e.startDate.slice(0, 19)).tz(userTimezone, true).tz(hostTimezone).unix())
        const maxEndDate = _.maxBy(sameDayEvents, (e) => dayjs(e.endDate.slice(0, 19))
            .tz(userTimezone, true)
            .tz(hostTimezone)
            .unix());
        let workEndHourByHost = dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .hour();
        const workEndMinuteByHost = dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(0), dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(15), 'minute', '[)')
            ? 15
            : dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(15), dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30), 'minute', '[)')
                ? 30
                : dayjs(maxEndDate.endDate.slice(0, 19))
                    .tz(maxEndDate.timezone || userTimezone, true)
                    .tz(hostTimezone)
                    .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
                    .tz(maxEndDate.timezone || userTimezone, true)
                    .tz(hostTimezone)
                    .minute(30), dayjs(maxEndDate.endDate.slice(0, 19))
                    .tz(maxEndDate.timezone || userTimezone, true)
                    .tz(hostTimezone)
                    .minute(45), 'minute', '[)')
                    ? 45
                    : 0;
        if (workEndMinuteByHost === 0) {
            if (workEndHourByHost < 23) {
                workEndHourByHost += 1;
            }
        }
        const minStartDate = _.minBy(sameDayEvents, (e) => dayjs(e.startDate.slice(0, 19))
            .tz(userTimezone, true)
            .tz(hostTimezone)
            .unix());
        const workStartHourByHost = dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .hour();
        const workStartMinuteByHost = dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(0), dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(15), 'minute', '[)')
            ? 0
            : dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(15), dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30), 'minute', '[)')
                ? 15
                : dayjs(minStartDate.startDate.slice(0, 19))
                    .tz(minStartDate.timezone || userTimezone, true)
                    .tz(hostTimezone)
                    .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
                    .tz(minStartDate.timezone || userTimezone, true)
                    .tz(hostTimezone)
                    .minute(30), dayjs(minStartDate.startDate.slice(0, 19))
                    .tz(minStartDate.timezone || userTimezone, true)
                    .tz(hostTimezone)
                    .minute(45), 'minute', '[)')
                    ? 30
                    : 45;
        // change to work start time as work start time is  after host start time
        if (dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isBefore(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(workStartHourByHost)
            .minute(workStartMinuteByHost))) {
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
            const timeSlots = [];
            console.log(hostStartDate, dayOfWeekIntByHost, dayOfMonthByHost, startHourOfHostDateByHost, startMinuteOfHostDateByHost, workEndHourByHost, workEndMinuteByHost, timezone, `startDate,  dayOfWeekIntByHost, dayOfMonthByHost, startHourByHost, startMinuteByHost, endHourByHost, endMinuteByHost totalMinutes, timezone, inside firstDay inside generateTimeslots`);
            for (let i = 0; i < totalMinutes; i += 15) {
                timeSlots.push({
                    dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
                    startTime: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .hour(startHourOfHostDateByHost)
                        .minute(startMinuteOfHostDateByHost)
                        .add(i, 'minute')
                        .format('HH:mm:ss'),
                    endTime: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .hour(startHourOfHostDateByHost)
                        .minute(startMinuteOfHostDateByHost)
                        .add(i + 15, 'minute')
                        .format('HH:mm:ss'),
                    hostId,
                    monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
                    date: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .format('YYYY-MM-DD'),
                });
            }
            console.log(timeSlots, ' timeSlots inside generateTimeSlots for first day where startDate is before work start time');
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
        const timeSlots = [];
        console.log(hostStartDate, dayOfWeekIntByHost, dayOfMonthByHost, startHourOfHostDateByHost, startMinuteOfHostDateByHost, workEndHourByHost, workEndMinuteByHost, hostTimezone, `startDate,  dayOfWeekIntByHost, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`);
        for (let i = 0; i < totalMinutes; i += 15) {
            timeSlots.push({
                dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
                startTime: dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .hour(startHourOfHostDateByHost)
                    .minute(startMinuteOfHostDateByHost)
                    .add(i, 'minute')
                    .format('HH:mm:ss'),
                endTime: dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .hour(startHourOfHostDateByHost)
                    .minute(startMinuteOfHostDateByHost)
                    .add(i + 15, 'minute')
                    .format('HH:mm:ss'),
                hostId,
                monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
                date: dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .format('YYYY-MM-DD'),
            });
        }
        console.log(timeSlots, ' timeSlots inside generateTimeSlots for first day');
        return timeSlots;
    }
    // not first day start from work start time schedule
    const dayOfWeekIntByHost = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
    // convert to host timezone so everything is linked to host timezone
    const monthByHost = dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .month();
    const dayOfMonthByHost = dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .date();
    const sameDayEvents = attendeeEvents.filter((e) => getISODay(dayjs(e.startDate.slice(0, 19))
        .tz(e.timezone || userTimezone, true)
        .tz(hostTimezone)
        .toDate()) === dayOfWeekIntByHost);
    const minStartDate = _.minBy(sameDayEvents, (e) => dayjs(e.startDate.slice(0, 19))
        .tz(e.timezone || userTimezone, true)
        .tz(hostTimezone)
        .unix());
    const maxEndDate = _.maxBy(sameDayEvents, (e) => dayjs(e.endDate.slice(0, 19))
        .tz(e.timezone || userTimezone, true)
        .tz(hostTimezone)
        .unix());
    let workEndHourByHost = dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .hour();
    const workEndMinuteByHost = dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(0), dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(15), 'minute', '[)')
        ? 15
        : dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(15), dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(30), 'minute', '[)')
            ? 30
            : dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30), dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(45), 'minute', '[)')
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
        .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
        .tz(minStartDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(0), dayjs(minStartDate.startDate.slice(0, 19))
        .tz(minStartDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(15), 'minute', '[)')
        ? 0
        : dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(15), dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(30), 'minute', '[)')
            ? 15
            : dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30), dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(45), 'minute', '[)')
                ? 30
                : 45;
    console.log(monthByHost, dayOfMonthByHost, workStartHourByHost, workStartMinuteByHost, workEndHourByHost, ' monthByHost, dayOfMonthByHost, workStartHourByHost, workStartMinuteByHost, workEndHourByHost');
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
    const timeSlots = [];
    for (let i = 0; i < totalMinutes; i += 15) {
        timeSlots.push({
            dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
            startTime: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(workStartHourByHost)
                .minute(workStartMinuteByHost)
                .add(i, 'minute')
                .format('HH:mm:ss'),
            endTime: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(workStartHourByHost)
                .minute(workStartMinuteByHost)
                .add(i + 15, 'minute')
                .format('HH:mm:ss'),
            hostId,
            monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
            date: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .format('YYYY-MM-DD'),
        });
    }
    console.log(timeSlots, ' timeSlots inside generateTimeSlots');
    return timeSlots;
};
export const generateTimeSlotsLiteForExternalAttendee = (hostStartDate, hostId, attendeeEvents, hostTimezone, userTimezone, isFirstDay) => {
    if (isFirstDay) {
        const dayOfWeekIntByHost = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
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
            .isBetween(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(0), dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).minute(30), 'minute', '[)')
            ? 0
            : dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .isBetween(dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(30), dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .minute(59), 'minute', '[)')
                ? 30
                : 0;
        const sameDayEvents = attendeeEvents.filter((e) => getISODay(dayjs(e.startDate.slice(0, 19))
            .tz(e?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .toDate()) === dayOfWeekIntByHost);
        // const minStartDate = _.minBy(sameDayEvents, (e) => dayjs(e.startDate.slice(0, 19)).tz(userTimezone, true).tz(hostTimezone).unix())
        const maxEndDate = _.maxBy(sameDayEvents, (e) => dayjs(e.endDate.slice(0, 19))
            .tz(e?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .unix());
        let workEndHourByHost = dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .hour();
        const workEndMinuteByHost = dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(0), dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(30), 'minute', '[)')
            ? 30
            : dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30), dayjs(maxEndDate.endDate.slice(0, 19))
                .tz(maxEndDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(59), 'minute', '[)')
                ? 0
                : 30;
        if (workEndMinuteByHost === 0) {
            if (workEndHourByHost < 23) {
                workEndHourByHost += 1;
            }
        }
        const minStartDate = _.minBy(sameDayEvents, (e) => dayjs(e.startDate.slice(0, 19))
            .tz(e?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .unix());
        const workStartHourByHost = dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .hour();
        const workStartMinuteByHost = dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(0), dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(30), 'minute', '[)')
            ? 0
            : dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(30), dayjs(minStartDate.startDate.slice(0, 19))
                .tz(minStartDate?.timezone || userTimezone, true)
                .tz(hostTimezone)
                .minute(59), 'minute', '[)')
                ? 30
                : 0;
        // change to work start time as work start time is  after host start time
        if (dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isBefore(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(workStartHourByHost)
            .minute(workStartMinuteByHost))) {
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
            const timeSlots = [];
            console.log(hostStartDate, dayOfWeekIntByHost, dayOfMonthByHost, startHourOfHostDateByHost, startMinuteOfHostDateByHost, workEndHourByHost, workEndMinuteByHost, timezone, `startDate,  dayOfWeekIntByHost, dayOfMonthByHost, startHourByHost, startMinuteByHost, endHourByHost, endMinuteByHost totalMinutes, timezone, inside firstDay inside generateTimeslots`);
            for (let i = 0; i < totalMinutes; i += 30) {
                timeSlots.push({
                    dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
                    startTime: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .hour(startHourOfHostDateByHost)
                        .minute(startMinuteOfHostDateByHost)
                        .add(i, 'minute')
                        .format('HH:mm:ss'),
                    endTime: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .hour(startHourOfHostDateByHost)
                        .minute(startMinuteOfHostDateByHost)
                        .add(i + 30, 'minute')
                        .format('HH:mm:ss'),
                    hostId,
                    monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
                    date: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .format('YYYY-MM-DD'),
                });
            }
            console.log(timeSlots, ' timeSlots inside generateTimeSlots for first day where startDate is before work start time');
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
        const timeSlots = [];
        console.log(hostStartDate, dayOfWeekIntByHost, dayOfMonthByHost, startHourOfHostDateByHost, startMinuteOfHostDateByHost, workEndHourByHost, workEndMinuteByHost, hostTimezone, `startDate,  dayOfWeekIntByHost, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`);
        for (let i = 0; i < totalMinutes; i += 30) {
            timeSlots.push({
                dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
                startTime: dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .hour(startHourOfHostDateByHost)
                    .minute(startMinuteOfHostDateByHost)
                    .add(i, 'minute')
                    .format('HH:mm:ss'),
                endTime: dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .hour(startHourOfHostDateByHost)
                    .minute(startMinuteOfHostDateByHost)
                    .add(i + 30, 'minute')
                    .format('HH:mm:ss'),
                hostId,
                monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
                date: dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .format('YYYY-MM-DD'),
            });
        }
        console.log(timeSlots, ' timeSlots inside generateTimeSlots for first day');
        return timeSlots;
    }
    // not first day start from work start time schedule
    const dayOfWeekIntByHost = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
    // convert to host timezone so everything is linked to host timezone
    const monthByHost = dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .month();
    const dayOfMonthByHost = dayjs(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .date();
    const sameDayEvents = attendeeEvents.filter((e) => getISODay(dayjs(e.startDate.slice(0, 19))
        .tz(userTimezone, true)
        .tz(hostTimezone)
        .toDate()) === dayOfWeekIntByHost);
    const minStartDate = _.minBy(sameDayEvents, (e) => dayjs(e.startDate.slice(0, 19))
        .tz(userTimezone, true)
        .tz(hostTimezone)
        .unix());
    const maxEndDate = _.maxBy(sameDayEvents, (e) => dayjs(e.endDate.slice(0, 19)).tz(userTimezone, true).tz(hostTimezone).unix());
    let workEndHourByHost = dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .hour();
    const workEndMinuteByHost = dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(0), dayjs(maxEndDate.endDate.slice(0, 19))
        .tz(maxEndDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(30), 'minute', '[)')
        ? 30
        : dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(30), dayjs(maxEndDate.endDate.slice(0, 19))
            .tz(maxEndDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(59), 'minute', '[)')
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
        .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
        .tz(minStartDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(0), dayjs(minStartDate.startDate.slice(0, 19))
        .tz(minStartDate?.timezone || userTimezone, true)
        .tz(hostTimezone)
        .minute(30), 'minute', '[)')
        ? 0
        : dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .isBetween(dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(30), dayjs(minStartDate.startDate.slice(0, 19))
            .tz(minStartDate?.timezone || userTimezone, true)
            .tz(hostTimezone)
            .minute(59), 'minute', '[)')
            ? 30
            : 0;
    console.log(monthByHost, dayOfMonthByHost, workStartHourByHost, workStartMinuteByHost, workEndHourByHost, ' monthByHost, dayOfMonthByHost, workStartHourByHost, workStartMinuteByHost, workEndHourByHost');
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
    const timeSlots = [];
    for (let i = 0; i < totalMinutes; i += 30) {
        timeSlots.push({
            dayOfWeek: dayOfWeekIntToString[dayOfWeekIntByHost],
            startTime: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(workStartHourByHost)
                .minute(workStartMinuteByHost)
                .add(i, 'minute')
                .format('HH:mm:ss'),
            endTime: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(workStartHourByHost)
                .minute(workStartMinuteByHost)
                .add(i + 30, 'minute')
                .format('HH:mm:ss'),
            hostId,
            monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
            date: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .format('YYYY-MM-DD'),
        });
    }
    console.log(timeSlots, ' timeSlots inside generateTimeSlots');
    return timeSlots;
};
export const processEventsForOptaPlannerForExternalAttendees = async (userIds, mainHostId, allExternalEvents, // These are MeetingAssistEvents from the user's calendar connection
windowStartDate, windowEndDate, hostTimezone, externalAttendees, oldExternalMeetingEvents, newMeetingEvents, meetingAssistId // Added: ID of the current meeting assist for preference lookup
) => {
    try {
        // Convert MeetingAssistEventType to EventPlusType for consistent processing
        // These events are typically from the external user's own calendar, not specific meeting invites yet
        const baseExternalUserEvents = allExternalEvents?.map((e) => convertMeetingAssistEventTypeToEventPlusType(e, externalAttendees?.find((a) => a?.id === e?.attendeeId)?.userId));
        let modifiedAllExternalEvents = [...baseExternalUserEvents];
        const oldConvertedMeetingEvents = oldExternalMeetingEvents
            ?.map((a) => convertMeetingPlusTypeToEventPlusType(a))
            ?.filter((e) => !!e);
        if (oldConvertedMeetingEvents?.length > 0) {
            modifiedAllExternalEvents.push(...oldConvertedMeetingEvents);
        }
        if (newMeetingEvents?.length > 0) {
            modifiedAllExternalEvents.push(...newMeetingEvents?.map((m) => convertMeetingPlusTypeToEventPlusType(m)));
        }
        const diffDays = dayjs(windowEndDate.slice(0, 19)).diff(dayjs(windowStartDate.slice(0, 19)), 'day');
        const startDatesForEachDay = [];
        for (let i = 0; i <= diffDays; i++) {
            startDatesForEachDay.push(dayjs(windowStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .add(i, 'day')
                .format());
        }
        const unfilteredWorkTimes = [];
        for (const externalAttendee of externalAttendees) {
            const workTimesForAttendee = generateWorkTimesForExternalAttendee(mainHostId, externalAttendee?.userId, modifiedAllExternalEvents, hostTimezone, externalAttendee?.timezone);
            unfilteredWorkTimes.push(...workTimesForAttendee);
        }
        const workTimes = _.uniqWith(unfilteredWorkTimes, _.isEqual);
        const unfilteredTimeslots = [];
        // This `timeslots` variable will be the final one passed to OptaPlanner after processing all attendees
        const timeslots = [];
        for (const externalAttendee of externalAttendees) {
            const attendeeSpecificTimeslots = [];
            let useExplicitPreferences = false;
            if (meetingAssistId && externalAttendee.id) {
                const externalPreferences = await listExternalAttendeePreferences(meetingAssistId, externalAttendee.id);
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
                            const meetingWindowDayjsStart = dayjs(windowStartDate).tz(hostTimezone, true);
                            const meetingWindowDayjsEnd = dayjs(windowEndDate).tz(hostTimezone, true);
                            if (startTimeInHostTz.isBefore(meetingWindowDayjsStart) ||
                                endTimeInHostTz.isAfter(meetingWindowDayjsEnd)) {
                                currentSlotStartTime = currentSlotEndTime;
                                continue;
                            }
                            attendeeSpecificTimeslots.push({
                                dayOfWeek: dayOfWeekIntToString[startTimeInHostTz.isoWeekday()],
                                startTime: startTimeInHostTz.format('HH:mm:ss'),
                                endTime: endTimeInHostTz.format('HH:mm:ss'),
                                hostId: mainHostId,
                                monthDay: formatToMonthDay(startTimeInHostTz.month(), startTimeInHostTz.date()),
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
                    const attendeeEventsForFallback = modifiedAllExternalEvents.filter((evt) => evt.userId === externalAttendee.userId);
                    const fallbackSlots = await generateTimeSlotsLiteForExternalAttendee(startDatesForEachDay[i], mainHostId, attendeeEventsForFallback, // Pass only this attendee's events
                    hostTimezone, externalAttendee.timezone, isFirstDayLoop);
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
        const filteredAllEvents = _.uniqBy(modifiedAllExternalEvents.filter((e) => validateEventDatesForExternalAttendee(e)), 'id');
        let eventParts = [];
        const eventPartMinisAccumulated = [];
        for (const event of filteredAllEvents) {
            const eventPartMinis = generateEventPartsLite(event, mainHostId);
            eventPartMinisAccumulated.push(...eventPartMinis);
        }
        const modifiedEventPartMinisPreBuffer = modifyEventPartsForMultiplePreBufferTime(eventPartMinisAccumulated);
        const modifiedEventPartMinisPreAndPostBuffer = modifyEventPartsForMultiplePostBufferTime(modifiedEventPartMinisPreBuffer);
        const formattedEventParts = modifiedEventPartMinisPreAndPostBuffer?.map((e) => formatEventTypeToPlannerEventForExternalAttendee(e, workTimes, filteredAllEvents, hostTimezone));
        if (formattedEventParts?.length > 0) {
            eventParts.push(...formattedEventParts);
        }
        if (eventParts.length > 0) {
            eventParts.forEach((e) => console.log(e, ' eventParts after formatting'));
            const newEventPartsWithPreferredTimeSet = eventParts.map((e) => setPreferredTimeForUnModifiableEvent(e, allExternalEvents.find((f) => f.id === e.eventId)?.timezone));
            newEventPartsWithPreferredTimeSet.forEach((e) => console.log(e, ' newEventPartsWithPreferredTimeSet'));
            const newEventParts = await tagEventsForDailyOrWeeklyTask(newEventPartsWithPreferredTimeSet);
            newEventParts.forEach((e) => console.log(e, ' newEventParts after tagEventsForDailyOrWeeklyTask'));
            const userList = [];
            for (const externalAttendee of externalAttendees) {
                const userPlannerRequestBody = generateUserPlannerRequestBodyForExternalAttendee(externalAttendee?.userId, workTimes, mainHostId);
                console.log(userPlannerRequestBody, ' userPlannerRequestBody');
                userList.push(userPlannerRequestBody);
            }
            const modifiedNewEventParts = newEventParts.map((eventPart) => {
                const oldEvent = filteredAllEvents.find((event) => event.id === eventPart.eventId);
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
    }
    catch (e) {
        console.log(e, ' unable to process events for optaplanner for external attendee');
    }
};
export const optaPlanWeekly = async (timeslots, userList, eventParts, singletonId, hostId, fileKey, delay, callBackUrl) => {
    try {
        const requestBody = {
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
    }
    catch (e) {
        console.log(e, ' optaPlanWeekly');
    }
};
export const updateFreemiumById = async (id, usage) => {
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
        console.log(response, response?.data?.update_Freemium_by_pk, ' response after updating update_Freemium_by_pk');
        return response?.data?.update_Freemium_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to update freemium');
    }
};
export const getFreemiumByUserId = async (userId) => {
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
        const res = await got
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
    }
    catch (e) {
        console.log(' unable to get freemium by user id');
    }
};
export const processEventsForOptaPlanner = async (mainHostId, internalAttendees, meetingEventPlus, newMeetingEventPlus, allEvents, windowStartDate, windowEndDate, hostTimezone, oldEvents, externalAttendees, meetingAssistEvents, newHostReminders, newHostBufferTimes, isReplan, eventBeingReplanned) => {
    try {
        let currentInternalAttendees = [...internalAttendees];
        let currentExternalAttendees = [...externalAttendees];
        console.log(windowStartDate, windowEndDate, ' windowStartDate, windowEndDate inside processEventsForOptaPlanner');
        if (isReplan && eventBeingReplanned) {
            console.log('Replanning event:', eventBeingReplanned.originalEventId, 'with constraints:', eventBeingReplanned.newConstraints);
            let processedOriginalAttendees = eventBeingReplanned.originalAttendees.map((a) => ({
                ...a,
                primaryEmail: a.emails?.find((e) => e.primary)?.value ||
                    a.emails?.[0]?.value ||
                    a.primaryEmail,
            }));
            // Handle removed attendees
            if (eventBeingReplanned.newConstraints.removedAttendeeEmailsOrIds?.length >
                0) {
                processedOriginalAttendees = processedOriginalAttendees.filter((att) => !eventBeingReplanned.newConstraints.removedAttendeeEmailsOrIds.includes(att.primaryEmail) &&
                    !eventBeingReplanned.newConstraints.removedAttendeeEmailsOrIds.includes(att.id) &&
                    !eventBeingReplanned.newConstraints.removedAttendeeEmailsOrIds.includes(att.userId));
            }
            // Handle added attendees
            if (eventBeingReplanned.newConstraints.addedAttendees?.length > 0) {
                for (const addedAtt of eventBeingReplanned.newConstraints
                    .addedAttendees) {
                    // Avoid adding duplicates if they somehow remained from original list
                    if (processedOriginalAttendees.some((oa) => oa.primaryEmail === addedAtt.email ||
                        (addedAtt.userId && oa.userId === addedAtt.userId))) {
                        continue;
                    }
                    // Fetch full attendee details if needed, or construct a partial MeetingAssistAttendeeType
                    // This example assumes we might need to fetch full details using getMeetingAssistAttendeeByEmailOrUserId (hypothetical function)
                    // For now, construct a partial object based on NewConstraints, assuming MA_Attendee ID is not known yet for new ones.
                    const newAttendeeObject = {
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
                        externalAttendee: addedAtt.externalAttendee !== undefined
                            ? addedAtt.externalAttendee
                            : !addedAtt.userId,
                        createdDate: dayjs().toISOString(),
                        updatedAt: dayjs().toISOString(),
                    };
                    processedOriginalAttendees.push(newAttendeeObject);
                }
            }
            // Separate into internal and external based on the final list
            currentInternalAttendees = processedOriginalAttendees.filter((a) => !a.externalAttendee);
            currentExternalAttendees = processedOriginalAttendees.filter((a) => a.externalAttendee);
        }
        const newInternalMeetingEventsPlus = newMeetingEventPlus
            ?.map((e) => {
            const foundIndex = currentExternalAttendees?.findIndex((a) => a?.userId === e?.userId);
            if (foundIndex > -1) {
                return null;
            }
            return e;
        })
            ?.filter((e) => e !== null);
        const newExternalMeetingEventsPlus = newMeetingEventPlus
            ?.map((e) => {
            const foundIndex = currentExternalAttendees?.findIndex((a) => a?.userId === e?.userId);
            if (foundIndex > -1) {
                return e;
            }
            return null;
        })
            ?.filter((e) => e !== null);
        const allHostEvents = allEvents.filter((e) => e.userId === mainHostId);
        const oldHostEvents = oldEvents.filter((e) => e?.userId === mainHostId);
        const hostIsInternalAttendee = currentInternalAttendees.some((ia) => ia?.userId === mainHostId);
        let returnValuesFromInternalAttendees = {};
        let returnValuesFromHost = {};
        console.log(hostIsInternalAttendee, ' hostIsInternalAttendee');
        if (hostIsInternalAttendee) {
            returnValuesFromInternalAttendees =
                await processEventsForOptaPlannerForInternalAttendees(mainHostId, allEvents, 
                // TODO: For replan, if eventBeingReplanned.newConstraints.newTimeWindowStartUTC is set, use it here for relevant attendees
                windowStartDate, windowEndDate, hostTimezone, currentInternalAttendees, // Use finalized list
                oldEvents, meetingEventPlus, newInternalMeetingEventsPlus, newHostBufferTimes, 
                // Pass isReplan and eventBeingReplanned for modifiable flag and duration logic
                isReplan, eventBeingReplanned);
        }
        else {
            // Assuming mainHost is always part of internalAttendees if they are internal.
            // If mainHost can be external or not in the list, this logic needs adjustment.
            returnValuesFromHost = await processEventsForOptaPlannerForMainHost(mainHostId, allHostEvents, 
            // TODO: For replan, if eventBeingReplanned.newConstraints.newTimeWindowStartUTC is set, use it here
            windowStartDate, windowEndDate, hostTimezone, oldHostEvents, newHostBufferTimes, 
            // Pass isReplan and eventBeingReplanned for modifiable flag and duration logic
            isReplan, eventBeingReplanned);
        }
        console.log(returnValuesFromInternalAttendees, ' returnValuesFromInternalAttendees');
        const externalMeetingEventPlus = meetingEventPlus
            .map((e) => {
            const foundIndex = currentExternalAttendees.findIndex((a) => a?.userId === e?.userId);
            if (foundIndex > -1) {
                return e;
            }
            return null;
        })
            ?.filter((e) => e !== null);
        const returnValuesFromExternalAttendees = currentExternalAttendees?.length > 0
            ? await processEventsForOptaPlannerForExternalAttendees(currentExternalAttendees?.map((a) => a.userId), mainHostId, meetingAssistEvents, 
            // TODO: For replan, if eventBeingReplanned.newConstraints.newTimeWindowStartUTC is set, use it here for relevant attendees
            windowStartDate, windowEndDate, hostTimezone, currentExternalAttendees, // Use finalized list
            externalMeetingEventPlus, newExternalMeetingEventsPlus, 
            // Pass meetingAssistId if available (e.g. from eventBeingReplanned or other context)
            // For now, assuming it might come from the event being replanned if it's a meeting assist event
            eventBeingReplanned?.originalEventId.includes('#')
                ? null
                : eventBeingReplanned?.originalEventId, // Simplistic check, might need better logic
            // Pass isReplan and eventBeingReplanned for modifiable flag and duration logic
            isReplan, eventBeingReplanned)
            : null;
        const eventParts = [];
        const allEventsForPlanner = [];
        const breaks = [];
        const oldEventsForPlanner = [];
        const oldAttendeeEvents = [];
        const unfilteredTimeslots = [];
        const unfilteredUserList = [];
        if (returnValuesFromHost
            ?.eventParts?.length > 0) {
            eventParts.push(...returnValuesFromHost
                ?.eventParts);
        }
        if (returnValuesFromHost
            ?.allEvents?.length > 0) {
            allEventsForPlanner.push(...returnValuesFromHost
                ?.allEvents);
        }
        if (returnValuesFromHost?.breaks
            ?.length > 0) {
            breaks.push(...returnValuesFromHost
                ?.breaks);
        }
        if (returnValuesFromHost
            ?.oldEvents?.length > 0) {
            oldEventsForPlanner.push(...returnValuesFromHost
                ?.oldEvents);
        }
        if (returnValuesFromHost
            ?.timeslots?.length > 0) {
            unfilteredTimeslots.push(...returnValuesFromHost
                ?.timeslots);
        }
        if (returnValuesFromHost
            ?.userPlannerRequestBody?.id) {
            unfilteredUserList.push(returnValuesFromHost
                ?.userPlannerRequestBody);
        }
        if (returnValuesFromInternalAttendees?.userList?.[0]?.id) {
            unfilteredUserList.push(...returnValuesFromInternalAttendees?.userList);
        }
        returnValuesFromInternalAttendees?.eventParts?.forEach((e) => console.log(e, ' (returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType)?.eventParts'));
        if (returnValuesFromInternalAttendees?.eventParts?.length > 0) {
            eventParts.push(...returnValuesFromInternalAttendees?.eventParts);
        }
        if (returnValuesFromInternalAttendees?.allEvents?.length > 0) {
            allEventsForPlanner.push(...returnValuesFromInternalAttendees?.allEvents);
        }
        returnValuesFromInternalAttendees?.breaks?.forEach((e) => console.log(e, ' (returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType)?.breaks'));
        if (returnValuesFromInternalAttendees?.breaks?.length > 0) {
            breaks.push(...returnValuesFromInternalAttendees?.breaks);
        }
        if (returnValuesFromInternalAttendees?.oldEvents?.length > 0) {
            oldEventsForPlanner.push(...returnValuesFromInternalAttendees?.oldEvents);
        }
        if (returnValuesFromInternalAttendees?.timeslots?.length > 0) {
            unfilteredTimeslots.push(...returnValuesFromInternalAttendees?.timeslots);
        }
        if (returnValuesFromExternalAttendees?.eventParts?.length > 0) {
            eventParts.push(...returnValuesFromExternalAttendees?.eventParts);
        }
        if (returnValuesFromExternalAttendees?.allEvents?.length > 0) {
            allEventsForPlanner.push(...returnValuesFromExternalAttendees?.allEvents);
        }
        if (returnValuesFromExternalAttendees?.oldAttendeeEvents?.length > 0) {
            oldAttendeeEvents.push(...returnValuesFromExternalAttendees?.oldAttendeeEvents);
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
        const duplicateFreeOldAttendeeEvents = _.uniqWith(oldAttendeeEvents, _.isEqual);
        const duplicateFreeTimeslots = _.uniqWith(unfilteredTimeslots, _.isEqual);
        const singletonId = uuid();
        console.log(eventParts, ' eventParts before validation');
        console.log(duplicateFreeEventParts, ' duplicateFreeEventParts before validation');
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
        duplicateFreeTimeslots?.forEach((d) => console.log(d, ' duplicateFreeTimeslots'));
        unfilteredUserList?.forEach((u) => console.log(u, ' unfilteredUserList'));
        newHostBufferTimes?.forEach((b) => console.log(b.beforeEvent, b.afterEvent, ' b.beforeEvent b.afterEvent '));
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
            Key: isReplan && eventBeingReplanned
                ? `${mainHostId}/${singletonId}_REPLAN_${eventBeingReplanned.googleEventId}.json`
                : `${mainHostId}/${singletonId}.json`,
            ContentType: 'application/json',
        };
        const s3Command = new PutObjectCommand(params);
        const s3Response = await s3Client.send(s3Command);
        console.log(s3Response, ' s3Response');
        await optaPlanWeekly(duplicateFreeTimeslots, unfilteredUserList, duplicateFreeEventParts, singletonId, mainHostId, isReplan && eventBeingReplanned
            ? `${mainHostId}/${singletonId}_REPLAN_${eventBeingReplanned.googleEventId}.json`
            : `${mainHostId}/${singletonId}.json`, optaplannerDuration, onOptaPlanCalendarAdminCallBackUrl);
        console.log('optaplanner request sent');
    }
    catch (e) {
        console.log(e, ' unable to process events for optaplanner');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUNMLFVBQVUsRUFDVixtQkFBbUIsRUFDbkIsb0JBQW9CLEVBQ3BCLGlCQUFpQixFQUNqQixjQUFjLEVBQ2Qsa0NBQWtDLEVBQ2xDLG1CQUFtQixFQUNuQixjQUFjLEVBQ2QsbUJBQW1CLEdBQ3BCLE1BQU0sa0NBQWtDLENBQUM7QUFvQzFDLE9BQU8sR0FBRyxNQUFNLEtBQUssQ0FBQztBQUN0QixPQUFPLEVBQUUsRUFBRSxJQUFJLElBQUksRUFBRSxNQUFNLE1BQU0sQ0FBQztBQUNsQyxPQUFPLEtBQUssTUFBTSxPQUFPLENBQUM7QUFFMUIsT0FBTyxRQUFRLE1BQU0sdUJBQXVCLENBQUM7QUFDN0MsT0FBTyxTQUFTLE1BQU0sd0JBQXdCLENBQUM7QUFDL0MsT0FBTyxRQUFRLE1BQU0sdUJBQXVCLENBQUM7QUFDN0MsT0FBTyxHQUFHLE1BQU0sa0JBQWtCLENBQUM7QUFDbkMsT0FBTyxDQUFDLE1BQU0sUUFBUSxDQUFDO0FBQ3ZCLE9BQU8sRUFBRSxnQkFBZ0IsRUFBRSxRQUFRLEVBQUUsTUFBTSxvQkFBb0IsQ0FBQztBQUNoRSxPQUFPLEVBQUUsU0FBUyxFQUFFLFNBQVMsRUFBRSxNQUFNLFVBQVUsQ0FBQztBQUVoRCxLQUFLLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxDQUFDO0FBQ3ZCLEtBQUssQ0FBQyxNQUFNLENBQUMsU0FBUyxDQUFDLENBQUM7QUFDeEIsS0FBSyxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsQ0FBQztBQUN2QixLQUFLLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDO0FBRWxCLE1BQU0sUUFBUSxHQUFHLElBQUksUUFBUSxDQUFDO0lBQzVCLFdBQVcsRUFBRTtRQUNYLFdBQVcsRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLGFBQWE7UUFDdEMsZUFBZSxFQUFFLE9B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QUFFLElBQUksQ0FBQztTQUNoRCxFQUFFLENBQUMsWUFBWSxDQUFDO1NBQ2hCLFNBQVMsQ0FDUixLQUFLLENBQUMsWUFBWSxDQUFDLFNBQVMsQ0FBQyxLQUFLLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1NBQ3ZDLEVBQUUsQ0FBQyxZQUFZLEVBQUUsUUFBUSxJQUFJLFlBQVksRUFBRSxJQUFJLENBQUM7U0FDaEQsRUFBRSxDQUFDLFlBQVksQ0FBQztTQUNoQixNQUFNLENBQUMsQ0FBQyxDQUFDLEVBQ1osS0FBSyxDQUFDLFlBQVksQ0FBQyxTQUFTLENBQUMsS0FBSyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQztTQUN2QyxFQUFFLENBQUMsWUFBWSxFQUFFLFFBQVEsSUFBSSxZQUFZLEVBQUUsSUFBSSxDQUFDO1NBQ2hELEVBQUUsQ0FBQyxZQUFZLENBQUM7U0FDaEIsTUFBTSxDQUFDLEVBQUUsQ0FBQyxFQUNiLFFBQVEsRUFDUixJQUFJLENBQ0w7UUFDRCxDQUFDLENBQUMsQ0FBQztRQUNILENBQUMsQ0FBQyxLQUFLLENBQUMsWUFBWSxDQUFDLFNBQVMsQ0FBQyxLQUFLLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO2FBQ3JDLEVBQUUsQ0FBQyxZQUFZLEVBQUUsUUFBUSxJQUFJLFlBQVksRUFBRSxJQUFJLENBQUM7YUFDaEQsRUFBRSxDQUFDLFlBQVksQ0FBQzthQUNoQixTQUFTLENBQ1IsS0FBSyxDQUFDLFlBQVksQ0FBQyxTQUFTLENBQUMsS0FBSyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQzthQUN2QyxFQUFFLENBQUMsWUFBWSxFQUFFLFFBQVEsSUFBSSxZQUFZLEVBQUUsSUFBSSxDQUFDO2FBQ2hELEVBQUUsQ0FBQyxZQUFZLENBQUM7YUFDaEIsTUFBTSxDQUFDLEVBQUUsQ0FBQyxFQUNiLEtBQUssQ0FBQyxZQUFZLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7YUFDdkMsRUFBRSxDQUFDLFlBQVksRUFBRSxR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T0FBTyxHQUFHLEtBQUssQ0FBQyxLQUFLLENBQUMsT0FBTyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7U0FDOUMsRUFBRSxDQUFDLEtBQUssQ0FBQyxRQUFRLEVBQUUsSUFBSSxDQUFDO1NBQ3hCLElBQUksQ0FBQyxLQUFLLENBQUMsS0FBSyxDQUFDLFNBQVMsQ0FBQyxLQUFLLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsRUFBRSxDQUFDLEtBQUssQ0FBQyxRQUFRLEVBQUUsSUFBSSxDQUFDLEVBQUUsR0FBRyxDQUFDLENBQUM7SUFDM0UsTUFBTSxTQUFTLEdBQUcsS0FBSyxDQUFDLEtBQUssQ0FBQyxPQUFPLENBQUMsS0FBSyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQztTQUNoRCxFQUFFLENBQUMsS0FBSyxDQUFDLFFBQVEsRUFBRSxJQUFJLENBQUM7U0FDeEIsSUFBSSxDQUFDLEtBQUssQ0FBQyxLQUFLLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLENBQUMsS0FBSyxDQUFDLFFBQVEsRUFBRSxJQUFJLENBQUMsRUFBRSxHQUFHLENBQUMsQ0FBQztJQUUzRSxNQUFNLFVBQVUsR0FBRyxTQUFTLENBQzFCLEtBQUssQ0FBQyxLQUFLLEVBQUUsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLENBQUMsS0FBSyxFQUFFLFFBQVEsRUFBRSxJQUFJLENBQUMsQ0FBQyxNQUFNLEVBQUUsQ0FDeEUsQ0FBQztJQUNGLE1BQU0sT0FBTyxHQUFHLGVBQWUsQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUMzQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLEdBQUcsS0FBSyxVQUFVLENBQzdCLEVBQUUsSUFBSSxDQUFDO0lBQ1IsTUFBTSxVQUFVLEdBQUcsZUFBZSxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQzlDLENBQUMsQ0FBQyxFQUFF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QUFDO1FBQ1YsTUFBTSxxQkFBcUIsR0FBRyxLQUFLLENBQUMsWUFBWSxDQUFDLFNBQVMsQ0FBQyxLQUFLLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO2FBQ3JFLEVBQUUsQ0FBQyxZQUFZLEVBQUUsUUFBUSxJQUFJLFlBQVksRUFBRSxJQUFJLENBQUM7YUFDaEQsRUFBRSxDQUFDLFlBQVksQ0FBQzthQUNoQixTQUFTLENBQ1IsS0FBSyxDQUFDLFlBQVksQ0FBQyxTQUFTLENBQUMsS0FBSyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQzthQUN2QyxFQUFFLENBQUMsWUFBWSxFQUFFLFFBQVEsSUFBSSxZQUFZLEVBQUUsSUFBSSxDQUFDO2FBQ2hELEVBQUUsQ0FBQyxZQUFZLENBQUM7YUFDaEIsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUNaLEtBQUssQ0FBQyxZQUFZLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7YUFDdkMsRUFBRSxDQUFDLFlBQVksRUFBRSxRQUFRLElBQUksWUFBWSxFQUFFLElBQUksQ0FBQzthQUNoRCxFQUFFLENBQUMsWUFBWSxDQUFDO2FBQ2hCLE1BQU0sQ0FBQyxFQUFFLENBQUMsRUFDYixRQUFRLEVBQ1IsSUFBSSxDQUNMO1lBQ0QsQ0FBQyxDQUFDLENBQUM7WUFDSCxDQUFDLENBQUMsS0FBSyxDQUFDLFlBQVksQ0FBQyxTQUFTLENBQUMsS0FBSyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQztpQkFDckMsRUFBRSxDQUFDLFlBQVksRUFBRSxRQUFRLElBQUksWUFBWSxFQUFFLElBQUksQ0FBQztpQkFDaEQsRUFBRSxDQUFDLFlBQVksQ0FBQztpQkFDaEIsU0FBUyxDQUNSLEtBQUssQ0FBQyxZQUFZLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7aUJBQ3ZDLEVBQUUsQ0FBQyxZQUFZLEVBQUUsUUFBUSxJQUFJLFlBQVksRUFBRSxJQUFJLENBQUM7aUJBQ2hELEVBQUUs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Q0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1NBQ3JFLEVBQUUsQ0FBQyxZQUFZLEVBQUUsUUFBUSxJQUFJLFlBQVksRUFBRSxJQUFJLENBQUM7U0FDaEQsRUFBRSxDQUFDLFlBQVksQ0FBQztTQUNoQixTQUFTLENBQ1IsS0FBSyxDQUFDLFlBQVksQ0FBQyxTQUFTLENBQUMsS0FBSyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQztTQUN2QyxFQUFFLENBQUMsWUFBWSxFQUFFLFFBQVEsSUFBSSxZQUFZLEVBQUUsSUFBSSxDQUFDO1NBQ2hELEVBQUUsQ0FBQyxZQUFZLENBQUM7U0FDaEIsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUNaLEtBQUssQ0FBQyxZQUFZLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7U0FDdkMsRUFBRSxDQUFDLFlBQVksRUFBRSxRQUFRLElBQUksWUFBWSxFQUFFLElBQUksQ0FBQztTQUNoRCxFQUFFLENBQUMsWUFBWSxDQUFDO1NBQ2hCLE1BQU0sQ0FBQyxFQUFFLENBQUMsRUFDYixRQUFRLEVBQ1IsSUFBSSxDQUNMO1FBQ0QsQ0FBQyxDQUFDLENBQUM7UUFDSCxDQUFDLENBQUMsS0FBSyxDQUFDLFlBQVksQ0FBQyxTQUFTLENBQUMsS0FBSyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQzthQUNyQyxFQUFFLENBQUMsWUFBWSxFQUFFLFFBQVEsSUFBSSxZQUFZLEVBQUUsSUFBSSxDQUFDO2FBQ2hELEVBQUUsQ0FBQyxZQUFZLENBQUM7YUFDaEIsU0FBUyxDQUNSLEtBQUssQ0FBQyxZQUFZLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7YUFDdkMsRUFBRSxDQUFDLFlBQVksRUFBRSxRQUFRLElBQUksWUFBWSxFQUFFLElBQUksQ0FBQzthQUNoRCxFQUFFLENBQUMsWUFBWSxDQUFDO2FBQ2hCLE1BQU0sQ0FBQyxFQUFFLENBQUMsRUFDYixLQUFLLENBQUMsWUFBWSxDQUFDLFNBQVMs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LEVBQUUsa0JBQWtCO1NBQ2hDLENBQUM7UUFFRixNQUFNLFNBQVMsR0FBRyxJQUFJLGdCQUFnQixDQUFDLE1BQU0sQ0FBQyxDQUFDO1FBRS9DLE1BQU0sVUFBVSxHQUFHLE1BQU0sUUFBUSxDQUFDLElBQUksQ0FBQyxTQUFTLENBQUMsQ0FBQztRQUVsRCxPQUFPLENBQUMsR0FBRyxDQUFDLFVBQVUsRUFBRSxhQUFhLENBQUMsQ0FBQztRQUV2QyxNQUFNLGNBQWMsQ0FDbEIsc0JBQXNCLEVBQ3RCLGtCQUFrQixFQUNsQix1QkFBdUIsRUFDdkIsV0FBVyxFQUNYLFVBQVUsRUFDVixRQUFRLElBQUksbUJBQW1CO1lBQzdCLENBQUMsQ0FBQyxHQUFHLFVBQVUsSUFBSSxXQUFXLFdBQVcsbUJBQW1CLENBQUMsYUFBYSxPQUFPO1lBQ2pGLENBQUMsQ0FBQyxHQUFHLFVBQVUsSUFBSSxXQUFXLE9BQU8sRUFDdkMsbUJBQW1CLEVBQ25CLGtDQUFrQyxDQUNuQyxDQUFDO1FBRUYsT0FBTyxDQUFDLEdBQUcsQ0FBQywwQkFBMEIsQ0FBQyxDQUFDO0lBQzFDLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsMkNBQTJDLENBQUMsQ0FBQztJQUM5RCxDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgYnVja2V0TmFtZSxcbiAgb3B0YXBsYW5uZXJEdXJhdGlvbixcbiAgZGF5T2ZXZWVrSW50VG9TdHJpbmcsXG4gIGhhc3VyYUFkbWluU2VjcmV0LFxuICBoYXN1cmFHcmFwaFVybCxcbiAgb25PcHRhUGxhbkNhbGVuZGFyQWRtaW5DYWxsQmFja1VybCxcbiAgb3B0YVBsYW5uZXJQYXNzd29yZCxcbiAgb3B0YVBsYW5uZXJVcmwsXG4gIG9wdGFQbGFubmVyVXNlcm5hbWUsXG59IGZyb20gJ0BzY2hlZHVsZV9hc3Npc3QvX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7XG4gIEJ1ZmZlclRpbWVOdW1iZXJUeXBlLFxuICBFdmVudFBsdXNUeXBlLFxuICBFdmVudFR5cGUsXG4gIE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGUsXG4gIE1lZXRpbmdBc3Npc3RFdmVudFR5cGUsXG4gIE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlLFxuICBNZWV0aW5nQXNzaXN0VHlwZSxcbiAgRXZlbnRNZWV0aW5nUGx1c1R5cGUsXG4gIFByZWZlcnJlZFRpbWVSYW5nZVR5cGUsXG4gIFJlbWluZGVyc0ZvckV2ZW50VHlwZSxcbiAgVmFsdWVzVG9SZXR1cm5Gb3JCdWZmZXJFdmVudHNUeXBlLFxuICBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIENhbGVuZGFyVHlwZSxcbiAgV29ya1RpbWVUeXBlLFxuICBUaW1lU2xvdFR5cGUsXG4gIE1vbnRoVHlwZSxcbiAgRGF5VHlwZSxcbiAgTU0sXG4gIERELFxuICBNb250aERheVR5cGUsXG4gIFRpbWUsXG4gIEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGUsXG4gIEluaXRpYWxFdmVudFBhcnRUeXBlLFxuICBJbml0aWFsRXZlbnRQYXJ0VHlwZVBsdXMsXG4gIFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlLFxuICBSZXR1cm5Cb2R5Rm9ySG9zdEZvck9wdGFwbGFubmVyUHJlcFR5cGUsXG4gIFJldHVybkJvZHlGb3JBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGUsXG4gIFJldHVybkJvZHlGb3JFeHRlcm5hbEF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZSxcbiAgUGxhbm5lclJlcXVlc3RCb2R5VHlwZSxcbiAgRnJlZW1pdW1UeXBlLFxuICBCdWZmZXJUaW1lT2JqZWN0VHlwZSxcbiAgRmV0Y2hlZEV4dGVybmFsUHJlZmVyZW5jZSxcbiAgTmV3Q29uc3RyYWludHMsXG59IGZyb20gJ0BzY2hlZHVsZV9hc3Npc3QvX2xpYnMvdHlwZXMnOyAvLyBBZGRlZCBGZXRjaGVkRXh0ZXJuYWxQcmVmZXJlbmNlIGFuZCBOZXdDb25zdHJhaW50c1xuaW1wb3J0IGdvdCBmcm9tICdnb3QnO1xuaW1wb3J0IHsgdjQgYXMgdXVpZCB9IGZyb20gJ3V1aWQnO1xuaW1wb3J0IGRheWpzIGZyb20gJ2RheWpzJztcblxuaW1wb3J0IGR1cmF0aW9uIGZyb20gJ2RheWpzL3BsdWdpbi9kdXJhdGlvbic7XG5pbXBvcnQgaXNCZXR3ZWVuIGZyb20gJ2RheWpzL3BsdWdpbi9pc0JldHdlZW4nO1xuaW1wb3J0IHRpbWV6b25lIGZyb20gJ2RheWpzL3BsdWdpbi90aW1lem9uZSc7XG5pbXBvcnQgdXRjIGZyb20gJ2RheWpzL3BsdWdpbi91dGMnO1xuaW1wb3J0IF8gZnJvbSAnbG9kYXNoJztcbmltcG9ydCB7IFB1dE9iamVjdENvbW1hbmQsIFMzQ2xpZW50IH0gZnJvbSAnQGF3cy1zZGsvY2xpZW50LXMzJztcbmltcG9ydCB7IGdldElTT0RheSwgc2V0SVNPRGF5IH0gZnJvbSAnZGF0ZS1mbnMnO1xuXG5kYXlqcy5leHRlbmQoZHVyYXRpb24pO1xuZGF5anMuZXh0ZW5kKGlzQmV0d2Vlbik7XG5kYXlqcy5leHRlbmQodGltZXpvbmUpO1xuZGF5anMuZXh0ZW5kKHV0Yyk7XG5cbmNvbnN0IHMzQ2xpZW50ID0gbmV3IFMzQ2xpZW50KHtcbiAgY3JlZGVudGlhbHM6IHtcbiAgICBhY2Nlc3NLZXlJZDogcHJvY2Vzcy5lbnYuUzNfQUNDRVNTX0tFWSxcbiAgICBzZWNyZXRBY2Nlc3NLZXk6IHByb2Nlc3MuZW52LlMzX1NFQ1JFVF9LRVksXG4gIH0sXG4gIGVuZHBvaW50OiBwcm9jZXNzLmVudi5TM19FTkRQT0lOVCxcbiAgZm9yY2VQYXRoU3R5bGU6IHRydWUsXG59KTtcblxuZXhwb3J0IGNvbnN0IGxpc3RGdXR1cmVNZWV0aW5nQXNzaXN0cyA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nLFxuICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gIGlkcz86IHN0cmluZ1tdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIHVzZXJJZCxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICBpZHMsXG4gICAgICAnIHVzZXJJZCwgd2luZG93U3RhcnREYXRlLCB3aW5kb3dFbmREYXRlLCBpZHMnXG4gICAgKTtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0xpc3RNZWV0aW5nQXNzaXN0JztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IExpc3RNZWV0aW5nQXNzaXN0KCR1c2VySWQ6IHV1aWQhLCAkd2luZG93U3RhcnREYXRlOiB0aW1lc3RhbXAhLCAkd2luZG93RW5kRGF0ZTogdGltZXN0YW1wISwgJHtpZHM/Lmxlbmd0aCA+IDAgPyAnJGlkczogW3V1aWQhXSEnIDogJyd9KSB7XG4gICAgICAgICAgICAgICAgTWVldGluZ19Bc3Npc3Qod2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9LCB3aW5kb3dFbmREYXRlOiB7X2x0ZTogJHdpbmRvd0VuZERhdGV9LCB3aW5kb3dTdGFydERhdGU6IHtfZ3RlOiAkd2luZG93U3RhcnREYXRlfSwgY2FuY2VsbGVkOiB7X2VxOiBmYWxzZX0ke2lkcz8ubGVuZ3RoID4gMCA/ICcsIGlkOiB7X25pbjogJGlkc30nIDogJyd9LCBldmVudElkOiB7X2lzX251bGw6IHRydWV9fSkge1xuICAgICAgICAgICAgICAgICAgICBhbGxvd0F0dGVuZGVlVXBkYXRlUHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUNhbk1vZGlmeVxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUNvdW50XG4gICAgICAgICAgICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZVJlc3BvbmRlZENvdW50XG4gICAgICAgICAgICAgICAgICAgIGJ1ZmZlclRpbWVcbiAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgICAgICAgICBjYW5jZWxJZkFueVJlZnVzZVxuICAgICAgICAgICAgICAgICAgICBjYW5jZWxsZWRcbiAgICAgICAgICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgICAgICAgICBjb25mZXJlbmNlQXBwXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgIGVuYWJsZUF0dGVuZGVlUHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgZW5hYmxlQ29uZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgICBlbmFibGVIb3N0UHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgZW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgIGV4cGlyZURhdGVcbiAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGd1YXJhbnRlZUF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgbG9jYXRpb25cbiAgICAgICAgICAgICAgICAgICAgbWluVGhyZXNob2xkQ291bnRcbiAgICAgICAgICAgICAgICAgICAgbm90ZXNcbiAgICAgICAgICAgICAgICAgICAgcHJpb3JpdHlcbiAgICAgICAgICAgICAgICAgICAgcmVtaW5kZXJzXG4gICAgICAgICAgICAgICAgICAgIHNlbmRVcGRhdGVzXG4gICAgICAgICAgICAgICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBzdW1tYXJ5XG4gICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHRyYW5zcGFyZW5jeVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlRGVmYXVsdEFsYXJtc1xuICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICAgICAgdmlzaWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICB3aW5kb3dFbmREYXRlXG4gICAgICAgICAgICAgICAgICAgIHdpbmRvd1N0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBpbnRlcnZhbFxuICAgICAgICAgICAgICAgICAgICBsb2NrQWZ0ZXJcbiAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxNZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgdW50aWxcbiAgICAgICAgICAgICAgICAgICAgZnJlcXVlbmN5XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgbGV0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICB9O1xuXG4gICAgaWYgKGlkcz8ubGVuZ3RoID4gMCkge1xuICAgICAgdmFyaWFibGVzLmlkcyA9IGlkcztcbiAgICB9XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBNZWV0aW5nX0Fzc2lzdDogTWVldGluZ0Fzc2lzdFR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBpbnNpZGUgbGlzdCBmdXR1cmUgbWVldGluZyBhc3Npc3QnKTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIHJlcz8uZGF0YT8uTWVldGluZ19Bc3Npc3QsXG4gICAgICAnIHN1Y2Nlc3NmdWxseSBnb3QgbWVldGluZyBhc3NzaXN0cydcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uTWVldGluZ19Bc3Npc3Q7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBsaXN0IG1lZXRpbmcgYXNzaXN0cycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VzR2l2ZW5NZWV0aW5nSWQgPSBhc3luYyAoXG4gIG1lZXRpbmdJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0xpc3RNZWV0aW5nQXNzaXN0UHJlZmVyZXJlZFRpbWVSYW5nZXNCeU1lZXRpbmdJZCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBxdWVyeSBMaXN0TWVldGluZ0Fzc2lzdFByZWZlcmVyZWRUaW1lUmFuZ2VzQnlNZWV0aW5nSWQoJG1lZXRpbmdJZDogdXVpZCEpIHtcbiAgICAgICAgICAgICAgICBNZWV0aW5nX0Fzc2lzdF9QcmVmZXJyZWRfVGltZV9SYW5nZSh3aGVyZToge21lZXRpbmdJZDoge19lcTogJG1lZXRpbmdJZH19KSB7XG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlSWRcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgIGVuZFRpbWVcbiAgICAgICAgICAgICAgICAgICAgaG9zdElkXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgICAgICAgICAgICBzdGFydFRpbWVcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgIH1cblxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgbWVldGluZ0lkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgTWVldGluZ19Bc3Npc3RfUHJlZmVycmVkX1RpbWVfUmFuZ2U6IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW107XG4gICAgICB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGxpc3RNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzICcpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uTWVldGluZ19Bc3Npc3RfUHJlZmVycmVkX1RpbWVfUmFuZ2U7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVhbmJsZSB0byBsaXN0IG1lZXRpbmcgYXNzaXN0IHByZWZlcnJlZCB0aW1lIHJhbmdlcycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbWVldGluZ0F0dGVuZGVlQ291bnRHaXZlbk1lZXRpbmdJZCA9IGFzeW5jIChtZWV0aW5nSWQ6IHN0cmluZykgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnQXR0ZW5kZWVDb3VudEdpdmVNZWV0aW5nSWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgQXR0ZW5kZWVDb3VudEdpdmVNZWV0aW5nSWQoJG1lZXRpbmdJZDogdXVpZCEpIHtcbiAgICAgICAgICAgICAgICBNZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZV9hZ2dyZWdhdGUod2hlcmU6IHttZWV0aW5nSWQ6IHtfZXE6ICRtZWV0aW5nSWR9fSkge1xuICAgICAgICAgICAgICAgICAgICBhZ2dyZWdhdGUge1xuICAgICAgICAgICAgICAgICAgICAgICAgY291bnRcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIG1lZXRpbmdJZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7XG4gICAgICBkYXRhOiB7XG4gICAgICAgIE1lZXRpbmdfQXNzaXN0X0F0dGVuZGVlX2FnZ3JlZ2F0ZTogeyBhZ2dyZWdhdGU6IHsgY291bnQ6IG51bWJlciB9IH07XG4gICAgICB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICByZXM/LmRhdGE/Lk1lZXRpbmdfQXNzaXN0X0F0dGVuZGVlX2FnZ3JlZ2F0ZT8uYWdncmVnYXRlPy5jb3VudCxcbiAgICAgICcgcmVjZWl2ZWQgYXR0ZW5kZWUgY291bnQnXG4gICAgKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/Lk1lZXRpbmdfQXNzaXN0X0F0dGVuZGVlX2FnZ3JlZ2F0ZT8uYWdncmVnYXRlPy5jb3VudDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBtZWV0aW5nIGF0dGVuZGVlIGNvdW50Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBsaXN0TWVldGluZ0Fzc2lzdEF0dGVuZGVlc0dpdmVuTWVldGluZ0lkID0gYXN5bmMgKFxuICBtZWV0aW5nSWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdMaXN0TWVldGluZ0Fzc2lzdEF0dGVuZGVlc0J5TWVldGluZ0lkJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IExpc3RNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzQnlNZWV0aW5nSWQoJG1lZXRpbmdJZDogdXVpZCEpIHtcbiAgICAgICAgICAgICAgICBNZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZSh3aGVyZToge21lZXRpbmdJZDoge19lcTogJG1lZXRpbmdJZH19KSB7XG4gICAgICAgICAgICAgICAgICAgIGNvbnRhY3RJZFxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBlbWFpbHNcbiAgICAgICAgICAgICAgICAgICAgZXh0ZXJuYWxBdHRlbmRlZVxuICAgICAgICAgICAgICAgICAgICBob3N0SWRcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgaW1BZGRyZXNzZXNcbiAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgICAgICAgICAgcGhvbmVOdW1iZXJzXG4gICAgICAgICAgICAgICAgICAgIHByaW1hcnlFbWFpbFxuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgbWVldGluZ0lkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHsgTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWU6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXSB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGxpc3RNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzICcpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWU7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBsaXN0IG1lZXRpbmcgYXNzaXN0IGF0dGVuZGVlcycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0TWVldGluZ0Fzc2lzdEF0dGVuZGVlID0gYXN5bmMgKGlkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0dldE1lZXRpbmdBc3Npc3RBdHRlbmRlZUJ5SWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgR2V0TWVldGluZ0Fzc2lzdEF0dGVuZGVlQnlJZCgkaWQ6IFN0cmluZyEpIHtcbiAgICAgICAgICAgICAgICBNZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZV9ieV9wayhpZDogJGlkKSB7XG4gICAgICAgICAgICAgICAgICAgIGNvbnRhY3RJZFxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBlbWFpbHNcbiAgICAgICAgICAgICAgICAgICAgaG9zdElkXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGltQWRkcmVzc2VzXG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICAgICAgICAgIHBob25lTnVtYmVyc1xuICAgICAgICAgICAgICAgICAgICBwcmltYXJ5RW1haWxcbiAgICAgICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgICAgICBleHRlcm5hbEF0dGVuZGVlXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgaWQsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczoge1xuICAgICAgZGF0YTogeyBNZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZV9ieV9wazogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGdldE1lZXRpbmdBc3Npc3RBdHRlbmRlZScpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWVfYnlfcGs7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgbWVldGluZyBhc3Npc3QgYXR0ZW5kZWUnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldE1lZXRpbmdBc3Npc3QgPSBhc3luYyAoaWQ6IHN0cmluZykgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnR2V0TWVldGluZ0Fzc2lzdEJ5SWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgR2V0TWVldGluZ0Fzc2lzdEJ5SWQoJGlkOiB1dWlkISkge1xuICAgICAgICAgICAgICAgIE1lZXRpbmdfQXNzaXN0X2J5X3BrKGlkOiAkaWQpIHtcbiAgICAgICAgICAgICAgICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUNhbk1vZGlmeVxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUNvdW50XG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlUmVzcG9uZGVkQ291bnRcbiAgICAgICAgICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGJ1ZmZlclRpbWVcbiAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgICAgICAgICBjYW5jZWxJZkFueVJlZnVzZVxuICAgICAgICAgICAgICAgICAgICBjYW5jZWxsZWRcbiAgICAgICAgICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgICAgICAgICBjb25mZXJlbmNlQXBwXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgIGVuYWJsZUF0dGVuZGVlUHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgZW5hYmxlQ29uZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgICBlbmFibGVIb3N0UHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgZW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgIGV4cGlyZURhdGVcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICAgICAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBsb2NhdGlvblxuICAgICAgICAgICAgICAgICAgICBtaW5UaHJlc2hvbGRDb3VudFxuICAgICAgICAgICAgICAgICAgICBub3Rlc1xuICAgICAgICAgICAgICAgICAgICBwcmlvcml0eVxuICAgICAgICAgICAgICAgICAgICByZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgc2VuZFVwZGF0ZXNcbiAgICAgICAgICAgICAgICAgICAgc3RhcnREYXRlXG4gICAgICAgICAgICAgICAgICAgIHN1bW1hcnlcbiAgICAgICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgdHJhbnNwYXJlbmN5XG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgICAgICB2aXNpYmlsaXR5XG4gICAgICAgICAgICAgICAgICAgIHdpbmRvd0VuZERhdGVcbiAgICAgICAgICAgICAgICAgICAgd2luZG93U3RhcnREYXRlXG4gICAgICAgICAgICAgICAgICAgIGFsbG93QXR0ZW5kZWVVcGRhdGVQcmVmZXJlbmNlc1xuICAgICAgICAgICAgICAgICAgICBndWFyYW50ZWVBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG5cbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBpZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgTWVldGluZ19Bc3Npc3RfYnlfcGs6IE1lZXRpbmdBc3Npc3RUeXBlIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gZ2V0TWVldGluZ0Fzc2lzdCcpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uTWVldGluZ19Bc3Npc3RfYnlfcGs7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgbWVldGluZyBhc3Npc3QgZnJvbSBpZCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdE1lZXRpbmdBc3Npc3RFdmVudHNGb3JBdHRlbmRlZUdpdmVuRGF0ZXMgPSBhc3luYyAoXG4gIGF0dGVuZGVlSWQ6IHN0cmluZyxcbiAgaG9zdFN0YXJ0RGF0ZTogc3RyaW5nLFxuICBob3N0RW5kRGF0ZTogc3RyaW5nLFxuICB1c2VyVGltZXpvbmU6IHN0cmluZyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnTGlzdE1lZXRpbmdBc3Npc3RFdmVudHNGb3JBdHRlbmRlZUdpdmVuRGF0ZXMnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgTGlzdE1lZXRpbmdBc3Npc3RFdmVudHNGb3JBdHRlbmRlZUdpdmVuRGF0ZXMoJGF0dGVuZGVlSWQ6IFN0cmluZyEsICRzdGFydERhdGU6IHRpbWVzdGFtcCEsICRlbmREYXRlOiB0aW1lc3RhbXAhKSB7XG4gICAgICAgICAgICAgICAgTWVldGluZ19Bc3Npc3RfRXZlbnQod2hlcmU6IHthdHRlbmRlZUlkOiB7X2VxOiAkYXR0ZW5kZWVJZH0sIGVuZERhdGU6IHtfZ3RlOiAkc3RhcnREYXRlfSwgc3RhcnREYXRlOiB7X2x0ZTogJGVuZERhdGV9fSkge1xuICAgICAgICAgICAgICAgICAgICBhbGxEYXlcbiAgICAgICAgICAgICAgICAgICAgYXR0YWNobWVudHNcbiAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVJZFxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZXNPbWl0dGVkXG4gICAgICAgICAgICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICBjYWxlbmRhcklkXG4gICAgICAgICAgICAgICAgICAgIGNvbG9ySWRcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRvclxuICAgICAgICAgICAgICAgICAgICBlbmREYXRlXG4gICAgICAgICAgICAgICAgICAgIGVuZFRpbWVVbnNwZWNpZmllZFxuICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgIGV2ZW50VHlwZVxuICAgICAgICAgICAgICAgICAgICBleHRlbmRlZFByb3BlcnRpZXNcbiAgICAgICAgICAgICAgICAgICAgZXh0ZXJuYWxVc2VyXG4gICAgICAgICAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5Nb2RpZnlcbiAgICAgICAgICAgICAgICAgICAgaGFuZ291dExpbmtcbiAgICAgICAgICAgICAgICAgICAgaHRtbExpbmtcbiAgICAgICAgICAgICAgICAgICAgaUNhbFVJRFxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBsaW5rc1xuICAgICAgICAgICAgICAgICAgICBsb2NhdGlvblxuICAgICAgICAgICAgICAgICAgICBsb2NrZWRcbiAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICAgICAgICAgIG9yZ2FuaXplclxuICAgICAgICAgICAgICAgICAgICBwcml2YXRlQ29weVxuICAgICAgICAgICAgICAgICAgICByZWN1cnJlbmNlXG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VSdWxlXG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmluZ0V2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgc291cmNlXG4gICAgICAgICAgICAgICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBzdW1tYXJ5XG4gICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHRyYW5zcGFyZW5jeVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlRGVmYXVsdEFsYXJtc1xuICAgICAgICAgICAgICAgICAgICB2aXNpYmlsaXR5XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3Qgc3RhcnREYXRlSW5Ib3N0VGltZXpvbmUgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooXG4gICAgICBob3N0VGltZXpvbmUsXG4gICAgICB0cnVlXG4gICAgKTtcbiAgICBjb25zdCBlbmREYXRlSW5Ib3N0VGltZXpvbmUgPSBkYXlqcyhob3N0RW5kRGF0ZS5zbGljZSgwLCAxOSkpLnR6KFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgdHJ1ZVxuICAgICk7XG4gICAgY29uc3Qgc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUgPSBkYXlqcyhzdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuZm9ybWF0KClcbiAgICAgIC5zbGljZSgwLCAxOSk7XG4gICAgY29uc3QgZW5kRGF0ZUluVXNlclRpbWV6b25lID0gZGF5anMoZW5kRGF0ZUluSG9zdFRpbWV6b25lKVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC5mb3JtYXQoKVxuICAgICAgLnNsaWNlKDAsIDE5KTtcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IE1lZXRpbmdfQXNzaXN0X0V2ZW50OiBNZWV0aW5nQXNzaXN0RXZlbnRUeXBlW10gfSB9ID1cbiAgICAgIGF3YWl0IGdvdFxuICAgICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBqc29uOiB7XG4gICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgcXVlcnksXG4gICAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgICAgYXR0ZW5kZWVJZCxcbiAgICAgICAgICAgICAgc3RhcnREYXRlOiBzdGFydERhdGVJblVzZXJUaW1lem9uZSxcbiAgICAgICAgICAgICAgZW5kRGF0ZTogZW5kRGF0ZUluVXNlclRpbWV6b25lLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9LFxuICAgICAgICB9KVxuICAgICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGxpc3RNZWV0aW5nQXNzaXN0RXZlbnRzRm9yQXR0ZW5kZWVHaXZlbkRhdGVzJyk7XG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uTWVldGluZ19Bc3Npc3RfRXZlbnQ7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUsXG4gICAgICAnIHVuYWJsZSB0byBsaXN0IG1lZXRpbmcgYXNzaXN0IGV2ZW50cyBmb3IgYXR0ZW5kZWUgZ2l2ZW4gZGF0ZXMnXG4gICAgKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RFdmVudHNGb3JEYXRlID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgc3RhcnREYXRlOiBzdHJpbmcsXG4gIGVuZERhdGU6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdsaXN0RXZlbnRzRm9yRGF0ZSc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgIHF1ZXJ5IGxpc3RFdmVudHNGb3JEYXRlKCR1c2VySWQ6IHV1aWQhLCAkc3RhcnREYXRlOiB0aW1lc3RhbXAhLCAkZW5kRGF0ZTogdGltZXN0YW1wISkge1xuICAgICAgICAgIEV2ZW50KHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgZW5kRGF0ZToge19ndGU6ICRzdGFydERhdGV9LCBzdGFydERhdGU6IHtfbHRlOiAkZW5kRGF0ZX0sIGRlbGV0ZWQ6IHtfZXE6IGZhbHNlfX0pIHtcbiAgICAgICAgICAgIGFsbERheVxuICAgICAgICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgICAgICAgYXR0YWNobWVudHNcbiAgICAgICAgICAgIGF0dGVuZGVlc09taXR0ZWRcbiAgICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgY29uZmVyZW5jZUlkXG4gICAgICAgICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICAgICAgICBjb3B5Q2F0ZWdvcmllc1xuICAgICAgICAgICAgY29weUR1cmF0aW9uXG4gICAgICAgICAgICBjb3B5SXNCcmVha1xuICAgICAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICAgICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgICAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGNyZWF0b3JcbiAgICAgICAgICAgIGRhaWx5VGFza0xpc3RcbiAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICBlbmREYXRlXG4gICAgICAgICAgICBlbmRUaW1lVW5zcGVjaWZpZWRcbiAgICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICAgIGV2ZW50VHlwZVxuICAgICAgICAgICAgZXh0ZW5kZWRQcm9wZXJ0aWVzXG4gICAgICAgICAgICBmb2xsb3dVcEV2ZW50SWRcbiAgICAgICAgICAgIGZvckV2ZW50SWRcbiAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzXG4gICAgICAgICAgICBndWVzdHNDYW5Nb2RpZnlcbiAgICAgICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICAgICAgICBoYW5nb3V0TGlua1xuICAgICAgICAgICAgaGFyZERlYWRsaW5lXG4gICAgICAgICAgICBodG1sTGlua1xuICAgICAgICAgICAgaUNhbFVJRFxuICAgICAgICAgICAgaWRcbiAgICAgICAgICAgIGlzQnJlYWtcbiAgICAgICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgIGlzRm9sbG93VXBcbiAgICAgICAgICAgIGlzTWVldGluZ1xuICAgICAgICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgaXNQb3N0RXZlbnRcbiAgICAgICAgICAgIGlzUHJlRXZlbnRcbiAgICAgICAgICAgIGxpbmtzXG4gICAgICAgICAgICBsb2NhdGlvblxuICAgICAgICAgICAgbG9ja2VkXG4gICAgICAgICAgICBtYXhBdHRlbmRlZXNcbiAgICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgICAgbWV0aG9kXG4gICAgICAgICAgICBtb2RpZmlhYmxlXG4gICAgICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3RTY29yZVxuICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3RUaW1lXG4gICAgICAgICAgICBub3Rlc1xuICAgICAgICAgICAgb3JnYW5pemVyXG4gICAgICAgICAgICBvcmlnaW5hbEFsbERheVxuICAgICAgICAgICAgb3JpZ2luYWxTdGFydERhdGVcbiAgICAgICAgICAgIG9yaWdpbmFsVGltZXpvbmVcbiAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgICAgICBwb3NpdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgICAgICBwb3NpdGl2ZUltcGFjdFRpbWVcbiAgICAgICAgICAgIHBvc3RFdmVudElkXG4gICAgICAgICAgICBwcmVFdmVudElkXG4gICAgICAgICAgICBwcmVmZXJyZWREYXlPZldlZWtcbiAgICAgICAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICAgICAgICAgIHByZWZlcnJlZFRpbWVcbiAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICBwcml2YXRlQ29weVxuICAgICAgICAgICAgcmVjdXJyZW5jZVxuICAgICAgICAgICAgcmVjdXJyZW5jZVJ1bGVcbiAgICAgICAgICAgIHJlY3VycmluZ0V2ZW50SWRcbiAgICAgICAgICAgIHNlbmRVcGRhdGVzXG4gICAgICAgICAgICBzb2Z0RGVhZGxpbmVcbiAgICAgICAgICAgIHNvdXJjZVxuICAgICAgICAgICAgc3RhcnREYXRlXG4gICAgICAgICAgICBzdGF0dXNcbiAgICAgICAgICAgIHN1bW1hcnlcbiAgICAgICAgICAgIHRhc2tJZFxuICAgICAgICAgICAgdGFza1R5cGVcbiAgICAgICAgICAgIHRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgIHRpdGxlXG4gICAgICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgICAgIHVubGlua1xuICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgdXNlck1vZGlmaWVkQ2F0ZWdvcmllc1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkRHVyYXRpb25cbiAgICAgICAgICAgIHVzZXJNb2RpZmllZElzQnJlYWtcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRJc01lZXRpbmdcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZFJlbWluZGVyc1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgdmlzaWJpbGl0eVxuICAgICAgICAgICAgd2Vla2x5VGFza0xpc3RcbiAgICAgICAgICAgIGJ5V2Vla0RheVxuICAgICAgICAgICAgbG9jYWxTeW5jZWRcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZENvbG9yXG4gICAgICAgICAgICBjb3B5Q29sb3JcbiAgICAgICAgICAgIGNvcHlFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgICAgICAgYDtcbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBFdmVudDogRXZlbnRUeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgIHN0YXJ0RGF0ZTogZGF5anMoc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgICAgICBlbmREYXRlOiBkYXlqcyhlbmREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLmZvcm1hdCgpLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBsaXN0RXZlbnRzZm9yVXNlcicpO1xuICAgIHJldHVybiByZXM/LmRhdGE/LkV2ZW50O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gbGlzdCBldmVudHMgZm9yIGRhdGUnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RFdmVudHNGb3JVc2VyR2l2ZW5EYXRlcyA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGhvc3RTdGFydERhdGU6IHN0cmluZyxcbiAgaG9zdEVuZERhdGU6IHN0cmluZyxcbiAgdXNlclRpbWV6b25lOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2xpc3RFdmVudHNGb3JVc2VyJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IGxpc3RFdmVudHNGb3JVc2VyKCR1c2VySWQ6IHV1aWQhLCAkc3RhcnREYXRlOiB0aW1lc3RhbXAhLCAkZW5kRGF0ZTogdGltZXN0YW1wISkge1xuICAgICAgICAgICAgICAgIEV2ZW50KHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgZW5kRGF0ZToge19ndGU6ICRzdGFydERhdGV9LCBzdGFydERhdGU6IHtfbHRlOiAkZW5kRGF0ZX0sIGRlbGV0ZWQ6IHtfbmVxOiB0cnVlfSwgYWxsRGF5OiB7X25lcTogdHJ1ZX19KSB7XG4gICAgICAgICAgICAgICAgICAgIGFsbERheVxuICAgICAgICAgICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICAgICAgICAgICAgICAgIGF0dGFjaG1lbnRzXG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlc09taXR0ZWRcbiAgICAgICAgICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgICAgICAgICBjb25mZXJlbmNlSWRcbiAgICAgICAgICAgICAgICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICBjb3B5Q2F0ZWdvcmllc1xuICAgICAgICAgICAgICAgICAgICBjb3B5RHVyYXRpb25cbiAgICAgICAgICAgICAgICAgICAgY29weUlzQnJlYWtcbiAgICAgICAgICAgICAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgICAgICAgICAgY29weVJlbWluZGVyc1xuICAgICAgICAgICAgICAgICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICAgICAgICAgICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBjcmVhdG9yXG4gICAgICAgICAgICAgICAgICAgIGRhaWx5VGFza0xpc3RcbiAgICAgICAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICAgICAgICBkdXJhdGlvblxuICAgICAgICAgICAgICAgICAgICBlbmREYXRlXG4gICAgICAgICAgICAgICAgICAgIGVuZFRpbWVVbnNwZWNpZmllZFxuICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgIGV2ZW50VHlwZVxuICAgICAgICAgICAgICAgICAgICBleHRlbmRlZFByb3BlcnRpZXNcbiAgICAgICAgICAgICAgICAgICAgZm9sbG93VXBFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIGZvckV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5Nb2RpZnlcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgICAgICAgICAgICAgICAgaGFuZ291dExpbmtcbiAgICAgICAgICAgICAgICAgICAgaGFyZERlYWRsaW5lXG4gICAgICAgICAgICAgICAgICAgIGh0bWxMaW5rXG4gICAgICAgICAgICAgICAgICAgIGlDYWxVSURcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgaXNCcmVha1xuICAgICAgICAgICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgaXNGb2xsb3dVcFxuICAgICAgICAgICAgICAgICAgICBpc01lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICBpc1Bvc3RFdmVudFxuICAgICAgICAgICAgICAgICAgICBpc1ByZUV2ZW50XG4gICAgICAgICAgICAgICAgICAgIGxpbmtzXG4gICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uXG4gICAgICAgICAgICAgICAgICAgIGxvY2tlZFxuICAgICAgICAgICAgICAgICAgICBtYXhBdHRlbmRlZXNcbiAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgIG1ldGhvZFxuICAgICAgICAgICAgICAgICAgICBtb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3RUaW1lXG4gICAgICAgICAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICAgICAgICAgIG9yZ2FuaXplclxuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbEFsbERheVxuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RUaW1lXG4gICAgICAgICAgICAgICAgICAgIHBvc3RFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIHByZUV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZVxuICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRUaW1lXG4gICAgICAgICAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICAgICAgICAgIHByaXZhdGVDb3B5XG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyZW5jZVJ1bGVcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyaW5nRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBzZW5kVXBkYXRlc1xuICAgICAgICAgICAgICAgICAgICBzb2Z0RGVhZGxpbmVcbiAgICAgICAgICAgICAgICAgICAgc291cmNlXG4gICAgICAgICAgICAgICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBzdGF0dXNcbiAgICAgICAgICAgICAgICAgICAgc3VtbWFyeVxuICAgICAgICAgICAgICAgICAgICB0YXNrSWRcbiAgICAgICAgICAgICAgICAgICAgdGFza1R5cGVcbiAgICAgICAgICAgICAgICAgICAgdGltZUJsb2NraW5nXG4gICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHRpdGxlXG4gICAgICAgICAgICAgICAgICAgIHRyYW5zcGFyZW5jeVxuICAgICAgICAgICAgICAgICAgICB1bmxpbmtcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRDYXRlZ29yaWVzXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZER1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzQnJlYWtcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgICAgICAgICAgIHZpc2liaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgd2Vla2x5VGFza0xpc3RcbiAgICAgICAgICAgICAgICAgICAgYnlXZWVrRGF5XG4gICAgICAgICAgICAgICAgICAgIGxvY2FsU3luY2VkXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGNvcHlDb2xvclxuICAgICAgICAgICAgICAgICAgICBjb3B5RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuICAgIGNvbnN0IHN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgdHJ1ZVxuICAgICk7XG4gICAgY29uc3QgZW5kRGF0ZUluSG9zdFRpbWV6b25lID0gZGF5anMoaG9zdEVuZERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIHRydWVcbiAgICApO1xuICAgIGNvbnN0IHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lID0gZGF5anMoc3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLmZvcm1hdCgpXG4gICAgICAuc2xpY2UoMCwgMTkpO1xuICAgIGNvbnN0IGVuZERhdGVJblVzZXJUaW1lem9uZSA9IGRheWpzKGVuZERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuZm9ybWF0KClcbiAgICAgIC5zbGljZSgwLCAxOSk7XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBFdmVudDogRXZlbnRUeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgIHN0YXJ0RGF0ZTogc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUsXG4gICAgICAgICAgICBlbmREYXRlOiBlbmREYXRlSW5Vc2VyVGltZXpvbmUsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGxpc3RFdmVudHNmb3JVc2VyJyk7XG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uRXZlbnQ7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIGxpc3RFdmVudHNGb3JVc2VyJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzTWVldGluZ0Fzc2lzdEZvck9wdGFwbGFubmVyID0gYXN5bmMgKCkgPT4ge1xuICB0cnkge1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcHJvY2VzcyBtZWV0aW5nIGFzc2lzdCBmb3Igb3B0YXBsYW5uZXInKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlTmV3TWVldGluZ0V2ZW50Rm9yQXR0ZW5kZWUgPSAoXG4gIGF0dGVuZGVlOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlLFxuICBtZWV0aW5nQXNzaXN0OiBNZWV0aW5nQXNzaXN0VHlwZSxcbiAgd2luZG93U3RhcnREYXRlOiBzdHJpbmcsXG4gIHdpbmRvd0VuZERhdGU6IHN0cmluZyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ/OiBzdHJpbmcsXG4gIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPzogTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVcbik6IEV2ZW50VHlwZSA9PiB7XG4gIGxldCBzdGFydERhdGUgPSBkYXlqcyh3aW5kb3dTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLmZvcm1hdCgpO1xuICBjb25zdCBlbmREYXRlID0gZGF5anMod2luZG93RW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAuZm9ybWF0KCk7XG4gIGNvbnNvbGUubG9nKFxuICAgIHN0YXJ0RGF0ZSxcbiAgICAnIHN0YXJ0RGF0ZSBpbnNpZGUgZ2VuZXJhdGVOZXdNZWV0aW5nRXZlbnRGb3JBdHRlbmRlZSBzdGVwIDEnXG4gICk7XG4gIGlmIChwcmVmZXJyZWRTdGFydFRpbWVSYW5nZT8uZGF5T2ZXZWVrID4gMCkge1xuICAgIGNvbnN0IGRhdGVPYmplY3QgPSBkYXlqcyhzdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50b0RhdGUoKTtcbiAgICBjb25zdCBkYXRlT2JqZWN0V2l0aFNldElTT0RheVBvc3NpYmxlID0gc2V0SVNPRGF5KFxuICAgICAgZGF0ZU9iamVjdCxcbiAgICAgIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPy5kYXlPZldlZWtcbiAgICApO1xuICAgIGNvbnN0IG9yaWdpbmFsRGF0ZU9iamVjdFdpdGhTZXRJU09EYXkgPSBkYXRlT2JqZWN0V2l0aFNldElTT0RheVBvc3NpYmxlO1xuICAgIGxldCBkYXRlT2JqZWN0V2l0aFNldElTT0RheSA9IG9yaWdpbmFsRGF0ZU9iamVjdFdpdGhTZXRJU09EYXk7XG5cbiAgICBpZiAoIWRheWpzKGRhdGVPYmplY3RXaXRoU2V0SVNPRGF5KS5pc0JldHdlZW4oc3RhcnREYXRlLCBlbmREYXRlKSkge1xuICAgICAgZGF0ZU9iamVjdFdpdGhTZXRJU09EYXkgPSBkYXlqcyhvcmlnaW5hbERhdGVPYmplY3RXaXRoU2V0SVNPRGF5KVxuICAgICAgICAuYWRkKDEsICd3ZWVrJylcbiAgICAgICAgLnRvRGF0ZSgpO1xuICAgIH1cblxuICAgIGlmICghZGF5anMoZGF0ZU9iamVjdFdpdGhTZXRJU09EYXkpLmlzQmV0d2VlbihzdGFydERhdGUsIGVuZERhdGUpKSB7XG4gICAgICBkYXRlT2JqZWN0V2l0aFNldElTT0RheSA9IGRheWpzKG9yaWdpbmFsRGF0ZU9iamVjdFdpdGhTZXRJU09EYXkpXG4gICAgICAgIC5zdWJ0cmFjdCgxLCAnd2VlaycpXG4gICAgICAgIC50b0RhdGUoKTtcbiAgICB9XG5cbiAgICBzdGFydERhdGUgPSBkYXlqcyhkYXRlT2JqZWN0V2l0aFNldElTT0RheSkudHooaG9zdFRpbWV6b25lKS5mb3JtYXQoKTtcbiAgfVxuXG4gIGNvbnNvbGUubG9nKFxuICAgIHN0YXJ0RGF0ZSxcbiAgICAnIHN0YXJ0RGF0ZSBpbnNpZGUgZ2VuZXJhdGVOZXdNZWV0aW5nRXZlbnRGb3JBdHRlbmRlZSBzdGVwIDInXG4gICk7XG5cbiAgaWYgKHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPy5zdGFydFRpbWUpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPy5zdGFydFRpbWUsXG4gICAgICAnIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPy5zdGFydFRpbWUnXG4gICAgKTtcbiAgICBjb25zdCBzdGFydFRpbWUgPSBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZT8uc3RhcnRUaW1lO1xuICAgIGNvbnN0IGhvdXIgPSBwYXJzZUludChzdGFydFRpbWUuc2xpY2UoMCwgMiksIDEwKTtcblxuICAgIGNvbnNvbGUubG9nKGhvdXIsICcgaG91cicpO1xuICAgIGNvbnN0IG1pbnV0ZSA9IHBhcnNlSW50KHN0YXJ0VGltZS5zbGljZSgzKSwgMTApO1xuXG4gICAgY29uc29sZS5sb2cobWludXRlLCAnIG1pbnV0ZScpO1xuXG4gICAgc3RhcnREYXRlID0gZGF5anMoc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuaG91cihob3VyKVxuICAgICAgLm1pbnV0ZShtaW51dGUpXG4gICAgICAuZm9ybWF0KCk7XG4gIH1cblxuICBjb25zb2xlLmxvZyhcbiAgICBzdGFydERhdGUsXG4gICAgJyBzdGFydERhdGUgaW5zaWRlIGdlbmVyYXRlTmV3TWVldGluZ0V2ZW50Rm9yQXR0ZW5kZWUgc3RlcCAzJ1xuICApO1xuXG4gIGNvbnN0IGV2ZW50SWQgPSB1dWlkKCk7XG5cbiAgY29uc3QgbmV3RXZlbnQ6IEV2ZW50VHlwZSA9IHtcbiAgICBpZDogYCR7ZXZlbnRJZH0jJHtjYWxlbmRhcklkID8/IG1lZXRpbmdBc3Npc3QuY2FsZW5kYXJJZH1gLFxuICAgIG1ldGhvZDogJ2NyZWF0ZScsXG4gICAgdGl0bGU6IG1lZXRpbmdBc3Npc3Quc3VtbWFyeSxcbiAgICBzdGFydERhdGUsXG4gICAgZW5kRGF0ZTogZGF5anMoc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuYWRkKG1lZXRpbmdBc3Npc3QuZHVyYXRpb24sICdtJylcbiAgICAgIC5mb3JtYXQoKSxcbiAgICBhbGxEYXk6IGZhbHNlLFxuICAgIG5vdGVzOiBtZWV0aW5nQXNzaXN0Lm5vdGVzLFxuICAgIHRpbWV6b25lOiBob3N0VGltZXpvbmUsXG4gICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgZGVsZXRlZDogZmFsc2UsXG4gICAgcHJpb3JpdHk6IG1lZXRpbmdBc3Npc3QucHJpb3JpdHksXG4gICAgaXNGb2xsb3dVcDogZmFsc2UsXG4gICAgaXNQcmVFdmVudDogZmFsc2UsXG4gICAgaXNQb3N0RXZlbnQ6IGZhbHNlLFxuICAgIG1vZGlmaWFibGU6IHRydWUsXG4gICAgc2VuZFVwZGF0ZXM6IG1lZXRpbmdBc3Npc3Q/LnNlbmRVcGRhdGVzLFxuICAgIHN0YXR1czogJ2NvbmZpcm1lZCcsXG4gICAgc3VtbWFyeTogbWVldGluZ0Fzc2lzdC5zdW1tYXJ5LFxuICAgIHRyYW5zcGFyZW5jeTogbWVldGluZ0Fzc2lzdD8udHJhbnNwYXJlbmN5LFxuICAgIHZpc2liaWxpdHk6IG1lZXRpbmdBc3Npc3Q/LnZpc2liaWxpdHksXG4gICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIGNhbGVuZGFySWQ6IGNhbGVuZGFySWQgPz8gbWVldGluZ0Fzc2lzdC5jYWxlbmRhcklkLFxuICAgIHVzZURlZmF1bHRBbGFybXM6IG1lZXRpbmdBc3Npc3QudXNlRGVmYXVsdEFsYXJtcyxcbiAgICB0aW1lQmxvY2tpbmc6IG1lZXRpbmdBc3Npc3QuYnVmZmVyVGltZSxcbiAgICB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmc6IG1lZXRpbmdBc3Npc3Q/LmJ1ZmZlclRpbWUgPyB0cnVlIDogZmFsc2UsXG4gICAgdXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2U6IHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPy5pZCA/IHRydWUgOiBmYWxzZSxcbiAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnM6IG1lZXRpbmdBc3Npc3Q/LnJlbWluZGVycz8uWzBdID4gLTEgPyB0cnVlIDogZmFsc2UsXG4gICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbDogdHJ1ZSxcbiAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlOiB0cnVlLFxuICAgIGR1cmF0aW9uOiBtZWV0aW5nQXNzaXN0Py5kdXJhdGlvbixcbiAgICB1c2VyTW9kaWZpZWREdXJhdGlvbjogdHJ1ZSxcbiAgICB1c2VySWQ6IGF0dGVuZGVlPy51c2VySWQsXG4gICAgYW55b25lQ2FuQWRkU2VsZjogZmFsc2UsXG4gICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiBtZWV0aW5nQXNzaXN0Py5ndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM6IG1lZXRpbmdBc3Npc3Q/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgIG9yaWdpbmFsU3RhcnREYXRlOiB1bmRlZmluZWQsXG4gICAgb3JpZ2luYWxBbGxEYXk6IGZhbHNlLFxuICAgIG1lZXRpbmdJZDogbWVldGluZ0Fzc2lzdC5pZCxcbiAgICBldmVudElkLFxuICB9O1xuXG4gIGNvbnNvbGUubG9nKG5ld0V2ZW50LCAnIG5ld0V2ZW50IGluc2lkZSBnZW5lcmF0ZU5ld01lZXRpbmdFdmVudEZvckF0dGVuZGVlJyk7XG4gIHJldHVybiBuZXdFdmVudDtcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZU5ld01lZXRpbmdFdmVudEZvckhvc3QgPSAoXG4gIGhvc3RBdHRlbmRlZTogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSxcbiAgbWVldGluZ0Fzc2lzdDogTWVldGluZ0Fzc2lzdFR5cGUsXG4gIHdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nLFxuICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZT86IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlXG4pOiBFdmVudFR5cGUgPT4ge1xuICBsZXQgc3RhcnREYXRlID0gZGF5anMod2luZG93U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgIC5mb3JtYXQoKTtcbiAgY29uc3QgZW5kRGF0ZSA9IGRheWpzKHdpbmRvd0VuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLmZvcm1hdCgpO1xuICBjb25zb2xlLmxvZyhcbiAgICBzdGFydERhdGUsXG4gICAgJyBzdGFydERhdGUgaW5zaWRlIGdlbmVyYXRlTmV3TWVldGluZ0V2ZW50Rm9yQXR0ZW5kZWUgc3RlcCAxJ1xuICApO1xuICBpZiAocHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U/LmRheU9mV2VlayA+IDApIHtcbiAgICBjb25zdCBkYXRlT2JqZWN0ID0gZGF5anMoc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAudG9EYXRlKCk7XG4gICAgY29uc3QgZGF0ZU9iamVjdFdpdGhTZXRJU09EYXlQb3NzaWJsZSA9IHNldElTT0RheShcbiAgICAgIGRhdGVPYmplY3QsXG4gICAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZT8uZGF5T2ZXZWVrXG4gICAgKTtcbiAgICBsZXQgZGF0ZU9iamVjdFdpdGhTZXRJU09EYXkgPSBkYXRlT2JqZWN0V2l0aFNldElTT0RheVBvc3NpYmxlO1xuICAgIGlmICghZGF5anMoZGF0ZU9iamVjdFdpdGhTZXRJU09EYXlQb3NzaWJsZSkuaXNCZXR3ZWVuKHN0YXJ0RGF0ZSwgZW5kRGF0ZSkpIHtcbiAgICAgIGRhdGVPYmplY3RXaXRoU2V0SVNPRGF5ID0gZGF5anMoZGF0ZU9iamVjdFdpdGhTZXRJU09EYXlQb3NzaWJsZSlcbiAgICAgICAgLmFkZCgxLCAnd2VlaycpXG4gICAgICAgIC50b0RhdGUoKTtcbiAgICB9XG4gICAgc3RhcnREYXRlID0gZGF5anMoZGF0ZU9iamVjdFdpdGhTZXRJU09EYXkpLnR6KGhvc3RUaW1lem9uZSkuZm9ybWF0KCk7XG4gIH1cblxuICBjb25zb2xlLmxvZyhcbiAgICBzdGFydERhdGUsXG4gICAgJyBzdGFydERhdGUgaW5zaWRlIGdlbmVyYXRlTmV3TWVldGluZ0V2ZW50Rm9yQXR0ZW5kZWUgc3RlcCAyJ1xuICApO1xuXG4gIGlmIChwcmVmZXJyZWRTdGFydFRpbWVSYW5nZT8uc3RhcnRUaW1lKSB7XG4gICAgY29uc3Qgc3RhcnRUaW1lID0gcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U/LnN0YXJ0VGltZTtcbiAgICBjb25zdCBob3VyID0gcGFyc2VJbnQoc3RhcnRUaW1lLnNsaWNlKDAsIDIpLCAxMCk7XG4gICAgY29uc3QgbWludXRlID0gcGFyc2VJbnQoc3RhcnRUaW1lLnNsaWNlKDMpLCAxMCk7XG5cbiAgICBzdGFydERhdGUgPSBkYXlqcyhzdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5ob3VyKGhvdXIpXG4gICAgICAubWludXRlKG1pbnV0ZSlcbiAgICAgIC5mb3JtYXQoKTtcbiAgfVxuXG4gIGNvbnNvbGUubG9nKFxuICAgIHN0YXJ0RGF0ZSxcbiAgICAnIHN0YXJ0RGF0ZSBpbnNpZGUgZ2VuZXJhdGVOZXdNZWV0aW5nRXZlbnRGb3JBdHRlbmRlZSBzdGVwIDMnXG4gICk7XG5cbiAgY29uc3QgZXZlbnRJZCA9IHV1aWQoKTtcblxuICBjb25zdCBuZXdFdmVudDogRXZlbnRUeXBlID0ge1xuICAgIGlkOiBgJHtldmVudElkfSMke21lZXRpbmdBc3Npc3QuY2FsZW5kYXJJZH1gLFxuICAgIG1ldGhvZDogJ2NyZWF0ZScsXG4gICAgdGl0bGU6IG1lZXRpbmdBc3Npc3Quc3VtbWFyeSxcbiAgICBzdGFydERhdGUsXG4gICAgZW5kRGF0ZTogZGF5anMoc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuYWRkKG1lZXRpbmdBc3Npc3QuZHVyYXRpb24sICdtJylcbiAgICAgIC5mb3JtYXQoKSxcbiAgICBhbGxEYXk6IGZhbHNlLFxuICAgIG5vdGVzOiBtZWV0aW5nQXNzaXN0Lm5vdGVzLFxuICAgIHRpbWV6b25lOiBob3N0VGltZXpvbmUsXG4gICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgZGVsZXRlZDogZmFsc2UsXG4gICAgcHJpb3JpdHk6IG1lZXRpbmdBc3Npc3QucHJpb3JpdHksXG4gICAgaXNGb2xsb3dVcDogZmFsc2UsXG4gICAgaXNQcmVFdmVudDogZmFsc2UsXG4gICAgaXNQb3N0RXZlbnQ6IGZhbHNlLFxuICAgIG1vZGlmaWFibGU6IHRydWUsXG4gICAgc2VuZFVwZGF0ZXM6IG1lZXRpbmdBc3Npc3Q/LnNlbmRVcGRhdGVzLFxuICAgIHN0YXR1czogJ2NvbmZpcm1lZCcsXG4gICAgc3VtbWFyeTogbWVldGluZ0Fzc2lzdC5zdW1tYXJ5LFxuICAgIHRyYW5zcGFyZW5jeTogbWVldGluZ0Fzc2lzdD8udHJhbnNwYXJlbmN5LFxuICAgIHZpc2liaWxpdHk6IG1lZXRpbmdBc3Npc3Q/LnZpc2liaWxpdHksXG4gICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIGNhbGVuZGFySWQ6IG1lZXRpbmdBc3Npc3QuY2FsZW5kYXJJZCxcbiAgICB1c2VEZWZhdWx0QWxhcm1zOiBtZWV0aW5nQXNzaXN0LnVzZURlZmF1bHRBbGFybXMsXG4gICAgdGltZUJsb2NraW5nOiBtZWV0aW5nQXNzaXN0LmJ1ZmZlclRpbWUsXG4gICAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nOiBtZWV0aW5nQXNzaXN0Py5idWZmZXJUaW1lID8gdHJ1ZSA6IGZhbHNlLFxuICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlOiBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZT8uaWQgPyB0cnVlIDogZmFsc2UsXG4gICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzOiBtZWV0aW5nQXNzaXN0Py5yZW1pbmRlcnM/LlswXSA+IC0xID8gdHJ1ZSA6IGZhbHNlLFxuICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWw6IHRydWUsXG4gICAgdXNlck1vZGlmaWVkTW9kaWZpYWJsZTogdHJ1ZSxcbiAgICBkdXJhdGlvbjogbWVldGluZ0Fzc2lzdD8uZHVyYXRpb24sXG4gICAgdXNlck1vZGlmaWVkRHVyYXRpb246IHRydWUsXG4gICAgdXNlcklkOiBob3N0QXR0ZW5kZWU/LnVzZXJJZCxcbiAgICBhbnlvbmVDYW5BZGRTZWxmOiBmYWxzZSxcbiAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnM6IG1lZXRpbmdBc3Npc3Q/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0czogbWVldGluZ0Fzc2lzdD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgb3JpZ2luYWxTdGFydERhdGU6IHVuZGVmaW5lZCxcbiAgICBvcmlnaW5hbEFsbERheTogZmFsc2UsXG4gICAgbWVldGluZ0lkOiBtZWV0aW5nQXNzaXN0LmlkLFxuICAgIGV2ZW50SWQsXG4gIH07XG5cbiAgcmV0dXJuIG5ld0V2ZW50O1xufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQgPSBhc3luYyAoZXZlbnRJZDogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgaWYgKCFldmVudElkKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgJyBubyBldmVudElkIGluc2lkZSBsaXN0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50J1xuICAgICAgKTtcbiAgICB9XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdMaXN0UHJlZmVycmVkVGltZVJhbmdlc0dpdmVuRXZlbnRJZCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBxdWVyeSBMaXN0UHJlZmVycmVkVGltZVJhbmdlc0dpdmVuRXZlbnRJZCgkZXZlbnRJZDogU3RyaW5nISkge1xuICAgICAgICBQcmVmZXJyZWRUaW1lUmFuZ2Uod2hlcmU6IHtldmVudElkOiB7X2VxOiAkZXZlbnRJZH19KSB7XG4gICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICBkYXlPZldlZWtcbiAgICAgICAgICBlbmRUaW1lXG4gICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgIGlkXG4gICAgICAgICAgc3RhcnRUaW1lXG4gICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgdXNlcklkXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGV2ZW50SWQsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IFByZWZlcnJlZFRpbWVSYW5nZTogUHJlZmVycmVkVGltZVJhbmdlVHlwZVtdIH0gfSA9XG4gICAgICBhd2FpdCBnb3RcbiAgICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBqc29uOiB7XG4gICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgcXVlcnksXG4gICAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgaW5zaWRlICBsaXN0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50Jyk7XG4gICAgcmVzPy5kYXRhPy5QcmVmZXJyZWRUaW1lUmFuZ2U/Lm1hcCgocHQpID0+XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgcHQsXG4gICAgICAgICcgcHJlZmVycmVkVGltZVJhbmdlIC0gcmVzPy5kYXRhPy5QcmVmZXJyZWRUaW1lUmFuZ2UgaW5zaWRlICBsaXN0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50ICdcbiAgICAgIClcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uUHJlZmVycmVkVGltZVJhbmdlO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gbGlzdCBwcmVmZXJyZWQgdGltZSByYW5nZXMgZm9yIGV2ZW50Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVSZW1pbmRlcnNGcm9tTWludXRlc0FuZEV2ZW50ID0gKFxuICBldmVudElkOiBzdHJpbmcsXG4gIG1pbnV0ZXM6IG51bWJlcltdLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICB1c2VEZWZhdWx0OiBib29sZWFuLFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUmVtaW5kZXJzRm9yRXZlbnRUeXBlID0+IHtcbiAgcmV0dXJuIHtcbiAgICBldmVudElkLFxuICAgIHJlbWluZGVyczogbWludXRlcy5tYXAoKG0pID0+ICh7XG4gICAgICBpZDogdXVpZCgpLFxuICAgICAgdXNlcklkLFxuICAgICAgZXZlbnRJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgbWludXRlczogbSxcbiAgICAgIHVzZURlZmF1bHQsXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgIGRlbGV0ZWQ6IHRydWUsXG4gICAgfSkpLFxuICB9O1xufTtcblxuZXhwb3J0IGNvbnN0IGNyZWF0ZUJ1ZmZlclRpbWVGb3JOZXdNZWV0aW5nRXZlbnQgPSAoXG4gIGV2ZW50OiBFdmVudE1lZXRpbmdQbHVzVHlwZSxcbiAgYnVmZmVyVGltZTogQnVmZmVyVGltZU51bWJlclR5cGVcbikgPT4ge1xuICBsZXQgdmFsdWVzVG9SZXR1cm46IGFueSA9IHt9O1xuICB2YWx1ZXNUb1JldHVybi5uZXdFdmVudCA9IGV2ZW50O1xuICBjb25zdCBldmVudElkID0gdXVpZCgpO1xuICBjb25zdCBldmVudElkMSA9IHV1aWQoKTtcbiAgY29uc3QgcHJlRXZlbnRJZCA9IGV2ZW50Py5wcmVFdmVudElkIHx8IGAke2V2ZW50SWR9IyR7ZXZlbnQ/LmNhbGVuZGFySWR9YDtcbiAgY29uc3QgcG9zdEV2ZW50SWQgPSBldmVudD8ucG9zdEV2ZW50SWQgfHwgYCR7ZXZlbnRJZDF9IyR7ZXZlbnQ/LmNhbGVuZGFySWR9YDtcblxuICBpZiAoYnVmZmVyVGltZS5iZWZvcmVFdmVudCA+IDApIHtcbiAgICBjb25zdCBiZWZvcmVFdmVudE9yRW1wdHk6IEV2ZW50UGx1c1R5cGUgPSB7XG4gICAgICBpZDogcHJlRXZlbnRJZCxcbiAgICAgIGlzUHJlRXZlbnQ6IHRydWUsXG4gICAgICBmb3JFdmVudElkOiBldmVudC5pZCxcbiAgICAgIG5vdGVzOiAnQnVmZmVyIHRpbWUnLFxuICAgICAgc3VtbWFyeTogJ0J1ZmZlciB0aW1lJyxcbiAgICAgIHN0YXJ0RGF0ZTogZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuc3VidHJhY3QoYnVmZmVyVGltZS5iZWZvcmVFdmVudCwgJ20nKVxuICAgICAgICAuZm9ybWF0KCksXG4gICAgICBlbmREYXRlOiBkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIG1ldGhvZDogJ2NyZWF0ZScsXG4gICAgICB1c2VySWQ6IGV2ZW50LnVzZXJJZCxcbiAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICBwcmlvcml0eTogMSxcbiAgICAgIG1vZGlmaWFibGU6IHRydWUsXG4gICAgICBhbnlvbmVDYW5BZGRTZWxmOiBmYWxzZSxcbiAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyczogZmFsc2UsXG4gICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0czogZmFsc2UsXG4gICAgICBvcmlnaW5hbFN0YXJ0RGF0ZTogdW5kZWZpbmVkLFxuICAgICAgb3JpZ2luYWxBbGxEYXk6IGZhbHNlLFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICBjYWxlbmRhcklkOiBldmVudD8uY2FsZW5kYXJJZCxcbiAgICAgIHRpbWV6b25lOiBldmVudD8udGltZXpvbmUsXG4gICAgICBpc0ZvbGxvd1VwOiBmYWxzZSxcbiAgICAgIGlzUG9zdEV2ZW50OiBmYWxzZSxcbiAgICAgIGV2ZW50SWQ6IHByZUV2ZW50SWQuc3BsaXQoJyMnKVswXSxcbiAgICB9O1xuXG4gICAgdmFsdWVzVG9SZXR1cm4uYmVmb3JlRXZlbnQgPSBiZWZvcmVFdmVudE9yRW1wdHk7XG4gICAgdmFsdWVzVG9SZXR1cm4ubmV3RXZlbnQgPSB7XG4gICAgICAuLi52YWx1ZXNUb1JldHVybi5uZXdFdmVudCxcbiAgICAgIHByZUV2ZW50SWQsXG4gICAgICB0aW1lQmxvY2tpbmc6IHtcbiAgICAgICAgLi4udmFsdWVzVG9SZXR1cm4/Lm5ld0V2ZW50Py50aW1lQmxvY2tpbmcsXG4gICAgICAgIGJlZm9yZUV2ZW50OiBidWZmZXJUaW1lLmJlZm9yZUV2ZW50LFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgaWYgKGJ1ZmZlclRpbWUuYWZ0ZXJFdmVudCA+IDApIHtcbiAgICBjb25zdCBhZnRlckV2ZW50T3JFbXB0eTogRXZlbnRQbHVzVHlwZSA9IHtcbiAgICAgIGlkOiBwb3N0RXZlbnRJZCxcbiAgICAgIGlzUHJlRXZlbnQ6IGZhbHNlLFxuICAgICAgZm9yRXZlbnRJZDogZXZlbnQuaWQsXG4gICAgICBpc1Bvc3RFdmVudDogdHJ1ZSxcbiAgICAgIG5vdGVzOiAnQnVmZmVyIHRpbWUnLFxuICAgICAgc3VtbWFyeTogJ0J1ZmZlciB0aW1lJyxcbiAgICAgIHN0YXJ0RGF0ZTogZGF5anMoZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgZW5kRGF0ZTogZGF5anMoZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmFkZChidWZmZXJUaW1lLmFmdGVyRXZlbnQsICdtJylcbiAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgbWV0aG9kOiAnY3JlYXRlJyxcbiAgICAgIHVzZXJJZDogZXZlbnQ/LnVzZXJJZCxcbiAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgIHByaW9yaXR5OiAxLFxuICAgICAgaXNGb2xsb3dVcDogZmFsc2UsXG4gICAgICBtb2RpZmlhYmxlOiB0cnVlLFxuICAgICAgYW55b25lQ2FuQWRkU2VsZjogZmFsc2UsXG4gICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnM6IGZhbHNlLFxuICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM6IGZhbHNlLFxuICAgICAgb3JpZ2luYWxTdGFydERhdGU6IHVuZGVmaW5lZCxcbiAgICAgIG9yaWdpbmFsQWxsRGF5OiBmYWxzZSxcbiAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgY2FsZW5kYXJJZDogZXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgICB0aW1lem9uZTogZXZlbnQ/LnRpbWV6b25lLFxuICAgICAgZXZlbnRJZDogcG9zdEV2ZW50SWQuc3BsaXQoJyMnKVswXSxcbiAgICB9O1xuXG4gICAgdmFsdWVzVG9SZXR1cm4uYWZ0ZXJFdmVudCA9IGFmdGVyRXZlbnRPckVtcHR5O1xuICAgIHZhbHVlc1RvUmV0dXJuLm5ld0V2ZW50ID0ge1xuICAgICAgLi4udmFsdWVzVG9SZXR1cm4ubmV3RXZlbnQsXG4gICAgICBwb3N0RXZlbnRJZCxcbiAgICAgIHRpbWVCbG9ja2luZzoge1xuICAgICAgICAuLi52YWx1ZXNUb1JldHVybj8ubmV3RXZlbnQ/LnRpbWVCbG9ja2luZyxcbiAgICAgICAgYWZ0ZXJFdmVudDogYnVmZmVyVGltZS5hZnRlckV2ZW50LFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgcmV0dXJuIHZhbHVlc1RvUmV0dXJuIGFzIFZhbHVlc1RvUmV0dXJuRm9yQnVmZmVyRXZlbnRzVHlwZTtcbn07XG5cbmV4cG9ydCBjb25zdCBnZXRVc2VyUHJlZmVyZW5jZXMgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nXG4pOiBQcm9taXNlPFVzZXJQcmVmZXJlbmNlVHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGlmICghdXNlcklkKSB7XG4gICAgICBjb25zb2xlLmxvZygndXNlcklkIGlzIG51bGwnKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2dldFVzZXJQcmVmZXJlbmNlcyc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgcXVlcnkgZ2V0VXNlclByZWZlcmVuY2VzKCR1c2VySWQ6IHV1aWQhKSB7XG4gICAgICBVc2VyX1ByZWZlcmVuY2Uod2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9fSkge1xuICAgICAgICBzdGFydFRpbWVzXG4gICAgICAgIGVuZFRpbWVzXG4gICAgICAgIGJhY2tUb0JhY2tNZWV0aW5nc1xuICAgICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICAgIGNvcHlDYXRlZ29yaWVzXG4gICAgICAgIGNvcHlJc0JyZWFrXG4gICAgICAgIGNvcHlNb2RpZmlhYmxlXG4gICAgICAgIGNvcHlQcmlvcml0eUxldmVsXG4gICAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgICAgY29weVRpbWVCbG9ja2luZ1xuICAgICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgZGVsZXRlZFxuICAgICAgICBmb2xsb3dVcFxuICAgICAgICBpZFxuICAgICAgICBpc1B1YmxpY0NhbGVuZGFyXG4gICAgICAgIG1heE51bWJlck9mTWVldGluZ3NcbiAgICAgICAgbWF4V29ya0xvYWRQZXJjZW50XG4gICAgICAgIHB1YmxpY0NhbGVuZGFyQ2F0ZWdvcmllc1xuICAgICAgICByZW1pbmRlcnNcbiAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIHVzZXJJZFxuICAgICAgICBtaW5OdW1iZXJPZkJyZWFrc1xuICAgICAgICBicmVha0NvbG9yXG4gICAgICAgIGJyZWFrTGVuZ3RoXG4gICAgICAgIGNvcHlDb2xvclxuICAgICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgY29weUlzTWVldGluZ1xuICAgICAgICBvbkJvYXJkZWRcbiAgICAgIH1cbiAgICB9ICAgIFxuICBgO1xuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IFVzZXJfUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uVXNlcl9QcmVmZXJlbmNlPy5bMF07XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIGdldFVzZXJQcmVmZXJlbmNlcycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0R2xvYmFsQ2FsZW5kYXIgPSBhc3luYyAodXNlcklkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2dldEdsb2JhbENhbGVuZGFyJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgcXVlcnkgZ2V0R2xvYmFsQ2FsZW5kYXIoJHVzZXJJZDogdXVpZCEpIHtcbiAgICAgICAgICBDYWxlbmRhcih3aGVyZToge2dsb2JhbFByaW1hcnk6IHtfZXE6IHRydWV9LCB1c2VySWQ6IHtfZXE6ICR1c2VySWR9fSkge1xuICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICBhY2Nlc3NMZXZlbFxuICAgICAgICAgICAgYWNjb3VudFxuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGRlZmF1bHRSZW1pbmRlcnNcbiAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgZ2xvYmFsUHJpbWFyeVxuICAgICAgICAgICAgaWRcbiAgICAgICAgICAgIG1vZGlmaWFibGVcbiAgICAgICAgICAgIHByaW1hcnlcbiAgICAgICAgICAgIHJlc291cmNlXG4gICAgICAgICAgICB0aXRsZVxuICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICBgO1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgQ2FsZW5kYXI6IENhbGVuZGFyVHlwZVtdIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgcmV0dXJuIHJlcy5kYXRhLkNhbGVuZGFyPy5bMF07XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgZ2xvYmFsIGNhbGVuZGFyJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBhZGp1c3RTdGFydERhdGVzRm9yQnJlYWtFdmVudHNGb3JEYXkgPSAoXG4gIGFsbEV2ZW50czogRXZlbnRQbHVzVHlwZVtdLFxuICBicmVha0V2ZW50czogRXZlbnRQbHVzVHlwZVtdLFxuICB1c2VyUHJlZmVyZW5jZXM6IFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgdGltZXpvbmU6IHN0cmluZ1xuKTogRXZlbnRQbHVzVHlwZVtdID0+IHtcbiAgaWYgKCFhbGxFdmVudHM/LlswXT8uaWQpIHtcbiAgICBjb25zb2xlLmxvZygnbm8gYWxsRXZlbnRzIGluc2lkZSBhZGp1c3RTdGFydERhdGVzRm9yQnJlYWtFdmVudHMnKTtcbiAgICByZXR1cm47XG4gIH1cblxuICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2VzLnN0YXJ0VGltZXM7XG4gIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2VzLmVuZFRpbWVzO1xuICBjb25zdCBkYXlPZldlZWtJbnQgPSBnZXRJU09EYXkoXG4gICAgZGF5anMoYWxsRXZlbnRzPy5bMF0/LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICApO1xuICBjb25zdCBzdGFydEhvdXIgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gIGNvbnN0IHN0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuICBjb25zdCBlbmRIb3VyID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgY29uc3QgZW5kTWludXRlID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcbiAgY29uc3QgbmV3QnJlYWtFdmVudHMgPSBbXTtcblxuICBjb25zdCBzdGFydE9mV29ya2luZ0RheSA9IGRheWpzKGFsbEV2ZW50c1swXT8uc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHoodGltZXpvbmUsIHRydWUpXG4gICAgLmhvdXIoc3RhcnRIb3VyKVxuICAgIC5taW51dGUoc3RhcnRNaW51dGUpO1xuXG4gIGNvbnN0IGVuZE9mV29ya2luZ0RheSA9IGRheWpzKGFsbEV2ZW50c1swXT8uZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgLm1pbnV0ZShlbmRNaW51dGUpO1xuXG4gIGNvbnN0IGZpbHRlcmVkRXZlbnRzID0gYWxsRXZlbnRzLmZpbHRlcigoZSkgPT4gIWUuaXNCcmVhayk7XG4gIGNvbnN0IGJyZWFrTGVuZ3RoID1cbiAgICB1c2VyUHJlZmVyZW5jZXMuYnJlYWtMZW5ndGggPD0gMTUgPyAxNSA6IHVzZXJQcmVmZXJlbmNlcy5icmVha0xlbmd0aDtcbiAgaWYgKGJyZWFrRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgZm9yIChjb25zdCBicmVha0V2ZW50IG9mIGJyZWFrRXZlbnRzKSB7XG4gICAgICBsZXQgZm91bmRTcGFjZSA9IGZhbHNlO1xuICAgICAgbGV0IGluZGV4ID0gMDtcbiAgICAgIHdoaWxlICghZm91bmRTcGFjZSAmJiBpbmRleCA8IGZpbHRlcmVkRXZlbnRzLmxlbmd0aCkge1xuICAgICAgICBjb25zdCBwb3NzaWJsZUVuZERhdGUgPSBkYXlqcyhcbiAgICAgICAgICBmaWx0ZXJlZEV2ZW50c1tpbmRleF0uc3RhcnREYXRlLnNsaWNlKDAsIDE5KVxuICAgICAgICApLnR6KHRpbWV6b25lLCB0cnVlKTtcblxuICAgICAgICBjb25zdCBwb3NzaWJsZVN0YXJ0RGF0ZSA9IGRheWpzKHBvc3NpYmxlRW5kRGF0ZS5mb3JtYXQoKS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5zdWJ0cmFjdChicmVha0xlbmd0aCwgJ21pbnV0ZScpO1xuICAgICAgICBsZXQgaXNCZXR3ZWVuU3RhcnQgPSB0cnVlO1xuICAgICAgICBsZXQgaXNCZXR3ZWVuRW5kID0gdHJ1ZTtcbiAgICAgICAgbGV0IGJldHdlZW5JbmRleCA9IDA7XG4gICAgICAgIGxldCBiZXR3ZWVuV29ya2luZ0RheVN0YXJ0ID0gdHJ1ZTtcbiAgICAgICAgbGV0IGJldHdlZW5Xb3JraW5nRGF5RW5kID0gdHJ1ZTtcbiAgICAgICAgbGV0IGlzQmV0d2VlbkJyZWFrU3RhcnQgPSB0cnVlO1xuICAgICAgICBsZXQgaXNCZXR3ZWVuQnJlYWtFbmQgPSB0cnVlO1xuXG4gICAgICAgIHdoaWxlIChcbiAgICAgICAgICAoaXNCZXR3ZWVuU3RhcnQgfHxcbiAgICAgICAgICAgIGlzQmV0d2VlbkVuZCB8fFxuICAgICAgICAgICAgIWJldHdlZW5Xb3JraW5nRGF5U3RhcnQgfHxcbiAgICAgICAgICAgICFiZXR3ZWVuV29ya2luZ0RheUVuZCB8fFxuICAgICAgICAgICAgaXNCZXR3ZWVuQnJlYWtTdGFydCB8fFxuICAgICAgICAgICAgaXNCZXR3ZWVuQnJlYWtFbmQpICYmXG4gICAgICAgICAgYmV0d2VlbkluZGV4IDwgZmlsdGVyZWRFdmVudHMubGVuZ3RoXG4gICAgICAgICkge1xuICAgICAgICAgIGlzQmV0d2VlblN0YXJ0ID0gcG9zc2libGVTdGFydERhdGUuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMoZmlsdGVyZWRFdmVudHNbYmV0d2VlbkluZGV4XS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICAgIHRydWVcbiAgICAgICAgICAgICksXG4gICAgICAgICAgICBkYXlqcyhmaWx0ZXJlZEV2ZW50c1tiZXR3ZWVuSW5kZXhdLmVuZERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICAgIHRydWVcbiAgICAgICAgICAgICksXG4gICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICdbKSdcbiAgICAgICAgICApO1xuXG4gICAgICAgICAgaXNCZXR3ZWVuRW5kID0gcG9zc2libGVFbmREYXRlLmlzQmV0d2VlbihcbiAgICAgICAgICAgIGRheWpzKGZpbHRlcmVkRXZlbnRzW2JldHdlZW5JbmRleF0uc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooXG4gICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgICAgICB0cnVlXG4gICAgICAgICAgICApLFxuICAgICAgICAgICAgZGF5anMoZmlsdGVyZWRFdmVudHNbYmV0d2VlbkluZGV4XS5lbmREYXRlLnNsaWNlKDAsIDE5KSkudHooXG4gICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgICAgICB0cnVlXG4gICAgICAgICAgICApLFxuICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAnKF0nXG4gICAgICAgICAgKTtcblxuICAgICAgICAgIGJldHdlZW5Xb3JraW5nRGF5U3RhcnQgPSBwb3NzaWJsZVN0YXJ0RGF0ZS5pc0JldHdlZW4oXG4gICAgICAgICAgICBzdGFydE9mV29ya2luZ0RheSxcbiAgICAgICAgICAgIGVuZE9mV29ya2luZ0RheSxcbiAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICk7XG5cbiAgICAgICAgICBiZXR3ZWVuV29ya2luZ0RheUVuZCA9IHBvc3NpYmxlRW5kRGF0ZS5pc0JldHdlZW4oXG4gICAgICAgICAgICBzdGFydE9mV29ya2luZ0RheSxcbiAgICAgICAgICAgIGVuZE9mV29ya2luZ0RheSxcbiAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgJyhdJ1xuICAgICAgICAgICk7XG5cbiAgICAgICAgICBmb3IgKGNvbnN0IGJyZWFrRXZlbnQgb2YgYnJlYWtFdmVudHMpIHtcbiAgICAgICAgICAgIGlzQmV0d2VlbkJyZWFrU3RhcnQgPSBwb3NzaWJsZVN0YXJ0RGF0ZS5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKGJyZWFrRXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLFxuICAgICAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApO1xuXG4gICAgICAgICAgICBpc0JldHdlZW5CcmVha0VuZCA9IHBvc3NpYmxlRW5kRGF0ZS5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKGJyZWFrRXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLFxuICAgICAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnKF0nXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGJldHdlZW5JbmRleCsrO1xuICAgICAgICB9XG5cbiAgICAgICAgZm91bmRTcGFjZSA9XG4gICAgICAgICAgIWlzQmV0d2VlblN0YXJ0ICYmXG4gICAgICAgICAgIWlzQmV0d2VlbkVuZCAmJlxuICAgICAgICAgIGJldHdlZW5Xb3JraW5nRGF5U3RhcnQgJiZcbiAgICAgICAgICBiZXR3ZWVuV29ya2luZ0RheUVuZCAmJlxuICAgICAgICAgICFpc0JldHdlZW5CcmVha1N0YXJ0ICYmXG4gICAgICAgICAgIWlzQmV0d2VlbkJyZWFrRW5kO1xuXG4gICAgICAgIGlmIChmb3VuZFNwYWNlKSB7XG4gICAgICAgICAgY29uc3QgbmV3QnJlYWtFdmVudCA9IHtcbiAgICAgICAgICAgIC4uLmJyZWFrRXZlbnQsXG4gICAgICAgICAgICBzdGFydERhdGU6IHBvc3NpYmxlU3RhcnREYXRlLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICBlbmREYXRlOiBwb3NzaWJsZUVuZERhdGUudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICB9O1xuICAgICAgICAgIG5ld0JyZWFrRXZlbnRzLnB1c2gobmV3QnJlYWtFdmVudCk7XG4gICAgICAgIH1cblxuICAgICAgICBpbmRleCsrO1xuICAgICAgfVxuICAgIH1cbiAgfVxuXG4gIHJldHVybiBuZXdCcmVha0V2ZW50cztcbn07XG5leHBvcnQgY29uc3QgY29udmVydFRvVG90YWxXb3JraW5nSG91cnNGb3JJbnRlcm5hbEF0dGVuZGVlID0gKFxuICB1c2VyUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlLFxuICBob3N0U3RhcnREYXRlOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nXG4pID0+IHtcbiAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlLnN0YXJ0VGltZXM7XG4gIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2UuZW5kVGltZXM7XG4gIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICApO1xuICBjb25zdCBzdGFydEhvdXIgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gIGNvbnN0IHN0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuICBjb25zdCBlbmRIb3VyID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgY29uc3QgZW5kTWludXRlID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcblxuICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiBzdGFydEhvdXIsXG4gICAgbWludXRlczogc3RhcnRNaW51dGUsXG4gIH0pO1xuICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHsgaG91cnM6IGVuZEhvdXIsIG1pbnV0ZXM6IGVuZE1pbnV0ZSB9KTtcbiAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICByZXR1cm4gdG90YWxEdXJhdGlvbi5hc0hvdXJzKCk7XG59O1xuXG5leHBvcnQgY29uc3QgY29udmVydFRvVG90YWxXb3JraW5nSG91cnNGb3JFeHRlcm5hbEF0dGVuZGVlID0gKFxuICBhdHRlbmRlZUV2ZW50czogRXZlbnRQbHVzVHlwZVtdLFxuICBob3N0U3RhcnREYXRlOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICB1c2VyVGltZXpvbmU6IHN0cmluZ1xuKSA9PiB7XG4gIGNvbnN0IGRheU9mV2Vla0ludEJ5SG9zdCA9IGdldElTT0RheShcbiAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICApO1xuICBjb25zdCBzYW1lRGF5RXZlbnRzID0gYXR0ZW5kZWVFdmVudHMuZmlsdGVyKFxuICAgIChlKSA9PlxuICAgICAgZ2V0SVNPRGF5KFxuICAgICAgICBkYXlqcyhlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLnRvRGF0ZSgpXG4gICAgICApID09PSBkYXlPZldlZWtJbnRCeUhvc3RcbiAgKTtcbiAgY29uc3QgbWluU3RhcnREYXRlID0gXy5taW5CeShzYW1lRGF5RXZlbnRzLCAoZSkgPT5cbiAgICBkYXlqcyhlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLnVuaXgoKVxuICApO1xuICBjb25zdCBtYXhFbmREYXRlID0gXy5tYXhCeShzYW1lRGF5RXZlbnRzLCAoZSkgPT5cbiAgICBkYXlqcyhlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC51bml4KClcbiAgKTtcblxuICBsZXQgd29ya0VuZEhvdXJCeUhvc3QgPSBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAuaG91cigpO1xuICBjb25zdCB3b3JrRW5kTWludXRlQnlIb3N0ID0gZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmlzQmV0d2VlbihcbiAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5taW51dGUoMCksXG4gICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICdtaW51dGUnLFxuICAgICAgJ1spJ1xuICAgIClcbiAgICA/IDE1XG4gICAgOiBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgIClcbiAgICAgID8gMzBcbiAgICAgIDogZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoNDUpLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDQ1XG4gICAgICAgIDogMDtcbiAgaWYgKHdvcmtFbmRNaW51dGVCeUhvc3QgPT09IDApIHtcbiAgICBpZiAod29ya0VuZEhvdXJCeUhvc3QgPCAyMykge1xuICAgICAgd29ya0VuZEhvdXJCeUhvc3QgKz0gMTtcbiAgICB9XG4gIH1cblxuICBjb25zdCB3b3JrU3RhcnRIb3VyQnlIb3N0ID0gZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmhvdXIoKTtcbiAgY29uc3Qgd29ya1N0YXJ0TWludXRlQnlIb3N0ID0gZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmlzQmV0d2VlbihcbiAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5taW51dGUoMCksXG4gICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICdtaW51dGUnLFxuICAgICAgJ1spJ1xuICAgIClcbiAgICA/IDBcbiAgICA6IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAnWyknXG4gICAgICAgICAgKVxuICAgICAgPyAxNVxuICAgICAgOiBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSg0NSksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgID8gMzBcbiAgICAgICAgOiA0NTtcblxuICBjb25zb2xlLmxvZyhcbiAgICB3b3JrU3RhcnRIb3VyQnlIb3N0LFxuICAgIHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCxcbiAgICB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAnIHdvcmtTdGFydEhvdXJCeUhvc3QsIHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCwgd29ya0VuZEhvdXJCeUhvc3QgZm9yIHRvdGFsIHdvcmtpbmcgaG91cnMnXG4gICk7XG4gIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgaG91cnM6IHdvcmtTdGFydEhvdXJCeUhvc3QsXG4gICAgbWludXRlczogd29ya1N0YXJ0TWludXRlQnlIb3N0LFxuICB9KTtcbiAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgaG91cnM6IHdvcmtFbmRIb3VyQnlIb3N0LFxuICAgIG1pbnV0ZXM6IHdvcmtFbmRNaW51dGVCeUhvc3QsXG4gIH0pO1xuICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gIHJldHVybiB0b3RhbER1cmF0aW9uLmFzSG91cnMoKTtcbn07XG5cbmV4cG9ydCBjb25zdCBnZXRFdmVudERldGFpbHNGb3JNb2RpZmljYXRpb24gPSBhc3luYyAoXG4gIGhhc3VyYUV2ZW50SWQ6IHN0cmluZyAvLyBGb3JtYXQ6IFwiZ29vZ2xlRXZlbnRJZCNjYWxlbmRhcklkXCJcbik6IFByb21pc2U8XG4gIChFdmVudFR5cGUgJiB7IGF0dGVuZGVlcz86IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXSB9KSB8IG51bGxcbj4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnR2V0RXZlbnRXaXRoQXR0ZW5kZWVzRm9yTW9kaWZpY2F0aW9uJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5ICR7b3BlcmF0aW9uTmFtZX0oJGV2ZW50SWQ6IFN0cmluZyEpIHtcbiAgICAgICAgICAgICAgICBFdmVudF9ieV9wayhpZDogJGV2ZW50SWQpIHtcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBzdW1tYXJ5XG4gICAgICAgICAgICAgICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBlbmREYXRlXG4gICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uXG4gICAgICAgICAgICAgICAgICAgIHN0YXR1c1xuICAgICAgICAgICAgICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgICAgICAgICAgICAgdmlzaWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICBjb2xvcklkXG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmluZ0V2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgYWxsRGF5XG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VSdWxlXG4gICAgICAgICAgICAgICAgICAgIGF0dGFjaG1lbnRzXG4gICAgICAgICAgICAgICAgICAgIGxpbmtzXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgICAgICAgICAgdGFza0lkXG4gICAgICAgICAgICAgICAgICAgIHRhc2tUeXBlXG4gICAgICAgICAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICAgICAgICAgIGZvbGxvd1VwRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBpc0ZvbGxvd1VwXG4gICAgICAgICAgICAgICAgICAgIGlzUHJlRXZlbnRcbiAgICAgICAgICAgICAgICAgICAgaXNQb3N0RXZlbnRcbiAgICAgICAgICAgICAgICAgICAgcHJlRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBwb3N0RXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBtb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIGZvckV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgY29uZmVyZW5jZUlkXG4gICAgICAgICAgICAgICAgICAgIG1heEF0dGVuZGVlc1xuICAgICAgICAgICAgICAgICAgICBzZW5kVXBkYXRlc1xuICAgICAgICAgICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0c1xuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbEFsbERheVxuICAgICAgICAgICAgICAgICAgICBodG1sTGlua1xuICAgICAgICAgICAgICAgICAgICBjcmVhdG9yXG4gICAgICAgICAgICAgICAgICAgIG9yZ2FuaXplclxuICAgICAgICAgICAgICAgICAgICBlbmRUaW1lVW5zcGVjaWZpZWRcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyZW5jZVxuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlc09taXR0ZWRcbiAgICAgICAgICAgICAgICAgICAgZXh0ZW5kZWRQcm9wZXJ0aWVzXG4gICAgICAgICAgICAgICAgICAgIGhhbmdvdXRMaW5rXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbk1vZGlmeVxuICAgICAgICAgICAgICAgICAgICBsb2NrZWRcbiAgICAgICAgICAgICAgICAgICAgc291cmNlXG4gICAgICAgICAgICAgICAgICAgIGV2ZW50VHlwZVxuICAgICAgICAgICAgICAgICAgICBwcml2YXRlQ29weVxuICAgICAgICAgICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgICAgICAgICAgICAgaUNhbFVJRFxuXG4gICAgICAgICAgICAgICAgICAgIEF0dGVuZGVlcyB7XG4gICAgICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgICAgICBjb250YWN0SWRcbiAgICAgICAgICAgICAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgICAgICAgICAgICAgIHByaW1hcnlFbWFpbFxuICAgICAgICAgICAgICAgICAgICAgICAgZW1haWxzXG4gICAgICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICAgICAgZXh0ZXJuYWxBdHRlbmRlZVxuICAgICAgICAgICAgICAgICAgICAgICAgaG9zdElkXG4gICAgICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGV2ZW50SWQ6IGhhc3VyYUV2ZW50SWQsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiB7XG4gICAgICBkYXRhOiB7XG4gICAgICAgIEV2ZW50X2J5X3BrOiBFdmVudFR5cGUgJiB7IEF0dGVuZGVlcz86IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXSB9O1xuICAgICAgfTtcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICAgIHJlc3BvbnNlVHlwZTogJ2pzb24nLFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBpZiAoKHJlc3BvbnNlIGFzIGFueSk/LmVycm9ycykge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYEhhc3VyYSBlcnJvciBmZXRjaGluZyBldmVudCAke2hhc3VyYUV2ZW50SWR9IGZvciBtb2RpZmljYXRpb246YCxcbiAgICAgICAgSlNPTi5zdHJpbmdpZnkoKHJlc3BvbnNlIGFzIGFueSkuZXJyb3JzLCBudWxsLCAyKVxuICAgICAgKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGNvbnN0IGV2ZW50RGF0YSA9IHJlc3BvbnNlLmRhdGEuRXZlbnRfYnlfcGs7XG4gICAgaWYgKGV2ZW50RGF0YSkge1xuICAgICAgaWYgKGV2ZW50RGF0YS5BdHRlbmRlZXMpIHtcbiAgICAgICAgZXZlbnREYXRhLmF0dGVuZGVlcyA9IGV2ZW50RGF0YS5BdHRlbmRlZXM7XG4gICAgICAgIGRlbGV0ZSAoZXZlbnREYXRhIGFzIGFueSkuQXR0ZW5kZWVzO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgZXZlbnREYXRhLmF0dGVuZGVlcyA9IFtdO1xuICAgICAgfVxuICAgICAgcmV0dXJuIGV2ZW50RGF0YTtcbiAgICB9XG4gICAgcmV0dXJuIG51bGw7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgIGBFcnJvciBpbiBnZXRFdmVudERldGFpbHNGb3JNb2RpZmljYXRpb24gZm9yIGV2ZW50ICR7aGFzdXJhRXZlbnRJZH06YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxufTtcblxuZXhwb3J0IGZ1bmN0aW9uIGdlbmVyYXRlRXZlbnRQYXJ0c0ZvclJlcGxhbihcbiAgYWxsVXNlckV2ZW50czogRXZlbnRQbHVzVHlwZVtdLCAvLyBBbGwgZXZlbnRzIGZvciBhbGwgcmVsZXZhbnQgdXNlcnNcbiAgZXZlbnRUb1JlcGxhbkhhc3VyYUlkOiBzdHJpbmcsIC8vIGUuZy4sIFwiZ29vZ2xlRXZlbnRJZCNjYWxlbmRhcklkXCJcbiAgcmVwbGFuQ29uc3RyYWludHM6IE5ld0NvbnN0cmFpbnRzLFxuICBob3N0SWQ6IHN0cmluZywgLy8gVHlwaWNhbGx5IG9yaWdpbmFsRXZlbnREZXRhaWxzLnVzZXJJZFxuICBob3N0VGltZXpvbmU6IHN0cmluZyAvLyBUbyByZXNvbHZlIGV2ZW50IHBhcnQgc3RhcnQvZW5kIGZvciBPcHRhUGxhbm5lciBpZiBuZWVkZWQgYnkgZm9ybWF0RXZlbnRUeXBlLi4uXG4pOiBJbml0aWFsRXZlbnRQYXJ0VHlwZVBsdXNbXSB7XG4gIGNvbnN0IGFsbEV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlUGx1c1tdID0gW107XG5cbiAgZm9yIChjb25zdCBldmVudCBvZiBhbGxVc2VyRXZlbnRzKSB7XG4gICAgLy8gRW5zdXJlIHByZWZlcnJlZFRpbWVSYW5nZXMgaXMgYXQgbGVhc3QgYW4gZW1wdHkgYXJyYXkgZm9yIEluaXRpYWxFdmVudFBhcnRUeXBlUGx1c1xuICAgIGNvbnN0IGV2ZW50V2l0aFByZWZzOiBFdmVudFBsdXNUeXBlID0ge1xuICAgICAgLi4uZXZlbnQsXG4gICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzOiBldmVudC5wcmVmZXJyZWRUaW1lUmFuZ2VzIHx8IFtdLFxuICAgIH07XG5cbiAgICBsZXQgcGFydHMgPSBnZW5lcmF0ZUV2ZW50UGFydHNMaXRlKGV2ZW50V2l0aFByZWZzLCBob3N0SWQpOyAvLyBSZXR1cm5zIEluaXRpYWxFdmVudFBhcnRUeXBlW11cblxuICAgIGlmIChldmVudC5pZCA9PT0gZXZlbnRUb1JlcGxhbkhhc3VyYUlkKSB7XG4gICAgICAvLyBUaGlzIGlzIHRoZSBldmVudCBiZWluZyByZXBsYW5uZWRcbiAgICAgIGNvbnN0IG5ld0R1cmF0aW9uID0gcmVwbGFuQ29uc3RyYWludHMubmV3RHVyYXRpb25NaW51dGVzO1xuICAgICAgaWYgKG5ld0R1cmF0aW9uICYmIG5ld0R1cmF0aW9uID4gMCkge1xuICAgICAgICBjb25zdCBvcmlnaW5hbEV2ZW50U3RhcnREYXRlID0gZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooXG4gICAgICAgICAgZXZlbnQudGltZXpvbmUgfHwgaG9zdFRpbWV6b25lLFxuICAgICAgICAgIHRydWVcbiAgICAgICAgKTtcbiAgICAgICAgY29uc3QgbmV3RXZlbnRFbmREYXRlID0gb3JpZ2luYWxFdmVudFN0YXJ0RGF0ZS5hZGQoXG4gICAgICAgICAgbmV3RHVyYXRpb24sXG4gICAgICAgICAgJ21pbnV0ZXMnXG4gICAgICAgICk7XG5cbiAgICAgICAgLy8gQ3JlYXRlIGEgdGVtcG9yYXJ5IGV2ZW50IHdpdGggdGhlIG5ldyBkdXJhdGlvbiB0byBnZW5lcmF0ZSBwYXJ0c1xuICAgICAgICBjb25zdCB0ZW1wRXZlbnRGb3JOZXdEdXJhdGlvbjogRXZlbnRQbHVzVHlwZSA9IHtcbiAgICAgICAgICAuLi5ldmVudFdpdGhQcmVmcyxcbiAgICAgICAgICBlbmREYXRlOiBuZXdFdmVudEVuZERhdGUuZm9ybWF0KCksIC8vIEVuc3VyZSBjb3JyZWN0IGZvcm1hdFxuICAgICAgICB9O1xuICAgICAgICBwYXJ0cyA9IGdlbmVyYXRlRXZlbnRQYXJ0c0xpdGUodGVtcEV2ZW50Rm9yTmV3RHVyYXRpb24sIGhvc3RJZCk7XG4gICAgICB9XG5cbiAgICAgIHBhcnRzID0gcGFydHMubWFwKChwKSA9PiAoe1xuICAgICAgICAuLi5wLFxuICAgICAgICBtb2RpZmlhYmxlOiB0cnVlLFxuICAgICAgICAvLyBBZGQgZW1wdHkgcHJlZmVycmVkVGltZVJhbmdlcyBpZiBub3QgcHJlc2VudCwgdG8gc2F0aXNmeSBJbml0aWFsRXZlbnRQYXJ0VHlwZVBsdXNcbiAgICAgICAgcHJlZmVycmVkVGltZVJhbmdlczpcbiAgICAgICAgICAocCBhcyBJbml0aWFsRXZlbnRQYXJ0VHlwZVBsdXMpLnByZWZlcnJlZFRpbWVSYW5nZXMgfHwgW10sXG4gICAgICB9KSk7XG4gICAgfSBlbHNlIHtcbiAgICAgIC8vIFRoaXMgaXMgbm90IHRoZSBldmVudCBiZWluZyByZXBsYW5uZWQsIHNvIHBpbiBpdFxuICAgICAgcGFydHMgPSBwYXJ0cy5tYXAoKHApID0+IHtcbiAgICAgICAgY29uc3QgaW5pdGlhbFBhcnRQbHVzOiBJbml0aWFsRXZlbnRQYXJ0VHlwZVBsdXMgPSB7XG4gICAgICAgICAgLi4ucCxcbiAgICAgICAgICBtb2RpZmlhYmxlOiBmYWxzZSxcbiAgICAgICAgICAvLyBBZGQgZW1wdHkgcHJlZmVycmVkVGltZVJhbmdlcyBpZiBub3QgcHJlc2VudFxuICAgICAgICAgIHByZWZlcnJlZFRpbWVSYW5nZXM6XG4gICAgICAgICAgICAocCBhcyBJbml0aWFsRXZlbnRQYXJ0VHlwZVBsdXMpLnByZWZlcnJlZFRpbWVSYW5nZXMgfHwgW10sXG4gICAgICAgIH07XG5cbiAgICAgICAgLy8gQXBwbHkgcGlubmluZyBsb2dpYyBzaW1pbGFyIHRvIHNldFByZWZlcnJlZFRpbWVGb3JVbk1vZGlmaWFibGVFdmVudFxuICAgICAgICAvLyBUaGlzIGZ1bmN0aW9uIGV4cGVjdHMgRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZSwgc28gd2UgYWRhcHQgaXRzIGxvZ2ljIGhlcmUgZm9yIEluaXRpYWxFdmVudFBhcnRUeXBlUGx1c1xuICAgICAgICBpZiAoXG4gICAgICAgICAgIWluaXRpYWxQYXJ0UGx1cy5wcmVmZXJyZWREYXlPZldlZWsgJiZcbiAgICAgICAgICAhaW5pdGlhbFBhcnRQbHVzLnByZWZlcnJlZFRpbWVcbiAgICAgICAgKSB7XG4gICAgICAgICAgY29uc3QgcGFydFN0YXJ0RGF0ZSA9IGRheWpzKFxuICAgICAgICAgICAgaW5pdGlhbFBhcnRQbHVzLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSlcbiAgICAgICAgICApLnR6KGluaXRpYWxQYXJ0UGx1cy50aW1lem9uZSB8fCBob3N0VGltZXpvbmUsIHRydWUpO1xuICAgICAgICAgIGluaXRpYWxQYXJ0UGx1cy5wcmVmZXJyZWREYXlPZldlZWsgPSBnZXRJU09EYXkoXG4gICAgICAgICAgICBwYXJ0U3RhcnREYXRlLnRvRGF0ZSgpXG4gICAgICAgICAgKSBhcyBhbnk7IC8vIE1heSBuZWVkIGRheU9mV2Vla0ludFRvU3RyaW5nIGNvbnZlcnNpb24gaWYgdHlwZSBtaXNtYXRjaFxuICAgICAgICAgIGluaXRpYWxQYXJ0UGx1cy5wcmVmZXJyZWRUaW1lID0gcGFydFN0YXJ0RGF0ZS5mb3JtYXQoXG4gICAgICAgICAgICAnSEg6bW06c3MnXG4gICAgICAgICAgKSBhcyBUaW1lO1xuICAgICAgICB9XG4gICAgICAgIHJldHVybiBpbml0aWFsUGFydFBsdXM7XG4gICAgICB9KTtcbiAgICB9XG4gICAgYWxsRXZlbnRQYXJ0cy5wdXNoKC4uLnBhcnRzKTtcbiAgfVxuICByZXR1cm4gYWxsRXZlbnRQYXJ0cztcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdlbmVyYXRlVGltZVNsb3RzRm9yUmVwbGFuKFxuICB1c2VyczogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdLCAvLyBGaW5hbCBsaXN0IG9mIHVzZXJzIGZvciB0aGUgcmVwbGFubmVkIGV2ZW50XG4gIHJlcGxhbkNvbnN0cmFpbnRzOiBOZXdDb25zdHJhaW50cyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIGdsb2JhbERlZmF1bHRXaW5kb3dTdGFydDogc3RyaW5nLCAvLyBGYWxsYmFjayB3aW5kb3cgc3RhcnQgKElTTyBzdHJpbmcpXG4gIGdsb2JhbERlZmF1bHRXaW5kb3dFbmQ6IHN0cmluZywgLy8gRmFsbGJhY2sgd2luZG93IGVuZCAoSVNPIHN0cmluZylcbiAgbWFpbkhvc3RJZDogc3RyaW5nLCAvLyBOZWVkZWQgYnkgZ2VuZXJhdGVUaW1lU2xvdHNMaXRlRm9ySW50ZXJuYWxBdHRlbmRlZVxuICB1c2VyUHJlZmVyZW5jZXNDYWNoZTogTWFwPHN0cmluZywgVXNlclByZWZlcmVuY2VUeXBlPiAvLyBDYWNoZSB0byBhdm9pZCByZS1mZXRjaGluZ1xuKTogUHJvbWlzZTxUaW1lU2xvdFR5cGVbXT4ge1xuICBjb25zdCBhbGxUaW1lU2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG5cbiAgY29uc3QgZWZmZWN0aXZlV2luZG93U3RhcnRVVEMgPVxuICAgIHJlcGxhbkNvbnN0cmFpbnRzLm5ld1RpbWVXaW5kb3dTdGFydFVUQyB8fCBnbG9iYWxEZWZhdWx0V2luZG93U3RhcnQ7XG4gIGNvbnN0IGVmZmVjdGl2ZVdpbmRvd0VuZFVUQyA9XG4gICAgcmVwbGFuQ29uc3RyYWludHMubmV3VGltZVdpbmRvd0VuZFVUQyB8fCBnbG9iYWxEZWZhdWx0V2luZG93RW5kO1xuXG4gIC8vIENvbnZlcnQgZWZmZWN0aXZlIFVUQyB3aW5kb3cgdG8gaG9zdFRpbWV6b25lIGZvciBnZW5lcmF0aW5nIHNsb3RzIGxvY2FsbHkgaWYgbmVlZGVkLFxuICAvLyBvciBlbnN1cmUgZG93bnN0cmVhbSBmdW5jdGlvbnMgY29ycmVjdGx5IGhhbmRsZSBVVEMgb3IgY29udmVydCB0byBob3N0VGltZXpvbmUuXG4gIC8vIEZvciBnZW5lcmF0ZVRpbWVTbG90c0xpdGVGb3JJbnRlcm5hbEF0dGVuZGVlLCBpdCBleHBlY3RzIGhvc3RTdGFydERhdGUgaW4gaG9zdFRpbWV6b25lLlxuICBjb25zdCBlZmZlY3RpdmVXaW5kb3dTdGFydEluSG9zdFR6ID0gZGF5anNcbiAgICAudXRjKGVmZmVjdGl2ZVdpbmRvd1N0YXJ0VVRDKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmZvcm1hdCgpO1xuICBjb25zdCBlZmZlY3RpdmVXaW5kb3dFbmRJbkhvc3RUeiA9IGRheWpzXG4gICAgLnV0YyhlZmZlY3RpdmVXaW5kb3dFbmRVVEMpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAuZm9ybWF0KCk7XG5cbiAgY29uc3QgZGlmZkRheXMgPSBkYXlqcyhlZmZlY3RpdmVXaW5kb3dFbmRJbkhvc3RUeikuZGlmZihcbiAgICBkYXlqcyhlZmZlY3RpdmVXaW5kb3dTdGFydEluSG9zdFR6KSxcbiAgICAnZGF5J1xuICApO1xuICBjb25zdCBzdGFydERhdGVzRm9yRWFjaERheUluV2luZG93OiBzdHJpbmdbXSA9IFtdO1xuICBmb3IgKGxldCBpID0gMDsgaSA8PSBkaWZmRGF5czsgaSsrKSB7XG4gICAgc3RhcnREYXRlc0ZvckVhY2hEYXlJbldpbmRvdy5wdXNoKFxuICAgICAgZGF5anMoZWZmZWN0aXZlV2luZG93U3RhcnRJbkhvc3RUeikuYWRkKGksICdkYXknKS5mb3JtYXQoKVxuICAgICk7XG4gIH1cblxuICBmb3IgKGNvbnN0IHVzZXIgb2YgdXNlcnMpIHtcbiAgICBsZXQgdXNlclByZWZzID0gdXNlclByZWZlcmVuY2VzQ2FjaGUuZ2V0KHVzZXIudXNlcklkKTtcbiAgICBpZiAoIXVzZXJQcmVmcykge1xuICAgICAgdXNlclByZWZzID0gYXdhaXQgZ2V0VXNlclByZWZlcmVuY2VzKHVzZXIudXNlcklkKTtcbiAgICAgIGlmICh1c2VyUHJlZnMpIHtcbiAgICAgICAgdXNlclByZWZlcmVuY2VzQ2FjaGUuc2V0KHVzZXIudXNlcklkLCB1c2VyUHJlZnMpO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgLy8gSGFuZGxlIGNhc2Ugd2hlcmUgdXNlciBwcmVmZXJlbmNlcyBtaWdodCBub3QgYmUgZm91bmQgZm9yIGEgdXNlclxuICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgYFByZWZlcmVuY2VzIG5vdCBmb3VuZCBmb3IgdXNlciAke3VzZXIudXNlcklkfSwgc2tpcHBpbmcgdGltZXNsb3QgZ2VuZXJhdGlvbiBmb3IgdGhlbS5gXG4gICAgICAgICk7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfVxuICAgIH1cblxuICAgIC8vIEFzc3VtaW5nIGdlbmVyYXRlVGltZVNsb3RzTGl0ZUZvckludGVybmFsQXR0ZW5kZWUgaXMgdGhlIHByaW1hcnkgb25lLlxuICAgIC8vIElmIGV4dGVybmFsIHVzZXJzIGhhdmUgYSBkaWZmZXJlbnQgc2xvdCBnZW5lcmF0aW9uIG1lY2hhbmlzbSwgdGhhdCB3b3VsZCBuZWVkIHRvIGJlIGNhbGxlZCBoZXJlLlxuICAgIC8vIFRoZSBnZW5lcmF0ZVRpbWVTbG90c0xpdGVGb3JJbnRlcm5hbEF0dGVuZGVlIGV4cGVjdHMgaG9zdFN0YXJ0RGF0ZSBmb3IgZWFjaCBkYXkuXG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCBzdGFydERhdGVzRm9yRWFjaERheUluV2luZG93Lmxlbmd0aDsgaSsrKSB7XG4gICAgICBjb25zdCBkYXlUb0dlbmVyYXRlU2xvdHMgPSBzdGFydERhdGVzRm9yRWFjaERheUluV2luZG93W2ldO1xuICAgICAgY29uc3QgaXNGaXJzdERheUxvb3AgPSBpID09PSAwO1xuXG4gICAgICAvLyBFbnN1cmUgdGhlIGRhdGUgYmVpbmcgcGFzc2VkIHRvIGdlbmVyYXRlVGltZVNsb3RzTGl0ZUZvckludGVybmFsQXR0ZW5kZWUgaXMgY29ycmVjdGx5IGZvcm1hdHRlZCBhbmQgaW4gaG9zdFRpbWV6b25lLlxuICAgICAgLy8gVGhlIGxvb3AgYWxyZWFkeSBnZW5lcmF0ZXMgZGF0ZXMgaW4gaG9zdFRpbWV6b25lIGJhc2VkIG9uIGVmZmVjdGl2ZVdpbmRvd1N0YXJ0SW5Ib3N0VHpcbiAgICAgIGNvbnN0IHVzZXJTcGVjaWZpY1Nsb3RzID0gZ2VuZXJhdGVUaW1lU2xvdHNMaXRlRm9ySW50ZXJuYWxBdHRlbmRlZShcbiAgICAgICAgZGF5VG9HZW5lcmF0ZVNsb3RzLCAvLyBUaGlzIGlzIGFscmVhZHkgYSBkYXRlIHN0cmluZyBpbiBob3N0VGltZXpvbmVcbiAgICAgICAgbWFpbkhvc3RJZCwgLy8gT3IgdXNlci5ob3N0SWQgaWYgYXBwcm9wcmlhdGUsIG1haW5Ib3N0SWQgc2VlbXMgbW9yZSBhbGlnbmVkIHdpdGggT3B0YVBsYW5uZXIncyBtb2RlbFxuICAgICAgICB1c2VyUHJlZnMsXG4gICAgICAgIGhvc3RUaW1lem9uZSwgLy8gSG9zdCdzIG92ZXJhbGwgdGltZXpvbmVcbiAgICAgICAgdXNlci50aW1lem9uZSB8fCBob3N0VGltZXpvbmUsIC8vIEF0dGVuZGVlJ3Mgc3BlY2lmaWMgdGltZXpvbmVcbiAgICAgICAgaXNGaXJzdERheUxvb3BcbiAgICAgICk7XG4gICAgICBhbGxUaW1lU2xvdHMucHVzaCguLi51c2VyU3BlY2lmaWNTbG90cyk7XG4gICAgfVxuICB9XG5cbiAgcmV0dXJuIF8udW5pcVdpdGgoYWxsVGltZVNsb3RzLCBfLmlzRXF1YWwpO1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gb3JjaGVzdHJhdGVSZXBsYW5PcHRhUGxhbm5lcklucHV0KFxuICB1c2VySWQ6IHN0cmluZywgLy8gVXNlciBpbml0aWF0aW5nIHRoZSByZXBsYW4gKHVzdWFsbHkgdGhlIGhvc3QpXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICBvcmlnaW5hbEV2ZW50RGV0YWlsczogRXZlbnRUeXBlICYge1xuICAgIGF0dGVuZGVlcz86IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXTtcbiAgICBtZWV0aW5nSWQ/OiBzdHJpbmc7XG4gIH0sXG4gIG5ld0NvbnN0cmFpbnRzOiBOZXdDb25zdHJhaW50cyxcbiAgYWxsVXNlcnNGcm9tT3JpZ2luYWxFdmVudEFuZEFkZGVkOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10sIC8vIENvbWJpbmVkIGxpc3Qgb2Ygb3JpZ2luYWwgYW5kIG5ld2x5IGFkZGVkIGF0dGVuZGVlc1xuICBhbGxFeGlzdGluZ0V2ZW50c0ZvclVzZXJzOiBFdmVudFBsdXNUeXBlW10gLy8gUHJlLWZldGNoZWQgZXZlbnRzIGZvciBBTEwgcmVsZXZhbnQgdXNlcnMgaW4gYSBicm9hZCB3aW5kb3dcbiAgLy8gY2xpZW50OiBhbnksIC8vIEFwb2xsb0NsaWVudCwgaWYgbmVlZGVkIC0gY3VycmVudGx5IHVzaW5nIGdsb2JhbCBnb3QgZm9yIEhhc3VyYVxuKTogUHJvbWlzZTxQbGFubmVyUmVxdWVzdEJvZHlUeXBlIHwgbnVsbD4ge1xuICB0cnkge1xuICAgIGNvbnN0IHNpbmdsZXRvbklkID0gdXVpZCgpO1xuICAgIGNvbnN0IGV2ZW50VG9SZXBsYW5IYXN1cmFJZCA9IG9yaWdpbmFsRXZlbnREZXRhaWxzLmlkOyAvLyBnb29nbGVFdmVudElkI2NhbGVuZGFySWRcblxuICAgIC8vIDEuIEdlbmVyYXRlIEV2ZW50IFBhcnRzXG4gICAgLy8gSG9zdCBJRCBmb3IgZXZlbnQgcGFydHMgaXMgdHlwaWNhbGx5IHRoZSB1c2VyIElEIGZyb20gdGhlIG9yaWdpbmFsIGV2ZW50XG4gICAgY29uc3QgZXZlbnRQYXJ0cyA9IGdlbmVyYXRlRXZlbnRQYXJ0c0ZvclJlcGxhbihcbiAgICAgIGFsbEV4aXN0aW5nRXZlbnRzRm9yVXNlcnMsXG4gICAgICBldmVudFRvUmVwbGFuSGFzdXJhSWQsXG4gICAgICBuZXdDb25zdHJhaW50cyxcbiAgICAgIG9yaWdpbmFsRXZlbnREZXRhaWxzLnVzZXJJZCxcbiAgICAgIGhvc3RUaW1lem9uZVxuICAgICk7XG5cbiAgICBpZiAoIWV2ZW50UGFydHMgfHwgZXZlbnRQYXJ0cy5sZW5ndGggPT09IDApIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoJ05vIGV2ZW50IHBhcnRzIGdlbmVyYXRlZCBmb3IgcmVwbGFuLiBBYm9ydGluZy4nKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIC8vIDIuIEdlbmVyYXRlIFRpbWUgU2xvdHNcbiAgICAvLyBVc2UgYSBjYWNoZSBmb3IgdXNlciBwcmVmZXJlbmNlcyB3aXRoaW4gdGhpcyBmdW5jdGlvbidzIHNjb3BlXG4gICAgY29uc3QgdXNlclByZWZlcmVuY2VzQ2FjaGUgPSBuZXcgTWFwPHN0cmluZywgVXNlclByZWZlcmVuY2VUeXBlPigpO1xuXG4gICAgLy8gRGVmaW5lIGdsb2JhbCBmYWxsYmFjayB3aW5kb3cgKGUuZy4sIG5leHQgNyBkYXlzIGZyb20gb3JpZ2luYWwgZXZlbnQgc3RhcnQgaWYgbm8gbmV3IHdpbmRvdyBzcGVjaWZpZWQpXG4gICAgLy8gVGhlc2Ugc2hvdWxkIGJlIElTTyBkYXRldGltZSBzdHJpbmdzXG4gICAgY29uc3Qgb3JpZ2luYWxFdmVudFN0YXJ0RGF5anMgPSBkYXlqcyhcbiAgICAgIG9yaWdpbmFsRXZlbnREZXRhaWxzLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSlcbiAgICApLnR6KG9yaWdpbmFsRXZlbnREZXRhaWxzLnRpbWV6b25lIHx8IGhvc3RUaW1lem9uZSwgdHJ1ZSk7XG4gICAgY29uc3QgZ2xvYmFsRGVmYXVsdFdpbmRvd1N0YXJ0ID1cbiAgICAgIG5ld0NvbnN0cmFpbnRzLm5ld1RpbWVXaW5kb3dTdGFydFVUQyB8fFxuICAgICAgb3JpZ2luYWxFdmVudFN0YXJ0RGF5anMudG9JU09TdHJpbmcoKTtcbiAgICBjb25zdCBnbG9iYWxEZWZhdWx0V2luZG93RW5kID1cbiAgICAgIG5ld0NvbnN0cmFpbnRzLm5ld1RpbWVXaW5kb3dFbmRVVEMgfHxcbiAgICAgIG9yaWdpbmFsRXZlbnRTdGFydERheWpzLmFkZCg3LCAnZGF5cycpLnRvSVNPU3RyaW5nKCk7XG5cbiAgICBjb25zdCB0aW1lU2xvdHMgPSBhd2FpdCBnZW5lcmF0ZVRpbWVTbG90c0ZvclJlcGxhbihcbiAgICAgIGFsbFVzZXJzRnJvbU9yaWdpbmFsRXZlbnRBbmRBZGRlZCxcbiAgICAgIG5ld0NvbnN0cmFpbnRzLFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgZ2xvYmFsRGVmYXVsdFdpbmRvd1N0YXJ0LFxuICAgICAgZ2xvYmFsRGVmYXVsdFdpbmRvd0VuZCxcbiAgICAgIG9yaWdpbmFsRXZlbnREZXRhaWxzLnVzZXJJZCwgLy8gbWFpbkhvc3RJZCBmb3IgdGltZXNsb3QgZ2VuZXJhdGlvbiBjb250ZXh0XG4gICAgICB1c2VyUHJlZmVyZW5jZXNDYWNoZVxuICAgICk7XG5cbiAgICBpZiAoIXRpbWVTbG90cyB8fCB0aW1lU2xvdHMubGVuZ3RoID09PSAwKSB7XG4gICAgICBjb25zb2xlLmVycm9yKCdObyB0aW1lIHNsb3RzIGdlbmVyYXRlZCBmb3IgcmVwbGFuLiBBYm9ydGluZy4nKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIC8vIDMuIENvbnN0cnVjdCBVc2VyIExpc3QgKFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlKVxuICAgIGNvbnN0IHVzZXJMaXN0Rm9yUGxhbm5lcjogVXNlclBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSA9IFtdO1xuICAgIGZvciAoY29uc3QgdXNlciBvZiBhbGxVc2Vyc0Zyb21PcmlnaW5hbEV2ZW50QW5kQWRkZWQpIHtcbiAgICAgIGxldCB1c2VyUHJlZnMgPSB1c2VyUHJlZmVyZW5jZXNDYWNoZS5nZXQodXNlci51c2VySWQpO1xuICAgICAgaWYgKCF1c2VyUHJlZnMpIHtcbiAgICAgICAgdXNlclByZWZzID0gYXdhaXQgZ2V0VXNlclByZWZlcmVuY2VzKHVzZXIudXNlcklkKTtcbiAgICAgICAgaWYgKHVzZXJQcmVmcykge1xuICAgICAgICAgIHVzZXJQcmVmZXJlbmNlc0NhY2hlLnNldCh1c2VyLnVzZXJJZCwgdXNlclByZWZzKTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgICBgUHJlZmVyZW5jZXMgbm90IGZvdW5kIGZvciB1c2VyICR7dXNlci51c2VySWR9IHdoaWxlIGJ1aWxkaW5nIHVzZXJMaXN0Rm9yUGxhbm5lci4gVXNpbmcgZGVmYXVsdHMuYFxuICAgICAgICAgICk7XG4gICAgICAgICAgLy8gUHJvdmlkZSBkZWZhdWx0L21pbmltYWwgVXNlclByZWZlcmVuY2VUeXBlIGlmIG5vbmUgZm91bmRcbiAgICAgICAgICB1c2VyUHJlZnMgPSB7XG4gICAgICAgICAgICBpZDogdXVpZCgpLCAvLyB0ZW1wIGlkXG4gICAgICAgICAgICB1c2VySWQ6IHVzZXIudXNlcklkLFxuICAgICAgICAgICAgbWF4V29ya0xvYWRQZXJjZW50OiAxMDAsIC8vIERlZmF1bHQgdmFsdWVzXG4gICAgICAgICAgICBiYWNrVG9CYWNrTWVldGluZ3M6IGZhbHNlLFxuICAgICAgICAgICAgbWF4TnVtYmVyT2ZNZWV0aW5nczogOTksXG4gICAgICAgICAgICBtaW5OdW1iZXJPZkJyZWFrczogMCxcbiAgICAgICAgICAgIHN0YXJ0VGltZXM6IFtdLCAvLyBEZWZhdWx0IGVtcHR5IHN0YXJ0L2VuZCB0aW1lc1xuICAgICAgICAgICAgZW5kVGltZXM6IFtdLFxuICAgICAgICAgICAgYnJlYWtMZW5ndGg6IDMwLFxuICAgICAgICAgICAgLy8gQWRkIG90aGVyIG1hbmRhdG9yeSBmaWVsZHMgZnJvbSBVc2VyUHJlZmVyZW5jZVR5cGUgd2l0aCBkZWZhdWx0c1xuICAgICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgICAgfSBhcyBVc2VyUHJlZmVyZW5jZVR5cGU7XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgY29uc3Qgd29ya1RpbWVzID0gdXNlci5leHRlcm5hbEF0dGVuZGVlXG4gICAgICAgID8gZ2VuZXJhdGVXb3JrVGltZXNGb3JFeHRlcm5hbEF0dGVuZGVlKFxuICAgICAgICAgICAgb3JpZ2luYWxFdmVudERldGFpbHMudXNlcklkLCAvLyBob3N0SWQgY29udGV4dFxuICAgICAgICAgICAgdXNlci51c2VySWQsXG4gICAgICAgICAgICBhbGxFeGlzdGluZ0V2ZW50c0ZvclVzZXJzLmZpbHRlcigoZSkgPT4gZS51c2VySWQgPT09IHVzZXIudXNlcklkKSwgLy8gUGFzcyBvbmx5IHRoaXMgdXNlcidzIGV2ZW50c1xuICAgICAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICAgICAgdXNlci50aW1lem9uZSB8fCBob3N0VGltZXpvbmVcbiAgICAgICAgICApXG4gICAgICAgIDogZ2VuZXJhdGVXb3JrVGltZXNGb3JJbnRlcm5hbEF0dGVuZGVlKFxuICAgICAgICAgICAgb3JpZ2luYWxFdmVudERldGFpbHMudXNlcklkLCAvLyBob3N0SWQgY29udGV4dFxuICAgICAgICAgICAgdXNlci51c2VySWQsXG4gICAgICAgICAgICB1c2VyUHJlZnMsXG4gICAgICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgICAgICB1c2VyLnRpbWV6b25lIHx8IGhvc3RUaW1lem9uZVxuICAgICAgICAgICk7XG5cbiAgICAgIHVzZXJMaXN0Rm9yUGxhbm5lci5wdXNoKFxuICAgICAgICB1c2VyLmV4dGVybmFsQXR0ZW5kZWVcbiAgICAgICAgICA/IGdlbmVyYXRlVXNlclBsYW5uZXJSZXF1ZXN0Qm9keUZvckV4dGVybmFsQXR0ZW5kZWUoXG4gICAgICAgICAgICAgIHVzZXIudXNlcklkLFxuICAgICAgICAgICAgICB3b3JrVGltZXMsXG4gICAgICAgICAgICAgIG9yaWdpbmFsRXZlbnREZXRhaWxzLnVzZXJJZFxuICAgICAgICAgICAgKVxuICAgICAgICAgIDogZ2VuZXJhdGVVc2VyUGxhbm5lclJlcXVlc3RCb2R5KFxuICAgICAgICAgICAgICB1c2VyUHJlZnMsXG4gICAgICAgICAgICAgIHVzZXIudXNlcklkLFxuICAgICAgICAgICAgICB3b3JrVGltZXMsXG4gICAgICAgICAgICAgIG9yaWdpbmFsRXZlbnREZXRhaWxzLnVzZXJJZFxuICAgICAgICAgICAgKVxuICAgICAgKTtcbiAgICB9XG5cbiAgICBjb25zdCB1bmlxdWVVc2VyTGlzdEZvclBsYW5uZXIgPSBfLnVuaXFCeSh1c2VyTGlzdEZvclBsYW5uZXIsICdpZCcpO1xuXG4gICAgLy8gNC4gQXNzZW1ibGUgUGxhbm5lclJlcXVlc3RCb2R5VHlwZVxuICAgIGNvbnN0IGZpbGVLZXkgPSBgJHtvcmlnaW5hbEV2ZW50RGV0YWlscy51c2VySWR9LyR7c2luZ2xldG9uSWR9X1JFUExBTl8ke29yaWdpbmFsRXZlbnREZXRhaWxzLmV2ZW50SWR9Lmpzb25gO1xuXG4gICAgY29uc3QgcGxhbm5lclJlcXVlc3RCb2R5OiBQbGFubmVyUmVxdWVzdEJvZHlUeXBlID0ge1xuICAgICAgc2luZ2xldG9uSWQsXG4gICAgICBob3N0SWQ6IG9yaWdpbmFsRXZlbnREZXRhaWxzLnVzZXJJZCxcbiAgICAgIHRpbWVzbG90czogXy51bmlxV2l0aCh0aW1lU2xvdHMsIF8uaXNFcXVhbCksXG4gICAgICB1c2VyTGlzdDogdW5pcXVlVXNlckxpc3RGb3JQbGFubmVyLFxuICAgICAgLy8gRXZlbnQgcGFydHMgbmVlZCB0byBiZSBjb3JyZWN0bHkgZm9ybWF0dGVkIGFzIEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVcbiAgICAgIC8vIFRoZSBnZW5lcmF0ZUV2ZW50UGFydHNGb3JSZXBsYW4gcmV0dXJucyBJbml0aWFsRXZlbnRQYXJ0VHlwZVBsdXNbXVxuICAgICAgLy8gV2UgbmVlZCB0byBtYXAgdGhlc2UgdG8gRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZSwgc2ltaWxhciB0byBob3cgcHJvY2Vzc0V2ZW50c0Zvck9wdGFQbGFubmVyIGRvZXMuXG4gICAgICAvLyBUaGlzIHJlcXVpcmVzIHVzZXJQcmVmZXJlbmNlcyBmb3IgZWFjaCBldmVudCBwYXJ0J3MgdXNlci5cbiAgICAgIGV2ZW50UGFydHM6IGV2ZW50UGFydHNcbiAgICAgICAgLm1hcCgoZXApID0+IHtcbiAgICAgICAgICBjb25zdCBwYXJ0VXNlciA9IGFsbFVzZXJzRnJvbU9yaWdpbmFsRXZlbnRBbmRBZGRlZC5maW5kKFxuICAgICAgICAgICAgKHUpID0+IHUudXNlcklkID09PSBlcC51c2VySWRcbiAgICAgICAgICApO1xuICAgICAgICAgIGxldCBwYXJ0VXNlclByZWZzID0gdXNlclByZWZlcmVuY2VzQ2FjaGUuZ2V0KGVwLnVzZXJJZCk7XG4gICAgICAgICAgaWYgKCFwYXJ0VXNlclByZWZzKSB7XG4gICAgICAgICAgICAvLyBUaGlzIHNob3VsZCBpZGVhbGx5IG5vdCBoYXBwZW4gaWYgYWxsIHVzZXJzIGluIGV2ZW50UGFydHMgYXJlIGluIGFsbFVzZXJzRnJvbU9yaWdpbmFsRXZlbnRBbmRBZGRlZFxuICAgICAgICAgICAgLy8gYW5kIHRoZWlyIHByZWZzIHdlcmUgZmV0Y2hlZCBmb3IgdXNlckxpc3QuIEFkZGluZyBhIGZhbGxiYWNrLlxuICAgICAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICAgICBgUHJlZnMgbm90IGluIGNhY2hlIGZvciB1c2VyICR7ZXAudXNlcklkfSBkdXJpbmcgZXZlbnQgcGFydCBmb3JtYXR0aW5nLiBVc2luZyBkZWZhdWx0cy5gXG4gICAgICAgICAgICApO1xuICAgICAgICAgICAgcGFydFVzZXJQcmVmcyA9IHtcbiAgICAgICAgICAgICAgLyogLi4uIGRlZmF1bHQgVXNlclByZWZlcmVuY2VUeXBlIC4uLiAqL1xuICAgICAgICAgICAgfSBhcyBVc2VyUHJlZmVyZW5jZVR5cGU7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgY29uc3QgcGFydFdvcmtUaW1lcyA9IHBhcnRVc2VyPy5leHRlcm5hbEF0dGVuZGVlXG4gICAgICAgICAgICA/IGdlbmVyYXRlV29ya1RpbWVzRm9yRXh0ZXJuYWxBdHRlbmRlZShcbiAgICAgICAgICAgICAgICBvcmlnaW5hbEV2ZW50RGV0YWlscy51c2VySWQsXG4gICAgICAgICAgICAgICAgZXAudXNlcklkLFxuICAgICAgICAgICAgICAgIGFsbEV4aXN0aW5nRXZlbnRzRm9yVXNlcnMuZmlsdGVyKChlKSA9PiBlLnVzZXJJZCA9PT0gZXAudXNlcklkKSxcbiAgICAgICAgICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgICAgICAgICAgcGFydFVzZXI/LnRpbWV6b25lIHx8IGhvc3RUaW1lem9uZVxuICAgICAgICAgICAgICApXG4gICAgICAgICAgICA6IGdlbmVyYXRlV29ya1RpbWVzRm9ySW50ZXJuYWxBdHRlbmRlZShcbiAgICAgICAgICAgICAgICBvcmlnaW5hbEV2ZW50RGV0YWlscy51c2VySWQsXG4gICAgICAgICAgICAgICAgZXAudXNlcklkLFxuICAgICAgICAgICAgICAgIHBhcnRVc2VyUHJlZnMsXG4gICAgICAgICAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICAgICAgICAgIHBhcnRVc2VyPy50aW1lem9uZSB8fCBob3N0VGltZXpvbmVcbiAgICAgICAgICAgICAgKTtcblxuICAgICAgICAgIHJldHVybiBwYXJ0VXNlcj8uZXh0ZXJuYWxBdHRlbmRlZVxuICAgICAgICAgICAgPyBmb3JtYXRFdmVudFR5cGVUb1BsYW5uZXJFdmVudEZvckV4dGVybmFsQXR0ZW5kZWUoXG4gICAgICAgICAgICAgICAgZXAsXG4gICAgICAgICAgICAgICAgcGFydFdvcmtUaW1lcyxcbiAgICAgICAgICAgICAgICBhbGxFeGlzdGluZ0V2ZW50c0ZvclVzZXJzLmZpbHRlcigoZSkgPT4gZS51c2VySWQgPT09IGVwLnVzZXJJZCksXG4gICAgICAgICAgICAgICAgaG9zdFRpbWV6b25lXG4gICAgICAgICAgICAgIClcbiAgICAgICAgICAgIDogZm9ybWF0RXZlbnRUeXBlVG9QbGFubmVyRXZlbnQoXG4gICAgICAgICAgICAgICAgZXAsXG4gICAgICAgICAgICAgICAgcGFydFVzZXJQcmVmcyxcbiAgICAgICAgICAgICAgICBwYXJ0V29ya1RpbWVzLFxuICAgICAgICAgICAgICAgIGhvc3RUaW1lem9uZVxuICAgICAgICAgICAgICApO1xuICAgICAgICB9KVxuICAgICAgICAuZmlsdGVyKChlcCkgPT4gZXAgIT09IG51bGwpLCAvLyBGaWx0ZXIgb3V0IG51bGxzIGlmIGFsbERheSBldmVudHMgd2VyZSBza2lwcGVkXG4gICAgICBmaWxlS2V5LFxuICAgICAgZGVsYXk6IG9wdGFwbGFubmVyRHVyYXRpb24sIC8vIGZyb20gY29uc3RhbnRzXG4gICAgICBjYWxsQmFja1VybDogb25PcHRhUGxhbkNhbGVuZGFyQWRtaW5DYWxsQmFja1VybCwgLy8gZnJvbSBjb25zdGFudHNcbiAgICB9O1xuXG4gICAgLy8gRmlsdGVyIG91dCBhbnkgbnVsbCBldmVudCBwYXJ0cyB0aGF0IG1pZ2h0IHJlc3VsdCBmcm9tIGFsbERheSBldmVudHMgZXRjLlxuICAgIHBsYW5uZXJSZXF1ZXN0Qm9keS5ldmVudFBhcnRzID0gcGxhbm5lclJlcXVlc3RCb2R5LmV2ZW50UGFydHMuZmlsdGVyKFxuICAgICAgKGVwKSA9PiBlcCAhPSBudWxsXG4gICAgKTtcblxuICAgIGlmIChcbiAgICAgICFwbGFubmVyUmVxdWVzdEJvZHkuZXZlbnRQYXJ0cyB8fFxuICAgICAgcGxhbm5lclJlcXVlc3RCb2R5LmV2ZW50UGFydHMubGVuZ3RoID09PSAwXG4gICAgKSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAnTm8gdmFsaWQgZXZlbnQgcGFydHMgdG8gc2VuZCB0byBPcHRhUGxhbm5lciBhZnRlciBmb3JtYXR0aW5nLiBBYm9ydGluZy4nXG4gICAgICApO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuXG4gICAgLy8gNS4gUzMgVXBsb2FkXG4gICAgY29uc3QgczNVcGxvYWRQYXJhbXMgPSB7XG4gICAgICBCb2R5OiBKU09OLnN0cmluZ2lmeSh7XG4gICAgICAgIC8vIFN0b3JpbmcgdGhlIGlucHV0IHRvIE9wdGFQbGFubmVyIGZvciBkZWJ1Z2dpbmcvaGlzdG9yeVxuICAgICAgICBzaW5nbGV0b25JZDogcGxhbm5lclJlcXVlc3RCb2R5LnNpbmdsZXRvbklkLFxuICAgICAgICBob3N0SWQ6IHBsYW5uZXJSZXF1ZXN0Qm9keS5ob3N0SWQsXG4gICAgICAgIGV2ZW50UGFydHM6IHBsYW5uZXJSZXF1ZXN0Qm9keS5ldmVudFBhcnRzLCAvLyBUaGVzZSBhcmUgbm93IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVcbiAgICAgICAgYWxsRXZlbnRzOiBhbGxFeGlzdGluZ0V2ZW50c0ZvclVzZXJzLCAvLyBGb3IgY29udGV4dFxuICAgICAgICAvLyBJbmNsdWRlIGFueSBvdGhlciByZWxldmFudCBkYXRhIGZvciBkZWJ1Z2dpbmcgdGhlIHJlcGxhbiByZXF1ZXN0XG4gICAgICAgIG9yaWdpbmFsRXZlbnREZXRhaWxzLFxuICAgICAgICBuZXdDb25zdHJhaW50cyxcbiAgICAgICAgZmluYWxVc2VyTGlzdEZvclBsYW5uZXI6IHVuaXF1ZVVzZXJMaXN0Rm9yUGxhbm5lcixcbiAgICAgICAgZmluYWxUaW1lU2xvdHM6IHRpbWVTbG90cyxcbiAgICAgICAgaXNSZXBsYW46IHRydWUsXG4gICAgICAgIG9yaWdpbmFsR29vZ2xlRXZlbnRJZDogb3JpZ2luYWxFdmVudERldGFpbHMuZXZlbnRJZCwgLy8gQXNzdW1pbmcgZXZlbnRJZCBpcyBnb29nbGVFdmVudElkIGhlcmVcbiAgICAgICAgb3JpZ2luYWxDYWxlbmRhcklkOiBvcmlnaW5hbEV2ZW50RGV0YWlscy5jYWxlbmRhcklkLFxuICAgICAgfSksXG4gICAgICBCdWNrZXQ6IGJ1Y2tldE5hbWUsIC8vIGZyb20gY29uc3RhbnRzXG4gICAgICBLZXk6IGZpbGVLZXksXG4gICAgICBDb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgIH07XG4gICAgY29uc3QgczNDb21tYW5kID0gbmV3IFB1dE9iamVjdENvbW1hbmQoczNVcGxvYWRQYXJhbXMpO1xuICAgIGF3YWl0IHMzQ2xpZW50LnNlbmQoczNDb21tYW5kKTtcbiAgICBjb25zb2xlLmxvZyhgU3VjY2Vzc2Z1bGx5IHVwbG9hZGVkIHJlcGxhbiBpbnB1dCB0byBTMzogJHtmaWxlS2V5fWApO1xuXG4gICAgLy8gNi4gQ2FsbCBvcHRhUGxhbldlZWtseVxuICAgIGF3YWl0IG9wdGFQbGFuV2Vla2x5KFxuICAgICAgcGxhbm5lclJlcXVlc3RCb2R5LnRpbWVzbG90cyxcbiAgICAgIHBsYW5uZXJSZXF1ZXN0Qm9keS51c2VyTGlzdCxcbiAgICAgIHBsYW5uZXJSZXF1ZXN0Qm9keS5ldmVudFBhcnRzLFxuICAgICAgcGxhbm5lclJlcXVlc3RCb2R5LnNpbmdsZXRvbklkLFxuICAgICAgcGxhbm5lclJlcXVlc3RCb2R5Lmhvc3RJZCxcbiAgICAgIHBsYW5uZXJSZXF1ZXN0Qm9keS5maWxlS2V5LFxuICAgICAgcGxhbm5lclJlcXVlc3RCb2R5LmRlbGF5LFxuICAgICAgcGxhbm5lclJlcXVlc3RCb2R5LmNhbGxCYWNrVXJsXG4gICAgKTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBPcHRhUGxhbm5lciByZXBsYW4gdGFzayBpbml0aWF0ZWQgZm9yIHNpbmdsZXRvbklkOiAke3NpbmdsZXRvbklkfWBcbiAgICApO1xuXG4gICAgcmV0dXJuIHBsYW5uZXJSZXF1ZXN0Qm9keTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgYEVycm9yIGluIG9yY2hlc3RyYXRlUmVwbGFuT3B0YVBsYW5uZXJJbnB1dCBmb3IgZXZlbnQgJHtvcmlnaW5hbEV2ZW50RGV0YWlscy5pZH06YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxufVxuXG4vLyBOZXcgZnVuY3Rpb24gdG8gbGlzdCBleHRlcm5hbCBhdHRlbmRlZSBwcmVmZXJlbmNlc1xuZXhwb3J0IGNvbnN0IGxpc3RFeHRlcm5hbEF0dGVuZGVlUHJlZmVyZW5jZXMgPSBhc3luYyAoXG4gIC8vIGNsaWVudDogYW55LCAvLyBOb3QgbmVlZGVkIGFzIGdvdCBpcyB1c2VkIGRpcmVjdGx5IHdpdGggZ2xvYmFsIGNvbmZpZ1xuICBtZWV0aW5nQXNzaXN0SWQ6IHN0cmluZyxcbiAgbWVldGluZ0Fzc2lzdEF0dGVuZGVlSWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxGZXRjaGVkRXh0ZXJuYWxQcmVmZXJlbmNlW10+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0xpc3RFeHRlcm5hbEF0dGVuZGVlUHJlZmVyZW5jZXMnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgTGlzdEV4dGVybmFsQXR0ZW5kZWVQcmVmZXJlbmNlcygkbWVldGluZ0Fzc2lzdElkOiB1dWlkISwgJG1lZXRpbmdBc3Npc3RBdHRlbmRlZUlkOiB1dWlkISkge1xuICAgICAgICAgICAgICAgIE1lZXRpbmdfQXNzaXN0X0V4dGVybmFsX0F0dGVuZGVlX1ByZWZlcmVuY2UoXG4gICAgICAgICAgICAgICAgICAgIHdoZXJlOiB7XG4gICAgICAgICAgICAgICAgICAgICAgICBtZWV0aW5nX2Fzc2lzdF9pZDoge19lcTogJG1lZXRpbmdBc3Npc3RJZH0sXG4gICAgICAgICAgICAgICAgICAgICAgICBtZWV0aW5nX2Fzc2lzdF9hdHRlbmRlZV9pZDoge19lcTogJG1lZXRpbmdBc3Npc3RBdHRlbmRlZUlkfVxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgICAgICBvcmRlcl9ieToge3ByZWZlcnJlZF9zdGFydF9kYXRldGltZTogYXNjfVxuICAgICAgICAgICAgICAgICkge1xuICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRfc3RhcnRfZGF0ZXRpbWVcbiAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkX2VuZF9kYXRldGltZVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIG1lZXRpbmdBc3Npc3RJZCxcbiAgICAgIG1lZXRpbmdBc3Npc3RBdHRlbmRlZUlkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgTWVldGluZ19Bc3Npc3RfRXh0ZXJuYWxfQXR0ZW5kZWVfUHJlZmVyZW5jZTogRmV0Y2hlZEV4dGVybmFsUHJlZmVyZW5jZVtdO1xuICAgICAgfTtcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLCAvLyBPciBhcHByb3ByaWF0ZSByb2xlXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgICAgcmVzcG9uc2VUeXBlOiAnanNvbicsIC8vIEVuc3VyZSBnb3QgcGFyc2VzIHRoZSByZXNwb25zZSBhcyBKU09OXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIC8vIENoZWNrIGZvciBHcmFwaFFMIGVycm9ycyBpbiB0aGUgcmVzcG9uc2UgYm9keVxuICAgIGlmICgocmVzIGFzIGFueSk/LmVycm9ycykge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ0hhc3VyYSBlcnJvcnMgd2hpbGUgZmV0Y2hpbmcgZXh0ZXJuYWwgcHJlZmVyZW5jZXM6JyxcbiAgICAgICAgSlNPTi5zdHJpbmdpZnkoKHJlcyBhcyBhbnkpLmVycm9ycywgbnVsbCwgMilcbiAgICAgICk7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgIGBIYXN1cmEgcmVxdWVzdCBmYWlsZWQ6ICR7KHJlcyBhcyBhbnkpLmVycm9yc1swXS5tZXNzYWdlfWBcbiAgICAgICk7XG4gICAgfVxuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uTWVldGluZ19Bc3Npc3RfRXh0ZXJuYWxfQXR0ZW5kZWVfUHJlZmVyZW5jZSB8fCBbXTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIC8vIExvZyB0aGUgZXJyb3IgY2F1Z2h0IGJ5IHRoZSB0cnktY2F0Y2ggYmxvY2tcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgJ0Vycm9yIGZldGNoaW5nIGV4dGVybmFsIGF0dGVuZGVlIHByZWZlcmVuY2VzIChjYXRjaCBibG9jayk6JyxcbiAgICAgIGVcbiAgICApO1xuICAgIHJldHVybiBbXTsgLy8gUmV0dXJuIGVtcHR5IGFycmF5IG9uIGVycm9yXG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZUJyZWFrcyA9IChcbiAgdXNlclByZWZlcmVuY2VzOiBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIG51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZTogbnVtYmVyLFxuICBldmVudE1pcnJvcjogRXZlbnRQbHVzVHlwZSxcbiAgZ2xvYmFsQ2FsZW5kYXJJZD86IHN0cmluZ1xuKTogRXZlbnRQbHVzVHlwZVtdID0+IHtcbiAgY29uc3QgYnJlYWtzID0gW107XG4gIGlmICghdXNlclByZWZlcmVuY2VzPy5icmVha0xlbmd0aCkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJ25vIHVzZXIgcHJlZmVyZW5jZXMgYnJlYWtMZW5ndGggcHJvdmlkZWQgaW5zaWRlIGdlbmVyYXRlQnJlYWtzJ1xuICAgICk7XG4gICAgcmV0dXJuIGJyZWFrcztcbiAgfVxuXG4gIGlmICghbnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICAnbm8gbnVtYmVyIG9mIGJyZWFrcyB0byBnZW5lcmF0ZSBwcm92aWRlZCBpbnNpZGUgZ2VuZXJhdGVCcmVha3MnXG4gICAgKTtcbiAgICByZXR1cm4gYnJlYWtzO1xuICB9XG5cbiAgaWYgKCFldmVudE1pcnJvcikge1xuICAgIGNvbnNvbGUubG9nKCdubyBldmVudCBtaXJyb3IgcHJvdmlkZWQgaW5zaWRlIGdlbmVyYXRlQnJlYWtzJyk7XG4gICAgcmV0dXJuIGJyZWFrcztcbiAgfVxuICBjb25zb2xlLmxvZyhcbiAgICBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUsXG4gICAgJyBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUgaW5zaWRlIGdlbmVyYXRlQnJlYWtzJ1xuICApO1xuICBjb25zdCBicmVha0xlbmd0aCA9XG4gICAgdXNlclByZWZlcmVuY2VzLmJyZWFrTGVuZ3RoIDw9IDE1ID8gMTUgOiB1c2VyUHJlZmVyZW5jZXMuYnJlYWtMZW5ndGg7XG4gIGZvciAobGV0IGkgPSAwOyBpIDwgbnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlOyBpKyspIHtcbiAgICBjb25zdCBldmVudElkID0gdXVpZCgpO1xuICAgIGNvbnN0IGJyZWFrRXZlbnQ6IEV2ZW50UGx1c1R5cGUgPSB7XG4gICAgICBpZDogYCR7ZXZlbnRJZH0jJHtnbG9iYWxDYWxlbmRhcklkIHx8IGV2ZW50TWlycm9yLmNhbGVuZGFySWR9YCxcbiAgICAgIHVzZXJJZDogdXNlclByZWZlcmVuY2VzLnVzZXJJZCxcbiAgICAgIHRpdGxlOiAnQnJlYWsnLFxuICAgICAgc3RhcnREYXRlOiBkYXlqcyhldmVudE1pcnJvci5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooZXZlbnRNaXJyb3IudGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIGVuZERhdGU6IGRheWpzKGV2ZW50TWlycm9yLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihldmVudE1pcnJvci50aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmFkZChicmVha0xlbmd0aCwgJ21pbnV0ZScpXG4gICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIGFsbERheTogZmFsc2UsXG4gICAgICBub3RlczogJ0JyZWFrJyxcbiAgICAgIHRpbWV6b25lOiBldmVudE1pcnJvci50aW1lem9uZSxcbiAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgcHJpb3JpdHk6IDEsXG4gICAgICBpc0ZvbGxvd1VwOiBmYWxzZSxcbiAgICAgIGlzUHJlRXZlbnQ6IGZhbHNlLFxuICAgICAgbW9kaWZpYWJsZTogdHJ1ZSxcbiAgICAgIGFueW9uZUNhbkFkZFNlbGY6IGZhbHNlLFxuICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiBmYWxzZSxcbiAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOiBmYWxzZSxcbiAgICAgIG9yaWdpbmFsU3RhcnREYXRlOiB1bmRlZmluZWQsXG4gICAgICBvcmlnaW5hbEFsbERheTogZmFsc2UsXG4gICAgICBjYWxlbmRhcklkOiBnbG9iYWxDYWxlbmRhcklkIHx8IGV2ZW50TWlycm9yLmNhbGVuZGFySWQsXG4gICAgICBiYWNrZ3JvdW5kQ29sb3I6IHVzZXJQcmVmZXJlbmNlcy5icmVha0NvbG9yIHx8ICcjRjdFQkY3JyxcbiAgICAgIGlzQnJlYWs6IHRydWUsXG4gICAgICBkdXJhdGlvbjogYnJlYWtMZW5ndGgsXG4gICAgICB1c2VyTW9kaWZpZWREdXJhdGlvbjogdHJ1ZSxcbiAgICAgIHVzZXJNb2RpZmllZENvbG9yOiB0cnVlLFxuICAgICAgaXNQb3N0RXZlbnQ6IGZhbHNlLFxuICAgICAgbWV0aG9kOiAnY3JlYXRlJyxcbiAgICAgIGV2ZW50SWQsXG4gICAgfTtcbiAgICBicmVha3MucHVzaChicmVha0V2ZW50KTtcbiAgfVxuXG4gIHJldHVybiBicmVha3M7XG59O1xuXG5leHBvcnQgY29uc3Qgc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50c0ZvckRheSA9IChcbiAgd29ya2luZ0hvdXJzOiBudW1iZXIsXG4gIHVzZXJQcmVmZXJlbmNlczogVXNlclByZWZlcmVuY2VUeXBlLFxuICBhbGxFdmVudHM6IEV2ZW50UGx1c1R5cGVbXVxuKSA9PiB7XG4gIGlmICghdXNlclByZWZlcmVuY2VzPy5icmVha0xlbmd0aCkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJ25vIHVzZXIgcHJlZmVyZW5jZXMgYnJlYWtMZW5ndGggcHJvdmlkZWQgaW5zaWRlIHNob3VsZEdlbmVyYXRlQnJlYWtFdmVudHMnXG4gICAgKTtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICBpZiAoIShhbGxFdmVudHM/Lmxlbmd0aCA+IDApKSB7XG4gICAgY29uc29sZS5sb2coJ25vIGFsbEV2ZW50cyBwcmVzZW50IGluc2lkZSBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF5Jyk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgY29uc3QgYnJlYWtFdmVudHMgPSBhbGxFdmVudHMuZmlsdGVyKChldmVudCkgPT4gZXZlbnQuaXNCcmVhayk7XG4gIGNvbnN0IG51bWJlck9mQnJlYWtzUGVyRGF5ID0gdXNlclByZWZlcmVuY2VzLm1pbk51bWJlck9mQnJlYWtzO1xuXG4gIGNvbnN0IGJyZWFrSG91cnNGcm9tTWluQnJlYWtzID1cbiAgICAodXNlclByZWZlcmVuY2VzLmJyZWFrTGVuZ3RoIC8gNjApICogbnVtYmVyT2ZCcmVha3NQZXJEYXk7XG4gIGNvbnN0IGhvdXJzTXVzdEJlQnJlYWsgPVxuICAgIHdvcmtpbmdIb3VycyAqICgxIC0gdXNlclByZWZlcmVuY2VzLm1heFdvcmtMb2FkUGVyY2VudCAvIDEwMCk7XG5cbiAgbGV0IGJyZWFrSG91cnNBdmFpbGFibGUgPSAwO1xuXG4gIGlmIChicmVha0hvdXJzRnJvbU1pbkJyZWFrcyA+IGhvdXJzTXVzdEJlQnJlYWspIHtcbiAgICBicmVha0hvdXJzQXZhaWxhYmxlID0gYnJlYWtIb3Vyc0Zyb21NaW5CcmVha3M7XG4gIH0gZWxzZSB7XG4gICAgYnJlYWtIb3Vyc0F2YWlsYWJsZSA9IGhvdXJzTXVzdEJlQnJlYWs7XG4gIH1cblxuICBsZXQgYnJlYWtIb3Vyc1VzZWQgPSAwO1xuICBmb3IgKGNvbnN0IGJyZWFrRXZlbnQgb2YgYnJlYWtFdmVudHMpIHtcbiAgICBjb25zdCBkdXJhdGlvbiA9IGRheWpzXG4gICAgICAuZHVyYXRpb24oXG4gICAgICAgIGRheWpzKFxuICAgICAgICAgIGRheWpzKGJyZWFrRXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpXG4gICAgICAgICkuZGlmZihcbiAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpXG4gICAgICAgIClcbiAgICAgIClcbiAgICAgIC5hc0hvdXJzKCk7XG4gICAgYnJlYWtIb3Vyc1VzZWQgKz0gZHVyYXRpb247XG4gIH1cblxuICBpZiAoYnJlYWtIb3Vyc1VzZWQgPj0gYnJlYWtIb3Vyc0F2YWlsYWJsZSkge1xuICAgIGNvbnNvbGUubG9nKCdicmVha0hvdXJzVXNlZCA+PSBicmVha0hvdXJzQXZhaWxhYmxlJyk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgaWYgKCEoYWxsRXZlbnRzPy5sZW5ndGggPiAwKSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJ3RoZXJlIGFyZSBubyBldmVudHMgZm9yIHRoaXMgZGF0ZSBpbnNpZGUgc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50cydcbiAgICApO1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuXG4gIHJldHVybiB0cnVlO1xufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlQnJlYWtFdmVudHNGb3JEYXkgPSBhc3luYyAoXG4gIHVzZXJQcmVmZXJlbmNlczogVXNlclByZWZlcmVuY2VUeXBlLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgaG9zdFN0YXJ0RGF0ZTogc3RyaW5nLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgZ2xvYmFsQ2FsZW5kYXJJZD86IHN0cmluZyxcbiAgaXNGaXJzdERheT86IGJvb2xlYW5cbikgPT4ge1xuICB0cnkge1xuICAgIGlmICghdXNlclByZWZlcmVuY2VzPy5icmVha0xlbmd0aCkge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICdubyB1c2VyIHByZWZlcmVuY2VzIGJyZWFrTGVuZ3RoIHByb3ZpZGVkIGluc2lkZSBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzJ1xuICAgICAgKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGlmICghdXNlcklkKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gdXNlcklkIHByb3ZpZGVkIGluc2lkZSBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzJyk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG5cbiAgICBpZiAoIWhvc3RTdGFydERhdGUpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyBzdGFydERhdGUgcHJvdmlkZWQgaW5zaWRlIHNob3VsZEdlbmVyYXRlQnJlYWtFdmVudHMnKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGlmICghaG9zdFRpbWV6b25lKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gdGltZXpvbmUgcHJvdmlkZWQgaW5zaWRlIHNob3VsZEdlbmVyYXRlQnJlYWtFdmVudHMnKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGlmIChpc0ZpcnN0RGF5KSB7XG4gICAgICBjb25zdCBlbmRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5lbmRUaW1lcztcbiAgICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkudG9EYXRlKClcbiAgICAgICk7XG5cbiAgICAgIGxldCBzdGFydEhvdXJCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmhvdXIoKTtcbiAgICAgIGxldCBzdGFydE1pbnV0ZUJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAubWludXRlKCk7XG4gICAgICBjb25zdCBlbmRIb3VyID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgICAgIGNvbnN0IGVuZE1pbnV0ZSA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG5cbiAgICAgIGNvbnN0IHN0YXJ0VGltZXMgPSB1c2VyUHJlZmVyZW5jZXMuc3RhcnRUaW1lcztcbiAgICAgIGNvbnN0IHdvcmtTdGFydEhvdXIgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gICAgICBjb25zdCB3b3JrU3RhcnRNaW51dGUgPSBzdGFydFRpbWVzLmZpbmQoXG4gICAgICAgIChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50XG4gICAgICApLm1pbnV0ZXM7XG5cbiAgICAgIGlmIChcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLmlzQWZ0ZXIoXG4gICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLmhvdXIoZW5kSG91cikubWludXRlKGVuZE1pbnV0ZSlcbiAgICAgICAgKVxuICAgICAgKSB7XG4gICAgICAgIHJldHVybiBudWxsO1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmlzQmVmb3JlKFxuICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXIpXG4gICAgICAgICAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlKVxuICAgICAgICAgIClcbiAgICAgICkge1xuICAgICAgICBzdGFydEhvdXJCeUhvc3QgPSB3b3JrU3RhcnRIb3VyO1xuICAgICAgICBzdGFydE1pbnV0ZUJ5SG9zdCA9IHdvcmtTdGFydE1pbnV0ZTtcbiAgICAgIH1cblxuICAgICAgY29uc3Qgd29ya2luZ0hvdXJzID0gY29udmVydFRvVG90YWxXb3JraW5nSG91cnNGb3JJbnRlcm5hbEF0dGVuZGVlKFxuICAgICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICAgIGhvc3RTdGFydERhdGUsXG4gICAgICAgIGhvc3RUaW1lem9uZVxuICAgICAgKTtcbiAgICAgIGNvbnNvbGUubG9nKHdvcmtpbmdIb3VycywgJyB3b3JraW5nSG91cnMnKTtcbiAgICAgIGNvbnN0IGFsbEV2ZW50cyA9IGF3YWl0IGxpc3RFdmVudHNGb3JEYXRlKFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGUpXG4gICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICBob3N0VGltZXpvbmVcbiAgICAgICk7XG5cbiAgICAgIGlmICghKGFsbEV2ZW50cz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgJ25vIGFsbEV2ZW50cyBwcmVzZW50IGluc2lkZSBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF5J1xuICAgICAgICApO1xuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH1cblxuICAgICAgY29uc3Qgc2hvdWxkR2VuZXJhdGVCcmVha3MgPSBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF5KFxuICAgICAgICB3b3JraW5nSG91cnMsXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgYWxsRXZlbnRzXG4gICAgICApO1xuXG4gICAgICBjb25zb2xlLmxvZyhzaG91bGRHZW5lcmF0ZUJyZWFrcywgJyBzaG91bGRHZW5lcmF0ZUJyZWFrcycpO1xuXG4gICAgICBpZiAoIXNob3VsZEdlbmVyYXRlQnJlYWtzKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKCdzaG91bGQgbm90IGdlbmVyYXRlIGJyZWFrcycpO1xuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH1cblxuICAgICAgbGV0IGhvdXJzVXNlZCA9IDA7XG5cbiAgICAgIGlmIChhbGxFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgZm9yIChjb25zdCBhbGxFdmVudCBvZiBhbGxFdmVudHMpIHtcbiAgICAgICAgICBjb25zdCBkdXJhdGlvbiA9IGRheWpzXG4gICAgICAgICAgICAuZHVyYXRpb24oXG4gICAgICAgICAgICAgIGRheWpzKGFsbEV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLmRpZmYoXG4gICAgICAgICAgICAgICAgICBkYXlqcyhhbGxFdmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgKVxuICAgICAgICAgICAgKVxuICAgICAgICAgICAgLmFzSG91cnMoKTtcbiAgICAgICAgICBob3Vyc1VzZWQgKz0gZHVyYXRpb247XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgY29uc29sZS5sb2coaG91cnNVc2VkLCAnIGhvdXJzVXNlZCcpO1xuXG4gICAgICBsZXQgaG91cnNBdmFpbGFibGUgPSB3b3JraW5nSG91cnMgLSBob3Vyc1VzZWQ7XG5cbiAgICAgIGNvbnNvbGUubG9nKGhvdXJzQXZhaWxhYmxlLCAnIGhvdXJzQXZhaWxhYmxlJyk7XG5cbiAgICAgIGNvbnN0IGhvdXJzTXVzdEJlQnJlYWsgPVxuICAgICAgICB3b3JraW5nSG91cnMgKiAoMSAtIHVzZXJQcmVmZXJlbmNlcy5tYXhXb3JrTG9hZFBlcmNlbnQgLyAxMDApO1xuXG4gICAgICBjb25zb2xlLmxvZyhob3Vyc011c3RCZUJyZWFrLCAnIGhvdXJzTXVzdEJlQnJlYWsnKTtcblxuICAgICAgaWYgKGhvdXJzQXZhaWxhYmxlIDwgaG91cnNNdXN0QmVCcmVhaykge1xuICAgICAgICBob3Vyc0F2YWlsYWJsZSA9IGhvdXJzTXVzdEJlQnJlYWs7XG4gICAgICB9XG4gICAgICBpZiAoaG91cnNBdmFpbGFibGUgPD0gMCkge1xuICAgICAgICBjb25zb2xlLmxvZyhob3Vyc0F2YWlsYWJsZSwgJyBubyBob3VycyBhdmFpbGFibGUnKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IG9sZEJyZWFrRXZlbnRzID0gYWxsRXZlbnRzXG4gICAgICAgIC5maWx0ZXIoKGV2ZW50KSA9PiBldmVudC5pc0JyZWFrKVxuICAgICAgICAuZmlsdGVyKChlKSA9PlxuICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5pc1NhbWUoXG4gICAgICAgICAgICAgIGRheWpzKGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKSxcbiAgICAgICAgICAgICAgJ2RheSdcbiAgICAgICAgICAgIClcbiAgICAgICAgKTtcblxuICAgICAgY29uc3QgYnJlYWtFdmVudHMgPSBvbGRCcmVha0V2ZW50cztcblxuICAgICAgY29uc3QgbnVtYmVyT2ZCcmVha3NQZXJEYXkgPSB1c2VyUHJlZmVyZW5jZXMubWluTnVtYmVyT2ZCcmVha3M7XG5cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBudW1iZXJPZkJyZWFrc1BlckRheSxcbiAgICAgICAgJyBudW1iZXJPZkJyZWFrc1BlckRheSBha2EgdXNlclByZWZlcmVuY2VzLm1pbk51bWJlck9mQnJlYWtzJ1xuICAgICAgKTtcbiAgICAgIGNvbnNvbGUubG9nKHVzZXJQcmVmZXJlbmNlcy5icmVha0xlbmd0aCwgJyB1c2VyUHJlZmVyZW5jZXMuYnJlYWtMZW5ndGgnKTtcblxuICAgICAgY29uc3QgYnJlYWtIb3Vyc1RvR2VuZXJhdGVGb3JNaW5CcmVha3MgPVxuICAgICAgICAodXNlclByZWZlcmVuY2VzLmJyZWFrTGVuZ3RoIC8gNjApICogbnVtYmVyT2ZCcmVha3NQZXJEYXk7XG5cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBicmVha0hvdXJzVG9HZW5lcmF0ZUZvck1pbkJyZWFrcyxcbiAgICAgICAgJyBicmVha0hvdXJzVG9HZW5lcmF0ZUZvck1pbkJyZWFrcydcbiAgICAgICk7XG5cbiAgICAgIGxldCBicmVha0hvdXJzVG9HZW5lcmF0ZSA9IDA7XG5cbiAgICAgIGlmIChicmVha0hvdXJzVG9HZW5lcmF0ZUZvck1pbkJyZWFrcyA+IGhvdXJzQXZhaWxhYmxlKSB7XG4gICAgICAgIGJyZWFrSG91cnNUb0dlbmVyYXRlID0gaG91cnNBdmFpbGFibGU7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBicmVha0hvdXJzVG9HZW5lcmF0ZSA9IGJyZWFrSG91cnNUb0dlbmVyYXRlRm9yTWluQnJlYWtzO1xuICAgICAgfVxuXG4gICAgICBjb25zb2xlLmxvZyhicmVha0hvdXJzVG9HZW5lcmF0ZSwgJyBicmVha0hvdXJzVG9HZW5lcmF0ZScpO1xuXG4gICAgICBsZXQgYnJlYWtIb3Vyc1VzZWQgPSAwO1xuXG4gICAgICBpZiAoYnJlYWtFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgZm9yIChjb25zdCBicmVha0V2ZW50IG9mIGJyZWFrRXZlbnRzKSB7XG4gICAgICAgICAgY29uc3QgZHVyYXRpb24gPSBkYXlqc1xuICAgICAgICAgICAgLmR1cmF0aW9uKFxuICAgICAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLmRpZmYoXG4gICAgICAgICAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KFxuICAgICAgICAgICAgICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgICAgICAgICAgICAgIHRydWVcbiAgICAgICAgICAgICAgICAgIClcbiAgICAgICAgICAgICAgICApXG4gICAgICAgICAgICApXG4gICAgICAgICAgICAuYXNIb3VycygpO1xuICAgICAgICAgIGJyZWFrSG91cnNVc2VkICs9IGR1cmF0aW9uO1xuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IGFjdHVhbEJyZWFrSG91cnNUb0dlbmVyYXRlID0gYnJlYWtIb3Vyc1RvR2VuZXJhdGUgLSBicmVha0hvdXJzVXNlZDtcblxuICAgICAgaWYgKGFjdHVhbEJyZWFrSG91cnNUb0dlbmVyYXRlID4gaG91cnNBdmFpbGFibGUpIHtcbiAgICAgICAgY29uc29sZS5sb2coJyBubyBob3VycyBhdmFpbGFibGUgdG8gZ2VuZXJhdGUgYnJlYWsnKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9XG4gICAgICBjb25zb2xlLmxvZyhhY3R1YWxCcmVha0hvdXJzVG9HZW5lcmF0ZSwgJyBhY3R1YWxCcmVha0hvdXJzVG9HZW5lcmF0ZScpO1xuICAgICAgY29uc29sZS5sb2coYnJlYWtIb3Vyc1VzZWQsICcgYnJlYWtIb3Vyc1VzZWQnKTtcbiAgICAgIGNvbnNvbGUubG9nKGJyZWFrSG91cnNUb0dlbmVyYXRlRm9yTWluQnJlYWtzLCAnIGJyZWFrSG91cnNBdmFpbGFibGUnKTtcbiAgICAgIGNvbnN0IGJyZWFrTGVuZ3RoQXNIb3VycyA9IHVzZXJQcmVmZXJlbmNlcy5icmVha0xlbmd0aCAvIDYwO1xuICAgICAgY29uc29sZS5sb2coYnJlYWtMZW5ndGhBc0hvdXJzLCAnIGJyZWFrTGVuZ3RoQXNIb3VycycpO1xuICAgICAgY29uc3QgbnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlID0gTWF0aC5mbG9vcihcbiAgICAgICAgYWN0dWFsQnJlYWtIb3Vyc1RvR2VuZXJhdGUgLyBicmVha0xlbmd0aEFzSG91cnNcbiAgICAgICk7XG4gICAgICBjb25zb2xlLmxvZyhudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUsICcgbnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlJyk7XG5cbiAgICAgIGlmIChudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUgPCAxKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKCdzaG91bGQgbm90IGdlbmVyYXRlIGJyZWFrcycpO1xuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH1cblxuICAgICAgaWYgKGJyZWFrSG91cnNUb0dlbmVyYXRlID4gNikge1xuICAgICAgICBjb25zb2xlLmxvZygnYnJlYWtIb3Vyc1RvR2VuZXJhdGUgaXMgPiA2Jyk7XG4gICAgICAgIHJldHVybiBudWxsO1xuICAgICAgfVxuXG4gICAgICBjb25zdCBldmVudE1pcnJvciA9IGFsbEV2ZW50cy5maW5kKChldmVudCkgPT4gIWV2ZW50LmlzQnJlYWspO1xuXG4gICAgICBjb25zdCBuZXdFdmVudHMgPSBnZW5lcmF0ZUJyZWFrcyhcbiAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUsXG4gICAgICAgIGV2ZW50TWlycm9yLFxuICAgICAgICBnbG9iYWxDYWxlbmRhcklkXG4gICAgICApO1xuXG4gICAgICByZXR1cm4gbmV3RXZlbnRzO1xuICAgIH1cblxuICAgIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2VzLmVuZFRpbWVzO1xuICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICAgKTtcblxuICAgIGNvbnN0IGVuZEhvdXIgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgIGNvbnN0IGVuZE1pbnV0ZSA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG5cbiAgICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2VzLnN0YXJ0VGltZXM7XG4gICAgY29uc3Qgc3RhcnRIb3VyID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuXG4gICAgY29uc3Qgd29ya2luZ0hvdXJzID0gY29udmVydFRvVG90YWxXb3JraW5nSG91cnNGb3JJbnRlcm5hbEF0dGVuZGVlKFxuICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgaG9zdFN0YXJ0RGF0ZSxcbiAgICAgIGhvc3RUaW1lem9uZVxuICAgICk7XG4gICAgY29uc3QgYWxsRXZlbnRzID0gYXdhaXQgbGlzdEV2ZW50c0ZvckRhdGUoXG4gICAgICB1c2VySWQsXG4gICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmhvdXIoc3RhcnRIb3VyKVxuICAgICAgICAubWludXRlKHN0YXJ0TWludXRlKVxuICAgICAgICAuZm9ybWF0KCksXG4gICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmhvdXIoZW5kSG91cilcbiAgICAgICAgLm1pbnV0ZShlbmRNaW51dGUpXG4gICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIGhvc3RUaW1lem9uZVxuICAgICk7XG4gICAgaWYgKCEoYWxsRXZlbnRzPy5sZW5ndGggPiAwKSkge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICdubyBhbGxFdmVudHMgcHJlc2VudCBpbnNpZGUgc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50c0ZvckRheSdcbiAgICAgICk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG4gICAgY29uc3Qgc2hvdWxkR2VuZXJhdGVCcmVha3MgPSBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF5KFxuICAgICAgd29ya2luZ0hvdXJzLFxuICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgYWxsRXZlbnRzXG4gICAgKTtcbiAgICBpZiAoIXNob3VsZEdlbmVyYXRlQnJlYWtzKSB7XG4gICAgICBjb25zb2xlLmxvZygnc2hvdWxkIG5vdCBnZW5lcmF0ZSBicmVha3MnKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGxldCBob3Vyc1VzZWQgPSAwO1xuXG4gICAgaWYgKGFsbEV2ZW50cz8ubGVuZ3RoID4gMCkge1xuICAgICAgZm9yIChjb25zdCBhbGxFdmVudCBvZiBhbGxFdmVudHMpIHtcbiAgICAgICAgY29uc3QgZHVyYXRpb24gPSBkYXlqc1xuICAgICAgICAgIC5kdXJhdGlvbihcbiAgICAgICAgICAgIGRheWpzKGFsbEV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAuZGlmZihcbiAgICAgICAgICAgICAgICBkYXlqcyhhbGxFdmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIClcbiAgICAgICAgICApXG4gICAgICAgICAgLmFzSG91cnMoKTtcbiAgICAgICAgaG91cnNVc2VkICs9IGR1cmF0aW9uO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKGhvdXJzVXNlZCwgJyBob3Vyc1VzZWQnKTtcblxuICAgIGxldCBob3Vyc0F2YWlsYWJsZSA9IHdvcmtpbmdIb3VycyAtIGhvdXJzVXNlZDtcbiAgICBjb25zdCBob3Vyc011c3RCZUJyZWFrID1cbiAgICAgIHdvcmtpbmdIb3VycyAqICgxIC0gdXNlclByZWZlcmVuY2VzLm1heFdvcmtMb2FkUGVyY2VudCAvIDEwMCk7XG5cbiAgICBjb25zb2xlLmxvZyhob3Vyc011c3RCZUJyZWFrLCAnIGhvdXJzTXVzdEJlQnJlYWsnKTtcbiAgICBjb25zb2xlLmxvZyhob3Vyc0F2YWlsYWJsZSwgJyBob3Vyc0F2YWlsYWJsZScpO1xuXG4gICAgaWYgKGhvdXJzQXZhaWxhYmxlIDwgaG91cnNNdXN0QmVCcmVhaykge1xuICAgICAgaG91cnNBdmFpbGFibGUgPSBob3Vyc011c3RCZUJyZWFrO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKGhvdXJzQXZhaWxhYmxlLCAnIGhvdXJzQXZhaWxhYmxlJyk7XG5cbiAgICBpZiAoaG91cnNBdmFpbGFibGUgPD0gMCkge1xuICAgICAgY29uc29sZS5sb2coaG91cnNBdmFpbGFibGUsICcgbm8gaG91cnMgYXZhaWxhYmxlJyk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG5cbiAgICBjb25zdCBvbGRCcmVha0V2ZW50cyA9IGFsbEV2ZW50c1xuICAgICAgLmZpbHRlcigoZXZlbnQpID0+IGV2ZW50LmlzQnJlYWspXG4gICAgICAuZmlsdGVyKChlKSA9PlxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5pc1NhbWUoZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLCAnZGF5JylcbiAgICAgICk7XG5cbiAgICBjb25zdCBicmVha0V2ZW50cyA9IG9sZEJyZWFrRXZlbnRzO1xuXG4gICAgY29uc3QgbnVtYmVyT2ZCcmVha3NQZXJEYXkgPSB1c2VyUHJlZmVyZW5jZXMubWluTnVtYmVyT2ZCcmVha3M7XG4gICAgY29uc29sZS5sb2cobnVtYmVyT2ZCcmVha3NQZXJEYXksICcgbnVtYmVyT2ZCcmVha3NQZXJEYXknKTtcbiAgICBjb25zdCBicmVha0hvdXJzVG9HZW5lcmF0ZUZvck1pbkJyZWFrcyA9XG4gICAgICAodXNlclByZWZlcmVuY2VzLmJyZWFrTGVuZ3RoIC8gNjApICogbnVtYmVyT2ZCcmVha3NQZXJEYXk7XG4gICAgbGV0IGJyZWFrSG91cnNUb0dlbmVyYXRlID0gMDtcblxuICAgIGlmIChicmVha0hvdXJzVG9HZW5lcmF0ZUZvck1pbkJyZWFrcyA+IGhvdXJzQXZhaWxhYmxlKSB7XG4gICAgICBicmVha0hvdXJzVG9HZW5lcmF0ZSA9IGhvdXJzQXZhaWxhYmxlO1xuICAgIH0gZWxzZSB7XG4gICAgICBicmVha0hvdXJzVG9HZW5lcmF0ZSA9IGJyZWFrSG91cnNUb0dlbmVyYXRlRm9yTWluQnJlYWtzO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKGJyZWFrSG91cnNUb0dlbmVyYXRlLCAnIGJyZWFrSG91cnNUb0dlbmVyYXRlJyk7XG5cbiAgICBsZXQgYnJlYWtIb3Vyc1VzZWQgPSAwO1xuXG4gICAgaWYgKGJyZWFrRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICBmb3IgKGNvbnN0IGJyZWFrRXZlbnQgb2YgYnJlYWtFdmVudHMpIHtcbiAgICAgICAgY29uc3QgZHVyYXRpb24gPSBkYXlqc1xuICAgICAgICAgIC5kdXJhdGlvbihcbiAgICAgICAgICAgIGRheWpzKGJyZWFrRXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC5kaWZmKFxuICAgICAgICAgICAgICAgIGRheWpzKGJyZWFrRXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICApXG4gICAgICAgICAgKVxuICAgICAgICAgIC5hc0hvdXJzKCk7XG4gICAgICAgIGJyZWFrSG91cnNVc2VkICs9IGR1cmF0aW9uO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IGFjdHVhbEJyZWFrSG91cnNUb0dlbmVyYXRlID0gYnJlYWtIb3Vyc1RvR2VuZXJhdGUgLSBicmVha0hvdXJzVXNlZDtcblxuICAgIGlmIChhY3R1YWxCcmVha0hvdXJzVG9HZW5lcmF0ZSA+IGhvdXJzQXZhaWxhYmxlKSB7XG4gICAgICBjb25zb2xlLmxvZygnIG5vIGhvdXJzIGF2YWlsYWJsZSB0byBnZW5lcmF0ZSBicmVhaycpO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2coYnJlYWtIb3Vyc1VzZWQsICcgYnJlYWtIb3Vyc1VzZWQnKTtcbiAgICBjb25zb2xlLmxvZyhicmVha0hvdXJzVG9HZW5lcmF0ZSwgJyBicmVha0hvdXJzQXZhaWxhYmxlJyk7XG4gICAgY29uc3QgYnJlYWtMZW5ndGhBc0hvdXJzID0gdXNlclByZWZlcmVuY2VzLmJyZWFrTGVuZ3RoIC8gNjA7XG4gICAgY29uc29sZS5sb2coYnJlYWtMZW5ndGhBc0hvdXJzLCAnIGJyZWFrTGVuZ3RoQXNIb3VycycpO1xuICAgIGNvbnN0IG51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZSA9IE1hdGguZmxvb3IoXG4gICAgICBhY3R1YWxCcmVha0hvdXJzVG9HZW5lcmF0ZSAvIGJyZWFrTGVuZ3RoQXNIb3Vyc1xuICAgICk7XG4gICAgY29uc29sZS5sb2cobnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlLCAnIG51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZScpO1xuXG4gICAgaWYgKG51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZSA8IDEpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdzaG91bGQgbm90IGdlbmVyYXRlIGJyZWFrcycpO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuXG4gICAgaWYgKGJyZWFrSG91cnNUb0dlbmVyYXRlID4gNikge1xuICAgICAgY29uc29sZS5sb2coJ2JyZWFrSG91cnNUb0dlbmVyYXRlIGlzID4gNicpO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuXG4gICAgY29uc3QgZXZlbnRNaXJyb3IgPSBhbGxFdmVudHMuZmluZCgoZXZlbnQpID0+ICFldmVudC5pc0JyZWFrKTtcblxuICAgIGNvbnN0IG5ld0V2ZW50cyA9IGdlbmVyYXRlQnJlYWtzKFxuICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgbnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlLFxuICAgICAgZXZlbnRNaXJyb3IsXG4gICAgICBnbG9iYWxDYWxlbmRhcklkXG4gICAgKTtcblxuICAgIHJldHVybiBuZXdFdmVudHM7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZW5lcmF0ZSBicmVha3MgZm9yIGRheScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVCcmVha0V2ZW50c0ZvckRhdGUgPSBhc3luYyAoXG4gIHVzZXJQcmVmZXJlbmNlczogVXNlclByZWZlcmVuY2VUeXBlLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgaG9zdFN0YXJ0RGF0ZTogc3RyaW5nLFxuICBob3N0RW5kRGF0ZTogc3RyaW5nLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgZ2xvYmFsQ2FsZW5kYXJJZD86IHN0cmluZ1xuKTogUHJvbWlzZTxFdmVudFBsdXNUeXBlW10gfCBbXT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHRvdGFsQnJlYWtFdmVudHMgPSBbXTtcbiAgICBjb25zdCB0b3RhbERheXMgPSBkYXlqcyhob3N0RW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmRpZmYoZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSksICdkYXknKTtcbiAgICBjb25zb2xlLmxvZyh0b3RhbERheXMsICcgdG90YWxEYXlzIGluc2lkZSBnZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF0ZScpO1xuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxEYXlzOyBpKyspIHtcbiAgICAgIGNvbnN0IGRheURhdGUgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmFkZChpLCAnZGF5JylcbiAgICAgICAgLmZvcm1hdCgpO1xuXG4gICAgICBjb25zdCBuZXdCcmVha0V2ZW50cyA9IGF3YWl0IGdlbmVyYXRlQnJlYWtFdmVudHNGb3JEYXkoXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBkYXlEYXRlLFxuICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgIGdsb2JhbENhbGVuZGFySWQsXG4gICAgICAgIGkgPT09IDBcbiAgICAgICk7XG5cbiAgICAgIGlmIChpID09PSAwKSB7XG4gICAgICAgIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2VzLmVuZFRpbWVzO1xuICAgICAgICBjb25zdCBkYXlPZldlZWtJbnQgPSBnZXRJU09EYXkoXG4gICAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkudG9EYXRlKClcbiAgICAgICAgKTtcblxuICAgICAgICBsZXQgc3RhcnRIb3VyID0gZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuaG91cigpO1xuICAgICAgICBsZXQgc3RhcnRNaW51dGUgPSBkYXlqcyhkYXlEYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5taW51dGUoKTtcbiAgICAgICAgY29uc3QgZW5kSG91ciA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gICAgICAgIGNvbnN0IGVuZE1pbnV0ZSA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG5cbiAgICAgICAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5zdGFydFRpbWVzO1xuICAgICAgICBjb25zdCB3b3JrU3RhcnRIb3VyID0gc3RhcnRUaW1lcy5maW5kKFxuICAgICAgICAgIChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50XG4gICAgICAgICkuaG91cjtcbiAgICAgICAgY29uc3Qgd29ya1N0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKFxuICAgICAgICAgIChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50XG4gICAgICAgICkubWludXRlcztcblxuICAgICAgICBpZiAoXG4gICAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpLmlzQWZ0ZXIoXG4gICAgICAgICAgICBkYXlqcyhkYXlEYXRlLnNsaWNlKDAsIDE5KSkuaG91cihlbmRIb3VyKS5taW51dGUoZW5kTWludXRlKVxuICAgICAgICAgIClcbiAgICAgICAgKSB7XG4gICAgICAgICAgY29udGludWU7XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoXG4gICAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpLmlzQmVmb3JlKFxuICAgICAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXIpXG4gICAgICAgICAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlKVxuICAgICAgICAgIClcbiAgICAgICAgKSB7XG4gICAgICAgICAgc3RhcnRIb3VyID0gd29ya1N0YXJ0SG91cjtcbiAgICAgICAgICBzdGFydE1pbnV0ZSA9IHdvcmtTdGFydE1pbnV0ZTtcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IGFsbEV2ZW50cyA9IGF3YWl0IGxpc3RFdmVudHNGb3JEYXRlKFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICBkYXlqcyhkYXlEYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cihzdGFydEhvdXIpXG4gICAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlKVxuICAgICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICAgIGRheWpzKGRheURhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZSlcbiAgICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgICBob3N0VGltZXpvbmVcbiAgICAgICAgKTtcbiAgICAgICAgY29uc3QgbmV3QnJlYWtFdmVudHNBZGp1c3RlZCA9XG4gICAgICAgICAgYXdhaXQgYWRqdXN0U3RhcnREYXRlc0ZvckJyZWFrRXZlbnRzRm9yRGF5KFxuICAgICAgICAgICAgYWxsRXZlbnRzLFxuICAgICAgICAgICAgbmV3QnJlYWtFdmVudHMsXG4gICAgICAgICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICAgICAgICBob3N0VGltZXpvbmVcbiAgICAgICAgICApO1xuICAgICAgICBpZiAobmV3QnJlYWtFdmVudHNBZGp1c3RlZD8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgIG5ld0JyZWFrRXZlbnRzQWRqdXN0ZWQuZm9yRWFjaCgoYikgPT5cbiAgICAgICAgICAgIGNvbnNvbGUubG9nKGIsICcgbmV3QnJlYWtFdmVudHNBZGp1c3RlZCcpXG4gICAgICAgICAgKTtcbiAgICAgICAgICB0b3RhbEJyZWFrRXZlbnRzLnB1c2goLi4ubmV3QnJlYWtFdmVudHNBZGp1c3RlZCk7XG4gICAgICAgIH1cblxuICAgICAgICBjb250aW51ZTtcbiAgICAgIH1cblxuICAgICAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZXMuZW5kVGltZXM7XG4gICAgICBjb25zdCBkYXlPZldlZWtJbnQgPSBnZXRJU09EYXkoXG4gICAgICAgIGRheWpzKGRheURhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICAgICApO1xuXG4gICAgICBjb25zdCBlbmRIb3VyID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgICAgIGNvbnN0IGVuZE1pbnV0ZSA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG5cbiAgICAgIGNvbnN0IHN0YXJ0VGltZXMgPSB1c2VyUHJlZmVyZW5jZXMuc3RhcnRUaW1lcztcbiAgICAgIGNvbnN0IHN0YXJ0SG91ciA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgICAgIGNvbnN0IHN0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKFxuICAgICAgICAoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludFxuICAgICAgKS5taW51dGVzO1xuXG4gICAgICBjb25zdCBhbGxFdmVudHMgPSBhd2FpdCBsaXN0RXZlbnRzRm9yRGF0ZShcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBkYXlqcyhkYXlEYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91cilcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuaG91cihlbmRIb3VyKVxuICAgICAgICAgIC5taW51dGUoZW5kTWludXRlKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgaG9zdFRpbWV6b25lXG4gICAgICApO1xuICAgICAgY29uc3QgbmV3QnJlYWtFdmVudHNBZGp1c3RlZCA9IGF3YWl0IGFkanVzdFN0YXJ0RGF0ZXNGb3JCcmVha0V2ZW50c0ZvckRheShcbiAgICAgICAgYWxsRXZlbnRzLFxuICAgICAgICBuZXdCcmVha0V2ZW50cyxcbiAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICBob3N0VGltZXpvbmVcbiAgICAgICk7XG4gICAgICBpZiAobmV3QnJlYWtFdmVudHNBZGp1c3RlZD8ubGVuZ3RoID4gMCkge1xuICAgICAgICBuZXdCcmVha0V2ZW50c0FkanVzdGVkLmZvckVhY2goKGIpID0+XG4gICAgICAgICAgY29uc29sZS5sb2coYiwgJyBuZXdCcmVha0V2ZW50c0FkanVzdGVkJylcbiAgICAgICAgKTtcbiAgICAgICAgdG90YWxCcmVha0V2ZW50cy5wdXNoKC4uLm5ld0JyZWFrRXZlbnRzQWRqdXN0ZWQpO1xuICAgICAgfVxuICAgIH1cblxuICAgIHJldHVybiB0b3RhbEJyZWFrRXZlbnRzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2VuZXJhdGVCcmVha0V2ZW50c0ZvckRhdGUnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlV29ya1RpbWVzRm9ySW50ZXJuYWxBdHRlbmRlZSA9IChcbiAgaG9zdElkOiBzdHJpbmcsXG4gIHVzZXJJZDogc3RyaW5nLFxuICB1c2VyUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgdXNlclRpbWV6b25lOiBzdHJpbmdcbik6IFdvcmtUaW1lVHlwZVtdID0+IHtcbiAgY29uc3QgZGF5c0luV2VlayA9IDc7XG4gIGNvbnN0IHN0YXJ0VGltZXMgPSB1c2VyUHJlZmVyZW5jZS5zdGFydFRpbWVzO1xuICBjb25zdCBlbmRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlLmVuZFRpbWVzO1xuICBjb25zdCB3b3JrVGltZXM6IFdvcmtUaW1lVHlwZVtdID0gW107XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBkYXlzSW5XZWVrOyBpKyspIHtcbiAgICBjb25zdCBkYXlPZldlZWtJbnQgPSBpICsgMTtcbiAgICBjb25zdCBzdGFydEhvdXIgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gICAgY29uc3Qgc3RhcnRNaW51dGUgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG4gICAgY29uc3QgZW5kSG91ciA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gICAgY29uc3QgZW5kTWludXRlID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcblxuICAgIHdvcmtUaW1lcy5wdXNoKHtcbiAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50XSxcbiAgICAgIHN0YXJ0VGltZTogZGF5anMoXG4gICAgICAgIHNldElTT0RheShcbiAgICAgICAgICBkYXlqcygpXG4gICAgICAgICAgICAuaG91cihzdGFydEhvdXIpXG4gICAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlKVxuICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC50b0RhdGUoKSxcbiAgICAgICAgICBpICsgMVxuICAgICAgICApXG4gICAgICApXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgIGVuZFRpbWU6IGRheWpzKFxuICAgICAgICBzZXRJU09EYXkoXG4gICAgICAgICAgZGF5anMoKVxuICAgICAgICAgICAgLmhvdXIoZW5kSG91cilcbiAgICAgICAgICAgIC5taW51dGUoZW5kTWludXRlKVxuICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC50b0RhdGUoKSxcbiAgICAgICAgICBpICsgMVxuICAgICAgICApXG4gICAgICApXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgIGhvc3RJZCxcbiAgICAgIHVzZXJJZCxcbiAgICB9KTtcbiAgfVxuXG4gIHJldHVybiB3b3JrVGltZXM7XG59O1xuXG5jb25zdCBmb3JtYXRUb01vbnRoRGF5ID0gKG1vbnRoOiBNb250aFR5cGUsIGRheTogRGF5VHlwZSk6IE1vbnRoRGF5VHlwZSA9PiB7XG4gIGNvbnN0IG1vbnRoRm9ybWF0ID0gKG1vbnRoIDwgOSA/IGAwJHttb250aCArIDF9YCA6IGAke21vbnRoICsgMX1gKSBhcyBNTTtcbiAgY29uc3QgZGF5Rm9ybWF0ID0gKGRheSA8IDEwID8gYDAke2RheX1gIDogYCR7ZGF5fWApIGFzIEREO1xuICByZXR1cm4gYC0tJHttb250aEZvcm1hdH0tJHtkYXlGb3JtYXR9YDtcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZVRpbWVTbG90c0ZvckludGVybmFsQXR0ZW5kZWUgPSAoXG4gIGhvc3RTdGFydERhdGU6IHN0cmluZyxcbiAgaG9zdElkOiBzdHJpbmcsXG4gIHVzZXJQcmVmZXJlbmNlOiBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICB1c2VyVGltZXpvbmU6IHN0cmluZyxcbiAgaXNGaXJzdERheT86IGJvb2xlYW5cbik6IFRpbWVTbG90VHlwZVtdID0+IHtcbiAgaWYgKGlzRmlyc3REYXkpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGhvc3RTdGFydERhdGUsXG4gICAgICAnIGhvc3RTdGFydERhdGUgaW5zaWRlIGZpcnN0ZGF5IGluc2lkZSBnZW5lcmF0ZXRpbWVzbG90c2ZvcmludGVybmFsYXR0ZW5kZWUnXG4gICAgKTtcbiAgICBjb25zdCBlbmRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlLmVuZFRpbWVzO1xuICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAudG9EYXRlKClcbiAgICApO1xuICAgIGNvbnN0IGRheU9mV2Vla0ludEJ5SG9zdCA9IGdldElTT0RheShcbiAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICAgKTtcbiAgICBjb25zdCBkYXlPZk1vbnRoID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC5kYXRlKCk7XG4gICAgY29uc3Qgc3RhcnRIb3VyID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgY29uc3Qgc3RhcnRNaW51dGUgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoMCksXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICdbKSdcbiAgICAgIClcbiAgICAgID8gMFxuICAgICAgOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMTUpLFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgID8gMTVcbiAgICAgICAgOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAgIC5taW51dGUoNDUpLFxuICAgICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgICAgKVxuICAgICAgICAgID8gMzBcbiAgICAgICAgICA6IDQ1O1xuXG4gICAgY29uc3QgbW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAubW9udGgoKTtcbiAgICBjb25zdCBkYXlPZk1vbnRoQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmRhdGUoKTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGRheU9mTW9udGhCeUhvc3QsXG4gICAgICAnIGRheU9mTW9udGhCeUhvc3QgaW5zaWRlIGdlbmVyYXRlVGltZVNsb3RzRm9ySW50ZXJuYWxBdHRlbmRlZXMnXG4gICAgKTtcbiAgICBjb25zdCBzdGFydEhvdXJCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkubWludXRlKDApLFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS5taW51dGUoMTUpLFxuICAgICAgICAnbWludXRlJyxcbiAgICAgICAgJ1spJ1xuICAgICAgKVxuICAgICAgPyAwXG4gICAgICA6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgID8gMTVcbiAgICAgICAgOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgICAubWludXRlKDQ1KSxcbiAgICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICAgIClcbiAgICAgICAgICA/IDMwXG4gICAgICAgICAgOiA0NTtcblxuICAgIGNvbnN0IGVuZEhvdXIgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgIGNvbnN0IGVuZE1pbnV0ZSA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG4gICAgY29uc3QgZW5kSG91ckJ5SG9zdCA9IGRheWpzKFxuICAgICAgc2V0SVNPRGF5KFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgLmhvdXIoZW5kSG91cilcbiAgICAgICAgICAudG9EYXRlKCksXG4gICAgICAgIGRheU9mV2Vla0ludFxuICAgICAgKVxuICAgIClcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IGVuZE1pbnV0ZUJ5SG9zdCA9IGRheWpzKFxuICAgICAgc2V0SVNPRGF5KFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGUpXG4gICAgICAgICAgLnRvRGF0ZSgpLFxuICAgICAgICBkYXlPZldlZWtJbnRcbiAgICAgIClcbiAgICApXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLm1pbnV0ZSgpO1xuICAgIGNvbnN0IHN0YXJ0VGltZXMgPSB1c2VyUHJlZmVyZW5jZS5zdGFydFRpbWVzO1xuICAgIGNvbnN0IHdvcmtTdGFydEhvdXIgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gICAgY29uc3Qgd29ya1N0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKFxuICAgICAgKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRcbiAgICApLm1pbnV0ZXM7XG4gICAgY29uc3Qgd29ya1N0YXJ0SG91ckJ5SG9zdCA9IGRheWpzKFxuICAgICAgc2V0SVNPRGF5KFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91cilcbiAgICAgICAgICAudG9EYXRlKCksXG4gICAgICAgIGRheU9mV2Vla0ludFxuICAgICAgKVxuICAgIClcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCA9IGRheWpzKFxuICAgICAgc2V0SVNPRGF5KFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGUpXG4gICAgICAgICAgLnRvRGF0ZSgpLFxuICAgICAgICBkYXlPZldlZWtJbnRcbiAgICAgIClcbiAgICApXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLm1pbnV0ZSgpO1xuXG4gICAgaWYgKFxuICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5pc0FmdGVyKFxuICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKGVuZEhvdXJCeUhvc3QpXG4gICAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgKVxuICAgICkge1xuICAgICAgcmV0dXJuIFtdO1xuICAgIH1cblxuICAgIGlmIChcbiAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuaXNCZWZvcmUoXG4gICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlQnlIb3N0KVxuICAgICAgICApXG4gICAgKSB7XG4gICAgICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgICBob3Vyczogd29ya1N0YXJ0SG91cixcbiAgICAgICAgbWludXRlczogd29ya1N0YXJ0TWludXRlLFxuICAgICAgfSk7XG4gICAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgICAgaG91cnM6IGVuZEhvdXIsXG4gICAgICAgIG1pbnV0ZXM6IGVuZE1pbnV0ZSxcbiAgICAgIH0pO1xuICAgICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgICAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcbiAgICAgIGNvbnN0IHRpbWVTbG90czogVGltZVNsb3RUeXBlW10gPSBbXTtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBob3N0U3RhcnREYXRlLFxuICAgICAgICBlbmRUaW1lcyxcbiAgICAgICAgZGF5T2ZXZWVrSW50QnlIb3N0LFxuICAgICAgICBkYXlPZk1vbnRoLFxuICAgICAgICBzdGFydEhvdXIsXG4gICAgICAgIHN0YXJ0TWludXRlLFxuICAgICAgICBlbmRIb3VyLFxuICAgICAgICBlbmRNaW51dGUsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBgc3RhcnREYXRlLCBlbmRUaW1lcywgZGF5T2ZXZWVrSW50QnlIb3N0LCBkYXlPZk1vbnRoLCBzdGFydEhvdXIsIHN0YXJ0TWludXRlLCBlbmRIb3VyLCBlbmRNaW51dGUgdG90YWxNaW51dGVzLCB0aW1lem9uZSwgaW5zaWRlIGZpcnN0RGF5IGluc2lkZSBnZW5lcmF0ZVRpbWVzbG90c2BcbiAgICAgICk7XG4gICAgICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsTWludXRlczsgaSArPSAxNSkge1xuICAgICAgICB0aW1lU2xvdHMucHVzaCh7XG4gICAgICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1tkYXlPZldlZWtJbnRCeUhvc3RdLFxuICAgICAgICAgIHN0YXJ0VGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICAgICAgZW5kVGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgICAgIC5hZGQoaSArIDE1LCAnbWludXRlJylcbiAgICAgICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgICAgICBob3N0SWQsXG4gICAgICAgICAgbW9udGhEYXk6IGZvcm1hdFRvTW9udGhEYXkoXG4gICAgICAgICAgICBtb250aEJ5SG9zdCBhcyBNb250aFR5cGUsXG4gICAgICAgICAgICBkYXlPZk1vbnRoQnlIb3N0IGFzIERheVR5cGVcbiAgICAgICAgICApLFxuICAgICAgICAgIGRhdGU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICAgICAgfSk7XG4gICAgICB9XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgdGltZVNsb3RzLFxuICAgICAgICAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMgZm9yIGZpcnN0IGRheSB3aGVyZSBzdGFydERhdGUgaXMgYmVmb3JlIHdvcmsgc3RhcnQgdGltZSdcbiAgICAgICk7XG4gICAgICByZXR1cm4gdGltZVNsb3RzO1xuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICBob3Vyczogc3RhcnRIb3VyLFxuICAgICAgbWludXRlczogc3RhcnRNaW51dGUsXG4gICAgfSk7XG4gICAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7IGhvdXJzOiBlbmRIb3VyLCBtaW51dGVzOiBlbmRNaW51dGUgfSk7XG4gICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG4gICAgY29uc3QgdGltZVNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgaG9zdFN0YXJ0RGF0ZSxcbiAgICAgIGVuZFRpbWVzLFxuICAgICAgZGF5T2ZXZWVrSW50LFxuICAgICAgZGF5T2ZNb250aEJ5SG9zdCxcbiAgICAgIHN0YXJ0SG91ckJ5SG9zdCxcbiAgICAgIHN0YXJ0TWludXRlQnlIb3N0LFxuICAgICAgZW5kSG91ckJ5SG9zdCxcbiAgICAgIGVuZE1pbnV0ZUJ5SG9zdCxcbiAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIGBzdGFydERhdGUsIGVuZFRpbWVzLCBkYXlPZldlZWtJbnQsIGRheU9mTW9udGgsIHN0YXJ0SG91ciwgc3RhcnRNaW51dGUsIGVuZEhvdXIsIGVuZE1pbnV0ZSB0b3RhbE1pbnV0ZXMsIHRpbWV6b25lLCBpbnNpZGUgZmlyc3REYXkgaW5zaWRlIGdlbmVyYXRlVGltZXNsb3RzYFxuICAgICk7XG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gMTUpIHtcbiAgICAgIHRpbWVTbG90cy5wdXNoKHtcbiAgICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1tkYXlPZldlZWtJbnRdLFxuICAgICAgICBzdGFydFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgLmFkZChpICsgMTUsICdtaW51dGUnKVxuICAgICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgICAgaG9zdElkLFxuICAgICAgICBtb250aERheTogZm9ybWF0VG9Nb250aERheShcbiAgICAgICAgICBtb250aEJ5SG9zdCBhcyBNb250aFR5cGUsXG4gICAgICAgICAgZGF5T2ZNb250aEJ5SG9zdCBhcyBEYXlUeXBlXG4gICAgICAgICksXG4gICAgICAgIGRhdGU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERCcpLFxuICAgICAgfSk7XG4gICAgfVxuICAgIGNvbnNvbGUubG9nKHRpbWVTbG90cywgJyB0aW1lU2xvdHMgaW5zaWRlIGdlbmVyYXRlVGltZVNsb3RzIGZvciBmaXJzdCBkYXknKTtcbiAgICByZXR1cm4gdGltZVNsb3RzO1xuICB9XG5cbiAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlLnN0YXJ0VGltZXM7XG4gIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2UuZW5kVGltZXM7XG4gIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLnRvRGF0ZSgpXG4gICk7XG4gIGNvbnN0IHN0YXJ0SG91ciA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgY29uc3Qgc3RhcnRNaW51dGUgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG4gIGNvbnN0IGVuZEhvdXIgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICBjb25zdCBlbmRNaW51dGUgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuXG4gIGNvbnN0IG1vbnRoQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAubW9udGgoKTtcbiAgY29uc3QgZGF5T2ZNb250aEJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLmRhdGUoKTtcblxuICBjb25zdCBzdGFydEhvdXJCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgLmhvdXIoc3RhcnRIb3VyKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmhvdXIoKTtcbiAgY29uc3Qgc3RhcnRNaW51dGVCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgLm1pbnV0ZShzdGFydE1pbnV0ZSlcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5taW51dGUoKTtcbiAgY29uc3QgZW5kSG91ckJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAuaG91cihlbmRIb3VyKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmhvdXIoKTtcblxuICBjb25zb2xlLmxvZyhcbiAgICBtb250aEJ5SG9zdCxcbiAgICBkYXlPZk1vbnRoQnlIb3N0LFxuICAgIHN0YXJ0SG91ckJ5SG9zdCxcbiAgICBzdGFydE1pbnV0ZUJ5SG9zdCxcbiAgICBlbmRIb3VyQnlIb3N0LFxuICAgICcgbW9udGhCeUhvc3QsIGRheU9mTW9udGhCeUhvc3QsIHN0YXJ0SG91ckJ5SG9zdCwgc3RhcnRNaW51dGVCeUhvc3QsIGVuZEhvdXJCeUhvc3QnXG4gICk7XG4gIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgaG91cnM6IHN0YXJ0SG91cixcbiAgICBtaW51dGVzOiBzdGFydE1pbnV0ZSxcbiAgfSk7XG4gIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oeyBob3VyczogZW5kSG91ciwgbWludXRlczogZW5kTWludXRlIH0pO1xuICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG4gIGNvbnN0IHRpbWVTbG90czogVGltZVNsb3RUeXBlW10gPSBbXTtcbiAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gMTUpIHtcbiAgICB0aW1lU2xvdHMucHVzaCh7XG4gICAgICBkYXlPZldlZWs6IGRheU9mV2Vla0ludFRvU3RyaW5nW2RheU9mV2Vla0ludF0sXG4gICAgICBzdGFydFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuaG91cihzdGFydEhvdXJCeUhvc3QpXG4gICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuaG91cihzdGFydEhvdXJCeUhvc3QpXG4gICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgIC5hZGQoaSArIDE1LCAnbWludXRlJylcbiAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgaG9zdElkLFxuICAgICAgbW9udGhEYXk6IGZvcm1hdFRvTW9udGhEYXkoXG4gICAgICAgIG1vbnRoQnlIb3N0IGFzIE1vbnRoVHlwZSxcbiAgICAgICAgZGF5T2ZNb250aEJ5SG9zdCBhcyBEYXlUeXBlXG4gICAgICApLFxuICAgICAgZGF0ZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICB9KTtcbiAgfVxuICBjb25zb2xlLmxvZyh0aW1lU2xvdHMsICcgdGltZVNsb3RzIGluc2lkZSBnZW5lcmF0ZVRpbWVTbG90cycpO1xuICByZXR1cm4gdGltZVNsb3RzO1xufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlVGltZVNsb3RzTGl0ZUZvckludGVybmFsQXR0ZW5kZWUgPSAoXG4gIGhvc3RTdGFydERhdGU6IHN0cmluZyxcbiAgaG9zdElkOiBzdHJpbmcsXG4gIHVzZXJQcmVmZXJlbmNlOiBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICB1c2VyVGltZXpvbmU6IHN0cmluZyxcbiAgaXNGaXJzdERheT86IGJvb2xlYW5cbik6IFRpbWVTbG90VHlwZVtdID0+IHtcbiAgaWYgKGlzRmlyc3REYXkpIHtcbiAgICBjb25zdCBlbmRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlLmVuZFRpbWVzO1xuXG4gICAgY29uc3QgZGF5T2ZXZWVrSW50ID0gZ2V0SVNPRGF5KFxuICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkudG9EYXRlKClcbiAgICApO1xuXG4gICAgY29uc3Qgc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgY29uc3Qgc3RhcnRNaW51dGVPZkhvc3REYXRlQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkubWludXRlKDApLFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS5taW51dGUoMzApLFxuICAgICAgICAnbWludXRlJyxcbiAgICAgICAgJ1spJ1xuICAgICAgKVxuICAgICAgPyAwXG4gICAgICA6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSg1OSksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgID8gMzBcbiAgICAgICAgOiAwO1xuXG4gICAgY29uc3QgbW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAubW9udGgoKTtcbiAgICBjb25zdCBkYXlPZk1vbnRoQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmRhdGUoKTtcbiAgICBjb25zdCBzdGFydEhvdXJCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkubWludXRlKDApLFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS5taW51dGUoMzApLFxuICAgICAgICAnbWludXRlJyxcbiAgICAgICAgJ1spJ1xuICAgICAgKVxuICAgICAgPyAwXG4gICAgICA6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSg1OSksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgID8gMzBcbiAgICAgICAgOiAwO1xuXG4gICAgY29uc3QgZW5kSG91ciA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gICAgY29uc3QgZW5kTWludXRlID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcbiAgICBjb25zdCBlbmRIb3VyQnlIb3N0ID0gZGF5anMoXG4gICAgICBzZXRJU09EYXkoXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAuaG91cihlbmRIb3VyKVxuICAgICAgICAgIC50b0RhdGUoKSxcbiAgICAgICAgZGF5T2ZXZWVrSW50XG4gICAgICApXG4gICAgKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgY29uc3QgZW5kTWludXRlQnlIb3N0ID0gZGF5anMoXG4gICAgICBzZXRJU09EYXkoXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZSlcbiAgICAgICAgICAudG9EYXRlKCksXG4gICAgICAgIGRheU9mV2Vla0ludFxuICAgICAgKVxuICAgIClcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAubWludXRlKCk7XG5cbiAgICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2Uuc3RhcnRUaW1lcztcbiAgICBjb25zdCB3b3JrU3RhcnRIb3VyID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZSA9IHN0YXJ0VGltZXMuZmluZChcbiAgICAgIChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50XG4gICAgKS5taW51dGVzO1xuICAgIGNvbnN0IHdvcmtTdGFydEhvdXJCeUhvc3QgPSBkYXlqcyhcbiAgICAgIHNldElTT0RheShcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXIpXG4gICAgICAgICAgLnRvRGF0ZSgpLFxuICAgICAgICBkYXlPZldlZWtJbnRcbiAgICAgIClcbiAgICApXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmhvdXIoKTtcbiAgICBjb25zdCB3b3JrU3RhcnRNaW51dGVCeUhvc3QgPSBkYXlqcyhcbiAgICAgIHNldElTT0RheShcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoZW5kTWludXRlKVxuICAgICAgICAgIC50b0RhdGUoKSxcbiAgICAgICAgZGF5T2ZXZWVrSW50XG4gICAgICApXG4gICAgKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5taW51dGUoKTtcblxuICAgIGlmIChcbiAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuaXNBZnRlcihcbiAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cihlbmRIb3VyQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGVCeUhvc3QpXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIHJldHVybiBbXTtcbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmlzQmVmb3JlKFxuICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXJCeUhvc3QpXG4gICAgICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgKVxuICAgICkge1xuICAgICAgY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgICAgaG91cnM6IHdvcmtTdGFydEhvdXIsXG4gICAgICAgIG1pbnV0ZXM6IHdvcmtTdGFydE1pbnV0ZSxcbiAgICAgIH0pO1xuICAgICAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICAgIGhvdXJzOiBlbmRIb3VyLFxuICAgICAgICBtaW51dGVzOiBlbmRNaW51dGUsXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgICAgIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG4gICAgICBjb25zdCB0aW1lU2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG4gICAgICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsTWludXRlczsgaSArPSAzMCkge1xuICAgICAgICB0aW1lU2xvdHMucHVzaCh7XG4gICAgICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1tkYXlPZldlZWtJbnRdLFxuICAgICAgICAgIHN0YXJ0VGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICAgICAgZW5kVGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgICAgIC5hZGQoaSArIDMwLCAnbWludXRlJylcbiAgICAgICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgICAgICBob3N0SWQsXG4gICAgICAgICAgbW9udGhEYXk6IGZvcm1hdFRvTW9udGhEYXkoXG4gICAgICAgICAgICBtb250aEJ5SG9zdCBhcyBNb250aFR5cGUsXG4gICAgICAgICAgICBkYXlPZk1vbnRoQnlIb3N0IGFzIERheVR5cGVcbiAgICAgICAgICApLFxuICAgICAgICAgIGRhdGU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICAgICAgfSk7XG4gICAgICB9XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgdGltZVNsb3RzLFxuICAgICAgICAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMgZm9yIGZpcnN0IGRheSBiZWZvcmUgc3RhcnQgdGltZSdcbiAgICAgICk7XG4gICAgICByZXR1cm4gdGltZVNsb3RzO1xuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICBob3Vyczogc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdCxcbiAgICAgIG1pbnV0ZXM6IHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdCxcbiAgICB9KTtcbiAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHsgaG91cnM6IGVuZEhvdXIsIG1pbnV0ZXM6IGVuZE1pbnV0ZSB9KTtcbiAgICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gICAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcbiAgICBjb25zdCB0aW1lU2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gMzApIHtcbiAgICAgIHRpbWVTbG90cy5wdXNoKHtcbiAgICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1tkYXlPZldlZWtJbnRdLFxuICAgICAgICBzdGFydFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgLmFkZChpICsgMzAsICdtaW51dGUnKVxuICAgICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgICAgaG9zdElkLFxuICAgICAgICBtb250aERheTogZm9ybWF0VG9Nb250aERheShcbiAgICAgICAgICBtb250aEJ5SG9zdCBhcyBNb250aFR5cGUsXG4gICAgICAgICAgZGF5T2ZNb250aEJ5SG9zdCBhcyBEYXlUeXBlXG4gICAgICAgICksXG4gICAgICAgIGRhdGU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERCcpLFxuICAgICAgfSk7XG4gICAgfVxuICAgIGNvbnNvbGUubG9nKHRpbWVTbG90cywgJyB0aW1lU2xvdHMgaW5zaWRlIGdlbmVyYXRlVGltZVNsb3RzIGZvciBmaXJzdCBkYXknKTtcbiAgICByZXR1cm4gdGltZVNsb3RzO1xuICB9XG4gIGNvbnN0IHN0YXJ0VGltZXMgPSB1c2VyUHJlZmVyZW5jZS5zdGFydFRpbWVzO1xuICBjb25zdCBlbmRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlLmVuZFRpbWVzO1xuXG4gIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLnRvRGF0ZSgpXG4gICk7XG4gIGNvbnN0IHN0YXJ0SG91ciA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgY29uc3Qgc3RhcnRNaW51dGUgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG4gIGNvbnN0IGVuZEhvdXIgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICBjb25zdCBlbmRNaW51dGUgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuXG4gIGNvbnN0IG1vbnRoQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAubW9udGgoKTtcbiAgY29uc3QgZGF5T2ZNb250aEJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLmRhdGUoKTtcbiAgY29uc3QgZGF5T2ZXZWVrSW50QnlIb3N0ID0gZ2V0SVNPRGF5KFxuICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICk7XG4gIGNvbnN0IHN0YXJ0SG91ckJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAuaG91cihzdGFydEhvdXIpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAuaG91cigpO1xuICBjb25zdCBzdGFydE1pbnV0ZUJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAubWludXRlKHN0YXJ0TWludXRlKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLm1pbnV0ZSgpO1xuXG4gIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgaG91cnM6IHN0YXJ0SG91cixcbiAgICBtaW51dGVzOiBzdGFydE1pbnV0ZSxcbiAgfSk7XG4gIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oeyBob3VyczogZW5kSG91ciwgbWludXRlczogZW5kTWludXRlIH0pO1xuICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG4gIGNvbnN0IHRpbWVTbG90czogVGltZVNsb3RUeXBlW10gPSBbXTtcbiAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gMzApIHtcbiAgICB0aW1lU2xvdHMucHVzaCh7XG4gICAgICBkYXlPZldlZWs6IGRheU9mV2Vla0ludFRvU3RyaW5nW2RheU9mV2Vla0ludEJ5SG9zdF0sXG4gICAgICBzdGFydFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuaG91cihzdGFydEhvdXJCeUhvc3QpXG4gICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuaG91cihzdGFydEhvdXJCeUhvc3QpXG4gICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgIC5hZGQoaSArIDMwLCAnbWludXRlJylcbiAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgaG9zdElkLFxuICAgICAgbW9udGhEYXk6IGZvcm1hdFRvTW9udGhEYXkoXG4gICAgICAgIG1vbnRoQnlIb3N0IGFzIE1vbnRoVHlwZSxcbiAgICAgICAgZGF5T2ZNb250aEJ5SG9zdCBhcyBEYXlUeXBlXG4gICAgICApLFxuICAgICAgZGF0ZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICB9KTtcbiAgfVxuICBjb25zb2xlLmxvZyh0aW1lU2xvdHMsICcgdGltZVNsb3RzIGluc2lkZSBnZW5lcmF0ZVRpbWVTbG90cycpO1xuICByZXR1cm4gdGltZVNsb3RzO1xufTtcblxuZXhwb3J0IGNvbnN0IHZhbGlkYXRlRXZlbnREYXRlcyA9IChcbiAgZXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIHVzZXJQcmVmZXJlbmNlczogVXNlclByZWZlcmVuY2VUeXBlXG4pOiBib29sZWFuID0+IHtcbiAgaWYgKCFldmVudD8udGltZXpvbmUpIHtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICBjb25zdCBkaWZmID0gZGF5anMoZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgIC5kaWZmKGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKSwgJ20nKTtcbiAgY29uc3QgZGlmZkRheSA9IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAuZGlmZihkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihldmVudC50aW1lem9uZSwgdHJ1ZSksICdkJyk7XG4gIGNvbnN0IGRpZmZIb3VycyA9IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAuZGlmZihkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihldmVudC50aW1lem9uZSwgdHJ1ZSksICdoJyk7XG5cbiAgY29uc3QgaXNvV2Vla0RheSA9IGdldElTT0RheShcbiAgICBkYXlqcyhldmVudD8uc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooZXZlbnQ/LnRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICApO1xuICBjb25zdCBlbmRIb3VyID0gdXNlclByZWZlcmVuY2VzLmVuZFRpbWVzLmZpbmQoXG4gICAgKGUpID0+IGU/LmRheSA9PT0gaXNvV2Vla0RheVxuICApPy5ob3VyO1xuICBjb25zdCBlbmRNaW51dGVzID0gdXNlclByZWZlcmVuY2VzLmVuZFRpbWVzLmZpbmQoXG4gICAgKGUpID0+IGU/LmRheSA9PT0gaXNvV2Vla0RheVxuICApPy5taW51dGVzO1xuICBjb25zdCBzdGFydEhvdXIgPSB1c2VyUHJlZmVyZW5jZXMuc3RhcnRUaW1lcy5maW5kKFxuICAgIChlKSA9PiBlPy5kYXkgPT09IGlzb1dlZWtEYXlcbiAgKT8uaG91cjtcbiAgY29uc3Qgc3RhcnRNaW51dGVzID0gdXNlclByZWZlcmVuY2VzLnN0YXJ0VGltZXMuZmluZChcbiAgICAoZSkgPT4gZT8uZGF5ID09PSBpc29XZWVrRGF5XG4gICk/Lm1pbnV0ZXM7XG5cbiAgaWYgKFxuICAgIGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAuaXNBZnRlcihcbiAgICAgICAgZGF5anMoZXZlbnQ/LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGVzKVxuICAgICAgKVxuICApIHtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICBpZiAoXG4gICAgZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5pc0JlZm9yZShcbiAgICAgICAgZGF5anMoZXZlbnQ/LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91cilcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlcylcbiAgICAgIClcbiAgKSB7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgaWYgKGRpZmYgPT09IDApIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGV2ZW50LmlkLFxuICAgICAgZXZlbnQuc3RhcnREYXRlLFxuICAgICAgZXZlbnQuZW5kRGF0ZSxcbiAgICAgICcgdGhlIHN0YXJ0IGRhdGUgYW5kIGVuZCBkYXRlIGFyZSB0aGUgc2FtZSdcbiAgICApO1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuXG4gIGlmIChkaWZmIDwgMCkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZXZlbnQuaWQsXG4gICAgICBldmVudC5zdGFydERhdGUsXG4gICAgICBldmVudC5lbmREYXRlLFxuICAgICAgJyB0aGUgc3RhcnQgZGF0ZSBpcyBhZnRlciBlbmQgZGF0ZSdcbiAgICApO1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuXG4gIGlmIChkaWZmRGF5ID49IDEpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGV2ZW50LmlkLFxuICAgICAgZXZlbnQuc3RhcnREYXRlLFxuICAgICAgZXZlbnQuZW5kRGF0ZSxcbiAgICAgICcgdGhlIHN0YXJ0IGRhdGUgYW5kIGVuZCBkYXRlIGFyZSBtb3JlIHRoYW4gMSBkYXkgYXBhcnQnXG4gICAgKTtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICBpZiAoZGlmZkhvdXJzID4gMjMpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGV2ZW50LmlkLFxuICAgICAgZXZlbnQuc3RhcnREYXRlLFxuICAgICAgZXZlbnQuZW5kRGF0ZSxcbiAgICAgICcgdGhlIHN0YXJ0IGRhdGUgYW5kIGVuZCBkYXRlIGFyZSBtb3JlIHRoYW4gMjMgaG91cnMgYXBhcnQnXG4gICAgKTtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICByZXR1cm4gdHJ1ZTtcbn07XG5cbmV4cG9ydCBjb25zdCB2YWxpZGF0ZUV2ZW50RGF0ZXNGb3JFeHRlcm5hbEF0dGVuZGVlID0gKFxuICBldmVudDogRXZlbnRQbHVzVHlwZVxuKTogYm9vbGVhbiA9PiB7XG4gIGlmICghZXZlbnQ/LnRpbWV6b25lKSB7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgY29uc3QgZGlmZiA9IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAuZGlmZihkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihldmVudC50aW1lem9uZSwgdHJ1ZSksICdtJyk7XG4gIGNvbnN0IGRpZmZEYXkgPSBkYXlqcyhldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgLmRpZmYoZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooZXZlbnQudGltZXpvbmUsIHRydWUpLCAnZCcpO1xuICBjb25zdCBkaWZmSG91cnMgPSBkYXlqcyhldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgLmRpZmYoZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooZXZlbnQudGltZXpvbmUsIHRydWUpLCAnaCcpO1xuXG4gIGlmIChkaWZmID09PSAwKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBldmVudC5pZCxcbiAgICAgIGV2ZW50LnN0YXJ0RGF0ZSxcbiAgICAgIGV2ZW50LmVuZERhdGUsXG4gICAgICAnIHRoZSBzdGFydCBkYXRlIGFuZCBlbmQgZGF0ZSBhcmUgdGhlIHNhbWUnXG4gICAgKTtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICBpZiAoZGlmZiA8IDApIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGV2ZW50LmlkLFxuICAgICAgZXZlbnQuc3RhcnREYXRlLFxuICAgICAgZXZlbnQuZW5kRGF0ZSxcbiAgICAgICcgdGhlIHN0YXJ0IGRhdGUgaXMgYWZ0ZXIgZW5kIGRhdGUnXG4gICAgKTtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICBpZiAoZGlmZkRheSA+PSAxKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBldmVudC5pZCxcbiAgICAgIGV2ZW50LnN0YXJ0RGF0ZSxcbiAgICAgIGV2ZW50LmVuZERhdGUsXG4gICAgICAnIHRoZSBzdGFydCBkYXRlIGFuZCBlbmQgZGF0ZSBhcmUgbW9yZSB0aGFuIDEgZGF5IGFwYXJ0J1xuICAgICk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgaWYgKGRpZmZIb3VycyA+IDIzKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBldmVudC5pZCxcbiAgICAgIGV2ZW50LnN0YXJ0RGF0ZSxcbiAgICAgIGV2ZW50LmVuZERhdGUsXG4gICAgICAnIHRoZSBzdGFydCBkYXRlIGFuZCBlbmQgZGF0ZSBhcmUgbW9yZSB0aGFuIDIzIGhvdXJzIGFwYXJ0J1xuICAgICk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgcmV0dXJuIHRydWU7XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVFdmVudFBhcnRzID0gKFxuICBldmVudDogRXZlbnRQbHVzVHlwZSxcbiAgaG9zdElkOiBzdHJpbmdcbik6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPT4ge1xuICBjb25zb2xlLmxvZyhcbiAgICBldmVudC5pZCxcbiAgICBldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpLFxuICAgIGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpLFxuICAgICcgZXZlbnQuaWQsIGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSksIGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpIGluc2lkZSBnZW5lcmF0ZUV2ZW50UGFydHMnXG4gICk7XG4gIGNvbnN0IG1pbnV0ZXMgPSBkYXlqcyhldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgLmRpZmYoZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooZXZlbnQudGltZXpvbmUsIHRydWUpLCAnbScpO1xuICBjb25zb2xlLmxvZyhcbiAgICBldmVudC5pZCxcbiAgICBtaW51dGVzLFxuICAgICdldmVudC5pZCwgIG1pbnV0ZXMgaW5zaWRlIGdlbmVyYXRlRXZlbnRQYXJ0cydcbiAgKTtcbiAgY29uc3QgcGFydHMgPSBNYXRoLmZsb29yKG1pbnV0ZXMgLyAxNSk7XG4gIGNvbnN0IHJlbWFpbmRlciA9IG1pbnV0ZXMgJSAxNTtcbiAgY29uc3QgZXZlbnRQYXJ0czogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSA9IFtdO1xuICBmb3IgKGxldCBpID0gMDsgaSA8IHBhcnRzOyBpKyspIHtcbiAgICBldmVudFBhcnRzLnB1c2goe1xuICAgICAgLi4uZXZlbnQsXG4gICAgICBncm91cElkOiBldmVudC5pZCxcbiAgICAgIGV2ZW50SWQ6IGV2ZW50LmlkLFxuICAgICAgc3RhcnREYXRlOiBldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpLFxuICAgICAgZW5kRGF0ZTogZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSksXG4gICAgICBwYXJ0OiBpICsgMSxcbiAgICAgIGxhc3RQYXJ0OiByZW1haW5kZXIgPiAwID8gcGFydHMgKyAxIDogcGFydHMsXG4gICAgICBob3N0SWQsXG4gICAgICBtZWV0aW5nUGFydDogaSArIDEsXG4gICAgICBtZWV0aW5nTGFzdFBhcnQ6IHJlbWFpbmRlciA+IDAgPyBwYXJ0cyArIDEgOiBwYXJ0cyxcbiAgICB9KTtcbiAgfVxuXG4gIGlmIChyZW1haW5kZXIgPiAwKSB7XG4gICAgZXZlbnRQYXJ0cy5wdXNoKHtcbiAgICAgIC4uLmV2ZW50LFxuICAgICAgZ3JvdXBJZDogZXZlbnQuaWQsXG4gICAgICBldmVudElkOiBldmVudC5pZCxcbiAgICAgIHN0YXJ0RGF0ZTogZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSxcbiAgICAgIGVuZERhdGU6IGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpLFxuICAgICAgcGFydDogcGFydHMgKyAxLFxuICAgICAgbGFzdFBhcnQ6IHBhcnRzICsgMSxcbiAgICAgIGhvc3RJZCxcbiAgICAgIG1lZXRpbmdQYXJ0OiBwYXJ0cyArIDEsXG4gICAgICBtZWV0aW5nTGFzdFBhcnQ6IHBhcnRzICsgMSxcbiAgICB9KTtcbiAgfVxuICBjb25zb2xlLmxvZyhcbiAgICBldmVudC5pZCxcbiAgICBldmVudFBhcnRzPy5bMF0/LnN0YXJ0RGF0ZSxcbiAgICBldmVudFBhcnRzPy5bMF0/LmVuZERhdGUsXG4gICAgZXZlbnRQYXJ0cz8uWzBdPy5wYXJ0LFxuICAgIGV2ZW50UGFydHM/LlswXT8ubGFzdFBhcnQsXG4gICAgJ2V2ZW50LmlkLCAgZXZlbnRQYXJ0cz8uWzBdPy5zdGFydERhdGUsIGV2ZW50UGFydHM/LlswXT8uZW5kRGF0ZSwgZXZlbnRQYXJ0cz8uWzBdPy5wYXJ0LCBldmVudFBhcnRzPy5bMF0/Lmxhc3RQYXJ0LCdcbiAgKTtcbiAgcmV0dXJuIGV2ZW50UGFydHM7XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVFdmVudFBhcnRzTGl0ZSA9IChcbiAgZXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIGhvc3RJZDogc3RyaW5nXG4pOiBJbml0aWFsRXZlbnRQYXJ0VHlwZVtdID0+IHtcbiAgY29uc29sZS5sb2coZXZlbnQsICcgZXZlbnQgYmVmb3JlIGdlbmVyYXRlRXZlbnRQYXJ0c0xpdGUnKTtcbiAgY29uc29sZS5sb2coXG4gICAgZXZlbnQuaWQsXG4gICAgZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSxcbiAgICBldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSxcbiAgICAnIGV2ZW50LmlkLCBldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpLCBldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSBpbnNpZGUgZ2VuZXJhdGVFdmVudFBhcnRzTGl0ZSdcbiAgKTtcbiAgY29uc3QgbWludXRlcyA9IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAuZGlmZihkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihldmVudC50aW1lem9uZSwgdHJ1ZSksICdtJyk7XG4gIGNvbnN0IHBhcnRzID0gTWF0aC5mbG9vcihtaW51dGVzIC8gMzApO1xuICBjb25zdCByZW1haW5kZXIgPSBtaW51dGVzICUgMzA7XG4gIGNvbnN0IGV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPSBbXTtcbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBwYXJ0czsgaSsrKSB7XG4gICAgZXZlbnRQYXJ0cy5wdXNoKHtcbiAgICAgIC4uLmV2ZW50LFxuICAgICAgZ3JvdXBJZDogZXZlbnQuaWQsXG4gICAgICBldmVudElkOiBldmVudC5pZCxcbiAgICAgIHN0YXJ0RGF0ZTogZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSxcbiAgICAgIGVuZERhdGU6IGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpLFxuICAgICAgcGFydDogaSArIDEsXG4gICAgICBsYXN0UGFydDogcmVtYWluZGVyID4gMCA/IHBhcnRzICsgMSA6IHBhcnRzLFxuICAgICAgaG9zdElkLFxuICAgICAgbWVldGluZ1BhcnQ6IGkgKyAxLFxuICAgICAgbWVldGluZ0xhc3RQYXJ0OiByZW1haW5kZXIgPiAwID8gcGFydHMgKyAxIDogcGFydHMsXG4gICAgfSk7XG4gIH1cblxuICBpZiAocmVtYWluZGVyID4gMCkge1xuICAgIGV2ZW50UGFydHMucHVzaCh7XG4gICAgICAuLi5ldmVudCxcbiAgICAgIGdyb3VwSWQ6IGV2ZW50LmlkLFxuICAgICAgZXZlbnRJZDogZXZlbnQuaWQsXG4gICAgICBzdGFydERhdGU6IGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSksXG4gICAgICBlbmREYXRlOiBldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSxcbiAgICAgIHBhcnQ6IHBhcnRzICsgMSxcbiAgICAgIGxhc3RQYXJ0OiBwYXJ0cyArIDEsXG4gICAgICBob3N0SWQsXG4gICAgICBtZWV0aW5nUGFydDogcGFydHMgKyAxLFxuICAgICAgbWVldGluZ0xhc3RQYXJ0OiBwYXJ0cyArIDEsXG4gICAgfSk7XG4gIH1cbiAgY29uc29sZS5sb2coZXZlbnRQYXJ0cywgJyBldmVudFBhcnRzIGluc2lkZSBnZW5lcmF0ZUV2ZW50UGFydHNMaXRlJyk7XG4gIHJldHVybiBldmVudFBhcnRzO1xufTtcblxuZXhwb3J0IGNvbnN0IG1vZGlmeUV2ZW50UGFydHNGb3JTaW5ndWxhclByZUJ1ZmZlclRpbWUgPSAoXG4gIGV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW10sXG4gIGZvckV2ZW50SWQ6IHN0cmluZ1xuKTogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSA9PiB7XG4gIGNvbnN0IHByZUJ1ZmZlckJlZm9yZUV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPSBbXTtcbiAgY29uc3QgcHJlQnVmZmVyQWN0dWFsRXZlbnRQYXJ0czogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSA9IFtdO1xuXG4gIGNvbnN0IHByZUJ1ZmZlckdyb3VwSWQgPSB1dWlkKCk7XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBldmVudFBhcnRzLmxlbmd0aDsgaSsrKSB7XG4gICAgaWYgKGV2ZW50UGFydHNbaV0uZm9yRXZlbnRJZCA9PT0gZm9yRXZlbnRJZCAmJiBldmVudFBhcnRzW2ldLmlzUHJlRXZlbnQpIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBldmVudFBhcnRzW2ldLmZvckV2ZW50SWQsXG4gICAgICAgIGZvckV2ZW50SWQsXG4gICAgICAgICcgZXZlbnRQYXJ0c1tpXS5mb3JFdmVudElkID09PSBmb3JFdmVudElkICBpbnNpZGUgbW9kaWZ5RXZlbnRQYXJ0c0ZvclNpbmd1bGFyUHJlQnVmZmVyVGltZSdcbiAgICAgICk7XG4gICAgICBwcmVCdWZmZXJCZWZvcmVFdmVudFBhcnRzLnB1c2goe1xuICAgICAgICAuLi5ldmVudFBhcnRzW2ldLFxuICAgICAgICBncm91cElkOiBwcmVCdWZmZXJHcm91cElkLFxuICAgICAgfSk7XG4gICAgfVxuICB9XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBldmVudFBhcnRzLmxlbmd0aDsgaSsrKSB7XG4gICAgaWYgKGV2ZW50UGFydHNbaV0uaWQgPT09IGZvckV2ZW50SWQpIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBldmVudFBhcnRzW2ldLmlkLFxuICAgICAgICBmb3JFdmVudElkLFxuICAgICAgICAnZXZlbnRQYXJ0c1tpXS5pZCA9PT0gZm9yRXZlbnRJZCBpbnNpZGUgbW9kaWZ5RXZlbnRQYXJ0c0ZvclNpbmd1bGFyUHJlQnVmZmVyVGltZSdcbiAgICAgICk7XG4gICAgICBwcmVCdWZmZXJBY3R1YWxFdmVudFBhcnRzLnB1c2goe1xuICAgICAgICAuLi5ldmVudFBhcnRzW2ldLFxuICAgICAgICBncm91cElkOiBwcmVCdWZmZXJHcm91cElkLFxuICAgICAgfSk7XG4gICAgfVxuICB9XG5cbiAgY29uc3QgcHJlQnVmZmVyQmVmb3JlRXZlbnRQYXJ0c1NvcnRlZCA9IHByZUJ1ZmZlckJlZm9yZUV2ZW50UGFydHMuc29ydChcbiAgICAoYSwgYikgPT4gYS5wYXJ0IC0gYi5wYXJ0XG4gICk7XG4gIGNvbnN0IHByZUJ1ZmZlckFjdHVhbEV2ZW50UGFydHNTb3J0ZWQgPSBwcmVCdWZmZXJBY3R1YWxFdmVudFBhcnRzLnNvcnQoXG4gICAgKGEsIGIpID0+IGEucGFydCAtIGIucGFydFxuICApO1xuXG4gIGNvbnN0IHByZUJ1ZmZlckV2ZW50UGFydHNUb3RhbCA9IHByZUJ1ZmZlckJlZm9yZUV2ZW50UGFydHNTb3J0ZWQuY29uY2F0KFxuICAgIHByZUJ1ZmZlckFjdHVhbEV2ZW50UGFydHNTb3J0ZWRcbiAgKTtcblxuICBmb3IgKGxldCBpID0gMDsgaSA8IHByZUJ1ZmZlckV2ZW50UGFydHNUb3RhbC5sZW5ndGg7IGkrKykge1xuICAgIHByZUJ1ZmZlckV2ZW50UGFydHNUb3RhbFtpXS5wYXJ0ID0gaSArIDE7XG4gICAgcHJlQnVmZmVyRXZlbnRQYXJ0c1RvdGFsW2ldLmxhc3RQYXJ0ID0gcHJlQnVmZmVyRXZlbnRQYXJ0c1RvdGFsLmxlbmd0aDtcbiAgfVxuICBwcmVCdWZmZXJFdmVudFBhcnRzVG90YWwuZm9yRWFjaCgoZSkgPT5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUuaWQsXG4gICAgICBlLmdyb3VwSWQsXG4gICAgICBlLmV2ZW50SWQsXG4gICAgICBlLnBhcnQsXG4gICAgICBlLmxhc3RQYXJ0LFxuICAgICAgZS5zdGFydERhdGUsXG4gICAgICBlLmVuZERhdGUsXG4gICAgICBgZS5pZCwgZS5ncm91cElkLCBlLmV2ZW50SWQsIGUucGFydCwgZS5sYXN0UGFydCwgZS5zdGFydERhdGUsIGUuZW5kRGF0ZSwgaW5zaWRlIG1vZGlmeUV2ZW50UGFydHNGb3JTaW5ndWxhclByZUJ1ZmZlclRpbWVgXG4gICAgKVxuICApO1xuICByZXR1cm4gcHJlQnVmZmVyRXZlbnRQYXJ0c1RvdGFsO1xufTtcbmV4cG9ydCBjb25zdCBtb2RpZnlFdmVudFBhcnRzRm9yTXVsdGlwbGVQcmVCdWZmZXJUaW1lID0gKFxuICBldmVudFBhcnRzOiBJbml0aWFsRXZlbnRQYXJ0VHlwZVtdXG4pOiBJbml0aWFsRXZlbnRQYXJ0VHlwZVtdID0+IHtcbiAgY29uc3QgdW5pcXVlUHJlQnVmZmVyUGFydEZvckV2ZW50SWRzOiBzdHJpbmdbXSA9IFtdO1xuICBjb25zdCBwcmVCdWZmZXJFdmVudFBhcnRzVG90YWw6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPSBbXTtcblxuICBmb3IgKGxldCBpID0gMDsgaSA8IGV2ZW50UGFydHMubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAoZXZlbnRQYXJ0c1tpXS5mb3JFdmVudElkICYmIGV2ZW50UGFydHNbaV0uaXNQcmVFdmVudCkge1xuICAgICAgY29uc3QgZm91bmRQYXJ0ID0gdW5pcXVlUHJlQnVmZmVyUGFydEZvckV2ZW50SWRzLmZpbmQoXG4gICAgICAgIChlKSA9PiBlID09PSBldmVudFBhcnRzW2ldLmZvckV2ZW50SWRcbiAgICAgICk7XG4gICAgICBpZiAoZm91bmRQYXJ0KSB7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgdW5pcXVlUHJlQnVmZmVyUGFydEZvckV2ZW50SWRzLnB1c2goZXZlbnRQYXJ0c1tpXS5mb3JFdmVudElkKTtcbiAgICAgIH1cbiAgICB9XG4gIH1cblxuICBmb3IgKGxldCBpID0gMDsgaSA8IHVuaXF1ZVByZUJ1ZmZlclBhcnRGb3JFdmVudElkcy5sZW5ndGg7IGkrKykge1xuICAgIGNvbnN0IHJldHVybmVkRXZlbnRQYXJ0VG90YWwgPSBtb2RpZnlFdmVudFBhcnRzRm9yU2luZ3VsYXJQcmVCdWZmZXJUaW1lKFxuICAgICAgZXZlbnRQYXJ0cyxcbiAgICAgIHVuaXF1ZVByZUJ1ZmZlclBhcnRGb3JFdmVudElkc1tpXVxuICAgICk7XG4gICAgcHJlQnVmZmVyRXZlbnRQYXJ0c1RvdGFsLnB1c2goLi4ucmV0dXJuZWRFdmVudFBhcnRUb3RhbCk7XG4gIH1cblxuICBjb25zdCBldmVudFBhcnRzRmlsdGVyZWQgPSBfLmRpZmZlcmVuY2VCeShcbiAgICBldmVudFBhcnRzLFxuICAgIHByZUJ1ZmZlckV2ZW50UGFydHNUb3RhbCxcbiAgICAnaWQnXG4gICk7XG4gIGNvbnN0IGNvbmNhdGVuYXRlZFZhbHVlcyA9IGV2ZW50UGFydHNGaWx0ZXJlZC5jb25jYXQoXG4gICAgcHJlQnVmZmVyRXZlbnRQYXJ0c1RvdGFsXG4gICk7XG4gIGNvbmNhdGVuYXRlZFZhbHVlcy5mb3JFYWNoKChlKSA9PlxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZS5pZCxcbiAgICAgIGUuZ3JvdXBJZCxcbiAgICAgIGUuZXZlbnRJZCxcbiAgICAgIGUucGFydCxcbiAgICAgIGUubGFzdFBhcnQsXG4gICAgICBlLnN0YXJ0RGF0ZSxcbiAgICAgIGUuZW5kRGF0ZSxcbiAgICAgIGU/LmZvckV2ZW50SWQsXG4gICAgICBgZS5pZCwgZS5ldmVudElkLCBlLmFjdHVhbElkLCBlLnBhcnQsIGUubGFzdFBhcnQsIGUuc3RhcnREYXRlLCBlLmVuZERhdGUsIGU/LmZvckV2ZW50SWQsICBpbnNpZGUgbW9kaWZ5RXZlbnRQYXJ0c0Zvck11bHRpcGxlUHJlQnVmZmVyVGltZWBcbiAgICApXG4gICk7XG4gIHJldHVybiBjb25jYXRlbmF0ZWRWYWx1ZXM7XG59O1xuXG5leHBvcnQgY29uc3QgbW9kaWZ5RXZlbnRQYXJ0c0Zvck11bHRpcGxlUG9zdEJ1ZmZlclRpbWUgPSAoXG4gIGV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW11cbik6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPT4ge1xuICBjb25zdCB1bmlxdWVQb3N0QnVmZmVyUGFydEZvckV2ZW50SWRzOiBzdHJpbmdbXSA9IFtdO1xuICBjb25zdCBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsOiBJbml0aWFsRXZlbnRQYXJ0VHlwZVtdID0gW107XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBldmVudFBhcnRzLmxlbmd0aDsgaSsrKSB7XG4gICAgaWYgKGV2ZW50UGFydHNbaV0uZm9yRXZlbnRJZCAmJiBldmVudFBhcnRzW2ldLmlzUG9zdEV2ZW50KSB7XG4gICAgICBjb25zdCBmb3VuZFBhcnQgPSB1bmlxdWVQb3N0QnVmZmVyUGFydEZvckV2ZW50SWRzLmZpbmQoXG4gICAgICAgIChlKSA9PiBlID09PSBldmVudFBhcnRzW2ldLmZvckV2ZW50SWRcbiAgICAgICk7XG4gICAgICBpZiAoZm91bmRQYXJ0KSB7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgdW5pcXVlUG9zdEJ1ZmZlclBhcnRGb3JFdmVudElkcy5wdXNoKGV2ZW50UGFydHNbaV0uZm9yRXZlbnRJZCk7XG4gICAgICB9XG4gICAgfVxuICB9XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPCB1bmlxdWVQb3N0QnVmZmVyUGFydEZvckV2ZW50SWRzLmxlbmd0aDsgaSsrKSB7XG4gICAgY29uc3QgcmV0dXJuZWRFdmVudFBhcnRUb3RhbCA9IG1vZGlmeUV2ZW50UGFydHNGb3JTaW5ndWxhclBvc3RCdWZmZXJUaW1lKFxuICAgICAgZXZlbnRQYXJ0cyxcbiAgICAgIHVuaXF1ZVBvc3RCdWZmZXJQYXJ0Rm9yRXZlbnRJZHNbaV1cbiAgICApO1xuICAgIHBvc3RCdWZmZXJFdmVudFBhcnRzVG90YWwucHVzaCguLi5yZXR1cm5lZEV2ZW50UGFydFRvdGFsKTtcbiAgfVxuXG4gIGNvbnN0IGV2ZW50UGFydHNGaWx0ZXJlZCA9IF8uZGlmZmVyZW5jZUJ5KFxuICAgIGV2ZW50UGFydHMsXG4gICAgcG9zdEJ1ZmZlckV2ZW50UGFydHNUb3RhbCxcbiAgICAnaWQnXG4gICk7XG4gIGNvbnN0IGNvbmNhdGVuYXRlZFZhbHVlcyA9IGV2ZW50UGFydHNGaWx0ZXJlZC5jb25jYXQoXG4gICAgcG9zdEJ1ZmZlckV2ZW50UGFydHNUb3RhbFxuICApO1xuXG4gIGNvbmNhdGVuYXRlZFZhbHVlcy5mb3JFYWNoKChlKSA9PlxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZS5pZCxcbiAgICAgIGUuZ3JvdXBJZCxcbiAgICAgIGUuZXZlbnRJZCxcbiAgICAgIGUucGFydCxcbiAgICAgIGUubGFzdFBhcnQsXG4gICAgICBlLnN0YXJ0RGF0ZSxcbiAgICAgIGUuZW5kRGF0ZSxcbiAgICAgIGU/LmZvckV2ZW50SWQsXG4gICAgICBgZS5pZCwgZS5ncm91cElkLCBlLmV2ZW50SWQsIGUucGFydCwgZS5sYXN0UGFydCwgZS5zdGFydERhdGUsIGUuZW5kRGF0ZSwgZT8uZm9yRXZlbnRJZCwgIGluc2lkZSBtb2RpZnlFdmVudFBhcnRzRm9yTXVsdGlwbGVQb3N0QnVmZmVyVGltZWBcbiAgICApXG4gICk7XG4gIHJldHVybiBjb25jYXRlbmF0ZWRWYWx1ZXM7XG59O1xuXG5leHBvcnQgY29uc3QgbW9kaWZ5RXZlbnRQYXJ0c0ZvclNpbmd1bGFyUG9zdEJ1ZmZlclRpbWUgPSAoXG4gIGV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW10sXG4gIGZvckV2ZW50SWQ6IHN0cmluZ1xuKTogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSA9PiB7XG4gIGNvbnN0IHBvc3RCdWZmZXJBZnRlckV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPSBbXTtcbiAgY29uc3QgcG9zdEJ1ZmZlckFjdHVhbEV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPSBbXTtcblxuICBjb25zdCBwb3N0QnVmZmVyR3JvdXBJZCA9IHV1aWQoKTtcblxuICBmb3IgKGxldCBpID0gMDsgaSA8IGV2ZW50UGFydHMubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAoZXZlbnRQYXJ0c1tpXS5pZCA9PSBmb3JFdmVudElkKSB7XG4gICAgICBwb3N0QnVmZmVyQWN0dWFsRXZlbnRQYXJ0cy5wdXNoKHtcbiAgICAgICAgLi4uZXZlbnRQYXJ0c1tpXSxcbiAgICAgICAgZ3JvdXBJZDogcG9zdEJ1ZmZlckdyb3VwSWQsXG4gICAgICB9KTtcbiAgICB9XG4gIH1cblxuICBmb3IgKGxldCBpID0gMDsgaSA8IGV2ZW50UGFydHMubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAoZXZlbnRQYXJ0c1tpXS5mb3JFdmVudElkID09PSBmb3JFdmVudElkICYmIGV2ZW50UGFydHNbaV0uaXNQb3N0RXZlbnQpIHtcbiAgICAgIHBvc3RCdWZmZXJBZnRlckV2ZW50UGFydHMucHVzaCh7XG4gICAgICAgIC4uLmV2ZW50UGFydHNbaV0sXG4gICAgICAgIGdyb3VwSWQ6IHBvc3RCdWZmZXJHcm91cElkLFxuICAgICAgfSk7XG4gICAgfVxuICB9XG5cbiAgY29uc3QgcG9zdEJ1ZmZlckFjdHVhbEV2ZW50UGFydHNTb3J0ZWQgPSBwb3N0QnVmZmVyQWN0dWFsRXZlbnRQYXJ0cy5zb3J0KFxuICAgIChhLCBiKSA9PiBhLnBhcnQgLSBiLnBhcnRcbiAgKTtcbiAgY29uc3QgcG9zdEJ1ZmZlckFmdGVyRXZlbnRQYXJ0c1NvcnRlZCA9IHBvc3RCdWZmZXJBZnRlckV2ZW50UGFydHMuc29ydChcbiAgICAoYSwgYikgPT4gYS5wYXJ0IC0gYi5wYXJ0XG4gICk7XG5cbiAgY29uc3QgcG9zdEJ1ZmZlckV2ZW50UGFydHNUb3RhbCA9IHBvc3RCdWZmZXJBY3R1YWxFdmVudFBhcnRzU29ydGVkLmNvbmNhdChcbiAgICBwb3N0QnVmZmVyQWZ0ZXJFdmVudFBhcnRzU29ydGVkXG4gICk7XG5cbiAgY29uc3QgcHJlRXZlbnRJZCA9IHBvc3RCdWZmZXJFdmVudFBhcnRzVG90YWw/LlswXT8ucHJlRXZlbnRJZDtcbiAgY29uc3QgYWN0dWFsRXZlbnRQcmV2aW91c0xhc3RQYXJ0ID0gcG9zdEJ1ZmZlckV2ZW50UGFydHNUb3RhbD8uWzBdPy5sYXN0UGFydDtcblxuICBmb3IgKGxldCBpID0gMDsgaSA8IHBvc3RCdWZmZXJFdmVudFBhcnRzVG90YWwubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAocHJlRXZlbnRJZCkge1xuICAgICAgcG9zdEJ1ZmZlckV2ZW50UGFydHNUb3RhbFtpXS5sYXN0UGFydCA9XG4gICAgICAgIGFjdHVhbEV2ZW50UHJldmlvdXNMYXN0UGFydCArIHBvc3RCdWZmZXJBZnRlckV2ZW50UGFydHNTb3J0ZWQubGVuZ3RoO1xuICAgIH0gZWxzZSB7XG4gICAgICBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsW2ldLnBhcnQgPSBpICsgMTtcbiAgICAgIHBvc3RCdWZmZXJFdmVudFBhcnRzVG90YWxbaV0ubGFzdFBhcnQgPSBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsLmxlbmd0aDtcbiAgICB9XG4gIH1cblxuICBmb3IgKGxldCBpID0gMDsgaSA8IHBvc3RCdWZmZXJBZnRlckV2ZW50UGFydHNTb3J0ZWQubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAoXG4gICAgICBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsPy5bcG9zdEJ1ZmZlckFjdHVhbEV2ZW50UGFydHNTb3J0ZWQ/Lmxlbmd0aCArIGldXG4gICAgKSB7XG4gICAgICBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsW1xuICAgICAgICBwb3N0QnVmZmVyQWN0dWFsRXZlbnRQYXJ0c1NvcnRlZD8ubGVuZ3RoICsgaVxuICAgICAgXS5wYXJ0ID0gYWN0dWFsRXZlbnRQcmV2aW91c0xhc3RQYXJ0ICsgaSArIDE7XG4gICAgfVxuICB9XG5cbiAgY29uc3QgcHJlRXZlbnRQYXJ0cyA9IGV2ZW50UGFydHMuZmlsdGVyKChlKSA9PiBlLmV2ZW50SWQgPT09IHByZUV2ZW50SWQpO1xuICBjb25zdCBwcmVCdWZmZXJFdmVudFBhcnRzID0gcHJlRXZlbnRQYXJ0cz8ubWFwKChlKSA9PiAoe1xuICAgIC4uLmUsXG4gICAgZ3JvdXBJZDogcG9zdEJ1ZmZlckdyb3VwSWQsXG4gICAgbGFzdFBhcnQ6XG4gICAgICBhY3R1YWxFdmVudFByZXZpb3VzTGFzdFBhcnQgKyBwb3N0QnVmZmVyQWZ0ZXJFdmVudFBhcnRzU29ydGVkLmxlbmd0aCxcbiAgfSkpO1xuICBjb25zdCBjb25jYXRlbmF0ZWRWYWx1ZXMgPSBwcmVCdWZmZXJFdmVudFBhcnRzLmNvbmNhdChcbiAgICBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsXG4gICk7XG4gIGNvbmNhdGVuYXRlZFZhbHVlcy5mb3JFYWNoKChlKSA9PlxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZS5pZCxcbiAgICAgIGUuZ3JvdXBJZCxcbiAgICAgIGUuZXZlbnRJZCxcbiAgICAgIGUucGFydCxcbiAgICAgIGUubGFzdFBhcnQsXG4gICAgICBlLnN0YXJ0RGF0ZSxcbiAgICAgIGUuZW5kRGF0ZSxcbiAgICAgIGU/LmZvckV2ZW50SWQsXG4gICAgICBgZS5pZCwgZS5ncm91cElkLCBlLmV2ZW50SWQsIGUucGFydCwgZS5sYXN0UGFydCwgZS5zdGFydERhdGUsIGUuZW5kRGF0ZSwgZT8uZm9yRXZlbnRJZCwgIGluc2lkZSBtb2RpZnlFdmVudFBhcnRzRm9yU2luZ2x1bGFyUG9zdEJ1ZmZlclRpbWVgXG4gICAgKVxuICApO1xuICByZXR1cm4gY29uY2F0ZW5hdGVkVmFsdWVzO1xufTtcblxuZXhwb3J0IGNvbnN0IGZvcm1hdEV2ZW50VHlwZVRvUGxhbm5lckV2ZW50ID0gKFxuICBldmVudDogSW5pdGlhbEV2ZW50UGFydFR5cGVQbHVzLFxuICB1c2VyUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlLFxuICB3b3JrVGltZXM6IFdvcmtUaW1lVHlwZVtdLFxuICBob3N0VGltZXpvbmU6IHN0cmluZ1xuKTogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9PiB7XG4gIGNvbnN0IHtcbiAgICBhbGxEYXksXG4gICAgcGFydCxcbiAgICBmb3JFdmVudElkLFxuICAgIGdyb3VwSWQsXG4gICAgZXZlbnRJZCxcbiAgICBpc0JyZWFrLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICBpc01lZXRpbmcsXG4gICAgaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICBpc1Bvc3RFdmVudCxcbiAgICBpc1ByZUV2ZW50LFxuICAgIG1vZGlmaWFibGUsXG4gICAgbmVnYXRpdmVJbXBhY3REYXlPZldlZWssXG4gICAgbmVnYXRpdmVJbXBhY3RTY29yZSxcbiAgICBuZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWssXG4gICAgcG9zaXRpdmVJbXBhY3RTY29yZSxcbiAgICBwb3NpdGl2ZUltcGFjdFRpbWUsXG4gICAgcHJlZmVycmVkRGF5T2ZXZWVrLFxuICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZSxcbiAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZSxcbiAgICBwcmVmZXJyZWRUaW1lLFxuICAgIHByaW9yaXR5LFxuICAgIHN0YXJ0RGF0ZSxcbiAgICBlbmREYXRlLFxuICAgIHRhc2tJZCxcbiAgICB1c2VySWQsXG4gICAgd2Vla2x5VGFza0xpc3QsXG4gICAgZGFpbHlUYXNrTGlzdCxcbiAgICBoYXJkRGVhZGxpbmUsXG4gICAgc29mdERlYWRsaW5lLFxuICAgIHJlY3VycmluZ0V2ZW50SWQsXG4gICAgbGFzdFBhcnQsXG4gICAgcHJlZmVycmVkVGltZVJhbmdlcyxcbiAgICBob3N0SWQsXG4gICAgbWVldGluZ0lkLFxuICAgIHRpbWV6b25lLFxuICAgIG1lZXRpbmdQYXJ0LFxuICAgIG1lZXRpbmdMYXN0UGFydCxcbiAgfSA9IGV2ZW50O1xuXG4gIGlmIChhbGxEYXkpIHtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIGNvbnN0IHRvdGFsV29ya2luZ0hvdXJzID0gY29udmVydFRvVG90YWxXb3JraW5nSG91cnNGb3JJbnRlcm5hbEF0dGVuZGVlKFxuICAgIHVzZXJQcmVmZXJlbmNlLFxuICAgIGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmZvcm1hdCgpLFxuICAgIGhvc3RUaW1lem9uZVxuICApO1xuXG4gIGNvbnN0IHVzZXI6IFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlID0ge1xuICAgIGlkOiBldmVudC51c2VySWQsXG4gICAgbWF4V29ya0xvYWRQZXJjZW50OiB1c2VyUHJlZmVyZW5jZS5tYXhXb3JrTG9hZFBlcmNlbnQsXG4gICAgYmFja1RvQmFja01lZXRpbmdzOiB1c2VyUHJlZmVyZW5jZS5iYWNrVG9CYWNrTWVldGluZ3MsXG4gICAgbWF4TnVtYmVyT2ZNZWV0aW5nczogdXNlclByZWZlcmVuY2UubWF4TnVtYmVyT2ZNZWV0aW5ncyxcbiAgICBtaW5OdW1iZXJPZkJyZWFrczogdXNlclByZWZlcmVuY2UubWluTnVtYmVyT2ZCcmVha3MsXG4gICAgd29ya1RpbWVzLFxuICAgIGhvc3RJZCxcbiAgfTtcblxuICBjb25zdCBhZGp1c3RlZFBvc2l0aXZlSW1wYWN0VGltZSA9XG4gICAgKHBvc2l0aXZlSW1wYWN0VGltZSAmJlxuICAgICAgKGRheWpzKHN0YXJ0RGF0ZT8uc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5ob3VyKHBhcnNlSW50KHBvc2l0aXZlSW1wYWN0VGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KHBvc2l0aXZlSW1wYWN0VGltZS5zbGljZSgzKSwgMTApKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUpKSB8fFxuICAgIHVuZGVmaW5lZDtcblxuICBjb25zdCBhZGp1c3RlZE5lZ2F0aXZlSW1wYWN0VGltZSA9XG4gICAgKG5lZ2F0aXZlSW1wYWN0VGltZSAmJlxuICAgICAgKGRheWpzKHN0YXJ0RGF0ZT8uc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5ob3VyKHBhcnNlSW50KG5lZ2F0aXZlSW1wYWN0VGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KG5lZ2F0aXZlSW1wYWN0VGltZS5zbGljZSgzKSwgMTApKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUpKSB8fFxuICAgIHVuZGVmaW5lZDtcblxuICBjb25zdCBhZGp1c3RlZFByZWZlcnJlZFRpbWUgPVxuICAgIChwcmVmZXJyZWRUaW1lICYmXG4gICAgICAoZGF5anMoc3RhcnREYXRlPy5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQocHJlZmVycmVkVGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KHByZWZlcnJlZFRpbWUuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lKSkgfHxcbiAgICB1bmRlZmluZWQ7XG5cbiAgY29uc3QgYWRqdXN0ZWRQcmVmZXJyZWRTdGFydFRpbWVSYW5nZSA9XG4gICAgKHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlICYmXG4gICAgICAoZGF5anMoc3RhcnREYXRlPy5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQocHJlZmVycmVkU3RhcnRUaW1lUmFuZ2Uuc2xpY2UoMCwgMiksIDEwKSlcbiAgICAgICAgLm1pbnV0ZShwYXJzZUludChwcmVmZXJyZWRTdGFydFRpbWVSYW5nZS5zbGljZSgzKSwgMTApKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUpKSB8fFxuICAgIHVuZGVmaW5lZDtcblxuICBjb25zdCBhZGp1c3RlZFByZWZlcnJlZEVuZFRpbWVSYW5nZSA9XG4gICAgKHByZWZlcnJlZEVuZFRpbWVSYW5nZSAmJlxuICAgICAgKGRheWpzKHN0YXJ0RGF0ZT8uc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5ob3VyKHBhcnNlSW50KHByZWZlcnJlZEVuZFRpbWVSYW5nZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KHByZWZlcnJlZEVuZFRpbWVSYW5nZS5zbGljZSgzKSwgMTApKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUpKSB8fFxuICAgIHVuZGVmaW5lZDtcblxuICBjb25zdCBhZGp1c3RlZFByZWZlcnJlZFRpbWVSYW5nZXMgPVxuICAgIHByZWZlcnJlZFRpbWVSYW5nZXM/Lm1hcCgoZSkgPT4gKHtcbiAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmc/LltlPy5kYXlPZldlZWtdID8/IG51bGwsXG4gICAgICBzdGFydFRpbWU6IGRheWpzKHN0YXJ0RGF0ZT8uc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5ob3VyKHBhcnNlSW50KGU/LnN0YXJ0VGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KGU/LnN0YXJ0VGltZS5zbGljZSgzKSwgMTApKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICBlbmRUaW1lOiBkYXlqcyhzdGFydERhdGU/LnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuaG91cihwYXJzZUludChlPy5lbmRUaW1lLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQoZT8uZW5kVGltZS5zbGljZSgzKSwgMTApKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICBldmVudElkLFxuICAgICAgdXNlcklkLFxuICAgICAgaG9zdElkLFxuICAgIH0pKSA/PyBudWxsO1xuXG4gIGNvbnN0IGV2ZW50UGxhbm5lclJlcXVlc3RCb2R5OiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlID0ge1xuICAgIGdyb3VwSWQsXG4gICAgZXZlbnRJZCxcbiAgICBwYXJ0LFxuICAgIGxhc3RQYXJ0LFxuICAgIG1lZXRpbmdQYXJ0LFxuICAgIG1lZXRpbmdMYXN0UGFydCxcbiAgICBzdGFydERhdGU6IGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tOnNzJyksXG4gICAgZW5kRGF0ZTogZGF5anMoZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tOnNzJyksXG4gICAgdGFza0lkLFxuICAgIGhhcmREZWFkbGluZSxcbiAgICBzb2Z0RGVhZGxpbmUsXG4gICAgdXNlcklkLFxuICAgIHVzZXIsXG4gICAgcHJpb3JpdHksXG4gICAgaXNQcmVFdmVudCxcbiAgICBpc1Bvc3RFdmVudCxcbiAgICBmb3JFdmVudElkLFxuICAgIHBvc2l0aXZlSW1wYWN0U2NvcmUsXG4gICAgbmVnYXRpdmVJbXBhY3RTY29yZSxcbiAgICBwb3NpdGl2ZUltcGFjdERheU9mV2VlazpcbiAgICAgIGRheU9mV2Vla0ludFRvU3RyaW5nW3Bvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrXSA/PyBudWxsLFxuICAgIHBvc2l0aXZlSW1wYWN0VGltZTogYWRqdXN0ZWRQb3NpdGl2ZUltcGFjdFRpbWUsXG4gICAgbmVnYXRpdmVJbXBhY3REYXlPZldlZWs6XG4gICAgICBkYXlPZldlZWtJbnRUb1N0cmluZ1tuZWdhdGl2ZUltcGFjdERheU9mV2Vla10gPz8gbnVsbCxcbiAgICBuZWdhdGl2ZUltcGFjdFRpbWU6IGFkanVzdGVkTmVnYXRpdmVJbXBhY3RUaW1lLFxuICAgIG1vZGlmaWFibGUsXG4gICAgcHJlZmVycmVkRGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1twcmVmZXJyZWREYXlPZldlZWtdID8/IG51bGwsXG4gICAgcHJlZmVycmVkVGltZTogYWRqdXN0ZWRQcmVmZXJyZWRUaW1lLFxuICAgIGlzTWVldGluZyxcbiAgICBpc0V4dGVybmFsTWVldGluZyxcbiAgICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGUsXG4gICAgaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICBkYWlseVRhc2tMaXN0LFxuICAgIHdlZWtseVRhc2tMaXN0LFxuICAgIGdhcDogaXNCcmVhayxcbiAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZTogYWRqdXN0ZWRQcmVmZXJyZWRTdGFydFRpbWVSYW5nZSxcbiAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2U6IGFkanVzdGVkUHJlZmVycmVkRW5kVGltZVJhbmdlLFxuICAgIHRvdGFsV29ya2luZ0hvdXJzLFxuICAgIHJlY3VycmluZ0V2ZW50SWQsXG4gICAgaG9zdElkLFxuICAgIG1lZXRpbmdJZCxcbiAgICBldmVudDoge1xuICAgICAgaWQ6IGV2ZW50SWQsXG4gICAgICB1c2VySWQsXG4gICAgICBob3N0SWQsXG4gICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzOiBhZGp1c3RlZFByZWZlcnJlZFRpbWVSYW5nZXMgPz8gbnVsbCxcbiAgICAgIGV2ZW50VHlwZTogZXZlbnQuZXZlbnRUeXBlLFxuICAgIH0sXG4gIH07XG4gIHJldHVybiBldmVudFBsYW5uZXJSZXF1ZXN0Qm9keTtcbn07XG5cbmV4cG9ydCBjb25zdCBmb3JtYXRFdmVudFR5cGVUb1BsYW5uZXJFdmVudEZvckV4dGVybmFsQXR0ZW5kZWUgPSAoXG4gIGV2ZW50OiBJbml0aWFsRXZlbnRQYXJ0VHlwZVBsdXMsXG4gIHdvcmtUaW1lczogV29ya1RpbWVUeXBlW10sXG4gIGF0dGVuZGVlRXZlbnRzOiBFdmVudFBsdXNUeXBlW10sXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nXG4pOiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlID0+IHtcbiAgY29uc3Qge1xuICAgIGFsbERheSxcbiAgICBwYXJ0LFxuICAgIGZvckV2ZW50SWQsXG4gICAgZ3JvdXBJZCxcbiAgICBldmVudElkLFxuICAgIGlzQnJlYWssXG4gICAgaXNFeHRlcm5hbE1lZXRpbmcsXG4gICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlLFxuICAgIGlzTWVldGluZyxcbiAgICBpc01lZXRpbmdNb2RpZmlhYmxlLFxuICAgIGlzUG9zdEV2ZW50LFxuICAgIGlzUHJlRXZlbnQsXG4gICAgbW9kaWZpYWJsZSxcbiAgICBuZWdhdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICBuZWdhdGl2ZUltcGFjdFNjb3JlLFxuICAgIG5lZ2F0aXZlSW1wYWN0VGltZSxcbiAgICBwb3NpdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICBwb3NpdGl2ZUltcGFjdFNjb3JlLFxuICAgIHBvc2l0aXZlSW1wYWN0VGltZSxcbiAgICBwcmVmZXJyZWREYXlPZldlZWssXG4gICAgcHJlZmVycmVkRW5kVGltZVJhbmdlLFxuICAgIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlLFxuICAgIHByZWZlcnJlZFRpbWUsXG4gICAgcHJpb3JpdHksXG4gICAgc3RhcnREYXRlLFxuICAgIGVuZERhdGUsXG4gICAgdGFza0lkLFxuICAgIHVzZXJJZCxcbiAgICB3ZWVrbHlUYXNrTGlzdCxcbiAgICBkYWlseVRhc2tMaXN0LFxuICAgIGhhcmREZWFkbGluZSxcbiAgICBzb2Z0RGVhZGxpbmUsXG4gICAgcmVjdXJyaW5nRXZlbnRJZCxcbiAgICBsYXN0UGFydCxcbiAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzLFxuICAgIGhvc3RJZCxcbiAgICBtZWV0aW5nSWQsXG4gICAgdGltZXpvbmUsXG4gICAgbWVldGluZ1BhcnQsXG4gICAgbWVldGluZ0xhc3RQYXJ0LFxuICB9ID0gZXZlbnQ7XG5cbiAgaWYgKGFsbERheSkge1xuICAgIHJldHVybiBudWxsO1xuICB9XG5cbiAgY29uc3QgdG90YWxXb3JraW5nSG91cnMgPSBjb252ZXJ0VG9Ub3RhbFdvcmtpbmdIb3Vyc0ZvckV4dGVybmFsQXR0ZW5kZWUoXG4gICAgYXR0ZW5kZWVFdmVudHMsXG4gICAgZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuZm9ybWF0KCksXG4gICAgaG9zdFRpbWV6b25lLFxuICAgIGV2ZW50Py50aW1lem9uZVxuICApO1xuXG4gIGNvbnN0IHVzZXI6IFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlID0ge1xuICAgIGlkOiBldmVudC51c2VySWQsXG4gICAgbWF4V29ya0xvYWRQZXJjZW50OiAxMDAsXG4gICAgYmFja1RvQmFja01lZXRpbmdzOiBmYWxzZSxcbiAgICBtYXhOdW1iZXJPZk1lZXRpbmdzOiA5OSxcbiAgICBtaW5OdW1iZXJPZkJyZWFrczogMCxcbiAgICB3b3JrVGltZXMsXG4gICAgaG9zdElkLFxuICB9O1xuXG4gIGNvbnN0IGFkanVzdGVkUG9zaXRpdmVJbXBhY3RUaW1lID1cbiAgICAocG9zaXRpdmVJbXBhY3RUaW1lICYmXG4gICAgICAoZGF5anMoKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5ob3VyKHBhcnNlSW50KHBvc2l0aXZlSW1wYWN0VGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KHBvc2l0aXZlSW1wYWN0VGltZS5zbGljZSgzKSwgMTApKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUpKSB8fFxuICAgIHVuZGVmaW5lZDtcblxuICBjb25zdCBhZGp1c3RlZE5lZ2F0aXZlSW1wYWN0VGltZSA9XG4gICAgKG5lZ2F0aXZlSW1wYWN0VGltZSAmJlxuICAgICAgKGRheWpzKClcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuaG91cihwYXJzZUludChuZWdhdGl2ZUltcGFjdFRpbWUuc2xpY2UoMCwgMiksIDEwKSlcbiAgICAgICAgLm1pbnV0ZShwYXJzZUludChuZWdhdGl2ZUltcGFjdFRpbWUuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lKSkgfHxcbiAgICB1bmRlZmluZWQ7XG5cbiAgY29uc3QgYWRqdXN0ZWRQcmVmZXJyZWRUaW1lID1cbiAgICAocHJlZmVycmVkVGltZSAmJlxuICAgICAgKGRheWpzKClcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuaG91cihwYXJzZUludChwcmVmZXJyZWRUaW1lLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQocHJlZmVycmVkVGltZS5zbGljZSgzKSwgMTApKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUpKSB8fFxuICAgIHVuZGVmaW5lZDtcblxuICBjb25zdCBhZGp1c3RlZFByZWZlcnJlZFN0YXJ0VGltZVJhbmdlID1cbiAgICAocHJlZmVycmVkU3RhcnRUaW1lUmFuZ2UgJiZcbiAgICAgIChkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQocHJlZmVycmVkU3RhcnRUaW1lUmFuZ2Uuc2xpY2UoMCwgMiksIDEwKSlcbiAgICAgICAgLm1pbnV0ZShwYXJzZUludChwcmVmZXJyZWRTdGFydFRpbWVSYW5nZS5zbGljZSgzKSwgMTApKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUpKSB8fFxuICAgIHVuZGVmaW5lZDtcblxuICBjb25zdCBhZGp1c3RlZFByZWZlcnJlZEVuZFRpbWVSYW5nZSA9XG4gICAgKHByZWZlcnJlZEVuZFRpbWVSYW5nZSAmJlxuICAgICAgKGRheWpzKClcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuaG91cihwYXJzZUludChwcmVmZXJyZWRFbmRUaW1lUmFuZ2Uuc2xpY2UoMCwgMiksIDEwKSlcbiAgICAgICAgLm1pbnV0ZShwYXJzZUludChwcmVmZXJyZWRFbmRUaW1lUmFuZ2Uuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lKSkgfHxcbiAgICB1bmRlZmluZWQ7XG5cbiAgY29uc3QgYWRqdXN0ZWRQcmVmZXJyZWRUaW1lUmFuZ2VzID1cbiAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzPy5tYXAoKGUpID0+ICh7XG4gICAgICBkYXlPZldlZWs6IGRheU9mV2Vla0ludFRvU3RyaW5nPy5bZT8uZGF5T2ZXZWVrXSA/PyBudWxsLFxuICAgICAgc3RhcnRUaW1lOiBkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQoZT8uc3RhcnRUaW1lLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQoZT8uc3RhcnRUaW1lLnNsaWNlKDMpLCAxMCkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgIGVuZFRpbWU6IGRheWpzKClcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuaG91cihwYXJzZUludChlPy5lbmRUaW1lLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQoZT8uZW5kVGltZS5zbGljZSgzKSwgMTApKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICBldmVudElkLFxuICAgICAgdXNlcklkLFxuICAgICAgaG9zdElkLFxuICAgIH0pKSA/PyBudWxsO1xuXG4gIGNvbnN0IGV2ZW50UGxhbm5lclJlcXVlc3RCb2R5OiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlID0ge1xuICAgIGdyb3VwSWQsXG4gICAgZXZlbnRJZCxcbiAgICBwYXJ0LFxuICAgIGxhc3RQYXJ0LFxuICAgIG1lZXRpbmdQYXJ0LFxuICAgIG1lZXRpbmdMYXN0UGFydCxcbiAgICBzdGFydERhdGU6IGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tOnNzJyksXG4gICAgZW5kRGF0ZTogZGF5anMoZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tOnNzJyksXG4gICAgdGFza0lkLFxuICAgIGhhcmREZWFkbGluZSxcbiAgICBzb2Z0RGVhZGxpbmUsXG4gICAgdXNlcklkLFxuICAgIHVzZXIsXG4gICAgcHJpb3JpdHksXG4gICAgaXNQcmVFdmVudCxcbiAgICBpc1Bvc3RFdmVudCxcbiAgICBmb3JFdmVudElkLFxuICAgIHBvc2l0aXZlSW1wYWN0U2NvcmUsXG4gICAgbmVnYXRpdmVJbXBhY3RTY29yZSxcbiAgICBwb3NpdGl2ZUltcGFjdERheU9mV2VlazpcbiAgICAgIGRheU9mV2Vla0ludFRvU3RyaW5nW3Bvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrXSA/PyBudWxsLFxuICAgIHBvc2l0aXZlSW1wYWN0VGltZTogYWRqdXN0ZWRQb3NpdGl2ZUltcGFjdFRpbWUsXG4gICAgbmVnYXRpdmVJbXBhY3REYXlPZldlZWs6XG4gICAgICBkYXlPZldlZWtJbnRUb1N0cmluZ1tuZWdhdGl2ZUltcGFjdERheU9mV2Vla10gPz8gbnVsbCxcbiAgICBuZWdhdGl2ZUltcGFjdFRpbWU6IGFkanVzdGVkTmVnYXRpdmVJbXBhY3RUaW1lLFxuICAgIG1vZGlmaWFibGUsXG4gICAgcHJlZmVycmVkRGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1twcmVmZXJyZWREYXlPZldlZWtdID8/IG51bGwsXG4gICAgcHJlZmVycmVkVGltZTogYWRqdXN0ZWRQcmVmZXJyZWRUaW1lLFxuICAgIGlzTWVldGluZyxcbiAgICBpc0V4dGVybmFsTWVldGluZyxcbiAgICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGUsXG4gICAgaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICBkYWlseVRhc2tMaXN0LFxuICAgIHdlZWtseVRhc2tMaXN0LFxuICAgIGdhcDogaXNCcmVhayxcbiAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZTogYWRqdXN0ZWRQcmVmZXJyZWRTdGFydFRpbWVSYW5nZSxcbiAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2U6IGFkanVzdGVkUHJlZmVycmVkRW5kVGltZVJhbmdlLFxuICAgIHRvdGFsV29ya2luZ0hvdXJzLFxuICAgIHJlY3VycmluZ0V2ZW50SWQsXG4gICAgaG9zdElkLFxuICAgIG1lZXRpbmdJZCxcbiAgICBldmVudDoge1xuICAgICAgaWQ6IGV2ZW50SWQsXG4gICAgICB1c2VySWQsXG4gICAgICBob3N0SWQsXG4gICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzOiBhZGp1c3RlZFByZWZlcnJlZFRpbWVSYW5nZXMgPz8gbnVsbCxcbiAgICAgIGV2ZW50VHlwZTogZXZlbnQuZXZlbnRUeXBlLFxuICAgIH0sXG4gIH07XG4gIHJldHVybiBldmVudFBsYW5uZXJSZXF1ZXN0Qm9keTtcbn07XG5cbmV4cG9ydCBjb25zdCBjb252ZXJ0TWVldGluZ1BsdXNUeXBlVG9FdmVudFBsdXNUeXBlID0gKFxuICBldmVudDogRXZlbnRNZWV0aW5nUGx1c1R5cGVcbik6IEV2ZW50UGx1c1R5cGUgPT4ge1xuICBjb25zdCBuZXdFdmVudDogRXZlbnRQbHVzVHlwZSA9IHtcbiAgICAuLi5ldmVudCxcbiAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzOlxuICAgICAgZXZlbnQ/LnByZWZlcnJlZFRpbWVSYW5nZXM/Lm1hcCgocHQpID0+ICh7XG4gICAgICAgIGlkOiBwdC5pZCxcbiAgICAgICAgZXZlbnRJZDogZXZlbnQuaWQsXG4gICAgICAgIGRheU9mV2VlazogcHQ/LmRheU9mV2VlayxcbiAgICAgICAgc3RhcnRUaW1lOiBwdD8uc3RhcnRUaW1lLFxuICAgICAgICBlbmRUaW1lOiBwdD8uZW5kVGltZSxcbiAgICAgICAgdXBkYXRlZEF0OiBwdD8udXBkYXRlZEF0LFxuICAgICAgICBjcmVhdGVkRGF0ZTogcHQ/LmNyZWF0ZWREYXRlLFxuICAgICAgICB1c2VySWQ6IGV2ZW50Py51c2VySWQsXG4gICAgICB9KSkgfHwgbnVsbCxcbiAgfTtcblxuICByZXR1cm4gbmV3RXZlbnQ7XG59O1xuXG5leHBvcnQgY29uc3Qgc2V0UHJlZmVycmVkVGltZUZvclVuTW9kaWZpYWJsZUV2ZW50ID0gKFxuICBldmVudDogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZSxcbiAgdGltZXpvbmU6IHN0cmluZ1xuKTogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9PiB7XG4gIGlmICghZXZlbnQ/Lm1vZGlmaWFibGUpIHtcbiAgICBpZiAoIWV2ZW50Py5wcmVmZXJyZWREYXlPZldlZWsgJiYgIWV2ZW50Py5wcmVmZXJyZWRUaW1lKSB7XG4gICAgICBjb25zdCBuZXdFdmVudCA9IHtcbiAgICAgICAgLi4uZXZlbnQsXG4gICAgICAgIHByZWZlcnJlZERheU9mV2VlazpcbiAgICAgICAgICBkYXlPZldlZWtJbnRUb1N0cmluZ1tcbiAgICAgICAgICAgIGdldElTT0RheShcbiAgICAgICAgICAgICAgZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICAgICAgICAgICApXG4gICAgICAgICAgXSxcbiAgICAgICAgcHJlZmVycmVkVGltZTogZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgfTtcbiAgICAgIHJldHVybiBuZXdFdmVudDtcbiAgICB9XG4gICAgcmV0dXJuIGV2ZW50O1xuICB9XG4gIHJldHVybiBldmVudDtcbn07XG5cbmV4cG9ydCBjb25zdCBsaXN0RXZlbnRzV2l0aElkcyA9IGFzeW5jIChpZHM6IHN0cmluZ1tdKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdsaXN0RXZlbnRzV2l0aElkcyc7XG5cbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICBxdWVyeSBsaXN0RXZlbnRzV2l0aElkcygkaWRzOiBbU3RyaW5nIV0hKSB7XG4gICAgICBFdmVudCh3aGVyZToge2lkOiB7X2luOiAkaWRzfX0pIHtcbiAgICAgICAgYWxsRGF5XG4gICAgICAgIGFueW9uZUNhbkFkZFNlbGZcbiAgICAgICAgYXR0YWNobWVudHNcbiAgICAgICAgYXR0ZW5kZWVzT21pdHRlZFxuICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICBjb2xvcklkXG4gICAgICAgIGNvbmZlcmVuY2VJZFxuICAgICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICAgIGNvcHlDYXRlZ29yaWVzXG4gICAgICAgIGNvcHlEdXJhdGlvblxuICAgICAgICBjb3B5SXNCcmVha1xuICAgICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgY29weUlzTWVldGluZ1xuICAgICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgICBjb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgICAgY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgIGNyZWF0b3JcbiAgICAgICAgZGFpbHlUYXNrTGlzdFxuICAgICAgICBkZWxldGVkXG4gICAgICAgIGR1cmF0aW9uXG4gICAgICAgIGVuZERhdGVcbiAgICAgICAgZW5kVGltZVVuc3BlY2lmaWVkXG4gICAgICAgIGV2ZW50SWRcbiAgICAgICAgZXZlbnRUeXBlXG4gICAgICAgIGV4dGVuZGVkUHJvcGVydGllc1xuICAgICAgICBmb2xsb3dVcEV2ZW50SWRcbiAgICAgICAgZm9yRXZlbnRJZFxuICAgICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzXG4gICAgICAgIGd1ZXN0c0Nhbk1vZGlmeVxuICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0c1xuICAgICAgICBoYW5nb3V0TGlua1xuICAgICAgICBoYXJkRGVhZGxpbmVcbiAgICAgICAgaHRtbExpbmtcbiAgICAgICAgaUNhbFVJRFxuICAgICAgICBpZFxuICAgICAgICBpc0JyZWFrXG4gICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICBpc0ZvbGxvd1VwXG4gICAgICAgIGlzTWVldGluZ1xuICAgICAgICBpc01lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgIGlzUG9zdEV2ZW50XG4gICAgICAgIGlzUHJlRXZlbnRcbiAgICAgICAgbGlua3NcbiAgICAgICAgbG9jYXRpb25cbiAgICAgICAgbG9ja2VkXG4gICAgICAgIG1heEF0dGVuZGVlc1xuICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgbWV0aG9kXG4gICAgICAgIG1vZGlmaWFibGVcbiAgICAgICAgbmVnYXRpdmVJbXBhY3REYXlPZldlZWtcbiAgICAgICAgbmVnYXRpdmVJbXBhY3RTY29yZVxuICAgICAgICBuZWdhdGl2ZUltcGFjdFRpbWVcbiAgICAgICAgbm90ZXNcbiAgICAgICAgb3JnYW5pemVyXG4gICAgICAgIG9yaWdpbmFsQWxsRGF5XG4gICAgICAgIG9yaWdpbmFsU3RhcnREYXRlXG4gICAgICAgIG9yaWdpbmFsVGltZXpvbmVcbiAgICAgICAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWtcbiAgICAgICAgcG9zaXRpdmVJbXBhY3RTY29yZVxuICAgICAgICBwb3NpdGl2ZUltcGFjdFRpbWVcbiAgICAgICAgcG9zdEV2ZW50SWRcbiAgICAgICAgcHJlRXZlbnRJZFxuICAgICAgICBwcmVmZXJyZWREYXlPZldlZWtcbiAgICAgICAgcHJlZmVycmVkRW5kVGltZVJhbmdlXG4gICAgICAgIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlXG4gICAgICAgIHByZWZlcnJlZFRpbWVcbiAgICAgICAgcHJpb3JpdHlcbiAgICAgICAgcHJpdmF0ZUNvcHlcbiAgICAgICAgcmVjdXJyZW5jZVxuICAgICAgICByZWN1cnJlbmNlUnVsZVxuICAgICAgICByZWN1cnJpbmdFdmVudElkXG4gICAgICAgIHNlbmRVcGRhdGVzXG4gICAgICAgIHNvZnREZWFkbGluZVxuICAgICAgICBzb3VyY2VcbiAgICAgICAgc3RhcnREYXRlXG4gICAgICAgIHN0YXR1c1xuICAgICAgICBzdW1tYXJ5XG4gICAgICAgIHRhc2tJZFxuICAgICAgICB0YXNrVHlwZVxuICAgICAgICB0aW1lQmxvY2tpbmdcbiAgICAgICAgdGltZXpvbmVcbiAgICAgICAgdGl0bGVcbiAgICAgICAgdHJhbnNwYXJlbmN5XG4gICAgICAgIHVubGlua1xuICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgdXNlRGVmYXVsdEFsYXJtc1xuICAgICAgICB1c2VySWRcbiAgICAgICAgdXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5XG4gICAgICAgIHVzZXJNb2RpZmllZENhdGVnb3JpZXNcbiAgICAgICAgdXNlck1vZGlmaWVkRHVyYXRpb25cbiAgICAgICAgdXNlck1vZGlmaWVkSXNCcmVha1xuICAgICAgICB1c2VyTW9kaWZpZWRJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICB1c2VyTW9kaWZpZWRJc01lZXRpbmdcbiAgICAgICAgdXNlck1vZGlmaWVkTW9kaWZpYWJsZVxuICAgICAgICB1c2VyTW9kaWZpZWRQcmlvcml0eUxldmVsXG4gICAgICAgIHVzZXJNb2RpZmllZFJlbWluZGVyc1xuICAgICAgICB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmdcbiAgICAgICAgdXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2VcbiAgICAgICAgdmlzaWJpbGl0eVxuICAgICAgICB3ZWVrbHlUYXNrTGlzdFxuICAgICAgICBieVdlZWtEYXlcbiAgICAgICAgbG9jYWxTeW5jZWRcbiAgICAgICAgdXNlck1vZGlmaWVkQ29sb3JcbiAgICAgICAgY29weUNvbG9yXG4gICAgICB9XG4gICAgfSAgICBcbiAgICBgO1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgRXZlbnQ6IEV2ZW50VHlwZVtdIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICBpZHMsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uRXZlbnQ7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBsaXN0IGlkcyB3aXRoIGlkcycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdGFnRXZlbnRzRm9yRGFpbHlPcldlZWtseVRhc2sgPSBhc3luYyAoXG4gIGV2ZW50czogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZVtdXG4pOiBQcm9taXNlPEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSB8IG51bGw+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBmaWx0ZXJlZEV2ZW50cyA9IGV2ZW50cy5maWx0ZXIoKGUpID0+IGUucmVjdXJyaW5nRXZlbnRJZCk7XG4gICAgaWYgKGZpbHRlcmVkRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICBjb25zdCBvcmlnaW5hbEV2ZW50cyA9IGF3YWl0IGxpc3RFdmVudHNXaXRoSWRzKFxuICAgICAgICBfLnVuaXEoZmlsdGVyZWRFdmVudHMubWFwKChlKSA9PiBlPy5yZWN1cnJpbmdFdmVudElkKSlcbiAgICAgICk7XG4gICAgICBpZiAob3JpZ2luYWxFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgY29uc3QgdGFnZ2VkRmlsdGVyZWRFdmVudHMgPSBmaWx0ZXJlZEV2ZW50cy5tYXAoKGUpID0+XG4gICAgICAgICAgdGFnRXZlbnRGb3JEYWlseU9yV2Vla2x5VGFzayhcbiAgICAgICAgICAgIGUsXG4gICAgICAgICAgICBvcmlnaW5hbEV2ZW50cy5maW5kKChvZSkgPT4gb2UuaWQgPT09IGUucmVjdXJyaW5nRXZlbnRJZClcbiAgICAgICAgICApXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IG5ld0V2ZW50cyA9IGV2ZW50cy5tYXAoKGUpID0+IHtcbiAgICAgICAgICBpZiAoZT8ucmVjdXJyaW5nRXZlbnRJZCkge1xuICAgICAgICAgICAgY29uc3QgdGFnZ2VkRmlsdGVyZWRFdmVudCA9IHRhZ2dlZEZpbHRlcmVkRXZlbnRzLmZpbmQoXG4gICAgICAgICAgICAgICh0ZSkgPT4gdGU/LmV2ZW50SWQgPT09IGU/LmV2ZW50SWRcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICBpZiAodGFnZ2VkRmlsdGVyZWRFdmVudD8uZXZlbnRJZCkge1xuICAgICAgICAgICAgICByZXR1cm4gdGFnZ2VkRmlsdGVyZWRFdmVudDtcbiAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgIHJldHVybiBlO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgICByZXR1cm4gZTtcbiAgICAgICAgfSk7XG4gICAgICAgIHJldHVybiBuZXdFdmVudHM7XG4gICAgICB9XG4gICAgICBjb25zb2xlLmxvZygndGFnRXZlbnRzRm9yRGFpbHlvcldlZWtseVRhc2s6IG9yaWdpbmFsRXZlbnRzIGlzIGVtcHR5Jyk7XG4gICAgICByZXR1cm4gZXZlbnRzO1xuICAgIH1cbiAgICByZXR1cm4gZXZlbnRzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdG8gdGFnIGV2ZW50cyBmb3IgZGFpbHkgb3Igd2Vla2x5IHRhc2snKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHRhZ0V2ZW50Rm9yRGFpbHlPcldlZWtseVRhc2sgPSAoXG4gIGV2ZW50VG9TdWJtaXQ6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGUsXG4gIGV2ZW50OiBFdmVudFBsdXNUeXBlXG4pID0+IHtcbiAgaWYgKCFldmVudD8uaWQpIHtcbiAgICBjb25zb2xlLmxvZygnbm8gb3JpZ2luYWwgZXZlbnQgaW5zaWRlIHRhZ0V2ZW50Rm9yRGFpbHlzT3JXZWVrbHlUYXNrJyk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICBpZiAoIWV2ZW50VG9TdWJtaXQ/LmV2ZW50SWQpIHtcbiAgICBjb25zb2xlLmxvZygnbm8gZXZlbnRUb1N1Ym1pdCBpbnNpZGUgdGFnRXZlbnRGb3JEYWlseU9yV2Vla2x5VGFzaycpO1xuICAgIHJldHVybiBudWxsO1xuICB9XG5cbiAgaWYgKGV2ZW50VG9TdWJtaXQ/LnJlY3VycmluZ0V2ZW50SWQpIHtcbiAgICBpZiAoZXZlbnQ/LndlZWtseVRhc2tMaXN0KSB7XG4gICAgICByZXR1cm4ge1xuICAgICAgICAuLi5ldmVudFRvU3VibWl0LFxuICAgICAgICB3ZWVrbHlUYXNrTGlzdDogZXZlbnQud2Vla2x5VGFza0xpc3QsXG4gICAgICB9O1xuICAgIH1cbiAgICBpZiAoZXZlbnQ/LmRhaWx5VGFza0xpc3QpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIC4uLmV2ZW50VG9TdWJtaXQsXG4gICAgICAgIGRhaWx5VGFza0xpc3Q6IGV2ZW50LmRhaWx5VGFza0xpc3QsXG4gICAgICB9O1xuICAgIH1cbiAgICByZXR1cm4gZXZlbnRUb1N1Ym1pdDtcbiAgfVxuICByZXR1cm4gZXZlbnRUb1N1Ym1pdDtcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZVVzZXJQbGFubmVyUmVxdWVzdEJvZHkgPSAoXG4gIHVzZXJQcmVmZXJlbmNlOiBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIHVzZXJJZDogc3RyaW5nLFxuICB3b3JrVGltZXM6IFdvcmtUaW1lVHlwZVtdLFxuICBob3N0SWQ6IHN0cmluZ1xuKTogVXNlclBsYW5uZXJSZXF1ZXN0Qm9keVR5cGUgPT4ge1xuICBjb25zdCB7XG4gICAgbWF4V29ya0xvYWRQZXJjZW50LFxuICAgIGJhY2tUb0JhY2tNZWV0aW5ncyxcbiAgICBtYXhOdW1iZXJPZk1lZXRpbmdzLFxuICAgIG1pbk51bWJlck9mQnJlYWtzLFxuICB9ID0gdXNlclByZWZlcmVuY2U7XG4gIGNvbnN0IHVzZXI6IFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlID0ge1xuICAgIGlkOiB1c2VySWQsXG4gICAgbWF4V29ya0xvYWRQZXJjZW50LFxuICAgIGJhY2tUb0JhY2tNZWV0aW5ncyxcbiAgICBtYXhOdW1iZXJPZk1lZXRpbmdzLFxuICAgIG1pbk51bWJlck9mQnJlYWtzLFxuICAgIHdvcmtUaW1lcyxcbiAgICBob3N0SWQsXG4gIH07XG4gIHJldHVybiB1c2VyO1xufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlVXNlclBsYW5uZXJSZXF1ZXN0Qm9keUZvckV4dGVybmFsQXR0ZW5kZWUgPSAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB3b3JrVGltZXM6IFdvcmtUaW1lVHlwZVtdLFxuICBob3N0SWQ6IHN0cmluZ1xuKTogVXNlclBsYW5uZXJSZXF1ZXN0Qm9keVR5cGUgPT4ge1xuICBjb25zdCB1c2VyOiBVc2VyUGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9IHtcbiAgICBpZDogdXNlcklkLFxuICAgIG1heFdvcmtMb2FkUGVyY2VudDogMTAwLFxuICAgIGJhY2tUb0JhY2tNZWV0aW5nczogZmFsc2UsXG4gICAgbWF4TnVtYmVyT2ZNZWV0aW5nczogOTksXG4gICAgbWluTnVtYmVyT2ZCcmVha3M6IDAsXG4gICAgd29ya1RpbWVzLFxuICAgIGhvc3RJZCxcbiAgfTtcbiAgcmV0dXJuIHVzZXI7XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0V2ZW50c0Zvck9wdGFQbGFubmVyRm9yTWFpbkhvc3QgPSBhc3luYyAoXG4gIG1haW5Ib3N0SWQ6IHN0cmluZyxcbiAgYWxsSG9zdEV2ZW50czogRXZlbnRQbHVzVHlwZVtdLFxuICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgd2luZG93RW5kRGF0ZTogc3RyaW5nLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgb2xkSG9zdEV2ZW50czogRXZlbnRQbHVzVHlwZVtdLFxuICBuZXdIb3N0QnVmZmVyVGltZXM/OiBCdWZmZXJUaW1lT2JqZWN0VHlwZVtdXG4pOiBQcm9taXNlPFJldHVybkJvZHlGb3JIb3N0Rm9yT3B0YXBsYW5uZXJQcmVwVHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG5ld0J1ZmZlclRpbWVBcnJheTogRXZlbnRQbHVzVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IG5ld0hvc3RCdWZmZXJUaW1lIG9mIG5ld0hvc3RCdWZmZXJUaW1lcykge1xuICAgICAgaWYgKG5ld0hvc3RCdWZmZXJUaW1lPy5iZWZvcmVFdmVudD8uaWQpIHtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgbmV3SG9zdEJ1ZmZlclRpbWU/LmJlZm9yZUV2ZW50LFxuICAgICAgICAgICcgbmV3VGltZUJsb2NraW5nPy5iZWZvcmVFdmVudCdcbiAgICAgICAgKTtcbiAgICAgICAgbmV3QnVmZmVyVGltZUFycmF5LnB1c2gobmV3SG9zdEJ1ZmZlclRpbWUuYmVmb3JlRXZlbnQpO1xuICAgICAgfVxuXG4gICAgICBpZiAobmV3SG9zdEJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQ/LmlkKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIG5ld0hvc3RCdWZmZXJUaW1lPy5hZnRlckV2ZW50LFxuICAgICAgICAgICcgbmV3VGltZUJsb2NraW5nPy5hZnRlckV2ZW50J1xuICAgICAgICApO1xuICAgICAgICBuZXdCdWZmZXJUaW1lQXJyYXkucHVzaChuZXdIb3N0QnVmZmVyVGltZS5hZnRlckV2ZW50KTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBtb2RpZmllZEFsbEhvc3RFdmVudHMgPSBfLmNsb25lRGVlcChhbGxIb3N0RXZlbnRzKTtcblxuICAgIGlmIChuZXdCdWZmZXJUaW1lQXJyYXk/Lmxlbmd0aCA+IDApIHtcbiAgICAgIG1vZGlmaWVkQWxsSG9zdEV2ZW50cy5wdXNoKC4uLm5ld0J1ZmZlclRpbWVBcnJheSk7XG4gICAgfVxuXG4gICAgY29uc3QgdXNlclByZWZlcmVuY2VzID0gYXdhaXQgZ2V0VXNlclByZWZlcmVuY2VzKG1haW5Ib3N0SWQpO1xuXG4gICAgY29uc3QgZ2xvYmFsUHJpbWFyeUNhbGVuZGFyID0gYXdhaXQgZ2V0R2xvYmFsQ2FsZW5kYXIobWFpbkhvc3RJZCk7XG5cbiAgICBjb25zdCBkaWZmRGF5cyA9IGRheWpzKHdpbmRvd0VuZERhdGUuc2xpY2UoMCwgMTkpKS5kaWZmKFxuICAgICAgZGF5anMod2luZG93U3RhcnREYXRlLnNsaWNlKDAsIDE5KSksXG4gICAgICAnZGF5J1xuICAgICk7XG5cbiAgICBjb25zdCBtb2RpZmllZEFsbEV2ZW50c1dpdGhCcmVha3M6IEV2ZW50UGx1c1R5cGVbXSA9IFtdO1xuXG4gICAgY29uc3Qgc3RhcnREYXRlc0ZvckVhY2hEYXkgPSBbXTtcblxuICAgIGZvciAobGV0IGkgPSAwOyBpIDw9IGRpZmZEYXlzOyBpKyspIHtcbiAgICAgIHN0YXJ0RGF0ZXNGb3JFYWNoRGF5LnB1c2goXG4gICAgICAgIGRheWpzKHdpbmRvd1N0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuYWRkKGksICdkYXknKVxuICAgICAgICAgIC5mb3JtYXQoKVxuICAgICAgKTtcbiAgICB9XG5cbiAgICBsZXQgcGFyZW50QnJlYWtzOiBFdmVudFBsdXNUeXBlW10gPSBbXTtcblxuICAgIGNvbnN0IGJyZWFrcyA9IGF3YWl0IGdlbmVyYXRlQnJlYWtFdmVudHNGb3JEYXRlKFxuICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgbWFpbkhvc3RJZCxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICBob3N0VGltZXpvbmUsXG4gICAgICBnbG9iYWxQcmltYXJ5Q2FsZW5kYXI/LmlkXG4gICAgKTtcblxuICAgIGJyZWFrcy5mb3JFYWNoKChiKSA9PiBjb25zb2xlLmxvZyhiLCAnIGdlbmVyYXRlZEJyZWFrcycpKTtcblxuICAgIGlmIChicmVha3M/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGNvbnN0IGFsbEV2ZW50c1dpdGhEdXBsaWNhdGVGcmVlQnJlYWtzID0gXy5kaWZmZXJlbmNlQnkoXG4gICAgICAgIG1vZGlmaWVkQWxsSG9zdEV2ZW50cyxcbiAgICAgICAgYnJlYWtzLFxuICAgICAgICAnaWQnXG4gICAgICApO1xuICAgICAgbW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzLnB1c2goLi4uYWxsRXZlbnRzV2l0aER1cGxpY2F0ZUZyZWVCcmVha3MpO1xuICAgICAgbW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzLnB1c2goLi4uYnJlYWtzKTtcbiAgICAgIHBhcmVudEJyZWFrcy5wdXNoKC4uLmJyZWFrcyk7XG4gICAgfSBlbHNlIHtcbiAgICAgIG1vZGlmaWVkQWxsRXZlbnRzV2l0aEJyZWFrcy5wdXNoKC4uLm1vZGlmaWVkQWxsSG9zdEV2ZW50cyk7XG4gICAgfVxuXG4gICAgY29uc3Qgd29ya1RpbWVzID0gZ2VuZXJhdGVXb3JrVGltZXNGb3JJbnRlcm5hbEF0dGVuZGVlKFxuICAgICAgbWFpbkhvc3RJZCxcbiAgICAgIG1haW5Ib3N0SWQsXG4gICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICBob3N0VGltZXpvbmUsXG4gICAgICBob3N0VGltZXpvbmVcbiAgICApO1xuICAgIGNvbnN0IHRpbWVzbG90cyA9IFtdO1xuXG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCBzdGFydERhdGVzRm9yRWFjaERheS5sZW5ndGg7IGkrKykge1xuICAgICAgaWYgKGkgPT09IDApIHtcbiAgICAgICAgY29uc3QgdGltZXNsb3RzRm9yRGF5ID0gYXdhaXQgZ2VuZXJhdGVUaW1lU2xvdHNMaXRlRm9ySW50ZXJuYWxBdHRlbmRlZShcbiAgICAgICAgICBzdGFydERhdGVzRm9yRWFjaERheT8uW2ldLFxuICAgICAgICAgIG1haW5Ib3N0SWQsXG4gICAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgICAgdHJ1ZVxuICAgICAgICApO1xuICAgICAgICB0aW1lc2xvdHMucHVzaCguLi50aW1lc2xvdHNGb3JEYXkpO1xuICAgICAgICBjb250aW51ZTtcbiAgICAgIH1cbiAgICAgIGNvbnN0IHRpbWVzbG90c0ZvckRheSA9IGF3YWl0IGdlbmVyYXRlVGltZVNsb3RzTGl0ZUZvckludGVybmFsQXR0ZW5kZWUoXG4gICAgICAgIHN0YXJ0RGF0ZXNGb3JFYWNoRGF5Py5baV0sXG4gICAgICAgIG1haW5Ib3N0SWQsXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgIGZhbHNlXG4gICAgICApO1xuICAgICAgdGltZXNsb3RzLnB1c2goLi4udGltZXNsb3RzRm9yRGF5KTtcbiAgICB9XG5cbiAgICBjb25zdCBmaWx0ZXJlZEFsbEV2ZW50cyA9IF8udW5pcUJ5KFxuICAgICAgbW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzLmZpbHRlcigoZSkgPT5cbiAgICAgICAgdmFsaWRhdGVFdmVudERhdGVzKGUsIHVzZXJQcmVmZXJlbmNlcylcbiAgICAgICksXG4gICAgICAnaWQnXG4gICAgKTtcbiAgICBsZXQgZXZlbnRQYXJ0czogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZVtdID0gW107XG5cbiAgICBjb25zdCBldmVudFBhcnRNaW5pc0FjY3VtdWxhdGVkID0gW107XG4gICAgZm9yIChjb25zdCBldmVudCBvZiBmaWx0ZXJlZEFsbEV2ZW50cykge1xuICAgICAgY29uc3QgZXZlbnRQYXJ0TWluaXMgPSBnZW5lcmF0ZUV2ZW50UGFydHNMaXRlKGV2ZW50LCBtYWluSG9zdElkKTtcbiAgICAgIGV2ZW50UGFydE1pbmlzQWNjdW11bGF0ZWQucHVzaCguLi5ldmVudFBhcnRNaW5pcyk7XG4gICAgfVxuXG4gICAgY29uc3QgbW9kaWZpZWRFdmVudFBhcnRNaW5pc1ByZUJ1ZmZlciA9XG4gICAgICBtb2RpZnlFdmVudFBhcnRzRm9yTXVsdGlwbGVQcmVCdWZmZXJUaW1lKGV2ZW50UGFydE1pbmlzQWNjdW11bGF0ZWQpO1xuICAgIGNvbnN0IG1vZGlmaWVkRXZlbnRQYXJ0TWluaXNQcmVBbmRQb3N0QnVmZmVyID1cbiAgICAgIG1vZGlmeUV2ZW50UGFydHNGb3JNdWx0aXBsZVBvc3RCdWZmZXJUaW1lKFxuICAgICAgICBtb2RpZmllZEV2ZW50UGFydE1pbmlzUHJlQnVmZmVyXG4gICAgICApO1xuICAgIGNvbnN0IGZvcm1hdHRlZEV2ZW50UGFydHM6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSA9XG4gICAgICBtb2RpZmllZEV2ZW50UGFydE1pbmlzUHJlQW5kUG9zdEJ1ZmZlci5tYXAoKGUpID0+XG4gICAgICAgIGZvcm1hdEV2ZW50VHlwZVRvUGxhbm5lckV2ZW50KFxuICAgICAgICAgIGUsXG4gICAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICAgIHdvcmtUaW1lcyxcbiAgICAgICAgICBob3N0VGltZXpvbmVcbiAgICAgICAgKVxuICAgICAgKTtcbiAgICBpZiAoZm9ybWF0dGVkRXZlbnRQYXJ0cz8ubGVuZ3RoID4gMCkge1xuICAgICAgZXZlbnRQYXJ0cy5wdXNoKC4uLmZvcm1hdHRlZEV2ZW50UGFydHMpO1xuICAgIH1cblxuICAgIGlmIChldmVudFBhcnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICBldmVudFBhcnRzLmZvckVhY2goKGUpID0+IGNvbnNvbGUubG9nKGUsICcgZXZlbnRQYXJ0cyBhZnRlciBmb3JtYXR0aW5nJykpO1xuICAgICAgY29uc3QgbmV3RXZlbnRQYXJ0c1dpdGhQcmVmZXJyZWRUaW1lU2V0ID0gZXZlbnRQYXJ0cy5tYXAoKGUpID0+XG4gICAgICAgIHNldFByZWZlcnJlZFRpbWVGb3JVbk1vZGlmaWFibGVFdmVudChcbiAgICAgICAgICBlLFxuICAgICAgICAgIGFsbEhvc3RFdmVudHMuZmluZCgoZikgPT4gZi5pZCA9PT0gZS5ldmVudElkKT8udGltZXpvbmVcbiAgICAgICAgKVxuICAgICAgKTtcbiAgICAgIG5ld0V2ZW50UGFydHNXaXRoUHJlZmVycmVkVGltZVNldC5mb3JFYWNoKChlKSA9PlxuICAgICAgICBjb25zb2xlLmxvZyhlLCAnIG5ld0V2ZW50UGFydHNXaXRoUHJlZmVycmVkVGltZVNldCcpXG4gICAgICApO1xuICAgICAgY29uc3QgbmV3RXZlbnRQYXJ0cyA9IGF3YWl0IHRhZ0V2ZW50c0ZvckRhaWx5T3JXZWVrbHlUYXNrKFxuICAgICAgICBuZXdFdmVudFBhcnRzV2l0aFByZWZlcnJlZFRpbWVTZXRcbiAgICAgICk7XG4gICAgICBuZXdFdmVudFBhcnRzLmZvckVhY2goKGUpID0+XG4gICAgICAgIGNvbnNvbGUubG9nKGUsICcgbmV3RXZlbnRQYXJ0cyBhZnRlciB0YWdFdmVudHNGb3JEYWlseU9yV2Vla2x5VGFzaycpXG4gICAgICApO1xuICAgICAgY29uc3QgdXNlclBsYW5uZXJSZXF1ZXN0Qm9keSA9IGdlbmVyYXRlVXNlclBsYW5uZXJSZXF1ZXN0Qm9keShcbiAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICB1c2VyUHJlZmVyZW5jZXMudXNlcklkLFxuICAgICAgICB3b3JrVGltZXMsXG4gICAgICAgIG1haW5Ib3N0SWRcbiAgICAgICk7XG4gICAgICBjb25zb2xlLmxvZyh1c2VyUGxhbm5lclJlcXVlc3RCb2R5LCAnIHVzZXJQbGFubmVyUmVxdWVzdEJvZHknKTtcblxuICAgICAgY29uc3QgbW9kaWZpZWROZXdFdmVudFBhcnRzOiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlW10gPVxuICAgICAgICBuZXdFdmVudFBhcnRzLm1hcCgoZXZlbnRQYXJ0KSA9PiB7XG4gICAgICAgICAgY29uc3Qgb2xkRXZlbnQgPSBmaWx0ZXJlZEFsbEV2ZW50cy5maW5kKFxuICAgICAgICAgICAgKGV2ZW50KSA9PiBldmVudC5pZCA9PT0gZXZlbnRQYXJ0LmV2ZW50SWRcbiAgICAgICAgICApO1xuICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICBncm91cElkOiBldmVudFBhcnQ/Lmdyb3VwSWQsXG4gICAgICAgICAgICBldmVudElkOiBldmVudFBhcnQ/LmV2ZW50SWQsXG4gICAgICAgICAgICBwYXJ0OiBldmVudFBhcnQ/LnBhcnQsXG4gICAgICAgICAgICBsYXN0UGFydDogZXZlbnRQYXJ0Py5sYXN0UGFydCxcbiAgICAgICAgICAgIG1lZXRpbmdQYXJ0OiBldmVudFBhcnQ/Lm1lZXRpbmdQYXJ0LFxuICAgICAgICAgICAgbWVldGluZ0xhc3RQYXJ0OiBldmVudFBhcnQ/Lm1lZXRpbmdMYXN0UGFydCxcbiAgICAgICAgICAgIG1lZXRpbmdJZDogZXZlbnRQYXJ0Py5tZWV0aW5nSWQsXG4gICAgICAgICAgICBob3N0SWQ6IG1haW5Ib3N0SWQsXG4gICAgICAgICAgICBzdGFydERhdGU6IGRheWpzKGV2ZW50UGFydD8uc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG9sZEV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tOnNzJyksXG4gICAgICAgICAgICBlbmREYXRlOiBkYXlqcyhldmVudFBhcnQ/LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoob2xkRXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW06c3MnKSxcbiAgICAgICAgICAgIHVzZXJJZDogZXZlbnRQYXJ0Py51c2VySWQsXG4gICAgICAgICAgICB1c2VyOiBldmVudFBhcnQ/LnVzZXIsXG4gICAgICAgICAgICBwcmlvcml0eTogZXZlbnRQYXJ0Py5wcmlvcml0eSxcbiAgICAgICAgICAgIGlzUHJlRXZlbnQ6IGV2ZW50UGFydD8uaXNQcmVFdmVudCxcbiAgICAgICAgICAgIGlzUG9zdEV2ZW50OiBldmVudFBhcnQ/LmlzUG9zdEV2ZW50LFxuICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RTY29yZTogZXZlbnRQYXJ0Py5wb3NpdGl2ZUltcGFjdFNjb3JlLFxuICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3RTY29yZTogZXZlbnRQYXJ0Py5uZWdhdGl2ZUltcGFjdFNjb3JlLFxuICAgICAgICAgICAgbW9kaWZpYWJsZTogZXZlbnRQYXJ0Py5tb2RpZmlhYmxlLFxuICAgICAgICAgICAgaXNNZWV0aW5nOiBldmVudFBhcnQ/LmlzTWVldGluZyxcbiAgICAgICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nOiBldmVudFBhcnQ/LmlzRXh0ZXJuYWxNZWV0aW5nLFxuICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlOiBldmVudFBhcnQ/LmlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgICAgICAgIGlzTWVldGluZ01vZGlmaWFibGU6IGV2ZW50UGFydD8uaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgICAgICAgIGRhaWx5VGFza0xpc3Q6IGV2ZW50UGFydD8uZGFpbHlUYXNrTGlzdCxcbiAgICAgICAgICAgIHdlZWtseVRhc2tMaXN0OiBldmVudFBhcnQ/LndlZWtseVRhc2tMaXN0LFxuICAgICAgICAgICAgZ2FwOiBldmVudFBhcnQ/LmdhcCxcbiAgICAgICAgICAgIHRvdGFsV29ya2luZ0hvdXJzOiBldmVudFBhcnQ/LnRvdGFsV29ya2luZ0hvdXJzLFxuICAgICAgICAgICAgaGFyZERlYWRsaW5lOiBldmVudFBhcnQ/LmhhcmREZWFkbGluZSxcbiAgICAgICAgICAgIHNvZnREZWFkbGluZTogZXZlbnRQYXJ0Py5zb2Z0RGVhZGxpbmUsXG4gICAgICAgICAgICBmb3JFdmVudElkOiBldmVudFBhcnQ/LmZvckV2ZW50SWQsXG4gICAgICAgICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2VlazogZXZlbnRQYXJ0Py5wb3NpdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0VGltZTogZXZlbnRQYXJ0Py5wb3NpdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2VlazogZXZlbnRQYXJ0Py5uZWdhdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZTogZXZlbnRQYXJ0Py5uZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgICAgICBwcmVmZXJyZWREYXlPZldlZWs6IGV2ZW50UGFydD8ucHJlZmVycmVkRGF5T2ZXZWVrLFxuICAgICAgICAgICAgcHJlZmVycmVkVGltZTogZXZlbnRQYXJ0Py5wcmVmZXJyZWRUaW1lLFxuICAgICAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U6IGV2ZW50UGFydD8ucHJlZmVycmVkU3RhcnRUaW1lUmFuZ2UsXG4gICAgICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2U6IGV2ZW50UGFydD8ucHJlZmVycmVkRW5kVGltZVJhbmdlLFxuICAgICAgICAgICAgZXZlbnQ6IGV2ZW50UGFydD8uZXZlbnQsXG4gICAgICAgICAgfTtcbiAgICAgICAgfSk7XG5cbiAgICAgIHJldHVybiBtb2RpZmllZE5ld0V2ZW50UGFydHM/Lmxlbmd0aCA+IDBcbiAgICAgICAgPyB7XG4gICAgICAgICAgICB1c2VySWQ6IG1haW5Ib3N0SWQsXG4gICAgICAgICAgICBob3N0SWQ6IG1haW5Ib3N0SWQsXG4gICAgICAgICAgICBldmVudFBhcnRzOiBtb2RpZmllZE5ld0V2ZW50UGFydHMsXG4gICAgICAgICAgICBhbGxFdmVudHM6IGZpbHRlcmVkQWxsRXZlbnRzLFxuICAgICAgICAgICAgYnJlYWtzOiBwYXJlbnRCcmVha3MsXG4gICAgICAgICAgICBvbGRFdmVudHM6IG9sZEhvc3RFdmVudHMsXG4gICAgICAgICAgICB0aW1lc2xvdHMsXG4gICAgICAgICAgICB1c2VyUGxhbm5lclJlcXVlc3RCb2R5LFxuICAgICAgICAgIH1cbiAgICAgICAgOiBudWxsO1xuICAgIH1cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZSxcbiAgICAgICcgdW5hYmxlIHRvIHByb2Nlc3MgZXZlbnRzIGZvciBvcHRhcGxhbm5lciBmb3IgaG9zdCBhdHRlbmRlZSdcbiAgICApO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0V2ZW50c0Zvck9wdGFQbGFubmVyRm9ySW50ZXJuYWxBdHRlbmRlZXMgPSBhc3luYyAoXG4gIG1haW5Ib3N0SWQ6IHN0cmluZyxcbiAgYWxsRXZlbnRzOiBFdmVudFBsdXNUeXBlW10sXG4gIHdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nLFxuICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICBpbnRlcm5hbEF0dGVuZGVlczogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdLFxuICBvbGRFdmVudHM6IEV2ZW50UGx1c1R5cGVbXSxcbiAgb2xkTWVldGluZ0V2ZW50cz86IEV2ZW50TWVldGluZ1BsdXNUeXBlW10sXG4gIG5ld01lZXRpbmdFdmVudHM/OiBFdmVudE1lZXRpbmdQbHVzVHlwZVtdLFxuICBuZXdIb3N0QnVmZmVyVGltZXM/OiBCdWZmZXJUaW1lT2JqZWN0VHlwZVtdXG4pOiBQcm9taXNlPFJldHVybkJvZHlGb3JBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGU+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBuZXdCdWZmZXJUaW1lQXJyYXk6IEV2ZW50UGx1c1R5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBuZXdIb3N0QnVmZmVyVGltZSBvZiBuZXdIb3N0QnVmZmVyVGltZXMpIHtcbiAgICAgIGlmIChuZXdIb3N0QnVmZmVyVGltZT8uYmVmb3JlRXZlbnQ/LmlkKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIG5ld0hvc3RCdWZmZXJUaW1lPy5iZWZvcmVFdmVudCxcbiAgICAgICAgICAnIG5ld1RpbWVCbG9ja2luZz8uYmVmb3JlRXZlbnQnXG4gICAgICAgICk7XG4gICAgICAgIG5ld0J1ZmZlclRpbWVBcnJheS5wdXNoKG5ld0hvc3RCdWZmZXJUaW1lLmJlZm9yZUV2ZW50KTtcbiAgICAgIH1cblxuICAgICAgaWYgKG5ld0hvc3RCdWZmZXJUaW1lPy5hZnRlckV2ZW50Py5pZCkge1xuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBuZXdIb3N0QnVmZmVyVGltZT8uYWZ0ZXJFdmVudCxcbiAgICAgICAgICAnIG5ld1RpbWVCbG9ja2luZz8uYWZ0ZXJFdmVudCdcbiAgICAgICAgKTtcbiAgICAgICAgbmV3QnVmZmVyVGltZUFycmF5LnB1c2gobmV3SG9zdEJ1ZmZlclRpbWUuYWZ0ZXJFdmVudCk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgb2xkTWVldGluZ0V2ZW50cz8uZm9yRWFjaCgobykgPT4gY29uc29sZS5sb2cobywgJyBvbGRNZWV0aW5nRXZlbnRzJykpO1xuICAgIGludGVybmFsQXR0ZW5kZWVzPy5mb3JFYWNoKChpKSA9PlxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGksXG4gICAgICAgICcgaW50ZXJuYWxBdHRlbmRlZXMgaW5zaWRlIHByb2Nlc3NFdmVudHNGb3JPcHRhUGxhbm5lckZvckludGVybmFsQXR0ZW5kZWVzJ1xuICAgICAgKVxuICAgICk7XG4gICAgY29uc3QgZmlsdGVyZWRPbGRNZWV0aW5nRXZlbnRzID0gb2xkTWVldGluZ0V2ZW50c1xuICAgICAgPy5tYXAoKG0pID0+IHtcbiAgICAgICAgY29uc3QgZm91bmRJbmRleCA9IGFsbEV2ZW50cz8uZmluZEluZGV4KChhKSA9PiBhPy5pZCA9PT0gbT8uaWQpO1xuXG4gICAgICAgIGlmIChmb3VuZEluZGV4ID4gLTEpIHtcbiAgICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgICAgfVxuICAgICAgICByZXR1cm4gbTtcbiAgICAgIH0pXG4gICAgICA/LmZpbHRlcigoZSkgPT4gISFlKTtcblxuICAgIGZpbHRlcmVkT2xkTWVldGluZ0V2ZW50cz8uZm9yRWFjaCgoZSkgPT5cbiAgICAgIGNvbnNvbGUubG9nKGUsICcgZmlsdGVyZWRPbGRNZWV0aW5nRXZlbnRzJylcbiAgICApO1xuICAgIGNvbnN0IG1vZGlmaWVkQWxsRXZlbnRzID0gXy5jbG9uZURlZXAoYWxsRXZlbnRzKT8uZmlsdGVyKChlKSA9PiB7XG4gICAgICBpZiAoZmlsdGVyZWRPbGRNZWV0aW5nRXZlbnRzPy5bMF0/LmlkKSB7XG4gICAgICAgIGNvbnN0IGZvdW5kSW5kZXggPSBmaWx0ZXJlZE9sZE1lZXRpbmdFdmVudHM/LmZpbmRJbmRleChcbiAgICAgICAgICAobSkgPT4gbT8uaWQgPT09IGU/LmlkXG4gICAgICAgICk7XG4gICAgICAgIGlmIChmb3VuZEluZGV4ID4gLTEpIHtcbiAgICAgICAgICByZXR1cm4gZmFsc2U7XG4gICAgICAgIH1cbiAgICAgICAgcmV0dXJuIHRydWU7XG4gICAgICB9XG4gICAgICByZXR1cm4gdHJ1ZTtcbiAgICB9KTtcblxuICAgIGlmIChmaWx0ZXJlZE9sZE1lZXRpbmdFdmVudHM/LlswXT8uaWQpIHtcbiAgICAgIG1vZGlmaWVkQWxsRXZlbnRzLnB1c2goXG4gICAgICAgIC4uLmZpbHRlcmVkT2xkTWVldGluZ0V2ZW50cz8ubWFwKChhKSA9PlxuICAgICAgICAgIGNvbnZlcnRNZWV0aW5nUGx1c1R5cGVUb0V2ZW50UGx1c1R5cGUoYSlcbiAgICAgICAgKVxuICAgICAgKTtcbiAgICB9XG5cbiAgICBpZiAobmV3QnVmZmVyVGltZUFycmF5Py5sZW5ndGggPiAwKSB7XG4gICAgICBtb2RpZmllZEFsbEV2ZW50cy5wdXNoKC4uLm5ld0J1ZmZlclRpbWVBcnJheSk7XG4gICAgfVxuXG4gICAgaWYgKG5ld01lZXRpbmdFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIG1vZGlmaWVkQWxsRXZlbnRzLnB1c2goXG4gICAgICAgIC4uLm5ld01lZXRpbmdFdmVudHM/Lm1hcCgobSkgPT5cbiAgICAgICAgICBjb252ZXJ0TWVldGluZ1BsdXNUeXBlVG9FdmVudFBsdXNUeXBlKG0pXG4gICAgICAgIClcbiAgICAgICk7XG4gICAgfVxuXG4gICAgbW9kaWZpZWRBbGxFdmVudHM/LmZvckVhY2goKGUpID0+IGNvbnNvbGUubG9nKGUsICcgbW9kaWZpZWRBbGxFdmVudHMnKSk7XG5cbiAgICBjb25zdCB1bmZpbHRlcmVkVXNlclByZWZlcmVuY2VzOiBVc2VyUHJlZmVyZW5jZVR5cGVbXSA9IFtdO1xuICAgIGZvciAoY29uc3QgaW50ZXJuYWxBdHRlbmRlZSBvZiBpbnRlcm5hbEF0dGVuZGVlcykge1xuICAgICAgY29uc3QgdXNlclByZWZlcmVuY2UgPSBhd2FpdCBnZXRVc2VyUHJlZmVyZW5jZXMoaW50ZXJuYWxBdHRlbmRlZT8udXNlcklkKTtcbiAgICAgIHVuZmlsdGVyZWRVc2VyUHJlZmVyZW5jZXMucHVzaCh1c2VyUHJlZmVyZW5jZSk7XG4gICAgfVxuXG4gICAgY29uc3QgdXNlclByZWZlcmVuY2VzOiBVc2VyUHJlZmVyZW5jZVR5cGVbXSA9IF8udW5pcVdpdGgoXG4gICAgICB1bmZpbHRlcmVkVXNlclByZWZlcmVuY2VzLFxuICAgICAgXy5pc0VxdWFsXG4gICAgKTtcblxuICAgIGNvbnN0IHVuZmlsdGVyZWRHbG9iYWxQcmltYXJ5Q2FsZW5kYXJzOiBDYWxlbmRhclR5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBpbnRlcm5hbEF0dGVuZGVlIG9mIGludGVybmFsQXR0ZW5kZWVzKSB7XG4gICAgICBjb25zdCBnbG9iYWxQcmltYXJ5Q2FsZW5kYXIgPSBhd2FpdCBnZXRHbG9iYWxDYWxlbmRhcihcbiAgICAgICAgaW50ZXJuYWxBdHRlbmRlZT8udXNlcklkXG4gICAgICApO1xuICAgICAgdW5maWx0ZXJlZEdsb2JhbFByaW1hcnlDYWxlbmRhcnMucHVzaChnbG9iYWxQcmltYXJ5Q2FsZW5kYXIpO1xuICAgIH1cblxuICAgIGNvbnN0IGdsb2JhbFByaW1hcnlDYWxlbmRhcnMgPSBfLnVuaXFXaXRoKFxuICAgICAgdW5maWx0ZXJlZEdsb2JhbFByaW1hcnlDYWxlbmRhcnMsXG4gICAgICBfLmlzRXF1YWxcbiAgICApO1xuXG4gICAgZ2xvYmFsUHJpbWFyeUNhbGVuZGFycz8uZm9yRWFjaCgoYykgPT5cbiAgICAgIGNvbnNvbGUubG9nKGMsICcgZ2xvYmFsUHJpbWFyeUNhbGVuZGFycycpXG4gICAgKTtcblxuICAgIGNvbnN0IG1vZGlmaWVkQWxsRXZlbnRzV2l0aEJyZWFrczogRXZlbnRQbHVzVHlwZVtdID0gW107XG5cbiAgICBsZXQgcGFyZW50QnJlYWtzOiBFdmVudFBsdXNUeXBlW10gPSBbXTtcbiAgICBmb3IgKGNvbnN0IHVzZXJQcmVmZXJlbmNlIG9mIHVzZXJQcmVmZXJlbmNlcykge1xuICAgICAgY29uc3QgZ2xvYmFsUHJpbWFyeUNhbGVuZGFyID0gZ2xvYmFsUHJpbWFyeUNhbGVuZGFycz8uZmluZChcbiAgICAgICAgKGcpID0+IGc/LnVzZXJJZCA9PT0gdXNlclByZWZlcmVuY2U/LnVzZXJJZFxuICAgICAgKTtcbiAgICAgIGlmICghZ2xvYmFsUHJpbWFyeUNhbGVuZGFyKSB7XG4gICAgICAgIHRocm93IG5ldyBFcnJvcignbm8gZ2xvYmFsIHByaW1hcnkgY2FsZW5kYXIgZm91bmQnKTtcbiAgICAgIH1cbiAgICAgIGNvbnN0IHVzZXJJZCA9IHVzZXJQcmVmZXJlbmNlPy51c2VySWQ7XG5cbiAgICAgIGNvbnN0IGJyZWFrcyA9IGF3YWl0IGdlbmVyYXRlQnJlYWtFdmVudHNGb3JEYXRlKFxuICAgICAgICB1c2VyUHJlZmVyZW5jZSxcbiAgICAgICAgdXNlcklkLFxuICAgICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgICAgZ2xvYmFsUHJpbWFyeUNhbGVuZGFyPy5pZFxuICAgICAgKTtcblxuICAgICAgYnJlYWtzLmZvckVhY2goKGIpID0+IGNvbnNvbGUubG9nKGIsICcgZ2VuZXJhdGVkQnJlYWtzJykpO1xuXG4gICAgICBpZiAoYnJlYWtzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGNvbnN0IGFsbEV2ZW50c1dpdGhEdXBsaWNhdGVGcmVlQnJlYWtzID0gXy5kaWZmZXJlbmNlQnkoXG4gICAgICAgICAgbW9kaWZpZWRBbGxFdmVudHMsXG4gICAgICAgICAgYnJlYWtzLFxuICAgICAgICAgICdpZCdcbiAgICAgICAgKTtcbiAgICAgICAgbW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzLnB1c2goXG4gICAgICAgICAgLi4uYWxsRXZlbnRzV2l0aER1cGxpY2F0ZUZyZWVCcmVha3M/LmZpbHRlcihcbiAgICAgICAgICAgIChlKSA9PiBlPy51c2VySWQgPT09IHVzZXJJZFxuICAgICAgICAgIClcbiAgICAgICAgKTtcbiAgICAgICAgbW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzLnB1c2goLi4uYnJlYWtzKTtcbiAgICAgICAgcGFyZW50QnJlYWtzLnB1c2goLi4uYnJlYWtzKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIG1vZGlmaWVkQWxsRXZlbnRzV2l0aEJyZWFrcy5wdXNoKFxuICAgICAgICAgIC4uLm1vZGlmaWVkQWxsRXZlbnRzPy5maWx0ZXIoKGUpID0+IGU/LnVzZXJJZCA9PT0gdXNlcklkKVxuICAgICAgICApO1xuICAgICAgfVxuICAgIH1cblxuICAgIG1vZGlmaWVkQWxsRXZlbnRzV2l0aEJyZWFrcz8uZm9yRWFjaCgobSkgPT5cbiAgICAgIGNvbnNvbGUubG9nKG0sICcgbW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzJylcbiAgICApO1xuXG4gICAgY29uc3QgZGlmZkRheXMgPSBkYXlqcyh3aW5kb3dFbmREYXRlLnNsaWNlKDAsIDE5KSkuZGlmZihcbiAgICAgIGRheWpzKHdpbmRvd1N0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLFxuICAgICAgJ2RheSdcbiAgICApO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZGlmZkRheXMsXG4gICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgJyBkaWZmRGF5cywgd2luZG93RW5kRGF0ZSwgd2luZG93U3RhcnREYXRlJ1xuICAgICk7XG4gICAgY29uc3Qgc3RhcnREYXRlc0ZvckVhY2hEYXkgPSBbXTtcblxuICAgIGZvciAobGV0IGkgPSAwOyBpIDw9IGRpZmZEYXlzOyBpKyspIHtcbiAgICAgIHN0YXJ0RGF0ZXNGb3JFYWNoRGF5LnB1c2goXG4gICAgICAgIGRheWpzKHdpbmRvd1N0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuYWRkKGksICdkYXknKVxuICAgICAgICAgIC5mb3JtYXQoKVxuICAgICAgKTtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhzdGFydERhdGVzRm9yRWFjaERheSwgJyBzdGFydERhdGVzRm9yRWFjaERheScpO1xuXG4gICAgY29uc3QgdW5maWx0ZXJlZFdvcmtUaW1lczogV29ya1RpbWVUeXBlW10gPSBbXTtcbiAgICBmb3IgKGNvbnN0IGludGVybmFsQXR0ZW5kZWUgb2YgaW50ZXJuYWxBdHRlbmRlZXMpIHtcbiAgICAgIGNvbnN0IHVzZXJQcmVmZXJlbmNlID0gdXNlclByZWZlcmVuY2VzLmZpbmQoXG4gICAgICAgICh1KSA9PiB1LnVzZXJJZCA9PT0gaW50ZXJuYWxBdHRlbmRlZS51c2VySWRcbiAgICAgICk7XG4gICAgICBjb25zdCBhdHRlbmRlZVRpbWV6b25lID0gaW50ZXJuYWxBdHRlbmRlZT8udGltZXpvbmU7XG4gICAgICBjb25zdCB3b3JrVGltZXNGb3JBdHRlbmRlZSA9IGdlbmVyYXRlV29ya1RpbWVzRm9ySW50ZXJuYWxBdHRlbmRlZShcbiAgICAgICAgbWFpbkhvc3RJZCxcbiAgICAgICAgaW50ZXJuYWxBdHRlbmRlZS51c2VySWQsXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlLFxuICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgIGF0dGVuZGVlVGltZXpvbmVcbiAgICAgICk7XG4gICAgICB1bmZpbHRlcmVkV29ya1RpbWVzLnB1c2goLi4ud29ya1RpbWVzRm9yQXR0ZW5kZWUpO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKHVuZmlsdGVyZWRXb3JrVGltZXMsICd1bmZpbHRlcmVkV29ya1RpbWVzJyk7XG4gICAgY29uc3Qgd29ya1RpbWVzOiBXb3JrVGltZVR5cGVbXSA9IF8udW5pcVdpdGgoXG4gICAgICB1bmZpbHRlcmVkV29ya1RpbWVzLFxuICAgICAgXy5pc0VxdWFsXG4gICAgKTtcblxuICAgIGNvbnN0IHVuZmlsdGVyZWRUaW1lc2xvdHMgPSBbXTtcbiAgICBjb25zdCB0aW1lc2xvdHMgPSBbXTtcblxuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgc3RhcnREYXRlc0ZvckVhY2hEYXkubGVuZ3RoOyBpKyspIHtcbiAgICAgIGlmIChpID09PSAwKSB7XG4gICAgICAgIGZvciAoY29uc3QgaW50ZXJuYWxBdHRlbmRlZSBvZiBpbnRlcm5hbEF0dGVuZGVlcykge1xuICAgICAgICAgIGNvbnN0IHVzZXJQcmVmZXJlbmNlID0gdXNlclByZWZlcmVuY2VzLmZpbmQoXG4gICAgICAgICAgICAodSkgPT4gdS51c2VySWQgPT09IGludGVybmFsQXR0ZW5kZWUudXNlcklkXG4gICAgICAgICAgKTtcbiAgICAgICAgICBjb25zdCB0aW1lc2xvdHNGb3JEYXkgPVxuICAgICAgICAgICAgYXdhaXQgZ2VuZXJhdGVUaW1lU2xvdHNMaXRlRm9ySW50ZXJuYWxBdHRlbmRlZShcbiAgICAgICAgICAgICAgc3RhcnREYXRlc0ZvckVhY2hEYXk/LltpXSxcbiAgICAgICAgICAgICAgbWFpbkhvc3RJZCxcbiAgICAgICAgICAgICAgdXNlclByZWZlcmVuY2UsXG4gICAgICAgICAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgICAgICAgICAgaW50ZXJuYWxBdHRlbmRlZT8udGltZXpvbmUsXG4gICAgICAgICAgICAgIHRydWVcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgdW5maWx0ZXJlZFRpbWVzbG90cy5wdXNoKC4uLnRpbWVzbG90c0ZvckRheSk7XG4gICAgICAgIH1cbiAgICAgICAgY29udGludWU7XG4gICAgICB9XG4gICAgICBmb3IgKGNvbnN0IGludGVybmFsQXR0ZW5kZWUgb2YgaW50ZXJuYWxBdHRlbmRlZXMpIHtcbiAgICAgICAgY29uc3QgdXNlclByZWZlcmVuY2UgPSB1c2VyUHJlZmVyZW5jZXMuZmluZChcbiAgICAgICAgICAodSkgPT4gdS51c2VySWQgPT09IGludGVybmFsQXR0ZW5kZWUudXNlcklkXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IHRpbWVzbG90c0ZvckRheSA9IGF3YWl0IGdlbmVyYXRlVGltZVNsb3RzTGl0ZUZvckludGVybmFsQXR0ZW5kZWUoXG4gICAgICAgICAgc3RhcnREYXRlc0ZvckVhY2hEYXk/LltpXSxcbiAgICAgICAgICBtYWluSG9zdElkLFxuICAgICAgICAgIHVzZXJQcmVmZXJlbmNlLFxuICAgICAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgICAgICBpbnRlcm5hbEF0dGVuZGVlPy50aW1lem9uZSxcbiAgICAgICAgICBmYWxzZVxuICAgICAgICApO1xuICAgICAgICB1bmZpbHRlcmVkVGltZXNsb3RzLnB1c2goLi4udGltZXNsb3RzRm9yRGF5KTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICB0aW1lc2xvdHMucHVzaCguLi5fLnVuaXFXaXRoKHVuZmlsdGVyZWRUaW1lc2xvdHMsIF8uaXNFcXVhbCkpO1xuXG4gICAgY29uc3QgdW5maWx0ZXJlZEFsbEV2ZW50czogRXZlbnRQbHVzVHlwZVtdID0gW107XG4gICAgZm9yIChjb25zdCBpbnRlcm5hbEF0dGVuZGVlIG9mIGludGVybmFsQXR0ZW5kZWVzKSB7XG4gICAgICBjb25zdCB1c2VyUHJlZmVyZW5jZSA9IHVzZXJQcmVmZXJlbmNlcy5maW5kKFxuICAgICAgICAodSkgPT4gdS51c2VySWQgPT09IGludGVybmFsQXR0ZW5kZWUudXNlcklkXG4gICAgICApO1xuICAgICAgY29uc3QgbW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzV2l0aFVzZXIgPVxuICAgICAgICBtb2RpZmllZEFsbEV2ZW50c1dpdGhCcmVha3MuZmlsdGVyKFxuICAgICAgICAgIChlKSA9PiBlLnVzZXJJZCA9PT0gaW50ZXJuYWxBdHRlbmRlZS51c2VySWRcbiAgICAgICAgKTtcbiAgICAgIGNvbnN0IGV2ZW50cyA9IG1vZGlmaWVkQWxsRXZlbnRzV2l0aEJyZWFrc1dpdGhVc2VyLmZpbHRlcigoZSkgPT5cbiAgICAgICAgdmFsaWRhdGVFdmVudERhdGVzKGUsIHVzZXJQcmVmZXJlbmNlKVxuICAgICAgKTtcbiAgICAgIHVuZmlsdGVyZWRBbGxFdmVudHMucHVzaCguLi5ldmVudHMpO1xuICAgIH1cbiAgICB1bmZpbHRlcmVkQWxsRXZlbnRzPy5mb3JFYWNoKChlKSA9PiBjb25zb2xlLmxvZyhlLCAnIHVuZmlsdGVyZWRBbGxFdmVudHMnKSk7XG5cbiAgICBjb25zdCBmaWx0ZXJlZEFsbEV2ZW50cyA9IF8udW5pcUJ5KHVuZmlsdGVyZWRBbGxFdmVudHMsICdpZCcpO1xuXG4gICAgZmlsdGVyZWRBbGxFdmVudHM/LmZvckVhY2goKGUpID0+IGNvbnNvbGUubG9nKGUsICcgZmlsdGVyZWRBbGxFdmVudHMnKSk7XG5cbiAgICBsZXQgZXZlbnRQYXJ0czogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZVtdID0gW107XG5cbiAgICBjb25zdCBldmVudFBhcnRNaW5pc0FjY3VtdWxhdGVkID0gW107XG4gICAgZm9yIChjb25zdCBldmVudCBvZiBmaWx0ZXJlZEFsbEV2ZW50cykge1xuICAgICAgY29uc3QgZXZlbnRQYXJ0TWluaXMgPSBnZW5lcmF0ZUV2ZW50UGFydHNMaXRlKGV2ZW50LCBtYWluSG9zdElkKTtcbiAgICAgIGV2ZW50UGFydE1pbmlzQWNjdW11bGF0ZWQucHVzaCguLi5ldmVudFBhcnRNaW5pcyk7XG4gICAgfVxuXG4gICAgZXZlbnRQYXJ0TWluaXNBY2N1bXVsYXRlZD8uZm9yRWFjaCgoZSkgPT5cbiAgICAgIGNvbnNvbGUubG9nKGUsICcgZXZlbnRQYXJ0TWluaXNBY2N1bXVsYXRlZCcpXG4gICAgKTtcbiAgICBjb25zdCBtb2RpZmllZEV2ZW50UGFydE1pbmlzUHJlQnVmZmVyID1cbiAgICAgIG1vZGlmeUV2ZW50UGFydHNGb3JNdWx0aXBsZVByZUJ1ZmZlclRpbWUoZXZlbnRQYXJ0TWluaXNBY2N1bXVsYXRlZCk7XG4gICAgY29uc3QgbW9kaWZpZWRFdmVudFBhcnRNaW5pc1ByZUFuZFBvc3RCdWZmZXIgPVxuICAgICAgbW9kaWZ5RXZlbnRQYXJ0c0Zvck11bHRpcGxlUG9zdEJ1ZmZlclRpbWUoXG4gICAgICAgIG1vZGlmaWVkRXZlbnRQYXJ0TWluaXNQcmVCdWZmZXJcbiAgICAgICk7XG5cbiAgICBtb2RpZmllZEV2ZW50UGFydE1pbmlzUHJlQW5kUG9zdEJ1ZmZlcj8uZm9yRWFjaCgoZSkgPT5cbiAgICAgIGNvbnNvbGUubG9nKGUsICcgbW9kaWZpZWRFdmVudFBhcnRNaW5pc1ByZUFuZFBvc3RCdWZmZXInKVxuICAgICk7XG5cbiAgICBjb25zdCBmb3JtYXR0ZWRFdmVudFBhcnRzOiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlW10gPSBbXTtcbiAgICBmb3IgKGNvbnN0IHVzZXJQcmVmZXJlbmNlIG9mIHVzZXJQcmVmZXJlbmNlcykge1xuICAgICAgY29uc3QgZm9ybWF0dGVkRXZlbnRQYXJ0c0ZvclVzZXI6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSA9XG4gICAgICAgIG1vZGlmaWVkRXZlbnRQYXJ0TWluaXNQcmVBbmRQb3N0QnVmZmVyXG4gICAgICAgICAgPy5maWx0ZXIoKGUpID0+IGU/LnVzZXJJZCA9PT0gdXNlclByZWZlcmVuY2U/LnVzZXJJZClcbiAgICAgICAgICA/Lm1hcCgoZSkgPT5cbiAgICAgICAgICAgIGZvcm1hdEV2ZW50VHlwZVRvUGxhbm5lckV2ZW50KFxuICAgICAgICAgICAgICBlLFxuICAgICAgICAgICAgICB1c2VyUHJlZmVyZW5jZSxcbiAgICAgICAgICAgICAgd29ya1RpbWVzLFxuICAgICAgICAgICAgICBob3N0VGltZXpvbmVcbiAgICAgICAgICAgIClcbiAgICAgICAgICApO1xuXG4gICAgICBmb3JtYXR0ZWRFdmVudFBhcnRzRm9yVXNlcj8uZm9yRWFjaCgoZSkgPT5cbiAgICAgICAgY29uc29sZS5sb2coZSwgJyBmb3JtYXR0ZWRFdmVudFBhcnRzRm9yVXNlcicpXG4gICAgICApO1xuXG4gICAgICBmb3JtYXR0ZWRFdmVudFBhcnRzLnB1c2goLi4uZm9ybWF0dGVkRXZlbnRQYXJ0c0ZvclVzZXIpO1xuICAgIH1cblxuICAgIGZvcm1hdHRlZEV2ZW50UGFydHM/LmZvckVhY2goKGUpID0+IGNvbnNvbGUubG9nKGUsICcgZm9ybWF0dGVkRXZlbnRQYXJ0cycpKTtcblxuICAgIGlmIChmb3JtYXR0ZWRFdmVudFBhcnRzLmxlbmd0aCA+IDApIHtcbiAgICAgIGV2ZW50UGFydHMucHVzaCguLi5fLnVuaXFXaXRoKGZvcm1hdHRlZEV2ZW50UGFydHMsIF8uaXNFcXVhbCkpO1xuICAgIH1cblxuICAgIGlmIChldmVudFBhcnRzLmxlbmd0aCA+IDApIHtcbiAgICAgIGV2ZW50UGFydHMuZm9yRWFjaCgoZSkgPT4gY29uc29sZS5sb2coZSwgJyBldmVudFBhcnRzIGFmdGVyIGZvcm1hdHRpbmcnKSk7XG4gICAgICBjb25zdCBuZXdFdmVudFBhcnRzV2l0aFByZWZlcnJlZFRpbWVTZXQgPSBldmVudFBhcnRzLm1hcCgoZSkgPT5cbiAgICAgICAgc2V0UHJlZmVycmVkVGltZUZvclVuTW9kaWZpYWJsZUV2ZW50KFxuICAgICAgICAgIGUsXG4gICAgICAgICAgYWxsRXZlbnRzLmZpbmQoKGYpID0+IGYuaWQgPT09IGUuZXZlbnRJZCk/LnRpbWV6b25lXG4gICAgICAgIClcbiAgICAgICk7XG4gICAgICBuZXdFdmVudFBhcnRzV2l0aFByZWZlcnJlZFRpbWVTZXQuZm9yRWFjaCgoZSkgPT5cbiAgICAgICAgY29uc29sZS5sb2coZSwgJyBuZXdFdmVudFBhcnRzV2l0aFByZWZlcnJlZFRpbWVTZXQnKVxuICAgICAgKTtcbiAgICAgIGNvbnN0IG5ld0V2ZW50UGFydHMgPSBhd2FpdCB0YWdFdmVudHNGb3JEYWlseU9yV2Vla2x5VGFzayhcbiAgICAgICAgbmV3RXZlbnRQYXJ0c1dpdGhQcmVmZXJyZWRUaW1lU2V0XG4gICAgICApO1xuICAgICAgbmV3RXZlbnRQYXJ0cy5mb3JFYWNoKChlKSA9PlxuICAgICAgICBjb25zb2xlLmxvZyhlLCAnIG5ld0V2ZW50UGFydHMgYWZ0ZXIgdGFnRXZlbnRzRm9yRGFpbHlPcldlZWtseVRhc2snKVxuICAgICAgKTtcbiAgICAgIGNvbnN0IHVuZmlsdGVyZWRVc2VyTGlzdDogVXNlclBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSA9IFtdO1xuICAgICAgZm9yIChjb25zdCB1c2VyUHJlZmVyZW5jZSBvZiB1c2VyUHJlZmVyZW5jZXMpIHtcbiAgICAgICAgY29uc3QgdXNlclBsYW5uZXJSZXF1ZXN0Qm9keSA9IGdlbmVyYXRlVXNlclBsYW5uZXJSZXF1ZXN0Qm9keShcbiAgICAgICAgICB1c2VyUHJlZmVyZW5jZSxcbiAgICAgICAgICB1c2VyUHJlZmVyZW5jZT8udXNlcklkLFxuICAgICAgICAgIHdvcmtUaW1lcyxcbiAgICAgICAgICBtYWluSG9zdElkXG4gICAgICAgICk7XG4gICAgICAgIGNvbnNvbGUubG9nKHVzZXJQbGFubmVyUmVxdWVzdEJvZHksICcgdXNlclBsYW5uZXJSZXF1ZXN0Qm9keScpO1xuICAgICAgICB1bmZpbHRlcmVkVXNlckxpc3QucHVzaCh1c2VyUGxhbm5lclJlcXVlc3RCb2R5KTtcbiAgICAgIH1cblxuICAgICAgY29uc3QgdXNlckxpc3Q6IFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlW10gPSBfLnVuaXFXaXRoKFxuICAgICAgICB1bmZpbHRlcmVkVXNlckxpc3QsXG4gICAgICAgIF8uaXNFcXVhbFxuICAgICAgKTtcblxuICAgICAgY29uc3QgbW9kaWZpZWROZXdFdmVudFBhcnRzOiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlW10gPVxuICAgICAgICBuZXdFdmVudFBhcnRzLm1hcCgoZXZlbnRQYXJ0KSA9PiB7XG4gICAgICAgICAgY29uc3Qgb2xkRXZlbnQgPSBmaWx0ZXJlZEFsbEV2ZW50cy5maW5kKFxuICAgICAgICAgICAgKGV2ZW50KSA9PiBldmVudC5pZCA9PT0gZXZlbnRQYXJ0LmV2ZW50SWRcbiAgICAgICAgICApO1xuICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICBncm91cElkOiBldmVudFBhcnQ/Lmdyb3VwSWQsXG4gICAgICAgICAgICBldmVudElkOiBldmVudFBhcnQ/LmV2ZW50SWQsXG4gICAgICAgICAgICBwYXJ0OiBldmVudFBhcnQ/LnBhcnQsXG4gICAgICAgICAgICBsYXN0UGFydDogZXZlbnRQYXJ0Py5sYXN0UGFydCxcbiAgICAgICAgICAgIG1lZXRpbmdQYXJ0OiBldmVudFBhcnQ/Lm1lZXRpbmdQYXJ0LFxuICAgICAgICAgICAgbWVldGluZ0xhc3RQYXJ0OiBldmVudFBhcnQ/Lm1lZXRpbmdMYXN0UGFydCxcbiAgICAgICAgICAgIG1lZXRpbmdJZDogZXZlbnRQYXJ0Py5tZWV0aW5nSWQsXG4gICAgICAgICAgICBob3N0SWQ6IG1haW5Ib3N0SWQsXG4gICAgICAgICAgICBzdGFydERhdGU6IGRheWpzKGV2ZW50UGFydD8uc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG9sZEV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tOnNzJyksXG4gICAgICAgICAgICBlbmREYXRlOiBkYXlqcyhldmVudFBhcnQ/LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoob2xkRXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW06c3MnKSxcbiAgICAgICAgICAgIHVzZXJJZDogZXZlbnRQYXJ0Py51c2VySWQsXG4gICAgICAgICAgICB1c2VyOiBldmVudFBhcnQ/LnVzZXIsXG4gICAgICAgICAgICBwcmlvcml0eTogZXZlbnRQYXJ0Py5wcmlvcml0eSxcbiAgICAgICAgICAgIGlzUHJlRXZlbnQ6IGV2ZW50UGFydD8uaXNQcmVFdmVudCxcbiAgICAgICAgICAgIGlzUG9zdEV2ZW50OiBldmVudFBhcnQ/LmlzUG9zdEV2ZW50LFxuICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RTY29yZTogZXZlbnRQYXJ0Py5wb3NpdGl2ZUltcGFjdFNjb3JlLFxuICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3RTY29yZTogZXZlbnRQYXJ0Py5uZWdhdGl2ZUltcGFjdFNjb3JlLFxuICAgICAgICAgICAgbW9kaWZpYWJsZTogZXZlbnRQYXJ0Py5tb2RpZmlhYmxlLFxuICAgICAgICAgICAgaXNNZWV0aW5nOiBldmVudFBhcnQ/LmlzTWVldGluZyxcbiAgICAgICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nOiBldmVudFBhcnQ/LmlzRXh0ZXJuYWxNZWV0aW5nLFxuICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlOiBldmVudFBhcnQ/LmlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgICAgICAgIGlzTWVldGluZ01vZGlmaWFibGU6IGV2ZW50UGFydD8uaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgICAgICAgIGRhaWx5VGFza0xpc3Q6IGV2ZW50UGFydD8uZGFpbHlUYXNrTGlzdCxcbiAgICAgICAgICAgIHdlZWtseVRhc2tMaXN0OiBldmVudFBhcnQ/LndlZWtseVRhc2tMaXN0LFxuICAgICAgICAgICAgZ2FwOiBldmVudFBhcnQ/LmdhcCxcbiAgICAgICAgICAgIHRvdGFsV29ya2luZ0hvdXJzOiBldmVudFBhcnQ/LnRvdGFsV29ya2luZ0hvdXJzLFxuICAgICAgICAgICAgaGFyZERlYWRsaW5lOiBldmVudFBhcnQ/LmhhcmREZWFkbGluZSxcbiAgICAgICAgICAgIHNvZnREZWFkbGluZTogZXZlbnRQYXJ0Py5zb2Z0RGVhZGxpbmUsXG4gICAgICAgICAgICBmb3JFdmVudElkOiBldmVudFBhcnQ/LmZvckV2ZW50SWQsXG4gICAgICAgICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2VlazogZXZlbnRQYXJ0Py5wb3NpdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0VGltZTogZXZlbnRQYXJ0Py5wb3NpdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2VlazogZXZlbnRQYXJ0Py5uZWdhdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZTogZXZlbnRQYXJ0Py5uZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgICAgICBwcmVmZXJyZWREYXlPZldlZWs6IGV2ZW50UGFydD8ucHJlZmVycmVkRGF5T2ZXZWVrLFxuICAgICAgICAgICAgcHJlZmVycmVkVGltZTogZXZlbnRQYXJ0Py5wcmVmZXJyZWRUaW1lLFxuICAgICAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U6IGV2ZW50UGFydD8ucHJlZmVycmVkU3RhcnRUaW1lUmFuZ2UsXG4gICAgICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2U6IGV2ZW50UGFydD8ucHJlZmVycmVkRW5kVGltZVJhbmdlLFxuICAgICAgICAgICAgZXZlbnQ6IGV2ZW50UGFydD8uZXZlbnQsXG4gICAgICAgICAgfTtcbiAgICAgICAgfSk7XG5cbiAgICAgIG1vZGlmaWVkTmV3RXZlbnRQYXJ0cz8uZm9yRWFjaCgoZSkgPT5cbiAgICAgICAgY29uc29sZS5sb2coZSwgJyBtb2RpZmllZE5ld0V2ZW50UGFydHMnKVxuICAgICAgKTtcblxuICAgICAgcmV0dXJuIG1vZGlmaWVkTmV3RXZlbnRQYXJ0cz8ubGVuZ3RoID4gMFxuICAgICAgICA/IHtcbiAgICAgICAgICAgIHVzZXJJZHM6IGludGVybmFsQXR0ZW5kZWVzLm1hcCgoYSkgPT4gYS51c2VySWQpLFxuICAgICAgICAgICAgaG9zdElkOiBtYWluSG9zdElkLFxuICAgICAgICAgICAgZXZlbnRQYXJ0czogbW9kaWZpZWROZXdFdmVudFBhcnRzLFxuICAgICAgICAgICAgYWxsRXZlbnRzOiBmaWx0ZXJlZEFsbEV2ZW50cyxcbiAgICAgICAgICAgIGJyZWFrczogcGFyZW50QnJlYWtzLFxuICAgICAgICAgICAgb2xkRXZlbnRzLFxuICAgICAgICAgICAgdGltZXNsb3RzLFxuICAgICAgICAgICAgdXNlckxpc3QsXG4gICAgICAgICAgfVxuICAgICAgICA6IG51bGw7XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBlLFxuICAgICAgJyB1bmFibGUgdG8gcHJvY2VzcyBldmVudHMgZm9yIG9wdGFwbGFubmVyIGZvciBlYWNoIGF0dGVuZGVlJ1xuICAgICk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjb252ZXJ0TWVldGluZ0Fzc2lzdEV2ZW50VHlwZVRvRXZlbnRQbHVzVHlwZSA9IChcbiAgZXZlbnQ6IE1lZXRpbmdBc3Npc3RFdmVudFR5cGUsXG4gIHVzZXJJZDogc3RyaW5nXG4pOiBFdmVudFBsdXNUeXBlID0+IHtcbiAgcmV0dXJuIHtcbiAgICBpZDogZXZlbnQ/LmlkLFxuICAgIHVzZXJJZDogdXNlcklkLFxuICAgIHRpdGxlOiBldmVudD8uc3VtbWFyeSxcbiAgICBzdGFydERhdGU6IGV2ZW50Py5zdGFydERhdGUsXG4gICAgZW5kRGF0ZTogZXZlbnQ/LmVuZERhdGUsXG4gICAgYWxsRGF5OiBldmVudD8uYWxsRGF5LFxuICAgIHJlY3VycmVuY2VSdWxlOiBldmVudD8ucmVjdXJyZW5jZVJ1bGUsXG4gICAgbG9jYXRpb246IGV2ZW50Py5sb2NhdGlvbixcbiAgICBub3RlczogZXZlbnQ/Lm5vdGVzLFxuICAgIGF0dGFjaG1lbnRzOiBldmVudD8uYXR0YWNobWVudHMsXG4gICAgbGlua3M6IGV2ZW50Py5saW5rcyxcbiAgICB0aW1lem9uZTogZXZlbnQ/LnRpbWV6b25lLFxuICAgIGNyZWF0ZWREYXRlOiBldmVudD8uY3JlYXRlZERhdGUsXG4gICAgZGVsZXRlZDogZmFsc2UsXG4gICAgcHJpb3JpdHk6IDEsXG4gICAgaXNGb2xsb3dVcDogZmFsc2UsXG4gICAgaXNQcmVFdmVudDogZmFsc2UsXG4gICAgaXNQb3N0RXZlbnQ6IGZhbHNlLFxuICAgIG1vZGlmaWFibGU6IGZhbHNlLFxuICAgIGFueW9uZUNhbkFkZFNlbGY6IHRydWUsXG4gICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiB0cnVlLFxuICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOiB0cnVlLFxuICAgIG9yaWdpbmFsU3RhcnREYXRlOiB1bmRlZmluZWQsXG4gICAgb3JpZ2luYWxBbGxEYXk6IGZhbHNlLFxuICAgIHN1bW1hcnk6IGV2ZW50Py5zdW1tYXJ5LFxuICAgIHRyYW5zcGFyZW5jeTogZXZlbnQ/LnRyYW5zcGFyZW5jeSxcbiAgICB2aXNpYmlsaXR5OiBldmVudD8udmlzaWJpbGl0eSxcbiAgICByZWN1cnJpbmdFdmVudElkOiBldmVudD8ucmVjdXJyaW5nRXZlbnRJZCxcbiAgICB1cGRhdGVkQXQ6IGV2ZW50Py51cGRhdGVkQXQsXG4gICAgaUNhbFVJRDogZXZlbnQ/LmlDYWxVSUQsXG4gICAgaHRtbExpbms6IGV2ZW50Py5odG1sTGluayxcbiAgICBjb2xvcklkOiBldmVudD8uY29sb3JJZCxcbiAgICBjcmVhdG9yOiBldmVudD8uY3JlYXRvcixcbiAgICBvcmdhbml6ZXI6IGV2ZW50Py5vcmdhbml6ZXIsXG4gICAgZW5kVGltZVVuc3BlY2lmaWVkOiBldmVudD8uZW5kVGltZVVuc3BlY2lmaWVkLFxuICAgIHJlY3VycmVuY2U6IGV2ZW50Py5yZWN1cnJlbmNlLFxuICAgIG9yaWdpbmFsVGltZXpvbmU6IGV2ZW50Py50aW1lem9uZSxcbiAgICBleHRlbmRlZFByb3BlcnRpZXM6IGV2ZW50Py5leHRlbmRlZFByb3BlcnRpZXMsXG4gICAgaGFuZ291dExpbms6IGV2ZW50Py5oYW5nb3V0TGluayxcbiAgICBndWVzdHNDYW5Nb2RpZnk6IGV2ZW50Py5ndWVzdHNDYW5Nb2RpZnksXG4gICAgbG9ja2VkOiBldmVudD8ubG9ja2VkLFxuICAgIHNvdXJjZTogZXZlbnQ/LnNvdXJjZSxcbiAgICBldmVudFR5cGU6IGV2ZW50Py5ldmVudFR5cGUsXG4gICAgcHJpdmF0ZUNvcHk6IGV2ZW50Py5wcml2YXRlQ29weSxcbiAgICBjYWxlbmRhcklkOiBldmVudD8uY2FsZW5kYXJJZCxcbiAgICBiYWNrZ3JvdW5kQ29sb3I6IGV2ZW50Py5iYWNrZ3JvdW5kQ29sb3IsXG4gICAgZm9yZWdyb3VuZENvbG9yOiBldmVudD8uZm9yZWdyb3VuZENvbG9yLFxuICAgIHVzZURlZmF1bHRBbGFybXM6IGV2ZW50Py51c2VEZWZhdWx0QWxhcm1zLFxuICAgIG1lZXRpbmdJZDogZXZlbnQ/Lm1lZXRpbmdJZCxcbiAgICBldmVudElkOiBldmVudD8uZXZlbnRJZCxcbiAgfTtcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZVdvcmtUaW1lc0ZvckV4dGVybmFsQXR0ZW5kZWUgPSAoXG4gIGhvc3RJZDogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgYXR0ZW5kZWVFdmVudHM6IEV2ZW50UGx1c1R5cGVbXSxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIHVzZXJUaW1lem9uZTogc3RyaW5nXG4pID0+IHtcbiAgY29uc3QgZGF5c0luV2VlayA9IDc7XG5cbiAgY29uc3Qgd29ya1RpbWVzOiBXb3JrVGltZVR5cGVbXSA9IFtdO1xuXG4gIGZvciAobGV0IGkgPSAwOyBpIDwgZGF5c0luV2VlazsgaSsrKSB7XG4gICAgY29uc3QgZGF5T2ZXZWVrSW50ID0gaSArIDE7XG5cbiAgICBjb25zdCBzYW1lRGF5RXZlbnRzID0gYXR0ZW5kZWVFdmVudHMuZmlsdGVyKFxuICAgICAgKGUpID0+XG4gICAgICAgIGdldElTT0RheShcbiAgICAgICAgICBkYXlqcyhlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLnRvRGF0ZSgpXG4gICAgICAgICkgPT09XG4gICAgICAgIGkgKyAxXG4gICAgKTtcbiAgICBjb25zdCBtaW5TdGFydERhdGUgPSBfLm1pbkJ5KHNhbWVEYXlFdmVudHMsIChlKSA9PlxuICAgICAgZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC51bml4KClcbiAgICApO1xuICAgIGNvbnN0IG1heEVuZERhdGUgPSBfLm1heEJ5KHNhbWVEYXlFdmVudHMsIChlKSA9PlxuICAgICAgZGF5anMoZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAudW5peCgpXG4gICAgKTtcbiAgICBjb25zdCBzdGFydEhvdXIgPSBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihtaW5TdGFydERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgY29uc3Qgc3RhcnRNaW51dGUgPSBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihtaW5TdGFydERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtaW5TdGFydERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLm1pbnV0ZSgwKSxcbiAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICdbKSdcbiAgICAgIClcbiAgICAgID8gMFxuICAgICAgOiBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihtaW5TdGFydERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgID8gMTVcbiAgICAgICAgOiBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAgIC5taW51dGUoNDUpLFxuICAgICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgICAgKVxuICAgICAgICAgID8gMzBcbiAgICAgICAgICA6IDQ1O1xuXG4gICAgbGV0IGVuZEhvdXIgPSBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgY29uc3QgZW5kTWludXRlID0gZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihtYXhFbmREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtYXhFbmREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoMCksXG4gICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICdtaW51dGUnLFxuICAgICAgICAnWyknXG4gICAgICApXG4gICAgICA/IDE1XG4gICAgICA6IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgIClcbiAgICAgICAgPyAzMFxuICAgICAgICA6IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihtYXhFbmREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgLm1pbnV0ZSg0NSksXG4gICAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgICApXG4gICAgICAgICAgPyA0NVxuICAgICAgICAgIDogMDtcbiAgICBpZiAoZW5kTWludXRlID09PSAwKSB7XG4gICAgICBpZiAoZW5kSG91ciA8IDIzKSB7XG4gICAgICAgIGVuZEhvdXIgKz0gMTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICB3b3JrVGltZXMucHVzaCh7XG4gICAgICBkYXlPZldlZWs6IGRheU9mV2Vla0ludFRvU3RyaW5nW2RheU9mV2Vla0ludF0sXG4gICAgICBzdGFydFRpbWU6IGRheWpzKFxuICAgICAgICBzZXRJU09EYXkoXG4gICAgICAgICAgZGF5anMoKVxuICAgICAgICAgICAgLmhvdXIoc3RhcnRIb3VyKVxuICAgICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudG9EYXRlKCksXG4gICAgICAgICAgaSArIDFcbiAgICAgICAgKVxuICAgICAgKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICBlbmRUaW1lOiBkYXlqcyhcbiAgICAgICAgc2V0SVNPRGF5KFxuICAgICAgICAgIGRheWpzKClcbiAgICAgICAgICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudG9EYXRlKCksXG4gICAgICAgICAgaSArIDFcbiAgICAgICAgKVxuICAgICAgKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICBob3N0SWQsXG4gICAgICB1c2VySWQsXG4gICAgfSk7XG4gIH1cblxuICByZXR1cm4gd29ya1RpbWVzO1xufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlVGltZVNsb3RzRm9yRXh0ZXJuYWxBdHRlbmRlZSA9IChcbiAgaG9zdFN0YXJ0RGF0ZTogc3RyaW5nLFxuICBob3N0SWQ6IHN0cmluZyxcbiAgYXR0ZW5kZWVFdmVudHM6IEV2ZW50UGx1c1R5cGVbXSxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIHVzZXJUaW1lem9uZTogc3RyaW5nLFxuICBpc0ZpcnN0RGF5PzogYm9vbGVhblxuKSA9PiB7XG4gIGlmIChpc0ZpcnN0RGF5KSB7XG4gICAgY29uc3QgZGF5T2ZXZWVrSW50QnlIb3N0ID0gZ2V0SVNPRGF5KFxuICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkudG9EYXRlKClcbiAgICApO1xuICAgIC8vIGNvbnZlcnQgdG8gaG9zdCB0aW1lem9uZSBzbyBldmVyeXRoaW5nIGlzIGxpbmtlZCB0byBob3N0IHRpbWV6b25lXG4gICAgY29uc3QgbW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAubW9udGgoKTtcbiAgICBjb25zdCBkYXlPZk1vbnRoQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmRhdGUoKTtcbiAgICBjb25zdCBzdGFydEhvdXJPZkhvc3REYXRlQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmhvdXIoKTtcbiAgICBjb25zdCBzdGFydE1pbnV0ZU9mSG9zdERhdGVCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS5taW51dGUoMCksXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLm1pbnV0ZSgxNSksXG4gICAgICAgICdtaW51dGUnLFxuICAgICAgICAnWyknXG4gICAgICApXG4gICAgICA/IDBcbiAgICAgIDogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgIClcbiAgICAgICAgPyAxNVxuICAgICAgICA6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAgIC5taW51dGUoNDUpLFxuICAgICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgICAgKVxuICAgICAgICAgID8gMzBcbiAgICAgICAgICA6IDQ1O1xuXG4gICAgY29uc3Qgc2FtZURheUV2ZW50cyA9IGF0dGVuZGVlRXZlbnRzLmZpbHRlcihcbiAgICAgIChlKSA9PlxuICAgICAgICBnZXRJU09EYXkoXG4gICAgICAgICAgZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAudG9EYXRlKClcbiAgICAgICAgKSA9PT0gZGF5T2ZXZWVrSW50QnlIb3N0XG4gICAgKTtcbiAgICAvLyBjb25zdCBtaW5TdGFydERhdGUgPSBfLm1pbkJ5KHNhbWVEYXlFdmVudHMsIChlKSA9PiBkYXlqcyhlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KHVzZXJUaW1lem9uZSwgdHJ1ZSkudHooaG9zdFRpbWV6b25lKS51bml4KCkpXG4gICAgY29uc3QgbWF4RW5kRGF0ZSA9IF8ubWF4Qnkoc2FtZURheUV2ZW50cywgKGUpID0+XG4gICAgICBkYXlqcyhlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoodXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAudW5peCgpXG4gICAgKTtcblxuICAgIGxldCB3b3JrRW5kSG91ckJ5SG9zdCA9IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmhvdXIoKTtcbiAgICBjb25zdCB3b3JrRW5kTWludXRlQnlIb3N0ID0gZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihtYXhFbmREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtYXhFbmREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoMCksXG4gICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICdtaW51dGUnLFxuICAgICAgICAnWyknXG4gICAgICApXG4gICAgICA/IDE1XG4gICAgICA6IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgIClcbiAgICAgICAgPyAzMFxuICAgICAgICA6IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihtYXhFbmREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgLm1pbnV0ZSg0NSksXG4gICAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgICApXG4gICAgICAgICAgPyA0NVxuICAgICAgICAgIDogMDtcbiAgICBpZiAod29ya0VuZE1pbnV0ZUJ5SG9zdCA9PT0gMCkge1xuICAgICAgaWYgKHdvcmtFbmRIb3VyQnlIb3N0IDwgMjMpIHtcbiAgICAgICAgd29ya0VuZEhvdXJCeUhvc3QgKz0gMTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBtaW5TdGFydERhdGUgPSBfLm1pbkJ5KHNhbWVEYXlFdmVudHMsIChlKSA9PlxuICAgICAgZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoodXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAudW5peCgpXG4gICAgKTtcblxuICAgIGNvbnN0IHdvcmtTdGFydEhvdXJCeUhvc3QgPSBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihtaW5TdGFydERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgY29uc3Qgd29ya1N0YXJ0TWludXRlQnlIb3N0ID0gZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoMCksXG4gICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtaW5TdGFydERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICdtaW51dGUnLFxuICAgICAgICAnWyknXG4gICAgICApXG4gICAgICA/IDBcbiAgICAgIDogZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMTUpLFxuICAgICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDE1XG4gICAgICAgIDogZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAubWludXRlKDQ1KSxcbiAgICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICAgIClcbiAgICAgICAgICA/IDMwXG4gICAgICAgICAgOiA0NTtcblxuICAgIC8vIGNoYW5nZSB0byB3b3JrIHN0YXJ0IHRpbWUgYXMgd29yayBzdGFydCB0aW1lIGlzICBhZnRlciBob3N0IHN0YXJ0IHRpbWVcbiAgICBpZiAoXG4gICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmlzQmVmb3JlKFxuICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXJCeUhvc3QpXG4gICAgICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgKVxuICAgICkge1xuICAgICAgY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgICAgaG91cnM6IHdvcmtTdGFydEhvdXJCeUhvc3QsXG4gICAgICAgIG1pbnV0ZXM6IHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCxcbiAgICAgIH0pO1xuICAgICAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICAgIGhvdXJzOiB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAgICAgbWludXRlczogd29ya0VuZE1pbnV0ZUJ5SG9zdCxcbiAgICAgIH0pO1xuICAgICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgICAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcblxuICAgICAgY29uc3QgdGltZVNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuXG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgaG9zdFN0YXJ0RGF0ZSxcbiAgICAgICAgZGF5T2ZXZWVrSW50QnlIb3N0LFxuICAgICAgICBkYXlPZk1vbnRoQnlIb3N0LFxuICAgICAgICBzdGFydEhvdXJPZkhvc3REYXRlQnlIb3N0LFxuICAgICAgICBzdGFydE1pbnV0ZU9mSG9zdERhdGVCeUhvc3QsXG4gICAgICAgIHdvcmtFbmRIb3VyQnlIb3N0LFxuICAgICAgICB3b3JrRW5kTWludXRlQnlIb3N0LFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgYHN0YXJ0RGF0ZSwgIGRheU9mV2Vla0ludEJ5SG9zdCwgZGF5T2ZNb250aEJ5SG9zdCwgc3RhcnRIb3VyQnlIb3N0LCBzdGFydE1pbnV0ZUJ5SG9zdCwgZW5kSG91ckJ5SG9zdCwgZW5kTWludXRlQnlIb3N0IHRvdGFsTWludXRlcywgdGltZXpvbmUsIGluc2lkZSBmaXJzdERheSBpbnNpZGUgZ2VuZXJhdGVUaW1lc2xvdHNgXG4gICAgICApO1xuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gMTUpIHtcbiAgICAgICAgdGltZVNsb3RzLnB1c2goe1xuICAgICAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50QnlIb3N0XSxcbiAgICAgICAgICBzdGFydFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QpXG4gICAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdClcbiAgICAgICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICAgICAgZW5kVGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmhvdXIoc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdClcbiAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVPZkhvc3REYXRlQnlIb3N0KVxuICAgICAgICAgICAgLmFkZChpICsgMTUsICdtaW51dGUnKVxuICAgICAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgICAgIGhvc3RJZCxcbiAgICAgICAgICBtb250aERheTogZm9ybWF0VG9Nb250aERheShcbiAgICAgICAgICAgIG1vbnRoQnlIb3N0IGFzIE1vbnRoVHlwZSxcbiAgICAgICAgICAgIGRheU9mTW9udGhCeUhvc3QgYXMgRGF5VHlwZVxuICAgICAgICAgICksXG4gICAgICAgICAgZGF0ZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERCcpLFxuICAgICAgICB9KTtcbiAgICAgIH1cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICB0aW1lU2xvdHMsXG4gICAgICAgICcgdGltZVNsb3RzIGluc2lkZSBnZW5lcmF0ZVRpbWVTbG90cyBmb3IgZmlyc3QgZGF5IHdoZXJlIHN0YXJ0RGF0ZSBpcyBiZWZvcmUgd29yayBzdGFydCB0aW1lJ1xuICAgICAgKTtcbiAgICAgIHJldHVybiB0aW1lU2xvdHM7XG4gICAgfVxuXG4gICAgY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgIGhvdXJzOiBzdGFydEhvdXJPZkhvc3REYXRlQnlIb3N0LFxuICAgICAgbWludXRlczogc3RhcnRNaW51dGVPZkhvc3REYXRlQnlIb3N0LFxuICAgIH0pO1xuICAgIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgaG91cnM6IHdvcmtFbmRIb3VyQnlIb3N0LFxuICAgICAgbWludXRlczogd29ya0VuZE1pbnV0ZUJ5SG9zdCxcbiAgICB9KTtcbiAgICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gICAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcblxuICAgIGNvbnN0IHRpbWVTbG90czogVGltZVNsb3RUeXBlW10gPSBbXTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGhvc3RTdGFydERhdGUsXG4gICAgICBkYXlPZldlZWtJbnRCeUhvc3QsXG4gICAgICBkYXlPZk1vbnRoQnlIb3N0LFxuICAgICAgc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdCxcbiAgICAgIHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdCxcbiAgICAgIHdvcmtFbmRIb3VyQnlIb3N0LFxuICAgICAgd29ya0VuZE1pbnV0ZUJ5SG9zdCxcbiAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIGBzdGFydERhdGUsICBkYXlPZldlZWtJbnRCeUhvc3QsIGRheU9mTW9udGgsIHN0YXJ0SG91ciwgc3RhcnRNaW51dGUsIGVuZEhvdXIsIGVuZE1pbnV0ZSB0b3RhbE1pbnV0ZXMsIHRpbWV6b25lLCBpbnNpZGUgZmlyc3REYXkgaW5zaWRlIGdlbmVyYXRlVGltZXNsb3RzYFxuICAgICk7XG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gMTUpIHtcbiAgICAgIHRpbWVTbG90cy5wdXNoKHtcbiAgICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1tkYXlPZldlZWtJbnRCeUhvc3RdLFxuICAgICAgICBzdGFydFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdClcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdClcbiAgICAgICAgICAuYWRkKGksICdtaW51dGUnKVxuICAgICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgICAgZW5kVGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuaG91cihzdGFydEhvdXJPZkhvc3REYXRlQnlIb3N0KVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVPZkhvc3REYXRlQnlIb3N0KVxuICAgICAgICAgIC5hZGQoaSArIDE1LCAnbWludXRlJylcbiAgICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICAgIGhvc3RJZCxcbiAgICAgICAgbW9udGhEYXk6IGZvcm1hdFRvTW9udGhEYXkoXG4gICAgICAgICAgbW9udGhCeUhvc3QgYXMgTW9udGhUeXBlLFxuICAgICAgICAgIGRheU9mTW9udGhCeUhvc3QgYXMgRGF5VHlwZVxuICAgICAgICApLFxuICAgICAgICBkYXRlOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICAgIH0pO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKHRpbWVTbG90cywgJyB0aW1lU2xvdHMgaW5zaWRlIGdlbmVyYXRlVGltZVNsb3RzIGZvciBmaXJzdCBkYXknKTtcbiAgICByZXR1cm4gdGltZVNsb3RzO1xuICB9XG5cbiAgLy8gbm90IGZpcnN0IGRheSBzdGFydCBmcm9tIHdvcmsgc3RhcnQgdGltZSBzY2hlZHVsZVxuXG4gIGNvbnN0IGRheU9mV2Vla0ludEJ5SG9zdCA9IGdldElTT0RheShcbiAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICApO1xuICAvLyBjb252ZXJ0IHRvIGhvc3QgdGltZXpvbmUgc28gZXZlcnl0aGluZyBpcyBsaW5rZWQgdG8gaG9zdCB0aW1lem9uZVxuICBjb25zdCBtb250aEJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLm1vbnRoKCk7XG4gIGNvbnN0IGRheU9mTW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgIC5kYXRlKCk7XG5cbiAgY29uc3Qgc2FtZURheUV2ZW50cyA9IGF0dGVuZGVlRXZlbnRzLmZpbHRlcihcbiAgICAoZSkgPT5cbiAgICAgIGdldElTT0RheShcbiAgICAgICAgZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC50b0RhdGUoKVxuICAgICAgKSA9PT0gZGF5T2ZXZWVrSW50QnlIb3N0XG4gICk7XG4gIGNvbnN0IG1pblN0YXJ0RGF0ZSA9IF8ubWluQnkoc2FtZURheUV2ZW50cywgKGUpID0+XG4gICAgZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC51bml4KClcbiAgKTtcbiAgY29uc3QgbWF4RW5kRGF0ZSA9IF8ubWF4Qnkoc2FtZURheUV2ZW50cywgKGUpID0+XG4gICAgZGF5anMoZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAudW5peCgpXG4gICk7XG5cbiAgbGV0IHdvcmtFbmRIb3VyQnlIb3N0ID0gZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmhvdXIoKTtcbiAgY29uc3Qgd29ya0VuZE1pbnV0ZUJ5SG9zdCA9IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5pc0JldHdlZW4oXG4gICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAubWludXRlKDApLFxuICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAnbWludXRlJyxcbiAgICAgICdbKSdcbiAgICApXG4gICAgPyAxNVxuICAgIDogZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5taW51dGUoMTUpLFxuICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICdbKSdcbiAgICAgICAgICApXG4gICAgICA/IDMwXG4gICAgICA6IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDQ1KSxcbiAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgIClcbiAgICAgICAgPyA0NVxuICAgICAgICA6IDA7XG4gIGlmICh3b3JrRW5kTWludXRlQnlIb3N0ID09PSAwKSB7XG4gICAgaWYgKHdvcmtFbmRIb3VyQnlIb3N0IDwgMjMpIHtcbiAgICAgIHdvcmtFbmRIb3VyQnlIb3N0ICs9IDE7XG4gICAgfVxuICB9XG5cbiAgY29uc3Qgd29ya1N0YXJ0SG91ckJ5SG9zdCA9IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5ob3VyKCk7XG4gIGNvbnN0IHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCA9IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5pc0JldHdlZW4oXG4gICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAubWludXRlKDApLFxuICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAnbWludXRlJyxcbiAgICAgICdbKSdcbiAgICApXG4gICAgPyAwXG4gICAgOiBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgIClcbiAgICAgID8gMTVcbiAgICAgIDogZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoNDUpLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDMwXG4gICAgICAgIDogNDU7XG5cbiAgY29uc29sZS5sb2coXG4gICAgbW9udGhCeUhvc3QsXG4gICAgZGF5T2ZNb250aEJ5SG9zdCxcbiAgICB3b3JrU3RhcnRIb3VyQnlIb3N0LFxuICAgIHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCxcbiAgICB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAnIG1vbnRoQnlIb3N0LCBkYXlPZk1vbnRoQnlIb3N0LCB3b3JrU3RhcnRIb3VyQnlIb3N0LCB3b3JrU3RhcnRNaW51dGVCeUhvc3QsIHdvcmtFbmRIb3VyQnlIb3N0J1xuICApO1xuICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiB3b3JrU3RhcnRIb3VyQnlIb3N0LFxuICAgIG1pbnV0ZXM6IHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCxcbiAgfSk7XG4gIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICBtaW51dGVzOiB3b3JrRW5kTWludXRlQnlIb3N0LFxuICB9KTtcbiAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICBjb25zdCB0b3RhbE1pbnV0ZXMgPSB0b3RhbER1cmF0aW9uLmFzTWludXRlcygpO1xuICBjb25zdCB0aW1lU2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG4gIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IDE1KSB7XG4gICAgdGltZVNsb3RzLnB1c2goe1xuICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1tkYXlPZldlZWtJbnRCeUhvc3RdLFxuICAgICAgc3RhcnRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgLmFkZChpICsgMTUsICdtaW51dGUnKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICBob3N0SWQsXG4gICAgICBtb250aERheTogZm9ybWF0VG9Nb250aERheShcbiAgICAgICAgbW9udGhCeUhvc3QgYXMgTW9udGhUeXBlLFxuICAgICAgICBkYXlPZk1vbnRoQnlIb3N0IGFzIERheVR5cGVcbiAgICAgICksXG4gICAgICBkYXRlOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERCcpLFxuICAgIH0pO1xuICB9XG5cbiAgY29uc29sZS5sb2codGltZVNsb3RzLCAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMnKTtcbiAgcmV0dXJuIHRpbWVTbG90cztcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZVRpbWVTbG90c0xpdGVGb3JFeHRlcm5hbEF0dGVuZGVlID0gKFxuICBob3N0U3RhcnREYXRlOiBzdHJpbmcsXG4gIGhvc3RJZDogc3RyaW5nLFxuICBhdHRlbmRlZUV2ZW50czogRXZlbnRQbHVzVHlwZVtdLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgdXNlclRpbWV6b25lOiBzdHJpbmcsXG4gIGlzRmlyc3REYXk/OiBib29sZWFuXG4pID0+IHtcbiAgaWYgKGlzRmlyc3REYXkpIHtcbiAgICBjb25zdCBkYXlPZldlZWtJbnRCeUhvc3QgPSBnZXRJU09EYXkoXG4gICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICAgICk7XG4gICAgLy8gY29udmVydCB0byBob3N0IHRpbWV6b25lIHNvIGV2ZXJ5dGhpbmcgaXMgbGlua2VkIHRvIGhvc3QgdGltZXpvbmVcbiAgICBjb25zdCBtb250aEJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5tb250aCgpO1xuICAgIGNvbnN0IGRheU9mTW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuZGF0ZSgpO1xuICAgIGNvbnN0IHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLm1pbnV0ZSgwKSxcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkubWludXRlKDMwKSxcbiAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICdbKSdcbiAgICAgIClcbiAgICAgID8gMFxuICAgICAgOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoNTkpLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDMwXG4gICAgICAgIDogMDtcblxuICAgIGNvbnN0IHNhbWVEYXlFdmVudHMgPSBhdHRlbmRlZUV2ZW50cy5maWx0ZXIoXG4gICAgICAoZSkgPT5cbiAgICAgICAgZ2V0SVNPRGF5KFxuICAgICAgICAgIGRheWpzKGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLnRvRGF0ZSgpXG4gICAgICAgICkgPT09IGRheU9mV2Vla0ludEJ5SG9zdFxuICAgICk7XG4gICAgLy8gY29uc3QgbWluU3RhcnREYXRlID0gXy5taW5CeShzYW1lRGF5RXZlbnRzLCAoZSkgPT4gZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eih1c2VyVGltZXpvbmUsIHRydWUpLnR6KGhvc3RUaW1lem9uZSkudW5peCgpKVxuICAgIGNvbnN0IG1heEVuZERhdGUgPSBfLm1heEJ5KHNhbWVEYXlFdmVudHMsIChlKSA9PlxuICAgICAgZGF5anMoZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLnVuaXgoKVxuICAgICk7XG5cbiAgICBsZXQgd29ya0VuZEhvdXJCeUhvc3QgPSBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHdvcmtFbmRNaW51dGVCeUhvc3QgPSBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKDApLFxuICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICdbKSdcbiAgICAgIClcbiAgICAgID8gMzBcbiAgICAgIDogZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoNTkpLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDBcbiAgICAgICAgOiAzMDtcbiAgICBpZiAod29ya0VuZE1pbnV0ZUJ5SG9zdCA9PT0gMCkge1xuICAgICAgaWYgKHdvcmtFbmRIb3VyQnlIb3N0IDwgMjMpIHtcbiAgICAgICAgd29ya0VuZEhvdXJCeUhvc3QgKz0gMTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBtaW5TdGFydERhdGUgPSBfLm1pbkJ5KHNhbWVEYXlFdmVudHMsIChlKSA9PlxuICAgICAgZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAudW5peCgpXG4gICAgKTtcblxuICAgIGNvbnN0IHdvcmtTdGFydEhvdXJCeUhvc3QgPSBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCA9IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoMCksXG4gICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAnbWludXRlJyxcbiAgICAgICAgJ1spJ1xuICAgICAgKVxuICAgICAgPyAwXG4gICAgICA6IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDU5KSxcbiAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgIClcbiAgICAgICAgPyAzMFxuICAgICAgICA6IDA7XG5cbiAgICAvLyBjaGFuZ2UgdG8gd29yayBzdGFydCB0aW1lIGFzIHdvcmsgc3RhcnQgdGltZSBpcyAgYWZ0ZXIgaG9zdCBzdGFydCB0aW1lXG4gICAgaWYgKFxuICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5pc0JlZm9yZShcbiAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICAgIGhvdXJzOiB3b3JrU3RhcnRIb3VyQnlIb3N0LFxuICAgICAgICBtaW51dGVzOiB3b3JrU3RhcnRNaW51dGVCeUhvc3QsXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgICBob3Vyczogd29ya0VuZEhvdXJCeUhvc3QsXG4gICAgICAgIG1pbnV0ZXM6IHdvcmtFbmRNaW51dGVCeUhvc3QsXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgICAgIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG5cbiAgICAgIGNvbnN0IHRpbWVTbG90czogVGltZVNsb3RUeXBlW10gPSBbXTtcblxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGhvc3RTdGFydERhdGUsXG4gICAgICAgIGRheU9mV2Vla0ludEJ5SG9zdCxcbiAgICAgICAgZGF5T2ZNb250aEJ5SG9zdCxcbiAgICAgICAgc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdCxcbiAgICAgICAgc3RhcnRNaW51dGVPZkhvc3REYXRlQnlIb3N0LFxuICAgICAgICB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAgICAgd29ya0VuZE1pbnV0ZUJ5SG9zdCxcbiAgICAgICAgdGltZXpvbmUsXG4gICAgICAgIGBzdGFydERhdGUsICBkYXlPZldlZWtJbnRCeUhvc3QsIGRheU9mTW9udGhCeUhvc3QsIHN0YXJ0SG91ckJ5SG9zdCwgc3RhcnRNaW51dGVCeUhvc3QsIGVuZEhvdXJCeUhvc3QsIGVuZE1pbnV0ZUJ5SG9zdCB0b3RhbE1pbnV0ZXMsIHRpbWV6b25lLCBpbnNpZGUgZmlyc3REYXkgaW5zaWRlIGdlbmVyYXRlVGltZXNsb3RzYFxuICAgICAgKTtcbiAgICAgIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IDMwKSB7XG4gICAgICAgIHRpbWVTbG90cy5wdXNoKHtcbiAgICAgICAgICBkYXlPZldlZWs6IGRheU9mV2Vla0ludFRvU3RyaW5nW2RheU9mV2Vla0ludEJ5SG9zdF0sXG4gICAgICAgICAgc3RhcnRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cihzdGFydEhvdXJPZkhvc3REYXRlQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZU9mSG9zdERhdGVCeUhvc3QpXG4gICAgICAgICAgICAuYWRkKGksICdtaW51dGUnKVxuICAgICAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QpXG4gICAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdClcbiAgICAgICAgICAgIC5hZGQoaSArIDMwLCAnbWludXRlJylcbiAgICAgICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgICAgICBob3N0SWQsXG4gICAgICAgICAgbW9udGhEYXk6IGZvcm1hdFRvTW9udGhEYXkoXG4gICAgICAgICAgICBtb250aEJ5SG9zdCBhcyBNb250aFR5cGUsXG4gICAgICAgICAgICBkYXlPZk1vbnRoQnlIb3N0IGFzIERheVR5cGVcbiAgICAgICAgICApLFxuICAgICAgICAgIGRhdGU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICAgICAgfSk7XG4gICAgICB9XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgdGltZVNsb3RzLFxuICAgICAgICAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMgZm9yIGZpcnN0IGRheSB3aGVyZSBzdGFydERhdGUgaXMgYmVmb3JlIHdvcmsgc3RhcnQgdGltZSdcbiAgICAgICk7XG4gICAgICByZXR1cm4gdGltZVNsb3RzO1xuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICBob3Vyczogc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdCxcbiAgICAgIG1pbnV0ZXM6IHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdCxcbiAgICB9KTtcbiAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgIGhvdXJzOiB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAgIG1pbnV0ZXM6IHdvcmtFbmRNaW51dGVCeUhvc3QsXG4gICAgfSk7XG4gICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG5cbiAgICBjb25zdCB0aW1lU2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG4gICAgY29uc29sZS5sb2coXG4gICAgICBob3N0U3RhcnREYXRlLFxuICAgICAgZGF5T2ZXZWVrSW50QnlIb3N0LFxuICAgICAgZGF5T2ZNb250aEJ5SG9zdCxcbiAgICAgIHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QsXG4gICAgICBzdGFydE1pbnV0ZU9mSG9zdERhdGVCeUhvc3QsXG4gICAgICB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAgIHdvcmtFbmRNaW51dGVCeUhvc3QsXG4gICAgICBob3N0VGltZXpvbmUsXG4gICAgICBgc3RhcnREYXRlLCAgZGF5T2ZXZWVrSW50QnlIb3N0LCBkYXlPZk1vbnRoLCBzdGFydEhvdXIsIHN0YXJ0TWludXRlLCBlbmRIb3VyLCBlbmRNaW51dGUgdG90YWxNaW51dGVzLCB0aW1lem9uZSwgaW5zaWRlIGZpcnN0RGF5IGluc2lkZSBnZW5lcmF0ZVRpbWVzbG90c2BcbiAgICApO1xuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IDMwKSB7XG4gICAgICB0aW1lU2xvdHMucHVzaCh7XG4gICAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50QnlIb3N0XSxcbiAgICAgICAgc3RhcnRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QpXG4gICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZU9mSG9zdERhdGVCeUhvc3QpXG4gICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdClcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdClcbiAgICAgICAgICAuYWRkKGkgKyAzMCwgJ21pbnV0ZScpXG4gICAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgICBob3N0SWQsXG4gICAgICAgIG1vbnRoRGF5OiBmb3JtYXRUb01vbnRoRGF5KFxuICAgICAgICAgIG1vbnRoQnlIb3N0IGFzIE1vbnRoVHlwZSxcbiAgICAgICAgICBkYXlPZk1vbnRoQnlIb3N0IGFzIERheVR5cGVcbiAgICAgICAgKSxcbiAgICAgICAgZGF0ZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgICB9KTtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyh0aW1lU2xvdHMsICcgdGltZVNsb3RzIGluc2lkZSBnZW5lcmF0ZVRpbWVTbG90cyBmb3IgZmlyc3QgZGF5Jyk7XG4gICAgcmV0dXJuIHRpbWVTbG90cztcbiAgfVxuXG4gIC8vIG5vdCBmaXJzdCBkYXkgc3RhcnQgZnJvbSB3b3JrIHN0YXJ0IHRpbWUgc2NoZWR1bGVcblxuICBjb25zdCBkYXlPZldlZWtJbnRCeUhvc3QgPSBnZXRJU09EYXkoXG4gICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkudG9EYXRlKClcbiAgKTtcbiAgLy8gY29udmVydCB0byBob3N0IHRpbWV6b25lIHNvIGV2ZXJ5dGhpbmcgaXMgbGlua2VkIHRvIGhvc3QgdGltZXpvbmVcbiAgY29uc3QgbW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgIC5tb250aCgpO1xuICBjb25zdCBkYXlPZk1vbnRoQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAuZGF0ZSgpO1xuXG4gIGNvbnN0IHNhbWVEYXlFdmVudHMgPSBhdHRlbmRlZUV2ZW50cy5maWx0ZXIoXG4gICAgKGUpID0+XG4gICAgICBnZXRJU09EYXkoXG4gICAgICAgIGRheWpzKGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoodXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLnRvRGF0ZSgpXG4gICAgICApID09PSBkYXlPZldlZWtJbnRCeUhvc3RcbiAgKTtcbiAgY29uc3QgbWluU3RhcnREYXRlID0gXy5taW5CeShzYW1lRGF5RXZlbnRzLCAoZSkgPT5cbiAgICBkYXlqcyhlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHoodXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC51bml4KClcbiAgKTtcbiAgY29uc3QgbWF4RW5kRGF0ZSA9IF8ubWF4Qnkoc2FtZURheUV2ZW50cywgKGUpID0+XG4gICAgZGF5anMoZS5lbmREYXRlLnNsaWNlKDAsIDE5KSkudHoodXNlclRpbWV6b25lLCB0cnVlKS50eihob3N0VGltZXpvbmUpLnVuaXgoKVxuICApO1xuXG4gIGxldCB3b3JrRW5kSG91ckJ5SG9zdCA9IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5ob3VyKCk7XG4gIGNvbnN0IHdvcmtFbmRNaW51dGVCeUhvc3QgPSBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAuaXNCZXR3ZWVuKFxuICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLm1pbnV0ZSgwKSxcbiAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5taW51dGUoMzApLFxuICAgICAgJ21pbnV0ZScsXG4gICAgICAnWyknXG4gICAgKVxuICAgID8gMzBcbiAgICA6IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5taW51dGUoNTkpLFxuICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAnWyknXG4gICAgICAgICAgKVxuICAgICAgPyAwXG4gICAgICA6IDMwO1xuICBpZiAod29ya0VuZE1pbnV0ZUJ5SG9zdCA9PT0gMCkge1xuICAgIGlmICh3b3JrRW5kSG91ckJ5SG9zdCA8IDIzKSB7XG4gICAgICB3b3JrRW5kSG91ckJ5SG9zdCArPSAxO1xuICAgIH1cbiAgfVxuXG4gIGNvbnN0IHdvcmtTdGFydEhvdXJCeUhvc3QgPSBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAuaG91cigpO1xuICBjb25zdCB3b3JrU3RhcnRNaW51dGVCeUhvc3QgPSBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAuaXNCZXR3ZWVuKFxuICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLm1pbnV0ZSgwKSxcbiAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5taW51dGUoMzApLFxuICAgICAgJ21pbnV0ZScsXG4gICAgICAnWyknXG4gICAgKVxuICAgID8gMFxuICAgIDogZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLm1pbnV0ZSg1OSksXG4gICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICdbKSdcbiAgICAgICAgICApXG4gICAgICA/IDMwXG4gICAgICA6IDA7XG5cbiAgY29uc29sZS5sb2coXG4gICAgbW9udGhCeUhvc3QsXG4gICAgZGF5T2ZNb250aEJ5SG9zdCxcbiAgICB3b3JrU3RhcnRIb3VyQnlIb3N0LFxuICAgIHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCxcbiAgICB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAnIG1vbnRoQnlIb3N0LCBkYXlPZk1vbnRoQnlIb3N0LCB3b3JrU3RhcnRIb3VyQnlIb3N0LCB3b3JrU3RhcnRNaW51dGVCeUhvc3QsIHdvcmtFbmRIb3VyQnlIb3N0J1xuICApO1xuICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiB3b3JrU3RhcnRIb3VyQnlIb3N0LFxuICAgIG1pbnV0ZXM6IHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCxcbiAgfSk7XG4gIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICBtaW51dGVzOiB3b3JrRW5kTWludXRlQnlIb3N0LFxuICB9KTtcbiAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICBjb25zdCB0b3RhbE1pbnV0ZXMgPSB0b3RhbER1cmF0aW9uLmFzTWludXRlcygpO1xuICBjb25zdCB0aW1lU2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG4gIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IDMwKSB7XG4gICAgdGltZVNsb3RzLnB1c2goe1xuICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1tkYXlPZldlZWtJbnRCeUhvc3RdLFxuICAgICAgc3RhcnRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgLmFkZChpICsgMzAsICdtaW51dGUnKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICBob3N0SWQsXG4gICAgICBtb250aERheTogZm9ybWF0VG9Nb250aERheShcbiAgICAgICAgbW9udGhCeUhvc3QgYXMgTW9udGhUeXBlLFxuICAgICAgICBkYXlPZk1vbnRoQnlIb3N0IGFzIERheVR5cGVcbiAgICAgICksXG4gICAgICBkYXRlOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERCcpLFxuICAgIH0pO1xuICB9XG5cbiAgY29uc29sZS5sb2codGltZVNsb3RzLCAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMnKTtcbiAgcmV0dXJuIHRpbWVTbG90cztcbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzRXZlbnRzRm9yT3B0YVBsYW5uZXJGb3JFeHRlcm5hbEF0dGVuZGVlcyA9IGFzeW5jIChcbiAgdXNlcklkczogc3RyaW5nW10sXG4gIG1haW5Ib3N0SWQ6IHN0cmluZyxcbiAgYWxsRXh0ZXJuYWxFdmVudHM6IE1lZXRpbmdBc3Npc3RFdmVudFR5cGVbXSwgLy8gVGhlc2UgYXJlIE1lZXRpbmdBc3Npc3RFdmVudHMgZnJvbSB0aGUgdXNlcidzIGNhbGVuZGFyIGNvbm5lY3Rpb25cbiAgd2luZG93U3RhcnREYXRlOiBzdHJpbmcsXG4gIHdpbmRvd0VuZERhdGU6IHN0cmluZyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIGV4dGVybmFsQXR0ZW5kZWVzOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10sXG4gIG9sZEV4dGVybmFsTWVldGluZ0V2ZW50cz86IEV2ZW50TWVldGluZ1BsdXNUeXBlW10sXG4gIG5ld01lZXRpbmdFdmVudHM/OiBFdmVudE1lZXRpbmdQbHVzVHlwZVtdLFxuICBtZWV0aW5nQXNzaXN0SWQ/OiBzdHJpbmcgLy8gQWRkZWQ6IElEIG9mIHRoZSBjdXJyZW50IG1lZXRpbmcgYXNzaXN0IGZvciBwcmVmZXJlbmNlIGxvb2t1cFxuKTogUHJvbWlzZTxSZXR1cm5Cb2R5Rm9yRXh0ZXJuYWxBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGU+ID0+IHtcbiAgdHJ5IHtcbiAgICAvLyBDb252ZXJ0IE1lZXRpbmdBc3Npc3RFdmVudFR5cGUgdG8gRXZlbnRQbHVzVHlwZSBmb3IgY29uc2lzdGVudCBwcm9jZXNzaW5nXG4gICAgLy8gVGhlc2UgZXZlbnRzIGFyZSB0eXBpY2FsbHkgZnJvbSB0aGUgZXh0ZXJuYWwgdXNlcidzIG93biBjYWxlbmRhciwgbm90IHNwZWNpZmljIG1lZXRpbmcgaW52aXRlcyB5ZXRcbiAgICBjb25zdCBiYXNlRXh0ZXJuYWxVc2VyRXZlbnRzID0gYWxsRXh0ZXJuYWxFdmVudHM/Lm1hcCgoZSkgPT5cbiAgICAgIGNvbnZlcnRNZWV0aW5nQXNzaXN0RXZlbnRUeXBlVG9FdmVudFBsdXNUeXBlKFxuICAgICAgICBlLFxuICAgICAgICBleHRlcm5hbEF0dGVuZGVlcz8uZmluZCgoYSkgPT4gYT8uaWQgPT09IGU/LmF0dGVuZGVlSWQpPy51c2VySWRcbiAgICAgIClcbiAgICApO1xuXG4gICAgbGV0IG1vZGlmaWVkQWxsRXh0ZXJuYWxFdmVudHMgPSBbLi4uYmFzZUV4dGVybmFsVXNlckV2ZW50c107XG5cbiAgICBjb25zdCBvbGRDb252ZXJ0ZWRNZWV0aW5nRXZlbnRzID0gb2xkRXh0ZXJuYWxNZWV0aW5nRXZlbnRzXG4gICAgICA/Lm1hcCgoYSkgPT4gY29udmVydE1lZXRpbmdQbHVzVHlwZVRvRXZlbnRQbHVzVHlwZShhKSlcbiAgICAgID8uZmlsdGVyKChlKSA9PiAhIWUpO1xuICAgIGlmIChvbGRDb252ZXJ0ZWRNZWV0aW5nRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICBtb2RpZmllZEFsbEV4dGVybmFsRXZlbnRzLnB1c2goLi4ub2xkQ29udmVydGVkTWVldGluZ0V2ZW50cyk7XG4gICAgfVxuXG4gICAgaWYgKG5ld01lZXRpbmdFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIG1vZGlmaWVkQWxsRXh0ZXJuYWxFdmVudHMucHVzaChcbiAgICAgICAgLi4ubmV3TWVldGluZ0V2ZW50cz8ubWFwKChtKSA9PlxuICAgICAgICAgIGNvbnZlcnRNZWV0aW5nUGx1c1R5cGVUb0V2ZW50UGx1c1R5cGUobSlcbiAgICAgICAgKVxuICAgICAgKTtcbiAgICB9XG5cbiAgICBjb25zdCBkaWZmRGF5cyA9IGRheWpzKHdpbmRvd0VuZERhdGUuc2xpY2UoMCwgMTkpKS5kaWZmKFxuICAgICAgZGF5anMod2luZG93U3RhcnREYXRlLnNsaWNlKDAsIDE5KSksXG4gICAgICAnZGF5J1xuICAgICk7XG5cbiAgICBjb25zdCBzdGFydERhdGVzRm9yRWFjaERheSA9IFtdO1xuXG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPD0gZGlmZkRheXM7IGkrKykge1xuICAgICAgc3RhcnREYXRlc0ZvckVhY2hEYXkucHVzaChcbiAgICAgICAgZGF5anMod2luZG93U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5hZGQoaSwgJ2RheScpXG4gICAgICAgICAgLmZvcm1hdCgpXG4gICAgICApO1xuICAgIH1cblxuICAgIGNvbnN0IHVuZmlsdGVyZWRXb3JrVGltZXM6IFdvcmtUaW1lVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IGV4dGVybmFsQXR0ZW5kZWUgb2YgZXh0ZXJuYWxBdHRlbmRlZXMpIHtcbiAgICAgIGNvbnN0IHdvcmtUaW1lc0ZvckF0dGVuZGVlID0gZ2VuZXJhdGVXb3JrVGltZXNGb3JFeHRlcm5hbEF0dGVuZGVlKFxuICAgICAgICBtYWluSG9zdElkLFxuICAgICAgICBleHRlcm5hbEF0dGVuZGVlPy51c2VySWQsXG4gICAgICAgIG1vZGlmaWVkQWxsRXh0ZXJuYWxFdmVudHMsXG4gICAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgICAgZXh0ZXJuYWxBdHRlbmRlZT8udGltZXpvbmVcbiAgICAgICk7XG4gICAgICB1bmZpbHRlcmVkV29ya1RpbWVzLnB1c2goLi4ud29ya1RpbWVzRm9yQXR0ZW5kZWUpO1xuICAgIH1cblxuICAgIGNvbnN0IHdvcmtUaW1lczogV29ya1RpbWVUeXBlW10gPSBfLnVuaXFXaXRoKFxuICAgICAgdW5maWx0ZXJlZFdvcmtUaW1lcyxcbiAgICAgIF8uaXNFcXVhbFxuICAgICk7XG5cbiAgICBjb25zdCB1bmZpbHRlcmVkVGltZXNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuICAgIC8vIFRoaXMgYHRpbWVzbG90c2AgdmFyaWFibGUgd2lsbCBiZSB0aGUgZmluYWwgb25lIHBhc3NlZCB0byBPcHRhUGxhbm5lciBhZnRlciBwcm9jZXNzaW5nIGFsbCBhdHRlbmRlZXNcbiAgICBjb25zdCB0aW1lc2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IGV4dGVybmFsQXR0ZW5kZWUgb2YgZXh0ZXJuYWxBdHRlbmRlZXMpIHtcbiAgICAgIGNvbnN0IGF0dGVuZGVlU3BlY2lmaWNUaW1lc2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG4gICAgICBsZXQgdXNlRXhwbGljaXRQcmVmZXJlbmNlcyA9IGZhbHNlO1xuXG4gICAgICBpZiAobWVldGluZ0Fzc2lzdElkICYmIGV4dGVybmFsQXR0ZW5kZWUuaWQpIHtcbiAgICAgICAgY29uc3QgZXh0ZXJuYWxQcmVmZXJlbmNlcyA9IGF3YWl0IGxpc3RFeHRlcm5hbEF0dGVuZGVlUHJlZmVyZW5jZXMoXG4gICAgICAgICAgbWVldGluZ0Fzc2lzdElkLFxuICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWUuaWRcbiAgICAgICAgKTtcbiAgICAgICAgaWYgKGV4dGVybmFsUHJlZmVyZW5jZXMubGVuZ3RoID4gMCkge1xuICAgICAgICAgIHVzZUV4cGxpY2l0UHJlZmVyZW5jZXMgPSB0cnVlO1xuICAgICAgICAgIGZvciAoY29uc3QgcHJlZiBvZiBleHRlcm5hbFByZWZlcmVuY2VzKSB7XG4gICAgICAgICAgICBsZXQgY3VycmVudFNsb3RTdGFydFRpbWUgPSBkYXlqcy51dGMocHJlZi5wcmVmZXJyZWRfc3RhcnRfZGF0ZXRpbWUpO1xuICAgICAgICAgICAgY29uc3QgcHJlZkVuZFRpbWUgPSBkYXlqcy51dGMocHJlZi5wcmVmZXJyZWRfZW5kX2RhdGV0aW1lKTtcblxuICAgICAgICAgICAgd2hpbGUgKGN1cnJlbnRTbG90U3RhcnRUaW1lLmlzQmVmb3JlKHByZWZFbmRUaW1lKSkge1xuICAgICAgICAgICAgICBjb25zdCBjdXJyZW50U2xvdEVuZFRpbWUgPSBjdXJyZW50U2xvdFN0YXJ0VGltZS5hZGQoMzAsICdtaW51dGUnKTtcbiAgICAgICAgICAgICAgaWYgKGN1cnJlbnRTbG90RW5kVGltZS5pc0FmdGVyKHByZWZFbmRUaW1lKSkge1xuICAgICAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgY29uc3Qgc3RhcnRUaW1lSW5Ib3N0VHogPSBjdXJyZW50U2xvdFN0YXJ0VGltZS50eihob3N0VGltZXpvbmUpO1xuICAgICAgICAgICAgICBjb25zdCBlbmRUaW1lSW5Ib3N0VHogPSBjdXJyZW50U2xvdEVuZFRpbWUudHooaG9zdFRpbWV6b25lKTtcblxuICAgICAgICAgICAgICBjb25zdCBtZWV0aW5nV2luZG93RGF5anNTdGFydCA9IGRheWpzKHdpbmRvd1N0YXJ0RGF0ZSkudHooXG4gICAgICAgICAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICAgICAgICAgIHRydWVcbiAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgY29uc3QgbWVldGluZ1dpbmRvd0RheWpzRW5kID0gZGF5anMod2luZG93RW5kRGF0ZSkudHooXG4gICAgICAgICAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICAgICAgICAgIHRydWVcbiAgICAgICAgICAgICAgKTtcblxuICAgICAgICAgICAgICBpZiAoXG4gICAgICAgICAgICAgICAgc3RhcnRUaW1lSW5Ib3N0VHouaXNCZWZvcmUobWVldGluZ1dpbmRvd0RheWpzU3RhcnQpIHx8XG4gICAgICAgICAgICAgICAgZW5kVGltZUluSG9zdFR6LmlzQWZ0ZXIobWVldGluZ1dpbmRvd0RheWpzRW5kKVxuICAgICAgICAgICAgICApIHtcbiAgICAgICAgICAgICAgICBjdXJyZW50U2xvdFN0YXJ0VGltZSA9IGN1cnJlbnRTbG90RW5kVGltZTtcbiAgICAgICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICAgIGF0dGVuZGVlU3BlY2lmaWNUaW1lc2xvdHMucHVzaCh7XG4gICAgICAgICAgICAgICAgZGF5T2ZXZWVrOlxuICAgICAgICAgICAgICAgICAgZGF5T2ZXZWVrSW50VG9TdHJpbmdbXG4gICAgICAgICAgICAgICAgICAgIHN0YXJ0VGltZUluSG9zdFR6Lmlzb1dlZWtkYXkoKSBhcyBrZXlvZiB0eXBlb2YgZGF5T2ZXZWVrSW50VG9TdHJpbmdcbiAgICAgICAgICAgICAgICAgIF0sXG4gICAgICAgICAgICAgICAgc3RhcnRUaW1lOiBzdGFydFRpbWVJbkhvc3RUei5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgICAgICAgICAgICBlbmRUaW1lOiBlbmRUaW1lSW5Ib3N0VHouZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICAgICAgICAgICAgaG9zdElkOiBtYWluSG9zdElkLFxuICAgICAgICAgICAgICAgIG1vbnRoRGF5OiBmb3JtYXRUb01vbnRoRGF5KFxuICAgICAgICAgICAgICAgICAgc3RhcnRUaW1lSW5Ib3N0VHoubW9udGgoKSBhcyBNb250aFR5cGUsXG4gICAgICAgICAgICAgICAgICBzdGFydFRpbWVJbkhvc3RUei5kYXRlKCkgYXMgRGF5VHlwZVxuICAgICAgICAgICAgICAgICksXG4gICAgICAgICAgICAgICAgZGF0ZTogc3RhcnRUaW1lSW5Ib3N0VHouZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgICAgICAgICAgICAgLy8gdXNlcklkOiBleHRlcm5hbEF0dGVuZGVlLnVzZXJJZCwgLy8gT3B0aW9uYWw6IGlmIE9wdGFQbGFubmVyIG5lZWRzIHRoaXNcbiAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICAgIGN1cnJlbnRTbG90U3RhcnRUaW1lID0gY3VycmVudFNsb3RFbmRUaW1lO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfVxuXG4gICAgICBpZiAoIXVzZUV4cGxpY2l0UHJlZmVyZW5jZXMpIHtcbiAgICAgICAgLy8gRmFsbGJhY2sgdG8gZXhpc3RpbmcgbG9naWM6IGdlbmVyYXRlIHRpbWVzbG90cyBiYXNlZCBvbiB0aGVpciBnZW5lcmFsIGF2YWlsYWJpbGl0eSAoZS5nLiBzeW5jZWQgY2FsZW5kYXIgZXZlbnRzKVxuICAgICAgICAvLyBUaGUgZXhpc3RpbmcgbG9naWMgaXRlcmF0ZXMgdGhyb3VnaCBgc3RhcnREYXRlc0ZvckVhY2hEYXlgXG4gICAgICAgIGZvciAobGV0IGkgPSAwOyBpIDwgc3RhcnREYXRlc0ZvckVhY2hEYXkubGVuZ3RoOyBpKyspIHtcbiAgICAgICAgICBjb25zdCBpc0ZpcnN0RGF5TG9vcCA9IGkgPT09IDA7XG4gICAgICAgICAgLy8gYG1vZGlmaWVkQWxsRXh0ZXJuYWxFdmVudHNgIHNob3VsZCBiZSBmaWx0ZXJlZCBmb3IgdGhlIHNwZWNpZmljIGBleHRlcm5hbEF0dGVuZGVlLnVzZXJJZGAgaWYgbm90IGFscmVhZHlcbiAgICAgICAgICBjb25zdCBhdHRlbmRlZUV2ZW50c0ZvckZhbGxiYWNrID0gbW9kaWZpZWRBbGxFeHRlcm5hbEV2ZW50cy5maWx0ZXIoXG4gICAgICAgICAgICAoZXZ0KSA9PiBldnQudXNlcklkID09PSBleHRlcm5hbEF0dGVuZGVlLnVzZXJJZFxuICAgICAgICAgICk7XG4gICAgICAgICAgY29uc3QgZmFsbGJhY2tTbG90cyA9IGF3YWl0IGdlbmVyYXRlVGltZVNsb3RzTGl0ZUZvckV4dGVybmFsQXR0ZW5kZWUoXG4gICAgICAgICAgICBzdGFydERhdGVzRm9yRWFjaERheVtpXSxcbiAgICAgICAgICAgIG1haW5Ib3N0SWQsXG4gICAgICAgICAgICBhdHRlbmRlZUV2ZW50c0ZvckZhbGxiYWNrLCAvLyBQYXNzIG9ubHkgdGhpcyBhdHRlbmRlZSdzIGV2ZW50c1xuICAgICAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICAgICAgZXh0ZXJuYWxBdHRlbmRlZS50aW1lem9uZSxcbiAgICAgICAgICAgIGlzRmlyc3REYXlMb29wXG4gICAgICAgICAgKTtcbiAgICAgICAgICBhdHRlbmRlZVNwZWNpZmljVGltZXNsb3RzLnB1c2goLi4uZmFsbGJhY2tTbG90cyk7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICAgIC8vIEFkZCB0aGlzIGF0dGVuZGVlJ3MgZ2VuZXJhdGVkIHRpbWVzbG90cyAoZWl0aGVyIGZyb20gcHJlZnMgb3IgZmFsbGJhY2spIHRvIHRoZSBtYWluIGxpc3RcbiAgICAgIHVuZmlsdGVyZWRUaW1lc2xvdHMucHVzaCguLi5hdHRlbmRlZVNwZWNpZmljVGltZXNsb3RzKTtcbiAgICB9XG5cbiAgICB0aW1lc2xvdHMucHVzaCguLi5fLnVuaXFXaXRoKHVuZmlsdGVyZWRUaW1lc2xvdHMsIF8uaXNFcXVhbCkpOyAvLyBFbnN1cmUgdW5pcXVlIHRpbWVzbG90cyBiZWZvcmUgc2VuZGluZyB0byBPcHRhUGxhbm5lclxuICAgIGNvbnNvbGUubG9nKHRpbWVzbG90cywgJyBmaW5hbCB0aW1lc2xvdHMgZm9yIGV4dGVybmFsIGF0dGVuZGVlcycpO1xuXG4gICAgLy8gTm90ZSBvbiBXb3JrVGltZXM6IElmIGV4cGxpY2l0IHByZWZlcmVuY2VzIGFyZSB1c2VkLCBXb3JrVGltZVR5cGUgZ2VuZXJhdGlvbiBtaWdodCBhbHNvIG5lZWQgYWRqdXN0bWVudC5cbiAgICAvLyBGb3IgdGhpcyBzdWJ0YXNrLCBXb3JrVGltZSBnZW5lcmF0aW9uIHJlbWFpbnMgYmFzZWQgb24gZXhpc3RpbmcgbG9naWMgKGluZmVycmVkIGZyb20gYWxsIGV2ZW50cykuXG4gICAgLy8gYHdvcmtUaW1lc2AgdmFyaWFibGUgdXNlZCBpbiBgZm9ybWF0RXZlbnRUeXBlVG9QbGFubmVyRXZlbnRGb3JFeHRlcm5hbEF0dGVuZGVlYCB3b3VsZCBiZSB0aGUgcGxhY2UgZm9yIHRoaXMuXG5cbiAgICBjb25zdCBmaWx0ZXJlZEFsbEV2ZW50cyA9IF8udW5pcUJ5KFxuICAgICAgbW9kaWZpZWRBbGxFeHRlcm5hbEV2ZW50cy5maWx0ZXIoKGUpID0+XG4gICAgICAgIHZhbGlkYXRlRXZlbnREYXRlc0ZvckV4dGVybmFsQXR0ZW5kZWUoZSlcbiAgICAgICksXG4gICAgICAnaWQnXG4gICAgKTtcbiAgICBsZXQgZXZlbnRQYXJ0czogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZVtdID0gW107XG5cbiAgICBjb25zdCBldmVudFBhcnRNaW5pc0FjY3VtdWxhdGVkID0gW107XG4gICAgZm9yIChjb25zdCBldmVudCBvZiBmaWx0ZXJlZEFsbEV2ZW50cykge1xuICAgICAgY29uc3QgZXZlbnRQYXJ0TWluaXMgPSBnZW5lcmF0ZUV2ZW50UGFydHNMaXRlKGV2ZW50LCBtYWluSG9zdElkKTtcbiAgICAgIGV2ZW50UGFydE1pbmlzQWNjdW11bGF0ZWQucHVzaCguLi5ldmVudFBhcnRNaW5pcyk7XG4gICAgfVxuXG4gICAgY29uc3QgbW9kaWZpZWRFdmVudFBhcnRNaW5pc1ByZUJ1ZmZlciA9XG4gICAgICBtb2RpZnlFdmVudFBhcnRzRm9yTXVsdGlwbGVQcmVCdWZmZXJUaW1lKGV2ZW50UGFydE1pbmlzQWNjdW11bGF0ZWQpO1xuICAgIGNvbnN0IG1vZGlmaWVkRXZlbnRQYXJ0TWluaXNQcmVBbmRQb3N0QnVmZmVyID1cbiAgICAgIG1vZGlmeUV2ZW50UGFydHNGb3JNdWx0aXBsZVBvc3RCdWZmZXJUaW1lKFxuICAgICAgICBtb2RpZmllZEV2ZW50UGFydE1pbmlzUHJlQnVmZmVyXG4gICAgICApO1xuICAgIGNvbnN0IGZvcm1hdHRlZEV2ZW50UGFydHM6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSA9XG4gICAgICBtb2RpZmllZEV2ZW50UGFydE1pbmlzUHJlQW5kUG9zdEJ1ZmZlcj8ubWFwKChlKSA9PlxuICAgICAgICBmb3JtYXRFdmVudFR5cGVUb1BsYW5uZXJFdmVudEZvckV4dGVybmFsQXR0ZW5kZWUoXG4gICAgICAgICAgZSxcbiAgICAgICAgICB3b3JrVGltZXMsXG4gICAgICAgICAgZmlsdGVyZWRBbGxFdmVudHMsXG4gICAgICAgICAgaG9zdFRpbWV6b25lXG4gICAgICAgIClcbiAgICAgICk7XG4gICAgaWYgKGZvcm1hdHRlZEV2ZW50UGFydHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGV2ZW50UGFydHMucHVzaCguLi5mb3JtYXR0ZWRFdmVudFBhcnRzKTtcbiAgICB9XG5cbiAgICBpZiAoZXZlbnRQYXJ0cy5sZW5ndGggPiAwKSB7XG4gICAgICBldmVudFBhcnRzLmZvckVhY2goKGUpID0+IGNvbnNvbGUubG9nKGUsICcgZXZlbnRQYXJ0cyBhZnRlciBmb3JtYXR0aW5nJykpO1xuICAgICAgY29uc3QgbmV3RXZlbnRQYXJ0c1dpdGhQcmVmZXJyZWRUaW1lU2V0ID0gZXZlbnRQYXJ0cy5tYXAoKGUpID0+XG4gICAgICAgIHNldFByZWZlcnJlZFRpbWVGb3JVbk1vZGlmaWFibGVFdmVudChcbiAgICAgICAgICBlLFxuICAgICAgICAgIGFsbEV4dGVybmFsRXZlbnRzLmZpbmQoKGYpID0+IGYuaWQgPT09IGUuZXZlbnRJZCk/LnRpbWV6b25lXG4gICAgICAgIClcbiAgICAgICk7XG4gICAgICBuZXdFdmVudFBhcnRzV2l0aFByZWZlcnJlZFRpbWVTZXQuZm9yRWFjaCgoZSkgPT5cbiAgICAgICAgY29uc29sZS5sb2coZSwgJyBuZXdFdmVudFBhcnRzV2l0aFByZWZlcnJlZFRpbWVTZXQnKVxuICAgICAgKTtcbiAgICAgIGNvbnN0IG5ld0V2ZW50UGFydHMgPSBhd2FpdCB0YWdFdmVudHNGb3JEYWlseU9yV2Vla2x5VGFzayhcbiAgICAgICAgbmV3RXZlbnRQYXJ0c1dpdGhQcmVmZXJyZWRUaW1lU2V0XG4gICAgICApO1xuICAgICAgbmV3RXZlbnRQYXJ0cy5mb3JFYWNoKChlKSA9PlxuICAgICAgICBjb25zb2xlLmxvZyhlLCAnIG5ld0V2ZW50UGFydHMgYWZ0ZXIgdGFnRXZlbnRzRm9yRGFpbHlPcldlZWtseVRhc2snKVxuICAgICAgKTtcbiAgICAgIGNvbnN0IHVzZXJMaXN0OiBVc2VyUGxhbm5lclJlcXVlc3RCb2R5VHlwZVtdID0gW107XG4gICAgICBmb3IgKGNvbnN0IGV4dGVybmFsQXR0ZW5kZWUgb2YgZXh0ZXJuYWxBdHRlbmRlZXMpIHtcbiAgICAgICAgY29uc3QgdXNlclBsYW5uZXJSZXF1ZXN0Qm9keSA9XG4gICAgICAgICAgZ2VuZXJhdGVVc2VyUGxhbm5lclJlcXVlc3RCb2R5Rm9yRXh0ZXJuYWxBdHRlbmRlZShcbiAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWU/LnVzZXJJZCxcbiAgICAgICAgICAgIHdvcmtUaW1lcyxcbiAgICAgICAgICAgIG1haW5Ib3N0SWRcbiAgICAgICAgICApO1xuICAgICAgICBjb25zb2xlLmxvZyh1c2VyUGxhbm5lclJlcXVlc3RCb2R5LCAnIHVzZXJQbGFubmVyUmVxdWVzdEJvZHknKTtcbiAgICAgICAgdXNlckxpc3QucHVzaCh1c2VyUGxhbm5lclJlcXVlc3RCb2R5KTtcbiAgICAgIH1cblxuICAgICAgY29uc3QgbW9kaWZpZWROZXdFdmVudFBhcnRzOiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlW10gPVxuICAgICAgICBuZXdFdmVudFBhcnRzLm1hcCgoZXZlbnRQYXJ0KSA9PiB7XG4gICAgICAgICAgY29uc3Qgb2xkRXZlbnQgPSBmaWx0ZXJlZEFsbEV2ZW50cy5maW5kKFxuICAgICAgICAgICAgKGV2ZW50KSA9PiBldmVudC5pZCA9PT0gZXZlbnRQYXJ0LmV2ZW50SWRcbiAgICAgICAgICApO1xuICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICBncm91cElkOiBldmVudFBhcnQ/Lmdyb3VwSWQsXG4gICAgICAgICAgICBldmVudElkOiBldmVudFBhcnQ/LmV2ZW50SWQsXG4gICAgICAgICAgICBwYXJ0OiBldmVudFBhcnQ/LnBhcnQsXG4gICAgICAgICAgICBsYXN0UGFydDogZXZlbnRQYXJ0Py5sYXN0UGFydCxcbiAgICAgICAgICAgIG1lZXRpbmdQYXJ0OiBldmVudFBhcnQ/Lm1lZXRpbmdQYXJ0LFxuICAgICAgICAgICAgbWVldGluZ0xhc3RQYXJ0OiBldmVudFBhcnQ/Lm1lZXRpbmdMYXN0UGFydCxcbiAgICAgICAgICAgIG1lZXRpbmdJZDogZXZlbnRQYXJ0Py5tZWV0aW5nSWQsXG4gICAgICAgICAgICBob3N0SWQ6IG1haW5Ib3N0SWQsXG4gICAgICAgICAgICBzdGFydERhdGU6IGRheWpzKGV2ZW50UGFydD8uc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG9sZEV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tOnNzJyksXG4gICAgICAgICAgICBlbmREYXRlOiBkYXlqcyhldmVudFBhcnQ/LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoob2xkRXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW06c3MnKSxcbiAgICAgICAgICAgIHVzZXJJZDogZXZlbnRQYXJ0Py51c2VySWQsXG4gICAgICAgICAgICB1c2VyOiBldmVudFBhcnQ/LnVzZXIsXG4gICAgICAgICAgICBwcmlvcml0eTogZXZlbnRQYXJ0Py5wcmlvcml0eSxcbiAgICAgICAgICAgIGlzUHJlRXZlbnQ6IGV2ZW50UGFydD8uaXNQcmVFdmVudCxcbiAgICAgICAgICAgIGlzUG9zdEV2ZW50OiBldmVudFBhcnQ/LmlzUG9zdEV2ZW50LFxuICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RTY29yZTogZXZlbnRQYXJ0Py5wb3NpdGl2ZUltcGFjdFNjb3JlLFxuICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3RTY29yZTogZXZlbnRQYXJ0Py5uZWdhdGl2ZUltcGFjdFNjb3JlLFxuICAgICAgICAgICAgbW9kaWZpYWJsZTogZXZlbnRQYXJ0Py5tb2RpZmlhYmxlLFxuICAgICAgICAgICAgaXNNZWV0aW5nOiBldmVudFBhcnQ/LmlzTWVldGluZyxcbiAgICAgICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nOiBldmVudFBhcnQ/LmlzRXh0ZXJuYWxNZWV0aW5nLFxuICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlOiBldmVudFBhcnQ/LmlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgICAgICAgIGlzTWVldGluZ01vZGlmaWFibGU6IGV2ZW50UGFydD8uaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgICAgICAgIGRhaWx5VGFza0xpc3Q6IGV2ZW50UGFydD8uZGFpbHlUYXNrTGlzdCxcbiAgICAgICAgICAgIHdlZWtseVRhc2tMaXN0OiBldmVudFBhcnQ/LndlZWtseVRhc2tMaXN0LFxuICAgICAgICAgICAgZ2FwOiBldmVudFBhcnQ/LmdhcCxcbiAgICAgICAgICAgIHRvdGFsV29ya2luZ0hvdXJzOiBldmVudFBhcnQ/LnRvdGFsV29ya2luZ0hvdXJzLFxuICAgICAgICAgICAgaGFyZERlYWRsaW5lOiBldmVudFBhcnQ/LmhhcmREZWFkbGluZSxcbiAgICAgICAgICAgIHNvZnREZWFkbGluZTogZXZlbnRQYXJ0Py5zb2Z0RGVhZGxpbmUsXG4gICAgICAgICAgICBmb3JFdmVudElkOiBldmVudFBhcnQ/LmZvckV2ZW50SWQsXG4gICAgICAgICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2VlazogZXZlbnRQYXJ0Py5wb3NpdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0VGltZTogZXZlbnRQYXJ0Py5wb3NpdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2VlazogZXZlbnRQYXJ0Py5uZWdhdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZTogZXZlbnRQYXJ0Py5uZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgICAgICBwcmVmZXJyZWREYXlPZldlZWs6IGV2ZW50UGFydD8ucHJlZmVycmVkRGF5T2ZXZWVrLFxuICAgICAgICAgICAgcHJlZmVycmVkVGltZTogZXZlbnRQYXJ0Py5wcmVmZXJyZWRUaW1lLFxuICAgICAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U6IGV2ZW50UGFydD8ucHJlZmVycmVkU3RhcnRUaW1lUmFuZ2UsXG4gICAgICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2U6IGV2ZW50UGFydD8ucHJlZmVycmVkRW5kVGltZVJhbmdlLFxuICAgICAgICAgICAgZXZlbnQ6IGV2ZW50UGFydD8uZXZlbnQsXG4gICAgICAgICAgfTtcbiAgICAgICAgfSk7XG5cbiAgICAgIHJldHVybiBtb2RpZmllZE5ld0V2ZW50UGFydHM/Lmxlbmd0aCA+IDBcbiAgICAgICAgPyB7XG4gICAgICAgICAgICB1c2VySWRzLFxuICAgICAgICAgICAgaG9zdElkOiBtYWluSG9zdElkLFxuICAgICAgICAgICAgZXZlbnRQYXJ0czogbW9kaWZpZWROZXdFdmVudFBhcnRzLFxuICAgICAgICAgICAgYWxsRXZlbnRzOiBmaWx0ZXJlZEFsbEV2ZW50cyxcbiAgICAgICAgICAgIG9sZEF0dGVuZGVlRXZlbnRzOiBhbGxFeHRlcm5hbEV2ZW50cyxcbiAgICAgICAgICAgIHRpbWVzbG90cyxcbiAgICAgICAgICAgIHVzZXJMaXN0LFxuICAgICAgICAgIH1cbiAgICAgICAgOiBudWxsO1xuICAgIH1cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZSxcbiAgICAgICcgdW5hYmxlIHRvIHByb2Nlc3MgZXZlbnRzIGZvciBvcHRhcGxhbm5lciBmb3IgZXh0ZXJuYWwgYXR0ZW5kZWUnXG4gICAgKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IG9wdGFQbGFuV2Vla2x5ID0gYXN5bmMgKFxuICB0aW1lc2xvdHM6IFRpbWVTbG90VHlwZVtdLFxuICB1c2VyTGlzdDogVXNlclBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSxcbiAgZXZlbnRQYXJ0czogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZVtdLFxuICBzaW5nbGV0b25JZDogc3RyaW5nLFxuICBob3N0SWQ6IHN0cmluZyxcbiAgZmlsZUtleTogc3RyaW5nLFxuICBkZWxheTogbnVtYmVyLFxuICBjYWxsQmFja1VybDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCByZXF1ZXN0Qm9keTogUGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9IHtcbiAgICAgIHNpbmdsZXRvbklkLFxuICAgICAgaG9zdElkLFxuICAgICAgdGltZXNsb3RzLFxuICAgICAgdXNlckxpc3QsXG4gICAgICBldmVudFBhcnRzLFxuICAgICAgZmlsZUtleSxcbiAgICAgIGRlbGF5LFxuICAgICAgY2FsbEJhY2tVcmwsXG4gICAgfTtcblxuICAgIGF3YWl0IGdvdFxuICAgICAgLnBvc3QoYCR7b3B0YVBsYW5uZXJVcmx9L3RpbWVUYWJsZS9hZG1pbi9zb2x2ZS1kYXlgLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgIEF1dGhvcml6YXRpb246IGBCYXNpYyAke0J1ZmZlci5mcm9tKGAke29wdGFQbGFubmVyVXNlcm5hbWV9OiR7b3B0YVBsYW5uZXJQYXNzd29yZH1gKS50b1N0cmluZygnYmFzZTY0Jyl9YCxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjogcmVxdWVzdEJvZHksXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKCcgb3B0YVBsYW5XZWVrbHkgY2FsbGVkJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIG9wdGFQbGFuV2Vla2x5Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB1cGRhdGVGcmVlbWl1bUJ5SWQgPSBhc3luYyAoaWQ6IHN0cmluZywgdXNhZ2U6IG51bWJlcikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnVXBkYXRlRnJlZW1pdW1CeUlkJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIG11dGF0aW9uIFVwZGF0ZUZyZWVtaXVtQnlJZCgkaWQ6IHV1aWQhLCAkdXNhZ2U6IEludCEpIHtcbiAgICAgICAgICAgICAgICB1cGRhdGVfRnJlZW1pdW1fYnlfcGsocGtfY29sdW1uczoge2lkOiAkaWR9LCBfc2V0OiB7dXNhZ2U6ICR1c2FnZX0pIHtcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIHBlcmlvZFxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNhZ2VcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgaWQsXG4gICAgICB1c2FnZSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IHsgZGF0YTogeyB1cGRhdGVfRnJlZW1pdW1fYnlfcGs6IEZyZWVtaXVtVHlwZSB9IH0gPVxuICAgICAgYXdhaXQgZ290XG4gICAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICAgIH0sXG4gICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgICAgIC5qc29uKCk7XG4gICAgY29uc29sZS5sb2coXG4gICAgICByZXNwb25zZSxcbiAgICAgIHJlc3BvbnNlPy5kYXRhPy51cGRhdGVfRnJlZW1pdW1fYnlfcGssXG4gICAgICAnIHJlc3BvbnNlIGFmdGVyIHVwZGF0aW5nIHVwZGF0ZV9GcmVlbWl1bV9ieV9waydcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlc3BvbnNlPy5kYXRhPy51cGRhdGVfRnJlZW1pdW1fYnlfcGs7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cGRhdGUgZnJlZW1pdW0nKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldEZyZWVtaXVtQnlVc2VySWQgPSBhc3luYyAodXNlcklkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0dldEZyZWVtaXVtQnlVc2VySWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgR2V0RnJlZW1pdW1CeVVzZXJJZCgkdXNlcklkOiB1dWlkISkge1xuICAgICAgICAgICAgICAgIEZyZWVtaXVtKHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfX0pIHtcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIHBlcmlvZFxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNhZ2VcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgdXNlcklkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBGcmVlbWl1bTogRnJlZW1pdW1UeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBnZXRGcmVlbWl1bUJ5VXNlcklkICcpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uRnJlZW1pdW0/LlswXTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKCcgdW5hYmxlIHRvIGdldCBmcmVlbWl1bSBieSB1c2VyIGlkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzRXZlbnRzRm9yT3B0YVBsYW5uZXIgPSBhc3luYyAoXG4gIG1haW5Ib3N0SWQ6IHN0cmluZyxcbiAgaW50ZXJuYWxBdHRlbmRlZXM6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXSxcbiAgbWVldGluZ0V2ZW50UGx1czogRXZlbnRNZWV0aW5nUGx1c1R5cGVbXSxcbiAgbmV3TWVldGluZ0V2ZW50UGx1czogRXZlbnRNZWV0aW5nUGx1c1R5cGVbXSxcbiAgYWxsRXZlbnRzOiBFdmVudFBsdXNUeXBlW10sXG4gIHdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nLFxuICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICBvbGRFdmVudHM6IEV2ZW50UGx1c1R5cGVbXSxcbiAgZXh0ZXJuYWxBdHRlbmRlZXM/OiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10sXG4gIG1lZXRpbmdBc3Npc3RFdmVudHM/OiBNZWV0aW5nQXNzaXN0RXZlbnRUeXBlW10sXG4gIG5ld0hvc3RSZW1pbmRlcnM/OiBSZW1pbmRlcnNGb3JFdmVudFR5cGVbXSxcbiAgbmV3SG9zdEJ1ZmZlclRpbWVzPzogQnVmZmVyVGltZU9iamVjdFR5cGVbXSxcbiAgaXNSZXBsYW4/OiBib29sZWFuLFxuICBldmVudEJlaW5nUmVwbGFubmVkPzoge1xuICAgIG9yaWdpbmFsRXZlbnRJZDogc3RyaW5nOyAvLyBIYXN1cmEgZXZlbnQgSUQ6IGdvb2dsZUV2ZW50SWQjY2FsZW5kYXJJZFxuICAgIGdvb2dsZUV2ZW50SWQ6IHN0cmluZztcbiAgICBjYWxlbmRhcklkOiBzdHJpbmc7XG4gICAgbmV3Q29uc3RyYWludHM6IE5ld0NvbnN0cmFpbnRzO1xuICAgIG9yaWdpbmFsQXR0ZW5kZWVzOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW107XG4gIH1cbikgPT4ge1xuICB0cnkge1xuICAgIGxldCBjdXJyZW50SW50ZXJuYWxBdHRlbmRlZXMgPSBbLi4uaW50ZXJuYWxBdHRlbmRlZXNdO1xuICAgIGxldCBjdXJyZW50RXh0ZXJuYWxBdHRlbmRlZXMgPSBbLi4uZXh0ZXJuYWxBdHRlbmRlZXNdO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgJyB3aW5kb3dTdGFydERhdGUsIHdpbmRvd0VuZERhdGUgaW5zaWRlIHByb2Nlc3NFdmVudHNGb3JPcHRhUGxhbm5lcidcbiAgICApO1xuICAgIGlmIChpc1JlcGxhbiAmJiBldmVudEJlaW5nUmVwbGFubmVkKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgJ1JlcGxhbm5pbmcgZXZlbnQ6JyxcbiAgICAgICAgZXZlbnRCZWluZ1JlcGxhbm5lZC5vcmlnaW5hbEV2ZW50SWQsXG4gICAgICAgICd3aXRoIGNvbnN0cmFpbnRzOicsXG4gICAgICAgIGV2ZW50QmVpbmdSZXBsYW5uZWQubmV3Q29uc3RyYWludHNcbiAgICAgICk7XG5cbiAgICAgIGxldCBwcm9jZXNzZWRPcmlnaW5hbEF0dGVuZGVlcyA9XG4gICAgICAgIGV2ZW50QmVpbmdSZXBsYW5uZWQub3JpZ2luYWxBdHRlbmRlZXMubWFwKChhKSA9PiAoe1xuICAgICAgICAgIC4uLmEsXG4gICAgICAgICAgcHJpbWFyeUVtYWlsOlxuICAgICAgICAgICAgYS5lbWFpbHM/LmZpbmQoKGUpID0+IGUucHJpbWFyeSk/LnZhbHVlIHx8XG4gICAgICAgICAgICBhLmVtYWlscz8uWzBdPy52YWx1ZSB8fFxuICAgICAgICAgICAgYS5wcmltYXJ5RW1haWwsXG4gICAgICAgIH0pKTtcblxuICAgICAgLy8gSGFuZGxlIHJlbW92ZWQgYXR0ZW5kZWVzXG4gICAgICBpZiAoXG4gICAgICAgIGV2ZW50QmVpbmdSZXBsYW5uZWQubmV3Q29uc3RyYWludHMucmVtb3ZlZEF0dGVuZGVlRW1haWxzT3JJZHM/Lmxlbmd0aCA+XG4gICAgICAgIDBcbiAgICAgICkge1xuICAgICAgICBwcm9jZXNzZWRPcmlnaW5hbEF0dGVuZGVlcyA9IHByb2Nlc3NlZE9yaWdpbmFsQXR0ZW5kZWVzLmZpbHRlcihcbiAgICAgICAgICAoYXR0KSA9PlxuICAgICAgICAgICAgIWV2ZW50QmVpbmdSZXBsYW5uZWQubmV3Q29uc3RyYWludHMucmVtb3ZlZEF0dGVuZGVlRW1haWxzT3JJZHMuaW5jbHVkZXMoXG4gICAgICAgICAgICAgIGF0dC5wcmltYXJ5RW1haWxcbiAgICAgICAgICAgICkgJiZcbiAgICAgICAgICAgICFldmVudEJlaW5nUmVwbGFubmVkLm5ld0NvbnN0cmFpbnRzLnJlbW92ZWRBdHRlbmRlZUVtYWlsc09ySWRzLmluY2x1ZGVzKFxuICAgICAgICAgICAgICBhdHQuaWRcbiAgICAgICAgICAgICkgJiZcbiAgICAgICAgICAgICFldmVudEJlaW5nUmVwbGFubmVkLm5ld0NvbnN0cmFpbnRzLnJlbW92ZWRBdHRlbmRlZUVtYWlsc09ySWRzLmluY2x1ZGVzKFxuICAgICAgICAgICAgICBhdHQudXNlcklkXG4gICAgICAgICAgICApXG4gICAgICAgICk7XG4gICAgICB9XG5cbiAgICAgIC8vIEhhbmRsZSBhZGRlZCBhdHRlbmRlZXNcbiAgICAgIGlmIChldmVudEJlaW5nUmVwbGFubmVkLm5ld0NvbnN0cmFpbnRzLmFkZGVkQXR0ZW5kZWVzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGZvciAoY29uc3QgYWRkZWRBdHQgb2YgZXZlbnRCZWluZ1JlcGxhbm5lZC5uZXdDb25zdHJhaW50c1xuICAgICAgICAgIC5hZGRlZEF0dGVuZGVlcykge1xuICAgICAgICAgIC8vIEF2b2lkIGFkZGluZyBkdXBsaWNhdGVzIGlmIHRoZXkgc29tZWhvdyByZW1haW5lZCBmcm9tIG9yaWdpbmFsIGxpc3RcbiAgICAgICAgICBpZiAoXG4gICAgICAgICAgICBwcm9jZXNzZWRPcmlnaW5hbEF0dGVuZGVlcy5zb21lKFxuICAgICAgICAgICAgICAob2EpID0+XG4gICAgICAgICAgICAgICAgb2EucHJpbWFyeUVtYWlsID09PSBhZGRlZEF0dC5lbWFpbCB8fFxuICAgICAgICAgICAgICAgIChhZGRlZEF0dC51c2VySWQgJiYgb2EudXNlcklkID09PSBhZGRlZEF0dC51c2VySWQpXG4gICAgICAgICAgICApXG4gICAgICAgICAgKSB7XG4gICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICB9XG4gICAgICAgICAgLy8gRmV0Y2ggZnVsbCBhdHRlbmRlZSBkZXRhaWxzIGlmIG5lZWRlZCwgb3IgY29uc3RydWN0IGEgcGFydGlhbCBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlXG4gICAgICAgICAgLy8gVGhpcyBleGFtcGxlIGFzc3VtZXMgd2UgbWlnaHQgbmVlZCB0byBmZXRjaCBmdWxsIGRldGFpbHMgdXNpbmcgZ2V0TWVldGluZ0Fzc2lzdEF0dGVuZGVlQnlFbWFpbE9yVXNlcklkIChoeXBvdGhldGljYWwgZnVuY3Rpb24pXG4gICAgICAgICAgLy8gRm9yIG5vdywgY29uc3RydWN0IGEgcGFydGlhbCBvYmplY3QgYmFzZWQgb24gTmV3Q29uc3RyYWludHMsIGFzc3VtaW5nIE1BX0F0dGVuZGVlIElEIGlzIG5vdCBrbm93biB5ZXQgZm9yIG5ldyBvbmVzLlxuICAgICAgICAgIGNvbnN0IG5ld0F0dGVuZGVlT2JqZWN0OiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlID0ge1xuICAgICAgICAgICAgaWQ6IHV1aWQoKSwgLy8gR2VuZXJhdGUgYSB0ZW1wb3JhcnkgSUQgb3IgaGFuZGxlIGFwcHJvcHJpYXRlbHkgaWYgaXQncyBhIGtub3duIHVzZXJcbiAgICAgICAgICAgIHVzZXJJZDogYWRkZWRBdHQudXNlcklkIHx8IG51bGwsIC8vIFVzZXJJRCBtaWdodCBiZSBrbm93biBpZiBpbnRlcm5hbFxuICAgICAgICAgICAgaG9zdElkOiBtYWluSG9zdElkLCAvLyBBc3NvY2lhdGUgd2l0aCB0aGUgbWFpbiBob3N0XG4gICAgICAgICAgICBtZWV0aW5nSWQ6IG51bGwsIC8vIE5vdCB0aWVkIHRvIGEgc3BlY2lmaWMgTUEgcmVjb3JkIHlldCwgb3IgdXNlIGN1cnJlbnQgTUEgaWYgYXBwcm9wcmlhdGVcbiAgICAgICAgICAgIG5hbWU6IGFkZGVkQXR0Lm5hbWUgfHwgYWRkZWRBdHQuZW1haWwuc3BsaXQoJ0AnKVswXSxcbiAgICAgICAgICAgIHByaW1hcnlFbWFpbDogYWRkZWRBdHQuZW1haWwsXG4gICAgICAgICAgICBlbWFpbHM6IFtcbiAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgIHByaW1hcnk6IHRydWUsXG4gICAgICAgICAgICAgICAgdmFsdWU6IGFkZGVkQXR0LmVtYWlsLFxuICAgICAgICAgICAgICAgIHR5cGU6ICd3b3JrJyxcbiAgICAgICAgICAgICAgICBkaXNwbGF5TmFtZTogYWRkZWRBdHQubmFtZSB8fCBhZGRlZEF0dC5lbWFpbC5zcGxpdCgnQCcpWzBdLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICAgIHRpbWV6b25lOiBhZGRlZEF0dC50aW1lem9uZSB8fCBob3N0VGltZXpvbmUsIC8vIERlZmF1bHQgdG8gaG9zdCB0aW1lem9uZSBpZiBub3QgcHJvdmlkZWRcbiAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWU6XG4gICAgICAgICAgICAgIGFkZGVkQXR0LmV4dGVybmFsQXR0ZW5kZWUgIT09IHVuZGVmaW5lZFxuICAgICAgICAgICAgICAgID8gYWRkZWRBdHQuZXh0ZXJuYWxBdHRlbmRlZVxuICAgICAgICAgICAgICAgIDogIWFkZGVkQXR0LnVzZXJJZCxcbiAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICB9O1xuICAgICAgICAgIHByb2Nlc3NlZE9yaWdpbmFsQXR0ZW5kZWVzLnB1c2gobmV3QXR0ZW5kZWVPYmplY3QpO1xuICAgICAgICB9XG4gICAgICB9XG4gICAgICAvLyBTZXBhcmF0ZSBpbnRvIGludGVybmFsIGFuZCBleHRlcm5hbCBiYXNlZCBvbiB0aGUgZmluYWwgbGlzdFxuICAgICAgY3VycmVudEludGVybmFsQXR0ZW5kZWVzID0gcHJvY2Vzc2VkT3JpZ2luYWxBdHRlbmRlZXMuZmlsdGVyKFxuICAgICAgICAoYSkgPT4gIWEuZXh0ZXJuYWxBdHRlbmRlZVxuICAgICAgKTtcbiAgICAgIGN1cnJlbnRFeHRlcm5hbEF0dGVuZGVlcyA9IHByb2Nlc3NlZE9yaWdpbmFsQXR0ZW5kZWVzLmZpbHRlcihcbiAgICAgICAgKGEpID0+IGEuZXh0ZXJuYWxBdHRlbmRlZVxuICAgICAgKTtcbiAgICB9XG5cbiAgICBjb25zdCBuZXdJbnRlcm5hbE1lZXRpbmdFdmVudHNQbHVzID0gbmV3TWVldGluZ0V2ZW50UGx1c1xuICAgICAgPy5tYXAoKGUpID0+IHtcbiAgICAgICAgY29uc3QgZm91bmRJbmRleCA9IGN1cnJlbnRFeHRlcm5hbEF0dGVuZGVlcz8uZmluZEluZGV4KFxuICAgICAgICAgIChhKSA9PiBhPy51c2VySWQgPT09IGU/LnVzZXJJZFxuICAgICAgICApO1xuXG4gICAgICAgIGlmIChmb3VuZEluZGV4ID4gLTEpIHtcbiAgICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgICAgfVxuICAgICAgICByZXR1cm4gZTtcbiAgICAgIH0pXG4gICAgICA/LmZpbHRlcigoZSkgPT4gZSAhPT0gbnVsbCk7XG5cbiAgICBjb25zdCBuZXdFeHRlcm5hbE1lZXRpbmdFdmVudHNQbHVzID0gbmV3TWVldGluZ0V2ZW50UGx1c1xuICAgICAgPy5tYXAoKGUpID0+IHtcbiAgICAgICAgY29uc3QgZm91bmRJbmRleCA9IGN1cnJlbnRFeHRlcm5hbEF0dGVuZGVlcz8uZmluZEluZGV4KFxuICAgICAgICAgIChhKSA9PiBhPy51c2VySWQgPT09IGU/LnVzZXJJZFxuICAgICAgICApO1xuXG4gICAgICAgIGlmIChmb3VuZEluZGV4ID4gLTEpIHtcbiAgICAgICAgICByZXR1cm4gZTtcbiAgICAgICAgfVxuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH0pXG4gICAgICA/LmZpbHRlcigoZSkgPT4gZSAhPT0gbnVsbCk7XG5cbiAgICBjb25zdCBhbGxIb3N0RXZlbnRzID0gYWxsRXZlbnRzLmZpbHRlcigoZSkgPT4gZS51c2VySWQgPT09IG1haW5Ib3N0SWQpO1xuXG4gICAgY29uc3Qgb2xkSG9zdEV2ZW50cyA9IG9sZEV2ZW50cy5maWx0ZXIoKGUpID0+IGU/LnVzZXJJZCA9PT0gbWFpbkhvc3RJZCk7XG5cbiAgICBjb25zdCBob3N0SXNJbnRlcm5hbEF0dGVuZGVlID0gY3VycmVudEludGVybmFsQXR0ZW5kZWVzLnNvbWUoXG4gICAgICAoaWEpID0+IGlhPy51c2VySWQgPT09IG1haW5Ib3N0SWRcbiAgICApO1xuXG4gICAgbGV0IHJldHVyblZhbHVlc0Zyb21JbnRlcm5hbEF0dGVuZGVlczpcbiAgICAgIHwgUmV0dXJuQm9keUZvckF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZVxuICAgICAgfCB7fSA9IHt9O1xuICAgIGxldCByZXR1cm5WYWx1ZXNGcm9tSG9zdDogUmV0dXJuQm9keUZvckhvc3RGb3JPcHRhcGxhbm5lclByZXBUeXBlIHwge30gPSB7fTtcblxuICAgIGNvbnNvbGUubG9nKGhvc3RJc0ludGVybmFsQXR0ZW5kZWUsICcgaG9zdElzSW50ZXJuYWxBdHRlbmRlZScpO1xuXG4gICAgaWYgKGhvc3RJc0ludGVybmFsQXR0ZW5kZWUpIHtcbiAgICAgIHJldHVyblZhbHVlc0Zyb21JbnRlcm5hbEF0dGVuZGVlcyA9XG4gICAgICAgIGF3YWl0IHByb2Nlc3NFdmVudHNGb3JPcHRhUGxhbm5lckZvckludGVybmFsQXR0ZW5kZWVzKFxuICAgICAgICAgIG1haW5Ib3N0SWQsXG4gICAgICAgICAgYWxsRXZlbnRzLFxuICAgICAgICAgIC8vIFRPRE86IEZvciByZXBsYW4sIGlmIGV2ZW50QmVpbmdSZXBsYW5uZWQubmV3Q29uc3RyYWludHMubmV3VGltZVdpbmRvd1N0YXJ0VVRDIGlzIHNldCwgdXNlIGl0IGhlcmUgZm9yIHJlbGV2YW50IGF0dGVuZGVlc1xuICAgICAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgICAgICBjdXJyZW50SW50ZXJuYWxBdHRlbmRlZXMsIC8vIFVzZSBmaW5hbGl6ZWQgbGlzdFxuICAgICAgICAgIG9sZEV2ZW50cyxcbiAgICAgICAgICBtZWV0aW5nRXZlbnRQbHVzLFxuICAgICAgICAgIG5ld0ludGVybmFsTWVldGluZ0V2ZW50c1BsdXMsXG4gICAgICAgICAgbmV3SG9zdEJ1ZmZlclRpbWVzLFxuICAgICAgICAgIC8vIFBhc3MgaXNSZXBsYW4gYW5kIGV2ZW50QmVpbmdSZXBsYW5uZWQgZm9yIG1vZGlmaWFibGUgZmxhZyBhbmQgZHVyYXRpb24gbG9naWNcbiAgICAgICAgICBpc1JlcGxhbixcbiAgICAgICAgICBldmVudEJlaW5nUmVwbGFubmVkXG4gICAgICAgICk7XG4gICAgfSBlbHNlIHtcbiAgICAgIC8vIEFzc3VtaW5nIG1haW5Ib3N0IGlzIGFsd2F5cyBwYXJ0IG9mIGludGVybmFsQXR0ZW5kZWVzIGlmIHRoZXkgYXJlIGludGVybmFsLlxuICAgICAgLy8gSWYgbWFpbkhvc3QgY2FuIGJlIGV4dGVybmFsIG9yIG5vdCBpbiB0aGUgbGlzdCwgdGhpcyBsb2dpYyBuZWVkcyBhZGp1c3RtZW50LlxuICAgICAgcmV0dXJuVmFsdWVzRnJvbUhvc3QgPSBhd2FpdCBwcm9jZXNzRXZlbnRzRm9yT3B0YVBsYW5uZXJGb3JNYWluSG9zdChcbiAgICAgICAgbWFpbkhvc3RJZCxcbiAgICAgICAgYWxsSG9zdEV2ZW50cyxcbiAgICAgICAgLy8gVE9ETzogRm9yIHJlcGxhbiwgaWYgZXZlbnRCZWluZ1JlcGxhbm5lZC5uZXdDb25zdHJhaW50cy5uZXdUaW1lV2luZG93U3RhcnRVVEMgaXMgc2V0LCB1c2UgaXQgaGVyZVxuICAgICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgICAgb2xkSG9zdEV2ZW50cyxcbiAgICAgICAgbmV3SG9zdEJ1ZmZlclRpbWVzLFxuICAgICAgICAvLyBQYXNzIGlzUmVwbGFuIGFuZCBldmVudEJlaW5nUmVwbGFubmVkIGZvciBtb2RpZmlhYmxlIGZsYWcgYW5kIGR1cmF0aW9uIGxvZ2ljXG4gICAgICAgIGlzUmVwbGFuLFxuICAgICAgICBldmVudEJlaW5nUmVwbGFubmVkXG4gICAgICApO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgcmV0dXJuVmFsdWVzRnJvbUludGVybmFsQXR0ZW5kZWVzLFxuICAgICAgJyByZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMnXG4gICAgKTtcbiAgICBjb25zdCBleHRlcm5hbE1lZXRpbmdFdmVudFBsdXMgPSBtZWV0aW5nRXZlbnRQbHVzXG4gICAgICAubWFwKChlKSA9PiB7XG4gICAgICAgIGNvbnN0IGZvdW5kSW5kZXggPSBjdXJyZW50RXh0ZXJuYWxBdHRlbmRlZXMuZmluZEluZGV4KFxuICAgICAgICAgIChhKSA9PiBhPy51c2VySWQgPT09IGU/LnVzZXJJZFxuICAgICAgICApO1xuICAgICAgICBpZiAoZm91bmRJbmRleCA+IC0xKSB7XG4gICAgICAgICAgcmV0dXJuIGU7XG4gICAgICAgIH1cbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9KVxuICAgICAgPy5maWx0ZXIoKGUpID0+IGUgIT09IG51bGwpO1xuXG4gICAgY29uc3QgcmV0dXJuVmFsdWVzRnJvbUV4dGVybmFsQXR0ZW5kZWVzOiBSZXR1cm5Cb2R5Rm9yRXh0ZXJuYWxBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGUgPVxuICAgICAgY3VycmVudEV4dGVybmFsQXR0ZW5kZWVzPy5sZW5ndGggPiAwXG4gICAgICAgID8gYXdhaXQgcHJvY2Vzc0V2ZW50c0Zvck9wdGFQbGFubmVyRm9yRXh0ZXJuYWxBdHRlbmRlZXMoXG4gICAgICAgICAgICBjdXJyZW50RXh0ZXJuYWxBdHRlbmRlZXM/Lm1hcCgoYSkgPT4gYS51c2VySWQpLFxuICAgICAgICAgICAgbWFpbkhvc3RJZCxcbiAgICAgICAgICAgIG1lZXRpbmdBc3Npc3RFdmVudHMsXG4gICAgICAgICAgICAvLyBUT0RPOiBGb3IgcmVwbGFuLCBpZiBldmVudEJlaW5nUmVwbGFubmVkLm5ld0NvbnN0cmFpbnRzLm5ld1RpbWVXaW5kb3dTdGFydFVUQyBpcyBzZXQsIHVzZSBpdCBoZXJlIGZvciByZWxldmFudCBhdHRlbmRlZXNcbiAgICAgICAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgICAgICBjdXJyZW50RXh0ZXJuYWxBdHRlbmRlZXMsIC8vIFVzZSBmaW5hbGl6ZWQgbGlzdFxuICAgICAgICAgICAgZXh0ZXJuYWxNZWV0aW5nRXZlbnRQbHVzLFxuICAgICAgICAgICAgbmV3RXh0ZXJuYWxNZWV0aW5nRXZlbnRzUGx1cyxcbiAgICAgICAgICAgIC8vIFBhc3MgbWVldGluZ0Fzc2lzdElkIGlmIGF2YWlsYWJsZSAoZS5nLiBmcm9tIGV2ZW50QmVpbmdSZXBsYW5uZWQgb3Igb3RoZXIgY29udGV4dClcbiAgICAgICAgICAgIC8vIEZvciBub3csIGFzc3VtaW5nIGl0IG1pZ2h0IGNvbWUgZnJvbSB0aGUgZXZlbnQgYmVpbmcgcmVwbGFubmVkIGlmIGl0J3MgYSBtZWV0aW5nIGFzc2lzdCBldmVudFxuICAgICAgICAgICAgZXZlbnRCZWluZ1JlcGxhbm5lZD8ub3JpZ2luYWxFdmVudElkLmluY2x1ZGVzKCcjJylcbiAgICAgICAgICAgICAgPyBudWxsXG4gICAgICAgICAgICAgIDogZXZlbnRCZWluZ1JlcGxhbm5lZD8ub3JpZ2luYWxFdmVudElkLCAvLyBTaW1wbGlzdGljIGNoZWNrLCBtaWdodCBuZWVkIGJldHRlciBsb2dpY1xuICAgICAgICAgICAgLy8gUGFzcyBpc1JlcGxhbiBhbmQgZXZlbnRCZWluZ1JlcGxhbm5lZCBmb3IgbW9kaWZpYWJsZSBmbGFnIGFuZCBkdXJhdGlvbiBsb2dpY1xuICAgICAgICAgICAgaXNSZXBsYW4sXG4gICAgICAgICAgICBldmVudEJlaW5nUmVwbGFubmVkXG4gICAgICAgICAgKVxuICAgICAgICA6IG51bGw7XG5cbiAgICBjb25zdCBldmVudFBhcnRzOiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlW10gPSBbXTtcbiAgICBjb25zdCBhbGxFdmVudHNGb3JQbGFubmVyOiBFdmVudFBsdXNUeXBlW10gPSBbXTtcbiAgICBjb25zdCBicmVha3M6IEV2ZW50UGx1c1R5cGVbXSA9IFtdO1xuICAgIGNvbnN0IG9sZEV2ZW50c0ZvclBsYW5uZXI6IEV2ZW50UGx1c1R5cGVbXSA9IFtdO1xuICAgIGNvbnN0IG9sZEF0dGVuZGVlRXZlbnRzOiBNZWV0aW5nQXNzaXN0RXZlbnRUeXBlW10gPSBbXTtcbiAgICBjb25zdCB1bmZpbHRlcmVkVGltZXNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuICAgIGNvbnN0IHVuZmlsdGVyZWRVc2VyTGlzdDogVXNlclBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSA9IFtdO1xuXG4gICAgaWYgKFxuICAgICAgKHJldHVyblZhbHVlc0Zyb21Ib3N0IGFzIFJldHVybkJvZHlGb3JIb3N0Rm9yT3B0YXBsYW5uZXJQcmVwVHlwZSlcbiAgICAgICAgPy5ldmVudFBhcnRzPy5sZW5ndGggPiAwXG4gICAgKSB7XG4gICAgICBldmVudFBhcnRzLnB1c2goXG4gICAgICAgIC4uLihyZXR1cm5WYWx1ZXNGcm9tSG9zdCBhcyBSZXR1cm5Cb2R5Rm9ySG9zdEZvck9wdGFwbGFubmVyUHJlcFR5cGUpXG4gICAgICAgICAgPy5ldmVudFBhcnRzXG4gICAgICApO1xuICAgIH1cblxuICAgIGlmIChcbiAgICAgIChyZXR1cm5WYWx1ZXNGcm9tSG9zdCBhcyBSZXR1cm5Cb2R5Rm9ySG9zdEZvck9wdGFwbGFubmVyUHJlcFR5cGUpXG4gICAgICAgID8uYWxsRXZlbnRzPy5sZW5ndGggPiAwXG4gICAgKSB7XG4gICAgICBhbGxFdmVudHNGb3JQbGFubmVyLnB1c2goXG4gICAgICAgIC4uLihyZXR1cm5WYWx1ZXNGcm9tSG9zdCBhcyBSZXR1cm5Cb2R5Rm9ySG9zdEZvck9wdGFwbGFubmVyUHJlcFR5cGUpXG4gICAgICAgICAgPy5hbGxFdmVudHNcbiAgICAgICk7XG4gICAgfVxuXG4gICAgaWYgKFxuICAgICAgKHJldHVyblZhbHVlc0Zyb21Ib3N0IGFzIFJldHVybkJvZHlGb3JIb3N0Rm9yT3B0YXBsYW5uZXJQcmVwVHlwZSk/LmJyZWFrc1xuICAgICAgICA/Lmxlbmd0aCA+IDBcbiAgICApIHtcbiAgICAgIGJyZWFrcy5wdXNoKFxuICAgICAgICAuLi4ocmV0dXJuVmFsdWVzRnJvbUhvc3QgYXMgUmV0dXJuQm9keUZvckhvc3RGb3JPcHRhcGxhbm5lclByZXBUeXBlKVxuICAgICAgICAgID8uYnJlYWtzXG4gICAgICApO1xuICAgIH1cblxuICAgIGlmIChcbiAgICAgIChyZXR1cm5WYWx1ZXNGcm9tSG9zdCBhcyBSZXR1cm5Cb2R5Rm9ySG9zdEZvck9wdGFwbGFubmVyUHJlcFR5cGUpXG4gICAgICAgID8ub2xkRXZlbnRzPy5sZW5ndGggPiAwXG4gICAgKSB7XG4gICAgICBvbGRFdmVudHNGb3JQbGFubmVyLnB1c2goXG4gICAgICAgIC4uLihyZXR1cm5WYWx1ZXNGcm9tSG9zdCBhcyBSZXR1cm5Cb2R5Rm9ySG9zdEZvck9wdGFwbGFubmVyUHJlcFR5cGUpXG4gICAgICAgICAgPy5vbGRFdmVudHNcbiAgICAgICk7XG4gICAgfVxuXG4gICAgaWYgKFxuICAgICAgKHJldHVyblZhbHVlc0Zyb21Ib3N0IGFzIFJldHVybkJvZHlGb3JIb3N0Rm9yT3B0YXBsYW5uZXJQcmVwVHlwZSlcbiAgICAgICAgPy50aW1lc2xvdHM/Lmxlbmd0aCA+IDBcbiAgICApIHtcbiAgICAgIHVuZmlsdGVyZWRUaW1lc2xvdHMucHVzaChcbiAgICAgICAgLi4uKHJldHVyblZhbHVlc0Zyb21Ib3N0IGFzIFJldHVybkJvZHlGb3JIb3N0Rm9yT3B0YXBsYW5uZXJQcmVwVHlwZSlcbiAgICAgICAgICA/LnRpbWVzbG90c1xuICAgICAgKTtcbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICAocmV0dXJuVmFsdWVzRnJvbUhvc3QgYXMgUmV0dXJuQm9keUZvckhvc3RGb3JPcHRhcGxhbm5lclByZXBUeXBlKVxuICAgICAgICA/LnVzZXJQbGFubmVyUmVxdWVzdEJvZHk/LmlkXG4gICAgKSB7XG4gICAgICB1bmZpbHRlcmVkVXNlckxpc3QucHVzaChcbiAgICAgICAgKHJldHVyblZhbHVlc0Zyb21Ib3N0IGFzIFJldHVybkJvZHlGb3JIb3N0Rm9yT3B0YXBsYW5uZXJQcmVwVHlwZSlcbiAgICAgICAgICA/LnVzZXJQbGFubmVyUmVxdWVzdEJvZHlcbiAgICAgICk7XG4gICAgfVxuXG4gICAgaWYgKFxuICAgICAgKFxuICAgICAgICByZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMgYXMgUmV0dXJuQm9keUZvckF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZVxuICAgICAgKT8udXNlckxpc3Q/LlswXT8uaWRcbiAgICApIHtcbiAgICAgIHVuZmlsdGVyZWRVc2VyTGlzdC5wdXNoKFxuICAgICAgICAuLi4oXG4gICAgICAgICAgcmV0dXJuVmFsdWVzRnJvbUludGVybmFsQXR0ZW5kZWVzIGFzIFJldHVybkJvZHlGb3JBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGVcbiAgICAgICAgKT8udXNlckxpc3RcbiAgICAgICk7XG4gICAgfVxuXG4gICAgKFxuICAgICAgcmV0dXJuVmFsdWVzRnJvbUludGVybmFsQXR0ZW5kZWVzIGFzIFJldHVybkJvZHlGb3JBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGVcbiAgICApPy5ldmVudFBhcnRzPy5mb3JFYWNoKChlKSA9PlxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGUsXG4gICAgICAgICcgKHJldHVyblZhbHVlc0Zyb21JbnRlcm5hbEF0dGVuZGVlcyBhcyBSZXR1cm5Cb2R5Rm9yQXR0ZW5kZWVGb3JPcHRhcGxhbm5lclByZXBUeXBlKT8uZXZlbnRQYXJ0cydcbiAgICAgIClcbiAgICApO1xuXG4gICAgaWYgKFxuICAgICAgKFxuICAgICAgICByZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMgYXMgUmV0dXJuQm9keUZvckF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZVxuICAgICAgKT8uZXZlbnRQYXJ0cz8ubGVuZ3RoID4gMFxuICAgICkge1xuICAgICAgZXZlbnRQYXJ0cy5wdXNoKFxuICAgICAgICAuLi4oXG4gICAgICAgICAgcmV0dXJuVmFsdWVzRnJvbUludGVybmFsQXR0ZW5kZWVzIGFzIFJldHVybkJvZHlGb3JBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGVcbiAgICAgICAgKT8uZXZlbnRQYXJ0c1xuICAgICAgKTtcbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICAoXG4gICAgICAgIHJldHVyblZhbHVlc0Zyb21JbnRlcm5hbEF0dGVuZGVlcyBhcyBSZXR1cm5Cb2R5Rm9yQXR0ZW5kZWVGb3JPcHRhcGxhbm5lclByZXBUeXBlXG4gICAgICApPy5hbGxFdmVudHM/Lmxlbmd0aCA+IDBcbiAgICApIHtcbiAgICAgIGFsbEV2ZW50c0ZvclBsYW5uZXIucHVzaChcbiAgICAgICAgLi4uKFxuICAgICAgICAgIHJldHVyblZhbHVlc0Zyb21JbnRlcm5hbEF0dGVuZGVlcyBhcyBSZXR1cm5Cb2R5Rm9yQXR0ZW5kZWVGb3JPcHRhcGxhbm5lclByZXBUeXBlXG4gICAgICAgICk/LmFsbEV2ZW50c1xuICAgICAgKTtcbiAgICB9XG5cbiAgICAoXG4gICAgICByZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMgYXMgUmV0dXJuQm9keUZvckF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZVxuICAgICk/LmJyZWFrcz8uZm9yRWFjaCgoZSkgPT5cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBlLFxuICAgICAgICAnIChyZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMgYXMgUmV0dXJuQm9keUZvckF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZSk/LmJyZWFrcydcbiAgICAgIClcbiAgICApO1xuXG4gICAgaWYgKFxuICAgICAgKFxuICAgICAgICByZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMgYXMgUmV0dXJuQm9keUZvckF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZVxuICAgICAgKT8uYnJlYWtzPy5sZW5ndGggPiAwXG4gICAgKSB7XG4gICAgICBicmVha3MucHVzaChcbiAgICAgICAgLi4uKFxuICAgICAgICAgIHJldHVyblZhbHVlc0Zyb21JbnRlcm5hbEF0dGVuZGVlcyBhcyBSZXR1cm5Cb2R5Rm9yQXR0ZW5kZWVGb3JPcHRhcGxhbm5lclByZXBUeXBlXG4gICAgICAgICk/LmJyZWFrc1xuICAgICAgKTtcbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICAoXG4gICAgICAgIHJldHVyblZhbHVlc0Zyb21JbnRlcm5hbEF0dGVuZGVlcyBhcyBSZXR1cm5Cb2R5Rm9yQXR0ZW5kZWVGb3JPcHRhcGxhbm5lclByZXBUeXBlXG4gICAgICApPy5vbGRFdmVudHM/Lmxlbmd0aCA+IDBcbiAgICApIHtcbiAgICAgIG9sZEV2ZW50c0ZvclBsYW5uZXIucHVzaChcbiAgICAgICAgLi4uKFxuICAgICAgICAgIHJldHVyblZhbHVlc0Zyb21JbnRlcm5hbEF0dGVuZGVlcyBhcyBSZXR1cm5Cb2R5Rm9yQXR0ZW5kZWVGb3JPcHRhcGxhbm5lclByZXBUeXBlXG4gICAgICAgICk/Lm9sZEV2ZW50c1xuICAgICAgKTtcbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICAoXG4gICAgICAgIHJldHVyblZhbHVlc0Zyb21JbnRlcm5hbEF0dGVuZGVlcyBhcyBSZXR1cm5Cb2R5Rm9yQXR0ZW5kZWVGb3JPcHRhcGxhbm5lclByZXBUeXBlXG4gICAgICApPy50aW1lc2xvdHM/Lmxlbmd0aCA+IDBcbiAgICApIHtcbiAgICAgIHVuZmlsdGVyZWRUaW1lc2xvdHMucHVzaChcbiAgICAgICAgLi4uKFxuICAgICAgICAgIHJldHVyblZhbHVlc0Zyb21JbnRlcm5hbEF0dGVuZGVlcyBhcyBSZXR1cm5Cb2R5Rm9yQXR0ZW5kZWVGb3JPcHRhcGxhbm5lclByZXBUeXBlXG4gICAgICAgICk/LnRpbWVzbG90c1xuICAgICAgKTtcbiAgICB9XG5cbiAgICBpZiAocmV0dXJuVmFsdWVzRnJvbUV4dGVybmFsQXR0ZW5kZWVzPy5ldmVudFBhcnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICBldmVudFBhcnRzLnB1c2goLi4ucmV0dXJuVmFsdWVzRnJvbUV4dGVybmFsQXR0ZW5kZWVzPy5ldmVudFBhcnRzKTtcbiAgICB9XG5cbiAgICBpZiAocmV0dXJuVmFsdWVzRnJvbUV4dGVybmFsQXR0ZW5kZWVzPy5hbGxFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGFsbEV2ZW50c0ZvclBsYW5uZXIucHVzaCguLi5yZXR1cm5WYWx1ZXNGcm9tRXh0ZXJuYWxBdHRlbmRlZXM/LmFsbEV2ZW50cyk7XG4gICAgfVxuXG4gICAgaWYgKHJldHVyblZhbHVlc0Zyb21FeHRlcm5hbEF0dGVuZGVlcz8ub2xkQXR0ZW5kZWVFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIG9sZEF0dGVuZGVlRXZlbnRzLnB1c2goXG4gICAgICAgIC4uLnJldHVyblZhbHVlc0Zyb21FeHRlcm5hbEF0dGVuZGVlcz8ub2xkQXR0ZW5kZWVFdmVudHNcbiAgICAgICk7XG4gICAgfVxuXG4gICAgaWYgKHJldHVyblZhbHVlc0Zyb21FeHRlcm5hbEF0dGVuZGVlcz8udGltZXNsb3RzPy5sZW5ndGggPiAwKSB7XG4gICAgICB1bmZpbHRlcmVkVGltZXNsb3RzLnB1c2goLi4ucmV0dXJuVmFsdWVzRnJvbUV4dGVybmFsQXR0ZW5kZWVzPy50aW1lc2xvdHMpO1xuICAgIH1cblxuICAgIGlmIChyZXR1cm5WYWx1ZXNGcm9tRXh0ZXJuYWxBdHRlbmRlZXM/LnVzZXJMaXN0Py5sZW5ndGggPiAwKSB7XG4gICAgICB1bmZpbHRlcmVkVXNlckxpc3QucHVzaCguLi5yZXR1cm5WYWx1ZXNGcm9tRXh0ZXJuYWxBdHRlbmRlZXM/LnVzZXJMaXN0KTtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhvbGRFdmVudHMsICcgb2xkRXZlbnRzIGJlZm9yZSBzYXZpbmcgdG8gczMnKTtcblxuICAgIGNvbnN0IGR1cGxpY2F0ZUZyZWVFdmVudFBhcnRzID0gXy51bmlxV2l0aChldmVudFBhcnRzLCBfLmlzRXF1YWwpO1xuICAgIGNvbnN0IGR1cGxpY2F0ZUZyZWVBbGxFdmVudHMgPSBfLnVuaXFXaXRoKGFsbEV2ZW50c0ZvclBsYW5uZXIsIF8uaXNFcXVhbCk7XG4gICAgY29uc3QgZHVwbGljYXRlRnJlZUJyZWFrcyA9IF8udW5pcVdpdGgoYnJlYWtzLCBfLmlzRXF1YWwpO1xuICAgIGNvbnN0IGR1cGxpY2F0ZUZyZWVPbGRFdmVudHMgPSBfLnVuaXFXaXRoKG9sZEV2ZW50cywgXy5pc0VxdWFsKTtcbiAgICBjb25zdCBkdXBsaWNhdGVGcmVlT2xkQXR0ZW5kZWVFdmVudHMgPSBfLnVuaXFXaXRoKFxuICAgICAgb2xkQXR0ZW5kZWVFdmVudHMsXG4gICAgICBfLmlzRXF1YWxcbiAgICApO1xuICAgIGNvbnN0IGR1cGxpY2F0ZUZyZWVUaW1lc2xvdHM6IFRpbWVTbG90VHlwZVtdID0gXy51bmlxV2l0aChcbiAgICAgIHVuZmlsdGVyZWRUaW1lc2xvdHMsXG4gICAgICBfLmlzRXF1YWxcbiAgICApO1xuICAgIGNvbnN0IHNpbmdsZXRvbklkID0gdXVpZCgpO1xuXG4gICAgY29uc29sZS5sb2coZXZlbnRQYXJ0cywgJyBldmVudFBhcnRzIGJlZm9yZSB2YWxpZGF0aW9uJyk7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBkdXBsaWNhdGVGcmVlRXZlbnRQYXJ0cyxcbiAgICAgICcgZHVwbGljYXRlRnJlZUV2ZW50UGFydHMgYmVmb3JlIHZhbGlkYXRpb24nXG4gICAgKTtcbiAgICBjb25zb2xlLmxvZyhkdXBsaWNhdGVGcmVlQWxsRXZlbnRzLCAnIGR1cGxpY2F0ZUZyZWVBbGxFdmVudHMnKTtcbiAgICBjb25zb2xlLmxvZyhkdXBsaWNhdGVGcmVlT2xkRXZlbnRzLCAnIGR1cGxpY2F0ZUZyZWVPbGRFdmVudHMnKTtcbiAgICBjb25zb2xlLmxvZyhkdXBsaWNhdGVGcmVlVGltZXNsb3RzLCAnIGR1cGxpY2F0ZUZyZWVUaW1lc2xvdHMnKTtcbiAgICBpZiAoIWR1cGxpY2F0ZUZyZWVFdmVudFBhcnRzIHx8IGR1cGxpY2F0ZUZyZWVFdmVudFBhcnRzPy5sZW5ndGggPT09IDApIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignRXZlbnQgUGFydHMgbGVuZ3RoIGlzIDAgb3IgZG8gbm90IGV4aXN0Jyk7XG4gICAgfVxuXG4gICAgaWYgKCFkdXBsaWNhdGVGcmVlVGltZXNsb3RzIHx8ICEoZHVwbGljYXRlRnJlZVRpbWVzbG90cz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignIGR1cGxpY2F0ZUZyZWVUaW1lc2xvdHMgaXMgZW1wdHknKTtcbiAgICB9XG5cbiAgICBpZiAoIXVuZmlsdGVyZWRVc2VyTGlzdCB8fCAhKHVuZmlsdGVyZWRVc2VyTGlzdD8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcigndW5maWx0ZXJlZFVzZXJMaXN0IGlzIGVtcHR5Jyk7XG4gICAgfVxuXG4gICAgZHVwbGljYXRlRnJlZVRpbWVzbG90cz8uZm9yRWFjaCgoZCkgPT5cbiAgICAgIGNvbnNvbGUubG9nKGQsICcgZHVwbGljYXRlRnJlZVRpbWVzbG90cycpXG4gICAgKTtcbiAgICB1bmZpbHRlcmVkVXNlckxpc3Q/LmZvckVhY2goKHUpID0+IGNvbnNvbGUubG9nKHUsICcgdW5maWx0ZXJlZFVzZXJMaXN0JykpO1xuICAgIG5ld0hvc3RCdWZmZXJUaW1lcz8uZm9yRWFjaCgoYikgPT5cbiAgICAgIGNvbnNvbGUubG9nKGIuYmVmb3JlRXZlbnQsIGIuYWZ0ZXJFdmVudCwgJyBiLmJlZm9yZUV2ZW50IGIuYWZ0ZXJFdmVudCAnKVxuICAgICk7XG5cbiAgICBjb25zdCBwYXJhbXMgPSB7XG4gICAgICBCb2R5OiBKU09OLnN0cmluZ2lmeSh7XG4gICAgICAgIHNpbmdsZXRvbklkLFxuICAgICAgICBob3N0SWQ6IG1haW5Ib3N0SWQsXG4gICAgICAgIGV2ZW50UGFydHM6IGR1cGxpY2F0ZUZyZWVFdmVudFBhcnRzLFxuICAgICAgICBhbGxFdmVudHM6IGR1cGxpY2F0ZUZyZWVBbGxFdmVudHMsXG4gICAgICAgIGJyZWFrczogZHVwbGljYXRlRnJlZUJyZWFrcyxcbiAgICAgICAgb2xkRXZlbnRzOiBkdXBsaWNhdGVGcmVlT2xkRXZlbnRzLFxuICAgICAgICBvbGRBdHRlbmRlZUV2ZW50czogZHVwbGljYXRlRnJlZU9sZEF0dGVuZGVlRXZlbnRzLFxuICAgICAgICBuZXdIb3N0QnVmZmVyVGltZXM6IG5ld0hvc3RCdWZmZXJUaW1lcyxcbiAgICAgICAgbmV3SG9zdFJlbWluZGVyczogbmV3SG9zdFJlbWluZGVycyxcbiAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICAuLi4oaXNSZXBsYW4gJiZcbiAgICAgICAgICBldmVudEJlaW5nUmVwbGFubmVkICYmIHtcbiAgICAgICAgICAgIGlzUmVwbGFuOiB0cnVlLFxuICAgICAgICAgICAgb3JpZ2luYWxHb29nbGVFdmVudElkOiBldmVudEJlaW5nUmVwbGFubmVkLmdvb2dsZUV2ZW50SWQsXG4gICAgICAgICAgICBvcmlnaW5hbENhbGVuZGFySWQ6IGV2ZW50QmVpbmdSZXBsYW5uZWQuY2FsZW5kYXJJZCxcbiAgICAgICAgICB9KSxcbiAgICAgIH0pLFxuICAgICAgQnVja2V0OiBidWNrZXROYW1lLFxuICAgICAgS2V5OlxuICAgICAgICBpc1JlcGxhbiAmJiBldmVudEJlaW5nUmVwbGFubmVkXG4gICAgICAgICAgPyBgJHttYWluSG9zdElkfS8ke3NpbmdsZXRvbklkfV9SRVBMQU5fJHtldmVudEJlaW5nUmVwbGFubmVkLmdvb2dsZUV2ZW50SWR9Lmpzb25gXG4gICAgICAgICAgOiBgJHttYWluSG9zdElkfS8ke3NpbmdsZXRvbklkfS5qc29uYCxcbiAgICAgIENvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgfTtcblxuICAgIGNvbnN0IHMzQ29tbWFuZCA9IG5ldyBQdXRPYmplY3RDb21tYW5kKHBhcmFtcyk7XG5cbiAgICBjb25zdCBzM1Jlc3BvbnNlID0gYXdhaXQgczNDbGllbnQuc2VuZChzM0NvbW1hbmQpO1xuXG4gICAgY29uc29sZS5sb2coczNSZXNwb25zZSwgJyBzM1Jlc3BvbnNlJyk7XG5cbiAgICBhd2FpdCBvcHRhUGxhbldlZWtseShcbiAgICAgIGR1cGxpY2F0ZUZyZWVUaW1lc2xvdHMsXG4gICAgICB1bmZpbHRlcmVkVXNlckxpc3QsXG4gICAgICBkdXBsaWNhdGVGcmVlRXZlbnRQYXJ0cyxcbiAgICAgIHNpbmdsZXRvbklkLFxuICAgICAgbWFpbkhvc3RJZCxcbiAgICAgIGlzUmVwbGFuICYmIGV2ZW50QmVpbmdSZXBsYW5uZWRcbiAgICAgICAgPyBgJHttYWluSG9zdElkfS8ke3NpbmdsZXRvbklkfV9SRVBMQU5fJHtldmVudEJlaW5nUmVwbGFubmVkLmdvb2dsZUV2ZW50SWR9Lmpzb25gXG4gICAgICAgIDogYCR7bWFpbkhvc3RJZH0vJHtzaW5nbGV0b25JZH0uanNvbmAsXG4gICAgICBvcHRhcGxhbm5lckR1cmF0aW9uLFxuICAgICAgb25PcHRhUGxhbkNhbGVuZGFyQWRtaW5DYWxsQmFja1VybFxuICAgICk7XG5cbiAgICBjb25zb2xlLmxvZygnb3B0YXBsYW5uZXIgcmVxdWVzdCBzZW50Jyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIGV2ZW50cyBmb3Igb3B0YXBsYW5uZXInKTtcbiAgfVxufTtcbiJdfQ==