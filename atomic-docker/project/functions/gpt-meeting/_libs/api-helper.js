import { ATOMIC_SUBDOMAIN_PATTERN, MAX_CHARACTER_LIMIT, NUMBER_TO_REMOVE_FOR_SUBDOMAIN_SLICE, defaultOpenAIAPIKey, googleCalendarResource, googleClientIdAndroid, googleClientIdAtomicWeb, googleClientIdIos, googleClientIdWeb, googleClientSecretAtomicWeb, googleClientSecretWeb, googleTokenUrl, hasuraAdminSecret, hasuraGraphUrl, openAIChatGPTModel, zoomBaseTokenUrl, zoomBaseUrl, zoomClientId, zoomClientSecret, zoomIVForPass, zoomPassKey, zoomResourceName, zoomSaltForPass, } from './constants';
import qs from 'qs';
import crypto from 'crypto';
import got from 'got';
import { v4 as uuid } from 'uuid';
import OpenAI from 'openai';
import { extractDateTimeExampleInput, extractDateTimeExampleOutput, extractDateTimePrompt, generateMeetingSummaryInput, generateMeetingSummaryOutput, generateMeetingSummaryPrompt, isMeetingTimeScheduledExampleInput, isMeetingTimeScheduledExampleOutput, isMeetingTimeScheduledPrompt, summarizeAvailabilityExampleInput, summarizeAvailabilityExampleOutput, summarizeAvailabilityPrompt, summarizeAvailabilityResponsesPrompt, summarizeAvailabilityResponsesPromptExampleInput, summarizeAvailabilityResponsesPromptExampleOutput, } from './prompts';
import { google } from 'googleapis';
import dayjs from 'dayjs';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import axios from 'axios';
import _ from 'lodash';
import * as cheerio from 'cheerio';
import quotedPrintable from 'quoted-printable';
import { getISODay } from 'date-fns';
dayjs.extend(duration);
dayjs.extend(isBetween);
dayjs.extend(timezone);
dayjs.extend(utc);
export const callOpenAI = async (prompt, model = 'gpt-3.5-turbo', userData, openai, exampleInput, exampleOutput) => {
    try {
        // assistant
        const completion = await openai.chat.completions.create({
            model,
            messages: [
                { role: 'system', content: prompt },
                exampleInput && {
                    role: 'user',
                    content: exampleInput,
                },
                exampleOutput && {
                    role: 'assistant',
                    content: exampleOutput,
                },
                { role: 'user', content: userData },
            ]?.filter((m) => !!m),
        });
        console.log(completion.choices[0]?.message?.content, ' response from openaiapi');
        return completion?.choices?.[0]?.message?.content;
    }
    catch (error) {
        if (error.response) {
            console.log(error.response.status, ' openai error status');
            console.log(error.response.data, ' openai error data');
        }
        else {
            console.log(error.message, ' openai error message');
        }
    }
};
export const getCalendarIntegration = async (userId, resource) => {
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
        console.log(res, ' res inside getCalendarIntegration');
        if (res?.data?.Calendar_Integration?.length > 0) {
            return res?.data?.Calendar_Integration?.[0];
        }
    }
    catch (e) {
        console.log(e, ' unable to get calendar integration');
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
    }
    catch (e) {
        console.log(e, ' unable to update calendar integration');
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
            encryptedRefreshToken,
        };
    }
    else {
        return { encryptedToken };
    }
};
export const getZoomIntegration = async (userId) => {
    try {
        const { id, token, expiresAt, refreshToken } = await getCalendarIntegration(userId, zoomResourceName);
        const decryptedTokens = decryptZoomTokens(token, refreshToken);
        return {
            id,
            expiresAt,
            ...decryptedTokens,
        };
    }
    catch (e) {
        console.log(e, ' unable to get zoom integration');
    }
};
export const updateZoomIntegration = async (id, accessToken, expiresIn) => {
    try {
        const { encryptedToken } = encryptZoomTokens(accessToken);
        await updateCalendarIntegration(id, encryptedToken, expiresIn);
    }
    catch (e) {
        console.log(e, ' unable to update zoom integration');
    }
};
export const refreshZoomToken = async (refreshToken) => {
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
    }
    catch (e) {
        console.log(e, ' unable to refresh zoom token');
    }
};
export const getZoomAPIToken = async (userId) => {
    let integrationId = '';
    try {
        console.log('getZoomAPIToken called');
        const { id, token, expiresAt, refreshToken } = await getZoomIntegration(userId);
        if (!refreshToken) {
            console.log('zoom not active, no refresh token');
            return;
        }
        integrationId = id;
        console.log(id, token, expiresAt, refreshToken, ' id, token, expiresAt, refreshToken');
        if (dayjs().isAfter(dayjs(expiresAt)) || !token) {
            const res = await refreshZoomToken(refreshToken);
            console.log(res, ' res from refreshZoomToken');
            await updateZoomIntegration(id, res.access_token, res.expires_in);
            return res.access_token;
        }
        return token;
    }
    catch (e) {
        console.log(e, ' unable to get zoom api token');
        await updateCalendarIntegration(integrationId, null, null, false);
    }
};
export const createZoomMeeting = async (zoomToken, startDate, timezone, agenda, duration, contactName, contactEmail, meetingInvitees) => {
    try {
        //valdiate
        if (dayjs().isAfter(dayjs(startDate))) {
            console.log(' starttime is in the past');
            throw new Error('starttime is in the past');
        }
        console.log(dayjs(startDate?.slice(0, 19))
            .tz(timezone, true)
            .format('YYYY-MM-DDTHH:mm:ss'), timezone, agenda, duration, ` dayjs(startDate?.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DDTHH:mm:ss'),
            timezone,
            agenda,
            duration, createZoomMeeting called`);
        let settings = {};
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
        let reqBody = {};
        if (Object.keys(settings)?.length > 0) {
            reqBody.settings = settings;
        }
        reqBody = {
            ...reqBody,
            start_time: dayjs(startDate?.slice(0, 19))
                .tz(timezone, true)
                .utc()
                .format(),
            // timezone,
            agenda,
            duration,
        };
        console.log(reqBody, ' reqBody inside createZoomMeeting');
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' unable to create zoom meeting');
    }
};
export const refreshGoogleToken = async (refreshToken, clientType) => {
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
        /*
            {
              "access_token": "1/fFAGRNJru1FTz70BzhT3Zg",
              "expires_in": 3920, // add seconds to now
              "scope": "https://www.googleapis.com/auth/drive.metadata.readonly",
              "token_type": "Bearer"
            }
            */
    }
    catch (e) {
        console.log(e, ' unable to refresh google token');
    }
};
export const getGoogleAPIToken = async (userId, resource, clientType) => {
    let integrationId = '';
    try {
        const { id, token, expiresAt, refreshToken } = await getCalendarIntegration(userId, resource);
        integrationId = id;
        console.log(id, token, expiresAt, refreshToken, ' id, token, expiresAt, refreshToken');
        if (dayjs().isAfter(dayjs(expiresAt)) || !token) {
            const res = await refreshGoogleToken(refreshToken, clientType);
            console.log(res, ' res from refreshGoogleToken');
            await updateCalendarIntegration(id, res.access_token, res.expires_in);
            return res.access_token;
        }
        return token;
    }
    catch (e) {
        console.log(e, ' unable to get api token');
        await updateCalendarIntegration(integrationId, null, null, false);
    }
};
export const createGoogleEvent = async (userId, calendarId, clientType, generatedId, endDateTime, // either endDateTime or endDate - all day vs specific period
startDateTime, conferenceDataVersion, maxAttendees, sendUpdates, anyoneCanAddSelf, attendees, conferenceData, summary, description, timezone, // required for recurrence
startDate, // all day
endDate, // all day
extendedProperties, guestsCanInviteOthers, guestsCanModify, guestsCanSeeOtherGuests, originalStartDateTime, originalStartDate, recurrence, reminders, source, status, transparency, visibility, iCalUID, attendeesOmitted, hangoutLink, privateCopy, locked, attachments, eventType, location, colorId) => {
    try {
        console.log(generatedId, conferenceDataVersion, conferenceData, ' generatedId, conferenceDataVersion, conferenceData inside createGoogleEvent');
        // get token =
        const token = await getGoogleAPIToken(userId, googleCalendarResource, clientType);
        const googleCalendar = google.calendar({
            version: 'v3',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });
        // create request body
        let data = {};
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
        }
        else if (conferenceData?.entryPoints?.[0]) {
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
        });
        console.log(res.data);
        console.log(res?.data, ' res?.data from googleCreateEvent');
        return {
            id: `${res?.data?.id}#${calendarId}`,
            googleEventId: res?.data?.id,
            generatedId,
            calendarId,
            generatedEventId: generatedId?.split('#')[0],
        };
    }
    catch (e) {
        console.log(e, ' createGoogleEvent');
    }
};
export const upsertEvents = async (events) => {
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
        _.uniqBy(events, 'id').forEach((e) => console.log(e?.id, e, 'id, e inside upsertEventsPostPlanner '));
        const variables = {
            events: _.uniqBy(events, 'id'),
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
        console.log(response, response?.data?.insert_Event?.affected_rows, ' response after upserting events');
        response?.data?.insert_Event?.returning?.forEach((e) => console.log(e, ' returning  response after upserting events'));
        return response;
    }
    catch (e) {
        console.log(e, ' unable to update event');
    }
};
export const insertReminders = async (reminders) => {
    try {
        // validate
        if (!(reminders?.filter((e) => !!e?.eventId)?.length > 0)) {
            return;
        }
        reminders.forEach((r) => console.log(r, ' reminder inside insertReminders'));
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
        console.log(response?.data?.insert_Reminder?.returning, ' this is response in insertReminders');
        response?.data?.insert_Reminder?.returning.forEach((r) => console.log(r, ' response in insertReminder'));
    }
    catch (e) {
        console.log(e, ' unable to insertReminders');
    }
};
export const insertConference = async (conference) => {
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
        console.log(res, ' successfully inserted one conference');
        return res?.data?.insert_Conference_one;
    }
    catch (e) {
        console.log(e, ' unable to insert conference');
    }
};
export const processEmailContent = async (content) => {
    try {
        const rawContent = content;
        console.log(rawContent, ' raw content');
        let html = '';
        // const html_regex = HTML_REGEX_PATTERN
        // const htmls = html_regex.exec(rawContent)
        // console.log(htmls, ' htmls')
        // html = htmls?.[0]
        // validate by matching
        // use cheerio to get content
        const decodedRawContent = decodeURIComponent(quotedPrintable.decode(rawContent));
        const $ = cheerio.load(decodedRawContent);
        $('div').each((_, element) => {
            console.log($(element).text(), ' $(element).text()');
            html += $(element).text();
        });
        console.log(html, ' html');
        if (!html) {
            console.log('html is not present');
            return;
        }
        const short_html = html?.length > MAX_CHARACTER_LIMIT
            ? html.slice(0, MAX_CHARACTER_LIMIT)
            : html;
        console.log(short_html, ' short_html');
        console.log(short_html.length, ' short_html.length');
        const url_regex = ATOMIC_SUBDOMAIN_PATTERN;
        const urls = url_regex.exec(decodedRawContent);
        console.log(urls, ' urls');
        let url = urls?.[0];
        console.log(url, ' url');
        if (!url) {
            console.log('no url present');
            return;
        }
        const urlObject = new URL(url.slice(0, url.length - NUMBER_TO_REMOVE_FOR_SUBDOMAIN_SLICE));
        // const searchParams = new URLSearchParams(urlObject.search)
        console.log(urlObject.href, ' urlObject.href');
        // console.log(searchParams, ' searchParams')
        url = url.slice(0, url.length - NUMBER_TO_REMOVE_FOR_SUBDOMAIN_SLICE);
        const urlQIndex = url.indexOf('?');
        const urlShort = url.slice(urlQIndex + 1);
        const atomicQSParamsString = urlShort;
        const rawQueryParamsObject = qs.parse(atomicQSParamsString);
        console.log(rawQueryParamsObject, ' rawQueryParamsObject');
        const newQueryParamsObject = {};
        for (const key in rawQueryParamsObject) {
            const newKey = key.replace('amp;', '');
            if (typeof rawQueryParamsObject[key] === 'string') {
                const oldValue = rawQueryParamsObject[key] || '';
                const newValue = oldValue?.replace('" target="_blank">Atomic</a> :)</pr', '');
                newQueryParamsObject[newKey] = newValue;
            }
            else {
                newQueryParamsObject[newKey] = rawQueryParamsObject[key];
            }
        }
        console.log(newQueryParamsObject, ' newQueryParamsObject');
        if (!newQueryParamsObject?.userId) {
            console.log(' newQueryParamsObject not parsed properly');
            return;
        }
        const queryParamsObject = newQueryParamsObject;
        const userId = queryParamsObject?.userId;
        const timezone = queryParamsObject?.timezone;
        const attendeeEmails = queryParamsObject?.attendeeEmails;
        const duration = queryParamsObject?.duration;
        const calendarId = queryParamsObject?.calendarId;
        const startTime = queryParamsObject?.startTime;
        const name = queryParamsObject?.name;
        const primaryEmail = queryParamsObject?.primaryEmail;
        // const attachments = queryParamsObject?.attachments
        // validate
        if (!userId) {
            throw new Error('no userId present inside query params');
        }
        if (!timezone) {
            throw new Error('no timezone provided');
        }
        if (!(attendeeEmails?.length > 0)) {
            throw new Error('no attendee emails');
        }
        if (!duration) {
            throw new Error('no duration provided');
        }
        if (!name) {
            throw new Error('no name provided');
        }
        if (!calendarId) {
            throw new Error('no calendarId provided');
        }
        if (!primaryEmail) {
            throw new Error('no new primaryEmail');
        }
        // get openai key
        const openai = new OpenAI({
            apiKey: defaultOpenAIAPIKey,
        });
        // check for whether a meeting time is scheduled or not
        const isMeetingPrompt = isMeetingTimeScheduledPrompt;
        const isMeetingUserData = `email body: ${short_html}`;
        const openAIResForMeetingTimeScheduled = await callOpenAI(isMeetingPrompt, openAIChatGPTModel, isMeetingUserData, openai, isMeetingTimeScheduledExampleInput, isMeetingTimeScheduledExampleOutput);
        // parse JSON
        console.log(openAIResForMeetingTimeScheduled, ' openAIResForMeetingTimeScheduled');
        // ChatGPT response
        // { "time_provided": true }
        const startIndex = openAIResForMeetingTimeScheduled?.indexOf('{');
        const endIndex = openAIResForMeetingTimeScheduled?.indexOf('}');
        const isMeetingTimeScheduledString = openAIResForMeetingTimeScheduled.slice(startIndex, endIndex + 1);
        const isMeetingScheduledObject = JSON.parse(isMeetingTimeScheduledString);
        // stop if meeting time is not scheduled
        if (!isMeetingScheduledObject?.time_provided) {
            console.log('no meeting time provided');
            return;
        }
        // extract data and time
        const extractDateAndTimePrompt = extractDateTimePrompt;
        const extractDateTimeUserData = `start time: ${startTime} \n timezone: ${timezone} \n email History: ${short_html}`;
        const openAIResForExtractDateTime = await callOpenAI(extractDateAndTimePrompt, openAIChatGPTModel, extractDateTimeUserData, openai, extractDateTimeExampleInput, extractDateTimeExampleOutput);
        const startIndex2 = openAIResForExtractDateTime?.indexOf('{');
        const endIndex2 = openAIResForExtractDateTime?.indexOf('}');
        const extractDateTimeString = openAIResForExtractDateTime.slice(startIndex2, endIndex2 + 1);
        const extractDateTimeObject = JSON.parse(extractDateTimeString);
        // ISO 8601 format time
        const meetingTime = extractDateTimeObject?.meeting_time;
        // validate meetingTime
        if (!meetingTime) {
            throw new Error('unable to extract date and time');
        }
        // schedule meeting
        // generate meeting summary and notes
        const generateSummaryAndNotesPrompt = generateMeetingSummaryPrompt;
        const generateSummaryAndNotesUserData = `start time: ${startTime} \n timezone: ${timezone} \n email History: ${short_html}`;
        const openAIResForSummaryAndNotes = await callOpenAI(generateSummaryAndNotesPrompt, openAIChatGPTModel, generateSummaryAndNotesUserData, openai, generateMeetingSummaryInput, generateMeetingSummaryOutput);
        const startIndex3 = openAIResForSummaryAndNotes?.indexOf('{');
        const endIndex3 = openAIResForSummaryAndNotes?.indexOf('}');
        const summaryAndNotesString = openAIResForSummaryAndNotes.slice(startIndex3, endIndex3 + 1);
        const summaryAndNotesObject = JSON.parse(summaryAndNotesString);
        // get primary calendar
        const primaryCalendar = await getGlobalCalendar(userId);
        // validate
        if (!primaryCalendar?.id) {
            throw new Error('no primary calendar found inside createAgenda');
        }
        // get client type
        const calIntegration = await getCalendarIntegration(userId, googleCalendarResource);
        // validate
        if (!calIntegration?.clientType) {
            throw new Error('no client type inside calendar integration inside create agenda');
        }
        const eventId = uuid();
        const remindersString = queryParamsObject?.reminders;
        const remindersToUpdateEventId = [];
        if (remindersString) {
            const newReminders = remindersString.map((r) => ({
                id: uuid(),
                userId,
                eventId, // generatedId
                timezone,
                minutes: parseInt(r, 10),
                useDefault: false,
                updatedAt: dayjs().format(),
                createdDate: dayjs().format(),
                deleted: false,
            }));
            remindersToUpdateEventId.push(...newReminders);
        }
        const googleReminder = {
            overrides: remindersToUpdateEventId?.map((r) => ({
                method: 'email',
                minutes: r?.minutes,
            })),
            useDefault: false,
        };
        // create attendees to create if any
        const attendees = [];
        if (attendeeEmails?.length > 0) {
            for (const aEmail of attendeeEmails) {
                const attendee = {
                    id: uuid(),
                    userId,
                    name: primaryEmail === aEmail ? name : undefined,
                    emails: [{ primary: true, value: aEmail }],
                    eventId, // generatedId
                    updatedAt: dayjs().format(),
                    createdDate: dayjs().format(),
                    deleted: false,
                };
                attendees.push(attendee);
            }
        }
        if (queryParamsObject?.enableConference) {
            let conference = {};
            // create conference object
            const zoomToken = await getZoomAPIToken(userId);
            conference = zoomToken
                ? {}
                : {
                    id: uuid(),
                    userId,
                    calendarId: calendarId || primaryCalendar?.id,
                    app: 'google',
                    name,
                    notes: summaryAndNotesObject?.notes,
                    updatedAt: dayjs().format(),
                    createdDate: dayjs().format(),
                    deleted: false,
                    isHost: true,
                };
            if (queryParamsObject?.conferenceApp === 'zoom' && zoomToken) {
                if (zoomToken) {
                    console.log(zoomToken, ' zoomToken inside if (zoomToken)');
                    const zoomObject = await createZoomMeeting(zoomToken, meetingTime, timezone, summaryAndNotesObject?.summary, parseInt(duration, 10), name, primaryEmail, attendeeEmails);
                    console.log(zoomObject, ' zoomObject after createZoomMeeting');
                    if (zoomObject) {
                        conference = {
                            id: `${zoomObject?.id}`,
                            userId: userId,
                            calendarId,
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
                        };
                    }
                }
            }
            const eventToUpsertLocal = {
                id: eventId,
                userId,
                title: summaryAndNotesObject?.summary,
                startDate: dayjs(meetingTime).tz(timezone).format(),
                endDate: dayjs(meetingTime)
                    .tz(timezone)
                    .add(parseInt(duration, 10), 'm')
                    .format(),
                allDay: false,
                notes: summaryAndNotesObject?.notes,
                timezone,
                createdDate: dayjs().format(),
                deleted: false,
                priority: 1,
                isFollowUp: false,
                isPreEvent: false,
                isPostEvent: false,
                modifiable: false,
                anyoneCanAddSelf: queryParamsObject?.anyoneCanAddSelf === 'true' ? true : false,
                guestsCanInviteOthers: queryParamsObject?.guestsCanInviteOthers === 'true' ? true : false,
                guestsCanSeeOtherGuests: queryParamsObject?.guestsCanSeeOtherGuests === 'true' ? true : false,
                transparency: queryParamsObject?.transparency,
                visibility: queryParamsObject?.visibility,
                originalStartDate: undefined,
                originalAllDay: false,
                summary: summaryAndNotesObject?.summary,
                updatedAt: dayjs().format(),
                calendarId: calendarId || primaryCalendar?.id,
                eventId: undefined,
                conferenceId: conference?.id,
                attachments: queryParamsObject?.attachments,
                sendUpdates: queryParamsObject?.sendUpdates,
                duration: parseInt(queryParamsObject?.duration, 10),
            };
            const googleResValue = await createGoogleEvent(userId, calendarId, calIntegration?.clientType, eventToUpsertLocal?.id, eventToUpsertLocal?.endDate, eventToUpsertLocal?.startDate, conference?.id ? 1 : 0, 2, eventToUpsertLocal?.sendUpdates, eventToUpsertLocal?.anyoneCanAddSelf, attendeeEmails?.map((a) => ({ email: a })), conference?.id
                ? {
                    type: conference?.app === 'zoom'
                        ? 'addOn'
                        : 'hangoutsMeet',
                    name: conference?.name,
                    conferenceId: conference?.id,
                    entryPoints: conference?.entryPoints,
                    createRequest: conference?.app === 'google'
                        ? {
                            requestId: conference?.requestId,
                            conferenceSolutionKey: {
                                type: 'hangoutsMeet',
                            },
                        }
                        : undefined,
                }
                : undefined, summaryAndNotesObject?.summary, summaryAndNotesObject?.notes, timezone, undefined, undefined, undefined, eventToUpsertLocal?.guestsCanInviteOthers, eventToUpsertLocal?.guestsCanModify, eventToUpsertLocal?.guestsCanSeeOtherGuests, eventToUpsertLocal?.originalStartDate, undefined, undefined, remindersToUpdateEventId?.length > 0 ? googleReminder : undefined, undefined, undefined, eventToUpsertLocal?.transparency, eventToUpsertLocal?.visibility, undefined, undefined, undefined, undefined, undefined, eventToUpsertLocal?.attachments, 'default', undefined, undefined);
            eventToUpsertLocal.id = googleResValue.id;
            eventToUpsertLocal.eventId = googleResValue.googleEventId;
            // update reminders for event Id
            remindersToUpdateEventId?.map((r) => ({
                ...r,
                eventId: eventToUpsertLocal.id,
            }));
            // update attendees for eventId
            attendees?.map((a) => ({ ...a, eventId: eventToUpsertLocal.id }));
            // insert conference
            await insertConference(conference);
            // insert events
            await upsertEvents([eventToUpsertLocal]);
            // insert reminders
            if (remindersToUpdateEventId?.length > 0) {
                await insertReminders(remindersToUpdateEventId);
            }
            if (attendees?.length > 0) {
                await insertAttendeesforEvent(attendees);
            }
        }
        else {
            const eventToUpsertLocal = {
                id: eventId,
                userId,
                title: summaryAndNotesObject?.summary,
                startDate: dayjs(meetingTime).tz(timezone).format(),
                endDate: dayjs(meetingTime)
                    .tz(timezone)
                    .add(parseInt(duration, 10), 'm')
                    .format(),
                allDay: false,
                notes: summaryAndNotesObject?.notes,
                timezone,
                createdDate: dayjs().format(),
                deleted: false,
                priority: 1,
                isFollowUp: false,
                isPreEvent: false,
                isPostEvent: false,
                modifiable: false,
                anyoneCanAddSelf: queryParamsObject?.anyoneCanAddSelf === 'true' ? true : false,
                guestsCanInviteOthers: queryParamsObject?.guestsCanInviteOthers === 'true' ? true : false,
                guestsCanSeeOtherGuests: queryParamsObject?.guestsCanSeeOtherGuests === 'true' ? true : false,
                transparency: queryParamsObject?.transparency,
                visibility: queryParamsObject?.visibility,
                originalStartDate: undefined,
                originalAllDay: false,
                summary: summaryAndNotesObject?.summary,
                updatedAt: dayjs().format(),
                calendarId: calendarId || primaryCalendar?.id,
                eventId: undefined,
                attachments: queryParamsObject?.attachments,
                sendUpdates: queryParamsObject?.sendUpdates,
                duration: parseInt(queryParamsObject?.duration, 10),
            };
            const googleResValue = await createGoogleEvent(userId, calendarId, calIntegration?.clientType, eventToUpsertLocal?.id, eventToUpsertLocal?.endDate, eventToUpsertLocal?.startDate, 0, 2, eventToUpsertLocal?.sendUpdates, eventToUpsertLocal?.anyoneCanAddSelf, attendeeEmails?.map((a) => ({ email: a })), undefined, summaryAndNotesObject?.summary, summaryAndNotesObject?.notes, timezone, undefined, undefined, undefined, eventToUpsertLocal?.guestsCanInviteOthers, eventToUpsertLocal?.guestsCanModify, eventToUpsertLocal?.guestsCanSeeOtherGuests, eventToUpsertLocal?.originalStartDate, undefined, undefined, remindersToUpdateEventId?.length > 0 ? googleReminder : undefined, undefined, undefined, eventToUpsertLocal?.transparency, eventToUpsertLocal?.visibility, undefined, undefined, undefined, undefined, undefined, eventToUpsertLocal?.attachments, 'default', undefined, undefined);
            eventToUpsertLocal.id = googleResValue.id;
            eventToUpsertLocal.eventId = googleResValue.googleEventId;
            // update reminders for event Id
            remindersToUpdateEventId?.map((r) => ({
                ...r,
                eventId: eventToUpsertLocal.id,
            }));
            // update attendees for eventId
            attendees?.map((a) => ({ ...a, eventId: eventToUpsertLocal.id }));
            // insert events
            await upsertEvents([eventToUpsertLocal]);
            // insert reminders
            if (remindersToUpdateEventId?.length > 0) {
                await insertReminders(remindersToUpdateEventId);
            }
            if (attendees?.length > 0) {
                await insertAttendeesforEvent(attendees);
            }
        }
    }
    catch (e) {
        console.log(e, ' unable to process email content');
    }
};
export const listEventsForUserGivenDates = async (userId, senderStartDate, senderEndDate
// senderTimezone: string,
// receiverTimezone: string,
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
        // get events
        // local date
        // const startDateInReceiverTimezone = dayjs(senderStartDate.slice(0, 19)).tz(receiverTimezone, true)
        // const endDateInReceiverTimezone = dayjs((senderEndDate.slice(0, 19))).tz(receiverTimezone, true)
        // const startDateInSenderTimezone = dayjs(startDateInReceiverTimezone).format().slice(0, 19)
        // const endDateInSenderTimezone = dayjs(endDateInReceiverTimezone).format().slice(0, 19)
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
                    startDate: senderStartDate,
                    endDate: senderEndDate,
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
        return null;
    }
};
export const generateAvailableSlotsForDate = (slotDuration, senderStartDateInReceiverTimezone, senderPreferences, receiverTimezone, senderTimezone, notAvailableSlotsInEventTimezone, isFirstDay, isLastDay, senderEndDateInReceiverTimezone) => {
    console.log(senderTimezone, ' senderTimezone');
    console.log(receiverTimezone, ' receiverTimezone');
    if (isFirstDay && isLastDay && senderEndDateInReceiverTimezone) {
        const endTimesBySender = senderPreferences.endTimes;
        const dayOfWeekIntAsReceiver = getISODay(dayjs(senderStartDateInReceiverTimezone?.slice(0, 19))
            .tz(receiverTimezone, true)
            .toDate());
        const dayOfMonthAsReceiver = dayjs(senderStartDateInReceiverTimezone?.slice(0, 19))
            .tz(receiverTimezone, true)
            .date();
        let startHourAsReceiver = dayjs(senderStartDateInReceiverTimezone?.slice(0, 19))
            .tz(receiverTimezone, true)
            .hour();
        const flooredValue = Math.floor(60 / slotDuration);
        let minuteValueAsReceiver = 0;
        if (dayjs(senderStartDateInReceiverTimezone).tz(receiverTimezone).minute() !==
            0) {
            for (let i = 0; i < flooredValue; i++) {
                const endMinutes = (i + 1) * slotDuration;
                const startMinutes = i * slotDuration;
                if (dayjs(senderStartDateInReceiverTimezone)
                    .tz(receiverTimezone)
                    .isBetween(dayjs(senderStartDateInReceiverTimezone)
                    .tz(receiverTimezone)
                    .minute(startMinutes), dayjs(senderStartDateInReceiverTimezone)
                    .tz(receiverTimezone)
                    .minute(endMinutes), 'minute', '[)')) {
                    minuteValueAsReceiver = endMinutes;
                }
            }
        }
        if (dayjs(senderStartDateInReceiverTimezone)
            .tz(receiverTimezone)
            .isBetween(dayjs(senderStartDateInReceiverTimezone)
            .tz(receiverTimezone)
            .minute(flooredValue * slotDuration), dayjs(senderStartDateInReceiverTimezone)
            .tz(receiverTimezone)
            .minute(59), 'minute', '[)')) {
            startHourAsReceiver += 1;
            minuteValueAsReceiver = 0;
        }
        const startMinuteAsReceiver = minuteValueAsReceiver;
        const endHourWorkBySender = endTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)?.hour ??
            20;
        const endMinuteWorkBySender = endTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)
            ?.minutes ?? 0;
        const endHourAsReceiver = dayjs(senderEndDateInReceiverTimezone)
            .tz(receiverTimezone)
            .hour();
        const endMinuteAsReceiver = dayjs(senderEndDateInReceiverTimezone)
            .tz(receiverTimezone)
            .minute();
        // validate values before calculating
        const startTimes = senderPreferences.startTimes;
        const workStartHourBySender = startTimes?.find((i) => i.day === dayOfWeekIntAsReceiver)?.hour || 8;
        const workStartMinuteBySender = startTimes?.find((i) => i.day === dayOfWeekIntAsReceiver)?.minutes || 0;
        if (dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .isAfter(dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .hour(endHourWorkBySender)
            .minute(endMinuteWorkBySender))) {
            // return empty as outside of work time
            return [];
        }
        // change to work start time as sender start time before work start time
        if (dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .isBefore(dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .hour(workStartHourBySender)
            .minute(workStartMinuteBySender))) {
            const startDuration = dayjs.duration({
                hours: workStartHourBySender,
                minutes: workStartMinuteBySender,
            });
            const endDuration = dayjs.duration({
                hours: endHourAsReceiver,
                minutes: endMinuteAsReceiver,
            });
            const totalDuration = endDuration.subtract(startDuration);
            const totalMinutes = totalDuration.asMinutes();
            const availableSlotsInReceiverTimezone = [];
            console.log(senderStartDateInReceiverTimezone, endTimesBySender, dayOfWeekIntAsReceiver, dayOfMonthAsReceiver, startHourAsReceiver, startMinuteAsReceiver, endHourAsReceiver, endMinuteAsReceiver, timezone, `startDate, endTimes, dayOfWeekIntByUser, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`);
            for (let i = 0; i < totalMinutes; i += slotDuration) {
                if (i > totalMinutes) {
                    continue;
                }
                availableSlotsInReceiverTimezone.push({
                    id: uuid(),
                    startDate: dayjs(senderStartDateInReceiverTimezone)
                        .tz(senderTimezone)
                        .hour(workStartHourBySender)
                        .minute(workStartMinuteBySender)
                        .tz(receiverTimezone)
                        .add(i, 'minute')
                        .second(0)
                        .format(),
                    endDate: dayjs(senderStartDateInReceiverTimezone)
                        .tz(senderTimezone)
                        .hour(workStartHourBySender)
                        .minute(workStartMinuteBySender)
                        .tz(receiverTimezone)
                        .add(i + slotDuration, 'minute')
                        .second(0)
                        .format(),
                });
            }
            console.log(availableSlotsInReceiverTimezone, ' timeSlots inside generateTimeSlots for first day where startDate is before work start time');
            // filter out unavailable times
            const filteredAvailableSlotsInReceiverTimezone = availableSlotsInReceiverTimezone.filter((a) => {
                const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
                    const partA = dayjs(a.endDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .isBetween(dayjs(na.startDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .add(1, 'm'), dayjs(na.endDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .subtract(1, 'm'), 'm', '[]');
                    const partB = dayjs(a.startDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .isBetween(dayjs(na.startDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .add(1, 'm'), dayjs(na.endDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .subtract(1, 'm'), 'm', '[]');
                    const partC = dayjs(na.startDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .format('YYYY-MM-DDTHH:mm') ===
                        dayjs(a.startDate)
                            .tz(receiverTimezone)
                            .second(0)
                            .format('YYYY-MM-DDTHH:mm') &&
                        dayjs(na.endDate)
                            .tz(receiverTimezone)
                            .second(0)
                            .format('YYYY-MM-DDTHH:mm') ===
                            dayjs(a.endDate)
                                .tz(receiverTimezone)
                                .second(0)
                                .format('YYYY-MM-DDTHH:mm');
                    const isNotAvailable = partA || partB || partC;
                    // console.log(a, na, ' a, na')
                    return isNotAvailable;
                });
                console.log(foundIndex, ' foundIndex');
                if (foundIndex !== undefined && foundIndex > -1) {
                    return false;
                }
                return true;
            });
            console.log(filteredAvailableSlotsInReceiverTimezone, ' filteredAvailableSlots');
            return filteredAvailableSlotsInReceiverTimezone;
        }
        const startDuration = dayjs.duration({
            hours: startHourAsReceiver,
            minutes: startMinuteAsReceiver,
        });
        const endDuration = dayjs.duration({
            hours: endHourAsReceiver,
            minutes: endMinuteAsReceiver,
        });
        const totalDuration = endDuration.subtract(startDuration);
        const totalMinutes = totalDuration.asMinutes();
        console.log(totalMinutes, ' totalMinutes inside first and last same day');
        const availableSlotsInReceiverTimezone = [];
        console.log(senderStartDateInReceiverTimezone, endTimesBySender, dayOfWeekIntAsReceiver, endHourWorkBySender, endMinuteWorkBySender, receiverTimezone, `startDate, endTimes, dayOfWeekInt, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside first & last Day inside generateTimeslots`);
        for (let i = 0; i < totalMinutes; i += slotDuration) {
            if (i > totalMinutes) {
                continue;
            }
            availableSlotsInReceiverTimezone.push({
                id: uuid(),
                startDate: dayjs(senderStartDateInReceiverTimezone)
                    .tz(receiverTimezone)
                    .hour(startHourAsReceiver)
                    .minute(startMinuteAsReceiver)
                    .add(i, 'minute')
                    .second(0)
                    .format(),
                endDate: dayjs(senderStartDateInReceiverTimezone)
                    .tz(receiverTimezone)
                    .hour(startHourAsReceiver)
                    .minute(startMinuteAsReceiver)
                    .add(i + slotDuration, 'minute')
                    .second(0)
                    .format(),
            });
        }
        console.log(availableSlotsInReceiverTimezone, ' availableSlots inside first & last same day');
        const filteredAvailableSlotsInReceiverTimezone = availableSlotsInReceiverTimezone.filter((a) => {
            const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
                const partA = dayjs(a.endDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .isBetween(dayjs(na.startDate).tz(receiverTimezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(receiverTimezone).second(0).subtract(1, 'm'), 'm', '[]');
                const partB = dayjs(a.startDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .isBetween(dayjs(na.startDate).tz(receiverTimezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(receiverTimezone).second(0).subtract(1, 'm'), 'm', '[]');
                const partC = dayjs(na.startDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm') ===
                    dayjs(a.startDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .format('YYYY-MM-DDTHH:mm') &&
                    dayjs(na.endDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .format('YYYY-MM-DDTHH:mm') ===
                        dayjs(a.endDate)
                            .tz(receiverTimezone)
                            .second(0)
                            .format('YYYY-MM-DDTHH:mm');
                const isNotAvailable = partA || partB || partC;
                // console.log(a, na, ' a, na')
                return isNotAvailable;
            });
            console.log(foundIndex, ' foundIndex');
            if (foundIndex !== undefined && foundIndex > -1) {
                return false;
            }
            return true;
        });
        console.log(filteredAvailableSlotsInReceiverTimezone, ' filteredAvailableSlots');
        return filteredAvailableSlotsInReceiverTimezone;
    }
    if (isFirstDay) {
        // firstday can be started outside of work time
        // if firstDay start is after end time -- return []
        const endTimesBySender = senderPreferences.endTimes;
        const dayOfWeekIntAsReceiver = getISODay(dayjs(senderStartDateInReceiverTimezone).tz(receiverTimezone).toDate());
        // month is zero-indexed
        // const month = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).month()
        const dayOfMonthAsReceiver = dayjs(senderStartDateInReceiverTimezone)
            .tz(receiverTimezone)
            .date();
        let startHourAsReceiver = dayjs(senderStartDateInReceiverTimezone)
            .tz(receiverTimezone)
            .hour();
        const startHourBySender = dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .hour();
        const startMinuteBySender = dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .minute();
        // create slot sizes
        const flooredValue = Math.floor(60 / slotDuration);
        let minuteValueAsReceiver = 0;
        if (dayjs(senderStartDateInReceiverTimezone).tz(receiverTimezone).minute() !==
            0) {
            for (let i = 0; i < flooredValue; i++) {
                const endMinutes = (i + 1) * slotDuration;
                const startMinutes = i * slotDuration;
                if (dayjs(senderStartDateInReceiverTimezone)
                    .tz(receiverTimezone)
                    .isBetween(dayjs(senderStartDateInReceiverTimezone)
                    .tz(receiverTimezone)
                    .minute(startMinutes), dayjs(senderStartDateInReceiverTimezone)
                    .tz(receiverTimezone)
                    .minute(endMinutes), 'minute', '[)')) {
                    minuteValueAsReceiver = endMinutes;
                }
            }
        }
        if (dayjs(senderStartDateInReceiverTimezone)
            .tz(receiverTimezone)
            .isBetween(dayjs(senderStartDateInReceiverTimezone)
            .tz(receiverTimezone)
            .minute(flooredValue * slotDuration), dayjs(senderStartDateInReceiverTimezone)
            .tz(receiverTimezone)
            .minute(59), 'minute', '[)')) {
            startHourAsReceiver += 1;
            minuteValueAsReceiver = 0;
        }
        const startMinuteAsReceiver = minuteValueAsReceiver;
        // convert to user timezone so everything is linked to user timezone
        const endHourBySender = endTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)?.hour ??
            20;
        const endMinuteBySender = endTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)
            ?.minutes ?? 0;
        // validate values before calculating
        const startTimes = senderPreferences.startTimes;
        const workStartHourBySender = startTimes?.find((i) => i.day === dayOfWeekIntAsReceiver)?.hour || 8;
        const workStartMinuteBySender = startTimes?.find((i) => i.day === dayOfWeekIntAsReceiver)?.minutes || 0;
        if (dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .isAfter(dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .hour(endHourBySender)
            .minute(endMinuteBySender))) {
            // return empty as outside of work time
            return [];
        }
        // change to work start time as host start time before work start time
        if (dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .isBefore(dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .hour(workStartHourBySender)
            .minute(workStartMinuteBySender))) {
            const startDuration = dayjs.duration({
                hours: workStartHourBySender,
                minutes: workStartMinuteBySender,
            });
            const endDuration = dayjs.duration({
                hours: endHourBySender,
                minutes: endMinuteBySender,
            });
            const totalDuration = endDuration.subtract(startDuration);
            const totalMinutes = totalDuration.asMinutes();
            const availableSlotsInReceiverTimezone = [];
            console.log(senderStartDateInReceiverTimezone, endTimesBySender, dayOfWeekIntAsReceiver, dayOfMonthAsReceiver, startHourAsReceiver, startMinuteAsReceiver, endHourBySender, endMinuteBySender, timezone, `startDate, endTimes, dayOfWeekIntByUser, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`);
            for (let i = 0; i < totalMinutes; i += slotDuration) {
                if (i > totalMinutes) {
                    continue;
                }
                availableSlotsInReceiverTimezone.push({
                    id: uuid(),
                    startDate: dayjs(senderStartDateInReceiverTimezone)
                        .tz(senderTimezone)
                        .hour(workStartHourBySender)
                        .minute(workStartMinuteBySender)
                        .tz(receiverTimezone)
                        .add(i, 'minute')
                        .second(0)
                        .format(),
                    endDate: dayjs(senderStartDateInReceiverTimezone)
                        .tz(senderTimezone)
                        .hour(workStartHourBySender)
                        .minute(workStartMinuteBySender)
                        .tz(receiverTimezone)
                        .add(i + slotDuration, 'minute')
                        .second(0)
                        .format(),
                });
            }
            console.log(availableSlotsInReceiverTimezone, ' timeSlots inside generateTimeSlots for first day where startDate is before work start time');
            // filter out unavailable times
            const filteredAvailableSlotsInReceiverTimezone = availableSlotsInReceiverTimezone.filter((a) => {
                const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
                    const partA = dayjs(a.endDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .isBetween(dayjs(na.startDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .add(1, 'm'), dayjs(na.endDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .subtract(1, 'm'), 'm', '[]');
                    const partB = dayjs(a.startDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .isBetween(dayjs(na.startDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .add(1, 'm'), dayjs(na.endDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .subtract(1, 'm'), 'm', '[]');
                    const partC = dayjs(na.startDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .format('YYYY-MM-DDTHH:mm') ===
                        dayjs(a.startDate)
                            .tz(receiverTimezone)
                            .second(0)
                            .format('YYYY-MM-DDTHH:mm') &&
                        dayjs(na.endDate)
                            .tz(receiverTimezone)
                            .second(0)
                            .format('YYYY-MM-DDTHH:mm') ===
                            dayjs(a.endDate)
                                .tz(receiverTimezone)
                                .second(0)
                                .format('YYYY-MM-DDTHH:mm');
                    const isNotAvailable = partA || partB || partC;
                    // console.log(a, na, ' a, na')
                    return isNotAvailable;
                });
                console.log(foundIndex, ' foundIndex');
                if (foundIndex !== undefined && foundIndex > -1) {
                    return false;
                }
                return true;
            });
            console.log(filteredAvailableSlotsInReceiverTimezone, ' filteredAvailableSlots');
            return filteredAvailableSlotsInReceiverTimezone;
        }
        const startDuration = dayjs.duration({
            hours: startHourBySender,
            minutes: startMinuteBySender,
        });
        const endDuration = dayjs.duration({
            hours: endHourBySender,
            minutes: endMinuteBySender,
        });
        const totalDuration = endDuration.subtract(startDuration);
        const totalMinutes = totalDuration.asMinutes();
        const availableSlotsInReceiverTimezone = [];
        console.log(senderStartDateInReceiverTimezone, endTimesBySender, dayOfWeekIntAsReceiver, endHourBySender, endMinuteBySender, receiverTimezone, `startDate, endTimes, dayOfWeekInt, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`);
        for (let i = 0; i < totalMinutes; i += slotDuration) {
            if (i > totalMinutes) {
                continue;
            }
            availableSlotsInReceiverTimezone.push({
                id: uuid(),
                startDate: dayjs(senderStartDateInReceiverTimezone)
                    .tz(receiverTimezone)
                    .hour(startHourAsReceiver)
                    .minute(startMinuteAsReceiver)
                    .add(i, 'minute')
                    .second(0)
                    .format(),
                endDate: dayjs(senderStartDateInReceiverTimezone)
                    .tz(receiverTimezone)
                    .hour(startHourAsReceiver)
                    .minute(startMinuteAsReceiver)
                    .add(i + slotDuration, 'minute')
                    .second(0)
                    .format(),
            });
        }
        const filteredAvailableSlotsInReceiverTimezone = availableSlotsInReceiverTimezone.filter((a) => {
            const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
                const partA = dayjs(a.endDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .isBetween(dayjs(na.startDate).tz(receiverTimezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(receiverTimezone).second(0).subtract(1, 'm'), 'm', '[]');
                const partB = dayjs(a.startDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .isBetween(dayjs(na.startDate).tz(receiverTimezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(receiverTimezone).second(0).subtract(1, 'm'), 'm', '[]');
                const partC = dayjs(na.startDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm') ===
                    dayjs(a.startDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .format('YYYY-MM-DDTHH:mm') &&
                    dayjs(na.endDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .format('YYYY-MM-DDTHH:mm') ===
                        dayjs(a.endDate)
                            .tz(receiverTimezone)
                            .second(0)
                            .format('YYYY-MM-DDTHH:mm');
                const isNotAvailable = partA || partB || partC;
                // console.log(a, na, ' a, na')
                return isNotAvailable;
            });
            console.log(foundIndex, ' foundIndex');
            if (foundIndex !== undefined && foundIndex > -1) {
                return false;
            }
            return true;
        });
        console.log(filteredAvailableSlotsInReceiverTimezone, ' filteredAvailableSlots server timezone');
        return filteredAvailableSlotsInReceiverTimezone;
    }
    // not first day start from work start time schedule
    const startTimesBySender = senderPreferences.startTimes;
    const endTimesBySender = senderPreferences.endTimes;
    const dayOfWeekIntAsReceiver = getISODay(dayjs(senderStartDateInReceiverTimezone?.slice(0, 19))
        .tz(receiverTimezone, true)
        .toDate());
    const dayOfMonthAsReceiver = dayjs(senderStartDateInReceiverTimezone?.slice(0, 19))
        .tz(receiverTimezone, true)
        .date();
    // convert to user timezone so everything is linked to user timezone
    let endHourBySender = endTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)?.hour ?? 20;
    let endMinuteBySender = endTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)?.minutes ??
        0;
    // if last day change end time to hostStartDate provided
    if (isLastDay && senderEndDateInReceiverTimezone) {
        endHourBySender = dayjs(senderEndDateInReceiverTimezone)
            .tz(senderTimezone)
            .hour();
        // create slot sizes
        const flooredValue = Math.floor(60 / slotDuration);
        let minuteValueBySender = 0;
        for (let i = 0; i < flooredValue; i++) {
            const endMinutes = (i + 1) * slotDuration;
            const startMinutes = i * slotDuration;
            if (dayjs(senderEndDateInReceiverTimezone)
                .tz(senderTimezone)
                .isBetween(dayjs(senderEndDateInReceiverTimezone)
                .tz(senderTimezone)
                .minute(startMinutes), dayjs(senderEndDateInReceiverTimezone)
                .tz(senderTimezone)
                .minute(endMinutes), 'minute', '[)')) {
                minuteValueBySender = startMinutes;
            }
        }
        endMinuteBySender = minuteValueBySender;
    }
    const startHourBySender = startTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)
        ?.hour || 8;
    const startMinuteBySender = startTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)
        ?.minutes || 0;
    const startDuration = dayjs.duration({
        hours: startHourBySender,
        minutes: startMinuteBySender,
    });
    const endDuration = dayjs.duration({
        hours: endHourBySender,
        minutes: endMinuteBySender,
    });
    const totalDuration = endDuration.subtract(startDuration);
    const totalMinutes = totalDuration.asMinutes();
    const availableSlotsInReceiverTimezone = [];
    console.log(senderStartDateInReceiverTimezone, endTimesBySender, dayOfWeekIntAsReceiver, dayOfMonthAsReceiver, startHourBySender, startMinuteBySender, endHourBySender, endMinuteBySender, timezone, `startDate, endTimes, dayOfWeekIntByHost, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateAvailableslots`);
    for (let i = 0; i < totalMinutes; i += slotDuration) {
        if (i > totalMinutes) {
            continue;
        }
        availableSlotsInReceiverTimezone.push({
            id: uuid(),
            startDate: dayjs(senderStartDateInReceiverTimezone)
                .tz(senderTimezone)
                .hour(startHourBySender)
                .minute(startMinuteBySender)
                .tz(receiverTimezone)
                .add(i, 'minute')
                .second(0)
                .format(),
            endDate: dayjs(senderStartDateInReceiverTimezone)
                .tz(senderTimezone)
                .hour(startHourBySender)
                .minute(startMinuteBySender)
                .tz(receiverTimezone)
                .add(i + slotDuration, 'minute')
                .second(0)
                .format(),
        });
    }
    console.log(availableSlotsInReceiverTimezone, ' timeSlots inside generateTimeSlots not first day');
    console.log(notAvailableSlotsInEventTimezone, ' notAvailableSlotsInEventTimezone not first day');
    // filter out unavailable times
    const filteredAvailableSlotsInReceiverTimezone = availableSlotsInReceiverTimezone.filter((a) => {
        const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
            const partA = dayjs(a.endDate)
                .tz(receiverTimezone)
                .second(0)
                .isBetween(dayjs(na.startDate).tz(receiverTimezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(receiverTimezone).second(0).subtract(1, 'm'), 'm', '[]');
            const partB = dayjs(a.startDate)
                .tz(receiverTimezone)
                .second(0)
                .isBetween(dayjs(na.startDate).tz(receiverTimezone).second(0).add(1, 'm'), dayjs(na.endDate).tz(receiverTimezone).second(0).subtract(1, 'm'), 'm', '[]');
            const partC = dayjs(na.startDate)
                .tz(receiverTimezone)
                .second(0)
                .format('YYYY-MM-DDTHH:mm') ===
                dayjs(a.startDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm') &&
                dayjs(na.endDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm') ===
                    dayjs(a.endDate)
                        .tz(receiverTimezone)
                        .second(0)
                        .format('YYYY-MM-DDTHH:mm');
            const isNotAvailable = partA || partB || partC;
            // console.log(a, na, ' a, na')
            return isNotAvailable;
        });
        console.log(foundIndex, ' foundIndex');
        if (foundIndex !== undefined && foundIndex > -1) {
            return false;
        }
        return true;
    });
    console.log(filteredAvailableSlotsInReceiverTimezone, ' filteredAvailableSlots in receiverTimezone');
    // convert to receiverTimezone before returning values
    return filteredAvailableSlotsInReceiverTimezone;
};
export const generateAvailableSlotsforTimeWindow = (windowStartDate, windowEndDate, slotDuration, senderPreferences, receiverTimezone, senderTimezone, notAvailableSlotsInEventTimezone) => {
    const diffDays = dayjs(windowEndDate).diff(dayjs(windowStartDate), 'd');
    const startDatesForEachDay = [];
    const availableSlots = [];
    for (let i = 0; i <= diffDays; i++) {
        startDatesForEachDay.push(dayjs(windowStartDate.slice(0, 19))
            .tz(receiverTimezone, true)
            .add(i, 'day')
            .format());
    }
    if (diffDays < 1) {
        const generatedSlots = generateAvailableSlotsForDate(slotDuration, dayjs(windowStartDate.slice(0, 19)).tz(receiverTimezone, true).format(), senderPreferences, receiverTimezone, senderTimezone, notAvailableSlotsInEventTimezone, true, true, dayjs(windowEndDate.slice(0, 19)).tz(receiverTimezone, true).format());
        //  0123456789
        //  2020-04-02T08:02:17-05:00
        availableSlots.push(...generatedSlots);
    }
    else {
        for (let i = 0; i < startDatesForEachDay.length; i++) {
            const filteredNotAvailableSlotsInEventTimezone = notAvailableSlotsInEventTimezone?.filter((na) => dayjs(na?.startDate).tz(receiverTimezone).format('YYYY-MM-DD') ===
                dayjs(startDatesForEachDay?.[i])
                    .tz(receiverTimezone)
                    .format('YYYY-MM-DD'));
            if (i === 0) {
                const generatedSlots = generateAvailableSlotsForDate(slotDuration, startDatesForEachDay?.[i], senderPreferences, receiverTimezone, senderTimezone, filteredNotAvailableSlotsInEventTimezone, true, false, dayjs(windowEndDate.slice(0, 19)).tz(receiverTimezone, true).format());
                //  0123456789
                //  2020-04-02T08:02:17-05:00
                availableSlots.push(...generatedSlots);
                continue;
            }
            if (i === startDatesForEachDay.length - 1) {
                const generatedSlots = generateAvailableSlotsForDate(slotDuration, startDatesForEachDay?.[i], senderPreferences, receiverTimezone, senderTimezone, filteredNotAvailableSlotsInEventTimezone, false, true, dayjs(windowEndDate.slice(0, 19)).tz(receiverTimezone, true).format());
                availableSlots.push(...generatedSlots);
                continue;
            }
            const generatedSlots = generateAvailableSlotsForDate(slotDuration, startDatesForEachDay?.[i], senderPreferences, receiverTimezone, senderTimezone, filteredNotAvailableSlotsInEventTimezone);
            availableSlots.push(...generatedSlots);
        }
    }
    return { availableSlots };
};
export const generateAvailability = async (userId, windowStartDateInSenderTimezone, windowEndDateInSenderTimezone, senderTimezone, receiverTimezone, slotDuration) => {
    try {
        const oldEventsInEventTimezone = await listEventsForUserGivenDates(userId, windowStartDateInSenderTimezone, windowEndDateInSenderTimezone);
        console.log(oldEventsInEventTimezone, ' oldEventsInEventTimezone');
        if (!oldEventsInEventTimezone || !(oldEventsInEventTimezone?.length > 0)) {
            console.log('no old events in generateAvailability');
        }
        const oldEventsInEventTimezoneFormatted = oldEventsInEventTimezone?.map((e) => ({
            ...e,
            startDate: dayjs(e?.startDate.slice(0, 19))
                .tz(e?.timezone, true)
                .format(),
            endDate: dayjs(e?.endDate.slice(0, 19)).tz(e?.timezone, true).format(),
            timezone: e?.timezone,
        }));
        const notAvailableFromEvents = oldEventsInEventTimezoneFormatted?.map((e) => ({
            startDate: e?.startDate,
            endDate: e?.endDate,
        }));
        const userPreferences = await getUserPreferences(userId);
        const { availableSlots: availableSlotsInReceiverTimezone } = await generateAvailableSlotsforTimeWindow(windowStartDateInSenderTimezone, windowEndDateInSenderTimezone, slotDuration, userPreferences, receiverTimezone, senderTimezone, notAvailableFromEvents?.length > 0 ? notAvailableFromEvents : undefined);
        return availableSlotsInReceiverTimezone;
    }
    catch (e) {
        console.log(e, ' unable to generate availability');
    }
};
export const process_summarize_availability = async (body) => {
    try {
        const userId = body?.userId;
        const dayAvailabilityList = body?.dayAvailabilityList;
        const openai = new OpenAI({
            apiKey: defaultOpenAIAPIKey,
        });
        const summarizedRes = await callOpenAI(summarizeAvailabilityResponsesPrompt, openAIChatGPTModel, dayAvailabilityList, openai, summarizeAvailabilityResponsesPromptExampleInput, summarizeAvailabilityResponsesPromptExampleOutput);
        return summarizedRes;
    }
    catch (e) {
        console.log(e, ' unable to process summarize availability');
    }
};
export const process_day_availibility = async (body) => {
    try {
        const userId = body?.userId;
        const windowStartDate = body?.windowStartDate;
        const windowEndDate = body?.windowEndDate;
        const senderTimezone = body?.senderTimezone;
        const receiverTimezone = body?.receiverTimezone;
        const slotDuration = body?.slotDuration;
        const openai = new OpenAI({
            apiKey: defaultOpenAIAPIKey,
        });
        // get availability
        const availability = await generateAvailability(userId, windowStartDate, windowEndDate, senderTimezone, receiverTimezone, parseInt(slotDuration, 10));
        if (!(availability?.length > 0)) {
            throw new Error('no availability present');
        }
        const uniqDates = _.uniqBy(availability, (curr) => dayjs(curr?.startDate).tz(receiverTimezone).format('YYYY-MM-DD'));
        let availabilityText = '';
        const prompt1 = summarizeAvailabilityPrompt;
        const exampleInput1 = summarizeAvailabilityExampleInput;
        const exampleOutput1 = summarizeAvailabilityExampleOutput;
        let openAIAvailabilityRes = '';
        for (const uniqDate of uniqDates) {
            const filteredAvailability = availability?.filter((a) => dayjs(a?.startDate).tz(receiverTimezone).format('YYYY-MM-DD') ===
                dayjs(uniqDate?.startDate).tz(receiverTimezone).format('YYYY-MM-DD'));
            if (filteredAvailability?.length > 0) {
                availabilityText +=
                    `${dayjs(uniqDate?.startDate).tz(receiverTimezone).format('L')} - ${filteredAvailability?.map((curr) => `${dayjs(curr?.startDate).tz(receiverTimezone).format('LT')} - ${dayjs(curr?.endDate).tz(receiverTimezone).format('LT')},`)?.reduce((prev, curr) => `${prev} ${curr}`, '')}` +
                        '\n\n';
                const miniAvailabilityText = `${dayjs(uniqDate?.startDate).tz(receiverTimezone).format('L')} - ${filteredAvailability?.map((curr) => `${dayjs(curr?.startDate).tz(receiverTimezone).format('LT')} - ${dayjs(curr?.endDate).tz(receiverTimezone).format('LT')},`)?.reduce((prev, curr) => `${prev} ${curr}`, '')}` +
                    '\n\n';
                const miniUserData = `My availability: ` + miniAvailabilityText;
                console.log(miniUserData, ' newAvailabilityPrompt');
                const miniOpenAIAvailabilityRes = await callOpenAI(prompt1, openAIChatGPTModel, miniUserData, openai, exampleInput1, exampleOutput1);
                // validate openai res
                if (!miniOpenAIAvailabilityRes) {
                    throw new Error('no openAIAvailabilityRes present inside appointmentRequest');
                }
                openAIAvailabilityRes += '\n' + miniOpenAIAvailabilityRes;
            }
        }
        console.log(openAIAvailabilityRes, ' openAIAvailabilityRes');
        return openAIAvailabilityRes;
    }
    catch (e) {
        console.log(e, ' unable to process day availability');
    }
};
export const insertAttendeesforEvent = async (attendees) => {
    try {
        // validate
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
        console.log(response?.data?.insert_Attendee?.returning, ' this is response in insertAttendees');
        response?.data?.insert_Attendee?.returning.forEach((r) => console.log(r, ' response in insertAttendees'));
    }
    catch (e) {
        console.log(e, ' unable to insert Attendees for new event');
    }
};
export const deleteAttendeesWithIds = async (eventIds, userId) => {
    try {
        // validate
        if (!(eventIds?.filter((e) => !!e)?.length > 0)) {
            return;
        }
        eventIds.forEach((e) => console.log(e, ' eventIds inside deleteRemindersWithIds'));
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
    }
    catch (e) {
        console.log(e, ' deleteAttendeesWithIds');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUNMLHdCQUF3QixFQUN4QixtQkFBbUIsRUFDbkIsb0NBQW9DLEVBQ3BDLG1CQUFtQixFQUNuQixzQkFBc0IsRUFDdEIscUJBQXFCLEVBQ3JCLHVCQUF1QixFQUN2QixpQkFBaUIsRUFDakIsaUJBQWlCLEVBQ2pCLDJCQUEyQixFQUMzQixxQkFBcUIsRUFDckIsY0FBYyxFQUNkLGlCQUFpQixFQUNqQixjQUFjLEVBQ2Qsa0JBQWtCLEVBQ2xCLGdCQUFnQixFQUNoQixXQUFXLEVBQ1gsWUFBWSxFQUNaLGdCQUFnQixFQUNoQixhQUFhLEVBQ2IsV0FBVyxFQUNYLGdCQUFnQixFQUNoQixlQUFlLEdBQ2hCLE1BQU0sYUFBYSxDQUFDO0FBQ3JCLE9BQU8sRUFBRSxNQUFNLElBQUksQ0FBQztBQTRCcEIsT0FBTyxNQUFNLE1BQU0sUUFBUSxDQUFDO0FBQzVCLE9BQU8sR0FBRyxNQUFNLEtBQUssQ0FBQztBQUN0QixPQUFPLEVBQUUsRUFBRSxJQUFJLElBQUksRUFBRSxNQUFNLE1BQU0sQ0FBQztBQUNsQyxPQUFPLE1BQU0sTUFBTSxRQUFRLENBQUM7QUFDNUIsT0FBTyxFQUNMLDJCQUEyQixFQUMzQiw0QkFBNEIsRUFDNUIscUJBQXFCLEVBQ3JCLDJCQUEyQixFQUMzQiw0QkFBNEIsRUFDNUIsNEJBQTRCLEVBQzVCLGtDQUFrQyxFQUNsQyxtQ0FBbUMsRUFDbkMsNEJBQTRCLEVBQzVCLGlDQUFpQyxFQUNqQyxrQ0FBa0MsRUFDbEMsMkJBQTJCLEVBQzNCLG9DQUFvQyxFQUNwQyxnREFBZ0QsRUFDaEQsaURBQWlELEdBQ2xELE1BQU0sV0FBVyxDQUFDO0FBQ25CLE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxZQUFZLENBQUM7QUFDcEMsT0FBTyxLQUFLLE1BQU0sT0FBTyxDQUFDO0FBQzFCLE9BQU8sUUFB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Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0tBeUJiLENBQUM7UUFFRixNQUFNLFNBQVMsR0FBRztZQUNoQixNQUFNO1lBQ04sUUFBUTtTQUNULENBQUM7UUFFRixNQUFNLFFBQVEsR0FBRyxNQUFNLEdBQUc7YUFDdkIsSUFBSSxDQUFDLGNBQWMsRUFBRTtZQUNwQixPQUFPLEVBQUU7Z0JBQ1AsdUJBQXVCLEVBQUUsaUJBQWlCO2dCQUMxQyxlQUFlLEVBQUUsT0FBTzthQUN6QjtZQUNELElBQUksRUFBRTtnQkFDSixhQUFhO2dCQUNiLEtBQUs7Z0JBQ0wsU0FBUzthQUNWO1NBQ0YsQ0FBQzthQUNELElBQUksRUFBRSxDQUFDO1FBQ1YsT0FBTyxDQUFDLEdBQUcsQ0FBQyxRQUFRLEVBQUUsNkNBQTZDLENBQUMsQ0FBQztJQUN2RSxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLHlCQUF5QixDQUFDLENBQUM7SUFDNUMsQ0FBQztBQUNILENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIEFUT01JQ19TVUJET01BSU5fUEFUVEVSTixcbiAgTUFYX0NIQVJBQ1RFUl9MSU1JVCxcbiAgTlVNQkVSX1RPX1JFTU9WRV9GT1JfU1VCRE9NQUlOX1NMSUNFLFxuICBkZWZhdWx0T3BlbkFJQVBJS2V5LFxuICBnb29nbGVDYWxlbmRhclJlc291cmNlLFxuICBnb29nbGVDbGllbnRJZEFuZHJvaWQsXG4gIGdvb2dsZUNsaWVudElkQXRvbWljV2ViLFxuICBnb29nbGVDbGllbnRJZElvcyxcbiAgZ29vZ2xlQ2xpZW50SWRXZWIsXG4gIGdvb2dsZUNsaWVudFNlY3JldEF0b21pY1dlYixcbiAgZ29vZ2xlQ2xpZW50U2VjcmV0V2ViLFxuICBnb29nbGVUb2tlblVybCxcbiAgaGFzdXJhQWRtaW5TZWNyZXQsXG4gIGhhc3VyYUdyYXBoVXJsLFxuICBvcGVuQUlDaGF0R1BUTW9kZWwsXG4gIHpvb21CYXNlVG9rZW5VcmwsXG4gIHpvb21CYXNlVXJsLFxuICB6b29tQ2xpZW50SWQsXG4gIHpvb21DbGllbnRTZWNyZXQsXG4gIHpvb21JVkZvclBhc3MsXG4gIHpvb21QYXNzS2V5LFxuICB6b29tUmVzb3VyY2VOYW1lLFxuICB6b29tU2FsdEZvclBhc3MsXG59IGZyb20gJy4vY29uc3RhbnRzJztcbmltcG9ydCBxcyBmcm9tICdxcyc7XG5pbXBvcnQge1xuICBBdHRlbmRlZVR5cGUsXG4gIENhbGVuZGFySW50ZWdyYXRpb25UeXBlLFxuICBDYWxlbmRhclR5cGUsXG4gIENvbmZlcmVuY2VUeXBlLFxuICBDcmVhdGVab29tTWVldGluZ1JlcXVlc3RCb2R5VHlwZSxcbiAgRXZlbnRUeXBlLFxuICBFeHRyYWN0RGF0ZVRpbWVPYmplY3RUeXBlLFxuICBHb29nbGVBdHRhY2htZW50VHlwZSxcbiAgR29vZ2xlQXR0ZW5kZWVUeXBlLFxuICBHb29nbGVDb25mZXJlbmNlRGF0YVR5cGUsXG4gIEdvb2dsZUV2ZW50VHlwZTEsXG4gIEdvb2dsZUV4dGVuZGVkUHJvcGVydGllc1R5cGUsXG4gIEdvb2dsZVJlbWluZGVyVHlwZSxcbiAgR29vZ2xlUmVzVHlwZSxcbiAgR29vZ2xlU2VuZFVwZGF0ZXNUeXBlLFxuICBHb29nbGVTb3VyY2VUeXBlLFxuICBHb29nbGVUcmFuc3BhcmVuY3lUeXBlLFxuICBHb29nbGVWaXNpYmlsaXR5VHlwZSxcbiAgTWVldGluZ1VybFF1ZXJ5UGFyYW1zVHlwZSxcbiAgUmVtaW5kZXJUeXBlLFxuICBTdW1tYXJ5QW5kTm90ZXNPYmplY3RUeXBlLFxuICBVc2VyT3BlbkFJVHlwZSxcbiAgVXNlclByZWZlcmVuY2VUeXBlLFxuICBab29tTWVldGluZ09iamVjdFR5cGUsXG4gIGlzTWVldGluZ1NjaGVkdWxlZE9iamVjdFR5cGUsXG59IGZyb20gJy4vdHlwZXMvZ2VuZXJpY1R5cGVzJztcbmltcG9ydCBjcnlwdG8gZnJvbSAnY3J5cHRvJztcbmltcG9ydCBnb3QgZnJvbSAnZ290JztcbmltcG9ydCB7IHY0IGFzIHV1aWQgfSBmcm9tICd1dWlkJztcbmltcG9ydCBPcGVuQUkgZnJvbSAnb3BlbmFpJztcbmltcG9ydCB7XG4gIGV4dHJhY3REYXRlVGltZUV4YW1wbGVJbnB1dCxcbiAgZXh0cmFjdERhdGVUaW1lRXhhbXBsZU91dHB1dCxcbiAgZXh0cmFjdERhdGVUaW1lUHJvbXB0LFxuICBnZW5lcmF0ZU1lZXRpbmdTdW1tYXJ5SW5wdXQsXG4gIGdlbmVyYXRlTWVldGluZ1N1bW1hcnlPdXRwdXQsXG4gIGdlbmVyYXRlTWVldGluZ1N1bW1hcnlQcm9tcHQsXG4gIGlzTWVldGluZ1RpbWVTY2hlZHVsZWRFeGFtcGxlSW5wdXQsXG4gIGlzTWVldGluZ1RpbWVTY2hlZHVsZWRFeGFtcGxlT3V0cHV0LFxuICBpc01lZXRpbmdUaW1lU2NoZWR1bGVkUHJvbXB0LFxuICBzdW1tYXJpemVBdmFpbGFiaWxpdHlFeGFtcGxlSW5wdXQsXG4gIHN1bW1hcml6ZUF2YWlsYWJpbGl0eUV4YW1wbGVPdXRwdXQsXG4gIHN1bW1hcml6ZUF2YWlsYWJpbGl0eVByb21wdCxcbiAgc3VtbWFyaXplQXZhaWxhYmlsaXR5UmVzcG9uc2VzUHJvbXB0LFxuICBzdW1tYXJpemVBdmFpbGFiaWxpdHlSZXNwb25zZXNQcm9tcHRFeGFtcGxlSW5wdXQsXG4gIHN1bW1hcml6ZUF2YWlsYWJpbGl0eVJlc3BvbnNlc1Byb21wdEV4YW1wbGVPdXRwdXQsXG59IGZyb20gJy4vcHJvbXB0cyc7XG5pbXBvcnQgeyBnb29nbGUgfSBmcm9tICdnb29nbGVhcGlzJztcbmltcG9ydCBkYXlqcyBmcm9tICdkYXlqcyc7XG5pbXBvcnQgZHVyYXRpb24gZnJvbSAnZGF5anMvcGx1Z2luL2R1cmF0aW9uJztcbmltcG9ydCBpc0JldHdlZW4gZnJvbSAnZGF5anMvcGx1Z2luL2lzQmV0d2Vlbic7XG5pbXBvcnQgdGltZXpvbmUgZnJvbSAnZGF5anMvcGx1Z2luL3RpbWV6b25lJztcbmltcG9ydCB1dGMgZnJvbSAnZGF5anMvcGx1Z2luL3V0Yyc7XG5pbXBvcnQgYXhpb3MgZnJvbSAnYXhpb3MnO1xuaW1wb3J0IF8gZnJvbSAnbG9kYXNoJztcbmltcG9ydCAqIGFzIGNoZWVyaW8gZnJvbSAnY2hlZXJpbyc7XG5pbXBvcnQgcXVvdGVkUHJpbnRhYmxlIGZyb20gJ3F1b3RlZC1wcmludGFibGUnO1xuaW1wb3J0IHtcbiAgQXZhaWxhYmxlU2xvdFR5cGUsXG4gIERheUF2YWlsYWJpbGl0eVR5cGUsXG4gIE5vdEF2YWlsYWJsZVNsb3RUeXBlLFxuICBTdW1tYXJpemVEYXlBdmFpbGFiaWxpdHlUeXBlLFxufSBmcm9tICcuL3R5cGVzL2F2YWlsYWJpbGl0eVR5cGVzJztcbmltcG9ydCB7IGdldElTT0RheSB9IGZyb20gJ2RhdGUtZm5zJztcbmltcG9ydCB7IENoYXRHUFRSb2xlVHlwZSB9IGZyb20gJy4vdHlwZXMvQ2hhdEdQVFR5cGVzJztcblxuZGF5anMuZXh0ZW5kKGR1cmF0aW9uKTtcbmRheWpzLmV4dGVuZChpc0JldHdlZW4pO1xuZGF5anMuZXh0ZW5kKHRpbWV6b25lKTtcbmRheWpzLmV4dGVuZCh1dGMpO1xuXG5leHBvcnQgY29uc3QgY2FsbE9wZW5BSSA9IGFzeW5jIChcbiAgcHJvbXB0OiBzdHJpbmcsXG4gIG1vZGVsOiAnZ3B0LTMuNS10dXJibycgPSAnZ3B0LTMuNS10dXJibycsXG4gIHVzZXJEYXRhOiBzdHJpbmcsXG4gIG9wZW5haTogT3BlbkFJLFxuICBleGFtcGxlSW5wdXQ/OiBzdHJpbmcsXG4gIGV4YW1wbGVPdXRwdXQ/OiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIC8vIGFzc2lzdGFudFxuICAgIGNvbnN0IGNvbXBsZXRpb24gPSBhd2FpdCBvcGVuYWkuY2hhdC5jb21wbGV0aW9ucy5jcmVhdGUoe1xuICAgICAgbW9kZWwsXG4gICAgICBtZXNzYWdlczogW1xuICAgICAgICB7IHJvbGU6ICdzeXN0ZW0nIGFzIENoYXRHUFRSb2xlVHlwZSwgY29udGVudDogcHJvbXB0IH0sXG4gICAgICAgIGV4YW1wbGVJbnB1dCAmJiB7XG4gICAgICAgICAgcm9sZTogJ3VzZXInIGFzIENoYXRHUFRSb2xlVHlwZSxcbiAgICAgICAgICBjb250ZW50OiBleGFtcGxlSW5wdXQsXG4gICAgICAgIH0sXG4gICAgICAgIGV4YW1wbGVPdXRwdXQgJiYge1xuICAgICAgICAgIHJvbGU6ICdhc3Npc3RhbnQnIGFzIENoYXRHUFRSb2xlVHlwZSxcbiAgICAgICAgICBjb250ZW50OiBleGFtcGxlT3V0cHV0LFxuICAgICAgICB9LFxuICAgICAgICB7IHJvbGU6ICd1c2VyJyBhcyBDaGF0R1BUUm9sZVR5cGUsIGNvbnRlbnQ6IHVzZXJEYXRhIH0sXG4gICAgICBdPy5maWx0ZXIoKG0pID0+ICEhbSksXG4gICAgfSk7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBjb21wbGV0aW9uLmNob2ljZXNbMF0/Lm1lc3NhZ2U/LmNvbnRlbnQsXG4gICAgICAnIHJlc3BvbnNlIGZyb20gb3BlbmFpYXBpJ1xuICAgICk7XG5cbiAgICByZXR1cm4gY29tcGxldGlvbj8uY2hvaWNlcz8uWzBdPy5tZXNzYWdlPy5jb250ZW50O1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGlmIChlcnJvci5yZXNwb25zZSkge1xuICAgICAgY29uc29sZS5sb2coZXJyb3IucmVzcG9uc2Uuc3RhdHVzLCAnIG9wZW5haSBlcnJvciBzdGF0dXMnKTtcbiAgICAgIGNvbnNvbGUubG9nKGVycm9yLnJlc3BvbnNlLmRhdGEsICcgb3BlbmFpIGVycm9yIGRhdGEnKTtcbiAgICB9IGVsc2Uge1xuICAgICAgY29uc29sZS5sb2coZXJyb3IubWVzc2FnZSwgJyBvcGVuYWkgZXJyb3IgbWVzc2FnZScpO1xuICAgIH1cbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldENhbGVuZGFySW50ZWdyYXRpb24gPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICByZXNvdXJjZTogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2dldENhbGVuZGFySW50ZWdyYXRpb24nO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgcXVlcnkgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbigkdXNlcklkOiB1dWlkISwgJHJlc291cmNlOiBTdHJpbmchKSB7XG4gICAgICAgIENhbGVuZGFyX0ludGVncmF0aW9uKHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgcmVzb3VyY2U6IHtfZXE6ICRyZXNvdXJjZX19KSB7XG4gICAgICAgICAgdG9rZW5cbiAgICAgICAgICBleHBpcmVzQXRcbiAgICAgICAgICBpZFxuICAgICAgICAgIHJlZnJlc2hUb2tlblxuICAgICAgICAgIHJlc291cmNlXG4gICAgICAgICAgbmFtZVxuICAgICAgICAgIGNsaWVudFR5cGVcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgcmVzb3VyY2UsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IENhbGVuZGFyX0ludGVncmF0aW9uOiBDYWxlbmRhckludGVncmF0aW9uVHlwZVtdIH0gfSA9XG4gICAgICBhd2FpdCBnb3RcbiAgICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgICBqc29uOiB7XG4gICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgcXVlcnksXG4gICAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGluc2lkZSBnZXRDYWxlbmRhckludGVncmF0aW9uJyk7XG4gICAgaWYgKHJlcz8uZGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb24/Lmxlbmd0aCA+IDApIHtcbiAgICAgIHJldHVybiByZXM/LmRhdGE/LkNhbGVuZGFyX0ludGVncmF0aW9uPy5bMF07XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGNhbGVuZGFyIGludGVncmF0aW9uJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRHbG9iYWxDYWxlbmRhciA9IGFzeW5jICh1c2VySWQ6IHN0cmluZykgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZ2V0R2xvYmFsQ2FsZW5kYXInO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICBxdWVyeSBnZXRHbG9iYWxDYWxlbmRhcigkdXNlcklkOiB1dWlkISkge1xuICAgICAgICAgIENhbGVuZGFyKHdoZXJlOiB7Z2xvYmFsUHJpbWFyeToge19lcTogdHJ1ZX0sIHVzZXJJZDoge19lcTogJHVzZXJJZH19KSB7XG4gICAgICAgICAgICBjb2xvcklkXG4gICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgIGFjY2Vzc0xldmVsXG4gICAgICAgICAgICBhY2NvdW50XG4gICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgZGVmYXVsdFJlbWluZGVyc1xuICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICBnbG9iYWxQcmltYXJ5XG4gICAgICAgICAgICBpZFxuICAgICAgICAgICAgbW9kaWZpYWJsZVxuICAgICAgICAgICAgcHJpbWFyeVxuICAgICAgICAgICAgcmVzb3VyY2VcbiAgICAgICAgICAgIHRpdGxlXG4gICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgIGA7XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBDYWxlbmRhcjogQ2FsZW5kYXJUeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICByZXR1cm4gcmVzLmRhdGEuQ2FsZW5kYXI/LlswXTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBnbG9iYWwgY2FsZW5kYXInKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24gPSBhc3luYyAoXG4gIGlkOiBzdHJpbmcsXG4gIHRva2VuPzogc3RyaW5nLFxuICBleHBpcmVzSW4/OiBudW1iZXIsXG4gIGVuYWJsZWQ/OiBib29sZWFuXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ3VwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24nO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICBtdXRhdGlvbiB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uKCRpZDogdXVpZCEsJHt0b2tlbiAhPT0gdW5kZWZpbmVkID8gJyAkdG9rZW46IFN0cmluZywnIDogJyd9JHtleHBpcmVzSW4gIT09IHVuZGVmaW5lZCA/ICcgJGV4cGlyZXNBdDogdGltZXN0YW1wdHosJyA6ICcnfSR7ZW5hYmxlZCAhPT0gdW5kZWZpbmVkID8gJyAkZW5hYmxlZDogQm9vbGVhbiwnIDogJyd9KSB7XG4gICAgICAgICAgdXBkYXRlX0NhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrKHBrX2NvbHVtbnM6IHtpZDogJGlkfSwgX3NldDogeyR7dG9rZW4gIT09IHVuZGVmaW5lZCA/ICd0b2tlbjogJHRva2VuLCcgOiAnJ30ke2V4cGlyZXNJbiAhPT0gdW5kZWZpbmVkID8gJyBleHBpcmVzQXQ6ICRleHBpcmVzQXQsJyA6ICcnfSR7ZW5hYmxlZCAhPT0gdW5kZWZpbmVkID8gJyBlbmFibGVkOiAkZW5hYmxlZCwnIDogJyd9fSkge1xuICAgICAgICAgICAgaWRcbiAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgIHJlZnJlc2hUb2tlblxuICAgICAgICAgICAgdG9rZW5cbiAgICAgICAgICAgIGNsaWVudFR5cGVcbiAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkLFxuICAgICAgdG9rZW4sXG4gICAgICBleHBpcmVzQXQ6IGRheWpzKCkuYWRkKGV4cGlyZXNJbiwgJ3NlY29uZHMnKS50b0lTT1N0cmluZygpLFxuICAgICAgZW5hYmxlZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgaW5zaWRlIHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24nKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwZGF0ZSBjYWxlbmRhciBpbnRlZ3JhdGlvbicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZGVjcnlwdFpvb21Ub2tlbnMgPSAoXG4gIGVuY3J5cHRlZFRva2VuOiBzdHJpbmcsXG4gIGVuY3J5cHRlZFJlZnJlc2hUb2tlbj86IHN0cmluZ1xuKSA9PiB7XG4gIGNvbnN0IGl2QnVmZmVyID0gQnVmZmVyLmZyb20oem9vbUlWRm9yUGFzcywgJ2Jhc2U2NCcpO1xuICBjb25zdCBzYWx0QnVmZmVyID0gQnVmZmVyLmZyb20oem9vbVNhbHRGb3JQYXNzLCAnYmFzZTY0Jyk7XG5cbiAgY29uc3Qga2V5ID0gY3J5cHRvLnBia2RmMlN5bmMoXG4gICAgem9vbVBhc3NLZXkgYXMgc3RyaW5nLFxuICAgIHNhbHRCdWZmZXIsXG4gICAgMTAwMDAsXG4gICAgMzIsXG4gICAgJ3NoYTI1NidcbiAgKTtcblxuICBjb25zdCBkZWNpcGhlclRva2VuID0gY3J5cHRvLmNyZWF0ZURlY2lwaGVyaXYoJ2Flcy0yNTYtY2JjJywga2V5LCBpdkJ1ZmZlcik7XG4gIGxldCBkZWNyeXB0ZWRUb2tlbiA9IGRlY2lwaGVyVG9rZW4udXBkYXRlKGVuY3J5cHRlZFRva2VuLCAnYmFzZTY0JywgJ3V0ZjgnKTtcbiAgZGVjcnlwdGVkVG9rZW4gKz0gZGVjaXBoZXJUb2tlbi5maW5hbCgndXRmOCcpO1xuXG4gIGlmIChlbmNyeXB0ZWRSZWZyZXNoVG9rZW4pIHtcbiAgICBjb25zdCBkZWNpcGhlclJlZnJlc2hUb2tlbiA9IGNyeXB0by5jcmVhdGVEZWNpcGhlcml2KFxuICAgICAgJ2Flcy0yNTYtY2JjJyxcbiAgICAgIGtleSxcbiAgICAgIGl2QnVmZmVyXG4gICAgKTtcbiAgICBsZXQgZGVjcnlwdGVkUmVmcmVzaFRva2VuID0gZGVjaXBoZXJSZWZyZXNoVG9rZW4udXBkYXRlKFxuICAgICAgZW5jcnlwdGVkUmVmcmVzaFRva2VuLFxuICAgICAgJ2Jhc2U2NCcsXG4gICAgICAndXRmOCdcbiAgICApO1xuICAgIGRlY3J5cHRlZFJlZnJlc2hUb2tlbiArPSBkZWNpcGhlclJlZnJlc2hUb2tlbi5maW5hbCgndXRmOCcpO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIHRva2VuOiBkZWNyeXB0ZWRUb2tlbixcbiAgICAgIHJlZnJlc2hUb2tlbjogZGVjcnlwdGVkUmVmcmVzaFRva2VuLFxuICAgIH07XG4gIH1cblxuICByZXR1cm4ge1xuICAgIHRva2VuOiBkZWNyeXB0ZWRUb2tlbixcbiAgfTtcbn07XG5cbmV4cG9ydCBjb25zdCBlbmNyeXB0Wm9vbVRva2VucyA9ICh0b2tlbjogc3RyaW5nLCByZWZyZXNoVG9rZW4/OiBzdHJpbmcpID0+IHtcbiAgY29uc3QgaXZCdWZmZXIgPSBCdWZmZXIuZnJvbSh6b29tSVZGb3JQYXNzLCAnYmFzZTY0Jyk7XG4gIGNvbnN0IHNhbHRCdWZmZXIgPSBCdWZmZXIuZnJvbSh6b29tU2FsdEZvclBhc3MsICdiYXNlNjQnKTtcblxuICBjb25zdCBrZXkgPSBjcnlwdG8ucGJrZGYyU3luYyhcbiAgICB6b29tUGFzc0tleSBhcyBzdHJpbmcsXG4gICAgc2FsdEJ1ZmZlcixcbiAgICAxMDAwMCxcbiAgICAzMixcbiAgICAnc2hhMjU2J1xuICApO1xuICBjb25zdCBjaXBoZXJUb2tlbiA9IGNyeXB0by5jcmVhdGVDaXBoZXJpdignYWVzLTI1Ni1jYmMnLCBrZXksIGl2QnVmZmVyKTtcbiAgbGV0IGVuY3J5cHRlZFRva2VuID0gY2lwaGVyVG9rZW4udXBkYXRlKHRva2VuLCAndXRmOCcsICdiYXNlNjQnKTtcbiAgZW5jcnlwdGVkVG9rZW4gKz0gY2lwaGVyVG9rZW4uZmluYWwoJ2Jhc2U2NCcpO1xuXG4gIGxldCBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4gPSAnJztcblxuICBpZiAocmVmcmVzaFRva2VuKSB7XG4gICAgY29uc3QgY2lwaGVyUmVmcmVzaFRva2VuID0gY3J5cHRvLmNyZWF0ZUNpcGhlcml2KFxuICAgICAgJ2Flcy0yNTYtY2JjJyxcbiAgICAgIGtleSxcbiAgICAgIGl2QnVmZmVyXG4gICAgKTtcbiAgICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4gPSBjaXBoZXJSZWZyZXNoVG9rZW4udXBkYXRlKFxuICAgICAgcmVmcmVzaFRva2VuLFxuICAgICAgJ3V0ZjgnLFxuICAgICAgJ2Jhc2U2NCdcbiAgICApO1xuICAgIGVuY3J5cHRlZFJlZnJlc2hUb2tlbiArPSBjaXBoZXJSZWZyZXNoVG9rZW4uZmluYWwoJ2Jhc2U2NCcpO1xuICB9XG5cbiAgaWYgKGVuY3J5cHRlZFJlZnJlc2hUb2tlbikge1xuICAgIHJldHVybiB7XG4gICAgICBlbmNyeXB0ZWRUb2tlbixcbiAgICAgIGVuY3J5cHRlZFJlZnJlc2hUb2tlbixcbiAgICB9O1xuICB9IGVsc2Uge1xuICAgIHJldHVybiB7IGVuY3J5cHRlZFRva2VuIH07XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRab29tSW50ZWdyYXRpb24gPSBhc3luYyAodXNlcklkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGlkLCB0b2tlbiwgZXhwaXJlc0F0LCByZWZyZXNoVG9rZW4gfSA9IGF3YWl0IGdldENhbGVuZGFySW50ZWdyYXRpb24oXG4gICAgICB1c2VySWQsXG4gICAgICB6b29tUmVzb3VyY2VOYW1lXG4gICAgKTtcblxuICAgIGNvbnN0IGRlY3J5cHRlZFRva2VucyA9IGRlY3J5cHRab29tVG9rZW5zKHRva2VuLCByZWZyZXNoVG9rZW4pO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIGlkLFxuICAgICAgZXhwaXJlc0F0LFxuICAgICAgLi4uZGVjcnlwdGVkVG9rZW5zLFxuICAgIH07XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgem9vbSBpbnRlZ3JhdGlvbicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBkYXRlWm9vbUludGVncmF0aW9uID0gYXN5bmMgKFxuICBpZDogc3RyaW5nLFxuICBhY2Nlc3NUb2tlbjogc3RyaW5nLFxuICBleHBpcmVzSW46IG51bWJlclxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgeyBlbmNyeXB0ZWRUb2tlbiB9ID0gZW5jcnlwdFpvb21Ub2tlbnMoYWNjZXNzVG9rZW4pO1xuICAgIGF3YWl0IHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24oaWQsIGVuY3J5cHRlZFRva2VuLCBleHBpcmVzSW4pO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdXBkYXRlIHpvb20gaW50ZWdyYXRpb24nKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHJlZnJlc2hab29tVG9rZW4gPSBhc3luYyAoXG4gIHJlZnJlc2hUb2tlbjogc3RyaW5nXG4pOiBQcm9taXNlPHtcbiAgYWNjZXNzX3Rva2VuOiBzdHJpbmc7XG4gIHRva2VuX3R5cGU6ICdiZWFyZXInO1xuICByZWZyZXNoX3Rva2VuOiBzdHJpbmc7XG4gIGV4cGlyZXNfaW46IG51bWJlcjtcbiAgc2NvcGU6IHN0cmluZztcbn0+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB1c2VybmFtZSA9IHpvb21DbGllbnRJZDtcbiAgICBjb25zdCBwYXNzd29yZCA9IHpvb21DbGllbnRTZWNyZXQ7XG5cbiAgICByZXR1cm4gYXhpb3Moe1xuICAgICAgZGF0YTogbmV3IFVSTFNlYXJjaFBhcmFtcyh7XG4gICAgICAgIHJlZnJlc2hfdG9rZW46IHJlZnJlc2hUb2tlbixcbiAgICAgICAgZ3JhbnRfdHlwZTogJ3JlZnJlc2hfdG9rZW4nLFxuICAgICAgfSkudG9TdHJpbmcoKSxcbiAgICAgIGJhc2VVUkw6IHpvb21CYXNlVG9rZW5VcmwsXG4gICAgICB1cmw6ICcvb2F1dGgvdG9rZW4nLFxuICAgICAgbWV0aG9kOiAnUE9TVCcsXG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24veC13d3ctZm9ybS11cmxlbmNvZGVkJyxcbiAgICAgIH0sXG4gICAgICBhdXRoOiB7XG4gICAgICAgIHVzZXJuYW1lLFxuICAgICAgICBwYXNzd29yZCxcbiAgICAgIH0sXG4gICAgfSkudGhlbigoeyBkYXRhIH0pID0+IFByb21pc2UucmVzb2x2ZShkYXRhKSk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byByZWZyZXNoIHpvb20gdG9rZW4nKTtcbiAgfVxufTtcbmV4cG9ydCBjb25zdCBnZXRab29tQVBJVG9rZW4gPSBhc3luYyAodXNlcklkOiBzdHJpbmcpID0+IHtcbiAgbGV0IGludGVncmF0aW9uSWQgPSAnJztcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZygnZ2V0Wm9vbUFQSVRva2VuIGNhbGxlZCcpO1xuICAgIGNvbnN0IHsgaWQsIHRva2VuLCBleHBpcmVzQXQsIHJlZnJlc2hUb2tlbiB9ID1cbiAgICAgIGF3YWl0IGdldFpvb21JbnRlZ3JhdGlvbih1c2VySWQpO1xuICAgIGlmICghcmVmcmVzaFRva2VuKSB7XG4gICAgICBjb25zb2xlLmxvZygnem9vbSBub3QgYWN0aXZlLCBubyByZWZyZXNoIHRva2VuJyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgaW50ZWdyYXRpb25JZCA9IGlkO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgaWQsXG4gICAgICB0b2tlbixcbiAgICAgIGV4cGlyZXNBdCxcbiAgICAgIHJlZnJlc2hUb2tlbixcbiAgICAgICcgaWQsIHRva2VuLCBleHBpcmVzQXQsIHJlZnJlc2hUb2tlbidcbiAgICApO1xuICAgIGlmIChkYXlqcygpLmlzQWZ0ZXIoZGF5anMoZXhwaXJlc0F0KSkgfHwgIXRva2VuKSB7XG4gICAgICBjb25zdCByZXMgPSBhd2FpdCByZWZyZXNoWm9vbVRva2VuKHJlZnJlc2hUb2tlbik7XG4gICAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gcmVmcmVzaFpvb21Ub2tlbicpO1xuICAgICAgYXdhaXQgdXBkYXRlWm9vbUludGVncmF0aW9uKGlkLCByZXMuYWNjZXNzX3Rva2VuLCByZXMuZXhwaXJlc19pbik7XG4gICAgICByZXR1cm4gcmVzLmFjY2Vzc190b2tlbjtcbiAgICB9XG5cbiAgICByZXR1cm4gdG9rZW47XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgem9vbSBhcGkgdG9rZW4nKTtcbiAgICBhd2FpdCB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uKGludGVncmF0aW9uSWQsIG51bGwsIG51bGwsIGZhbHNlKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGNyZWF0ZVpvb21NZWV0aW5nID0gYXN5bmMgKFxuICB6b29tVG9rZW46IHN0cmluZyxcbiAgc3RhcnREYXRlOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIGFnZW5kYTogc3RyaW5nLFxuICBkdXJhdGlvbjogbnVtYmVyLFxuICBjb250YWN0TmFtZT86IHN0cmluZyxcbiAgY29udGFjdEVtYWlsPzogc3RyaW5nLFxuICBtZWV0aW5nSW52aXRlZXM/OiBzdHJpbmdbXVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgLy92YWxkaWF0ZVxuICAgIGlmIChkYXlqcygpLmlzQWZ0ZXIoZGF5anMoc3RhcnREYXRlKSkpIHtcbiAgICAgIGNvbnNvbGUubG9nKCcgc3RhcnR0aW1lIGlzIGluIHRoZSBwYXN0Jyk7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ3N0YXJ0dGltZSBpcyBpbiB0aGUgcGFzdCcpO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZGF5anMoc3RhcnREYXRlPy5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpLFxuICAgICAgdGltZXpvbmUsXG4gICAgICBhZ2VuZGEsXG4gICAgICBkdXJhdGlvbixcbiAgICAgIGAgZGF5anMoc3RhcnREYXRlPy5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW06c3MnKSxcbiAgICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgICAgYWdlbmRhLFxuICAgICAgICAgICAgZHVyYXRpb24sIGNyZWF0ZVpvb21NZWV0aW5nIGNhbGxlZGBcbiAgICApO1xuXG4gICAgbGV0IHNldHRpbmdzOiBhbnkgPSB7fTtcblxuICAgIGlmIChjb250YWN0TmFtZT8ubGVuZ3RoID4gMCAmJiBjb250YWN0RW1haWw/Lmxlbmd0aCA+IDApIHtcbiAgICAgIHNldHRpbmdzID0ge1xuICAgICAgICBjb250YWN0X25hbWU6IGNvbnRhY3ROYW1lLFxuICAgICAgICBjb250YWN0X2VtYWlsOiBjb250YWN0RW1haWwsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChtZWV0aW5nSW52aXRlZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIHNldHRpbmdzID0ge1xuICAgICAgICAuLi5zZXR0aW5ncyxcbiAgICAgICAgbWVldGluZ19pbnZpdGVlczogbWVldGluZ0ludml0ZWVzPy5tYXAoKG0pID0+ICh7IGVtYWlsOiBtIH0pKSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgbGV0IHJlcUJvZHk6IENyZWF0ZVpvb21NZWV0aW5nUmVxdWVzdEJvZHlUeXBlID0ge307XG5cbiAgICBpZiAoT2JqZWN0LmtleXMoc2V0dGluZ3MpPy5sZW5ndGggPiAwKSB7XG4gICAgICByZXFCb2R5LnNldHRpbmdzID0gc2V0dGluZ3M7XG4gICAgfVxuXG4gICAgcmVxQm9keSA9IHtcbiAgICAgIC4uLnJlcUJvZHksXG4gICAgICBzdGFydF90aW1lOiBkYXlqcyhzdGFydERhdGU/LnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudXRjKClcbiAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgLy8gdGltZXpvbmUsXG4gICAgICBhZ2VuZGEsXG4gICAgICBkdXJhdGlvbixcbiAgICB9O1xuXG4gICAgY29uc29sZS5sb2cocmVxQm9keSwgJyByZXFCb2R5IGluc2lkZSBjcmVhdGVab29tTWVldGluZycpO1xuXG4gICAgY29uc3QgcmVzOiBab29tTWVldGluZ09iamVjdFR5cGUgPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGAke3pvb21CYXNlVXJsfS91c2Vycy9tZS9tZWV0aW5nc2AsIHtcbiAgICAgICAganNvbjogcmVxQm9keSxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt6b29tVG9rZW59YCxcbiAgICAgICAgICBDb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGluc2lkZSBjcmVhdGVab29tTWVldGluZycpO1xuXG4gICAgcmV0dXJuIHJlcztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGNyZWF0ZSB6b29tIG1lZXRpbmcnKTtcbiAgfVxufTtcbmV4cG9ydCBjb25zdCByZWZyZXNoR29vZ2xlVG9rZW4gPSBhc3luYyAoXG4gIHJlZnJlc2hUb2tlbjogc3RyaW5nLFxuICBjbGllbnRUeXBlOiAnaW9zJyB8ICdhbmRyb2lkJyB8ICd3ZWInIHwgJ2F0b21pYy13ZWInXG4pOiBQcm9taXNlPHtcbiAgYWNjZXNzX3Rva2VuOiBzdHJpbmc7XG4gIGV4cGlyZXNfaW46IG51bWJlcjsgLy8gYWRkIHNlY29uZHMgdG8gbm93XG4gIHNjb3BlOiBzdHJpbmc7XG4gIHRva2VuX3R5cGU6IHN0cmluZztcbn0+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZygncmVmcmVzaEdvb2dsZVRva2VuIGNhbGxlZCcsIHJlZnJlc2hUb2tlbik7XG4gICAgY29uc29sZS5sb2coJ2NsaWVudFR5cGUnLCBjbGllbnRUeXBlKTtcbiAgICBjb25zb2xlLmxvZygnZ29vZ2xlQ2xpZW50SWRJb3MnLCBnb29nbGVDbGllbnRJZElvcyk7XG4gICAgc3dpdGNoIChjbGllbnRUeXBlKSB7XG4gICAgICBjYXNlICdpb3MnOlxuICAgICAgICByZXR1cm4gZ290XG4gICAgICAgICAgLnBvc3QoZ29vZ2xlVG9rZW5VcmwsIHtcbiAgICAgICAgICAgIGZvcm06IHtcbiAgICAgICAgICAgICAgZ3JhbnRfdHlwZTogJ3JlZnJlc2hfdG9rZW4nLFxuICAgICAgICAgICAgICByZWZyZXNoX3Rva2VuOiByZWZyZXNoVG9rZW4sXG4gICAgICAgICAgICAgIGNsaWVudF9pZDogZ29vZ2xlQ2xpZW50SWRJb3MsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL3gtd3d3LWZvcm0tdXJsZW5jb2RlZCcsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0pXG4gICAgICAgICAgLmpzb24oKTtcbiAgICAgIGNhc2UgJ2FuZHJvaWQnOlxuICAgICAgICByZXR1cm4gZ290XG4gICAgICAgICAgLnBvc3QoZ29vZ2xlVG9rZW5VcmwsIHtcbiAgICAgICAgICAgIGZvcm06IHtcbiAgICAgICAgICAgICAgZ3JhbnRfdHlwZTogJ3JlZnJlc2hfdG9rZW4nLFxuICAgICAgICAgICAgICByZWZyZXNoX3Rva2VuOiByZWZyZXNoVG9rZW4sXG4gICAgICAgICAgICAgIGNsaWVudF9pZDogZ29vZ2xlQ2xpZW50SWRBbmRyb2lkLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi94LXd3dy1mb3JtLXVybGVuY29kZWQnLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9KVxuICAgICAgICAgIC5qc29uKCk7XG4gICAgICBjYXNlICd3ZWInOlxuICAgICAgICByZXR1cm4gZ290XG4gICAgICAgICAgLnBvc3QoZ29vZ2xlVG9rZW5VcmwsIHtcbiAgICAgICAgICAgIGZvcm06IHtcbiAgICAgICAgICAgICAgZ3JhbnRfdHlwZTogJ3JlZnJlc2hfdG9rZW4nLFxuICAgICAgICAgICAgICByZWZyZXNoX3Rva2VuOiByZWZyZXNoVG9rZW4sXG4gICAgICAgICAgICAgIGNsaWVudF9pZDogZ29vZ2xlQ2xpZW50SWRXZWIsXG4gICAgICAgICAgICAgIGNsaWVudF9zZWNyZXQ6IGdvb2dsZUNsaWVudFNlY3JldFdlYixcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24veC13d3ctZm9ybS11cmxlbmNvZGVkJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfSlcbiAgICAgICAgICAuanNvbigpO1xuICAgICAgY2FzZSAnYXRvbWljLXdlYic6XG4gICAgICAgIHJldHVybiBnb3RcbiAgICAgICAgICAucG9zdChnb29nbGVUb2tlblVybCwge1xuICAgICAgICAgICAgZm9ybToge1xuICAgICAgICAgICAgICBncmFudF90eXBlOiAncmVmcmVzaF90b2tlbicsXG4gICAgICAgICAgICAgIHJlZnJlc2hfdG9rZW46IHJlZnJlc2hUb2tlbixcbiAgICAgICAgICAgICAgY2xpZW50X2lkOiBnb29nbGVDbGllbnRJZEF0b21pY1dlYixcbiAgICAgICAgICAgICAgY2xpZW50X3NlY3JldDogZ29vZ2xlQ2xpZW50U2VjcmV0QXRvbWljV2ViLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi94LXd3dy1mb3JtLXVybGVuY29kZWQnLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9KVxuICAgICAgICAgIC5qc29uKCk7XG4gICAgfVxuXG4gICAgLyogIFxuICAgICAgICB7XG4gICAgICAgICAgXCJhY2Nlc3NfdG9rZW5cIjogXCIxL2ZGQUdSTkpydTFGVHo3MEJ6aFQzWmdcIixcbiAgICAgICAgICBcImV4cGlyZXNfaW5cIjogMzkyMCwgLy8gYWRkIHNlY29uZHMgdG8gbm93XG4gICAgICAgICAgXCJzY29wZVwiOiBcImh0dHBzOi8vd3d3Lmdvb2dsZWFwaXMuY29tL2F1dGgvZHJpdmUubWV0YWRhdGEucmVhZG9ubHlcIixcbiAgICAgICAgICBcInRva2VuX3R5cGVcIjogXCJCZWFyZXJcIlxuICAgICAgICB9XG4gICAgICAgICovXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byByZWZyZXNoIGdvb2dsZSB0b2tlbicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0R29vZ2xlQVBJVG9rZW4gPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICByZXNvdXJjZTogc3RyaW5nLFxuICBjbGllbnRUeXBlOiAnaW9zJyB8ICdhbmRyb2lkJyB8ICd3ZWInIHwgJ2F0b21pYy13ZWInXG4pID0+IHtcbiAgbGV0IGludGVncmF0aW9uSWQgPSAnJztcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGlkLCB0b2tlbiwgZXhwaXJlc0F0LCByZWZyZXNoVG9rZW4gfSA9IGF3YWl0IGdldENhbGVuZGFySW50ZWdyYXRpb24oXG4gICAgICB1c2VySWQsXG4gICAgICByZXNvdXJjZVxuICAgICk7XG4gICAgaW50ZWdyYXRpb25JZCA9IGlkO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgaWQsXG4gICAgICB0b2tlbixcbiAgICAgIGV4cGlyZXNBdCxcbiAgICAgIHJlZnJlc2hUb2tlbixcbiAgICAgICcgaWQsIHRva2VuLCBleHBpcmVzQXQsIHJlZnJlc2hUb2tlbidcbiAgICApO1xuICAgIGlmIChkYXlqcygpLmlzQWZ0ZXIoZGF5anMoZXhwaXJlc0F0KSkgfHwgIXRva2VuKSB7XG4gICAgICBjb25zdCByZXMgPSBhd2FpdCByZWZyZXNoR29vZ2xlVG9rZW4ocmVmcmVzaFRva2VuLCBjbGllbnRUeXBlKTtcbiAgICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSByZWZyZXNoR29vZ2xlVG9rZW4nKTtcbiAgICAgIGF3YWl0IHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24oaWQsIHJlcy5hY2Nlc3NfdG9rZW4sIHJlcy5leHBpcmVzX2luKTtcbiAgICAgIHJldHVybiByZXMuYWNjZXNzX3Rva2VuO1xuICAgIH1cbiAgICByZXR1cm4gdG9rZW47XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgYXBpIHRva2VuJyk7XG4gICAgYXdhaXQgdXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbihpbnRlZ3JhdGlvbklkLCBudWxsLCBudWxsLCBmYWxzZSk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVHb29nbGVFdmVudCA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ6IHN0cmluZyxcbiAgY2xpZW50VHlwZTogJ2lvcycgfCAnYW5kcm9pZCcgfCAnd2ViJyB8ICdhdG9taWMtd2ViJyxcbiAgZ2VuZXJhdGVkSWQ/OiBzdHJpbmcsXG4gIGVuZERhdGVUaW1lPzogc3RyaW5nLCAvLyBlaXRoZXIgZW5kRGF0ZVRpbWUgb3IgZW5kRGF0ZSAtIGFsbCBkYXkgdnMgc3BlY2lmaWMgcGVyaW9kXG4gIHN0YXJ0RGF0ZVRpbWU/OiBzdHJpbmcsXG4gIGNvbmZlcmVuY2VEYXRhVmVyc2lvbj86IDAgfCAxLFxuICBtYXhBdHRlbmRlZXM/OiBudW1iZXIsXG4gIHNlbmRVcGRhdGVzPzogR29vZ2xlU2VuZFVwZGF0ZXNUeXBlLFxuICBhbnlvbmVDYW5BZGRTZWxmPzogYm9vbGVhbixcbiAgYXR0ZW5kZWVzPzogR29vZ2xlQXR0ZW5kZWVUeXBlW10sXG4gIGNvbmZlcmVuY2VEYXRhPzogR29vZ2xlQ29uZmVyZW5jZURhdGFUeXBlLFxuICBzdW1tYXJ5Pzogc3RyaW5nLFxuICBkZXNjcmlwdGlvbj86IHN0cmluZyxcbiAgdGltZXpvbmU/OiBzdHJpbmcsIC8vIHJlcXVpcmVkIGZvciByZWN1cnJlbmNlXG4gIHN0YXJ0RGF0ZT86IHN0cmluZywgLy8gYWxsIGRheVxuICBlbmREYXRlPzogc3RyaW5nLCAvLyBhbGwgZGF5XG4gIGV4dGVuZGVkUHJvcGVydGllcz86IEdvb2dsZUV4dGVuZGVkUHJvcGVydGllc1R5cGUsXG4gIGd1ZXN0c0Nhbkludml0ZU90aGVycz86IGJvb2xlYW4sXG4gIGd1ZXN0c0Nhbk1vZGlmeT86IGJvb2xlYW4sXG4gIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzPzogYm9vbGVhbixcbiAgb3JpZ2luYWxTdGFydERhdGVUaW1lPzogc3RyaW5nLFxuICBvcmlnaW5hbFN0YXJ0RGF0ZT86IHN0cmluZyxcbiAgcmVjdXJyZW5jZT86IHN0cmluZ1tdLFxuICByZW1pbmRlcnM/OiBHb29nbGVSZW1pbmRlclR5cGUsXG4gIHNvdXJjZT86IEdvb2dsZVNvdXJjZVR5cGUsXG4gIHN0YXR1cz86IHN0cmluZyxcbiAgdHJhbnNwYXJlbmN5PzogR29vZ2xlVHJhbnNwYXJlbmN5VHlwZSxcbiAgdmlzaWJpbGl0eT86IEdvb2dsZVZpc2liaWxpdHlUeXBlLFxuICBpQ2FsVUlEPzogc3RyaW5nLFxuICBhdHRlbmRlZXNPbWl0dGVkPzogYm9vbGVhbixcbiAgaGFuZ291dExpbms/OiBzdHJpbmcsXG4gIHByaXZhdGVDb3B5PzogYm9vbGVhbixcbiAgbG9ja2VkPzogYm9vbGVhbixcbiAgYXR0YWNobWVudHM/OiBHb29nbGVBdHRhY2htZW50VHlwZVtdLFxuICBldmVudFR5cGU/OiBHb29nbGVFdmVudFR5cGUxLFxuICBsb2NhdGlvbj86IHN0cmluZyxcbiAgY29sb3JJZD86IHN0cmluZ1xuKTogUHJvbWlzZTxHb29nbGVSZXNUeXBlPiA9PiB7XG4gIHRyeSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBnZW5lcmF0ZWRJZCxcbiAgICAgIGNvbmZlcmVuY2VEYXRhVmVyc2lvbixcbiAgICAgIGNvbmZlcmVuY2VEYXRhLFxuICAgICAgJyBnZW5lcmF0ZWRJZCwgY29uZmVyZW5jZURhdGFWZXJzaW9uLCBjb25mZXJlbmNlRGF0YSBpbnNpZGUgY3JlYXRlR29vZ2xlRXZlbnQnXG4gICAgKTtcbiAgICAvLyBnZXQgdG9rZW4gPVxuICAgIGNvbnN0IHRva2VuID0gYXdhaXQgZ2V0R29vZ2xlQVBJVG9rZW4oXG4gICAgICB1c2VySWQsXG4gICAgICBnb29nbGVDYWxlbmRhclJlc291cmNlLFxuICAgICAgY2xpZW50VHlwZVxuICAgICk7XG5cbiAgICBjb25zdCBnb29nbGVDYWxlbmRhciA9IGdvb2dsZS5jYWxlbmRhcih7XG4gICAgICB2ZXJzaW9uOiAndjMnLFxuICAgICAgaGVhZGVyczoge1xuICAgICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7dG9rZW59YCxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICAvLyBjcmVhdGUgcmVxdWVzdCBib2R5XG4gICAgbGV0IGRhdGE6IGFueSA9IHt9O1xuXG4gICAgaWYgKGVuZERhdGVUaW1lICYmIHRpbWV6b25lICYmICFlbmREYXRlKSB7XG4gICAgICBjb25zdCBlbmQgPSB7XG4gICAgICAgIGRhdGVUaW1lOiBlbmREYXRlVGltZSxcbiAgICAgICAgdGltZVpvbmU6IHRpbWV6b25lLFxuICAgICAgfTtcblxuICAgICAgZGF0YS5lbmQgPSBlbmQ7XG4gICAgfVxuXG4gICAgaWYgKGVuZERhdGUgJiYgdGltZXpvbmUgJiYgIWVuZERhdGVUaW1lKSB7XG4gICAgICBjb25zdCBlbmQgPSB7XG4gICAgICAgIGRhdGU6IGRheWpzKGVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgICAgIHRpbWVab25lOiB0aW1lem9uZSxcbiAgICAgIH07XG5cbiAgICAgIGRhdGEuZW5kID0gZW5kO1xuICAgIH1cblxuICAgIGlmIChzdGFydERhdGUgJiYgdGltZXpvbmUgJiYgIXN0YXJ0RGF0ZVRpbWUpIHtcbiAgICAgIGNvbnN0IHN0YXJ0ID0ge1xuICAgICAgICBkYXRlOiBkYXlqcyhzdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgICAgIHRpbWVab25lOiB0aW1lem9uZSxcbiAgICAgIH07XG4gICAgICBkYXRhLnN0YXJ0ID0gc3RhcnQ7XG4gICAgfVxuXG4gICAgaWYgKHN0YXJ0RGF0ZVRpbWUgJiYgdGltZXpvbmUgJiYgIXN0YXJ0RGF0ZSkge1xuICAgICAgY29uc3Qgc3RhcnQgPSB7XG4gICAgICAgIGRhdGVUaW1lOiBzdGFydERhdGVUaW1lLFxuICAgICAgICB0aW1lWm9uZTogdGltZXpvbmUsXG4gICAgICB9O1xuICAgICAgZGF0YS5zdGFydCA9IHN0YXJ0O1xuICAgIH1cblxuICAgIGlmIChvcmlnaW5hbFN0YXJ0RGF0ZSAmJiB0aW1lem9uZSAmJiAhb3JpZ2luYWxTdGFydERhdGVUaW1lKSB7XG4gICAgICBjb25zdCBvcmlnaW5hbFN0YXJ0VGltZSA9IHtcbiAgICAgICAgZGF0ZTogb3JpZ2luYWxTdGFydERhdGUsXG4gICAgICAgIHRpbWVab25lOiB0aW1lem9uZSxcbiAgICAgIH07XG4gICAgICBkYXRhLm9yaWdpbmFsU3RhcnRUaW1lID0gb3JpZ2luYWxTdGFydFRpbWU7XG4gICAgfVxuXG4gICAgaWYgKG9yaWdpbmFsU3RhcnREYXRlVGltZSAmJiB0aW1lem9uZSAmJiAhb3JpZ2luYWxTdGFydERhdGUpIHtcbiAgICAgIGNvbnN0IG9yaWdpbmFsU3RhcnRUaW1lID0ge1xuICAgICAgICBkYXRlVGltZTogZGF5anMob3JpZ2luYWxTdGFydERhdGVUaW1lKS50eih0aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KCksXG4gICAgICAgIHRpbWVab25lOiB0aW1lem9uZSxcbiAgICAgIH07XG4gICAgICBkYXRhLm9yaWdpbmFsU3RhcnRUaW1lID0gb3JpZ2luYWxTdGFydFRpbWU7XG4gICAgfVxuXG4gICAgaWYgKGFueW9uZUNhbkFkZFNlbGYpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGFueW9uZUNhbkFkZFNlbGYgfTtcbiAgICB9XG5cbiAgICBpZiAoYXR0ZW5kZWVzPy5bMF0/LmVtYWlsKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBhdHRlbmRlZXMgfTtcbiAgICB9XG5cbiAgICBpZiAoY29uZmVyZW5jZURhdGE/LmNyZWF0ZVJlcXVlc3QpIHtcbiAgICAgIGRhdGEgPSB7XG4gICAgICAgIC4uLmRhdGEsXG4gICAgICAgIGNvbmZlcmVuY2VEYXRhOiB7XG4gICAgICAgICAgY3JlYXRlUmVxdWVzdDoge1xuICAgICAgICAgICAgY29uZmVyZW5jZVNvbHV0aW9uS2V5OiB7XG4gICAgICAgICAgICAgIHR5cGU6IGNvbmZlcmVuY2VEYXRhLnR5cGUsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgcmVxdWVzdElkOiBjb25mZXJlbmNlRGF0YT8ucmVxdWVzdElkIHx8IHV1aWQoKSxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9IGVsc2UgaWYgKGNvbmZlcmVuY2VEYXRhPy5lbnRyeVBvaW50cz8uWzBdKSB7XG4gICAgICBkYXRhID0ge1xuICAgICAgICAuLi5kYXRhLFxuICAgICAgICBjb25mZXJlbmNlRGF0YToge1xuICAgICAgICAgIGNvbmZlcmVuY2VTb2x1dGlvbjoge1xuICAgICAgICAgICAgaWNvblVyaTogY29uZmVyZW5jZURhdGE/Lmljb25VcmksXG4gICAgICAgICAgICBrZXk6IHtcbiAgICAgICAgICAgICAgdHlwZTogY29uZmVyZW5jZURhdGE/LnR5cGUsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgbmFtZTogY29uZmVyZW5jZURhdGE/Lm5hbWUsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBlbnRyeVBvaW50czogY29uZmVyZW5jZURhdGE/LmVudHJ5UG9pbnRzLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoZGVzY3JpcHRpb24/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGRlc2NyaXB0aW9uIH07XG4gICAgfVxuXG4gICAgaWYgKGV4dGVuZGVkUHJvcGVydGllcz8ucHJpdmF0ZSB8fCBleHRlbmRlZFByb3BlcnRpZXM/LnNoYXJlZCkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgZXh0ZW5kZWRQcm9wZXJ0aWVzIH07XG4gICAgfVxuXG4gICAgaWYgKGd1ZXN0c0Nhbkludml0ZU90aGVycykge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzIH07XG4gICAgfVxuXG4gICAgaWYgKGd1ZXN0c0Nhbk1vZGlmeSkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgZ3Vlc3RzQ2FuTW9kaWZ5IH07XG4gICAgfVxuXG4gICAgaWYgKGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyB9O1xuICAgIH1cblxuICAgIGlmIChsb2NrZWQpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGxvY2tlZCB9O1xuICAgIH1cblxuICAgIGlmIChwcml2YXRlQ29weSkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgcHJpdmF0ZUNvcHkgfTtcbiAgICB9XG5cbiAgICBpZiAocmVjdXJyZW5jZT8uWzBdKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCByZWN1cnJlbmNlIH07XG4gICAgfVxuXG4gICAgaWYgKHJlbWluZGVycz8ub3ZlcnJpZGVzPy5sZW5ndGggPiAwIHx8IHJlbWluZGVycz8udXNlRGVmYXVsdCkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgcmVtaW5kZXJzIH07XG4gICAgfVxuXG4gICAgaWYgKHNvdXJjZT8udGl0bGUgfHwgc291cmNlPy51cmwpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIHNvdXJjZSB9O1xuICAgIH1cblxuICAgIGlmIChhdHRhY2htZW50cz8uWzBdPy5maWxlSWQpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGF0dGFjaG1lbnRzIH07XG4gICAgfVxuXG4gICAgaWYgKGV2ZW50VHlwZT8ubGVuZ3RoID4gMCkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgZXZlbnRUeXBlIH07XG4gICAgfVxuXG4gICAgaWYgKHN0YXR1cykge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgc3RhdHVzIH07XG4gICAgfVxuXG4gICAgaWYgKHRyYW5zcGFyZW5jeSkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgdHJhbnNwYXJlbmN5IH07XG4gICAgfVxuXG4gICAgaWYgKHZpc2liaWxpdHkpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIHZpc2liaWxpdHkgfTtcbiAgICB9XG5cbiAgICBpZiAoaUNhbFVJRD8ubGVuZ3RoID4gMCkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgaUNhbFVJRCB9O1xuICAgIH1cblxuICAgIGlmIChhdHRlbmRlZXNPbWl0dGVkKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBhdHRlbmRlZXNPbWl0dGVkIH07XG4gICAgfVxuXG4gICAgaWYgKGhhbmdvdXRMaW5rPy5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBoYW5nb3V0TGluayB9O1xuICAgIH1cblxuICAgIGlmIChzdW1tYXJ5Py5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBzdW1tYXJ5IH07XG4gICAgfVxuXG4gICAgaWYgKGxvY2F0aW9uPy5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBsb2NhdGlvbiB9O1xuICAgIH1cblxuICAgIGlmIChjb2xvcklkKSB7XG4gICAgICBkYXRhLmNvbG9ySWQgPSBjb2xvcklkO1xuICAgIH1cblxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGdvb2dsZUNhbGVuZGFyLmV2ZW50cy5pbnNlcnQoe1xuICAgICAgLy8gQ2FsZW5kYXIgaWRlbnRpZmllci4gVG8gcmV0cmlldmUgY2FsZW5kYXIgSURzIGNhbGwgdGhlIGNhbGVuZGFyTGlzdC5saXN0IG1ldGhvZC4gSWYgeW91IHdhbnQgdG8gYWNjZXNzIHRoZSBwcmltYXJ5IGNhbGVuZGFyIG9mIHRoZSBjdXJyZW50bHkgbG9nZ2VkIGluIHVzZXIsIHVzZSB0aGUgXCJwcmltYXJ5XCIga2V5d29yZC5cbiAgICAgIGNhbGVuZGFySWQsXG4gICAgICAvLyBWZXJzaW9uIG51bWJlciBvZiBjb25mZXJlbmNlIGRhdGEgc3VwcG9ydGVkIGJ5IHRoZSBBUEkgY2xpZW50LiBWZXJzaW9uIDAgYXNzdW1lcyBubyBjb25mZXJlbmNlIGRhdGEgc3VwcG9ydCBhbmQgaWdub3JlcyBjb25mZXJlbmNlIGRhdGEgaW4gdGhlIGV2ZW50J3MgYm9keS4gVmVyc2lvbiAxIGVuYWJsZXMgc3VwcG9ydCBmb3IgY29weWluZyBvZiBDb25mZXJlbmNlRGF0YSBhcyB3ZWxsIGFzIGZvciBjcmVhdGluZyBuZXcgY29uZmVyZW5jZXMgdXNpbmcgdGhlIGNyZWF0ZVJlcXVlc3QgZmllbGQgb2YgY29uZmVyZW5jZURhdGEuIFRoZSBkZWZhdWx0IGlzIDAuXG4gICAgICBjb25mZXJlbmNlRGF0YVZlcnNpb24sXG4gICAgICAvLyBUaGUgbWF4aW11bSBudW1iZXIgb2YgYXR0ZW5kZWVzIHRvIGluY2x1ZGUgaW4gdGhlIHJlc3BvbnNlLiBJZiB0aGVyZSBhcmUgbW9yZSB0aGFuIHRoZSBzcGVjaWZpZWQgbnVtYmVyIG9mIGF0dGVuZGVlcywgb25seSB0aGUgcGFydGljaXBhbnQgaXMgcmV0dXJuZWQuIE9wdGlvbmFsLlxuICAgICAgbWF4QXR0ZW5kZWVzLFxuICAgICAgLy8gV2hldGhlciB0byBzZW5kIG5vdGlmaWNhdGlvbnMgYWJvdXQgdGhlIGNyZWF0aW9uIG9mIHRoZSBuZXcgZXZlbnQuIE5vdGUgdGhhdCBzb21lIGVtYWlscyBtaWdodCBzdGlsbCBiZSBzZW50LiBUaGUgZGVmYXVsdCBpcyBmYWxzZS5cbiAgICAgIHNlbmRVcGRhdGVzLFxuXG4gICAgICAvLyBSZXF1ZXN0IGJvZHkgbWV0YWRhdGFcbiAgICAgIHJlcXVlc3RCb2R5OiBkYXRhLFxuICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2cocmVzLmRhdGEpO1xuXG4gICAgY29uc29sZS5sb2cocmVzPy5kYXRhLCAnIHJlcz8uZGF0YSBmcm9tIGdvb2dsZUNyZWF0ZUV2ZW50Jyk7XG4gICAgcmV0dXJuIHtcbiAgICAgIGlkOiBgJHtyZXM/LmRhdGE/LmlkfSMke2NhbGVuZGFySWR9YCxcbiAgICAgIGdvb2dsZUV2ZW50SWQ6IHJlcz8uZGF0YT8uaWQsXG4gICAgICBnZW5lcmF0ZWRJZCxcbiAgICAgIGNhbGVuZGFySWQsXG4gICAgICBnZW5lcmF0ZWRFdmVudElkOiBnZW5lcmF0ZWRJZD8uc3BsaXQoJyMnKVswXSxcbiAgICB9O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyBjcmVhdGVHb29nbGVFdmVudCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBzZXJ0RXZlbnRzID0gYXN5bmMgKGV2ZW50czogRXZlbnRUeXBlW10pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0luc2VydEV2ZW50JztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIG11dGF0aW9uIEluc2VydEV2ZW50KCRldmVudHM6IFtFdmVudF9pbnNlcnRfaW5wdXQhXSEpIHtcbiAgICAgICAgICAgICAgICBpbnNlcnRfRXZlbnQoXG4gICAgICAgICAgICAgICAgICAgIG9iamVjdHM6ICRldmVudHMsXG4gICAgICAgICAgICAgICAgICAgIG9uX2NvbmZsaWN0OiB7XG4gICAgICAgICAgICAgICAgICAgICAgICBjb25zdHJhaW50OiBFdmVudF9wa2V5LFxuICAgICAgICAgICAgICAgICAgICAgICAgdXBkYXRlX2NvbHVtbnM6IFtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdGl0bGUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc3RhcnREYXRlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGVuZERhdGUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgYWxsRGF5LFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VSdWxlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIG5vdGVzLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGF0dGFjaG1lbnRzLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGxpbmtzLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGRlbGV0ZWQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdGFza0lkLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHRhc2tUeXBlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHByaW9yaXR5LFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGZvbGxvd1VwRXZlbnRJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBpc0ZvbGxvd1VwLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlzUHJlRXZlbnQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaXNQb3N0RXZlbnQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcHJlRXZlbnRJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBwb3N0RXZlbnRJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBtb2RpZmlhYmxlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGZvckV2ZW50SWQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29uZmVyZW5jZUlkLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1heEF0dGVuZGVlcyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzZW5kVXBkYXRlcyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbEFsbERheSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzdGF0dXMsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc3VtbWFyeSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB0cmFuc3BhcmVuY3ksXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdmlzaWJpbGl0eSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICByZWN1cnJpbmdFdmVudElkLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBpQ2FsVUlELFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGh0bWxMaW5rLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvbG9ySWQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY3JlYXRvcixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBvcmdhbml6ZXIsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZW5kVGltZVVuc3BlY2lmaWVkLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2UsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxUaW1lem9uZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZXNPbWl0dGVkLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGV4dGVuZGVkUHJvcGVydGllcyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBoYW5nb3V0TGluayxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5Nb2RpZnksXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgbG9ja2VkLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHNvdXJjZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBldmVudFR5cGUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcHJpdmF0ZUNvcHksXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3IsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXMsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RTY29yZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdFNjb3JlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0VGltZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkRGF5T2ZXZWVrLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZFRpbWUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmcsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlzTWVldGluZ01vZGlmaWFibGUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaXNNZWV0aW5nLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGRhaWx5VGFza0xpc3QsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgd2Vla2x5VGFza0xpc3QsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgaXNCcmVhayxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2UsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weUF2YWlsYWJpbGl0eSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb3B5VGltZUJsb2NraW5nLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb3B5UmVtaW5kZXJzLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlQcmlvcml0eUxldmVsLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlNb2RpZmlhYmxlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlDYXRlZ29yaWVzLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlJc0JyZWFrLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHRpbWVCbG9ja2luZyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHksXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFJlbWluZGVycyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRQcmlvcml0eUxldmVsLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZENhdGVnb3JpZXMsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkTW9kaWZpYWJsZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRJc0JyZWFrLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGhhcmREZWFkbGluZSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBzb2Z0RGVhZGxpbmUsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weUlzTWVldGluZyxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmcsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNNZWV0aW5nLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlEdXJhdGlvbixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWREdXJhdGlvbixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB1bmxpbmssXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgY29weUNvbG9yLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZENvbG9yLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGJ5V2Vla0RheSxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBsb2NhbFN5bmNlZCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWQsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgIF1cbiAgICAgICAgICAgICAgICAgICAgfSl7XG4gICAgICAgICAgICAgICAgICAgIHJldHVybmluZyB7XG4gICAgICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG4gICAgXy51bmlxQnkoZXZlbnRzLCAnaWQnKS5mb3JFYWNoKChlKSA9PlxuICAgICAgY29uc29sZS5sb2coZT8uaWQsIGUsICdpZCwgZSBpbnNpZGUgdXBzZXJ0RXZlbnRzUG9zdFBsYW5uZXIgJylcbiAgICApO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGV2ZW50czogXy51bmlxQnkoZXZlbnRzLCAnaWQnKSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IHtcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgaW5zZXJ0X0V2ZW50OiB7IGFmZmVjdGVkX3Jvd3M6IG51bWJlcjsgcmV0dXJuaW5nOiB7IGlkOiBzdHJpbmcgfVtdIH07XG4gICAgICB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIHJlc3BvbnNlLFxuICAgICAgcmVzcG9uc2U/LmRhdGE/Lmluc2VydF9FdmVudD8uYWZmZWN0ZWRfcm93cyxcbiAgICAgICcgcmVzcG9uc2UgYWZ0ZXIgdXBzZXJ0aW5nIGV2ZW50cydcbiAgICApO1xuICAgIHJlc3BvbnNlPy5kYXRhPy5pbnNlcnRfRXZlbnQ/LnJldHVybmluZz8uZm9yRWFjaCgoZSkgPT5cbiAgICAgIGNvbnNvbGUubG9nKGUsICcgcmV0dXJuaW5nICByZXNwb25zZSBhZnRlciB1cHNlcnRpbmcgZXZlbnRzJylcbiAgICApO1xuICAgIHJldHVybiByZXNwb25zZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwZGF0ZSBldmVudCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgaW5zZXJ0UmVtaW5kZXJzID0gYXN5bmMgKHJlbWluZGVyczogUmVtaW5kZXJUeXBlW10pID0+IHtcbiAgdHJ5IHtcbiAgICAvLyB2YWxpZGF0ZVxuICAgIGlmICghKHJlbWluZGVycz8uZmlsdGVyKChlKSA9PiAhIWU/LmV2ZW50SWQpPy5sZW5ndGggPiAwKSkge1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIHJlbWluZGVycy5mb3JFYWNoKChyKSA9PlxuICAgICAgY29uc29sZS5sb2cociwgJyByZW1pbmRlciBpbnNpZGUgaW5zZXJ0UmVtaW5kZXJzJylcbiAgICApO1xuXG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdJbnNlcnRSZW1pbmRlcic7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBtdXRhdGlvbiBJbnNlcnRSZW1pbmRlcigkcmVtaW5kZXJzOiBbUmVtaW5kZXJfaW5zZXJ0X2lucHV0IV0hKSB7XG4gICAgICAgICAgICAgICAgaW5zZXJ0X1JlbWluZGVyKG9iamVjdHM6ICRyZW1pbmRlcnMpIHtcbiAgICAgICAgICAgICAgICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgICAgICAgICAgICAgICByZXR1cm5pbmcge1xuICAgICAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgICAgICBtZXRob2RcbiAgICAgICAgICAgICAgICAgICAgICAgIG1pbnV0ZXNcbiAgICAgICAgICAgICAgICAgICAgICAgIHJlbWluZGVyRGF0ZVxuICAgICAgICAgICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICAgICAgdXNlRGVmYXVsdFxuICAgICAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgcmVtaW5kZXJzLFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZToge1xuICAgICAgZGF0YTogeyBpbnNlcnRfUmVtaW5kZXI6IHsgcmV0dXJuaW5nOiBSZW1pbmRlclR5cGVbXSB9IH07XG4gICAgfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICByZXNwb25zZT8uZGF0YT8uaW5zZXJ0X1JlbWluZGVyPy5yZXR1cm5pbmcsXG4gICAgICAnIHRoaXMgaXMgcmVzcG9uc2UgaW4gaW5zZXJ0UmVtaW5kZXJzJ1xuICAgICk7XG4gICAgcmVzcG9uc2U/LmRhdGE/Lmluc2VydF9SZW1pbmRlcj8ucmV0dXJuaW5nLmZvckVhY2goKHIpID0+XG4gICAgICBjb25zb2xlLmxvZyhyLCAnIHJlc3BvbnNlIGluIGluc2VydFJlbWluZGVyJylcbiAgICApO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gaW5zZXJ0UmVtaW5kZXJzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBpbnNlcnRDb25mZXJlbmNlID0gYXN5bmMgKGNvbmZlcmVuY2U6IENvbmZlcmVuY2VUeXBlKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdJbnNlcnRDb25mZXJlbmNlJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIG11dGF0aW9uIEluc2VydENvbmZlcmVuY2UoJGNvbmZlcmVuY2U6IENvbmZlcmVuY2VfaW5zZXJ0X2lucHV0ISkge1xuICAgICAgICAgICAgICAgIGluc2VydF9Db25mZXJlbmNlX29uZShvYmplY3Q6ICRjb25mZXJlbmNlKSB7XG4gICAgICAgICAgICAgICAgICAgIGFwcFxuICAgICAgICAgICAgICAgICAgICBjYWxlbmRhcklkXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgICAgICAgICAgZW50cnlQb2ludHNcbiAgICAgICAgICAgICAgICAgICAgaGFuZ291dExpbmtcbiAgICAgICAgICAgICAgICAgICAgaWNvblVyaVxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBpc0hvc3RcbiAgICAgICAgICAgICAgICAgICAgam9pblVybFxuICAgICAgICAgICAgICAgICAgICBrZXlcbiAgICAgICAgICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgICAgICAgICBub3Rlc1xuICAgICAgICAgICAgICAgICAgICBwYXJhbWV0ZXJzXG4gICAgICAgICAgICAgICAgICAgIHJlcXVlc3RJZFxuICAgICAgICAgICAgICAgICAgICBzdGFydFVybFxuICAgICAgICAgICAgICAgICAgICBzdGF0dXNcbiAgICAgICAgICAgICAgICAgICAgdHlwZVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIHpvb21Qcml2YXRlTWVldGluZ1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGNvbmZlcmVuY2UsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IGluc2VydF9Db25mZXJlbmNlX29uZTogQ29uZmVyZW5jZVR5cGUgfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgc3VjY2Vzc2Z1bGx5IGluc2VydGVkIG9uZSBjb25mZXJlbmNlJyk7XG5cbiAgICByZXR1cm4gcmVzPy5kYXRhPy5pbnNlcnRfQ29uZmVyZW5jZV9vbmU7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBpbnNlcnQgY29uZmVyZW5jZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0VtYWlsQ29udGVudCA9IGFzeW5jIChjb250ZW50OiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCByYXdDb250ZW50ID0gY29udGVudDtcblxuICAgIGNvbnNvbGUubG9nKHJhd0NvbnRlbnQsICcgcmF3IGNvbnRlbnQnKTtcbiAgICBsZXQgaHRtbCA9ICcnO1xuXG4gICAgLy8gY29uc3QgaHRtbF9yZWdleCA9IEhUTUxfUkVHRVhfUEFUVEVSTlxuICAgIC8vIGNvbnN0IGh0bWxzID0gaHRtbF9yZWdleC5leGVjKHJhd0NvbnRlbnQpXG4gICAgLy8gY29uc29sZS5sb2coaHRtbHMsICcgaHRtbHMnKVxuICAgIC8vIGh0bWwgPSBodG1scz8uWzBdXG4gICAgLy8gdmFsaWRhdGUgYnkgbWF0Y2hpbmdcblxuICAgIC8vIHVzZSBjaGVlcmlvIHRvIGdldCBjb250ZW50XG4gICAgY29uc3QgZGVjb2RlZFJhd0NvbnRlbnQgPSBkZWNvZGVVUklDb21wb25lbnQoXG4gICAgICBxdW90ZWRQcmludGFibGUuZGVjb2RlKHJhd0NvbnRlbnQpXG4gICAgKTtcbiAgICBjb25zdCAkID0gY2hlZXJpby5sb2FkKGRlY29kZWRSYXdDb250ZW50KTtcblxuICAgICQoJ2RpdicpLmVhY2goKF8sIGVsZW1lbnQpID0+IHtcbiAgICAgIGNvbnNvbGUubG9nKCQoZWxlbWVudCkudGV4dCgpLCAnICQoZWxlbWVudCkudGV4dCgpJyk7XG4gICAgICBodG1sICs9ICQoZWxlbWVudCkudGV4dCgpO1xuICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2coaHRtbCwgJyBodG1sJyk7XG5cbiAgICBpZiAoIWh0bWwpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdodG1sIGlzIG5vdCBwcmVzZW50Jyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgY29uc3Qgc2hvcnRfaHRtbCA9XG4gICAgICBodG1sPy5sZW5ndGggPiBNQVhfQ0hBUkFDVEVSX0xJTUlUXG4gICAgICAgID8gaHRtbC5zbGljZSgwLCBNQVhfQ0hBUkFDVEVSX0xJTUlUKVxuICAgICAgICA6IGh0bWw7XG5cbiAgICBjb25zb2xlLmxvZyhzaG9ydF9odG1sLCAnIHNob3J0X2h0bWwnKTtcbiAgICBjb25zb2xlLmxvZyhzaG9ydF9odG1sLmxlbmd0aCwgJyBzaG9ydF9odG1sLmxlbmd0aCcpO1xuXG4gICAgY29uc3QgdXJsX3JlZ2V4ID0gQVRPTUlDX1NVQkRPTUFJTl9QQVRURVJOO1xuXG4gICAgY29uc3QgdXJscyA9IHVybF9yZWdleC5leGVjKGRlY29kZWRSYXdDb250ZW50KTtcblxuICAgIGNvbnNvbGUubG9nKHVybHMsICcgdXJscycpO1xuXG4gICAgbGV0IHVybCA9IHVybHM/LlswXTtcblxuICAgIGNvbnNvbGUubG9nKHVybCwgJyB1cmwnKTtcblxuICAgIGlmICghdXJsKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gdXJsIHByZXNlbnQnKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBjb25zdCB1cmxPYmplY3QgPSBuZXcgVVJMKFxuICAgICAgdXJsLnNsaWNlKDAsIHVybC5sZW5ndGggLSBOVU1CRVJfVE9fUkVNT1ZFX0ZPUl9TVUJET01BSU5fU0xJQ0UpXG4gICAgKTtcblxuICAgIC8vIGNvbnN0IHNlYXJjaFBhcmFtcyA9IG5ldyBVUkxTZWFyY2hQYXJhbXModXJsT2JqZWN0LnNlYXJjaClcblxuICAgIGNvbnNvbGUubG9nKHVybE9iamVjdC5ocmVmLCAnIHVybE9iamVjdC5ocmVmJyk7XG4gICAgLy8gY29uc29sZS5sb2coc2VhcmNoUGFyYW1zLCAnIHNlYXJjaFBhcmFtcycpXG4gICAgdXJsID0gdXJsLnNsaWNlKDAsIHVybC5sZW5ndGggLSBOVU1CRVJfVE9fUkVNT1ZFX0ZPUl9TVUJET01BSU5fU0xJQ0UpO1xuXG4gICAgY29uc3QgdXJsUUluZGV4ID0gdXJsLmluZGV4T2YoJz8nKTtcbiAgICBjb25zdCB1cmxTaG9ydCA9IHVybC5zbGljZSh1cmxRSW5kZXggKyAxKTtcbiAgICBjb25zdCBhdG9taWNRU1BhcmFtc1N0cmluZyA9IHVybFNob3J0O1xuXG4gICAgY29uc3QgcmF3UXVlcnlQYXJhbXNPYmplY3QgPSBxcy5wYXJzZShhdG9taWNRU1BhcmFtc1N0cmluZyk7XG5cbiAgICBjb25zb2xlLmxvZyhyYXdRdWVyeVBhcmFtc09iamVjdCwgJyByYXdRdWVyeVBhcmFtc09iamVjdCcpO1xuXG4gICAgY29uc3QgbmV3UXVlcnlQYXJhbXNPYmplY3Q6IE1lZXRpbmdVcmxRdWVyeVBhcmFtc1R5cGUgfCB7fSA9IHt9O1xuXG4gICAgZm9yIChjb25zdCBrZXkgaW4gcmF3UXVlcnlQYXJhbXNPYmplY3QpIHtcbiAgICAgIGNvbnN0IG5ld0tleSA9IGtleS5yZXBsYWNlKCdhbXA7JywgJycpO1xuXG4gICAgICBpZiAodHlwZW9mIHJhd1F1ZXJ5UGFyYW1zT2JqZWN0W2tleV0gPT09ICdzdHJpbmcnKSB7XG4gICAgICAgIGNvbnN0IG9sZFZhbHVlOiBzdHJpbmcgPSByYXdRdWVyeVBhcmFtc09iamVjdFtrZXldIHx8ICcnO1xuICAgICAgICBjb25zdCBuZXdWYWx1ZSA9IG9sZFZhbHVlPy5yZXBsYWNlKFxuICAgICAgICAgICdcIiB0YXJnZXQ9XCJfYmxhbmtcIj5BdG9taWM8L2E+IDopPC9wcicsXG4gICAgICAgICAgJydcbiAgICAgICAgKTtcbiAgICAgICAgbmV3UXVlcnlQYXJhbXNPYmplY3RbbmV3S2V5XSA9IG5ld1ZhbHVlO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgbmV3UXVlcnlQYXJhbXNPYmplY3RbbmV3S2V5XSA9IHJhd1F1ZXJ5UGFyYW1zT2JqZWN0W2tleV07XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2cobmV3UXVlcnlQYXJhbXNPYmplY3QsICcgbmV3UXVlcnlQYXJhbXNPYmplY3QnKTtcblxuICAgIGlmICghKG5ld1F1ZXJ5UGFyYW1zT2JqZWN0IGFzIE1lZXRpbmdVcmxRdWVyeVBhcmFtc1R5cGUpPy51c2VySWQpIHtcbiAgICAgIGNvbnNvbGUubG9nKCcgbmV3UXVlcnlQYXJhbXNPYmplY3Qgbm90IHBhcnNlZCBwcm9wZXJseScpO1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIGNvbnN0IHF1ZXJ5UGFyYW1zT2JqZWN0OiBNZWV0aW5nVXJsUXVlcnlQYXJhbXNUeXBlID1cbiAgICAgIG5ld1F1ZXJ5UGFyYW1zT2JqZWN0IGFzIE1lZXRpbmdVcmxRdWVyeVBhcmFtc1R5cGU7XG5cbiAgICBjb25zdCB1c2VySWQgPSBxdWVyeVBhcmFtc09iamVjdD8udXNlcklkO1xuICAgIGNvbnN0IHRpbWV6b25lID0gcXVlcnlQYXJhbXNPYmplY3Q/LnRpbWV6b25lO1xuICAgIGNvbnN0IGF0dGVuZGVlRW1haWxzID0gcXVlcnlQYXJhbXNPYmplY3Q/LmF0dGVuZGVlRW1haWxzO1xuICAgIGNvbnN0IGR1cmF0aW9uID0gcXVlcnlQYXJhbXNPYmplY3Q/LmR1cmF0aW9uO1xuICAgIGNvbnN0IGNhbGVuZGFySWQgPSBxdWVyeVBhcmFtc09iamVjdD8uY2FsZW5kYXJJZDtcbiAgICBjb25zdCBzdGFydFRpbWUgPSBxdWVyeVBhcmFtc09iamVjdD8uc3RhcnRUaW1lO1xuICAgIGNvbnN0IG5hbWUgPSBxdWVyeVBhcmFtc09iamVjdD8ubmFtZTtcbiAgICBjb25zdCBwcmltYXJ5RW1haWwgPSBxdWVyeVBhcmFtc09iamVjdD8ucHJpbWFyeUVtYWlsO1xuICAgIC8vIGNvbnN0IGF0dGFjaG1lbnRzID0gcXVlcnlQYXJhbXNPYmplY3Q/LmF0dGFjaG1lbnRzXG5cbiAgICAvLyB2YWxpZGF0ZVxuICAgIGlmICghdXNlcklkKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIHVzZXJJZCBwcmVzZW50IGluc2lkZSBxdWVyeSBwYXJhbXMnKTtcbiAgICB9XG5cbiAgICBpZiAoIXRpbWV6b25lKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIHRpbWV6b25lIHByb3ZpZGVkJyk7XG4gICAgfVxuXG4gICAgaWYgKCEoYXR0ZW5kZWVFbWFpbHM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIGF0dGVuZGVlIGVtYWlscycpO1xuICAgIH1cblxuICAgIGlmICghZHVyYXRpb24pIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gZHVyYXRpb24gcHJvdmlkZWQnKTtcbiAgICB9XG5cbiAgICBpZiAoIW5hbWUpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gbmFtZSBwcm92aWRlZCcpO1xuICAgIH1cblxuICAgIGlmICghY2FsZW5kYXJJZCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBjYWxlbmRhcklkIHByb3ZpZGVkJyk7XG4gICAgfVxuXG4gICAgaWYgKCFwcmltYXJ5RW1haWwpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gbmV3IHByaW1hcnlFbWFpbCcpO1xuICAgIH1cblxuICAgIC8vIGdldCBvcGVuYWkga2V5XG5cbiAgICBjb25zdCBvcGVuYWkgPSBuZXcgT3BlbkFJKHtcbiAgICAgIGFwaUtleTogZGVmYXVsdE9wZW5BSUFQSUtleSxcbiAgICB9KTtcblxuICAgIC8vIGNoZWNrIGZvciB3aGV0aGVyIGEgbWVldGluZyB0aW1lIGlzIHNjaGVkdWxlZCBvciBub3RcbiAgICBjb25zdCBpc01lZXRpbmdQcm9tcHQgPSBpc01lZXRpbmdUaW1lU2NoZWR1bGVkUHJvbXB0O1xuXG4gICAgY29uc3QgaXNNZWV0aW5nVXNlckRhdGEgPSBgZW1haWwgYm9keTogJHtzaG9ydF9odG1sfWA7XG5cbiAgICBjb25zdCBvcGVuQUlSZXNGb3JNZWV0aW5nVGltZVNjaGVkdWxlZCA9IGF3YWl0IGNhbGxPcGVuQUkoXG4gICAgICBpc01lZXRpbmdQcm9tcHQsXG4gICAgICBvcGVuQUlDaGF0R1BUTW9kZWwsXG4gICAgICBpc01lZXRpbmdVc2VyRGF0YSxcbiAgICAgIG9wZW5haSxcbiAgICAgIGlzTWVldGluZ1RpbWVTY2hlZHVsZWRFeGFtcGxlSW5wdXQsXG4gICAgICBpc01lZXRpbmdUaW1lU2NoZWR1bGVkRXhhbXBsZU91dHB1dFxuICAgICk7XG5cbiAgICAvLyBwYXJzZSBKU09OXG4gICAgY29uc29sZS5sb2coXG4gICAgICBvcGVuQUlSZXNGb3JNZWV0aW5nVGltZVNjaGVkdWxlZCxcbiAgICAgICcgb3BlbkFJUmVzRm9yTWVldGluZ1RpbWVTY2hlZHVsZWQnXG4gICAgKTtcbiAgICAvLyBDaGF0R1BUIHJlc3BvbnNlXG4gICAgLy8geyBcInRpbWVfcHJvdmlkZWRcIjogdHJ1ZSB9XG5cbiAgICBjb25zdCBzdGFydEluZGV4ID0gb3BlbkFJUmVzRm9yTWVldGluZ1RpbWVTY2hlZHVsZWQ/LmluZGV4T2YoJ3snKTtcbiAgICBjb25zdCBlbmRJbmRleCA9IG9wZW5BSVJlc0Zvck1lZXRpbmdUaW1lU2NoZWR1bGVkPy5pbmRleE9mKCd9Jyk7XG5cbiAgICBjb25zdCBpc01lZXRpbmdUaW1lU2NoZWR1bGVkU3RyaW5nID0gb3BlbkFJUmVzRm9yTWVldGluZ1RpbWVTY2hlZHVsZWQuc2xpY2UoXG4gICAgICBzdGFydEluZGV4LFxuICAgICAgZW5kSW5kZXggKyAxXG4gICAgKTtcblxuICAgIGNvbnN0IGlzTWVldGluZ1NjaGVkdWxlZE9iamVjdDogaXNNZWV0aW5nU2NoZWR1bGVkT2JqZWN0VHlwZSA9IEpTT04ucGFyc2UoXG4gICAgICBpc01lZXRpbmdUaW1lU2NoZWR1bGVkU3RyaW5nXG4gICAgKTtcblxuICAgIC8vIHN0b3AgaWYgbWVldGluZyB0aW1lIGlzIG5vdCBzY2hlZHVsZWRcbiAgICBpZiAoIWlzTWVldGluZ1NjaGVkdWxlZE9iamVjdD8udGltZV9wcm92aWRlZCkge1xuICAgICAgY29uc29sZS5sb2coJ25vIG1lZXRpbmcgdGltZSBwcm92aWRlZCcpO1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIC8vIGV4dHJhY3QgZGF0YSBhbmQgdGltZVxuICAgIGNvbnN0IGV4dHJhY3REYXRlQW5kVGltZVByb21wdCA9IGV4dHJhY3REYXRlVGltZVByb21wdDtcbiAgICBjb25zdCBleHRyYWN0RGF0ZVRpbWVVc2VyRGF0YSA9IGBzdGFydCB0aW1lOiAke3N0YXJ0VGltZX0gXFxuIHRpbWV6b25lOiAke3RpbWV6b25lfSBcXG4gZW1haWwgSGlzdG9yeTogJHtzaG9ydF9odG1sfWA7XG5cbiAgICBjb25zdCBvcGVuQUlSZXNGb3JFeHRyYWN0RGF0ZVRpbWUgPSBhd2FpdCBjYWxsT3BlbkFJKFxuICAgICAgZXh0cmFjdERhdGVBbmRUaW1lUHJvbXB0LFxuICAgICAgb3BlbkFJQ2hhdEdQVE1vZGVsLFxuICAgICAgZXh0cmFjdERhdGVUaW1lVXNlckRhdGEsXG4gICAgICBvcGVuYWksXG4gICAgICBleHRyYWN0RGF0ZVRpbWVFeGFtcGxlSW5wdXQsXG4gICAgICBleHRyYWN0RGF0ZVRpbWVFeGFtcGxlT3V0cHV0XG4gICAgKTtcblxuICAgIGNvbnN0IHN0YXJ0SW5kZXgyID0gb3BlbkFJUmVzRm9yRXh0cmFjdERhdGVUaW1lPy5pbmRleE9mKCd7Jyk7XG4gICAgY29uc3QgZW5kSW5kZXgyID0gb3BlbkFJUmVzRm9yRXh0cmFjdERhdGVUaW1lPy5pbmRleE9mKCd9Jyk7XG5cbiAgICBjb25zdCBleHRyYWN0RGF0ZVRpbWVTdHJpbmcgPSBvcGVuQUlSZXNGb3JFeHRyYWN0RGF0ZVRpbWUuc2xpY2UoXG4gICAgICBzdGFydEluZGV4MixcbiAgICAgIGVuZEluZGV4MiArIDFcbiAgICApO1xuICAgIGNvbnN0IGV4dHJhY3REYXRlVGltZU9iamVjdDogRXh0cmFjdERhdGVUaW1lT2JqZWN0VHlwZSA9IEpTT04ucGFyc2UoXG4gICAgICBleHRyYWN0RGF0ZVRpbWVTdHJpbmdcbiAgICApO1xuXG4gICAgLy8gSVNPIDg2MDEgZm9ybWF0IHRpbWVcbiAgICBjb25zdCBtZWV0aW5nVGltZSA9IGV4dHJhY3REYXRlVGltZU9iamVjdD8ubWVldGluZ190aW1lO1xuXG4gICAgLy8gdmFsaWRhdGUgbWVldGluZ1RpbWVcbiAgICBpZiAoIW1lZXRpbmdUaW1lKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ3VuYWJsZSB0byBleHRyYWN0IGRhdGUgYW5kIHRpbWUnKTtcbiAgICB9XG5cbiAgICAvLyBzY2hlZHVsZSBtZWV0aW5nXG5cbiAgICAvLyBnZW5lcmF0ZSBtZWV0aW5nIHN1bW1hcnkgYW5kIG5vdGVzXG4gICAgY29uc3QgZ2VuZXJhdGVTdW1tYXJ5QW5kTm90ZXNQcm9tcHQgPSBnZW5lcmF0ZU1lZXRpbmdTdW1tYXJ5UHJvbXB0O1xuICAgIGNvbnN0IGdlbmVyYXRlU3VtbWFyeUFuZE5vdGVzVXNlckRhdGEgPSBgc3RhcnQgdGltZTogJHtzdGFydFRpbWV9IFxcbiB0aW1lem9uZTogJHt0aW1lem9uZX0gXFxuIGVtYWlsIEhpc3Rvcnk6ICR7c2hvcnRfaHRtbH1gO1xuICAgIGNvbnN0IG9wZW5BSVJlc0ZvclN1bW1hcnlBbmROb3RlcyA9IGF3YWl0IGNhbGxPcGVuQUkoXG4gICAgICBnZW5lcmF0ZVN1bW1hcnlBbmROb3Rlc1Byb21wdCxcbiAgICAgIG9wZW5BSUNoYXRHUFRNb2RlbCxcbiAgICAgIGdlbmVyYXRlU3VtbWFyeUFuZE5vdGVzVXNlckRhdGEsXG4gICAgICBvcGVuYWksXG4gICAgICBnZW5lcmF0ZU1lZXRpbmdTdW1tYXJ5SW5wdXQsXG4gICAgICBnZW5lcmF0ZU1lZXRpbmdTdW1tYXJ5T3V0cHV0XG4gICAgKTtcblxuICAgIGNvbnN0IHN0YXJ0SW5kZXgzID0gb3BlbkFJUmVzRm9yU3VtbWFyeUFuZE5vdGVzPy5pbmRleE9mKCd7Jyk7XG4gICAgY29uc3QgZW5kSW5kZXgzID0gb3BlbkFJUmVzRm9yU3VtbWFyeUFuZE5vdGVzPy5pbmRleE9mKCd9Jyk7XG5cbiAgICBjb25zdCBzdW1tYXJ5QW5kTm90ZXNTdHJpbmcgPSBvcGVuQUlSZXNGb3JTdW1tYXJ5QW5kTm90ZXMuc2xpY2UoXG4gICAgICBzdGFydEluZGV4MyxcbiAgICAgIGVuZEluZGV4MyArIDFcbiAgICApO1xuICAgIGNvbnN0IHN1bW1hcnlBbmROb3Rlc09iamVjdDogU3VtbWFyeUFuZE5vdGVzT2JqZWN0VHlwZSA9IEpTT04ucGFyc2UoXG4gICAgICBzdW1tYXJ5QW5kTm90ZXNTdHJpbmdcbiAgICApO1xuXG4gICAgLy8gZ2V0IHByaW1hcnkgY2FsZW5kYXJcbiAgICBjb25zdCBwcmltYXJ5Q2FsZW5kYXIgPSBhd2FpdCBnZXRHbG9iYWxDYWxlbmRhcih1c2VySWQpO1xuXG4gICAgLy8gdmFsaWRhdGVcbiAgICBpZiAoIXByaW1hcnlDYWxlbmRhcj8uaWQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gcHJpbWFyeSBjYWxlbmRhciBmb3VuZCBpbnNpZGUgY3JlYXRlQWdlbmRhJyk7XG4gICAgfVxuXG4gICAgLy8gZ2V0IGNsaWVudCB0eXBlXG4gICAgY29uc3QgY2FsSW50ZWdyYXRpb24gPSBhd2FpdCBnZXRDYWxlbmRhckludGVncmF0aW9uKFxuICAgICAgdXNlcklkLFxuICAgICAgZ29vZ2xlQ2FsZW5kYXJSZXNvdXJjZVxuICAgICk7XG5cbiAgICAvLyB2YWxpZGF0ZVxuICAgIGlmICghY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgJ25vIGNsaWVudCB0eXBlIGluc2lkZSBjYWxlbmRhciBpbnRlZ3JhdGlvbiBpbnNpZGUgY3JlYXRlIGFnZW5kYSdcbiAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc3QgZXZlbnRJZCA9IHV1aWQoKTtcblxuICAgIGNvbnN0IHJlbWluZGVyc1N0cmluZyA9IHF1ZXJ5UGFyYW1zT2JqZWN0Py5yZW1pbmRlcnM7XG5cbiAgICBjb25zdCByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQ6IFJlbWluZGVyVHlwZVtdID0gW107XG5cbiAgICBpZiAocmVtaW5kZXJzU3RyaW5nKSB7XG4gICAgICBjb25zdCBuZXdSZW1pbmRlcnM6IFJlbWluZGVyVHlwZVtdID0gcmVtaW5kZXJzU3RyaW5nLm1hcCgocikgPT4gKHtcbiAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBldmVudElkLCAvLyBnZW5lcmF0ZWRJZFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgbWludXRlczogcGFyc2VJbnQociwgMTApLFxuICAgICAgICB1c2VEZWZhdWx0OiBmYWxzZSxcbiAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICB9KSk7XG5cbiAgICAgIHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZC5wdXNoKC4uLm5ld1JlbWluZGVycyk7XG4gICAgfVxuXG4gICAgY29uc3QgZ29vZ2xlUmVtaW5kZXI6IEdvb2dsZVJlbWluZGVyVHlwZSA9IHtcbiAgICAgIG92ZXJyaWRlczogcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5tYXAoKHIpID0+ICh7XG4gICAgICAgIG1ldGhvZDogJ2VtYWlsJyxcbiAgICAgICAgbWludXRlczogcj8ubWludXRlcyxcbiAgICAgIH0pKSxcbiAgICAgIHVzZURlZmF1bHQ6IGZhbHNlLFxuICAgIH07XG5cbiAgICAvLyBjcmVhdGUgYXR0ZW5kZWVzIHRvIGNyZWF0ZSBpZiBhbnlcbiAgICBjb25zdCBhdHRlbmRlZXM6IEF0dGVuZGVlVHlwZVtdID0gW107XG4gICAgaWYgKGF0dGVuZGVlRW1haWxzPy5sZW5ndGggPiAwKSB7XG4gICAgICBmb3IgKGNvbnN0IGFFbWFpbCBvZiBhdHRlbmRlZUVtYWlscykge1xuICAgICAgICBjb25zdCBhdHRlbmRlZTogQXR0ZW5kZWVUeXBlID0ge1xuICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIG5hbWU6IHByaW1hcnlFbWFpbCA9PT0gYUVtYWlsID8gbmFtZSA6IHVuZGVmaW5lZCxcbiAgICAgICAgICBlbWFpbHM6IFt7IHByaW1hcnk6IHRydWUsIHZhbHVlOiBhRW1haWwgfV0sXG4gICAgICAgICAgZXZlbnRJZCwgLy8gZ2VuZXJhdGVkSWRcbiAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgIH07XG4gICAgICAgIGF0dGVuZGVlcy5wdXNoKGF0dGVuZGVlKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAocXVlcnlQYXJhbXNPYmplY3Q/LmVuYWJsZUNvbmZlcmVuY2UpIHtcbiAgICAgIGxldCBjb25mZXJlbmNlOiBDb25mZXJlbmNlVHlwZSB8IHt9ID0ge307XG4gICAgICAvLyBjcmVhdGUgY29uZmVyZW5jZSBvYmplY3RcbiAgICAgIGNvbnN0IHpvb21Ub2tlbiA9IGF3YWl0IGdldFpvb21BUElUb2tlbih1c2VySWQpO1xuICAgICAgY29uZmVyZW5jZSA9IHpvb21Ub2tlblxuICAgICAgICA/IHt9XG4gICAgICAgIDoge1xuICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgIGNhbGVuZGFySWQ6IGNhbGVuZGFySWQgfHwgcHJpbWFyeUNhbGVuZGFyPy5pZCxcbiAgICAgICAgICAgIGFwcDogJ2dvb2dsZScsXG4gICAgICAgICAgICBuYW1lLFxuICAgICAgICAgICAgbm90ZXM6IHN1bW1hcnlBbmROb3Rlc09iamVjdD8ubm90ZXMsXG4gICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICAgICAgaXNIb3N0OiB0cnVlLFxuICAgICAgICAgIH07XG5cbiAgICAgIGlmIChxdWVyeVBhcmFtc09iamVjdD8uY29uZmVyZW5jZUFwcCA9PT0gJ3pvb20nICYmIHpvb21Ub2tlbikge1xuICAgICAgICBpZiAoem9vbVRva2VuKSB7XG4gICAgICAgICAgY29uc29sZS5sb2coem9vbVRva2VuLCAnIHpvb21Ub2tlbiBpbnNpZGUgaWYgKHpvb21Ub2tlbiknKTtcblxuICAgICAgICAgIGNvbnN0IHpvb21PYmplY3QgPSBhd2FpdCBjcmVhdGVab29tTWVldGluZyhcbiAgICAgICAgICAgIHpvb21Ub2tlbixcbiAgICAgICAgICAgIG1lZXRpbmdUaW1lLFxuICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICBzdW1tYXJ5QW5kTm90ZXNPYmplY3Q/LnN1bW1hcnksXG4gICAgICAgICAgICBwYXJzZUludChkdXJhdGlvbiwgMTApLFxuICAgICAgICAgICAgbmFtZSxcbiAgICAgICAgICAgIHByaW1hcnlFbWFpbCxcbiAgICAgICAgICAgIGF0dGVuZGVlRW1haWxzXG4gICAgICAgICAgKTtcblxuICAgICAgICAgIGNvbnNvbGUubG9nKHpvb21PYmplY3QsICcgem9vbU9iamVjdCBhZnRlciBjcmVhdGVab29tTWVldGluZycpO1xuXG4gICAgICAgICAgaWYgKHpvb21PYmplY3QpIHtcbiAgICAgICAgICAgIGNvbmZlcmVuY2UgPSB7XG4gICAgICAgICAgICAgIGlkOiBgJHt6b29tT2JqZWN0Py5pZH1gLFxuICAgICAgICAgICAgICB1c2VySWQ6IHVzZXJJZCxcbiAgICAgICAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgICAgICAgICAgYXBwOiAnem9vbScsXG4gICAgICAgICAgICAgIG5hbWU6IHpvb21PYmplY3Q/LmFnZW5kYSxcbiAgICAgICAgICAgICAgbm90ZXM6IHpvb21PYmplY3Q/LmFnZW5kYSxcbiAgICAgICAgICAgICAgam9pblVybDogem9vbU9iamVjdD8uam9pbl91cmwsXG4gICAgICAgICAgICAgIHN0YXJ0VXJsOiB6b29tT2JqZWN0Py5zdGFydF91cmwsXG4gICAgICAgICAgICAgIGlzSG9zdDogdHJ1ZSxcbiAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgICAgICAgIGVudHJ5UG9pbnRzOiBbXG4gICAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgICAgZW50cnlQb2ludFR5cGU6ICd2aWRlbycsXG4gICAgICAgICAgICAgICAgICBsYWJlbDogem9vbU9iamVjdD8uam9pbl91cmwsXG4gICAgICAgICAgICAgICAgICBwYXNzd29yZDogem9vbU9iamVjdD8ucGFzc3dvcmQsXG4gICAgICAgICAgICAgICAgICB1cmk6IHpvb21PYmplY3Q/LmpvaW5fdXJsLFxuICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIF0sXG4gICAgICAgICAgICB9IGFzIENvbmZlcmVuY2VUeXBlO1xuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfVxuXG4gICAgICBjb25zdCBldmVudFRvVXBzZXJ0TG9jYWw6IEV2ZW50VHlwZSA9IHtcbiAgICAgICAgaWQ6IGV2ZW50SWQsXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgdGl0bGU6IHN1bW1hcnlBbmROb3Rlc09iamVjdD8uc3VtbWFyeSxcbiAgICAgICAgc3RhcnREYXRlOiBkYXlqcyhtZWV0aW5nVGltZSkudHoodGltZXpvbmUpLmZvcm1hdCgpLFxuICAgICAgICBlbmREYXRlOiBkYXlqcyhtZWV0aW5nVGltZSlcbiAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgLmFkZChwYXJzZUludChkdXJhdGlvbiwgMTApLCAnbScpXG4gICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICBhbGxEYXk6IGZhbHNlLFxuICAgICAgICBub3Rlczogc3VtbWFyeUFuZE5vdGVzT2JqZWN0Py5ub3RlcyxcbiAgICAgICAgdGltZXpvbmUsXG4gICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgcHJpb3JpdHk6IDEsXG4gICAgICAgIGlzRm9sbG93VXA6IGZhbHNlLFxuICAgICAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICAgICAgaXNQb3N0RXZlbnQ6IGZhbHNlLFxuICAgICAgICBtb2RpZmlhYmxlOiBmYWxzZSxcbiAgICAgICAgYW55b25lQ2FuQWRkU2VsZjpcbiAgICAgICAgICBxdWVyeVBhcmFtc09iamVjdD8uYW55b25lQ2FuQWRkU2VsZiA9PT0gJ3RydWUnID8gdHJ1ZSA6IGZhbHNlLFxuICAgICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnM6XG4gICAgICAgICAgcXVlcnlQYXJhbXNPYmplY3Q/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyA9PT0gJ3RydWUnID8gdHJ1ZSA6IGZhbHNlLFxuICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0czpcbiAgICAgICAgICBxdWVyeVBhcmFtc09iamVjdD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMgPT09ICd0cnVlJyA/IHRydWUgOiBmYWxzZSxcbiAgICAgICAgdHJhbnNwYXJlbmN5OiBxdWVyeVBhcmFtc09iamVjdD8udHJhbnNwYXJlbmN5LFxuICAgICAgICB2aXNpYmlsaXR5OiBxdWVyeVBhcmFtc09iamVjdD8udmlzaWJpbGl0eSxcbiAgICAgICAgb3JpZ2luYWxTdGFydERhdGU6IHVuZGVmaW5lZCxcbiAgICAgICAgb3JpZ2luYWxBbGxEYXk6IGZhbHNlLFxuICAgICAgICBzdW1tYXJ5OiBzdW1tYXJ5QW5kTm90ZXNPYmplY3Q/LnN1bW1hcnksXG4gICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgY2FsZW5kYXJJZDogY2FsZW5kYXJJZCB8fCBwcmltYXJ5Q2FsZW5kYXI/LmlkLFxuICAgICAgICBldmVudElkOiB1bmRlZmluZWQsXG4gICAgICAgIGNvbmZlcmVuY2VJZDogKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5pZCxcbiAgICAgICAgYXR0YWNobWVudHM6IHF1ZXJ5UGFyYW1zT2JqZWN0Py5hdHRhY2htZW50cyxcbiAgICAgICAgc2VuZFVwZGF0ZXM6IHF1ZXJ5UGFyYW1zT2JqZWN0Py5zZW5kVXBkYXRlcyxcbiAgICAgICAgZHVyYXRpb246IHBhcnNlSW50KHF1ZXJ5UGFyYW1zT2JqZWN0Py5kdXJhdGlvbiwgMTApLFxuICAgICAgfTtcblxuICAgICAgY29uc3QgZ29vZ2xlUmVzVmFsdWU6IEdvb2dsZVJlc1R5cGUgPSBhd2FpdCBjcmVhdGVHb29nbGVFdmVudChcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBjYWxlbmRhcklkLFxuICAgICAgICBjYWxJbnRlZ3JhdGlvbj8uY2xpZW50VHlwZSxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5pZCxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5lbmREYXRlLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnN0YXJ0RGF0ZSxcbiAgICAgICAgKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5pZCA/IDEgOiAwLFxuICAgICAgICAyLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnNlbmRVcGRhdGVzLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmFueW9uZUNhbkFkZFNlbGYsXG4gICAgICAgIGF0dGVuZGVlRW1haWxzPy5tYXAoKGEpID0+ICh7IGVtYWlsOiBhIH0pKSxcbiAgICAgICAgKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5pZFxuICAgICAgICAgID8ge1xuICAgICAgICAgICAgICB0eXBlOlxuICAgICAgICAgICAgICAgIChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8uYXBwID09PSAnem9vbSdcbiAgICAgICAgICAgICAgICAgID8gJ2FkZE9uJ1xuICAgICAgICAgICAgICAgICAgOiAnaGFuZ291dHNNZWV0JyxcbiAgICAgICAgICAgICAgbmFtZTogKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5uYW1lLFxuICAgICAgICAgICAgICBjb25mZXJlbmNlSWQ6IChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8uaWQsXG4gICAgICAgICAgICAgIGVudHJ5UG9pbnRzOiAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmVudHJ5UG9pbnRzLFxuICAgICAgICAgICAgICBjcmVhdGVSZXF1ZXN0OlxuICAgICAgICAgICAgICAgIChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8uYXBwID09PSAnZ29vZ2xlJ1xuICAgICAgICAgICAgICAgICAgPyB7XG4gICAgICAgICAgICAgICAgICAgICAgcmVxdWVzdElkOiAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LnJlcXVlc3RJZCxcbiAgICAgICAgICAgICAgICAgICAgICBjb25mZXJlbmNlU29sdXRpb25LZXk6IHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHR5cGU6ICdoYW5nb3V0c01lZXQnLFxuICAgICAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgIDogdW5kZWZpbmVkLFxuICAgICAgICAgICAgfVxuICAgICAgICAgIDogdW5kZWZpbmVkLFxuICAgICAgICBzdW1tYXJ5QW5kTm90ZXNPYmplY3Q/LnN1bW1hcnksXG4gICAgICAgIHN1bW1hcnlBbmROb3Rlc09iamVjdD8ubm90ZXMsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5ndWVzdHNDYW5Nb2RpZnksXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8ub3JpZ2luYWxTdGFydERhdGUsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQ/Lmxlbmd0aCA+IDAgPyBnb29nbGVSZW1pbmRlciA6IHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udHJhbnNwYXJlbmN5LFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnZpc2liaWxpdHksXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmF0dGFjaG1lbnRzLFxuICAgICAgICAnZGVmYXVsdCcsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkXG4gICAgICApO1xuXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZDtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5ldmVudElkID0gZ29vZ2xlUmVzVmFsdWUuZ29vZ2xlRXZlbnRJZDtcblxuICAgICAgLy8gdXBkYXRlIHJlbWluZGVycyBmb3IgZXZlbnQgSWRcbiAgICAgIHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZD8ubWFwKChyKSA9PiAoe1xuICAgICAgICAuLi5yLFxuICAgICAgICBldmVudElkOiBldmVudFRvVXBzZXJ0TG9jYWwuaWQsXG4gICAgICB9KSk7XG5cbiAgICAgIC8vIHVwZGF0ZSBhdHRlbmRlZXMgZm9yIGV2ZW50SWRcbiAgICAgIGF0dGVuZGVlcz8ubWFwKChhKSA9PiAoeyAuLi5hLCBldmVudElkOiBldmVudFRvVXBzZXJ0TG9jYWwuaWQgfSkpO1xuXG4gICAgICAvLyBpbnNlcnQgY29uZmVyZW5jZVxuICAgICAgYXdhaXQgaW5zZXJ0Q29uZmVyZW5jZShjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKTtcblxuICAgICAgLy8gaW5zZXJ0IGV2ZW50c1xuICAgICAgYXdhaXQgdXBzZXJ0RXZlbnRzKFtldmVudFRvVXBzZXJ0TG9jYWxdKTtcblxuICAgICAgLy8gaW5zZXJ0IHJlbWluZGVyc1xuICAgICAgaWYgKHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZD8ubGVuZ3RoID4gMCkge1xuICAgICAgICBhd2FpdCBpbnNlcnRSZW1pbmRlcnMocmVtaW5kZXJzVG9VcGRhdGVFdmVudElkKTtcbiAgICAgIH1cblxuICAgICAgaWYgKGF0dGVuZGVlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBhd2FpdCBpbnNlcnRBdHRlbmRlZXNmb3JFdmVudChhdHRlbmRlZXMpO1xuICAgICAgfVxuICAgIH0gZWxzZSB7XG4gICAgICBjb25zdCBldmVudFRvVXBzZXJ0TG9jYWw6IEV2ZW50VHlwZSA9IHtcbiAgICAgICAgaWQ6IGV2ZW50SWQsXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgdGl0bGU6IHN1bW1hcnlBbmROb3Rlc09iamVjdD8uc3VtbWFyeSxcbiAgICAgICAgc3RhcnREYXRlOiBkYXlqcyhtZWV0aW5nVGltZSkudHoodGltZXpvbmUpLmZvcm1hdCgpLFxuICAgICAgICBlbmREYXRlOiBkYXlqcyhtZWV0aW5nVGltZSlcbiAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgLmFkZChwYXJzZUludChkdXJhdGlvbiwgMTApLCAnbScpXG4gICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICBhbGxEYXk6IGZhbHNlLFxuICAgICAgICBub3Rlczogc3VtbWFyeUFuZE5vdGVzT2JqZWN0Py5ub3RlcyxcbiAgICAgICAgdGltZXpvbmUsXG4gICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgcHJpb3JpdHk6IDEsXG4gICAgICAgIGlzRm9sbG93VXA6IGZhbHNlLFxuICAgICAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICAgICAgaXNQb3N0RXZlbnQ6IGZhbHNlLFxuICAgICAgICBtb2RpZmlhYmxlOiBmYWxzZSxcbiAgICAgICAgYW55b25lQ2FuQWRkU2VsZjpcbiAgICAgICAgICBxdWVyeVBhcmFtc09iamVjdD8uYW55b25lQ2FuQWRkU2VsZiA9PT0gJ3RydWUnID8gdHJ1ZSA6IGZhbHNlLFxuICAgICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnM6XG4gICAgICAgICAgcXVlcnlQYXJhbXNPYmplY3Q/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyA9PT0gJ3RydWUnID8gdHJ1ZSA6IGZhbHNlLFxuICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0czpcbiAgICAgICAgICBxdWVyeVBhcmFtc09iamVjdD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMgPT09ICd0cnVlJyA/IHRydWUgOiBmYWxzZSxcbiAgICAgICAgdHJhbnNwYXJlbmN5OiBxdWVyeVBhcmFtc09iamVjdD8udHJhbnNwYXJlbmN5LFxuICAgICAgICB2aXNpYmlsaXR5OiBxdWVyeVBhcmFtc09iamVjdD8udmlzaWJpbGl0eSxcbiAgICAgICAgb3JpZ2luYWxTdGFydERhdGU6IHVuZGVmaW5lZCxcbiAgICAgICAgb3JpZ2luYWxBbGxEYXk6IGZhbHNlLFxuICAgICAgICBzdW1tYXJ5OiBzdW1tYXJ5QW5kTm90ZXNPYmplY3Q/LnN1bW1hcnksXG4gICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgY2FsZW5kYXJJZDogY2FsZW5kYXJJZCB8fCBwcmltYXJ5Q2FsZW5kYXI/LmlkLFxuICAgICAgICBldmVudElkOiB1bmRlZmluZWQsXG4gICAgICAgIGF0dGFjaG1lbnRzOiBxdWVyeVBhcmFtc09iamVjdD8uYXR0YWNobWVudHMsXG4gICAgICAgIHNlbmRVcGRhdGVzOiBxdWVyeVBhcmFtc09iamVjdD8uc2VuZFVwZGF0ZXMsXG4gICAgICAgIGR1cmF0aW9uOiBwYXJzZUludChxdWVyeVBhcmFtc09iamVjdD8uZHVyYXRpb24sIDEwKSxcbiAgICAgIH07XG5cbiAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uaWQsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZW5kRGF0ZSxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5zdGFydERhdGUsXG4gICAgICAgIDAsXG4gICAgICAgIDIsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uc2VuZFVwZGF0ZXMsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAgICAgYXR0ZW5kZWVFbWFpbHM/Lm1hcCgoYSkgPT4gKHsgZW1haWw6IGEgfSkpLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHN1bW1hcnlBbmROb3Rlc09iamVjdD8uc3VtbWFyeSxcbiAgICAgICAgc3VtbWFyeUFuZE5vdGVzT2JqZWN0Py5ub3RlcyxcbiAgICAgICAgdGltZXpvbmUsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lmd1ZXN0c0Nhbk1vZGlmeSxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5vcmlnaW5hbFN0YXJ0RGF0ZSxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZD8ubGVuZ3RoID4gMCA/IGdvb2dsZVJlbWluZGVyIDogdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy50cmFuc3BhcmVuY3ksXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udmlzaWJpbGl0eSxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uYXR0YWNobWVudHMsXG4gICAgICAgICdkZWZhdWx0JyxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWRcbiAgICAgICk7XG5cbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5pZCA9IGdvb2dsZVJlc1ZhbHVlLmlkO1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLmV2ZW50SWQgPSBnb29nbGVSZXNWYWx1ZS5nb29nbGVFdmVudElkO1xuXG4gICAgICAvLyB1cGRhdGUgcmVtaW5kZXJzIGZvciBldmVudCBJZFxuICAgICAgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5tYXAoKHIpID0+ICh7XG4gICAgICAgIC4uLnIsXG4gICAgICAgIGV2ZW50SWQ6IGV2ZW50VG9VcHNlcnRMb2NhbC5pZCxcbiAgICAgIH0pKTtcblxuICAgICAgLy8gdXBkYXRlIGF0dGVuZGVlcyBmb3IgZXZlbnRJZFxuICAgICAgYXR0ZW5kZWVzPy5tYXAoKGEpID0+ICh7IC4uLmEsIGV2ZW50SWQ6IGV2ZW50VG9VcHNlcnRMb2NhbC5pZCB9KSk7XG5cbiAgICAgIC8vIGluc2VydCBldmVudHNcbiAgICAgIGF3YWl0IHVwc2VydEV2ZW50cyhbZXZlbnRUb1Vwc2VydExvY2FsXSk7XG5cbiAgICAgIC8vIGluc2VydCByZW1pbmRlcnNcbiAgICAgIGlmIChyZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQ/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgYXdhaXQgaW5zZXJ0UmVtaW5kZXJzKHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZCk7XG4gICAgICB9XG5cbiAgICAgIGlmIChhdHRlbmRlZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgYXdhaXQgaW5zZXJ0QXR0ZW5kZWVzZm9yRXZlbnQoYXR0ZW5kZWVzKTtcbiAgICAgIH1cbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIGVtYWlsIGNvbnRlbnQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RFdmVudHNGb3JVc2VyR2l2ZW5EYXRlcyA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHNlbmRlclN0YXJ0RGF0ZTogc3RyaW5nLFxuICBzZW5kZXJFbmREYXRlOiBzdHJpbmdcbiAgLy8gc2VuZGVyVGltZXpvbmU6IHN0cmluZyxcbiAgLy8gcmVjZWl2ZXJUaW1lem9uZTogc3RyaW5nLFxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdsaXN0RXZlbnRzRm9yVXNlcic7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBxdWVyeSBsaXN0RXZlbnRzRm9yVXNlcigkdXNlcklkOiB1dWlkISwgJHN0YXJ0RGF0ZTogdGltZXN0YW1wISwgJGVuZERhdGU6IHRpbWVzdGFtcCEpIHtcbiAgICAgICAgICAgICAgICBFdmVudCh3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH0sIGVuZERhdGU6IHtfZ3RlOiAkc3RhcnREYXRlfSwgc3RhcnREYXRlOiB7X2x0ZTogJGVuZERhdGV9LCBkZWxldGVkOiB7X25lcTogdHJ1ZX0sIGFsbERheToge19uZXE6IHRydWV9fSkge1xuICAgICAgICAgICAgICAgICAgICBhbGxEYXlcbiAgICAgICAgICAgICAgICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgICAgICAgICAgICAgICBhdHRhY2htZW50c1xuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZXNPbWl0dGVkXG4gICAgICAgICAgICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICBjYWxlbmRhcklkXG4gICAgICAgICAgICAgICAgICAgIGNvbG9ySWRcbiAgICAgICAgICAgICAgICAgICAgY29uZmVyZW5jZUlkXG4gICAgICAgICAgICAgICAgICAgIGNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgY29weUNhdGVnb3JpZXNcbiAgICAgICAgICAgICAgICAgICAgY29weUR1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgIGNvcHlJc0JyZWFrXG4gICAgICAgICAgICAgICAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIGNvcHlNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIGNvcHlQcmlvcml0eUxldmVsXG4gICAgICAgICAgICAgICAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgY29weVRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRvclxuICAgICAgICAgICAgICAgICAgICBkYWlseVRhc2tMaXN0XG4gICAgICAgICAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb25cbiAgICAgICAgICAgICAgICAgICAgZW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICBlbmRUaW1lVW5zcGVjaWZpZWRcbiAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBldmVudFR5cGVcbiAgICAgICAgICAgICAgICAgICAgZXh0ZW5kZWRQcm9wZXJ0aWVzXG4gICAgICAgICAgICAgICAgICAgIGZvbGxvd1VwRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBmb3JFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuTW9kaWZ5XG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICAgICAgICAgICAgICAgIGhhbmdvdXRMaW5rXG4gICAgICAgICAgICAgICAgICAgIGhhcmREZWFkbGluZVxuICAgICAgICAgICAgICAgICAgICBodG1sTGlua1xuICAgICAgICAgICAgICAgICAgICBpQ2FsVUlEXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGlzQnJlYWtcbiAgICAgICAgICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIGlzRm9sbG93VXBcbiAgICAgICAgICAgICAgICAgICAgaXNNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIGlzTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgaXNQb3N0RXZlbnRcbiAgICAgICAgICAgICAgICAgICAgaXNQcmVFdmVudFxuICAgICAgICAgICAgICAgICAgICBsaW5rc1xuICAgICAgICAgICAgICAgICAgICBsb2NhdGlvblxuICAgICAgICAgICAgICAgICAgICBsb2NrZWRcbiAgICAgICAgICAgICAgICAgICAgbWF4QXR0ZW5kZWVzXG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgICAgICAgICAgICBtZXRob2RcbiAgICAgICAgICAgICAgICAgICAgbW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZVxuICAgICAgICAgICAgICAgICAgICBub3Rlc1xuICAgICAgICAgICAgICAgICAgICBvcmdhbml6ZXJcbiAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxBbGxEYXlcbiAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxTdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxUaW1lem9uZVxuICAgICAgICAgICAgICAgICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgICBwb3NpdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0VGltZVxuICAgICAgICAgICAgICAgICAgICBwb3N0RXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBwcmVFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZERheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2VcbiAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkVGltZVxuICAgICAgICAgICAgICAgICAgICBwcmlvcml0eVxuICAgICAgICAgICAgICAgICAgICBwcml2YXRlQ29weVxuICAgICAgICAgICAgICAgICAgICByZWN1cnJlbmNlXG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VSdWxlXG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmluZ0V2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgc2VuZFVwZGF0ZXNcbiAgICAgICAgICAgICAgICAgICAgc29mdERlYWRsaW5lXG4gICAgICAgICAgICAgICAgICAgIHNvdXJjZVxuICAgICAgICAgICAgICAgICAgICBzdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgc3RhdHVzXG4gICAgICAgICAgICAgICAgICAgIHN1bW1hcnlcbiAgICAgICAgICAgICAgICAgICAgdGFza0lkXG4gICAgICAgICAgICAgICAgICAgIHRhc2tUeXBlXG4gICAgICAgICAgICAgICAgICAgIHRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB0aXRsZVxuICAgICAgICAgICAgICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgICAgICAgICAgICAgdW5saW5rXG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkQ2F0ZWdvcmllc1xuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWREdXJhdGlvblxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRJc0JyZWFrXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgICB2aXNpYmlsaXR5XG4gICAgICAgICAgICAgICAgICAgIHdlZWtseVRhc2tMaXN0XG4gICAgICAgICAgICAgICAgICAgIGJ5V2Vla0RheVxuICAgICAgICAgICAgICAgICAgICBsb2NhbFN5bmNlZFxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRDb2xvclxuICAgICAgICAgICAgICAgICAgICBjb3B5Q29sb3JcbiAgICAgICAgICAgICAgICAgICAgY29weUV4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcbiAgICAvLyBnZXQgZXZlbnRzXG4gICAgLy8gbG9jYWwgZGF0ZVxuICAgIC8vIGNvbnN0IHN0YXJ0RGF0ZUluUmVjZWl2ZXJUaW1lem9uZSA9IGRheWpzKHNlbmRlclN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KHJlY2VpdmVyVGltZXpvbmUsIHRydWUpXG4gICAgLy8gY29uc3QgZW5kRGF0ZUluUmVjZWl2ZXJUaW1lem9uZSA9IGRheWpzKChzZW5kZXJFbmREYXRlLnNsaWNlKDAsIDE5KSkpLnR6KHJlY2VpdmVyVGltZXpvbmUsIHRydWUpXG4gICAgLy8gY29uc3Qgc3RhcnREYXRlSW5TZW5kZXJUaW1lem9uZSA9IGRheWpzKHN0YXJ0RGF0ZUluUmVjZWl2ZXJUaW1lem9uZSkuZm9ybWF0KCkuc2xpY2UoMCwgMTkpXG4gICAgLy8gY29uc3QgZW5kRGF0ZUluU2VuZGVyVGltZXpvbmUgPSBkYXlqcyhlbmREYXRlSW5SZWNlaXZlclRpbWV6b25lKS5mb3JtYXQoKS5zbGljZSgwLCAxOSlcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IEV2ZW50OiBFdmVudFR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgc3RhcnREYXRlOiBzZW5kZXJTdGFydERhdGUsXG4gICAgICAgICAgICBlbmREYXRlOiBzZW5kZXJFbmREYXRlLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBsaXN0RXZlbnRzZm9yVXNlcicpO1xuICAgIHJldHVybiByZXM/LmRhdGE/LkV2ZW50O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyBsaXN0RXZlbnRzRm9yVXNlcicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0VXNlclByZWZlcmVuY2VzID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxVc2VyUHJlZmVyZW5jZVR5cGUgfCBudWxsPiA9PiB7XG4gIHRyeSB7XG4gICAgaWYgKCF1c2VySWQpIHtcbiAgICAgIGNvbnNvbGUubG9nKCd1c2VySWQgaXMgbnVsbCcpO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZ2V0VXNlclByZWZlcmVuY2VzJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICBxdWVyeSBnZXRVc2VyUHJlZmVyZW5jZXMoJHVzZXJJZDogdXVpZCEpIHtcbiAgICAgIFVzZXJfUHJlZmVyZW5jZSh3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH19KSB7XG4gICAgICAgIHN0YXJ0VGltZXNcbiAgICAgICAgZW5kVGltZXNcbiAgICAgICAgYmFja1RvQmFja01lZXRpbmdzXG4gICAgICAgIGNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgY29weUNhdGVnb3JpZXNcbiAgICAgICAgY29weUlzQnJlYWtcbiAgICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgY29weVJlbWluZGVyc1xuICAgICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICBkZWxldGVkXG4gICAgICAgIGZvbGxvd1VwXG4gICAgICAgIGlkXG4gICAgICAgIGlzUHVibGljQ2FsZW5kYXJcbiAgICAgICAgbWF4TnVtYmVyT2ZNZWV0aW5nc1xuICAgICAgICBtYXhXb3JrTG9hZFBlcmNlbnRcbiAgICAgICAgcHVibGljQ2FsZW5kYXJDYXRlZ29yaWVzXG4gICAgICAgIHJlbWluZGVyc1xuICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgdXNlcklkXG4gICAgICAgIG1pbk51bWJlck9mQnJlYWtzXG4gICAgICAgIGJyZWFrQ29sb3JcbiAgICAgICAgYnJlYWtMZW5ndGhcbiAgICAgICAgY29weUNvbG9yXG4gICAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICAgIG9uQm9hcmRlZFxuICAgICAgfVxuICAgIH0gICAgXG4gIGA7XG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgVXNlcl9QcmVmZXJlbmNlOiBVc2VyUHJlZmVyZW5jZVR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICByZXR1cm4gcmVzPy5kYXRhPy5Vc2VyX1ByZWZlcmVuY2U/LlswXTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgZ2V0VXNlclByZWZlcmVuY2VzJyk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cbn07XG5leHBvcnQgY29uc3QgZ2VuZXJhdGVBdmFpbGFibGVTbG90c0ZvckRhdGUgPSAoXG4gIHNsb3REdXJhdGlvbjogbnVtYmVyLFxuICBzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmU6IHN0cmluZyxcbiAgc2VuZGVyUHJlZmVyZW5jZXM6IFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgcmVjZWl2ZXJUaW1lem9uZTogc3RyaW5nLFxuICBzZW5kZXJUaW1lem9uZTogc3RyaW5nLFxuICBub3RBdmFpbGFibGVTbG90c0luRXZlbnRUaW1lem9uZT86IE5vdEF2YWlsYWJsZVNsb3RUeXBlW10sXG4gIGlzRmlyc3REYXk/OiBib29sZWFuLFxuICBpc0xhc3REYXk/OiBib29sZWFuLFxuICBzZW5kZXJFbmREYXRlSW5SZWNlaXZlclRpbWV6b25lPzogc3RyaW5nXG4pID0+IHtcbiAgY29uc29sZS5sb2coc2VuZGVyVGltZXpvbmUsICcgc2VuZGVyVGltZXpvbmUnKTtcbiAgY29uc29sZS5sb2cocmVjZWl2ZXJUaW1lem9uZSwgJyByZWNlaXZlclRpbWV6b25lJyk7XG5cbiAgaWYgKGlzRmlyc3REYXkgJiYgaXNMYXN0RGF5ICYmIHNlbmRlckVuZERhdGVJblJlY2VpdmVyVGltZXpvbmUpIHtcbiAgICBjb25zdCBlbmRUaW1lc0J5U2VuZGVyID0gc2VuZGVyUHJlZmVyZW5jZXMuZW5kVGltZXM7XG4gICAgY29uc3QgZGF5T2ZXZWVrSW50QXNSZWNlaXZlciA9IGdldElTT0RheShcbiAgICAgIGRheWpzKHNlbmRlclN0YXJ0RGF0ZUluUmVjZWl2ZXJUaW1lem9uZT8uc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoocmVjZWl2ZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnRvRGF0ZSgpXG4gICAgKTtcblxuICAgIGNvbnN0IGRheU9mTW9udGhBc1JlY2VpdmVyID0gZGF5anMoXG4gICAgICBzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmU/LnNsaWNlKDAsIDE5KVxuICAgIClcbiAgICAgIC50eihyZWNlaXZlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLmRhdGUoKTtcbiAgICBsZXQgc3RhcnRIb3VyQXNSZWNlaXZlciA9IGRheWpzKFxuICAgICAgc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lPy5zbGljZSgwLCAxOSlcbiAgICApXG4gICAgICAudHoocmVjZWl2ZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5ob3VyKCk7XG5cbiAgICBjb25zdCBmbG9vcmVkVmFsdWUgPSBNYXRoLmZsb29yKDYwIC8gc2xvdER1cmF0aW9uKTtcblxuICAgIGxldCBtaW51dGVWYWx1ZUFzUmVjZWl2ZXIgPSAwO1xuICAgIGlmIChcbiAgICAgIGRheWpzKHNlbmRlclN0YXJ0RGF0ZUluUmVjZWl2ZXJUaW1lem9uZSkudHoocmVjZWl2ZXJUaW1lem9uZSkubWludXRlKCkgIT09XG4gICAgICAwXG4gICAgKSB7XG4gICAgICBmb3IgKGxldCBpID0gMDsgaSA8IGZsb29yZWRWYWx1ZTsgaSsrKSB7XG4gICAgICAgIGNvbnN0IGVuZE1pbnV0ZXMgPSAoaSArIDEpICogc2xvdER1cmF0aW9uO1xuICAgICAgICBjb25zdCBzdGFydE1pbnV0ZXMgPSBpICogc2xvdER1cmF0aW9uO1xuICAgICAgICBpZiAoXG4gICAgICAgICAgZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZXMpLFxuICAgICAgICAgICAgICBkYXlqcyhzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGVzKSxcbiAgICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAgICdbKSdcbiAgICAgICAgICAgIClcbiAgICAgICAgKSB7XG4gICAgICAgICAgbWludXRlVmFsdWVBc1JlY2VpdmVyID0gZW5kTWludXRlcztcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cblxuICAgIGlmIChcbiAgICAgIGRheWpzKHNlbmRlclN0YXJ0RGF0ZUluUmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAubWludXRlKGZsb29yZWRWYWx1ZSAqIHNsb3REdXJhdGlvbiksXG4gICAgICAgICAgZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAubWludXRlKDU5KSxcbiAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAnWyknXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIHN0YXJ0SG91ckFzUmVjZWl2ZXIgKz0gMTtcbiAgICAgIG1pbnV0ZVZhbHVlQXNSZWNlaXZlciA9IDA7XG4gICAgfVxuXG4gICAgY29uc3Qgc3RhcnRNaW51dGVBc1JlY2VpdmVyID0gbWludXRlVmFsdWVBc1JlY2VpdmVyO1xuXG4gICAgY29uc3QgZW5kSG91cldvcmtCeVNlbmRlciA9XG4gICAgICBlbmRUaW1lc0J5U2VuZGVyPy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50QXNSZWNlaXZlcik/LmhvdXIgPz9cbiAgICAgIDIwO1xuICAgIGNvbnN0IGVuZE1pbnV0ZVdvcmtCeVNlbmRlciA9XG4gICAgICBlbmRUaW1lc0J5U2VuZGVyPy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50QXNSZWNlaXZlcilcbiAgICAgICAgPy5taW51dGVzID8/IDA7XG4gICAgY29uc3QgZW5kSG91ckFzUmVjZWl2ZXIgPSBkYXlqcyhzZW5kZXJFbmREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IGVuZE1pbnV0ZUFzUmVjZWl2ZXIgPSBkYXlqcyhzZW5kZXJFbmREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAubWludXRlKCk7XG5cbiAgICAvLyB2YWxpZGF0ZSB2YWx1ZXMgYmVmb3JlIGNhbGN1bGF0aW5nXG4gICAgY29uc3Qgc3RhcnRUaW1lcyA9IHNlbmRlclByZWZlcmVuY2VzLnN0YXJ0VGltZXM7XG4gICAgY29uc3Qgd29ya1N0YXJ0SG91ckJ5U2VuZGVyID1cbiAgICAgIHN0YXJ0VGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRBc1JlY2VpdmVyKT8uaG91ciB8fCA4O1xuICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZUJ5U2VuZGVyID1cbiAgICAgIHN0YXJ0VGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRBc1JlY2VpdmVyKT8ubWludXRlcyB8fCAwO1xuXG4gICAgaWYgKFxuICAgICAgZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAudHooc2VuZGVyVGltZXpvbmUpXG4gICAgICAgIC5pc0FmdGVyKFxuICAgICAgICAgIGRheWpzKHNlbmRlclN0YXJ0RGF0ZUluUmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC50eihzZW5kZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC5ob3VyKGVuZEhvdXJXb3JrQnlTZW5kZXIpXG4gICAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZVdvcmtCeVNlbmRlcilcbiAgICAgICAgKVxuICAgICkge1xuICAgICAgLy8gcmV0dXJuIGVtcHR5IGFzIG91dHNpZGUgb2Ygd29yayB0aW1lXG4gICAgICByZXR1cm4gW107XG4gICAgfVxuXG4gICAgLy8gY2hhbmdlIHRvIHdvcmsgc3RhcnQgdGltZSBhcyBzZW5kZXIgc3RhcnQgdGltZSBiZWZvcmUgd29yayBzdGFydCB0aW1lXG4gICAgaWYgKFxuICAgICAgZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAudHooc2VuZGVyVGltZXpvbmUpXG4gICAgICAgIC5pc0JlZm9yZShcbiAgICAgICAgICBkYXlqcyhzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAudHooc2VuZGVyVGltZXpvbmUpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlTZW5kZXIpXG4gICAgICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZUJ5U2VuZGVyKVxuICAgICAgICApXG4gICAgKSB7XG4gICAgICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgICBob3Vyczogd29ya1N0YXJ0SG91ckJ5U2VuZGVyLFxuICAgICAgICBtaW51dGVzOiB3b3JrU3RhcnRNaW51dGVCeVNlbmRlcixcbiAgICAgIH0pO1xuICAgICAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICAgIGhvdXJzOiBlbmRIb3VyQXNSZWNlaXZlcixcbiAgICAgICAgbWludXRlczogZW5kTWludXRlQXNSZWNlaXZlcixcbiAgICAgIH0pO1xuICAgICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgICAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcblxuICAgICAgY29uc3QgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmU6IEF2YWlsYWJsZVNsb3RUeXBlW10gPSBbXTtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmUsXG4gICAgICAgIGVuZFRpbWVzQnlTZW5kZXIsXG4gICAgICAgIGRheU9mV2Vla0ludEFzUmVjZWl2ZXIsXG4gICAgICAgIGRheU9mTW9udGhBc1JlY2VpdmVyLFxuICAgICAgICBzdGFydEhvdXJBc1JlY2VpdmVyLFxuICAgICAgICBzdGFydE1pbnV0ZUFzUmVjZWl2ZXIsXG4gICAgICAgIGVuZEhvdXJBc1JlY2VpdmVyLFxuICAgICAgICBlbmRNaW51dGVBc1JlY2VpdmVyLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgYHN0YXJ0RGF0ZSwgZW5kVGltZXMsIGRheU9mV2Vla0ludEJ5VXNlciwgZGF5T2ZNb250aCwgc3RhcnRIb3VyLCBzdGFydE1pbnV0ZSwgZW5kSG91ciwgZW5kTWludXRlIHRvdGFsTWludXRlcywgdGltZXpvbmUsIGluc2lkZSBmaXJzdERheSBpbnNpZGUgZ2VuZXJhdGVUaW1lc2xvdHNgXG4gICAgICApO1xuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gc2xvdER1cmF0aW9uKSB7XG4gICAgICAgIGlmIChpID4gdG90YWxNaW51dGVzKSB7XG4gICAgICAgICAgY29udGludWU7XG4gICAgICAgIH1cblxuICAgICAgICBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZS5wdXNoKHtcbiAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgIHN0YXJ0RGF0ZTogZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHNlbmRlclRpbWV6b25lKVxuICAgICAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91ckJ5U2VuZGVyKVxuICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeVNlbmRlcilcbiAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgICBlbmREYXRlOiBkYXlqcyhzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAudHooc2VuZGVyVGltZXpvbmUpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlTZW5kZXIpXG4gICAgICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZUJ5U2VuZGVyKVxuICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAuYWRkKGkgKyBzbG90RHVyYXRpb24sICdtaW51dGUnKVxuICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICB9KTtcbiAgICAgIH1cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZSxcbiAgICAgICAgJyB0aW1lU2xvdHMgaW5zaWRlIGdlbmVyYXRlVGltZVNsb3RzIGZvciBmaXJzdCBkYXkgd2hlcmUgc3RhcnREYXRlIGlzIGJlZm9yZSB3b3JrIHN0YXJ0IHRpbWUnXG4gICAgICApO1xuXG4gICAgICAvLyBmaWx0ZXIgb3V0IHVuYXZhaWxhYmxlIHRpbWVzXG4gICAgICBjb25zdCBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lID1cbiAgICAgICAgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUuZmlsdGVyKChhKSA9PiB7XG4gICAgICAgICAgY29uc3QgZm91bmRJbmRleCA9IG5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lPy5maW5kSW5kZXgoXG4gICAgICAgICAgICAobmEpID0+IHtcbiAgICAgICAgICAgICAgY29uc3QgcGFydEEgPSBkYXlqcyhhLmVuZERhdGUpXG4gICAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpXG4gICAgICAgICAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgICAgIC5hZGQoMSwgJ20nKSxcbiAgICAgICAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpXG4gICAgICAgICAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgICAgIC5zdWJ0cmFjdCgxLCAnbScpLFxuICAgICAgICAgICAgICAgICAgJ20nLFxuICAgICAgICAgICAgICAgICAgJ1tdJ1xuICAgICAgICAgICAgICAgICk7XG5cbiAgICAgICAgICAgICAgY29uc3QgcGFydEIgPSBkYXlqcyhhLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgICAudHoocmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAgICAgLmFkZCgxLCAnbScpLFxuICAgICAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAgICAgLnN1YnRyYWN0KDEsICdtJyksXG4gICAgICAgICAgICAgICAgICAnbScsXG4gICAgICAgICAgICAgICAgICAnW10nXG4gICAgICAgICAgICAgICAgKTtcblxuICAgICAgICAgICAgICBjb25zdCBwYXJ0QyA9XG4gICAgICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKVxuICAgICAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgPT09XG4gICAgICAgICAgICAgICAgICBkYXlqcyhhLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpICYmXG4gICAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpID09PVxuICAgICAgICAgICAgICAgICAgZGF5anMoYS5lbmREYXRlKVxuICAgICAgICAgICAgICAgICAgICAudHoocmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJyk7XG5cbiAgICAgICAgICAgICAgY29uc3QgaXNOb3RBdmFpbGFibGUgPSBwYXJ0QSB8fCBwYXJ0QiB8fCBwYXJ0QztcblxuICAgICAgICAgICAgICAvLyBjb25zb2xlLmxvZyhhLCBuYSwgJyBhLCBuYScpXG4gICAgICAgICAgICAgIHJldHVybiBpc05vdEF2YWlsYWJsZTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICApO1xuXG4gICAgICAgICAgY29uc29sZS5sb2coZm91bmRJbmRleCwgJyBmb3VuZEluZGV4Jyk7XG5cbiAgICAgICAgICBpZiAoZm91bmRJbmRleCAhPT0gdW5kZWZpbmVkICYmIGZvdW5kSW5kZXggPiAtMSkge1xuICAgICAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIHJldHVybiB0cnVlO1xuICAgICAgICB9KTtcblxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUsXG4gICAgICAgICcgZmlsdGVyZWRBdmFpbGFibGVTbG90cydcbiAgICAgICk7XG5cbiAgICAgIHJldHVybiBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lO1xuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICBob3Vyczogc3RhcnRIb3VyQXNSZWNlaXZlcixcbiAgICAgIG1pbnV0ZXM6IHN0YXJ0TWludXRlQXNSZWNlaXZlcixcbiAgICB9KTtcbiAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgIGhvdXJzOiBlbmRIb3VyQXNSZWNlaXZlcixcbiAgICAgIG1pbnV0ZXM6IGVuZE1pbnV0ZUFzUmVjZWl2ZXIsXG4gICAgfSk7XG4gICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG4gICAgY29uc29sZS5sb2codG90YWxNaW51dGVzLCAnIHRvdGFsTWludXRlcyBpbnNpZGUgZmlyc3QgYW5kIGxhc3Qgc2FtZSBkYXknKTtcbiAgICBjb25zdCBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZTogQXZhaWxhYmxlU2xvdFR5cGVbXSA9IFtdO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lLFxuICAgICAgZW5kVGltZXNCeVNlbmRlcixcbiAgICAgIGRheU9mV2Vla0ludEFzUmVjZWl2ZXIsXG4gICAgICBlbmRIb3VyV29ya0J5U2VuZGVyLFxuICAgICAgZW5kTWludXRlV29ya0J5U2VuZGVyLFxuICAgICAgcmVjZWl2ZXJUaW1lem9uZSxcbiAgICAgIGBzdGFydERhdGUsIGVuZFRpbWVzLCBkYXlPZldlZWtJbnQsIGRheU9mTW9udGgsIHN0YXJ0SG91ciwgc3RhcnRNaW51dGUsIGVuZEhvdXIsIGVuZE1pbnV0ZSB0b3RhbE1pbnV0ZXMsIHRpbWV6b25lLCBpbnNpZGUgZmlyc3QgJiBsYXN0IERheSBpbnNpZGUgZ2VuZXJhdGVUaW1lc2xvdHNgXG4gICAgKTtcbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsTWludXRlczsgaSArPSBzbG90RHVyYXRpb24pIHtcbiAgICAgIGlmIChpID4gdG90YWxNaW51dGVzKSB7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfVxuICAgICAgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUucHVzaCh7XG4gICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgIHN0YXJ0RGF0ZTogZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ckFzUmVjZWl2ZXIpXG4gICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUFzUmVjZWl2ZXIpXG4gICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICBlbmREYXRlOiBkYXlqcyhzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQXNSZWNlaXZlcilcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQXNSZWNlaXZlcilcbiAgICAgICAgICAuYWRkKGkgKyBzbG90RHVyYXRpb24sICdtaW51dGUnKVxuICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICB9KTtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lLFxuICAgICAgJyBhdmFpbGFibGVTbG90cyBpbnNpZGUgZmlyc3QgJiBsYXN0IHNhbWUgZGF5J1xuICAgICk7XG4gICAgY29uc3QgZmlsdGVyZWRBdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZSA9XG4gICAgICBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZS5maWx0ZXIoKGEpID0+IHtcbiAgICAgICAgY29uc3QgZm91bmRJbmRleCA9IG5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lPy5maW5kSW5kZXgoKG5hKSA9PiB7XG4gICAgICAgICAgY29uc3QgcGFydEEgPSBkYXlqcyhhLmVuZERhdGUpXG4gICAgICAgICAgICAudHoocmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSkudHoocmVjZWl2ZXJUaW1lem9uZSkuc2Vjb25kKDApLmFkZCgxLCAnbScpLFxuICAgICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKS50eihyZWNlaXZlclRpbWV6b25lKS5zZWNvbmQoMCkuc3VidHJhY3QoMSwgJ20nKSxcbiAgICAgICAgICAgICAgJ20nLFxuICAgICAgICAgICAgICAnW10nXG4gICAgICAgICAgICApO1xuXG4gICAgICAgICAgY29uc3QgcGFydEIgPSBkYXlqcyhhLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKS50eihyZWNlaXZlclRpbWV6b25lKS5zZWNvbmQoMCkuYWRkKDEsICdtJyksXG4gICAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpLnR6KHJlY2VpdmVyVGltZXpvbmUpLnNlY29uZCgwKS5zdWJ0cmFjdCgxLCAnbScpLFxuICAgICAgICAgICAgICAnbScsXG4gICAgICAgICAgICAgICdbXSdcbiAgICAgICAgICAgICk7XG5cbiAgICAgICAgICBjb25zdCBwYXJ0QyA9XG4gICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpXG4gICAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSA9PT1cbiAgICAgICAgICAgICAgZGF5anMoYS5zdGFydERhdGUpXG4gICAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSAmJlxuICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpID09PVxuICAgICAgICAgICAgICBkYXlqcyhhLmVuZERhdGUpXG4gICAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKTtcblxuICAgICAgICAgIGNvbnN0IGlzTm90QXZhaWxhYmxlID0gcGFydEEgfHwgcGFydEIgfHwgcGFydEM7XG5cbiAgICAgICAgICAvLyBjb25zb2xlLmxvZyhhLCBuYSwgJyBhLCBuYScpXG5cbiAgICAgICAgICByZXR1cm4gaXNOb3RBdmFpbGFibGU7XG4gICAgICAgIH0pO1xuXG4gICAgICAgIGNvbnNvbGUubG9nKGZvdW5kSW5kZXgsICcgZm91bmRJbmRleCcpO1xuXG4gICAgICAgIGlmIChmb3VuZEluZGV4ICE9PSB1bmRlZmluZWQgJiYgZm91bmRJbmRleCA+IC0xKSB7XG4gICAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgICAgICB9XG5cbiAgICAgICAgcmV0dXJuIHRydWU7XG4gICAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZmlsdGVyZWRBdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZSxcbiAgICAgICcgZmlsdGVyZWRBdmFpbGFibGVTbG90cydcbiAgICApO1xuICAgIHJldHVybiBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lO1xuICB9XG5cbiAgaWYgKGlzRmlyc3REYXkpIHtcbiAgICAvLyBmaXJzdGRheSBjYW4gYmUgc3RhcnRlZCBvdXRzaWRlIG9mIHdvcmsgdGltZVxuICAgIC8vIGlmIGZpcnN0RGF5IHN0YXJ0IGlzIGFmdGVyIGVuZCB0aW1lIC0tIHJldHVybiBbXVxuICAgIGNvbnN0IGVuZFRpbWVzQnlTZW5kZXIgPSBzZW5kZXJQcmVmZXJlbmNlcy5lbmRUaW1lcztcbiAgICBjb25zdCBkYXlPZldlZWtJbnRBc1JlY2VpdmVyID0gZ2V0SVNPRGF5KFxuICAgICAgZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKS50eihyZWNlaXZlclRpbWV6b25lKS50b0RhdGUoKVxuICAgICk7XG5cbiAgICAvLyBtb250aCBpcyB6ZXJvLWluZGV4ZWRcbiAgICAvLyBjb25zdCBtb250aCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnR6KHVzZXJUaW1lem9uZSkubW9udGgoKVxuICAgIGNvbnN0IGRheU9mTW9udGhBc1JlY2VpdmVyID0gZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAuZGF0ZSgpO1xuICAgIGxldCBzdGFydEhvdXJBc1JlY2VpdmVyID0gZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHN0YXJ0SG91ckJ5U2VuZGVyID0gZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgLnR6KHNlbmRlclRpbWV6b25lKVxuICAgICAgLmhvdXIoKTtcbiAgICBjb25zdCBzdGFydE1pbnV0ZUJ5U2VuZGVyID0gZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgLnR6KHNlbmRlclRpbWV6b25lKVxuICAgICAgLm1pbnV0ZSgpO1xuICAgIC8vIGNyZWF0ZSBzbG90IHNpemVzXG4gICAgY29uc3QgZmxvb3JlZFZhbHVlID0gTWF0aC5mbG9vcig2MCAvIHNsb3REdXJhdGlvbik7XG5cbiAgICBsZXQgbWludXRlVmFsdWVBc1JlY2VpdmVyID0gMDtcbiAgICBpZiAoXG4gICAgICBkYXlqcyhzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmUpLnR6KHJlY2VpdmVyVGltZXpvbmUpLm1pbnV0ZSgpICE9PVxuICAgICAgMFxuICAgICkge1xuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCBmbG9vcmVkVmFsdWU7IGkrKykge1xuICAgICAgICBjb25zdCBlbmRNaW51dGVzID0gKGkgKyAxKSAqIHNsb3REdXJhdGlvbjtcbiAgICAgICAgY29uc3Qgc3RhcnRNaW51dGVzID0gaSAqIHNsb3REdXJhdGlvbjtcbiAgICAgICAgaWYgKFxuICAgICAgICAgIGRheWpzKHNlbmRlclN0YXJ0RGF0ZUluUmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVzKSxcbiAgICAgICAgICAgICAgZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoZW5kTWludXRlcyksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgICkge1xuICAgICAgICAgIG1pbnV0ZVZhbHVlQXNSZWNlaXZlciA9IGVuZE1pbnV0ZXM7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICBkYXlqcyhzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgIGRheWpzKHNlbmRlclN0YXJ0RGF0ZUluUmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgLm1pbnV0ZShmbG9vcmVkVmFsdWUgKiBzbG90RHVyYXRpb24pLFxuICAgICAgICAgIGRheWpzKHNlbmRlclN0YXJ0RGF0ZUluUmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgLm1pbnV0ZSg1OSksXG4gICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgJ1spJ1xuICAgICAgICApXG4gICAgKSB7XG4gICAgICBzdGFydEhvdXJBc1JlY2VpdmVyICs9IDE7XG4gICAgICBtaW51dGVWYWx1ZUFzUmVjZWl2ZXIgPSAwO1xuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0TWludXRlQXNSZWNlaXZlciA9IG1pbnV0ZVZhbHVlQXNSZWNlaXZlcjtcblxuICAgIC8vIGNvbnZlcnQgdG8gdXNlciB0aW1lem9uZSBzbyBldmVyeXRoaW5nIGlzIGxpbmtlZCB0byB1c2VyIHRpbWV6b25lXG5cbiAgICBjb25zdCBlbmRIb3VyQnlTZW5kZXIgPVxuICAgICAgZW5kVGltZXNCeVNlbmRlcj8uZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludEFzUmVjZWl2ZXIpPy5ob3VyID8/XG4gICAgICAyMDtcbiAgICBjb25zdCBlbmRNaW51dGVCeVNlbmRlciA9XG4gICAgICBlbmRUaW1lc0J5U2VuZGVyPy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50QXNSZWNlaXZlcilcbiAgICAgICAgPy5taW51dGVzID8/IDA7XG5cbiAgICAvLyB2YWxpZGF0ZSB2YWx1ZXMgYmVmb3JlIGNhbGN1bGF0aW5nXG4gICAgY29uc3Qgc3RhcnRUaW1lcyA9IHNlbmRlclByZWZlcmVuY2VzLnN0YXJ0VGltZXM7XG4gICAgY29uc3Qgd29ya1N0YXJ0SG91ckJ5U2VuZGVyID1cbiAgICAgIHN0YXJ0VGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRBc1JlY2VpdmVyKT8uaG91ciB8fCA4O1xuICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZUJ5U2VuZGVyID1cbiAgICAgIHN0YXJ0VGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRBc1JlY2VpdmVyKT8ubWludXRlcyB8fCAwO1xuXG4gICAgaWYgKFxuICAgICAgZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAudHooc2VuZGVyVGltZXpvbmUpXG4gICAgICAgIC5pc0FmdGVyKFxuICAgICAgICAgIGRheWpzKHNlbmRlclN0YXJ0RGF0ZUluUmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC50eihzZW5kZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC5ob3VyKGVuZEhvdXJCeVNlbmRlcilcbiAgICAgICAgICAgIC5taW51dGUoZW5kTWludXRlQnlTZW5kZXIpXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIC8vIHJldHVybiBlbXB0eSBhcyBvdXRzaWRlIG9mIHdvcmsgdGltZVxuICAgICAgcmV0dXJuIFtdO1xuICAgIH1cblxuICAgIC8vIGNoYW5nZSB0byB3b3JrIHN0YXJ0IHRpbWUgYXMgaG9zdCBzdGFydCB0aW1lIGJlZm9yZSB3b3JrIHN0YXJ0IHRpbWVcbiAgICBpZiAoXG4gICAgICBkYXlqcyhzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgIC50eihzZW5kZXJUaW1lem9uZSlcbiAgICAgICAgLmlzQmVmb3JlKFxuICAgICAgICAgIGRheWpzKHNlbmRlclN0YXJ0RGF0ZUluUmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC50eihzZW5kZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXJCeVNlbmRlcilcbiAgICAgICAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlQnlTZW5kZXIpXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICAgIGhvdXJzOiB3b3JrU3RhcnRIb3VyQnlTZW5kZXIsXG4gICAgICAgIG1pbnV0ZXM6IHdvcmtTdGFydE1pbnV0ZUJ5U2VuZGVyLFxuICAgICAgfSk7XG4gICAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgICAgaG91cnM6IGVuZEhvdXJCeVNlbmRlcixcbiAgICAgICAgbWludXRlczogZW5kTWludXRlQnlTZW5kZXIsXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgICAgIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG5cbiAgICAgIGNvbnN0IGF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lOiBBdmFpbGFibGVTbG90VHlwZVtdID0gW107XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lLFxuICAgICAgICBlbmRUaW1lc0J5U2VuZGVyLFxuICAgICAgICBkYXlPZldlZWtJbnRBc1JlY2VpdmVyLFxuICAgICAgICBkYXlPZk1vbnRoQXNSZWNlaXZlcixcbiAgICAgICAgc3RhcnRIb3VyQXNSZWNlaXZlcixcbiAgICAgICAgc3RhcnRNaW51dGVBc1JlY2VpdmVyLFxuICAgICAgICBlbmRIb3VyQnlTZW5kZXIsXG4gICAgICAgIGVuZE1pbnV0ZUJ5U2VuZGVyLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgYHN0YXJ0RGF0ZSwgZW5kVGltZXMsIGRheU9mV2Vla0ludEJ5VXNlciwgZGF5T2ZNb250aCwgc3RhcnRIb3VyLCBzdGFydE1pbnV0ZSwgZW5kSG91ciwgZW5kTWludXRlIHRvdGFsTWludXRlcywgdGltZXpvbmUsIGluc2lkZSBmaXJzdERheSBpbnNpZGUgZ2VuZXJhdGVUaW1lc2xvdHNgXG4gICAgICApO1xuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gc2xvdER1cmF0aW9uKSB7XG4gICAgICAgIGlmIChpID4gdG90YWxNaW51dGVzKSB7XG4gICAgICAgICAgY29udGludWU7XG4gICAgICAgIH1cblxuICAgICAgICBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZS5wdXNoKHtcbiAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgIHN0YXJ0RGF0ZTogZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHNlbmRlclRpbWV6b25lKVxuICAgICAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91ckJ5U2VuZGVyKVxuICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeVNlbmRlcilcbiAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgICBlbmREYXRlOiBkYXlqcyhzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAudHooc2VuZGVyVGltZXpvbmUpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlTZW5kZXIpXG4gICAgICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZUJ5U2VuZGVyKVxuICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAuYWRkKGkgKyBzbG90RHVyYXRpb24sICdtaW51dGUnKVxuICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICB9KTtcbiAgICAgIH1cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZSxcbiAgICAgICAgJyB0aW1lU2xvdHMgaW5zaWRlIGdlbmVyYXRlVGltZVNsb3RzIGZvciBmaXJzdCBkYXkgd2hlcmUgc3RhcnREYXRlIGlzIGJlZm9yZSB3b3JrIHN0YXJ0IHRpbWUnXG4gICAgICApO1xuXG4gICAgICAvLyBmaWx0ZXIgb3V0IHVuYXZhaWxhYmxlIHRpbWVzXG4gICAgICBjb25zdCBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lID1cbiAgICAgICAgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUuZmlsdGVyKChhKSA9PiB7XG4gICAgICAgICAgY29uc3QgZm91bmRJbmRleCA9IG5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lPy5maW5kSW5kZXgoXG4gICAgICAgICAgICAobmEpID0+IHtcbiAgICAgICAgICAgICAgY29uc3QgcGFydEEgPSBkYXlqcyhhLmVuZERhdGUpXG4gICAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpXG4gICAgICAgICAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgICAgIC5hZGQoMSwgJ20nKSxcbiAgICAgICAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpXG4gICAgICAgICAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgICAgIC5zdWJ0cmFjdCgxLCAnbScpLFxuICAgICAgICAgICAgICAgICAgJ20nLFxuICAgICAgICAgICAgICAgICAgJ1tdJ1xuICAgICAgICAgICAgICAgICk7XG5cbiAgICAgICAgICAgICAgY29uc3QgcGFydEIgPSBkYXlqcyhhLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgICAudHoocmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAgICAgLmFkZCgxLCAnbScpLFxuICAgICAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAgICAgLnN1YnRyYWN0KDEsICdtJyksXG4gICAgICAgICAgICAgICAgICAnbScsXG4gICAgICAgICAgICAgICAgICAnW10nXG4gICAgICAgICAgICAgICAgKTtcblxuICAgICAgICAgICAgICBjb25zdCBwYXJ0QyA9XG4gICAgICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKVxuICAgICAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgPT09XG4gICAgICAgICAgICAgICAgICBkYXlqcyhhLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpICYmXG4gICAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpID09PVxuICAgICAgICAgICAgICAgICAgZGF5anMoYS5lbmREYXRlKVxuICAgICAgICAgICAgICAgICAgICAudHoocmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJyk7XG5cbiAgICAgICAgICAgICAgY29uc3QgaXNOb3RBdmFpbGFibGUgPSBwYXJ0QSB8fCBwYXJ0QiB8fCBwYXJ0QztcblxuICAgICAgICAgICAgICAvLyBjb25zb2xlLmxvZyhhLCBuYSwgJyBhLCBuYScpXG4gICAgICAgICAgICAgIHJldHVybiBpc05vdEF2YWlsYWJsZTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICApO1xuXG4gICAgICAgICAgY29uc29sZS5sb2coZm91bmRJbmRleCwgJyBmb3VuZEluZGV4Jyk7XG5cbiAgICAgICAgICBpZiAoZm91bmRJbmRleCAhPT0gdW5kZWZpbmVkICYmIGZvdW5kSW5kZXggPiAtMSkge1xuICAgICAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIHJldHVybiB0cnVlO1xuICAgICAgICB9KTtcblxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUsXG4gICAgICAgICcgZmlsdGVyZWRBdmFpbGFibGVTbG90cydcbiAgICAgICk7XG5cbiAgICAgIHJldHVybiBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lO1xuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgICBob3Vyczogc3RhcnRIb3VyQnlTZW5kZXIsXG4gICAgICBtaW51dGVzOiBzdGFydE1pbnV0ZUJ5U2VuZGVyLFxuICAgIH0pO1xuICAgIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgaG91cnM6IGVuZEhvdXJCeVNlbmRlcixcbiAgICAgIG1pbnV0ZXM6IGVuZE1pbnV0ZUJ5U2VuZGVyLFxuICAgIH0pO1xuICAgIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgICBjb25zdCB0b3RhbE1pbnV0ZXMgPSB0b3RhbER1cmF0aW9uLmFzTWludXRlcygpO1xuICAgIGNvbnN0IGF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lOiBBdmFpbGFibGVTbG90VHlwZVtdID0gW107XG4gICAgY29uc29sZS5sb2coXG4gICAgICBzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmUsXG4gICAgICBlbmRUaW1lc0J5U2VuZGVyLFxuICAgICAgZGF5T2ZXZWVrSW50QXNSZWNlaXZlcixcbiAgICAgIGVuZEhvdXJCeVNlbmRlcixcbiAgICAgIGVuZE1pbnV0ZUJ5U2VuZGVyLFxuICAgICAgcmVjZWl2ZXJUaW1lem9uZSxcbiAgICAgIGBzdGFydERhdGUsIGVuZFRpbWVzLCBkYXlPZldlZWtJbnQsIGRheU9mTW9udGgsIHN0YXJ0SG91ciwgc3RhcnRNaW51dGUsIGVuZEhvdXIsIGVuZE1pbnV0ZSB0b3RhbE1pbnV0ZXMsIHRpbWV6b25lLCBpbnNpZGUgZmlyc3REYXkgaW5zaWRlIGdlbmVyYXRlVGltZXNsb3RzYFxuICAgICk7XG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gc2xvdER1cmF0aW9uKSB7XG4gICAgICBpZiAoaSA+IHRvdGFsTWludXRlcykge1xuICAgICAgICBjb250aW51ZTtcbiAgICAgIH1cbiAgICAgIGF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lLnB1c2goe1xuICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICBzdGFydERhdGU6IGRheWpzKHNlbmRlclN0YXJ0RGF0ZUluUmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAudHoocmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAuaG91cihzdGFydEhvdXJBc1JlY2VpdmVyKVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVBc1JlY2VpdmVyKVxuICAgICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgZW5kRGF0ZTogZGF5anMoc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ckFzUmVjZWl2ZXIpXG4gICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUFzUmVjZWl2ZXIpXG4gICAgICAgICAgLmFkZChpICsgc2xvdER1cmF0aW9uLCAnbWludXRlJylcbiAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgfSk7XG4gICAgfVxuICAgIGNvbnN0IGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUgPVxuICAgICAgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUuZmlsdGVyKChhKSA9PiB7XG4gICAgICAgIGNvbnN0IGZvdW5kSW5kZXggPSBub3RBdmFpbGFibGVTbG90c0luRXZlbnRUaW1lem9uZT8uZmluZEluZGV4KChuYSkgPT4ge1xuICAgICAgICAgIGNvbnN0IHBhcnRBID0gZGF5anMoYS5lbmREYXRlKVxuICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpLnR6KHJlY2VpdmVyVGltZXpvbmUpLnNlY29uZCgwKS5hZGQoMSwgJ20nKSxcbiAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSkudHoocmVjZWl2ZXJUaW1lem9uZSkuc2Vjb25kKDApLnN1YnRyYWN0KDEsICdtJyksXG4gICAgICAgICAgICAgICdtJyxcbiAgICAgICAgICAgICAgJ1tdJ1xuICAgICAgICAgICAgKTtcblxuICAgICAgICAgIGNvbnN0IHBhcnRCID0gZGF5anMoYS5zdGFydERhdGUpXG4gICAgICAgICAgICAudHoocmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSkudHoocmVjZWl2ZXJUaW1lem9uZSkuc2Vjb25kKDApLmFkZCgxLCAnbScpLFxuICAgICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKS50eihyZWNlaXZlclRpbWV6b25lKS5zZWNvbmQoMCkuc3VidHJhY3QoMSwgJ20nKSxcbiAgICAgICAgICAgICAgJ20nLFxuICAgICAgICAgICAgICAnW10nXG4gICAgICAgICAgICApO1xuXG4gICAgICAgICAgY29uc3QgcGFydEMgPVxuICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKVxuICAgICAgICAgICAgICAudHoocmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgPT09XG4gICAgICAgICAgICAgIGRheWpzKGEuc3RhcnREYXRlKVxuICAgICAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgJiZcbiAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpXG4gICAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSA9PT1cbiAgICAgICAgICAgICAgZGF5anMoYS5lbmREYXRlKVxuICAgICAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJyk7XG5cbiAgICAgICAgICBjb25zdCBpc05vdEF2YWlsYWJsZSA9IHBhcnRBIHx8IHBhcnRCIHx8IHBhcnRDO1xuXG4gICAgICAgICAgLy8gY29uc29sZS5sb2coYSwgbmEsICcgYSwgbmEnKVxuXG4gICAgICAgICAgcmV0dXJuIGlzTm90QXZhaWxhYmxlO1xuICAgICAgICB9KTtcblxuICAgICAgICBjb25zb2xlLmxvZyhmb3VuZEluZGV4LCAnIGZvdW5kSW5kZXgnKTtcblxuICAgICAgICBpZiAoZm91bmRJbmRleCAhPT0gdW5kZWZpbmVkICYmIGZvdW5kSW5kZXggPiAtMSkge1xuICAgICAgICAgIHJldHVybiBmYWxzZTtcbiAgICAgICAgfVxuXG4gICAgICAgIHJldHVybiB0cnVlO1xuICAgICAgfSk7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUsXG4gICAgICAnIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHMgc2VydmVyIHRpbWV6b25lJ1xuICAgICk7XG4gICAgcmV0dXJuIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmU7XG4gIH1cblxuICAvLyBub3QgZmlyc3QgZGF5IHN0YXJ0IGZyb20gd29yayBzdGFydCB0aW1lIHNjaGVkdWxlXG5cbiAgY29uc3Qgc3RhcnRUaW1lc0J5U2VuZGVyID0gc2VuZGVyUHJlZmVyZW5jZXMuc3RhcnRUaW1lcztcblxuICBjb25zdCBlbmRUaW1lc0J5U2VuZGVyID0gc2VuZGVyUHJlZmVyZW5jZXMuZW5kVGltZXM7XG5cbiAgY29uc3QgZGF5T2ZXZWVrSW50QXNSZWNlaXZlciA9IGdldElTT0RheShcbiAgICBkYXlqcyhzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmU/LnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihyZWNlaXZlclRpbWV6b25lLCB0cnVlKVxuICAgICAgLnRvRGF0ZSgpXG4gICk7XG4gIGNvbnN0IGRheU9mTW9udGhBc1JlY2VpdmVyID0gZGF5anMoXG4gICAgc2VuZGVyU3RhcnREYXRlSW5SZWNlaXZlclRpbWV6b25lPy5zbGljZSgwLCAxOSlcbiAgKVxuICAgIC50eihyZWNlaXZlclRpbWV6b25lLCB0cnVlKVxuICAgIC5kYXRlKCk7XG5cbiAgLy8gY29udmVydCB0byB1c2VyIHRpbWV6b25lIHNvIGV2ZXJ5dGhpbmcgaXMgbGlua2VkIHRvIHVzZXIgdGltZXpvbmVcbiAgbGV0IGVuZEhvdXJCeVNlbmRlciA9XG4gICAgZW5kVGltZXNCeVNlbmRlcj8uZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludEFzUmVjZWl2ZXIpPy5ob3VyID8/IDIwO1xuICBsZXQgZW5kTWludXRlQnlTZW5kZXIgPVxuICAgIGVuZFRpbWVzQnlTZW5kZXI/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRBc1JlY2VpdmVyKT8ubWludXRlcyA/P1xuICAgIDA7XG5cbiAgLy8gaWYgbGFzdCBkYXkgY2hhbmdlIGVuZCB0aW1lIHRvIGhvc3RTdGFydERhdGUgcHJvdmlkZWRcbiAgaWYgKGlzTGFzdERheSAmJiBzZW5kZXJFbmREYXRlSW5SZWNlaXZlclRpbWV6b25lKSB7XG4gICAgZW5kSG91ckJ5U2VuZGVyID0gZGF5anMoc2VuZGVyRW5kRGF0ZUluUmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgIC50eihzZW5kZXJUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgLy8gY3JlYXRlIHNsb3Qgc2l6ZXNcbiAgICBjb25zdCBmbG9vcmVkVmFsdWUgPSBNYXRoLmZsb29yKDYwIC8gc2xvdER1cmF0aW9uKTtcblxuICAgIGxldCBtaW51dGVWYWx1ZUJ5U2VuZGVyID0gMDtcbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IGZsb29yZWRWYWx1ZTsgaSsrKSB7XG4gICAgICBjb25zdCBlbmRNaW51dGVzID0gKGkgKyAxKSAqIHNsb3REdXJhdGlvbjtcbiAgICAgIGNvbnN0IHN0YXJ0TWludXRlcyA9IGkgKiBzbG90RHVyYXRpb247XG4gICAgICBpZiAoXG4gICAgICAgIGRheWpzKHNlbmRlckVuZERhdGVJblJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgLnR6KHNlbmRlclRpbWV6b25lKVxuICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICBkYXlqcyhzZW5kZXJFbmREYXRlSW5SZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAudHooc2VuZGVyVGltZXpvbmUpXG4gICAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVzKSxcbiAgICAgICAgICAgIGRheWpzKHNlbmRlckVuZERhdGVJblJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgIC50eihzZW5kZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGVzKSxcbiAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgIClcbiAgICAgICkge1xuICAgICAgICBtaW51dGVWYWx1ZUJ5U2VuZGVyID0gc3RhcnRNaW51dGVzO1xuICAgICAgfVxuICAgIH1cblxuICAgIGVuZE1pbnV0ZUJ5U2VuZGVyID0gbWludXRlVmFsdWVCeVNlbmRlcjtcbiAgfVxuXG4gIGNvbnN0IHN0YXJ0SG91ckJ5U2VuZGVyID1cbiAgICAoc3RhcnRUaW1lc0J5U2VuZGVyPy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50QXNSZWNlaXZlcilcbiAgICAgID8uaG91ciBhcyBudW1iZXIpIHx8IDg7XG4gIGNvbnN0IHN0YXJ0TWludXRlQnlTZW5kZXIgPVxuICAgIChzdGFydFRpbWVzQnlTZW5kZXI/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRBc1JlY2VpdmVyKVxuICAgICAgPy5taW51dGVzIGFzIG51bWJlcikgfHwgMDtcblxuICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiBzdGFydEhvdXJCeVNlbmRlcixcbiAgICBtaW51dGVzOiBzdGFydE1pbnV0ZUJ5U2VuZGVyLFxuICB9KTtcbiAgY29uc3QgZW5kRHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgaG91cnM6IGVuZEhvdXJCeVNlbmRlcixcbiAgICBtaW51dGVzOiBlbmRNaW51dGVCeVNlbmRlcixcbiAgfSk7XG4gIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcblxuICBjb25zdCBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZTogQXZhaWxhYmxlU2xvdFR5cGVbXSA9IFtdO1xuICBjb25zb2xlLmxvZyhcbiAgICBzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmUsXG4gICAgZW5kVGltZXNCeVNlbmRlcixcbiAgICBkYXlPZldlZWtJbnRBc1JlY2VpdmVyLFxuICAgIGRheU9mTW9udGhBc1JlY2VpdmVyLFxuICAgIHN0YXJ0SG91ckJ5U2VuZGVyLFxuICAgIHN0YXJ0TWludXRlQnlTZW5kZXIsXG4gICAgZW5kSG91ckJ5U2VuZGVyLFxuICAgIGVuZE1pbnV0ZUJ5U2VuZGVyLFxuICAgIHRpbWV6b25lLFxuICAgIGBzdGFydERhdGUsIGVuZFRpbWVzLCBkYXlPZldlZWtJbnRCeUhvc3QsIGRheU9mTW9udGgsIHN0YXJ0SG91ciwgc3RhcnRNaW51dGUsIGVuZEhvdXIsIGVuZE1pbnV0ZSB0b3RhbE1pbnV0ZXMsIHRpbWV6b25lLCBpbnNpZGUgZmlyc3REYXkgaW5zaWRlIGdlbmVyYXRlQXZhaWxhYmxlc2xvdHNgXG4gICk7XG4gIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IHNsb3REdXJhdGlvbikge1xuICAgIGlmIChpID4gdG90YWxNaW51dGVzKSB7XG4gICAgICBjb250aW51ZTtcbiAgICB9XG5cbiAgICBhdmFpbGFibGVTbG90c0luUmVjZWl2ZXJUaW1lem9uZS5wdXNoKHtcbiAgICAgIGlkOiB1dWlkKCksXG4gICAgICBzdGFydERhdGU6IGRheWpzKHNlbmRlclN0YXJ0RGF0ZUluUmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgLnR6KHNlbmRlclRpbWV6b25lKVxuICAgICAgICAuaG91cihzdGFydEhvdXJCeVNlbmRlcilcbiAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5U2VuZGVyKVxuICAgICAgICAudHoocmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAuZm9ybWF0KCksXG4gICAgICBlbmREYXRlOiBkYXlqcyhzZW5kZXJTdGFydERhdGVJblJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgIC50eihzZW5kZXJUaW1lem9uZSlcbiAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlTZW5kZXIpXG4gICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeVNlbmRlcilcbiAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgIC5hZGQoaSArIHNsb3REdXJhdGlvbiwgJ21pbnV0ZScpXG4gICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgLmZvcm1hdCgpLFxuICAgIH0pO1xuICB9XG5cbiAgY29uc29sZS5sb2coXG4gICAgYXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUsXG4gICAgJyB0aW1lU2xvdHMgaW5zaWRlIGdlbmVyYXRlVGltZVNsb3RzIG5vdCBmaXJzdCBkYXknXG4gICk7XG4gIGNvbnNvbGUubG9nKFxuICAgIG5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lLFxuICAgICcgbm90QXZhaWxhYmxlU2xvdHNJbkV2ZW50VGltZXpvbmUgbm90IGZpcnN0IGRheSdcbiAgKTtcblxuICAvLyBmaWx0ZXIgb3V0IHVuYXZhaWxhYmxlIHRpbWVzXG4gIGNvbnN0IGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmUgPVxuICAgIGF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lLmZpbHRlcigoYSkgPT4ge1xuICAgICAgY29uc3QgZm91bmRJbmRleCA9IG5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lPy5maW5kSW5kZXgoKG5hKSA9PiB7XG4gICAgICAgIGNvbnN0IHBhcnRBID0gZGF5anMoYS5lbmREYXRlKVxuICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKS50eihyZWNlaXZlclRpbWV6b25lKS5zZWNvbmQoMCkuYWRkKDEsICdtJyksXG4gICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKS50eihyZWNlaXZlclRpbWV6b25lKS5zZWNvbmQoMCkuc3VidHJhY3QoMSwgJ20nKSxcbiAgICAgICAgICAgICdtJyxcbiAgICAgICAgICAgICdbXSdcbiAgICAgICAgICApO1xuXG4gICAgICAgIGNvbnN0IHBhcnRCID0gZGF5anMoYS5zdGFydERhdGUpXG4gICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpLnR6KHJlY2VpdmVyVGltZXpvbmUpLnNlY29uZCgwKS5hZGQoMSwgJ20nKSxcbiAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpLnR6KHJlY2VpdmVyVGltZXpvbmUpLnNlY29uZCgwKS5zdWJ0cmFjdCgxLCAnbScpLFxuICAgICAgICAgICAgJ20nLFxuICAgICAgICAgICAgJ1tdJ1xuICAgICAgICAgICk7XG5cbiAgICAgICAgY29uc3QgcGFydEMgPVxuICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpID09PVxuICAgICAgICAgICAgZGF5anMoYS5zdGFydERhdGUpXG4gICAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSAmJlxuICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpXG4gICAgICAgICAgICAudHoocmVjZWl2ZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSA9PT1cbiAgICAgICAgICAgIGRheWpzKGEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgLnR6KHJlY2VpdmVyVGltZXpvbmUpXG4gICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpO1xuXG4gICAgICAgIGNvbnN0IGlzTm90QXZhaWxhYmxlID0gcGFydEEgfHwgcGFydEIgfHwgcGFydEM7XG5cbiAgICAgICAgLy8gY29uc29sZS5sb2coYSwgbmEsICcgYSwgbmEnKVxuXG4gICAgICAgIHJldHVybiBpc05vdEF2YWlsYWJsZTtcbiAgICAgIH0pO1xuXG4gICAgICBjb25zb2xlLmxvZyhmb3VuZEluZGV4LCAnIGZvdW5kSW5kZXgnKTtcblxuICAgICAgaWYgKGZvdW5kSW5kZXggIT09IHVuZGVmaW5lZCAmJiBmb3VuZEluZGV4ID4gLTEpIHtcbiAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgICAgfVxuXG4gICAgICByZXR1cm4gdHJ1ZTtcbiAgICB9KTtcblxuICBjb25zb2xlLmxvZyhcbiAgICBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lLFxuICAgICcgZmlsdGVyZWRBdmFpbGFibGVTbG90cyBpbiByZWNlaXZlclRpbWV6b25lJ1xuICApO1xuICAvLyBjb252ZXJ0IHRvIHJlY2VpdmVyVGltZXpvbmUgYmVmb3JlIHJldHVybmluZyB2YWx1ZXNcbiAgcmV0dXJuIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblJlY2VpdmVyVGltZXpvbmU7XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVBdmFpbGFibGVTbG90c2ZvclRpbWVXaW5kb3cgPSAoXG4gIHdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nLFxuICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gIHNsb3REdXJhdGlvbjogbnVtYmVyLFxuICBzZW5kZXJQcmVmZXJlbmNlczogVXNlclByZWZlcmVuY2VUeXBlLFxuICByZWNlaXZlclRpbWV6b25lOiBzdHJpbmcsXG4gIHNlbmRlclRpbWV6b25lOiBzdHJpbmcsXG4gIG5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lPzogTm90QXZhaWxhYmxlU2xvdFR5cGVbXVxuKSA9PiB7XG4gIGNvbnN0IGRpZmZEYXlzID0gZGF5anMod2luZG93RW5kRGF0ZSkuZGlmZihkYXlqcyh3aW5kb3dTdGFydERhdGUpLCAnZCcpO1xuXG4gIGNvbnN0IHN0YXJ0RGF0ZXNGb3JFYWNoRGF5ID0gW107XG4gIGNvbnN0IGF2YWlsYWJsZVNsb3RzOiBBdmFpbGFibGVTbG90VHlwZVtdID0gW107XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPD0gZGlmZkRheXM7IGkrKykge1xuICAgIHN0YXJ0RGF0ZXNGb3JFYWNoRGF5LnB1c2goXG4gICAgICBkYXlqcyh3aW5kb3dTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoocmVjZWl2ZXJUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmFkZChpLCAnZGF5JylcbiAgICAgICAgLmZvcm1hdCgpXG4gICAgKTtcbiAgfVxuXG4gIGlmIChkaWZmRGF5cyA8IDEpIHtcbiAgICBjb25zdCBnZW5lcmF0ZWRTbG90cyA9IGdlbmVyYXRlQXZhaWxhYmxlU2xvdHNGb3JEYXRlKFxuICAgICAgc2xvdER1cmF0aW9uLFxuICAgICAgZGF5anMod2luZG93U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoocmVjZWl2ZXJUaW1lem9uZSwgdHJ1ZSkuZm9ybWF0KCksXG4gICAgICBzZW5kZXJQcmVmZXJlbmNlcyxcbiAgICAgIHJlY2VpdmVyVGltZXpvbmUsXG4gICAgICBzZW5kZXJUaW1lem9uZSxcbiAgICAgIG5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lLFxuICAgICAgdHJ1ZSxcbiAgICAgIHRydWUsXG4gICAgICBkYXlqcyh3aW5kb3dFbmREYXRlLnNsaWNlKDAsIDE5KSkudHoocmVjZWl2ZXJUaW1lem9uZSwgdHJ1ZSkuZm9ybWF0KClcbiAgICApO1xuICAgIC8vICAwMTIzNDU2Nzg5XG4gICAgLy8gIDIwMjAtMDQtMDJUMDg6MDI6MTctMDU6MDBcbiAgICBhdmFpbGFibGVTbG90cy5wdXNoKC4uLmdlbmVyYXRlZFNsb3RzKTtcbiAgfSBlbHNlIHtcbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IHN0YXJ0RGF0ZXNGb3JFYWNoRGF5Lmxlbmd0aDsgaSsrKSB7XG4gICAgICBjb25zdCBmaWx0ZXJlZE5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lID1cbiAgICAgICAgbm90QXZhaWxhYmxlU2xvdHNJbkV2ZW50VGltZXpvbmU/LmZpbHRlcihcbiAgICAgICAgICAobmEpID0+XG4gICAgICAgICAgICBkYXlqcyhuYT8uc3RhcnREYXRlKS50eihyZWNlaXZlclRpbWV6b25lKS5mb3JtYXQoJ1lZWVktTU0tREQnKSA9PT1cbiAgICAgICAgICAgIGRheWpzKHN0YXJ0RGF0ZXNGb3JFYWNoRGF5Py5baV0pXG4gICAgICAgICAgICAgIC50eihyZWNlaXZlclRpbWV6b25lKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREJylcbiAgICAgICAgKTtcbiAgICAgIGlmIChpID09PSAwKSB7XG4gICAgICAgIGNvbnN0IGdlbmVyYXRlZFNsb3RzID0gZ2VuZXJhdGVBdmFpbGFibGVTbG90c0ZvckRhdGUoXG4gICAgICAgICAgc2xvdER1cmF0aW9uLFxuICAgICAgICAgIHN0YXJ0RGF0ZXNGb3JFYWNoRGF5Py5baV0sXG4gICAgICAgICAgc2VuZGVyUHJlZmVyZW5jZXMsXG4gICAgICAgICAgcmVjZWl2ZXJUaW1lem9uZSxcbiAgICAgICAgICBzZW5kZXJUaW1lem9uZSxcbiAgICAgICAgICBmaWx0ZXJlZE5vdEF2YWlsYWJsZVNsb3RzSW5FdmVudFRpbWV6b25lLFxuICAgICAgICAgIHRydWUsXG4gICAgICAgICAgZmFsc2UsXG4gICAgICAgICAgZGF5anMod2luZG93RW5kRGF0ZS5zbGljZSgwLCAxOSkpLnR6KHJlY2VpdmVyVGltZXpvbmUsIHRydWUpLmZvcm1hdCgpXG4gICAgICAgICk7XG4gICAgICAgIC8vICAwMTIzNDU2Nzg5XG4gICAgICAgIC8vICAyMDIwLTA0LTAyVDA4OjAyOjE3LTA1OjAwXG4gICAgICAgIGF2YWlsYWJsZVNsb3RzLnB1c2goLi4uZ2VuZXJhdGVkU2xvdHMpO1xuXG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfVxuXG4gICAgICBpZiAoaSA9PT0gc3RhcnREYXRlc0ZvckVhY2hEYXkubGVuZ3RoIC0gMSkge1xuICAgICAgICBjb25zdCBnZW5lcmF0ZWRTbG90cyA9IGdlbmVyYXRlQXZhaWxhYmxlU2xvdHNGb3JEYXRlKFxuICAgICAgICAgIHNsb3REdXJhdGlvbixcbiAgICAgICAgICBzdGFydERhdGVzRm9yRWFjaERheT8uW2ldLFxuICAgICAgICAgIHNlbmRlclByZWZlcmVuY2VzLFxuICAgICAgICAgIHJlY2VpdmVyVGltZXpvbmUsXG4gICAgICAgICAgc2VuZGVyVGltZXpvbmUsXG4gICAgICAgICAgZmlsdGVyZWROb3RBdmFpbGFibGVTbG90c0luRXZlbnRUaW1lem9uZSxcbiAgICAgICAgICBmYWxzZSxcbiAgICAgICAgICB0cnVlLFxuICAgICAgICAgIGRheWpzKHdpbmRvd0VuZERhdGUuc2xpY2UoMCwgMTkpKS50eihyZWNlaXZlclRpbWV6b25lLCB0cnVlKS5mb3JtYXQoKVxuICAgICAgICApO1xuXG4gICAgICAgIGF2YWlsYWJsZVNsb3RzLnB1c2goLi4uZ2VuZXJhdGVkU2xvdHMpO1xuXG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfVxuXG4gICAgICBjb25zdCBnZW5lcmF0ZWRTbG90cyA9IGdlbmVyYXRlQXZhaWxhYmxlU2xvdHNGb3JEYXRlKFxuICAgICAgICBzbG90RHVyYXRpb24sXG4gICAgICAgIHN0YXJ0RGF0ZXNGb3JFYWNoRGF5Py5baV0sXG4gICAgICAgIHNlbmRlclByZWZlcmVuY2VzLFxuICAgICAgICByZWNlaXZlclRpbWV6b25lLFxuICAgICAgICBzZW5kZXJUaW1lem9uZSxcbiAgICAgICAgZmlsdGVyZWROb3RBdmFpbGFibGVTbG90c0luRXZlbnRUaW1lem9uZVxuICAgICAgKTtcblxuICAgICAgYXZhaWxhYmxlU2xvdHMucHVzaCguLi5nZW5lcmF0ZWRTbG90cyk7XG4gICAgfVxuICB9XG5cbiAgcmV0dXJuIHsgYXZhaWxhYmxlU2xvdHMgfTtcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZUF2YWlsYWJpbGl0eSA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHdpbmRvd1N0YXJ0RGF0ZUluU2VuZGVyVGltZXpvbmU6IHN0cmluZyxcbiAgd2luZG93RW5kRGF0ZUluU2VuZGVyVGltZXpvbmU6IHN0cmluZyxcbiAgc2VuZGVyVGltZXpvbmU6IHN0cmluZyxcbiAgcmVjZWl2ZXJUaW1lem9uZTogc3RyaW5nLFxuICBzbG90RHVyYXRpb246IG51bWJlclxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb2xkRXZlbnRzSW5FdmVudFRpbWV6b25lID0gYXdhaXQgbGlzdEV2ZW50c0ZvclVzZXJHaXZlbkRhdGVzKFxuICAgICAgdXNlcklkLFxuICAgICAgd2luZG93U3RhcnREYXRlSW5TZW5kZXJUaW1lem9uZSxcbiAgICAgIHdpbmRvd0VuZERhdGVJblNlbmRlclRpbWV6b25lXG4gICAgKTtcblxuICAgIGNvbnNvbGUubG9nKG9sZEV2ZW50c0luRXZlbnRUaW1lem9uZSwgJyBvbGRFdmVudHNJbkV2ZW50VGltZXpvbmUnKTtcblxuICAgIGlmICghb2xkRXZlbnRzSW5FdmVudFRpbWV6b25lIHx8ICEob2xkRXZlbnRzSW5FdmVudFRpbWV6b25lPy5sZW5ndGggPiAwKSkge1xuICAgICAgY29uc29sZS5sb2coJ25vIG9sZCBldmVudHMgaW4gZ2VuZXJhdGVBdmFpbGFiaWxpdHknKTtcbiAgICB9XG5cbiAgICBjb25zdCBvbGRFdmVudHNJbkV2ZW50VGltZXpvbmVGb3JtYXR0ZWQgPSBvbGRFdmVudHNJbkV2ZW50VGltZXpvbmU/Lm1hcChcbiAgICAgIChlKSA9PiAoe1xuICAgICAgICAuLi5lLFxuICAgICAgICBzdGFydERhdGU6IGRheWpzKGU/LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGU/LnRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgZW5kRGF0ZTogZGF5anMoZT8uZW5kRGF0ZS5zbGljZSgwLCAxOSkpLnR6KGU/LnRpbWV6b25lLCB0cnVlKS5mb3JtYXQoKSxcbiAgICAgICAgdGltZXpvbmU6IGU/LnRpbWV6b25lLFxuICAgICAgfSlcbiAgICApO1xuXG4gICAgY29uc3Qgbm90QXZhaWxhYmxlRnJvbUV2ZW50czogTm90QXZhaWxhYmxlU2xvdFR5cGVbXSA9XG4gICAgICBvbGRFdmVudHNJbkV2ZW50VGltZXpvbmVGb3JtYXR0ZWQ/Lm1hcCgoZSkgPT4gKHtcbiAgICAgICAgc3RhcnREYXRlOiBlPy5zdGFydERhdGUsXG4gICAgICAgIGVuZERhdGU6IGU/LmVuZERhdGUsXG4gICAgICB9KSk7XG5cbiAgICBjb25zdCB1c2VyUHJlZmVyZW5jZXMgPSBhd2FpdCBnZXRVc2VyUHJlZmVyZW5jZXModXNlcklkKTtcblxuICAgIGNvbnN0IHsgYXZhaWxhYmxlU2xvdHM6IGF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lIH0gPVxuICAgICAgYXdhaXQgZ2VuZXJhdGVBdmFpbGFibGVTbG90c2ZvclRpbWVXaW5kb3coXG4gICAgICAgIHdpbmRvd1N0YXJ0RGF0ZUluU2VuZGVyVGltZXpvbmUsXG4gICAgICAgIHdpbmRvd0VuZERhdGVJblNlbmRlclRpbWV6b25lLFxuICAgICAgICBzbG90RHVyYXRpb24sXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgcmVjZWl2ZXJUaW1lem9uZSxcbiAgICAgICAgc2VuZGVyVGltZXpvbmUsXG4gICAgICAgIG5vdEF2YWlsYWJsZUZyb21FdmVudHM/Lmxlbmd0aCA+IDAgPyBub3RBdmFpbGFibGVGcm9tRXZlbnRzIDogdW5kZWZpbmVkXG4gICAgICApO1xuXG4gICAgcmV0dXJuIGF2YWlsYWJsZVNsb3RzSW5SZWNlaXZlclRpbWV6b25lO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2VuZXJhdGUgYXZhaWxhYmlsaXR5Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzX3N1bW1hcml6ZV9hdmFpbGFiaWxpdHkgPSBhc3luYyAoXG4gIGJvZHk6IFN1bW1hcml6ZURheUF2YWlsYWJpbGl0eVR5cGVcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHVzZXJJZCA9IGJvZHk/LnVzZXJJZDtcbiAgICBjb25zdCBkYXlBdmFpbGFiaWxpdHlMaXN0ID0gYm9keT8uZGF5QXZhaWxhYmlsaXR5TGlzdDtcblxuICAgIGNvbnN0IG9wZW5haSA9IG5ldyBPcGVuQUkoe1xuICAgICAgYXBpS2V5OiBkZWZhdWx0T3BlbkFJQVBJS2V5LFxuICAgIH0pO1xuXG4gICAgY29uc3Qgc3VtbWFyaXplZFJlcyA9IGF3YWl0IGNhbGxPcGVuQUkoXG4gICAgICBzdW1tYXJpemVBdmFpbGFiaWxpdHlSZXNwb25zZXNQcm9tcHQsXG4gICAgICBvcGVuQUlDaGF0R1BUTW9kZWwsXG4gICAgICBkYXlBdmFpbGFiaWxpdHlMaXN0LFxuICAgICAgb3BlbmFpLFxuICAgICAgc3VtbWFyaXplQXZhaWxhYmlsaXR5UmVzcG9uc2VzUHJvbXB0RXhhbXBsZUlucHV0LFxuICAgICAgc3VtbWFyaXplQXZhaWxhYmlsaXR5UmVzcG9uc2VzUHJvbXB0RXhhbXBsZU91dHB1dFxuICAgICk7XG5cbiAgICByZXR1cm4gc3VtbWFyaXplZFJlcztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHByb2Nlc3Mgc3VtbWFyaXplIGF2YWlsYWJpbGl0eScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc19kYXlfYXZhaWxpYmlsaXR5ID0gYXN5bmMgKGJvZHk6IERheUF2YWlsYWJpbGl0eVR5cGUpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB1c2VySWQgPSBib2R5Py51c2VySWQ7XG4gICAgY29uc3Qgd2luZG93U3RhcnREYXRlID0gYm9keT8ud2luZG93U3RhcnREYXRlO1xuICAgIGNvbnN0IHdpbmRvd0VuZERhdGUgPSBib2R5Py53aW5kb3dFbmREYXRlO1xuICAgIGNvbnN0IHNlbmRlclRpbWV6b25lID0gYm9keT8uc2VuZGVyVGltZXpvbmU7XG4gICAgY29uc3QgcmVjZWl2ZXJUaW1lem9uZSA9IGJvZHk/LnJlY2VpdmVyVGltZXpvbmU7XG4gICAgY29uc3Qgc2xvdER1cmF0aW9uID0gYm9keT8uc2xvdER1cmF0aW9uO1xuXG4gICAgY29uc3Qgb3BlbmFpID0gbmV3IE9wZW5BSSh7XG4gICAgICBhcGlLZXk6IGRlZmF1bHRPcGVuQUlBUElLZXksXG4gICAgfSk7XG5cbiAgICAvLyBnZXQgYXZhaWxhYmlsaXR5XG4gICAgY29uc3QgYXZhaWxhYmlsaXR5ID0gYXdhaXQgZ2VuZXJhdGVBdmFpbGFiaWxpdHkoXG4gICAgICB1c2VySWQsXG4gICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgc2VuZGVyVGltZXpvbmUsXG4gICAgICByZWNlaXZlclRpbWV6b25lLFxuICAgICAgcGFyc2VJbnQoc2xvdER1cmF0aW9uLCAxMClcbiAgICApO1xuXG4gICAgaWYgKCEoYXZhaWxhYmlsaXR5Py5sZW5ndGggPiAwKSkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBhdmFpbGFiaWxpdHkgcHJlc2VudCcpO1xuICAgIH1cblxuICAgIGNvbnN0IHVuaXFEYXRlcyA9IF8udW5pcUJ5KGF2YWlsYWJpbGl0eSwgKGN1cnIpID0+XG4gICAgICBkYXlqcyhjdXJyPy5zdGFydERhdGUpLnR6KHJlY2VpdmVyVGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpXG4gICAgKTtcblxuICAgIGxldCBhdmFpbGFiaWxpdHlUZXh0ID0gJyc7XG5cbiAgICBjb25zdCBwcm9tcHQxID0gc3VtbWFyaXplQXZhaWxhYmlsaXR5UHJvbXB0O1xuXG4gICAgY29uc3QgZXhhbXBsZUlucHV0MSA9IHN1bW1hcml6ZUF2YWlsYWJpbGl0eUV4YW1wbGVJbnB1dDtcblxuICAgIGNvbnN0IGV4YW1wbGVPdXRwdXQxID0gc3VtbWFyaXplQXZhaWxhYmlsaXR5RXhhbXBsZU91dHB1dDtcblxuICAgIGxldCBvcGVuQUlBdmFpbGFiaWxpdHlSZXMgPSAnJztcblxuICAgIGZvciAoY29uc3QgdW5pcURhdGUgb2YgdW5pcURhdGVzKSB7XG4gICAgICBjb25zdCBmaWx0ZXJlZEF2YWlsYWJpbGl0eSA9IGF2YWlsYWJpbGl0eT8uZmlsdGVyKFxuICAgICAgICAoYSkgPT5cbiAgICAgICAgICBkYXlqcyhhPy5zdGFydERhdGUpLnR6KHJlY2VpdmVyVGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpID09PVxuICAgICAgICAgIGRheWpzKHVuaXFEYXRlPy5zdGFydERhdGUpLnR6KHJlY2VpdmVyVGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpXG4gICAgICApO1xuXG4gICAgICBpZiAoZmlsdGVyZWRBdmFpbGFiaWxpdHk/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgYXZhaWxhYmlsaXR5VGV4dCArPVxuICAgICAgICAgIGAke2RheWpzKHVuaXFEYXRlPy5zdGFydERhdGUpLnR6KHJlY2VpdmVyVGltZXpvbmUpLmZvcm1hdCgnTCcpfSAtICR7ZmlsdGVyZWRBdmFpbGFiaWxpdHk/Lm1hcCgoY3VycikgPT4gYCR7ZGF5anMoY3Vycj8uc3RhcnREYXRlKS50eihyZWNlaXZlclRpbWV6b25lKS5mb3JtYXQoJ0xUJyl9IC0gJHtkYXlqcyhjdXJyPy5lbmREYXRlKS50eihyZWNlaXZlclRpbWV6b25lKS5mb3JtYXQoJ0xUJyl9LGApPy5yZWR1Y2UoKHByZXYsIGN1cnIpID0+IGAke3ByZXZ9ICR7Y3Vycn1gLCAnJyl9YCArXG4gICAgICAgICAgJ1xcblxcbic7XG5cbiAgICAgICAgY29uc3QgbWluaUF2YWlsYWJpbGl0eVRleHQgPVxuICAgICAgICAgIGAke2RheWpzKHVuaXFEYXRlPy5zdGFydERhdGUpLnR6KHJlY2VpdmVyVGltZXpvbmUpLmZvcm1hdCgnTCcpfSAtICR7ZmlsdGVyZWRBdmFpbGFiaWxpdHk/Lm1hcCgoY3VycikgPT4gYCR7ZGF5anMoY3Vycj8uc3RhcnREYXRlKS50eihyZWNlaXZlclRpbWV6b25lKS5mb3JtYXQoJ0xUJyl9IC0gJHtkYXlqcyhjdXJyPy5lbmREYXRlKS50eihyZWNlaXZlclRpbWV6b25lKS5mb3JtYXQoJ0xUJyl9LGApPy5yZWR1Y2UoKHByZXYsIGN1cnIpID0+IGAke3ByZXZ9ICR7Y3Vycn1gLCAnJyl9YCArXG4gICAgICAgICAgJ1xcblxcbic7XG5cbiAgICAgICAgY29uc3QgbWluaVVzZXJEYXRhID0gYE15IGF2YWlsYWJpbGl0eTogYCArIG1pbmlBdmFpbGFiaWxpdHlUZXh0O1xuXG4gICAgICAgIGNvbnNvbGUubG9nKG1pbmlVc2VyRGF0YSwgJyBuZXdBdmFpbGFiaWxpdHlQcm9tcHQnKTtcblxuICAgICAgICBjb25zdCBtaW5pT3BlbkFJQXZhaWxhYmlsaXR5UmVzID0gYXdhaXQgY2FsbE9wZW5BSShcbiAgICAgICAgICBwcm9tcHQxLFxuICAgICAgICAgIG9wZW5BSUNoYXRHUFRNb2RlbCxcbiAgICAgICAgICBtaW5pVXNlckRhdGEsXG4gICAgICAgICAgb3BlbmFpLFxuICAgICAgICAgIGV4YW1wbGVJbnB1dDEsXG4gICAgICAgICAgZXhhbXBsZU91dHB1dDFcbiAgICAgICAgKTtcblxuICAgICAgICAvLyB2YWxpZGF0ZSBvcGVuYWkgcmVzXG4gICAgICAgIGlmICghbWluaU9wZW5BSUF2YWlsYWJpbGl0eVJlcykge1xuICAgICAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgICAgICdubyBvcGVuQUlBdmFpbGFiaWxpdHlSZXMgcHJlc2VudCBpbnNpZGUgYXBwb2ludG1lbnRSZXF1ZXN0J1xuICAgICAgICAgICk7XG4gICAgICAgIH1cblxuICAgICAgICBvcGVuQUlBdmFpbGFiaWxpdHlSZXMgKz0gJ1xcbicgKyBtaW5pT3BlbkFJQXZhaWxhYmlsaXR5UmVzO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKG9wZW5BSUF2YWlsYWJpbGl0eVJlcywgJyBvcGVuQUlBdmFpbGFiaWxpdHlSZXMnKTtcblxuICAgIHJldHVybiBvcGVuQUlBdmFpbGFiaWxpdHlSZXM7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIGRheSBhdmFpbGFiaWxpdHknKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGluc2VydEF0dGVuZGVlc2ZvckV2ZW50ID0gYXN5bmMgKGF0dGVuZGVlczogQXR0ZW5kZWVUeXBlW10pID0+IHtcbiAgdHJ5IHtcbiAgICAvLyB2YWxpZGF0ZVxuICAgIGlmICghKGF0dGVuZGVlcz8uZmlsdGVyKChhKSA9PiAhIWE/LmV2ZW50SWQpPy5sZW5ndGggPiAwKSkge1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnSW5zZXJ0QXR0ZW5kZWVzRm9yRXZlbnQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgbXV0YXRpb24gSW5zZXJ0QXR0ZW5kZWVzRm9yRXZlbnQoJGF0dGVuZGVlczogW0F0dGVuZGVlX2luc2VydF9pbnB1dCFdISkge1xuICAgICAgICAgICAgICAgIGluc2VydF9BdHRlbmRlZShvYmplY3RzOiAkYXR0ZW5kZWVzKSB7XG4gICAgICAgICAgICAgICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgICAgICAgICAgICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGFkZGl0aW9uYWxHdWVzdHNcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvbW1lbnRcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvbnRhY3RJZFxuICAgICAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgICAgICAgICAgICAgIGVtYWlsc1xuICAgICAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgICAgIGltQWRkcmVzc2VzXG4gICAgICAgICAgICAgICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICAgICAgICAgICAgICBvcHRpb25hbFxuICAgICAgICAgICAgICAgICAgICAgICAgcGhvbmVOdW1iZXJzXG4gICAgICAgICAgICAgICAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgICAgICAgICAgICAgICAgcmVzcG9uc2VTdGF0dXNcbiAgICAgICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgYXR0ZW5kZWVzLFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZToge1xuICAgICAgZGF0YToge1xuICAgICAgICBpbnNlcnRfQXR0ZW5kZWU6IHsgYWZmZWN0ZWRfcm93czogbnVtYmVyOyByZXR1cm5pbmc6IEF0dGVuZGVlVHlwZVtdIH07XG4gICAgICB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgcmVzcG9uc2U/LmRhdGE/Lmluc2VydF9BdHRlbmRlZT8ucmV0dXJuaW5nLFxuICAgICAgJyB0aGlzIGlzIHJlc3BvbnNlIGluIGluc2VydEF0dGVuZGVlcydcbiAgICApO1xuICAgIHJlc3BvbnNlPy5kYXRhPy5pbnNlcnRfQXR0ZW5kZWU/LnJldHVybmluZy5mb3JFYWNoKChyKSA9PlxuICAgICAgY29uc29sZS5sb2cociwgJyByZXNwb25zZSBpbiBpbnNlcnRBdHRlbmRlZXMnKVxuICAgICk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBpbnNlcnQgQXR0ZW5kZWVzIGZvciBuZXcgZXZlbnQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGRlbGV0ZUF0dGVuZGVlc1dpdGhJZHMgPSBhc3luYyAoXG4gIGV2ZW50SWRzOiBzdHJpbmdbXSxcbiAgdXNlcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIC8vIHZhbGlkYXRlXG4gICAgaWYgKCEoZXZlbnRJZHM/LmZpbHRlcigoZSkgPT4gISFlKT8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHJldHVybjtcbiAgICB9XG4gICAgZXZlbnRJZHMuZm9yRWFjaCgoZSkgPT5cbiAgICAgIGNvbnNvbGUubG9nKGUsICcgZXZlbnRJZHMgaW5zaWRlIGRlbGV0ZVJlbWluZGVyc1dpdGhJZHMnKVxuICAgICk7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdEZWxldGVBdHRlbmRlZXNXaXRoRXZlbnRJZHMnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgbXV0YXRpb24gRGVsZXRlQXR0ZW5kZWVzV2l0aEV2ZW50SWRzKCR1c2VySWQ6IHV1aWQhLCAkZXZlbnRJZHM6IFtTdHJpbmchXSEpIHtcbiAgICAgICAgICAgICAgICBkZWxldGVfQXR0ZW5kZWUod2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9LCBldmVudElkOiB7X2luOiAkZXZlbnRJZHN9fSkge1xuICAgICAgICAgICAgICAgICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICAgICAgICAgICAgICAgIHJldHVybmluZyB7XG4gICAgICAgICAgICAgICAgICAgICAgICBhZGRpdGlvbmFsR3Vlc3RzXG4gICAgICAgICAgICAgICAgICAgICAgICBjb21tZW50XG4gICAgICAgICAgICAgICAgICAgICAgICBjb250YWN0SWRcbiAgICAgICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICAgICAgICAgICAgICBlbWFpbHNcbiAgICAgICAgICAgICAgICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgICAgICBpbUFkZHJlc3Nlc1xuICAgICAgICAgICAgICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgICAgICAgICAgICAgb3B0aW9uYWxcbiAgICAgICAgICAgICAgICAgICAgICAgIHBob25lTnVtYmVyc1xuICAgICAgICAgICAgICAgICAgICAgICAgcmVzb3VyY2VcbiAgICAgICAgICAgICAgICAgICAgICAgIHJlc3BvbnNlU3RhdHVzXG4gICAgICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuXG4gICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIGV2ZW50SWRzLFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuICAgIGNvbnNvbGUubG9nKHJlc3BvbnNlLCAnIHRoaXMgaXMgcmVzcG9uc2UgaW4gZGVsZXRlQXR0ZW5kZWVzV2l0aElkcycpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyBkZWxldGVBdHRlbmRlZXNXaXRoSWRzJyk7XG4gIH1cbn07XG4iXX0=