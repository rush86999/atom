import { authApiToken, bucketName, optaplannerDuration, optaplannerShortDuration, classificationUrl, dayOfWeekIntToString, defaultOpenAIAPIKey, externalMeetingLabel, hasuraAdminSecret, hasuraGraphUrl, meetingLabel, minThresholdScore, onOptaPlanCalendarAdminCallBackUrl, optaPlannerPassword, optaPlannerUrl, optaPlannerUsername, } from '@schedule_event/_libs/constants'; // Removed OpenSearch constants
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
// Removed: import { OpenSearchResponseBodyType } from "./types/OpenSearchResponseType"
import { Configuration, OpenAIApi } from 'openai';
import { getEventById, searchTrainingEvents, deleteTrainingEventsByIds, upsertTrainingEvents, } from '@functions/_utils/lancedb_service'; // Added LanceDB imports
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
export const getEventVectorById = async (id) => {
    try {
        const event = await getEventById(id); // from lancedb_service
        if (event && event.vector) {
            console.log(`Vector found for event ID ${id}`);
            return event.vector;
        }
        console.log(`No event or vector found for ID ${id}`);
        return null;
    }
    catch (e) {
        console.error(`Error fetching event vector for ID ${id} from LanceDB:`, e);
        return null;
    }
};
export const convertEventToVectorSpace2 = async (event) => {
    try {
        if (!event) {
            throw new Error('no event provided to convertEventToVectorSpace2');
        }
        const { summary, notes } = event;
        const text = `${summary}${notes ? `: ${notes}` : ''}`;
        if (!text || text.trim() === ':') {
            console.log('Empty or invalid text for embedding, returning empty array.');
            return [];
        }
        const embeddingRequest = {
            model: 'text-embedding-ada-002',
            input: text,
        };
        const res = await openai.embeddings.create(embeddingRequest);
        const vector = res?.data?.[0]?.embedding;
        console.log(vector
            ? `Vector generated with length: ${vector.length}`
            : 'No vector generated', ' vector inside convertEventToVectorSpace2');
        return vector;
    }
    catch (e) {
        console.error(e, ' unable to convertEventToVectorSpace using OpenAI');
        throw e;
    }
};
export const searchTrainingDataByVector = async (userId, searchVector) => {
    try {
        // Assuming min_score logic is handled by LanceDB's search or not strictly needed,
        // or would require more complex query building if it is.
        // For now, simple search and return top hit.
        const results = await searchTrainingEvents(searchVector, 1, // We need only the top match
        `userId = '${userId.replace(/'/g, "''")}'`);
        if (results && results.length > 0) {
            // console.log(results[0], ' search data from LanceDB training_data');
            return results[0];
        }
        return null;
    }
    catch (e) {
        console.error('Error searching training data in LanceDB:', e);
        throw e; // Or return null based on desired error handling
    }
};
export const deleteTrainingDataById = async (id) => {
    try {
        await deleteTrainingEventsByIds([id]);
        console.log(`Successfully deleted training data for ID: ${id} from LanceDB.`);
    }
    catch (e) {
        console.error(`Error deleting training data for ID ${id} from LanceDB:`, e);
        throw e;
    }
};
export const addTrainingData = async (trainingEntry) => {
    try {
        await upsertTrainingEvents([trainingEntry]);
        console.log(`Successfully added/updated training data for ID: ${trainingEntry.id} in LanceDB.`);
    }
    catch (e) {
        console.error(`Error adding/updating training data for ID ${trainingEntry.id} in LanceDB:`, e);
        throw e;
    }
};
export const convertEventTitleToOpenAIVector = async (title) => {
    try {
        const embeddingRequest = {
            model: 'text-embedding-ada-002',
            input: title,
        };
        const res = await openai.embeddings.create(embeddingRequest);
        console.log(res, ' res inside convertEventTitleToOpenAIVectors');
        return res?.data?.[0]?.embedding;
    }
    catch (e) {
        console.log(e, ' unable to convert event title to openaivectors');
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
        // get events
        // local date
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
    if (preferredStartTimeRange?.dayOfWeek > 0) {
        const dateObject = dayjs(startDate.slice(0, 19))
            .tz(hostTimezone, true)
            .toDate();
        const dateObjectWithSetISODayPossible = setISODay(dateObject, preferredStartTimeRange?.dayOfWeek);
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
    const newEvent = {
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
export const generateNewMeetingEventForHost = (hostAttendee, meetingAssist, windowStartDate, hostTimezone, preferredStartTimeRange) => {
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
    const newEvent = {
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
export const listPreferredTimeRangesForEvent = async (eventId) => {
    try {
        // validate
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
export const adjustStartDatesForBreakEventsForDay = (allEvents, breakEvents, userPreference, timezone) => {
    // validate
    if (!allEvents?.[0]?.id) {
        console.log('no allEvents inside adjustStartDatesForBreakEvents');
        return;
    }
    const startTimes = userPreference.startTimes;
    const endTimes = userPreference.endTimes;
    const dayOfWeekInt = getISODay(dayjs(allEvents?.[0]?.startDate.slice(0, 19)).tz(timezone, true).toDate());
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
                const possibleEndDate = dayjs(filteredEvents[index].startDate.slice(0, 19)).tz(timezone, true);
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
export const generateBreaks = (userPreferences, numberOfBreaksToGenerate, eventMirror, globalCalendarId) => {
    const breaks = [];
    // validate
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
export const shouldGenerateBreakEventsForDay = (workingHours, userPreferences, allEvents) => {
    // validate
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
        // validate
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
            // validate values before calculating
            const startTimes = userPreferences.startTimes;
            const workStartHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
            const workStartMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
            if (dayjs(hostStartDate.slice(0, 19)).isAfter(dayjs(hostStartDate.slice(0, 19)).hour(endHour).minute(endMinute))) {
                // return empty as outside of work time
                return null;
            }
            // change to work start time as work start time after start date
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
            // validate
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
            // guarantee breaks
            const hoursMustBeBreak = workingHours * (1 - userPreferences.maxWorkLoadPercent / 100);
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
        // validate values before calculating
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
        // validate
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
        // guarantee breaks
        const hoursMustBeBreak = workingHours * (1 - userPreferences.maxWorkLoadPercent / 100);
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
                // validate values before calculating
                const startTimes = userPreferences.startTimes;
                const workStartHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
                const workStartMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
                if (dayjs(dayDate.slice(0, 19)).isAfter(dayjs(dayDate.slice(0, 19)).hour(endHour).minute(endMinute))) {
                    // return empty as outside of work time
                    continue;
                }
                // change to work start time as before start time
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
            // validate values before calculating
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
    // 7 days in a week
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
        // firstday can be started outside of work time
        // prioritize work start time over when it is pressed
        // if firstDay start is after end time return []
        const endTimes = userPreference.endTimes;
        const dayOfWeekInt = getISODay(dayjs(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .toDate());
        const dayOfWeekIntByHost = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
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
        // validate values before calculating
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
            // return empty as outside of work time
            return [];
        }
        // change to work start time as after host start time
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
    // not first day start from work start time schedule
    const startTimes = userPreference.startTimes;
    const endTimes = userPreference.endTimes;
    // const month = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).month()
    // const dayOfMonth = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).date()
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
        // validate values before calculating
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
            // return empty as outside of work time
            return [];
        }
        // change to work start time as before start time
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
    // const month = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).month()
    // const dayOfMonth = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).date()
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
    // const endHourByHost = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).hour(endHour).tz(hostTimezone).hour()
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
    // if difference in hours > 23 likely all day event
    if (diffHours > 23) {
        console.log(event.id, event.startDate, event.endDate, ' the start date and end date are more than 23 hours apart');
        return false;
    }
    return true;
};
export const validateEventDatesForExternalAttendee = (event) => {
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
    // if difference in hours > 23 likely all day event
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
    console.log(event.id, eventParts?.[0]?.startDate, eventParts?.[0]?.endDate, eventParts?.[0]?.part, eventParts?.[0]?.lastPart, 'event.id,  eventParts?.[0]?.startDate, eventParts?.[0]?.endDate, eventParts?.[0]?.part, eventParts?.[0]?.lastPart,');
    return eventParts;
};
export const generateEventPartsLite = (event, hostId) => {
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
    console.log(event.id, eventParts?.[0]?.startDate, eventParts?.[0]?.endDate, eventParts?.[0]?.part, eventParts?.[0]?.lastPart, 'event.id,  eventParts?.[0]?.startDate, eventParts?.[0]?.endDate, eventParts?.[0]?.part, eventParts?.[0]?.lastPart,');
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
            // if found skip
            if (foundPart) {
                continue;
            }
            else {
                uniquePreBufferPartForEventIds.push(eventParts[i].forEventId);
            }
        }
    }
    // fill up preBufferEventPartsTotal
    for (let i = 0; i < uniquePreBufferPartForEventIds.length; i++) {
        const returnedEventPartTotal = modifyEventPartsForSingularPreBufferTime(eventParts, uniquePreBufferPartForEventIds[i]);
        preBufferEventPartsTotal.push(...returnedEventPartTotal);
    }
    // remove old values
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
            // if found skip
            if (foundPart) {
                continue;
            }
            else {
                uniquePostBufferPartForEventIds.push(eventParts[i].forEventId);
            }
        }
    }
    // fill up preBufferEventPartsTotal
    for (let i = 0; i < uniquePostBufferPartForEventIds.length; i++) {
        const returnedEventPartTotal = modifyEventPartsForSingularPostBufferTime(eventParts, uniquePostBufferPartForEventIds[i]);
        postBufferEventPartsTotal.push(...returnedEventPartTotal);
    }
    // remove old values
    const eventPartsFiltered = _.differenceBy(eventParts, postBufferEventPartsTotal, 'id');
    // add new values
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
    // add values for postBuffer part
    for (let i = 0; i < postBufferAfterEventPartsSorted.length; i++) {
        if (postBufferEventPartsTotal?.[postBufferActualEventPartsSorted?.length + i]) {
            postBufferEventPartsTotal[postBufferActualEventPartsSorted?.length + i].part = actualEventPreviousLastPart + i + 1;
        }
    }
    // change preEventId's last part and eventId
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
    // set preferred DayOfWeek and Time if not set
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
                // reconstruct events
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
// recurring events are not tagged with weekly or daily task boolean so need to be done manually
export const tagEventForDailyOrWeeklyTask = (eventToSubmit, event) => {
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
    // add default values for user request body
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
        console.log(modifiedAllHostEvents, ' modifiedAllHostEvents inside processEventsForOptaPlannerForMainHost');
        if (newBufferTimeArray?.length > 0) {
            modifiedAllHostEvents.push(...newBufferTimeArray);
        }
        // get user preferences
        const userPreferences = await getUserPreferences(mainHostId);
        // get global primary calendar
        const globalPrimaryCalendar = await getGlobalCalendar(mainHostId);
        // generate timeslots
        const diffDays = dayjs(windowEndDate.slice(0, 19)).diff(dayjs(windowStartDate.slice(0, 19)), 'day');
        const modifiedAllEventsWithBreaks = [];
        const startDatesForEachDay = [];
        for (let i = 0; i <= diffDays; i++) {
            startDatesForEachDay.push(dayjs(windowStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .add(i, 'day')
                .format());
        }
        // add breaks to all events
        let parentBreaks = [];
        const breaks = await generateBreakEventsForDate(userPreferences, mainHostId, windowStartDate, windowEndDate, hostTimezone, globalPrimaryCalendar?.id);
        breaks.forEach((b) => console.log(b, ' generatedBreaks'));
        if (breaks?.length > 0) {
            // modifiedAllEvents.push(...breaks)
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
                // const mostRecentEvent = _.minBy(modifiedAllEventsWithBreaks, (e) => dayjs(e?.startDate).unix())
                const timeslotsForDay = await generateTimeSlotsLiteForInternalAttendee(startDatesForEachDay?.[i], mainHostId, userPreferences, hostTimezone, hostTimezone, true);
                timeslots.push(...timeslotsForDay);
                continue;
            }
            const timeslotsForDay = await generateTimeSlotsLiteForInternalAttendee(startDatesForEachDay?.[i], mainHostId, userPreferences, hostTimezone, hostTimezone, false);
            timeslots.push(...timeslotsForDay);
        }
        // generate event parts
        const filteredAllEvents = _.uniqBy(modifiedAllEventsWithBreaks.filter((e) => validateEventDates(e, userPreferences)), 'id');
        console.log(filteredAllEvents, ' filteredAllEvents inside processEventsForOptaPlannerForMainHost');
        let eventParts = [];
        const eventPartMinisAccumulated = [];
        for (const event of filteredAllEvents) {
            const eventPartMinis = generateEventPartsLite(event, mainHostId);
            eventPartMinisAccumulated.push(...eventPartMinis);
        }
        console.log(eventPartMinisAccumulated, ' eventPartMinisAccumulated inside processEventsForOptaPlannerForMainHost');
        const modifiedEventPartMinisPreBuffer = modifyEventPartsForMultiplePreBufferTime(eventPartMinisAccumulated);
        console.log(modifiedEventPartMinisPreBuffer, ' modifiedEventPartMinisPreBuffer inside processEventsForOptaPlannerForMainHost');
        const modifiedEventPartMinisPreAndPostBuffer = modifyEventPartsForMultiplePostBufferTime(modifiedEventPartMinisPreBuffer);
        console.log(modifiedEventPartMinisPreAndPostBuffer, ' modifiedEventPartMinisPreAndPostBuffer inside processEventsForOptaPlannerForMainHost');
        console.log(userPreferences, workTimes, hostTimezone, ' userPreferences, workTimes, hostTimezone inside processEventsForOptaPlannerForMainHost');
        const formattedEventParts = modifiedEventPartMinisPreAndPostBuffer.map((e) => formatEventTypeToPlannerEvent(e, userPreferences, workTimes, hostTimezone));
        console.log(formattedEventParts, ' formattedEventParts inside processEventsForOptaPlannerForMainHost');
        if (formattedEventParts?.length > 0) {
            eventParts.push(...formattedEventParts);
        }
        console.log(eventParts, ' eventParts inside processEventsForOptaPlannerForMainHost');
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
        // add smart meeting events to all events
        if (filteredOldMeetingEvents?.[0]?.id) {
            modifiedAllEvents.push(...filteredOldMeetingEvents?.map((a) => convertMeetingPlusTypeToEventPlusType(a)));
        }
        if (newBufferTimeArray?.length > 0) {
            modifiedAllEvents.push(...newBufferTimeArray);
        }
        if (newMeetingEvents?.length > 0) {
            // add newly generated host event to rest
            modifiedAllEvents.push(...newMeetingEvents?.map((m) => convertMeetingPlusTypeToEventPlusType(m)));
        }
        modifiedAllEvents?.forEach((e) => console.log(e, ' modifiedAllEvents'));
        // get user preferences
        const unfilteredUserPreferences = [];
        for (const internalAttendee of internalAttendees) {
            const userPreference = await getUserPreferences(internalAttendee?.userId);
            unfilteredUserPreferences.push(userPreference);
        }
        const userPreferences = _.uniqWith(unfilteredUserPreferences, _.isEqual);
        // global primary calendars
        const unfilteredGlobalPrimaryCalendars = [];
        for (const internalAttendee of internalAttendees) {
            const globalPrimaryCalendar = await getGlobalCalendar(internalAttendee?.userId);
            unfilteredGlobalPrimaryCalendars.push(globalPrimaryCalendar);
        }
        const globalPrimaryCalendars = _.uniqWith(unfilteredGlobalPrimaryCalendars, _.isEqual);
        globalPrimaryCalendars?.forEach((c) => console.log(c, ' globalPrimaryCalendars'));
        const modifiedAllEventsWithBreaks = [];
        // add breaks to all events
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
                // modifiedAllEvents.push(...breaks)
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
        // generate timeslots
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
                    // const mostRecentEvent = _.minBy(modifiedAllEventsWithBreaks, (e) => dayjs(e?.startDate).unix())
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
        // generate event parts
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
            // const preferredTimeRanges = await listPreferredTimeRangesForEvent(event?.id)
            // const eventPlus: EventPlusType = { ...event, preferredTimeRanges }
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
export const generateWorkTimesForExternalAttendee = (hostId, userId, attendeeEvents, hostTimezone, userTimezone) => {
    // 7 days in a week
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
export const processEventsForOptaPlannerForExternalAttendees = async (userIds, mainHostId, allExternalEvents, windowStartDate, windowEndDate, hostTimezone, externalAttendees, oldExternalMeetingEvents, // converted from external events
newMeetingEvents) => {
    try {
        const modifiedAllExternalEvents = allExternalEvents?.map((e) => convertMeetingAssistEventTypeToEventPlusType(e, externalAttendees?.find((a) => a?.id === e?.attendeeId)?.userId));
        const oldConvertedMeetingEvents = oldExternalMeetingEvents
            ?.map((a) => convertMeetingPlusTypeToEventPlusType(a))
            ?.filter((e) => !!e);
        if (oldConvertedMeetingEvents?.length > 0) {
            modifiedAllExternalEvents.push(...oldConvertedMeetingEvents);
        }
        if (newMeetingEvents?.length > 0) {
            // add newly generated host event to rest
            modifiedAllExternalEvents.push(...newMeetingEvents?.map((m) => convertMeetingPlusTypeToEventPlusType(m)));
        }
        // generate timeslots
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
        const timeslots = [];
        for (let i = 0; i < startDatesForEachDay.length; i++) {
            if (i === 0) {
                for (const externalAttendee of externalAttendees) {
                    // const mostRecentEvent = _.minBy(modifiedAllExternalEvents, (e) => dayjs(e?.startDate).unix())
                    const timeslotsForDay = await generateTimeSlotsLiteForExternalAttendee(startDatesForEachDay?.[i], mainHostId, modifiedAllExternalEvents, hostTimezone, externalAttendee?.timezone, true);
                    unfilteredTimeslots.push(...timeslotsForDay);
                }
                continue;
            }
            for (const externalAttendee of externalAttendees) {
                const timeSlots = generateTimeSlotsLiteForInternalAttendee(startDatesForEachDay?.[i], mainHostId, modifiedAllExternalEvents, hostTimezone, externalAttendee?.timezone, false);
                unfilteredTimeslots.push(...timeslotsForDay);
            }
        }
        timeslots.push(..._.uniqWith(unfilteredTimeslots, _.isEqual));
        // generate event parts
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
        // populate timeslots with events
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
// attendeeMeetingEvents include hostMeeting as well
export const processEventsForOptaPlanner = async (mainHostId, internalAttendees, meetingEventPlus, // events with a meetingId
newMeetingEventPlus, allEvents, windowStartDate, windowEndDate, hostTimezone, oldEvents, externalAttendees, meetingAssistEvents, newHostReminders, newHostBufferTimes) => {
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
            const foundIndex = externalAttendees?.findIndex((a) => a?.userId === e?.userId);
            if (foundIndex > -1) {
                return null;
            }
            return e;
        })
            ?.filter((e) => e !== null);
        const newExternalMeetingEventsPlus = newMeetingEventPlus
            ?.map((e) => {
            const foundIndex = externalAttendees?.findIndex((a) => a?.userId === e?.userId);
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
        const hostIsInternalAttendee = internalAttendees.some((ia) => ia?.userId === mainHostId);
        let returnValuesFromInternalAttendees = {};
        let returnValuesFromHost = {};
        console.log(hostIsInternalAttendee, ' hostIsInternalAttendee');
        if (hostIsInternalAttendee) {
            returnValuesFromInternalAttendees =
                await processEventsForOptaPlannerForInternalAttendees(mainHostId, allEvents, windowStartDate, windowEndDate, hostTimezone, internalAttendees, oldEvents, meetingEventPlus, newInternalMeetingEventsPlus, newHostBufferTimes);
        }
        else {
            // host is not part of internal attendees
            returnValuesFromHost = await processEventsForOptaPlannerForMainHost(mainHostId, allHostEvents, windowStartDate, windowEndDate, hostTimezone, oldHostEvents, newHostBufferTimes);
        }
        console.log(returnValuesFromInternalAttendees, ' returnValuesFromInternalAttendees');
        const externalMeetingEventPlus = meetingEventPlus
            .map((e) => {
            const foundIndex = externalAttendees.findIndex((a) => a?.userId === e?.userId);
            if (foundIndex > -1) {
                return e;
            }
            return null;
        })
            ?.filter((e) => e !== null);
        const returnValuesFromExternalAttendees = externalAttendees?.length > 0
            ? await processEventsForOptaPlannerForExternalAttendees(externalAttendees?.map((a) => a.userId), mainHostId, meetingAssistEvents, windowStartDate, windowEndDate, hostTimezone, externalAttendees, externalMeetingEventPlus, // events with meetingId
            newExternalMeetingEventsPlus)
            : null;
        const eventParts = [];
        const allEventsForPlanner = [];
        const breaks = [];
        const oldEventsForPlanner = [];
        const oldAttendeeEvents = [];
        const unfilteredTimeslots = [];
        const unfilteredUserList = [];
        // start filling up the arrays for optaPlanner
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
        // create duplicate free data
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
            await optaPlanWeekly(duplicateFreeTimeslots, unfilteredUserList, duplicateFreeEventParts, singletonId, mainHostId, `${mainHostId}/${singletonId}.json`, optaplannerShortDuration, onOptaPlanCalendarAdminCallBackUrl);
        }
        else {
            await optaPlanWeekly(duplicateFreeTimeslots, unfilteredUserList, duplicateFreeEventParts, singletonId, mainHostId, `${mainHostId}/${singletonId}.json`, optaplannerDuration, onOptaPlanCalendarAdminCallBackUrl);
        }
        console.log('optaplanner request sent');
        // update freemium if not active subscription
        // if (!(activeSubscriptions?.length > 0)) {
        //     await updateFreemiumById(freemiumOfUser?.id, freemiumOfUser?.usage - 1 || 0)
        // }
    }
    catch (e) {
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
        return res?.data?.Category;
    }
    catch (e) {
        console.log(e, ' unable to get user categories');
    }
};
export const findBestMatchCategory2 = async (event, possibleLabels) => {
    try {
        // validate
        if (!event) {
            throw new Error('no event passed inside findBestMatchCategory2');
        }
        if (!possibleLabels) {
            throw new Error('no possible labels passed inside findBestMatchCategory2');
        }
        const { summary, notes } = event;
        const sentence = `${summary}${notes ? `: ${notes}` : ''}`;
        const res = await got
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
        console.log(res, event?.id, ' res, event?.id inside findBestMatchCategory2');
        return res;
    }
    catch (e) {
        console.log(e, ' unable to find categories');
    }
};
export const processBestMatchCategories = (body, newPossibleLabels) => {
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
const addToBestMatchCategories = (newEvent, newPossibleLabels, scores, categories) => {
    const bestMatchCategories = [];
    //  if meeting  categories meet threshold add to results
    const meetingIndex = newPossibleLabels.indexOf(meetingLabel);
    const externalMeetingIndex = newPossibleLabels.indexOf(externalMeetingLabel);
    if (meetingIndex > -1 && scores[meetingIndex] > minThresholdScore) {
        bestMatchCategories.push(categories.find((category) => category.name === meetingLabel));
    }
    if (externalMeetingIndex > -1 &&
        scores[externalMeetingIndex] > minThresholdScore) {
        bestMatchCategories.push(categories.find((category) => category.name === externalMeetingLabel));
    }
    // if event is classified as meeting type or external type then also copy over
    if (newEvent.isMeeting && meetingIndex > -1) {
        bestMatchCategories.push(categories.find((category) => category.name === meetingLabel));
    }
    if (newEvent.isExternalMeeting && externalMeetingIndex > -1) {
        bestMatchCategories.push(categories.find((category) => category.name === externalMeetingLabel));
    }
    return bestMatchCategories;
};
export const processEventForMeetingTypeCategories = (newEvent, bestMatchCategory, newPossibleLabels, scores, categories) => {
    // include meeting and conference types if any
    const bestMatchCategories = addToBestMatchCategories(newEvent, newPossibleLabels, scores, categories);
    if (bestMatchCategories?.length > 0) {
        return bestMatchCategories.concat([bestMatchCategory]);
    }
    return [bestMatchCategory];
};
export const getUniqueLabels = (labels) => {
    const uniqueLabels = _.uniqBy(labels, 'id');
    return uniqueLabels;
};
export const copyOverCategoryDefaults = (event, category) => {
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
        priority: (!event?.userModifiedPriorityLevel
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
        preferredTimeRanges: !event?.userModifiedTimePreference &&
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
export const createRemindersAndTimeBlockingForBestMatchCategory = async (id, userId, newEvent, bestMatchCategory, newReminders1, newTimeBlocking1, previousEvent) => {
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
        const reminders = createRemindersUsingCategoryDefaultsForEvent(newEvent, bestMatchCategory, oldReminders, previousEvent);
        console.log(reminders, ' reminders');
        if (reminders?.length > 0 &&
            bestMatchCategory?.copyReminders &&
            !newEvent?.userModifiedReminders) {
            newReminders.push(...reminders);
        }
        if (!newEvent?.userModifiedTimeBlocking &&
            bestMatchCategory?.copyTimeBlocking) {
            // create time blocking
            const bufferTimes = createPreAndPostEventsForCategoryDefaults(bestMatchCategory, newEvent, previousEvent);
            console.log(bufferTimes, ' timeBlocking');
            if (bufferTimes?.beforeEvent) {
                newBufferTimes.beforeEvent =
                    bufferTimes.beforeEvent;
            }
            if (bufferTimes?.afterEvent) {
                newBufferTimes.afterEvent =
                    bufferTimes.afterEvent;
            }
            if (bufferTimes?.newEvent?.preEventId ||
                bufferTimes?.newEvent?.postEventId) {
                newEvent = bufferTimes.newEvent;
            }
        }
        return { newEvent, newReminders, newBufferTimes: newBufferTimes };
    }
    catch (e) {
        console.log(e, ' unable to create reminders and time blocking for best match category');
    }
};
export const createCategoryEvents = async (categoryEvents) => {
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
    }
    catch (e) {
        console.log(e, ' unable to upsert category events');
    }
};
const copyOverCategoryDefaultsForMeetingType = (event, categories) => {
    const meetingCategory = categories.find((category) => category.name === meetingLabel);
    const externalCategory = categories.find((category) => category.name === externalMeetingLabel);
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
export const listRemindersForEvent = async (eventId, userId) => {
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
                    eventId,
                },
            },
        })
            .json();
        console.log(res, ' res from listRemindersForEvent');
        return res?.data?.Reminder;
    }
    catch (e) {
        console.log(e, ' listRemindersForEvent');
    }
};
export const createRemindersUsingCategoryDefaultsForEvent = (event, bestMatchCategory, oldReminders, previousEvent) => {
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
export const createPreAndPostEventsForCategoryDefaults = (bestMatchCategory, event, previousEvent) => {
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
    let valuesToReturn = {};
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
        const afterEvent = {
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
        const formattedZoneBeforeEventStartDate = dayjs(event.startDate.slice(0, 19))
            .tz(event.timezone, true)
            .subtract(bestMatchCategory.defaultTimeBlocking.beforeEvent, 'm')
            .format();
        const formattedZoneBeforeEventEndDate = dayjs(event.startDate.slice(0, 19))
            .tz(event.timezone, true)
            .format();
        const beforeEvent = {
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
export const updateValuesForMeetingTypeCategories = async (event, newEvent1, bestMatchCategories, userId, newReminders1, newTimeBlocking1, previousEvent) => {
    try {
        if (!(bestMatchCategories?.length > 0)) {
            throw new Error('bestMatchCategories cannot be empty inside updateValuesForMeetingTypeCategories ');
        }
        let newEvent = newEvent1;
        let newReminders = newReminders1 || [];
        let newBufferTime = newTimeBlocking1 || {};
        const newCategoryConstantEvents = copyOverCategoryDefaultsForMeetingType(event, bestMatchCategories);
        console.log(newCategoryConstantEvents, ' newCategoryConstantEvents');
        if (newCategoryConstantEvents?.newEventMeeting?.id) {
            newEvent = { ...newEvent, ...newCategoryConstantEvents.newEventMeeting };
            const meetingCategory = bestMatchCategories.find((category) => category.name === meetingLabel);
            // create reminders
            const oldReminders = await listRemindersForEvent(newCategoryConstantEvents.newEventMeeting.id, userId);
            const reminders = createRemindersUsingCategoryDefaultsForEvent(newEvent, meetingCategory, oldReminders, previousEvent);
            console.log(reminders, ' reminders');
            if (reminders?.length > 0) {
                newReminders.push(...reminders);
                newReminders = _.uniqBy(newReminders, 'minutes');
            }
            // create time blocking
            const bufferTime = createPreAndPostEventsForCategoryDefaults(meetingCategory, newEvent, previousEvent);
            console.log(bufferTime, ' timeBlocking');
            if (bufferTime?.beforeEvent) {
                newBufferTime.beforeEvent = bufferTime.beforeEvent;
            }
            if (bufferTime?.afterEvent) {
                newBufferTime.afterEvent = bufferTime.afterEvent;
            }
            if (bufferTime?.newEvent?.preEventId ||
                bufferTime?.newEvent?.postEventId) {
                newEvent = bufferTime.newEvent;
            }
        }
        if (newCategoryConstantEvents?.newEventExternal?.id) {
            newEvent = { ...newEvent, ...newCategoryConstantEvents.newEventExternal };
            const externalCategory = bestMatchCategories.find((category) => category.name === externalMeetingLabel);
            // create reminders
            const oldReminders = await listRemindersForEvent(newCategoryConstantEvents.newEventExternal.id, userId);
            const reminders = createRemindersUsingCategoryDefaultsForEvent(newEvent, externalCategory, oldReminders, previousEvent);
            console.log(reminders, ' reminders');
            if (reminders?.length > 0) {
                newReminders.push(...reminders);
                newReminders = _.uniqBy(newReminders, 'minutes');
            }
            // create time blocking
            const timeBlocking = createPreAndPostEventsForCategoryDefaults(externalCategory, newEvent, previousEvent);
            console.log(timeBlocking, ' timeBlocking');
            if (timeBlocking?.beforeEvent) {
                newBufferTime.beforeEvent = timeBlocking.beforeEvent;
            }
            if (timeBlocking?.afterEvent) {
                newBufferTime.afterEvent = timeBlocking.afterEvent;
            }
            if (timeBlocking?.newEvent?.preEventId ||
                timeBlocking?.newEvent?.postEventId) {
                newEvent = timeBlocking.newEvent;
            }
        }
        return { newEvent, newReminders, newTimeBlocking: newBufferTime };
    }
    catch (e) {
        console.log(e, ' unable to update values for default categories');
    }
};
export const processUserEventForCategoryDefaults = async (event, vector) => {
    try {
        const { id, userId } = event;
        console.log(id, ' id inside processUserEventForCategoryDefaults');
        //  create new event datatype in elastic search
        // await putDataInSearch(id, vector, userId)
        // find categories and copy over defaults if any
        const categories = await getUserCategories(userId);
        if (!categories?.[0]?.id) {
            throw new Error('categories is not available processUserEventForCategoryDefaults');
        }
        // labelConstants are already part of categories
        console.log(categories, id, ' categories, id processUserEventForCategoryDefaults');
        const body = await findBestMatchCategory2(event, categories);
        console.log(body, id, ' body, id processUserEventForCategoryDefaults');
        const { labels, scores } = body;
        const bestMatchLabel = processBestMatchCategories(body, labels);
        console.log(bestMatchLabel, id, ' bestMatchLabel, id processUserEventForCategoryDefaults');
        if (bestMatchLabel) {
            const bestMatchCategory = categories.find((category) => category.name === bestMatchLabel);
            let bestMatchPlusMeetingCategories = await processEventForMeetingTypeCategories(event, bestMatchCategory, labels, scores, categories);
            if (bestMatchPlusMeetingCategories?.length > 0) {
                bestMatchPlusMeetingCategories = getUniqueLabels(bestMatchPlusMeetingCategories);
                console.log(bestMatchPlusMeetingCategories, id, ' bestMatchAndMeetingCategories, id processUserEventForCategoryDefaults');
            }
            //  copy over category defaults
            const newCategoryDefaultEvent = copyOverCategoryDefaults(event, bestMatchCategory);
            console.log(newCategoryDefaultEvent, id, ' newCategoryDefaultEvent, id processUserEventForCategoryDefaults');
            // create new event
            let newEvent = newCategoryDefaultEvent ?? event;
            console.log(newEvent, ' newEvent processUserEventForCategoryDefaults');
            let newReminders = [];
            let newTimeBlocking = {};
            const { newEvent: newEvent1, newReminders: newReminders1, newBufferTimes: newTimeBlocking1, } = await createRemindersAndTimeBlockingForBestMatchCategory(id, userId, newEvent, bestMatchCategory, newReminders, newTimeBlocking);
            newEvent = newEvent1;
            newReminders = newReminders1;
            newTimeBlocking = newTimeBlocking1;
            if (bestMatchPlusMeetingCategories?.length > 0) {
                const categoryEvents = bestMatchPlusMeetingCategories.map((c) => {
                    const categoryEvent = {
                        categoryId: c.id,
                        eventId: id,
                        userId,
                        id: uuid(),
                        createdDate: new Date().toISOString(),
                        updatedAt: new Date().toISOString(),
                    };
                    return categoryEvent;
                });
                console.log(categoryEvents, id, ' categoryEvents, id processUserEventForCategoryDefaults');
                await createCategoryEvents(categoryEvents);
                const { newEvent: newEvent1, newReminders: newReminders1, newTimeBlocking: newTimeBlocking1, } = await updateValuesForMeetingTypeCategories(event, newEvent, bestMatchPlusMeetingCategories, userId, newReminders, newTimeBlocking);
                newEvent = newEvent1;
                newReminders = newReminders1;
                newTimeBlocking = newTimeBlocking1;
            }
            newEvent.vector = vector;
            console.log(newEvent, ' newEvent processUserEventForCategoryDefaults');
            console.log(newReminders, ' newReminders processUserEventForCategoryDefaults');
            console.log(newTimeBlocking, ' newTimeBlocking processUserEventForCategoryDefaults');
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
    }
    catch (e) {
        console.log(e, ' e');
    }
};
export const getEventFromPrimaryKey = async (eventId) => {
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
                    eventId,
                },
            },
        })
            .json();
        console.log(res, ' res from getEventFromPrimaryKey');
        return res?.data?.Event_by_pk;
    }
    catch (e) {
        console.log(e, ' getEventFromPrimaryKey');
    }
};
export const deleteDocInSearch3 = async (id) => {
    try {
        const client = await getSearchClient();
        const response = await client.delete({
            id,
            index: searchIndex,
        });
        console.log('Deleting document in search:');
        console.log(response.body);
    }
    catch (e) {
        console.log(e, ' unable to delete doc');
    }
};
export const copyOverPreviousEventDefaults = (event, previousEvent, category, userPreferences) => {
    const previousDuration = dayjs
        .duration(dayjs(previousEvent.endDate.slice(0, 19))
        .tz(previousEvent?.timezone, true)
        .diff(dayjs(previousEvent.startDate.slice(0, 19)).tz(previousEvent?.timezone, true)))
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
        priority: (!event?.userModifiedPriorityLevel
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
                            ? category.defaultTimePreference.map((tp) => ({
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUNMLFlBQVksRUFDWixVQUFVLEVBQ1YsbUJBQW1CLEVBQ25CLHdCQUF3QixFQUN4QixpQkFBaUIsRUFDakIsb0JBQW9CLEVBQ3BCLG1CQUFtQixFQUNuQixvQkFBb0IsRUFDcEIsaUJBQWlCLEVBQ2pCLGNBQWMsRUFDZCxZQUFZLEVBQ1osaUJBQWlCLEVBQ2pCLGtDQUFrQyxFQUNsQyxtQkFBbUIsRUFDbkIsY0FBYyxFQUNkLG1CQUFtQixHQUNwQixNQUFNLGlDQUFpQyxDQUFDLENBQUMsK0JBQStCO0FBdUN6RSxPQUFPLEdBQUcsTUFBTSxLQUFLLENBQUM7QUFDdEIsT0FBTyxFQUFFLEVBQUUsSUFBSSxJQUFJLEVBQUUsTUFBTSxNQUFNLENBQUM7QUFDbEMsT0FBTyxFQUFFLFNBQVMsRUFBRSxTQUFTLEVBQUUsTUFBTSxVQUFVLENBQUM7QUFDaEQsT0FBTyxLQUFLLE1BQU0sT0FBTyxDQUFDO0FBQzFCLDZDQUE2QztBQUM3QyxPQUFPLFFBQVEsTUFBTSx1QkFBdUIsQ0FBQztBQUM3QyxPQUFPLFNBQVMsTUFBTSx3QkFBd0IsQ0FBQztBQUMvQyxPQUFPLFFBQVEsTUFBTSx1QkFBdUIsQ0FBQztBQUM3QyxPQUFPLEdBQUcsTUFBTSxrQkFBa0IsQ0FBQztBQUNuQyxPQUFPLENBQUMsTUFBTSxRQUFRLENBQUM7QUFDdkIsT0FBTyxFQUFFLGdCQUFnQixFQUFFLFFBQVEsRUFBRSxNQUFNLG9CQUFvQixDQUFDO0FBRWhFLHVGQUF1RjtBQUN2RixPQUFPLEVBQUUsYUFBYSxFQUFFLFNBQVMsRUFBRSxNQUFNLFFBQVEsQ0FBQztBQUNsRCxPQUFPLEVBQ0wsWUFBWSxFQUNaLG9CQUFvQixFQUNwQix5QkFBeUIsRUFDekIsb0JBQW9CLEdBR3JCLE1BQU0sbUNBQW1DLENBQUMsQ0FBQyx3QkFBd0I7QUFFcEUs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QUMsWUFBWSxFQUFFLFFBQVEsSUFBSSxZQUFZLEVBQUUsSUFBSSxDQUFDO2FBQ2hELEVBQUUsQ0FBQyxZQUFZLENBQUM7YUFDaEIsU0FBUyxDQUNSLEtBQUssQ0FBQyxZQUFZLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7YUFDdkMsRUFBRSxDQUFDLFlBQVksRUFBRSxRQUFRLElBQUksWUFBWSxFQUFFLElBQUksQ0FBQzthQUNoRCxFQUFFLENBQUMsWUFBWSxDQUFDO2FBQ2hCLE1BQU0sQ0FBQyxFQUFFLENBQUMsRUFDYixLQUFLLENBQUMsWUFBWSxDQUFDLFNBQVMsQ0FBQyxLQUFLLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO2FBQ3ZDLEVBQUUsQ0FBQyxZQUFZLEVBQUUsUUFBUSxJQUFJLFlBQVksRUFBRSxJQUFJLENBQUM7YUFDaEQsRUFBRSxDQUFDLFlBQVksQ0FBQzthQUNoQixNQUFNLENBQUMsRUFBRSxDQUFDLEVBQ2IsUUFBUSxFQUNSLElBQUksQ0FDTDtZQUNMLENBQUMsQ0FBQyxFQUFFO1lBQ0osQ0FBQyxDQUFDLEtBQUssQ0FBQyxZQUFZLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7aUJBQ3JDLEVBQUUsQ0FBQyxZQUFZLEVBQUUsUUFBUSxJQUFJLFlBQVksRUFBRSxJQUFJLENBQUM7aUJBQ2hELEVBQUUsQ0FBQyxZQUFZLENBQUM7aUJBQ2hCLFNBQVMsQ0FDUixLQUFLLENBQUMsWUFBWSxDQUFDLFNBQVMsQ0FBQyxLQUFLLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO2lCQUN2QyxFQUFFLENBQUMsWUFBWSxFQUFFLFFBQVEsSUFBSSxZQUFZLEVBQUUsSUFBSSxDQUFDO2lCQUNoRCxFQUFFLENBQUMsWUFBWSxDQUFDO2lCQUNoQixNQUFNLENBQUMsRUFBRSxDQUFDLEVBQ2IsS0FBSyxDQUFDLFlBQVksQ0FBQyxTQUFTLENBQUMsS0FBSyxDQUFDLENBQUMsRUFBRSxFQUFFLENB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QztTQUNoRCxFQUFFLENBQUMsWUFBWSxDQUFDO1NBQ2hCLElBQUksRUFBRSxDQUFDO0lBQ1YsTUFBTSxxQkFBcUIsR0FBRyxLQUFLLENBQUMsWUFBWSxDQUFDLFNBQVMsQ0FBQyxLQUFLLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1NBQ3JFLEVBQUUsQ0FBQyxZQUFZLEVBQUUsUUFBUSxJQUFJLFlBQVksRUFBRSxJQUFJLENBQUM7U0FDaEQsRUFBRSxDQUFDLFlBQVksQ0FBQztTQUNoQixTQUFTLENBQ1IsS0FBSyxDQUFDLFlBQVksQ0FBQyxTQUFTLENBQUMsS0FBSyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQztTQUN2QyxFQUFFLENBQUMsWUFBWSxFQUFFLFFBQVEsSUFBSSxZQUFZLEVBQUUsSUFBSSxDQUFDO1NBQ2hELEVBQUUsQ0FBQyxZQUFZLENBQUM7U0FDaEIsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUNaLEtBQUssQ0FBQyxZQUFZLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7U0FDdkMsRUFBRSxDQUFDLFlBQVksRUFBRSxRQUFRLElBQUksWUFBWSxFQUFFLElBQUksQ0FBQztTQUNoRCxFQUFFLENBQUMsWUFBWSxDQUFDO1NBQ2hCLE1BQU0sQ0FBQyxFQUFFLENBQUMsRUFDYixRQUFRLEVBQ1IsSUFBSSxDQUNMO1FBQ0QsQ0FBQyxDQUFDLENBQUM7UUFDSCxDQUFDLENBQUMsS0FBSyxDQUFDLFlBQVksQ0FBQyxTQUFTLENBQUMsS0FBSyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQzthQUNyQyxFQUFFLENBQUMsWUFBWSxFQUFFLFFBQVEsSUFBSSxZQUFZLEVBQUUsSUFBSSxDQUFDO2FBQ2hELEVBQUUsQ0FBQyxZQUFZLENBQUM7YUFDaEIsU0FBUyxDQUNSLEtBQUssQ0FBQyxZQUFZLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7YUFDdkMsRUFBRSxDQUFDLFlBQVksRUFBRSxR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RTtnQ0FDVixPQUFPLEVBQUUsS0FBSyxFQUFFLEVBQUU7Z0NBQ2xCLFdBQVcsRUFBRSxLQUFLLEVBQUUsQ0FBQyxXQUFXLEVBQUU7Z0NBQ2xDLFNBQVMsRUFBRSxLQUFLLEVBQUUsQ0FBQyxXQUFXLEVBQUU7Z0NBQ2hDLE1BQU0sRUFBRSxLQUFLLEVBQUUsTUFBTTs2QkFDdEIsQ0FBQyxDQUFDOzRCQUNMLENBQUMsQ0FBQyxLQUFLLEVBQUUsbUJBQW1CO1lBQ3BDLENBQUMsQ0FBQyxLQUFLLENBQUMsbUJBQW1CO0tBQzlCLENBQUM7QUFDSixDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICBhdXRoQXBpVG9rZW4sXG4gIGJ1Y2tldE5hbWUsXG4gIG9wdGFwbGFubmVyRHVyYXRpb24sXG4gIG9wdGFwbGFubmVyU2hvcnREdXJhdGlvbixcbiAgY2xhc3NpZmljYXRpb25VcmwsXG4gIGRheU9mV2Vla0ludFRvU3RyaW5nLFxuICBkZWZhdWx0T3BlbkFJQVBJS2V5LFxuICBleHRlcm5hbE1lZXRpbmdMYWJlbCxcbiAgaGFzdXJhQWRtaW5TZWNyZXQsXG4gIGhhc3VyYUdyYXBoVXJsLFxuICBtZWV0aW5nTGFiZWwsXG4gIG1pblRocmVzaG9sZFNjb3JlLFxuICBvbk9wdGFQbGFuQ2FsZW5kYXJBZG1pbkNhbGxCYWNrVXJsLFxuICBvcHRhUGxhbm5lclBhc3N3b3JkLFxuICBvcHRhUGxhbm5lclVybCxcbiAgb3B0YVBsYW5uZXJVc2VybmFtZSxcbn0gZnJvbSAnQHNjaGVkdWxlX2V2ZW50L19saWJzL2NvbnN0YW50cyc7IC8vIFJlbW92ZWQgT3BlblNlYXJjaCBjb25zdGFudHNcbmltcG9ydCB7XG4gIEJ1ZmZlclRpbWVOdW1iZXJUeXBlLFxuICBFdmVudFBsdXNUeXBlLFxuICBFdmVudFR5cGUsXG4gIE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGUsXG4gIE1lZXRpbmdBc3Npc3RFdmVudFR5cGUsXG4gIE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlLFxuICBNZWV0aW5nQXNzaXN0VHlwZSxcbiAgRXZlbnRNZWV0aW5nUGx1c1R5cGUsXG4gIFByZWZlcnJlZFRpbWVSYW5nZVR5cGUsXG4gIFJlbWluZGVyc0ZvckV2ZW50VHlwZSxcbiAgVmFsdWVzVG9SZXR1cm5Gb3JCdWZmZXJFdmVudHNUeXBlLFxuICBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIENhbGVuZGFyVHlwZSxcbiAgV29ya1RpbWVUeXBlLFxuICBUaW1lU2xvdFR5cGUsXG4gIE1vbnRoVHlwZSxcbiAgRGF5VHlwZSxcbiAgTU0sXG4gIERELFxuICBNb250aERheVR5cGUsXG4gIFRpbWUsXG4gIEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGUsXG4gIEluaXRpYWxFdmVudFBhcnRUeXBlLFxuICBJbml0aWFsRXZlbnRQYXJ0VHlwZVBsdXMsXG4gIFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlLFxuICBSZXR1cm5Cb2R5Rm9ySG9zdEZvck9wdGFwbGFubmVyUHJlcFR5cGUsXG4gIFJldHVybkJvZHlGb3JBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGUsXG4gIFJldHVybkJvZHlGb3JFeHRlcm5hbEF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZSxcbiAgUGxhbm5lclJlcXVlc3RCb2R5VHlwZSxcbiAgRnJlZW1pdW1UeXBlLFxuICBlc1Jlc3BvbnNlQm9keSxcbiAgQ2F0ZWdvcnlUeXBlLFxuICBDbGFzc2lmaWNhdGlvblJlc3BvbnNlQm9keVR5cGUsXG4gIEJ1ZmZlclRpbWVPYmplY3RUeXBlLFxuICBSZW1pbmRlclR5cGUsXG4gIENhdGVnb3J5RXZlbnRUeXBlLFxufSBmcm9tICdAc2NoZWR1bGVfZXZlbnQvX2xpYnMvdHlwZXMnOyAvLyBSZW1vdmVkIE9wZW5TZWFyY2hHZXRSZXNwb25zZUJvZHlUeXBlXG5pbXBvcnQgZ290IGZyb20gJ2dvdCc7XG5pbXBvcnQgeyB2NCBhcyB1dWlkIH0gZnJvbSAndXVpZCc7XG5pbXBvcnQgeyBnZXRJU09EYXksIHNldElTT0RheSB9IGZyb20gJ2RhdGUtZm5zJztcbmltcG9ydCBkYXlqcyBmcm9tICdkYXlqcyc7XG4vLyBpbXBvcnQgaXNvV2VlayBmcm9tICdkYXlqcy9wbHVnaW4vaXNvV2VlaydcbmltcG9ydCBkdXJhdGlvbiBmcm9tICdkYXlqcy9wbHVnaW4vZHVyYXRpb24nO1xuaW1wb3J0IGlzQmV0d2VlbiBmcm9tICdkYXlqcy9wbHVnaW4vaXNCZXR3ZWVuJztcbmltcG9ydCB0aW1lem9uZSBmcm9tICdkYXlqcy9wbHVnaW4vdGltZXpvbmUnO1xuaW1wb3J0IHV0YyBmcm9tICdkYXlqcy9wbHVnaW4vdXRjJztcbmltcG9ydCBfIGZyb20gJ2xvZGFzaCc7XG5pbXBvcnQgeyBQdXRPYmplY3RDb21tYW5kLCBTM0NsaWVudCB9IGZyb20gJ0Bhd3Mtc2RrL2NsaWVudC1zMyc7XG5pbXBvcnQgQVdTIGZyb20gJ2F3cy1zZGsnO1xuLy8gUmVtb3ZlZDogaW1wb3J0IHsgT3BlblNlYXJjaFJlc3BvbnNlQm9keVR5cGUgfSBmcm9tIFwiLi90eXBlcy9PcGVuU2VhcmNoUmVzcG9uc2VUeXBlXCJcbmltcG9ydCB7IENvbmZpZ3VyYXRpb24sIE9wZW5BSUFwaSB9IGZyb20gJ29wZW5haSc7XG5pbXBvcnQge1xuICBnZXRFdmVudEJ5SWQsXG4gIHNlYXJjaFRyYWluaW5nRXZlbnRzLFxuICBkZWxldGVUcmFpbmluZ0V2ZW50c0J5SWRzLFxuICB1cHNlcnRUcmFpbmluZ0V2ZW50cyxcbiAgVHJhaW5pbmdFdmVudFNjaGVtYSxcbiAgRXZlbnRTY2hlbWEsXG59IGZyb20gJ0BmdW5jdGlvbnMvX3V0aWxzL2xhbmNlZGJfc2VydmljZSc7IC8vIEFkZGVkIExhbmNlREIgaW1wb3J0c1xuXG4vLyBkYXlqcy5leHRlbmQoaXNvV2VlaylcbmRheWpzLmV4dGVuZChkdXJhdGlvbik7XG5kYXlqcy5leHRlbmQoaXNCZXR3ZWVuKTtcbmRheWpzLmV4dGVuZCh0aW1lem9uZSk7XG5kYXlqcy5leHRlbmQodXRjKTtcblxuY29uc3QgczNDbGllbnQgPSBuZXcgUzNDbGllbnQoe1xuICBjcmVkZW50aWFsczoge1xuICAgIGFjY2Vzc0tleUlkOiBwcm9jZXNzLmVudi5TM19BQ0NFU1NfS0VZLFxuICAgIHNlY3JldEFjY2Vzc0tleTogcHJvY2Vzcy5lbnYuUzNfU0VDUkVUX0tFWSxcbiAgfSxcbiAgZW5kcG9pbnQ6IHByb2Nlc3MuZW52LlMzX0VORFBPSU5ULFxuICBmb3JjZVBhdGhTdHlsZTogdHJ1ZSxcbn0pO1xuXG5jb25zdCBjb25maWd1cmF0aW9uID0gbmV3IENvbmZpZ3VyYXRpb24oe1xuICBhcGlLZXk6IGRlZmF1bHRPcGVuQUlBUElLZXksXG59KTtcbmNvbnN0IG9wZW5haSA9IG5ldyBPcGVuQUlBcGkoY29uZmlndXJhdGlvbik7XG5cbmV4cG9ydCBjb25zdCBnZXRFdmVudFZlY3RvckJ5SWQgPSBhc3luYyAoXG4gIGlkOiBzdHJpbmdcbik6IFByb21pc2U8bnVtYmVyW10gfCBudWxsPiA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgZXZlbnQgPSBhd2FpdCBnZXRFdmVudEJ5SWQoaWQpOyAvLyBmcm9tIGxhbmNlZGJfc2VydmljZVxuICAgIGlmIChldmVudCAmJiBldmVudC52ZWN0b3IpIHtcbiAgICAgIGNvbnNvbGUubG9nKGBWZWN0b3IgZm91bmQgZm9yIGV2ZW50IElEICR7aWR9YCk7XG4gICAgICByZXR1cm4gZXZlbnQudmVjdG9yO1xuICAgIH1cbiAgICBjb25zb2xlLmxvZyhgTm8gZXZlbnQgb3IgdmVjdG9yIGZvdW5kIGZvciBJRCAke2lkfWApO1xuICAgIHJldHVybiBudWxsO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5lcnJvcihgRXJyb3IgZmV0Y2hpbmcgZXZlbnQgdmVjdG9yIGZvciBJRCAke2lkfSBmcm9tIExhbmNlREI6YCwgZSk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjb252ZXJ0RXZlbnRUb1ZlY3RvclNwYWNlMiA9IGFzeW5jIChcbiAgZXZlbnQ6IEV2ZW50VHlwZVxuKTogUHJvbWlzZTxudW1iZXJbXT4gPT4ge1xuICB0cnkge1xuICAgIGlmICghZXZlbnQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gZXZlbnQgcHJvdmlkZWQgdG8gY29udmVydEV2ZW50VG9WZWN0b3JTcGFjZTInKTtcbiAgICB9XG4gICAgY29uc3QgeyBzdW1tYXJ5LCBub3RlcyB9ID0gZXZlbnQ7XG4gICAgY29uc3QgdGV4dCA9IGAke3N1bW1hcnl9JHtub3RlcyA/IGA6ICR7bm90ZXN9YCA6ICcnfWA7XG5cbiAgICBpZiAoIXRleHQgfHwgdGV4dC50cmltKCkgPT09ICc6Jykge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICdFbXB0eSBvciBpbnZhbGlkIHRleHQgZm9yIGVtYmVkZGluZywgcmV0dXJuaW5nIGVtcHR5IGFycmF5LidcbiAgICAgICk7XG4gICAgICByZXR1cm4gW107XG4gICAgfVxuXG4gICAgY29uc3QgZW1iZWRkaW5nUmVxdWVzdDogT3BlbkFJLkVtYmVkZGluZ3MuRW1iZWRkaW5nQ3JlYXRlUGFyYW1zID0ge1xuICAgICAgbW9kZWw6ICd0ZXh0LWVtYmVkZGluZy1hZGEtMDAyJyxcbiAgICAgIGlucHV0OiB0ZXh0LFxuICAgIH07XG4gICAgY29uc3QgcmVzID0gYXdhaXQgb3BlbmFpLmVtYmVkZGluZ3MuY3JlYXRlKGVtYmVkZGluZ1JlcXVlc3QpO1xuICAgIGNvbnN0IHZlY3RvciA9IHJlcz8uZGF0YT8uWzBdPy5lbWJlZGRpbmc7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIHZlY3RvclxuICAgICAgICA/IGBWZWN0b3IgZ2VuZXJhdGVkIHdpdGggbGVuZ3RoOiAke3ZlY3Rvci5sZW5ndGh9YFxuICAgICAgICA6ICdObyB2ZWN0b3IgZ2VuZXJhdGVkJyxcbiAgICAgICcgdmVjdG9yIGluc2lkZSBjb252ZXJ0RXZlbnRUb1ZlY3RvclNwYWNlMidcbiAgICApO1xuICAgIHJldHVybiB2ZWN0b3I7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmVycm9yKGUsICcgdW5hYmxlIHRvIGNvbnZlcnRFdmVudFRvVmVjdG9yU3BhY2UgdXNpbmcgT3BlbkFJJyk7XG4gICAgdGhyb3cgZTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHNlYXJjaFRyYWluaW5nRGF0YUJ5VmVjdG9yID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgc2VhcmNoVmVjdG9yOiBudW1iZXJbXVxuKTogUHJvbWlzZTxUcmFpbmluZ0V2ZW50U2NoZW1hIHwgbnVsbD4gPT4ge1xuICB0cnkge1xuICAgIC8vIEFzc3VtaW5nIG1pbl9zY29yZSBsb2dpYyBpcyBoYW5kbGVkIGJ5IExhbmNlREIncyBzZWFyY2ggb3Igbm90IHN0cmljdGx5IG5lZWRlZCxcbiAgICAvLyBvciB3b3VsZCByZXF1aXJlIG1vcmUgY29tcGxleCBxdWVyeSBidWlsZGluZyBpZiBpdCBpcy5cbiAgICAvLyBGb3Igbm93LCBzaW1wbGUgc2VhcmNoIGFuZCByZXR1cm4gdG9wIGhpdC5cbiAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgc2VhcmNoVHJhaW5pbmdFdmVudHMoXG4gICAgICBzZWFyY2hWZWN0b3IsXG4gICAgICAxLCAvLyBXZSBuZWVkIG9ubHkgdGhlIHRvcCBtYXRjaFxuICAgICAgYHVzZXJJZCA9ICcke3VzZXJJZC5yZXBsYWNlKC8nL2csIFwiJydcIil9J2BcbiAgICApO1xuICAgIGlmIChyZXN1bHRzICYmIHJlc3VsdHMubGVuZ3RoID4gMCkge1xuICAgICAgLy8gY29uc29sZS5sb2cocmVzdWx0c1swXSwgJyBzZWFyY2ggZGF0YSBmcm9tIExhbmNlREIgdHJhaW5pbmdfZGF0YScpO1xuICAgICAgcmV0dXJuIHJlc3VsdHNbMF07XG4gICAgfVxuICAgIHJldHVybiBudWxsO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3Igc2VhcmNoaW5nIHRyYWluaW5nIGRhdGEgaW4gTGFuY2VEQjonLCBlKTtcbiAgICB0aHJvdyBlOyAvLyBPciByZXR1cm4gbnVsbCBiYXNlZCBvbiBkZXNpcmVkIGVycm9yIGhhbmRsaW5nXG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBkZWxldGVUcmFpbmluZ0RhdGFCeUlkID0gYXN5bmMgKGlkOiBzdHJpbmcpOiBQcm9taXNlPHZvaWQ+ID0+IHtcbiAgdHJ5IHtcbiAgICBhd2FpdCBkZWxldGVUcmFpbmluZ0V2ZW50c0J5SWRzKFtpZF0pO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYFN1Y2Nlc3NmdWxseSBkZWxldGVkIHRyYWluaW5nIGRhdGEgZm9yIElEOiAke2lkfSBmcm9tIExhbmNlREIuYFxuICAgICk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmVycm9yKGBFcnJvciBkZWxldGluZyB0cmFpbmluZyBkYXRhIGZvciBJRCAke2lkfSBmcm9tIExhbmNlREI6YCwgZSk7XG4gICAgdGhyb3cgZTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGFkZFRyYWluaW5nRGF0YSA9IGFzeW5jIChcbiAgdHJhaW5pbmdFbnRyeTogVHJhaW5pbmdFdmVudFNjaGVtYVxuKTogUHJvbWlzZTx2b2lkPiA9PiB7XG4gIHRyeSB7XG4gICAgYXdhaXQgdXBzZXJ0VHJhaW5pbmdFdmVudHMoW3RyYWluaW5nRW50cnldKTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBTdWNjZXNzZnVsbHkgYWRkZWQvdXBkYXRlZCB0cmFpbmluZyBkYXRhIGZvciBJRDogJHt0cmFpbmluZ0VudHJ5LmlkfSBpbiBMYW5jZURCLmBcbiAgICApO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgIGBFcnJvciBhZGRpbmcvdXBkYXRpbmcgdHJhaW5pbmcgZGF0YSBmb3IgSUQgJHt0cmFpbmluZ0VudHJ5LmlkfSBpbiBMYW5jZURCOmAsXG4gICAgICBlXG4gICAgKTtcbiAgICB0aHJvdyBlO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3RvciA9IGFzeW5jICh0aXRsZTogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgZW1iZWRkaW5nUmVxdWVzdDogT3BlbkFJLkVtYmVkZGluZ3MuRW1iZWRkaW5nQ3JlYXRlUGFyYW1zID0ge1xuICAgICAgbW9kZWw6ICd0ZXh0LWVtYmVkZGluZy1hZGEtMDAyJyxcbiAgICAgIGlucHV0OiB0aXRsZSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzID0gYXdhaXQgb3BlbmFpLmVtYmVkZGluZ3MuY3JlYXRlKGVtYmVkZGluZ1JlcXVlc3QpO1xuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgaW5zaWRlIGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3JzJyk7XG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uWzBdPy5lbWJlZGRpbmc7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBjb252ZXJ0IGV2ZW50IHRpdGxlIHRvIG9wZW5haXZlY3RvcnMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlc0dpdmVuTWVldGluZ0lkID0gYXN5bmMgKFxuICBtZWV0aW5nSWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdMaXN0TWVldGluZ0Fzc2lzdFByZWZlcmVyZWRUaW1lUmFuZ2VzQnlNZWV0aW5nSWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgTGlzdE1lZXRpbmdBc3Npc3RQcmVmZXJlcmVkVGltZVJhbmdlc0J5TWVldGluZ0lkKCRtZWV0aW5nSWQ6IHV1aWQhKSB7XG4gICAgICAgICAgICAgICAgTWVldGluZ19Bc3Npc3RfUHJlZmVycmVkX1RpbWVfUmFuZ2Uod2hlcmU6IHttZWV0aW5nSWQ6IHtfZXE6ICRtZWV0aW5nSWR9fSkge1xuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUlkXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGRheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgICBlbmRUaW1lXG4gICAgICAgICAgICAgICAgICAgIGhvc3RJZFxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgc3RhcnRUaW1lXG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICB9XG5cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIG1lZXRpbmdJZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7XG4gICAgICBkYXRhOiB7XG4gICAgICAgIE1lZXRpbmdfQXNzaXN0X1ByZWZlcnJlZF9UaW1lX1JhbmdlOiBNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlVHlwZVtdO1xuICAgICAgfTtcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBsaXN0TWVldGluZ0Fzc2lzdEF0dGVuZGVlcyAnKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/Lk1lZXRpbmdfQXNzaXN0X1ByZWZlcnJlZF9UaW1lX1JhbmdlO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1YW5ibGUgdG8gbGlzdCBtZWV0aW5nIGFzc2lzdCBwcmVmZXJyZWQgdGltZSByYW5nZXMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzR2l2ZW5NZWV0aW5nSWQgPSBhc3luYyAoXG4gIG1lZXRpbmdJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0xpc3RNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzQnlNZWV0aW5nSWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgTGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZXNCeU1lZXRpbmdJZCgkbWVldGluZ0lkOiB1dWlkISkge1xuICAgICAgICAgICAgICAgIE1lZXRpbmdfQXNzaXN0X0F0dGVuZGVlKHdoZXJlOiB7bWVldGluZ0lkOiB7X2VxOiAkbWVldGluZ0lkfX0pIHtcbiAgICAgICAgICAgICAgICAgICAgY29udGFjdElkXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGVtYWlsc1xuICAgICAgICAgICAgICAgICAgICBleHRlcm5hbEF0dGVuZGVlXG4gICAgICAgICAgICAgICAgICAgIGhvc3RJZFxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBpbUFkZHJlc3Nlc1xuICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgICAgICAgICBwaG9uZU51bWJlcnNcbiAgICAgICAgICAgICAgICAgICAgcHJpbWFyeUVtYWlsXG4gICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG5cbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBtZWV0aW5nSWQsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczoge1xuICAgICAgZGF0YTogeyBNZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZTogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdIH07XG4gICAgfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gbGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZXMgJyk7XG5cbiAgICByZXR1cm4gcmVzPy5kYXRhPy5NZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGxpc3QgbWVldGluZyBhc3Npc3QgYXR0ZW5kZWVzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRNZWV0aW5nQXNzaXN0QXR0ZW5kZWUgPSBhc3luYyAoaWQ6IHN0cmluZykgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnR2V0TWVldGluZ0Fzc2lzdEF0dGVuZGVlQnlJZCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBxdWVyeSBHZXRNZWV0aW5nQXNzaXN0QXR0ZW5kZWVCeUlkKCRpZDogU3RyaW5nISkge1xuICAgICAgICAgICAgICAgIE1lZXRpbmdfQXNzaXN0X0F0dGVuZGVlX2J5X3BrKGlkOiAkaWQpIHtcbiAgICAgICAgICAgICAgICAgICAgY29udGFjdElkXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGVtYWlsc1xuICAgICAgICAgICAgICAgICAgICBob3N0SWRcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgaW1BZGRyZXNzZXNcbiAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgICAgICAgICAgcGhvbmVOdW1iZXJzXG4gICAgICAgICAgICAgICAgICAgIHByaW1hcnlFbWFpbFxuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWVcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG5cbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBpZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7XG4gICAgICBkYXRhOiB7IE1lZXRpbmdfQXNzaXN0X0F0dGVuZGVlX2J5X3BrOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlIH07XG4gICAgfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gZ2V0TWVldGluZ0Fzc2lzdEF0dGVuZGVlJyk7XG5cbiAgICByZXR1cm4gcmVzPy5kYXRhPy5NZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZV9ieV9waztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBtZWV0aW5nIGFzc2lzdCBhdHRlbmRlZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0TWVldGluZ0Fzc2lzdCA9IGFzeW5jIChpZDogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdHZXRNZWV0aW5nQXNzaXN0QnlJZCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBxdWVyeSBHZXRNZWV0aW5nQXNzaXN0QnlJZCgkaWQ6IHV1aWQhKSB7XG4gICAgICAgICAgICAgICAgTWVldGluZ19Bc3Npc3RfYnlfcGsoaWQ6ICRpZCkge1xuICAgICAgICAgICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlQ2FuTW9kaWZ5XG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlQ291bnRcbiAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVSZXNwb25kZWRDb3VudFxuICAgICAgICAgICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgYnVmZmVyVGltZVxuICAgICAgICAgICAgICAgICAgICBjYWxlbmRhcklkXG4gICAgICAgICAgICAgICAgICAgIGNhbmNlbElmQW55UmVmdXNlXG4gICAgICAgICAgICAgICAgICAgIGNhbmNlbGxlZFxuICAgICAgICAgICAgICAgICAgICBjb2xvcklkXG4gICAgICAgICAgICAgICAgICAgIGNvbmZlcmVuY2VBcHBcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb25cbiAgICAgICAgICAgICAgICAgICAgZW5hYmxlQXR0ZW5kZWVQcmVmZXJlbmNlc1xuICAgICAgICAgICAgICAgICAgICBlbmFibGVDb25mZXJlbmNlXG4gICAgICAgICAgICAgICAgICAgIGVuYWJsZUhvc3RQcmVmZXJlbmNlc1xuICAgICAgICAgICAgICAgICAgICBlbmREYXRlXG4gICAgICAgICAgICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgZXhwaXJlRGF0ZVxuICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uXG4gICAgICAgICAgICAgICAgICAgIG1pblRocmVzaG9sZENvdW50XG4gICAgICAgICAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICAgICAgICAgIHJlbWluZGVyc1xuICAgICAgICAgICAgICAgICAgICBzZW5kVXBkYXRlc1xuICAgICAgICAgICAgICAgICAgICBzdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgc3VtbWFyeVxuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIHZpc2liaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgd2luZG93RW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICB3aW5kb3dTdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgYWxsb3dBdHRlbmRlZVVwZGF0ZVByZWZlcmVuY2VzXG4gICAgICAgICAgICAgICAgICAgIGd1YXJhbnRlZUF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBNZWV0aW5nX0Fzc2lzdF9ieV9wazogTWVldGluZ0Fzc2lzdFR5cGUgfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBnZXRNZWV0aW5nQXNzaXN0Jyk7XG5cbiAgICByZXR1cm4gcmVzPy5kYXRhPy5NZWV0aW5nX0Fzc2lzdF9ieV9waztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBtZWV0aW5nIGFzc2lzdCBmcm9tIGlkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBsaXN0TWVldGluZ0Fzc2lzdEV2ZW50c0ZvckF0dGVuZGVlR2l2ZW5EYXRlcyA9IGFzeW5jIChcbiAgYXR0ZW5kZWVJZDogc3RyaW5nLFxuICBob3N0U3RhcnREYXRlOiBzdHJpbmcsXG4gIGhvc3RFbmREYXRlOiBzdHJpbmcsXG4gIHVzZXJUaW1lem9uZTogc3RyaW5nLFxuICBob3N0VGltZXpvbmU6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdMaXN0TWVldGluZ0Fzc2lzdEV2ZW50c0ZvckF0dGVuZGVlR2l2ZW5EYXRlcyc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBxdWVyeSBMaXN0TWVldGluZ0Fzc2lzdEV2ZW50c0ZvckF0dGVuZGVlR2l2ZW5EYXRlcygkYXR0ZW5kZWVJZDogU3RyaW5nISwgJHN0YXJ0RGF0ZTogdGltZXN0YW1wISwgJGVuZERhdGU6IHRpbWVzdGFtcCEpIHtcbiAgICAgICAgICAgICAgICBNZWV0aW5nX0Fzc2lzdF9FdmVudCh3aGVyZToge2F0dGVuZGVlSWQ6IHtfZXE6ICRhdHRlbmRlZUlkfSwgc3RhcnREYXRlOiB7X2d0ZTogJHN0YXJ0RGF0ZX0sIGVuZERhdGU6IHtfbHRlOiAkZW5kRGF0ZX19KSB7XG4gICAgICAgICAgICAgICAgICAgIGFsbERheVxuICAgICAgICAgICAgICAgICAgICBhdHRhY2htZW50c1xuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUlkXG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlc09taXR0ZWRcbiAgICAgICAgICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBjcmVhdG9yXG4gICAgICAgICAgICAgICAgICAgIGVuZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZW5kVGltZVVuc3BlY2lmaWVkXG4gICAgICAgICAgICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgZXZlbnRUeXBlXG4gICAgICAgICAgICAgICAgICAgIGV4dGVuZGVkUHJvcGVydGllc1xuICAgICAgICAgICAgICAgICAgICBleHRlcm5hbFVzZXJcbiAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbk1vZGlmeVxuICAgICAgICAgICAgICAgICAgICBoYW5nb3V0TGlua1xuICAgICAgICAgICAgICAgICAgICBodG1sTGlua1xuICAgICAgICAgICAgICAgICAgICBpQ2FsVUlEXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGxpbmtzXG4gICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uXG4gICAgICAgICAgICAgICAgICAgIGxvY2tlZFxuICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgbm90ZXNcbiAgICAgICAgICAgICAgICAgICAgb3JnYW5pemVyXG4gICAgICAgICAgICAgICAgICAgIG9yaWdpbmFsVGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgcHJpdmF0ZUNvcHlcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyZW5jZVxuICAgICAgICAgICAgICAgICAgICByZWN1cnJlbmNlUnVsZVxuICAgICAgICAgICAgICAgICAgICByZWN1cnJpbmdFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIHNvdXJjZVxuICAgICAgICAgICAgICAgICAgICBzdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgc3VtbWFyeVxuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgICAgICAgICAgICAgdmlzaWJpbGl0eVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgdHJ1ZVxuICAgICk7XG4gICAgY29uc3QgZW5kRGF0ZUluSG9zdFRpbWV6b25lID0gZGF5anMoaG9zdEVuZERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIHRydWVcbiAgICApO1xuICAgIGNvbnN0IHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lID0gZGF5anMoc3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLmZvcm1hdCgpXG4gICAgICAuc2xpY2UoMCwgMTkpO1xuICAgIGNvbnN0IGVuZERhdGVJblVzZXJUaW1lem9uZSA9IGRheWpzKGVuZERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuZm9ybWF0KClcbiAgICAgIC5zbGljZSgwLCAxOSk7XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBNZWV0aW5nX0Fzc2lzdF9FdmVudDogTWVldGluZ0Fzc2lzdEV2ZW50VHlwZVtdIH0gfSA9XG4gICAgICBhd2FpdCBnb3RcbiAgICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICAgIH0sXG4gICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICAgIGF0dGVuZGVlSWQsXG4gICAgICAgICAgICAgIHN0YXJ0RGF0ZTogc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUsXG4gICAgICAgICAgICAgIGVuZERhdGU6IGVuZERhdGVJblVzZXJUaW1lem9uZSxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBsaXN0TWVldGluZ0Fzc2lzdEV2ZW50c0ZvckF0dGVuZGVlR2l2ZW5EYXRlcycpO1xuICAgIHJldHVybiByZXM/LmRhdGE/Lk1lZXRpbmdfQXNzaXN0X0V2ZW50O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBlLFxuICAgICAgJyB1bmFibGUgdG8gbGlzdCBtZWV0aW5nIGFzc2lzdCBldmVudHMgZm9yIGF0dGVuZGVlIGdpdmVuIGRhdGVzJ1xuICAgICk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBsaXN0RXZlbnRzRm9yRGF0ZSA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHN0YXJ0RGF0ZTogc3RyaW5nLFxuICBlbmREYXRlOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnbGlzdEV2ZW50c0ZvckRhdGUnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICBxdWVyeSBsaXN0RXZlbnRzRm9yRGF0ZSgkdXNlcklkOiB1dWlkISwgJHN0YXJ0RGF0ZTogdGltZXN0YW1wISwgJGVuZERhdGU6IHRpbWVzdGFtcCEpIHtcbiAgICAgICAgICBFdmVudCh3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH0sIGVuZERhdGU6IHtfZ3RlOiAkc3RhcnREYXRlfSwgc3RhcnREYXRlOiB7X2x0ZTogJGVuZERhdGV9LCBkZWxldGVkOiB7X2VxOiBmYWxzZX19KSB7XG4gICAgICAgICAgICBhbGxEYXlcbiAgICAgICAgICAgIGFueW9uZUNhbkFkZFNlbGZcbiAgICAgICAgICAgIGF0dGFjaG1lbnRzXG4gICAgICAgICAgICBhdHRlbmRlZXNPbWl0dGVkXG4gICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgIGNvbG9ySWRcbiAgICAgICAgICAgIGNvbmZlcmVuY2VJZFxuICAgICAgICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgY29weUNhdGVnb3JpZXNcbiAgICAgICAgICAgIGNvcHlEdXJhdGlvblxuICAgICAgICAgICAgY29weUlzQnJlYWtcbiAgICAgICAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgY29weUlzTWVldGluZ1xuICAgICAgICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgICAgICAgIGNvcHlQcmlvcml0eUxldmVsXG4gICAgICAgICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICAgICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICAgICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICBjcmVhdG9yXG4gICAgICAgICAgICBkYWlseVRhc2tMaXN0XG4gICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICBkdXJhdGlvblxuICAgICAgICAgICAgZW5kRGF0ZVxuICAgICAgICAgICAgZW5kVGltZVVuc3BlY2lmaWVkXG4gICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICBldmVudFR5cGVcbiAgICAgICAgICAgIGV4dGVuZGVkUHJvcGVydGllc1xuICAgICAgICAgICAgZm9sbG93VXBFdmVudElkXG4gICAgICAgICAgICBmb3JFdmVudElkXG4gICAgICAgICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICAgICAgZ3Vlc3RzQ2FuTW9kaWZ5XG4gICAgICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0c1xuICAgICAgICAgICAgaGFuZ291dExpbmtcbiAgICAgICAgICAgIGhhcmREZWFkbGluZVxuICAgICAgICAgICAgaHRtbExpbmtcbiAgICAgICAgICAgIGlDYWxVSURcbiAgICAgICAgICAgIGlkXG4gICAgICAgICAgICBpc0JyZWFrXG4gICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICBpc0ZvbGxvd1VwXG4gICAgICAgICAgICBpc01lZXRpbmdcbiAgICAgICAgICAgIGlzTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgIGlzUG9zdEV2ZW50XG4gICAgICAgICAgICBpc1ByZUV2ZW50XG4gICAgICAgICAgICBsaW5rc1xuICAgICAgICAgICAgbG9jYXRpb25cbiAgICAgICAgICAgIGxvY2tlZFxuICAgICAgICAgICAgbWF4QXR0ZW5kZWVzXG4gICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgIG1ldGhvZFxuICAgICAgICAgICAgbW9kaWZpYWJsZVxuICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3REYXlPZldlZWtcbiAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZVxuICAgICAgICAgICAgbm90ZXNcbiAgICAgICAgICAgIG9yZ2FuaXplclxuICAgICAgICAgICAgb3JpZ2luYWxBbGxEYXlcbiAgICAgICAgICAgIG9yaWdpbmFsU3RhcnREYXRlXG4gICAgICAgICAgICBvcmlnaW5hbFRpbWV6b25lXG4gICAgICAgICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RTY29yZVxuICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RUaW1lXG4gICAgICAgICAgICBwb3N0RXZlbnRJZFxuICAgICAgICAgICAgcHJlRXZlbnRJZFxuICAgICAgICAgICAgcHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2VcbiAgICAgICAgICAgIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlXG4gICAgICAgICAgICBwcmVmZXJyZWRUaW1lXG4gICAgICAgICAgICBwcmlvcml0eVxuICAgICAgICAgICAgcHJpdmF0ZUNvcHlcbiAgICAgICAgICAgIHJlY3VycmVuY2VcbiAgICAgICAgICAgIHJlY3VycmVuY2VSdWxlXG4gICAgICAgICAgICByZWN1cnJpbmdFdmVudElkXG4gICAgICAgICAgICBzZW5kVXBkYXRlc1xuICAgICAgICAgICAgc29mdERlYWRsaW5lXG4gICAgICAgICAgICBzb3VyY2VcbiAgICAgICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICAgICAgc3RhdHVzXG4gICAgICAgICAgICBzdW1tYXJ5XG4gICAgICAgICAgICB0YXNrSWRcbiAgICAgICAgICAgIHRhc2tUeXBlXG4gICAgICAgICAgICB0aW1lQmxvY2tpbmdcbiAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICB0aXRsZVxuICAgICAgICAgICAgdHJhbnNwYXJlbmN5XG4gICAgICAgICAgICB1bmxpbmtcbiAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgdXNlRGVmYXVsdEFsYXJtc1xuICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZENhdGVnb3JpZXNcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZER1cmF0aW9uXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRJc0JyZWFrXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNNZWV0aW5nXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRQcmlvcml0eUxldmVsXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnNcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2VcbiAgICAgICAgICAgIHZpc2liaWxpdHlcbiAgICAgICAgICAgIHdlZWtseVRhc2tMaXN0XG4gICAgICAgICAgICBieVdlZWtEYXlcbiAgICAgICAgICAgIGxvY2FsU3luY2VkXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRDb2xvclxuICAgICAgICAgICAgY29weUNvbG9yXG4gICAgICAgICAgICBjb3B5RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgdXNlck1vZGlmaWVkRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgdXNlck1vZGlmaWVkTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgICAgICAgIGA7XG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgRXZlbnQ6IEV2ZW50VHlwZVtdIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBzdGFydERhdGU6IGRheWpzKHN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICAgICAgZW5kRGF0ZTogZGF5anMoZW5kRGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoKSxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gbGlzdEV2ZW50c2ZvclVzZXInKTtcbiAgICByZXR1cm4gcmVzPy5kYXRhPy5FdmVudDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGxpc3QgZXZlbnRzIGZvciBkYXRlJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBsaXN0RXZlbnRzRm9yVXNlckdpdmVuRGF0ZXMgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBob3N0U3RhcnREYXRlOiBzdHJpbmcsXG4gIGhvc3RFbmREYXRlOiBzdHJpbmcsXG4gIHVzZXJUaW1lem9uZTogc3RyaW5nLFxuICBob3N0VGltZXpvbmU6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdsaXN0RXZlbnRzRm9yVXNlcic7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBxdWVyeSBsaXN0RXZlbnRzRm9yVXNlcigkdXNlcklkOiB1dWlkISwgJHN0YXJ0RGF0ZTogdGltZXN0YW1wISwgJGVuZERhdGU6IHRpbWVzdGFtcCEpIHtcbiAgICAgICAgICAgICAgICBFdmVudCh3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH0sIGVuZERhdGU6IHtfZ3RlOiAkc3RhcnREYXRlfSwgc3RhcnREYXRlOiB7X2x0ZTogJGVuZERhdGV9LCBkZWxldGVkOiB7X25lcTogdHJ1ZX0sIGFsbERheToge19uZXE6IHRydWV9fSkge1xuICAgICAgICAgICAgICAgICAgICBhbGxEYXlcbiAgICAgICAgICAgICAgICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgICAgICAgICAgICAgICBhdHRhY2htZW50c1xuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZXNPbWl0dGVkXG4gICAgICAgICAgICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICBjYWxlbmRhcklkXG4gICAgICAgICAgICAgICAgICAgIGNvbG9ySWRcbiAgICAgICAgICAgICAgICAgICAgY29uZmVyZW5jZUlkXG4gICAgICAgICAgICAgICAgICAgIGNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgY29weUNhdGVnb3JpZXNcbiAgICAgICAgICAgICAgICAgICAgY29weUR1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgIGNvcHlJc0JyZWFrXG4gICAgICAgICAgICAgICAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIGNvcHlNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIGNvcHlQcmlvcml0eUxldmVsXG4gICAgICAgICAgICAgICAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgY29weVRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRvclxuICAgICAgICAgICAgICAgICAgICBkYWlseVRhc2tMaXN0XG4gICAgICAgICAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb25cbiAgICAgICAgICAgICAgICAgICAgZW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICBlbmRUaW1lVW5zcGVjaWZpZWRcbiAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBldmVudFR5cGVcbiAgICAgICAgICAgICAgICAgICAgZXh0ZW5kZWRQcm9wZXJ0aWVzXG4gICAgICAgICAgICAgICAgICAgIGZvbGxvd1VwRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBmb3JFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuTW9kaWZ5XG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICAgICAgICAgICAgICAgIGhhbmdvdXRMaW5rXG4gICAgICAgICAgICAgICAgICAgIGhhcmREZWFkbGluZVxuICAgICAgICAgICAgICAgICAgICBodG1sTGlua1xuICAgICAgICAgICAgICAgICAgICBpQ2FsVUlEXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGlzQnJlYWtcbiAgICAgICAgICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIGlzRm9sbG93VXBcbiAgICAgICAgICAgICAgICAgICAgaXNNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIGlzTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgaXNQb3N0RXZlbnRcbiAgICAgICAgICAgICAgICAgICAgaXNQcmVFdmVudFxuICAgICAgICAgICAgICAgICAgICBsaW5rc1xuICAgICAgICAgICAgICAgICAgICBsb2NhdGlvblxuICAgICAgICAgICAgICAgICAgICBsb2NrZWRcbiAgICAgICAgICAgICAgICAgICAgbWF4QXR0ZW5kZWVzXG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgICAgICAgICAgICBtZXRob2RcbiAgICAgICAgICAgICAgICAgICAgbW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZVxuICAgICAgICAgICAgICAgICAgICBub3Rlc1xuICAgICAgICAgICAgICAgICAgICBvcmdhbml6ZXJcbiAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxBbGxEYXlcbiAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxTdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxUaW1lem9uZVxuICAgICAgICAgICAgICAgICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgICBwb3NpdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0VGltZVxuICAgICAgICAgICAgICAgICAgICBwb3N0RXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBwcmVFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZERheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2VcbiAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkVGltZVxuICAgICAgICAgICAgICAgICAgICBwcmlvcml0eVxuICAgICAgICAgICAgICAgICAgICBwcml2YXRlQ29weVxuICAgICAgICAgICAgICAgICAgICByZWN1cnJlbmNlXG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VSdWxlXG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmluZ0V2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgc2VuZFVwZGF0ZXNcbiAgICAgICAgICAgICAgICAgICAgc29mdERlYWRsaW5lXG4gICAgICAgICAgICAgICAgICAgIHNvdXJjZVxuICAgICAgICAgICAgICAgICAgICBzdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgc3RhdHVzXG4gICAgICAgICAgICAgICAgICAgIHN1bW1hcnlcbiAgICAgICAgICAgICAgICAgICAgdGFza0lkXG4gICAgICAgICAgICAgICAgICAgIHRhc2tUeXBlXG4gICAgICAgICAgICAgICAgICAgIHRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB0aXRsZVxuICAgICAgICAgICAgICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgICAgICAgICAgICAgdW5saW5rXG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkQ2F0ZWdvcmllc1xuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWREdXJhdGlvblxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRJc0JyZWFrXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgICB2aXNpYmlsaXR5XG4gICAgICAgICAgICAgICAgICAgIHdlZWtseVRhc2tMaXN0XG4gICAgICAgICAgICAgICAgICAgIGJ5V2Vla0RheVxuICAgICAgICAgICAgICAgICAgICBsb2NhbFN5bmNlZFxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRDb2xvclxuICAgICAgICAgICAgICAgICAgICBjb3B5Q29sb3JcbiAgICAgICAgICAgICAgICAgICAgY29weUV4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcbiAgICAvLyBnZXQgZXZlbnRzXG4gICAgLy8gbG9jYWwgZGF0ZVxuICAgIGNvbnN0IHN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgdHJ1ZVxuICAgICk7XG4gICAgY29uc3QgZW5kRGF0ZUluSG9zdFRpbWV6b25lID0gZGF5anMoaG9zdEVuZERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIHRydWVcbiAgICApO1xuICAgIGNvbnN0IHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lID0gZGF5anMoc3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLmZvcm1hdCgpXG4gICAgICAuc2xpY2UoMCwgMTkpO1xuICAgIGNvbnN0IGVuZERhdGVJblVzZXJUaW1lem9uZSA9IGRheWpzKGVuZERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuZm9ybWF0KClcbiAgICAgIC5zbGljZSgwLCAxOSk7XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBFdmVudDogRXZlbnRUeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgIHN0YXJ0RGF0ZTogc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUsXG4gICAgICAgICAgICBlbmREYXRlOiBlbmREYXRlSW5Vc2VyVGltZXpvbmUsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGxpc3RFdmVudHNmb3JVc2VyJyk7XG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uRXZlbnQ7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIGxpc3RFdmVudHNGb3JVc2VyJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzTWVldGluZ0Fzc2lzdEZvck9wdGFwbGFubmVyID0gYXN5bmMgKCkgPT4ge1xuICB0cnkge1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcHJvY2VzcyBtZWV0aW5nIGFzc2lzdCBmb3Igb3B0YXBsYW5uZXInKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlTmV3TWVldGluZ0V2ZW50Rm9yQXR0ZW5kZWUgPSAoXG4gIGF0dGVuZGVlOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlLFxuICBtZWV0aW5nQXNzaXN0OiBNZWV0aW5nQXNzaXN0VHlwZSxcbiAgd2luZG93U3RhcnREYXRlOiBzdHJpbmcsXG4gIHdpbmRvd0VuZERhdGU6IHN0cmluZyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ/OiBzdHJpbmcsXG4gIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPzogTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVcbik6IEV2ZW50VHlwZSA9PiB7XG4gIGxldCBzdGFydERhdGUgPSBkYXlqcyh3aW5kb3dTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLmZvcm1hdCgpO1xuICBjb25zdCBlbmREYXRlID0gZGF5anMod2luZG93RW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAuZm9ybWF0KCk7XG5cbiAgaWYgKHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPy5kYXlPZldlZWsgPiAwKSB7XG4gICAgY29uc3QgZGF0ZU9iamVjdCA9IGRheWpzKHN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLnRvRGF0ZSgpO1xuICAgIGNvbnN0IGRhdGVPYmplY3RXaXRoU2V0SVNPRGF5UG9zc2libGUgPSBzZXRJU09EYXkoXG4gICAgICBkYXRlT2JqZWN0LFxuICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U/LmRheU9mV2Vla1xuICAgICk7XG4gICAgY29uc3Qgb3JpZ2luYWxEYXRlT2JqZWN0V2l0aFNldElTT0RheSA9IGRhdGVPYmplY3RXaXRoU2V0SVNPRGF5UG9zc2libGU7XG4gICAgbGV0IGRhdGVPYmplY3RXaXRoU2V0SVNPRGF5ID0gb3JpZ2luYWxEYXRlT2JqZWN0V2l0aFNldElTT0RheTtcblxuICAgIC8vIHRyeSBhZGRcbiAgICBpZiAoIWRheWpzKGRhdGVPYmplY3RXaXRoU2V0SVNPRGF5KS5pc0JldHdlZW4oc3RhcnREYXRlLCBlbmREYXRlKSkge1xuICAgICAgZGF0ZU9iamVjdFdpdGhTZXRJU09EYXkgPSBkYXlqcyhvcmlnaW5hbERhdGVPYmplY3RXaXRoU2V0SVNPRGF5KVxuICAgICAgICAuYWRkKDEsICd3ZWVrJylcbiAgICAgICAgLnRvRGF0ZSgpO1xuICAgIH1cblxuICAgIC8vIHRyeSBzdWJ0cmFjdFxuICAgIGlmICghZGF5anMoZGF0ZU9iamVjdFdpdGhTZXRJU09EYXkpLmlzQmV0d2VlbihzdGFydERhdGUsIGVuZERhdGUpKSB7XG4gICAgICBkYXRlT2JqZWN0V2l0aFNldElTT0RheSA9IGRheWpzKG9yaWdpbmFsRGF0ZU9iamVjdFdpdGhTZXRJU09EYXkpXG4gICAgICAgIC5zdWJ0cmFjdCgxLCAnd2VlaycpXG4gICAgICAgIC50b0RhdGUoKTtcbiAgICB9XG5cbiAgICBzdGFydERhdGUgPSBkYXlqcyhkYXRlT2JqZWN0V2l0aFNldElTT0RheSkudHooaG9zdFRpbWV6b25lKS5mb3JtYXQoKTtcbiAgfVxuXG4gIGlmIChwcmVmZXJyZWRTdGFydFRpbWVSYW5nZT8uc3RhcnRUaW1lKSB7XG4gICAgY29uc3Qgc3RhcnRUaW1lID0gcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U/LnN0YXJ0VGltZTtcbiAgICBjb25zdCBob3VyID0gcGFyc2VJbnQoc3RhcnRUaW1lLnNsaWNlKDAsIDIpLCAxMCk7XG4gICAgY29uc3QgbWludXRlID0gcGFyc2VJbnQoc3RhcnRUaW1lLnNsaWNlKDMpLCAxMCk7XG5cbiAgICBzdGFydERhdGUgPSBkYXlqcyhzdGFydERhdGUuc2xpY2UoMCwgMTApKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5ob3VyKGhvdXIpXG4gICAgICAubWludXRlKG1pbnV0ZSlcbiAgICAgIC5mb3JtYXQoKTtcbiAgfVxuXG4gIGNvbnN0IGV2ZW50SWQgPSB1dWlkKCk7XG4gIGNvbnN0IG5ld0V2ZW50OiBFdmVudFR5cGUgPSB7XG4gICAgaWQ6IGAke2V2ZW50SWR9IyR7Y2FsZW5kYXJJZCA/PyBtZWV0aW5nQXNzaXN0LmNhbGVuZGFySWR9YCxcbiAgICBtZXRob2Q6ICdjcmVhdGUnLFxuICAgIHRpdGxlOiBtZWV0aW5nQXNzaXN0LnN1bW1hcnksXG4gICAgc3RhcnREYXRlLFxuICAgIGVuZERhdGU6IGRheWpzKHN0YXJ0RGF0ZSkuYWRkKG1lZXRpbmdBc3Npc3QuZHVyYXRpb24sICdtJykuZm9ybWF0KCksXG4gICAgYWxsRGF5OiBmYWxzZSxcbiAgICBub3RlczogbWVldGluZ0Fzc2lzdC5ub3RlcyxcbiAgICB0aW1lem9uZTogaG9zdFRpbWV6b25lLFxuICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIHByaW9yaXR5OiBtZWV0aW5nQXNzaXN0LnByaW9yaXR5LFxuICAgIGlzRm9sbG93VXA6IGZhbHNlLFxuICAgIGlzUHJlRXZlbnQ6IGZhbHNlLFxuICAgIGlzUG9zdEV2ZW50OiBmYWxzZSxcbiAgICBtb2RpZmlhYmxlOiB0cnVlLFxuICAgIHNlbmRVcGRhdGVzOiBtZWV0aW5nQXNzaXN0Py5zZW5kVXBkYXRlcyxcbiAgICBzdGF0dXM6ICdjb25maXJtZWQnLFxuICAgIHN1bW1hcnk6IG1lZXRpbmdBc3Npc3Quc3VtbWFyeSxcbiAgICB0cmFuc3BhcmVuY3k6IG1lZXRpbmdBc3Npc3Q/LnRyYW5zcGFyZW5jeSxcbiAgICB2aXNpYmlsaXR5OiBtZWV0aW5nQXNzaXN0Py52aXNpYmlsaXR5LFxuICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICBjYWxlbmRhcklkOiBjYWxlbmRhcklkID8/IG1lZXRpbmdBc3Npc3QuY2FsZW5kYXJJZCxcbiAgICB1c2VEZWZhdWx0QWxhcm1zOiBtZWV0aW5nQXNzaXN0LnVzZURlZmF1bHRBbGFybXMsXG4gICAgdGltZUJsb2NraW5nOiBtZWV0aW5nQXNzaXN0LmJ1ZmZlclRpbWUsXG4gICAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nOiBtZWV0aW5nQXNzaXN0Py5idWZmZXJUaW1lID8gdHJ1ZSA6IGZhbHNlLFxuICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlOiBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZT8uaWQgPyB0cnVlIDogZmFsc2UsXG4gICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzOiBtZWV0aW5nQXNzaXN0Py5yZW1pbmRlcnM/LlswXSA+IC0xID8gdHJ1ZSA6IGZhbHNlLFxuICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWw6IHRydWUsXG4gICAgdXNlck1vZGlmaWVkTW9kaWZpYWJsZTogdHJ1ZSxcbiAgICBkdXJhdGlvbjogbWVldGluZ0Fzc2lzdD8uZHVyYXRpb24sXG4gICAgdXNlck1vZGlmaWVkRHVyYXRpb246IHRydWUsXG4gICAgdXNlcklkOiBhdHRlbmRlZT8udXNlcklkLFxuICAgIGFueW9uZUNhbkFkZFNlbGY6IGZhbHNlLFxuICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyczogbWVldGluZ0Fzc2lzdD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOiBtZWV0aW5nQXNzaXN0Py5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICBvcmlnaW5hbFN0YXJ0RGF0ZTogdW5kZWZpbmVkLFxuICAgIG9yaWdpbmFsQWxsRGF5OiBmYWxzZSxcbiAgICBtZWV0aW5nSWQ6IG1lZXRpbmdBc3Npc3QuaWQsXG4gICAgZXZlbnRJZCxcbiAgfTtcblxuICByZXR1cm4gbmV3RXZlbnQ7XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVOZXdNZWV0aW5nRXZlbnRGb3JIb3N0ID0gKFxuICBob3N0QXR0ZW5kZWU6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGUsXG4gIG1lZXRpbmdBc3Npc3Q6IE1lZXRpbmdBc3Npc3RUeXBlLFxuICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPzogTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVcbik6IEV2ZW50VHlwZSA9PiB7XG4gIGxldCBzdGFydERhdGUgPSBkYXlqcyh3aW5kb3dTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLmZvcm1hdCgpO1xuICBpZiAocHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U/LmRheU9mV2VlayA+IDApIHtcbiAgICBzdGFydERhdGUgPSBkYXlqcyhzdGFydERhdGUpXG4gICAgICAuaXNvV2VlayhwcmVmZXJyZWRTdGFydFRpbWVSYW5nZT8uZGF5T2ZXZWVrKVxuICAgICAgLmZvcm1hdCgpO1xuICB9XG5cbiAgaWYgKHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPy5zdGFydFRpbWUpIHtcbiAgICBjb25zdCBzdGFydFRpbWUgPSBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZT8uc3RhcnRUaW1lO1xuICAgIGNvbnN0IGhvdXIgPSBwYXJzZUludChzdGFydFRpbWUuc2xpY2UoMCwgMiksIDEwKTtcbiAgICBjb25zdCBtaW51dGUgPSBwYXJzZUludChzdGFydFRpbWUuc2xpY2UoMyksIDEwKTtcblxuICAgIHN0YXJ0RGF0ZSA9IGRheWpzKHN0YXJ0RGF0ZSkuaG91cihob3VyKS5taW51dGUobWludXRlKS5mb3JtYXQoKTtcbiAgfVxuXG4gIGNvbnN0IGV2ZW50SWQgPSB1dWlkKCk7XG4gIGNvbnN0IG5ld0V2ZW50OiBFdmVudFR5cGUgPSB7XG4gICAgaWQ6IGAke2V2ZW50SWR9IyR7bWVldGluZ0Fzc2lzdC5jYWxlbmRhcklkfWAsXG4gICAgbWV0aG9kOiAnY3JlYXRlJyxcbiAgICB0aXRsZTogbWVldGluZ0Fzc2lzdC5zdW1tYXJ5LFxuICAgIHN0YXJ0RGF0ZSxcbiAgICBlbmREYXRlOiBkYXlqcyhzdGFydERhdGUpLmFkZChtZWV0aW5nQXNzaXN0LmR1cmF0aW9uLCAnbScpLmZvcm1hdCgpLFxuICAgIGFsbERheTogZmFsc2UsXG4gICAgbm90ZXM6IG1lZXRpbmdBc3Npc3Qubm90ZXMsXG4gICAgdGltZXpvbmU6IGhvc3RUaW1lem9uZSxcbiAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICBkZWxldGVkOiBmYWxzZSxcbiAgICBwcmlvcml0eTogbWVldGluZ0Fzc2lzdC5wcmlvcml0eSxcbiAgICBpc0ZvbGxvd1VwOiBmYWxzZSxcbiAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICBpc1Bvc3RFdmVudDogZmFsc2UsXG4gICAgbW9kaWZpYWJsZTogdHJ1ZSxcbiAgICBzZW5kVXBkYXRlczogbWVldGluZ0Fzc2lzdD8uc2VuZFVwZGF0ZXMsXG4gICAgc3RhdHVzOiAnY29uZmlybWVkJyxcbiAgICBzdW1tYXJ5OiBtZWV0aW5nQXNzaXN0LnN1bW1hcnksXG4gICAgdHJhbnNwYXJlbmN5OiBtZWV0aW5nQXNzaXN0Py50cmFuc3BhcmVuY3ksXG4gICAgdmlzaWJpbGl0eTogbWVldGluZ0Fzc2lzdD8udmlzaWJpbGl0eSxcbiAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgY2FsZW5kYXJJZDogbWVldGluZ0Fzc2lzdC5jYWxlbmRhcklkLFxuICAgIHVzZURlZmF1bHRBbGFybXM6IG1lZXRpbmdBc3Npc3QudXNlRGVmYXVsdEFsYXJtcyxcbiAgICB0aW1lQmxvY2tpbmc6IG1lZXRpbmdBc3Npc3QuYnVmZmVyVGltZSxcbiAgICB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmc6IG1lZXRpbmdBc3Npc3Q/LmJ1ZmZlclRpbWUgPyB0cnVlIDogZmFsc2UsXG4gICAgdXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2U6IHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPy5pZCA/IHRydWUgOiBmYWxzZSxcbiAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnM6IG1lZXRpbmdBc3Npc3Q/LnJlbWluZGVycz8uWzBdID4gLTEgPyB0cnVlIDogZmFsc2UsXG4gICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbDogdHJ1ZSxcbiAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlOiB0cnVlLFxuICAgIGR1cmF0aW9uOiBtZWV0aW5nQXNzaXN0Py5kdXJhdGlvbixcbiAgICB1c2VyTW9kaWZpZWREdXJhdGlvbjogdHJ1ZSxcbiAgICB1c2VySWQ6IGhvc3RBdHRlbmRlZT8udXNlcklkLFxuICAgIGFueW9uZUNhbkFkZFNlbGY6IGZhbHNlLFxuICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyczogbWVldGluZ0Fzc2lzdD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOiBtZWV0aW5nQXNzaXN0Py5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICBvcmlnaW5hbFN0YXJ0RGF0ZTogdW5kZWZpbmVkLFxuICAgIG9yaWdpbmFsQWxsRGF5OiBmYWxzZSxcbiAgICBtZWV0aW5nSWQ6IG1lZXRpbmdBc3Npc3QuaWQsXG4gICAgZXZlbnRJZCxcbiAgfTtcblxuICByZXR1cm4gbmV3RXZlbnQ7XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCA9IGFzeW5jIChldmVudElkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICAvLyB2YWxpZGF0ZVxuICAgIGlmICghZXZlbnRJZCkge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGV2ZW50SWQsXG4gICAgICAgICcgbm8gZXZlbnRJZCBpbnNpZGUgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCdcbiAgICAgICk7XG4gICAgfVxuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnTGlzdFByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbkV2ZW50SWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgcXVlcnkgTGlzdFByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbkV2ZW50SWQoJGV2ZW50SWQ6IFN0cmluZyEpIHtcbiAgICAgICAgUHJlZmVycmVkVGltZVJhbmdlKHdoZXJlOiB7ZXZlbnRJZDoge19lcTogJGV2ZW50SWR9fSkge1xuICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgZGF5T2ZXZWVrXG4gICAgICAgICAgZW5kVGltZVxuICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICBpZFxuICAgICAgICAgIHN0YXJ0VGltZVxuICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgIHVzZXJJZFxuICAgICAgICB9XG4gICAgICB9XG4gICAgYDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBldmVudElkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXSB9IH0gPVxuICAgICAgYXdhaXQgZ290XG4gICAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICAgIH0sXG4gICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGluc2lkZSAgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCcpO1xuICAgIHJlcz8uZGF0YT8uUHJlZmVycmVkVGltZVJhbmdlPy5tYXAoKHB0KSA9PlxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIHB0LFxuICAgICAgICAnIHByZWZlcnJlZFRpbWVSYW5nZSAtIHJlcz8uZGF0YT8uUHJlZmVycmVkVGltZVJhbmdlIGluc2lkZSAgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCAnXG4gICAgICApXG4gICAgKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/LlByZWZlcnJlZFRpbWVSYW5nZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGxpc3QgcHJlZmVycmVkIHRpbWUgcmFuZ2VzIGZvciBldmVudCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgY3JlYXRlUmVtaW5kZXJzRnJvbU1pbnV0ZXNBbmRFdmVudCA9IChcbiAgZXZlbnRJZDogc3RyaW5nLFxuICBtaW51dGVzOiBudW1iZXJbXSxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgdXNlRGVmYXVsdDogYm9vbGVhbixcbiAgdXNlcklkOiBzdHJpbmdcbik6IFJlbWluZGVyc0ZvckV2ZW50VHlwZSA9PiB7XG4gIHJldHVybiB7XG4gICAgZXZlbnRJZCxcbiAgICByZW1pbmRlcnM6IG1pbnV0ZXMubWFwKChtKSA9PiAoe1xuICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgIHVzZXJJZCxcbiAgICAgIGV2ZW50SWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIG1pbnV0ZXM6IG0sXG4gICAgICB1c2VEZWZhdWx0LFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICBkZWxldGVkOiB0cnVlLFxuICAgIH0pKSxcbiAgfTtcbn07XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVCdWZmZXJUaW1lRm9yTmV3TWVldGluZ0V2ZW50ID0gKFxuICBldmVudDogRXZlbnRNZWV0aW5nUGx1c1R5cGUsXG4gIGJ1ZmZlclRpbWU6IEJ1ZmZlclRpbWVOdW1iZXJUeXBlXG4pID0+IHtcbiAgbGV0IHZhbHVlc1RvUmV0dXJuOiBhbnkgPSB7fTtcbiAgdmFsdWVzVG9SZXR1cm4ubmV3RXZlbnQgPSBldmVudDtcbiAgY29uc3QgZXZlbnRJZCA9IHV1aWQoKTtcbiAgY29uc3QgZXZlbnRJZDEgPSB1dWlkKCk7XG4gIGNvbnN0IHByZUV2ZW50SWQgPSBldmVudD8ucHJlRXZlbnRJZCB8fCBgJHtldmVudElkfSMke2V2ZW50Py5jYWxlbmRhcklkfWA7XG4gIGNvbnN0IHBvc3RFdmVudElkID0gZXZlbnQ/LnBvc3RFdmVudElkIHx8IGAke2V2ZW50SWQxfSMke2V2ZW50Py5jYWxlbmRhcklkfWA7XG5cbiAgaWYgKGJ1ZmZlclRpbWUuYmVmb3JlRXZlbnQgPiAwKSB7XG4gICAgY29uc3QgYmVmb3JlRXZlbnRPckVtcHR5OiBFdmVudFBsdXNUeXBlID0ge1xuICAgICAgaWQ6IHByZUV2ZW50SWQsXG4gICAgICBpc1ByZUV2ZW50OiB0cnVlLFxuICAgICAgZm9yRXZlbnRJZDogZXZlbnQuaWQsXG4gICAgICBub3RlczogJ0J1ZmZlciB0aW1lJyxcbiAgICAgIHN1bW1hcnk6ICdCdWZmZXIgdGltZScsXG4gICAgICBzdGFydERhdGU6IGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnN1YnRyYWN0KGJ1ZmZlclRpbWUuYmVmb3JlRXZlbnQsICdtJylcbiAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgZW5kRGF0ZTogZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuZm9ybWF0KCksXG4gICAgICBtZXRob2Q6ICdjcmVhdGUnLFxuICAgICAgdXNlcklkOiBldmVudC51c2VySWQsXG4gICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgcHJpb3JpdHk6IDEsXG4gICAgICBtb2RpZmlhYmxlOiB0cnVlLFxuICAgICAgYW55b25lQ2FuQWRkU2VsZjogZmFsc2UsXG4gICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnM6IGZhbHNlLFxuICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM6IGZhbHNlLFxuICAgICAgb3JpZ2luYWxTdGFydERhdGU6IHVuZGVmaW5lZCxcbiAgICAgIG9yaWdpbmFsQWxsRGF5OiBmYWxzZSxcbiAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgY2FsZW5kYXJJZDogZXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgICB0aW1lem9uZTogZXZlbnQ/LnRpbWV6b25lLFxuICAgICAgaXNGb2xsb3dVcDogZmFsc2UsXG4gICAgICBpc1Bvc3RFdmVudDogZmFsc2UsXG4gICAgICBldmVudElkOiBwcmVFdmVudElkLnNwbGl0KCcjJylbMF0sXG4gICAgfTtcblxuICAgIHZhbHVlc1RvUmV0dXJuLmJlZm9yZUV2ZW50ID0gYmVmb3JlRXZlbnRPckVtcHR5O1xuICAgIHZhbHVlc1RvUmV0dXJuLm5ld0V2ZW50ID0ge1xuICAgICAgLi4udmFsdWVzVG9SZXR1cm4ubmV3RXZlbnQsXG4gICAgICBwcmVFdmVudElkLFxuICAgICAgdGltZUJsb2NraW5nOiB7XG4gICAgICAgIC4uLnZhbHVlc1RvUmV0dXJuPy5uZXdFdmVudD8udGltZUJsb2NraW5nLFxuICAgICAgICBiZWZvcmVFdmVudDogYnVmZmVyVGltZS5iZWZvcmVFdmVudCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIGlmIChidWZmZXJUaW1lLmFmdGVyRXZlbnQgPiAwKSB7XG4gICAgY29uc3QgYWZ0ZXJFdmVudE9yRW1wdHk6IEV2ZW50UGx1c1R5cGUgPSB7XG4gICAgICBpZDogcG9zdEV2ZW50SWQsXG4gICAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICAgIGZvckV2ZW50SWQ6IGV2ZW50LmlkLFxuICAgICAgaXNQb3N0RXZlbnQ6IHRydWUsXG4gICAgICBub3RlczogJ0J1ZmZlciB0aW1lJyxcbiAgICAgIHN1bW1hcnk6ICdCdWZmZXIgdGltZScsXG4gICAgICBzdGFydERhdGU6IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIGVuZERhdGU6IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5hZGQoYnVmZmVyVGltZS5hZnRlckV2ZW50LCAnbScpXG4gICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIG1ldGhvZDogJ2NyZWF0ZScsXG4gICAgICB1c2VySWQ6IGV2ZW50Py51c2VySWQsXG4gICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICBwcmlvcml0eTogMSxcbiAgICAgIGlzRm9sbG93VXA6IGZhbHNlLFxuICAgICAgbW9kaWZpYWJsZTogdHJ1ZSxcbiAgICAgIGFueW9uZUNhbkFkZFNlbGY6IGZhbHNlLFxuICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiBmYWxzZSxcbiAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOiBmYWxzZSxcbiAgICAgIG9yaWdpbmFsU3RhcnREYXRlOiB1bmRlZmluZWQsXG4gICAgICBvcmlnaW5hbEFsbERheTogZmFsc2UsXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIGNhbGVuZGFySWQ6IGV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgdGltZXpvbmU6IGV2ZW50Py50aW1lem9uZSxcbiAgICAgIGV2ZW50SWQ6IHBvc3RFdmVudElkLnNwbGl0KCcjJylbMF0sXG4gICAgfTtcblxuICAgIHZhbHVlc1RvUmV0dXJuLmFmdGVyRXZlbnQgPSBhZnRlckV2ZW50T3JFbXB0eTtcbiAgICB2YWx1ZXNUb1JldHVybi5uZXdFdmVudCA9IHtcbiAgICAgIC4uLnZhbHVlc1RvUmV0dXJuLm5ld0V2ZW50LFxuICAgICAgcG9zdEV2ZW50SWQsXG4gICAgICB0aW1lQmxvY2tpbmc6IHtcbiAgICAgICAgLi4udmFsdWVzVG9SZXR1cm4/Lm5ld0V2ZW50Py50aW1lQmxvY2tpbmcsXG4gICAgICAgIGFmdGVyRXZlbnQ6IGJ1ZmZlclRpbWUuYWZ0ZXJFdmVudCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIHJldHVybiB2YWx1ZXNUb1JldHVybiBhcyBWYWx1ZXNUb1JldHVybkZvckJ1ZmZlckV2ZW50c1R5cGU7XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0VXNlclByZWZlcmVuY2VzID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxVc2VyUHJlZmVyZW5jZVR5cGU+ID0+IHtcbiAgdHJ5IHtcbiAgICBpZiAoIXVzZXJJZCkge1xuICAgICAgY29uc29sZS5sb2coJ3VzZXJJZCBpcyBudWxsJyk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRVc2VyUHJlZmVyZW5jZXMnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgIHF1ZXJ5IGdldFVzZXJQcmVmZXJlbmNlcygkdXNlcklkOiB1dWlkISkge1xuICAgICAgVXNlcl9QcmVmZXJlbmNlKHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfX0pIHtcbiAgICAgICAgc3RhcnRUaW1lc1xuICAgICAgICBlbmRUaW1lc1xuICAgICAgICBiYWNrVG9CYWNrTWVldGluZ3NcbiAgICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgICBjb3B5Q2F0ZWdvcmllc1xuICAgICAgICBjb3B5SXNCcmVha1xuICAgICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgICBjb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgICAgY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgIGRlbGV0ZWRcbiAgICAgICAgZm9sbG93VXBcbiAgICAgICAgaWRcbiAgICAgICAgaXNQdWJsaWNDYWxlbmRhclxuICAgICAgICBtYXhOdW1iZXJPZk1lZXRpbmdzXG4gICAgICAgIG1heFdvcmtMb2FkUGVyY2VudFxuICAgICAgICBwdWJsaWNDYWxlbmRhckNhdGVnb3JpZXNcbiAgICAgICAgcmVtaW5kZXJzXG4gICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICB1c2VySWRcbiAgICAgICAgbWluTnVtYmVyT2ZCcmVha3NcbiAgICAgICAgYnJlYWtDb2xvclxuICAgICAgICBicmVha0xlbmd0aFxuICAgICAgICBjb3B5Q29sb3JcbiAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgICAgb25Cb2FyZGVkXG4gICAgICB9XG4gICAgfVxuICBgO1xuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IFVzZXJfUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uVXNlcl9QcmVmZXJlbmNlPy5bMF07XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIGdldFVzZXJQcmVmZXJlbmNlcycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0R2xvYmFsQ2FsZW5kYXIgPSBhc3luYyAodXNlcklkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2dldEdsb2JhbENhbGVuZGFyJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgcXVlcnkgZ2V0R2xvYmFsQ2FsZW5kYXIoJHVzZXJJZDogdXVpZCEpIHtcbiAgICAgICAgICBDYWxlbmRhcih3aGVyZToge2dsb2JhbFByaW1hcnk6IHtfZXE6IHRydWV9LCB1c2VySWQ6IHtfZXE6ICR1c2VySWR9fSkge1xuICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICBhY2Nlc3NMZXZlbFxuICAgICAgICAgICAgYWNjb3VudFxuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGRlZmF1bHRSZW1pbmRlcnNcbiAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgZ2xvYmFsUHJpbWFyeVxuICAgICAgICAgICAgaWRcbiAgICAgICAgICAgIG1vZGlmaWFibGVcbiAgICAgICAgICAgIHByaW1hcnlcbiAgICAgICAgICAgIHJlc291cmNlXG4gICAgICAgICAgICB0aXRsZVxuICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICBgO1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgQ2FsZW5kYXI6IENhbGVuZGFyVHlwZVtdIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgcmV0dXJuIHJlcy5kYXRhLkNhbGVuZGFyPy5bMF07XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgZ2xvYmFsIGNhbGVuZGFyJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBhZGp1c3RTdGFydERhdGVzRm9yQnJlYWtFdmVudHNGb3JEYXkgPSAoXG4gIGFsbEV2ZW50czogRXZlbnRQbHVzVHlwZVtdLFxuICBicmVha0V2ZW50czogRXZlbnRQbHVzVHlwZVtdLFxuICB1c2VyUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlLFxuICB0aW1lem9uZTogc3RyaW5nXG4pOiBFdmVudFBsdXNUeXBlW10gPT4ge1xuICAvLyB2YWxpZGF0ZVxuICBpZiAoIWFsbEV2ZW50cz8uWzBdPy5pZCkge1xuICAgIGNvbnNvbGUubG9nKCdubyBhbGxFdmVudHMgaW5zaWRlIGFkanVzdFN0YXJ0RGF0ZXNGb3JCcmVha0V2ZW50cycpO1xuICAgIHJldHVybjtcbiAgfVxuXG4gIGNvbnN0IHN0YXJ0VGltZXMgPSB1c2VyUHJlZmVyZW5jZS5zdGFydFRpbWVzO1xuICBjb25zdCBlbmRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlLmVuZFRpbWVzO1xuICBjb25zdCBkYXlPZldlZWtJbnQgPSBnZXRJU09EYXkoXG4gICAgZGF5anMoYWxsRXZlbnRzPy5bMF0/LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICApO1xuICBjb25zdCBzdGFydEhvdXIgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gIGNvbnN0IHN0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuICBjb25zdCBlbmRIb3VyID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgY29uc3QgZW5kTWludXRlID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcbiAgY29uc3QgbmV3QnJlYWtFdmVudHMgPSBbXTtcbiAgLyoqXG4gICAgICogY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHsgaG91cnM6IHN0YXJ0SG91ciwgbWludXRlczogc3RhcnRNaW51dGUgfSlcbiAgICAgIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oeyBob3VyczogZW5kSG91ciwgbWludXRlczogZW5kTWludXRlIH0pXG4gICAgICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbilcbiAgICAgIHJldHVybiB0b3RhbER1cmF0aW9uLmFzSG91cnMoKVxuICAgICAqL1xuXG4gIGNvbnN0IHN0YXJ0T2ZXb3JraW5nRGF5ID0gZGF5anMoYWxsRXZlbnRzWzBdPy5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAuaG91cihzdGFydEhvdXIpXG4gICAgLm1pbnV0ZShzdGFydE1pbnV0ZSk7XG5cbiAgY29uc3QgZW5kT2ZXb3JraW5nRGF5ID0gZGF5anMoYWxsRXZlbnRzWzBdPy5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHoodGltZXpvbmUsIHRydWUpXG4gICAgLmhvdXIoZW5kSG91cilcbiAgICAubWludXRlKGVuZE1pbnV0ZSk7XG5cbiAgY29uc3QgZmlsdGVyZWRFdmVudHMgPSBhbGxFdmVudHMuZmlsdGVyKChlKSA9PiAhZS5pc0JyZWFrKTtcbiAgaWYgKGJyZWFrRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgZm9yIChjb25zdCBicmVha0V2ZW50IG9mIGJyZWFrRXZlbnRzKSB7XG4gICAgICBsZXQgZm91bmRTcGFjZSA9IGZhbHNlO1xuICAgICAgbGV0IGluZGV4ID0gMDtcbiAgICAgIHdoaWxlICghZm91bmRTcGFjZSAmJiBpbmRleCA8IGZpbHRlcmVkRXZlbnRzLmxlbmd0aCkge1xuICAgICAgICBjb25zdCBwb3NzaWJsZUVuZERhdGUgPSBkYXlqcyhcbiAgICAgICAgICBmaWx0ZXJlZEV2ZW50c1tpbmRleF0uc3RhcnREYXRlLnNsaWNlKDAsIDE5KVxuICAgICAgICApLnR6KHRpbWV6b25lLCB0cnVlKTtcblxuICAgICAgICBjb25zdCBwb3NzaWJsZVN0YXJ0RGF0ZSA9IGRheWpzKHBvc3NpYmxlRW5kRGF0ZS5mb3JtYXQoKS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5zdWJ0cmFjdCh1c2VyUHJlZmVyZW5jZS5icmVha0xlbmd0aCwgJ21pbnV0ZScpO1xuICAgICAgICBsZXQgaXNCZXR3ZWVuU3RhcnQgPSB0cnVlO1xuICAgICAgICBsZXQgaXNCZXR3ZWVuRW5kID0gdHJ1ZTtcbiAgICAgICAgbGV0IGJldHdlZW5JbmRleCA9IDA7XG4gICAgICAgIGxldCBiZXR3ZWVuV29ya2luZ0RheVN0YXJ0ID0gdHJ1ZTtcbiAgICAgICAgbGV0IGJldHdlZW5Xb3JraW5nRGF5RW5kID0gdHJ1ZTtcbiAgICAgICAgbGV0IGlzQmV0d2VlbkJyZWFrU3RhcnQgPSB0cnVlO1xuICAgICAgICBsZXQgaXNCZXR3ZWVuQnJlYWtFbmQgPSB0cnVlO1xuXG4gICAgICAgIHdoaWxlIChcbiAgICAgICAgICAoaXNCZXR3ZWVuU3RhcnQgfHxcbiAgICAgICAgICAgIGlzQmV0d2VlbkVuZCB8fFxuICAgICAgICAgICAgIWJldHdlZW5Xb3JraW5nRGF5U3RhcnQgfHxcbiAgICAgICAgICAgICFiZXR3ZWVuV29ya2luZ0RheUVuZCB8fFxuICAgICAgICAgICAgaXNCZXR3ZWVuQnJlYWtTdGFydCB8fFxuICAgICAgICAgICAgaXNCZXR3ZWVuQnJlYWtFbmQpICYmXG4gICAgICAgICAgYmV0d2VlbkluZGV4IDwgZmlsdGVyZWRFdmVudHMubGVuZ3RoXG4gICAgICAgICkge1xuICAgICAgICAgIGlzQmV0d2VlblN0YXJ0ID0gcG9zc2libGVTdGFydERhdGUuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMoZmlsdGVyZWRFdmVudHNbYmV0d2VlbkluZGV4XS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICAgIHRydWVcbiAgICAgICAgICAgICksXG4gICAgICAgICAgICBkYXlqcyhmaWx0ZXJlZEV2ZW50c1tiZXR3ZWVuSW5kZXhdLmVuZERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICAgIHRydWVcbiAgICAgICAgICAgICksXG4gICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICdbKSdcbiAgICAgICAgICApO1xuXG4gICAgICAgICAgaXNCZXR3ZWVuRW5kID0gcG9zc2libGVFbmREYXRlLmlzQmV0d2VlbihcbiAgICAgICAgICAgIGRheWpzKGZpbHRlcmVkRXZlbnRzW2JldHdlZW5JbmRleF0uc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooXG4gICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgICAgICB0cnVlXG4gICAgICAgICAgICApLFxuICAgICAgICAgICAgZGF5anMoZmlsdGVyZWRFdmVudHNbYmV0d2VlbkluZGV4XS5lbmREYXRlLnNsaWNlKDAsIDE5KSkudHooXG4gICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgICAgICB0cnVlXG4gICAgICAgICAgICApLFxuICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAnKF0nXG4gICAgICAgICAgKTtcblxuICAgICAgICAgIGJldHdlZW5Xb3JraW5nRGF5U3RhcnQgPSBwb3NzaWJsZVN0YXJ0RGF0ZS5pc0JldHdlZW4oXG4gICAgICAgICAgICBzdGFydE9mV29ya2luZ0RheSxcbiAgICAgICAgICAgIGVuZE9mV29ya2luZ0RheSxcbiAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICk7XG5cbiAgICAgICAgICBiZXR3ZWVuV29ya2luZ0RheUVuZCA9IHBvc3NpYmxlRW5kRGF0ZS5pc0JldHdlZW4oXG4gICAgICAgICAgICBzdGFydE9mV29ya2luZ0RheSxcbiAgICAgICAgICAgIGVuZE9mV29ya2luZ0RheSxcbiAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgJyhdJ1xuICAgICAgICAgICk7XG5cbiAgICAgICAgICBmb3IgKGNvbnN0IGJyZWFrRXZlbnQgb2YgYnJlYWtFdmVudHMpIHtcbiAgICAgICAgICAgIGlzQmV0d2VlbkJyZWFrU3RhcnQgPSBwb3NzaWJsZVN0YXJ0RGF0ZS5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKGJyZWFrRXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLFxuICAgICAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApO1xuXG4gICAgICAgICAgICBpc0JldHdlZW5CcmVha0VuZCA9IHBvc3NpYmxlRW5kRGF0ZS5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKGJyZWFrRXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLFxuICAgICAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnKF0nXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGJldHdlZW5JbmRleCsrO1xuICAgICAgICB9XG5cbiAgICAgICAgZm91bmRTcGFjZSA9XG4gICAgICAgICAgIWlzQmV0d2VlblN0YXJ0ICYmXG4gICAgICAgICAgIWlzQmV0d2VlbkVuZCAmJlxuICAgICAgICAgIGJldHdlZW5Xb3JraW5nRGF5U3RhcnQgJiZcbiAgICAgICAgICBiZXR3ZWVuV29ya2luZ0RheUVuZCAmJlxuICAgICAgICAgICFpc0JldHdlZW5CcmVha1N0YXJ0ICYmXG4gICAgICAgICAgIWlzQmV0d2VlbkJyZWFrRW5kO1xuXG4gICAgICAgIGlmIChmb3VuZFNwYWNlKSB7XG4gICAgICAgICAgY29uc3QgbmV3QnJlYWtFdmVudCA9IHtcbiAgICAgICAgICAgIC4uLmJyZWFrRXZlbnQsXG4gICAgICAgICAgICBzdGFydERhdGU6IHBvc3NpYmxlU3RhcnREYXRlLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICBlbmREYXRlOiBwb3NzaWJsZUVuZERhdGUudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICB9O1xuICAgICAgICAgIG5ld0JyZWFrRXZlbnRzLnB1c2gobmV3QnJlYWtFdmVudCk7XG4gICAgICAgIH1cblxuICAgICAgICBpbmRleCsrO1xuICAgICAgfVxuICAgIH1cbiAgfVxuXG4gIHJldHVybiBuZXdCcmVha0V2ZW50cztcbn07XG5leHBvcnQgY29uc3QgY29udmVydFRvVG90YWxXb3JraW5nSG91cnNGb3JJbnRlcm5hbEF0dGVuZGVlID0gKFxuICB1c2VyUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlLFxuICBob3N0U3RhcnREYXRlOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nXG4pID0+IHtcbiAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlLnN0YXJ0VGltZXM7XG4gIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2UuZW5kVGltZXM7XG4gIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICApO1xuICBjb25zdCBzdGFydEhvdXIgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gIGNvbnN0IHN0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuICBjb25zdCBlbmRIb3VyID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgY29uc3QgZW5kTWludXRlID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcblxuICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiBzdGFydEhvdXIsXG4gICAgbWludXRlczogc3RhcnRNaW51dGUsXG4gIH0pO1xuICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHsgaG91cnM6IGVuZEhvdXIsIG1pbnV0ZXM6IGVuZE1pbnV0ZSB9KTtcbiAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICByZXR1cm4gdG90YWxEdXJhdGlvbi5hc0hvdXJzKCk7XG59O1xuXG5leHBvcnQgY29uc3QgY29udmVydFRvVG90YWxXb3JraW5nSG91cnNGb3JFeHRlcm5hbEF0dGVuZGVlID0gKFxuICBhdHRlbmRlZUV2ZW50czogRXZlbnRQbHVzVHlwZVtdLFxuICBob3N0U3RhcnREYXRlOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICB1c2VyVGltZXpvbmU6IHN0cmluZ1xuKSA9PiB7XG4gIGNvbnN0IGRheU9mV2Vla0ludEJ5SG9zdCA9IGdldElTT0RheShcbiAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICApO1xuICBjb25zdCBzYW1lRGF5RXZlbnRzID0gYXR0ZW5kZWVFdmVudHMuZmlsdGVyKFxuICAgIChlKSA9PlxuICAgICAgZ2V0SVNPRGF5KFxuICAgICAgICBkYXlqcyhlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLnRvRGF0ZSgpXG4gICAgICApID09PSBkYXlPZldlZWtJbnRCeUhvc3RcbiAgKTtcbiAgY29uc3QgbWluU3RhcnREYXRlID0gXy5taW5CeShzYW1lRGF5RXZlbnRzLCAoZSkgPT5cbiAgICBkYXlqcyhlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLnVuaXgoKVxuICApO1xuICBjb25zdCBtYXhFbmREYXRlID0gXy5tYXhCeShzYW1lRGF5RXZlbnRzLCAoZSkgPT5cbiAgICBkYXlqcyhlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC51bml4KClcbiAgKTtcblxuICBsZXQgd29ya0VuZEhvdXJCeUhvc3QgPSBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAuaG91cigpO1xuICBjb25zdCB3b3JrRW5kTWludXRlQnlIb3N0ID0gZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmlzQmV0d2VlbihcbiAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5taW51dGUoMCksXG4gICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICdtaW51dGUnLFxuICAgICAgJ1spJ1xuICAgIClcbiAgICA/IDE1XG4gICAgOiBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgIClcbiAgICAgID8gMzBcbiAgICAgIDogZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoNDUpLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDQ1XG4gICAgICAgIDogMDtcbiAgaWYgKHdvcmtFbmRNaW51dGVCeUhvc3QgPT09IDApIHtcbiAgICBpZiAod29ya0VuZEhvdXJCeUhvc3QgPCAyMykge1xuICAgICAgd29ya0VuZEhvdXJCeUhvc3QgKz0gMTtcbiAgICB9XG4gIH1cblxuICBjb25zdCB3b3JrU3RhcnRIb3VyQnlIb3N0ID0gZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmhvdXIoKTtcbiAgY29uc3Qgd29ya1N0YXJ0TWludXRlQnlIb3N0ID0gZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmlzQmV0d2VlbihcbiAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5taW51dGUoMCksXG4gICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICdtaW51dGUnLFxuICAgICAgJ1spJ1xuICAgIClcbiAgICA/IDBcbiAgICA6IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAnWyknXG4gICAgICAgICAgKVxuICAgICAgPyAxNVxuICAgICAgOiBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSg0NSksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgID8gMzBcbiAgICAgICAgOiA0NTtcblxuICBjb25zb2xlLmxvZyhcbiAgICB3b3JrU3RhcnRIb3VyQnlIb3N0LFxuICAgIHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCxcbiAgICB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAnIHdvcmtTdGFydEhvdXJCeUhvc3QsIHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCwgd29ya0VuZEhvdXJCeUhvc3QgZm9yIHRvdGFsIHdvcmtpbmcgaG91cnMnXG4gICk7XG4gIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgaG91cnM6IHdvcmtTdGFydEhvdXJCeUhvc3QsXG4gICAgbWludXRlczogd29ya1N0YXJ0TWludXRlQnlIb3N0LFxuICB9KTtcbiAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgaG91cnM6IHdvcmtFbmRIb3VyQnlIb3N0LFxuICAgIG1pbnV0ZXM6IHdvcmtFbmRNaW51dGVCeUhvc3QsXG4gIH0pO1xuICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gIHJldHVybiB0b3RhbER1cmF0aW9uLmFzSG91cnMoKTtcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZUJyZWFrcyA9IChcbiAgdXNlclByZWZlcmVuY2VzOiBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIG51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZTogbnVtYmVyLFxuICBldmVudE1pcnJvcjogRXZlbnRQbHVzVHlwZSxcbiAgZ2xvYmFsQ2FsZW5kYXJJZD86IHN0cmluZ1xuKTogRXZlbnRQbHVzVHlwZVtdID0+IHtcbiAgY29uc3QgYnJlYWtzID0gW107XG4gIC8vIHZhbGlkYXRlXG4gIGlmICghdXNlclByZWZlcmVuY2VzPy5icmVha0xlbmd0aCkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJ25vIHVzZXIgcHJlZmVyZW5jZXMgYnJlYWtMZW5ndGggcHJvdmlkZWQgaW5zaWRlIGdlbmVyYXRlQnJlYWtzJ1xuICAgICk7XG4gICAgcmV0dXJuIGJyZWFrcztcbiAgfVxuXG4gIGlmICghbnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICAnbm8gbnVtYmVyIG9mIGJyZWFrcyB0byBnZW5lcmF0ZSBwcm92aWRlZCBpbnNpZGUgZ2VuZXJhdGVCcmVha3MnXG4gICAgKTtcbiAgICByZXR1cm4gYnJlYWtzO1xuICB9XG5cbiAgaWYgKCFldmVudE1pcnJvcikge1xuICAgIGNvbnNvbGUubG9nKCdubyBldmVudCBtaXJyb3IgcHJvdmlkZWQgaW5zaWRlIGdlbmVyYXRlQnJlYWtzJyk7XG4gICAgcmV0dXJuIGJyZWFrcztcbiAgfVxuICBjb25zb2xlLmxvZyhcbiAgICBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUsXG4gICAgJyBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUgaW5zaWRlIGdlbmVyYXRlQnJlYWtzJ1xuICApO1xuICBmb3IgKGxldCBpID0gMDsgaSA8IG51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZTsgaSsrKSB7XG4gICAgY29uc3QgZXZlbnRJZCA9IHV1aWQoKTtcbiAgICBjb25zdCBicmVha0V2ZW50OiBFdmVudFBsdXNUeXBlID0ge1xuICAgICAgaWQ6IGAke2V2ZW50SWR9IyR7Z2xvYmFsQ2FsZW5kYXJJZCB8fCBldmVudE1pcnJvci5jYWxlbmRhcklkfWAsXG4gICAgICB1c2VySWQ6IHVzZXJQcmVmZXJlbmNlcy51c2VySWQsXG4gICAgICB0aXRsZTogJ0JyZWFrJyxcbiAgICAgIHN0YXJ0RGF0ZTogZGF5anMoZXZlbnRNaXJyb3Iuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGV2ZW50TWlycm9yLnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuZm9ybWF0KCksXG4gICAgICBlbmREYXRlOiBkYXlqcyhldmVudE1pcnJvci5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooZXZlbnRNaXJyb3IudGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5hZGQodXNlclByZWZlcmVuY2VzLmJyZWFrTGVuZ3RoLCAnbWludXRlJylcbiAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgYWxsRGF5OiBmYWxzZSxcbiAgICAgIG5vdGVzOiAnQnJlYWsnLFxuICAgICAgdGltZXpvbmU6IGV2ZW50TWlycm9yLnRpbWV6b25lLFxuICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICBwcmlvcml0eTogMSxcbiAgICAgIGlzRm9sbG93VXA6IGZhbHNlLFxuICAgICAgaXNQcmVFdmVudDogZmFsc2UsXG4gICAgICBtb2RpZmlhYmxlOiB0cnVlLFxuICAgICAgYW55b25lQ2FuQWRkU2VsZjogZmFsc2UsXG4gICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnM6IGZhbHNlLFxuICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM6IGZhbHNlLFxuICAgICAgb3JpZ2luYWxTdGFydERhdGU6IHVuZGVmaW5lZCxcbiAgICAgIG9yaWdpbmFsQWxsRGF5OiBmYWxzZSxcbiAgICAgIGNhbGVuZGFySWQ6IGdsb2JhbENhbGVuZGFySWQgfHwgZXZlbnRNaXJyb3IuY2FsZW5kYXJJZCxcbiAgICAgIGJhY2tncm91bmRDb2xvcjogdXNlclByZWZlcmVuY2VzLmJyZWFrQ29sb3IgfHwgJyNGN0VCRjcnLFxuICAgICAgaXNCcmVhazogdHJ1ZSxcbiAgICAgIGR1cmF0aW9uOiB1c2VyUHJlZmVyZW5jZXMuYnJlYWtMZW5ndGgsXG4gICAgICB1c2VyTW9kaWZpZWREdXJhdGlvbjogdHJ1ZSxcbiAgICAgIHVzZXJNb2RpZmllZENvbG9yOiB0cnVlLFxuICAgICAgaXNQb3N0RXZlbnQ6IGZhbHNlLFxuICAgICAgbWV0aG9kOiAnY3JlYXRlJyxcbiAgICAgIGV2ZW50SWQsXG4gICAgfTtcbiAgICBicmVha3MucHVzaChicmVha0V2ZW50KTtcbiAgfVxuXG4gIHJldHVybiBicmVha3M7XG59O1xuXG5leHBvcnQgY29uc3Qgc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50c0ZvckRheSA9IChcbiAgd29ya2luZ0hvdXJzOiBudW1iZXIsXG4gIHVzZXJQcmVmZXJlbmNlczogVXNlclByZWZlcmVuY2VUeXBlLFxuICBhbGxFdmVudHM6IEV2ZW50UGx1c1R5cGVbXVxuKSA9PiB7XG4gIC8vIHZhbGlkYXRlXG4gIGlmICghdXNlclByZWZlcmVuY2VzPy5icmVha0xlbmd0aCkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJ25vIHVzZXIgcHJlZmVyZW5jZXMgYnJlYWtMZW5ndGggcHJvdmlkZWQgaW5zaWRlIHNob3VsZEdlbmVyYXRlQnJlYWtFdmVudHMnXG4gICAgKTtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICBpZiAoIShhbGxFdmVudHM/Lmxlbmd0aCA+IDApKSB7XG4gICAgY29uc29sZS5sb2coJ25vIGFsbEV2ZW50cyBwcmVzZW50IGluc2lkZSBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF5Jyk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgY29uc3QgYnJlYWtFdmVudHMgPSBhbGxFdmVudHMuZmlsdGVyKChldmVudCkgPT4gZXZlbnQuaXNCcmVhayk7XG4gIGNvbnN0IG51bWJlck9mQnJlYWtzUGVyRGF5ID0gdXNlclByZWZlcmVuY2VzLm1pbk51bWJlck9mQnJlYWtzO1xuXG4gIGNvbnN0IGJyZWFrSG91cnNGcm9tTWluQnJlYWtzID1cbiAgICAodXNlclByZWZlcmVuY2VzLmJyZWFrTGVuZ3RoIC8gNjApICogbnVtYmVyT2ZCcmVha3NQZXJEYXk7XG4gIGNvbnN0IGhvdXJzTXVzdEJlQnJlYWsgPVxuICAgIHdvcmtpbmdIb3VycyAqICgxIC0gdXNlclByZWZlcmVuY2VzLm1heFdvcmtMb2FkUGVyY2VudCAvIDEwMCk7XG5cbiAgbGV0IGJyZWFrSG91cnNBdmFpbGFibGUgPSAwO1xuXG4gIGlmIChicmVha0hvdXJzRnJvbU1pbkJyZWFrcyA+IGhvdXJzTXVzdEJlQnJlYWspIHtcbiAgICBicmVha0hvdXJzQXZhaWxhYmxlID0gYnJlYWtIb3Vyc0Zyb21NaW5CcmVha3M7XG4gIH0gZWxzZSB7XG4gICAgYnJlYWtIb3Vyc0F2YWlsYWJsZSA9IGhvdXJzTXVzdEJlQnJlYWs7XG4gIH1cblxuICBsZXQgYnJlYWtIb3Vyc1VzZWQgPSAwO1xuICBmb3IgKGNvbnN0IGJyZWFrRXZlbnQgb2YgYnJlYWtFdmVudHMpIHtcbiAgICBjb25zdCBkdXJhdGlvbiA9IGRheWpzXG4gICAgICAuZHVyYXRpb24oXG4gICAgICAgIGRheWpzKFxuICAgICAgICAgIGRheWpzKGJyZWFrRXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpXG4gICAgICAgICkuZGlmZihcbiAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpXG4gICAgICAgIClcbiAgICAgIClcbiAgICAgIC5hc0hvdXJzKCk7XG4gICAgYnJlYWtIb3Vyc1VzZWQgKz0gZHVyYXRpb247XG4gIH1cblxuICBpZiAoYnJlYWtIb3Vyc1VzZWQgPj0gYnJlYWtIb3Vyc0F2YWlsYWJsZSkge1xuICAgIGNvbnNvbGUubG9nKCdicmVha0hvdXJzVXNlZCA+PSBicmVha0hvdXJzQXZhaWxhYmxlJyk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgaWYgKCEoYWxsRXZlbnRzPy5sZW5ndGggPiAwKSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJ3RoZXJlIGFyZSBubyBldmVudHMgZm9yIHRoaXMgZGF0ZSBpbnNpZGUgc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50cydcbiAgICApO1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuXG4gIHJldHVybiB0cnVlO1xufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlQnJlYWtFdmVudHNGb3JEYXkgPSBhc3luYyAoXG4gIHVzZXJQcmVmZXJlbmNlczogVXNlclByZWZlcmVuY2VUeXBlLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgaG9zdFN0YXJ0RGF0ZTogc3RyaW5nLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgZ2xvYmFsQ2FsZW5kYXJJZD86IHN0cmluZyxcbiAgaXNGaXJzdERheT86IGJvb2xlYW5cbikgPT4ge1xuICB0cnkge1xuICAgIC8vIHZhbGlkYXRlXG4gICAgaWYgKCF1c2VyUHJlZmVyZW5jZXM/LmJyZWFrTGVuZ3RoKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgJ25vIHVzZXIgcHJlZmVyZW5jZXMgYnJlYWtMZW5ndGggcHJvdmlkZWQgaW5zaWRlIHNob3VsZEdlbmVyYXRlQnJlYWtFdmVudHMnXG4gICAgICApO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuXG4gICAgaWYgKCF1c2VySWQpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyB1c2VySWQgcHJvdmlkZWQgaW5zaWRlIHNob3VsZEdlbmVyYXRlQnJlYWtFdmVudHMnKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGlmICghaG9zdFN0YXJ0RGF0ZSkge1xuICAgICAgY29uc29sZS5sb2coJ25vIHN0YXJ0RGF0ZSBwcm92aWRlZCBpbnNpZGUgc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50cycpO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuXG4gICAgaWYgKCFob3N0VGltZXpvbmUpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyB0aW1lem9uZSBwcm92aWRlZCBpbnNpZGUgc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50cycpO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuXG4gICAgaWYgKGlzRmlyc3REYXkpIHtcbiAgICAgIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2VzLmVuZFRpbWVzO1xuICAgICAgY29uc3QgZGF5T2ZXZWVrSW50ID0gZ2V0SVNPRGF5KFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICAgICAgKTtcblxuICAgICAgbGV0IHN0YXJ0SG91ckJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuaG91cigpO1xuICAgICAgbGV0IHN0YXJ0TWludXRlQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5taW51dGUoKTtcbiAgICAgIGNvbnN0IGVuZEhvdXIgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgICAgY29uc3QgZW5kTWludXRlID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcblxuICAgICAgLy8gdmFsaWRhdGUgdmFsdWVzIGJlZm9yZSBjYWxjdWxhdGluZ1xuICAgICAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5zdGFydFRpbWVzO1xuICAgICAgY29uc3Qgd29ya1N0YXJ0SG91ciA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZSA9IHN0YXJ0VGltZXMuZmluZChcbiAgICAgICAgKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRcbiAgICAgICkubWludXRlcztcblxuICAgICAgaWYgKFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkuaXNBZnRlcihcbiAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkuaG91cihlbmRIb3VyKS5taW51dGUoZW5kTWludXRlKVxuICAgICAgICApXG4gICAgICApIHtcbiAgICAgICAgLy8gcmV0dXJuIGVtcHR5IGFzIG91dHNpZGUgb2Ygd29yayB0aW1lXG4gICAgICAgIHJldHVybiBudWxsO1xuICAgICAgfVxuXG4gICAgICAvLyBjaGFuZ2UgdG8gd29yayBzdGFydCB0aW1lIGFzIHdvcmsgc3RhcnQgdGltZSBhZnRlciBzdGFydCBkYXRlXG4gICAgICBpZiAoXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmlzQmVmb3JlKFxuICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXIpXG4gICAgICAgICAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlKVxuICAgICAgICAgIClcbiAgICAgICkge1xuICAgICAgICBzdGFydEhvdXJCeUhvc3QgPSB3b3JrU3RhcnRIb3VyO1xuICAgICAgICBzdGFydE1pbnV0ZUJ5SG9zdCA9IHdvcmtTdGFydE1pbnV0ZTtcbiAgICAgIH1cblxuICAgICAgY29uc3Qgd29ya2luZ0hvdXJzID0gY29udmVydFRvVG90YWxXb3JraW5nSG91cnNGb3JJbnRlcm5hbEF0dGVuZGVlKFxuICAgICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICAgIGhvc3RTdGFydERhdGUsXG4gICAgICAgIGhvc3RUaW1lem9uZVxuICAgICAgKTtcbiAgICAgIGNvbnNvbGUubG9nKHdvcmtpbmdIb3VycywgJyB3b3JraW5nSG91cnMnKTtcbiAgICAgIGNvbnN0IGFsbEV2ZW50cyA9IGF3YWl0IGxpc3RFdmVudHNGb3JEYXRlKFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGUpXG4gICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICBob3N0VGltZXpvbmVcbiAgICAgICk7XG5cbiAgICAgIGlmICghKGFsbEV2ZW50cz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgJ25vIGFsbEV2ZW50cyBwcmVzZW50IGluc2lkZSBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF5J1xuICAgICAgICApO1xuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH1cblxuICAgICAgY29uc3Qgc2hvdWxkR2VuZXJhdGVCcmVha3MgPSBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF5KFxuICAgICAgICB3b3JraW5nSG91cnMsXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgYWxsRXZlbnRzXG4gICAgICApO1xuXG4gICAgICBjb25zb2xlLmxvZyhzaG91bGRHZW5lcmF0ZUJyZWFrcywgJyBzaG91bGRHZW5lcmF0ZUJyZWFrcycpO1xuXG4gICAgICAvLyB2YWxpZGF0ZVxuICAgICAgaWYgKCFzaG91bGRHZW5lcmF0ZUJyZWFrcykge1xuICAgICAgICBjb25zb2xlLmxvZygnc2hvdWxkIG5vdCBnZW5lcmF0ZSBicmVha3MnKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9XG5cbiAgICAgIGxldCBob3Vyc1VzZWQgPSAwO1xuXG4gICAgICBpZiAoYWxsRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGZvciAoY29uc3QgYWxsRXZlbnQgb2YgYWxsRXZlbnRzKSB7XG4gICAgICAgICAgY29uc3QgZHVyYXRpb24gPSBkYXlqc1xuICAgICAgICAgICAgLmR1cmF0aW9uKFxuICAgICAgICAgICAgICBkYXlqcyhhbGxFdmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5kaWZmKFxuICAgICAgICAgICAgICAgICAgZGF5anMoYWxsRXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIClcbiAgICAgICAgICAgIClcbiAgICAgICAgICAgIC5hc0hvdXJzKCk7XG4gICAgICAgICAgaG91cnNVc2VkICs9IGR1cmF0aW9uO1xuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGNvbnNvbGUubG9nKGhvdXJzVXNlZCwgJyBob3Vyc1VzZWQnKTtcblxuICAgICAgbGV0IGhvdXJzQXZhaWxhYmxlID0gd29ya2luZ0hvdXJzIC0gaG91cnNVc2VkO1xuXG4gICAgICBjb25zb2xlLmxvZyhob3Vyc0F2YWlsYWJsZSwgJyBob3Vyc0F2YWlsYWJsZScpO1xuXG4gICAgICAvLyBndWFyYW50ZWUgYnJlYWtzXG4gICAgICBjb25zdCBob3Vyc011c3RCZUJyZWFrID1cbiAgICAgICAgd29ya2luZ0hvdXJzICogKDEgLSB1c2VyUHJlZmVyZW5jZXMubWF4V29ya0xvYWRQZXJjZW50IC8gMTAwKTtcblxuICAgICAgY29uc29sZS5sb2coaG91cnNNdXN0QmVCcmVhaywgJyBob3Vyc011c3RCZUJyZWFrJyk7XG5cbiAgICAgIGlmIChob3Vyc0F2YWlsYWJsZSA8IGhvdXJzTXVzdEJlQnJlYWspIHtcbiAgICAgICAgaG91cnNBdmFpbGFibGUgPSBob3Vyc011c3RCZUJyZWFrO1xuICAgICAgfVxuICAgICAgLy8gbm8gaG91cnMgYXZhaWxhYmxlXG4gICAgICBpZiAoaG91cnNBdmFpbGFibGUgPD0gMCkge1xuICAgICAgICBjb25zb2xlLmxvZyhob3Vyc0F2YWlsYWJsZSwgJyBubyBob3VycyBhdmFpbGFibGUnKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IG9sZEJyZWFrRXZlbnRzID0gYWxsRXZlbnRzXG4gICAgICAgIC5maWx0ZXIoKGV2ZW50KSA9PiBldmVudC5pc0JyZWFrKVxuICAgICAgICAuZmlsdGVyKChlKSA9PlxuICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5pc1NhbWUoXG4gICAgICAgICAgICAgIGRheWpzKGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKSxcbiAgICAgICAgICAgICAgJ2RheSdcbiAgICAgICAgICAgIClcbiAgICAgICAgKTtcblxuICAgICAgY29uc3QgYnJlYWtFdmVudHMgPSBvbGRCcmVha0V2ZW50cztcblxuICAgICAgY29uc3QgbnVtYmVyT2ZCcmVha3NQZXJEYXkgPSB1c2VyUHJlZmVyZW5jZXMubWluTnVtYmVyT2ZCcmVha3M7XG5cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBudW1iZXJPZkJyZWFrc1BlckRheSxcbiAgICAgICAgJyBudW1iZXJPZkJyZWFrc1BlckRheSBha2EgdXNlclByZWZlcmVuY2VzLm1pbk51bWJlck9mQnJlYWtzJ1xuICAgICAgKTtcbiAgICAgIGNvbnNvbGUubG9nKHVzZXJQcmVmZXJlbmNlcy5icmVha0xlbmd0aCwgJyB1c2VyUHJlZmVyZW5jZXMuYnJlYWtMZW5ndGgnKTtcblxuICAgICAgY29uc3QgYnJlYWtIb3Vyc1RvR2VuZXJhdGVGb3JNaW5CcmVha3MgPVxuICAgICAgICAodXNlclByZWZlcmVuY2VzLmJyZWFrTGVuZ3RoIC8gNjApICogbnVtYmVyT2ZCcmVha3NQZXJEYXk7XG5cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBicmVha0hvdXJzVG9HZW5lcmF0ZUZvck1pbkJyZWFrcyxcbiAgICAgICAgJyBicmVha0hvdXJzVG9HZW5lcmF0ZUZvck1pbkJyZWFrcydcbiAgICAgICk7XG5cbiAgICAgIGxldCBicmVha0hvdXJzVG9HZW5lcmF0ZSA9IDA7XG5cbiAgICAgIGlmIChicmVha0hvdXJzVG9HZW5lcmF0ZUZvck1pbkJyZWFrcyA+IGhvdXJzQXZhaWxhYmxlKSB7XG4gICAgICAgIGJyZWFrSG91cnNUb0dlbmVyYXRlID0gaG91cnNBdmFpbGFibGU7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBicmVha0hvdXJzVG9HZW5lcmF0ZSA9IGJyZWFrSG91cnNUb0dlbmVyYXRlRm9yTWluQnJlYWtzO1xuICAgICAgfVxuXG4gICAgICBjb25zb2xlLmxvZyhicmVha0hvdXJzVG9HZW5lcmF0ZSwgJyBicmVha0hvdXJzVG9HZW5lcmF0ZScpO1xuXG4gICAgICBsZXQgYnJlYWtIb3Vyc1VzZWQgPSAwO1xuXG4gICAgICBpZiAoYnJlYWtFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgZm9yIChjb25zdCBicmVha0V2ZW50IG9mIGJyZWFrRXZlbnRzKSB7XG4gICAgICAgICAgY29uc3QgZHVyYXRpb24gPSBkYXlqc1xuICAgICAgICAgICAgLmR1cmF0aW9uKFxuICAgICAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLmRpZmYoXG4gICAgICAgICAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KFxuICAgICAgICAgICAgICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgICAgICAgICAgICAgIHRydWVcbiAgICAgICAgICAgICAgICAgIClcbiAgICAgICAgICAgICAgICApXG4gICAgICAgICAgICApXG4gICAgICAgICAgICAuYXNIb3VycygpO1xuICAgICAgICAgIGJyZWFrSG91cnNVc2VkICs9IGR1cmF0aW9uO1xuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IGFjdHVhbEJyZWFrSG91cnNUb0dlbmVyYXRlID0gYnJlYWtIb3Vyc1RvR2VuZXJhdGUgLSBicmVha0hvdXJzVXNlZDtcblxuICAgICAgaWYgKGFjdHVhbEJyZWFrSG91cnNUb0dlbmVyYXRlID4gaG91cnNBdmFpbGFibGUpIHtcbiAgICAgICAgY29uc29sZS5sb2coJyBubyBob3VycyBhdmFpbGFibGUgdG8gZ2VuZXJhdGUgYnJlYWsnKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9XG4gICAgICBjb25zb2xlLmxvZyhhY3R1YWxCcmVha0hvdXJzVG9HZW5lcmF0ZSwgJyBhY3R1YWxCcmVha0hvdXJzVG9HZW5lcmF0ZScpO1xuICAgICAgY29uc29sZS5sb2coYnJlYWtIb3Vyc1VzZWQsICcgYnJlYWtIb3Vyc1VzZWQnKTtcbiAgICAgIGNvbnNvbGUubG9nKGJyZWFrSG91cnNUb0dlbmVyYXRlRm9yTWluQnJlYWtzLCAnIGJyZWFrSG91cnNBdmFpbGFibGUnKTtcbiAgICAgIGNvbnN0IGJyZWFrTGVuZ3RoQXNIb3VycyA9IHVzZXJQcmVmZXJlbmNlcy5icmVha0xlbmd0aCAvIDYwO1xuICAgICAgY29uc29sZS5sb2coYnJlYWtMZW5ndGhBc0hvdXJzLCAnIGJyZWFrTGVuZ3RoQXNIb3VycycpO1xuICAgICAgY29uc3QgbnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlID0gTWF0aC5mbG9vcihcbiAgICAgICAgYWN0dWFsQnJlYWtIb3Vyc1RvR2VuZXJhdGUgLyBicmVha0xlbmd0aEFzSG91cnNcbiAgICAgICk7XG4gICAgICBjb25zb2xlLmxvZyhudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUsICcgbnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlJyk7XG5cbiAgICAgIGlmIChudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUgPCAxKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKCdzaG91bGQgbm90IGdlbmVyYXRlIGJyZWFrcycpO1xuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH1cblxuICAgICAgaWYgKGJyZWFrSG91cnNUb0dlbmVyYXRlID4gNikge1xuICAgICAgICBjb25zb2xlLmxvZygnYnJlYWtIb3Vyc1RvR2VuZXJhdGUgaXMgPiA2Jyk7XG4gICAgICAgIHJldHVybiBudWxsO1xuICAgICAgfVxuXG4gICAgICBjb25zdCBldmVudE1pcnJvciA9IGFsbEV2ZW50cy5maW5kKChldmVudCkgPT4gIWV2ZW50LmlzQnJlYWspO1xuXG4gICAgICBjb25zdCBuZXdFdmVudHMgPSBnZW5lcmF0ZUJyZWFrcyhcbiAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUsXG4gICAgICAgIGV2ZW50TWlycm9yLFxuICAgICAgICBnbG9iYWxDYWxlbmRhcklkXG4gICAgICApO1xuXG4gICAgICByZXR1cm4gbmV3RXZlbnRzO1xuICAgIH1cblxuICAgIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2VzLmVuZFRpbWVzO1xuICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICAgKTtcblxuICAgIGNvbnN0IGVuZEhvdXIgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgIGNvbnN0IGVuZE1pbnV0ZSA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG5cbiAgICAvLyB2YWxpZGF0ZSB2YWx1ZXMgYmVmb3JlIGNhbGN1bGF0aW5nXG4gICAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5zdGFydFRpbWVzO1xuICAgIGNvbnN0IHN0YXJ0SG91ciA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgICBjb25zdCBzdGFydE1pbnV0ZSA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcblxuICAgIGNvbnN0IHdvcmtpbmdIb3VycyA9IGNvbnZlcnRUb1RvdGFsV29ya2luZ0hvdXJzRm9ySW50ZXJuYWxBdHRlbmRlZShcbiAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgIGhvc3RTdGFydERhdGUsXG4gICAgICBob3N0VGltZXpvbmVcbiAgICApO1xuICAgIGNvbnN0IGFsbEV2ZW50cyA9IGF3YWl0IGxpc3RFdmVudHNGb3JEYXRlKFxuICAgICAgdXNlcklkLFxuICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5ob3VyKHN0YXJ0SG91cilcbiAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZSlcbiAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgICAgIC5taW51dGUoZW5kTWludXRlKVxuICAgICAgICAuZm9ybWF0KCksXG4gICAgICBob3N0VGltZXpvbmVcbiAgICApO1xuICAgIGlmICghKGFsbEV2ZW50cz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAnbm8gYWxsRXZlbnRzIHByZXNlbnQgaW5zaWRlIHNob3VsZEdlbmVyYXRlQnJlYWtFdmVudHNGb3JEYXknXG4gICAgICApO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuICAgIGNvbnN0IHNob3VsZEdlbmVyYXRlQnJlYWtzID0gc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50c0ZvckRheShcbiAgICAgIHdvcmtpbmdIb3VycyxcbiAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgIGFsbEV2ZW50c1xuICAgICk7XG4gICAgLy8gdmFsaWRhdGVcbiAgICBpZiAoIXNob3VsZEdlbmVyYXRlQnJlYWtzKSB7XG4gICAgICBjb25zb2xlLmxvZygnc2hvdWxkIG5vdCBnZW5lcmF0ZSBicmVha3MnKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGxldCBob3Vyc1VzZWQgPSAwO1xuXG4gICAgaWYgKGFsbEV2ZW50cz8ubGVuZ3RoID4gMCkge1xuICAgICAgZm9yIChjb25zdCBhbGxFdmVudCBvZiBhbGxFdmVudHMpIHtcbiAgICAgICAgY29uc3QgZHVyYXRpb24gPSBkYXlqc1xuICAgICAgICAgIC5kdXJhdGlvbihcbiAgICAgICAgICAgIGRheWpzKGFsbEV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAuZGlmZihcbiAgICAgICAgICAgICAgICBkYXlqcyhhbGxFdmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIClcbiAgICAgICAgICApXG4gICAgICAgICAgLmFzSG91cnMoKTtcbiAgICAgICAgaG91cnNVc2VkICs9IGR1cmF0aW9uO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKGhvdXJzVXNlZCwgJyBob3Vyc1VzZWQnKTtcblxuICAgIGxldCBob3Vyc0F2YWlsYWJsZSA9IHdvcmtpbmdIb3VycyAtIGhvdXJzVXNlZDtcbiAgICAvLyBndWFyYW50ZWUgYnJlYWtzXG4gICAgY29uc3QgaG91cnNNdXN0QmVCcmVhayA9XG4gICAgICB3b3JraW5nSG91cnMgKiAoMSAtIHVzZXJQcmVmZXJlbmNlcy5tYXhXb3JrTG9hZFBlcmNlbnQgLyAxMDApO1xuXG4gICAgY29uc29sZS5sb2coaG91cnNNdXN0QmVCcmVhaywgJyBob3Vyc011c3RCZUJyZWFrJyk7XG4gICAgY29uc29sZS5sb2coaG91cnNBdmFpbGFibGUsICcgaG91cnNBdmFpbGFibGUnKTtcblxuICAgIGlmIChob3Vyc0F2YWlsYWJsZSA8IGhvdXJzTXVzdEJlQnJlYWspIHtcbiAgICAgIGhvdXJzQXZhaWxhYmxlID0gaG91cnNNdXN0QmVCcmVhaztcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhob3Vyc0F2YWlsYWJsZSwgJyBob3Vyc0F2YWlsYWJsZScpO1xuXG4gICAgLy8gbm8gaG91cnMgYXZhaWxhYmxlXG4gICAgaWYgKGhvdXJzQXZhaWxhYmxlIDw9IDApIHtcbiAgICAgIGNvbnNvbGUubG9nKGhvdXJzQXZhaWxhYmxlLCAnIG5vIGhvdXJzIGF2YWlsYWJsZScpO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuXG4gICAgY29uc3Qgb2xkQnJlYWtFdmVudHMgPSBhbGxFdmVudHNcbiAgICAgIC5maWx0ZXIoKGV2ZW50KSA9PiBldmVudC5pc0JyZWFrKVxuICAgICAgLmZpbHRlcigoZSkgPT5cbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuaXNTYW1lKGRheWpzKGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKSwgJ2RheScpXG4gICAgICApO1xuXG4gICAgY29uc3QgYnJlYWtFdmVudHMgPSBvbGRCcmVha0V2ZW50cztcblxuICAgIGNvbnN0IG51bWJlck9mQnJlYWtzUGVyRGF5ID0gdXNlclByZWZlcmVuY2VzLm1pbk51bWJlck9mQnJlYWtzO1xuICAgIGNvbnNvbGUubG9nKG51bWJlck9mQnJlYWtzUGVyRGF5LCAnIG51bWJlck9mQnJlYWtzUGVyRGF5Jyk7XG4gICAgY29uc3QgYnJlYWtIb3Vyc1RvR2VuZXJhdGVGb3JNaW5CcmVha3MgPVxuICAgICAgKHVzZXJQcmVmZXJlbmNlcy5icmVha0xlbmd0aCAvIDYwKSAqIG51bWJlck9mQnJlYWtzUGVyRGF5O1xuICAgIGxldCBicmVha0hvdXJzVG9HZW5lcmF0ZSA9IDA7XG5cbiAgICBpZiAoYnJlYWtIb3Vyc1RvR2VuZXJhdGVGb3JNaW5CcmVha3MgPiBob3Vyc0F2YWlsYWJsZSkge1xuICAgICAgYnJlYWtIb3Vyc1RvR2VuZXJhdGUgPSBob3Vyc0F2YWlsYWJsZTtcbiAgICB9IGVsc2Uge1xuICAgICAgYnJlYWtIb3Vyc1RvR2VuZXJhdGUgPSBicmVha0hvdXJzVG9HZW5lcmF0ZUZvck1pbkJyZWFrcztcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhicmVha0hvdXJzVG9HZW5lcmF0ZSwgJyBicmVha0hvdXJzVG9HZW5lcmF0ZScpO1xuXG4gICAgbGV0IGJyZWFrSG91cnNVc2VkID0gMDtcblxuICAgIGlmIChicmVha0V2ZW50cz8ubGVuZ3RoID4gMCkge1xuICAgICAgZm9yIChjb25zdCBicmVha0V2ZW50IG9mIGJyZWFrRXZlbnRzKSB7XG4gICAgICAgIGNvbnN0IGR1cmF0aW9uID0gZGF5anNcbiAgICAgICAgICAuZHVyYXRpb24oXG4gICAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAuZGlmZihcbiAgICAgICAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgKVxuICAgICAgICAgIClcbiAgICAgICAgICAuYXNIb3VycygpO1xuICAgICAgICBicmVha0hvdXJzVXNlZCArPSBkdXJhdGlvbjtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBhY3R1YWxCcmVha0hvdXJzVG9HZW5lcmF0ZSA9IGJyZWFrSG91cnNUb0dlbmVyYXRlIC0gYnJlYWtIb3Vyc1VzZWQ7XG5cbiAgICBpZiAoYWN0dWFsQnJlYWtIb3Vyc1RvR2VuZXJhdGUgPiBob3Vyc0F2YWlsYWJsZSkge1xuICAgICAgY29uc29sZS5sb2coJyBubyBob3VycyBhdmFpbGFibGUgdG8gZ2VuZXJhdGUgYnJlYWsnKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKGJyZWFrSG91cnNVc2VkLCAnIGJyZWFrSG91cnNVc2VkJyk7XG4gICAgY29uc29sZS5sb2coYnJlYWtIb3Vyc1RvR2VuZXJhdGUsICcgYnJlYWtIb3Vyc0F2YWlsYWJsZScpO1xuICAgIGNvbnN0IGJyZWFrTGVuZ3RoQXNIb3VycyA9IHVzZXJQcmVmZXJlbmNlcy5icmVha0xlbmd0aCAvIDYwO1xuICAgIGNvbnNvbGUubG9nKGJyZWFrTGVuZ3RoQXNIb3VycywgJyBicmVha0xlbmd0aEFzSG91cnMnKTtcbiAgICBjb25zdCBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUgPSBNYXRoLmZsb29yKFxuICAgICAgYWN0dWFsQnJlYWtIb3Vyc1RvR2VuZXJhdGUgLyBicmVha0xlbmd0aEFzSG91cnNcbiAgICApO1xuICAgIGNvbnNvbGUubG9nKG51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZSwgJyBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUnKTtcblxuICAgIGlmIChudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUgPCAxKSB7XG4gICAgICBjb25zb2xlLmxvZygnc2hvdWxkIG5vdCBnZW5lcmF0ZSBicmVha3MnKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGlmIChicmVha0hvdXJzVG9HZW5lcmF0ZSA+IDYpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdicmVha0hvdXJzVG9HZW5lcmF0ZSBpcyA+IDYnKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGNvbnN0IGV2ZW50TWlycm9yID0gYWxsRXZlbnRzLmZpbmQoKGV2ZW50KSA9PiAhZXZlbnQuaXNCcmVhayk7XG5cbiAgICBjb25zdCBuZXdFdmVudHMgPSBnZW5lcmF0ZUJyZWFrcyhcbiAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgIG51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZSxcbiAgICAgIGV2ZW50TWlycm9yLFxuICAgICAgZ2xvYmFsQ2FsZW5kYXJJZFxuICAgICk7XG5cbiAgICByZXR1cm4gbmV3RXZlbnRzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2VuZXJhdGUgYnJlYWtzIGZvciBkYXknKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlQnJlYWtFdmVudHNGb3JEYXRlID0gYXN5bmMgKFxuICB1c2VyUHJlZmVyZW5jZXM6IFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGhvc3RTdGFydERhdGU6IHN0cmluZyxcbiAgaG9zdEVuZERhdGU6IHN0cmluZyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIGdsb2JhbENhbGVuZGFySWQ/OiBzdHJpbmdcbik6IFByb21pc2U8RXZlbnRQbHVzVHlwZVtdIHwgW10+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB0b3RhbEJyZWFrRXZlbnRzID0gW107XG4gICAgY29uc3QgdG90YWxEYXlzID0gZGF5anMoaG9zdEVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5kaWZmKGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLCAnZGF5Jyk7XG4gICAgY29uc29sZS5sb2codG90YWxEYXlzLCAnIHRvdGFsRGF5cyBpbnNpZGUgZ2VuZXJhdGVCcmVha0V2ZW50c0ZvckRhdGUnKTtcbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsRGF5czsgaSsrKSB7XG4gICAgICBjb25zdCBkYXlEYXRlID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5hZGQoaSwgJ2RheScpXG4gICAgICAgIC5mb3JtYXQoKTtcblxuICAgICAgY29uc3QgbmV3QnJlYWtFdmVudHMgPSBhd2FpdCBnZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF5KFxuICAgICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgZGF5RGF0ZSxcbiAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICBnbG9iYWxDYWxlbmRhcklkLFxuICAgICAgICBpID09PSAwXG4gICAgICApO1xuXG4gICAgICBpZiAoaSA9PT0gMCkge1xuICAgICAgICBjb25zdCBlbmRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5lbmRUaW1lcztcbiAgICAgICAgY29uc3QgZGF5T2ZXZWVrSW50ID0gZ2V0SVNPRGF5KFxuICAgICAgICAgIGRheWpzKGRheURhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICAgICAgICk7XG5cbiAgICAgICAgbGV0IHN0YXJ0SG91ciA9IGRheWpzKGRheURhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoKTtcbiAgICAgICAgbGV0IHN0YXJ0TWludXRlID0gZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAubWludXRlKCk7XG4gICAgICAgIGNvbnN0IGVuZEhvdXIgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgICAgICBjb25zdCBlbmRNaW51dGUgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuXG4gICAgICAgIC8vIHZhbGlkYXRlIHZhbHVlcyBiZWZvcmUgY2FsY3VsYXRpbmdcbiAgICAgICAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5zdGFydFRpbWVzO1xuICAgICAgICBjb25zdCB3b3JrU3RhcnRIb3VyID0gc3RhcnRUaW1lcy5maW5kKFxuICAgICAgICAgIChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50XG4gICAgICAgICkuaG91cjtcbiAgICAgICAgY29uc3Qgd29ya1N0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKFxuICAgICAgICAgIChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50XG4gICAgICAgICkubWludXRlcztcblxuICAgICAgICBpZiAoXG4gICAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpLmlzQWZ0ZXIoXG4gICAgICAgICAgICBkYXlqcyhkYXlEYXRlLnNsaWNlKDAsIDE5KSkuaG91cihlbmRIb3VyKS5taW51dGUoZW5kTWludXRlKVxuICAgICAgICAgIClcbiAgICAgICAgKSB7XG4gICAgICAgICAgLy8gcmV0dXJuIGVtcHR5IGFzIG91dHNpZGUgb2Ygd29yayB0aW1lXG4gICAgICAgICAgY29udGludWU7XG4gICAgICAgIH1cblxuICAgICAgICAvLyBjaGFuZ2UgdG8gd29yayBzdGFydCB0aW1lIGFzIGJlZm9yZSBzdGFydCB0aW1lXG4gICAgICAgIGlmIChcbiAgICAgICAgICBkYXlqcyhkYXlEYXRlLnNsaWNlKDAsIDE5KSkuaXNCZWZvcmUoXG4gICAgICAgICAgICBkYXlqcyhkYXlEYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91cilcbiAgICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGUpXG4gICAgICAgICAgKVxuICAgICAgICApIHtcbiAgICAgICAgICBzdGFydEhvdXIgPSB3b3JrU3RhcnRIb3VyO1xuICAgICAgICAgIHN0YXJ0TWludXRlID0gd29ya1N0YXJ0TWludXRlO1xuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgYWxsRXZlbnRzID0gYXdhaXQgbGlzdEV2ZW50c0ZvckRhdGUoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIGRheWpzKGRheURhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHN0YXJ0SG91cilcbiAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGUpXG4gICAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmhvdXIoZW5kSG91cilcbiAgICAgICAgICAgIC5taW51dGUoZW5kTWludXRlKVxuICAgICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICAgIGhvc3RUaW1lem9uZVxuICAgICAgICApO1xuICAgICAgICBjb25zdCBuZXdCcmVha0V2ZW50c0FkanVzdGVkID1cbiAgICAgICAgICBhd2FpdCBhZGp1c3RTdGFydERhdGVzRm9yQnJlYWtFdmVudHNGb3JEYXkoXG4gICAgICAgICAgICBhbGxFdmVudHMsXG4gICAgICAgICAgICBuZXdCcmVha0V2ZW50cyxcbiAgICAgICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgICAgIGhvc3RUaW1lem9uZVxuICAgICAgICAgICk7XG4gICAgICAgIGlmIChuZXdCcmVha0V2ZW50c0FkanVzdGVkPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgbmV3QnJlYWtFdmVudHNBZGp1c3RlZC5mb3JFYWNoKChiKSA9PlxuICAgICAgICAgICAgY29uc29sZS5sb2coYiwgJyBuZXdCcmVha0V2ZW50c0FkanVzdGVkJylcbiAgICAgICAgICApO1xuICAgICAgICAgIHRvdGFsQnJlYWtFdmVudHMucHVzaCguLi5uZXdCcmVha0V2ZW50c0FkanVzdGVkKTtcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfVxuXG4gICAgICBjb25zdCBlbmRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5lbmRUaW1lcztcbiAgICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkudG9EYXRlKClcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IGVuZEhvdXIgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgICAgY29uc3QgZW5kTWludXRlID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcblxuICAgICAgLy8gdmFsaWRhdGUgdmFsdWVzIGJlZm9yZSBjYWxjdWxhdGluZ1xuICAgICAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5zdGFydFRpbWVzO1xuICAgICAgY29uc3Qgc3RhcnRIb3VyID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgICAgY29uc3Qgc3RhcnRNaW51dGUgPSBzdGFydFRpbWVzLmZpbmQoXG4gICAgICAgIChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50XG4gICAgICApLm1pbnV0ZXM7XG5cbiAgICAgIGNvbnN0IGFsbEV2ZW50cyA9IGF3YWl0IGxpc3RFdmVudHNGb3JEYXRlKFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGRheWpzKGRheURhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyKVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGUpXG4gICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICBkYXlqcyhkYXlEYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGUpXG4gICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICBob3N0VGltZXpvbmVcbiAgICAgICk7XG4gICAgICBjb25zdCBuZXdCcmVha0V2ZW50c0FkanVzdGVkID0gYXdhaXQgYWRqdXN0U3RhcnREYXRlc0ZvckJyZWFrRXZlbnRzRm9yRGF5KFxuICAgICAgICBhbGxFdmVudHMsXG4gICAgICAgIG5ld0JyZWFrRXZlbnRzLFxuICAgICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICAgIGhvc3RUaW1lem9uZVxuICAgICAgKTtcbiAgICAgIGlmIChuZXdCcmVha0V2ZW50c0FkanVzdGVkPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIG5ld0JyZWFrRXZlbnRzQWRqdXN0ZWQuZm9yRWFjaCgoYikgPT5cbiAgICAgICAgICBjb25zb2xlLmxvZyhiLCAnIG5ld0JyZWFrRXZlbnRzQWRqdXN0ZWQnKVxuICAgICAgICApO1xuICAgICAgICB0b3RhbEJyZWFrRXZlbnRzLnB1c2goLi4ubmV3QnJlYWtFdmVudHNBZGp1c3RlZCk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgcmV0dXJuIHRvdGFsQnJlYWtFdmVudHM7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF0ZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVXb3JrVGltZXNGb3JJbnRlcm5hbEF0dGVuZGVlID0gKFxuICBob3N0SWQ6IHN0cmluZyxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHVzZXJQcmVmZXJlbmNlOiBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICB1c2VyVGltZXpvbmU6IHN0cmluZ1xuKTogV29ya1RpbWVUeXBlW10gPT4ge1xuICAvLyA3IGRheXMgaW4gYSB3ZWVrXG4gIGNvbnN0IGRheXNJbldlZWsgPSA3O1xuICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2Uuc3RhcnRUaW1lcztcbiAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZS5lbmRUaW1lcztcbiAgY29uc3Qgd29ya1RpbWVzOiBXb3JrVGltZVR5cGVbXSA9IFtdO1xuXG4gIGZvciAobGV0IGkgPSAwOyBpIDwgZGF5c0luV2VlazsgaSsrKSB7XG4gICAgY29uc3QgZGF5T2ZXZWVrSW50ID0gaSArIDE7XG4gICAgY29uc3Qgc3RhcnRIb3VyID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuICAgIGNvbnN0IGVuZEhvdXIgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgIGNvbnN0IGVuZE1pbnV0ZSA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG5cbiAgICB3b3JrVGltZXMucHVzaCh7XG4gICAgICBkYXlPZldlZWs6IGRheU9mV2Vla0ludFRvU3RyaW5nW2RheU9mV2Vla0ludF0sXG4gICAgICBzdGFydFRpbWU6IGRheWpzKFxuICAgICAgICBzZXRJU09EYXkoXG4gICAgICAgICAgZGF5anMoKVxuICAgICAgICAgICAgLmhvdXIoc3RhcnRIb3VyKVxuICAgICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZSlcbiAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudG9EYXRlKCksXG4gICAgICAgICAgaSArIDFcbiAgICAgICAgKVxuICAgICAgKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICBlbmRUaW1lOiBkYXlqcyhcbiAgICAgICAgc2V0SVNPRGF5KFxuICAgICAgICAgIGRheWpzKClcbiAgICAgICAgICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZSlcbiAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudG9EYXRlKCksXG4gICAgICAgICAgaSArIDFcbiAgICAgICAgKVxuICAgICAgKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICBob3N0SWQsXG4gICAgICB1c2VySWQsXG4gICAgfSk7XG4gIH1cblxuICByZXR1cm4gd29ya1RpbWVzO1xufTtcblxuY29uc3QgZm9ybWF0VG9Nb250aERheSA9IChtb250aDogTW9udGhUeXBlLCBkYXk6IERheVR5cGUpOiBNb250aERheVR5cGUgPT4ge1xuICBjb25zdCBtb250aEZvcm1hdCA9IChtb250aCA8IDkgPyBgMCR7bW9udGggKyAxfWAgOiBgJHttb250aCArIDF9YCkgYXMgTU07XG4gIGNvbnN0IGRheUZvcm1hdCA9IChkYXkgPCAxMCA/IGAwJHtkYXl9YCA6IGAke2RheX1gKSBhcyBERDtcbiAgcmV0dXJuIGAtLSR7bW9udGhGb3JtYXR9LSR7ZGF5Rm9ybWF0fWA7XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVUaW1lU2xvdHNGb3JJbnRlcm5hbEF0dGVuZGVlID0gKFxuICBob3N0U3RhcnREYXRlOiBzdHJpbmcsXG4gIGhvc3RJZDogc3RyaW5nLFxuICB1c2VyUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgdXNlclRpbWV6b25lOiBzdHJpbmcsXG4gIGlzRmlyc3REYXk/OiBib29sZWFuXG4pOiBUaW1lU2xvdFR5cGVbXSA9PiB7XG4gIGlmIChpc0ZpcnN0RGF5KSB7XG4gICAgLy8gZmlyc3RkYXkgY2FuIGJlIHN0YXJ0ZWQgb3V0c2lkZSBvZiB3b3JrIHRpbWVcbiAgICAvLyBwcmlvcml0aXplIHdvcmsgc3RhcnQgdGltZSBvdmVyIHdoZW4gaXQgaXMgcHJlc3NlZFxuICAgIC8vIGlmIGZpcnN0RGF5IHN0YXJ0IGlzIGFmdGVyIGVuZCB0aW1lIHJldHVybiBbXVxuICAgIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2UuZW5kVGltZXM7XG4gICAgY29uc3QgZGF5T2ZXZWVrSW50ID0gZ2V0SVNPRGF5KFxuICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgIC50b0RhdGUoKVxuICAgICk7XG4gICAgY29uc3QgZGF5T2ZXZWVrSW50QnlIb3N0ID0gZ2V0SVNPRGF5KFxuICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkudG9EYXRlKClcbiAgICApO1xuICAgIC8vIG1vbnRoIGlzIHplcm8taW5kZXhlZFxuICAgIC8vIGNvbnN0IG1vbnRoID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkudHoodXNlclRpbWV6b25lKS5tb250aCgpXG4gICAgY29uc3QgZGF5T2ZNb250aCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuZGF0ZSgpO1xuICAgIGNvbnN0IHN0YXJ0SG91ciA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKDApLFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICdtaW51dGUnLFxuICAgICAgICAnWyknXG4gICAgICApXG4gICAgICA/IDBcbiAgICAgIDogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDE1XG4gICAgICAgIDogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAubWludXRlKDQ1KSxcbiAgICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICAgIClcbiAgICAgICAgICA/IDMwXG4gICAgICAgICAgOiA0NTtcblxuICAgIC8vIGNvbnZlcnQgdG8gaG9zdCB0aW1lem9uZSBzbyBldmVyeXRoaW5nIGlzIGxpbmtlZCB0byBob3N0IHRpbWV6b25lXG4gICAgY29uc3QgbW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAubW9udGgoKTtcbiAgICBjb25zdCBkYXlPZk1vbnRoQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmRhdGUoKTtcbiAgICBjb25zdCBzdGFydEhvdXJCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkubWludXRlKDApLFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS5taW51dGUoMTUpLFxuICAgICAgICAnbWludXRlJyxcbiAgICAgICAgJ1spJ1xuICAgICAgKVxuICAgICAgPyAwXG4gICAgICA6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgID8gMTVcbiAgICAgICAgOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgICAubWludXRlKDQ1KSxcbiAgICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICAgIClcbiAgICAgICAgICA/IDMwXG4gICAgICAgICAgOiA0NTtcblxuICAgIGNvbnN0IGVuZEhvdXIgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgIGNvbnN0IGVuZE1pbnV0ZSA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG4gICAgY29uc3QgZW5kSG91ckJ5SG9zdCA9IGRheWpzKFxuICAgICAgc2V0SVNPRGF5KFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgLmhvdXIoZW5kSG91cilcbiAgICAgICAgICAudG9EYXRlKCksXG4gICAgICAgIGRheU9mV2Vla0ludFxuICAgICAgKVxuICAgIClcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IGVuZE1pbnV0ZUJ5SG9zdCA9IGRheWpzKFxuICAgICAgc2V0SVNPRGF5KFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGUpXG4gICAgICAgICAgLnRvRGF0ZSgpLFxuICAgICAgICBkYXlPZldlZWtJbnRcbiAgICAgIClcbiAgICApXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLm1pbnV0ZSgpO1xuICAgIC8vIHZhbGlkYXRlIHZhbHVlcyBiZWZvcmUgY2FsY3VsYXRpbmdcbiAgICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2Uuc3RhcnRUaW1lcztcbiAgICBjb25zdCB3b3JrU3RhcnRIb3VyID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZSA9IHN0YXJ0VGltZXMuZmluZChcbiAgICAgIChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50XG4gICAgKS5taW51dGVzO1xuICAgIGNvbnN0IHdvcmtTdGFydEhvdXJCeUhvc3QgPSBkYXlqcyhcbiAgICAgIHNldElTT0RheShcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXIpXG4gICAgICAgICAgLnRvRGF0ZSgpLFxuICAgICAgICBkYXlPZldlZWtJbnRcbiAgICAgIClcbiAgICApXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmhvdXIoKTtcbiAgICBjb25zdCB3b3JrU3RhcnRNaW51dGVCeUhvc3QgPSBkYXlqcyhcbiAgICAgIHNldElTT0RheShcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoZW5kTWludXRlKVxuICAgICAgICAgIC50b0RhdGUoKSxcbiAgICAgICAgZGF5T2ZXZWVrSW50XG4gICAgICApXG4gICAgKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5taW51dGUoKTtcblxuICAgIGlmIChcbiAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuaXNBZnRlcihcbiAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cihlbmRIb3VyQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGVCeUhvc3QpXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIC8vIHJldHVybiBlbXB0eSBhcyBvdXRzaWRlIG9mIHdvcmsgdGltZVxuICAgICAgcmV0dXJuIFtdO1xuICAgIH1cblxuICAgIC8vIGNoYW5nZSB0byB3b3JrIHN0YXJ0IHRpbWUgYXMgYWZ0ZXIgaG9zdCBzdGFydCB0aW1lXG4gICAgaWYgKFxuICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5pc0JlZm9yZShcbiAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICAgIGhvdXJzOiB3b3JrU3RhcnRIb3VyLFxuICAgICAgICBtaW51dGVzOiB3b3JrU3RhcnRNaW51dGUsXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgICBob3VyczogZW5kSG91cixcbiAgICAgICAgbWludXRlczogZW5kTWludXRlLFxuICAgICAgfSk7XG4gICAgICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gICAgICBjb25zdCB0b3RhbE1pbnV0ZXMgPSB0b3RhbER1cmF0aW9uLmFzTWludXRlcygpO1xuICAgICAgY29uc3QgdGltZVNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGhvc3RTdGFydERhdGUsXG4gICAgICAgIGVuZFRpbWVzLFxuICAgICAgICBkYXlPZldlZWtJbnRCeUhvc3QsXG4gICAgICAgIGRheU9mTW9udGgsXG4gICAgICAgIHN0YXJ0SG91cixcbiAgICAgICAgc3RhcnRNaW51dGUsXG4gICAgICAgIGVuZEhvdXIsXG4gICAgICAgIGVuZE1pbnV0ZSxcbiAgICAgICAgdGltZXpvbmUsXG4gICAgICAgIGBzdGFydERhdGUsIGVuZFRpbWVzLCBkYXlPZldlZWtJbnRCeUhvc3QsIGRheU9mTW9udGgsIHN0YXJ0SG91ciwgc3RhcnRNaW51dGUsIGVuZEhvdXIsIGVuZE1pbnV0ZSB0b3RhbE1pbnV0ZXMsIHRpbWV6b25lLCBpbnNpZGUgZmlyc3REYXkgaW5zaWRlIGdlbmVyYXRlVGltZXNsb3RzYFxuICAgICAgKTtcbiAgICAgIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IDE1KSB7XG4gICAgICAgIHRpbWVTbG90cy5wdXNoKHtcbiAgICAgICAgICBkYXlPZldlZWs6IGRheU9mV2Vla0ludFRvU3RyaW5nW2RheU9mV2Vla0ludEJ5SG9zdF0sXG4gICAgICAgICAgc3RhcnRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cihzdGFydEhvdXJCeUhvc3QpXG4gICAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQnlIb3N0KVxuICAgICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgICAgICBlbmRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cihzdGFydEhvdXJCeUhvc3QpXG4gICAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQnlIb3N0KVxuICAgICAgICAgICAgLmFkZChpICsgMTUsICdtaW51dGUnKVxuICAgICAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgICAgIGhvc3RJZCxcbiAgICAgICAgICBtb250aERheTogZm9ybWF0VG9Nb250aERheShcbiAgICAgICAgICAgIG1vbnRoQnlIb3N0IGFzIE1vbnRoVHlwZSxcbiAgICAgICAgICAgIGRheU9mTW9udGhCeUhvc3QgYXMgRGF5VHlwZVxuICAgICAgICAgICksXG4gICAgICAgICAgZGF0ZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERCcpLFxuICAgICAgICB9KTtcbiAgICAgIH1cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICB0aW1lU2xvdHMsXG4gICAgICAgICcgdGltZVNsb3RzIGluc2lkZSBnZW5lcmF0ZVRpbWVTbG90cyBmb3IgZmlyc3QgZGF5IHdoZXJlIHN0YXJ0RGF0ZSBpcyBiZWZvcmUgd29yayBzdGFydCB0aW1lJ1xuICAgICAgKTtcbiAgICAgIHJldHVybiB0aW1lU2xvdHM7XG4gICAgfVxuXG4gICAgY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgIGhvdXJzOiBzdGFydEhvdXIsXG4gICAgICBtaW51dGVzOiBzdGFydE1pbnV0ZSxcbiAgICB9KTtcbiAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHsgaG91cnM6IGVuZEhvdXIsIG1pbnV0ZXM6IGVuZE1pbnV0ZSB9KTtcbiAgICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gICAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcbiAgICBjb25zdCB0aW1lU2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG4gICAgY29uc29sZS5sb2coXG4gICAgICBob3N0U3RhcnREYXRlLFxuICAgICAgZW5kVGltZXMsXG4gICAgICBkYXlPZldlZWtJbnQsXG4gICAgICBkYXlPZk1vbnRoQnlIb3N0LFxuICAgICAgc3RhcnRIb3VyQnlIb3N0LFxuICAgICAgc3RhcnRNaW51dGVCeUhvc3QsXG4gICAgICBlbmRIb3VyQnlIb3N0LFxuICAgICAgZW5kTWludXRlQnlIb3N0LFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgYHN0YXJ0RGF0ZSwgZW5kVGltZXMsIGRheU9mV2Vla0ludCwgZGF5T2ZNb250aCwgc3RhcnRIb3VyLCBzdGFydE1pbnV0ZSwgZW5kSG91ciwgZW5kTWludXRlIHRvdGFsTWludXRlcywgdGltZXpvbmUsIGluc2lkZSBmaXJzdERheSBpbnNpZGUgZ2VuZXJhdGVUaW1lc2xvdHNgXG4gICAgKTtcbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsTWludXRlczsgaSArPSAxNSkge1xuICAgICAgdGltZVNsb3RzLnB1c2goe1xuICAgICAgICBkYXlPZldlZWs6IGRheU9mV2Vla0ludFRvU3RyaW5nW2RheU9mV2Vla0ludF0sXG4gICAgICAgIHN0YXJ0VGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuaG91cihzdGFydEhvdXJCeUhvc3QpXG4gICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgICAuYWRkKGksICdtaW51dGUnKVxuICAgICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgICAgZW5kVGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuaG91cihzdGFydEhvdXJCeUhvc3QpXG4gICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgICAuYWRkKGkgKyAxNSwgJ21pbnV0ZScpXG4gICAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgICBob3N0SWQsXG4gICAgICAgIG1vbnRoRGF5OiBmb3JtYXRUb01vbnRoRGF5KFxuICAgICAgICAgIG1vbnRoQnlIb3N0IGFzIE1vbnRoVHlwZSxcbiAgICAgICAgICBkYXlPZk1vbnRoQnlIb3N0IGFzIERheVR5cGVcbiAgICAgICAgKSxcbiAgICAgICAgZGF0ZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgICB9KTtcbiAgICB9XG4gICAgY29uc29sZS5sb2codGltZVNsb3RzLCAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMgZm9yIGZpcnN0IGRheScpO1xuICAgIHJldHVybiB0aW1lU2xvdHM7XG4gIH1cblxuICAvLyBub3QgZmlyc3QgZGF5IHN0YXJ0IGZyb20gd29yayBzdGFydCB0aW1lIHNjaGVkdWxlXG5cbiAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlLnN0YXJ0VGltZXM7XG4gIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2UuZW5kVGltZXM7XG4gIC8vIGNvbnN0IG1vbnRoID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkudHoodXNlclRpbWV6b25lKS5tb250aCgpXG4gIC8vIGNvbnN0IGRheU9mTW9udGggPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS50eih1c2VyVGltZXpvbmUpLmRhdGUoKVxuICBjb25zdCBkYXlPZldlZWtJbnQgPSBnZXRJU09EYXkoXG4gICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC50b0RhdGUoKVxuICApO1xuICBjb25zdCBzdGFydEhvdXIgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gIGNvbnN0IHN0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuICBjb25zdCBlbmRIb3VyID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgY29uc3QgZW5kTWludXRlID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcblxuICBjb25zdCBtb250aEJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLm1vbnRoKCk7XG4gIGNvbnN0IGRheU9mTW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgIC5kYXRlKCk7XG5cbiAgY29uc3Qgc3RhcnRIb3VyQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHoodXNlclRpbWV6b25lKVxuICAgIC5ob3VyKHN0YXJ0SG91cilcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5ob3VyKCk7XG4gIGNvbnN0IHN0YXJ0TWludXRlQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHoodXNlclRpbWV6b25lKVxuICAgIC5taW51dGUoc3RhcnRNaW51dGUpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAubWludXRlKCk7XG4gIGNvbnN0IGVuZEhvdXJCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgLmhvdXIoZW5kSG91cilcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5ob3VyKCk7XG5cbiAgY29uc29sZS5sb2coXG4gICAgbW9udGhCeUhvc3QsXG4gICAgZGF5T2ZNb250aEJ5SG9zdCxcbiAgICBzdGFydEhvdXJCeUhvc3QsXG4gICAgc3RhcnRNaW51dGVCeUhvc3QsXG4gICAgZW5kSG91ckJ5SG9zdCxcbiAgICAnIG1vbnRoQnlIb3N0LCBkYXlPZk1vbnRoQnlIb3N0LCBzdGFydEhvdXJCeUhvc3QsIHN0YXJ0TWludXRlQnlIb3N0LCBlbmRIb3VyQnlIb3N0J1xuICApO1xuICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiBzdGFydEhvdXIsXG4gICAgbWludXRlczogc3RhcnRNaW51dGUsXG4gIH0pO1xuICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHsgaG91cnM6IGVuZEhvdXIsIG1pbnV0ZXM6IGVuZE1pbnV0ZSB9KTtcbiAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICBjb25zdCB0b3RhbE1pbnV0ZXMgPSB0b3RhbER1cmF0aW9uLmFzTWludXRlcygpO1xuICBjb25zdCB0aW1lU2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG4gIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IDE1KSB7XG4gICAgdGltZVNsb3RzLnB1c2goe1xuICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1tkYXlPZldlZWtJbnRdLFxuICAgICAgc3RhcnRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQnlIb3N0KVxuICAgICAgICAuYWRkKGksICdtaW51dGUnKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICBlbmRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQnlIb3N0KVxuICAgICAgICAuYWRkKGkgKyAxNSwgJ21pbnV0ZScpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgIGhvc3RJZCxcbiAgICAgIG1vbnRoRGF5OiBmb3JtYXRUb01vbnRoRGF5KFxuICAgICAgICBtb250aEJ5SG9zdCBhcyBNb250aFR5cGUsXG4gICAgICAgIGRheU9mTW9udGhCeUhvc3QgYXMgRGF5VHlwZVxuICAgICAgKSxcbiAgICAgIGRhdGU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgfSk7XG4gIH1cbiAgY29uc29sZS5sb2codGltZVNsb3RzLCAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMnKTtcbiAgcmV0dXJuIHRpbWVTbG90cztcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZVRpbWVTbG90c0xpdGVGb3JJbnRlcm5hbEF0dGVuZGVlID0gKFxuICBob3N0U3RhcnREYXRlOiBzdHJpbmcsXG4gIGhvc3RJZDogc3RyaW5nLFxuICB1c2VyUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgdXNlclRpbWV6b25lOiBzdHJpbmcsXG4gIGlzRmlyc3REYXk/OiBib29sZWFuXG4pOiBUaW1lU2xvdFR5cGVbXSA9PiB7XG4gIGlmIChpc0ZpcnN0RGF5KSB7XG4gICAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZS5lbmRUaW1lcztcblxuICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICAgKTtcblxuICAgIGNvbnN0IHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLm1pbnV0ZSgwKSxcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkubWludXRlKDMwKSxcbiAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICdbKSdcbiAgICAgIClcbiAgICAgID8gMFxuICAgICAgOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoNTkpLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDMwXG4gICAgICAgIDogMDtcblxuICAgIC8vIGNvbnZlcnQgdG8gaG9zdCB0aW1lem9uZSBzbyBldmVyeXRoaW5nIGlzIGxpbmtlZCB0byBob3N0IHRpbWV6b25lXG4gICAgY29uc3QgbW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAubW9udGgoKTtcbiAgICBjb25zdCBkYXlPZk1vbnRoQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmRhdGUoKTtcbiAgICBjb25zdCBzdGFydEhvdXJCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkubWludXRlKDApLFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS5taW51dGUoMzApLFxuICAgICAgICAnbWludXRlJyxcbiAgICAgICAgJ1spJ1xuICAgICAgKVxuICAgICAgPyAwXG4gICAgICA6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSg1OSksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgID8gMzBcbiAgICAgICAgOiAwO1xuXG4gICAgY29uc3QgZW5kSG91ciA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gICAgY29uc3QgZW5kTWludXRlID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcbiAgICBjb25zdCBlbmRIb3VyQnlIb3N0ID0gZGF5anMoXG4gICAgICBzZXRJU09EYXkoXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAuaG91cihlbmRIb3VyKVxuICAgICAgICAgIC50b0RhdGUoKSxcbiAgICAgICAgZGF5T2ZXZWVrSW50XG4gICAgICApXG4gICAgKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgY29uc3QgZW5kTWludXRlQnlIb3N0ID0gZGF5anMoXG4gICAgICBzZXRJU09EYXkoXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZSlcbiAgICAgICAgICAudG9EYXRlKCksXG4gICAgICAgIGRheU9mV2Vla0ludFxuICAgICAgKVxuICAgIClcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAubWludXRlKCk7XG5cbiAgICAvLyB2YWxpZGF0ZSB2YWx1ZXMgYmVmb3JlIGNhbGN1bGF0aW5nXG4gICAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlLnN0YXJ0VGltZXM7XG4gICAgY29uc3Qgd29ya1N0YXJ0SG91ciA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgICBjb25zdCB3b3JrU3RhcnRNaW51dGUgPSBzdGFydFRpbWVzLmZpbmQoXG4gICAgICAoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludFxuICAgICkubWludXRlcztcbiAgICBjb25zdCB3b3JrU3RhcnRIb3VyQnlIb3N0ID0gZGF5anMoXG4gICAgICBzZXRJU09EYXkoXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyKVxuICAgICAgICAgIC50b0RhdGUoKSxcbiAgICAgICAgZGF5T2ZXZWVrSW50XG4gICAgICApXG4gICAgKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgY29uc3Qgd29ya1N0YXJ0TWludXRlQnlIb3N0ID0gZGF5anMoXG4gICAgICBzZXRJU09EYXkoXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZSlcbiAgICAgICAgICAudG9EYXRlKCksXG4gICAgICAgIGRheU9mV2Vla0ludFxuICAgICAgKVxuICAgIClcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAubWludXRlKCk7XG5cbiAgICBpZiAoXG4gICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmlzQWZ0ZXIoXG4gICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmhvdXIoZW5kSG91ckJ5SG9zdClcbiAgICAgICAgICAgIC5taW51dGUoZW5kTWludXRlQnlIb3N0KVxuICAgICAgICApXG4gICAgKSB7XG4gICAgICAvLyByZXR1cm4gZW1wdHkgYXMgb3V0c2lkZSBvZiB3b3JrIHRpbWVcbiAgICAgIHJldHVybiBbXTtcbiAgICB9XG5cbiAgICAvLyBjaGFuZ2UgdG8gd29yayBzdGFydCB0aW1lIGFzIGJlZm9yZSBzdGFydCB0aW1lXG4gICAgaWYgKFxuICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5pc0JlZm9yZShcbiAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICAgIGhvdXJzOiB3b3JrU3RhcnRIb3VyLFxuICAgICAgICBtaW51dGVzOiB3b3JrU3RhcnRNaW51dGUsXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgICBob3VyczogZW5kSG91cixcbiAgICAgICAgbWludXRlczogZW5kTWludXRlLFxuICAgICAgfSk7XG4gICAgICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gICAgICBjb25zdCB0b3RhbE1pbnV0ZXMgPSB0b3RhbER1cmF0aW9uLmFzTWludXRlcygpO1xuICAgICAgY29uc3QgdGltZVNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gMzApIHtcbiAgICAgICAgdGltZVNsb3RzLnB1c2goe1xuICAgICAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50XSxcbiAgICAgICAgICBzdGFydFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgICAuYWRkKGksICdtaW51dGUnKVxuICAgICAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgICAuYWRkKGkgKyAzMCwgJ21pbnV0ZScpXG4gICAgICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICAgICAgaG9zdElkLFxuICAgICAgICAgIG1vbnRoRGF5OiBmb3JtYXRUb01vbnRoRGF5KFxuICAgICAgICAgICAgbW9udGhCeUhvc3QgYXMgTW9udGhUeXBlLFxuICAgICAgICAgICAgZGF5T2ZNb250aEJ5SG9zdCBhcyBEYXlUeXBlXG4gICAgICAgICAgKSxcbiAgICAgICAgICBkYXRlOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgICAgIH0pO1xuICAgICAgfVxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIHRpbWVTbG90cyxcbiAgICAgICAgJyB0aW1lU2xvdHMgaW5zaWRlIGdlbmVyYXRlVGltZVNsb3RzIGZvciBmaXJzdCBkYXkgYmVmb3JlIHN0YXJ0IHRpbWUnXG4gICAgICApO1xuICAgICAgcmV0dXJuIHRpbWVTbG90cztcbiAgICB9XG5cbiAgICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgaG91cnM6IHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QsXG4gICAgICBtaW51dGVzOiBzdGFydE1pbnV0ZU9mSG9zdERhdGVCeUhvc3QsXG4gICAgfSk7XG4gICAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7IGhvdXJzOiBlbmRIb3VyLCBtaW51dGVzOiBlbmRNaW51dGUgfSk7XG4gICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG4gICAgY29uc3QgdGltZVNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IDMwKSB7XG4gICAgICB0aW1lU2xvdHMucHVzaCh7XG4gICAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50XSxcbiAgICAgICAgc3RhcnRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQnlIb3N0KVxuICAgICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgICBlbmRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQnlIb3N0KVxuICAgICAgICAgIC5hZGQoaSArIDMwLCAnbWludXRlJylcbiAgICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICAgIGhvc3RJZCxcbiAgICAgICAgbW9udGhEYXk6IGZvcm1hdFRvTW9udGhEYXkoXG4gICAgICAgICAgbW9udGhCeUhvc3QgYXMgTW9udGhUeXBlLFxuICAgICAgICAgIGRheU9mTW9udGhCeUhvc3QgYXMgRGF5VHlwZVxuICAgICAgICApLFxuICAgICAgICBkYXRlOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICAgIH0pO1xuICAgIH1cbiAgICBjb25zb2xlLmxvZyh0aW1lU2xvdHMsICcgdGltZVNsb3RzIGluc2lkZSBnZW5lcmF0ZVRpbWVTbG90cyBmb3IgZmlyc3QgZGF5Jyk7XG4gICAgcmV0dXJuIHRpbWVTbG90cztcbiAgfVxuICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2Uuc3RhcnRUaW1lcztcbiAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZS5lbmRUaW1lcztcbiAgLy8gY29uc3QgbW9udGggPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS50eih1c2VyVGltZXpvbmUpLm1vbnRoKClcbiAgLy8gY29uc3QgZGF5T2ZNb250aCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnR6KHVzZXJUaW1lem9uZSkuZGF0ZSgpXG4gIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLnRvRGF0ZSgpXG4gICk7XG4gIGNvbnN0IHN0YXJ0SG91ciA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgY29uc3Qgc3RhcnRNaW51dGUgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG4gIGNvbnN0IGVuZEhvdXIgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICBjb25zdCBlbmRNaW51dGUgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuXG4gIGNvbnN0IG1vbnRoQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAubW9udGgoKTtcbiAgY29uc3QgZGF5T2ZNb250aEJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLmRhdGUoKTtcbiAgY29uc3QgZGF5T2ZXZWVrSW50QnlIb3N0ID0gZ2V0SVNPRGF5KFxuICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICk7XG4gIGNvbnN0IHN0YXJ0SG91ckJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAuaG91cihzdGFydEhvdXIpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAuaG91cigpO1xuICBjb25zdCBzdGFydE1pbnV0ZUJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAubWludXRlKHN0YXJ0TWludXRlKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLm1pbnV0ZSgpO1xuICAvLyBjb25zdCBlbmRIb3VyQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkudHoodXNlclRpbWV6b25lKS5ob3VyKGVuZEhvdXIpLnR6KGhvc3RUaW1lem9uZSkuaG91cigpXG5cbiAgY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICBob3Vyczogc3RhcnRIb3VyLFxuICAgIG1pbnV0ZXM6IHN0YXJ0TWludXRlLFxuICB9KTtcbiAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7IGhvdXJzOiBlbmRIb3VyLCBtaW51dGVzOiBlbmRNaW51dGUgfSk7XG4gIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcbiAgY29uc3QgdGltZVNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsTWludXRlczsgaSArPSAzMCkge1xuICAgIHRpbWVTbG90cy5wdXNoKHtcbiAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50QnlIb3N0XSxcbiAgICAgIHN0YXJ0VGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgZW5kVGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgLmFkZChpICsgMzAsICdtaW51dGUnKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICBob3N0SWQsXG4gICAgICBtb250aERheTogZm9ybWF0VG9Nb250aERheShcbiAgICAgICAgbW9udGhCeUhvc3QgYXMgTW9udGhUeXBlLFxuICAgICAgICBkYXlPZk1vbnRoQnlIb3N0IGFzIERheVR5cGVcbiAgICAgICksXG4gICAgICBkYXRlOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERCcpLFxuICAgIH0pO1xuICB9XG4gIGNvbnNvbGUubG9nKHRpbWVTbG90cywgJyB0aW1lU2xvdHMgaW5zaWRlIGdlbmVyYXRlVGltZVNsb3RzJyk7XG4gIHJldHVybiB0aW1lU2xvdHM7XG59O1xuXG5leHBvcnQgY29uc3QgdmFsaWRhdGVFdmVudERhdGVzID0gKFxuICBldmVudDogRXZlbnRQbHVzVHlwZSxcbiAgdXNlclByZWZlcmVuY2VzOiBVc2VyUHJlZmVyZW5jZVR5cGVcbik6IGJvb2xlYW4gPT4ge1xuICAvLyBpZiBubyB0aW1lem9uZSByZW1vdmVcbiAgaWYgKCFldmVudD8udGltZXpvbmUpIHtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICBjb25zdCBkaWZmID0gZGF5anMoZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgIC5kaWZmKGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKSwgJ20nKTtcbiAgY29uc3QgZGlmZkRheSA9IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAuZGlmZihkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihldmVudC50aW1lem9uZSwgdHJ1ZSksICdkJyk7XG4gIGNvbnN0IGRpZmZIb3VycyA9IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAuZGlmZihkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihldmVudC50aW1lem9uZSwgdHJ1ZSksICdoJyk7XG5cbiAgY29uc3QgaXNvV2Vla0RheSA9IGdldElTT0RheShcbiAgICBkYXlqcyhldmVudD8uc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooZXZlbnQ/LnRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICApO1xuICBjb25zdCBlbmRIb3VyID0gdXNlclByZWZlcmVuY2VzLmVuZFRpbWVzLmZpbmQoXG4gICAgKGUpID0+IGU/LmRheSA9PT0gaXNvV2Vla0RheVxuICApPy5ob3VyO1xuICBjb25zdCBlbmRNaW51dGVzID0gdXNlclByZWZlcmVuY2VzLmVuZFRpbWVzLmZpbmQoXG4gICAgKGUpID0+IGU/LmRheSA9PT0gaXNvV2Vla0RheVxuICApPy5taW51dGVzO1xuICBjb25zdCBzdGFydEhvdXIgPSB1c2VyUHJlZmVyZW5jZXMuc3RhcnRUaW1lcy5maW5kKFxuICAgIChlKSA9PiBlPy5kYXkgPT09IGlzb1dlZWtEYXlcbiAgKT8uaG91cjtcbiAgY29uc3Qgc3RhcnRNaW51dGVzID0gdXNlclByZWZlcmVuY2VzLnN0YXJ0VGltZXMuZmluZChcbiAgICAoZSkgPT4gZT8uZGF5ID09PSBpc29XZWVrRGF5XG4gICk/Lm1pbnV0ZXM7XG5cbiAgaWYgKFxuICAgIGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAuaXNBZnRlcihcbiAgICAgICAgZGF5anMoZXZlbnQ/LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGVzKVxuICAgICAgKVxuICApIHtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICBpZiAoXG4gICAgZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5pc0JlZm9yZShcbiAgICAgICAgZGF5anMoZXZlbnQ/LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91cilcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlcylcbiAgICAgIClcbiAgKSB7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgaWYgKGRpZmYgPT09IDApIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGV2ZW50LmlkLFxuICAgICAgZXZlbnQuc3RhcnREYXRlLFxuICAgICAgZXZlbnQuZW5kRGF0ZSxcbiAgICAgICcgdGhlIHN0YXJ0IGRhdGUgYW5kIGVuZCBkYXRlIGFyZSB0aGUgc2FtZSdcbiAgICApO1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuXG4gIGlmIChkaWZmIDwgMCkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZXZlbnQuaWQsXG4gICAgICBldmVudC5zdGFydERhdGUsXG4gICAgICBldmVudC5lbmREYXRlLFxuICAgICAgJyB0aGUgc3RhcnQgZGF0ZSBpcyBhZnRlciBlbmQgZGF0ZSdcbiAgICApO1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuXG4gIGlmIChkaWZmRGF5ID49IDEpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGV2ZW50LmlkLFxuICAgICAgZXZlbnQuc3RhcnREYXRlLFxuICAgICAgZXZlbnQuZW5kRGF0ZSxcbiAgICAgICcgdGhlIHN0YXJ0IGRhdGUgYW5kIGVuZCBkYXRlIGFyZSBtb3JlIHRoYW4gMSBkYXkgYXBhcnQnXG4gICAgKTtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICAvLyBpZiBkaWZmZXJlbmNlIGluIGhvdXJzID4gMjMgbGlrZWx5IGFsbCBkYXkgZXZlbnRcbiAgaWYgKGRpZmZIb3VycyA+IDIzKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBldmVudC5pZCxcbiAgICAgIGV2ZW50LnN0YXJ0RGF0ZSxcbiAgICAgIGV2ZW50LmVuZERhdGUsXG4gICAgICAnIHRoZSBzdGFydCBkYXRlIGFuZCBlbmQgZGF0ZSBhcmUgbW9yZSB0aGFuIDIzIGhvdXJzIGFwYXJ0J1xuICAgICk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgcmV0dXJuIHRydWU7XG59O1xuXG5leHBvcnQgY29uc3QgdmFsaWRhdGVFdmVudERhdGVzRm9yRXh0ZXJuYWxBdHRlbmRlZSA9IChcbiAgZXZlbnQ6IEV2ZW50UGx1c1R5cGVcbik6IGJvb2xlYW4gPT4ge1xuICAvLyBpZiBubyB0aW1lem9uZSByZW1vdmVcbiAgaWYgKCFldmVudD8udGltZXpvbmUpIHtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICBjb25zdCBkaWZmID0gZGF5anMoZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgIC5kaWZmKGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKSwgJ20nKTtcbiAgY29uc3QgZGlmZkRheSA9IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAuZGlmZihkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihldmVudC50aW1lem9uZSwgdHJ1ZSksICdkJyk7XG4gIGNvbnN0IGRpZmZIb3VycyA9IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAuZGlmZihkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihldmVudC50aW1lem9uZSwgdHJ1ZSksICdoJyk7XG5cbiAgaWYgKGRpZmYgPT09IDApIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGV2ZW50LmlkLFxuICAgICAgZXZlbnQuc3RhcnREYXRlLFxuICAgICAgZXZlbnQuZW5kRGF0ZSxcbiAgICAgICcgdGhlIHN0YXJ0IGRhdGUgYW5kIGVuZCBkYXRlIGFyZSB0aGUgc2FtZSdcbiAgICApO1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuXG4gIGlmIChkaWZmIDwgMCkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZXZlbnQuaWQsXG4gICAgICBldmVudC5zdGFydERhdGUsXG4gICAgICBldmVudC5lbmREYXRlLFxuICAgICAgJyB0aGUgc3RhcnQgZGF0ZSBpcyBhZnRlciBlbmQgZGF0ZSdcbiAgICApO1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuXG4gIGlmIChkaWZmRGF5ID49IDEpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGV2ZW50LmlkLFxuICAgICAgZXZlbnQuc3RhcnREYXRlLFxuICAgICAgZXZlbnQuZW5kRGF0ZSxcbiAgICAgICcgdGhlIHN0YXJ0IGRhdGUgYW5kIGVuZCBkYXRlIGFyZSBtb3JlIHRoYW4gMSBkYXkgYXBhcnQnXG4gICAgKTtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICAvLyBpZiBkaWZmZXJlbmNlIGluIGhvdXJzID4gMjMgbGlrZWx5IGFsbCBkYXkgZXZlbnRcbiAgaWYgKGRpZmZIb3VycyA+IDIzKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBldmVudC5pZCxcbiAgICAgIGV2ZW50LnN0YXJ0RGF0ZSxcbiAgICAgIGV2ZW50LmVuZERhdGUsXG4gICAgICAnIHRoZSBzdGFydCBkYXRlIGFuZCBlbmQgZGF0ZSBhcmUgbW9yZSB0aGFuIDIzIGhvdXJzIGFwYXJ0J1xuICAgICk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgcmV0dXJuIHRydWU7XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVFdmVudFBhcnRzID0gKFxuICBldmVudDogRXZlbnRQbHVzVHlwZSxcbiAgaG9zdElkOiBzdHJpbmdcbik6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPT4ge1xuICBjb25zb2xlLmxvZyhcbiAgICBldmVudC5pZCxcbiAgICBldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpLFxuICAgIGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpLFxuICAgICcgZXZlbnQuaWQsIGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSksIGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpIGluc2lkZSBnZW5lcmF0ZUV2ZW50UGFydHMnXG4gICk7XG4gIGNvbnN0IG1pbnV0ZXMgPSBkYXlqcyhldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgLmRpZmYoZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooZXZlbnQudGltZXpvbmUsIHRydWUpLCAnbScpO1xuICBjb25zb2xlLmxvZyhcbiAgICBldmVudC5pZCxcbiAgICBtaW51dGVzLFxuICAgICdldmVudC5pZCwgIG1pbnV0ZXMgaW5zaWRlIGdlbmVyYXRlRXZlbnRQYXJ0cydcbiAgKTtcbiAgY29uc3QgcGFydHMgPSBNYXRoLmZsb29yKG1pbnV0ZXMgLyAxNSk7XG4gIGNvbnN0IHJlbWFpbmRlciA9IG1pbnV0ZXMgJSAxNTtcbiAgY29uc3QgZXZlbnRQYXJ0czogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSA9IFtdO1xuICBmb3IgKGxldCBpID0gMDsgaSA8IHBhcnRzOyBpKyspIHtcbiAgICBldmVudFBhcnRzLnB1c2goe1xuICAgICAgLi4uZXZlbnQsXG4gICAgICBncm91cElkOiBldmVudC5pZCxcbiAgICAgIGV2ZW50SWQ6IGV2ZW50LmlkLFxuICAgICAgc3RhcnREYXRlOiBldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpLFxuICAgICAgZW5kRGF0ZTogZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSksXG4gICAgICBwYXJ0OiBpICsgMSxcbiAgICAgIGxhc3RQYXJ0OiByZW1haW5kZXIgPiAwID8gcGFydHMgKyAxIDogcGFydHMsXG4gICAgICBtZWV0aW5nUGFydDogaSArIDEsXG4gICAgICBtZWV0aW5nTGFzdFBhcnQ6IHJlbWFpbmRlciA+IDAgPyBwYXJ0cyArIDEgOiBwYXJ0cyxcbiAgICAgIGhvc3RJZCxcbiAgICB9KTtcbiAgfVxuXG4gIGlmIChyZW1haW5kZXIgPiAwKSB7XG4gICAgZXZlbnRQYXJ0cy5wdXNoKHtcbiAgICAgIC4uLmV2ZW50LFxuICAgICAgZ3JvdXBJZDogZXZlbnQuaWQsXG4gICAgICBldmVudElkOiBldmVudC5pZCxcbiAgICAgIHN0YXJ0RGF0ZTogZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSxcbiAgICAgIGVuZERhdGU6IGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpLFxuICAgICAgcGFydDogcGFydHMgKyAxLFxuICAgICAgbGFzdFBhcnQ6IHBhcnRzICsgMSxcbiAgICAgIG1lZXRpbmdQYXJ0OiBwYXJ0cyArIDEsXG4gICAgICBtZWV0aW5nTGFzdFBhcnQ6IHBhcnRzICsgMSxcbiAgICAgIGhvc3RJZCxcbiAgICB9KTtcbiAgfVxuICBjb25zb2xlLmxvZyhcbiAgICBldmVudC5pZCxcbiAgICBldmVudFBhcnRzPy5bMF0/LnN0YXJ0RGF0ZSxcbiAgICBldmVudFBhcnRzPy5bMF0/LmVuZERhdGUsXG4gICAgZXZlbnRQYXJ0cz8uWzBdPy5wYXJ0LFxuICAgIGV2ZW50UGFydHM/LlswXT8ubGFzdFBhcnQsXG4gICAgJ2V2ZW50LmlkLCAgZXZlbnRQYXJ0cz8uWzBdPy5zdGFydERhdGUsIGV2ZW50UGFydHM/LlswXT8uZW5kRGF0ZSwgZXZlbnRQYXJ0cz8uWzBdPy5wYXJ0LCBldmVudFBhcnRzPy5bMF0/Lmxhc3RQYXJ0LCdcbiAgKTtcbiAgcmV0dXJuIGV2ZW50UGFydHM7XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVFdmVudFBhcnRzTGl0ZSA9IChcbiAgZXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIGhvc3RJZDogc3RyaW5nXG4pOiBJbml0aWFsRXZlbnRQYXJ0VHlwZVtdID0+IHtcbiAgY29uc3QgbWludXRlcyA9IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAuZGlmZihkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihldmVudC50aW1lem9uZSwgdHJ1ZSksICdtJyk7XG4gIGNvbnN0IHBhcnRzID0gTWF0aC5mbG9vcihtaW51dGVzIC8gMzApO1xuICBjb25zdCByZW1haW5kZXIgPSBtaW51dGVzICUgMzA7XG4gIGNvbnN0IGV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPSBbXTtcbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBwYXJ0czsgaSsrKSB7XG4gICAgZXZlbnRQYXJ0cy5wdXNoKHtcbiAgICAgIC4uLmV2ZW50LFxuICAgICAgZ3JvdXBJZDogZXZlbnQuaWQsXG4gICAgICBldmVudElkOiBldmVudC5pZCxcbiAgICAgIHN0YXJ0RGF0ZTogZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSxcbiAgICAgIGVuZERhdGU6IGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpLFxuICAgICAgcGFydDogaSArIDEsXG4gICAgICBsYXN0UGFydDogcmVtYWluZGVyID4gMCA/IHBhcnRzICsgMSA6IHBhcnRzLFxuICAgICAgbWVldGluZ1BhcnQ6IGkgKyAxLFxuICAgICAgbWVldGluZ0xhc3RQYXJ0OiByZW1haW5kZXIgPiAwID8gcGFydHMgKyAxIDogcGFydHMsXG4gICAgICBob3N0SWQsXG4gICAgfSk7XG4gIH1cblxuICBpZiAocmVtYWluZGVyID4gMCkge1xuICAgIGV2ZW50UGFydHMucHVzaCh7XG4gICAgICAuLi5ldmVudCxcbiAgICAgIGdyb3VwSWQ6IGV2ZW50LmlkLFxuICAgICAgZXZlbnRJZDogZXZlbnQuaWQsXG4gICAgICBzdGFydERhdGU6IGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSksXG4gICAgICBlbmREYXRlOiBldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSxcbiAgICAgIHBhcnQ6IHBhcnRzICsgMSxcbiAgICAgIGxhc3RQYXJ0OiBwYXJ0cyArIDEsXG4gICAgICBtZWV0aW5nUGFydDogcGFydHMgKyAxLFxuICAgICAgbWVldGluZ0xhc3RQYXJ0OiBwYXJ0cyArIDEsXG4gICAgICBob3N0SWQsXG4gICAgfSk7XG4gIH1cbiAgY29uc29sZS5sb2coXG4gICAgZXZlbnQuaWQsXG4gICAgZXZlbnRQYXJ0cz8uWzBdPy5zdGFydERhdGUsXG4gICAgZXZlbnRQYXJ0cz8uWzBdPy5lbmREYXRlLFxuICAgIGV2ZW50UGFydHM/LlswXT8ucGFydCxcbiAgICBldmVudFBhcnRzPy5bMF0/Lmxhc3RQYXJ0LFxuICAgICdldmVudC5pZCwgIGV2ZW50UGFydHM/LlswXT8uc3RhcnREYXRlLCBldmVudFBhcnRzPy5bMF0/LmVuZERhdGUsIGV2ZW50UGFydHM/LlswXT8ucGFydCwgZXZlbnRQYXJ0cz8uWzBdPy5sYXN0UGFydCwnXG4gICk7XG5cbiAgcmV0dXJuIGV2ZW50UGFydHM7XG59O1xuXG5leHBvcnQgY29uc3QgbW9kaWZ5RXZlbnRQYXJ0c0ZvclNpbmd1bGFyUHJlQnVmZmVyVGltZSA9IChcbiAgZXZlbnRQYXJ0czogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSxcbiAgZm9yRXZlbnRJZDogc3RyaW5nXG4pOiBJbml0aWFsRXZlbnRQYXJ0VHlwZVtdID0+IHtcbiAgY29uc3QgcHJlQnVmZmVyQmVmb3JlRXZlbnRQYXJ0czogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSA9IFtdO1xuICBjb25zdCBwcmVCdWZmZXJBY3R1YWxFdmVudFBhcnRzOiBJbml0aWFsRXZlbnRQYXJ0VHlwZVtdID0gW107XG5cbiAgY29uc3QgcHJlQnVmZmVyR3JvdXBJZCA9IHV1aWQoKTtcblxuICBmb3IgKGxldCBpID0gMDsgaSA8IGV2ZW50UGFydHMubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAoZXZlbnRQYXJ0c1tpXS5mb3JFdmVudElkID09PSBmb3JFdmVudElkICYmIGV2ZW50UGFydHNbaV0uaXNQcmVFdmVudCkge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGV2ZW50UGFydHNbaV0uZm9yRXZlbnRJZCxcbiAgICAgICAgZm9yRXZlbnRJZCxcbiAgICAgICAgJyBldmVudFBhcnRzW2ldLmZvckV2ZW50SWQgPT09IGZvckV2ZW50SWQgIGluc2lkZSBtb2RpZnlFdmVudFBhcnRzRm9yU2luZ3VsYXJQcmVCdWZmZXJUaW1lJ1xuICAgICAgKTtcbiAgICAgIHByZUJ1ZmZlckJlZm9yZUV2ZW50UGFydHMucHVzaCh7XG4gICAgICAgIC4uLmV2ZW50UGFydHNbaV0sXG4gICAgICAgIGdyb3VwSWQ6IHByZUJ1ZmZlckdyb3VwSWQsXG4gICAgICB9KTtcbiAgICB9XG4gIH1cblxuICBmb3IgKGxldCBpID0gMDsgaSA8IGV2ZW50UGFydHMubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAoZXZlbnRQYXJ0c1tpXS5pZCA9PT0gZm9yRXZlbnRJZCkge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGV2ZW50UGFydHNbaV0uaWQsXG4gICAgICAgIGZvckV2ZW50SWQsXG4gICAgICAgICdldmVudFBhcnRzW2ldLmlkID09PSBmb3JFdmVudElkIGluc2lkZSBtb2RpZnlFdmVudFBhcnRzRm9yU2luZ3VsYXJQcmVCdWZmZXJUaW1lJ1xuICAgICAgKTtcbiAgICAgIHByZUJ1ZmZlckFjdHVhbEV2ZW50UGFydHMucHVzaCh7XG4gICAgICAgIC4uLmV2ZW50UGFydHNbaV0sXG4gICAgICAgIGdyb3VwSWQ6IHByZUJ1ZmZlckdyb3VwSWQsXG4gICAgICB9KTtcbiAgICB9XG4gIH1cblxuICBjb25zdCBwcmVCdWZmZXJCZWZvcmVFdmVudFBhcnRzU29ydGVkID0gcHJlQnVmZmVyQmVmb3JlRXZlbnRQYXJ0cy5zb3J0KFxuICAgIChhLCBiKSA9PiBhLnBhcnQgLSBiLnBhcnRcbiAgKTtcbiAgY29uc3QgcHJlQnVmZmVyQWN0dWFsRXZlbnRQYXJ0c1NvcnRlZCA9IHByZUJ1ZmZlckFjdHVhbEV2ZW50UGFydHMuc29ydChcbiAgICAoYSwgYikgPT4gYS5wYXJ0IC0gYi5wYXJ0XG4gICk7XG5cbiAgY29uc3QgcHJlQnVmZmVyRXZlbnRQYXJ0c1RvdGFsID0gcHJlQnVmZmVyQmVmb3JlRXZlbnRQYXJ0c1NvcnRlZC5jb25jYXQoXG4gICAgcHJlQnVmZmVyQWN0dWFsRXZlbnRQYXJ0c1NvcnRlZFxuICApO1xuXG4gIGZvciAobGV0IGkgPSAwOyBpIDwgcHJlQnVmZmVyRXZlbnRQYXJ0c1RvdGFsLmxlbmd0aDsgaSsrKSB7XG4gICAgcHJlQnVmZmVyRXZlbnRQYXJ0c1RvdGFsW2ldLnBhcnQgPSBpICsgMTtcbiAgICBwcmVCdWZmZXJFdmVudFBhcnRzVG90YWxbaV0ubGFzdFBhcnQgPSBwcmVCdWZmZXJFdmVudFBhcnRzVG90YWwubGVuZ3RoO1xuICB9XG4gIHByZUJ1ZmZlckV2ZW50UGFydHNUb3RhbC5mb3JFYWNoKChlKSA9PlxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZS5pZCxcbiAgICAgIGUuZ3JvdXBJZCxcbiAgICAgIGUuZXZlbnRJZCxcbiAgICAgIGUucGFydCxcbiAgICAgIGUubGFzdFBhcnQsXG4gICAgICBlLnN0YXJ0RGF0ZSxcbiAgICAgIGUuZW5kRGF0ZSxcbiAgICAgIGBlLmlkLCBlLmdyb3VwSWQsIGUuZXZlbnRJZCwgZS5wYXJ0LCBlLmxhc3RQYXJ0LCBlLnN0YXJ0RGF0ZSwgZS5lbmREYXRlLCBpbnNpZGUgbW9kaWZ5RXZlbnRQYXJ0c0ZvclNpbmd1bGFyUHJlQnVmZmVyVGltZWBcbiAgICApXG4gICk7XG4gIHJldHVybiBwcmVCdWZmZXJFdmVudFBhcnRzVG90YWw7XG59O1xuZXhwb3J0IGNvbnN0IG1vZGlmeUV2ZW50UGFydHNGb3JNdWx0aXBsZVByZUJ1ZmZlclRpbWUgPSAoXG4gIGV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW11cbik6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPT4ge1xuICBjb25zdCB1bmlxdWVQcmVCdWZmZXJQYXJ0Rm9yRXZlbnRJZHM6IHN0cmluZ1tdID0gW107XG4gIGNvbnN0IHByZUJ1ZmZlckV2ZW50UGFydHNUb3RhbDogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSA9IFtdO1xuXG4gIGZvciAobGV0IGkgPSAwOyBpIDwgZXZlbnRQYXJ0cy5sZW5ndGg7IGkrKykge1xuICAgIGlmIChldmVudFBhcnRzW2ldLmZvckV2ZW50SWQgJiYgZXZlbnRQYXJ0c1tpXS5pc1ByZUV2ZW50KSB7XG4gICAgICBjb25zdCBmb3VuZFBhcnQgPSB1bmlxdWVQcmVCdWZmZXJQYXJ0Rm9yRXZlbnRJZHMuZmluZChcbiAgICAgICAgKGUpID0+IGUgPT09IGV2ZW50UGFydHNbaV0uZm9yRXZlbnRJZFxuICAgICAgKTtcbiAgICAgIC8vIGlmIGZvdW5kIHNraXBcbiAgICAgIGlmIChmb3VuZFBhcnQpIHtcbiAgICAgICAgY29udGludWU7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICB1bmlxdWVQcmVCdWZmZXJQYXJ0Rm9yRXZlbnRJZHMucHVzaChldmVudFBhcnRzW2ldLmZvckV2ZW50SWQpO1xuICAgICAgfVxuICAgIH1cbiAgfVxuXG4gIC8vIGZpbGwgdXAgcHJlQnVmZmVyRXZlbnRQYXJ0c1RvdGFsXG4gIGZvciAobGV0IGkgPSAwOyBpIDwgdW5pcXVlUHJlQnVmZmVyUGFydEZvckV2ZW50SWRzLmxlbmd0aDsgaSsrKSB7XG4gICAgY29uc3QgcmV0dXJuZWRFdmVudFBhcnRUb3RhbCA9IG1vZGlmeUV2ZW50UGFydHNGb3JTaW5ndWxhclByZUJ1ZmZlclRpbWUoXG4gICAgICBldmVudFBhcnRzLFxuICAgICAgdW5pcXVlUHJlQnVmZmVyUGFydEZvckV2ZW50SWRzW2ldXG4gICAgKTtcbiAgICBwcmVCdWZmZXJFdmVudFBhcnRzVG90YWwucHVzaCguLi5yZXR1cm5lZEV2ZW50UGFydFRvdGFsKTtcbiAgfVxuXG4gIC8vIHJlbW92ZSBvbGQgdmFsdWVzXG4gIGNvbnN0IGV2ZW50UGFydHNGaWx0ZXJlZCA9IF8uZGlmZmVyZW5jZUJ5KFxuICAgIGV2ZW50UGFydHMsXG4gICAgcHJlQnVmZmVyRXZlbnRQYXJ0c1RvdGFsLFxuICAgICdpZCdcbiAgKTtcbiAgY29uc3QgY29uY2F0ZW5hdGVkVmFsdWVzID0gZXZlbnRQYXJ0c0ZpbHRlcmVkLmNvbmNhdChcbiAgICBwcmVCdWZmZXJFdmVudFBhcnRzVG90YWxcbiAgKTtcbiAgY29uY2F0ZW5hdGVkVmFsdWVzLmZvckVhY2goKGUpID0+XG4gICAgY29uc29sZS5sb2coXG4gICAgICBlLmlkLFxuICAgICAgZS5ncm91cElkLFxuICAgICAgZS5ldmVudElkLFxuICAgICAgZS5wYXJ0LFxuICAgICAgZS5sYXN0UGFydCxcbiAgICAgIGUuc3RhcnREYXRlLFxuICAgICAgZS5lbmREYXRlLFxuICAgICAgZT8uZm9yRXZlbnRJZCxcbiAgICAgIGBlLmlkLCBlLmV2ZW50SWQsIGUuYWN0dWFsSWQsIGUucGFydCwgZS5sYXN0UGFydCwgZS5zdGFydERhdGUsIGUuZW5kRGF0ZSwgZT8uZm9yRXZlbnRJZCwgIGluc2lkZSBtb2RpZnlFdmVudFBhcnRzRm9yTXVsdGlwbGVQcmVCdWZmZXJUaW1lYFxuICAgIClcbiAgKTtcbiAgcmV0dXJuIGNvbmNhdGVuYXRlZFZhbHVlcztcbn07XG5cbmV4cG9ydCBjb25zdCBtb2RpZnlFdmVudFBhcnRzRm9yTXVsdGlwbGVQb3N0QnVmZmVyVGltZSA9IChcbiAgZXZlbnRQYXJ0czogSW5pdGlhbEV2ZW50UGFydFR5cGVbXVxuKTogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSA9PiB7XG4gIGNvbnN0IHVuaXF1ZVBvc3RCdWZmZXJQYXJ0Rm9yRXZlbnRJZHM6IHN0cmluZ1tdID0gW107XG4gIGNvbnN0IHBvc3RCdWZmZXJFdmVudFBhcnRzVG90YWw6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPSBbXTtcblxuICBmb3IgKGxldCBpID0gMDsgaSA8IGV2ZW50UGFydHMubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAoZXZlbnRQYXJ0c1tpXS5mb3JFdmVudElkICYmIGV2ZW50UGFydHNbaV0uaXNQb3N0RXZlbnQpIHtcbiAgICAgIGNvbnN0IGZvdW5kUGFydCA9IHVuaXF1ZVBvc3RCdWZmZXJQYXJ0Rm9yRXZlbnRJZHMuZmluZChcbiAgICAgICAgKGUpID0+IGUgPT09IGV2ZW50UGFydHNbaV0uZm9yRXZlbnRJZFxuICAgICAgKTtcbiAgICAgIC8vIGlmIGZvdW5kIHNraXBcbiAgICAgIGlmIChmb3VuZFBhcnQpIHtcbiAgICAgICAgY29udGludWU7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICB1bmlxdWVQb3N0QnVmZmVyUGFydEZvckV2ZW50SWRzLnB1c2goZXZlbnRQYXJ0c1tpXS5mb3JFdmVudElkKTtcbiAgICAgIH1cbiAgICB9XG4gIH1cblxuICAvLyBmaWxsIHVwIHByZUJ1ZmZlckV2ZW50UGFydHNUb3RhbFxuICBmb3IgKGxldCBpID0gMDsgaSA8IHVuaXF1ZVBvc3RCdWZmZXJQYXJ0Rm9yRXZlbnRJZHMubGVuZ3RoOyBpKyspIHtcbiAgICBjb25zdCByZXR1cm5lZEV2ZW50UGFydFRvdGFsID0gbW9kaWZ5RXZlbnRQYXJ0c0ZvclNpbmd1bGFyUG9zdEJ1ZmZlclRpbWUoXG4gICAgICBldmVudFBhcnRzLFxuICAgICAgdW5pcXVlUG9zdEJ1ZmZlclBhcnRGb3JFdmVudElkc1tpXVxuICAgICk7XG4gICAgcG9zdEJ1ZmZlckV2ZW50UGFydHNUb3RhbC5wdXNoKC4uLnJldHVybmVkRXZlbnRQYXJ0VG90YWwpO1xuICB9XG5cbiAgLy8gcmVtb3ZlIG9sZCB2YWx1ZXNcbiAgY29uc3QgZXZlbnRQYXJ0c0ZpbHRlcmVkID0gXy5kaWZmZXJlbmNlQnkoXG4gICAgZXZlbnRQYXJ0cyxcbiAgICBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsLFxuICAgICdpZCdcbiAgKTtcbiAgLy8gYWRkIG5ldyB2YWx1ZXNcbiAgY29uc3QgY29uY2F0ZW5hdGVkVmFsdWVzID0gZXZlbnRQYXJ0c0ZpbHRlcmVkLmNvbmNhdChcbiAgICBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsXG4gICk7XG5cbiAgY29uY2F0ZW5hdGVkVmFsdWVzLmZvckVhY2goKGUpID0+XG4gICAgY29uc29sZS5sb2coXG4gICAgICBlLmlkLFxuICAgICAgZS5ncm91cElkLFxuICAgICAgZS5ldmVudElkLFxuICAgICAgZS5wYXJ0LFxuICAgICAgZS5sYXN0UGFydCxcbiAgICAgIGUuc3RhcnREYXRlLFxuICAgICAgZS5lbmREYXRlLFxuICAgICAgZT8uZm9yRXZlbnRJZCxcbiAgICAgIGBlLmlkLCBlLmdyb3VwSWQsIGUuZXZlbnRJZCwgZS5wYXJ0LCBlLmxhc3RQYXJ0LCBlLnN0YXJ0RGF0ZSwgZS5lbmREYXRlLCBlPy5mb3JFdmVudElkLCAgaW5zaWRlIG1vZGlmeUV2ZW50UGFydHNGb3JNdWx0aXBsZVBvc3RCdWZmZXJUaW1lYFxuICAgIClcbiAgKTtcbiAgcmV0dXJuIGNvbmNhdGVuYXRlZFZhbHVlcztcbn07XG5cbmV4cG9ydCBjb25zdCBtb2RpZnlFdmVudFBhcnRzRm9yU2luZ3VsYXJQb3N0QnVmZmVyVGltZSA9IChcbiAgZXZlbnRQYXJ0czogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSxcbiAgZm9yRXZlbnRJZDogc3RyaW5nXG4pOiBJbml0aWFsRXZlbnRQYXJ0VHlwZVtdID0+IHtcbiAgY29uc3QgcG9zdEJ1ZmZlckFmdGVyRXZlbnRQYXJ0czogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSA9IFtdO1xuICBjb25zdCBwb3N0QnVmZmVyQWN0dWFsRXZlbnRQYXJ0czogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSA9IFtdO1xuXG4gIGNvbnN0IHBvc3RCdWZmZXJHcm91cElkID0gdXVpZCgpO1xuXG4gIGZvciAobGV0IGkgPSAwOyBpIDwgZXZlbnRQYXJ0cy5sZW5ndGg7IGkrKykge1xuICAgIGlmIChldmVudFBhcnRzW2ldLmlkID09IGZvckV2ZW50SWQpIHtcbiAgICAgIHBvc3RCdWZmZXJBY3R1YWxFdmVudFBhcnRzLnB1c2goe1xuICAgICAgICAuLi5ldmVudFBhcnRzW2ldLFxuICAgICAgICBncm91cElkOiBwb3N0QnVmZmVyR3JvdXBJZCxcbiAgICAgIH0pO1xuICAgIH1cbiAgfVxuXG4gIGZvciAobGV0IGkgPSAwOyBpIDwgZXZlbnRQYXJ0cy5sZW5ndGg7IGkrKykge1xuICAgIGlmIChldmVudFBhcnRzW2ldLmZvckV2ZW50SWQgPT09IGZvckV2ZW50SWQgJiYgZXZlbnRQYXJ0c1tpXS5pc1Bvc3RFdmVudCkge1xuICAgICAgcG9zdEJ1ZmZlckFmdGVyRXZlbnRQYXJ0cy5wdXNoKHtcbiAgICAgICAgLi4uZXZlbnRQYXJ0c1tpXSxcbiAgICAgICAgZ3JvdXBJZDogcG9zdEJ1ZmZlckdyb3VwSWQsXG4gICAgICB9KTtcbiAgICB9XG4gIH1cblxuICBjb25zdCBwb3N0QnVmZmVyQWN0dWFsRXZlbnRQYXJ0c1NvcnRlZCA9IHBvc3RCdWZmZXJBY3R1YWxFdmVudFBhcnRzLnNvcnQoXG4gICAgKGEsIGIpID0+IGEucGFydCAtIGIucGFydFxuICApO1xuICBjb25zdCBwb3N0QnVmZmVyQWZ0ZXJFdmVudFBhcnRzU29ydGVkID0gcG9zdEJ1ZmZlckFmdGVyRXZlbnRQYXJ0cy5zb3J0KFxuICAgIChhLCBiKSA9PiBhLnBhcnQgLSBiLnBhcnRcbiAgKTtcblxuICBjb25zdCBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsID0gcG9zdEJ1ZmZlckFjdHVhbEV2ZW50UGFydHNTb3J0ZWQuY29uY2F0KFxuICAgIHBvc3RCdWZmZXJBZnRlckV2ZW50UGFydHNTb3J0ZWRcbiAgKTtcblxuICBjb25zdCBwcmVFdmVudElkID0gcG9zdEJ1ZmZlckV2ZW50UGFydHNUb3RhbD8uWzBdPy5wcmVFdmVudElkO1xuICBjb25zdCBhY3R1YWxFdmVudFByZXZpb3VzTGFzdFBhcnQgPSBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsPy5bMF0/Lmxhc3RQYXJ0O1xuXG4gIGZvciAobGV0IGkgPSAwOyBpIDwgcG9zdEJ1ZmZlckV2ZW50UGFydHNUb3RhbC5sZW5ndGg7IGkrKykge1xuICAgIGlmIChwcmVFdmVudElkKSB7XG4gICAgICBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsW2ldLmxhc3RQYXJ0ID1cbiAgICAgICAgYWN0dWFsRXZlbnRQcmV2aW91c0xhc3RQYXJ0ICsgcG9zdEJ1ZmZlckFmdGVyRXZlbnRQYXJ0c1NvcnRlZC5sZW5ndGg7XG4gICAgfSBlbHNlIHtcbiAgICAgIHBvc3RCdWZmZXJFdmVudFBhcnRzVG90YWxbaV0ucGFydCA9IGkgKyAxO1xuICAgICAgcG9zdEJ1ZmZlckV2ZW50UGFydHNUb3RhbFtpXS5sYXN0UGFydCA9IHBvc3RCdWZmZXJFdmVudFBhcnRzVG90YWwubGVuZ3RoO1xuICAgIH1cbiAgfVxuXG4gIC8vIGFkZCB2YWx1ZXMgZm9yIHBvc3RCdWZmZXIgcGFydFxuICBmb3IgKGxldCBpID0gMDsgaSA8IHBvc3RCdWZmZXJBZnRlckV2ZW50UGFydHNTb3J0ZWQubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAoXG4gICAgICBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsPy5bcG9zdEJ1ZmZlckFjdHVhbEV2ZW50UGFydHNTb3J0ZWQ/Lmxlbmd0aCArIGldXG4gICAgKSB7XG4gICAgICBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsW1xuICAgICAgICBwb3N0QnVmZmVyQWN0dWFsRXZlbnRQYXJ0c1NvcnRlZD8ubGVuZ3RoICsgaVxuICAgICAgXS5wYXJ0ID0gYWN0dWFsRXZlbnRQcmV2aW91c0xhc3RQYXJ0ICsgaSArIDE7XG4gICAgfVxuICB9XG5cbiAgLy8gY2hhbmdlIHByZUV2ZW50SWQncyBsYXN0IHBhcnQgYW5kIGV2ZW50SWRcbiAgY29uc3QgcHJlRXZlbnRQYXJ0cyA9IGV2ZW50UGFydHMuZmlsdGVyKChlKSA9PiBlLmV2ZW50SWQgPT09IHByZUV2ZW50SWQpO1xuICBjb25zdCBwcmVCdWZmZXJFdmVudFBhcnRzID0gcHJlRXZlbnRQYXJ0cz8ubWFwKChlKSA9PiAoe1xuICAgIC4uLmUsXG4gICAgZ3JvdXBJZDogcG9zdEJ1ZmZlckdyb3VwSWQsXG4gICAgbGFzdFBhcnQ6XG4gICAgICBhY3R1YWxFdmVudFByZXZpb3VzTGFzdFBhcnQgKyBwb3N0QnVmZmVyQWZ0ZXJFdmVudFBhcnRzU29ydGVkLmxlbmd0aCxcbiAgfSkpO1xuICBjb25zdCBjb25jYXRlbmF0ZWRWYWx1ZXMgPSBwcmVCdWZmZXJFdmVudFBhcnRzLmNvbmNhdChcbiAgICBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsXG4gICk7XG4gIGNvbmNhdGVuYXRlZFZhbHVlcy5mb3JFYWNoKChlKSA9PlxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZS5pZCxcbiAgICAgIGUuZ3JvdXBJZCxcbiAgICAgIGUuZXZlbnRJZCxcbiAgICAgIGUucGFydCxcbiAgICAgIGUubGFzdFBhcnQsXG4gICAgICBlLnN0YXJ0RGF0ZSxcbiAgICAgIGUuZW5kRGF0ZSxcbiAgICAgIGU/LmZvckV2ZW50SWQsXG4gICAgICBgZS5pZCwgZS5ncm91cElkLCBlLmV2ZW50SWQsIGUucGFydCwgZS5sYXN0UGFydCwgZS5zdGFydERhdGUsIGUuZW5kRGF0ZSwgZT8uZm9yRXZlbnRJZCwgIGluc2lkZSBtb2RpZnlFdmVudFBhcnRzRm9yU2luZ2x1bGFyUG9zdEJ1ZmZlclRpbWVgXG4gICAgKVxuICApO1xuICByZXR1cm4gY29uY2F0ZW5hdGVkVmFsdWVzO1xufTtcblxuZXhwb3J0IGNvbnN0IGZvcm1hdEV2ZW50VHlwZVRvUGxhbm5lckV2ZW50ID0gKFxuICBldmVudDogSW5pdGlhbEV2ZW50UGFydFR5cGVQbHVzLFxuICB1c2VyUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlLFxuICB3b3JrVGltZXM6IFdvcmtUaW1lVHlwZVtdLFxuICBob3N0VGltZXpvbmU6IHN0cmluZ1xuKTogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9PiB7XG4gIGNvbnN0IHtcbiAgICBhbGxEYXksXG4gICAgcGFydCxcbiAgICBmb3JFdmVudElkLFxuICAgIGdyb3VwSWQsXG4gICAgZXZlbnRJZCxcbiAgICBpc0JyZWFrLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICBpc01lZXRpbmcsXG4gICAgaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICBpc1Bvc3RFdmVudCxcbiAgICBpc1ByZUV2ZW50LFxuICAgIG1vZGlmaWFibGUsXG4gICAgbmVnYXRpdmVJbXBhY3REYXlPZldlZWssXG4gICAgbmVnYXRpdmVJbXBhY3RTY29yZSxcbiAgICBuZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWssXG4gICAgcG9zaXRpdmVJbXBhY3RTY29yZSxcbiAgICBwb3NpdGl2ZUltcGFjdFRpbWUsXG4gICAgcHJlZmVycmVkRGF5T2ZXZWVrLFxuICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZSxcbiAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZSxcbiAgICBwcmVmZXJyZWRUaW1lLFxuICAgIHByaW9yaXR5LFxuICAgIHN0YXJ0RGF0ZSxcbiAgICBlbmREYXRlLFxuICAgIHRhc2tJZCxcbiAgICB1c2VySWQsXG4gICAgd2Vla2x5VGFza0xpc3QsXG4gICAgZGFpbHlUYXNrTGlzdCxcbiAgICBoYXJkRGVhZGxpbmUsXG4gICAgc29mdERlYWRsaW5lLFxuICAgIHJlY3VycmluZ0V2ZW50SWQsXG4gICAgbGFzdFBhcnQsXG4gICAgcHJlZmVycmVkVGltZVJhbmdlcyxcbiAgICBob3N0SWQsXG4gICAgbWVldGluZ0lkLFxuICAgIHRpbWV6b25lLFxuICAgIG1lZXRpbmdQYXJ0LFxuICAgIG1lZXRpbmdMYXN0UGFydCxcbiAgfSA9IGV2ZW50O1xuXG4gIGlmIChhbGxEYXkpIHtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIGNvbnN0IHRvdGFsV29ya2luZ0hvdXJzID0gY29udmVydFRvVG90YWxXb3JraW5nSG91cnNGb3JJbnRlcm5hbEF0dGVuZGVlKFxuICAgIHVzZXJQcmVmZXJlbmNlLFxuICAgIGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmZvcm1hdCgpLFxuICAgIGhvc3RUaW1lem9uZVxuICApO1xuXG4gIGNvbnN0IHVzZXI6IFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlID0ge1xuICAgIGlkOiBldmVudC51c2VySWQsXG4gICAgbWF4V29ya0xvYWRQZXJjZW50OiB1c2VyUHJlZmVyZW5jZS5tYXhXb3JrTG9hZFBlcmNlbnQsXG4gICAgYmFja1RvQmFja01lZXRpbmdzOiB1c2VyUHJlZmVyZW5jZS5iYWNrVG9CYWNrTWVldGluZ3MsXG4gICAgbWF4TnVtYmVyT2ZNZWV0aW5nczogdXNlclByZWZlcmVuY2UubWF4TnVtYmVyT2ZNZWV0aW5ncyxcbiAgICBtaW5OdW1iZXJPZkJyZWFrczogdXNlclByZWZlcmVuY2UubWluTnVtYmVyT2ZCcmVha3MsXG4gICAgd29ya1RpbWVzLFxuICAgIGhvc3RJZCxcbiAgfTtcblxuICBjb25zdCBhZGp1c3RlZFBvc2l0aXZlSW1wYWN0VGltZSA9XG4gICAgKHBvc2l0aXZlSW1wYWN0VGltZSAmJlxuICAgICAgKGRheWpzKClcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuaG91cihwYXJzZUludChwb3NpdGl2ZUltcGFjdFRpbWUuc2xpY2UoMCwgMiksIDEwKSlcbiAgICAgICAgLm1pbnV0ZShwYXJzZUludChwb3NpdGl2ZUltcGFjdFRpbWUuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lKSkgfHxcbiAgICB1bmRlZmluZWQ7XG5cbiAgY29uc3QgYWRqdXN0ZWROZWdhdGl2ZUltcGFjdFRpbWUgPVxuICAgIChuZWdhdGl2ZUltcGFjdFRpbWUgJiZcbiAgICAgIChkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQobmVnYXRpdmVJbXBhY3RUaW1lLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQobmVnYXRpdmVJbXBhY3RUaW1lLnNsaWNlKDMpLCAxMCkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSkpIHx8XG4gICAgdW5kZWZpbmVkO1xuXG4gIGNvbnN0IGFkanVzdGVkUHJlZmVycmVkVGltZSA9XG4gICAgKHByZWZlcnJlZFRpbWUgJiZcbiAgICAgIChkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQocHJlZmVycmVkVGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KHByZWZlcnJlZFRpbWUuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lKSkgfHxcbiAgICB1bmRlZmluZWQ7XG5cbiAgY29uc3QgYWRqdXN0ZWRQcmVmZXJyZWRTdGFydFRpbWVSYW5nZSA9XG4gICAgKHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlICYmXG4gICAgICAoZGF5anMoKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5ob3VyKHBhcnNlSW50KHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQocHJlZmVycmVkU3RhcnRUaW1lUmFuZ2Uuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lKSkgfHxcbiAgICB1bmRlZmluZWQ7XG5cbiAgY29uc3QgYWRqdXN0ZWRQcmVmZXJyZWRFbmRUaW1lUmFuZ2UgPVxuICAgIChwcmVmZXJyZWRFbmRUaW1lUmFuZ2UgJiZcbiAgICAgIChkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQocHJlZmVycmVkRW5kVGltZVJhbmdlLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQocHJlZmVycmVkRW5kVGltZVJhbmdlLnNsaWNlKDMpLCAxMCkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSkpIHx8XG4gICAgdW5kZWZpbmVkO1xuXG4gIGNvbnN0IGFkanVzdGVkUHJlZmVycmVkVGltZVJhbmdlcyA9XG4gICAgcHJlZmVycmVkVGltZVJhbmdlcz8ubWFwKChlKSA9PiAoe1xuICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZz8uW2U/LmRheU9mV2Vla10gPz8gbnVsbCxcbiAgICAgIHN0YXJ0VGltZTogZGF5anMoKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5ob3VyKHBhcnNlSW50KGU/LnN0YXJ0VGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KGU/LnN0YXJ0VGltZS5zbGljZSgzKSwgMTApKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICBlbmRUaW1lOiBkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQoZT8uZW5kVGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KGU/LmVuZFRpbWUuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgZXZlbnRJZCxcbiAgICAgIHVzZXJJZCxcbiAgICAgIGhvc3RJZCxcbiAgICB9KSkgPz8gbnVsbDtcblxuICBjb25zdCBldmVudFBsYW5uZXJSZXF1ZXN0Qm9keTogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9IHtcbiAgICBncm91cElkLFxuICAgIGV2ZW50SWQsXG4gICAgcGFydCxcbiAgICBsYXN0UGFydCxcbiAgICBtZWV0aW5nUGFydCxcbiAgICBtZWV0aW5nTGFzdFBhcnQsXG4gICAgc3RhcnREYXRlOiBkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpLFxuICAgIGVuZERhdGU6IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpLFxuICAgIHRhc2tJZCxcbiAgICBoYXJkRGVhZGxpbmUsXG4gICAgc29mdERlYWRsaW5lLFxuICAgIHVzZXJJZCxcbiAgICB1c2VyLFxuICAgIHByaW9yaXR5LFxuICAgIGlzUHJlRXZlbnQsXG4gICAgaXNQb3N0RXZlbnQsXG4gICAgZm9yRXZlbnRJZCxcbiAgICBwb3NpdGl2ZUltcGFjdFNjb3JlLFxuICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmUsXG4gICAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWs6XG4gICAgICBkYXlPZldlZWtJbnRUb1N0cmluZ1twb3NpdGl2ZUltcGFjdERheU9mV2Vla10gPz8gbnVsbCxcbiAgICBwb3NpdGl2ZUltcGFjdFRpbWU6IGFkanVzdGVkUG9zaXRpdmVJbXBhY3RUaW1lLFxuICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrOlxuICAgICAgZGF5T2ZXZWVrSW50VG9TdHJpbmdbbmVnYXRpdmVJbXBhY3REYXlPZldlZWtdID8/IG51bGwsXG4gICAgbmVnYXRpdmVJbXBhY3RUaW1lOiBhZGp1c3RlZE5lZ2F0aXZlSW1wYWN0VGltZSxcbiAgICBtb2RpZmlhYmxlLFxuICAgIHByZWZlcnJlZERheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbcHJlZmVycmVkRGF5T2ZXZWVrXSA/PyBudWxsLFxuICAgIHByZWZlcnJlZFRpbWU6IGFkanVzdGVkUHJlZmVycmVkVGltZSxcbiAgICBpc01lZXRpbmcsXG4gICAgaXNFeHRlcm5hbE1lZXRpbmcsXG4gICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlLFxuICAgIGlzTWVldGluZ01vZGlmaWFibGUsXG4gICAgZGFpbHlUYXNrTGlzdCxcbiAgICB3ZWVrbHlUYXNrTGlzdCxcbiAgICBnYXA6IGlzQnJlYWssXG4gICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U6IGFkanVzdGVkUHJlZmVycmVkU3RhcnRUaW1lUmFuZ2UsXG4gICAgcHJlZmVycmVkRW5kVGltZVJhbmdlOiBhZGp1c3RlZFByZWZlcnJlZEVuZFRpbWVSYW5nZSxcbiAgICB0b3RhbFdvcmtpbmdIb3VycyxcbiAgICByZWN1cnJpbmdFdmVudElkLFxuICAgIGhvc3RJZCxcbiAgICBtZWV0aW5nSWQsXG4gICAgZXZlbnQ6IHtcbiAgICAgIGlkOiBldmVudElkLFxuICAgICAgdXNlcklkLFxuICAgICAgaG9zdElkLFxuICAgICAgcHJlZmVycmVkVGltZVJhbmdlczogYWRqdXN0ZWRQcmVmZXJyZWRUaW1lUmFuZ2VzID8/IG51bGwsXG4gICAgICBldmVudFR5cGU6IGV2ZW50LmV2ZW50VHlwZSxcbiAgICB9LFxuICB9O1xuICByZXR1cm4gZXZlbnRQbGFubmVyUmVxdWVzdEJvZHk7XG59O1xuXG5leHBvcnQgY29uc3QgZm9ybWF0RXZlbnRUeXBlVG9QbGFubmVyRXZlbnRGb3JFeHRlcm5hbEF0dGVuZGVlID0gKFxuICBldmVudDogSW5pdGlhbEV2ZW50UGFydFR5cGVQbHVzLFxuICB3b3JrVGltZXM6IFdvcmtUaW1lVHlwZVtdLFxuICBhdHRlbmRlZUV2ZW50czogRXZlbnRQbHVzVHlwZVtdLFxuICBob3N0VGltZXpvbmU6IHN0cmluZ1xuKTogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9PiB7XG4gIGNvbnN0IHtcbiAgICBhbGxEYXksXG4gICAgcGFydCxcbiAgICBmb3JFdmVudElkLFxuICAgIGdyb3VwSWQsXG4gICAgZXZlbnRJZCxcbiAgICBpc0JyZWFrLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICBpc01lZXRpbmcsXG4gICAgaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICBpc1Bvc3RFdmVudCxcbiAgICBpc1ByZUV2ZW50LFxuICAgIG1vZGlmaWFibGUsXG4gICAgbmVnYXRpdmVJbXBhY3REYXlPZldlZWssXG4gICAgbmVnYXRpdmVJbXBhY3RTY29yZSxcbiAgICBuZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWssXG4gICAgcG9zaXRpdmVJbXBhY3RTY29yZSxcbiAgICBwb3NpdGl2ZUltcGFjdFRpbWUsXG4gICAgcHJlZmVycmVkRGF5T2ZXZWVrLFxuICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZSxcbiAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZSxcbiAgICBwcmVmZXJyZWRUaW1lLFxuICAgIHByaW9yaXR5LFxuICAgIHN0YXJ0RGF0ZSxcbiAgICBlbmREYXRlLFxuICAgIHRhc2tJZCxcbiAgICB1c2VySWQsXG4gICAgd2Vla2x5VGFza0xpc3QsXG4gICAgZGFpbHlUYXNrTGlzdCxcbiAgICBoYXJkRGVhZGxpbmUsXG4gICAgc29mdERlYWRsaW5lLFxuICAgIHJlY3VycmluZ0V2ZW50SWQsXG4gICAgbGFzdFBhcnQsXG4gICAgcHJlZmVycmVkVGltZVJhbmdlcyxcbiAgICBob3N0SWQsXG4gICAgbWVldGluZ0lkLFxuICAgIHRpbWV6b25lLFxuICAgIG1lZXRpbmdQYXJ0LFxuICAgIG1lZXRpbmdMYXN0UGFydCxcbiAgfSA9IGV2ZW50O1xuXG4gIGlmIChhbGxEYXkpIHtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIGNvbnN0IHRvdGFsV29ya2luZ0hvdXJzID0gY29udmVydFRvVG90YWxXb3JraW5nSG91cnNGb3JFeHRlcm5hbEF0dGVuZGVlKFxuICAgIGF0dGVuZGVlRXZlbnRzLFxuICAgIGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmZvcm1hdCgpLFxuICAgIGhvc3RUaW1lem9uZSxcbiAgICBldmVudD8udGltZXpvbmVcbiAgKTtcblxuICBjb25zdCB1c2VyOiBVc2VyUGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9IHtcbiAgICBpZDogZXZlbnQudXNlcklkLFxuICAgIG1heFdvcmtMb2FkUGVyY2VudDogMTAwLFxuICAgIGJhY2tUb0JhY2tNZWV0aW5nczogZmFsc2UsXG4gICAgbWF4TnVtYmVyT2ZNZWV0aW5nczogOTksXG4gICAgbWluTnVtYmVyT2ZCcmVha3M6IDAsXG4gICAgd29ya1RpbWVzLFxuICAgIGhvc3RJZCxcbiAgfTtcblxuICBjb25zdCBhZGp1c3RlZFBvc2l0aXZlSW1wYWN0VGltZSA9XG4gICAgKHBvc2l0aXZlSW1wYWN0VGltZSAmJlxuICAgICAgKGRheWpzKClcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuaG91cihwYXJzZUludChwb3NpdGl2ZUltcGFjdFRpbWUuc2xpY2UoMCwgMiksIDEwKSlcbiAgICAgICAgLm1pbnV0ZShwYXJzZUludChwb3NpdGl2ZUltcGFjdFRpbWUuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lKSkgfHxcbiAgICB1bmRlZmluZWQ7XG5cbiAgY29uc3QgYWRqdXN0ZWROZWdhdGl2ZUltcGFjdFRpbWUgPVxuICAgIChuZWdhdGl2ZUltcGFjdFRpbWUgJiZcbiAgICAgIChkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQobmVnYXRpdmVJbXBhY3RUaW1lLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQobmVnYXRpdmVJbXBhY3RUaW1lLnNsaWNlKDMpLCAxMCkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSkpIHx8XG4gICAgdW5kZWZpbmVkO1xuXG4gIGNvbnN0IGFkanVzdGVkUHJlZmVycmVkVGltZSA9XG4gICAgKHByZWZlcnJlZFRpbWUgJiZcbiAgICAgIChkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQocHJlZmVycmVkVGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KHByZWZlcnJlZFRpbWUuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lKSkgfHxcbiAgICB1bmRlZmluZWQ7XG5cbiAgY29uc3QgYWRqdXN0ZWRQcmVmZXJyZWRTdGFydFRpbWVSYW5nZSA9XG4gICAgKHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlICYmXG4gICAgICAoZGF5anMoKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5ob3VyKHBhcnNlSW50KHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQocHJlZmVycmVkU3RhcnRUaW1lUmFuZ2Uuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lKSkgfHxcbiAgICB1bmRlZmluZWQ7XG5cbiAgY29uc3QgYWRqdXN0ZWRQcmVmZXJyZWRFbmRUaW1lUmFuZ2UgPVxuICAgIChwcmVmZXJyZWRFbmRUaW1lUmFuZ2UgJiZcbiAgICAgIChkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQocHJlZmVycmVkRW5kVGltZVJhbmdlLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQocHJlZmVycmVkRW5kVGltZVJhbmdlLnNsaWNlKDMpLCAxMCkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSkpIHx8XG4gICAgdW5kZWZpbmVkO1xuXG4gIGNvbnN0IGFkanVzdGVkUHJlZmVycmVkVGltZVJhbmdlcyA9XG4gICAgcHJlZmVycmVkVGltZVJhbmdlcz8ubWFwKChlKSA9PiAoe1xuICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZz8uW2U/LmRheU9mV2Vla10gPz8gbnVsbCxcbiAgICAgIHN0YXJ0VGltZTogZGF5anMoKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5ob3VyKHBhcnNlSW50KGU/LnN0YXJ0VGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KGU/LnN0YXJ0VGltZS5zbGljZSgzKSwgMTApKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICBlbmRUaW1lOiBkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQoZT8uZW5kVGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KGU/LmVuZFRpbWUuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgZXZlbnRJZCxcbiAgICAgIHVzZXJJZCxcbiAgICAgIGhvc3RJZCxcbiAgICB9KSkgPz8gbnVsbDtcblxuICBjb25zdCBldmVudFBsYW5uZXJSZXF1ZXN0Qm9keTogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9IHtcbiAgICBncm91cElkLFxuICAgIGV2ZW50SWQsXG4gICAgcGFydCxcbiAgICBsYXN0UGFydCxcbiAgICBtZWV0aW5nUGFydCxcbiAgICBtZWV0aW5nTGFzdFBhcnQsXG4gICAgc3RhcnREYXRlOiBkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpLFxuICAgIGVuZERhdGU6IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpLFxuICAgIHRhc2tJZCxcbiAgICBoYXJkRGVhZGxpbmUsXG4gICAgc29mdERlYWRsaW5lLFxuICAgIHVzZXJJZCxcbiAgICB1c2VyLFxuICAgIHByaW9yaXR5LFxuICAgIGlzUHJlRXZlbnQsXG4gICAgaXNQb3N0RXZlbnQsXG4gICAgZm9yRXZlbnRJZCxcbiAgICBwb3NpdGl2ZUltcGFjdFNjb3JlLFxuICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmUsXG4gICAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWs6XG4gICAgICBkYXlPZldlZWtJbnRUb1N0cmluZ1twb3NpdGl2ZUltcGFjdERheU9mV2Vla10gPz8gbnVsbCxcbiAgICBwb3NpdGl2ZUltcGFjdFRpbWU6IGFkanVzdGVkUG9zaXRpdmVJbXBhY3RUaW1lLFxuICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrOlxuICAgICAgZGF5T2ZXZWVrSW50VG9TdHJpbmdbbmVnYXRpdmVJbXBhY3REYXlPZldlZWtdID8/IG51bGwsXG4gICAgbmVnYXRpdmVJbXBhY3RUaW1lOiBhZGp1c3RlZE5lZ2F0aXZlSW1wYWN0VGltZSxcbiAgICBtb2RpZmlhYmxlLFxuICAgIHByZWZlcnJlZERheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbcHJlZmVycmVkRGF5T2ZXZWVrXSA/PyBudWxsLFxuICAgIHByZWZlcnJlZFRpbWU6IGFkanVzdGVkUHJlZmVycmVkVGltZSxcbiAgICBpc01lZXRpbmcsXG4gICAgaXNFeHRlcm5hbE1lZXRpbmcsXG4gICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlLFxuICAgIGlzTWVldGluZ01vZGlmaWFibGUsXG4gICAgZGFpbHlUYXNrTGlzdCxcbiAgICB3ZWVrbHlUYXNrTGlzdCxcbiAgICBnYXA6IGlzQnJlYWssXG4gICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U6IGFkanVzdGVkUHJlZmVycmVkU3RhcnRUaW1lUmFuZ2UsXG4gICAgcHJlZmVycmVkRW5kVGltZVJhbmdlOiBhZGp1c3RlZFByZWZlcnJlZEVuZFRpbWVSYW5nZSxcbiAgICB0b3RhbFdvcmtpbmdIb3VycyxcbiAgICByZWN1cnJpbmdFdmVudElkLFxuICAgIGhvc3RJZCxcbiAgICBtZWV0aW5nSWQsXG4gICAgZXZlbnQ6IHtcbiAgICAgIGlkOiBldmVudElkLFxuICAgICAgdXNlcklkLFxuICAgICAgaG9zdElkLFxuICAgICAgcHJlZmVycmVkVGltZVJhbmdlczogYWRqdXN0ZWRQcmVmZXJyZWRUaW1lUmFuZ2VzID8/IG51bGwsXG4gICAgICBldmVudFR5cGU6IGV2ZW50LmV2ZW50VHlwZSxcbiAgICB9LFxuICB9O1xuICByZXR1cm4gZXZlbnRQbGFubmVyUmVxdWVzdEJvZHk7XG59O1xuXG5leHBvcnQgY29uc3QgY29udmVydE1lZXRpbmdQbHVzVHlwZVRvRXZlbnRQbHVzVHlwZSA9IChcbiAgZXZlbnQ6IEV2ZW50TWVldGluZ1BsdXNUeXBlXG4pOiBFdmVudFBsdXNUeXBlID0+IHtcbiAgY29uc3QgbmV3RXZlbnQ6IEV2ZW50UGx1c1R5cGUgPSB7XG4gICAgLi4uZXZlbnQsXG4gICAgcHJlZmVycmVkVGltZVJhbmdlczpcbiAgICAgIGV2ZW50Py5wcmVmZXJyZWRUaW1lUmFuZ2VzPy5tYXAoKHB0KSA9PiAoe1xuICAgICAgICBpZDogcHQuaWQsXG4gICAgICAgIGV2ZW50SWQ6IGV2ZW50LmlkLFxuICAgICAgICBkYXlPZldlZWs6IHB0Py5kYXlPZldlZWssXG4gICAgICAgIHN0YXJ0VGltZTogcHQ/LnN0YXJ0VGltZSxcbiAgICAgICAgZW5kVGltZTogcHQ/LmVuZFRpbWUsXG4gICAgICAgIHVwZGF0ZWRBdDogcHQ/LnVwZGF0ZWRBdCxcbiAgICAgICAgY3JlYXRlZERhdGU6IHB0Py5jcmVhdGVkRGF0ZSxcbiAgICAgICAgdXNlcklkOiBldmVudD8udXNlcklkLFxuICAgICAgfSkpIHx8IG51bGwsXG4gIH07XG5cbiAgcmV0dXJuIG5ld0V2ZW50O1xufTtcblxuZXhwb3J0IGNvbnN0IHNldFByZWZlcnJlZFRpbWVGb3JVbk1vZGlmaWFibGVFdmVudCA9IChcbiAgZXZlbnQ6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGUsXG4gIHRpbWV6b25lOiBzdHJpbmdcbik6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGUgPT4ge1xuICAvLyBzZXQgcHJlZmVycmVkIERheU9mV2VlayBhbmQgVGltZSBpZiBub3Qgc2V0XG4gIGlmICghZXZlbnQ/Lm1vZGlmaWFibGUpIHtcbiAgICBpZiAoIWV2ZW50Py5wcmVmZXJyZWREYXlPZldlZWsgJiYgIWV2ZW50Py5wcmVmZXJyZWRUaW1lKSB7XG4gICAgICBjb25zdCBuZXdFdmVudCA9IHtcbiAgICAgICAgLi4uZXZlbnQsXG4gICAgICAgIHByZWZlcnJlZERheU9mV2VlazpcbiAgICAgICAgICBkYXlPZldlZWtJbnRUb1N0cmluZ1tcbiAgICAgICAgICAgIGdldElTT0RheShcbiAgICAgICAgICAgICAgZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICAgICAgICAgICApXG4gICAgICAgICAgXSxcbiAgICAgICAgcHJlZmVycmVkVGltZTogZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgfTtcbiAgICAgIHJldHVybiBuZXdFdmVudDtcbiAgICB9XG4gICAgcmV0dXJuIGV2ZW50O1xuICB9XG4gIHJldHVybiBldmVudDtcbn07XG5cbmV4cG9ydCBjb25zdCBsaXN0RXZlbnRzV2l0aElkcyA9IGFzeW5jIChpZHM6IHN0cmluZ1tdKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdsaXN0RXZlbnRzV2l0aElkcyc7XG5cbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICBxdWVyeSBsaXN0RXZlbnRzV2l0aElkcygkaWRzOiBbU3RyaW5nIV0hKSB7XG4gICAgICBFdmVudCh3aGVyZToge2lkOiB7X2luOiAkaWRzfX0pIHtcbiAgICAgICAgYWxsRGF5XG4gICAgICAgIGFueW9uZUNhbkFkZFNlbGZcbiAgICAgICAgYXR0YWNobWVudHNcbiAgICAgICAgYXR0ZW5kZWVzT21pdHRlZFxuICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICBjb2xvcklkXG4gICAgICAgIGNvbmZlcmVuY2VJZFxuICAgICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICAgIGNvcHlDYXRlZ29yaWVzXG4gICAgICAgIGNvcHlEdXJhdGlvblxuICAgICAgICBjb3B5SXNCcmVha1xuICAgICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgY29weUlzTWVldGluZ1xuICAgICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgICBjb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgICAgY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgIGNyZWF0b3JcbiAgICAgICAgZGFpbHlUYXNrTGlzdFxuICAgICAgICBkZWxldGVkXG4gICAgICAgIGR1cmF0aW9uXG4gICAgICAgIGVuZERhdGVcbiAgICAgICAgZW5kVGltZVVuc3BlY2lmaWVkXG4gICAgICAgIGV2ZW50SWRcbiAgICAgICAgZXZlbnRUeXBlXG4gICAgICAgIGV4dGVuZGVkUHJvcGVydGllc1xuICAgICAgICBmb2xsb3dVcEV2ZW50SWRcbiAgICAgICAgZm9yRXZlbnRJZFxuICAgICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzXG4gICAgICAgIGd1ZXN0c0Nhbk1vZGlmeVxuICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0c1xuICAgICAgICBoYW5nb3V0TGlua1xuICAgICAgICBoYXJkRGVhZGxpbmVcbiAgICAgICAgaHRtbExpbmtcbiAgICAgICAgaUNhbFVJRFxuICAgICAgICBpZFxuICAgICAgICBpc0JyZWFrXG4gICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICBpc0ZvbGxvd1VwXG4gICAgICAgIGlzTWVldGluZ1xuICAgICAgICBpc01lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgIGlzUG9zdEV2ZW50XG4gICAgICAgIGlzUHJlRXZlbnRcbiAgICAgICAgbGlua3NcbiAgICAgICAgbG9jYXRpb25cbiAgICAgICAgbG9ja2VkXG4gICAgICAgIG1heEF0dGVuZGVlc1xuICAgICAgICBtZXRob2RcbiAgICAgICAgbW9kaWZpYWJsZVxuICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICBuZWdhdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZVxuICAgICAgICBub3Rlc1xuICAgICAgICBvcmdhbml6ZXJcbiAgICAgICAgb3JpZ2luYWxBbGxEYXlcbiAgICAgICAgb3JpZ2luYWxTdGFydERhdGVcbiAgICAgICAgb3JpZ2luYWxUaW1lem9uZVxuICAgICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICBwb3NpdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgIHBvc2l0aXZlSW1wYWN0VGltZVxuICAgICAgICBwb3N0RXZlbnRJZFxuICAgICAgICBwcmVFdmVudElkXG4gICAgICAgIHByZWZlcnJlZERheU9mV2Vla1xuICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2VcbiAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICAgICAgcHJlZmVycmVkVGltZVxuICAgICAgICBwcmlvcml0eVxuICAgICAgICBwcml2YXRlQ29weVxuICAgICAgICByZWN1cnJlbmNlXG4gICAgICAgIHJlY3VycmVuY2VSdWxlXG4gICAgICAgIHJlY3VycmluZ0V2ZW50SWRcbiAgICAgICAgc2VuZFVwZGF0ZXNcbiAgICAgICAgc29mdERlYWRsaW5lXG4gICAgICAgIHNvdXJjZVxuICAgICAgICBzdGFydERhdGVcbiAgICAgICAgc3RhdHVzXG4gICAgICAgIHN1bW1hcnlcbiAgICAgICAgdGFza0lkXG4gICAgICAgIHRhc2tUeXBlXG4gICAgICAgIHRpbWVCbG9ja2luZ1xuICAgICAgICB0aW1lem9uZVxuICAgICAgICB0aXRsZVxuICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgdW5saW5rXG4gICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICAgIHVzZXJJZFxuICAgICAgICB1c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHlcbiAgICAgICAgdXNlck1vZGlmaWVkQ2F0ZWdvcmllc1xuICAgICAgICB1c2VyTW9kaWZpZWREdXJhdGlvblxuICAgICAgICB1c2VyTW9kaWZpZWRJc0JyZWFrXG4gICAgICAgIHVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgIHVzZXJNb2RpZmllZElzTWVldGluZ1xuICAgICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlXG4gICAgICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWxcbiAgICAgICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzXG4gICAgICAgIHVzZXJNb2RpZmllZFRpbWVCbG9ja2luZ1xuICAgICAgICB1c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZVxuICAgICAgICB2aXNpYmlsaXR5XG4gICAgICAgIHdlZWtseVRhc2tMaXN0XG4gICAgICAgIGJ5V2Vla0RheVxuICAgICAgICBsb2NhbFN5bmNlZFxuICAgICAgICB1c2VyTW9kaWZpZWRDb2xvclxuICAgICAgICBjb3B5Q29sb3JcbiAgICAgIH1cbiAgICB9XG4gICAgYDtcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IEV2ZW50OiBFdmVudFR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgaWRzLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/LkV2ZW50O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gbGlzdCBpZHMgd2l0aCBpZHMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHRhZ0V2ZW50c0ZvckRhaWx5T3JXZWVrbHlUYXNrID0gYXN5bmMgKFxuICBldmVudHM6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXVxuKTogUHJvbWlzZTxFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlW10gfCBudWxsPiA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgZmlsdGVyZWRFdmVudHMgPSBldmVudHMuZmlsdGVyKChlKSA9PiBlLnJlY3VycmluZ0V2ZW50SWQpO1xuICAgIGlmIChmaWx0ZXJlZEV2ZW50cz8ubGVuZ3RoID4gMCkge1xuICAgICAgY29uc3Qgb3JpZ2luYWxFdmVudHMgPSBhd2FpdCBsaXN0RXZlbnRzV2l0aElkcyhcbiAgICAgICAgXy51bmlxKGZpbHRlcmVkRXZlbnRzLm1hcCgoZSkgPT4gZT8ucmVjdXJyaW5nRXZlbnRJZCkpXG4gICAgICApO1xuICAgICAgaWYgKG9yaWdpbmFsRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGNvbnN0IHRhZ2dlZEZpbHRlcmVkRXZlbnRzID0gZmlsdGVyZWRFdmVudHMubWFwKChlKSA9PlxuICAgICAgICAgIHRhZ0V2ZW50Rm9yRGFpbHlPcldlZWtseVRhc2soXG4gICAgICAgICAgICBlLFxuICAgICAgICAgICAgb3JpZ2luYWxFdmVudHMuZmluZCgob2UpID0+IG9lLmlkID09PSBlLnJlY3VycmluZ0V2ZW50SWQpXG4gICAgICAgICAgKVxuICAgICAgICApO1xuICAgICAgICAvLyByZWNvbnN0cnVjdCBldmVudHNcbiAgICAgICAgY29uc3QgbmV3RXZlbnRzID0gZXZlbnRzLm1hcCgoZSkgPT4ge1xuICAgICAgICAgIGlmIChlPy5yZWN1cnJpbmdFdmVudElkKSB7XG4gICAgICAgICAgICBjb25zdCB0YWdnZWRGaWx0ZXJlZEV2ZW50ID0gdGFnZ2VkRmlsdGVyZWRFdmVudHMuZmluZChcbiAgICAgICAgICAgICAgKHRlKSA9PiB0ZT8uZXZlbnRJZCA9PT0gZT8uZXZlbnRJZFxuICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIGlmICh0YWdnZWRGaWx0ZXJlZEV2ZW50Py5ldmVudElkKSB7XG4gICAgICAgICAgICAgIHJldHVybiB0YWdnZWRGaWx0ZXJlZEV2ZW50O1xuICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgcmV0dXJuIGU7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICAgIHJldHVybiBlO1xuICAgICAgICB9KTtcbiAgICAgICAgcmV0dXJuIG5ld0V2ZW50cztcbiAgICAgIH1cbiAgICAgIGNvbnNvbGUubG9nKCd0YWdFdmVudHNGb3JEYWlseW9yV2Vla2x5VGFzazogb3JpZ2luYWxFdmVudHMgaXMgZW1wdHknKTtcbiAgICAgIHJldHVybiBldmVudHM7XG4gICAgfVxuICAgIHJldHVybiBldmVudHM7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB0byB0YWcgZXZlbnRzIGZvciBkYWlseSBvciB3ZWVrbHkgdGFzaycpO1xuICB9XG59O1xuXG4vLyByZWN1cnJpbmcgZXZlbnRzIGFyZSBub3QgdGFnZ2VkIHdpdGggd2Vla2x5IG9yIGRhaWx5IHRhc2sgYm9vbGVhbiBzbyBuZWVkIHRvIGJlIGRvbmUgbWFudWFsbHlcbmV4cG9ydCBjb25zdCB0YWdFdmVudEZvckRhaWx5T3JXZWVrbHlUYXNrID0gKFxuICBldmVudFRvU3VibWl0OiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlLFxuICBldmVudDogRXZlbnRQbHVzVHlwZVxuKSA9PiB7XG4gIC8vIHZhbGlkYXRlXG4gIGlmICghZXZlbnQ/LmlkKSB7XG4gICAgY29uc29sZS5sb2coJ25vIG9yaWdpbmFsIGV2ZW50IGluc2lkZSB0YWdFdmVudEZvckRhaWx5c09yV2Vla2x5VGFzaycpO1xuICAgIHJldHVybiBudWxsO1xuICB9XG5cbiAgaWYgKCFldmVudFRvU3VibWl0Py5ldmVudElkKSB7XG4gICAgY29uc29sZS5sb2coJ25vIGV2ZW50VG9TdWJtaXQgaW5zaWRlIHRhZ0V2ZW50Rm9yRGFpbHlPcldlZWtseVRhc2snKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIGlmIChldmVudFRvU3VibWl0Py5yZWN1cnJpbmdFdmVudElkKSB7XG4gICAgLy8gY29uc3Qgb3JpZ2luYWxFdmVudCA9IGF3YWl0IGdldEV2ZW50RnJvbVByaW1hcnlLZXkoZXZlbnQucmVjdXJyaW5nRXZlbnRJZClcbiAgICBpZiAoZXZlbnQ/LndlZWtseVRhc2tMaXN0KSB7XG4gICAgICByZXR1cm4ge1xuICAgICAgICAuLi5ldmVudFRvU3VibWl0LFxuICAgICAgICB3ZWVrbHlUYXNrTGlzdDogZXZlbnQud2Vla2x5VGFza0xpc3QsXG4gICAgICB9O1xuICAgIH1cbiAgICBpZiAoZXZlbnQ/LmRhaWx5VGFza0xpc3QpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIC4uLmV2ZW50VG9TdWJtaXQsXG4gICAgICAgIGRhaWx5VGFza0xpc3Q6IGV2ZW50LmRhaWx5VGFza0xpc3QsXG4gICAgICB9O1xuICAgIH1cbiAgICByZXR1cm4gZXZlbnRUb1N1Ym1pdDtcbiAgfVxuICByZXR1cm4gZXZlbnRUb1N1Ym1pdDtcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZVVzZXJQbGFubmVyUmVxdWVzdEJvZHkgPSAoXG4gIHVzZXJQcmVmZXJlbmNlOiBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIHVzZXJJZDogc3RyaW5nLFxuICB3b3JrVGltZXM6IFdvcmtUaW1lVHlwZVtdLFxuICBob3N0SWQ6IHN0cmluZ1xuKTogVXNlclBsYW5uZXJSZXF1ZXN0Qm9keVR5cGUgPT4ge1xuICBjb25zdCB7XG4gICAgbWF4V29ya0xvYWRQZXJjZW50LFxuICAgIGJhY2tUb0JhY2tNZWV0aW5ncyxcbiAgICBtYXhOdW1iZXJPZk1lZXRpbmdzLFxuICAgIG1pbk51bWJlck9mQnJlYWtzLFxuICB9ID0gdXNlclByZWZlcmVuY2U7XG4gIGNvbnN0IHVzZXI6IFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlID0ge1xuICAgIGlkOiB1c2VySWQsXG4gICAgbWF4V29ya0xvYWRQZXJjZW50LFxuICAgIGJhY2tUb0JhY2tNZWV0aW5ncyxcbiAgICBtYXhOdW1iZXJPZk1lZXRpbmdzLFxuICAgIG1pbk51bWJlck9mQnJlYWtzLFxuICAgIHdvcmtUaW1lcyxcbiAgICBob3N0SWQsXG4gIH07XG4gIHJldHVybiB1c2VyO1xufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlVXNlclBsYW5uZXJSZXF1ZXN0Qm9keUZvckV4dGVybmFsQXR0ZW5kZWUgPSAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB3b3JrVGltZXM6IFdvcmtUaW1lVHlwZVtdLFxuICBob3N0SWQ6IHN0cmluZ1xuKTogVXNlclBsYW5uZXJSZXF1ZXN0Qm9keVR5cGUgPT4ge1xuICAvLyBhZGQgZGVmYXVsdCB2YWx1ZXMgZm9yIHVzZXIgcmVxdWVzdCBib2R5XG4gIGNvbnN0IHVzZXI6IFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlID0ge1xuICAgIGlkOiB1c2VySWQsXG4gICAgbWF4V29ya0xvYWRQZXJjZW50OiAxMDAsXG4gICAgYmFja1RvQmFja01lZXRpbmdzOiBmYWxzZSxcbiAgICBtYXhOdW1iZXJPZk1lZXRpbmdzOiA5OSxcbiAgICBtaW5OdW1iZXJPZkJyZWFrczogMCxcbiAgICB3b3JrVGltZXMsXG4gICAgaG9zdElkLFxuICB9O1xuICByZXR1cm4gdXNlcjtcbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzRXZlbnRzRm9yT3B0YVBsYW5uZXJGb3JNYWluSG9zdCA9IGFzeW5jIChcbiAgbWFpbkhvc3RJZDogc3RyaW5nLFxuICBhbGxIb3N0RXZlbnRzOiBFdmVudFBsdXNUeXBlW10sXG4gIHdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nLFxuICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICBvbGRIb3N0RXZlbnRzOiBFdmVudFBsdXNUeXBlW10sXG4gIG5ld0hvc3RCdWZmZXJUaW1lcz86IEJ1ZmZlclRpbWVPYmplY3RUeXBlW11cbik6IFByb21pc2U8UmV0dXJuQm9keUZvckhvc3RGb3JPcHRhcGxhbm5lclByZXBUeXBlPiA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgbmV3QnVmZmVyVGltZUFycmF5OiBFdmVudFBsdXNUeXBlW10gPSBbXTtcblxuICAgIGZvciAoY29uc3QgbmV3SG9zdEJ1ZmZlclRpbWUgb2YgbmV3SG9zdEJ1ZmZlclRpbWVzKSB7XG4gICAgICBpZiAobmV3SG9zdEJ1ZmZlclRpbWU/LmJlZm9yZUV2ZW50Py5pZCkge1xuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBuZXdIb3N0QnVmZmVyVGltZT8uYmVmb3JlRXZlbnQsXG4gICAgICAgICAgJyBuZXdUaW1lQmxvY2tpbmc/LmJlZm9yZUV2ZW50J1xuICAgICAgICApO1xuICAgICAgICBuZXdCdWZmZXJUaW1lQXJyYXkucHVzaChuZXdIb3N0QnVmZmVyVGltZS5iZWZvcmVFdmVudCk7XG4gICAgICB9XG5cbiAgICAgIGlmIChuZXdIb3N0QnVmZmVyVGltZT8uYWZ0ZXJFdmVudD8uaWQpIHtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgbmV3SG9zdEJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQsXG4gICAgICAgICAgJyBuZXdUaW1lQmxvY2tpbmc/LmFmdGVyRXZlbnQnXG4gICAgICAgICk7XG4gICAgICAgIG5ld0J1ZmZlclRpbWVBcnJheS5wdXNoKG5ld0hvc3RCdWZmZXJUaW1lLmFmdGVyRXZlbnQpO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IG1vZGlmaWVkQWxsSG9zdEV2ZW50cyA9IF8uY2xvbmVEZWVwKGFsbEhvc3RFdmVudHMpO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBtb2RpZmllZEFsbEhvc3RFdmVudHMsXG4gICAgICAnIG1vZGlmaWVkQWxsSG9zdEV2ZW50cyBpbnNpZGUgcHJvY2Vzc0V2ZW50c0Zvck9wdGFQbGFubmVyRm9yTWFpbkhvc3QnXG4gICAgKTtcblxuICAgIGlmIChuZXdCdWZmZXJUaW1lQXJyYXk/Lmxlbmd0aCA+IDApIHtcbiAgICAgIG1vZGlmaWVkQWxsSG9zdEV2ZW50cy5wdXNoKC4uLm5ld0J1ZmZlclRpbWVBcnJheSk7XG4gICAgfVxuXG4gICAgLy8gZ2V0IHVzZXIgcHJlZmVyZW5jZXNcbiAgICBjb25zdCB1c2VyUHJlZmVyZW5jZXMgPSBhd2FpdCBnZXRVc2VyUHJlZmVyZW5jZXMobWFpbkhvc3RJZCk7XG5cbiAgICAvLyBnZXQgZ2xvYmFsIHByaW1hcnkgY2FsZW5kYXJcbiAgICBjb25zdCBnbG9iYWxQcmltYXJ5Q2FsZW5kYXIgPSBhd2FpdCBnZXRHbG9iYWxDYWxlbmRhcihtYWluSG9zdElkKTtcblxuICAgIC8vIGdlbmVyYXRlIHRpbWVzbG90c1xuXG4gICAgY29uc3QgZGlmZkRheXMgPSBkYXlqcyh3aW5kb3dFbmREYXRlLnNsaWNlKDAsIDE5KSkuZGlmZihcbiAgICAgIGRheWpzKHdpbmRvd1N0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLFxuICAgICAgJ2RheSdcbiAgICApO1xuXG4gICAgY29uc3QgbW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzOiBFdmVudFBsdXNUeXBlW10gPSBbXTtcblxuICAgIGNvbnN0IHN0YXJ0RGF0ZXNGb3JFYWNoRGF5ID0gW107XG5cbiAgICBmb3IgKGxldCBpID0gMDsgaSA8PSBkaWZmRGF5czsgaSsrKSB7XG4gICAgICBzdGFydERhdGVzRm9yRWFjaERheS5wdXNoKFxuICAgICAgICBkYXlqcyh3aW5kb3dTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmFkZChpLCAnZGF5JylcbiAgICAgICAgICAuZm9ybWF0KClcbiAgICAgICk7XG4gICAgfVxuXG4gICAgLy8gYWRkIGJyZWFrcyB0byBhbGwgZXZlbnRzXG4gICAgbGV0IHBhcmVudEJyZWFrczogRXZlbnRQbHVzVHlwZVtdID0gW107XG5cbiAgICBjb25zdCBicmVha3MgPSBhd2FpdCBnZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF0ZShcbiAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgIG1haW5Ib3N0SWQsXG4gICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgZ2xvYmFsUHJpbWFyeUNhbGVuZGFyPy5pZFxuICAgICk7XG5cbiAgICBicmVha3MuZm9yRWFjaCgoYikgPT4gY29uc29sZS5sb2coYiwgJyBnZW5lcmF0ZWRCcmVha3MnKSk7XG5cbiAgICBpZiAoYnJlYWtzPy5sZW5ndGggPiAwKSB7XG4gICAgICAvLyBtb2RpZmllZEFsbEV2ZW50cy5wdXNoKC4uLmJyZWFrcylcbiAgICAgIGNvbnN0IGFsbEV2ZW50c1dpdGhEdXBsaWNhdGVGcmVlQnJlYWtzID0gXy5kaWZmZXJlbmNlQnkoXG4gICAgICAgIG1vZGlmaWVkQWxsSG9zdEV2ZW50cyxcbiAgICAgICAgYnJlYWtzLFxuICAgICAgICAnaWQnXG4gICAgICApO1xuICAgICAgbW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzLnB1c2goLi4uYWxsRXZlbnRzV2l0aER1cGxpY2F0ZUZyZWVCcmVha3MpO1xuICAgICAgbW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzLnB1c2goLi4uYnJlYWtzKTtcbiAgICAgIHBhcmVudEJyZWFrcy5wdXNoKC4uLmJyZWFrcyk7XG4gICAgfSBlbHNlIHtcbiAgICAgIG1vZGlmaWVkQWxsRXZlbnRzV2l0aEJyZWFrcy5wdXNoKC4uLm1vZGlmaWVkQWxsSG9zdEV2ZW50cyk7XG4gICAgfVxuXG4gICAgY29uc3Qgd29ya1RpbWVzID0gZ2VuZXJhdGVXb3JrVGltZXNGb3JJbnRlcm5hbEF0dGVuZGVlKFxuICAgICAgbWFpbkhvc3RJZCxcbiAgICAgIG1haW5Ib3N0SWQsXG4gICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICBob3N0VGltZXpvbmUsXG4gICAgICBob3N0VGltZXpvbmVcbiAgICApO1xuICAgIGNvbnN0IHRpbWVzbG90cyA9IFtdO1xuXG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCBzdGFydERhdGVzRm9yRWFjaERheS5sZW5ndGg7IGkrKykge1xuICAgICAgaWYgKGkgPT09IDApIHtcbiAgICAgICAgLy8gY29uc3QgbW9zdFJlY2VudEV2ZW50ID0gXy5taW5CeShtb2RpZmllZEFsbEV2ZW50c1dpdGhCcmVha3MsIChlKSA9PiBkYXlqcyhlPy5zdGFydERhdGUpLnVuaXgoKSlcbiAgICAgICAgY29uc3QgdGltZXNsb3RzRm9yRGF5ID0gYXdhaXQgZ2VuZXJhdGVUaW1lU2xvdHNMaXRlRm9ySW50ZXJuYWxBdHRlbmRlZShcbiAgICAgICAgICBzdGFydERhdGVzRm9yRWFjaERheT8uW2ldLFxuICAgICAgICAgIG1haW5Ib3N0SWQsXG4gICAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgICAgdHJ1ZVxuICAgICAgICApO1xuICAgICAgICB0aW1lc2xvdHMucHVzaCguLi50aW1lc2xvdHNGb3JEYXkpO1xuICAgICAgICBjb250aW51ZTtcbiAgICAgIH1cbiAgICAgIGNvbnN0IHRpbWVzbG90c0ZvckRheSA9IGF3YWl0IGdlbmVyYXRlVGltZVNsb3RzTGl0ZUZvckludGVybmFsQXR0ZW5kZWUoXG4gICAgICAgIHN0YXJ0RGF0ZXNGb3JFYWNoRGF5Py5baV0sXG4gICAgICAgIG1haW5Ib3N0SWQsXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgIGZhbHNlXG4gICAgICApO1xuICAgICAgdGltZXNsb3RzLnB1c2goLi4udGltZXNsb3RzRm9yRGF5KTtcbiAgICB9XG5cbiAgICAvLyBnZW5lcmF0ZSBldmVudCBwYXJ0c1xuICAgIGNvbnN0IGZpbHRlcmVkQWxsRXZlbnRzID0gXy51bmlxQnkoXG4gICAgICBtb2RpZmllZEFsbEV2ZW50c1dpdGhCcmVha3MuZmlsdGVyKChlKSA9PlxuICAgICAgICB2YWxpZGF0ZUV2ZW50RGF0ZXMoZSwgdXNlclByZWZlcmVuY2VzKVxuICAgICAgKSxcbiAgICAgICdpZCdcbiAgICApO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZmlsdGVyZWRBbGxFdmVudHMsXG4gICAgICAnIGZpbHRlcmVkQWxsRXZlbnRzIGluc2lkZSBwcm9jZXNzRXZlbnRzRm9yT3B0YVBsYW5uZXJGb3JNYWluSG9zdCdcbiAgICApO1xuICAgIGxldCBldmVudFBhcnRzOiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlW10gPSBbXTtcblxuICAgIGNvbnN0IGV2ZW50UGFydE1pbmlzQWNjdW11bGF0ZWQgPSBbXTtcbiAgICBmb3IgKGNvbnN0IGV2ZW50IG9mIGZpbHRlcmVkQWxsRXZlbnRzKSB7XG4gICAgICBjb25zdCBldmVudFBhcnRNaW5pcyA9IGdlbmVyYXRlRXZlbnRQYXJ0c0xpdGUoZXZlbnQsIG1haW5Ib3N0SWQpO1xuICAgICAgZXZlbnRQYXJ0TWluaXNBY2N1bXVsYXRlZC5wdXNoKC4uLmV2ZW50UGFydE1pbmlzKTtcbiAgICB9XG4gICAgY29uc29sZS5sb2coXG4gICAgICBldmVudFBhcnRNaW5pc0FjY3VtdWxhdGVkLFxuICAgICAgJyBldmVudFBhcnRNaW5pc0FjY3VtdWxhdGVkIGluc2lkZSBwcm9jZXNzRXZlbnRzRm9yT3B0YVBsYW5uZXJGb3JNYWluSG9zdCdcbiAgICApO1xuICAgIGNvbnN0IG1vZGlmaWVkRXZlbnRQYXJ0TWluaXNQcmVCdWZmZXIgPVxuICAgICAgbW9kaWZ5RXZlbnRQYXJ0c0Zvck11bHRpcGxlUHJlQnVmZmVyVGltZShldmVudFBhcnRNaW5pc0FjY3VtdWxhdGVkKTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIG1vZGlmaWVkRXZlbnRQYXJ0TWluaXNQcmVCdWZmZXIsXG4gICAgICAnIG1vZGlmaWVkRXZlbnRQYXJ0TWluaXNQcmVCdWZmZXIgaW5zaWRlIHByb2Nlc3NFdmVudHNGb3JPcHRhUGxhbm5lckZvck1haW5Ib3N0J1xuICAgICk7XG4gICAgY29uc3QgbW9kaWZpZWRFdmVudFBhcnRNaW5pc1ByZUFuZFBvc3RCdWZmZXIgPVxuICAgICAgbW9kaWZ5RXZlbnRQYXJ0c0Zvck11bHRpcGxlUG9zdEJ1ZmZlclRpbWUoXG4gICAgICAgIG1vZGlmaWVkRXZlbnRQYXJ0TWluaXNQcmVCdWZmZXJcbiAgICAgICk7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBtb2RpZmllZEV2ZW50UGFydE1pbmlzUHJlQW5kUG9zdEJ1ZmZlcixcbiAgICAgICcgbW9kaWZpZWRFdmVudFBhcnRNaW5pc1ByZUFuZFBvc3RCdWZmZXIgaW5zaWRlIHByb2Nlc3NFdmVudHNGb3JPcHRhUGxhbm5lckZvck1haW5Ib3N0J1xuICAgICk7XG4gICAgY29uc29sZS5sb2coXG4gICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICB3b3JrVGltZXMsXG4gICAgICBob3N0VGltZXpvbmUsXG4gICAgICAnIHVzZXJQcmVmZXJlbmNlcywgd29ya1RpbWVzLCBob3N0VGltZXpvbmUgaW5zaWRlIHByb2Nlc3NFdmVudHNGb3JPcHRhUGxhbm5lckZvck1haW5Ib3N0J1xuICAgICk7XG4gICAgY29uc3QgZm9ybWF0dGVkRXZlbnRQYXJ0czogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZVtdID1cbiAgICAgIG1vZGlmaWVkRXZlbnRQYXJ0TWluaXNQcmVBbmRQb3N0QnVmZmVyLm1hcCgoZSkgPT5cbiAgICAgICAgZm9ybWF0RXZlbnRUeXBlVG9QbGFubmVyRXZlbnQoXG4gICAgICAgICAgZSxcbiAgICAgICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICAgICAgd29ya1RpbWVzLFxuICAgICAgICAgIGhvc3RUaW1lem9uZVxuICAgICAgICApXG4gICAgICApO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZm9ybWF0dGVkRXZlbnRQYXJ0cyxcbiAgICAgICcgZm9ybWF0dGVkRXZlbnRQYXJ0cyBpbnNpZGUgcHJvY2Vzc0V2ZW50c0Zvck9wdGFQbGFubmVyRm9yTWFpbkhvc3QnXG4gICAgKTtcbiAgICBpZiAoZm9ybWF0dGVkRXZlbnRQYXJ0cz8ubGVuZ3RoID4gMCkge1xuICAgICAgZXZlbnRQYXJ0cy5wdXNoKC4uLmZvcm1hdHRlZEV2ZW50UGFydHMpO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZXZlbnRQYXJ0cyxcbiAgICAgICcgZXZlbnRQYXJ0cyBpbnNpZGUgcHJvY2Vzc0V2ZW50c0Zvck9wdGFQbGFubmVyRm9yTWFpbkhvc3QnXG4gICAgKTtcblxuICAgIGlmIChldmVudFBhcnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICBldmVudFBhcnRzLmZvckVhY2goKGUpID0+IGNvbnNvbGUubG9nKGUsICcgZXZlbnRQYXJ0cyBhZnRlciBmb3JtYXR0aW5nJykpO1xuICAgICAgY29uc3QgbmV3RXZlbnRQYXJ0c1dpdGhQcmVmZXJyZWRUaW1lU2V0ID0gZXZlbnRQYXJ0cy5tYXAoKGUpID0+XG4gICAgICAgIHNldFByZWZlcnJlZFRpbWVGb3JVbk1vZGlmaWFibGVFdmVudChcbiAgICAgICAgICBlLFxuICAgICAgICAgIGFsbEhvc3RFdmVudHMuZmluZCgoZikgPT4gZi5pZCA9PT0gZS5ldmVudElkKT8udGltZXpvbmVcbiAgICAgICAgKVxuICAgICAgKTtcbiAgICAgIG5ld0V2ZW50UGFydHNXaXRoUHJlZmVycmVkVGltZVNldC5mb3JFYWNoKChlKSA9PlxuICAgICAgICBjb25zb2xlLmxvZyhlLCAnIG5ld0V2ZW50UGFydHNXaXRoUHJlZmVycmVkVGltZVNldCcpXG4gICAgICApO1xuICAgICAgY29uc3QgbmV3RXZlbnRQYXJ0cyA9IGF3YWl0IHRhZ0V2ZW50c0ZvckRhaWx5T3JXZWVrbHlUYXNrKFxuICAgICAgICBuZXdFdmVudFBhcnRzV2l0aFByZWZlcnJlZFRpbWVTZXRcbiAgICAgICk7XG4gICAgICBuZXdFdmVudFBhcnRzLmZvckVhY2goKGUpID0+XG4gICAgICAgIGNvbnNvbGUubG9nKGUsICcgbmV3RXZlbnRQYXJ0cyBhZnRlciB0YWdFdmVudHNGb3JEYWlseU9yV2Vla2x5VGFzaycpXG4gICAgICApO1xuICAgICAgY29uc3QgdXNlclBsYW5uZXJSZXF1ZXN0Qm9keSA9IGdlbmVyYXRlVXNlclBsYW5uZXJSZXF1ZXN0Qm9keShcbiAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICB1c2VyUHJlZmVyZW5jZXMudXNlcklkLFxuICAgICAgICB3b3JrVGltZXMsXG4gICAgICAgIG1haW5Ib3N0SWRcbiAgICAgICk7XG4gICAgICBjb25zb2xlLmxvZyh1c2VyUGxhbm5lclJlcXVlc3RCb2R5LCAnIHVzZXJQbGFubmVyUmVxdWVzdEJvZHknKTtcblxuICAgICAgY29uc3QgbW9kaWZpZWROZXdFdmVudFBhcnRzOiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlW10gPVxuICAgICAgICBuZXdFdmVudFBhcnRzLm1hcCgoZXZlbnRQYXJ0KSA9PiB7XG4gICAgICAgICAgY29uc3Qgb2xkRXZlbnQgPSBmaWx0ZXJlZEFsbEV2ZW50cy5maW5kKFxuICAgICAgICAgICAgKGV2ZW50KSA9PiBldmVudC5pZCA9PT0gZXZlbnRQYXJ0LmV2ZW50SWRcbiAgICAgICAgICApO1xuICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICBncm91cElkOiBldmVudFBhcnQ/Lmdyb3VwSWQsXG4gICAgICAgICAgICBldmVudElkOiBldmVudFBhcnQ/LmV2ZW50SWQsXG4gICAgICAgICAgICBwYXJ0OiBldmVudFBhcnQ/LnBhcnQsXG4gICAgICAgICAgICBsYXN0UGFydDogZXZlbnRQYXJ0Py5sYXN0UGFydCxcbiAgICAgICAgICAgIG1lZXRpbmdQYXJ0OiBldmVudFBhcnQ/Lm1lZXRpbmdQYXJ0LFxuICAgICAgICAgICAgbWVldGluZ0xhc3RQYXJ0OiBldmVudFBhcnQ/Lm1lZXRpbmdMYXN0UGFydCxcbiAgICAgICAgICAgIG1lZXRpbmdJZDogZXZlbnRQYXJ0Py5tZWV0aW5nSWQsXG4gICAgICAgICAgICBob3N0SWQ6IG1haW5Ib3N0SWQsXG4gICAgICAgICAgICBzdGFydERhdGU6IGRheWpzKGV2ZW50UGFydD8uc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG9sZEV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tOnNzJyksXG4gICAgICAgICAgICBlbmREYXRlOiBkYXlqcyhldmVudFBhcnQ/LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoob2xkRXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW06c3MnKSxcbiAgICAgICAgICAgIHVzZXJJZDogZXZlbnRQYXJ0Py51c2VySWQsXG4gICAgICAgICAgICB1c2VyOiBldmVudFBhcnQ/LnVzZXIsXG4gICAgICAgICAgICBwcmlvcml0eTogZXZlbnRQYXJ0Py5wcmlvcml0eSxcbiAgICAgICAgICAgIGlzUHJlRXZlbnQ6IGV2ZW50UGFydD8uaXNQcmVFdmVudCxcbiAgICAgICAgICAgIGlzUG9zdEV2ZW50OiBldmVudFBhcnQ/LmlzUG9zdEV2ZW50LFxuICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RTY29yZTogZXZlbnRQYXJ0Py5wb3NpdGl2ZUltcGFjdFNjb3JlLFxuICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3RTY29yZTogZXZlbnRQYXJ0Py5uZWdhdGl2ZUltcGFjdFNjb3JlLFxuICAgICAgICAgICAgbW9kaWZpYWJsZTogZXZlbnRQYXJ0Py5tb2RpZmlhYmxlLFxuICAgICAgICAgICAgaXNNZWV0aW5nOiBldmVudFBhcnQ/LmlzTWVldGluZyxcbiAgICAgICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nOiBldmVudFBhcnQ/LmlzRXh0ZXJuYWxNZWV0aW5nLFxuICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlOiBldmVudFBhcnQ/LmlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgICAgICAgIGlzTWVldGluZ01vZGlmaWFibGU6IGV2ZW50UGFydD8uaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgICAgICAgIGRhaWx5VGFza0xpc3Q6IGV2ZW50UGFydD8uZGFpbHlUYXNrTGlzdCxcbiAgICAgICAgICAgIHdlZWtseVRhc2tMaXN0OiBldmVudFBhcnQ/LndlZWtseVRhc2tMaXN0LFxuICAgICAgICAgICAgZ2FwOiBldmVudFBhcnQ/LmdhcCxcbiAgICAgICAgICAgIHRvdGFsV29ya2luZ0hvdXJzOiBldmVudFBhcnQ/LnRvdGFsV29ya2luZ0hvdXJzLFxuICAgICAgICAgICAgaGFyZERlYWRsaW5lOiBldmVudFBhcnQ/LmhhcmREZWFkbGluZSxcbiAgICAgICAgICAgIHNvZnREZWFkbGluZTogZXZlbnRQYXJ0Py5zb2Z0RGVhZGxpbmUsXG4gICAgICAgICAgICBmb3JFdmVudElkOiBldmVudFBhcnQ/LmZvckV2ZW50SWQsXG4gICAgICAgICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2VlazogZXZlbnRQYXJ0Py5wb3NpdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0VGltZTogZXZlbnRQYXJ0Py5wb3NpdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2VlazogZXZlbnRQYXJ0Py5uZWdhdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZTogZXZlbnRQYXJ0Py5uZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgICAgICBwcmVmZXJyZWREYXlPZldlZWs6IGV2ZW50UGFydD8ucHJlZmVycmVkRGF5T2ZXZWVrLFxuICAgICAgICAgICAgcHJlZmVycmVkVGltZTogZXZlbnRQYXJ0Py5wcmVmZXJyZWRUaW1lLFxuICAgICAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U6IGV2ZW50UGFydD8ucHJlZmVycmVkU3RhcnRUaW1lUmFuZ2UsXG4gICAgICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2U6IGV2ZW50UGFydD8ucHJlZmVycmVkRW5kVGltZVJhbmdlLFxuICAgICAgICAgICAgZXZlbnQ6IGV2ZW50UGFydD8uZXZlbnQsXG4gICAgICAgICAgfTtcbiAgICAgICAgfSk7XG5cbiAgICAgIHJldHVybiBtb2RpZmllZE5ld0V2ZW50UGFydHM/Lmxlbmd0aCA+IDBcbiAgICAgICAgPyB7XG4gICAgICAgICAgICB1c2VySWQ6IG1haW5Ib3N0SWQsXG4gICAgICAgICAgICBob3N0SWQ6IG1haW5Ib3N0SWQsXG4gICAgICAgICAgICBldmVudFBhcnRzOiBtb2RpZmllZE5ld0V2ZW50UGFydHMsXG4gICAgICAgICAgICBhbGxFdmVudHM6IGZpbHRlcmVkQWxsRXZlbnRzLFxuICAgICAgICAgICAgYnJlYWtzOiBwYXJlbnRCcmVha3MsXG4gICAgICAgICAgICBvbGRFdmVudHM6IG9sZEhvc3RFdmVudHMsXG4gICAgICAgICAgICB0aW1lc2xvdHMsXG4gICAgICAgICAgICB1c2VyUGxhbm5lclJlcXVlc3RCb2R5LFxuICAgICAgICAgIH1cbiAgICAgICAgOiBudWxsO1xuICAgIH1cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZSxcbiAgICAgICcgdW5hYmxlIHRvIHByb2Nlc3MgZXZlbnRzIGZvciBvcHRhcGxhbm5lciBmb3IgaG9zdCBhdHRlbmRlZSdcbiAgICApO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0V2ZW50c0Zvck9wdGFQbGFubmVyRm9ySW50ZXJuYWxBdHRlbmRlZXMgPSBhc3luYyAoXG4gIG1haW5Ib3N0SWQ6IHN0cmluZyxcbiAgYWxsRXZlbnRzOiBFdmVudFBsdXNUeXBlW10sXG4gIHdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nLFxuICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICBpbnRlcm5hbEF0dGVuZGVlczogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdLFxuICBvbGRFdmVudHM6IEV2ZW50UGx1c1R5cGVbXSxcbiAgb2xkTWVldGluZ0V2ZW50cz86IEV2ZW50TWVldGluZ1BsdXNUeXBlW10sXG4gIG5ld01lZXRpbmdFdmVudHM/OiBFdmVudE1lZXRpbmdQbHVzVHlwZVtdLFxuICBuZXdIb3N0QnVmZmVyVGltZXM/OiBCdWZmZXJUaW1lT2JqZWN0VHlwZVtdXG4pOiBQcm9taXNlPFJldHVybkJvZHlGb3JBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGU+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBuZXdCdWZmZXJUaW1lQXJyYXk6IEV2ZW50UGx1c1R5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBuZXdIb3N0QnVmZmVyVGltZSBvZiBuZXdIb3N0QnVmZmVyVGltZXMpIHtcbiAgICAgIGlmIChuZXdIb3N0QnVmZmVyVGltZT8uYmVmb3JlRXZlbnQ/LmlkKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIG5ld0hvc3RCdWZmZXJUaW1lPy5iZWZvcmVFdmVudCxcbiAgICAgICAgICAnIG5ld1RpbWVCbG9ja2luZz8uYmVmb3JlRXZlbnQnXG4gICAgICAgICk7XG4gICAgICAgIG5ld0J1ZmZlclRpbWVBcnJheS5wdXNoKG5ld0hvc3RCdWZmZXJUaW1lLmJlZm9yZUV2ZW50KTtcbiAgICAgIH1cblxuICAgICAgaWYgKG5ld0hvc3RCdWZmZXJUaW1lPy5hZnRlckV2ZW50Py5pZCkge1xuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBuZXdIb3N0QnVmZmVyVGltZT8uYWZ0ZXJFdmVudCxcbiAgICAgICAgICAnIG5ld1RpbWVCbG9ja2luZz8uYWZ0ZXJFdmVudCdcbiAgICAgICAgKTtcbiAgICAgICAgbmV3QnVmZmVyVGltZUFycmF5LnB1c2gobmV3SG9zdEJ1ZmZlclRpbWUuYWZ0ZXJFdmVudCk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgb2xkTWVldGluZ0V2ZW50cz8uZm9yRWFjaCgobykgPT4gY29uc29sZS5sb2cobywgJyBvbGRNZWV0aW5nRXZlbnRzJykpO1xuICAgIGludGVybmFsQXR0ZW5kZWVzPy5mb3JFYWNoKChpKSA9PlxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGksXG4gICAgICAgICcgaW50ZXJuYWxBdHRlbmRlZXMgaW5zaWRlIHByb2Nlc3NFdmVudHNGb3JPcHRhUGxhbm5lckZvckludGVybmFsQXR0ZW5kZWVzJ1xuICAgICAgKVxuICAgICk7XG4gICAgY29uc3QgZmlsdGVyZWRPbGRNZWV0aW5nRXZlbnRzID0gb2xkTWVldGluZ0V2ZW50c1xuICAgICAgPy5tYXAoKG0pID0+IHtcbiAgICAgICAgY29uc3QgZm91bmRJbmRleCA9IGFsbEV2ZW50cz8uZmluZEluZGV4KChhKSA9PiBhPy5pZCA9PT0gbT8uaWQpO1xuXG4gICAgICAgIGlmIChmb3VuZEluZGV4ID4gLTEpIHtcbiAgICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgICAgfVxuICAgICAgICByZXR1cm4gbTtcbiAgICAgIH0pXG4gICAgICA/LmZpbHRlcigoZSkgPT4gISFlKTtcblxuICAgIGZpbHRlcmVkT2xkTWVldGluZ0V2ZW50cz8uZm9yRWFjaCgoZSkgPT5cbiAgICAgIGNvbnNvbGUubG9nKGUsICcgZmlsdGVyZWRPbGRNZWV0aW5nRXZlbnRzJylcbiAgICApO1xuICAgIGNvbnN0IG1vZGlmaWVkQWxsRXZlbnRzID0gXy5jbG9uZURlZXAoYWxsRXZlbnRzKT8uZmlsdGVyKChlKSA9PiB7XG4gICAgICBpZiAoZmlsdGVyZWRPbGRNZWV0aW5nRXZlbnRzPy5bMF0/LmlkKSB7XG4gICAgICAgIGNvbnN0IGZvdW5kSW5kZXggPSBmaWx0ZXJlZE9sZE1lZXRpbmdFdmVudHM/LmZpbmRJbmRleChcbiAgICAgICAgICAobSkgPT4gbT8uaWQgPT09IGU/LmlkXG4gICAgICAgICk7XG4gICAgICAgIGlmIChmb3VuZEluZGV4ID4gLTEpIHtcbiAgICAgICAgICByZXR1cm4gZmFsc2U7XG4gICAgICAgIH1cbiAgICAgICAgcmV0dXJuIHRydWU7XG4gICAgICB9XG4gICAgICByZXR1cm4gdHJ1ZTtcbiAgICB9KTtcblxuICAgIC8vIGFkZCBzbWFydCBtZWV0aW5nIGV2ZW50cyB0byBhbGwgZXZlbnRzXG4gICAgaWYgKGZpbHRlcmVkT2xkTWVldGluZ0V2ZW50cz8uWzBdPy5pZCkge1xuICAgICAgbW9kaWZpZWRBbGxFdmVudHMucHVzaChcbiAgICAgICAgLi4uZmlsdGVyZWRPbGRNZWV0aW5nRXZlbnRzPy5tYXAoKGEpID0+XG4gICAgICAgICAgY29udmVydE1lZXRpbmdQbHVzVHlwZVRvRXZlbnRQbHVzVHlwZShhKVxuICAgICAgICApXG4gICAgICApO1xuICAgIH1cblxuICAgIGlmIChuZXdCdWZmZXJUaW1lQXJyYXk/Lmxlbmd0aCA+IDApIHtcbiAgICAgIG1vZGlmaWVkQWxsRXZlbnRzLnB1c2goLi4ubmV3QnVmZmVyVGltZUFycmF5KTtcbiAgICB9XG5cbiAgICBpZiAobmV3TWVldGluZ0V2ZW50cz8ubGVuZ3RoID4gMCkge1xuICAgICAgLy8gYWRkIG5ld2x5IGdlbmVyYXRlZCBob3N0IGV2ZW50IHRvIHJlc3RcbiAgICAgIG1vZGlmaWVkQWxsRXZlbnRzLnB1c2goXG4gICAgICAgIC4uLm5ld01lZXRpbmdFdmVudHM/Lm1hcCgobSkgPT5cbiAgICAgICAgICBjb252ZXJ0TWVldGluZ1BsdXNUeXBlVG9FdmVudFBsdXNUeXBlKG0pXG4gICAgICAgIClcbiAgICAgICk7XG4gICAgfVxuXG4gICAgbW9kaWZpZWRBbGxFdmVudHM/LmZvckVhY2goKGUpID0+IGNvbnNvbGUubG9nKGUsICcgbW9kaWZpZWRBbGxFdmVudHMnKSk7XG5cbiAgICAvLyBnZXQgdXNlciBwcmVmZXJlbmNlc1xuICAgIGNvbnN0IHVuZmlsdGVyZWRVc2VyUHJlZmVyZW5jZXM6IFVzZXJQcmVmZXJlbmNlVHlwZVtdID0gW107XG4gICAgZm9yIChjb25zdCBpbnRlcm5hbEF0dGVuZGVlIG9mIGludGVybmFsQXR0ZW5kZWVzKSB7XG4gICAgICBjb25zdCB1c2VyUHJlZmVyZW5jZSA9IGF3YWl0IGdldFVzZXJQcmVmZXJlbmNlcyhpbnRlcm5hbEF0dGVuZGVlPy51c2VySWQpO1xuICAgICAgdW5maWx0ZXJlZFVzZXJQcmVmZXJlbmNlcy5wdXNoKHVzZXJQcmVmZXJlbmNlKTtcbiAgICB9XG5cbiAgICBjb25zdCB1c2VyUHJlZmVyZW5jZXM6IFVzZXJQcmVmZXJlbmNlVHlwZVtdID0gXy51bmlxV2l0aChcbiAgICAgIHVuZmlsdGVyZWRVc2VyUHJlZmVyZW5jZXMsXG4gICAgICBfLmlzRXF1YWxcbiAgICApO1xuXG4gICAgLy8gZ2xvYmFsIHByaW1hcnkgY2FsZW5kYXJzXG4gICAgY29uc3QgdW5maWx0ZXJlZEdsb2JhbFByaW1hcnlDYWxlbmRhcnM6IENhbGVuZGFyVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IGludGVybmFsQXR0ZW5kZWUgb2YgaW50ZXJuYWxBdHRlbmRlZXMpIHtcbiAgICAgIGNvbnN0IGdsb2JhbFByaW1hcnlDYWxlbmRhciA9IGF3YWl0IGdldEdsb2JhbENhbGVuZGFyKFxuICAgICAgICBpbnRlcm5hbEF0dGVuZGVlPy51c2VySWRcbiAgICAgICk7XG4gICAgICB1bmZpbHRlcmVkR2xvYmFsUHJpbWFyeUNhbGVuZGFycy5wdXNoKGdsb2JhbFByaW1hcnlDYWxlbmRhcik7XG4gICAgfVxuXG4gICAgY29uc3QgZ2xvYmFsUHJpbWFyeUNhbGVuZGFycyA9IF8udW5pcVdpdGgoXG4gICAgICB1bmZpbHRlcmVkR2xvYmFsUHJpbWFyeUNhbGVuZGFycyxcbiAgICAgIF8uaXNFcXVhbFxuICAgICk7XG5cbiAgICBnbG9iYWxQcmltYXJ5Q2FsZW5kYXJzPy5mb3JFYWNoKChjKSA9PlxuICAgICAgY29uc29sZS5sb2coYywgJyBnbG9iYWxQcmltYXJ5Q2FsZW5kYXJzJylcbiAgICApO1xuXG4gICAgY29uc3QgbW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzOiBFdmVudFBsdXNUeXBlW10gPSBbXTtcblxuICAgIC8vIGFkZCBicmVha3MgdG8gYWxsIGV2ZW50c1xuICAgIGxldCBwYXJlbnRCcmVha3M6IEV2ZW50UGx1c1R5cGVbXSA9IFtdO1xuICAgIGZvciAoY29uc3QgdXNlclByZWZlcmVuY2Ugb2YgdXNlclByZWZlcmVuY2VzKSB7XG4gICAgICBjb25zdCBnbG9iYWxQcmltYXJ5Q2FsZW5kYXIgPSBnbG9iYWxQcmltYXJ5Q2FsZW5kYXJzPy5maW5kKFxuICAgICAgICAoZykgPT4gZz8udXNlcklkID09PSB1c2VyUHJlZmVyZW5jZT8udXNlcklkXG4gICAgICApO1xuICAgICAgaWYgKCFnbG9iYWxQcmltYXJ5Q2FsZW5kYXIpIHtcbiAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBnbG9iYWwgcHJpbWFyeSBjYWxlbmRhciBmb3VuZCcpO1xuICAgICAgfVxuICAgICAgY29uc3QgdXNlcklkID0gdXNlclByZWZlcmVuY2U/LnVzZXJJZDtcblxuICAgICAgY29uc3QgYnJlYWtzID0gYXdhaXQgZ2VuZXJhdGVCcmVha0V2ZW50c0ZvckRhdGUoXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlLFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICBnbG9iYWxQcmltYXJ5Q2FsZW5kYXI/LmlkXG4gICAgICApO1xuXG4gICAgICBicmVha3MuZm9yRWFjaCgoYikgPT4gY29uc29sZS5sb2coYiwgJyBnZW5lcmF0ZWRCcmVha3MnKSk7XG5cbiAgICAgIGlmIChicmVha3M/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgLy8gbW9kaWZpZWRBbGxFdmVudHMucHVzaCguLi5icmVha3MpXG4gICAgICAgIGNvbnN0IGFsbEV2ZW50c1dpdGhEdXBsaWNhdGVGcmVlQnJlYWtzID0gXy5kaWZmZXJlbmNlQnkoXG4gICAgICAgICAgbW9kaWZpZWRBbGxFdmVudHMsXG4gICAgICAgICAgYnJlYWtzLFxuICAgICAgICAgICdpZCdcbiAgICAgICAgKTtcbiAgICAgICAgbW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzLnB1c2goXG4gICAgICAgICAgLi4uYWxsRXZlbnRzV2l0aER1cGxpY2F0ZUZyZWVCcmVha3M/LmZpbHRlcihcbiAgICAgICAgICAgIChlKSA9PiBlPy51c2VySWQgPT09IHVzZXJJZFxuICAgICAgICAgIClcbiAgICAgICAgKTtcbiAgICAgICAgbW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzLnB1c2goLi4uYnJlYWtzKTtcbiAgICAgICAgcGFyZW50QnJlYWtzLnB1c2goLi4uYnJlYWtzKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIG1vZGlmaWVkQWxsRXZlbnRzV2l0aEJyZWFrcy5wdXNoKFxuICAgICAgICAgIC4uLm1vZGlmaWVkQWxsRXZlbnRzPy5maWx0ZXIoKGUpID0+IGU/LnVzZXJJZCA9PT0gdXNlcklkKVxuICAgICAgICApO1xuICAgICAgfVxuICAgIH1cblxuICAgIG1vZGlmaWVkQWxsRXZlbnRzV2l0aEJyZWFrcz8uZm9yRWFjaCgobSkgPT5cbiAgICAgIGNvbnNvbGUubG9nKG0sICcgbW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzJylcbiAgICApO1xuXG4gICAgLy8gZ2VuZXJhdGUgdGltZXNsb3RzXG5cbiAgICBjb25zdCBkaWZmRGF5cyA9IGRheWpzKHdpbmRvd0VuZERhdGUuc2xpY2UoMCwgMTkpKS5kaWZmKFxuICAgICAgZGF5anMod2luZG93U3RhcnREYXRlLnNsaWNlKDAsIDE5KSksXG4gICAgICAnZGF5J1xuICAgICk7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBkaWZmRGF5cyxcbiAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICAnIGRpZmZEYXlzLCB3aW5kb3dFbmREYXRlLCB3aW5kb3dTdGFydERhdGUnXG4gICAgKTtcbiAgICBjb25zdCBzdGFydERhdGVzRm9yRWFjaERheSA9IFtdO1xuXG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPD0gZGlmZkRheXM7IGkrKykge1xuICAgICAgc3RhcnREYXRlc0ZvckVhY2hEYXkucHVzaChcbiAgICAgICAgZGF5anMod2luZG93U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5hZGQoaSwgJ2RheScpXG4gICAgICAgICAgLmZvcm1hdCgpXG4gICAgICApO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKHN0YXJ0RGF0ZXNGb3JFYWNoRGF5LCAnIHN0YXJ0RGF0ZXNGb3JFYWNoRGF5Jyk7XG5cbiAgICBjb25zdCB1bmZpbHRlcmVkV29ya1RpbWVzOiBXb3JrVGltZVR5cGVbXSA9IFtdO1xuICAgIGZvciAoY29uc3QgaW50ZXJuYWxBdHRlbmRlZSBvZiBpbnRlcm5hbEF0dGVuZGVlcykge1xuICAgICAgY29uc3QgdXNlclByZWZlcmVuY2UgPSB1c2VyUHJlZmVyZW5jZXMuZmluZChcbiAgICAgICAgKHUpID0+IHUudXNlcklkID09PSBpbnRlcm5hbEF0dGVuZGVlLnVzZXJJZFxuICAgICAgKTtcbiAgICAgIGNvbnN0IGF0dGVuZGVlVGltZXpvbmUgPSBpbnRlcm5hbEF0dGVuZGVlPy50aW1lem9uZTtcbiAgICAgIGNvbnN0IHdvcmtUaW1lc0ZvckF0dGVuZGVlID0gZ2VuZXJhdGVXb3JrVGltZXNGb3JJbnRlcm5hbEF0dGVuZGVlKFxuICAgICAgICBtYWluSG9zdElkLFxuICAgICAgICBpbnRlcm5hbEF0dGVuZGVlLnVzZXJJZCxcbiAgICAgICAgdXNlclByZWZlcmVuY2UsXG4gICAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgICAgYXR0ZW5kZWVUaW1lem9uZVxuICAgICAgKTtcbiAgICAgIHVuZmlsdGVyZWRXb3JrVGltZXMucHVzaCguLi53b3JrVGltZXNGb3JBdHRlbmRlZSk7XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2codW5maWx0ZXJlZFdvcmtUaW1lcywgJ3VuZmlsdGVyZWRXb3JrVGltZXMnKTtcbiAgICBjb25zdCB3b3JrVGltZXM6IFdvcmtUaW1lVHlwZVtdID0gXy51bmlxV2l0aChcbiAgICAgIHVuZmlsdGVyZWRXb3JrVGltZXMsXG4gICAgICBfLmlzRXF1YWxcbiAgICApO1xuXG4gICAgY29uc3QgdW5maWx0ZXJlZFRpbWVzbG90cyA9IFtdO1xuICAgIGNvbnN0IHRpbWVzbG90cyA9IFtdO1xuXG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCBzdGFydERhdGVzRm9yRWFjaERheS5sZW5ndGg7IGkrKykge1xuICAgICAgaWYgKGkgPT09IDApIHtcbiAgICAgICAgZm9yIChjb25zdCBpbnRlcm5hbEF0dGVuZGVlIG9mIGludGVybmFsQXR0ZW5kZWVzKSB7XG4gICAgICAgICAgY29uc3QgdXNlclByZWZlcmVuY2UgPSB1c2VyUHJlZmVyZW5jZXMuZmluZChcbiAgICAgICAgICAgICh1KSA9PiB1LnVzZXJJZCA9PT0gaW50ZXJuYWxBdHRlbmRlZS51c2VySWRcbiAgICAgICAgICApO1xuICAgICAgICAgIC8vIGNvbnN0IG1vc3RSZWNlbnRFdmVudCA9IF8ubWluQnkobW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzLCAoZSkgPT4gZGF5anMoZT8uc3RhcnREYXRlKS51bml4KCkpXG4gICAgICAgICAgY29uc3QgdGltZXNsb3RzRm9yRGF5ID1cbiAgICAgICAgICAgIGF3YWl0IGdlbmVyYXRlVGltZVNsb3RzTGl0ZUZvckludGVybmFsQXR0ZW5kZWUoXG4gICAgICAgICAgICAgIHN0YXJ0RGF0ZXNGb3JFYWNoRGF5Py5baV0sXG4gICAgICAgICAgICAgIG1haW5Ib3N0SWQsXG4gICAgICAgICAgICAgIHVzZXJQcmVmZXJlbmNlLFxuICAgICAgICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgICAgICAgIGludGVybmFsQXR0ZW5kZWU/LnRpbWV6b25lLFxuICAgICAgICAgICAgICB0cnVlXG4gICAgICAgICAgICApO1xuICAgICAgICAgIHVuZmlsdGVyZWRUaW1lc2xvdHMucHVzaCguLi50aW1lc2xvdHNGb3JEYXkpO1xuICAgICAgICB9XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfVxuICAgICAgZm9yIChjb25zdCBpbnRlcm5hbEF0dGVuZGVlIG9mIGludGVybmFsQXR0ZW5kZWVzKSB7XG4gICAgICAgIGNvbnN0IHVzZXJQcmVmZXJlbmNlID0gdXNlclByZWZlcmVuY2VzLmZpbmQoXG4gICAgICAgICAgKHUpID0+IHUudXNlcklkID09PSBpbnRlcm5hbEF0dGVuZGVlLnVzZXJJZFxuICAgICAgICApO1xuICAgICAgICBjb25zdCB0aW1lc2xvdHNGb3JEYXkgPSBhd2FpdCBnZW5lcmF0ZVRpbWVTbG90c0xpdGVGb3JJbnRlcm5hbEF0dGVuZGVlKFxuICAgICAgICAgIHN0YXJ0RGF0ZXNGb3JFYWNoRGF5Py5baV0sXG4gICAgICAgICAgbWFpbkhvc3RJZCxcbiAgICAgICAgICB1c2VyUHJlZmVyZW5jZSxcbiAgICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgICAgaW50ZXJuYWxBdHRlbmRlZT8udGltZXpvbmUsXG4gICAgICAgICAgZmFsc2VcbiAgICAgICAgKTtcbiAgICAgICAgdW5maWx0ZXJlZFRpbWVzbG90cy5wdXNoKC4uLnRpbWVzbG90c0ZvckRheSk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgdGltZXNsb3RzLnB1c2goLi4uXy51bmlxV2l0aCh1bmZpbHRlcmVkVGltZXNsb3RzLCBfLmlzRXF1YWwpKTtcblxuICAgIC8vIGdlbmVyYXRlIGV2ZW50IHBhcnRzXG4gICAgY29uc3QgdW5maWx0ZXJlZEFsbEV2ZW50czogRXZlbnRQbHVzVHlwZVtdID0gW107XG4gICAgZm9yIChjb25zdCBpbnRlcm5hbEF0dGVuZGVlIG9mIGludGVybmFsQXR0ZW5kZWVzKSB7XG4gICAgICBjb25zdCB1c2VyUHJlZmVyZW5jZSA9IHVzZXJQcmVmZXJlbmNlcy5maW5kKFxuICAgICAgICAodSkgPT4gdS51c2VySWQgPT09IGludGVybmFsQXR0ZW5kZWUudXNlcklkXG4gICAgICApO1xuICAgICAgY29uc3QgbW9kaWZpZWRBbGxFdmVudHNXaXRoQnJlYWtzV2l0aFVzZXIgPVxuICAgICAgICBtb2RpZmllZEFsbEV2ZW50c1dpdGhCcmVha3MuZmlsdGVyKFxuICAgICAgICAgIChlKSA9PiBlLnVzZXJJZCA9PT0gaW50ZXJuYWxBdHRlbmRlZS51c2VySWRcbiAgICAgICAgKTtcbiAgICAgIGNvbnN0IGV2ZW50cyA9IG1vZGlmaWVkQWxsRXZlbnRzV2l0aEJyZWFrc1dpdGhVc2VyLmZpbHRlcigoZSkgPT5cbiAgICAgICAgdmFsaWRhdGVFdmVudERhdGVzKGUsIHVzZXJQcmVmZXJlbmNlKVxuICAgICAgKTtcbiAgICAgIHVuZmlsdGVyZWRBbGxFdmVudHMucHVzaCguLi5ldmVudHMpO1xuICAgIH1cbiAgICB1bmZpbHRlcmVkQWxsRXZlbnRzPy5mb3JFYWNoKChlKSA9PiBjb25zb2xlLmxvZyhlLCAnIHVuZmlsdGVyZWRBbGxFdmVudHMnKSk7XG5cbiAgICBjb25zdCBmaWx0ZXJlZEFsbEV2ZW50cyA9IF8udW5pcUJ5KHVuZmlsdGVyZWRBbGxFdmVudHMsICdpZCcpO1xuXG4gICAgZmlsdGVyZWRBbGxFdmVudHM/LmZvckVhY2goKGUpID0+IGNvbnNvbGUubG9nKGUsICcgZmlsdGVyZWRBbGxFdmVudHMnKSk7XG5cbiAgICBsZXQgZXZlbnRQYXJ0czogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZVtdID0gW107XG5cbiAgICBjb25zdCBldmVudFBhcnRNaW5pc0FjY3VtdWxhdGVkID0gW107XG4gICAgZm9yIChjb25zdCBldmVudCBvZiBmaWx0ZXJlZEFsbEV2ZW50cykge1xuICAgICAgLy8gY29uc3QgcHJlZmVycmVkVGltZVJhbmdlcyA9IGF3YWl0IGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQoZXZlbnQ/LmlkKVxuICAgICAgLy8gY29uc3QgZXZlbnRQbHVzOiBFdmVudFBsdXNUeXBlID0geyAuLi5ldmVudCwgcHJlZmVycmVkVGltZVJhbmdlcyB9XG4gICAgICBjb25zdCBldmVudFBhcnRNaW5pcyA9IGdlbmVyYXRlRXZlbnRQYXJ0c0xpdGUoZXZlbnQsIG1haW5Ib3N0SWQpO1xuICAgICAgZXZlbnRQYXJ0TWluaXNBY2N1bXVsYXRlZC5wdXNoKC4uLmV2ZW50UGFydE1pbmlzKTtcbiAgICB9XG5cbiAgICBldmVudFBhcnRNaW5pc0FjY3VtdWxhdGVkPy5mb3JFYWNoKChlKSA9PlxuICAgICAgY29uc29sZS5sb2coZSwgJyBldmVudFBhcnRNaW5pc0FjY3VtdWxhdGVkJylcbiAgICApO1xuICAgIGNvbnN0IG1vZGlmaWVkRXZlbnRQYXJ0TWluaXNQcmVCdWZmZXIgPVxuICAgICAgbW9kaWZ5RXZlbnRQYXJ0c0Zvck11bHRpcGxlUHJlQnVmZmVyVGltZShldmVudFBhcnRNaW5pc0FjY3VtdWxhdGVkKTtcbiAgICBjb25zdCBtb2RpZmllZEV2ZW50UGFydE1pbmlzUHJlQW5kUG9zdEJ1ZmZlciA9XG4gICAgICBtb2RpZnlFdmVudFBhcnRzRm9yTXVsdGlwbGVQb3N0QnVmZmVyVGltZShcbiAgICAgICAgbW9kaWZpZWRFdmVudFBhcnRNaW5pc1ByZUJ1ZmZlclxuICAgICAgKTtcblxuICAgIG1vZGlmaWVkRXZlbnRQYXJ0TWluaXNQcmVBbmRQb3N0QnVmZmVyPy5mb3JFYWNoKChlKSA9PlxuICAgICAgY29uc29sZS5sb2coZSwgJyBtb2RpZmllZEV2ZW50UGFydE1pbmlzUHJlQW5kUG9zdEJ1ZmZlcicpXG4gICAgKTtcblxuICAgIGNvbnN0IGZvcm1hdHRlZEV2ZW50UGFydHM6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSA9IFtdO1xuICAgIGZvciAoY29uc3QgdXNlclByZWZlcmVuY2Ugb2YgdXNlclByZWZlcmVuY2VzKSB7XG4gICAgICBjb25zdCBmb3JtYXR0ZWRFdmVudFBhcnRzRm9yVXNlcjogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZVtdID1cbiAgICAgICAgbW9kaWZpZWRFdmVudFBhcnRNaW5pc1ByZUFuZFBvc3RCdWZmZXJcbiAgICAgICAgICA/LmZpbHRlcigoZSkgPT4gZT8udXNlcklkID09PSB1c2VyUHJlZmVyZW5jZT8udXNlcklkKVxuICAgICAgICAgID8ubWFwKChlKSA9PlxuICAgICAgICAgICAgZm9ybWF0RXZlbnRUeXBlVG9QbGFubmVyRXZlbnQoXG4gICAgICAgICAgICAgIGUsXG4gICAgICAgICAgICAgIHVzZXJQcmVmZXJlbmNlLFxuICAgICAgICAgICAgICB3b3JrVGltZXMsXG4gICAgICAgICAgICAgIGhvc3RUaW1lem9uZVxuICAgICAgICAgICAgKVxuICAgICAgICAgICk7XG5cbiAgICAgIGZvcm1hdHRlZEV2ZW50UGFydHNGb3JVc2VyPy5mb3JFYWNoKChlKSA9PlxuICAgICAgICBjb25zb2xlLmxvZyhlLCAnIGZvcm1hdHRlZEV2ZW50UGFydHNGb3JVc2VyJylcbiAgICAgICk7XG5cbiAgICAgIGZvcm1hdHRlZEV2ZW50UGFydHMucHVzaCguLi5mb3JtYXR0ZWRFdmVudFBhcnRzRm9yVXNlcik7XG4gICAgfVxuXG4gICAgZm9ybWF0dGVkRXZlbnRQYXJ0cz8uZm9yRWFjaCgoZSkgPT4gY29uc29sZS5sb2coZSwgJyBmb3JtYXR0ZWRFdmVudFBhcnRzJykpO1xuXG4gICAgaWYgKGZvcm1hdHRlZEV2ZW50UGFydHMubGVuZ3RoID4gMCkge1xuICAgICAgZXZlbnRQYXJ0cy5wdXNoKC4uLl8udW5pcVdpdGgoZm9ybWF0dGVkRXZlbnRQYXJ0cywgXy5pc0VxdWFsKSk7XG4gICAgfVxuXG4gICAgaWYgKGV2ZW50UGFydHMubGVuZ3RoID4gMCkge1xuICAgICAgZXZlbnRQYXJ0cy5mb3JFYWNoKChlKSA9PiBjb25zb2xlLmxvZyhlLCAnIGV2ZW50UGFydHMgYWZ0ZXIgZm9ybWF0dGluZycpKTtcbiAgICAgIGNvbnN0IG5ld0V2ZW50UGFydHNXaXRoUHJlZmVycmVkVGltZVNldCA9IGV2ZW50UGFydHMubWFwKChlKSA9PlxuICAgICAgICBzZXRQcmVmZXJyZWRUaW1lRm9yVW5Nb2RpZmlhYmxlRXZlbnQoXG4gICAgICAgICAgZSxcbiAgICAgICAgICBhbGxFdmVudHMuZmluZCgoZikgPT4gZi5pZCA9PT0gZS5ldmVudElkKT8udGltZXpvbmVcbiAgICAgICAgKVxuICAgICAgKTtcbiAgICAgIG5ld0V2ZW50UGFydHNXaXRoUHJlZmVycmVkVGltZVNldC5mb3JFYWNoKChlKSA9PlxuICAgICAgICBjb25zb2xlLmxvZyhlLCAnIG5ld0V2ZW50UGFydHNXaXRoUHJlZmVycmVkVGltZVNldCcpXG4gICAgICApO1xuICAgICAgY29uc3QgbmV3RXZlbnRQYXJ0cyA9IGF3YWl0IHRhZ0V2ZW50c0ZvckRhaWx5T3JXZWVrbHlUYXNrKFxuICAgICAgICBuZXdFdmVudFBhcnRzV2l0aFByZWZlcnJlZFRpbWVTZXRcbiAgICAgICk7XG4gICAgICBuZXdFdmVudFBhcnRzLmZvckVhY2goKGUpID0+XG4gICAgICAgIGNvbnNvbGUubG9nKGUsICcgbmV3RXZlbnRQYXJ0cyBhZnRlciB0YWdFdmVudHNGb3JEYWlseU9yV2Vla2x5VGFzaycpXG4gICAgICApO1xuICAgICAgY29uc3QgdW5maWx0ZXJlZFVzZXJMaXN0OiBVc2VyUGxhbm5lclJlcXVlc3RCb2R5VHlwZVtdID0gW107XG4gICAgICBmb3IgKGNvbnN0IHVzZXJQcmVmZXJlbmNlIG9mIHVzZXJQcmVmZXJlbmNlcykge1xuICAgICAgICBjb25zdCB1c2VyUGxhbm5lclJlcXVlc3RCb2R5ID0gZ2VuZXJhdGVVc2VyUGxhbm5lclJlcXVlc3RCb2R5KFxuICAgICAgICAgIHVzZXJQcmVmZXJlbmNlLFxuICAgICAgICAgIHVzZXJQcmVmZXJlbmNlPy51c2VySWQsXG4gICAgICAgICAgd29ya1RpbWVzLFxuICAgICAgICAgIG1haW5Ib3N0SWRcbiAgICAgICAgKTtcbiAgICAgICAgY29uc29sZS5sb2codXNlclBsYW5uZXJSZXF1ZXN0Qm9keSwgJyB1c2VyUGxhbm5lclJlcXVlc3RCb2R5Jyk7XG4gICAgICAgIHVuZmlsdGVyZWRVc2VyTGlzdC5wdXNoKHVzZXJQbGFubmVyUmVxdWVzdEJvZHkpO1xuICAgICAgfVxuXG4gICAgICBjb25zdCB1c2VyTGlzdDogVXNlclBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSA9IF8udW5pcVdpdGgoXG4gICAgICAgIHVuZmlsdGVyZWRVc2VyTGlzdCxcbiAgICAgICAgXy5pc0VxdWFsXG4gICAgICApO1xuXG4gICAgICBjb25zdCBtb2RpZmllZE5ld0V2ZW50UGFydHM6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSA9XG4gICAgICAgIG5ld0V2ZW50UGFydHMubWFwKChldmVudFBhcnQpID0+IHtcbiAgICAgICAgICBjb25zdCBvbGRFdmVudCA9IGZpbHRlcmVkQWxsRXZlbnRzLmZpbmQoXG4gICAgICAgICAgICAoZXZlbnQpID0+IGV2ZW50LmlkID09PSBldmVudFBhcnQuZXZlbnRJZFxuICAgICAgICAgICk7XG4gICAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICAgIGdyb3VwSWQ6IGV2ZW50UGFydD8uZ3JvdXBJZCxcbiAgICAgICAgICAgIGV2ZW50SWQ6IGV2ZW50UGFydD8uZXZlbnRJZCxcbiAgICAgICAgICAgIHBhcnQ6IGV2ZW50UGFydD8ucGFydCxcbiAgICAgICAgICAgIGxhc3RQYXJ0OiBldmVudFBhcnQ/Lmxhc3RQYXJ0LFxuICAgICAgICAgICAgbWVldGluZ1BhcnQ6IGV2ZW50UGFydD8ubWVldGluZ1BhcnQsXG4gICAgICAgICAgICBtZWV0aW5nTGFzdFBhcnQ6IGV2ZW50UGFydD8ubWVldGluZ0xhc3RQYXJ0LFxuICAgICAgICAgICAgbWVldGluZ0lkOiBldmVudFBhcnQ/Lm1lZXRpbmdJZCxcbiAgICAgICAgICAgIGhvc3RJZDogbWFpbkhvc3RJZCxcbiAgICAgICAgICAgIHN0YXJ0RGF0ZTogZGF5anMoZXZlbnRQYXJ0Py5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoob2xkRXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW06c3MnKSxcbiAgICAgICAgICAgIGVuZERhdGU6IGRheWpzKGV2ZW50UGFydD8uZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihvbGRFdmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpLFxuICAgICAgICAgICAgdXNlcklkOiBldmVudFBhcnQ/LnVzZXJJZCxcbiAgICAgICAgICAgIHVzZXI6IGV2ZW50UGFydD8udXNlcixcbiAgICAgICAgICAgIHByaW9yaXR5OiBldmVudFBhcnQ/LnByaW9yaXR5LFxuICAgICAgICAgICAgaXNQcmVFdmVudDogZXZlbnRQYXJ0Py5pc1ByZUV2ZW50LFxuICAgICAgICAgICAgaXNQb3N0RXZlbnQ6IGV2ZW50UGFydD8uaXNQb3N0RXZlbnQsXG4gICAgICAgICAgICBwb3NpdGl2ZUltcGFjdFNjb3JlOiBldmVudFBhcnQ/LnBvc2l0aXZlSW1wYWN0U2NvcmUsXG4gICAgICAgICAgICBuZWdhdGl2ZUltcGFjdFNjb3JlOiBldmVudFBhcnQ/Lm5lZ2F0aXZlSW1wYWN0U2NvcmUsXG4gICAgICAgICAgICBtb2RpZmlhYmxlOiBldmVudFBhcnQ/Lm1vZGlmaWFibGUsXG4gICAgICAgICAgICBpc01lZXRpbmc6IGV2ZW50UGFydD8uaXNNZWV0aW5nLFxuICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmc6IGV2ZW50UGFydD8uaXNFeHRlcm5hbE1lZXRpbmcsXG4gICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGU6IGV2ZW50UGFydD8uaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlLFxuICAgICAgICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZTogZXZlbnRQYXJ0Py5pc01lZXRpbmdNb2RpZmlhYmxlLFxuICAgICAgICAgICAgZGFpbHlUYXNrTGlzdDogZXZlbnRQYXJ0Py5kYWlseVRhc2tMaXN0LFxuICAgICAgICAgICAgd2Vla2x5VGFza0xpc3Q6IGV2ZW50UGFydD8ud2Vla2x5VGFza0xpc3QsXG4gICAgICAgICAgICBnYXA6IGV2ZW50UGFydD8uZ2FwLFxuICAgICAgICAgICAgdG90YWxXb3JraW5nSG91cnM6IGV2ZW50UGFydD8udG90YWxXb3JraW5nSG91cnMsXG4gICAgICAgICAgICBoYXJkRGVhZGxpbmU6IGV2ZW50UGFydD8uaGFyZERlYWRsaW5lLFxuICAgICAgICAgICAgc29mdERlYWRsaW5lOiBldmVudFBhcnQ/LnNvZnREZWFkbGluZSxcbiAgICAgICAgICAgIGZvckV2ZW50SWQ6IGV2ZW50UGFydD8uZm9yRXZlbnRJZCxcbiAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrOiBldmVudFBhcnQ/LnBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrLFxuICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RUaW1lOiBldmVudFBhcnQ/LnBvc2l0aXZlSW1wYWN0VGltZSxcbiAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrOiBldmVudFBhcnQ/Lm5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrLFxuICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3RUaW1lOiBldmVudFBhcnQ/Lm5lZ2F0aXZlSW1wYWN0VGltZSxcbiAgICAgICAgICAgIHByZWZlcnJlZERheU9mV2VlazogZXZlbnRQYXJ0Py5wcmVmZXJyZWREYXlPZldlZWssXG4gICAgICAgICAgICBwcmVmZXJyZWRUaW1lOiBldmVudFBhcnQ/LnByZWZlcnJlZFRpbWUsXG4gICAgICAgICAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZTogZXZlbnRQYXJ0Py5wcmVmZXJyZWRTdGFydFRpbWVSYW5nZSxcbiAgICAgICAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZTogZXZlbnRQYXJ0Py5wcmVmZXJyZWRFbmRUaW1lUmFuZ2UsXG4gICAgICAgICAgICBldmVudDogZXZlbnRQYXJ0Py5ldmVudCxcbiAgICAgICAgICB9O1xuICAgICAgICB9KTtcblxuICAgICAgbW9kaWZpZWROZXdFdmVudFBhcnRzPy5mb3JFYWNoKChlKSA9PlxuICAgICAgICBjb25zb2xlLmxvZyhlLCAnIG1vZGlmaWVkTmV3RXZlbnRQYXJ0cycpXG4gICAgICApO1xuXG4gICAgICByZXR1cm4gbW9kaWZpZWROZXdFdmVudFBhcnRzPy5sZW5ndGggPiAwXG4gICAgICAgID8ge1xuICAgICAgICAgICAgdXNlcklkczogaW50ZXJuYWxBdHRlbmRlZXMubWFwKChhKSA9PiBhLnVzZXJJZCksXG4gICAgICAgICAgICBob3N0SWQ6IG1haW5Ib3N0SWQsXG4gICAgICAgICAgICBldmVudFBhcnRzOiBtb2RpZmllZE5ld0V2ZW50UGFydHMsXG4gICAgICAgICAgICBhbGxFdmVudHM6IGZpbHRlcmVkQWxsRXZlbnRzLFxuICAgICAgICAgICAgYnJlYWtzOiBwYXJlbnRCcmVha3MsXG4gICAgICAgICAgICBvbGRFdmVudHMsXG4gICAgICAgICAgICB0aW1lc2xvdHMsXG4gICAgICAgICAgICB1c2VyTGlzdCxcbiAgICAgICAgICB9XG4gICAgICAgIDogbnVsbDtcbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUsXG4gICAgICAnIHVuYWJsZSB0byBwcm9jZXNzIGV2ZW50cyBmb3Igb3B0YXBsYW5uZXIgZm9yIGVhY2ggYXR0ZW5kZWUnXG4gICAgKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGNvbnZlcnRNZWV0aW5nQXNzaXN0RXZlbnRUeXBlVG9FdmVudFBsdXNUeXBlID0gKFxuICBldmVudDogTWVldGluZ0Fzc2lzdEV2ZW50VHlwZSxcbiAgdXNlcklkOiBzdHJpbmdcbik6IEV2ZW50UGx1c1R5cGUgPT4ge1xuICByZXR1cm4ge1xuICAgIC4uLmV2ZW50LFxuICAgIHVzZXJJZDogdXNlcklkLFxuICAgIHRpdGxlOiBldmVudD8uc3VtbWFyeSxcbiAgICBzdGFydERhdGU6IGV2ZW50Py5zdGFydERhdGUsXG4gICAgZW5kRGF0ZTogZXZlbnQ/LmVuZERhdGUsXG4gICAgYWxsRGF5OiBldmVudD8uYWxsRGF5LFxuICAgIHJlY3VycmVuY2VSdWxlOiBldmVudD8ucmVjdXJyZW5jZVJ1bGUsXG4gICAgbG9jYXRpb246IGV2ZW50Py5sb2NhdGlvbixcbiAgICBub3RlczogZXZlbnQ/Lm5vdGVzLFxuICAgIGF0dGFjaG1lbnRzOiBldmVudD8uYXR0YWNobWVudHMsXG4gICAgbGlua3M6IGV2ZW50Py5saW5rcyxcbiAgICB0aW1lem9uZTogZXZlbnQ/LnRpbWV6b25lLFxuICAgIGNyZWF0ZWREYXRlOiBldmVudD8uY3JlYXRlZERhdGUsXG4gICAgZGVsZXRlZDogZmFsc2UsXG4gICAgcHJpb3JpdHk6IDEsXG4gICAgaXNGb2xsb3dVcDogZmFsc2UsXG4gICAgaXNQcmVFdmVudDogZmFsc2UsXG4gICAgaXNQb3N0RXZlbnQ6IGZhbHNlLFxuICAgIG1vZGlmaWFibGU6IGZhbHNlLFxuICAgIGFueW9uZUNhbkFkZFNlbGY6IHRydWUsXG4gICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiB0cnVlLFxuICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOiB0cnVlLFxuICAgIG9yaWdpbmFsU3RhcnREYXRlOiB1bmRlZmluZWQsXG4gICAgb3JpZ2luYWxBbGxEYXk6IGZhbHNlLFxuICAgIHN1bW1hcnk6IGV2ZW50Py5zdW1tYXJ5LFxuICAgIHRyYW5zcGFyZW5jeTogZXZlbnQ/LnRyYW5zcGFyZW5jeSxcbiAgICB2aXNpYmlsaXR5OiBldmVudD8udmlzaWJpbGl0eSxcbiAgICByZWN1cnJpbmdFdmVudElkOiBldmVudD8ucmVjdXJyaW5nRXZlbnRJZCxcbiAgICB1cGRhdGVkQXQ6IGV2ZW50Py51cGRhdGVkQXQsXG4gICAgaUNhbFVJRDogZXZlbnQ/LmlDYWxVSUQsXG4gICAgaHRtbExpbms6IGV2ZW50Py5odG1sTGluayxcbiAgICBjb2xvcklkOiBldmVudD8uY29sb3JJZCxcbiAgICBjcmVhdG9yOiBldmVudD8uY3JlYXRvcixcbiAgICBvcmdhbml6ZXI6IGV2ZW50Py5vcmdhbml6ZXIsXG4gICAgZW5kVGltZVVuc3BlY2lmaWVkOiBldmVudD8uZW5kVGltZVVuc3BlY2lmaWVkLFxuICAgIHJlY3VycmVuY2U6IGV2ZW50Py5yZWN1cnJlbmNlLFxuICAgIG9yaWdpbmFsVGltZXpvbmU6IGV2ZW50Py50aW1lem9uZSxcbiAgICBleHRlbmRlZFByb3BlcnRpZXM6IGV2ZW50Py5leHRlbmRlZFByb3BlcnRpZXMsXG4gICAgaGFuZ291dExpbms6IGV2ZW50Py5oYW5nb3V0TGluayxcbiAgICBndWVzdHNDYW5Nb2RpZnk6IGV2ZW50Py5ndWVzdHNDYW5Nb2RpZnksXG4gICAgbG9ja2VkOiBldmVudD8ubG9ja2VkLFxuICAgIHNvdXJjZTogZXZlbnQ/LnNvdXJjZSxcbiAgICBldmVudFR5cGU6IGV2ZW50Py5ldmVudFR5cGUsXG4gICAgcHJpdmF0ZUNvcHk6IGV2ZW50Py5wcml2YXRlQ29weSxcbiAgICBjYWxlbmRhcklkOiBldmVudD8uY2FsZW5kYXJJZCxcbiAgICBiYWNrZ3JvdW5kQ29sb3I6IGV2ZW50Py5iYWNrZ3JvdW5kQ29sb3IsXG4gICAgZm9yZWdyb3VuZENvbG9yOiBldmVudD8uZm9yZWdyb3VuZENvbG9yLFxuICAgIHVzZURlZmF1bHRBbGFybXM6IGV2ZW50Py51c2VEZWZhdWx0QWxhcm1zLFxuICAgIG1lZXRpbmdJZDogZXZlbnQ/Lm1lZXRpbmdJZCxcbiAgICBldmVudElkOiBldmVudD8uZXZlbnRJZCxcbiAgfTtcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZVdvcmtUaW1lc0ZvckV4dGVybmFsQXR0ZW5kZWUgPSAoXG4gIGhvc3RJZDogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgYXR0ZW5kZWVFdmVudHM6IEV2ZW50UGx1c1R5cGVbXSxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIHVzZXJUaW1lem9uZTogc3RyaW5nXG4pID0+IHtcbiAgLy8gNyBkYXlzIGluIGEgd2Vla1xuICBjb25zdCBkYXlzSW5XZWVrID0gNztcblxuICBjb25zdCB3b3JrVGltZXM6IFdvcmtUaW1lVHlwZVtdID0gW107XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBkYXlzSW5XZWVrOyBpKyspIHtcbiAgICBjb25zdCBkYXlPZldlZWtJbnQgPSBpICsgMTtcblxuICAgIGNvbnN0IHNhbWVEYXlFdmVudHMgPSBhdHRlbmRlZUV2ZW50cy5maWx0ZXIoXG4gICAgICAoZSkgPT5cbiAgICAgICAgZ2V0SVNPRGF5KFxuICAgICAgICAgIGRheWpzKGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAudG9EYXRlKClcbiAgICAgICAgKSA9PT1cbiAgICAgICAgaSArIDFcbiAgICApO1xuICAgIGNvbnN0IG1pblN0YXJ0RGF0ZSA9IF8ubWluQnkoc2FtZURheUV2ZW50cywgKGUpID0+XG4gICAgICBkYXlqcyhlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLnVuaXgoKVxuICAgICk7XG4gICAgY29uc3QgbWF4RW5kRGF0ZSA9IF8ubWF4Qnkoc2FtZURheUV2ZW50cywgKGUpID0+XG4gICAgICBkYXlqcyhlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC51bml4KClcbiAgICApO1xuICAgIGNvbnN0IHN0YXJ0SG91ciA9IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmhvdXIoKTtcbiAgICBjb25zdCBzdGFydE1pbnV0ZSA9IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKDApLFxuICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoMTUpLFxuICAgICAgICAnbWludXRlJyxcbiAgICAgICAgJ1spJ1xuICAgICAgKVxuICAgICAgPyAwXG4gICAgICA6IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgIClcbiAgICAgICAgPyAxNVxuICAgICAgICA6IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgLm1pbnV0ZSg0NSksXG4gICAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgICApXG4gICAgICAgICAgPyAzMFxuICAgICAgICAgIDogNDU7XG5cbiAgICBsZXQgZW5kSG91ciA9IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmhvdXIoKTtcbiAgICBjb25zdCBlbmRNaW51dGUgPSBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLm1pbnV0ZSgwKSxcbiAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICdbKSdcbiAgICAgIClcbiAgICAgID8gMTVcbiAgICAgIDogZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihtYXhFbmREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihtYXhFbmREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMTUpLFxuICAgICAgICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihtYXhFbmREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDMwXG4gICAgICAgIDogZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAgIC50eihtYXhFbmREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAubWludXRlKDQ1KSxcbiAgICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICAgIClcbiAgICAgICAgICA/IDQ1XG4gICAgICAgICAgOiAwO1xuICAgIGlmIChlbmRNaW51dGUgPT09IDApIHtcbiAgICAgIGlmIChlbmRIb3VyIDwgMjMpIHtcbiAgICAgICAgZW5kSG91ciArPSAxO1xuICAgICAgfVxuICAgIH1cblxuICAgIHdvcmtUaW1lcy5wdXNoKHtcbiAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50XSxcbiAgICAgIHN0YXJ0VGltZTogZGF5anMoXG4gICAgICAgIHNldElTT0RheShcbiAgICAgICAgICBkYXlqcygpXG4gICAgICAgICAgICAuaG91cihzdGFydEhvdXIpXG4gICAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC50b0RhdGUoKSxcbiAgICAgICAgICBpICsgMVxuICAgICAgICApXG4gICAgICApXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgIGVuZFRpbWU6IGRheWpzKFxuICAgICAgICBzZXRJU09EYXkoXG4gICAgICAgICAgZGF5anMoKVxuICAgICAgICAgICAgLmhvdXIoZW5kSG91cilcbiAgICAgICAgICAgIC5taW51dGUoZW5kTWludXRlKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC50b0RhdGUoKSxcbiAgICAgICAgICBpICsgMVxuICAgICAgICApXG4gICAgICApXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgIGhvc3RJZCxcbiAgICAgIHVzZXJJZCxcbiAgICB9KTtcbiAgfVxuXG4gIHJldHVybiB3b3JrVGltZXM7XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVUaW1lU2xvdHNGb3JFeHRlcm5hbEF0dGVuZGVlID0gKFxuICBob3N0U3RhcnREYXRlOiBzdHJpbmcsXG4gIGhvc3RJZDogc3RyaW5nLFxuICBhdHRlbmRlZUV2ZW50czogRXZlbnRQbHVzVHlwZVtdLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgdXNlclRpbWV6b25lOiBzdHJpbmcsXG4gIGlzRmlyc3REYXk/OiBib29sZWFuXG4pID0+IHtcbiAgaWYgKGlzRmlyc3REYXkpIHtcbiAgICBjb25zdCBkYXlPZldlZWtJbnRCeUhvc3QgPSBnZXRJU09EYXkoXG4gICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICAgICk7XG4gICAgLy8gY29udmVydCB0byBob3N0IHRpbWV6b25lIHNvIGV2ZXJ5dGhpbmcgaXMgbGlua2VkIHRvIGhvc3QgdGltZXpvbmVcbiAgICBjb25zdCBtb250aEJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5tb250aCgpO1xuICAgIGNvbnN0IGRheU9mTW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuZGF0ZSgpO1xuICAgIGNvbnN0IHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLm1pbnV0ZSgwKSxcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkubWludXRlKDMwKSxcbiAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICdbKSdcbiAgICAgIClcbiAgICAgID8gMFxuICAgICAgOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoNTkpLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDMwXG4gICAgICAgIDogMDtcblxuICAgIGNvbnN0IHNhbWVEYXlFdmVudHMgPSBhdHRlbmRlZUV2ZW50cy5maWx0ZXIoXG4gICAgICAoZSkgPT5cbiAgICAgICAgZ2V0SVNPRGF5KFxuICAgICAgICAgIGRheWpzKGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLnRvRGF0ZSgpXG4gICAgICAgICkgPT09IGRheU9mV2Vla0ludEJ5SG9zdFxuICAgICk7XG4gICAgLy8gY29uc3QgbWluU3RhcnREYXRlID0gXy5taW5CeShzYW1lRGF5RXZlbnRzLCAoZSkgPT4gZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eih1c2VyVGltZXpvbmUsIHRydWUpLnR6KGhvc3RUaW1lem9uZSkudW5peCgpKVxuICAgIGNvbnN0IG1heEVuZERhdGUgPSBfLm1heEJ5KHNhbWVEYXlFdmVudHMsIChlKSA9PlxuICAgICAgZGF5anMoZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLnVuaXgoKVxuICAgICk7XG5cbiAgICBsZXQgd29ya0VuZEhvdXJCeUhvc3QgPSBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHdvcmtFbmRNaW51dGVCeUhvc3QgPSBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKDApLFxuICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICdbKSdcbiAgICAgIClcbiAgICAgID8gMzBcbiAgICAgIDogZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoNTkpLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDBcbiAgICAgICAgOiAzMDtcbiAgICBpZiAod29ya0VuZE1pbnV0ZUJ5SG9zdCA9PT0gMCkge1xuICAgICAgaWYgKHdvcmtFbmRIb3VyQnlIb3N0IDwgMjMpIHtcbiAgICAgICAgd29ya0VuZEhvdXJCeUhvc3QgKz0gMTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBtaW5TdGFydERhdGUgPSBfLm1pbkJ5KHNhbWVEYXlFdmVudHMsIChlKSA9PlxuICAgICAgZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAudW5peCgpXG4gICAgKTtcblxuICAgIGNvbnN0IHdvcmtTdGFydEhvdXJCeUhvc3QgPSBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCA9IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoMCksXG4gICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAnbWludXRlJyxcbiAgICAgICAgJ1spJ1xuICAgICAgKVxuICAgICAgPyAwXG4gICAgICA6IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDU5KSxcbiAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgIClcbiAgICAgICAgPyAzMFxuICAgICAgICA6IDA7XG5cbiAgICAvLyBjaGFuZ2UgdG8gd29yayBzdGFydCB0aW1lIGFzIHdvcmsgc3RhcnQgdGltZSBpcyAgYWZ0ZXIgaG9zdCBzdGFydCB0aW1lXG4gICAgaWYgKFxuICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5pc0JlZm9yZShcbiAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICAgIGhvdXJzOiB3b3JrU3RhcnRIb3VyQnlIb3N0LFxuICAgICAgICBtaW51dGVzOiB3b3JrU3RhcnRNaW51dGVCeUhvc3QsXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgICBob3Vyczogd29ya0VuZEhvdXJCeUhvc3QsXG4gICAgICAgIG1pbnV0ZXM6IHdvcmtFbmRNaW51dGVCeUhvc3QsXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgICAgIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG5cbiAgICAgIGNvbnN0IHRpbWVTbG90czogVGltZVNsb3RUeXBlW10gPSBbXTtcblxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGhvc3RTdGFydERhdGUsXG4gICAgICAgIGRheU9mV2Vla0ludEJ5SG9zdCxcbiAgICAgICAgZGF5T2ZNb250aEJ5SG9zdCxcbiAgICAgICAgc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdCxcbiAgICAgICAgc3RhcnRNaW51dGVPZkhvc3REYXRlQnlIb3N0LFxuICAgICAgICB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAgICAgd29ya0VuZE1pbnV0ZUJ5SG9zdCxcbiAgICAgICAgdGltZXpvbmUsXG4gICAgICAgIGBzdGFydERhdGUsICBkYXlPZldlZWtJbnRCeUhvc3QsIGRheU9mTW9udGhCeUhvc3QsIHN0YXJ0SG91ckJ5SG9zdCwgc3RhcnRNaW51dGVCeUhvc3QsIGVuZEhvdXJCeUhvc3QsIGVuZE1pbnV0ZUJ5SG9zdCB0b3RhbE1pbnV0ZXMsIHRpbWV6b25lLCBpbnNpZGUgZmlyc3REYXkgaW5zaWRlIGdlbmVyYXRlVGltZXNsb3RzYFxuICAgICAgKTtcbiAgICAgIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IDMwKSB7XG4gICAgICAgIHRpbWVTbG90cy5wdXNoKHtcbiAgICAgICAgICBkYXlPZldlZWs6IGRheU9mV2Vla0ludFRvU3RyaW5nW2RheU9mV2Vla0ludEJ5SG9zdF0sXG4gICAgICAgICAgc3RhcnRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cihzdGFydEhvdXJPZkhvc3REYXRlQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZU9mSG9zdERhdGVCeUhvc3QpXG4gICAgICAgICAgICAuYWRkKGksICdtaW51dGUnKVxuICAgICAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QpXG4gICAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdClcbiAgICAgICAgICAgIC5hZGQoaSArIDMwLCAnbWludXRlJylcbiAgICAgICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgICAgICBob3N0SWQsXG4gICAgICAgICAgbW9udGhEYXk6IGZvcm1hdFRvTW9udGhEYXkoXG4gICAgICAgICAgICBtb250aEJ5SG9zdCBhcyBNb250aFR5cGUsXG4gICAgICAgICAgICBkYXlPZk1vbnRoQnlIb3N0IGFzIERheVR5cGVcbiAgICAgICAgICApLFxuICAgICAgICAgIGRhdGU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICAgICAgfSk7XG4gICAgICB9XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgdGltZVNsb3RzLFxuICAgICAgICAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMgZm9yIGZpcnN0IGRheSB3aGVyZSBzdGFydERhdGUgaXMgYmVmb3JlIHdvcmsgc3RhcnQgdGltZSdcbiAgICAgICk7XG4gICAgICByZXR1cm4gdGltZVNsb3RzO1xuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICBob3Vyczogc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdCxcbiAgICAgIG1pbnV0ZXM6IHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdCxcbiAgICB9KTtcbiAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgIGhvdXJzOiB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAgIG1pbnV0ZXM6IHdvcmtFbmRNaW51dGVCeUhvc3QsXG4gICAgfSk7XG4gICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG5cbiAgICBjb25zdCB0aW1lU2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG4gICAgY29uc29sZS5sb2coXG4gICAgICBob3N0U3RhcnREYXRlLFxuICAgICAgZGF5T2ZXZWVrSW50QnlIb3N0LFxuICAgICAgZGF5T2ZNb250aEJ5SG9zdCxcbiAgICAgIHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QsXG4gICAgICBzdGFydE1pbnV0ZU9mSG9zdERhdGVCeUhvc3QsXG4gICAgICB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAgIHdvcmtFbmRNaW51dGVCeUhvc3QsXG4gICAgICBob3N0VGltZXpvbmUsXG4gICAgICBgc3RhcnREYXRlLCAgZGF5T2ZXZWVrSW50QnlIb3N0LCBkYXlPZk1vbnRoLCBzdGFydEhvdXIsIHN0YXJ0TWludXRlLCBlbmRIb3VyLCBlbmRNaW51dGUgdG90YWxNaW51dGVzLCB0aW1lem9uZSwgaW5zaWRlIGZpcnN0RGF5IGluc2lkZSBnZW5lcmF0ZVRpbWVzbG90c2BcbiAgICApO1xuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IDMwKSB7XG4gICAgICB0aW1lU2xvdHMucHVzaCh7XG4gICAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50QnlIb3N0XSxcbiAgICAgICAgc3RhcnRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QpXG4gICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZU9mSG9zdERhdGVCeUhvc3QpXG4gICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdClcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdClcbiAgICAgICAgICAuYWRkKGkgKyAzMCwgJ21pbnV0ZScpXG4gICAgICAgICAgLmZvcm1hdCgnSEg6bW06c3MnKSBhcyBUaW1lLFxuICAgICAgICBob3N0SWQsXG4gICAgICAgIG1vbnRoRGF5OiBmb3JtYXRUb01vbnRoRGF5KFxuICAgICAgICAgIG1vbnRoQnlIb3N0IGFzIE1vbnRoVHlwZSxcbiAgICAgICAgICBkYXlPZk1vbnRoQnlIb3N0IGFzIERheVR5cGVcbiAgICAgICAgKSxcbiAgICAgICAgZGF0ZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgICB9KTtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyh0aW1lU2xvdHMsICcgdGltZVNsb3RzIGluc2lkZSBnZW5lcmF0ZVRpbWVTbG90cyBmb3IgZmlyc3QgZGF5Jyk7XG4gICAgcmV0dXJuIHRpbWVTbG90cztcbiAgfVxuXG4gIC8vIG5vdCBmaXJzdCBkYXkgc3RhcnQgZnJvbSB3b3JrIHN0YXJ0IHRpbWUgc2NoZWR1bGVcblxuICBjb25zdCBkYXlPZldlZWtJbnRCeUhvc3QgPSBnZXRJU09EYXkoXG4gICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkudG9EYXRlKClcbiAgKTtcbiAgLy8gY29udmVydCB0byBob3N0IHRpbWV6b25lIHNvIGV2ZXJ5dGhpbmcgaXMgbGlua2VkIHRvIGhvc3QgdGltZXpvbmVcbiAgY29uc3QgbW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgIC5tb250aCgpO1xuICBjb25zdCBkYXlPZk1vbnRoQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAuZGF0ZSgpO1xuXG4gIGNvbnN0IHNhbWVEYXlFdmVudHMgPSBhdHRlbmRlZUV2ZW50cy5maWx0ZXIoXG4gICAgKGUpID0+XG4gICAgICBnZXRJU09EYXkoXG4gICAgICAgIGRheWpzKGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoodXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLnRvRGF0ZSgpXG4gICAgICApID09PSBkYXlPZldlZWtJbnRCeUhvc3RcbiAgKTtcbiAgY29uc3QgbWluU3RhcnREYXRlID0gXy5taW5CeShzYW1lRGF5RXZlbnRzLCAoZSkgPT5cbiAgICBkYXlqcyhlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHoodXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC51bml4KClcbiAgKTtcbiAgY29uc3QgbWF4RW5kRGF0ZSA9IF8ubWF4Qnkoc2FtZURheUV2ZW50cywgKGUpID0+XG4gICAgZGF5anMoZS5lbmREYXRlLnNsaWNlKDAsIDE5KSkudHoodXNlclRpbWV6b25lLCB0cnVlKS50eihob3N0VGltZXpvbmUpLnVuaXgoKVxuICApO1xuXG4gIGxldCB3b3JrRW5kSG91ckJ5SG9zdCA9IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5ob3VyKCk7XG4gIGNvbnN0IHdvcmtFbmRNaW51dGVCeUhvc3QgPSBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAuaXNCZXR3ZWVuKFxuICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLm1pbnV0ZSgwKSxcbiAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5taW51dGUoMzApLFxuICAgICAgJ21pbnV0ZScsXG4gICAgICAnWyknXG4gICAgKVxuICAgID8gMzBcbiAgICA6IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5taW51dGUoNTkpLFxuICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAnWyknXG4gICAgICAgICAgKVxuICAgICAgPyAwXG4gICAgICA6IDMwO1xuICBpZiAod29ya0VuZE1pbnV0ZUJ5SG9zdCA9PT0gMCkge1xuICAgIGlmICh3b3JrRW5kSG91ckJ5SG9zdCA8IDIzKSB7XG4gICAgICB3b3JrRW5kSG91ckJ5SG9zdCArPSAxO1xuICAgIH1cbiAgfVxuXG4gIGNvbnN0IHdvcmtTdGFydEhvdXJCeUhvc3QgPSBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAuaG91cigpO1xuICBjb25zdCB3b3JrU3RhcnRNaW51dGVCeUhvc3QgPSBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAuaXNCZXR3ZWVuKFxuICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLm1pbnV0ZSgwKSxcbiAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5taW51dGUoMzApLFxuICAgICAgJ21pbnV0ZScsXG4gICAgICAnWyknXG4gICAgKVxuICAgID8gMFxuICAgIDogZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLm1pbnV0ZSg1OSksXG4gICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICdbKSdcbiAgICAgICAgICApXG4gICAgICA/IDMwXG4gICAgICA6IDA7XG5cbiAgY29uc29sZS5sb2coXG4gICAgbW9udGhCeUhvc3QsXG4gICAgZGF5T2ZNb250aEJ5SG9zdCxcbiAgICB3b3JrU3RhcnRIb3VyQnlIb3N0LFxuICAgIHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCxcbiAgICB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAnIG1vbnRoQnlIb3N0LCBkYXlPZk1vbnRoQnlIb3N0LCB3b3JrU3RhcnRIb3VyQnlIb3N0LCB3b3JrU3RhcnRNaW51dGVCeUhvc3QsIHdvcmtFbmRIb3VyQnlIb3N0J1xuICApO1xuICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiB3b3JrU3RhcnRIb3VyQnlIb3N0LFxuICAgIG1pbnV0ZXM6IHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCxcbiAgfSk7XG4gIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICBtaW51dGVzOiB3b3JrRW5kTWludXRlQnlIb3N0LFxuICB9KTtcbiAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICBjb25zdCB0b3RhbE1pbnV0ZXMgPSB0b3RhbER1cmF0aW9uLmFzTWludXRlcygpO1xuICBjb25zdCB0aW1lU2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG4gIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IDMwKSB7XG4gICAgdGltZVNsb3RzLnB1c2goe1xuICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1tkYXlPZldlZWtJbnRCeUhvc3RdLFxuICAgICAgc3RhcnRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tOnNzJykgYXMgVGltZSxcbiAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgLmFkZChpICsgMzAsICdtaW51dGUnKVxuICAgICAgICAuZm9ybWF0KCdISDptbTpzcycpIGFzIFRpbWUsXG4gICAgICBob3N0SWQsXG4gICAgICBtb250aERheTogZm9ybWF0VG9Nb250aERheShcbiAgICAgICAgbW9udGhCeUhvc3QgYXMgTW9udGhUeXBlLFxuICAgICAgICBkYXlPZk1vbnRoQnlIb3N0IGFzIERheVR5cGVcbiAgICAgICksXG4gICAgICBkYXRlOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERCcpLFxuICAgIH0pO1xuICB9XG5cbiAgY29uc29sZS5sb2codGltZVNsb3RzLCAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMnKTtcbiAgcmV0dXJuIHRpbWVTbG90cztcbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzRXZlbnRzRm9yT3B0YVBsYW5uZXJGb3JFeHRlcm5hbEF0dGVuZGVlcyA9IGFzeW5jIChcbiAgdXNlcklkczogc3RyaW5nW10sXG4gIG1haW5Ib3N0SWQ6IHN0cmluZyxcbiAgYWxsRXh0ZXJuYWxFdmVudHM6IE1lZXRpbmdBc3Npc3RFdmVudFR5cGVbXSxcbiAgd2luZG93U3RhcnREYXRlOiBzdHJpbmcsXG4gIHdpbmRvd0VuZERhdGU6IHN0cmluZyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIGV4dGVybmFsQXR0ZW5kZWVzOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10sXG4gIG9sZEV4dGVybmFsTWVldGluZ0V2ZW50cz86IEV2ZW50TWVldGluZ1BsdXNUeXBlW10sIC8vIGNvbnZlcnRlZCBmcm9tIGV4dGVybmFsIGV2ZW50c1xuICBuZXdNZWV0aW5nRXZlbnRzPzogRXZlbnRNZWV0aW5nUGx1c1R5cGVbXVxuKTogUHJvbWlzZTxSZXR1cm5Cb2R5Rm9yRXh0ZXJuYWxBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGU+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBtb2RpZmllZEFsbEV4dGVybmFsRXZlbnRzID0gYWxsRXh0ZXJuYWxFdmVudHM/Lm1hcCgoZSkgPT5cbiAgICAgIGNvbnZlcnRNZWV0aW5nQXNzaXN0RXZlbnRUeXBlVG9FdmVudFBsdXNUeXBlKFxuICAgICAgICBlLFxuICAgICAgICBleHRlcm5hbEF0dGVuZGVlcz8uZmluZCgoYSkgPT4gYT8uaWQgPT09IGU/LmF0dGVuZGVlSWQpPy51c2VySWRcbiAgICAgIClcbiAgICApO1xuXG4gICAgY29uc3Qgb2xkQ29udmVydGVkTWVldGluZ0V2ZW50cyA9IG9sZEV4dGVybmFsTWVldGluZ0V2ZW50c1xuICAgICAgPy5tYXAoKGEpID0+IGNvbnZlcnRNZWV0aW5nUGx1c1R5cGVUb0V2ZW50UGx1c1R5cGUoYSkpXG4gICAgICA/LmZpbHRlcigoZSkgPT4gISFlKTtcbiAgICBpZiAob2xkQ29udmVydGVkTWVldGluZ0V2ZW50cz8ubGVuZ3RoID4gMCkge1xuICAgICAgbW9kaWZpZWRBbGxFeHRlcm5hbEV2ZW50cy5wdXNoKC4uLm9sZENvbnZlcnRlZE1lZXRpbmdFdmVudHMpO1xuICAgIH1cblxuICAgIGlmIChuZXdNZWV0aW5nRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICAvLyBhZGQgbmV3bHkgZ2VuZXJhdGVkIGhvc3QgZXZlbnQgdG8gcmVzdFxuICAgICAgbW9kaWZpZWRBbGxFeHRlcm5hbEV2ZW50cy5wdXNoKFxuICAgICAgICAuLi5uZXdNZWV0aW5nRXZlbnRzPy5tYXAoKG0pID0+XG4gICAgICAgICAgY29udmVydE1lZXRpbmdQbHVzVHlwZVRvRXZlbnRQbHVzVHlwZShtKVxuICAgICAgICApXG4gICAgICApO1xuICAgIH1cblxuICAgIC8vIGdlbmVyYXRlIHRpbWVzbG90c1xuXG4gICAgY29uc3QgZGlmZkRheXMgPSBkYXlqcyh3aW5kb3dFbmREYXRlLnNsaWNlKDAsIDE5KSkuZGlmZihcbiAgICAgIGRheWpzKHdpbmRvd1N0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLFxuICAgICAgJ2RheSdcbiAgICApO1xuXG4gICAgY29uc3Qgc3RhcnREYXRlc0ZvckVhY2hEYXkgPSBbXTtcblxuICAgIGZvciAobGV0IGkgPSAwOyBpIDw9IGRpZmZEYXlzOyBpKyspIHtcbiAgICAgIHN0YXJ0RGF0ZXNGb3JFYWNoRGF5LnB1c2goXG4gICAgICAgIGRheWpzKHdpbmRvd1N0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuYWRkKGksICdkYXknKVxuICAgICAgICAgIC5mb3JtYXQoKVxuICAgICAgKTtcbiAgICB9XG5cbiAgICBjb25zdCB1bmZpbHRlcmVkV29ya1RpbWVzOiBXb3JrVGltZVR5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBleHRlcm5hbEF0dGVuZGVlIG9mIGV4dGVybmFsQXR0ZW5kZWVzKSB7XG4gICAgICBjb25zdCB3b3JrVGltZXNGb3JBdHRlbmRlZSA9IGdlbmVyYXRlV29ya1RpbWVzRm9yRXh0ZXJuYWxBdHRlbmRlZShcbiAgICAgICAgbWFpbkhvc3RJZCxcbiAgICAgICAgZXh0ZXJuYWxBdHRlbmRlZT8udXNlcklkLFxuICAgICAgICBtb2RpZmllZEFsbEV4dGVybmFsRXZlbnRzLFxuICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgIGV4dGVybmFsQXR0ZW5kZWU/LnRpbWV6b25lXG4gICAgICApO1xuICAgICAgdW5maWx0ZXJlZFdvcmtUaW1lcy5wdXNoKC4uLndvcmtUaW1lc0ZvckF0dGVuZGVlKTtcbiAgICB9XG5cbiAgICBjb25zdCB3b3JrVGltZXM6IFdvcmtUaW1lVHlwZVtdID0gXy51bmlxV2l0aChcbiAgICAgIHVuZmlsdGVyZWRXb3JrVGltZXMsXG4gICAgICBfLmlzRXF1YWxcbiAgICApO1xuXG4gICAgY29uc3QgdW5maWx0ZXJlZFRpbWVzbG90czogVGltZVNsb3RUeXBlW10gPSBbXTtcbiAgICBjb25zdCB0aW1lc2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG5cbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IHN0YXJ0RGF0ZXNGb3JFYWNoRGF5Lmxlbmd0aDsgaSsrKSB7XG4gICAgICBpZiAoaSA9PT0gMCkge1xuICAgICAgICBmb3IgKGNvbnN0IGV4dGVybmFsQXR0ZW5kZWUgb2YgZXh0ZXJuYWxBdHRlbmRlZXMpIHtcbiAgICAgICAgICAvLyBjb25zdCBtb3N0UmVjZW50RXZlbnQgPSBfLm1pbkJ5KG1vZGlmaWVkQWxsRXh0ZXJuYWxFdmVudHMsIChlKSA9PiBkYXlqcyhlPy5zdGFydERhdGUpLnVuaXgoKSlcbiAgICAgICAgICBjb25zdCB0aW1lc2xvdHNGb3JEYXkgPVxuICAgICAgICAgICAgYXdhaXQgZ2VuZXJhdGVUaW1lU2xvdHNMaXRlRm9yRXh0ZXJuYWxBdHRlbmRlZShcbiAgICAgICAgICAgICAgc3RhcnREYXRlc0ZvckVhY2hEYXk/LltpXSxcbiAgICAgICAgICAgICAgbWFpbkhvc3RJZCxcbiAgICAgICAgICAgICAgbW9kaWZpZWRBbGxFeHRlcm5hbEV2ZW50cyxcbiAgICAgICAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICAgICAgICBleHRlcm5hbEF0dGVuZGVlPy50aW1lem9uZSxcbiAgICAgICAgICAgICAgdHJ1ZVxuICAgICAgICAgICAgKTtcbiAgICAgICAgICB1bmZpbHRlcmVkVGltZXNsb3RzLnB1c2goLi4udGltZXNsb3RzRm9yRGF5KTtcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfVxuICAgICAgZm9yIChjb25zdCBleHRlcm5hbEF0dGVuZGVlIG9mIGV4dGVybmFsQXR0ZW5kZWVzKSB7XG4gICAgICAgIGNvbnN0IHRpbWVTbG90cyA9IGdlbmVyYXRlVGltZVNsb3RzTGl0ZUZvckludGVybmFsQXR0ZW5kZWUoXG4gICAgICAgICAgc3RhcnREYXRlc0ZvckVhY2hEYXk/LltpXSxcbiAgICAgICAgICBtYWluSG9zdElkLFxuICAgICAgICAgIG1vZGlmaWVkQWxsRXh0ZXJuYWxFdmVudHMsXG4gICAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWU/LnRpbWV6b25lLFxuICAgICAgICAgIGZhbHNlXG4gICAgICAgICk7XG4gICAgICAgIHVuZmlsdGVyZWRUaW1lc2xvdHMucHVzaCguLi50aW1lc2xvdHNGb3JEYXkpO1xuICAgICAgfVxuICAgIH1cbiAgICB0aW1lc2xvdHMucHVzaCguLi5fLnVuaXFXaXRoKHVuZmlsdGVyZWRUaW1lc2xvdHMsIF8uaXNFcXVhbCkpO1xuXG4gICAgLy8gZ2VuZXJhdGUgZXZlbnQgcGFydHNcbiAgICBjb25zdCBmaWx0ZXJlZEFsbEV2ZW50cyA9IF8udW5pcUJ5KFxuICAgICAgbW9kaWZpZWRBbGxFeHRlcm5hbEV2ZW50cy5maWx0ZXIoKGUpID0+XG4gICAgICAgIHZhbGlkYXRlRXZlbnREYXRlc0ZvckV4dGVybmFsQXR0ZW5kZWUoZSlcbiAgICAgICksXG4gICAgICAnaWQnXG4gICAgKTtcbiAgICBsZXQgZXZlbnRQYXJ0czogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZVtdID0gW107XG5cbiAgICBjb25zdCBldmVudFBhcnRNaW5pc0FjY3VtdWxhdGVkID0gW107XG4gICAgZm9yIChjb25zdCBldmVudCBvZiBmaWx0ZXJlZEFsbEV2ZW50cykge1xuICAgICAgY29uc3QgZXZlbnRQYXJ0TWluaXMgPSBnZW5lcmF0ZUV2ZW50UGFydHNMaXRlKGV2ZW50LCBtYWluSG9zdElkKTtcbiAgICAgIGV2ZW50UGFydE1pbmlzQWNjdW11bGF0ZWQucHVzaCguLi5ldmVudFBhcnRNaW5pcyk7XG4gICAgfVxuXG4gICAgY29uc3QgbW9kaWZpZWRFdmVudFBhcnRNaW5pc1ByZUJ1ZmZlciA9XG4gICAgICBtb2RpZnlFdmVudFBhcnRzRm9yTXVsdGlwbGVQcmVCdWZmZXJUaW1lKGV2ZW50UGFydE1pbmlzQWNjdW11bGF0ZWQpO1xuICAgIGNvbnN0IG1vZGlmaWVkRXZlbnRQYXJ0TWluaXNQcmVBbmRQb3N0QnVmZmVyID1cbiAgICAgIG1vZGlmeUV2ZW50UGFydHNGb3JNdWx0aXBsZVBvc3RCdWZmZXJUaW1lKFxuICAgICAgICBtb2RpZmllZEV2ZW50UGFydE1pbmlzUHJlQnVmZmVyXG4gICAgICApO1xuICAgIGNvbnN0IGZvcm1hdHRlZEV2ZW50UGFydHM6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSA9XG4gICAgICBtb2RpZmllZEV2ZW50UGFydE1pbmlzUHJlQW5kUG9zdEJ1ZmZlcj8ubWFwKChlKSA9PlxuICAgICAgICBmb3JtYXRFdmVudFR5cGVUb1BsYW5uZXJFdmVudEZvckV4dGVybmFsQXR0ZW5kZWUoXG4gICAgICAgICAgZSxcbiAgICAgICAgICB3b3JrVGltZXMsXG4gICAgICAgICAgZmlsdGVyZWRBbGxFdmVudHMsXG4gICAgICAgICAgaG9zdFRpbWV6b25lXG4gICAgICAgIClcbiAgICAgICk7XG4gICAgaWYgKGZvcm1hdHRlZEV2ZW50UGFydHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGV2ZW50UGFydHMucHVzaCguLi5mb3JtYXR0ZWRFdmVudFBhcnRzKTtcbiAgICB9XG5cbiAgICBpZiAoZXZlbnRQYXJ0cy5sZW5ndGggPiAwKSB7XG4gICAgICBldmVudFBhcnRzLmZvckVhY2goKGUpID0+IGNvbnNvbGUubG9nKGUsICcgZXZlbnRQYXJ0cyBhZnRlciBmb3JtYXR0aW5nJykpO1xuICAgICAgY29uc3QgbmV3RXZlbnRQYXJ0c1dpdGhQcmVmZXJyZWRUaW1lU2V0ID0gZXZlbnRQYXJ0cy5tYXAoKGUpID0+XG4gICAgICAgIHNldFByZWZlcnJlZFRpbWVGb3JVbk1vZGlmaWFibGVFdmVudChcbiAgICAgICAgICBlLFxuICAgICAgICAgIGFsbEV4dGVybmFsRXZlbnRzLmZpbmQoKGYpID0+IGYuaWQgPT09IGUuZXZlbnRJZCk/LnRpbWV6b25lXG4gICAgICAgIClcbiAgICAgICk7XG4gICAgICBuZXdFdmVudFBhcnRzV2l0aFByZWZlcnJlZFRpbWVTZXQuZm9yRWFjaCgoZSkgPT5cbiAgICAgICAgY29uc29sZS5sb2coZSwgJyBuZXdFdmVudFBhcnRzV2l0aFByZWZlcnJlZFRpbWVTZXQnKVxuICAgICAgKTtcbiAgICAgIGNvbnN0IG5ld0V2ZW50UGFydHMgPSBhd2FpdCB0YWdFdmVudHNGb3JEYWlseU9yV2Vla2x5VGFzayhcbiAgICAgICAgbmV3RXZlbnRQYXJ0c1dpdGhQcmVmZXJyZWRUaW1lU2V0XG4gICAgICApO1xuICAgICAgbmV3RXZlbnRQYXJ0cy5mb3JFYWNoKChlKSA9PlxuICAgICAgICBjb25zb2xlLmxvZyhlLCAnIG5ld0V2ZW50UGFydHMgYWZ0ZXIgdGFnRXZlbnRzRm9yRGFpbHlPcldlZWtseVRhc2snKVxuICAgICAgKTtcbiAgICAgIGNvbnN0IHVzZXJMaXN0OiBVc2VyUGxhbm5lclJlcXVlc3RCb2R5VHlwZVtdID0gW107XG4gICAgICBmb3IgKGNvbnN0IGV4dGVybmFsQXR0ZW5kZWUgb2YgZXh0ZXJuYWxBdHRlbmRlZXMpIHtcbiAgICAgICAgY29uc3QgdXNlclBsYW5uZXJSZXF1ZXN0Qm9keSA9XG4gICAgICAgICAgZ2VuZXJhdGVVc2VyUGxhbm5lclJlcXVlc3RCb2R5Rm9yRXh0ZXJuYWxBdHRlbmRlZShcbiAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWU/LnVzZXJJZCxcbiAgICAgICAgICAgIHdvcmtUaW1lcyxcbiAgICAgICAgICAgIG1haW5Ib3N0SWRcbiAgICAgICAgICApO1xuICAgICAgICBjb25zb2xlLmxvZyh1c2VyUGxhbm5lclJlcXVlc3RCb2R5LCAnIHVzZXJQbGFubmVyUmVxdWVzdEJvZHknKTtcbiAgICAgICAgdXNlckxpc3QucHVzaCh1c2VyUGxhbm5lclJlcXVlc3RCb2R5KTtcbiAgICAgIH1cblxuICAgICAgY29uc3QgbW9kaWZpZWROZXdFdmVudFBhcnRzOiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlW10gPVxuICAgICAgICBuZXdFdmVudFBhcnRzLm1hcCgoZXZlbnRQYXJ0KSA9PiB7XG4gICAgICAgICAgY29uc3Qgb2xkRXZlbnQgPSBmaWx0ZXJlZEFsbEV2ZW50cy5maW5kKFxuICAgICAgICAgICAgKGV2ZW50KSA9PiBldmVudC5pZCA9PT0gZXZlbnRQYXJ0LmV2ZW50SWRcbiAgICAgICAgICApO1xuICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICBncm91cElkOiBldmVudFBhcnQ/Lmdyb3VwSWQsXG4gICAgICAgICAgICBldmVudElkOiBldmVudFBhcnQ/LmV2ZW50SWQsXG4gICAgICAgICAgICBwYXJ0OiBldmVudFBhcnQ/LnBhcnQsXG4gICAgICAgICAgICBsYXN0UGFydDogZXZlbnRQYXJ0Py5sYXN0UGFydCxcbiAgICAgICAgICAgIG1lZXRpbmdQYXJ0OiBldmVudFBhcnQ/Lm1lZXRpbmdQYXJ0LFxuICAgICAgICAgICAgbWVldGluZ0xhc3RQYXJ0OiBldmVudFBhcnQ/Lm1lZXRpbmdMYXN0UGFydCxcbiAgICAgICAgICAgIG1lZXRpbmdJZDogZXZlbnRQYXJ0Py5tZWV0aW5nSWQsXG4gICAgICAgICAgICBob3N0SWQ6IG1haW5Ib3N0SWQsXG4gICAgICAgICAgICBzdGFydERhdGU6IGRheWpzKGV2ZW50UGFydD8uc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG9sZEV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tOnNzJyksXG4gICAgICAgICAgICBlbmREYXRlOiBkYXlqcyhldmVudFBhcnQ/LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoob2xkRXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW06c3MnKSxcbiAgICAgICAgICAgIHVzZXJJZDogZXZlbnRQYXJ0Py51c2VySWQsXG4gICAgICAgICAgICB1c2VyOiBldmVudFBhcnQ/LnVzZXIsXG4gICAgICAgICAgICBwcmlvcml0eTogZXZlbnRQYXJ0Py5wcmlvcml0eSxcbiAgICAgICAgICAgIGlzUHJlRXZlbnQ6IGV2ZW50UGFydD8uaXNQcmVFdmVudCxcbiAgICAgICAgICAgIGlzUG9zdEV2ZW50OiBldmVudFBhcnQ/LmlzUG9zdEV2ZW50LFxuICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RTY29yZTogZXZlbnRQYXJ0Py5wb3NpdGl2ZUltcGFjdFNjb3JlLFxuICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3RTY29yZTogZXZlbnRQYXJ0Py5uZWdhdGl2ZUltcGFjdFNjb3JlLFxuICAgICAgICAgICAgbW9kaWZpYWJsZTogZXZlbnRQYXJ0Py5tb2RpZmlhYmxlLFxuICAgICAgICAgICAgaXNNZWV0aW5nOiBldmVudFBhcnQ/LmlzTWVldGluZyxcbiAgICAgICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nOiBldmVudFBhcnQ/LmlzRXh0ZXJuYWxNZWV0aW5nLFxuICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlOiBldmVudFBhcnQ/LmlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgICAgICAgIGlzTWVldGluZ01vZGlmaWFibGU6IGV2ZW50UGFydD8uaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgICAgICAgIGRhaWx5VGFza0xpc3Q6IGV2ZW50UGFydD8uZGFpbHlUYXNrTGlzdCxcbiAgICAgICAgICAgIHdlZWtseVRhc2tMaXN0OiBldmVudFBhcnQ/LndlZWtseVRhc2tMaXN0LFxuICAgICAgICAgICAgZ2FwOiBldmVudFBhcnQ/LmdhcCxcbiAgICAgICAgICAgIHRvdGFsV29ya2luZ0hvdXJzOiBldmVudFBhcnQ/LnRvdGFsV29ya2luZ0hvdXJzLFxuICAgICAgICAgICAgaGFyZERlYWRsaW5lOiBldmVudFBhcnQ/LmhhcmREZWFkbGluZSxcbiAgICAgICAgICAgIHNvZnREZWFkbGluZTogZXZlbnRQYXJ0Py5zb2Z0RGVhZGxpbmUsXG4gICAgICAgICAgICBmb3JFdmVudElkOiBldmVudFBhcnQ/LmZvckV2ZW50SWQsXG4gICAgICAgICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2VlazogZXZlbnRQYXJ0Py5wb3NpdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0VGltZTogZXZlbnRQYXJ0Py5wb3NpdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2VlazogZXZlbnRQYXJ0Py5uZWdhdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZTogZXZlbnRQYXJ0Py5uZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgICAgICBwcmVmZXJyZWREYXlPZldlZWs6IGV2ZW50UGFydD8ucHJlZmVycmVkRGF5T2ZXZWVrLFxuICAgICAgICAgICAgcHJlZmVycmVkVGltZTogZXZlbnRQYXJ0Py5wcmVmZXJyZWRUaW1lLFxuICAgICAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U6IGV2ZW50UGFydD8ucHJlZmVycmVkU3RhcnRUaW1lUmFuZ2UsXG4gICAgICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2U6IGV2ZW50UGFydD8ucHJlZmVycmVkRW5kVGltZVJhbmdlLFxuICAgICAgICAgICAgZXZlbnQ6IGV2ZW50UGFydD8uZXZlbnQsXG4gICAgICAgICAgfTtcbiAgICAgICAgfSk7XG5cbiAgICAgIHJldHVybiBtb2RpZmllZE5ld0V2ZW50UGFydHM/Lmxlbmd0aCA+IDBcbiAgICAgICAgPyB7XG4gICAgICAgICAgICB1c2VySWRzLFxuICAgICAgICAgICAgaG9zdElkOiBtYWluSG9zdElkLFxuICAgICAgICAgICAgZXZlbnRQYXJ0czogbW9kaWZpZWROZXdFdmVudFBhcnRzLFxuICAgICAgICAgICAgYWxsRXZlbnRzOiBmaWx0ZXJlZEFsbEV2ZW50cyxcbiAgICAgICAgICAgIG9sZEF0dGVuZGVlRXZlbnRzOiBhbGxFeHRlcm5hbEV2ZW50cyxcbiAgICAgICAgICAgIHRpbWVzbG90cyxcbiAgICAgICAgICAgIHVzZXJMaXN0LFxuICAgICAgICAgIH1cbiAgICAgICAgOiBudWxsO1xuICAgIH1cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZSxcbiAgICAgICcgdW5hYmxlIHRvIHByb2Nlc3MgZXZlbnRzIGZvciBvcHRhcGxhbm5lciBmb3IgZXh0ZXJuYWwgYXR0ZW5kZWUnXG4gICAgKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IG9wdGFQbGFuV2Vla2x5ID0gYXN5bmMgKFxuICB0aW1lc2xvdHM6IFRpbWVTbG90VHlwZVtdLFxuICB1c2VyTGlzdDogVXNlclBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSxcbiAgZXZlbnRQYXJ0czogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZVtdLFxuICBzaW5nbGV0b25JZDogc3RyaW5nLFxuICBob3N0SWQ6IHN0cmluZyxcbiAgZmlsZUtleTogc3RyaW5nLFxuICBkZWxheTogbnVtYmVyLFxuICBjYWxsQmFja1VybDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICAvLyBwb3B1bGF0ZSB0aW1lc2xvdHMgd2l0aCBldmVudHNcbiAgICBjb25zdCByZXF1ZXN0Qm9keTogUGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9IHtcbiAgICAgIHNpbmdsZXRvbklkLFxuICAgICAgaG9zdElkLFxuICAgICAgdGltZXNsb3RzLFxuICAgICAgdXNlckxpc3QsXG4gICAgICBldmVudFBhcnRzLFxuICAgICAgZmlsZUtleSxcbiAgICAgIGRlbGF5LFxuICAgICAgY2FsbEJhY2tVcmwsXG4gICAgfTtcblxuICAgIGF3YWl0IGdvdFxuICAgICAgLnBvc3QoYCR7b3B0YVBsYW5uZXJVcmx9L3RpbWVUYWJsZS9hZG1pbi9zb2x2ZS1kYXlgLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgIEF1dGhvcml6YXRpb246IGBCYXNpYyAke0J1ZmZlci5mcm9tKGAke29wdGFQbGFubmVyVXNlcm5hbWV9OiR7b3B0YVBsYW5uZXJQYXNzd29yZH1gKS50b1N0cmluZygnYmFzZTY0Jyl9YCxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjogcmVxdWVzdEJvZHksXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKCcgb3B0YVBsYW5XZWVrbHkgY2FsbGVkJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIG9wdGFQbGFuV2Vla2x5Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB1cGRhdGVGcmVlbWl1bUJ5SWQgPSBhc3luYyAoaWQ6IHN0cmluZywgdXNhZ2U6IG51bWJlcikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnVXBkYXRlRnJlZW1pdW1CeUlkJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIG11dGF0aW9uIFVwZGF0ZUZyZWVtaXVtQnlJZCgkaWQ6IHV1aWQhLCAkdXNhZ2U6IEludCEpIHtcbiAgICAgICAgICAgICAgICB1cGRhdGVfRnJlZW1pdW1fYnlfcGsocGtfY29sdW1uczoge2lkOiAkaWR9LCBfc2V0OiB7dXNhZ2U6ICR1c2FnZX0pIHtcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIHBlcmlvZFxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNhZ2VcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgaWQsXG4gICAgICB1c2FnZSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IHsgZGF0YTogeyB1cGRhdGVfRnJlZW1pdW1fYnlfcGs6IEZyZWVtaXVtVHlwZSB9IH0gPVxuICAgICAgYXdhaXQgZ290XG4gICAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICAgIH0sXG4gICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgICAgIC5qc29uKCk7XG4gICAgY29uc29sZS5sb2coXG4gICAgICByZXNwb25zZSxcbiAgICAgIHJlc3BvbnNlPy5kYXRhPy51cGRhdGVfRnJlZW1pdW1fYnlfcGssXG4gICAgICAnIHJlc3BvbnNlIGFmdGVyIHVwZGF0aW5nIHVwZGF0ZV9GcmVlbWl1bV9ieV9waydcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlc3BvbnNlPy5kYXRhPy51cGRhdGVfRnJlZW1pdW1fYnlfcGs7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cGRhdGUgZnJlZW1pdW0nKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldEZyZWVtaXVtQnlVc2VySWQgPSBhc3luYyAodXNlcklkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0dldEZyZWVtaXVtQnlVc2VySWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgR2V0RnJlZW1pdW1CeVVzZXJJZCgkdXNlcklkOiB1dWlkISkge1xuICAgICAgICAgICAgICAgIEZyZWVtaXVtKHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfX0pIHtcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIHBlcmlvZFxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNhZ2VcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgdXNlcklkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBGcmVlbWl1bTogRnJlZW1pdW1UeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBnZXRGcmVlbWl1bUJ5VXNlcklkICcpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uRnJlZW1pdW0/LlswXTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKCcgdW5hYmxlIHRvIGdldCBmcmVlbWl1bSBieSB1c2VyIGlkJyk7XG4gIH1cbn07XG5cbi8vIGF0dGVuZGVlTWVldGluZ0V2ZW50cyBpbmNsdWRlIGhvc3RNZWV0aW5nIGFzIHdlbGxcbmV4cG9ydCBjb25zdCBwcm9jZXNzRXZlbnRzRm9yT3B0YVBsYW5uZXIgPSBhc3luYyAoXG4gIG1haW5Ib3N0SWQ6IHN0cmluZyxcbiAgaW50ZXJuYWxBdHRlbmRlZXM6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXSxcbiAgbWVldGluZ0V2ZW50UGx1czogRXZlbnRNZWV0aW5nUGx1c1R5cGVbXSwgLy8gZXZlbnRzIHdpdGggYSBtZWV0aW5nSWRcbiAgbmV3TWVldGluZ0V2ZW50UGx1czogRXZlbnRNZWV0aW5nUGx1c1R5cGVbXSxcbiAgYWxsRXZlbnRzOiBFdmVudFBsdXNUeXBlW10sXG4gIHdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nLFxuICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICBvbGRFdmVudHM6IEV2ZW50UGx1c1R5cGVbXSxcbiAgZXh0ZXJuYWxBdHRlbmRlZXM/OiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10sXG4gIG1lZXRpbmdBc3Npc3RFdmVudHM/OiBNZWV0aW5nQXNzaXN0RXZlbnRUeXBlW10sXG4gIG5ld0hvc3RSZW1pbmRlcnM/OiBSZW1pbmRlcnNGb3JFdmVudFR5cGVbXSxcbiAgbmV3SG9zdEJ1ZmZlclRpbWVzPzogQnVmZmVyVGltZU9iamVjdFR5cGVbXVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgLyoqXG4gICAgICogcGFyZW50S2V5OiBob3N0SWQvc2luZ2xldG9uSWRcbiAgICAgKiBjaGlsZEtleTogaG9zdElkL3NpbmdsZXRvbmVJZC97aW50ZXJuYWwgfCBleHRlcm5hbCB8IGhvc3RPbmx5fVxuICAgICAqIGhvc3RJc0ludGVybmFsQXR0ZW5kZWU6IGJvb2xlYW5cbiAgICAgKiBleHRlcm5hbEF0dGVuZGVlczogYm9vbGVhblxuICAgICAqIGludGVybmFsQXR0ZW5kZWVzOiBib29sZWFuXG4gICAgICogaG9zdElzSW50ZXJuYWxBdHRlbmRlZTogZmFsc2UgPT4gSG9zdE9ubHlQcm9jZXNzZWQ6IGJvb2xlYW5cbiAgICAgKiBob3N0SXNJbnRlcm5hbEF0dGVuZGVlOiB0cnVlID0+IGludGVybmFsQXR0ZW5kZWVzUHJvY2Vzc2VkOiBib29sZWFuXG4gICAgICovXG5cbiAgICBjb25zdCBuZXdJbnRlcm5hbE1lZXRpbmdFdmVudHNQbHVzID0gbmV3TWVldGluZ0V2ZW50UGx1c1xuICAgICAgPy5tYXAoKGUpID0+IHtcbiAgICAgICAgY29uc3QgZm91bmRJbmRleCA9IGV4dGVybmFsQXR0ZW5kZWVzPy5maW5kSW5kZXgoXG4gICAgICAgICAgKGEpID0+IGE/LnVzZXJJZCA9PT0gZT8udXNlcklkXG4gICAgICAgICk7XG5cbiAgICAgICAgaWYgKGZvdW5kSW5kZXggPiAtMSkge1xuICAgICAgICAgIHJldHVybiBudWxsO1xuICAgICAgICB9XG4gICAgICAgIHJldHVybiBlO1xuICAgICAgfSlcbiAgICAgID8uZmlsdGVyKChlKSA9PiBlICE9PSBudWxsKTtcblxuICAgIGNvbnN0IG5ld0V4dGVybmFsTWVldGluZ0V2ZW50c1BsdXMgPSBuZXdNZWV0aW5nRXZlbnRQbHVzXG4gICAgICA/Lm1hcCgoZSkgPT4ge1xuICAgICAgICBjb25zdCBmb3VuZEluZGV4ID0gZXh0ZXJuYWxBdHRlbmRlZXM/LmZpbmRJbmRleChcbiAgICAgICAgICAoYSkgPT4gYT8udXNlcklkID09PSBlPy51c2VySWRcbiAgICAgICAgKTtcblxuICAgICAgICBpZiAoZm91bmRJbmRleCA+IC0xKSB7XG4gICAgICAgICAgcmV0dXJuIGU7XG4gICAgICAgIH1cbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9KVxuICAgICAgPy5maWx0ZXIoKGUpID0+IGUgIT09IG51bGwpO1xuXG4gICAgY29uc3QgYWxsSG9zdEV2ZW50cyA9IGFsbEV2ZW50cy5maWx0ZXIoKGUpID0+IGUudXNlcklkID09PSBtYWluSG9zdElkKTtcblxuICAgIGNvbnN0IG9sZEhvc3RFdmVudHMgPSBvbGRFdmVudHMuZmlsdGVyKChlKSA9PiBlPy51c2VySWQgPT09IG1haW5Ib3N0SWQpO1xuXG4gICAgLy8gZWl0aGVyIG9yIC0gZWl0aGVyIHRoZXJlIGFyZSBpbnRlcm5hbCBhdHRlbmRlZXMgdGhhdCBoYXZlIG1haW4gaG9zdCBpbmNsdWRlZFxuICAgIC8vIG9yIG1haW4gaG9zdCBpcyBub3QgcGFydCBvZiBpbnRlcm5hbCBhdHRlbmRlZXNcblxuICAgIGNvbnN0IGhvc3RJc0ludGVybmFsQXR0ZW5kZWUgPSBpbnRlcm5hbEF0dGVuZGVlcy5zb21lKFxuICAgICAgKGlhKSA9PiBpYT8udXNlcklkID09PSBtYWluSG9zdElkXG4gICAgKTtcblxuICAgIGxldCByZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXM6XG4gICAgICB8IFJldHVybkJvZHlGb3JBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGVcbiAgICAgIHwge30gPSB7fTtcbiAgICBsZXQgcmV0dXJuVmFsdWVzRnJvbUhvc3Q6IFJldHVybkJvZHlGb3JIb3N0Rm9yT3B0YXBsYW5uZXJQcmVwVHlwZSB8IHt9ID0ge307XG5cbiAgICBjb25zb2xlLmxvZyhob3N0SXNJbnRlcm5hbEF0dGVuZGVlLCAnIGhvc3RJc0ludGVybmFsQXR0ZW5kZWUnKTtcblxuICAgIGlmIChob3N0SXNJbnRlcm5hbEF0dGVuZGVlKSB7XG4gICAgICByZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMgPVxuICAgICAgICBhd2FpdCBwcm9jZXNzRXZlbnRzRm9yT3B0YVBsYW5uZXJGb3JJbnRlcm5hbEF0dGVuZGVlcyhcbiAgICAgICAgICBtYWluSG9zdElkLFxuICAgICAgICAgIGFsbEV2ZW50cyxcbiAgICAgICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgICAgaW50ZXJuYWxBdHRlbmRlZXMsXG4gICAgICAgICAgb2xkRXZlbnRzLFxuICAgICAgICAgIG1lZXRpbmdFdmVudFBsdXMsXG4gICAgICAgICAgbmV3SW50ZXJuYWxNZWV0aW5nRXZlbnRzUGx1cyxcbiAgICAgICAgICBuZXdIb3N0QnVmZmVyVGltZXNcbiAgICAgICAgKTtcbiAgICB9IGVsc2Uge1xuICAgICAgLy8gaG9zdCBpcyBub3QgcGFydCBvZiBpbnRlcm5hbCBhdHRlbmRlZXNcbiAgICAgIHJldHVyblZhbHVlc0Zyb21Ib3N0ID0gYXdhaXQgcHJvY2Vzc0V2ZW50c0Zvck9wdGFQbGFubmVyRm9yTWFpbkhvc3QoXG4gICAgICAgIG1haW5Ib3N0SWQsXG4gICAgICAgIGFsbEhvc3RFdmVudHMsXG4gICAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICBvbGRIb3N0RXZlbnRzLFxuICAgICAgICBuZXdIb3N0QnVmZmVyVGltZXNcbiAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2coXG4gICAgICByZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMsXG4gICAgICAnIHJldHVyblZhbHVlc0Zyb21JbnRlcm5hbEF0dGVuZGVlcydcbiAgICApO1xuICAgIGNvbnN0IGV4dGVybmFsTWVldGluZ0V2ZW50UGx1cyA9IG1lZXRpbmdFdmVudFBsdXNcbiAgICAgIC5tYXAoKGUpID0+IHtcbiAgICAgICAgY29uc3QgZm91bmRJbmRleCA9IGV4dGVybmFsQXR0ZW5kZWVzLmZpbmRJbmRleChcbiAgICAgICAgICAoYSkgPT4gYT8udXNlcklkID09PSBlPy51c2VySWRcbiAgICAgICAgKTtcbiAgICAgICAgaWYgKGZvdW5kSW5kZXggPiAtMSkge1xuICAgICAgICAgIHJldHVybiBlO1xuICAgICAgICB9XG4gICAgICAgIHJldHVybiBudWxsO1xuICAgICAgfSlcbiAgICAgID8uZmlsdGVyKChlKSA9PiBlICE9PSBudWxsKTtcblxuICAgIGNvbnN0IHJldHVyblZhbHVlc0Zyb21FeHRlcm5hbEF0dGVuZGVlczogUmV0dXJuQm9keUZvckV4dGVybmFsQXR0ZW5kZWVGb3JPcHRhcGxhbm5lclByZXBUeXBlID1cbiAgICAgIGV4dGVybmFsQXR0ZW5kZWVzPy5sZW5ndGggPiAwXG4gICAgICAgID8gYXdhaXQgcHJvY2Vzc0V2ZW50c0Zvck9wdGFQbGFubmVyRm9yRXh0ZXJuYWxBdHRlbmRlZXMoXG4gICAgICAgICAgICBleHRlcm5hbEF0dGVuZGVlcz8ubWFwKChhKSA9PiBhLnVzZXJJZCksXG4gICAgICAgICAgICBtYWluSG9zdElkLFxuICAgICAgICAgICAgbWVldGluZ0Fzc2lzdEV2ZW50cyxcbiAgICAgICAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgICAgICBleHRlcm5hbEF0dGVuZGVlcyxcbiAgICAgICAgICAgIGV4dGVybmFsTWVldGluZ0V2ZW50UGx1cywgLy8gZXZlbnRzIHdpdGggbWVldGluZ0lkXG4gICAgICAgICAgICBuZXdFeHRlcm5hbE1lZXRpbmdFdmVudHNQbHVzXG4gICAgICAgICAgKVxuICAgICAgICA6IG51bGw7XG5cbiAgICBjb25zdCBldmVudFBhcnRzOiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlW10gPSBbXTtcbiAgICBjb25zdCBhbGxFdmVudHNGb3JQbGFubmVyOiBFdmVudFBsdXNUeXBlW10gPSBbXTtcbiAgICBjb25zdCBicmVha3M6IEV2ZW50UGx1c1R5cGVbXSA9IFtdO1xuICAgIGNvbnN0IG9sZEV2ZW50c0ZvclBsYW5uZXI6IEV2ZW50UGx1c1R5cGVbXSA9IFtdO1xuICAgIGNvbnN0IG9sZEF0dGVuZGVlRXZlbnRzOiBNZWV0aW5nQXNzaXN0RXZlbnRUeXBlW10gPSBbXTtcbiAgICBjb25zdCB1bmZpbHRlcmVkVGltZXNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuICAgIGNvbnN0IHVuZmlsdGVyZWRVc2VyTGlzdDogVXNlclBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSA9IFtdO1xuXG4gICAgLy8gc3RhcnQgZmlsbGluZyB1cCB0aGUgYXJyYXlzIGZvciBvcHRhUGxhbm5lclxuICAgIGlmIChcbiAgICAgIChyZXR1cm5WYWx1ZXNGcm9tSG9zdCBhcyBSZXR1cm5Cb2R5Rm9ySG9zdEZvck9wdGFwbGFubmVyUHJlcFR5cGUpXG4gICAgICAgID8uZXZlbnRQYXJ0cz8ubGVuZ3RoID4gMFxuICAgICkge1xuICAgICAgZXZlbnRQYXJ0cy5wdXNoKFxuICAgICAgICAuLi4ocmV0dXJuVmFsdWVzRnJvbUhvc3QgYXMgUmV0dXJuQm9keUZvckhvc3RGb3JPcHRhcGxhbm5lclByZXBUeXBlKVxuICAgICAgICAgID8uZXZlbnRQYXJ0c1xuICAgICAgKTtcbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICAocmV0dXJuVmFsdWVzRnJvbUhvc3QgYXMgUmV0dXJuQm9keUZvckhvc3RGb3JPcHRhcGxhbm5lclByZXBUeXBlKVxuICAgICAgICA/LmFsbEV2ZW50cz8ubGVuZ3RoID4gMFxuICAgICkge1xuICAgICAgYWxsRXZlbnRzRm9yUGxhbm5lci5wdXNoKFxuICAgICAgICAuLi4ocmV0dXJuVmFsdWVzRnJvbUhvc3QgYXMgUmV0dXJuQm9keUZvckhvc3RGb3JPcHRhcGxhbm5lclByZXBUeXBlKVxuICAgICAgICAgID8uYWxsRXZlbnRzXG4gICAgICApO1xuICAgIH1cblxuICAgIGlmIChcbiAgICAgIChyZXR1cm5WYWx1ZXNGcm9tSG9zdCBhcyBSZXR1cm5Cb2R5Rm9ySG9zdEZvck9wdGFwbGFubmVyUHJlcFR5cGUpPy5icmVha3NcbiAgICAgICAgPy5sZW5ndGggPiAwXG4gICAgKSB7XG4gICAgICBicmVha3MucHVzaChcbiAgICAgICAgLi4uKHJldHVyblZhbHVlc0Zyb21Ib3N0IGFzIFJldHVybkJvZHlGb3JIb3N0Rm9yT3B0YXBsYW5uZXJQcmVwVHlwZSlcbiAgICAgICAgICA/LmJyZWFrc1xuICAgICAgKTtcbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICAocmV0dXJuVmFsdWVzRnJvbUhvc3QgYXMgUmV0dXJuQm9keUZvckhvc3RGb3JPcHRhcGxhbm5lclByZXBUeXBlKVxuICAgICAgICA/Lm9sZEV2ZW50cz8ubGVuZ3RoID4gMFxuICAgICkge1xuICAgICAgb2xkRXZlbnRzRm9yUGxhbm5lci5wdXNoKFxuICAgICAgICAuLi4ocmV0dXJuVmFsdWVzRnJvbUhvc3QgYXMgUmV0dXJuQm9keUZvckhvc3RGb3JPcHRhcGxhbm5lclByZXBUeXBlKVxuICAgICAgICAgID8ub2xkRXZlbnRzXG4gICAgICApO1xuICAgIH1cblxuICAgIGlmIChcbiAgICAgIChyZXR1cm5WYWx1ZXNGcm9tSG9zdCBhcyBSZXR1cm5Cb2R5Rm9ySG9zdEZvck9wdGFwbGFubmVyUHJlcFR5cGUpXG4gICAgICAgID8udGltZXNsb3RzPy5sZW5ndGggPiAwXG4gICAgKSB7XG4gICAgICB1bmZpbHRlcmVkVGltZXNsb3RzLnB1c2goXG4gICAgICAgIC4uLihyZXR1cm5WYWx1ZXNGcm9tSG9zdCBhcyBSZXR1cm5Cb2R5Rm9ySG9zdEZvck9wdGFwbGFubmVyUHJlcFR5cGUpXG4gICAgICAgICAgPy50aW1lc2xvdHNcbiAgICAgICk7XG4gICAgfVxuXG4gICAgaWYgKFxuICAgICAgKHJldHVyblZhbHVlc0Zyb21Ib3N0IGFzIFJldHVybkJvZHlGb3JIb3N0Rm9yT3B0YXBsYW5uZXJQcmVwVHlwZSlcbiAgICAgICAgPy51c2VyUGxhbm5lclJlcXVlc3RCb2R5Py5pZFxuICAgICkge1xuICAgICAgdW5maWx0ZXJlZFVzZXJMaXN0LnB1c2goXG4gICAgICAgIChyZXR1cm5WYWx1ZXNGcm9tSG9zdCBhcyBSZXR1cm5Cb2R5Rm9ySG9zdEZvck9wdGFwbGFubmVyUHJlcFR5cGUpXG4gICAgICAgICAgPy51c2VyUGxhbm5lclJlcXVlc3RCb2R5XG4gICAgICApO1xuICAgIH1cblxuICAgIGlmIChcbiAgICAgIChcbiAgICAgICAgcmV0dXJuVmFsdWVzRnJvbUludGVybmFsQXR0ZW5kZWVzIGFzIFJldHVybkJvZHlGb3JBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGVcbiAgICAgICk/LnVzZXJMaXN0Py5bMF0/LmlkXG4gICAgKSB7XG4gICAgICB1bmZpbHRlcmVkVXNlckxpc3QucHVzaChcbiAgICAgICAgLi4uKFxuICAgICAgICAgIHJldHVyblZhbHVlc0Zyb21JbnRlcm5hbEF0dGVuZGVlcyBhcyBSZXR1cm5Cb2R5Rm9yQXR0ZW5kZWVGb3JPcHRhcGxhbm5lclByZXBUeXBlXG4gICAgICAgICk/LnVzZXJMaXN0XG4gICAgICApO1xuICAgIH1cblxuICAgIChcbiAgICAgIHJldHVyblZhbHVlc0Zyb21JbnRlcm5hbEF0dGVuZGVlcyBhcyBSZXR1cm5Cb2R5Rm9yQXR0ZW5kZWVGb3JPcHRhcGxhbm5lclByZXBUeXBlXG4gICAgKT8uZXZlbnRQYXJ0cz8uZm9yRWFjaCgoZSkgPT5cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBlLFxuICAgICAgICAnIChyZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMgYXMgUmV0dXJuQm9keUZvckF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZSk/LmV2ZW50UGFydHMnXG4gICAgICApXG4gICAgKTtcblxuICAgIGlmIChcbiAgICAgIChcbiAgICAgICAgcmV0dXJuVmFsdWVzRnJvbUludGVybmFsQXR0ZW5kZWVzIGFzIFJldHVybkJvZHlGb3JBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGVcbiAgICAgICk/LmV2ZW50UGFydHM/Lmxlbmd0aCA+IDBcbiAgICApIHtcbiAgICAgIGV2ZW50UGFydHMucHVzaChcbiAgICAgICAgLi4uKFxuICAgICAgICAgIHJldHVyblZhbHVlc0Zyb21JbnRlcm5hbEF0dGVuZGVlcyBhcyBSZXR1cm5Cb2R5Rm9yQXR0ZW5kZWVGb3JPcHRhcGxhbm5lclByZXBUeXBlXG4gICAgICAgICk/LmV2ZW50UGFydHNcbiAgICAgICk7XG4gICAgfVxuXG4gICAgaWYgKFxuICAgICAgKFxuICAgICAgICByZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMgYXMgUmV0dXJuQm9keUZvckF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZVxuICAgICAgKT8uYWxsRXZlbnRzPy5sZW5ndGggPiAwXG4gICAgKSB7XG4gICAgICBhbGxFdmVudHNGb3JQbGFubmVyLnB1c2goXG4gICAgICAgIC4uLihcbiAgICAgICAgICByZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMgYXMgUmV0dXJuQm9keUZvckF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZVxuICAgICAgICApPy5hbGxFdmVudHNcbiAgICAgICk7XG4gICAgfVxuXG4gICAgKFxuICAgICAgcmV0dXJuVmFsdWVzRnJvbUludGVybmFsQXR0ZW5kZWVzIGFzIFJldHVybkJvZHlGb3JBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGVcbiAgICApPy5icmVha3M/LmZvckVhY2goKGUpID0+XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgZSxcbiAgICAgICAgJyAocmV0dXJuVmFsdWVzRnJvbUludGVybmFsQXR0ZW5kZWVzIGFzIFJldHVybkJvZHlGb3JBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGUpPy5icmVha3MnXG4gICAgICApXG4gICAgKTtcblxuICAgIGlmIChcbiAgICAgIChcbiAgICAgICAgcmV0dXJuVmFsdWVzRnJvbUludGVybmFsQXR0ZW5kZWVzIGFzIFJldHVybkJvZHlGb3JBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGVcbiAgICAgICk/LmJyZWFrcz8ubGVuZ3RoID4gMFxuICAgICkge1xuICAgICAgYnJlYWtzLnB1c2goXG4gICAgICAgIC4uLihcbiAgICAgICAgICByZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMgYXMgUmV0dXJuQm9keUZvckF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZVxuICAgICAgICApPy5icmVha3NcbiAgICAgICk7XG4gICAgfVxuXG4gICAgaWYgKFxuICAgICAgKFxuICAgICAgICByZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMgYXMgUmV0dXJuQm9keUZvckF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZVxuICAgICAgKT8ub2xkRXZlbnRzPy5sZW5ndGggPiAwXG4gICAgKSB7XG4gICAgICBvbGRFdmVudHNGb3JQbGFubmVyLnB1c2goXG4gICAgICAgIC4uLihcbiAgICAgICAgICByZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMgYXMgUmV0dXJuQm9keUZvckF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZVxuICAgICAgICApPy5vbGRFdmVudHNcbiAgICAgICk7XG4gICAgfVxuXG4gICAgaWYgKFxuICAgICAgKFxuICAgICAgICByZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMgYXMgUmV0dXJuQm9keUZvckF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZVxuICAgICAgKT8udGltZXNsb3RzPy5sZW5ndGggPiAwXG4gICAgKSB7XG4gICAgICB1bmZpbHRlcmVkVGltZXNsb3RzLnB1c2goXG4gICAgICAgIC4uLihcbiAgICAgICAgICByZXR1cm5WYWx1ZXNGcm9tSW50ZXJuYWxBdHRlbmRlZXMgYXMgUmV0dXJuQm9keUZvckF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZVxuICAgICAgICApPy50aW1lc2xvdHNcbiAgICAgICk7XG4gICAgfVxuXG4gICAgaWYgKHJldHVyblZhbHVlc0Zyb21FeHRlcm5hbEF0dGVuZGVlcz8uZXZlbnRQYXJ0cz8ubGVuZ3RoID4gMCkge1xuICAgICAgZXZlbnRQYXJ0cy5wdXNoKC4uLnJldHVyblZhbHVlc0Zyb21FeHRlcm5hbEF0dGVuZGVlcz8uZXZlbnRQYXJ0cyk7XG4gICAgfVxuXG4gICAgaWYgKHJldHVyblZhbHVlc0Zyb21FeHRlcm5hbEF0dGVuZGVlcz8uYWxsRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICBhbGxFdmVudHNGb3JQbGFubmVyLnB1c2goLi4ucmV0dXJuVmFsdWVzRnJvbUV4dGVybmFsQXR0ZW5kZWVzPy5hbGxFdmVudHMpO1xuICAgIH1cblxuICAgIGlmIChyZXR1cm5WYWx1ZXNGcm9tRXh0ZXJuYWxBdHRlbmRlZXM/Lm9sZEF0dGVuZGVlRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICBvbGRBdHRlbmRlZUV2ZW50cy5wdXNoKFxuICAgICAgICAuLi5yZXR1cm5WYWx1ZXNGcm9tRXh0ZXJuYWxBdHRlbmRlZXM/Lm9sZEF0dGVuZGVlRXZlbnRzXG4gICAgICApO1xuICAgIH1cblxuICAgIGlmIChyZXR1cm5WYWx1ZXNGcm9tRXh0ZXJuYWxBdHRlbmRlZXM/LnRpbWVzbG90cz8ubGVuZ3RoID4gMCkge1xuICAgICAgdW5maWx0ZXJlZFRpbWVzbG90cy5wdXNoKC4uLnJldHVyblZhbHVlc0Zyb21FeHRlcm5hbEF0dGVuZGVlcz8udGltZXNsb3RzKTtcbiAgICB9XG5cbiAgICBpZiAocmV0dXJuVmFsdWVzRnJvbUV4dGVybmFsQXR0ZW5kZWVzPy51c2VyTGlzdD8ubGVuZ3RoID4gMCkge1xuICAgICAgdW5maWx0ZXJlZFVzZXJMaXN0LnB1c2goLi4ucmV0dXJuVmFsdWVzRnJvbUV4dGVybmFsQXR0ZW5kZWVzPy51c2VyTGlzdCk7XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2cob2xkRXZlbnRzLCAnIG9sZEV2ZW50cyBiZWZvcmUgc2F2aW5nIHRvIHMzJyk7XG5cbiAgICAvLyBjcmVhdGUgZHVwbGljYXRlIGZyZWUgZGF0YVxuICAgIGNvbnN0IGR1cGxpY2F0ZUZyZWVFdmVudFBhcnRzID0gXy51bmlxV2l0aChldmVudFBhcnRzLCBfLmlzRXF1YWwpO1xuICAgIGNvbnN0IGR1cGxpY2F0ZUZyZWVBbGxFdmVudHMgPSBfLnVuaXFXaXRoKGFsbEV2ZW50c0ZvclBsYW5uZXIsIF8uaXNFcXVhbCk7XG4gICAgY29uc3QgZHVwbGljYXRlRnJlZUJyZWFrcyA9IF8udW5pcVdpdGgoYnJlYWtzLCBfLmlzRXF1YWwpO1xuICAgIGNvbnN0IGR1cGxpY2F0ZUZyZWVPbGRFdmVudHMgPSBfLnVuaXFXaXRoKG9sZEV2ZW50cywgXy5pc0VxdWFsKTtcbiAgICBjb25zdCBkdXBsaWNhdGVGcmVlT2xkQXR0ZW5kZWVFdmVudHMgPSBfLnVuaXFXaXRoKFxuICAgICAgb2xkQXR0ZW5kZWVFdmVudHMsXG4gICAgICBfLmlzRXF1YWxcbiAgICApO1xuICAgIGNvbnN0IGR1cGxpY2F0ZUZyZWVUaW1lc2xvdHM6IFRpbWVTbG90VHlwZVtdID0gXy51bmlxV2l0aChcbiAgICAgIHVuZmlsdGVyZWRUaW1lc2xvdHMsXG4gICAgICBfLmlzRXF1YWxcbiAgICApO1xuICAgIGNvbnN0IHNpbmdsZXRvbklkID0gdXVpZCgpO1xuXG4gICAgY29uc29sZS5sb2coZXZlbnRQYXJ0cywgJyBldmVudFBhcnRzIGJlZm9yZSB2YWxpZGF0aW9uJyk7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBkdXBsaWNhdGVGcmVlRXZlbnRQYXJ0cyxcbiAgICAgICcgZHVwbGljYXRlRnJlZUV2ZW50UGFydHMgYmVmb3JlIHZhbGlkYXRpb24nXG4gICAgKTtcbiAgICBjb25zb2xlLmxvZyhkdXBsaWNhdGVGcmVlQWxsRXZlbnRzLCAnIGR1cGxpY2F0ZUZyZWVBbGxFdmVudHMnKTtcbiAgICBjb25zb2xlLmxvZyhkdXBsaWNhdGVGcmVlT2xkRXZlbnRzLCAnIGR1cGxpY2F0ZUZyZWVPbGRFdmVudHMnKTtcbiAgICBjb25zb2xlLmxvZyhkdXBsaWNhdGVGcmVlVGltZXNsb3RzLCAnIGR1cGxpY2F0ZUZyZWVUaW1lc2xvdHMnKTtcbiAgICAvLyB2YWxpZGF0ZSBldmVudFBhcnRzXG4gICAgaWYgKCFkdXBsaWNhdGVGcmVlRXZlbnRQYXJ0cyB8fCBkdXBsaWNhdGVGcmVlRXZlbnRQYXJ0cz8ubGVuZ3RoID09PSAwKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ0V2ZW50IFBhcnRzIGxlbmd0aCBpcyAwIG9yIGRvIG5vdCBleGlzdCcpO1xuICAgIH1cblxuICAgIGlmICghZHVwbGljYXRlRnJlZVRpbWVzbG90cyB8fCAhKGR1cGxpY2F0ZUZyZWVUaW1lc2xvdHM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJyBkdXBsaWNhdGVGcmVlVGltZXNsb3RzIGlzIGVtcHR5Jyk7XG4gICAgfVxuXG4gICAgaWYgKCF1bmZpbHRlcmVkVXNlckxpc3QgfHwgISh1bmZpbHRlcmVkVXNlckxpc3Q/Lmxlbmd0aCA+IDApKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ3VuZmlsdGVyZWRVc2VyTGlzdCBpcyBlbXB0eScpO1xuICAgIH1cblxuICAgIGR1cGxpY2F0ZUZyZWVUaW1lc2xvdHM/LmZvckVhY2goKGQpID0+XG4gICAgICBjb25zb2xlLmxvZyhkLCAnIGR1cGxpY2F0ZUZyZWVUaW1lc2xvdHMnKVxuICAgICk7XG4gICAgdW5maWx0ZXJlZFVzZXJMaXN0Py5mb3JFYWNoKCh1KSA9PiBjb25zb2xlLmxvZyh1LCAnIHVuZmlsdGVyZWRVc2VyTGlzdCcpKTtcbiAgICBuZXdIb3N0QnVmZmVyVGltZXM/LmZvckVhY2goKGIpID0+XG4gICAgICBjb25zb2xlLmxvZyhiLmJlZm9yZUV2ZW50LCBiLmFmdGVyRXZlbnQsICcgYi5iZWZvcmVFdmVudCBiLmFmdGVyRXZlbnQgJylcbiAgICApO1xuXG4gICAgY29uc3QgcGFyYW1zID0ge1xuICAgICAgQm9keTogSlNPTi5zdHJpbmdpZnkoe1xuICAgICAgICBzaW5nbGV0b25JZCxcbiAgICAgICAgaG9zdElkOiBtYWluSG9zdElkLFxuICAgICAgICBldmVudFBhcnRzOiBkdXBsaWNhdGVGcmVlRXZlbnRQYXJ0cyxcbiAgICAgICAgYWxsRXZlbnRzOiBkdXBsaWNhdGVGcmVlQWxsRXZlbnRzLFxuICAgICAgICBicmVha3M6IGR1cGxpY2F0ZUZyZWVCcmVha3MsXG4gICAgICAgIG9sZEV2ZW50czogZHVwbGljYXRlRnJlZU9sZEV2ZW50cyxcbiAgICAgICAgb2xkQXR0ZW5kZWVFdmVudHM6IGR1cGxpY2F0ZUZyZWVPbGRBdHRlbmRlZUV2ZW50cyxcbiAgICAgICAgbmV3SG9zdEJ1ZmZlclRpbWVzOiBuZXdIb3N0QnVmZmVyVGltZXMsXG4gICAgICAgIG5ld0hvc3RSZW1pbmRlcnM6IG5ld0hvc3RSZW1pbmRlcnMsXG4gICAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIH0pLFxuICAgICAgQnVja2V0OiBidWNrZXROYW1lLFxuICAgICAgS2V5OiBgJHttYWluSG9zdElkfS8ke3NpbmdsZXRvbklkfS5qc29uYCxcbiAgICAgIENvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgfTtcblxuICAgIGNvbnN0IHMzQ29tbWFuZCA9IG5ldyBQdXRPYmplY3RDb21tYW5kKHBhcmFtcyk7XG5cbiAgICBjb25zdCBzM1Jlc3BvbnNlID0gYXdhaXQgczNDbGllbnQuc2VuZChzM0NvbW1hbmQpO1xuXG4gICAgY29uc29sZS5sb2coczNSZXNwb25zZSwgJyBzM1Jlc3BvbnNlJyk7XG5cbiAgICBjb25zdCBkaWZmRGF5cyA9IGRheWpzKHdpbmRvd0VuZERhdGUpLmRpZmYod2luZG93U3RhcnREYXRlLCAnZCcpO1xuXG4gICAgaWYgKGRpZmZEYXlzIDwgMikge1xuICAgICAgYXdhaXQgb3B0YVBsYW5XZWVrbHkoXG4gICAgICAgIGR1cGxpY2F0ZUZyZWVUaW1lc2xvdHMsXG4gICAgICAgIHVuZmlsdGVyZWRVc2VyTGlzdCxcbiAgICAgICAgZHVwbGljYXRlRnJlZUV2ZW50UGFydHMsXG4gICAgICAgIHNpbmdsZXRvbklkLFxuICAgICAgICBtYWluSG9zdElkLFxuICAgICAgICBgJHttYWluSG9zdElkfS8ke3NpbmdsZXRvbklkfS5qc29uYCxcbiAgICAgICAgb3B0YXBsYW5uZXJTaG9ydER1cmF0aW9uLFxuICAgICAgICBvbk9wdGFQbGFuQ2FsZW5kYXJBZG1pbkNhbGxCYWNrVXJsXG4gICAgICApO1xuICAgIH0gZWxzZSB7XG4gICAgICBhd2FpdCBvcHRhUGxhbldlZWtseShcbiAgICAgICAgZHVwbGljYXRlRnJlZVRpbWVzbG90cyxcbiAgICAgICAgdW5maWx0ZXJlZFVzZXJMaXN0LFxuICAgICAgICBkdXBsaWNhdGVGcmVlRXZlbnRQYXJ0cyxcbiAgICAgICAgc2luZ2xldG9uSWQsXG4gICAgICAgIG1haW5Ib3N0SWQsXG4gICAgICAgIGAke21haW5Ib3N0SWR9LyR7c2luZ2xldG9uSWR9Lmpzb25gLFxuICAgICAgICBvcHRhcGxhbm5lckR1cmF0aW9uLFxuICAgICAgICBvbk9wdGFQbGFuQ2FsZW5kYXJBZG1pbkNhbGxCYWNrVXJsXG4gICAgICApO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKCdvcHRhcGxhbm5lciByZXF1ZXN0IHNlbnQnKTtcbiAgICAvLyB1cGRhdGUgZnJlZW1pdW0gaWYgbm90IGFjdGl2ZSBzdWJzY3JpcHRpb25cblxuICAgIC8vIGlmICghKGFjdGl2ZVN1YnNjcmlwdGlvbnM/Lmxlbmd0aCA+IDApKSB7XG4gICAgLy8gICAgIGF3YWl0IHVwZGF0ZUZyZWVtaXVtQnlJZChmcmVlbWl1bU9mVXNlcj8uaWQsIGZyZWVtaXVtT2ZVc2VyPy51c2FnZSAtIDEgfHwgMClcbiAgICAvLyB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIGV2ZW50cyBmb3Igb3B0YXBsYW5uZXInKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldFVzZXJDYXRlZ29yaWVzID0gYXN5bmMgKHVzZXJJZCkgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZ2V0VXNlckNhdGVnb3JpZXMnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgcXVlcnkgZ2V0VXNlckNhdGVnb3JpZXMoJHVzZXJJZDogdXVpZCEpIHtcbiAgICAgICAgQ2F0ZWdvcnkod2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9fSkge1xuICAgICAgICAgIG5hbWVcbiAgICAgICAgICB1c2VySWRcbiAgICAgICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICAgICAgY29weVRpbWVCbG9ja2luZ1xuICAgICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgICAgICBjb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgICAgIGNvcHlNb2RpZmlhYmxlXG4gICAgICAgICAgZGVmYXVsdEF2YWlsYWJpbGl0eVxuICAgICAgICAgIGRlZmF1bHRUaW1lQmxvY2tpbmdcbiAgICAgICAgICBkZWZhdWx0VGltZVByZWZlcmVuY2VcbiAgICAgICAgICBkZWZhdWx0UmVtaW5kZXJzXG4gICAgICAgICAgZGVmYXVsdFByaW9yaXR5TGV2ZWxcbiAgICAgICAgICBkZWZhdWx0TW9kaWZpYWJsZVxuICAgICAgICAgIGNvcHlJc0JyZWFrXG4gICAgICAgICAgY29sb3JcbiAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgaWRcbiAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgdXNlcklkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBDYXRlZ29yeTogQ2F0ZWdvcnlUeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/LkNhdGVnb3J5O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IHVzZXIgY2F0ZWdvcmllcycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZmluZEJlc3RNYXRjaENhdGVnb3J5MiA9IGFzeW5jIChcbiAgZXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIHBvc3NpYmxlTGFiZWxzOiBDYXRlZ29yeVR5cGVbXVxuKTogUHJvbWlzZTxDbGFzc2lmaWNhdGlvblJlc3BvbnNlQm9keVR5cGU+ID0+IHtcbiAgdHJ5IHtcbiAgICAvLyB2YWxpZGF0ZVxuICAgIGlmICghZXZlbnQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gZXZlbnQgcGFzc2VkIGluc2lkZSBmaW5kQmVzdE1hdGNoQ2F0ZWdvcnkyJyk7XG4gICAgfVxuXG4gICAgaWYgKCFwb3NzaWJsZUxhYmVscykge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICAnbm8gcG9zc2libGUgbGFiZWxzIHBhc3NlZCBpbnNpZGUgZmluZEJlc3RNYXRjaENhdGVnb3J5MidcbiAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc3QgeyBzdW1tYXJ5LCBub3RlcyB9ID0gZXZlbnQ7XG4gICAgY29uc3Qgc2VudGVuY2UgPSBgJHtzdW1tYXJ5fSR7bm90ZXMgPyBgOiAke25vdGVzfWAgOiAnJ31gO1xuXG4gICAgY29uc3QgcmVzOiBDbGFzc2lmaWNhdGlvblJlc3BvbnNlQm9keVR5cGUgPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGNsYXNzaWZpY2F0aW9uVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgIEF1dGhvcml6YXRpb246IGBCYXNpYyAke0J1ZmZlci5mcm9tKGBhZG1pbjoke2F1dGhBcGlUb2tlbn1gKS50b1N0cmluZygnYmFzZTY0Jyl9YCxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIHNlbnRlbmNlLFxuICAgICAgICAgIGxhYmVsczogcG9zc2libGVMYWJlbHMubWFwKChhKSA9PiBhPy5uYW1lKSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgcmVzLFxuICAgICAgZXZlbnQ/LmlkLFxuICAgICAgJyByZXMsIGV2ZW50Py5pZCBpbnNpZGUgZmluZEJlc3RNYXRjaENhdGVnb3J5MidcbiAgICApO1xuICAgIHJldHVybiByZXM7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBmaW5kIGNhdGVnb3JpZXMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHByb2Nlc3NCZXN0TWF0Y2hDYXRlZ29yaWVzID0gKFxuICBib2R5OiBDbGFzc2lmaWNhdGlvblJlc3BvbnNlQm9keVR5cGUsXG4gIG5ld1Bvc3NpYmxlTGFiZWxzOiBzdHJpbmdbXVxuKSA9PiB7XG4gIGNvbnN0IHsgc2NvcmVzIH0gPSBib2R5O1xuICBsZXQgYmVzdE1hdGNoQ2F0ZWdvcnkgPSAnJztcbiAgbGV0IGJlc3RNYXRjaFNjb3JlID0gMDtcbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBuZXdQb3NzaWJsZUxhYmVscy5sZW5ndGg7IGkrKykge1xuICAgIGNvbnN0IGxhYmVsID0gbmV3UG9zc2libGVMYWJlbHNbaV07XG4gICAgY29uc3Qgc2NvcmUgPSBzY29yZXNbaV07XG4gICAgaWYgKHNjb3JlID4gbWluVGhyZXNob2xkU2NvcmUpIHtcbiAgICAgIGlmIChzY29yZSA+IGJlc3RNYXRjaFNjb3JlKSB7XG4gICAgICAgIGJlc3RNYXRjaENhdGVnb3J5ID0gbGFiZWw7XG4gICAgICAgIGJlc3RNYXRjaFNjb3JlID0gc2NvcmU7XG4gICAgICB9XG4gICAgfVxuICB9XG5cbiAgcmV0dXJuIGJlc3RNYXRjaENhdGVnb3J5O1xufTtcblxuY29uc3QgYWRkVG9CZXN0TWF0Y2hDYXRlZ29yaWVzID0gKFxuICBuZXdFdmVudDogRXZlbnRQbHVzVHlwZSxcbiAgbmV3UG9zc2libGVMYWJlbHM6IHN0cmluZ1tdLFxuICBzY29yZXM6IG51bWJlcltdLFxuICBjYXRlZ29yaWVzOiBDYXRlZ29yeVR5cGVbXVxuKTogQ2F0ZWdvcnlUeXBlW10gfCBbXSA9PiB7XG4gIGNvbnN0IGJlc3RNYXRjaENhdGVnb3JpZXMgPSBbXTtcblxuICAvLyAgaWYgbWVldGluZyAgY2F0ZWdvcmllcyBtZWV0IHRocmVzaG9sZCBhZGQgdG8gcmVzdWx0c1xuICBjb25zdCBtZWV0aW5nSW5kZXggPSBuZXdQb3NzaWJsZUxhYmVscy5pbmRleE9mKG1lZXRpbmdMYWJlbCk7XG4gIGNvbnN0IGV4dGVybmFsTWVldGluZ0luZGV4ID0gbmV3UG9zc2libGVMYWJlbHMuaW5kZXhPZihleHRlcm5hbE1lZXRpbmdMYWJlbCk7XG5cbiAgaWYgKG1lZXRpbmdJbmRleCA+IC0xICYmIHNjb3Jlc1ttZWV0aW5nSW5kZXhdID4gbWluVGhyZXNob2xkU2NvcmUpIHtcbiAgICBiZXN0TWF0Y2hDYXRlZ29yaWVzLnB1c2goXG4gICAgICBjYXRlZ29yaWVzLmZpbmQoKGNhdGVnb3J5KSA9PiBjYXRlZ29yeS5uYW1lID09PSBtZWV0aW5nTGFiZWwpXG4gICAgKTtcbiAgfVxuXG4gIGlmIChcbiAgICBleHRlcm5hbE1lZXRpbmdJbmRleCA+IC0xICYmXG4gICAgc2NvcmVzW2V4dGVybmFsTWVldGluZ0luZGV4XSA+IG1pblRocmVzaG9sZFNjb3JlXG4gICkge1xuICAgIGJlc3RNYXRjaENhdGVnb3JpZXMucHVzaChcbiAgICAgIGNhdGVnb3JpZXMuZmluZCgoY2F0ZWdvcnkpID0+IGNhdGVnb3J5Lm5hbWUgPT09IGV4dGVybmFsTWVldGluZ0xhYmVsKVxuICAgICk7XG4gIH1cblxuICAvLyBpZiBldmVudCBpcyBjbGFzc2lmaWVkIGFzIG1lZXRpbmcgdHlwZSBvciBleHRlcm5hbCB0eXBlIHRoZW4gYWxzbyBjb3B5IG92ZXJcbiAgaWYgKG5ld0V2ZW50LmlzTWVldGluZyAmJiBtZWV0aW5nSW5kZXggPiAtMSkge1xuICAgIGJlc3RNYXRjaENhdGVnb3JpZXMucHVzaChcbiAgICAgIGNhdGVnb3JpZXMuZmluZCgoY2F0ZWdvcnkpID0+IGNhdGVnb3J5Lm5hbWUgPT09IG1lZXRpbmdMYWJlbClcbiAgICApO1xuICB9XG5cbiAgaWYgKG5ld0V2ZW50LmlzRXh0ZXJuYWxNZWV0aW5nICYmIGV4dGVybmFsTWVldGluZ0luZGV4ID4gLTEpIHtcbiAgICBiZXN0TWF0Y2hDYXRlZ29yaWVzLnB1c2goXG4gICAgICBjYXRlZ29yaWVzLmZpbmQoKGNhdGVnb3J5KSA9PiBjYXRlZ29yeS5uYW1lID09PSBleHRlcm5hbE1lZXRpbmdMYWJlbClcbiAgICApO1xuICB9XG5cbiAgcmV0dXJuIGJlc3RNYXRjaENhdGVnb3JpZXM7XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0V2ZW50Rm9yTWVldGluZ1R5cGVDYXRlZ29yaWVzID0gKFxuICBuZXdFdmVudDogRXZlbnRQbHVzVHlwZSxcbiAgYmVzdE1hdGNoQ2F0ZWdvcnk6IENhdGVnb3J5VHlwZSxcbiAgbmV3UG9zc2libGVMYWJlbHM6IHN0cmluZ1tdLFxuICBzY29yZXM6IG51bWJlcltdLFxuICBjYXRlZ29yaWVzOiBDYXRlZ29yeVR5cGVbXVxuKTogQ2F0ZWdvcnlUeXBlW10gfCBbXSA9PiB7XG4gIC8vIGluY2x1ZGUgbWVldGluZyBhbmQgY29uZmVyZW5jZSB0eXBlcyBpZiBhbnlcblxuICBjb25zdCBiZXN0TWF0Y2hDYXRlZ29yaWVzID0gYWRkVG9CZXN0TWF0Y2hDYXRlZ29yaWVzKFxuICAgIG5ld0V2ZW50LFxuICAgIG5ld1Bvc3NpYmxlTGFiZWxzLFxuICAgIHNjb3JlcyxcbiAgICBjYXRlZ29yaWVzXG4gICk7XG5cbiAgaWYgKGJlc3RNYXRjaENhdGVnb3JpZXM/Lmxlbmd0aCA+IDApIHtcbiAgICByZXR1cm4gKGJlc3RNYXRjaENhdGVnb3JpZXMgYXMgQ2F0ZWdvcnlUeXBlW10pLmNvbmNhdChbYmVzdE1hdGNoQ2F0ZWdvcnldKTtcbiAgfVxuXG4gIHJldHVybiBbYmVzdE1hdGNoQ2F0ZWdvcnldO1xufTtcblxuZXhwb3J0IGNvbnN0IGdldFVuaXF1ZUxhYmVscyA9IChsYWJlbHM6IENhdGVnb3J5VHlwZVtdKSA9PiB7XG4gIGNvbnN0IHVuaXF1ZUxhYmVscyA9IF8udW5pcUJ5KGxhYmVscywgJ2lkJyk7XG4gIHJldHVybiB1bmlxdWVMYWJlbHM7XG59O1xuXG5leHBvcnQgY29uc3QgY29weU92ZXJDYXRlZ29yeURlZmF1bHRzID0gKFxuICBldmVudDogRXZlbnRQbHVzVHlwZSxcbiAgY2F0ZWdvcnk6IENhdGVnb3J5VHlwZVxuKTogRXZlbnRQbHVzVHlwZSA9PiB7XG4gIHJldHVybiB7XG4gICAgLi4uZXZlbnQsXG4gICAgdHJhbnNwYXJlbmN5OiAhZXZlbnQ/LnVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eVxuICAgICAgPyBjYXRlZ29yeT8uZGVmYXVsdEF2YWlsYWJpbGl0eVxuICAgICAgICA/ICd0cmFuc3BhcmVudCdcbiAgICAgICAgOiAnb3BhcXVlJ1xuICAgICAgOiBldmVudC50cmFuc3BhcmVuY3ksXG4gICAgLy8gcHJlZmVycmVkRGF5T2ZXZWVrOiAhZXZlbnQ/LnVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlID8gKGNhdGVnb3J5Py5kZWZhdWx0VGltZVByZWZlcmVuY2U/LnByZWZlcnJlZERheU9mV2VlaykgOiBldmVudC5wcmVmZXJyZWREYXlPZldlZWssXG4gICAgLy8gcHJlZmVycmVkVGltZTogIWV2ZW50Py51c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZSA/IChjYXRlZ29yeT8uZGVmYXVsdFRpbWVQcmVmZXJlbmNlPy5wcmVmZXJyZWRUaW1lKSA6IGV2ZW50LnByZWZlcnJlZFRpbWUsXG4gICAgLy8gcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U6ICFldmVudD8udXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2UgPyAoY2F0ZWdvcnk/LmRlZmF1bHRUaW1lUHJlZmVyZW5jZT8ucHJlZmVycmVkU3RhcnRUaW1lUmFuZ2UpIDogZXZlbnQucHJlZmVycmVkU3RhcnRUaW1lUmFuZ2UsXG4gICAgLy8gcHJlZmVycmVkRW5kVGltZVJhbmdlOiAhZXZlbnQ/LnVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlID8gKGNhdGVnb3J5Py5kZWZhdWx0VGltZVByZWZlcmVuY2U/LnByZWZlcnJlZEVuZFRpbWVSYW5nZSkgOiBldmVudC5wcmVmZXJyZWRFbmRUaW1lUmFuZ2UsXG4gICAgcHJpb3JpdHk6XG4gICAgICAoIWV2ZW50Py51c2VyTW9kaWZpZWRQcmlvcml0eUxldmVsXG4gICAgICAgID8gY2F0ZWdvcnk/LmRlZmF1bHRQcmlvcml0eUxldmVsXG4gICAgICAgIDogZXZlbnQ/LnByaW9yaXR5KSB8fCAxLFxuICAgIG1vZGlmaWFibGU6ICFldmVudD8udXNlck1vZGlmaWVkTW9kaWZpYWJsZVxuICAgICAgPyBjYXRlZ29yeT8uZGVmYXVsdE1vZGlmaWFibGVcbiAgICAgIDogZXZlbnQubW9kaWZpYWJsZSxcbiAgICBpc0JyZWFrOiAhZXZlbnQ/LnVzZXJNb2RpZmllZElzQnJlYWtcbiAgICAgID8gY2F0ZWdvcnk/LmRlZmF1bHRJc0JyZWFrXG4gICAgICA6IGV2ZW50LmlzQnJlYWssXG4gICAgaXNNZWV0aW5nOiAhZXZlbnQ/LnVzZXJNb2RpZmllZElzTWVldGluZ1xuICAgICAgPyBjYXRlZ29yeT8uZGVmYXVsdElzTWVldGluZ1xuICAgICAgOiBjYXRlZ29yeT8ubmFtZSA9PT0gbWVldGluZ0xhYmVsXG4gICAgICAgID8gdHJ1ZVxuICAgICAgICA6IGV2ZW50LmlzTWVldGluZyxcbiAgICBpc0V4dGVybmFsTWVldGluZzogIWV2ZW50Py51c2VyTW9kaWZpZWRJc0V4dGVybmFsTWVldGluZ1xuICAgICAgPyBjYXRlZ29yeT8uZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICA6IGNhdGVnb3J5Py5uYW1lID09PSBleHRlcm5hbE1lZXRpbmdMYWJlbFxuICAgICAgICA/IHRydWVcbiAgICAgICAgOiBldmVudC5pc0V4dGVybmFsTWVldGluZyxcbiAgICBpc01lZXRpbmdNb2RpZmlhYmxlOiAhZXZlbnQ/LnVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgID8gY2F0ZWdvcnk/LmRlZmF1bHRNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgOiBldmVudC5pc01lZXRpbmdNb2RpZmlhYmxlLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZTogIWV2ZW50Py51c2VyTW9kaWZpZWRNb2RpZmlhYmxlXG4gICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgOiBldmVudC5pc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGUsXG4gICAgYmFja2dyb3VuZENvbG9yOiAhZXZlbnQ/LnVzZXJNb2RpZmllZENvbG9yXG4gICAgICA/IGNhdGVnb3J5Py5jb2xvclxuICAgICAgOiBldmVudC5iYWNrZ3JvdW5kQ29sb3IsXG4gICAgcHJlZmVycmVkVGltZVJhbmdlczpcbiAgICAgICFldmVudD8udXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2UgJiZcbiAgICAgIGNhdGVnb3J5Py5kZWZhdWx0VGltZVByZWZlcmVuY2U/Lmxlbmd0aCA+IDBcbiAgICAgICAgPyBjYXRlZ29yeT8uZGVmYXVsdFRpbWVQcmVmZXJlbmNlPy5tYXAoKHRwKSA9PiAoe1xuICAgICAgICAgICAgLi4udHAsXG4gICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgZXZlbnRJZDogZXZlbnQ/LmlkLFxuICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgICAgdXNlcklkOiBldmVudD8udXNlcklkLFxuICAgICAgICAgIH0pKVxuICAgICAgICA6IGV2ZW50LnByZWZlcnJlZFRpbWVSYW5nZXMsXG4gIH07XG59O1xuXG5leHBvcnQgY29uc3QgY3JlYXRlUmVtaW5kZXJzQW5kVGltZUJsb2NraW5nRm9yQmVzdE1hdGNoQ2F0ZWdvcnkgPSBhc3luYyAoXG4gIGlkOiBzdHJpbmcsXG4gIHVzZXJJZDogc3RyaW5nLFxuICBuZXdFdmVudDogRXZlbnRQbHVzVHlwZSxcbiAgYmVzdE1hdGNoQ2F0ZWdvcnk6IENhdGVnb3J5VHlwZSxcbiAgbmV3UmVtaW5kZXJzMT86IFJlbWluZGVyVHlwZVtdLFxuICBuZXdUaW1lQmxvY2tpbmcxPzogQnVmZmVyVGltZU9iamVjdFR5cGUsXG4gIHByZXZpb3VzRXZlbnQ/OiBFdmVudFBsdXNUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICAvLyB2YWxpZGF0ZVxuICAgIGlmICghYmVzdE1hdGNoQ2F0ZWdvcnk/LmlkKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ2Jlc3RNYXRjaENhdGVnb3J5IGlzIHJlcXVpcmVkJyk7XG4gICAgfVxuICAgIGlmICghbmV3RXZlbnQ/LmlkKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ25ld0V2ZW50IGlzIHJlcXVpcmVkJyk7XG4gICAgfVxuXG4gICAgaWYgKCFpZCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdpZCBpcyByZXF1aXJlZCcpO1xuICAgIH1cblxuICAgIGlmICghdXNlcklkKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ3VzZXJJZCBpcyByZXF1aXJlZCcpO1xuICAgIH1cblxuICAgIGxldCBuZXdCdWZmZXJUaW1lcyA9IG5ld1RpbWVCbG9ja2luZzEgfHwge307XG4gICAgbGV0IG5ld1JlbWluZGVycyA9IG5ld1JlbWluZGVyczEgfHwgW107XG4gICAgLy8gY3JlYXRlIHJlbWluZGVyc1xuICAgIGNvbnN0IG9sZFJlbWluZGVycyA9IGF3YWl0IGxpc3RSZW1pbmRlcnNGb3JFdmVudChpZCwgdXNlcklkKTtcbiAgICBjb25zdCByZW1pbmRlcnMgPSBjcmVhdGVSZW1pbmRlcnNVc2luZ0NhdGVnb3J5RGVmYXVsdHNGb3JFdmVudChcbiAgICAgIG5ld0V2ZW50LFxuICAgICAgYmVzdE1hdGNoQ2F0ZWdvcnksXG4gICAgICBvbGRSZW1pbmRlcnMsXG4gICAgICBwcmV2aW91c0V2ZW50XG4gICAgKTtcbiAgICBjb25zb2xlLmxvZyhyZW1pbmRlcnMsICcgcmVtaW5kZXJzJyk7XG4gICAgaWYgKFxuICAgICAgcmVtaW5kZXJzPy5sZW5ndGggPiAwICYmXG4gICAgICBiZXN0TWF0Y2hDYXRlZ29yeT8uY29weVJlbWluZGVycyAmJlxuICAgICAgIW5ld0V2ZW50Py51c2VyTW9kaWZpZWRSZW1pbmRlcnNcbiAgICApIHtcbiAgICAgIG5ld1JlbWluZGVycy5wdXNoKC4uLnJlbWluZGVycyk7XG4gICAgfVxuXG4gICAgaWYgKFxuICAgICAgIW5ld0V2ZW50Py51c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmcgJiZcbiAgICAgIGJlc3RNYXRjaENhdGVnb3J5Py5jb3B5VGltZUJsb2NraW5nXG4gICAgKSB7XG4gICAgICAvLyBjcmVhdGUgdGltZSBibG9ja2luZ1xuICAgICAgY29uc3QgYnVmZmVyVGltZXMgPSBjcmVhdGVQcmVBbmRQb3N0RXZlbnRzRm9yQ2F0ZWdvcnlEZWZhdWx0cyhcbiAgICAgICAgYmVzdE1hdGNoQ2F0ZWdvcnksXG4gICAgICAgIG5ld0V2ZW50LFxuICAgICAgICBwcmV2aW91c0V2ZW50XG4gICAgICApO1xuICAgICAgY29uc29sZS5sb2coYnVmZmVyVGltZXMsICcgdGltZUJsb2NraW5nJyk7XG4gICAgICBpZiAoYnVmZmVyVGltZXM/LmJlZm9yZUV2ZW50KSB7XG4gICAgICAgIChuZXdCdWZmZXJUaW1lcyBhcyBCdWZmZXJUaW1lT2JqZWN0VHlwZSkuYmVmb3JlRXZlbnQgPVxuICAgICAgICAgIGJ1ZmZlclRpbWVzLmJlZm9yZUV2ZW50O1xuICAgICAgfVxuXG4gICAgICBpZiAoYnVmZmVyVGltZXM/LmFmdGVyRXZlbnQpIHtcbiAgICAgICAgKG5ld0J1ZmZlclRpbWVzIGFzIEJ1ZmZlclRpbWVPYmplY3RUeXBlKS5hZnRlckV2ZW50ID1cbiAgICAgICAgICBidWZmZXJUaW1lcy5hZnRlckV2ZW50O1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIGJ1ZmZlclRpbWVzPy5uZXdFdmVudD8ucHJlRXZlbnRJZCB8fFxuICAgICAgICBidWZmZXJUaW1lcz8ubmV3RXZlbnQ/LnBvc3RFdmVudElkXG4gICAgICApIHtcbiAgICAgICAgbmV3RXZlbnQgPSBidWZmZXJUaW1lcy5uZXdFdmVudDtcbiAgICAgIH1cbiAgICB9XG4gICAgcmV0dXJuIHsgbmV3RXZlbnQsIG5ld1JlbWluZGVycywgbmV3QnVmZmVyVGltZXM6IG5ld0J1ZmZlclRpbWVzIH07XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUsXG4gICAgICAnIHVuYWJsZSB0byBjcmVhdGUgcmVtaW5kZXJzIGFuZCB0aW1lIGJsb2NraW5nIGZvciBiZXN0IG1hdGNoIGNhdGVnb3J5J1xuICAgICk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVDYXRlZ29yeUV2ZW50cyA9IGFzeW5jIChcbiAgY2F0ZWdvcnlFdmVudHM6IENhdGVnb3J5RXZlbnRUeXBlW11cbikgPT4ge1xuICB0cnkge1xuICAgIGZvciAoY29uc3QgY2F0ZWdvcnlFdmVudCBvZiBjYXRlZ29yeUV2ZW50cykge1xuICAgICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgICBjYXRlZ29yeUlkOiBjYXRlZ29yeUV2ZW50Py5jYXRlZ29yeUlkLFxuICAgICAgICBldmVudElkOiBjYXRlZ29yeUV2ZW50Py5ldmVudElkLFxuICAgICAgfTtcbiAgICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnQ29ubmVjdGlvbkJ5Q2F0ZWdvcnlJZEFuZEV2ZW50SWQnO1xuICAgICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgIHF1ZXJ5IENvbm5lY3Rpb25CeUNhdGVnb3J5SWRBbmRFdmVudElkKCRjYXRlZ29yeUlkOiB1dWlkISwgJGV2ZW50SWQ6IFN0cmluZyEpIHtcbiAgICAgICAgICBDYXRlZ29yeV9FdmVudCh3aGVyZToge2NhdGVnb3J5SWQ6IHtfZXE6ICRjYXRlZ29yeUlkfSwgZXZlbnRJZDoge19lcTogJGV2ZW50SWR9fSkge1xuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGNhdGVnb3J5SWRcbiAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICAgIGlkXG4gICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICBgO1xuXG4gICAgICBjb25zdCByZXM6IHsgZGF0YTogeyBDYXRlZ29yeV9FdmVudDogQ2F0ZWdvcnlFdmVudFR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBqc29uOiB7XG4gICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgcXVlcnksXG4gICAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICAgLmpzb24oKTtcblxuICAgICAgaWYgKCFyZXM/LmRhdGE/LkNhdGVnb3J5X0V2ZW50Py5bMF0pIHtcbiAgICAgICAgY29uc3QgdmFyaWFibGVzMiA9IHtcbiAgICAgICAgICBpZDogY2F0ZWdvcnlFdmVudC5pZCxcbiAgICAgICAgICBjYXRlZ29yeUlkOiBjYXRlZ29yeUV2ZW50Py5jYXRlZ29yeUlkLFxuICAgICAgICAgIGV2ZW50SWQ6IGNhdGVnb3J5RXZlbnQ/LmV2ZW50SWQsXG4gICAgICAgICAgY3JlYXRlZERhdGU6IGNhdGVnb3J5RXZlbnQ/LmNyZWF0ZWREYXRlLFxuICAgICAgICAgIHVwZGF0ZWRBdDogY2F0ZWdvcnlFdmVudD8udXBkYXRlZEF0LFxuICAgICAgICAgIHVzZXJJZDogY2F0ZWdvcnlFdmVudD8udXNlcklkLFxuICAgICAgICB9O1xuICAgICAgICBjb25zdCBvcGVyYXRpb25OYW1lMiA9ICdJbnNlcnRDYXRlZ29yeV9FdmVudCc7XG4gICAgICAgIGNvbnN0IHF1ZXJ5MiA9IGBcbiAgICAgICAgICBtdXRhdGlvbiBJbnNlcnRDYXRlZ29yeV9FdmVudCgkaWQ6IHV1aWQhLCAkY2F0ZWdvcnlJZDogdXVpZCEsICRjcmVhdGVkRGF0ZTogdGltZXN0YW1wdHosICRldmVudElkOiBTdHJpbmchLCAkdXBkYXRlZEF0OiB0aW1lc3RhbXB0eiwgJHVzZXJJZDogdXVpZCEpIHtcbiAgICAgICAgICAgIGluc2VydF9DYXRlZ29yeV9FdmVudF9vbmUob2JqZWN0OiB7Y2F0ZWdvcnlJZDogJGNhdGVnb3J5SWQsIGNyZWF0ZWREYXRlOiAkY3JlYXRlZERhdGUsIGRlbGV0ZWQ6IGZhbHNlLCBldmVudElkOiAkZXZlbnRJZCwgaWQ6ICRpZCwgdXBkYXRlZEF0OiAkdXBkYXRlZEF0LCB1c2VySWQ6ICR1c2VySWR9KSB7XG4gICAgICAgICAgICAgIGNhdGVnb3J5SWRcbiAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgIGA7XG4gICAgICAgIGNvbnN0IHJlczIgPSBhd2FpdCBnb3RcbiAgICAgICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBqc29uOiB7XG4gICAgICAgICAgICAgIG9wZXJhdGlvbk5hbWU6IG9wZXJhdGlvbk5hbWUyLFxuICAgICAgICAgICAgICBxdWVyeTogcXVlcnkyLFxuICAgICAgICAgICAgICB2YXJpYWJsZXM6IHZhcmlhYmxlczIsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0pXG4gICAgICAgICAgLmpzb24oKTtcblxuICAgICAgICBjb25zb2xlLmxvZyhyZXMyLCAnIHJlc3BvbnNlIGFmdGVyIGluc2VydGluZyBjYXRlZ29yeSBldmVudCcpO1xuICAgICAgfVxuICAgIH1cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwc2VydCBjYXRlZ29yeSBldmVudHMnKTtcbiAgfVxufTtcblxuY29uc3QgY29weU92ZXJDYXRlZ29yeURlZmF1bHRzRm9yTWVldGluZ1R5cGUgPSAoXG4gIGV2ZW50LFxuICBjYXRlZ29yaWVzOiBDYXRlZ29yeVR5cGVbXVxuKSA9PiB7XG4gIGNvbnN0IG1lZXRpbmdDYXRlZ29yeSA9IGNhdGVnb3JpZXMuZmluZChcbiAgICAoY2F0ZWdvcnkpID0+IGNhdGVnb3J5Lm5hbWUgPT09IG1lZXRpbmdMYWJlbFxuICApO1xuICBjb25zdCBleHRlcm5hbENhdGVnb3J5ID0gY2F0ZWdvcmllcy5maW5kKFxuICAgIChjYXRlZ29yeSkgPT4gY2F0ZWdvcnkubmFtZSA9PT0gZXh0ZXJuYWxNZWV0aW5nTGFiZWxcbiAgKTtcblxuICBsZXQgbmV3RXZlbnRNZWV0aW5nID0gbnVsbDtcbiAgbGV0IG5ld0V2ZW50RXh0ZXJuYWwgPSBudWxsO1xuXG4gIGlmIChtZWV0aW5nQ2F0ZWdvcnk/LmlkKSB7XG4gICAgbmV3RXZlbnRNZWV0aW5nID0gY29weU92ZXJDYXRlZ29yeURlZmF1bHRzKGV2ZW50LCBtZWV0aW5nQ2F0ZWdvcnkpO1xuICB9XG5cbiAgaWYgKGV4dGVybmFsQ2F0ZWdvcnk/LmlkKSB7XG4gICAgbmV3RXZlbnRFeHRlcm5hbCA9IGNvcHlPdmVyQ2F0ZWdvcnlEZWZhdWx0cyhldmVudCwgZXh0ZXJuYWxDYXRlZ29yeSk7XG4gIH1cblxuICByZXR1cm4geyBuZXdFdmVudE1lZXRpbmcsIG5ld0V2ZW50RXh0ZXJuYWwgfTtcbn07XG5cbmV4cG9ydCBjb25zdCBsaXN0UmVtaW5kZXJzRm9yRXZlbnQgPSBhc3luYyAoXG4gIGV2ZW50SWQ6IHN0cmluZyxcbiAgdXNlcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIC8vIHZhbGlkYXRlXG4gICAgaWYgKCFldmVudElkKSB7XG4gICAgICBjb25zb2xlLmxvZyhldmVudElkLCAnIG5vIGV2ZW50SWQgcHJlc2VudCBpbnNpZGUgbGlzdFJlbWluZGVyc0ZvckV2ZW50Jyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgaWYgKCF1c2VySWQpIHtcbiAgICAgIGNvbnNvbGUubG9nKHVzZXJJZCwgJyBubyB1c2VySWQgcHJlc2VudCBpbnNpZGUgbGlzdFJlbWluZGVyc0ZvckV2ZW50Jyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuICAgIC8vIGdldCByZW1pbmRlcnNcbiAgICBjb25zb2xlLmxvZygnIGxpc3RSZW1pbmRlcnNGb3JFdmVudCBjYWxsZWQnKTtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2xpc3RSZW1pbmRlcnNGb3JFdmVudCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgcXVlcnkgbGlzdFJlbWluZGVyc0ZvckV2ZW50KCR1c2VySWQ6IHV1aWQhLCAkZXZlbnRJZDogU3RyaW5nISkge1xuICAgICAgUmVtaW5kZXIod2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9LCBldmVudElkOiB7X2VxOiAkZXZlbnRJZH0sIGRlbGV0ZWQ6IHtfbmVxOiB0cnVlfX0pIHtcbiAgICAgICAgZXZlbnRJZFxuICAgICAgICBpZFxuICAgICAgICBtaW51dGVzXG4gICAgICAgIHJlbWluZGVyRGF0ZVxuICAgICAgICB0aW1lem9uZVxuICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgdXNlRGVmYXVsdFxuICAgICAgICB1c2VySWRcbiAgICAgICAgZGVsZXRlZFxuICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgfVxuICAgIH1cbiAgYDtcbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBSZW1pbmRlcjogUmVtaW5kZXJUeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgIGV2ZW50SWQsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGxpc3RSZW1pbmRlcnNGb3JFdmVudCcpO1xuICAgIHJldHVybiByZXM/LmRhdGE/LlJlbWluZGVyO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyBsaXN0UmVtaW5kZXJzRm9yRXZlbnQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGNyZWF0ZVJlbWluZGVyc1VzaW5nQ2F0ZWdvcnlEZWZhdWx0c0ZvckV2ZW50ID0gKFxuICBldmVudDogRXZlbnRQbHVzVHlwZSxcbiAgYmVzdE1hdGNoQ2F0ZWdvcnk6IENhdGVnb3J5VHlwZSxcbiAgb2xkUmVtaW5kZXJzOiBSZW1pbmRlclR5cGVbXSxcbiAgcHJldmlvdXNFdmVudDogRXZlbnRQbHVzVHlwZVxuKTogUmVtaW5kZXJUeXBlW10gPT4ge1xuICAvLyB2YWxpZGF0ZSB0aW1lIGJsb2NraW5nXG4gIGlmIChldmVudC51c2VyTW9kaWZpZWRSZW1pbmRlcnMpIHtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIGlmIChwcmV2aW91c0V2ZW50Py5jb3B5UmVtaW5kZXJzKSB7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICBpZiAocHJldmlvdXNFdmVudD8uaWQgJiYgYmVzdE1hdGNoQ2F0ZWdvcnk/LmNvcHlSZW1pbmRlcnMpIHtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIGNvbnN0IHJlbWluZGVycyA9IGJlc3RNYXRjaENhdGVnb3J5Py5kZWZhdWx0UmVtaW5kZXJzO1xuICBpZiAoIShyZW1pbmRlcnM/Lmxlbmd0aCA+IDApKSB7XG4gICAgcmV0dXJuIG9sZFJlbWluZGVycztcbiAgfVxuXG4gIGNvbnN0IG5ld1JlbWluZGVycyA9IFtdO1xuICByZW1pbmRlcnMuZm9yRWFjaCgocmVtaW5kZXIpID0+IHtcbiAgICBuZXdSZW1pbmRlcnMucHVzaCh7XG4gICAgICBpZDogdXVpZCgpLFxuICAgICAgbWludXRlczogcmVtaW5kZXIsXG4gICAgICBldmVudElkOiBldmVudC5pZCxcbiAgICAgIHVzZXJJZDogZXZlbnQudXNlcklkLFxuICAgICAgLy8gZXZlbnQ6IGV2ZW50LFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgfSk7XG4gIH0pO1xuICByZXR1cm4gbmV3UmVtaW5kZXJzO1xufTtcblxuZXhwb3J0IGNvbnN0IGNyZWF0ZVByZUFuZFBvc3RFdmVudHNGb3JDYXRlZ29yeURlZmF1bHRzID0gKFxuICBiZXN0TWF0Y2hDYXRlZ29yeTogQ2F0ZWdvcnlUeXBlLFxuICBldmVudDogRXZlbnRQbHVzVHlwZSxcbiAgcHJldmlvdXNFdmVudD86IEV2ZW50UGx1c1R5cGVcbikgPT4ge1xuICAvLyAgdmFsaWRhdGUgdGltZSBibG9ja2luZ1xuICBpZiAocHJldmlvdXNFdmVudD8uY29weVRpbWVCbG9ja2luZykge1xuICAgIHJldHVybiBudWxsO1xuICB9XG5cbiAgaWYgKHByZXZpb3VzRXZlbnQ/LmlkICYmIGJlc3RNYXRjaENhdGVnb3J5Py5jb3B5VGltZUJsb2NraW5nKSB7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICAvLyB1c2VyIG1vZGlmaWVkIHRpbWUgYmxvY2tpbmcgZG8gbm90IG92ZXJyaWRlXG4gIGlmIChldmVudD8udXNlck1vZGlmaWVkVGltZUJsb2NraW5nKSB7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICBjb25zdCBldmVudElkID0gdXVpZCgpO1xuICBjb25zdCBldmVudElkMSA9IHV1aWQoKTtcbiAgY29uc3QgcHJlRXZlbnRJZCA9IGV2ZW50Py5wcmVFdmVudElkIHx8IGAke2V2ZW50SWR9IyR7ZXZlbnQ/LmNhbGVuZGFySWR9YDtcbiAgY29uc3QgcG9zdEV2ZW50SWQgPSBldmVudD8ucG9zdEV2ZW50SWQgfHwgYCR7ZXZlbnRJZDF9IyR7ZXZlbnQ/LmNhbGVuZGFySWR9YDtcblxuICBsZXQgdmFsdWVzVG9SZXR1cm46IGFueSA9IHt9O1xuICB2YWx1ZXNUb1JldHVybi5uZXdFdmVudCA9IGV2ZW50O1xuXG4gIGlmIChiZXN0TWF0Y2hDYXRlZ29yeT8uZGVmYXVsdFRpbWVCbG9ja2luZz8uYWZ0ZXJFdmVudCkge1xuICAgIC8vIGNvbnN0IGZvcm1hdHRlZFpvbmVBZnRlckV2ZW50RW5kRGF0ZSA9IGZvcm1hdEluVGltZVpvbmUoYWRkTWludXRlcyh6b25lZFRpbWVUb1V0YyhldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSwgZXZlbnQudGltZXpvbmUpLCBiZXN0TWF0Y2hDYXRlZ29yeS5kZWZhdWx0VGltZUJsb2NraW5nLmFmdGVyRXZlbnQpLnRvSVNPU3RyaW5nKCksIGV2ZW50LnRpbWV6b25lLCBcInl5eXktTU0tZGQnVCdISDptbTpzc1hYWFwiKVxuICAgIC8vIGNvbnN0IGZvcm1hdHRlZFpvbmVBZnRlckV2ZW50U3RhcnREYXRlID0gZm9ybWF0SW5UaW1lWm9uZSh6b25lZFRpbWVUb1V0YyhldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSwgZXZlbnQudGltZXpvbmUpLnRvSVNPU3RyaW5nKCksIGV2ZW50LnRpbWV6b25lLCBcInl5eXktTU0tZGQnVCdISDptbTpzc1hYWFwiKVxuXG4gICAgY29uc3QgZm9ybWF0dGVkWm9uZUFmdGVyRXZlbnRFbmREYXRlID0gZGF5anMoZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQ/LnRpbWV6b25lLCB0cnVlKVxuICAgICAgLmFkZChiZXN0TWF0Y2hDYXRlZ29yeS5kZWZhdWx0VGltZUJsb2NraW5nLmFmdGVyRXZlbnQsICdtJylcbiAgICAgIC5mb3JtYXQoKTtcbiAgICBjb25zdCBmb3JtYXR0ZWRab25lQWZ0ZXJFdmVudFN0YXJ0RGF0ZSA9IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGV2ZW50Py50aW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5mb3JtYXQoKTtcblxuICAgIGNvbnN0IGFmdGVyRXZlbnQ6IEV2ZW50UGx1c1R5cGUgPSB7XG4gICAgICBpZDogcG9zdEV2ZW50SWQsXG4gICAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICAgIGZvckV2ZW50SWQ6IGV2ZW50LmlkLFxuICAgICAgaXNQb3N0RXZlbnQ6IHRydWUsXG4gICAgICBub3RlczogJ0J1ZmZlciB0aW1lJyxcbiAgICAgIHN1bW1hcnk6ICdCdWZmZXIgdGltZScsXG4gICAgICBzdGFydERhdGU6IGZvcm1hdHRlZFpvbmVBZnRlckV2ZW50U3RhcnREYXRlLFxuICAgICAgZW5kRGF0ZTogZm9ybWF0dGVkWm9uZUFmdGVyRXZlbnRFbmREYXRlLFxuICAgICAgbWV0aG9kOiBldmVudD8ucG9zdEV2ZW50SWQgPyAndXBkYXRlJyA6ICdjcmVhdGUnLFxuICAgICAgdXNlcklkOiBldmVudD8udXNlcklkLFxuICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgcHJpb3JpdHk6IDEsXG4gICAgICBpc0ZvbGxvd1VwOiBmYWxzZSxcbiAgICAgIG1vZGlmaWFibGU6IHRydWUsXG4gICAgICBhbnlvbmVDYW5BZGRTZWxmOiBmYWxzZSxcbiAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyczogZmFsc2UsXG4gICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0czogZmFsc2UsXG4gICAgICBvcmlnaW5hbFN0YXJ0RGF0ZTogdW5kZWZpbmVkLFxuICAgICAgb3JpZ2luYWxBbGxEYXk6IGZhbHNlLFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICBjYWxlbmRhcklkOiBldmVudD8uY2FsZW5kYXJJZCxcbiAgICAgIHRpbWV6b25lOiBldmVudD8udGltZXpvbmUsXG4gICAgICBldmVudElkOiBwb3N0RXZlbnRJZC5zcGxpdCgnIycpWzBdLFxuICAgIH07XG4gICAgdmFsdWVzVG9SZXR1cm4uYWZ0ZXJFdmVudCA9IGFmdGVyRXZlbnQ7XG4gICAgdmFsdWVzVG9SZXR1cm4ubmV3RXZlbnQgPSB7XG4gICAgICAuLi52YWx1ZXNUb1JldHVybi5uZXdFdmVudCxcbiAgICAgIHBvc3RFdmVudElkLFxuICAgICAgdGltZUJsb2NraW5nOiB7XG4gICAgICAgIC4uLnZhbHVlc1RvUmV0dXJuPy5uZXdFdmVudD8udGltZUJsb2NraW5nLFxuICAgICAgICBhZnRlckV2ZW50OiBiZXN0TWF0Y2hDYXRlZ29yeS5kZWZhdWx0VGltZUJsb2NraW5nLmFmdGVyRXZlbnQsXG4gICAgICB9LFxuICAgIH07XG4gIH1cblxuICBpZiAoYmVzdE1hdGNoQ2F0ZWdvcnk/LmRlZmF1bHRUaW1lQmxvY2tpbmc/LmJlZm9yZUV2ZW50KSB7XG4gICAgLy8gY29uc3QgZm9ybWF0dGVkWm9uZUJlZm9yZUV2ZW50U3RhcnREYXRlID0gZm9ybWF0SW5UaW1lWm9uZShzdWJNaW51dGVzKHpvbmVkVGltZVRvVXRjKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSksIGV2ZW50LnRpbWV6b25lKSwgYmVzdE1hdGNoQ2F0ZWdvcnkuZGVmYXVsdFRpbWVCbG9ja2luZy5iZWZvcmVFdmVudCkudG9JU09TdHJpbmcoKSwgZXZlbnQudGltZXpvbmUsIFwieXl5eS1NTS1kZCdUJ0hIOm1tOnNzWFhYXCIpXG4gICAgLy8gY29uc3QgZm9ybWF0dGVkWm9uZUJlZm9yZUV2ZW50RW5kRGF0ZSA9IGZvcm1hdEluVGltZVpvbmUoem9uZWRUaW1lVG9VdGMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSwgZXZlbnQudGltZXpvbmUpLnRvSVNPU3RyaW5nKCksIGV2ZW50LnRpbWV6b25lLCBcInl5eXktTU0tZGQnVCdISDptbTpzc1hYWFwiKVxuXG4gICAgY29uc3QgZm9ybWF0dGVkWm9uZUJlZm9yZUV2ZW50U3RhcnREYXRlID0gZGF5anMoXG4gICAgICBldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpXG4gICAgKVxuICAgICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgLnN1YnRyYWN0KGJlc3RNYXRjaENhdGVnb3J5LmRlZmF1bHRUaW1lQmxvY2tpbmcuYmVmb3JlRXZlbnQsICdtJylcbiAgICAgIC5mb3JtYXQoKTtcbiAgICBjb25zdCBmb3JtYXR0ZWRab25lQmVmb3JlRXZlbnRFbmREYXRlID0gZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5mb3JtYXQoKTtcblxuICAgIGNvbnN0IGJlZm9yZUV2ZW50OiBFdmVudFBsdXNUeXBlID0ge1xuICAgICAgaWQ6IHByZUV2ZW50SWQsXG4gICAgICBpc1ByZUV2ZW50OiB0cnVlLFxuICAgICAgaXNQb3N0RXZlbnQ6IGZhbHNlLFxuICAgICAgZm9yRXZlbnRJZDogZXZlbnQuaWQsXG4gICAgICBub3RlczogJ0J1ZmZlciB0aW1lJyxcbiAgICAgIHN1bW1hcnk6ICdCdWZmZXIgdGltZScsXG4gICAgICBzdGFydERhdGU6IGZvcm1hdHRlZFpvbmVCZWZvcmVFdmVudFN0YXJ0RGF0ZSxcbiAgICAgIGVuZERhdGU6IGZvcm1hdHRlZFpvbmVCZWZvcmVFdmVudEVuZERhdGUsXG4gICAgICBtZXRob2Q6IGV2ZW50Py5wcmVFdmVudElkID8gJ3VwZGF0ZScgOiAnY3JlYXRlJyxcbiAgICAgIHVzZXJJZDogZXZlbnQ/LnVzZXJJZCxcbiAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgIHByaW9yaXR5OiAxLFxuICAgICAgaXNGb2xsb3dVcDogZmFsc2UsXG4gICAgICBtb2RpZmlhYmxlOiB0cnVlLFxuICAgICAgYW55b25lQ2FuQWRkU2VsZjogZmFsc2UsXG4gICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnM6IGZhbHNlLFxuICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM6IGZhbHNlLFxuICAgICAgb3JpZ2luYWxTdGFydERhdGU6IHVuZGVmaW5lZCxcbiAgICAgIG9yaWdpbmFsQWxsRGF5OiBmYWxzZSxcbiAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgY2FsZW5kYXJJZDogZXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgICB0aW1lem9uZTogZXZlbnQ/LnRpbWV6b25lLFxuICAgICAgZXZlbnRJZDogcHJlRXZlbnRJZC5zcGxpdCgnIycpWzBdLFxuICAgIH07XG4gICAgdmFsdWVzVG9SZXR1cm4uYmVmb3JlRXZlbnQgPSBiZWZvcmVFdmVudDtcbiAgICB2YWx1ZXNUb1JldHVybi5uZXdFdmVudCA9IHtcbiAgICAgIC4uLnZhbHVlc1RvUmV0dXJuLm5ld0V2ZW50LFxuICAgICAgcHJlRXZlbnRJZCxcbiAgICAgIHRpbWVCbG9ja2luZzoge1xuICAgICAgICAuLi52YWx1ZXNUb1JldHVybj8ubmV3RXZlbnQ/LnRpbWVCbG9ja2luZyxcbiAgICAgICAgYmVmb3JlRXZlbnQ6IGJlc3RNYXRjaENhdGVnb3J5LmRlZmF1bHRUaW1lQmxvY2tpbmcuYmVmb3JlRXZlbnQsXG4gICAgICB9LFxuICAgIH07XG4gIH1cblxuICByZXR1cm4gdmFsdWVzVG9SZXR1cm47XG59O1xuXG5leHBvcnQgY29uc3QgdXBkYXRlVmFsdWVzRm9yTWVldGluZ1R5cGVDYXRlZ29yaWVzID0gYXN5bmMgKFxuICBldmVudCxcbiAgbmV3RXZlbnQxOiBFdmVudFBsdXNUeXBlLFxuICBiZXN0TWF0Y2hDYXRlZ29yaWVzOiBDYXRlZ29yeVR5cGVbXSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIG5ld1JlbWluZGVyczE/OiBSZW1pbmRlclR5cGVbXSxcbiAgbmV3VGltZUJsb2NraW5nMT86IHtcbiAgICBiZWZvcmVFdmVudD86IEV2ZW50UGx1c1R5cGU7XG4gICAgYWZ0ZXJFdmVudD86IEV2ZW50UGx1c1R5cGU7XG4gIH0sXG4gIHByZXZpb3VzRXZlbnQ/OiBFdmVudFBsdXNUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBpZiAoIShiZXN0TWF0Y2hDYXRlZ29yaWVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICAnYmVzdE1hdGNoQ2F0ZWdvcmllcyBjYW5ub3QgYmUgZW1wdHkgaW5zaWRlIHVwZGF0ZVZhbHVlc0Zvck1lZXRpbmdUeXBlQ2F0ZWdvcmllcyAnXG4gICAgICApO1xuICAgIH1cbiAgICBsZXQgbmV3RXZlbnQgPSBuZXdFdmVudDE7XG4gICAgbGV0IG5ld1JlbWluZGVycyA9IG5ld1JlbWluZGVyczEgfHwgW107XG4gICAgbGV0IG5ld0J1ZmZlclRpbWUgPSBuZXdUaW1lQmxvY2tpbmcxIHx8IHt9O1xuICAgIGNvbnN0IG5ld0NhdGVnb3J5Q29uc3RhbnRFdmVudHMgPSBjb3B5T3ZlckNhdGVnb3J5RGVmYXVsdHNGb3JNZWV0aW5nVHlwZShcbiAgICAgIGV2ZW50LFxuICAgICAgYmVzdE1hdGNoQ2F0ZWdvcmllc1xuICAgICk7XG4gICAgY29uc29sZS5sb2cobmV3Q2F0ZWdvcnlDb25zdGFudEV2ZW50cywgJyBuZXdDYXRlZ29yeUNvbnN0YW50RXZlbnRzJyk7XG5cbiAgICBpZiAobmV3Q2F0ZWdvcnlDb25zdGFudEV2ZW50cz8ubmV3RXZlbnRNZWV0aW5nPy5pZCkge1xuICAgICAgbmV3RXZlbnQgPSB7IC4uLm5ld0V2ZW50LCAuLi5uZXdDYXRlZ29yeUNvbnN0YW50RXZlbnRzLm5ld0V2ZW50TWVldGluZyB9O1xuICAgICAgY29uc3QgbWVldGluZ0NhdGVnb3J5ID0gYmVzdE1hdGNoQ2F0ZWdvcmllcy5maW5kKFxuICAgICAgICAoY2F0ZWdvcnkpID0+IGNhdGVnb3J5Lm5hbWUgPT09IG1lZXRpbmdMYWJlbFxuICAgICAgKTtcblxuICAgICAgLy8gY3JlYXRlIHJlbWluZGVyc1xuICAgICAgY29uc3Qgb2xkUmVtaW5kZXJzID0gYXdhaXQgbGlzdFJlbWluZGVyc0ZvckV2ZW50KFxuICAgICAgICBuZXdDYXRlZ29yeUNvbnN0YW50RXZlbnRzLm5ld0V2ZW50TWVldGluZy5pZCxcbiAgICAgICAgdXNlcklkXG4gICAgICApO1xuICAgICAgY29uc3QgcmVtaW5kZXJzID0gY3JlYXRlUmVtaW5kZXJzVXNpbmdDYXRlZ29yeURlZmF1bHRzRm9yRXZlbnQoXG4gICAgICAgIG5ld0V2ZW50LFxuICAgICAgICBtZWV0aW5nQ2F0ZWdvcnksXG4gICAgICAgIG9sZFJlbWluZGVycyxcbiAgICAgICAgcHJldmlvdXNFdmVudFxuICAgICAgKTtcbiAgICAgIGNvbnNvbGUubG9nKHJlbWluZGVycywgJyByZW1pbmRlcnMnKTtcbiAgICAgIGlmIChyZW1pbmRlcnM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgbmV3UmVtaW5kZXJzLnB1c2goLi4ucmVtaW5kZXJzKTtcbiAgICAgICAgbmV3UmVtaW5kZXJzID0gXy51bmlxQnkobmV3UmVtaW5kZXJzLCAnbWludXRlcycpO1xuICAgICAgfVxuXG4gICAgICAvLyBjcmVhdGUgdGltZSBibG9ja2luZ1xuICAgICAgY29uc3QgYnVmZmVyVGltZSA9IGNyZWF0ZVByZUFuZFBvc3RFdmVudHNGb3JDYXRlZ29yeURlZmF1bHRzKFxuICAgICAgICBtZWV0aW5nQ2F0ZWdvcnksXG4gICAgICAgIG5ld0V2ZW50LFxuICAgICAgICBwcmV2aW91c0V2ZW50XG4gICAgICApO1xuICAgICAgY29uc29sZS5sb2coYnVmZmVyVGltZSwgJyB0aW1lQmxvY2tpbmcnKTtcbiAgICAgIGlmIChidWZmZXJUaW1lPy5iZWZvcmVFdmVudCkge1xuICAgICAgICBuZXdCdWZmZXJUaW1lLmJlZm9yZUV2ZW50ID0gYnVmZmVyVGltZS5iZWZvcmVFdmVudDtcbiAgICAgIH1cblxuICAgICAgaWYgKGJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQpIHtcbiAgICAgICAgbmV3QnVmZmVyVGltZS5hZnRlckV2ZW50ID0gYnVmZmVyVGltZS5hZnRlckV2ZW50O1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIGJ1ZmZlclRpbWU/Lm5ld0V2ZW50Py5wcmVFdmVudElkIHx8XG4gICAgICAgIGJ1ZmZlclRpbWU/Lm5ld0V2ZW50Py5wb3N0RXZlbnRJZFxuICAgICAgKSB7XG4gICAgICAgIG5ld0V2ZW50ID0gYnVmZmVyVGltZS5uZXdFdmVudDtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAobmV3Q2F0ZWdvcnlDb25zdGFudEV2ZW50cz8ubmV3RXZlbnRFeHRlcm5hbD8uaWQpIHtcbiAgICAgIG5ld0V2ZW50ID0geyAuLi5uZXdFdmVudCwgLi4ubmV3Q2F0ZWdvcnlDb25zdGFudEV2ZW50cy5uZXdFdmVudEV4dGVybmFsIH07XG4gICAgICBjb25zdCBleHRlcm5hbENhdGVnb3J5ID0gYmVzdE1hdGNoQ2F0ZWdvcmllcy5maW5kKFxuICAgICAgICAoY2F0ZWdvcnkpID0+IGNhdGVnb3J5Lm5hbWUgPT09IGV4dGVybmFsTWVldGluZ0xhYmVsXG4gICAgICApO1xuXG4gICAgICAvLyBjcmVhdGUgcmVtaW5kZXJzXG4gICAgICBjb25zdCBvbGRSZW1pbmRlcnMgPSBhd2FpdCBsaXN0UmVtaW5kZXJzRm9yRXZlbnQoXG4gICAgICAgIG5ld0NhdGVnb3J5Q29uc3RhbnRFdmVudHMubmV3RXZlbnRFeHRlcm5hbC5pZCxcbiAgICAgICAgdXNlcklkXG4gICAgICApO1xuICAgICAgY29uc3QgcmVtaW5kZXJzID0gY3JlYXRlUmVtaW5kZXJzVXNpbmdDYXRlZ29yeURlZmF1bHRzRm9yRXZlbnQoXG4gICAgICAgIG5ld0V2ZW50LFxuICAgICAgICBleHRlcm5hbENhdGVnb3J5LFxuICAgICAgICBvbGRSZW1pbmRlcnMsXG4gICAgICAgIHByZXZpb3VzRXZlbnRcbiAgICAgICk7XG4gICAgICBjb25zb2xlLmxvZyhyZW1pbmRlcnMsICcgcmVtaW5kZXJzJyk7XG4gICAgICBpZiAocmVtaW5kZXJzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIG5ld1JlbWluZGVycy5wdXNoKC4uLnJlbWluZGVycyk7XG4gICAgICAgIG5ld1JlbWluZGVycyA9IF8udW5pcUJ5KG5ld1JlbWluZGVycywgJ21pbnV0ZXMnKTtcbiAgICAgIH1cblxuICAgICAgLy8gY3JlYXRlIHRpbWUgYmxvY2tpbmdcbiAgICAgIGNvbnN0IHRpbWVCbG9ja2luZyA9IGNyZWF0ZVByZUFuZFBvc3RFdmVudHNGb3JDYXRlZ29yeURlZmF1bHRzKFxuICAgICAgICBleHRlcm5hbENhdGVnb3J5LFxuICAgICAgICBuZXdFdmVudCxcbiAgICAgICAgcHJldmlvdXNFdmVudFxuICAgICAgKTtcbiAgICAgIGNvbnNvbGUubG9nKHRpbWVCbG9ja2luZywgJyB0aW1lQmxvY2tpbmcnKTtcbiAgICAgIGlmICh0aW1lQmxvY2tpbmc/LmJlZm9yZUV2ZW50KSB7XG4gICAgICAgIG5ld0J1ZmZlclRpbWUuYmVmb3JlRXZlbnQgPSB0aW1lQmxvY2tpbmcuYmVmb3JlRXZlbnQ7XG4gICAgICB9XG5cbiAgICAgIGlmICh0aW1lQmxvY2tpbmc/LmFmdGVyRXZlbnQpIHtcbiAgICAgICAgbmV3QnVmZmVyVGltZS5hZnRlckV2ZW50ID0gdGltZUJsb2NraW5nLmFmdGVyRXZlbnQ7XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgdGltZUJsb2NraW5nPy5uZXdFdmVudD8ucHJlRXZlbnRJZCB8fFxuICAgICAgICB0aW1lQmxvY2tpbmc/Lm5ld0V2ZW50Py5wb3N0RXZlbnRJZFxuICAgICAgKSB7XG4gICAgICAgIG5ld0V2ZW50ID0gdGltZUJsb2NraW5nLm5ld0V2ZW50O1xuICAgICAgfVxuICAgIH1cbiAgICByZXR1cm4geyBuZXdFdmVudCwgbmV3UmVtaW5kZXJzLCBuZXdUaW1lQmxvY2tpbmc6IG5ld0J1ZmZlclRpbWUgfTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwZGF0ZSB2YWx1ZXMgZm9yIGRlZmF1bHQgY2F0ZWdvcmllcycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHMgPSBhc3luYyAoXG4gIGV2ZW50OiBFdmVudFBsdXNUeXBlLFxuICB2ZWN0b3I6IG51bWJlcltdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGlkLCB1c2VySWQgfSA9IGV2ZW50O1xuICAgIGNvbnNvbGUubG9nKGlkLCAnIGlkIGluc2lkZSBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0cycpO1xuICAgIC8vICBjcmVhdGUgbmV3IGV2ZW50IGRhdGF0eXBlIGluIGVsYXN0aWMgc2VhcmNoXG4gICAgLy8gYXdhaXQgcHV0RGF0YUluU2VhcmNoKGlkLCB2ZWN0b3IsIHVzZXJJZClcblxuICAgIC8vIGZpbmQgY2F0ZWdvcmllcyBhbmQgY29weSBvdmVyIGRlZmF1bHRzIGlmIGFueVxuICAgIGNvbnN0IGNhdGVnb3JpZXM6IENhdGVnb3J5VHlwZVtdID0gYXdhaXQgZ2V0VXNlckNhdGVnb3JpZXModXNlcklkKTtcblxuICAgIGlmICghY2F0ZWdvcmllcz8uWzBdPy5pZCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICAnY2F0ZWdvcmllcyBpcyBub3QgYXZhaWxhYmxlIHByb2Nlc3NVc2VyRXZlbnRGb3JDYXRlZ29yeURlZmF1bHRzJ1xuICAgICAgKTtcbiAgICB9XG5cbiAgICAvLyBsYWJlbENvbnN0YW50cyBhcmUgYWxyZWFkeSBwYXJ0IG9mIGNhdGVnb3JpZXNcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGNhdGVnb3JpZXMsXG4gICAgICBpZCxcbiAgICAgICcgY2F0ZWdvcmllcywgaWQgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHMnXG4gICAgKTtcbiAgICBjb25zdCBib2R5ID0gYXdhaXQgZmluZEJlc3RNYXRjaENhdGVnb3J5MihldmVudCwgY2F0ZWdvcmllcyk7XG4gICAgY29uc29sZS5sb2coYm9keSwgaWQsICcgYm9keSwgaWQgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHMnKTtcbiAgICBjb25zdCB7IGxhYmVscywgc2NvcmVzIH0gPSBib2R5O1xuXG4gICAgY29uc3QgYmVzdE1hdGNoTGFiZWwgPSBwcm9jZXNzQmVzdE1hdGNoQ2F0ZWdvcmllcyhib2R5LCBsYWJlbHMpO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYmVzdE1hdGNoTGFiZWwsXG4gICAgICBpZCxcbiAgICAgICcgYmVzdE1hdGNoTGFiZWwsIGlkIHByb2Nlc3NVc2VyRXZlbnRGb3JDYXRlZ29yeURlZmF1bHRzJ1xuICAgICk7XG5cbiAgICBpZiAoYmVzdE1hdGNoTGFiZWwpIHtcbiAgICAgIGNvbnN0IGJlc3RNYXRjaENhdGVnb3J5ID0gY2F0ZWdvcmllcy5maW5kKFxuICAgICAgICAoY2F0ZWdvcnkpID0+IGNhdGVnb3J5Lm5hbWUgPT09IGJlc3RNYXRjaExhYmVsXG4gICAgICApO1xuICAgICAgbGV0IGJlc3RNYXRjaFBsdXNNZWV0aW5nQ2F0ZWdvcmllcyA9XG4gICAgICAgIGF3YWl0IHByb2Nlc3NFdmVudEZvck1lZXRpbmdUeXBlQ2F0ZWdvcmllcyhcbiAgICAgICAgICBldmVudCxcbiAgICAgICAgICBiZXN0TWF0Y2hDYXRlZ29yeSxcbiAgICAgICAgICBsYWJlbHMsXG4gICAgICAgICAgc2NvcmVzLFxuICAgICAgICAgIGNhdGVnb3JpZXNcbiAgICAgICAgKTtcbiAgICAgIGlmIChiZXN0TWF0Y2hQbHVzTWVldGluZ0NhdGVnb3JpZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgYmVzdE1hdGNoUGx1c01lZXRpbmdDYXRlZ29yaWVzID0gZ2V0VW5pcXVlTGFiZWxzKFxuICAgICAgICAgIGJlc3RNYXRjaFBsdXNNZWV0aW5nQ2F0ZWdvcmllc1xuICAgICAgICApO1xuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBiZXN0TWF0Y2hQbHVzTWVldGluZ0NhdGVnb3JpZXMsXG4gICAgICAgICAgaWQsXG4gICAgICAgICAgJyBiZXN0TWF0Y2hBbmRNZWV0aW5nQ2F0ZWdvcmllcywgaWQgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHMnXG4gICAgICAgICk7XG4gICAgICB9XG4gICAgICAvLyAgY29weSBvdmVyIGNhdGVnb3J5IGRlZmF1bHRzXG4gICAgICBjb25zdCBuZXdDYXRlZ29yeURlZmF1bHRFdmVudCA9IGNvcHlPdmVyQ2F0ZWdvcnlEZWZhdWx0cyhcbiAgICAgICAgZXZlbnQsXG4gICAgICAgIGJlc3RNYXRjaENhdGVnb3J5XG4gICAgICApO1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIG5ld0NhdGVnb3J5RGVmYXVsdEV2ZW50LFxuICAgICAgICBpZCxcbiAgICAgICAgJyBuZXdDYXRlZ29yeURlZmF1bHRFdmVudCwgaWQgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHMnXG4gICAgICApO1xuXG4gICAgICAvLyBjcmVhdGUgbmV3IGV2ZW50XG4gICAgICBsZXQgbmV3RXZlbnQ6IEV2ZW50UGx1c1R5cGUgPSBuZXdDYXRlZ29yeURlZmF1bHRFdmVudCA/PyBldmVudDtcbiAgICAgIGNvbnNvbGUubG9nKG5ld0V2ZW50LCAnIG5ld0V2ZW50IHByb2Nlc3NVc2VyRXZlbnRGb3JDYXRlZ29yeURlZmF1bHRzJyk7XG4gICAgICBsZXQgbmV3UmVtaW5kZXJzOiBSZW1pbmRlclR5cGVbXSA9IFtdO1xuICAgICAgbGV0IG5ld1RpbWVCbG9ja2luZzogQnVmZmVyVGltZU9iamVjdFR5cGUgPSB7fTtcblxuICAgICAgY29uc3Qge1xuICAgICAgICBuZXdFdmVudDogbmV3RXZlbnQxLFxuICAgICAgICBuZXdSZW1pbmRlcnM6IG5ld1JlbWluZGVyczEsXG4gICAgICAgIG5ld0J1ZmZlclRpbWVzOiBuZXdUaW1lQmxvY2tpbmcxLFxuICAgICAgfSA9IGF3YWl0IGNyZWF0ZVJlbWluZGVyc0FuZFRpbWVCbG9ja2luZ0ZvckJlc3RNYXRjaENhdGVnb3J5KFxuICAgICAgICBpZCxcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBuZXdFdmVudCxcbiAgICAgICAgYmVzdE1hdGNoQ2F0ZWdvcnksXG4gICAgICAgIG5ld1JlbWluZGVycyxcbiAgICAgICAgbmV3VGltZUJsb2NraW5nXG4gICAgICApO1xuICAgICAgbmV3RXZlbnQgPSBuZXdFdmVudDE7XG4gICAgICBuZXdSZW1pbmRlcnMgPSBuZXdSZW1pbmRlcnMxO1xuICAgICAgbmV3VGltZUJsb2NraW5nID0gbmV3VGltZUJsb2NraW5nMTtcblxuICAgICAgaWYgKGJlc3RNYXRjaFBsdXNNZWV0aW5nQ2F0ZWdvcmllcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBjb25zdCBjYXRlZ29yeUV2ZW50czogQ2F0ZWdvcnlFdmVudFR5cGVbXSA9XG4gICAgICAgICAgYmVzdE1hdGNoUGx1c01lZXRpbmdDYXRlZ29yaWVzLm1hcCgoYykgPT4ge1xuICAgICAgICAgICAgY29uc3QgY2F0ZWdvcnlFdmVudDogQ2F0ZWdvcnlFdmVudFR5cGUgPSB7XG4gICAgICAgICAgICAgIGNhdGVnb3J5SWQ6IGMuaWQsXG4gICAgICAgICAgICAgIGV2ZW50SWQ6IGlkLFxuICAgICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICAgIHVwZGF0ZWRBdDogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgICAgfSBhcyBDYXRlZ29yeUV2ZW50VHlwZTtcbiAgICAgICAgICAgIHJldHVybiBjYXRlZ29yeUV2ZW50O1xuICAgICAgICAgIH0pO1xuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBjYXRlZ29yeUV2ZW50cyxcbiAgICAgICAgICBpZCxcbiAgICAgICAgICAnIGNhdGVnb3J5RXZlbnRzLCBpZCBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0cydcbiAgICAgICAgKTtcbiAgICAgICAgYXdhaXQgY3JlYXRlQ2F0ZWdvcnlFdmVudHMoY2F0ZWdvcnlFdmVudHMpO1xuICAgICAgICBjb25zdCB7XG4gICAgICAgICAgbmV3RXZlbnQ6IG5ld0V2ZW50MSxcbiAgICAgICAgICBuZXdSZW1pbmRlcnM6IG5ld1JlbWluZGVyczEsXG4gICAgICAgICAgbmV3VGltZUJsb2NraW5nOiBuZXdUaW1lQmxvY2tpbmcxLFxuICAgICAgICB9ID0gYXdhaXQgdXBkYXRlVmFsdWVzRm9yTWVldGluZ1R5cGVDYXRlZ29yaWVzKFxuICAgICAgICAgIGV2ZW50LFxuICAgICAgICAgIG5ld0V2ZW50LFxuICAgICAgICAgIGJlc3RNYXRjaFBsdXNNZWV0aW5nQ2F0ZWdvcmllcyxcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgbmV3UmVtaW5kZXJzLFxuICAgICAgICAgIG5ld1RpbWVCbG9ja2luZ1xuICAgICAgICApO1xuICAgICAgICBuZXdFdmVudCA9IG5ld0V2ZW50MTtcbiAgICAgICAgbmV3UmVtaW5kZXJzID0gbmV3UmVtaW5kZXJzMTtcbiAgICAgICAgbmV3VGltZUJsb2NraW5nID0gbmV3VGltZUJsb2NraW5nMTtcbiAgICAgIH1cblxuICAgICAgbmV3RXZlbnQudmVjdG9yID0gdmVjdG9yO1xuXG4gICAgICBjb25zb2xlLmxvZyhuZXdFdmVudCwgJyBuZXdFdmVudCBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0cycpO1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIG5ld1JlbWluZGVycyxcbiAgICAgICAgJyBuZXdSZW1pbmRlcnMgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHMnXG4gICAgICApO1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIG5ld1RpbWVCbG9ja2luZyxcbiAgICAgICAgJyBuZXdUaW1lQmxvY2tpbmcgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHMnXG4gICAgICApO1xuXG4gICAgICByZXR1cm4ge1xuICAgICAgICBuZXdFdmVudCxcbiAgICAgICAgbmV3UmVtaW5kZXJzLFxuICAgICAgICBuZXdUaW1lQmxvY2tpbmcsXG4gICAgICB9O1xuICAgIH1cbiAgICAvLyBubyBiZXN0IG1hdGNoIGNhdGVnb3J5IHdhcyBmb3VuZFxuICAgIC8vIGp1c3QgcmV0dXJuIHRoZSBldmVudCB0byBwbGFubmVyXG4gICAgLy8gZ2V0IHRoaXMgd2VlaydzIGV2ZW50c1xuICAgIGV2ZW50LnZlY3RvciA9IHZlY3RvcjtcbiAgICByZXR1cm4ge1xuICAgICAgbmV3RXZlbnQ6IGV2ZW50LFxuICAgIH07XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIGUnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldEV2ZW50RnJvbVByaW1hcnlLZXkgPSBhc3luYyAoXG4gIGV2ZW50SWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxFdmVudFBsdXNUeXBlPiA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRFdmVudEZyb21QcmltYXJ5S2V5JztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICBxdWVyeSBnZXRFdmVudEZyb21QcmltYXJ5S2V5KCRldmVudElkOiBTdHJpbmchKSB7XG4gICAgICBFdmVudF9ieV9wayhpZDogJGV2ZW50SWQpIHtcbiAgICAgICAgYWxsRGF5XG4gICAgICAgIGFueW9uZUNhbkFkZFNlbGZcbiAgICAgICAgYXR0YWNobWVudHNcbiAgICAgICAgYXR0ZW5kZWVzT21pdHRlZFxuICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICBjb2xvcklkXG4gICAgICAgIGNvbmZlcmVuY2VJZFxuICAgICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICAgIGNvcHlDYXRlZ29yaWVzXG4gICAgICAgIGNvcHlEdXJhdGlvblxuICAgICAgICBjb3B5SXNCcmVha1xuICAgICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgY29weUlzTWVldGluZ1xuICAgICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgICBjb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgICAgY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgIGNyZWF0b3JcbiAgICAgICAgZGFpbHlUYXNrTGlzdFxuICAgICAgICBkZWxldGVkXG4gICAgICAgIGR1cmF0aW9uXG4gICAgICAgIGVuZERhdGVcbiAgICAgICAgZW5kVGltZVVuc3BlY2lmaWVkXG4gICAgICAgIGV2ZW50SWRcbiAgICAgICAgZXZlbnRUeXBlXG4gICAgICAgIGV4dGVuZGVkUHJvcGVydGllc1xuICAgICAgICBmb2xsb3dVcEV2ZW50SWRcbiAgICAgICAgZm9yRXZlbnRJZFxuICAgICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzXG4gICAgICAgIGd1ZXN0c0Nhbk1vZGlmeVxuICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0c1xuICAgICAgICBoYW5nb3V0TGlua1xuICAgICAgICBoYXJkRGVhZGxpbmVcbiAgICAgICAgaHRtbExpbmtcbiAgICAgICAgaUNhbFVJRFxuICAgICAgICBpZFxuICAgICAgICBpc0JyZWFrXG4gICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICBpc0ZvbGxvd1VwXG4gICAgICAgIGlzTWVldGluZ1xuICAgICAgICBpc01lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgIGlzUG9zdEV2ZW50XG4gICAgICAgIGlzUHJlRXZlbnRcbiAgICAgICAgbGlua3NcbiAgICAgICAgbG9jYXRpb25cbiAgICAgICAgbG9ja2VkXG4gICAgICAgIG1heEF0dGVuZGVlc1xuICAgICAgICBtZXRob2RcbiAgICAgICAgbW9kaWZpYWJsZVxuICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICBuZWdhdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZVxuICAgICAgICBub3Rlc1xuICAgICAgICBvcmdhbml6ZXJcbiAgICAgICAgb3JpZ2luYWxBbGxEYXlcbiAgICAgICAgb3JpZ2luYWxTdGFydERhdGVcbiAgICAgICAgb3JpZ2luYWxUaW1lem9uZVxuICAgICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICBwb3NpdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgIHBvc2l0aXZlSW1wYWN0VGltZVxuICAgICAgICBwb3N0RXZlbnRJZFxuICAgICAgICBwcmVFdmVudElkXG4gICAgICAgIHByZWZlcnJlZERheU9mV2Vla1xuICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2VcbiAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICAgICAgcHJlZmVycmVkVGltZVxuICAgICAgICBwcmlvcml0eVxuICAgICAgICBwcml2YXRlQ29weVxuICAgICAgICByZWN1cnJlbmNlXG4gICAgICAgIHJlY3VycmVuY2VSdWxlXG4gICAgICAgIHJlY3VycmluZ0V2ZW50SWRcbiAgICAgICAgc2VuZFVwZGF0ZXNcbiAgICAgICAgc29mdERlYWRsaW5lXG4gICAgICAgIHNvdXJjZVxuICAgICAgICBzdGFydERhdGVcbiAgICAgICAgc3RhdHVzXG4gICAgICAgIHN1bW1hcnlcbiAgICAgICAgdGFza0lkXG4gICAgICAgIHRhc2tUeXBlXG4gICAgICAgIHRpbWVCbG9ja2luZ1xuICAgICAgICB0aW1lem9uZVxuICAgICAgICB0aXRsZVxuICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgdW5saW5rXG4gICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICAgIHVzZXJJZFxuICAgICAgICB1c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHlcbiAgICAgICAgdXNlck1vZGlmaWVkQ2F0ZWdvcmllc1xuICAgICAgICB1c2VyTW9kaWZpZWREdXJhdGlvblxuICAgICAgICB1c2VyTW9kaWZpZWRJc0JyZWFrXG4gICAgICAgIHVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgIHVzZXJNb2RpZmllZElzTWVldGluZ1xuICAgICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlXG4gICAgICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWxcbiAgICAgICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzXG4gICAgICAgIHVzZXJNb2RpZmllZFRpbWVCbG9ja2luZ1xuICAgICAgICB1c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZVxuICAgICAgICB2aXNpYmlsaXR5XG4gICAgICAgIHdlZWtseVRhc2tMaXN0XG4gICAgICAgIGJ5V2Vla0RheVxuICAgICAgICBsb2NhbFN5bmNlZFxuICAgICAgICB1c2VyTW9kaWZpZWRDb2xvclxuICAgICAgICBjb3B5Q29sb3JcbiAgICAgIH1cbiAgICB9XG4gIGA7XG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgRXZlbnRfYnlfcGs6IEV2ZW50UGx1c1R5cGUgfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIGV2ZW50SWQsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBnZXRFdmVudEZyb21QcmltYXJ5S2V5Jyk7XG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uRXZlbnRfYnlfcGs7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIGdldEV2ZW50RnJvbVByaW1hcnlLZXknKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGRlbGV0ZURvY0luU2VhcmNoMyA9IGFzeW5jIChpZDogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgY2xpZW50ID0gYXdhaXQgZ2V0U2VhcmNoQ2xpZW50KCk7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBjbGllbnQuZGVsZXRlKHtcbiAgICAgIGlkLFxuICAgICAgaW5kZXg6IHNlYXJjaEluZGV4LFxuICAgIH0pO1xuICAgIGNvbnNvbGUubG9nKCdEZWxldGluZyBkb2N1bWVudCBpbiBzZWFyY2g6Jyk7XG4gICAgY29uc29sZS5sb2cocmVzcG9uc2UuYm9keSk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBkZWxldGUgZG9jJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjb3B5T3ZlclByZXZpb3VzRXZlbnREZWZhdWx0cyA9IChcbiAgZXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIHByZXZpb3VzRXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIGNhdGVnb3J5PzogQ2F0ZWdvcnlUeXBlLFxuICB1c2VyUHJlZmVyZW5jZXM/OiBVc2VyUHJlZmVyZW5jZVR5cGVcbik6IEV2ZW50UGx1c1R5cGUgPT4ge1xuICBjb25zdCBwcmV2aW91c0R1cmF0aW9uID0gZGF5anNcbiAgICAuZHVyYXRpb24oXG4gICAgICBkYXlqcyhwcmV2aW91c0V2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoocHJldmlvdXNFdmVudD8udGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5kaWZmKFxuICAgICAgICAgIGRheWpzKHByZXZpb3VzRXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooXG4gICAgICAgICAgICBwcmV2aW91c0V2ZW50Py50aW1lem9uZSxcbiAgICAgICAgICAgIHRydWVcbiAgICAgICAgICApXG4gICAgICAgIClcbiAgICApXG4gICAgLmFzTWludXRlcygpO1xuICByZXR1cm4ge1xuICAgIC4uLmV2ZW50LFxuICAgIHRyYW5zcGFyZW5jeTogIWV2ZW50Py51c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHlcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weUF2YWlsYWJpbGl0eVxuICAgICAgICA/IHByZXZpb3VzRXZlbnQudHJhbnNwYXJlbmN5XG4gICAgICAgIDogY2F0ZWdvcnk/LmNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnRyYW5zcGFyZW5jeVxuICAgICAgICAgIDogY2F0ZWdvcnk/LmRlZmF1bHRBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgID8gJ3RyYW5zcGFyZW50J1xuICAgICAgICAgICAgOiB1c2VyUHJlZmVyZW5jZXM/LmNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py50cmFuc3BhcmVuY3lcbiAgICAgICAgICAgICAgOiBldmVudD8udHJhbnNwYXJlbmN5XG4gICAgICA6IGV2ZW50LnRyYW5zcGFyZW5jeSxcbiAgICBwcmVmZXJyZWRUaW1lOiAhZXZlbnQ/LnVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlXG4gICAgICA/IHByZXZpb3VzRXZlbnQ/LmNvcHlUaW1lUHJlZmVyZW5jZSAmJiBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWRUaW1lXG4gICAgICAgID8gcHJldmlvdXNFdmVudC5wcmVmZXJyZWRUaW1lXG4gICAgICAgIDogY2F0ZWdvcnk/LmNvcHlUaW1lUHJlZmVyZW5jZSAmJiBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWRUaW1lXG4gICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWRUaW1lXG4gICAgICAgICAgOiB1c2VyUHJlZmVyZW5jZXM/LmNvcHlUaW1lUHJlZmVyZW5jZSAmJiBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWRUaW1lXG4gICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZFRpbWVcbiAgICAgICAgICAgIDogZXZlbnQ/LnByZWZlcnJlZFRpbWVcbiAgICAgIDogZXZlbnQucHJlZmVycmVkVGltZSxcbiAgICBwcmVmZXJyZWREYXlPZldlZWs6ICFldmVudD8udXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2VcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weVRpbWVQcmVmZXJlbmNlICYmIHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZERheU9mV2Vla1xuICAgICAgICA/IHByZXZpb3VzRXZlbnQucHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICAgIDogY2F0ZWdvcnk/LmNvcHlUaW1lUHJlZmVyZW5jZSAmJiBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWREYXlPZldlZWtcbiAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZERheU9mV2Vla1xuICAgICAgICAgIDogdXNlclByZWZlcmVuY2VzPy5jb3B5VGltZVByZWZlcmVuY2UgJiZcbiAgICAgICAgICAgICAgcHJldmlvdXNFdmVudD8ucHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZERheU9mV2Vla1xuICAgICAgICAgICAgOiBldmVudD8ucHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICA6IGV2ZW50LnByZWZlcnJlZERheU9mV2VlayxcbiAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZTogIWV2ZW50Py51c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZVxuICAgICAgPyBwcmV2aW91c0V2ZW50Py5jb3B5VGltZVByZWZlcmVuY2UgJiZcbiAgICAgICAgcHJldmlvdXNFdmVudD8ucHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICAgICAgPyBwcmV2aW91c0V2ZW50LnByZWZlcnJlZFN0YXJ0VGltZVJhbmdlXG4gICAgICAgIDogY2F0ZWdvcnk/LmNvcHlUaW1lUHJlZmVyZW5jZSAmJiBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWRTdGFydFRpbWVSYW5nZVxuICAgICAgICAgID8gcHJldmlvdXNFdmVudD8ucHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weVRpbWVQcmVmZXJlbmNlICYmXG4gICAgICAgICAgICAgIHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZFN0YXJ0VGltZVJhbmdlXG4gICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZFN0YXJ0VGltZVJhbmdlXG4gICAgICAgICAgICA6IGV2ZW50Py5wcmVmZXJyZWRTdGFydFRpbWVSYW5nZVxuICAgICAgOiBldmVudC5wcmVmZXJyZWRTdGFydFRpbWVSYW5nZSxcbiAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2U6ICFldmVudD8udXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2VcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weVRpbWVQcmVmZXJlbmNlICYmXG4gICAgICAgIHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICA/IHByZXZpb3VzRXZlbnQucHJlZmVycmVkRW5kVGltZVJhbmdlXG4gICAgICAgIDogY2F0ZWdvcnk/LmNvcHlUaW1lUHJlZmVyZW5jZSAmJiBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWRFbmRUaW1lUmFuZ2VcbiAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICAgIDogdXNlclByZWZlcmVuY2VzPy5jb3B5VGltZVByZWZlcmVuY2UgJiZcbiAgICAgICAgICAgICAgcHJldmlvdXNFdmVudD8ucHJlZmVycmVkRW5kVGltZVJhbmdlXG4gICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICAgICAgOiBldmVudD8ucHJlZmVycmVkRW5kVGltZVJhbmdlXG4gICAgICA6IGV2ZW50LnByZWZlcnJlZEVuZFRpbWVSYW5nZSxcbiAgICBwcmlvcml0eTpcbiAgICAgICghZXZlbnQ/LnVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWxcbiAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5jb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgICAgID8gcHJldmlvdXNFdmVudC5wcmlvcml0eVxuICAgICAgICAgIDogY2F0ZWdvcnk/LmNvcHlQcmlvcml0eUxldmVsXG4gICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByaW9yaXR5XG4gICAgICAgICAgICA6IGNhdGVnb3J5Py5kZWZhdWx0UHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0UHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByaW9yaXR5XG4gICAgICAgICAgICAgICAgOiBldmVudD8ucHJpb3JpdHlcbiAgICAgICAgOiBldmVudD8ucHJpb3JpdHkpIHx8IDEsXG4gICAgaXNCcmVhazogIWV2ZW50Py51c2VyTW9kaWZpZWRJc0JyZWFrXG4gICAgICA/IHByZXZpb3VzRXZlbnQ/LmNvcHlJc0JyZWFrXG4gICAgICAgID8gcHJldmlvdXNFdmVudC5pc0JyZWFrXG4gICAgICAgIDogY2F0ZWdvcnk/LmNvcHlJc0JyZWFrXG4gICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5pc0JyZWFrXG4gICAgICAgICAgOiBjYXRlZ29yeT8uZGVmYXVsdElzQnJlYWtcbiAgICAgICAgICAgID8gY2F0ZWdvcnk/LmRlZmF1bHRJc0JyZWFrXG4gICAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weUlzQnJlYWtcbiAgICAgICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5pc0JyZWFrXG4gICAgICAgICAgICAgIDogZXZlbnQ/LmlzQnJlYWtcbiAgICAgIDogZXZlbnQuaXNCcmVhayxcbiAgICBpc01lZXRpbmc6ICFldmVudD8udXNlck1vZGlmaWVkSXNNZWV0aW5nXG4gICAgICA/IHByZXZpb3VzRXZlbnQ/LmNvcHlJc01lZXRpbmdcbiAgICAgICAgPyBwcmV2aW91c0V2ZW50LmlzTWVldGluZ1xuICAgICAgICA6IGNhdGVnb3J5Py5jb3B5SXNNZWV0aW5nXG4gICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5pc01lZXRpbmdcbiAgICAgICAgICA6IGNhdGVnb3J5Py5kZWZhdWx0SXNNZWV0aW5nXG4gICAgICAgICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0SXNNZWV0aW5nXG4gICAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weUlzTWVldGluZ1xuICAgICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LmlzTWVldGluZ1xuICAgICAgICAgICAgICA6IGNhdGVnb3J5Py5uYW1lID09PSBtZWV0aW5nTGFiZWxcbiAgICAgICAgICAgICAgICA/IHRydWVcbiAgICAgICAgICAgICAgICA6IGV2ZW50Py5pc01lZXRpbmdcbiAgICAgIDogZXZlbnQuaXNNZWV0aW5nLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nOiAhZXZlbnQ/LnVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICA/IHByZXZpb3VzRXZlbnQ/LmNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICA/IHByZXZpb3VzRXZlbnQuaXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgOiBjYXRlZ29yeT8uY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5pc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgIDogY2F0ZWdvcnk/LmRlZmF1bHRJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgPyBjYXRlZ29yeT8uZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICAgID8gcHJldmlvdXNFdmVudD8uaXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgOiBjYXRlZ29yeT8ubmFtZSA9PT0gZXh0ZXJuYWxNZWV0aW5nTGFiZWxcbiAgICAgICAgICAgICAgICA/IHRydWVcbiAgICAgICAgICAgICAgICA6IGV2ZW50Py5pc0V4dGVybmFsTWVldGluZ1xuICAgICAgOiBldmVudC5pc0V4dGVybmFsTWVldGluZyxcbiAgICBtb2RpZmlhYmxlOiAhZXZlbnQ/LnVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weU1vZGlmaWFibGVcbiAgICAgICAgPyBwcmV2aW91c0V2ZW50Lm1vZGlmaWFibGVcbiAgICAgICAgOiBjYXRlZ29yeT8uY29weU1vZGlmaWFibGVcbiAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/Lm1vZGlmaWFibGVcbiAgICAgICAgICA6IGNhdGVnb3J5Py5kZWZhdWx0TW9kaWZpYWJsZVxuICAgICAgICAgICAgPyBjYXRlZ29yeT8uZGVmYXVsdE1vZGlmaWFibGVcbiAgICAgICAgICAgIDogdXNlclByZWZlcmVuY2VzPy5jb3B5TW9kaWZpYWJsZVxuICAgICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/Lm1vZGlmaWFibGVcbiAgICAgICAgICAgICAgOiBldmVudD8ubW9kaWZpYWJsZVxuICAgICAgOiBldmVudC5tb2RpZmlhYmxlLFxuICAgIGlzTWVldGluZ01vZGlmaWFibGU6ICFldmVudD8udXNlck1vZGlmaWVkTW9kaWZpYWJsZVxuICAgICAgPyBwcmV2aW91c0V2ZW50Py5jb3B5SXNNZWV0aW5nXG4gICAgICAgID8gcHJldmlvdXNFdmVudC5pc01lZXRpbmdcbiAgICAgICAgOiBjYXRlZ29yeT8uY29weUlzTWVldGluZ1xuICAgICAgICAgID8gcHJldmlvdXNFdmVudD8uaXNNZWV0aW5nXG4gICAgICAgICAgOiBjYXRlZ29yeT8uZGVmYXVsdElzTWVldGluZ1xuICAgICAgICAgICAgPyBjYXRlZ29yeT8uZGVmYXVsdElzTWVldGluZ1xuICAgICAgICAgICAgOiB1c2VyUHJlZmVyZW5jZXM/LmNvcHlJc01lZXRpbmdcbiAgICAgICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5pc01lZXRpbmdcbiAgICAgICAgICAgICAgOiBldmVudD8uaXNNZWV0aW5nXG4gICAgICA6IGV2ZW50LmlzTWVldGluZ01vZGlmaWFibGUsXG4gICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlOiAhZXZlbnQ/LnVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgID8gcHJldmlvdXNFdmVudC5pc0V4dGVybmFsTWVldGluZ1xuICAgICAgICA6IGNhdGVnb3J5Py5jb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LmlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgOiBjYXRlZ29yeT8uZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgIDogdXNlclByZWZlcmVuY2VzPy5jb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5pc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgICA6IGV2ZW50Py5pc0V4dGVybmFsTWVldGluZ1xuICAgICAgOiBldmVudC5pc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGUsXG4gICAgZHVyYXRpb246ICFldmVudD8udXNlck1vZGlmaWVkRHVyYXRpb25cbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weUR1cmF0aW9uXG4gICAgICAgID8gcHJldmlvdXNFdmVudC5kdXJhdGlvbiB8fCBwcmV2aW91c0R1cmF0aW9uXG4gICAgICAgIDogZXZlbnQ/LmR1cmF0aW9uXG4gICAgICA6IGV2ZW50LmR1cmF0aW9uLFxuICAgIGVuZERhdGU6ICFldmVudD8udXNlck1vZGlmaWVkRHVyYXRpb25cbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weUR1cmF0aW9uXG4gICAgICAgID8gZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5hZGQocHJldmlvdXNFdmVudC5kdXJhdGlvbiB8fCBwcmV2aW91c0R1cmF0aW9uLCAnbWludXRlcycpXG4gICAgICAgICAgICAuZm9ybWF0KClcbiAgICAgICAgOiBldmVudD8uZW5kRGF0ZVxuICAgICAgOiBldmVudC5lbmREYXRlLFxuICAgIHByZWZlcnJlZFRpbWVSYW5nZXM6ICFldmVudD8udXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2VcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weVRpbWVQcmVmZXJlbmNlICYmXG4gICAgICAgIHByZXZpb3VzRXZlbnQucHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMFxuICAgICAgICA/IHByZXZpb3VzRXZlbnQucHJlZmVycmVkVGltZVJhbmdlc1xuICAgICAgICA6IGNhdGVnb3J5Py5jb3B5VGltZVByZWZlcmVuY2UgJiZcbiAgICAgICAgICAgIHByZXZpb3VzRXZlbnQucHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMFxuICAgICAgICAgID8gcHJldmlvdXNFdmVudD8ucHJlZmVycmVkVGltZVJhbmdlc1xuICAgICAgICAgIDogdXNlclByZWZlcmVuY2VzPy5jb3B5VGltZVByZWZlcmVuY2UgJiZcbiAgICAgICAgICAgICAgcHJldmlvdXNFdmVudC5wcmVmZXJyZWRUaW1lUmFuZ2VzPy5sZW5ndGggPiAwXG4gICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZFRpbWVSYW5nZXNcbiAgICAgICAgICAgIDogY2F0ZWdvcnk/LmRlZmF1bHRUaW1lUHJlZmVyZW5jZT8ubGVuZ3RoID4gMFxuICAgICAgICAgICAgICA/IGNhdGVnb3J5LmRlZmF1bHRUaW1lUHJlZmVyZW5jZS5tYXAoKHRwOiBhbnkpID0+ICh7XG4gICAgICAgICAgICAgICAgICAuLi50cCxcbiAgICAgICAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgICAgICAgICBldmVudElkOiBldmVudD8uaWQsXG4gICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICAgICAgICB1c2VySWQ6IGV2ZW50Py51c2VySWQsXG4gICAgICAgICAgICAgICAgfSkpXG4gICAgICAgICAgICAgIDogZXZlbnQ/LnByZWZlcnJlZFRpbWVSYW5nZXNcbiAgICAgIDogZXZlbnQucHJlZmVycmVkVGltZVJhbmdlcyxcbiAgfTtcbn07XG4iXX0=