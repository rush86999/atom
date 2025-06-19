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

// const sesClient = new SESClient({ region: "us-east-1" })

const openai = new OpenAI({
    apiKey: defaultOpenAIAPIKey,
});

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
        console.error('Error in searchSingleEventByVectorLanceDb:', e);
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
        console.error('Error in searchSingleEventByVectorWithDatesLanceDb:', e);
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
        console.error('Error in searchMultipleEventsByVectorWithDatesLanceDb:', e);
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

        const res: { data: { insert_Conference_one: ConferenceType } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        }).json()

        console.log(res, ' successfully inserted one conference')

        return res?.data?.insert_Conference_one
    } catch (e) {
        console.log(e, ' unable to insert conference')
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

        reminders.forEach(r => console.log(r, ' reminder inside insertReminders'))

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

        const response: { data: { insert_Reminder: { returning: ReminderType[] } } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        }).json()

        console.log(response?.data?.insert_Reminder?.returning, ' this is response in insertReminders')
        response?.data?.insert_Reminder?.returning.forEach(r => console.log(r, ' response in insertReminder'))

    } catch (e) {
        console.log(e, ' unable to insertReminders')
    }
}

export const upsertEvents = async (
    events: EventType[]
) => {
    try {
        if (!(events?.length > 0)) {
            console.log('no events found in upsertEvents')
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
        _.uniqBy(events, 'id').forEach(e => console.log(e?.id, e, 'id, e inside upsertEventsPostPlanner '))
        const variables = {
            events: _.uniqBy(events, 'id'),
        }

        const response: { data: { insert_Event: { affected_rows: number, returning: { id: string }[] } } } = await got.post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'X-Hasura-Role': 'admin'
            },
            json: {
                operationName,
                query,
                variables,
            }
        }).json()
        console.log(response, response?.data?.insert_Event?.affected_rows, ' response after upserting events')
        response?.data?.insert_Event?.returning?.forEach(e => console.log(e, ' returning  response after upserting events'))
        return response
    } catch (e) {
        console.log(e, ' unable to update event')
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
        console.log('Adding document:')
        console.log(response.body)
    } catch (e) {
        console.log(e, ' unable to put data into search')
    }
}

export const getEventVectorFromLanceDb = async (id: string): Promise<number[] | null> => {
    try {
        const event = await getEventFromLanceDbById(id);
        return event?.vector || null;
    } catch (e) {
        console.error(`Error fetching event vector for ID ${id} from LanceDB:`, e);
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
        await upsertEvents([eventEntry]);
        console.log(`Event ${id} upserted to LanceDB.`);
    } catch (e) {
        console.error(`Error upserting event ${id} to LanceDB:`, e);
        throw e;
    }
}

export const deleteEventFromLanceDb = async (id: string): Promise<void> => {
    try {
        await deleteEventsByIds([id]);
        console.log(`Event ${id} deleted from LanceDB.`);
    } catch (e) {
        console.error(`Error deleting event ${id} from LanceDB:`, e);
        throw e;
    }
}

export const deleteTrainingDataFromLanceDb = async (id: string): Promise<void> => {
    try {
        await deleteTrainingEventsByIds([id]);
        console.log(`Training data for ID ${id} deleted from LanceDB.`);
    } catch (e) {
        console.error(`Error deleting training data for ID ${id} from LanceDB:`, e);
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
        console.log(`Training data for ID ${id} updated/upserted in LanceDB.`);
    } catch (e) {
        console.error(`Error updating training data for ID ${id} in LanceDB:`, e);
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
        console.error('Error searching training data in LanceDB:', e);
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

        const res = await openai.embeddings.create(embeddingRequest)
        console.log(res, ' res inside convertEventTitleToOpenAIVectors')
        return res?.data?.[0]?.embedding
    } catch (e) {
        console.log(e, ' unable to convert event title to openaivectors')
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

    console.log(year, month, day, hour, minute, ' year, month, day, hour, minute,' )

    if (day) {

        if ((!!hour) && (!!minute)) {

            if (year && month) {
                const yearAndMonthAndDate = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true)
                console.log(yearAndMonthAndDate.format(), ' yearAndMonthAndDate.format()')
                
                meetingStartDateObject = meetingStartDateObject
                    .year(yearAndMonthAndDate.year())
                    .month(yearAndMonthAndDate.month())
                    .date(yearAndMonthAndDate.date())
                    .hour(hour)
                    .minute(minute)
                
                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month')
            } else {

                const dateOfMonth = dayjs(day, 'DD').tz(timezone, true)
                console.log(dateOfMonth, ' dateOfMonth')
                meetingStartDateObject = meetingStartDateObject
                    .date(dateOfMonth.date())
                    .hour(hour)
                    .minute(minute)

                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside DD')

            }


        } else if (time) {
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}-${day} ${time}`, 'YYYY-MM-DD HH:mm').tz(timezone, true)
                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside time, year && month')
            } else {

                meetingStartDateObject = dayjs(`${day} ${time}`, 'DD HH:mm').tz(timezone, true)

                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside time')

            }
        } else if (!time && !hour && !minute) {
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true)
                console.log(meetingStartDateObject.format(), ' meetingDateObject inside year && month')
            } else {

                meetingStartDateObject = dayjs(day, 'DD').tz(timezone, true)

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside DD')

            }
        }
    } else if (isoWeekday) {

        const givenISODay = isoWeekday
        const currentISODay = getISODay(dayjs(currentTime).tz(timezone, true).toDate())

        if ((!!hour) && (!!minute)) {

            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                    .hour(hour)
                    .minute(minute)
                
                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month from isoDay')

                if (givenISODay < currentISODay) {

                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay year && month')
                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))
                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay year && month')
                }

            } else {

                meetingStartDateObject = dayjs().tz(timezone, true)
                    .hour(hour)
                    .minute(minute)

                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, hour & minute')

                if (givenISODay < currentISODay) {

                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, hour & minute')

                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay, hour & minute')
                }

            }


        } else if (time) {
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month} ${time}`, 'YYYY-MM HH:mm').tz(timezone, true)

                if (givenISODay < currentISODay) {

                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, time, year && month')

                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay, time, year && month')
                }
            } else {

                meetingStartDateObject = dayjs(`${time}`, 'HH:mm').tz(timezone, true)

                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside isoWeekday, time')

                if (givenISODay < currentISODay) {

                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, isoWeekday, time, year && month')

                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay, isoWeekday, time, year && month')
                }
            }
        } else if (!hour && !minute && !time) {

            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)

                
                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month from isoDay')

                if (givenISODay < currentISODay) {

                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay year && month')
                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay year && month')
                }

            } else {

                meetingStartDateObject = dayjs().tz(timezone, true)

                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, hour & minute')

                if (givenISODay < currentISODay) {

                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, hour & minute')

                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay, hour & minute')
                }

            }
        }

    } else if (relativeTimeFromNow?.[0]) {
        let minuteChanged = false
        let hourChanged = false

        if ((relativeTimeChangeFromNow === 'add') || (relativeTimeChangeFromNow === null)) {
            // loop through all possible values
            let minute = 0
            let hour = 0
            let day = 0
            let week = 0
            let month = 0
            let year = 0

            for (const relativeTimeObject of relativeTimeFromNow) {

                if (relativeTimeObject?.unit === 'minute') {
                    if (relativeTimeObject?.value > 0) {
                        minute += relativeTimeObject?.value
                        minuteChanged = true
                    }
                } else if (relativeTimeObject?.unit === 'hour') {
                    if (relativeTimeObject?.value > 0) {
                        hour += relativeTimeObject?.value
                        hourChanged = true
                    }
                } else if (relativeTimeObject?.unit === 'day') {
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

            meetingStartDateObject = dayjs(currentTime, 'YYYY-MM-DD').tz(timezone, true)
                .add(minute, 'm')
                .add(hour, 'h')
                .add(day, 'd')
                .add(week, 'w')
                .add(month, 'M')
                .add(year, 'y')
            
            console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside relativeTime, add')

        } else if (relativeTimeChangeFromNow === 'subtract') {

            let minute = 0
            let hour = 0
            let day = 0
            let week = 0
            let month = 0
            let year = 0

            for (const relativeTimeObject of relativeTimeFromNow) {

                if (relativeTimeObject?.unit === 'minute') {
                    if (relativeTimeObject?.value > 0) {
                        minute += relativeTimeObject?.value
                        minuteChanged = true
                    }
                } else if (relativeTimeObject?.unit === 'hour') {
                    if (relativeTimeObject?.value > 0) {
                        hour += relativeTimeObject?.value
                        hourChanged = true
                    }
                } else if (relativeTimeObject?.unit === 'day') {
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

            meetingStartDateObject = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true)
                .subtract(minute, 'm')
                .subtract(hour, 'h')
                .subtract(day, 'd')
                .subtract(week, 'w')
                .subtract(month, 'M')
                .subtract(year, 'y')
            
            console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside relativeTime, subtract')
        }

        if ((!!hour) && (!!minute)) {
            
                if (year && month) {
                    const yearAndMonth = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                    meetingStartDateObject = meetingStartDateObject
                        .year(yearAndMonth.year())
                        .month(yearAndMonth.month())
                        .hour(hour)
                        .minute(minute)
                    
                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month')
                } else {
    
                    meetingStartDateObject = (meetingStartDateObject as Dayjs)
                    .hour(hour)
                    .minute(minute)
    
                }
            
            console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside relativeTime, hour, minute')

        } else if (time) {
            const temp = dayjs(time, 'HH:mm').tz(timezone, true)
            
                if (year && month) {
                    const yearAndMonth = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                    meetingStartDateObject = meetingStartDateObject
                        .year(yearAndMonth.year())
                        .month(yearAndMonth.month())
                        .hour(temp.hour())
                        .minute(temp.minute())
                    
                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month')
                } else {
    
                    meetingStartDateObject = (meetingStartDateObject as Dayjs)
                        .hour(temp.hour())
                        .minute(temp.minute())

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month')
    
                }
            
            console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside relativeTime, hour, minute')
        } else if (!hour && !minute && !time && !hourChanged && !minuteChanged) {
            
            if (year && month) {
                const yearAndMonth = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                meetingStartDateObject = meetingStartDateObject
                    .year(yearAndMonth.year())
                    .month(yearAndMonth.month())
                
                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month')
            } else {

                meetingStartDateObject = (meetingStartDateObject as Dayjs)

                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month')

            }
        }
    }

    console.log(meetingStartDateObject.format(), ' meetingStartDateObject final')

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

    let meetingStartDate = ''
    let meetingStartDateObject: Dayjs = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true)

    if (day) {

        if ((!!hour) && (!!minute)) {

            if (year && month) {
                const yearAndMonthAndDate = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true)
                meetingStartDateObject = meetingStartDateObject
                .year(yearAndMonthAndDate.year())
                .month(yearAndMonthAndDate.month())
                .date(yearAndMonthAndDate.date())
                .hour(hour)
                .minute(minute)
                
                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month')
            } else {

                const dateOfMonth = dayjs(day, 'DD').tz(timezone, true)
                meetingStartDateObject = meetingStartDateObject
                .date(dateOfMonth.date())
                .hour(hour)
                .minute(minute)

                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside DD')

            }


        } else if (time) {
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}-${day} ${time}`, 'YYYY-MM-DD HH:mm').tz(timezone, true)
                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside time, year && month')
            } else {

                meetingStartDateObject = dayjs(`${day} ${time}`, 'DD HH:mm').tz(timezone, true)

                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside time')

            }
        } else if (!time && !hour && !minute) {
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true)
                    .hour(0)
                    .minute(0)
                
                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month')
            } else {

                meetingStartDateObject = dayjs(day, 'DD').tz(timezone, true)
                    .hour(0)
                    .minute(0)

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside DD')

            }
        }
    } else if (isoWeekday) {

        const givenISODay = isoWeekday
        const currentISODay = getISODay(dayjs(currentTime).tz(timezone, true).toDate())

        if ((!!hour) && (!!minute)) {

            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                    .hour(hour)
                    .minute(minute)
                
                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month from isoDay')

                if (givenISODay < currentISODay) {

                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay year && month')
                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))
                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay year && month')
                }

            } else {

                meetingStartDateObject = dayjs().tz(timezone, true)
                    .hour(hour)
                    .minute(minute)

                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, hour & minute')

                if (givenISODay < currentISODay) {

                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, hour & minute')

                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay, hour & minute')
                }

            }


        } else if (time) {
            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month} ${time}`, 'YYYY-MM HH:mm').tz(timezone, true)

                if (givenISODay < currentISODay) {

                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, time, year && month')

                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay, time, year && month')
                }
            } else {

                meetingStartDateObject = dayjs(`${time}`, 'HH:mm').tz(timezone, true)

                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside isoWeekday, time')

                if (givenISODay < currentISODay) {

                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, isoWeekday, time, year && month')

                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay, isoWeekday, time, year && month')
                }
            }
        } else if (!hour && !minute && !time) {

            if (year && month) {
                meetingStartDateObject = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                    .hour(0)
                    .minute(0)
                
                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month from isoDay')

                if (givenISODay < currentISODay) {

                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay year && month')
                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay year && month')
                }

            } else {

                meetingStartDateObject = dayjs().tz(timezone, true)
                    .hour(0)
                    .minute(0)

                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, hour & minute')

                if (givenISODay < currentISODay) {

                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, hour & minute')

                } else {
                    meetingStartDateObject = dayjs(setISODay((meetingStartDateObject as Dayjs).toDate(), givenISODay))

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay, hour & minute')
                }

            }
        }

    } else if (relativeTimeFromNow?.[0]) {
        let minuteChanged = false
        let hourChanged = false

        if ((relativeTimeChangeFromNow === 'add') || (relativeTimeChangeFromNow === null)) {
            // loop through all possible values
            let minute = 0
            let hour = 0
            let day = 0
            let week = 0
            let month = 0
            let year = 0

            for (const relativeTimeObject of relativeTimeFromNow) {

                if (relativeTimeObject?.unit === 'minute') {
                    if (relativeTimeObject?.value > 0) {
                        minute += relativeTimeObject?.value
                        minuteChanged = true
                    }
                } else if (relativeTimeObject?.unit === 'hour') {
                    if (relativeTimeObject?.value > 0) {
                        hour += relativeTimeObject?.value
                        hourChanged = true
                    }
                } else if (relativeTimeObject?.unit === 'day') {
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

            meetingStartDateObject = dayjs(currentTime, 'YYYY-MM-DD').tz(timezone, true)
                .add(minute, 'm')
                .add(hour, 'h')
                .add(day, 'd')
                .add(week, 'w')
                .add(month, 'M')
                .add(year, 'y')
            
            console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside relativeTime, add')

        } else if (relativeTimeChangeFromNow === 'subtract') {

            let minute = 0
            let hour = 0
            let day = 0
            let week = 0
            let month = 0
            let year = 0

            for (const relativeTimeObject of relativeTimeFromNow) {

                if (relativeTimeObject?.unit === 'minute') {
                    if (relativeTimeObject?.value > 0) {
                        minute += relativeTimeObject?.value
                        minuteChanged = true
                    }
                } else if (relativeTimeObject?.unit === 'hour') {
                    if (relativeTimeObject?.value > 0) {
                        hour += relativeTimeObject?.value
                        hourChanged = true
                    }
                } else if (relativeTimeObject?.unit === 'day') {
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

            meetingStartDateObject = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true)
                .subtract(minute, 'm')
                .subtract(hour, 'h')
                .subtract(day, 'd')
                .subtract(week, 'w')
                .subtract(month, 'M')
                .subtract(year, 'y')
            
            console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside relativeTime, subtract')
        }

        if ((!!hour) && (!!minute)) {
            
                if (year && month) {
                    const yearAndMonth = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                    meetingStartDateObject = meetingStartDateObject
                        .year(yearAndMonth.year())
                        .month(yearAndMonth.month())
                        .hour(hour)
                        .minute(minute)
                    
                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month')
                } else {
    
                    meetingStartDateObject = (meetingStartDateObject as Dayjs)
                    .hour(hour)
                    .minute(minute)
    
                }
            
            console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside relativeTime, hour, minute')

        } else if (time) {
            const temp = dayjs(time, 'HH:mm').tz(timezone, true)
            
                if (year && month) {
                    const yearAndMonth = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                    meetingStartDateObject = meetingStartDateObject
                        .year(yearAndMonth.year())
                        .month(yearAndMonth.month())
                        .hour(temp.hour())
                        .minute(temp.minute())
                    
                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month')
                } else {
    
                    meetingStartDateObject = (meetingStartDateObject as Dayjs)
                        .hour(temp.hour())
                        .minute(temp.minute())

                    console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month')
    
                }
            
            console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside relativeTime, hour, minute')
        } else if (!hour && !minute && !time && !hourChanged && !minuteChanged) {
            
            if (year && month) {
                const yearAndMonth = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                meetingStartDateObject = meetingStartDateObject
                    .year(yearAndMonth.year())
                    .month(yearAndMonth.month())
                    .hour(0)
                    .minute(0)
                
                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month')
            } else {

                meetingStartDateObject = (meetingStartDateObject as Dayjs)
                    .hour(0)
                    .minute(0)

                console.log(meetingStartDateObject.format(), ' meetingStartDateObject inside year && month')

            }
        }
    }

    console.log(meetingStartDateObject.format(), ' meetingStartDateObject final')

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

    let meetingEndDate = ''
    let meetingEndDateObject: Dayjs = dayjs(currentTime, 'YYYY-MM-DDTHH:mm').tz(timezone, true)

    if (day) {

        if ((!!hour) && (!!minute)) {

            if (year && month) {
                const yearAndMonthAndDate = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true)
                meetingEndDateObject = meetingEndDateObject
                    .year(yearAndMonthAndDate.year())
                    .month(yearAndMonthAndDate.month())
                    .date(yearAndMonthAndDate.date())
                    .hour(hour)
                    .minute(minute)
                
                console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside year && month')
            } else {
                
                const dateOfMonth = dayjs(day, 'DD').tz(timezone, true)
                meetingEndDateObject = meetingEndDateObject
                    .date(dateOfMonth.date())
                    .hour(hour)
                    .minute(minute)

                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside DD')

            }

        } else if (time) {
            if (year && month) {
                meetingEndDateObject = dayjs(`${year}-${month}-${day} ${time}`, 'YYYY-MM-DD HH:mm').tz(timezone, true)
                console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside time, year && month')
            } else {

                meetingEndDateObject = dayjs(`${day} ${time}`, 'DD HH:mm').tz(timezone, true)

                console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside time')

            }
        } else if (!time && !hour && !minute) {
            if (year && month) {
                meetingEndDateObject = dayjs(`${year}-${month}-${day}`, 'YYYY-MM-DD').tz(timezone, true)
                    .hour(23)
                    .minute(59)
                
                console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside year && month')
            } else {

                meetingEndDateObject = dayjs(day, 'DD').tz(timezone, true)
                    .hour(23)
                    .minute(59)

                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside DD')

            }
        }
    } else if (isoWeekday) {

        const givenISODay = isoWeekday
        const currentISODay = getISODay(dayjs(currentTime).tz(timezone, true).toDate())

        if ((!!hour) && (!!minute)) {

            if (year && month) {
                meetingEndDateObject = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                    .hour(hour)
                    .minute(minute)
                
                console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside year && month from isoDay')

                if (givenISODay < currentISODay) {

                    meetingEndDateObject = dayjs(setISODay((meetingEndDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay year && month')
                } else {
                    meetingEndDateObject = dayjs(setISODay((meetingEndDateObject as Dayjs).toDate(), givenISODay))
                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay year && month')
                }

            } else {

                meetingEndDateObject = dayjs().tz(timezone, true)
                    .hour(hour)
                    .minute(minute)

                console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, hour & minute')

                if (givenISODay < currentISODay) {

                    meetingEndDateObject = dayjs(setISODay((meetingEndDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, hour & minute')

                } else {
                    meetingEndDateObject = dayjs(setISODay((meetingEndDateObject as Dayjs).toDate(), givenISODay))

                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay, hour & minute')
                }

            }

        } else if (time) {
            if (year && month) {
                meetingEndDateObject = dayjs(`${year}-${month} ${time}`, 'YYYY-MM HH:mm').tz(timezone, true)

                if (givenISODay < currentISODay) {

                    meetingEndDateObject = dayjs(setISODay((meetingEndDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, time, year && month')

                } else {
                    meetingEndDateObject = dayjs(setISODay((meetingEndDateObject as Dayjs).toDate(), givenISODay))

                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay, time, year && month')
                }
            } else {

                meetingEndDateObject = dayjs(`${time}`, 'HH:mm').tz(timezone, true)

                console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside isoWeekday, time')

                if (givenISODay < currentISODay) {

                    meetingEndDateObject = dayjs(setISODay((meetingEndDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, isoWeekday, time, year && month')

                } else {
                    meetingEndDateObject = dayjs(setISODay((meetingEndDateObject as Dayjs).toDate(), givenISODay))

                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay, isoWeekday, time, year && month')
                }
            }
        } else if (!hour && !minute && !time) {

            if (year && month) {
                meetingEndDateObject = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                    .hour(23)
                    .minute(59)
                
                console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside year && month from isoDay')

                if (givenISODay < currentISODay) {

                    meetingEndDateObject = dayjs(setISODay((meetingEndDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay year && month')
                } else {
                    meetingEndDateObject = dayjs(setISODay((meetingEndDateObject as Dayjs).toDate(), givenISODay))

                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay year && month')
                }

            } else {

                meetingEndDateObject = dayjs().tz(timezone, true)
                    .hour(23)
                    .minute(59)

                console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, hour & minute')

                if (givenISODay < currentISODay) {

                    meetingEndDateObject = dayjs(setISODay((meetingEndDateObject as Dayjs).add(1, 'w').toDate(), givenISODay))

                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside givenISODay < currentISODay, hour & minute')

                } else {
                    meetingEndDateObject = dayjs(setISODay((meetingEndDateObject as Dayjs).toDate(), givenISODay))

                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside givenISODay > currentISODay, hour & minute')
                }

            }
        }

    } 
    
    if (relativeTimeFromNow?.[0]) {
        let minuteChanged = false
        let hourChanged = false

        if ((relativeTimeChangeFromNow === 'add') || (relativeTimeChangeFromNow === null)) {
            // loop through all possible values
            let minute = 0
            let hour = 0
            let day = 0
            let week = 0
            let month = 0
            let year = 0

            for (const relativeTimeObject of relativeTimeFromNow) {

                if (relativeTimeObject?.unit === 'minute') {
                    if (relativeTimeObject?.value > 0) {
                        minute += relativeTimeObject?.value
                        minuteChanged = true
                    }
                } else if (relativeTimeObject?.unit === 'hour') {
                    if (relativeTimeObject?.value > 0) {
                        hour += relativeTimeObject?.value
                        hourChanged = true
                    }
                } else if (relativeTimeObject?.unit === 'day') {
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

            meetingEndDateObject = meetingEndDateObject
                .add(minute, 'm')
                .add(hour, 'h')
                .add(day, 'd')
                .add(week, 'w')
                .add(month, 'M')
                .add(year, 'y')
            
            console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside relativeTime, add')

        } else if (relativeTimeChangeFromNow === 'subtract') {

            let minute = 0
            let hour = 0
            let day = 0
            let week = 0
            let month = 0
            let year = 0

            for (const relativeTimeObject of relativeTimeFromNow) {

                if (relativeTimeObject?.unit === 'minute') {
                    if (relativeTimeObject?.value > 0) {
                        minute += relativeTimeObject?.value
                        minuteChanged = true
                    }
                } else if (relativeTimeObject?.unit === 'hour') {
                    if (relativeTimeObject?.value > 0) {
                        hour += relativeTimeObject?.value
                        hourChanged = true
                    }
                } else if (relativeTimeObject?.unit === 'day') {
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

            meetingEndDateObject = meetingEndDateObject
                .subtract(minute, 'm')
                .subtract(hour, 'h')
                .subtract(day, 'd')
                .subtract(week, 'w')
                .subtract(month, 'M')
                .subtract(year, 'y')
            
            console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside relativeTime, subtract')
        }

        if ((!!hour) && (!!minute)) {
            
            console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside relativeTime, hour, minute')

            if (year && month) {
                const yearAndMonth = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                meetingEndDateObject = meetingEndDateObject
                    .year(yearAndMonth.year())
                    .month(yearAndMonth.month())
                    .hour(hour)
                    .minute(minute)
                
                console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside year && month')
            } else {

                meetingEndDateObject = (meetingEndDateObject as Dayjs)
                .hour(hour)
                .minute(minute)

            }

        } else if (time) {
            const temp = dayjs(time, 'HH:mm').tz(timezone, true)
            
                if (year && month) {
                    const yearAndMonth = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                    meetingEndDateObject = meetingEndDateObject
                        .year(yearAndMonth.year())
                        .month(yearAndMonth.month())
                        .hour(temp.hour())
                        .minute(temp.minute())
                    
                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside year && month')
                } else {
    
                    meetingEndDateObject = (meetingEndDateObject as Dayjs)
                        .hour(temp.hour())
                        .minute(temp.minute())

                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside year && month')
    
                }
            
            console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside relativeTime, hour, minute')
        } else if (!hour && !minute && !time && !hourChanged && !minuteChanged) {
            
                if (year && month) {
                    const yearAndMonth = dayjs(`${year}-${month}`, 'YYYY-MM').tz(timezone, true)
                    meetingEndDateObject = meetingEndDateObject
                        .year(yearAndMonth.year())
                        .month(yearAndMonth.month())
                        .hour(23)
                        .minute(59)
                    
                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside year && month')
                } else {
    
                    meetingEndDateObject = (meetingEndDateObject as Dayjs)
                        .hour(23)
                        .minute(59)

                    console.log(meetingEndDateObject.format(), ' meetingStartDateObject inside year && month')
    
                }
        }
    }

    console.log(meetingEndDateObject.format(), ' meetingStartDateObject final')

    meetingEndDate = (meetingEndDateObject as Dayjs).format()

    return meetingEndDate
}

export const getGlobalCalendar = async (
    userId: string,
) => {
    try {
        const operationName = 'getGlobalCalendar'
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
    `

        const res: { data: { Calendar: CalendarType[] } } = await got.post(
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
                    },
                },
            },
        ).json()

        return res.data.Calendar?.[0]
    } catch (e) {
        console.log(e, ' unable to get global calendar')
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
    } catch (e) {
        console.log(e, ' unable to get calendar integration')
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
    } catch (e) {
        console.log(e, ' unable to get calendar integration')
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
        console.log(e, ' unable to get zoom integration')
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
    } catch (e) {
        console.log(e, ' unable to update calendar integration')
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
        console.log(e, ' unable to update zoom integration')
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
        }).then(({ data }) => Promise.resolve(data))
    } catch (e) {
        console.log(e, ' unable to refresh zoom token')
    }
}
export const getZoomAPIToken = async (
    userId: string,
) => {
    let integrationId = ''
    try {
        console.log('getZoomAPIToken called')
        const { id, token, expiresAt, refreshToken } = await getZoomIntegration(userId)
        if (!refreshToken) {
            console.log('zoom not active, no refresh token')
            return
        }

        integrationId = id
        console.log(id, token, expiresAt, refreshToken, ' id, token, expiresAt, refreshToken')
        if (dayjs().isAfter(dayjs(expiresAt)) || !token) {
            const res = await refreshZoomToken(refreshToken)
            console.log(res, ' res from refreshZoomToken')
            await updateZoomIntegration(id, res.access_token, res.expires_in)
            return res.access_token
        }

        return token


    } catch (e) {
        console.log(e, ' unable to get zoom api token')
        await updateCalendarIntegration(integrationId, null, null, false)
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
        }).json()
        console.log(response, ' this is response in deleteRemindersWithIds')

    } catch (e) {
        console.log(e, ' deleteRemindersWithIds')
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
            console.log(' starttime is in the past')
            throw new Error('starttime is in the past')
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

        await got.patch(
            `${zoomBaseUrl}/meetings/${meetingId}`,
            {
                json: reqBody,
                headers: {
                    Authorization: `Bearer ${zoomToken}`,
                    ContentType: 'application/json',
                }
            }
        ).json()

        console.log(meetingId, 'successfully patched zoom meeting starting date')
    } catch (e) {
        console.log(e, ' unable to update zoom meeting')
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
            console.log(' starttime is in the past')
            throw new Error('starttime is in the past')
        }

        console.log(dayjs(startDate?.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DDTHH:mm:ss'),
            timezone,
            agenda,
            duration, ` dayjs(startDate?.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DDTHH:mm:ss'),
            timezone,
            agenda,
            duration, createZoomMeeting called`)

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

        console.log(reqBody, ' reqBody inside createZoomMeeting')

        const res: ZoomMeetingObjectType = await got.post(
            `${zoomBaseUrl}/users/me/meetings`,
            {
                json: reqBody,
                headers: {
                    Authorization: `Bearer ${zoomToken}`,
                    ContentType: 'application/json',
                }
            }
        ).json()

        console.log(res, ' res inside createZoomMeeting')

        return res
    } catch (e) {
        console.log(e, ' unable to create zoom meeting')
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
    try {
        console.log('refreshGoogleToken called', refreshToken)
        console.log('clientType', clientType)
        console.log('googleClientIdIos', googleClientIdIos)
        switch (clientType) {
            case 'ios':
                return got.post(
                    googleTokenUrl,
                    {
                        form: {
                            grant_type: 'refresh_token',
                            refresh_token: refreshToken,
                            client_id: googleClientIdIos,
                        },
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                    },
                ).json()
            case 'android':
                return got.post(
                    googleTokenUrl,
                    {
                        form: {
                            grant_type: 'refresh_token',
                            refresh_token: refreshToken,
                            client_id: googleClientIdAndroid,
                        },
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                    },
                ).json()
            case 'web':
                return got.post(
                    googleTokenUrl,
                    {
                        form: {
                            grant_type: 'refresh_token',
                            refresh_token: refreshToken,
                            client_id: googleClientIdWeb,
                            client_secret: googleClientSecretWeb,
                        },
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                    },
                ).json()
            case 'atomic-web':
                return got.post(
                    googleTokenUrl,
                    {
                        form: {
                            grant_type: 'refresh_token',
                            refresh_token: refreshToken,
                            client_id: googleClientIdAtomicWeb,
                            client_secret: googleClientSecretAtomicWeb,
                        },
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                    },
                ).json()
        }

        /*  
        {
          "access_token": "1/fFAGRNJru1FTz70BzhT3Zg",
          "expires_in": 3920, // add seconds to now
          "scope": "https://www.googleapis.com/auth/drive.metadata.readonly",
          "token_type": "Bearer"
        }
        */
    } catch (e) {
        console.log(e, ' unable to refresh google token')
    }
}

export const getGoogleAPIToken = async (
    userId: string,
    name: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web',
) => {
    let integrationId = ''
    try {
        const { id, token, expiresAt, refreshToken } = await getCalendarIntegrationByName(userId, name)
        integrationId = id
        console.log(id, token, expiresAt, refreshToken, ' id, token, expiresAt, refreshToken')
        if (dayjs().isAfter(dayjs(expiresAt)) || !token) {
            const res = await refreshGoogleToken(refreshToken, clientType)
            console.log(res, ' res from refreshGoogleToken')
            await updateCalendarIntegration(id, res.access_token, res.expires_in)
            return res.access_token
        }
        return token
    } catch (e) {
        console.log(e, ' unable to get api token')
        await updateCalendarIntegration(integrationId, null, null, false)
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
): Promise<GoogleResType> => {
    try {
        console.log(generatedId, conferenceDataVersion, conferenceData, ' generatedId, conferenceDataVersion, conferenceData inside createGoogleEvent')
        // get token =
        const token = await getGoogleAPIToken(userId, googleCalendarName, clientType)

        const googleCalendar = google.calendar({
            version: 'v3',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        })

        // create request body
        let data: any = {}

        if (endDateTime && timezone && !endDate) {

            const end = {
                dateTime: endDateTime,
                timeZone: timezone,
            }

            data.end = end
        }

        if (endDate && timezone && !endDateTime) {
            const end = {
                date: dayjs(endDate.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD'),
                timeZone: timezone,
            }

            data.end = end
        }

        if (startDate && timezone && !startDateTime) {
            const start = {
                date: dayjs(startDate.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD'),
                timeZone: timezone,
            }
            data.start = start
        }

        if (startDateTime && timezone && !startDate) {
            const start = {
                dateTime: startDateTime,
                timeZone: timezone,
            }
            data.start = start
        }

        if (originalStartDate && timezone && !originalStartDateTime) {
            const originalStartTime = {
                date: dayjs(originalStartDate?.slice(0, 19)).format('YYYY-MM-DD'),
                timeZone: timezone,
            }
            data.originalStartTime = originalStartTime
        }

        if (originalStartDateTime && timezone && !originalStartDate) {
            const originalStartTime = {
                dateTime: originalStartDateTime,
                timeZone: timezone,
            }
            data.originalStartTime = originalStartTime
        }

        if (anyoneCanAddSelf) {
            data = { ...data, anyoneCanAddSelf }
        }

        if (attendees?.[0]?.email) {
            data = { ...data, attendees }
        }

        if (conferenceData?.createRequest) {
            data = {
                ...data,
                conferenceData: {
                    createRequest: {
                        conferenceSolutionKey: {
                            type: conferenceData.type
                        },
                        requestId: conferenceData?.requestId || uuid(),
                    }
                }
            }
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
            }
        }

        if (description?.length > 0) {
            data = { ...data, description }
        }

        if (extendedProperties?.private || extendedProperties?.shared) {
            data = { ...data, extendedProperties }
        }

        if (guestsCanInviteOthers) {
            data = { ...data, guestsCanInviteOthers }
        }

        if (guestsCanModify) {
            data = { ...data, guestsCanModify }
        }

        if (guestsCanSeeOtherGuests) {
            data = { ...data, guestsCanSeeOtherGuests }
        }

        if (locked) {
            data = { ...data, locked }
        }

        if (privateCopy) {
            data = { ...data, privateCopy }
        }

        if (recurrence?.[0]) {
            data = { ...data, recurrence }
        }

        if ((reminders?.overrides?.length > 0) || (reminders?.useDefault)) {
            data = { ...data, reminders }
        }

        if (source?.title || source?.url) {
            data = { ...data, source }
        }

        if (attachments?.[0]?.fileId) {
            data = { ...data, attachments }
        }

        if (eventType?.length > 0) {
            data = { ...data, eventType }
        }

        if (status) {
            data = { ...data, status }
        }

        if (transparency) {
            data = { ...data, transparency }
        }

        if (visibility) {
            data = { ...data, visibility }
        }

        if (iCalUID?.length > 0) {
            data = { ...data, iCalUID }
        }

        if (attendeesOmitted) {
            data = { ...data, attendeesOmitted }
        }

        if (hangoutLink?.length > 0) {
            data = { ...data, hangoutLink }
        }

        if (summary?.length > 0) {
            data = { ...data, summary }
        }

        if (location?.length > 0) {
            data = { ...data, location }
        }

        if (colorId) {
            data.colorId = colorId
        }

        console.log(data, ' data inside create google event')

        const res = await googleCalendar.events.insert({
            // Calendar identifier. To retrieve calendar IDs call the calendarList.list method. If you want to access the primary calendar of the currently logged in user, use the "primary" keyword.
            calendarId,
            // Version number of conference data supported by the API client. Version 0 assumes no conference data support and ignores conference data in the event's body. Version 1 enables support for copying of ConferenceData as well as for creating new conferences using the createRequest field of conferenceData. The default is 0.
            conferenceDataVersion,
            // The maximum number of attendees to include in the response. If there are more than the specified number of attendees, only the participant is returned. Optional.
            maxAttendees,
            // Whether to send notifications about the creation of the new event. Note that some emails might still be sent. The default is false.
            sendUpdates,

            // Request body metadata
            requestBody: data,
        })


        console.log(res.data)

        console.log(res?.data, ' res?.data from googleCreateEvent')
        return { id: `${res?.data?.id}#${calendarId}`, googleEventId: res?.data?.id, generatedId, calendarId, generatedEventId: generatedId?.split('#')[0] }
    } catch (e) {
        console.log(e, ' createGoogleEvent')
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
            console.log(eventId, endDateTime, timezone, ' eventId, endDateTime, timezone prior')
            const end = {
                dateTime: endDateTime,
                timezone
            }
            requestBody.end = end

            console.log(eventId, end.dateTime, end.timezone, ' eventId, endDateTime, timezone after')
        }

        if (startDate && timezone && !startDateTime) {
            const start = {
                date: dayjs(startDateTime.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD'),
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

        if (startDateTime && timezone && !startDate) {
            console.log(eventId, startDateTime, timezone, ' eventId, startDateTime, timezone prior')
            const start = {
                dateTime: startDateTime,
                timezone,
            }
            requestBody.start = start

            console.log(eventId, start.dateTime, start.timezone, ' eventId, startDateTime, timezone after')
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
        console.log(eventId, requestBody, ' eventId, requestBody inside googlePatchEvent')
        const res = await googleCalendar.events.patch(variables)
        console.log(eventId, res.data, ' eventId, results from googlePatchEvent')
    } catch (e) {
        console.log(e, ' unable to patch google event')
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
        ).json()
        console.log(res, ' res from getEventFromPrimaryKey')
        return res?.data?.Event_by_pk
    } catch (e) {
        console.log(e, ' getEventFromPrimaryKey')
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
        ).json()
        console.log(res, ' res from getTaskGivenId')
        return res?.data?.Task_by_pk
    } catch (e) {
        console.log(e, ' getTaskGivenId')
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
        }).json()

        console.log(response?.data?.insert_Attendee?.returning, ' this is response in insertAttendees')
        response?.data?.insert_Attendee?.returning.forEach(r => console.log(r, ' response in insertAttendees'))

    } catch (e) {
        console.log(e, ' unable to insert Attendees for new event')
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
        eventIds.forEach(e => console.log(e, ' eventIds inside DeleteAttendeesWithEventIds'))
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
        }).json()
        console.log(response, ' this is response in deleteAttendeesWithIds')

    } catch (e) {
        console.log(e, ' deleteAttendeesWithIds')
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
            console.log('no email provided')
            return
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
        }).json()

        console.log(response?.data?.Contact?.[0], ' this is response in findContactByEmailGivenUserId')
        return response?.data?.Contact?.[0]

    } catch (e) {
        console.log(e, ' unable to insert Attendees for new event')
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
        }).json()

        console.log(response?.data?.Conference_by_pk, ' this is response in getConferenceGivenId')
        return response?.data?.Conference_by_pk

    } catch (e) {
        console.log(e, ' unable to insert Attendees for new event')
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
        }).json()

        console.log(response?.data?.delete_Conference_by_pk, ' this is response in deleteConferenceGivenId')
        return response?.data?.delete_Conference_by_pk

    } catch (e) {
        console.log(e, ' unable to delete Attendees for new event')
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

        if (stringifiedObject) {
            await got.delete(
                `${zoomBaseUrl}/meetings/` + meetingId + '?' + stringifiedObject,
                {
                    headers: {
                        Authorization: `Bearer ${zoomToken}`,
                        ContentType: 'application/json',
                    }
                }
            )
        } else {
            await got.delete(
                `${zoomBaseUrl}/meetings/` + meetingId,
                {
                    headers: {
                        Authorization: `Bearer ${zoomToken}`,
                        ContentType: 'application/json',
                    }
                }
            )
        }


        console.log(meetingId, 'successfully deleted meeting')
    } catch (e) {
        console.log(e, ' unable to delete zoom meeting')
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
        }).json()

        console.log(response?.data?.delete_Event_by_pk, ' this is response in deleteEventGivenId')
        return response?.data?.delete_Event_by_pk

    } catch (e) {
        console.log(e, ' unable to deleteEventGivenId for new event')
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


        console.log(res, ' result after delete event')
    } catch (e) {
        console.log(e, ' unable to delete google event')
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
        console.log('recurringEndDate, interval or frequency missing')
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
        }).json()

        console.log(response?.data?.insert_Meeting_Assist_one, ' this is response in upsertMeetingAssistOne')
        return response?.data?.insert_Meeting_Assist_one

    } catch (e) {
        console.log(e, ' unable to upsertMeetingAssistOne for new event')
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
        }).json()

        console.log(response?.data?.User_Contact_Info, ' this is response?.data?.User_Contact_Info')
        return response?.data?.User_Contact_Info

    } catch (e) {
        console.log(e, ' unable to listUserContactInfosGivenUserId for new event')
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
        }).json()

        console.log(response?.data?.User_Contact_Info, ' this is response in getContactInfosGivenIds')
        return response?.data?.User_Contact_Info

    } catch (e) {
        console.log(e, ' unable to getContactInfosGivenIds for new event')
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
        }).json()

        console.log(response?.data?.Contact, ' this is response in getContactByNameWithUserId')
        return response?.data?.Contact?.[0]

    } catch (e) {
        console.log(e, ' unable to getContactByNameWithUserId for new event')
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
        }).json()

        console.log(response?.data?.insert_Meeting_Assist_Attendee_one, ' this is response in insertMeetingAssistAttendee')
        return response?.data?.insert_Meeting_Assist_Attendee_one

    } catch (e) {
        console.log(e, ' unable to upsertMeetingAssistOne for new event')
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
        console.log(e, ' unable to upsertMeetingAssistOne for new event')
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
        }).json()

        console.log(response?.data?.insert_Meeting_Assist_Invite, ' this is response in upsertMeetingAssistInviteMany')
        return response?.data?.insert_Meeting_Assist_Invite

    } catch (e) {
        console.log(e, ' unable to upsertMeetingAssistInviteMany for new event')
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
        }).json()

        console.log(response?.data?.update_User_by_pk, ' this is response in updateUserNameGivenId')
        return response?.data?.update_User_by_pk

    } catch (e) {
        console.log(e, ' unable to upsertMeetingAssistInviteMany for new event')
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
        }).json()

        console.log(response?.data?.User_by_pk, ' this is response in getUserGivenId')
        return response?.data?.User_by_pk

    } catch (e) {
        console.log(e, ' unable to getUserGivenId for new event')
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
        });
        console.log(completion.choices[0]?.message?.content, ' response from openaiapi');

        return completion?.choices?.[0]?.message?.content
    } catch (error) {
        if (error.response) {
            console.log(error.response.status, ' openai error status');
            console.log(error.response.data, ' openai error data');
        } else {
            console.log(error.message, ' openai error message');
        }
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
    try {
        // assistant
        const completion = await openai.chat.completions.create({
            model,
            messages: messageHistory.concat([
                { role: 'system' as ChatGPTRoleType, content: prompt },
                exampleInput && { role: 'user' as ChatGPTRoleType, content: exampleInput },
                exampleOutput && { role: 'assistant' as ChatGPTRoleType, content: exampleOutput },
                { role: 'user' as ChatGPTRoleType, content: userData }
            ])
                ?.filter(m => !!m),
        });
        console.log(completion.choices[0]?.message?.content, ' response from openaiapi');

        return { totalTokenCount: completion?.usage?.total_tokens, response: completion?.choices?.[0]?.message?.content }
    } catch (error) {
        if (error.response) {
            console.log(error.response.status, ' openai error status');
            console.log(error.response.data, ' openai error data');
        } else {
            console.log(error.message, ' openai error message');
        }
    }
}

export const callOpenAI = async (
    openai: OpenAI,
    prompt: string,
    model: 'gpt-3.5-turbo' | 'gpt-3.5-turbo-16k' | 'gpt-4' = 'gpt-3.5-turbo',
    userData: string,
    exampleInput?: string,
    exampleOutput?: string,
) => {
    try {
        // assistant
        const completion = await openai.chat.completions.create({
            model,
            messages: [
                { role: 'system' as ChatGPTRoleType, content: prompt },
                exampleInput && { role: 'user' as ChatGPTRoleType, content: exampleInput },
                exampleOutput && { role: 'assistant' as ChatGPTRoleType, content: exampleOutput },
                { role: 'user' as ChatGPTRoleType, content: userData }
            ]?.filter(m => !!m),
        });
        console.log(completion.choices[0]?.message?.content, ' response from openaiapi');

        return completion?.choices?.[0]?.message?.content
    } catch (error) {
        if (error.response) {
            console.log(error.response.status, ' openai error status');
            console.log(error.response.data, ' openai error data');
        } else {
            console.log(error.message, ' openai error message');
        }
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
        ).json()

        console.log(res, ' res from listEventsforUser')
        return res?.data?.Event
    } catch (e) {
        console.log(e, ' listEventsForUser')
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
        console.log(e, ' unable to extract attritubes needed')
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
        console.log(userWorkTimes, ' userWorkTimes')
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
        console.log(e, ' unable to generate queryDate from user input')
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
        console.log(userWorkTimes, ' userWorkTimes')
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
        console.log(e, ' unable to generate queryDate from user input')
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
        console.log(dateTimeStartIndex, ' dateTimeStartIndex')
        const dateTimeEndIndex = openAIDateTime.lastIndexOf('}')
        console.log(dateTimeEndIndex, ' dateTimeEndIndex')
        const dateTimeJSONString = openAIDateTime.slice(dateTimeStartIndex, dateTimeEndIndex + 1)
        const dateTime: DateTimeJSONType = JSON.parse(dateTimeJSONString)

        return dateTime
    } catch (e) {
        console.log(e, ' unable to generateDateTime')
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
        console.log(dateTimeStartIndex, ' dateTimeStartIndex')
        const dateTimeEndIndex = openAIDateTime.lastIndexOf('}')
        console.log(dateTimeEndIndex, ' dateTimeEndIndex')
        const dateTimeJSONString = openAIDateTime.slice(dateTimeStartIndex, dateTimeEndIndex + 1)
        const dateTime: DateTimeJSONType = JSON.parse(dateTimeJSONString)

        return dateTime
    } catch (e) {
        console.log(e, ' unable to generateDateTime')
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
        console.log(e, ' unable to generate assistant message from api response')
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
        console.log(e, ' unable to generate user request for missing fields')
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
        console.log(e, ' unable to generateJSONData from user input')
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
        console.log(e, ' unable to generateJSONData from user input')
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
        console.log(e, ' unable to generate work schedule')
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
        console.log(e, ' unable to find an empty slot')
    }
}


