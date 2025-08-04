import got from 'got';
import { getISODay } from 'date-fns';
import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import { authApiToken, featuresApplyAdminUrl, hasuraAdminSecret, hasuraGraphUrl, hasuraMetadataUrl, onScheduledTriggerDailyFeaturesApplyWebhookProdAdminUrl, scheduleAssistUrl, } from './constants';
dayjs.extend(isoWeek);
dayjs.extend(duration);
dayjs.extend(isBetween);
dayjs.extend(timezone);
dayjs.extend(utc);
function getRandomIntInclusive(min, max) {
    min = Math.ceil(min);
    max = Math.floor(max);
    return Math.floor(Math.random() * (max - min + 1) + min); // The maximum is inclusive and the minimum is inclusive
}
export const triggerFeaturesApplyUrl = async (body) => {
    if (!body || !body.userId) {
        // Basic validation
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Request body with userId is required.',
            },
        };
    }
    try {
        const url = featuresApplyAdminUrl;
        const res = await got
            .post(url, {
            headers: {
                Authorization: `Basic ${Buffer.from(`admin:${authApiToken}`).toString('base64')}`,
                'content-type': 'application/json',
            },
            json: body,
        })
            .json();
        console.log(res, ' successfully called featuresApplyAdminUrl');
        return { ok: true, data: { success: true, details: res } };
    }
    catch (e) {
        console.error('Error triggering features apply url:', e);
        const errorDetails = e.response?.body || e.message || e;
        return {
            ok: false,
            error: {
                code: 'EXTERNAL_API_ERROR',
                message: `Failed to trigger features apply URL: ${e.message}`,
                details: errorDetails,
            },
        };
    }
};
export const triggerScheduleAssistUrl = async (body) => {
    if (!body || !body.userId) {
        // Basic validation
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Request body with userId is required.',
            },
        };
    }
    try {
        const url = scheduleAssistUrl;
        const res = await got
            .post(url, {
            headers: {
                Authorization: `Basic ${Buffer.from(`admin:${authApiToken}`).toString('base64')}`,
                'content-type': 'application/json',
            },
            json: body,
        })
            .json();
        console.log(res, ' successfully called scheduleAssistUrl'); // Corrected log
        return { ok: true, data: { success: true, details: res } };
    }
    catch (e) {
        console.error('Error triggering schedule assist url:', e);
        const errorDetails = e.response?.body || e.message || e;
        return {
            ok: false,
            error: {
                code: 'EXTERNAL_API_ERROR',
                message: `Failed to trigger schedule assist URL: ${e.message}`,
                details: errorDetails,
            },
        };
    }
};
export const getUserPreferences = async (userId) => {
    if (!userId) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'User ID is required for getUserPreferences.',
            },
        };
    }
    try {
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
        return { ok: true, data: res?.data?.User_Preference?.[0] || null };
    }
    catch (e) {
        console.error('Error getting user preferences:', e);
        const errorDetails = e.response?.body || e.message || e;
        return {
            ok: false,
            error: {
                code: 'HASURA_ERROR',
                message: `Failed to get user preferences: ${e.message}`,
                details: errorDetails,
            },
        };
    }
};
export const createDailyFeaturesApplyEventTrigger = async (autopilot, body) => {
    if (!autopilot || !body || !autopilot.scheduleAt) {
        // Basic validation
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Autopilot data, body, and scheduleAt are required.',
            },
        };
    }
    try {
        const res = await got
            .post(hasuraMetadataUrl, {
            // This is a Hasura Metadata API call
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                // 'X-Hasura-Role': 'admin', // Not typically needed for metadata calls with admin secret
                'content-type': 'application/json',
            },
            json: {
                type: 'create_scheduled_event',
                args: {
                    webhook: onScheduledTriggerDailyFeaturesApplyWebhookProdAdminUrl,
                    schedule_at: dayjs.utc(autopilot.scheduleAt).format(), // Ensure autopilot is not null
                    payload: { autopilot, body },
                    headers: [
                        {
                            name: 'Authorization',
                            value: `Basic ${Buffer.from(`admin:${authApiToken}`).toString('base64')}`,
                        },
                        { name: 'Content-Type', value: 'application/json' },
                    ],
                    retry_conf: {
                        // Example retry configuration
                        num_retries: 3,
                        retry_interval_seconds: 10,
                        timeout_seconds: 60,
                    },
                    comment: `Daily features apply trigger for autopilot ${autopilot.id}`,
                },
            },
        })
            .json();
        if (res && res.message === 'success' && res.event_id) {
            console.log(`Successfully created scheduled event trigger: ${res.event_id}`);
            return { ok: true, data: res.event_id };
        }
        else {
            console.error('Failed to create Hasura scheduled event, response was not success or event_id missing:', res);
            return {
                ok: false,
                error: {
                    code: 'HASURA_METADATA_ERROR',
                    message: 'Failed to create Hasura scheduled event.',
                    details: res,
                },
            };
        }
    }
    catch (e) {
        console.error('Error creating Hasura scheduled event trigger:', e);
        const errorDetails = e.response?.body || e.message || e;
        return {
            ok: false,
            error: {
                code: 'HASURA_METADATA_ERROR',
                message: `Error creating Hasura scheduled event: ${e.message}`,
                details: errorDetails,
            },
        };
    }
};
export const upsertAutopilotOne = async (autopilot) => {
    if (!autopilot || !autopilot.id || !autopilot.userId) {
        // Basic validation
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Autopilot object with id and userId is required.',
            },
        };
    }
    try {
        const operationName = 'UpsertAutopilotOne';
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
          `;
        const variables = {
            autopilot,
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
        console.log(res, ' successfully upserted autopilot one');
        return { ok: true, data: res?.data?.insert_Autopilot_one || null };
    }
    catch (e) {
        console.error('Error upserting autopilot one:', e);
        const errorDetails = e.response?.body || e.message || e;
        return {
            ok: false,
            error: {
                code: 'HASURA_ERROR',
                message: `Failed to upsert autopilot: ${e.message}`,
                details: errorDetails,
            },
        };
    }
};
export const createInitialFeaturesApplyToEventTrigger = async (oldAutopilot, oldBody) => {
    // Returns void on success
    if (!oldAutopilot ||
        !oldBody ||
        !oldBody.userId ||
        !oldBody.windowEndDate ||
        !oldBody.timezone ||
        !oldBody.windowStartDate ||
        !oldAutopilot.timezone) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Missing critical autopilot or body parameters.',
            },
        };
    }
    try {
        const userPreferencesResponse = await getUserPreferences(oldBody.userId);
        if (!userPreferencesResponse.ok || !userPreferencesResponse.data) {
            throw new Error(`Failed to get user preferences: ${userPreferencesResponse.error?.message || 'Unknown error'}`);
        }
        const userPreferences = userPreferencesResponse.data;
        const startTimes = userPreferences.startTimes;
        const dayOfWeekInt = getISODay(dayjs(oldBody.windowEndDate.slice(0, 19))
            .tz(oldBody.timezone, true)
            .toDate());
        const applicableStartTime = startTimes.find((i) => i.day === dayOfWeekInt);
        if (!applicableStartTime) {
            throw new Error(`No applicable start time found for dayOfWeekInt ${dayOfWeekInt}.`);
        }
        const startHour = applicableStartTime.hour;
        const randomStartHour = getRandomIntInclusive(0, startHour > 0 ? startHour - 1 : 0); // Ensure positive range
        const randomStartMinute = getRandomIntInclusive(0, 59);
        const newWindowStartDate = dayjs(oldBody.windowStartDate.slice(0, 19))
            .tz(oldBody.timezone, true)
            .hour(randomStartHour)
            .minute(randomStartMinute)
            .format();
        const newWindowEndDate = dayjs(oldBody.windowStartDate.slice(0, 19))
            .tz(oldBody.timezone, true)
            .hour(randomStartHour)
            .minute(randomStartMinute)
            .add(6, 'd')
            .format();
        const newBody = {
            ...oldBody,
            windowStartDate: newWindowStartDate,
            windowEndDate: newWindowEndDate,
        };
        const newAutopilot = {
            ...oldAutopilot,
            scheduleAt: dayjs(newWindowStartDate.slice(0, 19))
                .tz(oldAutopilot.timezone, true)
                .utc()
                .format(),
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
    }
    catch (e) {
        console.error('Error creating initial features apply to event trigger:', e);
        return {
            ok: false,
            error: {
                code: 'INTERNAL_ERROR',
                message: `Failed to create initial trigger: ${e.message}`,
                details: e.toString(),
            },
        };
    }
};
export const listAutopilotsGivenUserId = async (userId) => {
    // Return single or null, as current logic returns [0]
    if (!userId) {
        return {
            ok: false,
            error: { code: 'VALIDATION_ERROR', message: 'User ID is required.' },
        };
    }
    try {
        const operationName = 'ListAutopilotsGivenUserId';
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
        console.log(res, ' successfully listed autopilots given userId');
        return { ok: true, data: res?.data?.Autopilot?.[0] || null };
    }
    catch (e) {
        console.error('Error listing autopilots given userId:', e);
        const errorDetails = e.response?.body || e.message || e;
        return {
            ok: false,
            error: {
                code: 'HASURA_ERROR',
                message: `Failed to list autopilots: ${e.message}`,
                details: errorDetails,
            },
        };
    }
};
export const deleteAutopilotGivenId = async (id) => {
    if (!id) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Autopilot ID is required for deletion.',
            },
        };
    }
    try {
        const operationName = 'DeleteAutopilotById';
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
        console.log(res, ' deleted autopilot by id');
        return { ok: true, data: res?.data?.delete_Autopilot_by_pk || null };
    }
    catch (e) {
        console.error('Error deleting autopilot by id:', e);
        const errorDetails = e.response?.body || e.message || e;
        return {
            ok: false,
            error: {
                code: 'HASURA_ERROR',
                message: `Failed to delete autopilot: ${e.message}`,
                details: errorDetails,
            },
        };
    }
};
export const onScheduleDailyFeaturesApply7DayWindowToEventTrigger = async (oldAutopilot, oldBody) => {
    if (!oldAutopilot || !oldAutopilot.userId || !oldBody || !oldBody.userId) {
        // Basic validation
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Old autopilot and body with userId are required.',
            },
        };
    }
    try {
        const dbAutopilotResponse = await listAutopilotsGivenUserId(oldAutopilot.userId);
        if (!dbAutopilotResponse.ok) {
            // Error fetching, critical
            throw new Error(`Failed to verify existing autopilot: ${dbAutopilotResponse.error?.message}`);
        }
        if (!dbAutopilotResponse.data?.id) {
            // Autopilot was deleted or not found
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
        const dayOfWeekInt = getISODay(dayjs(oldBody.windowEndDate.slice(0, 19))
            .tz(oldBody.timezone, true)
            .toDate());
        const applicableStartTime = startTimes.find((i) => i.day === dayOfWeekInt);
        if (!applicableStartTime) {
            throw new Error(`No applicable start time found for dayOfWeekInt ${dayOfWeekInt} for user ${oldBody.userId}.`);
        }
        const startHour = applicableStartTime.hour;
        const randomStartHour = getRandomIntInclusive(0, startHour > 0 ? startHour - 1 : 0);
        const randomStartMinute = getRandomIntInclusive(0, 59);
        const newWindowStartDate = dayjs(oldBody.windowStartDate.slice(0, 19))
            .tz(oldBody.timezone, true)
            .hour(randomStartHour)
            .minute(randomStartMinute)
            .add(1, 'd')
            .format();
        const newWindowEndDate = dayjs(oldBody.windowStartDate.slice(0, 19))
            .tz(oldBody.timezone, true)
            .hour(randomStartHour)
            .minute(randomStartMinute)
            .add(7, 'd')
            .format();
        const newBody = {
            ...oldBody,
            windowStartDate,
            windowEndDate: newWindowEndDate,
        };
        const newAutopilot = {
            ...oldAutopilot,
            scheduleAt: dayjs(newWindowStartDate.slice(0, 19))
                .tz(oldAutopilot.timezone, true)
                .utc()
                .format(),
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
    }
    catch (e) {
        console.error('Error in onScheduleDailyFeaturesApply7DayWindowToEventTrigger:', e);
        return {
            ok: false,
            error: {
                code: 'INTERNAL_ERROR',
                message: `Failed to reschedule daily features trigger: ${e.message}`,
                details: e.toString(),
            },
        };
    }
};
export const upsertAutopilotMany = async (autopilots) => {
    if (!autopilots || autopilots.length === 0) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Autopilots array cannot be empty.',
            },
        };
    }
    try {
        const operationName = 'UpsertAutopilotMany';
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
          `;
        const variables = {
            autopilots,
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
        console.log(res, ' successfully upserted autopilot many');
        return { ok: true, data: res?.data?.insert_Autopilot || null }; // Should be res.data.insert_Autopilot.returning for actual data
    }
    catch (e) {
        console.error('Error upserting autopilot many:', e);
        const errorDetails = e.response?.body || e.message || e;
        return {
            ok: false,
            error: {
                code: 'HASURA_ERROR',
                message: `Failed to upsert autopilots: ${e.message}`,
                details: errorDetails,
            },
        };
    }
};
export const getAutopilotGivenId = async (id) => {
    if (!id) {
        return {
            ok: false,
            error: { code: 'VALIDATION_ERROR', message: 'Autopilot ID is required.' },
        };
    }
    try {
        const operationName = 'GetAutopilotById';
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
        console.log(res, ' successfully got autopilot given Id');
        return { ok: true, data: res?.data?.Autopilot_by_pk || null };
    }
    catch (e) {
        console.error('Error getting autopilot by Id:', e);
        const errorDetails = e.response?.body || e.message || e;
        return {
            ok: false,
            error: {
                code: 'HASURA_ERROR',
                message: `Failed to get autopilot by ID: ${e.message}`,
                details: errorDetails,
            },
        };
    }
};
export const deleteScheduledEventForAutopilot = async (eventId) => {
    if (!eventId) {
        return {
            ok: false,
            error: {
                code: 'VALIDATION_ERROR',
                message: 'Scheduled event ID is required for deletion.',
            },
        };
    }
    try {
        const jsonBody = {
            type: 'delete_scheduled_event',
            args: {
                type: 'one_off',
                event_id: eventId,
            },
        };
        const res = await got
            .post(hasuraMetadataUrl, {
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'Content-Type': 'application/json',
                'X-Hasura-Role': 'admin',
            },
            json: jsonBody,
        })
            .json(); // Assuming res is {message: "success"} or similar from Hasura event trigger API
        console.log(res, ' successfully deleted scheduled event trigger');
        // Check actual response structure from Hasura for this type of call
        if (res?.message === 'success') {
            // Need to cast or define type for Hasura metadata response
            return { ok: true, data: { success: true } };
        }
        else {
            return {
                ok: false,
                error: {
                    code: 'HASURA_METADATA_ERROR',
                    message: 'Failed to delete scheduled event, unexpected response.',
                    details: res,
                },
            };
        }
    }
    catch (e) {
        console.error('Error deleting scheduled event for autopilot:', e);
        const errorDetails = e.response?.body || e.message || e;
        return {
            ok: false,
            error: {
                code: 'HASURA_METADATA_ERROR',
                message: `Failed to delete scheduled event: ${e.message}`,
                details: errorDetails,
            },
        };
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxHQUFHLE1BQU0sS0FBSyxDQUFDO0FBQ3RCLE9BQU8sRUFBRSxTQUFTLEVBQUUsTUFBTSxVQUFVLENBQUM7QUFDckMsT0FBTyxLQUFLLE1BQU0sT0FBTyxDQUFDO0FBQzFCLE9BQU8sT0FBTyxNQUFNLHNCQUFzQixDQUFDO0FBQzNDLE9BQU8sUUFBUSxNQUFNLHVCQUF1QixDQUFDO0FBQzdDLE9BQU8sU0FBUyxNQUFNLHdCQUF3QixDQUFDO0FBQy9DLE9BQU8sUUFBUSxNQUFNLHVCQUF1QixDQUFDO0FBQzdDLE9BQU8sR0FBRyxNQUFNLGtCQUFrQixDQUFDO0FBVW5DLE9BQU8sRUFDTCxZQUFZLEVBQ1oscUJBQXFCLEVBQ3JCLGlCQUFpQixFQUNqQixjQUFjLEVBQ2QsaUJBQWlCLEVBQ2pCLHVEQUF1RCxFQUV2RCxpQkFBaUIsR0FDbEIsTUFBTSxhQUFhLENBQUM7QUFFckIsS0FBSyxDQUFDLE1BQU0sQ0FBQyxPQUFPLENBQUMsQ0FBQztBQUN0QixLQUFLLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxDQUFDO0FBQ3ZCLEtBQUssQ0FBQyxNQUFNLENBQUMsU0FBUyxDQUFDLENBQUM7QUFDeEIsS0FBSyxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsQ0FBQztBQUN2QixLQUFLLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDO0FBRWxCLFNBQVMscUJBQXFCLENBQUMsR0FBRyxFQUFFLEdBQUc7SUFDckMsR0FBRyxHQUFHLElBQUksQ0FBQyxJQUFJLENBQUMsR0FBRyxDQUFDLENBQUM7SUFDckIsR0FBRyxHQUFHLElBQUksQ0FBQyxLQUFLLENBQUMsR0FBRyxDQUFDLENBQUM7SUFDdEIsT0FBTyxJQUFJLENBQUMsS0FBSyxDQUFDLElBQUksQ0FBQyxNQUFNLEVBQUUsR0FBRyxDQUFDLEdBQUcsR0FB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T0FBTyxFQUFFLHdEQUF3RDtvQkFDakUsT0FBTyxFQUFFLEdBQUc7aUJBQ2I7YUFDRixDQUFDO1FBQ0osQ0FBQztJQUNILENBQUM7SUFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO1FBQ2hCLE9BQU8sQ0FBQyxLQUFLLENBQUMsK0NBQStDLEVBQUUsQ0FBQyxDQUFDLENBQUM7UUFDbEUsTUFBTSxZQUFZLEdBQUcsQ0FBQyxDQUFDLFFBQVEsRUFBRSxJQUFJLElBQUksQ0FBQyxDQUFDLE9BQU8sSUFBSSxDQUFDLENBQUM7UUFDeEQsT0FBTztZQUNMLEVBQUUsRUFBRSxLQUFLO1lBQ1QsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSx1QkFBdUI7Z0JBQzdCLE9BQU8sRUFBRSxxQ0FBcUMsQ0FBQyxDQUFDLE9BQU8sRUFBRTtnQkFDekQsT0FBTyxFQUFFLFlBQVk7YUFDdEI7U0FDRixDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBnb3QgZnJvbSAnZ290JztcbmltcG9ydCB7IGdldElTT0RheSB9IGZyb20gJ2RhdGUtZm5zJztcbmltcG9ydCBkYXlqcyBmcm9tICdkYXlqcyc7XG5pbXBvcnQgaXNvV2VlayBmcm9tICdkYXlqcy9wbHVnaW4vaXNvV2Vlayc7XG5pbXBvcnQgZHVyYXRpb24gZnJvbSAnZGF5anMvcGx1Z2luL2R1cmF0aW9uJztcbmltcG9ydCBpc0JldHdlZW4gZnJvbSAnZGF5anMvcGx1Z2luL2lzQmV0d2Vlbic7XG5pbXBvcnQgdGltZXpvbmUgZnJvbSAnZGF5anMvcGx1Z2luL3RpbWV6b25lJztcbmltcG9ydCB1dGMgZnJvbSAnZGF5anMvcGx1Z2luL3V0Yyc7XG5pbXBvcnQgXyBmcm9tICdsb2Rhc2gnO1xuXG5pbXBvcnQge1xuICBBdXRvcGlsb3RUeXBlLFxuICBTY2hlZHVsZUFzc2lzdFdpdGhNZWV0aW5nUXVldWVCb2R5VHlwZSxcbiAgVXNlclByZWZlcmVuY2VUeXBlLFxuICBBdXRvcGlsb3RBcGlSZXNwb25zZSxcbiAgU2tpbGxFcnJvcixcbn0gZnJvbSAnLi90eXBlcyc7IC8vIEFkZGVkIEF1dG9waWxvdEFwaVJlc3BvbnNlLCBTa2lsbEVycm9yXG5pbXBvcnQge1xuICBhdXRoQXBpVG9rZW4sXG4gIGZlYXR1cmVzQXBwbHlBZG1pblVybCxcbiAgaGFzdXJhQWRtaW5TZWNyZXQsXG4gIGhhc3VyYUdyYXBoVXJsLFxuICBoYXN1cmFNZXRhZGF0YVVybCxcbiAgb25TY2hlZHVsZWRUcmlnZ2VyRGFpbHlGZWF0dXJlc0FwcGx5V2ViaG9va1Byb2RBZG1pblVybCxcbiAgb25TY2hlZHVsZWRUcmlnZ2VyRGFpbHlTY2hlZHVsZUFzc2lzdFdlYmhvb2tQcm9kQWRtaW5VcmwsXG4gIHNjaGVkdWxlQXNzaXN0VXJsLFxufSBmcm9tICcuL2NvbnN0YW50cyc7XG5cbmRheWpzLmV4dGVuZChpc29XZWVrKTtcbmRheWpzLmV4dGVuZChkdXJhdGlvbik7XG5kYXlqcy5leHRlbmQoaXNCZXR3ZWVuKTtcbmRheWpzLmV4dGVuZCh0aW1lem9uZSk7XG5kYXlqcy5leHRlbmQodXRjKTtcblxuZnVuY3Rpb24gZ2V0UmFuZG9tSW50SW5jbHVzaXZlKG1pbiwgbWF4KSB7XG4gIG1pbiA9IE1hdGguY2VpbChtaW4pO1xuICBtYXggPSBNYXRoLmZsb29yKG1heCk7XG4gIHJldHVybiBNYXRoLmZsb29yKE1hdGgucmFuZG9tKCkgKiAobWF4IC0gbWluICsgMSkgKyBtaW4pOyAvLyBUaGUgbWF4aW11bSBpcyBpbmNsdXNpdmUgYW5kIHRoZSBtaW5pbXVtIGlzIGluY2x1c2l2ZVxufVxuXG5leHBvcnQgY29uc3QgdHJpZ2dlckZlYXR1cmVzQXBwbHlVcmwgPSBhc3luYyAoXG4gIGJvZHk6IFNjaGVkdWxlQXNzaXN0V2l0aE1lZXRpbmdRdWV1ZUJvZHlUeXBlXG4pOiBQcm9taXNlPEF1dG9waWxvdEFwaVJlc3BvbnNlPHsgc3VjY2VzczogYm9vbGVhbjsgZGV0YWlscz86IGFueSB9Pj4gPT4ge1xuICBpZiAoIWJvZHkgfHwgIWJvZHkudXNlcklkKSB7XG4gICAgLy8gQmFzaWMgdmFsaWRhdGlvblxuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdSZXF1ZXN0IGJvZHkgd2l0aCB1c2VySWQgaXMgcmVxdWlyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICB0cnkge1xuICAgIGNvbnN0IHVybCA9IGZlYXR1cmVzQXBwbHlBZG1pblVybDtcbiAgICBjb25zdCByZXMgPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KHVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgQXV0aG9yaXphdGlvbjogYEJhc2ljICR7QnVmZmVyLmZyb20oYGFkbWluOiR7YXV0aEFwaVRva2VufWApLnRvU3RyaW5nKCdiYXNlNjQnKX1gLFxuICAgICAgICAgICdjb250ZW50LXR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IGJvZHksXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICBjb25zb2xlLmxvZyhyZXMsICcgc3VjY2Vzc2Z1bGx5IGNhbGxlZCBmZWF0dXJlc0FwcGx5QWRtaW5VcmwnKTtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogeyBzdWNjZXNzOiB0cnVlLCBkZXRhaWxzOiByZXMgfSB9O1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciB0cmlnZ2VyaW5nIGZlYXR1cmVzIGFwcGx5IHVybDonLCBlKTtcbiAgICBjb25zdCBlcnJvckRldGFpbHMgPSBlLnJlc3BvbnNlPy5ib2R5IHx8IGUubWVzc2FnZSB8fCBlO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnRVhURVJOQUxfQVBJX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byB0cmlnZ2VyIGZlYXR1cmVzIGFwcGx5IFVSTDogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZXJyb3JEZXRhaWxzLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdHJpZ2dlclNjaGVkdWxlQXNzaXN0VXJsID0gYXN5bmMgKFxuICBib2R5OiBTY2hlZHVsZUFzc2lzdFdpdGhNZWV0aW5nUXVldWVCb2R5VHlwZVxuKTogUHJvbWlzZTxBdXRvcGlsb3RBcGlSZXNwb25zZTx7IHN1Y2Nlc3M6IGJvb2xlYW47IGRldGFpbHM/OiBhbnkgfT4+ID0+IHtcbiAgaWYgKCFib2R5IHx8ICFib2R5LnVzZXJJZCkge1xuICAgIC8vIEJhc2ljIHZhbGlkYXRpb25cbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnUmVxdWVzdCBib2R5IHdpdGggdXNlcklkIGlzIHJlcXVpcmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBjb25zdCB1cmwgPSBzY2hlZHVsZUFzc2lzdFVybDtcbiAgICBjb25zdCByZXMgPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KHVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgQXV0aG9yaXphdGlvbjogYEJhc2ljICR7QnVmZmVyLmZyb20oYGFkbWluOiR7YXV0aEFwaVRva2VufWApLnRvU3RyaW5nKCdiYXNlNjQnKX1gLFxuICAgICAgICAgICdjb250ZW50LXR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IGJvZHksXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICBjb25zb2xlLmxvZyhyZXMsICcgc3VjY2Vzc2Z1bGx5IGNhbGxlZCBzY2hlZHVsZUFzc2lzdFVybCcpOyAvLyBDb3JyZWN0ZWQgbG9nXG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHsgc3VjY2VzczogdHJ1ZSwgZGV0YWlsczogcmVzIH0gfTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgdHJpZ2dlcmluZyBzY2hlZHVsZSBhc3Npc3QgdXJsOicsIGUpO1xuICAgIGNvbnN0IGVycm9yRGV0YWlscyA9IGUucmVzcG9uc2U/LmJvZHkgfHwgZS5tZXNzYWdlIHx8IGU7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdFWFRFUk5BTF9BUElfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgRmFpbGVkIHRvIHRyaWdnZXIgc2NoZWR1bGUgYXNzaXN0IFVSTDogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZXJyb3JEZXRhaWxzLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0VXNlclByZWZlcmVuY2VzID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxBdXRvcGlsb3RBcGlSZXNwb25zZTxVc2VyUHJlZmVyZW5jZVR5cGUgfCBudWxsPj4gPT4ge1xuICBpZiAoIXVzZXJJZCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdVc2VyIElEIGlzIHJlcXVpcmVkIGZvciBnZXRVc2VyUHJlZmVyZW5jZXMuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZ2V0VXNlclByZWZlcmVuY2VzJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICBxdWVyeSBnZXRVc2VyUHJlZmVyZW5jZXMoJHVzZXJJZDogdXVpZCEpIHtcbiAgICAgIFVzZXJfUHJlZmVyZW5jZSh3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH19KSB7XG4gICAgICAgIHN0YXJ0VGltZXNcbiAgICAgICAgZW5kVGltZXNcbiAgICAgICAgYmFja1RvQmFja01lZXRpbmdzXG4gICAgICAgIGNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgY29weUNhdGVnb3JpZXNcbiAgICAgICAgY29weUlzQnJlYWtcbiAgICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgY29weVJlbWluZGVyc1xuICAgICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICBkZWxldGVkXG4gICAgICAgIGZvbGxvd1VwXG4gICAgICAgIGlkXG4gICAgICAgIGlzUHVibGljQ2FsZW5kYXJcbiAgICAgICAgbWF4TnVtYmVyT2ZNZWV0aW5nc1xuICAgICAgICBtYXhXb3JrTG9hZFBlcmNlbnRcbiAgICAgICAgcHVibGljQ2FsZW5kYXJDYXRlZ29yaWVzXG4gICAgICAgIHJlbWluZGVyc1xuICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgdXNlcklkXG4gICAgICAgIG1pbk51bWJlck9mQnJlYWtzXG4gICAgICAgIGJyZWFrQ29sb3JcbiAgICAgICAgYnJlYWtMZW5ndGhcbiAgICAgICAgY29weUNvbG9yXG4gICAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICAgIG9uQm9hcmRlZFxuICAgICAgfVxuICAgIH0gICAgXG4gIGA7XG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgVXNlcl9QcmVmZXJlbmNlOiBVc2VyUHJlZmVyZW5jZVR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogcmVzPy5kYXRhPy5Vc2VyX1ByZWZlcmVuY2U/LlswXSB8fCBudWxsIH07XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0Vycm9yIGdldHRpbmcgdXNlciBwcmVmZXJlbmNlczonLCBlKTtcbiAgICBjb25zdCBlcnJvckRldGFpbHMgPSBlLnJlc3BvbnNlPy5ib2R5IHx8IGUubWVzc2FnZSB8fCBlO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnSEFTVVJBX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBnZXQgdXNlciBwcmVmZXJlbmNlczogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZXJyb3JEZXRhaWxzLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgY3JlYXRlRGFpbHlGZWF0dXJlc0FwcGx5RXZlbnRUcmlnZ2VyID0gYXN5bmMgKFxuICBhdXRvcGlsb3Q6IEF1dG9waWxvdFR5cGUsXG4gIGJvZHk6IFNjaGVkdWxlQXNzaXN0V2l0aE1lZXRpbmdRdWV1ZUJvZHlUeXBlXG4pOiBQcm9taXNlPEF1dG9waWxvdEFwaVJlc3BvbnNlPHN0cmluZyB8IG51bGw+PiA9PiB7XG4gIGlmICghYXV0b3BpbG90IHx8ICFib2R5IHx8ICFhdXRvcGlsb3Quc2NoZWR1bGVBdCkge1xuICAgIC8vIEJhc2ljIHZhbGlkYXRpb25cbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnQXV0b3BpbG90IGRhdGEsIGJvZHksIGFuZCBzY2hlZHVsZUF0IGFyZSByZXF1aXJlZC4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzOiB7XG4gICAgICBtZXNzYWdlOiBzdHJpbmc7IC8vIFR5cGljYWxseSBcInN1Y2Nlc3NcIlxuICAgICAgZXZlbnRfaWQ6IHN0cmluZztcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFNZXRhZGF0YVVybCwge1xuICAgICAgICAvLyBUaGlzIGlzIGEgSGFzdXJhIE1ldGFkYXRhIEFQSSBjYWxsXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgLy8gJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLCAvLyBOb3QgdHlwaWNhbGx5IG5lZWRlZCBmb3IgbWV0YWRhdGEgY2FsbHMgd2l0aCBhZG1pbiBzZWNyZXRcbiAgICAgICAgICAnY29udGVudC10eXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgdHlwZTogJ2NyZWF0ZV9zY2hlZHVsZWRfZXZlbnQnLFxuICAgICAgICAgIGFyZ3M6IHtcbiAgICAgICAgICAgIHdlYmhvb2s6IG9uU2NoZWR1bGVkVHJpZ2dlckRhaWx5RmVhdHVyZXNBcHBseVdlYmhvb2tQcm9kQWRtaW5VcmwsXG4gICAgICAgICAgICBzY2hlZHVsZV9hdDogZGF5anMudXRjKGF1dG9waWxvdC5zY2hlZHVsZUF0KS5mb3JtYXQoKSwgLy8gRW5zdXJlIGF1dG9waWxvdCBpcyBub3QgbnVsbFxuICAgICAgICAgICAgcGF5bG9hZDogeyBhdXRvcGlsb3QsIGJvZHkgfSxcbiAgICAgICAgICAgIGhlYWRlcnM6IFtcbiAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgIG5hbWU6ICdBdXRob3JpemF0aW9uJyxcbiAgICAgICAgICAgICAgICB2YWx1ZTogYEJhc2ljICR7QnVmZmVyLmZyb20oYGFkbWluOiR7YXV0aEFwaVRva2VufWApLnRvU3RyaW5nKCdiYXNlNjQnKX1gLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICB7IG5hbWU6ICdDb250ZW50LVR5cGUnLCB2YWx1ZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0sXG4gICAgICAgICAgICBdLFxuICAgICAgICAgICAgcmV0cnlfY29uZjoge1xuICAgICAgICAgICAgICAvLyBFeGFtcGxlIHJldHJ5IGNvbmZpZ3VyYXRpb25cbiAgICAgICAgICAgICAgbnVtX3JldHJpZXM6IDMsXG4gICAgICAgICAgICAgIHJldHJ5X2ludGVydmFsX3NlY29uZHM6IDEwLFxuICAgICAgICAgICAgICB0aW1lb3V0X3NlY29uZHM6IDYwLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGNvbW1lbnQ6IGBEYWlseSBmZWF0dXJlcyBhcHBseSB0cmlnZ2VyIGZvciBhdXRvcGlsb3QgJHthdXRvcGlsb3QuaWR9YCxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBpZiAocmVzICYmIHJlcy5tZXNzYWdlID09PSAnc3VjY2VzcycgJiYgcmVzLmV2ZW50X2lkKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYFN1Y2Nlc3NmdWxseSBjcmVhdGVkIHNjaGVkdWxlZCBldmVudCB0cmlnZ2VyOiAke3Jlcy5ldmVudF9pZH1gXG4gICAgICApO1xuICAgICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHJlcy5ldmVudF9pZCB9O1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAnRmFpbGVkIHRvIGNyZWF0ZSBIYXN1cmEgc2NoZWR1bGVkIGV2ZW50LCByZXNwb25zZSB3YXMgbm90IHN1Y2Nlc3Mgb3IgZXZlbnRfaWQgbWlzc2luZzonLFxuICAgICAgICByZXNcbiAgICAgICk7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBvazogZmFsc2UsXG4gICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgY29kZTogJ0hBU1VSQV9NRVRBREFUQV9FUlJPUicsXG4gICAgICAgICAgbWVzc2FnZTogJ0ZhaWxlZCB0byBjcmVhdGUgSGFzdXJhIHNjaGVkdWxlZCBldmVudC4nLFxuICAgICAgICAgIGRldGFpbHM6IHJlcyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBjcmVhdGluZyBIYXN1cmEgc2NoZWR1bGVkIGV2ZW50IHRyaWdnZXI6JywgZSk7XG4gICAgY29uc3QgZXJyb3JEZXRhaWxzID0gZS5yZXNwb25zZT8uYm9keSB8fCBlLm1lc3NhZ2UgfHwgZTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0hBU1VSQV9NRVRBREFUQV9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBFcnJvciBjcmVhdGluZyBIYXN1cmEgc2NoZWR1bGVkIGV2ZW50OiAke2UubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBlcnJvckRldGFpbHMsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB1cHNlcnRBdXRvcGlsb3RPbmUgPSBhc3luYyAoXG4gIGF1dG9waWxvdDogQXV0b3BpbG90VHlwZVxuKTogUHJvbWlzZTxBdXRvcGlsb3RBcGlSZXNwb25zZTxBdXRvcGlsb3RUeXBlIHwgbnVsbD4+ID0+IHtcbiAgaWYgKCFhdXRvcGlsb3QgfHwgIWF1dG9waWxvdC5pZCB8fCAhYXV0b3BpbG90LnVzZXJJZCkge1xuICAgIC8vIEJhc2ljIHZhbGlkYXRpb25cbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnQXV0b3BpbG90IG9iamVjdCB3aXRoIGlkIGFuZCB1c2VySWQgaXMgcmVxdWlyZWQuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnVXBzZXJ0QXV0b3BpbG90T25lJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIG11dGF0aW9uIFVwc2VydEF1dG9waWxvdE9uZSgkYXV0b3BpbG90OiBBdXRvcGlsb3RfaW5zZXJ0X2lucHV0ISkge1xuICAgICAgICAgICAgICAgIGluc2VydF9BdXRvcGlsb3Rfb25lKG9iamVjdDogJGF1dG9waWxvdCwgb25fY29uZmxpY3Q6IHtjb25zdHJhaW50OiBBdXRvcGlsb3RfcGtleSwgdXBkYXRlX2NvbHVtbnM6IFtcbiAgICAgICAgICAgICAgICBwYXlsb2FkLFxuICAgICAgICAgICAgICAgIHNjaGVkdWxlQXQsXG4gICAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICAgICAgdXBkYXRlZEF0LFxuICAgICAgICAgICAgICAgIF19KSB7XG4gICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgIHBheWxvYWRcbiAgICAgICAgICAgICAgICBzY2hlZHVsZUF0XG4gICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGF1dG9waWxvdCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgaW5zZXJ0X0F1dG9waWxvdF9vbmU6IEF1dG9waWxvdFR5cGUgfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyBzdWNjZXNzZnVsbHkgdXBzZXJ0ZWQgYXV0b3BpbG90IG9uZScpO1xuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiByZXM/LmRhdGE/Lmluc2VydF9BdXRvcGlsb3Rfb25lIHx8IG51bGwgfTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgdXBzZXJ0aW5nIGF1dG9waWxvdCBvbmU6JywgZSk7XG4gICAgY29uc3QgZXJyb3JEZXRhaWxzID0gZS5yZXNwb25zZT8uYm9keSB8fCBlLm1lc3NhZ2UgfHwgZTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0hBU1VSQV9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gdXBzZXJ0IGF1dG9waWxvdDogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZXJyb3JEZXRhaWxzLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgY3JlYXRlSW5pdGlhbEZlYXR1cmVzQXBwbHlUb0V2ZW50VHJpZ2dlciA9IGFzeW5jIChcbiAgb2xkQXV0b3BpbG90OiBBdXRvcGlsb3RUeXBlLFxuICBvbGRCb2R5OiBTY2hlZHVsZUFzc2lzdFdpdGhNZWV0aW5nUXVldWVCb2R5VHlwZVxuKTogUHJvbWlzZTxBdXRvcGlsb3RBcGlSZXNwb25zZTx2b2lkPj4gPT4ge1xuICAvLyBSZXR1cm5zIHZvaWQgb24gc3VjY2Vzc1xuICBpZiAoXG4gICAgIW9sZEF1dG9waWxvdCB8fFxuICAgICFvbGRCb2R5IHx8XG4gICAgIW9sZEJvZHkudXNlcklkIHx8XG4gICAgIW9sZEJvZHkud2luZG93RW5kRGF0ZSB8fFxuICAgICFvbGRCb2R5LnRpbWV6b25lIHx8XG4gICAgIW9sZEJvZHkud2luZG93U3RhcnREYXRlIHx8XG4gICAgIW9sZEF1dG9waWxvdC50aW1lem9uZVxuICApIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnTWlzc2luZyBjcml0aWNhbCBhdXRvcGlsb3Qgb3IgYm9keSBwYXJhbWV0ZXJzLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBjb25zdCB1c2VyUHJlZmVyZW5jZXNSZXNwb25zZSA9IGF3YWl0IGdldFVzZXJQcmVmZXJlbmNlcyhvbGRCb2R5LnVzZXJJZCk7XG4gICAgaWYgKCF1c2VyUHJlZmVyZW5jZXNSZXNwb25zZS5vayB8fCAhdXNlclByZWZlcmVuY2VzUmVzcG9uc2UuZGF0YSkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICBgRmFpbGVkIHRvIGdldCB1c2VyIHByZWZlcmVuY2VzOiAke3VzZXJQcmVmZXJlbmNlc1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlIHx8ICdVbmtub3duIGVycm9yJ31gXG4gICAgICApO1xuICAgIH1cbiAgICBjb25zdCB1c2VyUHJlZmVyZW5jZXMgPSB1c2VyUHJlZmVyZW5jZXNSZXNwb25zZS5kYXRhO1xuXG4gICAgY29uc3Qgc3RhcnRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5zdGFydFRpbWVzO1xuICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICAgIGRheWpzKG9sZEJvZHkud2luZG93RW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihvbGRCb2R5LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudG9EYXRlKClcbiAgICApO1xuXG4gICAgY29uc3QgYXBwbGljYWJsZVN0YXJ0VGltZSA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCk7XG4gICAgaWYgKCFhcHBsaWNhYmxlU3RhcnRUaW1lKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgIGBObyBhcHBsaWNhYmxlIHN0YXJ0IHRpbWUgZm91bmQgZm9yIGRheU9mV2Vla0ludCAke2RheU9mV2Vla0ludH0uYFxuICAgICAgKTtcbiAgICB9XG4gICAgY29uc3Qgc3RhcnRIb3VyID0gYXBwbGljYWJsZVN0YXJ0VGltZS5ob3VyO1xuICAgIGNvbnN0IHJhbmRvbVN0YXJ0SG91ciA9IGdldFJhbmRvbUludEluY2x1c2l2ZShcbiAgICAgIDAsXG4gICAgICBzdGFydEhvdXIgPiAwID8gc3RhcnRIb3VyIC0gMSA6IDBcbiAgICApOyAvLyBFbnN1cmUgcG9zaXRpdmUgcmFuZ2VcbiAgICBjb25zdCByYW5kb21TdGFydE1pbnV0ZSA9IGdldFJhbmRvbUludEluY2x1c2l2ZSgwLCA1OSk7XG5cbiAgICBjb25zdCBuZXdXaW5kb3dTdGFydERhdGUgPSBkYXlqcyhvbGRCb2R5LndpbmRvd1N0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHoob2xkQm9keS50aW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5ob3VyKHJhbmRvbVN0YXJ0SG91cilcbiAgICAgIC5taW51dGUocmFuZG9tU3RhcnRNaW51dGUpXG4gICAgICAuZm9ybWF0KCk7XG4gICAgY29uc3QgbmV3V2luZG93RW5kRGF0ZSA9IGRheWpzKG9sZEJvZHkud2luZG93U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihvbGRCb2R5LnRpbWV6b25lLCB0cnVlKVxuICAgICAgLmhvdXIocmFuZG9tU3RhcnRIb3VyKVxuICAgICAgLm1pbnV0ZShyYW5kb21TdGFydE1pbnV0ZSlcbiAgICAgIC5hZGQoNiwgJ2QnKVxuICAgICAgLmZvcm1hdCgpO1xuXG4gICAgY29uc3QgbmV3Qm9keTogU2NoZWR1bGVBc3Npc3RXaXRoTWVldGluZ1F1ZXVlQm9keVR5cGUgPSB7XG4gICAgICAuLi5vbGRCb2R5LFxuICAgICAgd2luZG93U3RhcnREYXRlOiBuZXdXaW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlOiBuZXdXaW5kb3dFbmREYXRlLFxuICAgIH07XG4gICAgY29uc3QgbmV3QXV0b3BpbG90OiBBdXRvcGlsb3RUeXBlID0ge1xuICAgICAgLi4ub2xkQXV0b3BpbG90LFxuICAgICAgc2NoZWR1bGVBdDogZGF5anMobmV3V2luZG93U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KG9sZEF1dG9waWxvdC50aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnV0YygpXG4gICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgIHBheWxvYWQ6IG5ld0JvZHksXG4gICAgfTtcblxuICAgIGNvbnN0IHRyaWdnZXJSZXNwb25zZSA9IGF3YWl0IGNyZWF0ZURhaWx5RmVhdHVyZXNBcHBseUV2ZW50VHJpZ2dlcihcbiAgICAgIG5ld0F1dG9waWxvdCxcbiAgICAgIG5ld0JvZHlcbiAgICApO1xuICAgIGlmICghdHJpZ2dlclJlc3BvbnNlLm9rIHx8ICF0cmlnZ2VyUmVzcG9uc2UuZGF0YSkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICBgRmFpbGVkIHRvIGNyZWF0ZSBkYWlseSBmZWF0dXJlcyB0cmlnZ2VyOiAke3RyaWdnZXJSZXNwb25zZS5lcnJvcj8ubWVzc2FnZSB8fCAnVW5rbm93biBlcnJvcid9YFxuICAgICAgKTtcbiAgICB9XG4gICAgbmV3QXV0b3BpbG90LmlkID0gdHJpZ2dlclJlc3BvbnNlLmRhdGE7IC8vIGF1dG9waWxvdElkIGlzIGV2ZW50X2lkIGZyb20gSGFzdXJhXG5cbiAgICBjb25zdCB1cHNlcnRSZXNwb25zZSA9IGF3YWl0IHVwc2VydEF1dG9waWxvdE9uZShuZXdBdXRvcGlsb3QpO1xuICAgIGlmICghdXBzZXJ0UmVzcG9uc2Uub2spIHtcbiAgICAgIC8vIElmIHVwc2VydCBmYWlscywgc2hvdWxkIHdlIHRyeSB0byBkZWxldGUgdGhlIHNjaGVkdWxlZCBldmVudD8gQ29tcGxleCByb2xsYmFjay5cbiAgICAgIC8vIEZvciBub3csIGp1c3QgcmVwb3J0IHRoZSB1cHNlcnQgZmFpbHVyZS5cbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgYEZhaWxlZCB0byB1cHNlcnQgYXV0b3BpbG90IGRhdGEgYWZ0ZXIgY3JlYXRpbmcgdHJpZ2dlcjogJHt1cHNlcnRSZXNwb25zZS5lcnJvcj8ubWVzc2FnZSB8fCAnVW5rbm93biBlcnJvcid9YFxuICAgICAgKTtcbiAgICB9XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHVuZGVmaW5lZCB9O1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBjcmVhdGluZyBpbml0aWFsIGZlYXR1cmVzIGFwcGx5IHRvIGV2ZW50IHRyaWdnZXI6JywgZSk7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdJTlRFUk5BTF9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gY3JlYXRlIGluaXRpYWwgdHJpZ2dlcjogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZS50b1N0cmluZygpLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdEF1dG9waWxvdHNHaXZlblVzZXJJZCA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmdcbik6IFByb21pc2U8QXV0b3BpbG90QXBpUmVzcG9uc2U8QXV0b3BpbG90VHlwZSB8IG51bGw+PiA9PiB7XG4gIC8vIFJldHVybiBzaW5nbGUgb3IgbnVsbCwgYXMgY3VycmVudCBsb2dpYyByZXR1cm5zIFswXVxuICBpZiAoIXVzZXJJZCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogeyBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsIG1lc3NhZ2U6ICdVc2VyIElEIGlzIHJlcXVpcmVkLicgfSxcbiAgICB9O1xuICB9XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdMaXN0QXV0b3BpbG90c0dpdmVuVXNlcklkJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IExpc3RBdXRvcGlsb3RzR2l2ZW5Vc2VySWQoJHVzZXJJZDogdXVpZCEpIHtcbiAgICAgICAgICAgICAgICBBdXRvcGlsb3Qod2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9fSkge1xuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBwYXlsb2FkXG4gICAgICAgICAgICAgICAgICAgIHNjaGVkdWxlQXRcbiAgICAgICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgQXV0b3BpbG90OiBBdXRvcGlsb3RUeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyBzdWNjZXNzZnVsbHkgbGlzdGVkIGF1dG9waWxvdHMgZ2l2ZW4gdXNlcklkJyk7XG4gICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHJlcz8uZGF0YT8uQXV0b3BpbG90Py5bMF0gfHwgbnVsbCB9O1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBsaXN0aW5nIGF1dG9waWxvdHMgZ2l2ZW4gdXNlcklkOicsIGUpO1xuICAgIGNvbnN0IGVycm9yRGV0YWlscyA9IGUucmVzcG9uc2U/LmJvZHkgfHwgZS5tZXNzYWdlIHx8IGU7XG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdIQVNVUkFfRVJST1InLFxuICAgICAgICBtZXNzYWdlOiBgRmFpbGVkIHRvIGxpc3QgYXV0b3BpbG90czogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZXJyb3JEZXRhaWxzLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZGVsZXRlQXV0b3BpbG90R2l2ZW5JZCA9IGFzeW5jIChcbiAgaWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxBdXRvcGlsb3RBcGlSZXNwb25zZTxBdXRvcGlsb3RUeXBlIHwgbnVsbD4+ID0+IHtcbiAgaWYgKCFpZCkge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6ICdBdXRvcGlsb3QgSUQgaXMgcmVxdWlyZWQgZm9yIGRlbGV0aW9uLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0RlbGV0ZUF1dG9waWxvdEJ5SWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgbXV0YXRpb24gRGVsZXRlQXV0b3BpbG90QnlJZCgkaWQ6IHV1aWQhKSB7XG4gICAgICAgICAgICAgICAgZGVsZXRlX0F1dG9waWxvdF9ieV9wayhpZDogJGlkKSB7XG4gICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgIHBheWxvYWRcbiAgICAgICAgICAgICAgICBzY2hlZHVsZUF0XG4gICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgICAgYDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBpZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgZGVsZXRlX0F1dG9waWxvdF9ieV9wazogQXV0b3BpbG90VHlwZSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuICAgIGNvbnNvbGUubG9nKHJlcywgJyBkZWxldGVkIGF1dG9waWxvdCBieSBpZCcpO1xuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiByZXM/LmRhdGE/LmRlbGV0ZV9BdXRvcGlsb3RfYnlfcGsgfHwgbnVsbCB9O1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBkZWxldGluZyBhdXRvcGlsb3QgYnkgaWQ6JywgZSk7XG4gICAgY29uc3QgZXJyb3JEZXRhaWxzID0gZS5yZXNwb25zZT8uYm9keSB8fCBlLm1lc3NhZ2UgfHwgZTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0hBU1VSQV9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gZGVsZXRlIGF1dG9waWxvdDogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZXJyb3JEZXRhaWxzLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3Qgb25TY2hlZHVsZURhaWx5RmVhdHVyZXNBcHBseTdEYXlXaW5kb3dUb0V2ZW50VHJpZ2dlciA9IGFzeW5jIChcbiAgb2xkQXV0b3BpbG90OiBBdXRvcGlsb3RUeXBlLFxuICBvbGRCb2R5OiBTY2hlZHVsZUFzc2lzdFdpdGhNZWV0aW5nUXVldWVCb2R5VHlwZVxuKTogUHJvbWlzZTxBdXRvcGlsb3RBcGlSZXNwb25zZTx2b2lkPj4gPT4ge1xuICBpZiAoIW9sZEF1dG9waWxvdCB8fCAhb2xkQXV0b3BpbG90LnVzZXJJZCB8fCAhb2xkQm9keSB8fCAhb2xkQm9keS51c2VySWQpIHtcbiAgICAvLyBCYXNpYyB2YWxpZGF0aW9uXG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiBmYWxzZSxcbiAgICAgIGVycm9yOiB7XG4gICAgICAgIGNvZGU6ICdWQUxJREFUSU9OX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ09sZCBhdXRvcGlsb3QgYW5kIGJvZHkgd2l0aCB1c2VySWQgYXJlIHJlcXVpcmVkLicsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbiAgdHJ5IHtcbiAgICBjb25zdCBkYkF1dG9waWxvdFJlc3BvbnNlID0gYXdhaXQgbGlzdEF1dG9waWxvdHNHaXZlblVzZXJJZChcbiAgICAgIG9sZEF1dG9waWxvdC51c2VySWRcbiAgICApO1xuICAgIGlmICghZGJBdXRvcGlsb3RSZXNwb25zZS5vaykge1xuICAgICAgLy8gRXJyb3IgZmV0Y2hpbmcsIGNyaXRpY2FsXG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgIGBGYWlsZWQgdG8gdmVyaWZ5IGV4aXN0aW5nIGF1dG9waWxvdDogJHtkYkF1dG9waWxvdFJlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICk7XG4gICAgfVxuICAgIGlmICghZGJBdXRvcGlsb3RSZXNwb25zZS5kYXRhPy5pZCkge1xuICAgICAgLy8gQXV0b3BpbG90IHdhcyBkZWxldGVkIG9yIG5vdCBmb3VuZFxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBBdXRvcGlsb3QgZm9yIHVzZXIgJHtvbGRBdXRvcGlsb3QudXNlcklkfSBzZWVtcyB0byBoYXZlIGJlZW4gZGVsZXRlZC4gSGFsdGluZyB0cmlnZ2VyLmBcbiAgICAgICk7XG4gICAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogdW5kZWZpbmVkIH07IC8vIE5vdCBhbiBlcnJvciwgYnV0IG9wZXJhdGlvbiBzdG9wc1xuICAgIH1cbiAgICBjb25zdCBkYkF1dG9waWxvdCA9IGRiQXV0b3BpbG90UmVzcG9uc2UuZGF0YTsgLy8gU2FmZSB0byB1c2Ugbm93XG5cbiAgICBjb25zdCB0cmlnZ2VyRmVhdHVyZXNSZXNwb25zZSA9IGF3YWl0IHRyaWdnZXJGZWF0dXJlc0FwcGx5VXJsKG9sZEJvZHkpO1xuICAgIGlmICghdHJpZ2dlckZlYXR1cmVzUmVzcG9uc2Uub2spIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgYEZhaWxlZCB0byB0cmlnZ2VyIGZlYXR1cmVzIGFwcGx5IFVSTDogJHt0cmlnZ2VyRmVhdHVyZXNSZXNwb25zZS5lcnJvcj8ubWVzc2FnZX1gXG4gICAgICApO1xuICAgIH1cblxuICAgIGNvbnN0IHVzZXJQcmVmZXJlbmNlc1Jlc3BvbnNlID0gYXdhaXQgZ2V0VXNlclByZWZlcmVuY2VzKG9sZEJvZHkudXNlcklkKTtcbiAgICBpZiAoIXVzZXJQcmVmZXJlbmNlc1Jlc3BvbnNlLm9rIHx8ICF1c2VyUHJlZmVyZW5jZXNSZXNwb25zZS5kYXRhKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgIGBGYWlsZWQgdG8gZ2V0IHVzZXIgcHJlZmVyZW5jZXM6ICR7dXNlclByZWZlcmVuY2VzUmVzcG9uc2UuZXJyb3I/Lm1lc3NhZ2V9YFxuICAgICAgKTtcbiAgICB9XG4gICAgY29uc3QgdXNlclByZWZlcmVuY2VzID0gdXNlclByZWZlcmVuY2VzUmVzcG9uc2UuZGF0YTtcblxuICAgIGNvbnN0IHN0YXJ0VGltZXMgPSB1c2VyUHJlZmVyZW5jZXMuc3RhcnRUaW1lcztcbiAgICBjb25zdCBkYXlPZldlZWtJbnQgPSBnZXRJU09EYXkoXG4gICAgICBkYXlqcyhvbGRCb2R5LndpbmRvd0VuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoob2xkQm9keS50aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnRvRGF0ZSgpXG4gICAgKTtcbiAgICBjb25zdCBhcHBsaWNhYmxlU3RhcnRUaW1lID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KTtcbiAgICBpZiAoIWFwcGxpY2FibGVTdGFydFRpbWUpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgYE5vIGFwcGxpY2FibGUgc3RhcnQgdGltZSBmb3VuZCBmb3IgZGF5T2ZXZWVrSW50ICR7ZGF5T2ZXZWVrSW50fSBmb3IgdXNlciAke29sZEJvZHkudXNlcklkfS5gXG4gICAgICApO1xuICAgIH1cbiAgICBjb25zdCBzdGFydEhvdXIgPSBhcHBsaWNhYmxlU3RhcnRUaW1lLmhvdXI7XG4gICAgY29uc3QgcmFuZG9tU3RhcnRIb3VyID0gZ2V0UmFuZG9tSW50SW5jbHVzaXZlKFxuICAgICAgMCxcbiAgICAgIHN0YXJ0SG91ciA+IDAgPyBzdGFydEhvdXIgLSAxIDogMFxuICAgICk7XG4gICAgY29uc3QgcmFuZG9tU3RhcnRNaW51dGUgPSBnZXRSYW5kb21JbnRJbmNsdXNpdmUoMCwgNTkpO1xuXG4gICAgY29uc3QgbmV3V2luZG93U3RhcnREYXRlID0gZGF5anMob2xkQm9keS53aW5kb3dTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KG9sZEJvZHkudGltZXpvbmUsIHRydWUpXG4gICAgICAuaG91cihyYW5kb21TdGFydEhvdXIpXG4gICAgICAubWludXRlKHJhbmRvbVN0YXJ0TWludXRlKVxuICAgICAgLmFkZCgxLCAnZCcpXG4gICAgICAuZm9ybWF0KCk7XG4gICAgY29uc3QgbmV3V2luZG93RW5kRGF0ZSA9IGRheWpzKG9sZEJvZHkud2luZG93U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihvbGRCb2R5LnRpbWV6b25lLCB0cnVlKVxuICAgICAgLmhvdXIocmFuZG9tU3RhcnRIb3VyKVxuICAgICAgLm1pbnV0ZShyYW5kb21TdGFydE1pbnV0ZSlcbiAgICAgIC5hZGQoNywgJ2QnKVxuICAgICAgLmZvcm1hdCgpO1xuXG4gICAgY29uc3QgbmV3Qm9keTogU2NoZWR1bGVBc3Npc3RXaXRoTWVldGluZ1F1ZXVlQm9keVR5cGUgPSB7XG4gICAgICAuLi5vbGRCb2R5LFxuICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgd2luZG93RW5kRGF0ZTogbmV3V2luZG93RW5kRGF0ZSxcbiAgICB9O1xuICAgIGNvbnN0IG5ld0F1dG9waWxvdDogQXV0b3BpbG90VHlwZSA9IHtcbiAgICAgIC4uLm9sZEF1dG9waWxvdCxcbiAgICAgIHNjaGVkdWxlQXQ6IGRheWpzKG5ld1dpbmRvd1N0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihvbGRBdXRvcGlsb3QudGltZXpvbmUsIHRydWUpXG4gICAgICAgIC51dGMoKVxuICAgICAgICAuZm9ybWF0KCksXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICBwYXlsb2FkOiBuZXdCb2R5LFxuICAgIH07XG5cbiAgICBjb25zdCBjcmVhdGVUcmlnZ2VyUmVzcG9uc2UgPSBhd2FpdCBjcmVhdGVEYWlseUZlYXR1cmVzQXBwbHlFdmVudFRyaWdnZXIoXG4gICAgICBuZXdBdXRvcGlsb3QsXG4gICAgICBuZXdCb2R5XG4gICAgKTtcbiAgICBpZiAoIWNyZWF0ZVRyaWdnZXJSZXNwb25zZS5vayB8fCAhY3JlYXRlVHJpZ2dlclJlc3BvbnNlLmRhdGEpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgYEZhaWxlZCB0byBjcmVhdGUgbmV3IGRhaWx5IGZlYXR1cmVzIHRyaWdnZXI6ICR7Y3JlYXRlVHJpZ2dlclJlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICk7XG4gICAgfVxuICAgIG5ld0F1dG9waWxvdC5pZCA9IGNyZWF0ZVRyaWdnZXJSZXNwb25zZS5kYXRhO1xuXG4gICAgY29uc3QgZGVsZXRlUmVzcG9uc2UgPSBhd2FpdCBkZWxldGVBdXRvcGlsb3RHaXZlbklkKGRiQXV0b3BpbG90LmlkKTtcbiAgICBpZiAoIWRlbGV0ZVJlc3BvbnNlLm9rKSB7XG4gICAgICAvLyBMb2cgdGhpcywgYnV0IHByb2NlZWQgdG8gdXBzZXJ0IHRoZSBuZXcgb25lIGFzIHRoZSBzY2hlZHVsZWQgZXZlbnQgaXMgYWxyZWFkeSBjcmVhdGVkLlxuICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICBgRmFpbGVkIHRvIGRlbGV0ZSBvbGQgYXV0b3BpbG90ICR7ZGJBdXRvcGlsb3QuaWR9OiAke2RlbGV0ZVJlc3BvbnNlLmVycm9yPy5tZXNzYWdlfS4gTmV3IHRyaWdnZXIgJHtuZXdBdXRvcGlsb3QuaWR9IGlzIGFscmVhZHkgc2NoZWR1bGVkLmBcbiAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc3QgdXBzZXJ0UmVzcG9uc2UgPSBhd2FpdCB1cHNlcnRBdXRvcGlsb3RPbmUobmV3QXV0b3BpbG90KTtcbiAgICBpZiAoIXVwc2VydFJlc3BvbnNlLm9rKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgIGBGYWlsZWQgdG8gdXBzZXJ0IG5ldyBhdXRvcGlsb3QgJHtuZXdBdXRvcGlsb3QuaWR9OiAke3Vwc2VydFJlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICk7XG4gICAgfVxuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiB1bmRlZmluZWQgfTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgICdFcnJvciBpbiBvblNjaGVkdWxlRGFpbHlGZWF0dXJlc0FwcGx5N0RheVdpbmRvd1RvRXZlbnRUcmlnZ2VyOicsXG4gICAgICBlXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0lOVEVSTkFMX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byByZXNjaGVkdWxlIGRhaWx5IGZlYXR1cmVzIHRyaWdnZXI6ICR7ZS5tZXNzYWdlfWAsXG4gICAgICAgIGRldGFpbHM6IGUudG9TdHJpbmcoKSxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwc2VydEF1dG9waWxvdE1hbnkgPSBhc3luYyAoXG4gIGF1dG9waWxvdHM6IEF1dG9waWxvdFR5cGVbXVxuKTogUHJvbWlzZTxBdXRvcGlsb3RBcGlSZXNwb25zZTxBdXRvcGlsb3RUeXBlW10gfCBudWxsPj4gPT4ge1xuICBpZiAoIWF1dG9waWxvdHMgfHwgYXV0b3BpbG90cy5sZW5ndGggPT09IDApIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnQXV0b3BpbG90cyBhcnJheSBjYW5ub3QgYmUgZW1wdHkuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnVXBzZXJ0QXV0b3BpbG90TWFueSc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgIG11dGF0aW9uIFVwc2VydEF1dG9waWxvdE1hbnkoJGF1dG9waWxvdHM6IFtBdXRvcGlsb3RfaW5zZXJ0X2lucHV0IV0hKSB7XG4gICAgICAgICAgICBpbnNlcnRfQXV0b3BpbG90KG9iamVjdHM6ICRhdXRvcGlsb3RzLCBvbl9jb25mbGljdDoge2NvbnN0cmFpbnQ6IEF1dG9waWxvdF9wa2V5LCB1cGRhdGVfY29sdW1uczogW1xuICAgICAgICAgICAgICAgICAgIHBheWxvYWQsXG4gICAgICAgICAgICAgICAgc2NoZWR1bGVBdCxcbiAgICAgICAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICAgICAgICB1cGRhdGVkQXQsXG4gICAgICAgICAgICBdfSkge1xuICAgICAgICAgICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICAgICAgICAgIHJldHVybmluZyB7XG4gICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgIHBheWxvYWRcbiAgICAgICAgICAgICAgICBzY2hlZHVsZUF0XG4gICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGF1dG9waWxvdHMsXG4gICAgfTtcbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBpbnNlcnRfQXV0b3BpbG90OiBBdXRvcGlsb3RUeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyBzdWNjZXNzZnVsbHkgdXBzZXJ0ZWQgYXV0b3BpbG90IG1hbnknKTtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogcmVzPy5kYXRhPy5pbnNlcnRfQXV0b3BpbG90IHx8IG51bGwgfTsgLy8gU2hvdWxkIGJlIHJlcy5kYXRhLmluc2VydF9BdXRvcGlsb3QucmV0dXJuaW5nIGZvciBhY3R1YWwgZGF0YVxuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciB1cHNlcnRpbmcgYXV0b3BpbG90IG1hbnk6JywgZSk7XG4gICAgY29uc3QgZXJyb3JEZXRhaWxzID0gZS5yZXNwb25zZT8uYm9keSB8fCBlLm1lc3NhZ2UgfHwgZTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0hBU1VSQV9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gdXBzZXJ0IGF1dG9waWxvdHM6ICR7ZS5tZXNzYWdlfWAsXG4gICAgICAgIGRldGFpbHM6IGVycm9yRGV0YWlscyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldEF1dG9waWxvdEdpdmVuSWQgPSBhc3luYyAoXG4gIGlkOiBzdHJpbmdcbik6IFByb21pc2U8QXV0b3BpbG90QXBpUmVzcG9uc2U8QXV0b3BpbG90VHlwZSB8IG51bGw+PiA9PiB7XG4gIGlmICghaWQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHsgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLCBtZXNzYWdlOiAnQXV0b3BpbG90IElEIGlzIHJlcXVpcmVkLicgfSxcbiAgICB9O1xuICB9XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdHZXRBdXRvcGlsb3RCeUlkJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IEdldEF1dG9waWxvdEJ5SWQoJGlkOiB1dWlkISkge1xuICAgICAgICAgICAgICAgIEF1dG9waWxvdF9ieV9wayhpZDogJGlkKSB7XG4gICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgIHBheWxvYWRcbiAgICAgICAgICAgICAgICBzY2hlZHVsZUF0XG4gICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG5cbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBpZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgQXV0b3BpbG90X2J5X3BrOiBBdXRvcGlsb3RUeXBlIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgc3VjY2Vzc2Z1bGx5IGdvdCBhdXRvcGlsb3QgZ2l2ZW4gSWQnKTtcbiAgICByZXR1cm4geyBvazogdHJ1ZSwgZGF0YTogcmVzPy5kYXRhPy5BdXRvcGlsb3RfYnlfcGsgfHwgbnVsbCB9O1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBnZXR0aW5nIGF1dG9waWxvdCBieSBJZDonLCBlKTtcbiAgICBjb25zdCBlcnJvckRldGFpbHMgPSBlLnJlc3BvbnNlPy5ib2R5IHx8IGUubWVzc2FnZSB8fCBlO1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnSEFTVVJBX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogYEZhaWxlZCB0byBnZXQgYXV0b3BpbG90IGJ5IElEOiAke2UubWVzc2FnZX1gLFxuICAgICAgICBkZXRhaWxzOiBlcnJvckRldGFpbHMsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBkZWxldGVTY2hlZHVsZWRFdmVudEZvckF1dG9waWxvdCA9IGFzeW5jIChcbiAgZXZlbnRJZDogc3RyaW5nXG4pOiBQcm9taXNlPEF1dG9waWxvdEFwaVJlc3BvbnNlPHsgc3VjY2VzczogYm9vbGVhbiB9Pj4gPT4ge1xuICBpZiAoIWV2ZW50SWQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ1ZBTElEQVRJT05fRVJST1InLFxuICAgICAgICBtZXNzYWdlOiAnU2NoZWR1bGVkIGV2ZW50IElEIGlzIHJlcXVpcmVkIGZvciBkZWxldGlvbi4nLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG4gIHRyeSB7XG4gICAgY29uc3QganNvbkJvZHkgPSB7XG4gICAgICB0eXBlOiAnZGVsZXRlX3NjaGVkdWxlZF9ldmVudCcsXG4gICAgICBhcmdzOiB7XG4gICAgICAgIHR5cGU6ICdvbmVfb2ZmJyxcbiAgICAgICAgZXZlbnRfaWQ6IGV2ZW50SWQsXG4gICAgICB9LFxuICAgIH07XG5cbiAgICBjb25zdCByZXMgPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYU1ldGFkYXRhVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IGpzb25Cb2R5LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7IC8vIEFzc3VtaW5nIHJlcyBpcyB7bWVzc2FnZTogXCJzdWNjZXNzXCJ9IG9yIHNpbWlsYXIgZnJvbSBIYXN1cmEgZXZlbnQgdHJpZ2dlciBBUElcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyBzdWNjZXNzZnVsbHkgZGVsZXRlZCBzY2hlZHVsZWQgZXZlbnQgdHJpZ2dlcicpO1xuICAgIC8vIENoZWNrIGFjdHVhbCByZXNwb25zZSBzdHJ1Y3R1cmUgZnJvbSBIYXN1cmEgZm9yIHRoaXMgdHlwZSBvZiBjYWxsXG4gICAgaWYgKChyZXMgYXMgYW55KT8ubWVzc2FnZSA9PT0gJ3N1Y2Nlc3MnKSB7XG4gICAgICAvLyBOZWVkIHRvIGNhc3Qgb3IgZGVmaW5lIHR5cGUgZm9yIEhhc3VyYSBtZXRhZGF0YSByZXNwb25zZVxuICAgICAgcmV0dXJuIHsgb2s6IHRydWUsIGRhdGE6IHsgc3VjY2VzczogdHJ1ZSB9IH07XG4gICAgfSBlbHNlIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnSEFTVVJBX01FVEFEQVRBX0VSUk9SJyxcbiAgICAgICAgICBtZXNzYWdlOiAnRmFpbGVkIHRvIGRlbGV0ZSBzY2hlZHVsZWQgZXZlbnQsIHVuZXhwZWN0ZWQgcmVzcG9uc2UuJyxcbiAgICAgICAgICBkZXRhaWxzOiByZXMsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgZGVsZXRpbmcgc2NoZWR1bGVkIGV2ZW50IGZvciBhdXRvcGlsb3Q6JywgZSk7XG4gICAgY29uc3QgZXJyb3JEZXRhaWxzID0gZS5yZXNwb25zZT8uYm9keSB8fCBlLm1lc3NhZ2UgfHwgZTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogJ0hBU1VSQV9NRVRBREFUQV9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6IGBGYWlsZWQgdG8gZGVsZXRlIHNjaGVkdWxlZCBldmVudDogJHtlLm1lc3NhZ2V9YCxcbiAgICAgICAgZGV0YWlsczogZXJyb3JEZXRhaWxzLFxuICAgICAgfSxcbiAgICB9O1xuICB9XG59O1xuIl19