// import { SESClient } from "@aws-sdk/client-ses";
import OpenAI from "openai"
import { hasuraAdminSecret, hasuraGraphUrl, zoomBaseTokenUrl, zoomBaseUrl, zoomClientId, zoomClientSecret, zoomIVForPass, zoomPassKey, zoomResourceName, zoomSaltForPass, googleClientIdAndroid, googleClientIdAtomicWeb, googleClientIdIos, googleClientIdWeb, googleClientSecretAtomicWeb, googleClientSecretWeb, googleTokenUrl, googleCalendarName, Day, defaultOpenAIAPIKey, openAIChatGPT35Model, openAIChatGPT35LongModel } from "./constants";

import { Dayjs, dayjs, getISODay, setISODay } from "./datetime/date-utils";
import { searchEvents, getEventById as getEventFromLanceDbById, upsertEvents, deleteEventsByIds, searchTrainingEvents, upsertTrainingEvents, deleteTrainingEventsByIds, EventSchema as LanceDbEventSchema, TrainingEventSchema as LanceDbTrainingEventSchema } from '@functions/_utils/lancedb_service';
import DateTimeJSONType, { RelativeTimeChangeFromNowType, RelativeTimeFromNowType } from "./datetime/DateTimeJSONJSONType";
import { BufferTimeType, RecurrenceFrequencyType, RecurrenceRuleType, SendUpdatesType, Time } from "./types/EventType";
import got from "got";
import { CalendarType } from "./types/CalendarType";
import { CalendarIntegrationType } from "./types/CalendarIntegrationType";
import axios from "axios";

import crypto from 'crypto'
import { ZoomMeetingObjectType } from "./types/ZoomMeetingObjectType";
import { GoogleReminderType } from "./types/GoogleReminderType";
import { GoogleResType } from "./types/GoogleResType";
import { GoogleSendUpdatesType, GoogleAttendeeType, GoogleConferenceDataType, GoogleExtendedPropertiesType, GoogleTransparencyType, GoogleVisibilityType, GoogleSourceType, GoogleAttachmentType, GoogleEventType1, ReminderType } from "./types/GoogleTypes";
import { google } from "googleapis";
import { v4 as uuid } from 'uuid'
import { ConferenceType } from "./types/ConferenceType";
import _ from "lodash";
import { EventType } from '@chat/_libs/types/EventType';
import getEventById from "./gql/getEventById";
import { PreAndPostEventReturnType } from "./types/PreAndPostEventReturnType";
import { AttendeeType } from "./types/AttendeeType";
import insertAttendeesForEvent from "./gql/insertAttendeesForEvent";
import findContactViaEmailByUserId from "./gql/findContactViaEmailByUserId";
import { ContactType } from "./types/ContactType";
import getConferenceById from "./gql/getConferenceById";
import deleteConferenceById from "./gql/deleteConferenceById";
import qs from 'qs'
import deleteEventById from "./gql/deleteEventById";
import * as pkg from 'rrule';

import { interopDefault } from 'mlly'
const { RRule } = interopDefault(pkg);
import DayOfWeekType from "./types/DayOfWeekType";
import ByMonthDayType from "./types/ByMonthDayType";
import { getWeekOfMonth } from 'date-fns'
import { MeetingAssistType } from "./types/MeetingAssistType";
import insertMeetingAssistOne from "./gql/insertMeetingAssistOne";
import { UserContactInfoType } from "./types/UserContactInfoType";
import { MeetingAssistAttendeeType } from "./types/MeetingAssistAttendeeType";
import insertMeetingAssistAttendeeOne from "./gql/insertMeetingAssistAttendeeOne";
import listUserContactInfosByUserId from "./gql/listUserContactInfosByUserId";
import { MeetingAssistInviteType } from "./types/MeetingAssistInviteType";
import upsertMeetingAssistInviteGraphql from "./gql/upsertMeetingAssistInviteGraphql";
import { UserType } from "./types/UserType";
import updateNameForUserId from "./gql/updateNameForUserId";
import getContactInfosByIds from "./gql/getContactInfosByIds";
import getContactByNameForUserId from "./gql/getContactByNameForUserId";
import getUserById from "./gql/getUserById";

import { ChatGPTMessageHistoryType } from "./types/ChatGPTTypes";
import { UserOpenAIType } from "./types/UserOpenAIType";
import getTaskById from "./gql/getTaskById";
import { TaskType } from "./types/TaskType";
import { CreateZoomMeetingRequestBodyType } from "./skills/orderCalendar/scheduleMeeting/types";
import { extractQueryUserInputTimeToJSONPrompt, extractQueryUserInputTimeToJSONExampleInput1, extractQueryUserInputTimeToJSONExampleOutput1, extractQueryUserInputTimeToJSONExampleInput2, extractQueryUserInputTimeToJSONExampleOutput2, extractQueryUserInputTimeToJSONExampleInput3, extractQueryUserInputTimeToJSONExampleOutput3, extractQueryUserInputTimeToJSONTemplate, userInputToDateTimeJSONPrompt, userInputToDateTimeJSONExampleInput1, userInputToDateTimeJSONExampleOutput1, userInputToDateTimeJSONExampleInput2, userInputToDateTimeJSONExampleInput3, userInputToDateTimeJSONExampleOutput2, userInputToDateTimeJSONExampleOutput3 } from "./datetime/prompts";
import QueryCalendarExtractedJSONType from "./datetime/QueryCalendarExtractedDateJSONType";
import { getUserPreferences, generateWorkTimesForUser } from "./skills/askCalendar/api-helper";
import { TemplateEngine } from "./template-engine";
import { AssistantMessageType, SkillMessageHistoryType, SystemMessageType } from './types/Messaging/MessagingTypes';
import RequiredFieldsType from "./types/RequiredFieldsType";
import {requestMissingFieldsExampleOutput, requestMissingFieldsPrompt, requestMissingFieldsSystemsExampleInput} from "./prompts/requestMissingData";
import { apiResponeToAssistantResponsePrompt } from "./prompts/apiResponseToAssistantResponse";
import { userInputToJSONExampleInput, userInputToJSONExampleOutput, userInputToJSONPrompt } from "./prompts/userRequestInputToJSON";
import UserInputToJSONType from "./types/UserInputToJSONType";
import { extractNeededAttributesExampleInput, extractNeededAttributesExampleOutput, extractNeededAttributesPrompt } from "./skills/askCalendar/prompts";
import { QueryCalendarExtractedAttributesType } from "./skills/askCalendar/types";
import { findASlotForNewEventExampleInput, findASlotForNewEventExampleOutput, findASlotForNewEventPrompt, findASlotForNewEventTemplate } from './prompts/findASlotForNewEvent';
import { FindASlotType } from "./types/FindASlotType";
import { ChatGPTRoleType } from "@/gpt-meeting/_libs/types/ChatGPTTypes";
import winston from 'winston'; // Added for logger

// const sesClient = new SESClient({ region: "us-east-1" })

// Logger Setup for this api-helper
const chatApiHelperLogger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json(),
    winston.format((info) => {
      info.module = 'chat-api-helper';
      return info;
    })()
  ),
  transports: [
    new winston.transports.Console(),
  ],
});

const openai = new OpenAI({
    apiKey: defaultOpenAIAPIKey,
});

// Helper for resilient Hasura calls using got
const resilientGotPostHasura = async (operationName: string, query: string, variables: Record<string, any>, userId?: string) => {
  const MAX_RETRIES = 3;
  const INITIAL_TIMEOUT_MS = 10000; // 10 seconds for Hasura calls
  let attempt = 0;
  let lastError: any = null;

  const headers: Record<string, string> = {
    'X-Hasura-Admin-Secret': hasuraAdminSecret,
    'Content-Type': 'application/json',
    'X-Hasura-Role': userId ? 'user' : 'admin',
  };
  if (userId) {
    headers['X-Hasura-User-Id'] = userId;
  }

  while (attempt < MAX_RETRIES) {
    try {
      chatApiHelperLogger.info(`Hasura call attempt ${attempt + 1} for ${operationName}`, { userId, operationName });
      const response = await got.post(hasuraGraphUrl, {
        json: { operationName, query, variables },
        headers,
        timeout: { request: INITIAL_TIMEOUT_MS },
        responseType: 'json',
      }).json<{ data?: any; errors?: any[] }>(); // Specify response type for got

      if (response.errors) {
        lastError = new Error(`GraphQL error in ${operationName}: ${JSON.stringify(response.errors)}`);
        // Potentially break here for non-retryable GraphQL errors, e.g. validation
        // For now, we retry all GraphQL errors from Hasura.
        throw lastError;
      }
      chatApiHelperLogger.info(`Hasura call ${operationName} successful on attempt ${attempt + 1}`, { userId, operationName });
      return response.data;
    } catch (error: any) {
      lastError = error;
      chatApiHelperLogger.warn(`Hasura call attempt ${attempt + 1} for ${operationName} failed.`, {
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
      } else if (!error.response && error.code && !['ETIMEDOUT', 'ECONNRESET', 'EADDRINUSE', 'ECONNREFUSED', 'EPIPE', 'ENETUNREACH', 'EAI_AGAIN'].includes(error.code)) {
        // If it's a got error without a response, but not a known retryable network error code, abort.
        chatApiHelperLogger.error(`Non-retryable got error code ${error.code} for ${operationName}. Aborting.`, { userId, operationName });
        break;
      }
    }
    attempt++;
    if (attempt < MAX_RETRIES) {
      const delay = Math.pow(2, attempt - 1) * 1000; // 1s, 2s
      chatApiHelperLogger.info(`Waiting ${delay}ms before Hasura retry ${attempt} for ${operationName}`, { userId, operationName });
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  chatApiHelperLogger.error(`Failed Hasura operation '${operationName}' after ${attempt} attempts.`, { userId, operationName, lastError: lastError?.message });
  throw lastError || new Error(`Failed Hasura operation '${operationName}' after all retries.`);
};


export const searchSingleEventByVectorLanceDb = async (
    userId: string,
    searchVector: number[],
): Promise<LanceDbEventSchema | null> => {
    try {
        const results = await searchEvents(searchVector, 1, `userId = '${userId.replace(/'/g, "''")}'`);
        if (results && results.length > 0) {
            return results[0];
        }
        return null;
    } catch (e) {
        chatApiHelperLogger.error('Error in searchSingleEventByVectorLanceDb', { userId, error: (e as Error).message, stack: (e as Error).stack });
        throw e;
    }
}

export const searchSingleEventByVectorWithDatesLanceDb = async (
    userId: string,
    qVector: number[],
    startDate: string,
    endDate: string,
): Promise<LanceDbEventSchema | null> => {
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
    } catch (e) {
        chatApiHelperLogger.error('Error in searchSingleEventByVectorWithDatesLanceDb', { userId, startDate, endDate, error: (e as Error).message, stack: (e as Error).stack });
        throw e;
    }
}

export const searchMultipleEventsByVectorWithDatesLanceDb = async (
    userId: string,
    qVector: number[],
    startDate: string,
    endDate: string,
    limit: number = 10,
): Promise<LanceDbEventSchema[]> => {
    try {
        if (typeof qVector[0] !== 'number') {
            throw new Error('qVector is not a number array or is empty');
        }
        const filterCondition = `userId = '${userId.replace(/'/g, "''")}' AND start_date >= '${startDate}' AND end_date <= '${endDate}'`;
        const results = await searchEvents(qVector, limit, filterCondition);
        return results || []; // Ensure an array is returned
    } catch (e) {
        chatApiHelperLogger.error('Error in searchMultipleEventsByVectorWithDatesLanceDb', { userId, startDate, endDate, limit, error: (e as Error).message, stack: (e as Error).stack });
        throw e;
    }
}

export const upsertConference = async (
    conference: ConferenceType,
) => {
    try {
        const operationName = 'UpsertConference'
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

        `

        const variables = {
            conference
        }

        // const res: { data: { insert_Conference_one: ConferenceType } } = await got.post(hasuraGraphUrl, {
        //     headers: {
        //         'X-Hasura-Admin-Secret': hasuraAdminSecret,
        //         'X-Hasura-Role': 'admin'
        //     },
        //     json: {
        //         operationName,
        //         query,
        //         variables,
        //     }
        // }).json()
        const responseData = await resilientGotPostHasura(operationName, query, variables) as { insert_Conference_one: ConferenceType };

        chatApiHelperLogger.info('Successfully upserted conference', { conferenceId: responseData?.insert_Conference_one?.id });
        return responseData?.insert_Conference_one;
    } catch (e) {
        chatApiHelperLogger.error('Error in upsertConference', { error: (e as Error).message, conferenceData: conference });
        // Re-throw or handle as per function's contract, for now, let it propagate if resilientGotPostHasura throws
        throw e;
    }
}

export const insertReminders = async (
    reminders: ReminderType[],
) => {
    try {
        // validate
        if (!(reminders?.filter(e => !!(e?.eventId))?.length > 0)) {
            return
        }

        reminders.forEach(r => chatApiHelperLogger.debug('Reminder object inside insertReminders loop', { reminder: r }));

        const operationName = 'InsertReminder'
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
        `
        const variables = {
            reminders
        }

        const responseData = await resilientGotPostHasura(operationName, query, variables) as { insert_Reminder: { returning: ReminderType[] } };

        if (responseData?.insert_Reminder?.returning) {
            chatApiHelperLogger.info('Successfully inserted reminders.', { count: responseData.insert_Reminder.returning.length });
            // responseData.insert_Reminder.returning.forEach(r => chatApiHelperLogger.debug('Inserted reminder details:', { reminder: r }));
        } else {
            chatApiHelperLogger.warn('InsertReminders call to Hasura did not return expected data structure.', { responseData });
        }
        // The function doesn't return anything in its original form, so we maintain that.
    } catch (e) {
        chatApiHelperLogger.error('Error in insertReminders', { error: (e as Error).message, remindersData: reminders });
        // Re-throw or handle as per function's contract
        throw e;
    }
}

export const upsertEvents = async (
    events: EventType[]
) => {
    try {
        if (!(events?.length > 0)) {
            chatApiHelperLogger.info('No events found in upsertEvents, returning early.', { eventCount: events?.length });
            return
        }
        const operationName = 'InsertEvent'
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
        `
        // _.uniqBy(events, 'id').forEach(e => console.log(e?.id, e, 'id, e inside upsertEventsPostPlanner ')) // Original verbose log
        _.uniqBy(events, 'id').forEach(e => chatApiHelperLogger.debug('Event object inside upsertEventsPostPlanner loop (after uniqBy)', { eventId: e?.id, eventSummary: e?.summary }));
        const variables = {
            events: _.uniqBy(events, 'id'),
        }

        // const response: { data: { insert_Event: { affected_rows: number, returning: { id: string }[] } } } = await got.post(hasuraGraphUrl, {
        //     headers: {
        //         'X-Hasura-Admin-Secret': hasuraAdminSecret,
        //         'X-Hasura-Role': 'admin'
        //     },
        //     json: {
        //         operationName,
        //         query,
        //         variables,
        //     }
        // }).json()
        // console.log(response, response?.data?.insert_Event?.affected_rows, ' response after upserting events')
        // response?.data?.insert_Event?.returning?.forEach(e => console.log(e, ' returning  response after upserting events'))
        // return response

        const responseData = await resilientGotPostHasura(operationName, query, variables) as { insert_Event: { affected_rows: number, returning: { id: string }[] } };

        if (responseData?.insert_Event) {
            chatApiHelperLogger.info('Successfully upserted events.', { affected_rows: responseData.insert_Event.affected_rows, returned_ids: responseData.insert_Event.returning?.map(r => r.id) });
        } else {
            chatApiHelperLogger.warn('UpsertEvents call to Hasura did not return expected data structure.', { responseData });
        }
        // Original function returned the whole response object, so we mimic that structure if needed, or just the data part.
        // For now, let's return the 'data' part, assuming consumers expect that.
        // If the full Axios-like response was expected, this would need adjustment.
        // Given the type annotation of the original `response` variable, it seems it expected the `data` property.
        return { data: responseData };

    } catch (e) {
        chatApiHelperLogger.error('Error in upsertEvents', { error: (e as Error).message, eventCount: events.length });
        throw e;
    }
}

// Note: listAllEventWithEventOpenSearch is consolidated into searchMultipleEventsByVectorWithDatesLanceDb

export const putDataInTrainEventIndexInOpenSearch = async (
    id: string,
    vector: number[],
    userId: string,
) => {
    try {
        const client = await getSearchClient()
        const response = await client.index({
            id,
            index: openTrainEventIndex,
            body: { [openTrainEventVectorName]: vector, userId },
            refresh: true
        })
        chatApiHelperLogger.info('Document added to OpenSearch train event index.', { documentId: id, responseBody: response.body });
    } catch (e) {
        chatApiHelperLogger.error('Unable to put data into OpenSearch train event index', { id, userId, error: (e as Error).message, stack: (e as Error).stack });
    }
}

export const getEventVectorFromLanceDb = async (id: string): Promise<number[] | null> => {
    try {
        const event = await getEventFromLanceDbById(id);
        return event?.vector || null;
    } catch (e) {
        chatApiHelperLogger.error(`Error fetching event vector for ID ${id} from LanceDB`, { eventId: id, error: (e as Error).message, stack: (e as Error).stack });
        return null;
    }
}

export const upsertEventToLanceDb = async (
    id: string,
    vector: number[],
    userId: string,
    start_date: string,
    end_date: string,
    title: string, // Assuming title is a good candidate for raw_event_text for now
    // Consider passing the actual text used for vector generation if different
) => {
    try {
        const eventEntry: LanceDbEventSchema = {
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
    } catch (e) {
        chatApiHelperLogger.error(`Error upserting event ${id} to LanceDB`, { eventId: id, userId, error: (e as Error).message, stack: (e as Error).stack });
        throw e;
    }
}

export const deleteEventFromLanceDb = async (id: string): Promise<void> => {
    try {
        await deleteEventsByIds([id]);
        chatApiHelperLogger.info(`Event ${id} deleted from LanceDB.`, { eventId: id });
    } catch (e) {
        chatApiHelperLogger.error(`Error deleting event ${id} from LanceDB`, { eventId: id, error: (e as Error).message, stack: (e as Error).stack });
        throw e;
    }
}

export const deleteTrainingDataFromLanceDb = async (id: string): Promise<void> => {
    try {
        await deleteTrainingEventsByIds([id]);
        chatApiHelperLogger.info(`Training data for ID ${id} deleted from LanceDB.`, { trainingDataId: id });
    } catch (e) {
        chatApiHelperLogger.error(`Error deleting training data for ID ${id} from LanceDB`, { trainingDataId: id, error: (e as Error).message, stack: (e as Error).stack });
        throw e;
    }
}

export const updateTrainingDataInLanceDb = async (
    id: string,
    vector: number[],
    userId: string,
    source_event_text: string, // Required for new upsert logic
) => {
    try {
        const trainingEntry: LanceDbTrainingEventSchema = {
            id,
            userId,
            vector,
            source_event_text,
            created_at: dayjs().toISOString(), // LanceDB upsert will update if exists based on ID
        };
        await upsertTrainingEvents([trainingEntry]);
        chatApiHelperLogger.info(`Training data for ID ${id} updated/upserted in LanceDB.`, { trainingDataId: id, userId });
    } catch (e) {
        chatApiHelperLogger.error(`Error updating training data for ID ${id} in LanceDB`, { trainingDataId: id, userId, error: (e as Error).message, stack: (e as Error).stack });
        throw e;
    }
}

export const searchTrainingDataFromLanceDb = async (
    userId: string,
    searchVector: number[],
): Promise<LanceDbTrainingEventSchema | null> => {
    try {
        const results = await searchTrainingEvents(searchVector, 1, `userId = '${userId.replace(/'/g, "''")}'`);
        if (results && results.length > 0) {
            return results[0];
        }
        return null;
    } catch (e) {
        chatApiHelperLogger.error('Error searching training data in LanceDB', { userId, error: (e as Error).message, stack: (e as Error).stack });
        throw e;
    }
}

export const convertEventTitleToOpenAIVector = async (
    title: string,
) => {
    try {
        const embeddingRequest: OpenAI.Embeddings.EmbeddingCreateParams = {
            model: 'text-embedding-3-small',
            input: title,
        }

        // const res = await openai.embeddings.create(embeddingRequest)
        // console.log(res, ' res inside convertEventTitleToOpenAIVectors')
        // return res?.data?.[0]?.embedding
        return await retry(async (bail, attemptNumber) => {
            try {
                chatApiHelperLogger.info(`Attempt ${attemptNumber} to get embedding for title: "${title.substring(0, 20)}..."`);
                const res = await openai.embeddings.create(embeddingRequest, { timeout: 15000 }); // 15s timeout
                if (!res?.data?.[0]?.embedding) {
                    chatApiHelperLogger.warn(`OpenAI embedding call for title "${title.substring(0,20)}..." returned no embedding data on attempt ${attemptNumber}.`, { response: res });
                    throw new Error("No embedding data returned from OpenAI.");
                }
                chatApiHelperLogger.info(`Successfully got embedding for title "${title.substring(0,20)}..." on attempt ${attemptNumber}.`);
                return res.data[0].embedding;
            } catch (error: any) {
                chatApiHelperLogger.warn(`Attempt ${attemptNumber} for OpenAI embedding for title "${title.substring(0,20)}..." failed.`, {
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
                chatApiHelperLogger.warn(`Retrying OpenAI embedding for title "${title.substring(0,20)}...", attempt ${attemptNumber}. Error: ${error.message}`);
            }
        });
    } catch (e) {
        chatApiHelperLogger.error('Failed to convert event title to OpenAI vector after all retries.', { title: title.substring(0,20), error: (e as Error).message });
        throw e; // Re-throw the final error
    }
}

export const eventSearchBoundary = (
    timezone: string,
    dateJSONBody: DateTimeJSONType,
    currentTime: string,
) => {
    let startDate = ''
    let endDate = ''
    let dateA = ''
    let dateB = ''

    // set dateA
    if (dateJSONBody?.oldDate?.day) {

        dateA = `${dateJSONBody?.oldDate?.year || dayjs().format('YYYY')}-${dateJSONBody?.oldDate?.month || dayjs().format('MM')}-${dateJSONBody?.oldDate?.day || dayjs().tz(timezone).format('DD')}`

    } else if (dateJSONBody?.oldDate?.isoWeekday) {
        const currentISODay = getISODay(dayjs().tz(timezone).toDate())

        const givenISODay = dateJSONBody?.oldDate?.isoWeekday

        // add a week if givenISODay < currentISODay

        if (givenISODay < currentISODay) {
            const parsedPartialEndDate = dayjs(`${dateJSONBody?.oldDate?.year || dayjs().format('YYYY')}-${dateJSONBody?.oldDate?.month || dayjs().format('MM')}-${dateJSONBody?.oldDate?.day || dayjs().tz(timezone).format('DD')}`, 'YYYY-MM-DD')
            dateA = dayjs(setISODay(dayjs(parsedPartialEndDate, 'YYYY-MM-DD').tz(timezone, true).add(1, 'w').toDate(), givenISODay)).format('YYYY-MM-DD')
        } else {
            const parsedPartialEndDate = dayjs(`${dateJSONBody?.oldDate?.year || dayjs().format('YYYY')}-${dateJSONBody?.oldDate?.month || dayjs().format('MM')}-${dateJSONBody?.oldDate?.day || dayjs().tz(timezone).format('DD')}`, 'YYYY-MM-DD')
            dateA = dayjs(setISODay(dayjs(parsedPartialEndDate, 'YYYY-MM-DD').tz(timezone, true).toDate(), givenISODay)).format('YYYY-MM-DD')
        }
    } else if (dateJSONBody?.oldDate?.relativeTimeFromNow?.[0]) {
        if (dateJSONBody?.oldDate?.relativeTimeChangeFromNow === 'add') {
            // loop through all possible values
            let day = 0
            let week = 0
            let month = 0
            let year = 0

            for (const relativeTimeObject of dateJSONBody?.oldDate?.relativeTimeFromNow) {

                if (relativeTimeObject?.unit === 'day') {
                    if (relativeTimeObject?.value > 0) {
                        day += relativeTimeObject?.value
                    }
                } else if (relativeTimeObject?.unit === 'week') {
                    if (relativeTimeObject?.value > 0) {
                        week += relativeTimeObject?.value
                    }
                } else if (relativeTimeObject?.unit === 'month') {
                    if (relativeTimeObject?.value > 0) {
                        month += relativeTimeObject?.value
                    }
                } else if (relativeTimeObject?.unit === 'year') {
                    if (relativeTimeObject?.value > 0) {
                        year += relativeTimeObject?.value
                    }
                }
            }

            dateA = dayjs(currentTime, 'YYYY-MM-DD').tz(timezone, true)
                .add(day, 'd')
                .add(week, 'w')
                .add(month, 'M')
                .add(year, 'y')
                .format('YYYYY-MM-DD')
        } else if (dateJSONBody?.oldDate?.relativeTimeChangeFromNow === 'subtract') {

            let day = 0
            let week = 0
            let month = 0
            let year = 0

            for (const relativeTimeObject of dateJSONBody?.oldDate?.relativeTimeFromNow) {

                if (relativeTimeObject?.unit === 'day') {
                    if (relativeTimeObject?.value > 0) {
                        day += relativeTimeObject?.value
                    }
                } else if (relativeTimeObject?.unit === 'week') {
                    if (relativeTimeObject?.value > 0) {
                        week += relativeTimeObject?.value
                    }
                } else if (relativeTimeObject?.unit === 'month') {
                    if (relativeTimeObject?.value > 0) {
                        month += relativeTimeObject?.value
                    }
                } else if (relativeTimeObject?.unit === 'year') {
                    if (relativeTimeObject?.value > 0) {
                        year += relativeTimeObject?.value
                    }
                }
            }

            dateA = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true)
                .subtract(day, 'd')
                .subtract(week, 'w')
                .subtract(month, 'M')
                .subtract(year, 'y')
                .format()
        }
    }

    // set dateB
    if (dateJSONBody?.day) {
        dateB = `${dateJSONBody?.year || dayjs().format('YYYY')}-${dateJSONBody?.month || dayjs().format('MM')}-${dateJSONBody?.day || dayjs().tz(timezone).format('DD')}`
        // if isoWeekday -> user intent is current week
    } else if (dateJSONBody?.isoWeekday) {
        const currentISODay = getISODay(dayjs().tz(timezone).toDate())

        const givenISODay = dateJSONBody.isoWeekday

        // add a week if givenISODay < currentISODay

        if (givenISODay < currentISODay) {
            const parsedPartialEndDate = dayjs(`${dateJSONBody?.year || dayjs().format('YYYY')}-${dateJSONBody?.month || dayjs().format('MM')}-${dateJSONBody?.day || dayjs().tz(timezone).format('DD')}`, 'YYYY-MM-DD')
            dateB = dayjs(setISODay(dayjs(parsedPartialEndDate, 'YYYY-MM-DD').tz(timezone, true).add(1, 'w').toDate(), givenISODay)).format('YYYY-MM-DD')
        } else {
            const parsedPartialEndDate = dayjs(`${dateJSONBody?.year || dayjs().format('YYYY')}-${dateJSONBody?.month || dayjs().format('MM')}-${dateJSONBody?.day || dayjs().tz(timezone).format('DD')}`, 'YYYY-MM-DD')
            dateB = dayjs(setISODay(dayjs(parsedPartialEndDate, 'YYYY-MM-DD').tz(timezone, true).toDate(), givenISODay)).format('YYYY-MM-DD')
        }
    } else if (dateJSONBody?.relativeTimeFromNow?.[0]) {

        if (dateJSONBody?.relativeTimeChangeFromNow === 'add') {
            // loop through all possible values
            let day = 0
            let week = 0
            let month = 0
            let year = 0

            for (const relativeTimeObject of dateJSONBody?.relativeTimeFromNow) {

                if (relativeTimeObject?.unit === 'day') {
                    if (relativeTimeObject?.value > 0) {
                        day += relativeTimeObject?.value
                    }
                } else if (relativeTimeObject?.unit === 'week') {
                    if (relativeTimeObject?.value > 0) {
                        week += relativeTimeObject?.value
                    }
                } else if (relativeTimeObject?.unit === 'month') {
                    if (relativeTimeObject?.value > 0) {
                        month += relativeTimeObject?.value
                    }
                } else if (relativeTimeObject?.unit === 'year') {
                    if (relativeTimeObject?.value > 0) {
                        year += relativeTimeObject?.value
                    }
                }
            }

            dateB = dayjs(dateA, 'YYYY-MM-DDTHH:mm').tz(timezone, true)
                .add(day, 'd')
                .add(week, 'w')
                .add(month, 'M')
                .add(year, 'y')
                .format()
        } else if (dateJSONBody?.relativeTimeChangeFromNow === 'subtract') {

            let day = 0
            let week = 0
            let month = 0
            let year = 0

            for (const relativeTimeObject of dateJSONBody?.relativeTimeFromNow) {

                if (relativeTimeObject?.unit === 'day') {
                    if (relativeTimeObject?.value > 0) {
                        day += relativeTimeObject?.value
                    }
                } else if (relativeTimeObject?.unit === 'week') {
                    if (relativeTimeObject?.value > 0) {
                        week += relativeTimeObject?.value
                    }
                } else if (relativeTimeObject?.unit === 'month') {
                    if (relativeTimeObject?.value > 0) {
                        month += relativeTimeObject?.value
                    }
                } else if (relativeTimeObject?.unit === 'year') {
                    if (relativeTimeObject?.value > 0) {
                        year += relativeTimeObject?.value
                    }
                }
            }

            dateB = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true)
                .subtract(day, 'd')
                .subtract(week, 'w')
                .subtract(month, 'M')
                .subtract(year, 'y')
                .format()
        }
    }

    if (dateA && dateB) {
        if (dayjs(dateA).isBefore(dayjs(dateB, 'day'))) {
            startDate = dayjs(dateA, 'YYYY-MM-DD').subtract(1, 'd').format('YYYY-MM-DD')
            endDate = dayjs(dateB, 'YYYY-MM-DD').add(1, 'd').format('YYYY-MM-DD')
        } else if (dayjs(dateB).isBefore(dayjs(dateA, 'day'))) {
            startDate = dayjs(dateB, 'YYYY-MM-DD').subtract(1, 'd').format('YYYY-MM-DD')
            endDate = dayjs(dateA, 'YYYY-MM-DD').add(1, 'd').format('YYYY-MM-DD')
        }
    } else if (dateA && !dateB) {
        startDate = dayjs(dateA, 'YYYY-MM-DD').subtract(1, 'd').format('YYYY-MM-DD')
        endDate = dayjs(startDate).tz(timezone, true).add(4, 'w').format('YYYY-MM-DD')
    } else if (dateB && !dateA) {
        startDate = dayjs(dateB, 'YYYY-MM-DD').subtract(1, 'd').format('YYYY-MM-DD')
        endDate = dayjs(startDate).tz(timezone, true).add(4, 'w').format('YYYY-MM-DD')
    }


    return {
        startDate,
        endDate,
    }
}

export const extrapolateDateFromJSONData = (
    currentTime: string,
    timezone: string,
    year: string | null | undefined,
    month: string | null | undefined,
    day: string | null | undefined,
    isoWeekday: number | null | undefined,
    hour: number | null | undefined,
    minute: number | null | undefined,
    time: Time | null | undefined,
    relativeTimeChangeFromNow: RelativeTimeChangeFromNowType | null | undefined,
    relativeTimeFromNow: RelativeTimeFromNowType[] | null | undefined,
) => {

    let meetingStartDate = ''
    let meetingStartDateObject: Dayjs = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true)
    const functionName = 'extrapolateDateFromJSONData';

    chatApiHelperLogger.debug(`[${functionName}] Initial params:`, { currentTime, timezone, year, month, day, isoWeekday, hour, minute, time, relativeTimeChangeFromNow, relativeTimeFromNow });


    if (day) {

        if ((!!hour) && (!!minute)) {

            if (year && month) {
                const yearAndMonthAndDate = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true)
                chatApiHelperLogger.debug(`[${functionName}] Condition: day, hour, minute, year, month`, { yearAndMonthAndDateFormatted: yearAndMonthAndDate.format() });
                
                meetingStartDateObject = meetingStartDateObject
                    .year(yearAndMonthAndDate.year())
                    .month(yearAndMonthAndDate.month())
                    .date(yearAndMonthAndDate.date())
                    .hour(hour)
                    .minute(minute)
                
                chatApiHelperLogger.debug(`[${functionName}] meetingStartDateObject updated (day, hour, minute, year, month):`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            } else {

                const dateOfMonth = dayjs(day, 'DD').tz(timezone, true)
                chatApiHelperLogger.debug(`[${functionName}] Condition: day, hour, minute (no year/month)`, { dateOfMonthFormatted: dateOfMonth.format() });
                meetingStartDateObject = meetingStartDateObject
                    .date(dateOfMonth.date())
                    .hour(hour)
                    .minute(minute)

                chatApiHelperLogger.debug(`[${functionName}] meetingStartDateObject updated (day, hour, minute):`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            }


        } else if (time) {
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}-${day} ${time}`, 'YYYY-MM-DD HH:mm').tz(timezone, true)
                chatApiHelperLogger.debug(`[${functionName}] Condition: day, time, year, month`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            } else {
                meetingStartDateObject = dayjs(`${day} ${time}`, 'DD HH:mm').tz(timezone, true)
                chatApiHelperLogger.debug(`[${functionName}] Condition: day, time (no year/month)`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            }
        } else if (!time && !hour && !minute) { // All day event inferred
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true)
                chatApiHelperLogger.debug(`[${functionName}] Condition: day, year, month (all day)`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            } else {
                meetingStartDateObject = dayjs(day, 'DD').tz(timezone, true)
                chatApiHelperLogger.debug(`[${functionName}] Condition: day (all day, no year/month)`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            }
        }
    } else if (isoWeekday) {
        const givenISODay = isoWeekday
        const currentISODay = getISODay(dayjs(currentTime).tz(timezone, true).toDate())
        chatApiHelperLogger.debug(`[${functionName}] Condition: isoWeekday`, { givenISODay, currentISODay });

        if ((!!hour) && (!!minute)) {
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                    .hour(hour)
                    .minute(minute)
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday, hour, minute, year, month - base:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });

                if (givenISODay < currentISODay) {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))
                    chatApiHelperLogger.debug(`[${functionName}] isoWeekday adjusted (past day this week, add week):`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))
                    chatApiHelperLogger.debug(`[${functionName}] isoWeekday adjusted (future/current day this week):`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                }
            } else {
                meetingStartDateObject = dayjs().tz(timezone, true)
                    .hour(hour)
                    .minute(minute)
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday, hour, minute (no year/month) - base:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });

                if (givenISODay < currentISODay) {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))
                    chatApiHelperLogger.debug(`[${functionName}] isoWeekday adjusted (past day this week, add week):`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))
                    chatApiHelperLogger.debug(`[${functionName}] isoWeekday adjusted (future/current day this week):`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                }
            }
        } else if (time) {
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month} ${time}`, 'YYYY-MM HH:mm').tz(timezone, true)
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday, time, year, month - base:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                if (givenISODay < currentISODay) {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))
                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))
                }
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday, time, year, month - adjusted:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            } else {
                meetingStartDateObject = dayjs(`${time}`, 'HH:mm').tz(timezone, true)
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday, time (no year/month) - base:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                if (givenISODay < currentISODay) {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))
                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))
                }
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday, time (no year/month) - adjusted:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            }
        } else if (!hour && !minute && !time) { // All day for isoWeekday
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday, year, month (all day) - base:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                if (givenISODay < currentISODay) {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))
                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))
                }
            } else {
                meetingStartDateObject = dayjs().tz(timezone, true)
                chatApiHelperLogger.debug(`[${functionName}] isoWeekday (all day, no year/month) - base:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
                if (givenISODay < currentISODay) {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))
                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))
                }
            }
            chatApiHelperLogger.debug(`[${functionName}] isoWeekday (all day) - adjusted:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
        }

    } else if (relativeTimeFromNow?.[0]) {
        let minuteChanged = false
        let hourChanged = false
        let calculatedMinute = 0, calculatedHour = 0, calculatedDay = 0, calculatedWeek = 0, calculatedMonth = 0, calculatedYear = 0;

        for (const relativeTimeObject of relativeTimeFromNow) {
            if (relativeTimeObject?.value > 0) {
                switch (relativeTimeObject.unit) {
                    case 'minute': calculatedMinute += relativeTimeObject.value; minuteChanged = true; break;
                    case 'hour': calculatedHour += relativeTimeObject.value; hourChanged = true; break;
                    case 'day': calculatedDay += relativeTimeObject.value; break;
                    case 'week': calculatedWeek += relativeTimeObject.value; break;
                    case 'month': calculatedMonth += relativeTimeObject.value; break;
                    case 'year': calculatedYear += relativeTimeObject.value; break;
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
                .add(calculatedYear, 'y')
            chatApiHelperLogger.debug(`[${functionName}] relativeTime - add operation:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
        } else if (relativeTimeChangeFromNow === 'subtract') {
            meetingStartDateObject = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true)
                .subtract(calculatedMinute, 'm')
                .subtract(calculatedHour, 'h')
                .subtract(calculatedDay, 'd')
                .subtract(calculatedWeek, 'w')
                .subtract(calculatedMonth, 'M')
                .subtract(calculatedYear, 'y')
            chatApiHelperLogger.debug(`[${functionName}] relativeTime - subtract operation:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
        }

        // Apply explicit hour/minute/time if provided, potentially overriding relative calculation for time part
        if ((!!hour) && (!!minute)) {
            if (year && month) {
                const yearAndMonth = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                meetingStartDateObject = meetingStartDateObject.year(yearAndMonth.year()).month(yearAndMonth.month());
            }
            meetingStartDateObject = meetingStartDateObject.hour(hour).minute(minute);
            chatApiHelperLogger.debug(`[${functionName}] relativeTime with explicit hour/minute override:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format(), year, month });
        } else if (time) {
            const tempTime = dayjs(time, 'HH:mm').tz(timezone, true)
            if (year && month) {
                const yearAndMonth = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                meetingStartDateObject = meetingStartDateObject.year(yearAndMonth.year()).month(yearAndMonth.month());
            }
            meetingStartDateObject = meetingStartDateObject.hour(tempTime.hour()).minute(tempTime.minute());
            chatApiHelperLogger.debug(`[${functionName}] relativeTime with explicit time override:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format(), year, month });
        } else if (!hourChanged && !minuteChanged) { // If no relative minute/hour and no explicit time, apply just year/month if given
             if (year && month) {
                const yearAndMonth = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                meetingStartDateObject = meetingStartDateObject.year(yearAndMonth.year()).month(yearAndMonth.month());
                chatApiHelperLogger.debug(`[${functionName}] relativeTime with explicit year/month (no time parts changed):`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
            }
        }
    }

    chatApiHelperLogger.debug(`[${functionName}] Final meetingStartDateObject:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
    meetingStartDate = (meetingStartDateObject as Dayjs).format()
    return meetingStartDate
}

export const extrapolateStartDateFromJSONData = (
    currentTime: string,
    timezone: string,
    year: string | null | undefined,
    month: string | null | undefined,
    day: string | null | undefined,
    isoWeekday: number | null | undefined,
    hour: number | null | undefined,
    minute: number | null | undefined,
    time: Time | null | undefined,
    relativeTimeChangeFromNow: RelativeTimeChangeFromNowType | null | undefined,
    relativeTimeFromNow: RelativeTimeFromNowType[] | null | undefined,
) => {
    // This function is very similar to extrapolateDateFromJSONData, but sets time to 00:00 if not specified.
    // For brevity, detailed logging for each path is omitted if it's identical to the above, focusing on differences.
    let meetingStartDate = ''
    let meetingStartDateObject: Dayjs = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true)
    const functionName = 'extrapolateStartDateFromJSONData'; // For specific logging if needed

    chatApiHelperLogger.debug(`[${functionName}] Initial params:`, { currentTime, timezone, year, month, day, isoWeekday, hour, minute, time, relativeTimeChangeFromNow, relativeTimeFromNow });

    if (day) {
        if ((!!hour) && (!!minute)) {
             if (year && month) {
                const yearAndMonthAndDate = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true)
                meetingStartDateObject = meetingStartDateObject.year(yearAndMonthAndDate.year()).month(yearAndMonthAndDate.month()).date(yearAndMonthAndDate.date()).hour(hour).minute(minute);
            } else {
                const dateOfMonth = dayjs(day, 'DD').tz(timezone, true)
                meetingStartDateObject = meetingStartDateObject.date(dateOfMonth.date()).hour(hour).minute(minute);
            }
        } else if (time) {
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}-${day} ${time}`, 'YYYY-MM-DD HH:mm').tz(timezone, true);
            } else {
                meetingStartDateObject = dayjs(`${day} ${time}`, 'DD HH:mm').tz(timezone, true);
            }
        } else if (!time && !hour && !minute) { // All day event, start at 00:00
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true).hour(0).minute(0);
            } else {
                meetingStartDateObject = dayjs(day, 'DD').tz(timezone, true).hour(0).minute(0);
            }
             chatApiHelperLogger.debug(`[${functionName}] Day specified, no time - setting to 00:00`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
        }
    } else if (isoWeekday) {
        const givenISODay = isoWeekday;
        const currentISODay = getISODay(dayjs(currentTime).tz(timezone, true).toDate());
        let baseDateObj: Dayjs;

        if ((!!hour) && (!!minute)) {
            baseDateObj = year && month ? dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true) : dayjs().tz(timezone, true);
            baseDateObj = baseDateObj.hour(hour).minute(minute);
        } else if (time) {
            baseDateObj = year && month ? dayjs(`${year}-${month} ${time}`, 'YYYY-MM HH:mm').tz(timezone, true) : dayjs(time, 'HH:mm').tz(timezone, true);
        } else { // All day for isoWeekday, start at 00:00
            baseDateObj = year && month ? dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true) : dayjs().tz(timezone, true);
            baseDateObj = baseDateObj.hour(0).minute(0);
            chatApiHelperLogger.debug(`[${functionName}] ISO Weekday specified, no time - setting to 00:00 for base`, { baseDateObjFormatted: baseDateObj.format() });
        }

        meetingStartDateObject = givenISODay < currentISODay ? dayjs(setISODay(baseDateObj.add(1, 'w').toDate(), givenISODay)) : dayjs(setISODay(baseDateObj.toDate(), givenISODay));

    } else if (relativeTimeFromNow?.[0]) {
        let minuteChanged = false, hourChanged = false;
        let calculatedMinute = 0, calculatedHour = 0, calculatedDay = 0, calculatedWeek = 0, calculatedMonth = 0, calculatedYear = 0;

        for (const relativeTimeObject of relativeTimeFromNow) {
             if (relativeTimeObject?.value > 0) {
                switch (relativeTimeObject.unit) {
                    case 'minute': calculatedMinute += relativeTimeObject.value; minuteChanged = true; break;
                    case 'hour': calculatedHour += relativeTimeObject.value; hourChanged = true; break;
                    case 'day': calculatedDay += relativeTimeObject.value; break;
                    case 'week': calculatedWeek += relativeTimeObject.value; break;
                    case 'month': calculatedMonth += relativeTimeObject.value; break;
                    case 'year': calculatedYear += relativeTimeObject.value; break;
                }
            }
        }

        const baseCurrentTime = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true); // Ensure we use full current time for subtractions

        if ((relativeTimeChangeFromNow === 'add') || (relativeTimeChangeFromNow === null)) {
            meetingStartDateObject = baseCurrentTime
                .add(calculatedMinute, 'm').add(calculatedHour, 'h')
                .add(calculatedDay, 'd').add(calculatedWeek, 'w')
                .add(calculatedMonth, 'M').add(calculatedYear, 'y');
        } else if (relativeTimeChangeFromNow === 'subtract') {
            meetingStartDateObject = baseCurrentTime
                .subtract(calculatedMinute, 'm').subtract(calculatedHour, 'h')
                .subtract(calculatedDay, 'd').subtract(calculatedWeek, 'w')
                .subtract(calculatedMonth, 'M').subtract(calculatedYear, 'y');
        }

        if ((!!hour) && (!!minute)) {
            if (year && month) meetingStartDateObject = meetingStartDateObject.year(dayjs(`${year}-${month}`, 'YYYY-MM').year()).month(dayjs(`${year}-${month}`, 'YYYY-MM').month());
            meetingStartDateObject = meetingStartDateObject.hour(hour).minute(minute);
        } else if (time) {
            const tempTime = dayjs(time, 'HH:mm').tz(timezone, true);
            if (year && month) meetingStartDateObject = meetingStartDateObject.year(dayjs(`${year}-${month}`, 'YYYY-MM').year()).month(dayjs(`${year}-${month}`, 'YYYY-MM').month());
            meetingStartDateObject = meetingStartDateObject.hour(tempTime.hour()).minute(tempTime.minute());
        } else if (!hourChanged && !minuteChanged) { // No relative time parts, no explicit time parts -> set to 00:00
            if (year && month) meetingStartDateObject = meetingStartDateObject.year(dayjs(`${year}-${month}`, 'YYYY-MM').year()).month(dayjs(`${year}-${month}`, 'YYYY-MM').month());
            meetingStartDateObject = meetingStartDateObject.hour(0).minute(0);
            chatApiHelperLogger.debug(`[${functionName}] Relative day/week/month/year, no time parts - setting to 00:00`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
        }
    }

    chatApiHelperLogger.debug(`[${functionName}] Final meetingStartDateObject:`, { meetingStartDateObjectFormatted: meetingStartDateObject.format() });
    meetingStartDate = (meetingStartDateObject as Dayjs).format()
    return meetingStartDate
}

export const extrapolateEndDateFromJSONData = (
    currentTime: string,
    timezone: string,
    year: string | null | undefined,
    month: string | null | undefined,
    day: string | null | undefined,
    isoWeekday: number | null | undefined,
    hour: number | null | undefined,
    minute: number | null | undefined,
    time: Time | null | undefined,
    relativeTimeChangeFromNow: RelativeTimeChangeFromNowType | null | undefined,
    relativeTimeFromNow: RelativeTimeFromNowType[] | null | undefined,
) => {
    // This function is very similar to extrapolateDateFromJSONData, but sets time to 23:59 if not specified.
    let meetingEndDate = ''
    let meetingEndDateObject: Dayjs = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true)
    const functionName = 'extrapolateEndDateFromJSONData';

    chatApiHelperLogger.debug(`[${functionName}] Initial params:`, { currentTime, timezone, year, month, day, isoWeekday, hour, minute, time, relativeTimeChangeFromNow, relativeTimeFromNow });

    if (day) {
        if ((!!hour) && (!!minute)) {
            if (year && month) {
                const yearAndMonthAndDate = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true);
                meetingEndDateObject = meetingEndDateObject.year(yearAndMonthAndDate.year()).month(yearAndMonthAndDate.month()).date(yearAndMonthAndDate.date()).hour(hour).minute(minute);
            } else {
                const dateOfMonth = dayjs(day, 'DD').tz(timezone, true);
                meetingEndDateObject = meetingEndDateObject.date(dateOfMonth.date()).hour(hour).minute(minute);
            }
        } else if (time) {
             if (year && month) {
                meetingEndDateObject = dayjs(`${year}-${month}-${day} ${time}`, 'YYYY-MM-DD HH:mm').tz(timezone, true);
            } else {
                meetingEndDateObject = dayjs(`${day} ${time}`, 'DD HH:mm').tz(timezone, true);
            }
        } else if (!time && !hour && !minute) { // All day event, end at 23:59
            if (year && month) {
                meetingEndDateObject = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true).hour(23).minute(59);
            } else {
                meetingEndDateObject = dayjs(day, 'DD').tz(timezone, true).hour(23).minute(59);
            }
            chatApiHelperLogger.debug(`[${functionName}] Day specified, no time - setting to 23:59`, { meetingEndDateObjectFormatted: meetingEndDateObject.format() });
        }
    } else if (isoWeekday) {
        const givenISODay = isoWeekday;
        const currentISODay = getISODay(dayjs(currentTime).tz(timezone, true).toDate());
        let baseDateObj: Dayjs;

        if ((!!hour) && (!!minute)) {
            baseDateObj = year && month ? dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true) : dayjs().tz(timezone, true);
            baseDateObj = baseDateObj.hour(hour).minute(minute);
        } else if (time) {
            baseDateObj = year && month ? dayjs(`${year}-${month} ${time}`, 'YYYY-MM HH:mm').tz(timezone, true) : dayjs(time, 'HH:mm').tz(timezone, true);
        } else { // All day for isoWeekday, end at 23:59
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
                    case 'minute': calculatedMinute += relativeTimeObject.value; minuteChanged = true; break;
                    case 'hour': calculatedHour += relativeTimeObject.value; hourChanged = true; break;
                    case 'day': calculatedDay += relativeTimeObject.value; break;
                    case 'week': calculatedWeek += relativeTimeObject.value; break;
                    case 'month': calculatedMonth += relativeTimeObject.value; break;
                    case 'year': calculatedYear += relativeTimeObject.value; break;
                }
            }
        }
        chatApiHelperLogger.debug(`[${functionName}] Applying relativeTimeFromNow adjustments:`, { calculatedMinute, calculatedHour, calculatedDay, calculatedWeek, calculatedMonth, calculatedYear, relativeTimeChangeFromNow });

        if ((relativeTimeChangeFromNow === 'add') || (relativeTimeChangeFromNow === null)) {
            meetingEndDateObject = meetingEndDateObject
                .add(calculatedMinute, 'm').add(calculatedHour, 'h')
                .add(calculatedDay, 'd').add(calculatedWeek, 'w')
                .add(calculatedMonth, 'M').add(calculatedYear, 'y');
        } else if (relativeTimeChangeFromNow === 'subtract') {
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
            if (year && month) meetingEndDateObject = meetingEndDateObject.year(dayjs(`${year}-${month}`, 'YYYY-MM').year()).month(dayjs(`${year}-${month}`, 'YYYY-MM').month());
            meetingEndDateObject = meetingEndDateObject.hour(hour).minute(minute);
             chatApiHelperLogger.debug(`[${functionName}] Relative time applied, then explicit hour/minute:`, { meetingEndDateObjectFormatted: meetingEndDateObject.format() });
        } else if (time) { // Explicit time given
            const tempTime = dayjs(time, 'HH:mm').tz(timezone, true);
            if (year && month) meetingEndDateObject = meetingEndDateObject.year(dayjs(`${year}-${month}`, 'YYYY-MM').year()).month(dayjs(`${year}-${month}`, 'YYYY-MM').month());
            meetingEndDateObject = meetingEndDateObject.hour(tempTime.hour()).minute(tempTime.minute());
            chatApiHelperLogger.debug(`[${functionName}] Relative time applied, then explicit time:`, { meetingEndDateObjectFormatted: meetingEndDateObject.format() });
        } else if (!hourChanged && !minuteChanged) { // No relative minute/hour adjustments, and no explicit time/hour/minute
            // This implies it might be an "all-day" type of relative adjustment (e.g., "next week")
            // So, set time to end of day.
            if (year && month) meetingEndDateObject = meetingEndDateObject.year(dayjs(`${year}-${month}`, 'YYYY-MM').year()).month(dayjs(`${year}-${month}`, 'YYYY-MM').month());
            meetingEndDateObject = meetingEndDateObject.hour(23).minute(59);
            chatApiHelperLogger.debug(`[${functionName}] Relative day/week/etc applied (no time parts), setting to 23:59:`, { meetingEndDateObjectFormatted: meetingEndDateObject.format() });
        }
    }

    chatApiHelperLogger.debug(`[${functionName}] Final meetingEndDateObject:`, { meetingEndDateObjectFormatted: meetingEndDateObject.format() });
    meetingEndDate = (meetingEndDateObject as Dayjs).format()
    return meetingEndDate
}

export const getGlobalCalendar = async (
    userId: string,
) => {
    const operationName = 'getGlobalCalendar'; // Defined operationName for logging and Hasura call
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
        //     hasuraGraphUrl,
        //     {
        //         headers: {
        //             'X-Hasura-Admin-Secret': hasuraAdminSecret,
        //             'Content-Type': 'application/json',
        //             'X-Hasura-Role': 'admin'
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

        // Using resilientGotPostHasura for the Hasura call
        // Assuming 'admin' role for this query as per original direct got call.
        // If user-specific role is needed, the resilientGotPostHasura call would need the userId passed as the 4th param.
        // For getGlobalCalendar, it seems like an admin or system-level query for a user's global calendar.
        const responseData = await resilientGotPostHasura(operationName, query, { userId } /*, userId (if user role needed) */) as { Calendar: CalendarType[] };

        if (responseData && responseData.Calendar && responseData.Calendar.length > 0) {
            chatApiHelperLogger.info(`${operationName} successful for user ${userId}. Calendar ID: ${responseData.Calendar[0].id}`);
            return responseData.Calendar[0];
        } else {
            chatApiHelperLogger.info(`${operationName}: No global primary calendar found for user ${userId}.`);
            return undefined; // Or null, depending on desired contract for "not found"
        }
    } catch (e) {
        chatApiHelperLogger.error(`Error in ${operationName} for user ${userId}`, { error: (e as Error).message });
        // resilientGotPostHasura will throw on failure after retries, so this catch block will handle that.
        throw e;
    }
}

export const getCalendarIntegrationByResource = async (
    userId: string,
    resource: string,
) => {
    try {
        const operationName = 'getCalendarIntegrationByResource'
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
    `
        const variables = {
            userId,
            resource,
        }

        const res: { data: { Calendar_Integration: CalendarIntegrationType[] } } = await got.post(
            hasuraGraphUrl,
            {
                json: {
                    operationName,
                    query,
                    variables,
                },
                headers: {
                    'X-Hasura-Admin-Secret': hasuraAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Hasura-Role': 'admin'
                },
            },
        ).json()

        console.log(res, ' res inside getCalendarIntegration')
        if (res?.data?.Calendar_Integration?.length > 0) {
            return res?.data?.Calendar_Integration?.[0]
        }
        const responseData = await resilientGotPostHasura(operationName, query, variables, userId) as { Calendar_Integration: CalendarIntegrationType[] };
        chatApiHelperLogger.info(`getCalendarIntegrationByResource response for user ${userId}, resource ${resource}`, { dataLength: responseData?.Calendar_Integration?.length });
        return responseData?.Calendar_Integration?.[0];
    } catch (e) {
        chatApiHelperLogger.error('Error in getCalendarIntegrationByResource', { userId, resource, error: (e as Error).message });
        throw e;
    }
}

export const getCalendarIntegrationByName = async (
    userId: string,
    name: string,
) => {
    try {
        const operationName = 'getCalendarIntegrationByName'
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
        `
        const variables = {
            userId,
            name,
        }

        const res: { data: { Calendar_Integration: CalendarIntegrationType[] } } = await got.post(
            hasuraGraphUrl,
            {
                json: {
                    operationName,
                    query,
                    variables,
                },
                headers: {
                    'X-Hasura-Admin-Secret': hasuraAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Hasura-Role': 'admin'
                },
            },
        ).json()

        console.log(res, ' res inside getCalendarIntegration')
        if (res?.data?.Calendar_Integration?.length > 0) {
            return res?.data?.Calendar_Integration?.[0]
        }
        const responseData = await resilientGotPostHasura(operationName, query, variables, userId) as { Calendar_Integration: CalendarIntegrationType[] };
        chatApiHelperLogger.info(`getCalendarIntegrationByName response for user ${userId}, name ${name}`, { dataLength: responseData?.Calendar_Integration?.length });
        return responseData?.Calendar_Integration?.[0];
    } catch (e) {
        chatApiHelperLogger.error('Error in getCalendarIntegrationByName', { userId, name, error: (e as Error).message });
        throw e;
    }
}

export const getZoomIntegration = async (
    userId: string,
) => {
    try {
        const { id, token, expiresAt, refreshToken } = await getCalendarIntegrationByResource(userId, zoomResourceName)

        const decryptedTokens = decryptZoomTokens(token, refreshToken)

        return {
            id,
            expiresAt,
            ...decryptedTokens,
        }

    } catch (e) {
        chatApiHelperLogger.error('Unable to get zoom integration', { userId, error: (e as Error).message, stack: (e as Error).stack });
        // Original function implicitly returns undefined here, so we'll maintain that.
        // Depending on desired strictness, could rethrow e.
    }
}

export const decryptZoomTokens = (
    encryptedToken: string,
    encryptedRefreshToken?: string,
) => {
    const ivBuffer = Buffer.from(zoomIVForPass, 'base64')
    const saltBuffer = Buffer.from(zoomSaltForPass, 'base64')

    const key = crypto.pbkdf2Sync(zoomPassKey as string, saltBuffer, 10000, 32, 'sha256')

    const decipherToken = crypto.createDecipheriv('aes-256-cbc', key, ivBuffer)
    let decryptedToken = decipherToken.update(encryptedToken, 'base64', 'utf8')
    decryptedToken += decipherToken.final('utf8')

    if (encryptedRefreshToken) {
        const decipherRefreshToken = crypto.createDecipheriv('aes-256-cbc', key, ivBuffer)
        let decryptedRefreshToken = decipherRefreshToken.update(encryptedRefreshToken, 'base64', 'utf8')
        decryptedRefreshToken += decipherRefreshToken.final('utf8')

        return {
            token: decryptedToken,
            refreshToken: decryptedRefreshToken,
        }
    }

    return {
        token: decryptedToken,
    }

}

export const encryptZoomTokens = (
    token: string,
    refreshToken?: string,
) => {
    const ivBuffer = Buffer.from(zoomIVForPass, 'base64')
    const saltBuffer = Buffer.from(zoomSaltForPass, 'base64')

    const key = crypto.pbkdf2Sync(zoomPassKey as string, saltBuffer, 10000, 32, 'sha256')
    const cipherToken = crypto.createCipheriv('aes-256-cbc', key, ivBuffer)
    let encryptedToken = cipherToken.update(token, 'utf8', 'base64');
    encryptedToken += cipherToken.final('base64')

    let encryptedRefreshToken = ''

    if (refreshToken) {
        const cipherRefreshToken = crypto.createCipheriv('aes-256-cbc', key, ivBuffer)
        encryptedRefreshToken = cipherRefreshToken.update(refreshToken, 'utf8', 'base64');
        encryptedRefreshToken += cipherRefreshToken.final('base64')
    }

    if (encryptedRefreshToken) {
        return {
            encryptedToken,
            encryptedRefreshToken
        }
    } else {
        return { encryptedToken }
    }
}

export const updateCalendarIntegration = async (
    id: string,
    token?: string,
    expiresIn?: number,
    enabled?: boolean,
) => {
    try {
        const operationName = 'updateCalendarIntegration'
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
      `
        const variables = {
            id,
            token,
            expiresAt: dayjs().add(expiresIn, 'seconds').toISOString(),
            enabled,
        }

        const res = await got.post(
            hasuraGraphUrl,
            {
                json: {
                    operationName,
                    query,
                    variables,
                },
                headers: {
                    'X-Hasura-Admin-Secret': hasuraAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Hasura-Role': 'admin'
                },
            },
        ).json()
        console.log(res, ' res inside updateCalendarIntegration')
        await resilientGotPostHasura(operationName, query, variables); // Assuming admin role for updates
        chatApiHelperLogger.info(`Successfully updated calendar integration ${id}.`);
    } catch (e) {
        chatApiHelperLogger.error('Error in updateCalendarIntegration', { id, token, expiresIn, enabled, error: (e as Error).message });
        throw e;
    }
}

export const updateZoomIntegration = async (
    id: string,
    accessToken: string,
    expiresIn: number,
) => {
    try {

        const { encryptedToken } = encryptZoomTokens(accessToken)
        await updateCalendarIntegration(id, encryptedToken, expiresIn)
    } catch (e) {
        chatApiHelperLogger.error('Unable to update zoom integration', { integrationId: id, error: (e as Error).message, stack: (e as Error).stack });
        // Original function implicitly returns undefined/void and does not rethrow.
    }
}

export const refreshZoomToken = async (
    refreshToken: string,
): Promise<{
    access_token: string,
    token_type: 'bearer',
    refresh_token: string,
    expires_in: number,
    scope: string
}> => {
    const operationName = 'refreshZoomToken';
    const MAX_RETRIES = 3;
    const INITIAL_TIMEOUT_MS = 10000; // 10 seconds
    let attempt = 0;
    let lastError: any = null;

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
        } catch (error: any) {
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
                } else if (error.code && !['ECONNABORTED', 'ETIMEDOUT', 'ECONNRESET', 'EADDRINUSE', 'ECONNREFUSED', 'EPIPE', 'ENETUNREACH', 'EAI_AGAIN'].includes(error.code)) {
                    break; // Non-retryable network or config error
                }
            } else { // Non-axios error
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
}

// Helper for resilient Zoom API calls using got
const resilientGotZoomApi = async (method: 'get' | 'post' | 'patch' | 'delete', endpoint: string, zoomToken: string, jsonData?: any, params?: any) => {
    const MAX_RETRIES = 3;
    const INITIAL_TIMEOUT_MS = 15000; // 15 seconds for Zoom API calls
    let attempt = 0;
    let lastError: any = null;

    const url = `${zoomBaseUrl}${endpoint}`;

    while (attempt < MAX_RETRIES) {
        try {
            chatApiHelperLogger.info(`Zoom API call attempt ${attempt + 1}: ${method.toUpperCase()} ${endpoint}`);
            const options: any = {
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
        } catch (error: any) {
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
                    if (attempt > 0) break;
                }
            } else if (!error.response && error.code && !['ETIMEDOUT', 'ECONNRESET', 'EADDRINUSE', 'ECONNREFUSED', 'EPIPE', 'ENETUNREACH', 'EAI_AGAIN'].includes(error.code)) {
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


export const getZoomAPIToken = async (
    userId: string,
) => {
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

    } catch (e) {
        chatApiHelperLogger.error(`[${operationName}] Failed to get/refresh Zoom API token.`, { userId, integrationIdOnError: integrationId, error: (e as Error).message, stack: (e as Error).stack });
        if (integrationId) { // Only attempt to disable if we had an ID
            try {
                chatApiHelperLogger.info(`[${operationName}] Attempting to disable Zoom integration due to error.`, { integrationId });
                await updateCalendarIntegration(integrationId, undefined, undefined, false);
                chatApiHelperLogger.info(`[${operationName}] Successfully disabled Zoom integration.`, { integrationId });
            } catch (disableError) {
                chatApiHelperLogger.error(`[${operationName}] Failed to disable Zoom integration after an error.`, { integrationId, disableError: (disableError as Error).message, stack: (disableError as Error).stack });
            }
        }
        // Original code implicitly returns undefined on error / attempts to disable.
        // We'll maintain this behavior by not re-throwing here, but callers should be aware it might return undefined.
        return undefined;
    }
}

export const deleteRemindersWithIds = async (
    eventIds: string[],
    userId: string,
) => {
    try {
        // validate
        if (!(eventIds?.filter(e => !!e)?.length > 0)) {
            return
        }
        eventIds.forEach(e => console.log(e, ' eventIds inside deleteRemindersWithIds'))
        const operationName = 'deleteRemindersWithIds'
        const query = `
      mutation deleteRemindersWithIds($userId: uuid!, $eventIds: [String!]!) {
        delete_Reminder(where: {userId: {_eq: $userId}, eventId: {_in: $eventIds}}) {
          affected_rows
        }
      }    
    `

        const variables = {
            userId,
            eventIds,
        }

        const response = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        // }).json()
        // console.log(response, ' this is response in deleteRemindersWithIds')
        await resilientGotPostHasura(operationName, query, variables, userId);
        chatApiHelperLogger.info(`Successfully deleted reminders for eventIds: ${eventIds.join(', ')} for user ${userId}.`);

    } catch (e) {
        chatApiHelperLogger.error('Error in deleteRemindersWithIds', { userId, eventIds, error: (e as Error).message });
        throw e;
    }
}

export const updateZoomMeeting = async (
    zoomToken: string,
    meetingId: number,
    startDate?: string,
    timezone?: string,
    agenda?: string,
    duration?: number,
    contactName?: string,
    contactEmail?: string,
    meetingInvitees?: string[],
    privateMeeting?: boolean,
    recur?: RecurrenceRuleType,
) => {
    try {
        //valdiate
        if (startDate && dayjs().isAfter(dayjs(startDate))) {
            chatApiHelperLogger.warn('[updateZoomMeeting] Start time is in the past.', { meetingId, startDate });
            throw new Error('Start time is in the past for updateZoomMeeting.');
        }

        let settings: any = {}

        if (privateMeeting) {
            settings = { ...settings, private_meeting: privateMeeting }
        }

        if ((contactName?.length > 0) && (contactEmail?.length > 0)) {
            settings = {
                contact_name: contactName,
                contact_email: contactEmail,
            }
        }

        if (meetingInvitees?.length > 0) {
            settings = { ...settings, meeting_invitees: meetingInvitees }
        }

        let reqBody: any = {}

        if (Object.keys(settings)?.length > 0) {
            reqBody.settings = settings
        }

        if (startDate && timezone) {
            reqBody.start_time = dayjs(startDate?.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss')
            reqBody.timezone = timezone
        }

        if (agenda) {
            reqBody.agenda = agenda
        }

        if (duration) {
            reqBody.duration = duration
        }

        if (recur?.frequency && recur?.interval && (recur?.endDate || recur?.occurrence)) {

            if (recur?.frequency === 'weekly') {
                reqBody.recurrence.type = 2
            } else if (recur?.frequency === 'monthly') {
                reqBody.recurrence.type = 3
            } else if (recur?.frequency === 'daily') {
                reqBody.recurrence.type = 1
            }

            if (reqBody.recurrence.type == 3) {

                if (recur?.byMonthDay?.[0]) {

                    reqBody.recurrence.monthly_day = recur?.byMonthDay?.[0]
                }
            }

            if (recur?.endDate) {
                reqBody.recurrence.end_date_time = dayjs(recur.endDate).tz(timezone).utc().format()
            } else if (recur?.occurrence) {
                reqBody.recurrence.end_times = recur.occurrence
            }

            reqBody.recurrence.repeat_interval = recur.interval

            if (recur?.byMonthDay?.length > 0) {
                // create rrule and go by each date
                const rule = new RRule({
                    freq: getRruleFreq(recur?.frequency),
                    interval: recur?.interval,
                    until: dayjs(recur?.endDate).toDate(),
                    byweekday: recur?.byWeekDay?.map(i => getRRuleByWeekDay(i)),
                    count: recur?.occurrence,
                    bymonthday: recur?.byMonthDay,
                })

                const ruleDates = rule.all()

                const nonUniqueWeekMonth = []
                const nonUniqueDayMonth = []
                const nonUniqueDayWeekMonth = []
                for (const ruleDate of ruleDates) {
                    const weekMonth = getWeekOfMonth(ruleDate)
                    nonUniqueWeekMonth.push(weekMonth)
                    const dayMonth = dayjs(ruleDate).date()
                    nonUniqueDayMonth.push(dayMonth)
                    const dayWeekMonth = getISODay(dayjs(ruleDate).toDate())
                    nonUniqueDayWeekMonth.push(dayWeekMonth)
                }

                const uniqueDayWeekMonth = _.uniq(nonUniqueDayWeekMonth)
                const uniqueDayMonth = _.uniq(nonUniqueDayMonth)
                const uniqueWeekMonth = _.uniq(nonUniqueWeekMonth)

                if (uniqueDayWeekMonth?.length > 0) {
                    reqBody.recurrence.monthly_week_day = uniqueDayWeekMonth?.[0]
                }

                if (uniqueDayMonth?.length > 0) {
                    reqBody.recurrence.monthly_day = uniqueDayMonth?.[0]
                }

                if (uniqueWeekMonth?.length > 0) {
                    reqBody.recurrence.monthly_week = uniqueWeekMonth?.[0]
                }
            } else if (recur?.byWeekDay?.length > 0) {
                reqBody.recurrence.weekly_days = getNumberInString(recur.byWeekDay)
            }
        }

        await resilientGotZoomApi('patch', `/meetings/${meetingId}`, zoomToken, reqBody);
        chatApiHelperLogger.info(`Successfully patched Zoom meeting ${meetingId}.`);
    } catch (e) {
        chatApiHelperLogger.error('Error in updateZoomMeeting', { meetingId, error: (e as Error).message });
        throw e; // Re-throw to allow caller to handle
    }
}

export const getNumberForWeekDay = (
    day: DayOfWeekType
) => {

    switch (day) {
        case 'MO':
            return '1'
        case 'TU':
            return '2'
        case 'WE':
            return '3'
        case 'TH':
            return '4'
        case 'FR':
            return '5'
        case 'SA':
            return '6'
        case 'SU':
            return '7'
    }
}

export const getNumberInString = (
    byWeekDays: DayOfWeekType[]
) => {

    let numberInString = ''

    for (const byWeekDay of byWeekDays) {
        numberInString += `${getNumberForWeekDay(byWeekDay)}, `
    }

    return numberInString
}
export const createZoomMeeting = async (
    zoomToken: string,
    startDate: string,
    timezone: string,
    agenda: string,
    duration: number,
    contactName?: string,
    contactEmail?: string,
    meetingInvitees?: string[],
    recur?: RecurrenceRuleType,
) => {
    try {
        //valdiate
        if (dayjs().isAfter(dayjs(startDate))) {
            chatApiHelperLogger.warn('[createZoomMeeting] Start time is in the past.', { startDate, agenda });
            throw new Error('Start time is in the past for createZoomMeeting.');
        }

        chatApiHelperLogger.info('[createZoomMeeting] Called.', { startDate, timezone, agenda, duration });

        let settings: any = {}

        if ((contactName?.length > 0) && (contactEmail?.length > 0)) {
            settings = {
                contact_name: contactName,
                contact_email: contactEmail,
            }
        }

        if (meetingInvitees?.length > 0) {
            settings = { ...settings, meeting_invitees: meetingInvitees?.map(m => ({ email: m })) }
        }

        let reqBody: CreateZoomMeetingRequestBodyType = {}

        if (Object.keys(settings)?.length > 0) {
            reqBody.settings = settings
        }

        reqBody = {
            ...reqBody,
            start_time: dayjs(startDate?.slice(0, 19)).tz(timezone, true).utc().format(),
            // timezone,
            agenda,
            duration,
        }

        if (recur?.frequency && recur?.interval && (recur?.endDate || recur?.occurrence)) {

            if (recur?.frequency === 'weekly') {
                reqBody.recurrence.type = 2
            } else if (recur?.frequency === 'monthly') {
                reqBody.recurrence.type = 3
            } else if (recur?.frequency === 'daily') {
                reqBody.recurrence.type = 1
            }

            if (reqBody.recurrence.type == 3) {

                if (recur?.byMonthDay?.[0]) {

                    reqBody.recurrence.monthly_day = recur?.byMonthDay?.[0]
                }
            }

            if (recur?.endDate) {
                reqBody.recurrence.end_date_time = dayjs(recur.endDate).tz(timezone).utc().format()
            } else if (recur?.occurrence) {
                reqBody.recurrence.end_times = recur.occurrence
            }

            reqBody.recurrence.repeat_interval = recur.interval

            if (recur?.byMonthDay?.length > 0) {
                // create rrule and go by each date
                const rule = new RRule({
                    freq: getRruleFreq(recur?.frequency),
                    interval: recur?.interval,
                    until: dayjs(recur?.endDate).toDate(),
                    byweekday: recur?.byWeekDay?.map(i => getRRuleByWeekDay(i)),
                    count: recur?.occurrence,
                    bymonthday: recur?.byMonthDay,
                })

                const ruleDates = rule.all()

                const nonUniqueWeekMonth = []
                const nonUniqueDayMonth = []
                const nonUniqueDayWeekMonth = []
                for (const ruleDate of ruleDates) {
                    const weekMonth = getWeekOfMonth(ruleDate)
                    nonUniqueWeekMonth.push(weekMonth)
                    const dayMonth = dayjs(ruleDate).date()
                    nonUniqueDayMonth.push(dayMonth)
                    const dayWeekMonth = getISODay(dayjs(ruleDate).toDate())
                    nonUniqueDayWeekMonth.push(dayWeekMonth)
                }

                const uniqueDayWeekMonth = _.uniq(nonUniqueDayWeekMonth)
                const uniqueDayMonth = _.uniq(nonUniqueDayMonth)
                const uniqueWeekMonth = _.uniq(nonUniqueWeekMonth)

                if (uniqueDayWeekMonth?.length > 0) {
                    reqBody.recurrence.monthly_week_day = uniqueDayWeekMonth?.[0]
                }

                if (uniqueDayMonth?.length > 0) {
                    reqBody.recurrence.monthly_day = uniqueDayMonth?.[0]
                }

                if (uniqueWeekMonth?.length > 0) {
                    reqBody.recurrence.monthly_week = uniqueWeekMonth?.[0]
                }
            } else if (recur?.byWeekDay?.length > 0) {
                reqBody.recurrence.weekly_days = getNumberInString(recur.byWeekDay)
            }
        }

        chatApiHelperLogger.debug('Zoom createMeeting request body:', { reqBody });

        const responseData = await resilientGotZoomApi('post', '/users/me/meetings', zoomToken, reqBody) as ZoomMeetingObjectType;

        chatApiHelperLogger.info('Successfully created Zoom meeting.', { meetingId: responseData?.id, topic: responseData?.topic });
        return responseData;
    } catch (e) {
        chatApiHelperLogger.error('Error in createZoomMeeting', { agenda, error: (e as Error).message });
        throw e;
    }
}

export const refreshGoogleToken = async (
    refreshToken: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web'
): Promise<{
    access_token: string,
    expires_in: number, // add seconds to now
    scope: string,
    token_type: string
}> => {
    const operationName = 'refreshGoogleToken';
    chatApiHelperLogger.info(`${operationName} called`, { clientType, refreshTokenSubstring: refreshToken?.substring(0,10) });

    let clientId: string;
    let clientSecret: string | undefined;

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

    const formPayload: Record<string, string> = {
        grant_type: 'refresh_token',
        refresh_token: refreshToken,
        client_id: clientId,
    };
    if (clientSecret) {
        formPayload.client_secret = clientSecret;
    }

    try {
        return await resilientGotGoogleAuth(googleTokenUrl, formPayload, operationName, clientType);
    } catch (e) {
        chatApiHelperLogger.error(`Failed ${operationName} for clientType ${clientType} after all retries.`, { error: (e as Error).message });
        // The original function would log and implicitly return undefined.
        // To maintain a clearer contract, we'll rethrow. Callers should handle this.
        throw e;
    }
}


// Helper for resilient Google Auth calls using got
const resilientGotGoogleAuth = async (
    url: string,
    formPayload: Record<string, string>,
    operationName: string,
    clientType: string
) => {
    const MAX_RETRIES = 3;
    const INITIAL_TIMEOUT_MS = 10000; // 10 seconds for Google Auth calls
    let attempt = 0;
    let lastError: any = null;

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
            }).json<{ access_token: string, expires_in: number, scope: string, token_type: string }>();

            chatApiHelperLogger.info(`Google Auth call ${operationName} (${clientType}) successful on attempt ${attempt + 1}`);
            return response;
        } catch (error: any) {
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
            } else if (!error.response && error.code && !['ETIMEDOUT', 'ECONNRESET', 'EADDRINUSE', 'ECONNREFUSED', 'EPIPE', 'ENETUNREACH', 'EAI_AGAIN'].includes(error.code)) {
                chatApiHelperLogger.error(`Non-retryable got error code ${error.code} for ${operationName} (${clientType}). Aborting.`, { operationName, clientType });
                break;
            }
        }
        attempt++;
        if (attempt < MAX_RETRIES) {
            const delay = Math.pow(2, attempt -1) * 1000; // Exponential backoff: 1s, 2s
            chatApiHelperLogger.info(`Waiting ${delay}ms before Google Auth retry ${attempt + 1} for ${operationName} (${clientType})`);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
    chatApiHelperLogger.error(`Failed Google Auth operation '${operationName}' (${clientType}) after ${attempt} attempts.`, { operationName, clientType, lastError: lastError?.message });
    throw lastError || new Error(`Failed Google Auth operation '${operationName}' (${clientType}) after all retries.`);
};


export const getGoogleAPIToken = async (
    userId: string,
    name: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web',
) => {
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

    } catch (e) {
        chatApiHelperLogger.error(`[${operationName}] Failed to get/refresh Google API token.`, { userId, name, clientType, integrationIdOnError: integrationId, error: (e as Error).message, stack: (e as Error).stack });

        if (integrationId) {
            try {
                chatApiHelperLogger.info(`[${operationName}] Attempting to disable calendar integration due to error.`, { integrationId });
                await updateCalendarIntegration(integrationId, undefined, undefined, false);
                chatApiHelperLogger.info(`[${operationName}] Successfully disabled calendar integration.`, { integrationId });
            } catch (disableError) {
                chatApiHelperLogger.error(`[${operationName}] Failed to disable calendar integration after an error.`, { integrationId, disableError: (disableError as Error).message, stack: (disableError as Error).stack });
            }
        }
        throw e; // Re-throw original error to ensure failure is propagated
    }
}

export const createGoogleEvent = async (
    userId: string,
    calendarId: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web',
    generatedId?: string,
    endDateTime?: string, // either endDateTime or endDate - all day vs specific period
    startDateTime?: string,
    conferenceDataVersion?: 0 | 1,
    maxAttendees?: number,
    sendUpdates?: GoogleSendUpdatesType,
    anyoneCanAddSelf?: boolean,
    attendees?: GoogleAttendeeType[],
    conferenceData?: GoogleConferenceDataType,
    summary?: string,
    description?: string,
    timezone?: string, // required for recurrence
    startDate?: string, // all day
    endDate?: string, // all day
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
    colorId?: string,
): Promise<GoogleResType> => { // Added Promise<GoogleResType> return type hint
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
          })

          // create request body (logic remains the same)
          let data: any = {}

          if (endDateTime && timezone && !endDate) {
              const end = { dateTime: endDateTime, timeZone: timezone }
              data.end = end
          }
          if (endDate && timezone && !endDateTime) {
              const end = { date: dayjs(endDate.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD'), timeZone: timezone }
              data.end = end
          }
          if (startDate && timezone && !startDateTime) {
              const start = { date: dayjs(startDate.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD'), timeZone: timezone }
              data.start = start
          }
          if (startDateTime && timezone && !startDate) {
              const start = { dateTime: startDateTime, timeZone: timezone }
              data.start = start
          }
          if (originalStartDate && timezone && !originalStartDateTime) {
              const originalStartTime = { date: dayjs(originalStartDate?.slice(0, 19)).format('YYYY-MM-DD'), timeZone: timezone }
              data.originalStartTime = originalStartTime
          }
          if (originalStartDateTime && timezone && !originalStartDate) {
              const originalStartTime = { dateTime: originalStartDateTime, timeZone: timezone }
              data.originalStartTime = originalStartTime
          }
          if (anyoneCanAddSelf) data = { ...data, anyoneCanAddSelf }
          if (attendees?.[0]?.email) data = { ...data, attendees }
          if (conferenceData?.createRequest) {
              data = { ...data, conferenceData: { createRequest: { conferenceSolutionKey: { type: conferenceData.type }, requestId: conferenceData?.requestId || uuid() } } }
          } else if (conferenceData?.entryPoints?.[0]) {
              data = { ...data, conferenceData: { conferenceSolution: { iconUri: conferenceData?.iconUri, key: { type: conferenceData?.type }, name: conferenceData?.name }, entryPoints: conferenceData?.entryPoints } }
          }
          if (description?.length > 0) data = { ...data, description }
          if (extendedProperties?.private || extendedProperties?.shared) data = { ...data, extendedProperties }
          if (guestsCanInviteOthers) data = { ...data, guestsCanInviteOthers }
          if (guestsCanModify) data = { ...data, guestsCanModify }
          if (guestsCanSeeOtherGuests) data = { ...data, guestsCanSeeOtherGuests }
          if (locked) data = { ...data, locked }
          if (privateCopy) data = { ...data, privateCopy }
          if (recurrence?.[0]) data = { ...data, recurrence }
          if ((reminders?.overrides?.length > 0) || (reminders?.useDefault)) data = { ...data, reminders }
          if (source?.title || source?.url) data = { ...data, source }
          if (attachments?.[0]?.fileId) data = { ...data, attachments }
          if (eventType?.length > 0) data = { ...data, eventType }
          if (status) data = { ...data, status }
          if (transparency) data = { ...data, transparency }
          if (visibility) data = { ...data, visibility }
          if (iCalUID?.length > 0) data = { ...data, iCalUID }
          if (attendeesOmitted) data = { ...data, attendeesOmitted }
          if (hangoutLink?.length > 0) data = { ...data, hangoutLink }
          if (summary?.length > 0) data = { ...data, summary }
          if (location?.length > 0) data = { ...data, location }
          if (colorId) data.colorId = colorId

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

      } catch (e: any) {
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
    },
    {
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
  } catch (e: any) {
    chatApiHelperLogger.error(`Failed to create Google event for user ${userId} after all retries or due to non-retryable error.`, {
      summary, error: e.message, code: e.code, errors: e.errors, details: e.response?.data || e.errors || e
    });
    throw e;
  }
}

export const patchGoogleEvent = async (
    userId: string,
    calendarId: string,
    eventId: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web',
    endDateTime?: string, // either endDateTime or endDate - all day vs specific period
    startDateTime?: string,
    conferenceDataVersion?: 0 | 1,
    maxAttendees?: number,
    sendUpdates?: GoogleSendUpdatesType,
    anyoneCanAddSelf?: boolean,
    attendees?: GoogleAttendeeType[],
    conferenceData?: GoogleConferenceDataType,
    summary?: string,
    description?: string,
    timezone?: string, // required for recurrence
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
    colorId?: string,
) => {
    try {
        // get token =
        const token = await getGoogleAPIToken(userId, googleCalendarName, clientType)
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
        })

        let variables: any = {
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
        }


        // create request body
        let requestBody: any = {}


        if (endDate && timezone && !endDateTime) {
            const end = {
                date: dayjs(endDateTime.slice(0, 19)).tz(timezone, true)
                    .format('YYYY-MM-DD'),
                timezone,
            }
            requestBody.end = end
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
            }
            requestBody.end = end
        }

        if (startDate && timezone && !startDateTime) { // All-day event start
            chatApiHelperLogger.debug('[patchGoogleEvent] Setting start date (all-day)', { eventId, startDate, timezone });
            const start = {
                date: dayjs(startDate.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD'), // Ensure correct formatting for date-only
                timezone,
            }
            requestBody.start = start
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
            }
            requestBody.start = start
        }

        if (originalStartDate && timezone && !originalStartDateTime) {
            const originalStartTime = {
                date: dayjs(originalStartDate.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD'),
                timezone,
            }
            requestBody.originalStartTime = originalStartTime
        }

        if (originalStartDateTime && timezone && !originalStartDate) {
            const originalStartTime = {
                dateTime: originalStartDateTime,
                timezone,
            }
            requestBody.originalStartTime = originalStartTime
        }

        if (anyoneCanAddSelf) {
            // data = { ...data, anyoneCanAddSelf }
            requestBody.anyoneCanAddSelf = anyoneCanAddSelf
        }

        if (attendees?.[0]?.email) {
            // data = { ...data, attendees }
            requestBody.attendees = attendees
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
            }
        } else if (conferenceData?.entryPoints?.[0]) {
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
            }
        }

        if (description?.length > 0) {
            // data = { ...data, description }
            requestBody.description = description
        }

        if (extendedProperties?.private || extendedProperties?.shared) {
            // data = { ...data, extendedProperties }
            requestBody.extendedProperties = extendedProperties
        }

        if (guestsCanInviteOthers) {
            // data = { ...data, guestsCanInviteOthers }
            requestBody.guestsCanInviteOthers = guestsCanInviteOthers
        }

        if (guestsCanModify) {
            // data = { ...data, guestsCanModify }
            requestBody.guestsCanModify = guestsCanModify
        }

        if (guestsCanSeeOtherGuests) {
            // data = { ...data, guestsCanSeeOtherGuests }
            requestBody.guestsCanSeeOtherGuests = guestsCanSeeOtherGuests
        }

        if (locked) {
            // data = { ...data, locked }
            requestBody.locked = locked
        }

        if (privateCopy) {
            // data = { ...data, privateCopy }
            requestBody.privateCopy = privateCopy
        }

        if (recurrence?.[0]) {
            // data = { ...data, recurrence }
            requestBody.recurrence = recurrence
        }

        if (reminders) {
            // data = { ...data, reminders }
            requestBody.reminders = reminders
        }

        if (source?.title || source?.url) {
            // data = { ...data, source }
            requestBody.source = source
        }

        if (attachments?.[0]?.fileId) {
            // data = { ...data, attachments }
            requestBody.attachments = attachments
        }

        if (eventType?.length > 0) {
            // data = { ...data, eventType }
            requestBody.eventType = eventType
        }

        if (status) {
            // data = { ...data, status }
            requestBody.status = status
        }

        if (transparency) {
            // data = { ...data, transparency }
            requestBody.transparency = transparency
        }

        if (visibility) {
            // data = { ...data, visibility }
            requestBody.visibility = visibility
        }

        if (iCalUID?.length > 0) {
            // data = { ...data, iCalUID }
            requestBody.iCalUID = iCalUID
        }

        if (attendeesOmitted) {
            // data = { ...data, attendeesOmitted }
            requestBody.attendeesOmitted = attendeesOmitted
        }

        if (hangoutLink?.length > 0) {
            // data = { ...data, hangoutLink }
            requestBody.hangoutLink = hangoutLink
        }

        if (summary?.length > 0) {
            // data = { ...data, summary }
            requestBody.summary = summary
        }

        if (location?.length > 0) {
            // data = { ...data, location }
            requestBody.location = location
        }

        if (colorId) {
            requestBody.colorId = colorId
        }

        variables.requestBody = requestBody
        // Do the magic
        chatApiHelperLogger.debug(`Google Calendar patch request for event ${eventId}`, { requestBody: variables.requestBody });

        return await retry(async (bail, attemptNumber) => {
            try {
                const res = await googleCalendar.events.patch(variables, { timeout: 20000 }); // 20 second timeout
                chatApiHelperLogger.info(`Google Calendar event ${eventId} patched successfully on attempt ${attemptNumber} for user ${userId}.`);
                // Original function didn't return anything, so we maintain that.
                return; // Explicitly return void for success if that's the contract
            } catch (e: any) {
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
                throw e;
            }
        }, {
            retries: 3,
            factor: 2,
            minTimeout: 1000,
            maxTimeout: 10000,
            onRetry: (error, attemptNumber) => {
                chatApiHelperLogger.warn(`Retrying Google event patch for event ${eventId}, user ${userId}, attempt ${attemptNumber}. Error: ${error.message}`, {
                    operation_name: `${operation_name}_onRetry`,
                    attempt: attemptNumber,
                    error_code: error.code,
                });
            },
        });
    } catch (e) {
        chatApiHelperLogger.error(`Failed to patch Google event ${eventId} for user ${userId} after all retries.`, { error: (e as Error).message });
        throw e;
    }
}

export const getEventFromPrimaryKey = async (eventId: string): Promise<EventType> => {
    try {
        const operationName = 'getEventFromPrimaryKey'
        const query = getEventById
        const res: { data: { Event_by_pk: EventType } } = await got.post(
            hasuraGraphUrl,
            {
                headers: {
                    'X-Hasura-Admin-Secret': hasuraAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Hasura-Role': 'admin'
                },
                json: {
                    operationName,
                    query,
                    variables: {
                        eventId,
                    },
                },
            },
        // ).json()
        // console.log(res, ' res from getEventFromPrimaryKey')
        // return res?.data?.Event_by_pk
        const responseData = await resilientGotPostHasura(operationName, query, { eventId }) as { Event_by_pk: EventType }; // Assuming admin role or appropriate user context if eventId implies user
        return responseData?.Event_by_pk;
    } catch (e) {
        chatApiHelperLogger.error('Error in getEventFromPrimaryKey', { eventId, error: (e as Error).message });
        throw e;
    }
}

export const getTaskGivenId = async (id: string): Promise<TaskType> => {
    try {
        const operationName = 'GetTaskById'
        const query = getTaskById
        const res: { data: { Task_by_pk: TaskType } } = await got.post(
            hasuraGraphUrl,
            {
                headers: {
                    'X-Hasura-Admin-Secret': hasuraAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Hasura-Role': 'admin'
                },
                json: {
                    operationName,
                    query,
                    variables: {
                        id,
                    },
                },
            },
        // ).json()
        // console.log(res, ' res from getTaskGivenId')
        // return res?.data?.Task_by_pk
        const responseData = await resilientGotPostHasura(operationName, query, { id }) as { Task_by_pk: TaskType }; // Assuming admin role or appropriate context
        return responseData?.Task_by_pk;
    } catch (e) {
        chatApiHelperLogger.error('Error in getTaskGivenId', { id, error: (e as Error).message });
        throw e;
    }
}


export const createPreAndPostEventsFromEvent = (event: EventType, bufferTime: BufferTimeType): PreAndPostEventReturnType => {

    const eventId = uuid()
    const eventId1 = uuid()

    const preEventId = event?.preEventId || `${eventId}#${event?.calendarId}`
    const postEventId = event?.postEventId || `${eventId1}#${event?.calendarId}`

    // await upsertEvents([beforeEvent, afterEvent])

    let valuesToReturn: any = {}
    valuesToReturn.newEvent = event

    if (bufferTime?.afterEvent) {
        // const formattedZoneAfterEventEndDate = formatInTimeZone(addMinutes(zonedTimeToUtc(event.endDate.slice(0, 19), event.timezone), previousEvent?.timeBlocking?.afterEvent), event.timezone, "yyyy-MM-dd'T'HH:mm:ssXXX")
        // const formattedZoneAfterEventStartDate = formatInTimeZone(zonedTimeToUtc(event.endDate.slice(0, 19), event.timezone), event.timezone, "yyyy-MM-dd'T'HH:mm:ssXXX")

        const formattedZoneAfterEventEndDate = dayjs(event.endDate.slice(0, 19)).tz(event.timezone, true).add(bufferTime?.afterEvent, 'm').format()
        const formattedZoneAfterEventStartDate = dayjs(event.endDate.slice(0, 19)).tz(event.timezone, true).format()

        const afterEvent: EventType = {
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
        }
        valuesToReturn.afterEvent = afterEvent
        valuesToReturn.newEvent = {
            ...valuesToReturn.newEvent,
            postEventId,
            timeBlocking: {
                ...valuesToReturn?.newEvent?.timeBlocking,
                afterEvent: bufferTime?.afterEvent,
            }
        }
    }

    if (bufferTime?.beforeEvent) {
        const formattedZoneBeforeEventStartDate = dayjs(event.startDate.slice(0, 19)).tz(event.timezone, true).subtract(bufferTime?.beforeEvent, 'm').format()
        const formattedZoneBeforeEventEndDate = dayjs(event.startDate.slice(0, 19)).tz(event.timezone, true).format()

        const beforeEvent: EventType = {
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
        }
        valuesToReturn.beforeEvent = beforeEvent
        valuesToReturn.newEvent = {
            ...valuesToReturn.newEvent,
            preEventId,
            timeBlocking: {
                ...valuesToReturn?.newEvent?.timeBlocking,
                beforeEvent: bufferTime?.beforeEvent,
            }
        }
    }

    return valuesToReturn

}

export const upsertAttendeesforEvent = async (
    attendees: AttendeeType[]
) => {
    try {
        // validate
        if (!(attendees?.filter(a => !!(a?.eventId))?.length > 0)) {
            return
        }

        const operationName = 'InsertAttendeesForEvent'
        const query = insertAttendeesForEvent
        const variables = {
            attendees,
        }

        const response: { data: { insert_Attendee: { affected_rows: number, returning: AttendeeType[] } } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        // }).json()
        // console.log(response?.data?.insert_Attendee?.returning, ' this is response in insertAttendees')
        // response?.data?.insert_Attendee?.returning.forEach(r => console.log(r, ' response in insertAttendees'))
        const responseData = await resilientGotPostHasura(operationName, query, variables) as { insert_Attendee: { returning: AttendeeType[] } };
        if (responseData?.insert_Attendee?.returning) {
            chatApiHelperLogger.info('Successfully upserted attendees.', { count: responseData.insert_Attendee.returning.length });
        } else {
            chatApiHelperLogger.warn('UpsertAttendeesforEvent call to Hasura did not return expected data structure.', { responseData });
        }
        // No return value in original
    } catch (e) {
        chatApiHelperLogger.error('Error in upsertAttendeesforEvent', { error: (e as Error).message });
        throw e;
    }
}

export const deleteAttendeesWithIds = async (
    eventIds: string[],
    userId: string,
) => {
    try {
        // validate
        if (!(eventIds?.filter(e => !!e)?.length > 0)) {
            return
        }
        chatApiHelperLogger.debug('Event IDs for attendee deletion:', { eventIds, userId, operationName: 'DeleteAttendeesWithEventIds' });
        const operationName = 'DeleteAttendeesWithEventIds'
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

    `

        const variables = {
            userId,
            eventIds,
        }

        const response = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        // }).json()
        // console.log(response, ' this is response in deleteAttendeesWithIds')
        await resilientGotPostHasura(operationName, query, variables, userId);
        chatApiHelperLogger.info(`Successfully deleted attendees for eventIds: ${eventIds.join(', ')} for user ${userId}.`);
    } catch (e) {
        chatApiHelperLogger.error('Error in deleteAttendeesWithIds', { userId, eventIds, error: (e as Error).message });
        throw e;
    }
}

export const findContactByEmailGivenUserId = async (
    userId: string,
    email: string,
): Promise<ContactType> => {
    try {
        // validate
        if (!userId) {
            throw new Error('no userId provided')
        }

        if (!email) {
            chatApiHelperLogger.warn('No email provided to findContactByEmailGivenUserId', { userId });
            return; // Or throw new Error('Email is required'); depending on desired strictness
        }

        const operationName = 'FindContactByEmailGivenUserId'
        const query = findContactViaEmailByUserId

        const variables = {
            userId,
            emailFilter: {
                value: email,
            }
        }

        const response: { data: { Contact: ContactType[] } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        // }).json()
        // console.log(response?.data?.Contact?.[0], ' this is response in findContactByEmailGivenUserId')
        // return response?.data?.Contact?.[0]
        const responseData = await resilientGotPostHasura(operationName, query, variables, userId) as { Contact: ContactType[] };
        return responseData?.Contact?.[0];
    } catch (e) {
        chatApiHelperLogger.error('Error in findContactByEmailGivenUserId', { userId, email, error: (e as Error).message });
        throw e;
    }
}

export const getConferenceGivenId = async (
    id: string,
): Promise<ConferenceType> => {
    try {
        // validate
        if (!id) {
            throw new Error('no conference id provided')
        }



        const operationName = 'GetConferenceById'
        const query = getConferenceById

        const variables = {
            id,
        }

        const response: { data: { Conference_by_pk: ConferenceType } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        // }).json()
        // console.log(response?.data?.Conference_by_pk, ' this is response in getConferenceGivenId')
        // return response?.data?.Conference_by_pk
        const responseData = await resilientGotPostHasura(operationName, query, variables) as { Conference_by_pk: ConferenceType };
        return responseData?.Conference_by_pk;
    } catch (e) {
        chatApiHelperLogger.error('Error in getConferenceGivenId', { id, error: (e as Error).message });
        throw e;
    }
}


export const deleteConferenceGivenId = async (
    id: string,
) => {
    try {
        // validate
        if (!id) {
            throw new Error('no conference id provided')
        }



        const operationName = 'DeleteConferenceById'
        const query = deleteConferenceById

        const variables = {
            id,
        }

        const response: { data: { delete_Conference_by_pk: ConferenceType } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        // }).json()
        // console.log(response?.data?.delete_Conference_by_pk, ' this is response in deleteConferenceGivenId')
        // return response?.data?.delete_Conference_by_pk
        const responseData = await resilientGotPostHasura(operationName, query, variables) as { delete_Conference_by_pk: ConferenceType };
        return responseData?.delete_Conference_by_pk;
    } catch (e) {
        chatApiHelperLogger.error('Error in deleteConferenceGivenId', { id, error: (e as Error).message });
        throw e;
    }
}

export const deleteZoomMeeting = async (
    zoomToken: string,
    meetingId: number,
    scheduleForReminder?: boolean,
    cancelMeetingReminder?: boolean,
) => {
    try {
        let params: any = {}
        if (
            cancelMeetingReminder
            || scheduleForReminder
        ) {

            if (cancelMeetingReminder) {
                params = { cancel_meeting_reminder: cancelMeetingReminder }
            }

            if (scheduleForReminder) {
                params = { ...params, schedule_for_reminder: scheduleForReminder }
            }
        }

        const stringifiedObject = Object.keys(params)?.length > 0 ? qs.stringify(params) : ''

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
    } catch (e) {
        chatApiHelperLogger.error('Error in deleteZoomMeeting', { meetingId, error: (e as Error).message });
        throw e;
    }
}


export const deleteEventGivenId = async (
    id: string,
) => {
    try {
        // validate
        if (!id) {
            throw new Error('no event id provided')
        }



        const operationName = 'DeleteEventById'
        const query = deleteEventById

        const variables = {
            id,
        }

        const response: { data: { delete_Event_by_pk: EventType } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        // }).json()
        // console.log(response?.data?.delete_Event_by_pk, ' this is response in deleteEventGivenId')
        // return response?.data?.delete_Event_by_pk
        const responseData = await resilientGotPostHasura(operationName, query, variables) as { delete_Event_by_pk: EventType };
        return responseData?.delete_Event_by_pk;
    } catch (e) {
        chatApiHelperLogger.error('Error in deleteEventGivenId', { id, error: (e as Error).message });
        throw e;
    }
}


export const deleteGoogleEvent = async (
    userId: string,
    calendarId: string,
    googleEventId: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web',
    sendUpdates: SendUpdatesType = 'all',
) => {
    try {

        // get token =
        const token = await getGoogleAPIToken(userId, googleCalendarName, clientType)


        const googleCalendar = google.calendar({
            version: 'v3',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        })

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
      } catch (e: any) {
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
    }, {
      retries: 3,
      factor: 2,
      minTimeout: 1000,
      maxTimeout: 10000,
      onRetry: (error, attemptNumber) => {
        chatApiHelperLogger.warn(`Retrying Google event delete for event ${googleEventId}, user ${userId}, attempt ${attemptNumber}. Error: ${error.message}`, {
            operation_name: `${operation_name}_onRetry`,
            attempt: attemptNumber,
            error_code: error.code,
        });
      },
    });
  } catch (e) {
    chatApiHelperLogger.error(`Failed to delete Google event ${googleEventId} for user ${userId} after all retries.`, { error: (e as Error).message });
    throw e;
  }
}

export const getRruleFreq = (
    freq: RecurrenceFrequencyType
) => {
    switch (freq) {
        case 'daily':
            return RRule.DAILY
        case 'weekly':
            return RRule.WEEKLY
        case 'monthly':
            return RRule.MONTHLY
        case 'yearly':
            return RRule.YEARLY
    }
}

export const getRRuleDay = (value: Day | undefined) => {
    switch (value) {
        case Day.MO:
            return RRule.MO
        case Day.TU:
            return RRule.TU
        case Day.WE:
            return RRule.WE
        case Day.TH:
            return RRule.TH
        case Day.FR:
            return RRule.FR
        case Day.SA:
            return RRule.SA
        case Day.SU:
            return RRule.SU
        default:
            return undefined
    }
}

export const getRRuleByWeekDay = (value: DayOfWeekType | undefined) => {
    switch (value) {
        case 'MO':
            return RRule.MO
        case 'TU':
            return RRule.TU
        case 'WE':
            return RRule.WE
        case 'TH':
            return RRule.TH
        case 'FR':
            return RRule.FR
        case 'SA':
            return RRule.SA
        case 'SU':
            return RRule.SU
        default:
            return undefined
    }
}

export const createRRuleString = (
    frequency: RecurrenceFrequencyType,
    interval: number,
    byWeekDay?: DayOfWeekType[] | null,
    count?: number | null,
    recurringEndDate?: string,
    byMonthDay?: ByMonthDayType[],
) => {
    if ((!(recurringEndDate?.length > 0) && !count) || !frequency || !interval) {
        chatApiHelperLogger.warn('Cannot create RRule string: recurringEndDate/count or frequency or interval missing.', { hasRecurringEndDate: !!recurringEndDate, count, frequency, interval });
        return undefined
    }

    const rule = new RRule({
        freq: getRruleFreq(frequency),
        interval,
        until: dayjs(recurringEndDate).toDate(),
        byweekday: byWeekDay?.map(i => getRRuleByWeekDay(i)),
        count,
        bymonthday: byMonthDay,
    })

    return [rule.toString()]
}

export const upsertMeetingAssistOne = async (
    meetingAssist: MeetingAssistType,
) => {
    try {
        // validate
        if (!meetingAssist) {
            throw new Error('no meeting assist provided')
        }



        const operationName = 'InsertMeetingAssist'
        const query = insertMeetingAssistOne

        const variables = {
            meetingAssist,
        }

        const response: { data: { insert_Meeting_Assist_one: MeetingAssistType } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        // }).json()
        // console.log(response?.data?.insert_Meeting_Assist_one, ' this is response in upsertMeetingAssistOne')
        // return response?.data?.insert_Meeting_Assist_one
        const responseData = await resilientGotPostHasura(operationName, query, variables) as { insert_Meeting_Assist_one: MeetingAssistType };
        return responseData?.insert_Meeting_Assist_one;
    } catch (e) {
        chatApiHelperLogger.error('Error in upsertMeetingAssistOne', { meetingAssistId: meetingAssist?.id, error: (e as Error).message });
        throw e;
    }
}

export const listUserContactInfosGivenUserId = async (
    userId: string,
) => {
    try {
        // validate
        if (!userId) {
            throw new Error('no userId provided')
        }

        const operationName = 'ListUserContactInfoByUserId'
        const query = listUserContactInfosByUserId

        const variables = {
            userId,
        }

        const response: { data: { User_Contact_Info: UserContactInfoType[] } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        // }).json()
        // console.log(response?.data?.User_Contact_Info, ' this is response?.data?.User_Contact_Info')
        // return response?.data?.User_Contact_Info
        const responseData = await resilientGotPostHasura(operationName, query, variables, userId) as { User_Contact_Info: UserContactInfoType[] };
        return responseData?.User_Contact_Info;
    } catch (e) {
        chatApiHelperLogger.error('Error in listUserContactInfosGivenUserId', { userId, error: (e as Error).message });
        throw e;
    }
}

export const getUserContactInfosGivenIds = async (
    ids: string[],
) => {
    try {
        // validate
        if (!(ids?.length > 0)) {
            console.log('no ids provided')
            return
        }

        const operationName = 'GetContactInfosWithIds'
        const query = getContactInfosByIds

        const variables = {
            ids,
        }

        const response: { data: { User_Contact_Info: UserContactInfoType[] } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        // }).json()
        // console.log(response?.data?.User_Contact_Info, ' this is response in getContactInfosGivenIds')
        // return response?.data?.User_Contact_Info
        const responseData = await resilientGotPostHasura(operationName, query, variables) as { User_Contact_Info: UserContactInfoType[] }; // Assuming admin for this system-level lookup
        return responseData?.User_Contact_Info;
    } catch (e) {
        chatApiHelperLogger.error('Error in getUserContactInfosGivenIds', { ids, error: (e as Error).message });
        throw e;
    }
}

export const getContactByNameWithUserId = async (
    userId: string,
    name: string,
) => {
    try {
        // validate
        if (!userId || !name) {
            console.log('no userId or name provided')
            return
        }

        const operationName = 'GetContactByNameForUserId'
        const query = getContactByNameForUserId

        const variables = {
            userId,
            name,
        }

        const response: { data: { Contact: ContactType[] } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        // }).json()
        // console.log(response?.data?.Contact, ' this is response in getContactByNameWithUserId')
        // return response?.data?.Contact?.[0]
        const responseData = await resilientGotPostHasura(operationName, query, variables, userId) as { Contact: ContactType[] };
        return responseData?.Contact?.[0];
    } catch (e) {
        chatApiHelperLogger.error('Error in getContactByNameWithUserId', { userId, name, error: (e as Error).message });
        throw e;
    }
}

export const insertMeetingAssistAttendee = async (
    attendee: MeetingAssistAttendeeType,
) => {
    try {
        // validate
        if (!attendee) {
            throw new Error('no meeting assist provided')
        }

        const operationName = 'InsertMeetingAssistAttendee'
        const query = insertMeetingAssistAttendeeOne

        const variables = {
            attendee,
        }

        const response: { data: { insert_Meeting_Assist_Attendee_one: MeetingAssistAttendeeType } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        // }).json()
        // console.log(response?.data?.insert_Meeting_Assist_Attendee_one, ' this is response in insertMeetingAssistAttendee')
        // return response?.data?.insert_Meeting_Assist_Attendee_one
        const responseData = await resilientGotPostHasura(operationName, query, variables) as { insert_Meeting_Assist_Attendee_one: MeetingAssistAttendeeType };
        return responseData?.insert_Meeting_Assist_Attendee_one;
    } catch (e) {
        chatApiHelperLogger.error('Error in insertMeetingAssistAttendee', { attendeeId: attendee?.id, error: (e as Error).message });
        throw e;
    }
}

export const createHostAttendee = async (
    userId: string,
    meetingId: string,
    timezone: string,
    email?: string,
    name?: string,
) => {
    try {
        // validate
        if (!meetingId) {
            throw new Error('no meetingId provided')
        }

        const userInfoItems = await listUserContactInfosGivenUserId(userId)

        const attendeeId = uuid()

        const primaryInfoItem = userInfoItems?.find(u => (u.primary && (u.type === 'email'))) || userInfoItems?.[0]

        const hostAttendee: MeetingAssistAttendeeType = {
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
        }

        await insertMeetingAssistAttendee(hostAttendee)

        return attendeeId
    } catch (e) {
        chatApiHelperLogger.error('Unable to create host attendee for new event', { userId, meetingId, timezone, email, name, error: (e as Error).message, stack: (e as Error).stack });
        return undefined;
    }
}


export const upsertMeetingAssistInviteMany = async (
    meetingAssistInvites: MeetingAssistInviteType[],
) => {
    try {
        // validate
        if (!(meetingAssistInvites?.length > 0)) {
            throw new Error('no meeting assist invites provided')
        }

        const operationName = 'InsertMeetingAssistInvite'
        const query = upsertMeetingAssistInviteGraphql

        const variables = {
            meetingAssistInvites,
        }

        const response: { data: { insert_Meeting_Assist_Invite: MeetingAssistInviteType[] } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        // }).json()
        // console.log(response?.data?.insert_Meeting_Assist_Invite, ' this is response in upsertMeetingAssistInviteMany')
        // return response?.data?.insert_Meeting_Assist_Invite
        const responseData = await resilientGotPostHasura(operationName, query, variables) as { insert_Meeting_Assist_Invite: MeetingAssistInviteType[] };
        return responseData?.insert_Meeting_Assist_Invite;
    } catch (e) {
        chatApiHelperLogger.error('Error in upsertMeetingAssistInviteMany', { inviteCount: meetingAssistInvites?.length, error: (e as Error).message });
        throw e;
    }
}


export const updateUserNameGivenId = async (
    userId: string,
    name: string,
) => {
    try {
        // validate
        if (!userId || !name) {
            throw new Error('no meeting assist invites provided')
        }

        const operationName = 'UpdateNameForUserById'
        const query = updateNameForUserId

        const variables = {
            id: userId,
            name,
        }

        const response: { data: { update_User_by_pk: UserType } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        // }).json()
        // console.log(response?.data?.update_User_by_pk, ' this is response in updateUserNameGivenId')
        // return response?.data?.update_User_by_pk
        const responseData = await resilientGotPostHasura(operationName, query, variables, userId) as { update_User_by_pk: UserType };
        return responseData?.update_User_by_pk;
    } catch (e) {
        chatApiHelperLogger.error('Error in updateUserNameGivenId', { userId, name, error: (e as Error).message });
        throw e;
    }
}

export const getUserGivenId = async (
    userId: string,
) => {
    try {
        // validate
        if (!userId) {
            throw new Error('no userId provided')
        }

        const operationName = 'GetUserById'
        const query = getUserById

        const variables = {
            id: userId,
        }

        const response: { data: { User_by_pk: UserType } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        // }).json()
        // console.log(response?.data?.User_by_pk, ' this is response in getUserGivenId')
        // return response?.data?.User_by_pk
        const responseData = await resilientGotPostHasura(operationName, query, variables, userId) as { User_by_pk: UserType };
        return responseData?.User_by_pk;
    } catch (e) {
        chatApiHelperLogger.error('Error in getUserGivenId', { userId, error: (e as Error).message });
        throw e;
    }
}



export const callOpenAIWithMessageHistoryOnly = async (
    openai: OpenAI,
    messageHistory: ChatGPTMessageHistoryType = [],
    model: 'gpt-3.5-turbo' | 'gpt-3.5-turbo-16k' | 'gpt-4' = 'gpt-3.5-turbo',
) => {
    try {
        // assistant
        const completion = await openai.chat.completions.create({
            model,
            messages: messageHistory,
            timeout: 20000, // 20s timeout per attempt
        });
        chatApiHelperLogger.info(`OpenAI call (history only) successful on attempt ${attemptNumber}. Model: ${model}.`);
        return completion?.choices?.[0]?.message?.content;
      } catch (error: any) {
        chatApiHelperLogger.warn(`Attempt ${attemptNumber} for OpenAI call (history only) failed. Model: ${model}.`, {
            error: error.message, code: error.code, status: error.response?.status
        });
        if (error.response && [400, 401, 403, 404, 429].includes(error.response.status)) { // Added 429 as potentially non-retryable for some quota errors
            bail(error);
            return;
        }
        throw error;
      }
    }, {
        retries: 2, factor: 2, minTimeout: 1000, maxTimeout: 5000,
        onRetry: (error, attemptNumber) => {
            chatApiHelperLogger.warn(`Retrying OpenAI call (history only), attempt ${attemptNumber}. Model: ${model}. Error: ${error.message}`);
        }
    });
  } catch (error) {
    chatApiHelperLogger.error('Failed OpenAI call (history only) after all retries.', { model, error: (error as Error).message });
    throw error;
  }
}


export const callOpenAIWithMessageHistory = async (
    openai: OpenAI,
    messageHistory: ChatGPTMessageHistoryType = [],
    prompt: string,
    model: 'gpt-3.5-turbo' | 'gpt-3.5-turbo-16k' | 'gpt-4' = 'gpt-3.5-turbo',
    userData: string,
    exampleInput?: string,
    exampleOutput?: string,
) => {
  const operationName = "callOpenAIWithMessageHistory";
  try {
    return await retry(async (bail, attemptNumber) => {
      try {
        chatApiHelperLogger.info(`Attempt ${attemptNumber} for ${operationName}. Model: ${model}.`);
        const messages: OpenAI.Chat.Completions.ChatCompletionMessageParam[] = messageHistory.concat([
            { role: 'system' as ChatGPTRoleType, content: prompt },
            exampleInput && { role: 'user' as ChatGPTRoleType, content: exampleInput },
            exampleOutput && { role: 'assistant' as ChatGPTRoleType, content: exampleOutput },
            { role: 'user' as ChatGPTRoleType, content: userData }
        ])?.filter(m => !!m) as OpenAI.Chat.Completions.ChatCompletionMessageParam[];

        const completion = await openai.chat.completions.create({
            model,
            messages,
            timeout: 30000, // 30s timeout, potentially longer prompts/responses
        });
        chatApiHelperLogger.info(`${operationName} successful on attempt ${attemptNumber}. Model: ${model}.`);
        return { totalTokenCount: completion?.usage?.total_tokens, response: completion?.choices?.[0]?.message?.content };
      } catch (error: any) {
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
  } catch (error) {
    chatApiHelperLogger.error(`Failed ${operationName} after all retries.`, { model, error: (error as Error).message });
    throw error;
  }
}

export const callOpenAI = async (
    openai: OpenAI, // This param was named 'openai', but it seems it should be 'prompt' based on usage
    prompt: string, // Renamed from 'model' for clarity, as 'model' is the next param
    model: 'gpt-3.5-turbo' | 'gpt-3.5-turbo-16k' | 'gpt-4' = 'gpt-3.5-turbo',  // This was 'userData'
    userData: string, // This was 'exampleInput'
    exampleInput?: string, // This was 'exampleOutput'
    exampleOutput?: string, // This was not present
) => {
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
        const messages: OpenAI.Chat.Completions.ChatCompletionMessageParam[] = [
            { role: 'system' as ChatGPTRoleType, content: prompt },
            exampleInput && { role: 'user' as ChatGPTRoleType, content: exampleInput },
            exampleOutput && { role: 'assistant' as ChatGPTRoleType, content: exampleOutput },
            { role: 'user' as ChatGPTRoleType, content: userData }
        ]?.filter(m => !!m) as OpenAI.Chat.Completions.ChatCompletionMessageParam[];

        const completion = await openai.chat.completions.create({
            model,
            messages,
            timeout: 30000, // 30s
        });
        chatApiHelperLogger.info(`${operationName} successful on attempt ${attemptNumber}. Model: ${model}.`);
        return completion?.choices?.[0]?.message?.content;
      } catch (error: any) {
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
  } catch (error) {
    chatApiHelperLogger.error(`Failed ${operationName} after all retries.`, { model, error: (error as Error).message });
    throw error;
  }
}





export const listEventsForUserGivenDates = async (
    userId: string,
    senderStartDate: string,
    senderEndDate: string,
    // senderTimezone: string,
    // receiverTimezone: string,
) => {
    try {

        const operationName = 'listEventsForUser'
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
        `
        // get events
        // local date
        // const startDateInReceiverTimezone = dayjs(senderStartDate.slice(0, 19)).tz(receiverTimezone, true)
        // const endDateInReceiverTimezone = dayjs((senderEndDate.slice(0, 19))).tz(receiverTimezone, true)
        // const startDateInSenderTimezone = dayjs(startDateInReceiverTimezone).format().slice(0, 19)
        // const endDateInSenderTimezone = dayjs(endDateInReceiverTimezone).format().slice(0, 19)


        const res: { data: { Event: EventType[] } } = await got.post(
            hasuraGraphUrl,
            {
                headers: {
                    'X-Hasura-Admin-Secret': hasuraAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Hasura-Role': 'admin'
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
            },
        // ).json()
        // console.log(res, ' res from listEventsforUser')
        // return res?.data?.Event
        const responseData = await resilientGotPostHasura(operationName, query, { userId, startDate: senderStartDate, endDate: senderEndDate }, userId) as { Event: EventType[] };
        return responseData?.Event;
    } catch (e) {
        chatApiHelperLogger.error('Error in listEventsForUserGivenDates', { userId, senderStartDate, senderEndDate, error: (e as Error).message });
        throw e;
    }
}

export const extractAttributesNeededFromUserInput = async (
    userInput: string,
) => {
    try {
        const openAIDateTime = await callOpenAI(openai, extractNeededAttributesPrompt, openAIChatGPT35Model, userInput, extractNeededAttributesExampleInput, extractNeededAttributesExampleOutput)
        const attributesStartIndex = openAIDateTime.indexOf('{')
        const attributesEndIndex = openAIDateTime.lastIndexOf('}')
        const attributesJSONString = openAIDateTime.slice(attributesStartIndex, attributesEndIndex + 1)
        const attributes: QueryCalendarExtractedAttributesType = JSON.parse(attributesJSONString)

        return attributes
    } catch (e) {
        chatApiHelperLogger.error('Unable to extract attributes needed from user input', { userInput, error: (e as Error).message, stack: (e as Error).stack });
        // Original function implicitly returns undefined here.
        return undefined;
    }
}


export const generateQueryDateFromUserInput = async (
    userId: string,
    timezone: string,
    userInput: string,
    userCurrentTime: string,
) => {
    try {
        const queryDateSysMessage = { role: 'system' as ChatGPTRoleType, content: extractQueryUserInputTimeToJSONPrompt }
        const queryDateMessageHistory: ChatGPTMessageHistoryType = []
        const queryDateUserMessage1 = { role: 'user' as ChatGPTRoleType, content: extractQueryUserInputTimeToJSONExampleInput1 }
        const queryDateAssistantMessage1 = { role: 'assistant' as ChatGPTRoleType, content: extractQueryUserInputTimeToJSONExampleOutput1 }
        const queryDateUserMessage2 = { role: 'user' as ChatGPTRoleType, content: extractQueryUserInputTimeToJSONExampleInput2 }
        const queryDateAssistantMessage2 = { role: 'assistant' as ChatGPTRoleType, content: extractQueryUserInputTimeToJSONExampleOutput2 }
        const queryDateUserMessage3 = { role: 'user' as ChatGPTRoleType, content: extractQueryUserInputTimeToJSONExampleInput3 }
        const queryDateAssistantMessage3 = { role: 'assistant' as ChatGPTRoleType, content: extractQueryUserInputTimeToJSONExampleOutput3 }

        
        // user work times
        const userPreferences = await getUserPreferences(userId)

        const workTimesObject = generateWorkTimesForUser(userPreferences, timezone)
        let userWorkTimes = ''
        for (const workTimeObject of workTimesObject) {

            userWorkTimes += `${workTimeObject?.dayOfWeek}: ${workTimeObject?.startTime} - ${workTimeObject?.endTime} \n`

        }
        chatApiHelperLogger.debug('[generateQueryDateFromUserInput] User work times string:', { userId, userWorkTimes });
        const queryDateEngine = new TemplateEngine(extractQueryUserInputTimeToJSONTemplate);
        const queryDateRendered = queryDateEngine.render({ userCurrentTime, userWorkTimes: userWorkTimes, userInput })

        const queryDateUserMessageInput = { role: 'user' as ChatGPTRoleType, content: queryDateRendered }
        queryDateMessageHistory.push(queryDateSysMessage, queryDateUserMessage1, queryDateAssistantMessage1, queryDateUserMessage2, queryDateAssistantMessage2, queryDateUserMessage3, queryDateAssistantMessage3, queryDateUserMessageInput)

        const openAIQueryDate = await callOpenAIWithMessageHistoryOnly(openai, queryDateMessageHistory, openAIChatGPT35Model)
        const queryDateStartIndex = openAIQueryDate.indexOf('{')
        const queryDateEndIndex = openAIQueryDate.lastIndexOf('}')
        const queryDateJSONString = openAIQueryDate.slice(queryDateStartIndex, queryDateEndIndex + 1)
        const queryDate: QueryCalendarExtractedJSONType = JSON.parse(queryDateJSONString)

        return queryDate
    } catch (e) {
        chatApiHelperLogger.error('Unable to generate queryDate from user input', { userId, timezone, userInput, userCurrentTime, error: (e as Error).message, stack: (e as Error).stack });
        // Original function implicitly returns undefined here.
        return undefined;
    }
}

export const generateMissingFieldsQueryDateFromUserInput = async (
    userId: string,
    timezone: string,
    userInput: string,
    priorUserInput: string,
    priorAssistantOutput: string,
    userCurrentTime: string,
) => {
    try {
        const queryDateSysMessage = { role: 'system' as ChatGPTRoleType, content: extractQueryUserInputTimeToJSONPrompt }
        const queryDateMessageHistory: ChatGPTMessageHistoryType = []
        const queryDateUserMessage1 = { role: 'user' as ChatGPTRoleType, content: extractQueryUserInputTimeToJSONExampleInput1 }
        const queryDateAssistantMessage1 = { role: 'assistant' as ChatGPTRoleType, content: extractQueryUserInputTimeToJSONExampleOutput1 }
        const queryDateUserMessage2 = { role: 'user' as ChatGPTRoleType, content: extractQueryUserInputTimeToJSONExampleInput2 }
        const queryDateAssistantMessage2 = { role: 'assistant' as ChatGPTRoleType, content: extractQueryUserInputTimeToJSONExampleOutput2 }
        const queryDateUserMessage3 = { role: 'user' as ChatGPTRoleType, content: extractQueryUserInputTimeToJSONExampleInput3 }
        const queryDateAssistantMessage3 = { role: 'assistant' as ChatGPTRoleType, content: extractQueryUserInputTimeToJSONExampleOutput3 }

        const queryDateUserMessage4 = { role: 'user' as ChatGPTRoleType, content: priorUserInput }
        const queryDateAssistantMessage4 = { role: 'assistant' as ChatGPTRoleType, content: priorAssistantOutput }

        // user work times
        const userPreferences = await getUserPreferences(userId)

        const workTimesObject = generateWorkTimesForUser(userPreferences, timezone)
        let userWorkTimes = ''
        for (const workTimeObject of workTimesObject) {

            userWorkTimes += `${workTimeObject?.dayOfWeek}: ${workTimeObject?.startTime} - ${workTimeObject?.endTime} \n`

        }
        chatApiHelperLogger.debug('[generateMissingFieldsQueryDateFromUserInput] User work times string:', { userId, userWorkTimes });
        const queryDateEngine = new TemplateEngine(extractQueryUserInputTimeToJSONTemplate);
        const queryDateRendered = queryDateEngine.render({ userCurrentTime, userWorkTimes: userWorkTimes, userInput })

        const queryDateUserMessageInput = { role: 'user' as ChatGPTRoleType, content: queryDateRendered }
        queryDateMessageHistory.push(queryDateSysMessage, queryDateUserMessage1, queryDateAssistantMessage1, queryDateUserMessage2, queryDateAssistantMessage2, queryDateUserMessage3, queryDateAssistantMessage3,
            queryDateUserMessage4, queryDateAssistantMessage4, queryDateUserMessageInput)

        const openAIQueryDate = await callOpenAIWithMessageHistoryOnly(openai, queryDateMessageHistory, openAIChatGPT35Model)
        const queryDateStartIndex = openAIQueryDate.indexOf('{')
        const queryDateEndIndex = openAIQueryDate.lastIndexOf('}')
        const queryDateJSONString = openAIQueryDate.slice(queryDateStartIndex, queryDateEndIndex + 1)
        const queryDate: QueryCalendarExtractedJSONType = JSON.parse(queryDateJSONString)

        return queryDate
    } catch (e) {
        chatApiHelperLogger.error('Unable to generate missing fields queryDate from user input', { userId, timezone, userInput, priorUserInput, priorAssistantOutput, userCurrentTime, error: (e as Error).message, stack: (e as Error).stack });
        return undefined;
    }
}

export const generateDateTime = async (
    userInput: string,
    userCurrentTime: string,
    timezone: string,
) => {
    try {
        // dayjs().tz(timezone).format('dddd, YYYY-MM-DDTHH:mm:ssZ')
        const template = userInputToDateTimeJSONPrompt
        const engine = new TemplateEngine(template)
        const rendered = engine.render({ userCurrentTime })
        const systemMessage1 = { role: 'system' as ChatGPTRoleType, content: rendered }
        const userMessage1 = { role: 'user' as ChatGPTRoleType, content: userInputToDateTimeJSONExampleInput1 }

        const exampleOutput1Template = userInputToDateTimeJSONExampleOutput1
        const engine2 = new TemplateEngine(exampleOutput1Template)
        const currentTimeObject = dayjs(userCurrentTime, 'dddd, YYYY-MM-DDTHH:mm:ssZ').tz(timezone)
        const year = currentTimeObject.format('YYYY')
        const month = currentTimeObject.format('MM')
        const exampleOutput1Rendered = engine2.render({ year, month })
        const assistantMessage1 = { role: 'assistant' as ChatGPTRoleType, content: exampleOutput1Rendered }

        const userMessage2 = { role: 'user' as ChatGPTRoleType, content: userInputToDateTimeJSONExampleInput2 }
        
        const exampleOutput2Template = userInputToDateTimeJSONExampleOutput2
        const engine3 = new TemplateEngine(exampleOutput2Template)
        const exampleOutput2Rendered = engine3.render({ year, month })
        const assistantMessage2 = { role: 'assistant' as ChatGPTRoleType, content: exampleOutput2Rendered }

        const userMessage3 = { role: 'user' as ChatGPTRoleType, content: userInputToDateTimeJSONExampleInput3 }
        const assistantMessage3 = { role: 'assistant' as ChatGPTRoleType, content: userInputToDateTimeJSONExampleOutput3 }


        const userMessage4 = { role: 'user' as ChatGPTRoleType, content: userInput }

        const messageHistory: ChatGPTMessageHistoryType = []

        messageHistory.push(systemMessage1, userMessage1, assistantMessage1, userMessage4)

        const openAIDateTime = await callOpenAIWithMessageHistoryOnly(openai, messageHistory, openAIChatGPT35Model)

        // const openAIDateTime = await callOpenAI(openai, userInputToDateTimeJSONPrompt, openAIChatGPT35Model, userInput, userInputToDateTimeJSONExampleInput1, userInputToDateTimeJSONExampleOutput1)
        const dateTimeStartIndex = openAIDateTime.indexOf('{')
        chatApiHelperLogger.debug('[generateDateTime] OpenAI response processing', { dateTimeStartIndex, openAIDateTimeLength: openAIDateTime?.length });
        const dateTimeEndIndex = openAIDateTime.lastIndexOf('}')
        chatApiHelperLogger.debug('[generateDateTime] OpenAI response processing', { dateTimeEndIndex });
        const dateTimeJSONString = openAIDateTime.slice(dateTimeStartIndex, dateTimeEndIndex + 1)
        const dateTime: DateTimeJSONType = JSON.parse(dateTimeJSONString)

        return dateTime
    } catch (e) {
        chatApiHelperLogger.error('Unable to generate DateTime from user input', { userInput, userCurrentTime, timezone, error: (e as Error).message, stack: (e as Error).stack });
        return undefined;
    }
}

export const generateMissingFieldsDateTime = async (
    userInput: string,
    priorUserInput: string,
    priorAssistantOutput: string,
    userCurrentTime: string,
    timezone: string,
) => {
    try {
        // dayjs().tz(timezone).format('dddd, YYYY-MM-DDTHH:mm:ssZ')
        const template = userInputToDateTimeJSONPrompt
        const engine = new TemplateEngine(template)
        const rendered = engine.render({ userCurrentTime })
        const systemMessage1 = { role: 'system' as ChatGPTRoleType, content: rendered }
        const userMessage1 = { role: 'user' as ChatGPTRoleType, content: userInputToDateTimeJSONExampleInput1 }

        const exampleOutput1Template = userInputToDateTimeJSONExampleOutput1
        const engine2 = new TemplateEngine(exampleOutput1Template)
        const currentTimeObject = dayjs(userCurrentTime, 'dddd, YYYY-MM-DDTHH:mm:ssZ').tz(timezone)
        const year = currentTimeObject.format('YYYY')
        const month = currentTimeObject.format('MM')
        const exampleOutput1Rendered = engine2.render({ year, month })
        const assistantMessage1 = { role: 'assistant' as ChatGPTRoleType, content: exampleOutput1Rendered }

        const userMessage2 = { role: 'user' as ChatGPTRoleType, content: userInputToDateTimeJSONExampleInput2 }
        
        const exampleOutput2Template = userInputToDateTimeJSONExampleOutput2
        const engine3 = new TemplateEngine(exampleOutput2Template)
        const exampleOutput2Rendered = engine3.render({ year, month })
        const assistantMessage2 = { role: 'assistant' as ChatGPTRoleType, content: exampleOutput2Rendered }

        const userMessage3 = { role: 'user' as ChatGPTRoleType, content: userInputToDateTimeJSONExampleInput3 }
        const assistantMessage3 = { role: 'assistant' as ChatGPTRoleType, content: userInputToDateTimeJSONExampleOutput3 }

        const userMessage4 = { role: 'user' as ChatGPTRoleType, content: priorUserInput }
        const assistantMessage4 = { role: 'assistant' as ChatGPTRoleType, content: priorAssistantOutput }

        const userMessage5 = { role: 'user' as ChatGPTRoleType, content: userInput }

        const messageHistory: ChatGPTMessageHistoryType = []

        messageHistory.push(systemMessage1, userMessage1, assistantMessage1, userMessage2, assistantMessage2, userMessage3, assistantMessage3, userMessage4, assistantMessage4, userMessage5)

        const openAIDateTime = await callOpenAIWithMessageHistoryOnly(openai, messageHistory, openAIChatGPT35LongModel)

        // const openAIDateTime = await callOpenAI(openai, userInputToDateTimeJSONPrompt, openAIChatGPT35Model, userInput, userInputToDateTimeJSONExampleInput1, userInputToDateTimeJSONExampleOutput1)
        const dateTimeStartIndex = openAIDateTime.indexOf('{')
        chatApiHelperLogger.debug('[generateMissingFieldsDateTime] OpenAI response processing', { dateTimeStartIndex, openAIDateTimeLength: openAIDateTime?.length });
        const dateTimeEndIndex = openAIDateTime.lastIndexOf('}')
        chatApiHelperLogger.debug('[generateMissingFieldsDateTime] OpenAI response processing', { dateTimeEndIndex });
        const dateTimeJSONString = openAIDateTime.slice(dateTimeStartIndex, dateTimeEndIndex + 1)
        const dateTime: DateTimeJSONType = JSON.parse(dateTimeJSONString)

        return dateTime
    } catch (e) {
        chatApiHelperLogger.error('Unable to generate missing fields DateTime from user input', { userInput, priorUserInput, priorAssistantOutput, userCurrentTime, timezone, error: (e as Error).message, stack: (e as Error).stack });
        return undefined;
    }
}


export const generateAssistantMessageFromAPIResponseForUserQuery = async (
    openai: OpenAI,
    apiResponse: string,
    messageHistoryObject: SkillMessageHistoryType
): Promise<AssistantMessageType> => {
    try {
        const messageLength = messageHistoryObject.messages?.length
        let userMessage = ''
        for (let i = messageLength; i > 0; i--) {

            const message = messageHistoryObject.messages[i - 1]

            if (message.role === 'user') {
                userMessage = message.content
                break
            }
        }

        const template = apiResponeToAssistantResponsePrompt
        const engine = new TemplateEngine(template)
        const rendered = engine.render({ userInput: userMessage, apiResponse })

        const systemMessage: SystemMessageType = {
            role: 'system',
            content: rendered,
        }

        const res = await callOpenAIWithMessageHistoryOnly(openai, [systemMessage], openAIChatGPT35Model)

        const assistantMessage: AssistantMessageType = {
            role: 'assistant',
            content: res,
        }

        return assistantMessage
    } catch (e) {
        chatApiHelperLogger.error('Unable to generate assistant message from API response', { apiResponse, messageHistoryObjectId: messageHistoryObject?.id, error: (e as Error).message, stack: (e as Error).stack });
        // Consider returning a default error message or rethrowing
        return { role: 'assistant', content: "I encountered an issue processing that request. Please try again." }; // Example fallback
    }
}

export const generateAssistantMessageToRequestUserForMissingFields = async (
    openai: OpenAI,
    missingData: RequiredFieldsType,
    messageHistoryObject: SkillMessageHistoryType
): Promise<AssistantMessageType> => {
    try {
        let missingDataString = ''

        for (const property in missingData) {

            if (property === 'required') {

                const requiredFields = missingData?.[property]

                if (requiredFields?.length > 0) {

                    for (const requiredField of requiredFields) {

                        for (const requiredProperty in requiredField) {

                            if (requiredProperty === 'oneOf') {
                                const oneOfs = requiredField[requiredProperty]
                                
                                if (oneOfs?.length > 0) {
                                    for (const oneOf of oneOfs) {

                                        for (const oneOfProperty in oneOf) {

                                            if (oneOfProperty === 'and') {

                                                const objectFields = oneOf[oneOfProperty]

                                                if (objectFields?.length > 0) {

                                                    for (const objectField of objectFields) {

                                                        missingDataString += `${objectField?.value}, `
                                                    }
                                                }
                                            } else if (oneOfProperty === 'value') {
                                                
                                                const value = oneOf[oneOfProperty]

                                                missingDataString += `${value}, `
                                            }
                                        }
                                    }
                                }
                            } else if (requiredProperty === 'value') {

                                const value = requiredField[requiredProperty]

                                missingDataString += `${value}, `
                            } else if (requiredProperty === 'and') {
                                const objectFields = requiredField[requiredProperty]

                                if (objectFields?.length > 0) {

                                    for (const objectField of objectFields) {

                                        missingDataString += `${objectField?.value}, `
                                    }
                                }
                            }
                        }
                    }
                }
            } else if (property === 'dateTime') {
                const dateTime = missingData[property]

                for (const dateTimeProperty in dateTime) {

                    if (dateTimeProperty === 'required') {
                        const requiredFields = dateTime?.[dateTimeProperty]

                        if (requiredFields?.length > 0) {

                            for (const requiredField of requiredFields) {

                                for (const requiredProperty in requiredField) {

                                    if (requiredProperty === 'oneOf') {
                                        const oneOfs = requiredField[requiredProperty]

                                        if (oneOfs?.length > 0) {
                                            for (const oneOf of oneOfs) {

                                                for (const oneOfProperty in oneOf) {

                                                    if (oneOfProperty === 'and') {

                                                        const objectFields = oneOf[oneOfProperty]

                                                        if (objectFields?.length > 0) {

                                                            for (const objectField of objectFields) {

                                                                missingDataString += `${objectField?.value}, `
                                                            }
                                                        }
                                                    } else if (oneOfProperty === 'value') {

                                                        const value = oneOf[oneOfProperty]

                                                        missingDataString += `${value}, `
                                                    }
                                                }
                                            }
                                        }
                                    } else if (requiredProperty === 'value') {

                                        const value = requiredField[requiredProperty]

                                        missingDataString += `${value}, `
                                    } else if (requiredProperty === 'and') {
                                        const objectFields = requiredField[requiredProperty]

                                        if (objectFields?.length > 0) {

                                            for (const objectField of objectFields) {

                                                missingDataString += `${objectField?.value}, `
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            } else if (property === 'attributes') {
                const attributes = missingData[property]

                for (const attributesProperty in attributes) {

                    if (attributesProperty === 'required') {
                        const requiredFields = attributes?.[attributesProperty]

                        if (requiredFields?.length > 0) {

                            for (const requiredField of requiredFields) {

                                for (const requiredProperty in requiredField) {

                                    if (requiredProperty === 'oneOf') {
                                        const oneOfs = requiredField[requiredProperty]

                                        if (oneOfs?.length > 0) {
                                            for (const oneOf of oneOfs) {

                                                for (const oneOfProperty in oneOf) {

                                                    if (oneOfProperty === 'and') {

                                                        const objectFields = oneOf[oneOfProperty]

                                                        if (objectFields?.length > 0) {

                                                            for (const objectField of objectFields) {

                                                                missingDataString += `${objectField?.value}, `
                                                            }
                                                        }
                                                    } else if (oneOfProperty === 'value') {

                                                        const value = oneOf[oneOfProperty]

                                                        missingDataString += `${value}, `
                                                    }
                                                }
                                            }
                                        }
                                    } else if (requiredProperty === 'value') {

                                        const value = requiredField[requiredProperty]

                                        missingDataString += `${value}, `
                                    } else if (requiredProperty === 'and') {
                                        const objectFields = requiredField[requiredProperty]

                                        if (objectFields?.length > 0) {

                                            for (const objectField of objectFields) {

                                                missingDataString += `${objectField?.value}, `
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            } else if (property === 'queryDate') {
                const queryDate = missingData[property]

                for (const queryDateProperty in queryDate) {

                    if (queryDateProperty === 'required') {
                        const requiredFields = queryDate?.[queryDateProperty]

                        if (requiredFields?.length > 0) {

                            for (const requiredField of requiredFields) {

                                for (const requiredProperty in requiredField) {

                                    if (requiredProperty === 'oneOf') {
                                        const oneOfs = requiredField[requiredProperty]

                                        if (oneOfs?.length > 0) {
                                            for (const oneOf of oneOfs) {

                                                for (const oneOfProperty in oneOf) {

                                                    if (oneOfProperty === 'and') {

                                                        const objectFields = oneOf[oneOfProperty]

                                                        if (objectFields?.length > 0) {

                                                            for (const objectField of objectFields) {

                                                                missingDataString += `${objectField?.value}, `
                                                            }
                                                        }
                                                    } else if (oneOfProperty === 'value') {

                                                        const value = oneOf[oneOfProperty]

                                                        missingDataString += `${value}, `
                                                    }
                                                }
                                            }
                                        }
                                    } else if (requiredProperty === 'value') {

                                        const value = requiredField[requiredProperty]

                                        missingDataString += `${value}, `
                                    } else if (requiredProperty === 'and') {
                                        const objectFields = requiredField[requiredProperty]

                                        if (objectFields?.length > 0) {

                                            for (const objectField of objectFields) {

                                                missingDataString += `${objectField?.value}, `
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

        const messageLength = messageHistoryObject.messages?.length
        let userMessage = ''
        for (let i = messageLength; i > 0; i--) {

            const message = messageHistoryObject.messages[i - 1]

            if (message.role === 'user') {
                userMessage = message.content
                break
            }
        }
        const template = requestMissingFieldsPrompt
        const engine = new TemplateEngine(template)
        const rendered = engine.render({ userInput: userMessage, missingFields: missingDataString })

        const systemMessage2: SystemMessageType = {
            role: 'system',
            content: rendered,
        }

        const systemMessage1 = { role: 'system' as ChatGPTRoleType, content: requestMissingFieldsSystemsExampleInput }
        const assistantMessage1 = { role: 'assistant' as ChatGPTRoleType, content: requestMissingFieldsExampleOutput }

        const messageHistory: ChatGPTMessageHistoryType = []

        messageHistory.push(systemMessage1, assistantMessage1, systemMessage2)

        const openAIData = await callOpenAIWithMessageHistoryOnly(openai, messageHistory, openAIChatGPT35Model)

        const assitantMessage: AssistantMessageType = {
            role: 'assistant',
            content: openAIData,
        }

        return assitantMessage

    } catch (e) {
        chatApiHelperLogger.error('Unable to generate user request for missing fields', { missingDataString, messageHistoryObjectId: messageHistoryObject?.id, error: (e as Error).message, stack: (e as Error).stack });
        return { role: 'assistant', content: "I need a bit more information to proceed. Could you clarify?" }; // Example fallback
    }
}

export const generateJSONDataFromUserInput = async (
    userInput: string,
    userCurrentTime: string,
) => {
    try {
        
        const messageHistory: ChatGPTMessageHistoryType = []

        const userMessage1 = { role: 'user' as ChatGPTRoleType, content: userInputToJSONExampleInput }
        const assistantMessage1 = { role: 'assistant' as ChatGPTRoleType, content: userInputToJSONExampleOutput }

        const dataEngine = new TemplateEngine(userInputToJSONPrompt);
        const dataRendered = dataEngine.render({ userCurrentTime })
        
        const dataSysMessage = { role: 'system' as ChatGPTRoleType, content: dataRendered }
        const dataUserMessageInput = { role: 'user' as ChatGPTRoleType, content: userInput }

        messageHistory.push(dataSysMessage, userMessage1, assistantMessage1, dataUserMessageInput)

        const openAIData = await callOpenAIWithMessageHistoryOnly(openai, messageHistory, openAIChatGPT35Model)
        const dataStartIndex = openAIData.indexOf('{')
        const dataEndIndex = openAIData.lastIndexOf('}')
        const dataJSONString = openAIData.slice(dataStartIndex, dataEndIndex + 1)
        const data: UserInputToJSONType = JSON.parse(dataJSONString)

        return data
    } catch (e) {
        chatApiHelperLogger.error('Unable to generate JSON data from user input', { userInput, userCurrentTime, error: (e as Error).message, stack: (e as Error).stack });
        return undefined;
    }
}

export const generateMissingFieldsJSONDataFromUserInput = async (
    userInput: string,
    priorUserInput: string,
    priorAssistantOutput: string,
    userCurrentTime: string,
) => {
    try {
        
        const messageHistory: ChatGPTMessageHistoryType = []

        const userMessage1 = { role: 'user' as ChatGPTRoleType, content: userInputToJSONExampleInput }
        const assistantMessage1 = { role: 'assistant' as ChatGPTRoleType, content: userInputToJSONExampleOutput }

        const dataEngine = new TemplateEngine(userInputToJSONPrompt);
        const dataRendered = dataEngine.render({ userCurrentTime })
        
        const dataSysMessage = { role: 'system' as ChatGPTRoleType, content: dataRendered }
        const dataUserMessageInput = { role: 'user' as ChatGPTRoleType, content: userInput }

        const userMessage2 = { role: 'user' as ChatGPTRoleType, content: priorUserInput }
        const assistantMessage2 = { role: 'assistant' as ChatGPTRoleType, content: priorAssistantOutput }

        messageHistory.push(dataSysMessage, userMessage1, assistantMessage1, userMessage2, assistantMessage2, dataSysMessage, dataUserMessageInput)

        const openAIData = await callOpenAIWithMessageHistoryOnly(openai, messageHistory, openAIChatGPT35Model)
        const dataStartIndex = openAIData.indexOf('{')
        const dataEndIndex = openAIData.lastIndexOf('}')
        const dataJSONString = openAIData.slice(dataStartIndex, dataEndIndex + 1)
        const data: UserInputToJSONType = JSON.parse(dataJSONString)

        return data
    } catch (e) {
        chatApiHelperLogger.error('Unable to generate missing fields JSON data from user input', { userInput, priorUserInput, priorAssistantOutput, userCurrentTime, error: (e as Error).message, stack: (e as Error).stack });
        return undefined;
    }
}

export const generateWorkSchedule = async (
    userId: string,
    timezone: string, 
    windowStartDate: string,
    windowEndDate: string,
) => {
    try {
        // listEventsForUserGivenDates
        const events = await listEventsForUserGivenDates(userId, windowStartDate, windowEndDate)

        let userSchedule = ''
        const uniqDates = _.uniqBy(events, (curr) => (dayjs(curr?.startDate?.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD')))

        for (const uniqDate of uniqDates) {
            const filteredEvents = events?.filter(a => (dayjs(a?.startDate?.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD') === dayjs(uniqDate?.startDate?.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD')))

            if (filteredEvents?.length > 0) {

                userSchedule += `${dayjs(uniqDate?.startDate?.slice(0, 19)).tz(timezone, true).format('ddd')} (${dayjs(uniqDate?.startDate?.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD')}) \n`
                
                for (const filteredEvent of filteredEvents) {
                    userSchedule += `- ${filteredEvent?.title || filteredEvent?.summary}: ${dayjs(filteredEvent?.startDate?.slice(0, 19)).tz(timezone, true).format('h:mm a')} - ${dayjs(filteredEvent?.endDate?.slice(0, 19)).tz(timezone, true).format('h:mm a')} \n`
                }
            }

        }

        return userSchedule
    } catch (e) {
        chatApiHelperLogger.error('Unable to generate work schedule', { userId, timezone, windowStartDate, windowEndDate, error: (e as Error).message, stack: (e as Error).stack });
        return ""; // Return empty string or handle error as appropriate
    }
}

export const findAnEmptySlot = async (
    userId: string,
    timezone: string,
    windowStartDate: string,
    windowEndDate: string,
    eventDuration: number,
) => {
    try {
        const userSchedule = await generateWorkSchedule(userId, timezone, windowStartDate, windowEndDate)

        const dataEngine = new TemplateEngine(findASlotForNewEventTemplate);
        const dataRendered = dataEngine.render({ eventDuration: `${eventDuration}`, userSchedule })

        const emptySlotRes = await callOpenAI(openai, findASlotForNewEventPrompt, openAIChatGPT35Model, dataRendered, findASlotForNewEventExampleInput, findASlotForNewEventExampleOutput)
        const dataStartIndex = emptySlotRes.indexOf('{')
        const dataEndIndex = emptySlotRes.lastIndexOf('}')
        const dataJSONString = emptySlotRes.slice(dataStartIndex, dataEndIndex + 1)
        const data: FindASlotType = JSON.parse(dataJSONString)
        return data
    } catch (e) {
        chatApiHelperLogger.error('Unable to find an empty slot', { userId, timezone, windowStartDate, windowEndDate, eventDuration, error: (e as Error).message, stack: (e as Error).stack });
        return undefined;
    }
}


