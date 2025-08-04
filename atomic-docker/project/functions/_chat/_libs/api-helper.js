// import { SESClient } from "@aws-sdk/client-ses";
import { Client } from '@opensearch-project/opensearch';
import OpenAI from "openai";
import retry from 'async-retry';
import { postgraphileAdminSecret, postgraphileGraphUrl, zoomBaseTokenUrl, zoomBaseUrl, zoomClientId, zoomClientSecret, zoomIVForPass, zoomPassKey, zoomResourceName, zoomSaltForPass, googleClientIdAndroid, googleClientIdAtomicWeb, googleClientIdIos, googleClientIdWeb, googleClientSecretAtomicWeb, googleClientSecretWeb, googleTokenUrl, googleCalendarName, Day, defaultOpenAIAPIKey, openAIChatGPT35Model, openAIChatGPT35LongModel } from "./constants";
import { dayjs, getISODay, setISODay } from "./datetime/date-utils";
import { searchEvents, getEventById as getEventFromLanceDbById, deleteEventsByIds, searchTrainingEvents, upsertTrainingEvents as lancedbUpsertTrainingEvents, deleteTrainingEventsByIds } from '../../_utils/lancedb_service';
import { RecurrenceFrequencyType } from "./types/EventType";
import got from "got";
import axios from "axios";
import crypto from 'crypto';
import { google } from "googleapis";
import { v4 as uuid } from 'uuid';
import _ from "lodash";
import getEventById from "./gql/getEventById";
import insertAttendeesForEvent from "./gql/insertAttendeesForEvent";
import findContactViaEmailByUserId from "./gql/findContactViaEmailByUserId";
import getConferenceById from "./gql/getConferenceById";
import deleteConferenceById from "./gql/deleteConferenceById";
import qs from 'qs';
import deleteEventById from "./gql/deleteEventById";
import * as pkg from 'rrule';
import { interopDefault } from 'mlly';
const { RRule } = interopDefault(pkg);
import { getWeekOfMonth } from 'date-fns';
import insertMeetingAssistOne from "./gql/insertMeetingAssistOne";
import insertMeetingAssistAttendeeOne from "./gql/insertMeetingAssistAttendeeOne";
import listUserContactInfosByUserId from "./gql/listUserContactInfosByUserId";
import upsertMeetingAssistInviteGraphql from "./gql/upsertMeetingAssistInviteGraphql";
import updateNameForUserId from "./gql/updateNameForUserId";
import getContactInfosByIds from "./gql/getContactInfosByIds";
import getContactByNameForUserId from "./gql/getContactByNameForUserId";
import getUserById from "./gql/getUserById";
import getTaskById from "./gql/getTaskById";
import { extractQueryUserInputTimeToJSONPrompt, extractQueryUserInputTimeToJSONExampleInput1, extractQueryUserInputTimeToJSONExampleOutput1, extractQueryUserInputTimeToJSONExampleInput2, extractQueryUserInputTimeToJSONExampleOutput2, extractQueryUserInputTimeToJSONExampleInput3, extractQueryUserInputTimeToJSONExampleOutput3, extractQueryUserInputTimeToJSONTemplate, userInputToDateTimeJSONPrompt, userInputToDateTimeJSONExampleInput1, userInputToDateTimeJSONExampleOutput1, userInputToDateTimeJSONExampleInput2, userInputToDateTimeJSONExampleInput3, userInputToDateTimeJSONExampleOutput2, userInputToDateTimeJSONExampleOutput3 } from "./datetime/prompts";
import { getUserPreferences, generateWorkTimesForUser } from "./skills/askCalendar/api-helper";
import { TemplateEngine } from "./template-engine";
import { requestMissingFieldsExampleOutput, requestMissingFieldsPrompt, requestMissingFieldsSystemsExampleInput } from "./prompts/requestMissingData";
import { apiResponeToAssistantResponsePrompt } from "./prompts/apiResponseToAssistantResponse";
import { userInputToJSONExampleInput, userInputToJSONExampleOutput, userInputToJSONPrompt } from "./prompts/userRequestInputToJSON";
import { extractNeededAttributesExampleInput, extractNeededAttributesExampleOutput, extractNeededAttributesPrompt } from "./skills/askCalendar/prompts";
import { findASlotForNewEventExampleInput, findASlotForNewEventExampleOutput, findASlotForNewEventPrompt, findASlotForNewEventTemplate } from './prompts/findASlotForNewEvent';
import winston from 'winston'; // Added for logger
// const sesClient = new SESClient({ region: "us-east-1" })
// Logger Setup for this api-helper
const chatApiHelperLogger = winston.createLogger({
    level: process.env.LOG_LEVEL || 'info',
    format: winston.format.combine(winston.format.timestamp(), winston.format.json(), winston.format((info) => {
        info.module = 'chat-api-helper';
        return info;
    })())
}, {
    transports: [
        new winston.transports.Console(),
    ],
});
const openai = new OpenAI({
    apiKey: defaultOpenAIAPIKey,
});
export const openTrainEventIndex = 'knn-open-train-event-index';
export const openTrainEventVectorName = 'embeddings';
const getSearchClient = async () => {
    try {
        return new Client({
            node: process.env.OPENSEARCH_ENDPOINT || '',
            auth: {
                username: process.env.OPENSEARCH_USERNAME || '',
                password: process.env.OPENSEARCH_PASSWORD || '',
            },
        });
    }
    catch (e) {
        chatApiHelperLogger.error(e, 'unable to get credentials from getSearchClient');
    }
};
// Helper for resilient Postgraphile calls using got
const resilientGotPostPostgraphile = async (operationName, query, variables, userId) => {
    const MAX_RETRIES = 3;
    const INITIAL_TIMEOUT_MS = 10000; // 10 seconds for Postgraphile calls
    let attempt = 0;
    let lastError = null;
    const headers = {
        'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
        'Content-Type': 'application/json',
        'X-Postgraphile-Role': userId ? 'user' : 'admin',
    };
    if (userId) {
        headers['X-Postgraphile-User-Id'] = userId;
    }
    while (attempt < MAX_RETRIES) {
        try {
            chatApiHelperLogger.info(`Postgraphile call attempt ${attempt + 1} for ${operationName}`, { userId, operationName });
            const response = await got.post(postgraphileGraphUrl, {
                json: { operationName, query, variables },
                headers,
                timeout: { request: INITIAL_TIMEOUT_MS },
                responseType: 'json',
            }).json(); // Specify response type for got
            if (response.errors) {
                lastError = new Error(`GraphQL error in ${operationName}: ${JSON.stringify(response.errors)}`);
                // Potentially break here for non-retryable GraphQL errors, e.g. validation
                // For now, we retry all GraphQL errors from Postgraphile.
                throw lastError;
            }
            chatApiHelperLogger.info(`Postgraphile call ${operationName} successful on attempt ${attempt + 1}`, { userId, operationName });
            return response.data;
        }
        catch (error) {
            lastError = error;
            chatApiHelperLogger.warn(`Postgraphile call attempt ${attempt + 1} for ${operationName} failed.`, {
                userId,
                operationName,
                error: error.message,
                code: error.code,
                // response: error.response?.body
            });
            // Check for non-retryable HTTP errors from `got`
            if (error.response && error.response.statusCode) {
                const status = error.response.statusCode;
                if (status < 500 && status !== 429 && status !== 408) { // Don't retry client errors other than 429/408
                    chatApiHelperLogger.error(`Non-retryable HTTP error ${status} for ${operationName}. Aborting.`, { userId, operationName });
                    break;
                }
            }
            else if (!error.response && error.code && !['ETIMEDOUT', 'ECONNRESET', 'EADDRINUSE', 'ECONNREFUSED', 'EPIPE', 'ENETUNREACH', 'EAI_AGAIN'].includes(error.code)) {
                // If it's a got error without a response, but not a known retryable network error code, abort.
                chatApiHelperLogger.error(`Non-retryable got error code ${error.code} for ${operationName}. Aborting.`, { userId, operationName });
                break;
            }
        }
        attempt++;
        if (attempt < MAX_RETRIES) {
            const delay = Math.pow(2, attempt - 1) * 1000; // 1s, 2s
            chatApiHelperLogger.info(`Waiting ${delay}ms before Postgraphile retry ${attempt} for ${operationName}`, { userId, operationName });
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
    chatApiHelperLogger.error(`Failed Postgraphile operation '${operationName}' after ${attempt} attempts.`, { userId, operationName, lastError: lastError?.message });
    throw lastError || new Error(`Failed Postgraphile operation '${operationName}' after all retries.`);
};
export const searchSingleEventByVectorLanceDb = async (userId, searchVector) => {
    try {
        const results = await searchEvents(searchVector, 1, `userId = '${userId.replace(/'/g, "''")}'`);
        if (results && results.length > 0) {
            return results[0];
        }
        return null;
    }
    catch (e) {
        chatApiHelperLogger.error('Error in searchSingleEventByVectorLanceDb', { userId, error: e.message, stack: e.stack });
        throw e;
    }
};
export const searchSingleEventByVectorWithDatesLanceDb = async (userId, qVector, startDate, endDate) => {
    try {
        if (typeof qVector[0] !== 'number') {
            throw new Error('qVector is not a number array or is empty');
        }
        const filterCondition = `userId = '${userId.replace(/'/g, "''")}' AND start_date >= '${startDate}' AND end_date <= '${endDate}'`;
        const results = await searchEvents(qVector, 1, filterCondition);
        if (results && results.length > 0) {
            return results[0];
        }
        return null;
    }
    catch (e) {
        chatApiHelperLogger.error('Error in searchSingleEventByVectorWithDatesLanceDb', { userId, startDate, endDate, error: e.message, stack: e.stack });
        throw e;
    }
};
export const searchMultipleEventsByVectorWithDatesLanceDb = async (userId, qVector, startDate, endDate, limit = 10) => {
    try {
        if (typeof qVector[0] !== 'number') {
            throw new Error('qVector is not a number array or is empty');
        }
        const filterCondition = `userId = '${userId.replace(/'/g, "''")}' AND start_date >= '${startDate}' AND end_date <= '${endDate}'`;
        const results = await searchEvents(qVector, limit, filterCondition);
        return results || []; // Ensure an array is returned
    }
    catch (e) {
        chatApiHelperLogger.error('Error in searchMultipleEventsByVectorWithDatesLanceDb', { userId, startDate, endDate, limit, error: e.message, stack: e.stack });
        throw e;
    }
};
export const upsertConference = async (conference) => {
    try {
        const operationName = 'UpsertConference';
        const query = `
            mutation UpsertConference($conference: Conference_insert_input!) {
                insert_Conference_one(object: $conference, on_conflict: {constraint: Conference_pkey, update_columns: [
                    app,
                    deleted,
                    entryPoints,
                    hangoutLink,
                    iconUri,
                    isHost,
                    joinUrl,
                    key,
                    name,
                    notes,
                    parameters,
                    requestId,
                    startUrl,
                    status,
                    type,
                    updatedAt,
                    zoomPrivateMeeting,
                ]}) {
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
            conference
        };
        // const res: { data: { insert_Conference_one: ConferenceType } } = await got.post(postgraphileGraphUrl, {
        //     headers: {
        //         'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
        //         'X-Postgraphile-Role': 'admin'
        //     },
        //     json: {
        const responseData = await resilientGotPostPostgraphile(operationName, query, variables);
        chatApiHelperLogger.info('Successfully upserted conference', { conferenceId: responseData?.insert_Conference_one?.id });
        return responseData?.insert_Conference_one;
    }
    catch (e) {
        chatApiHelperLogger.error('Error in upsertConference', { error: e.message, conferenceData: conference });
        // Re-throw or handle as per function's contract, for now, let it propagate if resilientGotPostPostgraphile throws
        throw e;
    }
};
export const insertReminders = async (reminders) => {
    try {
        // validate
        if (!(reminders?.filter(e => !!(e?.eventId))?.length > 0)) {
            return;
        }
        reminders.forEach(r => chatApiHelperLogger.debug('Reminder object inside insertReminders loop', { reminder: r }));
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
            reminders
        };
        const responseData = await resilientGotPostPostgraphile(operationName, query, variables);
        if (responseData?.insert_Reminder?.returning) {
            chatApiHelperLogger.info('Successfully inserted reminders.', { count: responseData.insert_Reminder.returning.length });
            // responseData.insert_Reminder.returning.forEach(r => chatApiHelperLogger.debug('Inserted reminder details:', { reminder: r }));
        }
        else {
            chatApiHelperLogger.warn('InsertReminders call to Postgraphile did not return expected data structure.', { responseData });
        }
        // The function doesn't return anything in its original form, so we maintain that.
    }
    catch (e) {
        chatApiHelperLogger.error('Error in insertReminders', { error: e.message, remindersData: reminders });
        // Re-throw or handle as per function's contract
        throw e;
    }
};
export const upsertEvents = async (events) => {
    try {
        if (!(events?.length > 0)) {
            chatApiHelperLogger.info('No events found in upsertEvents, returning early.', { eventCount: events?.length });
            return;
        }
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
        // _.uniqBy(events, 'id').forEach(e => console.log(e?.id, e, 'id, e inside upsertEventsPostPlanner ')) // Original verbose log
        _.uniqBy(events, 'id').forEach(e => chatApiHelperLogger.debug('Event object inside upsertEventsPostPlanner loop (after uniqBy)', { eventId: e?.id, eventSummary: e?.summary }));
        const variables = {
            events: _.uniqBy(events, 'id'),
        };
        // const response: { data: { insert_Event: { affected_rows: number, returning: { id: string }[] } } } = await got.post(postgraphileGraphUrl, {
        //     headers: {
        //         'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
        //         'X-Postgraphile-Role': 'admin'
        //         variables,
        //     }
        const responseData = await resilientGotPostPostgraphile(operationName, query, variables);
        if (responseData?.insert_Event) {
            chatApiHelperLogger.info('Successfully upserted events.', { affected_rows: responseData.insert_Event.affected_rows, returned_ids: responseData.insert_Event.returning?.map(r => r.id) });
        }
        else {
            chatApiHelperLogger.warn('UpsertEvents call to Postgraphile did not return expected data structure.', { responseData });
        }
        // Original function returned the whole response object, so we mimic that structure if needed, or just the data part.
        // For now, let's return the 'data' part, assuming consumers expect that.
        // If the full Axios-like response was expected, this would need adjustment.
        // Given the type annotation of the original `response` variable, it seems it expected the `data` property.
        return { data: responseData };
    }
    catch (e) {
        chatApiHelperLogger.error('Error in upsertEvents', { error: e.message, eventCount: events.length });
        throw e;
    }
};
// Note: listAllEventWithEventOpenSearch is consolidated into searchMultipleEventsByVectorWithDatesLanceDb
export const putDataInTrainEventIndexInOpenSearch = async (id, vector, userId) => {
    try {
        const client = await getSearchClient();
        const response = await client.index({
            id,
            index: openTrainEventIndex,
            body: { [openTrainEventVectorName]: vector, userId },
            refresh: true
        });
        chatApiHelperLogger.info('Document added to OpenSearch train event index.', { documentId: id, responseBody: response.body });
    }
    catch (e) {
        chatApiHelperLogger.error('Unable to put data into OpenSearch train event index', { id, userId, error: e.message, stack: e.stack });
    }
};
export const getEventVectorFromLanceDb = async (id) => {
    try {
        const event = await getEventFromLanceDbById(id);
        return event?.vector || null;
    }
    catch (e) {
        chatApiHelperLogger.error(`Error fetching event vector for ID ${id} from LanceDB`, { eventId: id, error: e.message, stack: e.stack });
        return null;
    }
};
export const upsertEventToLanceDb = async (id, vector, userId, start_date, end_date, title) => {
    try {
        const eventEntry = {
            id,
            userId,
            vector,
            start_date,
            end_date,
            raw_event_text: title, // Or a more comprehensive text source
            title: title,
            last_modified: dayjs().toISOString(),
        };
        await upsertEvents([eventEntry]); // This internal call to upsertEvents already has logging
        chatApiHelperLogger.info(`Event ${id} upserted to LanceDB.`, { eventId: id, userId });
    }
    catch (e) {
        chatApiHelperLogger.error(`Error upserting event ${id} to LanceDB`, { eventId: id, userId, error: e.message, stack: e.stack });
        throw e;
    }
};
export const deleteEventFromLanceDb = async (id) => {
    try {
        await deleteEventsByIds([id]);
        chatApiHelperLogger.info(`Event ${id} deleted from LanceDB.`, { eventId: id });
    }
    catch (e) {
        chatApiHelperLogger.error(`Error deleting event ${id} from LanceDB`, { eventId: id, error: e.message, stack: e.stack });
        throw e;
    }
};
export const deleteTrainingDataFromLanceDb = async (id) => {
    try {
        await deleteTrainingEventsByIds([id]);
        chatApiHelperLogger.info(`Training data for ID ${id} deleted from LanceDB.`, { trainingDataId: id });
    }
    catch (e) {
        chatApiHelperLogger.error(`Error deleting training data for ID ${id} from LanceDB`, { trainingDataId: id, error: e.message, stack: e.stack });
        throw e;
    }
};
export const updateTrainingDataInLanceDb = async (id, vector, userId, source_event_text) => {
    try {
        const trainingEntry = {
            id,
            userId,
            vector,
            source_event_text,
            created_at: dayjs().toISOString(),
        };
        // Map to proper TrainingEventSchema
        const trainingEvent = {
            id: trainingEntry.id,
            userId: trainingEntry.userId || '',
            vector: trainingEntry.vector || [],
            start_date: trainingEntry.start_date || trainingEntry.startDate || dayjs().toISOString(),
            end_date: trainingEntry.end_date || trainingEntry.endDate || dayjs().toISOString(),
            source_event_text: trainingEntry.event_text || trainingEntry.title || '',
            created_at: trainingEntry.created_at || dayjs().toISOString()
        };
        await lancedbUpsertTrainingEvents([trainingEvent]);
        chatApiHelperLogger.info(`Training data for ID ${id} updated/upserted in LanceDB.`, { trainingDataId: id, userId });
    }
    catch (e) {
        chatApiHelperLogger.error(`Error updating training data for ID ${id} in LanceDB`, { trainingDataId: id, userId, error: e.message, stack: e.stack });
        throw e;
    }
};
export const searchTrainingDataFromLanceDb = async (userId, searchVector) => {
    try {
        const results = await searchTrainingEvents(searchVector, 1, `userId = '${userId.replace(/'/g, "''")}'`);
        if (results && results.length > 0) {
            return results[0];
        }
        return null;
    }
    catch (e) {
        chatApiHelperLogger.error('Error searching training data in LanceDB', { userId, error: e.message, stack: e.stack });
        throw e;
    }
};
export const convertEventTitleToOpenAIVector = async (title) => {
    try {
        const embeddingRequest = {
            model: 'text-embedding-3-small',
            input: title,
        };
        // const res = await openai.embeddings.create(embeddingRequest)
        // console.log(res, ' res inside convertEventTitleToOpenAIVectors')
        // return res?.data?.[0]?.embedding
        return await retry(async (bail, attemptNumber) => {
            try {
                chatApiHelperLogger.info(`Attempt ${attemptNumber} to get embedding for title: "${title.substring(0, 20)}..."`);
                const res = await openai.embeddings.create(embeddingRequest, { timeout: 15000 }); // 15s timeout
                if (!res?.data?.[0]?.embedding) {
                    chatApiHelperLogger.warn(`OpenAI embedding call for title "${title.substring(0, 20)}..." returned no embedding data on attempt ${attemptNumber}.`, { response: res });
                    throw new Error("No embedding data returned from OpenAI.");
                }
                chatApiHelperLogger.info(`Successfully got embedding for title "${title.substring(0, 20)}..." on attempt ${attemptNumber}.`);
                return res.data[0].embedding;
            }
            catch (error) {
                chatApiHelperLogger.warn(`Attempt ${attemptNumber} for OpenAI embedding for title "${title.substring(0, 20)}..." failed.`, {
                    error: error.message, code: error.code, status: error.response?.status
                });
                if (error.response && [400, 401, 403, 404].includes(error.response.status)) {
                    bail(error); // Non-retryable client errors
                    return;
                }
                throw error; // Retry for other errors (5xx, network, timeout)
            }
        }, {
            retries: 2, // Total 3 attempts
            factor: 2,
            minTimeout: 500,
            maxTimeout: 4000,
            onRetry: (error, attemptNumber) => {
                chatApiHelperLogger.warn(`Retrying OpenAI embedding for title "${title.substring(0, 20)}...", attempt ${attemptNumber}. Error: ${error.message}`);
            }
        });
    }
    catch (e) {
        chatApiHelperLogger.error('Failed to convert event title to OpenAI vector after all retries.', { title: title.substring(0, 20), error: e.message });
        throw e; // Re-throw the final error
    }
};
export const eventSearchBoundary = (timezone, dateJSONBody, currentTime) => {
    let startDate = '';
    let endDate = '';
    let dateA = '';
    let dateB = '';
    // set dateA
    if (dateJSONBody?.oldDate?.day) {
        dateA = `${dateJSONBody?.oldDate?.year || dayjs().format('YYYY')}-${dateJSONBody?.oldDate?.month || dayjs().format('MM')}-${dateJSONBody?.oldDate?.day || dayjs().tz(timezone).format('DD')}`;
    }
    else if (dateJSONBody?.oldDate?.isoWeekday) {
        const currentISODay = getISODay(dayjs().tz(timezone).toDate());
        const givenISODay = dateJSONBody?.oldDate?.isoWeekday;
        // add a week if givenISODay < currentISODay
        if (givenISODay < currentISODay) {
            const parsedPartialEndDate = dayjs(`${dateJSONBody?.oldDate?.year || dayjs().format('YYYY')}-${dateJSONBody?.oldDate?.month || dayjs().format('MM')}-${dateJSONBody?.oldDate?.day || dayjs().tz(timezone).format('DD')}`, 'YYYY-MM-DD');
            dateA = dayjs(setISODay(dayjs(parsedPartialEndDate, 'YYYY-MM-DD').tz(timezone, true).add(1, 'w').toDate(), givenISODay)).format('YYYY-MM-DD');
        }
        else {
            const parsedPartialEndDate = dayjs(`${dateJSONBody?.oldDate?.year || dayjs().format('YYYY')}-${dateJSONBody?.oldDate?.month || dayjs().format('MM')}-${dateJSONBody?.oldDate?.day || dayjs().tz(timezone).format('DD')}`, 'YYYY-MM-DD');
            dateA = dayjs(setISODay(dayjs(parsedPartialEndDate, 'YYYY-MM-DD').tz(timezone, true).toDate(), givenISODay)).format('YYYY-MM-DD');
        }
    }
    else if (dateJSONBody?.oldDate?.relativeTimeFromNow?.[0]) {
        if (dateJSONBody?.oldDate?.relativeTimeChangeFromNow === 'add') {
            // loop through all possible values
            let day = 0;
            let week = 0;
            let month = 0;
            let year = 0;
            for (const relativeTimeObject of dateJSONBody?.oldDate?.relativeTimeFromNow) {
                if (relativeTimeObject?.unit === 'day') {
                    if (relativeTimeObject?.value > 0) {
                        day += relativeTimeObject?.value;
                    }
                }
                else if (relativeTimeObject?.unit === 'week') {
                    if (relativeTimeObject?.value > 0) {
                        week += relativeTimeObject?.value;
                    }
                }
                else if (relativeTimeObject?.unit === 'month') {
                    if (relativeTimeObject?.value > 0) {
                        month += relativeTimeObject?.value;
                    }
                }
                else if (relativeTimeObject?.unit === 'year') {
                    if (relativeTimeObject?.value > 0) {
                        year += relativeTimeObject?.value;
                    }
                }
            }
            dateA = dayjs(currentTime, 'YYYY-MM-DD').tz(timezone, true)
                .add(day, 'd')
                .add(week, 'w')
                .add(month, 'M')
                .add(year, 'y')
                .format('YYYYY-MM-DD');
        }
        else if (dateJSONBody?.oldDate?.relativeTimeChangeFromNow === 'subtract') {
            let day = 0;
            let week = 0;
            let month = 0;
            let year = 0;
            for (const relativeTimeObject of dateJSONBody?.oldDate?.relativeTimeFromNow) {
                if (relativeTimeObject?.unit === 'day') {
                    if (relativeTimeObject?.value > 0) {
                        day += relativeTimeObject?.value;
                    }
                }
                else if (relativeTimeObject?.unit === 'week') {
                    if (relativeTimeObject?.value > 0) {
                        week += relativeTimeObject?.value;
                    }
                }
                else if (relativeTimeObject?.unit === 'month') {
                    if (relativeTimeObject?.value > 0) {
                        month += relativeTimeObject?.value;
                    }
                }
                else if (relativeTimeObject?.unit === 'year') {
                    if (relativeTimeObject?.value > 0) {
                        year += relativeTimeObject?.value;
                    }
                }
            }
            dateA = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true)
                .subtract(day, 'd')
                .subtract(week, 'w')
                .subtract(month, 'M')
                .subtract(year, 'y')
                .format();
        }
    }
    // set dateB
    if (dateJSONBody?.day) {
        dateB = `${dateJSONBody?.year || dayjs().format('YYYY')}-${dateJSONBody?.month || dayjs().format('MM')}-${dateJSONBody?.day || dayjs().tz(timezone).format('DD')}`;
        // if isoWeekday -> user intent is current week
    }
    else if (dateJSONBody?.isoWeekday) {
        const currentISODay = getISODay(dayjs().tz(timezone).toDate());
        const givenISODay = dateJSONBody.isoWeekday;
        // add a week if givenISODay < currentISODay
        if (givenISODay < currentISODay) {
            const parsedPartialEndDate = dayjs(`${dateJSONBody?.year || dayjs().format('YYYY')}-${dateJSONBody?.month || dayjs().format('MM')}-${dateJSONBody?.day || dayjs().tz(timezone).format('DD')}`, 'YYYY-MM-DD');
            dateB = dayjs(setISODay(dayjs(parsedPartialEndDate, 'YYYY-MM-DD').tz(timezone, true).add(1, 'w').toDate(), givenISODay)).format('YYYY-MM-DD');
        }
        else {
            const parsedPartialEndDate = dayjs(`${dateJSONBody?.year || dayjs().format('YYYY')}-${dateJSONBody?.month || dayjs().format('MM')}-${dateJSONBody?.day || dayjs().tz(timezone).format('DD')}`, 'YYYY-MM-DD');
            dateB = dayjs(setISODay(dayjs(parsedPartialEndDate, 'YYYY-MM-DD').tz(timezone, true).toDate(), givenISODay)).format('YYYY-MM-DD');
        }
    }
    else if (dateJSONBody?.relativeTimeFromNow?.[0]) {
        if (dateJSONBody?.relativeTimeChangeFromNow === 'add') {
            // loop through all possible values
            let day = 0;
            let week = 0;
            let month = 0;
            let year = 0;
            for (const relativeTimeObject of dateJSONBody?.relativeTimeFromNow) {
                if (relativeTimeObject?.unit === 'day') {
                    if (relativeTimeObject?.value > 0) {
                        day += relativeTimeObject?.value;
                    }
                }
                else if (relativeTimeObject?.unit === 'week') {
                    if (relativeTimeObject?.value > 0) {
                        week += relativeTimeObject?.value;
                    }
                }
                else if (relativeTimeObject?.unit === 'month') {
                    if (relativeTimeObject?.value > 0) {
                        month += relativeTimeObject?.value;
                    }
                }
                else if (relativeTimeObject?.unit === 'year') {
                    if (relativeTimeObject?.value > 0) {
                        year += relativeTimeObject?.value;
                    }
                }
            }
            dateB = dayjs(dateA, 'YYYY-MM-DDTHH:mm').tz(timezone, true)
                .add(day, 'd')
                .add(week, 'w')
                .add(month, 'M')
                .add(year, 'y')
                .format();
        }
        else if (dateJSONBody?.relativeTimeChangeFromNow === 'subtract') {
            let day = 0;
            let week = 0;
            let month = 0;
            let year = 0;
            for (const relativeTimeObject of dateJSONBody?.relativeTimeFromNow) {
                if (relativeTimeObject?.unit === 'day') {
                    if (relativeTimeObject?.value > 0) {
                        day += relativeTimeObject?.value;
                    }
                }
                else if (relativeTimeObject?.unit === 'week') {
                    if (relativeTimeObject?.value > 0) {
                        week += relativeTimeObject?.value;
                    }
                }
                else if (relativeTimeObject?.unit === 'month') {
                    if (relativeTimeObject?.value > 0) {
                        month += relativeTimeObject?.value;
                    }
                }
                else if (relativeTimeObject?.unit === 'year') {
                    if (relativeTimeObject?.value > 0) {
                        year += relativeTimeObject?.value;
                    }
                }
            }
            dateB = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true)
                .subtract(day, 'd')
                .subtract(week, 'w')
                .subtract(month, 'M')
                .subtract(year, 'y')
                .format();
        }
    }
    if (dateA && dateB) {
        if (dayjs(dateA).isBefore(dayjs(dateB, 'day'))) {
            startDate = dayjs(dateA, 'YYYY-MM-DD').subtract(1, 'd').format('YYYY-MM-DD');
            endDate = dayjs(dateB, 'YYYY-MM-DD').add(1, 'd').format('YYYY-MM-DD');
        }
        else if (dayjs(dateB).isBefore(dayjs(dateA, 'day'))) {
            startDate = dayjs(dateB, 'YYYY-MM-DD').subtract(1, 'd').format('YYYY-MM-DD');
            endDate = dayjs(dateA, 'YYYY-MM-DD').add(1, 'd').format('YYYY-MM-DD');
        }
    }
    else if (dateA && !dateB) {
        startDate = dayjs(dateA, 'YYYY-MM-DD').subtract(1, 'd').format('YYYY-MM-DD');
        endDate = dayjs(startDate).tz(timezone, true).add(4, 'w').format('YYYY-MM-DD');
    }
    else if (dateB && !dateA) {
        startDate = dayjs(dateB, 'YYYY-MM-DD').subtract(1, 'd').format('YYYY-MM-DD');
        endDate = dayjs(startDate).tz(timezone, true).add(4, 'w').format('YYYY-MM-DD');
    }
    return {
        startDate,
        endDate,
    };
};
export const extrapolateDateFromJSONData = (currentTime, timezone, year, month, day, isoWeekday, hour, minute, time, relativeTimeChangeFromNow, relativeTimeFromNow) => {
    let meetingStartDate = '';
    let meetingStartDateObject = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true);
    const functionName = 'extrapolateDateFromJSONData';
    chatApiHelperLogger.debug(`[${functionName}] Initial params:`, { currentTime, timezone, year, month, day, isoWeekday, hour, minute, time, relativeTimeChangeFromNow, relativeTimeFromNow });
    if (day) {
        if ((!!hour) && (!!minute)) {
            if (year && month) {
                const yearAndMonthAndDate = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true);
                chatApiHelperLogger.debug(`[${functionName}] Condition: day, hour, minute, year, month`, { yearAndMonthAndDateFormatted: yearAndMonthAndDate.format() });
                meetingStartDateObject = meetingStartDateObject
                    .year(yearAndMonthAndDate.year())
                    .month(yearAndMonthAndDate.month())
                    .date(yearAndMonthAndDate.date())
                    .hour(hour)
                    .minute(minute);
                chatApiHelperLogger.debug(`[${functionName}] meetingStartDateObject updated (day, hour, minute, year, month):`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            }
            else {
                const dateOfMonth = dayjs(day, 'DD').tz(timezone, true);
                chatApiHelperLogger.debug(`[${functionName}] Condition: day, hour, minute (no year/month)`, { dateOfMonthFormatted: dateOfMonth.format() });
                meetingStartDateObject = meetingStartDateObject
                    .date(dateOfMonth.date())
                    .hour(hour)
                    .minute(minute);
                chatApiHelperLogger.debug(`[${functionName}] meetingStartDateObject updated (day, hour, minute):`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            }
        }
        else if (time) {
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}-${day} ${time}`, 'YYYY-MM-DD HH:mm').tz(timezone, true);
                chatApiHelperLogger.debug(`[${functionName}] Condition: day, time, year, month`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            }
            else {
                meetingStartDateObject = dayjs(`${day} ${time}`, 'DD HH:mm').tz(timezone, true);
                chatApiHelperLogger.debug(`[${functionName}] Condition: day, time (no year/month)`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            }
        }
        else if (!time && !hour && !minute) { // All day event inferred
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true);
                chatApiHelperLogger.debug(`[${functionName}] Condition: day, year, month (all day)`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            }
            else {
                meetingStartDateObject = dayjs(day, 'DD').tz(timezone, true);
                chatApiHelperLogger.debug(`[${functionName}] Condition: day (all day, no year/month)`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            }
        }
    }
    else if (isoWeekday) {
        const givenISODay = isoWeekday;
        const currentISODay = getISODay(dayjs(currentTime).tz(timezone, true).toDate());
        chatApiHelperLogger.debug(`[${functionName}] Condition: isoWeekday`, { givenISODay, currentISODay });
        if ((!!hour) && (!!minute)) {
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                    .hour(hour)
                    .minute(minute);
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday, hour, minute, year, month - base:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                if (givenISODay < currentISODay) {
                    meetingStartDateObject = dayjs(setISODay(meetingStartDateObject.add(1, 'w').toDate(), givenISODay));
                    chatApiHelperLogger.debug(`[${functionName}] isoWeekday adjusted (past day this week, add week):`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                }
                else {
                    meetingStartDateObject = dayjs(setISODay(meetingStartDateObject.toDate(), givenISODay));
                    chatApiHelperLogger.debug(`[${functionName}] isoWeekday adjusted (future/current day this week):`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                }
            }
            else {
                meetingStartDateObject = dayjs().tz(timezone, true)
                    .hour(hour)
                    .minute(minute);
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday, hour, minute (no year/month) - base:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                if (givenISODay < currentISODay) {
                    meetingStartDateObject = dayjs(setISODay(meetingStartDateObject.add(1, 'w').toDate(), givenISODay));
                    chatApiHelperLogger.debug(`[${functionName}] isoWeekday adjusted (past day this week, add week):`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                }
                else {
                    meetingStartDateObject = dayjs(setISODay(meetingStartDateObject.toDate(), givenISODay));
                    chatApiHelperLogger.debug(`[${functionName}] isoWeekday adjusted (future/current day this week):`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                }
            }
        }
        else if (time) {
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month} ${time}`, 'YYYY-MM HH:mm').tz(timezone, true);
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday, time, year, month - base:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                if (givenISODay < currentISODay) {
                    meetingStartDateObject = dayjs(setISODay(meetingStartDateObject.add(1, 'w').toDate(), givenISODay));
                }
                else {
                    meetingStartDateObject = dayjs(setISODay(meetingStartDateObject.toDate(), givenISODay));
                }
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday, time, year, month - adjusted:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            }
            else {
                meetingStartDateObject = dayjs(`${time}`, 'HH:mm').tz(timezone, true);
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday, time (no year/month) - base:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                if (givenISODay < currentISODay) {
                    meetingStartDateObject = dayjs(setISODay(meetingStartDateObject.add(1, 'w').toDate(), givenISODay));
                }
                else {
                    meetingStartDateObject = dayjs(setISODay(meetingStartDateObject.toDate(), givenISODay));
                }
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday, time (no year/month) - adjusted:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            }
        }
        else if (!hour && !minute && !time) { // All day for isoWeekday
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true);
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday, year, month (all day) - base:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                if (givenISODay < currentISODay) {
                    meetingStartDateObject = dayjs(setISODay(meetingStartDateObject.add(1, 'w').toDate(), givenISODay));
                }
                else {
                    meetingStartDateObject = dayjs(setISODay(meetingStartDateObject.toDate(), givenISODay));
                }
                // Utility function to safely extract GraphQL data from got responses
                const safeExtractGraphQLData = (response) => {
                    try {
                        if (response && response.data) {
                            return response.data;
                        }
                        if (response && response.body) {
                            const parsed = JSON.parse(response.body);
                            return parsed?.data || parsed;
                        }
                        return response;
                    }
                    catch (error) {
                        return response;
                    }
                };
                // Safe wrapper for got responses with proper typing
                const gotResponseHandler = async (promise) => {
                    const response = await promise;
                    if (response.data) {
                        return response.data;
                    }
                    try {
                        return JSON.parse(response.body).data;
                    }
                    catch {
                        throw new Error('Invalid response format');
                    }
                };
            }
            else {
                meetingStartDateObject = dayjs().tz(timezone, true);
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday (all day, no year/month) - base:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                if (givenISODay < currentISODay) {
                    meetingStartDateObject = dayjs(setISODay(meetingStartDateObject.add(1, 'w').toDate(), givenISODay));
                }
                else {
                    meetingStartDateObject = dayjs(setISODay(meetingStartDateObject.toDate(), givenISODay));
                }
            }
            chatApiHelperLogger.debug(`[${functionName}] isoWeekday (all day) - adjusted:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
        }
    }
    else if (relativeTimeFromNow?.[0]) {
        let minuteChanged = false;
        let hourChanged = false;
        let calculatedMinute = 0, calculatedHour = 0, calculatedDay = 0, calculatedWeek = 0, calculatedMonth = 0, calculatedYear = 0;
        for (const relativeTimeObject of relativeTimeFromNow) {
            if (relativeTimeObject?.value > 0) {
                switch (relativeTimeObject.unit) {
                    case 'minute':
                        calculatedMinute += relativeTimeObject.value;
                        minuteChanged = true;
                        break;
                    case 'hour':
                        calculatedHour += relativeTimeObject.value;
                        hourChanged = true;
                        break;
                    case 'day':
                        calculatedDay += relativeTimeObject.value;
                        break;
                    case 'week':
                        calculatedWeek += relativeTimeObject.value;
                        break;
                    case 'month':
                        calculatedMonth += relativeTimeObject.value;
                        break;
                    case 'year':
                        calculatedYear += relativeTimeObject.value;
                        break;
                }
            }
        }
        chatApiHelperLogger.debug(`[${functionName}] Condition: relativeTimeFromNow - calculated offsets:`, { calculatedMinute, calculatedHour, calculatedDay, calculatedWeek, calculatedMonth, calculatedYear, relativeTimeChangeFromNow });
        if ((relativeTimeChangeFromNow === 'add') || (relativeTimeChangeFromNow === null)) {
            meetingStartDateObject = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true) // Use full currentTime if adding time parts
                .add(calculatedMinute, 'm')
                .add(calculatedHour, 'h')
                .add(calculatedDay, 'd')
                .add(calculatedWeek, 'w')
                .add(calculatedMonth, 'M')
                .add(calculatedYear, 'y');
            chatApiHelperLogger.debug(`[${functionName}] relativeTime - add operation:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
        }
        else if (relativeTimeChangeFromNow === 'subtract') {
            meetingStartDateObject = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true)
                .subtract(calculatedMinute, 'm')
                .subtract(calculatedHour, 'h')
                .subtract(calculatedDay, 'd')
                .subtract(calculatedWeek, 'w')
                .subtract(calculatedMonth, 'M')
                .subtract(calculatedYear, 'y');
            chatApiHelperLogger.debug(`[${functionName}] relativeTime - subtract operation:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
        }
        // Apply explicit hour/minute/time if provided, potentially overriding relative calculation for time part
        if ((!!hour) && (!!minute)) {
            if (year && month) {
                const yearAndMonth = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true);
                meetingStartDateObject = meetingStartDateObject.year(yearAndMonth.year()).month(yearAndMonth.month());
            }
            meetingStartDateObject = meetingStartDateObject.hour(hour).minute(minute);
            chatApiHelperLogger.debug(`[${functionName}] relativeTime with explicit hour/minute override:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format(), year, month });
        }
        else if (time) {
            const tempTime = dayjs(time, 'HH:mm').tz(timezone, true);
            if (year && month) {
                const yearAndMonth = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true);
                meetingStartDateObject = meetingStartDateObject.year(yearAndMonth.year()).month(yearAndMonth.month());
            }
            meetingStartDateObject = meetingStartDateObject.hour(tempTime.hour()).minute(tempTime.minute());
            chatApiHelperLogger.debug(`[${functionName}] relativeTime with explicit time override:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format(), year, month });
        }
        else if (!hourChanged && !minuteChanged) { // If no relative minute/hour and no explicit time, apply just year/month if given
            if (year && month) {
                const yearAndMonth = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true);
                meetingStartDateObject = meetingStartDateObject.year(yearAndMonth.year()).month(yearAndMonth.month());
                chatApiHelperLogger.debug(`[${functionName}] relativeTime with explicit year/month (no time parts changed):`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            }
        }
    }
    chatApiHelperLogger.debug(`[${functionName}] Final meetingStartDateObject:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
    meetingStartDate = meetingStartDateObject.format();
    return meetingStartDate;
};
export const extrapolateStartDateFromJSONData = (currentTime, timezone, year, month, day, isoWeekday, hour, minute, time, relativeTimeChangeFromNow, relativeTimeFromNow) => {
    // This function is very similar to extrapolateDateFromJSONData, but sets time to 00:00 if not specified.
    // For brevity, detailed logging for each path is omitted if it's identical to the above, focusing on differences.
    let meetingStartDate = '';
    let meetingStartDateObject = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true);
    const functionName = 'extrapolateStartDateFromJSONData'; // For specific logging if needed
    chatApiHelperLogger.debug(`[${functionName}] Initial params:`, { currentTime, timezone, year, month, day, isoWeekday, hour, minute, time, relativeTimeChangeFromNow, relativeTimeFromNow });
    if (day) {
        if ((!!hour) && (!!minute)) {
            if (year && month) {
                const yearAndMonthAndDate = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true);
                meetingStartDateObject = meetingStartDateObject.year(yearAndMonthAndDate.year()).month(yearAndMonthAndDate.month()).date(yearAndMonthAndDate.date()).hour(hour).minute(minute);
            }
            else {
                const dateOfMonth = dayjs(day, 'DD').tz(timezone, true);
                meetingStartDateObject = meetingStartDateObject.date(dateOfMonth.date()).hour(hour).minute(minute);
            }
        }
        else if (time) {
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}-${day} ${time}`, 'YYYY-MM-DD HH:mm').tz(timezone, true);
            }
            else {
                meetingStartDateObject = dayjs(`${day} ${time}`, 'DD HH:mm').tz(timezone, true);
            }
        }
        else if (!time && !hour && !minute) { // All day event, start at 00:00
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true).hour(0).minute(0);
            }
            else {
                meetingStartDateObject = dayjs(day, 'DD').tz(timezone, true).hour(0).minute(0);
            }
            chatApiHelperLogger.debug(`[${functionName}] Day specified, no time - setting to 00:00`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
        }
    }
    else if (isoWeekday) {
        const givenISODay = isoWeekday;
        const currentISODay = getISODay(dayjs(currentTime).tz(timezone, true).toDate());
        let baseDateObj;
        if ((!!hour) && (!!minute)) {
            baseDateObj = year && month ? dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true) : dayjs().tz(timezone, true);
            baseDateObj = baseDateObj.hour(hour).minute(minute);
        }
        else if (time) {
            baseDateObj = year && month ? dayjs(`${year}-${month} ${time}`, 'YYYY-MM HH:mm').tz(timezone, true) : dayjs(time, 'HH:mm').tz(timezone, true);
        }
        else { // All day for isoWeekday, start at 00:00
            baseDateObj = year && month ? dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true) : dayjs().tz(timezone, true);
            baseDateObj = baseDateObj.hour(0).minute(0);
            chatApiHelperLogger.debug(`[${functionName}] ISO Weekday specified, no time - setting to 00:00 for base`, { baseDateObjFormatted: baseDateObj.format() });
        }
        meetingStartDateObject = givenISODay < currentISODay ? dayjs(setISODay(baseDateObj.add(1, 'w').toDate(), givenISODay)) : dayjs(setISODay(baseDateObj.toDate(), givenISODay));
    }
    else if (relativeTimeFromNow?.[0]) {
        let minuteChanged = false, hourChanged = false;
        let calculatedMinute = 0, calculatedHour = 0, calculatedDay = 0, calculatedWeek = 0, calculatedMonth = 0, calculatedYear = 0;
        for (const relativeTimeObject of relativeTimeFromNow) {
            if (relativeTimeObject?.value > 0) {
                switch (relativeTimeObject.unit) {
                    case 'minute':
                        calculatedMinute += relativeTimeObject.value;
                        minuteChanged = true;
                        break;
                    case 'hour':
                        calculatedHour += relativeTimeObject.value;
                        hourChanged = true;
                        break;
                    case 'day':
                        calculatedDay += relativeTimeObject.value;
                        break;
                    case 'week':
                        calculatedWeek += relativeTimeObject.value;
                        break;
                    case 'month':
                        calculatedMonth += relativeTimeObject.value;
                        break;
                    case 'year':
                        calculatedYear += relativeTimeObject.value;
                        break;
                }
            }
        }
        const baseCurrentTime = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true); // Ensure we use full current time for subtractions
        if ((relativeTimeChangeFromNow === 'add') || (relativeTimeChangeFromNow === null)) {
            meetingStartDateObject = baseCurrentTime
                .add(calculatedMinute, 'm').add(calculatedHour, 'h')
                .add(calculatedDay, 'd').add(calculatedWeek, 'w')
                .add(calculatedMonth, 'M').add(calculatedYear, 'y');
        }
        else if (relativeTimeChangeFromNow === 'subtract') {
            meetingStartDateObject = baseCurrentTime
                .subtract(calculatedMinute, 'm').subtract(calculatedHour, 'h')
                .subtract(calculatedDay, 'd').subtract(calculatedWeek, 'w')
                .subtract(calculatedMonth, 'M').subtract(calculatedYear, 'y');
        }
        if ((!!hour) && (!!minute)) {
            if (year && month)
                meetingStartDateObject = meetingStartDateObject.year(dayjs(`${year}-${month}`, 'YYYY-MM').year()).month(dayjs(`${year}-${month}`, 'YYYY-MM').month());
            meetingStartDateObject = meetingStartDateObject.hour(hour).minute(minute);
        }
        else if (time) {
            const tempTime = dayjs(time, 'HH:mm').tz(timezone, true);
            if (year && month)
                meetingStartDateObject = meetingStartDateObject.year(dayjs(`${year}-${month}`, 'YYYY-MM').year()).month(dayjs(`${year}-${month}`, 'YYYY-MM').month());
            meetingStartDateObject = meetingStartDateObject.hour(tempTime.hour()).minute(tempTime.minute());
        }
        else if (!hourChanged && !minuteChanged) { // No relative time parts, no explicit time parts -> set to 00:00
            if (year && month)
                meetingStartDateObject = meetingStartDateObject.year(dayjs(`${year}-${month}`, 'YYYY-MM').year()).month(dayjs(`${year}-${month}`, 'YYYY-MM').month());
            meetingStartDateObject = meetingStartDateObject.hour(0).minute(0);
            chatApiHelperLogger.debug(`[${functionName}] Relative day/week/month/year, no time parts - setting to 00:00`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
        }
    }
    chatApiHelperLogger.debug(`[${functionName}] Final meetingStartDateObject:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
    meetingStartDate = meetingStartDateObject.format();
    return meetingStartDate;
};
export const extrapolateEndDateFromJSONData = (currentTime, timezone, year, month, day, isoWeekday, hour, minute, time, relativeTimeChangeFromNow, relativeTimeFromNow) => {
    // This function is very similar to extrapolateDateFromJSONData, but sets time to 23:59 if not specified.
    let meetingEndDate = '';
    let meetingEndDateObject = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true);
    const functionName = 'extrapolateEndDateFromJSONData';
    chatApiHelperLogger.debug(`[${functionName}] Initial params:`, { currentTime, timezone, year, month, day, isoWeekday, hour, minute, time, relativeTimeChangeFromNow, relativeTimeFromNow });
    if (day) {
        if ((!!hour) && (!!minute)) {
            if (year && month) {
                const yearAndMonthAndDate = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true);
                meetingEndDateObject = meetingEndDateObject.year(yearAndMonthAndDate.year()).month(yearAndMonthAndDate.month()).date(yearAndMonthAndDate.date()).hour(hour).minute(minute);
            }
            else {
                const dateOfMonth = dayjs(day, 'DD').tz(timezone, true);
                meetingEndDateObject = meetingEndDateObject.date(dateOfMonth.date()).hour(hour).minute(minute);
            }
        }
        else if (time) {
            if (year && month) {
                meetingEndDateObject = dayjs(`${year}-${month}-${day} ${time}`, 'YYYY-MM-DD HH:mm').tz(timezone, true);
            }
            else {
                meetingEndDateObject = dayjs(`${day} ${time}`, 'DD HH:mm').tz(timezone, true);
            }
        }
        else if (!time && !hour && !minute) { // All day event, end at 23:59
            if (year && month) {
                meetingEndDateObject = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true).hour(23).minute(59);
            }
            else {
                meetingEndDateObject = dayjs(day, 'DD').tz(timezone, true).hour(23).minute(59);
            }
            chatApiHelperLogger.debug(`[${functionName}] Day specified, no time - setting to 23:59`, { meetingEndDateObjectFormatted: meetingEndDateObject.format() });
        }
    }
    else if (isoWeekday) {
        const givenISODay = isoWeekday;
        const currentISODay = getISODay(dayjs(currentTime).tz(timezone, true).toDate());
        let baseDateObj;
        if ((!!hour) && (!!minute)) {
            baseDateObj = year && month ? dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true) : dayjs().tz(timezone, true);
            baseDateObj = baseDateObj.hour(hour).minute(minute);
        }
        else if (time) {
            baseDateObj = year && month ? dayjs(`${year}-${month} ${time}`, 'YYYY-MM HH:mm').tz(timezone, true) : dayjs(time, 'HH:mm').tz(timezone, true);
        }
        else { // All day for isoWeekday, end at 23:59
            baseDateObj = year && month ? dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true) : dayjs().tz(timezone, true);
            baseDateObj = baseDateObj.hour(23).minute(59);
            chatApiHelperLogger.debug(`[${functionName}] ISO Weekday specified, no time - setting to 23:59 for base`, { baseDateObjFormatted: baseDateObj.format() });
        }
        meetingEndDateObject = givenISODay < currentISODay ? dayjs(setISODay(baseDateObj.add(1, 'w').toDate(), givenISODay)) : dayjs(setISODay(baseDateObj.toDate(), givenISODay));
    }
    // This 'else if' was incorrectly placed inside the isoWeekday block in the original. It should be at the same level.
    // Assuming it's intended to be an alternative to 'day' and 'isoWeekday' for the main date calculation.
    // However, the logic for relativeTimeFromNow in the original function for extrapolateEndDateFromJSONData *adds* to the *already calculated* meetingEndDateObject.
    // This is different from how extrapolateDateFromJSONData handles it (where it's an alternative initial calculation path).
    // Replicating the original behavior for extrapolateEndDateFromJSONData:
    if (relativeTimeFromNow?.[0]) { // This applies *after* day/isoWeekday logic if any
        let minuteChanged = false, hourChanged = false;
        let calculatedMinute = 0, calculatedHour = 0, calculatedDay = 0, calculatedWeek = 0, calculatedMonth = 0, calculatedYear = 0;
        for (const relativeTimeObject of relativeTimeFromNow) {
            if (relativeTimeObject?.value > 0) {
                switch (relativeTimeObject.unit) {
                    case 'minute':
                        calculatedMinute += relativeTimeObject.value;
                        minuteChanged = true;
                        break;
                    case 'hour':
                        calculatedHour += relativeTimeObject.value;
                        hourChanged = true;
                        break;
                    case 'day':
                        calculatedDay += relativeTimeObject.value;
                        break;
                    case 'week':
                        calculatedWeek += relativeTimeObject.value;
                        break;
                    case 'month':
                        calculatedMonth += relativeTimeObject.value;
                        break;
                    case 'year':
                        calculatedYear += relativeTimeObject.value;
                        break;
                }
            }
        }
        chatApiHelperLogger.debug(`[${functionName}] Applying relativeTimeFromNow adjustments:`, { calculatedMinute, calculatedHour, calculatedDay, calculatedWeek, calculatedMonth, calculatedYear, relativeTimeChangeFromNow });
        if ((relativeTimeChangeFromNow === 'add') || (relativeTimeChangeFromNow === null)) {
            meetingEndDateObject = meetingEndDateObject
                .add(calculatedMinute, 'm').add(calculatedHour, 'h')
                .add(calculatedDay, 'd').add(calculatedWeek, 'w')
                .add(calculatedMonth, 'M').add(calculatedYear, 'y');
        }
        else if (relativeTimeChangeFromNow === 'subtract') {
            meetingEndDateObject = meetingEndDateObject
                .subtract(calculatedMinute, 'm').subtract(calculatedHour, 'h')
                .subtract(calculatedDay, 'd').subtract(calculatedWeek, 'w')
                .subtract(calculatedMonth, 'M').subtract(calculatedYear, 'y');
        }
        // If explicit hour/minute/time are given, they might override the time part of relative calculation or adjust the existing one.
        // The original logic for EndDate didn't seem to re-apply explicit hour/minute if relative time was also given,
        // unless it was to set to 23:59 if no time parts were changed by relativeTime and no explicit time.
        // This part is tricky to replicate perfectly without ambiguity from original console logs.
        // The primary difference for EndDate was setting to 23:59 if it was an "all-day" type of relative adjustment.
        if ((!!hour) && (!!minute)) { // Explicit hour/minute given
            if (year && month)
                meetingEndDateObject = meetingEndDateObject.year(dayjs(`${year}-${month}`, 'YYYY-MM').year()).month(dayjs(`${year}-${month}`, 'YYYY-MM').month());
            meetingEndDateObject = meetingEndDateObject.hour(hour).minute(minute);
            chatApiHelperLogger.debug(`[${functionName}] Relative time applied, then explicit hour/minute:`, { meetingEndDateObjectFormatted: meetingEndDateObject.format() });
        }
        else if (time) { // Explicit time given
            const tempTime = dayjs(time, 'HH:mm').tz(timezone, true);
            if (year && month)
                meetingEndDateObject = meetingEndDateObject.year(dayjs(`${year}-${month}`, 'YYYY-MM').year()).month(dayjs(`${year}-${month}`, 'YYYY-MM').month());
            meetingEndDateObject = meetingEndDateObject.hour(tempTime.hour()).minute(tempTime.minute());
            chatApiHelperLogger.debug(`[${functionName}] Relative time applied, then explicit time:`, { meetingEndDateObjectFormatted: meetingEndDateObject.format() });
        }
        else if (!hourChanged && !minuteChanged) { // No relative minute/hour adjustments, and no explicit time/hour/minute
            // This implies it might be an "all-day" type of relative adjustment (e.g., "next week")
            // So, set time to end of day.
            if (year && month)
                meetingEndDateObject = meetingEndDateObject.year(dayjs(`${year}-${month}`, 'YYYY-MM').year()).month(dayjs(`${year}-${month}`, 'YYYY-MM').month());
            meetingEndDateObject = meetingEndDateObject.hour(23).minute(59);
            chatApiHelperLogger.debug(`[${functionName}] Relative day/week/etc applied (no time parts), setting to 23:59:`, { meetingEndDateObjectFormatted: meetingEndDateObject.format() });
        }
    }
    chatApiHelperLogger.debug(`[${functionName}] Final meetingEndDateObject:`, { meetingEndDateObjectFormatted: meetingEndDateObject.format() });
    meetingEndDate = meetingEndDateObject.format();
    return meetingEndDate;
};
export const getGlobalCalendar = async (userId) => {
    const operationName = 'getGlobalCalendar'; // Defined operationName for logging and Postgraphile call
    try {
        // const operationName = 'getGlobalCalendar' // Original position, removed as it's defined above
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
    `; // query remains the same
        // Removed direct got.post call and /* */ block
        // const res: { data: { Calendar: CalendarType[] } } = await got.post(
        //     postgraphileGraphUrl,
        //     {
        //         headers: {
        //             'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
        //             'Content-Type': 'application/json',
        //             'X-Postgraphile-Role': 'admin'
        //         },
        //         json: {
        //             operationName,
        //             query,
        //             variables: {
        //                 userId,
        //             },
        //         },
        //     },
        // ).json()
        // */
        // Using resilientGotPostPostgraphile for the Postgraphile call
        // Assuming 'admin' role for this query as per original direct got call.
        const responseData = await resilientGotPostPostgraphile(operationName, query, { userId } /*, userId (if user role needed) */);
        if (responseData && responseData.Calendar && responseData.Calendar.length > 0) {
            chatApiHelperLogger.info(`${operationName} successful for user ${userId}. Calendar ID: ${responseData.Calendar[0].id}`);
            return responseData.Calendar[0];
        }
        else {
            chatApiHelperLogger.info(`${operationName}: No global primary calendar found for user ${userId}.`);
            return undefined; // Or null, depending on desired contract for "not found"
        }
    }
    catch (e) {
        chatApiHelperLogger.error(`Error in ${operationName} for user ${userId}`, { error: e.message });
        // resilientGotPostPostgraphile will throw on failure after retries, so this catch block will handle that.
        throw e;
    }
};
export const getCalendarIntegrationByResource = async (userId, resource) => {
    try {
        const operationName = 'getCalendarIntegrationByResource';
        const query = `
      query getCalendarIntegrationByResource($userId: uuid!, $resource: String!) {
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
        const res = await got.post(postgraphileGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin'
            },
        }).json();
        console.log(res, ' res inside getCalendarIntegration');
        if (res?.data?.Calendar_Integration?.length > 0) {
            return res?.data?.Calendar_Integration?.[0];
        }
        const responseData = await resilientGotPostPostgraphile(operationName, query, variables, userId);
        chatApiHelperLogger.info(`getCalendarIntegrationByResource response for user ${userId}, resource ${resource}`, { dataLength: responseData?.Calendar_Integration?.length });
        return responseData?.Calendar_Integration?.[0];
    }
    catch (e) {
        chatApiHelperLogger.error('Error in getCalendarIntegrationByResource', { userId, resource, error: e.message });
        throw e;
    }
};
export const getCalendarIntegrationByName = async (userId, name) => {
    try {
        const operationName = 'getCalendarIntegrationByName';
        const query = `
            query getCalendarIntegrationByName($userId: uuid!, $name: String!) {
                Calendar_Integration(where: {userId: {_eq: $userId}, name: {_eq: $name}}) {
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
            name,
        };
        const res = await got.post(postgraphileGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin'
            },
        }).json();
        console.log(res, ' res inside getCalendarIntegration');
        if (res?.data?.Calendar_Integration?.length > 0) {
            return res?.data?.Calendar_Integration?.[0];
        }
        const responseData = await resilientGotPostPostgraphile(operationName, query, variables, userId);
        chatApiHelperLogger.info(`getCalendarIntegrationByName response for user ${userId}, name ${name}`, { dataLength: responseData?.Calendar_Integration?.length });
        return responseData?.Calendar_Integration?.[0];
    }
    catch (e) {
        chatApiHelperLogger.error('Error in getCalendarIntegrationByName', { userId, name, error: e.message });
        throw e;
    }
};
export const getZoomIntegration = async (userId) => {
    try {
        const { id, token, expiresAt, refreshToken } = await getCalendarIntegrationByResource(userId, zoomResourceName);
        const decryptedTokens = decryptZoomTokens(token, refreshToken);
        return {
            id,
            expiresAt,
            ...decryptedTokens,
        };
    }
    catch (e) {
        chatApiHelperLogger.error('Unable to get zoom integration', { userId, error: e.message, stack: e.stack });
        // Original function implicitly returns undefined here, so we'll maintain that.
        // Depending on desired strictness, could rethrow e.
    }
};
export const decryptZoomTokens = (encryptedToken, encryptedRefreshToken) => {
    const ivBuffer = Buffer.from(zoomIVForPass, 'base64');
    const saltBuffer = Buffer.from(zoomSaltForPass, 'base64');
    const key = crypto.pbkdf2Sync(zoomPassKey, saltBuffer, 10000, 32, 'sha256');
    const decipherToken = crypto.createDecipheriv('aes-256-cbc', key, ivBuffer);
    let decryptedToken = decipherToken.update(encryptedToken, 'base64', 'utf8');
    decryptedToken += decipherToken.final('utf8');
    if (encryptedRefreshToken) {
        const decipherRefreshToken = crypto.createDecipheriv('aes-256-cbc', key, ivBuffer);
        let decryptedRefreshToken = decipherRefreshToken.update(encryptedRefreshToken, 'base64', 'utf8');
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
export const encryptZoomTokens = (token, refreshToken) => {
    const ivBuffer = Buffer.from(zoomIVForPass, 'base64');
    const saltBuffer = Buffer.from(zoomSaltForPass, 'base64');
    const key = crypto.pbkdf2Sync(zoomPassKey, saltBuffer, 10000, 32, 'sha256');
    const cipherToken = crypto.createCipheriv('aes-256-cbc', key, ivBuffer);
    let encryptedToken = cipherToken.update(token, 'utf8', 'base64');
    encryptedToken += cipherToken.final('base64');
    let encryptedRefreshToken = '';
    if (refreshToken) {
        const cipherRefreshToken = crypto.createCipheriv('aes-256-cbc', key, ivBuffer);
        encryptedRefreshToken = cipherRefreshToken.update(refreshToken, 'utf8', 'base64');
        encryptedRefreshToken += cipherRefreshToken.final('base64');
    }
    if (encryptedRefreshToken) {
        return {
            encryptedToken,
            encryptedRefreshToken
        };
    }
    else {
        return { encryptedToken };
    }
};
export const updateCalendarIntegration = async (id, token, expiresIn, enabled) => {
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
        const res = await got.post(postgraphileGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin'
            },
        }).json();
        console.log(res, ' res inside updateCalendarIntegration');
        await resilientGotPostPostgraphile(operationName, query, variables); // Assuming admin role for updates
        chatApiHelperLogger.info(`Successfully updated calendar integration ${id}.`);
    }
    catch (e) {
        chatApiHelperLogger.error('Error in updateCalendarIntegration', { id, token, expiresIn, enabled, error: e.message });
        throw e;
    }
};
export const updateZoomIntegration = async (id, accessToken, expiresIn) => {
    try {
        const { encryptedToken } = encryptZoomTokens(accessToken);
        await updateCalendarIntegration(id, encryptedToken, expiresIn);
    }
    catch (e) {
        chatApiHelperLogger.error('Unable to update zoom integration', { integrationId: id, error: e.message, stack: e.stack });
        // Original function implicitly returns undefined/void and does not rethrow.
    }
};
export const refreshZoomToken = async (refreshToken) => {
    const operationName = 'refreshZoomToken';
    const MAX_RETRIES = 3;
    const INITIAL_TIMEOUT_MS = 10000; // 10 seconds
    let attempt = 0;
    let lastError = null;
    const requestData = new URLSearchParams({
        refresh_token: refreshToken,
        grant_type: 'refresh_token',
    }).toString();
    const authHeader = `Basic ${Buffer.from(`${zoomClientId}:${zoomClientSecret}`).toString('base64')}`;
    while (attempt < MAX_RETRIES) {
        try {
            chatApiHelperLogger.info(`Attempt ${attempt + 1} to ${operationName}`, { refreshTokenSubstring: refreshToken?.substring(0, 10) });
            const response = await axios({
                method: 'POST',
                url: `${zoomBaseTokenUrl}/oauth/token`,
                data: requestData,
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Authorization': authHeader,
                },
                timeout: INITIAL_TIMEOUT_MS,
            });
            chatApiHelperLogger.info(`${operationName} successful on attempt ${attempt + 1}`);
            return response.data;
        }
        catch (error) {
            lastError = error;
            chatApiHelperLogger.warn(`Attempt ${attempt + 1} for ${operationName} failed.`, {
                error: error.message,
                code: error.code,
                status: error.response?.status
            });
            if (axios.isAxiosError(error)) {
                if (error.response) {
                    const status = error.response.status;
                    if (status < 500 && status !== 429 && status !== 408) { // Non-retryable client HTTP error
                        break;
                    }
                }
                else if (error.code && !['ECONNABORTED', 'ETIMEDOUT', 'ECONNRESET', 'EADDRINUSE', 'ECONNREFUSED', 'EPIPE', 'ENETUNREACH', 'EAI_AGAIN'].includes(error.code)) {
                    break; // Non-retryable network or config error
                }
            }
            else { // Non-axios error
                break;
            }
        }
        attempt++;
        if (attempt < MAX_RETRIES) {
            const delay = Math.pow(2, attempt - 1) * 1000;
            chatApiHelperLogger.info(`Waiting ${delay}ms before ${operationName} retry ${attempt + 1}`);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
    chatApiHelperLogger.error(`Failed ${operationName} after ${attempt} attempts.`, { lastError: lastError?.message });
    throw lastError || new Error(`Failed ${operationName} after all retries.`);
};
// Helper for resilient Zoom API calls using got
const resilientGotZoomApi = async (method, endpoint, zoomToken, jsonData, params) => {
    const MAX_RETRIES = 3;
    const INITIAL_TIMEOUT_MS = 15000; // 15 seconds for Zoom API calls
    let attempt = 0;
    let lastError = null;
    const url = `${zoomBaseUrl}${endpoint}`;
    while (attempt < MAX_RETRIES) {
        try {
            chatApiHelperLogger.info(`Zoom API call attempt ${attempt + 1}: ${method.toUpperCase()} ${endpoint}`);
            const options = {
                headers: {
                    'Authorization': `Bearer ${zoomToken}`,
                    'Content-Type': 'application/json',
                },
                timeout: { request: INITIAL_TIMEOUT_MS },
                responseType: 'json',
            };
            if (jsonData) {
                options.json = jsonData;
            }
            if (params) {
                options.searchParams = params;
            }
            let response;
            switch (method) {
                case 'get':
                    response = await got.get(url, options).json();
                    break;
                case 'post':
                    response = await got.post(url, options).json();
                    break;
                case 'patch':
                    response = await got.patch(url, options).json(); // .json() might not be needed if no body expected
                    break; // If PATCH returns 204 No Content, .json() will fail. Adjust if needed.
                case 'delete':
                    await got.delete(url, options); // DELETE often returns 204 No Content
                    response = { success: true }; // Simulate a success object if no body
                    break;
                default:
                    throw new Error(`Unsupported method: ${method}`);
            }
            chatApiHelperLogger.info(`Zoom API call ${method.toUpperCase()} ${endpoint} successful on attempt ${attempt + 1}`);
            return response;
        }
        catch (error) {
            lastError = error;
            chatApiHelperLogger.warn(`Zoom API call attempt ${attempt + 1} for ${method.toUpperCase()} ${endpoint} failed.`, {
                error: error.message,
                code: error.code,
                statusCode: error.response?.statusCode,
                // body: error.response?.body
            });
            if (error.response && error.response.statusCode) {
                const status = error.response.statusCode;
                if (status < 500 && status !== 429 && status !== 408 && status !== 401) { // 401 might be token expiry, could retry once after refresh
                    break;
                }
                if (status === 401) { // Specific handling for 401 potentially
                    // TODO: Could integrate token refresh logic here if this helper becomes more sophisticated
                    // For now, just let it retry once or break if it's a persistent auth issue.
                    // If this is the first attempt, allow a retry. If more, break.
                    if (attempt > 0)
                        break;
                }
            }
            else if (!error.response && error.code && !['ETIMEDOUT', 'ECONNRESET', 'EADDRINUSE', 'ECONNREFUSED', 'EPIPE', 'ENETUNREACH', 'EAI_AGAIN'].includes(error.code)) {
                break;
            }
        }
        attempt++;
        if (attempt < MAX_RETRIES) {
            const delay = Math.pow(2, attempt - 1) * 1000;
            chatApiHelperLogger.info(`Waiting ${delay}ms before Zoom API retry ${attempt + 1} for ${method.toUpperCase()} ${endpoint}`);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
    chatApiHelperLogger.error(`Failed Zoom API operation ${method.toUpperCase()} ${endpoint} after ${attempt} attempts.`, { lastError: lastError?.message });
    throw lastError || new Error(`Failed Zoom API operation ${method.toUpperCase()} ${endpoint} after all retries.`);
};
export const getZoomAPIToken = async (userId) => {
    let integrationId = '';
    const operationName = 'getZoomAPIToken';
    chatApiHelperLogger.info(`[${operationName}] Called for user.`, { userId });
    try {
        const zoomIntegration = await getZoomIntegration(userId);
        if (!zoomIntegration || !zoomIntegration.id || !zoomIntegration.refreshToken) {
            chatApiHelperLogger.warn(`[${operationName}] Zoom integration or essential details (id, refreshToken) not found. Zoom might not be active or properly configured.`, { userId });
            return undefined; // Explicitly return undefined if integration is not usable
        }
        integrationId = zoomIntegration.id; // Assign here, after we know zoomIntegration is valid
        const { token, expiresAt, refreshToken } = zoomIntegration; // Destructure after validation
        chatApiHelperLogger.debug(`[${operationName}] Retrieved Zoom integration details.`, { userId, integrationId, expiresAt, tokenExists: !!token });
        if (dayjs().isAfter(dayjs(expiresAt)) || !token) {
            chatApiHelperLogger.info(`[${operationName}] Token expired or missing, attempting refresh.`, { userId, integrationId });
            const refreshResponse = await refreshZoomToken(refreshToken);
            chatApiHelperLogger.info(`[${operationName}] Zoom token refresh successful.`, { userId, integrationId, newExpiryIn: refreshResponse.expires_in });
            await updateZoomIntegration(integrationId, refreshResponse.access_token, refreshResponse.expires_in);
            return refreshResponse.access_token;
        }
        chatApiHelperLogger.debug(`[${operationName}] Existing Zoom token is valid.`, { userId, integrationId });
        return token;
    }
    catch (e) {
        chatApiHelperLogger.error(`[${operationName}] Failed to get/refresh Zoom API token.`, { userId, integrationIdOnError: integrationId, error: e.message, stack: e.stack });
        if (integrationId) { // Only attempt to disable if we had an ID
            try {
                chatApiHelperLogger.info(`[${operationName}] Attempting to disable Zoom integration due to error.`, { integrationId });
                await updateCalendarIntegration(integrationId, undefined, undefined, false);
                chatApiHelperLogger.info(`[${operationName}] Successfully disabled Zoom integration.`, { integrationId });
            }
            catch (disableError) {
                chatApiHelperLogger.error(`[${operationName}] Failed to disable Zoom integration after an error.`, { integrationId, disableError: disableError.message, stack: disableError.stack });
            }
        }
        // Original code implicitly returns undefined on error / attempts to disable.
        // We'll maintain this behavior by not re-throwing here, but callers should be aware it might return undefined.
        return undefined;
    }
};
export const deleteRemindersWithIds = async (eventIds, userId) => {
    try {
        // validate
        if (!(eventIds?.filter(e => !!e)?.length > 0)) {
            return;
        }
        eventIds.forEach(e => console.log(e, ' eventIds inside deleteRemindersWithIds'));
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
        const response = await got.post(postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                'X-Postgraphile-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            },
            await: resilientGotPostPostgraphile(operationName, query, variables, userId),
            chatApiHelperLogger, : .info(`Successfully deleted reminders for eventIds: ${eventIds.join(', ')} for user ${userId}.`)
        });
        try { }
        catch (e) {
            chatApiHelperLogger.error('Error in deleteRemindersWithIds', { userId, eventIds, error: e.message });
            throw e;
        }
    }
    finally {
    }
    export const updateZoomMeeting;
};
export const updateZoomMeeting = async();
try {
}
catch (e) {
    chatApiHelperLogger.error('Error in deleteRemindersWithIds', { userId, eventIds, error: e.message });
    throw e;
}
;
export const updateZoomMeeting = async (zoomToken, meetingId, startDate, timezone, agenda, duration, contactName, contactEmail, meetingInvitees, privateMeeting, recur) => {
    try {
        //valdiate
        if (startDate && dayjs().isAfter(dayjs(startDate))) {
            chatApiHelperLogger.warn('[updateZoomMeeting] Start time is in the past.', { meetingId, startDate });
            throw new Error('Start time is in the past for updateZoomMeeting.');
        }
        let settings = {};
        if (privateMeeting) {
            settings = { ...settings, private_meeting: privateMeeting };
        }
        if ((contactName?.length > 0) && (contactEmail?.length > 0)) {
            settings = {
                contact_name: contactName,
                contact_email: contactEmail,
            };
        }
        if (meetingInvitees?.length > 0) {
            settings = { ...settings, meeting_invitees: meetingInvitees };
        }
        let reqBody = {};
        if (Object.keys(settings)?.length > 0) {
            reqBody.settings = settings;
        }
        if (startDate && timezone) {
            reqBody.start_time = dayjs(startDate?.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss');
            reqBody.timezone = timezone;
        }
        if (agenda) {
            reqBody.agenda = agenda;
        }
        if (duration) {
            reqBody.duration = duration;
        }
        if (recur?.frequency && recur?.interval && (recur?.endDate || recur?.occurrence)) {
            if (recur?.frequency === 'weekly') {
                reqBody.recurrence.type = 2;
            }
            else if (recur?.frequency === 'monthly') {
                reqBody.recurrence.type = 3;
            }
            else if (recur?.frequency === 'daily') {
                reqBody.recurrence.type = 1;
            }
            if (reqBody.recurrence.type == 3) {
                if (recur?.byMonthDay?.[0]) {
                    reqBody.recurrence.monthly_day = recur?.byMonthDay?.[0];
                }
            }
            if (recur?.endDate) {
                reqBody.recurrence.end_date_time = dayjs(recur.endDate).tz(timezone).utc().format();
            }
            else if (recur?.occurrence) {
                reqBody.recurrence.end_times = recur.occurrence;
            }
            reqBody.recurrence.repeat_interval = recur.interval;
            if (recur?.byMonthDay?.length > 0) {
                // create rrule and go by each date
                const rule = new RRule({
                    freq: getRruleFreq(recur?.frequency),
                    interval: recur?.interval,
                    until: dayjs(recur?.endDate).toDate(),
                    byweekday: recur?.byWeekDay?.map(i => getRRuleByWeekDay(i)),
                    count: recur?.occurrence,
                    bymonthday: recur?.byMonthDay,
                });
                const ruleDates = rule.all();
                const nonUniqueWeekMonth = [];
                const nonUniqueDayMonth = [];
                const nonUniqueDayWeekMonth = [];
                for (const ruleDate of ruleDates) {
                    const weekMonth = getWeekOfMonth(ruleDate);
                    nonUniqueWeekMonth.push(weekMonth);
                    const dayMonth = dayjs(ruleDate).date();
                    nonUniqueDayMonth.push(dayMonth);
                    const dayWeekMonth = getISODay(dayjs(ruleDate).toDate());
                    nonUniqueDayWeekMonth.push(dayWeekMonth);
                }
                const uniqueDayWeekMonth = _.uniq(nonUniqueDayWeekMonth);
                const uniqueDayMonth = _.uniq(nonUniqueDayMonth);
                const uniqueWeekMonth = _.uniq(nonUniqueWeekMonth);
                if (uniqueDayWeekMonth?.length > 0) {
                    reqBody.recurrence.monthly_week_day = uniqueDayWeekMonth?.[0];
                }
                if (uniqueDayMonth?.length > 0) {
                    reqBody.recurrence.monthly_day = uniqueDayMonth?.[0];
                }
                if (uniqueWeekMonth?.length > 0) {
                    reqBody.recurrence.monthly_week = uniqueWeekMonth?.[0];
                }
            }
            else if (recur?.byWeekDay?.length > 0) {
                reqBody.recurrence.weekly_days = getNumberInString(recur.byWeekDay);
            }
        }
        await resilientGotZoomApi('patch', `/meetings/${meetingId}`, zoomToken, reqBody);
        chatApiHelperLogger.info(`Successfully patched Zoom meeting ${meetingId}.`);
    }
    catch (e) {
        chatApiHelperLogger.error('Error in updateZoomMeeting', { meetingId, error: e.message });
        throw e; // Re-throw to allow caller to handle
    }
};
export const getNumberForWeekDay = (day) => {
    switch (day) {
        case 'MO':
            return '1';
        case 'TU':
            return '2';
        case 'WE':
            return '3';
        case 'TH':
            return '4';
        case 'FR':
            return '5';
        case 'SA':
            return '6';
        case 'SU':
            return '7';
    }
};
export const getNumberInString = (byWeekDays) => {
    let numberInString = '';
    for (const byWeekDay of byWeekDays) {
        numberInString += `${getNumberForWeekDay(byWeekDay)}, `;
    }
    return numberInString;
};
export const createZoomMeeting = async (zoomToken, startDate, timezone, agenda, duration, contactName, contactEmail, meetingInvitees, recur) => {
    try {
        //valdiate
        if (dayjs().isAfter(dayjs(startDate))) {
            chatApiHelperLogger.warn('[createZoomMeeting] Start time is in the past.', { startDate, agenda });
            throw new Error('Start time is in the past for createZoomMeeting.');
        }
        chatApiHelperLogger.info('[createZoomMeeting] Called.', { startDate, timezone, agenda, duration });
        let settings = {};
        if ((contactName?.length > 0) && (contactEmail?.length > 0)) {
            settings = {
                contact_name: contactName,
                contact_email: contactEmail,
            };
        }
        if (meetingInvitees?.length > 0) {
            settings = { ...settings, meeting_invitees: meetingInvitees?.map(m => ({ email: m })) };
        }
        let reqBody = {};
        if (Object.keys(settings)?.length > 0) {
            reqBody.settings = settings;
        }
        reqBody = {
            ...reqBody,
            start_time: dayjs(startDate?.slice(0, 19)).tz(timezone, true).utc().format(),
            // timezone,
            agenda,
            duration,
        };
        if (recur?.frequency && recur?.interval && (recur?.endDate || recur?.occurrence)) {
            if (recur?.frequency === 'weekly') {
                reqBody.recurrence.type = 2;
            }
            else if (recur?.frequency === 'monthly') {
                reqBody.recurrence.type = 3;
            }
            else if (recur?.frequency === 'daily') {
                reqBody.recurrence.type = 1;
            }
            if (reqBody.recurrence.type == 3) {
                if (recur?.byMonthDay?.[0]) {
                    reqBody.recurrence.monthly_day = recur?.byMonthDay?.[0];
                }
            }
            if (recur?.endDate) {
                reqBody.recurrence.end_date_time = dayjs(recur.endDate).tz(timezone).utc().format();
            }
            else if (recur?.occurrence) {
                reqBody.recurrence.end_times = recur.occurrence;
            }
            reqBody.recurrence.repeat_interval = recur.interval;
            if (recur?.byMonthDay?.length > 0) {
                // create rrule and go by each date
                const rule = new RRule({
                    freq: getRruleFreq(recur?.frequency),
                    interval: recur?.interval,
                    until: dayjs(recur?.endDate).toDate(),
                    byweekday: recur?.byWeekDay?.map(i => getRRuleByWeekDay(i)),
                    count: recur?.occurrence,
                    bymonthday: recur?.byMonthDay,
                });
                const ruleDates = rule.all();
                const nonUniqueWeekMonth = [];
                const nonUniqueDayMonth = [];
                const nonUniqueDayWeekMonth = [];
                for (const ruleDate of ruleDates) {
                    const weekMonth = getWeekOfMonth(ruleDate);
                    nonUniqueWeekMonth.push(weekMonth);
                    const dayMonth = dayjs(ruleDate).date();
                    nonUniqueDayMonth.push(dayMonth);
                    const dayWeekMonth = getISODay(dayjs(ruleDate).toDate());
                    nonUniqueDayWeekMonth.push(dayWeekMonth);
                }
                const uniqueDayWeekMonth = _.uniq(nonUniqueDayWeekMonth);
                const uniqueDayMonth = _.uniq(nonUniqueDayMonth);
                const uniqueWeekMonth = _.uniq(nonUniqueWeekMonth);
                if (uniqueDayWeekMonth?.length > 0) {
                    reqBody.recurrence.monthly_week_day = uniqueDayWeekMonth?.[0];
                }
                if (uniqueDayMonth?.length > 0) {
                    reqBody.recurrence.monthly_day = uniqueDayMonth?.[0];
                }
                if (uniqueWeekMonth?.length > 0) {
                    reqBody.recurrence.monthly_week = uniqueWeekMonth?.[0];
                }
            }
            else if (recur?.byWeekDay?.length > 0) {
                reqBody.recurrence.weekly_days = getNumberInString(recur.byWeekDay);
            }
        }
        chatApiHelperLogger.debug('Zoom createMeeting request body:', { reqBody });
        const responseData = await resilientGotZoomApi('post', '/users/me/meetings', zoomToken, reqBody);
        chatApiHelperLogger.info('Successfully created Zoom meeting.', { meetingId: responseData?.id, topic: responseData?.topic });
        return responseData;
    }
    catch (e) {
        chatApiHelperLogger.error('Error in createZoomMeeting', { agenda, error: e.message });
        throw e;
    }
};
const refreshGoogleToken = async (refreshToken, clientType) => {
    const operationName = 'refreshGoogleToken';
    chatApiHelperLogger.info(`${operationName} called`, { clientType, refreshTokenSubstring: refreshToken?.substring(0, 10) });
    let clientId;
    let clientSecret;
    switch (clientType) {
        case 'ios':
            clientId = googleClientIdIos;
            break;
        case 'android':
            clientId = googleClientIdAndroid;
            break;
        case 'web':
            clientId = googleClientIdWeb;
            clientSecret = googleClientSecretWeb;
            break;
        case 'atomic-web':
            clientId = googleClientIdAtomicWeb;
            clientSecret = googleClientSecretAtomicWeb;
            break;
        default:
            chatApiHelperLogger.error(`Invalid clientType for ${operationName}`, { clientType });
            throw new Error(`Invalid clientType: ${clientType}`);
    }
    const formPayload = {
        grant_type: 'refresh_token',
        refresh_token: refreshToken,
        client_id: clientId,
    };
    if (clientSecret) {
        formPayload.client_secret = clientSecret;
    }
    try {
        return await resilientGotGoogleAuth(googleTokenUrl, formPayload, operationName, clientType);
    }
    catch (e) {
        chatApiHelperLogger.error(`Failed ${operationName} for clientType ${clientType} after all retries.`, { error: e.message });
        // The original function would log and implicitly return undefined.
        // To maintain a clearer contract, we'll rethrow. Callers should handle this.
        throw e;
    }
};
// Helper for resilient Google Auth calls using got
const resilientGotGoogleAuth = async (url, formPayload, operationName, clientType) => {
    const MAX_RETRIES = 3;
    const INITIAL_TIMEOUT_MS = 10000; // 10 seconds for Google Auth calls
    let attempt = 0;
    let lastError = null;
    while (attempt < MAX_RETRIES) {
        try {
            chatApiHelperLogger.info(`Google Auth call attempt ${attempt + 1} for ${operationName} (${clientType})`);
            const response = await got.post(url, {
                form: formPayload,
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                timeout: { request: INITIAL_TIMEOUT_MS },
                responseType: 'json',
            }).json();
            chatApiHelperLogger.info(`Google Auth call ${operationName} (${clientType}) successful on attempt ${attempt + 1}`);
            return response;
        }
        catch (error) {
            lastError = error;
            chatApiHelperLogger.warn(`Google Auth call attempt ${attempt + 1} for ${operationName} (${clientType}) failed.`, {
                error: error.message,
                code: error.code,
                statusCode: error.response?.statusCode,
                // body: error.response?.body // Be careful logging sensitive body parts
            });
            if (error.response && error.response.statusCode) {
                const status = error.response.statusCode;
                // 400, 401, 403 are usually client errors for auth, not typically retryable unless specific (e.g. temporary clock skew for 401, but unlikely here)
                if (status === 400 || status === 401 || status === 403) {
                    chatApiHelperLogger.error(`Non-retryable HTTP error ${status} for ${operationName} (${clientType}). Aborting.`, { operationName, clientType });
                    break;
                }
                if (status < 500 && status !== 429 && status !== 408) {
                    chatApiHelperLogger.error(`Non-retryable HTTP error ${status} for ${operationName} (${clientType}). Aborting.`, { operationName, clientType });
                    break;
                }
            }
            else if (!error.response && error.code && !['ETIMEDOUT', 'ECONNRESET', 'EADDRINUSE', 'ECONNREFUSED', 'EPIPE', 'ENETUNREACH', 'EAI_AGAIN'].includes(error.code)) {
                chatApiHelperLogger.error(`Non-retryable got error code ${error.code} for ${operationName} (${clientType}). Aborting.`, { operationName, clientType });
                break;
            }
        }
        attempt++;
        if (attempt < MAX_RETRIES) {
            const delay = Math.pow(2, attempt - 1) * 1000; // Exponential backoff: 1s, 2s
            chatApiHelperLogger.info(`Waiting ${delay}ms before Google Auth retry ${attempt + 1} for ${operationName} (${clientType})`);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
    chatApiHelperLogger.error(`Failed Google Auth operation '${operationName}' (${clientType}) after ${attempt} attempts.`, { operationName, clientType, lastError: lastError?.message });
    throw lastError || new Error(`Failed Google Auth operation '${operationName}' (${clientType}) after all retries.`);
};
export const getGoogleAPIToken = async (userId, name, clientType) => {
    let integrationId = '';
    const operationName = 'getGoogleAPIToken';
    chatApiHelperLogger.info(`[${operationName}] Called.`, { userId, name, clientType });
    try {
        const integration = await getCalendarIntegrationByName(userId, name);
        if (!integration || !integration.id || !integration.refreshToken) { // Added check for refreshToken
            chatApiHelperLogger.error(`[${operationName}] Calendar integration or essential details not found.`, { userId, name, clientType, integration });
            throw new Error(`Calendar integration or essential details not found for user ${userId}, name ${name}.`);
        }
        integrationId = integration.id;
        chatApiHelperLogger.debug(`[${operationName}] Retrieved calendar integration.`, { userId, name, integrationId, expiresAt: integration.expiresAt, tokenExists: !!integration.token });
        if (dayjs().isAfter(dayjs(integration.expiresAt)) || !integration.token) {
            chatApiHelperLogger.info(`[${operationName}] Token expired or missing, attempting refresh.`, { userId, name, integrationId });
            const refreshResponse = await refreshGoogleToken(integration.refreshToken, clientType);
            chatApiHelperLogger.info(`[${operationName}] Token refresh successful.`, { userId, name, integrationId, newExpiryIn: refreshResponse.expires_in });
            // Ensure expiresIn is a number for dayjs().add
            const expiresInSeconds = typeof refreshResponse.expires_in === 'number' ? refreshResponse.expires_in : parseInt(String(refreshResponse.expires_in), 10);
            await updateCalendarIntegration(integrationId, refreshResponse.access_token, expiresInSeconds);
            return refreshResponse.access_token;
        }
        chatApiHelperLogger.debug(`[${operationName}] Existing token is valid.`, { userId, name, integrationId });
        return integration.token;
    }
    catch (e) {
        chatApiHelperLogger.error(`[${operationName}] Failed to get/refresh Google API token.`, { userId, name, clientType, integrationIdOnError: integrationId, error: e.message, stack: e.stack });
        if (integrationId) {
            try {
                chatApiHelperLogger.info(`[${operationName}] Attempting to disable calendar integration due to error.`, { integrationId });
                await updateCalendarIntegration(integrationId, undefined, undefined, false);
                chatApiHelperLogger.info(`[${operationName}] Successfully disabled calendar integration.`, { integrationId });
            }
            catch (disableError) {
                chatApiHelperLogger.error(`[${operationName}] Failed to disable calendar integration after an error.`, { integrationId, disableError: disableError.message, stack: disableError.stack });
            }
        }
        throw e; // Re-throw original error to ensure failure is propagated
    }
};
export const createGoogleEvent = async (userId, calendarId, clientType, generatedId, endDateTime, // either endDateTime or endDate - all day vs specific period
startDateTime, conferenceDataVersion, maxAttendees, sendUpdates, anyoneCanAddSelf, attendees, conferenceData, summary, description, timezone, // required for recurrence
startDate, // all day
endDate, // all day
extendedProperties, guestsCanInviteOthers, guestsCanModify, guestsCanSeeOtherGuests, originalStartDateTime, originalStartDate, recurrence, reminders, source, status, transparency, visibility, iCalUID, attendeesOmitted, hangoutLink, privateCopy, locked, attachments, eventType, location, colorId) => {
    const operation_name = "ChatCreateGoogleEvent"; // For logging
    // Wrap the entire logic in async-retry
    return await retry(async (bail, attemptNumber) => {
        try {
            chatApiHelperLogger.info(`Attempt ${attemptNumber} to create Google event for user ${userId}`, { summary });
            // get token
            const token = await getGoogleAPIToken(userId, googleCalendarName, clientType);
            if (!token) { // getGoogleAPIToken might return undefined on failure if not throwing
                chatApiHelperLogger.error(`${operation_name}: Failed to get Google API Token for user ${userId} on attempt ${attemptNumber}.`);
                // This is a setup failure, likely non-retryable in the short term by this function.
                // Bail to prevent further retries for this specific issue.
                bail(new Error('Failed to acquire Google API token for event creation.'));
                return; // Should not be reached as bail throws
            }
            const googleCalendar = google.calendar({
                version: 'v3',
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            });
            // create request body (logic remains the same)
            let data = {};
            if (endDateTime && timezone && !endDate) {
                const end = { dateTime: endDateTime, timeZone: timezone };
                data.end = end;
            }
            if (endDate && timezone && !endDateTime) {
                const end = { date: dayjs(endDate.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD'), timeZone: timezone };
                data.end = end;
            }
            if (startDate && timezone && !startDateTime) {
                const start = { date: dayjs(startDate.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD'), timeZone: timezone };
                data.start = start;
            }
            if (startDateTime && timezone && !startDate) {
                const start = { dateTime: startDateTime, timeZone: timezone };
                data.start = start;
            }
            if (originalStartDate && timezone && !originalStartDateTime) {
                const originalStartTime = { date: dayjs(originalStartDate?.slice(0, 19)).format('YYYY-MM-DD'), timeZone: timezone };
                data.originalStartTime = originalStartTime;
            }
            if (originalStartDateTime && timezone && !originalStartDate) {
                const originalStartTime = { dateTime: originalStartDateTime, timeZone: timezone };
                data.originalStartTime = originalStartTime;
            }
            if (anyoneCanAddSelf)
                data = { ...data, anyoneCanAddSelf };
            if (attendees?.[0]?.email)
                data = { ...data, attendees };
            if (conferenceData?.createRequest) {
                data = { ...data, conferenceData: { createRequest: { conferenceSolutionKey: { type: conferenceData.type }, requestId: conferenceData?.requestId || uuid() } } };
            }
            else if (conferenceData?.entryPoints?.[0]) {
                data = { ...data, conferenceData: { conferenceSolution: { iconUri: conferenceData?.iconUri, key: { type: conferenceData?.type }, name: conferenceData?.name }, entryPoints: conferenceData?.entryPoints } };
            }
            if (description?.length > 0)
                data = { ...data, description };
            if (extendedProperties?.private || extendedProperties?.shared)
                data = { ...data, extendedProperties };
            if (guestsCanInviteOthers)
                data = { ...data, guestsCanInviteOthers };
            if (guestsCanModify)
                data = { ...data, guestsCanModify };
            if (guestsCanSeeOtherGuests)
                data = { ...data, guestsCanSeeOtherGuests };
            if (locked)
                data = { ...data, locked };
            if (privateCopy)
                data = { ...data, privateCopy };
            if (recurrence?.[0])
                data = { ...data, recurrence };
            if ((reminders?.overrides?.length > 0) || (reminders?.useDefault))
                data = { ...data, reminders };
            if (source?.title || source?.url)
                data = { ...data, source };
            if (attachments?.[0]?.fileId)
                data = { ...data, attachments };
            if (eventType?.length > 0)
                data = { ...data, eventType };
            if (status)
                data = { ...data, status };
            if (transparency)
                data = { ...data, transparency };
            if (visibility)
                data = { ...data, visibility };
            if (iCalUID?.length > 0)
                data = { ...data, iCalUID };
            if (attendeesOmitted)
                data = { ...data, attendeesOmitted };
            if (hangoutLink?.length > 0)
                data = { ...data, hangoutLink };
            if (summary?.length > 0)
                data = { ...data, summary };
            if (location?.length > 0)
                data = { ...data, location };
            if (colorId)
                data.colorId = colorId;
            chatApiHelperLogger.debug(`Google Calendar create request body for user ${userId} (attempt ${attemptNumber})`, { data });
            const res = await googleCalendar.events.insert({
                calendarId,
                conferenceDataVersion,
                maxAttendees,
                sendUpdates,
                requestBody: data,
            }, { timeout: 20000 }); // 20 second timeout per attempt
            chatApiHelperLogger.info(`Google Calendar event created successfully on attempt ${attemptNumber} for user ${userId}: ${res.data.id}`);
            return { id: `${res?.data?.id}#${calendarId}`, googleEventId: res?.data?.id, generatedId, calendarId, generatedEventId: generatedId?.split('#')[0] };
        }
        catch (e) {
            chatApiHelperLogger.warn(`Attempt ${attemptNumber} to create Google event for user ${userId} failed.`, {
                error: e.message, code: e.code, errors: e.errors, summary
            });
            const httpStatusCode = e.code;
            const googleErrorReason = e.errors && e.errors[0] ? e.errors[0].reason : null;
            if (httpStatusCode === 400 || httpStatusCode === 401 || httpStatusCode === 404 ||
                (httpStatusCode === 403 && googleErrorReason !== 'rateLimitExceeded' && googleErrorReason !== 'userRateLimitExceeded')) {
                bail(e); // Stop retrying for these client errors
                return; // bail will throw
            }
            throw e; // Re-throw other errors to trigger retry
        }
    }, {
        retries: 3,
        factor: 2,
        minTimeout: 1000,
        maxTimeout: 10000,
        onRetry: (error, attemptNumber) => {
            chatApiHelperLogger.warn(`Retrying Google event creation for user ${userId}, attempt ${attemptNumber}. Last error: ${error.message}`, {
                operation_name: `${operation_name}_onRetry`,
                attempt: attemptNumber,
                error_message: error.message,
                error_code: error.code,
                error_reason: error.errors && error.errors[0] ? error.errors[0].reason : null,
                summary
            });
        },
    });
};
try { }
catch (e) {
    chatApiHelperLogger.error(`Failed to create Google event for user ${userId} after all retries or due to non-retryable error.`, {
        summary, error: e.message, code: e.code, errors: e.errors, details: e.response?.data || e.errors || e
    });
    throw e;
}
export const patchGoogleEvent = async (userId, calendarId, eventId, clientType, endDateTime, // either endDateTime or endDate - all day vs specific period
startDateTime, conferenceDataVersion, maxAttendees, sendUpdates, anyoneCanAddSelf, attendees, conferenceData, summary, description, timezone, // required for recurrence
startDate, endDate, extendedProperties, guestsCanInviteOthers, guestsCanModify, guestsCanSeeOtherGuests, originalStartDateTime, originalStartDate, recurrence, reminders, source, status, transparency, visibility, iCalUID, attendeesOmitted, hangoutLink, privateCopy, locked, attachments, eventType, location, colorId) => {
    try {
        // get token =
        const token = await getGoogleAPIToken(userId, googleCalendarName, clientType);
        // let url = `${googleUrl}/${encodeURI(calendarId)}/events/${encodeURI(eventId)}`
        // const config = {
        //   headers: {
        //     Authorization: `Bearer ${token}`,
        //     'Content-Type': 'application/json',
        //     'Accept': 'application/json',
        //   },
        // }
        const googleCalendar = google.calendar({
            version: 'v3',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });
        let variables = {
            // Calendar identifier. To retrieve calendar IDs call the calendarList.list method. If you want to access the primary calendar of the currently logged in user, use the "primary" keyword.
            calendarId,
            // Version number of conference data supported by the API client. Version 0 assumes no conference data support and ignores conference data in the event's body. Version 1 enables support for copying of ConferenceData as well as for creating new conferences using the createRequest field of conferenceData. The default is 0.
            conferenceDataVersion,
            // Event identifier.
            eventId,
            // The maximum number of attendees to include in the response. If there are more than the specified number of attendees, only the participant is returned. Optional.
            maxAttendees,
            // Guests who should receive notifications about the event update (for example, title changes, etc.).
            sendUpdates,
            // Request body metadata
            requestBody: {
            // request body parameters
            // {
            //   "anyoneCanAddSelf": false,
            //   "attachments": [],
            //   "attendees": [],
            //   "attendeesOmitted": false,
            //   "colorId": "my_colorId",
            //   "conferenceData": {},
            //   "created": "my_created",
            //   "creator": {},
            //   "description": "my_description",
            //   "end": {},
            //   "endTimeUnspecified": false,
            //   "etag": "my_etag",
            //   "eventType": "my_eventType",
            //   "extendedProperties": {},
            //   "gadget": {},
            //   "guestsCanInviteOthers": false,
            //   "guestsCanModify": false,
            //   "guestsCanSeeOtherGuests": false,
            //   "hangoutLink": "my_hangoutLink",
            //   "htmlLink": "my_htmlLink",
            //   "iCalUID": "my_iCalUID",
            //   "id": "my_id",
            //   "kind": "my_kind",
            //   "location": "my_location",
            //   "locked": false,
            //   "organizer": {},
            //   "originalStartTime": {},
            //   "privateCopy": false,
            //   "recurrence": [],
            //   "recurringEventId": "my_recurringEventId",
            //   "reminders": {},
            //   "sequence": 0,
            //   "source": {},
            //   "start": {},
            //   "status": "my_status",
            //   "summary": "my_summary",
            //   "transparency": "my_transparency",
            //   "updated": "my_updated",
            //   "visibility": "my_visibility"
            // }
            },
        };
        // create request body
        let requestBody = {};
        if (endDate && timezone && !endDateTime) {
            const end = {
                date: dayjs(endDateTime.slice(0, 19)).tz(timezone, true)
                    .format('YYYY-MM-DD'),
                timezone,
            };
            requestBody.end = end;
        }
        // if (endDateTime && timezone && !endDate && (recurrence?.length > 0)) {
        //   const end = {
        //     dateTime: dayjs(endDateTime).tz(timezone, true)
        //       .format('YYYY-MM-DDTHH:mm:ss'),
        //     timezone
        //   }
        //   requestBody.end = end
        // }
        if (endDateTime && timezone && !endDate) {
            chatApiHelperLogger.debug('[patchGoogleEvent] Setting end dateTime', { eventId, endDateTime, timezone });
            const end = {
                dateTime: endDateTime,
                timezone
            };
            requestBody.end = end;
        }
        if (startDate && timezone && !startDateTime) { // All-day event start
            chatApiHelperLogger.debug('[patchGoogleEvent] Setting start date (all-day)', { eventId, startDate, timezone });
            const start = {
                date: dayjs(startDate.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD'), // Ensure correct formatting for date-only
                timezone,
            };
            requestBody.start = start;
        }
        // if (startDateTime && timezone && !startDate && (recurrence?.length > 0)) {
        //   const start = {
        //     dateTime: dayjs(startDateTime).tz(timezone, true).format('YYYY-MM-DDTHH:mm:ss'),
        //     timezone,
        //   }
        //   requestBody.start = start
        // }
        if (startDateTime && timezone && !startDate) { // Specific time event start
            chatApiHelperLogger.debug('[patchGoogleEvent] Setting start dateTime', { eventId, startDateTime, timezone });
            const start = {
                dateTime: startDateTime,
                timezone,
            };
            requestBody.start = start;
        }
        if (originalStartDate && timezone && !originalStartDateTime) {
            const originalStartTime = {
                date: dayjs(originalStartDate.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD'),
                timezone,
            };
            requestBody.originalStartTime = originalStartTime;
        }
        if (originalStartDateTime && timezone && !originalStartDate) {
            const originalStartTime = {
                dateTime: originalStartDateTime,
                timezone,
            };
            requestBody.originalStartTime = originalStartTime;
        }
        if (anyoneCanAddSelf) {
            // data = { ...data, anyoneCanAddSelf }
            requestBody.anyoneCanAddSelf = anyoneCanAddSelf;
        }
        if (attendees?.[0]?.email) {
            // data = { ...data, attendees }
            requestBody.attendees = attendees;
        }
        if (conferenceData?.createRequest) {
            // data = {
            //   ...data,
            //   conferenceData: {
            //     createRequest: {
            //       conferenceSolutionKey: {
            //         type: conferenceData.type
            //       },
            //       requestId: conferenceData?.requestId || uuidv1(),
            //     }
            //   }
            // }
            requestBody.conferenceData = {
                createRequest: {
                    conferenceSolutionKey: {
                        type: conferenceData.type
                    },
                    requestId: conferenceData?.requestId || uuid(),
                }
            };
        }
        else if (conferenceData?.entryPoints?.[0]) {
            // data = {
            //   ...data,
            //   conferenceData: {
            //     conferenceSolution: {
            //       iconUri: conferenceData?.iconUri,
            //       key: {
            //         type: conferenceData?.type,
            //       },
            //       name: conferenceData?.name,
            //     },
            //     entryPoints: conferenceData?.entryPoints,
            //   },
            // }
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
            // data = { ...data, description }
            requestBody.description = description;
        }
        if (extendedProperties?.private || extendedProperties?.shared) {
            // data = { ...data, extendedProperties }
            requestBody.extendedProperties = extendedProperties;
        }
        if (guestsCanInviteOthers) {
            // data = { ...data, guestsCanInviteOthers }
            requestBody.guestsCanInviteOthers = guestsCanInviteOthers;
        }
        if (guestsCanModify) {
            // data = { ...data, guestsCanModify }
            requestBody.guestsCanModify = guestsCanModify;
        }
        if (guestsCanSeeOtherGuests) {
            // data = { ...data, guestsCanSeeOtherGuests }
            requestBody.guestsCanSeeOtherGuests = guestsCanSeeOtherGuests;
        }
        if (locked) {
            // data = { ...data, locked }
            requestBody.locked = locked;
        }
        if (privateCopy) {
            // data = { ...data, privateCopy }
            requestBody.privateCopy = privateCopy;
        }
        if (recurrence?.[0]) {
            // data = { ...data, recurrence }
            requestBody.recurrence = recurrence;
        }
        if (reminders) {
            // data = { ...data, reminders }
            requestBody.reminders = reminders;
        }
        if (source?.title || source?.url) {
            // data = { ...data, source }
            requestBody.source = source;
        }
        if (attachments?.[0]?.fileId) {
            // data = { ...data, attachments }
            requestBody.attachments = attachments;
        }
        if (eventType?.length > 0) {
            // data = { ...data, eventType }
            requestBody.eventType = eventType;
        }
        if (status) {
            // data = { ...data, status }
            requestBody.status = status;
        }
        if (transparency) {
            // data = { ...data, transparency }
            requestBody.transparency = transparency;
        }
        if (visibility) {
            // data = { ...data, visibility }
            requestBody.visibility = visibility;
        }
        if (iCalUID?.length > 0) {
            // data = { ...data, iCalUID }
            requestBody.iCalUID = iCalUID;
        }
        if (attendeesOmitted) {
            // data = { ...data, attendeesOmitted }
            requestBody.attendeesOmitted = attendeesOmitted;
        }
        if (hangoutLink?.length > 0) {
            // data = { ...data, hangoutLink }
            requestBody.hangoutLink = hangoutLink;
        }
        if (summary?.length > 0) {
            // data = { ...data, summary }
            requestBody.summary = summary;
        }
        if (location?.length > 0) {
            // data = { ...data, location }
            requestBody.location = location;
        }
        if (colorId) {
            requestBody.colorId = colorId;
        }
        variables.requestBody = requestBody;
        // Do the magic
        chatApiHelperLogger.debug(`Google Calendar patch request for event ${eventId}`, { requestBody: variables.requestBody });
        return await retry(async (bail, attemptNumber) => {
            try {
                const res = await googleCalendar.events.patch(variables, { timeout: 20000 }); // 20 second timeout
                chatApiHelperLogger.info(`Google Calendar event ${eventId} patched successfully on attempt ${attemptNumber} for user ${userId}.`);
                // Original function didn't return anything, so we maintain that.
                return; // Explicitly return void for success if that's the contract
            }
            catch (e) {
                chatApiHelperLogger.warn(`Attempt ${attemptNumber} to patch Google event ${eventId} for user ${userId} failed.`, {
                    error: e.message, code: e.code, errors: e.errors
                });
                const httpStatusCode = e.code;
                const googleErrorReason = e.errors && e.errors[0] ? e.errors[0].reason : null;
                if (httpStatusCode === 400 || httpStatusCode === 401 || httpStatusCode === 404 ||
                    (httpStatusCode === 403 && googleErrorReason !== 'rateLimitExceeded' && googleErrorReason !== 'userRateLimitExceeded')) {
                    bail(e);
                    return;
                }
                ;
            }
            throw e;
        });
    }
    finally { }
    ;
};
try { }
catch (e) {
    chatApiHelperLogger.error('Error inserting attendees', { eventId, userId, attendeeIds, error: e.message });
    throw e;
}
;
;
try { }
catch (e) {
    chatApiHelperLogger.error('Error inserting attendees', { eventId, userId, attendeeIds, error: e.message });
    throw e;
}
;
try { }
catch (e) {
    chatApiHelperLogger.error('Error in insertAttendeesforEvent', { eventId, userId, attendeeIds, error: e.message });
    throw e;
}
// Function might need to be more robust. Expected response format and type.
export const insertAttendeesforEvent = async (retries, factor, minTimeout, maxTimeout, onRetry, chatApiHelperLogger, warn) => ;
(`Retrying Google event patch for event ${eventId}, user ${userId}, attempt ${attemptNumber}. Error: ${error.message}`, {
    operation_name: `${operation_name}_onRetry`,
    attempt: attemptNumber,
    error_code: error.code,
});
;
try { }
catch (e) {
    chatApiHelperLogger.error(`Failed to patch Google event ${eventId} for user ${userId} after all retries.`, { error: e.message });
    throw e;
}
export const getEventFromPrimaryKey = async (eventId) => {
    try {
        const operationName = 'getEventFromPrimaryKey';
        const query = getEventById;
        const responseData = await resilientGotPostPostgraphile(operationName, query, { eventId });
        return responseData?.Event_by_pk;
    }
    catch (e) {
        chatApiHelperLogger.error('Error in getEventFromPrimaryKey', { eventId, error: e.message });
        throw e;
    }
};
export const getTaskGivenId = async (id) => {
    try {
        const operationName = 'GetTaskById';
        const query = getTaskById;
        const response = await got.post(postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables: {
                    id,
                },
            },
        }).json();
        const res = response;
        // console.log(res, ' res from getTaskGivenId')
        // return res?.data?.Task_by_pk
        const responseData = await resilientGotPostPostgraphile(operationName, query, { id }); // Assuming admin role or appropriate context
        return responseData?.Task_by_pk;
    }
    catch (e) {
        chatApiHelperLogger.error('Error in getTaskGivenId', { id, error: e.message });
        throw e;
    }
};
export const createPreAndPostEventsFromEvent = (event, bufferTime) => {
    const eventId = uuid();
    const eventId1 = uuid();
    const preEventId = event?.preEventId || `${eventId}#${event?.calendarId}`;
    const postEventId = event?.postEventId || `${eventId1}#${event?.calendarId}`;
    // await upsertEvents([beforeEvent, afterEvent])
    let valuesToReturn = {};
    valuesToReturn.newEvent = event;
    if (bufferTime?.afterEvent) {
        // const formattedZoneAfterEventEndDate = formatInTimeZone(addMinutes(zonedTimeToUtc(event.endDate.slice(0, 19), event.timezone), previousEvent?.timeBlocking?.afterEvent), event.timezone, "yyyy-MM-dd'T'HH:mm:ssXXX")
        // const formattedZoneAfterEventStartDate = formatInTimeZone(zonedTimeToUtc(event.endDate.slice(0, 19), event.timezone), event.timezone, "yyyy-MM-dd'T'HH:mm:ssXXX")
        const formattedZoneAfterEventEndDate = dayjs(event.endDate.slice(0, 19)).tz(event.timezone, true).add(bufferTime?.afterEvent, 'm').format();
        const formattedZoneAfterEventStartDate = dayjs(event.endDate.slice(0, 19)).tz(event.timezone, true).format();
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
            eventId: postEventId.split('#')[0]
        };
        valuesToReturn.afterEvent = afterEvent;
        valuesToReturn.newEvent = {
            ...valuesToReturn.newEvent,
            postEventId,
            timeBlocking: {
                ...valuesToReturn?.newEvent?.timeBlocking,
                afterEvent: bufferTime?.afterEvent,
            }
        };
    }
    if (bufferTime?.beforeEvent) {
        const formattedZoneBeforeEventStartDate = dayjs(event.startDate.slice(0, 19)).tz(event.timezone, true).subtract(bufferTime?.beforeEvent, 'm').format();
        const formattedZoneBeforeEventEndDate = dayjs(event.startDate.slice(0, 19)).tz(event.timezone, true).format();
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
            eventId: preEventId.split('#')[0]
        };
        valuesToReturn.beforeEvent = beforeEvent;
        valuesToReturn.newEvent = {
            ...valuesToReturn.newEvent,
            preEventId,
            timeBlocking: {
                ...valuesToReturn?.newEvent?.timeBlocking,
                beforeEvent: bufferTime?.beforeEvent,
            }
        };
    }
    return valuesToReturn;
};
export const upsertAttendeesforEvent = async (attendees) => {
    try {
        // validate
        if (!(attendees?.filter(a => !!(a?.eventId))?.length > 0)) {
            return;
        }
        const operationName = 'InsertAttendeesForEvent';
        const query = insertAttendeesForEvent;
        const variables = {
            attendees,
        };
        const response = await got.post(postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                'X-Postgraphile-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            },
            const: responseData = await resilientGotPostPostgraphile(operationName, query, variables),
            if(responseData, insert_Attendee, returning) {
                chatApiHelperLogger.info('Successfully upserted attendees.', { count: responseData.insert_Attendee.returning.length });
            }, else: {
                chatApiHelperLogger, : .warn('UpsertAttendeesforEvent call to Postgraphile did not return expected data structure.', { responseData })
            }
            // No return value in original
        });
        try { }
        catch (e) {
            chatApiHelperLogger.error('Error in upsertAttendeesforEvent', { error: e.message });
            throw e;
        }
    }
    finally {
    }
    export const deleteAttendeesWithIds = async (eventIds, userId) => {
        try {
            // validate
            if (!(eventIds?.filter(e => !!e)?.length > 0)) {
                return;
            }
            chatApiHelperLogger.debug('Event IDs for attendee deletion:', { eventIds, userId, operationName: 'DeleteAttendeesWithEventIds' });
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
            const response = await got.post(postgraphileGraphUrl, {
                headers: {
                    'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                    'X-Postgraphile-Role': 'admin'
                },
                json: {
                    operationName,
                    query,
                    variables,
                },
                await: resilientGotPostPostgraphile(operationName, query, variables, userId),
                chatApiHelperLogger, : .info(`Successfully deleted attendees for eventIds: ${eventIds.join(', ')} for user ${userId}.`)
            });
            try { }
            catch (e) {
                chatApiHelperLogger.error('Error in deleteAttendeesWithIds', { userId, eventIds, error: e.message });
                throw e;
            }
        }
        finally {
        }
        export const findContactByEmailGivenUserId = async (userId, email) => {
            try {
                // validate
                if (!userId) {
                    throw new Error('no userId provided');
                }
                if (!email) {
                    chatApiHelperLogger.warn('No email provided to findContactByEmailGivenUserId', { userId });
                    return; // Or throw new Error('Email is required'); depending on desired strictness
                }
                const operationName = 'FindContactByEmailGivenUserId';
                const query = findContactViaEmailByUserId;
                const variables = {
                    userId,
                    emailFilter: {
                        value: email,
                    }
                };
                const response = await got.post(postgraphileGraphUrl, {
                    headers: {
                        'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                        'X-Postgraphile-Role': 'admin'
                    },
                    json: {
                        operationName,
                        query,
                        variables,
                    }
                    // return response?.data?.Contact?.[0]
                    ,
                    // return response?.data?.Contact?.[0]
                    const: responseData = await resilientGotPostPostgraphile(operationName, query, variables, userId),
                    return: responseData?.Contact?.[0]
                });
                try { }
                catch (e) {
                    chatApiHelperLogger.error('Error in findContactByEmailGivenUserId', { userId, email, error: e.message });
                    throw e;
                }
            }
            finally {
            }
            export const getConferenceGivenId = async (id) => {
                try {
                    // validate
                    if (!id) {
                        throw new Error('no conference id provided');
                    }
                    const operationName = 'GetConferenceById';
                    const query = getConferenceById;
                    const variables = {
                        id,
                    };
                    const response = await got.post(postgraphileGraphUrl, {
                        headers: {
                            'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                            'X-Postgraphile-Role': 'admin'
                        },
                        json: {
                            operationName,
                            query,
                            variables,
                        }
                        // return response?.data?.Conference_by_pk
                        ,
                        // return response?.data?.Conference_by_pk
                        const: responseData = await resilientGotPostPostgraphile(operationName, query, variables),
                        return: responseData?.Conference_by_pk
                    });
                    try { }
                    catch (e) {
                        chatApiHelperLogger.error('Error in getConferenceGivenId', { id, error: e.message });
                        throw e;
                    }
                }
                finally {
                }
                export const deleteConferenceGivenId = async (id) => {
                    try {
                        // validate
                        if (!id) {
                            throw new Error('no conference id provided');
                        }
                        const operationName = 'DeleteConferenceById';
                        const query = deleteConferenceById;
                        const variables = {
                            id,
                        };
                        const response = await got.post(postgraphileGraphUrl, {
                            headers: {
                                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                                'X-Postgraphile-Role': 'admin'
                            },
                            json: {
                                operationName,
                                query,
                                variables,
                            }
                            // return response?.data?.delete_Conference_by_pk
                            ,
                            // return response?.data?.delete_Conference_by_pk
                            const: responseData = await resilientGotPostPostgraphile(operationName, query, variables),
                            return: responseData?.delete_Conference_by_pk
                        });
                        try { }
                        catch (e) {
                            chatApiHelperLogger.error('Error in deleteConferenceGivenId', { id, error: e.message });
                            throw e;
                        }
                    }
                    finally {
                    }
                    export const deleteZoomMeeting = async (zoomToken, meetingId, scheduleForReminder, cancelMeetingReminder) => {
                        try {
                            let params = {};
                            if (cancelMeetingReminder
                                || scheduleForReminder) {
                                if (cancelMeetingReminder) {
                                    params = { cancel_meeting_reminder: cancelMeetingReminder };
                                }
                                if (scheduleForReminder) {
                                    params = { ...params, schedule_for_reminder: scheduleForReminder };
                                }
                            }
                            const stringifiedObject = Object.keys(params)?.length > 0 ? qs.stringify(params) : '';
                            // if (stringifiedObject) {
                            //     await got.delete(
                            //         `${zoomBaseUrl}/meetings/` + meetingId + '?' + stringifiedObject,
                            //         {
                            //             headers: {
                            //                 Authorization: `Bearer ${zoomToken}`,
                            //                 ContentType: 'application/json',
                            //             }
                            //         }
                            //     )
                            // } else {
                            //     await got.delete(
                            //         `${zoomBaseUrl}/meetings/` + meetingId,
                            //         {
                            //             headers: {
                            //                 Authorization: `Bearer ${zoomToken}`,
                            //                 ContentType: 'application/json',
                            //             }
                            //         }
                            //     )
                            // }
                            await resilientGotZoomApi('delete', `/meetings/${meetingId}`, zoomToken, undefined, params);
                            chatApiHelperLogger.info(`Successfully deleted Zoom meeting ${meetingId}.`);
                        }
                        catch (e) {
                            chatApiHelperLogger.error('Error in deleteZoomMeeting', { meetingId, error: e.message });
                            throw e;
                        }
                    };
                    export const deleteEventGivenId = async (id) => {
                        try {
                            // validate
                            if (!id) {
                                throw new Error('no event id provided');
                            }
                            const operationName = 'DeleteEventById';
                            const query = deleteEventById;
                            const variables = {
                                id,
                            };
                            const response = await got.post(postgraphileGraphUrl, {
                                headers: {
                                    'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                                    'X-Postgraphile-Role': 'admin'
                                },
                                json: {
                                    operationName,
                                    query,
                                    variables,
                                }
                                // return response?.data?.delete_Event_by_pk
                                ,
                                // return response?.data?.delete_Event_by_pk
                                const: responseData = await resilientGotPostPostgraphile(operationName, query, variables),
                                return: responseData?.delete_Event_by_pk
                            });
                            try { }
                            catch (e) {
                                chatApiHelperLogger.error('Error in deleteEventGivenId', { id, error: e.message });
                                throw e;
                            }
                        }
                        finally {
                        }
                        export const deleteGoogleEvent = async (userId, calendarId, googleEventId, clientType, sendUpdates = 'all') => {
                            try {
                                // get token =
                                const token = await getGoogleAPIToken(userId, googleCalendarName, clientType);
                                const googleCalendar = google.calendar({
                                    version: 'v3',
                                    headers: {
                                        Authorization: `Bearer ${token}`,
                                    },
                                });
                                const res = await googleCalendar.events.delete({
                                    // Calendar identifier. To retrieve calendar IDs call the calendarList.list method. If you want to access the primary calendar of the currently logged in user, use the "primary" keyword.
                                    calendarId,
                                    // Event identifier.
                                    eventId: googleEventId,
                                    // Guests who should receive notifications about the deletion of the event.
                                    sendUpdates,
                                });
                                chatApiHelperLogger.info(`Google Calendar event ${googleEventId} deleted successfully for user ${userId}.`);
                                // Original function didn't return anything.
                            }
                            catch (e) {
                                chatApiHelperLogger.warn(`Attempt ${attemptNumber} to delete Google event ${googleEventId} for user ${userId} failed.`, {
                                    error: e.message, code: e.code, errors: e.errors
                                });
                                const httpStatusCode = e.code;
                                const googleErrorReason = e.errors && e.errors[0] ? e.errors[0].reason : null;
                                if (httpStatusCode === 400 || httpStatusCode === 401 || // 404 is often retryable for eventual consistency or if event was just created
                                    (httpStatusCode === 403 && googleErrorReason !== 'rateLimitExceeded' && googleErrorReason !== 'userRateLimitExceeded')) {
                                    bail(e);
                                    return;
                                }
                                throw e;
                            }
                        }, { retries: , 3: , factor: , 2: , minTimeout: , 1000: , maxTimeout: , 10000: , onRetry:  };
                        (error, attemptNumber) => {
                            chatApiHelperLogger.warn(`Retrying Google event delete for event ${googleEventId}, user ${userId}, attempt ${attemptNumber}. Error: ${error.message}`, {
                                operation_name: `${operation_name}_onRetry`,
                                attempt: attemptNumber,
                                error_code: error.code,
                            });
                        },
                        ;
                    };
                };
                try { }
                catch (e) {
                    chatApiHelperLogger.error(`Failed to delete Google event ${googleEventId} for user ${userId} after all retries.`, { error: e.message });
                    throw e;
                }
            };
            export const getRruleFreq = (freq) => {
                switch (freq) {
                    case 'daily':
                        return RRule.DAILY;
                    case 'weekly':
                        return RRule.WEEKLY;
                    case 'monthly':
                        return RRule.MONTHLY;
                    case 'yearly':
                        return RRule.YEARLY;
                    default:
                        return RRule.DAILY;
                }
            };
            export const getRRuleDay = (value) => {
                switch (value) {
                    case 'MO':
                        return RRule.MO;
                    case 'TU':
                        return RRule.TU;
                    case 'WE':
                        return RRule.WE;
                    case 'TH':
                        return RRule.TH;
                    case 'FR':
                        return RRule.FR;
                    case 'SA':
                        return RRule.SA;
                    case 'SU':
                        return RRule.SU;
                    default:
                        return RRule.MO;
                }
            };
            export const getRRuleByWeekDay = (value) => {
                switch (value) {
                    case 'MO':
                        return RRule.MO;
                    case 'TU':
                        return RRule.TU;
                    case 'WE':
                        return RRule.WE;
                    case 'TH':
                        return RRule.TH;
                    case 'FR':
                        return RRule.FR;
                    case 'SA':
                        return RRule.SA;
                    case 'SU':
                        return RRule.SU;
                    default:
                        return RRule.MO;
                }
            };
            export const getRRuleDay = (value) => {
                switch (value) {
                    case 'MO':
                        return RRule.MO;
                    case 'TU':
                        return RRule.TU;
                    case 'WE':
                        return RRule.WE;
                    case 'TH':
                        return RRule.TH;
                    case 'FR':
                        return RRule.FR;
                    case 'SA':
                        return RRule.SA;
                    case 'SU':
                        return RRule.SU;
                    default:
                        return RRule.MO;
                }
            };
            export const getRRuleByWeekDay = (value) => {
                switch (value) {
                    case 'MO':
                        return RRule.MO;
                    case 'TU':
                        return RRule.TU;
                    case 'WE':
                        return RRule.WE;
                    case 'TH':
                        return RRule.TH;
                    case 'FR':
                        return RRule.FR;
                    case 'SA':
                        return RRule.SA;
                    case 'SU':
                        return RRule.SU;
                    default:
                        return RRule.MO;
                }
            };
            export const getGoogleAPIToken = async (refreshToken, userId) => {
                try {
                    const clientType = 'web';
                    const { refresh_token, access_token, expires_in, token_type } = await refreshGoogleToken(refreshToken, clientType);
                    return access_token;
                }
                catch (error) {
                    chatApiHelperLogger.error('Error getting Google API token', error);
                    throw error;
                }
            };
            const refreshGoogleToken = async (refreshToken, clientType) => {
                try {
                    // Mock implementation for Google token refresh
                    return {
                        access_token: 'mock_access_token',
                        refresh_token,
                        expires_in: 3600,
                        token_type: 'Bearer'
                    };
                }
                catch (error) {
                    throw new Error('Failed to refresh Google token');
                }
            };
            freq: RecurrenceFrequencyType;
        };
    };
};
{
    switch (freq) {
        case 'daily':
            return RRule.DAILY;
        case 'weekly':
            return RRule.WEEKLY;
        case 'monthly':
            return RRule.MONTHLY;
        case 'yearly':
            return RRule.YEARLY;
    }
}
export const getRRuleDay = (value) => {
    switch (value) {
        case Day.MO:
            return RRule.MO;
        case Day.TU:
            return RRule.TU;
        case Day.WE:
            return RRule.WE;
        case Day.TH:
            return RRule.TH;
        case Day.FR:
            return RRule.FR;
        case Day.SA:
            return RRule.SA;
        case Day.SU:
            return RRule.SU;
        default:
            return undefined;
    }
};
export const getRRuleByWeekDay = (value) => {
    switch (value) {
        case 'MO':
            return RRule.MO;
        case 'TU':
            return RRule.TU;
        case 'WE':
            return RRule.WE;
        case 'TH':
            return RRule.TH;
        case 'FR':
            return RRule.FR;
        case 'SA':
            return RRule.SA;
        case 'SU':
            return RRule.SU;
        default:
            return undefined;
    }
};
export const createRRuleString = (frequency, interval, byWeekDay, count, recurringEndDate, byMonthDay) => {
    if ((!(recurringEndDate?.length > 0) && !count) || !frequency || !interval) {
        chatApiHelperLogger.warn('Cannot create RRule string: recurringEndDate/count or frequency or interval missing.', { hasRecurringEndDate: !!recurringEndDate, count, frequency, interval });
        return undefined;
    }
    const rule = new RRule({
        freq: getRruleFreq(frequency),
        interval,
        until: dayjs(recurringEndDate).toDate(),
        byweekday: byWeekDay?.map(i => getRRuleByWeekDay(i)),
        count,
        bymonthday: byMonthDay,
    });
    return [rule.toString()];
};
export const upsertMeetingAssistOne = async (meetingAssist) => {
    try {
        // validate
        if (!meetingAssist) {
            throw new Error('no meeting assist provided');
        }
        const operationName = 'InsertMeetingAssist';
        const query = insertMeetingAssistOne;
        const variables = {
            meetingAssist,
        };
        const response = await got.post(postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                'X-Postgraphile-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
            // return response?.data?.insert_Meeting_Assist_one
            ,
            // return response?.data?.insert_Meeting_Assist_one
            const: responseData = await resilientGotPostPostgraphile(operationName, query, variables),
            return: responseData?.insert_Meeting_Assist_one
        });
        try { }
        catch (e) {
            chatApiHelperLogger.error('Error in upsertMeetingAssistOne', { meetingAssistId: meetingAssist?.id, error: e.message });
            throw e;
        }
    }
    finally {
    }
    export const listUserContactInfosGivenUserId = async (userId) => {
        try {
            // validate
            if (!userId) {
                throw new Error('no userId provided');
            }
            const operationName = 'ListUserContactInfoByUserId';
            const query = listUserContactInfosByUserId;
            const variables = {
                userId,
            };
            const response = await got.post(postgraphileGraphUrl, {
                headers: {
                    'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                    'X-Postgraphile-Role': 'admin'
                },
                json: {
                    operationName,
                    query,
                    variables,
                }
                // return response?.data?.User_Contact_Info
                ,
                // return response?.data?.User_Contact_Info
                const: responseData = await resilientGotPostPostgraphile(operationName, query, variables, userId),
                return: responseData?.User_Contact_Info
            });
            try { }
            catch (e) {
                chatApiHelperLogger.error('Error in listUserContactInfosGivenUserId', { userId, error: e.message });
                throw e;
            }
        }
        finally {
        }
        export const getUserContactInfosGivenIds = async (ids) => {
            try {
                // validate
                if (!(ids?.length > 0)) {
                    console.log('no ids provided');
                    return;
                }
                const operationName = 'GetContactInfosWithIds';
                const query = getContactInfosByIds;
                const variables = {
                    ids,
                };
                const response = await got.post(postgraphileGraphUrl, {
                    headers: {
                        'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                        'X-Postgraphile-Role': 'admin'
                    },
                    json: {
                        operationName,
                        query,
                        variables,
                    }
                    // return response?.data?.User_Contact_Info
                    ,
                    // return response?.data?.User_Contact_Info
                    const: responseData = await resilientGotPostPostgraphile(operationName, query, variables), // Assuming admin for this system-level lookup
                    return: responseData?.User_Contact_Info
                });
                try { }
                catch (e) {
                    chatApiHelperLogger.error('Error in getUserContactInfosGivenIds', { ids, error: e.message });
                    throw e;
                }
            }
            finally {
            }
            export const getContactByNameWithUserId = async (userId, name) => {
                try {
                    // validate
                    if (!userId || !name) {
                        console.log('no userId or name provided');
                        return;
                    }
                    const operationName = 'GetContactByNameForUserId';
                    const query = getContactByNameForUserId;
                    const variables = {
                        userId,
                        name,
                    };
                    const response = await got.post(postgraphileGraphUrl, {
                        headers: {
                            'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                            'X-Postgraphile-Role': 'admin'
                        },
                        json: {
                            operationName,
                            query,
                            variables,
                        }
                        // return response?.data?.Contact?.[0]
                        ,
                        // return response?.data?.Contact?.[0]
                        const: responseData = await resilientGotPostPostgraphile(operationName, query, variables, userId),
                        return: responseData?.Contact?.[0]
                    });
                    try { }
                    catch (e) {
                        chatApiHelperLogger.error('Error in getContactByNameWithUserId', { userId, name, error: e.message });
                        throw e;
                    }
                }
                finally {
                }
                export const insertMeetingAssistAttendee = async (attendee) => {
                    try {
                        // validate
                        if (!attendee) {
                            throw new Error('no meeting assist provided');
                        }
                        const operationName = 'InsertMeetingAssistAttendee';
                        const query = insertMeetingAssistAttendeeOne;
                        const variables = {
                            attendee,
                        };
                        const response = await got.post(postgraphileGraphUrl, {
                            headers: {
                                'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                                'X-Postgraphile-Role': 'admin'
                            },
                            json: {
                                operationName,
                                query,
                                variables,
                            }
                            // return response?.data?.insert_Meeting_Assist_Attendee_one
                            ,
                            // return response?.data?.insert_Meeting_Assist_Attendee_one
                            const: responseData = await resilientGotPostPostgraphile(operationName, query, variables),
                            return: responseData?.insert_Meeting_Assist_Attendee_one
                        });
                        try { }
                        catch (e) {
                            chatApiHelperLogger.error('Error in insertMeetingAssistAttendee', { attendeeId: attendee?.id, error: e.message });
                            throw e;
                        }
                    }
                    finally {
                    }
                    export const createHostAttendee = async (userId, meetingId, timezone, email, name) => {
                        try {
                            // validate
                            if (!meetingId) {
                                throw new Error('no meetingId provided');
                            }
                            const userInfoItems = await listUserContactInfosGivenUserId(userId);
                            const attendeeId = uuid();
                            const primaryInfoItem = userInfoItems?.find(u => (u.primary && (u.type === 'email'))) || userInfoItems?.[0];
                            const hostAttendee = {
                                id: attendeeId,
                                name: primaryInfoItem?.name || name,
                                hostId: userId,
                                userId,
                                emails: [{ primary: true, value: primaryInfoItem?.id || email || '', type: 'email', displayName: primaryInfoItem?.name || name || '' }],
                                meetingId,
                                createdDate: dayjs().format(),
                                timezone,
                                updatedAt: dayjs().format(),
                                externalAttendee: false,
                                primaryEmail: primaryInfoItem?.id || email,
                            };
                            await insertMeetingAssistAttendee(hostAttendee);
                            return attendeeId;
                        }
                        catch (e) {
                            chatApiHelperLogger.error('Unable to create host attendee for new event', { userId, meetingId, timezone, email, name, error: e.message, stack: e.stack });
                            return undefined;
                        }
                    };
                    export const upsertMeetingAssistInviteMany = async (meetingAssistInvites) => {
                        try {
                            // validate
                            if (!(meetingAssistInvites?.length > 0)) {
                                throw new Error('no meeting assist invites provided');
                            }
                            const operationName = 'InsertMeetingAssistInvite';
                            const query = upsertMeetingAssistInviteGraphql;
                            const variables = {
                                meetingAssistInvites,
                            };
                            const response = await got.post(postgraphileGraphUrl, {
                                headers: {
                                    'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                                    'X-Postgraphile-Role': 'admin'
                                },
                                json: {
                                    operationName,
                                    query,
                                    variables,
                                }
                                // return response?.data?.insert_Meeting_Assist_Invite
                                ,
                                // return response?.data?.insert_Meeting_Assist_Invite
                                const: responseData = await resilientGotPostPostgraphile(operationName, query, variables),
                                return: responseData?.insert_Meeting_Assist_Invite
                            });
                            try { }
                            catch (e) {
                                chatApiHelperLogger.error('Error in upsertMeetingAssistInviteMany', { inviteCount: meetingAssistInvites?.length, error: e.message });
                                throw e;
                            }
                        }
                        finally {
                        }
                        export const updateUserNameGivenId = async (userId, name) => {
                            try {
                                // validate
                                if (!userId || !name) {
                                    throw new Error('no meeting assist invites provided');
                                }
                                const operationName = 'UpdateNameForUserById';
                                const query = updateNameForUserId;
                                const variables = {
                                    id: userId,
                                    name,
                                };
                                const response = await got.post(postgraphileGraphUrl, {
                                    headers: {
                                        'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                                        'X-Postgraphile-Role': 'admin'
                                    },
                                    json: {
                                        operationName,
                                        query,
                                        variables,
                                    }
                                    // return response?.data?.update_User_by_pk
                                    ,
                                    // return response?.data?.update_User_by_pk
                                    const: responseData = await resilientGotPostPostgraphile(operationName, query, variables),
                                    return: responseData?.update_User_by_pk
                                });
                                try { }
                                catch (e) {
                                    chatApiHelperLogger.error('Error in updateUserNameGivenId', { userId, name, error: e.message });
                                    throw e;
                                }
                            }
                            finally {
                            }
                            export const getUserGivenId = async (userId) => {
                                try {
                                    // validate
                                    if (!userId) {
                                        throw new Error('no userId provided');
                                    }
                                    const operationName = 'GetUserById';
                                    const query = getUserById;
                                    const variables = {
                                        id: userId,
                                    };
                                    const response = await got.post(postgraphileGraphUrl, {
                                        headers: {
                                            'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                                            'X-Postgraphile-Role': 'admin'
                                        },
                                        json: {
                                            operationName,
                                            query,
                                            variables,
                                        }
                                        // return response?.data?.User_by_pk
                                        ,
                                        // return response?.data?.User_by_pk
                                        const: responseData = await resilientGotPostPostgraphile(operationName, query, variables),
                                        return: responseData?.User_by_pk
                                    });
                                    try { }
                                    catch (e) {
                                        chatApiHelperLogger.error('Error in getUserGivenId', { userId, error: e.message });
                                        throw e;
                                    }
                                }
                                finally {
                                }
                                export const callOpenAIWithMessageHistoryOnly = async (openaiInstance, messageHistory = [], model = 'gpt-3.5-turbo') => {
                                    try {
                                        // assistant
                                        const completion = await openai.chat.completions.create({
                                            model,
                                            messages: messageHistory,
                                            max_tokens: 2000,
                                        });
                                        return completion.choices[0].message.content;
                                    }
                                    catch (error) {
                                        chatApiHelperLogger.warn(`OpenAI call failed. Model: ${model}.`, {
                                            error: error.message, code: error.code, status: error.response?.status
                                        });
                                        if (error.response && [400, 401, 403, 404, 429].includes(error.response.status)) { // Added 429 as potentially non-retryable for some quota errors
                                            bail(error);
                                            return;
                                        }
                                        throw error;
                                    }
                                }, { retries: , 2: , factor: , 2: , minTimeout: , 1000: , maxTimeout: , 5000: , onRetry:  };
                                (error, attemptNumber) => {
                                    chatApiHelperLogger.warn(`Retrying OpenAI call (history only), attempt ${attemptNumber}. Model: ${model}. Error: ${error.message}`);
                                };
                            };
                        };
                        try { }
                        catch (error) {
                            chatApiHelperLogger.error('Failed OpenAI call (history only) after all retries.', { model, error: error.message });
                            throw error;
                        }
                    };
                    export const callOpenAIWithMessageHistory = async (openai, messageHistory = [], prompt, model = 'gpt-3.5-turbo', userData, exampleInput, exampleOutput) => {
                        const operationName = "callOpenAIWithMessageHistory";
                        try {
                            return await retry(async (bail, attemptNumber) => {
                                try {
                                    chatApiHelperLogger.info(`Attempt ${attemptNumber} for ${operationName}. Model: ${model}.`);
                                    const messages = messageHistory.concat([
                                        { role: 'system', content: prompt },
                                        exampleInput && { role: 'user', content: exampleInput },
                                        exampleOutput && { role: 'assistant', content: exampleOutput },
                                        { role: 'user', content: userData }
                                    ])?.filter(m => !!m);
                                    const completion = await openai.chat.completions.create({
                                        model,
                                        messages,
                                        timeout: 30000, // 30s timeout, potentially longer prompts/responses
                                    });
                                    chatApiHelperLogger.info(`${operationName} successful on attempt ${attemptNumber}. Model: ${model}.`);
                                    return { totalTokenCount: completion?.usage?.total_tokens, response: completion?.choices?.[0]?.message?.content };
                                }
                                catch (error) {
                                    chatApiHelperLogger.warn(`Attempt ${attemptNumber} for ${operationName} failed. Model: ${model}.`, {
                                        error: error.message, code: error.code, status: error.response?.status
                                    });
                                    if (error.response && [400, 401, 403, 404, 429].includes(error.response.status)) {
                                        bail(error);
                                        return;
                                    }
                                    throw error;
                                }
                            }, {
                                retries: 2, factor: 2, minTimeout: 1000, maxTimeout: 8000,
                                onRetry: (error, attemptNumber) => {
                                    chatApiHelperLogger.warn(`Retrying ${operationName}, attempt ${attemptNumber}. Model: ${model}. Error: ${error.message}`);
                                }
                            });
                        }
                        catch (error) {
                            chatApiHelperLogger.error(`Failed ${operationName} after all retries.`, { model, error: error.message });
                            throw error;
                        }
                    };
                    export const callOpenAI = async (openai, // This param was named 'openai', but it seems it should be 'prompt' based on usage
                    prompt, // Renamed from 'model' for clarity, as 'model' is the next param
                    model = 'gpt-3.5-turbo', // This was 'userData'
                    userData, // This was 'exampleInput'
                    exampleInput, // This was 'exampleOutput'
                    exampleOutput) => {
                        const operationName = "callOpenAI_Simple";
                        // Correcting parameter mapping based on likely intent and usage pattern:
                        // Original: openai (OpenAI client), prompt (string), model (string, e.g. 'gpt-3.5-turbo'), userData (string), exampleInput (string), exampleOutput (string)
                        // The first parameter `openai` is the OpenAI client instance.
                        // The second parameter `prompt` is the system prompt.
                        // The third parameter `model` is the model name.
                        // The fourth parameter `userData` is the main user message.
                        // The fifth and sixth are examples.
                        try {
                            return await retry(async (bail, attemptNumber) => {
                                try {
                                    chatApiHelperLogger.info(`Attempt ${attemptNumber} for ${operationName}. Model: ${model}.`);
                                    const messages = [
                                        { role: 'system', content: prompt },
                                        exampleInput && { role: 'user', content: exampleInput },
                                        exampleOutput && { role: 'assistant', content: exampleOutput },
                                        { role: 'user', content: userData }
                                    ]?.filter(m => !!m);
                                    const completion = await openai.chat.completions.create({
                                        model,
                                        messages,
                                        timeout: 30000, // 30s
                                    });
                                    chatApiHelperLogger.info(`${operationName} successful on attempt ${attemptNumber}. Model: ${model}.`);
                                    return completion?.choices?.[0]?.message?.content;
                                }
                                catch (error) {
                                    chatApiHelperLogger.warn(`Attempt ${attemptNumber} for ${operationName} failed. Model: ${model}.`, {
                                        error: error.message, code: error.code, status: error.response?.status
                                    });
                                    if (error.response && [400, 401, 403, 404, 429].includes(error.response.status)) {
                                        bail(error);
                                        return;
                                    }
                                    throw error;
                                }
                            }, {
                                retries: 2, factor: 2, minTimeout: 1000, maxTimeout: 8000,
                                onRetry: (error, attemptNumber) => {
                                    chatApiHelperLogger.warn(`Retrying ${operationName}, attempt ${attemptNumber}. Model: ${model}. Error: ${error.message}`);
                                }
                            });
                        }
                        catch (error) {
                            chatApiHelperLogger.error(`Failed ${operationName} after all retries.`, { model, error: error.message });
                            throw error;
                        }
                    };
                    export const listEventsForUserGivenDates = async (userId, senderStartDate, senderEndDate) => {
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
                            // const startDateInReceiverTimezone = dayjs(senderStartDate.slice(0, 19)).tz(receiverTimezone, true)
                            // const endDateInReceiverTimezone = dayjs((senderEndDate.slice(0, 19))).tz(receiverTimezone, true)
                            // const startDateInSenderTimezone = dayjs(startDateInReceiverTimezone).format().slice(0, 19)
                            // const endDateInSenderTimezone = dayjs(endDateInReceiverTimezone).format().slice(0, 19)
                            const res = await got.post(postgraphileGraphUrl, {
                                headers: {
                                    'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
                                    'Content-Type': 'application/json',
                                    'X-Postgraphile-Role': 'admin'
                                },
                                json: {
                                    operationName,
                                    query,
                                    variables: {
                                        userId,
                                        startDate: senderStartDate,
                                        endDate: senderEndDate,
                                    },
                                },
                            });
                            const responseData = await resilientGotPostPostgraphile(operationName, query, { userId, startDate: senderStartDate, endDate: senderEndDate }, userId);
                            return responseData?.Event;
                        }
                        catch (e) {
                            chatApiHelperLogger.error('Error in listEventsForUserGivenDates', { userId, senderStartDate, senderEndDate, error: e.message });
                            throw e;
                        }
                    };
                    export const extractAttributesNeededFromUserInput = async (userInput) => {
                        try {
                            const openAIDateTime = await callOpenAI(openai, extractNeededAttributesPrompt, openAIChatGPT35Model, userInput, extractNeededAttributesExampleInput, extractNeededAttributesExampleOutput);
                            const attributesStartIndex = openAIDateTime.indexOf('{');
                            const attributesEndIndex = openAIDateTime.lastIndexOf('}');
                            const attributesJSONString = openAIDateTime.slice(attributesStartIndex, attributesEndIndex + 1);
                            const attributes = JSON.parse(attributesJSONString);
                            return attributes;
                        }
                        catch (e) {
                            chatApiHelperLogger.error('Unable to extract attributes needed from user input', { userInput, error: e.message, stack: e.stack });
                            // Original function implicitly returns undefined here.
                            return undefined;
                        }
                    };
                    export const generateQueryDateFromUserInput = async (userId, timezone, userInput, userCurrentTime) => {
                        try {
                            const queryDateSysMessage = { role: 'system', content: extractQueryUserInputTimeToJSONPrompt };
                            const queryDateMessageHistory = [];
                            const queryDateUserMessage1 = { role: 'user', content: extractQueryUserInputTimeToJSONExampleInput1 };
                            const queryDateAssistantMessage1 = { role: 'assistant', content: extractQueryUserInputTimeToJSONExampleOutput1 };
                            const queryDateUserMessage2 = { role: 'user', content: extractQueryUserInputTimeToJSONExampleInput2 };
                            const queryDateAssistantMessage2 = { role: 'assistant', content: extractQueryUserInputTimeToJSONExampleOutput2 };
                            const queryDateUserMessage3 = { role: 'user', content: extractQueryUserInputTimeToJSONExampleInput3 };
                            const queryDateAssistantMessage3 = { role: 'assistant', content: extractQueryUserInputTimeToJSONExampleOutput3 };
                            // user work times
                            const userPreferences = await getUserPreferences(userId);
                            const workTimesObject = generateWorkTimesForUser(userPreferences, timezone);
                            let userWorkTimes = '';
                            for (const workTimeObject of workTimesObject) {
                                userWorkTimes += `${workTimeObject?.dayOfWeek}: ${workTimeObject?.startTime} - ${workTimeObject?.endTime} \n`;
                            }
                            chatApiHelperLogger.debug('[generateQueryDateFromUserInput] User work times string:', { userId, userWorkTimes });
                            const queryDateEngine = new TemplateEngine(extractQueryUserInputTimeToJSONTemplate);
                            const queryDateRendered = queryDateEngine.render({ userCurrentTime, userWorkTimes: userWorkTimes, userInput });
                            const queryDateUserMessageInput = { role: 'user', content: queryDateRendered };
                            queryDateMessageHistory.push(queryDateSysMessage, queryDateUserMessage1, queryDateAssistantMessage1, queryDateUserMessage2, queryDateAssistantMessage2, queryDateUserMessage3, queryDateAssistantMessage3, queryDateUserMessageInput);
                            const openAIQueryDate = await callOpenAIWithMessageHistoryOnly(openai, queryDateMessageHistory, openAIChatGPT35Model);
                            const queryDateStartIndex = openAIQueryDate.indexOf('{');
                            const queryDateEndIndex = openAIQueryDate.lastIndexOf('}');
                            const queryDateJSONString = openAIQueryDate.slice(queryDateStartIndex, queryDateEndIndex + 1);
                            const queryDate = JSON.parse(queryDateJSONString);
                            return queryDate;
                        }
                        catch (e) {
                            chatApiHelperLogger.error('Unable to generate queryDate from user input', { userId, timezone, userInput, userCurrentTime, error: e.message, stack: e.stack });
                            // Original function implicitly returns undefined here.
                            return undefined;
                        }
                    };
                    export const generateMissingFieldsQueryDateFromUserInput = async (userId, timezone, userInput, priorUserInput, priorAssistantOutput, userCurrentTime) => {
                        try {
                            const queryDateSysMessage = { role: 'system', content: extractQueryUserInputTimeToJSONPrompt };
                            const queryDateMessageHistory = [];
                            const queryDateUserMessage1 = { role: 'user', content: extractQueryUserInputTimeToJSONExampleInput1 };
                            const queryDateAssistantMessage1 = { role: 'assistant', content: extractQueryUserInputTimeToJSONExampleOutput1 };
                            const queryDateUserMessage2 = { role: 'user', content: extractQueryUserInputTimeToJSONExampleInput2 };
                            const queryDateAssistantMessage2 = { role: 'assistant', content: extractQueryUserInputTimeToJSONExampleOutput2 };
                            const queryDateUserMessage3 = { role: 'user', content: extractQueryUserInputTimeToJSONExampleInput3 };
                            const queryDateAssistantMessage3 = { role: 'assistant', content: extractQueryUserInputTimeToJSONExampleOutput3 };
                            const queryDateUserMessage4 = { role: 'user', content: priorUserInput };
                            const queryDateAssistantMessage4 = { role: 'assistant', content: priorAssistantOutput };
                            // user work times
                            const userPreferences = await getUserPreferences(userId);
                            const workTimesObject = generateWorkTimesForUser(userPreferences, timezone);
                            let userWorkTimes = '';
                            for (const workTimeObject of workTimesObject) {
                                userWorkTimes += `${workTimeObject?.dayOfWeek}: ${workTimeObject?.startTime} - ${workTimeObject?.endTime} \n`;
                            }
                            chatApiHelperLogger.debug('[generateMissingFieldsQueryDateFromUserInput] User work times string:', { userId, userWorkTimes });
                            const queryDateEngine = new TemplateEngine(extractQueryUserInputTimeToJSONTemplate);
                            const queryDateRendered = queryDateEngine.render({ userCurrentTime, userWorkTimes: userWorkTimes, userInput });
                            const queryDateUserMessageInput = { role: 'user', content: queryDateRendered };
                            queryDateMessageHistory.push(queryDateSysMessage, queryDateUserMessage1, queryDateAssistantMessage1, queryDateUserMessage2, queryDateAssistantMessage2, queryDateUserMessage3, queryDateAssistantMessage3, queryDateUserMessage4, queryDateAssistantMessage4, queryDateUserMessageInput);
                            const openAIQueryDate = await callOpenAIWithMessageHistoryOnly(openai, queryDateMessageHistory, openAIChatGPT35Model);
                            const queryDateStartIndex = openAIQueryDate.indexOf('{');
                            const queryDateEndIndex = openAIQueryDate.lastIndexOf('}');
                            const queryDateJSONString = openAIQueryDate.slice(queryDateStartIndex, queryDateEndIndex + 1);
                            const queryDate = JSON.parse(queryDateJSONString);
                            return queryDate;
                        }
                        catch (e) {
                            chatApiHelperLogger.error('Unable to generate missing fields queryDate from user input', { userId, timezone, userInput, priorUserInput, priorAssistantOutput, userCurrentTime, error: e.message, stack: e.stack });
                            return undefined;
                        }
                    };
                    export const generateDateTime = async (userInput, userCurrentTime, timezone) => {
                        try {
                            // dayjs().tz(timezone).format('dddd, YYYY-MM-DDTHH:mm:ssZ')
                            const template = userInputToDateTimeJSONPrompt;
                            const engine = new TemplateEngine(template);
                            const rendered = engine.render({ userCurrentTime });
                            const systemMessage1 = { role: 'system', content: rendered };
                            const userMessage1 = { role: 'user', content: userInputToDateTimeJSONExampleInput1 };
                            const exampleOutput1Template = userInputToDateTimeJSONExampleOutput1;
                            const engine2 = new TemplateEngine(exampleOutput1Template);
                            const currentTimeObject = dayjs(userCurrentTime, 'dddd, YYYY-MM-DDTHH:mm:ssZ').tz(timezone);
                            const year = currentTimeObject.format('YYYY');
                            const month = currentTimeObject.format('MM');
                            const exampleOutput1Rendered = engine2.render({ year, month });
                            const assistantMessage1 = { role: 'assistant', content: exampleOutput1Rendered };
                            const userMessage2 = { role: 'user', content: userInputToDateTimeJSONExampleInput2 };
                            const exampleOutput2Template = userInputToDateTimeJSONExampleOutput2;
                            const engine3 = new TemplateEngine(exampleOutput2Template);
                            const exampleOutput2Rendered = engine3.render({ year, month });
                            const assistantMessage2 = { role: 'assistant', content: exampleOutput2Rendered };
                            const userMessage3 = { role: 'user', content: userInputToDateTimeJSONExampleInput3 };
                            const assistantMessage3 = { role: 'assistant', content: userInputToDateTimeJSONExampleOutput3 };
                            const userMessage4 = { role: 'user', content: userInput };
                            const messageHistory = [];
                            messageHistory.push(systemMessage1, userMessage1, assistantMessage1, userMessage4);
                            const openAIDateTime = await callOpenAIWithMessageHistoryOnly(openai, messageHistory, openAIChatGPT35Model);
                            // const openAIDateTime = await callOpenAI(openai, userInputToDateTimeJSONPrompt, openAIChatGPT35Model, userInput, userInputToDateTimeJSONExampleInput1, userInputToDateTimeJSONExampleOutput1)
                            const dateTimeStartIndex = openAIDateTime.indexOf('{');
                            chatApiHelperLogger.debug('[generateDateTime] OpenAI response processing', { dateTimeStartIndex, openAIDateTimeLength: openAIDateTime?.length });
                            const dateTimeEndIndex = openAIDateTime.lastIndexOf('}');
                            chatApiHelperLogger.debug('[generateDateTime] OpenAI response processing', { dateTimeEndIndex });
                            const dateTimeJSONString = openAIDateTime.slice(dateTimeStartIndex, dateTimeEndIndex + 1);
                            const dateTime = JSON.parse(dateTimeJSONString);
                            return dateTime;
                        }
                        catch (e) {
                            chatApiHelperLogger.error('Unable to generate DateTime from user input', { userInput, userCurrentTime, timezone, error: e.message, stack: e.stack });
                            return undefined;
                        }
                    };
                    export const generateMissingFieldsDateTime = async (userInput, priorUserInput, priorAssistantOutput, userCurrentTime, timezone) => {
                        try {
                            // dayjs().tz(timezone).format('dddd, YYYY-MM-DDTHH:mm:ssZ')
                            const template = userInputToDateTimeJSONPrompt;
                            const engine = new TemplateEngine(template);
                            const rendered = engine.render({ userCurrentTime });
                            const systemMessage1 = { role: 'system', content: rendered };
                            const userMessage1 = { role: 'user', content: userInputToDateTimeJSONExampleInput1 };
                            const exampleOutput1Template = userInputToDateTimeJSONExampleOutput1;
                            const engine2 = new TemplateEngine(exampleOutput1Template);
                            const currentTimeObject = dayjs(userCurrentTime, 'dddd, YYYY-MM-DDTHH:mm:ssZ').tz(timezone);
                            const year = currentTimeObject.format('YYYY');
                            const month = currentTimeObject.format('MM');
                            const exampleOutput1Rendered = engine2.render({ year, month });
                            const assistantMessage1 = { role: 'assistant', content: exampleOutput1Rendered };
                            const userMessage2 = { role: 'user', content: userInputToDateTimeJSONExampleInput2 };
                            const exampleOutput2Template = userInputToDateTimeJSONExampleOutput2;
                            const engine3 = new TemplateEngine(exampleOutput2Template);
                            const exampleOutput2Rendered = engine3.render({ year, month });
                            const assistantMessage2 = { role: 'assistant', content: exampleOutput2Rendered };
                            const userMessage3 = { role: 'user', content: userInputToDateTimeJSONExampleInput3 };
                            const assistantMessage3 = { role: 'assistant', content: userInputToDateTimeJSONExampleOutput3 };
                            const userMessage4 = { role: 'user', content: priorUserInput };
                            const assistantMessage4 = { role: 'assistant', content: priorAssistantOutput };
                            const userMessage5 = { role: 'user', content: userInput };
                            const messageHistory = [];
                            messageHistory.push(systemMessage1, userMessage1, assistantMessage1, userMessage2, assistantMessage2, userMessage3, assistantMessage3, userMessage4, assistantMessage4, userMessage5);
                            const openAIDateTime = await callOpenAIWithMessageHistoryOnly(openai, messageHistory, openAIChatGPT35LongModel);
                            // const openAIDateTime = await callOpenAI(openai, userInputToDateTimeJSONPrompt, openAIChatGPT35Model, userInput, userInputToDateTimeJSONExampleInput1, userInputToDateTimeJSONExampleOutput1)
                            const dateTimeStartIndex = openAIDateTime.indexOf('{');
                            chatApiHelperLogger.debug('[generateMissingFieldsDateTime] OpenAI response processing', { dateTimeStartIndex, openAIDateTimeLength: openAIDateTime?.length });
                            const dateTimeEndIndex = openAIDateTime.lastIndexOf('}');
                            chatApiHelperLogger.debug('[generateMissingFieldsDateTime] OpenAI response processing', { dateTimeEndIndex });
                            const dateTimeJSONString = openAIDateTime.slice(dateTimeStartIndex, dateTimeEndIndex + 1);
                            const dateTime = JSON.parse(dateTimeJSONString);
                            return dateTime;
                        }
                        catch (e) {
                            chatApiHelperLogger.error('Unable to generate missing fields DateTime from user input', { userInput, priorUserInput, priorAssistantOutput, userCurrentTime, timezone, error: e.message, stack: e.stack });
                            return undefined;
                        }
                    };
                    export const generateAssistantMessageFromAPIResponseForUserQuery = async (openaiInstance, apiResponse, messageHistoryObject) => {
                        try {
                            const messageLength = messageHistoryObject.messages?.length;
                            let userMessage = '';
                            for (let i = messageLength; i > 0; i--) {
                                const message = messageHistoryObject.messages[i - 1];
                                if (message.role === 'user') {
                                    userMessage = message.content;
                                    break;
                                }
                            }
                            const template = apiResponeToAssistantResponsePrompt;
                            const engine = new TemplateEngine(template);
                            const rendered = engine.render({ userInput: userMessage, apiResponse });
                            const systemMessage = {
                                role: 'system',
                                content: rendered,
                            };
                            const res = await callOpenAIWithMessageHistoryOnly(openai, [systemMessage], openAIChatGPT35Model);
                            const assistantMessage = {
                                role: 'assistant',
                                content: res,
                            };
                            return assistantMessage;
                        }
                        catch (e) {
                            chatApiHelperLogger.error('Unable to generate assistant message from API response', { apiResponse, messageHistoryObjectId: messageHistoryObject?.id, error: e.message, stack: e.stack });
                            // Consider returning a default error message or rethrowing
                            return { role: 'assistant', content: "I encountered an issue processing that request. Please try again." }; // Example fallback
                        }
                    };
                    export const generateAssistantMessageToRequestUserForMissingFields = async (openaiInstance, missingData, messageHistoryObject) => {
                        try {
                            let missingDataString = '';
                            for (const property in missingData) {
                                if (property === 'required') {
                                    const requiredFields = missingData?.[property];
                                    if (requiredFields?.length > 0) {
                                        for (const requiredField of requiredFields) {
                                            for (const requiredProperty in requiredField) {
                                                if (requiredProperty === 'oneOf') {
                                                    const oneOfs = requiredField[requiredProperty];
                                                    if (oneOfs?.length > 0) {
                                                        for (const oneOf of oneOfs) {
                                                            for (const oneOfProperty in oneOf) {
                                                                if (oneOfProperty === 'and') {
                                                                    const objectFields = oneOf[oneOfProperty];
                                                                    if (objectFields?.length > 0) {
                                                                        for (const objectField of objectFields) {
                                                                            missingDataString += `${objectField?.value}, `;
                                                                        }
                                                                    }
                                                                }
                                                                else if (oneOfProperty === 'value') {
                                                                    const value = oneOf[oneOfProperty];
                                                                    missingDataString += `${value}, `;
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                                else if (requiredProperty === 'value') {
                                                    const value = requiredField[requiredProperty];
                                                    missingDataString += `${value}, `;
                                                }
                                                else if (requiredProperty === 'and') {
                                                    const objectFields = requiredField[requiredProperty];
                                                    if (objectFields?.length > 0) {
                                                        for (const objectField of objectFields) {
                                                            missingDataString += `${objectField?.value}, `;
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                                else if (property === 'dateTime') {
                                    const dateTime = missingData[property];
                                    for (const dateTimeProperty in dateTime) {
                                        if (dateTimeProperty === 'required') {
                                            const requiredFields = dateTime?.[dateTimeProperty];
                                            if (requiredFields?.length > 0) {
                                                for (const requiredField of requiredFields) {
                                                    for (const requiredProperty in requiredField) {
                                                        if (requiredProperty === 'oneOf') {
                                                            const oneOfs = requiredField[requiredProperty];
                                                            if (oneOfs?.length > 0) {
                                                                for (const oneOf of oneOfs) {
                                                                    for (const oneOfProperty in oneOf) {
                                                                        if (oneOfProperty === 'and') {
                                                                            const objectFields = oneOf[oneOfProperty];
                                                                            if (objectFields?.length > 0) {
                                                                                for (const objectField of objectFields) {
                                                                                    missingDataString += `${objectField?.value}, `;
                                                                                }
                                                                            }
                                                                        }
                                                                        else if (oneOfProperty === 'value') {
                                                                            const value = oneOf[oneOfProperty];
                                                                            missingDataString += `${value}, `;
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                        else if (requiredProperty === 'value') {
                                                            const value = requiredField[requiredProperty];
                                                            missingDataString += `${value}, `;
                                                        }
                                                        else if (requiredProperty === 'and') {
                                                            const objectFields = requiredField[requiredProperty];
                                                            if (objectFields?.length > 0) {
                                                                for (const objectField of objectFields) {
                                                                    missingDataString += `${objectField?.value}, `;
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                                else if (property === 'attributes') {
                                    const attributes = missingData[property];
                                    for (const attributesProperty in attributes) {
                                        if (attributesProperty === 'required') {
                                            const requiredFields = attributes?.[attributesProperty];
                                            if (requiredFields?.length > 0) {
                                                for (const requiredField of requiredFields) {
                                                    for (const requiredProperty in requiredField) {
                                                        if (requiredProperty === 'oneOf') {
                                                            const oneOfs = requiredField[requiredProperty];
                                                            if (oneOfs?.length > 0) {
                                                                for (const oneOf of oneOfs) {
                                                                    for (const oneOfProperty in oneOf) {
                                                                        if (oneOfProperty === 'and') {
                                                                            const objectFields = oneOf[oneOfProperty];
                                                                            if (objectFields?.length > 0) {
                                                                                for (const objectField of objectFields) {
                                                                                    missingDataString += `${objectField?.value}, `;
                                                                                }
                                                                            }
                                                                        }
                                                                        else if (oneOfProperty === 'value') {
                                                                            const value = oneOf[oneOfProperty];
                                                                            missingDataString += `${value}, `;
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                        else if (requiredProperty === 'value') {
                                                            const value = requiredField[requiredProperty];
                                                            missingDataString += `${value}, `;
                                                        }
                                                        else if (requiredProperty === 'and') {
                                                            const objectFields = requiredField[requiredProperty];
                                                            if (objectFields?.length > 0) {
                                                                for (const objectField of objectFields) {
                                                                    missingDataString += `${objectField?.value}, `;
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                                else if (property === 'queryDate') {
                                    const queryDate = missingData[property];
                                    for (const queryDateProperty in queryDate) {
                                        if (queryDateProperty === 'required') {
                                            const requiredFields = queryDate?.[queryDateProperty];
                                            if (requiredFields?.length > 0) {
                                                for (const requiredField of requiredFields) {
                                                    for (const requiredProperty in requiredField) {
                                                        if (requiredProperty === 'oneOf') {
                                                            const oneOfs = requiredField[requiredProperty];
                                                            if (oneOfs?.length > 0) {
                                                                for (const oneOf of oneOfs) {
                                                                    for (const oneOfProperty in oneOf) {
                                                                        if (oneOfProperty === 'and') {
                                                                            const objectFields = oneOf[oneOfProperty];
                                                                            if (objectFields?.length > 0) {
                                                                                for (const objectField of objectFields) {
                                                                                    missingDataString += `${objectField?.value}, `;
                                                                                }
                                                                            }
                                                                        }
                                                                        else if (oneOfProperty === 'value') {
                                                                            const value = oneOf[oneOfProperty];
                                                                            missingDataString += `${value}, `;
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                        else if (requiredProperty === 'value') {
                                                            const value = requiredField[requiredProperty];
                                                            missingDataString += `${value}, `;
                                                        }
                                                        else if (requiredProperty === 'and') {
                                                            const objectFields = requiredField[requiredProperty];
                                                            if (objectFields?.length > 0) {
                                                                for (const objectField of objectFields) {
                                                                    missingDataString += `${objectField?.value}, `;
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            const messageLength = messageHistoryObject.messages?.length;
                            let userMessage = '';
                            for (let i = messageLength; i > 0; i--) {
                                const message = messageHistoryObject.messages[i - 1];
                                if (message.role === 'user') {
                                    userMessage = message.content;
                                    break;
                                }
                            }
                            const template = requestMissingFieldsPrompt;
                            const engine = new TemplateEngine(template);
                            const rendered = engine.render({ userInput: userMessage, missingFields: missingDataString });
                            const systemMessage2 = {
                                role: 'system',
                                content: rendered,
                            };
                            const systemMessage1 = { role: 'system', content: requestMissingFieldsSystemsExampleInput };
                            const assistantMessage1 = { role: 'assistant', content: requestMissingFieldsExampleOutput };
                            const messageHistory = [];
                            messageHistory.push(systemMessage1, assistantMessage1, systemMessage2);
                            const openAIData = await callOpenAIWithMessageHistoryOnly(openai, messageHistory, openAIChatGPT35Model);
                            const assitantMessage = {
                                role: 'assistant',
                                content: openAIData,
                            };
                            return assitantMessage;
                        }
                        catch (e) {
                            chatApiHelperLogger.error('Unable to generate user request for missing fields', { missingDataString, messageHistoryObjectId: messageHistoryObject?.id, error: e.message, stack: e.stack });
                            return { role: 'assistant', content: "I need a bit more information to proceed. Could you clarify?" }; // Example fallback
                        }
                    };
                    export const generateJSONDataFromUserInput = async (userInput, userCurrentTime) => {
                        try {
                            const messageHistory = [];
                            const userMessage1 = { role: 'user', content: userInputToJSONExampleInput };
                            const assistantMessage1 = { role: 'assistant', content: userInputToJSONExampleOutput };
                            const dataEngine = new TemplateEngine(userInputToJSONPrompt);
                            const dataRendered = dataEngine.render({ userCurrentTime });
                            const dataSysMessage = { role: 'system', content: dataRendered };
                            const dataUserMessageInput = { role: 'user', content: userInput };
                            messageHistory.push(dataSysMessage, userMessage1, assistantMessage1, dataUserMessageInput);
                            const openAIData = await callOpenAIWithMessageHistoryOnly(openai, messageHistory, openAIChatGPT35Model);
                            const dataStartIndex = openAIData.indexOf('{');
                            const dataEndIndex = openAIData.lastIndexOf('}');
                            const dataJSONString = openAIData.slice(dataStartIndex, dataEndIndex + 1);
                            const data = JSON.parse(dataJSONString);
                            return data;
                        }
                        catch (e) {
                            chatApiHelperLogger.error('Unable to generate JSON data from user input', { userInput, userCurrentTime, error: e.message, stack: e.stack });
                            return undefined;
                        }
                    };
                    export const generateMissingFieldsJSONDataFromUserInput = async (userInput, priorUserInput, priorAssistantOutput, userCurrentTime) => {
                        try {
                            const messageHistory = [];
                            const userMessage1 = { role: 'user', content: userInputToJSONExampleInput };
                            const assistantMessage1 = { role: 'assistant', content: userInputToJSONExampleOutput };
                            const dataEngine = new TemplateEngine(userInputToJSONPrompt);
                            const dataRendered = dataEngine.render({ userCurrentTime });
                            const dataSysMessage = { role: 'system', content: dataRendered };
                            const dataUserMessageInput = { role: 'user', content: userInput };
                            const userMessage2 = { role: 'user', content: priorUserInput };
                            const assistantMessage2 = { role: 'assistant', content: priorAssistantOutput };
                            messageHistory.push(dataSysMessage, userMessage1, assistantMessage1, userMessage2, assistantMessage2, dataSysMessage, dataUserMessageInput);
                            const openAIData = await callOpenAIWithMessageHistoryOnly(openai, messageHistory, openAIChatGPT35Model);
                            const dataStartIndex = openAIData.indexOf('{');
                            const dataEndIndex = openAIData.lastIndexOf('}');
                            const dataJSONString = openAIData.slice(dataStartIndex, dataEndIndex + 1);
                            const data = JSON.parse(dataJSONString);
                            return data;
                        }
                        catch (e) {
                            chatApiHelperLogger.error('Unable to generate missing fields JSON data from user input', { userInput, priorUserInput, priorAssistantOutput, userCurrentTime, error: e.message, stack: e.stack });
                            return undefined;
                        }
                    };
                    export const generateWorkSchedule = async (userId, timezone, windowStartDate, windowEndDate) => {
                        try {
                            // listEventsForUserGivenDates
                            const events = await listEventsForUserGivenDates(userId, windowStartDate, windowEndDate);
                            let userSchedule = '';
                            const uniqDates = _.uniqBy(events, (curr) => (dayjs(curr?.startDate?.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD')));
                            for (const uniqDate of uniqDates) {
                                const filteredEvents = events?.filter(a => (dayjs(a?.startDate?.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD') === dayjs(uniqDate?.startDate?.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD')));
                                if (filteredEvents?.length > 0) {
                                    userSchedule += `${dayjs(uniqDate?.startDate?.slice(0, 19)).tz(timezone, true).format('ddd')} (${dayjs(uniqDate?.startDate?.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD')}) \n`;
                                    for (const filteredEvent of filteredEvents) {
                                        userSchedule += `- ${filteredEvent?.title || filteredEvent?.summary}: ${dayjs(filteredEvent?.startDate?.slice(0, 19)).tz(timezone, true).format('h:mm a')} - ${dayjs(filteredEvent?.endDate?.slice(0, 19)).tz(timezone, true).format('h:mm a')} \n`;
                                    }
                                }
                            }
                            return userSchedule;
                        }
                        catch (e) {
                            chatApiHelperLogger.error('Unable to generate work schedule', { userId, timezone, windowStartDate, windowEndDate, error: e.message, stack: e.stack });
                            return ""; // Return empty string or handle error as appropriate
                        }
                    };
                    export const findAnEmptySlot = async (userId, timezone, windowStartDate, windowEndDate, eventDuration) => {
                        try {
                            const userSchedule = await generateWorkSchedule(userId, timezone, windowStartDate, windowEndDate);
                            const dataEngine = new TemplateEngine(findASlotForNewEventTemplate);
                            const dataRendered = dataEngine.render({ eventDuration: `${eventDuration}`, userSchedule });
                            const emptySlotRes = await callOpenAI(openai, findASlotForNewEventPrompt, openAIChatGPT35Model, dataRendered, findASlotForNewEventExampleInput, findASlotForNewEventExampleOutput);
                            const dataStartIndex = emptySlotRes.indexOf('{');
                            const dataEndIndex = emptySlotRes.lastIndexOf('}');
                            const dataJSONString = emptySlotRes.slice(dataStartIndex, dataEndIndex + 1);
                            const data = JSON.parse(dataJSONString);
                            return data;
                        }
                        catch (e) {
                            chatApiHelperLogger.error('Unable to find an empty slot', { userId, timezone, windowStartDate, windowEndDate, eventDuration, error: e.message, stack: e.stack });
                            return undefined;
                        }
                    };
                    return undefined;
                };
                export const callOpenAIWithMessageHistoryOnly = async (openaiInstance, messageHistory = [], model = 'gpt-3.5-turbo') => {
                    try {
                        const completion = await openaiInstance.chat.completions.create({
                            model,
                            messages: messageHistory,
                        });
                        return completion.choices[0]?.message?.content || '';
                    }
                    catch (e) {
                        chatApiHelperLogger.error('Error in callOpenAIWithMessageHistoryOnly:', e.message);
                        throw e;
                    }
                };
            };
        };
    };
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsbURBQW1EO0FBQ25ELE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxnQ0FBZ0MsQ0FBQztBQUN4RCxPQUFPLE1BQU0sTUFBTSxRQUFRLENBQUE7QUFDM0IsT0FBTyxLQUFLLE1BQU0sYUFBYSxDQUFDO0FBQ2hDLE9BQU8sRUFBRSx1QkFBdUIsRUFBRSxvQkFBb0IsRUFBRSxnQkFBZ0IsRUFBRSxXQUFXLEVBQUUsWUFBWSxFQUFFLGdCQUFnQixFQUFFLGFBQWEsRUFBRSxXQUFXLEVBQUUsZ0JBQWdCLEVBQUUsZUFBZSxFQUFFLHFCQUFxQixFQUFFLHVCQUF1QixFQUFFLGlCQUFpQixFQUFFLGlCQUFpQixFQUFFLDJCQUEyQixFQUFFLHFCQUFxQixFQUFFLGNBQWMsRUFBRSxrQkFBa0IsRUFBRSxHQUFHLEVBQUUsbUJBQW1CLEVBQUUsb0JBQW9CLEVBQUUsd0JBQXdCLEVBQUUsTUFBTSxhQUFhLENBQUM7QUFFbGMsT0FBTyxFQUFTLEtBQUssRUFBRSxTQUFTLEVBQUUsU0FBUyxFQUFFLE1BQU0sdUJBQXVCLENBQUM7QUFDM0UsT0FBTyxFQUFFLFlBQVksRUFBRSxZQUFZLElBQUksdUJBQXVCLEVBQXVDLGlCQUFpQixFQUFFLG9CQUFvQixFQUFFLG9CQUFvQixJQUFJLDJCQUEyQixFQUFFLHlCQUF5QixFQUFFLE1BQU0sOEJBQThCLENBQUM7QUFJblEsT0FBTyxFQUFrQix1QkFBdUIsRUFBNkMsTUFBTSxtQkFBbUIsQ0FBQztBQUN2SCxPQUFPLEdBQUcsTUFBTSxLQUFLLENBQUM7QUFHdEIsT0FBTyxLQUFLLE1BQU0sT0FBTyxDQUFDO0FBRTFCLE9BQU8sTUFBTSxNQUFNLFFBQVEsQ0FBQTtBQUszQixPQUFPLEVBQUUsTUFBTSxFQUFFLE1BQU0sWUFBWSxDQUFDO0FBQ3BDLE9BQU8sRUFBRSxFQUFFLElBQUksSUFB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QWM7eUJBQzNCLENBQUMsQ0FBQzt3QkFDSCxPQUFPLFVBQVUsQ0FBQyxPQUFPLENBQUMsQ0FBQyxDQUFDLEVBQUUsT0FBTyxFQUFFLE9BQU8sSUFBSSxFQUFFLENBQUM7b0JBQ3pELENBQUM7b0JBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQzt3QkFDVCxtQkFBbUIsQ0FBQyxLQUFLLENBQUMsNENBQTRDLEVBQUcsQ0FBVyxDQUFDLE9BQU8sQ0FBQyxDQUFDO3dCQUM5RixNQUFNLENBQUMsQ0FBQztvQkFDWixDQUFDO2dCQUlMLENBQUMsQ0FBQTtZQUNELENBQUMsQUFEQSxDQUFBO1FBQ0QsQ0FBQyxBQURBLENBQUE7SUFDRCxDQUFDLEFBREEsQ0FBQTtBQUNELENBQUMsQUFEQSxDQUFBIiwic291cmNlc0NvbnRlbnQiOlsiLy8gaW1wb3J0IHsgU0VTQ2xpZW50IH0gZnJvbSBcIkBhd3Mtc2RrL2NsaWVudC1zZXNcIjtcbmltcG9ydCB7IENsaWVudCB9IGZyb20gJ0BvcGVuc2VhcmNoLXByb2plY3Qvb3BlbnNlYXJjaCc7XG5pbXBvcnQgT3BlbkFJIGZyb20gXCJvcGVuYWlcIlxuaW1wb3J0IHJldHJ5IGZyb20gJ2FzeW5jLXJldHJ5JztcbmltcG9ydCB7IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LCBwb3N0Z3JhcGhpbGVHcmFwaFVybCwgem9vbUJhc2VUb2tlblVybCwgem9vbUJhc2VVcmwsIHpvb21DbGllbnRJZCwgem9vbUNsaWVudFNlY3JldCwgem9vbUlWRm9yUGFzcywgem9vbVBhc3NLZXksIHpvb21SZXNvdXJjZU5hbWUsIHpvb21TYWx0Rm9yUGFzcywgZ29vZ2xlQ2xpZW50SWRBbmRyb2lkLCBnb29nbGVDbGllbnRJZEF0b21pY1dlYiwgZ29vZ2xlQ2xpZW50SWRJb3MsIGdvb2dsZUNsaWVudElkV2ViLCBnb29nbGVDbGllbnRTZWNyZXRBdG9taWNXZWIsIGdvb2dsZUNsaWVudFNlY3JldFdlYiwgZ29vZ2xlVG9rZW5VcmwsIGdvb2dsZUNhbGVuZGFyTmFtZSwgRGF5LCBkZWZhdWx0T3BlbkFJQVBJS2V5LCBvcGVuQUlDaGF0R1BUMzVNb2RlbCwgb3BlbkFJQ2hhdEdQVDM1TG9uZ01vZGVsIH0gZnJvbSBcIi4vY29uc3RhbnRzXCI7XG5cbmltcG9ydCB7IERheWpzLCBkYXlqcywgZ2V0SVNPRGF5LCBzZXRJU09EYXkgfSBmcm9tIFwiLi9kYXRldGltZS9kYXRlLXV0aWxzXCI7XG5pbXBvcnQgeyBzZWFyY2hFdmVudHMsIGdldEV2ZW50QnlJZCBhcyBnZXRFdmVudEZyb21MYW5jZURiQnlJZCwgdXBzZXJ0RXZlbnRzIGFzIGxhbmNlZGJVcHNlcnRFdmVudHMsIGRlbGV0ZUV2ZW50c0J5SWRzLCBzZWFyY2hUcmFpbmluZ0V2ZW50cywgdXBzZXJ0VHJhaW5pbmdFdmVudHMgYXMgbGFuY2VkYlVwc2VydFRyYWluaW5nRXZlbnRzLCBkZWxldGVUcmFpbmluZ0V2ZW50c0J5SWRzIH0gZnJvbSAnLi4vLi4vX3V0aWxzL2xhbmNlZGJfc2VydmljZSc7XG5pbXBvcnQgeyBFdmVudFNjaGVtYSBhcyBMYW5jZURiRXZlbnRTY2hlbWEsIFRyYWluaW5nRXZlbnRTY2hlbWEgYXMgTGFuY2VEYlRyYWluaW5nRXZlbnRTY2hlbWEgfSBmcm9tICcuLi8uLi9fdXRpbHMvbGFuY2VkYl9zZXJ2aWNlJztcbmltcG9ydCBEYXRlVGltZUpTT05UeXBlLCB7IFJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3dUeXBlLCBSZWxhdGl2ZVRpbWVGcm9tTm93VHlwZSB9IGZyb20gXCIuL2RhdGV0aW1lL0RhdGVUaW1lSlNPTkpTT05UeXBlXCI7XG5cbmltcG9ydCB7IEJ1ZmZlclRpbWVUeXBlLCBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZSwgUmVjdXJyZW5jZVJ1bGVUeXBlLCBTZW5kVXBkYXRlc1R5cGUsIFRpbWUgfSBmcm9tIFwiLi90eXBlcy9FdmVudFR5cGVcIjtcbmltcG9ydCBnb3QgZnJvbSBcImdvdFwiO1xuaW1wb3J0IHsgQ2FsZW5kYXJUeXBlIH0gZnJvbSBcIi4vdHlwZXMvQ2FsZW5kYXJUeXBlXCI7XG5pbXBvcnQgeyBDYWxlbmRhckludGVncmF0aW9uVHlwZSB9IGZyb20gXCIuL3R5cGVzL0NhbGVuZGFySW50ZWdyYXRpb25UeXBlXCI7XG5pbXBvcnQgYXhpb3MgZnJvbSBcImF4aW9zXCI7XG5cbmltcG9ydCBjcnlwdG8gZnJvbSAnY3J5cHRvJ1xuaW1wb3J0IHsgWm9vbU1lZXRpbmdPYmplY3RUeXBlIH0gZnJvbSBcIi4vdHlwZXMvWm9vbU1lZXRpbmdPYmplY3RUeXBlXCI7XG5pbXBvcnQgeyBHb29nbGVSZW1pbmRlclR5cGUgfSBmcm9tIFwiLi90eXBlcy9Hb29nbGVSZW1pbmRlclR5cGVcIjtcbmltcG9ydCB7IEdvb2dsZVJlc1R5cGUgfSBmcm9tIFwiLi90eXBlcy9Hb29nbGVSZXNUeXBlXCI7XG5pbXBvcnQgeyBHb29nbGVTZW5kVXBkYXRlc1R5cGUsIEdvb2dsZUF0dGVuZGVlVHlwZSwgR29vZ2xlQ29uZmVyZW5jZURhdGFUeXBlLCBHb29nbGVFeHRlbmRlZFByb3BlcnRpZXNUeXBlLCBHb29nbGVUcmFuc3BhcmVuY3lUeXBlLCBHb29nbGVWaXNpYmlsaXR5VHlwZSwgR29vZ2xlU291cmNlVHlwZSwgR29vZ2xlQXR0YWNobWVudFR5cGUsIEdvb2dsZUV2ZW50VHlwZTEsIFJlbWluZGVyVHlwZSB9IGZyb20gXCIuL3R5cGVzL0dvb2dsZVR5cGVzXCI7XG5pbXBvcnQgeyBnb29nbGUgfSBmcm9tIFwiZ29vZ2xlYXBpc1wiO1xuaW1wb3J0IHsgdjQgYXMgdXVpZCB9IGZyb20gJ3V1aWQnXG5pbXBvcnQgeyBDb25mZXJlbmNlVHlwZSB9IGZyb20gXCIuL3R5cGVzL0NvbmZlcmVuY2VUeXBlXCI7XG5pbXBvcnQgXyBmcm9tIFwibG9kYXNoXCI7XG5pbXBvcnQgeyBFdmVudFR5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9FdmVudFR5cGUnO1xuaW1wb3J0IGdldEV2ZW50QnlJZCBmcm9tIFwiLi9ncWwvZ2V0RXZlbnRCeUlkXCI7XG5pbXBvcnQgeyBQcmVBbmRQb3N0RXZlbnRSZXR1cm5UeXBlIH0gZnJvbSBcIi4vdHlwZXMvUHJlQW5kUG9zdEV2ZW50UmV0dXJuVHlwZVwiO1xuaW1wb3J0IHsgQXR0ZW5kZWVUeXBlIH0gZnJvbSBcIi4vdHlwZXMvQXR0ZW5kZWVUeXBlXCI7XG5pbXBvcnQgaW5zZXJ0QXR0ZW5kZWVzRm9yRXZlbnQgZnJvbSBcIi4vZ3FsL2luc2VydEF0dGVuZGVlc0ZvckV2ZW50XCI7XG5pbXBvcnQgZmluZENvbnRhY3RWaWFFbWFpbEJ5VXNlcklkIGZyb20gXCIuL2dxbC9maW5kQ29udGFjdFZpYUVtYWlsQnlVc2VySWRcIjtcbmltcG9ydCB7IENvbnRhY3RUeXBlIH0gZnJvbSBcIi4vdHlwZXMvQ29udGFjdFR5cGVcIjtcbmltcG9ydCBnZXRDb25mZXJlbmNlQnlJZCBmcm9tIFwiLi9ncWwvZ2V0Q29uZmVyZW5jZUJ5SWRcIjtcbmltcG9ydCBkZWxldGVDb25mZXJlbmNlQnlJZCBmcm9tIFwiLi9ncWwvZGVsZXRlQ29uZmVyZW5jZUJ5SWRcIjtcbmltcG9ydCBxcyBmcm9tICdxcydcbmltcG9ydCBkZWxldGVFdmVudEJ5SWQgZnJvbSBcIi4vZ3FsL2RlbGV0ZUV2ZW50QnlJZFwiO1xuaW1wb3J0ICogYXMgcGtnIGZyb20gJ3JydWxlJztcblxuaW1wb3J0IHsgaW50ZXJvcERlZmF1bHQgfSBmcm9tICdtbGx5J1xuY29uc3QgeyBSUnVsZSB9ID0gaW50ZXJvcERlZmF1bHQocGtnKTtcbmltcG9ydCBEYXlPZldlZWtUeXBlIGZyb20gXCIuL3R5cGVzL0RheU9mV2Vla1R5cGVcIjtcbmltcG9ydCBCeU1vbnRoRGF5VHlwZSBmcm9tIFwiLi90eXBlcy9CeU1vbnRoRGF5VHlwZVwiO1xuaW1wb3J0IHsgZ2V0V2Vla09mTW9udGggfSBmcm9tICdkYXRlLWZucydcbmltcG9ydCB7IE1lZXRpbmdBc3Npc3RUeXBlIH0gZnJvbSBcIi4vdHlwZXMvTWVldGluZ0Fzc2lzdFR5cGVcIjtcbmltcG9ydCBpbnNlcnRNZWV0aW5nQXNzaXN0T25lIGZyb20gXCIuL2dxbC9pbnNlcnRNZWV0aW5nQXNzaXN0T25lXCI7XG5pbXBvcnQgeyBVc2VyQ29udGFjdEluZm9UeXBlIH0gZnJvbSBcIi4vdHlwZXMvVXNlckNvbnRhY3RJbmZvVHlwZVwiO1xuaW1wb3J0IHsgTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSB9IGZyb20gXCIuL3R5cGVzL01lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVcIjtcbmltcG9ydCBpbnNlcnRNZWV0aW5nQXNzaXN0QXR0ZW5kZWVPbmUgZnJvbSBcIi4vZ3FsL2luc2VydE1lZXRpbmdBc3Npc3RBdHRlbmRlZU9uZVwiO1xuaW1wb3J0IGxpc3RVc2VyQ29udGFjdEluZm9zQnlVc2VySWQgZnJvbSBcIi4vZ3FsL2xpc3RVc2VyQ29udGFjdEluZm9zQnlVc2VySWRcIjtcbmltcG9ydCB7IE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlIH0gZnJvbSBcIi4vdHlwZXMvTWVldGluZ0Fzc2lzdEludml0ZVR5cGVcIjtcbmltcG9ydCB1cHNlcnRNZWV0aW5nQXNzaXN0SW52aXRlR3JhcGhxbCBmcm9tIFwiLi9ncWwvdXBzZXJ0TWVldGluZ0Fzc2lzdEludml0ZUdyYXBocWxcIjtcbmltcG9ydCB7IFVzZXJUeXBlIH0gZnJvbSBcIi4vdHlwZXMvVXNlclR5cGVcIjtcbmltcG9ydCB1cGRhdGVOYW1lRm9yVXNlcklkIGZyb20gXCIuL2dxbC91cGRhdGVOYW1lRm9yVXNlcklkXCI7XG5pbXBvcnQgZ2V0Q29udGFjdEluZm9zQnlJZHMgZnJvbSBcIi4vZ3FsL2dldENvbnRhY3RJbmZvc0J5SWRzXCI7XG5pbXBvcnQgZ2V0Q29udGFjdEJ5TmFtZUZvclVzZXJJZCBmcm9tIFwiLi9ncWwvZ2V0Q29udGFjdEJ5TmFtZUZvclVzZXJJZFwiO1xuaW1wb3J0IGdldFVzZXJCeUlkIGZyb20gXCIuL2dxbC9nZXRVc2VyQnlJZFwiO1xuXG5pbXBvcnQgeyBDaGF0R1BUTWVzc2FnZUhpc3RvcnlUeXBlIH0gZnJvbSBcIi4vdHlwZXMvQ2hhdEdQVFR5cGVzXCI7XG5pbXBvcnQgeyBVc2VyT3BlbkFJVHlwZSB9IGZyb20gXCIuL3R5cGVzL1VzZXJPcGVuQUlUeXBlXCI7XG5pbXBvcnQgZ2V0VGFza0J5SWQgZnJvbSBcIi4vZ3FsL2dldFRhc2tCeUlkXCI7XG5pbXBvcnQgeyBUYXNrVHlwZSB9IGZyb20gXCIuL3R5cGVzL1Rhc2tUeXBlXCI7XG5pbXBvcnQgeyBDcmVhdGVab29tTWVldGluZ1JlcXVlc3RCb2R5VHlwZSB9IGZyb20gXCIuL3NraWxscy9vcmRlckNhbGVuZGFyL3NjaGVkdWxlTWVldGluZy90eXBlc1wiO1xuaW1wb3J0IHsgZXh0cmFjdFF1ZXJ5VXNlcklucHV0VGltZVRvSlNPTlByb21wdCwgZXh0cmFjdFF1ZXJ5VXNlcklucHV0VGltZVRvSlNPTkV4YW1wbGVJbnB1dDEsIGV4dHJhY3RRdWVyeVVzZXJJbnB1dFRpbWVUb0pTT05FeGFtcGxlT3V0cHV0MSwgZXh0cmFjdFF1ZXJ5VXNlcklucHV0VGltZVRvSlNPTkV4YW1wbGVJbnB1dDIsIGV4dHJhY3RRdWVyeVVzZXJJbnB1dFRpbWVUb0pTT05FeGFtcGxlT3V0cHV0MiwgZXh0cmFjdFF1ZXJ5VXNlcklucHV0VGltZVRvSlNPTkV4YW1wbGVJbnB1dDMsIGV4dHJhY3RRdWVyeVVzZXJJbnB1dFRpbWVUb0pTT05FeGFtcGxlT3V0cHV0MywgZXh0cmFjdFF1ZXJ5VXNlcklucHV0VGltZVRvSlNPTlRlbXBsYXRlLCB1c2VySW5wdXRUb0RhdGVUaW1lSlNPTlByb21wdCwgdXNlcklucHV0VG9EYXRlVGltZUpTT05FeGFtcGxlSW5wdXQxLCB1c2VySW5wdXRUb0RhdGVUaW1lSlNPTkV4YW1wbGVPdXRwdXQxLCB1c2VySW5wdXRUb0RhdGVUaW1lSlNPTkV4YW1wbGVJbnB1dDIsIHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09ORXhhbXBsZUlucHV0MywgdXNlcklucHV0VG9EYXRlVGltZUpTT05FeGFtcGxlT3V0cHV0MiwgdXNlcklucHV0VG9EYXRlVGltZUpTT05FeGFtcGxlT3V0cHV0MyB9IGZyb20gXCIuL2RhdGV0aW1lL3Byb21wdHNcIjtcbmltcG9ydCBRdWVyeUNhbGVuZGFyRXh0cmFjdGVkSlNPTlR5cGUgZnJvbSBcIi4vZGF0ZXRpbWUvUXVlcnlDYWxlbmRhckV4dHJhY3RlZERhdGVKU09OVHlwZVwiO1xuaW1wb3J0IHsgZ2V0VXNlclByZWZlcmVuY2VzLCBnZW5lcmF0ZVdvcmtUaW1lc0ZvclVzZXIgfSBmcm9tIFwiLi9za2lsbHMvYXNrQ2FsZW5kYXIvYXBpLWhlbHBlclwiO1xuaW1wb3J0IHsgVGVtcGxhdGVFbmdpbmUgfSBmcm9tIFwiLi90ZW1wbGF0ZS1lbmdpbmVcIjtcbmltcG9ydCB7IEFzc2lzdGFudE1lc3NhZ2VUeXBlLCBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSwgU3lzdGVtTWVzc2FnZVR5cGUgfSBmcm9tICcuL3R5cGVzL01lc3NhZ2luZy9NZXNzYWdpbmdUeXBlcyc7XG5pbXBvcnQgUmVxdWlyZWRGaWVsZHNUeXBlIGZyb20gXCIuL3R5cGVzL1JlcXVpcmVkRmllbGRzVHlwZVwiO1xuaW1wb3J0IHtyZXF1ZXN0TWlzc2luZ0ZpZWxkc0V4YW1wbGVPdXRwdXQsIHJlcXVlc3RNaXNzaW5nRmllbGRzUHJvbXB0LCByZXF1ZXN0TWlzc2luZ0ZpZWxkc1N5c3RlbXNFeGFtcGxlSW5wdXR9IGZyb20gXCIuL3Byb21wdHMvcmVxdWVzdE1pc3NpbmdEYXRhXCI7XG5pbXBvcnQgeyBhcGlSZXNwb25lVG9Bc3Npc3RhbnRSZXNwb25zZVByb21wdCB9IGZyb20gXCIuL3Byb21wdHMvYXBpUmVzcG9uc2VUb0Fzc2lzdGFudFJlc3BvbnNlXCI7XG5pbXBvcnQgeyB1c2VySW5wdXRUb0pTT05FeGFtcGxlSW5wdXQsIHVzZXJJbnB1dFRvSlNPTkV4YW1wbGVPdXRwdXQsIHVzZXJJbnB1dFRvSlNPTlByb21wdCB9IGZyb20gXCIuL3Byb21wdHMvdXNlclJlcXVlc3RJbnB1dFRvSlNPTlwiO1xuaW1wb3J0IFVzZXJJbnB1dFRvSlNPTlR5cGUgZnJvbSBcIi4vdHlwZXMvVXNlcklucHV0VG9KU09OVHlwZVwiO1xuaW1wb3J0IHsgZXh0cmFjdE5lZWRlZEF0dHJpYnV0ZXNFeGFtcGxlSW5wdXQsIGV4dHJhY3ROZWVkZWRBdHRyaWJ1dGVzRXhhbXBsZU91dHB1dCwgZXh0cmFjdE5lZWRlZEF0dHJpYnV0ZXNQcm9tcHQgfSBmcm9tIFwiLi9za2lsbHMvYXNrQ2FsZW5kYXIvcHJvbXB0c1wiO1xuaW1wb3J0IHsgUXVlcnlDYWxlbmRhckV4dHJhY3RlZEF0dHJpYnV0ZXNUeXBlIH0gZnJvbSBcIi4vc2tpbGxzL2Fza0NhbGVuZGFyL3R5cGVzXCI7XG5pbXBvcnQgeyBmaW5kQVNsb3RGb3JOZXdFdmVudEV4YW1wbGVJbnB1dCwgZmluZEFTbG90Rm9yTmV3RXZlbnRFeGFtcGxlT3V0cHV0LCBmaW5kQVNsb3RGb3JOZXdFdmVudFByb21wdCwgZmluZEFTbG90Rm9yTmV3RXZlbnRUZW1wbGF0ZSB9IGZyb20gJy4vcHJvbXB0cy9maW5kQVNsb3RGb3JOZXdFdmVudCc7XG5pbXBvcnQgeyBGaW5kQVNsb3RUeXBlIH0gZnJvbSBcIi4vdHlwZXMvRmluZEFTbG90VHlwZVwiO1xuaW1wb3J0IHsgQ2hhdEdQVFJvbGVUeXBlIH0gZnJvbSBcIkAvZ3B0LW1lZXRpbmcvX2xpYnMvdHlwZXMvQ2hhdEdQVFR5cGVzXCI7XG5pbXBvcnQgd2luc3RvbiBmcm9tICd3aW5zdG9uJzsgLy8gQWRkZWQgZm9yIGxvZ2dlclxuXG4vLyBjb25zdCBzZXNDbGllbnQgPSBuZXcgU0VTQ2xpZW50KHsgcmVnaW9uOiBcInVzLWVhc3QtMVwiIH0pXG5cbi8vIExvZ2dlciBTZXR1cCBmb3IgdGhpcyBhcGktaGVscGVyXG5jb25zdCBjaGF0QXBpSGVscGVyTG9nZ2VyID0gd2luc3Rvbi5jcmVhdGVMb2dnZXIoe1xuICBsZXZlbDogcHJvY2Vzcy5lbnYuTE9HX0xFVkVMIHx8ICdpbmZvJyxcbiAgZm9ybWF0OiB3aW5zdG9uLmZvcm1hdC5jb21iaW5lKFxuICAgIHdpbnN0b24uZm9ybWF0LnRpbWVzdGFtcCgpLFxuICAgIHdpbnN0b24uZm9ybWF0Lmpzb24oKSxcbiAgICB3aW5zdG9uLmZvcm1hdCgoaW5mbykgPT4ge1xuICAgICAgaW5mby5tb2R1bGUgPSAnY2hhdC1hcGktaGVscGVyJztcbiAgICAgIHJldHVybiBpbmZvO1xuICAgIH0pKClcbiAgfSwge1xuICB0cmFuc3BvcnRzOiBbXG4gICAgbmV3IHdpbnN0b24udHJhbnNwb3J0cy5Db25zb2xlKCksXG4gIF0sXG59KTtcblxuY29uc3Qgb3BlbmFpID0gbmV3IE9wZW5BSSh7XG4gICAgYXBpS2V5OiBkZWZhdWx0T3BlbkFJQVBJS2V5LFxufSk7XG5cbmV4cG9ydCBjb25zdCBvcGVuVHJhaW5FdmVudEluZGV4ID0gJ2tubi1vcGVuLXRyYWluLWV2ZW50LWluZGV4JztcbmV4cG9ydCBjb25zdCBvcGVuVHJhaW5FdmVudFZlY3Rvck5hbWUgPSAnZW1iZWRkaW5ncyc7XG5cbmNvbnN0IGdldFNlYXJjaENsaWVudCA9IGFzeW5jICgpID0+IHtcbiAgdHJ5IHtcbiAgICByZXR1cm4gbmV3IENsaWVudCh7XG4gICAgICBub2RlOiBwcm9jZXNzLmVudi5PUEVOU0VBUkNIX0VORFBPSU5UIHx8ICcnLFxuICAgICAgYXV0aDoge1xuICAgICAgICB1c2VybmFtZTogcHJvY2Vzcy5lbnYuT1BFTlNFQVJDSF9VU0VSTkFNRSB8fCAnJyxcbiAgICAgICAgcGFzc3dvcmQ6IHByb2Nlc3MuZW52Lk9QRU5TRUFSQ0hfUEFTU1dPUkQgfHwgJycsXG4gICAgICB9LFxuICAgIH0pO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcihlLCAndW5hYmxlIHRvIGdldCBjcmVkZW50aWFscyBmcm9tIGdldFNlYXJjaENsaWVudCcpO1xuICB9XG59O1xuXG4vLyBIZWxwZXIgZm9yIHJlc2lsaWVudCBQb3N0Z3JhcGhpbGUgY2FsbHMgdXNpbmcgZ290XG5jb25zdCByZXNpbGllbnRHb3RQb3N0UG9zdGdyYXBoaWxlID0gYXN5bmMgKG9wZXJhdGlvbk5hbWU6IHN0cmluZywgcXVlcnk6IHN0cmluZywgdmFyaWFibGVzOiBSZWNvcmQ8c3RyaW5nLCBhbnk+LCB1c2VySWQ/OiBzdHJpbmcpID0+IHtcbiAgY29uc3QgTUFYX1JFVFJJRVMgPSAzO1xuICBjb25zdCBJTklUSUFMX1RJTUVPVVRfTVMgPSAxMDAwMDsgLy8gMTAgc2Vjb25kcyBmb3IgUG9zdGdyYXBoaWxlIGNhbGxzXG4gIGxldCBhdHRlbXB0ID0gMDtcbiAgbGV0IGxhc3RFcnJvcjogYW55ID0gbnVsbDtcblxuICBjb25zdCBoZWFkZXJzOiBSZWNvcmQ8c3RyaW5nLCBzdHJpbmc+ID0ge1xuICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogdXNlcklkID8gJ3VzZXInIDogJ2FkbWluJyxcbiAgfTtcbiAgaWYgKHVzZXJJZCkge1xuICAgIGhlYWRlcnNbJ1gtUG9zdGdyYXBoaWxlLVVzZXItSWQnXSA9IHVzZXJJZDtcbiAgfVxuXG4gIHdoaWxlIChhdHRlbXB0IDwgTUFYX1JFVFJJRVMpIHtcbiAgICB0cnkge1xuICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKGBQb3N0Z3JhcGhpbGUgY2FsbCBhdHRlbXB0ICR7YXR0ZW1wdCArIDF9IGZvciAke29wZXJhdGlvbk5hbWV9YCwgeyB1c2VySWQsIG9wZXJhdGlvbk5hbWUgfSk7XG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGdvdC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgIGpzb246IHsgb3BlcmF0aW9uTmFtZSwgcXVlcnksIHZhcmlhYmxlcyB9LFxuICAgICAgICBoZWFkZXJzLFxuICAgICAgICB0aW1lb3V0OiB7IHJlcXVlc3Q6IElOSVRJQUxfVElNRU9VVF9NUyB9LFxuICAgICAgICByZXNwb25zZVR5cGU6ICdqc29uJyxcbiAgICAgIH0pLmpzb248eyBkYXRhPzogYW55OyBlcnJvcnM/OiBhbnlbXSB9PigpOyAvLyBTcGVjaWZ5IHJlc3BvbnNlIHR5cGUgZm9yIGdvdFxuXG4gICAgICBpZiAocmVzcG9uc2UuZXJyb3JzKSB7XG4gICAgICAgIGxhc3RFcnJvciA9IG5ldyBFcnJvcihgR3JhcGhRTCBlcnJvciBpbiAke29wZXJhdGlvbk5hbWV9OiAke0pTT04uc3RyaW5naWZ5KHJlc3BvbnNlLmVycm9ycyl9YCk7XG4gICAgICAgIC8vIFBvdGVudGlhbGx5IGJyZWFrIGhlcmUgZm9yIG5vbi1yZXRyeWFibGUgR3JhcGhRTCBlcnJvcnMsIGUuZy4gdmFsaWRhdGlvblxuICAgICAgICAvLyBGb3Igbm93LCB3ZSByZXRyeSBhbGwgR3JhcGhRTCBlcnJvcnMgZnJvbSBQb3N0Z3JhcGhpbGUuXG4gICAgICAgIHRocm93IGxhc3RFcnJvcjtcbiAgICAgIH1cbiAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbyhgUG9zdGdyYXBoaWxlIGNhbGwgJHtvcGVyYXRpb25OYW1lfSBzdWNjZXNzZnVsIG9uIGF0dGVtcHQgJHthdHRlbXB0ICsgMX1gLCB7IHVzZXJJZCwgb3BlcmF0aW9uTmFtZSB9KTtcbiAgICAgIHJldHVybiByZXNwb25zZS5kYXRhO1xuICAgIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICAgIGxhc3RFcnJvciA9IGVycm9yO1xuICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci53YXJuKGBQb3N0Z3JhcGhpbGUgY2FsbCBhdHRlbXB0ICR7YXR0ZW1wdCArIDF9IGZvciAke29wZXJhdGlvbk5hbWV9IGZhaWxlZC5gLCB7XG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgZXJyb3I6IGVycm9yLm1lc3NhZ2UsXG4gICAgICAgIGNvZGU6IGVycm9yLmNvZGUsXG4gICAgICAgIC8vIHJlc3BvbnNlOiBlcnJvci5yZXNwb25zZT8uYm9keVxuICAgICAgfSk7XG5cbiAgICAgIC8vIENoZWNrIGZvciBub24tcmV0cnlhYmxlIEhUVFAgZXJyb3JzIGZyb20gYGdvdGBcbiAgICAgIGlmIChlcnJvci5yZXNwb25zZSAmJiBlcnJvci5yZXNwb25zZS5zdGF0dXNDb2RlKSB7XG4gICAgICAgIGNvbnN0IHN0YXR1cyA9IGVycm9yLnJlc3BvbnNlLnN0YXR1c0NvZGU7XG4gICAgICAgIGlmIChzdGF0dXMgPCA1MDAgJiYgc3RhdHVzICE9PSA0MjkgJiYgc3RhdHVzICE9PSA0MDgpIHsgLy8gRG9uJ3QgcmV0cnkgY2xpZW50IGVycm9ycyBvdGhlciB0aGFuIDQyOS80MDhcbiAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKGBOb24tcmV0cnlhYmxlIEhUVFAgZXJyb3IgJHtzdGF0dXN9IGZvciAke29wZXJhdGlvbk5hbWV9LiBBYm9ydGluZy5gLCB7IHVzZXJJZCwgb3BlcmF0aW9uTmFtZSB9KTtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgfVxuICAgICAgfSBlbHNlIGlmICghZXJyb3IucmVzcG9uc2UgJiYgZXJyb3IuY29kZSAmJiAhWydFVElNRURPVVQnLCAnRUNPTk5SRVNFVCcsICdFQUREUklOVVNFJywgJ0VDT05OUkVGVVNFRCcsICdFUElQRScsICdFTkVUVU5SRUFDSCcsICdFQUlfQUdBSU4nXS5pbmNsdWRlcyhlcnJvci5jb2RlKSkge1xuICAgICAgICAvLyBJZiBpdCdzIGEgZ290IGVycm9yIHdpdGhvdXQgYSByZXNwb25zZSwgYnV0IG5vdCBhIGtub3duIHJldHJ5YWJsZSBuZXR3b3JrIGVycm9yIGNvZGUsIGFib3J0LlxuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKGBOb24tcmV0cnlhYmxlIGdvdCBlcnJvciBjb2RlICR7ZXJyb3IuY29kZX0gZm9yICR7b3BlcmF0aW9uTmFtZX0uIEFib3J0aW5nLmAsIHsgdXNlcklkLCBvcGVyYXRpb25OYW1lIH0pO1xuICAgICAgICBicmVhaztcbiAgICAgIH1cbiAgICB9XG4gICAgYXR0ZW1wdCsrO1xuICAgIGlmIChhdHRlbXB0IDwgTUFYX1JFVFJJRVMpIHtcbiAgICAgIGNvbnN0IGRlbGF5ID0gTWF0aC5wb3coMiwgYXR0ZW1wdCAtIDEpICogMTAwMDsgLy8gMXMsIDJzXG4gICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYFdhaXRpbmcgJHtkZWxheX1tcyBiZWZvcmUgUG9zdGdyYXBoaWxlIHJldHJ5ICR7YXR0ZW1wdH0gZm9yICR7b3BlcmF0aW9uTmFtZX1gLCB7IHVzZXJJZCwgb3BlcmF0aW9uTmFtZSB9KTtcbiAgICAgIGF3YWl0IG5ldyBQcm9taXNlKHJlc29sdmUgPT4gc2V0VGltZW91dChyZXNvbHZlLCBkZWxheSkpO1xuICAgIH1cbiAgfVxuICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKGBGYWlsZWQgUG9zdGdyYXBoaWxlIG9wZXJhdGlvbiAnJHtvcGVyYXRpb25OYW1lfScgYWZ0ZXIgJHthdHRlbXB0fSBhdHRlbXB0cy5gLCB7IHVzZXJJZCwgb3BlcmF0aW9uTmFtZSwgbGFzdEVycm9yOiBsYXN0RXJyb3I/Lm1lc3NhZ2UgfSk7XG4gIHRocm93IGxhc3RFcnJvciB8fCBuZXcgRXJyb3IoYEZhaWxlZCBQb3N0Z3JhcGhpbGUgb3BlcmF0aW9uICcke29wZXJhdGlvbk5hbWV9JyBhZnRlciBhbGwgcmV0cmllcy5gKTtcbn07XG5cblxuZXhwb3J0IGNvbnN0IHNlYXJjaFNpbmdsZUV2ZW50QnlWZWN0b3JMYW5jZURiID0gYXN5bmMgKFxuICAgIHVzZXJJZDogc3RyaW5nLFxuICAgIHNlYXJjaFZlY3RvcjogbnVtYmVyW10sXG4pOiBQcm9taXNlPExhbmNlRGJFdmVudFNjaGVtYSB8IG51bGw+ID0+IHtcbiAgICB0cnkge1xuICAgICAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgc2VhcmNoRXZlbnRzKHNlYXJjaFZlY3RvciwgMSwgYHVzZXJJZCA9ICcke3VzZXJJZC5yZXBsYWNlKC8nL2csIFwiJydcIil9J2ApO1xuICAgICAgICBpZiAocmVzdWx0cyAmJiByZXN1bHRzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgIHJldHVybiByZXN1bHRzWzBdO1xuICAgICAgICB9XG4gICAgICAgIHJldHVybiBudWxsO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gc2VhcmNoU2luZ2xlRXZlbnRCeVZlY3RvckxhbmNlRGInLCB7IHVzZXJJZCwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlLCBzdGFjazogKGUgYXMgRXJyb3IpLnN0YWNrIH0pO1xuICAgICAgICB0aHJvdyBlO1xuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IHNlYXJjaFNpbmdsZUV2ZW50QnlWZWN0b3JXaXRoRGF0ZXNMYW5jZURiID0gYXN5bmMgKFxuICAgIHVzZXJJZDogc3RyaW5nLFxuICAgIHFWZWN0b3I6IG51bWJlcltdLFxuICAgIHN0YXJ0RGF0ZTogc3RyaW5nLFxuICAgIGVuZERhdGU6IHN0cmluZyxcbik6IFByb21pc2U8TGFuY2VEYkV2ZW50U2NoZW1hIHwgbnVsbD4gPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIGlmICh0eXBlb2YgcVZlY3RvclswXSAhPT0gJ251bWJlcicpIHtcbiAgICAgICAgICAgIHRocm93IG5ldyBFcnJvcigncVZlY3RvciBpcyBub3QgYSBudW1iZXIgYXJyYXkgb3IgaXMgZW1wdHknKTtcbiAgICAgICAgfVxuICAgICAgICBjb25zdCBmaWx0ZXJDb25kaXRpb24gPSBgdXNlcklkID0gJyR7dXNlcklkLnJlcGxhY2UoLycvZywgXCInJ1wiKX0nIEFORCBzdGFydF9kYXRlID49ICcke3N0YXJ0RGF0ZX0nIEFORCBlbmRfZGF0ZSA8PSAnJHtlbmREYXRlfSdgO1xuICAgICAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgc2VhcmNoRXZlbnRzKHFWZWN0b3IsIDEsIGZpbHRlckNvbmRpdGlvbik7XG4gICAgICAgIGlmIChyZXN1bHRzICYmIHJlc3VsdHMubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgcmV0dXJuIHJlc3VsdHNbMF07XG4gICAgICAgIH1cbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdFcnJvciBpbiBzZWFyY2hTaW5nbGVFdmVudEJ5VmVjdG9yV2l0aERhdGVzTGFuY2VEYicsIHsgdXNlcklkLCBzdGFydERhdGUsIGVuZERhdGUsIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSwgc3RhY2s6IChlIGFzIEVycm9yKS5zdGFjayB9KTtcbiAgICAgICAgdGhyb3cgZTtcbiAgICB9XG59XG5cbmV4cG9ydCBjb25zdCBzZWFyY2hNdWx0aXBsZUV2ZW50c0J5VmVjdG9yV2l0aERhdGVzTGFuY2VEYiA9IGFzeW5jIChcbiAgICB1c2VySWQ6IHN0cmluZyxcbiAgICBxVmVjdG9yOiBudW1iZXJbXSxcbiAgICBzdGFydERhdGU6IHN0cmluZyxcbiAgICBlbmREYXRlOiBzdHJpbmcsXG4gICAgbGltaXQ6IG51bWJlciA9IDEwLFxuKTogUHJvbWlzZTxMYW5jZURiRXZlbnRTY2hlbWFbXT4gPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIGlmICh0eXBlb2YgcVZlY3RvclswXSAhPT0gJ251bWJlcicpIHtcbiAgICAgICAgICAgIHRocm93IG5ldyBFcnJvcigncVZlY3RvciBpcyBub3QgYSBudW1iZXIgYXJyYXkgb3IgaXMgZW1wdHknKTtcbiAgICAgICAgfVxuICAgICAgICBjb25zdCBmaWx0ZXJDb25kaXRpb24gPSBgdXNlcklkID0gJyR7dXNlcklkLnJlcGxhY2UoLycvZywgXCInJ1wiKX0nIEFORCBzdGFydF9kYXRlID49ICcke3N0YXJ0RGF0ZX0nIEFORCBlbmRfZGF0ZSA8PSAnJHtlbmREYXRlfSdgO1xuICAgICAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgc2VhcmNoRXZlbnRzKHFWZWN0b3IsIGxpbWl0LCBmaWx0ZXJDb25kaXRpb24pO1xuICAgICAgICByZXR1cm4gcmVzdWx0cyB8fCBbXTsgLy8gRW5zdXJlIGFuIGFycmF5IGlzIHJldHVybmVkXG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdFcnJvciBpbiBzZWFyY2hNdWx0aXBsZUV2ZW50c0J5VmVjdG9yV2l0aERhdGVzTGFuY2VEYicsIHsgdXNlcklkLCBzdGFydERhdGUsIGVuZERhdGUsIGxpbWl0LCBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UsIHN0YWNrOiAoZSBhcyBFcnJvcikuc3RhY2sgfSk7XG4gICAgICAgIHRocm93IGU7XG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgdXBzZXJ0Q29uZmVyZW5jZSA9IGFzeW5jIChcbiAgICBjb25mZXJlbmNlOiBDb25mZXJlbmNlVHlwZSxcbikgPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnVXBzZXJ0Q29uZmVyZW5jZSdcbiAgICAgICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBtdXRhdGlvbiBVcHNlcnRDb25mZXJlbmNlKCRjb25mZXJlbmNlOiBDb25mZXJlbmNlX2luc2VydF9pbnB1dCEpIHtcbiAgICAgICAgICAgICAgICBpbnNlcnRfQ29uZmVyZW5jZV9vbmUob2JqZWN0OiAkY29uZmVyZW5jZSwgb25fY29uZmxpY3Q6IHtjb25zdHJhaW50OiBDb25mZXJlbmNlX3BrZXksIHVwZGF0ZV9jb2x1bW5zOiBbXG4gICAgICAgICAgICAgICAgICAgIGFwcCxcbiAgICAgICAgICAgICAgICAgICAgZGVsZXRlZCxcbiAgICAgICAgICAgICAgICAgICAgZW50cnlQb2ludHMsXG4gICAgICAgICAgICAgICAgICAgIGhhbmdvdXRMaW5rLFxuICAgICAgICAgICAgICAgICAgICBpY29uVXJpLFxuICAgICAgICAgICAgICAgICAgICBpc0hvc3QsXG4gICAgICAgICAgICAgICAgICAgIGpvaW5VcmwsXG4gICAgICAgICAgICAgICAgICAgIGtleSxcbiAgICAgICAgICAgICAgICAgICAgbmFtZSxcbiAgICAgICAgICAgICAgICAgICAgbm90ZXMsXG4gICAgICAgICAgICAgICAgICAgIHBhcmFtZXRlcnMsXG4gICAgICAgICAgICAgICAgICAgIHJlcXVlc3RJZCxcbiAgICAgICAgICAgICAgICAgICAgc3RhcnRVcmwsXG4gICAgICAgICAgICAgICAgICAgIHN0YXR1cyxcbiAgICAgICAgICAgICAgICAgICAgdHlwZSxcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0LFxuICAgICAgICAgICAgICAgICAgICB6b29tUHJpdmF0ZU1lZXRpbmcsXG4gICAgICAgICAgICAgICAgXX0pIHtcbiAgICAgICAgICAgICAgICAgICAgYXBwXG4gICAgICAgICAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICAgICAgICBlbnRyeVBvaW50c1xuICAgICAgICAgICAgICAgICAgICBoYW5nb3V0TGlua1xuICAgICAgICAgICAgICAgICAgICBpY29uVXJpXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGlzSG9zdFxuICAgICAgICAgICAgICAgICAgICBqb2luVXJsXG4gICAgICAgICAgICAgICAgICAgIGtleVxuICAgICAgICAgICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICAgICAgICAgIHBhcmFtZXRlcnNcbiAgICAgICAgICAgICAgICAgICAgcmVxdWVzdElkXG4gICAgICAgICAgICAgICAgICAgIHN0YXJ0VXJsXG4gICAgICAgICAgICAgICAgICAgIHN0YXR1c1xuICAgICAgICAgICAgICAgICAgICB0eXBlXG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICAgICAgem9vbVByaXZhdGVNZWV0aW5nXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuXG4gICAgICAgIGBcblxuICAgICAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICAgICAgICBjb25mZXJlbmNlXG4gICAgICAgIH1cblxuICAgICAgICAvLyBjb25zdCByZXM6IHsgZGF0YTogeyBpbnNlcnRfQ29uZmVyZW5jZV9vbmU6IENvbmZlcmVuY2VUeXBlIH0gfSA9IGF3YWl0IGdvdC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgIC8vICAgICBoZWFkZXJzOiB7XG4gICAgICAgIC8vICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAvLyAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJ1xuICAgICAgICAvLyAgICAgfSxcbiAgICAgICAgLy8gICAgIGpzb246IHtcbiAgICAgICAgY29uc3QgcmVzcG9uc2VEYXRhID0gYXdhaXQgcmVzaWxpZW50R290UG9zdFBvc3RncmFwaGlsZShvcGVyYXRpb25OYW1lLCBxdWVyeSwgdmFyaWFibGVzKSBhcyB7IGluc2VydF9Db25mZXJlbmNlX29uZTogQ29uZmVyZW5jZVR5cGUgfTtcblxuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oJ1N1Y2Nlc3NmdWxseSB1cHNlcnRlZCBjb25mZXJlbmNlJywgeyBjb25mZXJlbmNlSWQ6IHJlc3BvbnNlRGF0YT8uaW5zZXJ0X0NvbmZlcmVuY2Vfb25lPy5pZCB9KTtcbiAgICAgICAgcmV0dXJuIHJlc3BvbnNlRGF0YT8uaW5zZXJ0X0NvbmZlcmVuY2Vfb25lO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gdXBzZXJ0Q29uZmVyZW5jZScsIHsgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlLCBjb25mZXJlbmNlRGF0YTogY29uZmVyZW5jZSB9KTtcbiAgICAgICAgLy8gUmUtdGhyb3cgb3IgaGFuZGxlIGFzIHBlciBmdW5jdGlvbidzIGNvbnRyYWN0LCBmb3Igbm93LCBsZXQgaXQgcHJvcGFnYXRlIGlmIHJlc2lsaWVudEdvdFBvc3RQb3N0Z3JhcGhpbGUgdGhyb3dzXG4gICAgICAgIHRocm93IGU7XG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgaW5zZXJ0UmVtaW5kZXJzID0gYXN5bmMgKFxuICAgIHJlbWluZGVyczogUmVtaW5kZXJUeXBlW10sXG4pID0+IHtcbiAgICB0cnkge1xuICAgICAgICAvLyB2YWxpZGF0ZVxuICAgICAgICBpZiAoIShyZW1pbmRlcnM/LmZpbHRlcihlID0+ICEhKGU/LmV2ZW50SWQpKT8ubGVuZ3RoID4gMCkpIHtcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG5cbiAgICAgICAgcmVtaW5kZXJzLmZvckVhY2gociA9PiBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKCdSZW1pbmRlciBvYmplY3QgaW5zaWRlIGluc2VydFJlbWluZGVycyBsb29wJywgeyByZW1pbmRlcjogciB9KSk7XG5cbiAgICAgICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdJbnNlcnRSZW1pbmRlcidcbiAgICAgICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBtdXRhdGlvbiBJbnNlcnRSZW1pbmRlcigkcmVtaW5kZXJzOiBbUmVtaW5kZXJfaW5zZXJ0X2lucHV0IV0hKSB7XG4gICAgICAgICAgICAgICAgaW5zZXJ0X1JlbWluZGVyKG9iamVjdHM6ICRyZW1pbmRlcnMpIHtcbiAgICAgICAgICAgICAgICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgICAgICAgICAgICAgICByZXR1cm5pbmcge1xuICAgICAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgICAgICBtZXRob2RcbiAgICAgICAgICAgICAgICAgICAgICAgIG1pbnV0ZXNcbiAgICAgICAgICAgICAgICAgICAgICAgIHJlbWluZGVyRGF0ZVxuICAgICAgICAgICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICAgICAgdXNlRGVmYXVsdFxuICAgICAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGBcbiAgICAgICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgICAgICAgcmVtaW5kZXJzXG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCByZXNwb25zZURhdGEgPSBhd2FpdCByZXNpbGllbnRHb3RQb3N0UG9zdGdyYXBoaWxlKG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB2YXJpYWJsZXMpIGFzIHsgaW5zZXJ0X1JlbWluZGVyOiB7IHJldHVybmluZzogUmVtaW5kZXJUeXBlW10gfSB9O1xuXG4gICAgICAgIGlmIChyZXNwb25zZURhdGE/Lmluc2VydF9SZW1pbmRlcj8ucmV0dXJuaW5nKSB7XG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oJ1N1Y2Nlc3NmdWxseSBpbnNlcnRlZCByZW1pbmRlcnMuJywgeyBjb3VudDogcmVzcG9uc2VEYXRhLmluc2VydF9SZW1pbmRlci5yZXR1cm5pbmcubGVuZ3RoIH0pO1xuICAgICAgICAgICAgLy8gcmVzcG9uc2VEYXRhLmluc2VydF9SZW1pbmRlci5yZXR1cm5pbmcuZm9yRWFjaChyID0+IGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoJ0luc2VydGVkIHJlbWluZGVyIGRldGFpbHM6JywgeyByZW1pbmRlcjogciB9KSk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLndhcm4oJ0luc2VydFJlbWluZGVycyBjYWxsIHRvIFBvc3RncmFwaGlsZSBkaWQgbm90IHJldHVybiBleHBlY3RlZCBkYXRhIHN0cnVjdHVyZS4nLCB7IHJlc3BvbnNlRGF0YSB9KTtcbiAgICAgICAgfVxuICAgICAgICAvLyBUaGUgZnVuY3Rpb24gZG9lc24ndCByZXR1cm4gYW55dGhpbmcgaW4gaXRzIG9yaWdpbmFsIGZvcm0sIHNvIHdlIG1haW50YWluIHRoYXQuXG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdFcnJvciBpbiBpbnNlcnRSZW1pbmRlcnMnLCB7IGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSwgcmVtaW5kZXJzRGF0YTogcmVtaW5kZXJzIH0pO1xuICAgICAgICAvLyBSZS10aHJvdyBvciBoYW5kbGUgYXMgcGVyIGZ1bmN0aW9uJ3MgY29udHJhY3RcbiAgICAgICAgdGhyb3cgZTtcbiAgICB9XG59XG5cbmV4cG9ydCBjb25zdCB1cHNlcnRFdmVudHMgPSBhc3luYyAoXG4gICAgZXZlbnRzOiBFdmVudFR5cGVbXVxuKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgaWYgKCEoZXZlbnRzPy5sZW5ndGggPiAwKSkge1xuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKCdObyBldmVudHMgZm91bmQgaW4gdXBzZXJ0RXZlbnRzLCByZXR1cm5pbmcgZWFybHkuJywgeyBldmVudENvdW50OiBldmVudHM/Lmxlbmd0aCB9KTtcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG4gICAgICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnSW5zZXJ0RXZlbnQnXG4gICAgICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgbXV0YXRpb24gSW5zZXJ0RXZlbnQoJGV2ZW50czogW0V2ZW50X2luc2VydF9pbnB1dCFdISkge1xuICAgICAgICAgICAgICAgIGluc2VydF9FdmVudChcbiAgICAgICAgICAgICAgICAgICAgb2JqZWN0czogJGV2ZW50cyxcbiAgICAgICAgICAgICAgICAgICAgb25fY29uZmxpY3Q6IHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvbnN0cmFpbnQ6IEV2ZW50X3BrZXksXG4gICAgICAgICAgICAgICAgICAgICAgICB1cGRhdGVfY29sdW1uczogW1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB0aXRsZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzdGFydERhdGUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZW5kRGF0ZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBhbGxEYXksXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcmVjdXJyZW5jZVJ1bGUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgbG9jYXRpb24sXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgbm90ZXMsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgYXR0YWNobWVudHMsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgbGlua3MsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZGVsZXRlZCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB0YXNrSWQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdGFza1R5cGUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcHJpb3JpdHksXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZm9sbG93VXBFdmVudElkLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlzRm9sbG93VXAsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaXNQcmVFdmVudCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBpc1Bvc3RFdmVudCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBwcmVFdmVudElkLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHBvc3RFdmVudElkLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1vZGlmaWFibGUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZm9yRXZlbnRJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb25mZXJlbmNlSWQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgbWF4QXR0ZW5kZWVzLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNlbmRVcGRhdGVzLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGFueW9uZUNhbkFkZFNlbGYsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIG9yaWdpbmFsU3RhcnREYXRlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIG9yaWdpbmFsQWxsRGF5LFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHN0YXR1cyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzdW1tYXJ5LFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHRyYW5zcGFyZW5jeSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB2aXNpYmlsaXR5LFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJlY3VycmluZ0V2ZW50SWQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0LFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlDYWxVSUQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaHRtbExpbmssXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29sb3JJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjcmVhdG9yLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIG9yZ2FuaXplcixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBlbmRUaW1lVW5zcGVjaWZpZWQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcmVjdXJyZW5jZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFRpbWV6b25lLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlc09taXR0ZWQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZXh0ZW5kZWRQcm9wZXJ0aWVzLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGhhbmdvdXRMaW5rLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbk1vZGlmeSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBsb2NrZWQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc291cmNlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGV2ZW50VHlwZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBwcml2YXRlQ29weSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjYWxlbmRhcklkLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGJhY2tncm91bmRDb2xvcixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBmb3JlZ3JvdW5kQ29sb3IsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlRGVmYXVsdEFsYXJtcyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBwb3NpdGl2ZUltcGFjdFNjb3JlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWssXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RUaW1lLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWREYXlPZldlZWssXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkVGltZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBpc01lZXRpbmcsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZGFpbHlUYXNrTGlzdCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB3ZWVrbHlUYXNrTGlzdCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBpc0JyZWFrLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb3B5QXZhaWxhYmlsaXR5LFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlUaW1lQmxvY2tpbmcsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weVRpbWVQcmVmZXJlbmNlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlSZW1pbmRlcnMsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weVByaW9yaXR5TGV2ZWwsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weU1vZGlmaWFibGUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weUNhdGVnb3JpZXMsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weUlzQnJlYWssXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdGltZUJsb2NraW5nLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmcsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2UsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWwsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkQ2F0ZWdvcmllcyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzQnJlYWssXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaGFyZERlYWRsaW5lLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNvZnREZWFkbGluZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb3B5SXNNZWV0aW5nLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRJc01lZXRpbmcsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNFeHRlcm5hbE1lZXRpbmcsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZHVyYXRpb24sXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weUR1cmF0aW9uLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZER1cmF0aW9uLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVubGluayxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb3B5Q29sb3IsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkQ29sb3IsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgYnlXZWVrRGF5LFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGxvY2FsU3luY2VkLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1lZXRpbmdJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBldmVudElkLFxuICAgICAgICAgICAgICAgICAgICAgICAgXVxuICAgICAgICAgICAgICAgICAgICB9KXtcbiAgICAgICAgICAgICAgICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYFxuICAgICAgICAvLyBfLnVuaXFCeShldmVudHMsICdpZCcpLmZvckVhY2goZSA9PiBjb25zb2xlLmxvZyhlPy5pZCwgZSwgJ2lkLCBlIGluc2lkZSB1cHNlcnRFdmVudHNQb3N0UGxhbm5lciAnKSkgLy8gT3JpZ2luYWwgdmVyYm9zZSBsb2dcbiAgICAgICAgXy51bmlxQnkoZXZlbnRzLCAnaWQnKS5mb3JFYWNoKGUgPT4gY2hhdEFwaUhlbHBlckxvZ2dlci5kZWJ1ZygnRXZlbnQgb2JqZWN0IGluc2lkZSB1cHNlcnRFdmVudHNQb3N0UGxhbm5lciBsb29wIChhZnRlciB1bmlxQnkpJywgeyBldmVudElkOiBlPy5pZCwgZXZlbnRTdW1tYXJ5OiBlPy5zdW1tYXJ5IH0pKTtcbiAgICAgICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgICAgICAgZXZlbnRzOiBfLnVuaXFCeShldmVudHMsICdpZCcpLFxuICAgICAgICB9XG5cbiAgICAgICAgLy8gY29uc3QgcmVzcG9uc2U6IHsgZGF0YTogeyBpbnNlcnRfRXZlbnQ6IHsgYWZmZWN0ZWRfcm93czogbnVtYmVyLCByZXR1cm5pbmc6IHsgaWQ6IHN0cmluZyB9W10gfSB9IH0gPSBhd2FpdCBnb3QucG9zdChwb3N0Z3JhcGhpbGVHcmFwaFVybCwge1xuICAgICAgICAvLyAgICAgaGVhZGVyczoge1xuICAgICAgICAvLyAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgLy8gICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbidcbiAgICAgICAgLy8gICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIC8vICAgICB9XG4gICAgICAgIGNvbnN0IHJlc3BvbnNlRGF0YSA9IGF3YWl0IHJlc2lsaWVudEdvdFBvc3RQb3N0Z3JhcGhpbGUob3BlcmF0aW9uTmFtZSwgcXVlcnksIHZhcmlhYmxlcykgYXMgeyBpbnNlcnRfRXZlbnQ6IHsgYWZmZWN0ZWRfcm93czogbnVtYmVyLCByZXR1cm5pbmc6IHsgaWQ6IHN0cmluZyB9W10gfSB9O1xuXG4gICAgICAgIGlmIChyZXNwb25zZURhdGE/Lmluc2VydF9FdmVudCkge1xuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKCdTdWNjZXNzZnVsbHkgdXBzZXJ0ZWQgZXZlbnRzLicsIHsgYWZmZWN0ZWRfcm93czogcmVzcG9uc2VEYXRhLmluc2VydF9FdmVudC5hZmZlY3RlZF9yb3dzLCByZXR1cm5lZF9pZHM6IHJlc3BvbnNlRGF0YS5pbnNlcnRfRXZlbnQucmV0dXJuaW5nPy5tYXAociA9PiByLmlkKSB9KTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIud2FybignVXBzZXJ0RXZlbnRzIGNhbGwgdG8gUG9zdGdyYXBoaWxlIGRpZCBub3QgcmV0dXJuIGV4cGVjdGVkIGRhdGEgc3RydWN0dXJlLicsIHsgcmVzcG9uc2VEYXRhIH0pO1xuICAgICAgICB9XG4gICAgICAgIC8vIE9yaWdpbmFsIGZ1bmN0aW9uIHJldHVybmVkIHRoZSB3aG9sZSByZXNwb25zZSBvYmplY3QsIHNvIHdlIG1pbWljIHRoYXQgc3RydWN0dXJlIGlmIG5lZWRlZCwgb3IganVzdCB0aGUgZGF0YSBwYXJ0LlxuICAgICAgICAvLyBGb3Igbm93LCBsZXQncyByZXR1cm4gdGhlICdkYXRhJyBwYXJ0LCBhc3N1bWluZyBjb25zdW1lcnMgZXhwZWN0IHRoYXQuXG4gICAgICAgIC8vIElmIHRoZSBmdWxsIEF4aW9zLWxpa2UgcmVzcG9uc2Ugd2FzIGV4cGVjdGVkLCB0aGlzIHdvdWxkIG5lZWQgYWRqdXN0bWVudC5cbiAgICAgICAgLy8gR2l2ZW4gdGhlIHR5cGUgYW5ub3RhdGlvbiBvZiB0aGUgb3JpZ2luYWwgYHJlc3BvbnNlYCB2YXJpYWJsZSwgaXQgc2VlbXMgaXQgZXhwZWN0ZWQgdGhlIGBkYXRhYCBwcm9wZXJ0eS5cbiAgICAgICAgcmV0dXJuIHsgZGF0YTogcmVzcG9uc2VEYXRhIH07XG5cbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoJ0Vycm9yIGluIHVwc2VydEV2ZW50cycsIHsgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlLCBldmVudENvdW50OiBldmVudHMubGVuZ3RoIH0pO1xuICAgICAgICB0aHJvdyBlO1xuICAgIH1cbn1cblxuLy8gTm90ZTogbGlzdEFsbEV2ZW50V2l0aEV2ZW50T3BlblNlYXJjaCBpcyBjb25zb2xpZGF0ZWQgaW50byBzZWFyY2hNdWx0aXBsZUV2ZW50c0J5VmVjdG9yV2l0aERhdGVzTGFuY2VEYlxuXG5leHBvcnQgY29uc3QgcHV0RGF0YUluVHJhaW5FdmVudEluZGV4SW5PcGVuU2VhcmNoID0gYXN5bmMgKFxuICAgIGlkOiBzdHJpbmcsXG4gICAgdmVjdG9yOiBudW1iZXJbXSxcbiAgICB1c2VySWQ6IHN0cmluZyxcbikgPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IGNsaWVudCA9IGF3YWl0IGdldFNlYXJjaENsaWVudCgpXG4gICAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgY2xpZW50LmluZGV4KHtcbiAgICAgICAgICAgIGlkLFxuICAgICAgICAgICAgaW5kZXg6IG9wZW5UcmFpbkV2ZW50SW5kZXgsXG4gICAgICAgICAgICBib2R5OiB7IFtvcGVuVHJhaW5FdmVudFZlY3Rvck5hbWVdOiB2ZWN0b3IsIHVzZXJJZCB9LFxuICAgICAgICAgICAgcmVmcmVzaDogdHJ1ZVxuICAgICAgICB9KVxuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oJ0RvY3VtZW50IGFkZGVkIHRvIE9wZW5TZWFyY2ggdHJhaW4gZXZlbnQgaW5kZXguJywgeyBkb2N1bWVudElkOiBpZCwgcmVzcG9uc2VCb2R5OiByZXNwb25zZS5ib2R5IH0pO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignVW5hYmxlIHRvIHB1dCBkYXRhIGludG8gT3BlblNlYXJjaCB0cmFpbiBldmVudCBpbmRleCcsIHsgaWQsIHVzZXJJZCwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlLCBzdGFjazogKGUgYXMgRXJyb3IpLnN0YWNrIH0pO1xuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IGdldEV2ZW50VmVjdG9yRnJvbUxhbmNlRGIgPSBhc3luYyAoaWQ6IHN0cmluZyk6IFByb21pc2U8bnVtYmVyW10gfCBudWxsPiA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgY29uc3QgZXZlbnQgPSBhd2FpdCBnZXRFdmVudEZyb21MYW5jZURiQnlJZChpZCk7XG4gICAgICAgIHJldHVybiBldmVudD8udmVjdG9yIHx8IG51bGw7XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKGBFcnJvciBmZXRjaGluZyBldmVudCB2ZWN0b3IgZm9yIElEICR7aWR9IGZyb20gTGFuY2VEQmAsIHsgZXZlbnRJZDogaWQsIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSwgc3RhY2s6IChlIGFzIEVycm9yKS5zdGFjayB9KTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgdXBzZXJ0RXZlbnRUb0xhbmNlRGIgPSBhc3luYyAoXG4gICAgaWQ6IHN0cmluZyxcbiAgICB2ZWN0b3I6IG51bWJlcltdLFxuICAgIHVzZXJJZDogc3RyaW5nLFxuICAgIHN0YXJ0X2RhdGU6IHN0cmluZyxcbiAgICBlbmRfZGF0ZTogc3RyaW5nLFxuICAgIHRpdGxlOiBzdHJpbmcsIC8vIEFzc3VtaW5nIHRpdGxlIGlzIGEgZ29vZCBjYW5kaWRhdGUgZm9yIHJhd19ldmVudF90ZXh0IGZvciBub3dcbiAgICAvLyBDb25zaWRlciBwYXNzaW5nIHRoZSBhY3R1YWwgdGV4dCB1c2VkIGZvciB2ZWN0b3IgZ2VuZXJhdGlvbiBpZiBkaWZmZXJlbnRcbikgPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IGV2ZW50RW50cnk6IExhbmNlRGJFdmVudFNjaGVtYSA9IHtcbiAgICAgICAgICAgIGlkLFxuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgdmVjdG9yLFxuICAgICAgICAgICAgc3RhcnRfZGF0ZSxcbiAgICAgICAgICAgIGVuZF9kYXRlLFxuICAgICAgICAgICAgcmF3X2V2ZW50X3RleHQ6IHRpdGxlLCAvLyBPciBhIG1vcmUgY29tcHJlaGVuc2l2ZSB0ZXh0IHNvdXJjZVxuICAgICAgICAgICAgdGl0bGU6IHRpdGxlLFxuICAgICAgICAgICAgbGFzdF9tb2RpZmllZDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICB9O1xuICAgICAgICBhd2FpdCB1cHNlcnRFdmVudHMoW2V2ZW50RW50cnldKTsgLy8gVGhpcyBpbnRlcm5hbCBjYWxsIHRvIHVwc2VydEV2ZW50cyBhbHJlYWR5IGhhcyBsb2dnaW5nXG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbyhgRXZlbnQgJHtpZH0gdXBzZXJ0ZWQgdG8gTGFuY2VEQi5gLCB7IGV2ZW50SWQ6IGlkLCB1c2VySWQgfSk7XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKGBFcnJvciB1cHNlcnRpbmcgZXZlbnQgJHtpZH0gdG8gTGFuY2VEQmAsIHsgZXZlbnRJZDogaWQsIHVzZXJJZCwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlLCBzdGFjazogKGUgYXMgRXJyb3IpLnN0YWNrIH0pO1xuICAgICAgICB0aHJvdyBlO1xuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IGRlbGV0ZUV2ZW50RnJvbUxhbmNlRGIgPSBhc3luYyAoaWQ6IHN0cmluZyk6IFByb21pc2U8dm9pZD4gPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIGF3YWl0IGRlbGV0ZUV2ZW50c0J5SWRzKFtpZF0pO1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYEV2ZW50ICR7aWR9IGRlbGV0ZWQgZnJvbSBMYW5jZURCLmAsIHsgZXZlbnRJZDogaWQgfSk7XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKGBFcnJvciBkZWxldGluZyBldmVudCAke2lkfSBmcm9tIExhbmNlREJgLCB7IGV2ZW50SWQ6IGlkLCBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UsIHN0YWNrOiAoZSBhcyBFcnJvcikuc3RhY2sgfSk7XG4gICAgICAgIHRocm93IGU7XG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgZGVsZXRlVHJhaW5pbmdEYXRhRnJvbUxhbmNlRGIgPSBhc3luYyAoaWQ6IHN0cmluZyk6IFByb21pc2U8dm9pZD4gPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIGF3YWl0IGRlbGV0ZVRyYWluaW5nRXZlbnRzQnlJZHMoW2lkXSk7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbyhgVHJhaW5pbmcgZGF0YSBmb3IgSUQgJHtpZH0gZGVsZXRlZCBmcm9tIExhbmNlREIuYCwgeyB0cmFpbmluZ0RhdGFJZDogaWQgfSk7XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKGBFcnJvciBkZWxldGluZyB0cmFpbmluZyBkYXRhIGZvciBJRCAke2lkfSBmcm9tIExhbmNlREJgLCB7IHRyYWluaW5nRGF0YUlkOiBpZCwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlLCBzdGFjazogKGUgYXMgRXJyb3IpLnN0YWNrIH0pO1xuICAgICAgICB0aHJvdyBlO1xuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IHVwZGF0ZVRyYWluaW5nRGF0YUluTGFuY2VEYiA9IGFzeW5jIChcbiAgICBpZDogc3RyaW5nLFxuICAgIHZlY3RvcjogbnVtYmVyW10sXG4gICAgdXNlcklkOiBzdHJpbmcsXG4gICAgc291cmNlX2V2ZW50X3RleHQ6IHN0cmluZywgLy8gUmVxdWlyZWQgZm9yIG5ldyB1cHNlcnQgbG9naWNcbikgPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IHRyYWluaW5nRW50cnk6IExhbmNlRGJUcmFpbmluZ0V2ZW50U2NoZW1hID0ge1xuICAgICAgICAgICAgaWQsXG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICB2ZWN0b3IsXG4gICAgICAgICAgICBzb3VyY2VfZXZlbnRfdGV4dCxcbiAgICAgICAgICAgIGNyZWF0ZWRfYXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICAgIH07XG5cbiAgICAgICAgICAgIC8vIE1hcCB0byBwcm9wZXIgVHJhaW5pbmdFdmVudFNjaGVtYVxuICAgICAgICAgICAgY29uc3QgdHJhaW5pbmdFdmVudDogTGFuY2VEYlRyYWluaW5nRXZlbnRTY2hlbWEgPSB7XG4gICAgICAgICAgICAgICAgaWQ6IHRyYWluaW5nRW50cnkuaWQsXG4gICAgICAgICAgICAgICAgdXNlcklkOiB0cmFpbmluZ0VudHJ5LnVzZXJJZCB8fCAnJyxcbiAgICAgICAgICAgICAgICB2ZWN0b3I6IHRyYWluaW5nRW50cnkudmVjdG9yIHx8IFtdLFxuICAgICAgICAgICAgICAgIHN0YXJ0X2RhdGU6IHRyYWluaW5nRW50cnkuc3RhcnRfZGF0ZSB8fCB0cmFpbmluZ0VudHJ5LnN0YXJ0RGF0ZSB8fCBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICAgICAgZW5kX2RhdGU6IHRyYWluaW5nRW50cnkuZW5kX2RhdGUgfHwgdHJhaW5pbmdFbnRyeS5lbmREYXRlIHx8IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICAgICAgICBzb3VyY2VfZXZlbnRfdGV4dDogdHJhaW5pbmdFbnRyeS5ldmVudF90ZXh0IHx8IHRyYWluaW5nRW50cnkudGl0bGUgfHwgJycsXG4gICAgICAgICAgICAgICAgY3JlYXRlZF9hdDogdHJhaW5pbmdFbnRyeS5jcmVhdGVkX2F0IHx8IGRheWpzKCkudG9JU09TdHJpbmcoKVxuICAgICAgICAgICAgfTtcbiAgICAgICAgYXdhaXQgbGFuY2VkYlVwc2VydFRyYWluaW5nRXZlbnRzKFt0cmFpbmluZ0V2ZW50XSk7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbyhgVHJhaW5pbmcgZGF0YSBmb3IgSUQgJHtpZH0gdXBkYXRlZC91cHNlcnRlZCBpbiBMYW5jZURCLmAsIHsgdHJhaW5pbmdEYXRhSWQ6IGlkLCB1c2VySWQgfSk7XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKGBFcnJvciB1cGRhdGluZyB0cmFpbmluZyBkYXRhIGZvciBJRCAke2lkfSBpbiBMYW5jZURCYCwgeyB0cmFpbmluZ0RhdGFJZDogaWQsIHVzZXJJZCwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlLCBzdGFjazogKGUgYXMgRXJyb3IpLnN0YWNrIH0pO1xuICAgICAgICB0aHJvdyBlO1xuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IHNlYXJjaFRyYWluaW5nRGF0YUZyb21MYW5jZURiID0gYXN5bmMgKFxuICAgIHVzZXJJZDogc3RyaW5nLFxuICAgIHNlYXJjaFZlY3RvcjogbnVtYmVyW10sXG4pOiBQcm9taXNlPExhbmNlRGJUcmFpbmluZ0V2ZW50U2NoZW1hIHwgbnVsbD4gPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IHJlc3VsdHMgPSBhd2FpdCBzZWFyY2hUcmFpbmluZ0V2ZW50cyhzZWFyY2hWZWN0b3IsIDEsIGB1c2VySWQgPSAnJHt1c2VySWQucmVwbGFjZSgvJy9nLCBcIicnXCIpfSdgKTtcbiAgICAgICAgaWYgKHJlc3VsdHMgJiYgcmVzdWx0cy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgICByZXR1cm4gcmVzdWx0c1swXTtcbiAgICAgICAgfVxuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoJ0Vycm9yIHNlYXJjaGluZyB0cmFpbmluZyBkYXRhIGluIExhbmNlREInLCB7IHVzZXJJZCwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlLCBzdGFjazogKGUgYXMgRXJyb3IpLnN0YWNrIH0pO1xuICAgICAgICB0aHJvdyBlO1xuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IgPSBhc3luYyAoXG4gICAgdGl0bGU6IHN0cmluZyxcbikgPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IGVtYmVkZGluZ1JlcXVlc3QgPSB7XG4gICAgICAgICAgICBtb2RlbDogJ3RleHQtZW1iZWRkaW5nLTMtc21hbGwnLFxuICAgICAgICAgICAgaW5wdXQ6IHRpdGxlLFxuICAgICAgICB9IGFzIGFueVxuXG4gICAgICAgIC8vIGNvbnN0IHJlcyA9IGF3YWl0IG9wZW5haS5lbWJlZGRpbmdzLmNyZWF0ZShlbWJlZGRpbmdSZXF1ZXN0KVxuICAgICAgICAvLyBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGluc2lkZSBjb252ZXJ0RXZlbnRUaXRsZVRvT3BlbkFJVmVjdG9ycycpXG4gICAgICAgIC8vIHJldHVybiByZXM/LmRhdGE/LlswXT8uZW1iZWRkaW5nXG4gICAgICAgIHJldHVybiBhd2FpdCByZXRyeShhc3luYyAoYmFpbCwgYXR0ZW1wdE51bWJlcikgPT4ge1xuICAgICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYEF0dGVtcHQgJHthdHRlbXB0TnVtYmVyfSB0byBnZXQgZW1iZWRkaW5nIGZvciB0aXRsZTogXCIke3RpdGxlLnN1YnN0cmluZygwLCAyMCl9Li4uXCJgKTtcbiAgICAgICAgICAgICAgICBjb25zdCByZXMgPSBhd2FpdCBvcGVuYWkuZW1iZWRkaW5ncy5jcmVhdGUoZW1iZWRkaW5nUmVxdWVzdCwgeyB0aW1lb3V0OiAxNTAwMCB9KTsgLy8gMTVzIHRpbWVvdXRcbiAgICAgICAgICAgICAgICBpZiAoIXJlcz8uZGF0YT8uWzBdPy5lbWJlZGRpbmcpIHtcbiAgICAgICAgICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci53YXJuKGBPcGVuQUkgZW1iZWRkaW5nIGNhbGwgZm9yIHRpdGxlIFwiJHt0aXRsZS5zdWJzdHJpbmcoMCwyMCl9Li4uXCIgcmV0dXJuZWQgbm8gZW1iZWRkaW5nIGRhdGEgb24gYXR0ZW1wdCAke2F0dGVtcHROdW1iZXJ9LmAsIHsgcmVzcG9uc2U6IHJlcyB9KTtcbiAgICAgICAgICAgICAgICAgICAgdGhyb3cgbmV3IEVycm9yKFwiTm8gZW1iZWRkaW5nIGRhdGEgcmV0dXJuZWQgZnJvbSBPcGVuQUkuXCIpO1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYFN1Y2Nlc3NmdWxseSBnb3QgZW1iZWRkaW5nIGZvciB0aXRsZSBcIiR7dGl0bGUuc3Vic3RyaW5nKDAsMjApfS4uLlwiIG9uIGF0dGVtcHQgJHthdHRlbXB0TnVtYmVyfS5gKTtcbiAgICAgICAgICAgICAgICByZXR1cm4gcmVzLmRhdGFbMF0uZW1iZWRkaW5nO1xuICAgICAgICAgICAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgICAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIud2FybihgQXR0ZW1wdCAke2F0dGVtcHROdW1iZXJ9IGZvciBPcGVuQUkgZW1iZWRkaW5nIGZvciB0aXRsZSBcIiR7dGl0bGUuc3Vic3RyaW5nKDAsMjApfS4uLlwiIGZhaWxlZC5gLCB7XG4gICAgICAgICAgICAgICAgICAgIGVycm9yOiBlcnJvci5tZXNzYWdlLCBjb2RlOiBlcnJvci5jb2RlLCBzdGF0dXM6IGVycm9yLnJlc3BvbnNlPy5zdGF0dXNcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgICBpZiAoZXJyb3IucmVzcG9uc2UgJiYgWzQwMCwgNDAxLCA0MDMsIDQwNF0uaW5jbHVkZXMoZXJyb3IucmVzcG9uc2Uuc3RhdHVzKSkge1xuICAgICAgICAgICAgICAgICAgICBiYWlsKGVycm9yKTsgLy8gTm9uLXJldHJ5YWJsZSBjbGllbnQgZXJyb3JzXG4gICAgICAgICAgICAgICAgICAgIHJldHVybjtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgdGhyb3cgZXJyb3I7IC8vIFJldHJ5IGZvciBvdGhlciBlcnJvcnMgKDV4eCwgbmV0d29yaywgdGltZW91dClcbiAgICAgICAgICAgIH1cbiAgICAgICAgfSwge1xuICAgICAgICAgICAgcmV0cmllczogMiwgLy8gVG90YWwgMyBhdHRlbXB0c1xuICAgICAgICAgICAgZmFjdG9yOiAyLFxuICAgICAgICAgICAgbWluVGltZW91dDogNTAwLFxuICAgICAgICAgICAgbWF4VGltZW91dDogNDAwMCxcbiAgICAgICAgICAgIG9uUmV0cnk6IChlcnJvciwgYXR0ZW1wdE51bWJlcikgPT4ge1xuICAgICAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIud2FybihgUmV0cnlpbmcgT3BlbkFJIGVtYmVkZGluZyBmb3IgdGl0bGUgXCIke3RpdGxlLnN1YnN0cmluZygwLDIwKX0uLi5cIiwgYXR0ZW1wdCAke2F0dGVtcHROdW1iZXJ9LiBFcnJvcjogJHtlcnJvci5tZXNzYWdlfWApO1xuICAgICAgICAgICAgfVxuICAgICAgICB9KTtcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoJ0ZhaWxlZCB0byBjb252ZXJ0IGV2ZW50IHRpdGxlIHRvIE9wZW5BSSB2ZWN0b3IgYWZ0ZXIgYWxsIHJldHJpZXMuJywgeyB0aXRsZTogdGl0bGUuc3Vic3RyaW5nKDAsMjApLCBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UgfSk7XG4gICAgICAgIHRocm93IGU7IC8vIFJlLXRocm93IHRoZSBmaW5hbCBlcnJvclxuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IGV2ZW50U2VhcmNoQm91bmRhcnkgPSAoXG4gICAgdGltZXpvbmU6IHN0cmluZyxcbiAgICBkYXRlSlNPTkJvZHk6IERhdGVUaW1lSlNPTlR5cGUsXG4gICAgY3VycmVudFRpbWU6IHN0cmluZyxcbikgPT4ge1xuICAgIGxldCBzdGFydERhdGUgPSAnJ1xuICAgIGxldCBlbmREYXRlID0gJydcbiAgICBsZXQgZGF0ZUEgPSAnJ1xuICAgIGxldCBkYXRlQiA9ICcnXG5cbiAgICAvLyBzZXQgZGF0ZUFcbiAgICBpZiAoZGF0ZUpTT05Cb2R5Py5vbGREYXRlPy5kYXkpIHtcblxuICAgICAgICBkYXRlQSA9IGAke2RhdGVKU09OQm9keT8ub2xkRGF0ZT8ueWVhciB8fCBkYXlqcygpLmZvcm1hdCgnWVlZWScpfS0ke2RhdGVKU09OQm9keT8ub2xkRGF0ZT8ubW9udGggfHwgZGF5anMoKS5mb3JtYXQoJ01NJyl9LSR7ZGF0ZUpTT05Cb2R5Py5vbGREYXRlPy5kYXkgfHwgZGF5anMoKS50eih0aW1lem9uZSkuZm9ybWF0KCdERCcpfWBcblxuICAgIH0gZWxzZSBpZiAoZGF0ZUpTT05Cb2R5Py5vbGREYXRlPy5pc29XZWVrZGF5KSB7XG4gICAgICAgIGNvbnN0IGN1cnJlbnRJU09EYXkgPSBnZXRJU09EYXkoZGF5anMoKS50eih0aW1lem9uZSkudG9EYXRlKCkpXG5cbiAgICAgICAgY29uc3QgZ2l2ZW5JU09EYXkgPSBkYXRlSlNPTkJvZHk/Lm9sZERhdGU/Lmlzb1dlZWtkYXlcblxuICAgICAgICAvLyBhZGQgYSB3ZWVrIGlmIGdpdmVuSVNPRGF5IDwgY3VycmVudElTT0RheVxuXG4gICAgICAgIGlmIChnaXZlbklTT0RheSA8IGN1cnJlbnRJU09EYXkpIHtcbiAgICAgICAgICAgIGNvbnN0IHBhcnNlZFBhcnRpYWxFbmREYXRlID0gZGF5anMoYCR7ZGF0ZUpTT05Cb2R5Py5vbGREYXRlPy55ZWFyIHx8IGRheWpzKCkuZm9ybWF0KCdZWVlZJyl9LSR7ZGF0ZUpTT05Cb2R5Py5vbGREYXRlPy5tb250aCB8fCBkYXlqcygpLmZvcm1hdCgnTU0nKX0tJHtkYXRlSlNPTkJvZHk/Lm9sZERhdGU/LmRheSB8fCBkYXlqcygpLnR6KHRpbWV6b25lKS5mb3JtYXQoJ0REJyl9YCwgJ1lZWVktTU0tREQnKVxuICAgICAgICAgICAgZGF0ZUEgPSBkYXlqcyhzZXRJU09EYXkoZGF5anMocGFyc2VkUGFydGlhbEVuZERhdGUsICdZWVlZLU1NLUREJykudHoodGltZXpvbmUsIHRydWUpLmFkZCgxLCAndycpLnRvRGF0ZSgpLCBnaXZlbklTT0RheSkpLmZvcm1hdCgnWVlZWS1NTS1ERCcpXG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBjb25zdCBwYXJzZWRQYXJ0aWFsRW5kRGF0ZSA9IGRheWpzKGAke2RhdGVKU09OQm9keT8ub2xkRGF0ZT8ueWVhciB8fCBkYXlqcygpLmZvcm1hdCgnWVlZWScpfS0ke2RhdGVKU09OQm9keT8ub2xkRGF0ZT8ubW9udGggfHwgZGF5anMoKS5mb3JtYXQoJ01NJyl9LSR7ZGF0ZUpTT05Cb2R5Py5vbGREYXRlPy5kYXkgfHwgZGF5anMoKS50eih0aW1lem9uZSkuZm9ybWF0KCdERCcpfWAsICdZWVlZLU1NLUREJylcbiAgICAgICAgICAgIGRhdGVBID0gZGF5anMoc2V0SVNPRGF5KGRheWpzKHBhcnNlZFBhcnRpYWxFbmREYXRlLCAnWVlZWS1NTS1ERCcpLnR6KHRpbWV6b25lLCB0cnVlKS50b0RhdGUoKSwgZ2l2ZW5JU09EYXkpKS5mb3JtYXQoJ1lZWVktTU0tREQnKVxuICAgICAgICB9XG4gICAgfSBlbHNlIGlmIChkYXRlSlNPTkJvZHk/Lm9sZERhdGU/LnJlbGF0aXZlVGltZUZyb21Ob3c/LlswXSkge1xuICAgICAgICBpZiAoZGF0ZUpTT05Cb2R5Py5vbGREYXRlPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93ID09PSAnYWRkJykge1xuICAgICAgICAgICAgLy8gbG9vcCB0aHJvdWdoIGFsbCBwb3NzaWJsZSB2YWx1ZXNcbiAgICAgICAgICAgIGxldCBkYXkgPSAwXG4gICAgICAgICAgICBsZXQgd2VlayA9IDBcbiAgICAgICAgICAgIGxldCBtb250aCA9IDBcbiAgICAgICAgICAgIGxldCB5ZWFyID0gMFxuXG4gICAgICAgICAgICBmb3IgKGNvbnN0IHJlbGF0aXZlVGltZU9iamVjdCBvZiBkYXRlSlNPTkJvZHk/Lm9sZERhdGU/LnJlbGF0aXZlVGltZUZyb21Ob3cpIHtcblxuICAgICAgICAgICAgICAgIGlmIChyZWxhdGl2ZVRpbWVPYmplY3Q/LnVuaXQgPT09ICdkYXknKSB7XG4gICAgICAgICAgICAgICAgICAgIGlmIChyZWxhdGl2ZVRpbWVPYmplY3Q/LnZhbHVlID4gMCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgZGF5ICs9IHJlbGF0aXZlVGltZU9iamVjdD8udmFsdWVcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAocmVsYXRpdmVUaW1lT2JqZWN0Py51bml0ID09PSAnd2VlaycpIHtcbiAgICAgICAgICAgICAgICAgICAgaWYgKHJlbGF0aXZlVGltZU9iamVjdD8udmFsdWUgPiAwKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICB3ZWVrICs9IHJlbGF0aXZlVGltZU9iamVjdD8udmFsdWVcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAocmVsYXRpdmVUaW1lT2JqZWN0Py51bml0ID09PSAnbW9udGgnKSB7XG4gICAgICAgICAgICAgICAgICAgIGlmIChyZWxhdGl2ZVRpbWVPYmplY3Q/LnZhbHVlID4gMCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgbW9udGggKz0gcmVsYXRpdmVUaW1lT2JqZWN0Py52YWx1ZVxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfSBlbHNlIGlmIChyZWxhdGl2ZVRpbWVPYmplY3Q/LnVuaXQgPT09ICd5ZWFyJykge1xuICAgICAgICAgICAgICAgICAgICBpZiAocmVsYXRpdmVUaW1lT2JqZWN0Py52YWx1ZSA+IDApIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHllYXIgKz0gcmVsYXRpdmVUaW1lT2JqZWN0Py52YWx1ZVxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBkYXRlQSA9IGRheWpzKGN1cnJlbnRUaW1lLCAnWVlZWS1NTS1ERCcpLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5hZGQoZGF5LCAnZCcpXG4gICAgICAgICAgICAgICAgLmFkZCh3ZWVrLCAndycpXG4gICAgICAgICAgICAgICAgLmFkZChtb250aCwgJ00nKVxuICAgICAgICAgICAgICAgIC5hZGQoeWVhciwgJ3knKVxuICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVlZLU1NLUREJylcbiAgICAgICAgfSBlbHNlIGlmIChkYXRlSlNPTkJvZHk/Lm9sZERhdGU/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3cgPT09ICdzdWJ0cmFjdCcpIHtcblxuICAgICAgICAgICAgbGV0IGRheSA9IDBcbiAgICAgICAgICAgIGxldCB3ZWVrID0gMFxuICAgICAgICAgICAgbGV0IG1vbnRoID0gMFxuICAgICAgICAgICAgbGV0IHllYXIgPSAwXG5cbiAgICAgICAgICAgIGZvciAoY29uc3QgcmVsYXRpdmVUaW1lT2JqZWN0IG9mIGRhdGVKU09OQm9keT8ub2xkRGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vdykge1xuXG4gICAgICAgICAgICAgICAgaWYgKHJlbGF0aXZlVGltZU9iamVjdD8udW5pdCA9PT0gJ2RheScpIHtcbiAgICAgICAgICAgICAgICAgICAgaWYgKHJlbGF0aXZlVGltZU9iamVjdD8udmFsdWUgPiAwKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICBkYXkgKz0gcmVsYXRpdmVUaW1lT2JqZWN0Py52YWx1ZVxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfSBlbHNlIGlmIChyZWxhdGl2ZVRpbWVPYmplY3Q/LnVuaXQgPT09ICd3ZWVrJykge1xuICAgICAgICAgICAgICAgICAgICBpZiAocmVsYXRpdmVUaW1lT2JqZWN0Py52YWx1ZSA+IDApIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHdlZWsgKz0gcmVsYXRpdmVUaW1lT2JqZWN0Py52YWx1ZVxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfSBlbHNlIGlmIChyZWxhdGl2ZVRpbWVPYmplY3Q/LnVuaXQgPT09ICdtb250aCcpIHtcbiAgICAgICAgICAgICAgICAgICAgaWYgKHJlbGF0aXZlVGltZU9iamVjdD8udmFsdWUgPiAwKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICBtb250aCArPSByZWxhdGl2ZVRpbWVPYmplY3Q/LnZhbHVlXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9IGVsc2UgaWYgKHJlbGF0aXZlVGltZU9iamVjdD8udW5pdCA9PT0gJ3llYXInKSB7XG4gICAgICAgICAgICAgICAgICAgIGlmIChyZWxhdGl2ZVRpbWVPYmplY3Q/LnZhbHVlID4gMCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgeWVhciArPSByZWxhdGl2ZVRpbWVPYmplY3Q/LnZhbHVlXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGRhdGVBID0gZGF5anMoY3VycmVudFRpbWUsICdZWVlZLU1NLUREVEhIOm1tJykudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLnN1YnRyYWN0KGRheSwgJ2QnKVxuICAgICAgICAgICAgICAgIC5zdWJ0cmFjdCh3ZWVrLCAndycpXG4gICAgICAgICAgICAgICAgLnN1YnRyYWN0KG1vbnRoLCAnTScpXG4gICAgICAgICAgICAgICAgLnN1YnRyYWN0KHllYXIsICd5JylcbiAgICAgICAgICAgICAgICAuZm9ybWF0KClcbiAgICAgICAgfVxuICAgIH1cblxuICAgIC8vIHNldCBkYXRlQlxuICAgIGlmIChkYXRlSlNPTkJvZHk/LmRheSkge1xuICAgICAgICBkYXRlQiA9IGAke2RhdGVKU09OQm9keT8ueWVhciB8fCBkYXlqcygpLmZvcm1hdCgnWVlZWScpfS0ke2RhdGVKU09OQm9keT8ubW9udGggfHwgZGF5anMoKS5mb3JtYXQoJ01NJyl9LSR7ZGF0ZUpTT05Cb2R5Py5kYXkgfHwgZGF5anMoKS50eih0aW1lem9uZSkuZm9ybWF0KCdERCcpfWBcbiAgICAgICAgLy8gaWYgaXNvV2Vla2RheSAtPiB1c2VyIGludGVudCBpcyBjdXJyZW50IHdlZWtcbiAgICB9IGVsc2UgaWYgKGRhdGVKU09OQm9keT8uaXNvV2Vla2RheSkge1xuICAgICAgICBjb25zdCBjdXJyZW50SVNPRGF5ID0gZ2V0SVNPRGF5KGRheWpzKCkudHoodGltZXpvbmUpLnRvRGF0ZSgpKVxuXG4gICAgICAgIGNvbnN0IGdpdmVuSVNPRGF5ID0gZGF0ZUpTT05Cb2R5Lmlzb1dlZWtkYXlcblxuICAgICAgICAvLyBhZGQgYSB3ZWVrIGlmIGdpdmVuSVNPRGF5IDwgY3VycmVudElTT0RheVxuXG4gICAgICAgIGlmIChnaXZlbklTT0RheSA8IGN1cnJlbnRJU09EYXkpIHtcbiAgICAgICAgICAgIGNvbnN0IHBhcnNlZFBhcnRpYWxFbmREYXRlID0gZGF5anMoYCR7ZGF0ZUpTT05Cb2R5Py55ZWFyIHx8IGRheWpzKCkuZm9ybWF0KCdZWVlZJyl9LSR7ZGF0ZUpTT05Cb2R5Py5tb250aCB8fCBkYXlqcygpLmZvcm1hdCgnTU0nKX0tJHtkYXRlSlNPTkJvZHk/LmRheSB8fCBkYXlqcygpLnR6KHRpbWV6b25lKS5mb3JtYXQoJ0REJyl9YCwgJ1lZWVktTU0tREQnKVxuICAgICAgICAgICAgZGF0ZUIgPSBkYXlqcyhzZXRJU09EYXkoZGF5anMocGFyc2VkUGFydGlhbEVuZERhdGUsICdZWVlZLU1NLUREJykudHoodGltZXpvbmUsIHRydWUpLmFkZCgxLCAndycpLnRvRGF0ZSgpLCBnaXZlbklTT0RheSkpLmZvcm1hdCgnWVlZWS1NTS1ERCcpXG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBjb25zdCBwYXJzZWRQYXJ0aWFsRW5kRGF0ZSA9IGRheWpzKGAke2RhdGVKU09OQm9keT8ueWVhciB8fCBkYXlqcygpLmZvcm1hdCgnWVlZWScpfS0ke2RhdGVKU09OQm9keT8ubW9udGggfHwgZGF5anMoKS5mb3JtYXQoJ01NJyl9LSR7ZGF0ZUpTT05Cb2R5Py5kYXkgfHwgZGF5anMoKS50eih0aW1lem9uZSkuZm9ybWF0KCdERCcpfWAsICdZWVlZLU1NLUREJylcbiAgICAgICAgICAgIGRhdGVCID0gZGF5anMoc2V0SVNPRGF5KGRheWpzKHBhcnNlZFBhcnRpYWxFbmREYXRlLCAnWVlZWS1NTS1ERCcpLnR6KHRpbWV6b25lLCB0cnVlKS50b0RhdGUoKSwgZ2l2ZW5JU09EYXkpKS5mb3JtYXQoJ1lZWVktTU0tREQnKVxuICAgICAgICB9XG4gICAgfSBlbHNlIGlmIChkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUZyb21Ob3c/LlswXSkge1xuXG4gICAgICAgIGlmIChkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3cgPT09ICdhZGQnKSB7XG4gICAgICAgICAgICAvLyBsb29wIHRocm91Z2ggYWxsIHBvc3NpYmxlIHZhbHVlc1xuICAgICAgICAgICAgbGV0IGRheSA9IDBcbiAgICAgICAgICAgIGxldCB3ZWVrID0gMFxuICAgICAgICAgICAgbGV0IG1vbnRoID0gMFxuICAgICAgICAgICAgbGV0IHllYXIgPSAwXG5cbiAgICAgICAgICAgIGZvciAoY29uc3QgcmVsYXRpdmVUaW1lT2JqZWN0IG9mIGRhdGVKU09OQm9keT8ucmVsYXRpdmVUaW1lRnJvbU5vdykge1xuXG4gICAgICAgICAgICAgICAgaWYgKHJlbGF0aXZlVGltZU9iamVjdD8udW5pdCA9PT0gJ2RheScpIHtcbiAgICAgICAgICAgICAgICAgICAgaWYgKHJlbGF0aXZlVGltZU9iamVjdD8udmFsdWUgPiAwKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICBkYXkgKz0gcmVsYXRpdmVUaW1lT2JqZWN0Py52YWx1ZVxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfSBlbHNlIGlmIChyZWxhdGl2ZVRpbWVPYmplY3Q/LnVuaXQgPT09ICd3ZWVrJykge1xuICAgICAgICAgICAgICAgICAgICBpZiAocmVsYXRpdmVUaW1lT2JqZWN0Py52YWx1ZSA+IDApIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHdlZWsgKz0gcmVsYXRpdmVUaW1lT2JqZWN0Py52YWx1ZVxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfSBlbHNlIGlmIChyZWxhdGl2ZVRpbWVPYmplY3Q/LnVuaXQgPT09ICdtb250aCcpIHtcbiAgICAgICAgICAgICAgICAgICAgaWYgKHJlbGF0aXZlVGltZU9iamVjdD8udmFsdWUgPiAwKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICBtb250aCArPSByZWxhdGl2ZVRpbWVPYmplY3Q/LnZhbHVlXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9IGVsc2UgaWYgKHJlbGF0aXZlVGltZU9iamVjdD8udW5pdCA9PT0gJ3llYXInKSB7XG4gICAgICAgICAgICAgICAgICAgIGlmIChyZWxhdGl2ZVRpbWVPYmplY3Q/LnZhbHVlID4gMCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgeWVhciArPSByZWxhdGl2ZVRpbWVPYmplY3Q/LnZhbHVlXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGRhdGVCID0gZGF5anMoZGF0ZUEsICdZWVlZLU1NLUREVEhIOm1tJykudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgLmFkZChkYXksICdkJylcbiAgICAgICAgICAgICAgICAuYWRkKHdlZWssICd3JylcbiAgICAgICAgICAgICAgICAuYWRkKG1vbnRoLCAnTScpXG4gICAgICAgICAgICAgICAgLmFkZCh5ZWFyLCAneScpXG4gICAgICAgICAgICAgICAgLmZvcm1hdCgpXG4gICAgICAgIH0gZWxzZSBpZiAoZGF0ZUpTT05Cb2R5Py5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93ID09PSAnc3VidHJhY3QnKSB7XG5cbiAgICAgICAgICAgIGxldCBkYXkgPSAwXG4gICAgICAgICAgICBsZXQgd2VlayA9IDBcbiAgICAgICAgICAgIGxldCBtb250aCA9IDBcbiAgICAgICAgICAgIGxldCB5ZWFyID0gMFxuXG4gICAgICAgICAgICBmb3IgKGNvbnN0IHJlbGF0aXZlVGltZU9iamVjdCBvZiBkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUZyb21Ob3cpIHtcblxuICAgICAgICAgICAgICAgIGlmIChyZWxhdGl2ZVRpbWVPYmplY3Q/LnVuaXQgPT09ICdkYXknKSB7XG4gICAgICAgICAgICAgICAgICAgIGlmIChyZWxhdGl2ZVRpbWVPYmplY3Q/LnZhbHVlID4gMCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgZGF5ICs9IHJlbGF0aXZlVGltZU9iamVjdD8udmFsdWVcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAocmVsYXRpdmVUaW1lT2JqZWN0Py51bml0ID09PSAnd2VlaycpIHtcbiAgICAgICAgICAgICAgICAgICAgaWYgKHJlbGF0aXZlVGltZU9iamVjdD8udmFsdWUgPiAwKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICB3ZWVrICs9IHJlbGF0aXZlVGltZU9iamVjdD8udmFsdWVcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAocmVsYXRpdmVUaW1lT2JqZWN0Py51bml0ID09PSAnbW9udGgnKSB7XG4gICAgICAgICAgICAgICAgICAgIGlmIChyZWxhdGl2ZVRpbWVPYmplY3Q/LnZhbHVlID4gMCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgbW9udGggKz0gcmVsYXRpdmVUaW1lT2JqZWN0Py52YWx1ZVxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfSBlbHNlIGlmIChyZWxhdGl2ZVRpbWVPYmplY3Q/LnVuaXQgPT09ICd5ZWFyJykge1xuICAgICAgICAgICAgICAgICAgICBpZiAocmVsYXRpdmVUaW1lT2JqZWN0Py52YWx1ZSA+IDApIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHllYXIgKz0gcmVsYXRpdmVUaW1lT2JqZWN0Py52YWx1ZVxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBkYXRlQiA9IGRheWpzKGN1cnJlbnRUaW1lLCAnWVlZWS1NTS1ERFRISDptbScpLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5zdWJ0cmFjdChkYXksICdkJylcbiAgICAgICAgICAgICAgICAuc3VidHJhY3Qod2VlaywgJ3cnKVxuICAgICAgICAgICAgICAgIC5zdWJ0cmFjdChtb250aCwgJ00nKVxuICAgICAgICAgICAgICAgIC5zdWJ0cmFjdCh5ZWFyLCAneScpXG4gICAgICAgICAgICAgICAgLmZvcm1hdCgpXG4gICAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAoZGF0ZUEgJiYgZGF0ZUIpIHtcbiAgICAgICAgaWYgKGRheWpzKGRhdGVBKS5pc0JlZm9yZShkYXlqcyhkYXRlQiwgJ2RheScpKSkge1xuICAgICAgICAgICAgc3RhcnREYXRlID0gZGF5anMoZGF0ZUEsICdZWVlZLU1NLUREJykuc3VidHJhY3QoMSwgJ2QnKS5mb3JtYXQoJ1lZWVktTU0tREQnKVxuICAgICAgICAgICAgZW5kRGF0ZSA9IGRheWpzKGRhdGVCLCAnWVlZWS1NTS1ERCcpLmFkZCgxLCAnZCcpLmZvcm1hdCgnWVlZWS1NTS1ERCcpXG4gICAgICAgIH0gZWxzZSBpZiAoZGF5anMoZGF0ZUIpLmlzQmVmb3JlKGRheWpzKGRhdGVBLCAnZGF5JykpKSB7XG4gICAgICAgICAgICBzdGFydERhdGUgPSBkYXlqcyhkYXRlQiwgJ1lZWVktTU0tREQnKS5zdWJ0cmFjdCgxLCAnZCcpLmZvcm1hdCgnWVlZWS1NTS1ERCcpXG4gICAgICAgICAgICBlbmREYXRlID0gZGF5anMoZGF0ZUEsICdZWVlZLU1NLUREJykuYWRkKDEsICdkJykuZm9ybWF0KCdZWVlZLU1NLUREJylcbiAgICAgICAgfVxuICAgIH0gZWxzZSBpZiAoZGF0ZUEgJiYgIWRhdGVCKSB7XG4gICAgICAgIHN0YXJ0RGF0ZSA9IGRheWpzKGRhdGVBLCAnWVlZWS1NTS1ERCcpLnN1YnRyYWN0KDEsICdkJykuZm9ybWF0KCdZWVlZLU1NLUREJylcbiAgICAgICAgZW5kRGF0ZSA9IGRheWpzKHN0YXJ0RGF0ZSkudHoodGltZXpvbmUsIHRydWUpLmFkZCg0LCAndycpLmZvcm1hdCgnWVlZWS1NTS1ERCcpXG4gICAgfSBlbHNlIGlmIChkYXRlQiAmJiAhZGF0ZUEpIHtcbiAgICAgICAgc3RhcnREYXRlID0gZGF5anMoZGF0ZUIsICdZWVlZLU1NLUREJykuc3VidHJhY3QoMSwgJ2QnKS5mb3JtYXQoJ1lZWVktTU0tREQnKVxuICAgICAgICBlbmREYXRlID0gZGF5anMoc3RhcnREYXRlKS50eih0aW1lem9uZSwgdHJ1ZSkuYWRkKDQsICd3JykuZm9ybWF0KCdZWVlZLU1NLUREJylcbiAgICB9XG5cblxuICAgIHJldHVybiB7XG4gICAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgICAgZW5kRGF0ZSxcbiAgICB9XG59XG5cbmV4cG9ydCBjb25zdCBleHRyYXBvbGF0ZURhdGVGcm9tSlNPTkRhdGEgPSAoXG4gICAgY3VycmVudFRpbWU6IHN0cmluZyxcbiAgICB0aW1lem9uZTogc3RyaW5nLFxuICAgIHllYXI6IHN0cmluZyB8IG51bGwgfCB1bmRlZmluZWQsXG4gICAgbW9udGg6IHN0cmluZyB8IG51bGwgfCB1bmRlZmluZWQsXG4gICAgZGF5OiBzdHJpbmcgfCBudWxsIHwgdW5kZWZpbmVkLFxuICAgIGlzb1dlZWtkYXk6IG51bWJlciB8IG51bGwgfCB1bmRlZmluZWQsXG4gICAgaG91cjogbnVtYmVyIHwgbnVsbCB8IHVuZGVmaW5lZCxcbiAgICBtaW51dGU6IG51bWJlciB8IG51bGwgfCB1bmRlZmluZWQsXG4gICAgdGltZTogVGltZSB8IG51bGwgfCB1bmRlZmluZWQsXG4gICAgcmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdzogUmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vd1R5cGUgfCBudWxsIHwgdW5kZWZpbmVkLFxuICAgIHJlbGF0aXZlVGltZUZyb21Ob3c6IFJlbGF0aXZlVGltZUZyb21Ob3dUeXBlW10gfCBudWxsIHwgdW5kZWZpbmVkLFxuKSA9PiB7XG5cbiAgICBsZXQgbWVldGluZ1N0YXJ0RGF0ZSA9ICcnXG4gICAgbGV0IG1lZXRpbmdTdGFydERhdGVPYmplY3Q6IERheWpzID0gZGF5anMoY3VycmVudFRpbWUsICdZWVlZLU1NLUREVEhIOm1tJykudHoodGltZXpvbmUsIHRydWUpXG4gICAgY29uc3QgZnVuY3Rpb25OYW1lID0gJ2V4dHJhcG9sYXRlRGF0ZUZyb21KU09ORGF0YSc7XG5cbiAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBJbml0aWFsIHBhcmFtczpgLCB7IGN1cnJlbnRUaW1lLCB0aW1lem9uZSwgeWVhciwgbW9udGgsIGRheSwgaXNvV2Vla2RheSwgaG91ciwgbWludXRlLCB0aW1lLCByZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93LCByZWxhdGl2ZVRpbWVGcm9tTm93IH0pO1xuXG5cbiAgICBpZiAoZGF5KSB7XG5cbiAgICAgICAgaWYgKCghIWhvdXIpICYmICghIW1pbnV0ZSkpIHtcblxuICAgICAgICAgICAgaWYgKHllYXIgJiYgbW9udGgpIHtcbiAgICAgICAgICAgICAgICBjb25zdCB5ZWFyQW5kTW9udGhBbmREYXRlID0gZGF5anMoYCR7eWVhcn0tJHttb250aH0tJHtkYXl9YCwgJ1lZWVktTU0tREQnKS50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBDb25kaXRpb246IGRheSwgaG91ciwgbWludXRlLCB5ZWFyLCBtb250aGAsIHsgeWVhckFuZE1vbnRoQW5kRGF0ZUZvcm1hdHRlZDogeWVhckFuZE1vbnRoQW5kRGF0ZS5mb3JtYXQoKSB9KTtcblxuICAgICAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBtZWV0aW5nU3RhcnREYXRlT2JqZWN0XG4gICAgICAgICAgICAgICAgICAgIC55ZWFyKHllYXJBbmRNb250aEFuZERhdGUueWVhcigpKVxuICAgICAgICAgICAgICAgICAgICAubW9udGgoeWVhckFuZE1vbnRoQW5kRGF0ZS5tb250aCgpKVxuICAgICAgICAgICAgICAgICAgICAuZGF0ZSh5ZWFyQW5kTW9udGhBbmREYXRlLmRhdGUoKSlcbiAgICAgICAgICAgICAgICAgICAgLmhvdXIoaG91cilcbiAgICAgICAgICAgICAgICAgICAgLm1pbnV0ZShtaW51dGUpXG5cbiAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBtZWV0aW5nU3RhcnREYXRlT2JqZWN0IHVwZGF0ZWQgKGRheSwgaG91ciwgbWludXRlLCB5ZWFyLCBtb250aCk6YCwgeyBtZWV0aW5nU3RhcnREYXRlT2JqZWN0Rm9ybWF0dGVkOiBtZWV0aW5nU3RhcnREYXRlT2JqZWN0LmZvcm1hdCgpIH0pO1xuICAgICAgICAgICAgfSBlbHNlIHtcblxuICAgICAgICAgICAgICAgIGNvbnN0IGRhdGVPZk1vbnRoID0gZGF5anMoZGF5LCAnREQnKS50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBDb25kaXRpb246IGRheSwgaG91ciwgbWludXRlIChubyB5ZWFyL21vbnRoKWAsIHsgZGF0ZU9mTW9udGhGb3JtYXR0ZWQ6IGRhdGVPZk1vbnRoLmZvcm1hdCgpIH0pO1xuICAgICAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBtZWV0aW5nU3RhcnREYXRlT2JqZWN0XG4gICAgICAgICAgICAgICAgICAgIC5kYXRlKGRhdGVPZk1vbnRoLmRhdGUoKSlcbiAgICAgICAgICAgICAgICAgICAgLmhvdXIoaG91cilcbiAgICAgICAgICAgICAgICAgICAgLm1pbnV0ZShtaW51dGUpXG5cbiAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBtZWV0aW5nU3RhcnREYXRlT2JqZWN0IHVwZGF0ZWQgKGRheSwgaG91ciwgbWludXRlKTpgLCB7IG1lZXRpbmdTdGFydERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdTdGFydERhdGVPYmplY3QuZm9ybWF0KCkgfSk7XG4gICAgICAgICAgICB9XG5cblxuICAgICAgICB9IGVsc2UgaWYgKHRpbWUpIHtcbiAgICAgICAgICAgIGlmICh5ZWFyICYmIG1vbnRoKSB7XG4gICAgICAgICAgICAgICAgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdCA9IGRheWpzKGAke3llYXJ9LSR7bW9udGh9LSR7ZGF5fSAke3RpbWV9YCwgJ1lZWVktTU0tREQgSEg6bW0nKS50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBDb25kaXRpb246IGRheSwgdGltZSwgeWVhciwgbW9udGhgLCB7IG1lZXRpbmdTdGFydERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdTdGFydERhdGVPYmplY3QuZm9ybWF0KCkgfSk7XG4gICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBkYXlqcyhgJHtkYXl9ICR7dGltZX1gLCAnREQgSEg6bW0nKS50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBDb25kaXRpb246IGRheSwgdGltZSAobm8geWVhci9tb250aClgLCB7IG1lZXRpbmdTdGFydERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdTdGFydERhdGVPYmplY3QuZm9ybWF0KCkgfSk7XG4gICAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSBpZiAoIXRpbWUgJiYgIWhvdXIgJiYgIW1pbnV0ZSkgeyAvLyBBbGwgZGF5IGV2ZW50IGluZmVycmVkXG4gICAgICAgICAgICBpZiAoeWVhciAmJiBtb250aCkge1xuICAgICAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBkYXlqcyhgJHt5ZWFyfS0ke21vbnRofS0ke2RheX1gLCAnWVlZWS1NTS1ERCcpLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoYFske2Z1bmN0aW9uTmFtZX1dIENvbmRpdGlvbjogZGF5LCB5ZWFyLCBtb250aCAoYWxsIGRheSlgLCB7IG1lZXRpbmdTdGFydERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdTdGFydERhdGVPYmplY3QuZm9ybWF0KCkgfSk7XG4gICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBkYXlqcyhkYXksICdERCcpLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoYFske2Z1bmN0aW9uTmFtZX1dIENvbmRpdGlvbjogZGF5IChhbGwgZGF5LCBubyB5ZWFyL21vbnRoKWAsIHsgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdEZvcm1hdHRlZDogbWVldGluZ1N0YXJ0RGF0ZU9iamVjdC5mb3JtYXQoKSB9KTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgIH0gZWxzZSBpZiAoaXNvV2Vla2RheSkge1xuICAgICAgICBjb25zdCBnaXZlbklTT0RheSA9IGlzb1dlZWtkYXlcbiAgICAgICAgY29uc3QgY3VycmVudElTT0RheSA9IGdldElTT0RheShkYXlqcyhjdXJyZW50VGltZSkudHoodGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpKVxuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBDb25kaXRpb246IGlzb1dlZWtkYXlgLCB7IGdpdmVuSVNPRGF5LCBjdXJyZW50SVNPRGF5IH0pO1xuXG4gICAgICAgIGlmICgoISFob3VyKSAmJiAoISFtaW51dGUpKSB7XG4gICAgICAgICAgICBpZiAoeWVhciAmJiBtb250aCkge1xuICAgICAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBkYXlqcyhgJHt5ZWFyfS0ke21vbnRofWAsICdZWVlZLU1NJykudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgICAgIC5ob3VyKGhvdXIpXG4gICAgICAgICAgICAgICAgICAgIC5taW51dGUobWludXRlKVxuICAgICAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoYFske2Z1bmN0aW9uTmFtZX1dIGlzb1dlZWtkYXksIGhvdXIsIG1pbnV0ZSwgeWVhciwgbW9udGggLSBiYXNlOmAsIHsgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdEZvcm1hdHRlZDogbWVldGluZ1N0YXJ0RGF0ZU9iamVjdC5mb3JtYXQoKSB9KTtcblxuICAgICAgICAgICAgICAgIGlmIChnaXZlbklTT0RheSA8IGN1cnJlbnRJU09EYXkpIHtcbiAgICAgICAgICAgICAgICAgICAgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdCA9IGRheWpzKHNldElTT0RheSgobWVldGluZ1N0YXJ0RGF0ZU9iamVjdCBhcyBEYXlqcykuYWRkKDEsICd3JykudG9EYXRlKCksIGdpdmVuSVNPRGF5KSlcbiAgICAgICAgICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5kZWJ1ZyhgWyR7ZnVuY3Rpb25OYW1lfV0gaXNvV2Vla2RheSBhZGp1c3RlZCAocGFzdCBkYXkgdGhpcyB3ZWVrLCBhZGQgd2Vlayk6YCwgeyBtZWV0aW5nU3RhcnREYXRlT2JqZWN0Rm9ybWF0dGVkOiBtZWV0aW5nU3RhcnREYXRlT2JqZWN0LmZvcm1hdCgpIH0pO1xuICAgICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBkYXlqcyhzZXRJU09EYXkoKG1lZXRpbmdTdGFydERhdGVPYmplY3QgYXMgRGF5anMpLnRvRGF0ZSgpLCBnaXZlbklTT0RheSkpXG4gICAgICAgICAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoYFske2Z1bmN0aW9uTmFtZX1dIGlzb1dlZWtkYXkgYWRqdXN0ZWQgKGZ1dHVyZS9jdXJyZW50IGRheSB0aGlzIHdlZWspOmAsIHsgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdEZvcm1hdHRlZDogbWVldGluZ1N0YXJ0RGF0ZU9iamVjdC5mb3JtYXQoKSB9KTtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBkYXlqcygpLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgICAgICAuaG91cihob3VyKVxuICAgICAgICAgICAgICAgICAgICAubWludXRlKG1pbnV0ZSlcbiAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBpc29XZWVrZGF5LCBob3VyLCBtaW51dGUgKG5vIHllYXIvbW9udGgpIC0gYmFzZTpgLCB7IG1lZXRpbmdTdGFydERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdTdGFydERhdGVPYmplY3QuZm9ybWF0KCkgfSk7XG5cbiAgICAgICAgICAgICAgICBpZiAoZ2l2ZW5JU09EYXkgPCBjdXJyZW50SVNPRGF5KSB7XG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBkYXlqcyhzZXRJU09EYXkoKG1lZXRpbmdTdGFydERhdGVPYmplY3QgYXMgRGF5anMpLmFkZCgxLCAndycpLnRvRGF0ZSgpLCBnaXZlbklTT0RheSkpXG4gICAgICAgICAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoYFske2Z1bmN0aW9uTmFtZX1dIGlzb1dlZWtkYXkgYWRqdXN0ZWQgKHBhc3QgZGF5IHRoaXMgd2VlaywgYWRkIHdlZWspOmAsIHsgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdEZvcm1hdHRlZDogbWVldGluZ1N0YXJ0RGF0ZU9iamVjdC5mb3JtYXQoKSB9KTtcbiAgICAgICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgICAgICBtZWV0aW5nU3RhcnREYXRlT2JqZWN0ID0gZGF5anMoc2V0SVNPRGF5KChtZWV0aW5nU3RhcnREYXRlT2JqZWN0IGFzIERheWpzKS50b0RhdGUoKSwgZ2l2ZW5JU09EYXkpKVxuICAgICAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBpc29XZWVrZGF5IGFkanVzdGVkIChmdXR1cmUvY3VycmVudCBkYXkgdGhpcyB3ZWVrKTpgLCB7IG1lZXRpbmdTdGFydERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdTdGFydERhdGVPYmplY3QuZm9ybWF0KCkgfSk7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICB9IGVsc2UgaWYgKHRpbWUpIHtcbiAgICAgICAgICAgIGlmICh5ZWFyICYmIG1vbnRoKSB7XG4gICAgICAgICAgICAgICAgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdCA9IGRheWpzKGAke3llYXJ9LSR7bW9udGh9ICR7dGltZX1gLCAnWVlZWS1NTSBISDptbScpLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoYFske2Z1bmN0aW9uTmFtZX1dIGlzb1dlZWtkYXksIHRpbWUsIHllYXIsIG1vbnRoIC0gYmFzZTpgLCB7IG1lZXRpbmdTdGFydERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdTdGFydERhdGVPYmplY3QuZm9ybWF0KCkgfSk7XG4gICAgICAgICAgICAgICAgaWYgKGdpdmVuSVNPRGF5IDwgY3VycmVudElTT0RheSkge1xuICAgICAgICAgICAgICAgICAgICBtZWV0aW5nU3RhcnREYXRlT2JqZWN0ID0gZGF5anMoc2V0SVNPRGF5KChtZWV0aW5nU3RhcnREYXRlT2JqZWN0IGFzIERheWpzKS5hZGQoMSwgJ3cnKS50b0RhdGUoKSwgZ2l2ZW5JU09EYXkpKVxuICAgICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBkYXlqcyhzZXRJU09EYXkoKG1lZXRpbmdTdGFydERhdGVPYmplY3QgYXMgRGF5anMpLnRvRGF0ZSgpLCBnaXZlbklTT0RheSkpXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoYFske2Z1bmN0aW9uTmFtZX1dIGlzb1dlZWtkYXksIHRpbWUsIHllYXIsIG1vbnRoIC0gYWRqdXN0ZWQ6YCwgeyBtZWV0aW5nU3RhcnREYXRlT2JqZWN0Rm9ybWF0dGVkOiBtZWV0aW5nU3RhcnREYXRlT2JqZWN0LmZvcm1hdCgpIH0pO1xuICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICBtZWV0aW5nU3RhcnREYXRlT2JqZWN0ID0gZGF5anMoYCR7dGltZX1gLCAnSEg6bW0nKS50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBpc29XZWVrZGF5LCB0aW1lIChubyB5ZWFyL21vbnRoKSAtIGJhc2U6YCwgeyBtZWV0aW5nU3RhcnREYXRlT2JqZWN0Rm9ybWF0dGVkOiBtZWV0aW5nU3RhcnREYXRlT2JqZWN0LmZvcm1hdCgpIH0pO1xuICAgICAgICAgICAgICAgIGlmIChnaXZlbklTT0RheSA8IGN1cnJlbnRJU09EYXkpIHtcbiAgICAgICAgICAgICAgICAgICAgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdCA9IGRheWpzKHNldElTT0RheSgobWVldGluZ1N0YXJ0RGF0ZU9iamVjdCBhcyBEYXlqcykuYWRkKDEsICd3JykudG9EYXRlKCksIGdpdmVuSVNPRGF5KSlcbiAgICAgICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgICAgICBtZWV0aW5nU3RhcnREYXRlT2JqZWN0ID0gZGF5anMoc2V0SVNPRGF5KChtZWV0aW5nU3RhcnREYXRlT2JqZWN0IGFzIERheWpzKS50b0RhdGUoKSwgZ2l2ZW5JU09EYXkpKVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBpc29XZWVrZGF5LCB0aW1lIChubyB5ZWFyL21vbnRoKSAtIGFkanVzdGVkOmAsIHsgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdEZvcm1hdHRlZDogbWVldGluZ1N0YXJ0RGF0ZU9iamVjdC5mb3JtYXQoKSB9KTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfSBlbHNlIGlmICghaG91ciAmJiAhbWludXRlICYmICF0aW1lKSB7IC8vIEFsbCBkYXkgZm9yIGlzb1dlZWtkYXlcbiAgICAgICAgICAgIGlmICh5ZWFyICYmIG1vbnRoKSB7XG4gICAgICAgICAgICAgICAgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdCA9IGRheWpzKGAke3llYXJ9LSR7bW9udGh9YCwgJ1lZWVktTU0nKS50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBpc29XZWVrZGF5LCB5ZWFyLCBtb250aCAoYWxsIGRheSkgLSBiYXNlOmAsIHsgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdEZvcm1hdHRlZDogbWVldGluZ1N0YXJ0RGF0ZU9iamVjdC5mb3JtYXQoKSB9KTtcbiAgICAgICAgICAgICAgICBpZiAoZ2l2ZW5JU09EYXkgPCBjdXJyZW50SVNPRGF5KSB7XG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBkYXlqcyhzZXRJU09EYXkoKG1lZXRpbmdTdGFydERhdGVPYmplY3QgYXMgRGF5anMpLmFkZCgxLCAndycpLnRvRGF0ZSgpLCBnaXZlbklTT0RheSkpXG4gICAgICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICAgICAgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdCA9IGRheWpzKHNldElTT0RheSgobWVldGluZ1N0YXJ0RGF0ZU9iamVjdCBhcyBEYXlqcykudG9EYXRlKCksIGdpdmVuSVNPRGF5KSlcbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICAvLyBVdGlsaXR5IGZ1bmN0aW9uIHRvIHNhZmVseSBleHRyYWN0IEdyYXBoUUwgZGF0YSBmcm9tIGdvdCByZXNwb25zZXNcbiAgICAgICAgICAgICAgICBjb25zdCBzYWZlRXh0cmFjdEdyYXBoUUxEYXRhID0gPFQ+KHJlc3BvbnNlOiBhbnkpOiBUID0+IHtcbiAgICAgICAgICAgICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGlmIChyZXNwb25zZSAmJiByZXNwb25zZS5kYXRhKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcmV0dXJuIHJlc3BvbnNlLmRhdGEgYXMgVDtcbiAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICAgIGlmIChyZXNwb25zZSAmJiByZXNwb25zZS5ib2R5KSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29uc3QgcGFyc2VkID0gSlNPTi5wYXJzZShyZXNwb25zZS5ib2R5KTtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICByZXR1cm4gcGFyc2VkPy5kYXRhIHx8IHBhcnNlZDtcbiAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiByZXNwb25zZSBhcyBUO1xuICAgICAgICAgICAgICAgICAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgICAgICAgICAgICAgICAgICAgcmV0dXJuIHJlc3BvbnNlIGFzIFQ7XG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9O1xuXG4gICAgICAgICAgICAgICAgLy8gU2FmZSB3cmFwcGVyIGZvciBnb3QgcmVzcG9uc2VzIHdpdGggcHJvcGVyIHR5cGluZ1xuICAgICAgICAgICAgICAgIGNvbnN0IGdvdFJlc3BvbnNlSGFuZGxlciA9IGFzeW5jIDxUPihwcm9taXNlOiBQcm9taXNlPGFueT4pOiBQcm9taXNlPFQ+ID0+IHtcbiAgICAgICAgICAgICAgICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBwcm9taXNlO1xuICAgICAgICAgICAgICAgICAgICBpZiAocmVzcG9uc2UuZGF0YSkge1xuICAgICAgICAgICAgICAgICAgICAgICAgcmV0dXJuIHJlc3BvbnNlLmRhdGEgYXMgVDtcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICB0cnkge1xuICAgICAgICAgICAgICAgICAgICAgICAgcmV0dXJuIEpTT04ucGFyc2UocmVzcG9uc2UuYm9keSkuZGF0YSBhcyBUO1xuICAgICAgICAgICAgICAgICAgICB9IGNhdGNoIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHRocm93IG5ldyBFcnJvcignSW52YWxpZCByZXNwb25zZSBmb3JtYXQnKTtcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH07XG4gICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBkYXlqcygpLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoYFske2Z1bmN0aW9uTmFtZX1dIGlzb1dlZWtkYXkgKGFsbCBkYXksIG5vIHllYXIvbW9udGgpIC0gYmFzZTpgLCB7IG1lZXRpbmdTdGFydERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdTdGFydERhdGVPYmplY3QuZm9ybWF0KCkgfSk7XG4gICAgICAgICAgICAgICAgaWYgKGdpdmVuSVNPRGF5IDwgY3VycmVudElTT0RheSkge1xuICAgICAgICAgICAgICAgICAgICBtZWV0aW5nU3RhcnREYXRlT2JqZWN0ID0gZGF5anMoc2V0SVNPRGF5KChtZWV0aW5nU3RhcnREYXRlT2JqZWN0IGFzIERheWpzKS5hZGQoMSwgJ3cnKS50b0RhdGUoKSwgZ2l2ZW5JU09EYXkpKVxuICAgICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBkYXlqcyhzZXRJU09EYXkoKG1lZXRpbmdTdGFydERhdGVPYmplY3QgYXMgRGF5anMpLnRvRGF0ZSgpLCBnaXZlbklTT0RheSkpXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5kZWJ1ZyhgWyR7ZnVuY3Rpb25OYW1lfV0gaXNvV2Vla2RheSAoYWxsIGRheSkgLSBhZGp1c3RlZDpgLCB7IG1lZXRpbmdTdGFydERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdTdGFydERhdGVPYmplY3QuZm9ybWF0KCkgfSk7XG4gICAgICAgIH1cblxuICAgIH0gZWxzZSBpZiAocmVsYXRpdmVUaW1lRnJvbU5vdz8uWzBdKSB7XG4gICAgICAgIGxldCBtaW51dGVDaGFuZ2VkID0gZmFsc2VcbiAgICAgICAgbGV0IGhvdXJDaGFuZ2VkID0gZmFsc2VcbiAgICAgICAgbGV0IGNhbGN1bGF0ZWRNaW51dGUgPSAwLCBjYWxjdWxhdGVkSG91ciA9IDAsIGNhbGN1bGF0ZWREYXkgPSAwLCBjYWxjdWxhdGVkV2VlayA9IDAsIGNhbGN1bGF0ZWRNb250aCA9IDAsIGNhbGN1bGF0ZWRZZWFyID0gMDtcblxuICAgICAgICBmb3IgKGNvbnN0IHJlbGF0aXZlVGltZU9iamVjdCBvZiByZWxhdGl2ZVRpbWVGcm9tTm93KSB7XG4gICAgICAgICAgICBpZiAocmVsYXRpdmVUaW1lT2JqZWN0Py52YWx1ZSA+IDApIHtcbiAgICAgICAgICAgICAgICBzd2l0Y2ggKHJlbGF0aXZlVGltZU9iamVjdC51bml0KSB7XG4gICAgICAgICAgICAgICAgICAgIGNhc2UgJ21pbnV0ZSc6IGNhbGN1bGF0ZWRNaW51dGUgKz0gcmVsYXRpdmVUaW1lT2JqZWN0LnZhbHVlOyBtaW51dGVDaGFuZ2VkID0gdHJ1ZTsgYnJlYWs7XG4gICAgICAgICAgICAgICAgICAgIGNhc2UgJ2hvdXInOiBjYWxjdWxhdGVkSG91ciArPSByZWxhdGl2ZVRpbWVPYmplY3QudmFsdWU7IGhvdXJDaGFuZ2VkID0gdHJ1ZTsgYnJlYWs7XG4gICAgICAgICAgICAgICAgICAgIGNhc2UgJ2RheSc6IGNhbGN1bGF0ZWREYXkgKz0gcmVsYXRpdmVUaW1lT2JqZWN0LnZhbHVlOyBicmVhaztcbiAgICAgICAgICAgICAgICAgICAgY2FzZSAnd2Vlayc6IGNhbGN1bGF0ZWRXZWVrICs9IHJlbGF0aXZlVGltZU9iamVjdC52YWx1ZTsgYnJlYWs7XG4gICAgICAgICAgICAgICAgICAgIGNhc2UgJ21vbnRoJzogY2FsY3VsYXRlZE1vbnRoICs9IHJlbGF0aXZlVGltZU9iamVjdC52YWx1ZTsgYnJlYWs7XG4gICAgICAgICAgICAgICAgICAgIGNhc2UgJ3llYXInOiBjYWxjdWxhdGVkWWVhciArPSByZWxhdGl2ZVRpbWVPYmplY3QudmFsdWU7IGJyZWFrO1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBDb25kaXRpb246IHJlbGF0aXZlVGltZUZyb21Ob3cgLSBjYWxjdWxhdGVkIG9mZnNldHM6YCwgeyBjYWxjdWxhdGVkTWludXRlLCBjYWxjdWxhdGVkSG91ciwgY2FsY3VsYXRlZERheSwgY2FsY3VsYXRlZFdlZWssIGNhbGN1bGF0ZWRNb250aCwgY2FsY3VsYXRlZFllYXIsIHJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3cgfSk7XG5cblxuICAgICAgICBpZiAoKHJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3cgPT09ICdhZGQnKSB8fCAocmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyA9PT0gbnVsbCkpIHtcbiAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBkYXlqcyhjdXJyZW50VGltZSwgJ1lZWVktTU0tRERUSEg6bW0nKS50eih0aW1lem9uZSwgdHJ1ZSkgLy8gVXNlIGZ1bGwgY3VycmVudFRpbWUgaWYgYWRkaW5nIHRpbWUgcGFydHNcbiAgICAgICAgICAgICAgICAuYWRkKGNhbGN1bGF0ZWRNaW51dGUsICdtJylcbiAgICAgICAgICAgICAgICAuYWRkKGNhbGN1bGF0ZWRIb3VyLCAnaCcpXG4gICAgICAgICAgICAgICAgLmFkZChjYWxjdWxhdGVkRGF5LCAnZCcpXG4gICAgICAgICAgICAgICAgLmFkZChjYWxjdWxhdGVkV2VlaywgJ3cnKVxuICAgICAgICAgICAgICAgIC5hZGQoY2FsY3VsYXRlZE1vbnRoLCAnTScpXG4gICAgICAgICAgICAgICAgLmFkZChjYWxjdWxhdGVkWWVhciwgJ3knKVxuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5kZWJ1ZyhgWyR7ZnVuY3Rpb25OYW1lfV0gcmVsYXRpdmVUaW1lIC0gYWRkIG9wZXJhdGlvbjpgLCB7IG1lZXRpbmdTdGFydERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdTdGFydERhdGVPYmplY3QuZm9ybWF0KCkgfSk7XG4gICAgICAgIH0gZWxzZSBpZiAocmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyA9PT0gJ3N1YnRyYWN0Jykge1xuICAgICAgICAgICAgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdCA9IGRheWpzKGN1cnJlbnRUaW1lLCAnWVlZWS1NTS1ERFRISDptbScpLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5zdWJ0cmFjdChjYWxjdWxhdGVkTWludXRlLCAnbScpXG4gICAgICAgICAgICAgICAgLnN1YnRyYWN0KGNhbGN1bGF0ZWRIb3VyLCAnaCcpXG4gICAgICAgICAgICAgICAgLnN1YnRyYWN0KGNhbGN1bGF0ZWREYXksICdkJylcbiAgICAgICAgICAgICAgICAuc3VidHJhY3QoY2FsY3VsYXRlZFdlZWssICd3JylcbiAgICAgICAgICAgICAgICAuc3VidHJhY3QoY2FsY3VsYXRlZE1vbnRoLCAnTScpXG4gICAgICAgICAgICAgICAgLnN1YnRyYWN0KGNhbGN1bGF0ZWRZZWFyLCAneScpXG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSByZWxhdGl2ZVRpbWUgLSBzdWJ0cmFjdCBvcGVyYXRpb246YCwgeyBtZWV0aW5nU3RhcnREYXRlT2JqZWN0Rm9ybWF0dGVkOiBtZWV0aW5nU3RhcnREYXRlT2JqZWN0LmZvcm1hdCgpIH0pO1xuICAgICAgICB9XG5cbiAgICAgICAgLy8gQXBwbHkgZXhwbGljaXQgaG91ci9taW51dGUvdGltZSBpZiBwcm92aWRlZCwgcG90ZW50aWFsbHkgb3ZlcnJpZGluZyByZWxhdGl2ZSBjYWxjdWxhdGlvbiBmb3IgdGltZSBwYXJ0XG4gICAgICAgIGlmICgoISFob3VyKSAmJiAoISFtaW51dGUpKSB7XG4gICAgICAgICAgICBpZiAoeWVhciAmJiBtb250aCkge1xuICAgICAgICAgICAgICAgIGNvbnN0IHllYXJBbmRNb250aCA9IGRheWpzKGAke3llYXJ9LSR7bW9udGh9YCwgJ1lZWVktTU0nKS50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICBtZWV0aW5nU3RhcnREYXRlT2JqZWN0ID0gbWVldGluZ1N0YXJ0RGF0ZU9iamVjdC55ZWFyKHllYXJBbmRNb250aC55ZWFyKCkpLm1vbnRoKHllYXJBbmRNb250aC5tb250aCgpKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBtZWV0aW5nU3RhcnREYXRlT2JqZWN0LmhvdXIoaG91cikubWludXRlKG1pbnV0ZSk7XG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSByZWxhdGl2ZVRpbWUgd2l0aCBleHBsaWNpdCBob3VyL21pbnV0ZSBvdmVycmlkZTpgLCB7IG1lZXRpbmdTdGFydERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdTdGFydERhdGVPYmplY3QuZm9ybWF0KCksIHllYXIsIG1vbnRoIH0pO1xuICAgICAgICB9IGVsc2UgaWYgKHRpbWUpIHtcbiAgICAgICAgICAgIGNvbnN0IHRlbXBUaW1lID0gZGF5anModGltZSwgJ0hIOm1tJykudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICBpZiAoeWVhciAmJiBtb250aCkge1xuICAgICAgICAgICAgICAgIGNvbnN0IHllYXJBbmRNb250aCA9IGRheWpzKGAke3llYXJ9LSR7bW9udGh9YCwgJ1lZWVktTU0nKS50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICBtZWV0aW5nU3RhcnREYXRlT2JqZWN0ID0gbWVldGluZ1N0YXJ0RGF0ZU9iamVjdC55ZWFyKHllYXJBbmRNb250aC55ZWFyKCkpLm1vbnRoKHllYXJBbmRNb250aC5tb250aCgpKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBtZWV0aW5nU3RhcnREYXRlT2JqZWN0LmhvdXIodGVtcFRpbWUuaG91cigpKS5taW51dGUodGVtcFRpbWUubWludXRlKCkpO1xuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5kZWJ1ZyhgWyR7ZnVuY3Rpb25OYW1lfV0gcmVsYXRpdmVUaW1lIHdpdGggZXhwbGljaXQgdGltZSBvdmVycmlkZTpgLCB7IG1lZXRpbmdTdGFydERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdTdGFydERhdGVPYmplY3QuZm9ybWF0KCksIHllYXIsIG1vbnRoIH0pO1xuICAgICAgICB9IGVsc2UgaWYgKCFob3VyQ2hhbmdlZCAmJiAhbWludXRlQ2hhbmdlZCkgeyAvLyBJZiBubyByZWxhdGl2ZSBtaW51dGUvaG91ciBhbmQgbm8gZXhwbGljaXQgdGltZSwgYXBwbHkganVzdCB5ZWFyL21vbnRoIGlmIGdpdmVuXG4gICAgICAgICAgICAgaWYgKHllYXIgJiYgbW9udGgpIHtcbiAgICAgICAgICAgICAgICBjb25zdCB5ZWFyQW5kTW9udGggPSBkYXlqcyhgJHt5ZWFyfS0ke21vbnRofWAsICdZWVlZLU1NJykudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdCA9IG1lZXRpbmdTdGFydERhdGVPYmplY3QueWVhcih5ZWFyQW5kTW9udGgueWVhcigpKS5tb250aCh5ZWFyQW5kTW9udGgubW9udGgoKSk7XG4gICAgICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5kZWJ1ZyhgWyR7ZnVuY3Rpb25OYW1lfV0gcmVsYXRpdmVUaW1lIHdpdGggZXhwbGljaXQgeWVhci9tb250aCAobm8gdGltZSBwYXJ0cyBjaGFuZ2VkKTpgLCB7IG1lZXRpbmdTdGFydERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdTdGFydERhdGVPYmplY3QuZm9ybWF0KCkgfSk7XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICB9XG5cbiAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBGaW5hbCBtZWV0aW5nU3RhcnREYXRlT2JqZWN0OmAsIHsgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdEZvcm1hdHRlZDogbWVldGluZ1N0YXJ0RGF0ZU9iamVjdC5mb3JtYXQoKSB9KTtcbiAgICBtZWV0aW5nU3RhcnREYXRlID0gKG1lZXRpbmdTdGFydERhdGVPYmplY3QgYXMgRGF5anMpLmZvcm1hdCgpXG4gICAgcmV0dXJuIG1lZXRpbmdTdGFydERhdGVcbn1cblxuZXhwb3J0IGNvbnN0IGV4dHJhcG9sYXRlU3RhcnREYXRlRnJvbUpTT05EYXRhID0gKFxuICAgIGN1cnJlbnRUaW1lOiBzdHJpbmcsXG4gICAgdGltZXpvbmU6IHN0cmluZyxcbiAgICB5ZWFyOiBzdHJpbmcgfCBudWxsIHwgdW5kZWZpbmVkLFxuICAgIG1vbnRoOiBzdHJpbmcgfCBudWxsIHwgdW5kZWZpbmVkLFxuICAgIGRheTogc3RyaW5nIHwgbnVsbCB8IHVuZGVmaW5lZCxcbiAgICBpc29XZWVrZGF5OiBudW1iZXIgfCBudWxsIHwgdW5kZWZpbmVkLFxuICAgIGhvdXI6IG51bWJlciB8IG51bGwgfCB1bmRlZmluZWQsXG4gICAgbWludXRlOiBudW1iZXIgfCBudWxsIHwgdW5kZWZpbmVkLFxuICAgIHRpbWU6IFRpbWUgfCBudWxsIHwgdW5kZWZpbmVkLFxuICAgIHJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3c6IFJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3dUeXBlIHwgbnVsbCB8IHVuZGVmaW5lZCxcbiAgICByZWxhdGl2ZVRpbWVGcm9tTm93OiBSZWxhdGl2ZVRpbWVGcm9tTm93VHlwZVtdIHwgbnVsbCB8IHVuZGVmaW5lZCxcbikgPT4ge1xuICAgIC8vIFRoaXMgZnVuY3Rpb24gaXMgdmVyeSBzaW1pbGFyIHRvIGV4dHJhcG9sYXRlRGF0ZUZyb21KU09ORGF0YSwgYnV0IHNldHMgdGltZSB0byAwMDowMCBpZiBub3Qgc3BlY2lmaWVkLlxuICAgIC8vIEZvciBicmV2aXR5LCBkZXRhaWxlZCBsb2dnaW5nIGZvciBlYWNoIHBhdGggaXMgb21pdHRlZCBpZiBpdCdzIGlkZW50aWNhbCB0byB0aGUgYWJvdmUsIGZvY3VzaW5nIG9uIGRpZmZlcmVuY2VzLlxuICAgIGxldCBtZWV0aW5nU3RhcnREYXRlID0gJydcbiAgICBsZXQgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdDogRGF5anMgPSBkYXlqcyhjdXJyZW50VGltZSwgJ1lZWVktTU0tRERUSEg6bW0nKS50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICBjb25zdCBmdW5jdGlvbk5hbWUgPSAnZXh0cmFwb2xhdGVTdGFydERhdGVGcm9tSlNPTkRhdGEnOyAvLyBGb3Igc3BlY2lmaWMgbG9nZ2luZyBpZiBuZWVkZWRcblxuICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoYFske2Z1bmN0aW9uTmFtZX1dIEluaXRpYWwgcGFyYW1zOmAsIHsgY3VycmVudFRpbWUsIHRpbWV6b25lLCB5ZWFyLCBtb250aCwgZGF5LCBpc29XZWVrZGF5LCBob3VyLCBtaW51dGUsIHRpbWUsIHJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csIHJlbGF0aXZlVGltZUZyb21Ob3cgfSk7XG5cbiAgICBpZiAoZGF5KSB7XG4gICAgICAgIGlmICgoISFob3VyKSAmJiAoISFtaW51dGUpKSB7XG4gICAgICAgICAgICAgaWYgKHllYXIgJiYgbW9udGgpIHtcbiAgICAgICAgICAgICAgICBjb25zdCB5ZWFyQW5kTW9udGhBbmREYXRlID0gZGF5anMoYCR7eWVhcn0tJHttb250aH0tJHtkYXl9YCwgJ1lZWVktTU0tREQnKS50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICBtZWV0aW5nU3RhcnREYXRlT2JqZWN0ID0gbWVldGluZ1N0YXJ0RGF0ZU9iamVjdC55ZWFyKHllYXJBbmRNb250aEFuZERhdGUueWVhcigpKS5tb250aCh5ZWFyQW5kTW9udGhBbmREYXRlLm1vbnRoKCkpLmRhdGUoeWVhckFuZE1vbnRoQW5kRGF0ZS5kYXRlKCkpLmhvdXIoaG91cikubWludXRlKG1pbnV0ZSk7XG4gICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgIGNvbnN0IGRhdGVPZk1vbnRoID0gZGF5anMoZGF5LCAnREQnKS50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICBtZWV0aW5nU3RhcnREYXRlT2JqZWN0ID0gbWVldGluZ1N0YXJ0RGF0ZU9iamVjdC5kYXRlKGRhdGVPZk1vbnRoLmRhdGUoKSkuaG91cihob3VyKS5taW51dGUobWludXRlKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfSBlbHNlIGlmICh0aW1lKSB7XG4gICAgICAgICAgICBpZiAoeWVhciAmJiBtb250aCkge1xuICAgICAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBkYXlqcyhgJHt5ZWFyfS0ke21vbnRofS0ke2RheX0gJHt0aW1lfWAsICdZWVlZLU1NLUREIEhIOm1tJykudHoodGltZXpvbmUsIHRydWUpO1xuICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICBtZWV0aW5nU3RhcnREYXRlT2JqZWN0ID0gZGF5anMoYCR7ZGF5fSAke3RpbWV9YCwgJ0REIEhIOm1tJykudHoodGltZXpvbmUsIHRydWUpO1xuICAgICAgICAgICAgfVxuICAgICAgICB9IGVsc2UgaWYgKCF0aW1lICYmICFob3VyICYmICFtaW51dGUpIHsgLy8gQWxsIGRheSBldmVudCwgc3RhcnQgYXQgMDA6MDBcbiAgICAgICAgICAgIGlmICh5ZWFyICYmIG1vbnRoKSB7XG4gICAgICAgICAgICAgICAgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdCA9IGRheWpzKGAke3llYXJ9LSR7bW9udGh9LSR7ZGF5fWAsICdZWVlZLU1NLUREJykudHoodGltZXpvbmUsIHRydWUpLmhvdXIoMCkubWludXRlKDApO1xuICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICBtZWV0aW5nU3RhcnREYXRlT2JqZWN0ID0gZGF5anMoZGF5LCAnREQnKS50eih0aW1lem9uZSwgdHJ1ZSkuaG91cigwKS5taW51dGUoMCk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5kZWJ1ZyhgWyR7ZnVuY3Rpb25OYW1lfV0gRGF5IHNwZWNpZmllZCwgbm8gdGltZSAtIHNldHRpbmcgdG8gMDA6MDBgLCB7IG1lZXRpbmdTdGFydERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdTdGFydERhdGVPYmplY3QuZm9ybWF0KCkgfSk7XG4gICAgICAgIH1cbiAgICB9IGVsc2UgaWYgKGlzb1dlZWtkYXkpIHtcbiAgICAgICAgY29uc3QgZ2l2ZW5JU09EYXkgPSBpc29XZWVrZGF5O1xuICAgICAgICBjb25zdCBjdXJyZW50SVNPRGF5ID0gZ2V0SVNPRGF5KGRheWpzKGN1cnJlbnRUaW1lKS50eih0aW1lem9uZSwgdHJ1ZSkudG9EYXRlKCkpO1xuICAgICAgICBsZXQgYmFzZURhdGVPYmo6IERheWpzO1xuXG4gICAgICAgIGlmICgoISFob3VyKSAmJiAoISFtaW51dGUpKSB7XG4gICAgICAgICAgICBiYXNlRGF0ZU9iaiA9IHllYXIgJiYgbW9udGggPyBkYXlqcyhgJHt5ZWFyfS0ke21vbnRofWAsICdZWVlZLU1NJykudHoodGltZXpvbmUsIHRydWUpIDogZGF5anMoKS50eih0aW1lem9uZSwgdHJ1ZSk7XG4gICAgICAgICAgICBiYXNlRGF0ZU9iaiA9IGJhc2VEYXRlT2JqLmhvdXIoaG91cikubWludXRlKG1pbnV0ZSk7XG4gICAgICAgIH0gZWxzZSBpZiAodGltZSkge1xuICAgICAgICAgICAgYmFzZURhdGVPYmogPSB5ZWFyICYmIG1vbnRoID8gZGF5anMoYCR7eWVhcn0tJHttb250aH0gJHt0aW1lfWAsICdZWVlZLU1NIEhIOm1tJykudHoodGltZXpvbmUsIHRydWUpIDogZGF5anModGltZSwgJ0hIOm1tJykudHoodGltZXpvbmUsIHRydWUpO1xuICAgICAgICB9IGVsc2UgeyAvLyBBbGwgZGF5IGZvciBpc29XZWVrZGF5LCBzdGFydCBhdCAwMDowMFxuICAgICAgICAgICAgYmFzZURhdGVPYmogPSB5ZWFyICYmIG1vbnRoID8gZGF5anMoYCR7eWVhcn0tJHttb250aH1gLCAnWVlZWS1NTScpLnR6KHRpbWV6b25lLCB0cnVlKSA6IGRheWpzKCkudHoodGltZXpvbmUsIHRydWUpO1xuICAgICAgICAgICAgYmFzZURhdGVPYmogPSBiYXNlRGF0ZU9iai5ob3VyKDApLm1pbnV0ZSgwKTtcbiAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoYFske2Z1bmN0aW9uTmFtZX1dIElTTyBXZWVrZGF5IHNwZWNpZmllZCwgbm8gdGltZSAtIHNldHRpbmcgdG8gMDA6MDAgZm9yIGJhc2VgLCB7IGJhc2VEYXRlT2JqRm9ybWF0dGVkOiBiYXNlRGF0ZU9iai5mb3JtYXQoKSB9KTtcbiAgICAgICAgfVxuXG4gICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBnaXZlbklTT0RheSA8IGN1cnJlbnRJU09EYXkgPyBkYXlqcyhzZXRJU09EYXkoYmFzZURhdGVPYmouYWRkKDEsICd3JykudG9EYXRlKCksIGdpdmVuSVNPRGF5KSkgOiBkYXlqcyhzZXRJU09EYXkoYmFzZURhdGVPYmoudG9EYXRlKCksIGdpdmVuSVNPRGF5KSk7XG5cbiAgICB9IGVsc2UgaWYgKHJlbGF0aXZlVGltZUZyb21Ob3c/LlswXSkge1xuICAgICAgICBsZXQgbWludXRlQ2hhbmdlZCA9IGZhbHNlLCBob3VyQ2hhbmdlZCA9IGZhbHNlO1xuICAgICAgICBsZXQgY2FsY3VsYXRlZE1pbnV0ZSA9IDAsIGNhbGN1bGF0ZWRIb3VyID0gMCwgY2FsY3VsYXRlZERheSA9IDAsIGNhbGN1bGF0ZWRXZWVrID0gMCwgY2FsY3VsYXRlZE1vbnRoID0gMCwgY2FsY3VsYXRlZFllYXIgPSAwO1xuXG4gICAgICAgIGZvciAoY29uc3QgcmVsYXRpdmVUaW1lT2JqZWN0IG9mIHJlbGF0aXZlVGltZUZyb21Ob3cpIHtcbiAgICAgICAgICAgICBpZiAocmVsYXRpdmVUaW1lT2JqZWN0Py52YWx1ZSA+IDApIHtcbiAgICAgICAgICAgICAgICBzd2l0Y2ggKHJlbGF0aXZlVGltZU9iamVjdC51bml0KSB7XG4gICAgICAgICAgICAgICAgICAgIGNhc2UgJ21pbnV0ZSc6IGNhbGN1bGF0ZWRNaW51dGUgKz0gcmVsYXRpdmVUaW1lT2JqZWN0LnZhbHVlOyBtaW51dGVDaGFuZ2VkID0gdHJ1ZTsgYnJlYWs7XG4gICAgICAgICAgICAgICAgICAgIGNhc2UgJ2hvdXInOiBjYWxjdWxhdGVkSG91ciArPSByZWxhdGl2ZVRpbWVPYmplY3QudmFsdWU7IGhvdXJDaGFuZ2VkID0gdHJ1ZTsgYnJlYWs7XG4gICAgICAgICAgICAgICAgICAgIGNhc2UgJ2RheSc6IGNhbGN1bGF0ZWREYXkgKz0gcmVsYXRpdmVUaW1lT2JqZWN0LnZhbHVlOyBicmVhaztcbiAgICAgICAgICAgICAgICAgICAgY2FzZSAnd2Vlayc6IGNhbGN1bGF0ZWRXZWVrICs9IHJlbGF0aXZlVGltZU9iamVjdC52YWx1ZTsgYnJlYWs7XG4gICAgICAgICAgICAgICAgICAgIGNhc2UgJ21vbnRoJzogY2FsY3VsYXRlZE1vbnRoICs9IHJlbGF0aXZlVGltZU9iamVjdC52YWx1ZTsgYnJlYWs7XG4gICAgICAgICAgICAgICAgICAgIGNhc2UgJ3llYXInOiBjYWxjdWxhdGVkWWVhciArPSByZWxhdGl2ZVRpbWVPYmplY3QudmFsdWU7IGJyZWFrO1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IGJhc2VDdXJyZW50VGltZSA9IGRheWpzKGN1cnJlbnRUaW1lLCAnWVlZWS1NTS1ERFRISDptbScpLnR6KHRpbWV6b25lLCB0cnVlKTsgLy8gRW5zdXJlIHdlIHVzZSBmdWxsIGN1cnJlbnQgdGltZSBmb3Igc3VidHJhY3Rpb25zXG5cbiAgICAgICAgaWYgKChyZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93ID09PSAnYWRkJykgfHwgKHJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3cgPT09IG51bGwpKSB7XG4gICAgICAgICAgICBtZWV0aW5nU3RhcnREYXRlT2JqZWN0ID0gYmFzZUN1cnJlbnRUaW1lXG4gICAgICAgICAgICAgICAgLmFkZChjYWxjdWxhdGVkTWludXRlLCAnbScpLmFkZChjYWxjdWxhdGVkSG91ciwgJ2gnKVxuICAgICAgICAgICAgICAgIC5hZGQoY2FsY3VsYXRlZERheSwgJ2QnKS5hZGQoY2FsY3VsYXRlZFdlZWssICd3JylcbiAgICAgICAgICAgICAgICAuYWRkKGNhbGN1bGF0ZWRNb250aCwgJ00nKS5hZGQoY2FsY3VsYXRlZFllYXIsICd5Jyk7XG4gICAgICAgIH0gZWxzZSBpZiAocmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyA9PT0gJ3N1YnRyYWN0Jykge1xuICAgICAgICAgICAgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdCA9IGJhc2VDdXJyZW50VGltZVxuICAgICAgICAgICAgICAgIC5zdWJ0cmFjdChjYWxjdWxhdGVkTWludXRlLCAnbScpLnN1YnRyYWN0KGNhbGN1bGF0ZWRIb3VyLCAnaCcpXG4gICAgICAgICAgICAgICAgLnN1YnRyYWN0KGNhbGN1bGF0ZWREYXksICdkJykuc3VidHJhY3QoY2FsY3VsYXRlZFdlZWssICd3JylcbiAgICAgICAgICAgICAgICAuc3VidHJhY3QoY2FsY3VsYXRlZE1vbnRoLCAnTScpLnN1YnRyYWN0KGNhbGN1bGF0ZWRZZWFyLCAneScpO1xuICAgICAgICB9XG5cbiAgICAgICAgaWYgKCghIWhvdXIpICYmICghIW1pbnV0ZSkpIHtcbiAgICAgICAgICAgIGlmICh5ZWFyICYmIG1vbnRoKSBtZWV0aW5nU3RhcnREYXRlT2JqZWN0ID0gbWVldGluZ1N0YXJ0RGF0ZU9iamVjdC55ZWFyKGRheWpzKGAke3llYXJ9LSR7bW9udGh9YCwgJ1lZWVktTU0nKS55ZWFyKCkpLm1vbnRoKGRheWpzKGAke3llYXJ9LSR7bW9udGh9YCwgJ1lZWVktTU0nKS5tb250aCgpKTtcbiAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBtZWV0aW5nU3RhcnREYXRlT2JqZWN0LmhvdXIoaG91cikubWludXRlKG1pbnV0ZSk7XG4gICAgICAgIH0gZWxzZSBpZiAodGltZSkge1xuICAgICAgICAgICAgY29uc3QgdGVtcFRpbWUgPSBkYXlqcyh0aW1lLCAnSEg6bW0nKS50eih0aW1lem9uZSwgdHJ1ZSk7XG4gICAgICAgICAgICBpZiAoeWVhciAmJiBtb250aCkgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdCA9IG1lZXRpbmdTdGFydERhdGVPYmplY3QueWVhcihkYXlqcyhgJHt5ZWFyfS0ke21vbnRofWAsICdZWVlZLU1NJykueWVhcigpKS5tb250aChkYXlqcyhgJHt5ZWFyfS0ke21vbnRofWAsICdZWVlZLU1NJykubW9udGgoKSk7XG4gICAgICAgICAgICBtZWV0aW5nU3RhcnREYXRlT2JqZWN0ID0gbWVldGluZ1N0YXJ0RGF0ZU9iamVjdC5ob3VyKHRlbXBUaW1lLmhvdXIoKSkubWludXRlKHRlbXBUaW1lLm1pbnV0ZSgpKTtcbiAgICAgICAgfSBlbHNlIGlmICghaG91ckNoYW5nZWQgJiYgIW1pbnV0ZUNoYW5nZWQpIHsgLy8gTm8gcmVsYXRpdmUgdGltZSBwYXJ0cywgbm8gZXhwbGljaXQgdGltZSBwYXJ0cyAtPiBzZXQgdG8gMDA6MDBcbiAgICAgICAgICAgIGlmICh5ZWFyICYmIG1vbnRoKSBtZWV0aW5nU3RhcnREYXRlT2JqZWN0ID0gbWVldGluZ1N0YXJ0RGF0ZU9iamVjdC55ZWFyKGRheWpzKGAke3llYXJ9LSR7bW9udGh9YCwgJ1lZWVktTU0nKS55ZWFyKCkpLm1vbnRoKGRheWpzKGAke3llYXJ9LSR7bW9udGh9YCwgJ1lZWVktTU0nKS5tb250aCgpKTtcbiAgICAgICAgICAgIG1lZXRpbmdTdGFydERhdGVPYmplY3QgPSBtZWV0aW5nU3RhcnREYXRlT2JqZWN0LmhvdXIoMCkubWludXRlKDApO1xuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5kZWJ1ZyhgWyR7ZnVuY3Rpb25OYW1lfV0gUmVsYXRpdmUgZGF5L3dlZWsvbW9udGgveWVhciwgbm8gdGltZSBwYXJ0cyAtIHNldHRpbmcgdG8gMDA6MDBgLCB7IG1lZXRpbmdTdGFydERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdTdGFydERhdGVPYmplY3QuZm9ybWF0KCkgfSk7XG4gICAgICAgIH1cbiAgICB9XG5cbiAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBGaW5hbCBtZWV0aW5nU3RhcnREYXRlT2JqZWN0OmAsIHsgbWVldGluZ1N0YXJ0RGF0ZU9iamVjdEZvcm1hdHRlZDogbWVldGluZ1N0YXJ0RGF0ZU9iamVjdC5mb3JtYXQoKSB9KTtcbiAgICBtZWV0aW5nU3RhcnREYXRlID0gKG1lZXRpbmdTdGFydERhdGVPYmplY3QgYXMgRGF5anMpLmZvcm1hdCgpXG4gICAgcmV0dXJuIG1lZXRpbmdTdGFydERhdGVcbn1cblxuZXhwb3J0IGNvbnN0IGV4dHJhcG9sYXRlRW5kRGF0ZUZyb21KU09ORGF0YSA9IChcbiAgICBjdXJyZW50VGltZTogc3RyaW5nLFxuICAgIHRpbWV6b25lOiBzdHJpbmcsXG4gICAgeWVhcjogc3RyaW5nIHwgbnVsbCB8IHVuZGVmaW5lZCxcbiAgICBtb250aDogc3RyaW5nIHwgbnVsbCB8IHVuZGVmaW5lZCxcbiAgICBkYXk6IHN0cmluZyB8IG51bGwgfCB1bmRlZmluZWQsXG4gICAgaXNvV2Vla2RheTogbnVtYmVyIHwgbnVsbCB8IHVuZGVmaW5lZCxcbiAgICBob3VyOiBudW1iZXIgfCBudWxsIHwgdW5kZWZpbmVkLFxuICAgIG1pbnV0ZTogbnVtYmVyIHwgbnVsbCB8IHVuZGVmaW5lZCxcbiAgICB0aW1lOiBUaW1lIHwgbnVsbCB8IHVuZGVmaW5lZCxcbiAgICByZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93OiBSZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93VHlwZSB8IG51bGwgfCB1bmRlZmluZWQsXG4gICAgcmVsYXRpdmVUaW1lRnJvbU5vdzogUmVsYXRpdmVUaW1lRnJvbU5vd1R5cGVbXSB8IG51bGwgfCB1bmRlZmluZWQsXG4pID0+IHtcbiAgICAvLyBUaGlzIGZ1bmN0aW9uIGlzIHZlcnkgc2ltaWxhciB0byBleHRyYXBvbGF0ZURhdGVGcm9tSlNPTkRhdGEsIGJ1dCBzZXRzIHRpbWUgdG8gMjM6NTkgaWYgbm90IHNwZWNpZmllZC5cbiAgICBsZXQgbWVldGluZ0VuZERhdGUgPSAnJ1xuICAgIGxldCBtZWV0aW5nRW5kRGF0ZU9iamVjdDogRGF5anMgPSBkYXlqcyhjdXJyZW50VGltZSwgJ1lZWVktTU0tRERUSEg6bW0nKS50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICBjb25zdCBmdW5jdGlvbk5hbWUgPSAnZXh0cmFwb2xhdGVFbmREYXRlRnJvbUpTT05EYXRhJztcblxuICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoYFske2Z1bmN0aW9uTmFtZX1dIEluaXRpYWwgcGFyYW1zOmAsIHsgY3VycmVudFRpbWUsIHRpbWV6b25lLCB5ZWFyLCBtb250aCwgZGF5LCBpc29XZWVrZGF5LCBob3VyLCBtaW51dGUsIHRpbWUsIHJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csIHJlbGF0aXZlVGltZUZyb21Ob3cgfSk7XG5cbiAgICBpZiAoZGF5KSB7XG4gICAgICAgIGlmICgoISFob3VyKSAmJiAoISFtaW51dGUpKSB7XG4gICAgICAgICAgICBpZiAoeWVhciAmJiBtb250aCkge1xuICAgICAgICAgICAgICAgIGNvbnN0IHllYXJBbmRNb250aEFuZERhdGUgPSBkYXlqcyhgJHt5ZWFyfS0ke21vbnRofS0ke2RheX1gLCAnWVlZWS1NTS1ERCcpLnR6KHRpbWV6b25lLCB0cnVlKTtcbiAgICAgICAgICAgICAgICBtZWV0aW5nRW5kRGF0ZU9iamVjdCA9IG1lZXRpbmdFbmREYXRlT2JqZWN0LnllYXIoeWVhckFuZE1vbnRoQW5kRGF0ZS55ZWFyKCkpLm1vbnRoKHllYXJBbmRNb250aEFuZERhdGUubW9udGgoKSkuZGF0ZSh5ZWFyQW5kTW9udGhBbmREYXRlLmRhdGUoKSkuaG91cihob3VyKS5taW51dGUobWludXRlKTtcbiAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgY29uc3QgZGF0ZU9mTW9udGggPSBkYXlqcyhkYXksICdERCcpLnR6KHRpbWV6b25lLCB0cnVlKTtcbiAgICAgICAgICAgICAgICBtZWV0aW5nRW5kRGF0ZU9iamVjdCA9IG1lZXRpbmdFbmREYXRlT2JqZWN0LmRhdGUoZGF0ZU9mTW9udGguZGF0ZSgpKS5ob3VyKGhvdXIpLm1pbnV0ZShtaW51dGUpO1xuICAgICAgICAgICAgfVxuICAgICAgICB9IGVsc2UgaWYgKHRpbWUpIHtcbiAgICAgICAgICAgICBpZiAoeWVhciAmJiBtb250aCkge1xuICAgICAgICAgICAgICAgIG1lZXRpbmdFbmREYXRlT2JqZWN0ID0gZGF5anMoYCR7eWVhcn0tJHttb250aH0tJHtkYXl9ICR7dGltZX1gLCAnWVlZWS1NTS1ERCBISDptbScpLnR6KHRpbWV6b25lLCB0cnVlKTtcbiAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgbWVldGluZ0VuZERhdGVPYmplY3QgPSBkYXlqcyhgJHtkYXl9ICR7dGltZX1gLCAnREQgSEg6bW0nKS50eih0aW1lem9uZSwgdHJ1ZSk7XG4gICAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSBpZiAoIXRpbWUgJiYgIWhvdXIgJiYgIW1pbnV0ZSkgeyAvLyBBbGwgZGF5IGV2ZW50LCBlbmQgYXQgMjM6NTlcbiAgICAgICAgICAgIGlmICh5ZWFyICYmIG1vbnRoKSB7XG4gICAgICAgICAgICAgICAgbWVldGluZ0VuZERhdGVPYmplY3QgPSBkYXlqcyhgJHt5ZWFyfS0ke21vbnRofS0ke2RheX1gLCAnWVlZWS1NTS1ERCcpLnR6KHRpbWV6b25lLCB0cnVlKS5ob3VyKDIzKS5taW51dGUoNTkpO1xuICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgICBtZWV0aW5nRW5kRGF0ZU9iamVjdCA9IGRheWpzKGRheSwgJ0REJykudHoodGltZXpvbmUsIHRydWUpLmhvdXIoMjMpLm1pbnV0ZSg1OSk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBEYXkgc3BlY2lmaWVkLCBubyB0aW1lIC0gc2V0dGluZyB0byAyMzo1OWAsIHsgbWVldGluZ0VuZERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdFbmREYXRlT2JqZWN0LmZvcm1hdCgpIH0pO1xuICAgICAgICB9XG4gICAgfSBlbHNlIGlmIChpc29XZWVrZGF5KSB7XG4gICAgICAgIGNvbnN0IGdpdmVuSVNPRGF5ID0gaXNvV2Vla2RheTtcbiAgICAgICAgY29uc3QgY3VycmVudElTT0RheSA9IGdldElTT0RheShkYXlqcyhjdXJyZW50VGltZSkudHoodGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpKTtcbiAgICAgICAgbGV0IGJhc2VEYXRlT2JqOiBEYXlqcztcblxuICAgICAgICBpZiAoKCEhaG91cikgJiYgKCEhbWludXRlKSkge1xuICAgICAgICAgICAgYmFzZURhdGVPYmogPSB5ZWFyICYmIG1vbnRoID8gZGF5anMoYCR7eWVhcn0tJHttb250aH1gLCAnWVlZWS1NTScpLnR6KHRpbWV6b25lLCB0cnVlKSA6IGRheWpzKCkudHoodGltZXpvbmUsIHRydWUpO1xuICAgICAgICAgICAgYmFzZURhdGVPYmogPSBiYXNlRGF0ZU9iai5ob3VyKGhvdXIpLm1pbnV0ZShtaW51dGUpO1xuICAgICAgICB9IGVsc2UgaWYgKHRpbWUpIHtcbiAgICAgICAgICAgIGJhc2VEYXRlT2JqID0geWVhciAmJiBtb250aCA/IGRheWpzKGAke3llYXJ9LSR7bW9udGh9ICR7dGltZX1gLCAnWVlZWS1NTSBISDptbScpLnR6KHRpbWV6b25lLCB0cnVlKSA6IGRheWpzKHRpbWUsICdISDptbScpLnR6KHRpbWV6b25lLCB0cnVlKTtcbiAgICAgICAgfSBlbHNlIHsgLy8gQWxsIGRheSBmb3IgaXNvV2Vla2RheSwgZW5kIGF0IDIzOjU5XG4gICAgICAgICAgICBiYXNlRGF0ZU9iaiA9IHllYXIgJiYgbW9udGggPyBkYXlqcyhgJHt5ZWFyfS0ke21vbnRofWAsICdZWVlZLU1NJykudHoodGltZXpvbmUsIHRydWUpIDogZGF5anMoKS50eih0aW1lem9uZSwgdHJ1ZSk7XG4gICAgICAgICAgICBiYXNlRGF0ZU9iaiA9IGJhc2VEYXRlT2JqLmhvdXIoMjMpLm1pbnV0ZSg1OSk7XG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBJU08gV2Vla2RheSBzcGVjaWZpZWQsIG5vIHRpbWUgLSBzZXR0aW5nIHRvIDIzOjU5IGZvciBiYXNlYCwgeyBiYXNlRGF0ZU9iakZvcm1hdHRlZDogYmFzZURhdGVPYmouZm9ybWF0KCkgfSk7XG4gICAgICAgIH1cblxuICAgICAgICBtZWV0aW5nRW5kRGF0ZU9iamVjdCA9IGdpdmVuSVNPRGF5IDwgY3VycmVudElTT0RheSA/IGRheWpzKHNldElTT0RheShiYXNlRGF0ZU9iai5hZGQoMSwgJ3cnKS50b0RhdGUoKSwgZ2l2ZW5JU09EYXkpKSA6IGRheWpzKHNldElTT0RheShiYXNlRGF0ZU9iai50b0RhdGUoKSwgZ2l2ZW5JU09EYXkpKTtcblxuICAgIH1cbiAgICAvLyBUaGlzICdlbHNlIGlmJyB3YXMgaW5jb3JyZWN0bHkgcGxhY2VkIGluc2lkZSB0aGUgaXNvV2Vla2RheSBibG9jayBpbiB0aGUgb3JpZ2luYWwuIEl0IHNob3VsZCBiZSBhdCB0aGUgc2FtZSBsZXZlbC5cbiAgICAvLyBBc3N1bWluZyBpdCdzIGludGVuZGVkIHRvIGJlIGFuIGFsdGVybmF0aXZlIHRvICdkYXknIGFuZCAnaXNvV2Vla2RheScgZm9yIHRoZSBtYWluIGRhdGUgY2FsY3VsYXRpb24uXG4gICAgLy8gSG93ZXZlciwgdGhlIGxvZ2ljIGZvciByZWxhdGl2ZVRpbWVGcm9tTm93IGluIHRoZSBvcmlnaW5hbCBmdW5jdGlvbiBmb3IgZXh0cmFwb2xhdGVFbmREYXRlRnJvbUpTT05EYXRhICphZGRzKiB0byB0aGUgKmFscmVhZHkgY2FsY3VsYXRlZCogbWVldGluZ0VuZERhdGVPYmplY3QuXG4gICAgLy8gVGhpcyBpcyBkaWZmZXJlbnQgZnJvbSBob3cgZXh0cmFwb2xhdGVEYXRlRnJvbUpTT05EYXRhIGhhbmRsZXMgaXQgKHdoZXJlIGl0J3MgYW4gYWx0ZXJuYXRpdmUgaW5pdGlhbCBjYWxjdWxhdGlvbiBwYXRoKS5cbiAgICAvLyBSZXBsaWNhdGluZyB0aGUgb3JpZ2luYWwgYmVoYXZpb3IgZm9yIGV4dHJhcG9sYXRlRW5kRGF0ZUZyb21KU09ORGF0YTpcblxuICAgIGlmIChyZWxhdGl2ZVRpbWVGcm9tTm93Py5bMF0pIHsgLy8gVGhpcyBhcHBsaWVzICphZnRlciogZGF5L2lzb1dlZWtkYXkgbG9naWMgaWYgYW55XG4gICAgICAgIGxldCBtaW51dGVDaGFuZ2VkID0gZmFsc2UsIGhvdXJDaGFuZ2VkID0gZmFsc2U7XG4gICAgICAgIGxldCBjYWxjdWxhdGVkTWludXRlID0gMCwgY2FsY3VsYXRlZEhvdXIgPSAwLCBjYWxjdWxhdGVkRGF5ID0gMCwgY2FsY3VsYXRlZFdlZWsgPSAwLCBjYWxjdWxhdGVkTW9udGggPSAwLCBjYWxjdWxhdGVkWWVhciA9IDA7XG5cbiAgICAgICAgZm9yIChjb25zdCByZWxhdGl2ZVRpbWVPYmplY3Qgb2YgcmVsYXRpdmVUaW1lRnJvbU5vdykge1xuICAgICAgICAgICAgaWYgKHJlbGF0aXZlVGltZU9iamVjdD8udmFsdWUgPiAwKSB7XG4gICAgICAgICAgICAgICAgc3dpdGNoIChyZWxhdGl2ZVRpbWVPYmplY3QudW5pdCkge1xuICAgICAgICAgICAgICAgICAgICBjYXNlICdtaW51dGUnOiBjYWxjdWxhdGVkTWludXRlICs9IHJlbGF0aXZlVGltZU9iamVjdC52YWx1ZTsgbWludXRlQ2hhbmdlZCA9IHRydWU7IGJyZWFrO1xuICAgICAgICAgICAgICAgICAgICBjYXNlICdob3VyJzogY2FsY3VsYXRlZEhvdXIgKz0gcmVsYXRpdmVUaW1lT2JqZWN0LnZhbHVlOyBob3VyQ2hhbmdlZCA9IHRydWU7IGJyZWFrO1xuICAgICAgICAgICAgICAgICAgICBjYXNlICdkYXknOiBjYWxjdWxhdGVkRGF5ICs9IHJlbGF0aXZlVGltZU9iamVjdC52YWx1ZTsgYnJlYWs7XG4gICAgICAgICAgICAgICAgICAgIGNhc2UgJ3dlZWsnOiBjYWxjdWxhdGVkV2VlayArPSByZWxhdGl2ZVRpbWVPYmplY3QudmFsdWU7IGJyZWFrO1xuICAgICAgICAgICAgICAgICAgICBjYXNlICdtb250aCc6IGNhbGN1bGF0ZWRNb250aCArPSByZWxhdGl2ZVRpbWVPYmplY3QudmFsdWU7IGJyZWFrO1xuICAgICAgICAgICAgICAgICAgICBjYXNlICd5ZWFyJzogY2FsY3VsYXRlZFllYXIgKz0gcmVsYXRpdmVUaW1lT2JqZWN0LnZhbHVlOyBicmVhaztcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5kZWJ1ZyhgWyR7ZnVuY3Rpb25OYW1lfV0gQXBwbHlpbmcgcmVsYXRpdmVUaW1lRnJvbU5vdyBhZGp1c3RtZW50czpgLCB7IGNhbGN1bGF0ZWRNaW51dGUsIGNhbGN1bGF0ZWRIb3VyLCBjYWxjdWxhdGVkRGF5LCBjYWxjdWxhdGVkV2VlaywgY2FsY3VsYXRlZE1vbnRoLCBjYWxjdWxhdGVkWWVhciwgcmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyB9KTtcblxuICAgICAgICBpZiAoKHJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3cgPT09ICdhZGQnKSB8fCAocmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyA9PT0gbnVsbCkpIHtcbiAgICAgICAgICAgIG1lZXRpbmdFbmREYXRlT2JqZWN0ID0gbWVldGluZ0VuZERhdGVPYmplY3RcbiAgICAgICAgICAgICAgICAuYWRkKGNhbGN1bGF0ZWRNaW51dGUsICdtJykuYWRkKGNhbGN1bGF0ZWRIb3VyLCAnaCcpXG4gICAgICAgICAgICAgICAgLmFkZChjYWxjdWxhdGVkRGF5LCAnZCcpLmFkZChjYWxjdWxhdGVkV2VlaywgJ3cnKVxuICAgICAgICAgICAgICAgIC5hZGQoY2FsY3VsYXRlZE1vbnRoLCAnTScpLmFkZChjYWxjdWxhdGVkWWVhciwgJ3knKTtcbiAgICAgICAgfSBlbHNlIGlmIChyZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93ID09PSAnc3VidHJhY3QnKSB7XG4gICAgICAgICAgICBtZWV0aW5nRW5kRGF0ZU9iamVjdCA9IG1lZXRpbmdFbmREYXRlT2JqZWN0XG4gICAgICAgICAgICAgICAgLnN1YnRyYWN0KGNhbGN1bGF0ZWRNaW51dGUsICdtJykuc3VidHJhY3QoY2FsY3VsYXRlZEhvdXIsICdoJylcbiAgICAgICAgICAgICAgICAuc3VidHJhY3QoY2FsY3VsYXRlZERheSwgJ2QnKS5zdWJ0cmFjdChjYWxjdWxhdGVkV2VlaywgJ3cnKVxuICAgICAgICAgICAgICAgIC5zdWJ0cmFjdChjYWxjdWxhdGVkTW9udGgsICdNJykuc3VidHJhY3QoY2FsY3VsYXRlZFllYXIsICd5Jyk7XG4gICAgICAgIH1cblxuICAgICAgICAvLyBJZiBleHBsaWNpdCBob3VyL21pbnV0ZS90aW1lIGFyZSBnaXZlbiwgdGhleSBtaWdodCBvdmVycmlkZSB0aGUgdGltZSBwYXJ0IG9mIHJlbGF0aXZlIGNhbGN1bGF0aW9uIG9yIGFkanVzdCB0aGUgZXhpc3Rpbmcgb25lLlxuICAgICAgICAvLyBUaGUgb3JpZ2luYWwgbG9naWMgZm9yIEVuZERhdGUgZGlkbid0IHNlZW0gdG8gcmUtYXBwbHkgZXhwbGljaXQgaG91ci9taW51dGUgaWYgcmVsYXRpdmUgdGltZSB3YXMgYWxzbyBnaXZlbixcbiAgICAgICAgLy8gdW5sZXNzIGl0IHdhcyB0byBzZXQgdG8gMjM6NTkgaWYgbm8gdGltZSBwYXJ0cyB3ZXJlIGNoYW5nZWQgYnkgcmVsYXRpdmVUaW1lIGFuZCBubyBleHBsaWNpdCB0aW1lLlxuICAgICAgICAvLyBUaGlzIHBhcnQgaXMgdHJpY2t5IHRvIHJlcGxpY2F0ZSBwZXJmZWN0bHkgd2l0aG91dCBhbWJpZ3VpdHkgZnJvbSBvcmlnaW5hbCBjb25zb2xlIGxvZ3MuXG4gICAgICAgIC8vIFRoZSBwcmltYXJ5IGRpZmZlcmVuY2UgZm9yIEVuZERhdGUgd2FzIHNldHRpbmcgdG8gMjM6NTkgaWYgaXQgd2FzIGFuIFwiYWxsLWRheVwiIHR5cGUgb2YgcmVsYXRpdmUgYWRqdXN0bWVudC5cblxuICAgICAgICBpZiAoKCEhaG91cikgJiYgKCEhbWludXRlKSkgeyAvLyBFeHBsaWNpdCBob3VyL21pbnV0ZSBnaXZlblxuICAgICAgICAgICAgaWYgKHllYXIgJiYgbW9udGgpIG1lZXRpbmdFbmREYXRlT2JqZWN0ID0gbWVldGluZ0VuZERhdGVPYmplY3QueWVhcihkYXlqcyhgJHt5ZWFyfS0ke21vbnRofWAsICdZWVlZLU1NJykueWVhcigpKS5tb250aChkYXlqcyhgJHt5ZWFyfS0ke21vbnRofWAsICdZWVlZLU1NJykubW9udGgoKSk7XG4gICAgICAgICAgICBtZWV0aW5nRW5kRGF0ZU9iamVjdCA9IG1lZXRpbmdFbmREYXRlT2JqZWN0LmhvdXIoaG91cikubWludXRlKG1pbnV0ZSk7XG4gICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5kZWJ1ZyhgWyR7ZnVuY3Rpb25OYW1lfV0gUmVsYXRpdmUgdGltZSBhcHBsaWVkLCB0aGVuIGV4cGxpY2l0IGhvdXIvbWludXRlOmAsIHsgbWVldGluZ0VuZERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdFbmREYXRlT2JqZWN0LmZvcm1hdCgpIH0pO1xuICAgICAgICB9IGVsc2UgaWYgKHRpbWUpIHsgLy8gRXhwbGljaXQgdGltZSBnaXZlblxuICAgICAgICAgICAgY29uc3QgdGVtcFRpbWUgPSBkYXlqcyh0aW1lLCAnSEg6bW0nKS50eih0aW1lem9uZSwgdHJ1ZSk7XG4gICAgICAgICAgICBpZiAoeWVhciAmJiBtb250aCkgbWVldGluZ0VuZERhdGVPYmplY3QgPSBtZWV0aW5nRW5kRGF0ZU9iamVjdC55ZWFyKGRheWpzKGAke3llYXJ9LSR7bW9udGh9YCwgJ1lZWVktTU0nKS55ZWFyKCkpLm1vbnRoKGRheWpzKGAke3llYXJ9LSR7bW9udGh9YCwgJ1lZWVktTU0nKS5tb250aCgpKTtcbiAgICAgICAgICAgIG1lZXRpbmdFbmREYXRlT2JqZWN0ID0gbWVldGluZ0VuZERhdGVPYmplY3QuaG91cih0ZW1wVGltZS5ob3VyKCkpLm1pbnV0ZSh0ZW1wVGltZS5taW51dGUoKSk7XG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtmdW5jdGlvbk5hbWV9XSBSZWxhdGl2ZSB0aW1lIGFwcGxpZWQsIHRoZW4gZXhwbGljaXQgdGltZTpgLCB7IG1lZXRpbmdFbmREYXRlT2JqZWN0Rm9ybWF0dGVkOiBtZWV0aW5nRW5kRGF0ZU9iamVjdC5mb3JtYXQoKSB9KTtcbiAgICAgICAgfSBlbHNlIGlmICghaG91ckNoYW5nZWQgJiYgIW1pbnV0ZUNoYW5nZWQpIHsgLy8gTm8gcmVsYXRpdmUgbWludXRlL2hvdXIgYWRqdXN0bWVudHMsIGFuZCBubyBleHBsaWNpdCB0aW1lL2hvdXIvbWludXRlXG4gICAgICAgICAgICAvLyBUaGlzIGltcGxpZXMgaXQgbWlnaHQgYmUgYW4gXCJhbGwtZGF5XCIgdHlwZSBvZiByZWxhdGl2ZSBhZGp1c3RtZW50IChlLmcuLCBcIm5leHQgd2Vla1wiKVxuICAgICAgICAgICAgLy8gU28sIHNldCB0aW1lIHRvIGVuZCBvZiBkYXkuXG4gICAgICAgICAgICBpZiAoeWVhciAmJiBtb250aCkgbWVldGluZ0VuZERhdGVPYmplY3QgPSBtZWV0aW5nRW5kRGF0ZU9iamVjdC55ZWFyKGRheWpzKGAke3llYXJ9LSR7bW9udGh9YCwgJ1lZWVktTU0nKS55ZWFyKCkpLm1vbnRoKGRheWpzKGAke3llYXJ9LSR7bW9udGh9YCwgJ1lZWVktTU0nKS5tb250aCgpKTtcbiAgICAgICAgICAgIG1lZXRpbmdFbmREYXRlT2JqZWN0ID0gbWVldGluZ0VuZERhdGVPYmplY3QuaG91cigyMykubWludXRlKDU5KTtcbiAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoYFske2Z1bmN0aW9uTmFtZX1dIFJlbGF0aXZlIGRheS93ZWVrL2V0YyBhcHBsaWVkIChubyB0aW1lIHBhcnRzKSwgc2V0dGluZyB0byAyMzo1OTpgLCB7IG1lZXRpbmdFbmREYXRlT2JqZWN0Rm9ybWF0dGVkOiBtZWV0aW5nRW5kRGF0ZU9iamVjdC5mb3JtYXQoKSB9KTtcbiAgICAgICAgfVxuICAgIH1cblxuICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoYFske2Z1bmN0aW9uTmFtZX1dIEZpbmFsIG1lZXRpbmdFbmREYXRlT2JqZWN0OmAsIHsgbWVldGluZ0VuZERhdGVPYmplY3RGb3JtYXR0ZWQ6IG1lZXRpbmdFbmREYXRlT2JqZWN0LmZvcm1hdCgpIH0pO1xuICAgIG1lZXRpbmdFbmREYXRlID0gKG1lZXRpbmdFbmREYXRlT2JqZWN0IGFzIERheWpzKS5mb3JtYXQoKVxuICAgIHJldHVybiBtZWV0aW5nRW5kRGF0ZVxufVxuXG5leHBvcnQgY29uc3QgZ2V0R2xvYmFsQ2FsZW5kYXIgPSBhc3luYyAoXG4gICAgdXNlcklkOiBzdHJpbmcsXG4pID0+IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2dldEdsb2JhbENhbGVuZGFyJzsgLy8gRGVmaW5lZCBvcGVyYXRpb25OYW1lIGZvciBsb2dnaW5nIGFuZCBQb3N0Z3JhcGhpbGUgY2FsbFxuICAgIHRyeSB7XG4gICAgICAgIC8vIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZ2V0R2xvYmFsQ2FsZW5kYXInIC8vIE9yaWdpbmFsIHBvc2l0aW9uLCByZW1vdmVkIGFzIGl0J3MgZGVmaW5lZCBhYm92ZVxuICAgICAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgcXVlcnkgZ2V0R2xvYmFsQ2FsZW5kYXIoJHVzZXJJZDogdXVpZCEpIHtcbiAgICAgICAgICBDYWxlbmRhcih3aGVyZToge2dsb2JhbFByaW1hcnk6IHtfZXE6IHRydWV9LCB1c2VySWQ6IHtfZXE6ICR1c2VySWR9fSkge1xuICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICBhY2Nlc3NMZXZlbFxuICAgICAgICAgICAgYWNjb3VudFxuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGRlZmF1bHRSZW1pbmRlcnNcbiAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgZ2xvYmFsUHJpbWFyeVxuICAgICAgICAgICAgaWRcbiAgICAgICAgICAgIG1vZGlmaWFibGVcbiAgICAgICAgICAgIHByaW1hcnlcbiAgICAgICAgICAgIHJlc291cmNlXG4gICAgICAgICAgICB0aXRsZVxuICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICBgOyAvLyBxdWVyeSByZW1haW5zIHRoZSBzYW1lXG5cbiAgICAgICAgLy8gUmVtb3ZlZCBkaXJlY3QgZ290LnBvc3QgY2FsbCBhbmQgLyogKi8gYmxvY2tcbiAgICAgICAgLy8gY29uc3QgcmVzOiB7IGRhdGE6IHsgQ2FsZW5kYXI6IENhbGVuZGFyVHlwZVtdIH0gfSA9IGF3YWl0IGdvdC5wb3N0KFxuICAgICAgICAvLyAgICAgcG9zdGdyYXBoaWxlR3JhcGhVcmwsXG4gICAgICAgIC8vICAgICB7XG4gICAgICAgIC8vICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAvLyAgICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgIC8vICAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIC8vICAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJ1xuICAgICAgICAvLyAgICAgICAgIH0sXG4gICAgICAgIC8vICAgICAgICAganNvbjoge1xuICAgICAgICAvLyAgICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAvLyAgICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgLy8gICAgICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIC8vICAgICAgICAgICAgICAgICB1c2VySWQsXG4gICAgICAgIC8vICAgICAgICAgICAgIH0sXG4gICAgICAgIC8vICAgICAgICAgfSxcbiAgICAgICAgLy8gICAgIH0sXG4gICAgICAgIC8vICkuanNvbigpXG4gICAgICAgIC8vICovXG5cbiAgICAgICAgLy8gVXNpbmcgcmVzaWxpZW50R290UG9zdFBvc3RncmFwaGlsZSBmb3IgdGhlIFBvc3RncmFwaGlsZSBjYWxsXG4gICAgICAgIC8vIEFzc3VtaW5nICdhZG1pbicgcm9sZSBmb3IgdGhpcyBxdWVyeSBhcyBwZXIgb3JpZ2luYWwgZGlyZWN0IGdvdCBjYWxsLlxuICAgICAgICBjb25zdCByZXNwb25zZURhdGEgPSBhd2FpdCByZXNpbGllbnRHb3RQb3N0UG9zdGdyYXBoaWxlKG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB7IHVzZXJJZCB9IC8qLCB1c2VySWQgKGlmIHVzZXIgcm9sZSBuZWVkZWQpICovKSBhcyB7IENhbGVuZGFyOiBDYWxlbmRhclR5cGVbXSB9O1xuXG4gICAgICAgIGlmIChyZXNwb25zZURhdGEgJiYgcmVzcG9uc2VEYXRhLkNhbGVuZGFyICYmIHJlc3BvbnNlRGF0YS5DYWxlbmRhci5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYCR7b3BlcmF0aW9uTmFtZX0gc3VjY2Vzc2Z1bCBmb3IgdXNlciAke3VzZXJJZH0uIENhbGVuZGFyIElEOiAke3Jlc3BvbnNlRGF0YS5DYWxlbmRhclswXS5pZH1gKTtcbiAgICAgICAgICAgIHJldHVybiByZXNwb25zZURhdGEuQ2FsZW5kYXJbMF07XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYCR7b3BlcmF0aW9uTmFtZX06IE5vIGdsb2JhbCBwcmltYXJ5IGNhbGVuZGFyIGZvdW5kIGZvciB1c2VyICR7dXNlcklkfS5gKTtcbiAgICAgICAgICAgIHJldHVybiB1bmRlZmluZWQ7IC8vIE9yIG51bGwsIGRlcGVuZGluZyBvbiBkZXNpcmVkIGNvbnRyYWN0IGZvciBcIm5vdCBmb3VuZFwiXG4gICAgICAgIH1cbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoYEVycm9yIGluICR7b3BlcmF0aW9uTmFtZX0gZm9yIHVzZXIgJHt1c2VySWR9YCwgeyBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UgfSk7XG4gICAgICAgIC8vIHJlc2lsaWVudEdvdFBvc3RQb3N0Z3JhcGhpbGUgd2lsbCB0aHJvdyBvbiBmYWlsdXJlIGFmdGVyIHJldHJpZXMsIHNvIHRoaXMgY2F0Y2ggYmxvY2sgd2lsbCBoYW5kbGUgdGhhdC5cbiAgICAgICAgdGhyb3cgZTtcbiAgICB9XG59XG5cbmV4cG9ydCBjb25zdCBnZXRDYWxlbmRhckludGVncmF0aW9uQnlSZXNvdXJjZSA9IGFzeW5jIChcbiAgICB1c2VySWQ6IHN0cmluZyxcbiAgICByZXNvdXJjZTogc3RyaW5nLFxuKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRDYWxlbmRhckludGVncmF0aW9uQnlSZXNvdXJjZSdcbiAgICAgICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBxdWVyeSBnZXRDYWxlbmRhckludGVncmF0aW9uQnlSZXNvdXJjZSgkdXNlcklkOiB1dWlkISwgJHJlc291cmNlOiBTdHJpbmchKSB7XG4gICAgICAgIENhbGVuZGFyX0ludGVncmF0aW9uKHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgcmVzb3VyY2U6IHtfZXE6ICRyZXNvdXJjZX19KSB7XG4gICAgICAgICAgdG9rZW5cbiAgICAgICAgICBleHBpcmVzQXRcbiAgICAgICAgICBpZFxuICAgICAgICAgIHJlZnJlc2hUb2tlblxuICAgICAgICAgIHJlc291cmNlXG4gICAgICAgICAgbmFtZVxuICAgICAgICAgIGNsaWVudFR5cGVcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGBcbiAgICAgICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgcmVzb3VyY2UsXG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCByZXM6IHsgZGF0YTogeyBDYWxlbmRhcl9JbnRlZ3JhdGlvbjogQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGVbXSB9IH0gPSBhd2FpdCBnb3QucG9zdChcbiAgICAgICAgICAgIHBvc3RncmFwaGlsZUdyYXBoVXJsLFxuICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgICAgICAgICAgcXVlcnksXG4gICAgICAgICAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbidcbiAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgfSxcbiAgICAgICAgKS5qc29uKClcblxuICAgICAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGluc2lkZSBnZXRDYWxlbmRhckludGVncmF0aW9uJylcbiAgICAgICAgaWYgKHJlcz8uZGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb24/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgIHJldHVybiByZXM/LmRhdGE/LkNhbGVuZGFyX0ludGVncmF0aW9uPy5bMF1cbiAgICAgICAgfVxuICAgICAgICBjb25zdCByZXNwb25zZURhdGEgPSBhd2FpdCByZXNpbGllbnRHb3RQb3N0UG9zdGdyYXBoaWxlKG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB2YXJpYWJsZXMsIHVzZXJJZCkgYXMgeyBDYWxlbmRhcl9JbnRlZ3JhdGlvbjogQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGVbXSB9O1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYGdldENhbGVuZGFySW50ZWdyYXRpb25CeVJlc291cmNlIHJlc3BvbnNlIGZvciB1c2VyICR7dXNlcklkfSwgcmVzb3VyY2UgJHtyZXNvdXJjZX1gLCB7IGRhdGFMZW5ndGg6IHJlc3BvbnNlRGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb24/Lmxlbmd0aCB9KTtcbiAgICAgICAgcmV0dXJuIHJlc3BvbnNlRGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb24/LlswXTtcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoJ0Vycm9yIGluIGdldENhbGVuZGFySW50ZWdyYXRpb25CeVJlc291cmNlJywgeyB1c2VySWQsIHJlc291cmNlLCBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UgfSk7XG4gICAgICAgIHRocm93IGU7XG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZSA9IGFzeW5jIChcbiAgICB1c2VySWQ6IHN0cmluZyxcbiAgICBuYW1lOiBzdHJpbmcsXG4pID0+IHtcbiAgICB0cnkge1xuICAgICAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2dldENhbGVuZGFySW50ZWdyYXRpb25CeU5hbWUnXG4gICAgICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZSgkdXNlcklkOiB1dWlkISwgJG5hbWU6IFN0cmluZyEpIHtcbiAgICAgICAgICAgICAgICBDYWxlbmRhcl9JbnRlZ3JhdGlvbih3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH0sIG5hbWU6IHtfZXE6ICRuYW1lfX0pIHtcbiAgICAgICAgICAgICAgICAgICAgdG9rZW5cbiAgICAgICAgICAgICAgICAgICAgZXhwaXJlc0F0XG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIHJlZnJlc2hUb2tlblxuICAgICAgICAgICAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICAgICAgICAgIGNsaWVudFR5cGVcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGBcbiAgICAgICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgbmFtZSxcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IENhbGVuZGFyX0ludGVncmF0aW9uOiBDYWxlbmRhckludGVncmF0aW9uVHlwZVtdIH0gfSA9IGF3YWl0IGdvdC5wb3N0KFxuICAgICAgICAgICAgcG9zdGdyYXBoaWxlR3JhcGhVcmwsXG4gICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICAgICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJ1xuICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICB9LFxuICAgICAgICApLmpzb24oKVxuXG4gICAgICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgaW5zaWRlIGdldENhbGVuZGFySW50ZWdyYXRpb24nKVxuICAgICAgICBpZiAocmVzPy5kYXRhPy5DYWxlbmRhcl9JbnRlZ3JhdGlvbj8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgcmV0dXJuIHJlcz8uZGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb24/LlswXVxuICAgICAgICB9XG4gICAgICAgIGNvbnN0IHJlc3BvbnNlRGF0YSA9IGF3YWl0IHJlc2lsaWVudEdvdFBvc3RQb3N0Z3JhcGhpbGUob3BlcmF0aW9uTmFtZSwgcXVlcnksIHZhcmlhYmxlcywgdXNlcklkKSBhcyB7IENhbGVuZGFyX0ludGVncmF0aW9uOiBDYWxlbmRhckludGVncmF0aW9uVHlwZVtdIH07XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbyhgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZSByZXNwb25zZSBmb3IgdXNlciAke3VzZXJJZH0sIG5hbWUgJHtuYW1lfWAsIHsgZGF0YUxlbmd0aDogcmVzcG9uc2VEYXRhPy5DYWxlbmRhcl9JbnRlZ3JhdGlvbj8ubGVuZ3RoIH0pO1xuICAgICAgICByZXR1cm4gcmVzcG9uc2VEYXRhPy5DYWxlbmRhcl9JbnRlZ3JhdGlvbj8uWzBdO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZScsIHsgdXNlcklkLCBuYW1lLCBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UgfSk7XG4gICAgICAgIHRocm93IGU7XG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgZ2V0Wm9vbUludGVncmF0aW9uID0gYXN5bmMgKFxuICAgIHVzZXJJZDogc3RyaW5nLFxuKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgY29uc3QgeyBpZCwgdG9rZW4sIGV4cGlyZXNBdCwgcmVmcmVzaFRva2VuIH0gPSBhd2FpdCBnZXRDYWxlbmRhckludGVncmF0aW9uQnlSZXNvdXJjZSh1c2VySWQsIHpvb21SZXNvdXJjZU5hbWUpXG5cbiAgICAgICAgY29uc3QgZGVjcnlwdGVkVG9rZW5zID0gZGVjcnlwdFpvb21Ub2tlbnModG9rZW4sIHJlZnJlc2hUb2tlbilcblxuICAgICAgICByZXR1cm4ge1xuICAgICAgICAgICAgaWQsXG4gICAgICAgICAgICBleHBpcmVzQXQsXG4gICAgICAgICAgICAuLi5kZWNyeXB0ZWRUb2tlbnMsXG4gICAgICAgIH1cblxuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignVW5hYmxlIHRvIGdldCB6b29tIGludGVncmF0aW9uJywgeyB1c2VySWQsIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSwgc3RhY2s6IChlIGFzIEVycm9yKS5zdGFjayB9KTtcbiAgICAgICAgLy8gT3JpZ2luYWwgZnVuY3Rpb24gaW1wbGljaXRseSByZXR1cm5zIHVuZGVmaW5lZCBoZXJlLCBzbyB3ZSdsbCBtYWludGFpbiB0aGF0LlxuICAgICAgICAvLyBEZXBlbmRpbmcgb24gZGVzaXJlZCBzdHJpY3RuZXNzLCBjb3VsZCByZXRocm93IGUuXG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgZGVjcnlwdFpvb21Ub2tlbnMgPSAoXG4gICAgZW5jcnlwdGVkVG9rZW46IHN0cmluZyxcbiAgICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4/OiBzdHJpbmcsXG4pID0+IHtcbiAgICBjb25zdCBpdkJ1ZmZlciA9IEJ1ZmZlci5mcm9tKHpvb21JVkZvclBhc3MsICdiYXNlNjQnKVxuICAgIGNvbnN0IHNhbHRCdWZmZXIgPSBCdWZmZXIuZnJvbSh6b29tU2FsdEZvclBhc3MsICdiYXNlNjQnKVxuXG4gICAgY29uc3Qga2V5ID0gY3J5cHRvLnBia2RmMlN5bmMoem9vbVBhc3NLZXkgYXMgc3RyaW5nLCBzYWx0QnVmZmVyLCAxMDAwMCwgMzIsICdzaGEyNTYnKVxuXG4gICAgY29uc3QgZGVjaXBoZXJUb2tlbiA9IGNyeXB0by5jcmVhdGVEZWNpcGhlcml2KCdhZXMtMjU2LWNiYycsIGtleSwgaXZCdWZmZXIpXG4gICAgbGV0IGRlY3J5cHRlZFRva2VuID0gZGVjaXBoZXJUb2tlbi51cGRhdGUoZW5jcnlwdGVkVG9rZW4sICdiYXNlNjQnLCAndXRmOCcpXG4gICAgZGVjcnlwdGVkVG9rZW4gKz0gZGVjaXBoZXJUb2tlbi5maW5hbCgndXRmOCcpXG5cbiAgICBpZiAoZW5jcnlwdGVkUmVmcmVzaFRva2VuKSB7XG4gICAgICAgIGNvbnN0IGRlY2lwaGVyUmVmcmVzaFRva2VuID0gY3J5cHRvLmNyZWF0ZURlY2lwaGVyaXYoJ2Flcy0yNTYtY2JjJywga2V5LCBpdkJ1ZmZlcilcbiAgICAgICAgbGV0IGRlY3J5cHRlZFJlZnJlc2hUb2tlbiA9IGRlY2lwaGVyUmVmcmVzaFRva2VuLnVwZGF0ZShlbmNyeXB0ZWRSZWZyZXNoVG9rZW4sICdiYXNlNjQnLCAndXRmOCcpXG4gICAgICAgIGRlY3J5cHRlZFJlZnJlc2hUb2tlbiArPSBkZWNpcGhlclJlZnJlc2hUb2tlbi5maW5hbCgndXRmOCcpXG5cbiAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICAgIHRva2VuOiBkZWNyeXB0ZWRUb2tlbixcbiAgICAgICAgICAgIHJlZnJlc2hUb2tlbjogZGVjcnlwdGVkUmVmcmVzaFRva2VuLFxuICAgICAgICB9XG4gICAgfVxuXG4gICAgcmV0dXJuIHtcbiAgICAgICAgdG9rZW46IGRlY3J5cHRlZFRva2VuLFxuICAgIH1cblxufVxuXG5leHBvcnQgY29uc3QgZW5jcnlwdFpvb21Ub2tlbnMgPSAoXG4gICAgdG9rZW46IHN0cmluZyxcbiAgICByZWZyZXNoVG9rZW4/OiBzdHJpbmcsXG4pID0+IHtcbiAgICBjb25zdCBpdkJ1ZmZlciA9IEJ1ZmZlci5mcm9tKHpvb21JVkZvclBhc3MsICdiYXNlNjQnKVxuICAgIGNvbnN0IHNhbHRCdWZmZXIgPSBCdWZmZXIuZnJvbSh6b29tU2FsdEZvclBhc3MsICdiYXNlNjQnKVxuXG4gICAgY29uc3Qga2V5ID0gY3J5cHRvLnBia2RmMlN5bmMoem9vbVBhc3NLZXkgYXMgc3RyaW5nLCBzYWx0QnVmZmVyLCAxMDAwMCwgMzIsICdzaGEyNTYnKVxuICAgIGNvbnN0IGNpcGhlclRva2VuID0gY3J5cHRvLmNyZWF0ZUNpcGhlcml2KCdhZXMtMjU2LWNiYycsIGtleSwgaXZCdWZmZXIpXG4gICAgbGV0IGVuY3J5cHRlZFRva2VuID0gY2lwaGVyVG9rZW4udXBkYXRlKHRva2VuLCAndXRmOCcsICdiYXNlNjQnKTtcbiAgICBlbmNyeXB0ZWRUb2tlbiArPSBjaXBoZXJUb2tlbi5maW5hbCgnYmFzZTY0JylcblxuICAgIGxldCBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4gPSAnJ1xuXG4gICAgaWYgKHJlZnJlc2hUb2tlbikge1xuICAgICAgICBjb25zdCBjaXBoZXJSZWZyZXNoVG9rZW4gPSBjcnlwdG8uY3JlYXRlQ2lwaGVyaXYoJ2Flcy0yNTYtY2JjJywga2V5LCBpdkJ1ZmZlcilcbiAgICAgICAgZW5jcnlwdGVkUmVmcmVzaFRva2VuID0gY2lwaGVyUmVmcmVzaFRva2VuLnVwZGF0ZShyZWZyZXNoVG9rZW4sICd1dGY4JywgJ2Jhc2U2NCcpO1xuICAgICAgICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4gKz0gY2lwaGVyUmVmcmVzaFRva2VuLmZpbmFsKCdiYXNlNjQnKVxuICAgIH1cblxuICAgIGlmIChlbmNyeXB0ZWRSZWZyZXNoVG9rZW4pIHtcbiAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICAgIGVuY3J5cHRlZFRva2VuLFxuICAgICAgICAgICAgZW5jcnlwdGVkUmVmcmVzaFRva2VuXG4gICAgICAgIH1cbiAgICB9IGVsc2Uge1xuICAgICAgICByZXR1cm4geyBlbmNyeXB0ZWRUb2tlbiB9XG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgdXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbiA9IGFzeW5jIChcbiAgICBpZDogc3RyaW5nLFxuICAgIHRva2VuPzogc3RyaW5nLFxuICAgIGV4cGlyZXNJbj86IG51bWJlcixcbiAgICBlbmFibGVkPzogYm9vbGVhbixcbikgPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAndXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbidcbiAgICAgICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgIG11dGF0aW9uIHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24oJGlkOiB1dWlkISwke3Rva2VuICE9PSB1bmRlZmluZWQgPyAnICR0b2tlbjogU3RyaW5nLCcgOiAnJ30ke2V4cGlyZXNJbiAhPT0gdW5kZWZpbmVkID8gJyAkZXhwaXJlc0F0OiB0aW1lc3RhbXB0eiwnIDogJyd9JHtlbmFibGVkICE9PSB1bmRlZmluZWQgPyAnICRlbmFibGVkOiBCb29sZWFuLCcgOiAnJ30pIHtcbiAgICAgICAgICB1cGRhdGVfQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGsocGtfY29sdW1uczoge2lkOiAkaWR9LCBfc2V0OiB7JHt0b2tlbiAhPT0gdW5kZWZpbmVkID8gJ3Rva2VuOiAkdG9rZW4sJyA6ICcnfSR7ZXhwaXJlc0luICE9PSB1bmRlZmluZWQgPyAnIGV4cGlyZXNBdDogJGV4cGlyZXNBdCwnIDogJyd9JHtlbmFibGVkICE9PSB1bmRlZmluZWQgPyAnIGVuYWJsZWQ6ICRlbmFibGVkLCcgOiAnJ319KSB7XG4gICAgICAgICAgICBpZFxuICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgcmVmcmVzaFRva2VuXG4gICAgICAgICAgICB0b2tlblxuICAgICAgICAgICAgY2xpZW50VHlwZVxuICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgIGBcbiAgICAgICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgICAgICAgaWQsXG4gICAgICAgICAgICB0b2tlbixcbiAgICAgICAgICAgIGV4cGlyZXNBdDogZGF5anMoKS5hZGQoZXhwaXJlc0luLCAnc2Vjb25kcycpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICBlbmFibGVkLFxuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgcmVzID0gYXdhaXQgZ290LnBvc3QoXG4gICAgICAgICAgICBwb3N0Z3JhcGhpbGVHcmFwaFVybCxcbiAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBqc29uOiB7XG4gICAgICAgICAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAgICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLVJvbGUnOiAnYWRtaW4nXG4gICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICkuanNvbigpXG4gICAgICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgaW5zaWRlIHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24nKVxuICAgICAgICBhd2FpdCByZXNpbGllbnRHb3RQb3N0UG9zdGdyYXBoaWxlKG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB2YXJpYWJsZXMpOyAvLyBBc3N1bWluZyBhZG1pbiByb2xlIGZvciB1cGRhdGVzXG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbyhgU3VjY2Vzc2Z1bGx5IHVwZGF0ZWQgY2FsZW5kYXIgaW50ZWdyYXRpb24gJHtpZH0uYCk7XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdFcnJvciBpbiB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uJywgeyBpZCwgdG9rZW4sIGV4cGlyZXNJbiwgZW5hYmxlZCwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlIH0pO1xuICAgICAgICB0aHJvdyBlO1xuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IHVwZGF0ZVpvb21JbnRlZ3JhdGlvbiA9IGFzeW5jIChcbiAgICBpZDogc3RyaW5nLFxuICAgIGFjY2Vzc1Rva2VuOiBzdHJpbmcsXG4gICAgZXhwaXJlc0luOiBudW1iZXIsXG4pID0+IHtcbiAgICB0cnkge1xuXG4gICAgICAgIGNvbnN0IHsgZW5jcnlwdGVkVG9rZW4gfSA9IGVuY3J5cHRab29tVG9rZW5zKGFjY2Vzc1Rva2VuKVxuICAgICAgICBhd2FpdCB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uKGlkLCBlbmNyeXB0ZWRUb2tlbiwgZXhwaXJlc0luKVxuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignVW5hYmxlIHRvIHVwZGF0ZSB6b29tIGludGVncmF0aW9uJywgeyBpbnRlZ3JhdGlvbklkOiBpZCwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlLCBzdGFjazogKGUgYXMgRXJyb3IpLnN0YWNrIH0pO1xuICAgICAgICAvLyBPcmlnaW5hbCBmdW5jdGlvbiBpbXBsaWNpdGx5IHJldHVybnMgdW5kZWZpbmVkL3ZvaWQgYW5kIGRvZXMgbm90IHJldGhyb3cuXG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgcmVmcmVzaFpvb21Ub2tlbiA9IGFzeW5jIChcbiAgICByZWZyZXNoVG9rZW46IHN0cmluZyxcbik6IFByb21pc2U8e1xuICAgIGFjY2Vzc190b2tlbjogc3RyaW5nLFxuICAgIHRva2VuX3R5cGU6ICdiZWFyZXInLFxuICAgIHJlZnJlc2hfdG9rZW46IHN0cmluZyxcbiAgICBleHBpcmVzX2luOiBudW1iZXIsXG4gICAgc2NvcGU6IHN0cmluZ1xufT4gPT4ge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAncmVmcmVzaFpvb21Ub2tlbic7XG4gICAgY29uc3QgTUFYX1JFVFJJRVMgPSAzO1xuICAgIGNvbnN0IElOSVRJQUxfVElNRU9VVF9NUyA9IDEwMDAwOyAvLyAxMCBzZWNvbmRzXG4gICAgbGV0IGF0dGVtcHQgPSAwO1xuICAgIGxldCBsYXN0RXJyb3I6IGFueSA9IG51bGw7XG5cbiAgICBjb25zdCByZXF1ZXN0RGF0YSA9IG5ldyBVUkxTZWFyY2hQYXJhbXMoe1xuICAgICAgICByZWZyZXNoX3Rva2VuOiByZWZyZXNoVG9rZW4sXG4gICAgICAgIGdyYW50X3R5cGU6ICdyZWZyZXNoX3Rva2VuJyxcbiAgICB9KS50b1N0cmluZygpO1xuXG4gICAgY29uc3QgYXV0aEhlYWRlciA9IGBCYXNpYyAke0J1ZmZlci5mcm9tKGAke3pvb21DbGllbnRJZH06JHt6b29tQ2xpZW50U2VjcmV0fWApLnRvU3RyaW5nKCdiYXNlNjQnKX1gO1xuXG4gICAgd2hpbGUgKGF0dGVtcHQgPCBNQVhfUkVUUklFUykge1xuICAgICAgICB0cnkge1xuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKGBBdHRlbXB0ICR7YXR0ZW1wdCArIDF9IHRvICR7b3BlcmF0aW9uTmFtZX1gLCB7IHJlZnJlc2hUb2tlblN1YnN0cmluZzogcmVmcmVzaFRva2VuPy5zdWJzdHJpbmcoMCwgMTApIH0pO1xuICAgICAgICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcyh7XG4gICAgICAgICAgICAgICAgbWV0aG9kOiAnUE9TVCcsXG4gICAgICAgICAgICAgICAgdXJsOiBgJHt6b29tQmFzZVRva2VuVXJsfS9vYXV0aC90b2tlbmAsXG4gICAgICAgICAgICAgICAgZGF0YTogcmVxdWVzdERhdGEsXG4gICAgICAgICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL3gtd3d3LWZvcm0tdXJsZW5jb2RlZCcsXG4gICAgICAgICAgICAgICAgICAgICdBdXRob3JpemF0aW9uJzogYXV0aEhlYWRlcixcbiAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgIHRpbWVvdXQ6IElOSVRJQUxfVElNRU9VVF9NUyxcbiAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKGAke29wZXJhdGlvbk5hbWV9IHN1Y2Nlc3NmdWwgb24gYXR0ZW1wdCAke2F0dGVtcHQgKyAxfWApO1xuICAgICAgICAgICAgcmV0dXJuIHJlc3BvbnNlLmRhdGE7XG4gICAgICAgIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICAgICAgICAgIGxhc3RFcnJvciA9IGVycm9yO1xuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci53YXJuKGBBdHRlbXB0ICR7YXR0ZW1wdCArIDF9IGZvciAke29wZXJhdGlvbk5hbWV9IGZhaWxlZC5gLCB7XG4gICAgICAgICAgICAgICAgZXJyb3I6IGVycm9yLm1lc3NhZ2UsXG4gICAgICAgICAgICAgICAgY29kZTogZXJyb3IuY29kZSxcbiAgICAgICAgICAgICAgICBzdGF0dXM6IGVycm9yLnJlc3BvbnNlPy5zdGF0dXNcbiAgICAgICAgICAgIH0pO1xuXG4gICAgICAgICAgICBpZiAoYXhpb3MuaXNBeGlvc0Vycm9yKGVycm9yKSkge1xuICAgICAgICAgICAgICAgIGlmIChlcnJvci5yZXNwb25zZSkge1xuICAgICAgICAgICAgICAgICAgICBjb25zdCBzdGF0dXMgPSBlcnJvci5yZXNwb25zZS5zdGF0dXM7XG4gICAgICAgICAgICAgICAgICAgIGlmIChzdGF0dXMgPCA1MDAgJiYgc3RhdHVzICE9PSA0MjkgJiYgc3RhdHVzICE9PSA0MDgpIHsgLy8gTm9uLXJldHJ5YWJsZSBjbGllbnQgSFRUUCBlcnJvclxuICAgICAgICAgICAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9IGVsc2UgaWYgKGVycm9yLmNvZGUgJiYgIVsnRUNPTk5BQk9SVEVEJywgJ0VUSU1FRE9VVCcsICdFQ09OTlJFU0VUJywgJ0VBRERSSU5VU0UnLCAnRUNPTk5SRUZVU0VEJywgJ0VQSVBFJywgJ0VORVRVTlJFQUNIJywgJ0VBSV9BR0FJTiddLmluY2x1ZGVzKGVycm9yLmNvZGUpKSB7XG4gICAgICAgICAgICAgICAgICAgIGJyZWFrOyAvLyBOb24tcmV0cnlhYmxlIG5ldHdvcmsgb3IgY29uZmlnIGVycm9yXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIHsgLy8gTm9uLWF4aW9zIGVycm9yXG4gICAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgICAgYXR0ZW1wdCsrO1xuICAgICAgICBpZiAoYXR0ZW1wdCA8IE1BWF9SRVRSSUVTKSB7XG4gICAgICAgICAgICBjb25zdCBkZWxheSA9IE1hdGgucG93KDIsIGF0dGVtcHQgLSAxKSAqIDEwMDA7XG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYFdhaXRpbmcgJHtkZWxheX1tcyBiZWZvcmUgJHtvcGVyYXRpb25OYW1lfSByZXRyeSAke2F0dGVtcHQgKyAxfWApO1xuICAgICAgICAgICAgYXdhaXQgbmV3IFByb21pc2UocmVzb2x2ZSA9PiBzZXRUaW1lb3V0KHJlc29sdmUsIGRlbGF5KSk7XG4gICAgICAgIH1cbiAgICB9XG4gICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcihgRmFpbGVkICR7b3BlcmF0aW9uTmFtZX0gYWZ0ZXIgJHthdHRlbXB0fSBhdHRlbXB0cy5gLCB7IGxhc3RFcnJvcjogbGFzdEVycm9yPy5tZXNzYWdlIH0pO1xuICAgIHRocm93IGxhc3RFcnJvciB8fCBuZXcgRXJyb3IoYEZhaWxlZCAke29wZXJhdGlvbk5hbWV9IGFmdGVyIGFsbCByZXRyaWVzLmApO1xufVxuXG4vLyBIZWxwZXIgZm9yIHJlc2lsaWVudCBab29tIEFQSSBjYWxscyB1c2luZyBnb3RcbmNvbnN0IHJlc2lsaWVudEdvdFpvb21BcGkgPSBhc3luYyAobWV0aG9kOiAnZ2V0JyB8ICdwb3N0JyB8ICdwYXRjaCcgfCAnZGVsZXRlJywgZW5kcG9pbnQ6IHN0cmluZywgem9vbVRva2VuOiBzdHJpbmcsIGpzb25EYXRhPzogYW55LCBwYXJhbXM/OiBhbnkpID0+IHtcbiAgICBjb25zdCBNQVhfUkVUUklFUyA9IDM7XG4gICAgY29uc3QgSU5JVElBTF9USU1FT1VUX01TID0gMTUwMDA7IC8vIDE1IHNlY29uZHMgZm9yIFpvb20gQVBJIGNhbGxzXG4gICAgbGV0IGF0dGVtcHQgPSAwO1xuICAgIGxldCBsYXN0RXJyb3I6IGFueSA9IG51bGw7XG5cbiAgICBjb25zdCB1cmwgPSBgJHt6b29tQmFzZVVybH0ke2VuZHBvaW50fWA7XG5cbiAgICB3aGlsZSAoYXR0ZW1wdCA8IE1BWF9SRVRSSUVTKSB7XG4gICAgICAgIHRyeSB7XG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYFpvb20gQVBJIGNhbGwgYXR0ZW1wdCAke2F0dGVtcHQgKyAxfTogJHttZXRob2QudG9VcHBlckNhc2UoKX0gJHtlbmRwb2ludH1gKTtcbiAgICAgICAgICAgIGNvbnN0IG9wdGlvbnM6IGFueSA9IHtcbiAgICAgICAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAgICAgICAgICdBdXRob3JpemF0aW9uJzogYEJlYXJlciAke3pvb21Ub2tlbn1gLFxuICAgICAgICAgICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgdGltZW91dDogeyByZXF1ZXN0OiBJTklUSUFMX1RJTUVPVVRfTVMgfSxcbiAgICAgICAgICAgICAgICByZXNwb25zZVR5cGU6ICdqc29uJyxcbiAgICAgICAgICAgIH07XG4gICAgICAgICAgICBpZiAoanNvbkRhdGEpIHtcbiAgICAgICAgICAgICAgICBvcHRpb25zLmpzb24gPSBqc29uRGF0YTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIGlmIChwYXJhbXMpIHtcbiAgICAgICAgICAgICAgICBvcHRpb25zLnNlYXJjaFBhcmFtcyA9IHBhcmFtcztcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgbGV0IHJlc3BvbnNlO1xuICAgICAgICAgICAgc3dpdGNoIChtZXRob2QpIHtcbiAgICAgICAgICAgICAgICBjYXNlICdnZXQnOlxuICAgICAgICAgICAgICAgICAgICByZXNwb25zZSA9IGF3YWl0IGdvdC5nZXQodXJsLCBvcHRpb25zKS5qc29uKCk7XG4gICAgICAgICAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgICAgICAgIGNhc2UgJ3Bvc3QnOlxuICAgICAgICAgICAgICAgICAgICByZXNwb25zZSA9IGF3YWl0IGdvdC5wb3N0KHVybCwgb3B0aW9ucykuanNvbigpO1xuICAgICAgICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgICAgICBjYXNlICdwYXRjaCc6XG4gICAgICAgICAgICAgICAgICAgIHJlc3BvbnNlID0gYXdhaXQgZ290LnBhdGNoKHVybCwgb3B0aW9ucykuanNvbigpOyAvLyAuanNvbigpIG1pZ2h0IG5vdCBiZSBuZWVkZWQgaWYgbm8gYm9keSBleHBlY3RlZFxuICAgICAgICAgICAgICAgICAgICBicmVhazsgLy8gSWYgUEFUQ0ggcmV0dXJucyAyMDQgTm8gQ29udGVudCwgLmpzb24oKSB3aWxsIGZhaWwuIEFkanVzdCBpZiBuZWVkZWQuXG4gICAgICAgICAgICAgICAgY2FzZSAnZGVsZXRlJzpcbiAgICAgICAgICAgICAgICAgICAgYXdhaXQgZ290LmRlbGV0ZSh1cmwsIG9wdGlvbnMpOyAvLyBERUxFVEUgb2Z0ZW4gcmV0dXJucyAyMDQgTm8gQ29udGVudFxuICAgICAgICAgICAgICAgICAgICByZXNwb25zZSA9IHsgc3VjY2VzczogdHJ1ZSB9OyAvLyBTaW11bGF0ZSBhIHN1Y2Nlc3Mgb2JqZWN0IGlmIG5vIGJvZHlcbiAgICAgICAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICAgICAgZGVmYXVsdDpcbiAgICAgICAgICAgICAgICAgICAgdGhyb3cgbmV3IEVycm9yKGBVbnN1cHBvcnRlZCBtZXRob2Q6ICR7bWV0aG9kfWApO1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYFpvb20gQVBJIGNhbGwgJHttZXRob2QudG9VcHBlckNhc2UoKX0gJHtlbmRwb2ludH0gc3VjY2Vzc2Z1bCBvbiBhdHRlbXB0ICR7YXR0ZW1wdCArIDF9YCk7XG4gICAgICAgICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgICAgIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICAgICAgICAgIGxhc3RFcnJvciA9IGVycm9yO1xuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci53YXJuKGBab29tIEFQSSBjYWxsIGF0dGVtcHQgJHthdHRlbXB0ICsgMX0gZm9yICR7bWV0aG9kLnRvVXBwZXJDYXNlKCl9ICR7ZW5kcG9pbnR9IGZhaWxlZC5gLCB7XG4gICAgICAgICAgICAgICAgZXJyb3I6IGVycm9yLm1lc3NhZ2UsXG4gICAgICAgICAgICAgICAgY29kZTogZXJyb3IuY29kZSxcbiAgICAgICAgICAgICAgICBzdGF0dXNDb2RlOiBlcnJvci5yZXNwb25zZT8uc3RhdHVzQ29kZSxcbiAgICAgICAgICAgICAgICAvLyBib2R5OiBlcnJvci5yZXNwb25zZT8uYm9keVxuICAgICAgICAgICAgfSk7XG5cbiAgICAgICAgICAgIGlmIChlcnJvci5yZXNwb25zZSAmJiBlcnJvci5yZXNwb25zZS5zdGF0dXNDb2RlKSB7XG4gICAgICAgICAgICAgICAgY29uc3Qgc3RhdHVzID0gZXJyb3IucmVzcG9uc2Uuc3RhdHVzQ29kZTtcbiAgICAgICAgICAgICAgICBpZiAoc3RhdHVzIDwgNTAwICYmIHN0YXR1cyAhPT0gNDI5ICYmIHN0YXR1cyAhPT0gNDA4ICYmIHN0YXR1cyAhPT0gNDAxKSB7IC8vIDQwMSBtaWdodCBiZSB0b2tlbiBleHBpcnksIGNvdWxkIHJldHJ5IG9uY2UgYWZ0ZXIgcmVmcmVzaFxuICAgICAgICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgIGlmIChzdGF0dXMgPT09IDQwMSkgeyAvLyBTcGVjaWZpYyBoYW5kbGluZyBmb3IgNDAxIHBvdGVudGlhbGx5XG4gICAgICAgICAgICAgICAgICAgIC8vIFRPRE86IENvdWxkIGludGVncmF0ZSB0b2tlbiByZWZyZXNoIGxvZ2ljIGhlcmUgaWYgdGhpcyBoZWxwZXIgYmVjb21lcyBtb3JlIHNvcGhpc3RpY2F0ZWRcbiAgICAgICAgICAgICAgICAgICAgLy8gRm9yIG5vdywganVzdCBsZXQgaXQgcmV0cnkgb25jZSBvciBicmVhayBpZiBpdCdzIGEgcGVyc2lzdGVudCBhdXRoIGlzc3VlLlxuICAgICAgICAgICAgICAgICAgICAvLyBJZiB0aGlzIGlzIHRoZSBmaXJzdCBhdHRlbXB0LCBhbGxvdyBhIHJldHJ5LiBJZiBtb3JlLCBicmVhay5cbiAgICAgICAgICAgICAgICAgICAgaWYgKGF0dGVtcHQgPiAwKSBicmVhaztcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IGVsc2UgaWYgKCFlcnJvci5yZXNwb25zZSAmJiBlcnJvci5jb2RlICYmICFbJ0VUSU1FRE9VVCcsICdFQ09OTlJFU0VUJywgJ0VBRERSSU5VU0UnLCAnRUNPTk5SRUZVU0VEJywgJ0VQSVBFJywgJ0VORVRVTlJFQUNIJywgJ0VBSV9BR0FJTiddLmluY2x1ZGVzKGVycm9yLmNvZGUpKSB7XG4gICAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgICAgYXR0ZW1wdCsrO1xuICAgICAgICBpZiAoYXR0ZW1wdCA8IE1BWF9SRVRSSUVTKSB7XG4gICAgICAgICAgICBjb25zdCBkZWxheSA9IE1hdGgucG93KDIsIGF0dGVtcHQgLSAxKSAqIDEwMDA7XG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYFdhaXRpbmcgJHtkZWxheX1tcyBiZWZvcmUgWm9vbSBBUEkgcmV0cnkgJHthdHRlbXB0ICsgMX0gZm9yICR7bWV0aG9kLnRvVXBwZXJDYXNlKCl9ICR7ZW5kcG9pbnR9YCk7XG4gICAgICAgICAgICBhd2FpdCBuZXcgUHJvbWlzZShyZXNvbHZlID0+IHNldFRpbWVvdXQocmVzb2x2ZSwgZGVsYXkpKTtcbiAgICAgICAgfVxuICAgIH1cbiAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKGBGYWlsZWQgWm9vbSBBUEkgb3BlcmF0aW9uICR7bWV0aG9kLnRvVXBwZXJDYXNlKCl9ICR7ZW5kcG9pbnR9IGFmdGVyICR7YXR0ZW1wdH0gYXR0ZW1wdHMuYCwgeyBsYXN0RXJyb3I6IGxhc3RFcnJvcj8ubWVzc2FnZSB9KTtcbiAgICB0aHJvdyBsYXN0RXJyb3IgfHwgbmV3IEVycm9yKGBGYWlsZWQgWm9vbSBBUEkgb3BlcmF0aW9uICR7bWV0aG9kLnRvVXBwZXJDYXNlKCl9ICR7ZW5kcG9pbnR9IGFmdGVyIGFsbCByZXRyaWVzLmApO1xufTtcblxuXG5leHBvcnQgY29uc3QgZ2V0Wm9vbUFQSVRva2VuID0gYXN5bmMgKFxuICAgIHVzZXJJZDogc3RyaW5nLFxuKSA9PiB7XG4gICAgbGV0IGludGVncmF0aW9uSWQgPSAnJztcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2dldFpvb21BUElUb2tlbic7XG4gICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKGBbJHtvcGVyYXRpb25OYW1lfV0gQ2FsbGVkIGZvciB1c2VyLmAsIHsgdXNlcklkIH0pO1xuXG4gICAgdHJ5IHtcbiAgICAgICAgY29uc3Qgem9vbUludGVncmF0aW9uID0gYXdhaXQgZ2V0Wm9vbUludGVncmF0aW9uKHVzZXJJZCk7XG4gICAgICAgIGlmICghem9vbUludGVncmF0aW9uIHx8ICF6b29tSW50ZWdyYXRpb24uaWQgfHwgIXpvb21JbnRlZ3JhdGlvbi5yZWZyZXNoVG9rZW4pIHtcbiAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIud2FybihgWyR7b3BlcmF0aW9uTmFtZX1dIFpvb20gaW50ZWdyYXRpb24gb3IgZXNzZW50aWFsIGRldGFpbHMgKGlkLCByZWZyZXNoVG9rZW4pIG5vdCBmb3VuZC4gWm9vbSBtaWdodCBub3QgYmUgYWN0aXZlIG9yIHByb3Blcmx5IGNvbmZpZ3VyZWQuYCwgeyB1c2VySWQgfSk7XG4gICAgICAgICAgICByZXR1cm4gdW5kZWZpbmVkOyAvLyBFeHBsaWNpdGx5IHJldHVybiB1bmRlZmluZWQgaWYgaW50ZWdyYXRpb24gaXMgbm90IHVzYWJsZVxuICAgICAgICB9XG5cbiAgICAgICAgaW50ZWdyYXRpb25JZCA9IHpvb21JbnRlZ3JhdGlvbi5pZDsgLy8gQXNzaWduIGhlcmUsIGFmdGVyIHdlIGtub3cgem9vbUludGVncmF0aW9uIGlzIHZhbGlkXG4gICAgICAgIGNvbnN0IHsgdG9rZW4sIGV4cGlyZXNBdCwgcmVmcmVzaFRva2VuIH0gPSB6b29tSW50ZWdyYXRpb247IC8vIERlc3RydWN0dXJlIGFmdGVyIHZhbGlkYXRpb25cblxuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtvcGVyYXRpb25OYW1lfV0gUmV0cmlldmVkIFpvb20gaW50ZWdyYXRpb24gZGV0YWlscy5gLCB7IHVzZXJJZCwgaW50ZWdyYXRpb25JZCwgZXhwaXJlc0F0LCB0b2tlbkV4aXN0czogISF0b2tlbiB9KTtcblxuICAgICAgICBpZiAoZGF5anMoKS5pc0FmdGVyKGRheWpzKGV4cGlyZXNBdCkpIHx8ICF0b2tlbikge1xuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKGBbJHtvcGVyYXRpb25OYW1lfV0gVG9rZW4gZXhwaXJlZCBvciBtaXNzaW5nLCBhdHRlbXB0aW5nIHJlZnJlc2guYCwgeyB1c2VySWQsIGludGVncmF0aW9uSWQgfSk7XG4gICAgICAgICAgICBjb25zdCByZWZyZXNoUmVzcG9uc2UgPSBhd2FpdCByZWZyZXNoWm9vbVRva2VuKHJlZnJlc2hUb2tlbik7XG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYFske29wZXJhdGlvbk5hbWV9XSBab29tIHRva2VuIHJlZnJlc2ggc3VjY2Vzc2Z1bC5gLCB7IHVzZXJJZCwgaW50ZWdyYXRpb25JZCwgbmV3RXhwaXJ5SW46IHJlZnJlc2hSZXNwb25zZS5leHBpcmVzX2luIH0pO1xuICAgICAgICAgICAgYXdhaXQgdXBkYXRlWm9vbUludGVncmF0aW9uKGludGVncmF0aW9uSWQsIHJlZnJlc2hSZXNwb25zZS5hY2Nlc3NfdG9rZW4sIHJlZnJlc2hSZXNwb25zZS5leHBpcmVzX2luKTtcbiAgICAgICAgICAgIHJldHVybiByZWZyZXNoUmVzcG9uc2UuYWNjZXNzX3Rva2VuO1xuICAgICAgICB9XG5cbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5kZWJ1ZyhgWyR7b3BlcmF0aW9uTmFtZX1dIEV4aXN0aW5nIFpvb20gdG9rZW4gaXMgdmFsaWQuYCwgeyB1c2VySWQsIGludGVncmF0aW9uSWQgfSk7XG4gICAgICAgIHJldHVybiB0b2tlbjtcblxuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcihgWyR7b3BlcmF0aW9uTmFtZX1dIEZhaWxlZCB0byBnZXQvcmVmcmVzaCBab29tIEFQSSB0b2tlbi5gLCB7IHVzZXJJZCwgaW50ZWdyYXRpb25JZE9uRXJyb3I6IGludGVncmF0aW9uSWQsIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSwgc3RhY2s6IChlIGFzIEVycm9yKS5zdGFjayB9KTtcbiAgICAgICAgaWYgKGludGVncmF0aW9uSWQpIHsgLy8gT25seSBhdHRlbXB0IHRvIGRpc2FibGUgaWYgd2UgaGFkIGFuIElEXG4gICAgICAgICAgICB0cnkge1xuICAgICAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbyhgWyR7b3BlcmF0aW9uTmFtZX1dIEF0dGVtcHRpbmcgdG8gZGlzYWJsZSBab29tIGludGVncmF0aW9uIGR1ZSB0byBlcnJvci5gLCB7IGludGVncmF0aW9uSWQgfSk7XG4gICAgICAgICAgICAgICAgYXdhaXQgdXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbihpbnRlZ3JhdGlvbklkLCB1bmRlZmluZWQsIHVuZGVmaW5lZCwgZmFsc2UpO1xuICAgICAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbyhgWyR7b3BlcmF0aW9uTmFtZX1dIFN1Y2Nlc3NmdWxseSBkaXNhYmxlZCBab29tIGludGVncmF0aW9uLmAsIHsgaW50ZWdyYXRpb25JZCB9KTtcbiAgICAgICAgICAgIH0gY2F0Y2ggKGRpc2FibGVFcnJvcikge1xuICAgICAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoYFske29wZXJhdGlvbk5hbWV9XSBGYWlsZWQgdG8gZGlzYWJsZSBab29tIGludGVncmF0aW9uIGFmdGVyIGFuIGVycm9yLmAsIHsgaW50ZWdyYXRpb25JZCwgZGlzYWJsZUVycm9yOiAoZGlzYWJsZUVycm9yIGFzIEVycm9yKS5tZXNzYWdlLCBzdGFjazogKGRpc2FibGVFcnJvciBhcyBFcnJvcikuc3RhY2sgfSk7XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgICAgLy8gT3JpZ2luYWwgY29kZSBpbXBsaWNpdGx5IHJldHVybnMgdW5kZWZpbmVkIG9uIGVycm9yIC8gYXR0ZW1wdHMgdG8gZGlzYWJsZS5cbiAgICAgICAgLy8gV2UnbGwgbWFpbnRhaW4gdGhpcyBiZWhhdmlvciBieSBub3QgcmUtdGhyb3dpbmcgaGVyZSwgYnV0IGNhbGxlcnMgc2hvdWxkIGJlIGF3YXJlIGl0IG1pZ2h0IHJldHVybiB1bmRlZmluZWQuXG4gICAgICAgIHJldHVybiB1bmRlZmluZWQ7XG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgZGVsZXRlUmVtaW5kZXJzV2l0aElkcyA9IGFzeW5jIChcbiAgICBldmVudElkczogc3RyaW5nW10sXG4gICAgdXNlcklkOiBzdHJpbmcsXG4pID0+IHtcbiAgICB0cnkge1xuICAgICAgICAvLyB2YWxpZGF0ZVxuICAgICAgICBpZiAoIShldmVudElkcz8uZmlsdGVyKGUgPT4gISFlKT8ubGVuZ3RoID4gMCkpIHtcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG4gICAgICAgIGV2ZW50SWRzLmZvckVhY2goZSA9PiBjb25zb2xlLmxvZyhlLCAnIGV2ZW50SWRzIGluc2lkZSBkZWxldGVSZW1pbmRlcnNXaXRoSWRzJykpXG4gICAgICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZGVsZXRlUmVtaW5kZXJzV2l0aElkcydcbiAgICAgICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBtdXRhdGlvbiBkZWxldGVSZW1pbmRlcnNXaXRoSWRzKCR1c2VySWQ6IHV1aWQhLCAkZXZlbnRJZHM6IFtTdHJpbmchXSEpIHtcbiAgICAgICAgZGVsZXRlX1JlbWluZGVyKHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgZXZlbnRJZDoge19pbjogJGV2ZW50SWRzfX0pIHtcbiAgICAgICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgXG5cbiAgICAgICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgZXZlbnRJZHMsXG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGdvdC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJ1xuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICAgIH1cbiAgICAgICAgYXdhaXQgcmVzaWxpZW50R290UG9zdFBvc3RncmFwaGlsZShvcGVyYXRpb25OYW1lLCBxdWVyeSwgdmFyaWFibGVzLCB1c2VySWQpO1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYFN1Y2Nlc3NmdWxseSBkZWxldGVkIHJlbWluZGVycyBmb3IgZXZlbnRJZHM6ICR7ZXZlbnRJZHMuam9pbignLCAnKX0gZm9yIHVzZXIgJHt1c2VySWR9LmApO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gZGVsZXRlUmVtaW5kZXJzV2l0aElkcycsIHsgdXNlcklkLCBldmVudElkcywgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlIH0pO1xuICAgICAgICB0aHJvdyBlO1xuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IHVwZGF0ZVpvb21NZWV0aW5nXG59XG5cbmV4cG9ydCBjb25zdCB1cGRhdGVab29tTWVldGluZyA9IGFzeW5jIChcbmNhdGNoIChlKSB7XG4gICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gZGVsZXRlUmVtaW5kZXJzV2l0aElkcycsIHsgdXNlcklkLCBldmVudElkcywgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlIH0pO1xuICAgIHRocm93IGU7XG59XG59KTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZVpvb21NZWV0aW5nID0gYXN5bmMgKFxuICAgIHpvb21Ub2tlbjogc3RyaW5nLFxuICAgIG1lZXRpbmdJZDogbnVtYmVyLFxuICAgIHN0YXJ0RGF0ZT86IHN0cmluZyxcbiAgICB0aW1lem9uZT86IHN0cmluZyxcbiAgICBhZ2VuZGE/OiBzdHJpbmcsXG4gICAgZHVyYXRpb24/OiBudW1iZXIsXG4gICAgY29udGFjdE5hbWU/OiBzdHJpbmcsXG4gICAgY29udGFjdEVtYWlsPzogc3RyaW5nLFxuICAgIG1lZXRpbmdJbnZpdGVlcz86IHN0cmluZ1tdLFxuICAgIHByaXZhdGVNZWV0aW5nPzogYm9vbGVhbixcbiAgICByZWN1cj86IFJlY3VycmVuY2VSdWxlVHlwZSxcbikgPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIC8vdmFsZGlhdGVcbiAgICAgICAgaWYgKHN0YXJ0RGF0ZSAmJiBkYXlqcygpLmlzQWZ0ZXIoZGF5anMoc3RhcnREYXRlKSkpIHtcbiAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIud2FybignW3VwZGF0ZVpvb21NZWV0aW5nXSBTdGFydCB0aW1lIGlzIGluIHRoZSBwYXN0LicsIHsgbWVldGluZ0lkLCBzdGFydERhdGUgfSk7XG4gICAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoJ1N0YXJ0IHRpbWUgaXMgaW4gdGhlIHBhc3QgZm9yIHVwZGF0ZVpvb21NZWV0aW5nLicpO1xuICAgICAgICB9XG5cbiAgICAgICAgbGV0IHNldHRpbmdzOiBhbnkgPSB7fVxuXG4gICAgICAgIGlmIChwcml2YXRlTWVldGluZykge1xuICAgICAgICAgICAgc2V0dGluZ3MgPSB7IC4uLnNldHRpbmdzLCBwcml2YXRlX21lZXRpbmc6IHByaXZhdGVNZWV0aW5nIH1cbiAgICAgICAgfVxuXG4gICAgICAgIGlmICgoY29udGFjdE5hbWU/Lmxlbmd0aCA+IDApICYmIChjb250YWN0RW1haWw/Lmxlbmd0aCA+IDApKSB7XG4gICAgICAgICAgICBzZXR0aW5ncyA9IHtcbiAgICAgICAgICAgICAgICBjb250YWN0X25hbWU6IGNvbnRhY3ROYW1lLFxuICAgICAgICAgICAgICAgIGNvbnRhY3RfZW1haWw6IGNvbnRhY3RFbWFpbCxcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChtZWV0aW5nSW52aXRlZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgIHNldHRpbmdzID0geyAuLi5zZXR0aW5ncywgbWVldGluZ19pbnZpdGVlczogbWVldGluZ0ludml0ZWVzIH1cbiAgICAgICAgfVxuXG4gICAgICAgIGxldCByZXFCb2R5OiBhbnkgPSB7fVxuXG4gICAgICAgIGlmIChPYmplY3Qua2V5cyhzZXR0aW5ncyk/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgIHJlcUJvZHkuc2V0dGluZ3MgPSBzZXR0aW5nc1xuICAgICAgICB9XG5cbiAgICAgICAgaWYgKHN0YXJ0RGF0ZSAmJiB0aW1lem9uZSkge1xuICAgICAgICAgICAgcmVxQm9keS5zdGFydF90aW1lID0gZGF5anMoc3RhcnREYXRlPy5zbGljZSgwLCAxOSkpLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpXG4gICAgICAgICAgICByZXFCb2R5LnRpbWV6b25lID0gdGltZXpvbmVcbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChhZ2VuZGEpIHtcbiAgICAgICAgICAgIHJlcUJvZHkuYWdlbmRhID0gYWdlbmRhXG4gICAgICAgIH1cblxuICAgICAgICBpZiAoZHVyYXRpb24pIHtcbiAgICAgICAgICAgIHJlcUJvZHkuZHVyYXRpb24gPSBkdXJhdGlvblxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKHJlY3VyPy5mcmVxdWVuY3kgJiYgcmVjdXI/LmludGVydmFsICYmIChyZWN1cj8uZW5kRGF0ZSB8fCByZWN1cj8ub2NjdXJyZW5jZSkpIHtcblxuICAgICAgICAgICAgaWYgKHJlY3VyPy5mcmVxdWVuY3kgPT09ICd3ZWVrbHknKSB7XG4gICAgICAgICAgICAgICAgcmVxQm9keS5yZWN1cnJlbmNlLnR5cGUgPSAyXG4gICAgICAgICAgICB9IGVsc2UgaWYgKHJlY3VyPy5mcmVxdWVuY3kgPT09ICdtb250aGx5Jykge1xuICAgICAgICAgICAgICAgIHJlcUJvZHkucmVjdXJyZW5jZS50eXBlID0gM1xuICAgICAgICAgICAgfSBlbHNlIGlmIChyZWN1cj8uZnJlcXVlbmN5ID09PSAnZGFpbHknKSB7XG4gICAgICAgICAgICAgICAgcmVxQm9keS5yZWN1cnJlbmNlLnR5cGUgPSAxXG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGlmIChyZXFCb2R5LnJlY3VycmVuY2UudHlwZSA9PSAzKSB7XG5cbiAgICAgICAgICAgICAgICBpZiAocmVjdXI/LmJ5TW9udGhEYXk/LlswXSkge1xuXG4gICAgICAgICAgICAgICAgICAgIHJlcUJvZHkucmVjdXJyZW5jZS5tb250aGx5X2RheSA9IHJlY3VyPy5ieU1vbnRoRGF5Py5bMF1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGlmIChyZWN1cj8uZW5kRGF0ZSkge1xuICAgICAgICAgICAgICAgIHJlcUJvZHkucmVjdXJyZW5jZS5lbmRfZGF0ZV90aW1lID0gZGF5anMocmVjdXIuZW5kRGF0ZSkudHoodGltZXpvbmUpLnV0YygpLmZvcm1hdCgpXG4gICAgICAgICAgICB9IGVsc2UgaWYgKHJlY3VyPy5vY2N1cnJlbmNlKSB7XG4gICAgICAgICAgICAgICAgcmVxQm9keS5yZWN1cnJlbmNlLmVuZF90aW1lcyA9IHJlY3VyLm9jY3VycmVuY2VcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgcmVxQm9keS5yZWN1cnJlbmNlLnJlcGVhdF9pbnRlcnZhbCA9IHJlY3VyLmludGVydmFsXG5cbiAgICAgICAgICAgIGlmIChyZWN1cj8uYnlNb250aERheT8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgICAgIC8vIGNyZWF0ZSBycnVsZSBhbmQgZ28gYnkgZWFjaCBkYXRlXG4gICAgICAgICAgICAgICAgY29uc3QgcnVsZSA9IG5ldyBSUnVsZSh7XG4gICAgICAgICAgICAgICAgICAgIGZyZXE6IGdldFJydWxlRnJlcSgocmVjdXIgYXMgYW55KT8uZnJlcXVlbmN5KSxcbiAgICAgICAgICAgICAgICAgICAgaW50ZXJ2YWw6IHJlY3VyPy5pbnRlcnZhbCxcbiAgICAgICAgICAgICAgICAgICAgdW50aWw6IGRheWpzKHJlY3VyPy5lbmREYXRlKS50b0RhdGUoKSxcbiAgICAgICAgICAgICAgICAgICAgYnl3ZWVrZGF5OiByZWN1cj8uYnlXZWVrRGF5Py5tYXAoaSA9PiBnZXRSUnVsZUJ5V2Vla0RheShpKSksXG4gICAgICAgICAgICAgICAgICAgIGNvdW50OiByZWN1cj8ub2NjdXJyZW5jZSxcbiAgICAgICAgICAgICAgICAgICAgYnltb250aGRheTogcmVjdXI/LmJ5TW9udGhEYXksXG4gICAgICAgICAgICAgICAgfSlcblxuICAgICAgICAgICAgICAgIGNvbnN0IHJ1bGVEYXRlcyA9IHJ1bGUuYWxsKClcblxuICAgICAgICAgICAgICAgIGNvbnN0IG5vblVuaXF1ZVdlZWtNb250aCA9IFtdXG4gICAgICAgICAgICAgICAgY29uc3Qgbm9uVW5pcXVlRGF5TW9udGggPSBbXVxuICAgICAgICAgICAgICAgIGNvbnN0IG5vblVuaXF1ZURheVdlZWtNb250aCA9IFtdXG4gICAgICAgICAgICAgICAgZm9yIChjb25zdCBydWxlRGF0ZSBvZiBydWxlRGF0ZXMpIHtcbiAgICAgICAgICAgICAgICAgICAgY29uc3Qgd2Vla01vbnRoID0gZ2V0V2Vla09mTW9udGgocnVsZURhdGUpXG4gICAgICAgICAgICAgICAgICAgIG5vblVuaXF1ZVdlZWtNb250aC5wdXNoKHdlZWtNb250aClcbiAgICAgICAgICAgICAgICAgICAgY29uc3QgZGF5TW9udGggPSBkYXlqcyhydWxlRGF0ZSkuZGF0ZSgpXG4gICAgICAgICAgICAgICAgICAgIG5vblVuaXF1ZURheU1vbnRoLnB1c2goZGF5TW9udGgpXG4gICAgICAgICAgICAgICAgICAgIGNvbnN0IGRheVdlZWtNb250aCA9IGdldElTT0RheShkYXlqcyhydWxlRGF0ZSkudG9EYXRlKCkpXG4gICAgICAgICAgICAgICAgICAgIG5vblVuaXF1ZURheVdlZWtNb250aC5wdXNoKGRheVdlZWtNb250aClcbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBjb25zdCB1bmlxdWVEYXlXZWVrTW9udGggPSBfLnVuaXEobm9uVW5pcXVlRGF5V2Vla01vbnRoKVxuICAgICAgICAgICAgICAgIGNvbnN0IHVuaXF1ZURheU1vbnRoID0gXy51bmlxKG5vblVuaXF1ZURheU1vbnRoKVxuICAgICAgICAgICAgICAgIGNvbnN0IHVuaXF1ZVdlZWtNb250aCA9IF8udW5pcShub25VbmlxdWVXZWVrTW9udGgpXG5cbiAgICAgICAgICAgICAgICBpZiAodW5pcXVlRGF5V2Vla01vbnRoPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgICAgICAgICAgIHJlcUJvZHkucmVjdXJyZW5jZS5tb250aGx5X3dlZWtfZGF5ID0gdW5pcXVlRGF5V2Vla01vbnRoPy5bMF1cbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICBpZiAodW5pcXVlRGF5TW9udGg/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgICAgICAgICAgcmVxQm9keS5yZWN1cnJlbmNlLm1vbnRobHlfZGF5ID0gdW5pcXVlRGF5TW9udGg/LlswXVxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGlmICh1bmlxdWVXZWVrTW9udGg/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgICAgICAgICAgcmVxQm9keS5yZWN1cnJlbmNlLm1vbnRobHlfd2VlayA9IHVuaXF1ZVdlZWtNb250aD8uWzBdXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIGlmIChyZWN1cj8uYnlXZWVrRGF5Py5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgICAgICAgcmVxQm9keS5yZWN1cnJlbmNlLndlZWtseV9kYXlzID0gZ2V0TnVtYmVySW5TdHJpbmcocmVjdXIuYnlXZWVrRGF5KVxuICAgICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgYXdhaXQgcmVzaWxpZW50R290Wm9vbUFwaSgncGF0Y2gnLCBgL21lZXRpbmdzLyR7bWVldGluZ0lkfWAsIHpvb21Ub2tlbiwgcmVxQm9keSk7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbyhgU3VjY2Vzc2Z1bGx5IHBhdGNoZWQgWm9vbSBtZWV0aW5nICR7bWVldGluZ0lkfS5gKTtcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoJ0Vycm9yIGluIHVwZGF0ZVpvb21NZWV0aW5nJywgeyBtZWV0aW5nSWQsIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSB9KTtcbiAgICAgICAgdGhyb3cgZTsgLy8gUmUtdGhyb3cgdG8gYWxsb3cgY2FsbGVyIHRvIGhhbmRsZVxuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IGdldE51bWJlckZvcldlZWtEYXkgPSAoXG4gICAgZGF5OiBEYXlPZldlZWtUeXBlXG4pID0+IHtcblxuICAgIHN3aXRjaCAoZGF5KSB7XG4gICAgICAgIGNhc2UgJ01PJzpcbiAgICAgICAgICAgIHJldHVybiAnMSdcbiAgICAgICAgY2FzZSAnVFUnOlxuICAgICAgICAgICAgcmV0dXJuICcyJ1xuICAgICAgICBjYXNlICdXRSc6XG4gICAgICAgICAgICByZXR1cm4gJzMnXG4gICAgICAgIGNhc2UgJ1RIJzpcbiAgICAgICAgICAgIHJldHVybiAnNCdcbiAgICAgICAgY2FzZSAnRlInOlxuICAgICAgICAgICAgcmV0dXJuICc1J1xuICAgICAgICBjYXNlICdTQSc6XG4gICAgICAgICAgICByZXR1cm4gJzYnXG4gICAgICAgIGNhc2UgJ1NVJzpcbiAgICAgICAgICAgIHJldHVybiAnNydcbiAgICB9XG59XG5cbmV4cG9ydCBjb25zdCBnZXROdW1iZXJJblN0cmluZyA9IChcbiAgICBieVdlZWtEYXlzOiBEYXlPZldlZWtUeXBlW11cbikgPT4ge1xuXG4gICAgbGV0IG51bWJlckluU3RyaW5nID0gJydcblxuICAgIGZvciAoY29uc3QgYnlXZWVrRGF5IG9mIGJ5V2Vla0RheXMpIHtcbiAgICAgICAgbnVtYmVySW5TdHJpbmcgKz0gYCR7Z2V0TnVtYmVyRm9yV2Vla0RheShieVdlZWtEYXkpfSwgYFxuICAgIH1cblxuICAgIHJldHVybiBudW1iZXJJblN0cmluZ1xufVxuZXhwb3J0IGNvbnN0IGNyZWF0ZVpvb21NZWV0aW5nID0gYXN5bmMgKFxuICAgIHpvb21Ub2tlbjogc3RyaW5nLFxuICAgIHN0YXJ0RGF0ZTogc3RyaW5nLFxuICAgIHRpbWV6b25lOiBzdHJpbmcsXG4gICAgYWdlbmRhOiBzdHJpbmcsXG4gICAgZHVyYXRpb246IG51bWJlcixcbiAgICBjb250YWN0TmFtZT86IHN0cmluZyxcbiAgICBjb250YWN0RW1haWw/OiBzdHJpbmcsXG4gICAgbWVldGluZ0ludml0ZWVzPzogc3RyaW5nW10sXG4gICAgcmVjdXI/OiBSZWN1cnJlbmNlUnVsZVR5cGUsXG4pID0+IHtcbiAgICB0cnkge1xuICAgICAgICAvL3ZhbGRpYXRlXG4gICAgICAgIGlmIChkYXlqcygpLmlzQWZ0ZXIoZGF5anMoc3RhcnREYXRlKSkpIHtcbiAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIud2FybignW2NyZWF0ZVpvb21NZWV0aW5nXSBTdGFydCB0aW1lIGlzIGluIHRoZSBwYXN0LicsIHsgc3RhcnREYXRlLCBhZ2VuZGEgfSk7XG4gICAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoJ1N0YXJ0IHRpbWUgaXMgaW4gdGhlIHBhc3QgZm9yIGNyZWF0ZVpvb21NZWV0aW5nLicpO1xuICAgICAgICB9XG5cbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKCdbY3JlYXRlWm9vbU1lZXRpbmddIENhbGxlZC4nLCB7IHN0YXJ0RGF0ZSwgdGltZXpvbmUsIGFnZW5kYSwgZHVyYXRpb24gfSk7XG5cbiAgICAgICAgbGV0IHNldHRpbmdzOiBhbnkgPSB7fVxuXG4gICAgICAgIGlmICgoY29udGFjdE5hbWU/Lmxlbmd0aCA+IDApICYmIChjb250YWN0RW1haWw/Lmxlbmd0aCA+IDApKSB7XG4gICAgICAgICAgICBzZXR0aW5ncyA9IHtcbiAgICAgICAgICAgICAgICBjb250YWN0X25hbWU6IGNvbnRhY3ROYW1lLFxuICAgICAgICAgICAgICAgIGNvbnRhY3RfZW1haWw6IGNvbnRhY3RFbWFpbCxcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChtZWV0aW5nSW52aXRlZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgIHNldHRpbmdzID0geyAuLi5zZXR0aW5ncywgbWVldGluZ19pbnZpdGVlczogbWVldGluZ0ludml0ZWVzPy5tYXAobSA9PiAoeyBlbWFpbDogbSB9KSkgfVxuICAgICAgICB9XG5cbiAgICAgICAgbGV0IHJlcUJvZHk6IENyZWF0ZVpvb21NZWV0aW5nUmVxdWVzdEJvZHlUeXBlID0ge31cblxuICAgICAgICBpZiAoT2JqZWN0LmtleXMoc2V0dGluZ3MpPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgICByZXFCb2R5LnNldHRpbmdzID0gc2V0dGluZ3NcbiAgICAgICAgfVxuXG4gICAgICAgIHJlcUJvZHkgPSB7XG4gICAgICAgICAgICAuLi5yZXFCb2R5LFxuICAgICAgICAgICAgc3RhcnRfdGltZTogZGF5anMoc3RhcnREYXRlPy5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKS51dGMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIC8vIHRpbWV6b25lLFxuICAgICAgICAgICAgYWdlbmRhLFxuICAgICAgICAgICAgZHVyYXRpb24sXG4gICAgICAgIH1cblxuICAgICAgICBpZiAocmVjdXI/LmZyZXF1ZW5jeSAmJiByZWN1cj8uaW50ZXJ2YWwgJiYgKHJlY3VyPy5lbmREYXRlIHx8IHJlY3VyPy5vY2N1cnJlbmNlKSkge1xuXG4gICAgICAgICAgICBpZiAocmVjdXI/LmZyZXF1ZW5jeSA9PT0gJ3dlZWtseScpIHtcbiAgICAgICAgICAgICAgICByZXFCb2R5LnJlY3VycmVuY2UudHlwZSA9IDJcbiAgICAgICAgICAgIH0gZWxzZSBpZiAocmVjdXI/LmZyZXF1ZW5jeSA9PT0gJ21vbnRobHknKSB7XG4gICAgICAgICAgICAgICAgcmVxQm9keS5yZWN1cnJlbmNlLnR5cGUgPSAzXG4gICAgICAgICAgICB9IGVsc2UgaWYgKHJlY3VyPy5mcmVxdWVuY3kgPT09ICdkYWlseScpIHtcbiAgICAgICAgICAgICAgICByZXFCb2R5LnJlY3VycmVuY2UudHlwZSA9IDFcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKHJlcUJvZHkucmVjdXJyZW5jZS50eXBlID09IDMpIHtcblxuICAgICAgICAgICAgICAgIGlmIChyZWN1cj8uYnlNb250aERheT8uWzBdKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgcmVxQm9keS5yZWN1cnJlbmNlLm1vbnRobHlfZGF5ID0gcmVjdXI/LmJ5TW9udGhEYXk/LlswXVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKHJlY3VyPy5lbmREYXRlKSB7XG4gICAgICAgICAgICAgICAgcmVxQm9keS5yZWN1cnJlbmNlLmVuZF9kYXRlX3RpbWUgPSBkYXlqcyhyZWN1ci5lbmREYXRlKS50eih0aW1lem9uZSkudXRjKCkuZm9ybWF0KClcbiAgICAgICAgICAgIH0gZWxzZSBpZiAocmVjdXI/Lm9jY3VycmVuY2UpIHtcbiAgICAgICAgICAgICAgICByZXFCb2R5LnJlY3VycmVuY2UuZW5kX3RpbWVzID0gcmVjdXIub2NjdXJyZW5jZVxuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICByZXFCb2R5LnJlY3VycmVuY2UucmVwZWF0X2ludGVydmFsID0gcmVjdXIuaW50ZXJ2YWxcblxuICAgICAgICAgICAgaWYgKHJlY3VyPy5ieU1vbnRoRGF5Py5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgICAgICAgLy8gY3JlYXRlIHJydWxlIGFuZCBnbyBieSBlYWNoIGRhdGVcbiAgICAgICAgICAgICAgICBjb25zdCBydWxlID0gbmV3IFJSdWxlKHtcbiAgICAgICAgICAgICAgICAgICAgZnJlcTogZ2V0UnJ1bGVGcmVxKChyZWN1ciBhcyBhbnkpPy5mcmVxdWVuY3kpLFxuICAgICAgICAgICAgICAgICAgICBpbnRlcnZhbDogcmVjdXI/LmludGVydmFsLFxuICAgICAgICAgICAgICAgICAgICB1bnRpbDogZGF5anMocmVjdXI/LmVuZERhdGUpLnRvRGF0ZSgpLFxuICAgICAgICAgICAgICAgICAgICBieXdlZWtkYXk6IHJlY3VyPy5ieVdlZWtEYXk/Lm1hcChpID0+IGdldFJSdWxlQnlXZWVrRGF5KGkpKSxcbiAgICAgICAgICAgICAgICAgICAgY291bnQ6IHJlY3VyPy5vY2N1cnJlbmNlLFxuICAgICAgICAgICAgICAgICAgICBieW1vbnRoZGF5OiByZWN1cj8uYnlNb250aERheSxcbiAgICAgICAgICAgICAgICB9KVxuXG4gICAgICAgICAgICAgICAgY29uc3QgcnVsZURhdGVzID0gcnVsZS5hbGwoKVxuXG4gICAgICAgICAgICAgICAgY29uc3Qgbm9uVW5pcXVlV2Vla01vbnRoID0gW11cbiAgICAgICAgICAgICAgICBjb25zdCBub25VbmlxdWVEYXlNb250aCA9IFtdXG4gICAgICAgICAgICAgICAgY29uc3Qgbm9uVW5pcXVlRGF5V2Vla01vbnRoID0gW11cbiAgICAgICAgICAgICAgICBmb3IgKGNvbnN0IHJ1bGVEYXRlIG9mIHJ1bGVEYXRlcykge1xuICAgICAgICAgICAgICAgICAgICBjb25zdCB3ZWVrTW9udGggPSBnZXRXZWVrT2ZNb250aChydWxlRGF0ZSlcbiAgICAgICAgICAgICAgICAgICAgbm9uVW5pcXVlV2Vla01vbnRoLnB1c2god2Vla01vbnRoKVxuICAgICAgICAgICAgICAgICAgICBjb25zdCBkYXlNb250aCA9IGRheWpzKHJ1bGVEYXRlKS5kYXRlKClcbiAgICAgICAgICAgICAgICAgICAgbm9uVW5pcXVlRGF5TW9udGgucHVzaChkYXlNb250aClcbiAgICAgICAgICAgICAgICAgICAgY29uc3QgZGF5V2Vla01vbnRoID0gZ2V0SVNPRGF5KGRheWpzKHJ1bGVEYXRlKS50b0RhdGUoKSlcbiAgICAgICAgICAgICAgICAgICAgbm9uVW5pcXVlRGF5V2Vla01vbnRoLnB1c2goZGF5V2Vla01vbnRoKVxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGNvbnN0IHVuaXF1ZURheVdlZWtNb250aCA9IF8udW5pcShub25VbmlxdWVEYXlXZWVrTW9udGgpXG4gICAgICAgICAgICAgICAgY29uc3QgdW5pcXVlRGF5TW9udGggPSBfLnVuaXEobm9uVW5pcXVlRGF5TW9udGgpXG4gICAgICAgICAgICAgICAgY29uc3QgdW5pcXVlV2Vla01vbnRoID0gXy51bmlxKG5vblVuaXF1ZVdlZWtNb250aClcblxuICAgICAgICAgICAgICAgIGlmICh1bmlxdWVEYXlXZWVrTW9udGg/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgICAgICAgICAgcmVxQm9keS5yZWN1cnJlbmNlLm1vbnRobHlfd2Vla19kYXkgPSB1bmlxdWVEYXlXZWVrTW9udGg/LlswXVxuICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgIGlmICh1bmlxdWVEYXlNb250aD8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgICAgICAgICByZXFCb2R5LnJlY3VycmVuY2UubW9udGhseV9kYXkgPSB1bmlxdWVEYXlNb250aD8uWzBdXG4gICAgICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICAgICAgaWYgKHVuaXF1ZVdlZWtNb250aD8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgICAgICAgICByZXFCb2R5LnJlY3VycmVuY2UubW9udGhseV93ZWVrID0gdW5pcXVlV2Vla01vbnRoPy5bMF1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IGVsc2UgaWYgKHJlY3VyPy5ieVdlZWtEYXk/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgICAgICByZXFCb2R5LnJlY3VycmVuY2Uud2Vla2x5X2RheXMgPSBnZXROdW1iZXJJblN0cmluZyhyZWN1ci5ieVdlZWtEYXkpXG4gICAgICAgICAgICB9XG4gICAgICAgIH1cblxuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKCdab29tIGNyZWF0ZU1lZXRpbmcgcmVxdWVzdCBib2R5OicsIHsgcmVxQm9keSB9KTtcblxuICAgICAgICBjb25zdCByZXNwb25zZURhdGEgPSBhd2FpdCByZXNpbGllbnRHb3Rab29tQXBpKCdwb3N0JywgJy91c2Vycy9tZS9tZWV0aW5ncycsIHpvb21Ub2tlbiwgcmVxQm9keSkgYXMgWm9vbU1lZXRpbmdPYmplY3RUeXBlO1xuXG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbygnU3VjY2Vzc2Z1bGx5IGNyZWF0ZWQgWm9vbSBtZWV0aW5nLicsIHsgbWVldGluZ0lkOiByZXNwb25zZURhdGE/LmlkLCB0b3BpYzogcmVzcG9uc2VEYXRhPy50b3BpYyB9KTtcbiAgICAgICAgcmV0dXJuIHJlc3BvbnNlRGF0YTtcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoJ0Vycm9yIGluIGNyZWF0ZVpvb21NZWV0aW5nJywgeyBhZ2VuZGEsIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSB9KTtcbiAgICAgICAgdGhyb3cgZTtcbiAgICB9XG59XG5cbmNvbnN0IHJlZnJlc2hHb29nbGVUb2tlbiA9IGFzeW5jIChcbiAgICByZWZyZXNoVG9rZW46IHN0cmluZyxcbiAgICBjbGllbnRUeXBlOiAnaW9zJyB8ICdhbmRyb2lkJyB8ICd3ZWInIHwgJ2F0b21pYy13ZWInXG4pOiBQcm9taXNlPHtcbiAgICBhY2Nlc3NfdG9rZW46IHN0cmluZyxcbiAgICBleHBpcmVzX2luOiBudW1iZXIsIC8vIGFkZCBzZWNvbmRzIHRvIG5vd1xuICAgIHNjb3BlOiBzdHJpbmcsXG4gICAgdG9rZW5fdHlwZTogc3RyaW5nXG59PiA9PiB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdyZWZyZXNoR29vZ2xlVG9rZW4nO1xuICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbyhgJHtvcGVyYXRpb25OYW1lfSBjYWxsZWRgLCB7IGNsaWVudFR5cGUsIHJlZnJlc2hUb2tlblN1YnN0cmluZzogcmVmcmVzaFRva2VuPy5zdWJzdHJpbmcoMCwxMCkgfSk7XG5cbiAgICBsZXQgY2xpZW50SWQ6IHN0cmluZztcbiAgICBsZXQgY2xpZW50U2VjcmV0OiBzdHJpbmcgfCB1bmRlZmluZWQ7XG5cbiAgICBzd2l0Y2ggKGNsaWVudFR5cGUpIHtcbiAgICAgICAgY2FzZSAnaW9zJzpcbiAgICAgICAgICAgIGNsaWVudElkID0gZ29vZ2xlQ2xpZW50SWRJb3M7XG4gICAgICAgICAgICBicmVhaztcbiAgICAgICAgY2FzZSAnYW5kcm9pZCc6XG4gICAgICAgICAgICBjbGllbnRJZCA9IGdvb2dsZUNsaWVudElkQW5kcm9pZDtcbiAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICBjYXNlICd3ZWInOlxuICAgICAgICAgICAgY2xpZW50SWQgPSBnb29nbGVDbGllbnRJZFdlYjtcbiAgICAgICAgICAgIGNsaWVudFNlY3JldCA9IGdvb2dsZUNsaWVudFNlY3JldFdlYjtcbiAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICBjYXNlICdhdG9taWMtd2ViJzpcbiAgICAgICAgICAgIGNsaWVudElkID0gZ29vZ2xlQ2xpZW50SWRBdG9taWNXZWI7XG4gICAgICAgICAgICBjbGllbnRTZWNyZXQgPSBnb29nbGVDbGllbnRTZWNyZXRBdG9taWNXZWI7XG4gICAgICAgICAgICBicmVhaztcbiAgICAgICAgZGVmYXVsdDpcbiAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoYEludmFsaWQgY2xpZW50VHlwZSBmb3IgJHtvcGVyYXRpb25OYW1lfWAsIHsgY2xpZW50VHlwZSB9KTtcbiAgICAgICAgICAgIHRocm93IG5ldyBFcnJvcihgSW52YWxpZCBjbGllbnRUeXBlOiAke2NsaWVudFR5cGV9YCk7XG4gICAgfVxuXG4gICAgY29uc3QgZm9ybVBheWxvYWQ6IFJlY29yZDxzdHJpbmcsIHN0cmluZz4gPSB7XG4gICAgICAgIGdyYW50X3R5cGU6ICdyZWZyZXNoX3Rva2VuJyxcbiAgICAgICAgcmVmcmVzaF90b2tlbjogcmVmcmVzaFRva2VuLFxuICAgICAgICBjbGllbnRfaWQ6IGNsaWVudElkLFxuICAgIH07XG4gICAgaWYgKGNsaWVudFNlY3JldCkge1xuICAgICAgICBmb3JtUGF5bG9hZC5jbGllbnRfc2VjcmV0ID0gY2xpZW50U2VjcmV0O1xuICAgIH1cblxuICAgIHRyeSB7XG4gICAgICAgIHJldHVybiBhd2FpdCByZXNpbGllbnRHb3RHb29nbGVBdXRoKGdvb2dsZVRva2VuVXJsLCBmb3JtUGF5bG9hZCwgb3BlcmF0aW9uTmFtZSwgY2xpZW50VHlwZSk7XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKGBGYWlsZWQgJHtvcGVyYXRpb25OYW1lfSBmb3IgY2xpZW50VHlwZSAke2NsaWVudFR5cGV9IGFmdGVyIGFsbCByZXRyaWVzLmAsIHsgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlIH0pO1xuICAgICAgICAvLyBUaGUgb3JpZ2luYWwgZnVuY3Rpb24gd291bGQgbG9nIGFuZCBpbXBsaWNpdGx5IHJldHVybiB1bmRlZmluZWQuXG4gICAgICAgIC8vIFRvIG1haW50YWluIGEgY2xlYXJlciBjb250cmFjdCwgd2UnbGwgcmV0aHJvdy4gQ2FsbGVycyBzaG91bGQgaGFuZGxlIHRoaXMuXG4gICAgICAgIHRocm93IGU7XG4gICAgfVxufVxuXG5cbi8vIEhlbHBlciBmb3IgcmVzaWxpZW50IEdvb2dsZSBBdXRoIGNhbGxzIHVzaW5nIGdvdFxuY29uc3QgcmVzaWxpZW50R290R29vZ2xlQXV0aCA9IGFzeW5jIChcbiAgICB1cmw6IHN0cmluZyxcbiAgICBmb3JtUGF5bG9hZDogUmVjb3JkPHN0cmluZywgc3RyaW5nPixcbiAgICBvcGVyYXRpb25OYW1lOiBzdHJpbmcsXG4gICAgY2xpZW50VHlwZTogc3RyaW5nXG4pID0+IHtcbiAgICBjb25zdCBNQVhfUkVUUklFUyA9IDM7XG4gICAgY29uc3QgSU5JVElBTF9USU1FT1VUX01TID0gMTAwMDA7IC8vIDEwIHNlY29uZHMgZm9yIEdvb2dsZSBBdXRoIGNhbGxzXG4gICAgbGV0IGF0dGVtcHQgPSAwO1xuICAgIGxldCBsYXN0RXJyb3I6IGFueSA9IG51bGw7XG5cbiAgICB3aGlsZSAoYXR0ZW1wdCA8IE1BWF9SRVRSSUVTKSB7XG4gICAgICAgIHRyeSB7XG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYEdvb2dsZSBBdXRoIGNhbGwgYXR0ZW1wdCAke2F0dGVtcHQgKyAxfSBmb3IgJHtvcGVyYXRpb25OYW1lfSAoJHtjbGllbnRUeXBlfSlgKTtcbiAgICAgICAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZ290LnBvc3QodXJsLCB7XG4gICAgICAgICAgICAgICAgZm9ybTogZm9ybVBheWxvYWQsXG4gICAgICAgICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL3gtd3d3LWZvcm0tdXJsZW5jb2RlZCcsXG4gICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICB0aW1lb3V0OiB7IHJlcXVlc3Q6IElOSVRJQUxfVElNRU9VVF9NUyB9LFxuICAgICAgICAgICAgICAgIHJlc3BvbnNlVHlwZTogJ2pzb24nLFxuICAgICAgICAgICAgfSkuanNvbjx7IGFjY2Vzc190b2tlbjogc3RyaW5nLCBleHBpcmVzX2luOiBudW1iZXIsIHNjb3BlOiBzdHJpbmcsIHRva2VuX3R5cGU6IHN0cmluZyB9PigpO1xuXG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYEdvb2dsZSBBdXRoIGNhbGwgJHtvcGVyYXRpb25OYW1lfSAoJHtjbGllbnRUeXBlfSkgc3VjY2Vzc2Z1bCBvbiBhdHRlbXB0ICR7YXR0ZW1wdCArIDF9YCk7XG4gICAgICAgICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgICAgIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICAgICAgICAgIGxhc3RFcnJvciA9IGVycm9yO1xuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci53YXJuKGBHb29nbGUgQXV0aCBjYWxsIGF0dGVtcHQgJHthdHRlbXB0ICsgMX0gZm9yICR7b3BlcmF0aW9uTmFtZX0gKCR7Y2xpZW50VHlwZX0pIGZhaWxlZC5gLCB7XG4gICAgICAgICAgICAgICAgZXJyb3I6IGVycm9yLm1lc3NhZ2UsXG4gICAgICAgICAgICAgICAgY29kZTogZXJyb3IuY29kZSxcbiAgICAgICAgICAgICAgICBzdGF0dXNDb2RlOiBlcnJvci5yZXNwb25zZT8uc3RhdHVzQ29kZSxcbiAgICAgICAgICAgICAgICAvLyBib2R5OiBlcnJvci5yZXNwb25zZT8uYm9keSAvLyBCZSBjYXJlZnVsIGxvZ2dpbmcgc2Vuc2l0aXZlIGJvZHkgcGFydHNcbiAgICAgICAgICAgIH0pO1xuXG4gICAgICAgICAgICBpZiAoZXJyb3IucmVzcG9uc2UgJiYgZXJyb3IucmVzcG9uc2Uuc3RhdHVzQ29kZSkge1xuICAgICAgICAgICAgICAgIGNvbnN0IHN0YXR1cyA9IGVycm9yLnJlc3BvbnNlLnN0YXR1c0NvZGU7XG4gICAgICAgICAgICAgICAgLy8gNDAwLCA0MDEsIDQwMyBhcmUgdXN1YWxseSBjbGllbnQgZXJyb3JzIGZvciBhdXRoLCBub3QgdHlwaWNhbGx5IHJldHJ5YWJsZSB1bmxlc3Mgc3BlY2lmaWMgKGUuZy4gdGVtcG9yYXJ5IGNsb2NrIHNrZXcgZm9yIDQwMSwgYnV0IHVubGlrZWx5IGhlcmUpXG4gICAgICAgICAgICAgICAgaWYgKHN0YXR1cyA9PT0gNDAwIHx8IHN0YXR1cyA9PT0gNDAxIHx8IHN0YXR1cyA9PT0gNDAzKSB7XG4gICAgICAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKGBOb24tcmV0cnlhYmxlIEhUVFAgZXJyb3IgJHtzdGF0dXN9IGZvciAke29wZXJhdGlvbk5hbWV9ICgke2NsaWVudFR5cGV9KS4gQWJvcnRpbmcuYCwgeyBvcGVyYXRpb25OYW1lLCBjbGllbnRUeXBlIH0pO1xuICAgICAgICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgaWYgKHN0YXR1cyA8IDUwMCAmJiBzdGF0dXMgIT09IDQyOSAmJiBzdGF0dXMgIT09IDQwOCkge1xuICAgICAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKGBOb24tcmV0cnlhYmxlIEhUVFAgZXJyb3IgJHtzdGF0dXN9IGZvciAke29wZXJhdGlvbk5hbWV9ICgke2NsaWVudFR5cGV9KS4gQWJvcnRpbmcuYCwgeyBvcGVyYXRpb25OYW1lLCBjbGllbnRUeXBlIH0pO1xuICAgICAgICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IGVsc2UgaWYgKCFlcnJvci5yZXNwb25zZSAmJiBlcnJvci5jb2RlICYmICFbJ0VUSU1FRE9VVCcsICdFQ09OTlJFU0VUJywgJ0VBRERSSU5VU0UnLCAnRUNPTk5SRUZVU0VEJywgJ0VQSVBFJywgJ0VORVRVTlJFQUNIJywgJ0VBSV9BR0FJTiddLmluY2x1ZGVzKGVycm9yLmNvZGUpKSB7XG4gICAgICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcihgTm9uLXJldHJ5YWJsZSBnb3QgZXJyb3IgY29kZSAke2Vycm9yLmNvZGV9IGZvciAke29wZXJhdGlvbk5hbWV9ICgke2NsaWVudFR5cGV9KS4gQWJvcnRpbmcuYCwgeyBvcGVyYXRpb25OYW1lLCBjbGllbnRUeXBlIH0pO1xuICAgICAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICAgIGF0dGVtcHQrKztcbiAgICAgICAgaWYgKGF0dGVtcHQgPCBNQVhfUkVUUklFUykge1xuICAgICAgICAgICAgY29uc3QgZGVsYXkgPSBNYXRoLnBvdygyLCBhdHRlbXB0IC0xKSAqIDEwMDA7IC8vIEV4cG9uZW50aWFsIGJhY2tvZmY6IDFzLCAyc1xuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKGBXYWl0aW5nICR7ZGVsYXl9bXMgYmVmb3JlIEdvb2dsZSBBdXRoIHJldHJ5ICR7YXR0ZW1wdCArIDF9IGZvciAke29wZXJhdGlvbk5hbWV9ICgke2NsaWVudFR5cGV9KWApO1xuICAgICAgICAgICAgYXdhaXQgbmV3IFByb21pc2UocmVzb2x2ZSA9PiBzZXRUaW1lb3V0KHJlc29sdmUsIGRlbGF5KSk7XG4gICAgICAgIH1cbiAgICB9XG4gICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcihgRmFpbGVkIEdvb2dsZSBBdXRoIG9wZXJhdGlvbiAnJHtvcGVyYXRpb25OYW1lfScgKCR7Y2xpZW50VHlwZX0pIGFmdGVyICR7YXR0ZW1wdH0gYXR0ZW1wdHMuYCwgeyBvcGVyYXRpb25OYW1lLCBjbGllbnRUeXBlLCBsYXN0RXJyb3I6IGxhc3RFcnJvcj8ubWVzc2FnZSB9KTtcbiAgICB0aHJvdyBsYXN0RXJyb3IgfHwgbmV3IEVycm9yKGBGYWlsZWQgR29vZ2xlIEF1dGggb3BlcmF0aW9uICcke29wZXJhdGlvbk5hbWV9JyAoJHtjbGllbnRUeXBlfSkgYWZ0ZXIgYWxsIHJldHJpZXMuYCk7XG59O1xuXG5cbmV4cG9ydCBjb25zdCBnZXRHb29nbGVBUElUb2tlbiA9IGFzeW5jIChcbiAgICB1c2VySWQ6IHN0cmluZyxcbiAgICBuYW1lOiBzdHJpbmcsXG4gICAgY2xpZW50VHlwZTogJ2lvcycgfCAnYW5kcm9pZCcgfCAnd2ViJyB8ICdhdG9taWMtd2ViJyxcbikgPT4ge1xuICAgIGxldCBpbnRlZ3JhdGlvbklkID0gJyc7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRHb29nbGVBUElUb2tlbic7XG4gICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKGBbJHtvcGVyYXRpb25OYW1lfV0gQ2FsbGVkLmAsIHsgdXNlcklkLCBuYW1lLCBjbGllbnRUeXBlIH0pO1xuXG4gICAgdHJ5IHtcbiAgICAgICAgY29uc3QgaW50ZWdyYXRpb24gPSBhd2FpdCBnZXRDYWxlbmRhckludGVncmF0aW9uQnlOYW1lKHVzZXJJZCwgbmFtZSk7XG5cbiAgICAgICAgaWYgKCFpbnRlZ3JhdGlvbiB8fCAhaW50ZWdyYXRpb24uaWQgfHwgIWludGVncmF0aW9uLnJlZnJlc2hUb2tlbikgeyAvLyBBZGRlZCBjaGVjayBmb3IgcmVmcmVzaFRva2VuXG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKGBbJHtvcGVyYXRpb25OYW1lfV0gQ2FsZW5kYXIgaW50ZWdyYXRpb24gb3IgZXNzZW50aWFsIGRldGFpbHMgbm90IGZvdW5kLmAsIHsgdXNlcklkLCBuYW1lLCBjbGllbnRUeXBlLCBpbnRlZ3JhdGlvbiB9KTtcbiAgICAgICAgICAgIHRocm93IG5ldyBFcnJvcihgQ2FsZW5kYXIgaW50ZWdyYXRpb24gb3IgZXNzZW50aWFsIGRldGFpbHMgbm90IGZvdW5kIGZvciB1c2VyICR7dXNlcklkfSwgbmFtZSAke25hbWV9LmApO1xuICAgICAgICB9XG5cbiAgICAgICAgaW50ZWdyYXRpb25JZCA9IGludGVncmF0aW9uLmlkO1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBbJHtvcGVyYXRpb25OYW1lfV0gUmV0cmlldmVkIGNhbGVuZGFyIGludGVncmF0aW9uLmAsIHsgdXNlcklkLCBuYW1lLCBpbnRlZ3JhdGlvbklkLCBleHBpcmVzQXQ6IGludGVncmF0aW9uLmV4cGlyZXNBdCwgdG9rZW5FeGlzdHM6ICEhaW50ZWdyYXRpb24udG9rZW4gfSk7XG5cbiAgICAgICAgaWYgKGRheWpzKCkuaXNBZnRlcihkYXlqcyhpbnRlZ3JhdGlvbi5leHBpcmVzQXQpKSB8fCAhaW50ZWdyYXRpb24udG9rZW4pIHtcbiAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbyhgWyR7b3BlcmF0aW9uTmFtZX1dIFRva2VuIGV4cGlyZWQgb3IgbWlzc2luZywgYXR0ZW1wdGluZyByZWZyZXNoLmAsIHsgdXNlcklkLCBuYW1lLCBpbnRlZ3JhdGlvbklkIH0pO1xuICAgICAgICAgICAgY29uc3QgcmVmcmVzaFJlc3BvbnNlID0gYXdhaXQgcmVmcmVzaEdvb2dsZVRva2VuKGludGVncmF0aW9uLnJlZnJlc2hUb2tlbiwgY2xpZW50VHlwZSk7XG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYFske29wZXJhdGlvbk5hbWV9XSBUb2tlbiByZWZyZXNoIHN1Y2Nlc3NmdWwuYCwgeyB1c2VySWQsIG5hbWUsIGludGVncmF0aW9uSWQsIG5ld0V4cGlyeUluOiByZWZyZXNoUmVzcG9uc2UuZXhwaXJlc19pbiB9KTtcbiAgICAgICAgICAgIC8vIEVuc3VyZSBleHBpcmVzSW4gaXMgYSBudW1iZXIgZm9yIGRheWpzKCkuYWRkXG4gICAgICAgICAgICBjb25zdCBleHBpcmVzSW5TZWNvbmRzID0gdHlwZW9mIHJlZnJlc2hSZXNwb25zZS5leHBpcmVzX2luID09PSAnbnVtYmVyJyA/IHJlZnJlc2hSZXNwb25zZS5leHBpcmVzX2luIDogcGFyc2VJbnQoU3RyaW5nKHJlZnJlc2hSZXNwb25zZS5leHBpcmVzX2luKSwgMTApO1xuICAgICAgICAgICAgYXdhaXQgdXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbihpbnRlZ3JhdGlvbklkLCByZWZyZXNoUmVzcG9uc2UuYWNjZXNzX3Rva2VuLCBleHBpcmVzSW5TZWNvbmRzKTtcbiAgICAgICAgICAgIHJldHVybiByZWZyZXNoUmVzcG9uc2UuYWNjZXNzX3Rva2VuO1xuICAgICAgICB9XG5cbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5kZWJ1ZyhgWyR7b3BlcmF0aW9uTmFtZX1dIEV4aXN0aW5nIHRva2VuIGlzIHZhbGlkLmAsIHsgdXNlcklkLCBuYW1lLCBpbnRlZ3JhdGlvbklkIH0pO1xuICAgICAgICByZXR1cm4gaW50ZWdyYXRpb24udG9rZW47XG5cbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoYFske29wZXJhdGlvbk5hbWV9XSBGYWlsZWQgdG8gZ2V0L3JlZnJlc2ggR29vZ2xlIEFQSSB0b2tlbi5gLCB7IHVzZXJJZCwgbmFtZSwgY2xpZW50VHlwZSwgaW50ZWdyYXRpb25JZE9uRXJyb3I6IGludGVncmF0aW9uSWQsIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSwgc3RhY2s6IChlIGFzIEVycm9yKS5zdGFjayB9KTtcblxuICAgICAgICBpZiAoaW50ZWdyYXRpb25JZCkge1xuICAgICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYFske29wZXJhdGlvbk5hbWV9XSBBdHRlbXB0aW5nIHRvIGRpc2FibGUgY2FsZW5kYXIgaW50ZWdyYXRpb24gZHVlIHRvIGVycm9yLmAsIHsgaW50ZWdyYXRpb25JZCB9KTtcbiAgICAgICAgICAgICAgICBhd2FpdCB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uKGludGVncmF0aW9uSWQsIHVuZGVmaW5lZCwgdW5kZWZpbmVkLCBmYWxzZSk7XG4gICAgICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKGBbJHtvcGVyYXRpb25OYW1lfV0gU3VjY2Vzc2Z1bGx5IGRpc2FibGVkIGNhbGVuZGFyIGludGVncmF0aW9uLmAsIHsgaW50ZWdyYXRpb25JZCB9KTtcbiAgICAgICAgICAgIH0gY2F0Y2ggKGRpc2FibGVFcnJvcikge1xuICAgICAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoYFske29wZXJhdGlvbk5hbWV9XSBGYWlsZWQgdG8gZGlzYWJsZSBjYWxlbmRhciBpbnRlZ3JhdGlvbiBhZnRlciBhbiBlcnJvci5gLCB7IGludGVncmF0aW9uSWQsIGRpc2FibGVFcnJvcjogKGRpc2FibGVFcnJvciBhcyBFcnJvcikubWVzc2FnZSwgc3RhY2s6IChkaXNhYmxlRXJyb3IgYXMgRXJyb3IpLnN0YWNrIH0pO1xuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICAgIHRocm93IGU7IC8vIFJlLXRocm93IG9yaWdpbmFsIGVycm9yIHRvIGVuc3VyZSBmYWlsdXJlIGlzIHByb3BhZ2F0ZWRcbiAgICB9XG59XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVHb29nbGVFdmVudCA9IGFzeW5jIChcbiAgICB1c2VySWQ6IHN0cmluZyxcbiAgICBjYWxlbmRhcklkOiBzdHJpbmcsXG4gICAgY2xpZW50VHlwZTogJ2lvcycgfCAnYW5kcm9pZCcgfCAnd2ViJyB8ICdhdG9taWMtd2ViJyxcbiAgICBnZW5lcmF0ZWRJZD86IHN0cmluZyxcbiAgICBlbmREYXRlVGltZT86IHN0cmluZywgLy8gZWl0aGVyIGVuZERhdGVUaW1lIG9yIGVuZERhdGUgLSBhbGwgZGF5IHZzIHNwZWNpZmljIHBlcmlvZFxuICAgIHN0YXJ0RGF0ZVRpbWU/OiBzdHJpbmcsXG4gICAgY29uZmVyZW5jZURhdGFWZXJzaW9uPzogMCB8IDEsXG4gICAgbWF4QXR0ZW5kZWVzPzogbnVtYmVyLFxuICAgIHNlbmRVcGRhdGVzPzogR29vZ2xlU2VuZFVwZGF0ZXNUeXBlLFxuICAgIGFueW9uZUNhbkFkZFNlbGY/OiBib29sZWFuLFxuICAgIGF0dGVuZGVlcz86IEdvb2dsZUF0dGVuZGVlVHlwZVtdLFxuICAgIGNvbmZlcmVuY2VEYXRhPzogR29vZ2xlQ29uZmVyZW5jZURhdGFUeXBlLFxuICAgIHN1bW1hcnk/OiBzdHJpbmcsXG4gICAgZGVzY3JpcHRpb24/OiBzdHJpbmcsXG4gICAgdGltZXpvbmU/OiBzdHJpbmcsIC8vIHJlcXVpcmVkIGZvciByZWN1cnJlbmNlXG4gICAgc3RhcnREYXRlPzogc3RyaW5nLCAvLyBhbGwgZGF5XG4gICAgZW5kRGF0ZT86IHN0cmluZywgLy8gYWxsIGRheVxuICAgIGV4dGVuZGVkUHJvcGVydGllcz86IEdvb2dsZUV4dGVuZGVkUHJvcGVydGllc1R5cGUsXG4gICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzPzogYm9vbGVhbixcbiAgICBndWVzdHNDYW5Nb2RpZnk/OiBib29sZWFuLFxuICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzPzogYm9vbGVhbixcbiAgICBvcmlnaW5hbFN0YXJ0RGF0ZVRpbWU/OiBzdHJpbmcsXG4gICAgb3JpZ2luYWxTdGFydERhdGU/OiBzdHJpbmcsXG4gICAgcmVjdXJyZW5jZT86IHN0cmluZ1tdLFxuICAgIHJlbWluZGVycz86IEdvb2dsZVJlbWluZGVyVHlwZSxcbiAgICBzb3VyY2U/OiBHb29nbGVTb3VyY2VUeXBlLFxuICAgIHN0YXR1cz86IHN0cmluZyxcbiAgICB0cmFuc3BhcmVuY3k/OiBHb29nbGVUcmFuc3BhcmVuY3lUeXBlLFxuICAgIHZpc2liaWxpdHk/OiBHb29nbGVWaXNpYmlsaXR5VHlwZSxcbiAgICBpQ2FsVUlEPzogc3RyaW5nLFxuICAgIGF0dGVuZGVlc09taXR0ZWQ/OiBib29sZWFuLFxuICAgIGhhbmdvdXRMaW5rPzogc3RyaW5nLFxuICAgIHByaXZhdGVDb3B5PzogYm9vbGVhbixcbiAgICBsb2NrZWQ/OiBib29sZWFuLFxuICAgIGF0dGFjaG1lbnRzPzogR29vZ2xlQXR0YWNobWVudFR5cGVbXSxcbiAgICBldmVudFR5cGU/OiBHb29nbGVFdmVudFR5cGUxLFxuICAgIGxvY2F0aW9uPzogc3RyaW5nLFxuICAgIGNvbG9ySWQ/OiBzdHJpbmcsXG4pOiBQcm9taXNlPEdvb2dsZVJlc1R5cGU+ID0+IHsgLy8gQWRkZWQgUHJvbWlzZTxHb29nbGVSZXNUeXBlPiByZXR1cm4gdHlwZSBoaW50XG4gICAgY29uc3Qgb3BlcmF0aW9uX25hbWUgPSBcIkNoYXRDcmVhdGVHb29nbGVFdmVudFwiOyAvLyBGb3IgbG9nZ2luZ1xuICAgIC8vIFdyYXAgdGhlIGVudGlyZSBsb2dpYyBpbiBhc3luYy1yZXRyeVxuICAgIHJldHVybiBhd2FpdCByZXRyeShhc3luYyAoYmFpbCwgYXR0ZW1wdE51bWJlcikgPT4ge1xuICAgICAgdHJ5IHtcbiAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmluZm8oYEF0dGVtcHQgJHthdHRlbXB0TnVtYmVyfSB0byBjcmVhdGUgR29vZ2xlIGV2ZW50IGZvciB1c2VyICR7dXNlcklkfWAsIHsgc3VtbWFyeSB9KTtcbiAgICAgICAgICAvLyBnZXQgdG9rZW5cbiAgICAgICAgICBjb25zdCB0b2tlbiA9IGF3YWl0IGdldEdvb2dsZUFQSVRva2VuKHVzZXJJZCwgZ29vZ2xlQ2FsZW5kYXJOYW1lLCBjbGllbnRUeXBlKTtcbiAgICAgICAgICBpZiAoIXRva2VuKSB7IC8vIGdldEdvb2dsZUFQSVRva2VuIG1pZ2h0IHJldHVybiB1bmRlZmluZWQgb24gZmFpbHVyZSBpZiBub3QgdGhyb3dpbmdcbiAgICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcihgJHtvcGVyYXRpb25fbmFtZX06IEZhaWxlZCB0byBnZXQgR29vZ2xlIEFQSSBUb2tlbiBmb3IgdXNlciAke3VzZXJJZH0gb24gYXR0ZW1wdCAke2F0dGVtcHROdW1iZXJ9LmApO1xuICAgICAgICAgICAgICAvLyBUaGlzIGlzIGEgc2V0dXAgZmFpbHVyZSwgbGlrZWx5IG5vbi1yZXRyeWFibGUgaW4gdGhlIHNob3J0IHRlcm0gYnkgdGhpcyBmdW5jdGlvbi5cbiAgICAgICAgICAgICAgLy8gQmFpbCB0byBwcmV2ZW50IGZ1cnRoZXIgcmV0cmllcyBmb3IgdGhpcyBzcGVjaWZpYyBpc3N1ZS5cbiAgICAgICAgICAgICAgYmFpbChuZXcgRXJyb3IoJ0ZhaWxlZCB0byBhY3F1aXJlIEdvb2dsZSBBUEkgdG9rZW4gZm9yIGV2ZW50IGNyZWF0aW9uLicpKTtcbiAgICAgICAgICAgICAgcmV0dXJuOyAvLyBTaG91bGQgbm90IGJlIHJlYWNoZWQgYXMgYmFpbCB0aHJvd3NcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBjb25zdCBnb29nbGVDYWxlbmRhciA9IGdvb2dsZS5jYWxlbmRhcih7XG4gICAgICAgICAgICAgIHZlcnNpb246ICd2MycsXG4gICAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgIH0pXG5cbiAgICAgICAgICAvLyBjcmVhdGUgcmVxdWVzdCBib2R5IChsb2dpYyByZW1haW5zIHRoZSBzYW1lKVxuICAgICAgICAgIGxldCBkYXRhOiBhbnkgPSB7fVxuXG4gICAgICAgICAgaWYgKGVuZERhdGVUaW1lICYmIHRpbWV6b25lICYmICFlbmREYXRlKSB7XG4gICAgICAgICAgICAgIGNvbnN0IGVuZCA9IHsgZGF0ZVRpbWU6IGVuZERhdGVUaW1lLCB0aW1lWm9uZTogdGltZXpvbmUgfVxuICAgICAgICAgICAgICBkYXRhLmVuZCA9IGVuZFxuICAgICAgICAgIH1cbiAgICAgICAgICBpZiAoZW5kRGF0ZSAmJiB0aW1lem9uZSAmJiAhZW5kRGF0ZVRpbWUpIHtcbiAgICAgICAgICAgICAgY29uc3QgZW5kID0geyBkYXRlOiBkYXlqcyhlbmREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpLCB0aW1lWm9uZTogdGltZXpvbmUgfVxuICAgICAgICAgICAgICBkYXRhLmVuZCA9IGVuZFxuICAgICAgICAgIH1cbiAgICAgICAgICBpZiAoc3RhcnREYXRlICYmIHRpbWV6b25lICYmICFzdGFydERhdGVUaW1lKSB7XG4gICAgICAgICAgICAgIGNvbnN0IHN0YXJ0ID0geyBkYXRlOiBkYXlqcyhzdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KCdZWVlZLU1NLUREJyksIHRpbWVab25lOiB0aW1lem9uZSB9XG4gICAgICAgICAgICAgIGRhdGEuc3RhcnQgPSBzdGFydFxuICAgICAgICAgIH1cbiAgICAgICAgICBpZiAoc3RhcnREYXRlVGltZSAmJiB0aW1lem9uZSAmJiAhc3RhcnREYXRlKSB7XG4gICAgICAgICAgICAgIGNvbnN0IHN0YXJ0ID0geyBkYXRlVGltZTogc3RhcnREYXRlVGltZSwgdGltZVpvbmU6IHRpbWV6b25lIH1cbiAgICAgICAgICAgICAgZGF0YS5zdGFydCA9IHN0YXJ0XG4gICAgICAgICAgfVxuICAgICAgICAgIGlmIChvcmlnaW5hbFN0YXJ0RGF0ZSAmJiB0aW1lem9uZSAmJiAhb3JpZ2luYWxTdGFydERhdGVUaW1lKSB7XG4gICAgICAgICAgICAgIGNvbnN0IG9yaWdpbmFsU3RhcnRUaW1lID0geyBkYXRlOiBkYXlqcyhvcmlnaW5hbFN0YXJ0RGF0ZT8uc2xpY2UoMCwgMTkpKS5mb3JtYXQoJ1lZWVktTU0tREQnKSwgdGltZVpvbmU6IHRpbWV6b25lIH1cbiAgICAgICAgICAgICAgZGF0YS5vcmlnaW5hbFN0YXJ0VGltZSA9IG9yaWdpbmFsU3RhcnRUaW1lXG4gICAgICAgICAgfVxuICAgICAgICAgIGlmIChvcmlnaW5hbFN0YXJ0RGF0ZVRpbWUgJiYgdGltZXpvbmUgJiYgIW9yaWdpbmFsU3RhcnREYXRlKSB7XG4gICAgICAgICAgICAgIGNvbnN0IG9yaWdpbmFsU3RhcnRUaW1lID0geyBkYXRlVGltZTogb3JpZ2luYWxTdGFydERhdGVUaW1lLCB0aW1lWm9uZTogdGltZXpvbmUgfVxuICAgICAgICAgICAgICBkYXRhLm9yaWdpbmFsU3RhcnRUaW1lID0gb3JpZ2luYWxTdGFydFRpbWVcbiAgICAgICAgICB9XG4gICAgICAgICAgaWYgKGFueW9uZUNhbkFkZFNlbGYpIGRhdGEgPSB7IC4uLmRhdGEsIGFueW9uZUNhbkFkZFNlbGYgfVxuICAgICAgICAgIGlmIChhdHRlbmRlZXM/LlswXT8uZW1haWwpIGRhdGEgPSB7IC4uLmRhdGEsIGF0dGVuZGVlcyB9XG4gICAgICAgICAgaWYgKGNvbmZlcmVuY2VEYXRhPy5jcmVhdGVSZXF1ZXN0KSB7XG4gICAgICAgICAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGNvbmZlcmVuY2VEYXRhOiB7IGNyZWF0ZVJlcXVlc3Q6IHsgY29uZmVyZW5jZVNvbHV0aW9uS2V5OiB7IHR5cGU6IGNvbmZlcmVuY2VEYXRhLnR5cGUgfSwgcmVxdWVzdElkOiBjb25mZXJlbmNlRGF0YT8ucmVxdWVzdElkIHx8IHV1aWQoKSB9IH0gfVxuICAgICAgICAgIH0gZWxzZSBpZiAoY29uZmVyZW5jZURhdGE/LmVudHJ5UG9pbnRzPy5bMF0pIHtcbiAgICAgICAgICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgY29uZmVyZW5jZURhdGE6IHsgY29uZmVyZW5jZVNvbHV0aW9uOiB7IGljb25Vcmk6IGNvbmZlcmVuY2VEYXRhPy5pY29uVXJpLCBrZXk6IHsgdHlwZTogY29uZmVyZW5jZURhdGE/LnR5cGUgfSwgbmFtZTogY29uZmVyZW5jZURhdGE/Lm5hbWUgfSwgZW50cnlQb2ludHM6IGNvbmZlcmVuY2VEYXRhPy5lbnRyeVBvaW50cyB9IH1cbiAgICAgICAgICB9XG4gICAgICAgICAgaWYgKGRlc2NyaXB0aW9uPy5sZW5ndGggPiAwKSBkYXRhID0geyAuLi5kYXRhLCBkZXNjcmlwdGlvbiB9XG4gICAgICAgICAgaWYgKGV4dGVuZGVkUHJvcGVydGllcz8ucHJpdmF0ZSB8fCBleHRlbmRlZFByb3BlcnRpZXM/LnNoYXJlZCkgZGF0YSA9IHsgLi4uZGF0YSwgZXh0ZW5kZWRQcm9wZXJ0aWVzIH1cbiAgICAgICAgICBpZiAoZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzKSBkYXRhID0geyAuLi5kYXRhLCBndWVzdHNDYW5JbnZpdGVPdGhlcnMgfVxuICAgICAgICAgIGlmIChndWVzdHNDYW5Nb2RpZnkpIGRhdGEgPSB7IC4uLmRhdGEsIGd1ZXN0c0Nhbk1vZGlmeSB9XG4gICAgICAgICAgaWYgKGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzKSBkYXRhID0geyAuLi5kYXRhLCBndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyB9XG4gICAgICAgICAgaWYgKGxvY2tlZCkgZGF0YSA9IHsgLi4uZGF0YSwgbG9ja2VkIH1cbiAgICAgICAgICBpZiAocHJpdmF0ZUNvcHkpIGRhdGEgPSB7IC4uLmRhdGEsIHByaXZhdGVDb3B5IH1cbiAgICAgICAgICBpZiAocmVjdXJyZW5jZT8uWzBdKSBkYXRhID0geyAuLi5kYXRhLCByZWN1cnJlbmNlIH1cbiAgICAgICAgICBpZiAoKHJlbWluZGVycz8ub3ZlcnJpZGVzPy5sZW5ndGggPiAwKSB8fCAocmVtaW5kZXJzPy51c2VEZWZhdWx0KSkgZGF0YSA9IHsgLi4uZGF0YSwgcmVtaW5kZXJzIH1cbiAgICAgICAgICBpZiAoc291cmNlPy50aXRsZSB8fCBzb3VyY2U/LnVybCkgZGF0YSA9IHsgLi4uZGF0YSwgc291cmNlIH1cbiAgICAgICAgICBpZiAoYXR0YWNobWVudHM/LlswXT8uZmlsZUlkKSBkYXRhID0geyAuLi5kYXRhLCBhdHRhY2htZW50cyB9XG4gICAgICAgICAgaWYgKGV2ZW50VHlwZT8ubGVuZ3RoID4gMCkgZGF0YSA9IHsgLi4uZGF0YSwgZXZlbnRUeXBlIH1cbiAgICAgICAgICBpZiAoc3RhdHVzKSBkYXRhID0geyAuLi5kYXRhLCBzdGF0dXMgfVxuICAgICAgICAgIGlmICh0cmFuc3BhcmVuY3kpIGRhdGEgPSB7IC4uLmRhdGEsIHRyYW5zcGFyZW5jeSB9XG4gICAgICAgICAgaWYgKHZpc2liaWxpdHkpIGRhdGEgPSB7IC4uLmRhdGEsIHZpc2liaWxpdHkgfVxuICAgICAgICAgIGlmIChpQ2FsVUlEPy5sZW5ndGggPiAwKSBkYXRhID0geyAuLi5kYXRhLCBpQ2FsVUlEIH1cbiAgICAgICAgICBpZiAoYXR0ZW5kZWVzT21pdHRlZCkgZGF0YSA9IHsgLi4uZGF0YSwgYXR0ZW5kZWVzT21pdHRlZCB9XG4gICAgICAgICAgaWYgKGhhbmdvdXRMaW5rPy5sZW5ndGggPiAwKSBkYXRhID0geyAuLi5kYXRhLCBoYW5nb3V0TGluayB9XG4gICAgICAgICAgaWYgKHN1bW1hcnk/Lmxlbmd0aCA+IDApIGRhdGEgPSB7IC4uLmRhdGEsIHN1bW1hcnkgfVxuICAgICAgICAgIGlmIChsb2NhdGlvbj8ubGVuZ3RoID4gMCkgZGF0YSA9IHsgLi4uZGF0YSwgbG9jYXRpb24gfVxuICAgICAgICAgIGlmIChjb2xvcklkKSBkYXRhLmNvbG9ySWQgPSBjb2xvcklkXG5cbiAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKGBHb29nbGUgQ2FsZW5kYXIgY3JlYXRlIHJlcXVlc3QgYm9keSBmb3IgdXNlciAke3VzZXJJZH0gKGF0dGVtcHQgJHthdHRlbXB0TnVtYmVyfSlgLCB7IGRhdGEgfSk7XG5cbiAgICAgICAgICBjb25zdCByZXMgPSBhd2FpdCBnb29nbGVDYWxlbmRhci5ldmVudHMuaW5zZXJ0KHtcbiAgICAgICAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgICAgICAgICAgY29uZmVyZW5jZURhdGFWZXJzaW9uLFxuICAgICAgICAgICAgICBtYXhBdHRlbmRlZXMsXG4gICAgICAgICAgICAgIHNlbmRVcGRhdGVzLFxuICAgICAgICAgICAgICByZXF1ZXN0Qm9keTogZGF0YSxcbiAgICAgICAgICB9LCB7IHRpbWVvdXQ6IDIwMDAwIH0pOyAvLyAyMCBzZWNvbmQgdGltZW91dCBwZXIgYXR0ZW1wdFxuXG4gICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKGBHb29nbGUgQ2FsZW5kYXIgZXZlbnQgY3JlYXRlZCBzdWNjZXNzZnVsbHkgb24gYXR0ZW1wdCAke2F0dGVtcHROdW1iZXJ9IGZvciB1c2VyICR7dXNlcklkfTogJHtyZXMuZGF0YS5pZH1gKTtcbiAgICAgICAgICByZXR1cm4geyBpZDogYCR7cmVzPy5kYXRhPy5pZH0jJHtjYWxlbmRhcklkfWAsIGdvb2dsZUV2ZW50SWQ6IHJlcz8uZGF0YT8uaWQsIGdlbmVyYXRlZElkLCBjYWxlbmRhcklkLCBnZW5lcmF0ZWRFdmVudElkOiBnZW5lcmF0ZWRJZD8uc3BsaXQoJyMnKVswXSB9O1xuXG4gICAgICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLndhcm4oYEF0dGVtcHQgJHthdHRlbXB0TnVtYmVyfSB0byBjcmVhdGUgR29vZ2xlIGV2ZW50IGZvciB1c2VyICR7dXNlcklkfSBmYWlsZWQuYCwge1xuICAgICAgICAgICAgZXJyb3I6IGUubWVzc2FnZSwgY29kZTogZS5jb2RlLCBlcnJvcnM6IGUuZXJyb3JzLCBzdW1tYXJ5XG4gICAgICAgICAgfSk7XG4gICAgICAgICAgY29uc3QgaHR0cFN0YXR1c0NvZGUgPSBlLmNvZGU7XG4gICAgICAgICAgY29uc3QgZ29vZ2xlRXJyb3JSZWFzb24gPSBlLmVycm9ycyAmJiBlLmVycm9yc1swXSA/IGUuZXJyb3JzWzBdLnJlYXNvbiA6IG51bGw7XG5cbiAgICAgICAgICBpZiAoaHR0cFN0YXR1c0NvZGUgPT09IDQwMCB8fCBodHRwU3RhdHVzQ29kZSA9PT0gNDAxIHx8IGh0dHBTdGF0dXNDb2RlID09PSA0MDQgfHxcbiAgICAgICAgICAgICAgKGh0dHBTdGF0dXNDb2RlID09PSA0MDMgJiYgZ29vZ2xlRXJyb3JSZWFzb24gIT09ICdyYXRlTGltaXRFeGNlZWRlZCcgJiYgZ29vZ2xlRXJyb3JSZWFzb24gIT09ICd1c2VyUmF0ZUxpbWl0RXhjZWVkZWQnKSkge1xuICAgICAgICAgICAgYmFpbChlKTsgLy8gU3RvcCByZXRyeWluZyBmb3IgdGhlc2UgY2xpZW50IGVycm9yc1xuICAgICAgICAgICAgcmV0dXJuOyAvLyBiYWlsIHdpbGwgdGhyb3dcbiAgICAgICAgICB9XG4gICAgICAgICAgdGhyb3cgZTsgLy8gUmUtdGhyb3cgb3RoZXIgZXJyb3JzIHRvIHRyaWdnZXIgcmV0cnlcbiAgICAgIH1cbiAgICB9LFxuICAgIHtcbiAgICAgIHJldHJpZXM6IDMsXG4gICAgICBmYWN0b3I6IDIsXG4gICAgICBtaW5UaW1lb3V0OiAxMDAwLFxuICAgICAgbWF4VGltZW91dDogMTAwMDAsXG4gICAgICBvblJldHJ5OiAoZXJyb3IsIGF0dGVtcHROdW1iZXIpID0+IHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci53YXJuKGBSZXRyeWluZyBHb29nbGUgZXZlbnQgY3JlYXRpb24gZm9yIHVzZXIgJHt1c2VySWR9LCBhdHRlbXB0ICR7YXR0ZW1wdE51bWJlcn0uIExhc3QgZXJyb3I6ICR7ZXJyb3IubWVzc2FnZX1gLCB7XG4gICAgICAgICAgICBvcGVyYXRpb25fbmFtZTogYCR7b3BlcmF0aW9uX25hbWV9X29uUmV0cnlgLFxuICAgICAgICAgICAgYXR0ZW1wdDogYXR0ZW1wdE51bWJlcixcbiAgICAgICAgICAgIGVycm9yX21lc3NhZ2U6IGVycm9yLm1lc3NhZ2UsXG4gICAgICAgICAgICBlcnJvcl9jb2RlOiBlcnJvci5jb2RlLFxuICAgICAgICAgICAgZXJyb3JfcmVhc29uOiBlcnJvci5lcnJvcnMgJiYgZXJyb3IuZXJyb3JzWzBdID8gZXJyb3IuZXJyb3JzWzBdLnJlYXNvbiA6IG51bGwsXG4gICAgICAgICAgICBzdW1tYXJ5XG4gICAgICAgIH0pO1xuICAgICAgfSxcbiAgICB9KTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcihgRmFpbGVkIHRvIGNyZWF0ZSBHb29nbGUgZXZlbnQgZm9yIHVzZXIgJHt1c2VySWR9IGFmdGVyIGFsbCByZXRyaWVzIG9yIGR1ZSB0byBub24tcmV0cnlhYmxlIGVycm9yLmAsIHtcbiAgICAgIHN1bW1hcnksIGVycm9yOiBlLm1lc3NhZ2UsIGNvZGU6IGUuY29kZSwgZXJyb3JzOiBlLmVycm9ycywgZGV0YWlsczogZS5yZXNwb25zZT8uZGF0YSB8fCBlLmVycm9ycyB8fCBlXG4gICAgfSk7XG4gICAgdGhyb3cgZTtcbiAgfVxufVxuXG5leHBvcnQgY29uc3QgcGF0Y2hHb29nbGVFdmVudCA9IGFzeW5jIChcbiAgICB1c2VySWQ6IHN0cmluZyxcbiAgICBjYWxlbmRhcklkOiBzdHJpbmcsXG4gICAgZXZlbnRJZDogc3RyaW5nLFxuICAgIGNsaWVudFR5cGU6ICdpb3MnIHwgJ2FuZHJvaWQnIHwgJ3dlYicgfCAnYXRvbWljLXdlYicsXG4gICAgZW5kRGF0ZVRpbWU/OiBzdHJpbmcsIC8vIGVpdGhlciBlbmREYXRlVGltZSBvciBlbmREYXRlIC0gYWxsIGRheSB2cyBzcGVjaWZpYyBwZXJpb2RcbiAgICBzdGFydERhdGVUaW1lPzogc3RyaW5nLFxuICAgIGNvbmZlcmVuY2VEYXRhVmVyc2lvbj86IDAgfCAxLFxuICAgIG1heEF0dGVuZGVlcz86IG51bWJlcixcbiAgICBzZW5kVXBkYXRlcz86IEdvb2dsZVNlbmRVcGRhdGVzVHlwZSxcbiAgICBhbnlvbmVDYW5BZGRTZWxmPzogYm9vbGVhbixcbiAgICBhdHRlbmRlZXM/OiBHb29nbGVBdHRlbmRlZVR5cGVbXSxcbiAgICBjb25mZXJlbmNlRGF0YT86IEdvb2dsZUNvbmZlcmVuY2VEYXRhVHlwZSxcbiAgICBzdW1tYXJ5Pzogc3RyaW5nLFxuICAgIGRlc2NyaXB0aW9uPzogc3RyaW5nLFxuICAgIHRpbWV6b25lPzogc3RyaW5nLCAvLyByZXF1aXJlZCBmb3IgcmVjdXJyZW5jZVxuICAgIHN0YXJ0RGF0ZT86IHN0cmluZyxcbiAgICBlbmREYXRlPzogc3RyaW5nLFxuICAgIGV4dGVuZGVkUHJvcGVydGllcz86IEdvb2dsZUV4dGVuZGVkUHJvcGVydGllc1R5cGUsXG4gICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzPzogYm9vbGVhbixcbiAgICBndWVzdHNDYW5Nb2RpZnk/OiBib29sZWFuLFxuICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzPzogYm9vbGVhbixcbiAgICBvcmlnaW5hbFN0YXJ0RGF0ZVRpbWU/OiBzdHJpbmcsXG4gICAgb3JpZ2luYWxTdGFydERhdGU/OiBzdHJpbmcsXG4gICAgcmVjdXJyZW5jZT86IHN0cmluZ1tdLFxuICAgIHJlbWluZGVycz86IEdvb2dsZVJlbWluZGVyVHlwZSxcbiAgICBzb3VyY2U/OiBHb29nbGVTb3VyY2VUeXBlLFxuICAgIHN0YXR1cz86IHN0cmluZyxcbiAgICB0cmFuc3BhcmVuY3k/OiBHb29nbGVUcmFuc3BhcmVuY3lUeXBlLFxuICAgIHZpc2liaWxpdHk/OiBHb29nbGVWaXNpYmlsaXR5VHlwZSxcbiAgICBpQ2FsVUlEPzogc3RyaW5nLFxuICAgIGF0dGVuZGVlc09taXR0ZWQ/OiBib29sZWFuLFxuICAgIGhhbmdvdXRMaW5rPzogc3RyaW5nLFxuICAgIHByaXZhdGVDb3B5PzogYm9vbGVhbixcbiAgICBsb2NrZWQ/OiBib29sZWFuLFxuICAgIGF0dGFjaG1lbnRzPzogR29vZ2xlQXR0YWNobWVudFR5cGVbXSxcbiAgICBldmVudFR5cGU/OiBHb29nbGVFdmVudFR5cGUxLFxuICAgIGxvY2F0aW9uPzogc3RyaW5nLFxuICAgIGNvbG9ySWQ/OiBzdHJpbmcsXG4pID0+IHtcbiAgICB0cnkge1xuICAgICAgICAvLyBnZXQgdG9rZW4gPVxuICAgICAgICBjb25zdCB0b2tlbiA9IGF3YWl0IGdldEdvb2dsZUFQSVRva2VuKHVzZXJJZCwgZ29vZ2xlQ2FsZW5kYXJOYW1lLCBjbGllbnRUeXBlKVxuICAgICAgICAvLyBsZXQgdXJsID0gYCR7Z29vZ2xlVXJsfS8ke2VuY29kZVVSSShjYWxlbmRhcklkKX0vZXZlbnRzLyR7ZW5jb2RlVVJJKGV2ZW50SWQpfWBcblxuICAgICAgICAvLyBjb25zdCBjb25maWcgPSB7XG4gICAgICAgIC8vICAgaGVhZGVyczoge1xuICAgICAgICAvLyAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Rva2VufWAsXG4gICAgICAgIC8vICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAvLyAgICAgJ0FjY2VwdCc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgLy8gICB9LFxuICAgICAgICAvLyB9XG5cbiAgICAgICAgY29uc3QgZ29vZ2xlQ2FsZW5kYXIgPSBnb29nbGUuY2FsZW5kYXIoe1xuICAgICAgICAgICAgdmVyc2lvbjogJ3YzJyxcbiAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7dG9rZW59YCxcbiAgICAgICAgICAgIH0sXG4gICAgICAgIH0pXG5cbiAgICAgICAgbGV0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgICAgICAgLy8gQ2FsZW5kYXIgaWRlbnRpZmllci4gVG8gcmV0cmlldmUgY2FsZW5kYXIgSURzIGNhbGwgdGhlIGNhbGVuZGFyTGlzdC5saXN0IG1ldGhvZC4gSWYgeW91IHdhbnQgdG8gYWNjZXNzIHRoZSBwcmltYXJ5IGNhbGVuZGFyIG9mIHRoZSBjdXJyZW50bHkgbG9nZ2VkIGluIHVzZXIsIHVzZSB0aGUgXCJwcmltYXJ5XCIga2V5d29yZC5cbiAgICAgICAgICAgIGNhbGVuZGFySWQsXG4gICAgICAgICAgICAvLyBWZXJzaW9uIG51bWJlciBvZiBjb25mZXJlbmNlIGRhdGEgc3VwcG9ydGVkIGJ5IHRoZSBBUEkgY2xpZW50LiBWZXJzaW9uIDAgYXNzdW1lcyBubyBjb25mZXJlbmNlIGRhdGEgc3VwcG9ydCBhbmQgaWdub3JlcyBjb25mZXJlbmNlIGRhdGEgaW4gdGhlIGV2ZW50J3MgYm9keS4gVmVyc2lvbiAxIGVuYWJsZXMgc3VwcG9ydCBmb3IgY29weWluZyBvZiBDb25mZXJlbmNlRGF0YSBhcyB3ZWxsIGFzIGZvciBjcmVhdGluZyBuZXcgY29uZmVyZW5jZXMgdXNpbmcgdGhlIGNyZWF0ZVJlcXVlc3QgZmllbGQgb2YgY29uZmVyZW5jZURhdGEuIFRoZSBkZWZhdWx0IGlzIDAuXG4gICAgICAgICAgICBjb25mZXJlbmNlRGF0YVZlcnNpb24sXG4gICAgICAgICAgICAvLyBFdmVudCBpZGVudGlmaWVyLlxuICAgICAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgICAgIC8vIFRoZSBtYXhpbXVtIG51bWJlciBvZiBhdHRlbmRlZXMgdG8gaW5jbHVkZSBpbiB0aGUgcmVzcG9uc2UuIElmIHRoZXJlIGFyZSBtb3JlIHRoYW4gdGhlIHNwZWNpZmllZCBudW1iZXIgb2YgYXR0ZW5kZWVzLCBvbmx5IHRoZSBwYXJ0aWNpcGFudCBpcyByZXR1cm5lZC4gT3B0aW9uYWwuXG4gICAgICAgICAgICBtYXhBdHRlbmRlZXMsXG4gICAgICAgICAgICAvLyBHdWVzdHMgd2hvIHNob3VsZCByZWNlaXZlIG5vdGlmaWNhdGlvbnMgYWJvdXQgdGhlIGV2ZW50IHVwZGF0ZSAoZm9yIGV4YW1wbGUsIHRpdGxlIGNoYW5nZXMsIGV0Yy4pLlxuICAgICAgICAgICAgc2VuZFVwZGF0ZXMsXG4gICAgICAgICAgICAvLyBSZXF1ZXN0IGJvZHkgbWV0YWRhdGFcbiAgICAgICAgICAgIHJlcXVlc3RCb2R5OiB7XG4gICAgICAgICAgICAgICAgLy8gcmVxdWVzdCBib2R5IHBhcmFtZXRlcnNcbiAgICAgICAgICAgICAgICAvLyB7XG4gICAgICAgICAgICAgICAgLy8gICBcImFueW9uZUNhbkFkZFNlbGZcIjogZmFsc2UsXG4gICAgICAgICAgICAgICAgLy8gICBcImF0dGFjaG1lbnRzXCI6IFtdLFxuICAgICAgICAgICAgICAgIC8vICAgXCJhdHRlbmRlZXNcIjogW10sXG4gICAgICAgICAgICAgICAgLy8gICBcImF0dGVuZGVlc09taXR0ZWRcIjogZmFsc2UsXG4gICAgICAgICAgICAgICAgLy8gICBcImNvbG9ySWRcIjogXCJteV9jb2xvcklkXCIsXG4gICAgICAgICAgICAgICAgLy8gICBcImNvbmZlcmVuY2VEYXRhXCI6IHt9LFxuICAgICAgICAgICAgICAgIC8vICAgXCJjcmVhdGVkXCI6IFwibXlfY3JlYXRlZFwiLFxuICAgICAgICAgICAgICAgIC8vICAgXCJjcmVhdG9yXCI6IHt9LFxuICAgICAgICAgICAgICAgIC8vICAgXCJkZXNjcmlwdGlvblwiOiBcIm15X2Rlc2NyaXB0aW9uXCIsXG4gICAgICAgICAgICAgICAgLy8gICBcImVuZFwiOiB7fSxcbiAgICAgICAgICAgICAgICAvLyAgIFwiZW5kVGltZVVuc3BlY2lmaWVkXCI6IGZhbHNlLFxuICAgICAgICAgICAgICAgIC8vICAgXCJldGFnXCI6IFwibXlfZXRhZ1wiLFxuICAgICAgICAgICAgICAgIC8vICAgXCJldmVudFR5cGVcIjogXCJteV9ldmVudFR5cGVcIixcbiAgICAgICAgICAgICAgICAvLyAgIFwiZXh0ZW5kZWRQcm9wZXJ0aWVzXCI6IHt9LFxuICAgICAgICAgICAgICAgIC8vICAgXCJnYWRnZXRcIjoge30sXG4gICAgICAgICAgICAgICAgLy8gICBcImd1ZXN0c0Nhbkludml0ZU90aGVyc1wiOiBmYWxzZSxcbiAgICAgICAgICAgICAgICAvLyAgIFwiZ3Vlc3RzQ2FuTW9kaWZ5XCI6IGZhbHNlLFxuICAgICAgICAgICAgICAgIC8vICAgXCJndWVzdHNDYW5TZWVPdGhlckd1ZXN0c1wiOiBmYWxzZSxcbiAgICAgICAgICAgICAgICAvLyAgIFwiaGFuZ291dExpbmtcIjogXCJteV9oYW5nb3V0TGlua1wiLFxuICAgICAgICAgICAgICAgIC8vICAgXCJodG1sTGlua1wiOiBcIm15X2h0bWxMaW5rXCIsXG4gICAgICAgICAgICAgICAgLy8gICBcImlDYWxVSURcIjogXCJteV9pQ2FsVUlEXCIsXG4gICAgICAgICAgICAgICAgLy8gICBcImlkXCI6IFwibXlfaWRcIixcbiAgICAgICAgICAgICAgICAvLyAgIFwia2luZFwiOiBcIm15X2tpbmRcIixcbiAgICAgICAgICAgICAgICAvLyAgIFwibG9jYXRpb25cIjogXCJteV9sb2NhdGlvblwiLFxuICAgICAgICAgICAgICAgIC8vICAgXCJsb2NrZWRcIjogZmFsc2UsXG4gICAgICAgICAgICAgICAgLy8gICBcIm9yZ2FuaXplclwiOiB7fSxcbiAgICAgICAgICAgICAgICAvLyAgIFwib3JpZ2luYWxTdGFydFRpbWVcIjoge30sXG4gICAgICAgICAgICAgICAgLy8gICBcInByaXZhdGVDb3B5XCI6IGZhbHNlLFxuICAgICAgICAgICAgICAgIC8vICAgXCJyZWN1cnJlbmNlXCI6IFtdLFxuICAgICAgICAgICAgICAgIC8vICAgXCJyZWN1cnJpbmdFdmVudElkXCI6IFwibXlfcmVjdXJyaW5nRXZlbnRJZFwiLFxuICAgICAgICAgICAgICAgIC8vICAgXCJyZW1pbmRlcnNcIjoge30sXG4gICAgICAgICAgICAgICAgLy8gICBcInNlcXVlbmNlXCI6IDAsXG4gICAgICAgICAgICAgICAgLy8gICBcInNvdXJjZVwiOiB7fSxcbiAgICAgICAgICAgICAgICAvLyAgIFwic3RhcnRcIjoge30sXG4gICAgICAgICAgICAgICAgLy8gICBcInN0YXR1c1wiOiBcIm15X3N0YXR1c1wiLFxuICAgICAgICAgICAgICAgIC8vICAgXCJzdW1tYXJ5XCI6IFwibXlfc3VtbWFyeVwiLFxuICAgICAgICAgICAgICAgIC8vICAgXCJ0cmFuc3BhcmVuY3lcIjogXCJteV90cmFuc3BhcmVuY3lcIixcbiAgICAgICAgICAgICAgICAvLyAgIFwidXBkYXRlZFwiOiBcIm15X3VwZGF0ZWRcIixcbiAgICAgICAgICAgICAgICAvLyAgIFwidmlzaWJpbGl0eVwiOiBcIm15X3Zpc2liaWxpdHlcIlxuICAgICAgICAgICAgICAgIC8vIH1cbiAgICAgICAgICAgIH0sXG4gICAgICAgIH1cblxuXG4gICAgICAgIC8vIGNyZWF0ZSByZXF1ZXN0IGJvZHlcbiAgICAgICAgbGV0IHJlcXVlc3RCb2R5OiBhbnkgPSB7fVxuXG5cbiAgICAgICAgaWYgKGVuZERhdGUgJiYgdGltZXpvbmUgJiYgIWVuZERhdGVUaW1lKSB7XG4gICAgICAgICAgICBjb25zdCBlbmQgPSB7XG4gICAgICAgICAgICAgICAgZGF0ZTogZGF5anMoZW5kRGF0ZVRpbWUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERCcpLFxuICAgICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgICAgfVxuICAgICAgICAgICAgcmVxdWVzdEJvZHkuZW5kID0gZW5kXG4gICAgICAgIH1cblxuICAgICAgICAvLyBpZiAoZW5kRGF0ZVRpbWUgJiYgdGltZXpvbmUgJiYgIWVuZERhdGUgJiYgKHJlY3VycmVuY2U/Lmxlbmd0aCA+IDApKSB7XG4gICAgICAgIC8vICAgY29uc3QgZW5kID0ge1xuICAgICAgICAvLyAgICAgZGF0ZVRpbWU6IGRheWpzKGVuZERhdGVUaW1lKS50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLy8gICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpLFxuICAgICAgICAvLyAgICAgdGltZXpvbmVcbiAgICAgICAgLy8gICB9XG4gICAgICAgIC8vICAgcmVxdWVzdEJvZHkuZW5kID0gZW5kXG4gICAgICAgIC8vIH1cblxuICAgICAgICBpZiAoZW5kRGF0ZVRpbWUgJiYgdGltZXpvbmUgJiYgIWVuZERhdGUpIHtcbiAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoJ1twYXRjaEdvb2dsZUV2ZW50XSBTZXR0aW5nIGVuZCBkYXRlVGltZScsIHsgZXZlbnRJZCwgZW5kRGF0ZVRpbWUsIHRpbWV6b25lIH0pO1xuICAgICAgICAgICAgY29uc3QgZW5kID0ge1xuICAgICAgICAgICAgICAgIGRhdGVUaW1lOiBlbmREYXRlVGltZSxcbiAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgfVxuICAgICAgICAgICAgcmVxdWVzdEJvZHkuZW5kID0gZW5kXG4gICAgICAgIH1cblxuICAgICAgICBpZiAoc3RhcnREYXRlICYmIHRpbWV6b25lICYmICFzdGFydERhdGVUaW1lKSB7IC8vIEFsbC1kYXkgZXZlbnQgc3RhcnRcbiAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoJ1twYXRjaEdvb2dsZUV2ZW50XSBTZXR0aW5nIHN0YXJ0IGRhdGUgKGFsbC1kYXkpJywgeyBldmVudElkLCBzdGFydERhdGUsIHRpbWV6b25lIH0pO1xuICAgICAgICAgICAgY29uc3Qgc3RhcnQgPSB7XG4gICAgICAgICAgICAgICAgZGF0ZTogZGF5anMoc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpLCAvLyBFbnN1cmUgY29ycmVjdCBmb3JtYXR0aW5nIGZvciBkYXRlLW9ubHlcbiAgICAgICAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIHJlcXVlc3RCb2R5LnN0YXJ0ID0gc3RhcnRcbiAgICAgICAgfVxuXG4gICAgICAgIC8vIGlmIChzdGFydERhdGVUaW1lICYmIHRpbWV6b25lICYmICFzdGFydERhdGUgJiYgKHJlY3VycmVuY2U/Lmxlbmd0aCA+IDApKSB7XG4gICAgICAgIC8vICAgY29uc3Qgc3RhcnQgPSB7XG4gICAgICAgIC8vICAgICBkYXRlVGltZTogZGF5anMoc3RhcnREYXRlVGltZSkudHoodGltZXpvbmUsIHRydWUpLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpLFxuICAgICAgICAvLyAgICAgdGltZXpvbmUsXG4gICAgICAgIC8vICAgfVxuICAgICAgICAvLyAgIHJlcXVlc3RCb2R5LnN0YXJ0ID0gc3RhcnRcbiAgICAgICAgLy8gfVxuXG4gICAgICAgIGlmIChzdGFydERhdGVUaW1lICYmIHRpbWV6b25lICYmICFzdGFydERhdGUpIHsgLy8gU3BlY2lmaWMgdGltZSBldmVudCBzdGFydFxuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5kZWJ1ZygnW3BhdGNoR29vZ2xlRXZlbnRdIFNldHRpbmcgc3RhcnQgZGF0ZVRpbWUnLCB7IGV2ZW50SWQsIHN0YXJ0RGF0ZVRpbWUsIHRpbWV6b25lIH0pO1xuICAgICAgICAgICAgY29uc3Qgc3RhcnQgPSB7XG4gICAgICAgICAgICAgICAgZGF0ZVRpbWU6IHN0YXJ0RGF0ZVRpbWUsXG4gICAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICB9XG4gICAgICAgICAgICByZXF1ZXN0Qm9keS5zdGFydCA9IHN0YXJ0XG4gICAgICAgIH1cblxuICAgICAgICBpZiAob3JpZ2luYWxTdGFydERhdGUgJiYgdGltZXpvbmUgJiYgIW9yaWdpbmFsU3RhcnREYXRlVGltZSkge1xuICAgICAgICAgICAgY29uc3Qgb3JpZ2luYWxTdGFydFRpbWUgPSB7XG4gICAgICAgICAgICAgICAgZGF0ZTogZGF5anMob3JpZ2luYWxTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICB9XG4gICAgICAgICAgICByZXF1ZXN0Qm9keS5vcmlnaW5hbFN0YXJ0VGltZSA9IG9yaWdpbmFsU3RhcnRUaW1lXG4gICAgICAgIH1cblxuICAgICAgICBpZiAob3JpZ2luYWxTdGFydERhdGVUaW1lICYmIHRpbWV6b25lICYmICFvcmlnaW5hbFN0YXJ0RGF0ZSkge1xuICAgICAgICAgICAgY29uc3Qgb3JpZ2luYWxTdGFydFRpbWUgPSB7XG4gICAgICAgICAgICAgICAgZGF0ZVRpbWU6IG9yaWdpbmFsU3RhcnREYXRlVGltZSxcbiAgICAgICAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIHJlcXVlc3RCb2R5Lm9yaWdpbmFsU3RhcnRUaW1lID0gb3JpZ2luYWxTdGFydFRpbWVcbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChhbnlvbmVDYW5BZGRTZWxmKSB7XG4gICAgICAgICAgICAvLyBkYXRhID0geyAuLi5kYXRhLCBhbnlvbmVDYW5BZGRTZWxmIH1cbiAgICAgICAgICAgIHJlcXVlc3RCb2R5LmFueW9uZUNhbkFkZFNlbGYgPSBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICAgIH1cblxuICAgICAgICBpZiAoYXR0ZW5kZWVzPy5bMF0/LmVtYWlsKSB7XG4gICAgICAgICAgICAvLyBkYXRhID0geyAuLi5kYXRhLCBhdHRlbmRlZXMgfVxuICAgICAgICAgICAgcmVxdWVzdEJvZHkuYXR0ZW5kZWVzID0gYXR0ZW5kZWVzXG4gICAgICAgIH1cblxuICAgICAgICBpZiAoY29uZmVyZW5jZURhdGE/LmNyZWF0ZVJlcXVlc3QpIHtcbiAgICAgICAgICAgIC8vIGRhdGEgPSB7XG4gICAgICAgICAgICAvLyAgIC4uLmRhdGEsXG4gICAgICAgICAgICAvLyAgIGNvbmZlcmVuY2VEYXRhOiB7XG4gICAgICAgICAgICAvLyAgICAgY3JlYXRlUmVxdWVzdDoge1xuICAgICAgICAgICAgLy8gICAgICAgY29uZmVyZW5jZVNvbHV0aW9uS2V5OiB7XG4gICAgICAgICAgICAvLyAgICAgICAgIHR5cGU6IGNvbmZlcmVuY2VEYXRhLnR5cGVcbiAgICAgICAgICAgIC8vICAgICAgIH0sXG4gICAgICAgICAgICAvLyAgICAgICByZXF1ZXN0SWQ6IGNvbmZlcmVuY2VEYXRhPy5yZXF1ZXN0SWQgfHwgdXVpZHYxKCksXG4gICAgICAgICAgICAvLyAgICAgfVxuICAgICAgICAgICAgLy8gICB9XG4gICAgICAgICAgICAvLyB9XG4gICAgICAgICAgICByZXF1ZXN0Qm9keS5jb25mZXJlbmNlRGF0YSA9IHtcbiAgICAgICAgICAgICAgICBjcmVhdGVSZXF1ZXN0OiB7XG4gICAgICAgICAgICAgICAgICAgIGNvbmZlcmVuY2VTb2x1dGlvbktleToge1xuICAgICAgICAgICAgICAgICAgICAgICAgdHlwZTogY29uZmVyZW5jZURhdGEudHlwZVxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgICAgICByZXF1ZXN0SWQ6IGNvbmZlcmVuY2VEYXRhPy5yZXF1ZXN0SWQgfHwgdXVpZCgpLFxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgfSBlbHNlIGlmIChjb25mZXJlbmNlRGF0YT8uZW50cnlQb2ludHM/LlswXSkge1xuICAgICAgICAgICAgLy8gZGF0YSA9IHtcbiAgICAgICAgICAgIC8vICAgLi4uZGF0YSxcbiAgICAgICAgICAgIC8vICAgY29uZmVyZW5jZURhdGE6IHtcbiAgICAgICAgICAgIC8vICAgICBjb25mZXJlbmNlU29sdXRpb246IHtcbiAgICAgICAgICAgIC8vICAgICAgIGljb25Vcmk6IGNvbmZlcmVuY2VEYXRhPy5pY29uVXJpLFxuICAgICAgICAgICAgLy8gICAgICAga2V5OiB7XG4gICAgICAgICAgICAvLyAgICAgICAgIHR5cGU6IGNvbmZlcmVuY2VEYXRhPy50eXBlLFxuICAgICAgICAgICAgLy8gICAgICAgfSxcbiAgICAgICAgICAgIC8vICAgICAgIG5hbWU6IGNvbmZlcmVuY2VEYXRhPy5uYW1lLFxuICAgICAgICAgICAgLy8gICAgIH0sXG4gICAgICAgICAgICAvLyAgICAgZW50cnlQb2ludHM6IGNvbmZlcmVuY2VEYXRhPy5lbnRyeVBvaW50cyxcbiAgICAgICAgICAgIC8vICAgfSxcbiAgICAgICAgICAgIC8vIH1cbiAgICAgICAgICAgIHJlcXVlc3RCb2R5LmNvbmZlcmVuY2VEYXRhID0ge1xuICAgICAgICAgICAgICAgIGNvbmZlcmVuY2VTb2x1dGlvbjoge1xuICAgICAgICAgICAgICAgICAgICBpY29uVXJpOiBjb25mZXJlbmNlRGF0YT8uaWNvblVyaSxcbiAgICAgICAgICAgICAgICAgICAga2V5OiB7XG4gICAgICAgICAgICAgICAgICAgICAgICB0eXBlOiBjb25mZXJlbmNlRGF0YT8udHlwZSxcbiAgICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICAgICAgbmFtZTogY29uZmVyZW5jZURhdGE/Lm5hbWUsXG4gICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICBlbnRyeVBvaW50czogY29uZmVyZW5jZURhdGE/LmVudHJ5UG9pbnRzLFxuICAgICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKGRlc2NyaXB0aW9uPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgICAvLyBkYXRhID0geyAuLi5kYXRhLCBkZXNjcmlwdGlvbiB9XG4gICAgICAgICAgICByZXF1ZXN0Qm9keS5kZXNjcmlwdGlvbiA9IGRlc2NyaXB0aW9uXG4gICAgICAgIH1cblxuICAgICAgICBpZiAoZXh0ZW5kZWRQcm9wZXJ0aWVzPy5wcml2YXRlIHx8IGV4dGVuZGVkUHJvcGVydGllcz8uc2hhcmVkKSB7XG4gICAgICAgICAgICAvLyBkYXRhID0geyAuLi5kYXRhLCBleHRlbmRlZFByb3BlcnRpZXMgfVxuICAgICAgICAgICAgcmVxdWVzdEJvZHkuZXh0ZW5kZWRQcm9wZXJ0aWVzID0gZXh0ZW5kZWRQcm9wZXJ0aWVzXG4gICAgICAgIH1cblxuICAgICAgICBpZiAoZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzKSB7XG4gICAgICAgICAgICAvLyBkYXRhID0geyAuLi5kYXRhLCBndWVzdHNDYW5JbnZpdGVPdGhlcnMgfVxuICAgICAgICAgICAgcmVxdWVzdEJvZHkuZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzID0gZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzXG4gICAgICAgIH1cblxuICAgICAgICBpZiAoZ3Vlc3RzQ2FuTW9kaWZ5KSB7XG4gICAgICAgICAgICAvLyBkYXRhID0geyAuLi5kYXRhLCBndWVzdHNDYW5Nb2RpZnkgfVxuICAgICAgICAgICAgcmVxdWVzdEJvZHkuZ3Vlc3RzQ2FuTW9kaWZ5ID0gZ3Vlc3RzQ2FuTW9kaWZ5XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMpIHtcbiAgICAgICAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzIH1cbiAgICAgICAgICAgIHJlcXVlc3RCb2R5Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzID0gZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChsb2NrZWQpIHtcbiAgICAgICAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIGxvY2tlZCB9XG4gICAgICAgICAgICByZXF1ZXN0Qm9keS5sb2NrZWQgPSBsb2NrZWRcbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChwcml2YXRlQ29weSkge1xuICAgICAgICAgICAgLy8gZGF0YSA9IHsgLi4uZGF0YSwgcHJpdmF0ZUNvcHkgfVxuICAgICAgICAgICAgcmVxdWVzdEJvZHkucHJpdmF0ZUNvcHkgPSBwcml2YXRlQ29weVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKHJlY3VycmVuY2U/LlswXSkge1xuICAgICAgICAgICAgLy8gZGF0YSA9IHsgLi4uZGF0YSwgcmVjdXJyZW5jZSB9XG4gICAgICAgICAgICByZXF1ZXN0Qm9keS5yZWN1cnJlbmNlID0gcmVjdXJyZW5jZVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKHJlbWluZGVycykge1xuICAgICAgICAgICAgLy8gZGF0YSA9IHsgLi4uZGF0YSwgcmVtaW5kZXJzIH1cbiAgICAgICAgICAgIHJlcXVlc3RCb2R5LnJlbWluZGVycyA9IHJlbWluZGVyc1xuICAgICAgICB9XG5cbiAgICAgICAgaWYgKHNvdXJjZT8udGl0bGUgfHwgc291cmNlPy51cmwpIHtcbiAgICAgICAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIHNvdXJjZSB9XG4gICAgICAgICAgICByZXF1ZXN0Qm9keS5zb3VyY2UgPSBzb3VyY2VcbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChhdHRhY2htZW50cz8uWzBdPy5maWxlSWQpIHtcbiAgICAgICAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIGF0dGFjaG1lbnRzIH1cbiAgICAgICAgICAgIHJlcXVlc3RCb2R5LmF0dGFjaG1lbnRzID0gYXR0YWNobWVudHNcbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChldmVudFR5cGU/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIGV2ZW50VHlwZSB9XG4gICAgICAgICAgICByZXF1ZXN0Qm9keS5ldmVudFR5cGUgPSBldmVudFR5cGVcbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChzdGF0dXMpIHtcbiAgICAgICAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIHN0YXR1cyB9XG4gICAgICAgICAgICByZXF1ZXN0Qm9keS5zdGF0dXMgPSBzdGF0dXNcbiAgICAgICAgfVxuXG4gICAgICAgIGlmICh0cmFuc3BhcmVuY3kpIHtcbiAgICAgICAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIHRyYW5zcGFyZW5jeSB9XG4gICAgICAgICAgICByZXF1ZXN0Qm9keS50cmFuc3BhcmVuY3kgPSB0cmFuc3BhcmVuY3lcbiAgICAgICAgfVxuXG4gICAgICAgIGlmICh2aXNpYmlsaXR5KSB7XG4gICAgICAgICAgICAvLyBkYXRhID0geyAuLi5kYXRhLCB2aXNpYmlsaXR5IH1cbiAgICAgICAgICAgIHJlcXVlc3RCb2R5LnZpc2liaWxpdHkgPSB2aXNpYmlsaXR5XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoaUNhbFVJRD8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgLy8gZGF0YSA9IHsgLi4uZGF0YSwgaUNhbFVJRCB9XG4gICAgICAgICAgICByZXF1ZXN0Qm9keS5pQ2FsVUlEID0gaUNhbFVJRFxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKGF0dGVuZGVlc09taXR0ZWQpIHtcbiAgICAgICAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIGF0dGVuZGVlc09taXR0ZWQgfVxuICAgICAgICAgICAgcmVxdWVzdEJvZHkuYXR0ZW5kZWVzT21pdHRlZCA9IGF0dGVuZGVlc09taXR0ZWRcbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChoYW5nb3V0TGluaz8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgLy8gZGF0YSA9IHsgLi4uZGF0YSwgaGFuZ291dExpbmsgfVxuICAgICAgICAgICAgcmVxdWVzdEJvZHkuaGFuZ291dExpbmsgPSBoYW5nb3V0TGlua1xuICAgICAgICB9XG5cbiAgICAgICAgaWYgKHN1bW1hcnk/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIHN1bW1hcnkgfVxuICAgICAgICAgICAgcmVxdWVzdEJvZHkuc3VtbWFyeSA9IHN1bW1hcnlcbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChsb2NhdGlvbj8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgLy8gZGF0YSA9IHsgLi4uZGF0YSwgbG9jYXRpb24gfVxuICAgICAgICAgICAgcmVxdWVzdEJvZHkubG9jYXRpb24gPSBsb2NhdGlvblxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKGNvbG9ySWQpIHtcbiAgICAgICAgICAgIHJlcXVlc3RCb2R5LmNvbG9ySWQgPSBjb2xvcklkXG4gICAgICAgIH1cblxuICAgICAgICB2YXJpYWJsZXMucmVxdWVzdEJvZHkgPSByZXF1ZXN0Qm9keVxuICAgICAgICAvLyBEbyB0aGUgbWFnaWNcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5kZWJ1ZyhgR29vZ2xlIENhbGVuZGFyIHBhdGNoIHJlcXVlc3QgZm9yIGV2ZW50ICR7ZXZlbnRJZH1gLCB7IHJlcXVlc3RCb2R5OiB2YXJpYWJsZXMucmVxdWVzdEJvZHkgfSk7XG5cbiAgICAgICAgcmV0dXJuIGF3YWl0IHJldHJ5KGFzeW5jIChiYWlsLCBhdHRlbXB0TnVtYmVyKSA9PiB7XG4gICAgICAgICAgICB0cnkge1xuICAgICAgICAgICAgICAgIGNvbnN0IHJlcyA9IGF3YWl0IGdvb2dsZUNhbGVuZGFyLmV2ZW50cy5wYXRjaCh2YXJpYWJsZXMsIHsgdGltZW91dDogMjAwMDAgfSk7IC8vIDIwIHNlY29uZCB0aW1lb3V0XG4gICAgICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKGBHb29nbGUgQ2FsZW5kYXIgZXZlbnQgJHtldmVudElkfSBwYXRjaGVkIHN1Y2Nlc3NmdWxseSBvbiBhdHRlbXB0ICR7YXR0ZW1wdE51bWJlcn0gZm9yIHVzZXIgJHt1c2VySWR9LmApO1xuICAgICAgICAgICAgICAgIC8vIE9yaWdpbmFsIGZ1bmN0aW9uIGRpZG4ndCByZXR1cm4gYW55dGhpbmcsIHNvIHdlIG1haW50YWluIHRoYXQuXG4gICAgICAgICAgICAgICAgcmV0dXJuOyAvLyBFeHBsaWNpdGx5IHJldHVybiB2b2lkIGZvciBzdWNjZXNzIGlmIHRoYXQncyB0aGUgY29udHJhY3RcbiAgICAgICAgICAgIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgICAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIud2FybihgQXR0ZW1wdCAke2F0dGVtcHROdW1iZXJ9IHRvIHBhdGNoIEdvb2dsZSBldmVudCAke2V2ZW50SWR9IGZvciB1c2VyICR7dXNlcklkfSBmYWlsZWQuYCwge1xuICAgICAgICAgICAgICAgICAgICBlcnJvcjogZS5tZXNzYWdlLCBjb2RlOiBlLmNvZGUsIGVycm9yczogZS5lcnJvcnNcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgICBjb25zdCBodHRwU3RhdHVzQ29kZSA9IGUuY29kZTtcbiAgICAgICAgICAgICAgICBjb25zdCBnb29nbGVFcnJvclJlYXNvbiA9IGUuZXJyb3JzICYmIGUuZXJyb3JzWzBdID8gZS5lcnJvcnNbMF0ucmVhc29uIDogbnVsbDtcblxuICAgICAgICAgICAgICAgIGlmIChodHRwU3RhdHVzQ29kZSA9PT0gNDAwIHx8IGh0dHBTdGF0dXNDb2RlID09PSA0MDEgfHwgaHR0cFN0YXR1c0NvZGUgPT09IDQwNCB8fFxuICAgICAgICAgICAgICAgICAgICAoaHR0cFN0YXR1c0NvZGUgPT09IDQwMyAmJiBnb29nbGVFcnJvclJlYXNvbiAhPT0gJ3JhdGVMaW1pdEV4Y2VlZGVkJyAmJiBnb29nbGVFcnJvclJlYXNvbiAhPT0gJ3VzZXJSYXRlTGltaXRFeGNlZWRlZCcpKSB7XG4gICAgICAgICAgICAgICAgICAgIGJhaWwoZSk7XG4gICAgICAgICAgICAgICAgICAgIHJldHVybjtcbiAgICAgICAgICAgICAgICB9O1xuICAgICAgICAgICAgfVxuICAgICAgICAgICAgdGhyb3cgZTtcbiAgICAgICAgfSk7XG4gICAgfTtcbn0gY2F0Y2ggKGUpIHtcbiAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdFcnJvciBpbnNlcnRpbmcgYXR0ZW5kZWVzJywgeyBldmVudElkLCB1c2VySWQsIGF0dGVuZGVlSWRzLCBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UgfSk7XG4gICAgdGhyb3cgZTtcbn1cbn0pO1xufSk7XG59IGNhdGNoIChlKSB7XG4gICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW5zZXJ0aW5nIGF0dGVuZGVlcycsIHsgZXZlbnRJZCwgdXNlcklkLCBhdHRlbmRlZUlkcywgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlIH0pO1xuICAgIHRocm93IGU7XG59XG59O1xufSBjYXRjaCAoZSkge1xuY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gaW5zZXJ0QXR0ZW5kZWVzZm9yRXZlbnQnLCB7IGV2ZW50SWQsIHVzZXJJZCwgYXR0ZW5kZWVJZHMsIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSB9KTtcbnRocm93IGU7XG59XG59XG5cbi8vIEZ1bmN0aW9uIG1pZ2h0IG5lZWQgdG8gYmUgbW9yZSByb2J1c3QuIEV4cGVjdGVkIHJlc3BvbnNlIGZvcm1hdCBhbmQgdHlwZS5cbmV4cG9ydCBjb25zdCBpbnNlcnRBdHRlbmRlZXNmb3JFdmVudCA9IGFzeW5jIChcbiAgICAgICAgICAgIHJldHJpZXM6IDMsXG4gICAgICAgICAgICBmYWN0b3I6IDIsXG4gICAgICAgICAgICBtaW5UaW1lb3V0OiAxMDAwLFxuICAgICAgICAgICAgbWF4VGltZW91dDogMTAwMDAsXG4gICAgICAgICAgICBvblJldHJ5OiAoZXJyb3IsIGF0dGVtcHROdW1iZXIpID0+IHtcbiAgICAgICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLndhcm4oYFJldHJ5aW5nIEdvb2dsZSBldmVudCBwYXRjaCBmb3IgZXZlbnQgJHtldmVudElkfSwgdXNlciAke3VzZXJJZH0sIGF0dGVtcHQgJHthdHRlbXB0TnVtYmVyfS4gRXJyb3I6ICR7ZXJyb3IubWVzc2FnZX1gLCB7XG4gICAgICAgICAgICAgICAgICAgIG9wZXJhdGlvbl9uYW1lOiBgJHtvcGVyYXRpb25fbmFtZX1fb25SZXRyeWAsXG4gICAgICAgICAgICAgICAgICAgIGF0dGVtcHQ6IGF0dGVtcHROdW1iZXIsXG4gICAgICAgICAgICAgICAgICAgIGVycm9yX2NvZGU6IGVycm9yLmNvZGUsXG4gICAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICB9LFxuICAgICAgICB9KTtcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoYEZhaWxlZCB0byBwYXRjaCBHb29nbGUgZXZlbnQgJHtldmVudElkfSBmb3IgdXNlciAke3VzZXJJZH0gYWZ0ZXIgYWxsIHJldHJpZXMuYCwgeyBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UgfSk7XG4gICAgICAgIHRocm93IGU7XG4gICAgfVxufVxuXG5pbnRlcmZhY2UgR290UmVzcG9uc2VXaXRoSnNvbjxUPiB7XG4gICAgYm9keTogc3RyaW5nO1xuICAgIGRhdGE6IFQ7XG59XG5cbmV4cG9ydCBjb25zdCBnZXRFdmVudEZyb21QcmltYXJ5S2V5ID0gYXN5bmMgKGV2ZW50SWQ6IHN0cmluZyk6IFByb21pc2U8RXZlbnRUeXBlPiA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRFdmVudEZyb21QcmltYXJ5S2V5J1xuICAgICAgICBjb25zdCBxdWVyeSA9IGdldEV2ZW50QnlJZFxuICAgICAgICBjb25zdCByZXNwb25zZURhdGEgPSBhd2FpdCByZXNpbGllbnRHb3RQb3N0UG9zdGdyYXBoaWxlKG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB7IGV2ZW50SWQgfSkgYXMgeyBFdmVudF9ieV9wazogRXZlbnRUeXBlIH07XG4gICAgICAgIHJldHVybiByZXNwb25zZURhdGE/LkV2ZW50X2J5X3BrO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gZ2V0RXZlbnRGcm9tUHJpbWFyeUtleScsIHsgZXZlbnRJZCwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlIH0pO1xuICAgICAgICB0aHJvdyBlO1xuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IGdldFRhc2tHaXZlbklkID0gYXN5bmMgKGlkOiBzdHJpbmcpOiBQcm9taXNlPFRhc2tUeXBlPiA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdHZXRUYXNrQnlJZCdcbiAgICAgICAgY29uc3QgcXVlcnkgPSBnZXRUYXNrQnlJZFxuICAgICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGdvdC5wb3N0KFxuICAgICAgICAgICAgcG9zdGdyYXBoaWxlR3JhcGhVcmwsXG4gICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJ1xuICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICAgICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICAgICAgICAgICAgICBpZCxcbiAgICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgfSxcbiAgICAgICAgKS5qc29uKCk7XG4gICAgICAgIGNvbnN0IHJlcyA9IHJlc3BvbnNlIGFzIHsgZGF0YTogeyBUYXNrX2J5X3BrOiBFdmVudFR5cGUgfSB9O1xuICAgICAgICAvLyBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gZ2V0VGFza0dpdmVuSWQnKVxuICAgICAgICAvLyByZXR1cm4gcmVzPy5kYXRhPy5UYXNrX2J5X3BrXG4gICAgICAgIGNvbnN0IHJlc3BvbnNlRGF0YSA9IGF3YWl0IHJlc2lsaWVudEdvdFBvc3RQb3N0Z3JhcGhpbGUob3BlcmF0aW9uTmFtZSwgcXVlcnksIHsgaWQgfSkgYXMgeyBUYXNrX2J5X3BrOiBUYXNrVHlwZSB9OyAvLyBBc3N1bWluZyBhZG1pbiByb2xlIG9yIGFwcHJvcHJpYXRlIGNvbnRleHRcbiAgICAgICAgcmV0dXJuIHJlc3BvbnNlRGF0YT8uVGFza19ieV9waztcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoJ0Vycm9yIGluIGdldFRhc2tHaXZlbklkJywgeyBpZCwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlIH0pO1xuICAgICAgICB0aHJvdyBlO1xuICAgIH1cbn1cblxuXG5leHBvcnQgY29uc3QgY3JlYXRlUHJlQW5kUG9zdEV2ZW50c0Zyb21FdmVudCA9IChldmVudDogRXZlbnRUeXBlLCBidWZmZXJUaW1lOiBCdWZmZXJUaW1lVHlwZSk6IFByZUFuZFBvc3RFdmVudFJldHVyblR5cGUgPT4ge1xuXG4gICAgY29uc3QgZXZlbnRJZCA9IHV1aWQoKVxuICAgIGNvbnN0IGV2ZW50SWQxID0gdXVpZCgpXG5cbiAgICBjb25zdCBwcmVFdmVudElkID0gZXZlbnQ/LnByZUV2ZW50SWQgfHwgYCR7ZXZlbnRJZH0jJHtldmVudD8uY2FsZW5kYXJJZH1gXG4gICAgY29uc3QgcG9zdEV2ZW50SWQgPSBldmVudD8ucG9zdEV2ZW50SWQgfHwgYCR7ZXZlbnRJZDF9IyR7ZXZlbnQ/LmNhbGVuZGFySWR9YFxuXG4gICAgLy8gYXdhaXQgdXBzZXJ0RXZlbnRzKFtiZWZvcmVFdmVudCwgYWZ0ZXJFdmVudF0pXG5cbiAgICBsZXQgdmFsdWVzVG9SZXR1cm46IGFueSA9IHt9XG4gICAgdmFsdWVzVG9SZXR1cm4ubmV3RXZlbnQgPSBldmVudFxuXG4gICAgaWYgKGJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQpIHtcbiAgICAgICAgLy8gY29uc3QgZm9ybWF0dGVkWm9uZUFmdGVyRXZlbnRFbmREYXRlID0gZm9ybWF0SW5UaW1lWm9uZShhZGRNaW51dGVzKHpvbmVkVGltZVRvVXRjKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpLCBldmVudC50aW1lem9uZSksIHByZXZpb3VzRXZlbnQ/LnRpbWVCbG9ja2luZz8uYWZ0ZXJFdmVudCksIGV2ZW50LnRpbWV6b25lLCBcInl5eXktTU0tZGQnVCdISDptbTpzc1hYWFwiKVxuICAgICAgICAvLyBjb25zdCBmb3JtYXR0ZWRab25lQWZ0ZXJFdmVudFN0YXJ0RGF0ZSA9IGZvcm1hdEluVGltZVpvbmUoem9uZWRUaW1lVG9VdGMoZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSksIGV2ZW50LnRpbWV6b25lKSwgZXZlbnQudGltZXpvbmUsIFwieXl5eS1NTS1kZCdUJ0hIOm1tOnNzWFhYXCIpXG5cbiAgICAgICAgY29uc3QgZm9ybWF0dGVkWm9uZUFmdGVyRXZlbnRFbmREYXRlID0gZGF5anMoZXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKS5hZGQoYnVmZmVyVGltZT8uYWZ0ZXJFdmVudCwgJ20nKS5mb3JtYXQoKVxuICAgICAgICBjb25zdCBmb3JtYXR0ZWRab25lQWZ0ZXJFdmVudFN0YXJ0RGF0ZSA9IGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKS50eihldmVudC50aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KClcblxuICAgICAgICBjb25zdCBhZnRlckV2ZW50OiBFdmVudFR5cGUgPSB7XG4gICAgICAgICAgICBpZDogcG9zdEV2ZW50SWQsXG4gICAgICAgICAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICAgICAgICAgIGZvckV2ZW50SWQ6IGV2ZW50LmlkLFxuICAgICAgICAgICAgaXNQb3N0RXZlbnQ6IHRydWUsXG4gICAgICAgICAgICBub3RlczogJ0J1ZmZlciB0aW1lJyxcbiAgICAgICAgICAgIHN1bW1hcnk6ICdCdWZmZXIgdGltZScsXG4gICAgICAgICAgICBzdGFydERhdGU6IGZvcm1hdHRlZFpvbmVBZnRlckV2ZW50U3RhcnREYXRlLFxuICAgICAgICAgICAgZW5kRGF0ZTogZm9ybWF0dGVkWm9uZUFmdGVyRXZlbnRFbmREYXRlLFxuICAgICAgICAgICAgbWV0aG9kOiBldmVudD8ucG9zdEV2ZW50SWQgPyAndXBkYXRlJyA6ICdjcmVhdGUnLFxuICAgICAgICAgICAgdXNlcklkOiBldmVudD8udXNlcklkLFxuICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICAgICAgcHJpb3JpdHk6IDEsXG4gICAgICAgICAgICBpc0ZvbGxvd1VwOiBmYWxzZSxcbiAgICAgICAgICAgIG1vZGlmaWFibGU6IHRydWUsXG4gICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmOiBmYWxzZSxcbiAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyczogZmFsc2UsXG4gICAgICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0czogZmFsc2UsXG4gICAgICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZTogdW5kZWZpbmVkLFxuICAgICAgICAgICAgb3JpZ2luYWxBbGxEYXk6IGZhbHNlLFxuICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICBjYWxlbmRhcklkOiBldmVudD8uY2FsZW5kYXJJZCxcbiAgICAgICAgICAgIHRpbWV6b25lOiBldmVudD8udGltZXpvbmUsXG4gICAgICAgICAgICBldmVudElkOiBwb3N0RXZlbnRJZC5zcGxpdCgnIycpWzBdXG4gICAgICAgIH1cbiAgICAgICAgdmFsdWVzVG9SZXR1cm4uYWZ0ZXJFdmVudCA9IGFmdGVyRXZlbnRcbiAgICAgICAgdmFsdWVzVG9SZXR1cm4ubmV3RXZlbnQgPSB7XG4gICAgICAgICAgICAuLi52YWx1ZXNUb1JldHVybi5uZXdFdmVudCxcbiAgICAgICAgICAgIHBvc3RFdmVudElkLFxuICAgICAgICAgICAgdGltZUJsb2NraW5nOiB7XG4gICAgICAgICAgICAgICAgLi4udmFsdWVzVG9SZXR1cm4/Lm5ld0V2ZW50Py50aW1lQmxvY2tpbmcsXG4gICAgICAgICAgICAgICAgYWZ0ZXJFdmVudDogYnVmZmVyVGltZT8uYWZ0ZXJFdmVudCxcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgIH1cblxuICAgIGlmIChidWZmZXJUaW1lPy5iZWZvcmVFdmVudCkge1xuICAgICAgICBjb25zdCBmb3JtYXR0ZWRab25lQmVmb3JlRXZlbnRTdGFydERhdGUgPSBkYXlqcyhldmVudC5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihldmVudC50aW1lem9uZSwgdHJ1ZSkuc3VidHJhY3QoYnVmZmVyVGltZT8uYmVmb3JlRXZlbnQsICdtJykuZm9ybWF0KClcbiAgICAgICAgY29uc3QgZm9ybWF0dGVkWm9uZUJlZm9yZUV2ZW50RW5kRGF0ZSA9IGRheWpzKGV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGV2ZW50LnRpbWV6b25lLCB0cnVlKS5mb3JtYXQoKVxuXG4gICAgICAgIGNvbnN0IGJlZm9yZUV2ZW50OiBFdmVudFR5cGUgPSB7XG4gICAgICAgICAgICBpZDogcHJlRXZlbnRJZCxcbiAgICAgICAgICAgIGlzUHJlRXZlbnQ6IHRydWUsXG4gICAgICAgICAgICBpc1Bvc3RFdmVudDogZmFsc2UsXG4gICAgICAgICAgICBmb3JFdmVudElkOiBldmVudC5pZCxcbiAgICAgICAgICAgIG5vdGVzOiAnQnVmZmVyIHRpbWUnLFxuICAgICAgICAgICAgc3VtbWFyeTogJ0J1ZmZlciB0aW1lJyxcbiAgICAgICAgICAgIHN0YXJ0RGF0ZTogZm9ybWF0dGVkWm9uZUJlZm9yZUV2ZW50U3RhcnREYXRlLFxuICAgICAgICAgICAgZW5kRGF0ZTogZm9ybWF0dGVkWm9uZUJlZm9yZUV2ZW50RW5kRGF0ZSxcbiAgICAgICAgICAgIG1ldGhvZDogZXZlbnQ/LnByZUV2ZW50SWQgPyAndXBkYXRlJyA6ICdjcmVhdGUnLFxuICAgICAgICAgICAgdXNlcklkOiBldmVudD8udXNlcklkLFxuICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICAgICAgcHJpb3JpdHk6IDEsXG4gICAgICAgICAgICBpc0ZvbGxvd1VwOiBmYWxzZSxcbiAgICAgICAgICAgIG1vZGlmaWFibGU6IHRydWUsXG4gICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmOiBmYWxzZSxcbiAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyczogZmFsc2UsXG4gICAgICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0czogZmFsc2UsXG4gICAgICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZTogdW5kZWZpbmVkLFxuICAgICAgICAgICAgb3JpZ2luYWxBbGxEYXk6IGZhbHNlLFxuICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICBjYWxlbmRhcklkOiBldmVudD8uY2FsZW5kYXJJZCxcbiAgICAgICAgICAgIHRpbWV6b25lOiBldmVudD8udGltZXpvbmUsXG4gICAgICAgICAgICBldmVudElkOiBwcmVFdmVudElkLnNwbGl0KCcjJylbMF1cbiAgICAgICAgfVxuICAgICAgICB2YWx1ZXNUb1JldHVybi5iZWZvcmVFdmVudCA9IGJlZm9yZUV2ZW50XG4gICAgICAgIHZhbHVlc1RvUmV0dXJuLm5ld0V2ZW50ID0ge1xuICAgICAgICAgICAgLi4udmFsdWVzVG9SZXR1cm4ubmV3RXZlbnQsXG4gICAgICAgICAgICBwcmVFdmVudElkLFxuICAgICAgICAgICAgdGltZUJsb2NraW5nOiB7XG4gICAgICAgICAgICAgICAgLi4udmFsdWVzVG9SZXR1cm4/Lm5ld0V2ZW50Py50aW1lQmxvY2tpbmcsXG4gICAgICAgICAgICAgICAgYmVmb3JlRXZlbnQ6IGJ1ZmZlclRpbWU/LmJlZm9yZUV2ZW50LFxuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgfVxuXG4gICAgcmV0dXJuIHZhbHVlc1RvUmV0dXJuXG5cbn1cblxuZXhwb3J0IGNvbnN0IHVwc2VydEF0dGVuZGVlc2ZvckV2ZW50ID0gYXN5bmMgKFxuICAgIGF0dGVuZGVlczogQXR0ZW5kZWVUeXBlW11cbikgPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIC8vIHZhbGlkYXRlXG4gICAgICAgIGlmICghKGF0dGVuZGVlcz8uZmlsdGVyKGEgPT4gISEoYT8uZXZlbnRJZCkpPy5sZW5ndGggPiAwKSkge1xuICAgICAgICAgICAgcmV0dXJuXG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0luc2VydEF0dGVuZGVlc0ZvckV2ZW50J1xuICAgICAgICBjb25zdCBxdWVyeSA9IGluc2VydEF0dGVuZGVlc0ZvckV2ZW50XG4gICAgICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgICAgICAgIGF0dGVuZGVlcyxcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHJlc3BvbnNlOiB7IGRhdGE6IHsgaW5zZXJ0X0F0dGVuZGVlOiB7IGFmZmVjdGVkX3Jvd3M6IG51bWJlciwgcmV0dXJuaW5nOiBBdHRlbmRlZVR5cGVbXSB9IH0gfSA9IGF3YWl0IGdvdC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJ1xuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICAgIH1cblxuICAgICAgICBjb25zdCByZXNwb25zZURhdGEgPSBhd2FpdCByZXNpbGllbnRHb3RQb3N0UG9zdGdyYXBoaWxlKG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB2YXJpYWJsZXMpIGFzIHsgaW5zZXJ0X0F0dGVuZGVlOiB7IHJldHVybmluZzogQXR0ZW5kZWVUeXBlW10gfSB9O1xuICAgICAgICBpZiAocmVzcG9uc2VEYXRhPy5pbnNlcnRfQXR0ZW5kZWU/LnJldHVybmluZykge1xuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKCdTdWNjZXNzZnVsbHkgdXBzZXJ0ZWQgYXR0ZW5kZWVzLicsIHsgY291bnQ6IHJlc3BvbnNlRGF0YS5pbnNlcnRfQXR0ZW5kZWUucmV0dXJuaW5nLmxlbmd0aCB9KTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIud2FybignVXBzZXJ0QXR0ZW5kZWVzZm9yRXZlbnQgY2FsbCB0byBQb3N0Z3JhcGhpbGUgZGlkIG5vdCByZXR1cm4gZXhwZWN0ZWQgZGF0YSBzdHJ1Y3R1cmUuJywgeyByZXNwb25zZURhdGEgfSk7XG4gICAgICAgIH1cbiAgICAgICAgLy8gTm8gcmV0dXJuIHZhbHVlIGluIG9yaWdpbmFsXG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdFcnJvciBpbiB1cHNlcnRBdHRlbmRlZXNmb3JFdmVudCcsIHsgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlIH0pO1xuICAgICAgICB0aHJvdyBlO1xuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IGRlbGV0ZUF0dGVuZGVlc1dpdGhJZHMgPSBhc3luYyAoXG4gICAgZXZlbnRJZHM6IHN0cmluZ1tdLFxuICAgIHVzZXJJZDogc3RyaW5nLFxuKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgLy8gdmFsaWRhdGVcbiAgICAgICAgaWYgKCEoZXZlbnRJZHM/LmZpbHRlcihlID0+ICEhZSk/Lmxlbmd0aCA+IDApKSB7XG4gICAgICAgICAgICByZXR1cm5cbiAgICAgICAgfVxuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKCdFdmVudCBJRHMgZm9yIGF0dGVuZGVlIGRlbGV0aW9uOicsIHsgZXZlbnRJZHMsIHVzZXJJZCwgb3BlcmF0aW9uTmFtZTogJ0RlbGV0ZUF0dGVuZGVlc1dpdGhFdmVudElkcycgfSk7XG4gICAgICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnRGVsZXRlQXR0ZW5kZWVzV2l0aEV2ZW50SWRzJ1xuICAgICAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIG11dGF0aW9uIERlbGV0ZUF0dGVuZGVlc1dpdGhFdmVudElkcygkdXNlcklkOiB1dWlkISwgJGV2ZW50SWRzOiBbU3RyaW5nIV0hKSB7XG4gICAgICAgICAgICAgICAgZGVsZXRlX0F0dGVuZGVlKHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgZXZlbnRJZDoge19pbjogJGV2ZW50SWRzfX0pIHtcbiAgICAgICAgICAgICAgICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgICAgICAgICAgICAgICByZXR1cm5pbmcge1xuICAgICAgICAgICAgICAgICAgICAgICAgYWRkaXRpb25hbEd1ZXN0c1xuICAgICAgICAgICAgICAgICAgICAgICAgY29tbWVudFxuICAgICAgICAgICAgICAgICAgICAgICAgY29udGFjdElkXG4gICAgICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICAgICAgICAgICAgZW1haWxzXG4gICAgICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICAgICAgaW1BZGRyZXNzZXNcbiAgICAgICAgICAgICAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgICAgICAgICAgICAgIG9wdGlvbmFsXG4gICAgICAgICAgICAgICAgICAgICAgICBwaG9uZU51bWJlcnNcbiAgICAgICAgICAgICAgICAgICAgICAgIHJlc291cmNlXG4gICAgICAgICAgICAgICAgICAgICAgICByZXNwb25zZVN0YXR1c1xuICAgICAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cblxuICAgIGBcblxuICAgICAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBldmVudElkcyxcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZ290LnBvc3QocG9zdGdyYXBoaWxlR3JhcGhVcmwsIHtcbiAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLVJvbGUnOiAnYWRtaW4nXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICAgICAgcXVlcnksXG4gICAgICAgICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICAgICAgfVxuICAgICAgICBhd2FpdCByZXNpbGllbnRHb3RQb3N0UG9zdGdyYXBoaWxlKG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB2YXJpYWJsZXMsIHVzZXJJZCk7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbyhgU3VjY2Vzc2Z1bGx5IGRlbGV0ZWQgYXR0ZW5kZWVzIGZvciBldmVudElkczogJHtldmVudElkcy5qb2luKCcsICcpfSBmb3IgdXNlciAke3VzZXJJZH0uYCk7XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdFcnJvciBpbiBkZWxldGVBdHRlbmRlZXNXaXRoSWRzJywgeyB1c2VySWQsIGV2ZW50SWRzLCBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UgfSk7XG4gICAgICAgIHRocm93IGU7XG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgZmluZENvbnRhY3RCeUVtYWlsR2l2ZW5Vc2VySWQgPSBhc3luYyAoXG4gICAgdXNlcklkOiBzdHJpbmcsXG4gICAgZW1haWw6IHN0cmluZyxcbik6IFByb21pc2U8Q29udGFjdFR5cGU+ID0+IHtcbiAgICB0cnkge1xuICAgICAgICAvLyB2YWxpZGF0ZVxuICAgICAgICBpZiAoIXVzZXJJZCkge1xuICAgICAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyB1c2VySWQgcHJvdmlkZWQnKVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKCFlbWFpbCkge1xuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci53YXJuKCdObyBlbWFpbCBwcm92aWRlZCB0byBmaW5kQ29udGFjdEJ5RW1haWxHaXZlblVzZXJJZCcsIHsgdXNlcklkIH0pO1xuICAgICAgICAgICAgcmV0dXJuOyAvLyBPciB0aHJvdyBuZXcgRXJyb3IoJ0VtYWlsIGlzIHJlcXVpcmVkJyk7IGRlcGVuZGluZyBvbiBkZXNpcmVkIHN0cmljdG5lc3NcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnRmluZENvbnRhY3RCeUVtYWlsR2l2ZW5Vc2VySWQnXG4gICAgICAgIGNvbnN0IHF1ZXJ5ID0gZmluZENvbnRhY3RWaWFFbWFpbEJ5VXNlcklkXG5cbiAgICAgICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgZW1haWxGaWx0ZXI6IHtcbiAgICAgICAgICAgICAgICB2YWx1ZTogZW1haWwsXG4gICAgICAgICAgICB9XG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCByZXNwb25zZTogeyBkYXRhOiB7IENvbnRhY3Q6IENvbnRhY3RUeXBlW10gfSB9ID0gYXdhaXQgZ290LnBvc3QocG9zdGdyYXBoaWxlR3JhcGhVcmwsIHtcbiAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLVJvbGUnOiAnYWRtaW4nXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICAgICAgcXVlcnksXG4gICAgICAgICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICAgICAgfVxuICAgICAgICAvLyByZXR1cm4gcmVzcG9uc2U/LmRhdGE/LkNvbnRhY3Q/LlswXVxuICAgICAgICBjb25zdCByZXNwb25zZURhdGEgPSBhd2FpdCByZXNpbGllbnRHb3RQb3N0UG9zdGdyYXBoaWxlKG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB2YXJpYWJsZXMsIHVzZXJJZCkgYXMgeyBDb250YWN0OiBDb250YWN0VHlwZVtdIH07XG4gICAgICAgIHJldHVybiByZXNwb25zZURhdGE/LkNvbnRhY3Q/LlswXTtcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoJ0Vycm9yIGluIGZpbmRDb250YWN0QnlFbWFpbEdpdmVuVXNlcklkJywgeyB1c2VySWQsIGVtYWlsLCBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UgfSk7XG4gICAgICAgIHRocm93IGU7XG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgZ2V0Q29uZmVyZW5jZUdpdmVuSWQgPSBhc3luYyAoXG4gICAgaWQ6IHN0cmluZyxcbik6IFByb21pc2U8Q29uZmVyZW5jZVR5cGU+ID0+IHtcbiAgICB0cnkge1xuICAgICAgICAvLyB2YWxpZGF0ZVxuICAgICAgICBpZiAoIWlkKSB7XG4gICAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIGNvbmZlcmVuY2UgaWQgcHJvdmlkZWQnKVxuICAgICAgICB9XG5cblxuXG4gICAgICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnR2V0Q29uZmVyZW5jZUJ5SWQnXG4gICAgICAgIGNvbnN0IHF1ZXJ5ID0gZ2V0Q29uZmVyZW5jZUJ5SWRcblxuICAgICAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICAgICAgICBpZCxcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHJlc3BvbnNlOiB7IGRhdGE6IHsgQ29uZmVyZW5jZV9ieV9wazogQ29uZmVyZW5jZVR5cGUgfSB9ID0gYXdhaXQgZ290LnBvc3QocG9zdGdyYXBoaWxlR3JhcGhVcmwsIHtcbiAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLVJvbGUnOiAnYWRtaW4nXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICAgICAgcXVlcnksXG4gICAgICAgICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICAgICAgfVxuICAgICAgICAvLyByZXR1cm4gcmVzcG9uc2U/LmRhdGE/LkNvbmZlcmVuY2VfYnlfcGtcbiAgICAgICAgY29uc3QgcmVzcG9uc2VEYXRhID0gYXdhaXQgcmVzaWxpZW50R290UG9zdFBvc3RncmFwaGlsZShvcGVyYXRpb25OYW1lLCBxdWVyeSwgdmFyaWFibGVzKSBhcyB7IENvbmZlcmVuY2VfYnlfcGs6IENvbmZlcmVuY2VUeXBlIH07XG4gICAgICAgIHJldHVybiByZXNwb25zZURhdGE/LkNvbmZlcmVuY2VfYnlfcGs7XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdFcnJvciBpbiBnZXRDb25mZXJlbmNlR2l2ZW5JZCcsIHsgaWQsIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSB9KTtcbiAgICAgICAgdGhyb3cgZTtcbiAgICB9XG59XG5cblxuZXhwb3J0IGNvbnN0IGRlbGV0ZUNvbmZlcmVuY2VHaXZlbklkID0gYXN5bmMgKFxuICAgIGlkOiBzdHJpbmcsXG4pID0+IHtcbiAgICB0cnkge1xuICAgICAgICAvLyB2YWxpZGF0ZVxuICAgICAgICBpZiAoIWlkKSB7XG4gICAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIGNvbmZlcmVuY2UgaWQgcHJvdmlkZWQnKVxuICAgICAgICB9XG5cblxuXG4gICAgICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnRGVsZXRlQ29uZmVyZW5jZUJ5SWQnXG4gICAgICAgIGNvbnN0IHF1ZXJ5ID0gZGVsZXRlQ29uZmVyZW5jZUJ5SWRcblxuICAgICAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICAgICAgICBpZCxcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHJlc3BvbnNlOiB7IGRhdGE6IHsgZGVsZXRlX0NvbmZlcmVuY2VfYnlfcGs6IENvbmZlcmVuY2VUeXBlIH0gfSA9IGF3YWl0IGdvdC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJ1xuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICAgIH1cbiAgICAgICAgLy8gcmV0dXJuIHJlc3BvbnNlPy5kYXRhPy5kZWxldGVfQ29uZmVyZW5jZV9ieV9wa1xuICAgICAgICBjb25zdCByZXNwb25zZURhdGEgPSBhd2FpdCByZXNpbGllbnRHb3RQb3N0UG9zdGdyYXBoaWxlKG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB2YXJpYWJsZXMpIGFzIHsgZGVsZXRlX0NvbmZlcmVuY2VfYnlfcGs6IENvbmZlcmVuY2VUeXBlIH07XG4gICAgICAgIHJldHVybiByZXNwb25zZURhdGE/LmRlbGV0ZV9Db25mZXJlbmNlX2J5X3BrO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gZGVsZXRlQ29uZmVyZW5jZUdpdmVuSWQnLCB7IGlkLCBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UgfSk7XG4gICAgICAgIHRocm93IGU7XG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgZGVsZXRlWm9vbU1lZXRpbmcgPSBhc3luYyAoXG4gICAgem9vbVRva2VuOiBzdHJpbmcsXG4gICAgbWVldGluZ0lkOiBudW1iZXIsXG4gICAgc2NoZWR1bGVGb3JSZW1pbmRlcj86IGJvb2xlYW4sXG4gICAgY2FuY2VsTWVldGluZ1JlbWluZGVyPzogYm9vbGVhbixcbikgPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIGxldCBwYXJhbXM6IGFueSA9IHt9XG4gICAgICAgIGlmIChcbiAgICAgICAgICAgIGNhbmNlbE1lZXRpbmdSZW1pbmRlclxuICAgICAgICAgICAgfHwgc2NoZWR1bGVGb3JSZW1pbmRlclxuICAgICAgICApIHtcblxuICAgICAgICAgICAgaWYgKGNhbmNlbE1lZXRpbmdSZW1pbmRlcikge1xuICAgICAgICAgICAgICAgIHBhcmFtcyA9IHsgY2FuY2VsX21lZXRpbmdfcmVtaW5kZXI6IGNhbmNlbE1lZXRpbmdSZW1pbmRlciB9XG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGlmIChzY2hlZHVsZUZvclJlbWluZGVyKSB7XG4gICAgICAgICAgICAgICAgcGFyYW1zID0geyAuLi5wYXJhbXMsIHNjaGVkdWxlX2Zvcl9yZW1pbmRlcjogc2NoZWR1bGVGb3JSZW1pbmRlciB9XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBzdHJpbmdpZmllZE9iamVjdCA9IE9iamVjdC5rZXlzKHBhcmFtcyk/Lmxlbmd0aCA+IDAgPyBxcy5zdHJpbmdpZnkocGFyYW1zKSA6ICcnXG5cbiAgICAgICAgLy8gaWYgKHN0cmluZ2lmaWVkT2JqZWN0KSB7XG4gICAgICAgIC8vICAgICBhd2FpdCBnb3QuZGVsZXRlKFxuICAgICAgICAvLyAgICAgICAgIGAke3pvb21CYXNlVXJsfS9tZWV0aW5ncy9gICsgbWVldGluZ0lkICsgJz8nICsgc3RyaW5naWZpZWRPYmplY3QsXG4gICAgICAgIC8vICAgICAgICAge1xuICAgICAgICAvLyAgICAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgIC8vICAgICAgICAgICAgICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7em9vbVRva2VufWAsXG4gICAgICAgIC8vICAgICAgICAgICAgICAgICBDb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAvLyAgICAgICAgICAgICB9XG4gICAgICAgIC8vICAgICAgICAgfVxuICAgICAgICAvLyAgICAgKVxuICAgICAgICAvLyB9IGVsc2Uge1xuICAgICAgICAvLyAgICAgYXdhaXQgZ290LmRlbGV0ZShcbiAgICAgICAgLy8gICAgICAgICBgJHt6b29tQmFzZVVybH0vbWVldGluZ3MvYCArIG1lZXRpbmdJZCxcbiAgICAgICAgLy8gICAgICAgICB7XG4gICAgICAgIC8vICAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgLy8gICAgICAgICAgICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt6b29tVG9rZW59YCxcbiAgICAgICAgLy8gICAgICAgICAgICAgICAgIENvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIC8vICAgICAgICAgICAgIH1cbiAgICAgICAgLy8gICAgICAgICB9XG4gICAgICAgIC8vICAgICApXG4gICAgICAgIC8vIH1cbiAgICAgICAgYXdhaXQgcmVzaWxpZW50R290Wm9vbUFwaSgnZGVsZXRlJywgYC9tZWV0aW5ncy8ke21lZXRpbmdJZH1gLCB6b29tVG9rZW4sIHVuZGVmaW5lZCwgcGFyYW1zKTtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKGBTdWNjZXNzZnVsbHkgZGVsZXRlZCBab29tIG1lZXRpbmcgJHttZWV0aW5nSWR9LmApO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gZGVsZXRlWm9vbU1lZXRpbmcnLCB7IG1lZXRpbmdJZCwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlIH0pO1xuICAgICAgICB0aHJvdyBlO1xuICAgIH1cbn1cblxuXG5leHBvcnQgY29uc3QgZGVsZXRlRXZlbnRHaXZlbklkID0gYXN5bmMgKFxuICAgIGlkOiBzdHJpbmcsXG4pID0+IHtcbiAgICB0cnkge1xuICAgICAgICAvLyB2YWxpZGF0ZVxuICAgICAgICBpZiAoIWlkKSB7XG4gICAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIGV2ZW50IGlkIHByb3ZpZGVkJylcbiAgICAgICAgfVxuXG5cblxuICAgICAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0RlbGV0ZUV2ZW50QnlJZCdcbiAgICAgICAgY29uc3QgcXVlcnkgPSBkZWxldGVFdmVudEJ5SWRcblxuICAgICAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICAgICAgICBpZCxcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHJlc3BvbnNlOiB7IGRhdGE6IHsgZGVsZXRlX0V2ZW50X2J5X3BrOiBFdmVudFR5cGUgfSB9ID0gYXdhaXQgZ290LnBvc3QocG9zdGdyYXBoaWxlR3JhcGhVcmwsIHtcbiAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLVJvbGUnOiAnYWRtaW4nXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICAgICAgcXVlcnksXG4gICAgICAgICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICAgICAgfVxuICAgICAgICAvLyByZXR1cm4gcmVzcG9uc2U/LmRhdGE/LmRlbGV0ZV9FdmVudF9ieV9wa1xuICAgICAgICBjb25zdCByZXNwb25zZURhdGEgPSBhd2FpdCByZXNpbGllbnRHb3RQb3N0UG9zdGdyYXBoaWxlKG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB2YXJpYWJsZXMpIGFzIHsgZGVsZXRlX0V2ZW50X2J5X3BrOiBFdmVudFR5cGUgfTtcbiAgICAgICAgcmV0dXJuIHJlc3BvbnNlRGF0YT8uZGVsZXRlX0V2ZW50X2J5X3BrO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gZGVsZXRlRXZlbnRHaXZlbklkJywgeyBpZCwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlIH0pO1xuICAgICAgICB0aHJvdyBlO1xuICAgIH1cbn1cblxuXG5leHBvcnQgY29uc3QgZGVsZXRlR29vZ2xlRXZlbnQgPSBhc3luYyAoXG4gICAgdXNlcklkOiBzdHJpbmcsXG4gICAgY2FsZW5kYXJJZDogc3RyaW5nLFxuICAgIGdvb2dsZUV2ZW50SWQ6IHN0cmluZyxcbiAgICBjbGllbnRUeXBlOiAnaW9zJyB8ICdhbmRyb2lkJyB8ICd3ZWInIHwgJ2F0b21pYy13ZWInLFxuICAgIHNlbmRVcGRhdGVzOiBTZW5kVXBkYXRlc1R5cGUgPSAnYWxsJyxcbikgPT4ge1xuICAgIHRyeSB7XG5cbiAgICAgICAgLy8gZ2V0IHRva2VuID1cbiAgICAgICAgY29uc3QgdG9rZW4gPSBhd2FpdCBnZXRHb29nbGVBUElUb2tlbih1c2VySWQsIGdvb2dsZUNhbGVuZGFyTmFtZSwgY2xpZW50VHlwZSlcblxuXG4gICAgICAgIGNvbnN0IGdvb2dsZUNhbGVuZGFyID0gZ29vZ2xlLmNhbGVuZGFyKHtcbiAgICAgICAgICAgIHZlcnNpb246ICd2MycsXG4gICAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Rva2VufWAsXG4gICAgICAgICAgICB9LFxuICAgICAgICB9KVxuXG4gICAgICAgIGNvbnN0IHJlcyA9IGF3YWl0IGdvb2dsZUNhbGVuZGFyLmV2ZW50cy5kZWxldGUoe1xuICAgICAgICAgICAgLy8gQ2FsZW5kYXIgaWRlbnRpZmllci4gVG8gcmV0cmlldmUgY2FsZW5kYXIgSURzIGNhbGwgdGhlIGNhbGVuZGFyTGlzdC5saXN0IG1ldGhvZC4gSWYgeW91IHdhbnQgdG8gYWNjZXNzIHRoZSBwcmltYXJ5IGNhbGVuZGFyIG9mIHRoZSBjdXJyZW50bHkgbG9nZ2VkIGluIHVzZXIsIHVzZSB0aGUgXCJwcmltYXJ5XCIga2V5d29yZC5cbiAgICAgICAgICAgIGNhbGVuZGFySWQsXG4gICAgICAgICAgICAvLyBFdmVudCBpZGVudGlmaWVyLlxuICAgICAgICAgICAgZXZlbnRJZDogZ29vZ2xlRXZlbnRJZCxcbiAgICAgICAgICAgIC8vIEd1ZXN0cyB3aG8gc2hvdWxkIHJlY2VpdmUgbm90aWZpY2F0aW9ucyBhYm91dCB0aGUgZGVsZXRpb24gb2YgdGhlIGV2ZW50LlxuICAgICAgICAgICAgc2VuZFVwZGF0ZXMsXG4gICAgICAgIH0pO1xuXG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbyhgR29vZ2xlIENhbGVuZGFyIGV2ZW50ICR7Z29vZ2xlRXZlbnRJZH0gZGVsZXRlZCBzdWNjZXNzZnVsbHkgZm9yIHVzZXIgJHt1c2VySWR9LmApO1xuICAgICAgICAvLyBPcmlnaW5hbCBmdW5jdGlvbiBkaWRuJ3QgcmV0dXJuIGFueXRoaW5nLlxuICAgICAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIud2FybihgQXR0ZW1wdCAke2F0dGVtcHROdW1iZXJ9IHRvIGRlbGV0ZSBHb29nbGUgZXZlbnQgJHtnb29nbGVFdmVudElkfSBmb3IgdXNlciAke3VzZXJJZH0gZmFpbGVkLmAsIHtcbiAgICAgICAgICAgIGVycm9yOiBlLm1lc3NhZ2UsIGNvZGU6IGUuY29kZSwgZXJyb3JzOiBlLmVycm9yc1xuICAgICAgICB9KTtcbiAgICAgICAgY29uc3QgaHR0cFN0YXR1c0NvZGUgPSBlLmNvZGU7XG4gICAgICAgIGNvbnN0IGdvb2dsZUVycm9yUmVhc29uID0gZS5lcnJvcnMgJiYgZS5lcnJvcnNbMF0gPyBlLmVycm9yc1swXS5yZWFzb24gOiBudWxsO1xuXG4gICAgICAgIGlmIChodHRwU3RhdHVzQ29kZSA9PT0gNDAwIHx8IGh0dHBTdGF0dXNDb2RlID09PSA0MDEgfHwgLy8gNDA0IGlzIG9mdGVuIHJldHJ5YWJsZSBmb3IgZXZlbnR1YWwgY29uc2lzdGVuY3kgb3IgaWYgZXZlbnQgd2FzIGp1c3QgY3JlYXRlZFxuICAgICAgICAgICAgKGh0dHBTdGF0dXNDb2RlID09PSA0MDMgJiYgZ29vZ2xlRXJyb3JSZWFzb24gIT09ICdyYXRlTGltaXRFeGNlZWRlZCcgJiYgZ29vZ2xlRXJyb3JSZWFzb24gIT09ICd1c2VyUmF0ZUxpbWl0RXhjZWVkZWQnKSkge1xuICAgICAgICAgIGJhaWwoZSk7XG4gICAgICAgICAgcmV0dXJuO1xuICAgICAgICB9XG4gICAgICAgIHRocm93IGU7XG4gICAgICB9XG4gICAgfSwge1xuICAgICAgcmV0cmllczogMyxcbiAgICAgIGZhY3RvcjogMixcbiAgICAgIG1pblRpbWVvdXQ6IDEwMDAsXG4gICAgICBtYXhUaW1lb3V0OiAxMDAwMCxcbiAgICAgIG9uUmV0cnk6IChlcnJvciwgYXR0ZW1wdE51bWJlcikgPT4ge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLndhcm4oYFJldHJ5aW5nIEdvb2dsZSBldmVudCBkZWxldGUgZm9yIGV2ZW50ICR7Z29vZ2xlRXZlbnRJZH0sIHVzZXIgJHt1c2VySWR9LCBhdHRlbXB0ICR7YXR0ZW1wdE51bWJlcn0uIEVycm9yOiAke2Vycm9yLm1lc3NhZ2V9YCwge1xuICAgICAgICAgICAgb3BlcmF0aW9uX25hbWU6IGAke29wZXJhdGlvbl9uYW1lfV9vblJldHJ5YCxcbiAgICAgICAgICAgIGF0dGVtcHQ6IGF0dGVtcHROdW1iZXIsXG4gICAgICAgICAgICBlcnJvcl9jb2RlOiBlcnJvci5jb2RlLFxuICAgICAgICB9KTtcbiAgICAgIH0sXG4gICAgfSk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKGBGYWlsZWQgdG8gZGVsZXRlIEdvb2dsZSBldmVudCAke2dvb2dsZUV2ZW50SWR9IGZvciB1c2VyICR7dXNlcklkfSBhZnRlciBhbGwgcmV0cmllcy5gLCB7IGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSB9KTtcbiAgICB0aHJvdyBlO1xuICB9XG59XG5cbmV4cG9ydCBjb25zdCBnZXRScnVsZUZyZXEgPSAoXG4gICAgZnJlcTogUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGVcbikgPT4ge1xuICAgIHN3aXRjaCAoZnJlcSkge1xuICAgIGNhc2UgJ2RhaWx5JzpcbiAgICAgIHJldHVybiBSUnVsZS5EQUlMWVxuICAgIGNhc2UgJ3dlZWtseSc6XG4gICAgICByZXR1cm4gUlJ1bGUuV0VFS0xZXG4gICAgY2FzZSAnbW9udGhseSc6XG4gICAgICByZXR1cm4gUlJ1bGUuTU9OVEhMWVxuICAgIGNhc2UgJ3llYXJseSc6XG4gICAgICByZXR1cm4gUlJ1bGUuWUVBUkxZXG4gICAgZGVmYXVsdDpcbiAgICAgIHJldHVybiBSUnVsZS5EQUlMWVxuICB9XG59XG5cbmV4cG9ydCBjb25zdCBnZXRSUnVsZURheSA9ICh2YWx1ZTogRGF5T2ZXZWVrVHlwZSkgPT4ge1xuICBzd2l0Y2ggKHZhbHVlKSB7XG4gICAgY2FzZSAnTU8nOlxuICAgICAgcmV0dXJuIFJSdWxlLk1PXG4gICAgY2FzZSAnVFUnOlxuICAgICAgcmV0dXJuIFJSdWxlLlRVXG4gICAgY2FzZSAnV0UnOlxuICAgICAgcmV0dXJuIFJSdWxlLldFXG4gICAgY2FzZSAnVEgnOlxuICAgICAgcmV0dXJuIFJSdWxlLlRIXG4gICAgY2FzZSAnRlInOlxuICAgICAgcmV0dXJuIFJSdWxlLkZSXG4gICAgY2FzZSAnU0EnOlxuICAgICAgcmV0dXJuIFJSdWxlLlNBXG4gICAgY2FzZSAnU1UnOlxuICAgICAgcmV0dXJuIFJSdWxlLlNVXG4gICAgZGVmYXVsdDpcbiAgICAgIHJldHVybiBSUnVsZS5NT1xuICB9XG59XG5cbmV4cG9ydCBjb25zdCBnZXRSUnVsZUJ5V2Vla0RheSA9ICh2YWx1ZTogRGF5T2ZXZWVrVHlwZSB8IHVuZGVmaW5lZCkgPT4ge1xuICBzd2l0Y2ggKHZhbHVlKSB7XG4gICAgY2FzZSAnTU8nOlxuICAgICAgcmV0dXJuIFJSdWxlLk1PXG4gICAgY2FzZSAnVFUnOlxuICAgICAgcmV0dXJuIFJSdWxlLlRVXG4gICAgY2FzZSAnV0UnOlxuICAgICAgcmV0dXJuIFJSdWxlLldFXG4gICAgY2FzZSAnVEgnOlxuICAgICAgcmV0dXJuIFJSdWxlLlRIXG4gICAgY2FzZSAnRlInOlxuICAgICAgcmV0dXJuIFJSdWxlLkZSXG4gICAgY2FzZSAnU0EnOlxuICAgICAgcmV0dXJuIFJSdWxlLlNBXG4gICAgY2FzZSAnU1UnOlxuICAgICAgcmV0dXJuIFJSdWxlLlNVXG4gICAgZGVmYXVsdDpcbiAgICAgIHJldHVybiBSUnVsZS5NT1xuICB9XG59XG5cbmV4cG9ydCBjb25zdCBnZXRSUnVsZURheSA9ICh2YWx1ZTogRGF5T2ZXZWVrVHlwZSkgPT4ge1xuc3dpdGNoICh2YWx1ZSkge1xuICBjYXNlICdNTyc6XG4gICAgcmV0dXJuIFJSdWxlLk1PXG4gIGNhc2UgJ1RVJzpcbiAgICByZXR1cm4gUlJ1bGUuVFVcbiAgY2FzZSAnV0UnOlxuICAgIHJldHVybiBSUnVsZS5XRVxuICBjYXNlICdUSCc6XG4gICAgcmV0dXJuIFJSdWxlLlRIXG4gIGNhc2UgJ0ZSJzpcbiAgICByZXR1cm4gUlJ1bGUuRlJcbiAgY2FzZSAnU0EnOlxuICAgIHJldHVybiBSUnVsZS5TQVxuICBjYXNlICdTVSc6XG4gICAgcmV0dXJuIFJSdWxlLlNVXG4gIGRlZmF1bHQ6XG4gICAgcmV0dXJuIFJSdWxlLk1PXG59XG59XG5cbmV4cG9ydCBjb25zdCBnZXRSUnVsZUJ5V2Vla0RheSA9ICh2YWx1ZTogRGF5T2ZXZWVrVHlwZSB8IHVuZGVmaW5lZCkgPT4ge1xuc3dpdGNoICh2YWx1ZSkge1xuICBjYXNlICdNTyc6XG4gICAgcmV0dXJuIFJSdWxlLk1PXG4gIGNhc2UgJ1RVJzpcbiAgICByZXR1cm4gUlJ1bGUuVFVcbiAgY2FzZSAnV0UnOlxuICAgIHJldHVybiBSUnVsZS5XRVxuICBjYXNlICdUSCc6XG4gICAgcmV0dXJuIFJSdWxlLlRIXG4gIGNhc2UgJ0ZSJzpcbiAgICByZXR1cm4gUlJ1bGUuRlJcbiAgY2FzZSAnU0EnOlxuICAgIHJldHVybiBSUnVsZS5TQVxuICBjYXNlICdTVSc6XG4gICAgcmV0dXJuIFJSdWxlLlNVXG4gIGRlZmF1bHQ6XG4gICAgcmV0dXJuIFJSdWxlLk1PXG59XG59XG5cbmV4cG9ydCBjb25zdCBnZXRHb29nbGVBUElUb2tlbiA9IGFzeW5jIChyZWZyZXNoVG9rZW46IHN0cmluZywgdXNlcklkPzogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgICBjb25zdCBjbGllbnRUeXBlID0gJ3dlYic7XG4gICAgICBjb25zdCB7IHJlZnJlc2hfdG9rZW4sIGFjY2Vzc190b2tlbiwgZXhwaXJlc19pbiwgdG9rZW5fdHlwZSB9ID0gYXdhaXQgcmVmcmVzaEdvb2dsZVRva2VuKHJlZnJlc2hUb2tlbiwgY2xpZW50VHlwZSk7XG4gICAgICByZXR1cm4gYWNjZXNzX3Rva2VuO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgZ2V0dGluZyBHb29nbGUgQVBJIHRva2VuJywgZXJyb3IpO1xuICAgICAgdGhyb3cgZXJyb3I7XG4gIH1cbn07XG5cbmNvbnN0IHJlZnJlc2hHb29nbGVUb2tlbiA9IGFzeW5jIChcbiAgcmVmcmVzaFRva2VuOiBzdHJpbmcsXG4gIGNsaWVudFR5cGU6ICdpb3MnIHwgJ2FuZHJvaWQnIHwgJ3dlYicgfCAnYXRvbWljLXdlYidcbikgPT4ge1xuICB0cnkge1xuICAgICAgLy8gTW9jayBpbXBsZW1lbnRhdGlvbiBmb3IgR29vZ2xlIHRva2VuIHJlZnJlc2hcbiAgICAgIHJldHVybiB7XG4gICAgICAgICAgYWNjZXNzX3Rva2VuOiAnbW9ja19hY2Nlc3NfdG9rZW4nLFxuICAgICAgICAgIHJlZnJlc2hfdG9rZW4sXG4gICAgICAgICAgZXhwaXJlc19pbjogMzYwMCxcbiAgICAgICAgICB0b2tlbl90eXBlOiAnQmVhcmVyJ1xuICAgICAgfTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignRmFpbGVkIHRvIHJlZnJlc2ggR29vZ2xlIHRva2VuJyk7XG4gIH1cbn07XG4gICAgZnJlcTogUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGVcbikgPT4ge1xuICAgIHN3aXRjaCAoZnJlcSkge1xuICAgICAgICBjYXNlICdkYWlseSc6XG4gICAgICAgICAgICByZXR1cm4gUlJ1bGUuREFJTFlcbiAgICAgICAgY2FzZSAnd2Vla2x5JzpcbiAgICAgICAgICAgIHJldHVybiBSUnVsZS5XRUVLTFlcbiAgICAgICAgY2FzZSAnbW9udGhseSc6XG4gICAgICAgICAgICByZXR1cm4gUlJ1bGUuTU9OVEhMWVxuICAgICAgICBjYXNlICd5ZWFybHknOlxuICAgICAgICAgICAgcmV0dXJuIFJSdWxlLllFQVJMWVxuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IGdldFJSdWxlRGF5ID0gKHZhbHVlOiBEYXkgfCB1bmRlZmluZWQpID0+IHtcbiAgICBzd2l0Y2ggKHZhbHVlKSB7XG4gICAgICAgIGNhc2UgRGF5Lk1POlxuICAgICAgICAgICAgcmV0dXJuIFJSdWxlLk1PXG4gICAgICAgIGNhc2UgRGF5LlRVOlxuICAgICAgICAgICAgcmV0dXJuIFJSdWxlLlRVXG4gICAgICAgIGNhc2UgRGF5LldFOlxuICAgICAgICAgICAgcmV0dXJuIFJSdWxlLldFXG4gICAgICAgIGNhc2UgRGF5LlRIOlxuICAgICAgICAgICAgcmV0dXJuIFJSdWxlLlRIXG4gICAgICAgIGNhc2UgRGF5LkZSOlxuICAgICAgICAgICAgcmV0dXJuIFJSdWxlLkZSXG4gICAgICAgIGNhc2UgRGF5LlNBOlxuICAgICAgICAgICAgcmV0dXJuIFJSdWxlLlNBXG4gICAgICAgIGNhc2UgRGF5LlNVOlxuICAgICAgICAgICAgcmV0dXJuIFJSdWxlLlNVXG4gICAgICAgIGRlZmF1bHQ6XG4gICAgICAgICAgICByZXR1cm4gdW5kZWZpbmVkXG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgZ2V0UlJ1bGVCeVdlZWtEYXkgPSAodmFsdWU6IERheU9mV2Vla1R5cGUgfCB1bmRlZmluZWQpID0+IHtcbiAgICBzd2l0Y2ggKHZhbHVlKSB7XG4gICAgICAgIGNhc2UgJ01PJzpcbiAgICAgICAgICAgIHJldHVybiBSUnVsZS5NT1xuICAgICAgICBjYXNlICdUVSc6XG4gICAgICAgICAgICByZXR1cm4gUlJ1bGUuVFVcbiAgICAgICAgY2FzZSAnV0UnOlxuICAgICAgICAgICAgcmV0dXJuIFJSdWxlLldFXG4gICAgICAgIGNhc2UgJ1RIJzpcbiAgICAgICAgICAgIHJldHVybiBSUnVsZS5USFxuICAgICAgICBjYXNlICdGUic6XG4gICAgICAgICAgICByZXR1cm4gUlJ1bGUuRlJcbiAgICAgICAgY2FzZSAnU0EnOlxuICAgICAgICAgICAgcmV0dXJuIFJSdWxlLlNBXG4gICAgICAgIGNhc2UgJ1NVJzpcbiAgICAgICAgICAgIHJldHVybiBSUnVsZS5TVVxuICAgICAgICBkZWZhdWx0OlxuICAgICAgICAgICAgcmV0dXJuIHVuZGVmaW5lZFxuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IGNyZWF0ZVJSdWxlU3RyaW5nID0gKFxuICAgIGZyZXF1ZW5jeTogUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUsXG4gICAgaW50ZXJ2YWw6IG51bWJlcixcbiAgICBieVdlZWtEYXk/OiBEYXlPZldlZWtUeXBlW10gfCBudWxsLFxuICAgIGNvdW50PzogbnVtYmVyIHwgbnVsbCxcbiAgICByZWN1cnJpbmdFbmREYXRlPzogc3RyaW5nLFxuICAgIGJ5TW9udGhEYXk/OiBCeU1vbnRoRGF5VHlwZVtdLFxuKSA9PiB7XG4gICAgaWYgKCghKHJlY3VycmluZ0VuZERhdGU/Lmxlbmd0aCA+IDApICYmICFjb3VudCkgfHwgIWZyZXF1ZW5jeSB8fCAhaW50ZXJ2YWwpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci53YXJuKCdDYW5ub3QgY3JlYXRlIFJSdWxlIHN0cmluZzogcmVjdXJyaW5nRW5kRGF0ZS9jb3VudCBvciBmcmVxdWVuY3kgb3IgaW50ZXJ2YWwgbWlzc2luZy4nLCB7IGhhc1JlY3VycmluZ0VuZERhdGU6ICEhcmVjdXJyaW5nRW5kRGF0ZSwgY291bnQsIGZyZXF1ZW5jeSwgaW50ZXJ2YWwgfSk7XG4gICAgICAgIHJldHVybiB1bmRlZmluZWRcbiAgICB9XG5cbiAgICBjb25zdCBydWxlID0gbmV3IFJSdWxlKHtcbiAgICAgICAgZnJlcTogZ2V0UnJ1bGVGcmVxKGZyZXF1ZW5jeSksXG4gICAgICAgIGludGVydmFsLFxuICAgICAgICB1bnRpbDogZGF5anMocmVjdXJyaW5nRW5kRGF0ZSkudG9EYXRlKCksXG4gICAgICAgIGJ5d2Vla2RheTogYnlXZWVrRGF5Py5tYXAoaSA9PiBnZXRSUnVsZUJ5V2Vla0RheShpKSksXG4gICAgICAgIGNvdW50LFxuICAgICAgICBieW1vbnRoZGF5OiBieU1vbnRoRGF5LFxuICAgIH0pXG5cbiAgICByZXR1cm4gW3J1bGUudG9TdHJpbmcoKV1cbn1cblxuZXhwb3J0IGNvbnN0IHVwc2VydE1lZXRpbmdBc3Npc3RPbmUgPSBhc3luYyAoXG4gICAgbWVldGluZ0Fzc2lzdDogTWVldGluZ0Fzc2lzdFR5cGUsXG4pID0+IHtcbiAgICB0cnkge1xuICAgICAgICAvLyB2YWxpZGF0ZVxuICAgICAgICBpZiAoIW1lZXRpbmdBc3Npc3QpIHtcbiAgICAgICAgICAgIHRocm93IG5ldyBFcnJvcignbm8gbWVldGluZyBhc3Npc3QgcHJvdmlkZWQnKVxuICAgICAgICB9XG5cblxuXG4gICAgICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnSW5zZXJ0TWVldGluZ0Fzc2lzdCdcbiAgICAgICAgY29uc3QgcXVlcnkgPSBpbnNlcnRNZWV0aW5nQXNzaXN0T25lXG5cbiAgICAgICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgICAgICAgbWVldGluZ0Fzc2lzdCxcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHJlc3BvbnNlOiB7IGRhdGE6IHsgaW5zZXJ0X01lZXRpbmdfQXNzaXN0X29uZTogTWVldGluZ0Fzc2lzdFR5cGUgfSB9ID0gYXdhaXQgZ290LnBvc3QocG9zdGdyYXBoaWxlR3JhcGhVcmwsIHtcbiAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLVJvbGUnOiAnYWRtaW4nXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICAgICAgcXVlcnksXG4gICAgICAgICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICAgICAgfVxuICAgICAgICAvLyByZXR1cm4gcmVzcG9uc2U/LmRhdGE/Lmluc2VydF9NZWV0aW5nX0Fzc2lzdF9vbmVcbiAgICAgICAgY29uc3QgcmVzcG9uc2VEYXRhID0gYXdhaXQgcmVzaWxpZW50R290UG9zdFBvc3RncmFwaGlsZShvcGVyYXRpb25OYW1lLCBxdWVyeSwgdmFyaWFibGVzKSBhcyB7IGluc2VydF9NZWV0aW5nX0Fzc2lzdF9vbmU6IE1lZXRpbmdBc3Npc3RUeXBlIH07XG4gICAgICAgIHJldHVybiByZXNwb25zZURhdGE/Lmluc2VydF9NZWV0aW5nX0Fzc2lzdF9vbmU7XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdFcnJvciBpbiB1cHNlcnRNZWV0aW5nQXNzaXN0T25lJywgeyBtZWV0aW5nQXNzaXN0SWQ6IG1lZXRpbmdBc3Npc3Q/LmlkLCBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UgfSk7XG4gICAgICAgIHRocm93IGU7XG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgbGlzdFVzZXJDb250YWN0SW5mb3NHaXZlblVzZXJJZCA9IGFzeW5jIChcbiAgICB1c2VySWQ6IHN0cmluZyxcbikgPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIC8vIHZhbGlkYXRlXG4gICAgICAgIGlmICghdXNlcklkKSB7XG4gICAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIHVzZXJJZCBwcm92aWRlZCcpXG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0xpc3RVc2VyQ29udGFjdEluZm9CeVVzZXJJZCdcbiAgICAgICAgY29uc3QgcXVlcnkgPSBsaXN0VXNlckNvbnRhY3RJbmZvc0J5VXNlcklkXG5cbiAgICAgICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgcmVzcG9uc2U6IHsgZGF0YTogeyBVc2VyX0NvbnRhY3RfSW5mbzogVXNlckNvbnRhY3RJbmZvVHlwZVtdIH0gfSA9IGF3YWl0IGdvdC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJ1xuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICAgIH1cbiAgICAgICAgLy8gcmV0dXJuIHJlc3BvbnNlPy5kYXRhPy5Vc2VyX0NvbnRhY3RfSW5mb1xuICAgICAgICBjb25zdCByZXNwb25zZURhdGEgPSBhd2FpdCByZXNpbGllbnRHb3RQb3N0UG9zdGdyYXBoaWxlKG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB2YXJpYWJsZXMsIHVzZXJJZCkgYXMgeyBVc2VyX0NvbnRhY3RfSW5mbzogVXNlckNvbnRhY3RJbmZvVHlwZVtdIH07XG4gICAgICAgIHJldHVybiByZXNwb25zZURhdGE/LlVzZXJfQ29udGFjdF9JbmZvO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gbGlzdFVzZXJDb250YWN0SW5mb3NHaXZlblVzZXJJZCcsIHsgdXNlcklkLCBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UgfSk7XG4gICAgICAgIHRocm93IGU7XG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgZ2V0VXNlckNvbnRhY3RJbmZvc0dpdmVuSWRzID0gYXN5bmMgKFxuICAgIGlkczogc3RyaW5nW10sXG4pID0+IHtcbiAgICB0cnkge1xuICAgICAgICAvLyB2YWxpZGF0ZVxuICAgICAgICBpZiAoIShpZHM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZygnbm8gaWRzIHByb3ZpZGVkJylcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG5cbiAgICAgICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdHZXRDb250YWN0SW5mb3NXaXRoSWRzJ1xuICAgICAgICBjb25zdCBxdWVyeSA9IGdldENvbnRhY3RJbmZvc0J5SWRzXG5cbiAgICAgICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgICAgICAgaWRzLFxuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgcmVzcG9uc2U6IHsgZGF0YTogeyBVc2VyX0NvbnRhY3RfSW5mbzogVXNlckNvbnRhY3RJbmZvVHlwZVtdIH0gfSA9IGF3YWl0IGdvdC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJ1xuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICAgIH1cbiAgICAgICAgLy8gcmV0dXJuIHJlc3BvbnNlPy5kYXRhPy5Vc2VyX0NvbnRhY3RfSW5mb1xuICAgICAgICBjb25zdCByZXNwb25zZURhdGEgPSBhd2FpdCByZXNpbGllbnRHb3RQb3N0UG9zdGdyYXBoaWxlKG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB2YXJpYWJsZXMpIGFzIHsgVXNlcl9Db250YWN0X0luZm86IFVzZXJDb250YWN0SW5mb1R5cGVbXSB9OyAvLyBBc3N1bWluZyBhZG1pbiBmb3IgdGhpcyBzeXN0ZW0tbGV2ZWwgbG9va3VwXG4gICAgICAgIHJldHVybiByZXNwb25zZURhdGE/LlVzZXJfQ29udGFjdF9JbmZvO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gZ2V0VXNlckNvbnRhY3RJbmZvc0dpdmVuSWRzJywgeyBpZHMsIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSB9KTtcbiAgICAgICAgdGhyb3cgZTtcbiAgICB9XG59XG5cbmV4cG9ydCBjb25zdCBnZXRDb250YWN0QnlOYW1lV2l0aFVzZXJJZCA9IGFzeW5jIChcbiAgICB1c2VySWQ6IHN0cmluZyxcbiAgICBuYW1lOiBzdHJpbmcsXG4pID0+IHtcbiAgICB0cnkge1xuICAgICAgICAvLyB2YWxpZGF0ZVxuICAgICAgICBpZiAoIXVzZXJJZCB8fCAhbmFtZSkge1xuICAgICAgICAgICAgY29uc29sZS5sb2coJ25vIHVzZXJJZCBvciBuYW1lIHByb3ZpZGVkJylcbiAgICAgICAgICAgIHJldHVyblxuICAgICAgICB9XG5cbiAgICAgICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdHZXRDb250YWN0QnlOYW1lRm9yVXNlcklkJ1xuICAgICAgICBjb25zdCBxdWVyeSA9IGdldENvbnRhY3RCeU5hbWVGb3JVc2VySWRcblxuICAgICAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBuYW1lLFxuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgcmVzcG9uc2U6IHsgZGF0YTogeyBDb250YWN0OiBDb250YWN0VHlwZVtdIH0gfSA9IGF3YWl0IGdvdC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJ1xuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICAgIH1cbiAgICAgICAgLy8gcmV0dXJuIHJlc3BvbnNlPy5kYXRhPy5Db250YWN0Py5bMF1cbiAgICAgICAgY29uc3QgcmVzcG9uc2VEYXRhID0gYXdhaXQgcmVzaWxpZW50R290UG9zdFBvc3RncmFwaGlsZShvcGVyYXRpb25OYW1lLCBxdWVyeSwgdmFyaWFibGVzLCB1c2VySWQpIGFzIHsgQ29udGFjdDogQ29udGFjdFR5cGVbXSB9O1xuICAgICAgICByZXR1cm4gcmVzcG9uc2VEYXRhPy5Db250YWN0Py5bMF07XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdFcnJvciBpbiBnZXRDb250YWN0QnlOYW1lV2l0aFVzZXJJZCcsIHsgdXNlcklkLCBuYW1lLCBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UgfSk7XG4gICAgICAgIHRocm93IGU7XG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgaW5zZXJ0TWVldGluZ0Fzc2lzdEF0dGVuZGVlID0gYXN5bmMgKFxuICAgIGF0dGVuZGVlOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlLFxuKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgLy8gdmFsaWRhdGVcbiAgICAgICAgaWYgKCFhdHRlbmRlZSkge1xuICAgICAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBtZWV0aW5nIGFzc2lzdCBwcm92aWRlZCcpXG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0luc2VydE1lZXRpbmdBc3Npc3RBdHRlbmRlZSdcbiAgICAgICAgY29uc3QgcXVlcnkgPSBpbnNlcnRNZWV0aW5nQXNzaXN0QXR0ZW5kZWVPbmVcblxuICAgICAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICAgICAgICBhdHRlbmRlZSxcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHJlc3BvbnNlOiB7IGRhdGE6IHsgaW5zZXJ0X01lZXRpbmdfQXNzaXN0X0F0dGVuZGVlX29uZTogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSB9IH0gPSBhd2FpdCBnb3QucG9zdChwb3N0Z3JhcGhpbGVHcmFwaFVybCwge1xuICAgICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbidcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBqc29uOiB7XG4gICAgICAgICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgICAgICB9XG4gICAgICAgIC8vIHJldHVybiByZXNwb25zZT8uZGF0YT8uaW5zZXJ0X01lZXRpbmdfQXNzaXN0X0F0dGVuZGVlX29uZVxuICAgICAgICBjb25zdCByZXNwb25zZURhdGEgPSBhd2FpdCByZXNpbGllbnRHb3RQb3N0UG9zdGdyYXBoaWxlKG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB2YXJpYWJsZXMpIGFzIHsgaW5zZXJ0X01lZXRpbmdfQXNzaXN0X0F0dGVuZGVlX29uZTogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSB9O1xuICAgICAgICByZXR1cm4gcmVzcG9uc2VEYXRhPy5pbnNlcnRfTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWVfb25lO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gaW5zZXJ0TWVldGluZ0Fzc2lzdEF0dGVuZGVlJywgeyBhdHRlbmRlZUlkOiBhdHRlbmRlZT8uaWQsIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSB9KTtcbiAgICAgICAgdGhyb3cgZTtcbiAgICB9XG59XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVIb3N0QXR0ZW5kZWUgPSBhc3luYyAoXG4gICAgdXNlcklkOiBzdHJpbmcsXG4gICAgbWVldGluZ0lkOiBzdHJpbmcsXG4gICAgdGltZXpvbmU6IHN0cmluZyxcbiAgICBlbWFpbD86IHN0cmluZyxcbiAgICBuYW1lPzogc3RyaW5nLFxuKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgLy8gdmFsaWRhdGVcbiAgICAgICAgaWYgKCFtZWV0aW5nSWQpIHtcbiAgICAgICAgICAgIHRocm93IG5ldyBFcnJvcignbm8gbWVldGluZ0lkIHByb3ZpZGVkJylcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHVzZXJJbmZvSXRlbXMgPSBhd2FpdCBsaXN0VXNlckNvbnRhY3RJbmZvc0dpdmVuVXNlcklkKHVzZXJJZClcblxuICAgICAgICBjb25zdCBhdHRlbmRlZUlkID0gdXVpZCgpXG5cbiAgICAgICAgY29uc3QgcHJpbWFyeUluZm9JdGVtID0gdXNlckluZm9JdGVtcz8uZmluZCh1ID0+ICh1LnByaW1hcnkgJiYgKHUudHlwZSA9PT0gJ2VtYWlsJykpKSB8fCB1c2VySW5mb0l0ZW1zPy5bMF1cblxuICAgICAgICBjb25zdCBob3N0QXR0ZW5kZWU6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGUgPSB7XG4gICAgICAgICAgICBpZDogYXR0ZW5kZWVJZCxcbiAgICAgICAgICAgIG5hbWU6IHByaW1hcnlJbmZvSXRlbT8ubmFtZSB8fCBuYW1lLFxuICAgICAgICAgICAgaG9zdElkOiB1c2VySWQsXG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBlbWFpbHM6IFt7IHByaW1hcnk6IHRydWUsIHZhbHVlOiBwcmltYXJ5SW5mb0l0ZW0/LmlkIHx8IGVtYWlsIHx8ICcnLCB0eXBlOiAnZW1haWwnLCBkaXNwbGF5TmFtZTogcHJpbWFyeUluZm9JdGVtPy5uYW1lIHx8IG5hbWUgfHwgJycgfV0sXG4gICAgICAgICAgICBtZWV0aW5nSWQsXG4gICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgZXh0ZXJuYWxBdHRlbmRlZTogZmFsc2UsXG4gICAgICAgICAgICBwcmltYXJ5RW1haWw6IHByaW1hcnlJbmZvSXRlbT8uaWQgfHwgZW1haWwsXG4gICAgICAgIH1cblxuICAgICAgICBhd2FpdCBpbnNlcnRNZWV0aW5nQXNzaXN0QXR0ZW5kZWUoaG9zdEF0dGVuZGVlKVxuXG4gICAgICAgIHJldHVybiBhdHRlbmRlZUlkXG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdVbmFibGUgdG8gY3JlYXRlIGhvc3QgYXR0ZW5kZWUgZm9yIG5ldyBldmVudCcsIHsgdXNlcklkLCBtZWV0aW5nSWQsIHRpbWV6b25lLCBlbWFpbCwgbmFtZSwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlLCBzdGFjazogKGUgYXMgRXJyb3IpLnN0YWNrIH0pO1xuICAgICAgICByZXR1cm4gdW5kZWZpbmVkO1xuICAgIH1cbn1cblxuXG5leHBvcnQgY29uc3QgdXBzZXJ0TWVldGluZ0Fzc2lzdEludml0ZU1hbnkgPSBhc3luYyAoXG4gICAgbWVldGluZ0Fzc2lzdEludml0ZXM6IE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlW10sXG4pID0+IHtcbiAgICB0cnkge1xuICAgICAgICAvLyB2YWxpZGF0ZVxuICAgICAgICBpZiAoIShtZWV0aW5nQXNzaXN0SW52aXRlcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgICAgICAgIHRocm93IG5ldyBFcnJvcignbm8gbWVldGluZyBhc3Npc3QgaW52aXRlcyBwcm92aWRlZCcpXG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0luc2VydE1lZXRpbmdBc3Npc3RJbnZpdGUnXG4gICAgICAgIGNvbnN0IHF1ZXJ5ID0gdXBzZXJ0TWVldGluZ0Fzc2lzdEludml0ZUdyYXBocWxcblxuICAgICAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICAgICAgICBtZWV0aW5nQXNzaXN0SW52aXRlcyxcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHJlc3BvbnNlOiB7IGRhdGE6IHsgaW5zZXJ0X01lZXRpbmdfQXNzaXN0X0ludml0ZTogTWVldGluZ0Fzc2lzdEludml0ZVR5cGVbXSB9IH0gPSBhd2FpdCBnb3QucG9zdChwb3N0Z3JhcGhpbGVHcmFwaFVybCwge1xuICAgICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbidcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBqc29uOiB7XG4gICAgICAgICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgICAgICB9XG4gICAgICAgIC8vIHJldHVybiByZXNwb25zZT8uZGF0YT8uaW5zZXJ0X01lZXRpbmdfQXNzaXN0X0ludml0ZVxuICAgICAgICBjb25zdCByZXNwb25zZURhdGEgPSBhd2FpdCByZXNpbGllbnRHb3RQb3N0UG9zdGdyYXBoaWxlKG9wZXJhdGlvbk5hbWUsIHF1ZXJ5LCB2YXJpYWJsZXMpIGFzIHsgaW5zZXJ0X01lZXRpbmdfQXNzaXN0X0ludml0ZTogTWVldGluZ0Fzc2lzdEludml0ZVR5cGVbXSB9O1xuICAgICAgICByZXR1cm4gcmVzcG9uc2VEYXRhPy5pbnNlcnRfTWVldGluZ19Bc3Npc3RfSW52aXRlO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gdXBzZXJ0TWVldGluZ0Fzc2lzdEludml0ZU1hbnknLCB7IGludml0ZUNvdW50OiBtZWV0aW5nQXNzaXN0SW52aXRlcz8ubGVuZ3RoLCBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UgfSk7XG4gICAgICAgIHRocm93IGU7XG4gICAgfVxufVxuXG5cbmV4cG9ydCBjb25zdCB1cGRhdGVVc2VyTmFtZUdpdmVuSWQgPSBhc3luYyAoXG4gICAgdXNlcklkOiBzdHJpbmcsXG4gICAgbmFtZTogc3RyaW5nLFxuKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgLy8gdmFsaWRhdGVcbiAgICAgICAgaWYgKCF1c2VySWQgfHwgIW5hbWUpIHtcbiAgICAgICAgICAgIHRocm93IG5ldyBFcnJvcignbm8gbWVldGluZyBhc3Npc3QgaW52aXRlcyBwcm92aWRlZCcpXG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ1VwZGF0ZU5hbWVGb3JVc2VyQnlJZCdcbiAgICAgICAgY29uc3QgcXVlcnkgPSB1cGRhdGVOYW1lRm9yVXNlcklkXG5cbiAgICAgICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgICAgICAgaWQ6IHVzZXJJZCxcbiAgICAgICAgICAgIG5hbWUsXG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCByZXNwb25zZTogeyBkYXRhOiB7IHVwZGF0ZV9Vc2VyX2J5X3BrOiBVc2VyVHlwZSB9IH0gPSBhd2FpdCBnb3QucG9zdChwb3N0Z3JhcGhpbGVHcmFwaFVybCwge1xuICAgICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbidcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBqc29uOiB7XG4gICAgICAgICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgICAgICB9XG4gICAgICAgIC8vIHJldHVybiByZXNwb25zZT8uZGF0YT8udXBkYXRlX1VzZXJfYnlfcGtcbiAgICAgICAgY29uc3QgcmVzcG9uc2VEYXRhID0gYXdhaXQgcmVzaWxpZW50R290UG9zdFBvc3RncmFwaGlsZShvcGVyYXRpb25OYW1lLCBxdWVyeSwgdmFyaWFibGVzKSBhcyB7IHVwZGF0ZV9Vc2VyX2J5X3BrOiBVc2VyVHlwZSB9O1xuICAgICAgICByZXR1cm4gcmVzcG9uc2VEYXRhPy51cGRhdGVfVXNlcl9ieV9waztcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoJ0Vycm9yIGluIHVwZGF0ZVVzZXJOYW1lR2l2ZW5JZCcsIHsgdXNlcklkLCBuYW1lLCBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UgfSk7XG4gICAgICAgIHRocm93IGU7XG4gICAgfVxufVxuXG5leHBvcnQgY29uc3QgZ2V0VXNlckdpdmVuSWQgPSBhc3luYyAoXG4gICAgdXNlcklkOiBzdHJpbmcsXG4pID0+IHtcbiAgICB0cnkge1xuICAgICAgICAvLyB2YWxpZGF0ZVxuICAgICAgICBpZiAoIXVzZXJJZCkge1xuICAgICAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyB1c2VySWQgcHJvdmlkZWQnKVxuICAgICAgICB9XG5cbiAgICAgICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdHZXRVc2VyQnlJZCdcbiAgICAgICAgY29uc3QgcXVlcnkgPSBnZXRVc2VyQnlJZFxuXG4gICAgICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgICAgICAgIGlkOiB1c2VySWQsXG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCByZXNwb25zZTogeyBkYXRhOiB7IFVzZXJfYnlfcGs6IFVzZXJUeXBlIH0gfSA9IGF3YWl0IGdvdC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJ1xuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICAgIH1cbiAgICAgICAgLy8gcmV0dXJuIHJlc3BvbnNlPy5kYXRhPy5Vc2VyX2J5X3BrXG4gICAgICAgIGNvbnN0IHJlc3BvbnNlRGF0YSA9IGF3YWl0IHJlc2lsaWVudEdvdFBvc3RQb3N0Z3JhcGhpbGUob3BlcmF0aW9uTmFtZSwgcXVlcnksIHZhcmlhYmxlcykgYXMgeyBVc2VyX2J5X3BrOiBVc2VyVHlwZSB9O1xuICAgICAgICByZXR1cm4gcmVzcG9uc2VEYXRhPy5Vc2VyX2J5X3BrO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gZ2V0VXNlckdpdmVuSWQnLCB7IHVzZXJJZCwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlIH0pO1xuICAgICAgICB0aHJvdyBlO1xuICAgIH1cbn1cblxuXG5cbmV4cG9ydCBjb25zdCBjYWxsT3BlbkFJV2l0aE1lc3NhZ2VIaXN0b3J5T25seSA9IGFzeW5jIChcbiAgICBvcGVuYWlJbnN0YW5jZTogT3BlbkFJLFxuICAgIG1lc3NhZ2VIaXN0b3J5OiBDaGF0R1BUTWVzc2FnZUhpc3RvcnlUeXBlID0gW10sXG4gICAgbW9kZWw6ICdncHQtMy41LXR1cmJvJyB8ICdncHQtMy41LXR1cmJvLTE2aycgfCAnZ3B0LTQnID0gJ2dwdC0zLjUtdHVyYm8nLFxuKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgLy8gYXNzaXN0YW50XG4gICAgICAgIGNvbnN0IGNvbXBsZXRpb24gPSBhd2FpdCBvcGVuYWkuY2hhdC5jb21wbGV0aW9ucy5jcmVhdGUoe1xuICAgICAgICAgICAgbW9kZWwsXG4gICAgICAgICAgICBtZXNzYWdlczogbWVzc2FnZUhpc3RvcnksXG4gICAgICAgICAgICBtYXhfdG9rZW5zOiAyMDAwLFxuICAgICAgICB9KTtcbiAgICAgICAgcmV0dXJuIGNvbXBsZXRpb24uY2hvaWNlc1swXS5tZXNzYWdlLmNvbnRlbnQ7XG4gICAgICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci53YXJuKGBPcGVuQUkgY2FsbCBmYWlsZWQuIE1vZGVsOiAke21vZGVsfS5gLCB7XG4gICAgICAgICAgICBlcnJvcjogZXJyb3IubWVzc2FnZSwgY29kZTogZXJyb3IuY29kZSwgc3RhdHVzOiBlcnJvci5yZXNwb25zZT8uc3RhdHVzXG4gICAgICAgIH0pO1xuICAgICAgICBpZiAoZXJyb3IucmVzcG9uc2UgJiYgWzQwMCwgNDAxLCA0MDMsIDQwNCwgNDI5XS5pbmNsdWRlcyhlcnJvci5yZXNwb25zZS5zdGF0dXMpKSB7IC8vIEFkZGVkIDQyOSBhcyBwb3RlbnRpYWxseSBub24tcmV0cnlhYmxlIGZvciBzb21lIHF1b3RhIGVycm9yc1xuICAgICAgICAgICAgYmFpbChlcnJvcik7XG4gICAgICAgICAgICByZXR1cm47XG4gICAgICAgIH1cbiAgICAgICAgdGhyb3cgZXJyb3I7XG4gICAgICB9XG4gICAgfSwge1xuICAgICAgICByZXRyaWVzOiAyLCBmYWN0b3I6IDIsIG1pblRpbWVvdXQ6IDEwMDAsIG1heFRpbWVvdXQ6IDUwMDAsXG4gICAgICAgIG9uUmV0cnk6IChlcnJvciwgYXR0ZW1wdE51bWJlcikgPT4ge1xuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci53YXJuKGBSZXRyeWluZyBPcGVuQUkgY2FsbCAoaGlzdG9yeSBvbmx5KSwgYXR0ZW1wdCAke2F0dGVtcHROdW1iZXJ9LiBNb2RlbDogJHttb2RlbH0uIEVycm9yOiAke2Vycm9yLm1lc3NhZ2V9YCk7XG4gICAgICAgIH1cbiAgICB9KTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdGYWlsZWQgT3BlbkFJIGNhbGwgKGhpc3Rvcnkgb25seSkgYWZ0ZXIgYWxsIHJldHJpZXMuJywgeyBtb2RlbCwgZXJyb3I6IChlcnJvciBhcyBFcnJvcikubWVzc2FnZSB9KTtcbiAgICB0aHJvdyBlcnJvcjtcbiAgfVxufVxuXG5cbmV4cG9ydCBjb25zdCBjYWxsT3BlbkFJV2l0aE1lc3NhZ2VIaXN0b3J5ID0gYXN5bmMgKFxuICAgIG9wZW5haTogT3BlbkFJLFxuICAgIG1lc3NhZ2VIaXN0b3J5OiBDaGF0R1BUTWVzc2FnZUhpc3RvcnlUeXBlID0gW10sXG4gICAgcHJvbXB0OiBzdHJpbmcsXG4gICAgbW9kZWw6ICdncHQtMy41LXR1cmJvJyB8ICdncHQtMy41LXR1cmJvLTE2aycgfCAnZ3B0LTQnID0gJ2dwdC0zLjUtdHVyYm8nLFxuICAgIHVzZXJEYXRhOiBzdHJpbmcsXG4gICAgZXhhbXBsZUlucHV0Pzogc3RyaW5nLFxuICAgIGV4YW1wbGVPdXRwdXQ/OiBzdHJpbmcsXG4pID0+IHtcbiAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9IFwiY2FsbE9wZW5BSVdpdGhNZXNzYWdlSGlzdG9yeVwiO1xuICB0cnkge1xuICAgIHJldHVybiBhd2FpdCByZXRyeShhc3luYyAoYmFpbCwgYXR0ZW1wdE51bWJlcikgPT4ge1xuICAgICAgdHJ5IHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKGBBdHRlbXB0ICR7YXR0ZW1wdE51bWJlcn0gZm9yICR7b3BlcmF0aW9uTmFtZX0uIE1vZGVsOiAke21vZGVsfS5gKTtcbiAgICAgICAgY29uc3QgbWVzc2FnZXM6IE9wZW5BSS5DaGF0LkNvbXBsZXRpb25zLkNoYXRDb21wbGV0aW9uTWVzc2FnZVBhcmFtW10gPSBtZXNzYWdlSGlzdG9yeS5jb25jYXQoW1xuICAgICAgICAgICAgeyByb2xlOiAnc3lzdGVtJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHByb21wdCB9LFxuICAgICAgICAgICAgZXhhbXBsZUlucHV0ICYmIHsgcm9sZTogJ3VzZXInIGFzIENoYXRHUFRSb2xlVHlwZSwgY29udGVudDogZXhhbXBsZUlucHV0IH0sXG4gICAgICAgICAgICBleGFtcGxlT3V0cHV0ICYmIHsgcm9sZTogJ2Fzc2lzdGFudCcgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiBleGFtcGxlT3V0cHV0IH0sXG4gICAgICAgICAgICB7IHJvbGU6ICd1c2VyJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHVzZXJEYXRhIH1cbiAgICAgICAgXSk/LmZpbHRlcihtID0+ICEhbSkgYXMgT3BlbkFJLkNoYXQuQ29tcGxldGlvbnMuQ2hhdENvbXBsZXRpb25NZXNzYWdlUGFyYW1bXTtcblxuICAgICAgICBjb25zdCBjb21wbGV0aW9uID0gYXdhaXQgb3BlbmFpLmNoYXQuY29tcGxldGlvbnMuY3JlYXRlKHtcbiAgICAgICAgICAgIG1vZGVsLFxuICAgICAgICAgICAgbWVzc2FnZXMsXG4gICAgICAgICAgICB0aW1lb3V0OiAzMDAwMCwgLy8gMzBzIHRpbWVvdXQsIHBvdGVudGlhbGx5IGxvbmdlciBwcm9tcHRzL3Jlc3BvbnNlc1xuICAgICAgICB9KTtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5pbmZvKGAke29wZXJhdGlvbk5hbWV9IHN1Y2Nlc3NmdWwgb24gYXR0ZW1wdCAke2F0dGVtcHROdW1iZXJ9LiBNb2RlbDogJHttb2RlbH0uYCk7XG4gICAgICAgIHJldHVybiB7IHRvdGFsVG9rZW5Db3VudDogY29tcGxldGlvbj8udXNhZ2U/LnRvdGFsX3Rva2VucywgcmVzcG9uc2U6IGNvbXBsZXRpb24/LmNob2ljZXM/LlswXT8ubWVzc2FnZT8uY29udGVudCB9O1xuICAgICAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLndhcm4oYEF0dGVtcHQgJHthdHRlbXB0TnVtYmVyfSBmb3IgJHtvcGVyYXRpb25OYW1lfSBmYWlsZWQuIE1vZGVsOiAke21vZGVsfS5gLCB7XG4gICAgICAgICAgICBlcnJvcjogZXJyb3IubWVzc2FnZSwgY29kZTogZXJyb3IuY29kZSwgc3RhdHVzOiBlcnJvci5yZXNwb25zZT8uc3RhdHVzXG4gICAgICAgIH0pO1xuICAgICAgICAgaWYgKGVycm9yLnJlc3BvbnNlICYmIFs0MDAsIDQwMSwgNDAzLCA0MDQsIDQyOV0uaW5jbHVkZXMoZXJyb3IucmVzcG9uc2Uuc3RhdHVzKSkge1xuICAgICAgICAgICAgYmFpbChlcnJvcik7XG4gICAgICAgICAgICByZXR1cm47XG4gICAgICAgIH1cbiAgICAgICAgdGhyb3cgZXJyb3I7XG4gICAgICB9XG4gICAgfSwge1xuICAgICAgICByZXRyaWVzOiAyLCBmYWN0b3I6IDIsIG1pblRpbWVvdXQ6IDEwMDAsIG1heFRpbWVvdXQ6IDgwMDAsXG4gICAgICAgIG9uUmV0cnk6IChlcnJvciwgYXR0ZW1wdE51bWJlcikgPT4ge1xuICAgICAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci53YXJuKGBSZXRyeWluZyAke29wZXJhdGlvbk5hbWV9LCBhdHRlbXB0ICR7YXR0ZW1wdE51bWJlcn0uIE1vZGVsOiAke21vZGVsfS4gRXJyb3I6ICR7ZXJyb3IubWVzc2FnZX1gKTtcbiAgICAgICAgfVxuICAgIH0pO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoYEZhaWxlZCAke29wZXJhdGlvbk5hbWV9IGFmdGVyIGFsbCByZXRyaWVzLmAsIHsgbW9kZWwsIGVycm9yOiAoZXJyb3IgYXMgRXJyb3IpLm1lc3NhZ2UgfSk7XG4gICAgdGhyb3cgZXJyb3I7XG4gIH1cbn1cblxuZXhwb3J0IGNvbnN0IGNhbGxPcGVuQUkgPSBhc3luYyAoXG4gICAgb3BlbmFpOiBPcGVuQUksIC8vIFRoaXMgcGFyYW0gd2FzIG5hbWVkICdvcGVuYWknLCBidXQgaXQgc2VlbXMgaXQgc2hvdWxkIGJlICdwcm9tcHQnIGJhc2VkIG9uIHVzYWdlXG4gICAgcHJvbXB0OiBzdHJpbmcsIC8vIFJlbmFtZWQgZnJvbSAnbW9kZWwnIGZvciBjbGFyaXR5LCBhcyAnbW9kZWwnIGlzIHRoZSBuZXh0IHBhcmFtXG4gICAgbW9kZWw6ICdncHQtMy41LXR1cmJvJyB8ICdncHQtMy41LXR1cmJvLTE2aycgfCAnZ3B0LTQnID0gJ2dwdC0zLjUtdHVyYm8nLCAgLy8gVGhpcyB3YXMgJ3VzZXJEYXRhJ1xuICAgIHVzZXJEYXRhOiBzdHJpbmcsIC8vIFRoaXMgd2FzICdleGFtcGxlSW5wdXQnXG4gICAgZXhhbXBsZUlucHV0Pzogc3RyaW5nLCAvLyBUaGlzIHdhcyAnZXhhbXBsZU91dHB1dCdcbiAgICBleGFtcGxlT3V0cHV0Pzogc3RyaW5nLCAvLyBUaGlzIHdhcyBub3QgcHJlc2VudFxuKSA9PiB7XG4gIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSBcImNhbGxPcGVuQUlfU2ltcGxlXCI7XG4gICAvLyBDb3JyZWN0aW5nIHBhcmFtZXRlciBtYXBwaW5nIGJhc2VkIG9uIGxpa2VseSBpbnRlbnQgYW5kIHVzYWdlIHBhdHRlcm46XG4gIC8vIE9yaWdpbmFsOiBvcGVuYWkgKE9wZW5BSSBjbGllbnQpLCBwcm9tcHQgKHN0cmluZyksIG1vZGVsIChzdHJpbmcsIGUuZy4gJ2dwdC0zLjUtdHVyYm8nKSwgdXNlckRhdGEgKHN0cmluZyksIGV4YW1wbGVJbnB1dCAoc3RyaW5nKSwgZXhhbXBsZU91dHB1dCAoc3RyaW5nKVxuICAvLyBUaGUgZmlyc3QgcGFyYW1ldGVyIGBvcGVuYWlgIGlzIHRoZSBPcGVuQUkgY2xpZW50IGluc3RhbmNlLlxuICAvLyBUaGUgc2Vjb25kIHBhcmFtZXRlciBgcHJvbXB0YCBpcyB0aGUgc3lzdGVtIHByb21wdC5cbiAgLy8gVGhlIHRoaXJkIHBhcmFtZXRlciBgbW9kZWxgIGlzIHRoZSBtb2RlbCBuYW1lLlxuICAvLyBUaGUgZm91cnRoIHBhcmFtZXRlciBgdXNlckRhdGFgIGlzIHRoZSBtYWluIHVzZXIgbWVzc2FnZS5cbiAgLy8gVGhlIGZpZnRoIGFuZCBzaXh0aCBhcmUgZXhhbXBsZXMuXG5cbiAgdHJ5IHtcbiAgICByZXR1cm4gYXdhaXQgcmV0cnkoYXN5bmMgKGJhaWwsIGF0dGVtcHROdW1iZXIpID0+IHtcbiAgICAgIHRyeSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbyhgQXR0ZW1wdCAke2F0dGVtcHROdW1iZXJ9IGZvciAke29wZXJhdGlvbk5hbWV9LiBNb2RlbDogJHttb2RlbH0uYCk7XG4gICAgICAgIGNvbnN0IG1lc3NhZ2VzOiBPcGVuQUkuQ2hhdC5Db21wbGV0aW9ucy5DaGF0Q29tcGxldGlvbk1lc3NhZ2VQYXJhbVtdID0gW1xuICAgICAgICAgICAgeyByb2xlOiAnc3lzdGVtJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHByb21wdCB9LFxuICAgICAgICAgICAgZXhhbXBsZUlucHV0ICYmIHsgcm9sZTogJ3VzZXInIGFzIENoYXRHUFRSb2xlVHlwZSwgY29udGVudDogZXhhbXBsZUlucHV0IH0sXG4gICAgICAgICAgICBleGFtcGxlT3V0cHV0ICYmIHsgcm9sZTogJ2Fzc2lzdGFudCcgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiBleGFtcGxlT3V0cHV0IH0sXG4gICAgICAgICAgICB7IHJvbGU6ICd1c2VyJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHVzZXJEYXRhIH1cbiAgICAgICAgXT8uZmlsdGVyKG0gPT4gISFtKSBhcyBPcGVuQUkuQ2hhdC5Db21wbGV0aW9ucy5DaGF0Q29tcGxldGlvbk1lc3NhZ2VQYXJhbVtdO1xuXG4gICAgICAgIGNvbnN0IGNvbXBsZXRpb24gPSBhd2FpdCBvcGVuYWkuY2hhdC5jb21wbGV0aW9ucy5jcmVhdGUoe1xuICAgICAgICAgICAgbW9kZWwsXG4gICAgICAgICAgICBtZXNzYWdlcyxcbiAgICAgICAgICAgIHRpbWVvdXQ6IDMwMDAwLCAvLyAzMHNcbiAgICAgICAgfSk7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuaW5mbyhgJHtvcGVyYXRpb25OYW1lfSBzdWNjZXNzZnVsIG9uIGF0dGVtcHQgJHthdHRlbXB0TnVtYmVyfS4gTW9kZWw6ICR7bW9kZWx9LmApO1xuICAgICAgICByZXR1cm4gY29tcGxldGlvbj8uY2hvaWNlcz8uWzBdPy5tZXNzYWdlPy5jb250ZW50O1xuICAgICAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLndhcm4oYEF0dGVtcHQgJHthdHRlbXB0TnVtYmVyfSBmb3IgJHtvcGVyYXRpb25OYW1lfSBmYWlsZWQuIE1vZGVsOiAke21vZGVsfS5gLCB7XG4gICAgICAgICAgICBlcnJvcjogZXJyb3IubWVzc2FnZSwgY29kZTogZXJyb3IuY29kZSwgc3RhdHVzOiBlcnJvci5yZXNwb25zZT8uc3RhdHVzXG4gICAgICAgIH0pO1xuICAgICAgICBpZiAoZXJyb3IucmVzcG9uc2UgJiYgWzQwMCwgNDAxLCA0MDMsIDQwNCwgNDI5XS5pbmNsdWRlcyhlcnJvci5yZXNwb25zZS5zdGF0dXMpKSB7XG4gICAgICAgICAgICBiYWlsKGVycm9yKTtcbiAgICAgICAgICAgIHJldHVybjtcbiAgICAgICAgfVxuICAgICAgICB0aHJvdyBlcnJvcjtcbiAgICAgIH1cbiAgICB9LCB7XG4gICAgICAgIHJldHJpZXM6IDIsIGZhY3RvcjogMiwgbWluVGltZW91dDogMTAwMCwgbWF4VGltZW91dDogODAwMCxcbiAgICAgICAgb25SZXRyeTogKGVycm9yLCBhdHRlbXB0TnVtYmVyKSA9PiB7XG4gICAgICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLndhcm4oYFJldHJ5aW5nICR7b3BlcmF0aW9uTmFtZX0sIGF0dGVtcHQgJHthdHRlbXB0TnVtYmVyfS4gTW9kZWw6ICR7bW9kZWx9LiBFcnJvcjogJHtlcnJvci5tZXNzYWdlfWApO1xuICAgICAgICB9XG4gICAgfSk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcihgRmFpbGVkICR7b3BlcmF0aW9uTmFtZX0gYWZ0ZXIgYWxsIHJldHJpZXMuYCwgeyBtb2RlbCwgZXJyb3I6IChlcnJvciBhcyBFcnJvcikubWVzc2FnZSB9KTtcbiAgICB0aHJvdyBlcnJvcjtcbiAgfVxufVxuXG5cblxuXG5cbmV4cG9ydCBjb25zdCBsaXN0RXZlbnRzRm9yVXNlckdpdmVuRGF0ZXMgPSBhc3luYyAoXG4gICAgdXNlcklkOiBzdHJpbmcsXG4gICAgc2VuZGVyU3RhcnREYXRlOiBzdHJpbmcsXG4gICAgc2VuZGVyRW5kRGF0ZTogc3RyaW5nLFxuICAgIC8vIHNlbmRlclRpbWV6b25lOiBzdHJpbmcsXG4gICAgLy8gcmVjZWl2ZXJUaW1lem9uZTogc3RyaW5nLFxuKSA9PiB7XG4gICAgdHJ5IHtcblxuICAgICAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2xpc3RFdmVudHNGb3JVc2VyJ1xuICAgICAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IGxpc3RFdmVudHNGb3JVc2VyKCR1c2VySWQ6IHV1aWQhLCAkc3RhcnREYXRlOiB0aW1lc3RhbXAhLCAkZW5kRGF0ZTogdGltZXN0YW1wISkge1xuICAgICAgICAgICAgICAgIEV2ZW50KHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgZW5kRGF0ZToge19ndGU6ICRzdGFydERhdGV9LCBzdGFydERhdGU6IHtfbHRlOiAkZW5kRGF0ZX0sIGRlbGV0ZWQ6IHtfbmVxOiB0cnVlfSwgYWxsRGF5OiB7X25lcTogdHJ1ZX19KSB7XG4gICAgICAgICAgICAgICAgICAgIGFsbERheVxuICAgICAgICAgICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICAgICAgICAgICAgICAgIGF0dGFjaG1lbnRzXG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlc09taXR0ZWRcbiAgICAgICAgICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgICAgICAgICBjb25mZXJlbmNlSWRcbiAgICAgICAgICAgICAgICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICBjb3B5Q2F0ZWdvcmllc1xuICAgICAgICAgICAgICAgICAgICBjb3B5RHVyYXRpb25cbiAgICAgICAgICAgICAgICAgICAgY29weUlzQnJlYWtcbiAgICAgICAgICAgICAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgICAgICAgICAgY29weVJlbWluZGVyc1xuICAgICAgICAgICAgICAgICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICAgICAgICAgICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBjcmVhdG9yXG4gICAgICAgICAgICAgICAgICAgIGRhaWx5VGFza0xpc3RcbiAgICAgICAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICAgICAgICBkdXJhdGlvblxuICAgICAgICAgICAgICAgICAgICBlbmREYXRlXG4gICAgICAgICAgICAgICAgICAgIGVuZFRpbWVVbnNwZWNpZmllZFxuICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgIGV2ZW50VHlwZVxuICAgICAgICAgICAgICAgICAgICBleHRlbmRlZFByb3BlcnRpZXNcbiAgICAgICAgICAgICAgICAgICAgZm9sbG93VXBFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIGZvckV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5Nb2RpZnlcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgICAgICAgICAgICAgICAgaGFuZ291dExpbmtcbiAgICAgICAgICAgICAgICAgICAgaGFyZERlYWRsaW5lXG4gICAgICAgICAgICAgICAgICAgIGh0bWxMaW5rXG4gICAgICAgICAgICAgICAgICAgIGlDYWxVSURcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgaXNCcmVha1xuICAgICAgICAgICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgaXNGb2xsb3dVcFxuICAgICAgICAgICAgICAgICAgICBpc01lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICBpc1Bvc3RFdmVudFxuICAgICAgICAgICAgICAgICAgICBpc1ByZUV2ZW50XG4gICAgICAgICAgICAgICAgICAgIGxpbmtzXG4gICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uXG4gICAgICAgICAgICAgICAgICAgIGxvY2tlZFxuICAgICAgICAgICAgICAgICAgICBtYXhBdHRlbmRlZXNcbiAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgIG1ldGhvZFxuICAgICAgICAgICAgICAgICAgICBtb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3RUaW1lXG4gICAgICAgICAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICAgICAgICAgIG9yZ2FuaXplclxuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbEFsbERheVxuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RUaW1lXG4gICAgICAgICAgICAgICAgICAgIHBvc3RFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIHByZUV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZVxuICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRUaW1lXG4gICAgICAgICAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICAgICAgICAgIHByaXZhdGVDb3B5XG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyZW5jZVJ1bGVcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyaW5nRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBzZW5kVXBkYXRlc1xuICAgICAgICAgICAgICAgICAgICBzb2Z0RGVhZGxpbmVcbiAgICAgICAgICAgICAgICAgICAgc291cmNlXG4gICAgICAgICAgICAgICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBzdGF0dXNcbiAgICAgICAgICAgICAgICAgICAgc3VtbWFyeVxuICAgICAgICAgICAgICAgICAgICB0YXNrSWRcbiAgICAgICAgICAgICAgICAgICAgdGFza1R5cGVcbiAgICAgICAgICAgICAgICAgICAgdGltZUJsb2NraW5nXG4gICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHRpdGxlXG4gICAgICAgICAgICAgICAgICAgIHRyYW5zcGFyZW5jeVxuICAgICAgICAgICAgICAgICAgICB1bmxpbmtcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRDYXRlZ29yaWVzXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZER1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzQnJlYWtcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgICAgICAgICAgIHZpc2liaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgd2Vla2x5VGFza0xpc3RcbiAgICAgICAgICAgICAgICAgICAgYnlXZWVrRGF5XG4gICAgICAgICAgICAgICAgICAgIGxvY2FsU3luY2VkXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGNvcHlDb2xvclxuICAgICAgICAgICAgICAgICAgICBjb3B5RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgXG4gICAgICAgIC8vIGdldCBldmVudHNcbiAgICAgICAgLy8gbG9jYWwgZGF0ZVxuICAgICAgICAvLyBjb25zdCBzdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmUgPSBkYXlqcyhzZW5kZXJTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihyZWNlaXZlclRpbWV6b25lLCB0cnVlKVxuICAgICAgICAvLyBjb25zdCBlbmREYXRlSW5SZWNlaXZlclRpbWV6b25lID0gZGF5anMoKHNlbmRlckVuZERhdGUuc2xpY2UoMCwgMTkpKSkudHoocmVjZWl2ZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLy8gY29uc3Qgc3RhcnREYXRlSW5TZW5kZXJUaW1lem9uZSA9IGRheWpzKHN0YXJ0RGF0ZUluUmVjZWl2ZXJUaW1lem9uZSkuZm9ybWF0KCkuc2xpY2UoMCwgMTkpXG4gICAgICAgIC8vIGNvbnN0IGVuZERhdGVJblNlbmRlclRpbWV6b25lID0gZGF5anMoZW5kRGF0ZUluUmVjZWl2ZXJUaW1lem9uZSkuZm9ybWF0KCkuc2xpY2UoMCwgMTkpXG5cblxuICAgICAgICBjb25zdCByZXMgPSBhd2FpdCBnb3QucG9zdChcbiAgICAgICAgICAgIHBvc3RncmFwaGlsZUdyYXBoVXJsLFxuICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbidcbiAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgICAgICAgICAgcXVlcnksXG4gICAgICAgICAgICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgICAgICAgICAgICAgc3RhcnREYXRlOiBzZW5kZXJTdGFydERhdGUsXG4gICAgICAgICAgICAgICAgICAgICAgICBlbmREYXRlOiBzZW5kZXJFbmREYXRlLFxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICB9LFxuXG4gICAgICAgIGNvbnN0IHJlc3BvbnNlRGF0YSA9IGF3YWl0IHJlc2lsaWVudEdvdFBvc3RQb3N0Z3JhcGhpbGUob3BlcmF0aW9uTmFtZSwgcXVlcnksIHsgdXNlcklkLCBzdGFydERhdGU6IHNlbmRlclN0YXJ0RGF0ZSwgZW5kRGF0ZTogc2VuZGVyRW5kRGF0ZSB9LCB1c2VySWQpIGFzIHsgRXZlbnQ6IEV2ZW50VHlwZVtdIH07XG4gICAgICAgIHJldHVybiByZXNwb25zZURhdGE/LkV2ZW50O1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignRXJyb3IgaW4gbGlzdEV2ZW50c0ZvclVzZXJHaXZlbkRhdGVzJywgeyB1c2VySWQsIHNlbmRlclN0YXJ0RGF0ZSwgc2VuZGVyRW5kRGF0ZSwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlIH0pO1xuICAgICAgICB0aHJvdyBlO1xuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IGV4dHJhY3RBdHRyaWJ1dGVzTmVlZGVkRnJvbVVzZXJJbnB1dCA9IGFzeW5jIChcbiAgICB1c2VySW5wdXQ6IHN0cmluZyxcbikgPT4ge1xuICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IG9wZW5BSURhdGVUaW1lID0gYXdhaXQgY2FsbE9wZW5BSShvcGVuYWksIGV4dHJhY3ROZWVkZWRBdHRyaWJ1dGVzUHJvbXB0LCBvcGVuQUlDaGF0R1BUMzVNb2RlbCwgdXNlcklucHV0LCBleHRyYWN0TmVlZGVkQXR0cmlidXRlc0V4YW1wbGVJbnB1dCwgZXh0cmFjdE5lZWRlZEF0dHJpYnV0ZXNFeGFtcGxlT3V0cHV0KVxuICAgICAgICBjb25zdCBhdHRyaWJ1dGVzU3RhcnRJbmRleCA9IG9wZW5BSURhdGVUaW1lLmluZGV4T2YoJ3snKVxuICAgICAgICBjb25zdCBhdHRyaWJ1dGVzRW5kSW5kZXggPSBvcGVuQUlEYXRlVGltZS5sYXN0SW5kZXhPZignfScpXG4gICAgICAgIGNvbnN0IGF0dHJpYnV0ZXNKU09OU3RyaW5nID0gb3BlbkFJRGF0ZVRpbWUuc2xpY2UoYXR0cmlidXRlc1N0YXJ0SW5kZXgsIGF0dHJpYnV0ZXNFbmRJbmRleCArIDEpXG4gICAgICAgIGNvbnN0IGF0dHJpYnV0ZXM6IFF1ZXJ5Q2FsZW5kYXJFeHRyYWN0ZWRBdHRyaWJ1dGVzVHlwZSA9IEpTT04ucGFyc2UoYXR0cmlidXRlc0pTT05TdHJpbmcpXG5cbiAgICAgICAgcmV0dXJuIGF0dHJpYnV0ZXNcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoJ1VuYWJsZSB0byBleHRyYWN0IGF0dHJpYnV0ZXMgbmVlZGVkIGZyb20gdXNlciBpbnB1dCcsIHsgdXNlcklucHV0LCBlcnJvcjogKGUgYXMgRXJyb3IpLm1lc3NhZ2UsIHN0YWNrOiAoZSBhcyBFcnJvcikuc3RhY2sgfSk7XG4gICAgICAgIC8vIE9yaWdpbmFsIGZ1bmN0aW9uIGltcGxpY2l0bHkgcmV0dXJucyB1bmRlZmluZWQgaGVyZS5cbiAgICAgICAgcmV0dXJuIHVuZGVmaW5lZDtcbiAgICB9XG59XG5cblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlUXVlcnlEYXRlRnJvbVVzZXJJbnB1dCA9IGFzeW5jIChcbiAgICB1c2VySWQ6IHN0cmluZyxcbiAgICB0aW1lem9uZTogc3RyaW5nLFxuICAgIHVzZXJJbnB1dDogc3RyaW5nLFxuICAgIHVzZXJDdXJyZW50VGltZTogc3RyaW5nLFxuKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgY29uc3QgcXVlcnlEYXRlU3lzTWVzc2FnZSA9IHsgcm9sZTogJ3N5c3RlbScgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiBleHRyYWN0UXVlcnlVc2VySW5wdXRUaW1lVG9KU09OUHJvbXB0IH1cbiAgICAgICAgY29uc3QgcXVlcnlEYXRlTWVzc2FnZUhpc3Rvcnk6IENoYXRHUFRNZXNzYWdlSGlzdG9yeVR5cGUgPSBbXVxuICAgICAgICBjb25zdCBxdWVyeURhdGVVc2VyTWVzc2FnZTEgPSB7IHJvbGU6ICd1c2VyJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IGV4dHJhY3RRdWVyeVVzZXJJbnB1dFRpbWVUb0pTT05FeGFtcGxlSW5wdXQxIH1cbiAgICAgICAgY29uc3QgcXVlcnlEYXRlQXNzaXN0YW50TWVzc2FnZTEgPSB7IHJvbGU6ICdhc3Npc3RhbnQnIGFzIENoYXRHUFRSb2xlVHlwZSwgY29udGVudDogZXh0cmFjdFF1ZXJ5VXNlcklucHV0VGltZVRvSlNPTkV4YW1wbGVPdXRwdXQxIH1cbiAgICAgICAgY29uc3QgcXVlcnlEYXRlVXNlck1lc3NhZ2UyID0geyByb2xlOiAndXNlcicgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiBleHRyYWN0UXVlcnlVc2VySW5wdXRUaW1lVG9KU09ORXhhbXBsZUlucHV0MiB9XG4gICAgICAgIGNvbnN0IHF1ZXJ5RGF0ZUFzc2lzdGFudE1lc3NhZ2UyID0geyByb2xlOiAnYXNzaXN0YW50JyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IGV4dHJhY3RRdWVyeVVzZXJJbnB1dFRpbWVUb0pTT05FeGFtcGxlT3V0cHV0MiB9XG4gICAgICAgIGNvbnN0IHF1ZXJ5RGF0ZVVzZXJNZXNzYWdlMyA9IHsgcm9sZTogJ3VzZXInIGFzIENoYXRHUFRSb2xlVHlwZSwgY29udGVudDogZXh0cmFjdFF1ZXJ5VXNlcklucHV0VGltZVRvSlNPTkV4YW1wbGVJbnB1dDMgfVxuICAgICAgICBjb25zdCBxdWVyeURhdGVBc3Npc3RhbnRNZXNzYWdlMyA9IHsgcm9sZTogJ2Fzc2lzdGFudCcgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiBleHRyYWN0UXVlcnlVc2VySW5wdXRUaW1lVG9KU09ORXhhbXBsZU91dHB1dDMgfVxuXG5cbiAgICAgICAgLy8gdXNlciB3b3JrIHRpbWVzXG4gICAgICAgIGNvbnN0IHVzZXJQcmVmZXJlbmNlcyA9IGF3YWl0IGdldFVzZXJQcmVmZXJlbmNlcyh1c2VySWQpXG5cbiAgICAgICAgY29uc3Qgd29ya1RpbWVzT2JqZWN0ID0gZ2VuZXJhdGVXb3JrVGltZXNGb3JVc2VyKHVzZXJQcmVmZXJlbmNlcywgdGltZXpvbmUpXG4gICAgICAgIGxldCB1c2VyV29ya1RpbWVzID0gJydcbiAgICAgICAgZm9yIChjb25zdCB3b3JrVGltZU9iamVjdCBvZiB3b3JrVGltZXNPYmplY3QpIHtcblxuICAgICAgICAgICAgdXNlcldvcmtUaW1lcyArPSBgJHt3b3JrVGltZU9iamVjdD8uZGF5T2ZXZWVrfTogJHt3b3JrVGltZU9iamVjdD8uc3RhcnRUaW1lfSAtICR7d29ya1RpbWVPYmplY3Q/LmVuZFRpbWV9IFxcbmBcblxuICAgICAgICB9XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoJ1tnZW5lcmF0ZVF1ZXJ5RGF0ZUZyb21Vc2VySW5wdXRdIFVzZXIgd29yayB0aW1lcyBzdHJpbmc6JywgeyB1c2VySWQsIHVzZXJXb3JrVGltZXMgfSk7XG4gICAgICAgIGNvbnN0IHF1ZXJ5RGF0ZUVuZ2luZSA9IG5ldyBUZW1wbGF0ZUVuZ2luZShleHRyYWN0UXVlcnlVc2VySW5wdXRUaW1lVG9KU09OVGVtcGxhdGUpO1xuICAgICAgICBjb25zdCBxdWVyeURhdGVSZW5kZXJlZCA9IHF1ZXJ5RGF0ZUVuZ2luZS5yZW5kZXIoeyB1c2VyQ3VycmVudFRpbWUsIHVzZXJXb3JrVGltZXM6IHVzZXJXb3JrVGltZXMsIHVzZXJJbnB1dCB9KVxuXG4gICAgICAgIGNvbnN0IHF1ZXJ5RGF0ZVVzZXJNZXNzYWdlSW5wdXQgPSB7IHJvbGU6ICd1c2VyJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHF1ZXJ5RGF0ZVJlbmRlcmVkIH1cbiAgICAgICAgcXVlcnlEYXRlTWVzc2FnZUhpc3RvcnkucHVzaChxdWVyeURhdGVTeXNNZXNzYWdlLCBxdWVyeURhdGVVc2VyTWVzc2FnZTEsIHF1ZXJ5RGF0ZUFzc2lzdGFudE1lc3NhZ2UxLCBxdWVyeURhdGVVc2VyTWVzc2FnZTIsIHF1ZXJ5RGF0ZUFzc2lzdGFudE1lc3NhZ2UyLCBxdWVyeURhdGVVc2VyTWVzc2FnZTMsIHF1ZXJ5RGF0ZUFzc2lzdGFudE1lc3NhZ2UzLCBxdWVyeURhdGVVc2VyTWVzc2FnZUlucHV0KVxuXG4gICAgICAgIGNvbnN0IG9wZW5BSVF1ZXJ5RGF0ZSA9IGF3YWl0IGNhbGxPcGVuQUlXaXRoTWVzc2FnZUhpc3RvcnlPbmx5KG9wZW5haSwgcXVlcnlEYXRlTWVzc2FnZUhpc3RvcnksIG9wZW5BSUNoYXRHUFQzNU1vZGVsKVxuICAgICAgICBjb25zdCBxdWVyeURhdGVTdGFydEluZGV4ID0gb3BlbkFJUXVlcnlEYXRlLmluZGV4T2YoJ3snKVxuICAgICAgICBjb25zdCBxdWVyeURhdGVFbmRJbmRleCA9IG9wZW5BSVF1ZXJ5RGF0ZS5sYXN0SW5kZXhPZignfScpXG4gICAgICAgIGNvbnN0IHF1ZXJ5RGF0ZUpTT05TdHJpbmcgPSBvcGVuQUlRdWVyeURhdGUuc2xpY2UocXVlcnlEYXRlU3RhcnRJbmRleCwgcXVlcnlEYXRlRW5kSW5kZXggKyAxKVxuICAgICAgICBjb25zdCBxdWVyeURhdGU6IFF1ZXJ5Q2FsZW5kYXJFeHRyYWN0ZWRKU09OVHlwZSA9IEpTT04ucGFyc2UocXVlcnlEYXRlSlNPTlN0cmluZylcblxuICAgICAgICByZXR1cm4gcXVlcnlEYXRlXG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdVbmFibGUgdG8gZ2VuZXJhdGUgcXVlcnlEYXRlIGZyb20gdXNlciBpbnB1dCcsIHsgdXNlcklkLCB0aW1lem9uZSwgdXNlcklucHV0LCB1c2VyQ3VycmVudFRpbWUsIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSwgc3RhY2s6IChlIGFzIEVycm9yKS5zdGFjayB9KTtcbiAgICAgICAgLy8gT3JpZ2luYWwgZnVuY3Rpb24gaW1wbGljaXRseSByZXR1cm5zIHVuZGVmaW5lZCBoZXJlLlxuICAgICAgICByZXR1cm4gdW5kZWZpbmVkO1xuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlTWlzc2luZ0ZpZWxkc1F1ZXJ5RGF0ZUZyb21Vc2VySW5wdXQgPSBhc3luYyAoXG4gICAgdXNlcklkOiBzdHJpbmcsXG4gICAgdGltZXpvbmU6IHN0cmluZyxcbiAgICB1c2VySW5wdXQ6IHN0cmluZyxcbiAgICBwcmlvclVzZXJJbnB1dDogc3RyaW5nLFxuICAgIHByaW9yQXNzaXN0YW50T3V0cHV0OiBzdHJpbmcsXG4gICAgdXNlckN1cnJlbnRUaW1lOiBzdHJpbmcsXG4pID0+IHtcbiAgICB0cnkge1xuICAgICAgICBjb25zdCBxdWVyeURhdGVTeXNNZXNzYWdlID0geyByb2xlOiAnc3lzdGVtJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IGV4dHJhY3RRdWVyeVVzZXJJbnB1dFRpbWVUb0pTT05Qcm9tcHQgfVxuICAgICAgICBjb25zdCBxdWVyeURhdGVNZXNzYWdlSGlzdG9yeTogQ2hhdEdQVE1lc3NhZ2VIaXN0b3J5VHlwZSA9IFtdXG4gICAgICAgIGNvbnN0IHF1ZXJ5RGF0ZVVzZXJNZXNzYWdlMSA9IHsgcm9sZTogJ3VzZXInIGFzIENoYXRHUFRSb2xlVHlwZSwgY29udGVudDogZXh0cmFjdFF1ZXJ5VXNlcklucHV0VGltZVRvSlNPTkV4YW1wbGVJbnB1dDEgfVxuICAgICAgICBjb25zdCBxdWVyeURhdGVBc3Npc3RhbnRNZXNzYWdlMSA9IHsgcm9sZTogJ2Fzc2lzdGFudCcgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiBleHRyYWN0UXVlcnlVc2VySW5wdXRUaW1lVG9KU09ORXhhbXBsZU91dHB1dDEgfVxuICAgICAgICBjb25zdCBxdWVyeURhdGVVc2VyTWVzc2FnZTIgPSB7IHJvbGU6ICd1c2VyJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IGV4dHJhY3RRdWVyeVVzZXJJbnB1dFRpbWVUb0pTT05FeGFtcGxlSW5wdXQyIH1cbiAgICAgICAgY29uc3QgcXVlcnlEYXRlQXNzaXN0YW50TWVzc2FnZTIgPSB7IHJvbGU6ICdhc3Npc3RhbnQnIGFzIENoYXRHUFRSb2xlVHlwZSwgY29udGVudDogZXh0cmFjdFF1ZXJ5VXNlcklucHV0VGltZVRvSlNPTkV4YW1wbGVPdXRwdXQyIH1cbiAgICAgICAgY29uc3QgcXVlcnlEYXRlVXNlck1lc3NhZ2UzID0geyByb2xlOiAndXNlcicgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiBleHRyYWN0UXVlcnlVc2VySW5wdXRUaW1lVG9KU09ORXhhbXBsZUlucHV0MyB9XG4gICAgICAgIGNvbnN0IHF1ZXJ5RGF0ZUFzc2lzdGFudE1lc3NhZ2UzID0geyByb2xlOiAnYXNzaXN0YW50JyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IGV4dHJhY3RRdWVyeVVzZXJJbnB1dFRpbWVUb0pTT05FeGFtcGxlT3V0cHV0MyB9XG5cbiAgICAgICAgY29uc3QgcXVlcnlEYXRlVXNlck1lc3NhZ2U0ID0geyByb2xlOiAndXNlcicgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiBwcmlvclVzZXJJbnB1dCB9XG4gICAgICAgIGNvbnN0IHF1ZXJ5RGF0ZUFzc2lzdGFudE1lc3NhZ2U0ID0geyByb2xlOiAnYXNzaXN0YW50JyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHByaW9yQXNzaXN0YW50T3V0cHV0IH1cblxuICAgICAgICAvLyB1c2VyIHdvcmsgdGltZXNcbiAgICAgICAgY29uc3QgdXNlclByZWZlcmVuY2VzID0gYXdhaXQgZ2V0VXNlclByZWZlcmVuY2VzKHVzZXJJZClcblxuICAgICAgICBjb25zdCB3b3JrVGltZXNPYmplY3QgPSBnZW5lcmF0ZVdvcmtUaW1lc0ZvclVzZXIodXNlclByZWZlcmVuY2VzLCB0aW1lem9uZSlcbiAgICAgICAgbGV0IHVzZXJXb3JrVGltZXMgPSAnJ1xuICAgICAgICBmb3IgKGNvbnN0IHdvcmtUaW1lT2JqZWN0IG9mIHdvcmtUaW1lc09iamVjdCkge1xuXG4gICAgICAgICAgICB1c2VyV29ya1RpbWVzICs9IGAke3dvcmtUaW1lT2JqZWN0Py5kYXlPZldlZWt9OiAke3dvcmtUaW1lT2JqZWN0Py5zdGFydFRpbWV9IC0gJHt3b3JrVGltZU9iamVjdD8uZW5kVGltZX0gXFxuYFxuXG4gICAgICAgIH1cbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5kZWJ1ZygnW2dlbmVyYXRlTWlzc2luZ0ZpZWxkc1F1ZXJ5RGF0ZUZyb21Vc2VySW5wdXRdIFVzZXIgd29yayB0aW1lcyBzdHJpbmc6JywgeyB1c2VySWQsIHVzZXJXb3JrVGltZXMgfSk7XG4gICAgICAgIGNvbnN0IHF1ZXJ5RGF0ZUVuZ2luZSA9IG5ldyBUZW1wbGF0ZUVuZ2luZShleHRyYWN0UXVlcnlVc2VySW5wdXRUaW1lVG9KU09OVGVtcGxhdGUpO1xuICAgICAgICBjb25zdCBxdWVyeURhdGVSZW5kZXJlZCA9IHF1ZXJ5RGF0ZUVuZ2luZS5yZW5kZXIoeyB1c2VyQ3VycmVudFRpbWUsIHVzZXJXb3JrVGltZXM6IHVzZXJXb3JrVGltZXMsIHVzZXJJbnB1dCB9KVxuXG4gICAgICAgIGNvbnN0IHF1ZXJ5RGF0ZVVzZXJNZXNzYWdlSW5wdXQgPSB7IHJvbGU6ICd1c2VyJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHF1ZXJ5RGF0ZVJlbmRlcmVkIH1cbiAgICAgICAgcXVlcnlEYXRlTWVzc2FnZUhpc3RvcnkucHVzaChxdWVyeURhdGVTeXNNZXNzYWdlLCBxdWVyeURhdGVVc2VyTWVzc2FnZTEsIHF1ZXJ5RGF0ZUFzc2lzdGFudE1lc3NhZ2UxLCBxdWVyeURhdGVVc2VyTWVzc2FnZTIsIHF1ZXJ5RGF0ZUFzc2lzdGFudE1lc3NhZ2UyLCBxdWVyeURhdGVVc2VyTWVzc2FnZTMsIHF1ZXJ5RGF0ZUFzc2lzdGFudE1lc3NhZ2UzLFxuICAgICAgICAgICAgcXVlcnlEYXRlVXNlck1lc3NhZ2U0LCBxdWVyeURhdGVBc3Npc3RhbnRNZXNzYWdlNCwgcXVlcnlEYXRlVXNlck1lc3NhZ2VJbnB1dClcblxuICAgICAgICBjb25zdCBvcGVuQUlRdWVyeURhdGUgPSBhd2FpdCBjYWxsT3BlbkFJV2l0aE1lc3NhZ2VIaXN0b3J5T25seShvcGVuYWksIHF1ZXJ5RGF0ZU1lc3NhZ2VIaXN0b3J5LCBvcGVuQUlDaGF0R1BUMzVNb2RlbClcbiAgICAgICAgY29uc3QgcXVlcnlEYXRlU3RhcnRJbmRleCA9IG9wZW5BSVF1ZXJ5RGF0ZS5pbmRleE9mKCd7JylcbiAgICAgICAgY29uc3QgcXVlcnlEYXRlRW5kSW5kZXggPSBvcGVuQUlRdWVyeURhdGUubGFzdEluZGV4T2YoJ30nKVxuICAgICAgICBjb25zdCBxdWVyeURhdGVKU09OU3RyaW5nID0gb3BlbkFJUXVlcnlEYXRlLnNsaWNlKHF1ZXJ5RGF0ZVN0YXJ0SW5kZXgsIHF1ZXJ5RGF0ZUVuZEluZGV4ICsgMSlcbiAgICAgICAgY29uc3QgcXVlcnlEYXRlOiBRdWVyeUNhbGVuZGFyRXh0cmFjdGVkSlNPTlR5cGUgPSBKU09OLnBhcnNlKHF1ZXJ5RGF0ZUpTT05TdHJpbmcpXG5cbiAgICAgICAgcmV0dXJuIHF1ZXJ5RGF0ZVxuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignVW5hYmxlIHRvIGdlbmVyYXRlIG1pc3NpbmcgZmllbGRzIHF1ZXJ5RGF0ZSBmcm9tIHVzZXIgaW5wdXQnLCB7IHVzZXJJZCwgdGltZXpvbmUsIHVzZXJJbnB1dCwgcHJpb3JVc2VySW5wdXQsIHByaW9yQXNzaXN0YW50T3V0cHV0LCB1c2VyQ3VycmVudFRpbWUsIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSwgc3RhY2s6IChlIGFzIEVycm9yKS5zdGFjayB9KTtcbiAgICAgICAgcmV0dXJuIHVuZGVmaW5lZDtcbiAgICB9XG59XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZURhdGVUaW1lID0gYXN5bmMgKFxuICAgIHVzZXJJbnB1dDogc3RyaW5nLFxuICAgIHVzZXJDdXJyZW50VGltZTogc3RyaW5nLFxuICAgIHRpbWV6b25lOiBzdHJpbmcsXG4pID0+IHtcbiAgICB0cnkge1xuICAgICAgICAvLyBkYXlqcygpLnR6KHRpbWV6b25lKS5mb3JtYXQoJ2RkZGQsIFlZWVktTU0tRERUSEg6bW06c3NaJylcbiAgICAgICAgY29uc3QgdGVtcGxhdGUgPSB1c2VySW5wdXRUb0RhdGVUaW1lSlNPTlByb21wdFxuICAgICAgICBjb25zdCBlbmdpbmUgPSBuZXcgVGVtcGxhdGVFbmdpbmUodGVtcGxhdGUpXG4gICAgICAgIGNvbnN0IHJlbmRlcmVkID0gZW5naW5lLnJlbmRlcih7IHVzZXJDdXJyZW50VGltZSB9KVxuICAgICAgICBjb25zdCBzeXN0ZW1NZXNzYWdlMSA9IHsgcm9sZTogJ3N5c3RlbScgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiByZW5kZXJlZCB9XG4gICAgICAgIGNvbnN0IHVzZXJNZXNzYWdlMSA9IHsgcm9sZTogJ3VzZXInIGFzIENoYXRHUFRSb2xlVHlwZSwgY29udGVudDogdXNlcklucHV0VG9EYXRlVGltZUpTT05FeGFtcGxlSW5wdXQxIH1cblxuICAgICAgICBjb25zdCBleGFtcGxlT3V0cHV0MVRlbXBsYXRlID0gdXNlcklucHV0VG9EYXRlVGltZUpTT05FeGFtcGxlT3V0cHV0MVxuICAgICAgICBjb25zdCBlbmdpbmUyID0gbmV3IFRlbXBsYXRlRW5naW5lKGV4YW1wbGVPdXRwdXQxVGVtcGxhdGUpXG4gICAgICAgIGNvbnN0IGN1cnJlbnRUaW1lT2JqZWN0ID0gZGF5anModXNlckN1cnJlbnRUaW1lLCAnZGRkZCwgWVlZWS1NTS1ERFRISDptbTpzc1onKS50eih0aW1lem9uZSlcbiAgICAgICAgY29uc3QgeWVhciA9IGN1cnJlbnRUaW1lT2JqZWN0LmZvcm1hdCgnWVlZWScpXG4gICAgICAgIGNvbnN0IG1vbnRoID0gY3VycmVudFRpbWVPYmplY3QuZm9ybWF0KCdNTScpXG4gICAgICAgIGNvbnN0IGV4YW1wbGVPdXRwdXQxUmVuZGVyZWQgPSBlbmdpbmUyLnJlbmRlcih7IHllYXIsIG1vbnRoIH0pXG4gICAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UxID0geyByb2xlOiAnYXNzaXN0YW50JyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IGV4YW1wbGVPdXRwdXQxUmVuZGVyZWQgfVxuXG4gICAgICAgIGNvbnN0IHVzZXJNZXNzYWdlMiA9IHsgcm9sZTogJ3VzZXInIGFzIENoYXRHUFRSb2xlVHlwZSwgY29udGVudDogdXNlcklucHV0VG9EYXRlVGltZUpTT05FeGFtcGxlSW5wdXQyIH1cblxuICAgICAgICBjb25zdCBleGFtcGxlT3V0cHV0MlRlbXBsYXRlID0gdXNlcklucHV0VG9EYXRlVGltZUpTT05FeGFtcGxlT3V0cHV0MlxuICAgICAgICBjb25zdCBlbmdpbmUzID0gbmV3IFRlbXBsYXRlRW5naW5lKGV4YW1wbGVPdXRwdXQyVGVtcGxhdGUpXG4gICAgICAgIGNvbnN0IGV4YW1wbGVPdXRwdXQyUmVuZGVyZWQgPSBlbmdpbmUzLnJlbmRlcih7IHllYXIsIG1vbnRoIH0pXG4gICAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UyID0geyByb2xlOiAnYXNzaXN0YW50JyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IGV4YW1wbGVPdXRwdXQyUmVuZGVyZWQgfVxuXG4gICAgICAgIGNvbnN0IHVzZXJNZXNzYWdlMyA9IHsgcm9sZTogJ3VzZXInIGFzIENoYXRHUFRSb2xlVHlwZSwgY29udGVudDogdXNlcklucHV0VG9EYXRlVGltZUpTT05FeGFtcGxlSW5wdXQzIH1cbiAgICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZTMgPSB7IHJvbGU6ICdhc3Npc3RhbnQnIGFzIENoYXRHUFRSb2xlVHlwZSwgY29udGVudDogdXNlcklucHV0VG9EYXRlVGltZUpTT05FeGFtcGxlT3V0cHV0MyB9XG5cblxuICAgICAgICBjb25zdCB1c2VyTWVzc2FnZTQgPSB7IHJvbGU6ICd1c2VyJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHVzZXJJbnB1dCB9XG5cbiAgICAgICAgY29uc3QgbWVzc2FnZUhpc3Rvcnk6IENoYXRHUFRNZXNzYWdlSGlzdG9yeVR5cGUgPSBbXVxuXG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5LnB1c2goc3lzdGVtTWVzc2FnZTEsIHVzZXJNZXNzYWdlMSwgYXNzaXN0YW50TWVzc2FnZTEsIHVzZXJNZXNzYWdlNClcblxuICAgICAgICBjb25zdCBvcGVuQUlEYXRlVGltZSA9IGF3YWl0IGNhbGxPcGVuQUlXaXRoTWVzc2FnZUhpc3RvcnlPbmx5KG9wZW5haSwgbWVzc2FnZUhpc3RvcnksIG9wZW5BSUNoYXRHUFQzNU1vZGVsKVxuXG4gICAgICAgIC8vIGNvbnN0IG9wZW5BSURhdGVUaW1lID0gYXdhaXQgY2FsbE9wZW5BSShvcGVuYWksIHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09OUHJvbXB0LCBvcGVuQUlDaGF0R1BUMzVNb2RlbCwgdXNlcklucHV0LCB1c2VySW5wdXRUb0RhdGVUaW1lSlNPTkV4YW1wbGVJbnB1dDEsIHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09ORXhhbXBsZU91dHB1dDEpXG4gICAgICAgIGNvbnN0IGRhdGVUaW1lU3RhcnRJbmRleCA9IG9wZW5BSURhdGVUaW1lLmluZGV4T2YoJ3snKVxuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmRlYnVnKCdbZ2VuZXJhdGVEYXRlVGltZV0gT3BlbkFJIHJlc3BvbnNlIHByb2Nlc3NpbmcnLCB7IGRhdGVUaW1lU3RhcnRJbmRleCwgb3BlbkFJRGF0ZVRpbWVMZW5ndGg6IG9wZW5BSURhdGVUaW1lPy5sZW5ndGggfSk7XG4gICAgICAgIGNvbnN0IGRhdGVUaW1lRW5kSW5kZXggPSBvcGVuQUlEYXRlVGltZS5sYXN0SW5kZXhPZignfScpXG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoJ1tnZW5lcmF0ZURhdGVUaW1lXSBPcGVuQUkgcmVzcG9uc2UgcHJvY2Vzc2luZycsIHsgZGF0ZVRpbWVFbmRJbmRleCB9KTtcbiAgICAgICAgY29uc3QgZGF0ZVRpbWVKU09OU3RyaW5nID0gb3BlbkFJRGF0ZVRpbWUuc2xpY2UoZGF0ZVRpbWVTdGFydEluZGV4LCBkYXRlVGltZUVuZEluZGV4ICsgMSlcbiAgICAgICAgY29uc3QgZGF0ZVRpbWU6IERhdGVUaW1lSlNPTlR5cGUgPSBKU09OLnBhcnNlKGRhdGVUaW1lSlNPTlN0cmluZylcblxuICAgICAgICByZXR1cm4gZGF0ZVRpbWVcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoJ1VuYWJsZSB0byBnZW5lcmF0ZSBEYXRlVGltZSBmcm9tIHVzZXIgaW5wdXQnLCB7IHVzZXJJbnB1dCwgdXNlckN1cnJlbnRUaW1lLCB0aW1lem9uZSwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlLCBzdGFjazogKGUgYXMgRXJyb3IpLnN0YWNrIH0pO1xuICAgICAgICByZXR1cm4gdW5kZWZpbmVkO1xuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0RhdGVUaW1lID0gYXN5bmMgKFxuICAgIHVzZXJJbnB1dDogc3RyaW5nLFxuICAgIHByaW9yVXNlcklucHV0OiBzdHJpbmcsXG4gICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQ6IHN0cmluZyxcbiAgICB1c2VyQ3VycmVudFRpbWU6IHN0cmluZyxcbiAgICB0aW1lem9uZTogc3RyaW5nLFxuKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgLy8gZGF5anMoKS50eih0aW1lem9uZSkuZm9ybWF0KCdkZGRkLCBZWVlZLU1NLUREVEhIOm1tOnNzWicpXG4gICAgICAgIGNvbnN0IHRlbXBsYXRlID0gdXNlcklucHV0VG9EYXRlVGltZUpTT05Qcm9tcHRcbiAgICAgICAgY29uc3QgZW5naW5lID0gbmV3IFRlbXBsYXRlRW5naW5lKHRlbXBsYXRlKVxuICAgICAgICBjb25zdCByZW5kZXJlZCA9IGVuZ2luZS5yZW5kZXIoeyB1c2VyQ3VycmVudFRpbWUgfSlcbiAgICAgICAgY29uc3Qgc3lzdGVtTWVzc2FnZTEgPSB7IHJvbGU6ICdzeXN0ZW0nIGFzIENoYXRHUFRSb2xlVHlwZSwgY29udGVudDogcmVuZGVyZWQgfVxuICAgICAgICBjb25zdCB1c2VyTWVzc2FnZTEgPSB7IHJvbGU6ICd1c2VyJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09ORXhhbXBsZUlucHV0MSB9XG5cbiAgICAgICAgY29uc3QgZXhhbXBsZU91dHB1dDFUZW1wbGF0ZSA9IHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09ORXhhbXBsZU91dHB1dDFcbiAgICAgICAgY29uc3QgZW5naW5lMiA9IG5ldyBUZW1wbGF0ZUVuZ2luZShleGFtcGxlT3V0cHV0MVRlbXBsYXRlKVxuICAgICAgICBjb25zdCBjdXJyZW50VGltZU9iamVjdCA9IGRheWpzKHVzZXJDdXJyZW50VGltZSwgJ2RkZGQsIFlZWVktTU0tRERUSEg6bW06c3NaJykudHoodGltZXpvbmUpXG4gICAgICAgIGNvbnN0IHllYXIgPSBjdXJyZW50VGltZU9iamVjdC5mb3JtYXQoJ1lZWVknKVxuICAgICAgICBjb25zdCBtb250aCA9IGN1cnJlbnRUaW1lT2JqZWN0LmZvcm1hdCgnTU0nKVxuICAgICAgICBjb25zdCBleGFtcGxlT3V0cHV0MVJlbmRlcmVkID0gZW5naW5lMi5yZW5kZXIoeyB5ZWFyLCBtb250aCB9KVxuICAgICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlMSA9IHsgcm9sZTogJ2Fzc2lzdGFudCcgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiBleGFtcGxlT3V0cHV0MVJlbmRlcmVkIH1cblxuICAgICAgICBjb25zdCB1c2VyTWVzc2FnZTIgPSB7IHJvbGU6ICd1c2VyJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09ORXhhbXBsZUlucHV0MiB9XG5cbiAgICAgICAgY29uc3QgZXhhbXBsZU91dHB1dDJUZW1wbGF0ZSA9IHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09ORXhhbXBsZU91dHB1dDJcbiAgICAgICAgY29uc3QgZW5naW5lMyA9IG5ldyBUZW1wbGF0ZUVuZ2luZShleGFtcGxlT3V0cHV0MlRlbXBsYXRlKVxuICAgICAgICBjb25zdCBleGFtcGxlT3V0cHV0MlJlbmRlcmVkID0gZW5naW5lMy5yZW5kZXIoeyB5ZWFyLCBtb250aCB9KVxuICAgICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlMiA9IHsgcm9sZTogJ2Fzc2lzdGFudCcgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiBleGFtcGxlT3V0cHV0MlJlbmRlcmVkIH1cblxuICAgICAgICBjb25zdCB1c2VyTWVzc2FnZTMgPSB7IHJvbGU6ICd1c2VyJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09ORXhhbXBsZUlucHV0MyB9XG4gICAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UzID0geyByb2xlOiAnYXNzaXN0YW50JyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09ORXhhbXBsZU91dHB1dDMgfVxuXG4gICAgICAgIGNvbnN0IHVzZXJNZXNzYWdlNCA9IHsgcm9sZTogJ3VzZXInIGFzIENoYXRHUFRSb2xlVHlwZSwgY29udGVudDogcHJpb3JVc2VySW5wdXQgfVxuICAgICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlNCA9IHsgcm9sZTogJ2Fzc2lzdGFudCcgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiBwcmlvckFzc2lzdGFudE91dHB1dCB9XG5cbiAgICAgICAgY29uc3QgdXNlck1lc3NhZ2U1ID0geyByb2xlOiAndXNlcicgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiB1c2VySW5wdXQgfVxuXG4gICAgICAgIGNvbnN0IG1lc3NhZ2VIaXN0b3J5OiBDaGF0R1BUTWVzc2FnZUhpc3RvcnlUeXBlID0gW11cblxuICAgICAgICBtZXNzYWdlSGlzdG9yeS5wdXNoKHN5c3RlbU1lc3NhZ2UxLCB1c2VyTWVzc2FnZTEsIGFzc2lzdGFudE1lc3NhZ2UxLCB1c2VyTWVzc2FnZTIsIGFzc2lzdGFudE1lc3NhZ2UyLCB1c2VyTWVzc2FnZTMsIGFzc2lzdGFudE1lc3NhZ2UzLCB1c2VyTWVzc2FnZTQsIGFzc2lzdGFudE1lc3NhZ2U0LCB1c2VyTWVzc2FnZTUpXG5cbiAgICAgICAgY29uc3Qgb3BlbkFJRGF0ZVRpbWUgPSBhd2FpdCBjYWxsT3BlbkFJV2l0aE1lc3NhZ2VIaXN0b3J5T25seShvcGVuYWksIG1lc3NhZ2VIaXN0b3J5LCBvcGVuQUlDaGF0R1BUMzVMb25nTW9kZWwpXG5cbiAgICAgICAgLy8gY29uc3Qgb3BlbkFJRGF0ZVRpbWUgPSBhd2FpdCBjYWxsT3BlbkFJKG9wZW5haSwgdXNlcklucHV0VG9EYXRlVGltZUpTT05Qcm9tcHQsIG9wZW5BSUNoYXRHUFQzNU1vZGVsLCB1c2VySW5wdXQsIHVzZXJJbnB1dFRvRGF0ZVRpbWVKU09ORXhhbXBsZUlucHV0MSwgdXNlcklucHV0VG9EYXRlVGltZUpTT05FeGFtcGxlT3V0cHV0MSlcbiAgICAgICAgY29uc3QgZGF0ZVRpbWVTdGFydEluZGV4ID0gb3BlbkFJRGF0ZVRpbWUuaW5kZXhPZigneycpXG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoJ1tnZW5lcmF0ZU1pc3NpbmdGaWVsZHNEYXRlVGltZV0gT3BlbkFJIHJlc3BvbnNlIHByb2Nlc3NpbmcnLCB7IGRhdGVUaW1lU3RhcnRJbmRleCwgb3BlbkFJRGF0ZVRpbWVMZW5ndGg6IG9wZW5BSURhdGVUaW1lPy5sZW5ndGggfSk7XG4gICAgICAgIGNvbnN0IGRhdGVUaW1lRW5kSW5kZXggPSBvcGVuQUlEYXRlVGltZS5sYXN0SW5kZXhPZignfScpXG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZGVidWcoJ1tnZW5lcmF0ZU1pc3NpbmdGaWVsZHNEYXRlVGltZV0gT3BlbkFJIHJlc3BvbnNlIHByb2Nlc3NpbmcnLCB7IGRhdGVUaW1lRW5kSW5kZXggfSk7XG4gICAgICAgIGNvbnN0IGRhdGVUaW1lSlNPTlN0cmluZyA9IG9wZW5BSURhdGVUaW1lLnNsaWNlKGRhdGVUaW1lU3RhcnRJbmRleCwgZGF0ZVRpbWVFbmRJbmRleCArIDEpXG4gICAgICAgIGNvbnN0IGRhdGVUaW1lOiBEYXRlVGltZUpTT05UeXBlID0gSlNPTi5wYXJzZShkYXRlVGltZUpTT05TdHJpbmcpXG5cbiAgICAgICAgcmV0dXJuIGRhdGVUaW1lXG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdVbmFibGUgdG8gZ2VuZXJhdGUgbWlzc2luZyBmaWVsZHMgRGF0ZVRpbWUgZnJvbSB1c2VyIGlucHV0JywgeyB1c2VySW5wdXQsIHByaW9yVXNlcklucHV0LCBwcmlvckFzc2lzdGFudE91dHB1dCwgdXNlckN1cnJlbnRUaW1lLCB0aW1lem9uZSwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlLCBzdGFjazogKGUgYXMgRXJyb3IpLnN0YWNrIH0pO1xuICAgICAgICByZXR1cm4gdW5kZWZpbmVkO1xuICAgIH1cbn1cblxuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlRnJvbUFQSVJlc3BvbnNlRm9yVXNlclF1ZXJ5ID0gYXN5bmMgKFxuICAgIG9wZW5haUluc3RhbmNlOiBPcGVuQUksXG4gICAgYXBpUmVzcG9uc2U6IHN0cmluZyxcbiAgICBtZXNzYWdlSGlzdG9yeU9iamVjdDogU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGVcbik6IFByb21pc2U8QXNzaXN0YW50TWVzc2FnZVR5cGU+ID0+IHtcbiAgICB0cnkge1xuICAgICAgICBjb25zdCBtZXNzYWdlTGVuZ3RoID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXM/Lmxlbmd0aFxuICAgICAgICBsZXQgdXNlck1lc3NhZ2UgPSAnJ1xuICAgICAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuXG4gICAgICAgICAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXNbaSAtIDFdXG5cbiAgICAgICAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICd1c2VyJykge1xuICAgICAgICAgICAgICAgIHVzZXJNZXNzYWdlID0gbWVzc2FnZS5jb250ZW50XG4gICAgICAgICAgICAgICAgYnJlYWtcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHRlbXBsYXRlID0gYXBpUmVzcG9uZVRvQXNzaXN0YW50UmVzcG9uc2VQcm9tcHRcbiAgICAgICAgY29uc3QgZW5naW5lID0gbmV3IFRlbXBsYXRlRW5naW5lKHRlbXBsYXRlKVxuICAgICAgICBjb25zdCByZW5kZXJlZCA9IGVuZ2luZS5yZW5kZXIoeyB1c2VySW5wdXQ6IHVzZXJNZXNzYWdlLCBhcGlSZXNwb25zZSB9KVxuXG4gICAgICAgIGNvbnN0IHN5c3RlbU1lc3NhZ2U6IFN5c3RlbU1lc3NhZ2VUeXBlID0ge1xuICAgICAgICAgICAgcm9sZTogJ3N5c3RlbScsXG4gICAgICAgICAgICBjb250ZW50OiByZW5kZXJlZCxcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHJlcyA9IGF3YWl0IGNhbGxPcGVuQUlXaXRoTWVzc2FnZUhpc3RvcnlPbmx5KG9wZW5haSwgW3N5c3RlbU1lc3NhZ2VdLCBvcGVuQUlDaGF0R1BUMzVNb2RlbClcblxuICAgICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlOiBBc3Npc3RhbnRNZXNzYWdlVHlwZSA9IHtcbiAgICAgICAgICAgIHJvbGU6ICdhc3Npc3RhbnQnLFxuICAgICAgICAgICAgY29udGVudDogcmVzLFxuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIGFzc2lzdGFudE1lc3NhZ2VcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoJ1VuYWJsZSB0byBnZW5lcmF0ZSBhc3Npc3RhbnQgbWVzc2FnZSBmcm9tIEFQSSByZXNwb25zZScsIHsgYXBpUmVzcG9uc2UsIG1lc3NhZ2VIaXN0b3J5T2JqZWN0SWQ6IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5pZCwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlLCBzdGFjazogKGUgYXMgRXJyb3IpLnN0YWNrIH0pO1xuICAgICAgICAvLyBDb25zaWRlciByZXR1cm5pbmcgYSBkZWZhdWx0IGVycm9yIG1lc3NhZ2Ugb3IgcmV0aHJvd2luZ1xuICAgICAgICByZXR1cm4geyByb2xlOiAnYXNzaXN0YW50JywgY29udGVudDogXCJJIGVuY291bnRlcmVkIGFuIGlzc3VlIHByb2Nlc3NpbmcgdGhhdCByZXF1ZXN0LiBQbGVhc2UgdHJ5IGFnYWluLlwiIH07IC8vIEV4YW1wbGUgZmFsbGJhY2tcbiAgICB9XG59XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VUb1JlcXVlc3RVc2VyRm9yTWlzc2luZ0ZpZWxkcyA9IGFzeW5jIChcbiAgICBvcGVuYWlJbnN0YW5jZTogT3BlbkFJLFxuICAgIG1pc3NpbmdEYXRhOiBSZXF1aXJlZEZpZWxkc1R5cGUsXG4gICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlXG4pOiBQcm9taXNlPEFzc2lzdGFudE1lc3NhZ2VUeXBlPiA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgbGV0IG1pc3NpbmdEYXRhU3RyaW5nID0gJydcblxuICAgICAgICBmb3IgKGNvbnN0IHByb3BlcnR5IGluIG1pc3NpbmdEYXRhKSB7XG5cbiAgICAgICAgICAgIGlmIChwcm9wZXJ0eSA9PT0gJ3JlcXVpcmVkJykge1xuXG4gICAgICAgICAgICAgICAgY29uc3QgcmVxdWlyZWRGaWVsZHMgPSBtaXNzaW5nRGF0YT8uW3Byb3BlcnR5XVxuXG4gICAgICAgICAgICAgICAgaWYgKHJlcXVpcmVkRmllbGRzPy5sZW5ndGggPiAwKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgZm9yIChjb25zdCByZXF1aXJlZEZpZWxkIG9mIHJlcXVpcmVkRmllbGRzKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgIGZvciAoY29uc3QgcmVxdWlyZWRQcm9wZXJ0eSBpbiByZXF1aXJlZEZpZWxkKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBpZiAocmVxdWlyZWRQcm9wZXJ0eSA9PT0gJ29uZU9mJykge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb25zdCBvbmVPZnMgPSByZXF1aXJlZEZpZWxkW3JlcXVpcmVkUHJvcGVydHldXG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaWYgKG9uZU9mcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgZm9yIChjb25zdCBvbmVPZiBvZiBvbmVPZnMpIHtcblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGZvciAoY29uc3Qgb25lT2ZQcm9wZXJ0eSBpbiBvbmVPZikge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlmIChvbmVPZlByb3BlcnR5ID09PSAnYW5kJykge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb25zdCBvYmplY3RGaWVsZHMgPSBvbmVPZltvbmVPZlByb3BlcnR5XVxuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBpZiAob2JqZWN0RmllbGRzPy5sZW5ndGggPiAwKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBmb3IgKGNvbnN0IG9iamVjdEZpZWxkIG9mIG9iamVjdEZpZWxkcykge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1pc3NpbmdEYXRhU3RyaW5nICs9IGAke29iamVjdEZpZWxkPy52YWx1ZX0sIGBcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAob25lT2ZQcm9wZXJ0eSA9PT0gJ3ZhbHVlJykge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb25zdCB2YWx1ZSA9IG9uZU9mW29uZU9mUHJvcGVydHldXG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1pc3NpbmdEYXRhU3RyaW5nICs9IGAke3ZhbHVlfSwgYFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgfSBlbHNlIGlmIChyZXF1aXJlZFByb3BlcnR5ID09PSAndmFsdWUnKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY29uc3QgdmFsdWUgPSByZXF1aXJlZEZpZWxkW3JlcXVpcmVkUHJvcGVydHldXG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgbWlzc2luZ0RhdGFTdHJpbmcgKz0gYCR7dmFsdWV9LCBgXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgfSBlbHNlIGlmIChyZXF1aXJlZFByb3BlcnR5ID09PSAnYW5kJykge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb25zdCBvYmplY3RGaWVsZHMgPSByZXF1aXJlZEZpZWxkW3JlcXVpcmVkUHJvcGVydHldXG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaWYgKG9iamVjdEZpZWxkcz8ubGVuZ3RoID4gMCkge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBmb3IgKGNvbnN0IG9iamVjdEZpZWxkIG9mIG9iamVjdEZpZWxkcykge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgbWlzc2luZ0RhdGFTdHJpbmcgKz0gYCR7b2JqZWN0RmllbGQ/LnZhbHVlfSwgYFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2RhdGVUaW1lJykge1xuICAgICAgICAgICAgICAgIGNvbnN0IGRhdGVUaW1lID0gbWlzc2luZ0RhdGFbcHJvcGVydHldXG5cbiAgICAgICAgICAgICAgICBmb3IgKGNvbnN0IGRhdGVUaW1lUHJvcGVydHkgaW4gZGF0ZVRpbWUpIHtcblxuICAgICAgICAgICAgICAgICAgICBpZiAoZGF0ZVRpbWVQcm9wZXJ0eSA9PT0gJ3JlcXVpcmVkJykge1xuICAgICAgICAgICAgICAgICAgICAgICAgY29uc3QgcmVxdWlyZWRGaWVsZHMgPSBkYXRlVGltZT8uW2RhdGVUaW1lUHJvcGVydHldXG5cbiAgICAgICAgICAgICAgICAgICAgICAgIGlmIChyZXF1aXJlZEZpZWxkcz8ubGVuZ3RoID4gMCkge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZm9yIChjb25zdCByZXF1aXJlZEZpZWxkIG9mIHJlcXVpcmVkRmllbGRzKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgZm9yIChjb25zdCByZXF1aXJlZFByb3BlcnR5IGluIHJlcXVpcmVkRmllbGQpIHtcblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaWYgKHJlcXVpcmVkUHJvcGVydHkgPT09ICdvbmVPZicpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb25zdCBvbmVPZnMgPSByZXF1aXJlZEZpZWxkW3JlcXVpcmVkUHJvcGVydHldXG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBpZiAob25lT2ZzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGZvciAoY29uc3Qgb25lT2Ygb2Ygb25lT2ZzKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGZvciAoY29uc3Qgb25lT2ZQcm9wZXJ0eSBpbiBvbmVPZikge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaWYgKG9uZU9mUHJvcGVydHkgPT09ICdhbmQnKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY29uc3Qgb2JqZWN0RmllbGRzID0gb25lT2Zbb25lT2ZQcm9wZXJ0eV1cblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBpZiAob2JqZWN0RmllbGRzPy5sZW5ndGggPiAwKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGZvciAoY29uc3Qgb2JqZWN0RmllbGQgb2Ygb2JqZWN0RmllbGRzKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBtaXNzaW5nRGF0YVN0cmluZyArPSBgJHtvYmplY3RGaWVsZD8udmFsdWV9LCBgXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9IGVsc2UgaWYgKG9uZU9mUHJvcGVydHkgPT09ICd2YWx1ZScpIHtcblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb25zdCB2YWx1ZSA9IG9uZU9mW29uZU9mUHJvcGVydHldXG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgbWlzc2luZ0RhdGFTdHJpbmcgKz0gYCR7dmFsdWV9LCBgXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSBlbHNlIGlmIChyZXF1aXJlZFByb3BlcnR5ID09PSAndmFsdWUnKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb25zdCB2YWx1ZSA9IHJlcXVpcmVkRmllbGRbcmVxdWlyZWRQcm9wZXJ0eV1cblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1pc3NpbmdEYXRhU3RyaW5nICs9IGAke3ZhbHVlfSwgYFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSBlbHNlIGlmIChyZXF1aXJlZFByb3BlcnR5ID09PSAnYW5kJykge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvbnN0IG9iamVjdEZpZWxkcyA9IHJlcXVpcmVkRmllbGRbcmVxdWlyZWRQcm9wZXJ0eV1cblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlmIChvYmplY3RGaWVsZHM/Lmxlbmd0aCA+IDApIHtcblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBmb3IgKGNvbnN0IG9iamVjdEZpZWxkIG9mIG9iamVjdEZpZWxkcykge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBtaXNzaW5nRGF0YVN0cmluZyArPSBgJHtvYmplY3RGaWVsZD8udmFsdWV9LCBgXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnYXR0cmlidXRlcycpIHtcbiAgICAgICAgICAgICAgICBjb25zdCBhdHRyaWJ1dGVzID0gbWlzc2luZ0RhdGFbcHJvcGVydHldXG5cbiAgICAgICAgICAgICAgICBmb3IgKGNvbnN0IGF0dHJpYnV0ZXNQcm9wZXJ0eSBpbiBhdHRyaWJ1dGVzKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgaWYgKGF0dHJpYnV0ZXNQcm9wZXJ0eSA9PT0gJ3JlcXVpcmVkJykge1xuICAgICAgICAgICAgICAgICAgICAgICAgY29uc3QgcmVxdWlyZWRGaWVsZHMgPSBhdHRyaWJ1dGVzPy5bYXR0cmlidXRlc1Byb3BlcnR5XVxuXG4gICAgICAgICAgICAgICAgICAgICAgICBpZiAocmVxdWlyZWRGaWVsZHM/Lmxlbmd0aCA+IDApIHtcblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGZvciAoY29uc3QgcmVxdWlyZWRGaWVsZCBvZiByZXF1aXJlZEZpZWxkcykge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGZvciAoY29uc3QgcmVxdWlyZWRQcm9wZXJ0eSBpbiByZXF1aXJlZEZpZWxkKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlmIChyZXF1aXJlZFByb3BlcnR5ID09PSAnb25lT2YnKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY29uc3Qgb25lT2ZzID0gcmVxdWlyZWRGaWVsZFtyZXF1aXJlZFByb3BlcnR5XVxuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaWYgKG9uZU9mcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBmb3IgKGNvbnN0IG9uZU9mIG9mIG9uZU9mcykge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBmb3IgKGNvbnN0IG9uZU9mUHJvcGVydHkgaW4gb25lT2YpIHtcblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlmIChvbmVPZlByb3BlcnR5ID09PSAnYW5kJykge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvbnN0IG9iamVjdEZpZWxkcyA9IG9uZU9mW29uZU9mUHJvcGVydHldXG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaWYgKG9iamVjdEZpZWxkcz8ubGVuZ3RoID4gMCkge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBmb3IgKGNvbnN0IG9iamVjdEZpZWxkIG9mIG9iamVjdEZpZWxkcykge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgbWlzc2luZ0RhdGFTdHJpbmcgKz0gYCR7b2JqZWN0RmllbGQ/LnZhbHVlfSwgYFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSBlbHNlIGlmIChvbmVPZlByb3BlcnR5ID09PSAndmFsdWUnKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY29uc3QgdmFsdWUgPSBvbmVPZltvbmVPZlByb3BlcnR5XVxuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1pc3NpbmdEYXRhU3RyaW5nICs9IGAke3ZhbHVlfSwgYFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAocmVxdWlyZWRQcm9wZXJ0eSA9PT0gJ3ZhbHVlJykge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY29uc3QgdmFsdWUgPSByZXF1aXJlZEZpZWxkW3JlcXVpcmVkUHJvcGVydHldXG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBtaXNzaW5nRGF0YVN0cmluZyArPSBgJHt2YWx1ZX0sIGBcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAocmVxdWlyZWRQcm9wZXJ0eSA9PT0gJ2FuZCcpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb25zdCBvYmplY3RGaWVsZHMgPSByZXF1aXJlZEZpZWxkW3JlcXVpcmVkUHJvcGVydHldXG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBpZiAob2JqZWN0RmllbGRzPy5sZW5ndGggPiAwKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgZm9yIChjb25zdCBvYmplY3RGaWVsZCBvZiBvYmplY3RGaWVsZHMpIHtcblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgbWlzc2luZ0RhdGFTdHJpbmcgKz0gYCR7b2JqZWN0RmllbGQ/LnZhbHVlfSwgYFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3F1ZXJ5RGF0ZScpIHtcbiAgICAgICAgICAgICAgICBjb25zdCBxdWVyeURhdGUgPSBtaXNzaW5nRGF0YVtwcm9wZXJ0eV1cblxuICAgICAgICAgICAgICAgIGZvciAoY29uc3QgcXVlcnlEYXRlUHJvcGVydHkgaW4gcXVlcnlEYXRlKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgaWYgKHF1ZXJ5RGF0ZVByb3BlcnR5ID09PSAncmVxdWlyZWQnKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICBjb25zdCByZXF1aXJlZEZpZWxkcyA9IHF1ZXJ5RGF0ZT8uW3F1ZXJ5RGF0ZVByb3BlcnR5XVxuXG4gICAgICAgICAgICAgICAgICAgICAgICBpZiAocmVxdWlyZWRGaWVsZHM/Lmxlbmd0aCA+IDApIHtcblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGZvciAoY29uc3QgcmVxdWlyZWRGaWVsZCBvZiByZXF1aXJlZEZpZWxkcykge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGZvciAoY29uc3QgcmVxdWlyZWRQcm9wZXJ0eSBpbiByZXF1aXJlZEZpZWxkKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlmIChyZXF1aXJlZFByb3BlcnR5ID09PSAnb25lT2YnKSB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY29uc3Qgb25lT2ZzID0gcmVxdWlyZWRGaWVsZFtyZXF1aXJlZFByb3BlcnR5XVxuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaWYgKG9uZU9mcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBmb3IgKGNvbnN0IG9uZU9mIG9mIG9uZU9mcykge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBmb3IgKGNvbnN0IG9uZU9mUHJvcGVydHkgaW4gb25lT2YpIHtcblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlmIChvbmVPZlByb3BlcnR5ID09PSAnYW5kJykge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvbnN0IG9iamVjdEZpZWxkcyA9IG9uZU9mW29uZU9mUHJvcGVydHldXG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaWYgKG9iamVjdEZpZWxkcz8ubGVuZ3RoID4gMCkge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBmb3IgKGNvbnN0IG9iamVjdEZpZWxkIG9mIG9iamVjdEZpZWxkcykge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgbWlzc2luZ0RhdGFTdHJpbmcgKz0gYCR7b2JqZWN0RmllbGQ/LnZhbHVlfSwgYFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfSBlbHNlIGlmIChvbmVPZlByb3BlcnR5ID09PSAndmFsdWUnKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY29uc3QgdmFsdWUgPSBvbmVPZltvbmVPZlByb3BlcnR5XVxuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1pc3NpbmdEYXRhU3RyaW5nICs9IGAke3ZhbHVlfSwgYFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAocmVxdWlyZWRQcm9wZXJ0eSA9PT0gJ3ZhbHVlJykge1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY29uc3QgdmFsdWUgPSByZXF1aXJlZEZpZWxkW3JlcXVpcmVkUHJvcGVydHldXG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBtaXNzaW5nRGF0YVN0cmluZyArPSBgJHt2YWx1ZX0sIGBcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAocmVxdWlyZWRQcm9wZXJ0eSA9PT0gJ2FuZCcpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb25zdCBvYmplY3RGaWVsZHMgPSByZXF1aXJlZEZpZWxkW3JlcXVpcmVkUHJvcGVydHldXG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBpZiAob2JqZWN0RmllbGRzPy5sZW5ndGggPiAwKSB7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgZm9yIChjb25zdCBvYmplY3RGaWVsZCBvZiBvYmplY3RGaWVsZHMpIHtcblxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgbWlzc2luZ0RhdGFTdHJpbmcgKz0gYCR7b2JqZWN0RmllbGQ/LnZhbHVlfSwgYFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgbWVzc2FnZUxlbmd0aCA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzPy5sZW5ndGhcbiAgICAgICAgbGV0IHVzZXJNZXNzYWdlID0gJydcbiAgICAgICAgZm9yIChsZXQgaSA9IG1lc3NhZ2VMZW5ndGg7IGkgPiAwOyBpLS0pIHtcblxuICAgICAgICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzW2kgLSAxXVxuXG4gICAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAndXNlcicpIHtcbiAgICAgICAgICAgICAgICB1c2VyTWVzc2FnZSA9IG1lc3NhZ2UuY29udGVudFxuICAgICAgICAgICAgICAgIGJyZWFrXG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgICAgY29uc3QgdGVtcGxhdGUgPSByZXF1ZXN0TWlzc2luZ0ZpZWxkc1Byb21wdFxuICAgICAgICBjb25zdCBlbmdpbmUgPSBuZXcgVGVtcGxhdGVFbmdpbmUodGVtcGxhdGUpXG4gICAgICAgIGNvbnN0IHJlbmRlcmVkID0gZW5naW5lLnJlbmRlcih7IHVzZXJJbnB1dDogdXNlck1lc3NhZ2UsIG1pc3NpbmdGaWVsZHM6IG1pc3NpbmdEYXRhU3RyaW5nIH0pXG5cbiAgICAgICAgY29uc3Qgc3lzdGVtTWVzc2FnZTI6IFN5c3RlbU1lc3NhZ2VUeXBlID0ge1xuICAgICAgICAgICAgcm9sZTogJ3N5c3RlbScsXG4gICAgICAgICAgICBjb250ZW50OiByZW5kZXJlZCxcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHN5c3RlbU1lc3NhZ2UxID0geyByb2xlOiAnc3lzdGVtJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHJlcXVlc3RNaXNzaW5nRmllbGRzU3lzdGVtc0V4YW1wbGVJbnB1dCB9XG4gICAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UxID0geyByb2xlOiAnYXNzaXN0YW50JyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHJlcXVlc3RNaXNzaW5nRmllbGRzRXhhbXBsZU91dHB1dCB9XG5cbiAgICAgICAgY29uc3QgbWVzc2FnZUhpc3Rvcnk6IENoYXRHUFRNZXNzYWdlSGlzdG9yeVR5cGUgPSBbXVxuXG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5LnB1c2goc3lzdGVtTWVzc2FnZTEsIGFzc2lzdGFudE1lc3NhZ2UxLCBzeXN0ZW1NZXNzYWdlMilcblxuICAgICAgICBjb25zdCBvcGVuQUlEYXRhID0gYXdhaXQgY2FsbE9wZW5BSVdpdGhNZXNzYWdlSGlzdG9yeU9ubHkob3BlbmFpLCBtZXNzYWdlSGlzdG9yeSwgb3BlbkFJQ2hhdEdQVDM1TW9kZWwpXG5cbiAgICAgICAgY29uc3QgYXNzaXRhbnRNZXNzYWdlOiBBc3Npc3RhbnRNZXNzYWdlVHlwZSA9IHtcbiAgICAgICAgICAgIHJvbGU6ICdhc3Npc3RhbnQnLFxuICAgICAgICAgICAgY29udGVudDogb3BlbkFJRGF0YSxcbiAgICAgICAgfVxuXG4gICAgICAgIHJldHVybiBhc3NpdGFudE1lc3NhZ2VcblxuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignVW5hYmxlIHRvIGdlbmVyYXRlIHVzZXIgcmVxdWVzdCBmb3IgbWlzc2luZyBmaWVsZHMnLCB7IG1pc3NpbmdEYXRhU3RyaW5nLCBtZXNzYWdlSGlzdG9yeU9iamVjdElkOiBtZXNzYWdlSGlzdG9yeU9iamVjdD8uaWQsIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSwgc3RhY2s6IChlIGFzIEVycm9yKS5zdGFjayB9KTtcbiAgICAgICAgcmV0dXJuIHsgcm9sZTogJ2Fzc2lzdGFudCcsIGNvbnRlbnQ6IFwiSSBuZWVkIGEgYml0IG1vcmUgaW5mb3JtYXRpb24gdG8gcHJvY2VlZC4gQ291bGQgeW91IGNsYXJpZnk/XCIgfTsgLy8gRXhhbXBsZSBmYWxsYmFja1xuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0ID0gYXN5bmMgKFxuICAgIHVzZXJJbnB1dDogc3RyaW5nLFxuICAgIHVzZXJDdXJyZW50VGltZTogc3RyaW5nLFxuKSA9PiB7XG4gICAgdHJ5IHtcblxuICAgICAgICBjb25zdCBtZXNzYWdlSGlzdG9yeTogQ2hhdEdQVE1lc3NhZ2VIaXN0b3J5VHlwZSA9IFtdXG5cbiAgICAgICAgY29uc3QgdXNlck1lc3NhZ2UxID0geyByb2xlOiAndXNlcicgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiB1c2VySW5wdXRUb0pTT05FeGFtcGxlSW5wdXQgfVxuICAgICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlMSA9IHsgcm9sZTogJ2Fzc2lzdGFudCcgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiB1c2VySW5wdXRUb0pTT05FeGFtcGxlT3V0cHV0IH1cblxuICAgICAgICBjb25zdCBkYXRhRW5naW5lID0gbmV3IFRlbXBsYXRlRW5naW5lKHVzZXJJbnB1dFRvSlNPTlByb21wdCk7XG4gICAgICAgIGNvbnN0IGRhdGFSZW5kZXJlZCA9IGRhdGFFbmdpbmUucmVuZGVyKHsgdXNlckN1cnJlbnRUaW1lIH0pXG5cbiAgICAgICAgY29uc3QgZGF0YVN5c01lc3NhZ2UgPSB7IHJvbGU6ICdzeXN0ZW0nIGFzIENoYXRHUFRSb2xlVHlwZSwgY29udGVudDogZGF0YVJlbmRlcmVkIH1cbiAgICAgICAgY29uc3QgZGF0YVVzZXJNZXNzYWdlSW5wdXQgPSB7IHJvbGU6ICd1c2VyJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHVzZXJJbnB1dCB9XG5cbiAgICAgICAgbWVzc2FnZUhpc3RvcnkucHVzaChkYXRhU3lzTWVzc2FnZSwgdXNlck1lc3NhZ2UxLCBhc3Npc3RhbnRNZXNzYWdlMSwgZGF0YVVzZXJNZXNzYWdlSW5wdXQpXG5cbiAgICAgICAgY29uc3Qgb3BlbkFJRGF0YSA9IGF3YWl0IGNhbGxPcGVuQUlXaXRoTWVzc2FnZUhpc3RvcnlPbmx5KG9wZW5haSwgbWVzc2FnZUhpc3RvcnksIG9wZW5BSUNoYXRHUFQzNU1vZGVsKVxuICAgICAgICBjb25zdCBkYXRhU3RhcnRJbmRleCA9IG9wZW5BSURhdGEuaW5kZXhPZigneycpXG4gICAgICAgIGNvbnN0IGRhdGFFbmRJbmRleCA9IG9wZW5BSURhdGEubGFzdEluZGV4T2YoJ30nKVxuICAgICAgICBjb25zdCBkYXRhSlNPTlN0cmluZyA9IG9wZW5BSURhdGEuc2xpY2UoZGF0YVN0YXJ0SW5kZXgsIGRhdGFFbmRJbmRleCArIDEpXG4gICAgICAgIGNvbnN0IGRhdGE6IFVzZXJJbnB1dFRvSlNPTlR5cGUgPSBKU09OLnBhcnNlKGRhdGFKU09OU3RyaW5nKVxuXG4gICAgICAgIHJldHVybiBkYXRhXG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdVbmFibGUgdG8gZ2VuZXJhdGUgSlNPTiBkYXRhIGZyb20gdXNlciBpbnB1dCcsIHsgdXNlcklucHV0LCB1c2VyQ3VycmVudFRpbWUsIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSwgc3RhY2s6IChlIGFzIEVycm9yKS5zdGFjayB9KTtcbiAgICAgICAgcmV0dXJuIHVuZGVmaW5lZDtcbiAgICB9XG59XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNKU09ORGF0YUZyb21Vc2VySW5wdXQgPSBhc3luYyAoXG4gICAgdXNlcklucHV0OiBzdHJpbmcsXG4gICAgcHJpb3JVc2VySW5wdXQ6IHN0cmluZyxcbiAgICBwcmlvckFzc2lzdGFudE91dHB1dDogc3RyaW5nLFxuICAgIHVzZXJDdXJyZW50VGltZTogc3RyaW5nLFxuKSA9PiB7XG4gICAgdHJ5IHtcblxuICAgICAgICBjb25zdCBtZXNzYWdlSGlzdG9yeTogQ2hhdEdQVE1lc3NhZ2VIaXN0b3J5VHlwZSA9IFtdXG5cbiAgICAgICAgY29uc3QgdXNlck1lc3NhZ2UxID0geyByb2xlOiAndXNlcicgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiB1c2VySW5wdXRUb0pTT05FeGFtcGxlSW5wdXQgfVxuICAgICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlMSA9IHsgcm9sZTogJ2Fzc2lzdGFudCcgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiB1c2VySW5wdXRUb0pTT05FeGFtcGxlT3V0cHV0IH1cblxuICAgICAgICBjb25zdCBkYXRhRW5naW5lID0gbmV3IFRlbXBsYXRlRW5naW5lKHVzZXJJbnB1dFRvSlNPTlByb21wdCk7XG4gICAgICAgIGNvbnN0IGRhdGFSZW5kZXJlZCA9IGRhdGFFbmdpbmUucmVuZGVyKHsgdXNlckN1cnJlbnRUaW1lIH0pXG5cbiAgICAgICAgY29uc3QgZGF0YVN5c01lc3NhZ2UgPSB7IHJvbGU6ICdzeXN0ZW0nIGFzIENoYXRHUFRSb2xlVHlwZSwgY29udGVudDogZGF0YVJlbmRlcmVkIH1cbiAgICAgICAgY29uc3QgZGF0YVVzZXJNZXNzYWdlSW5wdXQgPSB7IHJvbGU6ICd1c2VyJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHVzZXJJbnB1dCB9XG5cbiAgICAgICAgY29uc3QgdXNlck1lc3NhZ2UyID0geyByb2xlOiAndXNlcicgYXMgQ2hhdEdQVFJvbGVUeXBlLCBjb250ZW50OiBwcmlvclVzZXJJbnB1dCB9XG4gICAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UyID0geyByb2xlOiAnYXNzaXN0YW50JyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHByaW9yQXNzaXN0YW50T3V0cHV0IH1cblxuICAgICAgICBtZXNzYWdlSGlzdG9yeS5wdXNoKGRhdGFTeXNNZXNzYWdlLCB1c2VyTWVzc2FnZTEsIGFzc2lzdGFudE1lc3NhZ2UxLCB1c2VyTWVzc2FnZTIsIGFzc2lzdGFudE1lc3NhZ2UyLCBkYXRhU3lzTWVzc2FnZSwgZGF0YVVzZXJNZXNzYWdlSW5wdXQpXG5cbiAgICAgICAgY29uc3Qgb3BlbkFJRGF0YSA9IGF3YWl0IGNhbGxPcGVuQUlXaXRoTWVzc2FnZUhpc3RvcnlPbmx5KG9wZW5haSwgbWVzc2FnZUhpc3RvcnksIG9wZW5BSUNoYXRHUFQzNU1vZGVsKVxuICAgICAgICBjb25zdCBkYXRhU3RhcnRJbmRleCA9IG9wZW5BSURhdGEuaW5kZXhPZigneycpXG4gICAgICAgIGNvbnN0IGRhdGFFbmRJbmRleCA9IG9wZW5BSURhdGEubGFzdEluZGV4T2YoJ30nKVxuICAgICAgICBjb25zdCBkYXRhSlNPTlN0cmluZyA9IG9wZW5BSURhdGEuc2xpY2UoZGF0YVN0YXJ0SW5kZXgsIGRhdGFFbmRJbmRleCArIDEpXG4gICAgICAgIGNvbnN0IGRhdGE6IFVzZXJJbnB1dFRvSlNPTlR5cGUgPSBKU09OLnBhcnNlKGRhdGFKU09OU3RyaW5nKVxuXG4gICAgICAgIHJldHVybiBkYXRhXG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdVbmFibGUgdG8gZ2VuZXJhdGUgbWlzc2luZyBmaWVsZHMgSlNPTiBkYXRhIGZyb20gdXNlciBpbnB1dCcsIHsgdXNlcklucHV0LCBwcmlvclVzZXJJbnB1dCwgcHJpb3JBc3Npc3RhbnRPdXRwdXQsIHVzZXJDdXJyZW50VGltZSwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlLCBzdGFjazogKGUgYXMgRXJyb3IpLnN0YWNrIH0pO1xuICAgICAgICByZXR1cm4gdW5kZWZpbmVkO1xuICAgIH1cbn1cblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlV29ya1NjaGVkdWxlID0gYXN5bmMgKFxuICAgIHVzZXJJZDogc3RyaW5nLFxuICAgIHRpbWV6b25lOiBzdHJpbmcsXG4gICAgd2luZG93U3RhcnREYXRlOiBzdHJpbmcsXG4gICAgd2luZG93RW5kRGF0ZTogc3RyaW5nLFxuKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgLy8gbGlzdEV2ZW50c0ZvclVzZXJHaXZlbkRhdGVzXG4gICAgICAgIGNvbnN0IGV2ZW50cyA9IGF3YWl0IGxpc3RFdmVudHNGb3JVc2VyR2l2ZW5EYXRlcyh1c2VySWQsIHdpbmRvd1N0YXJ0RGF0ZSwgd2luZG93RW5kRGF0ZSlcblxuICAgICAgICBsZXQgdXNlclNjaGVkdWxlID0gJydcbiAgICAgICAgY29uc3QgdW5pcURhdGVzID0gXy51bmlxQnkoZXZlbnRzLCAoY3VycikgPT4gKGRheWpzKGN1cnI/LnN0YXJ0RGF0ZT8uc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KCdZWVlZLU1NLUREJykpKVxuXG4gICAgICAgIGZvciAoY29uc3QgdW5pcURhdGUgb2YgdW5pcURhdGVzKSB7XG4gICAgICAgICAgICBjb25zdCBmaWx0ZXJlZEV2ZW50cyA9IGV2ZW50cz8uZmlsdGVyKGEgPT4gKGRheWpzKGE/LnN0YXJ0RGF0ZT8uc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KCdZWVlZLU1NLUREJykgPT09IGRheWpzKHVuaXFEYXRlPy5zdGFydERhdGU/LnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpKSlcblxuICAgICAgICAgICAgaWYgKGZpbHRlcmVkRXZlbnRzPy5sZW5ndGggPiAwKSB7XG5cbiAgICAgICAgICAgICAgICB1c2VyU2NoZWR1bGUgKz0gYCR7ZGF5anModW5pcURhdGU/LnN0YXJ0RGF0ZT8uc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KCdkZGQnKX0gKCR7ZGF5anModW5pcURhdGU/LnN0YXJ0RGF0ZT8uc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KCdZWVlZLU1NLUREJyl9KSBcXG5gXG5cbiAgICAgICAgICAgICAgICBmb3IgKGNvbnN0IGZpbHRlcmVkRXZlbnQgb2YgZmlsdGVyZWRFdmVudHMpIHtcbiAgICAgICAgICAgICAgICAgICAgdXNlclNjaGVkdWxlICs9IGAtICR7ZmlsdGVyZWRFdmVudD8udGl0bGUgfHwgZmlsdGVyZWRFdmVudD8uc3VtbWFyeX06ICR7ZGF5anMoZmlsdGVyZWRFdmVudD8uc3RhcnREYXRlPy5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoJ2g6bW0gYScpfSAtICR7ZGF5anMoZmlsdGVyZWRFdmVudD8uZW5kRGF0ZT8uc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KCdoOm1tIGEnKX0gXFxuYFxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cblxuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIHVzZXJTY2hlZHVsZVxuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgY2hhdEFwaUhlbHBlckxvZ2dlci5lcnJvcignVW5hYmxlIHRvIGdlbmVyYXRlIHdvcmsgc2NoZWR1bGUnLCB7IHVzZXJJZCwgdGltZXpvbmUsIHdpbmRvd1N0YXJ0RGF0ZSwgd2luZG93RW5kRGF0ZSwgZXJyb3I6IChlIGFzIEVycm9yKS5tZXNzYWdlLCBzdGFjazogKGUgYXMgRXJyb3IpLnN0YWNrIH0pO1xuICAgICAgICByZXR1cm4gXCJcIjsgLy8gUmV0dXJuIGVtcHR5IHN0cmluZyBvciBoYW5kbGUgZXJyb3IgYXMgYXBwcm9wcmlhdGVcbiAgICB9XG59XG5cbmV4cG9ydCBjb25zdCBmaW5kQW5FbXB0eVNsb3QgPSBhc3luYyAoXG4gICAgdXNlcklkOiBzdHJpbmcsXG4gICAgdGltZXpvbmU6IHN0cmluZyxcbiAgICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gICAgZXZlbnREdXJhdGlvbjogbnVtYmVyLFxuKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgY29uc3QgdXNlclNjaGVkdWxlID0gYXdhaXQgZ2VuZXJhdGVXb3JrU2NoZWR1bGUodXNlcklkLCB0aW1lem9uZSwgd2luZG93U3RhcnREYXRlLCB3aW5kb3dFbmREYXRlKVxuXG4gICAgICAgIGNvbnN0IGRhdGFFbmdpbmUgPSBuZXcgVGVtcGxhdGVFbmdpbmUoZmluZEFTbG90Rm9yTmV3RXZlbnRUZW1wbGF0ZSk7XG4gICAgICAgIGNvbnN0IGRhdGFSZW5kZXJlZCA9IGRhdGFFbmdpbmUucmVuZGVyKHsgZXZlbnREdXJhdGlvbjogYCR7ZXZlbnREdXJhdGlvbn1gLCB1c2VyU2NoZWR1bGUgfSlcblxuICAgICAgICBjb25zdCBlbXB0eVNsb3RSZXMgPSBhd2FpdCBjYWxsT3BlbkFJKG9wZW5haSwgZmluZEFTbG90Rm9yTmV3RXZlbnRQcm9tcHQsIG9wZW5BSUNoYXRHUFQzNU1vZGVsLCBkYXRhUmVuZGVyZWQsIGZpbmRBU2xvdEZvck5ld0V2ZW50RXhhbXBsZUlucHV0LCBmaW5kQVNsb3RGb3JOZXdFdmVudEV4YW1wbGVPdXRwdXQpXG4gICAgICAgIGNvbnN0IGRhdGFTdGFydEluZGV4ID0gZW1wdHlTbG90UmVzLmluZGV4T2YoJ3snKVxuICAgICAgICBjb25zdCBkYXRhRW5kSW5kZXggPSBlbXB0eVNsb3RSZXMubGFzdEluZGV4T2YoJ30nKVxuICAgICAgICBjb25zdCBkYXRhSlNPTlN0cmluZyA9IGVtcHR5U2xvdFJlcy5zbGljZShkYXRhU3RhcnRJbmRleCwgZGF0YUVuZEluZGV4ICsgMSlcbiAgICAgICAgY29uc3QgZGF0YTogRmluZEFTbG90VHlwZSA9IEpTT04ucGFyc2UoZGF0YUpTT05TdHJpbmcpXG4gICAgICAgIHJldHVybiBkYXRhXG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgICBjaGF0QXBpSGVscGVyTG9nZ2VyLmVycm9yKCdVbmFibGUgdG8gZmluZCBhbiBlbXB0eSBzbG90JywgeyB1c2VySWQsIHRpbWV6b25lLCB3aW5kb3dTdGFydERhdGUsIHdpbmRvd0VuZERhdGUsIGV2ZW50RHVyYXRpb24sIGVycm9yOiAoZSBhcyBFcnJvcikubWVzc2FnZSwgc3RhY2s6IChlIGFzIEVycm9yKS5zdGFjayB9KTtcbiAgICAgICAgcmV0dXJuIHVuZGVmaW5lZDtcbiAgICB9XG59XG5cbnJldHVybiB1bmRlZmluZWQ7XG59XG5cbmV4cG9ydCBjb25zdCBjYWxsT3BlbkFJV2l0aE1lc3NhZ2VIaXN0b3J5T25seSA9IGFzeW5jIChcbiAgICBvcGVuYWlJbnN0YW5jZTogT3BlbkFJLFxuICAgIG1lc3NhZ2VIaXN0b3J5OiBhbnlbXSA9IFtdLFxuICAgIG1vZGVsOiBzdHJpbmcgPSAnZ3B0LTMuNS10dXJibydcbik6IFByb21pc2U8c3RyaW5nPiA9PiB7XG4gICAgdHJ5IHtcbiAgICAgICAgY29uc3QgY29tcGxldGlvbiA9IGF3YWl0IG9wZW5haUluc3RhbmNlLmNoYXQuY29tcGxldGlvbnMuY3JlYXRlKHtcbiAgICAgICAgICAgIG1vZGVsLFxuICAgICAgICAgICAgbWVzc2FnZXM6IG1lc3NhZ2VIaXN0b3J5LFxuICAgICAgICB9KTtcbiAgICAgICAgcmV0dXJuIGNvbXBsZXRpb24uY2hvaWNlc1swXT8ubWVzc2FnZT8uY29udGVudCB8fCAnJztcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICAgIGNoYXRBcGlIZWxwZXJMb2dnZXIuZXJyb3IoJ0Vycm9yIGluIGNhbGxPcGVuQUlXaXRoTWVzc2FnZUhpc3RvcnlPbmx5OicsIChlIGFzIEVycm9yKS5tZXNzYWdlKTtcbiAgICAgICAgdGhyb3cgZTtcbiAgICB9XG5cblxuXG59XG4iXX0=