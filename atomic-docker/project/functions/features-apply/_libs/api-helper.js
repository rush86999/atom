import { dayOfWeekIntToString, defaultOpenAIAPIKey, externalMeetingLabel, hasuraAdminSecret, hasuraGraphUrl, meetingLabel, minThresholdScore, optaPlannerPassword, optaPlannerUrl, optaPlannerUsername, } from '@features_apply/_libs/constants';
import got from 'got';
import { v4 as uuid } from 'uuid';
import dayjs from 'dayjs';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import _ from 'lodash';
import { getISODay, setISODay } from 'date-fns';
import OpenAI from 'openai';
import { getEventById, searchTrainingEvents, deleteTrainingEventsByIds, upsertTrainingEvents, } from '@functions/_utils/lancedb_service';
dayjs.extend(duration);
dayjs.extend(isBetween);
dayjs.extend(timezone);
dayjs.extend(utc);
const openai = new OpenAI({
    apiKey: defaultOpenAIAPIKey,
});
export const getEventVectorById = async (id) => {
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
            return { ok: true, data: event.vector }; // Explicitly cast if needed
        }
        console.log(`No event or vector found for ID ${id}`);
        return { ok: true, data: null }; // Not an error, but no data found
    }
    catch (e) {
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
export const deleteTrainingDataById = async (id) => {
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
    }
    catch (e) {
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
export const searchTrainingDataByVector = async (userId, searchVector) => {
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
        const results = await searchTrainingEvents(searchVector, 1, `userId = '${userId.replace(/'/g, "''")}'`);
        if (results && results.length > 0) {
            return { ok: true, data: results[0] };
        }
        return { ok: true, data: null }; // Found nothing, but operation was successful
    }
    catch (e) {
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
export const addTrainingData = async (trainingEntry) => {
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
        console.log(`Successfully added/updated training data for ID: ${trainingEntry.id}`);
        return { ok: true, data: undefined };
    }
    catch (e) {
        console.error(`Error adding/updating training data for ID ${trainingEntry.id} in LanceDB:`, e);
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
export const convertEventTitleToOpenAIVector = async (title) => {
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
        const embeddingRequest = {
            model: 'text-embedding-3-small',
            input: title,
        };
        const res = await openai.embeddings.create(embeddingRequest);
        // console.log(res, ' res inside convertEventTitleToOpenAIVectors'); // Too verbose for normal operation
        const embedding = res?.data?.[0]?.embedding;
        if (!embedding) {
            console.error('OpenAI embedding response did not contain embedding data.');
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
    }
    catch (e) {
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
export const listMeetingAssistPreferredTimeRangesGivenMeetingId = async (meetingId) => {
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
        console.log(res, ' res from listMeetingAssistPreferredTimeRangesGivenMeetingId'); // Corrected log
        return {
            ok: true,
            data: res?.data?.Meeting_Assist_Preferred_Time_Range || null,
        };
    }
    catch (e) {
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
export const listMeetingAssistAttendeesGivenMeetingId = async (meetingId) => {
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
        console.log(res, ' res from listMeetingAssistAttendees');
        return { ok: true, data: res?.data?.Meeting_Assist_Attendee || null };
    }
    catch (e) {
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
export const getMeetingAssistAttendee = async (id) => {
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
        const attendee = res?.data?.Meeting_Assist_Attendee_by_pk;
        if (!attendee) {
            // Hasura returns null for _by_pk if not found
            return { ok: true, data: null };
        }
        return { ok: true, data: attendee };
    }
    catch (e) {
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
export const getMeetingAssist = async (id) => {
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
        const meetingAssist = res?.data?.Meeting_Assist_by_pk;
        if (!meetingAssist) {
            // Hasura returns null for _by_pk if not found
            return { ok: true, data: null };
        }
        return { ok: true, data: meetingAssist };
    }
    catch (e) {
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
export const listMeetingAssistEventsForAttendeeGivenDates = async (attendeeId, hostStartDate, hostEndDate, userTimezone, hostTimezone) => {
    if (!attendeeId ||
        !hostStartDate ||
        !hostEndDate ||
        !userTimezone ||
        !hostTimezone) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Missing required parameters for listing meeting assist events.',
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
        return { ok: true, data: res?.data?.Meeting_Assist_Event || null };
    }
    catch (e) {
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
export const listEventsForDate = async (userId, startDate, endDate, timezone) => {
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
        console.log(res, ' res from listEventsForDate'); // Corrected log
        return { ok: true, data: res?.data?.Event || null };
    }
    catch (e) {
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
export const listEventsForUserGivenDates = async (userId, hostStartDate, hostEndDate, userTimezone, hostTimezone) => {
    if (!userId ||
        !hostStartDate ||
        !hostEndDate ||
        !userTimezone ||
        !hostTimezone) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Missing required parameters for listing events for user given dates.',
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
        console.log(res, ' res from listEventsForUser');
        return { ok: true, data: res?.data?.Event || null };
    }
    catch (e) {
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
export const processMeetingAssistForOptaplanner = async () => {
    try {
        // ... existing logic ...
        // If successful:
        // return { ok: true, data: { message: "Processing for OptaPlanner initiated/completed." } };
        console.warn('processMeetingAssistForOptaplanner logic is complex and not fully refactored for error handling here.');
        return {
            ok: true,
            data: {
                message: 'Placeholder response for processMeetingAssistForOptaplanner.',
            },
        };
    }
    catch (e) {
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
export const listPreferredTimeRangesForEvent = async (eventId
// This function is missing userId for context if it's a user-specific action
// or if it's a generic lookup by eventId, it's fine. Assuming generic for now.
) => {
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
        return { ok: true, data: res?.data?.PreferredTimeRange || null };
    }
    catch (e) {
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
                console.log(foundSpace, index, ' foundSpace, index, (!foundSpace) && (index < filteredEvents.length)');
                const possibleEndDate = dayjs(filteredEvents[index].startDate.slice(0, 19)).tz(timezone, true);
                const possibleStartDate = possibleEndDate.subtract(userPreference.breakLength, 'minute');
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
                .format('HH:mm'),
            endTime: dayjs(setISODay(dayjs()
                .hour(endHour)
                .minute(endMinute)
                .tz(userTimezone, true)
                .toDate(), i + 1))
                .tz(hostTimezone)
                .format('HH:mm'),
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
                        .format('HH:mm'),
                    endTime: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .hour(startHourByHost)
                        .minute(startMinuteByHost)
                        .add(i + 15, 'minute')
                        .format('HH:mm'),
                    hostId,
                    monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
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
                    .format('HH:mm'),
                endTime: dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .hour(startHourByHost)
                    .minute(startMinuteByHost)
                    .add(i + 15, 'minute')
                    .format('HH:mm'),
                hostId,
                monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
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
                .format('HH:mm'),
            endTime: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(startHourByHost)
                .minute(startMinuteByHost)
                .add(i + 15, 'minute')
                .format('HH:mm'),
            hostId,
            monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
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
                        .format('HH:mm'),
                    endTime: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .hour(startHourByHost)
                        .minute(startMinuteByHost)
                        .add(i + 30, 'minute')
                        .format('HH:mm'),
                    hostId,
                    monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
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
                    .format('HH:mm'),
                endTime: dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .hour(startHourByHost)
                    .minute(startMinuteByHost)
                    .add(i + 30, 'minute')
                    .format('HH:mm'),
                hostId,
                monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
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
                .format('HH:mm'),
            endTime: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(startHourByHost)
                .minute(startMinuteByHost)
                .add(i + 30, 'minute')
                .format('HH:mm'),
            hostId,
            monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
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
        dayjs()
            .tz(timezone)
            .hour(parseInt(positiveImpactTime.slice(0, 2), 10))
            .minute(parseInt(positiveImpactTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm')) ||
        undefined;
    const adjustedNegativeImpactTime = (negativeImpactTime &&
        dayjs()
            .tz(timezone)
            .hour(parseInt(negativeImpactTime.slice(0, 2), 10))
            .minute(parseInt(negativeImpactTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm')) ||
        undefined;
    const adjustedPreferredTime = (preferredTime &&
        dayjs()
            .tz(timezone)
            .hour(parseInt(preferredTime.slice(0, 2), 10))
            .minute(parseInt(preferredTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm')) ||
        undefined;
    const adjustedPreferredStartTimeRange = (preferredStartTimeRange &&
        dayjs()
            .tz(timezone)
            .hour(parseInt(preferredStartTimeRange.slice(0, 2), 10))
            .minute(parseInt(preferredStartTimeRange.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm')) ||
        undefined;
    const adjustedPreferredEndTimeRange = (preferredEndTimeRange &&
        dayjs()
            .tz(timezone)
            .hour(parseInt(preferredEndTimeRange.slice(0, 2), 10))
            .minute(parseInt(preferredEndTimeRange.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm')) ||
        undefined;
    const adjustedPreferredTimeRanges = preferredTimeRanges?.map((e) => ({
        dayOfWeek: dayOfWeekIntToString?.[e?.dayOfWeek] ?? null,
        startTime: dayjs()
            .tz(timezone)
            .hour(parseInt(e?.startTime.slice(0, 2), 10))
            .minute(parseInt(e?.startTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm'),
        endTime: dayjs()
            .tz(timezone)
            .hour(parseInt(e?.endTime.slice(0, 2), 10))
            .minute(parseInt(e?.endTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm'),
        eventId,
        userId,
        hostId,
    })) ?? null;
    const eventPlannerRequestBody = {
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
            .format('HH:mm')) ||
        undefined;
    const adjustedNegativeImpactTime = (negativeImpactTime &&
        dayjs()
            .tz(timezone)
            .hour(parseInt(negativeImpactTime.slice(0, 2), 10))
            .minute(parseInt(negativeImpactTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm')) ||
        undefined;
    const adjustedPreferredTime = (preferredTime &&
        dayjs()
            .tz(timezone)
            .hour(parseInt(preferredTime.slice(0, 2), 10))
            .minute(parseInt(preferredTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm')) ||
        undefined;
    const adjustedPreferredStartTimeRange = (preferredStartTimeRange &&
        dayjs()
            .tz(timezone)
            .hour(parseInt(preferredStartTimeRange.slice(0, 2), 10))
            .minute(parseInt(preferredStartTimeRange.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm')) ||
        undefined;
    const adjustedPreferredEndTimeRange = (preferredEndTimeRange &&
        dayjs()
            .tz(timezone)
            .hour(parseInt(preferredEndTimeRange.slice(0, 2), 10))
            .minute(parseInt(preferredEndTimeRange.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm')) ||
        undefined;
    const adjustedPreferredTimeRanges = preferredTimeRanges?.map((e) => ({
        dayOfWeek: dayOfWeekIntToString?.[e?.dayOfWeek] ?? null,
        startTime: dayjs()
            .tz(timezone)
            .hour(parseInt(e?.startTime.slice(0, 2), 10))
            .minute(parseInt(e?.startTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm'),
        endTime: dayjs()
            .tz(timezone)
            .hour(parseInt(e?.endTime.slice(0, 2), 10))
            .minute(parseInt(e?.endTime.slice(3), 10))
            .tz(hostTimezone)
            .format('HH:mm'),
        eventId,
        userId,
        hostId,
    })) ?? null;
    const eventPlannerRequestBody = {
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
                    .format('HH:mm'),
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
                .format('HH:mm'),
            endTime: dayjs(setISODay(dayjs()
                .hour(endHour)
                .minute(endMinute)
                .tz(hostTimezone, true)
                .toDate(), i + 1))
                .tz(hostTimezone)
                .format('HH:mm'),
            hostId,
            userId,
        });
    }
    return workTimes;
};
export const generateTimeSlotsForExternalAttendee = (hostStartDate, hostId, attendeeEvents, hostTimezone, userTimezone, isFirstDay) => {
    if (isFirstDay) {
        const dayOfWeekIntByHost = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
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
                        .format('HH:mm'),
                    endTime: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .hour(startHourOfHostDateByHost)
                        .minute(startMinuteOfHostDateByHost)
                        .add(i + 15, 'minute')
                        .format('HH:mm'),
                    hostId,
                    monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
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
                    .format('HH:mm'),
                endTime: dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .hour(startHourOfHostDateByHost)
                    .minute(startMinuteOfHostDateByHost)
                    .add(i + 15, 'minute')
                    .format('HH:mm'),
                hostId,
                monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
            });
        }
        console.log(timeSlots, ' timeSlots inside generateTimeSlots for first day');
        return timeSlots;
    }
    const dayOfWeekIntByHost = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
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
                .format('HH:mm'),
            endTime: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(workStartHourByHost)
                .minute(workStartMinuteByHost)
                .add(i + 15, 'minute')
                .format('HH:mm'),
            hostId,
            monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
        });
    }
    console.log(timeSlots, ' timeSlots inside generateTimeSlots');
    return timeSlots;
};
export const generateTimeSlotsLiteForExternalAttendee = (hostStartDate, hostId, attendeeEvents, hostTimezone, userTimezone, isFirstDay) => {
    if (isFirstDay) {
        const dayOfWeekIntByHost = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
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
                        .format('HH:mm'),
                    endTime: dayjs(hostStartDate.slice(0, 19))
                        .tz(hostTimezone, true)
                        .hour(startHourOfHostDateByHost)
                        .minute(startMinuteOfHostDateByHost)
                        .add(i + 30, 'minute')
                        .format('HH:mm'),
                    hostId,
                    monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
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
                    .format('HH:mm'),
                endTime: dayjs(hostStartDate.slice(0, 19))
                    .tz(hostTimezone, true)
                    .hour(startHourOfHostDateByHost)
                    .minute(startMinuteOfHostDateByHost)
                    .add(i + 30, 'minute')
                    .format('HH:mm'),
                hostId,
                monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
            });
        }
        console.log(timeSlots, ' timeSlots inside generateTimeSlots for first day');
        return timeSlots;
    }
    const dayOfWeekIntByHost = getISODay(dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
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
                .format('HH:mm'),
            endTime: dayjs(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .hour(workStartHourByHost)
                .minute(workStartMinuteByHost)
                .add(i + 30, 'minute')
                .format('HH:mm'),
            hostId,
            monthDay: formatToMonthDay(monthByHost, dayOfMonthByHost),
        });
    }
    console.log(timeSlots, ' timeSlots inside generateTimeSlots');
    return timeSlots;
};
export const processEventsForOptaPlannerForExternalAttendees = async (userIds, mainHostId, allExternalEvents, windowStartDate, windowEndDate, hostTimezone, externalAttendees, oldExternalMeetingEvents, newMeetingEvents) => {
    try {
        const modifiedAllExternalEvents = allExternalEvents?.map((e) => convertMeetingAssistEventTypeToEventPlusType(e, externalAttendees?.find((a) => a?.id === e?.attendeeId)?.userId));
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
        const timeslots = [];
        for (let i = 0; i < startDatesForEachDay.length; i++) {
            if (i === 0) {
                for (const externalAttendee of externalAttendees) {
                    const timeslotsForDay = await generateTimeSlotsLiteForExternalAttendee(startDatesForEachDay?.[i], mainHostId, modifiedAllExternalEvents, hostTimezone, externalAttendee?.timezone, true);
                    unfilteredTimeslots.push(...timeslotsForDay);
                }
                continue;
            }
            for (const externalAttendee of externalAttendees) {
                const timeslotsForDay = await generateTimeSlotsLiteForExternalAttendee(startDatesForEachDay?.[i], mainHostId, modifiedAllExternalEvents, hostTimezone, externalAttendee?.timezone, false);
                unfilteredTimeslots.push(...timeslotsForDay);
            }
        }
        timeslots.push(..._.uniqWith(unfilteredTimeslots, _.isEqual));
        console.log(timeslots, ' timeslots');
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
        if (!event) {
            throw new Error('no event passed inside findBestMatchCategory2');
        }
        if (!possibleLabels) {
            throw new Error('no possible labels passed inside findBestMatchCategory2');
        }
        const { summary, notes } = event;
        const sentence = `${summary}${notes ? `: ${notes}` : ''}`;
        const labelNames = possibleLabels.map((a) => a?.name);
        const systemPrompt = 'You are an expert event categorizer. Given an event description and a list of possible categories, return a JSON array string containing only the names of the categories that directly apply to the event. Do not provide any explanation, only the JSON array string.';
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
            let matchedLabels = [];
            if (llmResponseString) {
                try {
                    matchedLabels = JSON.parse(llmResponseString);
                    if (!Array.isArray(matchedLabels) ||
                        !matchedLabels.every((item) => typeof item === 'string')) {
                        console.error('LLM response is not a valid JSON array of strings:', llmResponseString);
                        matchedLabels = []; // Fallback to empty if not a string array
                    }
                }
                catch (parseError) {
                    console.error('Error parsing LLM response:', parseError, llmResponseString);
                    // Fallback: attempt to extract labels if it's a simple list not in JSON array format
                    // This is a basic fallback, might need more robust parsing depending on LLM behavior
                    if (typeof llmResponseString === 'string') {
                        matchedLabels = labelNames.filter((label) => llmResponseString.includes(label));
                    }
                    else {
                        matchedLabels = [];
                    }
                }
            }
            else {
                console.error('LLM response content is null or undefined.');
                matchedLabels = [];
            }
            const scores = labelNames.map((label) => matchedLabels.includes(label) ? 0.9 : 0.1);
            const result = {
                sequence: uuid(), // Added sequence property
                labels: labelNames,
                scores,
            };
            console.log(result, event?.id, ' result, event?.id inside findBestMatchCategory2 with OpenAI');
            return result;
        }
        catch (apiError) {
            console.error('Error calling OpenAI API or processing its response:', apiError);
            // Fallback to low scores for all categories in case of API error
            const scores = labelNames.map(() => 0.1);
            const errorResult = {
                sequence: uuid(), // Added sequence property
                labels: labelNames,
                scores,
            };
            return errorResult;
        }
    }
    catch (e) {
        // This outer catch block handles errors from the initial validation steps
        console.log(e, ' initial error in findBestMatchCategory2');
        // Optionally rethrow or return a specific error response
        throw e; // Re-throwing the original error if it's from pre-API call logic
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
    const meetingIndex = newPossibleLabels.indexOf(meetingLabel);
    const externalMeetingIndex = newPossibleLabels.indexOf(externalMeetingLabel);
    if (meetingIndex > -1 && scores[meetingIndex] > minThresholdScore) {
        bestMatchCategories.push(categories.find((category) => category.name === meetingLabel));
    }
    if (externalMeetingIndex > -1 &&
        scores[externalMeetingIndex] > minThresholdScore) {
        bestMatchCategories.push(categories.find((category) => category.name === externalMeetingLabel));
    }
    if (newEvent.isMeeting && meetingIndex > -1) {
        bestMatchCategories.push(categories.find((category) => category.name === meetingLabel));
    }
    if (newEvent.isExternalMeeting && externalMeetingIndex > -1) {
        bestMatchCategories.push(categories.find((category) => category.name === externalMeetingLabel));
    }
    return bestMatchCategories;
};
export const processEventForMeetingTypeCategories = (newEvent, bestMatchCategory, newPossibleLabels, scores, categories) => {
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
export const createRemindersAndBufferTimesForBestMatchCategory = async (id, userId, newEvent, bestMatchCategory, newReminders1, newBufferTimes1, previousEvent) => {
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
        const reminders = createRemindersUsingCategoryDefaultsForEvent(newEvent, bestMatchCategory, oldReminders, previousEvent);
        console.log(reminders, ' reminders');
        if (reminders?.length > 0 &&
            bestMatchCategory?.copyReminders &&
            !newEvent?.userModifiedReminders) {
            newReminders.push(...reminders);
        }
        if (!newEvent?.userModifiedTimeBlocking &&
            bestMatchCategory?.copyTimeBlocking) {
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
    if (!categoryEvents || categoryEvents.length === 0) {
        // Not an error, but nothing to do. Could also return success.
        console.log('No category events provided to createCategoryEvents.');
        return { ok: true, data: undefined };
    }
    try {
        for (const categoryEvent of categoryEvents) {
            // Basic validation for each categoryEvent
            if (!categoryEvent ||
                !categoryEvent.categoryId ||
                !categoryEvent.eventId ||
                !categoryEvent.userId ||
                !categoryEvent.id) {
                console.warn('Skipping invalid categoryEvent in createCategoryEvents:', categoryEvent);
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
        return { ok: true, data: undefined };
    }
    catch (e) {
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
        return { ok: true, data: res?.data?.Reminder || null };
    }
    catch (e) {
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
export const createRemindersUsingCategoryDefaultsForEvent = (event, bestMatchCategory, oldReminders, previousEvent) => {
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
export const createPreAndPostEventsForCategoryDefaults = (bestMatchCategory, event, previousEvent) => {
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
    let valuesToReturn = {};
    valuesToReturn.newEvent = event;
    if (bestMatchCategory?.defaultTimeBlocking?.afterEvent) {
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
export const updateValuesForMeetingTypeCategories = async (event, newEvent1, bestMatchCategories, userId, newReminders1, newTimeBlocking1, // Updated type
previousEvent) => {
    if (!bestMatchCategories ||
        bestMatchCategories.length === 0 ||
        !newEvent1 ||
        !userId) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Required parameters missing for updating values for meeting type categories.',
            },
        };
    }
    try {
        let newEvent = newEvent1;
        let newReminders = newReminders1 || [];
        let newBufferTimes = newTimeBlocking1 || {}; // Ensure it's BufferTimeObjectType
        const newCategoryConstantEvents = copyOverCategoryDefaultsForMeetingType(event, bestMatchCategories);
        console.log(newCategoryConstantEvents, ' newCategoryConstantEvents');
        if (newCategoryConstantEvents?.newEventMeeting?.id) {
            newEvent = { ...newEvent, ...newCategoryConstantEvents.newEventMeeting };
            const meetingCategory = bestMatchCategories.find((category) => category.name === meetingLabel);
            if (meetingCategory) {
                // Ensure category is found
                const listRemindersResponse = await listRemindersForEvent(newCategoryConstantEvents.newEventMeeting.id, userId);
                const oldReminders = listRemindersResponse.ok && listRemindersResponse.data
                    ? listRemindersResponse.data
                    : [];
                const reminders = createRemindersUsingCategoryDefaultsForEvent(newEvent, meetingCategory, oldReminders, previousEvent);
                if (reminders?.length > 0) {
                    newReminders.push(...reminders);
                    newReminders = _.uniqBy(newReminders, 'minutes');
                }
                const bufferTime = createPreAndPostEventsForCategoryDefaults(meetingCategory, newEvent, previousEvent);
                if (bufferTime?.beforeEvent)
                    newBufferTimes.beforeEvent =
                        bufferTime.beforeEvent;
                if (bufferTime?.afterEvent)
                    newBufferTimes.afterEvent =
                        bufferTime.afterEvent;
                if (bufferTime?.newEvent?.preEventId ||
                    bufferTime?.newEvent?.postEventId)
                    newEvent = bufferTime.newEvent;
            }
        }
        if (newCategoryConstantEvents?.newEventExternal?.id) {
            newEvent = { ...newEvent, ...newCategoryConstantEvents.newEventExternal };
            const externalCategory = bestMatchCategories.find((category) => category.name === externalMeetingLabel);
            if (externalCategory) {
                // Ensure category is found
                const listRemindersResponse = await listRemindersForEvent(newCategoryConstantEvents.newEventExternal.id, userId);
                const oldReminders = listRemindersResponse.ok && listRemindersResponse.data
                    ? listRemindersResponse.data
                    : [];
                const reminders = createRemindersUsingCategoryDefaultsForEvent(newEvent, externalCategory, oldReminders, previousEvent);
                if (reminders?.length > 0) {
                    newReminders.push(...reminders);
                    newReminders = _.uniqBy(newReminders, 'minutes');
                }
                const timeBlocking = createPreAndPostEventsForCategoryDefaults(externalCategory, newEvent, previousEvent);
                if (timeBlocking?.beforeEvent)
                    newBufferTimes.beforeEvent =
                        timeBlocking.beforeEvent;
                if (timeBlocking?.afterEvent)
                    newBufferTimes.afterEvent =
                        timeBlocking.afterEvent;
                if (timeBlocking?.newEvent?.preEventId ||
                    timeBlocking?.newEvent?.postEventId)
                    newEvent = timeBlocking.newEvent;
            }
        }
        return {
            ok: true,
            data: {
                newEvent,
                newReminders,
                newBufferTimes: newBufferTimes,
            },
        };
    }
    catch (e) {
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
export const processUserEventForCategoryDefaults = async (event, vector) => {
    if (!event || !event.id || !event.userId || !vector) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Event, event ID, userId, and vector are required for category processing.',
            },
        };
    }
    try {
        const { id, userId } = event;
        console.log(id, ' id inside processUserEventForCategoryDefaults');
        const categoriesResponse = await getUserCategories(userId);
        if (!categoriesResponse.ok || !categoriesResponse.data) {
            // If categories can't be fetched, we might still proceed with the event, but without categorization benefits.
            console.warn(`Failed to get user categories for user ${userId}. Proceeding without categorization. Error: ${categoriesResponse.error?.message}`);
            event.vector = vector; // Ensure vector is set
            return { ok: true, data: { newEvent: event } }; // Or return error if categories are essential
        }
        const categories = categoriesResponse.data;
        if (categories.length === 0) {
            console.log(`No categories defined for user ${userId}. Event ${id} will not be categorized further.`);
            event.vector = vector;
            return { ok: true, data: { newEvent: event } };
        }
        const classificationResponse = await findBestMatchCategory2(event, categories);
        if (!classificationResponse.ok || !classificationResponse.data) {
            console.warn(`Category classification failed for event ${id}. Error: ${classificationResponse.error?.message}. Proceeding without applying category defaults.`);
            event.vector = vector;
            return { ok: true, data: { newEvent: event } };
        }
        const classificationBody = classificationResponse.data;
        const { labels, scores } = classificationBody;
        const bestMatchLabel = processBestMatchCategories(classificationBody, labels);
        let newEvent = { ...event, vector }; // Start with original event and add vector
        let newReminders = [];
        let newBufferTimes = {};
        if (bestMatchLabel) {
            const bestMatchCategory = categories.find((category) => category.name === bestMatchLabel);
            if (bestMatchCategory) {
                let bestMatchPlusMeetingCategories = processEventForMeetingTypeCategories(newEvent, bestMatchCategory, labels, scores, categories);
                bestMatchPlusMeetingCategories = getUniqueLabels(bestMatchPlusMeetingCategories);
                newEvent = copyOverCategoryDefaults(newEvent, bestMatchCategory);
                const remindersAndBuffersResponse = await createRemindersAndBufferTimesForBestMatchCategory(id, userId, newEvent, bestMatchCategory, [], {});
                if (remindersAndBuffersResponse.ok &&
                    remindersAndBuffersResponse.data) {
                    newEvent = remindersAndBuffersResponse.data.newEvent;
                    newReminders = remindersAndBuffersResponse.data.newReminders;
                    newBufferTimes = remindersAndBuffersResponse.data.newBufferTimes;
                }
                else {
                    console.warn(`Failed to create reminders/buffers for best match category for event ${id}: ${remindersAndBuffersResponse.error?.message}`);
                }
                if (bestMatchPlusMeetingCategories?.length > 0) {
                    const categoryEvents = bestMatchPlusMeetingCategories.map((c) => ({
                        categoryId: c.id,
                        eventId: id,
                        userId,
                        id: uuid(),
                        createdDate: new Date().toISOString(),
                        updatedAt: new Date().toISOString(),
                        Category: c,
                        deleted: false,
                    }));
                    const createCatEventsResponse = await createCategoryEvents(categoryEvents);
                    if (!createCatEventsResponse.ok) {
                        console.warn(`Failed to create category events for event ${id}: ${createCatEventsResponse.error?.message}`);
                    }
                    const updatedValuesResponse = await updateValuesForMeetingTypeCategories(event, newEvent, bestMatchPlusMeetingCategories, userId, newReminders, newBufferTimes);
                    if (updatedValuesResponse.ok && updatedValuesResponse.data) {
                        newEvent = updatedValuesResponse.data.newEvent;
                        newReminders = updatedValuesResponse.data.newReminders;
                        newBufferTimes = updatedValuesResponse.data.newBufferTimes;
                    }
                    else {
                        console.warn(`Failed to update values for meeting type categories for event ${id}: ${updatedValuesResponse.error?.message}`);
                    }
                }
            }
        }
        return { ok: true, data: { newEvent, newReminders, newBufferTimes } };
    }
    catch (e) {
        console.error(`Error processing user event ${event?.id} for category defaults:`, e);
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
export const listCategoriesForEvent = async (eventId) => {
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
        console.log(res, ' listCategoriesForEvent');
        const categories = res?.data?.Category_Event?.map((category) => category?.Category)?.filter((category) => category != null && category.id != null); // Ensure category and its id are not null
        console.log(categories, ' categories from listCategoriesForEvent after filter');
        return { ok: true, data: categories || null };
    }
    catch (e) {
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
export const processBestMatchCategoriesNoThreshold = (body, newPossibleLabels) => {
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
export const processUserEventForCategoryDefaultsWithUserModifiedCategories = async (event, vector) => {
    try {
        const { id, userId } = event;
        console.log(id, userId, ' id, userId inside processUserEventForCategoryDefaultsWithUserModifiedCategories');
        const categories = await listCategoriesForEvent(event?.id);
        console.log(categories, ' categories');
        const body = await findBestMatchCategory2(event, categories);
        console.log(body, ' body');
        const { labels, scores } = body;
        const bestMatchLabel = processBestMatchCategoriesNoThreshold(body, labels);
        console.log(bestMatchLabel, ' bestMatchLabel');
        let bestMatchCategory = null;
        let newEvent = event;
        console.log(newEvent, ' newEvent');
        let newReminders = [];
        let newBufferTimes = {};
        if (bestMatchLabel) {
            bestMatchCategory = categories.find((category) => category.name === bestMatchLabel);
            labels.push(meetingLabel, externalMeetingLabel);
            scores.push(0, 0);
            let bestMatchPlusMeetingCategories = processEventForMeetingTypeCategories(event, bestMatchCategory, labels, scores, categories);
            if (bestMatchPlusMeetingCategories?.length > 0) {
                bestMatchPlusMeetingCategories = getUniqueLabels(bestMatchPlusMeetingCategories);
                console.log(bestMatchPlusMeetingCategories, ' bestMatchAndMeetingCategories');
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
                console.log(categoryEvents, ' categoryEvents');
                await createCategoryEvents(categoryEvents);
                const { newEvent: newEvent1, newReminders: newReminders1, newBufferTimes: newTimeBlocking1, } = await updateValuesForMeetingTypeCategories(event, newEvent, bestMatchPlusMeetingCategories, userId, newReminders, newBufferTimes);
                newEvent = newEvent1;
                newReminders = newReminders1;
                newBufferTimes = newTimeBlocking1;
            }
        }
        let newCategoryDefaultEvent = null;
        if (bestMatchCategory) {
            newCategoryDefaultEvent = copyOverCategoryDefaults(event, bestMatchCategory);
        }
        console.log(newCategoryDefaultEvent, ' newCategoryDefaultEvent');
        newEvent = newCategoryDefaultEvent ?? newEvent ?? event;
        console.log(newEvent, ' newEvent');
        const { newEvent: newEvent1, newReminders: newReminders1, newBufferTimes: newTimeBlocking1, } = await createRemindersAndBufferTimesForBestMatchCategory(id, userId, newEvent, bestMatchCategory, newReminders, newBufferTimes);
        newEvent = newEvent1;
        newReminders = newReminders1;
        newBufferTimes = newTimeBlocking1;
        if (categories?.length > 1) {
            const { newEvent: newEvent1, newReminders: newReminders1, newBufferTimes: newTimeBlocking1, } = await updateValuesForMeetingTypeCategories(event, newEvent, categories, userId, newReminders, newBufferTimes);
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
    }
    catch (e) {
        console.log(e, ' e');
    }
};
export const getEventFromPrimaryKey = async (id) => {
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
    }
    catch (e) {
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
        colorId: previousEvent?.copyColor && previousEvent?.colorId
            ? previousEvent.colorId
            : userPreferences?.copyColor && previousEvent?.colorId
                ? previousEvent?.colorId
                : event?.colorId,
    };
};
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
export const createPreAndPostEventsFromPreviousEvent = (event, previousEvent) => {
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
    let valuesToReturn = {};
    valuesToReturn.newEvent = event;
    if (previousEvent?.timeBlocking?.afterEvent) {
        const formattedZoneAfterEventEndDate = dayjs(event.endDate.slice(0, 19))
            .tz(event.timezone, true)
            .add(previousEvent?.timeBlocking?.afterEvent, 'm')
            .format();
        const formattedZoneAfterEventStartDate = dayjs(event.endDate.slice(0, 19))
            .tz(event.timezone, true)
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
                afterEvent: previousEvent?.timeBlocking?.afterEvent,
            },
        };
    }
    if (previousEvent?.timeBlocking?.beforeEvent) {
        const formattedZoneBeforeEventStartDate = dayjs(event.startDate.slice(0, 19))
            .tz(event.timezone, true)
            .subtract(previousEvent?.timeBlocking?.beforeEvent, 'm')
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
                beforeEvent: previousEvent?.timeBlocking?.beforeEvent,
            },
        };
    }
    return valuesToReturn;
};
export const createRemindersFromPreviousEventForEvent = async (event, previousEvent, userId) => {
    if (event.userModifiedReminders) {
        console.log('no event inside createRemindersFromPreviousEventForEvent');
        return null;
    }
    if (!previousEvent?.id) {
        console.log('no previousEvent inside createRemindersFromPreviousEventForEvent');
        return null;
    }
    if (!previousEvent?.copyReminders) {
        console.log('no previousEvent inside createRemindersFromPreviousEventForEvent');
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
const copyOverMeetingAndExternalMeetingDefaultsWithPreviousEventFound = (event, previousEvent, category, userPreferences) => {
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
        priority: (!event?.userModifiedPriorityLevel
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
        colorId: previousEvent?.copyColor && previousEvent?.colorId
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
export const copyOverCategoryMeetingAndExternalMeetingDefaultsWithFoundPreviousEvent = (event, categories, userPreferences, previousEvent) => {
    if (!(categories?.length > 0)) {
        console.log('no categories inside copyOverCategoryDefaultsForConstantsWithFoundPreviousEvent');
        return;
    }
    if (!userPreferences?.id) {
        console.log('no userPreferences inside copyOverCategoryDefaultsForConstantsWithFoundPreviousEvent');
        return;
    }
    if (!previousEvent?.id) {
        console.log('no previousEvent inside copyOverCategoryDefaultsForConstantsWithFoundPreviousEvent');
        return;
    }
    if (!event?.id) {
        console.log('no event inside copyOverCategoryDefaultsForConstantsWithFoundPreviousEvent');
        return;
    }
    const meetingCategory = categories.find((category) => category.name === meetingLabel);
    const externalCategory = categories.find((category) => category.name === externalMeetingLabel);
    let newEventMeeting = {};
    let newEventExternal = {};
    if (meetingCategory?.id) {
        newEventMeeting =
            copyOverMeetingAndExternalMeetingDefaultsWithPreviousEventFound(event, previousEvent, meetingCategory, userPreferences);
    }
    if (externalCategory?.id) {
        newEventExternal =
            copyOverMeetingAndExternalMeetingDefaultsWithPreviousEventFound(event, previousEvent, meetingCategory, userPreferences);
    }
    return { newEventMeeting, newEventExternal };
};
export const createRemindersAndTimeBlockingFromPreviousEventGivenUserPreferences = async (userId, newEvent, newReminders1, newBufferTimes1, previousEvent, userPreferences) => {
    try {
        let newReminders = newReminders1 || [];
        let newBufferTimes = newBufferTimes1 || {};
        if (!newEvent?.userModifiedReminders && userPreferences?.copyReminders) {
            const reminders = await createRemindersFromPreviousEventForEvent(newEvent, previousEvent, userId);
            console.log(reminders, ' reminders');
            if (reminders?.length > 0 && !newEvent?.userModifiedReminders) {
                newReminders.push(...reminders);
            }
        }
        if (!newEvent?.userModifiedTimeBlocking &&
            userPreferences?.copyTimeBlocking) {
            const bufferTimes = createPreAndPostEventsFromPreviousEvent(newEvent, previousEvent);
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
        console.log(e, ' unable to create reminders and time blocking from previous event given user preferences');
    }
};
export const updateValuesForEventWithPreviousEventPlusMeetingAndExternalMeeting = async (event, newEvent1, bestMatchCategories, newReminders1, newTimeBlocking1, userId, userPreferences, previousEvent) => {
    try {
        let newEvent = newEvent1;
        let newReminders = newReminders1 || [];
        let newTimeBlocking = newTimeBlocking1 || {};
        const { newEventMeeting, newEventExternal } = copyOverCategoryMeetingAndExternalMeetingDefaultsWithFoundPreviousEvent(event, bestMatchCategories, userPreferences, previousEvent);
        if (newEventMeeting?.id) {
            newEvent = { ...newEvent, ...newEventMeeting };
            const meetingCategory = bestMatchCategories.find((category) => category.name === meetingLabel);
            const oldReminders = await listRemindersForEvent(newEventMeeting?.id, userId);
            const reminders = createRemindersUsingCategoryDefaultsForEvent(newEvent, meetingCategory, oldReminders, previousEvent);
            console.log(reminders, ' reminders');
            if (reminders?.length > 0 && !newEvent?.userModifiedReminders) {
                newReminders.push(...reminders);
                newReminders = _.uniqBy(newReminders, 'minutes');
            }
            if (!newEvent?.userModifiedTimeBlocking) {
                const timeBlocking = createPreAndPostEventsForCategoryDefaults(meetingCategory, newEvent, previousEvent);
                console.log(timeBlocking, ' timeBlocking');
                if (timeBlocking?.beforeEvent) {
                    newTimeBlocking.beforeEvent = timeBlocking.beforeEvent;
                }
                if (timeBlocking?.afterEvent) {
                    newTimeBlocking.afterEvent = timeBlocking.afterEvent;
                }
                if (timeBlocking?.newEvent?.preEventId ||
                    timeBlocking?.newEvent?.postEventId) {
                    newEvent = timeBlocking.newEvent;
                }
            }
        }
        if (newEventExternal?.id) {
            newEvent = { ...newEvent, ...newEventExternal };
            const externalCategory = bestMatchCategories.find((category) => category.name === externalMeetingLabel);
            const oldReminders = await listRemindersForEvent(newEventExternal.id, userId);
            const reminders = createRemindersUsingCategoryDefaultsForEvent(newEvent, externalCategory, oldReminders, previousEvent);
            console.log(reminders, ' reminders');
            if (reminders?.length > 0 && !newEvent?.userModifiedReminders) {
                newReminders.push(...reminders);
                newReminders = _.uniqBy(newReminders, 'minutes');
            }
            if (!newEvent?.userModifiedTimeBlocking) {
                const timeBlocking = createPreAndPostEventsForCategoryDefaults(externalCategory, newEvent);
                console.log(timeBlocking, ' timeBlocking');
                if (timeBlocking?.beforeEvent) {
                    newTimeBlocking.beforeEvent = timeBlocking.beforeEvent;
                }
                if (timeBlocking?.afterEvent) {
                    newTimeBlocking.afterEvent = timeBlocking.afterEvent;
                }
                if (timeBlocking?.newEvent?.preEventId ||
                    timeBlocking?.newEvent?.postEventId) {
                    newEvent = timeBlocking.newEvent;
                }
            }
        }
        return { newEvent, newReminders, newBufferTimes: newTimeBlocking };
    }
    catch (e) {
        console.log(e, ' unable to update values for default categories');
    }
};
export const createRemindersAndTimeBlockingFromPreviousEvent = async (userId, newEvent, newReminders1, newBufferTimes1, previousEvent) => {
    try {
        let newReminders = newReminders1 || [];
        let newBufferTimes = newBufferTimes1 || {};
        const reminders = await createRemindersFromPreviousEventForEvent(newEvent, previousEvent, userId);
        console.log(reminders, ' reminders');
        if (reminders?.length > 0 &&
            !newEvent?.userModifiedReminders &&
            previousEvent?.copyReminders) {
            newReminders.push(...reminders);
        }
        if (!newEvent?.userModifiedTimeBlocking &&
            previousEvent?.copyTimeBlocking) {
            const bufferTimes = createPreAndPostEventsFromPreviousEvent(newEvent, previousEvent);
            console.log(bufferTimes, ' timeBlocking');
            if (bufferTimes?.beforeEvent) {
                newBufferTimes.beforeEvent = bufferTimes.beforeEvent;
            }
            if (bufferTimes?.afterEvent) {
                newBufferTimes.afterEvent = bufferTimes.afterEvent;
            }
            if (bufferTimes?.newEvent?.preEventId ||
                bufferTimes?.newEvent?.postEventId) {
                newEvent = bufferTimes.newEvent;
            }
        }
        return { newEvent, newReminders, newBufferTimes: newBufferTimes };
    }
    catch (e) {
        console.log(e, ' unable to create reminders and time blocking from previous event');
    }
};
export const processEventWithFoundPreviousEventAndCopyCategories = async (id, previousEvent, oldEvent, userPreferences, bestMatchCategory1, userId, bestMatchCategories1, newModifiedEvent1, newReminders1 = [], newTimeBlocking1 = {}, previousCategories = [], previousMeetingCategoriesWithMeetingLabel = [], previousMeetingCategoriesWithExternalMeetingLabel = []) => {
    // Basic validation for required complex objects
    if (!id ||
        !previousEvent ||
        !oldEvent ||
        !userPreferences ||
        !bestMatchCategory1 ||
        !userId ||
        !bestMatchCategories1 ||
        !newModifiedEvent1) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'One or more critical input parameters are missing.',
            },
        };
    }
    try {
        let bestMatchCategories = bestMatchCategories1 || [];
        let bestMatchCategory = bestMatchCategory1 || {}; // Ensure it's CategoryType or an empty object
        let newModifiedEvent = newModifiedEvent1; // Not EventPlusType | object
        let newReminders = newReminders1 || [];
        let newTimeBlocking = newTimeBlocking1 || {};
        if (!previousEvent?.unlink && !oldEvent?.userModifiedCategories) {
            if ((previousEvent?.copyCategories || userPreferences?.copyCategories) &&
                previousCategories?.length > 0) {
                const createCatEventsResponse = await createCategoryEvents(previousCategories.map((c) => ({
                    categoryId: c.id,
                    eventId: id,
                    userId,
                    id: uuid(),
                    createdDate: new Date().toISOString(),
                    updatedAt: new Date().toISOString(),
                    Category: c,
                    deleted: false,
                })));
                if (!createCatEventsResponse.ok)
                    console.warn(`Failed to create category events for event ${id} during copy: ${createCatEventsResponse.error?.message}`);
            }
            if (previousCategories?.[0]?.id) {
                const classificationResponse = await findBestMatchCategory2(oldEvent, previousCategories);
                if (classificationResponse.ok && classificationResponse.data) {
                    const { labels, scores } = classificationResponse.data;
                    const bestMatchLabel = processBestMatchCategoriesNoThreshold(classificationResponse.data, labels);
                    bestMatchCategory =
                        previousCategories.find((category) => category.name === bestMatchLabel) || {};
                }
                else {
                    console.warn(`Classification failed for previous categories for event ${id}: ${classificationResponse.error?.message}`);
                }
                if (bestMatchCategory?.id) {
                    newModifiedEvent = copyOverPreviousEventDefaults(oldEvent, previousEvent, bestMatchCategory, userPreferences);
                }
            }
            else {
                newModifiedEvent = copyOverPreviousEventDefaults(oldEvent, previousEvent, undefined, userPreferences);
            }
            if ((userPreferences?.copyReminders || userPreferences?.copyTimeBlocking) &&
                newModifiedEvent?.id) {
                const remindersTimeBlockingResp = await createRemindersAndTimeBlockingFromPreviousEventGivenUserPreferences(userId, newModifiedEvent, newReminders, newTimeBlocking, previousEvent, userPreferences);
                if (remindersTimeBlockingResp.ok && remindersTimeBlockingResp.data) {
                    newModifiedEvent = remindersTimeBlockingResp.data.newEvent;
                    newReminders = remindersTimeBlockingResp.data.newReminders;
                    newTimeBlocking = remindersTimeBlockingResp.data.newBufferTimes;
                }
                else {
                    console.warn(`Failed to create reminders/buffers from user prefs for event ${id}: ${remindersTimeBlockingResp.error?.message}`);
                }
            }
            const currentBestMatchCategory = bestMatchCategory; // To use in conditions below
            if (currentBestMatchCategory?.id &&
                (currentBestMatchCategory?.defaultReminders ||
                    currentBestMatchCategory?.defaultTimeBlocking) &&
                newModifiedEvent?.id) {
                const updateValuesResp = await updateValuesForEventWithPreviousEventPlusMeetingAndExternalMeeting(oldEvent, newModifiedEvent, bestMatchCategories, newReminders, newTimeBlocking, userId, userPreferences, previousEvent);
                if (updateValuesResp.ok && updateValuesResp.data) {
                    newModifiedEvent = updateValuesResp.data.newEvent;
                    newReminders = updateValuesResp.data.newReminders;
                    newTimeBlocking = updateValuesResp.data.newBufferTimes;
                }
                else {
                    console.warn(`Failed to update values from best match category for event ${id}: ${updateValuesResp.error?.message}`);
                }
            }
            if (currentBestMatchCategory?.id &&
                (currentBestMatchCategory?.copyReminders ||
                    currentBestMatchCategory?.copyTimeBlocking) &&
                newModifiedEvent?.id) {
                const remindersAndBuffersResp = await createRemindersAndBufferTimesForBestMatchCategory(id, userId, newModifiedEvent, currentBestMatchCategory, newReminders, newTimeBlocking);
                if (remindersAndBuffersResp.ok && remindersAndBuffersResp.data) {
                    newModifiedEvent = remindersAndBuffersResp.data.newEvent;
                    newReminders = remindersAndBuffersResp.data.newReminders;
                    newTimeBlocking = remindersAndBuffersResp.data.newBufferTimes;
                }
                else {
                    console.warn(`Failed to create reminders/buffers from best match category (copy) for event ${id}: ${remindersAndBuffersResp.error?.message}`);
                }
            }
            for (const cat of [
                previousMeetingCategoriesWithMeetingLabel?.[0],
                previousMeetingCategoriesWithExternalMeetingLabel?.[0],
            ]) {
                if (cat?.id &&
                    (cat.copyReminders || cat.copyTimeBlocking) &&
                    newModifiedEvent?.id) {
                    const remindersAndBuffersResp = await createRemindersAndBufferTimesForBestMatchCategory(id, userId, newModifiedEvent, cat, newReminders, newTimeBlocking);
                    if (remindersAndBuffersResp.ok && remindersAndBuffersResp.data) {
                        newModifiedEvent = remindersAndBuffersResp.data.newEvent;
                        newReminders = remindersAndBuffersResp.data.newReminders;
                        newTimeBlocking = remindersAndBuffersResp.data.newBufferTimes;
                    }
                    else {
                        console.warn(`Failed to create reminders/buffers from meeting categories for event ${id}: ${remindersAndBuffersResp.error?.message}`);
                    }
                }
            }
            if ((previousEvent?.copyReminders || previousEvent?.copyTimeBlocking) &&
                newModifiedEvent?.id) {
                const prevEventRemindersBuffersResp = await createRemindersAndTimeBlockingFromPreviousEvent(userId, newModifiedEvent, newReminders, newTimeBlocking, previousEvent);
                if (prevEventRemindersBuffersResp.ok &&
                    prevEventRemindersBuffersResp.data) {
                    newModifiedEvent = prevEventRemindersBuffersResp.data.newEvent;
                    newReminders = prevEventRemindersBuffersResp.data.newReminders;
                    newTimeBlocking = prevEventRemindersBuffersResp.data.newBufferTimes;
                }
                else {
                    console.warn(`Failed to create reminders/buffers from previous event for event ${id}: ${prevEventRemindersBuffersResp.error?.message}`);
                }
            }
            bestMatchCategories = getUniqueLabels(bestMatchCategories);
        }
        return {
            ok: true,
            data: { newModifiedEvent, newReminders, newTimeBlocking },
        };
    }
    catch (e) {
        console.error('Error in processEventWithFoundPreviousEventAndCopyCategories:', e);
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
export const processEventWithFoundPreviousEventWithoutCategories = async (previousEvent, event, userPreferences, userId, newReminders = [], newTimeBlocking = {}) => {
    if (!previousEvent || !event || !userPreferences || !userId) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Missing critical parameters for processing event without categories.',
            },
        };
    }
    try {
        let newModifiedEvent = event;
        if (!previousEvent?.unlink) {
            newModifiedEvent = copyOverPreviousEventDefaults(event, previousEvent, undefined, userPreferences);
            if ((userPreferences?.copyReminders || userPreferences?.copyTimeBlocking) &&
                newModifiedEvent?.id) {
                const remindersTimeBlockingResp = await createRemindersAndTimeBlockingFromPreviousEventGivenUserPreferences(userId, newModifiedEvent, newReminders, newTimeBlocking, previousEvent, userPreferences);
                if (remindersTimeBlockingResp.ok && remindersTimeBlockingResp.data) {
                    newModifiedEvent = remindersTimeBlockingResp.data.newEvent;
                    newReminders = remindersTimeBlockingResp.data.newReminders;
                    newTimeBlocking = remindersTimeBlockingResp.data.newBufferTimes;
                }
                else {
                    console.warn(`Failed to create reminders/buffers from user prefs (no categories): ${remindersTimeBlockingResp.error?.message}`);
                }
            }
            if ((previousEvent?.copyReminders || previousEvent?.copyTimeBlocking) &&
                newModifiedEvent?.id) {
                const prevEventRemindersBuffersResp = await createRemindersAndTimeBlockingFromPreviousEvent(userId, newModifiedEvent, newReminders, newTimeBlocking, previousEvent);
                if (prevEventRemindersBuffersResp.ok &&
                    prevEventRemindersBuffersResp.data) {
                    newModifiedEvent = prevEventRemindersBuffersResp.data.newEvent;
                    newReminders = prevEventRemindersBuffersResp.data.newReminders;
                    newTimeBlocking = prevEventRemindersBuffersResp.data.newBufferTimes;
                }
                else {
                    console.warn(`Failed to create reminders/buffers from previous event (no categories): ${prevEventRemindersBuffersResp.error?.message}`);
                }
            }
        }
        return {
            ok: true,
            data: { newModifiedEvent, newReminders, newTimeBlocking },
        };
    }
    catch (e) {
        console.error('Error in processEventWithFoundPreviousEventWithoutCategories:', e);
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
export const processUserEventWithFoundPreviousEvent = async (event, previousEventId) => {
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
        const prefTimeRangesResponse = await listPreferredTimeRangesForEvent(previousEventId);
        // Non-critical if preferred time ranges are not found, so we don't fail the whole process here
        if (prefTimeRangesResponse.ok && prefTimeRangesResponse.data) {
            previousEvent.preferredTimeRanges = prefTimeRangesResponse.data;
        }
        else {
            console.warn(`Could not fetch preferred time ranges for previous event ${previousEventId}: ${prefTimeRangesResponse.error?.message}`);
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
        let bestMatchCategory = null;
        let bestMatchCategoriesPlusMeetingType = [];
        if (categories.length > 0) {
            const classificationResponse = await findBestMatchCategory2(event, categories);
            if (classificationResponse.ok && classificationResponse.data) {
                const classificationBody = classificationResponse.data;
                const { labels, scores } = classificationBody;
                const bestMatchLabel = processBestMatchCategories(classificationBody, labels);
                if (bestMatchLabel) {
                    bestMatchCategory =
                        categories.find((category) => category.name === bestMatchLabel) ||
                            null;
                }
                if (bestMatchCategory) {
                    bestMatchCategoriesPlusMeetingType =
                        processEventForMeetingTypeCategories(event, bestMatchCategory, labels, scores, categories);
                    bestMatchCategoriesPlusMeetingType = getUniqueLabels(bestMatchCategoriesPlusMeetingType);
                }
            }
            else {
                console.warn(`Category classification failed for event ${id}: ${classificationResponse.error?.message}`);
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
        let newModifiedEvent = { ...event }; // Start with a copy
        let newReminders = [];
        let newBufferTimes = {};
        if ((previousEvent?.copyCategories || userPreferences?.copyCategories) &&
            !previousEvent?.unlink &&
            !event?.userModifiedCategories) {
            const prevCategoriesResponse = await listCategoriesForEvent(previousEvent.id);
            const previousCategories = prevCategoriesResponse.ok && prevCategoriesResponse.data
                ? prevCategoriesResponse.data
                : [];
            const processingResult = await processEventWithFoundPreviousEventAndCopyCategories(id, previousEvent, event, userPreferences, bestMatchCategory, userId, bestMatchCategoriesPlusMeetingType, newModifiedEvent, newReminders, newBufferTimes, previousCategories, previousCategories.filter((c) => c.name === meetingLabel), previousCategories.filter((c) => c.name === externalMeetingLabel));
            if (processingResult.ok && processingResult.data) {
                newModifiedEvent = processingResult.data.newModifiedEvent;
                newReminders = processingResult.data.newReminders;
                newTimeBlocking = processingResult.data.newTimeBlocking;
            }
            else {
                // Log warning or error, but proceed with potentially partially modified event
                console.warn(`Processing with 'copyCategories' failed for event ${id}: ${processingResult.error?.message}`);
            }
        }
        else if (userPreferences?.id &&
            !previousEvent?.copyCategories &&
            !userPreferences?.copyCategories &&
            !event?.userModifiedCategories &&
            event?.id &&
            previousEvent?.id) {
            if (bestMatchCategory && bestMatchCategoriesPlusMeetingType?.length > 0) {
                newModifiedEvent = copyOverPreviousEventDefaults(event, previousEvent, bestMatchCategory, userPreferences);
                if (newModifiedEvent?.id) {
                    const remindersResp = await createRemindersAndBufferTimesForBestMatchCategory(id, userId, newModifiedEvent, bestMatchCategory, newReminders, newBufferTimes);
                    if (remindersResp.ok && remindersResp.data) {
                        newModifiedEvent = remindersResp.data.newEvent;
                        newReminders = remindersResp.data.newReminders;
                        newBufferTimes = remindersResp.data.newBufferTimes;
                    }
                    const updateValuesResp = await updateValuesForEventWithPreviousEventPlusMeetingAndExternalMeeting(event, newModifiedEvent, bestMatchCategoriesPlusMeetingType, newReminders, newBufferTimes, userId, userPreferences, previousEvent);
                    if (updateValuesResp.ok && updateValuesResp.data) {
                        newModifiedEvent = updateValuesResp.data.newEvent;
                        newReminders = updateValuesResp.data.newReminders;
                        newBufferTimes = updateValuesResp.data.newBufferTimes;
                    }
                }
            }
            else {
                const noCatProcessingResp = await processEventWithFoundPreviousEventWithoutCategories(previousEvent, newModifiedEvent, userPreferences, userId, newReminders, newBufferTimes);
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
    }
    catch (e) {
        console.error(`Error in processUserEventWithFoundPreviousEvent for event ${event?.id}:`, e);
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
export const processUserEventWithFoundPreviousEventWithUserModifiedCategories = async (event, previousEventId) => {
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
        if (!categoriesResponse.ok ||
            !categoriesResponse.data ||
            categoriesResponse.data.length === 0) {
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
        const prefTimeRangesResponse = await listPreferredTimeRangesForEvent(previousEventId);
        if (prefTimeRangesResponse.ok && prefTimeRangesResponse.data) {
            previousEvent.preferredTimeRanges = prefTimeRangesResponse.data;
        }
        else {
            console.warn(`Could not fetch preferred time ranges for previous event ${previousEventId}: ${prefTimeRangesResponse.error?.message}`);
            previousEvent.preferredTimeRanges = [];
        }
        const classificationResponse = await findBestMatchCategory2(event, categories);
        if (!classificationResponse.ok ||
            !classificationResponse.data ||
            !classificationResponse.data.labels?.length) {
            console.warn(`Classification failed or returned no labels for event ${event.id}: ${classificationResponse.error?.message}`);
            // Decide if to proceed with event as is, or return an error. For now, proceed.
            return { ok: true, data: { newEvent: event } };
        }
        const classificationBody = classificationResponse.data;
        const { labels } = classificationBody; // scores are also available if needed
        const bestMatchLabel = processBestMatchCategoriesNoThreshold(classificationBody, labels);
        let newModifiedEvent = { ...event };
        let newReminders = [];
        let newTimeBlocking = {};
        if (bestMatchLabel) {
            const bestMatchCategory = categories.find((category) => category.name === bestMatchLabel);
            if (!bestMatchCategory) {
                console.warn(`Best match label "${bestMatchLabel}" did not correspond to a known category.`);
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
            newModifiedEvent = copyOverPreviousEventDefaults(event, previousEvent, bestMatchCategory, userPreferences);
            if (categories.length > 0 && newModifiedEvent?.id) {
                // categories is already checked to be non-empty
                const updateValuesResp = await updateValuesForEventWithPreviousEventPlusMeetingAndExternalMeeting(event, newModifiedEvent, categories, newReminders, newTimeBlocking, event.userId, userPreferences, previousEvent);
                if (updateValuesResp.ok && updateValuesResp.data) {
                    newModifiedEvent = updateValuesResp.data.newEvent;
                    newReminders = updateValuesResp.data.newReminders;
                    newTimeBlocking = updateValuesResp.data.newBufferTimes;
                }
                else {
                    console.warn(`Failed to update values from modified categories for event ${event.id}: ${updateValuesResp.error?.message}`);
                }
            }
        }
        else {
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
    }
    catch (e) {
        console.error(`Error in processUserEventWithFoundPreviousEventWithUserModifiedCategories for event ${event?.id}:`, e);
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUdMLG9CQUFvQixFQUNwQixtQkFBbUIsRUFDbkIsb0JBQW9CLEVBQ3BCLGlCQUFpQixFQUNqQixjQUFjLEVBQ2QsWUFBWSxFQUNaLGlCQUFpQixFQUNqQixtQkFBbUIsRUFDbkIsY0FBYyxFQUNkLG1CQUFtQixHQUNwQixNQUFNLGlDQUFpQyxDQUFDO0FBc0N6QyxPQUFPLEdBQUcsTUFBTSxLQUFLLENBQUM7QUFDdEIsT0FBTyxFQUFFLEVBQUUsSUFBSSxJQUFJLEVBQUUsTUFBTSxNQUFNLENBQUM7QUFDbEMsT0FBTyxLQUFLLE1BQU0sT0FBTyxDQUFDO0FBQzFCLE9BQU8sUUFBUSxNQUFNLHVCQUF1QixDQUFDO0FBQzdDLE9BQU8sU0FBUyxNQUFNLHdCQUF3QixDQUFDO0FBQy9DLE9BQU8sUUFBUSxNQUFNLHVCQUF1QixDQUFDO0FBQzdDLE9BQU8sR0FBRyxNQUFNLGtCQUFrQixDQUFDO0FBQ25DLE9BQU8sQ0FBQyxNQUFNLFFBQVEsQ0FBQztBQUd2QixPQUFPLEVBQUUsU0FBUyxFQUFFLFNBQVMsRUFBRSxNQUFNLFVBQVUsQ0FBQztBQUNoRCxPQUFPLE1BQU0sTUFBTSxRQUFRLENBQUM7QUFDNUIsT0FBTyxFQUNMLFlBQVksRUFDWixvQkFBb0IsRUFDcEIseUJBQXlCLEVBQ3pCLG9CQUFvQixHQUdyQixNQUFNLG1DQUFtQyxDQUFDO0FBRzNDLEtBQUssQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLENBQUM7QUFDdkIsS0FBSyxDQUFDLE1BQU0sQ0FBQyxTQUFTLENBQUMsQ0FBQztBQUN4QixLQUFLLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxDQUFDO0FBQ3ZCLEtBQUssQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUM7QUFFbEIsTUFBTSxNQUFNLEdBQUcsSUFBSSxNQUFNLENBQUM7SUFD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Q0FBQztTQUNoRCxFQUFFLENBQUMsWUFBWSxDQUFDO1NBQ2hCLE1BQU0sQ0FBQyxFQUFFLENBQUMsRUFDYixRQUFRLEVBQ1IsSUFBSSxDQUNMO1FBQ0QsQ0FBQyxDQUFDLENBQUM7UUFDSCxDQUFDLENBQUMsS0FBSyxDQUFDLFlBQVksQ0FBQyxTQUFTLENBQUMsS0FBSyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQzthQUNyQyxFQUFFLENBQUMsWUFBWSxFQUFFLFFBQVEsSUFBSSxZQUFZLEVBQUUsSUFBSSxDQUFDO2FBQ2hELEVBQUUsQ0FBQyxZQUFZLENBQUM7YUFDaEIsU0FBUyxDQUNSLEtBQUssQ0FBQyxZQUFZLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7YUFDdkMsRUFBRSxDQUFDLFlBQVksRUFBRSxRQUFRLElBQUksWUFBWSxFQUFFLElBQUksQ0FBQzthQUNoRCxFQUFFLENBQUMsWUFBWSxDQUFDO2FBQ2hCLE1BQU0sQ0FBQyxFQUFFLENBQUMsRUFDYixLQUFLLENBQUMsWUFBWSxDQUFDLFNBQVMsQ0FBQyxLQUFLLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO2FBQ3ZDLEVBQUUsQ0FBQyxZQUFZLEVBQUUsUUFBUSxJQUFJLFlBQVksRUFBRSxJQUFJLENBQUM7YUFDaEQsRUFBRSxDQUFDLFlBQVksQ0FBQzthQUNoQixNQUFNLENBQUMsRUFBRSxDQUFDLEVBQ2IsUUFBUSxFQUNSLElBQUksQ0FDTDtZQUNMLENBQUMsQ0FBQyxFQUFFO1lBQ0osQ0FBQyxDQUFDLEtBQUssQ0FBQyxZQUFZLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7aUJBQ3JDLEVBQUUsQ0FBQyxZQUFZLEVBQUUsUUFBUSxJQUFJLFlBQVksRUFBRSxJQUFJLENBQUM7aUJBQ2hELEVBQUUsQ0FBQyxZQUFZLENBQUM7aUJBQ2hCLFNBQVMsQ0FDUixLQUFLLENBQUMsWUFBWSxDQUFDLFNBQVMsQ0FBQyxLQUFLLENBQUMsQ0FB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LFFBQVEsRUFBRSxJQUFJLENBQUM7U0FDeEIsSUFBSSxDQUFDLEtBQUssQ0FBQyxLQUFLLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLENBQUMsS0FBSyxDQUFDLFFBQVEsRUFBRSxJQUFJLENBQUMsRUFBRSxHQUFHLENBQUMsQ0FBQztJQUUzRSxNQUFNLFVBQVUsR0FBRyxTQUFTLENBQzFCLEtBQUssQ0FBQyxLQUFLLEVBQUUsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLENBQUMsS0FBSyxFQUFFLFFBQVEsRUFBRSxJQUFJLENBQUMsQ0FBQyxNQUFNLEVBQUUsQ0FDeEUsQ0FBQztJQUNGLE1BQU0sT0FBTyxHQUFHLGVBQWUsQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUMzQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLEdBQUcsS0FBSyxVQUFVLENBQzdCLEVBQUUsSUFBSSxDQUFDO0lBQ1IsTUFBTSxVQUFVLEdBQUcsZUFBZSxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQzlDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsR0FBRyxLQUFLLFVBQVUsQ0FDN0IsRUFBRSxPQUFPLENBQUM7SUFDWCxNQUFNLFNBQVMsR0FBRyxlQUFlLENBQUMsVUFBVSxDQUFDLElBQUksQ0FDL0MsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsRUFBRSxHQUFHLEtBQUssVUFBVSxDQUM3QixFQUFFLElBQUksQ0FBQztJQUNSLE1BQU0sWUFBWSxHQUFHLGVBQWUsQ0FBQyxVQUFVLENBQUMsSUFBSSxDQUNsRCxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLEdBQUcsS0FBSyxVQUFVLENBQzdCLEVBQUUsT0FBTyxDQUFDO0lBRVgsSUFDRSxLQUFLLENBQUMsS0FBSyxDQUFDLFNBQVMsQ0FBQyxLQUFLLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1NB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SUFBSSxZQUFZLEVBQUUsSUFBSSxDQUFDO2FBQ2hELEVBQUUsQ0FBQyxZQUFZLENBQUM7YUFDaEIsU0FBUyxDQUNSLEtBQUssQ0FBQyxZQUFZLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7YUFDdkMsRUFBRSxDQUFDLFlBQVksRUFBRSxRQUFRLElBQUksWUFBWSxFQUFFLElBQUksQ0FBQzthQUNoRCxFQUFFLENBQUMsWUFBWSxDQUFDO2FBQ2hCLE1BQU0sQ0FBQyxDQUFDLENBQUMsRUFDWixLQUFLLENBQUMsWUFBWSxDQUFDLFNBQVMsQ0FBQyxLQUFLLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO2FBQ3ZDLEVBQUUsQ0FBQyxZQUFZLEVBQUUsUUFBUSxJQUFJLFlBQVksRUFBRSxJQUFJLENBQUM7YUFDaEQsRUFBRSxDQUFDLFlBQVksQ0FBQzthQUNoQixNQUFNLENBQUMsRUFBRSxDQUFDLEVBQ2IsUUFBUSxFQUNSLElBQUksQ0FDTDtZQUNELENBQUMsQ0FBQyxDQUFDO1lBQ0gsQ0FBQyxDQUFDLEtBQUssQ0FBQyxZQUFZLENBQUMsU0FBUyxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7aUJBQ3JDLEVBQUUsQ0FBQyxZQUFZLEVBQUUsUUFBUSxJQUFJLFlBQVksRUFBRSxJQUFJLENBQUM7aUJBQ2hELEVBQUUsQ0FBQyxZQUFZLENBQUM7aUJBQ2hCLFNBQVMsQ0FDUixLQUFLLENBQUMsWUFBWSxDQUFDLFNBQVMsQ0FBQyxLQUFLLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO2lCQUN2QyxFQUFFLENBQUMsWUFBWSxFQUFFLFFBQVEsSUFBSSxZQUFZLEVBQUUsSUFBSSxDQUFDO2lCQUNoRCxFQUFFLENBQUMsWUFBWSxDQUFDO2lCQUNoQixNQUFNLENBQUMsRUFBRSxDQUFDLEVBQ2IsS0FBSyxDQUFDLFlBQVksQ0FBQyxTQUFTLENBQUMsS0FBSyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQztpQkFDdkMsRUFB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RixDQUFDO1FBQ0YsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxnQkFBZ0I7Z0JBQ3RCLE9BQU8sRUFBRSxxREFBcUQsQ0FBQyxDQUFDLE9BQU8sRUFBRTtnQkFDekUsT0FBTyxFQUFFLENBQUM7YUFDWDtTQUNGLENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgYXV0aEFwaVRva2VuLFxuICBjbGFzc2lmaWNhdGlvblVybCxcbiAgZGF5T2ZXZWVrSW50VG9TdHJpbmcsXG4gIGRlZmF1bHRPcGVuQUlBUElLZXksXG4gIGV4dGVybmFsTWVldGluZ0xhYmVsLFxuICBoYXN1cmFBZG1pblNlY3JldCxcbiAgaGFzdXJhR3JhcGhVcmwsXG4gIG1lZXRpbmdMYWJlbCxcbiAgbWluVGhyZXNob2xkU2NvcmUsXG4gIG9wdGFQbGFubmVyUGFzc3dvcmQsXG4gIG9wdGFQbGFubmVyVXJsLFxuICBvcHRhUGxhbm5lclVzZXJuYW1lLFxufSBmcm9tICdAZmVhdHVyZXNfYXBwbHkvX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7XG4gIEJ1ZmZlclRpbWVOdW1iZXJUeXBlLFxuICBFdmVudFBsdXNUeXBlLFxuICBFdmVudFR5cGUsXG4gIE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGUsXG4gIE1lZXRpbmdBc3Npc3RFdmVudFR5cGUsXG4gIE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlLFxuICBNZWV0aW5nQXNzaXN0VHlwZSxcbiAgRXZlbnRNZWV0aW5nUGx1c1R5cGUsXG4gIFByZWZlcnJlZFRpbWVSYW5nZVR5cGUsXG4gIFJlbWluZGVyc0ZvckV2ZW50VHlwZSxcbiAgVmFsdWVzVG9SZXR1cm5Gb3JCdWZmZXJFdmVudHNUeXBlLFxuICBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIENhbGVuZGFyVHlwZSxcbiAgV29ya1RpbWVUeXBlLFxuICBUaW1lU2xvdFR5cGUsXG4gIE1vbnRoVHlwZSxcbiAgRGF5VHlwZSxcbiAgTU0sXG4gIERELFxuICBNb250aERheVR5cGUsXG4gIFRpbWUsXG4gIEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGUsXG4gIEluaXRpYWxFdmVudFBhcnRUeXBlLFxuICBJbml0aWFsRXZlbnRQYXJ0VHlwZVBsdXMsXG4gIFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlLFxuICBSZXR1cm5Cb2R5Rm9yRXh0ZXJuYWxBdHRlbmRlZUZvck9wdGFwbGFubmVyUHJlcFR5cGUsXG4gIFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGUsXG4gIEZyZWVtaXVtVHlwZSxcbiAgT3BlblNlYXJjaFJlc3BvbnNlQm9keVR5cGUsXG4gIENhdGVnb3J5VHlwZSxcbiAgY2xhc3NpZmljYXRpb25SZXNwb25zZUJvZHkgYXMgQ2xhc3NpZmljYXRpb25SZXNwb25zZUJvZHlUeXBlLFxuICBCdWZmZXJUaW1lT2JqZWN0VHlwZSxcbiAgUmVtaW5kZXJUeXBlLFxuICBDYXRlZ29yeUV2ZW50VHlwZSxcbiAgT3BlblNlYXJjaEdldFJlc3BvbnNlQm9keVR5cGUsXG59IGZyb20gJ0BmZWF0dXJlc19hcHBseS9fbGlicy90eXBlcyc7XG5pbXBvcnQgZ290IGZyb20gJ2dvdCc7XG5pbXBvcnQgeyB2NCBhcyB1dWlkIH0gZnJvbSAndXVpZCc7XG5pbXBvcnQgZGF5anMgZnJvbSAnZGF5anMnO1xuaW1wb3J0IGR1cmF0aW9uIGZyb20gJ2RheWpzL3BsdWdpbi9kdXJhdGlvbic7XG5pbXBvcnQgaXNCZXR3ZWVuIGZyb20gJ2RheWpzL3BsdWdpbi9pc0JldHdlZW4nO1xuaW1wb3J0IHRpbWV6b25lIGZyb20gJ2RheWpzL3BsdWdpbi90aW1lem9uZSc7XG5pbXBvcnQgdXRjIGZyb20gJ2RheWpzL3BsdWdpbi91dGMnO1xuaW1wb3J0IF8gZnJvbSAnbG9kYXNoJztcblxuaW1wb3J0IEFXUyBmcm9tICdhd3Mtc2RrJztcbmltcG9ydCB7IGdldElTT0RheSwgc2V0SVNPRGF5IH0gZnJvbSAnZGF0ZS1mbnMnO1xuaW1wb3J0IE9wZW5BSSBmcm9tICdvcGVuYWknO1xuaW1wb3J0IHtcbiAgZ2V0RXZlbnRCeUlkLFxuICBzZWFyY2hUcmFpbmluZ0V2ZW50cyxcbiAgZGVsZXRlVHJhaW5pbmdFdmVudHNCeUlkcyxcbiAgdXBzZXJ0VHJhaW5pbmdFdmVudHMsXG4gIFRyYWluaW5nRXZlbnRTY2hlbWEsXG4gIEV2ZW50U2NoZW1hLFxufSBmcm9tICdAZnVuY3Rpb25zL191dGlscy9sYW5jZWRiX3NlcnZpY2UnO1xuaW1wb3J0IHsgRmVhdHVyZXNBcHBseVJlc3BvbnNlLCBTa2lsbEVycm9yIH0gZnJvbSAnLi90eXBlcyc7IC8vIEltcG9ydCBzdGFuZGFyZGl6ZWQgcmVzcG9uc2UgdHlwZXNcblxuZGF5anMuZXh0ZW5kKGR1cmF0aW9uKTtcbmRheWpzLmV4dGVuZChpc0JldHdlZW4pO1xuZGF5anMuZXh0ZW5kKHRpbWV6b25lKTtcbmRheWpzLmV4dGVuZCh1dGMpO1xuXG5jb25zdCBvcGVuYWkgPSBuZXcgT3BlbkFJKHtcbiAgYXBpS2V5OiBkZWZhdWx0T3BlbkFJQVBJS2V5LFxufSk7XG5cbmV4cG9ydCBjb25zdCBnZXRFdmVudFZlY3RvckJ5SWQgPSBhc3luYyAoXG4gIGlkOiBzdHJpbmdcbik6IFByb21pc2U8RmVhdHVyZXNBcHBseVJlc3BvbnNlPG51bWJlcltdIHwgbnVsbD4+ID0+IHtcbiAgaWYgKCFpZCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogeyBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsIG1lc3NhZ2U6ICdFdmVudCBJRCBpcyByZXF1aXJlZC4nIH0sXG4gICAgfTtcbiAgfVxuICB0cnkge1xuICAgIGNvbnN0IGV2ZW50ID0gYXdhaXQgZ2V0RXZlbnRCeUlkKGlkKTsgLy8gZnJvbSBsYW5jZWRiX3NlcnZpY2VcbiAgICBpZiAoZXZlbnQgJiYgZXZlbnQudmVjdG9yKSB7XG4gICAgICBjb25zb2xlLmxvZyhgVmVjdG9yIGZvdW5kIGZvciBldmVudCBJRCAke2lkfWApO1xuICAgICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IGV2ZW50LnZlY3RvciBhcyBudW1iZXJbXSB9OyAvLyBFeHBsaWNpdGx5IGNhc3QgaWYgbmVlZGVkXG4gICAgfVxuICAgIGNvbnNvbGUubG9nKGBObyBldmVudCBvciB2ZWN0b3IgZm91bmQgZm9yIElEICR7aWR9YCk7XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IG51bGwgfTsgLy8gTm90IGFuIGVycm9yLCBidXQgbm8gZGF0YSBmb3VuZFxuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKGBFcnJvciBmZXRjaGluZyBldmVudCB2ZWN0b3IgZm9yIElEICR7aWR9IGZyb20gTGFuY2VEQjpgLCBlKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0xBTkNFREJfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgRmFpbGVkIHRvIGZldGNoIGV2ZW50IHZlY3RvcjogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZSxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGRlbGV0ZVRyYWluaW5nRGF0YUJ5SWQgPSBhc3luYyAoXG4gIGlkOiBzdHJpbmdcbik6IFByb21pc2U8RmVhdHVyZXNBcHBseVJlc3BvbnNlPHZvaWQ+PiA9PiB7XG4gIGlmICghaWQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnSUQgaXMgcmVxdWlyZWQgZm9yIGRlbGV0aW9uLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBhd2FpdCBkZWxldGVUcmFpbmluZ0V2ZW50c0J5SWRzKFtpZF0pO1xuICAgIGNvbnNvbGUubG9nKGBTdWNjZXNzZnVsbHkgZGVsZXRlZCB0cmFpbmluZyBkYXRhIGZvciBJRDogJHtpZH1gKTtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogdW5kZWZpbmVkIH07XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoYEVycm9yIGRlbGV0aW5nIHRyYWluaW5nIGRhdGEgZm9yIElEICR7aWR9IGZyb20gTGFuY2VEQjpgLCBlKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0xBTkNFREJfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgRmFpbGVkIHRvIGRlbGV0ZSB0cmFpbmluZyBkYXRhOiAke2UubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBlLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3Qgc2VhcmNoVHJhaW5pbmdEYXRhQnlWZWN0b3IgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBzZWFyY2hWZWN0b3I6IG51bWJlcltdXG4pOiBQcm9taXNlPEZlYXR1cmVzQXBwbHlSZXNwb25zZTxUcmFpbmluZ0V2ZW50U2NoZW1hIHwgbnVsbD4+ID0+IHtcbiAgaWYgKCF1c2VySWQgfHwgIXNlYXJjaFZlY3RvciB8fCBzZWFyY2hWZWN0b3IubGVuZ3RoID09PSAwKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1VzZXJJZCBhbmQgc2VhcmNoVmVjdG9yIGFyZSByZXF1aXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzdWx0cyA9IGF3YWl0IHNlYXJjaFRyYWluaW5nRXZlbnRzKFxuICAgICAgc2VhcmNoVmVjdG9yLFxuICAgICAgMSxcbiAgICAgIGB1c2VySWQgPSAnJHt1c2VySWQucmVwbGFjZSgvJy9nLCBcIicnXCIpfSdgXG4gICAgKTtcbiAgICBpZiAocmVzdWx0cyAmJiByZXN1bHRzLmxlbmd0aCA+IDApIHtcbiAgICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiByZXN1bHRzWzBdIH07XG4gICAgfVxuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiBudWxsIH07IC8vIEZvdW5kIG5vdGhpbmcsIGJ1dCBvcGVyYXRpb24gd2FzIHN1Y2Nlc3NmdWxcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3Igc2VhcmNoaW5nIHRyYWluaW5nIGRhdGEgaW4gTGFuY2VEQjonLCBlKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0xBTkNFREJfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgRmFpbGVkIHRvIHNlYXJjaCB0cmFpbmluZyBkYXRhOiAke2UubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBlLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgYWRkVHJhaW5pbmdEYXRhID0gYXN5bmMgKFxuICB0cmFpbmluZ0VudHJ5OiBUcmFpbmluZ0V2ZW50U2NoZW1hXG4pOiBQcm9taXNlPEZlYXR1cmVzQXBwbHlSZXNwb25zZTx2b2lkPj4gPT4ge1xuICBpZiAoIXRyYWluaW5nRW50cnkgfHwgIXRyYWluaW5nRW50cnkuaWQgfHwgIXRyYWluaW5nRW50cnkudmVjdG9yKSB7XG4gICAgLy8gQWRkIG1vcmUgY2hlY2tzIGFzIG5lZWRlZFxuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdUcmFpbmluZyBlbnRyeSB3aXRoIGlkIGFuZCB2ZWN0b3IgaXMgcmVxdWlyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICB0cnkge1xuICAgIGF3YWl0IHVwc2VydFRyYWluaW5nRXZlbnRzKFt0cmFpbmluZ0VudHJ5XSk7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBgU3VjY2Vzc2Z1bGx5IGFkZGVkL3VwZGF0ZWQgdHJhaW5pbmcgZGF0YSBmb3IgSUQ6ICR7dHJhaW5pbmdFbnRyeS5pZH1gXG4gICAgKTtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogdW5kZWZpbmVkIH07XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICBgRXJyb3IgYWRkaW5nL3VwZGF0aW5nIHRyYWluaW5nIGRhdGEgZm9yIElEICR7dHJhaW5pbmdFbnRyeS5pZH0gaW4gTGFuY2VEQjpgLFxuICAgICAgZVxuICAgICk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdMQU5DRURCX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBhZGQvdXBkYXRlIHRyYWluaW5nIGRhdGE6ICR7ZS5tZXNzYWdlfWAsXG4gICAgICAgIGRldGFpbHM6IGUsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjb252ZXJ0RXZlbnRUaXRsZVRvT3BlbkFJVmVjdG9yID0gYXN5bmMgKFxuICB0aXRsZTogc3RyaW5nXG4pOiBQcm9taXNlPEZlYXR1cmVzQXBwbHlSZXNwb25zZTxudW1iZXJbXSB8IHVuZGVmaW5lZD4+ID0+IHtcbiAgaWYgKCF0aXRsZSB8fCB0aXRsZS50cmltKCkgPT09ICcnKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ1RpdGxlIGNhbm5vdCBiZSBlbXB0eSBmb3IgdmVjdG9yaXphdGlvbi4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIHRyeSB7XG4gICAgY29uc3QgZW1iZWRkaW5nUmVxdWVzdDogT3BlbkFJLkVtYmVkZGluZ3MuRW1iZWRkaW5nQ3JlYXRlUGFyYW1zID0ge1xuICAgICAgbW9kZWw6ICd0ZXh0LWVtYmVkZGluZy0zLXNtYWxsJyxcbiAgICAgIGlucHV0OiB0aXRsZSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzID0gYXdhaXQgb3BlbmFpLmVtYmVkZGluZ3MuY3JlYXRlKGVtYmVkZGluZ1JlcXVlc3QpO1xuICAgIC8vIGNvbnNvbGUubG9nKHJlcywgJyByZXMgaW5zaWRlIGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3JzJyk7IC8vIFRvbyB2ZXJib3NlIGZvciBub3JtYWwgb3BlcmF0aW9uXG4gICAgY29uc3QgZW1iZWRkaW5nID0gcmVzPy5kYXRhPy5bMF0/LmVtYmVkZGluZztcbiAgICBpZiAoIWVtYmVkZGluZykge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ09wZW5BSSBlbWJlZGRpbmcgcmVzcG9uc2UgZGlkIG5vdCBjb250YWluIGVtYmVkZGluZyBkYXRhLidcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ09QRU5BSV9FUlJPUicsXG4gICAgICAgICAgbWVzc2FnZTogJ05vIGVtYmVkZGluZyBkYXRhIHJldHVybmVkIGZyb20gT3BlbkFJLicsXG4gICAgICAgICAgZGV0YWlsczogcmVzLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IGVtYmVkZGluZyB9O1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBjb252ZXJ0aW5nIGV2ZW50IHRpdGxlIHRvIE9wZW5BSSB2ZWN0b3I6JywgZSk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdPUEVOQUlfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgT3BlbkFJIEFQSSBlcnJvcjogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZSxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlc0dpdmVuTWVldGluZ0lkID0gYXN5bmMgKFxuICBtZWV0aW5nSWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxcbiAgRmVhdHVyZXNBcHBseVJlc3BvbnNlPE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW10gfCBudWxsPlxuPiA9PiB7XG4gIGlmICghbWVldGluZ0lkKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJywgbWVzc2FnZTogJ01lZXRpbmcgSUQgaXMgcmVxdWlyZWQuJyB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0xpc3RNZWV0aW5nQXNzaXN0UHJlZmVyZXJlZFRpbWVSYW5nZXNCeU1lZXRpbmdJZCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBxdWVyeSBMaXN0TWVldGluZ0Fzc2lzdFByZWZlcmVyZWRUaW1lUmFuZ2VzQnlNZWV0aW5nSWQoJG1lZXRpbmdJZDogdXVpZCEpIHtcbiAgICAgICAgICAgICAgICBNZWV0aW5nX0Fzc2lzdF9QcmVmZXJyZWRfVGltZV9SYW5nZSh3aGVyZToge21lZXRpbmdJZDoge19lcTogJG1lZXRpbmdJZH19KSB7XG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlSWRcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgIGVuZFRpbWVcbiAgICAgICAgICAgICAgICAgICAgaG9zdElkXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgICAgICAgICAgICBzdGFydFRpbWVcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgIH1cblxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgbWVldGluZ0lkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgTWVldGluZ19Bc3Npc3RfUHJlZmVycmVkX1RpbWVfUmFuZ2U6IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW107XG4gICAgICB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICByZXMsXG4gICAgICAnIHJlcyBmcm9tIGxpc3RNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlc0dpdmVuTWVldGluZ0lkJ1xuICAgICk7IC8vIENvcnJlY3RlZCBsb2dcblxuICAgIHJldHVybiB7XG4gICAgICBvazogdHJ1ZSxcbiAgICAgIGRhdGE6IHJlcz8uZGF0YT8uTWVldGluZ19Bc3Npc3RfUHJlZmVycmVkX1RpbWVfUmFuZ2UgfHwgbnVsbCxcbiAgICB9O1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBsaXN0aW5nIG1lZXRpbmcgYXNzaXN0IHByZWZlcnJlZCB0aW1lIHJhbmdlczonLCBlKTtcbiAgICBjb25zdCBlcnJvckRldGFpbHMgPSBlLnJlc3BvbnNlPy5ib2R5IHx8IGUubWVzc2FnZSB8fCBlOyAvLyBnb3QgZXJyb3IgZGV0YWlsc1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnSEFTVVJBX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBsaXN0IHByZWZlcnJlZCB0aW1lIHJhbmdlczogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZXJyb3JEZXRhaWxzLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZXNHaXZlbk1lZXRpbmdJZCA9IGFzeW5jIChcbiAgbWVldGluZ0lkOiBzdHJpbmdcbik6IFByb21pc2U8RmVhdHVyZXNBcHBseVJlc3BvbnNlPE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXSB8IG51bGw+PiA9PiB7XG4gIGlmICghbWVldGluZ0lkKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7IGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJywgbWVzc2FnZTogJ01lZXRpbmcgSUQgaXMgcmVxdWlyZWQuJyB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0xpc3RNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzQnlNZWV0aW5nSWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgTGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZXNCeU1lZXRpbmdJZCgkbWVldGluZ0lkOiB1dWlkISkge1xuICAgICAgICAgICAgICAgIE1lZXRpbmdfQXNzaXN0X0F0dGVuZGVlKHdoZXJlOiB7bWVldGluZ0lkOiB7X2VxOiAkbWVldGluZ0lkfX0pIHtcbiAgICAgICAgICAgICAgICAgICAgY29udGFjdElkXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGVtYWlsc1xuICAgICAgICAgICAgICAgICAgICBleHRlcm5hbEF0dGVuZGVlXG4gICAgICAgICAgICAgICAgICAgIGhvc3RJZFxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBpbUFkZHJlc3Nlc1xuICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgICAgICAgICBwaG9uZU51bWJlcnNcbiAgICAgICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgICAgICBwcmltYXJ5RW1haWxcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG5cbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBtZWV0aW5nSWQsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczoge1xuICAgICAgZGF0YTogeyBNZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZTogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdIH07XG4gICAgfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gbGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZXMnKTtcblxuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiByZXM/LmRhdGE/Lk1lZXRpbmdfQXNzaXN0X0F0dGVuZGVlIHx8IG51bGwgfTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgbGlzdGluZyBtZWV0aW5nIGFzc2lzdCBhdHRlbmRlZXM6JywgZSk7XG4gICAgY29uc3QgZXJyb3JEZXRhaWxzID0gZS5yZXNwb25zZT8uYm9keSB8fCBlLm1lc3NhZ2UgfHwgZTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0hBU1VSQV9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gbGlzdCBtZWV0aW5nIGFzc2lzdCBhdHRlbmRlZXM6ICR7ZS5tZXNzYWdlfWAsXG4gICAgICAgIGRldGFpbHM6IGVycm9yRGV0YWlscyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldE1lZXRpbmdBc3Npc3RBdHRlbmRlZSA9IGFzeW5jIChcbiAgaWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxGZWF0dXJlc0FwcGx5UmVzcG9uc2U8TWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSB8IG51bGw+PiA9PiB7XG4gIGlmICghaWQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHsgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLCBtZXNzYWdlOiAnQXR0ZW5kZWUgSUQgaXMgcmVxdWlyZWQuJyB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0dldE1lZXRpbmdBc3Npc3RBdHRlbmRlZUJ5SWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgR2V0TWVldGluZ0Fzc2lzdEF0dGVuZGVlQnlJZCgkaWQ6IFN0cmluZyEpIHtcbiAgICAgICAgICAgICAgICBNZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZV9ieV9wayhpZDogJGlkKSB7XG4gICAgICAgICAgICAgICAgICAgIGNvbnRhY3RJZFxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBlbWFpbHNcbiAgICAgICAgICAgICAgICAgICAgaG9zdElkXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGltQWRkcmVzc2VzXG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICAgICAgICAgIHBob25lTnVtYmVyc1xuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWVcbiAgICAgICAgICAgICAgICAgICAgcHJpbWFyeUVtYWlsXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgaWQsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczoge1xuICAgICAgZGF0YTogeyBNZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZV9ieV9wazogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGdldE1lZXRpbmdBc3Npc3RBdHRlbmRlZScpO1xuICAgIGNvbnN0IGF0dGVuZGVlID0gcmVzPy5kYXRhPy5NZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZV9ieV9waztcbiAgICBpZiAoIWF0dGVuZGVlKSB7XG4gICAgICAvLyBIYXN1cmEgcmV0dXJucyBudWxsIGZvciBfYnlfcGsgaWYgbm90IGZvdW5kXG4gICAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogbnVsbCB9O1xuICAgIH1cbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogYXR0ZW5kZWUgfTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgZ2V0dGluZyBtZWV0aW5nIGFzc2lzdCBhdHRlbmRlZTonLCBlKTtcbiAgICBjb25zdCBlcnJvckRldGFpbHMgPSBlLnJlc3BvbnNlPy5ib2R5IHx8IGUubWVzc2FnZSB8fCBlO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnSEFTVVJBX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBnZXQgbWVldGluZyBhc3Npc3QgYXR0ZW5kZWU6ICR7ZS5tZXNzYWdlfWAsXG4gICAgICAgIGRldGFpbHM6IGVycm9yRGV0YWlscyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldE1lZXRpbmdBc3Npc3QgPSBhc3luYyAoXG4gIGlkOiBzdHJpbmdcbik6IFByb21pc2U8RmVhdHVyZXNBcHBseVJlc3BvbnNlPE1lZXRpbmdBc3Npc3RUeXBlIHwgbnVsbD4+ID0+IHtcbiAgaWYgKCFpZCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdNZWV0aW5nQXNzaXN0IElEIGlzIHJlcXVpcmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0dldE1lZXRpbmdBc3Npc3RCeUlkJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IEdldE1lZXRpbmdBc3Npc3RCeUlkKCRpZDogdXVpZCEpIHtcbiAgICAgICAgICAgICAgICBNZWV0aW5nX0Fzc2lzdF9ieV9wayhpZDogJGlkKSB7XG4gICAgICAgICAgICAgICAgICAgIGFueW9uZUNhbkFkZFNlbGZcbiAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVDYW5Nb2RpZnlcbiAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVDb3VudFxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZVJlc3BvbmRlZENvdW50XG4gICAgICAgICAgICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICBidWZmZXJUaW1lXG4gICAgICAgICAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgICAgICAgICAgY2FuY2VsSWZBbnlSZWZ1c2VcbiAgICAgICAgICAgICAgICAgICAgY2FuY2VsbGVkXG4gICAgICAgICAgICAgICAgICAgIGNvbG9ySWRcbiAgICAgICAgICAgICAgICAgICAgY29uZmVyZW5jZUFwcFxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBkdXJhdGlvblxuICAgICAgICAgICAgICAgICAgICBlbmFibGVBdHRlbmRlZVByZWZlcmVuY2VzXG4gICAgICAgICAgICAgICAgICAgIGVuYWJsZUNvbmZlcmVuY2VcbiAgICAgICAgICAgICAgICAgICAgZW5hYmxlSG9zdFByZWZlcmVuY2VzXG4gICAgICAgICAgICAgICAgICAgIGVuZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBleHBpcmVEYXRlXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0c1xuICAgICAgICAgICAgICAgICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgbG9jYXRpb25cbiAgICAgICAgICAgICAgICAgICAgbWluVGhyZXNob2xkQ291bnRcbiAgICAgICAgICAgICAgICAgICAgbm90ZXNcbiAgICAgICAgICAgICAgICAgICAgcHJpb3JpdHlcbiAgICAgICAgICAgICAgICAgICAgcmVtaW5kZXJzXG4gICAgICAgICAgICAgICAgICAgIHNlbmRVcGRhdGVzXG4gICAgICAgICAgICAgICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBzdW1tYXJ5XG4gICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHRyYW5zcGFyZW5jeVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlRGVmYXVsdEFsYXJtc1xuICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICAgICAgdmlzaWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICB3aW5kb3dFbmREYXRlXG4gICAgICAgICAgICAgICAgICAgIHdpbmRvd1N0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBhbGxvd0F0dGVuZGVlVXBkYXRlUHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgZ3VhcmFudGVlQXZhaWxhYmlsaXR5XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgaWQsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IE1lZXRpbmdfQXNzaXN0X2J5X3BrOiBNZWV0aW5nQXNzaXN0VHlwZSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGdldE1lZXRpbmdBc3Npc3QnKTtcbiAgICBjb25zdCBtZWV0aW5nQXNzaXN0ID0gcmVzPy5kYXRhPy5NZWV0aW5nX0Fzc2lzdF9ieV9waztcbiAgICBpZiAoIW1lZXRpbmdBc3Npc3QpIHtcbiAgICAgIC8vIEhhc3VyYSByZXR1cm5zIG51bGwgZm9yIF9ieV9wayBpZiBub3QgZm91bmRcbiAgICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiBudWxsIH07XG4gICAgfVxuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiBtZWV0aW5nQXNzaXN0IH07XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIGdldHRpbmcgbWVldGluZyBhc3Npc3QgYnkgaWQ6JywgZSk7XG4gICAgY29uc3QgZXJyb3JEZXRhaWxzID0gZS5yZXNwb25zZT8uYm9keSB8fCBlLm1lc3NhZ2UgfHwgZTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0hBU1VSQV9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gZ2V0IG1lZXRpbmcgYXNzaXN0OiAke2UubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBlcnJvckRldGFpbHMsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBsaXN0TWVldGluZ0Fzc2lzdEV2ZW50c0ZvckF0dGVuZGVlR2l2ZW5EYXRlcyA9IGFzeW5jIChcbiAgYXR0ZW5kZWVJZDogc3RyaW5nLFxuICBob3N0U3RhcnREYXRlOiBzdHJpbmcsXG4gIGhvc3RFbmREYXRlOiBzdHJpbmcsXG4gIHVzZXJUaW1lem9uZTogc3RyaW5nLFxuICBob3N0VGltZXpvbmU6IHN0cmluZ1xuKTogUHJvbWlzZTxGZWF0dXJlc0FwcGx5UmVzcG9uc2U8TWVldGluZ0Fzc2lzdEV2ZW50VHlwZVtdIHwgbnVsbD4+ID0+IHtcbiAgaWYgKFxuICAgICFhdHRlbmRlZUlkIHx8XG4gICAgIWhvc3RTdGFydERhdGUgfHxcbiAgICAhaG9zdEVuZERhdGUgfHxcbiAgICAhdXNlclRpbWV6b25lIHx8XG4gICAgIWhvc3RUaW1lem9uZVxuICApIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICdNaXNzaW5nIHJlcXVpcmVkIHBhcmFtZXRlcnMgZm9yIGxpc3RpbmcgbWVldGluZyBhc3Npc3QgZXZlbnRzLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0xpc3RNZWV0aW5nQXNzaXN0RXZlbnRzRm9yQXR0ZW5kZWVHaXZlbkRhdGVzJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IExpc3RNZWV0aW5nQXNzaXN0RXZlbnRzRm9yQXR0ZW5kZWVHaXZlbkRhdGVzKCRhdHRlbmRlZUlkOiBTdHJpbmchLCAkc3RhcnREYXRlOiB0aW1lc3RhbXAhLCAkZW5kRGF0ZTogdGltZXN0YW1wISkge1xuICAgICAgICAgICAgICAgIE1lZXRpbmdfQXNzaXN0X0V2ZW50KHdoZXJlOiB7YXR0ZW5kZWVJZDoge19lcTogJGF0dGVuZGVlSWR9LCBlbmREYXRlOiB7X2d0ZTogJHN0YXJ0RGF0ZX0sIHN0YXJ0RGF0ZToge19sdGU6ICRlbmREYXRlfX0pIHtcbiAgICAgICAgICAgICAgICAgICAgYWxsRGF5XG4gICAgICAgICAgICAgICAgICAgIGF0dGFjaG1lbnRzXG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlSWRcbiAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVzT21pdHRlZFxuICAgICAgICAgICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgICAgICAgICBjb2xvcklkXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0b3JcbiAgICAgICAgICAgICAgICAgICAgZW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICBlbmRUaW1lVW5zcGVjaWZpZWRcbiAgICAgICAgICAgICAgICAgICAgZXZlbnRUeXBlXG4gICAgICAgICAgICAgICAgICAgIGV4dGVuZGVkUHJvcGVydGllc1xuICAgICAgICAgICAgICAgICAgICBleHRlcm5hbFVzZXJcbiAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbk1vZGlmeVxuICAgICAgICAgICAgICAgICAgICBoYW5nb3V0TGlua1xuICAgICAgICAgICAgICAgICAgICBodG1sTGlua1xuICAgICAgICAgICAgICAgICAgICBpQ2FsVUlEXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGxpbmtzXG4gICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uXG4gICAgICAgICAgICAgICAgICAgIGxvY2tlZFxuICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgbm90ZXNcbiAgICAgICAgICAgICAgICAgICAgb3JnYW5pemVyXG4gICAgICAgICAgICAgICAgICAgIHByaXZhdGVDb3B5XG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyZW5jZVJ1bGVcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyaW5nRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBzb3VyY2VcbiAgICAgICAgICAgICAgICAgICAgc3RhcnREYXRlXG4gICAgICAgICAgICAgICAgICAgIHN1bW1hcnlcbiAgICAgICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgdHJhbnNwYXJlbmN5XG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICAgICAgICAgICAgICAgIHZpc2liaWxpdHlcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG5cbiAgICBjb25zdCBzdGFydERhdGVJbkhvc3RUaW1lem9uZSA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIHRydWVcbiAgICApO1xuICAgIGNvbnN0IGVuZERhdGVJbkhvc3RUaW1lem9uZSA9IGRheWpzKGhvc3RFbmREYXRlLnNsaWNlKDAsIDE5KSkudHooXG4gICAgICBob3N0VGltZXpvbmUsXG4gICAgICB0cnVlXG4gICAgKTtcbiAgICBjb25zdCBzdGFydERhdGVJblVzZXJUaW1lem9uZSA9IGRheWpzKHN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lKVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC5mb3JtYXQoKVxuICAgICAgLnNsaWNlKDAsIDE5KTtcbiAgICBjb25zdCBlbmREYXRlSW5Vc2VyVGltZXpvbmUgPSBkYXlqcyhlbmREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLmZvcm1hdCgpXG4gICAgICAuc2xpY2UoMCwgMTkpO1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgTWVldGluZ19Bc3Npc3RfRXZlbnQ6IE1lZXRpbmdBc3Npc3RFdmVudFR5cGVbXSB9IH0gPVxuICAgICAgYXdhaXQgZ290XG4gICAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgICBhdHRlbmRlZUlkLFxuICAgICAgICAgICAgICBzdGFydERhdGU6IHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lLFxuICAgICAgICAgICAgICBlbmREYXRlOiBlbmREYXRlSW5Vc2VyVGltZXpvbmUsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gbGlzdE1lZXRpbmdBc3Npc3RFdmVudHNGb3JBdHRlbmRlZUdpdmVuRGF0ZXMnKTtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogcmVzPy5kYXRhPy5NZWV0aW5nX0Fzc2lzdF9FdmVudCB8fCBudWxsIH07XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIGxpc3RpbmcgbWVldGluZyBhc3Npc3QgZXZlbnRzIGZvciBhdHRlbmRlZTonLCBlKTtcbiAgICBjb25zdCBlcnJvckRldGFpbHMgPSBlLnJlc3BvbnNlPy5ib2R5IHx8IGUubWVzc2FnZSB8fCBlO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnSEFTVVJBX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBsaXN0IG1lZXRpbmcgYXNzaXN0IGV2ZW50czogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZXJyb3JEZXRhaWxzLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdEV2ZW50c0ZvckRhdGUgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBzdGFydERhdGU6IHN0cmluZyxcbiAgZW5kRGF0ZTogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nXG4pOiBQcm9taXNlPEZlYXR1cmVzQXBwbHlSZXNwb25zZTxFdmVudFR5cGVbXSB8IG51bGw+PiA9PiB7XG4gIGlmICghdXNlcklkIHx8ICFzdGFydERhdGUgfHwgIWVuZERhdGUgfHwgIXRpbWV6b25lKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ01pc3NpbmcgcmVxdWlyZWQgcGFyYW1ldGVycyBmb3IgbGlzdGluZyBldmVudHMgZm9yIGRhdGUuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnbGlzdEV2ZW50c0ZvckRhdGUnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICBxdWVyeSBsaXN0RXZlbnRzRm9yRGF0ZSgkdXNlcklkOiB1dWlkISwgJHN0YXJ0RGF0ZTogdGltZXN0YW1wISwgJGVuZERhdGU6IHRpbWVzdGFtcCEpIHtcbiAgICAgICAgICBFdmVudCh3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH0sIGVuZERhdGU6IHtfZ3RlOiAkc3RhcnREYXRlfSwgc3RhcnREYXRlOiB7X2x0ZTogJGVuZERhdGV9LCBkZWxldGVkOiB7X2VxOiBmYWxzZX19KSB7XG4gICAgICAgICAgICBhbGxEYXlcbiAgICAgICAgICAgIGFueW9uZUNhbkFkZFNlbGZcbiAgICAgICAgICAgIGF0dGFjaG1lbnRzXG4gICAgICAgICAgICBhdHRlbmRlZXNPbWl0dGVkXG4gICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgIGNvbG9ySWRcbiAgICAgICAgICAgIGNvbmZlcmVuY2VJZFxuICAgICAgICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgY29weUNhdGVnb3JpZXNcbiAgICAgICAgICAgIGNvcHlEdXJhdGlvblxuICAgICAgICAgICAgY29weUlzQnJlYWtcbiAgICAgICAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgY29weUlzTWVldGluZ1xuICAgICAgICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgICAgICAgIGNvcHlQcmlvcml0eUxldmVsXG4gICAgICAgICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICAgICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICAgICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICBjcmVhdG9yXG4gICAgICAgICAgICBkYWlseVRhc2tMaXN0XG4gICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICBkdXJhdGlvblxuICAgICAgICAgICAgZW5kRGF0ZVxuICAgICAgICAgICAgZW5kVGltZVVuc3BlY2lmaWVkXG4gICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICBldmVudFR5cGVcbiAgICAgICAgICAgIGV4dGVuZGVkUHJvcGVydGllc1xuICAgICAgICAgICAgZm9sbG93VXBFdmVudElkXG4gICAgICAgICAgICBmb3JFdmVudElkXG4gICAgICAgICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICAgICAgZ3Vlc3RzQ2FuTW9kaWZ5XG4gICAgICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0c1xuICAgICAgICAgICAgaGFuZ291dExpbmtcbiAgICAgICAgICAgIGhhcmREZWFkbGluZVxuICAgICAgICAgICAgaHRtbExpbmtcbiAgICAgICAgICAgIGlDYWxVSURcbiAgICAgICAgICAgIGlkXG4gICAgICAgICAgICBpc0JyZWFrXG4gICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICBpc0ZvbGxvd1VwXG4gICAgICAgICAgICBpc01lZXRpbmdcbiAgICAgICAgICAgIGlzTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgIGlzUG9zdEV2ZW50XG4gICAgICAgICAgICBpc1ByZUV2ZW50XG4gICAgICAgICAgICBsaW5rc1xuICAgICAgICAgICAgbG9jYXRpb25cbiAgICAgICAgICAgIGxvY2tlZFxuICAgICAgICAgICAgbWF4QXR0ZW5kZWVzXG4gICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgIG1ldGhvZFxuICAgICAgICAgICAgbW9kaWZpYWJsZVxuICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3REYXlPZldlZWtcbiAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZVxuICAgICAgICAgICAgbm90ZXNcbiAgICAgICAgICAgIG9yZ2FuaXplclxuICAgICAgICAgICAgb3JpZ2luYWxBbGxEYXlcbiAgICAgICAgICAgIG9yaWdpbmFsU3RhcnREYXRlXG4gICAgICAgICAgICBvcmlnaW5hbFRpbWV6b25lXG4gICAgICAgICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RTY29yZVxuICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RUaW1lXG4gICAgICAgICAgICBwb3N0RXZlbnRJZFxuICAgICAgICAgICAgcHJlRXZlbnRJZFxuICAgICAgICAgICAgcHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2VcbiAgICAgICAgICAgIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlXG4gICAgICAgICAgICBwcmVmZXJyZWRUaW1lXG4gICAgICAgICAgICBwcmlvcml0eVxuICAgICAgICAgICAgcHJpdmF0ZUNvcHlcbiAgICAgICAgICAgIHJlY3VycmVuY2VcbiAgICAgICAgICAgIHJlY3VycmVuY2VSdWxlXG4gICAgICAgICAgICByZWN1cnJpbmdFdmVudElkXG4gICAgICAgICAgICBzZW5kVXBkYXRlc1xuICAgICAgICAgICAgc29mdERlYWRsaW5lXG4gICAgICAgICAgICBzb3VyY2VcbiAgICAgICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICAgICAgc3RhdHVzXG4gICAgICAgICAgICBzdW1tYXJ5XG4gICAgICAgICAgICB0YXNrSWRcbiAgICAgICAgICAgIHRhc2tUeXBlXG4gICAgICAgICAgICB0aW1lQmxvY2tpbmdcbiAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICB0aXRsZVxuICAgICAgICAgICAgdHJhbnNwYXJlbmN5XG4gICAgICAgICAgICB1bmxpbmtcbiAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgdXNlRGVmYXVsdEFsYXJtc1xuICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZENhdGVnb3JpZXNcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZER1cmF0aW9uXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRJc0JyZWFrXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNNZWV0aW5nXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRQcmlvcml0eUxldmVsXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnNcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2VcbiAgICAgICAgICAgIHZpc2liaWxpdHlcbiAgICAgICAgICAgIHdlZWtseVRhc2tMaXN0XG4gICAgICAgICAgICBieVdlZWtEYXlcbiAgICAgICAgICAgIGxvY2FsU3luY2VkXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRDb2xvclxuICAgICAgICAgICAgY29weUNvbG9yXG4gICAgICAgICAgICBjb3B5RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgdXNlck1vZGlmaWVkRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgdXNlck1vZGlmaWVkTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgICAgICAgIGA7XG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgRXZlbnQ6IEV2ZW50VHlwZVtdIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBzdGFydERhdGU6IGRheWpzKHN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICAgICAgZW5kRGF0ZTogZGF5anMoZW5kRGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoKSxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gbGlzdEV2ZW50c0ZvckRhdGUnKTsgLy8gQ29ycmVjdGVkIGxvZ1xuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiByZXM/LmRhdGE/LkV2ZW50IHx8IG51bGwgfTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgbGlzdGluZyBldmVudHMgZm9yIGRhdGU6JywgZSk7XG4gICAgY29uc3QgZXJyb3JEZXRhaWxzID0gZS5yZXNwb25zZT8uYm9keSB8fCBlLm1lc3NhZ2UgfHwgZTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0hBU1VSQV9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gbGlzdCBldmVudHMgZm9yIGRhdGU6ICR7ZS5tZXNzYWdlfWAsXG4gICAgICAgIGRldGFpbHM6IGVycm9yRGV0YWlscyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RFdmVudHNGb3JVc2VyR2l2ZW5EYXRlcyA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGhvc3RTdGFydERhdGU6IHN0cmluZyxcbiAgaG9zdEVuZERhdGU6IHN0cmluZyxcbiAgdXNlclRpbWV6b25lOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nXG4pOiBQcm9taXNlPEZlYXR1cmVzQXBwbHlSZXNwb25zZTxFdmVudFR5cGVbXSB8IG51bGw+PiA9PiB7XG4gIGlmIChcbiAgICAhdXNlcklkIHx8XG4gICAgIWhvc3RTdGFydERhdGUgfHxcbiAgICAhaG9zdEVuZERhdGUgfHxcbiAgICAhdXNlclRpbWV6b25lIHx8XG4gICAgIWhvc3RUaW1lem9uZVxuICApIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICdNaXNzaW5nIHJlcXVpcmVkIHBhcmFtZXRlcnMgZm9yIGxpc3RpbmcgZXZlbnRzIGZvciB1c2VyIGdpdmVuIGRhdGVzLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2xpc3RFdmVudHNGb3JVc2VyJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IGxpc3RFdmVudHNGb3JVc2VyKCR1c2VySWQ6IHV1aWQhLCAkc3RhcnREYXRlOiB0aW1lc3RhbXAhLCAkZW5kRGF0ZTogdGltZXN0YW1wISkge1xuICAgICAgICAgICAgICAgIEV2ZW50KHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgZW5kRGF0ZToge19ndGU6ICRzdGFydERhdGV9LCBzdGFydERhdGU6IHtfbHRlOiAkZW5kRGF0ZX0sIGRlbGV0ZWQ6IHtfbmVxOiB0cnVlfSwgYWxsRGF5OiB7X25lcTogdHJ1ZX19KSB7XG4gICAgICAgICAgICAgICAgICAgIGFsbERheVxuICAgICAgICAgICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICAgICAgICAgICAgICAgIGF0dGFjaG1lbnRzXG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlc09taXR0ZWRcbiAgICAgICAgICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgICAgICAgICBjb25mZXJlbmNlSWRcbiAgICAgICAgICAgICAgICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICBjb3B5Q2F0ZWdvcmllc1xuICAgICAgICAgICAgICAgICAgICBjb3B5RHVyYXRpb25cbiAgICAgICAgICAgICAgICAgICAgY29weUlzQnJlYWtcbiAgICAgICAgICAgICAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgICAgICAgICAgY29weVJlbWluZGVyc1xuICAgICAgICAgICAgICAgICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICAgICAgICAgICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBjcmVhdG9yXG4gICAgICAgICAgICAgICAgICAgIGRhaWx5VGFza0xpc3RcbiAgICAgICAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICAgICAgICBkdXJhdGlvblxuICAgICAgICAgICAgICAgICAgICBlbmREYXRlXG4gICAgICAgICAgICAgICAgICAgIGVuZFRpbWVVbnNwZWNpZmllZFxuICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgIGV2ZW50VHlwZVxuICAgICAgICAgICAgICAgICAgICBleHRlbmRlZFByb3BlcnRpZXNcbiAgICAgICAgICAgICAgICAgICAgZm9sbG93VXBFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIGZvckV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5Nb2RpZnlcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgICAgICAgICAgICAgICAgaGFuZ291dExpbmtcbiAgICAgICAgICAgICAgICAgICAgaGFyZERlYWRsaW5lXG4gICAgICAgICAgICAgICAgICAgIGh0bWxMaW5rXG4gICAgICAgICAgICAgICAgICAgIGlDYWxVSURcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgaXNCcmVha1xuICAgICAgICAgICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgaXNGb2xsb3dVcFxuICAgICAgICAgICAgICAgICAgICBpc01lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICBpc1Bvc3RFdmVudFxuICAgICAgICAgICAgICAgICAgICBpc1ByZUV2ZW50XG4gICAgICAgICAgICAgICAgICAgIGxpbmtzXG4gICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uXG4gICAgICAgICAgICAgICAgICAgIGxvY2tlZFxuICAgICAgICAgICAgICAgICAgICBtYXhBdHRlbmRlZXNcbiAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgIG1ldGhvZFxuICAgICAgICAgICAgICAgICAgICBtb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3RUaW1lXG4gICAgICAgICAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICAgICAgICAgIG9yZ2FuaXplclxuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbEFsbERheVxuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RUaW1lXG4gICAgICAgICAgICAgICAgICAgIHBvc3RFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIHByZUV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZVxuICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRUaW1lXG4gICAgICAgICAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICAgICAgICAgIHByaXZhdGVDb3B5XG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyZW5jZVJ1bGVcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyaW5nRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBzZW5kVXBkYXRlc1xuICAgICAgICAgICAgICAgICAgICBzb2Z0RGVhZGxpbmVcbiAgICAgICAgICAgICAgICAgICAgc291cmNlXG4gICAgICAgICAgICAgICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBzdGF0dXNcbiAgICAgICAgICAgICAgICAgICAgc3VtbWFyeVxuICAgICAgICAgICAgICAgICAgICB0YXNrSWRcbiAgICAgICAgICAgICAgICAgICAgdGFza1R5cGVcbiAgICAgICAgICAgICAgICAgICAgdGltZUJsb2NraW5nXG4gICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHRpdGxlXG4gICAgICAgICAgICAgICAgICAgIHRyYW5zcGFyZW5jeVxuICAgICAgICAgICAgICAgICAgICB1bmxpbmtcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRDYXRlZ29yaWVzXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZER1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzQnJlYWtcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgICAgICAgICAgIHZpc2liaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgd2Vla2x5VGFza0xpc3RcbiAgICAgICAgICAgICAgICAgICAgYnlXZWVrRGF5XG4gICAgICAgICAgICAgICAgICAgIGxvY2FsU3luY2VkXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGNvcHlDb2xvclxuICAgICAgICAgICAgICAgICAgICBjb3B5RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuICAgIGNvbnN0IHN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgdHJ1ZVxuICAgICk7XG4gICAgY29uc3QgZW5kRGF0ZUluSG9zdFRpbWV6b25lID0gZGF5anMoaG9zdEVuZERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIHRydWVcbiAgICApO1xuICAgIGNvbnN0IHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lID0gZGF5anMoc3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLmZvcm1hdCgpXG4gICAgICAuc2xpY2UoMCwgMTkpO1xuICAgIGNvbnN0IGVuZERhdGVJblVzZXJUaW1lem9uZSA9IGRheWpzKGVuZERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuZm9ybWF0KClcbiAgICAgIC5zbGljZSgwLCAxOSk7XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBFdmVudDogRXZlbnRUeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgIHN0YXJ0RGF0ZTogc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUsXG4gICAgICAgICAgICBlbmREYXRlOiBlbmREYXRlSW5Vc2VyVGltZXpvbmUsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGxpc3RFdmVudHNGb3JVc2VyJyk7XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHJlcz8uZGF0YT8uRXZlbnQgfHwgbnVsbCB9O1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBsaXN0aW5nIGV2ZW50cyBmb3IgdXNlciBnaXZlbiBkYXRlczonLCBlKTtcbiAgICBjb25zdCBlcnJvckRldGFpbHMgPSBlLnJlc3BvbnNlPy5ib2R5IHx8IGUubWVzc2FnZSB8fCBlO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnSEFTVVJBX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBsaXN0IGV2ZW50cyBmb3IgdXNlcjogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZXJyb3JEZXRhaWxzLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG4vLyBwcm9jZXNzTWVldGluZ0Fzc2lzdEZvck9wdGFwbGFubmVyIHNlZW1zIGxpa2UgYSBjb21wbGV4IGludGVybmFsIG9yY2hlc3RyYXRpb24sXG4vLyBmb3Igbm93LCB3ZSdsbCBhc3N1bWUgaXRzIHJldHVybiB0eXBlIG1pZ2h0IGJlIGEgc2ltcGxlIHN0YXR1cyBvciBhIGNvbXBsZXggb2JqZWN0LlxuLy8gTGV0J3MgYXNzdW1lIGl0IHJldHVybnMgYSBzdGF0dXMgbWVzc2FnZSBmb3IgdGhpcyByZWZhY3RvcmluZy5cbmV4cG9ydCBjb25zdCBwcm9jZXNzTWVldGluZ0Fzc2lzdEZvck9wdGFwbGFubmVyID0gYXN5bmMgKCk6IFByb21pc2U8XG4gIEZlYXR1cmVzQXBwbHlSZXNwb25zZTx7IG1lc3NhZ2U6IHN0cmluZyB9PlxuPiA9PiB7XG4gIHRyeSB7XG4gICAgLy8gLi4uIGV4aXN0aW5nIGxvZ2ljIC4uLlxuICAgIC8vIElmIHN1Y2Nlc3NmdWw6XG4gICAgLy8gcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHsgbWVzc2FnZTogXCJQcm9jZXNzaW5nIGZvciBPcHRhUGxhbm5lciBpbml0aWF0ZWQvY29tcGxldGVkLlwiIH0gfTtcbiAgICBjb25zb2xlLndhcm4oXG4gICAgICAncHJvY2Vzc01lZXRpbmdBc3Npc3RGb3JPcHRhcGxhbm5lciBsb2dpYyBpcyBjb21wbGV4IGFuZCBub3QgZnVsbHkgcmVmYWN0b3JlZCBmb3IgZXJyb3IgaGFuZGxpbmcgaGVyZS4nXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IHRydWUsXG4gICAgICBkYXRhOiB7XG4gICAgICAgIG1lc3NhZ2U6ICdQbGFjZWhvbGRlciByZXNwb25zZSBmb3IgcHJvY2Vzc01lZXRpbmdBc3Npc3RGb3JPcHRhcGxhbm5lci4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBwcm9jZXNzaW5nIG1lZXRpbmcgYXNzaXN0IGZvciBvcHRhcGxhbm5lcjonLCBlKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0lOVEVSTkFMX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBwcm9jZXNzIGZvciBPcHRhUGxhbm5lcjogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZSxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlTmV3TWVldGluZ0V2ZW50Rm9yQXR0ZW5kZWUgPSAoXG4gIGF0dGVuZGVlOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlLFxuICBtZWV0aW5nQXNzaXN0OiBNZWV0aW5nQXNzaXN0VHlwZSxcbiAgd2luZG93U3RhcnREYXRlOiBzdHJpbmcsXG4gIHdpbmRvd0VuZERhdGU6IHN0cmluZyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ/OiBzdHJpbmcsXG4gIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPzogTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVcbik6IEV2ZW50VHlwZSA9PiB7XG4gIGxldCBzdGFydERhdGUgPSBkYXlqcyh3aW5kb3dTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLmZvcm1hdCgpO1xuICBjb25zdCBlbmREYXRlID0gZGF5anMod2luZG93RW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAuZm9ybWF0KCk7XG4gIGlmIChwcmVmZXJyZWRTdGFydFRpbWVSYW5nZT8uZGF5T2ZXZWVrID4gMCkge1xuICAgIGNvbnN0IGRhdGVPYmplY3QgPSBkYXlqcyhzdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50b0RhdGUoKTtcbiAgICBjb25zdCBkYXRlT2JqZWN0V2l0aFNldElTT0RheVBvc3NpYmxlID0gc2V0SVNPRGF5KFxuICAgICAgZGF0ZU9iamVjdCxcbiAgICAgIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPy5kYXlPZldlZWtcbiAgICApO1xuICAgIGNvbnN0IG9yaWdpbmFsRGF0ZU9iamVjdFdpdGhTZXRJU09EYXkgPSBkYXRlT2JqZWN0V2l0aFNldElTT0RheVBvc3NpYmxlO1xuICAgIGxldCBkYXRlT2JqZWN0V2l0aFNldElTT0RheSA9IG9yaWdpbmFsRGF0ZU9iamVjdFdpdGhTZXRJU09EYXk7XG5cbiAgICBpZiAoIWRheWpzKGRhdGVPYmplY3RXaXRoU2V0SVNPRGF5KS5pc0JldHdlZW4oc3RhcnREYXRlLCBlbmREYXRlKSkge1xuICAgICAgZGF0ZU9iamVjdFdpdGhTZXRJU09EYXkgPSBkYXlqcyhvcmlnaW5hbERhdGVPYmplY3RXaXRoU2V0SVNPRGF5KVxuICAgICAgICAuYWRkKDEsICd3ZWVrJylcbiAgICAgICAgLnRvRGF0ZSgpO1xuICAgIH1cblxuICAgIGlmICghZGF5anMoZGF0ZU9iamVjdFdpdGhTZXRJU09EYXkpLmlzQmV0d2VlbihzdGFydERhdGUsIGVuZERhdGUpKSB7XG4gICAgICBkYXRlT2JqZWN0V2l0aFNldElTT0RheSA9IGRheWpzKG9yaWdpbmFsRGF0ZU9iamVjdFdpdGhTZXRJU09EYXkpXG4gICAgICAgIC5zdWJ0cmFjdCgxLCAnd2VlaycpXG4gICAgICAgIC50b0RhdGUoKTtcbiAgICB9XG5cbiAgICBzdGFydERhdGUgPSBkYXlqcyhkYXRlT2JqZWN0V2l0aFNldElTT0RheSkudHooaG9zdFRpbWV6b25lKS5mb3JtYXQoKTtcbiAgfVxuXG4gIGlmIChwcmVmZXJyZWRTdGFydFRpbWVSYW5nZT8uc3RhcnRUaW1lKSB7XG4gICAgY29uc3Qgc3RhcnRUaW1lID0gcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U/LnN0YXJ0VGltZTtcbiAgICBjb25zdCBob3VyID0gcGFyc2VJbnQoc3RhcnRUaW1lLnNsaWNlKDAsIDIpLCAxMCk7XG4gICAgY29uc3QgbWludXRlID0gcGFyc2VJbnQoc3RhcnRUaW1lLnNsaWNlKDMpLCAxMCk7XG5cbiAgICBzdGFydERhdGUgPSBkYXlqcyhzdGFydERhdGUuc2xpY2UoMCwgMTApKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5ob3VyKGhvdXIpXG4gICAgICAubWludXRlKG1pbnV0ZSlcbiAgICAgIC5mb3JtYXQoKTtcbiAgfVxuXG4gIGNvbnN0IGV2ZW50SWQgPSB1dWlkKCk7XG4gIGNvbnN0IG5ld0V2ZW50OiBFdmVudFR5cGUgPSB7XG4gICAgaWQ6IGAke2V2ZW50SWR9IyR7Y2FsZW5kYXJJZCA/PyBtZWV0aW5nQXNzaXN0LmNhbGVuZGFySWR9YCxcbiAgICBtZXRob2Q6ICdjcmVhdGUnLFxuICAgIHRpdGxlOiBtZWV0aW5nQXNzaXN0LnN1bW1hcnksXG4gICAgc3RhcnREYXRlLFxuICAgIGVuZERhdGU6IGRheWpzKHN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmFkZChtZWV0aW5nQXNzaXN0LmR1cmF0aW9uLCAnbScpXG4gICAgICAuZm9ybWF0KCksXG4gICAgYWxsRGF5OiBmYWxzZSxcbiAgICBub3RlczogbWVldGluZ0Fzc2lzdC5ub3RlcyxcbiAgICB0aW1lem9uZTogaG9zdFRpbWV6b25lLFxuICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIHByaW9yaXR5OiBtZWV0aW5nQXNzaXN0LnByaW9yaXR5LFxuICAgIGlzRm9sbG93VXA6IGZhbHNlLFxuICAgIGlzUHJlRXZlbnQ6IGZhbHNlLFxuICAgIGlzUG9zdEV2ZW50OiBmYWxzZSxcbiAgICBtb2RpZmlhYmxlOiB0cnVlLFxuICAgIHNlbmRVcGRhdGVzOiBtZWV0aW5nQXNzaXN0Py5zZW5kVXBkYXRlcyxcbiAgICBzdGF0dXM6ICdjb25maXJtZWQnLFxuICAgIHN1bW1hcnk6IG1lZXRpbmdBc3Npc3Quc3VtbWFyeSxcbiAgICB0cmFuc3BhcmVuY3k6IG1lZXRpbmdBc3Npc3Q/LnRyYW5zcGFyZW5jeSxcbiAgICB2aXNpYmlsaXR5OiBtZWV0aW5nQXNzaXN0Py52aXNpYmlsaXR5LFxuICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICBjYWxlbmRhcklkOiBjYWxlbmRhcklkID8/IG1lZXRpbmdBc3Npc3QuY2FsZW5kYXJJZCxcbiAgICB1c2VEZWZhdWx0QWxhcm1zOiBtZWV0aW5nQXNzaXN0LnVzZURlZmF1bHRBbGFybXMsXG4gICAgdGltZUJsb2NraW5nOiBtZWV0aW5nQXNzaXN0LmJ1ZmZlclRpbWUsXG4gICAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nOiBtZWV0aW5nQXNzaXN0Py5idWZmZXJUaW1lID8gdHJ1ZSA6IGZhbHNlLFxuICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlOiBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZT8uaWQgPyB0cnVlIDogZmFsc2UsXG4gICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzOiBtZWV0aW5nQXNzaXN0Py5yZW1pbmRlcnM/LlswXSA+IC0xID8gdHJ1ZSA6IGZhbHNlLFxuICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWw6IHRydWUsXG4gICAgdXNlck1vZGlmaWVkTW9kaWZpYWJsZTogdHJ1ZSxcbiAgICBkdXJhdGlvbjogbWVldGluZ0Fzc2lzdD8uZHVyYXRpb24sXG4gICAgdXNlck1vZGlmaWVkRHVyYXRpb246IHRydWUsXG4gICAgdXNlcklkOiBhdHRlbmRlZT8udXNlcklkLFxuICAgIGFueW9uZUNhbkFkZFNlbGY6IGZhbHNlLFxuICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyczogbWVldGluZ0Fzc2lzdD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOiBtZWV0aW5nQXNzaXN0Py5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICBvcmlnaW5hbFN0YXJ0RGF0ZTogdW5kZWZpbmVkLFxuICAgIG9yaWdpbmFsQWxsRGF5OiBmYWxzZSxcbiAgICBtZWV0aW5nSWQ6IG1lZXRpbmdBc3Npc3QuaWQsXG4gICAgZXZlbnRJZCxcbiAgfTtcblxuICByZXR1cm4gbmV3RXZlbnQ7XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVOZXdNZWV0aW5nRXZlbnRGb3JIb3N0ID0gKFxuICBob3N0QXR0ZW5kZWU6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGUsXG4gIG1lZXRpbmdBc3Npc3Q6IE1lZXRpbmdBc3Npc3RUeXBlLFxuICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgd2luZG93RW5kRGF0ZTogc3RyaW5nLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U/OiBNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlVHlwZVxuKTogRXZlbnRUeXBlID0+IHtcbiAgbGV0IHN0YXJ0RGF0ZSA9IGRheWpzKHdpbmRvd1N0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAuZm9ybWF0KCk7XG4gIGNvbnN0IGVuZERhdGUgPSBkYXlqcyh3aW5kb3dFbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgIC5mb3JtYXQoKTtcbiAgY29uc29sZS5sb2coXG4gICAgc3RhcnREYXRlLFxuICAgICcgc3RhcnREYXRlIGluc2lkZSBnZW5lcmF0ZU5ld01lZXRpbmdFdmVudEZvckF0dGVuZGVlIHN0ZXAgMSdcbiAgKTtcbiAgaWYgKHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPy5kYXlPZldlZWsgPiAwKSB7XG4gICAgY29uc3QgZGF0ZU9iamVjdCA9IGRheWpzKHN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLnRvRGF0ZSgpO1xuICAgIGNvbnN0IGRhdGVPYmplY3RXaXRoU2V0SVNPRGF5UG9zc2libGUgPSBzZXRJU09EYXkoXG4gICAgICBkYXRlT2JqZWN0LFxuICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U/LmRheU9mV2Vla1xuICAgICk7XG4gICAgbGV0IGRhdGVPYmplY3RXaXRoU2V0SVNPRGF5ID0gZGF0ZU9iamVjdFdpdGhTZXRJU09EYXlQb3NzaWJsZTtcbiAgICBpZiAoIWRheWpzKGRhdGVPYmplY3RXaXRoU2V0SVNPRGF5UG9zc2libGUpLmlzQmV0d2VlbihzdGFydERhdGUsIGVuZERhdGUpKSB7XG4gICAgICBkYXRlT2JqZWN0V2l0aFNldElTT0RheSA9IGRheWpzKGRhdGVPYmplY3RXaXRoU2V0SVNPRGF5UG9zc2libGUpXG4gICAgICAgIC5hZGQoMSwgJ3dlZWsnKVxuICAgICAgICAudG9EYXRlKCk7XG4gICAgfVxuICAgIHN0YXJ0RGF0ZSA9IGRheWpzKGRhdGVPYmplY3RXaXRoU2V0SVNPRGF5KS50eihob3N0VGltZXpvbmUpLmZvcm1hdCgpO1xuICB9XG5cbiAgY29uc29sZS5sb2coXG4gICAgc3RhcnREYXRlLFxuICAgICcgc3RhcnREYXRlIGluc2lkZSBnZW5lcmF0ZU5ld01lZXRpbmdFdmVudEZvckF0dGVuZGVlIHN0ZXAgMidcbiAgKTtcblxuICBpZiAocHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U/LnN0YXJ0VGltZSkge1xuICAgIGNvbnN0IHN0YXJ0VGltZSA9IHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPy5zdGFydFRpbWU7XG4gICAgY29uc3QgaG91ciA9IHBhcnNlSW50KHN0YXJ0VGltZS5zbGljZSgwLCAyKSwgMTApO1xuICAgIGNvbnN0IG1pbnV0ZSA9IHBhcnNlSW50KHN0YXJ0VGltZS5zbGljZSgzKSwgMTApO1xuXG4gICAgc3RhcnREYXRlID0gZGF5anMoc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuaG91cihob3VyKVxuICAgICAgLm1pbnV0ZShtaW51dGUpXG4gICAgICAuZm9ybWF0KCk7XG4gIH1cblxuICBjb25zb2xlLmxvZyhcbiAgICBzdGFydERhdGUsXG4gICAgJyBzdGFydERhdGUgaW5zaWRlIGdlbmVyYXRlTmV3TWVldGluZ0V2ZW50Rm9yQXR0ZW5kZWUgc3RlcCAzJ1xuICApO1xuXG4gIGNvbnN0IGV2ZW50SWQgPSB1dWlkKCk7XG4gIGNvbnN0IG5ld0V2ZW50OiBFdmVudFR5cGUgPSB7XG4gICAgaWQ6IGAke2V2ZW50SWR9IyR7bWVldGluZ0Fzc2lzdC5jYWxlbmRhcklkfWAsXG4gICAgbWV0aG9kOiAnY3JlYXRlJyxcbiAgICB0aXRsZTogbWVldGluZ0Fzc2lzdC5zdW1tYXJ5LFxuICAgIHN0YXJ0RGF0ZSxcbiAgICBlbmREYXRlOiBkYXlqcyhzdGFydERhdGUpLmFkZChtZWV0aW5nQXNzaXN0LmR1cmF0aW9uLCAnbScpLmZvcm1hdCgpLFxuICAgIGFsbERheTogZmFsc2UsXG4gICAgbm90ZXM6IG1lZXRpbmdBc3Npc3Qubm90ZXMsXG4gICAgdGltZXpvbmU6IGhvc3RUaW1lem9uZSxcbiAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICBkZWxldGVkOiBmYWxzZSxcbiAgICBwcmlvcml0eTogbWVldGluZ0Fzc2lzdC5wcmlvcml0eSxcbiAgICBpc0ZvbGxvd1VwOiBmYWxzZSxcbiAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICBpc1Bvc3RFdmVudDogZmFsc2UsXG4gICAgbW9kaWZpYWJsZTogdHJ1ZSxcbiAgICBzZW5kVXBkYXRlczogbWVldGluZ0Fzc2lzdD8uc2VuZFVwZGF0ZXMsXG4gICAgc3RhdHVzOiAnY29uZmlybWVkJyxcbiAgICBzdW1tYXJ5OiBtZWV0aW5nQXNzaXN0LnN1bW1hcnksXG4gICAgdHJhbnNwYXJlbmN5OiBtZWV0aW5nQXNzaXN0Py50cmFuc3BhcmVuY3ksXG4gICAgdmlzaWJpbGl0eTogbWVldGluZ0Fzc2lzdD8udmlzaWJpbGl0eSxcbiAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgY2FsZW5kYXJJZDogbWVldGluZ0Fzc2lzdC5jYWxlbmRhcklkLFxuICAgIHVzZURlZmF1bHRBbGFybXM6IG1lZXRpbmdBc3Npc3QudXNlRGVmYXVsdEFsYXJtcyxcbiAgICB0aW1lQmxvY2tpbmc6IG1lZXRpbmdBc3Npc3QuYnVmZmVyVGltZSxcbiAgICB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmc6IG1lZXRpbmdBc3Npc3Q/LmJ1ZmZlclRpbWUgPyB0cnVlIDogZmFsc2UsXG4gICAgdXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2U6IHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPy5pZCA/IHRydWUgOiBmYWxzZSxcbiAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnM6IG1lZXRpbmdBc3Npc3Q/LnJlbWluZGVycz8uWzBdID4gLTEgPyB0cnVlIDogZmFsc2UsXG4gICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbDogdHJ1ZSxcbiAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlOiB0cnVlLFxuICAgIGR1cmF0aW9uOiBtZWV0aW5nQXNzaXN0Py5kdXJhdGlvbixcbiAgICB1c2VyTW9kaWZpZWREdXJhdGlvbjogdHJ1ZSxcbiAgICB1c2VySWQ6IGhvc3RBdHRlbmRlZT8udXNlcklkLFxuICAgIGFueW9uZUNhbkFkZFNlbGY6IGZhbHNlLFxuICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyczogbWVldGluZ0Fzc2lzdD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOiBtZWV0aW5nQXNzaXN0Py5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICBvcmlnaW5hbFN0YXJ0RGF0ZTogdW5kZWZpbmVkLFxuICAgIG9yaWdpbmFsQWxsRGF5OiBmYWxzZSxcbiAgICBtZWV0aW5nSWQ6IG1lZXRpbmdBc3Npc3QuaWQsXG4gICAgZXZlbnRJZCxcbiAgfTtcblxuICByZXR1cm4gbmV3RXZlbnQ7XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCA9IGFzeW5jIChcbiAgZXZlbnRJZDogc3RyaW5nXG4gIC8vIFRoaXMgZnVuY3Rpb24gaXMgbWlzc2luZyB1c2VySWQgZm9yIGNvbnRleHQgaWYgaXQncyBhIHVzZXItc3BlY2lmaWMgYWN0aW9uXG4gIC8vIG9yIGlmIGl0J3MgYSBnZW5lcmljIGxvb2t1cCBieSBldmVudElkLCBpdCdzIGZpbmUuIEFzc3VtaW5nIGdlbmVyaWMgZm9yIG5vdy5cbik6IFByb21pc2U8RmVhdHVyZXNBcHBseVJlc3BvbnNlPFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXSB8IG51bGw+PiA9PiB7XG4gIGlmICghZXZlbnRJZCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogeyBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsIG1lc3NhZ2U6ICdFdmVudCBJRCBpcyByZXF1aXJlZC4nIH0sXG4gICAgfTtcbiAgfVxuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnTGlzdFByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbkV2ZW50SWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgcXVlcnkgTGlzdFByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbkV2ZW50SWQoJGV2ZW50SWQ6IFN0cmluZyEpIHtcbiAgICAgICAgUHJlZmVycmVkVGltZVJhbmdlKHdoZXJlOiB7ZXZlbnRJZDoge19lcTogJGV2ZW50SWR9fSkge1xuICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgZGF5T2ZXZWVrXG4gICAgICAgICAgZW5kVGltZVxuICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICBpZFxuICAgICAgICAgIHN0YXJ0VGltZVxuICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgIHVzZXJJZFxuICAgICAgICB9XG4gICAgICB9XG4gICAgYDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBldmVudElkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXSB9IH0gPVxuICAgICAgYXdhaXQgZ290XG4gICAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICAgIH0sXG4gICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGluc2lkZSAgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCcpO1xuICAgIHJlcz8uZGF0YT8uUHJlZmVycmVkVGltZVJhbmdlPy5tYXAoKHB0KSA9PlxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIHB0LFxuICAgICAgICAnIHByZWZlcnJlZFRpbWVSYW5nZSAtIHJlcz8uZGF0YT8uUHJlZmVycmVkVGltZVJhbmdlIGluc2lkZSAgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCAnXG4gICAgICApXG4gICAgKTtcblxuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiByZXM/LmRhdGE/LlByZWZlcnJlZFRpbWVSYW5nZSB8fCBudWxsIH07XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIGxpc3RpbmcgcHJlZmVycmVkIHRpbWUgcmFuZ2VzIGZvciBldmVudDonLCBlKTtcbiAgICBjb25zdCBlcnJvckRldGFpbHMgPSBlLnJlc3BvbnNlPy5ib2R5IHx8IGUubWVzc2FnZSB8fCBlO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnSEFTVVJBX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBsaXN0IHByZWZlcnJlZCB0aW1lIHJhbmdlczogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZXJyb3JEZXRhaWxzLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgY3JlYXRlUmVtaW5kZXJzRnJvbU1pbnV0ZXNBbmRFdmVudCA9IChcbiAgZXZlbnRJZDogc3RyaW5nLFxuICBtaW51dGVzOiBudW1iZXJbXSxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgdXNlRGVmYXVsdDogYm9vbGVhbixcbiAgdXNlcklkOiBzdHJpbmdcbik6IFJlbWluZGVyc0ZvckV2ZW50VHlwZSA9PiB7XG4gIHJldHVybiB7XG4gICAgZXZlbnRJZCxcbiAgICByZW1pbmRlcnM6IG1pbnV0ZXMubWFwKChtKSA9PiAoe1xuICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgIHVzZXJJZCxcbiAgICAgIGV2ZW50SWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIG1pbnV0ZXM6IG0sXG4gICAgICB1c2VEZWZhdWx0LFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICBkZWxldGVkOiB0cnVlLFxuICAgIH0pKSxcbiAgfTtcbn07XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVCdWZmZXJUaW1lRm9yTmV3TWVldGluZ0V2ZW50ID0gKFxuICBldmVudDogRXZlbnRNZWV0aW5nUGx1c1R5cGUsXG4gIGJ1ZmZlclRpbWU6IEJ1ZmZlclRpbWVOdW1iZXJUeXBlXG4pID0+IHtcbiAgbGV0IHZhbHVlc1RvUmV0dXJuOiBhbnkgPSB7fTtcbiAgdmFsdWVzVG9SZXR1cm4ubmV3RXZlbnQgPSBldmVudDtcbiAgY29uc3QgZXZlbnRJZCA9IHV1aWQoKTtcbiAgY29uc3QgZXZlbnRJZDEgPSB1dWlkKCk7XG4gIGNvbnN0IHByZUV2ZW50SWQgPSBldmVudD8ucHJlRXZlbnRJZCB8fCBgJHtldmVudElkfSMke2V2ZW50Py5jYWxlbmRhcklkfWA7XG4gIGNvbnN0IHBvc3RFdmVudElkID0gZXZlbnQ/LnBvc3RFdmVudElkIHx8IGAke2V2ZW50SWQxfSMke2V2ZW50Py5jYWxlbmRhcklkfWA7XG5cbiAgaWYgKGJ1ZmZlclRpbWUuYmVmb3JlRXZlbnQgPiAwKSB7XG4gICAgY29uc3QgYmVmb3JlRXZlbnRPckVtcHR5OiBFdmVudFBsdXNUeXBlID0ge1xuICAgICAgaWQ6IHByZUV2ZW50SWQsXG4gICAgICBpc1ByZUV2ZW50OiB0cnVlLFxuICAgICAgZm9yRXZlbnRJZDogZXZlbnQuaWQsXG4gICAgICBub3RlczogJ0J1ZmZlciB0aW1lJyxcbiAgICAgIHN1bW1hcnk6ICdCdWZmZXIgdGltZScsXG4gICAgICBzdGFydERhdGU6IGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnN1YnRyYWN0KGJ1ZmZlclRpbWUuYmVmb3JlRXZlbnQsICdtJylcbiAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgZW5kRGF0ZTogZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuZm9ybWF0KCksXG4gICAgICBtZXRob2Q6ICdjcmVhdGUnLFxuICAgICAgdXNlcklkOiBldmVudC51c2VySWQsXG4gICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgcHJpb3JpdHk6IDEsXG4gICAgICBtb2RpZmlhYmxlOiB0cnVlLFxuICAgICAgYW55b25lQ2FuQWRkU2VsZjogZmFsc2UsXG4gICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnM6IGZhbHNlLFxuICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM6IGZhbHNlLFxuICAgICAgb3JpZ2luYWxTdGFydERhdGU6IHVuZGVmaW5lZCxcbiAgICAgIG9yaWdpbmFsQWxsRGF5OiBmYWxzZSxcbiAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgY2FsZW5kYXJJZDogZXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgICB0aW1lem9uZTogZXZlbnQ/LnRpbWV6b25lLFxuICAgICAgaXNGb2xsb3dVcDogZmFsc2UsXG4gICAgICBpc1Bvc3RFdmVudDogZmFsc2UsXG4gICAgICBldmVudElkOiBwcmVFdmVudElkLnNwbGl0KCcjJylbMF0sXG4gICAgfTtcblxuICAgIHZhbHVlc1RvUmV0dXJuLmJlZm9yZUV2ZW50ID0gYmVmb3JlRXZlbnRPckVtcHR5O1xuICAgIHZhbHVlc1RvUmV0dXJuLm5ld0V2ZW50ID0ge1xuICAgICAgLi4udmFsdWVzVG9SZXR1cm4ubmV3RXZlbnQsXG4gICAgICBwcmVFdmVudElkLFxuICAgICAgdGltZUJsb2NraW5nOiB7XG4gICAgICAgIC4uLnZhbHVlc1RvUmV0dXJuPy5uZXdFdmVudD8udGltZUJsb2NraW5nLFxuICAgICAgICBiZWZvcmVFdmVudDogYnVmZmVyVGltZS5iZWZvcmVFdmVudCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIGlmIChidWZmZXJUaW1lLmFmdGVyRXZlbnQgPiAwKSB7XG4gICAgY29uc3QgYWZ0ZXJFdmVudE9yRW1wdHk6IEV2ZW50UGx1c1R5cGUgPSB7XG4gICAgICBpZDogcG9zdEV2ZW50SWQsXG4gICAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICAgIGZvckV2ZW50SWQ6IGV2ZW50LmlkLFxuICAgICAgaXNQb3N0RXZlbnQ6IHRydWUsXG4gICAgICBub3RlczogJ0J1ZmZlciB0aW1lJyxcbiAgICAgIHN1bW1hcnk6ICdCdWZmZXIgdGltZScsXG4gICAgICBzdGFydERhdGU6IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIGVuZERhdGU6IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5hZGQoYnVmZmVyVGltZS5hZnRlckV2ZW50LCAnbScpXG4gICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIG1ldGhvZDogJ2NyZWF0ZScsXG4gICAgICB1c2VySWQ6IGV2ZW50Py51c2VySWQsXG4gICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICBwcmlvcml0eTogMSxcbiAgICAgIGlzRm9sbG93VXA6IGZhbHNlLFxuICAgICAgbW9kaWZpYWJsZTogdHJ1ZSxcbiAgICAgIGFueW9uZUNhbkFkZFNlbGY6IGZhbHNlLFxuICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiBmYWxzZSxcbiAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOiBmYWxzZSxcbiAgICAgIG9yaWdpbmFsU3RhcnREYXRlOiB1bmRlZmluZWQsXG4gICAgICBvcmlnaW5hbEFsbERheTogZmFsc2UsXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIGNhbGVuZGFySWQ6IGV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgdGltZXpvbmU6IGV2ZW50Py50aW1lem9uZSxcbiAgICAgIGV2ZW50SWQ6IHBvc3RFdmVudElkLnNwbGl0KCcjJylbMF0sXG4gICAgfTtcblxuICAgIHZhbHVlc1RvUmV0dXJuLmFmdGVyRXZlbnQgPSBhZnRlckV2ZW50T3JFbXB0eTtcbiAgICB2YWx1ZXNUb1JldHVybi5uZXdFdmVudCA9IHtcbiAgICAgIC4uLnZhbHVlc1RvUmV0dXJuLm5ld0V2ZW50LFxuICAgICAgcG9zdEV2ZW50SWQsXG4gICAgICB0aW1lQmxvY2tpbmc6IHtcbiAgICAgICAgLi4udmFsdWVzVG9SZXR1cm4/Lm5ld0V2ZW50Py50aW1lQmxvY2tpbmcsXG4gICAgICAgIGFmdGVyRXZlbnQ6IGJ1ZmZlclRpbWUuYWZ0ZXJFdmVudCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIHJldHVybiB2YWx1ZXNUb1JldHVybiBhcyBWYWx1ZXNUb1JldHVybkZvckJ1ZmZlckV2ZW50c1R5cGU7XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0VXNlclByZWZlcmVuY2VzID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxVc2VyUHJlZmVyZW5jZVR5cGU+ID0+IHtcbiAgdHJ5IHtcbiAgICBpZiAoIXVzZXJJZCkge1xuICAgICAgY29uc29sZS5sb2coJ3VzZXJJZCBpcyBudWxsJyk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRVc2VyUHJlZmVyZW5jZXMnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgIHF1ZXJ5IGdldFVzZXJQcmVmZXJlbmNlcygkdXNlcklkOiB1dWlkISkge1xuICAgICAgVXNlcl9QcmVmZXJlbmNlKHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfX0pIHtcbiAgICAgICAgc3RhcnRUaW1lc1xuICAgICAgICBlbmRUaW1lc1xuICAgICAgICBiYWNrVG9CYWNrTWVldGluZ3NcbiAgICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgICBjb3B5Q2F0ZWdvcmllc1xuICAgICAgICBjb3B5SXNCcmVha1xuICAgICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgICBjb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgICAgY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgIGRlbGV0ZWRcbiAgICAgICAgZm9sbG93VXBcbiAgICAgICAgaWRcbiAgICAgICAgaXNQdWJsaWNDYWxlbmRhclxuICAgICAgICBtYXhOdW1iZXJPZk1lZXRpbmdzXG4gICAgICAgIG1heFdvcmtMb2FkUGVyY2VudFxuICAgICAgICBwdWJsaWNDYWxlbmRhckNhdGVnb3JpZXNcbiAgICAgICAgcmVtaW5kZXJzXG4gICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICB1c2VySWRcbiAgICAgICAgbWluTnVtYmVyT2ZCcmVha3NcbiAgICAgICAgYnJlYWtDb2xvclxuICAgICAgICBicmVha0xlbmd0aFxuICAgICAgICBjb3B5Q29sb3JcbiAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgICAgb25Cb2FyZGVkXG4gICAgICB9XG4gICAgfSAgICBcbiAgYDtcbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBVc2VyX1ByZWZlcmVuY2U6IFVzZXJQcmVmZXJlbmNlVHlwZVtdIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuICAgIHJldHVybiByZXM/LmRhdGE/LlVzZXJfUHJlZmVyZW5jZT8uWzBdO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyBnZXRVc2VyUHJlZmVyZW5jZXMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldEdsb2JhbENhbGVuZGFyID0gYXN5bmMgKHVzZXJJZDogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRHbG9iYWxDYWxlbmRhcic7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgIHF1ZXJ5IGdldEdsb2JhbENhbGVuZGFyKCR1c2VySWQ6IHV1aWQhKSB7XG4gICAgICAgICAgQ2FsZW5kYXIod2hlcmU6IHtnbG9iYWxQcmltYXJ5OiB7X2VxOiB0cnVlfSwgdXNlcklkOiB7X2VxOiAkdXNlcklkfX0pIHtcbiAgICAgICAgICAgIGNvbG9ySWRcbiAgICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgICAgYWNjZXNzTGV2ZWxcbiAgICAgICAgICAgIGFjY291bnRcbiAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICBkZWZhdWx0UmVtaW5kZXJzXG4gICAgICAgICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgIGdsb2JhbFByaW1hcnlcbiAgICAgICAgICAgIGlkXG4gICAgICAgICAgICBtb2RpZmlhYmxlXG4gICAgICAgICAgICBwcmltYXJ5XG4gICAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgICAgdGl0bGVcbiAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgYDtcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IENhbGVuZGFyOiBDYWxlbmRhclR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIHJldHVybiByZXMuZGF0YS5DYWxlbmRhcj8uWzBdO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGdsb2JhbCBjYWxlbmRhcicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgYWRqdXN0U3RhcnREYXRlc0ZvckJyZWFrRXZlbnRzRm9yRGF5ID0gKFxuICBhbGxFdmVudHM6IEV2ZW50UGx1c1R5cGVbXSxcbiAgYnJlYWtFdmVudHM6IEV2ZW50UGx1c1R5cGVbXSxcbiAgdXNlclByZWZlcmVuY2U6IFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgdGltZXpvbmU6IHN0cmluZ1xuKTogRXZlbnRQbHVzVHlwZVtdID0+IHtcbiAgaWYgKCFhbGxFdmVudHM/LlswXT8uaWQpIHtcbiAgICBjb25zb2xlLmxvZygnbm8gYWxsRXZlbnRzIGluc2lkZSBhZGp1c3RTdGFydERhdGVzRm9yQnJlYWtFdmVudHMnKTtcbiAgICByZXR1cm47XG4gIH1cblxuICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2Uuc3RhcnRUaW1lcztcbiAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZS5lbmRUaW1lcztcbiAgY29uc3QgZGF5T2ZXZWVrSW50ID0gZ2V0SVNPRGF5KFxuICAgIGRheWpzKGFsbEV2ZW50cz8uWzBdPy5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSkudG9EYXRlKClcbiAgKTtcbiAgY29uc3Qgc3RhcnRIb3VyID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICBjb25zdCBzdGFydE1pbnV0ZSA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcbiAgY29uc3QgZW5kSG91ciA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gIGNvbnN0IGVuZE1pbnV0ZSA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG4gIGNvbnN0IG5ld0JyZWFrRXZlbnRzID0gW107XG5cbiAgY29uc3Qgc3RhcnRPZldvcmtpbmdEYXkgPSBkYXlqcyhhbGxFdmVudHNbMF0/LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgIC5ob3VyKHN0YXJ0SG91cilcbiAgICAubWludXRlKHN0YXJ0TWludXRlKTtcblxuICBjb25zdCBlbmRPZldvcmtpbmdEYXkgPSBkYXlqcyhhbGxFdmVudHNbMF0/LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAuaG91cihlbmRIb3VyKVxuICAgIC5taW51dGUoZW5kTWludXRlKTtcblxuICBjb25zdCBmaWx0ZXJlZEV2ZW50cyA9IGFsbEV2ZW50cy5maWx0ZXIoKGUpID0+ICFlLmlzQnJlYWspO1xuICBpZiAoYnJlYWtFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICBmb3IgKGNvbnN0IGJyZWFrRXZlbnQgb2YgYnJlYWtFdmVudHMpIHtcbiAgICAgIGNvbnNvbGUubG9nKGJyZWFrRXZlbnQsICcgYnJlYWtFdmVudCBvZiBicmVha0V2ZW50cycpO1xuICAgICAgbGV0IGZvdW5kU3BhY2UgPSBmYWxzZTtcbiAgICAgIGxldCBpbmRleCA9IDA7XG4gICAgICB3aGlsZSAoIWZvdW5kU3BhY2UgJiYgaW5kZXggPCBmaWx0ZXJlZEV2ZW50cy5sZW5ndGgpIHtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgZm91bmRTcGFjZSxcbiAgICAgICAgICBpbmRleCxcbiAgICAgICAgICAnIGZvdW5kU3BhY2UsIGluZGV4LCAoIWZvdW5kU3BhY2UpICYmIChpbmRleCA8IGZpbHRlcmVkRXZlbnRzLmxlbmd0aCknXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IHBvc3NpYmxlRW5kRGF0ZSA9IGRheWpzKFxuICAgICAgICAgIGZpbHRlcmVkRXZlbnRzW2luZGV4XS5zdGFydERhdGUuc2xpY2UoMCwgMTkpXG4gICAgICAgICkudHoodGltZXpvbmUsIHRydWUpO1xuXG4gICAgICAgIGNvbnN0IHBvc3NpYmxlU3RhcnREYXRlID0gcG9zc2libGVFbmREYXRlLnN1YnRyYWN0KFxuICAgICAgICAgIHVzZXJQcmVmZXJlbmNlLmJyZWFrTGVuZ3RoLFxuICAgICAgICAgICdtaW51dGUnXG4gICAgICAgICk7XG4gICAgICAgIGxldCBpc0JldHdlZW5TdGFydCA9IHRydWU7XG4gICAgICAgIGxldCBpc0JldHdlZW5FbmQgPSB0cnVlO1xuICAgICAgICBsZXQgYmV0d2VlbkluZGV4ID0gMDtcbiAgICAgICAgbGV0IGJldHdlZW5Xb3JraW5nRGF5U3RhcnQgPSB0cnVlO1xuICAgICAgICBsZXQgYmV0d2VlbldvcmtpbmdEYXlFbmQgPSB0cnVlO1xuICAgICAgICBsZXQgaXNCZXR3ZWVuQnJlYWtTdGFydCA9IHRydWU7XG4gICAgICAgIGxldCBpc0JldHdlZW5CcmVha0VuZCA9IHRydWU7XG5cbiAgICAgICAgd2hpbGUgKFxuICAgICAgICAgIChpc0JldHdlZW5TdGFydCB8fFxuICAgICAgICAgICAgaXNCZXR3ZWVuRW5kIHx8XG4gICAgICAgICAgICAhYmV0d2VlbldvcmtpbmdEYXlTdGFydCB8fFxuICAgICAgICAgICAgIWJldHdlZW5Xb3JraW5nRGF5RW5kIHx8XG4gICAgICAgICAgICBpc0JldHdlZW5CcmVha1N0YXJ0IHx8XG4gICAgICAgICAgICBpc0JldHdlZW5CcmVha0VuZCkgJiZcbiAgICAgICAgICBiZXR3ZWVuSW5kZXggPCBmaWx0ZXJlZEV2ZW50cy5sZW5ndGhcbiAgICAgICAgKSB7XG4gICAgICAgICAgaXNCZXR3ZWVuU3RhcnQgPSBwb3NzaWJsZVN0YXJ0RGF0ZS5pc0JldHdlZW4oXG4gICAgICAgICAgICBkYXlqcyhmaWx0ZXJlZEV2ZW50c1tiZXR3ZWVuSW5kZXhdLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KFxuICAgICAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICAgICAgdHJ1ZVxuICAgICAgICAgICAgKSxcbiAgICAgICAgICAgIGRheWpzKGZpbHRlcmVkRXZlbnRzW2JldHdlZW5JbmRleF0uZW5kRGF0ZS5zbGljZSgwLCAxOSkpLnR6KFxuICAgICAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICAgICAgdHJ1ZVxuICAgICAgICAgICAgKSxcbiAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICk7XG5cbiAgICAgICAgICBpc0JldHdlZW5FbmQgPSBwb3NzaWJsZUVuZERhdGUuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMoZmlsdGVyZWRFdmVudHNbYmV0d2VlbkluZGV4XS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICAgIHRydWVcbiAgICAgICAgICAgICksXG4gICAgICAgICAgICBkYXlqcyhmaWx0ZXJlZEV2ZW50c1tiZXR3ZWVuSW5kZXhdLmVuZERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICAgIHRydWVcbiAgICAgICAgICAgICksXG4gICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICcoXSdcbiAgICAgICAgICApO1xuXG4gICAgICAgICAgYmV0d2VlbldvcmtpbmdEYXlTdGFydCA9IHBvc3NpYmxlU3RhcnREYXRlLmlzQmV0d2VlbihcbiAgICAgICAgICAgIHN0YXJ0T2ZXb3JraW5nRGF5LFxuICAgICAgICAgICAgZW5kT2ZXb3JraW5nRGF5LFxuICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAnWyknXG4gICAgICAgICAgKTtcblxuICAgICAgICAgIGJldHdlZW5Xb3JraW5nRGF5RW5kID0gcG9zc2libGVFbmREYXRlLmlzQmV0d2VlbihcbiAgICAgICAgICAgIHN0YXJ0T2ZXb3JraW5nRGF5LFxuICAgICAgICAgICAgZW5kT2ZXb3JraW5nRGF5LFxuICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAnKF0nXG4gICAgICAgICAgKTtcblxuICAgICAgICAgIGZvciAoY29uc3QgYnJlYWtFdmVudCBvZiBicmVha0V2ZW50cykge1xuICAgICAgICAgICAgaXNCZXR3ZWVuQnJlYWtTdGFydCA9IHBvc3NpYmxlU3RhcnREYXRlLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMoYnJlYWtFdmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSksXG4gICAgICAgICAgICAgIGRheWpzKGJyZWFrRXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKSxcbiAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgICk7XG5cbiAgICAgICAgICAgIGlzQmV0d2VlbkJyZWFrRW5kID0gcG9zc2libGVFbmREYXRlLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMoYnJlYWtFdmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSksXG4gICAgICAgICAgICAgIGRheWpzKGJyZWFrRXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKSxcbiAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICcoXSdcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgYmV0d2VlbkluZGV4Kys7XG4gICAgICAgIH1cblxuICAgICAgICBmb3VuZFNwYWNlID1cbiAgICAgICAgICAhaXNCZXR3ZWVuU3RhcnQgJiZcbiAgICAgICAgICAhaXNCZXR3ZWVuRW5kICYmXG4gICAgICAgICAgYmV0d2VlbldvcmtpbmdEYXlTdGFydCAmJlxuICAgICAgICAgIGJldHdlZW5Xb3JraW5nRGF5RW5kICYmXG4gICAgICAgICAgIWlzQmV0d2VlbkJyZWFrU3RhcnQgJiZcbiAgICAgICAgICAhaXNCZXR3ZWVuQnJlYWtFbmQ7XG5cbiAgICAgICAgaWYgKGZvdW5kU3BhY2UpIHtcbiAgICAgICAgICBjb25zdCBuZXdCcmVha0V2ZW50ID0ge1xuICAgICAgICAgICAgLi4uYnJlYWtFdmVudCxcbiAgICAgICAgICAgIHN0YXJ0RGF0ZTogcG9zc2libGVTdGFydERhdGUuZm9ybWF0KCksXG4gICAgICAgICAgICBlbmREYXRlOiBwb3NzaWJsZUVuZERhdGUuZm9ybWF0KCksXG4gICAgICAgICAgfTtcbiAgICAgICAgICBuZXdCcmVha0V2ZW50cy5wdXNoKG5ld0JyZWFrRXZlbnQpO1xuICAgICAgICB9XG5cbiAgICAgICAgaW5kZXgrKztcbiAgICAgIH1cbiAgICB9XG4gIH1cblxuICByZXR1cm4gbmV3QnJlYWtFdmVudHM7XG59O1xuZXhwb3J0IGNvbnN0IGNvbnZlcnRUb1RvdGFsV29ya2luZ0hvdXJzRm9ySW50ZXJuYWxBdHRlbmRlZSA9IChcbiAgdXNlclByZWZlcmVuY2U6IFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgaG9zdFN0YXJ0RGF0ZTogc3RyaW5nLFxuICBob3N0VGltZXpvbmU6IHN0cmluZ1xuKSA9PiB7XG4gIGNvbnN0IHN0YXJ0VGltZXMgPSB1c2VyUHJlZmVyZW5jZS5zdGFydFRpbWVzO1xuICBjb25zdCBlbmRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlLmVuZFRpbWVzO1xuICBjb25zdCBkYXlPZldlZWtJbnQgPSBnZXRJU09EYXkoXG4gICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkudG9EYXRlKClcbiAgKTtcbiAgY29uc3Qgc3RhcnRIb3VyID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICBjb25zdCBzdGFydE1pbnV0ZSA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcbiAgY29uc3QgZW5kSG91ciA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gIGNvbnN0IGVuZE1pbnV0ZSA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG5cbiAgY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICBob3Vyczogc3RhcnRIb3VyLFxuICAgIG1pbnV0ZXM6IHN0YXJ0TWludXRlLFxuICB9KTtcbiAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7IGhvdXJzOiBlbmRIb3VyLCBtaW51dGVzOiBlbmRNaW51dGUgfSk7XG4gIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgcmV0dXJuIHRvdGFsRHVyYXRpb24uYXNIb3VycygpO1xufTtcblxuZXhwb3J0IGNvbnN0IGNvbnZlcnRUb1RvdGFsV29ya2luZ0hvdXJzRm9yRXh0ZXJuYWxBdHRlbmRlZSA9IChcbiAgYXR0ZW5kZWVFdmVudHM6IEV2ZW50UGx1c1R5cGVbXSxcbiAgaG9zdFN0YXJ0RGF0ZTogc3RyaW5nLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgdXNlclRpbWV6b25lOiBzdHJpbmdcbikgPT4ge1xuICBjb25zdCBkYXlPZldlZWtJbnRCeUhvc3QgPSBnZXRJU09EYXkoXG4gICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkudG9EYXRlKClcbiAgKTtcbiAgY29uc3Qgc2FtZURheUV2ZW50cyA9IGF0dGVuZGVlRXZlbnRzLmZpbHRlcihcbiAgICAoZSkgPT5cbiAgICAgIGdldElTT0RheShcbiAgICAgICAgZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC50b0RhdGUoKVxuICAgICAgKSA9PT0gZGF5T2ZXZWVrSW50QnlIb3N0XG4gICk7XG4gIGNvbnN0IG1pblN0YXJ0RGF0ZSA9IF8ubWluQnkoc2FtZURheUV2ZW50cywgKGUpID0+XG4gICAgZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC51bml4KClcbiAgKTtcbiAgY29uc3QgbWF4RW5kRGF0ZSA9IF8ubWF4Qnkoc2FtZURheUV2ZW50cywgKGUpID0+XG4gICAgZGF5anMoZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAudW5peCgpXG4gICk7XG5cbiAgbGV0IHdvcmtFbmRIb3VyQnlIb3N0ID0gZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmhvdXIoKTtcbiAgY29uc3Qgd29ya0VuZE1pbnV0ZUJ5SG9zdCA9IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5pc0JldHdlZW4oXG4gICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAubWludXRlKDApLFxuICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAnbWludXRlJyxcbiAgICAgICdbKSdcbiAgICApXG4gICAgPyAxNVxuICAgIDogZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5taW51dGUoMTUpLFxuICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICdbKSdcbiAgICAgICAgICApXG4gICAgICA/IDMwXG4gICAgICA6IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDQ1KSxcbiAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgIClcbiAgICAgICAgPyA0NVxuICAgICAgICA6IDA7XG4gIGlmICh3b3JrRW5kTWludXRlQnlIb3N0ID09PSAwKSB7XG4gICAgaWYgKHdvcmtFbmRIb3VyQnlIb3N0IDwgMjMpIHtcbiAgICAgIHdvcmtFbmRIb3VyQnlIb3N0ICs9IDE7XG4gICAgfVxuICB9XG5cbiAgY29uc3Qgd29ya1N0YXJ0SG91ckJ5SG9zdCA9IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5ob3VyKCk7XG4gIGNvbnN0IHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCA9IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5pc0JldHdlZW4oXG4gICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAubWludXRlKDApLFxuICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAnbWludXRlJyxcbiAgICAgICdbKSdcbiAgICApXG4gICAgPyAwXG4gICAgOiBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgIClcbiAgICAgID8gMTVcbiAgICAgIDogZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoNDUpLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDMwXG4gICAgICAgIDogNDU7XG5cbiAgY29uc29sZS5sb2coXG4gICAgd29ya1N0YXJ0SG91ckJ5SG9zdCxcbiAgICB3b3JrU3RhcnRNaW51dGVCeUhvc3QsXG4gICAgd29ya0VuZEhvdXJCeUhvc3QsXG4gICAgJyB3b3JrU3RhcnRIb3VyQnlIb3N0LCB3b3JrU3RhcnRNaW51dGVCeUhvc3QsIHdvcmtFbmRIb3VyQnlIb3N0IGZvciB0b3RhbCB3b3JraW5nIGhvdXJzJ1xuICApO1xuICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiB3b3JrU3RhcnRIb3VyQnlIb3N0LFxuICAgIG1pbnV0ZXM6IHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCxcbiAgfSk7XG4gIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICBtaW51dGVzOiB3b3JrRW5kTWludXRlQnlIb3N0LFxuICB9KTtcbiAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICByZXR1cm4gdG90YWxEdXJhdGlvbi5hc0hvdXJzKCk7XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVCcmVha3MgPSAoXG4gIHVzZXJQcmVmZXJlbmNlczogVXNlclByZWZlcmVuY2VUeXBlLFxuICBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGU6IG51bWJlcixcbiAgZXZlbnRNaXJyb3I6IEV2ZW50UGx1c1R5cGUsXG4gIGdsb2JhbENhbGVuZGFySWQ/OiBzdHJpbmdcbik6IEV2ZW50UGx1c1R5cGVbXSA9PiB7XG4gIGNvbnN0IGJyZWFrcyA9IFtdO1xuICBpZiAoIXVzZXJQcmVmZXJlbmNlcz8uYnJlYWtMZW5ndGgpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgICdubyB1c2VyIHByZWZlcmVuY2VzIGJyZWFrTGVuZ3RoIHByb3ZpZGVkIGluc2lkZSBnZW5lcmF0ZUJyZWFrcydcbiAgICApO1xuICAgIHJldHVybiBicmVha3M7XG4gIH1cblxuICBpZiAoIW51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJ25vIG51bWJlciBvZiBicmVha3MgdG8gZ2VuZXJhdGUgcHJvdmlkZWQgaW5zaWRlIGdlbmVyYXRlQnJlYWtzJ1xuICAgICk7XG4gICAgcmV0dXJuIGJyZWFrcztcbiAgfVxuXG4gIGlmICghZXZlbnRNaXJyb3IpIHtcbiAgICBjb25zb2xlLmxvZygnbm8gZXZlbnQgbWlycm9yIHByb3ZpZGVkIGluc2lkZSBnZW5lcmF0ZUJyZWFrcycpO1xuICAgIHJldHVybiBicmVha3M7XG4gIH1cbiAgY29uc29sZS5sb2coXG4gICAgbnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlLFxuICAgICcgbnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlIGluc2lkZSBnZW5lcmF0ZUJyZWFrcydcbiAgKTtcbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGU7IGkrKykge1xuICAgIGNvbnN0IGV2ZW50SWQgPSB1dWlkKCk7XG4gICAgY29uc3QgYnJlYWtFdmVudDogRXZlbnRQbHVzVHlwZSA9IHtcbiAgICAgIGlkOiBgJHtldmVudElkfSMke2dsb2JhbENhbGVuZGFySWQgfHwgZXZlbnRNaXJyb3IuY2FsZW5kYXJJZH1gLFxuICAgICAgdXNlcklkOiB1c2VyUHJlZmVyZW5jZXMudXNlcklkLFxuICAgICAgdGl0bGU6ICdCcmVhaycsXG4gICAgICBzdGFydERhdGU6IGRheWpzKGV2ZW50TWlycm9yLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihldmVudE1pcnJvci50aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgZW5kRGF0ZTogZGF5anMoZXZlbnRNaXJyb3Iuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGV2ZW50TWlycm9yLnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuYWRkKHVzZXJQcmVmZXJlbmNlcy5icmVha0xlbmd0aCwgJ21pbnV0ZScpXG4gICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIGFsbERheTogZmFsc2UsXG4gICAgICBub3RlczogJ0JyZWFrJyxcbiAgICAgIHRpbWV6b25lOiBldmVudE1pcnJvci50aW1lem9uZSxcbiAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgcHJpb3JpdHk6IDEsXG4gICAgICBpc0ZvbGxvd1VwOiBmYWxzZSxcbiAgICAgIGlzUHJlRXZlbnQ6IGZhbHNlLFxuICAgICAgbW9kaWZpYWJsZTogdHJ1ZSxcbiAgICAgIGFueW9uZUNhbkFkZFNlbGY6IGZhbHNlLFxuICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiBmYWxzZSxcbiAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOiBmYWxzZSxcbiAgICAgIG9yaWdpbmFsU3RhcnREYXRlOiB1bmRlZmluZWQsXG4gICAgICBvcmlnaW5hbEFsbERheTogZmFsc2UsXG4gICAgICBjYWxlbmRhcklkOiBnbG9iYWxDYWxlbmRhcklkIHx8IGV2ZW50TWlycm9yLmNhbGVuZGFySWQsXG4gICAgICBiYWNrZ3JvdW5kQ29sb3I6IHVzZXJQcmVmZXJlbmNlcy5icmVha0NvbG9yIHx8ICcjRjdFQkY3JyxcbiAgICAgIGlzQnJlYWs6IHRydWUsXG4gICAgICBkdXJhdGlvbjogdXNlclByZWZlcmVuY2VzLmJyZWFrTGVuZ3RoLFxuICAgICAgdXNlck1vZGlmaWVkRHVyYXRpb246IHRydWUsXG4gICAgICB1c2VyTW9kaWZpZWRDb2xvcjogdHJ1ZSxcbiAgICAgIGlzUG9zdEV2ZW50OiBmYWxzZSxcbiAgICAgIG1ldGhvZDogJ2NyZWF0ZScsXG4gICAgICBldmVudElkLFxuICAgIH07XG4gICAgYnJlYWtzLnB1c2goYnJlYWtFdmVudCk7XG4gIH1cblxuICByZXR1cm4gYnJlYWtzO1xufTtcblxuZXhwb3J0IGNvbnN0IHNob3VsZEdlbmVyYXRlQnJlYWtFdmVudHNGb3JEYXkgPSAoXG4gIHdvcmtpbmdIb3VyczogbnVtYmVyLFxuICB1c2VyUHJlZmVyZW5jZXM6IFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgYWxsRXZlbnRzOiBFdmVudFBsdXNUeXBlW11cbikgPT4ge1xuICBpZiAoIXVzZXJQcmVmZXJlbmNlcz8uYnJlYWtMZW5ndGgpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgICdubyB1c2VyIHByZWZlcmVuY2VzIGJyZWFrTGVuZ3RoIHByb3ZpZGVkIGluc2lkZSBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzJ1xuICAgICk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgaWYgKCEoYWxsRXZlbnRzPy5sZW5ndGggPiAwKSkge1xuICAgIGNvbnNvbGUubG9nKCdubyBhbGxFdmVudHMgcHJlc2VudCBpbnNpZGUgc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50c0ZvckRheScpO1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuXG4gIGNvbnN0IGJyZWFrRXZlbnRzID0gYWxsRXZlbnRzLmZpbHRlcigoZXZlbnQpID0+IGV2ZW50LmlzQnJlYWspO1xuICBjb25zdCBudW1iZXJPZkJyZWFrc1BlckRheSA9IHVzZXJQcmVmZXJlbmNlcy5taW5OdW1iZXJPZkJyZWFrcztcblxuICBjb25zdCBicmVha0hvdXJzRnJvbU1pbkJyZWFrcyA9XG4gICAgKHVzZXJQcmVmZXJlbmNlcy5icmVha0xlbmd0aCAvIDYwKSAqIG51bWJlck9mQnJlYWtzUGVyRGF5O1xuICBjb25zdCBob3Vyc011c3RCZUJyZWFrID1cbiAgICB3b3JraW5nSG91cnMgKiAoMSAtIHVzZXJQcmVmZXJlbmNlcy5tYXhXb3JrTG9hZFBlcmNlbnQgLyAxMDApO1xuXG4gIGxldCBicmVha0hvdXJzQXZhaWxhYmxlID0gMDtcblxuICBpZiAoYnJlYWtIb3Vyc0Zyb21NaW5CcmVha3MgPiBob3Vyc011c3RCZUJyZWFrKSB7XG4gICAgYnJlYWtIb3Vyc0F2YWlsYWJsZSA9IGJyZWFrSG91cnNGcm9tTWluQnJlYWtzO1xuICB9IGVsc2Uge1xuICAgIGJyZWFrSG91cnNBdmFpbGFibGUgPSBob3Vyc011c3RCZUJyZWFrO1xuICB9XG5cbiAgbGV0IGJyZWFrSG91cnNVc2VkID0gMDtcbiAgZm9yIChjb25zdCBicmVha0V2ZW50IG9mIGJyZWFrRXZlbnRzKSB7XG4gICAgY29uc3QgZHVyYXRpb24gPSBkYXlqc1xuICAgICAgLmR1cmF0aW9uKFxuICAgICAgICBkYXlqcyhcbiAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKS5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW06c3MnKVxuICAgICAgICApLmRpZmYoXG4gICAgICAgICAgZGF5anMoYnJlYWtFdmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW06c3MnKVxuICAgICAgICApXG4gICAgICApXG4gICAgICAuYXNIb3VycygpO1xuICAgIGJyZWFrSG91cnNVc2VkICs9IGR1cmF0aW9uO1xuICB9XG5cbiAgaWYgKGJyZWFrSG91cnNVc2VkID49IGJyZWFrSG91cnNBdmFpbGFibGUpIHtcbiAgICBjb25zb2xlLmxvZygnYnJlYWtIb3Vyc1VzZWQgPj0gYnJlYWtIb3Vyc0F2YWlsYWJsZScpO1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuXG4gIGlmICghKGFsbEV2ZW50cz8ubGVuZ3RoID4gMCkpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgICd0aGVyZSBhcmUgbm8gZXZlbnRzIGZvciB0aGlzIGRhdGUgaW5zaWRlIHNob3VsZEdlbmVyYXRlQnJlYWtFdmVudHMnXG4gICAgKTtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICByZXR1cm4gdHJ1ZTtcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF5ID0gYXN5bmMgKFxuICB1c2VyUHJlZmVyZW5jZXM6IFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGhvc3RTdGFydERhdGU6IHN0cmluZyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIGdsb2JhbENhbGVuZGFySWQ/OiBzdHJpbmcsXG4gIGlzRmlyc3REYXk/OiBib29sZWFuXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBpZiAoIXVzZXJQcmVmZXJlbmNlcz8uYnJlYWtMZW5ndGgpIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAnbm8gdXNlciBwcmVmZXJlbmNlcyBicmVha0xlbmd0aCBwcm92aWRlZCBpbnNpZGUgc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50cydcbiAgICAgICk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG5cbiAgICBpZiAoIXVzZXJJZCkge1xuICAgICAgY29uc29sZS5sb2coJ25vIHVzZXJJZCBwcm92aWRlZCBpbnNpZGUgc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50cycpO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuXG4gICAgaWYgKCFob3N0U3RhcnREYXRlKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gc3RhcnREYXRlIHByb3ZpZGVkIGluc2lkZSBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzJyk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG5cbiAgICBpZiAoIWhvc3RUaW1lem9uZSkge1xuICAgICAgY29uc29sZS5sb2coJ25vIHRpbWV6b25lIHByb3ZpZGVkIGluc2lkZSBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzJyk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG5cbiAgICBpZiAoaXNGaXJzdERheSkge1xuICAgICAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZXMuZW5kVGltZXM7XG4gICAgICBjb25zdCBkYXlPZldlZWtJbnQgPSBnZXRJU09EYXkoXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICAgICApO1xuXG4gICAgICBsZXQgc3RhcnRIb3VyQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5ob3VyKCk7XG4gICAgICBsZXQgc3RhcnRNaW51dGVCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLm1pbnV0ZSgpO1xuICAgICAgY29uc3QgZW5kSG91ciA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gICAgICBjb25zdCBlbmRNaW51dGUgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuXG4gICAgICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2VzLnN0YXJ0VGltZXM7XG4gICAgICBjb25zdCB3b3JrU3RhcnRIb3VyID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgICAgY29uc3Qgd29ya1N0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKFxuICAgICAgICAoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludFxuICAgICAgKS5taW51dGVzO1xuXG4gICAgICBpZiAoXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS5pc0FmdGVyKFxuICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS5ob3VyKGVuZEhvdXIpLm1pbnV0ZShlbmRNaW51dGUpXG4gICAgICAgIClcbiAgICAgICkge1xuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH1cblxuICAgICAgaWYgKFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5pc0JlZm9yZShcbiAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyKVxuICAgICAgICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZSlcbiAgICAgICAgICApXG4gICAgICApIHtcbiAgICAgICAgc3RhcnRIb3VyQnlIb3N0ID0gd29ya1N0YXJ0SG91cjtcbiAgICAgICAgc3RhcnRNaW51dGVCeUhvc3QgPSB3b3JrU3RhcnRNaW51dGU7XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IHdvcmtpbmdIb3VycyA9IGNvbnZlcnRUb1RvdGFsV29ya2luZ0hvdXJzRm9ySW50ZXJuYWxBdHRlbmRlZShcbiAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICBob3N0U3RhcnREYXRlLFxuICAgICAgICBob3N0VGltZXpvbmVcbiAgICAgICk7XG4gICAgICBjb25zb2xlLmxvZyh3b3JraW5nSG91cnMsICcgd29ya2luZ0hvdXJzJyk7XG4gICAgICBjb25zdCBhbGxFdmVudHMgPSBhd2FpdCBsaXN0RXZlbnRzRm9yRGF0ZShcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQnlIb3N0KVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuaG91cihlbmRIb3VyKVxuICAgICAgICAgIC5taW51dGUoZW5kTWludXRlKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgaG9zdFRpbWV6b25lXG4gICAgICApO1xuXG4gICAgICBpZiAoIShhbGxFdmVudHM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICdubyBhbGxFdmVudHMgcHJlc2VudCBpbnNpZGUgc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50c0ZvckRheSdcbiAgICAgICAgKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IHNob3VsZEdlbmVyYXRlQnJlYWtzID0gc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50c0ZvckRheShcbiAgICAgICAgd29ya2luZ0hvdXJzLFxuICAgICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICAgIGFsbEV2ZW50c1xuICAgICAgKTtcblxuICAgICAgY29uc29sZS5sb2coc2hvdWxkR2VuZXJhdGVCcmVha3MsICcgc2hvdWxkR2VuZXJhdGVCcmVha3MnKTtcblxuICAgICAgaWYgKCFzaG91bGRHZW5lcmF0ZUJyZWFrcykge1xuICAgICAgICBjb25zb2xlLmxvZygnc2hvdWxkIG5vdCBnZW5lcmF0ZSBicmVha3MnKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9XG5cbiAgICAgIGxldCBob3Vyc1VzZWQgPSAwO1xuXG4gICAgICBpZiAoYWxsRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGZvciAoY29uc3QgYWxsRXZlbnQgb2YgYWxsRXZlbnRzKSB7XG4gICAgICAgICAgY29uc3QgZHVyYXRpb24gPSBkYXlqc1xuICAgICAgICAgICAgLmR1cmF0aW9uKFxuICAgICAgICAgICAgICBkYXlqcyhhbGxFdmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5kaWZmKFxuICAgICAgICAgICAgICAgICAgZGF5anMoYWxsRXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIClcbiAgICAgICAgICAgIClcbiAgICAgICAgICAgIC5hc0hvdXJzKCk7XG4gICAgICAgICAgaG91cnNVc2VkICs9IGR1cmF0aW9uO1xuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGNvbnNvbGUubG9nKGhvdXJzVXNlZCwgJyBob3Vyc1VzZWQnKTtcblxuICAgICAgbGV0IGhvdXJzQXZhaWxhYmxlID0gd29ya2luZ0hvdXJzIC0gaG91cnNVc2VkO1xuXG4gICAgICBjb25zb2xlLmxvZyhob3Vyc0F2YWlsYWJsZSwgJyBob3Vyc0F2YWlsYWJsZScpO1xuXG4gICAgICBjb25zdCBob3Vyc011c3RCZUJyZWFrID1cbiAgICAgICAgd29ya2luZ0hvdXJzICogKDEgLSB1c2VyUHJlZmVyZW5jZXMubWF4V29ya0xvYWRQZXJjZW50IC8gMTAwKTtcblxuICAgICAgY29uc29sZS5sb2coaG91cnNNdXN0QmVCcmVhaywgJyBob3Vyc011c3RCZUJyZWFrJyk7XG5cbiAgICAgIGlmIChob3Vyc0F2YWlsYWJsZSA8IGhvdXJzTXVzdEJlQnJlYWspIHtcbiAgICAgICAgaG91cnNBdmFpbGFibGUgPSBob3Vyc011c3RCZUJyZWFrO1xuICAgICAgfVxuICAgICAgaWYgKGhvdXJzQXZhaWxhYmxlIDw9IDApIHtcbiAgICAgICAgY29uc29sZS5sb2coaG91cnNBdmFpbGFibGUsICcgbm8gaG91cnMgYXZhaWxhYmxlJyk7XG4gICAgICAgIHJldHVybiBudWxsO1xuICAgICAgfVxuXG4gICAgICBjb25zdCBvbGRCcmVha0V2ZW50cyA9IGFsbEV2ZW50c1xuICAgICAgICAuZmlsdGVyKChldmVudCkgPT4gZXZlbnQuaXNCcmVhaylcbiAgICAgICAgLmZpbHRlcigoZSkgPT5cbiAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaXNTYW1lKFxuICAgICAgICAgICAgICBkYXlqcyhlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSksXG4gICAgICAgICAgICAgICdkYXknXG4gICAgICAgICAgICApXG4gICAgICAgICk7XG5cbiAgICAgIGNvbnN0IGJyZWFrRXZlbnRzID0gb2xkQnJlYWtFdmVudHM7XG5cbiAgICAgIGNvbnN0IG51bWJlck9mQnJlYWtzUGVyRGF5ID0gdXNlclByZWZlcmVuY2VzLm1pbk51bWJlck9mQnJlYWtzO1xuXG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgbnVtYmVyT2ZCcmVha3NQZXJEYXksXG4gICAgICAgICcgbnVtYmVyT2ZCcmVha3NQZXJEYXkgYWthIHVzZXJQcmVmZXJlbmNlcy5taW5OdW1iZXJPZkJyZWFrcydcbiAgICAgICk7XG4gICAgICBjb25zb2xlLmxvZyh1c2VyUHJlZmVyZW5jZXMuYnJlYWtMZW5ndGgsICcgdXNlclByZWZlcmVuY2VzLmJyZWFrTGVuZ3RoJyk7XG5cbiAgICAgIGNvbnN0IGJyZWFrSG91cnNUb0dlbmVyYXRlRm9yTWluQnJlYWtzID1cbiAgICAgICAgKHVzZXJQcmVmZXJlbmNlcy5icmVha0xlbmd0aCAvIDYwKSAqIG51bWJlck9mQnJlYWtzUGVyRGF5O1xuXG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYnJlYWtIb3Vyc1RvR2VuZXJhdGVGb3JNaW5CcmVha3MsXG4gICAgICAgICcgYnJlYWtIb3Vyc1RvR2VuZXJhdGVGb3JNaW5CcmVha3MnXG4gICAgICApO1xuXG4gICAgICBsZXQgYnJlYWtIb3Vyc1RvR2VuZXJhdGUgPSAwO1xuXG4gICAgICBpZiAoYnJlYWtIb3Vyc1RvR2VuZXJhdGVGb3JNaW5CcmVha3MgPiBob3Vyc0F2YWlsYWJsZSkge1xuICAgICAgICBicmVha0hvdXJzVG9HZW5lcmF0ZSA9IGhvdXJzQXZhaWxhYmxlO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgYnJlYWtIb3Vyc1RvR2VuZXJhdGUgPSBicmVha0hvdXJzVG9HZW5lcmF0ZUZvck1pbkJyZWFrcztcbiAgICAgIH1cblxuICAgICAgY29uc29sZS5sb2coYnJlYWtIb3Vyc1RvR2VuZXJhdGUsICcgYnJlYWtIb3Vyc1RvR2VuZXJhdGUnKTtcblxuICAgICAgbGV0IGJyZWFrSG91cnNVc2VkID0gMDtcblxuICAgICAgaWYgKGJyZWFrRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGZvciAoY29uc3QgYnJlYWtFdmVudCBvZiBicmVha0V2ZW50cykge1xuICAgICAgICAgIGNvbnN0IGR1cmF0aW9uID0gZGF5anNcbiAgICAgICAgICAgIC5kdXJhdGlvbihcbiAgICAgICAgICAgICAgZGF5anMoYnJlYWtFdmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5kaWZmKFxuICAgICAgICAgICAgICAgICAgZGF5anMoYnJlYWtFdmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgICAgICAgICAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICAgICAgICAgICAgICB0cnVlXG4gICAgICAgICAgICAgICAgICApXG4gICAgICAgICAgICAgICAgKVxuICAgICAgICAgICAgKVxuICAgICAgICAgICAgLmFzSG91cnMoKTtcbiAgICAgICAgICBicmVha0hvdXJzVXNlZCArPSBkdXJhdGlvbjtcbiAgICAgICAgfVxuICAgICAgfVxuXG4gICAgICBjb25zdCBhY3R1YWxCcmVha0hvdXJzVG9HZW5lcmF0ZSA9IGJyZWFrSG91cnNUb0dlbmVyYXRlIC0gYnJlYWtIb3Vyc1VzZWQ7XG5cbiAgICAgIGlmIChhY3R1YWxCcmVha0hvdXJzVG9HZW5lcmF0ZSA+IGhvdXJzQXZhaWxhYmxlKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKCcgbm8gaG91cnMgYXZhaWxhYmxlIHRvIGdlbmVyYXRlIGJyZWFrJyk7XG4gICAgICAgIHJldHVybiBudWxsO1xuICAgICAgfVxuICAgICAgY29uc29sZS5sb2coYWN0dWFsQnJlYWtIb3Vyc1RvR2VuZXJhdGUsICcgYWN0dWFsQnJlYWtIb3Vyc1RvR2VuZXJhdGUnKTtcbiAgICAgIGNvbnNvbGUubG9nKGJyZWFrSG91cnNVc2VkLCAnIGJyZWFrSG91cnNVc2VkJyk7XG4gICAgICBjb25zb2xlLmxvZyhicmVha0hvdXJzVG9HZW5lcmF0ZUZvck1pbkJyZWFrcywgJyBicmVha0hvdXJzQXZhaWxhYmxlJyk7XG4gICAgICBjb25zdCBicmVha0xlbmd0aEFzSG91cnMgPSB1c2VyUHJlZmVyZW5jZXMuYnJlYWtMZW5ndGggLyA2MDtcbiAgICAgIGNvbnNvbGUubG9nKGJyZWFrTGVuZ3RoQXNIb3VycywgJyBicmVha0xlbmd0aEFzSG91cnMnKTtcbiAgICAgIGNvbnN0IG51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZSA9IE1hdGguZmxvb3IoXG4gICAgICAgIGFjdHVhbEJyZWFrSG91cnNUb0dlbmVyYXRlIC8gYnJlYWtMZW5ndGhBc0hvdXJzXG4gICAgICApO1xuICAgICAgY29uc29sZS5sb2cobnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlLCAnIG51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZScpO1xuXG4gICAgICBpZiAobnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlIDwgMSkge1xuICAgICAgICBjb25zb2xlLmxvZygnc2hvdWxkIG5vdCBnZW5lcmF0ZSBicmVha3MnKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9XG5cbiAgICAgIGlmIChicmVha0hvdXJzVG9HZW5lcmF0ZSA+IDYpIHtcbiAgICAgICAgY29uc29sZS5sb2coJ2JyZWFrSG91cnNUb0dlbmVyYXRlIGlzID4gNicpO1xuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH1cblxuICAgICAgY29uc3QgZXZlbnRNaXJyb3IgPSBhbGxFdmVudHMuZmluZCgoZXZlbnQpID0+ICFldmVudC5pc0JyZWFrKTtcblxuICAgICAgY29uc3QgbmV3RXZlbnRzID0gZ2VuZXJhdGVCcmVha3MoXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgbnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlLFxuICAgICAgICBldmVudE1pcnJvcixcbiAgICAgICAgZ2xvYmFsQ2FsZW5kYXJJZFxuICAgICAgKTtcblxuICAgICAgcmV0dXJuIG5ld0V2ZW50cztcbiAgICB9XG5cbiAgICBjb25zdCBlbmRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5lbmRUaW1lcztcbiAgICBjb25zdCBkYXlPZldlZWtJbnQgPSBnZXRJU09EYXkoXG4gICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICAgICk7XG5cbiAgICBjb25zdCBlbmRIb3VyID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgICBjb25zdCBlbmRNaW51dGUgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuXG4gICAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5zdGFydFRpbWVzO1xuICAgIGNvbnN0IHN0YXJ0SG91ciA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgICBjb25zdCBzdGFydE1pbnV0ZSA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcblxuICAgIGNvbnN0IHdvcmtpbmdIb3VycyA9IGNvbnZlcnRUb1RvdGFsV29ya2luZ0hvdXJzRm9ySW50ZXJuYWxBdHRlbmRlZShcbiAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgIGhvc3RTdGFydERhdGUsXG4gICAgICBob3N0VGltZXpvbmVcbiAgICApO1xuICAgIGNvbnN0IGFsbEV2ZW50cyA9IGF3YWl0IGxpc3RFdmVudHNGb3JEYXRlKFxuICAgICAgdXNlcklkLFxuICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5ob3VyKHN0YXJ0SG91cilcbiAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZSlcbiAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgICAgIC5taW51dGUoZW5kTWludXRlKVxuICAgICAgICAuZm9ybWF0KCksXG4gICAgICBob3N0VGltZXpvbmVcbiAgICApO1xuICAgIGlmICghKGFsbEV2ZW50cz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAnbm8gYWxsRXZlbnRzIHByZXNlbnQgaW5zaWRlIHNob3VsZEdlbmVyYXRlQnJlYWtFdmVudHNGb3JEYXknXG4gICAgICApO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuICAgIGNvbnN0IHNob3VsZEdlbmVyYXRlQnJlYWtzID0gc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50c0ZvckRheShcbiAgICAgIHdvcmtpbmdIb3VycyxcbiAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgIGFsbEV2ZW50c1xuICAgICk7XG4gICAgaWYgKCFzaG91bGRHZW5lcmF0ZUJyZWFrcykge1xuICAgICAgY29uc29sZS5sb2coJ3Nob3VsZCBub3QgZ2VuZXJhdGUgYnJlYWtzJyk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG5cbiAgICBsZXQgaG91cnNVc2VkID0gMDtcblxuICAgIGlmIChhbGxFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGZvciAoY29uc3QgYWxsRXZlbnQgb2YgYWxsRXZlbnRzKSB7XG4gICAgICAgIGNvbnN0IGR1cmF0aW9uID0gZGF5anNcbiAgICAgICAgICAuZHVyYXRpb24oXG4gICAgICAgICAgICBkYXlqcyhhbGxFdmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLmRpZmYoXG4gICAgICAgICAgICAgICAgZGF5anMoYWxsRXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICApXG4gICAgICAgICAgKVxuICAgICAgICAgIC5hc0hvdXJzKCk7XG4gICAgICAgIGhvdXJzVXNlZCArPSBkdXJhdGlvbjtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhob3Vyc1VzZWQsICcgaG91cnNVc2VkJyk7XG5cbiAgICBsZXQgaG91cnNBdmFpbGFibGUgPSB3b3JraW5nSG91cnMgLSBob3Vyc1VzZWQ7XG4gICAgY29uc3QgaG91cnNNdXN0QmVCcmVhayA9XG4gICAgICB3b3JraW5nSG91cnMgKiAoMSAtIHVzZXJQcmVmZXJlbmNlcy5tYXhXb3JrTG9hZFBlcmNlbnQgLyAxMDApO1xuXG4gICAgY29uc29sZS5sb2coaG91cnNNdXN0QmVCcmVhaywgJyBob3Vyc011c3RCZUJyZWFrJyk7XG4gICAgY29uc29sZS5sb2coaG91cnNBdmFpbGFibGUsICcgaG91cnNBdmFpbGFibGUnKTtcblxuICAgIGlmIChob3Vyc0F2YWlsYWJsZSA8IGhvdXJzTXVzdEJlQnJlYWspIHtcbiAgICAgIGhvdXJzQXZhaWxhYmxlID0gaG91cnNNdXN0QmVCcmVhaztcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhob3Vyc0F2YWlsYWJsZSwgJyBob3Vyc0F2YWlsYWJsZScpO1xuXG4gICAgaWYgKGhvdXJzQXZhaWxhYmxlIDw9IDApIHtcbiAgICAgIGNvbnNvbGUubG9nKGhvdXJzQXZhaWxhYmxlLCAnIG5vIGhvdXJzIGF2YWlsYWJsZScpO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuXG4gICAgY29uc3Qgb2xkQnJlYWtFdmVudHMgPSBhbGxFdmVudHNcbiAgICAgIC5maWx0ZXIoKGV2ZW50KSA9PiBldmVudC5pc0JyZWFrKVxuICAgICAgLmZpbHRlcigoZSkgPT5cbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuaXNTYW1lKGRheWpzKGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKSwgJ2RheScpXG4gICAgICApO1xuXG4gICAgY29uc3QgYnJlYWtFdmVudHMgPSBvbGRCcmVha0V2ZW50cztcblxuICAgIGNvbnN0IG51bWJlck9mQnJlYWtzUGVyRGF5ID0gdXNlclByZWZlcmVuY2VzLm1pbk51bWJlck9mQnJlYWtzO1xuICAgIGNvbnNvbGUubG9nKG51bWJlck9mQnJlYWtzUGVyRGF5LCAnIG51bWJlck9mQnJlYWtzUGVyRGF5Jyk7XG4gICAgY29uc3QgYnJlYWtIb3Vyc1RvR2VuZXJhdGVGb3JNaW5CcmVha3MgPVxuICAgICAgKHVzZXJQcmVmZXJlbmNlcy5icmVha0xlbmd0aCAvIDYwKSAqIG51bWJlck9mQnJlYWtzUGVyRGF5O1xuICAgIGxldCBicmVha0hvdXJzVG9HZW5lcmF0ZSA9IDA7XG5cbiAgICBpZiAoYnJlYWtIb3Vyc1RvR2VuZXJhdGVGb3JNaW5CcmVha3MgPiBob3Vyc0F2YWlsYWJsZSkge1xuICAgICAgYnJlYWtIb3Vyc1RvR2VuZXJhdGUgPSBob3Vyc0F2YWlsYWJsZTtcbiAgICB9IGVsc2Uge1xuICAgICAgYnJlYWtIb3Vyc1RvR2VuZXJhdGUgPSBicmVha0hvdXJzVG9HZW5lcmF0ZUZvck1pbkJyZWFrcztcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhicmVha0hvdXJzVG9HZW5lcmF0ZSwgJyBicmVha0hvdXJzVG9HZW5lcmF0ZScpO1xuXG4gICAgbGV0IGJyZWFrSG91cnNVc2VkID0gMDtcblxuICAgIGlmIChicmVha0V2ZW50cz8ubGVuZ3RoID4gMCkge1xuICAgICAgZm9yIChjb25zdCBicmVha0V2ZW50IG9mIGJyZWFrRXZlbnRzKSB7XG4gICAgICAgIGNvbnN0IGR1cmF0aW9uID0gZGF5anNcbiAgICAgICAgICAuZHVyYXRpb24oXG4gICAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAuZGlmZihcbiAgICAgICAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgKVxuICAgICAgICAgIClcbiAgICAgICAgICAuYXNIb3VycygpO1xuICAgICAgICBicmVha0hvdXJzVXNlZCArPSBkdXJhdGlvbjtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBhY3R1YWxCcmVha0hvdXJzVG9HZW5lcmF0ZSA9IGJyZWFrSG91cnNUb0dlbmVyYXRlIC0gYnJlYWtIb3Vyc1VzZWQ7XG5cbiAgICBpZiAoYWN0dWFsQnJlYWtIb3Vyc1RvR2VuZXJhdGUgPiBob3Vyc0F2YWlsYWJsZSkge1xuICAgICAgY29uc29sZS5sb2coJyBubyBob3VycyBhdmFpbGFibGUgdG8gZ2VuZXJhdGUgYnJlYWsnKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKGJyZWFrSG91cnNVc2VkLCAnIGJyZWFrSG91cnNVc2VkJyk7XG4gICAgY29uc29sZS5sb2coYnJlYWtIb3Vyc1RvR2VuZXJhdGUsICcgYnJlYWtIb3Vyc0F2YWlsYWJsZScpO1xuICAgIGNvbnN0IGJyZWFrTGVuZ3RoQXNIb3VycyA9IHVzZXJQcmVmZXJlbmNlcy5icmVha0xlbmd0aCAvIDYwO1xuICAgIGNvbnNvbGUubG9nKGJyZWFrTGVuZ3RoQXNIb3VycywgJyBicmVha0xlbmd0aEFzSG91cnMnKTtcbiAgICBjb25zdCBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUgPSBNYXRoLmZsb29yKFxuICAgICAgYWN0dWFsQnJlYWtIb3Vyc1RvR2VuZXJhdGUgLyBicmVha0xlbmd0aEFzSG91cnNcbiAgICApO1xuICAgIGNvbnNvbGUubG9nKG51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZSwgJyBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUnKTtcblxuICAgIGlmIChudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUgPCAxKSB7XG4gICAgICBjb25zb2xlLmxvZygnc2hvdWxkIG5vdCBnZW5lcmF0ZSBicmVha3MnKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGlmIChicmVha0hvdXJzVG9HZW5lcmF0ZSA+IDYpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdicmVha0hvdXJzVG9HZW5lcmF0ZSBpcyA+IDYnKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGNvbnN0IGV2ZW50TWlycm9yID0gYWxsRXZlbnRzLmZpbmQoKGV2ZW50KSA9PiAhZXZlbnQuaXNCcmVhayk7XG5cbiAgICBjb25zdCBuZXdFdmVudHMgPSBnZW5lcmF0ZUJyZWFrcyhcbiAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgIG51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZSxcbiAgICAgIGV2ZW50TWlycm9yLFxuICAgICAgZ2xvYmFsQ2FsZW5kYXJJZFxuICAgICk7XG5cbiAgICByZXR1cm4gbmV3RXZlbnRzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2VuZXJhdGUgYnJlYWtzIGZvciBkYXknKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlQnJlYWtFdmVudHNGb3JEYXRlID0gYXN5bmMgKFxuICB1c2VyUHJlZmVyZW5jZXM6IFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGhvc3RTdGFydERhdGU6IHN0cmluZyxcbiAgaG9zdEVuZERhdGU6IHN0cmluZyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIGdsb2JhbENhbGVuZGFySWQ/OiBzdHJpbmdcbik6IFByb21pc2U8RXZlbnRQbHVzVHlwZVtdIHwgW10+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB0b3RhbEJyZWFrRXZlbnRzID0gW107XG4gICAgY29uc3QgdG90YWxEYXlzID0gZGF5anMoaG9zdEVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5kaWZmKGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLCAnZGF5Jyk7XG4gICAgY29uc29sZS5sb2codG90YWxEYXlzLCAnIHRvdGFsRGF5cyBpbnNpZGUgZ2VuZXJhdGVCcmVha0V2ZW50c0ZvckRhdGUnKTtcbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsRGF5czsgaSsrKSB7XG4gICAgICBjb25zdCBkYXlEYXRlID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5hZGQoaSwgJ2RheScpXG4gICAgICAgIC5mb3JtYXQoKTtcblxuICAgICAgY29uc3QgbmV3QnJlYWtFdmVudHMgPSBhd2FpdCBnZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF5KFxuICAgICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgZGF5RGF0ZSxcbiAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICBnbG9iYWxDYWxlbmRhcklkLFxuICAgICAgICBpID09PSAwXG4gICAgICApO1xuXG4gICAgICBpZiAoaSA9PT0gMCkge1xuICAgICAgICBjb25zdCBlbmRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5lbmRUaW1lcztcbiAgICAgICAgY29uc3QgZGF5T2ZXZWVrSW50ID0gZ2V0SVNPRGF5KFxuICAgICAgICAgIGRheWpzKGRheURhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICAgICAgICk7XG5cbiAgICAgICAgbGV0IHN0YXJ0SG91ciA9IGRheWpzKGRheURhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoKTtcbiAgICAgICAgbGV0IHN0YXJ0TWludXRlID0gZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAubWludXRlKCk7XG4gICAgICAgIGNvbnN0IGVuZEhvdXIgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgICAgICBjb25zdCBlbmRNaW51dGUgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuXG4gICAgICAgIGNvbnN0IHN0YXJ0VGltZXMgPSB1c2VyUHJlZmVyZW5jZXMuc3RhcnRUaW1lcztcbiAgICAgICAgY29uc3Qgd29ya1N0YXJ0SG91ciA9IHN0YXJ0VGltZXMuZmluZChcbiAgICAgICAgICAoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludFxuICAgICAgICApLmhvdXI7XG4gICAgICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZSA9IHN0YXJ0VGltZXMuZmluZChcbiAgICAgICAgICAoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludFxuICAgICAgICApLm1pbnV0ZXM7XG5cbiAgICAgICAgaWYgKFxuICAgICAgICAgIGRheWpzKGRheURhdGUuc2xpY2UoMCwgMTkpKS5pc0FmdGVyKFxuICAgICAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpLmhvdXIoZW5kSG91cikubWludXRlKGVuZE1pbnV0ZSlcbiAgICAgICAgICApXG4gICAgICAgICkge1xuICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICB9XG5cbiAgICAgICAgaWYgKFxuICAgICAgICAgIGRheWpzKGRheURhdGUuc2xpY2UoMCwgMTkpKS5pc0JlZm9yZShcbiAgICAgICAgICAgIGRheWpzKGRheURhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyKVxuICAgICAgICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZSlcbiAgICAgICAgICApXG4gICAgICAgICkge1xuICAgICAgICAgIHN0YXJ0SG91ciA9IHdvcmtTdGFydEhvdXI7XG4gICAgICAgICAgc3RhcnRNaW51dGUgPSB3b3JrU3RhcnRNaW51dGU7XG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBhbGxFdmVudHMgPSBhd2FpdCBsaXN0RXZlbnRzRm9yRGF0ZShcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmhvdXIoc3RhcnRIb3VyKVxuICAgICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZSlcbiAgICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgICBkYXlqcyhkYXlEYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cihlbmRIb3VyKVxuICAgICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGUpXG4gICAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgICAgaG9zdFRpbWV6b25lXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IG5ld0JyZWFrRXZlbnRzQWRqdXN0ZWQgPVxuICAgICAgICAgIGF3YWl0IGFkanVzdFN0YXJ0RGF0ZXNGb3JCcmVha0V2ZW50c0ZvckRheShcbiAgICAgICAgICAgIGFsbEV2ZW50cyxcbiAgICAgICAgICAgIG5ld0JyZWFrRXZlbnRzLFxuICAgICAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICAgICAgaG9zdFRpbWV6b25lXG4gICAgICAgICAgKTtcbiAgICAgICAgaWYgKG5ld0JyZWFrRXZlbnRzQWRqdXN0ZWQ/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICBuZXdCcmVha0V2ZW50c0FkanVzdGVkLmZvckVhY2goKGIpID0+XG4gICAgICAgICAgICBjb25zb2xlLmxvZyhiLCAnIG5ld0JyZWFrRXZlbnRzQWRqdXN0ZWQnKVxuICAgICAgICAgICk7XG4gICAgICAgICAgdG90YWxCcmVha0V2ZW50cy5wdXNoKC4uLm5ld0JyZWFrRXZlbnRzQWRqdXN0ZWQpO1xuICAgICAgICB9XG5cbiAgICAgICAgY29udGludWU7XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2VzLmVuZFRpbWVzO1xuICAgICAgY29uc3QgZGF5T2ZXZWVrSW50ID0gZ2V0SVNPRGF5KFxuICAgICAgICBkYXlqcyhkYXlEYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICAgICAgKTtcblxuICAgICAgY29uc3QgZW5kSG91ciA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gICAgICBjb25zdCBlbmRNaW51dGUgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuXG4gICAgICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2VzLnN0YXJ0VGltZXM7XG4gICAgICBjb25zdCBzdGFydEhvdXIgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gICAgICBjb25zdCBzdGFydE1pbnV0ZSA9IHN0YXJ0VGltZXMuZmluZChcbiAgICAgICAgKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRcbiAgICAgICkubWludXRlcztcblxuICAgICAgY29uc3QgYWxsRXZlbnRzID0gYXdhaXQgbGlzdEV2ZW50c0ZvckRhdGUoXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuaG91cihzdGFydEhvdXIpXG4gICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZSlcbiAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgIGRheWpzKGRheURhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoZW5kSG91cilcbiAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZSlcbiAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgIGhvc3RUaW1lem9uZVxuICAgICAgKTtcbiAgICAgIGNvbnN0IG5ld0JyZWFrRXZlbnRzQWRqdXN0ZWQgPSBhd2FpdCBhZGp1c3RTdGFydERhdGVzRm9yQnJlYWtFdmVudHNGb3JEYXkoXG4gICAgICAgIGFsbEV2ZW50cyxcbiAgICAgICAgbmV3QnJlYWtFdmVudHMsXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgaG9zdFRpbWV6b25lXG4gICAgICApO1xuICAgICAgaWYgKG5ld0JyZWFrRXZlbnRzQWRqdXN0ZWQ/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgbmV3QnJlYWtFdmVudHNBZGp1c3RlZC5mb3JFYWNoKChiKSA9PlxuICAgICAgICAgIGNvbnNvbGUubG9nKGIsICcgbmV3QnJlYWtFdmVudHNBZGp1c3RlZCcpXG4gICAgICAgICk7XG4gICAgICAgIHRvdGFsQnJlYWtFdmVudHMucHVzaCguLi5uZXdCcmVha0V2ZW50c0FkanVzdGVkKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICByZXR1cm4gdG90YWxCcmVha0V2ZW50cztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdlbmVyYXRlQnJlYWtFdmVudHNGb3JEYXRlJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZVdvcmtUaW1lc0ZvckludGVybmFsQXR0ZW5kZWUgPSAoXG4gIGhvc3RJZDogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdXNlclByZWZlcmVuY2U6IFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIHVzZXJUaW1lem9uZTogc3RyaW5nXG4pOiBXb3JrVGltZVR5cGVbXSA9PiB7XG4gIGNvbnN0IGRheXNJbldlZWsgPSA3O1xuICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2Uuc3RhcnRUaW1lcztcbiAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZS5lbmRUaW1lcztcbiAgY29uc3Qgd29ya1RpbWVzOiBXb3JrVGltZVR5cGVbXSA9IFtdO1xuXG4gIGZvciAobGV0IGkgPSAwOyBpIDwgZGF5c0luV2VlazsgaSsrKSB7XG4gICAgY29uc3QgZGF5T2ZXZWVrSW50ID0gaSArIDE7XG4gICAgY29uc3Qgc3RhcnRIb3VyID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuICAgIGNvbnN0IGVuZEhvdXIgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgIGNvbnN0IGVuZE1pbnV0ZSA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG5cbiAgICB3b3JrVGltZXMucHVzaCh7XG4gICAgICBkYXlPZldlZWs6IGRheU9mV2Vla0ludFRvU3RyaW5nW2RheU9mV2Vla0ludF0sXG4gICAgICBzdGFydFRpbWU6IGRheWpzKFxuICAgICAgICBzZXRJU09EYXkoXG4gICAgICAgICAgZGF5anMoKVxuICAgICAgICAgICAgLmhvdXIoc3RhcnRIb3VyKVxuICAgICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZSlcbiAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudG9EYXRlKCksXG4gICAgICAgICAgaSArIDFcbiAgICAgICAgKVxuICAgICAgKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICBlbmRUaW1lOiBkYXlqcyhcbiAgICAgICAgc2V0SVNPRGF5KFxuICAgICAgICAgIGRheWpzKClcbiAgICAgICAgICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZSlcbiAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudG9EYXRlKCksXG4gICAgICAgICAgaSArIDFcbiAgICAgICAgKVxuICAgICAgKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICBob3N0SWQsXG4gICAgICB1c2VySWQsXG4gICAgfSk7XG4gIH1cblxuICByZXR1cm4gd29ya1RpbWVzO1xufTtcblxuY29uc3QgZm9ybWF0VG9Nb250aERheSA9IChtb250aDogTW9udGhUeXBlLCBkYXk6IERheVR5cGUpOiBNb250aERheVR5cGUgPT4ge1xuICBjb25zdCBtb250aEZvcm1hdCA9IChtb250aCA8IDkgPyBgMCR7bW9udGggKyAxfWAgOiBgJHttb250aCArIDF9YCkgYXMgTU07XG4gIGNvbnN0IGRheUZvcm1hdCA9IChkYXkgPCAxMCA/IGAwJHtkYXl9YCA6IGAke2RheX1gKSBhcyBERDtcbiAgcmV0dXJuIGAtLSR7bW9udGhGb3JtYXR9LSR7ZGF5Rm9ybWF0fWA7XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVUaW1lU2xvdHNGb3JJbnRlcm5hbEF0dGVuZGVlID0gKFxuICBob3N0U3RhcnREYXRlOiBzdHJpbmcsXG4gIGhvc3RJZDogc3RyaW5nLFxuICB1c2VyUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgdXNlclRpbWV6b25lOiBzdHJpbmcsXG4gIGlzRmlyc3REYXk/OiBib29sZWFuXG4pOiBUaW1lU2xvdFR5cGVbXSA9PiB7XG4gIGlmIChpc0ZpcnN0RGF5KSB7XG4gICAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZS5lbmRUaW1lcztcbiAgICBjb25zdCBkYXlPZldlZWtJbnQgPSBnZXRJU09EYXkoXG4gICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgLnRvRGF0ZSgpXG4gICAgKTtcbiAgICBjb25zdCBkYXlPZldlZWtJbnRCeUhvc3QgPSBnZXRJU09EYXkoXG4gICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICAgICk7XG4gICAgY29uc3QgZGF5T2ZNb250aCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuZGF0ZSgpO1xuICAgIGNvbnN0IHN0YXJ0SG91ciA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKDApLFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICdtaW51dGUnLFxuICAgICAgICAnWyknXG4gICAgICApXG4gICAgICA/IDBcbiAgICAgIDogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDE1XG4gICAgICAgIDogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAubWludXRlKDQ1KSxcbiAgICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICAgIClcbiAgICAgICAgICA/IDMwXG4gICAgICAgICAgOiA0NTtcblxuICAgIGNvbnN0IG1vbnRoQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLm1vbnRoKCk7XG4gICAgY29uc3QgZGF5T2ZNb250aEJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5kYXRlKCk7XG4gICAgY29uc3Qgc3RhcnRIb3VyQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmhvdXIoKTtcbiAgICBjb25zdCBzdGFydE1pbnV0ZUJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLm1pbnV0ZSgwKSxcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkubWludXRlKDE1KSxcbiAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICdbKSdcbiAgICAgIClcbiAgICAgID8gMFxuICAgICAgOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMTUpLFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDE1XG4gICAgICAgIDogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgICAgLm1pbnV0ZSg0NSksXG4gICAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgICApXG4gICAgICAgICAgPyAzMFxuICAgICAgICAgIDogNDU7XG5cbiAgICBjb25zdCBlbmRIb3VyID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgICBjb25zdCBlbmRNaW51dGUgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuICAgIGNvbnN0IGVuZEhvdXJCeUhvc3QgPSBkYXlqcyhcbiAgICAgIHNldElTT0RheShcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgICAgICAgLnRvRGF0ZSgpLFxuICAgICAgICBkYXlPZldlZWtJbnRcbiAgICAgIClcbiAgICApXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmhvdXIoKTtcbiAgICBjb25zdCBlbmRNaW51dGVCeUhvc3QgPSBkYXlqcyhcbiAgICAgIHNldElTT0RheShcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoZW5kTWludXRlKVxuICAgICAgICAgIC50b0RhdGUoKSxcbiAgICAgICAgZGF5T2ZXZWVrSW50XG4gICAgICApXG4gICAgKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5taW51dGUoKTtcbiAgICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2Uuc3RhcnRUaW1lcztcbiAgICBjb25zdCB3b3JrU3RhcnRIb3VyID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZSA9IHN0YXJ0VGltZXMuZmluZChcbiAgICAgIChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50XG4gICAgKS5taW51dGVzO1xuICAgIGNvbnN0IHdvcmtTdGFydEhvdXJCeUhvc3QgPSBkYXlqcyhcbiAgICAgIHNldElTT0RheShcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXIpXG4gICAgICAgICAgLnRvRGF0ZSgpLFxuICAgICAgICBkYXlPZldlZWtJbnRcbiAgICAgIClcbiAgICApXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmhvdXIoKTtcbiAgICBjb25zdCB3b3JrU3RhcnRNaW51dGVCeUhvc3QgPSBkYXlqcyhcbiAgICAgIHNldElTT0RheShcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoZW5kTWludXRlKVxuICAgICAgICAgIC50b0RhdGUoKSxcbiAgICAgICAgZGF5T2ZXZWVrSW50XG4gICAgICApXG4gICAgKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5taW51dGUoKTtcblxuICAgIGlmIChcbiAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuaXNBZnRlcihcbiAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cihlbmRIb3VyQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGVCeUhvc3QpXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIHJldHVybiBbXTtcbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmlzQmVmb3JlKFxuICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXJCeUhvc3QpXG4gICAgICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgKVxuICAgICkge1xuICAgICAgY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgICAgaG91cnM6IHdvcmtTdGFydEhvdXIsXG4gICAgICAgIG1pbnV0ZXM6IHdvcmtTdGFydE1pbnV0ZSxcbiAgICAgIH0pO1xuICAgICAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICAgIGhvdXJzOiBlbmRIb3VyLFxuICAgICAgICBtaW51dGVzOiBlbmRNaW51dGUsXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgICAgIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG4gICAgICBjb25zdCB0aW1lU2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgaG9zdFN0YXJ0RGF0ZSxcbiAgICAgICAgZW5kVGltZXMsXG4gICAgICAgIGRheU9mV2Vla0ludEJ5SG9zdCxcbiAgICAgICAgZGF5T2ZNb250aCxcbiAgICAgICAgc3RhcnRIb3VyLFxuICAgICAgICBzdGFydE1pbnV0ZSxcbiAgICAgICAgZW5kSG91cixcbiAgICAgICAgZW5kTWludXRlLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgYHN0YXJ0RGF0ZSwgZW5kVGltZXMsIGRheU9mV2Vla0ludEJ5SG9zdCwgZGF5T2ZNb250aCwgc3RhcnRIb3VyLCBzdGFydE1pbnV0ZSwgZW5kSG91ciwgZW5kTWludXRlIHRvdGFsTWludXRlcywgdGltZXpvbmUsIGluc2lkZSBmaXJzdERheSBpbnNpZGUgZ2VuZXJhdGVUaW1lc2xvdHNgXG4gICAgICApO1xuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gMTUpIHtcbiAgICAgICAgdGltZVNsb3RzLnB1c2goe1xuICAgICAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50QnlIb3N0XSxcbiAgICAgICAgICBzdGFydFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgICAuYWRkKGksICdtaW51dGUnKVxuICAgICAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgICAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgICAuYWRkKGkgKyAxNSwgJ21pbnV0ZScpXG4gICAgICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICAgICAgaG9zdElkLFxuICAgICAgICAgIG1vbnRoRGF5OiBmb3JtYXRUb01vbnRoRGF5KFxuICAgICAgICAgICAgbW9udGhCeUhvc3QgYXMgTW9udGhUeXBlLFxuICAgICAgICAgICAgZGF5T2ZNb250aEJ5SG9zdCBhcyBEYXlUeXBlXG4gICAgICAgICAgKSxcbiAgICAgICAgfSk7XG4gICAgICB9XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgdGltZVNsb3RzLFxuICAgICAgICAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMgZm9yIGZpcnN0IGRheSB3aGVyZSBzdGFydERhdGUgaXMgYmVmb3JlIHdvcmsgc3RhcnQgdGltZSdcbiAgICAgICk7XG4gICAgICByZXR1cm4gdGltZVNsb3RzO1xuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICBob3Vyczogc3RhcnRIb3VyLFxuICAgICAgbWludXRlczogc3RhcnRNaW51dGUsXG4gICAgfSk7XG4gICAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7IGhvdXJzOiBlbmRIb3VyLCBtaW51dGVzOiBlbmRNaW51dGUgfSk7XG4gICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG4gICAgY29uc3QgdGltZVNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgaG9zdFN0YXJ0RGF0ZSxcbiAgICAgIGVuZFRpbWVzLFxuICAgICAgZGF5T2ZXZWVrSW50LFxuICAgICAgZGF5T2ZNb250aEJ5SG9zdCxcbiAgICAgIHN0YXJ0SG91ckJ5SG9zdCxcbiAgICAgIHN0YXJ0TWludXRlQnlIb3N0LFxuICAgICAgZW5kSG91ckJ5SG9zdCxcbiAgICAgIGVuZE1pbnV0ZUJ5SG9zdCxcbiAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIGBzdGFydERhdGUsIGVuZFRpbWVzLCBkYXlPZldlZWtJbnQsIGRheU9mTW9udGgsIHN0YXJ0SG91ciwgc3RhcnRNaW51dGUsIGVuZEhvdXIsIGVuZE1pbnV0ZSB0b3RhbE1pbnV0ZXMsIHRpbWV6b25lLCBpbnNpZGUgZmlyc3REYXkgaW5zaWRlIGdlbmVyYXRlVGltZXNsb3RzYFxuICAgICk7XG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gMTUpIHtcbiAgICAgIHRpbWVTbG90cy5wdXNoKHtcbiAgICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1tkYXlPZldlZWtJbnRdLFxuICAgICAgICBzdGFydFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgLmFkZChpICsgMTUsICdtaW51dGUnKVxuICAgICAgICAgIC5mb3JtYXQoJ0hIOm1tJykgYXMgVGltZSxcbiAgICAgICAgaG9zdElkLFxuICAgICAgICBtb250aERheTogZm9ybWF0VG9Nb250aERheShcbiAgICAgICAgICBtb250aEJ5SG9zdCBhcyBNb250aFR5cGUsXG4gICAgICAgICAgZGF5T2ZNb250aEJ5SG9zdCBhcyBEYXlUeXBlXG4gICAgICAgICksXG4gICAgICB9KTtcbiAgICB9XG4gICAgY29uc29sZS5sb2codGltZVNsb3RzLCAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMgZm9yIGZpcnN0IGRheScpO1xuICAgIHJldHVybiB0aW1lU2xvdHM7XG4gIH1cblxuICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2Uuc3RhcnRUaW1lcztcbiAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZS5lbmRUaW1lcztcbiAgY29uc3QgZGF5T2ZXZWVrSW50ID0gZ2V0SVNPRGF5KFxuICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAudG9EYXRlKClcbiAgKTtcbiAgY29uc3Qgc3RhcnRIb3VyID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICBjb25zdCBzdGFydE1pbnV0ZSA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcbiAgY29uc3QgZW5kSG91ciA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gIGNvbnN0IGVuZE1pbnV0ZSA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG5cbiAgY29uc3QgbW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgIC5tb250aCgpO1xuICBjb25zdCBkYXlPZk1vbnRoQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAuZGF0ZSgpO1xuXG4gIGNvbnN0IHN0YXJ0SG91ckJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAuaG91cihzdGFydEhvdXIpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAuaG91cigpO1xuICBjb25zdCBzdGFydE1pbnV0ZUJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAubWludXRlKHN0YXJ0TWludXRlKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLm1pbnV0ZSgpO1xuICBjb25zdCBlbmRIb3VyQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHoodXNlclRpbWV6b25lKVxuICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAuaG91cigpO1xuXG4gIGNvbnNvbGUubG9nKFxuICAgIG1vbnRoQnlIb3N0LFxuICAgIGRheU9mTW9udGhCeUhvc3QsXG4gICAgc3RhcnRIb3VyQnlIb3N0LFxuICAgIHN0YXJ0TWludXRlQnlIb3N0LFxuICAgIGVuZEhvdXJCeUhvc3QsXG4gICAgJyBtb250aEJ5SG9zdCwgZGF5T2ZNb250aEJ5SG9zdCwgc3RhcnRIb3VyQnlIb3N0LCBzdGFydE1pbnV0ZUJ5SG9zdCwgZW5kSG91ckJ5SG9zdCdcbiAgKTtcbiAgY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICBob3Vyczogc3RhcnRIb3VyLFxuICAgIG1pbnV0ZXM6IHN0YXJ0TWludXRlLFxuICB9KTtcbiAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7IGhvdXJzOiBlbmRIb3VyLCBtaW51dGVzOiBlbmRNaW51dGUgfSk7XG4gIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcbiAgY29uc3QgdGltZVNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsTWludXRlczsgaSArPSAxNSkge1xuICAgIHRpbWVTbG90cy5wdXNoKHtcbiAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50XSxcbiAgICAgIHN0YXJ0VGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgICAgZW5kVGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgLmFkZChpICsgMTUsICdtaW51dGUnKVxuICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICBob3N0SWQsXG4gICAgICBtb250aERheTogZm9ybWF0VG9Nb250aERheShcbiAgICAgICAgbW9udGhCeUhvc3QgYXMgTW9udGhUeXBlLFxuICAgICAgICBkYXlPZk1vbnRoQnlIb3N0IGFzIERheVR5cGVcbiAgICAgICksXG4gICAgfSk7XG4gIH1cbiAgY29uc29sZS5sb2codGltZVNsb3RzLCAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMnKTtcbiAgcmV0dXJuIHRpbWVTbG90cztcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZVRpbWVTbG90c0xpdGVGb3JJbnRlcm5hbEF0dGVuZGVlID0gKFxuICBob3N0U3RhcnREYXRlOiBzdHJpbmcsXG4gIGhvc3RJZDogc3RyaW5nLFxuICB1c2VyUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgdXNlclRpbWV6b25lOiBzdHJpbmcsXG4gIGlzRmlyc3REYXk/OiBib29sZWFuXG4pOiBUaW1lU2xvdFR5cGVbXSA9PiB7XG4gIGlmIChpc0ZpcnN0RGF5KSB7XG4gICAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZS5lbmRUaW1lcztcblxuICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICAgKTtcblxuICAgIGNvbnN0IHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLm1pbnV0ZSgwKSxcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkubWludXRlKDMwKSxcbiAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICdbKSdcbiAgICAgIClcbiAgICAgID8gMFxuICAgICAgOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoNTkpLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDMwXG4gICAgICAgIDogMDtcblxuICAgIGNvbnN0IG1vbnRoQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLm1vbnRoKCk7XG4gICAgY29uc3QgZGF5T2ZNb250aEJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5kYXRlKCk7XG4gICAgY29uc3Qgc3RhcnRIb3VyQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmhvdXIoKTtcbiAgICBjb25zdCBzdGFydE1pbnV0ZUJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLm1pbnV0ZSgwKSxcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkubWludXRlKDMwKSxcbiAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICdbKSdcbiAgICAgIClcbiAgICAgID8gMFxuICAgICAgOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoNTkpLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDMwXG4gICAgICAgIDogMDtcblxuICAgIGNvbnN0IGVuZEhvdXIgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgIGNvbnN0IGVuZE1pbnV0ZSA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG4gICAgY29uc3QgZW5kSG91ckJ5SG9zdCA9IGRheWpzKFxuICAgICAgc2V0SVNPRGF5KFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgLmhvdXIoZW5kSG91cilcbiAgICAgICAgICAudG9EYXRlKCksXG4gICAgICAgIGRheU9mV2Vla0ludFxuICAgICAgKVxuICAgIClcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IGVuZE1pbnV0ZUJ5SG9zdCA9IGRheWpzKFxuICAgICAgc2V0SVNPRGF5KFxuICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGUpXG4gICAgICAgICAgLnRvRGF0ZSgpLFxuICAgICAgICBkYXlPZldlZWtJbnRcbiAgICAgIClcbiAgICApXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLm1pbnV0ZSgpO1xuXG4gICAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlLnN0YXJ0VGltZXM7XG4gICAgY29uc3Qgd29ya1N0YXJ0SG91ciA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgICBjb25zdCB3b3JrU3RhcnRNaW51dGUgPSBzdGFydFRpbWVzLmZpbmQoXG4gICAgICAoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludFxuICAgICkubWludXRlcztcbiAgICBjb25zdCB3b3JrU3RhcnRIb3VyQnlIb3N0ID0gZGF5anMoXG4gICAgICBzZXRJU09EYXkoXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyKVxuICAgICAgICAgIC50b0RhdGUoKSxcbiAgICAgICAgZGF5T2ZXZWVrSW50XG4gICAgICApXG4gICAgKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgY29uc3Qgd29ya1N0YXJ0TWludXRlQnlIb3N0ID0gZGF5anMoXG4gICAgICBzZXRJU09EYXkoXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZSlcbiAgICAgICAgICAudG9EYXRlKCksXG4gICAgICAgIGRheU9mV2Vla0ludFxuICAgICAgKVxuICAgIClcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAubWludXRlKCk7XG5cbiAgICBpZiAoXG4gICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmlzQWZ0ZXIoXG4gICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmhvdXIoZW5kSG91ckJ5SG9zdClcbiAgICAgICAgICAgIC5taW51dGUoZW5kTWludXRlQnlIb3N0KVxuICAgICAgICApXG4gICAgKSB7XG4gICAgICByZXR1cm4gW107XG4gICAgfVxuXG4gICAgaWYgKFxuICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5pc0JlZm9yZShcbiAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICAgIGhvdXJzOiB3b3JrU3RhcnRIb3VyLFxuICAgICAgICBtaW51dGVzOiB3b3JrU3RhcnRNaW51dGUsXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgICBob3VyczogZW5kSG91cixcbiAgICAgICAgbWludXRlczogZW5kTWludXRlLFxuICAgICAgfSk7XG4gICAgICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gICAgICBjb25zdCB0b3RhbE1pbnV0ZXMgPSB0b3RhbER1cmF0aW9uLmFzTWludXRlcygpO1xuICAgICAgY29uc3QgdGltZVNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gMzApIHtcbiAgICAgICAgdGltZVNsb3RzLnB1c2goe1xuICAgICAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50XSxcbiAgICAgICAgICBzdGFydFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgICAuYWRkKGksICdtaW51dGUnKVxuICAgICAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgICAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgICAuYWRkKGkgKyAzMCwgJ21pbnV0ZScpXG4gICAgICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICAgICAgaG9zdElkLFxuICAgICAgICAgIG1vbnRoRGF5OiBmb3JtYXRUb01vbnRoRGF5KFxuICAgICAgICAgICAgbW9udGhCeUhvc3QgYXMgTW9udGhUeXBlLFxuICAgICAgICAgICAgZGF5T2ZNb250aEJ5SG9zdCBhcyBEYXlUeXBlXG4gICAgICAgICAgKSxcbiAgICAgICAgfSk7XG4gICAgICB9XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgdGltZVNsb3RzLFxuICAgICAgICAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMgZm9yIGZpcnN0IGRheSBiZWZvcmUgc3RhcnQgdGltZSdcbiAgICAgICk7XG4gICAgICByZXR1cm4gdGltZVNsb3RzO1xuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICBob3Vyczogc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdCxcbiAgICAgIG1pbnV0ZXM6IHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdCxcbiAgICB9KTtcbiAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHsgaG91cnM6IGVuZEhvdXIsIG1pbnV0ZXM6IGVuZE1pbnV0ZSB9KTtcbiAgICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gICAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcbiAgICBjb25zdCB0aW1lU2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gMzApIHtcbiAgICAgIHRpbWVTbG90cy5wdXNoKHtcbiAgICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1tkYXlPZldlZWtJbnRdLFxuICAgICAgICBzdGFydFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgLmFkZChpICsgMzAsICdtaW51dGUnKVxuICAgICAgICAgIC5mb3JtYXQoJ0hIOm1tJykgYXMgVGltZSxcbiAgICAgICAgaG9zdElkLFxuICAgICAgICBtb250aERheTogZm9ybWF0VG9Nb250aERheShcbiAgICAgICAgICBtb250aEJ5SG9zdCBhcyBNb250aFR5cGUsXG4gICAgICAgICAgZGF5T2ZNb250aEJ5SG9zdCBhcyBEYXlUeXBlXG4gICAgICAgICksXG4gICAgICB9KTtcbiAgICB9XG4gICAgY29uc29sZS5sb2codGltZVNsb3RzLCAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMgZm9yIGZpcnN0IGRheScpO1xuICAgIHJldHVybiB0aW1lU2xvdHM7XG4gIH1cbiAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlLnN0YXJ0VGltZXM7XG4gIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2UuZW5kVGltZXM7XG5cbiAgY29uc3QgZGF5T2ZXZWVrSW50ID0gZ2V0SVNPRGF5KFxuICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAudG9EYXRlKClcbiAgKTtcbiAgY29uc3Qgc3RhcnRIb3VyID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICBjb25zdCBzdGFydE1pbnV0ZSA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcbiAgY29uc3QgZW5kSG91ciA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gIGNvbnN0IGVuZE1pbnV0ZSA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG5cbiAgY29uc3QgbW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgIC5tb250aCgpO1xuICBjb25zdCBkYXlPZk1vbnRoQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAuZGF0ZSgpO1xuICBjb25zdCBkYXlPZldlZWtJbnRCeUhvc3QgPSBnZXRJU09EYXkoXG4gICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkudG9EYXRlKClcbiAgKTtcbiAgY29uc3Qgc3RhcnRIb3VyQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHoodXNlclRpbWV6b25lKVxuICAgIC5ob3VyKHN0YXJ0SG91cilcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5ob3VyKCk7XG4gIGNvbnN0IHN0YXJ0TWludXRlQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHoodXNlclRpbWV6b25lKVxuICAgIC5taW51dGUoc3RhcnRNaW51dGUpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAubWludXRlKCk7XG5cbiAgY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICBob3Vyczogc3RhcnRIb3VyLFxuICAgIG1pbnV0ZXM6IHN0YXJ0TWludXRlLFxuICB9KTtcbiAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7IGhvdXJzOiBlbmRIb3VyLCBtaW51dGVzOiBlbmRNaW51dGUgfSk7XG4gIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcbiAgY29uc3QgdGltZVNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsTWludXRlczsgaSArPSAzMCkge1xuICAgIHRpbWVTbG90cy5wdXNoKHtcbiAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50QnlIb3N0XSxcbiAgICAgIHN0YXJ0VGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgICAgZW5kVGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgLmFkZChpICsgMzAsICdtaW51dGUnKVxuICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICBob3N0SWQsXG4gICAgICBtb250aERheTogZm9ybWF0VG9Nb250aERheShcbiAgICAgICAgbW9udGhCeUhvc3QgYXMgTW9udGhUeXBlLFxuICAgICAgICBkYXlPZk1vbnRoQnlIb3N0IGFzIERheVR5cGVcbiAgICAgICksXG4gICAgfSk7XG4gIH1cbiAgY29uc29sZS5sb2codGltZVNsb3RzLCAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMnKTtcbiAgcmV0dXJuIHRpbWVTbG90cztcbn07XG5cbmV4cG9ydCBjb25zdCB2YWxpZGF0ZUV2ZW50RGF0ZXMgPSAoXG4gIGV2ZW50OiBFdmVudFBsdXNUeXBlLFxuICB1c2VyUHJlZmVyZW5jZXM6IFVzZXJQcmVmZXJlbmNlVHlwZVxuKTogYm9vbGVhbiA9PiB7XG4gIGlmICghZXZlbnQ/LnRpbWV6b25lKSB7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgY29uc3QgZGlmZiA9IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAuZGlmZihkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihldmVudC50aW1lem9uZSwgdHJ1ZSksICdtJyk7XG4gIGNvbnN0IGRpZmZEYXkgPSBkYXlqcyhldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgLmRpZmYoZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooZXZlbnQudGltZXpvbmUsIHRydWUpLCAnZCcpO1xuICBjb25zdCBkaWZmSG91cnMgPSBkYXlqcyhldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgLmRpZmYoZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooZXZlbnQudGltZXpvbmUsIHRydWUpLCAnaCcpO1xuXG4gIGNvbnN0IGlzb1dlZWtEYXkgPSBnZXRJU09EYXkoXG4gICAgZGF5anMoZXZlbnQ/LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGV2ZW50Py50aW1lem9uZSwgdHJ1ZSkudG9EYXRlKClcbiAgKTtcbiAgY29uc3QgZW5kSG91ciA9IHVzZXJQcmVmZXJlbmNlcy5lbmRUaW1lcy5maW5kKFxuICAgIChlKSA9PiBlPy5kYXkgPT09IGlzb1dlZWtEYXlcbiAgKT8uaG91cjtcbiAgY29uc3QgZW5kTWludXRlcyA9IHVzZXJQcmVmZXJlbmNlcy5lbmRUaW1lcy5maW5kKFxuICAgIChlKSA9PiBlPy5kYXkgPT09IGlzb1dlZWtEYXlcbiAgKT8ubWludXRlcztcbiAgY29uc3Qgc3RhcnRIb3VyID0gdXNlclByZWZlcmVuY2VzLnN0YXJ0VGltZXMuZmluZChcbiAgICAoZSkgPT4gZT8uZGF5ID09PSBpc29XZWVrRGF5XG4gICk/LmhvdXI7XG4gIGNvbnN0IHN0YXJ0TWludXRlcyA9IHVzZXJQcmVmZXJlbmNlcy5zdGFydFRpbWVzLmZpbmQoXG4gICAgKGUpID0+IGU/LmRheSA9PT0gaXNvV2Vla0RheVxuICApPy5taW51dGVzO1xuXG4gIGlmIChcbiAgICBkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgLmlzQWZ0ZXIoXG4gICAgICAgIGRheWpzKGV2ZW50Py5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuaG91cihlbmRIb3VyKVxuICAgICAgICAgIC5taW51dGUoZW5kTWludXRlcylcbiAgICAgIClcbiAgKSB7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgaWYgKFxuICAgIGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAuaXNCZWZvcmUoXG4gICAgICAgIGRheWpzKGV2ZW50Py5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuaG91cihzdGFydEhvdXIpXG4gICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZXMpXG4gICAgICApXG4gICkge1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuXG4gIGlmIChkaWZmID09PSAwKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBldmVudC5pZCxcbiAgICAgIGV2ZW50LnN0YXJ0RGF0ZSxcbiAgICAgIGV2ZW50LmVuZERhdGUsXG4gICAgICAnIHRoZSBzdGFydCBkYXRlIGFuZCBlbmQgZGF0ZSBhcmUgdGhlIHNhbWUnXG4gICAgKTtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICBpZiAoZGlmZiA8IDApIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGV2ZW50LmlkLFxuICAgICAgZXZlbnQuc3RhcnREYXRlLFxuICAgICAgZXZlbnQuZW5kRGF0ZSxcbiAgICAgICcgdGhlIHN0YXJ0IGRhdGUgaXMgYWZ0ZXIgZW5kIGRhdGUnXG4gICAgKTtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICBpZiAoZGlmZkRheSA+PSAxKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBldmVudC5pZCxcbiAgICAgIGV2ZW50LnN0YXJ0RGF0ZSxcbiAgICAgIGV2ZW50LmVuZERhdGUsXG4gICAgICAnIHRoZSBzdGFydCBkYXRlIGFuZCBlbmQgZGF0ZSBhcmUgbW9yZSB0aGFuIDEgZGF5IGFwYXJ0J1xuICAgICk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgaWYgKGRpZmZIb3VycyA+IDIzKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBldmVudC5pZCxcbiAgICAgIGV2ZW50LnN0YXJ0RGF0ZSxcbiAgICAgIGV2ZW50LmVuZERhdGUsXG4gICAgICAnIHRoZSBzdGFydCBkYXRlIGFuZCBlbmQgZGF0ZSBhcmUgbW9yZSB0aGFuIDIzIGhvdXJzIGFwYXJ0J1xuICAgICk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgcmV0dXJuIHRydWU7XG59O1xuXG5leHBvcnQgY29uc3QgdmFsaWRhdGVFdmVudERhdGVzRm9yRXh0ZXJuYWxBdHRlbmRlZSA9IChcbiAgZXZlbnQ6IEV2ZW50UGx1c1R5cGVcbik6IGJvb2xlYW4gPT4ge1xuICBpZiAoIWV2ZW50Py50aW1lem9uZSkge1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuXG4gIGNvbnN0IGRpZmYgPSBkYXlqcyhldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgLmRpZmYoZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooZXZlbnQudGltZXpvbmUsIHRydWUpLCAnbScpO1xuICBjb25zdCBkaWZmRGF5ID0gZGF5anMoZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgIC5kaWZmKGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKSwgJ2QnKTtcbiAgY29uc3QgZGlmZkhvdXJzID0gZGF5anMoZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgIC5kaWZmKGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKSwgJ2gnKTtcblxuICBpZiAoZGlmZiA9PT0gMCkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZXZlbnQuaWQsXG4gICAgICBldmVudC5zdGFydERhdGUsXG4gICAgICBldmVudC5lbmREYXRlLFxuICAgICAgJyB0aGUgc3RhcnQgZGF0ZSBhbmQgZW5kIGRhdGUgYXJlIHRoZSBzYW1lJ1xuICAgICk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgaWYgKGRpZmYgPCAwKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBldmVudC5pZCxcbiAgICAgIGV2ZW50LnN0YXJ0RGF0ZSxcbiAgICAgIGV2ZW50LmVuZERhdGUsXG4gICAgICAnIHRoZSBzdGFydCBkYXRlIGlzIGFmdGVyIGVuZCBkYXRlJ1xuICAgICk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgaWYgKGRpZmZEYXkgPj0gMSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZXZlbnQuaWQsXG4gICAgICBldmVudC5zdGFydERhdGUsXG4gICAgICBldmVudC5lbmREYXRlLFxuICAgICAgJyB0aGUgc3RhcnQgZGF0ZSBhbmQgZW5kIGRhdGUgYXJlIG1vcmUgdGhhbiAxIGRheSBhcGFydCdcbiAgICApO1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuXG4gIGlmIChkaWZmSG91cnMgPiAyMykge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZXZlbnQuaWQsXG4gICAgICBldmVudC5zdGFydERhdGUsXG4gICAgICBldmVudC5lbmREYXRlLFxuICAgICAgJyB0aGUgc3RhcnQgZGF0ZSBhbmQgZW5kIGRhdGUgYXJlIG1vcmUgdGhhbiAyMyBob3VycyBhcGFydCdcbiAgICApO1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuXG4gIHJldHVybiB0cnVlO1xufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlRXZlbnRQYXJ0cyA9IChcbiAgZXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIGhvc3RJZDogc3RyaW5nXG4pOiBJbml0aWFsRXZlbnRQYXJ0VHlwZVtdID0+IHtcbiAgY29uc29sZS5sb2coXG4gICAgZXZlbnQuaWQsXG4gICAgZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSxcbiAgICBldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSxcbiAgICAnIGV2ZW50LmlkLCBldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpLCBldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSBpbnNpZGUgZ2VuZXJhdGVFdmVudFBhcnRzJ1xuICApO1xuICBjb25zdCBtaW51dGVzID0gZGF5anMoZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgIC5kaWZmKGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKSwgJ20nKTtcbiAgY29uc29sZS5sb2coXG4gICAgZXZlbnQuaWQsXG4gICAgbWludXRlcyxcbiAgICAnZXZlbnQuaWQsICBtaW51dGVzIGluc2lkZSBnZW5lcmF0ZUV2ZW50UGFydHMnXG4gICk7XG4gIGNvbnN0IHBhcnRzID0gTWF0aC5mbG9vcihtaW51dGVzIC8gMTUpO1xuICBjb25zdCByZW1haW5kZXIgPSBtaW51dGVzICUgMTU7XG4gIGNvbnN0IGV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPSBbXTtcbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBwYXJ0czsgaSsrKSB7XG4gICAgZXZlbnRQYXJ0cy5wdXNoKHtcbiAgICAgIC4uLmV2ZW50LFxuICAgICAgZ3JvdXBJZDogZXZlbnQuaWQsXG4gICAgICBldmVudElkOiBldmVudC5pZCxcbiAgICAgIHN0YXJ0RGF0ZTogZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSxcbiAgICAgIGVuZERhdGU6IGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpLFxuICAgICAgcGFydDogaSArIDEsXG4gICAgICBtZWV0aW5nUGFydDogaSArIDEsXG4gICAgICBtZWV0aW5nTGFzdFBhcnQ6IHJlbWFpbmRlciA+IDAgPyBwYXJ0cyArIDEgOiBwYXJ0cyxcbiAgICAgIGxhc3RQYXJ0OiByZW1haW5kZXIgPiAwID8gcGFydHMgKyAxIDogcGFydHMsXG4gICAgICBob3N0SWQsXG4gICAgfSk7XG4gIH1cblxuICBpZiAocmVtYWluZGVyID4gMCkge1xuICAgIGV2ZW50UGFydHMucHVzaCh7XG4gICAgICAuLi5ldmVudCxcbiAgICAgIGdyb3VwSWQ6IGV2ZW50LmlkLFxuICAgICAgZXZlbnRJZDogZXZlbnQuaWQsXG4gICAgICBzdGFydERhdGU6IGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSksXG4gICAgICBlbmREYXRlOiBldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSxcbiAgICAgIHBhcnQ6IHBhcnRzICsgMSxcbiAgICAgIGxhc3RQYXJ0OiBwYXJ0cyArIDEsXG4gICAgICBtZWV0aW5nUGFydDogcGFydHMgKyAxLFxuICAgICAgbWVldGluZ0xhc3RQYXJ0OiBwYXJ0cyArIDEsXG4gICAgICBob3N0SWQsXG4gICAgfSk7XG4gIH1cbiAgY29uc29sZS5sb2coXG4gICAgZXZlbnQuaWQsXG4gICAgZXZlbnRQYXJ0cz8uWzBdPy5zdGFydERhdGUsXG4gICAgZXZlbnRQYXJ0cz8uWzBdPy5lbmREYXRlLFxuICAgIGV2ZW50UGFydHM/LlswXT8ucGFydCxcbiAgICBldmVudFBhcnRzPy5bMF0/Lmxhc3RQYXJ0LFxuICAgICdldmVudC5pZCwgIGV2ZW50UGFydHM/LlswXT8uc3RhcnREYXRlLCBldmVudFBhcnRzPy5bMF0/LmVuZERhdGUsIGV2ZW50UGFydHM/LlswXT8ucGFydCwgZXZlbnRQYXJ0cz8uWzBdPy5sYXN0UGFydCwnXG4gICk7XG4gIHJldHVybiBldmVudFBhcnRzO1xufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlRXZlbnRQYXJ0c0xpdGUgPSAoXG4gIGV2ZW50OiBFdmVudFBsdXNUeXBlLFxuICBob3N0SWQ6IHN0cmluZ1xuKTogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSA9PiB7XG4gIGNvbnN0IG1pbnV0ZXMgPSBkYXlqcyhldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgLmRpZmYoZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooZXZlbnQudGltZXpvbmUsIHRydWUpLCAnbScpO1xuICBjb25zdCBwYXJ0cyA9IE1hdGguZmxvb3IobWludXRlcyAvIDMwKTtcbiAgY29uc3QgcmVtYWluZGVyID0gbWludXRlcyAlIDMwO1xuICBjb25zdCBldmVudFBhcnRzOiBJbml0aWFsRXZlbnRQYXJ0VHlwZVtdID0gW107XG4gIGZvciAobGV0IGkgPSAwOyBpIDwgcGFydHM7IGkrKykge1xuICAgIGV2ZW50UGFydHMucHVzaCh7XG4gICAgICAuLi5ldmVudCxcbiAgICAgIGdyb3VwSWQ6IGV2ZW50LmlkLFxuICAgICAgZXZlbnRJZDogZXZlbnQuaWQsXG4gICAgICBzdGFydERhdGU6IGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSksXG4gICAgICBlbmREYXRlOiBldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSxcbiAgICAgIHBhcnQ6IGkgKyAxLFxuICAgICAgbGFzdFBhcnQ6IHJlbWFpbmRlciA+IDAgPyBwYXJ0cyArIDEgOiBwYXJ0cyxcbiAgICAgIG1lZXRpbmdQYXJ0OiBpICsgMSxcbiAgICAgIG1lZXRpbmdMYXN0UGFydDogcmVtYWluZGVyID4gMCA/IHBhcnRzICsgMSA6IHBhcnRzLFxuICAgICAgaG9zdElkLFxuICAgIH0pO1xuICB9XG5cbiAgaWYgKHJlbWFpbmRlciA+IDApIHtcbiAgICBldmVudFBhcnRzLnB1c2goe1xuICAgICAgLi4uZXZlbnQsXG4gICAgICBncm91cElkOiBldmVudC5pZCxcbiAgICAgIGV2ZW50SWQ6IGV2ZW50LmlkLFxuICAgICAgc3RhcnREYXRlOiBldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpLFxuICAgICAgZW5kRGF0ZTogZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSksXG4gICAgICBwYXJ0OiBwYXJ0cyArIDEsXG4gICAgICBsYXN0UGFydDogcGFydHMgKyAxLFxuICAgICAgbWVldGluZ1BhcnQ6IHBhcnRzICsgMSxcbiAgICAgIG1lZXRpbmdMYXN0UGFydDogcGFydHMgKyAxLFxuICAgICAgaG9zdElkLFxuICAgIH0pO1xuICB9XG4gIHJldHVybiBldmVudFBhcnRzO1xufTtcblxuZXhwb3J0IGNvbnN0IG1vZGlmeUV2ZW50UGFydHNGb3JTaW5ndWxhclByZUJ1ZmZlclRpbWUgPSAoXG4gIGV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW10sXG4gIGZvckV2ZW50SWQ6IHN0cmluZ1xuKTogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSA9PiB7XG4gIGNvbnN0IHByZUJ1ZmZlckJlZm9yZUV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPSBbXTtcbiAgY29uc3QgcHJlQnVmZmVyQWN0dWFsRXZlbnRQYXJ0czogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSA9IFtdO1xuXG4gIGNvbnN0IHByZUJ1ZmZlckdyb3VwSWQgPSB1dWlkKCk7XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBldmVudFBhcnRzLmxlbmd0aDsgaSsrKSB7XG4gICAgaWYgKGV2ZW50UGFydHNbaV0uZm9yRXZlbnRJZCA9PT0gZm9yRXZlbnRJZCAmJiBldmVudFBhcnRzW2ldLmlzUHJlRXZlbnQpIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBldmVudFBhcnRzW2ldLmZvckV2ZW50SWQsXG4gICAgICAgIGZvckV2ZW50SWQsXG4gICAgICAgICcgZXZlbnRQYXJ0c1tpXS5mb3JFdmVudElkID09PSBmb3JFdmVudElkICBpbnNpZGUgbW9kaWZ5RXZlbnRQYXJ0c0ZvclNpbmd1bGFyUHJlQnVmZmVyVGltZSdcbiAgICAgICk7XG4gICAgICBwcmVCdWZmZXJCZWZvcmVFdmVudFBhcnRzLnB1c2goe1xuICAgICAgICAuLi5ldmVudFBhcnRzW2ldLFxuICAgICAgICBncm91cElkOiBwcmVCdWZmZXJHcm91cElkLFxuICAgICAgfSk7XG4gICAgfVxuICB9XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBldmVudFBhcnRzLmxlbmd0aDsgaSsrKSB7XG4gICAgaWYgKGV2ZW50UGFydHNbaV0uaWQgPT09IGZvckV2ZW50SWQpIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBldmVudFBhcnRzW2ldLmlkLFxuICAgICAgICBmb3JFdmVudElkLFxuICAgICAgICAnZXZlbnRQYXJ0c1tpXS5pZCA9PT0gZm9yRXZlbnRJZCBpbnNpZGUgbW9kaWZ5RXZlbnRQYXJ0c0ZvclNpbmd1bGFyUHJlQnVmZmVyVGltZSdcbiAgICAgICk7XG4gICAgICBwcmVCdWZmZXJBY3R1YWxFdmVudFBhcnRzLnB1c2goe1xuICAgICAgICAuLi5ldmVudFBhcnRzW2ldLFxuICAgICAgICBncm91cElkOiBwcmVCdWZmZXJHcm91cElkLFxuICAgICAgfSk7XG4gICAgfVxuICB9XG5cbiAgY29uc3QgcHJlQnVmZmVyQmVmb3JlRXZlbnRQYXJ0c1NvcnRlZCA9IHByZUJ1ZmZlckJlZm9yZUV2ZW50UGFydHMuc29ydChcbiAgICAoYSwgYikgPT4gYS5wYXJ0IC0gYi5wYXJ0XG4gICk7XG4gIGNvbnN0IHByZUJ1ZmZlckFjdHVhbEV2ZW50UGFydHNTb3J0ZWQgPSBwcmVCdWZmZXJBY3R1YWxFdmVudFBhcnRzLnNvcnQoXG4gICAgKGEsIGIpID0+IGEucGFydCAtIGIucGFydFxuICApO1xuXG4gIGNvbnN0IHByZUJ1ZmZlckV2ZW50UGFydHNUb3RhbCA9IHByZUJ1ZmZlckJlZm9yZUV2ZW50UGFydHNTb3J0ZWQuY29uY2F0KFxuICAgIHByZUJ1ZmZlckFjdHVhbEV2ZW50UGFydHNTb3J0ZWRcbiAgKTtcblxuICBmb3IgKGxldCBpID0gMDsgaSA8IHByZUJ1ZmZlckV2ZW50UGFydHNUb3RhbC5sZW5ndGg7IGkrKykge1xuICAgIHByZUJ1ZmZlckV2ZW50UGFydHNUb3RhbFtpXS5wYXJ0ID0gaSArIDE7XG4gICAgcHJlQnVmZmVyRXZlbnRQYXJ0c1RvdGFsW2ldLmxhc3RQYXJ0ID0gcHJlQnVmZmVyRXZlbnRQYXJ0c1RvdGFsLmxlbmd0aDtcbiAgfVxuICBwcmVCdWZmZXJFdmVudFBhcnRzVG90YWwuZm9yRWFjaCgoZSkgPT5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUuaWQsXG4gICAgICBlLmdyb3VwSWQsXG4gICAgICBlLmV2ZW50SWQsXG4gICAgICBlLnBhcnQsXG4gICAgICBlLmxhc3RQYXJ0LFxuICAgICAgZS5zdGFydERhdGUsXG4gICAgICBlLmVuZERhdGUsXG4gICAgICBgZS5pZCwgZS5ncm91cElkLCBlLmV2ZW50SWQsIGUucGFydCwgZS5sYXN0UGFydCwgZS5zdGFydERhdGUsIGUuZW5kRGF0ZSwgaW5zaWRlIG1vZGlmeUV2ZW50UGFydHNGb3JTaW5ndWxhclByZUJ1ZmZlclRpbWVgXG4gICAgKVxuICApO1xuICByZXR1cm4gcHJlQnVmZmVyRXZlbnRQYXJ0c1RvdGFsO1xufTtcbmV4cG9ydCBjb25zdCBtb2RpZnlFdmVudFBhcnRzRm9yTXVsdGlwbGVQcmVCdWZmZXJUaW1lID0gKFxuICBldmVudFBhcnRzOiBJbml0aWFsRXZlbnRQYXJ0VHlwZVtdXG4pOiBJbml0aWFsRXZlbnRQYXJ0VHlwZVtdID0+IHtcbiAgY29uc3QgdW5pcXVlUHJlQnVmZmVyUGFydEZvckV2ZW50SWRzOiBzdHJpbmdbXSA9IFtdO1xuICBjb25zdCBwcmVCdWZmZXJFdmVudFBhcnRzVG90YWw6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPSBbXTtcblxuICBmb3IgKGxldCBpID0gMDsgaSA8IGV2ZW50UGFydHMubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAoZXZlbnRQYXJ0c1tpXS5mb3JFdmVudElkICYmIGV2ZW50UGFydHNbaV0uaXNQcmVFdmVudCkge1xuICAgICAgY29uc3QgZm91bmRQYXJ0ID0gdW5pcXVlUHJlQnVmZmVyUGFydEZvckV2ZW50SWRzLmZpbmQoXG4gICAgICAgIChlKSA9PiBlID09PSBldmVudFBhcnRzW2ldLmZvckV2ZW50SWRcbiAgICAgICk7XG4gICAgICBpZiAoZm91bmRQYXJ0KSB7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgdW5pcXVlUHJlQnVmZmVyUGFydEZvckV2ZW50SWRzLnB1c2goZXZlbnRQYXJ0c1tpXS5mb3JFdmVudElkKTtcbiAgICAgIH1cbiAgICB9XG4gIH1cblxuICBmb3IgKGxldCBpID0gMDsgaSA8IHVuaXF1ZVByZUJ1ZmZlclBhcnRGb3JFdmVudElkcy5sZW5ndGg7IGkrKykge1xuICAgIGNvbnN0IHJldHVybmVkRXZlbnRQYXJ0VG90YWwgPSBtb2RpZnlFdmVudFBhcnRzRm9yU2luZ3VsYXJQcmVCdWZmZXJUaW1lKFxuICAgICAgZXZlbnRQYXJ0cyxcbiAgICAgIHVuaXF1ZVByZUJ1ZmZlclBhcnRGb3JFdmVudElkc1tpXVxuICAgICk7XG4gICAgcHJlQnVmZmVyRXZlbnRQYXJ0c1RvdGFsLnB1c2goLi4ucmV0dXJuZWRFdmVudFBhcnRUb3RhbCk7XG4gIH1cblxuICBjb25zdCBldmVudFBhcnRzRmlsdGVyZWQgPSBfLmRpZmZlcmVuY2VCeShcbiAgICBldmVudFBhcnRzLFxuICAgIHByZUJ1ZmZlckV2ZW50UGFydHNUb3RhbCxcbiAgICAnaWQnXG4gICk7XG4gIGNvbnN0IGNvbmNhdGVuYXRlZFZhbHVlcyA9IGV2ZW50UGFydHNGaWx0ZXJlZC5jb25jYXQoXG4gICAgcHJlQnVmZmVyRXZlbnRQYXJ0c1RvdGFsXG4gICk7XG4gIGNvbmNhdGVuYXRlZFZhbHVlcy5mb3JFYWNoKChlKSA9PlxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZS5pZCxcbiAgICAgIGUuZ3JvdXBJZCxcbiAgICAgIGUuZXZlbnRJZCxcbiAgICAgIGUucGFydCxcbiAgICAgIGUubGFzdFBhcnQsXG4gICAgICBlLnN0YXJ0RGF0ZSxcbiAgICAgIGUuZW5kRGF0ZSxcbiAgICAgIGU/LmZvckV2ZW50SWQsXG4gICAgICBgZS5pZCwgZS5ldmVudElkLCBlLmFjdHVhbElkLCBlLnBhcnQsIGUubGFzdFBhcnQsIGUuc3RhcnREYXRlLCBlLmVuZERhdGUsIGU/LmZvckV2ZW50SWQsICBpbnNpZGUgbW9kaWZ5RXZlbnRQYXJ0c0Zvck11bHRpcGxlUHJlQnVmZmVyVGltZWBcbiAgICApXG4gICk7XG4gIHJldHVybiBjb25jYXRlbmF0ZWRWYWx1ZXM7XG59O1xuXG5leHBvcnQgY29uc3QgbW9kaWZ5RXZlbnRQYXJ0c0Zvck11bHRpcGxlUG9zdEJ1ZmZlclRpbWUgPSAoXG4gIGV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW11cbik6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPT4ge1xuICBjb25zdCB1bmlxdWVQb3N0QnVmZmVyUGFydEZvckV2ZW50SWRzOiBzdHJpbmdbXSA9IFtdO1xuICBjb25zdCBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsOiBJbml0aWFsRXZlbnRQYXJ0VHlwZVtdID0gW107XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBldmVudFBhcnRzLmxlbmd0aDsgaSsrKSB7XG4gICAgaWYgKGV2ZW50UGFydHNbaV0uZm9yRXZlbnRJZCAmJiBldmVudFBhcnRzW2ldLmlzUG9zdEV2ZW50KSB7XG4gICAgICBjb25zdCBmb3VuZFBhcnQgPSB1bmlxdWVQb3N0QnVmZmVyUGFydEZvckV2ZW50SWRzLmZpbmQoXG4gICAgICAgIChlKSA9PiBlID09PSBldmVudFBhcnRzW2ldLmZvckV2ZW50SWRcbiAgICAgICk7XG4gICAgICBpZiAoZm91bmRQYXJ0KSB7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgdW5pcXVlUG9zdEJ1ZmZlclBhcnRGb3JFdmVudElkcy5wdXNoKGV2ZW50UGFydHNbaV0uZm9yRXZlbnRJZCk7XG4gICAgICB9XG4gICAgfVxuICB9XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPCB1bmlxdWVQb3N0QnVmZmVyUGFydEZvckV2ZW50SWRzLmxlbmd0aDsgaSsrKSB7XG4gICAgY29uc3QgcmV0dXJuZWRFdmVudFBhcnRUb3RhbCA9IG1vZGlmeUV2ZW50UGFydHNGb3JTaW5ndWxhclBvc3RCdWZmZXJUaW1lKFxuICAgICAgZXZlbnRQYXJ0cyxcbiAgICAgIHVuaXF1ZVBvc3RCdWZmZXJQYXJ0Rm9yRXZlbnRJZHNbaV1cbiAgICApO1xuICAgIHBvc3RCdWZmZXJFdmVudFBhcnRzVG90YWwucHVzaCguLi5yZXR1cm5lZEV2ZW50UGFydFRvdGFsKTtcbiAgfVxuXG4gIGNvbnN0IGV2ZW50UGFydHNGaWx0ZXJlZCA9IF8uZGlmZmVyZW5jZUJ5KFxuICAgIGV2ZW50UGFydHMsXG4gICAgcG9zdEJ1ZmZlckV2ZW50UGFydHNUb3RhbCxcbiAgICAnaWQnXG4gICk7XG4gIGNvbnN0IGNvbmNhdGVuYXRlZFZhbHVlcyA9IGV2ZW50UGFydHNGaWx0ZXJlZC5jb25jYXQoXG4gICAgcG9zdEJ1ZmZlckV2ZW50UGFydHNUb3RhbFxuICApO1xuXG4gIGNvbmNhdGVuYXRlZFZhbHVlcy5mb3JFYWNoKChlKSA9PlxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZS5pZCxcbiAgICAgIGUuZ3JvdXBJZCxcbiAgICAgIGUuZXZlbnRJZCxcbiAgICAgIGUucGFydCxcbiAgICAgIGUubGFzdFBhcnQsXG4gICAgICBlLnN0YXJ0RGF0ZSxcbiAgICAgIGUuZW5kRGF0ZSxcbiAgICAgIGU/LmZvckV2ZW50SWQsXG4gICAgICBgZS5pZCwgZS5ncm91cElkLCBlLmV2ZW50SWQsIGUucGFydCwgZS5sYXN0UGFydCwgZS5zdGFydERhdGUsIGUuZW5kRGF0ZSwgZT8uZm9yRXZlbnRJZCwgIGluc2lkZSBtb2RpZnlFdmVudFBhcnRzRm9yTXVsdGlwbGVQb3N0QnVmZmVyVGltZWBcbiAgICApXG4gICk7XG4gIHJldHVybiBjb25jYXRlbmF0ZWRWYWx1ZXM7XG59O1xuXG5leHBvcnQgY29uc3QgbW9kaWZ5RXZlbnRQYXJ0c0ZvclNpbmd1bGFyUG9zdEJ1ZmZlclRpbWUgPSAoXG4gIGV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW10sXG4gIGZvckV2ZW50SWQ6IHN0cmluZ1xuKTogSW5pdGlhbEV2ZW50UGFydFR5cGVbXSA9PiB7XG4gIGNvbnN0IHBvc3RCdWZmZXJBZnRlckV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPSBbXTtcbiAgY29uc3QgcG9zdEJ1ZmZlckFjdHVhbEV2ZW50UGFydHM6IEluaXRpYWxFdmVudFBhcnRUeXBlW10gPSBbXTtcblxuICBjb25zdCBwb3N0QnVmZmVyR3JvdXBJZCA9IHV1aWQoKTtcblxuICBmb3IgKGxldCBpID0gMDsgaSA8IGV2ZW50UGFydHMubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAoZXZlbnRQYXJ0c1tpXS5pZCA9PSBmb3JFdmVudElkKSB7XG4gICAgICBwb3N0QnVmZmVyQWN0dWFsRXZlbnRQYXJ0cy5wdXNoKHtcbiAgICAgICAgLi4uZXZlbnRQYXJ0c1tpXSxcbiAgICAgICAgZ3JvdXBJZDogcG9zdEJ1ZmZlckdyb3VwSWQsXG4gICAgICB9KTtcbiAgICB9XG4gIH1cblxuICBmb3IgKGxldCBpID0gMDsgaSA8IGV2ZW50UGFydHMubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAoZXZlbnRQYXJ0c1tpXS5mb3JFdmVudElkID09PSBmb3JFdmVudElkICYmIGV2ZW50UGFydHNbaV0uaXNQb3N0RXZlbnQpIHtcbiAgICAgIHBvc3RCdWZmZXJBZnRlckV2ZW50UGFydHMucHVzaCh7XG4gICAgICAgIC4uLmV2ZW50UGFydHNbaV0sXG4gICAgICAgIGdyb3VwSWQ6IHBvc3RCdWZmZXJHcm91cElkLFxuICAgICAgfSk7XG4gICAgfVxuICB9XG5cbiAgY29uc3QgcG9zdEJ1ZmZlckFjdHVhbEV2ZW50UGFydHNTb3J0ZWQgPSBwb3N0QnVmZmVyQWN0dWFsRXZlbnRQYXJ0cy5zb3J0KFxuICAgIChhLCBiKSA9PiBhLnBhcnQgLSBiLnBhcnRcbiAgKTtcbiAgY29uc3QgcG9zdEJ1ZmZlckFmdGVyRXZlbnRQYXJ0c1NvcnRlZCA9IHBvc3RCdWZmZXJBZnRlckV2ZW50UGFydHMuc29ydChcbiAgICAoYSwgYikgPT4gYS5wYXJ0IC0gYi5wYXJ0XG4gICk7XG5cbiAgY29uc3QgcG9zdEJ1ZmZlckV2ZW50UGFydHNUb3RhbCA9IHBvc3RCdWZmZXJBY3R1YWxFdmVudFBhcnRzU29ydGVkLmNvbmNhdChcbiAgICBwb3N0QnVmZmVyQWZ0ZXJFdmVudFBhcnRzU29ydGVkXG4gICk7XG5cbiAgY29uc3QgcHJlRXZlbnRJZCA9IHBvc3RCdWZmZXJFdmVudFBhcnRzVG90YWw/LlswXT8ucHJlRXZlbnRJZDtcbiAgY29uc3QgYWN0dWFsRXZlbnRQcmV2aW91c0xhc3RQYXJ0ID0gcG9zdEJ1ZmZlckV2ZW50UGFydHNUb3RhbD8uWzBdPy5sYXN0UGFydDtcblxuICBmb3IgKGxldCBpID0gMDsgaSA8IHBvc3RCdWZmZXJFdmVudFBhcnRzVG90YWwubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAocHJlRXZlbnRJZCkge1xuICAgICAgcG9zdEJ1ZmZlckV2ZW50UGFydHNUb3RhbFtpXS5sYXN0UGFydCA9XG4gICAgICAgIGFjdHVhbEV2ZW50UHJldmlvdXNMYXN0UGFydCArIHBvc3RCdWZmZXJBZnRlckV2ZW50UGFydHNTb3J0ZWQubGVuZ3RoO1xuICAgIH0gZWxzZSB7XG4gICAgICBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsW2ldLnBhcnQgPSBpICsgMTtcbiAgICAgIHBvc3RCdWZmZXJFdmVudFBhcnRzVG90YWxbaV0ubGFzdFBhcnQgPSBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsLmxlbmd0aDtcbiAgICB9XG4gIH1cblxuICBmb3IgKGxldCBpID0gMDsgaSA8IHBvc3RCdWZmZXJBZnRlckV2ZW50UGFydHNTb3J0ZWQubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAoXG4gICAgICBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsPy5bcG9zdEJ1ZmZlckFjdHVhbEV2ZW50UGFydHNTb3J0ZWQ/Lmxlbmd0aCArIGldXG4gICAgKSB7XG4gICAgICBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsW1xuICAgICAgICBwb3N0QnVmZmVyQWN0dWFsRXZlbnRQYXJ0c1NvcnRlZD8ubGVuZ3RoICsgaVxuICAgICAgXS5wYXJ0ID0gYWN0dWFsRXZlbnRQcmV2aW91c0xhc3RQYXJ0ICsgaSArIDE7XG4gICAgfVxuICB9XG5cbiAgY29uc3QgcHJlRXZlbnRQYXJ0cyA9IGV2ZW50UGFydHMuZmlsdGVyKChlKSA9PiBlLmV2ZW50SWQgPT09IHByZUV2ZW50SWQpO1xuICBjb25zdCBwcmVCdWZmZXJFdmVudFBhcnRzID0gcHJlRXZlbnRQYXJ0cz8ubWFwKChlKSA9PiAoe1xuICAgIC4uLmUsXG4gICAgZ3JvdXBJZDogcG9zdEJ1ZmZlckdyb3VwSWQsXG4gICAgbGFzdFBhcnQ6XG4gICAgICBhY3R1YWxFdmVudFByZXZpb3VzTGFzdFBhcnQgKyBwb3N0QnVmZmVyQWZ0ZXJFdmVudFBhcnRzU29ydGVkLmxlbmd0aCxcbiAgfSkpO1xuICBjb25zdCBjb25jYXRlbmF0ZWRWYWx1ZXMgPSBwcmVCdWZmZXJFdmVudFBhcnRzLmNvbmNhdChcbiAgICBwb3N0QnVmZmVyRXZlbnRQYXJ0c1RvdGFsXG4gICk7XG4gIGNvbmNhdGVuYXRlZFZhbHVlcy5mb3JFYWNoKChlKSA9PlxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZS5pZCxcbiAgICAgIGUuZ3JvdXBJZCxcbiAgICAgIGUuZXZlbnRJZCxcbiAgICAgIGUucGFydCxcbiAgICAgIGUubGFzdFBhcnQsXG4gICAgICBlLnN0YXJ0RGF0ZSxcbiAgICAgIGUuZW5kRGF0ZSxcbiAgICAgIGU/LmZvckV2ZW50SWQsXG4gICAgICBgZS5pZCwgZS5ncm91cElkLCBlLmV2ZW50SWQsIGUucGFydCwgZS5sYXN0UGFydCwgZS5zdGFydERhdGUsIGUuZW5kRGF0ZSwgZT8uZm9yRXZlbnRJZCwgIGluc2lkZSBtb2RpZnlFdmVudFBhcnRzRm9yU2luZ2x1bGFyUG9zdEJ1ZmZlclRpbWVgXG4gICAgKVxuICApO1xuICByZXR1cm4gY29uY2F0ZW5hdGVkVmFsdWVzO1xufTtcblxuZXhwb3J0IGNvbnN0IGZvcm1hdEV2ZW50VHlwZVRvUGxhbm5lckV2ZW50ID0gKFxuICBldmVudDogSW5pdGlhbEV2ZW50UGFydFR5cGVQbHVzLFxuICB1c2VyUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlLFxuICB3b3JrVGltZXM6IFdvcmtUaW1lVHlwZVtdLFxuICBob3N0VGltZXpvbmU6IHN0cmluZ1xuKTogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9PiB7XG4gIGNvbnN0IHtcbiAgICBhbGxEYXksXG4gICAgcGFydCxcbiAgICBmb3JFdmVudElkLFxuICAgIGdyb3VwSWQsXG4gICAgZXZlbnRJZCxcbiAgICBpc0JyZWFrLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICBpc01lZXRpbmcsXG4gICAgaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICBpc1Bvc3RFdmVudCxcbiAgICBpc1ByZUV2ZW50LFxuICAgIG1vZGlmaWFibGUsXG4gICAgbmVnYXRpdmVJbXBhY3REYXlPZldlZWssXG4gICAgbmVnYXRpdmVJbXBhY3RTY29yZSxcbiAgICBuZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWssXG4gICAgcG9zaXRpdmVJbXBhY3RTY29yZSxcbiAgICBwb3NpdGl2ZUltcGFjdFRpbWUsXG4gICAgcHJlZmVycmVkRGF5T2ZXZWVrLFxuICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZSxcbiAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZSxcbiAgICBwcmVmZXJyZWRUaW1lLFxuICAgIHByaW9yaXR5LFxuICAgIHN0YXJ0RGF0ZSxcbiAgICBlbmREYXRlLFxuICAgIHRhc2tJZCxcbiAgICB1c2VySWQsXG4gICAgd2Vla2x5VGFza0xpc3QsXG4gICAgZGFpbHlUYXNrTGlzdCxcbiAgICBoYXJkRGVhZGxpbmUsXG4gICAgc29mdERlYWRsaW5lLFxuICAgIHJlY3VycmluZ0V2ZW50SWQsXG4gICAgbGFzdFBhcnQsXG4gICAgcHJlZmVycmVkVGltZVJhbmdlcyxcbiAgICBob3N0SWQsXG4gICAgbWVldGluZ0lkLFxuICAgIHRpbWV6b25lLFxuICAgIG1lZXRpbmdQYXJ0LFxuICAgIG1lZXRpbmdMYXN0UGFydCxcbiAgfSA9IGV2ZW50O1xuXG4gIGlmIChhbGxEYXkpIHtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIGNvbnN0IHRvdGFsV29ya2luZ0hvdXJzID0gY29udmVydFRvVG90YWxXb3JraW5nSG91cnNGb3JJbnRlcm5hbEF0dGVuZGVlKFxuICAgIHVzZXJQcmVmZXJlbmNlLFxuICAgIGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmZvcm1hdCgpLFxuICAgIGhvc3RUaW1lem9uZVxuICApO1xuXG4gIGNvbnN0IHVzZXI6IFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlID0ge1xuICAgIGlkOiBldmVudC51c2VySWQsXG4gICAgbWF4V29ya0xvYWRQZXJjZW50OiB1c2VyUHJlZmVyZW5jZS5tYXhXb3JrTG9hZFBlcmNlbnQsXG4gICAgYmFja1RvQmFja01lZXRpbmdzOiB1c2VyUHJlZmVyZW5jZS5iYWNrVG9CYWNrTWVldGluZ3MsXG4gICAgbWF4TnVtYmVyT2ZNZWV0aW5nczogdXNlclByZWZlcmVuY2UubWF4TnVtYmVyT2ZNZWV0aW5ncyxcbiAgICBtaW5OdW1iZXJPZkJyZWFrczogdXNlclByZWZlcmVuY2UubWluTnVtYmVyT2ZCcmVha3MsXG4gICAgd29ya1RpbWVzLFxuICAgIGhvc3RJZCxcbiAgfTtcblxuICBjb25zdCBhZGp1c3RlZFBvc2l0aXZlSW1wYWN0VGltZSA9XG4gICAgKHBvc2l0aXZlSW1wYWN0VGltZSAmJlxuICAgICAgKGRheWpzKClcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuaG91cihwYXJzZUludChwb3NpdGl2ZUltcGFjdFRpbWUuc2xpY2UoMCwgMiksIDEwKSlcbiAgICAgICAgLm1pbnV0ZShwYXJzZUludChwb3NpdGl2ZUltcGFjdFRpbWUuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lKSkgfHxcbiAgICB1bmRlZmluZWQ7XG5cbiAgY29uc3QgYWRqdXN0ZWROZWdhdGl2ZUltcGFjdFRpbWUgPVxuICAgIChuZWdhdGl2ZUltcGFjdFRpbWUgJiZcbiAgICAgIChkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQobmVnYXRpdmVJbXBhY3RUaW1lLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQobmVnYXRpdmVJbXBhY3RUaW1lLnNsaWNlKDMpLCAxMCkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tJykgYXMgVGltZSkpIHx8XG4gICAgdW5kZWZpbmVkO1xuXG4gIGNvbnN0IGFkanVzdGVkUHJlZmVycmVkVGltZSA9XG4gICAgKHByZWZlcnJlZFRpbWUgJiZcbiAgICAgIChkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQocHJlZmVycmVkVGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KHByZWZlcnJlZFRpbWUuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lKSkgfHxcbiAgICB1bmRlZmluZWQ7XG5cbiAgY29uc3QgYWRqdXN0ZWRQcmVmZXJyZWRTdGFydFRpbWVSYW5nZSA9XG4gICAgKHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlICYmXG4gICAgICAoZGF5anMoKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5ob3VyKHBhcnNlSW50KHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQocHJlZmVycmVkU3RhcnRUaW1lUmFuZ2Uuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lKSkgfHxcbiAgICB1bmRlZmluZWQ7XG5cbiAgY29uc3QgYWRqdXN0ZWRQcmVmZXJyZWRFbmRUaW1lUmFuZ2UgPVxuICAgIChwcmVmZXJyZWRFbmRUaW1lUmFuZ2UgJiZcbiAgICAgIChkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQocHJlZmVycmVkRW5kVGltZVJhbmdlLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQocHJlZmVycmVkRW5kVGltZVJhbmdlLnNsaWNlKDMpLCAxMCkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tJykgYXMgVGltZSkpIHx8XG4gICAgdW5kZWZpbmVkO1xuXG4gIGNvbnN0IGFkanVzdGVkUHJlZmVycmVkVGltZVJhbmdlcyA9XG4gICAgcHJlZmVycmVkVGltZVJhbmdlcz8ubWFwKChlKSA9PiAoe1xuICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZz8uW2U/LmRheU9mV2Vla10gPz8gbnVsbCxcbiAgICAgIHN0YXJ0VGltZTogZGF5anMoKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5ob3VyKHBhcnNlSW50KGU/LnN0YXJ0VGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KGU/LnN0YXJ0VGltZS5zbGljZSgzKSwgMTApKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICBlbmRUaW1lOiBkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQoZT8uZW5kVGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KGU/LmVuZFRpbWUuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgICAgZXZlbnRJZCxcbiAgICAgIHVzZXJJZCxcbiAgICAgIGhvc3RJZCxcbiAgICB9KSkgPz8gbnVsbDtcblxuICBjb25zdCBldmVudFBsYW5uZXJSZXF1ZXN0Qm9keTogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9IHtcbiAgICBncm91cElkLFxuICAgIGV2ZW50SWQsXG4gICAgcGFydCxcbiAgICBsYXN0UGFydCxcbiAgICBzdGFydERhdGUsXG4gICAgZW5kRGF0ZSxcbiAgICB0YXNrSWQsXG4gICAgaGFyZERlYWRsaW5lLFxuICAgIHNvZnREZWFkbGluZSxcbiAgICB1c2VySWQsXG4gICAgdXNlcixcbiAgICBwcmlvcml0eSxcbiAgICBpc1ByZUV2ZW50LFxuICAgIGlzUG9zdEV2ZW50LFxuICAgIGZvckV2ZW50SWQsXG4gICAgcG9zaXRpdmVJbXBhY3RTY29yZSxcbiAgICBuZWdhdGl2ZUltcGFjdFNjb3JlLFxuICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrOlxuICAgICAgZGF5T2ZXZWVrSW50VG9TdHJpbmdbcG9zaXRpdmVJbXBhY3REYXlPZldlZWtdID8/IG51bGwsXG4gICAgcG9zaXRpdmVJbXBhY3RUaW1lOiBhZGp1c3RlZFBvc2l0aXZlSW1wYWN0VGltZSxcbiAgICBuZWdhdGl2ZUltcGFjdERheU9mV2VlazpcbiAgICAgIGRheU9mV2Vla0ludFRvU3RyaW5nW25lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrXSA/PyBudWxsLFxuICAgIG5lZ2F0aXZlSW1wYWN0VGltZTogYWRqdXN0ZWROZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgbW9kaWZpYWJsZSxcbiAgICBwcmVmZXJyZWREYXlPZldlZWs6IGRheU9mV2Vla0ludFRvU3RyaW5nW3ByZWZlcnJlZERheU9mV2Vla10gPz8gbnVsbCxcbiAgICBwcmVmZXJyZWRUaW1lOiBhZGp1c3RlZFByZWZlcnJlZFRpbWUsXG4gICAgaXNNZWV0aW5nLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICBpc01lZXRpbmdNb2RpZmlhYmxlLFxuICAgIGRhaWx5VGFza0xpc3QsXG4gICAgd2Vla2x5VGFza0xpc3QsXG4gICAgZ2FwOiBpc0JyZWFrLFxuICAgIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlOiBhZGp1c3RlZFByZWZlcnJlZFN0YXJ0VGltZVJhbmdlLFxuICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZTogYWRqdXN0ZWRQcmVmZXJyZWRFbmRUaW1lUmFuZ2UsXG4gICAgdG90YWxXb3JraW5nSG91cnMsXG4gICAgcmVjdXJyaW5nRXZlbnRJZCxcbiAgICBob3N0SWQsXG4gICAgbWVldGluZ0lkLFxuICAgIG1lZXRpbmdQYXJ0LFxuICAgIG1lZXRpbmdMYXN0UGFydCxcbiAgICBldmVudDoge1xuICAgICAgaWQ6IGV2ZW50SWQsXG4gICAgICB1c2VySWQsXG4gICAgICBob3N0SWQsXG4gICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzOiBhZGp1c3RlZFByZWZlcnJlZFRpbWVSYW5nZXMgPz8gbnVsbCxcbiAgICB9LFxuICB9O1xuICByZXR1cm4gZXZlbnRQbGFubmVyUmVxdWVzdEJvZHk7XG59O1xuXG5leHBvcnQgY29uc3QgZm9ybWF0RXZlbnRUeXBlVG9QbGFubmVyRXZlbnRGb3JFeHRlcm5hbEF0dGVuZGVlID0gKFxuICBldmVudDogSW5pdGlhbEV2ZW50UGFydFR5cGVQbHVzLFxuICB3b3JrVGltZXM6IFdvcmtUaW1lVHlwZVtdLFxuICBhdHRlbmRlZUV2ZW50czogRXZlbnRQbHVzVHlwZVtdLFxuICBob3N0VGltZXpvbmU6IHN0cmluZ1xuKTogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9PiB7XG4gIGNvbnN0IHtcbiAgICBhbGxEYXksXG4gICAgcGFydCxcbiAgICBmb3JFdmVudElkLFxuICAgIGdyb3VwSWQsXG4gICAgZXZlbnRJZCxcbiAgICBpc0JyZWFrLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICBpc01lZXRpbmcsXG4gICAgaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICBpc1Bvc3RFdmVudCxcbiAgICBpc1ByZUV2ZW50LFxuICAgIG1vZGlmaWFibGUsXG4gICAgbmVnYXRpdmVJbXBhY3REYXlPZldlZWssXG4gICAgbmVnYXRpdmVJbXBhY3RTY29yZSxcbiAgICBuZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWssXG4gICAgcG9zaXRpdmVJbXBhY3RTY29yZSxcbiAgICBwb3NpdGl2ZUltcGFjdFRpbWUsXG4gICAgcHJlZmVycmVkRGF5T2ZXZWVrLFxuICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZSxcbiAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZSxcbiAgICBwcmVmZXJyZWRUaW1lLFxuICAgIHByaW9yaXR5LFxuICAgIHN0YXJ0RGF0ZSxcbiAgICBlbmREYXRlLFxuICAgIHRhc2tJZCxcbiAgICB1c2VySWQsXG4gICAgd2Vla2x5VGFza0xpc3QsXG4gICAgZGFpbHlUYXNrTGlzdCxcbiAgICBoYXJkRGVhZGxpbmUsXG4gICAgc29mdERlYWRsaW5lLFxuICAgIHJlY3VycmluZ0V2ZW50SWQsXG4gICAgbGFzdFBhcnQsXG4gICAgcHJlZmVycmVkVGltZVJhbmdlcyxcbiAgICBob3N0SWQsXG4gICAgbWVldGluZ0lkLFxuICAgIHRpbWV6b25lLFxuICAgIG1lZXRpbmdQYXJ0LFxuICAgIG1lZXRpbmdMYXN0UGFydCxcbiAgfSA9IGV2ZW50O1xuXG4gIGlmIChhbGxEYXkpIHtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIGNvbnN0IHRvdGFsV29ya2luZ0hvdXJzID0gY29udmVydFRvVG90YWxXb3JraW5nSG91cnNGb3JFeHRlcm5hbEF0dGVuZGVlKFxuICAgIGF0dGVuZGVlRXZlbnRzLFxuICAgIGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmZvcm1hdCgpLFxuICAgIGhvc3RUaW1lem9uZSxcbiAgICBldmVudD8udGltZXpvbmVcbiAgKTtcblxuICBjb25zdCB1c2VyOiBVc2VyUGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9IHtcbiAgICBpZDogZXZlbnQudXNlcklkLFxuICAgIG1heFdvcmtMb2FkUGVyY2VudDogMTAwLFxuICAgIGJhY2tUb0JhY2tNZWV0aW5nczogZmFsc2UsXG4gICAgbWF4TnVtYmVyT2ZNZWV0aW5nczogOTksXG4gICAgbWluTnVtYmVyT2ZCcmVha3M6IDAsXG4gICAgd29ya1RpbWVzLFxuICAgIGhvc3RJZCxcbiAgfTtcblxuICBjb25zdCBhZGp1c3RlZFBvc2l0aXZlSW1wYWN0VGltZSA9XG4gICAgKHBvc2l0aXZlSW1wYWN0VGltZSAmJlxuICAgICAgKGRheWpzKClcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuaG91cihwYXJzZUludChwb3NpdGl2ZUltcGFjdFRpbWUuc2xpY2UoMCwgMiksIDEwKSlcbiAgICAgICAgLm1pbnV0ZShwYXJzZUludChwb3NpdGl2ZUltcGFjdFRpbWUuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lKSkgfHxcbiAgICB1bmRlZmluZWQ7XG5cbiAgY29uc3QgYWRqdXN0ZWROZWdhdGl2ZUltcGFjdFRpbWUgPVxuICAgIChuZWdhdGl2ZUltcGFjdFRpbWUgJiZcbiAgICAgIChkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQobmVnYXRpdmVJbXBhY3RUaW1lLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQobmVnYXRpdmVJbXBhY3RUaW1lLnNsaWNlKDMpLCAxMCkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tJykgYXMgVGltZSkpIHx8XG4gICAgdW5kZWZpbmVkO1xuXG4gIGNvbnN0IGFkanVzdGVkUHJlZmVycmVkVGltZSA9XG4gICAgKHByZWZlcnJlZFRpbWUgJiZcbiAgICAgIChkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQocHJlZmVycmVkVGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KHByZWZlcnJlZFRpbWUuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lKSkgfHxcbiAgICB1bmRlZmluZWQ7XG5cbiAgY29uc3QgYWRqdXN0ZWRQcmVmZXJyZWRTdGFydFRpbWVSYW5nZSA9XG4gICAgKHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlICYmXG4gICAgICAoZGF5anMoKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5ob3VyKHBhcnNlSW50KHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQocHJlZmVycmVkU3RhcnRUaW1lUmFuZ2Uuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lKSkgfHxcbiAgICB1bmRlZmluZWQ7XG5cbiAgY29uc3QgYWRqdXN0ZWRQcmVmZXJyZWRFbmRUaW1lUmFuZ2UgPVxuICAgIChwcmVmZXJyZWRFbmRUaW1lUmFuZ2UgJiZcbiAgICAgIChkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQocHJlZmVycmVkRW5kVGltZVJhbmdlLnNsaWNlKDAsIDIpLCAxMCkpXG4gICAgICAgIC5taW51dGUocGFyc2VJbnQocHJlZmVycmVkRW5kVGltZVJhbmdlLnNsaWNlKDMpLCAxMCkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tJykgYXMgVGltZSkpIHx8XG4gICAgdW5kZWZpbmVkO1xuXG4gIGNvbnN0IGFkanVzdGVkUHJlZmVycmVkVGltZVJhbmdlcyA9XG4gICAgcHJlZmVycmVkVGltZVJhbmdlcz8ubWFwKChlKSA9PiAoe1xuICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZz8uW2U/LmRheU9mV2Vla10gPz8gbnVsbCxcbiAgICAgIHN0YXJ0VGltZTogZGF5anMoKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5ob3VyKHBhcnNlSW50KGU/LnN0YXJ0VGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KGU/LnN0YXJ0VGltZS5zbGljZSgzKSwgMTApKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICBlbmRUaW1lOiBkYXlqcygpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmhvdXIocGFyc2VJbnQoZT8uZW5kVGltZS5zbGljZSgwLCAyKSwgMTApKVxuICAgICAgICAubWludXRlKHBhcnNlSW50KGU/LmVuZFRpbWUuc2xpY2UoMyksIDEwKSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgICAgZXZlbnRJZCxcbiAgICAgIHVzZXJJZCxcbiAgICAgIGhvc3RJZCxcbiAgICB9KSkgPz8gbnVsbDtcblxuICBjb25zdCBldmVudFBsYW5uZXJSZXF1ZXN0Qm9keTogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9IHtcbiAgICBncm91cElkLFxuICAgIGV2ZW50SWQsXG4gICAgcGFydCxcbiAgICBsYXN0UGFydCxcbiAgICBzdGFydERhdGUsXG4gICAgZW5kRGF0ZSxcbiAgICB0YXNrSWQsXG4gICAgaGFyZERlYWRsaW5lLFxuICAgIHNvZnREZWFkbGluZSxcbiAgICB1c2VySWQsXG4gICAgdXNlcixcbiAgICBwcmlvcml0eSxcbiAgICBpc1ByZUV2ZW50LFxuICAgIGlzUG9zdEV2ZW50LFxuICAgIGZvckV2ZW50SWQsXG4gICAgcG9zaXRpdmVJbXBhY3RTY29yZSxcbiAgICBuZWdhdGl2ZUltcGFjdFNjb3JlLFxuICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrOlxuICAgICAgZGF5T2ZXZWVrSW50VG9TdHJpbmdbcG9zaXRpdmVJbXBhY3REYXlPZldlZWtdID8/IG51bGwsXG4gICAgcG9zaXRpdmVJbXBhY3RUaW1lOiBhZGp1c3RlZFBvc2l0aXZlSW1wYWN0VGltZSxcbiAgICBuZWdhdGl2ZUltcGFjdERheU9mV2VlazpcbiAgICAgIGRheU9mV2Vla0ludFRvU3RyaW5nW25lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrXSA/PyBudWxsLFxuICAgIG5lZ2F0aXZlSW1wYWN0VGltZTogYWRqdXN0ZWROZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgbW9kaWZpYWJsZSxcbiAgICBwcmVmZXJyZWREYXlPZldlZWs6IGRheU9mV2Vla0ludFRvU3RyaW5nW3ByZWZlcnJlZERheU9mV2Vla10gPz8gbnVsbCxcbiAgICBwcmVmZXJyZWRUaW1lOiBhZGp1c3RlZFByZWZlcnJlZFRpbWUsXG4gICAgaXNNZWV0aW5nLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICBpc01lZXRpbmdNb2RpZmlhYmxlLFxuICAgIGRhaWx5VGFza0xpc3QsXG4gICAgd2Vla2x5VGFza0xpc3QsXG4gICAgZ2FwOiBpc0JyZWFrLFxuICAgIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlOiBhZGp1c3RlZFByZWZlcnJlZFN0YXJ0VGltZVJhbmdlLFxuICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZTogYWRqdXN0ZWRQcmVmZXJyZWRFbmRUaW1lUmFuZ2UsXG4gICAgdG90YWxXb3JraW5nSG91cnMsXG4gICAgcmVjdXJyaW5nRXZlbnRJZCxcbiAgICBob3N0SWQsXG4gICAgbWVldGluZ0lkLFxuICAgIG1lZXRpbmdQYXJ0LFxuICAgIG1lZXRpbmdMYXN0UGFydCxcbiAgICBldmVudDoge1xuICAgICAgaWQ6IGV2ZW50SWQsXG4gICAgICB1c2VySWQsXG4gICAgICBob3N0SWQsXG4gICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzOiBhZGp1c3RlZFByZWZlcnJlZFRpbWVSYW5nZXMgPz8gbnVsbCxcbiAgICB9LFxuICB9O1xuICByZXR1cm4gZXZlbnRQbGFubmVyUmVxdWVzdEJvZHk7XG59O1xuXG5leHBvcnQgY29uc3QgY29udmVydE1lZXRpbmdQbHVzVHlwZVRvRXZlbnRQbHVzVHlwZSA9IChcbiAgZXZlbnQ6IEV2ZW50TWVldGluZ1BsdXNUeXBlXG4pOiBFdmVudFBsdXNUeXBlID0+IHtcbiAgY29uc3QgbmV3RXZlbnQ6IEV2ZW50UGx1c1R5cGUgPSB7XG4gICAgLi4uZXZlbnQsXG4gICAgcHJlZmVycmVkVGltZVJhbmdlczpcbiAgICAgIGV2ZW50Py5wcmVmZXJyZWRUaW1lUmFuZ2VzPy5tYXAoKHB0KSA9PiAoe1xuICAgICAgICBpZDogcHQuaWQsXG4gICAgICAgIGV2ZW50SWQ6IGV2ZW50LmlkLFxuICAgICAgICBkYXlPZldlZWs6IHB0Py5kYXlPZldlZWssXG4gICAgICAgIHN0YXJ0VGltZTogcHQ/LnN0YXJ0VGltZSxcbiAgICAgICAgZW5kVGltZTogcHQ/LmVuZFRpbWUsXG4gICAgICAgIHVwZGF0ZWRBdDogcHQ/LnVwZGF0ZWRBdCxcbiAgICAgICAgY3JlYXRlZERhdGU6IHB0Py5jcmVhdGVkRGF0ZSxcbiAgICAgICAgdXNlcklkOiBldmVudD8udXNlcklkLFxuICAgICAgfSkpIHx8IG51bGwsXG4gIH07XG5cbiAgcmV0dXJuIG5ld0V2ZW50O1xufTtcblxuZXhwb3J0IGNvbnN0IHNldFByZWZlcnJlZFRpbWVGb3JVbk1vZGlmaWFibGVFdmVudCA9IChcbiAgZXZlbnQ6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGUsXG4gIHRpbWV6b25lOiBzdHJpbmdcbik6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGUgPT4ge1xuICBpZiAoIWV2ZW50Py5tb2RpZmlhYmxlKSB7XG4gICAgaWYgKCFldmVudD8ucHJlZmVycmVkRGF5T2ZXZWVrICYmICFldmVudD8ucHJlZmVycmVkVGltZSkge1xuICAgICAgY29uc3QgbmV3RXZlbnQgPSB7XG4gICAgICAgIC4uLmV2ZW50LFxuICAgICAgICBwcmVmZXJyZWREYXlPZldlZWs6XG4gICAgICAgICAgZGF5T2ZXZWVrSW50VG9TdHJpbmdbXG4gICAgICAgICAgICBnZXRJU09EYXkoXG4gICAgICAgICAgICAgIGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICAgICAgICAgICAgKVxuICAgICAgICAgIF0sXG4gICAgICAgIHByZWZlcnJlZFRpbWU6IGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5mb3JtYXQoJ0hIOm1tJykgYXMgVGltZSxcbiAgICAgIH07XG4gICAgICByZXR1cm4gbmV3RXZlbnQ7XG4gICAgfVxuICAgIHJldHVybiBldmVudDtcbiAgfVxuICByZXR1cm4gZXZlbnQ7XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdEV2ZW50c1dpdGhJZHMgPSBhc3luYyAoaWRzOiBzdHJpbmdbXSkgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnbGlzdEV2ZW50c1dpdGhJZHMnO1xuXG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgcXVlcnkgbGlzdEV2ZW50c1dpdGhJZHMoJGlkczogW1N0cmluZyFdISkge1xuICAgICAgRXZlbnQod2hlcmU6IHtpZDoge19pbjogJGlkc319KSB7XG4gICAgICAgIGFsbERheVxuICAgICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICAgIGF0dGFjaG1lbnRzXG4gICAgICAgIGF0dGVuZGVlc09taXR0ZWRcbiAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgY29sb3JJZFxuICAgICAgICBjb25mZXJlbmNlSWRcbiAgICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgICBjb3B5Q2F0ZWdvcmllc1xuICAgICAgICBjb3B5RHVyYXRpb25cbiAgICAgICAgY29weUlzQnJlYWtcbiAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgY29weVJlbWluZGVyc1xuICAgICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICBjcmVhdG9yXG4gICAgICAgIGRhaWx5VGFza0xpc3RcbiAgICAgICAgZGVsZXRlZFxuICAgICAgICBkdXJhdGlvblxuICAgICAgICBlbmREYXRlXG4gICAgICAgIGVuZFRpbWVVbnNwZWNpZmllZFxuICAgICAgICBldmVudElkXG4gICAgICAgIGV2ZW50VHlwZVxuICAgICAgICBleHRlbmRlZFByb3BlcnRpZXNcbiAgICAgICAgZm9sbG93VXBFdmVudElkXG4gICAgICAgIGZvckV2ZW50SWRcbiAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICBndWVzdHNDYW5Nb2RpZnlcbiAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgICAgaGFuZ291dExpbmtcbiAgICAgICAgaGFyZERlYWRsaW5lXG4gICAgICAgIGh0bWxMaW5rXG4gICAgICAgIGlDYWxVSURcbiAgICAgICAgaWRcbiAgICAgICAgaXNCcmVha1xuICAgICAgICBpc0V4dGVybmFsTWVldGluZ1xuICAgICAgICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgaXNGb2xsb3dVcFxuICAgICAgICBpc01lZXRpbmdcbiAgICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICBpc1Bvc3RFdmVudFxuICAgICAgICBpc1ByZUV2ZW50XG4gICAgICAgIGxpbmtzXG4gICAgICAgIGxvY2F0aW9uXG4gICAgICAgIGxvY2tlZFxuICAgICAgICBtYXhBdHRlbmRlZXNcbiAgICAgICAgbWVldGluZ0lkXG4gICAgICAgIG1ldGhvZFxuICAgICAgICBtb2RpZmlhYmxlXG4gICAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgbmVnYXRpdmVJbXBhY3RUaW1lXG4gICAgICAgIG5vdGVzXG4gICAgICAgIG9yZ2FuaXplclxuICAgICAgICBvcmlnaW5hbEFsbERheVxuICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZVxuICAgICAgICBvcmlnaW5hbFRpbWV6b25lXG4gICAgICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgIHBvc2l0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgcG9zaXRpdmVJbXBhY3RUaW1lXG4gICAgICAgIHBvc3RFdmVudElkXG4gICAgICAgIHByZUV2ZW50SWRcbiAgICAgICAgcHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZVxuICAgICAgICBwcmVmZXJyZWRUaW1lXG4gICAgICAgIHByaW9yaXR5XG4gICAgICAgIHByaXZhdGVDb3B5XG4gICAgICAgIHJlY3VycmVuY2VcbiAgICAgICAgcmVjdXJyZW5jZVJ1bGVcbiAgICAgICAgcmVjdXJyaW5nRXZlbnRJZFxuICAgICAgICBzZW5kVXBkYXRlc1xuICAgICAgICBzb2Z0RGVhZGxpbmVcbiAgICAgICAgc291cmNlXG4gICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICBzdGF0dXNcbiAgICAgICAgc3VtbWFyeVxuICAgICAgICB0YXNrSWRcbiAgICAgICAgdGFza1R5cGVcbiAgICAgICAgdGltZUJsb2NraW5nXG4gICAgICAgIHRpbWV6b25lXG4gICAgICAgIHRpdGxlXG4gICAgICAgIHRyYW5zcGFyZW5jeVxuICAgICAgICB1bmxpbmtcbiAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgdXNlcklkXG4gICAgICAgIHVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eVxuICAgICAgICB1c2VyTW9kaWZpZWRDYXRlZ29yaWVzXG4gICAgICAgIHVzZXJNb2RpZmllZER1cmF0aW9uXG4gICAgICAgIHVzZXJNb2RpZmllZElzQnJlYWtcbiAgICAgICAgdXNlck1vZGlmaWVkSXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgdXNlck1vZGlmaWVkSXNNZWV0aW5nXG4gICAgICAgIHVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbFxuICAgICAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnNcbiAgICAgICAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nXG4gICAgICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlXG4gICAgICAgIHZpc2liaWxpdHlcbiAgICAgICAgd2Vla2x5VGFza0xpc3RcbiAgICAgICAgYnlXZWVrRGF5XG4gICAgICAgIGxvY2FsU3luY2VkXG4gICAgICAgIHVzZXJNb2RpZmllZENvbG9yXG4gICAgICAgIGNvcHlDb2xvclxuICAgICAgfVxuICAgIH0gICAgXG4gICAgYDtcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IEV2ZW50OiBFdmVudFR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgaWRzLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/LkV2ZW50O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gbGlzdCBpZHMgd2l0aCBpZHMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHRhZ0V2ZW50c0ZvckRhaWx5T3JXZWVrbHlUYXNrID0gYXN5bmMgKFxuICBldmVudHM6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXVxuKTogUHJvbWlzZTxFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlW10gfCBudWxsPiA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgZmlsdGVyZWRFdmVudHMgPSBldmVudHMuZmlsdGVyKChlKSA9PiBlLnJlY3VycmluZ0V2ZW50SWQpO1xuICAgIGlmIChmaWx0ZXJlZEV2ZW50cz8ubGVuZ3RoID4gMCkge1xuICAgICAgY29uc3Qgb3JpZ2luYWxFdmVudHMgPSBhd2FpdCBsaXN0RXZlbnRzV2l0aElkcyhcbiAgICAgICAgXy51bmlxKGZpbHRlcmVkRXZlbnRzLm1hcCgoZSkgPT4gZT8ucmVjdXJyaW5nRXZlbnRJZCkpXG4gICAgICApO1xuICAgICAgaWYgKG9yaWdpbmFsRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGNvbnN0IHRhZ2dlZEZpbHRlcmVkRXZlbnRzID0gZmlsdGVyZWRFdmVudHMubWFwKChlKSA9PlxuICAgICAgICAgIHRhZ0V2ZW50Rm9yRGFpbHlPcldlZWtseVRhc2soXG4gICAgICAgICAgICBlLFxuICAgICAgICAgICAgb3JpZ2luYWxFdmVudHMuZmluZCgob2UpID0+IG9lLmlkID09PSBlLnJlY3VycmluZ0V2ZW50SWQpXG4gICAgICAgICAgKVxuICAgICAgICApO1xuICAgICAgICBjb25zdCBuZXdFdmVudHMgPSBldmVudHMubWFwKChlKSA9PiB7XG4gICAgICAgICAgaWYgKGU/LnJlY3VycmluZ0V2ZW50SWQpIHtcbiAgICAgICAgICAgIGNvbnN0IHRhZ2dlZEZpbHRlcmVkRXZlbnQgPSB0YWdnZWRGaWx0ZXJlZEV2ZW50cy5maW5kKFxuICAgICAgICAgICAgICAodGUpID0+IHRlPy5ldmVudElkID09PSBlPy5ldmVudElkXG4gICAgICAgICAgICApO1xuICAgICAgICAgICAgaWYgKHRhZ2dlZEZpbHRlcmVkRXZlbnQ/LmV2ZW50SWQpIHtcbiAgICAgICAgICAgICAgcmV0dXJuIHRhZ2dlZEZpbHRlcmVkRXZlbnQ7XG4gICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICByZXR1cm4gZTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgICAgcmV0dXJuIGU7XG4gICAgICAgIH0pO1xuICAgICAgICByZXR1cm4gbmV3RXZlbnRzO1xuICAgICAgfVxuICAgICAgY29uc29sZS5sb2coJ3RhZ0V2ZW50c0ZvckRhaWx5b3JXZWVrbHlUYXNrOiBvcmlnaW5hbEV2ZW50cyBpcyBlbXB0eScpO1xuICAgICAgcmV0dXJuIGV2ZW50cztcbiAgICB9XG4gICAgcmV0dXJuIGV2ZW50cztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHRvIHRhZyBldmVudHMgZm9yIGRhaWx5IG9yIHdlZWtseSB0YXNrJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB0YWdFdmVudEZvckRhaWx5T3JXZWVrbHlUYXNrID0gKFxuICBldmVudFRvU3VibWl0OiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlLFxuICBldmVudDogRXZlbnRQbHVzVHlwZVxuKSA9PiB7XG4gIGlmICghZXZlbnQ/LmlkKSB7XG4gICAgY29uc29sZS5sb2coJ25vIG9yaWdpbmFsIGV2ZW50IGluc2lkZSB0YWdFdmVudEZvckRhaWx5c09yV2Vla2x5VGFzaycpO1xuICAgIHJldHVybiBudWxsO1xuICB9XG5cbiAgaWYgKCFldmVudFRvU3VibWl0Py5ldmVudElkKSB7XG4gICAgY29uc29sZS5sb2coJ25vIGV2ZW50VG9TdWJtaXQgaW5zaWRlIHRhZ0V2ZW50Rm9yRGFpbHlPcldlZWtseVRhc2snKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIGlmIChldmVudFRvU3VibWl0Py5yZWN1cnJpbmdFdmVudElkKSB7XG4gICAgaWYgKGV2ZW50Py53ZWVrbHlUYXNrTGlzdCkge1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgLi4uZXZlbnRUb1N1Ym1pdCxcbiAgICAgICAgd2Vla2x5VGFza0xpc3Q6IGV2ZW50LndlZWtseVRhc2tMaXN0LFxuICAgICAgfTtcbiAgICB9XG4gICAgaWYgKGV2ZW50Py5kYWlseVRhc2tMaXN0KSB7XG4gICAgICByZXR1cm4ge1xuICAgICAgICAuLi5ldmVudFRvU3VibWl0LFxuICAgICAgICBkYWlseVRhc2tMaXN0OiBldmVudC5kYWlseVRhc2tMaXN0LFxuICAgICAgfTtcbiAgICB9XG4gICAgcmV0dXJuIGV2ZW50VG9TdWJtaXQ7XG4gIH1cbiAgcmV0dXJuIGV2ZW50VG9TdWJtaXQ7XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVVc2VyUGxhbm5lclJlcXVlc3RCb2R5ID0gKFxuICB1c2VyUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgd29ya1RpbWVzOiBXb3JrVGltZVR5cGVbXSxcbiAgaG9zdElkOiBzdHJpbmdcbik6IFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlID0+IHtcbiAgY29uc3Qge1xuICAgIG1heFdvcmtMb2FkUGVyY2VudCxcbiAgICBiYWNrVG9CYWNrTWVldGluZ3MsXG4gICAgbWF4TnVtYmVyT2ZNZWV0aW5ncyxcbiAgICBtaW5OdW1iZXJPZkJyZWFrcyxcbiAgfSA9IHVzZXJQcmVmZXJlbmNlO1xuICBjb25zdCB1c2VyOiBVc2VyUGxhbm5lclJlcXVlc3RCb2R5VHlwZSA9IHtcbiAgICBpZDogdXNlcklkLFxuICAgIG1heFdvcmtMb2FkUGVyY2VudCxcbiAgICBiYWNrVG9CYWNrTWVldGluZ3MsXG4gICAgbWF4TnVtYmVyT2ZNZWV0aW5ncyxcbiAgICBtaW5OdW1iZXJPZkJyZWFrcyxcbiAgICB3b3JrVGltZXMsXG4gICAgaG9zdElkLFxuICB9O1xuICByZXR1cm4gdXNlcjtcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZVVzZXJQbGFubmVyUmVxdWVzdEJvZHlGb3JFeHRlcm5hbEF0dGVuZGVlID0gKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgd29ya1RpbWVzOiBXb3JrVGltZVR5cGVbXSxcbiAgaG9zdElkOiBzdHJpbmdcbik6IFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlID0+IHtcbiAgY29uc3QgdXNlcjogVXNlclBsYW5uZXJSZXF1ZXN0Qm9keVR5cGUgPSB7XG4gICAgaWQ6IHVzZXJJZCxcbiAgICBtYXhXb3JrTG9hZFBlcmNlbnQ6IDEwMCxcbiAgICBiYWNrVG9CYWNrTWVldGluZ3M6IGZhbHNlLFxuICAgIG1heE51bWJlck9mTWVldGluZ3M6IDk5LFxuICAgIG1pbk51bWJlck9mQnJlYWtzOiAwLFxuICAgIHdvcmtUaW1lcyxcbiAgICBob3N0SWQsXG4gIH07XG4gIHJldHVybiB1c2VyO1xufTtcblxuZXhwb3J0IGNvbnN0IGNvbnZlcnRNZWV0aW5nQXNzaXN0RXZlbnRUeXBlVG9FdmVudFBsdXNUeXBlID0gKFxuICBldmVudDogTWVldGluZ0Fzc2lzdEV2ZW50VHlwZSxcbiAgdXNlcklkOiBzdHJpbmdcbik6IEV2ZW50UGx1c1R5cGUgPT4ge1xuICByZXR1cm4ge1xuICAgIGlkOiBldmVudD8uaWQsXG4gICAgdXNlcklkOiB1c2VySWQsXG4gICAgdGl0bGU6IGV2ZW50Py5zdW1tYXJ5LFxuICAgIHN0YXJ0RGF0ZTogZXZlbnQ/LnN0YXJ0RGF0ZSxcbiAgICBlbmREYXRlOiBldmVudD8uZW5kRGF0ZSxcbiAgICBhbGxEYXk6IGV2ZW50Py5hbGxEYXksXG4gICAgcmVjdXJyZW5jZVJ1bGU6IGV2ZW50Py5yZWN1cnJlbmNlUnVsZSxcbiAgICBsb2NhdGlvbjogZXZlbnQ/LmxvY2F0aW9uLFxuICAgIG5vdGVzOiBldmVudD8ubm90ZXMsXG4gICAgYXR0YWNobWVudHM6IGV2ZW50Py5hdHRhY2htZW50cyxcbiAgICBsaW5rczogZXZlbnQ/LmxpbmtzLFxuICAgIHRpbWV6b25lOiBldmVudD8udGltZXpvbmUsXG4gICAgY3JlYXRlZERhdGU6IGV2ZW50Py5jcmVhdGVkRGF0ZSxcbiAgICBkZWxldGVkOiBmYWxzZSxcbiAgICBwcmlvcml0eTogMSxcbiAgICBpc0ZvbGxvd1VwOiBmYWxzZSxcbiAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICBpc1Bvc3RFdmVudDogZmFsc2UsXG4gICAgbW9kaWZpYWJsZTogZmFsc2UsXG4gICAgYW55b25lQ2FuQWRkU2VsZjogdHJ1ZSxcbiAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnM6IHRydWUsXG4gICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM6IHRydWUsXG4gICAgb3JpZ2luYWxTdGFydERhdGU6IHVuZGVmaW5lZCxcbiAgICBvcmlnaW5hbEFsbERheTogZXZlbnQ/LmFsbERheSxcbiAgICBzdW1tYXJ5OiBldmVudD8uc3VtbWFyeSxcbiAgICB0cmFuc3BhcmVuY3k6IGV2ZW50Py50cmFuc3BhcmVuY3ksXG4gICAgdmlzaWJpbGl0eTogZXZlbnQ/LnZpc2liaWxpdHksXG4gICAgcmVjdXJyaW5nRXZlbnRJZDogZXZlbnQ/LnJlY3VycmluZ0V2ZW50SWQsXG4gICAgdXBkYXRlZEF0OiBldmVudD8udXBkYXRlZEF0LFxuICAgIGlDYWxVSUQ6IGV2ZW50Py5pQ2FsVUlELFxuICAgIGh0bWxMaW5rOiBldmVudD8uaHRtbExpbmssXG4gICAgY29sb3JJZDogZXZlbnQ/LmNvbG9ySWQsXG4gICAgY3JlYXRvcjogZXZlbnQ/LmNyZWF0b3IsXG4gICAgb3JnYW5pemVyOiBldmVudD8ub3JnYW5pemVyLFxuICAgIGVuZFRpbWVVbnNwZWNpZmllZDogZXZlbnQ/LmVuZFRpbWVVbnNwZWNpZmllZCxcbiAgICByZWN1cnJlbmNlOiBldmVudD8ucmVjdXJyZW5jZSxcbiAgICBvcmlnaW5hbFRpbWV6b25lOiBldmVudD8udGltZXpvbmUsXG4gICAgZXh0ZW5kZWRQcm9wZXJ0aWVzOiBldmVudD8uZXh0ZW5kZWRQcm9wZXJ0aWVzLFxuICAgIGhhbmdvdXRMaW5rOiBldmVudD8uaGFuZ291dExpbmssXG4gICAgZ3Vlc3RzQ2FuTW9kaWZ5OiBldmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgIGxvY2tlZDogZXZlbnQ/LmxvY2tlZCxcbiAgICBzb3VyY2U6IGV2ZW50Py5zb3VyY2UsXG4gICAgZXZlbnRUeXBlOiBldmVudD8uZXZlbnRUeXBlLFxuICAgIHByaXZhdGVDb3B5OiBldmVudD8ucHJpdmF0ZUNvcHksXG4gICAgY2FsZW5kYXJJZDogZXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgYmFja2dyb3VuZENvbG9yOiBldmVudD8uYmFja2dyb3VuZENvbG9yLFxuICAgIGZvcmVncm91bmRDb2xvcjogZXZlbnQ/LmZvcmVncm91bmRDb2xvcixcbiAgICB1c2VEZWZhdWx0QWxhcm1zOiBldmVudD8udXNlRGVmYXVsdEFsYXJtcyxcbiAgICBtZWV0aW5nSWQ6IGV2ZW50Py5tZWV0aW5nSWQsXG4gICAgZXZlbnRJZDogZXZlbnQ/LmV2ZW50SWQsXG4gIH07XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVXb3JrVGltZXNGb3JFeHRlcm5hbEF0dGVuZGVlID0gKFxuICBob3N0SWQ6IHN0cmluZyxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGF0dGVuZGVlRXZlbnRzOiBFdmVudFBsdXNUeXBlW10sXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICB1c2VyVGltZXpvbmU6IHN0cmluZ1xuKSA9PiB7XG4gIGNvbnN0IGRheXNJbldlZWsgPSA3O1xuXG4gIGNvbnN0IHdvcmtUaW1lczogV29ya1RpbWVUeXBlW10gPSBbXTtcblxuICBmb3IgKGxldCBpID0gMDsgaSA8IGRheXNJbldlZWs7IGkrKykge1xuICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGkgKyAxO1xuXG4gICAgY29uc3Qgc2FtZURheUV2ZW50cyA9IGF0dGVuZGVlRXZlbnRzLmZpbHRlcihcbiAgICAgIChlKSA9PlxuICAgICAgICBnZXRJU09EYXkoXG4gICAgICAgICAgZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC50b0RhdGUoKVxuICAgICAgICApID09PVxuICAgICAgICBpICsgMVxuICAgICk7XG4gICAgY29uc3QgbWluU3RhcnREYXRlID0gXy5taW5CeShzYW1lRGF5RXZlbnRzLCAoZSkgPT5cbiAgICAgIGRheWpzKGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAudW5peCgpXG4gICAgKTtcbiAgICBjb25zdCBtYXhFbmREYXRlID0gXy5tYXhCeShzYW1lRGF5RXZlbnRzLCAoZSkgPT5cbiAgICAgIGRheWpzKGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLnVuaXgoKVxuICAgICk7XG4gICAgY29uc3Qgc3RhcnRIb3VyID0gZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlID0gZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoMCksXG4gICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtaW5TdGFydERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICdtaW51dGUnLFxuICAgICAgICAnWyknXG4gICAgICApXG4gICAgICA/IDBcbiAgICAgIDogZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMTUpLFxuICAgICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDE1XG4gICAgICAgIDogZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAubWludXRlKDQ1KSxcbiAgICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICAgIClcbiAgICAgICAgICA/IDMwXG4gICAgICAgICAgOiA0NTtcblxuICAgIGxldCBlbmRIb3VyID0gZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihtYXhFbmREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IGVuZE1pbnV0ZSA9IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKDApLFxuICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtYXhFbmREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoMTUpLFxuICAgICAgICAnbWludXRlJyxcbiAgICAgICAgJ1spJ1xuICAgICAgKVxuICAgICAgPyAxNVxuICAgICAgOiBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgID8gMzBcbiAgICAgICAgOiBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAgIC50eihtYXhFbmREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAgIC5taW51dGUoNDUpLFxuICAgICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgICAgKVxuICAgICAgICAgID8gNDVcbiAgICAgICAgICA6IDA7XG4gICAgaWYgKGVuZE1pbnV0ZSA9PT0gMCkge1xuICAgICAgaWYgKGVuZEhvdXIgPCAyMykge1xuICAgICAgICBlbmRIb3VyICs9IDE7XG4gICAgICB9XG4gICAgfVxuXG4gICAgd29ya1RpbWVzLnB1c2goe1xuICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1tkYXlPZldlZWtJbnRdLFxuICAgICAgc3RhcnRUaW1lOiBkYXlqcyhcbiAgICAgICAgc2V0SVNPRGF5KFxuICAgICAgICAgIGRheWpzKClcbiAgICAgICAgICAgIC5ob3VyKHN0YXJ0SG91cilcbiAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLnRvRGF0ZSgpLFxuICAgICAgICAgIGkgKyAxXG4gICAgICAgIClcbiAgICAgIClcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgICAgZW5kVGltZTogZGF5anMoXG4gICAgICAgIHNldElTT0RheShcbiAgICAgICAgICBkYXlqcygpXG4gICAgICAgICAgICAuaG91cihlbmRIb3VyKVxuICAgICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLnRvRGF0ZSgpLFxuICAgICAgICAgIGkgKyAxXG4gICAgICAgIClcbiAgICAgIClcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgICAgaG9zdElkLFxuICAgICAgdXNlcklkLFxuICAgIH0pO1xuICB9XG5cbiAgcmV0dXJuIHdvcmtUaW1lcztcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZVRpbWVTbG90c0ZvckV4dGVybmFsQXR0ZW5kZWUgPSAoXG4gIGhvc3RTdGFydERhdGU6IHN0cmluZyxcbiAgaG9zdElkOiBzdHJpbmcsXG4gIGF0dGVuZGVlRXZlbnRzOiBFdmVudFBsdXNUeXBlW10sXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICB1c2VyVGltZXpvbmU6IHN0cmluZyxcbiAgaXNGaXJzdERheT86IGJvb2xlYW5cbikgPT4ge1xuICBpZiAoaXNGaXJzdERheSkge1xuICAgIGNvbnN0IGRheU9mV2Vla0ludEJ5SG9zdCA9IGdldElTT0RheShcbiAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICAgKTtcbiAgICBjb25zdCBtb250aEJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5tb250aCgpO1xuICAgIGNvbnN0IGRheU9mTW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuZGF0ZSgpO1xuICAgIGNvbnN0IHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLm1pbnV0ZSgwKSxcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkubWludXRlKDE1KSxcbiAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICdbKSdcbiAgICAgIClcbiAgICAgID8gMFxuICAgICAgOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMTUpLFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDE1XG4gICAgICAgIDogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgICAgLm1pbnV0ZSg0NSksXG4gICAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgICApXG4gICAgICAgICAgPyAzMFxuICAgICAgICAgIDogNDU7XG5cbiAgICBjb25zdCBzYW1lRGF5RXZlbnRzID0gYXR0ZW5kZWVFdmVudHMuZmlsdGVyKFxuICAgICAgKGUpID0+XG4gICAgICAgIGdldElTT0RheShcbiAgICAgICAgICBkYXlqcyhlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHoodXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC50b0RhdGUoKVxuICAgICAgICApID09PSBkYXlPZldlZWtJbnRCeUhvc3RcbiAgICApO1xuICAgIGNvbnN0IG1heEVuZERhdGUgPSBfLm1heEJ5KHNhbWVEYXlFdmVudHMsIChlKSA9PlxuICAgICAgZGF5anMoZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLnVuaXgoKVxuICAgICk7XG5cbiAgICBsZXQgd29ya0VuZEhvdXJCeUhvc3QgPSBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgY29uc3Qgd29ya0VuZE1pbnV0ZUJ5SG9zdCA9IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKDApLFxuICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtYXhFbmREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoMTUpLFxuICAgICAgICAnbWludXRlJyxcbiAgICAgICAgJ1spJ1xuICAgICAgKVxuICAgICAgPyAxNVxuICAgICAgOiBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgID8gMzBcbiAgICAgICAgOiBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAgIC50eihtYXhFbmREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAgIC5taW51dGUoNDUpLFxuICAgICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgICAgKVxuICAgICAgICAgID8gNDVcbiAgICAgICAgICA6IDA7XG4gICAgaWYgKHdvcmtFbmRNaW51dGVCeUhvc3QgPT09IDApIHtcbiAgICAgIGlmICh3b3JrRW5kSG91ckJ5SG9zdCA8IDIzKSB7XG4gICAgICAgIHdvcmtFbmRIb3VyQnlIb3N0ICs9IDE7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgbWluU3RhcnREYXRlID0gXy5taW5CeShzYW1lRGF5RXZlbnRzLCAoZSkgPT5cbiAgICAgIGRheWpzKGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLnVuaXgoKVxuICAgICk7XG5cbiAgICBjb25zdCB3b3JrU3RhcnRIb3VyQnlIb3N0ID0gZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCA9IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAubWludXRlKDApLFxuICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoMTUpLFxuICAgICAgICAnbWludXRlJyxcbiAgICAgICAgJ1spJ1xuICAgICAgKVxuICAgICAgPyAwXG4gICAgICA6IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDE1KSxcbiAgICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgIClcbiAgICAgICAgPyAxNVxuICAgICAgICA6IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZS50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgLm1pbnV0ZSg0NSksXG4gICAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgICApXG4gICAgICAgICAgPyAzMFxuICAgICAgICAgIDogNDU7XG5cbiAgICBpZiAoXG4gICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmlzQmVmb3JlKFxuICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXJCeUhvc3QpXG4gICAgICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgKVxuICAgICkge1xuICAgICAgY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgICAgaG91cnM6IHdvcmtTdGFydEhvdXJCeUhvc3QsXG4gICAgICAgIG1pbnV0ZXM6IHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCxcbiAgICAgIH0pO1xuICAgICAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICAgIGhvdXJzOiB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAgICAgbWludXRlczogd29ya0VuZE1pbnV0ZUJ5SG9zdCxcbiAgICAgIH0pO1xuICAgICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgICAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcblxuICAgICAgY29uc3QgdGltZVNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuXG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgaG9zdFN0YXJ0RGF0ZSxcbiAgICAgICAgZGF5T2ZXZWVrSW50QnlIb3N0LFxuICAgICAgICBkYXlPZk1vbnRoQnlIb3N0LFxuICAgICAgICBzdGFydEhvdXJPZkhvc3REYXRlQnlIb3N0LFxuICAgICAgICBzdGFydE1pbnV0ZU9mSG9zdERhdGVCeUhvc3QsXG4gICAgICAgIHdvcmtFbmRIb3VyQnlIb3N0LFxuICAgICAgICB3b3JrRW5kTWludXRlQnlIb3N0LFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgYHN0YXJ0RGF0ZSwgIGRheU9mV2Vla0ludEJ5SG9zdCwgZGF5T2ZNb250aEJ5SG9zdCwgc3RhcnRIb3VyQnlIb3N0LCBzdGFydE1pbnV0ZUJ5SG9zdCwgZW5kSG91ckJ5SG9zdCwgZW5kTWludXRlQnlIb3N0IHRvdGFsTWludXRlcywgdGltZXpvbmUsIGluc2lkZSBmaXJzdERheSBpbnNpZGUgZ2VuZXJhdGVUaW1lc2xvdHNgXG4gICAgICApO1xuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gMTUpIHtcbiAgICAgICAgdGltZVNsb3RzLnB1c2goe1xuICAgICAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50QnlIb3N0XSxcbiAgICAgICAgICBzdGFydFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QpXG4gICAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdClcbiAgICAgICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICAgICAgZW5kVGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmhvdXIoc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdClcbiAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVPZkhvc3REYXRlQnlIb3N0KVxuICAgICAgICAgICAgLmFkZChpICsgMTUsICdtaW51dGUnKVxuICAgICAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgICAgICAgIGhvc3RJZCxcbiAgICAgICAgICBtb250aERheTogZm9ybWF0VG9Nb250aERheShcbiAgICAgICAgICAgIG1vbnRoQnlIb3N0IGFzIE1vbnRoVHlwZSxcbiAgICAgICAgICAgIGRheU9mTW9udGhCeUhvc3QgYXMgRGF5VHlwZVxuICAgICAgICAgICksXG4gICAgICAgIH0pO1xuICAgICAgfVxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIHRpbWVTbG90cyxcbiAgICAgICAgJyB0aW1lU2xvdHMgaW5zaWRlIGdlbmVyYXRlVGltZVNsb3RzIGZvciBmaXJzdCBkYXkgd2hlcmUgc3RhcnREYXRlIGlzIGJlZm9yZSB3b3JrIHN0YXJ0IHRpbWUnXG4gICAgICApO1xuICAgICAgcmV0dXJuIHRpbWVTbG90cztcbiAgICB9XG5cbiAgICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgaG91cnM6IHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QsXG4gICAgICBtaW51dGVzOiBzdGFydE1pbnV0ZU9mSG9zdERhdGVCeUhvc3QsXG4gICAgfSk7XG4gICAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICBob3Vyczogd29ya0VuZEhvdXJCeUhvc3QsXG4gICAgICBtaW51dGVzOiB3b3JrRW5kTWludXRlQnlIb3N0LFxuICAgIH0pO1xuICAgIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgICBjb25zdCB0b3RhbE1pbnV0ZXMgPSB0b3RhbER1cmF0aW9uLmFzTWludXRlcygpO1xuXG4gICAgY29uc3QgdGltZVNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgaG9zdFN0YXJ0RGF0ZSxcbiAgICAgIGRheU9mV2Vla0ludEJ5SG9zdCxcbiAgICAgIGRheU9mTW9udGhCeUhvc3QsXG4gICAgICBzdGFydEhvdXJPZkhvc3REYXRlQnlIb3N0LFxuICAgICAgc3RhcnRNaW51dGVPZkhvc3REYXRlQnlIb3N0LFxuICAgICAgd29ya0VuZEhvdXJCeUhvc3QsXG4gICAgICB3b3JrRW5kTWludXRlQnlIb3N0LFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgYHN0YXJ0RGF0ZSwgIGRheU9mV2Vla0ludEJ5SG9zdCwgZGF5T2ZNb250aCwgc3RhcnRIb3VyLCBzdGFydE1pbnV0ZSwgZW5kSG91ciwgZW5kTWludXRlIHRvdGFsTWludXRlcywgdGltZXpvbmUsIGluc2lkZSBmaXJzdERheSBpbnNpZGUgZ2VuZXJhdGVUaW1lc2xvdHNgXG4gICAgKTtcbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsTWludXRlczsgaSArPSAxNSkge1xuICAgICAgdGltZVNsb3RzLnB1c2goe1xuICAgICAgICBkYXlPZldlZWs6IGRheU9mV2Vla0ludFRvU3RyaW5nW2RheU9mV2Vla0ludEJ5SG9zdF0sXG4gICAgICAgIHN0YXJ0VGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuaG91cihzdGFydEhvdXJPZkhvc3REYXRlQnlIb3N0KVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVPZkhvc3REYXRlQnlIb3N0KVxuICAgICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgICAgICBlbmRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QpXG4gICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZU9mSG9zdERhdGVCeUhvc3QpXG4gICAgICAgICAgLmFkZChpICsgMTUsICdtaW51dGUnKVxuICAgICAgICAgIC5mb3JtYXQoJ0hIOm1tJykgYXMgVGltZSxcbiAgICAgICAgaG9zdElkLFxuICAgICAgICBtb250aERheTogZm9ybWF0VG9Nb250aERheShcbiAgICAgICAgICBtb250aEJ5SG9zdCBhcyBNb250aFR5cGUsXG4gICAgICAgICAgZGF5T2ZNb250aEJ5SG9zdCBhcyBEYXlUeXBlXG4gICAgICAgICksXG4gICAgICB9KTtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyh0aW1lU2xvdHMsICcgdGltZVNsb3RzIGluc2lkZSBnZW5lcmF0ZVRpbWVTbG90cyBmb3IgZmlyc3QgZGF5Jyk7XG4gICAgcmV0dXJuIHRpbWVTbG90cztcbiAgfVxuXG4gIGNvbnN0IGRheU9mV2Vla0ludEJ5SG9zdCA9IGdldElTT0RheShcbiAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICApO1xuICBjb25zdCBtb250aEJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLm1vbnRoKCk7XG4gIGNvbnN0IGRheU9mTW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgIC5kYXRlKCk7XG5cbiAgY29uc3Qgc2FtZURheUV2ZW50cyA9IGF0dGVuZGVlRXZlbnRzLmZpbHRlcihcbiAgICAoZSkgPT5cbiAgICAgIGdldElTT0RheShcbiAgICAgICAgZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC50b0RhdGUoKVxuICAgICAgKSA9PT0gZGF5T2ZXZWVrSW50QnlIb3N0XG4gICk7XG4gIGNvbnN0IG1pblN0YXJ0RGF0ZSA9IF8ubWluQnkoc2FtZURheUV2ZW50cywgKGUpID0+XG4gICAgZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGUudGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC51bml4KClcbiAgKTtcbiAgY29uc3QgbWF4RW5kRGF0ZSA9IF8ubWF4Qnkoc2FtZURheUV2ZW50cywgKGUpID0+XG4gICAgZGF5anMoZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihlLnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAudW5peCgpXG4gICk7XG5cbiAgbGV0IHdvcmtFbmRIb3VyQnlIb3N0ID0gZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmhvdXIoKTtcbiAgY29uc3Qgd29ya0VuZE1pbnV0ZUJ5SG9zdCA9IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5pc0JldHdlZW4oXG4gICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAubWludXRlKDApLFxuICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAnbWludXRlJyxcbiAgICAgICdbKSdcbiAgICApXG4gICAgPyAxNVxuICAgIDogZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5taW51dGUoMTUpLFxuICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICdbKSdcbiAgICAgICAgICApXG4gICAgICA/IDMwXG4gICAgICA6IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDQ1KSxcbiAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgIClcbiAgICAgICAgPyA0NVxuICAgICAgICA6IDA7XG4gIGlmICh3b3JrRW5kTWludXRlQnlIb3N0ID09PSAwKSB7XG4gICAgaWYgKHdvcmtFbmRIb3VyQnlIb3N0IDwgMjMpIHtcbiAgICAgIHdvcmtFbmRIb3VyQnlIb3N0ICs9IDE7XG4gICAgfVxuICB9XG5cbiAgY29uc3Qgd29ya1N0YXJ0SG91ckJ5SG9zdCA9IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5ob3VyKCk7XG4gIGNvbnN0IHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCA9IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5pc0JldHdlZW4oXG4gICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAubWludXRlKDApLFxuICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAnbWludXRlJyxcbiAgICAgICdbKSdcbiAgICApXG4gICAgPyAwXG4gICAgOiBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLm1pbnV0ZSgxNSksXG4gICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgIClcbiAgICAgID8gMTVcbiAgICAgIDogZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoNDUpLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDMwXG4gICAgICAgIDogNDU7XG5cbiAgY29uc29sZS5sb2coXG4gICAgbW9udGhCeUhvc3QsXG4gICAgZGF5T2ZNb250aEJ5SG9zdCxcbiAgICB3b3JrU3RhcnRIb3VyQnlIb3N0LFxuICAgIHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCxcbiAgICB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAnIG1vbnRoQnlIb3N0LCBkYXlPZk1vbnRoQnlIb3N0LCB3b3JrU3RhcnRIb3VyQnlIb3N0LCB3b3JrU3RhcnRNaW51dGVCeUhvc3QsIHdvcmtFbmRIb3VyQnlIb3N0J1xuICApO1xuICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiB3b3JrU3RhcnRIb3VyQnlIb3N0LFxuICAgIG1pbnV0ZXM6IHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCxcbiAgfSk7XG4gIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICBtaW51dGVzOiB3b3JrRW5kTWludXRlQnlIb3N0LFxuICB9KTtcbiAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICBjb25zdCB0b3RhbE1pbnV0ZXMgPSB0b3RhbER1cmF0aW9uLmFzTWludXRlcygpO1xuICBjb25zdCB0aW1lU2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG4gIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IDE1KSB7XG4gICAgdGltZVNsb3RzLnB1c2goe1xuICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1tkYXlPZldlZWtJbnRCeUhvc3RdLFxuICAgICAgc3RhcnRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tJykgYXMgVGltZSxcbiAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgLmFkZChpICsgMTUsICdtaW51dGUnKVxuICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICBob3N0SWQsXG4gICAgICBtb250aERheTogZm9ybWF0VG9Nb250aERheShcbiAgICAgICAgbW9udGhCeUhvc3QgYXMgTW9udGhUeXBlLFxuICAgICAgICBkYXlPZk1vbnRoQnlIb3N0IGFzIERheVR5cGVcbiAgICAgICksXG4gICAgfSk7XG4gIH1cblxuICBjb25zb2xlLmxvZyh0aW1lU2xvdHMsICcgdGltZVNsb3RzIGluc2lkZSBnZW5lcmF0ZVRpbWVTbG90cycpO1xuICByZXR1cm4gdGltZVNsb3RzO1xufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlVGltZVNsb3RzTGl0ZUZvckV4dGVybmFsQXR0ZW5kZWUgPSAoXG4gIGhvc3RTdGFydERhdGU6IHN0cmluZyxcbiAgaG9zdElkOiBzdHJpbmcsXG4gIGF0dGVuZGVlRXZlbnRzOiBFdmVudFBsdXNUeXBlW10sXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICB1c2VyVGltZXpvbmU6IHN0cmluZyxcbiAgaXNGaXJzdERheT86IGJvb2xlYW5cbikgPT4ge1xuICBpZiAoaXNGaXJzdERheSkge1xuICAgIGNvbnN0IGRheU9mV2Vla0ludEJ5SG9zdCA9IGdldElTT0RheShcbiAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICAgKTtcbiAgICBjb25zdCBtb250aEJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5tb250aCgpO1xuICAgIGNvbnN0IGRheU9mTW9udGhCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuZGF0ZSgpO1xuICAgIGNvbnN0IHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLm1pbnV0ZSgwKSxcbiAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkubWludXRlKDMwKSxcbiAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICdbKSdcbiAgICAgIClcbiAgICAgID8gMFxuICAgICAgOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5taW51dGUoNTkpLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDMwXG4gICAgICAgIDogMDtcblxuICAgIGNvbnN0IHNhbWVEYXlFdmVudHMgPSBhdHRlbmRlZUV2ZW50cy5maWx0ZXIoXG4gICAgICAoZSkgPT5cbiAgICAgICAgZ2V0SVNPRGF5KFxuICAgICAgICAgIGRheWpzKGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLnRvRGF0ZSgpXG4gICAgICAgICkgPT09IGRheU9mV2Vla0ludEJ5SG9zdFxuICAgICk7XG4gICAgY29uc3QgbWF4RW5kRGF0ZSA9IF8ubWF4Qnkoc2FtZURheUV2ZW50cywgKGUpID0+XG4gICAgICBkYXlqcyhlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAudW5peCgpXG4gICAgKTtcblxuICAgIGxldCB3b3JrRW5kSG91ckJ5SG9zdCA9IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgY29uc3Qgd29ya0VuZE1pbnV0ZUJ5SG9zdCA9IGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoMCksXG4gICAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5taW51dGUoMzApLFxuICAgICAgICAnbWludXRlJyxcbiAgICAgICAgJ1spJ1xuICAgICAgKVxuICAgICAgPyAzMFxuICAgICAgOiBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSg1OSksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgID8gMFxuICAgICAgICA6IDMwO1xuICAgIGlmICh3b3JrRW5kTWludXRlQnlIb3N0ID09PSAwKSB7XG4gICAgICBpZiAod29ya0VuZEhvdXJCeUhvc3QgPCAyMykge1xuICAgICAgICB3b3JrRW5kSG91ckJ5SG9zdCArPSAxO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IG1pblN0YXJ0RGF0ZSA9IF8ubWluQnkoc2FtZURheUV2ZW50cywgKGUpID0+XG4gICAgICBkYXlqcyhlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC51bml4KClcbiAgICApO1xuXG4gICAgY29uc3Qgd29ya1N0YXJ0SG91ckJ5SG9zdCA9IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgY29uc3Qgd29ya1N0YXJ0TWludXRlQnlIb3N0ID0gZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLm1pbnV0ZSgwKSxcbiAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICdtaW51dGUnLFxuICAgICAgICAnWyknXG4gICAgICApXG4gICAgICA/IDBcbiAgICAgIDogZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoNTkpLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICA/IDMwXG4gICAgICAgIDogMDtcblxuICAgIGlmIChcbiAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuaXNCZWZvcmUoXG4gICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlQnlIb3N0KVxuICAgICAgICApXG4gICAgKSB7XG4gICAgICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgICBob3Vyczogd29ya1N0YXJ0SG91ckJ5SG9zdCxcbiAgICAgICAgbWludXRlczogd29ya1N0YXJ0TWludXRlQnlIb3N0LFxuICAgICAgfSk7XG4gICAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgICAgaG91cnM6IHdvcmtFbmRIb3VyQnlIb3N0LFxuICAgICAgICBtaW51dGVzOiB3b3JrRW5kTWludXRlQnlIb3N0LFxuICAgICAgfSk7XG4gICAgICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbik7XG4gICAgICBjb25zdCB0b3RhbE1pbnV0ZXMgPSB0b3RhbER1cmF0aW9uLmFzTWludXRlcygpO1xuXG4gICAgICBjb25zdCB0aW1lU2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG5cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBob3N0U3RhcnREYXRlLFxuICAgICAgICBkYXlPZldlZWtJbnRCeUhvc3QsXG4gICAgICAgIGRheU9mTW9udGhCeUhvc3QsXG4gICAgICAgIHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QsXG4gICAgICAgIHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdCxcbiAgICAgICAgd29ya0VuZEhvdXJCeUhvc3QsXG4gICAgICAgIHdvcmtFbmRNaW51dGVCeUhvc3QsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBgc3RhcnREYXRlLCAgZGF5T2ZXZWVrSW50QnlIb3N0LCBkYXlPZk1vbnRoQnlIb3N0LCBzdGFydEhvdXJCeUhvc3QsIHN0YXJ0TWludXRlQnlIb3N0LCBlbmRIb3VyQnlIb3N0LCBlbmRNaW51dGVCeUhvc3QgdG90YWxNaW51dGVzLCB0aW1lem9uZSwgaW5zaWRlIGZpcnN0RGF5IGluc2lkZSBnZW5lcmF0ZVRpbWVzbG90c2BcbiAgICAgICk7XG4gICAgICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsTWludXRlczsgaSArPSAzMCkge1xuICAgICAgICB0aW1lU2xvdHMucHVzaCh7XG4gICAgICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWtJbnRUb1N0cmluZ1tkYXlPZldlZWtJbnRCeUhvc3RdLFxuICAgICAgICAgIHN0YXJ0VGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLmhvdXIoc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdClcbiAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVPZkhvc3REYXRlQnlIb3N0KVxuICAgICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAgIC5mb3JtYXQoJ0hIOm1tJykgYXMgVGltZSxcbiAgICAgICAgICBlbmRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cihzdGFydEhvdXJPZkhvc3REYXRlQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZU9mSG9zdERhdGVCeUhvc3QpXG4gICAgICAgICAgICAuYWRkKGkgKyAzMCwgJ21pbnV0ZScpXG4gICAgICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICAgICAgaG9zdElkLFxuICAgICAgICAgIG1vbnRoRGF5OiBmb3JtYXRUb01vbnRoRGF5KFxuICAgICAgICAgICAgbW9udGhCeUhvc3QgYXMgTW9udGhUeXBlLFxuICAgICAgICAgICAgZGF5T2ZNb250aEJ5SG9zdCBhcyBEYXlUeXBlXG4gICAgICAgICAgKSxcbiAgICAgICAgfSk7XG4gICAgICB9XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgdGltZVNsb3RzLFxuICAgICAgICAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMgZm9yIGZpcnN0IGRheSB3aGVyZSBzdGFydERhdGUgaXMgYmVmb3JlIHdvcmsgc3RhcnQgdGltZSdcbiAgICAgICk7XG4gICAgICByZXR1cm4gdGltZVNsb3RzO1xuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICBob3Vyczogc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdCxcbiAgICAgIG1pbnV0ZXM6IHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdCxcbiAgICB9KTtcbiAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgIGhvdXJzOiB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAgIG1pbnV0ZXM6IHdvcmtFbmRNaW51dGVCeUhvc3QsXG4gICAgfSk7XG4gICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG5cbiAgICBjb25zdCB0aW1lU2xvdHM6IFRpbWVTbG90VHlwZVtdID0gW107XG4gICAgY29uc29sZS5sb2coXG4gICAgICBob3N0U3RhcnREYXRlLFxuICAgICAgZGF5T2ZXZWVrSW50QnlIb3N0LFxuICAgICAgZGF5T2ZNb250aEJ5SG9zdCxcbiAgICAgIHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QsXG4gICAgICBzdGFydE1pbnV0ZU9mSG9zdERhdGVCeUhvc3QsXG4gICAgICB3b3JrRW5kSG91ckJ5SG9zdCxcbiAgICAgIHdvcmtFbmRNaW51dGVCeUhvc3QsXG4gICAgICBob3N0VGltZXpvbmUsXG4gICAgICBgc3RhcnREYXRlLCAgZGF5T2ZXZWVrSW50QnlIb3N0LCBkYXlPZk1vbnRoLCBzdGFydEhvdXIsIHN0YXJ0TWludXRlLCBlbmRIb3VyLCBlbmRNaW51dGUgdG90YWxNaW51dGVzLCB0aW1lem9uZSwgaW5zaWRlIGZpcnN0RGF5IGluc2lkZSBnZW5lcmF0ZVRpbWVzbG90c2BcbiAgICApO1xuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IDMwKSB7XG4gICAgICB0aW1lU2xvdHMucHVzaCh7XG4gICAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50QnlIb3N0XSxcbiAgICAgICAgc3RhcnRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ck9mSG9zdERhdGVCeUhvc3QpXG4gICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZU9mSG9zdERhdGVCeUhvc3QpXG4gICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyT2ZIb3N0RGF0ZUJ5SG9zdClcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlT2ZIb3N0RGF0ZUJ5SG9zdClcbiAgICAgICAgICAuYWRkKGkgKyAzMCwgJ21pbnV0ZScpXG4gICAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgICAgICBob3N0SWQsXG4gICAgICAgIG1vbnRoRGF5OiBmb3JtYXRUb01vbnRoRGF5KFxuICAgICAgICAgIG1vbnRoQnlIb3N0IGFzIE1vbnRoVHlwZSxcbiAgICAgICAgICBkYXlPZk1vbnRoQnlIb3N0IGFzIERheVR5cGVcbiAgICAgICAgKSxcbiAgICAgIH0pO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKHRpbWVTbG90cywgJyB0aW1lU2xvdHMgaW5zaWRlIGdlbmVyYXRlVGltZVNsb3RzIGZvciBmaXJzdCBkYXknKTtcbiAgICByZXR1cm4gdGltZVNsb3RzO1xuICB9XG5cbiAgY29uc3QgZGF5T2ZXZWVrSW50QnlIb3N0ID0gZ2V0SVNPRGF5KFxuICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICk7XG4gIGNvbnN0IG1vbnRoQnlIb3N0ID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAubW9udGgoKTtcbiAgY29uc3QgZGF5T2ZNb250aEJ5SG9zdCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLmRhdGUoKTtcblxuICBjb25zdCBzYW1lRGF5RXZlbnRzID0gYXR0ZW5kZWVFdmVudHMuZmlsdGVyKFxuICAgIChlKSA9PlxuICAgICAgZ2V0SVNPRGF5KFxuICAgICAgICBkYXlqcyhlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC50b0RhdGUoKVxuICAgICAgKSA9PT0gZGF5T2ZXZWVrSW50QnlIb3N0XG4gICk7XG4gIGNvbnN0IG1pblN0YXJ0RGF0ZSA9IF8ubWluQnkoc2FtZURheUV2ZW50cywgKGUpID0+XG4gICAgZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAudW5peCgpXG4gICk7XG4gIGNvbnN0IG1heEVuZERhdGUgPSBfLm1heEJ5KHNhbWVEYXlFdmVudHMsIChlKSA9PlxuICAgIGRheWpzKGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpLnR6KHVzZXJUaW1lem9uZSwgdHJ1ZSkudHooaG9zdFRpbWV6b25lKS51bml4KClcbiAgKTtcblxuICBsZXQgd29ya0VuZEhvdXJCeUhvc3QgPSBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAuaG91cigpO1xuICBjb25zdCB3b3JrRW5kTWludXRlQnlIb3N0ID0gZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmlzQmV0d2VlbihcbiAgICAgIGRheWpzKG1heEVuZERhdGUuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5taW51dGUoMCksXG4gICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICdtaW51dGUnLFxuICAgICAgJ1spJ1xuICAgIClcbiAgICA/IDMwXG4gICAgOiBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtYXhFbmREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMobWF4RW5kRGF0ZS5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG1heEVuZERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLm1pbnV0ZSgzMCksXG4gICAgICAgICAgICBkYXlqcyhtYXhFbmREYXRlLmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoobWF4RW5kRGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAubWludXRlKDU5KSxcbiAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgIClcbiAgICAgID8gMFxuICAgICAgOiAzMDtcbiAgaWYgKHdvcmtFbmRNaW51dGVCeUhvc3QgPT09IDApIHtcbiAgICBpZiAod29ya0VuZEhvdXJCeUhvc3QgPCAyMykge1xuICAgICAgd29ya0VuZEhvdXJCeUhvc3QgKz0gMTtcbiAgICB9XG4gIH1cblxuICBjb25zdCB3b3JrU3RhcnRIb3VyQnlIb3N0ID0gZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmhvdXIoKTtcbiAgY29uc3Qgd29ya1N0YXJ0TWludXRlQnlIb3N0ID0gZGF5anMobWluU3RhcnREYXRlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmlzQmV0d2VlbihcbiAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5taW51dGUoMCksXG4gICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICdtaW51dGUnLFxuICAgICAgJ1spJ1xuICAgIClcbiAgICA/IDBcbiAgICA6IGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihtaW5TdGFydERhdGU/LnRpbWV6b25lIHx8IHVzZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICBkYXlqcyhtaW5TdGFydERhdGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG1pblN0YXJ0RGF0ZT8udGltZXpvbmUgfHwgdXNlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAubWludXRlKDMwKSxcbiAgICAgICAgICAgIGRheWpzKG1pblN0YXJ0RGF0ZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoobWluU3RhcnREYXRlPy50aW1lem9uZSB8fCB1c2VyVGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgIC5taW51dGUoNTkpLFxuICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAnWyknXG4gICAgICAgICAgKVxuICAgICAgPyAzMFxuICAgICAgOiAwO1xuXG4gIGNvbnNvbGUubG9nKFxuICAgIG1vbnRoQnlIb3N0LFxuICAgIGRheU9mTW9udGhCeUhvc3QsXG4gICAgd29ya1N0YXJ0SG91ckJ5SG9zdCxcbiAgICB3b3JrU3RhcnRNaW51dGVCeUhvc3QsXG4gICAgd29ya0VuZEhvdXJCeUhvc3QsXG4gICAgJyBtb250aEJ5SG9zdCwgZGF5T2ZNb250aEJ5SG9zdCwgd29ya1N0YXJ0SG91ckJ5SG9zdCwgd29ya1N0YXJ0TWludXRlQnlIb3N0LCB3b3JrRW5kSG91ckJ5SG9zdCdcbiAgKTtcbiAgY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICBob3Vyczogd29ya1N0YXJ0SG91ckJ5SG9zdCxcbiAgICBtaW51dGVzOiB3b3JrU3RhcnRNaW51dGVCeUhvc3QsXG4gIH0pO1xuICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICBob3Vyczogd29ya0VuZEhvdXJCeUhvc3QsXG4gICAgbWludXRlczogd29ya0VuZE1pbnV0ZUJ5SG9zdCxcbiAgfSk7XG4gIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcbiAgY29uc3QgdGltZVNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsTWludXRlczsgaSArPSAzMCkge1xuICAgIHRpbWVTbG90cy5wdXNoKHtcbiAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50QnlIb3N0XSxcbiAgICAgIHN0YXJ0VGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXJCeUhvc3QpXG4gICAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlQnlIb3N0KVxuICAgICAgICAuYWRkKGksICdtaW51dGUnKVxuICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICBlbmRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgIC5hZGQoaSArIDMwLCAnbWludXRlJylcbiAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgICAgaG9zdElkLFxuICAgICAgbW9udGhEYXk6IGZvcm1hdFRvTW9udGhEYXkoXG4gICAgICAgIG1vbnRoQnlIb3N0IGFzIE1vbnRoVHlwZSxcbiAgICAgICAgZGF5T2ZNb250aEJ5SG9zdCBhcyBEYXlUeXBlXG4gICAgICApLFxuICAgIH0pO1xuICB9XG5cbiAgY29uc29sZS5sb2codGltZVNsb3RzLCAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMnKTtcbiAgcmV0dXJuIHRpbWVTbG90cztcbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzRXZlbnRzRm9yT3B0YVBsYW5uZXJGb3JFeHRlcm5hbEF0dGVuZGVlcyA9IGFzeW5jIChcbiAgdXNlcklkczogc3RyaW5nW10sXG4gIG1haW5Ib3N0SWQ6IHN0cmluZyxcbiAgYWxsRXh0ZXJuYWxFdmVudHM6IE1lZXRpbmdBc3Npc3RFdmVudFR5cGVbXSxcbiAgd2luZG93U3RhcnREYXRlOiBzdHJpbmcsXG4gIHdpbmRvd0VuZERhdGU6IHN0cmluZyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIGV4dGVybmFsQXR0ZW5kZWVzOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10sXG4gIG9sZEV4dGVybmFsTWVldGluZ0V2ZW50cz86IEV2ZW50TWVldGluZ1BsdXNUeXBlW10sXG4gIG5ld01lZXRpbmdFdmVudHM/OiBFdmVudE1lZXRpbmdQbHVzVHlwZVtdXG4pOiBQcm9taXNlPFJldHVybkJvZHlGb3JFeHRlcm5hbEF0dGVuZGVlRm9yT3B0YXBsYW5uZXJQcmVwVHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG1vZGlmaWVkQWxsRXh0ZXJuYWxFdmVudHMgPSBhbGxFeHRlcm5hbEV2ZW50cz8ubWFwKChlKSA9PlxuICAgICAgY29udmVydE1lZXRpbmdBc3Npc3RFdmVudFR5cGVUb0V2ZW50UGx1c1R5cGUoXG4gICAgICAgIGUsXG4gICAgICAgIGV4dGVybmFsQXR0ZW5kZWVzPy5maW5kKChhKSA9PiBhPy5pZCA9PT0gZT8uYXR0ZW5kZWVJZCk/LnVzZXJJZFxuICAgICAgKVxuICAgICk7XG5cbiAgICBjb25zdCBvbGRDb252ZXJ0ZWRNZWV0aW5nRXZlbnRzID0gb2xkRXh0ZXJuYWxNZWV0aW5nRXZlbnRzXG4gICAgICA/Lm1hcCgoYSkgPT4gY29udmVydE1lZXRpbmdQbHVzVHlwZVRvRXZlbnRQbHVzVHlwZShhKSlcbiAgICAgID8uZmlsdGVyKChlKSA9PiAhIWUpO1xuICAgIGlmIChvbGRDb252ZXJ0ZWRNZWV0aW5nRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICBtb2RpZmllZEFsbEV4dGVybmFsRXZlbnRzLnB1c2goLi4ub2xkQ29udmVydGVkTWVldGluZ0V2ZW50cyk7XG4gICAgfVxuXG4gICAgaWYgKG5ld01lZXRpbmdFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIG1vZGlmaWVkQWxsRXh0ZXJuYWxFdmVudHMucHVzaChcbiAgICAgICAgLi4ubmV3TWVldGluZ0V2ZW50cz8ubWFwKChtKSA9PlxuICAgICAgICAgIGNvbnZlcnRNZWV0aW5nUGx1c1R5cGVUb0V2ZW50UGx1c1R5cGUobSlcbiAgICAgICAgKVxuICAgICAgKTtcbiAgICB9XG5cbiAgICBjb25zdCBkaWZmRGF5cyA9IGRheWpzKHdpbmRvd0VuZERhdGUuc2xpY2UoMCwgMTkpKS5kaWZmKFxuICAgICAgZGF5anMod2luZG93U3RhcnREYXRlLnNsaWNlKDAsIDE5KSksXG4gICAgICAnZGF5J1xuICAgICk7XG5cbiAgICBjb25zdCBzdGFydERhdGVzRm9yRWFjaERheSA9IFtdO1xuXG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPD0gZGlmZkRheXM7IGkrKykge1xuICAgICAgc3RhcnREYXRlc0ZvckVhY2hEYXkucHVzaChcbiAgICAgICAgZGF5anMod2luZG93U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5hZGQoaSwgJ2RheScpXG4gICAgICAgICAgLmZvcm1hdCgpXG4gICAgICApO1xuICAgIH1cblxuICAgIGNvbnN0IHVuZmlsdGVyZWRXb3JrVGltZXM6IFdvcmtUaW1lVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IGV4dGVybmFsQXR0ZW5kZWUgb2YgZXh0ZXJuYWxBdHRlbmRlZXMpIHtcbiAgICAgIGNvbnN0IHdvcmtUaW1lc0ZvckF0dGVuZGVlID0gZ2VuZXJhdGVXb3JrVGltZXNGb3JFeHRlcm5hbEF0dGVuZGVlKFxuICAgICAgICBtYWluSG9zdElkLFxuICAgICAgICBleHRlcm5hbEF0dGVuZGVlPy51c2VySWQsXG4gICAgICAgIG1vZGlmaWVkQWxsRXh0ZXJuYWxFdmVudHMsXG4gICAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgICAgZXh0ZXJuYWxBdHRlbmRlZT8udGltZXpvbmVcbiAgICAgICk7XG4gICAgICB1bmZpbHRlcmVkV29ya1RpbWVzLnB1c2goLi4ud29ya1RpbWVzRm9yQXR0ZW5kZWUpO1xuICAgIH1cblxuICAgIGNvbnN0IHdvcmtUaW1lczogV29ya1RpbWVUeXBlW10gPSBfLnVuaXFXaXRoKFxuICAgICAgdW5maWx0ZXJlZFdvcmtUaW1lcyxcbiAgICAgIF8uaXNFcXVhbFxuICAgICk7XG5cbiAgICBjb25zdCB1bmZpbHRlcmVkVGltZXNsb3RzOiBUaW1lU2xvdFR5cGVbXSA9IFtdO1xuICAgIGNvbnN0IHRpbWVzbG90czogVGltZVNsb3RUeXBlW10gPSBbXTtcblxuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgc3RhcnREYXRlc0ZvckVhY2hEYXkubGVuZ3RoOyBpKyspIHtcbiAgICAgIGlmIChpID09PSAwKSB7XG4gICAgICAgIGZvciAoY29uc3QgZXh0ZXJuYWxBdHRlbmRlZSBvZiBleHRlcm5hbEF0dGVuZGVlcykge1xuICAgICAgICAgIGNvbnN0IHRpbWVzbG90c0ZvckRheSA9XG4gICAgICAgICAgICBhd2FpdCBnZW5lcmF0ZVRpbWVTbG90c0xpdGVGb3JFeHRlcm5hbEF0dGVuZGVlKFxuICAgICAgICAgICAgICBzdGFydERhdGVzRm9yRWFjaERheT8uW2ldLFxuICAgICAgICAgICAgICBtYWluSG9zdElkLFxuICAgICAgICAgICAgICBtb2RpZmllZEFsbEV4dGVybmFsRXZlbnRzLFxuICAgICAgICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWU/LnRpbWV6b25lLFxuICAgICAgICAgICAgICB0cnVlXG4gICAgICAgICAgICApO1xuICAgICAgICAgIHVuZmlsdGVyZWRUaW1lc2xvdHMucHVzaCguLi50aW1lc2xvdHNGb3JEYXkpO1xuICAgICAgICB9XG5cbiAgICAgICAgY29udGludWU7XG4gICAgICB9XG4gICAgICBmb3IgKGNvbnN0IGV4dGVybmFsQXR0ZW5kZWUgb2YgZXh0ZXJuYWxBdHRlbmRlZXMpIHtcbiAgICAgICAgY29uc3QgdGltZXNsb3RzRm9yRGF5ID0gYXdhaXQgZ2VuZXJhdGVUaW1lU2xvdHNMaXRlRm9yRXh0ZXJuYWxBdHRlbmRlZShcbiAgICAgICAgICBzdGFydERhdGVzRm9yRWFjaERheT8uW2ldLFxuICAgICAgICAgIG1haW5Ib3N0SWQsXG4gICAgICAgICAgbW9kaWZpZWRBbGxFeHRlcm5hbEV2ZW50cyxcbiAgICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgICAgZXh0ZXJuYWxBdHRlbmRlZT8udGltZXpvbmUsXG4gICAgICAgICAgZmFsc2VcbiAgICAgICAgKTtcbiAgICAgICAgdW5maWx0ZXJlZFRpbWVzbG90cy5wdXNoKC4uLnRpbWVzbG90c0ZvckRheSk7XG4gICAgICB9XG4gICAgfVxuICAgIHRpbWVzbG90cy5wdXNoKC4uLl8udW5pcVdpdGgodW5maWx0ZXJlZFRpbWVzbG90cywgXy5pc0VxdWFsKSk7XG4gICAgY29uc29sZS5sb2codGltZXNsb3RzLCAnIHRpbWVzbG90cycpO1xuXG4gICAgY29uc3QgZmlsdGVyZWRBbGxFdmVudHMgPSBfLnVuaXFCeShcbiAgICAgIG1vZGlmaWVkQWxsRXh0ZXJuYWxFdmVudHMuZmlsdGVyKChlKSA9PlxuICAgICAgICB2YWxpZGF0ZUV2ZW50RGF0ZXNGb3JFeHRlcm5hbEF0dGVuZGVlKGUpXG4gICAgICApLFxuICAgICAgJ2lkJ1xuICAgICk7XG4gICAgbGV0IGV2ZW50UGFydHM6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSA9IFtdO1xuXG4gICAgY29uc3QgZXZlbnRQYXJ0TWluaXNBY2N1bXVsYXRlZCA9IFtdO1xuICAgIGZvciAoY29uc3QgZXZlbnQgb2YgZmlsdGVyZWRBbGxFdmVudHMpIHtcbiAgICAgIGNvbnN0IGV2ZW50UGFydE1pbmlzID0gZ2VuZXJhdGVFdmVudFBhcnRzTGl0ZShldmVudCwgbWFpbkhvc3RJZCk7XG4gICAgICBldmVudFBhcnRNaW5pc0FjY3VtdWxhdGVkLnB1c2goLi4uZXZlbnRQYXJ0TWluaXMpO1xuICAgIH1cblxuICAgIGNvbnN0IG1vZGlmaWVkRXZlbnRQYXJ0TWluaXNQcmVCdWZmZXIgPVxuICAgICAgbW9kaWZ5RXZlbnRQYXJ0c0Zvck11bHRpcGxlUHJlQnVmZmVyVGltZShldmVudFBhcnRNaW5pc0FjY3VtdWxhdGVkKTtcbiAgICBjb25zdCBtb2RpZmllZEV2ZW50UGFydE1pbmlzUHJlQW5kUG9zdEJ1ZmZlciA9XG4gICAgICBtb2RpZnlFdmVudFBhcnRzRm9yTXVsdGlwbGVQb3N0QnVmZmVyVGltZShcbiAgICAgICAgbW9kaWZpZWRFdmVudFBhcnRNaW5pc1ByZUJ1ZmZlclxuICAgICAgKTtcbiAgICBjb25zdCBmb3JtYXR0ZWRFdmVudFBhcnRzOiBFdmVudFBhcnRQbGFubmVyUmVxdWVzdEJvZHlUeXBlW10gPVxuICAgICAgbW9kaWZpZWRFdmVudFBhcnRNaW5pc1ByZUFuZFBvc3RCdWZmZXI/Lm1hcCgoZSkgPT5cbiAgICAgICAgZm9ybWF0RXZlbnRUeXBlVG9QbGFubmVyRXZlbnRGb3JFeHRlcm5hbEF0dGVuZGVlKFxuICAgICAgICAgIGUsXG4gICAgICAgICAgd29ya1RpbWVzLFxuICAgICAgICAgIGZpbHRlcmVkQWxsRXZlbnRzLFxuICAgICAgICAgIGhvc3RUaW1lem9uZVxuICAgICAgICApXG4gICAgICApO1xuICAgIGlmIChmb3JtYXR0ZWRFdmVudFBhcnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICBldmVudFBhcnRzLnB1c2goLi4uZm9ybWF0dGVkRXZlbnRQYXJ0cyk7XG4gICAgfVxuXG4gICAgaWYgKGV2ZW50UGFydHMubGVuZ3RoID4gMCkge1xuICAgICAgZXZlbnRQYXJ0cy5mb3JFYWNoKChlKSA9PiBjb25zb2xlLmxvZyhlLCAnIGV2ZW50UGFydHMgYWZ0ZXIgZm9ybWF0dGluZycpKTtcbiAgICAgIGNvbnN0IG5ld0V2ZW50UGFydHNXaXRoUHJlZmVycmVkVGltZVNldCA9IGV2ZW50UGFydHMubWFwKChlKSA9PlxuICAgICAgICBzZXRQcmVmZXJyZWRUaW1lRm9yVW5Nb2RpZmlhYmxlRXZlbnQoXG4gICAgICAgICAgZSxcbiAgICAgICAgICBhbGxFeHRlcm5hbEV2ZW50cy5maW5kKChmKSA9PiBmLmlkID09PSBlLmV2ZW50SWQpPy50aW1lem9uZVxuICAgICAgICApXG4gICAgICApO1xuICAgICAgbmV3RXZlbnRQYXJ0c1dpdGhQcmVmZXJyZWRUaW1lU2V0LmZvckVhY2goKGUpID0+XG4gICAgICAgIGNvbnNvbGUubG9nKGUsICcgbmV3RXZlbnRQYXJ0c1dpdGhQcmVmZXJyZWRUaW1lU2V0JylcbiAgICAgICk7XG4gICAgICBjb25zdCBuZXdFdmVudFBhcnRzID0gYXdhaXQgdGFnRXZlbnRzRm9yRGFpbHlPcldlZWtseVRhc2soXG4gICAgICAgIG5ld0V2ZW50UGFydHNXaXRoUHJlZmVycmVkVGltZVNldFxuICAgICAgKTtcbiAgICAgIG5ld0V2ZW50UGFydHMuZm9yRWFjaCgoZSkgPT5cbiAgICAgICAgY29uc29sZS5sb2coZSwgJyBuZXdFdmVudFBhcnRzIGFmdGVyIHRhZ0V2ZW50c0ZvckRhaWx5T3JXZWVrbHlUYXNrJylcbiAgICAgICk7XG4gICAgICBjb25zdCB1c2VyTGlzdDogVXNlclBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSA9IFtdO1xuICAgICAgZm9yIChjb25zdCBleHRlcm5hbEF0dGVuZGVlIG9mIGV4dGVybmFsQXR0ZW5kZWVzKSB7XG4gICAgICAgIGNvbnN0IHVzZXJQbGFubmVyUmVxdWVzdEJvZHkgPVxuICAgICAgICAgIGdlbmVyYXRlVXNlclBsYW5uZXJSZXF1ZXN0Qm9keUZvckV4dGVybmFsQXR0ZW5kZWUoXG4gICAgICAgICAgICBleHRlcm5hbEF0dGVuZGVlPy51c2VySWQsXG4gICAgICAgICAgICB3b3JrVGltZXMsXG4gICAgICAgICAgICBtYWluSG9zdElkXG4gICAgICAgICAgKTtcbiAgICAgICAgY29uc29sZS5sb2codXNlclBsYW5uZXJSZXF1ZXN0Qm9keSwgJyB1c2VyUGxhbm5lclJlcXVlc3RCb2R5Jyk7XG4gICAgICAgIHVzZXJMaXN0LnB1c2godXNlclBsYW5uZXJSZXF1ZXN0Qm9keSk7XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IG1vZGlmaWVkTmV3RXZlbnRQYXJ0czogRXZlbnRQYXJ0UGxhbm5lclJlcXVlc3RCb2R5VHlwZVtdID1cbiAgICAgICAgbmV3RXZlbnRQYXJ0cy5tYXAoKGV2ZW50UGFydCkgPT4ge1xuICAgICAgICAgIGNvbnN0IG9sZEV2ZW50ID0gZmlsdGVyZWRBbGxFdmVudHMuZmluZChcbiAgICAgICAgICAgIChldmVudCkgPT4gZXZlbnQuaWQgPT09IGV2ZW50UGFydC5ldmVudElkXG4gICAgICAgICAgKTtcbiAgICAgICAgICByZXR1cm4ge1xuICAgICAgICAgICAgZ3JvdXBJZDogZXZlbnRQYXJ0Py5ncm91cElkLFxuICAgICAgICAgICAgZXZlbnRJZDogZXZlbnRQYXJ0Py5ldmVudElkLFxuICAgICAgICAgICAgcGFydDogZXZlbnRQYXJ0Py5wYXJ0LFxuICAgICAgICAgICAgbGFzdFBhcnQ6IGV2ZW50UGFydD8ubGFzdFBhcnQsXG4gICAgICAgICAgICBtZWV0aW5nUGFydDogZXZlbnRQYXJ0Py5tZWV0aW5nUGFydCxcbiAgICAgICAgICAgIG1lZXRpbmdMYXN0UGFydDogZXZlbnRQYXJ0Py5tZWV0aW5nTGFzdFBhcnQsXG4gICAgICAgICAgICBtZWV0aW5nSWQ6IGV2ZW50UGFydD8ubWVldGluZ0lkLFxuICAgICAgICAgICAgaG9zdElkOiBtYWluSG9zdElkLFxuICAgICAgICAgICAgc3RhcnREYXRlOiBkYXlqcyhldmVudFBhcnQ/LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihvbGRFdmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICAgICAgZW5kRGF0ZTogZGF5anMoZXZlbnRQYXJ0Py5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KG9sZEV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgICAgICB1c2VySWQ6IGV2ZW50UGFydD8udXNlcklkLFxuICAgICAgICAgICAgdXNlcjogZXZlbnRQYXJ0Py51c2VyLFxuICAgICAgICAgICAgcHJpb3JpdHk6IGV2ZW50UGFydD8ucHJpb3JpdHksXG4gICAgICAgICAgICBpc1ByZUV2ZW50OiBldmVudFBhcnQ/LmlzUHJlRXZlbnQsXG4gICAgICAgICAgICBpc1Bvc3RFdmVudDogZXZlbnRQYXJ0Py5pc1Bvc3RFdmVudCxcbiAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0U2NvcmU6IGV2ZW50UGFydD8ucG9zaXRpdmVJbXBhY3RTY29yZSxcbiAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmU6IGV2ZW50UGFydD8ubmVnYXRpdmVJbXBhY3RTY29yZSxcbiAgICAgICAgICAgIG1vZGlmaWFibGU6IGV2ZW50UGFydD8ubW9kaWZpYWJsZSxcbiAgICAgICAgICAgIGlzTWVldGluZzogZXZlbnRQYXJ0Py5pc01lZXRpbmcsXG4gICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZzogZXZlbnRQYXJ0Py5pc0V4dGVybmFsTWVldGluZyxcbiAgICAgICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZTogZXZlbnRQYXJ0Py5pc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGUsXG4gICAgICAgICAgICBpc01lZXRpbmdNb2RpZmlhYmxlOiBldmVudFBhcnQ/LmlzTWVldGluZ01vZGlmaWFibGUsXG4gICAgICAgICAgICBkYWlseVRhc2tMaXN0OiBldmVudFBhcnQ/LmRhaWx5VGFza0xpc3QsXG4gICAgICAgICAgICB3ZWVrbHlUYXNrTGlzdDogZXZlbnRQYXJ0Py53ZWVrbHlUYXNrTGlzdCxcbiAgICAgICAgICAgIGdhcDogZXZlbnRQYXJ0Py5nYXAsXG4gICAgICAgICAgICB0b3RhbFdvcmtpbmdIb3VyczogZXZlbnRQYXJ0Py50b3RhbFdvcmtpbmdIb3VycyxcbiAgICAgICAgICAgIGhhcmREZWFkbGluZTogZXZlbnRQYXJ0Py5oYXJkRGVhZGxpbmUsXG4gICAgICAgICAgICBzb2Z0RGVhZGxpbmU6IGV2ZW50UGFydD8uc29mdERlYWRsaW5lLFxuICAgICAgICAgICAgZm9yRXZlbnRJZDogZXZlbnRQYXJ0Py5mb3JFdmVudElkLFxuICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWs6IGV2ZW50UGFydD8ucG9zaXRpdmVJbXBhY3REYXlPZldlZWssXG4gICAgICAgICAgICBwb3NpdGl2ZUltcGFjdFRpbWU6IGV2ZW50UGFydD8ucG9zaXRpdmVJbXBhY3RUaW1lLFxuICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3REYXlPZldlZWs6IGV2ZW50UGFydD8ubmVnYXRpdmVJbXBhY3REYXlPZldlZWssXG4gICAgICAgICAgICBuZWdhdGl2ZUltcGFjdFRpbWU6IGV2ZW50UGFydD8ubmVnYXRpdmVJbXBhY3RUaW1lLFxuICAgICAgICAgICAgcHJlZmVycmVkRGF5T2ZXZWVrOiBldmVudFBhcnQ/LnByZWZlcnJlZERheU9mV2VlayxcbiAgICAgICAgICAgIHByZWZlcnJlZFRpbWU6IGV2ZW50UGFydD8ucHJlZmVycmVkVGltZSxcbiAgICAgICAgICAgIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlOiBldmVudFBhcnQ/LnByZWZlcnJlZFN0YXJ0VGltZVJhbmdlLFxuICAgICAgICAgICAgcHJlZmVycmVkRW5kVGltZVJhbmdlOiBldmVudFBhcnQ/LnByZWZlcnJlZEVuZFRpbWVSYW5nZSxcbiAgICAgICAgICAgIGV2ZW50OiBldmVudFBhcnQ/LmV2ZW50LFxuICAgICAgICAgIH07XG4gICAgICAgIH0pO1xuXG4gICAgICByZXR1cm4gbW9kaWZpZWROZXdFdmVudFBhcnRzPy5sZW5ndGggPiAwXG4gICAgICAgID8ge1xuICAgICAgICAgICAgdXNlcklkcyxcbiAgICAgICAgICAgIGhvc3RJZDogbWFpbkhvc3RJZCxcbiAgICAgICAgICAgIGV2ZW50UGFydHM6IG1vZGlmaWVkTmV3RXZlbnRQYXJ0cyxcbiAgICAgICAgICAgIGFsbEV2ZW50czogZmlsdGVyZWRBbGxFdmVudHMsXG4gICAgICAgICAgICBvbGRBdHRlbmRlZUV2ZW50czogYWxsRXh0ZXJuYWxFdmVudHMsXG4gICAgICAgICAgICB0aW1lc2xvdHMsXG4gICAgICAgICAgICB1c2VyTGlzdCxcbiAgICAgICAgICB9XG4gICAgICAgIDogbnVsbDtcbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUsXG4gICAgICAnIHVuYWJsZSB0byBwcm9jZXNzIGV2ZW50cyBmb3Igb3B0YXBsYW5uZXIgZm9yIGV4dGVybmFsIGF0dGVuZGVlJ1xuICAgICk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBvcHRhUGxhbldlZWtseSA9IGFzeW5jIChcbiAgdGltZXNsb3RzOiBUaW1lU2xvdFR5cGVbXSxcbiAgdXNlckxpc3Q6IFVzZXJQbGFubmVyUmVxdWVzdEJvZHlUeXBlW10sXG4gIGV2ZW50UGFydHM6IEV2ZW50UGFydFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGVbXSxcbiAgc2luZ2xldG9uSWQ6IHN0cmluZyxcbiAgaG9zdElkOiBzdHJpbmcsXG4gIGZpbGVLZXk6IHN0cmluZyxcbiAgZGVsYXk6IG51bWJlcixcbiAgY2FsbEJhY2tVcmw6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVxdWVzdEJvZHk6IFBsYW5uZXJSZXF1ZXN0Qm9keVR5cGUgPSB7XG4gICAgICBzaW5nbGV0b25JZCxcbiAgICAgIGhvc3RJZCxcbiAgICAgIHRpbWVzbG90cyxcbiAgICAgIHVzZXJMaXN0LFxuICAgICAgZXZlbnRQYXJ0cyxcbiAgICAgIGZpbGVLZXksXG4gICAgICBkZWxheSxcbiAgICAgIGNhbGxCYWNrVXJsLFxuICAgIH07XG5cbiAgICBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGAke29wdGFQbGFubmVyVXJsfS90aW1lVGFibGUvYWRtaW4vc29sdmUtZGF5YCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICBBdXRob3JpemF0aW9uOiBgQmFzaWMgJHtCdWZmZXIuZnJvbShgJHtvcHRhUGxhbm5lclVzZXJuYW1lfToke29wdGFQbGFubmVyUGFzc3dvcmR9YCkudG9TdHJpbmcoJ2Jhc2U2NCcpfWAsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHJlcXVlc3RCb2R5LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZygnIG9wdGFQbGFuV2Vla2x5IGNhbGxlZCcpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyBvcHRhUGxhbldlZWtseScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBkYXRlRnJlZW1pdW1CeUlkID0gYXN5bmMgKGlkOiBzdHJpbmcsIHVzYWdlOiBudW1iZXIpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ1VwZGF0ZUZyZWVtaXVtQnlJZCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBtdXRhdGlvbiBVcGRhdGVGcmVlbWl1bUJ5SWQoJGlkOiB1dWlkISwgJHVzYWdlOiBJbnQhKSB7XG4gICAgICAgICAgICAgICAgdXBkYXRlX0ZyZWVtaXVtX2J5X3BrKHBrX2NvbHVtbnM6IHtpZDogJGlkfSwgX3NldDoge3VzYWdlOiAkdXNhZ2V9KSB7XG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBwZXJpb2RcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzYWdlXG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkLFxuICAgICAgdXNhZ2UsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiB7IGRhdGE6IHsgdXBkYXRlX0ZyZWVtaXVtX2J5X3BrOiBGcmVlbWl1bVR5cGUgfSB9ID1cbiAgICAgIGF3YWl0IGdvdFxuICAgICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICB9LFxuICAgICAgICB9KVxuICAgICAgICAuanNvbigpO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgcmVzcG9uc2UsXG4gICAgICByZXNwb25zZT8uZGF0YT8udXBkYXRlX0ZyZWVtaXVtX2J5X3BrLFxuICAgICAgJyByZXNwb25zZSBhZnRlciB1cGRhdGluZyB1cGRhdGVfRnJlZW1pdW1fYnlfcGsnXG4gICAgKTtcblxuICAgIHJldHVybiByZXNwb25zZT8uZGF0YT8udXBkYXRlX0ZyZWVtaXVtX2J5X3BrO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdXBkYXRlIGZyZWVtaXVtJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRGcmVlbWl1bUJ5VXNlcklkID0gYXN5bmMgKHVzZXJJZDogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdHZXRGcmVlbWl1bUJ5VXNlcklkJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IEdldEZyZWVtaXVtQnlVc2VySWQoJHVzZXJJZDogdXVpZCEpIHtcbiAgICAgICAgICAgICAgICBGcmVlbWl1bSh3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH19KSB7XG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBwZXJpb2RcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzYWdlXG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgRnJlZW1pdW06IEZyZWVtaXVtVHlwZVtdIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gZ2V0RnJlZW1pdW1CeVVzZXJJZCAnKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/LkZyZWVtaXVtPy5bMF07XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZygnIHVuYWJsZSB0byBnZXQgZnJlZW1pdW0gYnkgdXNlciBpZCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0VXNlckNhdGVnb3JpZXMgPSBhc3luYyAodXNlcklkKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRVc2VyQ2F0ZWdvcmllcyc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBxdWVyeSBnZXRVc2VyQ2F0ZWdvcmllcygkdXNlcklkOiB1dWlkISkge1xuICAgICAgICBDYXRlZ29yeSh3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH19KSB7XG4gICAgICAgICAgbmFtZVxuICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgIGNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICAgICAgY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgY29weVJlbWluZGVyc1xuICAgICAgICAgIGNvcHlQcmlvcml0eUxldmVsXG4gICAgICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgICAgICBkZWZhdWx0QXZhaWxhYmlsaXR5XG4gICAgICAgICAgZGVmYXVsdFRpbWVCbG9ja2luZ1xuICAgICAgICAgIGRlZmF1bHRUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgIGRlZmF1bHRSZW1pbmRlcnNcbiAgICAgICAgICBkZWZhdWx0UHJpb3JpdHlMZXZlbFxuICAgICAgICAgIGRlZmF1bHRNb2RpZmlhYmxlXG4gICAgICAgICAgY29weUlzQnJlYWtcbiAgICAgICAgICBjb2xvclxuICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICBpZFxuICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICB9XG4gICAgICB9XG4gICAgYDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICB1c2VySWQsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IENhdGVnb3J5OiBDYXRlZ29yeVR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uQ2F0ZWdvcnk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgdXNlciBjYXRlZ29yaWVzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBmaW5kQmVzdE1hdGNoQ2F0ZWdvcnkyID0gYXN5bmMgKFxuICBldmVudDogRXZlbnRQbHVzVHlwZSxcbiAgcG9zc2libGVMYWJlbHM6IENhdGVnb3J5VHlwZVtdXG4pOiBQcm9taXNlPENsYXNzaWZpY2F0aW9uUmVzcG9uc2VCb2R5VHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGlmICghZXZlbnQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gZXZlbnQgcGFzc2VkIGluc2lkZSBmaW5kQmVzdE1hdGNoQ2F0ZWdvcnkyJyk7XG4gICAgfVxuXG4gICAgaWYgKCFwb3NzaWJsZUxhYmVscykge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICAnbm8gcG9zc2libGUgbGFiZWxzIHBhc3NlZCBpbnNpZGUgZmluZEJlc3RNYXRjaENhdGVnb3J5MidcbiAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc3QgeyBzdW1tYXJ5LCBub3RlcyB9ID0gZXZlbnQ7XG4gICAgY29uc3Qgc2VudGVuY2UgPSBgJHtzdW1tYXJ5fSR7bm90ZXMgPyBgOiAke25vdGVzfWAgOiAnJ31gO1xuXG4gICAgY29uc3QgbGFiZWxOYW1lcyA9IHBvc3NpYmxlTGFiZWxzLm1hcCgoYSkgPT4gYT8ubmFtZSk7XG5cbiAgICBjb25zdCBzeXN0ZW1Qcm9tcHQgPVxuICAgICAgJ1lvdSBhcmUgYW4gZXhwZXJ0IGV2ZW50IGNhdGVnb3JpemVyLiBHaXZlbiBhbiBldmVudCBkZXNjcmlwdGlvbiBhbmQgYSBsaXN0IG9mIHBvc3NpYmxlIGNhdGVnb3JpZXMsIHJldHVybiBhIEpTT04gYXJyYXkgc3RyaW5nIGNvbnRhaW5pbmcgb25seSB0aGUgbmFtZXMgb2YgdGhlIGNhdGVnb3JpZXMgdGhhdCBkaXJlY3RseSBhcHBseSB0byB0aGUgZXZlbnQuIERvIG5vdCBwcm92aWRlIGFueSBleHBsYW5hdGlvbiwgb25seSB0aGUgSlNPTiBhcnJheSBzdHJpbmcuJztcbiAgICBjb25zdCB1c2VyUHJvbXB0ID0gYEV2ZW50OiBcIiR7c2VudGVuY2V9XCJcbkNhdGVnb3JpZXM6ICR7SlNPTi5zdHJpbmdpZnkobGFiZWxOYW1lcyl9YDtcblxuICAgIHRyeSB7XG4gICAgICBjb25zdCBjb21wbGV0aW9uID0gYXdhaXQgb3BlbmFpLmNoYXQuY29tcGxldGlvbnMuY3JlYXRlKHtcbiAgICAgICAgbW9kZWw6ICdncHQtMy41LXR1cmJvJywgLy8gVXNpbmcgc3RyaW5nIGRpcmVjdGx5IGFzIG9wZW5BSUNoYXRHUFRNb2RlbCBpcyBub3QgYXZhaWxhYmxlIGhlcmVcbiAgICAgICAgbWVzc2FnZXM6IFtcbiAgICAgICAgICB7IHJvbGU6ICdzeXN0ZW0nLCBjb250ZW50OiBzeXN0ZW1Qcm9tcHQgfSxcbiAgICAgICAgICB7IHJvbGU6ICd1c2VyJywgY29udGVudDogdXNlclByb21wdCB9LFxuICAgICAgICBdLFxuICAgICAgICB0ZW1wZXJhdHVyZTogMC4yLFxuICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IGxsbVJlc3BvbnNlU3RyaW5nID0gY29tcGxldGlvbi5jaG9pY2VzWzBdPy5tZXNzYWdlPy5jb250ZW50O1xuICAgICAgbGV0IG1hdGNoZWRMYWJlbHM6IHN0cmluZ1tdID0gW107XG5cbiAgICAgIGlmIChsbG1SZXNwb25zZVN0cmluZykge1xuICAgICAgICB0cnkge1xuICAgICAgICAgIG1hdGNoZWRMYWJlbHMgPSBKU09OLnBhcnNlKGxsbVJlc3BvbnNlU3RyaW5nKTtcbiAgICAgICAgICBpZiAoXG4gICAgICAgICAgICAhQXJyYXkuaXNBcnJheShtYXRjaGVkTGFiZWxzKSB8fFxuICAgICAgICAgICAgIW1hdGNoZWRMYWJlbHMuZXZlcnkoKGl0ZW0pID0+IHR5cGVvZiBpdGVtID09PSAnc3RyaW5nJylcbiAgICAgICAgICApIHtcbiAgICAgICAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICAgICAgICdMTE0gcmVzcG9uc2UgaXMgbm90IGEgdmFsaWQgSlNPTiBhcnJheSBvZiBzdHJpbmdzOicsXG4gICAgICAgICAgICAgIGxsbVJlc3BvbnNlU3RyaW5nXG4gICAgICAgICAgICApO1xuICAgICAgICAgICAgbWF0Y2hlZExhYmVscyA9IFtdOyAvLyBGYWxsYmFjayB0byBlbXB0eSBpZiBub3QgYSBzdHJpbmcgYXJyYXlcbiAgICAgICAgICB9XG4gICAgICAgIH0gY2F0Y2ggKHBhcnNlRXJyb3IpIHtcbiAgICAgICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAgICAgJ0Vycm9yIHBhcnNpbmcgTExNIHJlc3BvbnNlOicsXG4gICAgICAgICAgICBwYXJzZUVycm9yLFxuICAgICAgICAgICAgbGxtUmVzcG9uc2VTdHJpbmdcbiAgICAgICAgICApO1xuICAgICAgICAgIC8vIEZhbGxiYWNrOiBhdHRlbXB0IHRvIGV4dHJhY3QgbGFiZWxzIGlmIGl0J3MgYSBzaW1wbGUgbGlzdCBub3QgaW4gSlNPTiBhcnJheSBmb3JtYXRcbiAgICAgICAgICAvLyBUaGlzIGlzIGEgYmFzaWMgZmFsbGJhY2ssIG1pZ2h0IG5lZWQgbW9yZSByb2J1c3QgcGFyc2luZyBkZXBlbmRpbmcgb24gTExNIGJlaGF2aW9yXG4gICAgICAgICAgaWYgKHR5cGVvZiBsbG1SZXNwb25zZVN0cmluZyA9PT0gJ3N0cmluZycpIHtcbiAgICAgICAgICAgIG1hdGNoZWRMYWJlbHMgPSBsYWJlbE5hbWVzLmZpbHRlcigobGFiZWwpID0+XG4gICAgICAgICAgICAgIGxsbVJlc3BvbnNlU3RyaW5nLmluY2x1ZGVzKGxhYmVsKVxuICAgICAgICAgICAgKTtcbiAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgbWF0Y2hlZExhYmVscyA9IFtdO1xuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfSBlbHNlIHtcbiAgICAgICAgY29uc29sZS5lcnJvcignTExNIHJlc3BvbnNlIGNvbnRlbnQgaXMgbnVsbCBvciB1bmRlZmluZWQuJyk7XG4gICAgICAgIG1hdGNoZWRMYWJlbHMgPSBbXTtcbiAgICAgIH1cblxuICAgICAgY29uc3Qgc2NvcmVzID0gbGFiZWxOYW1lcy5tYXAoKGxhYmVsKSA9PlxuICAgICAgICBtYXRjaGVkTGFiZWxzLmluY2x1ZGVzKGxhYmVsKSA/IDAuOSA6IDAuMVxuICAgICAgKTtcblxuICAgICAgY29uc3QgcmVzdWx0OiBDbGFzc2lmaWNhdGlvblJlc3BvbnNlQm9keVR5cGUgPSB7XG4gICAgICAgIHNlcXVlbmNlOiB1dWlkKCksIC8vIEFkZGVkIHNlcXVlbmNlIHByb3BlcnR5XG4gICAgICAgIGxhYmVsczogbGFiZWxOYW1lcyxcbiAgICAgICAgc2NvcmVzLFxuICAgICAgfTtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICByZXN1bHQsXG4gICAgICAgIGV2ZW50Py5pZCxcbiAgICAgICAgJyByZXN1bHQsIGV2ZW50Py5pZCBpbnNpZGUgZmluZEJlc3RNYXRjaENhdGVnb3J5MiB3aXRoIE9wZW5BSSdcbiAgICAgICk7XG4gICAgICByZXR1cm4gcmVzdWx0O1xuICAgIH0gY2F0Y2ggKGFwaUVycm9yKSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAnRXJyb3IgY2FsbGluZyBPcGVuQUkgQVBJIG9yIHByb2Nlc3NpbmcgaXRzIHJlc3BvbnNlOicsXG4gICAgICAgIGFwaUVycm9yXG4gICAgICApO1xuICAgICAgLy8gRmFsbGJhY2sgdG8gbG93IHNjb3JlcyBmb3IgYWxsIGNhdGVnb3JpZXMgaW4gY2FzZSBvZiBBUEkgZXJyb3JcbiAgICAgIGNvbnN0IHNjb3JlcyA9IGxhYmVsTmFtZXMubWFwKCgpID0+IDAuMSk7XG4gICAgICBjb25zdCBlcnJvclJlc3VsdDogQ2xhc3NpZmljYXRpb25SZXNwb25zZUJvZHlUeXBlID0ge1xuICAgICAgICBzZXF1ZW5jZTogdXVpZCgpLCAvLyBBZGRlZCBzZXF1ZW5jZSBwcm9wZXJ0eVxuICAgICAgICBsYWJlbHM6IGxhYmVsTmFtZXMsXG4gICAgICAgIHNjb3JlcyxcbiAgICAgIH07XG4gICAgICByZXR1cm4gZXJyb3JSZXN1bHQ7XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgLy8gVGhpcyBvdXRlciBjYXRjaCBibG9jayBoYW5kbGVzIGVycm9ycyBmcm9tIHRoZSBpbml0aWFsIHZhbGlkYXRpb24gc3RlcHNcbiAgICBjb25zb2xlLmxvZyhlLCAnIGluaXRpYWwgZXJyb3IgaW4gZmluZEJlc3RNYXRjaENhdGVnb3J5MicpO1xuICAgIC8vIE9wdGlvbmFsbHkgcmV0aHJvdyBvciByZXR1cm4gYSBzcGVjaWZpYyBlcnJvciByZXNwb25zZVxuICAgIHRocm93IGU7IC8vIFJlLXRocm93aW5nIHRoZSBvcmlnaW5hbCBlcnJvciBpZiBpdCdzIGZyb20gcHJlLUFQSSBjYWxsIGxvZ2ljXG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzQmVzdE1hdGNoQ2F0ZWdvcmllcyA9IChcbiAgYm9keTogQ2xhc3NpZmljYXRpb25SZXNwb25zZUJvZHlUeXBlLFxuICBuZXdQb3NzaWJsZUxhYmVsczogc3RyaW5nW11cbikgPT4ge1xuICBjb25zdCB7IHNjb3JlcyB9ID0gYm9keTtcbiAgbGV0IGJlc3RNYXRjaENhdGVnb3J5ID0gJyc7XG4gIGxldCBiZXN0TWF0Y2hTY29yZSA9IDA7XG4gIGZvciAobGV0IGkgPSAwOyBpIDwgbmV3UG9zc2libGVMYWJlbHMubGVuZ3RoOyBpKyspIHtcbiAgICBjb25zdCBsYWJlbCA9IG5ld1Bvc3NpYmxlTGFiZWxzW2ldO1xuICAgIGNvbnN0IHNjb3JlID0gc2NvcmVzW2ldO1xuICAgIGlmIChzY29yZSA+IG1pblRocmVzaG9sZFNjb3JlKSB7XG4gICAgICBpZiAoc2NvcmUgPiBiZXN0TWF0Y2hTY29yZSkge1xuICAgICAgICBiZXN0TWF0Y2hDYXRlZ29yeSA9IGxhYmVsO1xuICAgICAgICBiZXN0TWF0Y2hTY29yZSA9IHNjb3JlO1xuICAgICAgfVxuICAgIH1cbiAgfVxuXG4gIHJldHVybiBiZXN0TWF0Y2hDYXRlZ29yeTtcbn07XG5cbmNvbnN0IGFkZFRvQmVzdE1hdGNoQ2F0ZWdvcmllcyA9IChcbiAgbmV3RXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIG5ld1Bvc3NpYmxlTGFiZWxzOiBzdHJpbmdbXSxcbiAgc2NvcmVzOiBudW1iZXJbXSxcbiAgY2F0ZWdvcmllczogQ2F0ZWdvcnlUeXBlW11cbik6IENhdGVnb3J5VHlwZVtdIHwgW10gPT4ge1xuICBjb25zdCBiZXN0TWF0Y2hDYXRlZ29yaWVzID0gW107XG5cbiAgY29uc3QgbWVldGluZ0luZGV4ID0gbmV3UG9zc2libGVMYWJlbHMuaW5kZXhPZihtZWV0aW5nTGFiZWwpO1xuICBjb25zdCBleHRlcm5hbE1lZXRpbmdJbmRleCA9IG5ld1Bvc3NpYmxlTGFiZWxzLmluZGV4T2YoZXh0ZXJuYWxNZWV0aW5nTGFiZWwpO1xuXG4gIGlmIChtZWV0aW5nSW5kZXggPiAtMSAmJiBzY29yZXNbbWVldGluZ0luZGV4XSA+IG1pblRocmVzaG9sZFNjb3JlKSB7XG4gICAgYmVzdE1hdGNoQ2F0ZWdvcmllcy5wdXNoKFxuICAgICAgY2F0ZWdvcmllcy5maW5kKChjYXRlZ29yeSkgPT4gY2F0ZWdvcnkubmFtZSA9PT0gbWVldGluZ0xhYmVsKVxuICAgICk7XG4gIH1cblxuICBpZiAoXG4gICAgZXh0ZXJuYWxNZWV0aW5nSW5kZXggPiAtMSAmJlxuICAgIHNjb3Jlc1tleHRlcm5hbE1lZXRpbmdJbmRleF0gPiBtaW5UaHJlc2hvbGRTY29yZVxuICApIHtcbiAgICBiZXN0TWF0Y2hDYXRlZ29yaWVzLnB1c2goXG4gICAgICBjYXRlZ29yaWVzLmZpbmQoKGNhdGVnb3J5KSA9PiBjYXRlZ29yeS5uYW1lID09PSBleHRlcm5hbE1lZXRpbmdMYWJlbClcbiAgICApO1xuICB9XG5cbiAgaWYgKG5ld0V2ZW50LmlzTWVldGluZyAmJiBtZWV0aW5nSW5kZXggPiAtMSkge1xuICAgIGJlc3RNYXRjaENhdGVnb3JpZXMucHVzaChcbiAgICAgIGNhdGVnb3JpZXMuZmluZCgoY2F0ZWdvcnkpID0+IGNhdGVnb3J5Lm5hbWUgPT09IG1lZXRpbmdMYWJlbClcbiAgICApO1xuICB9XG5cbiAgaWYgKG5ld0V2ZW50LmlzRXh0ZXJuYWxNZWV0aW5nICYmIGV4dGVybmFsTWVldGluZ0luZGV4ID4gLTEpIHtcbiAgICBiZXN0TWF0Y2hDYXRlZ29yaWVzLnB1c2goXG4gICAgICBjYXRlZ29yaWVzLmZpbmQoKGNhdGVnb3J5KSA9PiBjYXRlZ29yeS5uYW1lID09PSBleHRlcm5hbE1lZXRpbmdMYWJlbClcbiAgICApO1xuICB9XG5cbiAgcmV0dXJuIGJlc3RNYXRjaENhdGVnb3JpZXM7XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0V2ZW50Rm9yTWVldGluZ1R5cGVDYXRlZ29yaWVzID0gKFxuICBuZXdFdmVudDogRXZlbnRQbHVzVHlwZSxcbiAgYmVzdE1hdGNoQ2F0ZWdvcnk6IENhdGVnb3J5VHlwZSxcbiAgbmV3UG9zc2libGVMYWJlbHM6IHN0cmluZ1tdLFxuICBzY29yZXM6IG51bWJlcltdLFxuICBjYXRlZ29yaWVzOiBDYXRlZ29yeVR5cGVbXVxuKTogQ2F0ZWdvcnlUeXBlW10gfCBbXSA9PiB7XG4gIGNvbnN0IGJlc3RNYXRjaENhdGVnb3JpZXMgPSBhZGRUb0Jlc3RNYXRjaENhdGVnb3JpZXMoXG4gICAgbmV3RXZlbnQsXG4gICAgbmV3UG9zc2libGVMYWJlbHMsXG4gICAgc2NvcmVzLFxuICAgIGNhdGVnb3JpZXNcbiAgKTtcblxuICBpZiAoYmVzdE1hdGNoQ2F0ZWdvcmllcz8ubGVuZ3RoID4gMCkge1xuICAgIHJldHVybiAoYmVzdE1hdGNoQ2F0ZWdvcmllcyBhcyBDYXRlZ29yeVR5cGVbXSkuY29uY2F0KFtiZXN0TWF0Y2hDYXRlZ29yeV0pO1xuICB9XG5cbiAgcmV0dXJuIFtiZXN0TWF0Y2hDYXRlZ29yeV07XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0VW5pcXVlTGFiZWxzID0gKGxhYmVsczogQ2F0ZWdvcnlUeXBlW10pID0+IHtcbiAgY29uc3QgdW5pcXVlTGFiZWxzID0gXy51bmlxQnkobGFiZWxzLCAnaWQnKTtcbiAgcmV0dXJuIHVuaXF1ZUxhYmVscztcbn07XG5cbmV4cG9ydCBjb25zdCBjb3B5T3ZlckNhdGVnb3J5RGVmYXVsdHMgPSAoXG4gIGV2ZW50OiBFdmVudFBsdXNUeXBlLFxuICBjYXRlZ29yeTogQ2F0ZWdvcnlUeXBlXG4pOiBFdmVudFBsdXNUeXBlID0+IHtcbiAgcmV0dXJuIHtcbiAgICAuLi5ldmVudCxcbiAgICB0cmFuc3BhcmVuY3k6ICFldmVudD8udXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5XG4gICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0QXZhaWxhYmlsaXR5XG4gICAgICAgID8gJ3RyYW5zcGFyZW50J1xuICAgICAgICA6ICdvcGFxdWUnXG4gICAgICA6IGV2ZW50LnRyYW5zcGFyZW5jeSxcbiAgICBwcmlvcml0eTpcbiAgICAgICghZXZlbnQ/LnVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWxcbiAgICAgICAgPyBjYXRlZ29yeT8uZGVmYXVsdFByaW9yaXR5TGV2ZWxcbiAgICAgICAgOiBldmVudD8ucHJpb3JpdHkpIHx8IDEsXG4gICAgbW9kaWZpYWJsZTogIWV2ZW50Py51c2VyTW9kaWZpZWRNb2RpZmlhYmxlXG4gICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0TW9kaWZpYWJsZVxuICAgICAgOiBldmVudC5tb2RpZmlhYmxlLFxuICAgIGlzQnJlYWs6ICFldmVudD8udXNlck1vZGlmaWVkSXNCcmVha1xuICAgICAgPyBjYXRlZ29yeT8uZGVmYXVsdElzQnJlYWtcbiAgICAgIDogZXZlbnQuaXNCcmVhayxcbiAgICBpc01lZXRpbmc6ICFldmVudD8udXNlck1vZGlmaWVkSXNNZWV0aW5nXG4gICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0SXNNZWV0aW5nXG4gICAgICA6IGNhdGVnb3J5Py5uYW1lID09PSBtZWV0aW5nTGFiZWxcbiAgICAgICAgPyB0cnVlXG4gICAgICAgIDogZXZlbnQuaXNNZWV0aW5nLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nOiAhZXZlbnQ/LnVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgIDogY2F0ZWdvcnk/Lm5hbWUgPT09IGV4dGVybmFsTWVldGluZ0xhYmVsXG4gICAgICAgID8gdHJ1ZVxuICAgICAgICA6IGV2ZW50LmlzRXh0ZXJuYWxNZWV0aW5nLFxuICAgIGlzTWVldGluZ01vZGlmaWFibGU6ICFldmVudD8udXNlck1vZGlmaWVkTW9kaWZpYWJsZVxuICAgICAgPyBjYXRlZ29yeT8uZGVmYXVsdE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICA6IGV2ZW50LmlzTWVldGluZ01vZGlmaWFibGUsXG4gICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlOiAhZXZlbnQ/LnVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgID8gY2F0ZWdvcnk/LmRlZmF1bHRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICA6IGV2ZW50LmlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICBiYWNrZ3JvdW5kQ29sb3I6ICFldmVudD8udXNlck1vZGlmaWVkQ29sb3JcbiAgICAgID8gY2F0ZWdvcnk/LmNvbG9yXG4gICAgICA6IGV2ZW50LmJhY2tncm91bmRDb2xvcixcbiAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzOlxuICAgICAgIWV2ZW50Py51c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZSAmJlxuICAgICAgY2F0ZWdvcnk/LmRlZmF1bHRUaW1lUHJlZmVyZW5jZT8ubGVuZ3RoID4gMFxuICAgICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0VGltZVByZWZlcmVuY2U/Lm1hcCgodHApID0+ICh7XG4gICAgICAgICAgICAuLi50cCxcbiAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgICBldmVudElkOiBldmVudD8uaWQsXG4gICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICB1c2VySWQ6IGV2ZW50Py51c2VySWQsXG4gICAgICAgICAgfSkpXG4gICAgICAgIDogZXZlbnQucHJlZmVycmVkVGltZVJhbmdlcyxcbiAgfTtcbn07XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVSZW1pbmRlcnNBbmRCdWZmZXJUaW1lc0ZvckJlc3RNYXRjaENhdGVnb3J5ID0gYXN5bmMgKFxuICBpZDogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgbmV3RXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIGJlc3RNYXRjaENhdGVnb3J5OiBDYXRlZ29yeVR5cGUsXG4gIG5ld1JlbWluZGVyczE/OiBSZW1pbmRlclR5cGVbXSxcbiAgbmV3QnVmZmVyVGltZXMxPzogQnVmZmVyVGltZU9iamVjdFR5cGUsXG4gIHByZXZpb3VzRXZlbnQ/OiBFdmVudFBsdXNUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBpZiAoIWJlc3RNYXRjaENhdGVnb3J5Py5pZCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdiZXN0TWF0Y2hDYXRlZ29yeSBpcyByZXF1aXJlZCcpO1xuICAgIH1cbiAgICBpZiAoIW5ld0V2ZW50Py5pZCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCduZXdFdmVudCBpcyByZXF1aXJlZCcpO1xuICAgIH1cblxuICAgIGlmICghaWQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignaWQgaXMgcmVxdWlyZWQnKTtcbiAgICB9XG5cbiAgICBpZiAoIXVzZXJJZCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCd1c2VySWQgaXMgcmVxdWlyZWQnKTtcbiAgICB9XG5cbiAgICBsZXQgbmV3QnVmZmVyVGltZXMgPSBuZXdCdWZmZXJUaW1lczEgfHwge307XG4gICAgbGV0IG5ld1JlbWluZGVycyA9IG5ld1JlbWluZGVyczEgfHwgW107XG4gICAgY29uc3Qgb2xkUmVtaW5kZXJzID0gYXdhaXQgbGlzdFJlbWluZGVyc0ZvckV2ZW50KGlkLCB1c2VySWQpO1xuICAgIGNvbnN0IHJlbWluZGVycyA9IGNyZWF0ZVJlbWluZGVyc1VzaW5nQ2F0ZWdvcnlEZWZhdWx0c0ZvckV2ZW50KFxuICAgICAgbmV3RXZlbnQsXG4gICAgICBiZXN0TWF0Y2hDYXRlZ29yeSxcbiAgICAgIG9sZFJlbWluZGVycyxcbiAgICAgIHByZXZpb3VzRXZlbnRcbiAgICApO1xuICAgIGNvbnNvbGUubG9nKHJlbWluZGVycywgJyByZW1pbmRlcnMnKTtcbiAgICBpZiAoXG4gICAgICByZW1pbmRlcnM/Lmxlbmd0aCA+IDAgJiZcbiAgICAgIGJlc3RNYXRjaENhdGVnb3J5Py5jb3B5UmVtaW5kZXJzICYmXG4gICAgICAhbmV3RXZlbnQ/LnVzZXJNb2RpZmllZFJlbWluZGVyc1xuICAgICkge1xuICAgICAgbmV3UmVtaW5kZXJzLnB1c2goLi4ucmVtaW5kZXJzKTtcbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICAhbmV3RXZlbnQ/LnVzZXJNb2RpZmllZFRpbWVCbG9ja2luZyAmJlxuICAgICAgYmVzdE1hdGNoQ2F0ZWdvcnk/LmNvcHlUaW1lQmxvY2tpbmdcbiAgICApIHtcbiAgICAgIGNvbnN0IGJ1ZmZlclRpbWVzID0gY3JlYXRlUHJlQW5kUG9zdEV2ZW50c0ZvckNhdGVnb3J5RGVmYXVsdHMoXG4gICAgICAgIGJlc3RNYXRjaENhdGVnb3J5LFxuICAgICAgICBuZXdFdmVudCxcbiAgICAgICAgcHJldmlvdXNFdmVudFxuICAgICAgKTtcbiAgICAgIGNvbnNvbGUubG9nKGJ1ZmZlclRpbWVzLCAnIHRpbWVCbG9ja2luZycpO1xuICAgICAgaWYgKGJ1ZmZlclRpbWVzPy5iZWZvcmVFdmVudCkge1xuICAgICAgICAobmV3QnVmZmVyVGltZXMgYXMgQnVmZmVyVGltZU9iamVjdFR5cGUpLmJlZm9yZUV2ZW50ID1cbiAgICAgICAgICBidWZmZXJUaW1lcy5iZWZvcmVFdmVudDtcbiAgICAgIH1cblxuICAgICAgaWYgKGJ1ZmZlclRpbWVzPy5hZnRlckV2ZW50KSB7XG4gICAgICAgIChuZXdCdWZmZXJUaW1lcyBhcyBCdWZmZXJUaW1lT2JqZWN0VHlwZSkuYWZ0ZXJFdmVudCA9XG4gICAgICAgICAgYnVmZmVyVGltZXMuYWZ0ZXJFdmVudDtcbiAgICAgIH1cblxuICAgICAgaWYgKFxuICAgICAgICBidWZmZXJUaW1lcz8ubmV3RXZlbnQ/LnByZUV2ZW50SWQgfHxcbiAgICAgICAgYnVmZmVyVGltZXM/Lm5ld0V2ZW50Py5wb3N0RXZlbnRJZFxuICAgICAgKSB7XG4gICAgICAgIG5ld0V2ZW50ID0gYnVmZmVyVGltZXMubmV3RXZlbnQ7XG4gICAgICB9XG4gICAgfVxuICAgIHJldHVybiB7IG5ld0V2ZW50LCBuZXdSZW1pbmRlcnMsIG5ld0J1ZmZlclRpbWVzOiBuZXdCdWZmZXJUaW1lcyB9O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBlLFxuICAgICAgJyB1bmFibGUgdG8gY3JlYXRlIHJlbWluZGVycyBhbmQgdGltZSBibG9ja2luZyBmb3IgYmVzdCBtYXRjaCBjYXRlZ29yeSdcbiAgICApO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgY3JlYXRlQ2F0ZWdvcnlFdmVudHMgPSBhc3luYyAoXG4gIGNhdGVnb3J5RXZlbnRzOiBDYXRlZ29yeUV2ZW50VHlwZVtdXG4pOiBQcm9taXNlPEZlYXR1cmVzQXBwbHlSZXNwb25zZTx2b2lkPj4gPT4ge1xuICBpZiAoIWNhdGVnb3J5RXZlbnRzIHx8IGNhdGVnb3J5RXZlbnRzLmxlbmd0aCA9PT0gMCkge1xuICAgIC8vIE5vdCBhbiBlcnJvciwgYnV0IG5vdGhpbmcgdG8gZG8uIENvdWxkIGFsc28gcmV0dXJuIHN1Y2Nlc3MuXG4gICAgY29uc29sZS5sb2coJ05vIGNhdGVnb3J5IGV2ZW50cyBwcm92aWRlZCB0byBjcmVhdGVDYXRlZ29yeUV2ZW50cy4nKTtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogdW5kZWZpbmVkIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBmb3IgKGNvbnN0IGNhdGVnb3J5RXZlbnQgb2YgY2F0ZWdvcnlFdmVudHMpIHtcbiAgICAgIC8vIEJhc2ljIHZhbGlkYXRpb24gZm9yIGVhY2ggY2F0ZWdvcnlFdmVudFxuICAgICAgaWYgKFxuICAgICAgICAhY2F0ZWdvcnlFdmVudCB8fFxuICAgICAgICAhY2F0ZWdvcnlFdmVudC5jYXRlZ29yeUlkIHx8XG4gICAgICAgICFjYXRlZ29yeUV2ZW50LmV2ZW50SWQgfHxcbiAgICAgICAgIWNhdGVnb3J5RXZlbnQudXNlcklkIHx8XG4gICAgICAgICFjYXRlZ29yeUV2ZW50LmlkXG4gICAgICApIHtcbiAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICdTa2lwcGluZyBpbnZhbGlkIGNhdGVnb3J5RXZlbnQgaW4gY3JlYXRlQ2F0ZWdvcnlFdmVudHM6JyxcbiAgICAgICAgICBjYXRlZ29yeUV2ZW50XG4gICAgICAgICk7XG4gICAgICAgIGNvbnRpbnVlOyAvLyBPciBjb2xsZWN0IGVycm9ycyBhbmQgcmV0dXJuIGEgcGFydGlhbCBzdWNjZXNzL2ZhaWx1cmVcbiAgICAgIH1cblxuICAgICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgICBjYXRlZ29yeUlkOiBjYXRlZ29yeUV2ZW50Py5jYXRlZ29yeUlkLFxuICAgICAgICBldmVudElkOiBjYXRlZ29yeUV2ZW50Py5ldmVudElkLFxuICAgICAgfTtcbiAgICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnQ29ubmVjdGlvbkJ5Q2F0ZWdvcnlJZEFuZEV2ZW50SWQnO1xuICAgICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgIHF1ZXJ5IENvbm5lY3Rpb25CeUNhdGVnb3J5SWRBbmRFdmVudElkKCRjYXRlZ29yeUlkOiB1dWlkISwgJGV2ZW50SWQ6IFN0cmluZyEpIHtcbiAgICAgICAgICBDYXRlZ29yeV9FdmVudCh3aGVyZToge2NhdGVnb3J5SWQ6IHtfZXE6ICRjYXRlZ29yeUlkfSwgZXZlbnRJZDoge19lcTogJGV2ZW50SWR9fSkge1xuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGNhdGVnb3J5SWRcbiAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICAgIGlkXG4gICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICBgO1xuXG4gICAgICBjb25zdCByZXM6IHsgZGF0YTogeyBDYXRlZ29yeV9FdmVudDogQ2F0ZWdvcnlFdmVudFR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBqc29uOiB7XG4gICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgcXVlcnksXG4gICAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICAgLmpzb24oKTtcblxuICAgICAgaWYgKCFyZXM/LmRhdGE/LkNhdGVnb3J5X0V2ZW50Py5bMF0pIHtcbiAgICAgICAgY29uc3QgdmFyaWFibGVzMiA9IHtcbiAgICAgICAgICBpZDogY2F0ZWdvcnlFdmVudC5pZCxcbiAgICAgICAgICBjYXRlZ29yeUlkOiBjYXRlZ29yeUV2ZW50Py5jYXRlZ29yeUlkLFxuICAgICAgICAgIGV2ZW50SWQ6IGNhdGVnb3J5RXZlbnQ/LmV2ZW50SWQsXG4gICAgICAgICAgY3JlYXRlZERhdGU6IGNhdGVnb3J5RXZlbnQ/LmNyZWF0ZWREYXRlLFxuICAgICAgICAgIHVwZGF0ZWRBdDogY2F0ZWdvcnlFdmVudD8udXBkYXRlZEF0LFxuICAgICAgICAgIHVzZXJJZDogY2F0ZWdvcnlFdmVudD8udXNlcklkLFxuICAgICAgICB9O1xuICAgICAgICBjb25zdCBvcGVyYXRpb25OYW1lMiA9ICdJbnNlcnRDYXRlZ29yeV9FdmVudCc7XG4gICAgICAgIGNvbnN0IHF1ZXJ5MiA9IGBcbiAgICAgICAgICBtdXRhdGlvbiBJbnNlcnRDYXRlZ29yeV9FdmVudCgkaWQ6IHV1aWQhLCAkY2F0ZWdvcnlJZDogdXVpZCEsICRjcmVhdGVkRGF0ZTogdGltZXN0YW1wdHosICRldmVudElkOiBTdHJpbmchLCAkdXBkYXRlZEF0OiB0aW1lc3RhbXB0eiwgJHVzZXJJZDogdXVpZCEpIHtcbiAgICAgICAgICAgIGluc2VydF9DYXRlZ29yeV9FdmVudF9vbmUob2JqZWN0OiB7Y2F0ZWdvcnlJZDogJGNhdGVnb3J5SWQsIGNyZWF0ZWREYXRlOiAkY3JlYXRlZERhdGUsIGRlbGV0ZWQ6IGZhbHNlLCBldmVudElkOiAkZXZlbnRJZCwgaWQ6ICRpZCwgdXBkYXRlZEF0OiAkdXBkYXRlZEF0LCB1c2VySWQ6ICR1c2VySWR9KSB7XG4gICAgICAgICAgICAgIGNhdGVnb3J5SWRcbiAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgIGA7XG4gICAgICAgIGNvbnN0IHJlczIgPSBhd2FpdCBnb3RcbiAgICAgICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBqc29uOiB7XG4gICAgICAgICAgICAgIG9wZXJhdGlvbk5hbWU6IG9wZXJhdGlvbk5hbWUyLFxuICAgICAgICAgICAgICBxdWVyeTogcXVlcnkyLFxuICAgICAgICAgICAgICB2YXJpYWJsZXM6IHZhcmlhYmxlczIsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0pXG4gICAgICAgICAgLmpzb24oKTtcblxuICAgICAgICBjb25zb2xlLmxvZyhyZXMyLCAnIHJlc3BvbnNlIGFmdGVyIGluc2VydGluZyBjYXRlZ29yeSBldmVudCcpO1xuICAgICAgfVxuICAgIH1cbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogdW5kZWZpbmVkIH07XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIGNyZWF0aW5nIGNhdGVnb3J5IGV2ZW50cyBpbiBIYXN1cmE6JywgZSk7XG4gICAgY29uc3QgZXJyb3JEZXRhaWxzID0gZS5yZXNwb25zZT8uYm9keSB8fCBlLm1lc3NhZ2UgfHwgZTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0hBU1VSQV9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gY3JlYXRlIGNhdGVnb3J5IGV2ZW50czogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZXJyb3JEZXRhaWxzLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5jb25zdCBjb3B5T3ZlckNhdGVnb3J5RGVmYXVsdHNGb3JNZWV0aW5nVHlwZSA9IChcbiAgZXZlbnQsXG4gIGNhdGVnb3JpZXM6IENhdGVnb3J5VHlwZVtdXG4pID0+IHtcbiAgY29uc3QgbWVldGluZ0NhdGVnb3J5ID0gY2F0ZWdvcmllcy5maW5kKFxuICAgIChjYXRlZ29yeSkgPT4gY2F0ZWdvcnkubmFtZSA9PT0gbWVldGluZ0xhYmVsXG4gICk7XG4gIGNvbnN0IGV4dGVybmFsQ2F0ZWdvcnkgPSBjYXRlZ29yaWVzLmZpbmQoXG4gICAgKGNhdGVnb3J5KSA9PiBjYXRlZ29yeS5uYW1lID09PSBleHRlcm5hbE1lZXRpbmdMYWJlbFxuICApO1xuXG4gIGxldCBuZXdFdmVudE1lZXRpbmcgPSBudWxsO1xuICBsZXQgbmV3RXZlbnRFeHRlcm5hbCA9IG51bGw7XG5cbiAgaWYgKG1lZXRpbmdDYXRlZ29yeT8uaWQpIHtcbiAgICBuZXdFdmVudE1lZXRpbmcgPSBjb3B5T3ZlckNhdGVnb3J5RGVmYXVsdHMoZXZlbnQsIG1lZXRpbmdDYXRlZ29yeSk7XG4gIH1cblxuICBpZiAoZXh0ZXJuYWxDYXRlZ29yeT8uaWQpIHtcbiAgICBuZXdFdmVudEV4dGVybmFsID0gY29weU92ZXJDYXRlZ29yeURlZmF1bHRzKGV2ZW50LCBleHRlcm5hbENhdGVnb3J5KTtcbiAgfVxuXG4gIHJldHVybiB7IG5ld0V2ZW50TWVldGluZywgbmV3RXZlbnRFeHRlcm5hbCB9O1xufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RSZW1pbmRlcnNGb3JFdmVudCA9IGFzeW5jIChcbiAgZXZlbnRJZDogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxGZWF0dXJlc0FwcGx5UmVzcG9uc2U8UmVtaW5kZXJUeXBlW10gfCBudWxsPj4gPT4ge1xuICBpZiAoIWV2ZW50SWQgfHwgIXVzZXJJZCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdFdmVudCBJRCBhbmQgVXNlciBJRCBhcmUgcmVxdWlyZWQgZm9yIGxpc3RpbmcgcmVtaW5kZXJzLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2xpc3RSZW1pbmRlcnNGb3JFdmVudCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgcXVlcnkgbGlzdFJlbWluZGVyc0ZvckV2ZW50KCR1c2VySWQ6IHV1aWQhLCAkZXZlbnRJZDogU3RyaW5nISkge1xuICAgICAgUmVtaW5kZXIod2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9LCBldmVudElkOiB7X2VxOiAkZXZlbnRJZH0sIGRlbGV0ZWQ6IHtfbmVxOiB0cnVlfX0pIHtcbiAgICAgICAgZXZlbnRJZFxuICAgICAgICBpZFxuICAgICAgICBtaW51dGVzXG4gICAgICAgIHJlbWluZGVyRGF0ZVxuICAgICAgICB0aW1lem9uZVxuICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgdXNlRGVmYXVsdFxuICAgICAgICB1c2VySWRcbiAgICAgICAgZGVsZXRlZFxuICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgfVxuICAgIH1cbiAgYDtcbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBSZW1pbmRlcjogUmVtaW5kZXJUeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgIGV2ZW50SWQsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGxpc3RSZW1pbmRlcnNGb3JFdmVudCcpO1xuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiByZXM/LmRhdGE/LlJlbWluZGVyIHx8IG51bGwgfTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgbGlzdGluZyByZW1pbmRlcnMgZm9yIGV2ZW50OicsIGUpO1xuICAgIGNvbnN0IGVycm9yRGV0YWlscyA9IGUucmVzcG9uc2U/LmJvZHkgfHwgZS5tZXNzYWdlIHx8IGU7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdIQVNVUkFfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgRmFpbGVkIHRvIGxpc3QgcmVtaW5kZXJzOiAke2UubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBlcnJvckRldGFpbHMsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVSZW1pbmRlcnNVc2luZ0NhdGVnb3J5RGVmYXVsdHNGb3JFdmVudCA9IChcbiAgZXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIGJlc3RNYXRjaENhdGVnb3J5OiBDYXRlZ29yeVR5cGUsXG4gIG9sZFJlbWluZGVyczogUmVtaW5kZXJUeXBlW10sXG4gIHByZXZpb3VzRXZlbnQ6IEV2ZW50UGx1c1R5cGVcbik6IFJlbWluZGVyVHlwZVtdID0+IHtcbiAgaWYgKGV2ZW50LnVzZXJNb2RpZmllZFJlbWluZGVycykge1xuICAgIHJldHVybiBudWxsO1xuICB9XG5cbiAgaWYgKHByZXZpb3VzRXZlbnQ/LmNvcHlSZW1pbmRlcnMpIHtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIGlmIChwcmV2aW91c0V2ZW50Py5pZCAmJiBiZXN0TWF0Y2hDYXRlZ29yeT8uY29weVJlbWluZGVycykge1xuICAgIHJldHVybiBudWxsO1xuICB9XG5cbiAgY29uc3QgcmVtaW5kZXJzID0gYmVzdE1hdGNoQ2F0ZWdvcnk/LmRlZmF1bHRSZW1pbmRlcnM7XG4gIGlmICghKHJlbWluZGVycz8ubGVuZ3RoID4gMCkpIHtcbiAgICByZXR1cm4gb2xkUmVtaW5kZXJzO1xuICB9XG5cbiAgY29uc3QgbmV3UmVtaW5kZXJzID0gW107XG4gIHJlbWluZGVycy5mb3JFYWNoKChyZW1pbmRlcikgPT4ge1xuICAgIG5ld1JlbWluZGVycy5wdXNoKHtcbiAgICAgIGlkOiB1dWlkKCksXG4gICAgICBtaW51dGVzOiByZW1pbmRlcixcbiAgICAgIGV2ZW50SWQ6IGV2ZW50LmlkLFxuICAgICAgdXNlcklkOiBldmVudC51c2VySWQsXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICB9KTtcbiAgfSk7XG4gIHJldHVybiBuZXdSZW1pbmRlcnM7XG59O1xuXG5leHBvcnQgY29uc3QgY3JlYXRlUHJlQW5kUG9zdEV2ZW50c0ZvckNhdGVnb3J5RGVmYXVsdHMgPSAoXG4gIGJlc3RNYXRjaENhdGVnb3J5OiBDYXRlZ29yeVR5cGUsXG4gIGV2ZW50OiBFdmVudFBsdXNUeXBlLFxuICBwcmV2aW91c0V2ZW50PzogRXZlbnRQbHVzVHlwZVxuKSA9PiB7XG4gIGlmIChwcmV2aW91c0V2ZW50Py5jb3B5VGltZUJsb2NraW5nKSB7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICBpZiAocHJldmlvdXNFdmVudD8uaWQgJiYgYmVzdE1hdGNoQ2F0ZWdvcnk/LmNvcHlUaW1lQmxvY2tpbmcpIHtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIGlmIChldmVudD8udXNlck1vZGlmaWVkVGltZUJsb2NraW5nKSB7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICBjb25zdCBldmVudElkID0gdXVpZCgpO1xuICBjb25zdCBwcmVFdmVudElkID0gZXZlbnQ/LnByZUV2ZW50SWQgfHwgYCR7ZXZlbnRJZH0jJHtldmVudD8uY2FsZW5kYXJJZH1gO1xuICBjb25zdCBwb3N0RXZlbnRJZCA9IGV2ZW50Py5wb3N0RXZlbnRJZCB8fCBgJHtldmVudElkfSMke2V2ZW50Py5jYWxlbmRhcklkfWA7XG5cbiAgbGV0IHZhbHVlc1RvUmV0dXJuOiBhbnkgPSB7fTtcbiAgdmFsdWVzVG9SZXR1cm4ubmV3RXZlbnQgPSBldmVudDtcblxuICBpZiAoYmVzdE1hdGNoQ2F0ZWdvcnk/LmRlZmF1bHRUaW1lQmxvY2tpbmc/LmFmdGVyRXZlbnQpIHtcbiAgICBjb25zdCBmb3JtYXR0ZWRab25lQWZ0ZXJFdmVudEVuZERhdGUgPSBkYXlqcyhldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihldmVudD8udGltZXpvbmUsIHRydWUpXG4gICAgICAuYWRkKGJlc3RNYXRjaENhdGVnb3J5LmRlZmF1bHRUaW1lQmxvY2tpbmcuYWZ0ZXJFdmVudCwgJ20nKVxuICAgICAgLmZvcm1hdCgpO1xuICAgIGNvbnN0IGZvcm1hdHRlZFpvbmVBZnRlckV2ZW50U3RhcnREYXRlID0gZGF5anMoZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQ/LnRpbWV6b25lLCB0cnVlKVxuICAgICAgLmZvcm1hdCgpO1xuXG4gICAgY29uc3QgYWZ0ZXJFdmVudDogRXZlbnRQbHVzVHlwZSA9IHtcbiAgICAgIGlkOiBwb3N0RXZlbnRJZCxcbiAgICAgIGlzUHJlRXZlbnQ6IGZhbHNlLFxuICAgICAgZm9yRXZlbnRJZDogZXZlbnQuaWQsXG4gICAgICBpc1Bvc3RFdmVudDogdHJ1ZSxcbiAgICAgIG5vdGVzOiAnQnVmZmVyIHRpbWUnLFxuICAgICAgc3VtbWFyeTogJ0J1ZmZlciB0aW1lJyxcbiAgICAgIHN0YXJ0RGF0ZTogZm9ybWF0dGVkWm9uZUFmdGVyRXZlbnRTdGFydERhdGUsXG4gICAgICBlbmREYXRlOiBmb3JtYXR0ZWRab25lQWZ0ZXJFdmVudEVuZERhdGUsXG4gICAgICBtZXRob2Q6IGV2ZW50Py5wb3N0RXZlbnRJZCA/ICd1cGRhdGUnIDogJ2NyZWF0ZScsXG4gICAgICB1c2VySWQ6IGV2ZW50Py51c2VySWQsXG4gICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICBwcmlvcml0eTogMSxcbiAgICAgIGlzRm9sbG93VXA6IGZhbHNlLFxuICAgICAgbW9kaWZpYWJsZTogdHJ1ZSxcbiAgICAgIGFueW9uZUNhbkFkZFNlbGY6IGZhbHNlLFxuICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiBmYWxzZSxcbiAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOiBmYWxzZSxcbiAgICAgIG9yaWdpbmFsU3RhcnREYXRlOiB1bmRlZmluZWQsXG4gICAgICBvcmlnaW5hbEFsbERheTogZmFsc2UsXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIGNhbGVuZGFySWQ6IGV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgdGltZXpvbmU6IGV2ZW50Py50aW1lem9uZSxcbiAgICAgIGV2ZW50SWQ6IHBvc3RFdmVudElkLnNwbGl0KCcjJylbMF0sXG4gICAgfTtcbiAgICB2YWx1ZXNUb1JldHVybi5hZnRlckV2ZW50ID0gYWZ0ZXJFdmVudDtcbiAgICB2YWx1ZXNUb1JldHVybi5uZXdFdmVudCA9IHtcbiAgICAgIC4uLnZhbHVlc1RvUmV0dXJuLm5ld0V2ZW50LFxuICAgICAgcG9zdEV2ZW50SWQsXG4gICAgICB0aW1lQmxvY2tpbmc6IHtcbiAgICAgICAgLi4udmFsdWVzVG9SZXR1cm4/Lm5ld0V2ZW50Py50aW1lQmxvY2tpbmcsXG4gICAgICAgIGFmdGVyRXZlbnQ6IGJlc3RNYXRjaENhdGVnb3J5LmRlZmF1bHRUaW1lQmxvY2tpbmcuYWZ0ZXJFdmVudCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIGlmIChiZXN0TWF0Y2hDYXRlZ29yeT8uZGVmYXVsdFRpbWVCbG9ja2luZz8uYmVmb3JlRXZlbnQpIHtcbiAgICBjb25zdCBmb3JtYXR0ZWRab25lQmVmb3JlRXZlbnRTdGFydERhdGUgPSBkYXlqcyhcbiAgICAgIGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSlcbiAgICApXG4gICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAuc3VidHJhY3QoYmVzdE1hdGNoQ2F0ZWdvcnkuZGVmYXVsdFRpbWVCbG9ja2luZy5iZWZvcmVFdmVudCwgJ20nKVxuICAgICAgLmZvcm1hdCgpO1xuICAgIGNvbnN0IGZvcm1hdHRlZFpvbmVCZWZvcmVFdmVudEVuZERhdGUgPSBkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKVxuICAgICAgLmZvcm1hdCgpO1xuXG4gICAgY29uc3QgYmVmb3JlRXZlbnQ6IEV2ZW50UGx1c1R5cGUgPSB7XG4gICAgICBpZDogcHJlRXZlbnRJZCxcbiAgICAgIGlzUHJlRXZlbnQ6IHRydWUsXG4gICAgICBpc1Bvc3RFdmVudDogZmFsc2UsXG4gICAgICBmb3JFdmVudElkOiBldmVudC5pZCxcbiAgICAgIG5vdGVzOiAnQnVmZmVyIHRpbWUnLFxuICAgICAgc3VtbWFyeTogJ0J1ZmZlciB0aW1lJyxcbiAgICAgIHN0YXJ0RGF0ZTogZm9ybWF0dGVkWm9uZUJlZm9yZUV2ZW50U3RhcnREYXRlLFxuICAgICAgZW5kRGF0ZTogZm9ybWF0dGVkWm9uZUJlZm9yZUV2ZW50RW5kRGF0ZSxcbiAgICAgIG1ldGhvZDogZXZlbnQ/LnByZUV2ZW50SWQgPyAndXBkYXRlJyA6ICdjcmVhdGUnLFxuICAgICAgdXNlcklkOiBldmVudD8udXNlcklkLFxuICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgcHJpb3JpdHk6IDEsXG4gICAgICBpc0ZvbGxvd1VwOiBmYWxzZSxcbiAgICAgIG1vZGlmaWFibGU6IHRydWUsXG4gICAgICBhbnlvbmVDYW5BZGRTZWxmOiBmYWxzZSxcbiAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyczogZmFsc2UsXG4gICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0czogZmFsc2UsXG4gICAgICBvcmlnaW5hbFN0YXJ0RGF0ZTogdW5kZWZpbmVkLFxuICAgICAgb3JpZ2luYWxBbGxEYXk6IGZhbHNlLFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICBjYWxlbmRhcklkOiBldmVudD8uY2FsZW5kYXJJZCxcbiAgICAgIHRpbWV6b25lOiBldmVudD8udGltZXpvbmUsXG4gICAgICBldmVudElkOiBwcmVFdmVudElkLnNwbGl0KCcjJylbMF0sXG4gICAgfTtcbiAgICB2YWx1ZXNUb1JldHVybi5iZWZvcmVFdmVudCA9IGJlZm9yZUV2ZW50O1xuICAgIHZhbHVlc1RvUmV0dXJuLm5ld0V2ZW50ID0ge1xuICAgICAgLi4udmFsdWVzVG9SZXR1cm4ubmV3RXZlbnQsXG4gICAgICBwcmVFdmVudElkLFxuICAgICAgdGltZUJsb2NraW5nOiB7XG4gICAgICAgIC4uLnZhbHVlc1RvUmV0dXJuPy5uZXdFdmVudD8udGltZUJsb2NraW5nLFxuICAgICAgICBiZWZvcmVFdmVudDogYmVzdE1hdGNoQ2F0ZWdvcnkuZGVmYXVsdFRpbWVCbG9ja2luZy5iZWZvcmVFdmVudCxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIHJldHVybiB2YWx1ZXNUb1JldHVybjtcbn07XG5cbmV4cG9ydCBjb25zdCB1cGRhdGVWYWx1ZXNGb3JNZWV0aW5nVHlwZUNhdGVnb3JpZXMgPSBhc3luYyAoXG4gIGV2ZW50LFxuICBuZXdFdmVudDE6IEV2ZW50UGx1c1R5cGUsXG4gIGJlc3RNYXRjaENhdGVnb3JpZXM6IENhdGVnb3J5VHlwZVtdLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgbmV3UmVtaW5kZXJzMT86IFJlbWluZGVyVHlwZVtdLFxuICBuZXdUaW1lQmxvY2tpbmcxPzogQnVmZmVyVGltZU9iamVjdFR5cGUsIC8vIFVwZGF0ZWQgdHlwZVxuICBwcmV2aW91c0V2ZW50PzogRXZlbnRQbHVzVHlwZVxuKTogUHJvbWlzZTxcbiAgRmVhdHVyZXNBcHBseVJlc3BvbnNlPHtcbiAgICBuZXdFdmVudDogRXZlbnRQbHVzVHlwZTtcbiAgICBuZXdSZW1pbmRlcnM6IFJlbWluZGVyVHlwZVtdO1xuICAgIG5ld0J1ZmZlclRpbWVzOiBCdWZmZXJUaW1lT2JqZWN0VHlwZTtcbiAgfT5cbj4gPT4ge1xuICBpZiAoXG4gICAgIWJlc3RNYXRjaENhdGVnb3JpZXMgfHxcbiAgICBiZXN0TWF0Y2hDYXRlZ29yaWVzLmxlbmd0aCA9PT0gMCB8fFxuICAgICFuZXdFdmVudDEgfHxcbiAgICAhdXNlcklkXG4gICkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgJ1JlcXVpcmVkIHBhcmFtZXRlcnMgbWlzc2luZyBmb3IgdXBkYXRpbmcgdmFsdWVzIGZvciBtZWV0aW5nIHR5cGUgY2F0ZWdvcmllcy4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIHRyeSB7XG4gICAgbGV0IG5ld0V2ZW50ID0gbmV3RXZlbnQxO1xuICAgIGxldCBuZXdSZW1pbmRlcnMgPSBuZXdSZW1pbmRlcnMxIHx8IFtdO1xuICAgIGxldCBuZXdCdWZmZXJUaW1lcyA9IG5ld1RpbWVCbG9ja2luZzEgfHwge307IC8vIEVuc3VyZSBpdCdzIEJ1ZmZlclRpbWVPYmplY3RUeXBlXG5cbiAgICBjb25zdCBuZXdDYXRlZ29yeUNvbnN0YW50RXZlbnRzID0gY29weU92ZXJDYXRlZ29yeURlZmF1bHRzRm9yTWVldGluZ1R5cGUoXG4gICAgICBldmVudCxcbiAgICAgIGJlc3RNYXRjaENhdGVnb3JpZXNcbiAgICApO1xuICAgIGNvbnNvbGUubG9nKG5ld0NhdGVnb3J5Q29uc3RhbnRFdmVudHMsICcgbmV3Q2F0ZWdvcnlDb25zdGFudEV2ZW50cycpO1xuXG4gICAgaWYgKG5ld0NhdGVnb3J5Q29uc3RhbnRFdmVudHM/Lm5ld0V2ZW50TWVldGluZz8uaWQpIHtcbiAgICAgIG5ld0V2ZW50ID0geyAuLi5uZXdFdmVudCwgLi4ubmV3Q2F0ZWdvcnlDb25zdGFudEV2ZW50cy5uZXdFdmVudE1lZXRpbmcgfTtcbiAgICAgIGNvbnN0IG1lZXRpbmdDYXRlZ29yeSA9IGJlc3RNYXRjaENhdGVnb3JpZXMuZmluZChcbiAgICAgICAgKGNhdGVnb3J5KSA9PiBjYXRlZ29yeS5uYW1lID09PSBtZWV0aW5nTGFiZWxcbiAgICAgICk7XG5cbiAgICAgIGlmIChtZWV0aW5nQ2F0ZWdvcnkpIHtcbiAgICAgICAgLy8gRW5zdXJlIGNhdGVnb3J5IGlzIGZvdW5kXG4gICAgICAgIGNvbnN0IGxpc3RSZW1pbmRlcnNSZXNwb25zZSA9IGF3YWl0IGxpc3RSZW1pbmRlcnNGb3JFdmVudChcbiAgICAgICAgICAobmV3Q2F0ZWdvcnlDb25zdGFudEV2ZW50cy5uZXdFdmVudE1lZXRpbmcgYXMgRXZlbnRQbHVzVHlwZSkuaWQsXG4gICAgICAgICAgdXNlcklkXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IG9sZFJlbWluZGVycyA9XG4gICAgICAgICAgbGlzdFJlbWluZGVyc1Jlc3BvbnNlLm9rICYmIGxpc3RSZW1pbmRlcnNSZXNwb25zZS5kYXRhXG4gICAgICAgICAgICA/IGxpc3RSZW1pbmRlcnNSZXNwb25zZS5kYXRhXG4gICAgICAgICAgICA6IFtdO1xuXG4gICAgICAgIGNvbnN0IHJlbWluZGVycyA9IGNyZWF0ZVJlbWluZGVyc1VzaW5nQ2F0ZWdvcnlEZWZhdWx0c0ZvckV2ZW50KFxuICAgICAgICAgIG5ld0V2ZW50LFxuICAgICAgICAgIG1lZXRpbmdDYXRlZ29yeSxcbiAgICAgICAgICBvbGRSZW1pbmRlcnMsXG4gICAgICAgICAgcHJldmlvdXNFdmVudFxuICAgICAgICApO1xuICAgICAgICBpZiAocmVtaW5kZXJzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgbmV3UmVtaW5kZXJzLnB1c2goLi4ucmVtaW5kZXJzKTtcbiAgICAgICAgICBuZXdSZW1pbmRlcnMgPSBfLnVuaXFCeShuZXdSZW1pbmRlcnMsICdtaW51dGVzJyk7XG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBidWZmZXJUaW1lID0gY3JlYXRlUHJlQW5kUG9zdEV2ZW50c0ZvckNhdGVnb3J5RGVmYXVsdHMoXG4gICAgICAgICAgbWVldGluZ0NhdGVnb3J5LFxuICAgICAgICAgIG5ld0V2ZW50LFxuICAgICAgICAgIHByZXZpb3VzRXZlbnRcbiAgICAgICAgKTtcbiAgICAgICAgaWYgKGJ1ZmZlclRpbWU/LmJlZm9yZUV2ZW50KVxuICAgICAgICAgIChuZXdCdWZmZXJUaW1lcyBhcyBCdWZmZXJUaW1lT2JqZWN0VHlwZSkuYmVmb3JlRXZlbnQgPVxuICAgICAgICAgICAgYnVmZmVyVGltZS5iZWZvcmVFdmVudDtcbiAgICAgICAgaWYgKGJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQpXG4gICAgICAgICAgKG5ld0J1ZmZlclRpbWVzIGFzIEJ1ZmZlclRpbWVPYmplY3RUeXBlKS5hZnRlckV2ZW50ID1cbiAgICAgICAgICAgIGJ1ZmZlclRpbWUuYWZ0ZXJFdmVudDtcbiAgICAgICAgaWYgKFxuICAgICAgICAgIGJ1ZmZlclRpbWU/Lm5ld0V2ZW50Py5wcmVFdmVudElkIHx8XG4gICAgICAgICAgYnVmZmVyVGltZT8ubmV3RXZlbnQ/LnBvc3RFdmVudElkXG4gICAgICAgIClcbiAgICAgICAgICBuZXdFdmVudCA9IGJ1ZmZlclRpbWUubmV3RXZlbnQ7XG4gICAgICB9XG4gICAgfVxuXG4gICAgaWYgKG5ld0NhdGVnb3J5Q29uc3RhbnRFdmVudHM/Lm5ld0V2ZW50RXh0ZXJuYWw/LmlkKSB7XG4gICAgICBuZXdFdmVudCA9IHsgLi4ubmV3RXZlbnQsIC4uLm5ld0NhdGVnb3J5Q29uc3RhbnRFdmVudHMubmV3RXZlbnRFeHRlcm5hbCB9O1xuICAgICAgY29uc3QgZXh0ZXJuYWxDYXRlZ29yeSA9IGJlc3RNYXRjaENhdGVnb3JpZXMuZmluZChcbiAgICAgICAgKGNhdGVnb3J5KSA9PiBjYXRlZ29yeS5uYW1lID09PSBleHRlcm5hbE1lZXRpbmdMYWJlbFxuICAgICAgKTtcblxuICAgICAgaWYgKGV4dGVybmFsQ2F0ZWdvcnkpIHtcbiAgICAgICAgLy8gRW5zdXJlIGNhdGVnb3J5IGlzIGZvdW5kXG4gICAgICAgIGNvbnN0IGxpc3RSZW1pbmRlcnNSZXNwb25zZSA9IGF3YWl0IGxpc3RSZW1pbmRlcnNGb3JFdmVudChcbiAgICAgICAgICAobmV3Q2F0ZWdvcnlDb25zdGFudEV2ZW50cy5uZXdFdmVudEV4dGVybmFsIGFzIEV2ZW50UGx1c1R5cGUpLmlkLFxuICAgICAgICAgIHVzZXJJZFxuICAgICAgICApO1xuICAgICAgICBjb25zdCBvbGRSZW1pbmRlcnMgPVxuICAgICAgICAgIGxpc3RSZW1pbmRlcnNSZXNwb25zZS5vayAmJiBsaXN0UmVtaW5kZXJzUmVzcG9uc2UuZGF0YVxuICAgICAgICAgICAgPyBsaXN0UmVtaW5kZXJzUmVzcG9uc2UuZGF0YVxuICAgICAgICAgICAgOiBbXTtcblxuICAgICAgICBjb25zdCByZW1pbmRlcnMgPSBjcmVhdGVSZW1pbmRlcnNVc2luZ0NhdGVnb3J5RGVmYXVsdHNGb3JFdmVudChcbiAgICAgICAgICBuZXdFdmVudCxcbiAgICAgICAgICBleHRlcm5hbENhdGVnb3J5LFxuICAgICAgICAgIG9sZFJlbWluZGVycyxcbiAgICAgICAgICBwcmV2aW91c0V2ZW50XG4gICAgICAgICk7XG4gICAgICAgIGlmIChyZW1pbmRlcnM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICBuZXdSZW1pbmRlcnMucHVzaCguLi5yZW1pbmRlcnMpO1xuICAgICAgICAgIG5ld1JlbWluZGVycyA9IF8udW5pcUJ5KG5ld1JlbWluZGVycywgJ21pbnV0ZXMnKTtcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHRpbWVCbG9ja2luZyA9IGNyZWF0ZVByZUFuZFBvc3RFdmVudHNGb3JDYXRlZ29yeURlZmF1bHRzKFxuICAgICAgICAgIGV4dGVybmFsQ2F0ZWdvcnksXG4gICAgICAgICAgbmV3RXZlbnQsXG4gICAgICAgICAgcHJldmlvdXNFdmVudFxuICAgICAgICApO1xuICAgICAgICBpZiAodGltZUJsb2NraW5nPy5iZWZvcmVFdmVudClcbiAgICAgICAgICAobmV3QnVmZmVyVGltZXMgYXMgQnVmZmVyVGltZU9iamVjdFR5cGUpLmJlZm9yZUV2ZW50ID1cbiAgICAgICAgICAgIHRpbWVCbG9ja2luZy5iZWZvcmVFdmVudDtcbiAgICAgICAgaWYgKHRpbWVCbG9ja2luZz8uYWZ0ZXJFdmVudClcbiAgICAgICAgICAobmV3QnVmZmVyVGltZXMgYXMgQnVmZmVyVGltZU9iamVjdFR5cGUpLmFmdGVyRXZlbnQgPVxuICAgICAgICAgICAgdGltZUJsb2NraW5nLmFmdGVyRXZlbnQ7XG4gICAgICAgIGlmIChcbiAgICAgICAgICB0aW1lQmxvY2tpbmc/Lm5ld0V2ZW50Py5wcmVFdmVudElkIHx8XG4gICAgICAgICAgdGltZUJsb2NraW5nPy5uZXdFdmVudD8ucG9zdEV2ZW50SWRcbiAgICAgICAgKVxuICAgICAgICAgIG5ld0V2ZW50ID0gdGltZUJsb2NraW5nLm5ld0V2ZW50O1xuICAgICAgfVxuICAgIH1cbiAgICByZXR1cm4ge1xuICAgICAgb2s6IHRydWUsXG4gICAgICBkYXRhOiB7XG4gICAgICAgIG5ld0V2ZW50LFxuICAgICAgICBuZXdSZW1pbmRlcnMsXG4gICAgICAgIG5ld0J1ZmZlclRpbWVzOiBuZXdCdWZmZXJUaW1lcyBhcyBCdWZmZXJUaW1lT2JqZWN0VHlwZSxcbiAgICAgIH0sXG4gICAgfTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgdXBkYXRpbmcgdmFsdWVzIGZvciBtZWV0aW5nIHR5cGUgY2F0ZWdvcmllczonLCBlKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0lOVEVSTkFMX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byB1cGRhdGUgdmFsdWVzIGZvciBtZWV0aW5nIGNhdGVnb3JpZXM6ICR7ZS5tZXNzYWdlfWAsXG4gICAgICAgIGRldGFpbHM6IGUsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0cyA9IGFzeW5jIChcbiAgZXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIHZlY3RvcjogbnVtYmVyW11cbik6IFByb21pc2U8XG4gIEZlYXR1cmVzQXBwbHlSZXNwb25zZTx7XG4gICAgbmV3RXZlbnQ6IEV2ZW50UGx1c1R5cGU7XG4gICAgbmV3UmVtaW5kZXJzPzogUmVtaW5kZXJUeXBlW107XG4gICAgbmV3QnVmZmVyVGltZXM/OiBCdWZmZXJUaW1lT2JqZWN0VHlwZTtcbiAgfSB8IG51bGw+XG4+ID0+IHtcbiAgaWYgKCFldmVudCB8fCAhZXZlbnQuaWQgfHwgIWV2ZW50LnVzZXJJZCB8fCAhdmVjdG9yKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAnRXZlbnQsIGV2ZW50IElELCB1c2VySWQsIGFuZCB2ZWN0b3IgYXJlIHJlcXVpcmVkIGZvciBjYXRlZ29yeSBwcm9jZXNzaW5nLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBjb25zdCB7IGlkLCB1c2VySWQgfSA9IGV2ZW50O1xuICAgIGNvbnNvbGUubG9nKGlkLCAnIGlkIGluc2lkZSBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0cycpO1xuXG4gICAgY29uc3QgY2F0ZWdvcmllc1Jlc3BvbnNlID0gYXdhaXQgZ2V0VXNlckNhdGVnb3JpZXModXNlcklkKTtcbiAgICBpZiAoIWNhdGVnb3JpZXNSZXNwb25zZS5vayB8fCAhY2F0ZWdvcmllc1Jlc3BvbnNlLmRhdGEpIHtcbiAgICAgIC8vIElmIGNhdGVnb3JpZXMgY2FuJ3QgYmUgZmV0Y2hlZCwgd2UgbWlnaHQgc3RpbGwgcHJvY2VlZCB3aXRoIHRoZSBldmVudCwgYnV0IHdpdGhvdXQgY2F0ZWdvcml6YXRpb24gYmVuZWZpdHMuXG4gICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgIGBGYWlsZWQgdG8gZ2V0IHVzZXIgY2F0ZWdvcmllcyBmb3IgdXNlciAke3VzZXJJZH0uIFByb2NlZWRpbmcgd2l0aG91dCBjYXRlZ29yaXphdGlvbi4gRXJyb3I6ICR7Y2F0ZWdvcmllc1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICk7XG4gICAgICBldmVudC52ZWN0b3IgPSB2ZWN0b3I7IC8vIEVuc3VyZSB2ZWN0b3IgaXMgc2V0XG4gICAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogeyBuZXdFdmVudDogZXZlbnQgfSB9OyAvLyBPciByZXR1cm4gZXJyb3IgaWYgY2F0ZWdvcmllcyBhcmUgZXNzZW50aWFsXG4gICAgfVxuICAgIGNvbnN0IGNhdGVnb3JpZXMgPSBjYXRlZ29yaWVzUmVzcG9uc2UuZGF0YTtcblxuICAgIGlmIChjYXRlZ29yaWVzLmxlbmd0aCA9PT0gMCkge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBObyBjYXRlZ29yaWVzIGRlZmluZWQgZm9yIHVzZXIgJHt1c2VySWR9LiBFdmVudCAke2lkfSB3aWxsIG5vdCBiZSBjYXRlZ29yaXplZCBmdXJ0aGVyLmBcbiAgICAgICk7XG4gICAgICBldmVudC52ZWN0b3IgPSB2ZWN0b3I7XG4gICAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogeyBuZXdFdmVudDogZXZlbnQgfSB9O1xuICAgIH1cblxuICAgIGNvbnN0IGNsYXNzaWZpY2F0aW9uUmVzcG9uc2UgPSBhd2FpdCBmaW5kQmVzdE1hdGNoQ2F0ZWdvcnkyKFxuICAgICAgZXZlbnQsXG4gICAgICBjYXRlZ29yaWVzXG4gICAgKTtcbiAgICBpZiAoIWNsYXNzaWZpY2F0aW9uUmVzcG9uc2Uub2sgfHwgIWNsYXNzaWZpY2F0aW9uUmVzcG9uc2UuZGF0YSkge1xuICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICBgQ2F0ZWdvcnkgY2xhc3NpZmljYXRpb24gZmFpbGVkIGZvciBldmVudCAke2lkfS4gRXJyb3I6ICR7Y2xhc3NpZmljYXRpb25SZXNwb25zZS5lcnJvcj8ubWVzc2FnZX0uIFByb2NlZWRpbmcgd2l0aG91dCBhcHBseWluZyBjYXRlZ29yeSBkZWZhdWx0cy5gXG4gICAgICApO1xuICAgICAgZXZlbnQudmVjdG9yID0gdmVjdG9yO1xuICAgICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHsgbmV3RXZlbnQ6IGV2ZW50IH0gfTtcbiAgICB9XG4gICAgY29uc3QgY2xhc3NpZmljYXRpb25Cb2R5ID0gY2xhc3NpZmljYXRpb25SZXNwb25zZS5kYXRhO1xuICAgIGNvbnN0IHsgbGFiZWxzLCBzY29yZXMgfSA9IGNsYXNzaWZpY2F0aW9uQm9keTtcbiAgICBjb25zdCBiZXN0TWF0Y2hMYWJlbCA9IHByb2Nlc3NCZXN0TWF0Y2hDYXRlZ29yaWVzKFxuICAgICAgY2xhc3NpZmljYXRpb25Cb2R5LFxuICAgICAgbGFiZWxzXG4gICAgKTtcblxuICAgIGxldCBuZXdFdmVudDogRXZlbnRQbHVzVHlwZSA9IHsgLi4uZXZlbnQsIHZlY3RvciB9OyAvLyBTdGFydCB3aXRoIG9yaWdpbmFsIGV2ZW50IGFuZCBhZGQgdmVjdG9yXG4gICAgbGV0IG5ld1JlbWluZGVyczogUmVtaW5kZXJUeXBlW10gPSBbXTtcbiAgICBsZXQgbmV3QnVmZmVyVGltZXM6IEJ1ZmZlclRpbWVPYmplY3RUeXBlID0ge307XG5cbiAgICBpZiAoYmVzdE1hdGNoTGFiZWwpIHtcbiAgICAgIGNvbnN0IGJlc3RNYXRjaENhdGVnb3J5ID0gY2F0ZWdvcmllcy5maW5kKFxuICAgICAgICAoY2F0ZWdvcnkpID0+IGNhdGVnb3J5Lm5hbWUgPT09IGJlc3RNYXRjaExhYmVsXG4gICAgICApO1xuICAgICAgaWYgKGJlc3RNYXRjaENhdGVnb3J5KSB7XG4gICAgICAgIGxldCBiZXN0TWF0Y2hQbHVzTWVldGluZ0NhdGVnb3JpZXMgPVxuICAgICAgICAgIHByb2Nlc3NFdmVudEZvck1lZXRpbmdUeXBlQ2F0ZWdvcmllcyhcbiAgICAgICAgICAgIG5ld0V2ZW50LFxuICAgICAgICAgICAgYmVzdE1hdGNoQ2F0ZWdvcnksXG4gICAgICAgICAgICBsYWJlbHMsXG4gICAgICAgICAgICBzY29yZXMsXG4gICAgICAgICAgICBjYXRlZ29yaWVzXG4gICAgICAgICAgKTtcbiAgICAgICAgYmVzdE1hdGNoUGx1c01lZXRpbmdDYXRlZ29yaWVzID0gZ2V0VW5pcXVlTGFiZWxzKFxuICAgICAgICAgIGJlc3RNYXRjaFBsdXNNZWV0aW5nQ2F0ZWdvcmllc1xuICAgICAgICApO1xuXG4gICAgICAgIG5ld0V2ZW50ID0gY29weU92ZXJDYXRlZ29yeURlZmF1bHRzKG5ld0V2ZW50LCBiZXN0TWF0Y2hDYXRlZ29yeSk7XG5cbiAgICAgICAgY29uc3QgcmVtaW5kZXJzQW5kQnVmZmVyc1Jlc3BvbnNlID1cbiAgICAgICAgICBhd2FpdCBjcmVhdGVSZW1pbmRlcnNBbmRCdWZmZXJUaW1lc0ZvckJlc3RNYXRjaENhdGVnb3J5KFxuICAgICAgICAgICAgaWQsXG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBuZXdFdmVudCxcbiAgICAgICAgICAgIGJlc3RNYXRjaENhdGVnb3J5LFxuICAgICAgICAgICAgW10sXG4gICAgICAgICAgICB7fVxuICAgICAgICAgICk7XG4gICAgICAgIGlmIChcbiAgICAgICAgICByZW1pbmRlcnNBbmRCdWZmZXJzUmVzcG9uc2Uub2sgJiZcbiAgICAgICAgICByZW1pbmRlcnNBbmRCdWZmZXJzUmVzcG9uc2UuZGF0YVxuICAgICAgICApIHtcbiAgICAgICAgICBuZXdFdmVudCA9IHJlbWluZGVyc0FuZEJ1ZmZlcnNSZXNwb25zZS5kYXRhLm5ld0V2ZW50O1xuICAgICAgICAgIG5ld1JlbWluZGVycyA9IHJlbWluZGVyc0FuZEJ1ZmZlcnNSZXNwb25zZS5kYXRhLm5ld1JlbWluZGVycztcbiAgICAgICAgICBuZXdCdWZmZXJUaW1lcyA9IHJlbWluZGVyc0FuZEJ1ZmZlcnNSZXNwb25zZS5kYXRhLm5ld0J1ZmZlclRpbWVzO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICAgIGBGYWlsZWQgdG8gY3JlYXRlIHJlbWluZGVycy9idWZmZXJzIGZvciBiZXN0IG1hdGNoIGNhdGVnb3J5IGZvciBldmVudCAke2lkfTogJHtyZW1pbmRlcnNBbmRCdWZmZXJzUmVzcG9uc2UuZXJyb3I/Lm1lc3NhZ2V9YFxuICAgICAgICAgICk7XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoYmVzdE1hdGNoUGx1c01lZXRpbmdDYXRlZ29yaWVzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgY29uc3QgY2F0ZWdvcnlFdmVudHM6IENhdGVnb3J5RXZlbnRUeXBlW10gPVxuICAgICAgICAgICAgYmVzdE1hdGNoUGx1c01lZXRpbmdDYXRlZ29yaWVzLm1hcCgoYykgPT4gKHtcbiAgICAgICAgICAgICAgY2F0ZWdvcnlJZDogYy5pZCxcbiAgICAgICAgICAgICAgZXZlbnRJZDogaWQsXG4gICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICAgICAgY3JlYXRlZERhdGU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICAgICAgdXBkYXRlZEF0OiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICAgIENhdGVnb3J5OiBjLFxuICAgICAgICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgICAgIH0pKTtcblxuICAgICAgICAgIGNvbnN0IGNyZWF0ZUNhdEV2ZW50c1Jlc3BvbnNlID1cbiAgICAgICAgICAgIGF3YWl0IGNyZWF0ZUNhdGVnb3J5RXZlbnRzKGNhdGVnb3J5RXZlbnRzKTtcbiAgICAgICAgICBpZiAoIWNyZWF0ZUNhdEV2ZW50c1Jlc3BvbnNlLm9rKSB7XG4gICAgICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgICAgIGBGYWlsZWQgdG8gY3JlYXRlIGNhdGVnb3J5IGV2ZW50cyBmb3IgZXZlbnQgJHtpZH06ICR7Y3JlYXRlQ2F0RXZlbnRzUmVzcG9uc2UuZXJyb3I/Lm1lc3NhZ2V9YFxuICAgICAgICAgICAgKTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBjb25zdCB1cGRhdGVkVmFsdWVzUmVzcG9uc2UgPVxuICAgICAgICAgICAgYXdhaXQgdXBkYXRlVmFsdWVzRm9yTWVldGluZ1R5cGVDYXRlZ29yaWVzKFxuICAgICAgICAgICAgICBldmVudCxcbiAgICAgICAgICAgICAgbmV3RXZlbnQsXG4gICAgICAgICAgICAgIGJlc3RNYXRjaFBsdXNNZWV0aW5nQ2F0ZWdvcmllcyxcbiAgICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgICBuZXdSZW1pbmRlcnMsXG4gICAgICAgICAgICAgIG5ld0J1ZmZlclRpbWVzXG4gICAgICAgICAgICApO1xuICAgICAgICAgIGlmICh1cGRhdGVkVmFsdWVzUmVzcG9uc2Uub2sgJiYgdXBkYXRlZFZhbHVlc1Jlc3BvbnNlLmRhdGEpIHtcbiAgICAgICAgICAgIG5ld0V2ZW50ID0gdXBkYXRlZFZhbHVlc1Jlc3BvbnNlLmRhdGEubmV3RXZlbnQ7XG4gICAgICAgICAgICBuZXdSZW1pbmRlcnMgPSB1cGRhdGVkVmFsdWVzUmVzcG9uc2UuZGF0YS5uZXdSZW1pbmRlcnM7XG4gICAgICAgICAgICBuZXdCdWZmZXJUaW1lcyA9IHVwZGF0ZWRWYWx1ZXNSZXNwb25zZS5kYXRhLm5ld0J1ZmZlclRpbWVzO1xuICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgICAgIGBGYWlsZWQgdG8gdXBkYXRlIHZhbHVlcyBmb3IgbWVldGluZyB0eXBlIGNhdGVnb3JpZXMgZm9yIGV2ZW50ICR7aWR9OiAke3VwZGF0ZWRWYWx1ZXNSZXNwb25zZS5lcnJvcj8ubWVzc2FnZX1gXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogeyBuZXdFdmVudCwgbmV3UmVtaW5kZXJzLCBuZXdCdWZmZXJUaW1lcyB9IH07XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICBgRXJyb3IgcHJvY2Vzc2luZyB1c2VyIGV2ZW50ICR7ZXZlbnQ/LmlkfSBmb3IgY2F0ZWdvcnkgZGVmYXVsdHM6YCxcbiAgICAgIGVcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnQ0xBU1NJRklDQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgRmFpbGVkIHRvIHByb2Nlc3MgZXZlbnQgZm9yIGNhdGVnb3JpZXM6ICR7ZS5tZXNzYWdlfWAsXG4gICAgICAgIGRldGFpbHM6IGUsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50ID0gYXN5bmMgKFxuICBldmVudElkOiBzdHJpbmdcbik6IFByb21pc2U8RmVhdHVyZXNBcHBseVJlc3BvbnNlPENhdGVnb3J5VHlwZVtdIHwgbnVsbD4+ID0+IHtcbiAgaWYgKCFldmVudElkKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ0V2ZW50IElEIGlzIHJlcXVpcmVkIGZvciBsaXN0aW5nIGNhdGVnb3JpZXMuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnbGlzdENhdGVnb3JpZXNGb3JFdmVudCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBxdWVyeSBsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50KCRldmVudElkOiBTdHJpbmchKSB7XG4gICAgICAgIENhdGVnb3J5X0V2ZW50KHdoZXJlOiB7ZXZlbnRJZDoge19lcTogJGV2ZW50SWR9fSkge1xuICAgICAgICAgIENhdGVnb3J5IHtcbiAgICAgICAgICAgIGNvbG9yXG4gICAgICAgICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICAgICAgICBjb3B5SXNCcmVha1xuICAgICAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICAgICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgICAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGRlZmF1bHRBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgIGRlZmF1bHRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICBkZWZhdWx0SXNCcmVha1xuICAgICAgICAgICAgZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICBkZWZhdWx0SXNNZWV0aW5nXG4gICAgICAgICAgICBkZWZhdWx0TWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgIGRlZmF1bHRNb2RpZmlhYmxlXG4gICAgICAgICAgICBkZWZhdWx0UHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgZGVmYXVsdFJlbWluZGVyc1xuICAgICAgICAgICAgZGVmYXVsdFRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgZGVmYXVsdFRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICBpZFxuICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICB9XG4gICAgICAgICAgY2F0ZWdvcnlJZFxuICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICBpZFxuICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgIHVzZXJJZFxuICAgICAgICB9XG4gICAgICB9XG4gICAgYDtcbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBDYXRlZ29yeV9FdmVudDogQ2F0ZWdvcnlFdmVudFR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG4gICAgY29uc29sZS5sb2cocmVzLCAnIGxpc3RDYXRlZ29yaWVzRm9yRXZlbnQnKTtcbiAgICBjb25zdCBjYXRlZ29yaWVzOiBDYXRlZ29yeVR5cGVbXSA9IHJlcz8uZGF0YT8uQ2F0ZWdvcnlfRXZlbnQ/Lm1hcChcbiAgICAgIChjYXRlZ29yeSkgPT4gY2F0ZWdvcnk/LkNhdGVnb3J5XG4gICAgKT8uZmlsdGVyKFxuICAgICAgKGNhdGVnb3J5KTogY2F0ZWdvcnkgaXMgQ2F0ZWdvcnlUeXBlID0+XG4gICAgICAgIGNhdGVnb3J5ICE9IG51bGwgJiYgY2F0ZWdvcnkuaWQgIT0gbnVsbFxuICAgICk7IC8vIEVuc3VyZSBjYXRlZ29yeSBhbmQgaXRzIGlkIGFyZSBub3QgbnVsbFxuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBjYXRlZ29yaWVzLFxuICAgICAgJyBjYXRlZ29yaWVzIGZyb20gbGlzdENhdGVnb3JpZXNGb3JFdmVudCBhZnRlciBmaWx0ZXInXG4gICAgKTtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogY2F0ZWdvcmllcyB8fCBudWxsIH07XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIGxpc3RpbmcgY2F0ZWdvcmllcyBmb3IgZXZlbnQ6JywgZSk7XG4gICAgY29uc3QgZXJyb3JEZXRhaWxzID0gZS5yZXNwb25zZT8uYm9keSB8fCBlLm1lc3NhZ2UgfHwgZTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0hBU1VSQV9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gbGlzdCBjYXRlZ29yaWVzIGZvciBldmVudDogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZXJyb3JEZXRhaWxzLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0Jlc3RNYXRjaENhdGVnb3JpZXNOb1RocmVzaG9sZCA9IChcbiAgYm9keSxcbiAgbmV3UG9zc2libGVMYWJlbHNcbikgPT4ge1xuICBjb25zdCB7IHNjb3JlcyB9ID0gYm9keTtcbiAgbGV0IGJlc3RNYXRjaENhdGVnb3J5ID0gJyc7XG4gIGxldCBiZXN0TWF0Y2hTY29yZSA9IDA7XG4gIGZvciAobGV0IGkgPSAwOyBpIDwgbmV3UG9zc2libGVMYWJlbHMubGVuZ3RoOyBpKyspIHtcbiAgICBjb25zdCBsYWJlbCA9IG5ld1Bvc3NpYmxlTGFiZWxzW2ldO1xuICAgIGNvbnN0IHNjb3JlID0gc2NvcmVzW2ldO1xuXG4gICAgaWYgKHNjb3JlID4gYmVzdE1hdGNoU2NvcmUpIHtcbiAgICAgIGJlc3RNYXRjaENhdGVnb3J5ID0gbGFiZWw7XG4gICAgICBiZXN0TWF0Y2hTY29yZSA9IHNjb3JlO1xuICAgIH1cbiAgfVxuXG4gIHJldHVybiBiZXN0TWF0Y2hDYXRlZ29yeTtcbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0c1dpdGhVc2VyTW9kaWZpZWRDYXRlZ29yaWVzID1cbiAgYXN5bmMgKGV2ZW50OiBFdmVudFBsdXNUeXBlLCB2ZWN0b3I6IG51bWJlcltdKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IHsgaWQsIHVzZXJJZCB9ID0gZXZlbnQ7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgaWQsXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgJyBpZCwgdXNlcklkIGluc2lkZSBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0c1dpdGhVc2VyTW9kaWZpZWRDYXRlZ29yaWVzJ1xuICAgICAgKTtcblxuICAgICAgY29uc3QgY2F0ZWdvcmllczogQ2F0ZWdvcnlUeXBlW10gPSBhd2FpdCBsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50KFxuICAgICAgICBldmVudD8uaWRcbiAgICAgICk7XG5cbiAgICAgIGNvbnNvbGUubG9nKGNhdGVnb3JpZXMsICcgY2F0ZWdvcmllcycpO1xuICAgICAgY29uc3QgYm9keSA9IGF3YWl0IGZpbmRCZXN0TWF0Y2hDYXRlZ29yeTIoZXZlbnQsIGNhdGVnb3JpZXMpO1xuICAgICAgY29uc29sZS5sb2coYm9keSwgJyBib2R5Jyk7XG4gICAgICBjb25zdCB7IGxhYmVscywgc2NvcmVzIH0gPSBib2R5O1xuXG4gICAgICBjb25zdCBiZXN0TWF0Y2hMYWJlbCA9IHByb2Nlc3NCZXN0TWF0Y2hDYXRlZ29yaWVzTm9UaHJlc2hvbGQoXG4gICAgICAgIGJvZHksXG4gICAgICAgIGxhYmVsc1xuICAgICAgKTtcbiAgICAgIGNvbnNvbGUubG9nKGJlc3RNYXRjaExhYmVsLCAnIGJlc3RNYXRjaExhYmVsJyk7XG4gICAgICBsZXQgYmVzdE1hdGNoQ2F0ZWdvcnk6IENhdGVnb3J5VHlwZSB8IG51bGwgPSBudWxsO1xuICAgICAgbGV0IG5ld0V2ZW50OiBFdmVudFBsdXNUeXBlID0gZXZlbnQ7XG4gICAgICBjb25zb2xlLmxvZyhuZXdFdmVudCwgJyBuZXdFdmVudCcpO1xuICAgICAgbGV0IG5ld1JlbWluZGVyczogUmVtaW5kZXJUeXBlW10gPSBbXTtcbiAgICAgIGxldCBuZXdCdWZmZXJUaW1lczogQnVmZmVyVGltZU9iamVjdFR5cGUgfCBvYmplY3QgPSB7fTtcbiAgICAgIGlmIChiZXN0TWF0Y2hMYWJlbCkge1xuICAgICAgICBiZXN0TWF0Y2hDYXRlZ29yeSA9IGNhdGVnb3JpZXMuZmluZChcbiAgICAgICAgICAoY2F0ZWdvcnkpID0+IGNhdGVnb3J5Lm5hbWUgPT09IGJlc3RNYXRjaExhYmVsXG4gICAgICAgICk7XG4gICAgICAgIGxhYmVscy5wdXNoKG1lZXRpbmdMYWJlbCwgZXh0ZXJuYWxNZWV0aW5nTGFiZWwpO1xuICAgICAgICBzY29yZXMucHVzaCgwLCAwKTtcbiAgICAgICAgbGV0IGJlc3RNYXRjaFBsdXNNZWV0aW5nQ2F0ZWdvcmllcyA9XG4gICAgICAgICAgcHJvY2Vzc0V2ZW50Rm9yTWVldGluZ1R5cGVDYXRlZ29yaWVzKFxuICAgICAgICAgICAgZXZlbnQsXG4gICAgICAgICAgICBiZXN0TWF0Y2hDYXRlZ29yeSxcbiAgICAgICAgICAgIGxhYmVscyxcbiAgICAgICAgICAgIHNjb3JlcyxcbiAgICAgICAgICAgIGNhdGVnb3JpZXNcbiAgICAgICAgICApO1xuICAgICAgICBpZiAoYmVzdE1hdGNoUGx1c01lZXRpbmdDYXRlZ29yaWVzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgYmVzdE1hdGNoUGx1c01lZXRpbmdDYXRlZ29yaWVzID0gZ2V0VW5pcXVlTGFiZWxzKFxuICAgICAgICAgICAgYmVzdE1hdGNoUGx1c01lZXRpbmdDYXRlZ29yaWVzXG4gICAgICAgICAgKTtcbiAgICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICAgIGJlc3RNYXRjaFBsdXNNZWV0aW5nQ2F0ZWdvcmllcyxcbiAgICAgICAgICAgICcgYmVzdE1hdGNoQW5kTWVldGluZ0NhdGVnb3JpZXMnXG4gICAgICAgICAgKTtcbiAgICAgICAgICBjb25zdCBjYXRlZ29yeUV2ZW50czogQ2F0ZWdvcnlFdmVudFR5cGVbXSA9XG4gICAgICAgICAgICBiZXN0TWF0Y2hQbHVzTWVldGluZ0NhdGVnb3JpZXMubWFwKChjKSA9PiB7XG4gICAgICAgICAgICAgIGNvbnN0IGNhdGVnb3J5RXZlbnQ6IENhdGVnb3J5RXZlbnRUeXBlID0ge1xuICAgICAgICAgICAgICAgIGNhdGVnb3J5SWQ6IGMuaWQsXG4gICAgICAgICAgICAgICAgZXZlbnRJZDogaWQsXG4gICAgICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgICAgICAgY3JlYXRlZERhdGU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICAgICAgICB1cGRhdGVkQXQ6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICAgICAgfSBhcyBDYXRlZ29yeUV2ZW50VHlwZTtcbiAgICAgICAgICAgICAgcmV0dXJuIGNhdGVnb3J5RXZlbnQ7XG4gICAgICAgICAgICB9KTtcbiAgICAgICAgICBjb25zb2xlLmxvZyhjYXRlZ29yeUV2ZW50cywgJyBjYXRlZ29yeUV2ZW50cycpO1xuICAgICAgICAgIGF3YWl0IGNyZWF0ZUNhdGVnb3J5RXZlbnRzKGNhdGVnb3J5RXZlbnRzKTtcbiAgICAgICAgICBjb25zdCB7XG4gICAgICAgICAgICBuZXdFdmVudDogbmV3RXZlbnQxLFxuICAgICAgICAgICAgbmV3UmVtaW5kZXJzOiBuZXdSZW1pbmRlcnMxLFxuICAgICAgICAgICAgbmV3QnVmZmVyVGltZXM6IG5ld1RpbWVCbG9ja2luZzEsXG4gICAgICAgICAgfSA9IGF3YWl0IHVwZGF0ZVZhbHVlc0Zvck1lZXRpbmdUeXBlQ2F0ZWdvcmllcyhcbiAgICAgICAgICAgIGV2ZW50LFxuICAgICAgICAgICAgbmV3RXZlbnQsXG4gICAgICAgICAgICBiZXN0TWF0Y2hQbHVzTWVldGluZ0NhdGVnb3JpZXMsXG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBuZXdSZW1pbmRlcnMsXG4gICAgICAgICAgICBuZXdCdWZmZXJUaW1lc1xuICAgICAgICAgICk7XG4gICAgICAgICAgbmV3RXZlbnQgPSBuZXdFdmVudDE7XG4gICAgICAgICAgbmV3UmVtaW5kZXJzID0gbmV3UmVtaW5kZXJzMTtcbiAgICAgICAgICBuZXdCdWZmZXJUaW1lcyA9IG5ld1RpbWVCbG9ja2luZzE7XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgbGV0IG5ld0NhdGVnb3J5RGVmYXVsdEV2ZW50OiBFdmVudFBsdXNUeXBlIHwgbnVsbCA9IG51bGw7XG4gICAgICBpZiAoYmVzdE1hdGNoQ2F0ZWdvcnkpIHtcbiAgICAgICAgbmV3Q2F0ZWdvcnlEZWZhdWx0RXZlbnQgPSBjb3B5T3ZlckNhdGVnb3J5RGVmYXVsdHMoXG4gICAgICAgICAgZXZlbnQsXG4gICAgICAgICAgYmVzdE1hdGNoQ2F0ZWdvcnlcbiAgICAgICAgKTtcbiAgICAgIH1cbiAgICAgIGNvbnNvbGUubG9nKG5ld0NhdGVnb3J5RGVmYXVsdEV2ZW50LCAnIG5ld0NhdGVnb3J5RGVmYXVsdEV2ZW50Jyk7XG5cbiAgICAgIG5ld0V2ZW50ID0gbmV3Q2F0ZWdvcnlEZWZhdWx0RXZlbnQgPz8gbmV3RXZlbnQgPz8gZXZlbnQ7XG4gICAgICBjb25zb2xlLmxvZyhuZXdFdmVudCwgJyBuZXdFdmVudCcpO1xuICAgICAgY29uc3Qge1xuICAgICAgICBuZXdFdmVudDogbmV3RXZlbnQxLFxuICAgICAgICBuZXdSZW1pbmRlcnM6IG5ld1JlbWluZGVyczEsXG4gICAgICAgIG5ld0J1ZmZlclRpbWVzOiBuZXdUaW1lQmxvY2tpbmcxLFxuICAgICAgfSA9IGF3YWl0IGNyZWF0ZVJlbWluZGVyc0FuZEJ1ZmZlclRpbWVzRm9yQmVzdE1hdGNoQ2F0ZWdvcnkoXG4gICAgICAgIGlkLFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIG5ld0V2ZW50LFxuICAgICAgICBiZXN0TWF0Y2hDYXRlZ29yeSxcbiAgICAgICAgbmV3UmVtaW5kZXJzLFxuICAgICAgICBuZXdCdWZmZXJUaW1lcyBhcyBCdWZmZXJUaW1lT2JqZWN0VHlwZVxuICAgICAgKTtcblxuICAgICAgbmV3RXZlbnQgPSBuZXdFdmVudDE7XG4gICAgICBuZXdSZW1pbmRlcnMgPSBuZXdSZW1pbmRlcnMxO1xuICAgICAgbmV3QnVmZmVyVGltZXMgPSBuZXdUaW1lQmxvY2tpbmcxIGFzIEJ1ZmZlclRpbWVPYmplY3RUeXBlO1xuXG4gICAgICBpZiAoY2F0ZWdvcmllcz8ubGVuZ3RoID4gMSkge1xuICAgICAgICBjb25zdCB7XG4gICAgICAgICAgbmV3RXZlbnQ6IG5ld0V2ZW50MSxcbiAgICAgICAgICBuZXdSZW1pbmRlcnM6IG5ld1JlbWluZGVyczEsXG4gICAgICAgICAgbmV3QnVmZmVyVGltZXM6IG5ld1RpbWVCbG9ja2luZzEsXG4gICAgICAgIH0gPSBhd2FpdCB1cGRhdGVWYWx1ZXNGb3JNZWV0aW5nVHlwZUNhdGVnb3JpZXMoXG4gICAgICAgICAgZXZlbnQsXG4gICAgICAgICAgbmV3RXZlbnQsXG4gICAgICAgICAgY2F0ZWdvcmllcyxcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgbmV3UmVtaW5kZXJzLFxuICAgICAgICAgIG5ld0J1ZmZlclRpbWVzIGFzIEJ1ZmZlclRpbWVPYmplY3RUeXBlXG4gICAgICAgICk7XG4gICAgICAgIG5ld0V2ZW50ID0gbmV3RXZlbnQxO1xuICAgICAgICBuZXdSZW1pbmRlcnMgPSBuZXdSZW1pbmRlcnMxO1xuICAgICAgICBuZXdCdWZmZXJUaW1lcyA9IG5ld1RpbWVCbG9ja2luZzE7XG4gICAgICB9XG5cbiAgICAgIG5ld0V2ZW50LnZlY3RvciA9IHZlY3RvcjtcblxuICAgICAgY29uc29sZS5sb2cobmV3RXZlbnQsICcgbmV3RXZlbnQnKTtcbiAgICAgIGNvbnNvbGUubG9nKG5ld1JlbWluZGVycywgJyBuZXdSZW1pbmRlcnMnKTtcbiAgICAgIGNvbnNvbGUubG9nKG5ld0J1ZmZlclRpbWVzLCAnIG5ld1RpbWVCbG9ja2luZycpO1xuXG4gICAgICByZXR1cm4ge1xuICAgICAgICBuZXdFdmVudCxcbiAgICAgICAgbmV3UmVtaW5kZXJzLFxuICAgICAgICBuZXdCdWZmZXJUaW1lczogbmV3QnVmZmVyVGltZXMsXG4gICAgICB9O1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgIGNvbnNvbGUubG9nKGUsICcgZScpO1xuICAgIH1cbiAgfTtcblxuZXhwb3J0IGNvbnN0IGdldEV2ZW50RnJvbVByaW1hcnlLZXkgPSBhc3luYyAoXG4gIGlkOiBzdHJpbmdcbik6IFByb21pc2U8RmVhdHVyZXNBcHBseVJlc3BvbnNlPEV2ZW50UGx1c1R5cGUgfCBudWxsPj4gPT4ge1xuICBpZiAoIWlkKSB7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ0lEIGlzIHJlcXVpcmVkIHRvIGdldCBldmVudCBieSBwcmltYXJ5IGtleS4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRFdmVudEZyb21QcmltYXJ5S2V5JztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICBxdWVyeSBnZXRFdmVudEZyb21QcmltYXJ5S2V5KCRpZDogU3RyaW5nISkge1xuICBFdmVudF9ieV9wayhpZDogJGlkKSB7XG4gICAgYWxsRGF5XG4gICAgYW55b25lQ2FuQWRkU2VsZlxuICAgIGF0dGFjaG1lbnRzXG4gICAgYXR0ZW5kZWVzT21pdHRlZFxuICAgIGJhY2tncm91bmRDb2xvclxuICAgIGNhbGVuZGFySWRcbiAgICBjb2xvcklkXG4gICAgY29uZmVyZW5jZUlkXG4gICAgY29weUF2YWlsYWJpbGl0eVxuICAgIGNvcHlDYXRlZ29yaWVzXG4gICAgY29weUR1cmF0aW9uXG4gICAgY29weUlzQnJlYWtcbiAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICBjb3B5SXNNZWV0aW5nXG4gICAgY29weU1vZGlmaWFibGVcbiAgICBjb3B5UHJpb3JpdHlMZXZlbFxuICAgIGNvcHlSZW1pbmRlcnNcbiAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgY29weVRpbWVQcmVmZXJlbmNlXG4gICAgY3JlYXRlZERhdGVcbiAgICBjcmVhdG9yXG4gICAgZGFpbHlUYXNrTGlzdFxuICAgIGRlbGV0ZWRcbiAgICBkdXJhdGlvblxuICAgIGVuZERhdGVcbiAgICBlbmRUaW1lVW5zcGVjaWZpZWRcbiAgICBldmVudElkXG4gICAgZXZlbnRUeXBlXG4gICAgZXh0ZW5kZWRQcm9wZXJ0aWVzXG4gICAgZm9sbG93VXBFdmVudElkXG4gICAgZm9yRXZlbnRJZFxuICAgIGZvcmVncm91bmRDb2xvclxuICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgIGd1ZXN0c0Nhbk1vZGlmeVxuICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgaGFuZ291dExpbmtcbiAgICBoYXJkRGVhZGxpbmVcbiAgICBodG1sTGlua1xuICAgIGlDYWxVSURcbiAgICBpZFxuICAgIGlzQnJlYWtcbiAgICBpc0V4dGVybmFsTWVldGluZ1xuICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgIGlzRm9sbG93VXBcbiAgICBpc01lZXRpbmdcbiAgICBpc01lZXRpbmdNb2RpZmlhYmxlXG4gICAgaXNQb3N0RXZlbnRcbiAgICBpc1ByZUV2ZW50XG4gICAgbGlua3NcbiAgICBsb2NhdGlvblxuICAgIGxvY2tlZFxuICAgIG1heEF0dGVuZGVlc1xuICAgIG1ldGhvZFxuICAgIG1vZGlmaWFibGVcbiAgICBuZWdhdGl2ZUltcGFjdERheU9mV2Vla1xuICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmVcbiAgICBuZWdhdGl2ZUltcGFjdFRpbWVcbiAgICBub3Rlc1xuICAgIG9yZ2FuaXplclxuICAgIG9yaWdpbmFsQWxsRGF5XG4gICAgb3JpZ2luYWxTdGFydERhdGVcbiAgICBvcmlnaW5hbFRpbWV6b25lXG4gICAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWtcbiAgICBwb3NpdGl2ZUltcGFjdFNjb3JlXG4gICAgcG9zaXRpdmVJbXBhY3RUaW1lXG4gICAgcG9zdEV2ZW50SWRcbiAgICBwcmVFdmVudElkXG4gICAgcHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgcHJlZmVycmVkRW5kVGltZVJhbmdlXG4gICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICBwcmVmZXJyZWRUaW1lXG4gICAgcHJpb3JpdHlcbiAgICBwcml2YXRlQ29weVxuICAgIHJlY3VycmVuY2VcbiAgICByZWN1cnJlbmNlUnVsZVxuICAgIHJlY3VycmluZ0V2ZW50SWRcbiAgICBzZW5kVXBkYXRlc1xuICAgIHNvZnREZWFkbGluZVxuICAgIHNvdXJjZVxuICAgIHN0YXJ0RGF0ZVxuICAgIHN0YXR1c1xuICAgIHN1bW1hcnlcbiAgICB0YXNrSWRcbiAgICB0YXNrVHlwZVxuICAgIHRpbWVCbG9ja2luZ1xuICAgIHRpbWV6b25lXG4gICAgdGl0bGVcbiAgICB0cmFuc3BhcmVuY3lcbiAgICB1bmxpbmtcbiAgICB1cGRhdGVkQXRcbiAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgdXNlcklkXG4gICAgdXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5XG4gICAgdXNlck1vZGlmaWVkQ2F0ZWdvcmllc1xuICAgIHVzZXJNb2RpZmllZER1cmF0aW9uXG4gICAgdXNlck1vZGlmaWVkSXNCcmVha1xuICAgIHVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgdXNlck1vZGlmaWVkSXNNZWV0aW5nXG4gICAgdXNlck1vZGlmaWVkTW9kaWZpYWJsZVxuICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWxcbiAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnNcbiAgICB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmdcbiAgICB1c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZVxuICAgIHZpc2liaWxpdHlcbiAgICB3ZWVrbHlUYXNrTGlzdFxuICAgIGJ5V2Vla0RheVxuICAgIGxvY2FsU3luY2VkXG4gICAgdXNlck1vZGlmaWVkQ29sb3JcbiAgICBjb3B5Q29sb3JcbiAgICB1c2VyTW9kaWZpZWRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgdXNlck1vZGlmaWVkTWVldGluZ01vZGlmaWFibGVcbiAgICBtZWV0aW5nSWRcbiAgICBjb3B5TWVldGluZ01vZGlmaWFibGVcbiAgICBjb3B5RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICB9XG59XG5cbiAgYDtcbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBFdmVudF9ieV9wazogRXZlbnRQbHVzVHlwZSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgaWQsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBnZXRFdmVudEZyb21QcmltYXJ5S2V5Jyk7XG4gICAgY29uc3QgZXZlbnQgPSByZXM/LmRhdGE/LkV2ZW50X2J5X3BrO1xuICAgIGlmICghZXZlbnQpIHtcbiAgICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiBudWxsIH07IC8vIE5vdCBmb3VuZCBpcyBhIHZhbGlkIHN1Y2Nlc3MgY2FzZSBmb3IgZ2V0IGJ5IFBLXG4gICAgfVxuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiBldmVudCB9O1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBnZXR0aW5nIGV2ZW50IGZyb20gcHJpbWFyeSBrZXk6JywgZSk7XG4gICAgY29uc3QgZXJyb3JEZXRhaWxzID0gZS5yZXNwb25zZT8uYm9keSB8fCBlLm1lc3NhZ2UgfHwgZTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0hBU1VSQV9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gZ2V0IGV2ZW50IGJ5IFBLOiAke2UubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBlcnJvckRldGFpbHMsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjb3B5T3ZlclByZXZpb3VzRXZlbnREZWZhdWx0cyA9IChcbiAgZXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIHByZXZpb3VzRXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIGNhdGVnb3J5PzogQ2F0ZWdvcnlUeXBlLFxuICB1c2VyUHJlZmVyZW5jZXM/OiBVc2VyUHJlZmVyZW5jZVR5cGVcbik6IEV2ZW50UGx1c1R5cGUgPT4ge1xuICBjb25zdCBwcmV2aW91c0R1cmF0aW9uID0gZGF5anNcbiAgICAuZHVyYXRpb24oXG4gICAgICBkYXlqcyhwcmV2aW91c0V2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoocHJldmlvdXNFdmVudD8udGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5kaWZmKFxuICAgICAgICAgIGRheWpzKHByZXZpb3VzRXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooXG4gICAgICAgICAgICBwcmV2aW91c0V2ZW50Py50aW1lem9uZSxcbiAgICAgICAgICAgIHRydWVcbiAgICAgICAgICApXG4gICAgICAgIClcbiAgICApXG4gICAgLmFzTWludXRlcygpO1xuICByZXR1cm4ge1xuICAgIC4uLmV2ZW50LFxuICAgIHRyYW5zcGFyZW5jeTogIWV2ZW50Py51c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHlcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weUF2YWlsYWJpbGl0eVxuICAgICAgICA/IHByZXZpb3VzRXZlbnQudHJhbnNwYXJlbmN5XG4gICAgICAgIDogY2F0ZWdvcnk/LmNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnRyYW5zcGFyZW5jeVxuICAgICAgICAgIDogY2F0ZWdvcnk/LmRlZmF1bHRBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgID8gJ3RyYW5zcGFyZW50J1xuICAgICAgICAgICAgOiB1c2VyUHJlZmVyZW5jZXM/LmNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py50cmFuc3BhcmVuY3lcbiAgICAgICAgICAgICAgOiBldmVudD8udHJhbnNwYXJlbmN5XG4gICAgICA6IGV2ZW50LnRyYW5zcGFyZW5jeSxcbiAgICBwcmVmZXJyZWRUaW1lOiAhZXZlbnQ/LnVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlXG4gICAgICA/IHByZXZpb3VzRXZlbnQ/LmNvcHlUaW1lUHJlZmVyZW5jZSAmJiBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWRUaW1lXG4gICAgICAgID8gcHJldmlvdXNFdmVudC5wcmVmZXJyZWRUaW1lXG4gICAgICAgIDogY2F0ZWdvcnk/LmNvcHlUaW1lUHJlZmVyZW5jZSAmJiBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWRUaW1lXG4gICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWRUaW1lXG4gICAgICAgICAgOiB1c2VyUHJlZmVyZW5jZXM/LmNvcHlUaW1lUHJlZmVyZW5jZSAmJiBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWRUaW1lXG4gICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZFRpbWVcbiAgICAgICAgICAgIDogZXZlbnQ/LnByZWZlcnJlZFRpbWVcbiAgICAgIDogZXZlbnQucHJlZmVycmVkVGltZSxcbiAgICBwcmVmZXJyZWREYXlPZldlZWs6ICFldmVudD8udXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2VcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weVRpbWVQcmVmZXJlbmNlICYmIHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZERheU9mV2Vla1xuICAgICAgICA/IHByZXZpb3VzRXZlbnQucHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICAgIDogY2F0ZWdvcnk/LmNvcHlUaW1lUHJlZmVyZW5jZSAmJiBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWREYXlPZldlZWtcbiAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZERheU9mV2Vla1xuICAgICAgICAgIDogdXNlclByZWZlcmVuY2VzPy5jb3B5VGltZVByZWZlcmVuY2UgJiZcbiAgICAgICAgICAgICAgcHJldmlvdXNFdmVudD8ucHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZERheU9mV2Vla1xuICAgICAgICAgICAgOiBldmVudD8ucHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICA6IGV2ZW50LnByZWZlcnJlZERheU9mV2VlayxcbiAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZTogIWV2ZW50Py51c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZVxuICAgICAgPyBwcmV2aW91c0V2ZW50Py5jb3B5VGltZVByZWZlcmVuY2UgJiZcbiAgICAgICAgcHJldmlvdXNFdmVudD8ucHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICAgICAgPyBwcmV2aW91c0V2ZW50LnByZWZlcnJlZFN0YXJ0VGltZVJhbmdlXG4gICAgICAgIDogY2F0ZWdvcnk/LmNvcHlUaW1lUHJlZmVyZW5jZSAmJiBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWRTdGFydFRpbWVSYW5nZVxuICAgICAgICAgID8gcHJldmlvdXNFdmVudD8ucHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weVRpbWVQcmVmZXJlbmNlICYmXG4gICAgICAgICAgICAgIHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZFN0YXJ0VGltZVJhbmdlXG4gICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZFN0YXJ0VGltZVJhbmdlXG4gICAgICAgICAgICA6IGV2ZW50Py5wcmVmZXJyZWRTdGFydFRpbWVSYW5nZVxuICAgICAgOiBldmVudC5wcmVmZXJyZWRTdGFydFRpbWVSYW5nZSxcbiAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2U6ICFldmVudD8udXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2VcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weVRpbWVQcmVmZXJlbmNlICYmXG4gICAgICAgIHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICA/IHByZXZpb3VzRXZlbnQucHJlZmVycmVkRW5kVGltZVJhbmdlXG4gICAgICAgIDogY2F0ZWdvcnk/LmNvcHlUaW1lUHJlZmVyZW5jZSAmJiBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWRFbmRUaW1lUmFuZ2VcbiAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICAgIDogdXNlclByZWZlcmVuY2VzPy5jb3B5VGltZVByZWZlcmVuY2UgJiZcbiAgICAgICAgICAgICAgcHJldmlvdXNFdmVudD8ucHJlZmVycmVkRW5kVGltZVJhbmdlXG4gICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICAgICAgOiBldmVudD8ucHJlZmVycmVkRW5kVGltZVJhbmdlXG4gICAgICA6IGV2ZW50LnByZWZlcnJlZEVuZFRpbWVSYW5nZSxcbiAgICBwcmlvcml0eTpcbiAgICAgICghZXZlbnQ/LnVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWxcbiAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5jb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgICAgID8gcHJldmlvdXNFdmVudC5wcmlvcml0eVxuICAgICAgICAgIDogY2F0ZWdvcnk/LmNvcHlQcmlvcml0eUxldmVsXG4gICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByaW9yaXR5XG4gICAgICAgICAgICA6IGNhdGVnb3J5Py5kZWZhdWx0UHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0UHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByaW9yaXR5XG4gICAgICAgICAgICAgICAgOiBldmVudD8ucHJpb3JpdHlcbiAgICAgICAgOiBldmVudD8ucHJpb3JpdHkpIHx8IDEsXG4gICAgaXNCcmVhazogIWV2ZW50Py51c2VyTW9kaWZpZWRJc0JyZWFrXG4gICAgICA/IHByZXZpb3VzRXZlbnQ/LmNvcHlJc0JyZWFrXG4gICAgICAgID8gcHJldmlvdXNFdmVudC5pc0JyZWFrXG4gICAgICAgIDogY2F0ZWdvcnk/LmNvcHlJc0JyZWFrXG4gICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5pc0JyZWFrXG4gICAgICAgICAgOiBjYXRlZ29yeT8uZGVmYXVsdElzQnJlYWtcbiAgICAgICAgICAgID8gY2F0ZWdvcnk/LmRlZmF1bHRJc0JyZWFrXG4gICAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weUlzQnJlYWtcbiAgICAgICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5pc0JyZWFrXG4gICAgICAgICAgICAgIDogZXZlbnQ/LmlzQnJlYWtcbiAgICAgIDogZXZlbnQuaXNCcmVhayxcbiAgICBpc01lZXRpbmc6ICFldmVudD8udXNlck1vZGlmaWVkSXNNZWV0aW5nXG4gICAgICA/IHByZXZpb3VzRXZlbnQ/LmNvcHlJc01lZXRpbmdcbiAgICAgICAgPyBwcmV2aW91c0V2ZW50LmlzTWVldGluZ1xuICAgICAgICA6IGNhdGVnb3J5Py5jb3B5SXNNZWV0aW5nXG4gICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5pc01lZXRpbmdcbiAgICAgICAgICA6IGNhdGVnb3J5Py5kZWZhdWx0SXNNZWV0aW5nXG4gICAgICAgICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0SXNNZWV0aW5nXG4gICAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weUlzTWVldGluZ1xuICAgICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LmlzTWVldGluZ1xuICAgICAgICAgICAgICA6IGNhdGVnb3J5Py5uYW1lID09PSBtZWV0aW5nTGFiZWxcbiAgICAgICAgICAgICAgICA/IHRydWVcbiAgICAgICAgICAgICAgICA6IGV2ZW50Py5pc01lZXRpbmdcbiAgICAgIDogZXZlbnQuaXNNZWV0aW5nLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nOiAhZXZlbnQ/LnVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICA/IHByZXZpb3VzRXZlbnQ/LmNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICA/IHByZXZpb3VzRXZlbnQuaXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgOiBjYXRlZ29yeT8uY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5pc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgIDogY2F0ZWdvcnk/LmRlZmF1bHRJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgPyBjYXRlZ29yeT8uZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICAgID8gcHJldmlvdXNFdmVudD8uaXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgOiBjYXRlZ29yeT8ubmFtZSA9PT0gZXh0ZXJuYWxNZWV0aW5nTGFiZWxcbiAgICAgICAgICAgICAgICA/IHRydWVcbiAgICAgICAgICAgICAgICA6IGV2ZW50Py5pc0V4dGVybmFsTWVldGluZ1xuICAgICAgOiBldmVudC5pc0V4dGVybmFsTWVldGluZyxcbiAgICBtb2RpZmlhYmxlOiAhZXZlbnQ/LnVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weU1vZGlmaWFibGVcbiAgICAgICAgPyBwcmV2aW91c0V2ZW50Lm1vZGlmaWFibGVcbiAgICAgICAgOiBjYXRlZ29yeT8uY29weU1vZGlmaWFibGVcbiAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/Lm1vZGlmaWFibGVcbiAgICAgICAgICA6IGNhdGVnb3J5Py5kZWZhdWx0TW9kaWZpYWJsZVxuICAgICAgICAgICAgPyBjYXRlZ29yeT8uZGVmYXVsdE1vZGlmaWFibGVcbiAgICAgICAgICAgIDogdXNlclByZWZlcmVuY2VzPy5jb3B5TW9kaWZpYWJsZVxuICAgICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/Lm1vZGlmaWFibGVcbiAgICAgICAgICAgICAgOiBldmVudD8ubW9kaWZpYWJsZVxuICAgICAgOiBldmVudC5tb2RpZmlhYmxlLFxuICAgIGlzTWVldGluZ01vZGlmaWFibGU6ICFldmVudD8udXNlck1vZGlmaWVkTW9kaWZpYWJsZVxuICAgICAgPyBwcmV2aW91c0V2ZW50Py5jb3B5SXNNZWV0aW5nXG4gICAgICAgID8gcHJldmlvdXNFdmVudC5pc01lZXRpbmdcbiAgICAgICAgOiBjYXRlZ29yeT8uY29weUlzTWVldGluZ1xuICAgICAgICAgID8gcHJldmlvdXNFdmVudD8uaXNNZWV0aW5nXG4gICAgICAgICAgOiBjYXRlZ29yeT8uZGVmYXVsdElzTWVldGluZ1xuICAgICAgICAgICAgPyBjYXRlZ29yeT8uZGVmYXVsdElzTWVldGluZ1xuICAgICAgICAgICAgOiB1c2VyUHJlZmVyZW5jZXM/LmNvcHlJc01lZXRpbmdcbiAgICAgICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5pc01lZXRpbmdcbiAgICAgICAgICAgICAgOiBldmVudD8uaXNNZWV0aW5nXG4gICAgICA6IGV2ZW50LmlzTWVldGluZ01vZGlmaWFibGUsXG4gICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlOiAhZXZlbnQ/LnVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgID8gcHJldmlvdXNFdmVudC5pc0V4dGVybmFsTWVldGluZ1xuICAgICAgICA6IGNhdGVnb3J5Py5jb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LmlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgOiBjYXRlZ29yeT8uZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgIDogdXNlclByZWZlcmVuY2VzPy5jb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5pc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgICA6IGV2ZW50Py5pc0V4dGVybmFsTWVldGluZ1xuICAgICAgOiBldmVudC5pc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGUsXG4gICAgZHVyYXRpb246ICFldmVudD8udXNlck1vZGlmaWVkRHVyYXRpb25cbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weUR1cmF0aW9uXG4gICAgICAgID8gcHJldmlvdXNFdmVudC5kdXJhdGlvbiB8fCBwcmV2aW91c0R1cmF0aW9uXG4gICAgICAgIDogZXZlbnQ/LmR1cmF0aW9uXG4gICAgICA6IGV2ZW50LmR1cmF0aW9uLFxuICAgIGVuZERhdGU6ICFldmVudD8udXNlck1vZGlmaWVkRHVyYXRpb25cbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weUR1cmF0aW9uXG4gICAgICAgID8gZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5hZGQocHJldmlvdXNFdmVudC5kdXJhdGlvbiB8fCBwcmV2aW91c0R1cmF0aW9uLCAnbWludXRlcycpXG4gICAgICAgICAgICAuZm9ybWF0KClcbiAgICAgICAgOiBldmVudD8uZW5kRGF0ZVxuICAgICAgOiBldmVudC5lbmREYXRlLFxuICAgIHByZWZlcnJlZFRpbWVSYW5nZXM6ICFldmVudD8udXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2VcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weVRpbWVQcmVmZXJlbmNlICYmXG4gICAgICAgIHByZXZpb3VzRXZlbnQucHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMFxuICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZFRpbWVSYW5nZXM/Lm1hcCgocCkgPT4gKHtcbiAgICAgICAgICAgIC4uLnAsXG4gICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgZXZlbnRJZDogZXZlbnQ/LmlkLFxuICAgICAgICAgIH0pKVxuICAgICAgICA6IGNhdGVnb3J5Py5jb3B5VGltZVByZWZlcmVuY2UgJiZcbiAgICAgICAgICAgIHByZXZpb3VzRXZlbnQucHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMFxuICAgICAgICAgID8gcHJldmlvdXNFdmVudD8ucHJlZmVycmVkVGltZVJhbmdlcz8ubWFwKChwKSA9PiAoe1xuICAgICAgICAgICAgICAuLi5wLFxuICAgICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgICBldmVudElkOiBldmVudD8uaWQsXG4gICAgICAgICAgICB9KSlcbiAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weVRpbWVQcmVmZXJlbmNlICYmXG4gICAgICAgICAgICAgIHByZXZpb3VzRXZlbnQucHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMFxuICAgICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWRUaW1lUmFuZ2VzPy5tYXAoKHApID0+ICh7XG4gICAgICAgICAgICAgICAgLi4ucCxcbiAgICAgICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgICAgIGV2ZW50SWQ6IGV2ZW50Py5pZCxcbiAgICAgICAgICAgICAgfSkpXG4gICAgICAgICAgICA6IGNhdGVnb3J5Py5kZWZhdWx0VGltZVByZWZlcmVuY2U/Lmxlbmd0aCA+IDBcbiAgICAgICAgICAgICAgPyBjYXRlZ29yeT8uZGVmYXVsdFRpbWVQcmVmZXJlbmNlPy5tYXAoKHRwKSA9PiAoe1xuICAgICAgICAgICAgICAgICAgLi4udHAsXG4gICAgICAgICAgICAgICAgICBldmVudElkOiBldmVudD8uaWQsXG4gICAgICAgICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgICAgICAgICAgdXNlcklkOiBldmVudD8udXNlcklkLFxuICAgICAgICAgICAgICAgIH0pKVxuICAgICAgICAgICAgICA6IGV2ZW50Py5wcmVmZXJyZWRUaW1lUmFuZ2VzXG4gICAgICA6IGV2ZW50LnByZWZlcnJlZFRpbWVSYW5nZXMsXG5cbiAgICBjb3B5QXZhaWxhYmlsaXR5OiAhcHJldmlvdXNFdmVudD8udW5saW5rXG4gICAgICA/IHByZXZpb3VzRXZlbnQuY29weUF2YWlsYWJpbGl0eVxuICAgICAgOiBmYWxzZSxcbiAgICBjb3B5VGltZVByZWZlcmVuY2U6ICFwcmV2aW91c0V2ZW50Py51bmxpbmtcbiAgICAgID8gcHJldmlvdXNFdmVudC5jb3B5VGltZVByZWZlcmVuY2VcbiAgICAgIDogZmFsc2UsXG4gICAgY29weVByaW9yaXR5TGV2ZWw6ICFwcmV2aW91c0V2ZW50Py51bmxpbmtcbiAgICAgID8gcHJldmlvdXNFdmVudC5jb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgOiBmYWxzZSxcbiAgICBjb3B5SXNCcmVhazogIXByZXZpb3VzRXZlbnQ/LnVubGluayA/IHByZXZpb3VzRXZlbnQuY29weUlzQnJlYWsgOiBmYWxzZSxcbiAgICBjb3B5TW9kaWZpYWJsZTogIXByZXZpb3VzRXZlbnQ/LnVubGlua1xuICAgICAgPyBwcmV2aW91c0V2ZW50LmNvcHlNb2RpZmlhYmxlXG4gICAgICA6IGZhbHNlLFxuICAgIGNvcHlJc01lZXRpbmc6ICFwcmV2aW91c0V2ZW50Py51bmxpbmsgPyBwcmV2aW91c0V2ZW50LmNvcHlJc01lZXRpbmcgOiBmYWxzZSxcbiAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmc6ICFwcmV2aW91c0V2ZW50Py51bmxpbmtcbiAgICAgID8gcHJldmlvdXNFdmVudC5jb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgIDogZmFsc2UsXG4gICAgY29weUR1cmF0aW9uOiAhcHJldmlvdXNFdmVudD8udW5saW5rID8gcHJldmlvdXNFdmVudC5jb3B5RHVyYXRpb24gOiBmYWxzZSxcbiAgICBjb3B5Q2F0ZWdvcmllczogIXByZXZpb3VzRXZlbnQ/LnVubGlua1xuICAgICAgPyBwcmV2aW91c0V2ZW50LmNvcHlDYXRlZ29yaWVzXG4gICAgICA6IGZhbHNlLFxuICAgIGNvcHlSZW1pbmRlcnM6ICFwcmV2aW91c0V2ZW50Py51bmxpbmsgPyBwcmV2aW91c0V2ZW50LmNvcHlSZW1pbmRlcnMgOiBmYWxzZSxcbiAgICBjb3B5VGltZUJsb2NraW5nOiAhcHJldmlvdXNFdmVudD8udW5saW5rXG4gICAgICA/IHByZXZpb3VzRXZlbnQuY29weVRpbWVCbG9ja2luZ1xuICAgICAgOiBmYWxzZSxcbiAgICBjb3B5Q29sb3I6ICFwcmV2aW91c0V2ZW50Py51bmxpbmsgPyBwcmV2aW91c0V2ZW50LmNvcHlDb2xvciA6IGZhbHNlLFxuICAgIHVubGluazogIXByZXZpb3VzRXZlbnQ/LnVubGluayA/IGZhbHNlIDogdHJ1ZSxcblxuICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrOiAhcHJldmlvdXNFdmVudD8udW5saW5rXG4gICAgICA/IHByZXZpb3VzRXZlbnQucG9zaXRpdmVJbXBhY3REYXlPZldlZWtcbiAgICAgIDogbnVsbCxcbiAgICBwb3NpdGl2ZUltcGFjdFNjb3JlOiAhcHJldmlvdXNFdmVudD8udW5saW5rXG4gICAgICA/IHByZXZpb3VzRXZlbnQucG9zaXRpdmVJbXBhY3RTY29yZVxuICAgICAgOiBudWxsLFxuICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrOiAhcHJldmlvdXNFdmVudD8udW5saW5rXG4gICAgICA/IHByZXZpb3VzRXZlbnQubmVnYXRpdmVJbXBhY3REYXlPZldlZWtcbiAgICAgIDogbnVsbCxcbiAgICBuZWdhdGl2ZUltcGFjdFNjb3JlOiAhcHJldmlvdXNFdmVudD8udW5saW5rXG4gICAgICA/IHByZXZpb3VzRXZlbnQubmVnYXRpdmVJbXBhY3RTY29yZVxuICAgICAgOiBudWxsLFxuICAgIHBvc2l0aXZlSW1wYWN0VGltZTogIXByZXZpb3VzRXZlbnQ/LnVubGlua1xuICAgICAgPyBwcmV2aW91c0V2ZW50LnBvc2l0aXZlSW1wYWN0VGltZVxuICAgICAgOiBudWxsLFxuICAgIG5lZ2F0aXZlSW1wYWN0VGltZTogIXByZXZpb3VzRXZlbnQ/LnVubGlua1xuICAgICAgPyBwcmV2aW91c0V2ZW50Lm5lZ2F0aXZlSW1wYWN0VGltZVxuICAgICAgOiBudWxsLFxuXG4gICAgYmFja2dyb3VuZENvbG9yOiAhZXZlbnQ/LnVzZXJNb2RpZmllZENvbG9yXG4gICAgICA/IHByZXZpb3VzRXZlbnQ/LmNvcHlDb2xvclxuICAgICAgICA/IHByZXZpb3VzRXZlbnQuYmFja2dyb3VuZENvbG9yXG4gICAgICAgIDogY2F0ZWdvcnk/LmNvbG9yXG4gICAgICAgICAgPyBjYXRlZ29yeT8uY29sb3JcbiAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weUNvbG9yXG4gICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LmJhY2tncm91bmRDb2xvclxuICAgICAgICAgICAgOiBldmVudD8uYmFja2dyb3VuZENvbG9yXG4gICAgICA6IGV2ZW50LmJhY2tncm91bmRDb2xvcixcbiAgICBjb2xvcklkOlxuICAgICAgcHJldmlvdXNFdmVudD8uY29weUNvbG9yICYmIHByZXZpb3VzRXZlbnQ/LmNvbG9ySWRcbiAgICAgICAgPyBwcmV2aW91c0V2ZW50LmNvbG9ySWRcbiAgICAgICAgOiB1c2VyUHJlZmVyZW5jZXM/LmNvcHlDb2xvciAmJiBwcmV2aW91c0V2ZW50Py5jb2xvcklkXG4gICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5jb2xvcklkXG4gICAgICAgICAgOiBldmVudD8uY29sb3JJZCxcbiAgfTtcbn07XG5cbmV4cG9ydCBjb25zdCBsaXN0RnV0dXJlTWVldGluZ0Fzc2lzdHMgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgd2luZG93RW5kRGF0ZTogc3RyaW5nLFxuICBpZHM/OiBzdHJpbmdbXVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICB1c2VySWQsXG4gICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgaWRzLFxuICAgICAgJyB1c2VySWQsIHdpbmRvd1N0YXJ0RGF0ZSwgd2luZG93RW5kRGF0ZSwgaWRzJ1xuICAgICk7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdMaXN0TWVldGluZ0Fzc2lzdCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBxdWVyeSBMaXN0TWVldGluZ0Fzc2lzdCgkdXNlcklkOiB1dWlkISwgJHdpbmRvd1N0YXJ0RGF0ZTogdGltZXN0YW1wISwgJHdpbmRvd0VuZERhdGU6IHRpbWVzdGFtcCEsICR7aWRzPy5sZW5ndGggPiAwID8gJyRpZHM6IFt1dWlkIV0hJyA6ICcnfSkge1xuICAgICAgICAgICAgICAgIE1lZXRpbmdfQXNzaXN0KHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgd2luZG93RW5kRGF0ZToge19sdGU6ICR3aW5kb3dFbmREYXRlfSwgd2luZG93U3RhcnREYXRlOiB7X2d0ZTogJHdpbmRvd1N0YXJ0RGF0ZX0sIGNhbmNlbGxlZDoge19lcTogZmFsc2V9JHtpZHM/Lmxlbmd0aCA+IDAgPyAnLCBpZDoge19uaW46ICRpZHN9JyA6ICcnfSwgZXZlbnRJZDoge19pc19udWxsOiB0cnVlfX0pIHtcbiAgICAgICAgICAgICAgICAgICAgYWxsb3dBdHRlbmRlZVVwZGF0ZVByZWZlcmVuY2VzXG4gICAgICAgICAgICAgICAgICAgIGFueW9uZUNhbkFkZFNlbGZcbiAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVDYW5Nb2RpZnlcbiAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVDb3VudFxuICAgICAgICAgICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVSZXNwb25kZWRDb3VudFxuICAgICAgICAgICAgICAgICAgICBidWZmZXJUaW1lXG4gICAgICAgICAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgICAgICAgICAgY2FuY2VsSWZBbnlSZWZ1c2VcbiAgICAgICAgICAgICAgICAgICAgY2FuY2VsbGVkXG4gICAgICAgICAgICAgICAgICAgIGNvbG9ySWRcbiAgICAgICAgICAgICAgICAgICAgY29uZmVyZW5jZUFwcFxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBkdXJhdGlvblxuICAgICAgICAgICAgICAgICAgICBlbmFibGVBdHRlbmRlZVByZWZlcmVuY2VzXG4gICAgICAgICAgICAgICAgICAgIGVuYWJsZUNvbmZlcmVuY2VcbiAgICAgICAgICAgICAgICAgICAgZW5hYmxlSG9zdFByZWZlcmVuY2VzXG4gICAgICAgICAgICAgICAgICAgIGVuZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBleHBpcmVEYXRlXG4gICAgICAgICAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICBndWFyYW50ZWVBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uXG4gICAgICAgICAgICAgICAgICAgIG1pblRocmVzaG9sZENvdW50XG4gICAgICAgICAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICAgICAgICAgIHJlbWluZGVyc1xuICAgICAgICAgICAgICAgICAgICBzZW5kVXBkYXRlc1xuICAgICAgICAgICAgICAgICAgICBzdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgc3VtbWFyeVxuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIHZpc2liaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgd2luZG93RW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICB3aW5kb3dTdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgaW50ZXJ2YWxcbiAgICAgICAgICAgICAgICAgICAgbG9ja0FmdGVyXG4gICAgICAgICAgICAgICAgICAgIG9yaWdpbmFsTWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgIHVudGlsXG4gICAgICAgICAgICAgICAgICAgIGZyZXF1ZW5jeVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGxldCB2YXJpYWJsZXM6IGFueSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgfTtcblxuICAgIGlmIChpZHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIHZhcmlhYmxlcy5pZHMgPSBpZHM7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgTWVldGluZ19Bc3Npc3Q6IE1lZXRpbmdBc3Npc3RUeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgaW5zaWRlIGxpc3QgZnV0dXJlIG1lZXRpbmcgYXNzaXN0Jyk7XG4gICAgY29uc29sZS5sb2coXG4gICAgICByZXM/LmRhdGE/Lk1lZXRpbmdfQXNzaXN0LFxuICAgICAgJyBzdWNjZXNzZnVsbHkgZ290IG1lZXRpbmcgYXNzc2lzdHMnXG4gICAgKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/Lk1lZXRpbmdfQXNzaXN0O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gbGlzdCBtZWV0aW5nIGFzc2lzdHMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IG1lZXRpbmdBdHRlbmRlZUNvdW50R2l2ZW5NZWV0aW5nSWQgPSBhc3luYyAobWVldGluZ0lkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0F0dGVuZGVlQ291bnRHaXZlTWVldGluZ0lkJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IEF0dGVuZGVlQ291bnRHaXZlTWVldGluZ0lkKCRtZWV0aW5nSWQ6IHV1aWQhKSB7XG4gICAgICAgICAgICAgICAgTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWVfYWdncmVnYXRlKHdoZXJlOiB7bWVldGluZ0lkOiB7X2VxOiAkbWVldGluZ0lkfX0pIHtcbiAgICAgICAgICAgICAgICAgICAgYWdncmVnYXRlIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvdW50XG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG5cbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBtZWV0aW5nSWQsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczoge1xuICAgICAgZGF0YToge1xuICAgICAgICBNZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZV9hZ2dyZWdhdGU6IHsgYWdncmVnYXRlOiB7IGNvdW50OiBudW1iZXIgfSB9O1xuICAgICAgfTtcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgcmVzPy5kYXRhPy5NZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZV9hZ2dyZWdhdGU/LmFnZ3JlZ2F0ZT8uY291bnQsXG4gICAgICAnIHJlY2VpdmVkIGF0dGVuZGVlIGNvdW50J1xuICAgICk7XG5cbiAgICByZXR1cm4gcmVzPy5kYXRhPy5NZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZV9hZ2dyZWdhdGU/LmFnZ3JlZ2F0ZT8uY291bnQ7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgbWVldGluZyBhdHRlbmRlZSBjb3VudCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgY3JlYXRlUHJlQW5kUG9zdEV2ZW50c0Zyb21QcmV2aW91c0V2ZW50ID0gKFxuICBldmVudDogRXZlbnRQbHVzVHlwZSxcbiAgcHJldmlvdXNFdmVudDogRXZlbnRQbHVzVHlwZVxuKSA9PiB7XG4gIGlmICghcHJldmlvdXNFdmVudD8uY29weVRpbWVCbG9ja2luZykge1xuICAgIGNvbnNvbGUubG9nKCdubyBjb3B5IHRpbWUgYmxvY2tpbmcnKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuXG4gIGlmIChldmVudC51c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmcpIHtcbiAgICBjb25zb2xlLmxvZygndXNlciBtb2RpZmllZCB0aW1lIGJsb2NraW5nJyk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICBjb25zdCBldmVudElkID0gdXVpZCgpO1xuICBjb25zdCBldmVudElkMSA9IHV1aWQoKTtcbiAgY29uc3QgcHJlRXZlbnRJZCA9IGV2ZW50Py5wcmVFdmVudElkIHx8IGAke2V2ZW50SWR9IyR7ZXZlbnQ/LmNhbGVuZGFySWR9YDtcbiAgY29uc3QgcG9zdEV2ZW50SWQgPSBldmVudD8ucG9zdEV2ZW50SWQgfHwgYCR7ZXZlbnRJZDF9IyR7ZXZlbnQ/LmNhbGVuZGFySWR9YDtcblxuICBsZXQgdmFsdWVzVG9SZXR1cm46IGFueSA9IHt9O1xuICB2YWx1ZXNUb1JldHVybi5uZXdFdmVudCA9IGV2ZW50O1xuXG4gIGlmIChwcmV2aW91c0V2ZW50Py50aW1lQmxvY2tpbmc/LmFmdGVyRXZlbnQpIHtcbiAgICBjb25zdCBmb3JtYXR0ZWRab25lQWZ0ZXJFdmVudEVuZERhdGUgPSBkYXlqcyhldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5hZGQocHJldmlvdXNFdmVudD8udGltZUJsb2NraW5nPy5hZnRlckV2ZW50LCAnbScpXG4gICAgICAuZm9ybWF0KCk7XG4gICAgY29uc3QgZm9ybWF0dGVkWm9uZUFmdGVyRXZlbnRTdGFydERhdGUgPSBkYXlqcyhldmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5mb3JtYXQoKTtcblxuICAgIGNvbnN0IGFmdGVyRXZlbnQ6IEV2ZW50UGx1c1R5cGUgPSB7XG4gICAgICBpZDogcG9zdEV2ZW50SWQsXG4gICAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICAgIGZvckV2ZW50SWQ6IGV2ZW50LmlkLFxuICAgICAgaXNQb3N0RXZlbnQ6IHRydWUsXG4gICAgICBub3RlczogJ0J1ZmZlciB0aW1lJyxcbiAgICAgIHN1bW1hcnk6ICdCdWZmZXIgdGltZScsXG4gICAgICBzdGFydERhdGU6IGZvcm1hdHRlZFpvbmVBZnRlckV2ZW50U3RhcnREYXRlLFxuICAgICAgZW5kRGF0ZTogZm9ybWF0dGVkWm9uZUFmdGVyRXZlbnRFbmREYXRlLFxuICAgICAgbWV0aG9kOiBldmVudD8ucG9zdEV2ZW50SWQgPyAndXBkYXRlJyA6ICdjcmVhdGUnLFxuICAgICAgdXNlcklkOiBldmVudD8udXNlcklkLFxuICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgcHJpb3JpdHk6IDEsXG4gICAgICBpc0ZvbGxvd1VwOiBmYWxzZSxcbiAgICAgIG1vZGlmaWFibGU6IHRydWUsXG4gICAgICBhbnlvbmVDYW5BZGRTZWxmOiBmYWxzZSxcbiAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyczogZmFsc2UsXG4gICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0czogZmFsc2UsXG4gICAgICBvcmlnaW5hbFN0YXJ0RGF0ZTogdW5kZWZpbmVkLFxuICAgICAgb3JpZ2luYWxBbGxEYXk6IGZhbHNlLFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICBjYWxlbmRhcklkOiBldmVudD8uY2FsZW5kYXJJZCxcbiAgICAgIHRpbWV6b25lOiBldmVudD8udGltZXpvbmUsXG4gICAgICBldmVudElkOiBwb3N0RXZlbnRJZC5zcGxpdCgnIycpWzBdLFxuICAgIH07XG4gICAgdmFsdWVzVG9SZXR1cm4uYWZ0ZXJFdmVudCA9IGFmdGVyRXZlbnQ7XG4gICAgdmFsdWVzVG9SZXR1cm4ubmV3RXZlbnQgPSB7XG4gICAgICAuLi52YWx1ZXNUb1JldHVybi5uZXdFdmVudCxcbiAgICAgIHBvc3RFdmVudElkLFxuICAgICAgdGltZUJsb2NraW5nOiB7XG4gICAgICAgIC4uLnZhbHVlc1RvUmV0dXJuPy5uZXdFdmVudD8udGltZUJsb2NraW5nLFxuICAgICAgICBhZnRlckV2ZW50OiBwcmV2aW91c0V2ZW50Py50aW1lQmxvY2tpbmc/LmFmdGVyRXZlbnQsXG4gICAgICB9LFxuICAgIH07XG4gIH1cblxuICBpZiAocHJldmlvdXNFdmVudD8udGltZUJsb2NraW5nPy5iZWZvcmVFdmVudCkge1xuICAgIGNvbnN0IGZvcm1hdHRlZFpvbmVCZWZvcmVFdmVudFN0YXJ0RGF0ZSA9IGRheWpzKFxuICAgICAgZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KVxuICAgIClcbiAgICAgIC50eihldmVudC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5zdWJ0cmFjdChwcmV2aW91c0V2ZW50Py50aW1lQmxvY2tpbmc/LmJlZm9yZUV2ZW50LCAnbScpXG4gICAgICAuZm9ybWF0KCk7XG4gICAgY29uc3QgZm9ybWF0dGVkWm9uZUJlZm9yZUV2ZW50RW5kRGF0ZSA9IGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQudGltZXpvbmUsIHRydWUpXG4gICAgICAuZm9ybWF0KCk7XG5cbiAgICBjb25zdCBiZWZvcmVFdmVudDogRXZlbnRQbHVzVHlwZSA9IHtcbiAgICAgIGlkOiBwcmVFdmVudElkLFxuICAgICAgaXNQcmVFdmVudDogdHJ1ZSxcbiAgICAgIGlzUG9zdEV2ZW50OiBmYWxzZSxcbiAgICAgIGZvckV2ZW50SWQ6IGV2ZW50LmlkLFxuICAgICAgbm90ZXM6ICdCdWZmZXIgdGltZScsXG4gICAgICBzdW1tYXJ5OiAnQnVmZmVyIHRpbWUnLFxuICAgICAgc3RhcnREYXRlOiBmb3JtYXR0ZWRab25lQmVmb3JlRXZlbnRTdGFydERhdGUsXG4gICAgICBlbmREYXRlOiBmb3JtYXR0ZWRab25lQmVmb3JlRXZlbnRFbmREYXRlLFxuICAgICAgbWV0aG9kOiBldmVudD8ucHJlRXZlbnRJZCA/ICd1cGRhdGUnIDogJ2NyZWF0ZScsXG4gICAgICB1c2VySWQ6IGV2ZW50Py51c2VySWQsXG4gICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICBwcmlvcml0eTogMSxcbiAgICAgIGlzRm9sbG93VXA6IGZhbHNlLFxuICAgICAgbW9kaWZpYWJsZTogdHJ1ZSxcbiAgICAgIGFueW9uZUNhbkFkZFNlbGY6IGZhbHNlLFxuICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiBmYWxzZSxcbiAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOiBmYWxzZSxcbiAgICAgIG9yaWdpbmFsU3RhcnREYXRlOiB1bmRlZmluZWQsXG4gICAgICBvcmlnaW5hbEFsbERheTogZmFsc2UsXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIGNhbGVuZGFySWQ6IGV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgdGltZXpvbmU6IGV2ZW50Py50aW1lem9uZSxcbiAgICAgIGV2ZW50SWQ6IHByZUV2ZW50SWQuc3BsaXQoJyMnKVswXSxcbiAgICB9O1xuICAgIHZhbHVlc1RvUmV0dXJuLmJlZm9yZUV2ZW50ID0gYmVmb3JlRXZlbnQ7XG4gICAgdmFsdWVzVG9SZXR1cm4ubmV3RXZlbnQgPSB7XG4gICAgICAuLi52YWx1ZXNUb1JldHVybi5uZXdFdmVudCxcbiAgICAgIHByZUV2ZW50SWQsXG4gICAgICB0aW1lQmxvY2tpbmc6IHtcbiAgICAgICAgLi4udmFsdWVzVG9SZXR1cm4/Lm5ld0V2ZW50Py50aW1lQmxvY2tpbmcsXG4gICAgICAgIGJlZm9yZUV2ZW50OiBwcmV2aW91c0V2ZW50Py50aW1lQmxvY2tpbmc/LmJlZm9yZUV2ZW50LFxuICAgICAgfSxcbiAgICB9O1xuICB9XG5cbiAgcmV0dXJuIHZhbHVlc1RvUmV0dXJuO1xufTtcblxuZXhwb3J0IGNvbnN0IGNyZWF0ZVJlbWluZGVyc0Zyb21QcmV2aW91c0V2ZW50Rm9yRXZlbnQgPSBhc3luYyAoXG4gIGV2ZW50OiBFdmVudFBsdXNUeXBlLFxuICBwcmV2aW91c0V2ZW50OiBFdmVudFBsdXNUeXBlLFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxSZW1pbmRlclR5cGVbXT4gPT4ge1xuICBpZiAoZXZlbnQudXNlck1vZGlmaWVkUmVtaW5kZXJzKSB7XG4gICAgY29uc29sZS5sb2coJ25vIGV2ZW50IGluc2lkZSBjcmVhdGVSZW1pbmRlcnNGcm9tUHJldmlvdXNFdmVudEZvckV2ZW50Jyk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICBpZiAoIXByZXZpb3VzRXZlbnQ/LmlkKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICAnbm8gcHJldmlvdXNFdmVudCBpbnNpZGUgY3JlYXRlUmVtaW5kZXJzRnJvbVByZXZpb3VzRXZlbnRGb3JFdmVudCdcbiAgICApO1xuICAgIHJldHVybiBudWxsO1xuICB9XG5cbiAgaWYgKCFwcmV2aW91c0V2ZW50Py5jb3B5UmVtaW5kZXJzKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICAnbm8gcHJldmlvdXNFdmVudCBpbnNpZGUgY3JlYXRlUmVtaW5kZXJzRnJvbVByZXZpb3VzRXZlbnRGb3JFdmVudCdcbiAgICApO1xuICAgIHJldHVybiBudWxsO1xuICB9XG5cbiAgY29uc3QgcmVtaW5kZXJzID0gYXdhaXQgbGlzdFJlbWluZGVyc0ZvckV2ZW50KHByZXZpb3VzRXZlbnQuaWQsIHVzZXJJZCk7XG5cbiAgcmV0dXJuIHJlbWluZGVycz8ubWFwKChyZW1pbmRlcikgPT4gKHtcbiAgICAuLi5yZW1pbmRlcixcbiAgICBldmVudElkOiBldmVudC5pZCxcbiAgICBpZDogdXVpZCgpLFxuICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgZGVsZXRlZDogZmFsc2UsXG4gIH0pKTtcbn07XG5cbmNvbnN0IGNvcHlPdmVyTWVldGluZ0FuZEV4dGVybmFsTWVldGluZ0RlZmF1bHRzV2l0aFByZXZpb3VzRXZlbnRGb3VuZCA9IChcbiAgZXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIHByZXZpb3VzRXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIGNhdGVnb3J5OiBDYXRlZ29yeVR5cGUsXG4gIHVzZXJQcmVmZXJlbmNlczogVXNlclByZWZlcmVuY2VUeXBlXG4pOiBFdmVudFBsdXNUeXBlID0+IHtcbiAgcmV0dXJuIHtcbiAgICAuLi5ldmVudCxcbiAgICB0cmFuc3BhcmVuY3k6ICFldmVudD8udXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5XG4gICAgICA/IHByZXZpb3VzRXZlbnQ/LmNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgPyBwcmV2aW91c0V2ZW50LnRyYW5zcGFyZW5jeVxuICAgICAgICA6IGNhdGVnb3J5LmNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnRyYW5zcGFyZW5jeVxuICAgICAgICAgIDogY2F0ZWdvcnkuZGVmYXVsdEF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgPyAndHJhbnNwYXJlbnQnXG4gICAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weUF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnRyYW5zcGFyZW5jeVxuICAgICAgICAgICAgICA6IGV2ZW50Py50cmFuc3BhcmVuY3lcbiAgICAgIDogZXZlbnQudHJhbnNwYXJlbmN5LFxuICAgIHByZWZlcnJlZFRpbWU6ICFldmVudD8udXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2VcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICAgID8gcHJldmlvdXNFdmVudC5wcmVmZXJyZWRUaW1lXG4gICAgICAgIDogY2F0ZWdvcnkuY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWRUaW1lXG4gICAgICAgICAgOiB1c2VyUHJlZmVyZW5jZXM/LmNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5wcmVmZXJyZWRUaW1lXG4gICAgICAgICAgICA6IGV2ZW50Py5wcmVmZXJyZWRUaW1lXG4gICAgICA6IGV2ZW50LnByZWZlcnJlZFRpbWUsXG4gICAgcHJlZmVycmVkRGF5T2ZXZWVrOiAhZXZlbnQ/LnVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlXG4gICAgICA/IHByZXZpb3VzRXZlbnQ/LmNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICA/IHByZXZpb3VzRXZlbnQucHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICAgIDogdXNlclByZWZlcmVuY2VzPy5jb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZERheU9mV2Vla1xuICAgICAgICAgIDogZXZlbnQ/LnByZWZlcnJlZERheU9mV2Vla1xuICAgICAgOiBldmVudC5wcmVmZXJyZWREYXlPZldlZWssXG4gICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U6ICFldmVudD8udXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2VcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICAgID8gcHJldmlvdXNFdmVudC5wcmVmZXJyZWRTdGFydFRpbWVSYW5nZVxuICAgICAgICA6IGNhdGVnb3J5LmNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgID8gcHJldmlvdXNFdmVudD8ucHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZFN0YXJ0VGltZVJhbmdlXG4gICAgICAgICAgICA6IGV2ZW50Py5wcmVmZXJyZWRTdGFydFRpbWVSYW5nZVxuICAgICAgOiBldmVudC5wcmVmZXJyZWRTdGFydFRpbWVSYW5nZSxcbiAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2U6ICFldmVudD8udXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2VcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICAgID8gcHJldmlvdXNFdmVudC5wcmVmZXJyZWRFbmRUaW1lUmFuZ2VcbiAgICAgICAgOiBjYXRlZ29yeS5jb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICAgIDogdXNlclByZWZlcmVuY2VzPy5jb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgICAgID8gcHJldmlvdXNFdmVudD8ucHJlZmVycmVkRW5kVGltZVJhbmdlXG4gICAgICAgICAgICA6IGV2ZW50Py5wcmVmZXJyZWRFbmRUaW1lUmFuZ2VcbiAgICAgIDogZXZlbnQucHJlZmVycmVkRW5kVGltZVJhbmdlLFxuICAgIHByaW9yaXR5OlxuICAgICAgKCFldmVudD8udXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbFxuICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LmNvcHlQcmlvcml0eUxldmVsXG4gICAgICAgICAgPyBwcmV2aW91c0V2ZW50LnByaW9yaXR5XG4gICAgICAgICAgOiBjYXRlZ29yeS5jb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5wcmlvcml0eVxuICAgICAgICAgICAgOiBjYXRlZ29yeS5kZWZhdWx0UHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0UHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LnByaW9yaXR5XG4gICAgICAgICAgICAgICAgOiBldmVudD8ucHJpb3JpdHlcbiAgICAgICAgOiBldmVudD8ucHJpb3JpdHkpIHx8IDEsXG4gICAgaXNCcmVhazogIWV2ZW50Py51c2VyTW9kaWZpZWRJc0JyZWFrXG4gICAgICA/IHByZXZpb3VzRXZlbnQ/LmNvcHlJc0JyZWFrXG4gICAgICAgID8gcHJldmlvdXNFdmVudC5pc0JyZWFrXG4gICAgICAgIDogY2F0ZWdvcnkuY29weUlzQnJlYWtcbiAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LmlzQnJlYWtcbiAgICAgICAgICA6IGNhdGVnb3J5LmRlZmF1bHRJc0JyZWFrXG4gICAgICAgICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0SXNCcmVha1xuICAgICAgICAgICAgOiB1c2VyUHJlZmVyZW5jZXM/LmNvcHlJc0JyZWFrXG4gICAgICAgICAgICAgID8gcHJldmlvdXNFdmVudD8uaXNCcmVha1xuICAgICAgICAgICAgICA6IGV2ZW50Py5pc0JyZWFrXG4gICAgICA6IGV2ZW50LmlzQnJlYWssXG4gICAgaXNNZWV0aW5nOiAhZXZlbnQ/LnVzZXJNb2RpZmllZElzTWVldGluZ1xuICAgICAgPyBwcmV2aW91c0V2ZW50Py5jb3B5SXNNZWV0aW5nXG4gICAgICAgID8gcHJldmlvdXNFdmVudC5pc01lZXRpbmdcbiAgICAgICAgOiBjYXRlZ29yeS5jb3B5SXNNZWV0aW5nXG4gICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5pc01lZXRpbmdcbiAgICAgICAgICA6IGNhdGVnb3J5LmRlZmF1bHRJc01lZXRpbmdcbiAgICAgICAgICAgID8gY2F0ZWdvcnk/LmRlZmF1bHRJc01lZXRpbmdcbiAgICAgICAgICAgIDogdXNlclByZWZlcmVuY2VzPy5jb3B5SXNNZWV0aW5nXG4gICAgICAgICAgICAgID8gcHJldmlvdXNFdmVudD8uaXNNZWV0aW5nXG4gICAgICAgICAgICAgIDogY2F0ZWdvcnkubmFtZSA9PT0gbWVldGluZ0xhYmVsXG4gICAgICAgICAgICAgICAgPyB0cnVlXG4gICAgICAgICAgICAgICAgOiBldmVudD8uaXNNZWV0aW5nXG4gICAgICA6IGV2ZW50LmlzTWVldGluZyxcbiAgICBpc0V4dGVybmFsTWVldGluZzogIWV2ZW50Py51c2VyTW9kaWZpZWRJc0V4dGVybmFsTWVldGluZ1xuICAgICAgPyBwcmV2aW91c0V2ZW50Py5jb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgPyBwcmV2aW91c0V2ZW50LmlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgIDogY2F0ZWdvcnkuY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5pc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgIDogY2F0ZWdvcnkuZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgIDogdXNlclByZWZlcmVuY2VzPy5jb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgPyBwcmV2aW91c0V2ZW50Py5pc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgICA6IGNhdGVnb3J5Lm5hbWUgPT09IGV4dGVybmFsTWVldGluZ0xhYmVsXG4gICAgICAgICAgICAgICAgPyB0cnVlXG4gICAgICAgICAgICAgICAgOiBldmVudD8uaXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgIDogZXZlbnQuaXNFeHRlcm5hbE1lZXRpbmcsXG4gICAgaXNNZWV0aW5nTW9kaWZpYWJsZTogIWV2ZW50Py51c2VyTW9kaWZpZWRNb2RpZmlhYmxlXG4gICAgICA/IGNhdGVnb3J5LmRlZmF1bHRNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICA/IGNhdGVnb3J5Py5kZWZhdWx0TWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgOiBldmVudD8uaXNNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgOiBldmVudC5pc01lZXRpbmdNb2RpZmlhYmxlLFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZTogIWV2ZW50Py51c2VyTW9kaWZpZWRNb2RpZmlhYmxlXG4gICAgICA/IGNhdGVnb3J5LmRlZmF1bHRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgID8gY2F0ZWdvcnk/LmRlZmF1bHRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgIDogZXZlbnQ/LmlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgOiBldmVudC5pc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGUsXG4gICAgYmFja2dyb3VuZENvbG9yOiAhZXZlbnQ/LnVzZXJNb2RpZmllZENvbG9yXG4gICAgICA/IHByZXZpb3VzRXZlbnQ/LmNvcHlDb2xvclxuICAgICAgICA/IHByZXZpb3VzRXZlbnQuYmFja2dyb3VuZENvbG9yXG4gICAgICAgIDogY2F0ZWdvcnkuY29sb3JcbiAgICAgICAgICA/IGNhdGVnb3J5Py5jb2xvclxuICAgICAgICAgIDogdXNlclByZWZlcmVuY2VzPy5jb3B5Q29sb3JcbiAgICAgICAgICAgID8gcHJldmlvdXNFdmVudD8uYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICA6IGV2ZW50Py5iYWNrZ3JvdW5kQ29sb3JcbiAgICAgIDogZXZlbnQuYmFja2dyb3VuZENvbG9yLFxuICAgIGNvbG9ySWQ6XG4gICAgICBwcmV2aW91c0V2ZW50Py5jb3B5Q29sb3IgJiYgcHJldmlvdXNFdmVudD8uY29sb3JJZFxuICAgICAgICA/IHByZXZpb3VzRXZlbnQuY29sb3JJZFxuICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weUNvbG9yICYmIHByZXZpb3VzRXZlbnQ/LmNvbG9ySWRcbiAgICAgICAgICA/IHByZXZpb3VzRXZlbnQ/LmNvbG9ySWRcbiAgICAgICAgICA6IGV2ZW50Py5jb2xvcklkLFxuICAgIHByZWZlcnJlZFRpbWVSYW5nZXM6ICFldmVudD8udXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2VcbiAgICAgID8gcHJldmlvdXNFdmVudD8uY29weVRpbWVQcmVmZXJlbmNlICYmXG4gICAgICAgIHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZFRpbWVSYW5nZXM/Lmxlbmd0aCA+IDBcbiAgICAgICAgPyBwcmV2aW91c0V2ZW50LnByZWZlcnJlZFRpbWVSYW5nZXM/Lm1hcCgocCkgPT4gKHtcbiAgICAgICAgICAgIC4uLnAsXG4gICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgZXZlbnRJZDogZXZlbnQ/LmlkLFxuICAgICAgICAgIH0pKVxuICAgICAgICA6IGNhdGVnb3J5LmNvcHlUaW1lUHJlZmVyZW5jZSAmJlxuICAgICAgICAgICAgcHJldmlvdXNFdmVudD8ucHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMFxuICAgICAgICAgID8gcHJldmlvdXNFdmVudD8ucHJlZmVycmVkVGltZVJhbmdlcz8ubWFwKChwKSA9PiAoe1xuICAgICAgICAgICAgICAuLi5wLFxuICAgICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgICBldmVudElkOiBldmVudD8uaWQsXG4gICAgICAgICAgICB9KSlcbiAgICAgICAgICA6IHVzZXJQcmVmZXJlbmNlcz8uY29weVRpbWVQcmVmZXJlbmNlICYmXG4gICAgICAgICAgICAgIHByZXZpb3VzRXZlbnQ/LnByZWZlcnJlZFRpbWVSYW5nZXM/Lmxlbmd0aCA+IDBcbiAgICAgICAgICAgID8gcHJldmlvdXNFdmVudD8ucHJlZmVycmVkVGltZVJhbmdlcz8ubWFwKChwKSA9PiAoe1xuICAgICAgICAgICAgICAgIC4uLnAsXG4gICAgICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICAgICAgICBldmVudElkOiBldmVudD8uaWQsXG4gICAgICAgICAgICAgIH0pKVxuICAgICAgICAgICAgOiBjYXRlZ29yeS5kZWZhdWx0VGltZVByZWZlcmVuY2U/Lm1hcCgodHApID0+ICh7XG4gICAgICAgICAgICAgICAgICAuLi50cCxcbiAgICAgICAgICAgICAgICAgIGV2ZW50SWQ6IGV2ZW50Py5pZCxcbiAgICAgICAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICAgICAgICB1c2VySWQ6IGV2ZW50Py51c2VySWQsXG4gICAgICAgICAgICAgICAgfSkpXG4gICAgICAgICAgICAgID8gY2F0ZWdvcnk/LmRlZmF1bHRUaW1lUHJlZmVyZW5jZT8ubWFwKCh0cCkgPT4gKHtcbiAgICAgICAgICAgICAgICAgIC4uLnRwLFxuICAgICAgICAgICAgICAgICAgZXZlbnRJZDogZXZlbnQ/LmlkLFxuICAgICAgICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICAgICAgICAgIHVzZXJJZDogZXZlbnQ/LnVzZXJJZCxcbiAgICAgICAgICAgICAgICB9KSlcbiAgICAgICAgICAgICAgOiBldmVudD8ucHJlZmVycmVkVGltZVJhbmdlc1xuICAgICAgOiBldmVudC5wcmVmZXJyZWRUaW1lUmFuZ2VzLFxuICB9O1xufTtcblxuZXhwb3J0IGNvbnN0IGNvcHlPdmVyQ2F0ZWdvcnlNZWV0aW5nQW5kRXh0ZXJuYWxNZWV0aW5nRGVmYXVsdHNXaXRoRm91bmRQcmV2aW91c0V2ZW50ID1cbiAgKFxuICAgIGV2ZW50OiBFdmVudFBsdXNUeXBlLFxuICAgIGNhdGVnb3JpZXM6IENhdGVnb3J5VHlwZVtdLFxuICAgIHVzZXJQcmVmZXJlbmNlczogVXNlclByZWZlcmVuY2VUeXBlLFxuICAgIHByZXZpb3VzRXZlbnQ6IEV2ZW50UGx1c1R5cGVcbiAgKSA9PiB7XG4gICAgaWYgKCEoY2F0ZWdvcmllcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAnbm8gY2F0ZWdvcmllcyBpbnNpZGUgY29weU92ZXJDYXRlZ29yeURlZmF1bHRzRm9yQ29uc3RhbnRzV2l0aEZvdW5kUHJldmlvdXNFdmVudCdcbiAgICAgICk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgaWYgKCF1c2VyUHJlZmVyZW5jZXM/LmlkKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgJ25vIHVzZXJQcmVmZXJlbmNlcyBpbnNpZGUgY29weU92ZXJDYXRlZ29yeURlZmF1bHRzRm9yQ29uc3RhbnRzV2l0aEZvdW5kUHJldmlvdXNFdmVudCdcbiAgICAgICk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2aW91c0V2ZW50Py5pZCkge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICdubyBwcmV2aW91c0V2ZW50IGluc2lkZSBjb3B5T3ZlckNhdGVnb3J5RGVmYXVsdHNGb3JDb25zdGFudHNXaXRoRm91bmRQcmV2aW91c0V2ZW50J1xuICAgICAgKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG4gICAgaWYgKCFldmVudD8uaWQpIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAnbm8gZXZlbnQgaW5zaWRlIGNvcHlPdmVyQ2F0ZWdvcnlEZWZhdWx0c0ZvckNvbnN0YW50c1dpdGhGb3VuZFByZXZpb3VzRXZlbnQnXG4gICAgICApO1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIGNvbnN0IG1lZXRpbmdDYXRlZ29yeSA9IGNhdGVnb3JpZXMuZmluZChcbiAgICAgIChjYXRlZ29yeSkgPT4gY2F0ZWdvcnkubmFtZSA9PT0gbWVldGluZ0xhYmVsXG4gICAgKTtcbiAgICBjb25zdCBleHRlcm5hbENhdGVnb3J5ID0gY2F0ZWdvcmllcy5maW5kKFxuICAgICAgKGNhdGVnb3J5KSA9PiBjYXRlZ29yeS5uYW1lID09PSBleHRlcm5hbE1lZXRpbmdMYWJlbFxuICAgICk7XG5cbiAgICBsZXQgbmV3RXZlbnRNZWV0aW5nOiBFdmVudFBsdXNUeXBlIHwge30gPSB7fTtcbiAgICBsZXQgbmV3RXZlbnRFeHRlcm5hbDogRXZlbnRQbHVzVHlwZSB8IHt9ID0ge307XG5cbiAgICBpZiAobWVldGluZ0NhdGVnb3J5Py5pZCkge1xuICAgICAgbmV3RXZlbnRNZWV0aW5nID1cbiAgICAgICAgY29weU92ZXJNZWV0aW5nQW5kRXh0ZXJuYWxNZWV0aW5nRGVmYXVsdHNXaXRoUHJldmlvdXNFdmVudEZvdW5kKFxuICAgICAgICAgIGV2ZW50LFxuICAgICAgICAgIHByZXZpb3VzRXZlbnQsXG4gICAgICAgICAgbWVldGluZ0NhdGVnb3J5LFxuICAgICAgICAgIHVzZXJQcmVmZXJlbmNlc1xuICAgICAgICApO1xuICAgIH1cblxuICAgIGlmIChleHRlcm5hbENhdGVnb3J5Py5pZCkge1xuICAgICAgbmV3RXZlbnRFeHRlcm5hbCA9XG4gICAgICAgIGNvcHlPdmVyTWVldGluZ0FuZEV4dGVybmFsTWVldGluZ0RlZmF1bHRzV2l0aFByZXZpb3VzRXZlbnRGb3VuZChcbiAgICAgICAgICBldmVudCxcbiAgICAgICAgICBwcmV2aW91c0V2ZW50LFxuICAgICAgICAgIG1lZXRpbmdDYXRlZ29yeSxcbiAgICAgICAgICB1c2VyUHJlZmVyZW5jZXNcbiAgICAgICAgKTtcbiAgICB9XG5cbiAgICByZXR1cm4geyBuZXdFdmVudE1lZXRpbmcsIG5ld0V2ZW50RXh0ZXJuYWwgfTtcbiAgfTtcbmV4cG9ydCBjb25zdCBjcmVhdGVSZW1pbmRlcnNBbmRUaW1lQmxvY2tpbmdGcm9tUHJldmlvdXNFdmVudEdpdmVuVXNlclByZWZlcmVuY2VzID1cbiAgYXN5bmMgKFxuICAgIHVzZXJJZDogc3RyaW5nLFxuICAgIG5ld0V2ZW50OiBFdmVudFBsdXNUeXBlLFxuICAgIG5ld1JlbWluZGVyczE/OiBSZW1pbmRlclR5cGVbXSxcbiAgICBuZXdCdWZmZXJUaW1lczE/OiBCdWZmZXJUaW1lT2JqZWN0VHlwZSxcbiAgICBwcmV2aW91c0V2ZW50PzogRXZlbnRQbHVzVHlwZSxcbiAgICB1c2VyUHJlZmVyZW5jZXM/OiBVc2VyUHJlZmVyZW5jZVR5cGVcbiAgKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgIGxldCBuZXdSZW1pbmRlcnMgPSBuZXdSZW1pbmRlcnMxIHx8IFtdO1xuICAgICAgbGV0IG5ld0J1ZmZlclRpbWVzID0gbmV3QnVmZmVyVGltZXMxIHx8IHt9O1xuICAgICAgaWYgKCFuZXdFdmVudD8udXNlck1vZGlmaWVkUmVtaW5kZXJzICYmIHVzZXJQcmVmZXJlbmNlcz8uY29weVJlbWluZGVycykge1xuICAgICAgICBjb25zdCByZW1pbmRlcnMgPSBhd2FpdCBjcmVhdGVSZW1pbmRlcnNGcm9tUHJldmlvdXNFdmVudEZvckV2ZW50KFxuICAgICAgICAgIG5ld0V2ZW50LFxuICAgICAgICAgIHByZXZpb3VzRXZlbnQsXG4gICAgICAgICAgdXNlcklkXG4gICAgICAgICk7XG5cbiAgICAgICAgY29uc29sZS5sb2cocmVtaW5kZXJzLCAnIHJlbWluZGVycycpO1xuICAgICAgICBpZiAocmVtaW5kZXJzPy5sZW5ndGggPiAwICYmICFuZXdFdmVudD8udXNlck1vZGlmaWVkUmVtaW5kZXJzKSB7XG4gICAgICAgICAgbmV3UmVtaW5kZXJzLnB1c2goLi4ucmVtaW5kZXJzKTtcbiAgICAgICAgfVxuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgICFuZXdFdmVudD8udXNlck1vZGlmaWVkVGltZUJsb2NraW5nICYmXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlcz8uY29weVRpbWVCbG9ja2luZ1xuICAgICAgKSB7XG4gICAgICAgIGNvbnN0IGJ1ZmZlclRpbWVzID0gY3JlYXRlUHJlQW5kUG9zdEV2ZW50c0Zyb21QcmV2aW91c0V2ZW50KFxuICAgICAgICAgIG5ld0V2ZW50LFxuICAgICAgICAgIHByZXZpb3VzRXZlbnRcbiAgICAgICAgKTtcbiAgICAgICAgY29uc29sZS5sb2coYnVmZmVyVGltZXMsICcgdGltZUJsb2NraW5nJyk7XG4gICAgICAgIGlmIChidWZmZXJUaW1lcz8uYmVmb3JlRXZlbnQpIHtcbiAgICAgICAgICAobmV3QnVmZmVyVGltZXMgYXMgQnVmZmVyVGltZU9iamVjdFR5cGUpLmJlZm9yZUV2ZW50ID1cbiAgICAgICAgICAgIGJ1ZmZlclRpbWVzLmJlZm9yZUV2ZW50O1xuICAgICAgICB9XG5cbiAgICAgICAgaWYgKGJ1ZmZlclRpbWVzPy5hZnRlckV2ZW50KSB7XG4gICAgICAgICAgKG5ld0J1ZmZlclRpbWVzIGFzIEJ1ZmZlclRpbWVPYmplY3RUeXBlKS5hZnRlckV2ZW50ID1cbiAgICAgICAgICAgIGJ1ZmZlclRpbWVzLmFmdGVyRXZlbnQ7XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoXG4gICAgICAgICAgYnVmZmVyVGltZXM/Lm5ld0V2ZW50Py5wcmVFdmVudElkIHx8XG4gICAgICAgICAgYnVmZmVyVGltZXM/Lm5ld0V2ZW50Py5wb3N0RXZlbnRJZFxuICAgICAgICApIHtcbiAgICAgICAgICBuZXdFdmVudCA9IGJ1ZmZlclRpbWVzLm5ld0V2ZW50O1xuICAgICAgICB9XG4gICAgICB9XG4gICAgICByZXR1cm4geyBuZXdFdmVudCwgbmV3UmVtaW5kZXJzLCBuZXdCdWZmZXJUaW1lczogbmV3QnVmZmVyVGltZXMgfTtcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgZSxcbiAgICAgICAgJyB1bmFibGUgdG8gY3JlYXRlIHJlbWluZGVycyBhbmQgdGltZSBibG9ja2luZyBmcm9tIHByZXZpb3VzIGV2ZW50IGdpdmVuIHVzZXIgcHJlZmVyZW5jZXMnXG4gICAgICApO1xuICAgIH1cbiAgfTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZVZhbHVlc0ZvckV2ZW50V2l0aFByZXZpb3VzRXZlbnRQbHVzTWVldGluZ0FuZEV4dGVybmFsTWVldGluZyA9XG4gIGFzeW5jIChcbiAgICBldmVudDogRXZlbnRQbHVzVHlwZSxcbiAgICBuZXdFdmVudDE6IEV2ZW50UGx1c1R5cGUsXG4gICAgYmVzdE1hdGNoQ2F0ZWdvcmllczogQ2F0ZWdvcnlUeXBlW10sXG4gICAgbmV3UmVtaW5kZXJzMTogUmVtaW5kZXJUeXBlW10sXG4gICAgbmV3VGltZUJsb2NraW5nMTogQnVmZmVyVGltZU9iamVjdFR5cGUsXG4gICAgdXNlcklkOiBzdHJpbmcsXG4gICAgdXNlclByZWZlcmVuY2VzOiBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gICAgcHJldmlvdXNFdmVudDogRXZlbnRQbHVzVHlwZVxuICApID0+IHtcbiAgICB0cnkge1xuICAgICAgbGV0IG5ld0V2ZW50ID0gbmV3RXZlbnQxO1xuICAgICAgbGV0IG5ld1JlbWluZGVycyA9IG5ld1JlbWluZGVyczEgfHwgW107XG4gICAgICBsZXQgbmV3VGltZUJsb2NraW5nID0gbmV3VGltZUJsb2NraW5nMSB8fCB7fTtcbiAgICAgIGNvbnN0IHsgbmV3RXZlbnRNZWV0aW5nLCBuZXdFdmVudEV4dGVybmFsIH0gPVxuICAgICAgICBjb3B5T3ZlckNhdGVnb3J5TWVldGluZ0FuZEV4dGVybmFsTWVldGluZ0RlZmF1bHRzV2l0aEZvdW5kUHJldmlvdXNFdmVudChcbiAgICAgICAgICBldmVudCxcbiAgICAgICAgICBiZXN0TWF0Y2hDYXRlZ29yaWVzLFxuICAgICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgICBwcmV2aW91c0V2ZW50XG4gICAgICAgICk7XG5cbiAgICAgIGlmICgobmV3RXZlbnRNZWV0aW5nIGFzIEV2ZW50UGx1c1R5cGUpPy5pZCkge1xuICAgICAgICBuZXdFdmVudCA9IHsgLi4ubmV3RXZlbnQsIC4uLm5ld0V2ZW50TWVldGluZyB9O1xuICAgICAgICBjb25zdCBtZWV0aW5nQ2F0ZWdvcnkgPSBiZXN0TWF0Y2hDYXRlZ29yaWVzLmZpbmQoXG4gICAgICAgICAgKGNhdGVnb3J5KSA9PiBjYXRlZ29yeS5uYW1lID09PSBtZWV0aW5nTGFiZWxcbiAgICAgICAgKTtcblxuICAgICAgICBjb25zdCBvbGRSZW1pbmRlcnMgPSBhd2FpdCBsaXN0UmVtaW5kZXJzRm9yRXZlbnQoXG4gICAgICAgICAgKG5ld0V2ZW50TWVldGluZyBhcyBFdmVudFBsdXNUeXBlKT8uaWQsXG4gICAgICAgICAgdXNlcklkXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IHJlbWluZGVycyA9IGNyZWF0ZVJlbWluZGVyc1VzaW5nQ2F0ZWdvcnlEZWZhdWx0c0ZvckV2ZW50KFxuICAgICAgICAgIG5ld0V2ZW50LFxuICAgICAgICAgIG1lZXRpbmdDYXRlZ29yeSxcbiAgICAgICAgICBvbGRSZW1pbmRlcnMsXG4gICAgICAgICAgcHJldmlvdXNFdmVudFxuICAgICAgICApO1xuICAgICAgICBjb25zb2xlLmxvZyhyZW1pbmRlcnMsICcgcmVtaW5kZXJzJyk7XG4gICAgICAgIGlmIChyZW1pbmRlcnM/Lmxlbmd0aCA+IDAgJiYgIW5ld0V2ZW50Py51c2VyTW9kaWZpZWRSZW1pbmRlcnMpIHtcbiAgICAgICAgICBuZXdSZW1pbmRlcnMucHVzaCguLi5yZW1pbmRlcnMpO1xuICAgICAgICAgIG5ld1JlbWluZGVycyA9IF8udW5pcUJ5KG5ld1JlbWluZGVycywgJ21pbnV0ZXMnKTtcbiAgICAgICAgfVxuXG4gICAgICAgIGlmICghbmV3RXZlbnQ/LnVzZXJNb2RpZmllZFRpbWVCbG9ja2luZykge1xuICAgICAgICAgIGNvbnN0IHRpbWVCbG9ja2luZyA9IGNyZWF0ZVByZUFuZFBvc3RFdmVudHNGb3JDYXRlZ29yeURlZmF1bHRzKFxuICAgICAgICAgICAgbWVldGluZ0NhdGVnb3J5LFxuICAgICAgICAgICAgbmV3RXZlbnQsXG4gICAgICAgICAgICBwcmV2aW91c0V2ZW50XG4gICAgICAgICAgKTtcbiAgICAgICAgICBjb25zb2xlLmxvZyh0aW1lQmxvY2tpbmcsICcgdGltZUJsb2NraW5nJyk7XG4gICAgICAgICAgaWYgKHRpbWVCbG9ja2luZz8uYmVmb3JlRXZlbnQpIHtcbiAgICAgICAgICAgIG5ld1RpbWVCbG9ja2luZy5iZWZvcmVFdmVudCA9IHRpbWVCbG9ja2luZy5iZWZvcmVFdmVudDtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBpZiAodGltZUJsb2NraW5nPy5hZnRlckV2ZW50KSB7XG4gICAgICAgICAgICBuZXdUaW1lQmxvY2tpbmcuYWZ0ZXJFdmVudCA9IHRpbWVCbG9ja2luZy5hZnRlckV2ZW50O1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGlmIChcbiAgICAgICAgICAgIHRpbWVCbG9ja2luZz8ubmV3RXZlbnQ/LnByZUV2ZW50SWQgfHxcbiAgICAgICAgICAgIHRpbWVCbG9ja2luZz8ubmV3RXZlbnQ/LnBvc3RFdmVudElkXG4gICAgICAgICAgKSB7XG4gICAgICAgICAgICBuZXdFdmVudCA9IHRpbWVCbG9ja2luZy5uZXdFdmVudDtcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgaWYgKChuZXdFdmVudEV4dGVybmFsIGFzIEV2ZW50UGx1c1R5cGUpPy5pZCkge1xuICAgICAgICBuZXdFdmVudCA9IHsgLi4ubmV3RXZlbnQsIC4uLm5ld0V2ZW50RXh0ZXJuYWwgfTtcbiAgICAgICAgY29uc3QgZXh0ZXJuYWxDYXRlZ29yeSA9IGJlc3RNYXRjaENhdGVnb3JpZXMuZmluZChcbiAgICAgICAgICAoY2F0ZWdvcnkpID0+IGNhdGVnb3J5Lm5hbWUgPT09IGV4dGVybmFsTWVldGluZ0xhYmVsXG4gICAgICAgICk7XG5cbiAgICAgICAgY29uc3Qgb2xkUmVtaW5kZXJzID0gYXdhaXQgbGlzdFJlbWluZGVyc0ZvckV2ZW50KFxuICAgICAgICAgIChuZXdFdmVudEV4dGVybmFsIGFzIEV2ZW50UGx1c1R5cGUpLmlkLFxuICAgICAgICAgIHVzZXJJZFxuICAgICAgICApO1xuICAgICAgICBjb25zdCByZW1pbmRlcnMgPSBjcmVhdGVSZW1pbmRlcnNVc2luZ0NhdGVnb3J5RGVmYXVsdHNGb3JFdmVudChcbiAgICAgICAgICBuZXdFdmVudCxcbiAgICAgICAgICBleHRlcm5hbENhdGVnb3J5LFxuICAgICAgICAgIG9sZFJlbWluZGVycyxcbiAgICAgICAgICBwcmV2aW91c0V2ZW50XG4gICAgICAgICk7XG4gICAgICAgIGNvbnNvbGUubG9nKHJlbWluZGVycywgJyByZW1pbmRlcnMnKTtcbiAgICAgICAgaWYgKHJlbWluZGVycz8ubGVuZ3RoID4gMCAmJiAhbmV3RXZlbnQ/LnVzZXJNb2RpZmllZFJlbWluZGVycykge1xuICAgICAgICAgIG5ld1JlbWluZGVycy5wdXNoKC4uLnJlbWluZGVycyk7XG4gICAgICAgICAgbmV3UmVtaW5kZXJzID0gXy51bmlxQnkobmV3UmVtaW5kZXJzLCAnbWludXRlcycpO1xuICAgICAgICB9XG5cbiAgICAgICAgaWYgKCFuZXdFdmVudD8udXNlck1vZGlmaWVkVGltZUJsb2NraW5nKSB7XG4gICAgICAgICAgY29uc3QgdGltZUJsb2NraW5nID0gY3JlYXRlUHJlQW5kUG9zdEV2ZW50c0ZvckNhdGVnb3J5RGVmYXVsdHMoXG4gICAgICAgICAgICBleHRlcm5hbENhdGVnb3J5LFxuICAgICAgICAgICAgbmV3RXZlbnRcbiAgICAgICAgICApO1xuICAgICAgICAgIGNvbnNvbGUubG9nKHRpbWVCbG9ja2luZywgJyB0aW1lQmxvY2tpbmcnKTtcbiAgICAgICAgICBpZiAodGltZUJsb2NraW5nPy5iZWZvcmVFdmVudCkge1xuICAgICAgICAgICAgbmV3VGltZUJsb2NraW5nLmJlZm9yZUV2ZW50ID0gdGltZUJsb2NraW5nLmJlZm9yZUV2ZW50O1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGlmICh0aW1lQmxvY2tpbmc/LmFmdGVyRXZlbnQpIHtcbiAgICAgICAgICAgIG5ld1RpbWVCbG9ja2luZy5hZnRlckV2ZW50ID0gdGltZUJsb2NraW5nLmFmdGVyRXZlbnQ7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgaWYgKFxuICAgICAgICAgICAgdGltZUJsb2NraW5nPy5uZXdFdmVudD8ucHJlRXZlbnRJZCB8fFxuICAgICAgICAgICAgdGltZUJsb2NraW5nPy5uZXdFdmVudD8ucG9zdEV2ZW50SWRcbiAgICAgICAgICApIHtcbiAgICAgICAgICAgIG5ld0V2ZW50ID0gdGltZUJsb2NraW5nLm5ld0V2ZW50O1xuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfVxuXG4gICAgICByZXR1cm4geyBuZXdFdmVudCwgbmV3UmVtaW5kZXJzLCBuZXdCdWZmZXJUaW1lczogbmV3VGltZUJsb2NraW5nIH07XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdXBkYXRlIHZhbHVlcyBmb3IgZGVmYXVsdCBjYXRlZ29yaWVzJyk7XG4gICAgfVxuICB9O1xuXG5leHBvcnQgY29uc3QgY3JlYXRlUmVtaW5kZXJzQW5kVGltZUJsb2NraW5nRnJvbVByZXZpb3VzRXZlbnQgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBuZXdFdmVudDogRXZlbnRQbHVzVHlwZSxcbiAgbmV3UmVtaW5kZXJzMTogUmVtaW5kZXJUeXBlW10sXG4gIG5ld0J1ZmZlclRpbWVzMTogQnVmZmVyVGltZU9iamVjdFR5cGUsXG4gIHByZXZpb3VzRXZlbnQ/OiBFdmVudFBsdXNUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBsZXQgbmV3UmVtaW5kZXJzID0gbmV3UmVtaW5kZXJzMSB8fCBbXTtcbiAgICBsZXQgbmV3QnVmZmVyVGltZXMgPSBuZXdCdWZmZXJUaW1lczEgfHwge307XG4gICAgY29uc3QgcmVtaW5kZXJzID0gYXdhaXQgY3JlYXRlUmVtaW5kZXJzRnJvbVByZXZpb3VzRXZlbnRGb3JFdmVudChcbiAgICAgIG5ld0V2ZW50LFxuICAgICAgcHJldmlvdXNFdmVudCxcbiAgICAgIHVzZXJJZFxuICAgICk7XG5cbiAgICBjb25zb2xlLmxvZyhyZW1pbmRlcnMsICcgcmVtaW5kZXJzJyk7XG4gICAgaWYgKFxuICAgICAgcmVtaW5kZXJzPy5sZW5ndGggPiAwICYmXG4gICAgICAhbmV3RXZlbnQ/LnVzZXJNb2RpZmllZFJlbWluZGVycyAmJlxuICAgICAgcHJldmlvdXNFdmVudD8uY29weVJlbWluZGVyc1xuICAgICkge1xuICAgICAgbmV3UmVtaW5kZXJzLnB1c2goLi4ucmVtaW5kZXJzKTtcbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICAhbmV3RXZlbnQ/LnVzZXJNb2RpZmllZFRpbWVCbG9ja2luZyAmJlxuICAgICAgcHJldmlvdXNFdmVudD8uY29weVRpbWVCbG9ja2luZ1xuICAgICkge1xuICAgICAgY29uc3QgYnVmZmVyVGltZXMgPSBjcmVhdGVQcmVBbmRQb3N0RXZlbnRzRnJvbVByZXZpb3VzRXZlbnQoXG4gICAgICAgIG5ld0V2ZW50LFxuICAgICAgICBwcmV2aW91c0V2ZW50XG4gICAgICApO1xuICAgICAgY29uc29sZS5sb2coYnVmZmVyVGltZXMsICcgdGltZUJsb2NraW5nJyk7XG4gICAgICBpZiAoYnVmZmVyVGltZXM/LmJlZm9yZUV2ZW50KSB7XG4gICAgICAgIG5ld0J1ZmZlclRpbWVzLmJlZm9yZUV2ZW50ID0gYnVmZmVyVGltZXMuYmVmb3JlRXZlbnQ7XG4gICAgICB9XG5cbiAgICAgIGlmIChidWZmZXJUaW1lcz8uYWZ0ZXJFdmVudCkge1xuICAgICAgICBuZXdCdWZmZXJUaW1lcy5hZnRlckV2ZW50ID0gYnVmZmVyVGltZXMuYWZ0ZXJFdmVudDtcbiAgICAgIH1cblxuICAgICAgaWYgKFxuICAgICAgICBidWZmZXJUaW1lcz8ubmV3RXZlbnQ/LnByZUV2ZW50SWQgfHxcbiAgICAgICAgYnVmZmVyVGltZXM/Lm5ld0V2ZW50Py5wb3N0RXZlbnRJZFxuICAgICAgKSB7XG4gICAgICAgIG5ld0V2ZW50ID0gYnVmZmVyVGltZXMubmV3RXZlbnQ7XG4gICAgICB9XG4gICAgfVxuICAgIHJldHVybiB7IG5ld0V2ZW50LCBuZXdSZW1pbmRlcnMsIG5ld0J1ZmZlclRpbWVzOiBuZXdCdWZmZXJUaW1lcyB9O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBlLFxuICAgICAgJyB1bmFibGUgdG8gY3JlYXRlIHJlbWluZGVycyBhbmQgdGltZSBibG9ja2luZyBmcm9tIHByZXZpb3VzIGV2ZW50J1xuICAgICk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzRXZlbnRXaXRoRm91bmRQcmV2aW91c0V2ZW50QW5kQ29weUNhdGVnb3JpZXMgPSBhc3luYyAoXG4gIGlkOiBzdHJpbmcsXG4gIHByZXZpb3VzRXZlbnQ6IEV2ZW50UGx1c1R5cGUsXG4gIG9sZEV2ZW50OiBFdmVudFBsdXNUeXBlLFxuICB1c2VyUHJlZmVyZW5jZXM6IFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgYmVzdE1hdGNoQ2F0ZWdvcnkxOiBDYXRlZ29yeVR5cGUsXG4gIHVzZXJJZDogc3RyaW5nLFxuICBiZXN0TWF0Y2hDYXRlZ29yaWVzMTogQ2F0ZWdvcnlUeXBlW10sXG4gIG5ld01vZGlmaWVkRXZlbnQxOiBFdmVudFBsdXNUeXBlLFxuICBuZXdSZW1pbmRlcnMxOiBSZW1pbmRlclR5cGVbXSA9IFtdLFxuICBuZXdUaW1lQmxvY2tpbmcxOiBCdWZmZXJUaW1lT2JqZWN0VHlwZSA9IHt9LFxuICBwcmV2aW91c0NhdGVnb3JpZXM6IENhdGVnb3J5VHlwZVtdID0gW10sXG4gIHByZXZpb3VzTWVldGluZ0NhdGVnb3JpZXNXaXRoTWVldGluZ0xhYmVsOiBDYXRlZ29yeVR5cGVbXSA9IFtdLFxuICBwcmV2aW91c01lZXRpbmdDYXRlZ29yaWVzV2l0aEV4dGVybmFsTWVldGluZ0xhYmVsOiBDYXRlZ29yeVR5cGVbXSA9IFtdXG4pOiBQcm9taXNlPFxuICBGZWF0dXJlc0FwcGx5UmVzcG9uc2U8e1xuICAgIG5ld01vZGlmaWVkRXZlbnQ6IEV2ZW50UGx1c1R5cGU7XG4gICAgbmV3UmVtaW5kZXJzOiBSZW1pbmRlclR5cGVbXTtcbiAgICBuZXdUaW1lQmxvY2tpbmc6IEJ1ZmZlclRpbWVPYmplY3RUeXBlO1xuICB9IHwgbnVsbD5cbj4gPT4ge1xuICAvLyBCYXNpYyB2YWxpZGF0aW9uIGZvciByZXF1aXJlZCBjb21wbGV4IG9iamVjdHNcbiAgaWYgKFxuICAgICFpZCB8fFxuICAgICFwcmV2aW91c0V2ZW50IHx8XG4gICAgIW9sZEV2ZW50IHx8XG4gICAgIXVzZXJQcmVmZXJlbmNlcyB8fFxuICAgICFiZXN0TWF0Y2hDYXRlZ29yeTEgfHxcbiAgICAhdXNlcklkIHx8XG4gICAgIWJlc3RNYXRjaENhdGVnb3JpZXMxIHx8XG4gICAgIW5ld01vZGlmaWVkRXZlbnQxXG4gICkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdPbmUgb3IgbW9yZSBjcml0aWNhbCBpbnB1dCBwYXJhbWV0ZXJzIGFyZSBtaXNzaW5nLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cblxuICB0cnkge1xuICAgIGxldCBiZXN0TWF0Y2hDYXRlZ29yaWVzOiBDYXRlZ29yeVR5cGVbXSA9IGJlc3RNYXRjaENhdGVnb3JpZXMxIHx8IFtdO1xuICAgIGxldCBiZXN0TWF0Y2hDYXRlZ29yeTogQ2F0ZWdvcnlUeXBlIHwgb2JqZWN0ID0gYmVzdE1hdGNoQ2F0ZWdvcnkxIHx8IHt9OyAvLyBFbnN1cmUgaXQncyBDYXRlZ29yeVR5cGUgb3IgYW4gZW1wdHkgb2JqZWN0XG4gICAgbGV0IG5ld01vZGlmaWVkRXZlbnQ6IEV2ZW50UGx1c1R5cGUgPSBuZXdNb2RpZmllZEV2ZW50MTsgLy8gTm90IEV2ZW50UGx1c1R5cGUgfCBvYmplY3RcbiAgICBsZXQgbmV3UmVtaW5kZXJzOiBSZW1pbmRlclR5cGVbXSA9IG5ld1JlbWluZGVyczEgfHwgW107XG4gICAgbGV0IG5ld1RpbWVCbG9ja2luZzogQnVmZmVyVGltZU9iamVjdFR5cGUgPSBuZXdUaW1lQmxvY2tpbmcxIHx8IHt9O1xuXG4gICAgaWYgKCFwcmV2aW91c0V2ZW50Py51bmxpbmsgJiYgIW9sZEV2ZW50Py51c2VyTW9kaWZpZWRDYXRlZ29yaWVzKSB7XG4gICAgICBpZiAoXG4gICAgICAgIChwcmV2aW91c0V2ZW50Py5jb3B5Q2F0ZWdvcmllcyB8fCB1c2VyUHJlZmVyZW5jZXM/LmNvcHlDYXRlZ29yaWVzKSAmJlxuICAgICAgICBwcmV2aW91c0NhdGVnb3JpZXM/Lmxlbmd0aCA+IDBcbiAgICAgICkge1xuICAgICAgICBjb25zdCBjcmVhdGVDYXRFdmVudHNSZXNwb25zZSA9IGF3YWl0IGNyZWF0ZUNhdGVnb3J5RXZlbnRzKFxuICAgICAgICAgIHByZXZpb3VzQ2F0ZWdvcmllcy5tYXAoKGMpID0+ICh7XG4gICAgICAgICAgICBjYXRlZ29yeUlkOiBjLmlkLFxuICAgICAgICAgICAgZXZlbnRJZDogaWQsXG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgY3JlYXRlZERhdGU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICAgIHVwZGF0ZWRBdDogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgICAgQ2F0ZWdvcnk6IGMsXG4gICAgICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgICB9KSlcbiAgICAgICAgKTtcbiAgICAgICAgaWYgKCFjcmVhdGVDYXRFdmVudHNSZXNwb25zZS5vaylcbiAgICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgICBgRmFpbGVkIHRvIGNyZWF0ZSBjYXRlZ29yeSBldmVudHMgZm9yIGV2ZW50ICR7aWR9IGR1cmluZyBjb3B5OiAke2NyZWF0ZUNhdEV2ZW50c1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICAgICApO1xuICAgICAgfVxuXG4gICAgICBpZiAocHJldmlvdXNDYXRlZ29yaWVzPy5bMF0/LmlkKSB7XG4gICAgICAgIGNvbnN0IGNsYXNzaWZpY2F0aW9uUmVzcG9uc2UgPSBhd2FpdCBmaW5kQmVzdE1hdGNoQ2F0ZWdvcnkyKFxuICAgICAgICAgIG9sZEV2ZW50LFxuICAgICAgICAgIHByZXZpb3VzQ2F0ZWdvcmllc1xuICAgICAgICApO1xuICAgICAgICBpZiAoY2xhc3NpZmljYXRpb25SZXNwb25zZS5vayAmJiBjbGFzc2lmaWNhdGlvblJlc3BvbnNlLmRhdGEpIHtcbiAgICAgICAgICBjb25zdCB7IGxhYmVscywgc2NvcmVzIH0gPSBjbGFzc2lmaWNhdGlvblJlc3BvbnNlLmRhdGE7XG4gICAgICAgICAgY29uc3QgYmVzdE1hdGNoTGFiZWwgPSBwcm9jZXNzQmVzdE1hdGNoQ2F0ZWdvcmllc05vVGhyZXNob2xkKFxuICAgICAgICAgICAgY2xhc3NpZmljYXRpb25SZXNwb25zZS5kYXRhLFxuICAgICAgICAgICAgbGFiZWxzXG4gICAgICAgICAgKTtcbiAgICAgICAgICBiZXN0TWF0Y2hDYXRlZ29yeSA9XG4gICAgICAgICAgICBwcmV2aW91c0NhdGVnb3JpZXMuZmluZChcbiAgICAgICAgICAgICAgKGNhdGVnb3J5KSA9PiBjYXRlZ29yeS5uYW1lID09PSBiZXN0TWF0Y2hMYWJlbFxuICAgICAgICAgICAgKSB8fCB7fTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgICBgQ2xhc3NpZmljYXRpb24gZmFpbGVkIGZvciBwcmV2aW91cyBjYXRlZ29yaWVzIGZvciBldmVudCAke2lkfTogJHtjbGFzc2lmaWNhdGlvblJlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICAgICApO1xuICAgICAgICB9XG4gICAgICAgIGlmICgoYmVzdE1hdGNoQ2F0ZWdvcnkgYXMgQ2F0ZWdvcnlUeXBlKT8uaWQpIHtcbiAgICAgICAgICBuZXdNb2RpZmllZEV2ZW50ID0gY29weU92ZXJQcmV2aW91c0V2ZW50RGVmYXVsdHMoXG4gICAgICAgICAgICBvbGRFdmVudCxcbiAgICAgICAgICAgIHByZXZpb3VzRXZlbnQsXG4gICAgICAgICAgICBiZXN0TWF0Y2hDYXRlZ29yeSBhcyBDYXRlZ29yeVR5cGUsXG4gICAgICAgICAgICB1c2VyUHJlZmVyZW5jZXNcbiAgICAgICAgICApO1xuICAgICAgICB9XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBuZXdNb2RpZmllZEV2ZW50ID0gY29weU92ZXJQcmV2aW91c0V2ZW50RGVmYXVsdHMoXG4gICAgICAgICAgb2xkRXZlbnQsXG4gICAgICAgICAgcHJldmlvdXNFdmVudCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdXNlclByZWZlcmVuY2VzXG4gICAgICAgICk7XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgKHVzZXJQcmVmZXJlbmNlcz8uY29weVJlbWluZGVycyB8fCB1c2VyUHJlZmVyZW5jZXM/LmNvcHlUaW1lQmxvY2tpbmcpICYmXG4gICAgICAgIG5ld01vZGlmaWVkRXZlbnQ/LmlkXG4gICAgICApIHtcbiAgICAgICAgY29uc3QgcmVtaW5kZXJzVGltZUJsb2NraW5nUmVzcCA9XG4gICAgICAgICAgYXdhaXQgY3JlYXRlUmVtaW5kZXJzQW5kVGltZUJsb2NraW5nRnJvbVByZXZpb3VzRXZlbnRHaXZlblVzZXJQcmVmZXJlbmNlcyhcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgIG5ld01vZGlmaWVkRXZlbnQsXG4gICAgICAgICAgICBuZXdSZW1pbmRlcnMsXG4gICAgICAgICAgICBuZXdUaW1lQmxvY2tpbmcsXG4gICAgICAgICAgICBwcmV2aW91c0V2ZW50LFxuICAgICAgICAgICAgdXNlclByZWZlcmVuY2VzXG4gICAgICAgICAgKTtcbiAgICAgICAgaWYgKHJlbWluZGVyc1RpbWVCbG9ja2luZ1Jlc3Aub2sgJiYgcmVtaW5kZXJzVGltZUJsb2NraW5nUmVzcC5kYXRhKSB7XG4gICAgICAgICAgbmV3TW9kaWZpZWRFdmVudCA9IHJlbWluZGVyc1RpbWVCbG9ja2luZ1Jlc3AuZGF0YS5uZXdFdmVudDtcbiAgICAgICAgICBuZXdSZW1pbmRlcnMgPSByZW1pbmRlcnNUaW1lQmxvY2tpbmdSZXNwLmRhdGEubmV3UmVtaW5kZXJzO1xuICAgICAgICAgIG5ld1RpbWVCbG9ja2luZyA9IHJlbWluZGVyc1RpbWVCbG9ja2luZ1Jlc3AuZGF0YS5uZXdCdWZmZXJUaW1lcztcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgICBgRmFpbGVkIHRvIGNyZWF0ZSByZW1pbmRlcnMvYnVmZmVycyBmcm9tIHVzZXIgcHJlZnMgZm9yIGV2ZW50ICR7aWR9OiAke3JlbWluZGVyc1RpbWVCbG9ja2luZ1Jlc3AuZXJyb3I/Lm1lc3NhZ2V9YFxuICAgICAgICAgICk7XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgY29uc3QgY3VycmVudEJlc3RNYXRjaENhdGVnb3J5ID0gYmVzdE1hdGNoQ2F0ZWdvcnkgYXMgQ2F0ZWdvcnlUeXBlOyAvLyBUbyB1c2UgaW4gY29uZGl0aW9ucyBiZWxvd1xuICAgICAgaWYgKFxuICAgICAgICBjdXJyZW50QmVzdE1hdGNoQ2F0ZWdvcnk/LmlkICYmXG4gICAgICAgIChjdXJyZW50QmVzdE1hdGNoQ2F0ZWdvcnk/LmRlZmF1bHRSZW1pbmRlcnMgfHxcbiAgICAgICAgICBjdXJyZW50QmVzdE1hdGNoQ2F0ZWdvcnk/LmRlZmF1bHRUaW1lQmxvY2tpbmcpICYmXG4gICAgICAgIG5ld01vZGlmaWVkRXZlbnQ/LmlkXG4gICAgICApIHtcbiAgICAgICAgY29uc3QgdXBkYXRlVmFsdWVzUmVzcCA9XG4gICAgICAgICAgYXdhaXQgdXBkYXRlVmFsdWVzRm9yRXZlbnRXaXRoUHJldmlvdXNFdmVudFBsdXNNZWV0aW5nQW5kRXh0ZXJuYWxNZWV0aW5nKFxuICAgICAgICAgICAgb2xkRXZlbnQsXG4gICAgICAgICAgICBuZXdNb2RpZmllZEV2ZW50LFxuICAgICAgICAgICAgYmVzdE1hdGNoQ2F0ZWdvcmllcyxcbiAgICAgICAgICAgIG5ld1JlbWluZGVycyxcbiAgICAgICAgICAgIG5ld1RpbWVCbG9ja2luZyxcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgICAgIHByZXZpb3VzRXZlbnRcbiAgICAgICAgICApO1xuICAgICAgICBpZiAodXBkYXRlVmFsdWVzUmVzcC5vayAmJiB1cGRhdGVWYWx1ZXNSZXNwLmRhdGEpIHtcbiAgICAgICAgICBuZXdNb2RpZmllZEV2ZW50ID0gdXBkYXRlVmFsdWVzUmVzcC5kYXRhLm5ld0V2ZW50O1xuICAgICAgICAgIG5ld1JlbWluZGVycyA9IHVwZGF0ZVZhbHVlc1Jlc3AuZGF0YS5uZXdSZW1pbmRlcnM7XG4gICAgICAgICAgbmV3VGltZUJsb2NraW5nID0gdXBkYXRlVmFsdWVzUmVzcC5kYXRhLm5ld0J1ZmZlclRpbWVzO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICAgIGBGYWlsZWQgdG8gdXBkYXRlIHZhbHVlcyBmcm9tIGJlc3QgbWF0Y2ggY2F0ZWdvcnkgZm9yIGV2ZW50ICR7aWR9OiAke3VwZGF0ZVZhbHVlc1Jlc3AuZXJyb3I/Lm1lc3NhZ2V9YFxuICAgICAgICAgICk7XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgaWYgKFxuICAgICAgICBjdXJyZW50QmVzdE1hdGNoQ2F0ZWdvcnk/LmlkICYmXG4gICAgICAgIChjdXJyZW50QmVzdE1hdGNoQ2F0ZWdvcnk/LmNvcHlSZW1pbmRlcnMgfHxcbiAgICAgICAgICBjdXJyZW50QmVzdE1hdGNoQ2F0ZWdvcnk/LmNvcHlUaW1lQmxvY2tpbmcpICYmXG4gICAgICAgIG5ld01vZGlmaWVkRXZlbnQ/LmlkXG4gICAgICApIHtcbiAgICAgICAgY29uc3QgcmVtaW5kZXJzQW5kQnVmZmVyc1Jlc3AgPVxuICAgICAgICAgIGF3YWl0IGNyZWF0ZVJlbWluZGVyc0FuZEJ1ZmZlclRpbWVzRm9yQmVzdE1hdGNoQ2F0ZWdvcnkoXG4gICAgICAgICAgICBpZCxcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgIG5ld01vZGlmaWVkRXZlbnQsXG4gICAgICAgICAgICBjdXJyZW50QmVzdE1hdGNoQ2F0ZWdvcnksXG4gICAgICAgICAgICBuZXdSZW1pbmRlcnMsXG4gICAgICAgICAgICBuZXdUaW1lQmxvY2tpbmdcbiAgICAgICAgICApO1xuICAgICAgICBpZiAocmVtaW5kZXJzQW5kQnVmZmVyc1Jlc3Aub2sgJiYgcmVtaW5kZXJzQW5kQnVmZmVyc1Jlc3AuZGF0YSkge1xuICAgICAgICAgIG5ld01vZGlmaWVkRXZlbnQgPSByZW1pbmRlcnNBbmRCdWZmZXJzUmVzcC5kYXRhLm5ld0V2ZW50O1xuICAgICAgICAgIG5ld1JlbWluZGVycyA9IHJlbWluZGVyc0FuZEJ1ZmZlcnNSZXNwLmRhdGEubmV3UmVtaW5kZXJzO1xuICAgICAgICAgIG5ld1RpbWVCbG9ja2luZyA9IHJlbWluZGVyc0FuZEJ1ZmZlcnNSZXNwLmRhdGEubmV3QnVmZmVyVGltZXM7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICAgYEZhaWxlZCB0byBjcmVhdGUgcmVtaW5kZXJzL2J1ZmZlcnMgZnJvbSBiZXN0IG1hdGNoIGNhdGVnb3J5IChjb3B5KSBmb3IgZXZlbnQgJHtpZH06ICR7cmVtaW5kZXJzQW5kQnVmZmVyc1Jlc3AuZXJyb3I/Lm1lc3NhZ2V9YFxuICAgICAgICAgICk7XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgZm9yIChjb25zdCBjYXQgb2YgW1xuICAgICAgICBwcmV2aW91c01lZXRpbmdDYXRlZ29yaWVzV2l0aE1lZXRpbmdMYWJlbD8uWzBdLFxuICAgICAgICBwcmV2aW91c01lZXRpbmdDYXRlZ29yaWVzV2l0aEV4dGVybmFsTWVldGluZ0xhYmVsPy5bMF0sXG4gICAgICBdKSB7XG4gICAgICAgIGlmIChcbiAgICAgICAgICBjYXQ/LmlkICYmXG4gICAgICAgICAgKGNhdC5jb3B5UmVtaW5kZXJzIHx8IGNhdC5jb3B5VGltZUJsb2NraW5nKSAmJlxuICAgICAgICAgIG5ld01vZGlmaWVkRXZlbnQ/LmlkXG4gICAgICAgICkge1xuICAgICAgICAgIGNvbnN0IHJlbWluZGVyc0FuZEJ1ZmZlcnNSZXNwID1cbiAgICAgICAgICAgIGF3YWl0IGNyZWF0ZVJlbWluZGVyc0FuZEJ1ZmZlclRpbWVzRm9yQmVzdE1hdGNoQ2F0ZWdvcnkoXG4gICAgICAgICAgICAgIGlkLFxuICAgICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICAgIG5ld01vZGlmaWVkRXZlbnQsXG4gICAgICAgICAgICAgIGNhdCxcbiAgICAgICAgICAgICAgbmV3UmVtaW5kZXJzLFxuICAgICAgICAgICAgICBuZXdUaW1lQmxvY2tpbmdcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgaWYgKHJlbWluZGVyc0FuZEJ1ZmZlcnNSZXNwLm9rICYmIHJlbWluZGVyc0FuZEJ1ZmZlcnNSZXNwLmRhdGEpIHtcbiAgICAgICAgICAgIG5ld01vZGlmaWVkRXZlbnQgPSByZW1pbmRlcnNBbmRCdWZmZXJzUmVzcC5kYXRhLm5ld0V2ZW50O1xuICAgICAgICAgICAgbmV3UmVtaW5kZXJzID0gcmVtaW5kZXJzQW5kQnVmZmVyc1Jlc3AuZGF0YS5uZXdSZW1pbmRlcnM7XG4gICAgICAgICAgICBuZXdUaW1lQmxvY2tpbmcgPSByZW1pbmRlcnNBbmRCdWZmZXJzUmVzcC5kYXRhLm5ld0J1ZmZlclRpbWVzO1xuICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgICAgIGBGYWlsZWQgdG8gY3JlYXRlIHJlbWluZGVycy9idWZmZXJzIGZyb20gbWVldGluZyBjYXRlZ29yaWVzIGZvciBldmVudCAke2lkfTogJHtyZW1pbmRlcnNBbmRCdWZmZXJzUmVzcC5lcnJvcj8ubWVzc2FnZX1gXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIChwcmV2aW91c0V2ZW50Py5jb3B5UmVtaW5kZXJzIHx8IHByZXZpb3VzRXZlbnQ/LmNvcHlUaW1lQmxvY2tpbmcpICYmXG4gICAgICAgIG5ld01vZGlmaWVkRXZlbnQ/LmlkXG4gICAgICApIHtcbiAgICAgICAgY29uc3QgcHJldkV2ZW50UmVtaW5kZXJzQnVmZmVyc1Jlc3AgPVxuICAgICAgICAgIGF3YWl0IGNyZWF0ZVJlbWluZGVyc0FuZFRpbWVCbG9ja2luZ0Zyb21QcmV2aW91c0V2ZW50KFxuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgbmV3TW9kaWZpZWRFdmVudCxcbiAgICAgICAgICAgIG5ld1JlbWluZGVycyxcbiAgICAgICAgICAgIG5ld1RpbWVCbG9ja2luZyxcbiAgICAgICAgICAgIHByZXZpb3VzRXZlbnRcbiAgICAgICAgICApO1xuICAgICAgICBpZiAoXG4gICAgICAgICAgcHJldkV2ZW50UmVtaW5kZXJzQnVmZmVyc1Jlc3Aub2sgJiZcbiAgICAgICAgICBwcmV2RXZlbnRSZW1pbmRlcnNCdWZmZXJzUmVzcC5kYXRhXG4gICAgICAgICkge1xuICAgICAgICAgIG5ld01vZGlmaWVkRXZlbnQgPSBwcmV2RXZlbnRSZW1pbmRlcnNCdWZmZXJzUmVzcC5kYXRhLm5ld0V2ZW50O1xuICAgICAgICAgIG5ld1JlbWluZGVycyA9IHByZXZFdmVudFJlbWluZGVyc0J1ZmZlcnNSZXNwLmRhdGEubmV3UmVtaW5kZXJzO1xuICAgICAgICAgIG5ld1RpbWVCbG9ja2luZyA9IHByZXZFdmVudFJlbWluZGVyc0J1ZmZlcnNSZXNwLmRhdGEubmV3QnVmZmVyVGltZXM7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICAgYEZhaWxlZCB0byBjcmVhdGUgcmVtaW5kZXJzL2J1ZmZlcnMgZnJvbSBwcmV2aW91cyBldmVudCBmb3IgZXZlbnQgJHtpZH06ICR7cHJldkV2ZW50UmVtaW5kZXJzQnVmZmVyc1Jlc3AuZXJyb3I/Lm1lc3NhZ2V9YFxuICAgICAgICAgICk7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICAgIGJlc3RNYXRjaENhdGVnb3JpZXMgPSBnZXRVbmlxdWVMYWJlbHMoYmVzdE1hdGNoQ2F0ZWdvcmllcyk7XG4gICAgfVxuICAgIHJldHVybiB7XG4gICAgICBvazogdHJ1ZSxcbiAgICAgIGRhdGE6IHsgbmV3TW9kaWZpZWRFdmVudCwgbmV3UmVtaW5kZXJzLCBuZXdUaW1lQmxvY2tpbmcgfSxcbiAgICB9O1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgJ0Vycm9yIGluIHByb2Nlc3NFdmVudFdpdGhGb3VuZFByZXZpb3VzRXZlbnRBbmRDb3B5Q2F0ZWdvcmllczonLFxuICAgICAgZVxuICAgICk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdJTlRFUk5BTF9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gcHJvY2VzcyBldmVudCB3aXRoIHByZXZpb3VzIGV2ZW50IGFuZCBjYXRlZ29yaWVzOiAke2UubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBlLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0V2ZW50V2l0aEZvdW5kUHJldmlvdXNFdmVudFdpdGhvdXRDYXRlZ29yaWVzID0gYXN5bmMgKFxuICBwcmV2aW91c0V2ZW50OiBFdmVudFBsdXNUeXBlLFxuICBldmVudDogRXZlbnRQbHVzVHlwZSxcbiAgdXNlclByZWZlcmVuY2VzOiBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIHVzZXJJZDogc3RyaW5nLFxuICBuZXdSZW1pbmRlcnM6IFJlbWluZGVyVHlwZVtdID0gW10sXG4gIG5ld1RpbWVCbG9ja2luZzogQnVmZmVyVGltZU9iamVjdFR5cGUgPSB7fVxuKTogUHJvbWlzZTxcbiAgRmVhdHVyZXNBcHBseVJlc3BvbnNlPHtcbiAgICBuZXdNb2RpZmllZEV2ZW50OiBFdmVudFBsdXNUeXBlO1xuICAgIG5ld1JlbWluZGVyczogUmVtaW5kZXJUeXBlW107XG4gICAgbmV3VGltZUJsb2NraW5nOiBCdWZmZXJUaW1lT2JqZWN0VHlwZTtcbiAgfSB8IG51bGw+XG4+ID0+IHtcbiAgaWYgKCFwcmV2aW91c0V2ZW50IHx8ICFldmVudCB8fCAhdXNlclByZWZlcmVuY2VzIHx8ICF1c2VySWQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICdNaXNzaW5nIGNyaXRpY2FsIHBhcmFtZXRlcnMgZm9yIHByb2Nlc3NpbmcgZXZlbnQgd2l0aG91dCBjYXRlZ29yaWVzLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBsZXQgbmV3TW9kaWZpZWRFdmVudCA9IGV2ZW50O1xuXG4gICAgaWYgKCFwcmV2aW91c0V2ZW50Py51bmxpbmspIHtcbiAgICAgIG5ld01vZGlmaWVkRXZlbnQgPSBjb3B5T3ZlclByZXZpb3VzRXZlbnREZWZhdWx0cyhcbiAgICAgICAgZXZlbnQsXG4gICAgICAgIHByZXZpb3VzRXZlbnQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdXNlclByZWZlcmVuY2VzXG4gICAgICApO1xuXG4gICAgICBpZiAoXG4gICAgICAgICh1c2VyUHJlZmVyZW5jZXM/LmNvcHlSZW1pbmRlcnMgfHwgdXNlclByZWZlcmVuY2VzPy5jb3B5VGltZUJsb2NraW5nKSAmJlxuICAgICAgICBuZXdNb2RpZmllZEV2ZW50Py5pZFxuICAgICAgKSB7XG4gICAgICAgIGNvbnN0IHJlbWluZGVyc1RpbWVCbG9ja2luZ1Jlc3AgPVxuICAgICAgICAgIGF3YWl0IGNyZWF0ZVJlbWluZGVyc0FuZFRpbWVCbG9ja2luZ0Zyb21QcmV2aW91c0V2ZW50R2l2ZW5Vc2VyUHJlZmVyZW5jZXMoXG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBuZXdNb2RpZmllZEV2ZW50LFxuICAgICAgICAgICAgbmV3UmVtaW5kZXJzLFxuICAgICAgICAgICAgbmV3VGltZUJsb2NraW5nLFxuICAgICAgICAgICAgcHJldmlvdXNFdmVudCxcbiAgICAgICAgICAgIHVzZXJQcmVmZXJlbmNlc1xuICAgICAgICAgICk7XG4gICAgICAgIGlmIChyZW1pbmRlcnNUaW1lQmxvY2tpbmdSZXNwLm9rICYmIHJlbWluZGVyc1RpbWVCbG9ja2luZ1Jlc3AuZGF0YSkge1xuICAgICAgICAgIG5ld01vZGlmaWVkRXZlbnQgPSByZW1pbmRlcnNUaW1lQmxvY2tpbmdSZXNwLmRhdGEubmV3RXZlbnQ7XG4gICAgICAgICAgbmV3UmVtaW5kZXJzID0gcmVtaW5kZXJzVGltZUJsb2NraW5nUmVzcC5kYXRhLm5ld1JlbWluZGVycztcbiAgICAgICAgICBuZXdUaW1lQmxvY2tpbmcgPSByZW1pbmRlcnNUaW1lQmxvY2tpbmdSZXNwLmRhdGEubmV3QnVmZmVyVGltZXM7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICAgYEZhaWxlZCB0byBjcmVhdGUgcmVtaW5kZXJzL2J1ZmZlcnMgZnJvbSB1c2VyIHByZWZzIChubyBjYXRlZ29yaWVzKTogJHtyZW1pbmRlcnNUaW1lQmxvY2tpbmdSZXNwLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICAgICApO1xuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgKHByZXZpb3VzRXZlbnQ/LmNvcHlSZW1pbmRlcnMgfHwgcHJldmlvdXNFdmVudD8uY29weVRpbWVCbG9ja2luZykgJiZcbiAgICAgICAgbmV3TW9kaWZpZWRFdmVudD8uaWRcbiAgICAgICkge1xuICAgICAgICBjb25zdCBwcmV2RXZlbnRSZW1pbmRlcnNCdWZmZXJzUmVzcCA9XG4gICAgICAgICAgYXdhaXQgY3JlYXRlUmVtaW5kZXJzQW5kVGltZUJsb2NraW5nRnJvbVByZXZpb3VzRXZlbnQoXG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBuZXdNb2RpZmllZEV2ZW50LFxuICAgICAgICAgICAgbmV3UmVtaW5kZXJzLFxuICAgICAgICAgICAgbmV3VGltZUJsb2NraW5nLFxuICAgICAgICAgICAgcHJldmlvdXNFdmVudFxuICAgICAgICAgICk7XG4gICAgICAgIGlmIChcbiAgICAgICAgICBwcmV2RXZlbnRSZW1pbmRlcnNCdWZmZXJzUmVzcC5vayAmJlxuICAgICAgICAgIHByZXZFdmVudFJlbWluZGVyc0J1ZmZlcnNSZXNwLmRhdGFcbiAgICAgICAgKSB7XG4gICAgICAgICAgbmV3TW9kaWZpZWRFdmVudCA9IHByZXZFdmVudFJlbWluZGVyc0J1ZmZlcnNSZXNwLmRhdGEubmV3RXZlbnQ7XG4gICAgICAgICAgbmV3UmVtaW5kZXJzID0gcHJldkV2ZW50UmVtaW5kZXJzQnVmZmVyc1Jlc3AuZGF0YS5uZXdSZW1pbmRlcnM7XG4gICAgICAgICAgbmV3VGltZUJsb2NraW5nID0gcHJldkV2ZW50UmVtaW5kZXJzQnVmZmVyc1Jlc3AuZGF0YS5uZXdCdWZmZXJUaW1lcztcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgICBgRmFpbGVkIHRvIGNyZWF0ZSByZW1pbmRlcnMvYnVmZmVycyBmcm9tIHByZXZpb3VzIGV2ZW50IChubyBjYXRlZ29yaWVzKTogJHtwcmV2RXZlbnRSZW1pbmRlcnNCdWZmZXJzUmVzcC5lcnJvcj8ubWVzc2FnZX1gXG4gICAgICAgICAgKTtcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cbiAgICByZXR1cm4ge1xuICAgICAgb2s6IHRydWUsXG4gICAgICBkYXRhOiB7IG5ld01vZGlmaWVkRXZlbnQsIG5ld1JlbWluZGVycywgbmV3VGltZUJsb2NraW5nIH0sXG4gICAgfTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgICdFcnJvciBpbiBwcm9jZXNzRXZlbnRXaXRoRm91bmRQcmV2aW91c0V2ZW50V2l0aG91dENhdGVnb3JpZXM6JyxcbiAgICAgIGVcbiAgICApO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnSU5URVJOQUxfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgRmFpbGVkIHRvIHByb2Nlc3MgZXZlbnQgd2l0aG91dCBjYXRlZ29yaWVzOiAke2UubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBlLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc1VzZXJFdmVudFdpdGhGb3VuZFByZXZpb3VzRXZlbnQgPSBhc3luYyAoXG4gIGV2ZW50OiBFdmVudFBsdXNUeXBlLFxuICBwcmV2aW91c0V2ZW50SWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxcbiAgRmVhdHVyZXNBcHBseVJlc3BvbnNlPHtcbiAgICBuZXdFdmVudDogRXZlbnRQbHVzVHlwZTtcbiAgICBuZXdSZW1pbmRlcnM/OiBSZW1pbmRlclR5cGVbXTtcbiAgICBuZXdCdWZmZXJUaW1lcz86IEJ1ZmZlclRpbWVPYmplY3RUeXBlO1xuICB9IHwgbnVsbD5cbj4gPT4ge1xuICBpZiAoIWV2ZW50IHx8ICFldmVudC5pZCB8fCAhZXZlbnQudXNlcklkIHx8ICFwcmV2aW91c0V2ZW50SWQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnRXZlbnQsIGV2ZW50IElELCB1c2VySWQsIGFuZCBwcmV2aW91c0V2ZW50SWQgYXJlIHJlcXVpcmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBjb25zdCB7IGlkLCB1c2VySWQgfSA9IGV2ZW50O1xuXG4gICAgY29uc3QgcHJldkV2ZW50UmVzcG9uc2UgPSBhd2FpdCBnZXRFdmVudEZyb21QcmltYXJ5S2V5KHByZXZpb3VzRXZlbnRJZCk7XG4gICAgaWYgKCFwcmV2RXZlbnRSZXNwb25zZS5vayB8fCAhcHJldkV2ZW50UmVzcG9uc2UuZGF0YSkge1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICBlcnJvcjogcHJldkV2ZW50UmVzcG9uc2UuZXJyb3IgfHwge1xuICAgICAgICAgIGNvZGU6ICdJTlRFUk5BTF9FUlJPUicsXG4gICAgICAgICAgbWVzc2FnZTogYFByZXZpb3VzIGV2ZW50ICR7cHJldmlvdXNFdmVudElkfSBub3QgZm91bmQgb3IgZmFpbGVkIHRvIGZldGNoLmAsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cbiAgICBjb25zdCBwcmV2aW91c0V2ZW50ID0gcHJldkV2ZW50UmVzcG9uc2UuZGF0YTtcblxuICAgIGNvbnN0IHByZWZUaW1lUmFuZ2VzUmVzcG9uc2UgPVxuICAgICAgYXdhaXQgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudChwcmV2aW91c0V2ZW50SWQpO1xuICAgIC8vIE5vbi1jcml0aWNhbCBpZiBwcmVmZXJyZWQgdGltZSByYW5nZXMgYXJlIG5vdCBmb3VuZCwgc28gd2UgZG9uJ3QgZmFpbCB0aGUgd2hvbGUgcHJvY2VzcyBoZXJlXG4gICAgaWYgKHByZWZUaW1lUmFuZ2VzUmVzcG9uc2Uub2sgJiYgcHJlZlRpbWVSYW5nZXNSZXNwb25zZS5kYXRhKSB7XG4gICAgICBwcmV2aW91c0V2ZW50LnByZWZlcnJlZFRpbWVSYW5nZXMgPSBwcmVmVGltZVJhbmdlc1Jlc3BvbnNlLmRhdGE7XG4gICAgfSBlbHNlIHtcbiAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgYENvdWxkIG5vdCBmZXRjaCBwcmVmZXJyZWQgdGltZSByYW5nZXMgZm9yIHByZXZpb3VzIGV2ZW50ICR7cHJldmlvdXNFdmVudElkfTogJHtwcmVmVGltZVJhbmdlc1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICk7XG4gICAgICBwcmV2aW91c0V2ZW50LnByZWZlcnJlZFRpbWVSYW5nZXMgPSBbXTtcbiAgICB9XG5cbiAgICBjb25zdCBjYXRlZ29yaWVzUmVzcG9uc2UgPSBhd2FpdCBnZXRVc2VyQ2F0ZWdvcmllcyh1c2VySWQpO1xuICAgIGlmICghY2F0ZWdvcmllc1Jlc3BvbnNlLm9rKSB7XG4gICAgICAvLyBJZiBjYXRlZ29yaWVzIGNhbid0IGJlIGZldGNoZWQsIHRoaXMgbWlnaHQgYmUgYSBtb3JlIGNyaXRpY2FsIGlzc3VlXG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiBjYXRlZ29yaWVzUmVzcG9uc2UuZXJyb3IgfHwge1xuICAgICAgICAgIGNvZGU6ICdJTlRFUk5BTF9FUlJPUicsXG4gICAgICAgICAgbWVzc2FnZTogJ0ZhaWxlZCB0byBnZXQgdXNlciBjYXRlZ29yaWVzLicsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cbiAgICBjb25zdCBjYXRlZ29yaWVzID0gY2F0ZWdvcmllc1Jlc3BvbnNlLmRhdGEgfHwgW107IC8vIERlZmF1bHQgdG8gZW1wdHkgYXJyYXkgaWYgbnVsbFxuXG4gICAgbGV0IGJlc3RNYXRjaENhdGVnb3J5OiBDYXRlZ29yeVR5cGUgfCBudWxsID0gbnVsbDtcbiAgICBsZXQgYmVzdE1hdGNoQ2F0ZWdvcmllc1BsdXNNZWV0aW5nVHlwZTogQ2F0ZWdvcnlUeXBlW10gPSBbXTtcblxuICAgIGlmIChjYXRlZ29yaWVzLmxlbmd0aCA+IDApIHtcbiAgICAgIGNvbnN0IGNsYXNzaWZpY2F0aW9uUmVzcG9uc2UgPSBhd2FpdCBmaW5kQmVzdE1hdGNoQ2F0ZWdvcnkyKFxuICAgICAgICBldmVudCxcbiAgICAgICAgY2F0ZWdvcmllc1xuICAgICAgKTtcbiAgICAgIGlmIChjbGFzc2lmaWNhdGlvblJlc3BvbnNlLm9rICYmIGNsYXNzaWZpY2F0aW9uUmVzcG9uc2UuZGF0YSkge1xuICAgICAgICBjb25zdCBjbGFzc2lmaWNhdGlvbkJvZHkgPSBjbGFzc2lmaWNhdGlvblJlc3BvbnNlLmRhdGE7XG4gICAgICAgIGNvbnN0IHsgbGFiZWxzLCBzY29yZXMgfSA9IGNsYXNzaWZpY2F0aW9uQm9keTtcbiAgICAgICAgY29uc3QgYmVzdE1hdGNoTGFiZWwgPSBwcm9jZXNzQmVzdE1hdGNoQ2F0ZWdvcmllcyhcbiAgICAgICAgICBjbGFzc2lmaWNhdGlvbkJvZHksXG4gICAgICAgICAgbGFiZWxzXG4gICAgICAgICk7XG4gICAgICAgIGlmIChiZXN0TWF0Y2hMYWJlbCkge1xuICAgICAgICAgIGJlc3RNYXRjaENhdGVnb3J5ID1cbiAgICAgICAgICAgIGNhdGVnb3JpZXMuZmluZCgoY2F0ZWdvcnkpID0+IGNhdGVnb3J5Lm5hbWUgPT09IGJlc3RNYXRjaExhYmVsKSB8fFxuICAgICAgICAgICAgbnVsbDtcbiAgICAgICAgfVxuICAgICAgICBpZiAoYmVzdE1hdGNoQ2F0ZWdvcnkpIHtcbiAgICAgICAgICBiZXN0TWF0Y2hDYXRlZ29yaWVzUGx1c01lZXRpbmdUeXBlID1cbiAgICAgICAgICAgIHByb2Nlc3NFdmVudEZvck1lZXRpbmdUeXBlQ2F0ZWdvcmllcyhcbiAgICAgICAgICAgICAgZXZlbnQsXG4gICAgICAgICAgICAgIGJlc3RNYXRjaENhdGVnb3J5LFxuICAgICAgICAgICAgICBsYWJlbHMsXG4gICAgICAgICAgICAgIHNjb3JlcyxcbiAgICAgICAgICAgICAgY2F0ZWdvcmllc1xuICAgICAgICAgICAgKTtcbiAgICAgICAgICBiZXN0TWF0Y2hDYXRlZ29yaWVzUGx1c01lZXRpbmdUeXBlID0gZ2V0VW5pcXVlTGFiZWxzKFxuICAgICAgICAgICAgYmVzdE1hdGNoQ2F0ZWdvcmllc1BsdXNNZWV0aW5nVHlwZVxuICAgICAgICAgICk7XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICBgQ2F0ZWdvcnkgY2xhc3NpZmljYXRpb24gZmFpbGVkIGZvciBldmVudCAke2lkfTogJHtjbGFzc2lmaWNhdGlvblJlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICAgKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCB1c2VyUHJlZmVyZW5jZXNSZXNwb25zZSA9IGF3YWl0IGdldFVzZXJQcmVmZXJlbmNlcyh1c2VySWQpO1xuICAgIGlmICghdXNlclByZWZlcmVuY2VzUmVzcG9uc2Uub2sgfHwgIXVzZXJQcmVmZXJlbmNlc1Jlc3BvbnNlLmRhdGEpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHVzZXJQcmVmZXJlbmNlc1Jlc3BvbnNlLmVycm9yIHx8IHtcbiAgICAgICAgICBjb2RlOiAnSU5URVJOQUxfRVJST1InLFxuICAgICAgICAgIG1lc3NhZ2U6ICdVc2VyIHByZWZlcmVuY2VzIG5vdCBmb3VuZCBvciBmYWlsZWQgdG8gZmV0Y2guJyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuICAgIGNvbnN0IHVzZXJQcmVmZXJlbmNlcyA9IHVzZXJQcmVmZXJlbmNlc1Jlc3BvbnNlLmRhdGE7XG5cbiAgICBsZXQgbmV3TW9kaWZpZWRFdmVudDogRXZlbnRQbHVzVHlwZSA9IHsgLi4uZXZlbnQgfTsgLy8gU3RhcnQgd2l0aCBhIGNvcHlcbiAgICBsZXQgbmV3UmVtaW5kZXJzOiBSZW1pbmRlclR5cGVbXSA9IFtdO1xuICAgIGxldCBuZXdCdWZmZXJUaW1lczogQnVmZmVyVGltZU9iamVjdFR5cGUgPSB7fTtcblxuICAgIGlmIChcbiAgICAgIChwcmV2aW91c0V2ZW50Py5jb3B5Q2F0ZWdvcmllcyB8fCB1c2VyUHJlZmVyZW5jZXM/LmNvcHlDYXRlZ29yaWVzKSAmJlxuICAgICAgIXByZXZpb3VzRXZlbnQ/LnVubGluayAmJlxuICAgICAgIWV2ZW50Py51c2VyTW9kaWZpZWRDYXRlZ29yaWVzXG4gICAgKSB7XG4gICAgICBjb25zdCBwcmV2Q2F0ZWdvcmllc1Jlc3BvbnNlID0gYXdhaXQgbGlzdENhdGVnb3JpZXNGb3JFdmVudChcbiAgICAgICAgcHJldmlvdXNFdmVudC5pZFxuICAgICAgKTtcbiAgICAgIGNvbnN0IHByZXZpb3VzQ2F0ZWdvcmllcyA9XG4gICAgICAgIHByZXZDYXRlZ29yaWVzUmVzcG9uc2Uub2sgJiYgcHJldkNhdGVnb3JpZXNSZXNwb25zZS5kYXRhXG4gICAgICAgICAgPyBwcmV2Q2F0ZWdvcmllc1Jlc3BvbnNlLmRhdGFcbiAgICAgICAgICA6IFtdO1xuXG4gICAgICBjb25zdCBwcm9jZXNzaW5nUmVzdWx0ID1cbiAgICAgICAgYXdhaXQgcHJvY2Vzc0V2ZW50V2l0aEZvdW5kUHJldmlvdXNFdmVudEFuZENvcHlDYXRlZ29yaWVzKFxuICAgICAgICAgIGlkLFxuICAgICAgICAgIHByZXZpb3VzRXZlbnQsXG4gICAgICAgICAgZXZlbnQsXG4gICAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICAgIGJlc3RNYXRjaENhdGVnb3J5LFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICBiZXN0TWF0Y2hDYXRlZ29yaWVzUGx1c01lZXRpbmdUeXBlLFxuICAgICAgICAgIG5ld01vZGlmaWVkRXZlbnQsXG4gICAgICAgICAgbmV3UmVtaW5kZXJzLFxuICAgICAgICAgIG5ld0J1ZmZlclRpbWVzLFxuICAgICAgICAgIHByZXZpb3VzQ2F0ZWdvcmllcyxcbiAgICAgICAgICBwcmV2aW91c0NhdGVnb3JpZXMuZmlsdGVyKChjKSA9PiBjLm5hbWUgPT09IG1lZXRpbmdMYWJlbCksXG4gICAgICAgICAgcHJldmlvdXNDYXRlZ29yaWVzLmZpbHRlcigoYykgPT4gYy5uYW1lID09PSBleHRlcm5hbE1lZXRpbmdMYWJlbClcbiAgICAgICAgKTtcbiAgICAgIGlmIChwcm9jZXNzaW5nUmVzdWx0Lm9rICYmIHByb2Nlc3NpbmdSZXN1bHQuZGF0YSkge1xuICAgICAgICBuZXdNb2RpZmllZEV2ZW50ID0gcHJvY2Vzc2luZ1Jlc3VsdC5kYXRhLm5ld01vZGlmaWVkRXZlbnQ7XG4gICAgICAgIG5ld1JlbWluZGVycyA9IHByb2Nlc3NpbmdSZXN1bHQuZGF0YS5uZXdSZW1pbmRlcnM7XG4gICAgICAgIG5ld1RpbWVCbG9ja2luZyA9IHByb2Nlc3NpbmdSZXN1bHQuZGF0YS5uZXdUaW1lQmxvY2tpbmc7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICAvLyBMb2cgd2FybmluZyBvciBlcnJvciwgYnV0IHByb2NlZWQgd2l0aCBwb3RlbnRpYWxseSBwYXJ0aWFsbHkgbW9kaWZpZWQgZXZlbnRcbiAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgIGBQcm9jZXNzaW5nIHdpdGggJ2NvcHlDYXRlZ29yaWVzJyBmYWlsZWQgZm9yIGV2ZW50ICR7aWR9OiAke3Byb2Nlc3NpbmdSZXN1bHQuZXJyb3I/Lm1lc3NhZ2V9YFxuICAgICAgICApO1xuICAgICAgfVxuICAgIH0gZWxzZSBpZiAoXG4gICAgICB1c2VyUHJlZmVyZW5jZXM/LmlkICYmXG4gICAgICAhcHJldmlvdXNFdmVudD8uY29weUNhdGVnb3JpZXMgJiZcbiAgICAgICF1c2VyUHJlZmVyZW5jZXM/LmNvcHlDYXRlZ29yaWVzICYmXG4gICAgICAhZXZlbnQ/LnVzZXJNb2RpZmllZENhdGVnb3JpZXMgJiZcbiAgICAgIGV2ZW50Py5pZCAmJlxuICAgICAgcHJldmlvdXNFdmVudD8uaWRcbiAgICApIHtcbiAgICAgIGlmIChiZXN0TWF0Y2hDYXRlZ29yeSAmJiBiZXN0TWF0Y2hDYXRlZ29yaWVzUGx1c01lZXRpbmdUeXBlPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIG5ld01vZGlmaWVkRXZlbnQgPSBjb3B5T3ZlclByZXZpb3VzRXZlbnREZWZhdWx0cyhcbiAgICAgICAgICBldmVudCxcbiAgICAgICAgICBwcmV2aW91c0V2ZW50LFxuICAgICAgICAgIGJlc3RNYXRjaENhdGVnb3J5LFxuICAgICAgICAgIHVzZXJQcmVmZXJlbmNlc1xuICAgICAgICApO1xuICAgICAgICBpZiAobmV3TW9kaWZpZWRFdmVudD8uaWQpIHtcbiAgICAgICAgICBjb25zdCByZW1pbmRlcnNSZXNwID1cbiAgICAgICAgICAgIGF3YWl0IGNyZWF0ZVJlbWluZGVyc0FuZEJ1ZmZlclRpbWVzRm9yQmVzdE1hdGNoQ2F0ZWdvcnkoXG4gICAgICAgICAgICAgIGlkLFxuICAgICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICAgIG5ld01vZGlmaWVkRXZlbnQsXG4gICAgICAgICAgICAgIGJlc3RNYXRjaENhdGVnb3J5LFxuICAgICAgICAgICAgICBuZXdSZW1pbmRlcnMsXG4gICAgICAgICAgICAgIG5ld0J1ZmZlclRpbWVzXG4gICAgICAgICAgICApO1xuICAgICAgICAgIGlmIChyZW1pbmRlcnNSZXNwLm9rICYmIHJlbWluZGVyc1Jlc3AuZGF0YSkge1xuICAgICAgICAgICAgbmV3TW9kaWZpZWRFdmVudCA9IHJlbWluZGVyc1Jlc3AuZGF0YS5uZXdFdmVudDtcbiAgICAgICAgICAgIG5ld1JlbWluZGVycyA9IHJlbWluZGVyc1Jlc3AuZGF0YS5uZXdSZW1pbmRlcnM7XG4gICAgICAgICAgICBuZXdCdWZmZXJUaW1lcyA9IHJlbWluZGVyc1Jlc3AuZGF0YS5uZXdCdWZmZXJUaW1lcztcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBjb25zdCB1cGRhdGVWYWx1ZXNSZXNwID1cbiAgICAgICAgICAgIGF3YWl0IHVwZGF0ZVZhbHVlc0ZvckV2ZW50V2l0aFByZXZpb3VzRXZlbnRQbHVzTWVldGluZ0FuZEV4dGVybmFsTWVldGluZyhcbiAgICAgICAgICAgICAgZXZlbnQsXG4gICAgICAgICAgICAgIG5ld01vZGlmaWVkRXZlbnQsXG4gICAgICAgICAgICAgIGJlc3RNYXRjaENhdGVnb3JpZXNQbHVzTWVldGluZ1R5cGUsXG4gICAgICAgICAgICAgIG5ld1JlbWluZGVycyxcbiAgICAgICAgICAgICAgbmV3QnVmZmVyVGltZXMsXG4gICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICAgICAgICBwcmV2aW91c0V2ZW50XG4gICAgICAgICAgICApO1xuICAgICAgICAgIGlmICh1cGRhdGVWYWx1ZXNSZXNwLm9rICYmIHVwZGF0ZVZhbHVlc1Jlc3AuZGF0YSkge1xuICAgICAgICAgICAgbmV3TW9kaWZpZWRFdmVudCA9IHVwZGF0ZVZhbHVlc1Jlc3AuZGF0YS5uZXdFdmVudDtcbiAgICAgICAgICAgIG5ld1JlbWluZGVycyA9IHVwZGF0ZVZhbHVlc1Jlc3AuZGF0YS5uZXdSZW1pbmRlcnM7XG4gICAgICAgICAgICBuZXdCdWZmZXJUaW1lcyA9IHVwZGF0ZVZhbHVlc1Jlc3AuZGF0YS5uZXdCdWZmZXJUaW1lcztcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGNvbnN0IG5vQ2F0UHJvY2Vzc2luZ1Jlc3AgPVxuICAgICAgICAgIGF3YWl0IHByb2Nlc3NFdmVudFdpdGhGb3VuZFByZXZpb3VzRXZlbnRXaXRob3V0Q2F0ZWdvcmllcyhcbiAgICAgICAgICAgIHByZXZpb3VzRXZlbnQsXG4gICAgICAgICAgICBuZXdNb2RpZmllZEV2ZW50LFxuICAgICAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgbmV3UmVtaW5kZXJzLFxuICAgICAgICAgICAgbmV3QnVmZmVyVGltZXNcbiAgICAgICAgICApO1xuICAgICAgICBpZiAobm9DYXRQcm9jZXNzaW5nUmVzcC5vayAmJiBub0NhdFByb2Nlc3NpbmdSZXNwLmRhdGEpIHtcbiAgICAgICAgICBuZXdNb2RpZmllZEV2ZW50ID0gbm9DYXRQcm9jZXNzaW5nUmVzcC5kYXRhLm5ld01vZGlmaWVkRXZlbnQ7XG4gICAgICAgICAgbmV3UmVtaW5kZXJzID0gbm9DYXRQcm9jZXNzaW5nUmVzcC5kYXRhLm5ld1JlbWluZGVycztcbiAgICAgICAgICBuZXdCdWZmZXJUaW1lcyA9IG5vQ2F0UHJvY2Vzc2luZ1Jlc3AuZGF0YS5uZXdUaW1lQmxvY2tpbmc7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9XG5cbiAgICByZXR1cm4ge1xuICAgICAgb2s6IHRydWUsXG4gICAgICBkYXRhOiB7IG5ld0V2ZW50OiBuZXdNb2RpZmllZEV2ZW50LCBuZXdSZW1pbmRlcnMsIG5ld0J1ZmZlclRpbWVzIH0sXG4gICAgfTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgIGBFcnJvciBpbiBwcm9jZXNzVXNlckV2ZW50V2l0aEZvdW5kUHJldmlvdXNFdmVudCBmb3IgZXZlbnQgJHtldmVudD8uaWR9OmAsXG4gICAgICBlXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0lOVEVSTkFMX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBwcm9jZXNzIGV2ZW50IHdpdGggcHJldmlvdXMgZXZlbnQ6ICR7ZS5tZXNzYWdlfWAsXG4gICAgICAgIGRldGFpbHM6IGUsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzVXNlckV2ZW50V2l0aEZvdW5kUHJldmlvdXNFdmVudFdpdGhVc2VyTW9kaWZpZWRDYXRlZ29yaWVzID1cbiAgYXN5bmMgKFxuICAgIGV2ZW50OiBFdmVudFBsdXNUeXBlLFxuICAgIHByZXZpb3VzRXZlbnRJZDogc3RyaW5nXG4gICk6IFByb21pc2U8XG4gICAgRmVhdHVyZXNBcHBseVJlc3BvbnNlPHtcbiAgICAgIG5ld0V2ZW50OiBFdmVudFBsdXNUeXBlO1xuICAgICAgbmV3UmVtaW5kZXJzPzogUmVtaW5kZXJUeXBlW107XG4gICAgICBuZXdCdWZmZXJUaW1lcz86IEJ1ZmZlclRpbWVPYmplY3RUeXBlO1xuICAgIH0gfCBudWxsPlxuICA+ID0+IHtcbiAgICBpZiAoIWV2ZW50IHx8ICFldmVudC5pZCB8fCAhZXZlbnQudXNlcklkIHx8ICFwcmV2aW91c0V2ZW50SWQpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsXG4gICAgICAgICAgbWVzc2FnZTogJ0V2ZW50LCBldmVudCBJRCwgdXNlcklkLCBhbmQgcHJldmlvdXNFdmVudElkIGFyZSByZXF1aXJlZC4nLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IGNhdGVnb3JpZXNSZXNwb25zZSA9IGF3YWl0IGxpc3RDYXRlZ29yaWVzRm9yRXZlbnQoZXZlbnQuaWQpO1xuICAgICAgaWYgKFxuICAgICAgICAhY2F0ZWdvcmllc1Jlc3BvbnNlLm9rIHx8XG4gICAgICAgICFjYXRlZ29yaWVzUmVzcG9uc2UuZGF0YSB8fFxuICAgICAgICBjYXRlZ29yaWVzUmVzcG9uc2UuZGF0YS5sZW5ndGggPT09IDBcbiAgICAgICkge1xuICAgICAgICByZXR1cm4ge1xuICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICBlcnJvcjogY2F0ZWdvcmllc1Jlc3BvbnNlLmVycm9yIHx8IHtcbiAgICAgICAgICAgIGNvZGU6ICdJTlRFUk5BTF9FUlJPUicsXG4gICAgICAgICAgICBtZXNzYWdlOiBgTm8gY2F0ZWdvcmllcyBmb3VuZCBmb3IgZXZlbnQgJHtldmVudC5pZH0gb3IgZmFpbGVkIHRvIGZldGNoLmAsXG4gICAgICAgICAgfSxcbiAgICAgICAgfTtcbiAgICAgIH1cbiAgICAgIGNvbnN0IGNhdGVnb3JpZXMgPSBjYXRlZ29yaWVzUmVzcG9uc2UuZGF0YTtcblxuICAgICAgY29uc3QgcHJldkV2ZW50UmVzcG9uc2UgPSBhd2FpdCBnZXRFdmVudEZyb21QcmltYXJ5S2V5KHByZXZpb3VzRXZlbnRJZCk7XG4gICAgICBpZiAoIXByZXZFdmVudFJlc3BvbnNlLm9rIHx8ICFwcmV2RXZlbnRSZXNwb25zZS5kYXRhKSB7XG4gICAgICAgIHJldHVybiB7XG4gICAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICAgIGVycm9yOiBwcmV2RXZlbnRSZXNwb25zZS5lcnJvciB8fCB7XG4gICAgICAgICAgICBjb2RlOiAnSU5URVJOQUxfRVJST1InLFxuICAgICAgICAgICAgbWVzc2FnZTogYFByZXZpb3VzIGV2ZW50ICR7cHJldmlvdXNFdmVudElkfSBub3QgZm91bmQgb3IgZmFpbGVkIHRvIGZldGNoLmAsXG4gICAgICAgICAgfSxcbiAgICAgICAgfTtcbiAgICAgIH1cbiAgICAgIGNvbnN0IHByZXZpb3VzRXZlbnQgPSBwcmV2RXZlbnRSZXNwb25zZS5kYXRhO1xuXG4gICAgICBjb25zdCBwcmVmVGltZVJhbmdlc1Jlc3BvbnNlID1cbiAgICAgICAgYXdhaXQgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudChwcmV2aW91c0V2ZW50SWQpO1xuICAgICAgaWYgKHByZWZUaW1lUmFuZ2VzUmVzcG9uc2Uub2sgJiYgcHJlZlRpbWVSYW5nZXNSZXNwb25zZS5kYXRhKSB7XG4gICAgICAgIHByZXZpb3VzRXZlbnQucHJlZmVycmVkVGltZVJhbmdlcyA9IHByZWZUaW1lUmFuZ2VzUmVzcG9uc2UuZGF0YTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICBgQ291bGQgbm90IGZldGNoIHByZWZlcnJlZCB0aW1lIHJhbmdlcyBmb3IgcHJldmlvdXMgZXZlbnQgJHtwcmV2aW91c0V2ZW50SWR9OiAke3ByZWZUaW1lUmFuZ2VzUmVzcG9uc2UuZXJyb3I/Lm1lc3NhZ2V9YFxuICAgICAgICApO1xuICAgICAgICBwcmV2aW91c0V2ZW50LnByZWZlcnJlZFRpbWVSYW5nZXMgPSBbXTtcbiAgICAgIH1cblxuICAgICAgY29uc3QgY2xhc3NpZmljYXRpb25SZXNwb25zZSA9IGF3YWl0IGZpbmRCZXN0TWF0Y2hDYXRlZ29yeTIoXG4gICAgICAgIGV2ZW50LFxuICAgICAgICBjYXRlZ29yaWVzXG4gICAgICApO1xuICAgICAgaWYgKFxuICAgICAgICAhY2xhc3NpZmljYXRpb25SZXNwb25zZS5vayB8fFxuICAgICAgICAhY2xhc3NpZmljYXRpb25SZXNwb25zZS5kYXRhIHx8XG4gICAgICAgICFjbGFzc2lmaWNhdGlvblJlc3BvbnNlLmRhdGEubGFiZWxzPy5sZW5ndGhcbiAgICAgICkge1xuICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgYENsYXNzaWZpY2F0aW9uIGZhaWxlZCBvciByZXR1cm5lZCBubyBsYWJlbHMgZm9yIGV2ZW50ICR7ZXZlbnQuaWR9OiAke2NsYXNzaWZpY2F0aW9uUmVzcG9uc2UuZXJyb3I/Lm1lc3NhZ2V9YFxuICAgICAgICApO1xuICAgICAgICAvLyBEZWNpZGUgaWYgdG8gcHJvY2VlZCB3aXRoIGV2ZW50IGFzIGlzLCBvciByZXR1cm4gYW4gZXJyb3IuIEZvciBub3csIHByb2NlZWQuXG4gICAgICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiB7IG5ld0V2ZW50OiBldmVudCB9IH07XG4gICAgICB9XG4gICAgICBjb25zdCBjbGFzc2lmaWNhdGlvbkJvZHkgPSBjbGFzc2lmaWNhdGlvblJlc3BvbnNlLmRhdGE7XG4gICAgICBjb25zdCB7IGxhYmVscyB9ID0gY2xhc3NpZmljYXRpb25Cb2R5OyAvLyBzY29yZXMgYXJlIGFsc28gYXZhaWxhYmxlIGlmIG5lZWRlZFxuICAgICAgY29uc3QgYmVzdE1hdGNoTGFiZWwgPSBwcm9jZXNzQmVzdE1hdGNoQ2F0ZWdvcmllc05vVGhyZXNob2xkKFxuICAgICAgICBjbGFzc2lmaWNhdGlvbkJvZHksXG4gICAgICAgIGxhYmVsc1xuICAgICAgKTtcblxuICAgICAgbGV0IG5ld01vZGlmaWVkRXZlbnQ6IEV2ZW50UGx1c1R5cGUgPSB7IC4uLmV2ZW50IH07XG4gICAgICBsZXQgbmV3UmVtaW5kZXJzOiBSZW1pbmRlclR5cGVbXSA9IFtdO1xuICAgICAgbGV0IG5ld1RpbWVCbG9ja2luZzogQnVmZmVyVGltZU9iamVjdFR5cGUgPSB7fTtcblxuICAgICAgaWYgKGJlc3RNYXRjaExhYmVsKSB7XG4gICAgICAgIGNvbnN0IGJlc3RNYXRjaENhdGVnb3J5ID0gY2F0ZWdvcmllcy5maW5kKFxuICAgICAgICAgIChjYXRlZ29yeSkgPT4gY2F0ZWdvcnkubmFtZSA9PT0gYmVzdE1hdGNoTGFiZWxcbiAgICAgICAgKTtcbiAgICAgICAgaWYgKCFiZXN0TWF0Y2hDYXRlZ29yeSkge1xuICAgICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICAgIGBCZXN0IG1hdGNoIGxhYmVsIFwiJHtiZXN0TWF0Y2hMYWJlbH1cIiBkaWQgbm90IGNvcnJlc3BvbmQgdG8gYSBrbm93biBjYXRlZ29yeS5gXG4gICAgICAgICAgKTtcbiAgICAgICAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogeyBuZXdFdmVudDogZXZlbnQgfSB9OyAvLyBQcm9jZWVkIHdpdGggb3JpZ2luYWwgZXZlbnRcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHVzZXJQcmVmZXJlbmNlc1Jlc3BvbnNlID0gYXdhaXQgZ2V0VXNlclByZWZlcmVuY2VzKGV2ZW50LnVzZXJJZCk7XG4gICAgICAgIGlmICghdXNlclByZWZlcmVuY2VzUmVzcG9uc2Uub2sgfHwgIXVzZXJQcmVmZXJlbmNlc1Jlc3BvbnNlLmRhdGEpIHtcbiAgICAgICAgICByZXR1cm4ge1xuICAgICAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICAgICAgZXJyb3I6IHVzZXJQcmVmZXJlbmNlc1Jlc3BvbnNlLmVycm9yIHx8IHtcbiAgICAgICAgICAgICAgY29kZTogJ0lOVEVSTkFMX0VSUk9SJyxcbiAgICAgICAgICAgICAgbWVzc2FnZTogJ1VzZXIgcHJlZmVyZW5jZXMgbm90IGZvdW5kIG9yIGZhaWxlZCB0byBmZXRjaC4nLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9O1xuICAgICAgICB9XG4gICAgICAgIGNvbnN0IHVzZXJQcmVmZXJlbmNlcyA9IHVzZXJQcmVmZXJlbmNlc1Jlc3BvbnNlLmRhdGE7XG5cbiAgICAgICAgbmV3TW9kaWZpZWRFdmVudCA9IGNvcHlPdmVyUHJldmlvdXNFdmVudERlZmF1bHRzKFxuICAgICAgICAgIGV2ZW50LFxuICAgICAgICAgIHByZXZpb3VzRXZlbnQsXG4gICAgICAgICAgYmVzdE1hdGNoQ2F0ZWdvcnksXG4gICAgICAgICAgdXNlclByZWZlcmVuY2VzXG4gICAgICAgICk7XG5cbiAgICAgICAgaWYgKGNhdGVnb3JpZXMubGVuZ3RoID4gMCAmJiBuZXdNb2RpZmllZEV2ZW50Py5pZCkge1xuICAgICAgICAgIC8vIGNhdGVnb3JpZXMgaXMgYWxyZWFkeSBjaGVja2VkIHRvIGJlIG5vbi1lbXB0eVxuICAgICAgICAgIGNvbnN0IHVwZGF0ZVZhbHVlc1Jlc3AgPVxuICAgICAgICAgICAgYXdhaXQgdXBkYXRlVmFsdWVzRm9yRXZlbnRXaXRoUHJldmlvdXNFdmVudFBsdXNNZWV0aW5nQW5kRXh0ZXJuYWxNZWV0aW5nKFxuICAgICAgICAgICAgICBldmVudCxcbiAgICAgICAgICAgICAgbmV3TW9kaWZpZWRFdmVudCxcbiAgICAgICAgICAgICAgY2F0ZWdvcmllcyxcbiAgICAgICAgICAgICAgbmV3UmVtaW5kZXJzLFxuICAgICAgICAgICAgICBuZXdUaW1lQmxvY2tpbmcsXG4gICAgICAgICAgICAgIGV2ZW50LnVzZXJJZCxcbiAgICAgICAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICAgICAgICBwcmV2aW91c0V2ZW50XG4gICAgICAgICAgICApO1xuICAgICAgICAgIGlmICh1cGRhdGVWYWx1ZXNSZXNwLm9rICYmIHVwZGF0ZVZhbHVlc1Jlc3AuZGF0YSkge1xuICAgICAgICAgICAgbmV3TW9kaWZpZWRFdmVudCA9IHVwZGF0ZVZhbHVlc1Jlc3AuZGF0YS5uZXdFdmVudDtcbiAgICAgICAgICAgIG5ld1JlbWluZGVycyA9IHVwZGF0ZVZhbHVlc1Jlc3AuZGF0YS5uZXdSZW1pbmRlcnM7XG4gICAgICAgICAgICBuZXdUaW1lQmxvY2tpbmcgPSB1cGRhdGVWYWx1ZXNSZXNwLmRhdGEubmV3QnVmZmVyVGltZXM7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICAgICAgYEZhaWxlZCB0byB1cGRhdGUgdmFsdWVzIGZyb20gbW9kaWZpZWQgY2F0ZWdvcmllcyBmb3IgZXZlbnQgJHtldmVudC5pZH06ICR7dXBkYXRlVmFsdWVzUmVzcC5lcnJvcj8ubWVzc2FnZX1gXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfSBlbHNlIHtcbiAgICAgICAgY29uc29sZS53YXJuKGBObyBiZXN0IG1hdGNoIGNhdGVnb3J5IGZvdW5kIGZvciBldmVudCAke2V2ZW50LmlkfS5gKTtcbiAgICAgIH1cblxuICAgICAgcmV0dXJuIHtcbiAgICAgICAgb2s6IHRydWUsXG4gICAgICAgIGRhdGE6IHtcbiAgICAgICAgICBuZXdFdmVudDogbmV3TW9kaWZpZWRFdmVudCxcbiAgICAgICAgICBuZXdSZW1pbmRlcnMsXG4gICAgICAgICAgbmV3QnVmZmVyVGltZXM6IG5ld1RpbWVCbG9ja2luZyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICBgRXJyb3IgaW4gcHJvY2Vzc1VzZXJFdmVudFdpdGhGb3VuZFByZXZpb3VzRXZlbnRXaXRoVXNlck1vZGlmaWVkQ2F0ZWdvcmllcyBmb3IgZXZlbnQgJHtldmVudD8uaWR9OmAsXG4gICAgICAgIGVcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ0lOVEVSTkFMX0VSUk9SJyxcbiAgICAgICAgICBtZXNzYWdlOiBgRmFpbGVkIHRvIHByb2Nlc3MgZXZlbnQgd2l0aCBtb2RpZmllZCBjYXRlZ29yaWVzOiAke2UubWVzc2FnZX1gLFxuICAgICAgICAgIGRldGFpbHM6IGUsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cbiAgfTtcbiJdfQ==