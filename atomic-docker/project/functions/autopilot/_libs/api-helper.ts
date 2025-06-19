import got from "got"
import { getISODay } from 'date-fns'
import dayjs from 'dayjs'
import isoWeek from 'dayjs/plugin/isoWeek'
import duration from 'dayjs/plugin/duration'
import isBetween from 'dayjs/plugin/isBetween'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'
import _ from "lodash"

import { AutopilotType, ScheduleAssistWithMeetingQueueBodyType,UserPreferenceType, AutopilotApiResponse, SkillError } from "./types" // Added AutopilotApiResponse, SkillError
import { authApiToken, featuresApplyAdminUrl, hasuraAdminSecret, hasuraGraphUrl, hasuraMetadataUrl, onScheduledTriggerDailyFeaturesApplyWebhookProdAdminUrl, onScheduledTriggerDailyScheduleAssistWebhookProdAdminUrl, scheduleAssistUrl } from "./constants"

dayjs.extend(isoWeek)
dayjs.extend(duration)
dayjs.extend(isBetween)
dayjs.extend(timezone)
dayjs.extend(utc)

function getRandomIntInclusive(min, max) {
    min = Math.ceil(min);
    max = Math.floor(max);
    return Math.floor(Math.random() * (max - min + 1) + min); // The maximum is inclusive and the minimum is inclusive
}


export const triggerFeaturesApplyUrl = async (
    body: ScheduleAssistWithMeetingQueueBodyType,
): Promise<AutopilotApiResponse<{ success: boolean, details?: any }>> => {
    if (!body || !body.userId) { // Basic validation
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Request body with userId is required.' } };
    }
    try {
        const url = featuresApplyAdminUrl;
        const res = await got.post( url, {
            headers: {
                'Authorization': `Basic ${Buffer.from(`admin:${authApiToken}`).toString('base64')}`,
                'content-type': 'application/json',
            },
            json: body,
        }).json();
        console.log(res, ' successfully called featuresApplyAdminUrl');
        return { ok: true, data: { success: true, details: res } };
    } catch (e: any) {
        console.error('Error triggering features apply url:', e);
        const errorDetails = e.response?.body || e.message || e;
        return { ok: false, error: { code: 'EXTERNAL_API_ERROR', message: `Failed to trigger features apply URL: ${e.message}`, details: errorDetails } };
    }
}

export const triggerScheduleAssistUrl = async (
    body: ScheduleAssistWithMeetingQueueBodyType,
): Promise<AutopilotApiResponse<{ success: boolean, details?: any }>> => {
    if (!body || !body.userId) { // Basic validation
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Request body with userId is required.' } };
    }
    try {
        const url = scheduleAssistUrl;
        const res = await got.post( url, {
            headers: {
                'Authorization': `Basic ${Buffer.from(`admin:${authApiToken}`).toString('base64')}`,
                'content-type': 'application/json',
            },
            json: body,
        }).json();
        console.log(res, ' successfully called scheduleAssistUrl');  // Corrected log
        return { ok: true, data: { success: true, details: res } };
    } catch (e: any) {
        console.error('Error triggering schedule assist url:', e);
        const errorDetails = e.response?.body || e.message || e;
        return { ok: false, error: { code: 'EXTERNAL_API_ERROR', message: `Failed to trigger schedule assist URL: ${e.message}`, details: errorDetails } };
    }
}

export const getUserPreferences = async (userId: string): Promise<AutopilotApiResponse<UserPreferenceType | null>> => {
    if (!userId) {
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'User ID is required for getUserPreferences.'}};
    }
    try {
        const operationName = 'getUserPreferences'
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
  `
        const res: { data: { User_Preference: UserPreferenceType[] } } = await got.post(
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
        return { ok: true, data: res?.data?.User_Preference?.[0] || null };
    } catch (e: any) {
        console.error('Error getting user preferences:', e);
        const errorDetails = e.response?.body || e.message || e;
        return { ok: false, error: { code: 'HASURA_ERROR', message: `Failed to get user preferences: ${e.message}`, details: errorDetails } };
    }
}

export const createDailyFeaturesApplyEventTrigger = async (
    autopilot: AutopilotType,
    body: ScheduleAssistWithMeetingQueueBodyType,
): Promise<AutopilotApiResponse<string | null>> => {
    if (!autopilot || !body || !autopilot.scheduleAt) { // Basic validation
         return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Autopilot data, body, and scheduleAt are required.' } };
    }
    try {
        const res: {
            message: string, // Typically "success"
            event_id: string,
        } = await got.post(hasuraMetadataUrl, { // This is a Hasura Metadata API call
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                // 'X-Hasura-Role': 'admin', // Not typically needed for metadata calls with admin secret
                'content-type': 'application/json'
            },
            json: {
                type: 'create_scheduled_event',
                args: {
                    webhook: onScheduledTriggerDailyFeaturesApplyWebhookProdAdminUrl,
                    schedule_at: dayjs.utc(autopilot.scheduleAt).format(), // Ensure autopilot is not null
                    payload: { autopilot, body },
                    headers: [
                        { name: 'Authorization', value: `Basic ${Buffer.from(`admin:${authApiToken}`).toString('base64')}` },
                        { name: 'Content-Type', value: 'application/json' }
                    ],
                    retry_conf: { // Example retry configuration
                        num_retries: 3,
                        retry_interval_seconds: 10,
                        timeout_seconds: 60,
                    },
                    comment: `Daily features apply trigger for autopilot ${autopilot.id}`
                }
            }
        }).json();

        if (res && res.message === "success" && res.event_id) {
            console.log(`Successfully created scheduled event trigger: ${res.event_id}`);
            return { ok: true, data: res.event_id };
        } else {
            console.error('Failed to create Hasura scheduled event, response was not success or event_id missing:', res);
            return { ok: false, error: { code: 'HASURA_METADATA_ERROR', message: 'Failed to create Hasura scheduled event.', details: res }};
        }
    } catch (e: any) {
        console.error('Error creating Hasura scheduled event trigger:', e);
        const errorDetails = e.response?.body || e.message || e;
        return { ok: false, error: { code: 'HASURA_METADATA_ERROR', message: `Error creating Hasura scheduled event: ${e.message}`, details: errorDetails } };
    }
}

export const upsertAutopilotOne = async (
    autopilot: AutopilotType
): Promise<AutopilotApiResponse<AutopilotType | null>> => {
    if (!autopilot || !autopilot.id || !autopilot.userId) { // Basic validation
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Autopilot object with id and userId is required.' } };
    }
    try {
        const operationName = 'UpsertAutopilotOne'
        const query = `
            mutation UpsertAutopilotOne($autopilot: Autopilot_insert_input!) {
                insert_Autopilot_one(object: $autopilot, on_conflict: {constraint: Autopilot_pkey, update_columns: [
                payload,
                scheduleAt,
                timezone,
                updatedAt,
                ]}) {
                createdDate
                id
                payload
                scheduleAt
                timezone
                updatedAt
                userId
                }
            }
          `

        const variables = {
            autopilot,
        }

        const res: { data: { insert_Autopilot_one: AutopilotType } } = await got.post(
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
                    variables,
                },
            },
        ).json()

        console.log(res, ' successfully upserted autopilot one');
        return { ok: true, data: res?.data?.insert_Autopilot_one || null };
    } catch (e: any) {
        console.error('Error upserting autopilot one:', e);
        const errorDetails = e.response?.body || e.message || e;
        return { ok: false, error: { code: 'HASURA_ERROR', message: `Failed to upsert autopilot: ${e.message}`, details: errorDetails } };
    }
}

export const createInitialFeaturesApplyToEventTrigger = async (
    oldAutopilot: AutopilotType,
    oldBody: ScheduleAssistWithMeetingQueueBodyType,
): Promise<AutopilotApiResponse<void>> => { // Returns void on success
    if (!oldAutopilot || !oldBody || !oldBody.userId || !oldBody.windowEndDate || !oldBody.timezone || !oldBody.windowStartDate || !oldAutopilot.timezone) {
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Missing critical autopilot or body parameters.' } };
    }
    try {
        const userPreferencesResponse = await getUserPreferences(oldBody.userId);
        if (!userPreferencesResponse.ok || !userPreferencesResponse.data) {
            throw new Error(`Failed to get user preferences: ${userPreferencesResponse.error?.message || 'Unknown error'}`);
        }
        const userPreferences = userPreferencesResponse.data;

        const startTimes = userPreferences.startTimes;
        const dayOfWeekInt = getISODay(dayjs(oldBody.windowEndDate.slice(0, 19)).tz(oldBody.timezone, true).toDate());

        const applicableStartTime = startTimes.find(i => i.day === dayOfWeekInt);
        if (!applicableStartTime) {
            throw new Error(`No applicable start time found for dayOfWeekInt ${dayOfWeekInt}.`);
        }
        const startHour = applicableStartTime.hour;
        const randomStartHour = getRandomIntInclusive(0, startHour > 0 ? startHour - 1 : 0); // Ensure positive range
        const randomStartMinute = getRandomIntInclusive(0, 59);

        const newWindowStartDate = dayjs(oldBody.windowStartDate.slice(0, 19)).tz(oldBody.timezone, true).hour(randomStartHour).minute(randomStartMinute).format();
        const newWindowEndDate = dayjs(oldBody.windowStartDate.slice(0, 19)).tz(oldBody.timezone, true).hour(randomStartHour).minute(randomStartMinute).add(6, 'd').format();

        const newBody: ScheduleAssistWithMeetingQueueBodyType = {
            ...oldBody, windowStartDate: newWindowStartDate, windowEndDate: newWindowEndDate,
        };
        const newAutopilot: AutopilotType = {
            ...oldAutopilot,
            scheduleAt: dayjs(newWindowStartDate.slice(0, 19)).tz(oldAutopilot.timezone, true).utc().format(),
            updatedAt: dayjs().format(),
            payload: newBody,
        };

        const triggerResponse = await createDailyFeaturesApplyEventTrigger(newAutopilot, newBody);
        if (!triggerResponse.ok || !triggerResponse.data) {
            throw new Error(`Failed to create daily features trigger: ${triggerResponse.error?.message || 'Unknown error'}`);
        }
        newAutopilot.id = triggerResponse.data; // autopilotId is event_id from Hasura

        const upsertResponse = await upsertAutopilotOne(newAutopilot);
        if (!upsertResponse.ok) {
            // If upsert fails, should we try to delete the scheduled event? Complex rollback.
            // For now, just report the upsert failure.
            throw new Error(`Failed to upsert autopilot data after creating trigger: ${upsertResponse.error?.message || 'Unknown error'}`);
        }
        return { ok: true, data: undefined };
    } catch (e: any) {
        console.error('Error creating initial features apply to event trigger:', e);
        return { ok: false, error: { code: 'INTERNAL_ERROR', message: `Failed to create initial trigger: ${e.message}`, details: e.toString() } };
    }
}

export const listAutopilotsGivenUserId = async (
    userId: string,
): Promise<AutopilotApiResponse<AutopilotType | null>> => { // Return single or null, as current logic returns [0]
    if (!userId) {
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'User ID is required.'}};
    }
    try {
        const operationName = 'ListAutopilotsGivenUserId'
        const query = `
            query ListAutopilotsGivenUserId($userId: uuid!) {
                Autopilot(where: {userId: {_eq: $userId}}) {
                    createdDate
                    id
                    payload
                    scheduleAt
                    timezone
                    updatedAt
                    userId
                }
            }
        `

        const variables = {
            userId,
        }

        const res: { data: { Autopilot: AutopilotType[] } } = await got.post(
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
                    variables,
                },
            },
        ).json()

        console.log(res, ' successfully listed autopilots given userId');
        return { ok: true, data: res?.data?.Autopilot?.[0] || null };
    } catch (e: any) {
        console.error('Error listing autopilots given userId:', e);
        const errorDetails = e.response?.body || e.message || e;
        return { ok: false, error: { code: 'HASURA_ERROR', message: `Failed to list autopilots: ${e.message}`, details: errorDetails } };
    }
}

export const deleteAutopilotGivenId = async (
    id: string,
): Promise<AutopilotApiResponse<AutopilotType | null>> => {
    if (!id) {
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Autopilot ID is required for deletion.'}};
    }
    try {
        const operationName = 'DeleteAutopilotById'
        const query = `
            mutation DeleteAutopilotById($id: uuid!) {
                delete_Autopilot_by_pk(id: $id) {
                createdDate
                id
                payload
                scheduleAt
                timezone
                updatedAt
                userId
                }
            }
          `
        const variables = {
            id,
        }

        const res: { data: { delete_Autopilot_by_pk: AutopilotType } } = await got.post(
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
                    variables,
                },
            },
        ).json();
        console.log(res, ' deleted autopilot by id');
        return { ok: true, data: res?.data?.delete_Autopilot_by_pk || null };
    } catch (e: any) {
        console.error('Error deleting autopilot by id:', e);
        const errorDetails = e.response?.body || e.message || e;
        return { ok: false, error: { code: 'HASURA_ERROR', message: `Failed to delete autopilot: ${e.message}`, details: errorDetails } };
    }
}

export const onScheduleDailyFeaturesApply7DayWindowToEventTrigger = async (
    oldAutopilot: AutopilotType,
    oldBody: ScheduleAssistWithMeetingQueueBodyType,
): Promise<AutopilotApiResponse<void>> => {
    if (!oldAutopilot || !oldAutopilot.userId || !oldBody || !oldBody.userId) { // Basic validation
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Old autopilot and body with userId are required.' } };
    }
    try {
        const dbAutopilotResponse = await listAutopilotsGivenUserId(oldAutopilot.userId);
        if (!dbAutopilotResponse.ok) { // Error fetching, critical
            throw new Error(`Failed to verify existing autopilot: ${dbAutopilotResponse.error?.message}`);
        }
        if (!dbAutopilotResponse.data?.id) { // Autopilot was deleted or not found
            console.log(`Autopilot for user ${oldAutopilot.userId} seems to have been deleted. Halting trigger.`);
            return { ok: true, data: undefined }; // Not an error, but operation stops
        }
        const dbAutopilot = dbAutopilotResponse.data; // Safe to use now

        const triggerFeaturesResponse = await triggerFeaturesApplyUrl(oldBody);
        if (!triggerFeaturesResponse.ok) {
            throw new Error(`Failed to trigger features apply URL: ${triggerFeaturesResponse.error?.message}`);
        }

        const userPreferencesResponse = await getUserPreferences(oldBody.userId);
        if (!userPreferencesResponse.ok || !userPreferencesResponse.data) {
            throw new Error(`Failed to get user preferences: ${userPreferencesResponse.error?.message}`);
        }
        const userPreferences = userPreferencesResponse.data;

        const startTimes = userPreferences.startTimes;
        const dayOfWeekInt = getISODay(dayjs(oldBody.windowEndDate.slice(0, 19)).tz(oldBody.timezone, true).toDate());
        const applicableStartTime = startTimes.find(i => i.day === dayOfWeekInt);
        if (!applicableStartTime) {
            throw new Error(`No applicable start time found for dayOfWeekInt ${dayOfWeekInt} for user ${oldBody.userId}.`);
        }
        const startHour = applicableStartTime.hour;
        const randomStartHour = getRandomIntInclusive(0, startHour > 0 ? startHour - 1 : 0);
        const randomStartMinute = getRandomIntInclusive(0, 59);

        const newWindowStartDate = dayjs(oldBody.windowStartDate.slice(0, 19)).tz(oldBody.timezone, true).hour(randomStartHour).minute(randomStartMinute).add(1, 'd').format();
        const newWindowEndDate = dayjs(oldBody.windowStartDate.slice(0, 19)).tz(oldBody.timezone, true).hour(randomStartHour).minute(randomStartMinute).add(7, 'd').format();

        const newBody: ScheduleAssistWithMeetingQueueBodyType = { ...oldBody, windowStartDate, windowEndDate: newWindowEndDate };
        const newAutopilot: AutopilotType = {
            ...oldAutopilot,
            scheduleAt: dayjs(newWindowStartDate.slice(0, 19)).tz(oldAutopilot.timezone, true).utc().format(),
            updatedAt: dayjs().format(),
            payload: newBody,
        };

        const createTriggerResponse = await createDailyFeaturesApplyEventTrigger(newAutopilot, newBody);
        if (!createTriggerResponse.ok || !createTriggerResponse.data) {
            throw new Error(`Failed to create new daily features trigger: ${createTriggerResponse.error?.message}`);
        }
        newAutopilot.id = createTriggerResponse.data;

        const deleteResponse = await deleteAutopilotGivenId(dbAutopilot.id);
        if (!deleteResponse.ok) {
            // Log this, but proceed to upsert the new one as the scheduled event is already created.
            console.warn(`Failed to delete old autopilot ${dbAutopilot.id}: ${deleteResponse.error?.message}. New trigger ${newAutopilot.id} is already scheduled.`);
        }

        const upsertResponse = await upsertAutopilotOne(newAutopilot);
        if (!upsertResponse.ok) {
            throw new Error(`Failed to upsert new autopilot ${newAutopilot.id}: ${upsertResponse.error?.message}`);
        }
        return { ok: true, data: undefined };
    } catch (e: any) {
        console.error('Error in onScheduleDailyFeaturesApply7DayWindowToEventTrigger:', e);
        return { ok: false, error: { code: 'INTERNAL_ERROR', message: `Failed to reschedule daily features trigger: ${e.message}`, details: e.toString() } };
    }
}

export const upsertAutopilotMany = async (
    autopilots: AutopilotType[],
): Promise<AutopilotApiResponse<AutopilotType[] | null>> => {
    if (!autopilots || autopilots.length === 0) {
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Autopilots array cannot be empty.'}};
    }
    try {
        const operationName = 'UpsertAutopilotMany'
        const query = `
        mutation UpsertAutopilotMany($autopilots: [Autopilot_insert_input!]!) {
            insert_Autopilot(objects: $autopilots, on_conflict: {constraint: Autopilot_pkey, update_columns: [
                   payload,
                scheduleAt,
                timezone,
                updatedAt,
            ]}) {
              affected_rows
              returning {
                createdDate
                id
                payload
                scheduleAt
                timezone
                updatedAt
                userId
              }
            }
          }
          `
        const variables = {
            autopilots,
        }
        const res: { data: { insert_Autopilot: AutopilotType[] } } = await got.post(
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
                    variables,
                },
            },
        ).json()

        console.log(res, ' successfully upserted autopilot many');
        return { ok: true, data: res?.data?.insert_Autopilot || null }; // Should be res.data.insert_Autopilot.returning for actual data
    } catch (e: any) {
        console.error('Error upserting autopilot many:', e);
        const errorDetails = e.response?.body || e.message || e;
        return { ok: false, error: { code: 'HASURA_ERROR', message: `Failed to upsert autopilots: ${e.message}`, details: errorDetails } };
    }
}

export const getAutopilotGivenId = async (
    id: string,
): Promise<AutopilotApiResponse<AutopilotType | null>> => {
    if (!id) {
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Autopilot ID is required.'}};
    }
    try {
        const operationName = 'GetAutopilotById'
        const query = `
            query GetAutopilotById($id: uuid!) {
                Autopilot_by_pk(id: $id) {
                createdDate
                id
                payload
                scheduleAt
                timezone
                updatedAt
                userId
                }
            }
        `

        const variables = {
            id,
        }

        const res: { data: { Autopilot_by_pk: AutopilotType } } = await got.post(
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
                    variables,
                },
            },
        ).json()

        console.log(res, ' successfully got autopilot given Id');
        return { ok: true, data: res?.data?.Autopilot_by_pk || null };
    } catch (e: any) {
        console.error('Error getting autopilot by Id:', e);
        const errorDetails = e.response?.body || e.message || e;
        return { ok: false, error: { code: 'HASURA_ERROR', message: `Failed to get autopilot by ID: ${e.message}`, details: errorDetails } };
    }
}

export const deleteScheduledEventForAutopilot = async (
    eventId: string,
): Promise<AutopilotApiResponse<{success: boolean}>> => {
    if (!eventId) {
        return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Scheduled event ID is required for deletion.'}};
    }
    try {
        const jsonBody = {
            type: 'delete_scheduled_event',
            args: {
                type: 'one_off',
                event_id: eventId,
            }
        }

        const res = await got.post(
            hasuraMetadataUrl,
            {
                headers: {
                    'X-Hasura-Admin-Secret': hasuraAdminSecret,
                    'Content-Type': 'application/json',
                    'X-Hasura-Role': 'admin'
                },
                json: jsonBody,
            }
        ).json(); // Assuming res is {message: "success"} or similar from Hasura event trigger API

        console.log(res, ' successfully deleted scheduled event trigger');
        // Check actual response structure from Hasura for this type of call
        if ((res as any)?.message === "success") { // Need to cast or define type for Hasura metadata response
             return { ok: true, data: { success: true } };
        } else {
            return { ok: false, error: {code: 'HASURA_METADATA_ERROR', message: 'Failed to delete scheduled event, unexpected response.', details: res }};
        }
    } catch (e: any) {
        console.error('Error deleting scheduled event for autopilot:', e);
        const errorDetails = e.response?.body || e.message || e;
        return { ok: false, error: { code: 'HASURA_METADATA_ERROR', message: `Failed to delete scheduled event: ${e.message}`, details: errorDetails } };
    }
}

